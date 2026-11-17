from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.roles import ALMACEN, asignar_rol
from categorias.models import Categoria


class CategoriasTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user(username="cat", password="test-only")
        asignar_rol(cls.usuario, ALMACEN)

    def setUp(self):
        self.client.force_login(self.usuario)

    def test_requiere_sesion(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("categorias:index")).status_code, 302)

    def test_crear_y_editar(self):
        self.client.post(reverse("categorias:add"), {"nombre": "Herramientas", "activo": "on"})
        categoria = Categoria.objects.get(nombre="Herramientas")
        self.client.post(reverse("categorias:edit", args=[categoria.pk]), {"nombre": "Herramienta menor"})
        categoria.refresh_from_db()
        self.assertEqual(categoria.nombre, "Herramienta menor")
        self.assertFalse(categoria.activo)

    def test_nombre_repetido_sin_importar_mayusculas(self):
        Categoria.objects.create(nombre="Materiales")
        respuesta = self.client.post(reverse("categorias:add"), {"nombre": "materiales", "activo": "on"})
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(Categoria.objects.count(), 1)

    def test_categoria_inexistente_es_404(self):
        self.assertEqual(self.client.get(reverse("categorias:edit", args=[999])).status_code, 404)
