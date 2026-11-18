"""Prefacturas: documento informativo con los datos de una factura. NO es un CFDI timbrado.

Para emitir facturas válidas ante el SAT hace falta un proveedor autorizado de certificación (PAC).
`ProveedorTimbrado` es el punto de conexión: se implementa una subclase y se indica su ruta en
`settings.FACTURACION_PROVEEDOR`. Mientras no exista, el sistema solo genera prefacturas.
"""
import re
import xml.etree.ElementTree as ET
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db import transaction
from django.utils.module_loading import import_string

from .models import EstatusVenta, Prefactura

TASA_IVA = Decimal("0.16")
CENTAVOS = Decimal("0.01")
RFC_VALIDO = re.compile(r"^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}$")
CP_VALIDO = re.compile(r"^\d{5}$")
AVISO = "PREFACTURA: documento informativo sin validez fiscal. No es un CFDI."


class PrefacturaInvalida(ValueError):
    """Faltan datos para preparar la prefactura."""


class TimbradoNoDisponible(Exception):
    """No hay un proveedor de timbrado configurado."""


class ProveedorTimbrado:
    """Contrato para conectar un PAC. Debe devolver el UUID fiscal y el XML timbrado."""

    def timbrar(self, prefactura):  # pragma: no cover - lo implementa quien contrate un PAC
        raise NotImplementedError


def obtener_proveedor():
    ruta = getattr(settings, "FACTURACION_PROVEEDOR", "")
    if not ruta:
        raise TimbradoNoDisponible("No hay un proveedor de timbrado (PAC) configurado.")
    return import_string(ruta)()


def timbrado_disponible():
    try:
        obtener_proveedor()
    except TimbradoNoDisponible:
        return False
    return True


def rfc_valido(rfc):
    return bool(RFC_VALIDO.match((rfc or "").strip().upper()))


def _dinero(valor):
    return Decimal(valor).quantize(CENTAVOS, ROUND_HALF_UP)


def _datos_emisor(negocio):
    faltan = []
    if not negocio:
        raise PrefacturaInvalida("La venta no está ligada a un negocio; no hay datos del emisor.")
    if not (negocio.nombre_fiscal or "").strip():
        faltan.append("razón social")
    if not rfc_valido(negocio.rfc):
        faltan.append("RFC válido")
    if negocio.regimen_fiscal_id is None:
        faltan.append("régimen fiscal")
    if not CP_VALIDO.match((negocio.codigo_postal or "").strip()):
        faltan.append("código postal de 5 dígitos")
    if faltan:
        raise PrefacturaInvalida(f"Completa los datos fiscales del negocio «{negocio.nombre}»: {', '.join(faltan)}.")
    return {
        "nombre": negocio.nombre_fiscal.strip(), "rfc": negocio.rfc.strip().upper(),
        "regimen": f"{negocio.regimen_fiscal.codigo} · {negocio.regimen_fiscal.descripcion or ''}".strip(" ·"),
        "regimen_codigo": str(negocio.regimen_fiscal.codigo), "codigo_postal": negocio.codigo_postal.strip(),
    }


def _datos_receptor(cliente):
    faltan = []
    if not (cliente.razon_social or "").strip():
        faltan.append("razón social")
    if not rfc_valido(cliente.rfc):
        faltan.append("RFC válido")
    if cliente.regimen_fiscal_id is None:
        faltan.append("régimen fiscal")
    if not CP_VALIDO.match((cliente.codigo_postal or "").strip()):
        faltan.append("código postal de 5 dígitos")
    if faltan:
        raise PrefacturaInvalida(f"Completa los datos fiscales del cliente «{cliente.nombre}»: {', '.join(faltan)}.")
    return {
        "nombre": cliente.razon_social.strip(), "rfc": cliente.rfc.strip().upper(),
        "regimen": f"{cliente.regimen_fiscal.codigo} · {cliente.regimen_fiscal.descripcion or ''}".strip(" ·"),
        "regimen_codigo": str(cliente.regimen_fiscal.codigo), "codigo_postal": cliente.codigo_postal.strip(),
        "uso_cfdi": cliente.uso_cfdi, "email": cliente.email,
    }


def generar_prefactura(venta, cliente, usuario):
    """Crea (una sola vez) la prefactura de una venta completada. Guarda una copia de los datos fiscales."""
    with transaction.atomic():
        venta = type(venta).objects.select_for_update().get(pk=venta.pk)
        if hasattr(venta, "prefactura"):
            return venta.prefactura
        if venta.estatus != EstatusVenta.COMPLETADA:
            raise PrefacturaInvalida("No se puede facturar una venta cancelada.")
        cliente = venta.cliente or cliente
        if cliente is None:
            raise PrefacturaInvalida("Elige el cliente al que se le va a facturar.")
        emisor, receptor = _datos_emisor(venta.negocio), _datos_receptor(cliente)

        conceptos = [
            {"sku": l.producto.sku, "descripcion": l.producto.nombre, "cantidad": l.cantidad,
             "unidad": l.producto.medida.nombre if l.producto.medida_id else "Pieza",
             "valor_unitario": str(l.precio_unitario), "importe": str(l.subtotal)}
            for l in venta.lineas.select_related("producto", "producto__medida")
        ]
        subtotal = _dinero(venta.total)
        iva = _dinero(subtotal * TASA_IVA)
        if venta.cliente_id is None:
            venta.cliente = cliente
            venta.save(update_fields=["cliente"])
        prefactura = Prefactura.objects.create(
            venta=venta, numero=f"TMP-{venta.folio}", creada_por=usuario,
            subtotal=subtotal, iva=iva, total=subtotal + iva,
            datos={"emisor": emisor, "receptor": receptor, "conceptos": conceptos,
                   "tasa_iva": str(TASA_IVA), "moneda": "MXN", "venta_folio": venta.folio},
        )
        prefactura.numero = f"PF-{prefactura.pk:06d}"
        prefactura.save(update_fields=["numero"])
    return prefactura


def construir_xml(prefactura):
    """XML con nombres de atributos del CFDI 4.0 para facilitar un futuro timbrado. No es válido ante el SAT."""
    d = prefactura.datos
    raiz = ET.Element("Prefactura", {"Aviso": AVISO, "Version": "1.0"})
    ET.SubElement(raiz, "Comprobante", {
        "Serie": "PF", "Folio": prefactura.numero.split("-")[-1],
        "Fecha": prefactura.creada.strftime("%Y-%m-%dT%H:%M:%S"), "Moneda": d["moneda"],
        "SubTotal": str(prefactura.subtotal), "Total": str(prefactura.total),
        "LugarExpedicion": d["emisor"]["codigo_postal"], "Referencia": d["venta_folio"],
    })
    ET.SubElement(raiz, "Emisor", {
        "Rfc": d["emisor"]["rfc"], "Nombre": d["emisor"]["nombre"], "RegimenFiscal": d["emisor"]["regimen_codigo"]})
    ET.SubElement(raiz, "Receptor", {
        "Rfc": d["receptor"]["rfc"], "Nombre": d["receptor"]["nombre"],
        "DomicilioFiscalReceptor": d["receptor"]["codigo_postal"],
        "RegimenFiscalReceptor": d["receptor"]["regimen_codigo"], "UsoCFDI": d["receptor"]["uso_cfdi"]})
    conceptos = ET.SubElement(raiz, "Conceptos")
    for c in d["conceptos"]:
        ET.SubElement(conceptos, "Concepto", {
            "NoIdentificacion": c["sku"], "Descripcion": c["descripcion"], "Cantidad": f"{c['cantidad']:g}",
            "Unidad": c["unidad"], "ValorUnitario": c["valor_unitario"], "Importe": c["importe"]})
    impuestos = ET.SubElement(raiz, "Impuestos", {"TotalImpuestosTrasladados": str(prefactura.iva)})
    ET.SubElement(impuestos, "Traslado", {
        "Impuesto": "002", "TipoFactor": "Tasa", "TasaOCuota": f"{Decimal(d['tasa_iva']):.6f}",
        "Base": str(prefactura.subtotal), "Importe": str(prefactura.iva)})
    ET.indent(raiz)
    return ET.tostring(raiz, encoding="utf-8", xml_declaration=True)
