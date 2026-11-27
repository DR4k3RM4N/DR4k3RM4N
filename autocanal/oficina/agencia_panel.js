// 🕵️ Pestañas de la Agencia de Expedientes (como las otras oficinas): Bandeja, Casos, Equipo, Agenda, Canales y Chat.
// «Casos» es expedientes.js (importar, verificar, aprobar). Lo demás se pinta aquí.
(() => {
  const $ = (s) => document.querySelector(s);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const leer = (k, d) => { try { return localStorage.getItem(k) ?? d; } catch { return d; } };
  const guardar = (k, v) => { try { localStorage.setItem(k, v); } catch { /* sin almacenamiento */ } };
  const hora = (t) => new Date(t * 1000).toLocaleString("es-MX", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
  const fechaBonita = (iso) => new Date(`${iso}T12:00:00`).toLocaleDateString("es-MX", { weekday: "short", day: "numeric", month: "short" });
  async function api(ruta, datos) {
    const r = await fetch(ruta, { method: datos ? "POST" : "GET", headers: { "Content-Type": "application/json" },
                                  body: datos ? JSON.stringify(datos) : undefined });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.error || "Algo salió mal");
    return j;
  }

  // ---------- pestañas ----------
  const PANELES = { bandeja: "#tab-exp-bandeja", temas: "#tab-exp-temas", casos: "#tab-expedientes", equipo: "#tab-exp-equipo", agenda: "#tab-exp-agenda",
                    canales: "#tab-exp-canales", chat: "#tab-exp-chat" };
  let tab = PANELES[leer("exp_tab", "bandeja")] ? leer("exp_tab", "bandeja") : "bandeja";
  function abrir(nombre) {
    tab = nombre; guardar("exp_tab", nombre);
    document.querySelectorAll("[data-exp-tab]").forEach((b) => b.classList.toggle("activa", b.dataset.expTab === nombre));
    Object.entries(PANELES).forEach(([k, sel]) => { $(sel).hidden = k !== nombre; });
    if (nombre === "casos") window.dispatchEvent(new CustomEvent("pestana", { detail: "expedientes" }));
    pintar(true);
  }
  document.querySelectorAll("[data-exp-tab]").forEach((b) => b.addEventListener("click", () => abrir(b.dataset.expTab)));
  const abrirCaso = (id) => { abrir("casos"); window.dispatchEvent(new CustomEvent("exp-abrir", { detail: id })); };

  let resumen = null, agendaDatos = null, fabrica = null;
  const nombreDe = (id) => (id === "jefe" ? "Tú" : (resumen?.equipo || []).find((a) => a.id === id)?.nombre || id);

  // ---------- 📥 Bandeja: lo que te toca a ti ----------
  function pintarBandeja() {
    const casos = resumen?.expedientes || [];
    const pendientes = [];
    for (const c of casos) {
      const paso = (k) => (c.pasos || []).find((p) => p.clave === k)?.estado;
      if (paso("verificacion") === "espera_ok") pendientes.push({ c, ico: "🔎", txt: "Ramos terminó de verificar: revisa los ✅⚠️❌ y aprueba", btn: "Revisar" });
      else if (paso("voz") === "pendiente") pendientes.push({ c, ico: "🎙️", txt: "Verificación aprobada: ya se puede hacer la voz y el video", btn: "Ver caso" });
      else if (paso("verificacion") === "pendiente") pendientes.push({ c, ico: "▶️", txt: "Caso importado: pídele a Ramos que verifique los datos", btn: "Abrir" });
      else if (paso("verificacion") === "error") pendientes.push({ c, ico: "⚠️", txt: "Algo falló en la verificación", btn: "Ver" });
    }
    const revisar = (fabrica?.casos || []).filter((c) => c.paso === "revision");
    const total = pendientes.length + revisar.length;
    $("#exp-cuenta").hidden = !total;
    $("#exp-cuenta").textContent = total;
    const ag = (agendaDatos?.canales || [])[0];
    if (document.activeElement?.closest?.("#exp-bandeja") || [...document.querySelectorAll("#exp-bandeja video")].some((v) => !v.paused)) return;
    const marcha = fabrica?.en_marcha_todos || (fabrica?.en_marcha ? [fabrica.en_marcha] : []);
    $("#exp-bandeja").innerHTML = tarjetaEnMarcha(null, 0) + marcha.map((id) => tarjetaEnMarcha(id, 1)).join("") + tarjetaFabrica() + revisar.map(tarjetaVideo).join("") + `
      <section class="tarjeta">
        <h4>📥 Lo que te toca</h4>
        ${pendientes.length ? pendientes.map((x) => `<article class="exp-pendiente">
            <span class="exp-pendiente-ico">${x.ico}</span>
            <div><b>#${String(x.c.numero).padStart(3, "0")} · ${esc(x.c.marca)}</b><p class="pista">${esc(x.txt)}</p></div>
            <button class="btn btn-mini btn-primario" data-abrir-caso="${esc(x.c.id)}">${esc(x.btn)}</button></article>`).join("")
          : `<p class="vacio">Nada pendiente por ahora. 🕵️ El equipo te avisa aquí cuando necesite tu OK.</p>`}
      </section>
      ${ag ? `<section class="tarjeta">
        <h4>📅 Material por delante · ${esc(ag.nombre)}</h4>
        <p>${ag.llenos ? `Tienes <b>${ag.llenos}</b> video(s) programado(s), cubierto hasta el <b>${esc(fechaBonita(ag.cubierto_hasta))}</b> (${ag.dias_cubiertos} días).`
          : `Todavía no hay videos programados. Un video cada <b>${ag.ritmo_dias}</b> día(s) a las <b>${esc(ag.hora)}</b>.`}</p>
        <p class="pista">Siguiente fecha libre: ${esc(fechaBonita((ag.fechas.find((f) => !f.caso) || {}).fecha || agendaDatos.hoy))}</p>
        <button class="btn btn-mini" data-ir="agenda">Ver agenda</button></section>` : ""}
      <section class="tarjeta">
        <h4>🗂️ Casos</h4>
        ${casos.length ? `<ul class="exp-lista-mini">${casos.map((c) => `<li><button class="link" data-abrir-caso="${esc(c.id)}">#${String(c.numero).padStart(3, "0")} · ${esc(c.marca)}</button>
          <span class="pista">${esc(estadoCaso(c))}</span>
          ${!(fabrica?.casos || []).some((f) => f.id === c.id) ? `<button class="btn btn-mini btn-primario" data-fab-video="${esc(c.id)}" title="La fábrica busca material, arma el storyboard y tu compu lo hace con voz de Azure">🎬 Hacer video</button>` : ""}</li>`).join("")}</ul>` : `<p class="vacio">Sin casos todavía. Importa un paquete en la pestaña Casos.</p>`}
        <button class="btn btn-mini" data-ir="casos">📥 Importar paquete</button>
      </section>`;
  }
  // 🏭 la fábrica: prendida/pausada, qué está haciendo y cuánto material hay por delante
  const PASO_TXT = { investigacion: "🔎 Vera investiga", guion: "✍️ Vera escribe el guion", material: "🗄️ Inés busca material libre",
                     storyboard: "📊 Nico arma el storyboard", verificacion: "🔎 Ramos verifica", render: "🎬 Tu compu hace el video",
                     revision: "👀 Te toca revisar", programado: "📤 Programado" };
  function tarjetaFabrica() {
    if (!fabrica) return "";
    const e = fabrica.estado, enCurso = fabrica.temas.find((x) => x.id === e.en_curso);
    const trabajando = fabrica.casos.filter((c) => c.paso && !["revision", "programado"].includes(c.paso));
    const sig = fabrica.temas.find((x) => x.estado === "pendiente");
    return `<section class="tarjeta fab">
      <div class="cabeza"><h4>🏭 Fábrica de videos</h4>
        <label class="fab-switch"><input type="checkbox" data-fab-activa ${e.activa ? "checked" : ""}> ${e.activa ? "Prendida" : "Pausada"}</label></div>
      <p class="pista">Cuando tu plan de Claude tiene uso libre, el equipo toma el siguiente tema, lo investiga con fuentes, escribe el guion
        y el storyboard; tu compu hace el video y ${e.subir_solo ? "lo sube sola en PRIVADO con su fecha (tú lo haces público)" : "te lo deja aquí para revisar"}.
        Claude va por tu plan (cero centavos de la API); si se acaba el límite, espera y sigue sola.</p>
      ${!fabrica.plan ? `<p class="error">🧠 Tu plan de Claude no está conectado en el servidor (o está en pausa por el límite): la fábrica espera.</p>` : ""}
      ${e.nota ? `<p class="pista">⏳ ${esc(e.nota)}</p>` : ""}
      ${enCurso ? `<p>⚙️ Produciendo: <b>${esc(enCurso.marca)}</b></p>` : ""}
      ${trabajando.map((c) => `<p>• #${esc(c.numero)} ${esc(c.marca)} — ${esc(PASO_TXT[c.paso] || c.paso)}${c.paso === "render" && c.render_paso ? ` · ${esc(c.render_paso)} (${Math.round((c.render_avance || 0) * 100)} %)` : ""}${c.error ? ` <span class="error">· ${esc(c.error)}</span> <button class="btn btn-mini" data-fab-reintentar="${esc(c.id)}">🔁 Reintentar</button>` : ""}</p>`).join("")}
      <label class="fab-switch"><input type="checkbox" data-fab-subir ${e.subir_solo ? "checked" : ""}> 📤 Que lo suba sola en PRIVADO al terminar (con su fecha)</label>
      ${e.azure ? `<p class="pista">🎙️ Voz de Azure este mes: ${(e.azure.chars || 0).toLocaleString("es-MX")} de ~480,000 caracteres (≈ ${Math.max(0, Math.floor((480000 - (e.azure.chars || 0)) / 18000))} videos más)</p>` : ""}
      <p>📦 Material por delante: <b>${fabrica.por_delante}</b> de ${fabrica.meta} videos
        <label class="pista">· juntar para <select data-fab-meta>${[30, 60, 90, 180, 365].map((n) => `<option value="${n}" ${+e.meta_dias === n ? "selected" : ""}>${n} días</option>`).join("")}</select></label></p>
      <div class="fila"><button class="btn btn-mini btn-primario" data-fab-continuar title="Quita esperas, destraba lo atorado y reintenta lo que falló">▶ Continuar ahora</button>
        <button class="btn btn-mini" data-fab-reinicio title="Destraba todo a la fuerza: los videos trabados se cambian de compu o van al servidor">🔄 Reinicio forzoso</button>
        <a class="btn btn-mini" href="/edicion" target="_blank" rel="noopener">🎬 Sala de edición ↗</a>
        ${sig && !e.en_curso ? `<button class="btn btn-mini" data-producir="${esc(sig.id)}">⚙️ Producir ya: ${esc(sig.marca)}</button>` : ""}
        <button class="btn btn-mini" data-ir="temas">🧾 Temas (${fabrica.temas.filter((x) => x.estado === "pendiente").length} en fila)</button></div>
      <details class="fab-compus" ${fabrica.compus.some((c) => c.viva) ? "" : "open"}><summary>🖥️ Quién hace los videos (${fabrica.compus.filter((c) => c.viva && c.puede && c.pref !== "no").length} compu(s) lista(s))</summary>
        ${fabrica.compus.map((c) => `<div class="fab-compu"><span>${c.viva ? "🟢" : "⚪"} <b>${esc(c.nombre)}</b>
            <small class="pista">${c.viva ? (c.puede ? (c.ocupada ? "ocupada" : "lista") : esc(c.motivo)) : "apagada"}</small></span>
          <select data-fab-compu="${esc(c.id)}">${[["preferida", "⭐ Preferida"], ["respaldo", "Respaldo"], ["no", "🚫 No usar"]].map(([v, t]) => `<option value="${v}" ${c.pref === v ? "selected" : ""}>${t}</option>`).join("")}</select></div>`).join("") || `<p class="pista">No hay compus en la sala.</p>`}
        <label class="fab-switch"><input type="checkbox" data-fab-servidor ${e.servidor_respaldo ? "checked" : ""}> Si no hay ninguna, que lo haga el servidor (más lento)</label>
        <p class="pista">🖼️ Imágenes realistas para miniaturas: ${fabrica.imagenes === "cloudflare" ? "Cloudflare (gratis) ✔" : fabrica.imagenes === "gemini" ? "Gemini (~4-7 ¢ por imagen) ✔" : "sin conectar (usa la mejor foto real; guía: despliegue/GUIA_IMAGENES_IA.md)"}</p>
        ${!fabrica.azure_ok ? `<p class="error">🎙️ Falta la clave de Azure en el servidor (AZURE_SPEECH_KEY en el .env): sin ella no hay voz.</p>` : ""}
      </details>
      ${!fabrica.pexels ? `<p class="pista">🎞️ Sin clave de Pexels en el servidor: solo fotos de Wikimedia (opcional).</p>` : ""}
    </section>`;
  }
  // 🎬 el video que va ahorita: paso por paso, con su avance y cuándo se movió por última vez
  const ICONO_PASO = { listo: "✅", trabajando: "⏳", espera_ok: "👀", error: "⚠️", pendiente: "○" };
  function haceCuanto(t) {
    if (!t) return "";
    const s = Math.max(0, Math.round((fabrica.ahora || Date.now() / 1000) - t));
    return s < 60 ? `hace ${s} s` : s < 3600 ? `hace ${Math.round(s / 60)} min` : `hace ${Math.round(s / 3600)} h`;
  }
  function tarjetaEnMarcha(id, k) {
    const c = (fabrica?.casos || []).find((x) => x.id === id);
    const tema = !c && !k && fabrica?.estado?.en_curso ? fabrica.temas.find((x) => x.id === fabrica.estado.en_curso) : null;
    if (!c && !tema) return "";
    if (!c) {
      const quien = (resumen?.equipo || []).find((a) => a.id === "ex_guion");
      return `<section class="tarjeta fab-marcha"><h4>🎬 Ahorita: ¿Quién MATÓ a ${esc(tema.marca)}?</h4>
        <p>⏳ ${esc(quien?.dice || "Vera está investigando y escribiendo el guion…")}</p>
        <div class="fab-barra"><b style="width:8%"></b></div><p class="pista">Mientras las compus hacen un video, el equipo ya prepara el siguiente.</p></section>`;
    }
    const pasos = c.pasos || [];
    const hechos = pasos.filter((p) => p.estado === "listo").length;
    const enRender = c.paso === "render" && c.render_avance != null;
    const pct = Math.round(((hechos + (enRender ? c.render_avance : 0)) / Math.max(1, pasos.length)) * 100);
    const actual = pasos.find((p) => p.clave === c.paso);
    const quieto = c.t_mov && (fabrica.ahora - c.t_mov) > 900 && !c.error;
    return `<section class="tarjeta fab-marcha"><h4>🎬 Ahorita: #${esc(c.numero)} ¿Quién MATÓ a ${esc(c.marca)}?</h4>
      <ol class="fab-pasos">${pasos.map((p) => `<li class="fab-p-${esc(p.estado)} ${p.clave === c.paso ? "actual" : ""}">${ICONO_PASO[p.estado] || "○"} ${esc(p.etiqueta)}</li>`).join("")}</ol>
      <div class="fab-barra"><b style="width:${pct}%"></b></div>
      <p>${c.error ? `⚠️ <span class="error">${esc(c.error)}</span> <button class="btn btn-mini" data-fab-reintentar="${esc(c.id)}">🔁 Reintentar</button>`
        : `⏳ <b>${esc(actual?.etiqueta || c.paso || "")}</b>${c.render_paso ? ` — ${esc(c.render_paso)}` : ""}${enRender ? ` (${Math.round(c.render_avance * 100)} %)` : ""}`}</p>
      <p class="pista">Último movimiento: ${esc(haceCuanto(c.t_mov))} · ${pct} % del video${quieto ? " · ⚠️ lleva rato sin moverse: dale ▶ Continuar ahora" : ""}</p>
    </section>`;
  }
  function tarjetaVideo(c) {
    const libre = (agendaDatos?.canales?.[0]?.fechas || []).find((f) => !f.caso);
    const ruta = (n) => `/expedientes-render/${encodeURIComponent(c.id)}/${encodeURIComponent(n)}`;
    return `<section class="tarjeta fab-video">
      <h4>🎬 #${esc(c.numero)} · ¿Quién MATÓ a ${esc(c.marca)}? <span class="chip">listo para revisar</span></h4>
      ${c.video ? `<video controls preload="metadata" src="${ruta(c.video)}" poster="${ruta("miniatura-A.jpg")}"></video>
        <p class="pista"><a href="${ruta("miniatura-A.jpg")}" target="_blank">Miniatura A</a> · <a href="${ruta("miniatura-B.jpg")}" target="_blank">Miniatura B</a></p>`
        : `<p class="pista">${esc(c.render_nota || "Sin video")}</p>`}
      <p class="pista">${c.palabras || "?"} palabras · ${c.material || 0} archivos libres · Ramos: ✅ ${c.cuenta?.confirmado || 0} · ⚠️ ${c.cuenta?.corregir || 0} · ❌ ${c.cuenta?.no_confirmado || 0}
        · <button class="link" data-abrir-caso="${esc(c.id)}">ver verificación</button></p>
      ${c.error ? `<p class="error">${esc(c.error)}</p>` : ""}
      <div class="fila">
        <button class="btn btn-primario" data-fab-revisar="programar" data-eid="${esc(c.id)}">✅ Aprobar y programar${libre ? ` (${esc(fechaBonita(libre.fecha))} ${esc(libre.hora)})` : ""}</button>
        <button class="btn" data-fab-revisar="privado" data-eid="${esc(c.id)}">🔒 Subir privado sin fecha</button>
        <button class="btn btn-mini" data-fab-revisar="rehacer_video" data-eid="${esc(c.id)}">🔁 Rehacer video</button>
      </div>
      <p class="pista">Se sube en PRIVADO. Con fecha, YouTube lo publica solo ese día; sin fecha, tú lo haces público cuando quieras.</p>
    </section>`;
  }

  // ---------- 🧾 Temas ----------
  const ESTADO_TEMA = { produciendo: "⚙️ Produciendo", pendiente: "🕒 En fila", propuesto: "💡 Propuesto (apruébalo)", listo: "📦 Ya es caso",
                        hecho: "✅ Hecho", saltado: "⏭️ Saltado" };
  function pintarTemas() {
    if (!fabrica || document.activeElement?.closest?.("#exp-temas")) return;
    const orden = ["produciendo", "pendiente", "propuesto", "listo", "hecho", "saltado"];
    const lista = [...fabrica.temas].sort((a, b) => orden.indexOf(a.estado) - orden.indexOf(b.estado));
    let n = 0;
    $("#exp-temas").innerHTML = `<section class="tarjeta">
        <h4>🧾 Temas de ¿Quién MATÓ a…?</h4>
        <p class="pista">La fábrica toma el primero «En fila». Súbelo, sáltalo o agrega los tuyos. Cuando se acaben, el equipo propone más (tú los apruebas).</p>
        <form class="fila" id="fab-nuevo"><input name="marca" maxlength="80" placeholder="Marca (ej. Kmart México)"><input name="gancho" maxlength="300" placeholder="El gancho (opcional)">
          <button class="btn btn-mini btn-primario" type="submit">Agregar</button></form>
        <p><button class="btn btn-mini" data-fab-proponer>💡 Que el equipo proponga 6 temas</button></p>
      </section>
      <ol class="fab-temas">${lista.map((x) => `<li class="fab-tema fab-${esc(x.estado)}">
        <div><b>${x.estado === "pendiente" ? `${++n}. ` : ""}${esc(x.marca)}</b> <span class="chip">${esc(ESTADO_TEMA[x.estado] || x.estado)}</span>
          <p class="pista">${esc(x.gancho)}${x.grupo ? ` · ${esc(x.grupo)}` : ""}</p>
          ${x.error ? `<p class="error">Último intento: ${esc(x.error)}</p>` : ""}</div>
        <div class="fab-botones">
          ${x.estado === "pendiente" && !fabrica.estado.en_curso ? `<button class="btn btn-mini btn-primario" data-producir="${esc(x.id)}">▶ Ya</button>` : ""}
          ${x.estado === "pendiente" ? `<button class="btn btn-mini" data-tema="primero" data-id="${esc(x.id)}" title="Que sea el siguiente">⬆</button>
            <button class="btn btn-mini" data-tema="saltar" data-id="${esc(x.id)}">Saltar</button>` : ""}
          ${x.estado === "propuesto" ? `<button class="btn btn-mini btn-primario" data-tema="aprobar" data-id="${esc(x.id)}">👍 Aprobar</button>` : ""}
          ${x.estado === "saltado" ? `<button class="btn btn-mini" data-tema="reactivar" data-id="${esc(x.id)}">Regresar a la fila</button>` : ""}
          ${["propuesto", "saltado"].includes(x.estado) ? `<button class="btn btn-mini btn-no" data-tema="borrar" data-id="${esc(x.id)}">✕</button>` : ""}
          ${x.eid ? `<button class="btn btn-mini" data-abrir-caso="${esc(x.eid)}">Ver caso</button>` : ""}
        </div></li>`).join("")}</ol>`;
  }

  function estadoCaso(c) {
    const p = Object.fromEntries((c.pasos || []).map((x) => [x.clave, x.estado]));
    if (p.subida === "listo") return "✅ Subido (privado)";
    if (p.verificacion === "trabajando") return "⏳ Ramos verificando";
    if (p.verificacion === "espera_ok") return "👀 Te toca revisar";
    if (p.verificacion === "listo") return "✔ Verificado";
    return "○ Por verificar";
  }

  // ---------- 👥 Equipo ----------
  function pintarEquipo() {
    const tareas = resumen?.tareas || [];
    $("#exp-equipo").innerHTML = (resumen?.equipo || []).map((a) => {
      const mias = tareas.filter((t) => t.agente === a.id);
      const ahora = mias.find((t) => t.estado === "trabajando");
      const chip = a.estado === "trabajando" ? ["Trabajando", "trab"] : a.obra ? ["En obra", "fila"] : ["Libre", "libre"];
      return `<article class="tarjeta exp-agente" style="--c:${esc(a.color)}">
        <div class="exp-agente-cab"><span class="exp-avatar" style="background:${esc(a.color)}">${esc(a.nombre[0])}</span>
          <div><b>${esc(a.nombre)}</b> <small class="pista">${esc(a.rol)}</small><br><span class="estado-chip ${chip[1]}">${chip[0]}</span></div></div>
        <p class="pista">${esc(a.desc)}</p>
        ${ahora ? `<p>⏳ ${esc(ahora.accion)} · ${esc(ahora.titulo)}${ahora.paso ? ` — ${esc(ahora.paso)}` : ""}</p>` : a.dice ? `<p>💬 «${esc(a.dice)}»</p>` : ""}
        ${a.obra ? `<p class="pista">🚧 ${esc(a.obra)}</p>` : ""}
        ${mias.filter((t) => t.estado !== "trabajando").slice(-3).reverse().map((t) => `<p class="pista">${t.estado === "fallo" ? "✖" : "✔"} ${esc(t.accion)} · ${esc(t.titulo)} · ${esc(hora(t.fin || t.inicio))}</p>`).join("")}
      </article>`;
    }).join("");
  }

  // ---------- 📅 Agenda ----------
  function pintarAgenda() {
    if (!agendaDatos) { $("#exp-agenda").innerHTML = `<p class="pista">Cargando…</p>`; return; }
    $("#exp-agenda").innerHTML = agendaDatos.canales.map((c) => `<section class="tarjeta">
      <h4>📺 ${esc(c.nombre)}</h4>
      <p class="pista">Un video cada <b>${c.ritmo_dias}</b> día(s) a las <b>${esc(c.hora)}</b> · todo se sube en <b>privado y programado</b>: tú lo haces público.</p>
      <p>${c.llenos ? `✅ ${c.llenos} programado(s) · cubierto hasta el ${esc(fechaBonita(c.cubierto_hasta))} (${c.dias_cubiertos} días)` : "Todavía nada programado."}</p>
      <ol class="exp-agenda">${c.fechas.slice(0, 15).map((f) => `<li class="${f.caso ? "lleno" : ""}">
        <span class="exp-fecha">${esc(fechaBonita(f.fecha))} · ${esc(f.hora)}</span>
        ${f.caso ? `<button class="link" data-abrir-caso="${esc(f.caso.id)}">#${String(f.caso.numero).padStart(3, "0")} · ${esc(f.caso.marca)}</button>` : `<span class="pista">— libre —</span>`}</li>`).join("")}</ol>
    </section>`).join("") || `<p class="vacio">No hay canales activos. Agrégalos en la pestaña Canales.</p>`;
  }

  // ---------- 📺 Canales ----------
  function pintarCanales() {
    if (!agendaDatos) return;
    if (document.activeElement?.closest?.("#exp-canales")) return;
    const yt = agendaDatos.youtube || [];
    const opciones = (sel) => `<option value="">— elige el canal de YouTube —</option>` + yt.map((y) =>
      `<option value="${esc(y.id)}" ${sel === y.id ? "selected" : ""}>${esc(y.nombre)}${y.conectado ? "" : " (sin conectar)"}</option>`).join("");
    $("#exp-canales").innerHTML = agendaDatos.canales.map((c) => `<form class="tarjeta exp-canal" data-canal="${esc(c.id)}">
        <h4>📺 ${esc(c.nombre)}</h4>
        <label>Nombre <input name="nombre" value="${esc(c.nombre)}" maxlength="80"></label>
        <label>Título fijo de la serie <input name="plantilla" value="${esc(c.plantilla)}" maxlength="120" placeholder="¿Quién MATÓ a [Marca]?"></label>
        <label>De qué trata <textarea name="tema" rows="2" maxlength="600">${esc(c.tema)}</textarea></label>
        <div class="fila">
          <label>Un video cada <select name="ritmo_dias">${[1, 2, 3, 4, 5, 7].map((n) => `<option value="${n}" ${+c.ritmo_dias === n ? "selected" : ""}>${n === 1 ? "día" : `${n} días`}</option>`).join("")}</select></label>
          <label>a las <input name="hora" value="${esc(c.hora)}" maxlength="5" size="5"></label>
        </div>
        <label>Sube a <select name="canal_youtube">${opciones(c.canal_youtube)}</select></label>
        <div class="fila"><button class="btn btn-primario" type="submit">Guardar</button>
          ${agendaDatos.canales.length > 1 ? `<button class="btn btn-mini btn-no" type="button" data-borrar-canal="${esc(c.id)}">Quitar</button>` : ""}</div>
      </form>`).join("") + `<form class="tarjeta exp-canal" data-canal="">
        <h4>➕ Otro canal con la misma estructura</h4>
        <p class="pista">Mismo formato de caso (gancho, sospechosos, giro, veredicto), otro tema.</p>
        <label>Nombre <input name="nombre" maxlength="80" placeholder="Ej. ¿Qué pasó con…?"></label>
        <label>De qué trata <textarea name="tema" rows="2" maxlength="600"></textarea></label>
        <button class="btn" type="submit">Agregar canal</button></form>
      <p class="pista">Los canales de YouTube se conectan en la oficina principal (pestaña Estilo → canales).</p>`;
  }
  $("#exp-canales").addEventListener("submit", async (e) => {
    e.preventDefault();
    const f = e.target, datos = Object.fromEntries(new FormData(f));
    datos.id = f.dataset.canal;
    try { await api("/api/expedientes/canal", datos); document.activeElement?.blur(); await cargarAgenda(); pintar(true); alert("Guardado ✔"); }
    catch (err) { alert(err.message); }
  });

  document.querySelector(".ag-panel").addEventListener("change", async (e) => {
    const t = e.target;
    if (t.matches("[data-fab-activa]")) {
      try { await api("/api/expedientes/fabrica", { accion: "ajustar", activa: t.checked }); } catch (err) { alert(err.message); }
      t.blur(); cargar(true);
    }
    if (t.matches("[data-fab-subir]")) {
      try { await api("/api/expedientes/fabrica", { accion: "ajustar", subir_solo: t.checked }); } catch (err) { alert(err.message); }
      t.blur(); cargar(true);
    }
    if (t.matches("[data-fab-compu]")) {
      try { await api("/api/expedientes/fabrica", { accion: "compu", compu: t.dataset.fabCompu, pref: t.value }); } catch (err) { alert(err.message); }
      t.blur(); cargar(true);
    }
    if (t.matches("[data-fab-servidor]")) {
      try { await api("/api/expedientes/fabrica", { accion: "ajustar", servidor_respaldo: t.checked }); } catch (err) { alert(err.message); }
      t.blur(); cargar(true);
    }
    if (t.matches("[data-fab-meta]")) {
      try { await api("/api/expedientes/fabrica", { accion: "ajustar", meta_dias: +t.value }); } catch (err) { alert(err.message); }
      t.blur(); cargar(true);
    }
  });
  document.querySelector(".ag-panel").addEventListener("submit", async (e) => {
    if (e.target.id !== "fab-nuevo") return;
    e.preventDefault();
    const d = Object.fromEntries(new FormData(e.target));
    try { await api("/api/expedientes/fabrica", { accion: "tema", op: "nuevo", ...d }); e.target.reset(); document.activeElement?.blur(); cargar(true); }
    catch (err) { alert(err.message); }
  });

  // ---------- 💬 Chat: con toda la agencia (instrucciones reales) o sobre un caso ----------
  const AGENCIA = "__agencia__";
  let chatCaso = leer("exp_chat_caso", AGENCIA), chatDatos = null;
  async function pintarChat(forzar) {
    const casos = resumen?.expedientes || [];
    if (chatCaso !== AGENCIA && !casos.some((c) => c.id === chatCaso)) chatCaso = AGENCIA;
    if (!forzar && document.activeElement?.closest?.("#exp-chat")) return;
    let msgs, corriendo;
    if (chatCaso === AGENCIA) {
      msgs = fabrica?.chat || [];
      corriendo = msgs.at(-1)?.quien === "jefe";
    } else {
      try { chatDatos = await api(`/api/expedientes/${encodeURIComponent(chatCaso)}`); } catch { return; }
      msgs = chatDatos.chat || [];
      corriendo = chatDatos.corriendo || msgs.at(-1)?.quien === "jefe";
    }
    const borrador = $("#ag-chat-texto")?.value || "";
    const ejemplo = chatCaso === AGENCIA
      ? "Pídele lo que sea: «continúa», «haz el de Kodak ya», «pausa la fábrica», «¿qué está haciendo cada quien?», «sube el de Blockbuster sin fecha», «reintenta el 004», «junta material para un año», «propón 6 temas de marcas mexicanas»."
      : "Sobre este caso: «Ramos, ¿de dónde sale lo de las 9,094 tiendas?», «cambia la frase de la escena 3», «verifica otra vez la escena 12».";
    $("#exp-chat").innerHTML = `
      <label class="pista">Hablar con: <select id="ag-chat-caso">
        <option value="${AGENCIA}" ${chatCaso === AGENCIA ? "selected" : ""}>🕵️ Toda la agencia (instrucciones)</option>
        ${casos.map((c) => `<option value="${esc(c.id)}" ${c.id === chatCaso ? "selected" : ""}>🗂️ Caso #${String(c.numero).padStart(3, "0")} · ${esc(c.marca)}</option>`).join("")}</select></label>
      <ol class="chat ag-chat-log">${msgs.map((m) => `<li class="${m.quien === "jefe" ? "mio" : ""}"><span class="hora">${esc(hora(m.t))}</span>
        <b>${esc(nombreDe(m.quien))}</b> ${esc(m.texto)}${(m.hechos || []).length ? `<ul class="ag-hechos">${m.hechos.map((h) => `<li>${esc(h)}</li>`).join("")}</ul>` : ""}</li>`).join("")
        || `<li class="pista">${esc(ejemplo)}</li>`}</ol>
      ${corriendo ? `<p class="pista">✍️ El equipo está contestando…</p>` : ""}
      <form id="ag-chat-form" class="chat-escribir">
        <textarea id="ag-chat-texto" rows="2" maxlength="1500" placeholder="${chatCaso === AGENCIA ? "Escríbele a la agencia: «continúa», «haz el de Kodak», «pausa»…" : "Escríbele al equipo sobre este caso"}"></textarea>
        <button class="btn btn-primario" type="submit">Enviar</button>
      </form>`;
    $("#ag-chat-texto").value = borrador;
    const log = $(".ag-chat-log"); log.scrollTop = log.scrollHeight;
  }
  $("#exp-chat").addEventListener("change", (e) => { if (e.target.id === "ag-chat-caso") { chatCaso = e.target.value; guardar("exp_chat_caso", chatCaso); pintarChat(true); } });
  $("#exp-chat").addEventListener("keydown", (e) => {
    if (e.target.id === "ag-chat-texto" && e.key === "Enter" && !e.shiftKey && !matchMedia("(pointer: coarse)").matches) { e.preventDefault(); $("#ag-chat-form").requestSubmit(); }
  });
  $("#exp-chat").addEventListener("submit", async (e) => {
    e.preventDefault();
    const texto = $("#ag-chat-texto").value.trim();
    if (!texto) return;
    try {
      if (chatCaso === AGENCIA) await api("/api/expedientes/fabrica", { accion: "chat", texto });
      else await api(`/api/expedientes/${encodeURIComponent(chatCaso)}`, { accion: "chat", texto });
      $("#ag-chat-texto").value = ""; document.activeElement?.blur(); await cargar(true);
    } catch (err) { alert(err.message); }
  });

  // ---------- clics comunes ----------
  document.querySelector(".ag-panel").addEventListener("click", async (e) => {
    const a = e.target.closest("[data-abrir-caso]"); if (a) return abrirCaso(a.dataset.abrirCaso);
    const ir = e.target.closest("[data-ir]"); if (ir) return abrir(ir.dataset.ir);
    const fab = async (datos, boton, ok) => {
      if (boton) boton.disabled = true;
      try { const r = await api("/api/expedientes/fabrica", datos); if (ok) alert(ok(r)); } catch (err) { alert(err.message); }
      if (boton) boton.disabled = false;
      await cargar(true);
    };
    const rf = e.target.closest("[data-fab-reinicio]");
    if (rf) return fab({ accion: "reinicio" }, rf, (r) => "🔄 Reinicio forzoso: " + (r.hechos || []).join(" · "));
    const co = e.target.closest("[data-fab-continuar]");
    if (co) return fab({ accion: "continuar" }, co, (r) => `▶ Seguimos. ${r.reintentos ? `Reintenté ${r.reintentos} caso(s) atorado(s).` : "No había nada atorado."}`);
    const hv = e.target.closest("[data-fab-video]");
    if (hv) return fab({ accion: "hacer_video", eid: hv.dataset.fabVideo }, hv, () => "🎬 Va: Inés busca material, Nico arma el storyboard y luego tu compu hace el video.");
    const re = e.target.closest("[data-fab-reintentar]");
    if (re) return fab({ accion: "reintentar", eid: re.dataset.fabReintentar }, re, () => "🔁 Lo estoy reintentando.");
    const pr = e.target.closest("[data-producir]");
    if (pr) return fab({ accion: "producir", id: pr.dataset.producir }, pr, () => "Arrancó la producción ⚙️ Mira el avance en la Bandeja.");
    const tm = e.target.closest("[data-tema]");
    if (tm) {
      if (tm.dataset.tema === "borrar" && !confirm("¿Quitar este tema de la lista?")) return;
      return fab({ accion: "tema", id: tm.dataset.id, op: tm.dataset.tema }, tm);
    }
    const pp = e.target.closest("[data-fab-proponer]");
    if (pp) { pp.textContent = "Pensando…"; return fab({ accion: "proponer" }, pp, (r) => `Listo: ${r.nuevos} tema(s) nuevo(s) para que los apruebes.`); }
    const rv = e.target.closest("[data-fab-revisar]");
    if (rv) {
      const a = rv.dataset.fabRevisar;
      const msg = { programar: "¿Aprobar este video? Se sube en PRIVADO y YouTube lo publica solo en la fecha que toca.",
                    privado: "¿Aprobar y subirlo en PRIVADO sin fecha? Tú lo haces público cuando quieras.",
                    rehacer_video: "¿Mandar a tu compu a hacer el video otra vez?" }[a];
      if (!confirm(msg)) return;
      return fab({ accion: a, eid: rv.dataset.eid }, rv, (r) => a === "programar" ? `Subiendo en privado, programado para el ${r.fecha} ✔` : "Va ✔");
    }
    const b = e.target.closest("[data-borrar-canal]");
    if (b && confirm("¿Quitar este canal de la agencia? (No borra nada en YouTube)")) {
      try { await api("/api/expedientes/canal", { id: b.dataset.borrarCanal, borrar: true }); await cargarAgenda(); pintar(true); } catch (err) { alert(err.message); }
    }
  });

  // ---------- datos ----------
  async function cargarAgenda() { try { agendaDatos = await api("/api/expedientes/agenda"); } catch { /* sigue */ } }
  async function cargar(forzar) {
    if (document.hidden) return;
    try { [resumen, fabrica] = await Promise.all([api("/api/expedientes"), api("/api/expedientes/fabrica")]); } catch { return; }
    if (tab === "agenda" || tab === "bandeja" || tab === "canales" || !agendaDatos) await cargarAgenda();
    pintar(forzar);
  }
  function pintar(forzar) {
    if (!resumen) return;
    if (tab === "bandeja") pintarBandeja(); else {
      const n = (resumen.expedientes || []).filter((c) => (c.pasos || []).some((p) => p.estado === "espera_ok")).length;
      $("#exp-cuenta").hidden = !n; $("#exp-cuenta").textContent = n;
    }
    if (tab === "equipo") pintarEquipo();
    if (tab === "temas") pintarTemas();
    if (tab === "agenda") pintarAgenda();
    if (tab === "canales") pintarCanales();
    if (tab === "chat") pintarChat(forzar);
  }
  setInterval(cargar, 4000);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) cargar(); });
  abrir(tab);
  cargar();
})();
