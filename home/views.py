from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import F, Q
from django.views.generic import TemplateView

from inventory.models import Producto, Almacen, Registro_Inventario
from proveedores.models import Proveedor


class HomeView(LoginRequiredMixin, TemplateView):
    template_name = "index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        productos = Producto.objects.filter(activo=True)

        productos_bajo_stock = productos.filter(
            Q(inventario__cantidad__lte=F("stock_min")) | Q(inventario__isnull=True)
        )

        movimientos = (
            Registro_Inventario.objects
            .select_related("inventario_producto_id__producto_id")
            .order_by("-creado")[:8]
        )

        context.update({
            "total_productos": productos.count(),
            "total_proveedores": Proveedor.objects.filter(activo=True).count(),
            "total_almacenes": Almacen.objects.count(),
            "total_alertas": productos_bajo_stock.count(),

            "productos_bajo_stock": productos_bajo_stock[:5],

            "ultimos_movimientos": movimientos,
        })

        return context