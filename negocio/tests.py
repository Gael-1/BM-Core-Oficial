from django.test import TestCase

from negocio.models import Negocio
from proveedores.models import RegimenFiscal


class CatalogoRegimenFiscalTests(TestCase):
    def test_catalogo_del_sat_viene_cargado(self):
        self.assertGreaterEqual(RegimenFiscal.objects.count(), 20)
        for codigo in (601, 612, 626):
            with self.subTest(codigo=codigo):
                self.assertTrue(RegimenFiscal.objects.filter(codigo=codigo, activo=True).exists())


class CatalogoMedidasTests(TestCase):
    def test_unidades_de_medida_vienen_cargadas(self):
        from inventory.models import Medidas_Inventario

        self.assertFalse(Medidas_Inventario.objects.get(nombre="Pieza").permite_decimales)
        self.assertTrue(Medidas_Inventario.objects.get(nombre="Kilogramo").permite_decimales)


class InventarioDeNegocioTests(TestCase):
    def test_suma_las_existencias_de_los_almacenes_del_negocio(self):
        from inventory import services
        from inventory.models import Almacen
        from inventory.tests import crear_datos

        d = crear_datos()
        otro = Almacen.objects.create(nombre="Bodega", negocio=d["negocio"])
        services.asegurar_existencias(d["inventario"])
        services.mover(d["inventario"], d["almacen"], -4)
        services.mover(d["inventario"], otro, 4)
        filas = services.inventario_de_negocio(d["negocio"])
        self.assertEqual(len(filas), 1)
        self.assertEqual(filas[0]["cantidad"], 10)
        self.assertEqual({a.nombre: c for a, c in filas[0]["almacenes"]}, {"Principal": 6, "Bodega": 4})

    def test_ignora_almacenes_de_otros_negocios(self):
        from inventory import services
        from inventory.tests import crear_datos
        from negocio.models import Negocio

        d = crear_datos()
        otro = Negocio.objects.create(nombre="Otro", nombre_fiscal="Otro", direccion="X", rfc="XYZ010101AA1",
                                      codigo_postal="64000", regimen_fiscal=d["regimen"])
        self.assertEqual(services.inventario_de_negocio(otro), [])

    def test_pantalla_responde(self):
        from django.urls import reverse
        from inventory.tests import crear_datos

        d = crear_datos()
        self.client.force_login(d["usuario"])
        respuesta = self.client.get(reverse("negocio:view_inventario", args=[d["negocio"].pk]))
        self.assertContains(respuesta, "Producto")
        self.assertContains(respuesta, "Principal: 10")


class SeedDemoTests(TestCase):
    def test_es_idempotente(self):
        from io import StringIO

        from django.core.management import call_command
        from django.test import override_settings
        from inventory.models import Producto

        with override_settings(DEBUG=True):
            call_command("seed_demo", stdout=StringIO())
            call_command("seed_demo", stdout=StringIO())
        self.assertEqual(Producto.objects.filter(sku__in=["TOR-001", "CEM-001"]).count(), 2)
        self.assertEqual(Negocio.objects.filter(rfc="DEM010101AA1").count(), 1)
