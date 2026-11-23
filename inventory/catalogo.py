"""Etiquetas QR y carga/descarga de productos en CSV."""
import csv
import io
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils.safestring import mark_safe

from categorias.models import Categoria

from .models import Medidas_Inventario, Producto

COLUMNAS = ["sku", "codigo_barras", "nombre", "categoria", "precio", "stock_min", "medida", "descripcion"]
MAX_FILAS = 2000
MAX_BYTES = 2 * 1024 * 1024


class CsvInvalido(Exception):
    def __init__(self, errores):
        self.errores = errores
        super().__init__("; ".join(errores))


def valor_qr(producto):
    """Lo que codifica la etiqueta: el código de barras si existe y, si no, el SKU."""
    return producto.codigo_barras or producto.sku


def qr_svg(texto):
    """SVG del QR listo para incrustar, o None si la librería `segno` no está instalada."""
    try:
        import segno
    except ImportError:
        return None
    return mark_safe(segno.make(texto, error="m").svg_inline(scale=4, border=1))


def _seguro(valor):
    """Evita que Excel interprete una celda como fórmula."""
    texto = "" if valor is None else str(valor)
    return "'" + texto if texto[:1] in ("=", "+", "-", "@", "\t", "\r") else texto


def exportar_csv():
    salida = io.StringIO()
    escritor = csv.writer(salida)
    escritor.writerow(COLUMNAS)
    productos = Producto.objects.filter(activo=True).select_related("categoria_id", "medida").order_by("sku")
    for p in productos:
        escritor.writerow([
            _seguro(p.sku), _seguro(p.codigo_barras), _seguro(p.nombre), _seguro(p.categoria_id.nombre),
            p.precio, f"{p.stock_min:g}", _seguro(p.medida.nombre if p.medida else ""), _seguro(p.descripcion),
        ])
    return "﻿" + salida.getvalue()  # BOM para que Excel respete los acentos


def importar_csv(archivo, usuario):
    """Crea o actualiza productos por SKU. Todo o nada: ante cualquier error no se guarda nada.

    Devuelve (creados, actualizados). Las categorías y medidas deben existir.
    """
    crudo = archivo.read(MAX_BYTES + 1)
    if len(crudo) > MAX_BYTES:
        raise CsvInvalido(["El archivo pesa más de 2 MB."])
    try:
        texto = crudo.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise CsvInvalido(["El archivo debe estar guardado como CSV UTF-8."])
    lector = csv.DictReader(io.StringIO(texto))
    faltantes = [c for c in ("sku", "nombre", "categoria", "precio") if c not in (lector.fieldnames or [])]
    if faltantes:
        raise CsvInvalido([f"Faltan columnas obligatorias: {', '.join(faltantes)}."])

    categorias = {c.nombre.strip().lower(): c for c in Categoria.objects.filter(activo=True)}
    medidas = {m.nombre.strip().lower(): m for m in Medidas_Inventario.objects.all()}
    filas, errores, vistos = [], [], set()
    for n, fila in enumerate(lector, start=2):
        if n - 1 > MAX_FILAS:
            errores.append(f"Máximo {MAX_FILAS} filas por archivo.")
            break
        sku = (fila.get("sku") or "").strip()
        nombre = (fila.get("nombre") or "").strip()
        if not sku or not nombre:
            errores.append(f"Fila {n}: SKU y nombre son obligatorios.")
            continue
        if sku in vistos:
            errores.append(f"Fila {n}: el SKU «{sku}» está repetido en el archivo.")
            continue
        vistos.add(sku)
        categoria = categorias.get((fila.get("categoria") or "").strip().lower())
        if categoria is None:
            errores.append(f"Fila {n}: la categoría «{fila.get('categoria')}» no existe.")
        nombre_medida = (fila.get("medida") or "").strip()
        medida = medidas.get(nombre_medida.lower()) if nombre_medida else None
        if nombre_medida and medida is None:
            errores.append(f"Fila {n}: la unidad «{nombre_medida}» no existe.")
        try:
            precio = Decimal((fila.get("precio") or "").strip())
            if not precio.is_finite() or precio < Decimal("0.01"):
                raise InvalidOperation
        except InvalidOperation:
            errores.append(f"Fila {n}: el precio debe ser un número mayor a 0.")
            precio = None
        try:
            stock_min = float((fila.get("stock_min") or "0").strip() or 0)
            if stock_min < 0 or stock_min != stock_min or stock_min == float("inf"):
                raise ValueError
        except ValueError:
            errores.append(f"Fila {n}: el stock mínimo debe ser un número de 0 en adelante.")
            stock_min = None
        barras = (fila.get("codigo_barras") or "").strip() or None
        if len(sku) > 100 or len(nombre) > 100 or (barras and len(barras) > 100):
            errores.append(f"Fila {n}: SKU, nombre y código de barras admiten hasta 100 caracteres.")
        if categoria and precio is not None and stock_min is not None:
            filas.append((sku, barras, nombre, categoria, precio, stock_min, medida,
                          (fila.get("descripcion") or "").strip()[:255]))
    if not filas and not errores:
        errores.append("El archivo no tiene productos.")
    if errores:
        raise CsvInvalido(errores[:20] + ([f"…y {len(errores) - 20} errores más."] if len(errores) > 20 else []))

    creados = actualizados = 0
    with transaction.atomic():
        for sku, barras, nombre, categoria, precio, stock_min, medida, descripcion in filas:
            if barras:
                otro = Producto.objects.filter(codigo_barras=barras).exclude(sku=sku).first()
                if otro:
                    raise CsvInvalido([f"El código de barras «{barras}» ya pertenece a {otro.sku}."])
            producto = Producto.objects.filter(sku=sku).first()
            datos = {"codigo_barras": barras, "nombre": nombre, "categoria_id": categoria, "precio": precio,
                     "stock_min": stock_min, "medida": medida, "descripcion": descripcion, "activo": True,
                     "modificado_por": usuario}
            if producto:
                for campo, valor in datos.items():
                    setattr(producto, campo, valor)
                producto.save()
                actualizados += 1
            else:
                Producto.objects.create(sku=sku, creado_por=usuario, **datos)
                creados += 1
    return creados, actualizados
