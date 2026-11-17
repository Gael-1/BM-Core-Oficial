# BM-Core — Manual técnico

## 1. Stack
Python 3.13, Django 5.2, templates de Django con Bootstrap 5, HTMX y crispy-forms. Base de datos: PostgreSQL en producción (vía `DATABASE_URL`) o SQLite en desarrollo. Servidor: gunicorn + WhiteNoise.

## 2. Estructura
| App | Responsabilidad |
|---|---|
| `core` | Configuración, URLs raíz, middleware de login obligatorio |
| `accounts` | Login, tema, **roles** (`roles.py`), procesadores de contexto |
| `inventory` | Productos, existencias, almacenes, movimientos, motivos |
| `categorias` | Categorías de producto |
| `proveedores` | Proveedores, contactos, régimen fiscal, productos por proveedor |
| `negocio` | Negocios/sucursales e inventario por negocio |
| `compra` | Órdenes de compra y su flujo de estados |
| `reportes` | Consulta y exportación de movimientos |
| `home`, `navigation` | Tablero y menú lateral dinámico (modelo `Menu`) |

## 3. Modelo de datos (resumen)
- `Producto` 1—1 `Inventario_Producto` (existencia actual, almacén). `Registro_Inventario` es la bitácora: tipo (`ENTRADA`/`SALIDA`/`TRASPASO`), cantidad, cantidad anterior, motivo, orden de compra opcional, usuario.
- `OrdenDeCompra` 1—N `ProductoEnOrden`; estatus: `pendiente → autorizada → completada` (o `rechazada`).
- `Proveedor` 1—N `ContactoProveedor`, `ProductosProveedor`. `Negocio` 1—N `ContactoNegocio`, `Negocio_Inventario`.
- Registros históricos pueden traer `ALTA`/`BAJA` como tipo; los reportes e historial los tratan como entrada/salida.

## 4. Seguridad
- `LoginRequiredMiddleware` exige sesión en todas las vistas salvo login/logout.
- **Roles** = grupos de Django (`Administrador`, `Almacenista`, `Compras`, `Consulta`), creados por la señal `post_migrate`. Los decoradores de `accounts/roles.py` se aplican en cada `urls.py`; sin rol → `403` (`templates/403.html`). El superusuario siempre pasa.
- Separación de funciones: quien solicitó una orden no puede autorizarla (`compra.views._cambiar_estado`).
- `accounts.context_processors.permisos_context` entrega `puede_inventario`, `puede_compras` y `puede_admin` a las plantillas solo para ocultar botones; **la validación real está en el servidor**.
- Con `DEBUG=False` el sistema no arranca sin `SECRET_KEY`. `ALLOWED_HOSTS` por defecto es solo localhost.
- El CSV de reportes neutraliza texto que Excel interpretaría como fórmula.

## 5. Integridad de inventario
Las operaciones que modifican existencias (`edit`, `registrar_movimiento`, `completar_orden`) usan `transaction.atomic()` y `select_for_update()` sobre el producto para evitar condiciones de carrera. La recepción de una orden es atómica: si una línea falla, no se aplica ninguna.

## 6. Configuración (variables de entorno)
Ver `.env.example`: `DEBUG`, `SECRET_KEY`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `DATABASE_URL`, `DATABASE_SSL`, `USE_HTTPS`, `SERVE_MEDIA`, `POSTGRES_PASSWORD` (compose).

## 7. Migraciones relevantes
- `inventory/0024` agrega `Registro_Inventario.motivo`; `0025` carga motivos iniciales.
- `navigation/0002` agrega accesos al menú dinámico si existe un menú "Inventario".

## 8. Pruebas
```bash
python manage.py test
```
Cubren compras (incluida concurrencia), inventario, movimientos, reportes, categorías y roles/interfaz. La concurrencia real requiere PostgreSQL; en SQLite esas pruebas se omiten.

## 9. Despliegue
**Docker Compose** (servidor propio o VM):
```bash
cp .env.example .env     # DEBUG=False, SECRET_KEY, POSTGRES_PASSWORD, ALLOWED_HOSTS...
docker compose up -d --build
docker compose exec web python manage.py createsuperuser
```
El contenedor corre `migrate` y `collectstatic` al iniciar. Los archivos subidos viven en el volumen `media`.

**Sin Docker** (DigitalOcean App Platform / Droplet):
```bash
pip install -r requirements.txt
python manage.py migrate && python manage.py collectstatic --noinput
gunicorn core.wsgi:application --bind 0.0.0.0:8000
```
Detrás de Nginx con HTTPS define `USE_HTTPS=True` y `CSRF_TRUSTED_ORIGINS=https://tu-dominio`. Para `/media/`: Nginx, almacenamiento externo o `SERVE_MEDIA=True`.

## 10. Asignar roles
En `/admin/` → Usuarios → editar usuario → **Grupos**. Un usuario sin grupo no puede usar ningún módulo.

## 11. Pendientes conocidos
- Traspasos entre almacenes: hay una sola existencia por producto; requiere rediseño.
- `Negocio_Inventario` duplica cantidades que ya existen en `Inventario_Producto`.
- La presentación del proyecto menciona React; la implementación usa templates de Django + HTMX.
