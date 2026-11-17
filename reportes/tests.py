from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from inventory.models import Registro_Inventario
from reportes.views import inicio_reportes


@override_settings(USE_TZ=True, TIME_ZONE="America/Mexico_City")
class ReportesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        usuario = get_user_model().objects.create_user(username="reportes")
        cls.registros = {}
        for tipo in ("ENTRADA", "entrada", "ALTA", "SALIDA", "salida", "BAJA", "TRASPASO"):
            cls.registros[tipo] = Registro_Inventario.objects.create(
                tipo_movimiento=tipo, cantidad_nueva=1, creado_por=usuario
            )

    def consultar(self, **params):
        request = RequestFactory().get("/reportes/", params)
        with patch("reportes.views.render", side_effect=lambda request, template, context: context):
            return inicio_reportes(request)

    def test_entradas_incluyen_compras_y_registros_historicos(self):
        resultado = self.consultar(tipo_reporte="entrada")
        self.assertEqual(set(resultado["movimientos"].values_list("tipo_movimiento", flat=True)),
                         {"ENTRADA", "entrada", "ALTA"})

    def test_salidas_incluyen_registros_historicos(self):
        resultado = self.consultar(tipo_reporte="salida")
        self.assertEqual(set(resultado["movimientos"].values_list("tipo_movimiento", flat=True)),
                         {"SALIDA", "salida", "BAJA"})

    def test_sin_filtros_incluye_traspasos(self):
        self.assertEqual(self.consultar()["movimientos"].count(), 7)

    def test_fechas_invalidas_y_rangos_invertidos(self):
        for params in (
            {"fecha_inicio": "incorrecta"},
            {"fecha_fin": "2026-02-30"},
            {"fecha_inicio": "2026-10-07", "fecha_fin": "2026-10-06"},
            {"tipo_reporte": "desconocido"},
        ):
            with self.subTest(params=params):
                resultado = self.consultar(**params)
                self.assertTrue(resultado["errores_filtros"])
                self.assertFalse(resultado["movimientos"].exists())

    def test_limites_de_fecha_inclusivos_en_horario_local(self):
        zona = ZoneInfo("America/Mexico_City")
        momentos = [
            datetime(2026, 10, 5, 23, 59, tzinfo=zona),
            datetime(2026, 10, 6, 0, 0, tzinfo=zona),
            datetime(2026, 10, 6, 23, 59, tzinfo=zona),
            datetime(2026, 10, 7, 0, 0, tzinfo=zona),
        ]
        ids = []
        for registro, momento in zip(self.registros.values(), momentos):
            Registro_Inventario.objects.filter(pk=registro.pk).update(creado=momento)
            ids.append(registro.pk)
        # Limitar al tipo no es necesario: los demás registros tienen otra fecha.
        Registro_Inventario.objects.exclude(pk__in=ids).update(creado=momentos[0])
        ambos = self.consultar(fecha_inicio="2026-10-06", fecha_fin="2026-10-06")
        self.assertEqual(set(ambos["movimientos"].values_list("pk", flat=True)), set(ids[1:3]))
        desde = self.consultar(fecha_inicio="2026-10-06")
        self.assertEqual(set(desde["movimientos"].values_list("pk", flat=True)), set(ids[1:]))
        hasta = self.consultar(fecha_fin="2026-10-05")
        self.assertEqual(hasta["movimientos"].count(), 4)


class ReportesFiltrosTests(TestCase):
    """Filtros por proveedor y producto, y exportación a CSV."""

    @classmethod
    def setUpTestData(cls):
        from inventory.tests import crear_datos
        from compra.models import OrdenDeCompra

        for nombre, valor in crear_datos().items():
            setattr(cls, nombre, valor)
        orden = OrdenDeCompra.objects.create(
            numero_de_orden="OC-REP", proveedor=cls.proveedor, negocio=cls.negocio,
            subtotal="10.00", total="10.00", usuario_creo=cls.usuario,
        )
        cls.de_compra = Registro_Inventario.objects.create(
            inventario_producto_id=cls.inventario, tipo_movimiento="ENTRADA", cantidad_nueva=3,
            creado_por=cls.usuario, orden_compra=orden, comentarios="=1+1",
        )
        cls.manual = Registro_Inventario.objects.create(
            inventario_producto_id=cls.inventario, tipo_movimiento="SALIDA", cantidad_nueva=2,
            creado_por=cls.usuario,
        )

    def setUp(self):
        self.client.force_login(self.usuario)

    def test_filtra_por_proveedor_y_producto(self):
        por_proveedor = self.client.get(reverse("reportes:inicio"), {"proveedor": self.proveedor.pk})
        self.assertEqual(list(por_proveedor.context["movimientos"]), [self.de_compra])
        por_producto = self.client.get(reverse("reportes:inicio"), {"producto": self.producto.pk})
        self.assertEqual(por_producto.context["resumen"]["registros"], 2)
        self.assertEqual(por_producto.context["resumen"]["entradas"], 3)
        self.assertEqual(por_producto.context["resumen"]["salidas"], 2)

    def test_proveedor_inexistente_es_filtro_invalido(self):
        respuesta = self.client.get(reverse("reportes:inicio"), {"proveedor": 99999})
        self.assertTrue(respuesta.context["errores_filtros"])
        self.assertFalse(respuesta.context["movimientos"].exists())

    def test_exporta_csv_y_neutraliza_formulas(self):
        respuesta = self.client.get(reverse("reportes:inicio"), {"exportar": "csv"})
        self.assertTrue(respuesta["Content-Type"].startswith("text/csv"))
        texto = respuesta.content.decode("utf-8-sig")
        self.assertIn("Fecha,Producto,Tipo", texto)
        self.assertIn("OC-REP", texto)
        self.assertIn("'=1+1", texto)

    def test_no_exporta_con_filtros_invalidos(self):
        respuesta = self.client.get(reverse("reportes:inicio"), {"exportar": "csv", "fecha_inicio": "mal"})
        self.assertNotEqual(respuesta.get("Content-Type", "").split(";")[0], "text/csv")
