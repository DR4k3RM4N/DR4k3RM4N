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
  const PANELES = { bandeja: "#tab-exp-bandeja", casos: "#tab-expedientes", equipo: "#tab-exp-equipo", agenda: "#tab-exp-agenda",
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

  let resumen = null, agendaDatos = null;
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
    $("#exp-cuenta").hidden = !pendientes.length;
    $("#exp-cuenta").textContent = pendientes.length;
    const ag = (agendaDatos?.canales || [])[0];
    $("#exp-bandeja").innerHTML = `
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
          <span class="pista">${esc(estadoCaso(c))}</span></li>`).join("")}</ul>` : `<p class="vacio">Sin casos todavía. Importa un paquete en la pestaña Casos.</p>`}
        <button class="btn btn-mini" data-ir="casos">📥 Importar paquete</button>
      </section>`;
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

  // ---------- 💬 Chat (con el equipo, sobre un caso) ----------
  let chatCaso = leer("exp_chat_caso", ""), chatDatos = null;
  async function pintarChat(forzar) {
    const casos = resumen?.expedientes || [];
    if (!casos.length) { $("#exp-chat").innerHTML = `<p class="vacio">Importa un caso para platicar con el equipo sobre él.</p>`; return; }
    if (!casos.some((c) => c.id === chatCaso)) chatCaso = casos[0].id;
    if (!forzar && document.activeElement?.closest?.("#exp-chat")) return;
    try { chatDatos = await api(`/api/expedientes/${encodeURIComponent(chatCaso)}`); } catch { return; }
    const msgs = chatDatos.chat || [];
    const borrador = $("#ag-chat-texto")?.value || "";
    $("#exp-chat").innerHTML = `
      <label class="pista">Caso: <select id="ag-chat-caso">${casos.map((c) => `<option value="${esc(c.id)}" ${c.id === chatCaso ? "selected" : ""}>#${String(c.numero).padStart(3, "0")} · ${esc(c.marca)}</option>`).join("")}</select></label>
      <ol class="chat ag-chat-log">${msgs.map((m) => `<li class="${m.quien === "jefe" ? "mio" : ""}"><span class="hora">${esc(hora(m.t))}</span>
        <b>${esc(nombreDe(m.quien))}</b> ${esc(m.texto)}</li>`).join("") || `<li class="pista">Escríbele al equipo: «Ramos, ¿de dónde sale lo de los 500 autos?», «cambia la frase de la isla», «verifica otra vez la escena 12».</li>`}</ol>
      ${chatDatos.corriendo || msgs.at(-1)?.quien === "jefe" ? `<p class="pista">✍️ El equipo está contestando…</p>` : ""}
      <form id="ag-chat-form" class="chat-escribir">
        <textarea id="ag-chat-texto" rows="2" maxlength="1500" placeholder="Escríbele al equipo sobre este caso"></textarea>
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
    try { await api(`/api/expedientes/${encodeURIComponent(chatCaso)}`, { accion: "chat", texto }); $("#ag-chat-texto").value = ""; document.activeElement?.blur(); pintarChat(true); }
    catch (err) { alert(err.message); }
  });

  // ---------- clics comunes ----------
  document.querySelector(".ag-panel").addEventListener("click", async (e) => {
    const a = e.target.closest("[data-abrir-caso]"); if (a) return abrirCaso(a.dataset.abrirCaso);
    const ir = e.target.closest("[data-ir]"); if (ir) return abrir(ir.dataset.ir);
    const b = e.target.closest("[data-borrar-canal]");
    if (b && confirm("¿Quitar este canal de la agencia? (No borra nada en YouTube)")) {
      try { await api("/api/expedientes/canal", { id: b.dataset.borrarCanal, borrar: true }); await cargarAgenda(); pintar(true); } catch (err) { alert(err.message); }
    }
  });

  // ---------- datos ----------
  async function cargarAgenda() { try { agendaDatos = await api("/api/expedientes/agenda"); } catch { /* sigue */ } }
  async function cargar() {
    if (document.hidden) return;
    try { resumen = await api("/api/expedientes"); } catch { return; }
    if (tab === "agenda" || tab === "bandeja" || tab === "canales" || !agendaDatos) await cargarAgenda();
    pintar();
  }
  function pintar(forzar) {
    if (!resumen) return;
    if (tab === "bandeja") pintarBandeja(); else {
      const n = (resumen.expedientes || []).filter((c) => (c.pasos || []).some((p) => p.estado === "espera_ok")).length;
      $("#exp-cuenta").hidden = !n; $("#exp-cuenta").textContent = n;
    }
    if (tab === "equipo") pintarEquipo();
    if (tab === "agenda") pintarAgenda();
    if (tab === "canales") pintarCanales();
    if (tab === "chat") pintarChat(forzar);
  }
  setInterval(cargar, 4000);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) cargar(); });
  abrir(tab);
  cargar();
})();
