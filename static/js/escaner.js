/* Escaneo con la cámara (código de barras y QR) usando la API nativa BarcodeDetector.
   Uso: <button type="button" data-escaner="#id-del-input" [data-escaner-envia]>.
   Si el navegador no la soporta, el botón se oculta y sigue funcionando el lector USB o el teclado. */
(function () {
  "use strict";
  var botones = document.querySelectorAll("[data-escaner]");
  if (!botones.length) return;
  if (!("BarcodeDetector" in window) || !navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    botones.forEach(function (b) { b.hidden = true; });
    return;
  }
  var formatos = ["qr_code", "ean_13", "ean_8", "upc_a", "upc_e", "code_128", "code_39", "itf"];
  botones.forEach(function (boton) {
    boton.addEventListener("click", function () { abrir(boton); });
  });

  function abrir(boton) {
    var entrada = document.querySelector(boton.dataset.escaner);
    if (!entrada) return;
    var capa = document.createElement("div");
    capa.className = "position-fixed top-0 start-0 w-100 h-100 d-flex flex-column align-items-center justify-content-center bg-dark bg-opacity-75";
    capa.style.zIndex = 2000;
    capa.setAttribute("role", "dialog");
    capa.setAttribute("aria-label", "Escáner de códigos");
    capa.innerHTML = '<video playsinline muted style="max-width:92vw;max-height:70vh;border-radius:8px"></video>' +
      '<p class="text-white mt-2 mb-2" role="status">Apunta la cámara al código…</p>' +
      '<button type="button" class="btn btn-light">Cancelar</button>';
    document.body.appendChild(capa);
    var video = capa.querySelector("video");
    var aviso = capa.querySelector("p");
    var flujo = null, activo = true;
    var detector = new BarcodeDetector({formats: formatos});

    function cerrar() {
      activo = false;
      if (flujo) flujo.getTracks().forEach(function (t) { t.stop(); });
      capa.remove();
    }
    capa.querySelector("button").addEventListener("click", cerrar);
    document.addEventListener("keydown", function esc(e) {
      if (e.key === "Escape") { cerrar(); document.removeEventListener("keydown", esc); }
    });

    navigator.mediaDevices.getUserMedia({video: {facingMode: "environment"}}).then(function (s) {
      flujo = s; video.srcObject = s; return video.play();
    }).then(function leer() {
      if (!activo) return;
      detector.detect(video).then(function (codigos) {
        if (codigos.length) {
          entrada.value = codigos[0].rawValue;
          cerrar();
          entrada.dispatchEvent(new KeyboardEvent("keydown", {key: "Enter", bubbles: true, cancelable: true}));
          if (boton.hasAttribute("data-escaner-envia") && entrada.form) entrada.form.requestSubmit();
        } else { requestAnimationFrame(leer); }
      }).catch(function () { requestAnimationFrame(leer); });
    }).catch(function () {
      aviso.textContent = "No se pudo acceder a la cámara. Revisa el permiso del navegador (requiere HTTPS).";
    });
  }
})();
