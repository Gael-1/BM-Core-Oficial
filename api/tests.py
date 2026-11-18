from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.roles import ADMIN, ALMACEN, COMPRAS, CONSULTA, asignar_rol
from api.models import TokenAPI
from inventory import services
from inventory.models import Almacen, Inventario_Producto, Registro_Inventario
from inventory.tests import crear_datos


class ApiBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.d = crear_datos()  # TEST-1, 10 piezas en «Principal», unidad Pieza (sin decimales)
        User = get_user_model()
        cls.tokens = {}
        for rol in (ADMIN, ALMACEN, COMPRAS, CONSULTA):
            usuario = User.objects.create_user(username=f"api_{rol.lower()}", password="test-only")
            asignar_rol(usuario, rol)
            cls.tokens[rol] = TokenAPI.crear(usuario, f"sistema {rol}")[1]
        cls.bodega = Almacen.objects.create(nombre="Bodega norte", negocio=cls.d["negocio"])

    def get(self, ruta, rol=CONSULTA, **params):
        return self.client.get(ruta, params, HTTP_AUTHORIZATION=f"Bearer {self.tokens[rol]}")

    def post(self, cuerpo, rol=ALMACEN, tipo="application/json"):
        import json

        datos = cuerpo if isinstance(cuerpo, str) else json.dumps(cuerpo)
        return self.client.post(reverse("api_v1:movimientos"), datos, content_type=tipo,
                                HTTP_AUTHORIZATION=f"Bearer {self.tokens[rol]}")


class AutenticacionApiTests(ApiBase):
    def test_sin_token_o_con_token_invalido_da_401(self):
        ruta = reverse("api_v1:productos")
        self.assertEqual(self.client.get(ruta).status_code, 401)
        for cabecera in ("Bearer bmc_falso", "Bearer ", "Token abc", "Basic xyz", "bmc_sin_esquema"):
            with self.subTest(cabecera=cabecera):
                self.assertEqual(self.client.get(ruta, HTTP_AUTHORIZATION=cabecera).status_code, 401)

    def test_la_sesion_del_navegador_no_sirve_en_la_api(self):
        self.client.force_login(self.d["usuario"])
        self.assertEqual(self.client.get(reverse("api_v1:productos")).status_code, 401)

    def test_el_token_no_abre_las_pantallas_web(self):
        respuesta = self.client.get(reverse("inventory:productos"), HTTP_AUTHORIZATION=f"Bearer {self.tokens[ADMIN]}")
        self.assertEqual(respuesta.status_code, 302)

    def test_token_revocado_o_usuario_inactivo_se_rechaza(self):
        TokenAPI.objects.filter(nombre=f"sistema {CONSULTA}").update(activo=False)
        self.assertEqual(self.get(reverse("api_v1:productos")).status_code, 401)
        usuario = get_user_model().objects.get(username="api_almacenista")
        usuario.is_active = False
        usuario.save()
        self.assertEqual(self.get(reverse("api_v1:productos"), rol=ALMACEN).status_code, 401)

    def test_solo_se_guarda_el_hash_del_token(self):
        token = self.tokens[ADMIN]
        registro = TokenAPI.objects.get(nombre=f"sistema {ADMIN}")
        self.assertNotIn(token, (registro.hash, registro.inicio))
        self.assertTrue(token.startswith(registro.inicio))
        self.assertEqual(len(registro.hash), 64)

    def test_registra_el_ultimo_uso(self):
        self.get(reverse("api_v1:productos"))
        self.assertIsNotNone(TokenAPI.objects.get(nombre=f"sistema {CONSULTA}").ultimo_uso)


class LecturaApiTests(ApiBase):
    def test_lista_de_productos_con_existencia(self):
        datos = self.get(reverse("api_v1:productos")).json()
        self.assertEqual(datos["total"], 1)
        producto = datos["resultados"][0]
        self.assertEqual((producto["sku"], producto["existencia"], producto["medida"]), ("TEST-1", 10, "Pieza"))
        self.assertEqual(producto["precio"], "12.50")

    def test_busqueda_y_filtro_de_activos(self):
        ruta = reverse("api_v1:productos")
        self.assertEqual(self.get(ruta, q="test-1").json()["total"], 1)
        self.assertEqual(self.get(ruta, q="no-existe").json()["total"], 0)
        self.assertEqual(self.get(ruta, activo="false").json()["total"], 0)

    def test_parametros_de_paginacion_invalidos_no_rompen(self):
        respuesta = self.get(reverse("api_v1:productos"), limite="abc", pagina="-4")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(self.get(reverse("api_v1:productos"), limite="100000").json()["pagina"], 1)

    def test_detalle_incluye_desglose_por_almacen(self):
        inventario = self.d["inventario"]
        services.asegurar_existencias(inventario)
        services.mover(inventario, self.d["almacen"], -4)
        services.mover(inventario, self.bodega, 4)
        datos = self.get(reverse("api_v1:producto", args=[self.d["producto"].pk])).json()
        self.assertEqual({a["almacen"]: a["cantidad"] for a in datos["almacenes"]}, {"Principal": 6, "Bodega norte": 4})

    def test_producto_inexistente_da_404(self):
        self.assertEqual(self.get(reverse("api_v1:producto", args=[999999])).status_code, 404)

    def test_almacenes_y_movimientos(self):
        self.assertEqual(len(self.get(reverse("api_v1:almacenes")).json()["resultados"]), 2)
        self.assertEqual(self.get(reverse("api_v1:movimientos"), tipo="entrada", limite="5").json()["resultados"], [])


class MovimientosApiTests(ApiBase):
    def existencia(self):
        return Inventario_Producto.objects.get(producto_id=self.d["producto"]).cantidad

    def test_salida_por_sku_descuenta_y_responde_201(self):
        respuesta = self.post({"sku": "TEST-1", "tipo": "salida", "cantidad": 3})
        self.assertEqual(respuesta.status_code, 201)
        self.assertEqual(respuesta.json()["existencia"], 7)
        self.assertEqual(self.existencia(), 7)
        movimiento = Registro_Inventario.objects.get()
        self.assertEqual((movimiento.tipo_movimiento, movimiento.cantidad_nueva), ("SALIDA", 3))
        self.assertEqual(movimiento.creado_por.username, "api_almacenista")

    def test_entrada_a_un_almacen_concreto(self):
        respuesta = self.post({"producto": self.d["producto"].pk, "tipo": "ENTRADA", "cantidad": 5,
                               "almacen": self.bodega.pk})
        self.assertEqual(respuesta.status_code, 201)
        inventario = Inventario_Producto.objects.get()
        self.assertEqual(inventario.cantidad, 15)
        self.assertEqual(services.existencia_en(inventario, self.bodega), 5)

    def test_existencia_insuficiente_da_409_y_no_cambia_nada(self):
        self.assertEqual(self.post({"sku": "TEST-1", "tipo": "SALIDA", "cantidad": 11}).status_code, 409)
        self.assertEqual(self.post({"sku": "TEST-1", "tipo": "SALIDA", "cantidad": 1, "almacen": self.bodega.pk}).status_code, 409)
        self.assertEqual(self.existencia(), 10)
        self.assertFalse(Registro_Inventario.objects.exists())

    def test_datos_invalidos_dan_400(self):
        for cuerpo in ({"sku": "TEST-1", "tipo": "SALIDA", "cantidad": 0},
                       {"sku": "TEST-1", "tipo": "SALIDA", "cantidad": -2},
                       {"sku": "TEST-1", "tipo": "SALIDA", "cantidad": "3"},
                       {"sku": "TEST-1", "tipo": "SALIDA", "cantidad": True},
                       {"sku": "TEST-1", "tipo": "SALIDA", "cantidad": 1.5},
                       {"sku": "TEST-1", "tipo": "SALIDA"},
                       {"sku": "TEST-1", "tipo": "AJUSTE", "cantidad": 1},
                       {"sku": "TEST-1", "tipo": "SALIDA", "cantidad": 1, "almacen": 99999},
                       {"sku": "TEST-1", "tipo": "SALIDA", "cantidad": 1, "motivo": 99999},
                       "[1, 2]", "no es json", '{"sku": "TEST-1", "tipo": "SALIDA", "cantidad": NaN}'):
            with self.subTest(cuerpo=cuerpo):
                self.assertEqual(self.post(cuerpo).status_code, 400)
        self.assertEqual(self.existencia(), 10)

    def test_producto_desconocido_o_inactivo(self):
        self.assertEqual(self.post({"sku": "NADA", "tipo": "SALIDA", "cantidad": 1}).status_code, 404)
        self.assertEqual(self.post({"tipo": "SALIDA", "cantidad": 1}).status_code, 404)
        self.d["producto"].activo = False
        self.d["producto"].save()
        self.assertEqual(self.post({"sku": "TEST-1", "tipo": "SALIDA", "cantidad": 1}).status_code, 400)

    def test_solo_administrador_y_almacenista_pueden_escribir(self):
        cuerpo = {"sku": "TEST-1", "tipo": "SALIDA", "cantidad": 1}
        self.assertEqual(self.post(cuerpo, rol=CONSULTA).status_code, 403)
        self.assertEqual(self.post(cuerpo, rol=COMPRAS).status_code, 403)
        self.assertEqual(self.existencia(), 10)
        self.assertEqual(self.post(cuerpo, rol=ADMIN).status_code, 201)

    def test_post_sin_token_da_401_y_otros_metodos_405(self):
        self.assertEqual(self.client.post(reverse("api_v1:movimientos"), "{}", content_type="application/json").status_code, 401)
        respuesta = self.client.delete(reverse("api_v1:productos"), HTTP_AUTHORIZATION=f"Bearer {self.tokens[ADMIN]}")
        self.assertEqual(respuesta.status_code, 405)


class GestionTokensTests(ApiBase):
    def setUp(self):
        self.admin = get_user_model().objects.get(username="api_administrador")
        self.client.force_login(self.admin)

    def test_solo_el_administrador_ve_la_pantalla(self):
        self.client.force_login(get_user_model().objects.get(username="api_almacenista"))
        self.assertEqual(self.client.get(reverse("api:tokens")).status_code, 403)

    def test_crear_muestra_el_token_una_vez_y_funciona(self):
        respuesta = self.client.post(reverse("api:tokens"), {
            "nombre": "Punto de venta", "usuario": get_user_model().objects.get(username="api_consulta").pk})
        token = respuesta.context["token_nuevo"]
        self.assertContains(respuesta, token)
        self.assertNotContains(self.client.get(reverse("api:tokens")), token)
        self.client.logout()
        self.assertEqual(self.client.get(reverse("api_v1:productos"), HTTP_AUTHORIZATION=f"Bearer {token}").status_code, 200)

    def test_revocar_deja_el_token_sin_acceso(self):
        registro = TokenAPI.objects.get(nombre=f"sistema {CONSULTA}")
        self.assertEqual(self.client.post(reverse("api:revocar", args=[registro.pk])).status_code, 302)
        self.client.logout()
        self.assertEqual(self.get(reverse("api_v1:productos")).status_code, 401)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("api:revocar", args=[registro.pk])).status_code, 405)
