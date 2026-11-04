// Motor de la oficina isométrica en pixel art: sala, muebles, agentes caminando y globos de texto.
(() => {
  const COLS = 14, ROWS = 10, TW = 32, TH = 16, MURO = 74, PAD = 14;
  const ANCHO = (COLS + ROWS) * TW / 2 + PAD * 2;
  const ALTO = MURO + (COLS + ROWS) * TH / 2 + PAD * 2 + 12;
  const OX = ROWS * TW / 2 + PAD, OY = MURO + PAD + 6;
  const VELOCIDAD = 3.2; // casillas por segundo

  const iso = (x, y, z = 0) => [OX + (x - y) * TW / 2, OY + (x + y) * TH / 2 - z];

  // ---------- distribución de la oficina ----------
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
  const PASEOS = [[12, 5], [11, 7], [10, 4], [6, 3], [9, 8]]; // cafetera, sala, ventana…

  const bloqueado = new Set();
  const bloquear = (x, y) => bloqueado.add(`${x},${y}`);
  Object.values(ESCRITORIOS).forEach(([x, y]) => bloquear(x, y));
  [[10, 2], [11, 2], [12, 2], [11, 1], [13, 5], [13, 7], [13, 8], [13, 9], [12, 8], [0, 0], [13, 0], [0, 9],
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

  // ---------- dibujo ----------
  const lienzo = document.getElementById("lienzo");
  const capas = document.getElementById("capas");
  const sala = document.getElementById("sala");
  const buf = document.createElement("canvas");
  buf.width = ANCHO; buf.height = ALTO;
  const g = buf.getContext("2d");
  const ctx = lienzo.getContext("2d");
  let escala = 2;

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

  function piso() {
    for (let x = 0; x < COLS; x++) for (let y = 0; y < ROWS; y++) {
      const c = (x + y) % 2 ? "#d8b88f" : "#ceac81";
      poligono([iso(x, y), iso(x + 1, y), iso(x + 1, y + 1), iso(x, y + 1)], c, "rgba(120,80,40,.18)");
    }
    // tapete de la sala de descanso
    poligono([iso(10, 6.4), iso(13, 6.4), iso(13, 9.6), iso(10, 9.6)], "#5b6fd6");
    poligono([iso(10.25, 6.65), iso(12.75, 6.65), iso(12.75, 9.35), iso(10.25, 9.35)], "#6f82e8");
    // borde del piso (grosor)
    poligono([iso(0, ROWS), iso(COLS, ROWS), [iso(COLS, ROWS)[0], iso(COLS, ROWS)[1] + 6], [iso(0, ROWS)[0], iso(0, ROWS)[1] + 6]], "#8f6a44");
    poligono([iso(COLS, 0), iso(COLS, ROWS), [iso(COLS, ROWS)[0], iso(COLS, ROWS)[1] + 6], [iso(COLS, 0)[0], iso(COLS, 0)[1] + 6]], "#7a5838");
  }

  const muroD = (x, h) => iso(x, 0, h);   // muro del fondo derecho (a lo largo de x)
  const muroI = (y, h) => iso(0, y, h);   // muro del fondo izquierdo (a lo largo de y)

  function muros(t, estado) {
    poligono([muroI(0, 0), muroI(ROWS, 0), muroI(ROWS, MURO), muroI(0, MURO)], "#e6d7bd");
    poligono([muroD(0, 0), muroD(COLS, 0), muroD(COLS, MURO), muroD(0, MURO)], "#f1e6d2");
    // zoclo y moldura
    poligono([muroI(0, 0), muroI(ROWS, 0), muroI(ROWS, 4), muroI(0, 4)], "#b89b74");
    poligono([muroD(0, 0), muroD(COLS, 0), muroD(COLS, 4), muroD(0, 4)], "#c7aa82");
    poligono([muroI(0, MURO - 3), muroI(ROWS, MURO - 3), muroI(ROWS, MURO), muroI(0, MURO)], "#9c7f5a");
    poligono([muroD(0, MURO - 3), muroD(COLS, MURO - 3), muroD(COLS, MURO), muroD(0, MURO)], "#a88a63");
    // ventanas con cielo que cambia con la hora
    const hora = new Date().getHours();
    const cielo = hora >= 19 || hora < 6 ? ["#1d2a5a", "#3a4a8a"] : hora >= 17 ? ["#f59e6b", "#fcd5a5"] : ["#7cc4f2", "#c9ecff"];
    for (const [a, b] of [[1.6, 3.4], [9.4, 10.6]]) {
      poligono([muroD(a, 26), muroD(b, 26), muroD(b, 62), muroD(a, 62)], cielo[0]);
      poligono([muroD(a, 26), muroD(b, 26), muroD(b, 42), muroD(a, 42)], cielo[1]);
      poligono([muroD(a, 24), muroD(b, 24), muroD(b, 26), muroD(a, 26)], "#fff");
      const m = (a + b) / 2;
      poligono([muroD(m - 0.04, 26), muroD(m + 0.04, 26), muroD(m + 0.04, 62), muroD(m - 0.04, 62)], "#fff");
      poligono([muroD(a, 43), muroD(b, 43), muroD(b, 45), muroD(a, 45)], "#fff");
    }
    // póster del canal (botón de play)
    poligono([muroD(6.6, 30), muroD(7.9, 30), muroD(7.9, 60), muroD(6.6, 60)], "#e53935", "#7f1d1d");
    poligono([muroD(7.05, 37), muroD(7.55, 45), muroD(7.05, 53)], "#fff");
    // luz "AL AIRE" del locutor
    const alAire = estado.agentes.locutor?.estado === "trabajando";
    poligono([muroD(4.75, 50), muroD(5.5, 50), muroD(5.5, 58), muroD(4.75, 58)], alAire && Math.floor(t * 2) % 2 ? "#ff3b30" : "#5a2020", "#2a0d0d");
    // reloj
    const [cx, cy] = muroD(12.3, 52);
    g.fillStyle = "#fff"; g.beginPath(); g.ellipse(cx, cy, 6, 7, 0, 0, Math.PI * 2); g.fill();
    g.strokeStyle = "#333"; g.stroke();
    const d = new Date(), am = (d.getMinutes() / 60) * Math.PI * 2, ah = ((d.getHours() % 12) / 12) * Math.PI * 2 + am / 12;
    g.beginPath(); g.moveTo(cx, cy); g.lineTo(cx + Math.sin(am) * 5, cy - Math.cos(am) * 5);
    g.moveTo(cx, cy); g.lineTo(cx + Math.sin(ah) * 3, cy - Math.cos(ah) * 3); g.stroke();
    // pizarrón con notas (muro izquierdo)
    poligono([muroI(5.2, 22), muroI(8.8, 22), muroI(8.8, 60), muroI(5.2, 60)], "#fbfbf7", "#8a8a8a");
    const notas = ["#fde047", "#f9a8d4", "#86efac", "#93c5fd", "#fdba74", "#c4b5fd"];
    notas.forEach((c, i) => {
      const y0 = 5.5 + (i % 3) * 1.1, z0 = 30 + Math.floor(i / 3) * 14;
      poligono([muroI(y0, z0), muroI(y0 + 0.7, z0), muroI(y0 + 0.7, z0 + 10), muroI(y0, z0 + 10)], c);
    });
  }

  // ---------- muebles ----------
  function escritorio(id, x, y, t, estado) {
    caja(x + 0.08, y + 0.12, x + 0.92, y + 0.88, 0, 12, "#c8915a", "#9c6b3e", "#875a32");
    const a = estado.agentes[id];
    const trabajando = a?.estado === "trabajando" && a?.ubicacion === "casa";
    // monitor: la cara frontal es la pantalla
    caja(x + 0.28, y + 0.3, x + 0.72, y + 0.4, 12, 10, "#2b2b3a", trabajando ? colorPantalla(id, t) : "#25344f", "#1c1c28");
    if (trabajando) { // líneas de código/texto en la pantalla
      for (let i = 0; i < 3; i++) {
        const w = 0.08 + ((Math.sin(t * 3 + i * 2 + x) + 1) / 2) * 0.22;
        poligono([iso(x + 0.32, y + 0.4, 19 - i * 3), iso(x + 0.32 + w, y + 0.4, 19 - i * 3),
                  iso(x + 0.32 + w, y + 0.4, 18 - i * 3), iso(x + 0.32, y + 0.4, 18 - i * 3)], "rgba(255,255,255,.75)");
      }
    }
    caja(x + 0.3, y + 0.55, x + 0.7, y + 0.7, 12, 1.2, "#e5e7eb", "#9ca3af", "#9ca3af"); // teclado
    if (id === "locutor") { // micrófono
      caja(x + 0.78, y + 0.5, x + 0.84, y + 0.56, 12, 9, "#333", "#222", "#111");
      const [mx, my] = iso(x + 0.81, y + 0.53, 23);
      g.fillStyle = "#555"; g.fillRect(Math.round(mx) - 2, Math.round(my) - 3, 4, 5);
    }
    if (id === "productora") caja(x + 0.1, y + 0.2, x + 0.25, y + 0.35, 12, 5, "#fef08a", "#eab308", "#ca8a04"); // post-its
    if (id === "disenadora") caja(x + 0.74, y + 0.55, x + 0.9, y + 0.8, 12, 1, "#f472b6", "#be185d", "#9d174d"); // tableta
  }

  const PANTALLA = { investigador: "#1e3a8a", guionista: "#78350f", locutor: "#4c1d95", productora: "#831843",
                     disenadora: "#065f46", editor: "#7f1d1d", redactora: "#155e75", community: "#7c2d12" };
  const colorPantalla = (id, t) => (Math.floor(t * 4) % 7 ? PANTALLA[id] : "#475569");

  function escritorioJefe(t, estado) {
    caja(10.05, 2.1, 12.95, 2.9, 0, 14, "#8a5530", "#6b3f20", "#5a3418");
    caja(11.2, 2.3, 11.8, 2.55, 14, 1, "#cbd5e1", "#94a3b8", "#64748b"); // laptop
    caja(11.2, 2.25, 11.8, 2.3, 15, 8, "#94a3b8", "#334155", "#1e293b");
    caja(10.3, 2.3, 10.7, 2.7, 14, 4, "#f1f5f9", "#cbd5e1", "#94a3b8"); // bandeja de entrada
    const pendientes = (estado.propuestas?.length || 0) + (estado.proyectos || []).filter((p) => p.estado === "revision").length;
    for (let i = 0; i < Math.min(pendientes, 5); i++) caja(10.35, 2.35, 10.65, 2.65, 15 + i * 1.5, 1.2, "#fff", "#e2e8f0", "#cbd5e1");
    caja(12.35, 2.35, 12.6, 2.6, 14, 6, "#fff", "#e5e7eb", "#d1d5db"); // taza
  }

  function planta(x, y) {
    caja(x + 0.3, y + 0.3, x + 0.7, y + 0.7, 0, 8, "#b45309", "#92400e", "#78350f");
    const [px, py] = iso(x + 0.5, y + 0.5, 8);
    g.fillStyle = "#15803d";
    [[0, -14, 7], [-5, -8, 6], [5, -8, 6], [0, -4, 6]].forEach(([dx, dy, r]) => {
      g.beginPath(); g.arc(px + dx, py + dy, r, 0, Math.PI * 2); g.fill();
    });
    g.fillStyle = "#22c55e";
    [[-2, -16, 3], [-6, -10, 2], [4, -10, 3]].forEach(([dx, dy, r]) => { g.beginPath(); g.arc(px + dx, py + dy, r, 0, Math.PI * 2); g.fill(); });
  }

  function librero() {
    caja(0.05, 3.05, 0.45, 4.95, 0, 40, "#8b5e3c", "#6d4528", "#7a4f30");
    const colores = ["#ef4444", "#3b82f6", "#f59e0b", "#10b981", "#8b5cf6", "#ec4899"];
    for (let fila = 0; fila < 3; fila++) for (let i = 0; i < 7; i++) {
      const y0 = 3.15 + i * 0.25, z0 = 4 + fila * 12;
      caja(0.45, y0, 0.47, y0 + 0.18, z0, 9, colores[(i + fila) % 6], colores[(i + fila) % 6], colores[(i + fila * 2) % 6]);
    }
  }

  function cafetera(t, hayCafe) {
    caja(13.15, 5.15, 13.85, 5.85, 0, 13, "#9ca3af", "#6b7280", "#4b5563");
    caja(13.2, 5.2, 13.8, 5.8, 13, 16, "#374151", "#1f2937", "#111827");
    const [lx, ly] = iso(13.2, 5.6, 24);
    g.fillStyle = Math.floor(t * 3) % 2 ? "#22c55e" : "#166534"; g.fillRect(Math.round(lx) - 2, Math.round(ly), 2, 2);
    if (hayCafe) { // vapor
      g.fillStyle = "rgba(255,255,255,.6)";
      const [vx, vy] = iso(13.5, 5.5, 32);
      for (let i = 0; i < 3; i++) g.fillRect(Math.round(vx + Math.sin(t * 2 + i) * 2), Math.round(vy - i * 4 - (t * 6) % 4), 2, 2);
    }
  }

  function sillon() {
    caja(13.15, 7.0, 13.95, 9.95, 0, 7, "#4f46e5", "#3730a3", "#312e81");
    caja(13.7, 7.0, 13.95, 9.95, 7, 10, "#6366f1", "#4338ca", "#3730a3");
    caja(13.15, 7.0, 13.95, 7.25, 7, 5, "#6366f1", "#4338ca", "#3730a3");
    caja(13.15, 9.7, 13.95, 9.95, 7, 5, "#6366f1", "#4338ca", "#3730a3");
    caja(11.55, 7.9, 12.45, 8.6, 0, 6, "#a16207", "#854d0e", "#713f12"); // mesita
    caja(11.8, 8.1, 12.05, 8.3, 6, 3, "#fff", "#e5e7eb", "#d1d5db");
  }

  // ---------- avatares ----------
  const PIEL = { productora: "#f2c6a0", investigador: "#d9a17a", guionista: "#8d5a3b", locutor: "#f5d0b0", disenadora: "#c68863",
                 editor: "#e8b48f", redactora: "#a86b4a", community: "#f0c09a", jefe: "#e0ac85" };
  const PELO = { productora: "#2b1a12", investigador: "#3b2a20", guionista: "#1a1110", locutor: "#c08a3e", disenadora: "#5a2d82",
                 editor: "#2a2a2a", redactora: "#6b2f1a", community: "#e2683c", jefe: "#1f1f1f" };
  const PANTALON = "#2f3a56";
  const CONTORNO = "#1b1a26";

  function oscurecer(hex, f = 0.75) {
    const n = parseInt(hex.slice(1), 16);
    const c = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map((v) => Math.round(v * f));
    return `rgb(${c.join(",")})`;
  }

  function avatar(a, fx, fy, frente, paso, tecleando, t) {
    fx = Math.round(fx); fy = Math.round(fy);
    g.fillStyle = "rgba(0,0,0,.22)";
    g.beginPath(); g.ellipse(fx, fy, 6, 2.5, 0, 0, Math.PI * 2); g.fill();
    const piel = PIEL[a.id] || "#e0ac85", pelo = PELO[a.id] || "#222", ropa = a.color;
    const p = []; // [x, y, w, h, color]
    const zancada = paso ? (Math.floor(t * 8) % 2 ? 1 : -1) : 0;
    p.push([fx - 3, fy - 7 + Math.max(0, zancada), 2, 7 - Math.max(0, zancada), PANTALON]);
    p.push([fx + 1, fy - 7 + Math.max(0, -zancada), 2, 7 - Math.max(0, -zancada), PANTALON]);
    p.push([fx - 3, fy - 1, 2, 1, "#111"], [fx + 1, fy - 1, 2, 1, "#111"]);
    p.push([fx - 4, fy - 15, 8, 9, ropa], [fx + 3, fy - 15, 1, 9, oscurecer(ropa)]);
    const brazoY = tecleando ? (Math.floor(t * 6) % 2 ? -1 : 0) : 0;
    const balanceo = paso ? zancada : 0;
    p.push([fx - 6, fy - 15 + (tecleando ? -1 : 0), 2, 7 + brazoY + balanceo, ropa]);
    p.push([fx + 4, fy - 15 + (tecleando ? -1 : 0), 2, 7 - brazoY - balanceo, oscurecer(ropa)]);
    if (frente) p.push([fx - 6, fy - 8 + brazoY + balanceo, 2, 2, piel], [fx + 4, fy - 8 - brazoY - balanceo, 2, 2, piel]);
    p.push([fx - 4, fy - 23, 8, 8, piel]);
    // peinados
    const estilo = a.pelo;
    if (frente) {
      p.push([fx - 4, fy - 24, 8, 3, pelo], [fx - 4, fy - 21, 1, 2, pelo], [fx + 3, fy - 21, 1, 2, pelo]);
    } else {
      p.push([fx - 4, fy - 24, 8, 8, pelo]);
    }
    if (estilo === "coleta") p.push([fx + 4, fy - 22, 2, 6, pelo]);
    if (estilo === "rizos") p.push([fx - 5, fy - 25, 10, 3, pelo], [fx - 5, fy - 22, 1, 3, pelo], [fx + 4, fy - 22, 1, 3, pelo]);
    if (estilo === "chongo") p.push([fx - 2, fy - 27, 4, 3, pelo]);
    if (estilo === "largo") p.push([fx - 5, fy - 22, 1, 8, pelo], [fx + 4, fy - 22, 1, 8, pelo]);
    if (estilo === "bob") p.push([fx - 5, fy - 23, 1, 5, pelo], [fx + 4, fy - 23, 1, 5, pelo]);
    if (estilo === "gorra") p.push([fx - 4, fy - 25, 8, 3, "#dc2626"], frente ? [fx - 4, fy - 22, 10, 1, "#991b1b"] : [fx - 4, fy - 22, 8, 1, "#991b1b"]);
    if (estilo === "audifonos") p.push([fx - 5, fy - 25, 10, 1, "#111"], [fx - 6, fy - 21, 2, 4, "#111"], [fx + 4, fy - 21, 2, 4, "#111"]);
    if (estilo === "corto" && a.id === "jefe") p.push([fx - 2, fy - 15, 4, 1, "#fff"], [fx - 1, fy - 14, 2, 4, "#b91c1c"]); // corbata
    // contorno primero, luego relleno
    g.fillStyle = CONTORNO;
    for (const [x, y, w, h] of p) g.fillRect(x - 1, y - 1, w + 2, h + 2);
    for (const [x, y, w, h, c] of p) { g.fillStyle = c; g.fillRect(x, y, w, h); }
    if (frente) {
      const parpadeo = Math.floor(t * 10 + fx) % 40 === 0;
      g.fillStyle = "#1b1a26";
      g.fillRect(fx - 2, fy - 19, 1, parpadeo ? 1 : 2); g.fillRect(fx + 1, fy - 19, 1, parpadeo ? 1 : 2);
      if (estilo === "lentes") { g.fillRect(fx - 3, fy - 20, 3, 1); g.fillRect(fx + 0, fy - 20, 3, 1); }
      g.fillStyle = "rgba(240,110,110,.55)"; g.fillRect(fx - 3, fy - 17, 1, 1); g.fillRect(fx + 2, fy - 17, 1, 1);
    }
  }

  // ---------- estado de los agentes en pantalla ----------
  const vivos = {}; // id -> {pos, camino, destino, frente, globo...}
  let estado = { agentes: {}, propuestas: [], proyectos: [] };

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
      if (clave !== v.claveServidor) { v.claveServidor = clave; irA(v, meta); } // solo si el servidor lo mandó a otro lado
      if (a.dice && a.dice_t !== v.dice_t) {
        v.dice_t = a.dice_t;
        v.pendiente = a.dice; // se muestra cuando llega a su destino
      }
    }
  }

  function irA(v, meta) {
    v.meta = meta;
    v.camino = ruta(v.pos.map((n) => n - 0.5), meta);
  }

  function crearDom(a) {
    const nombre = document.createElement("div");
    nombre.className = "nombre";
    nombre.textContent = a.id === "jefe" ? "Tú · Jefe" : a.nombre;
    nombre.style.setProperty("--c", a.color);
    const globo = document.createElement("div");
    globo.className = "globo";
    globo.hidden = true;
    const alerta = document.createElement("div");
    alerta.className = "alerta";
    alerta.textContent = "!";
    alerta.hidden = true;
    capas.append(nombre, globo, alerta);
    return { nombre, globo, alerta };
  }

  // ---------- bucle principal ----------
  let ultimo = performance.now();
  function cuadro(ahora) {
    const dt = Math.min(0.1, (ahora - ultimo) / 1000);
    ultimo = ahora;
    const t = ahora / 1000;
    g.clearRect(0, 0, ANCHO, ALTO);
    piso();
    muros(t, estado);

    const dibujos = [];
    const agrega = (prof, fn) => dibujos.push([prof, fn]);
    for (const [id, [x, y]] of Object.entries(ESCRITORIOS)) agrega(x + y + 1, () => escritorio(id, x, y, t, estado));
    agrega(11.5 + 2.5 + 0.2, () => escritorioJefe(t, estado));
    agrega(1, () => planta(0, 0)); agrega(14, () => planta(13, 0)); agrega(10, () => planta(0, 9));
    agrega(4.2, librero);
    const hayCafe = Object.values(vivos).some((v) => !v.camino.length && v.meta[0] === 12 && v.meta[1] === 5);
    agrega(19, () => cafetera(t, hayCafe));
    agrega(21.5, sillon);

    for (const [id, v] of Object.entries(vivos)) {
      const a = estado.agentes[id];
      if (!a) continue;
      // caminar
      let caminando = false;
      if (v.camino.length) {
        const [tx, ty] = [v.camino[0][0] + 0.5, v.camino[0][1] + 0.5];
        const dx = tx - v.pos[0], dy = ty - v.pos[1], dist = Math.hypot(dx, dy);
        const paso = VELOCIDAD * dt;
        v.frente = dx + dy > 0 || (dx + dy === 0 && dx > 0);
        if (dist <= paso) { v.pos = [tx, ty]; v.camino.shift(); } else { v.pos = [v.pos[0] + dx / dist * paso, v.pos[1] + dy / dist * paso]; }
        caminando = true;
      } else {
        // orientación en reposo: de espaldas en su escritorio, de frente el jefe o de visita
        const enCasa = v.meta === CASA[id];
        v.frente = id === "jefe" ? true : !enCasa;
        if (v.meta[0] === 11 && v.meta[1] === 3) v.frente = false; // frente al jefe, de espaldas a la cámara
      }
      // paseos al café cuando están libres
      if (id !== "jefe" && a.estado === "libre" && a.ubicacion === "casa" && !v.camino.length && ahora > v.pasearEn) {
        const enCasa = v.meta === CASA[id] || (v.meta[0] === CASA[id][0] && v.meta[1] === CASA[id][1]);
        if (enCasa) irA(v, PASEOS[Math.floor(Math.random() * PASEOS.length)]);
        else irA(v, CASA[id]);
        v.pasearEn = ahora + (enCasa ? 6000 + Math.random() * 4000 : 25000 + Math.random() * 30000);
      }
      if (a.estado !== "libre" && !v.camino.length) {
        const m = destinoDe(a);
        if (m[0] !== v.meta[0] || m[1] !== v.meta[1]) irA(v, m);
      }
      // globo de texto: aparece al llegar
      if (v.pendiente && !v.camino.length) { v.globo = { texto: v.pendiente, hasta: ahora + 6500 }; v.pendiente = null; }
      const tecleando = a.estado === "trabajando" && !caminando && a.ubicacion === "casa";
      const [px, py] = iso(v.pos[0], v.pos[1]);
      agrega(v.pos[0] + v.pos[1] + (id === "jefe" ? 0 : 0.01), () => avatar(a, px, py, v.frente, caminando, tecleando, t));
      v.pantalla = [px, py];
    }

    dibujos.sort((a, b) => a[0] - b[0]).forEach(([, fn]) => fn());

    // pasar al lienzo visible sin suavizado (pixeles nítidos)
    ctx.imageSmoothingEnabled = false;
    ctx.clearRect(0, 0, lienzo.width, lienzo.height);
    ctx.drawImage(buf, 0, 0, lienzo.width, lienzo.height);
    capasDom(ahora);
    requestAnimationFrame(cuadro);
  }

  function capasDom(ahora) {
    const pendientes = (estado.propuestas?.length || 0) + (estado.proyectos || []).filter((p) => ["revision", "error"].includes(p.estado)).length;
    for (const [id, v] of Object.entries(vivos)) {
      if (!v.pantalla) continue;
      const [px, py] = v.pantalla;
      const x = px * escala, y = py * escala;
      const { nombre, globo, alerta } = v.dom;
      nombre.style.transform = `translate(${x}px, ${y + 4 * escala}px) translateX(-50%)`;
      const visible = v.globo && ahora < v.globo.hasta;
      if (visible) {
        if (globo.textContent !== v.globo.texto) globo.textContent = v.globo.texto;
        globo.style.transform = `translate(${x}px, ${y - 30 * escala}px) translate(-50%, -100%)`;
      }
      globo.hidden = !visible;
      const conAlerta = id === "productora" && pendientes > 0 && !visible;
      alerta.hidden = !conAlerta;
      if (conAlerta) alerta.style.transform = `translate(${x}px, ${y - 32 * escala + Math.sin(ahora / 200) * 3}px) translate(-50%, -100%)`;
    }
  }

  function ajustar() {
    const dpr = window.devicePixelRatio || 1;
    const ancho = sala.clientWidth;
    const ajuste = ancho / ANCHO;
    // pixeles enteros cuando cabe a 1x o más; en pantallas chicas se ajusta al ancho
    escala = ajuste >= 1 ? Math.floor(ajuste * dpr) / dpr : ajuste;
    lienzo.style.width = `${ANCHO * escala}px`;
    lienzo.style.height = `${ALTO * escala}px`;
    lienzo.width = Math.round(ANCHO * escala * dpr);
    lienzo.height = Math.round(ALTO * escala * dpr);
    capas.style.width = lienzo.style.width;
    capas.style.height = lienzo.style.height;
    capas.style.setProperty("--tag", `${Math.max(8, Math.min(13, 5.5 * escala))}px`);
    capas.style.setProperty("--globo", `${Math.max(11, Math.min(13, 6.2 * escala))}px`);
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
      if (nx > px - 8 && nx < px + 8 && ny > py - 28 && ny < py + 3) {
        const d = Math.abs(ny - (py - 12));
        if (d < distMejor) { mejor = id; distMejor = d; }
      }
    }
    return mejor;
  }

  window.Oficina = { actualizar, agenteEn, escala: () => escala, posicion: (id) => vivos[id]?.pantalla };
})();
