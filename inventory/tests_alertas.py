from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.test import TestCase
from io import StringIO

from accounts.roles import ADMIN, ALMACEN, COMPRAS, asignar_rol
from inventory import alertas
from inventory.models import AlertaStock
from inventory.tests import crear_datos


class AlertasPorCorreoTests(TestCase):
    def setUp(self):
        self.d = crear_datos()  # 10 unidades, mínimo 2
        self.inventario = self.d["inventario"]
        User = get_user_model()
        for nombre, rol, correo in (("alm", ALMACEN, "alm@ejemplo.com"), ("adm", ADMIN, "adm@ejemplo.com"),
                                    ("com", COMPRAS, "com@ejemplo.com"), ("sin", ALMACEN, "")):
            usuario = User.objects.create_user(username=nombre, password="test-only", email=correo)
            asignar_rol(usuario, rol)

    def bajar(self, cantidad):
        self.inventario.cantidad = cantidad
        self.inventario.save()

    def test_destinatarios_son_admin_y_almacen_con_correo(self):
        self.assertEqual(alertas.destinatarios(), ["adm@ejemplo.com", "alm@ejemplo.com"])

    def test_no_avisa_si_hay_existencia_suficiente(self):
        self.assertFalse(alertas.revisar(self.inventario.pk))
        self.assertEqual(len(mail.outbox), 0)

    def test_avisa_una_sola_vez_mientras_siga_bajo(self):
        self.bajar(2)
        self.assertTrue(alertas.revisar(self.inventario.pk))
        self.assertFalse(alertas.revisar(self.inventario.pk))
        self.bajar(1)
        self.assertFalse(alertas.revisar(self.inventario.pk))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Producto", mail.outbox[0].subject)
        self.assertEqual(sorted(mail.outbox[0].to), ["adm@ejemplo.com", "alm@ejemplo.com"])
        self.assertIn("existencia 2", mail.outbox[0].body)

    def test_se_rearma_al_recuperar_y_vuelve_a_avisar(self):
        self.bajar(1)
        alertas.revisar(self.inventario.pk)
        self.bajar(10)
        alertas.revisar(self.inventario.pk)
        self.assertIsNone(AlertaStock.objects.get().notificado)
        self.bajar(0)
        alertas.revisar(self.inventario.pk)
        self.assertEqual(len(mail.outbox), 2)

    def test_producto_inactivo_no_avisa(self):
        producto = self.d["producto"]
        producto.activo = False
        producto.save()
        self.bajar(0)
        self.assertFalse(alertas.revisar(self.inventario.pk))

    def test_sin_destinatarios_no_marca_como_avisado(self):
        get_user_model().objects.update(email="")
        self.bajar(0)
        self.assertFalse(alertas.revisar(self.inventario.pk))
        self.assertFalse(AlertaStock.objects.exists())

    def test_fallo_de_correo_no_rompe_y_se_reintenta_despues(self):
        from unittest.mock import patch

        self.bajar(0)
        with patch("inventory.alertas.send_mail", side_effect=OSError("sin red")):
            self.assertFalse(alertas.revisar(self.inventario.pk))
        self.assertFalse(AlertaStock.objects.exists())
        self.assertTrue(alertas.revisar(self.inventario.pk))

    def test_guardar_el_inventario_dispara_el_aviso_al_confirmar(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.bajar(1)
        self.assertEqual(len(mail.outbox), 1)

    def test_comando_envia_resumen_unico_y_no_repite(self):
        self.bajar(0)
        salida = StringIO()
        call_command("enviar_alertas", stdout=salida)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("1 producto", salida.getvalue())
        call_command("enviar_alertas", stdout=salida)
        self.assertEqual(len(mail.outbox), 1)
        call_command("enviar_alertas", "--todos", stdout=salida)
        self.assertEqual(len(mail.outbox), 2)
