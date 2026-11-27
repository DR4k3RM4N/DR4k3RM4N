// 🏠 Cuartos propios (vista desde arriba), dibujados desde cero para cada oficina que vive en su página:
//   🎬 la sala de edición (cuarto de control: cada compu y el servidor con su monitor mostrando qué edita) y
//   🛒 TikTok Shop (estudio claro con los escritorios del equipo y el set de grabación).
// Ligero: lo fijo se pinta una vez; cada cuadro solo lo que se mueve (10 cuadros/s) y se detiene si no se ve.
// Uso: Cuarto.montar(contenedor, { tema, plano(datos) → {estaciones, adornos}, cargar: async () => datos, cada })
(() => {
  const quieto = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const PELO = { gorra: "#1f2937", copete: "#3a2216", chongo: "#1d120c", bob: "#2a1a12", corto: "#2b1d14", largo: "#4a2c19",
                 rizos: "#20140d", coleta: "#3b2314", audifonos: "#1b1b1b" };
  const TEMAS = {
    edicion: { piso: ["#151a23", "#131820"], linea: "rgba(110,140,255,.07)", pared: "#0c0f15", borde: "#2a3550", texto: "#e8edf3",
               suave: "#8b97a6", acento: "#4da3ff", escritorio: "#1f2633", canto: "#2c3648", monitor: "#05070b", neon: "#8b5cf6",
               letrero: "SALA DE EDICIÓN" },
    tiktok: { piso: ["#eef0f4", "#e6e9ef"], linea: "rgba(40,50,70,.06)", pared: "#ffffff", borde: "#d5d9e2", texto: "#1b1f2a",
              suave: "#5b6474", acento: "#fe2c55", escritorio: "#f7f2ea", canto: "#d9cdb9", monitor: "#111318", neon: "#25f4ee",
              letrero: "TIKTOK SHOP" },
  };

  function montar(caja, opciones) {
    const tema = TEMAS[opciones.tema];
    const cv = document.createElement("canvas");
    cv.className = "cuarto-lienzo";
    cv.setAttribute("role", "img");
    cv.setAttribute("aria-label", opciones.descripcion || "El cuarto de la oficina");
    caja.appendChild(cv);
    const g = cv.getContext("2d");
    const base = document.createElement("canvas"), gb = base.getContext("2d");
    let W = 1000, H = 560, escala = 1, dpr = 1, datos = null, plano = { estaciones: [], adornos: [] }, t = 0, baseLista = false;

    const rr = (c, x, y, w, h, r) => { c.beginPath(); c.roundRect ? c.roundRect(x, y, w, h, r) : c.rect(x, y, w, h); };
    const caja2 = (c, x, y, w, h, col, r = 4) => { rr(c, x, y, w, h, r); c.fillStyle = col; c.fill(); };
    const texto = (c, s, x, y, { tam = 12, col = tema.texto, peso = 600, alin = "center", max } = {}) => {
      c.font = `${peso} ${tam}px Inter, system-ui, sans-serif`; c.fillStyle = col; c.textAlign = alin; c.textBaseline = "middle";
      let v = String(s ?? "");
      if (max) while (v.length > 3 && c.measureText(v).width > max) v = v.slice(0, -2).trimEnd() + "…";
      c.fillText(v, x, y);
    };

    // ---------- lo que no se mueve ----------
    function pintarBase() {
      base.width = W * escala * dpr; base.height = H * escala * dpr;
      gb.setTransform(escala * dpr, 0, 0, escala * dpr, 0, 0);
      const c = gb;
      for (let y = 0; y < H; y += 40) for (let x = 0; x < W; x += 40) { c.fillStyle = tema.piso[((x + y) / 40) % 2]; c.fillRect(x, y, 40, 40); }
      c.strokeStyle = tema.linea; c.lineWidth = 1;
      for (let x = 0; x <= W; x += 40) { c.beginPath(); c.moveTo(x, 0); c.lineTo(x, H); c.stroke(); }
      for (let y = 0; y <= H; y += 40) { c.beginPath(); c.moveTo(0, y); c.lineTo(W, y); c.stroke(); }
      // muros (vista de arriba) con la puerta abajo
      c.fillStyle = tema.pared; c.fillRect(0, 0, W, 26); c.fillRect(0, 0, 14, H); c.fillRect(W - 14, 0, 14, H);
      c.fillRect(0, H - 14, W / 2 - 60, 14); c.fillRect(W / 2 + 60, H - 14, W / 2 - 60, 14);
      c.strokeStyle = tema.borde; c.lineWidth = 2; c.strokeRect(1, 1, W - 2, H - 2);
      // letrero de neón en el muro del fondo
      c.save(); c.shadowColor = tema.neon; c.shadowBlur = 14;
      texto(c, tema.letrero, W / 2, 13, { tam: 15, col: tema.neon, peso: 800 }); c.restore();
      for (const a of plano.adornos) adorno(c, a);
      for (const e of plano.estaciones) mueble(c, e);
      baseLista = true;
    }
    function adorno(c, [tipo, x, y, extra]) {
      if (tipo === "planta") {
        caja2(c, x - 12, y - 12, 24, 24, "#7c5a3c", 6);
        for (let i = 0; i < 6; i++) { c.fillStyle = i % 2 ? "#2f9e44" : "#40c057"; c.beginPath(); c.ellipse(x + Math.cos(i) * 8, y + Math.sin(i) * 8, 9, 6, i, 0, 7); c.fill(); }
      } else if (tipo === "rack") { // el servidor: gabinete con luces
        caja2(c, x, y, 70, 120, "#0a0c12", 6); c.strokeStyle = "#2a3550"; c.lineWidth = 2; rr(c, x, y, 70, 120, 6); c.stroke();
        for (let i = 0; i < 6; i++) caja2(c, x + 8, y + 10 + i * 18, 54, 12, "#151b27", 2);
        texto(c, "SERVIDOR", x + 35, y + 132, { tam: 11, col: tema.suave, peso: 700 });
      } else if (tipo === "aro") { // aro de luz y tripié del set de grabación
        c.strokeStyle = "#f8f9fa"; c.lineWidth = 7; c.beginPath(); c.arc(x, y, 26, 0, 7); c.stroke();
        c.strokeStyle = "#ced4da"; c.lineWidth = 2; c.beginPath(); c.arc(x, y, 26, 0, 7); c.stroke();
        c.strokeStyle = "#495057"; c.lineWidth = 3;
        for (const a of [0.6, 2.5, 4.4]) { c.beginPath(); c.moveTo(x, y); c.lineTo(x + Math.cos(a) * 34, y + Math.sin(a) * 34); c.stroke(); }
        caja2(c, x - 8, y - 6, 16, 12, "#212529", 3);
      } else if (tipo === "mesa") { // mesa del producto con cajas
        caja2(c, x, y, 150, 70, "#ffffff", 8); c.strokeStyle = tema.borde; c.lineWidth = 2; rr(c, x, y, 150, 70, 8); c.stroke();
        const cols = ["#fe2c55", "#25f4ee", "#ffd43b", "#845ef7"];
        for (let i = 0; i < 4; i++) caja2(c, x + 14 + i * 33, y + 18 + (i % 2) * 10, 26, 26, cols[i], 4);
        texto(c, extra || "Set de grabación", x + 75, y + 84, { tam: 11, col: tema.suave });
      } else if (tipo === "repisa") {
        caja2(c, x, y, 220, 22, "#d9cdb9", 4);
        const cols = ["#ff6b6b", "#4dabf7", "#ffd43b", "#69db7c", "#da77f2", "#ffa94d"];
        for (let i = 0; i < 6; i++) caja2(c, x + 8 + i * 35, y + 3, 26, 16, cols[i], 3);
      } else if (tipo === "sillon") {
        caja2(c, x, y, 110, 46, extra || "#495057", 12); caja2(c, x + 8, y + 8, 94, 30, "rgba(255,255,255,.12)", 8);
      } else if (tipo === "cables") {
        c.strokeStyle = "rgba(77,163,255,.18)"; c.lineWidth = 3; c.setLineDash([6, 6]);
        for (const [a, b] of extra) { c.beginPath(); c.moveTo(a[0], a[1]); c.bezierCurveTo(a[0], (a[1] + b[1]) / 2, b[0], (a[1] + b[1]) / 2, b[0], b[1]); c.stroke(); }
        c.setLineDash([]);
      }
    }
    function mueble(c, e) {
      // escritorio con monitor grande (la pantalla se pinta en vivo) y silla
      caja2(c, e.x - 70, e.y - 34, 140, 52, tema.escritorio, 8);
      c.strokeStyle = tema.canto; c.lineWidth = 2; rr(c, e.x - 70, e.y - 34, 140, 52, 8); c.stroke();
      caja2(c, e.x - 58, e.y - 30, 116, 34, "#2b2f38", 4); // marco del monitor
      caja2(c, e.x - 14, e.y + 4, 28, 6, "#3b404c", 2); // base
      caja2(c, e.x - 30, e.y + 10, 60, 6, tema.opcion === "claro" ? "#ced4da" : "#2c3344", 3); // teclado
    }

    // ---------- lo que se mueve ----------
    function persona(c, x, y, p, tecleo) {
      caja2(c, x - 16, y - 2, 32, 24, opciones.tema === "tiktok" ? "#adb5bd" : "#0d1017", 10); // silla
      c.fillStyle = p.color || "#888"; c.beginPath(); c.ellipse(x, y + 5, 15, 10, 0, 0, 7); c.fill(); // hombros
      const mano = tecleo && !quieto ? Math.sin(t * 18) * 2 : 0;
      c.fillStyle = "#d6a27a"; c.beginPath(); c.arc(x - 10, y - 6 + mano, 3, 0, 7); c.arc(x + 10, y - 6 - mano, 3, 0, 7); c.fill();
      c.beginPath(); c.arc(x, y + 1, 8, 0, 7); c.fill();
      c.fillStyle = PELO[p.pelo] || "#2b1d14"; c.beginPath(); c.arc(x, y + 2, 8.2, 0, 7); c.fill();
      if (p.pelo === "audifonos" || p.audifonos) { c.strokeStyle = "#111"; c.lineWidth = 3; c.beginPath(); c.arc(x, y + 2, 10, Math.PI * 1.1, Math.PI * 1.9); c.stroke(); }
    }
    function pantalla(c, e, s) {
      const x = e.x - 55, y = e.y - 27, w = 110, h = 28;
      const encendida = s && s.encendida !== false;
      caja2(c, x, y, w, h, encendida ? (s.fondo || "#0b1220") : tema.monitor, 2);
      if (!encendida) return;
      if (s.titulo) texto(c, s.titulo, x + w / 2, y + 8, { tam: 8.5, col: "#e9eef5", peso: 700, max: w - 8 });
      if (s.avance != null) {
        caja2(c, x + 6, y + 15, w - 12, 5, "rgba(255,255,255,.15)", 2);
        caja2(c, x + 6, y + 15, Math.max(3, (w - 12) * Math.min(1, s.avance)), 5, s.color || tema.acento, 2);
        texto(c, `${Math.round(s.avance * 100)} %`, x + w / 2, y + 24, { tam: 7, col: "#b8c2d0", peso: 700 });
      } else if (s.linea) {
        texto(c, s.linea, x + w / 2, y + 20, { tam: 7.5, col: "#9fb0c4", peso: 500, max: w - 8 });
      }
    }
    function medidor(c, x, y, etiqueta, v) {
      texto(c, etiqueta, x, y, { tam: 8, col: tema.suave, alin: "left", peso: 700 });
      caja2(c, x + 22, y - 3, 40, 6, opciones.tema === "tiktok" ? "#dee2e6" : "#1a2130", 3);
      if (v != null) caja2(c, x + 22, y - 3, 40 * Math.min(1, v / 100), 6, v >= 85 ? "#ffb020" : tema.acento, 3);
    }
    function globo(c, x, y, s) {
      c.font = "600 11px Inter, system-ui, sans-serif";
      let v = s; while (v.length > 3 && c.measureText(v).width > 200) v = v.slice(0, -2).trimEnd() + "…";
      const w = c.measureText(v).width + 16;
      caja2(c, x - w / 2, y - 26, w, 22, "#ffffff", 8);
      c.fillStyle = "#ffffff"; c.beginPath(); c.moveTo(x - 5, y - 5); c.lineTo(x + 5, y - 5); c.lineTo(x, y + 1); c.fill();
      texto(c, v, x, y - 15, { tam: 11, col: "#111", peso: 600 });
    }
    function cuadro() {
      if (!baseLista) pintarBase();
      g.setTransform(1, 0, 0, 1, 0, 0);
      g.clearRect(0, 0, cv.width, cv.height);
      g.drawImage(base, 0, 0);
      g.setTransform(escala * dpr, 0, 0, escala * dpr, 0, 0);
      const ahora = Date.now() / 1000;
      for (const e of plano.estaciones) {
        pantalla(g, e, e.pantalla);
        if (e.luz) { // brillo del monitor encendido en el escritorio
          const gr = g.createRadialGradient(e.x, e.y - 10, 4, e.x, e.y - 10, 90);
          gr.addColorStop(0, e.luz); gr.addColorStop(1, "rgba(0,0,0,0)");
          g.fillStyle = gr; g.fillRect(e.x - 90, e.y - 100, 180, 180);
        }
        if (e.persona) persona(g, e.x, e.y + 40, e.persona, e.trabajando);
        else caja2(g, e.x - 16, e.y + 38, 32, 24, opciones.tema === "tiktok" ? "#ced4da" : "#0d1017", 10);
        // nombre y estado debajo
        caja2(g, e.x - 68, e.y + 70, 136, 18, opciones.tema === "tiktok" ? "rgba(255,255,255,.92)" : "rgba(5,8,12,.75)", 9);
        g.fillStyle = e.viva === false ? "#6b7280" : e.trabajando ? "#3ddc84" : "#ffb020";
        g.beginPath(); g.arc(e.x - 58, e.y + 79, 4, 0, 7); g.fill();
        texto(g, e.nombre, e.x + 4, e.y + 79, { tam: 10.5, peso: 700, max: 112, col: opciones.tema === "tiktok" ? "#1b1f2a" : "#e8edf3" });
        if (e.sub) texto(g, e.sub, e.x, e.y + 97, { tam: 9, col: tema.suave, max: 150 });
        if (e.medidores) { medidor(g, e.x - 62, e.y + 112, "CPU", e.medidores.cpu); medidor(g, e.x + 4, e.y + 112, "GPU", e.medidores.gpu); }
        if (e.dice && ahora - (e.dice_t || 0) < 9) globo(g, e.x, e.y - 40, e.dice);
      }
      if (plano.encima) plano.encima(g, t, { texto, caja2 });
    }

    // ---------- tamaño, datos y animación ----------
    function ajustar() {
      const ancho = Math.max(280, caja.clientWidth);
      escala = ancho / W; dpr = Math.min(2, window.devicePixelRatio || 1);
      cv.width = Math.round(W * escala * dpr); cv.height = Math.round(H * escala * dpr);
      cv.style.width = `${Math.round(W * escala)}px`; cv.style.height = `${Math.round(H * escala)}px`;
      baseLista = false;
    }
    async function refrescar() {
      try {
        datos = await opciones.cargar();
        const nuevo = opciones.plano(datos);
        const firma = JSON.stringify(nuevo.estaciones.map((e) => [e.id, e.x, e.y])) + nuevo.adornos.length;
        if (firma !== plano._firma) { baseLista = false; nuevo._firma = firma; } else nuevo._firma = plano._firma;
        if (nuevo.alto && nuevo.alto !== H) { H = nuevo.alto; ajustar(); }
        plano = nuevo;
      } catch { /* sin datos: se queda lo último */ }
    }
    let ultimo = 0, visible = true;
    function anima(ms) {
      requestAnimationFrame(anima);
      if (!visible || document.hidden || ms - ultimo < 100) return;
      t += (ms - ultimo) / 1000 || 0.1; ultimo = ms;
      cuadro();
    }
    if ("IntersectionObserver" in window) new IntersectionObserver((es) => { visible = es.some((e) => e.isIntersecting); }).observe(cv);
    window.addEventListener("resize", ajustar);
    ajustar();
    refrescar().then(() => { cuadro(); requestAnimationFrame(anima); });
    setInterval(() => { if (!document.hidden) refrescar(); }, opciones.cada || 3000);
  }

  window.Cuarto = { montar };
})();
