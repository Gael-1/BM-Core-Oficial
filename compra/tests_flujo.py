"""Flujo completo con usuarios de cada rol: compra -> autorización -> recepción -> traspaso -> reporte."""
import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.roles import ADMIN, ALMACEN, COMPRAS, CONSULTA, asignar_rol
from compra.models import EstatusChoices, OrdenDeCompra
from inventory import services
from inventory.models import Almacen, Existencia_Almacen, Inventario_Producto, Registro_Inventario, motivo_movimiento
from inventory.tests import crear_datos


class FlujoCompletoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.d = crear_datos()
        User = get_user_model()
        cls.usuarios = {}
        for rol in (ADMIN, ALMACEN, COMPRAS, CONSULTA):
            usuario = User.objects.create_user(username=f"flujo_{rol.lower()}", password="test-only")
            asignar_rol(usuario, rol)
            cls.usuarios[rol] = usuario
        cls.bodega = Almacen.objects.create(nombre="Bodega norte", negocio=cls.d["negocio"])

    def entrar(self, rol):
        self.client.force_login(self.usuarios[rol])

    def test_flujo_de_punta_a_punta(self):
        d = self.d
        producto = d["producto"]
        # 1. Compras solicita 5 piezas.
        self.entrar(COMPRAS)
        respuesta = self.client.post(reverse("compra:add"), {
            "numero_de_orden": "X", "subtotal": "0.01", "total": "0.01",
            "proveedor": d["proveedor"].pk, "negocio": d["negocio"].pk,
            "productos_json": json.dumps([{"producto_id": producto.pk, "cantidad": 5}]),
        })
        self.assertEqual(respuesta.status_code, 302)
        orden = OrdenDeCompra.objects.get()
        self.assertEqual(orden.estatus, EstatusChoices.PENDIENTE)

        # 2. Quien solicita no puede autorizar ni recibir; el almacenista tampoco autoriza.
        self.assertEqual(self.client.post(reverse("compra:autorizar_od", args=[orden.pk])).status_code, 403)
        self.assertEqual(self.client.post(reverse("compra:completar_orden", args=[orden.pk])).status_code, 403)
        self.entrar(ALMACEN)
        self.assertEqual(self.client.post(reverse("compra:autorizar_od", args=[orden.pk])).status_code, 403)

        # 3. El administrador autoriza.
        self.entrar(ADMIN)
        self.client.post(reverse("compra:autorizar_od", args=[orden.pk]))
        orden.refresh_from_db()
        self.assertEqual(orden.estatus, EstatusChoices.AUTORIZADA)

        # 4. El almacenista recibe: el total pasa de 10 a 15 y queda en el almacén por defecto.
        self.entrar(ALMACEN)
        self.client.post(reverse("compra:completar_orden", args=[orden.pk]))
        orden.refresh_from_db()
        self.assertEqual(orden.estatus, EstatusChoices.COMPLETADA)
        inventario = Inventario_Producto.objects.get(producto_id=producto)
        self.assertEqual(inventario.cantidad, 15)
        self.assertEqual(services.existencia_en(inventario, d["almacen"]), 15)

        # 5. Traspaso de 6 piezas a la bodega norte: el total no cambia.
        respuesta = self.client.post(reverse("inventory:traspaso"), {
            "producto": producto.pk, "almacen_origen": d["almacen"].pk,
            "almacen_destino": self.bodega.pk, "cantidad": 6})
        self.assertEqual(respuesta.status_code, 302)
        inventario.refresh_from_db()
        self.assertEqual(inventario.cantidad, 15)
        self.assertEqual(services.existencia_en(inventario, d["almacen"]), 9)
        self.assertEqual(services.existencia_en(inventario, self.bodega), 6)

        # 6. No se puede traspasar más de lo que hay en el origen.
        respuesta = self.client.post(reverse("inventory:traspaso"), {
            "producto": producto.pk, "almacen_origen": self.bodega.pk,
            "almacen_destino": d["almacen"].pk, "cantidad": 7})
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(services.existencia_en(inventario, self.bodega), 6)

        # 7. Una salida registrada en la bodega baja el total y esa existencia.
        self.client.post(reverse("inventory:movimiento"), {
            "producto": producto.pk, "tipo_movimiento": "SALIDA", "cantidad": 2,
            "almacen": self.bodega.pk,
            "motivo": motivo_movimiento.objects.filter(activo=True).first().pk})
        inventario.refresh_from_db()
        self.assertEqual(inventario.cantidad, 13)
        self.assertEqual(services.existencia_en(inventario, self.bodega), 4)
        self.assertEqual(sum(e.cantidad for e in Existencia_Almacen.objects.filter(inventario=inventario)), 13)

        # 8. El inventario del negocio suma ambos almacenes.
        filas = services.inventario_de_negocio(d["negocio"])
        self.assertEqual(filas[0]["cantidad"], 13)

        # 9. Consulta puede ver el reporte y descargar el CSV, pero no registrar movimientos.
        self.entrar(CONSULTA)
        csv = self.client.get(reverse("reportes:inicio"), {"exportar": "csv"})
        self.assertEqual(csv.status_code, 200)
        texto = csv.content.decode("utf-8")
        for esperado in ("ENTRADA", "TRASPASO", "SALIDA", "Bodega norte", orden.numero_de_orden):
            self.assertIn(esperado, texto)
        self.assertEqual(Registro_Inventario.objects.count(), 3)
        self.assertEqual(self.client.post(reverse("inventory:movimiento"), {}).status_code, 403)


class AutorizacionAutomaticaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.d = crear_datos()
        User = get_user_model()
        cls.compras = User.objects.create_user(username="auto_compras", password="test-only")
        asignar_rol(cls.compras, COMPRAS)
        cls.admin = User.objects.create_user(username="auto_admin", password="test-only")
        asignar_rol(cls.admin, ADMIN)

    def crear_orden(self, cantidad):
        d = self.d
        self.client.force_login(self.compras)
        self.client.post(reverse("compra:add"), {
            "numero_de_orden": "X", "subtotal": "0.01", "total": "0.01",
            "proveedor": d["proveedor"].pk, "negocio": d["negocio"].pk,
            "productos_json": json.dumps([{"producto_id": d["producto"].pk, "cantidad": cantidad}]),
        })
        return OrdenDeCompra.objects.latest("pk")

    def configurar(self, activa, monto):
        from compra.models import ConfiguracionCompras

        ConfiguracionCompras.objects.update_or_create(pk=1, defaults={"autoautorizar": activa, "monto_maximo": monto})

    def test_por_defecto_no_se_autoriza_sola(self):
        orden = self.crear_orden(1)
        self.assertEqual(orden.estatus, EstatusChoices.PENDIENTE)
        self.assertFalse(orden.autorizada_por_regla)

    def test_orden_dentro_del_limite_se_autoriza_y_queda_marcada(self):
        self.configurar(True, "50.00")  # 3 piezas * 12.50 = 37.50
        orden = self.crear_orden(3)
        self.assertEqual(orden.estatus, EstatusChoices.AUTORIZADA)
        self.assertTrue(orden.autorizada_por_regla)
        self.assertIsNone(orden.usuario_autorizo)

    def test_el_limite_es_inclusivo_y_lo_mayor_queda_pendiente(self):
        self.configurar(True, "37.50")
        self.assertEqual(self.crear_orden(3).estatus, EstatusChoices.AUTORIZADA)
        self.assertEqual(self.crear_orden(4).estatus, EstatusChoices.PENDIENTE)

    def test_regla_desactivada_o_monto_cero_no_autoriza(self):
        for activa, monto in ((False, "500"), (True, "0")):
            with self.subTest(activa=activa, monto=monto):
                self.configurar(activa, monto)
                self.assertEqual(self.crear_orden(1).estatus, EstatusChoices.PENDIENTE)

    def test_orden_autorizada_por_regla_se_puede_recibir(self):
        self.configurar(True, "100")
        orden = self.crear_orden(2)
        almacenista = get_user_model().objects.create_user(username="auto_alm", password="test-only")
        asignar_rol(almacenista, ALMACEN)
        self.client.force_login(almacenista)
        self.client.post(reverse("compra:completar_orden", args=[orden.pk]))
        orden.refresh_from_db()
        self.assertEqual(orden.estatus, EstatusChoices.COMPLETADA)

    def test_solo_el_administrador_configura_la_regla(self):
        self.client.force_login(self.compras)
        self.assertEqual(self.client.get(reverse("compra:configuracion")).status_code, 403)
        self.client.force_login(self.admin)
        respuesta = self.client.post(reverse("compra:configuracion"), {"autoautorizar": "on", "monto_maximo": "250.00"})
        self.assertEqual(respuesta.status_code, 302)
        from compra.models import ConfiguracionCompras

        self.assertTrue(ConfiguracionCompras.obtener().aplica_a(Decimal("250.00")))

    def test_no_se_puede_activar_sin_monto(self):
        self.client.force_login(self.admin)
        respuesta = self.client.post(reverse("compra:configuracion"), {"autoautorizar": "on", "monto_maximo": "0"})
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("monto_maximo", respuesta.context["form"].errors)
