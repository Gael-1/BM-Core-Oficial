from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory, TestCase
from django.urls import reverse

from categorias.models import Categoria
from negocio.models import Negocio
from proveedores.models import Proveedor, ProductosProveedor, RegimenFiscal
from inventory.forms import addProductForm
from inventory.models import Almacen, Inventario_Producto, Medidas_Inventario, Producto, Registro_Inventario
from inventory import services, views


def crear_datos():
    usuario = get_user_model().objects.create_superuser(username="operador", password="test-only")
    regimen, _ = RegimenFiscal.objects.get_or_create(codigo=601, defaults={"descripcion": "General"})
    negocio = Negocio.objects.create(nombre="Sucursal", nombre_fiscal="Sucursal", direccion="Centro",
                                     rfc="ABC010101AA1", codigo_postal="64000", regimen_fiscal=regimen)
    proveedor = Proveedor.objects.create(nombre="Proveedor", razon_social="Proveedor", rfc="DEF010101AA1",
                                         direccion="Centro", codigo_postal="64000", regimen_fiscal=regimen)
    categoria = Categoria.objects.create(nombre="Materiales")
    medida, _ = Medidas_Inventario.objects.get_or_create(
        nombre="Pieza", defaults={"abreviatura": "pza", "permite_decimales": False})
    almacen = Almacen.objects.create(nombre="Principal", negocio=negocio)
    producto = Producto.objects.create(nombre="Producto", sku="TEST-1", categoria_id=categoria, precio="12.50",
                                       medida=medida, stock_min=2, creado_por=usuario, modificado_por=usuario)
    inventario = Inventario_Producto.objects.create(producto_id=producto, cantidad=10, almacen=almacen,
                                                   creado_por=usuario, modificado_por=usuario)
    ProductosProveedor.objects.create(proveedor=proveedor, producto=producto, precio="12.50")
    return locals()


def solicitud(usuario, ruta, datos=None):
    request = RequestFactory().post(ruta, datos or {})
    request.user = usuario
    request.session = {}
    request._messages = FallbackStorage(request)
    return request


class InventoryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        for nombre, valor in crear_datos().items():
            setattr(cls, nombre, valor)

    def datos(self, **extras):
        datos = {"nombre": "Producto", "sku": "TEST-1", "categoria_id": self.categoria.pk,
                 "medida": self.medida.pk, "precio": "12.50", "stock_min": "2",
                 "cantidad_actual": "10", "almacen": self.almacen.pk}
        datos.update(extras)
        return datos

    def ajustar(self, **extras):
        request = solicitud(self.usuario, "/inventory/", self.datos(**extras))
        with patch("inventory.views.render", side_effect=lambda request, template, context: context):
            return views.edit(request, self.producto.pk)

    def test_ruta_edicion_y_formulario(self):
        self.client.force_login(self.usuario)
        response = self.client.get(reverse("inventory:edit", args=[self.producto.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "id_codigo_barras")
        self.assertContains(response, "id_almacen")
        self.assertEqual(response.context["form"].initial["almacen"], self.almacen.pk)

    def test_entrada_y_salida_registran_la_diferencia(self):
        self.assertEqual(self.ajustar(cantidad_nueva="13").status_code, 302)
        movimiento = Registro_Inventario.objects.get()
        self.assertEqual((movimiento.tipo_movimiento, movimiento.cantidad_nueva, movimiento.cantidad_anterior),
                         ("ENTRADA", 3, 10))
        self.assertEqual(self.ajustar(cantidad_actual="13", cantidad_nueva="8").status_code, 302)
        movimiento = Registro_Inventario.objects.latest("pk")
        self.assertEqual((movimiento.tipo_movimiento, movimiento.cantidad_nueva, movimiento.cantidad_anterior),
                         ("SALIDA", 5, 13))
        self.inventario.refresh_from_db()
        self.assertEqual(self.inventario.cantidad, 8)

    def test_misma_cantidad_y_edicion_sin_cantidad_no_crean_movimientos(self):
        self.ajustar(cantidad_nueva="10")
        self.ajustar(nombre="Nombre nuevo")
        self.assertFalse(Registro_Inventario.objects.exists())
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.nombre, "Nombre nuevo")

    def test_validacion_negativos_no_finitos_y_fracciones(self):
        for campo, valor in (("cantidad_nueva", "-1"), ("cantidad_nueva", "1.5"),
                             ("stock_min", "-2"), ("stock_min", "1.5"), ("cantidad", "-1"),
                             ("cantidad_nueva", "NaN"), ("cantidad_nueva", "inf")):
            with self.subTest(campo=campo, valor=valor):
                form = addProductForm(self.datos(**{campo: valor}), instance=self.producto)
                self.assertFalse(form.is_valid())
                self.assertIn(campo, form.errors)

    def test_unidad_decimal_permite_fracciones(self):
        self.medida.permite_decimales = True
        self.medida.save()
        self.ajustar(cantidad_nueva="9.5")
        movimiento = Registro_Inventario.objects.get()
        self.assertEqual(movimiento.cantidad_nueva, .5)
        self.inventario.refresh_from_db()
        self.assertEqual(self.inventario.cantidad, 9.5)

    def test_ajuste_desactualizado_no_sobrescribe_stock(self):
        resultado = self.ajustar(cantidad_actual="9", cantidad_nueva="4", nombre="No guardar")
        self.assertIn("cantidad_nueva", resultado["form"].errors)
        self.inventario.refresh_from_db(); self.producto.refresh_from_db()
        self.assertEqual(self.inventario.cantidad, 10)
        self.assertEqual(self.producto.nombre, "Producto")
        self.assertFalse(Registro_Inventario.objects.exists())

    def test_no_reasignar_almacen_con_existencias(self):
        otro = Almacen.objects.create(nombre="Otro")
        resultado = self.ajustar(almacen=otro.pk, cantidad_nueva="12")
        self.assertIn("almacen", resultado["form"].errors)
        self.inventario.refresh_from_db()
        self.assertEqual(self.inventario.almacen_id, self.almacen.pk)

    def test_creacion_sin_stock_y_codigo_vacio(self):
        datos = self.datos(sku="TEST-2", cantidad_actual="", codigo_barras="")
        response = views.add(solicitud(self.usuario, "/inventory/agregar/", datos))
        self.assertEqual(response.status_code, 302)
        producto = Producto.objects.get(sku="TEST-2")
        self.assertIsNone(producto.codigo_barras)
        self.assertEqual(producto.stock_actual, 0)
        self.assertEqual(producto.inventario.almacen_id, self.almacen.pk)

    def test_creacion_con_stock_inicial(self):
        datos = self.datos(sku="TEST-3", addCantidad="on", cantidad="4")
        response = views.add(solicitud(self.usuario, "/inventory/agregar/", datos))
        self.assertEqual(response.status_code, 302)
        producto = Producto.objects.get(sku="TEST-3")
        self.assertEqual(producto.stock_actual, 4)
        self.assertEqual(Registro_Inventario.objects.get().cantidad_nueva, 4)


    def test_catalogo_busqueda_alertas_y_almacen(self):
        self.client.force_login(self.usuario)
        for nombre, params in (("productos", {}), ("buscar_codigo", {"q": "TEST-1"}),
                               ("buscar_codigo", {"q": "NO-EXISTE"}), ("alertas", {}),
                               ("inventario_por_almacen", {"almacen_id": self.almacen.pk})):
            with self.subTest(nombre=nombre, params=params):
                response = self.client.get(reverse("inventory:" + nombre), params)
                self.assertEqual(response.status_code, 200)
        response = self.client.get(reverse("inventory:inventario_por_almacen"), {"almacen_id": "incorrecto"})
        self.assertEqual(response.status_code, 400)

    def test_alertas_incluyen_producto_sin_inventario(self):
        self.inventario.delete()
        request = RequestFactory().get("/inventory/alertas/")
        with patch("inventory.views.render", side_effect=lambda request, template, context: context):
            context = views.alertas_reabastecimiento(request)
        self.assertEqual(context["total_alertas"], 1)


    def test_ajuste_fallido_revierte_producto_existencia_y_bitacora(self):
        with patch("inventory.views.Registro_Inventario.objects.create", side_effect=RuntimeError("fallo simulado")):
            with self.assertRaises(RuntimeError):
                self.ajustar(cantidad_nueva="13", nombre="No guardar")
        self.inventario.refresh_from_db(); self.producto.refresh_from_db()
        self.assertEqual(self.inventario.cantidad, 10)
        self.assertEqual(self.producto.nombre, "Producto")
        self.assertFalse(Registro_Inventario.objects.exists())


class MovimientosTests(TestCase):
    """Entradas / salidas manuales e historial (pantallas nuevas)."""

    @classmethod
    def setUpTestData(cls):
        from inventory.models import motivo_movimiento

        for nombre, valor in crear_datos().items():
            setattr(cls, nombre, valor)
        cls.motivo = motivo_movimiento.objects.create(nombre="Motivo de prueba")

    def setUp(self):
        self.client.force_login(self.usuario)

    def registrar(self, **extras):
        datos = {"producto": self.producto.pk, "tipo_movimiento": "SALIDA", "cantidad": "4",
                 "motivo": self.motivo.pk, "comentarios": "Prueba"}
        datos.update(extras)
        return self.client.post(reverse("inventory:movimiento"), datos)

    def test_salida_descuenta_y_registra_motivo(self):
        respuesta = self.registrar()
        self.assertRedirects(respuesta, reverse("inventory:historial"), fetch_redirect_response=False)
        self.inventario.refresh_from_db()
        self.assertEqual(self.inventario.cantidad, 6)
        registro = Registro_Inventario.objects.get()
        self.assertEqual((registro.tipo_movimiento, registro.cantidad_nueva, registro.cantidad_anterior), ("SALIDA", 4, 10))
        self.assertEqual(registro.motivo, self.motivo)

    def test_entrada_suma_existencias(self):
        self.registrar(tipo_movimiento="ENTRADA", cantidad="5")
        self.inventario.refresh_from_db()
        self.assertEqual(self.inventario.cantidad, 15)

    def test_salida_mayor_a_la_existencia_se_rechaza(self):
        respuesta = self.registrar(cantidad="11")
        self.assertEqual(respuesta.status_code, 200)
        self.inventario.refresh_from_db()
        self.assertEqual(self.inventario.cantidad, 10)
        self.assertFalse(Registro_Inventario.objects.exists())

    def test_cantidad_invalida_se_rechaza(self):
        for cantidad in ("0", "-3", "2.5", "nan", "inf"):
            with self.subTest(cantidad=cantidad):
                self.assertEqual(self.registrar(cantidad=cantidad).status_code, 200)
        self.inventario.refresh_from_db()
        self.assertEqual(self.inventario.cantidad, 10)
        self.assertFalse(Registro_Inventario.objects.exists())

    def test_historial_filtra_por_tipo_y_producto(self):
        self.registrar()
        self.registrar(tipo_movimiento="ENTRADA", cantidad="1")
        todos = self.client.get(reverse("inventory:historial"))
        self.assertEqual(todos.context["page_obj"].paginator.count, 2)
        salidas = self.client.get(reverse("inventory:historial"), {"tipo": "SALIDA"})
        self.assertEqual(salidas.context["page_obj"].paginator.count, 1)
        otro = self.client.get(reverse("inventory:historial"), {"producto": self.producto.pk + 999})
        self.assertEqual(otro.context["page_obj"].paginator.count, 0)


class AlmacenesTests(TestCase):
    """Existencias por almacén, traspasos y administración de almacenes."""

    @classmethod
    def setUpTestData(cls):
        from inventory.models import motivo_movimiento

        for nombre, valor in crear_datos().items():
            setattr(cls, nombre, valor)
        cls.otro = Almacen.objects.create(nombre="Secundario", negocio=cls.negocio)
        cls.motivo = motivo_movimiento.objects.create(nombre="Motivo almacenes")

    def setUp(self):
        self.client.force_login(self.usuario)

    def traspasar(self, origen, destino, cantidad, **extras):
        datos = {"producto": self.producto.pk, "almacen_origen": origen.pk if origen else "",
                 "almacen_destino": destino.pk if destino else "", "cantidad": cantidad}
        datos.update(extras)
        return self.client.post(reverse("inventory:traspaso"), datos)

    def movimiento(self, **extras):
        datos = {"producto": self.producto.pk, "tipo_movimiento": "SALIDA", "cantidad": "1",
                 "motivo": self.motivo.pk}
        datos.update(extras)
        return self.client.post(reverse("inventory:movimiento"), datos)

    def existencia(self, almacen):
        self.inventario.refresh_from_db()
        return services.existencia_en(self.inventario, almacen)

    def ajustar(self, **extras):
        datos = {"nombre": "Producto", "sku": "TEST-1", "categoria_id": self.categoria.pk,
                 "medida": self.medida.pk, "precio": "12.50", "stock_min": "2",
                 "cantidad_actual": "10", "almacen": self.almacen.pk}
        datos.update(extras)
        request = solicitud(self.usuario, "/inventory/", datos)
        with patch("inventory.views.render", side_effect=lambda request, template, context: context):
            return views.edit(request, self.producto.pk)

    # --- traspasos
    def test_traspaso_mueve_existencias_sin_cambiar_el_total(self):
        respuesta = self.traspasar(self.almacen, self.otro, "4")
        self.assertRedirects(respuesta, reverse("inventory:inventario_por_almacen"), fetch_redirect_response=False)
        self.assertEqual(self.existencia(self.almacen), 6)
        self.assertEqual(self.existencia(self.otro), 4)
        self.assertEqual(self.inventario.cantidad, 10)
        registro = Registro_Inventario.objects.get()
        self.assertEqual(registro.tipo_movimiento, "TRASPASO")
        self.assertEqual((registro.almacen_origen, registro.almacen_destino), (self.almacen, self.otro))
        self.assertEqual((registro.cantidad_nueva, registro.cantidad_anterior), (4, 10))

    def test_traspaso_mayor_a_lo_disponible_se_rechaza(self):
        respuesta = self.traspasar(self.almacen, self.otro, "11")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(self.existencia(self.otro), 0)
        self.assertEqual(self.inventario.cantidad, 10)
        self.assertFalse(Registro_Inventario.objects.exists())

    def test_traspaso_con_datos_invalidos_se_rechaza(self):
        casos = [(self.almacen, self.almacen, "1"), (self.almacen, self.otro, "0"),
                 (self.almacen, self.otro, "-1"), (self.almacen, self.otro, "nan"),
                 (self.almacen, self.otro, "inf"), (self.almacen, self.otro, "2.5")]
        for origen, destino, cantidad in casos:
            with self.subTest(destino=destino.nombre, cantidad=cantidad):
                self.assertEqual(self.traspasar(origen, destino, cantidad).status_code, 200)
        self.assertFalse(Registro_Inventario.objects.exists())
        self.assertEqual(self.existencia(self.otro), 0)

    def test_traspaso_desde_sin_asignar(self):
        Inventario_Producto.objects.filter(pk=self.inventario.pk).update(almacen=None)
        respuesta = self.traspasar(None, self.otro, "3")
        self.assertEqual(respuesta.status_code, 302)
        self.inventario.refresh_from_db()
        self.assertEqual(self.existencia(self.otro), 3)
        self.assertEqual(services.sin_asignar(self.inventario), 7)
        self.assertEqual(self.inventario.cantidad, 10)
        self.assertIsNone(self.inventario.almacen_id)

    def test_traspaso_de_producto_sin_inventario_se_rechaza(self):
        self.inventario.delete()
        self.assertEqual(self.traspasar(self.almacen, self.otro, "1").status_code, 200)
        self.assertFalse(Registro_Inventario.objects.exists())

    # --- entradas y salidas por almacén
    def test_salida_por_almacen_respeta_el_desglose(self):
        self.traspasar(self.almacen, self.otro, "4")
        rechazada = self.movimiento(cantidad="7", almacen=self.almacen.pk)
        self.assertEqual(rechazada.status_code, 200)
        self.assertEqual(self.existencia(self.almacen), 6)
        aceptada = self.movimiento(cantidad="6", almacen=self.almacen.pk)
        self.assertEqual(aceptada.status_code, 302)
        self.assertEqual(self.existencia(self.almacen), 0)
        self.assertEqual(self.existencia(self.otro), 4)
        self.assertEqual(self.inventario.cantidad, 4)

    def test_entrada_a_un_almacen_especifico(self):
        self.movimiento(tipo_movimiento="ENTRADA", cantidad="5", almacen=self.otro.pk)
        self.assertEqual(self.existencia(self.otro), 5)
        self.assertEqual(self.existencia(self.almacen), 10)
        self.assertEqual(self.inventario.cantidad, 15)

    def test_movimiento_sin_almacen_usa_el_predeterminado(self):
        self.movimiento(cantidad="3")
        self.assertEqual(self.existencia(self.almacen), 7)
        registro = Registro_Inventario.objects.get()
        self.assertEqual(registro.almacen_origen, self.almacen)

    # --- ajuste desde el catálogo
    def test_ajuste_desde_catalogo_se_refleja_en_el_almacen(self):
        self.ajustar(cantidad_nueva="13")
        self.assertEqual(self.existencia(self.almacen), 13)
        self.assertEqual(self.inventario.cantidad, 13)

    def test_ajuste_a_la_baja_no_puede_exceder_el_almacen(self):
        services.asegurar_existencias(self.inventario)
        services.mover(self.inventario, self.almacen, -4)
        services.mover(self.inventario, self.otro, 4)
        resultado = self.ajustar(cantidad_nueva="3")
        self.assertIn("cantidad_nueva", resultado["form"].errors)
        self.inventario.refresh_from_db()
        self.assertEqual(self.inventario.cantidad, 10)

    # --- vistas
    def test_vista_por_almacen_con_datos_anteriores(self):
        respuesta = self.client.get(reverse("inventory:inventario_por_almacen"))
        filas = {f["almacen"].pk: f["cantidad"] for f in respuesta.context["inventario"]}
        self.assertEqual(filas, {self.almacen.pk: 10})

    def test_vista_por_almacen_refleja_el_desglose_y_filtra(self):
        self.traspasar(self.almacen, self.otro, "4")
        todas = self.client.get(reverse("inventory:inventario_por_almacen"))
        self.assertEqual({f["almacen"].pk: f["cantidad"] for f in todas.context["inventario"]},
                         {self.almacen.pk: 6, self.otro.pk: 4})
        filtrada = self.client.get(reverse("inventory:inventario_por_almacen"), {"almacen_id": self.otro.pk})
        self.assertEqual([(f["almacen"].pk, f["cantidad"]) for f in filtrada.context["inventario"]],
                         [(self.otro.pk, 4)])

    def test_lista_de_almacenes_con_totales(self):
        self.traspasar(self.almacen, self.otro, "4")
        respuesta = self.client.get(reverse("inventory:almacenes"))
        por_nombre = {f["almacen"].nombre: (f["productos"], f["unidades"]) for f in respuesta.context["almacenes"]}
        self.assertEqual(por_nombre["Principal"], (1, 6))
        self.assertEqual(por_nombre["Secundario"], (1, 4))

    def test_historial_incluye_traspasos(self):
        self.traspasar(self.almacen, self.otro, "2")
        respuesta = self.client.get(reverse("inventory:historial"), {"tipo": "TRASPASO"})
        self.assertEqual(respuesta.context["page_obj"].paginator.count, 1)
        self.assertContains(respuesta, "Principal → Secundario")

    # --- administración de almacenes
    def test_crear_almacen_y_principal_unico_por_negocio(self):
        datos = {"nombre": "Norte", "direccion": "", "negocio": self.negocio.pk, "es_principal": "on"}
        self.assertEqual(self.client.post(reverse("inventory:almacen_add"), datos).status_code, 302)
        datos.update(nombre="Sur")
        self.client.post(reverse("inventory:almacen_add"), datos)
        self.assertFalse(Almacen.objects.get(nombre="Norte").es_principal)
        self.assertTrue(Almacen.objects.get(nombre="Sur").es_principal)

    def test_nombre_de_almacen_repetido_se_rechaza(self):
        respuesta = self.client.post(reverse("inventory:almacen_add"), {"nombre": "principal", "direccion": ""})
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(Almacen.objects.filter(nombre__iexact="principal").count(), 1)

    def test_editar_almacen(self):
        self.client.post(reverse("inventory:almacen_edit", args=[self.otro.pk]),
                         {"nombre": "Bodega 2", "direccion": "Calle 1", "negocio": self.negocio.pk})
        self.otro.refresh_from_db()
        self.assertEqual((self.otro.nombre, self.otro.direccion), ("Bodega 2", "Calle 1"))
        self.assertEqual(self.client.get(reverse("inventory:almacen_edit", args=[9999])).status_code, 404)

    # --- servicio
    def test_asegurar_existencias_es_idempotente(self):
        services.asegurar_existencias(self.inventario)
        services.asegurar_existencias(self.inventario)
        self.assertEqual(self.inventario.existencias.get().cantidad, 10)
        self.assertEqual(services.sin_asignar(self.inventario), 0)


class AlmacenSinNegocioTests(TestCase):
    def test_se_puede_crear_un_almacen_sin_negocio(self):
        usuario = get_user_model().objects.create_superuser(username="sinneg", password="test-only")
        self.client.force_login(usuario)
        respuesta = self.client.post(reverse("inventory:almacen_add"), {"nombre": "Bodega general", "direccion": ""})
        self.assertEqual(respuesta.status_code, 302)
        self.assertIsNone(Almacen.objects.get(nombre="Bodega general").negocio)
