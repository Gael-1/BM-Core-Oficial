# BM-Core ![python](https://img.shields.io/badge/python-v3.13.3-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54) ![Static Badge](https://img.shields.io/badge/django-v5.2.5-3670A0?style=for-the-badge&logo=django&logoColor=%23ffffff&labelColor=%230C4B33&color=%23181D27)

Sistema web de gestión de inventarios y proveedores (Proyecto Integrador 2, Equipo 10, FIME).

## Módulos

| Módulo | Qué hace |
|---|---|
| `inventory` | Productos, existencias, alertas de stock mínimo, búsqueda por código, **entradas/salidas manuales con motivo**, **historial de movimientos**, **almacenes y traspasos** con existencias por ubicación |
| `categorias` | Alta y edición de categorías de producto |
| `proveedores` | Proveedores, contactos y productos que surte cada uno |
| `compra` | Órdenes de compra: crear → autorizar/rechazar → recibir (actualiza existencias) |
| `negocio` | Negocios / sucursales y su inventario |
| `reportes` | Reportes por tipo, proveedor, producto y fechas, con **exportación a CSV** |
| `accounts`, `home`, `navigation` | Login, tablero y menú lateral |

## Roles y permisos

Los roles son grupos de Django y se crean solos al correr `migrate`. Se asignan en `/admin/` (Usuarios → Grupos). Un superusuario puede todo; un usuario **sin rol no puede entrar a ningún módulo**.

| Acción | Administrador | Almacenista | Compras | Consulta |
|---|:--:|:--:|:--:|:--:|
| Ver inventario, proveedores, negocios, compras y reportes | ✔ | ✔ | ✔ | ✔ |
| Productos, categorías, entradas/salidas | ✔ | ✔ | | |
| Recibir mercancía de una orden | ✔ | ✔ | | |
| Proveedores y crear órdenes de compra | ✔ | | ✔ | |
| Autorizar / rechazar órdenes, alta y edición de negocios | ✔ | | | |

Quien solicitó una orden no puede autorizarla (salvo un superusuario).

## Puesta en marcha (desarrollo)

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # opcional en desarrollo
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Sin `DATABASE_URL` se usa SQLite (`db.sqlite3`). Los menús del sidebar se pueden editar desde `/admin/` (modelo *Menú*).

## Pruebas

```bash
python manage.py test
```

## Producción (DigitalOcean)

1. Define en el entorno: `DEBUG=False`, `SECRET_KEY`, `ALLOWED_HOSTS`, `DATABASE_URL` (PostgreSQL), `CSRF_TRUSTED_ORIGINS` y, si hay HTTPS, `USE_HTTPS=True`. Con `DEBUG=False` el sistema se niega a arrancar sin `SECRET_KEY`.
2. `pip install -r requirements.txt`
3. `python manage.py migrate && python manage.py collectstatic --noinput`
4. Arranque: `gunicorn core.wsgi:application --bind 0.0.0.0:8000` detrás de Nginx. Los archivos estáticos los sirve WhiteNoise; los archivos subidos (`/media/`) los sirve Nginx, un almacenamiento externo o `SERVE_MEDIA=True`.

## Documentación

- [Manual de usuario](docs/MANUAL_USUARIO.md)
- [Manual técnico](docs/MANUAL_TECNICO.md)

Despliegue rápido con Docker: `cp .env.example .env` → `docker compose up -d --build`.

## Pendiente / ideas futuras

- Unificar `Negocio_Inventario` con el desglose por almacén (hoy son dos fuentes de existencia).
