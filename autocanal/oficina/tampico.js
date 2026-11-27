// 🌮 Tampiqueando en su propia página (como TikTok Shop y Expedientes)
(() => {
  const $ = (s) => document.querySelector(s);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  async function api(ruta, datos) {
    const r = await fetch(ruta, { method: datos ? "POST" : "GET", headers: { "Content-Type": "application/json" },
                                  body: datos ? JSON.stringify(datos) : undefined });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.error || "Algo salió mal");
    return j;
  }
  // ---------- 🌮 Tampiqueando ----------
  let tamp = null;
  const ESTADO_NEGOCIO = { nuevo: "🆕 Nuevo", contactado: "📨 Contactado", respondio: "💬 Respondió", interesado: "🤝 Interesado",
    plan: "🎬 Con plan", grabado: "🎥 Grabado", publicado: "✅ Publicado", no_interesado: "🚫 No le interesa", sin_numero: "☎️ Sin WhatsApp" };
  async function pintarTampico(forzar) {
    const caja = $("#tampico");
    if (!caja) return;
    if (document.activeElement?.closest?.("#tampico") && !forzar) return;
    try { tamp = await api("/api/tampico"); } catch (err) { caja.innerHTML = `<p class="error">${esc(err.message)}</p>`; return; }
    const t = tamp, aj = t.ajustes, cx = t.conexiones;
    const ok = (b) => (b ? "✅" : "❌");
    const chipsEstado = Object.entries(t.cuenta).filter(([, n]) => n).map(([e, n]) => `<span class="chip">${ESTADO_NEGOCIO[e] || e}: ${n}</span>`).join(" ");
    const opcionesEstado = (actual) => Object.entries(ESTADO_NEGOCIO).map(([e, txt]) => `<option value="${e}" ${e === actual ? "selected" : ""}>${txt}</option>`).join("");
    caja.innerHTML = `
      <section class="tarjeta"><h4>🌮 Tampiqueando · foodie de Tampico, Madero y Altamira</h4>
        <p class="pista">Lupita busca negocios sin repetir, Chuy les escribe por WhatsApp y les contesta, Fer planea cada visita
          (guion, tomas y textos) y la manda a la sala de edición; aquí planeas el dron, el formato y publicas en Facebook,
          Instagram y TikTok.</p>
        <p>WhatsApp (plantilla) ${ok(cx.whatsapp_plantilla)} · Facebook ${ok(cx.facebook)} · Instagram ${ok(cx.instagram)} · TikTok: listo para subir tú</p>
        ${!cx.whatsapp_plantilla || !cx.facebook || !cx.instagram ? `<details><summary class="pista">¿Cómo conecto lo que falta?</summary><p class="pista">
          Se configura una vez en el servidor (no por el chat). Pídele a Claude la guía de «conectar Tampiqueando»: plantilla de WhatsApp aprobada
          (TAMPICO_WA_PLANTILLA), página de Facebook (TAMPICO_FB_PAGINA + TAMPICO_FB_TOKEN) e Instagram de empresa (TAMPICO_IG_ID).</p></details>` : ""}
      </section>
      <section class="tarjeta"><h4>💬 Lo que les ofreces a los negocios</h4>
        <textarea id="tp-propuesta" rows="3" placeholder="Ej.: Te hago un video para Facebook, Instagram y TikTok de tu negocio sin costo a cambio de la comida; lo publico en Tampiqueando y te lo comparto…">${esc(aj.propuesta)}</textarea>
        <div class="acciones"><button class="btn" data-tp="guardar_propuesta">💾 Guardar</button></div>
        <label class="chk"><input type="checkbox" data-tp-aj="envio_auto" ${aj.envio_auto ? "checked" : ""}> Chuy escribe solo a los negocios nuevos (lun-sáb, ${aj.hora_inicio}:00-${aj.hora_fin}:00)</label>
        <label class="chk"><input type="checkbox" data-tp-aj="responder_auto" ${aj.responder_auto ? "checked" : ""}> Chuy contesta solo cuando un negocio responde (siempre te avisa)</label>
        <label>Primeros mensajes al día <select data-tp-aj="mensajes_dia">${[0, 3, 5, 8, 10, 15, 20].map((n) => `<option ${n === aj.mensajes_dia ? "selected" : ""}>${n}</option>`).join("")}</select></label>
        <p class="pista">Hoy van ${t.enviados_hoy}. Si alguien dice «no gracias», ya no se le escribe.</p>
      </section>
      <section class="tarjeta"><h4>🔎 Negocios</h4>
        <form id="tp-buscar" class="fila"><input id="tp-tipo" placeholder="restaurantes, tacos, mariscos, café…" value="restaurantes">
          <select id="tp-zona"><option>Tampico</option><option>Ciudad Madero</option><option>Altamira</option></select>
          <button class="btn btn-primario">Buscar</button></form>
        <p>${chipsEstado || '<span class="pista">Todavía no hay negocios: búscalos arriba.</span>'}</p>
        <div class="tp-negocios">${t.negocios.map((n) => `<div class="tp-negocio">
          <b>${esc(n.nombre)}</b> <small>${esc(n.categoria || "")} · ${esc(n.zona)}${n.estrellas ? ` · ⭐${esc(n.estrellas)} (${esc(n.resenas || 0)})` : ""}</small>
          <small class="pista">${esc(n.direccion || "")}${n.fecha_propuesta ? ` · 📅 propone: ${esc(n.fecha_propuesta)}` : ""}</small>
          <div class="fila"><select data-tp-estado="${esc(n.id)}">${opcionesEstado(n.estado)}</select>
            <button class="btn btn-mini" data-tp="plan" data-id="${esc(n.id)}">🎬 Plan de visita</button>
            ${(t.chats[n.id] || []).length ? `<details><summary class="btn btn-mini">💬 Plática (${t.chats[n.id].length})</summary>${t.chats[n.id].map((m) => `<p class="pista"><b>${m.de === "negocio" ? "Ellos" : "Chuy"}:</b> ${esc(m.texto)}</p>`).join("")}</details>` : ""}</div>
        </div>`).join("")}</div>
      </section>
      <section class="tarjeta"><h4>🎬 Planes de visita</h4>
        ${t.planes.length ? t.planes.map((p) => `<details class="tp-plan"><summary><b>${esc(p.nombre)}</b> · ${esc(p.formato)}</summary>
          <p>🪝 <b>${esc(p.gancho)}</b></p>
          <ol>${p.guion.map((g) => `<li><b>${esc(g.momento)}</b>: ${esc(g.se_ve)}<br><i>«${esc(g.se_dice)}»</i>${g.texto_pantalla ? ` · 🅣 ${esc(g.texto_pantalla)}` : ""}</li>`).join("")}</ol>
          <p><b>Tomas</b></p><ul>${p.tomas.map((x) => `<li>${{ dron: "🚁", camara: "📷", gimbal: "🎥", microfono: "🎙️" }[x.equipo] || "📱"} ${esc(x.toma)} — ${esc(x.como)} (${esc(x.segundos)} s)</li>`).join("")}</ul>
          <p><b>Pregúntale al dueño</b></p><ul>${p.preguntas_al_dueno.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>
          <p><b>Llevar:</b> ${esc(p.llevar.join(", "))}</p>
          <p><b>Facebook:</b> ${esc(p.textos.facebook)}</p><p><b>Instagram:</b> ${esc(p.textos.instagram)}</p><p><b>TikTok:</b> ${esc(p.textos.tiktok)}</p>
          ${p.sala ? `<p class="pista">🎬 Ya está su proyecto en la pestaña Sala: pasa tus clips y la sala lo edita con este guion.</p>` : ""}
        </details>`).join("") : `<p class="pista">Elige un negocio y dale «🎬 Plan de visita».</p>`}
      </section>
      <section class="tarjeta"><h4>🚁 Tomas de dron (sin repetir)</h4>
        <p class="pista">${esc(t.precauciones_dron)}</p>
        <button class="btn" data-tp="dron">📍 Planear lugares nuevos</button>
        <ul>${t.dron.map((x) => `<li class="${x.usado ? "salio" : ""}"><b>${esc(x.lugar)}</b> (${esc(x.zona)}) — ${esc(x.toma)} · 🕐 ${esc(x.mejor_hora)}
          <br><small class="pista">${esc(x.por_que)} · ⚠️ ${esc(x.precaucion)}${x.fuente ? ` · <a href="${esc(x.fuente)}" target="_blank" rel="noopener">fuente</a>` : ""}</small>
          <button class="btn btn-mini" data-tp="dron_usado" data-id="${esc(x.id)}">${x.usado ? "↩️ No lo he grabado" : "✔ Ya lo grabé"}</button></li>`).join("")}</ul>
      </section>
      <section class="tarjeta"><h4>🧪 Formato que nadie hace en Tampico</h4>
        <button class="btn" data-tp="formatos">🔎 Ver qué hacen los foodies y proponer</button>
        ${t.lo_que_ya_hay ? `<p class="pista">Lo que ya hay: ${esc(t.lo_que_ya_hay)}</p>` : ""}
        ${t.formatos.map((f) => `<div class="tp-formato ${f.elegido ? "elegido" : ""}"><b>${f.elegido ? "⭐ " : ""}${esc(f.nombre)}</b> — ${esc(f.descripcion)}
          <br><small>Por qué funciona: ${esc(f.por_que_funciona)} · Cómo: ${esc(f.como_se_graba)} · Gancho: «${esc(f.ejemplo_gancho)}» · Serie: ${esc(f.serie)}</small>
          ${f.elegido ? "" : `<button class="btn btn-mini" data-tp="elegir_formato" data-id="${esc(f.id)}">Usar este</button>`}</div>`).join("")}
      </section>
      <section class="tarjeta"><h4>📣 Publicar</h4>
        <form id="tp-publicar"><input id="tp-titulo" placeholder="Título (para ti)">
          <textarea id="tp-fb" rows="2" placeholder="Texto para Facebook"></textarea>
          <textarea id="tp-ig" rows="2" placeholder="Texto para Instagram"></textarea>
          <textarea id="tp-tt" rows="2" placeholder="Texto para TikTok"></textarea>
          <label class="chk"><input type="checkbox" value="facebook" checked> Facebook</label>
          <label class="chk"><input type="checkbox" value="instagram" checked> Instagram</label>
          <label class="chk"><input type="checkbox" value="tiktok" checked> TikTok (te lo dejo para bajar)</label>
          <label class="btn btn-primario">📤 Elegir video o foto y publicar<input type="file" id="tp-archivo" accept="video/*,image/*" hidden></label></form>
        <ul>${t.publicaciones.map((p) => `<li><b>${esc(p.titulo || p.archivo)}</b> · ${esc(p.estado)}
          ${Object.entries(p.resultado || {}).map(([k, v]) => `<small class="${k.endsWith("_error") ? "error" : "pista"}">${esc(k)}: ${esc(v)}</small>`).join(" ")}
          ${p.redes.includes("tiktok") ? `<a class="btn btn-mini" href="/tampico/medio/${encodeURIComponent(p.archivo)}" download>⬇ Para TikTok</a>` : ""}
          ${p.estado !== "publicado" ? `<button class="btn btn-mini" data-tp="publicar" data-id="${esc(p.id)}">Reintentar</button>` : ""}</li>`).join("")}</ul>
      </section>
      <section class="tarjeta"><h4>♻️ Remarketing</h4>
        <button class="btn" data-tp="remarketing">💡 Ideas para reusar lo publicado</button>
        <ul>${t.remarketing.map((x) => `<li><b>${esc(x.red)}:</b> ${esc(x.idea)} <small class="pista">${esc(x.como)}</small></li>`).join("")}</ul>
      </section>`;
  }
  async function tpAccion(datos, boton, texto) {
    if (boton) { boton.disabled = true; boton.dataset.antes = boton.textContent; boton.textContent = texto || "Trabajando…"; }
    try {
      const r = await api("/api/tampico", datos);
      if (datos.accion === "buscar") alert(`Lupita encontró ${r.nuevos} negocio(s) nuevo(s).`);
      if (datos.accion === "dron") alert(`${r.nuevos} lugar(es) nuevo(s) para dron.`);
    } catch (err) { alert(err.message); }
    pintarTampico(true);
  }
  $("#tampico").addEventListener("click", (e) => {
    const b = e.target.closest("[data-tp]");
    if (!b) return;
    const a = b.dataset.tp;
    if (a === "guardar_propuesta") return tpAccion({ accion: "ajustes", propuesta: $("#tp-propuesta").value }, b, "Guardando…");
    if (a === "plan") {
      const notas = prompt("¿Algo que deba saber Fer? (platillos, qué te gustó, lo que te pidieron). Puedes dejarlo vacío.") ?? null;
      if (notas === null) return;
      return tpAccion({ accion: "plan", id: b.dataset.id, notas }, b, "Fer está planeando… (1-2 min)");
    }
    const textos = { dron: "Buscando lugares… (1 min)", formatos: "Investigando… (1-2 min)", remarketing: "Pensando…" };
    tpAccion({ accion: a, id: b.dataset.id }, b, textos[a]);
  });
  $("#tampico").addEventListener("change", (e) => {
    const sel = e.target.closest("[data-tp-estado]");
    if (sel) return tpAccion({ accion: "mover", id: sel.dataset.tpEstado, estado: sel.value });
    const aj = e.target.closest("[data-tp-aj]");
    if (aj) return tpAccion({ accion: "ajustes", [aj.dataset.tpAj]: aj.type === "checkbox" ? aj.checked : Number(aj.value) });
    if (e.target.id === "tp-archivo" && e.target.files[0]) {
      const archivo = e.target.files[0], f = e.target.closest("form");
      const redes = [...f.querySelectorAll('input[type=checkbox]:checked')].map((x) => x.value).join(",");
      const q = new URLSearchParams({ nombre: archivo.name, titulo: $("#tp-titulo").value, redes, facebook: $("#tp-fb").value,
        instagram: $("#tp-ig").value, tiktok: $("#tp-tt").value });
      const x = new XMLHttpRequest();
      const etiqueta = e.target.closest("label");
      x.open("POST", `/api/tampico/subir?${q}`);
      x.setRequestHeader("Content-Type", "application/octet-stream");
      x.upload.onprogress = (ev) => { if (ev.lengthComputable) etiqueta.firstChild.textContent = `Subiendo ${Math.round(ev.loaded / ev.total * 100)}%…`; };
      x.onload = () => { etiqueta.firstChild.textContent = "📤 Elegir video o foto y publicar"; if (x.status !== 200) alert("No se pudo subir"); pintarTampico(true); };
      x.send(archivo);
    }
  });
  $("#tampico").addEventListener("submit", (e) => {
    if (e.target.id !== "tp-buscar") return;
    e.preventDefault();
    tpAccion({ accion: "buscar", tipo: $("#tp-tipo").value, zona: $("#tp-zona").value }, e.target.querySelector("button"), "Buscando…");
  });
  setInterval(() => { if (!document.hidden) pintarTampico(); }, 30000);

  pintarTampico(true);
})();
