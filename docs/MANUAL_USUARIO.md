# BM-Core — Manual de usuario

## 1. Acceso
1. Abre la dirección del sistema e ingresa con tu usuario y contraseña.
2. Marca **Recuérdame** si quieres que la sesión siga abierta al cerrar el navegador.
3. Por seguridad la sesión se cierra tras **15 minutos sin actividad**.

Si al entrar a una pantalla ves *"No tienes permiso para esta acción"*, tu usuario no tiene un rol con acceso. Pide a un administrador que te lo asigne.

## 2. Roles
| Rol | Qué puede hacer |
|---|---|
| **Administrador** | Todo: autorizar/rechazar órdenes, negocios, proveedores, inventario |
| **Almacenista** | Productos, categorías, entradas/salidas y recibir mercancía |
| **Compras** | Proveedores y crear órdenes de compra |
| **Consulta** | Solo ver pantallas y reportes |

Los botones que tu rol no puede usar no aparecen.

## 3. Inventario
- **Catálogo** (`Inventario`): tarjetas con existencia y unidad de cada producto.
- **Nuevo producto**: captura nombre, categoría, precio, unidad de medida, stock mínimo y, opcionalmente, código de barras, imagen y cantidad inicial con su almacén. Si dejas el SKU vacío, el sistema genera uno.
- **Editar / ajustar existencia**: cambia datos del producto o captura una *cantidad nueva*; el sistema registra la diferencia como entrada o salida. Si alguien más movió el inventario mientras editabas, te pedirá recargar.
- **Buscar por código**: escanea el código de barras o escribe el SKU.
- **Alertas**: productos en o por debajo de su stock mínimo, incluidos los que aún no tienen inventario.
- **Por almacén**: filtra las existencias por ubicación.

Las unidades que no permiten decimales (por ejemplo "Pieza") rechazan cantidades fraccionadas.

## 4. Entradas y salidas
`Inventario → Movimientos → Registrar movimiento`

1. Elige el producto, el tipo (**Entrada** o **Salida**), la cantidad y el **motivo** (Compra, Venta, Merma, Ajuste, Devolución, Consumo interno…).
2. Guarda. La existencia se actualiza al momento.
3. Una salida mayor a la existencia disponible se rechaza.

El **historial** muestra fecha, producto, tipo, cantidad, existencia anterior, motivo, origen (manual o número de orden de compra) y usuario. Se filtra por tipo y producto.

## 4 bis. Almacenes y traspasos
Cada producto tiene una existencia total que se reparte entre uno o más **almacenes**.

- **Almacenes** (`Inventario → Almacenes`): lista con negocio, productos y unidades de cada uno. Desde ahí puedes crear o editar almacenes (Almacenista y Administrador). Solo puede haber **un almacén principal por negocio**.
- **Existencias por almacén**: cuánto de cada producto hay en cada ubicación; se puede filtrar por almacén. Lo que no está asignado a ninguno aparece como *Sin asignar*.
- **Traspaso** (`Nuevo traspaso`): elige producto, almacén origen (o *Sin asignar*), destino y cantidad. El total del producto **no cambia**; solo se mueve de lugar. No puedes traspasar más de lo que hay en el origen ni al mismo almacén.
- En **entradas y salidas** puedes elegir el almacén; si lo dejas vacío se usa el predeterminado del producto. Una salida no puede exceder lo que hay en ese almacén, aunque el total del producto alcance.
- Al **recibir una compra** la mercancía entra al almacén predeterminado del producto.
- En el historial, los traspasos aparecen como *Origen → Destino*.

## 5. Categorías
`Categorías`: lista, alta y edición. No se repiten nombres (sin importar mayúsculas). Desactivar una categoría no borra sus productos.

## 6. Proveedores
- **Añadir proveedor**: nombre, razón social, RFC, régimen fiscal, dirección, código postal, archivos (carátula y opinión de cumplimiento) y uno o más contactos.
- **Asignar productos** (ícono ±): define qué productos surte y a qué precio. Solo esos productos pueden incluirse en sus órdenes.

## 7. Órdenes de compra
1. **Crear** (Compras/Administrador): elige proveedor y negocio, agrega productos del proveedor con cantidad. Los importes se recalculan en el servidor. La orden queda **Pendiente**.
2. **Autorizar o rechazar** (solo Administrador). *Quien solicitó la orden no puede autorizarla.*
3. **Recibir** (Almacenista/Administrador), solo órdenes **Autorizadas**: suma las cantidades al inventario y deja un movimiento de entrada ligado a la orden. Una orden completada no puede recibirse dos veces.

## 8. Negocios
Alta y edición de negocios/sucursales con sus contactos (solo Administrador). Desde la lista puedes consultar el inventario de cada negocio.

## 9. Reportes
`Reportes`: filtra por **tipo** (entradas/salidas), **proveedor** (movimientos de compras recibidas de ese proveedor), **producto** y **rango de fechas**.
- Se muestran el total de movimientos y los totales de entradas y salidas.
- **Exportar CSV** descarga el resultado completo y se abre en Excel.
- En pantalla se ven los 500 movimientos más recientes; el CSV trae todos.

## 10. Tema claro / oscuro
El ícono de medio círculo en el menú lateral alterna el tema; se guarda en tu perfil.
