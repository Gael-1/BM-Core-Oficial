import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.roles import ALMACEN, asignar_rol
from api import webhooks
from api.models import Webhook
from inventory.tests import crear_datos
from ventas import services


class WebhooksTests(TestCase):
    def setUp(self):
        self.d = crear_datos()
        self.usuario = self.d["usuario"]
        self.client.force_login(self.usuario)

    def test_firma_hmac_es_verificable(self):
        cuerpo = b'{"a":1}'
        self.assertEqual(webhooks.firmar("secreto", cuerpo), webhooks.firmar("secreto", cuerpo))
        self.assertNotEqual(webhooks.firmar("secreto", cuerpo), webhooks.firmar("otro", cuerpo))

    def test_crear_desde_la_pantalla_genera_secreto(self):
        respuesta = self.client.post(reverse("api:webhooks"), {
            "nombre": "ERP", "url": "https://erp.ejemplo.com/hook", "eventos": ["venta.creada", "stock.bajo"]})
        self.assertRedirects(respuesta, reverse("api:webhooks"))
        hook = Webhook.objects.get()
        self.assertEqual(len(hook.secreto), 48)
        self.assertEqual(hook.lista_eventos(), ["venta.creada", "stock.bajo"])

    def test_rechaza_urls_que_no_son_http(self):
        self.client.post(reverse("api:webhooks"), {"nombre": "X", "url": "ftp://x.com/a", "eventos": ["venta.creada"]})
        self.assertFalse(Webhook.objects.exists())

    def test_solo_el_administrador_los_gestiona(self):
        alm = get_user_model().objects.create_user(username="alm", password="test-only")
        asignar_rol(alm, ALMACEN)
        self.client.force_login(alm)
        self.assertNotEqual(self.client.get(reverse("api:webhooks")).status_code, 200)

    def test_emite_solo_a_los_suscritos_y_activos(self):
        Webhook.objects.create(nombre="A", url="https://a.com/h", eventos="venta.creada")
        Webhook.objects.create(nombre="B", url="https://b.com/h", eventos="stock.bajo")
        Webhook.objects.create(nombre="C", url="https://c.com/h", eventos="venta.creada", activo=False)
        with patch("api.webhooks._despachar") as despachar, self.captureOnCommitCallbacks(execute=True):
            webhooks.emitir("venta.creada", {"folio": "V-1"})
        self.assertEqual(despachar.call_count, 1)
        hook, evento, cuerpo = despachar.call_args.args
        self.assertEqual((hook.nombre, evento), ("A", "venta.creada"))
        self.assertEqual(json.loads(cuerpo)["datos"], {"folio": "V-1"})

    def test_una_venta_dispara_el_aviso(self):
        Webhook.objects.create(nombre="A", url="https://a.com/h", eventos="venta.creada")
        linea = {"producto": self.d["producto"], "cantidad": 1, "precio_unitario": None}
        with patch("api.webhooks._despachar") as despachar, self.captureOnCommitCallbacks(execute=True):
            venta, _ = services.crear_venta(self.usuario, self.d["almacen"], [linea])
        self.assertEqual(despachar.call_count, 1)
        self.assertEqual(json.loads(despachar.call_args.args[2])["datos"]["folio"], venta.folio)

    def test_un_destino_caido_no_rompe_el_envio(self):
        hook = Webhook.objects.create(nombre="A", url="https://a.com/h", eventos="venta.creada")
        with patch("api.webhooks.urllib.request.urlopen", side_effect=OSError("sin red")):
            webhooks._enviar(hook, "venta.creada", b"{}")
        hook.refresh_from_db()
        self.assertIn("sin red", hook.ultimo_estado)
        self.assertIsNotNone(hook.ultimo_envio)

    def test_pausar_y_eliminar(self):
        hook = Webhook.objects.create(nombre="A", url="https://a.com/h", eventos="venta.creada")
        self.client.post(reverse("api:webhook_alternar", args=[hook.pk]))
        hook.refresh_from_db()
        self.assertFalse(hook.activo)
        self.client.post(reverse("api:webhook_eliminar", args=[hook.pk]))
        self.assertFalse(Webhook.objects.exists())
