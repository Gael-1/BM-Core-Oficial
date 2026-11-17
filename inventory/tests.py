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
from inventory import views


def crear_datos():
    usuario = get_user_model().objects.create_superuser(username="operador", password="test-only")
    regimen = RegimenFiscal.objects.create(codigo=601, descripcion="General")
    negocio = Negocio.objects.create(nombre="Sucursal", nombre_fiscal="Sucursal", direccion="Centro",
                                     rfc="ABC010101AA1", codigo_postal="64000", regimen_fiscal=regimen)
    proveedor = Proveedor.objects.create(nombre="Proveedor", razon_social="Proveedor", rfc="DEF010101AA1",
                                         direccion="Centro", codigo_postal="64000", regimen_fiscal=regimen)
    categoria = Categoria.objects.create(nombre="Materiales")
    medida = Medidas_Inventario.objects.create(nombre="Pieza", abreviatura="pza", permite_decimales=False)
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
