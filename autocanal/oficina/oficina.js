// Motor de la oficina isométrica en pixel art: sala, muebles, agentes, selección y globos de texto.
(() => {
  const K = 2; // densidad: cada "pixel" de diseño de muebles mide K pixeles reales; los personajes usan el detalle completo
  const COLS = 14, ROWS = 10, TW = 32 * K, TH = 16 * K, MURO = 74, PAD = 16 * K;
  const ANCHO = (COLS + ROWS) * TW / 2 + PAD * 2;
  const ALTO = MURO * K + (COLS + ROWS) * TH / 2 + PAD * 2 + 14 * K;
  const OX = ROWS * TW / 2 + PAD, OY = MURO * K + PAD + 8 * K;
  const VELOCIDAD = 3.2; // casillas por segundo

  const iso = (x, y, z = 0) => [OX + (x - y) * TW / 2, OY + (x + y) * TH / 2 - z * K];

  // ---------- distribución ----------
  const ESCRITORIOS = {
    investigador: [1, 1], guionista: [3, 1], locutor: [5, 1], productora: [8, 1],
    disenadora: [2, 5], editor: [4, 5], redactora: [6, 5], community: [8, 5],
  };
  const CASA = { jefe: [11, 1] };
  const VISITA = { jefe: [11, 3] };
  for (const [id, [x, y]] of Object.entries(ESCRITORIOS)) {
    CASA[id] = [x, y + 1];
    VISITA[id] = [x + 1, y + 1];
  }
  const CAFE = [12, 5];
  const PASEOS = [CAFE, [11, 7], [10, 4], [6, 3], [9, 8], [12, 7]];

  const bloqueado = new Set();
  const bloquear = (x, y) => bloqueado.add(`${x},${y}`);
  Object.values(ESCRITORIOS).forEach(([x, y]) => bloquear(x, y));
  [[10, 2], [11, 2], [12, 2], [11, 1], [13, 5], [13, 6], [13, 7], [13, 8], [13, 9], [12, 8], [0, 0], [13, 0], [0, 9],
   [0, 3], [0, 4]].forEach(([x, y]) => bloquear(x, y));

  function ruta(desde, hasta) { // BFS sobre la cuadrícula
    const clave = (p) => `${p[0]},${p[1]}`;
    const inicio = [Math.round(desde[0]), Math.round(desde[1])];
    const meta = clave(hasta);
    const previo = new Map([[clave(inicio), null]]);
    const cola = [inicio];
    while (cola.length) {
      const p = cola.shift();
      if (clave(p) === meta) break;
      for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
        const n = [p[0] + dx, p[1] + dy], k = clave(n);
        if (n[0] < 0 || n[1] < 0 || n[0] >= COLS || n[1] >= ROWS || previo.has(k)) continue;
        if (bloqueado.has(k) && k !== meta) continue;
        previo.set(k, p);
        cola.push(n);
      }
    }
    if (!previo.has(meta)) return [hasta];
    const camino = [];
    for (let p = hasta; p && clave(p) !== clave(inicio); p = previo.get(clave(p))) camino.unshift(p);
    return camino;
  }

  // ---------- lienzos ----------
  const lienzo = document.getElementById("lienzo");
  const capas = document.getElementById("capas");
  const sala = document.getElementById("sala");
  const buf = document.createElement("canvas");
  buf.width = ANCHO; buf.height = ALTO;
  const g = buf.getContext("2d");
  const ctx = lienzo.getContext("2d");
  let escala = 1;

  function poligono(puntos, relleno, borde) {
    g.beginPath();
    puntos.forEach(([x, y], i) => (i ? g.lineTo(x, y) : g.moveTo(x, y)));
    g.closePath();
    g.fillStyle = relleno; g.fill();
    if (borde) { g.strokeStyle = borde; g.lineWidth = 1; g.stroke(); }
  }

  function caja(x0, y0, x1, y1, z0, h, arriba, izq, der) {
    const P = (x, y, z) => iso(x, y, z);
    poligono([P(x0, y1, z0), P(x1, y1, z0), P(x1, y1, z0 + h), P(x0, y1, z0 + h)], izq);
    poligono([P(x1, y0, z0), P(x1, y1, z0), P(x1, y1, z0 + h), P(x1, y0, z0 + h)], der);
    poligono([P(x0, y0, z0 + h), P(x1, y0, z0 + h), P(x1, y1, z0 + h), P(x0, y1, z0 + h)], arriba);
  }

  function aclarar(hex, f) {
    const n = parseInt(hex.slice(1), 16);
    const c = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map((v) => Math.max(0, Math.min(255, Math.round(f > 1 ? v + (255 - v) * (f - 1) : v * f))));
    return `rgb(${c.join(",")})`;
  }

  const esDeNoche = () => { const h = new Date().getHours(); return h >= 19 || h < 7; };

  // ---------- sala ----------
  function piso(estado, t) {
    for (let x = 0; x < COLS; x++) for (let y = 0; y < ROWS; y++) {
      const c = (x + y) % 2 ? "#d8b88f" : "#ceac81";
      poligono([iso(x, y), iso(x + 1, y), iso(x + 1, y + 1), iso(x, y + 1)], c, "rgba(120,80,40,.16)");
      // vetas de madera
      g.fillStyle = "rgba(120,80,40,.10)";
      const [vx, vy] = iso(x + 0.35, y + 0.5);
      g.fillRect(Math.round(vx), Math.round(vy), 10, 1);
    }
    // tapete de la sala de descanso
    poligono([iso(10, 6.4), iso(13, 6.4), iso(13, 9.6), iso(10, 9.6)], "#5b6fd6");
    poligono([iso(10.25, 6.65), iso(12.75, 6.65), iso(12.75, 9.35), iso(10.25, 9.35)], "#6f82e8");
    poligono([iso(10.5, 6.9), iso(12.5, 6.9), iso(12.5, 9.1), iso(10.5, 9.1)], "#7b8df0");
    // tapete del jefe
    poligono([iso(9.8, 0.6), iso(13.2, 0.6), iso(13.2, 3.6), iso(9.8, 3.6)], "#9b2c3c");
    poligono([iso(10, 0.8), iso(13, 0.8), iso(13, 3.4), iso(10, 3.4)], "#b4384a");
    // borde del piso (grosor)
    const grosor = 6 * K;
    poligono([iso(0, ROWS), iso(COLS, ROWS), [iso(COLS, ROWS)[0], iso(COLS, ROWS)[1] + grosor], [iso(0, ROWS)[0], iso(0, ROWS)[1] + grosor]], "#8f6a44");
    poligono([iso(COLS, 0), iso(COLS, ROWS), [iso(COLS, ROWS)[0], iso(COLS, ROWS)[1] + grosor], [iso(COLS, 0)[0], iso(COLS, 0)[1] + grosor]], "#7a5838");
    // brillo de los monitores encendidos sobre el piso
    g.save();
    g.globalCompositeOperation = "lighter";
    for (const [id, [x, y]] of Object.entries(ESCRITORIOS)) {
      const a = estado.agentes[id];
      if (a?.estado !== "trabajando") continue;
      const [cx, cy] = iso(x + 0.5, y + 1.05);
      const pulso = 0.16 + Math.sin(t * 3 + x) * 0.03;
      const gr = g.createRadialGradient(cx, cy, 2, cx, cy, 46);
      gr.addColorStop(0, hexA(PANTALLA_LUZ[id], pulso));
      gr.addColorStop(1, hexA(PANTALLA_LUZ[id], 0));
      g.fillStyle = gr;
      g.beginPath(); g.ellipse(cx, cy, 46, 23, 0, 0, Math.PI * 2); g.fill();
    }
    g.restore();
  }

  function hexA(hex, a) {
    const n = parseInt(hex.slice(1), 16);
    return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
  }

  const muroD = (x, h) => iso(x, 0, h);
  const muroI = (y, h) => iso(0, y, h);

  function muros(t, estado) {
    poligono([muroI(0, 0), muroI(ROWS, 0), muroI(ROWS, MURO), muroI(0, MURO)], "#e6d7bd");
    poligono([muroD(0, 0), muroD(COLS, 0), muroD(COLS, MURO), muroD(0, MURO)], "#f1e6d2");
    // franja inferior de color
    poligono([muroI(0, 0), muroI(ROWS, 0), muroI(ROWS, 18), muroI(0, 18)], "#c9b28d");
    poligono([muroD(0, 0), muroD(COLS, 0), muroD(COLS, 18), muroD(0, 18)], "#d6bf99");
    poligono([muroI(0, 18), muroI(ROWS, 18), muroI(ROWS, 19), muroI(0, 19)], "#a88d66");
    poligono([muroD(0, 18), muroD(COLS, 18), muroD(COLS, 19), muroD(0, 19)], "#b39771");
    poligono([muroI(0, 0), muroI(ROWS, 0), muroI(ROWS, 3), muroI(0, 3)], "#8f7552");
    poligono([muroD(0, 0), muroD(COLS, 0), muroD(COLS, 3), muroD(0, 3)], "#9c8059");
    poligono([muroI(0, MURO - 3), muroI(ROWS, MURO - 3), muroI(ROWS, MURO), muroI(0, MURO)], "#9c7f5a");
    poligono([muroD(0, MURO - 3), muroD(COLS, MURO - 3), muroD(COLS, MURO), muroD(0, MURO)], "#a88a63");
    // ventanas
    const hora = new Date().getHours();
    const cielo = esDeNoche() ? ["#16204a", "#2a3a78"] : hora >= 17 ? ["#f59e6b", "#fcd5a5"] : ["#7cc4f2", "#c9ecff"];
    for (const [a, b] of [[1.6, 3.4], [9.4, 10.6]]) {
      poligono([muroD(a - 0.08, 22), muroD(b + 0.08, 22), muroD(b + 0.08, 64), muroD(a - 0.08, 64)], "#fff");
      poligono([muroD(a, 26), muroD(b, 26), muroD(b, 62), muroD(a, 62)], cielo[0]);
      poligono([muroD(a, 26), muroD(b, 26), muroD(b, 40), muroD(a, 40)], cielo[1]);
      if (esDeNoche()) { // estrellas y edificios
        g.fillStyle = "#fff";
        for (let i = 0; i < 6; i++) { const [sx, sy] = muroD(a + 0.15 + i * 0.27, 50 + ((i * 7) % 10)); if (Math.floor(t * 2 + i) % 5) g.fillRect(Math.round(sx), Math.round(sy), 2, 2); }
        poligono([muroD(a, 26), muroD(a + 0.5, 26), muroD(a + 0.5, 38), muroD(a, 38)], "#0d1430");
        poligono([muroD(a + 0.7, 26), muroD(a + 1.1, 26), muroD(a + 1.1, 44), muroD(a + 0.7, 44)], "#0d1430");
      } else { // nube
        const nx = a + 0.2 + ((t * 0.03) % 1) * (b - a - 0.6);
        poligono([muroD(nx, 50), muroD(nx + 0.4, 50), muroD(nx + 0.4, 54), muroD(nx, 54)], "rgba(255,255,255,.85)");
        poligono([muroD(nx + 0.1, 54), muroD(nx + 0.3, 54), muroD(nx + 0.3, 57), muroD(nx + 0.1, 57)], "rgba(255,255,255,.85)");
      }
      const m = (a + b) / 2;
      poligono([muroD(m - 0.04, 26), muroD(m + 0.04, 26), muroD(m + 0.04, 62), muroD(m - 0.04, 62)], "#fff");
      poligono([muroD(a, 43), muroD(b, 43), muroD(b, 45), muroD(a, 45)], "#fff");
      poligono([muroD(a - 0.12, 20), muroD(b + 0.12, 20), muroD(b + 0.12, 22), muroD(a - 0.12, 22)], "#d9cbb3"); // repisa
    }
    // póster del canal
    poligono([muroD(6.6, 30), muroD(7.9, 30), muroD(7.9, 60), muroD(6.6, 60)], "#e53935", "#7f1d1d");
    poligono([muroD(7.05, 37), muroD(7.55, 45), muroD(7.05, 53)], "#fff");
    // luz "AL AIRE" del locutor
    const alAire = estado.agentes.locutor?.estado === "trabajando";
    poligono([muroD(4.7, 50), muroD(5.55, 50), muroD(5.55, 58), muroD(4.7, 58)], alAire && Math.floor(t * 2) % 2 ? "#ff3b30" : "#5a2020", "#2a0d0d");
    if (alAire) { const [lx, ly] = muroD(4.9, 55.5); g.fillStyle = "#fff"; g.fillRect(Math.round(lx), Math.round(ly), 2 * K, K); g.fillRect(Math.round(lx) + 3 * K, Math.round(ly) + K, 2 * K, K); }
    // reloj
    const [cx, cy] = muroD(12.3, 52);
    g.fillStyle = "#fff"; g.beginPath(); g.ellipse(cx, cy, 6 * K, 7 * K, 0, 0, Math.PI * 2); g.fill();
    g.strokeStyle = "#333"; g.lineWidth = K; g.stroke();
    const d = new Date(), am = (d.getMinutes() / 60) * Math.PI * 2, ah = ((d.getHours() % 12) / 12) * Math.PI * 2 + am / 12;
    g.beginPath(); g.moveTo(cx, cy); g.lineTo(cx + Math.sin(am) * 5 * K, cy - Math.cos(am) * 5 * K);
    g.moveTo(cx, cy); g.lineTo(cx + Math.sin(ah) * 3 * K, cy - Math.cos(ah) * 3 * K); g.stroke();
    g.lineWidth = 1;
    // pizarrón con notas
    poligono([muroI(5.2, 22), muroI(8.8, 22), muroI(8.8, 60), muroI(5.2, 60)], "#fbfbf7", "#8a8a8a");
    const notas = ["#fde047", "#f9a8d4", "#86efac", "#93c5fd", "#fdba74", "#c4b5fd"];
    notas.forEach((c, i) => {
      const y0 = 5.5 + (i % 3) * 1.1, z0 = 30 + Math.floor(i / 3) * 14;
      poligono([muroI(y0, z0), muroI(y0 + 0.7, z0), muroI(y0 + 0.7, z0 + 10), muroI(y0, z0 + 10)], c);
    });
    // pantalla de estadísticas (proyectos por estado)
    poligono([muroI(1.0, 30), muroI(3.4, 30), muroI(3.4, 62), muroI(1.0, 62)], "#111827", "#000");
    const proy = estado.proyectos || [];
    const cuenta = [proy.filter((p) => p.estado === "produccion").length, proy.filter((p) => p.estado === "revision").length,
                    proy.filter((p) => p.estado === "publicado").length];
    const colores = ["#f59e0b", "#e84d8a", "#22c55e"];
    cuenta.forEach((n, i) => {
      const alto = 4 + Math.min(n, 6) * 3.5 + Math.sin(t * 2 + i) * 0.6;
      const y0 = 1.35 + i * 0.7;
      poligono([muroI(y0, 34), muroI(y0 + 0.45, 34), muroI(y0 + 0.45, 34 + alto), muroI(y0, 34 + alto)], colores[i]);
    });
    poligono([muroI(1.0, 58), muroI(3.4, 58), muroI(3.4, 62), muroI(1.0, 62)], "#e53935");
  }

  // ---------- muebles ----------
  const PANTALLA = { investigador: "#1e3a8a", guionista: "#78350f", locutor: "#4c1d95", productora: "#831843",
                     disenadora: "#065f46", editor: "#7f1d1d", redactora: "#155e75", community: "#7c2d12" };
  const PANTALLA_LUZ = { investigador: "#60a5fa", guionista: "#fbbf24", locutor: "#a78bfa", productora: "#f472b6",
                         disenadora: "#34d399", editor: "#f87171", redactora: "#22d3ee", community: "#fb923c" };

  function escritorio(id, x, y, t, estado) {
    caja(x + 0.06, y + 0.12, x + 0.94, y + 0.88, 0, 12, "#c8915a", "#9c6b3e", "#875a32");
    caja(x + 0.06, y + 0.12, x + 0.94, y + 0.88, 11, 1, "#d9a46b", "#b07a4a", "#9c6b3e"); // canto
    const a = estado.agentes[id];
    const trabajando = a?.estado === "trabajando";
    caja(x + 0.46, y + 0.32, x + 0.54, y + 0.38, 12, 3, "#1f2937", "#111827", "#111827"); // pie del monitor
    caja(x + 0.24, y + 0.3, x + 0.76, y + 0.38, 15, 11, "#2b2b3a", trabajando ? (Math.floor(t * 4) % 9 ? PANTALLA[id] : "#475569") : "#22314d", "#1c1c28");
    if (trabajando) {
      for (let i = 0; i < 4; i++) {
        const w = 0.06 + ((Math.sin(t * 3 + i * 2 + x) + 1) / 2) * 0.3;
        poligono([iso(x + 0.29, y + 0.38, 23.5 - i * 2.2), iso(x + 0.29 + w, y + 0.38, 23.5 - i * 2.2),
                  iso(x + 0.29 + w, y + 0.38, 22.8 - i * 2.2), iso(x + 0.29, y + 0.38, 22.8 - i * 2.2)], "rgba(255,255,255,.8)");
      }
    } else {
      poligono([iso(x + 0.3, y + 0.38, 24), iso(x + 0.42, y + 0.38, 24), iso(x + 0.42, y + 0.38, 21), iso(x + 0.3, y + 0.38, 21)], "rgba(255,255,255,.08)");
    }
    caja(x + 0.3, y + 0.55, x + 0.7, y + 0.68, 12, 1, "#e5e7eb", "#9ca3af", "#9ca3af"); // teclado
    caja(x + 0.76, y + 0.58, x + 0.84, y + 0.66, 12, 1, "#e5e7eb", "#9ca3af", "#9ca3af"); // mouse
    if (id === "locutor") {
      caja(x + 0.14, y + 0.5, x + 0.2, y + 0.56, 12, 10, "#333", "#222", "#111");
      const [mx, my] = iso(x + 0.17, y + 0.53, 24);
      g.fillStyle = "#555"; g.fillRect(Math.round(mx) - 3, Math.round(my) - 6, 7, 9);
      g.fillStyle = "#777"; g.fillRect(Math.round(mx) - 2, Math.round(my) - 5, 2, 7);
    }
    if (id === "productora") { caja(x + 0.1, y + 0.2, x + 0.22, y + 0.32, 12, 5, "#fef08a", "#eab308", "#ca8a04"); caja(x + 0.12, y + 0.56, x + 0.26, y + 0.8, 12, 1, "#fff", "#ddd", "#ccc"); }
    if (id === "disenadora") caja(x + 0.1, y + 0.55, x + 0.26, y + 0.8, 12, 1, "#f472b6", "#be185d", "#9d174d");
    if (id === "investigador") { caja(x + 0.1, y + 0.6, x + 0.24, y + 0.84, 12, 2, "#f5f5f4", "#d6d3d1", "#a8a29e"); caja(x + 0.1, y + 0.6, x + 0.24, y + 0.84, 14, 2, "#fde68a", "#f59e0b", "#d97706"); }
    if (id === "guionista" || id === "redactora") caja(x + 0.1, y + 0.2, x + 0.2, y + 0.3, 12, 5, "#fff", "#e5e7eb", "#d1d5db"); // taza
    if (id === "editor") caja(x + 0.8, y + 0.2, x + 0.9, y + 0.34, 12, 9, "#111827", "#1f2937", "#111827"); // bocina
    if (id === "community") { caja(x + 0.12, y + 0.56, x + 0.2, y + 0.7, 12, 0.6, "#111", "#000", "#000"); }
  }

  function silla(x, y, color) { // silla de oficina; el respaldo queda hacia la cámara
    const cx = x + 0.5, cy = y + 0.5;
    caja(cx - 0.05, cy - 0.05, cx + 0.05, cy + 0.05, 1, 8, "#4b5563", "#374151", "#1f2937");
    caja(cx - 0.18, cy - 0.04, cx + 0.18, cy + 0.04, 0, 1.5, "#374151", "#1f2937", "#111827");
    caja(cx - 0.04, cy - 0.18, cx + 0.04, cy + 0.18, 0, 1.5, "#374151", "#1f2937", "#111827");
    caja(cx - 0.22, cy - 0.2, cx + 0.22, cy + 0.2, 9, 2.5, "#4b5563", "#374151", "#1f2937");
  }
  function respaldo(x, y, color) {
    const cx = x + 0.5, cy = y + 0.5;
    caja(cx - 0.17, cy + 0.2, cx + 0.17, cy + 0.27, 11, 9, aclarar(color, 0.55), aclarar(color, 0.45), aclarar(color, 0.35));
    caja(cx - 0.17, cy + 0.2, cx + 0.17, cy + 0.27, 19.5, 1, aclarar(color, 0.7), aclarar(color, 0.55), aclarar(color, 0.45));
  }

  function escritorioJefe(t, estado) {
    caja(10.05, 2.1, 12.95, 2.9, 0, 14, "#7a4b2a", "#5e391f", "#4f2f19");
    caja(10.05, 2.1, 12.95, 2.9, 13, 1.5, "#8f5a34", "#6b4225", "#5a371f");
    caja(10.2, 2.88, 12.8, 2.92, 2, 10, "#6b4225", "#4f2f19", "#4f2f19"); // panel frontal
    caja(11.2, 2.3, 11.8, 2.55, 14.5, 1, "#cbd5e1", "#94a3b8", "#64748b"); // laptop
    caja(11.2, 2.25, 11.8, 2.3, 15.5, 8, "#94a3b8", "#334155", "#1e293b");
    caja(10.3, 2.3, 10.7, 2.7, 14.5, 4, "#f1f5f9", "#cbd5e1", "#94a3b8"); // bandeja
    const pendientes = (estado.propuestas?.length || 0) + (estado.proyectos || []).filter((p) => p.estado === "revision").length;
    for (let i = 0; i < Math.min(pendientes, 6); i++) caja(10.35, 2.35, 10.65, 2.65, 15.5 + i * 1.4, 1.1, i % 2 ? "#fff" : "#fef9c3", "#e2e8f0", "#cbd5e1");
    caja(12.35, 2.35, 12.6, 2.6, 14.5, 6, "#fff", "#e5e7eb", "#d1d5db"); // taza
    caja(12.6, 2.2, 12.85, 2.45, 14.5, 3, "#fbbf24", "#d97706", "#b45309"); // trofeo
    caja(12.68, 2.28, 12.77, 2.37, 17.5, 4, "#fde047", "#eab308", "#ca8a04");
  }
  function sillaJefe() {
    caja(11.25, 1.15, 11.75, 1.25, 10, 26, "#1f2937", "#111827", "#0b0f19");
    caja(11.22, 1.3, 11.78, 1.8, 8, 3, "#334155", "#1f2937", "#111827");
  }

  function planta(x, y, grande = false) {
    caja(x + 0.3, y + 0.3, x + 0.7, y + 0.7, 0, 9, "#c2410c", "#9a3412", "#7c2d12");
    caja(x + 0.28, y + 0.28, x + 0.72, y + 0.72, 9, 1.5, "#ea580c", "#c2410c", "#9a3412");
    const [px, py] = iso(x + 0.5, y + 0.5, 10);
    const s = grande ? 1.3 : 1;
    g.fillStyle = "#166534";
    [[0, -14, 8], [-6, -8, 7], [6, -8, 7], [0, -3, 6], [-3, -18, 5]].forEach(([dx, dy, r]) => {
      g.beginPath(); g.arc(px + dx * K * s, py + dy * K * s, r * K * s, 0, Math.PI * 2); g.fill();
    });
    g.fillStyle = "#22c55e";
    [[-2, -16, 3], [-6, -10, 2.5], [4, -11, 3], [2, -5, 2]].forEach(([dx, dy, r]) => { g.beginPath(); g.arc(px + dx * K * s, py + dy * K * s, r * K * s, 0, Math.PI * 2); g.fill(); });
    g.fillStyle = "#86efac";
    [[-3, -18, 1], [3, -12, 1]].forEach(([dx, dy, r]) => { g.beginPath(); g.arc(px + dx * K * s, py + dy * K * s, r * K * s, 0, Math.PI * 2); g.fill(); });
  }

  function librero() {
    caja(0.05, 3.05, 0.45, 4.95, 0, 40, "#8b5e3c", "#6d4528", "#7a4f30");
    const colores = ["#ef4444", "#3b82f6", "#f59e0b", "#10b981", "#8b5cf6", "#ec4899"];
    for (let fila = 0; fila < 3; fila++) {
      caja(0.45, 3.1, 0.47, 4.9, 3 + fila * 12, 0.8, "#5c3b22", "#5c3b22", "#5c3b22");
      for (let i = 0; i < 7; i++) {
        const y0 = 3.15 + i * 0.25, z0 = 4 + fila * 12, alto = 8 + ((i + fila) % 3);
        caja(0.45, y0, 0.47, y0 + 0.18, z0, alto, colores[(i + fila) % 6], colores[(i + fila) % 6], aclarar(colores[(i + fila * 2) % 6], 0.8));
      }
    }
  }

  function cafetera(t, hayCafe) {
    caja(13.1, 5.1, 13.9, 5.9, 0, 13, "#9ca3af", "#6b7280", "#4b5563");
    caja(13.15, 5.15, 13.85, 5.85, 13, 17, "#374151", "#1f2937", "#111827");
    caja(13.15, 5.3, 13.18, 5.7, 18, 6, "#0ea5e9", "#0369a1", "#0369a1"); // pantallita
    const [lx, ly] = iso(13.2, 5.6, 26);
    g.fillStyle = Math.floor(t * 3) % 2 ? "#22c55e" : "#166534"; g.fillRect(Math.round(lx) - 2 * K, Math.round(ly), 2 * K, 2 * K);
    caja(13.3, 5.4, 13.5, 5.6, 13, 4, "#fff", "#e5e7eb", "#d1d5db"); // taza
    if (hayCafe) {
      g.fillStyle = "rgba(255,255,255,.6)";
      const [vx, vy] = iso(13.4, 5.5, 20);
      for (let i = 0; i < 4; i++) g.fillRect(Math.round(vx + Math.sin(t * 2 + i) * 2 * K), Math.round(vy - i * 5 * K - ((t * 12) % (5 * K))), 2 * K, 2 * K);
    }
  }

  function lampara(t) {
    caja(13.42, 6.42, 13.58, 6.58, 0, 2, "#374151", "#1f2937", "#111827");
    caja(13.48, 6.48, 13.52, 6.52, 2, 34, "#6b7280", "#4b5563", "#374151");
    caja(13.3, 6.3, 13.7, 6.7, 36, 8, "#fef3c7", "#fde68a", "#fcd34d");
  }

  function sillon() {
    caja(13.15, 7.0, 13.95, 9.95, 0, 7, "#4f46e5", "#3730a3", "#312e81");
    caja(13.7, 7.0, 13.95, 9.95, 7, 10, "#6366f1", "#4338ca", "#3730a3");
    caja(13.15, 7.0, 13.95, 7.25, 7, 5, "#6366f1", "#4338ca", "#3730a3");
    caja(13.15, 9.7, 13.95, 9.95, 7, 5, "#6366f1", "#4338ca", "#3730a3");
    caja(13.25, 7.4, 13.65, 7.9, 7, 4, "#f472b6", "#db2777", "#be185d"); // cojín
    caja(11.55, 7.9, 12.45, 8.6, 0, 6, "#a16207", "#854d0e", "#713f12");
    caja(11.8, 8.1, 12.05, 8.3, 6, 3, "#fff", "#e5e7eb", "#d1d5db");
    caja(12.1, 8.2, 12.35, 8.45, 6, 1, "#60a5fa", "#2563eb", "#1d4ed8"); // revista
  }

  // ---------- personajes ----------
  const PIEL = { productora: "#f2c6a0", investigador: "#d9a17a", guionista: "#8d5a3b", locutor: "#f5d0b0", disenadora: "#c68863",
                 editor: "#e8b48f", redactora: "#a86b4a", community: "#f0c09a", jefe: "#e0ac85" };
  const PELO = { productora: "#2b1a12", investigador: "#3b2a20", guionista: "#1a1110", locutor: "#c08a3e", disenadora: "#5a2d82",
                 editor: "#2a2a2a", redactora: "#6b2f1a", community: "#e2683c", jefe: "#1f1f1f" };
  const PANTALON = { productora: "#1f2937", investigador: "#2f3a56", guionista: "#3f3f46", locutor: "#2f3a56", disenadora: "#4b3a2a",
                     editor: "#2f3a56", redactora: "#3f3f46", community: "#2f3a56", jefe: "#1e293b" };
  const CONTORNO = "#1b1a26";

  // Dibuja un personaje con los pies en (fx, fy). o = {frente, paso, tecleando, sentado, libre, t}
  function personaje(c, a, fx, fy, o) {
    fx = Math.round(fx); fy = Math.round(fy);
    const t = o.t || 0;
    const piel = PIEL[a.id] || "#e0ac85", pelo = PELO[a.id] || "#222", ropa = a.color, pant = PANTALON[a.id] || "#2f3a56";
    const semilla = (a.id.charCodeAt(0) + a.id.length) % 7;
    if (!o.sinSombra) {
      c.fillStyle = "rgba(0,0,0,.22)";
      c.beginPath(); c.ellipse(fx, fy, 12, 5, 0, 0, Math.PI * 2); c.fill();
    }
    const cuadro = Math.floor(t * 8) % 2;
    const z = o.paso ? (cuadro ? 1 : -1) : 0;
    const respira = !o.paso && Math.floor(t * 1.3 + semilla) % 2 ? 1 : 0;
    const U = fy + (o.sentado ? 6 : 0) + (o.paso && cuadro ? -1 : 0) + respira;
    const contorno = [], detalle = [];
    const P = (x, y, w, h, color) => contorno.push([x, y, w, h, color]);
    const D = (x, y, w, h, color) => detalle.push([x, y, w, h, color]);

    if (!o.sentado) {
      P(fx - 7, fy - 20 + Math.max(0, z) * 2, 5, 16 - Math.max(0, z) * 2, pant);
      P(fx + 2, fy - 20 + Math.max(0, -z) * 2, 5, 16 - Math.max(0, -z) * 2, pant);
      P(fx - 8, fy - 4 - (z > 0 ? 2 : 0), 6, 4, "#2a2a35");
      P(fx + 2, fy - 4 - (z < 0 ? 2 : 0), 6, 4, "#2a2a35");
      D(fx - 8, fy - 4 - (z > 0 ? 2 : 0), 6, 1, "#4b4b5a"); D(fx + 2, fy - 4 - (z < 0 ? 2 : 0), 6, 1, "#4b4b5a");
      D(fx - 3, fy - 20, 1, 14, aclarar(pant, 0.7));
    }
    // brazos
    const s = o.paso ? z * 2 : 0;
    const ty = o.tecleando ? (Math.floor(t * 7) % 2 ? -2 : 0) : 0;
    const alza = o.tecleando ? -3 : 0;
    P(fx - 13, U - 37 + alza, 4, 14 + s, ropa);
    P(fx + 9, U - 37 + alza, 4, 14 - s, aclarar(ropa, 0.8));
    P(fx - 13, U - 23 + s + alza + ty, 4, 4, piel);
    P(fx + 9, U - 23 - s + alza - ty, 4, 4, piel);
    // torso
    P(fx - 9, U - 38, 18, 17, ropa);
    D(fx + 6, U - 38, 3, 17, aclarar(ropa, 0.78));
    D(fx - 9, U - 38, 2, 17, aclarar(ropa, 1.15));
    if (!o.sentado) D(fx - 9, U - 22, 18, 2, aclarar(pant, 0.7));
    if (o.frente) {
      D(fx - 4, U - 38, 8, 2, aclarar(ropa, 1.25));
      D(fx - 1, U - 38, 2, 3, piel);
      if (a.id === "jefe") { D(fx - 4, U - 38, 8, 2, "#f8fafc"); D(fx - 1, U - 36, 2, 10, "#b91c1c"); D(fx - 2, U - 36, 4, 2, "#991b1b"); }
      if (a.id === "productora") D(fx + 2, U - 33, 4, 5, "#fef3c7"); // gafete
      if (a.id === "investigador") { D(fx - 4, U - 37, 1, 8, "#1e293b"); D(fx - 5, U - 30, 3, 4, "#e2e8f0"); }
    }
    // cuello y cabeza
    P(fx - 3, U - 41, 6, 3, aclarar(piel, 0.85));
    P(fx - 8, U - 57, 16, 16, piel);
    D(fx + 5, U - 57, 3, 16, aclarar(piel, 0.9));
    P(fx - 10, U - 50, 2, 5, piel); P(fx + 8, U - 50, 2, 5, piel);

    const estilo = a.pelo;
    if (o.frente) {
      const parpadeo = Math.floor(t * 10 + semilla * 13) % 47 === 0;
      if (parpadeo) { D(fx - 6, U - 48, 4, 1, CONTORNO); D(fx + 2, U - 48, 4, 1, CONTORNO); }
      else {
        D(fx - 6, U - 50, 4, 4, "#fff"); D(fx + 2, U - 50, 4, 4, "#fff");
        const mira = o.mira || 0;
        D(fx - 5 + mira, U - 49, 2, 3, CONTORNO); D(fx + 3 + mira, U - 49, 2, 3, CONTORNO);
        D(fx - 5 + mira, U - 49, 1, 1, "#fff"); D(fx + 3 + mira, U - 49, 1, 1, "#fff");
      }
      D(fx - 6, U - 52, 4, 1, pelo); D(fx + 2, U - 52, 4, 1, pelo);
      D(fx - 1, U - 46, 2, 1, aclarar(piel, 0.8));
      if (o.libre) { D(fx - 3, U - 44, 6, 1, "#9f3a2f"); D(fx - 4, U - 45, 1, 1, "#9f3a2f"); D(fx + 3, U - 45, 1, 1, "#9f3a2f"); }
      else D(fx - 2, U - 44, 4, 1, "#9f3a2f");
      D(fx - 8, U - 46, 2, 1, "rgba(240,110,110,.55)"); D(fx + 6, U - 46, 2, 1, "rgba(240,110,110,.55)");
      P(fx - 9, U - 61, 18, 6, pelo);
      P(fx - 9, U - 55, 3, 4, pelo); P(fx + 6, U - 55, 3, 4, pelo);
      D(fx - 5, U - 60, 6, 1, aclarar(pelo, 1.35));
      if (estilo === "lentes") {
        const f = "#111827";
        for (const lx of [fx - 7, fx + 1]) { D(lx, U - 51, 6, 1, f); D(lx, U - 46, 6, 1, f); D(lx, U - 51, 1, 6, f); D(lx + 5, U - 51, 1, 6, f); }
        D(fx - 1, U - 50, 2, 1, f);
      }
    } else {
      P(fx - 9, U - 61, 18, 18, pelo);
      D(fx - 5, U - 60, 6, 1, aclarar(pelo, 1.35));
      D(fx - 9, U - 45, 18, 2, aclarar(pelo, 0.8));
    }
    if (estilo === "coleta") { if (o.frente) { P(fx + 9, U - 56, 3, 11, pelo); D(fx + 9, U - 56, 3, 2, "#e84d8a"); } else { P(fx - 2, U - 48, 4, 11, pelo); D(fx - 2, U - 48, 4, 2, "#e84d8a"); } }
    if (estilo === "rizos") { P(fx - 11, U - 63, 22, 8, pelo); P(fx - 11, U - 56, 3, 9, pelo); P(fx + 8, U - 56, 3, 9, pelo); D(fx - 8, U - 62, 3, 1, aclarar(pelo, 1.5)); D(fx + 3, U - 61, 3, 1, aclarar(pelo, 1.5)); if (!o.frente) P(fx - 11, U - 63, 22, 20, pelo); }
    if (estilo === "audifonos") { P(fx - 10, U - 64, 20, 2, "#1f2937"); P(fx - 12, U - 53, 4, 8, "#1f2937"); P(fx + 8, U - 53, 4, 8, "#1f2937"); D(fx - 12, U - 51, 4, 2, ropa); D(fx + 8, U - 51, 4, 2, ropa); }
    if (estilo === "chongo") { P(fx - 4, U - 67, 8, 6, pelo); D(fx - 4, U - 62, 8, 1, ropa); }
    if (estilo === "gorra") { P(fx - 9, U - 64, 18, 7, "#dc2626"); D(fx - 9, U - 64, 18, 1, "#f87171"); if (o.frente) P(fx - 9, U - 58, 21, 2, "#991b1b"); else D(fx - 3, U - 58, 6, 1, "#991b1b"); }
    if (estilo === "largo") { P(fx - 10, U - 56, 3, 22, pelo); P(fx + 7, U - 56, 3, 22, pelo); if (!o.frente) P(fx - 10, U - 61, 20, 27, pelo); }
    if (estilo === "bob") { P(fx - 10, U - 58, 3, 14, pelo); P(fx + 7, U - 58, 3, 14, pelo); if (!o.frente) P(fx - 10, U - 61, 20, 18, pelo); }

    c.fillStyle = CONTORNO;
    for (const [x, y, w, h] of contorno) c.fillRect(x - 1, y - 1, w + 2, h + 2);
    for (const [x, y, w, h, col] of contorno) { c.fillStyle = col; c.fillRect(x, y, w, h); }
    for (const [x, y, w, h, col] of detalle) { c.fillStyle = col; c.fillRect(x, y, w, h); }
  }

  // ---------- agentes en pantalla ----------
  const vivos = {};
  let estado = { agentes: {}, propuestas: [], proyectos: [], tareas: [] };
  let seleccionado = null, encima = null;

  function destinoDe(a) {
    if (a.ubicacion?.startsWith("visita:")) return VISITA[a.ubicacion.slice(7)] || CASA[a.id];
    return CASA[a.id];
  }

  function actualizar(nuevo) {
    const agentes = {};
    nuevo.agentes.forEach((a) => (agentes[a.id] = a));
    estado = { ...nuevo, agentes };
    for (const a of nuevo.agentes) {
      let v = vivos[a.id];
      if (!v) {
        const c = CASA[a.id];
        v = vivos[a.id] = { pos: [c[0] + 0.5, c[1] + 0.5], camino: [], meta: c, frente: a.id === "jefe", dice_t: a.dice_t,
                            globo: null, pasearEn: performance.now() + 8000 + Math.random() * 20000, dom: crearDom(a) };
      }
      const meta = destinoDe(a), clave = meta.join(",");
      if (v.claveServidor === undefined) v.claveServidor = clave;
      if (clave !== v.claveServidor) { v.claveServidor = clave; irA(v, meta); }
      if (a.dice && a.dice_t !== v.dice_t) { v.dice_t = a.dice_t; v.pendiente = a.dice; }
    }
  }

  function irA(v, meta) { v.meta = meta; v.camino = ruta(v.pos.map((n) => n - 0.5), meta); }
  const igual = (p, q) => p && q && p[0] === q[0] && p[1] === q[1];

  function crearDom(a) {
    const nombre = document.createElement("div");
    nombre.className = "nombre";
    nombre.style.setProperty("--c", a.color);
    nombre.innerHTML = `<i class="pto"></i><span></span><b class="barra-progreso" hidden><b></b></b>`;
    nombre.querySelector("span").textContent = a.id === "jefe" ? "Tú · Jefe" : a.nombre;
    const globo = document.createElement("div");
    globo.className = "globo"; globo.hidden = true;
    const icono = document.createElement("div");
    icono.className = "icono"; icono.hidden = true;
    capas.append(nombre, globo, icono);
    return { nombre, globo, icono };
  }

  const ICONO_TRABAJO = { productora: "📋", investigador: "🔎", guionista: "✍️", locutor: "🎙️", disenadora: "🎨",
                          editor: "🎬", redactora: "📝", community: "📤", jefe: "👔" };
  const DURACION = { ideas: 30, investigar: 90, guion: 60, voz: 45, miniatura: 8, video: 150, blog: 60, publicar: 60 };

  function tareasDe(id) { return (estado.tareas || []).filter((t) => t.agente === id); }

  // ---------- bucle ----------
  let ultimo = performance.now();
  function cuadro(ahora) {
    const dt = Math.min(0.1, (ahora - ultimo) / 1000);
    ultimo = ahora;
    const t = ahora / 1000;
    g.clearRect(0, 0, ANCHO, ALTO);
    piso(estado, t);
    muros(t, estado);

    const dibujos = [];
    const agrega = (prof, fn) => dibujos.push([prof, fn]);
    for (const [id, [x, y]] of Object.entries(ESCRITORIOS)) {
      agrega(x + y + 1, () => escritorio(id, x, y, t, estado));
      const [hx, hy] = CASA[id];
      agrega(hx + hy + 0.9, () => silla(hx, hy));
      agrega(hx + hy + 1.3, () => respaldo(hx, hy, estado.agentes[id]?.color || "#555"));
    }
    agrega(11 + 1 + 0.5, sillaJefe);
    agrega(11.5 + 2.5 + 0.2, () => escritorioJefe(t, estado));
    agrega(1, () => planta(0, 0)); agrega(14, () => planta(13, 0, true)); agrega(10, () => planta(0, 9, true));
    agrega(4.2, librero);
    const hayCafe = Object.values(vivos).some((v) => !v.camino.length && igual(v.meta, CAFE));
    agrega(19, () => cafetera(t, hayCafe));
    agrega(20, () => lampara(t));
    agrega(21.5, sillon);

    for (const [id, v] of Object.entries(vivos)) {
      const a = estado.agentes[id];
      if (!a) continue;
      let caminando = false;
      if (v.camino.length) {
        const [tx, ty] = [v.camino[0][0] + 0.5, v.camino[0][1] + 0.5];
        const dx = tx - v.pos[0], dy = ty - v.pos[1], dist = Math.hypot(dx, dy);
        const paso = VELOCIDAD * dt;
        v.frente = dx + dy > 0 || (dx + dy === 0 && dx > 0);
        if (dist <= paso) { v.pos = [tx, ty]; v.camino.shift(); } else v.pos = [v.pos[0] + dx / dist * paso, v.pos[1] + dy / dist * paso];
        caminando = true;
      } else {
        const enCasa = igual(v.meta, CASA[id]);
        v.frente = id === "jefe" ? true : !enCasa;
        if (igual(v.meta, VISITA.jefe)) v.frente = false;
      }
      if (id !== "jefe" && a.estado === "libre" && a.ubicacion === "casa" && !v.camino.length && ahora > v.pasearEn
          && !tareasDe(id).some((x) => x.estado === "en_cola")) {
        const enCasa = igual(v.meta, CASA[id]);
        irA(v, enCasa ? PASEOS[Math.floor(Math.random() * PASEOS.length)] : CASA[id]);
        v.pasearEn = ahora + (enCasa ? 6000 + Math.random() * 5000 : 25000 + Math.random() * 30000);
      }
      if (a.estado !== "libre" && !v.camino.length) {
        const m = destinoDe(a);
        if (!igual(m, v.meta)) irA(v, m);
      }
      if (v.pendiente && !v.camino.length) { v.globo = { texto: v.pendiente, hasta: ahora + 6500 }; v.pendiente = null; }
      const enSilla = !caminando && (igual(v.meta, CASA[id])) && id !== "jefe";
      const tecleando = a.estado === "trabajando" && enSilla;
      const [px, py] = iso(v.pos[0], v.pos[1]);
      v.pantalla = [px, py];
      v.sentado = enSilla || (id === "jefe" && !caminando);
      const marcado = id === seleccionado || id === encima;
      agrega(v.pos[0] + v.pos[1] + 0.01, () => {
        if (marcado) aro(px, py, a.color, id === seleccionado, t);
        personaje(g, a, px, py, { frente: v.frente, paso: caminando, tecleando, sentado: v.sentado, libre: a.estado === "libre", t });
      });
    }

    dibujos.sort((p, q) => p[0] - q[0]).forEach(([, fn]) => fn());

    if (esDeNoche()) { // ambiente de noche con luces cálidas
      g.save();
      g.globalCompositeOperation = "source-atop"; // solo oscurece lo dibujado, no el fondo
      g.fillStyle = "rgba(18,26,70,.28)";
      g.fillRect(0, 0, ANCHO, ALTO);
      g.globalCompositeOperation = "lighter";
      const [lx, ly] = iso(13.5, 6.5, 30);
      const gr = g.createRadialGradient(lx, ly, 4, lx, ly, 150);
      gr.addColorStop(0, "rgba(255,200,120,.35)"); gr.addColorStop(1, "rgba(255,200,120,0)");
      g.globalCompositeOperation = "source-atop";
      g.fillStyle = gr; g.fillRect(lx - 150, ly - 150, 300, 300);
      g.restore();
    }

    ctx.imageSmoothingEnabled = false;
    ctx.clearRect(0, 0, lienzo.width, lienzo.height);
    ctx.drawImage(buf, 0, 0, lienzo.width, lienzo.height);
    capasDom(ahora);
    requestAnimationFrame(cuadro);
  }

  function aro(px, py, color, fijo, t) {
    g.save();
    g.lineWidth = fijo ? 3 : 2;
    g.strokeStyle = fijo ? color : "rgba(255,255,255,.7)";
    g.globalAlpha = fijo ? 0.75 + Math.sin(t * 5) * 0.25 : 0.8;
    g.beginPath(); g.ellipse(px, py, 18, 9, 0, 0, Math.PI * 2); g.stroke();
    g.restore();
  }

  function capasDom(ahora) {
    const pendientes = (estado.propuestas?.length || 0) + (estado.proyectos || []).filter((p) => ["revision", "error"].includes(p.estado)).length;
    const relojServidor = (estado.ahora || Date.now() / 1000) + (Date.now() - (estado._recibido || Date.now())) / 1000;
    for (const [id, v] of Object.entries(vivos)) {
      if (!v.pantalla) continue;
      const a = estado.agentes[id];
      const [px, py] = v.pantalla;
      const x = px * escala, y = py * escala;
      const alto = (v.sentado ? 58 : 64) * escala;
      const { nombre, globo, icono } = v.dom;
      nombre.style.transform = `translate(${x}px, ${y + 8 * escala}px) translateX(-50%)`;
      nombre.classList.toggle("sel", id === seleccionado);
      // barra de progreso mientras trabaja
      const actual = tareasDe(id).find((tk) => tk.estado === "trabajando");
      const barra = nombre.querySelector(".barra-progreso");
      barra.hidden = !actual;
      if (actual) {
        const pasado = Math.max(0, relojServidor - (actual.inicio || relojServidor));
        const esperado = DURACION[actual.etapa] || 60;
        const avance = actual.avance != null ? actual.avance : 1 - Math.exp(-pasado / esperado * 1.6);
        barra.firstChild.style.width = `${Math.min(97, avance * 100)}%`;
      }
      nombre.querySelector(".pto").className = `pto ${a?.estado === "trabajando" ? "trab" : tareasDe(id).some((tk) => tk.estado === "en_cola") ? "cola" : ""}`;
      // globo
      const visible = v.globo && ahora < v.globo.hasta;
      if (visible) {
        if (globo.textContent !== v.globo.texto) globo.textContent = v.globo.texto;
        globo.style.transform = `translate(${x}px, ${y - alto - 6 * escala}px) translate(-50%, -100%)`;
      }
      globo.hidden = !visible;
      // ícono de estado
      let ico = "";
      const enCola = tareasDe(id).filter((tk) => tk.estado === "en_cola").length;
      if (id === "productora" && pendientes > 0) ico = "❗";
      else if (actual) ico = ICONO_TRABAJO[id];
      else if (enCola) ico = `⏳${enCola > 1 ? enCola : ""}`;
      else if (igual(v.meta, CAFE) && !v.camino.length) ico = "☕";
      else if (escala >= 0.75 && id !== "jefe" && a?.estado === "libre" && igual(v.meta, CASA[id]) && !v.camino.length) ico = "💤";
      icono.hidden = !ico || visible;
      if (!icono.hidden) {
        if (icono.textContent !== ico) icono.textContent = ico;
        icono.classList.toggle("alerta", ico === "❗");
        icono.style.transform = `translate(${x}px, ${y - alto - 2 * escala + Math.sin(ahora / 300 + px) * 2}px) translate(-50%, -100%)`;
      }
    }
  }

  function ajustar() {
    const dpr = window.devicePixelRatio || 1;
    const ancho = sala.clientWidth - 8;
    const alto = window.innerHeight - 140;
    escala = Math.max(0.3, Math.min(ancho / ANCHO, alto > 300 ? alto / ALTO : 9, 1.6));
    lienzo.style.width = `${ANCHO * escala}px`;
    lienzo.style.height = `${ALTO * escala}px`;
    lienzo.width = Math.round(ANCHO * escala * dpr);
    lienzo.height = Math.round(ALTO * escala * dpr);
    capas.style.width = lienzo.style.width;
    capas.style.height = lienzo.style.height;
    capas.style.setProperty("--tag", `${Math.max(9, Math.min(13, 11 * escala))}px`);
    capas.style.setProperty("--globo", `${Math.max(11, Math.min(13.5, 12.5 * escala))}px`);
  }
  window.addEventListener("resize", ajustar);
  ajustar();
  requestAnimationFrame(cuadro);

  function agenteEn(clientX, clientY) {
    const r = lienzo.getBoundingClientRect();
    const nx = (clientX - r.left) / escala, ny = (clientY - r.top) / escala;
    let mejor = null, distMejor = 1e9;
    for (const [id, v] of Object.entries(vivos)) {
      if (!v.pantalla) continue;
      const [px, py] = v.pantalla;
      if (nx > px - 16 && nx < px + 16 && ny > py - 68 && ny < py + 8) {
        const d = Math.hypot(nx - px, (ny - (py - 30)) / 2);
        if (d < distMejor) { mejor = id; distMejor = d; }
      }
    }
    return mejor;
  }

  // retrato para el panel del equipo
  function retrato(id, canvas) {
    const a = estado.agentes[id];
    if (!a) return;
    const c = canvas.getContext("2d");
    c.imageSmoothingEnabled = false;
    c.clearRect(0, 0, canvas.width, canvas.height);
    c.save();
    const f = canvas.width / 36;
    c.scale(f, f);
    personaje(c, a, 18, 74, { frente: true, libre: a.estado === "libre", t: performance.now() / 1000, sinSombra: true });
    c.restore();
  }

  window.Oficina = {
    actualizar: (n) => { n._recibido = Date.now(); actualizar(n); },
    agenteEn, retrato,
    escala: () => escala,
    posicion: (id) => vivos[id]?.pantalla,
    seleccionar: (id) => { seleccionado = id; },
    encima: (id) => { encima = id; },
  };
})();
