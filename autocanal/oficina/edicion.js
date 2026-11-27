// 🎬 Sala de edición central: todas las compus (y el servidor) editando lo de todas las oficinas
(() => {
  const $ = (s) => document.querySelector(s);
  const esc = (t) => String(t ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const ORIGEN = { youtube: "🏢 Edificio", expedientes: "🕵️ Expedientes", tiktok: "🛍️ TikTok Shop", tienda: "🛍️ TikTok Shop",
                   sala: "🎞️ Tus clips", "": "🎞️ Sala" };
  const TIPO = { edu: "Plantilla", edu_ia: "Claude dirige", edu_estilo: "Estilo del canal", expediente: "Motor Expedientes",
                 cris: "Video TikTok", libre: "Edición libre", probar_app: "📱 Robot del cel", pensar: "Pensando", claude_libre: "Editor IA" };
  let datos = null, ocupado = false;

  async function api(ruta, cuerpo) {
    const r = await fetch(ruta, cuerpo ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(cuerpo) } : {});
    const j = await r.json().catch(() => ({}));
    if (!r.ok || j.error) throw new Error(j.error || `Error ${r.status}`);
    return j;
  }
  const hace = (t) => {
    if (!t) return "";
    const s = Math.max(0, Math.round((datos?.ahora || Date.now() / 1000) - t));
    return s < 60 ? `${s} s` : s < 3600 ? `${Math.round(s / 60)} min` : `${Math.round(s / 3600)} h`;
  };
  const pct = (x) => Math.round((Number(x) || 0) * 100);
  function medidor(nombre, v) {
    if (v == null) return `<div class="ed-med">${nombre}<i><b style="width:0"></b></i><span>—</span></div>`;
    return `<div class="ed-med ${v >= 85 ? "alto" : ""}">${nombre}<i><b style="width:${v}%"></b></i><span>${v}%</span></div>`;
  }
  function trabajo(t) {
    const quieto = t.mov && (datos.ahora - t.mov) > 600;
    return `<div class="ed-trab ${quieto ? "quieto" : ""}">
      <div class="ed-trab-cab"><b>${esc(t.etiqueta || "Video")}</b><span class="ed-pct">${pct(t.avance)}%</span></div>
      <div class="ed-barra-av"><b style="width:${pct(t.avance)}%"></b></div>
      <small><span class="ed-chip">${esc(ORIGEN[t.origen] ?? t.origen)}</span>${esc(TIPO[t.tipo] || t.tipo || "")} · ${esc(t.paso || "empezando")}</small>
      <small class="mov">${t.mov ? `Se movió hace ${hace(t.mov)}${quieto ? " · ⚠️ parece trabado" : ""}` : `Empezó hace ${hace(t.inicio)}`}</small>
    </div>`;
  }
  function maquina(c) {
    const u = c.uso || {};
    const activos = c.activos || [];
    const cap = c.capacidad || 1;
    return `<article class="ed-maq ${c.viva ? "" : "apagada"}">
      <div class="ed-maq-cab"><h3>${c.interno ? "🖥️" : "💻"} ${esc(c.nombre)}</h3>
        <span class="ed-estado ${c.viva ? "viva" : ""}">${c.viva ? esc(c.estado_texto || "Lista") : "Apagada"}</span></div>
      <p class="ed-gpu">${esc(c.gpu || c.sistema || "")}${u.hilos ? ` · ${u.hilos} hilos` : ""}${c.nvenc ? " · NVENC" : ""}</p>
      <div class="ed-medidores">${medidor("Procesador", u.cpu)}${medidor("Memoria", u.ram)}${medidor("Tarjeta", u.gpu)}</div>
      <p class="ed-cap">Editando ${activos.length} de ${cap} a la vez · ${c.editados || 0} hechos${c.tipos?.length ? ` · sabe: ${esc(c.tipos.map((x) => TIPO[x] || x).join(", "))}` : ""}</p>
      ${activos.length ? activos.map(trabajo).join("") : `<p class="ed-vacio">${c.viva ? "Libre: esperando video." : "Préndela para que edite."}</p>`}
    </article>`;
  }
  function pintar() {
    const s = datos.sala || {};
    const compus = s.compus || [];
    const usarSrv = !!s.ajustes?.usar_servidor;
    $("#ed-todas").classList.toggle("prendido", usarSrv);
    $("#ed-todas b").textContent = usarSrv ? "⚡ Usando todas las compus + servidor" : "⚡ Usar todas las compus + servidor";
    $("#ed-todas-sub").textContent = usarSrv ? "Prendido: el servidor también edita (tus compus primero). Toca para apagarlo."
      : "Apagado: el servidor solo edita si no hay ninguna compu.";
    if (document.activeElement?.id !== "ed-srv-n") $("#ed-srv-n").value = String(s.ajustes?.servidor_a_la_vez || 1);
    if (document.activeElement?.id !== "ed-cerebro") $("#ed-cerebro").value = datos.cerebro || "auto";

    const vivas = compus.filter((c) => c.viva);
    const editando = compus.reduce((a, c) => a + (c.activos || []).length, 0);
    const lugares = vivas.reduce((a, c) => a + (c.capacidad || 1), 0);
    const hoy = (s.trabajos || []).filter((t) => t.estado === "listo" && t.fin && datos.ahora - t.fin < 86400).length;
    $("#ed-resumen").innerHTML = [
      [vivas.length, `máquinas prendidas de ${compus.length}`], [`${editando}/${lugares}`, "videos editándose / lugares"],
      [s.cola || 0, "videos en fila"], [hoy, "terminados en 24 h"]].map(([n, t]) => `<div class="ed-cifra"><b>${esc(n)}</b><span>${esc(t)}</span></div>`).join("");
    $("#ed-maquinas").innerHTML = s.error ? `<p class="ed-err">${esc(s.error)}</p>`
      : compus.length ? [...compus].sort((a, b) => (b.viva - a.viva) || (a.interno - b.interno)).map(maquina).join("")
      : `<p class="ed-vacio">No hay compus dadas de alta. Agrégalas desde la pestaña Sala del edificio.</p>`;

    const ex = datos.expedientes || {};
    const casos = (ex.casos || []).map((c) => `<li><span>#${esc(c.numero)} ${esc(c.marca)} — ${esc(c.error ? `⚠️ ${c.error}` : c.render_paso || c.paso)}</span>
        <em>${c.paso === "render" && c.render_avance != null ? `${pct(c.render_avance)}%` : esc(c.paso)} · ${esc(hace(c.t_mov))}</em></li>`).join("");
    const edif = (datos.edificio || []).map((p) => `<li><span>${esc(p.titulo)} <span class="ed-chip">${esc(p.canal)}</span>${p.error ? ` <span class="ed-err">⚠️ ${esc(p.error)}</span>` : ""}</span>
        <em>${esc(p.estado === "publicando" ? "subiendo" : p.etapa || p.estado)}</em></li>`).join("");
    $("#ed-oficinas").innerHTML = `
      <div class="ed-ofi"><h3>🏢 Edificio (YouTube: todos los canales)</h3>${edif ? `<ul class="ed-lista">${edif}</ul>` : `<p class="ed-vacio">Nada en producción ahorita.</p>`}</div>
      <div class="ed-ofi"><h3>🕵️ Expedientes · ¿Quién MATÓ a…? ${ex.activa === false ? '<span class="ed-chip">pausada</span>' : ""}</h3>
        ${casos ? `<ul class="ed-lista">${casos}</ul>` : `<p class="ed-vacio">${ex.tema ? "Preparando el siguiente caso (investigación y guion)…" : "Sin casos en marcha."}</p>`}</div>
      <div class="ed-ofi"><h3>🛍️ TikTok Shop y 🎞️ tus clips</h3><p class="ed-vacio">Cuando mandes videos de aquí, también salen en las máquinas.</p></div>`;

    const cola = (s.trabajos || []).filter((t) => t.estado === "en_cola");
    const ultimos = (s.trabajos || []).filter((t) => ["listo", "error", "cancelado"].includes(t.estado)).slice(0, 10);
    $("#ed-fila").innerHTML = `<div class="ed-ofi"><h3>⏳ En fila (${cola.length})</h3>${cola.length ? `<ul class="ed-lista">${cola.map((t) =>
        `<li><span><span class="ed-chip">${esc(ORIGEN[t.origen] ?? t.origen)}</span>${esc(t.etiqueta)}</span><em>espera ${esc(hace(t.creado))}</em></li>`).join("")}</ul>`
        : `<p class="ed-vacio">Nada esperando.</p>`}</div>
      <div class="ed-ofi"><h3>🗂️ Lo último</h3>${ultimos.length ? `<ul class="ed-lista">${ultimos.map((t) =>
        `<li><span>${t.estado === "listo" ? '<span class="ed-ok">✔</span>' : '<span class="ed-err">✖</span>'} ${esc(t.etiqueta)}${t.error ? ` <span class="ed-err">${esc(t.error)}</span>` : ""}</span>
          <em>${esc(t.compu_nombre || "")} · hace ${esc(hace(t.fin))}</em></li>`).join("")}</ul>` : `<p class="ed-vacio">Todavía nada.</p>`}</div>`;
  }
  async function cargar() {
    try {
      datos = await api("/api/edicion");
      pintar();
    } catch (err) {
      $("#ed-maquinas").innerHTML = `<p class="ed-err">${esc(err.message)}</p>`;
    }
  }
  function avisar(t) {
    $("#ed-aviso").hidden = !t;
    $("#ed-aviso").textContent = t || "";
  }
  async function accion(boton, ruta, cuerpo, ok) {
    if (ocupado) return;
    ocupado = true;
    boton.disabled = true;
    try {
      const r = await api(ruta, cuerpo);
      avisar(ok(r));
      await cargar();
    } catch (err) {
      avisar(`⚠️ ${err.message}`);
    } finally {
      ocupado = false;
      boton.disabled = false;
    }
  }
  $("#ed-todas").addEventListener("click", (e) => {
    const prender = !datos?.sala?.ajustes?.usar_servidor;
    accion(e.currentTarget, "/api/edicion/ajustes", { usar_todas: prender },
      () => prender ? "⚡ Listo: tus compus y el servidor editan. Tus compus toman primero cada video; si en 30 s ninguna puede, lo hace el servidor."
        : "Apagado: el servidor ya no toma videos (salvo que no haya ninguna compu).");
  });
  $("#ed-reinicio").addEventListener("click", (e) =>
    accion(e.currentTarget, "/api/edicion/reinicio", {}, (r) => "🔄 Reinicio forzoso hecho:\n• " + (r.hechos || []).join("\n• ")));
  $("#ed-srv-n").addEventListener("change", (e) =>
    accion(e.currentTarget, "/api/edicion/ajustes", { servidor_a_la_vez: Number(e.target.value) }, () => `El servidor edita hasta ${e.target.value} video(s) a la vez.`));
  $("#ed-cerebro").addEventListener("change", (e) =>
    accion(e.currentTarget, "/api/edicion/ajustes", { cerebro: e.target.value }, () => e.target.value === "claude"
      ? "🧠 Claude dirige la edición de los videos del edificio en tu compu (usa tu plan). Cuida Tu Lana sigue con su estilo fijo."
      : "🧠 Edición automática: no gasta tu plan."));
  cargar();
  setInterval(() => { if (!document.hidden) cargar(); }, 3000);
})();
