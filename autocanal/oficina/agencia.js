// 🕵️ La Agencia de Expedientes («¿Quién MATÓ a…?»): UNA sola oficina de detectives, de noche. Cubículos chiquitos
// alrededor (uno por área) y el despacho de vidrio del jefe en el centro, con el pizarrón de evidencias. Luz de
// lámparas sobre los escritorios, lluvia en las ventanas y el letrero de neón del canal.
// Ligero: lo fijo se dibuja una vez en una capa aparte; cada cuadro solo pinta lo que se mueve (12 cuadros/s) y se
// detiene si la pestaña está escondida. El panel de la derecha es expedientes.js.
(() => {
  const cv = document.getElementById("ag-lienzo");
  const capas = document.getElementById("ag-capas");
  const ficha = document.getElementById("ag-ficha");
  if (!cv) return;
  const g = cv.getContext("2d");
  const base = document.createElement("canvas"), gb = base.getContext("2d"); // lo que no se mueve
  const sombra = document.createElement("canvas"), gs = sombra.getContext("2d"); // la oscuridad con huecos de luz
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const AM = "#FFD60A", ROJO = "#E63946", VERDE = "#2DC653", BLANCO = "#F5F5F5";
  const quieto = matchMedia("(prefers-reduced-motion: reduce)").matches;

  // ---------- quién está en cada cubículo ----------
  const AREAS = {
    ex_guion: { cuarto: "Redacción", icono: "✍️" }, ex_ramos: { cuarto: "Interrogatorios", icono: "🔎" }, ex_archivista: { cuarto: "Archivo", icono: "🗄️" },
    ex_graficas: { cuarto: "Laboratorio", icono: "📊" }, ex_miniaturas: { cuarto: "Estudio", icono: "🖼️" },
    ex_editor: { cuarto: "Edición", icono: "✂️" }, ex_subtitulos: { cuarto: "Subtítulos", icono: "💬" },
    ex_publicacion: { cuarto: "Publicación", icono: "📤" }, jefe: { cuarto: "Despacho del jefe", icono: "🎙️" },
  };
  const JEFE = { id: "jefe", nombre: "Tú (Miguel)", rol: "El jefe · la voz del canal", color: AM, pelo: "corto",
                 desc: "Grabas la narración por escena (escena-01 a escena-14) y apruebas todo. Nada se hace público sin ti." };

  // Dos planos: ancho (compu) y alto (cel). Todo en unidades del plano; se escala al tamaño de la pantalla.
  const PLANOS = {
    ancho: { w: 1000, h: 640, cub: [150, 112], jefe: { x: 330, y: 150, w: 340, h: 300 },
             cubs: { ex_ramos: [40, 80], ex_archivista: [40, 222], ex_graficas: [40, 364], ex_miniaturas: [810, 80],
                     ex_editor: [810, 222], ex_subtitulos: [810, 364], ex_guion: [250, 500], ex_publicacion: [600, 500] },
             ventanas: [[90, 150], [330, 340], [760, 150]], neon: [500, 92],
             adornos: [["planta", 440, 600], ["planta", 560, 470], ["cafe", 120, 540], ["sillon", 860, 560], ["archivero", 230, 90], ["archivero", 735, 90]] },
    alto: { w: 600, h: 1000, cub: [135, 112], jefe: { x: 50, y: 370, w: 500, h: 280 },
            cubs: { ex_ramos: [20, 80], ex_miniaturas: [445, 80], ex_archivista: [20, 222], ex_editor: [445, 222],
                    ex_graficas: [20, 700], ex_subtitulos: [445, 700], ex_guion: [90, 860], ex_publicacion: [375, 860] },
            ventanas: [[40, 110], [190, 220], [450, 110]], neon: [300, 160],
            adornos: [["planta", 200, 300], ["planta", 385, 300], ["planta", 300, 960]] },
  };
  let P = PLANOS.ancho, escala = 1, dpr = 1;
  let equipo = [], expedientes = [], elegido = null, t = 0, baseLista = false;
  const agente = (id) => (id === "jefe" ? JEFE : equipo.find((a) => a.id === id));
  const trabaja = (a) => a?.estado === "trabajando";
  const enObra = (a) => a && a.id !== "jefe" && a.obra && !trabaja(a);
  const jefeTrabaja = () => expedientes.some((e) => (e.pasos || []).some((p) => p.clave === "voz" && p.estado === "pendiente"));
  const caso = () => expedientes[0];

  // ---------- utilidades de dibujo ----------
  function rr(c, x, y, w, h, r) { c.beginPath(); c.roundRect ? c.roundRect(x, y, w, h, r) : c.rect(x, y, w, h); }
  function caja(c, x, y, w, h, col, r = 3) { rr(c, x, y, w, h, r); c.fillStyle = col; c.fill(); }
  const PELO = { gorra: "#1f2937", copete: "#3a2216", chongo: "#1d120c", bob: "#2a1a12", corto: "#2b1d14", largo: "#4a2c19", rizos: "#20140d" };
  // persona vista desde arriba: de espaldas (mira su monitor) o de frente (el jefe)
  function persona(c, x, y, a, { frente = false, tecleo = false, apagada = false } = {}) {
    c.save();
    c.globalAlpha = apagada ? 0.35 : 1;
    caja(c, x - 15, y - 2, 30, 22, "#15161a", 9); // silla
    c.fillStyle = a?.color || "#888";
    c.beginPath(); c.ellipse(x, y + 4, 14, 9, 0, 0, Math.PI * 2); c.fill(); // hombros
    c.fillStyle = "rgba(0,0,0,.18)"; c.beginPath(); c.ellipse(x, y + 7, 12, 5, 0, 0, Math.PI); c.fill();
    const mano = tecleo ? Math.sin(t * 18) * 2 : 0, dir = frente ? 1 : -1;
    c.fillStyle = "#d6a27a";
    c.beginPath(); c.arc(x - 9, y + dir * 8 + mano, 3, 0, 7); c.arc(x + 9, y + dir * 8 - mano, 3, 0, 7); c.fill(); // manos
    c.fillStyle = "#d6a27a"; c.beginPath(); c.arc(x, y - 3 * dir * -1 - 1, 7.5, 0, 7); c.fill(); // cabeza
    c.fillStyle = PELO[a?.pelo] || "#2b1d14";
    c.beginPath();
    if (frente) c.arc(x, y - 3, 7.5, Math.PI * 1.05, Math.PI * 1.95); else c.arc(x, y + 0.5, 7.6, 0, 7);
    c.fill();
    if (a?.pelo === "gorra") { c.fillStyle = "#111827"; c.beginPath(); c.arc(x, y + (frente ? -3 : 0.5), 8.5, Math.PI, 0); c.fill(); }
    if (a?.pelo === "chongo") { c.fillStyle = PELO.chongo; c.beginPath(); c.arc(x, y + (frente ? -11 : 8), 3.5, 0, 7); c.fill(); }
    c.restore();
  }

  // ---------- lo que no se mueve (capa base) ----------
  function piso(c) {
    for (let y = 0; y < P.h; y += 22) {
      for (let x = (y / 22) % 2 ? -60 : 0; x < P.w; x += 120) {
        c.fillStyle = ((x + y) / 22) % 3 < 1 ? "#24190f" : ((x + y) / 22) % 3 < 2 ? "#201610" : "#1c130d";
        c.fillRect(x, y, 119, 21);
      }
    }
    // sombras de persianas que entran por las ventanas
    c.save(); c.globalAlpha = 0.07; c.fillStyle = "#cfe3ff";
    for (const [vx, vw] of P.ventanas) for (let i = 0; i < 9; i++) {
      c.beginPath(); c.moveTo(vx + 10, 60 + i * 26); c.lineTo(vx + vw - 10, 60 + i * 26); c.lineTo(vx + vw + 70, 74 + i * 26 + 40); c.lineTo(vx + 80, 74 + i * 26 + 40); c.fill();
    }
    c.restore();
    // pared de arriba
    const pared = c.createLinearGradient(0, 0, 0, 60); pared.addColorStop(0, "#0e0f12"); pared.addColorStop(1, "#1b1c21");
    c.fillStyle = pared; c.fillRect(0, 0, P.w, 60); c.fillStyle = "#08090b"; c.fillRect(0, 58, P.w, 4);
    c.fillStyle = "#0b0c0e"; c.fillRect(0, 0, 8, P.h); c.fillRect(P.w - 8, 0, 8, P.h); c.fillRect(0, P.h - 8, P.w, 8);
    for (const [vx, vw] of P.ventanas) { // marco de las ventanas y la ciudad
      caja(c, vx - 4, 6, vw + 8, 48, "#050608", 2);
      const cielo = c.createLinearGradient(0, 8, 0, 52); cielo.addColorStop(0, "#0b1430"); cielo.addColorStop(1, "#1c1530");
      c.fillStyle = cielo; c.fillRect(vx, 9, vw, 42);
      let sx = vx;
      while (sx < vx + vw) {
        const bw = 10 + ((sx * 7) % 17), bh = 12 + ((sx * 13) % 22);
        c.fillStyle = "#05070d"; c.fillRect(sx, 51 - bh, bw, bh);
        for (let wy = 51 - bh + 3; wy < 49; wy += 5) for (let wx = sx + 2; wx < sx + bw - 2; wx += 4)
          if ((wx * 31 + wy * 17) % 7 === 0) { c.fillStyle = "#f6c453"; c.fillRect(wx, wy, 1.6, 1.6); }
        sx += bw + 2;
      }
      c.fillStyle = "#050608"; c.fillRect(vx + vw / 2 - 1.5, 9, 3, 42); // cruz del marco
    }
  }
  function adorno(c, tipo, x, y) {
    if (tipo === "planta") {
      caja(c, x - 12, y + 2, 24, 18, "#4a3426", 4);
      c.fillStyle = "#14532d"; for (let i = 0; i < 7; i++) { c.beginPath(); c.ellipse(x + Math.cos(i) * 9, y - 4 + Math.sin(i * 2) * 6, 9, 5, i, 0, 7); c.fill(); }
      c.fillStyle = "#1f7a3f"; c.beginPath(); c.arc(x, y - 4, 6, 0, 7); c.fill();
    } else if (tipo === "cafe") {
      caja(c, x - 30, y - 18, 60, 34, "#2a2b31", 4); caja(c, x - 22, y - 14, 20, 24, "#111", 3);
      c.fillStyle = ROJO; c.beginPath(); c.arc(x - 12, y - 6, 2, 0, 7); c.fill();
      caja(c, x + 4, y - 10, 9, 11, BLANCO, 2); caja(c, x + 16, y - 10, 9, 11, "#e8e2d4", 2);
    } else if (tipo === "sillon") {
      caja(c, x - 50, y - 20, 100, 40, "#3b1d20", 10); caja(c, x - 42, y - 12, 84, 26, "#4c2328", 8);
    } else if (tipo === "archivero") {
      caja(c, x - 18, y - 22, 36, 44, "#3c414a", 3);
      for (let i = 0; i < 3; i++) { caja(c, x - 15, y - 19 + i * 14, 30, 11, "#4b515b", 2); c.fillStyle = "#9aa0a6"; c.fillRect(x - 5, y - 15 + i * 14, 10, 2); }
    }
  }
  function cubiculo(c, id) {
    const [x, y] = P.cubs[id], [w, h] = P.cub, a = agente(id);
    const obra = enObra(a);
    c.fillStyle = "rgba(0,0,0,.25)"; c.fillRect(x + 4, y + 6, w, h); // sombra
    c.fillStyle = "#262a33"; c.fillRect(x, y, w, h); // alfombra del cubículo
    // mamparas (tres lados; abierto abajo)
    const mampara = (mx, my, mw, mh) => { caja(c, mx, my, mw, mh, "#3c4352", 2); c.fillStyle = "#5a6274"; c.fillRect(mx, my, mw, 2); };
    mampara(x - 4, y - 6, w + 8, 10); mampara(x - 4, y - 6, 8, h + 6); mampara(x + w - 4, y - 6, 8, h + 6);
    // escritorio y cosas
    caja(c, x + 10, y + 8, w - 20, 34, "#5b3e25", 3); c.fillStyle = "rgba(255,255,255,.06)"; c.fillRect(x + 10, y + 8, w - 20, 3);
    if (obra) { // cinta de escena del crimen en la entrada: esa área todavía se está construyendo
      c.save(); c.translate(x + w / 2, y + h - 3); c.rotate(-0.06);
      c.fillStyle = AM; c.fillRect(-w / 2 - 8, -5, w + 16, 10);
      c.fillStyle = "#111"; c.font = "700 7.5px Inter, sans-serif"; c.textAlign = "center"; c.textBaseline = "middle";
      c.fillText("EN OBRA · NO PASAR · EN OBRA", 0, 0.5); c.restore();
    }
    caja(c, x + w - 32, y + 14, 8, 8, "#2b2b2b", 4); // base de la lámpara
    if (id === "ex_ramos") { // corcho con fotos e hilo rojo en la mampara
      caja(c, x + 14, y - 4, 42, 7, "#8a6239", 1);
      c.fillStyle = "#e7e2d4"; [16, 26, 36, 46].forEach((dx) => c.fillRect(x + dx, y - 3, 6, 5));
    }
    if (id === "ex_archivista") { [0, 1, 2].forEach((i) => caja(c, x + 14 + i * 13, y + h - 26, 12, 12, ["#8b6a43", "#9b7a50", "#7a5c39"][i], 2)); }
    if (id === "ex_publicacion") { caja(c, x + 14, y + 14, 16, 12, "#e7e2d4", 2); }
    if (id === "ex_miniaturas") { caja(c, x + w - 22, y + h - 30, 14, 14, "#2a2a2e", 7); c.fillStyle = "#555"; c.beginPath(); c.arc(x + w - 15, y + h - 23, 4, 0, 7); c.fill(); }
  }
  function despacho(c) {
    const { x, y, w, h } = P.jefe;
    c.fillStyle = "rgba(0,0,0,.3)"; c.fillRect(x + 6, y + 8, w, h);
    c.fillStyle = "#1b1416"; c.fillRect(x, y, w, h); // piso del despacho
    c.fillStyle = "#3b1d20"; c.beginPath(); c.ellipse(x + w / 2, y + h * 0.66, w * 0.33, h * 0.2, 0, 0, 7); c.fill(); // tapete
    c.strokeStyle = "rgba(230,57,70,.35)"; c.lineWidth = 2; c.beginPath(); c.ellipse(x + w / 2, y + h * 0.66, w * 0.3, h * 0.17, 0, 0, 7); c.stroke();
    // pizarrón de evidencias en la pared del fondo
    const pw = Math.min(220, w - 60), px = x + (w - pw) / 2;
    caja(c, px, y + 10, pw, 46, "#6b4a2b", 3); caja(c, px + 3, y + 13, pw - 6, 40, "#8a6239", 2);
    const fotos = [[0.08, 0.2], [0.27, 0.55], [0.46, 0.18], [0.64, 0.6], [0.84, 0.25]];
    c.strokeStyle = ROJO; c.lineWidth = 1.2; c.beginPath();
    fotos.forEach(([fx, fy], i) => { const X = px + fx * pw + 6, Y = y + 13 + fy * 40 + 5; i ? c.lineTo(X, Y) : c.moveTo(X, Y); });
    c.stroke();
    fotos.forEach(([fx, fy], i) => { caja(c, px + fx * pw, y + 13 + fy * 40, 13, 11, i === 2 ? AM : "#e7e2d4", 1); c.fillStyle = ROJO; c.beginPath(); c.arc(px + fx * pw + 6, y + 14 + fy * 40, 1.6, 0, 7); c.fill(); });
    // escritorio grande con el expediente, micrófono y café
    const ew = Math.min(170, w - 80), ex = x + (w - ew) / 2, ey = y + 92;
    caja(c, ex, ey, ew, 48, "#4a2f1c", 4); c.fillStyle = "rgba(255,255,255,.07)"; c.fillRect(ex, ey, ew, 3);
    caja(c, ex + ew / 2 - 22, ey + 10, 44, 30, AM, 2); caja(c, ex + ew / 2 - 22, ey + 10, 44, 6, "#e0b800", 2); // carpeta del caso
    c.fillStyle = "#111"; c.font = "400 13px 'Bebas Neue', Impact, sans-serif"; c.textAlign = "center";
    c.fillText(caso() ? `#${String(caso().numero).padStart(3, "0")}` : "CASO", ex + ew / 2, ey + 34);
    caja(c, ex + 12, ey + 14, 10, 10, BLANCO, 5); c.fillStyle = "#3b2414"; c.beginPath(); c.arc(ex + 17, ey + 19, 3, 0, 7); c.fill(); // café
    c.strokeStyle = "#555"; c.lineWidth = 3; c.beginPath(); c.moveTo(ex + ew - 10, ey + 8); c.lineTo(ex + ew - 30, ey - 6); c.lineTo(ex + ew - 46, ey + 6); c.stroke(); // brazo del micro
    caja(c, ex + ew - 52, ey + 2, 12, 16, "#1b1b1b", 6);
    // sillas para los que vienen a reportar
    [-1, 1].forEach((s) => { caja(c, x + w / 2 + s * 40 - 14, ey + 78, 28, 24, "#2d1a1d", 8); });
    // paredes de vidrio (con puerta abajo)
    c.save();
    c.strokeStyle = "rgba(170,215,255,.45)"; c.lineWidth = 5;
    c.beginPath(); c.moveTo(x + w / 2 - 34, y + h); c.lineTo(x, y + h); c.lineTo(x, y); c.lineTo(x + w, y); c.lineTo(x + w, y + h); c.lineTo(x + w / 2 + 34, y + h); c.stroke();
    c.strokeStyle = "rgba(255,255,255,.25)"; c.lineWidth = 1;
    for (let i = 0; i < 4; i++) { c.beginPath(); c.moveTo(x + 30 + i * 70, y + 1); c.lineTo(x + 52 + i * 70, y + 1); c.stroke(); }
    c.restore();
    caja(c, x + w - 40, y + 66, 26, 10, "#2a0d10", 2); // foco ON AIR (se prende en el cuadro)
  }
  function pintarBase() {
    base.width = cv.width; base.height = cv.height;
    gb.setTransform(escala * dpr, 0, 0, escala * dpr, 0, 0);
    piso(gb);
    P.adornos.forEach(([tipo, x, y]) => adorno(gb, tipo, x, y));
    despacho(gb);
    Object.keys(P.cubs).forEach((id) => cubiculo(gb, id));
    pintarSombra();
    baseLista = true;
  }
  // La oscuridad de la noche, con huecos donde hay luz (lámparas, el despacho, la luz de la luna)
  function pintarSombra() {
    sombra.width = cv.width; sombra.height = cv.height;
    gs.setTransform(escala * dpr, 0, 0, escala * dpr, 0, 0);
    gs.fillStyle = "rgba(4,5,12,.5)"; gs.fillRect(0, 0, P.w, P.h);
    gs.globalCompositeOperation = "destination-out";
    const hueco = (x, y, r, fuerza) => {
      const gr = gs.createRadialGradient(x, y, 0, x, y, r);
      gr.addColorStop(0, `rgba(0,0,0,${fuerza})`); gr.addColorStop(1, "rgba(0,0,0,0)");
      gs.fillStyle = gr; gs.fillRect(x - r, y - r, r * 2, r * 2);
    };
    const J = P.jefe;
    hueco(J.x + J.w / 2, J.y + J.h * 0.45, Math.max(J.w, J.h) * 0.62, 0.95);
    for (const id of Object.keys(P.cubs)) {
      const a = agente(id);
      const [x, y] = P.cubs[id], [w, h] = P.cub;
      hueco(x + w / 2, y + h * 0.45, trabaja(a) ? 115 : enObra(a) ? 70 : 90, trabaja(a) ? 1 : enObra(a) ? 0.45 : 0.75);
    }
    for (const [vx, vw] of P.ventanas) hueco(vx + vw / 2, 30, vw * 0.7, 0.5);
    hueco(P.neon[0], P.neon[1], 150, 0.45);
    gs.globalCompositeOperation = "source-over";
    const vin = gs.createRadialGradient(P.w / 2, P.h / 2, Math.min(P.w, P.h) * 0.35, P.w / 2, P.h / 2, Math.max(P.w, P.h) * 0.75);
    vin.addColorStop(0, "rgba(0,0,0,0)"); vin.addColorStop(1, "rgba(0,0,0,.55)");
    gs.fillStyle = vin; gs.fillRect(0, 0, P.w, P.h);
  }

  // ---------- lo que se mueve (cada cuadro) ----------
  function pantalla(c, id, x, y, w, h, on) {
    caja(c, x - 2, y - 2, w + 4, h + 4, "#0a0a0c", 2);
    c.fillStyle = on ? "#0b1622" : "#0c0e12"; c.fillRect(x, y, w, h);
    if (!on) { c.fillStyle = "rgba(255,255,255,.05)"; c.fillRect(x + 2, y + 2, w * 0.4, 2); return; }
    const k = (t * 1.3) % 1;
    if (id === "ex_ramos") for (let i = 0; i < 4; i++) { const v = (i + Math.floor(t * 2)) % 4; c.fillStyle = [VERDE, AM, ROJO, VERDE][v]; c.fillRect(x + 3, y + 3 + i * 5, 3, 3); c.fillStyle = "#9fb0c3"; c.fillRect(x + 8, y + 4 + i * 5, w - 14 - (i * 7) % 12, 1.5); }
    if (id === "ex_archivista") for (let i = 0; i < 6; i++) { c.fillStyle = (Math.floor(t * 3) % 6) === i ? AM : ["#2d6a8a", VERDE, "#6b7280"][i % 3]; c.fillRect(x + 3 + (i % 3) * ((w - 6) / 3), y + 3 + Math.floor(i / 3) * 9, (w - 6) / 3 - 2, 7); }
    if (id === "ex_graficas") [[ROJO, 0.9], [AM, 0.5], [VERDE, 0.75], [AM, 0.35], [VERDE, 1]].forEach(([col, v], i) => { const hh = (h - 6) * v * Math.min(1, Math.max(0.05, k * 1.8 - i * 0.15)); c.fillStyle = col; c.fillRect(x + 4 + i * ((w - 8) / 5), y + h - 3 - hh, (w - 8) / 5 - 2, hh); });
    if (id === "ex_miniaturas") { c.fillStyle = "#9fb9c9"; c.fillRect(x + 4, y + 5, 12, 12); c.fillStyle = BLANCO; c.fillRect(x + 19, y + 5, w - 24, 4); c.fillStyle = AM; c.fillRect(x + 19, y + 11, (w - 24) * (0.5 + 0.5 * Math.sin(t * 3)), 4); }
    if (id === "ex_editor") { [[AM, 4], [VERDE, 9], [ROJO, 14]].forEach(([col, dy]) => { c.fillStyle = col; c.fillRect(x + 3, y + dy, w * 0.35, 3); c.fillRect(x + w * 0.42, y + dy, w * 0.4, 3); }); c.fillStyle = "#fff"; c.fillRect(x + 3 + (w - 6) * k, y + 2, 1.5, h - 4); }
    if (id === "ex_subtitulos") for (let i = 0; i < 4; i++) { const on2 = Math.floor(t * 2.5) % 4 === i; c.fillStyle = on2 ? AM : "#9fb0c3"; c.fillRect(x + 4, y + 4 + i * 5, on2 ? w - 8 : w - 14 - i * 4, 2); }
    if (id === "ex_guion") for (let i = 0; i < 4; i++) { const largo = i === 3 ? (w - 8) * ((t * 0.7) % 1) : w - 8 - (i * 9) % 14; c.fillStyle = i === 3 ? AM : "#c7d2de"; c.fillRect(x + 4, y + 4 + i * 5, largo, 1.8); }
    if (id === "ex_publicacion") { c.fillStyle = ROJO; c.fillRect(x + w / 2 - 6, y + 4, 12, 9); c.fillStyle = "#fff"; c.beginPath(); c.moveTo(x + w / 2 - 2, y + 6); c.lineTo(x + w / 2 + 3, y + 8.5); c.lineTo(x + w / 2 - 2, y + 11); c.fill(); c.fillStyle = VERDE; c.fillRect(x + 4, y + h - 5, (w - 8) * k, 2); }
  }
  function lluvia(c) {
    c.save(); c.strokeStyle = "rgba(170,200,255,.35)"; c.lineWidth = 0.8;
    for (const [vx, vw] of P.ventanas) {
      c.beginPath(); c.rect(vx, 9, vw, 42); c.clip();
      for (let i = 0; i < vw / 6; i++) {
        const sx = vx + ((i * 37 + Math.floor(t * 60) * 3) % vw), sy = 9 + ((i * 53 + t * 160) % 46);
        c.moveTo(sx, sy); c.lineTo(sx - 2, sy + 6);
      }
      c.stroke();
      c.restore(); c.save(); c.strokeStyle = "rgba(170,200,255,.35)"; c.lineWidth = 0.8;
    }
    c.restore();
  }
  function neon(c) {
    const [nx, ny] = P.neon;
    const parpadeo = !quieto && Math.sin(t * 0.9) > 0.985 && Math.floor(t * 20) % 2 ? 0.25 : 1;
    c.save(); c.textAlign = "center"; c.textBaseline = "middle";
    const tam = P === PLANOS.alto ? 40 : 46;
    c.font = `400 ${tam}px 'Bebas Neue', Impact, sans-serif`;
    c.globalAlpha = parpadeo;
    c.shadowColor = ROJO; c.shadowBlur = 18; c.fillStyle = "#ff6b74";
    c.fillText("¿QUIÉN MATÓ A…?", nx, ny);
    c.shadowBlur = 4; c.fillStyle = "#ffd9dc"; c.fillText("¿QUIÉN MATÓ A…?", nx, ny);
    c.globalAlpha = 1; c.shadowColor = AM; c.shadowBlur = 10; c.fillStyle = AM;
    c.font = `400 ${Math.round(tam * 0.38)}px 'Bebas Neue', Impact, sans-serif`;
    c.fillText("AGENCIA DE EXPEDIENTES", nx, ny + tam * 0.62);
    c.restore();
  }
  function cuadro() {
    if (!baseLista) pintarBase();
    g.setTransform(1, 0, 0, 1, 0, 0);
    g.drawImage(base, 0, 0);
    g.setTransform(escala * dpr, 0, 0, escala * dpr, 0, 0);
    lluvia(g);
    for (const id of Object.keys(P.cubs)) { // monitores y gente
      const a = agente(id);
      const [x, y] = P.cubs[id], [w, h] = P.cub, on = trabaja(a);
      pantalla(g, id, x + w / 2 - 22, y + 12, 44, 24, on);
      if (id === "ex_editor") pantalla(g, id, x + 14, y + 16, 18, 18, on);
      persona(g, x + w / 2, y + 62, a, { tecleo: on && !quieto, apagada: enObra(a) });
      if (on) { const k = (Math.sin(t * 6) + 1) / 2; g.fillStyle = `rgba(255,214,10,${0.5 + k * 0.4})`; g.beginPath(); g.arc(x + w - 28, y + 18, 3, 0, 7); g.fill(); }
    }
    const J = P.jefe, onJ = jefeTrabaja();
    persona(g, J.x + J.w / 2, J.y + 72, JEFE, { frente: true });
    if (onJ && Math.floor(t * 2) % 2 === 0) { g.fillStyle = ROJO; g.shadowColor = ROJO; g.shadowBlur = 12; g.fillRect(J.x + J.w - 38, J.y + 68, 22, 6); g.shadowBlur = 0; }
    g.setTransform(1, 0, 0, 1, 0, 0);
    g.drawImage(sombra, 0, 0); // la noche
    g.setTransform(escala * dpr, 0, 0, escala * dpr, 0, 0);
    neon(g); // el neón brilla sobre la oscuridad
    g.globalCompositeOperation = "lighter";
    for (const id of Object.keys(P.cubs)) { // brillo de los monitores encendidos
      const a = agente(id); if (!trabaja(a)) continue;
      const [x, y] = P.cubs[id], [w] = P.cub;
      const gr = g.createRadialGradient(x + w / 2, y + 26, 2, x + w / 2, y + 26, 46);
      gr.addColorStop(0, "rgba(80,160,255,.22)"); gr.addColorStop(1, "rgba(80,160,255,0)");
      g.fillStyle = gr; g.fillRect(x + w / 2 - 46, y - 20, 92, 92);
    }
    g.globalCompositeOperation = "source-over";
    if (elegido) { // marco del lugar elegido
      const r = rect(elegido);
      g.strokeStyle = AM; g.lineWidth = 2.5; g.setLineDash([8, 5]); g.strokeRect(r.x - 8, r.y - 10, r.w + 16, r.h + 16); g.setLineDash([]);
    }
  }
  const rect = (id) => (id === "jefe" ? P.jefe : { x: P.cubs[id][0], y: P.cubs[id][1], w: P.cub[0], h: P.cub[1] });

  // ---------- letreros y globos (HTML: texto nítido) ----------
  let capasHtml = "";
  function pintarCapas() {
    const ahora = Date.now() / 1000;
    const html = [...Object.keys(P.cubs), "jefe"].map((id) => {
      const a = agente(id), r = rect(id), ar = AREAS[id];
      const obra = enObra(a);
      const nx = (r.x + r.w / 2) / P.w * 100, ny = (id === "jefe" ? r.y + r.h - 34 : r.y + r.h - 34) / P.h * 100;
      let s = `<span class="ag-letrero${obra ? " obra" : ""}" style="left:${nx}%;top:${ny}%">${ar.icono} ${esc(ar.cuarto)}<small>${obra ? "🚧 En obra" : esc(a?.nombre || "")}</small></span>`;
      const dice = id === "jefe" ? (jefeTrabaja() ? "Te toca grabar 🎙️" : "") : (a?.dice && (trabaja(a) || ahora - (a.dice_t || 0) < 60) ? a.dice : "");
      if (dice) {
        const gx = Math.min(78, Math.max(22, nx));
        s += `<span class="ag-globo" style="left:${gx}%;top:${(r.y - 8) / P.h * 100}%">${esc(dice)}</span>`;
      }
      return s;
    }).join("");
    if (html !== capasHtml) { capas.innerHTML = html; capasHtml = html; }
  }
  function pintarFicha() {
    if (!elegido) return;
    const a = agente(elegido), ar = AREAS[elegido];
    if (!a) return;
    const estado = elegido === "jefe" ? (jefeTrabaja() ? "🎙️ Te toca grabar la voz" : "👀 Revisa el panel: ahí apruebas todo")
      : trabaja(a) ? "⏳ Trabajando" : a.obra ? `🚧 ${a.obra}` : "😌 Libre";
    ficha.innerHTML = `<h3>${ar.icono} ${esc(ar.cuarto)} · ${esc(a.nombre)}</h3><p class="rol">${esc(a.rol)}</p>
      <p>${esc(estado)}${a.dice && elegido !== "jefe" ? ` — «${esc(a.dice)}»` : ""}</p><p class="pista">${esc(a.desc || "")}</p>`;
  }

  cv.addEventListener("click", (e) => {
    const b = cv.getBoundingClientRect();
    const px = (e.clientX - b.left) / b.width * P.w, py = (e.clientY - b.top) / b.height * P.h;
    const id = [...Object.keys(P.cubs), "jefe"].find((k) => { const r = rect(k); return px >= r.x - 6 && px < r.x + r.w + 6 && py >= r.y - 8 && py < r.y + r.h + 8; });
    elegido = id || null;
    if (!id) ficha.innerHTML = `<p class="pista">Toca un cubículo o tu despacho para ver quién está y qué hace.</p>`;
    pintarFicha(); cuadro();
  });

  // ---------- tamaño ----------
  function acomodar() {
    const ancho = cv.parentElement.clientWidth || innerWidth;
    P = ancho < 620 ? PLANOS.alto : PLANOS.ancho;
    dpr = Math.min(2, devicePixelRatio || 1);
    escala = ancho / P.w;
    cv.style.aspectRatio = `${P.w} / ${P.h}`;
    cv.width = Math.round(ancho * dpr); cv.height = Math.round(ancho * P.h / P.w * dpr);
    baseLista = false; capasHtml = "";
    cuadro(); pintarCapas();
  }
  let ultimoAncho = 0;
  addEventListener("resize", () => { const a = cv.parentElement.clientWidth; if (Math.abs(a - ultimoAncho) > 2) { ultimoAncho = a; acomodar(); } });

  // ---------- animación: 12 cuadros/s, solo con la pestaña a la vista ----------
  let reloj = null;
  function animar() {
    const vivo = !document.hidden && !quieto;
    if (vivo && !reloj) reloj = setInterval(() => { t += 1 / 12; cuadro(); }, 1000 / 12);
    if (!vivo && reloj) { clearInterval(reloj); reloj = null; }
  }
  document.addEventListener("visibilitychange", () => { animar(); if (!document.hidden) cargar(); });

  // ---------- datos ----------
  window.Oficina = { equipoExp: () => equipo }; // expedientes.js saca de aquí los nombres del equipo
  let firma = "";
  async function cargar() {
    if (document.hidden) return;
    try {
      const r = await fetch("/api/expedientes").then((x) => x.json());
      equipo = r.equipo || [];
      expedientes = r.expedientes || [];
      const chip = document.getElementById("ag-caso"), c = caso();
      if (chip) { chip.hidden = !c; if (c) chip.textContent = `Expediente #${String(c.numero).padStart(3, "0")} · ${c.marca}`; }
    } catch { /* sin conexión: se queda lo último */ }
    const nueva = JSON.stringify([equipo.map((a) => [a.id, a.estado, a.obra]), caso()?.numero, jefeTrabaja()]);
    if (nueva !== firma) { firma = nueva; baseLista = false; } // cambió quién trabaja: se redibuja la base
    cuadro(); pintarCapas(); pintarFicha(); animar();
  }
  setInterval(cargar, 4000);
  ultimoAncho = cv.parentElement.clientWidth;
  acomodar();
  document.fonts?.ready.then(() => { baseLista = false; cuadro(); });
  cargar();
})();
