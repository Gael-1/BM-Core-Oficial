(function () {
  function iniciar() {
    const form = document.getElementById("orden-compra-form");
    if (!form || form.dataset.initialized) return;
    form.dataset.initialized = "true";
    const proveedor = form.querySelector("#id_proveedor");
    const body = form.querySelector("#productos-body");
    const add = form.querySelector("#addProductoBtn");
    const template = form.querySelector("#producto-template");
    const inputJson = form.querySelector("#productos-json");
    let disponibles = [];
    let solicitud = 0;
    function totalizar() {
      let total = 0;
      body.querySelectorAll("tr").forEach(row => {
        const cantidad = Number(row.querySelector(".cantidad").value);
        const precio = Number(row.querySelector(".precio").value);
        const importe = Number.isFinite(cantidad * precio) ? cantidad * precio : 0;
        row.querySelector(".subtotal").value = importe.toFixed(2);
        total += importe;
      });
      form.querySelector("#id_subtotal").value = total.toFixed(2);
      form.querySelector("#id_total").value = total.toFixed(2);
    }
    function fila(item = {}) {
      const row = template.content.cloneNode(true).querySelector("tr");
      const select = row.querySelector(".producto-select");
      disponibles.forEach(p => {
        const option = document.createElement("option");
        option.value = p.id; option.textContent = p.nombre; option.dataset.precio = p.precio;
        select.appendChild(option);
      });
      select.value = item.producto_id || "";
      const cantidad = row.querySelector(".cantidad");
      cantidad.value = item.cantidad ?? 1;
      cantidad.required = true; select.required = true;
      function precio() { row.querySelector(".precio").value = select.selectedOptions[0]?.dataset.precio || "0"; totalizar(); }
      select.addEventListener("change", precio);
      cantidad.addEventListener("input", totalizar);
      row.querySelector(".eliminar").addEventListener("click", () => { row.remove(); totalizar(); });
      body.appendChild(row); precio();
    }
    async function cargar(iniciales = []) {
      const numero = ++solicitud;
      body.innerHTML = ""; disponibles = []; add.disabled = true; totalizar();
      if (!proveedor.value) return;
      try {
        const response = await fetch(`${findProductosUrl}?proveedor=${encodeURIComponent(proveedor.value)}`);
        if (!response.ok) throw new Error("No se pudieron cargar los productos del proveedor.");
        const datos = await response.json();
        if (numero !== solicitud) return;
        disponibles = datos; add.disabled = !disponibles.length;
        iniciales.forEach(item => fila(item));
      } catch (error) { if (numero === solicitud) alert(error.message); }
    }
    proveedor.addEventListener("change", () => cargar());
    add.addEventListener("click", () => fila());
    form.addEventListener("submit", event => {
      const productos = Array.from(body.querySelectorAll("tr"), row => ({
        producto_id: row.querySelector(".producto-select").value,
        cantidad: row.querySelector(".cantidad").value,
      }));
      if (!productos.length) { event.preventDefault(); alert("Agrega al menos un producto."); return; }
      inputJson.value = JSON.stringify(productos);
    });
    const iniciales = JSON.parse(document.getElementById("productos-iniciales").textContent);
    cargar(iniciales);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", iniciar);
  else iniciar();
})();
