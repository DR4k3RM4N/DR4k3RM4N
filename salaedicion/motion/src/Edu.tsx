// 🎬 Edu IA: un video de YouTube completo, dirigido por Claude con un "guion de edición" (edu.json).
// Cada escena dura lo que dura su narración (la voz nunca se desfasa); Claude decide qué se ve encima:
// fondo con movimiento + capas animadas (texto cinético, celular, chat, datos, comparativas, sellos, mascota…).
import React from "react";
import {
  AbsoluteFill, Audio, Easing, Img, OffthreadVideo, Sequence, interpolate, spring, staticFile, useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { loadFont as cargarMontserrat } from "@remotion/google-fonts/Montserrat";
import { loadFont as cargarLuckiest } from "@remotion/google-fonts/LuckiestGuy";

const { fontFamily: MONT } = cargarMontserrat("normal", { weights: ["600", "800", "900"], subsets: ["latin", "latin-ext"] });
const { fontFamily: LUCK } = cargarLuckiest("normal", { weights: ["400"], subsets: ["latin", "latin-ext"] });

// ---------- lo que recibe (edu.json) ----------
export type Palabra = { w: string; t: number; d: number }; // t relativo al inicio de SU escena
export type Fondo = {
  tipo: "imagen" | "video" | "color" | "degradado";
  archivo?: string; // imagen o video (ruta dentro de la mesa)
  desde?: number; // video: segundo donde empieza
  movimiento?: "acercar" | "alejar" | "izquierda" | "derecha" | "fijo";
  color?: string; color2?: string;
  oscurecer?: number; // 0-0.8: oscurece para que se lean las capas
  desenfocar?: boolean; // imagen de fondo desenfocada (y la misma imagen nítida encima en tarjeta, si quieres)
  ajuste?: "cubrir" | "contener"; // contener = se ve completa (capturas verticales) sobre fondo desenfocado
};
export type Mensaje = { de: "ellos" | "yo"; texto: string };
export type Capa = {
  tipo: "texto" | "titulo_seccion" | "dato" | "celular" | "chat" | "resena" | "lista" | "comparativa" | "alerta" |
    "sello" | "flecha" | "circulo" | "imagen" | "mascota" | "emoji" | "zoom_golpe" | "sacudida" | "destello" | "cintillo";
  desde: number; // segundos desde el inicio de la escena
  hasta?: number; // segundos desde el inicio de la escena (por defecto: fin de la escena)
  texto?: string; textos?: string[]; titulo?: string;
  numero?: number; prefijo?: string; sufijo?: string; decimales?: number;
  archivo?: string; nombre?: string; mensajes?: Mensaje[];
  izquierda?: { titulo: string; puntos: string[] }; derecha?: { titulo: string; puntos: string[] };
  estrellas?: number; usuario?: string;
  x?: number; y?: number; tamano?: number; color?: string; estilo?: string; lado?: "izquierda" | "derecha"; angulo?: number;
};
export type Escena = {
  audio?: string; duracion: number; palabras?: Palabra[]; fondo?: Fondo; capas?: Capa[];
  transicion?: "corte" | "zoom" | "barrido" | "destello" | "deslizar";
  sfx?: { archivo: string; desde: number; volumen?: number }[];
};
export type EduProps = {
  ancho?: number; alto?: number; fps?: number;
  acento?: string; acento2?: string; peligro?: string;
  escenas: Escena[];
  musica?: { archivo: string; volumen?: number } | null;
  subtitulos?: { activar?: boolean; estilo?: "pop" | "karaoke" | "caja"; y?: number; porGrupo?: number; resaltado?: string; mayusculas?: boolean };
  barra?: boolean;
};

export const ejemploEdu: EduProps = {
  acento: "#FFD23F", escenas: [{ duracion: 4, fondo: { tipo: "degradado", color: "#1b1035", color2: "#7b2cbf" },
    capas: [{ tipo: "texto", desde: 0.2, texto: "ESTA APP TE PROMETE $500", y: 0.45 }] }],
};
export const duracionEdu = (p: EduProps) => (p.escenas || []).reduce((a, e) => a + Math.max(0.5, e.duracion || 0), 0);

// ---------- ayudas ----------
const SOMBRA = "0 8px 0 rgba(0,0,0,.35), 0 14px 40px rgba(0,0,0,.5)";
const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
const src = (archivo?: string) => (archivo ? (/^https?:/.test(archivo) ? archivo : staticFile(archivo)) : "");

const useCapa = (dur: number) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const entra = spring({ frame: f, fps, config: { damping: 13, stiffness: 170, mass: 0.7 } });
  const sale = interpolate(f, [dur - 7, dur], [1, 0], clamp);
  return { f, fps, entra, sale };
};

const En: React.FC<{ x?: number; y?: number; children: React.ReactNode; style?: React.CSSProperties }> = ({ x = 0.5, y = 0.5, children, style }) => (
  <div style={{ position: "absolute", left: `${x * 100}%`, top: `${y * 100}%`, transform: "translate(-50%, -50%)", ...style }}>{children}</div>
);

// una capa puesta a un lado (x lejos del centro) se hace angosta para no encimarse con lo del otro lado
const lado = (c: Capa) => c.x !== undefined && Math.abs(c.x - 0.5) > 0.12;

const contorno = (px: number, color = "#000"): React.CSSProperties => ({ WebkitTextStroke: `${px}px ${color}`, paintOrder: "stroke fill" });

// ---------- fondos ----------
const FondoEscena: React.FC<{ fondo?: Fondo; dur: number; acento: string }> = ({ fondo, dur, acento }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const fo = fondo || { tipo: "degradado" };
  const p = interpolate(f, [0, dur], [0, 1], clamp);
  const mov = fo.movimiento || "acercar";
  const escala = mov === "acercar" ? 1.04 + 0.12 * p : mov === "alejar" ? 1.16 - 0.12 * p : mov === "fijo" ? 1 : 1.12;
  const dx = mov === "izquierda" ? 40 - 80 * p : mov === "derecha" ? -40 + 80 * p : 0;
  const capaOscura = fo.oscurecer ? <AbsoluteFill style={{ background: `rgba(0,0,0,${Math.min(0.85, fo.oscurecer)})` }} /> : null;
  if (fo.tipo === "color") return <AbsoluteFill style={{ background: fo.color || "#111" }} />;
  if (fo.tipo === "degradado" || !fo.archivo) {
    const ang = 120 + 30 * Math.sin(f / (fps * 3));
    return (
      <AbsoluteFill style={{ background: `linear-gradient(${ang}deg, ${fo.color || "#0f172a"}, ${fo.color2 || acento}55)` }}>
        <AbsoluteFill style={{ backgroundImage: "radial-gradient(rgba(255,255,255,.07) 2px, transparent 2px)", backgroundSize: "46px 46px",
          transform: `translateY(${(f * 0.6) % 46}px)` }} />
        {capaOscura}
      </AbsoluteFill>
    );
  }
  const transform = `scale(${escala}) translateX(${dx}px)`;
  if (fo.tipo === "video") {
    const inicio = Math.round((fo.desde || 0) * fps);
    if (fo.ajuste === "contener") {  // grabación vertical del cel: completa al centro, sobre su versión desenfocada
      return (
        <AbsoluteFill style={{ background: "#000" }}>
          <OffthreadVideo src={src(fo.archivo)} muted startFrom={inicio}
            style={{ position: "absolute", width: "100%", height: "100%", objectFit: "cover", filter: "blur(36px) brightness(.5)",
              transform: "scale(1.15)" }} />
          <OffthreadVideo src={src(fo.archivo)} muted startFrom={inicio}
            style={{ position: "absolute", width: "100%", height: "100%", objectFit: "contain", transform,
              filter: "drop-shadow(0 20px 40px rgba(0,0,0,.6))" }} />
          {capaOscura}
        </AbsoluteFill>
      );
    }
    return (
      <AbsoluteFill>
        <OffthreadVideo src={src(fo.archivo)} muted startFrom={inicio}
          style={{ width: "100%", height: "100%", objectFit: "cover", transform }} />
        {capaOscura}
      </AbsoluteFill>
    );
  }
  const contener = fo.ajuste === "contener";
  return (
    <AbsoluteFill style={{ background: "#000" }}>
      {(contener || fo.desenfocar) ? (
        <Img src={src(fo.archivo)} style={{ position: "absolute", width: "100%", height: "100%", objectFit: "cover",
          filter: "blur(40px) brightness(.55)", transform: "scale(1.2)" }} />
      ) : null}
      {!fo.desenfocar || contener ? (
        <Img src={src(fo.archivo)} style={{ position: "absolute", width: "100%", height: "100%", objectFit: contener ? "contain" : "cover",
          transform }} />
      ) : null}
      {capaOscura}
    </AbsoluteFill>
  );
};

// ---------- capas ----------
type P = { c: Capa; dur: number; acento: string; acento2: string; peligro: string };

const Texto: React.FC<P> = ({ c, dur, acento }) => {
  const { f, fps, sale } = useCapa(dur);
  const palabras = (c.texto || "").split(/\s+/).filter(Boolean);
  const estilo = c.estilo || "pop";
  const t = (c.tamano || 1) * (palabras.length > 6 ? 92 : 120);
  if (estilo === "maquina") {
    const n = Math.floor(interpolate(f, [0, Math.min(dur - 6, (c.texto || "").length * 1.4)], [0, (c.texto || "").length], clamp));
    return (
      <En x={c.x} y={c.y ?? 0.45}>
        <div style={{ width: 1600, textAlign: "center", fontFamily: MONT, fontWeight: 900, fontSize: t * 0.8, color: "#fff",
          ...contorno(8), textShadow: SOMBRA, opacity: sale }}>
          {(c.texto || "").slice(0, n)}<span style={{ opacity: f % 16 < 8 ? 1 : 0, color: acento }}>|</span>
        </div>
      </En>
    );
  }
  return (
    <En x={c.x} y={c.y ?? 0.45}>
      <div style={{ width: lado(c) ? 900 : 1650, textAlign: "center", lineHeight: 1.05, opacity: sale }}>
        {palabras.map((p, i) => {
          const s = spring({ frame: f - i * (estilo === "golpe" ? 5 : 3), fps, config: { damping: estilo === "golpe" ? 8 : 11, stiffness: 200 } });
          const marcada = /[$%!¡?¿0-9]/.test(p) || i === palabras.length - 1;
          const escala = estilo === "golpe" ? 2.2 - 1.2 * s : 0.4 + 0.6 * s;
          return (
            <span key={i} style={{ display: "inline-block", margin: "0 16px", fontFamily: LUCK, fontSize: t,
              color: marcada ? c.color || acento : "#fff", ...contorno(9), textShadow: SOMBRA, opacity: Math.min(1, s * 1.4),
              transform: `translateY(${(1 - s) * 70}px) scale(${escala}) rotate(${(1 - s) * -8}deg)` }}>{p}</span>
          );
        })}
      </div>
    </En>
  );
};

const TituloSeccion: React.FC<P> = ({ c, dur, acento }) => {
  const { f, fps, entra, sale } = useCapa(dur);
  const barra = interpolate(f, [0, 12], [0, 1], { ...clamp, easing: Easing.out(Easing.cubic) });
  const t2 = spring({ frame: f - 6, fps, config: { damping: 12 } });
  return (
    <AbsoluteFill style={{ opacity: sale }}>
      <div style={{ position: "absolute", left: 0, top: "38%", height: "24%", width: `${barra * 100}%`, background: acento,
        transform: "skewY(-3deg)", boxShadow: SOMBRA }} />
      <En y={0.5}>
        <div style={{ display: "flex", alignItems: "center", gap: 40, transform: `scale(${0.6 + 0.4 * entra})` }}>
          {c.texto ? <div style={{ fontFamily: LUCK, fontSize: 230, color: "#fff", ...contorno(12), textShadow: SOMBRA }}>{c.texto}</div> : null}
          <div style={{ fontFamily: LUCK, fontSize: 120, color: "#111", opacity: t2, transform: `translateX(${(1 - t2) * 200}px)`,
            maxWidth: 1300, lineHeight: 1 }}>{c.titulo}</div>
        </div>
      </En>
    </AbsoluteFill>
  );
};

const Dato: React.FC<P> = ({ c, dur, acento }) => {
  const { f, entra, sale } = useCapa(dur);
  const n = interpolate(f, [0, Math.max(8, Math.min(dur - 10, 36))], [0, c.numero ?? 0], { ...clamp, easing: Easing.out(Easing.cubic) });
  const numero = n.toLocaleString("es-MX", { minimumFractionDigits: c.decimales || 0, maximumFractionDigits: c.decimales || 0 });
  return (
    <En x={c.x} y={c.y ?? 0.45}>
      <div style={{ textAlign: "center", opacity: sale, transform: `scale(${(0.4 + 0.6 * entra) * (c.tamano || 1)})` }}>
        <div style={{ fontFamily: LUCK, fontSize: 260, color: c.color || acento, ...contorno(14), textShadow: SOMBRA, lineHeight: 1 }}>
          {c.prefijo || ""}{numero}{c.sufijo || ""}
        </div>
        {c.texto ? <div style={{ marginTop: 24, display: "inline-block", fontFamily: MONT, fontWeight: 900, fontSize: 64, color: "#111",
          background: "#fff", padding: "10px 34px", borderRadius: 18, boxShadow: SOMBRA }}>{c.texto}</div> : null}
      </div>
    </En>
  );
};

const Celular: React.FC<P> = ({ c, dur }) => {
  const { f, fps, entra, sale } = useCapa(dur);
  const { height } = useVideoConfig();
  const alto = height * 0.86 * (c.tamano || 1);
  const ancho = alto * 0.49;
  const esVideo = /\.(mp4|mov|webm|mkv)$/i.test(c.archivo || "");
  const flota = Math.sin(f / (fps * 0.9)) * 8;
  return (
    <En x={c.x ?? 0.5} y={0.5} style={{ opacity: sale }}>
      <div style={{ width: ancho, height: alto, borderRadius: alto * 0.07, background: "#0b0b0f", padding: alto * 0.018,
        boxShadow: `0 0 0 6px #2a2a33, ${SOMBRA}`, transform: `translateY(${(1 - entra) * height + flota}px) rotate(${(c.angulo ?? 0) * (1 - entra) + (c.angulo ?? 0) * 0.2}deg)` }}>
        <div style={{ width: "100%", height: "100%", borderRadius: alto * 0.055, overflow: "hidden", background: "#000", position: "relative" }}>
          {c.archivo ? (esVideo
            ? <OffthreadVideo src={src(c.archivo)} muted startFrom={Math.round((c.numero || 0) * fps)} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
            : <Img src={src(c.archivo)} style={{ width: "100%", height: "100%", objectFit: "cover" }} />) : null}
          <div style={{ position: "absolute", top: alto * 0.012, left: "50%", width: ancho * 0.3, height: alto * 0.028, borderRadius: 99,
            background: "#0b0b0f", transform: "translateX(-50%)" }} />
        </div>
      </div>
    </En>
  );
};

const Chat: React.FC<P> = ({ c, dur }) => {
  const { f, fps, entra, sale } = useCapa(dur);
  const msgs = c.mensajes || [];
  const cada = Math.max(10, Math.min(45, (dur - 12) / Math.max(1, msgs.length)));
  const visibles = msgs.filter((_, i) => f >= 6 + i * cada);
  return (
    <En x={c.x ?? 0.5} y={0.5} style={{ opacity: sale }}>
      <div style={{ width: 900, minHeight: 420, borderRadius: 40, overflow: "hidden", background: "#efeae2", boxShadow: SOMBRA,
        transform: `scale(${(0.5 + 0.5 * entra) * (c.tamano || 1)})`, display: "flex", flexDirection: "column" }}>
        <div style={{ background: "#075e54", color: "#fff", padding: "26px 34px", fontFamily: MONT, fontWeight: 800, fontSize: 40,
          display: "flex", alignItems: "center", gap: 20 }}>
          <div style={{ width: 70, height: 70, borderRadius: 99, background: "#cfd8dc", display: "grid", placeItems: "center", fontSize: 40 }}>👤</div>
          {c.nombre || c.titulo || "Desconocido"}
        </div>
        <div style={{ flex: 1, padding: 30, display: "flex", flexDirection: "column", justifyContent: "flex-end", gap: 18,
          minHeight: 300 }}>
          {visibles.slice(-6).map((m, i, arr) => {
            const k = msgs.indexOf(m);
            const s = spring({ frame: f - 6 - k * cada, fps, config: { damping: 14, stiffness: 200 } });
            const yo = m.de === "yo";
            return (
              <div key={k} style={{ alignSelf: yo ? "flex-end" : "flex-start", maxWidth: "82%", background: yo ? "#d9fdd3" : "#fff",
                borderRadius: 22, padding: "18px 26px", fontFamily: MONT, fontWeight: 700, fontSize: 46, color: "#111", lineHeight: 1.25,
                boxShadow: "0 2px 0 rgba(0,0,0,.12)", transform: `scale(${s}) translateY(${(1 - s) * 40}px)`,
                transformOrigin: yo ? "right bottom" : "left bottom", opacity: i < arr.length - 4 ? 0.6 : 1 }}>{m.texto}</div>
            );
          })}
        </div>
      </div>
    </En>
  );
};

const Resena: React.FC<P> = ({ c, dur, acento }) => {
  const { f, entra, sale } = useCapa(dur);
  const texto = c.texto || "";
  const n = Math.floor(interpolate(f, [8, Math.max(9, Math.min(dur - 10, 8 + texto.length * 0.9))], [0, texto.length], clamp));
  const estrellas = Math.max(0, Math.min(5, Math.round(c.estrellas ?? 1)));
  return (
    <En x={c.x} y={c.y ?? 0.5} style={{ opacity: sale }}>
      <div style={{ width: 1300, background: "#fff", borderRadius: 34, padding: "40px 50px", boxShadow: SOMBRA,
        transform: `translateX(${(1 - entra) * 900}px) rotate(${(1 - entra) * 6 - 1.5}deg)` }}>
        <div style={{ display: "flex", alignItems: "center", gap: 22, fontFamily: MONT, fontWeight: 800, fontSize: 40, color: "#333" }}>
          <div style={{ width: 74, height: 74, borderRadius: 99, background: acento, display: "grid", placeItems: "center", fontSize: 40 }}>
            {(c.usuario || "U").slice(0, 1).toUpperCase()}</div>
          {c.usuario || "Usuario"}
          <span style={{ marginLeft: "auto", fontSize: 54, letterSpacing: 4 }}>
            {"★★★★★".slice(0, estrellas)}<span style={{ color: "#ccc" }}>{"★★★★★".slice(estrellas)}</span></span>
        </div>
        <div style={{ marginTop: 24, fontFamily: MONT, fontWeight: 600, fontSize: 48, color: "#111", lineHeight: 1.3 }}>
          “{texto.slice(0, n)}{n < texto.length ? "▌" : "”"}</div>
      </div>
    </En>
  );
};

const Lista: React.FC<P> = ({ c, dur, acento }) => {
  const { f, fps, entra, sale } = useCapa(dur);
  const items = c.textos || [];
  const cada = Math.max(8, Math.min(40, (dur - 10) / Math.max(1, items.length)));
  return (
    <En x={c.x} y={c.y ?? 0.5} style={{ opacity: sale }}>
      <div style={{ width: lado(c) ? 820 : 1400, transform: `scale(${0.7 + 0.3 * entra})` }}>
        {c.titulo ? <div style={{ fontFamily: LUCK, fontSize: 96, color: c.color || acento, ...contorno(8), textShadow: SOMBRA, marginBottom: 20 }}>{c.titulo}</div> : null}
        {items.map((it, i) => {
          const s = spring({ frame: f - 6 - i * cada, fps, config: { damping: 13 } });
          return (
            <div key={i} style={{ display: "flex", alignItems: "center", gap: 26, margin: "16px 0", opacity: s,
              transform: `translateX(${(1 - s) * -300}px)` }}>
              <div style={{ minWidth: 86, height: 86, borderRadius: 22, background: c.color || acento, display: "grid", placeItems: "center",
                fontFamily: LUCK, fontSize: 54, color: "#111", boxShadow: SOMBRA }}>{c.estilo === "check" ? "✓" : c.estilo === "x" ? "✕" : i + 1}</div>
              <div style={{ fontFamily: MONT, fontWeight: 900, fontSize: 60, color: "#fff", ...contorno(7), textShadow: SOMBRA }}>{it}</div>
            </div>
          );
        })}
      </div>
    </En>
  );
};

const Comparativa: React.FC<P> = ({ c, dur, acento2, peligro }) => {
  const { f, fps, entra, sale } = useCapa(dur);
  const col = (lado: { titulo: string; puntos: string[] } | undefined, color: string, k: number) => {
    const s = spring({ frame: f - k * 10, fps, config: { damping: 13 } });
    const pts = lado?.puntos || [];
    return (
      <div style={{ flex: 1, alignSelf: "center", background: "#fff", borderRadius: 34, overflow: "hidden", boxShadow: SOMBRA, opacity: s,
        transform: `translateY(${(1 - s) * 300}px)` }}>
        <div style={{ background: color, padding: "26px 30px", fontFamily: LUCK, fontSize: 84, color: "#fff", textAlign: "center", ...contorno(4) }}>
          {lado?.titulo}</div>
        <div style={{ padding: "26px 40px 34px" }}>
          {pts.map((p, i) => {
            const v = interpolate(f, [16 + k * 10 + i * 12, 24 + k * 10 + i * 12], [0, 1], clamp);
            return <div key={i} style={{ fontFamily: MONT, fontWeight: 900, fontSize: 58, color: "#111", margin: "20px 0", opacity: v,
              transform: `translateX(${(1 - v) * 40}px)` }}>{k === 0 ? "✓" : "✕"} {p}</div>;
          })}
        </div>
      </div>
    );
  };
  return (
    <AbsoluteFill style={{ padding: "110px 120px", display: "flex", flexDirection: "row", gap: 60, opacity: sale,
      transform: `scale(${0.85 + 0.15 * entra})` }}>
      {col(c.izquierda, acento2, 0)}
      <div style={{ alignSelf: "center", fontFamily: LUCK, fontSize: 120, color: "#fff", ...contorno(10) }}>VS</div>
      {col(c.derecha, peligro, 1)}
    </AbsoluteFill>
  );
};

const Alerta: React.FC<P> = ({ c, dur, peligro }) => {
  const { f, entra, sale } = useCapa(dur);
  const late = 1 + 0.04 * Math.sin(f / 3);
  return (
    <AbsoluteFill style={{ opacity: sale }}>
      <AbsoluteFill style={{ boxShadow: `inset 0 0 ${120 + 60 * Math.abs(Math.sin(f / 5))}px ${peligro}` }} />
      <En y={c.y ?? 0.5}>
        <div style={{ display: "flex", alignItems: "center", gap: 30, background: c.color || peligro, padding: "30px 60px", borderRadius: 26,
          boxShadow: `0 0 0 8px #fff, ${SOMBRA}`, transform: `scale(${(0.3 + 0.7 * entra) * late}) rotate(-2deg)` }}>
          <span style={{ fontSize: 120 }}>⚠️</span>
          <span style={{ fontFamily: LUCK, fontSize: 130, color: "#fff", ...contorno(8), whiteSpace: "nowrap" }}>{c.texto || "¡CUIDADO!"}</span>
        </div>
      </En>
    </AbsoluteFill>
  );
};

const Sello: React.FC<P> = ({ c, dur, peligro }) => {
  const { f, fps, sale } = useCapa(dur);
  const s = spring({ frame: f, fps, config: { damping: 9, stiffness: 260, mass: 0.6 } });
  const color = c.color || peligro;
  return (
    <En x={c.x ?? 0.5} y={c.y ?? 0.5} style={{ opacity: sale }}>
      <div style={{ border: `16px solid ${color}`, borderRadius: 30, padding: "20px 60px", fontFamily: LUCK, fontSize: 170 * (c.tamano || 1),
        color, transform: `rotate(${c.angulo ?? -12}deg) scale(${2.6 - 1.6 * s})`, opacity: Math.min(1, s * 2), background: "rgba(255,255,255,.88)",
        boxShadow: SOMBRA, whiteSpace: "nowrap" }}>{c.texto || "ESTAFA"}</div>
    </En>
  );
};

const Imagen: React.FC<P> = ({ c, dur }) => {
  const { f, fps, entra, sale } = useCapa(dur);
  const { width } = useVideoConfig();
  const ancho = width * 0.42 * (c.tamano || 1);
  const izq = (c.lado || (c.x !== undefined && c.x < 0.5 ? "izquierda" : "derecha")) === "izquierda";
  return (
    <En x={c.x ?? (izq ? 0.27 : 0.73)} y={c.y ?? 0.5} style={{ opacity: sale }}>
      <Img src={src(c.archivo)} style={{ width: ancho, borderRadius: 28, border: "10px solid #fff", boxShadow: SOMBRA,
        transform: `translateX(${(1 - entra) * (izq ? -width : width)}px) rotate(${(izq ? -3 : 3) + Math.sin(f / (fps * 1.2)) * 1}deg)` }} />
    </En>
  );
};

const Mascota: React.FC<P> = ({ c, dur }) => {
  const { f, fps, entra, sale } = useCapa(dur);
  const { height } = useVideoConfig();
  const der = (c.lado || "derecha") === "derecha";
  const brinco = Math.abs(Math.sin(f / (fps * 0.28))) * 14;
  return (
    <div style={{ position: "absolute", bottom: -10, [der ? "right" : "left"]: 30, opacity: sale,
      transform: `translateY(${(1 - entra) * 500 - brinco}px) rotate(${Math.sin(f / 6) * 3}deg)` } as React.CSSProperties}>
      <Img src={src(c.archivo)} style={{ height: height * 0.5 * (c.tamano || 1), filter: "drop-shadow(0 12px 18px rgba(0,0,0,.5))",
        transform: der ? "none" : "scaleX(-1)" }} />
      {c.texto ? (
        <div style={{ position: "absolute", top: -40, [der ? "right" : "left"]: "70%", background: "#fff", borderRadius: 30,
          padding: "18px 28px", fontFamily: MONT, fontWeight: 900, fontSize: 44, color: "#111", whiteSpace: "nowrap", boxShadow: SOMBRA,
          transform: `scale(${entra})` } as React.CSSProperties}>{c.texto}</div>
      ) : null}
    </div>
  );
};

const Emoji: React.FC<P> = ({ c, dur }) => {
  const { f, entra, sale } = useCapa(dur);
  return (
    <En x={c.x ?? 0.8} y={c.y ?? 0.3}>
      <div style={{ fontSize: 200 * (c.tamano || 1), opacity: sale, transform: `scale(${entra}) rotate(${Math.sin(f / 4) * 10}deg)`,
        filter: "drop-shadow(0 10px 12px rgba(0,0,0,.5))" }}>{c.texto}</div>
    </En>
  );
};

const Flecha: React.FC<P> = ({ c, dur, acento }) => {
  const { f, sale } = useCapa(dur);
  const largo = 280 * (c.tamano || 1);
  const dibuja = interpolate(f, [0, 10], [0, 1], { ...clamp, easing: Easing.out(Easing.cubic) });
  const ang = c.angulo ?? 200;
  const vaiven = 14 * Math.sin(f / 5);
  const color = c.color || acento;
  return (
    <En x={c.x} y={c.y}>
      <svg width={largo * 2 + 80} height={largo * 2 + 80} style={{ overflow: "visible", opacity: sale }}
        viewBox={`${-largo - 40} ${-largo - 40} ${largo * 2 + 80} ${largo * 2 + 80}`}>
        <g transform={`rotate(${ang + 180}) translate(${vaiven}, 0)`}>
          <line x1={-largo - 30} y1={0} x2={-largo - 30 + largo * dibuja} y2={0} stroke="#000" strokeWidth={36} strokeLinecap="round" />
          <line x1={-largo - 30} y1={0} x2={-largo - 30 + largo * dibuja} y2={0} stroke={color} strokeWidth={22} strokeLinecap="round" />
          {dibuja > 0.9 ? <polygon points="-30,0 -105,-58 -105,58" fill={color} stroke="#000" strokeWidth={8} strokeLinejoin="round" /> : null}
        </g>
      </svg>
    </En>
  );
};

const Circulo: React.FC<P> = ({ c, dur, peligro }) => {
  const { f, sale } = useCapa(dur);
  const r = 180 * (c.tamano || 1);
  const total = 2 * Math.PI * r;
  const dibuja = interpolate(f, [0, 14], [0, 1], { ...clamp, easing: Easing.inOut(Easing.cubic) });
  return (
    <En x={c.x} y={c.y}>
      <svg width={r * 2 + 60} height={r * 2 + 60} style={{ opacity: sale, overflow: "visible" }}>
        <ellipse cx={r + 30} cy={r + 30} rx={r} ry={r * 0.82} fill="none" stroke={c.color || peligro} strokeWidth={18} strokeLinecap="round"
          strokeDasharray={total} strokeDashoffset={total * (1 - dibuja)} transform={`rotate(-100 ${r + 30} ${r + 30})`}
          style={{ filter: "drop-shadow(0 4px 6px rgba(0,0,0,.6))" }} />
      </svg>
    </En>
  );
};

const Cintillo: React.FC<P> = ({ c, dur, acento }) => {
  const { entra, sale } = useCapa(dur);
  return (
    <div style={{ position: "absolute", left: 80, bottom: 150, opacity: sale, transform: `translateX(${(1 - entra) * -1200}px)` }}>
      <div style={{ display: "inline-block", background: c.color || acento, padding: "14px 30px", fontFamily: MONT, fontWeight: 900, fontSize: 50,
        color: "#111", borderRadius: "16px 16px 0 0" }}>{c.titulo || ""}</div>
      <div style={{ background: "#fff", padding: "16px 30px", fontFamily: MONT, fontWeight: 800, fontSize: 44, color: "#111",
        borderRadius: "0 16px 16px 16px", boxShadow: SOMBRA }}>{c.texto}</div>
    </div>
  );
};

const PIEZAS: Record<string, React.FC<P>> = {
  texto: Texto, titulo_seccion: TituloSeccion, dato: Dato, celular: Celular, chat: Chat, resena: Resena, lista: Lista,
  comparativa: Comparativa, alerta: Alerta, sello: Sello, imagen: Imagen, mascota: Mascota, emoji: Emoji, flecha: Flecha,
  circulo: Circulo, cintillo: Cintillo,
};

// ---------- una escena ----------
const EscenaVideo: React.FC<{ e: Escena; dur: number; props: EduProps }> = ({ e, dur, props }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const acento = props.acento || "#FFD23F", acento2 = props.acento2 || "#22c55e", peligro = props.peligro || "#ef4444";
  const capas = e.capas || [];
  // efectos de cámara de la escena: zoom de golpe y sacudidas en sus tiempos
  let escala = 1, sx = 0, sy = 0;
  for (const c of capas) {
    const a = Math.round((c.desde || 0) * fps), b = Math.round(((c.hasta ?? (c.desde || 0) + 0.6)) * fps);
    if (c.tipo === "zoom_golpe" && f >= a && f <= b) {
      const s = spring({ frame: f - a, fps, config: { damping: 12, stiffness: 240 } });
      escala *= 1 + (c.tamano ?? 0.18) * s;
    }
    if (c.tipo === "sacudida" && f >= a && f <= b) {
      const fuerza = 16 * (c.tamano || 1) * (1 - (f - a) / Math.max(1, b - a));
      sx += Math.sin(f * 2.3) * fuerza; sy += Math.cos(f * 2.9) * fuerza;
    }
  }
  // entrada de la escena
  const tr = e.transicion || "corte";
  const ent = spring({ frame: f, fps, config: { damping: 15, stiffness: 180 } });
  if (tr === "zoom") escala *= 1.25 - 0.25 * ent;
  const deslizar = tr === "deslizar" ? (1 - ent) * 1920 : 0;
  const destellos = capas.filter((c) => c.tipo === "destello");
  return (
    <AbsoluteFill style={{ overflow: "hidden" }}>
      <AbsoluteFill style={{ transform: `translate(${sx + deslizar}px, ${sy}px) scale(${escala})` }}>
        <FondoEscena fondo={e.fondo} dur={dur} acento={acento} />
        {capas.map((c, i) => {
          const Pieza = PIEZAS[c.tipo];
          if (!Pieza) return null;
          const desde = Math.max(0, Math.round((c.desde || 0) * fps));
          const hasta = Math.min(dur, Math.round((c.hasta ?? e.duracion) * fps));
          const d = Math.max(8, hasta - desde);
          return (
            <Sequence key={i} from={desde} durationInFrames={d} layout="none">
              <AbsoluteFill><Pieza c={c} dur={d} acento={acento} acento2={acento2} peligro={peligro} /></AbsoluteFill>
            </Sequence>
          );
        })}
      </AbsoluteFill>
      {tr === "barrido" ? (
        <AbsoluteFill style={{ background: acento, transform: `translateX(${interpolate(f, [0, 9], [0, 105], clamp)}%) skewX(-12deg)` }} />
      ) : null}
      {tr === "destello" ? <AbsoluteFill style={{ background: "#fff", opacity: interpolate(f, [0, 7], [0.9, 0], clamp) }} /> : null}
      {destellos.map((c, i) => {
        const a = Math.round((c.desde || 0) * fps);
        return <AbsoluteFill key={`d${i}`} style={{ background: c.color || "#fff", opacity: interpolate(f, [a, a + 7], [0.85, 0], clamp) * (f >= a ? 1 : 0) }} />;
      })}
      {e.audio ? <Audio src={src(e.audio)} /> : null}
      {(e.sfx || []).map((s, i) => (
        <Sequence key={`s${i}`} from={Math.max(0, Math.round(s.desde * fps))} layout="none">
          <Audio src={src(s.archivo)} volume={s.volumen ?? 0.6} />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};

// ---------- subtítulos de todo el video ----------
const Subtitulos: React.FC<{ palabras: Palabra[]; props: EduProps }> = ({ palabras, props }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = props.subtitulos || {};
  const t = f / fps;
  const n = Math.max(1, s.porGrupo || 3);
  const grupos: Palabra[][] = [];
  for (const p of palabras) {
    const g = grupos[grupos.length - 1];
    const ant = g ? g[g.length - 1] : null;
    if (!g || g.length >= n || (ant && p.t - (ant.t + ant.d) > 0.5) || /[.?!,]$/.test(ant?.w || "")) grupos.push([p]);
    else g.push(p);
  }
  const g = grupos.find((x) => t >= x[0].t - 0.05 && t < x[x.length - 1].t + x[x.length - 1].d + 0.2);
  if (!g) return null;
  const estilo = s.estilo || "pop";
  const resaltado = s.resaltado || props.acento || "#FFD23F";
  return (
    <En y={s.y ?? 0.86}>
      <div style={{ width: 1700, textAlign: "center" }}>
        {g.map((p, i) => {
          const activa = t >= p.t && t < p.t + p.d + 0.06;
          const dicha = t >= p.t;
          const sp = spring({ frame: f - Math.round(p.t * fps), fps, config: { damping: 10, stiffness: 220, mass: 0.5 } });
          return (
            <span key={i} style={{ display: "inline-block", margin: "0 14px", fontFamily: MONT, fontWeight: 900, fontSize: 70,
              color: estilo === "caja" ? (activa ? "#111" : "#fff") : activa || (estilo === "karaoke" && dicha) ? resaltado : "#fff",
              background: estilo === "caja" && activa ? resaltado : "transparent", borderRadius: 12, padding: "0 10px",
              ...contorno(estilo === "caja" && activa ? 0 : 7), textShadow: SOMBRA,
              transform: `scale(${estilo === "pop" && activa ? 1 + 0.16 * sp : 1})` }}>
              {s.mayusculas === false ? p.w : p.w.toUpperCase()}
            </span>
          );
        })}
      </div>
    </En>
  );
};

// ---------- el video ----------
export const Edu: React.FC<EduProps> = (props) => {
  const { fps, durationInFrames } = useVideoConfig();
  const f = useCurrentFrame();
  let inicio = 0;
  const palabras: Palabra[] = [];
  const escenas = (props.escenas || []).map((e) => {
    const dur = Math.max(1, Math.round(Math.max(0.5, e.duracion || 0) * fps));
    const desde = inicio;
    for (const p of e.palabras || []) palabras.push({ ...p, t: p.t + desde / fps });
    inicio += dur;
    return { e, desde, dur };
  });
  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      {escenas.map(({ e, desde, dur }, i) => (
        <Sequence key={i} from={desde} durationInFrames={dur}>
          <EscenaVideo e={e} dur={dur} props={props} />
        </Sequence>
      ))}
      {props.subtitulos?.activar !== false && palabras.length ? <Subtitulos palabras={palabras} props={props} /> : null}
      {props.musica?.archivo ? <Audio src={src(props.musica.archivo)} volume={props.musica.volumen ?? 0.08} loop /> : null}
      {props.barra !== false ? (
        <div style={{ position: "absolute", left: 0, bottom: 0, height: 12, width: `${(f / durationInFrames) * 100}%`,
          background: props.acento || "#FFD23F" }} />
      ) : null}
    </AbsoluteFill>
  );
};
