from django.test import TestCase

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
