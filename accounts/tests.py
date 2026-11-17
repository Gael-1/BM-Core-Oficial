from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from accounts.roles import ADMIN, ALMACEN, COMPRAS, CONSULTA, ROLES, asignar_rol
from compra.models import EstatusChoices, OrdenDeCompra, ProductoEnOrden
from inventory.tests import crear_datos


def usuario_con_rol(nombre, rol=None):
    usuario = get_user_model().objects.create_user(username=nombre, password="test-only")
    if rol:
        asignar_rol(usuario, rol)
    return usuario


class RolesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        for nombre, valor in crear_datos().items():
            setattr(cls, nombre, valor)
        cls.sin_rol = usuario_con_rol("sinrol")
        cls.admin = usuario_con_rol("admin1", ADMIN)
        cls.admin_2 = usuario_con_rol("admin2", ADMIN)
        cls.almacenista = usuario_con_rol("almacen1", ALMACEN)
        cls.comprador = usuario_con_rol("compras1", COMPRAS)
        cls.consulta = usuario_con_rol("consulta1", CONSULTA)

    def estado(self, usuario, nombre, metodo="get", **kwargs):
        self.client.force_login(usuario)
        return getattr(self.client, metodo)(reverse(nombre, **kwargs)).status_code

    def orden(self, solicito):
        orden = OrdenDeCompra.objects.create(
            numero_de_orden="OC-ROL", proveedor=self.proveedor, negocio=self.negocio,
            subtotal="37.50", total="37.50", usuario_creo=solicito, usuario_solicito=solicito)
        ProductoEnOrden.objects.create(orden=orden, producto=self.producto, cantidad=3,
                                       precio_unitario="12.50", subtotal="37.50")
        return orden

    def test_los_roles_existen_tras_migrar(self):
        self.assertEqual(set(Group.objects.values_list("name", flat=True)) & set(ROLES), set(ROLES))

    def test_usuario_sin_rol_no_entra_a_ningun_modulo(self):
        for nombre in ("inventory:productos", "proveedores:index", "compra:index",
                       "reportes:inicio", "negocio:index", "categorias:index"):
            with self.subTest(pantalla=nombre):
                self.assertEqual(self.estado(self.sin_rol, nombre), 403)

    def test_consulta_lee_pero_no_escribe(self):
        for nombre in ("inventory:productos", "compra:index", "reportes:inicio", "categorias:index"):
            with self.subTest(lectura=nombre):
                self.assertEqual(self.estado(self.consulta, nombre), 200)
        for nombre in ("inventory:add", "inventory:movimiento", "proveedores:add",
                       "compra:add", "negocio:add", "categorias:add"):
            with self.subTest(escritura=nombre):
                self.assertEqual(self.estado(self.consulta, nombre), 403)

    def test_almacenista_gestiona_inventario_pero_no_compras(self):
        for nombre in ("inventory:movimiento", "inventory:add", "categorias:add"):
            with self.subTest(permitido=nombre):
                self.assertEqual(self.estado(self.almacenista, nombre), 200)
        for nombre in ("proveedores:add", "compra:add", "negocio:add"):
            with self.subTest(negado=nombre):
                self.assertEqual(self.estado(self.almacenista, nombre), 403)
        self.assertEqual(self.estado(self.almacenista, "compra:findProductos"), 403)

    def test_compras_gestiona_ordenes_pero_no_inventario(self):
        # Sin parámetros esta ruta responde 400 (no 403), lo que prueba que sí hay acceso.
        self.assertEqual(self.estado(self.comprador, "compra:findProductos"), 400)
        for nombre in ("inventory:add", "inventory:movimiento", "categorias:add", "negocio:add"):
            with self.subTest(negado=nombre):
                self.assertEqual(self.estado(self.comprador, nombre), 403)

    def test_solo_admin_autoriza_y_rechaza(self):
        orden = self.orden(self.comprador)
        for usuario in (self.comprador, self.almacenista, self.consulta, self.sin_rol):
            for nombre in ("compra:autorizar_od", "compra:rechazar_od"):
                with self.subTest(usuario=usuario.username, accion=nombre):
                    self.assertEqual(self.estado(usuario, nombre, "post", args=[orden.pk]), 403)
        orden.refresh_from_db()
        self.assertEqual(orden.estatus, EstatusChoices.PENDIENTE)
        self.assertEqual(self.estado(self.admin, "compra:autorizar_od", "post", args=[orden.pk]), 302)
        orden.refresh_from_db()
        self.assertEqual(orden.estatus, EstatusChoices.AUTORIZADA)
        self.assertEqual(orden.usuario_autorizo, self.admin)

    def test_solicitante_no_autoriza_su_propia_orden(self):
        orden = self.orden(self.admin)
        self.estado(self.admin, "compra:autorizar_od", "post", args=[orden.pk])
        orden.refresh_from_db()
        self.assertEqual(orden.estatus, EstatusChoices.PENDIENTE)
        self.estado(self.admin_2, "compra:autorizar_od", "post", args=[orden.pk])
        orden.refresh_from_db()
        self.assertEqual(orden.estatus, EstatusChoices.AUTORIZADA)

    def test_superusuario_puede_todo(self):
        self.assertEqual(self.estado(self.usuario, "inventory:movimiento"), 200)
        orden = self.orden(self.usuario)
        self.estado(self.usuario, "compra:autorizar_od", "post", args=[orden.pk])
        orden.refresh_from_db()
        self.assertEqual(orden.estatus, EstatusChoices.AUTORIZADA)

    def test_solo_almacen_recibe_mercancia(self):
        orden = self.orden(self.comprador)
        for usuario in (self.comprador, self.consulta, self.sin_rol):
            with self.subTest(usuario=usuario.username):
                self.assertEqual(self.estado(usuario, "compra:completar_orden", "post", args=[orden.pk]), 403)
        self.assertEqual(self.estado(self.almacenista, "compra:completar_orden", "post", args=[orden.pk]), 302)


class InterfazPorRolTests(TestCase):
    """Los botones de escritura solo aparecen para quien puede usarlos."""

    @classmethod
    def setUpTestData(cls):
        for nombre, valor in crear_datos().items():
            setattr(cls, nombre, valor)
        cls.consulta = usuario_con_rol("ui_consulta", CONSULTA)
        cls.almacenista = usuario_con_rol("ui_almacen", ALMACEN)
        cls.comprador = usuario_con_rol("ui_compras", COMPRAS)

    def html(self, usuario, nombre, **kwargs):
        self.client.force_login(usuario)
        return self.client.get(reverse(nombre, **kwargs)).content.decode()

    def test_catalogo_oculta_edicion_a_consulta(self):
        url_editar = reverse("inventory:edit", args=[self.producto.pk])
        self.assertNotIn(url_editar, self.html(self.consulta, "inventory:productos"))
        self.assertIn(url_editar, self.html(self.almacenista, "inventory:productos"))

    def test_proveedores_ocultan_alta_a_almacen(self):
        url_alta = reverse("proveedores:add")
        self.assertNotIn(url_alta, self.html(self.almacenista, "proveedores:index"))
        self.assertIn(url_alta, self.html(self.comprador, "proveedores:index"))

    def test_orden_pendiente_solo_muestra_autorizar_a_admin(self):
        orden = OrdenDeCompra.objects.create(
            numero_de_orden="OC-UI", proveedor=self.proveedor, negocio=self.negocio,
            subtotal="1.00", total="1.00", usuario_creo=self.comprador, usuario_solicito=self.comprador)
        ProductoEnOrden.objects.create(orden=orden, producto=self.producto, cantidad=1,
                                       precio_unitario="1.00", subtotal="1.00")
        url = reverse("compra:autorizar_od", args=[orden.pk])
        self.assertNotIn(url, self.html(self.comprador, "compra:view", args=[orden.pk]))
        self.assertIn(url, self.html(usuario_con_rol("ui_admin", ADMIN), "compra:view", args=[orden.pk]))
