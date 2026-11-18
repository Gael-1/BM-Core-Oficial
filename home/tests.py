from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from compra.models import EstatusChoices, OrdenDeCompra
from home.kpis import calcular_kpis
from inventory.models import Producto, Registro_Inventario
from inventory.tests import crear_datos


class KpiTests(TestCase):
    def setUp(self):
        self.d = crear_datos()  # 1 producto de $12.50 con 10 unidades

    def test_valor_y_existencia(self):
        kpi = calcular_kpis()
        self.assertEqual(kpi["valor_inventario"], 125.0)
        self.assertEqual(kpi["unidades_en_existencia"], 10)
        self.assertEqual(kpi["productos_agotados"], 0)

    def test_producto_sin_existencia_cuenta_como_agotado(self):
        inventario = self.d["inventario"]
        inventario.cantidad = 0
        inventario.save()
        Producto.objects.create(nombre="Sin inventario", sku="SIN-1", categoria_id=self.d["categoria"],
                                precio="5", creado_por=self.d["usuario"], modificado_por=self.d["usuario"])
        self.assertEqual(calcular_kpis()["productos_agotados"], 2)

    def test_rotacion_usa_solo_salidas_del_periodo(self):
        inventario = self.d["inventario"]
        for dias, cantidad in ((2, 5), (45, 100)):
            mov = Registro_Inventario.objects.create(
                inventario_producto_id=inventario, tipo_movimiento="SALIDA", cantidad_anterior=10,
                cantidad_nueva=cantidad, creado_por=self.d["usuario"])
            Registro_Inventario.objects.filter(pk=mov.pk).update(creado=timezone.now() - timedelta(days=dias))
        kpi = calcular_kpis()
        self.assertEqual(kpi["salidas_periodo"], 5)
        self.assertEqual(kpi["rotacion"], 0.5)

    def test_rotacion_sin_existencia_no_divide_entre_cero(self):
        self.d["inventario"].delete()
        self.assertEqual(calcular_kpis()["rotacion"], 0.0)

    def test_gasto_por_proveedor_solo_compras_recibidas(self):
        d = self.d
        for estatus, total in ((EstatusChoices.COMPLETADA, "300.00"), (EstatusChoices.PENDIENTE, "999.00")):
            OrdenDeCompra.objects.create(numero_de_orden=f"OC-{estatus}", proveedor=d["proveedor"], negocio=d["negocio"],
                                         subtotal=total, total=total, estatus=estatus, usuario_creo=d["usuario"])
        gasto = calcular_kpis()["gasto_proveedores"]
        self.assertEqual(len(gasto), 1)
        self.assertEqual(float(gasto[0]["total_gastado"]), 300.0)
        self.assertEqual(gasto[0]["porcentaje"], 100)

    def test_pantalla_de_inicio_muestra_los_indicadores(self):
        self.client.force_login(self.d["usuario"])
        respuesta = self.client.get(reverse("home:index"))
        self.assertContains(respuesta, "Indicadores clave")
        self.assertContains(respuesta, "$125.00")
