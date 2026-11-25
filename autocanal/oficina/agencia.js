// 🕵️ La Agencia de Expedientes: plano de la agencia por cuartos (uno por área), en pixel art y con los colores del
// canal «¿Quién MATÓ a…?». Ligero: solo se anima cuando alguien trabaja, a pocos cuadros por segundo, y se detiene si
// la pestaña está escondida. El panel de la derecha es expedientes.js (importar, verificar, aprobar, chat).
(() => {
  const ESC = 4;
  let W = 320, H = 196;
  const cv = document.getElementById("ag-lienzo");
  const capas = document.getElementById("ag-capas");
  const ficha = document.getElementById("ag-ficha");
  if (!cv) return;
  const g = cv.getContext("2d");
  const R = (x, y, w, h, c) => { g.fillStyle = c; g.fillRect(Math.round(x), Math.round(y), w, h); };
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const AM = "#FFD60A", ROJO = "#E63946", VERDE = "#2DC653", BLANCO = "#F5F5F5";

  // ---------- los cuartos (uno por área) ----------
  // Compu: 4 columnas × 2 filas con el pasillo en medio. Cel: 2 columnas × 4 filas con dos pasillos.
  const CW = 78, CH = 84, PAS = 20;
  const BASE = [
    { id: "ex_ramos", nombre: "Interrogatorios", sub: "Verificación", piso: ["#2b2320", "#251e1b"], deco: verificacion },
    { id: "ex_archivista", nombre: "Archivo", sub: "Stock y archivo", piso: ["#22262a", "#1e2125"], deco: archivo },
    { id: "ex_graficas", nombre: "Laboratorio", sub: "Gráficas", piso: ["#1f2621", "#1b211d"], deco: graficas },
    { id: "ex_miniaturas", nombre: "Estudio", sub: "Miniaturas", piso: ["#2a2128", "#241c22"], deco: miniaturas },
    { id: "jefe", nombre: "Cabina", sub: "Tu voz", piso: ["#262321", "#201e1c"], deco: cabina },
    { id: "ex_editor", nombre: "Edición", sub: "El armado", piso: ["#1e2230", "#1a1d29"], deco: edicion },
    { id: "ex_subtitulos", nombre: "Subtítulos", sub: "y Shorts", piso: ["#2a2420", "#241f1b"], deco: subtitulos },
    { id: "ex_publicacion", nombre: "Publicación", sub: "YouTube en privado", piso: ["#2a1f20", "#241a1b"], deco: publicacion },
  ];
  let CUARTOS = [], PASILLOS = [], estrecho = null;
  function acomodar() {
    const angosto = (cv.parentElement?.clientWidth || innerWidth) < 560;
    if (angosto === estrecho) return false;
    estrecho = angosto;
    const cols = angosto ? 2 : 4, filas = 8 / cols;
    W = 4 + cols * CW + 4;
    // cada par de filas comparte un pasillo: fila de arriba (puerta abajo), pasillo, fila de abajo (puerta arriba)
    const ys = [];
    let y = 4;
    PASILLOS = [];
    for (let f = 0; f < filas; f++) {
      ys.push(y);
      y += CH;
      if (f % 2 === 0) { PASILLOS.push(y); y += PAS; }
    }
    H = y + 4;
    CUARTOS = BASE.map((c, i) => {
      const col = i % cols, fila = Math.floor(i / cols);
      return { ...c, x: 4 + col * CW, y: ys[fila], w: CW, h: CH, abajo: fila % 2 === 0 };
    });
    cv.width = W * ESC; cv.height = H * ESC;
    g.setTransform(ESC, 0, 0, ESC, 0, 0);
    g.imageSmoothingEnabled = false;
    capasHtml = "";
    return true;
  }

  const JEFE = { id: "jefe", nombre: "Tú (Miguel)", rol: "La voz del canal", color: AM, pelo: "corto",
                 desc: "Grabas la narración por escena (escena-01 a escena-14) y apruebas todo. Nada se hace público sin ti." };
  let equipo = [], expedientes = [], elegido = null, t = 0;
  const agente = (id) => (id === "jefe" ? JEFE : equipo.find((a) => a.id === id));
  const trabaja = (a) => a && a.estado === "trabajando";

  // ---------- piezas de dibujo ----------
  function cuarto(c) {
    const { x, y, w, h } = c;
    for (let yy = y; yy < y + h; yy += 6)
      for (let xx = x; xx < x + w; xx += 6) R(xx, yy, 6, 6, ((xx + yy) / 6) % 2 ? c.piso[0] : c.piso[1]);
    R(x, y, w, 14, "#2f2f35"); R(x, y + 13, w, 2, "#17171a"); // pared del fondo y zócalo
    R(x, y, w, 2, "#45454d");
    // muros laterales y puerta al pasillo
    R(x, y, 2, h, "#0d0d0f"); R(x + w - 2, y, 2, h, "#0d0d0f");
    const puertaY = c.abajo ? y + h - 2 : y;
    R(x, puertaY, w, 2, "#0d0d0f");
    R(x + w / 2 - 8, puertaY, 16, 2, "#3a2c1c");
  }
  function pasillo(py) {
    R(0, py, W, PAS, "#161616");
    for (let x = 0; x < W; x += 8) { R(x, py, 4, 2, AM); R(x + 4, py, 4, 2, "#111"); R(x + 2, py + 18, 4, 2, AM); R(x + 6, py + 18, 4, 2, "#111"); }
    R(W / 2 - 10, py + 6, 20, 8, "#3b1d20"); R(W / 2 - 4, py + 8, 8, 4, ROJO); // tapete
    planta(6, py + 5); planta(W - 14, py + 5);
  }
  function planta(x, y) { R(x + 2, y + 6, 6, 6, "#5a3b22"); R(x, y, 10, 6, "#1f6b35"); R(x + 2, y - 3, 6, 4, VERDE); }
  function escritorio(x, y, w = 30) { R(x, y, w, 9, "#5b3e25"); R(x, y, w, 2, "#7a5634"); R(x + 2, y + 9, 2, 4, "#3a2716"); R(x + w - 4, y + 9, 2, 4, "#3a2716"); }
  function monitor(x, y, w = 14, h = 9, pantalla = "#0b2238") { R(x, y, w, h, "#111"); R(x + 1, y + 1, w - 2, h - 2, pantalla); R(x + w / 2 - 1, y + h, 2, 2, "#222"); }
  // persona: de espaldas (trabajando en su escritorio) o de frente (en la cabina)
  const PELO = { gorra: "#26313f", copete: "#3a2216", chongo: "#1d120c", bob: "#2a1a12", corto: "#2b1d14", largo: "#4a2c19", rizos: "#20140d" };
  function persona(x, y, a, { frente = false, tecleo = false, apagado = false } = {}) {
    const piel = "#d9a47a", pelo = PELO[a?.pelo] || "#2b1d14", ropa = a?.color || "#888";
    const b = tecleo && Math.floor(t * 6) % 2 ? 1 : 0;
    g.globalAlpha = apagado ? 0.45 : 1;
    R(x - 4, y + 7, 9, 7, ropa); R(x - 5, y + 8 + b, 2, 5, ropa); R(x + 4, y + 9 - b, 2, 5, ropa); // cuerpo y brazos
    if (frente) {
      R(x - 3, y, 7, 7, piel); R(x - 3, y, 7, 2, pelo); R(x - 2, y + 3, 1, 1, "#111"); R(x + 2, y + 3, 1, 1, "#111");
    } else {
      R(x - 3, y, 7, 7, pelo); R(x - 3, y + 6, 7, 1, piel);
    }
    if (a?.pelo === "gorra") { R(x - 4, y - 1, 9, 3, "#1b2430"); R(frente ? x - 4 : x - 1, frente ? y + 1 : y - 2, 9, 1, "#111"); }
    if (a?.pelo === "chongo") R(x - 1, y - 3, 3, 3, pelo);
    if (a?.pelo === "largo") { R(x - 4, y + 2, 1, 6, pelo); R(x + 4, y + 2, 1, 6, pelo); }
    g.globalAlpha = 1;
  }

  // ---------- la decoración de cada área ----------
  function verificacion(c, a, on) {
    const { x, y } = c;
    R(x + 6, y + 2, 38, 11, "#6b4a2b"); R(x + 7, y + 3, 36, 9, "#8a6239"); // pizarrón de evidencias
    [[9, 4], [18, 6], [28, 4], [36, 7], [13, 8]].forEach(([dx, dy]) => R(x + dx, y + dy, 5, 4, "#e7e2d4"));
    g.strokeStyle = ROJO; g.lineWidth = 0.6; g.beginPath(); g.moveTo(x + 11, y + 6); g.lineTo(x + 20, y + 8); g.lineTo(x + 30, y + 6);
    g.lineTo(x + 38, y + 9); g.moveTo(x + 20, y + 8); g.lineTo(x + 15, y + 10); g.stroke();
    R(x + 54, y + 4, 14, 22, "#4b4f57"); [0, 7, 14].forEach((d) => { R(x + 55, y + 5 + d, 12, 6, "#5c616a"); R(x + 59, y + 7 + d, 4, 1, "#999"); }); // archivero
    escritorio(x + 12, y + 30, 34); monitor(x + 22, y + 22, 14, 9, on ? "#3a3000" : "#1d1d1d");
    if (on) { R(x + 23, y + 23, 12, 1, AM); R(x + 23, y + 25, 8, 1, AM); R(x + 23, y + 27, 10, 1, AM); }
    R(x + 14, y + 24, 2, 7, "#333"); R(x + 12, y + 22, 6, 3, on ? AM : "#555"); // lámpara
    if (on) { g.globalAlpha = 0.12; R(x + 8, y + 25, 16, 14, AM); g.globalAlpha = 1; }
    R(x + 40, y + 44, 10, 7, "#8b6a43"); R(x + 40, y + 44, 10, 2, "#a5825a"); // caja de evidencias
    persona(x + 29, y + 42, a, { tecleo: on });
    R(x + 10, y + 64, 22, 12, "#3a2a1e"); R(x + 12, y + 66, 18, 8, "#4a3626"); // mesa de interrogatorio
  }
  function archivo(c, a, on) {
    const { x, y } = c;
    for (let fila = 0; fila < 3; fila++) {
      R(x + 4, y + 2 + fila * 5, 70, 1, "#3a2716");
      for (let i = 0; i < 10; i++) R(x + 5 + i * 7, y + fila * 5 - 1 + 0, 6, 3, ["#8b6a43", "#7a5c39", "#9b7a50"][(i + fila) % 3]);
    }
    escritorio(x + 22, y + 32, 34); monitor(x + 32, y + 24, 14, 9, "#0d1a26");
    for (let i = 0; i < 6; i++) R(x + 33 + (i % 3) * 4, y + 25 + Math.floor(i / 3) * 3, 3, 2, on && (Math.floor(t * 3) + i) % 6 === 0 ? AM : ["#2d6a8a", VERDE, "#7a7a7a"][i % 3]);
    persona(x + 39, y + 44, a, { tecleo: on });
    R(x + 6, y + 54, 12, 18, "#4b4f57"); R(x + 7, y + 56, 10, 4, "#5c616a"); R(x + 7, y + 62, 10, 4, "#5c616a"); R(x + 7, y + 68, 10, 3, "#5c616a");
    R(x + 58, y + 58, 12, 9, "#8b6a43"); R(x + 60, y + 54, 12, 9, "#9b7a50");
  }
  function graficas(c, a, on) {
    const { x, y } = c;
    R(x + 8, y + 2, 30, 11, "#e9e9e9"); R(x + 10, y + 10, 26, 1, "#888"); // pizarrón blanco con una gráfica
    [[12, 5, ROJO], [18, 3, AM], [24, 6, VERDE], [30, 2, AM]].forEach(([dx, hh, col]) => R(x + dx, y + 10 - hh * 1.2, 4, hh * 1.2, col));
    escritorio(x + 18, y + 32, 40);
    monitor(x + 24, y + 20, 28, 13, "#101010");
    const n = on ? (t * 1.2) % 1 : 1;
    [[ROJO, 0.9], [AM, 0.55], [VERDE, 0.75], [AM, 0.4], [VERDE, 1]].forEach(([col, v], i) => {
      const hh = Math.max(1, Math.round(9 * v * Math.min(1, n * 1.6 - i * 0.12 > 0 ? n * 1.6 - i * 0.12 : 0.02)));
      R(x + 26 + i * 5, y + 31 - hh, 3, hh, col);
    });
    persona(x + 38, y + 44, a, { tecleo: on });
    R(x + 62, y + 50, 10, 16, "#2a2a2e"); R(x + 63, y + 52, 8, 3, on ? VERDE : "#333"); R(x + 63, y + 57, 8, 3, "#333"); // render (la compu)
  }
  function miniaturas(c, a, on) {
    const { x, y } = c;
    R(x + 40, y + 20, 3, 26, "#3a2716"); R(x + 26, y + 18, 30, 18, "#111"); R(x + 27, y + 19, 28, 16, "#1d1d1d"); // caballete con la miniatura
    R(x + 30, y + 25, 9, 7, "#9fb9c9"); R(x + 30, y + 27, 9, 1, AM); // un tóper con cinta amarilla
    R(x + 41, y + 22, 12, 3, BLANCO); R(x + 41, y + 27, 12, 3, AM);
    R(x + 6, y + 18, 9, 9, on ? "#fff" : "#bbb"); R(x + 10, y + 27, 1, 18, "#444"); // luces
    R(x + 62, y + 18, 9, 9, on ? "#fff" : "#bbb"); R(x + 66, y + 27, 1, 18, "#444");
    if (on) { g.globalAlpha = 0.1; R(x + 14, y + 20, 50, 30, "#fff"); g.globalAlpha = 1; }
    persona(x + 41, y + 52, a, { tecleo: on });
    R(x + 10, y + 62, 6, 5, "#222"); R(x + 12, y + 67, 1, 10, "#444"); R(x + 9, y + 77, 8, 1, "#444"); // cámara en tripié
  }
  function cabina(c, a, on) {
    const { x, y } = c;
    for (let i = 0; i < 12; i++) for (let j = 0; j < 2; j++) R(x + 3 + i * 6, y + 2 + j * 6, 5, 5, (i + j) % 2 ? "#2a2a2e" : "#333338"); // espuma acústica
    const alAire = on && Math.floor(t * 2) % 2 === 0;
    R(x + 54, y + 16, 18, 6, alAire ? ROJO : "#3a1a1c"); R(x + 56, y + 18, 14, 2, alAire ? "#ffd0d0" : "#5a2a2c"); // ON AIR
    persona(x + 30, y + 40, JEFE, { frente: true });
    R(x + 38, y + 30, 1, 30, "#555"); R(x + 34, y + 60, 9, 1, "#555"); R(x + 36, y + 27, 5, 6, "#1b1b1b"); R(x + 37, y + 28, 3, 4, "#444"); // micrófono
    R(x + 18, y + 30, 6, 8, "#222"); R(x + 19, y + 31, 4, 6, on ? AM : "#333"); // el atril con la narración
    R(x + 4, y + 66, 26, 10, "#3a2c22"); R(x + 6, y + 68, 22, 6, "#4a382a"); // sillón
  }
  function edicion(c, a, on) {
    const { x, y } = c;
    R(x + 8, y + 2, 20, 11, "#111"); R(x + 9, y + 3, 18, 9, "#1c2733"); // póster de la serie
    R(x + 10, y + 5, 14, 2, BLANCO); R(x + 10, y + 8, 10, 2, ROJO);
    escritorio(x + 12, y + 32, 52);
    monitor(x + 16, y + 21, 20, 12, "#0e1520"); monitor(x + 40, y + 21, 20, 12, "#0e1520");
    [[AM, 0], [VERDE, 3], [ROJO, 6]].forEach(([col, dy]) => { R(x + 17, y + 25 + dy, 8, 2, col); R(x + 27, y + 25 + dy, 6, 2, col); });
    const cab = on ? Math.floor((t * 8) % 16) : 4;
    R(x + 17 + cab, y + 23, 1, 9, "#fff"); // cabezal de la línea de tiempo
    R(x + 41, y + 22, 18, 10, on ? "#334155" : "#1c2733"); if (on) R(x + 47, y + 25, 5, 4, AM);
    persona(x + 38, y + 44, a, { tecleo: on });
  }
  function subtitulos(c, a, on) {
    const { x, y } = c;
    escritorio(x + 14, y + 32, 40); monitor(x + 18, y + 20, 22, 13, "#101418");
    for (let i = 0; i < 4; i++) R(x + 20, y + 22 + i * 3, on && i === Math.floor(t * 3) % 4 ? 18 : 14 - i * 2, 1, on && i === Math.floor(t * 3) % 4 ? AM : "#9aa");
    R(x + 46, y + 18, 8, 14, "#111"); R(x + 47, y + 19, 6, 12, on ? "#1f2937" : "#18181b"); R(x + 48, y + 27, 4, 1, AM); // cel vertical (Shorts)
    persona(x + 32, y + 44, a, { tecleo: on });
    R(x + 58, y + 4, 12, 9, "#111"); R(x + 59, y + 5, 10, 7, "#1d1d1d"); R(x + 60, y + 10, 8, 1, BLANCO); // .srt en la pared
    planta(x + 62, y + 64);
  }
  function publicacion(c, a, on) {
    const { x, y } = c;
    R(x + 8, y + 2, 16, 11, ROJO); g.fillStyle = "#fff"; g.beginPath(); g.moveTo(x + 14, y + 4); g.lineTo(x + 19, y + 7.5); g.lineTo(x + 14, y + 11); g.fill();
    R(x + 52, y + 3, 9, 7, "#9aa0a6"); R(x + 54, y + 0, 5, 4, "#9aa0a6"); R(x + 55, y + 1, 3, 3, "#2f2f35"); R(x + 55, y + 5, 3, 2, "#333"); // candado (siempre privado)
    escritorio(x + 18, y + 32, 40); monitor(x + 26, y + 20, 24, 13, "#141414");
    R(x + 28, y + 22, 20, 8, "#202020"); R(x + 34, y + 24, 6, 4, ROJO);
    if (on) R(x + 28, y + 31, Math.round(20 * ((t * 0.4) % 1)), 1, VERDE); // barra de subida
    persona(x + 38, y + 44, a, { tecleo: on });
    R(x + 8, y + 50, 14, 6, "#5b3e25"); R(x + 9, y + 48, 12, 3, "#e7e2d4"); // bandeja de salida
  }

  // ---------- pintar ----------
  function jefeTrabaja() {
    return expedientes.some((e) => (e.pasos || []).some((p) => p.clave === "voz" && p.estado === "pendiente"));
  }
  function pintar() {
    R(0, 0, W, H, "#0b0b0c");
    PASILLOS.forEach(pasillo);
    for (const c of CUARTOS) {
      const a = agente(c.id);
      const on = c.id === "jefe" ? jefeTrabaja() : trabaja(a);
      cuarto(c);
      c.deco(c, a, on);
      const obra = c.id !== "jefe" && a?.obra && !on;
      if (obra) {
        g.globalAlpha = 0.5; R(c.x + 2, c.y + 2, c.w - 4, c.h - 4, "#000"); g.globalAlpha = 1;
        const yy = c.abajo ? c.y + c.h - 9 : c.y + 4;
        for (let i = 0; i < c.w - 8; i += 6) { R(c.x + 4 + i, yy, 3, 3, AM); R(c.x + 7 + i, yy, 3, 3, "#111"); }
      }
      if (elegido === c.id) {
        g.strokeStyle = AM; g.lineWidth = 1; g.strokeRect(c.x + 1.5, c.y + 1.5, c.w - 3, c.h - 3);
      }
    }
  }

  // Letreros y globos en HTML (texto nítido en cualquier pantalla)
  let capasHtml = "";
  function pintarCapas() {
    const ahora = Date.now() / 1000;
    const html = CUARTOS.map((c) => {
      const a = agente(c.id);
      const obra = c.id !== "jefe" && a?.obra && !trabaja(a);
      const ly = c.y + c.h - 13;
      let s = `<span class="ag-letrero${obra ? " obra" : ""}" style="left:${(c.x + c.w / 2) / W * 100}%;top:${ly / H * 100}%">${esc(c.nombre)}<small>${obra ? "🚧 En obra" : esc(a?.nombre || c.sub)}</small></span>`;
      const dice = c.id === "jefe" ? (jefeTrabaja() ? "Te toca grabar 🎙️" : "") : (a?.dice && (trabaja(a) || ahora - (a.dice_t || 0) < 60) ? a.dice : "");
      const gx = Math.min(W - 30, Math.max(30, c.x + c.w / 2)); // que el globo no se salga del plano
      if (dice) s += `<span class="ag-globo" style="left:${gx / W * 100}%;top:${(c.y + 26) / H * 100}%">${esc(dice)}</span>`;
      return s;
    }).join("");
    if (html !== capasHtml) { capas.innerHTML = html; capasHtml = html; }
  }

  function pintarFicha() {
    if (!elegido) return;
    const a = agente(elegido), c = CUARTOS.find((x) => x.id === elegido);
    if (!a || !c) return;
    const estado = elegido === "jefe" ? (jefeTrabaja() ? "🎙️ Te toca grabar la voz" : "👀 Revisa el panel de la derecha")
      : trabaja(a) ? "⏳ Trabajando" : a.obra ? `🚧 ${a.obra}` : "😌 Libre";
    ficha.innerHTML = `<h3>${esc(c.nombre)} · ${esc(a.nombre)}</h3><p class="rol">${esc(a.rol)}</p>
      <p>${esc(estado)}${a.dice && elegido !== "jefe" ? ` — «${esc(a.dice)}»` : ""}</p><p class="pista">${esc(a.desc || "")}</p>`;
  }

  cv.addEventListener("click", (e) => {
    const r = cv.getBoundingClientRect();
    const px = (e.clientX - r.left) / r.width * W, py = (e.clientY - r.top) / r.height * H;
    const c = CUARTOS.find((q) => px >= q.x && px < q.x + q.w && py >= q.y && py < q.y + q.h);
    elegido = c ? c.id : null;
    if (!c) ficha.innerHTML = `<p class="pista">Toca un cuarto para ver quién trabaja ahí y qué está haciendo.</p>`;
    pintar(); pintarFicha();
  });

  // ---------- animación: solo cuando alguien trabaja (6 cuadros por segundo) ----------
  let reloj = null;
  function animar() {
    const vivo = !document.hidden && (equipo.some(trabaja) || jefeTrabaja());
    if (vivo && !reloj) reloj = setInterval(() => { t += 1 / 6; pintar(); }, 1000 / 6);
    if (!vivo && reloj) { clearInterval(reloj); reloj = null; }
  }
  document.addEventListener("visibilitychange", () => { animar(); if (!document.hidden) cargar(); });

  // ---------- datos ----------
  window.Oficina = { equipoExp: () => equipo }; // expedientes.js saca de aquí los nombres del equipo
  async function cargar() {
    if (document.hidden) return;
    try {
      const r = await fetch("/api/expedientes").then((x) => x.json());
      equipo = r.equipo || [];
      expedientes = r.expedientes || [];
      const caso = expedientes[0];
      const chip = document.getElementById("ag-caso");
      if (chip) { chip.hidden = !caso; if (caso) chip.textContent = `Expediente #${String(caso.numero).padStart(3, "0")} · ${caso.marca}`; }
    } catch { /* sin conexión: se queda lo último */ }
    pintar(); pintarCapas(); pintarFicha(); animar();
  }
  setInterval(cargar, 4000);
  addEventListener("resize", () => { if (acomodar()) { pintar(); pintarCapas(); } });
  acomodar();
  pintar();
  cargar();
  window.dispatchEvent(new CustomEvent("pestana", { detail: "expedientes" }));
})();
