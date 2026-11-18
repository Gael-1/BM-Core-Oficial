import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.roles import ADMIN, ALMACEN, COMPRAS, CONSULTA, asignar_rol
from api.models import TokenAPI
from inventory import services as inv
from inventory.models import Inventario_Producto, Producto, Registro_Inventario
from inventory.tests import crear_datos
from ventas import services
from ventas.models import EstatusVenta, LineaVenta, Venta


class VentasBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.d = crear_datos()  # TEST-1: 10 piezas en «Principal», precio 12.50
        cls.usuario = cls.d["usuario"]
        cls.almacen = cls.d["almacen"]
        cls.producto = cls.d["producto"]
        User = get_user_model()
        cls.roles = {}
        for rol in (ADMIN, ALMACEN, COMPRAS, CONSULTA):
            u = User.objects.create_user(username=f"v_{rol.lower()}", password="test-only")
            asignar_rol(u, rol)
            cls.roles[rol] = u

    def existencia(self, producto=None):
        return Inventario_Producto.objects.get(producto_id=producto or self.producto).cantidad

    def otro_producto(self, sku="TEST-2", cantidad=5, precio="20.00"):
        p = Producto.objects.create(nombre="Otro", sku=sku, categoria_id=self.d["categoria"], precio=precio,
                                    medida=self.d["medida"], stock_min=1,
                                    creado_por=self.usuario, modificado_por=self.usuario)
        Inventario_Producto.objects.create(producto_id=p, cantidad=cantidad, almacen=self.almacen,
                                           creado_por=self.usuario, modificado_por=self.usuario)
        return p

    def linea(self, producto=None, cantidad=1, precio=None):
        return {"producto": producto or self.producto, "cantidad": cantidad, "precio_unitario": precio}


class ServicioVentasTests(VentasBase):
    def test_descuenta_existencias_calcula_total_y_registra_movimiento(self):
        venta, creada = services.crear_venta(self.usuario, self.almacen, [self.linea(cantidad=3)])
        self.assertTrue(creada)
        self.assertEqual(self.existencia(), 7)
        self.assertEqual(venta.total, Decimal("37.50"))
        self.assertEqual(venta.negocio, self.d["negocio"])
        self.assertEqual(venta.lineas.get().subtotal, Decimal("37.50"))
        movimiento = Registro_Inventario.objects.get()
        self.assertEqual((movimiento.tipo_movimiento, movimiento.cantidad_nueva), ("SALIDA", 3))
        self.assertEqual(movimiento.motivo.nombre, "Venta")
        self.assertIn(venta.folio, movimiento.comentarios)
        self.assertEqual(inv.existencia_en(Inventario_Producto.objects.get(), self.almacen), 7)

    def test_precio_personalizado_y_varias_lineas(self):
        otro = self.otro_producto()
        venta, _ = services.crear_venta(self.usuario, self.almacen, [
            self.linea(cantidad=2, precio="15.005"), self.linea(otro, 1)])
        self.assertEqual(venta.total, Decimal("30.02") + Decimal("20.00"))  # 15.005 se redondea a 15.01

    def test_si_una_linea_falla_no_se_guarda_nada(self):
        otro = self.otro_producto(cantidad=1)
        with self.assertRaises(services.VentaInvalida):
            services.crear_venta(self.usuario, self.almacen, [self.linea(cantidad=4), self.linea(otro, 2)])
        self.assertEqual(self.existencia(), 10)
        self.assertEqual(self.existencia(otro), 1)
        self.assertFalse(Venta.objects.exists())
        self.assertFalse(Registro_Inventario.objects.exists())

    def test_datos_invalidos(self):
        casos = [([], "Agrega"), ([self.linea(cantidad=0)], "mayor a cero"), ([self.linea(cantidad=-1)], "mayor a cero"),
                 ([self.linea(cantidad=1.5)], "enteras"), ([self.linea(cantidad=11)], "insuficiente"),
                 ([self.linea(precio="abc")], "precio"), ([self.linea(precio="-1")], "precio")]
        for lineas, texto in casos:
            with self.subTest(texto=texto, lineas=lineas):
                with self.assertRaisesRegex(services.VentaInvalida, texto):
                    services.crear_venta(self.usuario, self.almacen, lineas)
        with self.assertRaises(services.VentaInvalida):
            services.crear_venta(self.usuario, None, [self.linea()])
        self.assertEqual(self.existencia(), 10)

    def test_no_vende_de_un_almacen_que_no_tiene_la_mercancia(self):
        from inventory.models import Almacen

        bodega = Almacen.objects.create(nombre="Bodega", negocio=self.d["negocio"])
        with self.assertRaisesRegex(services.VentaInvalida, "Bodega"):
            services.crear_venta(self.usuario, bodega, [self.linea()])
        self.assertEqual(self.existencia(), 10)

    def test_referencia_externa_evita_duplicados(self):
        primera, creada1 = services.crear_venta(self.usuario, self.almacen, [self.linea(cantidad=2)], referencia=" POS-1 ")
        segunda, creada2 = services.crear_venta(self.usuario, self.almacen, [self.linea(cantidad=2)], referencia="POS-1")
        self.assertTrue(creada1)
        self.assertFalse(creada2)
        self.assertEqual(primera.pk, segunda.pk)
        self.assertEqual(self.existencia(), 8)

    def test_cancelar_devuelve_existencias_una_sola_vez(self):
        venta, _ = services.crear_venta(self.usuario, self.almacen, [self.linea(cantidad=4)])
        services.cancelar_venta(venta, self.usuario)
        venta.refresh_from_db()
        self.assertEqual(venta.estatus, EstatusVenta.CANCELADA)
        self.assertEqual(self.existencia(), 10)
        self.assertEqual(inv.existencia_en(Inventario_Producto.objects.get(), self.almacen), 10)
        with self.assertRaises(services.VentaInvalida):
            services.cancelar_venta(venta, self.usuario)
        self.assertEqual(self.existencia(), 10)

    def test_cancelar_funciona_aunque_el_producto_ya_este_inactivo(self):
        venta, _ = services.crear_venta(self.usuario, self.almacen, [self.linea(cantidad=4)])
        self.producto.activo = False
        self.producto.save()
        services.cancelar_venta(venta, self.usuario)
        self.assertEqual(self.existencia(), 10)

    def test_no_vende_productos_inactivos(self):
        self.producto.activo = False
        self.producto.save()
        with self.assertRaises(services.VentaInvalida):
            services.crear_venta(self.usuario, self.almacen, [self.linea()])


class PantallasVentasTests(VentasBase):
    def datos(self, **extras):
        base = {"almacen": self.almacen.pk, "cliente_nombre": "Cliente Uno", "comentarios": "",
                "lineas-TOTAL_FORMS": "6", "lineas-INITIAL_FORMS": "0",
                "lineas-MIN_NUM_FORMS": "0", "lineas-MAX_NUM_FORMS": "20",
                "lineas-0-producto": self.producto.pk, "lineas-0-cantidad": "2", "lineas-0-precio_unitario": ""}
        for i in range(1, 6):
            base.update({f"lineas-{i}-producto": "", f"lineas-{i}-cantidad": "", f"lineas-{i}-precio_unitario": ""})
        base.update(extras)
        return base

    def test_permisos_por_rol(self):
        for rol, puede in ((ADMIN, True), (ALMACEN, True), (COMPRAS, False), (CONSULTA, False)):
            with self.subTest(rol=rol):
                self.client.force_login(self.roles[rol])
                self.assertEqual(self.client.get(reverse("ventas:index")).status_code, 200)
                self.assertEqual(self.client.get(reverse("ventas:nueva")).status_code, 200 if puede else 403)
        self.client.logout()
        self.assertEqual(self.client.get(reverse("ventas:index")).status_code, 302)

    def test_registrar_venta_desde_el_formulario(self):
        self.client.force_login(self.roles[ALMACEN])
        respuesta = self.client.post(reverse("ventas:nueva"), self.datos())
        venta = Venta.objects.get()
        self.assertRedirects(respuesta, reverse("ventas:detalle", args=[venta.pk]))
        self.assertEqual(self.existencia(), 8)
        self.assertEqual(venta.cliente_nombre, "Cliente Uno")
        self.assertContains(self.client.get(reverse("ventas:detalle", args=[venta.pk])), venta.folio)
        self.assertContains(self.client.get(reverse("ventas:index")), venta.folio)

    def test_errores_del_formulario_no_descuentan(self):
        self.client.force_login(self.roles[ALMACEN])
        for extras in ({"lineas-0-producto": "", "lineas-0-cantidad": ""},
                       {"lineas-0-cantidad": "0"}, {"lineas-0-cantidad": ""},
                       {"lineas-0-producto": "", "lineas-0-cantidad": "3"},
                       {"lineas-0-cantidad": "50"}, {"almacen": ""}):
            with self.subTest(extras=extras):
                self.assertEqual(self.client.post(reverse("ventas:nueva"), self.datos(**extras)).status_code, 200)
        self.assertEqual(self.existencia(), 10)
        self.assertFalse(Venta.objects.exists())

    def test_solo_el_administrador_cancela(self):
        venta, _ = services.crear_venta(self.usuario, self.almacen, [self.linea(cantidad=2)])
        ruta = reverse("ventas:cancelar", args=[venta.pk])
        self.client.force_login(self.roles[ALMACEN])
        self.assertEqual(self.client.post(ruta).status_code, 403)
        self.assertEqual(self.existencia(), 8)
        self.client.force_login(self.roles[ADMIN])
        self.assertEqual(self.client.get(ruta).status_code, 405)
        self.assertEqual(self.client.post(ruta).status_code, 302)
        self.assertEqual(self.existencia(), 10)

    def test_filtro_por_estatus(self):
        venta, _ = services.crear_venta(self.usuario, self.almacen, [self.linea()])
        services.cancelar_venta(venta, self.usuario)
        self.client.force_login(self.roles[CONSULTA])
        self.assertNotContains(self.client.get(reverse("ventas:index"), {"estatus": "completada"}), venta.folio)
        self.assertContains(self.client.get(reverse("ventas:index"), {"estatus": "cancelada"}), venta.folio)


class ApiVentasTests(VentasBase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.tokens = {rol: TokenAPI.crear(u, f"t-{rol}")[1] for rol, u in cls.roles.items()}

    def post(self, cuerpo, rol=ALMACEN):
        datos = cuerpo if isinstance(cuerpo, str) else json.dumps(cuerpo)
        return self.client.post(reverse("api_v1:ventas"), datos, content_type="application/json",
                                HTTP_AUTHORIZATION=f"Bearer {self.tokens[rol]}")

    def cuerpo(self, **extras):
        base = {"almacen": self.almacen.pk, "referencia": "POS-77", "cliente": "Tienda online",
                "lineas": [{"sku": "TEST-1", "cantidad": 2, "precio_unitario": 15}]}
        base.update(extras)
        return base

    def test_registrar_venta_responde_201_con_el_detalle(self):
        respuesta = self.post(self.cuerpo())
        self.assertEqual(respuesta.status_code, 201)
        venta = respuesta.json()["venta"]
        self.assertEqual((venta["total"], venta["origen"], venta["referencia"]), ("30.00", "api", "POS-77"))
        self.assertEqual(venta["lineas"][0]["sku"], "TEST-1")
        self.assertEqual(self.existencia(), 8)

    def test_reintento_con_la_misma_referencia_no_duplica(self):
        self.post(self.cuerpo())
        respuesta = self.post(self.cuerpo())
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.json()["duplicada"])
        self.assertEqual(Venta.objects.count(), 1)
        self.assertEqual(self.existencia(), 8)

    def test_errores(self):
        self.assertEqual(self.post(self.cuerpo(lineas=[{"sku": "TEST-1", "cantidad": 99}])).status_code, 409)
        self.assertEqual(self.post(self.cuerpo(lineas=[{"sku": "NADA", "cantidad": 1}])).status_code, 404)
        for cuerpo in (self.cuerpo(almacen=99999), self.cuerpo(almacen=None), self.cuerpo(lineas=[]),
                       self.cuerpo(lineas="x"), self.cuerpo(lineas=[{"sku": "TEST-1", "cantidad": "2"}]),
                       self.cuerpo(lineas=[{"sku": "TEST-1", "cantidad": 0}]),
                       self.cuerpo(lineas=[{"sku": "TEST-1", "cantidad": 1, "precio_unitario": "abc"}]),
                       self.cuerpo(lineas=[3]), "no es json", "[]"):
            with self.subTest(cuerpo=cuerpo):
                self.assertEqual(self.post(cuerpo).status_code, 400)
        self.assertEqual(self.existencia(), 10)
        self.assertFalse(Venta.objects.exists())

    def test_permisos_y_autenticacion(self):
        self.assertEqual(self.post(self.cuerpo(), rol=CONSULTA).status_code, 403)
        self.assertEqual(self.post(self.cuerpo(), rol=COMPRAS).status_code, 403)
        self.assertEqual(self.client.post(reverse("api_v1:ventas"), "{}", content_type="application/json").status_code, 401)
        self.assertEqual(self.existencia(), 10)

    def test_listar_ventas(self):
        self.post(self.cuerpo())
        respuesta = self.client.get(reverse("api_v1:ventas"), HTTP_AUTHORIZATION=f"Bearer {self.tokens[CONSULTA]}")
        self.assertEqual(len(respuesta.json()["resultados"]), 1)
