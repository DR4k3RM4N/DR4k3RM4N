// Motor de la oficina isométrica en pixel art: sala, muebles, agentes, selección y globos de texto.
(() => {
  const K = 2; // densidad: cada "pixel" de diseño de muebles mide K pixeles reales; los personajes usan el detalle completo
  // El edificio: ala de YouTube (x 0–13), pasillo con el despacho del jefe (x 14–16) y ala de TikTok Shop (x 17–30).
  // Abajo (filas 10–14) el patio de descanso que comparten los dos equipos.
  const COLS = 31, OFI = 10, ROWS = 15, TW = 32 * K, TH = 16 * K, MURO = 74, PAD = 16 * K;
  const ALA_TT = 17, PASILLO = 14; // primera columna de cada zona
  const MAMPARAS = [PASILLO, ALA_TT]; // muros de vidrio entre zonas (sobre la línea x = …)
  const PUERTAS = new Set([6, 7]); // filas donde las mamparas tienen puerta
  const ANCHO = (COLS + ROWS) * TW / 2 + PAD * 2;
  const ALTO = MURO * K + (COLS + ROWS) * TH / 2 + PAD * 2 + 14 * K;
  const OX = ROWS * TW / 2 + PAD, OY = MURO * K + PAD + 8 * K;
  const VELOCIDAD = 3.2; // casillas por segundo

  const iso = (x, y, z = 0) => [OX + (x - y) * TW / 2, OY + (x + y) * TH / 2 - z * K];
  const esTT = (id) => id.startsWith("tt_");

  // ---------- el equipo de TikTok Shop (su oficina se conecta en el siguiente paso) ----------
  const EQUIPO_TT = [
    // id, nombre, rol, color de ropa, peinado, qué hace
    ["tt_cazador", "Toño", "Cazador de productos", "#0ea5e9", "corto", "Busca productos que se están vendiendo en México: precio, comisión y reseñas reales."],
    ["tt_guionista", "Sofi", "Guionista de Shop", "#f43f5e", "largo", "Escribe guiones que venden: 3 ganchos, cuerpo, caption, hashtags y comentario fijado."],
    ["tt_director", "Diego", "Director de grabación", "#a3e635", "rizos", "Te arma la lista de tomas para grabar el producto con tu celular."],
    ["tt_editor", "Cris", "Editor vertical", "#f97316", "copete", "Edita tus clips en vertical: cortes rápidos, subtítulos karaoke y efectos."],
    ["tt_disenadora", "Vale", "Diseñadora de portadas", "#d946ef", "bob", "Hace la portada del video para que se vea chida en tu perfil."],
    ["tt_analista", "Ana", "Analista de ventas", "#22c55e", "chongo", "Lee lo que vendió cada video y le dice al equipo qué repetir."],
  ];
  const SALUDOS_TT = { tt_editor: "¡Ya llegué! Lentes listos 🤓", tt_guionista: "¿Y nuestros productos, jefe?",
                       tt_cazador: "Ya ando viendo qué se vende…", tt_director: "Luces, cámara… ¿celular?" };

  // ---------- distribución ----------
  const ESCRITORIOS = {
    investigador: [1, 1], guionista: [3, 1], locutor: [5, 1], productora: [8, 1],
    disenadora: [2, 5], editor: [4, 5], redactora: [6, 5], community: [8, 5],
    tt_cazador: [18, 1], tt_guionista: [20, 1], tt_director: [22, 1],
    tt_editor: [19, 5], tt_disenadora: [21, 5], tt_analista: [23, 5],
  };
  const CASA = { jefe: [15, 1] };
  const VISITA = { jefe: [15, 3] };
  for (const [id, [x, y]] of Object.entries(ESCRITORIOS)) {
    CASA[id] = [x, y + 1];
    VISITA[id] = [x + 1, y + 1];
  }
  const CAFE = [12, 5], CAFE_TT = [29, 5];
  const esCafe = (p) => igual(p, CAFE) || igual(p, CAFE_TT);
  const PASEOS = [CAFE, [11, 7], [10, 4], [6, 3], [9, 8], [12, 7]];
  const PASEOS_TT = [CAFE_TT, [28, 7], [25, 6], [24, 3], [26, 8], [29, 7]];
  // patio de descanso (filas 10 a 14), compartido: cada lugar con su actividad
  const ACTIVIDADES = [
    { id: "ping_a", pos: [1, 12], icono: "🏓", frente: true, mano: true },
    { id: "ping_b", pos: [4, 12], icono: "🏓", frente: false, mano: true },
    { id: "arcade", pos: [1, 11], icono: "🎮", frente: false, mano: true },
    { id: "puf_1", pos: [9, 12], icono: "📱", frente: true, sentado: true, puf: "#f472b6" },
    { id: "puf_2", pos: [10, 13], icono: "📱", frente: true, sentado: true, puf: "#60a5fa" },
    { id: "camastro_1", pos: [12, 11], icono: "💤", frente: true, sentado: true, camastro: true },
    { id: "camastro_2", pos: [12, 13], icono: "💤", frente: true, sentado: true, camastro: true },
    { id: "mesa_1", pos: [5, 13], icono: "☕", frente: true, sentado: true, silla: true },
    { id: "mesa_2", pos: [7, 13], icono: "☕", frente: true, sentado: true, silla: true },
    { id: "fuente", pos: [12, 14], icono: "🌿", frente: false },
    { id: "futbol_a", pos: [18, 12], icono: "⚽", frente: true, mano: true },
    { id: "futbol_b", pos: [21, 12], icono: "⚽", frente: false, mano: true },
    { id: "mesa_3", pos: [22, 13], icono: "🌮", frente: true, sentado: true, silla: true },
    { id: "mesa_4", pos: [24, 13], icono: "🥤", frente: true, sentado: true, silla: true },
    { id: "puf_3", pos: [26, 12], icono: "📱", frente: true, sentado: true, puf: "#facc15" },
    { id: "puf_4", pos: [27, 13], icono: "🎧", frente: true, sentado: true, puf: "#a78bfa" },
    { id: "camastro_3", pos: [29, 11], icono: "💤", frente: true, sentado: true, camastro: true },
    { id: "camastro_4", pos: [29, 13], icono: "😎", frente: true, sentado: true, camastro: true },
  ];
  const actividadEn = (p) => ACTIVIDADES.find((x) => igual(x.pos, p));

  const bloqueado = new Set();
  const bloquear = (x, y) => bloqueado.add(`${x},${y}`);
  Object.values(ESCRITORIOS).forEach(([x, y]) => bloquear(x, y));
  // ala YouTube: plantas, librero, garrafón y la esquina de descanso
  [[13, 5], [13, 6], [13, 7], [13, 8], [13, 9], [12, 8], [0, 0], [13, 0], [12, 0], [0, 9], [0, 3], [0, 4]].forEach(([x, y]) => bloquear(x, y));
  // despacho del jefe y sala de juntas en el pasillo
  [[14, 2], [15, 2], [16, 2], [15, 1], [14, 0], [16, 0], [15, 5], [15, 6], [15, 7], [15, 8], [14, 9], [16, 9]].forEach(([x, y]) => bloquear(x, y));
  // ala TikTok: estudio de grabación, esquina de descanso y plantas
  [[27, 2], [28, 2], [29, 3], [27, 4], [24, 0], [25, 0], [30, 5], [30, 6], [30, 7], [30, 8], [30, 9], [29, 8], [30, 0], [17, 9]]
    .forEach(([x, y]) => bloquear(x, y));
  // jardineras entre el edificio y el patio, con una entrada por zona
  const ENTRADAS = new Set([6, 7, 15, 23, 24]);
  for (let x = 0; x < COLS; x++) if (!ENTRADAS.has(x)) bloquear(x, OFI);
  [[2, 12], [3, 12], [0, 11], [6, 13], [8, 11], [0, 14], [13, 14], [13, 11],
   [19, 12], [20, 12], [23, 13], [25, 11], [30, 11], [17, 14], [30, 14]].forEach(([x, y]) => bloquear(x, y));
  // las mamparas de vidrio solo se cruzan por sus puertas
  const cruzaMampara = (p, n) => p[1] < OFI && p[0] !== n[0] && MAMPARAS.includes(Math.max(p[0], n[0])) && !PUERTAS.has(p[1]);

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
        if ((bloqueado.has(k) && k !== meta) || cruzaMampara(p, n)) continue;
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
      if (y >= OFI) { // patio: pasto, con un camino de deck desde la puerta
        const deck = ENTRADAS.has(x) || (y === 13 && ((x >= 4 && x <= 8) || (x >= 14 && x <= 16) || (x >= 21 && x <= 25)))
                     || (y === 12 && ((x >= 1 && x <= 4) || (x >= 18 && x <= 21)));
        const c = deck ? ((x + y) % 2 ? "#c79a6a" : "#bb8d5d") : ((x * 7 + y * 3) % 5 === 0 ? "#6fbf5f" : (x + y) % 2 ? "#7ccb6b" : "#74c263");
        poligono([iso(x, y), iso(x + 1, y), iso(x + 1, y + 1), iso(x, y + 1)], c, deck ? "rgba(90,55,25,.25)" : "rgba(40,90,30,.18)");
        if (!deck && (x * 13 + y * 7) % 4 === 0) { // matitas de pasto
          g.fillStyle = "#4f9a43";
          const [hx, hy] = iso(x + 0.4, y + 0.55);
          g.fillRect(Math.round(hx), Math.round(hy) - 3, 2, 4); g.fillRect(Math.round(hx) + 3, Math.round(hy) - 2, 2, 3);
        }
        continue;
      }
      const celda = [iso(x, y), iso(x + 1, y), iso(x + 1, y + 1), iso(x, y + 1)];
      if (x >= ALA_TT) { // ala TikTok: loseta clara
        poligono(celda, (x + y) % 2 ? "#e4e7ec" : "#d7dbe2", "rgba(90,100,120,.22)");
        continue;
      }
      if (x >= PASILLO) { // pasillo: mármol oscuro con vetas
        poligono(celda, (x + y) % 2 ? "#4b5160" : "#444a58", "rgba(20,24,32,.35)");
        g.fillStyle = "rgba(255,255,255,.07)";
        const [mx, my] = iso(x + 0.2 + ((x * 3 + y) % 4) * 0.12, y + 0.4);
        g.fillRect(Math.round(mx), Math.round(my), 14, 1); g.fillRect(Math.round(mx) + 8, Math.round(my) + 2, 8, 1);
        continue;
      }
      const c = (x + y) % 2 ? "#d8b88f" : "#ceac81";
      poligono(celda, c, "rgba(120,80,40,.16)");
      // vetas de madera
      g.fillStyle = "rgba(120,80,40,.10)";
      const [vx, vy] = iso(x + 0.35, y + 0.5);
      g.fillRect(Math.round(vx), Math.round(vy), 10, 1);
    }
    // escalones de las puertas al patio y tapetes de bienvenida
    for (const [a, b, color] of [[6, 8, "#a16207"], [15, 16, "#7f1d1d"], [23, 25, "#ea580c"]]) {
      poligono([iso(a, OFI - 0.08), iso(b, OFI - 0.08), iso(b, OFI + 0.08), iso(a, OFI + 0.08)], "#8f6a44");
      poligono([iso(a + 0.2, OFI + 0.2), iso(b - 0.2, OFI + 0.2), iso(b - 0.2, OFI + 0.8), iso(a + 0.2, OFI + 0.8)], color);
    }
    // tapetes de las salas de descanso (una por ala)
    for (const [dx, cs] of [[0, ["#5b6fd6", "#6f82e8", "#7b8df0"]], [ALA_TT, ["#c2410c", "#ea580c", "#fb923c"]]]) {
      poligono([iso(dx + 10, 6.4), iso(dx + 13, 6.4), iso(dx + 13, 9.6), iso(dx + 10, 9.6)], cs[0]);
      poligono([iso(dx + 10.25, 6.65), iso(dx + 12.75, 6.65), iso(dx + 12.75, 9.35), iso(dx + 10.25, 9.35)], cs[1]);
      poligono([iso(dx + 10.5, 6.9), iso(dx + 12.5, 6.9), iso(dx + 12.5, 9.1), iso(dx + 10.5, 9.1)], cs[2]);
    }
    // tapete del despacho del jefe y de la sala de juntas
    poligono([iso(14.1, 0.6), iso(16.9, 0.6), iso(16.9, 3.6), iso(14.1, 3.6)], "#9b2c3c");
    poligono([iso(14.3, 0.8), iso(16.7, 0.8), iso(16.7, 3.4), iso(14.3, 3.4)], "#b4384a");
    poligono([iso(14.3, 5.3), iso(16.7, 5.3), iso(16.7, 8.7), iso(14.3, 8.7)], "#1e3a5f");
    poligono([iso(14.5, 5.5), iso(16.5, 5.5), iso(16.5, 8.5), iso(14.5, 8.5)], "#27507f");
    // borde del piso (grosor)
    const grosor = 6 * K;
    poligono([iso(0, ROWS), iso(COLS, ROWS), [iso(COLS, ROWS)[0], iso(COLS, ROWS)[1] + grosor], [iso(0, ROWS)[0], iso(0, ROWS)[1] + grosor]], "#6b4a2b");
    poligono([iso(COLS, 0), iso(COLS, OFI), [iso(COLS, OFI)[0], iso(COLS, OFI)[1] + grosor], [iso(COLS, 0)[0], iso(COLS, 0)[1] + grosor]], "#7a5838");
    poligono([iso(COLS, OFI), iso(COLS, ROWS), [iso(COLS, ROWS)[0], iso(COLS, ROWS)[1] + grosor], [iso(COLS, OFI)[0], iso(COLS, OFI)[1] + grosor]], "#5c3f24");
    poligono([iso(0, OFI), iso(0, ROWS), [iso(0, ROWS)[0] - 0, iso(0, ROWS)[1] + grosor], [iso(0, OFI)[0], iso(0, OFI)[1] + grosor]], "#5c3f24");
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
    poligono([muroI(0, 0), muroI(OFI, 0), muroI(OFI, MURO), muroI(0, MURO)], "#e6d7bd");
    poligono([muroI(0, 0), muroI(OFI, 0), muroI(OFI, 18), muroI(0, 18)], "#c9b28d");
    poligono([muroI(0, 18), muroI(OFI, 18), muroI(OFI, 19), muroI(0, 19)], "#a88d66");
    poligono([muroI(0, 0), muroI(OFI, 0), muroI(OFI, 3), muroI(0, 3)], "#8f7552");
    poligono([muroI(0, MURO - 3), muroI(OFI, MURO - 3), muroI(OFI, MURO), muroI(0, MURO)], "#9c7f5a");
    // muro del fondo, con un color por zona: YouTube (crema), despacho (madera) y TikTok (blanco)
    for (const [a, b, c] of [[0, PASILLO, ["#f1e6d2", "#d6bf99", "#b39771", "#9c8059", "#a88a63"]],
                             [PASILLO, ALA_TT, ["#8a6446", "#6f4e35", "#5a3e2a", "#4a3222", "#5a3e2a"]],
                             [ALA_TT, COLS, ["#f4f6f9", "#2b2d3a", "#f97316", "#1f2130", "#3a3d4e"]]]) {
      poligono([muroD(a, 0), muroD(b, 0), muroD(b, MURO), muroD(a, MURO)], c[0]);
      poligono([muroD(a, 0), muroD(b, 0), muroD(b, 18), muroD(a, 18)], c[1]); // franja inferior
      poligono([muroD(a, 18), muroD(b, 18), muroD(b, 19), muroD(a, 19)], c[2]);
      poligono([muroD(a, 0), muroD(b, 0), muroD(b, 3), muroD(a, 3)], c[3]);
      poligono([muroD(a, MURO - 3), muroD(b, MURO - 3), muroD(b, MURO), muroD(a, MURO)], c[4]);
    }
    // ventanas
    const hora = new Date().getHours();
    const cielo = esDeNoche() ? ["#16204a", "#2a3a78"] : hora >= 17 ? ["#f59e6b", "#fcd5a5"] : ["#7cc4f2", "#c9ecff"];
    for (const [a, b] of [[1.6, 3.4], [9.4, 10.6], [18.4, 20.2], [21.6, 23.4]]) {
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

    // despacho: placa dorada y cuadro de la ciudad
    poligono([muroD(14.5, 34), muroD(16.5, 34), muroD(16.5, 62), muroD(14.5, 62)], "#3b2416", "#1f130b");
    poligono([muroD(14.62, 37), muroD(16.38, 37), muroD(16.38, 59), muroD(14.62, 59)], esDeNoche() ? "#1e1b4b" : "#f59e6b");
    [[14.7, 0.25, 12], [15.0, 0.3, 17], [15.4, 0.25, 9], [15.7, 0.35, 14], [16.1, 0.2, 11]].forEach(([x0, w, h]) =>
      poligono([muroD(x0, 37), muroD(x0 + w, 37), muroD(x0 + w, 37 + h), muroD(x0, 37 + h)], "#2b1d3d"));
    letrero(14.3, 31.5, "DIRECCIÓN", "#fcd34d", 5);

    // ala TikTok: repisa de muestras de marcas, letrero de la tienda y fondo del estudio de grabación
    poligono([muroD(24.1, 44), muroD(25.9, 44), muroD(25.9, 64), muroD(24.1, 64)], "#1f2130", "#000");
    letrero(24.45, 60, "SHOP", "#fb923c", 7);
    const [cx0, cy0] = muroD(25.0, 49); // carrito naranja
    g.fillStyle = "#fb923c"; g.fillRect(Math.round(cx0) - 4, Math.round(cy0) - 2, 9, 5);
    g.fillStyle = "#fff"; g.fillRect(Math.round(cx0) - 3, Math.round(cy0) + 4, 2, 2); g.fillRect(Math.round(cx0) + 2, Math.round(cy0) + 6, 2, 2);
    poligono([muroD(26.1, 3), muroD(29.9, 3), muroD(29.9, 70), muroD(26.1, 70)], "#fde2e4");
    poligono([muroD(26.1, 3), muroD(29.9, 3), muroD(29.9, 12), muroD(26.1, 12)], "#fbcfe8");
    for (let i = 0; i < 5; i++) poligono([muroD(26.4 + i * 0.75, 46), muroD(26.7 + i * 0.75, 46), muroD(26.7 + i * 0.75, 66), muroD(26.4 + i * 0.75, 66)], "rgba(249,115,22,.18)");
    // lámparas tipo neón con el nombre de cada ala
    letrero(3.75, 72.5, "▶ YOUTUBE", "#ef4444", 7);
    letrero(17.6, 72.5, "TIKTOK SHOP", "#22d3ee", 7, "#f472b6");
  }

  // Texto pintado sobre el muro del fondo (sigue la inclinación del muro)
  function letrero(x, z, texto, color, px, sombra) {
    const [sx, sy] = muroD(x, z);
    g.save();
    g.translate(Math.round(sx), Math.round(sy));
    g.transform(1, TH / TW, 0, 1, 0, 0);
    g.font = `700 ${px * K}px Silkscreen, monospace`;
    g.textBaseline = "top";
    if (sombra) { g.fillStyle = sombra; g.fillText(texto, K, K); }
    g.fillStyle = color;
    g.fillText(texto, 0, 0);
    g.restore();
  }

  // ---------- muebles ----------
  const PANTALLA = { investigador: "#1e3a8a", guionista: "#78350f", locutor: "#4c1d95", productora: "#831843",
                     disenadora: "#065f46", editor: "#7f1d1d", redactora: "#155e75", community: "#7c2d12",
                     tt_cazador: "#0c4a6e", tt_guionista: "#881337", tt_director: "#365314", tt_editor: "#7c2d12",
                     tt_disenadora: "#701a75", tt_analista: "#14532d" };
  const PANTALLA_LUZ = { investigador: "#60a5fa", guionista: "#fbbf24", locutor: "#a78bfa", productora: "#f472b6",
                         disenadora: "#34d399", editor: "#f87171", redactora: "#22d3ee", community: "#fb923c",
                         tt_cazador: "#38bdf8", tt_guionista: "#fb7185", tt_director: "#a3e635", tt_editor: "#fb923c",
                         tt_disenadora: "#e879f9", tt_analista: "#4ade80" };

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
    if (id === "tt_cazador") caja(x + 0.1, y + 0.56, x + 0.26, y + 0.8, 12, 4, "#fb923c", "#ea580c", "#c2410c"); // cajita de muestra
    if (id === "tt_guionista") caja(x + 0.1, y + 0.2, x + 0.2, y + 0.3, 12, 5, "#fde68a", "#f59e0b", "#d97706"); // taza
    if (id === "tt_director") { caja(x + 0.1, y + 0.55, x + 0.28, y + 0.62, 12, 1, "#111827", "#000", "#000"); caja(x + 0.12, y + 0.62, x + 0.26, y + 0.8, 12, 0.6, "#f8fafc", "#e5e7eb", "#d1d5db"); } // claqueta
    if (id === "tt_editor") { caja(x + 0.12, y + 0.56, x + 0.2, y + 0.72, 12, 0.6, "#111", "#000", "#000"); caja(x + 0.8, y + 0.2, x + 0.9, y + 0.34, 12, 9, "#111827", "#1f2937", "#111827"); } // celular y bocina
    if (id === "tt_disenadora") caja(x + 0.1, y + 0.55, x + 0.26, y + 0.8, 12, 1, "#e879f9", "#a21caf", "#86198f"); // tableta
    if (id === "tt_analista") for (let i = 0; i < 3; i++) caja(x + 0.1 + i * 0.05, y + 0.6, x + 0.13 + i * 0.05, y + 0.66, 12, 2 + i * 2, "#4ade80", "#16a34a", "#15803d"); // gráfica
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
    const J = PASILLO - 10; // el despacho está en el pasillo
    caja(J + 10.05, 2.1, J + 12.95, 2.9, 0, 14, "#7a4b2a", "#5e391f", "#4f2f19");
    caja(J + 10.05, 2.1, J + 12.95, 2.9, 13, 1.5, "#8f5a34", "#6b4225", "#5a371f");
    caja(J + 10.2, 2.88, J + 12.8, 2.92, 2, 10, "#6b4225", "#4f2f19", "#4f2f19"); // panel frontal
    caja(J + 11.2, 2.3, J + 11.8, 2.55, 14.5, 1, "#cbd5e1", "#94a3b8", "#64748b"); // laptop
    caja(J + 11.2, 2.25, J + 11.8, 2.3, 15.5, 8, "#94a3b8", "#334155", "#1e293b");
    caja(J + 10.3, 2.3, J + 10.7, 2.7, 14.5, 4, "#f1f5f9", "#cbd5e1", "#94a3b8"); // bandeja
    const pendientes = (estado.propuestas?.length || 0) + (estado.proyectos || []).filter((p) => p.estado === "revision").length;
    for (let i = 0; i < Math.min(pendientes, 6); i++) caja(J + 10.35, 2.35, J + 10.65, 2.65, 15.5 + i * 1.4, 1.1, i % 2 ? "#fff" : "#fef9c3", "#e2e8f0", "#cbd5e1");
    caja(J + 12.35, 2.35, J + 12.6, 2.6, 14.5, 6, "#fff", "#e5e7eb", "#d1d5db"); // taza
    caja(J + 12.6, 2.2, J + 12.85, 2.45, 14.5, 3, "#fbbf24", "#d97706", "#b45309"); // trofeo
    caja(J + 12.68, 2.28, J + 12.77, 2.37, 17.5, 4, "#fde047", "#eab308", "#ca8a04");
  }
  function sillaJefe() {
    const J = PASILLO - 10;
    caja(J + 11.25, 1.15, J + 11.75, 1.25, 10, 26, "#1f2937", "#111827", "#0b0f19");
    caja(J + 11.22, 1.3, J + 11.78, 1.8, 8, 3, "#334155", "#1f2937", "#111827");
  }

  // ---------- pasillo ----------
  // Mampara de vidrio sobre la línea x = lx, en la fila y (con marcos en las puertas)
  function mampara(lx, y) {
    caja(lx - 0.06, y, lx + 0.06, y + 1, 0, 14, "#6b7280", "#4b5563", "#374151");
    caja(lx - 0.03, y, lx + 0.03, y + 1, 14, 30, "rgba(186,230,253,.55)", "rgba(186,230,253,.22)", "rgba(165,215,245,.28)");
    caja(lx - 0.06, y, lx + 0.06, y + 1, 44, 2, "#cbd5e1", "#94a3b8", "#64748b");
    caja(lx - 0.06, y, lx + 0.06, y + 0.06, 0, 46, "#cbd5e1", "#94a3b8", "#64748b"); // poste
  }
  function marcoPuerta(lx, y) { caja(lx - 0.07, y - 0.07, lx + 0.07, y, 0, 52, "#9ca3af", "#6b7280", "#4b5563"); }

  function mesaJuntas() {
    const [cx, cy] = iso(15.5, 7.0, 0);
    caja(15.4, 6.9, 15.6, 7.1, 0, 12, "#374151", "#1f2937", "#111827");
    g.fillStyle = "rgba(0,0,0,.2)"; g.beginPath(); g.ellipse(cx, cy + 2, 40, 18, 0, 0, Math.PI * 2); g.fill();
    g.fillStyle = "#3f2a1c"; g.beginPath(); g.ellipse(cx, cy - 12 * K + 3, 42, 21, 0, 0, Math.PI * 2); g.fill();
    g.fillStyle = "#5b3b26"; g.beginPath(); g.ellipse(cx, cy - 12 * K, 42, 21, 0, 0, Math.PI * 2); g.fill();
    g.fillStyle = "#f8fafc"; g.fillRect(Math.round(cx) - 16, Math.round(cy) - 12 * K - 6, 10, 7); g.fillRect(Math.round(cx) + 6, Math.round(cy) - 12 * K + 1, 10, 7);
    g.fillStyle = "#38bdf8"; g.fillRect(Math.round(cx) - 4, Math.round(cy) - 12 * K - 4, 8, 5); // tableta con la junta
  }

  function libreroChico(x, y) {
    caja(x + 0.08, y + 0.05, x + 0.92, y + 0.45, 0, 36, "#5b3b26", "#4a2f1e", "#3f2718");
    const colores = ["#fbbf24", "#ef4444", "#60a5fa", "#a78bfa", "#34d399"];
    for (let fila = 0; fila < 2; fila++) for (let i = 0; i < 5; i++)
      caja(x + 0.14 + i * 0.15, y + 0.45, x + 0.25 + i * 0.15, y + 0.47, 6 + fila * 14, 9 + (i % 2) * 2, colores[(i + fila) % 5], colores[(i + fila) % 5], colores[(i + fila) % 5]);
  }

  function garrafon(x, y) {
    caja(x + 0.3, y + 0.3, x + 0.7, y + 0.7, 0, 20, "#e5e7eb", "#d1d5db", "#9ca3af");
    caja(x + 0.32, y + 0.32, x + 0.68, y + 0.68, 20, 16, "rgba(125,211,252,.85)", "rgba(56,189,248,.75)", "rgba(14,165,233,.75)");
    caja(x + 0.62, y + 0.45, x + 0.7, y + 0.55, 12, 3, "#3b82f6", "#1d4ed8", "#1e40af"); // llave
  }

  // ---------- estudio de grabación (ala TikTok) ----------
  function mesaProducto(t) {
    caja(27.05, 2.1, 28.95, 2.9, 0, 13, "#f8fafc", "#e2e8f0", "#cbd5e1");
    caja(27.3, 2.3, 27.8, 2.7, 13, 7, "#fb923c", "#ea580c", "#c2410c"); // caja del producto
    caja(27.3, 2.48, 27.8, 2.52, 20, 0.5, "#fef3c7", "#fde68a", "#fde68a");
    caja(28.1, 2.35, 28.4, 2.65, 13, 10, "#e0f2fe", "#7dd3fc", "#38bdf8"); // gadget
    caja(28.5, 2.4, 28.75, 2.6, 13, 4, "#f472b6", "#db2777", "#be185d");
  }
  function aroDeLuz(t) {
    caja(29.45, 3.45, 29.55, 3.55, 0, 44, "#1f2937", "#111827", "#0b0f19");
    for (const [dx, dy] of [[-0.2, 0], [0.2, 0], [0, 0.2]]) caja(29.5 + dx - 0.02, 3.5 + dy - 0.02, 29.5 + dx + 0.02, 3.5 + dy + 0.02, 0, 3, "#111827", "#111827", "#111827");
    const [rx, ry] = iso(29.5, 3.5, 52);
    g.strokeStyle = "#fffbeb"; g.lineWidth = 3 * K;
    g.beginPath(); g.ellipse(rx, ry, 9 * K, 11 * K, 0, 0, Math.PI * 2); g.stroke();
    g.lineWidth = 1;
  }
  function tripie(t) {
    for (const [dx, dy] of [[-0.18, -0.1], [0.18, -0.1], [0, 0.2]]) {
      const [ax, ay] = iso(27.5 + dx, 4.4 + dy, 0), [bx, by] = iso(27.5, 4.4, 30);
      g.strokeStyle = "#111827"; g.lineWidth = K; g.beginPath(); g.moveTo(ax, ay); g.lineTo(bx, by); g.stroke();
    }
    g.lineWidth = 1;
    const [px, py] = iso(27.5, 4.4, 30);
    g.fillStyle = "#111827"; g.fillRect(Math.round(px) - 5 * K, Math.round(py) - 18 * K, 10 * K, 18 * K); // celular vertical
    g.fillStyle = "#334155"; g.fillRect(Math.round(px) - 4 * K, Math.round(py) - 17 * K, 8 * K, 16 * K);
    g.fillStyle = Math.floor(t * 2) % 2 ? "#ef4444" : "#7f1d1d"; g.fillRect(Math.round(px) + 2 * K, Math.round(py) - 16 * K, 2 * K, 2 * K); // REC
  }
  function repisaMuestras() {
    caja(24.08, 0.05, 25.92, 0.5, 0, 36, "#f8fafc", "#e2e8f0", "#cbd5e1");
    const cajas = ["#fb923c", "#f472b6", "#60a5fa", "#facc15", "#34d399", "#a78bfa"];
    for (let fila = 0; fila < 2; fila++) for (let i = 0; i < 3; i++) {
      const x0 = 24.2 + i * 0.58;
      caja(x0, 0.15, x0 + 0.42, 0.45, 2 + fila * 18, 9 + ((i + fila) % 2) * 3, cajas[(i * 2 + fila) % 6], aclarar(cajas[(i * 2 + fila) % 6], 0.8), aclarar(cajas[(i * 2 + fila) % 6], 0.65));
    }
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

  function cafetera(t, hayCafe, d = 0) {
    caja(d + 13.1, 5.1, d + 13.9, 5.9, 0, 13, "#9ca3af", "#6b7280", "#4b5563");
    caja(d + 13.15, 5.15, d + 13.85, 5.85, 13, 17, "#374151", "#1f2937", "#111827");
    caja(d + 13.15, 5.3, d + 13.18, 5.7, 18, 6, "#0ea5e9", "#0369a1", "#0369a1"); // pantallita
    const [lx, ly] = iso(d + 13.2, 5.6, 26);
    g.fillStyle = Math.floor(t * 3) % 2 ? "#22c55e" : "#166534"; g.fillRect(Math.round(lx) - 2 * K, Math.round(ly), 2 * K, 2 * K);
    caja(d + 13.3, 5.4, d + 13.5, 5.6, 13, 4, "#fff", "#e5e7eb", "#d1d5db"); // taza
    if (hayCafe) {
      g.fillStyle = "rgba(255,255,255,.6)";
      const [vx, vy] = iso(d + 13.4, 5.5, 20);
      for (let i = 0; i < 4; i++) g.fillRect(Math.round(vx + Math.sin(t * 2 + i) * 2 * K), Math.round(vy - i * 5 * K - ((t * 12) % (5 * K))), 2 * K, 2 * K);
    }
  }

  function lampara(t, d = 0) {
    caja(d + 13.42, 6.42, d + 13.58, 6.58, 0, 2, "#374151", "#1f2937", "#111827");
    caja(d + 13.48, 6.48, d + 13.52, 6.52, 2, 34, "#6b7280", "#4b5563", "#374151");
    caja(d + 13.3, 6.3, d + 13.7, 6.7, 36, 8, "#fef3c7", "#fde68a", "#fcd34d");
  }

  function sillon(d = 0, c = ["#4f46e5", "#3730a3", "#312e81", "#6366f1", "#4338ca"]) {
    caja(d + 13.15, 7.0, d + 13.95, 9.95, 0, 7, c[0], c[1], c[2]);
    caja(d + 13.7, 7.0, d + 13.95, 9.95, 7, 10, c[3], c[4], c[1]);
    caja(d + 13.15, 7.0, d + 13.95, 7.25, 7, 5, c[3], c[4], c[1]);
    caja(d + 13.15, 9.7, d + 13.95, 9.95, 7, 5, c[3], c[4], c[1]);
    caja(d + 13.25, 7.4, d + 13.65, 7.9, 7, 4, "#f472b6", "#db2777", "#be185d"); // cojín
    caja(d + 11.55, 7.9, d + 12.45, 8.6, 0, 6, "#a16207", "#854d0e", "#713f12");
    caja(d + 11.8, 8.1, d + 12.05, 8.3, 6, 3, "#fff", "#e5e7eb", "#d1d5db");
    caja(d + 12.1, 8.2, d + 12.35, 8.45, 6, 1, "#60a5fa", "#2563eb", "#1d4ed8"); // revista
  }

  // ---------- patio de descanso ----------
  function jardinera(x) {
    caja(x + 0.08, OFI + 0.2, x + 0.92, OFI + 0.8, 0, 7, "#a16207", "#854d0e", "#713f12");
    caja(x + 0.12, OFI + 0.25, x + 0.88, OFI + 0.75, 7, 1, "#3f2a14", "#3f2a14", "#3f2a14");
    const [px, py] = iso(x + 0.5, OFI + 0.5, 8);
    g.fillStyle = (x % 3) ? "#22c55e" : "#16a34a";
    for (const [dx, dy, r] of [[-8, -4, 6], [0, -8, 7], [8, -4, 6]]) { g.beginPath(); g.arc(px + dx * K / 2 * 2, py + dy, r * K / 2 * 2, 0, Math.PI * 2); g.fill(); }
    if (x % 2 === 0) { g.fillStyle = ["#f472b6", "#facc15", "#f87171"][x % 3]; g.fillRect(Math.round(px) - 3, Math.round(py) - 14, 4, 4); g.fillRect(Math.round(px) + 8, Math.round(py) - 8, 4, 4); }
  }

  function pingpong(t, jugando) {
    caja(2.1, 12.15, 3.9, 12.85, 0, 11, "#166534", "#14532d", "#14532d");
    caja(2.1, 12.15, 3.9, 12.85, 11, 1, "#15803d", "#166534", "#166534");
    poligono([iso(2.1, 12.5, 12), iso(3.9, 12.5, 12), iso(3.9, 12.52, 12), iso(2.1, 12.52, 12)], "#fff");
    caja(2.97, 12.15, 3.03, 12.85, 12, 4, "rgba(255,255,255,.8)", "rgba(230,230,230,.8)", "rgba(220,220,220,.8)"); // red
    if (jugando) { // pelotita que va y viene entre los dos jugadores
      const f = (Math.sin(t * 3.2) + 1) / 2;
      const x = 1.6 + f * 2.8, z = 14 + Math.abs(Math.sin(t * 6.4)) * 12;
      const [bx, by] = iso(x, 12.5, z);
      g.fillStyle = "rgba(0,0,0,.25)"; const [sx, sy] = iso(x, 12.5, 12); g.beginPath(); g.ellipse(sx, sy, 3, 1.5, 0, 0, Math.PI * 2); g.fill();
      g.fillStyle = "#fff"; g.beginPath(); g.arc(bx, by, 3, 0, Math.PI * 2); g.fill();
    }
  }

  function arcade(t) {
    caja(0.15, 11.1, 0.85, 11.9, 0, 40, "#7c3aed", "#5b21b6", "#4c1d95");
    caja(0.85, 11.2, 0.88, 11.8, 22, 14, "#0f172a", "#0f172a", Math.floor(t * 3) % 2 ? "#22d3ee" : "#a78bfa"); // pantalla
    caja(0.85, 11.25, 1.05, 11.75, 18, 3, "#1f2937", "#111827", "#111827"); // controles
    const [jx, jy] = iso(1.0, 11.45, 22);
    g.fillStyle = "#ef4444"; g.beginPath(); g.arc(jx, jy, 3, 0, Math.PI * 2); g.fill();
    caja(0.15, 11.1, 0.85, 11.9, 40, 5, "#facc15", "#eab308", "#ca8a04"); // marquesina
  }

  function puf(x, y, color) {
    const [cx, cy] = iso(x + 0.5, y + 0.55, 0);
    g.fillStyle = "rgba(0,0,0,.2)"; g.beginPath(); g.ellipse(cx, cy + 2, 22, 10, 0, 0, Math.PI * 2); g.fill();
    g.fillStyle = aclarar(color, 0.75); g.beginPath(); g.ellipse(cx, cy - 6, 22, 13, 0, 0, Math.PI * 2); g.fill();
    g.fillStyle = color; g.beginPath(); g.ellipse(cx, cy - 10, 19, 10, 0, 0, Math.PI * 2); g.fill();
    g.fillStyle = aclarar(color, 1.3); g.beginPath(); g.ellipse(cx - 6, cy - 13, 6, 3, 0, 0, Math.PI * 2); g.fill();
  }

  function camastro(x, y) {
    caja(x + 0.1, y + 0.3, x + 0.9, y + 0.7, 2, 3, "#e5e7eb", "#9ca3af", "#6b7280");
    caja(x + 0.1, y + 0.3, x + 0.25, y + 0.7, 5, 9, "#f1f5f9", "#cbd5e1", "#94a3b8"); // respaldo inclinado
    for (const lx of [x + 0.15, x + 0.85]) caja(lx - 0.03, y + 0.32, lx + 0.03, y + 0.38, 0, 2, "#374151", "#1f2937", "#111827");
    caja(x + 0.3, y + 0.32, x + 0.8, y + 0.68, 5, 1, "#38bdf8", "#0284c7", "#0369a1"); // toalla
  }

  function mesaSombrilla(t, d = 0, color = "#ef4444") {
    caja(d + 6.25, 13.25, d + 6.75, 13.75, 0, 10, "#f5f5f4", "#d6d3d1", "#a8a29e");
    caja(d + 6.2, 13.2, d + 6.8, 13.8, 10, 1, "#fafaf9", "#e7e5e4", "#d6d3d1");
    caja(d + 6.47, 13.47, d + 6.53, 13.53, 11, 30, "#78716c", "#57534e", "#44403c"); // palo
    const [cx, cy] = iso(d + 6.5, 13.5, 44);
    for (let k = 0; k < 8; k++) { // sombrilla a gajos
      g.fillStyle = k % 2 ? color : "#fff";
      g.beginPath(); g.moveTo(cx, cy - 10);
      g.ellipse(cx, cy, 44, 20, 0, Math.PI + k * Math.PI / 8, Math.PI + (k + 1) * Math.PI / 8); g.closePath(); g.fill();
    }
    caja(d + 6.35, 13.3, d + 6.5, 13.45, 11, 3, "#fff", "#e5e7eb", "#d1d5db"); // tazas
    caja(d + 6.55, 13.55, d + 6.7, 13.7, 11, 3, "#fff", "#e5e7eb", "#d1d5db");
    for (const [sx, sy] of [[d + 5, 13], [d + 7, 13]]) caja(sx + 0.3, sy + 0.3, sx + 0.7, sy + 0.7, 0, 7, "#f5f5f4", "#d6d3d1", "#a8a29e");
  }

  function futbolito(t, jugando) {
    caja(19.1, 12.2, 20.9, 12.8, 0, 12, "#1e3a8a", "#1e40af", "#172554");
    caja(19.2, 12.28, 20.8, 12.72, 12, 0.5, "#16a34a", "#15803d", "#15803d"); // cancha
    for (let i = 0; i < 4; i++) { // barras con jugadores
      const x = 19.4 + i * 0.4;
      caja(x - 0.02, 12.05, x + 0.02, 12.95, 15, 1, "#d1d5db", "#9ca3af", "#6b7280");
      const mueve = jugando ? Math.sin(t * 6 + i) * 0.08 : 0;
      caja(x - 0.04, 12.46 + mueve, x + 0.04, 12.54 + mueve, 12, 5, i % 2 ? "#ef4444" : "#facc15", "#b91c1c", "#a16207");
    }
    if (jugando) {
      const [bx, by] = iso(20 + Math.sin(t * 2.4) * 0.6, 12.5 + Math.sin(t * 3.7) * 0.15, 13);
      g.fillStyle = "#fff"; g.beginPath(); g.arc(bx, by, 2.5, 0, Math.PI * 2); g.fill();
    }
  }

  function arbol(x, y) {
    caja(x + 0.43, y + 0.43, x + 0.57, y + 0.57, 0, 22, "#92400e", "#78350f", "#713f12");
    const [px, py] = iso(x + 0.5, y + 0.5, 22);
    g.fillStyle = "#15803d";
    for (const [dx, dy, r] of [[0, -20, 22], [-16, -8, 16], [16, -8, 16], [0, 0, 14]]) { g.beginPath(); g.arc(px + dx, py + dy, r, 0, Math.PI * 2); g.fill(); }
    g.fillStyle = "#22c55e";
    for (const [dx, dy, r] of [[-6, -26, 8], [10, -14, 7]]) { g.beginPath(); g.arc(px + dx, py + dy, r, 0, Math.PI * 2); g.fill(); }
  }

  function fuente(t) {
    caja(13.08, 14.08, 13.92, 14.92, 0, 6, "#9ca3af", "#6b7280", "#4b5563");
    caja(13.18, 14.18, 13.82, 14.82, 5.5, 0.6, "#38bdf8", "#0ea5e9", "#0284c7");
    caja(13.44, 14.44, 13.56, 14.56, 6, 10, "#d1d5db", "#9ca3af", "#6b7280");
    g.fillStyle = "rgba(186,230,253,.9)";
    const [fx, fy] = iso(13.5, 14.5, 16);
    for (let k = 0; k < 6; k++) {
      const f = ((t * 1.5 + k / 6) % 1);
      g.fillRect(Math.round(fx + Math.cos(k) * f * 14), Math.round(fy - 6 + f * f * 24 - f * 10), 2, 2);
    }
  }

  function foquitos(t) { // guirnalda de focos sobre el patio
    const noche = esDeNoche();
    for (const fila of [10.6, 14.4]) {
      for (let k = 0; k <= 60; k++) {
        const x = 0.5 + k * 0.5, z = 62 - Math.sin((k % 15) / 15 * Math.PI) * 10;
        const [bx, by] = iso(x, fila, z);
        if (k < 60) { const [nx, ny] = iso(x + 0.5, fila, 62 - Math.sin(((k + 1) % 15) / 15 * Math.PI) * 10); g.strokeStyle = "rgba(40,40,40,.6)"; g.lineWidth = 1; g.beginPath(); g.moveTo(bx, by); g.lineTo(nx, ny); g.stroke(); }
        const color = ["#fde047", "#fb7185", "#60a5fa", "#4ade80"][k % 4];
        g.fillStyle = noche ? color : aclarar(color, 0.8);
        g.beginPath(); g.arc(bx, by + 3, 3, 0, Math.PI * 2); g.fill();
      }
    }
    for (const [x, y] of [[0.3, 10.6], [15.5, 10.6], [30.7, 10.6], [0.3, 14.4], [15.5, 14.4], [30.7, 14.4]]) caja(x - 0.04, y - 0.04, x + 0.04, y + 0.04, 0, 62, "#57534e", "#44403c", "#292524");
  }

  function brilloFoquitos() {
    g.save();
    g.globalCompositeOperation = "source-atop";
    for (const fila of [10.6, 14.4]) for (let k = 0; k <= 60; k += 2) {
      const [bx, by] = iso(0.5 + k * 0.5, fila, 30);
      const gr = g.createRadialGradient(bx, by, 2, bx, by, 60);
      gr.addColorStop(0, "rgba(255,220,140,.16)"); gr.addColorStop(1, "rgba(255,220,140,0)");
      g.fillStyle = gr; g.fillRect(bx - 60, by - 60, 120, 120);
    }
    g.restore();
  }

  // ---------- personajes ----------
  const PIEL = { productora: "#f2c6a0", investigador: "#d9a17a", guionista: "#8d5a3b", locutor: "#f5d0b0", disenadora: "#c68863",
                 editor: "#e8b48f", redactora: "#a86b4a", community: "#f0c09a", jefe: "#e0ac85",
                 tt_cazador: "#b97a56", tt_guionista: "#f1c6a3", tt_director: "#7a4a2e", tt_editor: "#e9b996",
                 tt_disenadora: "#c98e6b", tt_analista: "#9a5f3f" };
  const PELO = { productora: "#2b1a12", investigador: "#3b2a20", guionista: "#1a1110", locutor: "#c08a3e", disenadora: "#5a2d82",
                 editor: "#2a2a2a", redactora: "#6b2f1a", community: "#e2683c", jefe: "#1f1f1f",
                 tt_cazador: "#1c1917", tt_guionista: "#7c2d12", tt_director: "#111111", tt_editor: "#3b2a1a",
                 tt_disenadora: "#be185d", tt_analista: "#27170f" };
  const PANTALON = { productora: "#1f2937", investigador: "#2f3a56", guionista: "#3f3f46", locutor: "#2f3a56", disenadora: "#4b3a2a",
                     editor: "#2f3a56", redactora: "#3f3f46", community: "#2f3a56", jefe: "#1e293b",
                     tt_cazador: "#3f3f46", tt_guionista: "#1f2937", tt_director: "#4b3a2a", tt_editor: "#1e293b",
                     tt_disenadora: "#2f3a56", tt_analista: "#3f3f46" };
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
      if (estilo === "lentes" || a.lentes) {
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
    if (estilo === "copete") { P(fx - 7, U - 66, 12, 6, pelo); P(fx + 1, U - 68, 5, 4, pelo); D(fx - 4, U - 66, 5, 1, aclarar(pelo, 1.5)); }
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

  // Mientras la oficina de TikTok no tenga servidor propio, su equipo está "en obra": pasea, descansa y saluda.
  const enObraTT = EQUIPO_TT.map(([id, nombre, rol, color, pelo, desc]) => ({
    id, nombre, rol, color, pelo, desc, lentes: id === "tt_editor", estado: "libre", ubicacion: "casa", dice: "", dice_t: 0, enObra: true,
  }));
  let equipoTT = enObraTT, tareasTT = [], ultimoYT = null;

  // Estado de la oficina de TikTok Shop (null = apagada: su equipo vuelve a estar "en obra")
  function actualizarTT(tt) {
    equipoTT = tt?.agentes?.length ? tt.agentes : enObraTT;
    tareasTT = tt?.tareas || [];
    if (ultimoYT) actualizar(ultimoYT);
  }

  function actualizar(nuevo) {
    ultimoYT = nuevo;
    const lista = [...nuevo.agentes, ...equipoTT];
    const agentes = {};
    lista.forEach((a) => (agentes[a.id] = a));
    estado = { ...nuevo, agentes, tareas: [...(nuevo.tareas || []), ...tareasTT] };
    for (const a of lista) {
      let v = vivos[a.id];
      if (!v) {
        const c = CASA[a.id];
        v = vivos[a.id] = { pos: [c[0] + 0.5, c[1] + 0.5], camino: [], meta: c, frente: a.id === "jefe", dice_t: a.dice_t,
                            globo: null, pasearEn: performance.now() + 8000 + Math.random() * 20000, dom: crearDom(a) };
        if (a.enObra && SALUDOS_TT[a.id]) setTimeout(() => { if (vivos[a.id] && equipoTT === enObraTT) vivos[a.id].pendiente = SALUDOS_TT[a.id]; }, 2500 + Math.random() * 9000);
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
                          editor: "🎬", redactora: "📝", community: "📤", jefe: "👔",
                          tt_cazador: "🔎", tt_guionista: "✍️", tt_director: "🎥", tt_editor: "🎬", tt_disenadora: "🎨", tt_analista: "📊" };
  const DURACION = { ficha: 25, tomas: 25, ideas: 30, investigar: 90, guion: 60, voz: 45, miniatura: 8, video: 150, blog: 60, publicar: 60 };

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
    // despacho del jefe y sala de juntas (pasillo)
    agrega(15 + 1 + 0.5, sillaJefe);
    agrega(15.5 + 2.5 + 0.2, () => escritorioJefe(t, estado));
    agrega(14.6, () => libreroChico(14, 0)); agrega(17, () => planta(16, 0));
    agrega(15 + 5 + 0.9, () => silla(15, 5)); agrega(15 + 5 + 1.3, () => respaldo(15, 5, "#1e3a8a"));
    agrega(22.5, mesaJuntas);
    agrega(15 + 8 + 0.9, () => silla(15, 8)); agrega(15 + 8 + 1.3, () => respaldo(15, 8, "#1e3a8a"));
    agrega(24, () => planta(14, 9)); agrega(26, () => planta(16, 9));
    // ala YouTube
    agrega(1, () => planta(0, 0)); agrega(14, () => planta(13, 0, true)); agrega(10, () => planta(0, 9, true));
    agrega(12.9, () => garrafon(12, 0));
    agrega(4.2, librero);
    const tomandoCafe = (c) => Object.values(vivos).some((v) => !v.camino.length && igual(v.meta, c));
    agrega(19, () => cafetera(t, tomandoCafe(CAFE)));
    agrega(20, () => lampara(t));
    agrega(21.5, () => sillon());
    // ala TikTok
    agrega(24.6, repisaMuestras);
    agrega(30.7, () => mesaProducto(t));
    agrega(32, () => tripie(t));
    agrega(33.2, () => aroDeLuz(t));
    agrega(27, () => planta(17, 9)); agrega(31, () => planta(30, 0, true));
    agrega(19 + ALA_TT, () => cafetera(t, tomandoCafe(CAFE_TT), ALA_TT));
    agrega(20 + ALA_TT, () => lampara(t, ALA_TT));
    agrega(21.5 + ALA_TT, () => sillon(ALA_TT, ["#0f766e", "#115e59", "#134e4a", "#14b8a6", "#0d9488"]));
    // mamparas de vidrio entre zonas, con marcos en las puertas
    for (const lx of MAMPARAS) {
      for (let y = 0; y < OFI; y++) if (!PUERTAS.has(y)) agrega(lx + y + 0.5, () => mampara(lx, y));
      const p0 = Math.min(...PUERTAS), p1 = Math.max(...PUERTAS) + 1;
      agrega(lx + p0 + 0.05, () => marcoPuerta(lx, p0)); agrega(lx + p1 + 0.05, () => marcoPuerta(lx, p1));
    }
    for (let x = 0; x < COLS; x++) if (!ENTRADAS.has(x)) agrega(x + OFI + 1, () => jardinera(x));
    const enLugar = (idAct) => Object.values(vivos).some((v) => v.actividad === idAct && !v.camino.length);
    agrega(14.5 + 0.2, () => pingpong(t, enLugar("ping_a") && enLugar("ping_b")));
    agrega(11.5 + 0.7, () => arcade(t));
    for (const a of ACTIVIDADES) {
      if (a.puf) agrega(a.pos[0] + a.pos[1] + 0.6, () => puf(a.pos[0], a.pos[1], a.puf));
      if (a.camastro) agrega(a.pos[0] + a.pos[1] + 0.6, () => camastro(a.pos[0], a.pos[1]));
    }
    agrega(6.5 + 13.5 + 0.3, () => mesaSombrilla(t));
    agrega(8.5 + 11.5 + 0.5, () => arbol(8, 11)); agrega(13.5 + 11.5 + 0.5, () => arbol(13, 11)); agrega(0.5 + 14.5 + 0.5, () => arbol(0, 14));
    agrega(13.5 + 14.5 + 0.5, () => fuente(t));
    agrega(32.7, () => futbolito(t, enLugar("futbol_a") && enLugar("futbol_b")));
    agrega(23.5 + 13.5 + 0.3, () => mesaSombrilla(t, ALA_TT, "#f97316"));
    agrega(25.5 + 11.5 + 0.5, () => arbol(25, 11)); agrega(30.5 + 11.5 + 0.5, () => arbol(30, 11));
    agrega(17.5 + 14.5 + 0.5, () => arbol(17, 14)); agrega(30.5 + 14.5 + 0.5, () => arbol(30, 14));
    agrega(100, () => foquitos(t));

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
        if (enCasa || Math.random() < 0.5) { // ir a descansar (o cambiar de actividad)
          const ocupadas = new Set(Object.values(vivos).filter((o) => o !== v).map((o) => o.actividad));
          const libres = ACTIVIDADES.filter((x) => !ocupadas.has(x.id));
          const conPareja = libres.filter((x) => x.id.startsWith("ping") && ocupadas.has(x.id === "ping_a" ? "ping_b" : "ping_a"));
          let elegido = conPareja[0] || (Math.random() < 0.75 && libres.length ? libres[Math.floor(Math.random() * libres.length)] : null);
          v.actividad = elegido ? elegido.id : null;
          const paseos = esTT(id) ? PASEOS_TT : PASEOS;
          irA(v, elegido ? elegido.pos : paseos[Math.floor(Math.random() * paseos.length)]);
          v.pasearEn = ahora + 18000 + Math.random() * 25000;
        } else {
          v.actividad = null;
          irA(v, CASA[id]);
          v.pasearEn = ahora + 20000 + Math.random() * 25000;
        }
      }
      if (a.estado !== "libre" && !v.camino.length) {
        const m = destinoDe(a);
        if (!igual(m, v.meta)) { v.actividad = null; irA(v, m); } // le llegó trabajo: regresa
      }
      if (v.pendiente && !v.camino.length) { v.globo = { texto: v.pendiente, hasta: ahora + 6500 }; v.pendiente = null; }
      const enSilla = !caminando && (igual(v.meta, CASA[id])) && id !== "jefe";
      const act = !caminando && v.actividad ? ACTIVIDADES.find((x) => x.id === v.actividad) : null;
      if (act) v.frente = act.frente;
      const tecleando = (a.estado === "trabajando" && enSilla) || Boolean(act?.mano);
      const [px, py] = iso(v.pos[0], v.pos[1]);
      v.pantalla = [px, py];
      v.sentado = enSilla || (id === "jefe" && !caminando) || Boolean(act?.sentado);
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
      brilloFoquitos();
    }

    moverCamara(dt);
    const dpr = window.devicePixelRatio || 1;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    reflector(ahora);
    ctx.imageSmoothingEnabled = false;
    ctx.clearRect(0, 0, lienzo.width, lienzo.height);
    ctx.drawImage(buf, cam.x, cam.y, cam.w, cam.h, offX, offY, cam.w * escala, cam.h * escala);
    capasDom(ahora);
    requestAnimationFrame(cuadro);
  }

  // Al elegir un agente: la oficina se oscurece un momento con un reflector sobre él y le queda una flechita encima
  const sinMovimiento = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  let foco = null; // { id, desde }
  function reflector(ahora) {
    const v = seleccionado && vivos[seleccionado];
    if (!v?.pantalla) return;
    const [px, py] = v.pantalla;
    const color = estado.agentes[seleccionado]?.color || "#ffd23f";
    if (foco?.id === seleccionado) {
      const t = (ahora - foco.desde) / 1000, dura = sinMovimiento ? 1.2 : 2.2;
      if (t < dura) {
        const sube = sinMovimiento ? 1 : Math.min(1, t / 0.25);
        const baja = 1 - Math.max(0, (t - dura + 0.8) / 0.8);
        const radio = 46 + (sinMovimiento ? 0 : (1 - Math.min(1, t / 0.5)) * 120);
        g.save();
        g.fillStyle = `rgba(8,10,24,${0.5 * sube * baja})`;
        g.beginPath();
        g.rect(0, 0, ANCHO, ALTO);
        g.ellipse(px, py - 30, radio, radio * 1.15, 0, 0, Math.PI * 2);
        g.fill("evenodd");
        g.restore();
      }
    }
    const brinco = sinMovimiento ? 0 : Math.abs(Math.sin(ahora / 260)) * 7;
    const y0 = py - 88 - brinco;
    g.save();
    g.fillStyle = color; g.strokeStyle = "#1b1a26"; g.lineWidth = 2;
    g.beginPath(); g.moveTo(px - 9, y0 - 12); g.lineTo(px + 9, y0 - 12); g.lineTo(px, y0); g.closePath();
    g.fill(); g.stroke();
    g.restore();
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
      const [x, y] = aPantalla(px, py);
      const alto = (v.sentado ? 58 : 64) * escala;
      const { nombre, globo, icono } = v.dom;
      const fuera = x < -20 || x > lienzoW + 20 || y < 0 || y > lienzoH + 20;
      nombre.hidden = fuera;
      if (fuera) { globo.hidden = true; icono.hidden = true; continue; }
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
      else if (v.actividad && !v.camino.length) ico = ACTIVIDADES.find((x) => x.id === v.actividad)?.icono || "";
      else if (esCafe(v.meta) && !v.camino.length) ico = "☕";
      else if (escala >= 0.75 && id !== "jefe" && a?.estado === "libre" && igual(v.meta, CASA[id]) && !v.camino.length) ico = "💤";
      icono.hidden = !ico || visible;
      if (!icono.hidden) {
        if (icono.textContent !== ico) icono.textContent = ico;
        icono.classList.toggle("alerta", ico === "❗");
        icono.style.transform = `translate(${x}px, ${y - alto - 2 * escala + Math.sin(ahora / 300 + px) * 2}px) translate(-50%, -100%)`;
      }
    }
  }

  // ---------- cámara: todo el edificio o un ala ----------
  function marco(x0, x1) { // rectángulo del lienzo que muestra las columnas x0..x1 (con muro y patio)
    const izq = iso(x0, ROWS)[0], der = iso(x1, 0)[0];
    const arriba = iso(x0, 0, MURO)[1], abajo = iso(x1, ROWS)[1] + 8 * K;
    const m = 10 * K;
    return { x: izq - m, y: arriba - m, w: der - izq + m * 2, h: abajo - arriba + m * 2 };
  }
  const VISTAS = { todo: { x: 0, y: 0, w: ANCHO, h: ALTO }, youtube: marco(0, ALA_TT), tiktok: marco(PASILLO, COLS) };
  const leerAla = () => { try { return localStorage.getItem("ala"); } catch { return null; } };
  let ala = VISTAS[leerAla()] ? leerAla() : (window.innerWidth < 760 ? "youtube" : "todo");
  const cam = { ...VISTAS[ala] };
  let offX = 0, offY = 0, lienzoW = 0, lienzoH = 0;

  function moverCamara(dt) {
    const meta = VISTAS[ala], f = Math.min(1, dt * 7);
    for (const k of ["x", "y", "w", "h"]) cam[k] = Math.abs(meta[k] - cam[k]) < 0.5 ? meta[k] : cam[k] + (meta[k] - cam[k]) * f;
    escala = Math.min(lienzoW / cam.w, lienzoH / cam.h, 1.6);
    offX = (lienzoW - cam.w * escala) / 2;
    offY = (lienzoH - cam.h * escala) / 2;
    capas.style.setProperty("--tag", `${Math.max(9, Math.min(13, 11 * escala))}px`);
    capas.style.setProperty("--globo", `${Math.max(11, Math.min(13.5, 12.5 * escala))}px`);
  }
  const aPantalla = (px, py) => [(px - cam.x) * escala + offX, (py - cam.y) * escala + offY];

  function ajustar() {
    const dpr = window.devicePixelRatio || 1;
    const meta = VISTAS[ala];
    lienzoW = Math.max(240, sala.clientWidth - 8);
    const altoLibre = window.innerHeight - 180;
    lienzoH = Math.round(Math.min(lienzoW * meta.h / meta.w, altoLibre > 260 ? altoLibre : 9e9, meta.h * 1.6));
    lienzoW = Math.round(Math.min(lienzoW, meta.w * 1.6));
    lienzo.style.width = `${lienzoW}px`;
    lienzo.style.height = `${lienzoH}px`;
    lienzo.width = Math.round(lienzoW * dpr);
    lienzo.height = Math.round(lienzoH * dpr);
    capas.style.width = lienzo.style.width;
    capas.style.height = lienzo.style.height;
    moverCamara(0);
  }

  function verAla(nueva) {
    if (!VISTAS[nueva]) return;
    ala = nueva;
    try { localStorage.setItem("ala", ala); } catch { /* sin almacenamiento: solo no se recuerda */ }
    document.querySelectorAll("[data-ala]").forEach((b) => b.classList.toggle("activa", b.dataset.ala === ala));
    ajustar();
    window.dispatchEvent(new CustomEvent("ala", { detail: ala }));
  }
  document.querySelectorAll("[data-ala]").forEach((b) => b.addEventListener("click", () => verAla(b.dataset.ala)));
  window.addEventListener("resize", ajustar);
  verAla(ala);
  Object.assign(cam, VISTAS[ala]);
  requestAnimationFrame(cuadro);

  function agenteEn(clientX, clientY) {
    const r = lienzo.getBoundingClientRect();
    const nx = (clientX - r.left - offX) / escala + cam.x, ny = (clientY - r.top - offY) / escala + cam.y;
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
    actualizarTT,
    agenteEn, retrato,
    escala: () => escala,
    posicion: (id) => vivos[id]?.pantalla,
    seleccionar: (id) => {
      if (id && id !== seleccionado) foco = { id, desde: performance.now() };
      seleccionado = id;
      // si el agente está en la otra ala, la cámara se va para allá
      if (id && ala !== "todo" && (esTT(id) ? "tiktok" : "youtube") !== ala && id !== "jefe") verAla(esTT(id) ? "tiktok" : "youtube");
    },
    ala: () => ala,
    equipoTT: () => equipoTT,
    encima: (id) => { encima = id; },
    verAla,
  };
})();
