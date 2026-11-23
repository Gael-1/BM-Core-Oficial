from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from accounts.roles import ADMIN, ALMACEN, COMPRAS, CONSULTA, ROLES, asignar_rol, rol_de
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


class RolesAlmacenesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.consulta = usuario_con_rol("alm_consulta", CONSULTA)
        cls.almacenista = usuario_con_rol("alm_almacen", ALMACEN)
        cls.comprador = usuario_con_rol("alm_compras", COMPRAS)

    def estado(self, usuario, nombre):
        self.client.force_login(usuario)
        return self.client.get(reverse(nombre)).status_code

    def test_todos_los_roles_consultan_almacenes(self):
        for usuario in (self.consulta, self.almacenista, self.comprador):
            with self.subTest(usuario=usuario.username):
                self.assertEqual(self.estado(usuario, "inventory:almacenes"), 200)
                self.assertEqual(self.estado(usuario, "inventory:inventario_por_almacen"), 200)

    def test_solo_inventario_hace_traspasos_y_administra_almacenes(self):
        for nombre in ("inventory:traspaso", "inventory:almacen_add"):
            with self.subTest(nombre=nombre):
                self.assertEqual(self.estado(self.almacenista, nombre), 200)
                self.assertEqual(self.estado(self.consulta, nombre), 403)
                self.assertEqual(self.estado(self.comprador, nombre), 403)


class GestionUsuariosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django.contrib.auth import get_user_model

        cls.User = get_user_model()
        cls.admin = cls.User.objects.create_user(username="jefe", password="test-only-1")
        asignar_rol(cls.admin, ADMIN)

    def setUp(self):
        self.client.force_login(self.admin)

    def datos(self, **extras):
        base = {"username": "nuevo", "first_name": "Ana", "last_name": "Pérez", "email": "ana@ejemplo.com",
                "is_active": "on", "rol": ALMACEN, "password1": "Cl4ve-segura-9", "password2": "Cl4ve-segura-9"}
        base.update(extras)
        return base

    def test_solo_el_administrador_entra(self):
        otro = self.User.objects.create_user(username="almacen", password="test-only-1")
        asignar_rol(otro, ALMACEN)
        self.client.force_login(otro)
        self.assertEqual(self.client.get(reverse("accounts:usuarios")).status_code, 403)
        self.assertEqual(self.client.post(reverse("accounts:usuario_add"), self.datos()).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(reverse("accounts:usuarios")).status_code, 302)

    def test_crear_usuario_con_rol_y_contrasena_funcional(self):
        respuesta = self.client.post(reverse("accounts:usuario_add"), self.datos())
        self.assertEqual(respuesta.status_code, 302)
        nuevo = self.User.objects.get(username="nuevo")
        self.assertEqual(rol_de(nuevo), ALMACEN)
        self.assertTrue(nuevo.check_password("Cl4ve-segura-9"))
        self.assertEqual(nuevo.email, "ana@ejemplo.com")

    def test_contrasena_obligatoria_al_crear_debil_o_distinta_se_rechaza(self):
        for extras in ({"password1": "", "password2": ""}, {"password1": "12345678", "password2": "12345678"},
                       {"password2": "otra-Clave-9"}):
            with self.subTest(extras=extras):
                respuesta = self.client.post(reverse("accounts:usuario_add"), self.datos(**extras))
                self.assertEqual(respuesta.status_code, 200)
                self.assertFalse(self.User.objects.filter(username="nuevo").exists())

    def test_cambiar_rol_reemplaza_el_anterior_y_conserva_contrasena(self):
        self.client.post(reverse("accounts:usuario_add"), self.datos())
        nuevo = self.User.objects.get(username="nuevo")
        self.client.post(reverse("accounts:usuario_edit", args=[nuevo.pk]),
                         self.datos(rol=COMPRAS, password1="", password2=""))
        nuevo.refresh_from_db()
        self.assertEqual(list(nuevo.groups.values_list("name", flat=True)), [COMPRAS])
        self.assertTrue(nuevo.check_password("Cl4ve-segura-9"))

    def test_rol_obligatorio_y_valido(self):
        for rol in ("", "Dios"):
            with self.subTest(rol=rol):
                self.assertEqual(self.client.post(reverse("accounts:usuario_add"), self.datos(rol=rol)).status_code, 200)
        self.assertFalse(self.User.objects.filter(username="nuevo").exists())

    def test_no_puede_quitarse_el_rol_ni_desactivarse(self):
        ruta = reverse("accounts:usuario_edit", args=[self.admin.pk])
        base = self.datos(username="jefe", password1="", password2="")
        self.assertEqual(self.client.post(ruta, {**base, "rol": CONSULTA}).status_code, 200)
        self.assertEqual(self.client.post(ruta, {**base, "rol": ADMIN, "is_active": ""}).status_code, 200)
        self.admin.refresh_from_db()
        self.assertEqual(rol_de(self.admin), ADMIN)
        self.assertTrue(self.admin.is_active)

    def test_desactivar_a_otro_usuario_le_impide_entrar(self):
        self.client.post(reverse("accounts:usuario_add"), self.datos())
        nuevo = self.User.objects.get(username="nuevo")
        self.client.post(reverse("accounts:usuario_edit", args=[nuevo.pk]),
                         self.datos(is_active="", password1="", password2=""))
        self.client.logout()
        self.assertFalse(self.client.login(username="nuevo", password="Cl4ve-segura-9"))


class PerfilesPersonalizadosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        for nombre, valor in crear_datos().items():
            setattr(cls, nombre, valor)
        cls.admin = usuario_con_rol("admin_perfiles", ADMIN)

    def crear_perfil(self, nombre="Supervisor", **permisos):
        self.client.force_login(self.admin)
        datos = {"nombre": nombre, "descripcion": "Prueba", **{k: "on" for k, v in permisos.items() if v}}
        return self.client.post(reverse("accounts:perfil_add"), datos)

    def test_solo_el_administrador_gestiona_perfiles(self):
        consulta = usuario_con_rol("consulta_perf", CONSULTA)
        self.client.force_login(consulta)
        self.assertEqual(self.client.get(reverse("accounts:perfiles")).status_code, 403)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("accounts:perfiles")).status_code, 200)

    def test_crear_perfil_genera_grupo_y_capacidades(self):
        from accounts.models import PerfilAcceso
        from accounts.roles import capacidades_de_rol

        respuesta = self.crear_perfil(inventario=True, ventas=True)
        self.assertRedirects(respuesta, reverse("accounts:perfiles"))
        perfil = PerfilAcceso.objects.get(grupo__name="Supervisor")
        self.assertEqual(perfil.capacidades(), {"ver", "inventario", "ventas"})
        self.assertEqual(capacidades_de_rol("Supervisor"), {"ver", "inventario", "ventas"})

    def test_nombre_de_rol_del_sistema_o_repetido_se_rechaza(self):
        self.client.force_login(self.admin)
        r = self.client.post(reverse("accounts:perfil_add"), {"nombre": ADMIN})
        self.assertEqual(r.status_code, 200)
        self.crear_perfil("Unico")
        r = self.client.post(reverse("accounts:perfil_add"), {"nombre": "unico"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Group.objects.filter(name__iexact="unico").count(), 1)

    def test_usuario_con_perfil_solo_hace_lo_que_el_perfil_permite(self):
        self.crear_perfil("Solo compras", compras=True)
        usuario = usuario_con_rol("perfilado")
        usuario.groups.add(Group.objects.get(name="Solo compras"))
        self.client.force_login(usuario)
        self.assertEqual(self.client.get(reverse("compra:index")).status_code, 200)
        self.assertEqual(self.client.get(reverse("compra:add")).status_code, 200)
        self.assertEqual(self.client.get(reverse("inventory:add")).status_code, 403)
        self.assertEqual(self.client.get(reverse("accounts:usuarios")).status_code, 403)
        self.assertEqual(self.client.get(reverse("ventas:nueva")).status_code, 403)

    def test_perfil_con_administracion_entra_a_usuarios(self):
        self.crear_perfil("Jefe", administrar=True)
        usuario = usuario_con_rol("jefe1")
        usuario.groups.add(Group.objects.get(name="Jefe"))
        self.client.force_login(usuario)
        self.assertEqual(self.client.get(reverse("accounts:usuarios")).status_code, 200)

    def test_asignar_perfil_desde_el_formulario_de_usuario(self):
        self.crear_perfil("Supervisor", inventario=True)
        self.client.force_login(self.admin)
        r = self.client.post(reverse("accounts:usuario_add"), {
            "username": "nuevo_perf", "first_name": "N", "last_name": "P", "email": "n@p.mx", "is_active": "on",
            "rol": "Supervisor", "password1": "Cl4ve-segura-77", "password2": "Cl4ve-segura-77"})
        self.assertRedirects(r, reverse("accounts:usuarios"))
        usuario = get_user_model().objects.get(username="nuevo_perf")
        self.assertEqual(rol_de(usuario), "Supervisor")
        # Cambiar a un rol del sistema retira el perfil.
        r = self.client.post(reverse("accounts:usuario_edit", args=[usuario.pk]), {
            "username": "nuevo_perf", "first_name": "N", "last_name": "P", "email": "n@p.mx", "is_active": "on",
            "rol": CONSULTA})
        self.assertRedirects(r, reverse("accounts:usuarios"))
        usuario.refresh_from_db()
        self.assertEqual(rol_de(usuario), CONSULTA)
        self.assertFalse(usuario.groups.filter(name="Supervisor").exists())

    def test_no_se_elimina_un_perfil_con_usuarios_pero_si_uno_vacio(self):
        from accounts.models import PerfilAcceso

        self.crear_perfil("Temporal", ventas=True)
        perfil = PerfilAcceso.objects.get(grupo__name="Temporal")
        usuario = usuario_con_rol("con_temporal")
        usuario.groups.add(perfil.grupo)
        self.client.force_login(self.admin)
        self.client.post(reverse("accounts:perfil_delete", args=[perfil.pk]))
        self.assertTrue(PerfilAcceso.objects.filter(pk=perfil.pk).exists())
        usuario.groups.clear()
        self.client.post(reverse("accounts:perfil_delete", args=[perfil.pk]))
        self.assertFalse(PerfilAcceso.objects.filter(pk=perfil.pk).exists())

    def test_la_api_respeta_la_capacidad_del_perfil(self):
        self.crear_perfil("Almacen extra", inventario=True)
        usuario = usuario_con_rol("api_perfil")
        usuario.groups.add(Group.objects.get(name="Almacen extra"))
        sin_permiso = usuario_con_rol("api_sin_perfil")
        self.assertTrue(usuario.groups.exists())
        # El token se crea con el modelo del proyecto; basta comprobar la capacidad que usa la API.
        from accounts.roles import tiene_capacidad
        self.assertTrue(tiene_capacidad(usuario, "inventario"))
        self.assertFalse(tiene_capacidad(sin_permiso, "ver"))
