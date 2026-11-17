"""Carga datos de ejemplo para probar el sistema: python manage.py seed_demo"""
import secrets

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.roles import ADMIN, ALMACEN, COMPRAS, CONSULTA, asignar_rol
from categorias.models import Categoria
from inventory import services
from inventory.models import Almacen, Inventario_Producto, Medidas_Inventario, Producto
from negocio.models import Negocio
from proveedores.models import ProductosProveedor, Proveedor, RegimenFiscal

USUARIOS = (("demo_admin", ADMIN), ("demo_almacen", ALMACEN), ("demo_compras", COMPRAS), ("demo_consulta", CONSULTA))

PRODUCTOS = (
    # sku, nombre, categoría, medida, precio, stock mínimo, cantidad inicial
    ("TOR-001", "Tornillo hexagonal 1/4", "Ferretería", "Caja", "85.00", 5, 40),
    ("CEM-001", "Cemento gris 50 kg", "Construcción", "Pieza", "245.00", 10, 60),
    ("PIN-001", "Pintura vinílica blanca", "Pinturas", "Litro", "72.50", 20, 15),
    ("ARE-001", "Arena fina", "Construcción", "Kilogramo", "3.20", 200, 900),
    ("GUA-001", "Guantes de carga", "Seguridad", "Paquete", "120.00", 4, 3),
)


class Command(BaseCommand):
    help = "Crea un negocio, almacenes, proveedores, productos y usuarios de ejemplo (idempotente)."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Permite ejecutarlo con DEBUG=False.")

    @transaction.atomic
    def handle(self, *args, **opciones):
        if not settings.DEBUG and not opciones["force"]:
            raise CommandError("Es un comando de pruebas: usa --force si de verdad lo quieres en este entorno.")

        User = get_user_model()
        contrasena = secrets.token_urlsafe(9)
        creados = []
        for nombre, rol in USUARIOS:
            usuario, nuevo = User.objects.get_or_create(username=nombre)
            if nuevo:
                usuario.set_password(contrasena)
                usuario.save()
                creados.append(nombre)
            asignar_rol(usuario, rol)
        autor = User.objects.get(username="demo_admin")

        regimen = RegimenFiscal.objects.filter(codigo=601).first() or RegimenFiscal.objects.first()
        if regimen is None:
            raise CommandError("No hay regímenes fiscales; corre primero 'python manage.py migrate'.")

        negocio, _ = Negocio.objects.get_or_create(
            rfc="DEM010101AA1",
            defaults=dict(nombre="Ferretería Demo", nombre_fiscal="Ferretería Demo SA de CV",
                          direccion="Av. Universidad 100, San Nicolás de los Garza, N.L.",
                          codigo_postal="66450", regimen_fiscal=regimen, usuario_creo=autor, usuario_modifico=autor),
        )
        principal, _ = Almacen.objects.get_or_create(
            nombre="Almacén central", negocio=negocio, defaults={"es_principal": True, "direccion": "Planta baja"})
        Almacen.objects.get_or_create(nombre="Bodega norte", negocio=negocio, defaults={"direccion": "Patio trasero"})

        proveedor, _ = Proveedor.objects.get_or_create(
            rfc="PRO010101AA1",
            defaults=dict(nombre="Distribuidora Demo", razon_social="Distribuidora Demo SA de CV",
                          direccion="Parque Industrial 5, Monterrey, N.L.", codigo_postal="64000",
                          regimen_fiscal=regimen, usuario_creo=autor, usuario_modifico=autor),
        )

        for sku, nombre, categoria, medida, precio, minimo, cantidad in PRODUCTOS:
            cat, _ = Categoria.objects.get_or_create(nombre=categoria)
            med = Medidas_Inventario.objects.filter(nombre=medida).first()
            producto, nuevo = Producto.objects.get_or_create(
                sku=sku,
                defaults=dict(nombre=nombre, categoria_id=cat, medida=med, precio=precio, stock_min=minimo,
                              creado_por=autor, modificado_por=autor),
            )
            ProductosProveedor.objects.get_or_create(proveedor=proveedor, producto=producto,
                                                     defaults={"precio": precio})
            if nuevo:
                inventario = Inventario_Producto.objects.create(
                    producto_id=producto, cantidad=cantidad, almacen=principal,
                    creado_por=autor, modificado_por=autor)
                services.asegurar_existencias(inventario)

        self.stdout.write(self.style.SUCCESS("Datos de ejemplo listos."))
        if creados:
            self.stdout.write(f"Usuarios creados: {', '.join(creados)}")
            self.stdout.write(f"Contraseña (solo se muestra ahora): {contrasena}")
        else:
            self.stdout.write("Los usuarios demo ya existían; no se cambió su contraseña.")
