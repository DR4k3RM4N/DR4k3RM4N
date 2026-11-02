// PulsoLive — portada: aparición escalonada, apertura de la curva, la curva "en vivo" y el tablero de momentos.
(function () {
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // Curva de pedidos por minuto de un live de ejemplo: base baja, picos después de la oferta (min 20) y de la escasez (min 51).
  var curve = document.getElementById("curve");
  if (curve) {
    var N = 64, vals = [];
    for (var m = 0; m < N; m++) {
      var base = 0.9 + 0.35 * Math.sin(m / 4) + (m % 7 === 3 ? 0.4 : 0);
      if (m >= 20 && m < 25) base += 2.2 - (m - 20) * 0.35;
      if (m >= 51 && m < 56) base += 1.7 - (m - 51) * 0.3;
      if (m >= 40 && m < 44) base -= 0.5;
      vals.push(Math.max(0.15, base));
    }
    var max = Math.max.apply(null, vals);
    var bars = vals.map(function (v, i) {
      var b = document.createElement("i");
      b.style.height = (v / max * 100).toFixed(1) + "%";
      if (!((i >= 20 && i < 25) || (i >= 51 && i < 56))) b.className = "dim";
      curve.appendChild(b);
      return b;
    });
    [[20, "Oferta relámpago"], [51, "Quedan pocas piezas"]].forEach(function (p) {
      var mk = document.createElement("span");
      mk.className = p[0] > N * 0.6 ? "mark end" : "mark";
      mk.style.left = (p[0] / N * 100) + "%";
      mk.textContent = "min " + p[0] + " · " + p[1];
      curve.appendChild(mk);
    });
    // El live sigue: cada segundo y medio "llega" un minuto nuevo al final de la curva.
    if (!reduce) {
      var k = 0;
      setInterval(function () {
        if (document.hidden) return;
        var b = bars[N - 1 - (k % 6)];
        b.classList.remove("grow"); void b.offsetWidth; b.classList.add("grow");
        k++;
      }, 1500);
    }
  }

  // Aparición de las partes de cada sección, escalonada 70 ms.
  // La curva está en la primera pantalla y empieza recortada (un observador no la vería): se abre al cargar.
  var shutters = [].slice.call(document.querySelectorAll(".shutter"));
  requestAnimationFrame(function () { setTimeout(function () { shutters.forEach(function (el) { el.classList.add("is-in"); }); }, 150); });

  var items = [].slice.call(document.querySelectorAll(".reveal"));
  var groups = new Map();
  items.forEach(function (el) {
    var host = el.closest("section, header") || document.body;
    var n = groups.get(host) || 0;
    el.style.setProperty("--d", Math.min(n, 6) * 70 + "ms");
    groups.set(host, n + 1);
  });
  if ("IntersectionObserver" in window && !reduce) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add("is-in"); io.unobserve(e.target); } });
    }, { rootMargin: "0px 0px -8% 0px", threshold: 0.05 });
    items.forEach(function (el) { io.observe(el); });
  } else {
    items.forEach(function (el) { el.classList.add("is-in"); });
  }

  // Tablero de momentos: abrir uno cierra el anterior.
  var board = document.getElementById("dboard");
  if (board) {
    board.addEventListener("click", function (ev) {
      var row = ev.target.closest(".drow");
      if (!row || row.classList.contains("open")) return;
      board.querySelectorAll(".drow.open").forEach(function (r) { r.classList.remove("open"); r.setAttribute("aria-expanded", "false"); });
      row.classList.add("open");
      row.setAttribute("aria-expanded", "true");
    });
  }
})();
