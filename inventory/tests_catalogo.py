import io

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from accounts.roles import CONSULTA, asignar_rol
from django.contrib.auth import get_user_model
from inventory import catalogo
from inventory.models import Producto
from inventory.tests import crear_datos


def archivo(texto, nombre="productos.csv"):
    return SimpleUploadedFile(nombre, texto.encode("utf-8"), content_type="text/csv")


ENCABEZADO = "sku,codigo_barras,nombre,categoria,precio,stock_min,medida,descripcion\n"


class CsvProductosTests(TestCase):
    def setUp(self):
        self.d = crear_datos()
        self.usuario = self.d["usuario"]
        self.client.force_login(self.usuario)

    def test_exportar_incluye_productos_y_neutraliza_formulas(self):
        p = self.d["producto"]
        p.nombre = "=SUMA(A1)"
        p.save()
        respuesta = self.client.get(reverse("inventory:exportar"))
        self.assertEqual(respuesta.status_code, 200)
        texto = respuesta.content.decode("utf-8-sig")
        self.assertTrue(texto.startswith("sku,codigo_barras,nombre"))
        self.assertIn("TEST-1", texto)
        self.assertIn("'=SUMA(A1)", texto)

    def test_importar_crea_y_actualiza_por_sku(self):
        csv = (ENCABEZADO + "TEST-1,,Producto renombrado,Materiales,15.00,3,Pieza,\n"
               "NUEVO-1,7501,Nuevo,Materiales,9.90,1,Pieza,Con descripción\n")
        respuesta = self.client.post(reverse("inventory:importar"), {"archivo": archivo(csv)})
        self.assertRedirects(respuesta, reverse("inventory:productos"))
        self.assertEqual(Producto.objects.get(sku="TEST-1").nombre, "Producto renombrado")
        self.assertEqual(str(Producto.objects.get(sku="TEST-1").precio), "15.00")
        nuevo = Producto.objects.get(sku="NUEVO-1")
        self.assertEqual(nuevo.codigo_barras, "7501")
        self.assertEqual(nuevo.creado_por, self.usuario)

    def test_un_error_no_guarda_nada(self):
        csv = (ENCABEZADO + "NUEVO-1,,Bueno,Materiales,9.90,1,Pieza,\n"
               "NUEVO-2,,Malo,NoExiste,9.90,1,Pieza,\n"
               "NUEVO-3,,Precio,Materiales,abc,1,Pieza,\n")
        respuesta = self.client.post(reverse("inventory:importar"), {"archivo": archivo(csv)})
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Fila 3")
        self.assertContains(respuesta, "Fila 4")
        self.assertFalse(Producto.objects.filter(sku="NUEVO-1").exists())

    def test_columnas_faltantes_y_archivo_vacio(self):
        with self.assertRaises(catalogo.CsvInvalido):
            catalogo.importar_csv(io.BytesIO(b"sku,nombre\nA,B\n"), self.usuario)
        with self.assertRaises(catalogo.CsvInvalido):
            catalogo.importar_csv(io.BytesIO(ENCABEZADO.encode()), self.usuario)

    def test_sku_repetido_y_codigo_de_barras_de_otro_producto(self):
        with self.assertRaises(catalogo.CsvInvalido):
            catalogo.importar_csv(io.BytesIO((ENCABEZADO + "A,,X,Materiales,1,0,,\nA,,Y,Materiales,1,0,,\n").encode()),
                                  self.usuario)
        p = self.d["producto"]
        p.codigo_barras = "999"
        p.save()
        with self.assertRaises(catalogo.CsvInvalido):
            catalogo.importar_csv(io.BytesIO((ENCABEZADO + "OTRO,999,X,Materiales,1,0,,\n").encode()), self.usuario)
        self.assertFalse(Producto.objects.filter(sku="OTRO").exists())

    def test_consulta_puede_exportar_pero_no_importar(self):
        lector = get_user_model().objects.create_user(username="lector", password="test-only")
        asignar_rol(lector, CONSULTA)
        self.client.force_login(lector)
        self.assertEqual(self.client.get(reverse("inventory:exportar")).status_code, 200)
        self.assertNotEqual(self.client.get(reverse("inventory:importar")).status_code, 200)
        respuesta = self.client.post(reverse("inventory:importar"),
                                     {"archivo": archivo(ENCABEZADO + "Z,,Z,Materiales,1,0,,\n")})
        self.assertNotEqual(respuesta.status_code, 200)
        self.assertFalse(Producto.objects.filter(sku="Z").exists())


class EtiquetasTests(TestCase):
    def setUp(self):
        self.d = crear_datos()
        self.client.force_login(self.d["usuario"])

    def test_la_hoja_lista_los_productos(self):
        respuesta = self.client.get(reverse("inventory:etiquetas"))
        self.assertContains(respuesta, "TEST-1")

    def test_filtra_por_ids(self):
        respuesta = self.client.get(reverse("inventory:etiquetas"), {"ids": "99999"})
        self.assertNotContains(respuesta, "TEST-1")

    def test_valor_del_qr_prefiere_codigo_de_barras(self):
        p = self.d["producto"]
        self.assertEqual(catalogo.valor_qr(p), "TEST-1")
        p.codigo_barras = "7501234"
        self.assertEqual(catalogo.valor_qr(p), "7501234")

    def test_qr_es_svg_cuando_segno_esta_instalado(self):
        try:
            import segno  # noqa: F401
        except ImportError:
            self.skipTest("segno no está instalado")
        self.assertIn("<svg", catalogo.qr_svg("TEST-1"))
