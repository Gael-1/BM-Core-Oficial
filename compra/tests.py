import json
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase, skipUnlessDBFeature
from django.urls import reverse

from inventory.tests import crear_datos, solicitud
from inventory.models import Inventario_Producto, Negocio_Inventario, Registro_Inventario, Registro_Negocio_Inventario
from compra.forms import OrdenDeCompraForm
from compra.models import EstatusChoices, OrdenDeCompra, ProductoEnOrden
from compra import views


class CompraTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        for nombre, valor in crear_datos().items():
            setattr(cls, nombre, valor)

    def datos(self, items=None, **extras):
        datos = {"numero_de_orden": "MANIPULADO", "subtotal": "0.01", "total": "0.01",
                 "proveedor": self.proveedor.pk, "negocio": self.negocio.pk,
                 "productos_json": json.dumps(items if items is not None else [
                     {"producto_id": self.producto.pk, "cantidad": 3, "precio_unitario": .01, "subtotal": .01}])}
        datos.update(extras)
        return datos

    def orden(self, estado=EstatusChoices.PENDIENTE):
        orden = OrdenDeCompra.objects.create(numero_de_orden="OC-TEST", proveedor=self.proveedor,
                 negocio=self.negocio, subtotal="37.50", total="37.50", estatus=estado, usuario_creo=self.usuario)
        ProductoEnOrden.objects.create(orden=orden, producto=self.producto, cantidad=3, precio_unitario="12.50", subtotal="37.50")
        return orden

    def post(self, view, orden):
        return view(solicitud(self.usuario, "/compras/"), orden.pk)

    def test_crear_orden_recalcula_importes_y_redirige(self):
        response = views.add(solicitud(self.usuario, "/compras/add/", self.datos()))
        self.assertEqual(response.status_code, 302)
        orden = OrdenDeCompra.objects.get()
        self.assertEqual(str(orden.total), "37.50")
        self.assertTrue(orden.numero_de_orden.startswith("OC-"))
        self.assertEqual(orden.estatus, EstatusChoices.PENDIENTE)
        self.assertEqual(orden.productos.get().precio_unitario, Decimal(self.producto.precio))
        self.assertFalse(Registro_Inventario.objects.exists())

    def test_rechazar_lineas_invalidas_y_ajenas(self):
        for items in ([], {}, [{"producto_id": self.producto.pk, "cantidad": 0}],
                      [{"producto_id": self.producto.pk, "cantidad": -2}],
                      [{"producto_id": self.producto.pk, "cantidad": 1.5}],
                      [{"producto_id": self.producto.pk, "cantidad": "NaN"}],
                      [{"producto_id": 999999, "cantidad": 1}],
                      [{"producto_id": self.producto.pk, "cantidad": 1}] * 2):
            with self.subTest(items=items):
                form = OrdenDeCompraForm(self.datos(items))
                self.assertFalse(form.is_valid())
        self.assertFalse(OrdenDeCompra.objects.exists())

    def test_json_invalido_no_crea_orden(self):
        with patch("compra.views.render", side_effect=lambda request, template, context: context):
            resultado = views.add(solicitud(self.usuario, "/compras/add/", self.datos(productos_json="{")))
        self.assertTrue(resultado["form"].errors)
        self.assertFalse(OrdenDeCompra.objects.exists())

    def test_fallo_al_crear_linea_revierte_la_orden(self):
        with patch("compra.views.ProductoEnOrden.objects.create", side_effect=RuntimeError("fallo simulado")):
            with self.assertRaises(RuntimeError):
                views.add(solicitud(self.usuario, "/compras/add/", self.datos()))
        self.assertFalse(OrdenDeCompra.objects.exists())

    def test_acciones_requieren_post(self):
        self.client.force_login(self.usuario)
        orden = self.orden()
        for nombre in ("autorizar_od", "rechazar_od", "completar_orden"):
            response = self.client.get(reverse("compra:" + nombre, args=[orden.pk]))
            self.assertEqual(response.status_code, 405)
        orden.refresh_from_db()
        self.assertEqual(orden.estatus, EstatusChoices.PENDIENTE)

    def test_autorizar_registra_usuario_y_no_reabre_orden(self):
        orden = self.orden()
        self.post(views.autorizar_oden, orden)
        orden.refresh_from_db()
        self.assertEqual(orden.usuario_autorizo_id, self.usuario.pk)
        self.assertEqual(orden.estatus, EstatusChoices.AUTORIZADA)
        self.post(views.rechazar_orden, orden)
        orden.refresh_from_db()
        self.assertEqual(orden.estatus, EstatusChoices.AUTORIZADA)

    def test_rechazada_no_se_autoriza_ni_recibe(self):
        orden = self.orden()
        self.post(views.rechazar_orden, orden)
        self.post(views.autorizar_oden, orden)
        self.post(views.completar_orden, orden)
        orden.refresh_from_db()
        self.assertEqual(orden.estatus, EstatusChoices.RECHAZADA)
        self.assertFalse(Registro_Inventario.objects.exists())

    def test_pendiente_no_se_recibe(self):
        orden = self.orden()
        self.post(views.completar_orden, orden)
        orden.refresh_from_db(); self.inventario.refresh_from_db()
        self.assertEqual(orden.estatus, EstatusChoices.PENDIENTE)
        self.assertEqual(self.inventario.cantidad, 10)

    def test_recepcion_unica_y_trazabilidad(self):
        orden = self.orden(EstatusChoices.AUTORIZADA)
        self.post(views.completar_orden, orden)
        self.post(views.completar_orden, orden)
        self.inventario.refresh_from_db(); orden.refresh_from_db()
        self.assertEqual(self.inventario.cantidad, 13)
        self.assertEqual(orden.estatus, EstatusChoices.COMPLETADA)
        mov = Registro_Inventario.objects.get()
        self.assertEqual((mov.tipo_movimiento, mov.cantidad_nueva, mov.orden_compra_id), ("ENTRADA", 3, orden.pk))
        self.assertEqual(Negocio_Inventario.objects.get().cantidad, 3)
        self.assertEqual(Registro_Negocio_Inventario.objects.count(), 1)

    def test_fallo_en_recepcion_revierte_toda_la_operacion(self):
        orden = self.orden(EstatusChoices.AUTORIZADA)
        with patch("compra.views.Registro_Negocio_Inventario.objects.create", side_effect=RuntimeError("fallo simulado")):
            with self.assertRaises(RuntimeError):
                self.post(views.completar_orden, orden)
        self.inventario.refresh_from_db(); orden.refresh_from_db()
        self.assertEqual(self.inventario.cantidad, 10)
        self.assertEqual(orden.estatus, EstatusChoices.AUTORIZADA)
        self.assertFalse(Registro_Inventario.objects.exists())
        self.assertFalse(Negocio_Inventario.objects.exists())

    def test_recepcion_crea_inventario_inexistente(self):
        self.inventario.delete()
        orden = self.orden(EstatusChoices.AUTORIZADA)
        self.post(views.completar_orden, orden)
        self.assertEqual(Inventario_Producto.objects.get().cantidad, 3)

    def test_pantallas_y_botones_post(self):
        self.client.force_login(self.usuario)
        orden = self.orden()
        for ruta in (reverse("compra:index"), reverse("compra:add"), reverse("compra:view", args=[orden.pk])):
            response = self.client.get(ruta)
            self.assertEqual(response.status_code, 200)
        response = self.client.get(reverse("compra:view", args=[orden.pk]))
        self.assertContains(response, 'method="post"')
        self.assertContains(response, 'csrfmiddlewaretoken')


    def test_producto_inactivo_revierte_recepcion(self):
        orden = self.orden(EstatusChoices.AUTORIZADA)
        self.producto.activo = False
        self.producto.save()
        self.post(views.completar_orden, orden)
        orden.refresh_from_db(); self.inventario.refresh_from_db()
        self.assertEqual(orden.estatus, EstatusChoices.AUTORIZADA)
        self.assertEqual(self.inventario.cantidad, 10)
        self.assertFalse(Registro_Inventario.objects.exists())

    def test_post_sin_csrf_es_rechazado(self):
        from django.test import Client
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.usuario)
        orden = self.orden()
        response = client.post(reverse("compra:autorizar_od", args=[orden.pk]))
        self.assertEqual(response.status_code, 403)
        orden.refresh_from_db()
        self.assertEqual(orden.estatus, EstatusChoices.PENDIENTE)


class RecepcionConcurrenteTests(TransactionTestCase):
    @skipUnlessDBFeature("has_select_for_update")
    def test_dos_recepciones_simultaneas_suman_una_sola_vez(self):
        datos = crear_datos()
        usuario, producto = datos["usuario"], datos["producto"]
        orden = OrdenDeCompra.objects.create(numero_de_orden="OC-CONCURRENTE", proveedor=datos["proveedor"],
                 negocio=datos["negocio"], subtotal="37.50", total="37.50", estatus=EstatusChoices.AUTORIZADA)
        ProductoEnOrden.objects.create(orden=orden, producto=producto, cantidad=3, precio_unitario="12.50", subtotal="37.50")
        barrera = Barrier(2)
        def recibir():
            close_old_connections()
            try:
                barrera.wait(timeout=10)
                return views.completar_orden(solicitud(usuario, "/compras/"), orden.pk).status_code
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futuros = [pool.submit(recibir) for _ in range(2)]
            self.assertEqual([f.result(timeout=30) for f in futuros], [302, 302])
        datos["inventario"].refresh_from_db()
        self.assertEqual(datos["inventario"].cantidad, 13)
        self.assertEqual(Registro_Inventario.objects.filter(orden_compra=orden).count(), 1)


class CorreccionesCompraTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        for nombre, valor in crear_datos().items():
            setattr(cls, nombre, valor)

    def test_str_de_producto_en_orden(self):
        orden = OrdenDeCompra.objects.create(numero_de_orden="OC-STR", proveedor=self.proveedor, negocio=self.negocio,
                                             subtotal="1.00", total="1.00", usuario_creo=self.usuario)
        linea = ProductoEnOrden.objects.create(orden=orden, producto=self.producto, cantidad=2,
                                               precio_unitario="0.50", subtotal="1.00")
        self.assertIn(self.producto.nombre, str(linea))

    def test_find_negocio_rfc_rechaza_json_invalido(self):
        self.client.force_login(self.usuario)
        url = reverse("compra:findNegocioRFC")
        for cuerpo in ("esto no es json", "[1, 2]", '{"negocio_id": "abc"}'):
            with self.subTest(cuerpo=cuerpo):
                respuesta = self.client.post(url, data=cuerpo, content_type="application/json")
                self.assertIn(respuesta.status_code, (400, 404))


class RecepcionPorAlmacenTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        for nombre, valor in crear_datos().items():
            setattr(cls, nombre, valor)

    def test_recepcion_suma_al_almacen_predeterminado(self):
        from inventory import services

        orden = OrdenDeCompra.objects.create(
            numero_de_orden="OC-ALM", proveedor=self.proveedor, negocio=self.negocio, subtotal="37.50",
            total="37.50", estatus=EstatusChoices.AUTORIZADA, usuario_creo=self.usuario)
        ProductoEnOrden.objects.create(orden=orden, producto=self.producto, cantidad=3,
                                       precio_unitario="12.50", subtotal="37.50")
        self.client.force_login(self.usuario)
        self.client.post(reverse("compra:completar_orden", args=[orden.pk]))
        self.inventario.refresh_from_db()
        self.assertEqual(self.inventario.cantidad, 13)
        self.assertEqual(services.existencia_en(self.inventario, self.almacen), 13)
        self.assertEqual(services.sin_asignar(self.inventario), 0)
