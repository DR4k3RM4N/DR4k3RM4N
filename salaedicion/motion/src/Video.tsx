import React from "react";
import {
  AbsoluteFill, Easing, OffthreadVideo, Sequence, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig,
} from "remotion";
import { loadFont } from "@remotion/google-fonts/Montserrat";

const { fontFamily } = loadFont("normal", { weights: ["700", "900"], subsets: ["latin", "latin-ext"] });

// ---------- lo que recibe (props.json) ----------
export type Elemento = {
  tipo: "titulo" | "etiqueta" | "precio" | "flecha" | "circulo" | "link" | "emoji" | "contador";
  desde: number; // segundo en que aparece
  hasta: number; // segundo en que se va
  texto?: string; // titulo / etiqueta / link / emoji; en precio: el precio ("$299")
  antes?: string; // precio: el precio tachado ("$499")
  x?: number; // 0-1 (izquierda→derecha). flecha/círculo: a dónde apuntan
  y?: number; // 0-1 (arriba→abajo)
  tamano?: number; // escala (1 = normal)
  color?: string; // color de acento (#RRGGBB)
  angulo?: number; // flecha: de dónde viene, en grados (0 = desde la izquierda, 90 = desde arriba)
  icono?: string; // etiqueta: emoji al inicio ("✅", "🔥")
  hastaNumero?: number; // contador: a qué número llega
};

export type Palabra = { w: string; t: number; d: number };

export type Subtitulos = {
  palabras: Palabra[]; // las de tu voz con sus tiempos (herramientas.py transcribir)
  estilo?: "pop" | "karaoke" | "caja"; // pop: la palabra salta; karaoke: se pinta; caja: cajita de color detrás
  y?: number; // 0-1, altura (0.72 por defecto)
  color?: string; // texto
  resaltado?: string; // palabra que se dice
  mayusculas?: boolean;
  porGrupo?: number; // palabras a la vez (3)
  emojis?: Record<string, string>; // palabra → emoji que salta encima ("dinero": "💰")
};

export type PropsVideo = {
  fondo: string; // nombre del video base dentro de --public-dir (tus cortes ya hechos, con su audio)
  duracion: number; // segundos
  ancho?: number; alto?: number; fps?: number;
  elementos?: Elemento[];
  subtitulos?: Subtitulos | null;
  acento?: string; // color de marca para todo
  textos?: { borde?: number; sombra?: boolean; colorBorde?: string }; // borde: 0 = sin contorno, 1 normal, 1.5 grueso
};

export const ejemplo: PropsVideo = {
  fondo: "", duracion: 6, acento: "#FFD23F",
  elementos: [
    { tipo: "titulo", desde: 0, hasta: 2.5, texto: "ESTO CAMBIÓ MI COCINA", y: 0.18 },
    { tipo: "etiqueta", desde: 1, hasta: 5, texto: "Se carga en 2 horas", icono: "⚡", y: 0.42 },
    { tipo: "precio", desde: 2.5, hasta: 6, texto: "$299", antes: "$499", y: 0.3 },
    { tipo: "circulo", desde: 3, hasta: 5, x: 0.5, y: 0.6 },
    { tipo: "flecha", desde: 3, hasta: 5, x: 0.5, y: 0.6, angulo: 200 },
    { tipo: "link", desde: 4, hasta: 6, texto: "Link aquí 👇" },
  ],
  subtitulos: {
    estilo: "pop", emojis: { cocina: "🍳" },
    palabras: "esta cosa me cambió la cocina por completo".split(" ").map((w, i) => ({ w, t: 0.2 + i * 0.4, d: 0.35 })),
  },
};

// ---------- ayudas ----------
const sombra = "0 6px 0 rgba(0,0,0,.35), 0 10px 30px rgba(0,0,0,.45)";
const ESTILO = { borde: 1, sombra: true, colorBorde: "#000" }; // lo pone <Video> con props.textos
const sombraTexto = () => (ESTILO.sombra ? sombra : "none");
const borde = (px: number) => `${px * ESTILO.borde}px ${ESTILO.colorBorde}`;

const useEntrada = (dur: number) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const entra = spring({ frame: f, fps, config: { damping: 12, stiffness: 160, mass: 0.7 } });
  const sale = interpolate(f, [dur - 8, dur], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return { f, fps, entra, sale };
};

const Posicion: React.FC<{ x?: number; y?: number; children: React.ReactNode }> = ({ x = 0.5, y = 0.5, children }) => (
  <div style={{ position: "absolute", left: `${x * 100}%`, top: `${y * 100}%`, transform: "translate(-50%, -50%)" }}>{children}</div>
);

// ---------- piezas ----------
const Titulo: React.FC<{ e: Elemento; dur: number; acento: string }> = ({ e, dur, acento }) => {
  const { f, fps, entra, sale } = useEntrada(dur);
  const palabras = (e.texto || "").split(" ");
  return (
    <Posicion x={e.x} y={e.y ?? 0.18}>
      <div style={{ width: 960, textAlign: "center", opacity: sale, transform: `scale(${(0.6 + 0.4 * entra) * (e.tamano || 1)})` }}>
        {palabras.map((p, i) => {
          const s = spring({ frame: f - i * 3, fps, config: { damping: 11, stiffness: 180 } });
          const marcada = i === palabras.length - 1 || /[!¡]/.test(p);
          return (
            <span key={i} style={{
              display: "inline-block", margin: "0 12px", fontFamily, fontWeight: 900, fontSize: 96, lineHeight: 1.05,
              color: marcada ? e.color || acento : "#fff", WebkitTextStroke: borde(6), paintOrder: "stroke fill",
              textShadow: sombraTexto(), transform: `translateY(${(1 - s) * 60}px) rotate(${(1 - s) * -6}deg)`, opacity: s,
            }}>{p}</span>
          );
        })}
      </div>
    </Posicion>
  );
};

const Etiqueta: React.FC<{ e: Elemento; dur: number; acento: string }> = ({ e, dur, acento }) => {
  const { entra, sale } = useEntrada(dur);
  const desdeIzq = (e.x ?? 0.5) <= 0.5;
  return (
    <Posicion x={e.x} y={e.y ?? 0.4}>
      <div style={{
        display: "flex", alignItems: "center", gap: 18, padding: "22px 36px", borderRadius: 999, background: "#fff",
        boxShadow: `0 0 0 6px ${e.color || acento}, ${sombra}`, fontFamily, fontWeight: 800, fontSize: 56, color: "#111",
        whiteSpace: "nowrap", opacity: sale,
        transform: `translateX(${(1 - entra) * (desdeIzq ? -700 : 700)}px) scale(${e.tamano || 1})`,
      }}>
        {e.icono ? <span style={{ fontSize: 64 }}>{e.icono}</span> : null}
        <span>{e.texto}</span>
      </div>
    </Posicion>
  );
};

const Precio: React.FC<{ e: Elemento; dur: number; acento: string }> = ({ e, dur, acento }) => {
  const { f, fps, entra, sale } = useEntrada(dur);
  const tacha = interpolate(f, [6, 16], [0, 100], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const late = 1 + 0.06 * Math.sin((f / fps) * Math.PI * 2.4);
  return (
    <Posicion x={e.x} y={e.y ?? 0.3}>
      <div style={{ textAlign: "center", opacity: sale, transform: `scale(${(0.3 + 0.7 * entra) * (e.tamano || 1)}) rotate(-4deg)` }}>
        {e.antes ? (
          <div style={{ position: "relative", display: "inline-block", fontFamily, fontWeight: 800, fontSize: 64, color: "#fff",
            WebkitTextStroke: borde(4), paintOrder: "stroke fill", textShadow: sombraTexto() }}>
            {e.antes}
            <div style={{ position: "absolute", left: 0, top: "52%", height: 10, width: `${tacha}%`, background: "#ff2d55",
              borderRadius: 6, transform: "rotate(-8deg)" }} />
          </div>
        ) : null}
        <div style={{ fontFamily, fontWeight: 900, fontSize: 150, color: "#111", background: e.color || acento, padding: "6px 40px",
          borderRadius: 28, boxShadow: sombra, transform: `scale(${late})` }}>{e.texto}</div>
      </div>
    </Posicion>
  );
};

const Flecha: React.FC<{ e: Elemento; dur: number; acento: string }> = ({ e, dur, acento }) => {
  const { f, sale } = useEntrada(dur);
  const largo = 260 * (e.tamano || 1);
  const dibuja = interpolate(f, [0, 10], [0, 1], { extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) });
  const vaiven = 14 * Math.sin(f / 5);
  const ang = ((e.angulo ?? 200) * Math.PI) / 180; // de dónde viene la flecha
  const dx = Math.cos(ang), dy = Math.sin(ang);
  const color = e.color || acento;
  return (
    <Posicion x={e.x} y={e.y}>
      <svg width={largo * 2 + 80} height={largo * 2 + 80} style={{ overflow: "visible", opacity: sale,
        transform: `translate(${-dx * vaiven}px, ${-dy * vaiven}px)` }} viewBox={`${-largo - 40} ${-largo - 40} ${largo * 2 + 80} ${largo * 2 + 80}`}>
        <g transform={`rotate(${(e.angulo ?? 200) + 180})`}>
          <line x1={-largo - 30} y1={0} x2={-largo - 30 + largo * dibuja} y2={0} stroke="#000" strokeWidth={34} strokeLinecap="round" />
          <line x1={-largo - 30} y1={0} x2={-largo - 30 + largo * dibuja} y2={0} stroke={color} strokeWidth={22} strokeLinecap="round" />
          {dibuja > 0.9 ? (
            <polygon points={`${-30},0 ${-100},-55 ${-100},55`} fill={color} stroke="#000" strokeWidth={8} strokeLinejoin="round" />
          ) : null}
        </g>
      </svg>
    </Posicion>
  );
};

const Circulo: React.FC<{ e: Elemento; dur: number; acento: string }> = ({ e, dur, acento }) => {
  const { f, sale } = useEntrada(dur);
  const r = 170 * (e.tamano || 1);
  const total = 2 * Math.PI * r;
  const dibuja = interpolate(f, [0, 14], [0, 1], { extrapolateRight: "clamp", easing: Easing.inOut(Easing.cubic) });
  return (
    <Posicion x={e.x} y={e.y}>
      <svg width={r * 2 + 60} height={r * 2 + 60} style={{ opacity: sale, overflow: "visible" }}>
        <ellipse cx={r + 30} cy={r + 30} rx={r} ry={r * 0.86} fill="none" stroke={e.color || acento} strokeWidth={16}
          strokeLinecap="round" strokeDasharray={total} strokeDashoffset={total * (1 - dibuja)}
          transform={`rotate(-100 ${r + 30} ${r + 30})`} style={{ filter: "drop-shadow(0 4px 6px rgba(0,0,0,.6))" }} />
      </svg>
    </Posicion>
  );
};

const Link: React.FC<{ e: Elemento; dur: number; acento: string }> = ({ e, dur, acento }) => {
  const { f, entra, sale } = useEntrada(dur);
  const brinco = Math.abs(Math.sin(f / 6)) * 22;
  return (
    <Posicion x={e.x ?? 0.32} y={e.y ?? 0.86}>
      <div style={{ fontFamily, fontWeight: 900, fontSize: 64, color: "#111", background: e.color || acento, padding: "20px 44px",
        borderRadius: 999, boxShadow: `0 0 0 6px #fff, ${sombra}`, whiteSpace: "nowrap", opacity: sale,
        transform: `translateY(${(1 - entra) * 200 - brinco}px) scale(${e.tamano || 1})` }}>
        {e.texto || "🛒 Link aquí"}
      </div>
    </Posicion>
  );
};

const Emoji: React.FC<{ e: Elemento; dur: number }> = ({ e, dur }) => {
  const { f, entra, sale } = useEntrada(dur);
  return (
    <Posicion x={e.x} y={e.y ?? 0.3}>
      <div style={{ fontSize: 180 * (e.tamano || 1), opacity: sale, transform: `scale(${entra}) rotate(${Math.sin(f / 4) * 10}deg)`,
        filter: "drop-shadow(0 8px 10px rgba(0,0,0,.5))" }}>{e.texto}</div>
    </Posicion>
  );
};

const Contador: React.FC<{ e: Elemento; dur: number; acento: string }> = ({ e, dur, acento }) => {
  const { f, entra, sale } = useEntrada(dur);
  const n = Math.round(interpolate(f, [0, Math.min(dur - 10, 40)], [0, e.hastaNumero ?? 100], {
    extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) }));
  return (
    <Posicion x={e.x} y={e.y ?? 0.3}>
      <div style={{ fontFamily, fontWeight: 900, fontSize: 160 * (e.tamano || 1), color: e.color || acento, WebkitTextStroke: borde(8),
        paintOrder: "stroke fill", textShadow: sombraTexto(), opacity: sale, transform: `scale(${0.5 + 0.5 * entra})` }}>
        {(e.texto || "{n}").replace("{n}", n.toLocaleString("es-MX"))}
      </div>
    </Posicion>
  );
};

// ---------- subtítulos con estilo ----------
const Subs: React.FC<{ s: Subtitulos; acento: string }> = ({ s, acento }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = f / fps;
  const n = Math.max(1, s.porGrupo || 3);
  const grupos: Palabra[][] = [];
  for (const p of s.palabras || []) {
    const g = grupos[grupos.length - 1];
    const anterior = g ? g[g.length - 1] : null;
    if (!g || g.length >= n || (anterior && p.t - (anterior.t + anterior.d) > 0.6) || /[.?!]$/.test(anterior?.w || "")) grupos.push([p]);
    else g.push(p);
  }
  const g = grupos.find((x) => t >= x[0].t - 0.05 && t < x[x.length - 1].t + x[x.length - 1].d + 0.25);
  if (!g) return null;
  const estilo = s.estilo || "pop";
  const resaltado = s.resaltado || acento;
  const emojis = s.emojis || {};
  return (
    <Posicion y={s.y ?? 0.72}>
      <div style={{ width: 980, textAlign: "center", lineHeight: 1.15 }}>
        {g.map((p, i) => {
          const activa = t >= p.t && t < p.t + p.d + 0.08;
          const dicha = t >= p.t;
          const s2 = spring({ frame: f - Math.round(p.t * fps), fps, config: { damping: 10, stiffness: 220, mass: 0.5 } });
          const limpia = p.w.toLowerCase().replace(/[^\p{L}\p{N}]/gu, "");
          const emoji = emojis[limpia];
          const texto = s.mayusculas === false ? p.w : p.w.toUpperCase();
          return (
            <span key={i} style={{ position: "relative", display: "inline-block", margin: "0 18px" }}>
              {emoji && dicha ? (
                <span style={{ position: "absolute", left: "50%", top: -120, fontSize: 110,
                  transform: `translateX(-50%) scale(${s2})` }}>{emoji}</span>
              ) : null}
              <span style={{
                display: "inline-block", fontFamily, fontWeight: 900, fontSize: 84,
                color: estilo === "caja" ? (activa ? "#111" : "#fff") : activa || (estilo === "karaoke" && dicha) ? resaltado : s.color || "#fff",
                background: estilo === "caja" && activa ? resaltado : "transparent", borderRadius: 14, padding: "0 12px",
                WebkitTextStroke: estilo === "caja" && activa ? "0px" : borde(7), paintOrder: "stroke fill", textShadow: sombraTexto(),
                transform: `scale(${estilo === "pop" && activa ? 1 + 0.18 * s2 : 1}) translateY(${dicha ? 0 : 6}px)`,
                opacity: estilo === "pop" && !dicha ? 0.85 : 1,
              }}>{texto}</span>
            </span>
          );
        })}
      </div>
    </Posicion>
  );
};

// ---------- el video ----------
export const Video: React.FC<PropsVideo> = (props) => {
  const { fps } = useVideoConfig();
  const acento = props.acento || "#FFD23F";
  ESTILO.borde = typeof props.textos?.borde === "number" ? Math.max(0, Math.min(2, props.textos.borde)) : 1;
  ESTILO.sombra = props.textos?.sombra !== false;
  ESTILO.colorBorde = props.textos?.colorBorde || "#000";
  const piezas: Record<string, React.FC<{ e: Elemento; dur: number; acento: string }>> = {
    titulo: Titulo, etiqueta: Etiqueta, precio: Precio, flecha: Flecha, circulo: Circulo, link: Link, contador: Contador,
    emoji: ({ e, dur }) => <Emoji e={e} dur={dur} />,
  };
  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      {props.fondo ? <OffthreadVideo src={staticFile(props.fondo)} /> : null}
      {(props.elementos || []).map((e, i) => {
        const Pieza = piezas[e.tipo];
        const desde = Math.round((e.desde || 0) * fps);
        const dur = Math.max(6, Math.round(((e.hasta || props.duracion) - (e.desde || 0)) * fps));
        return Pieza ? (
          <Sequence key={i} from={desde} durationInFrames={dur} layout="none">
            <AbsoluteFill><Pieza e={e} dur={dur} acento={acento} /></AbsoluteFill>
          </Sequence>
        ) : null;
      })}
      {props.subtitulos?.palabras?.length ? <Subs s={props.subtitulos} acento={acento} /> : null}
    </AbsoluteFill>
  );
};
