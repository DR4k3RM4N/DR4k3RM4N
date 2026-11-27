// 🛒 La página de TikTok Shop dibuja SU estudio desde cero (cuarto.js), en lugar del edificio.
// El cuarto de edición (/sala-oficina) solo se usa dentro de la Sala central para dar de alta compus: sin dibujo.
(() => {
  const pagina = document.body.dataset.oficina;
  if (!pagina || pagina === "youtube") return;
  const estilo = document.createElement("style");
  estilo.textContent = `#lienzo, #capas, .ayuda, .alas { display: none !important; }
    .escenario { padding: 0 !important; width: 100% !important; display: block !important; }
    .cuarto-caja { width: 100%; border-radius: 14px; overflow: hidden; border: 2px solid #d5d9e2; background: #fff; }
    .cuarto-caja canvas { display: block; max-width: 100%; }
    body[data-oficina="sala"] .sala { display: none !important; }
    body[data-oficina="sala"] .layout { grid-template-columns: minmax(0, 1fr) !important; }`;
  document.head.appendChild(estilo);
  if (pagina !== "tiktok" || !window.Cuarto) return;
  const escenario = document.querySelector(".escenario");
  if (!escenario) return;
  const caja = document.createElement("div");
  caja.className = "cuarto-caja";
  escenario.prepend(caja);
  // lugares: 6 escritorios del equipo a la izquierda y al centro; el set de grabación a la derecha
  const LUGAR = { tt_cazador: [150, 110], tt_guionista: [380, 110], tt_director: [610, 110],
                  tt_editor: [150, 320], tt_disenadora: [380, 320], tt_analista: [610, 320] };
  const COLOR_ETAPA = { ficha: "#4dabf7", guion: "#fe2c55", tomas: "#69db7c", video: "#ff922b", portada: "#da77f2" };
  window.Cuarto.montar(caja, {
    tema: "tiktok", cada: 2500, descripcion: "El estudio de TikTok Shop",
    cargar: async () => {
      const r = await fetch("/tiktok/api/estado");
      if (!r.ok) throw new Error("apagada");
      return r.json();
    },
    plano: (d) => {
      const tareas = (d.tareas || []).filter((t) => ["trabajando", "en_cola"].includes(t.estado));
      const estaciones = (d.agentes || []).filter((a) => LUGAR[a.id]).map((a) => {
        const t = tareas.find((x) => x.agente === a.id);
        const trabaja = a.estado === "trabajando" || !!t;
        return { id: a.id, x: LUGAR[a.id][0], y: LUGAR[a.id][1], nombre: a.nombre, sub: a.rol, viva: true, trabajando: trabaja,
          persona: a, dice: a.dice, dice_t: a.dice_t,
          pantalla: t ? { titulo: t.titulo || t.accion, linea: t.accion, fondo: "#111318", color: COLOR_ETAPA[t.etapa] }
            : { encendida: true, titulo: "TikTok Shop", linea: trabaja ? "trabajando…" : "libre", fondo: "#16181d" },
          luz: trabaja ? "rgba(254,44,85,.16)" : null };
      });
      const enSet = (d.productos || []).find((p) => p.estado === "listo" || p.estado === "video_listo");
      return { estaciones, alto: 520,
               adornos: [["repisa", 380, 30], ["aro", 870, 150], ["mesa", 795, 250, enSet ? `Para grabar: ${enSet.nombre}`.slice(0, 34) : "Set de grabación"],
                         ["sillon", 820, 430, "#fe2c55"], ["planta", 40, 470], ["planta", 960, 60], ["planta", 720, 470]] };
    },
  });
})();
