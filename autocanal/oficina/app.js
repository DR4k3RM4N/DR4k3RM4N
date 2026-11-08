// Interfaz: bandeja de aprobaciones, proyectos, chat y conexión en vivo con el servidor.
(() => {
  const $ = (s) => document.querySelector(s);
  let estado = null;
  const abiertos = new Set(); // ideas con el cuadro de opinión abierto
  const borradores = {}; // texto escrito en cada opinión, para no perderlo al repintar

  const ETIQUETA_ETAPA = { investigar: "Investiga", guion: "Guion", voz: "Voz", miniatura: "Miniatura", video: "Video",
                           blog: "Blog", revision: "Tu revisión", publicar: "Publica", publicado: "Publicado" };
  const AGENTE_ETAPA = { investigar: "investigador", guion: "guionista", voz: "locutor", miniatura: "disenadora",
                         video: "editor", blog: "redactora", revision: "jefe", publicar: "community", publicado: "community" };
  const VEREDICTO = { estafa_comprobada: ["NO PAGA", "rojo"], senales_de_alerta: ["CUIDADO", "naranja"],
                      paga_pero_no_vale_la_pena: ["NO VALE LA PENA", "amarillo"], legitima: ["SÍ PAGA", "verde"],
                      no_concluyente: ["SIN PRUEBAS", "gris"], tema: ["TEMA LIBRE", "amarillo"] };
  const ESTADO_PROY = { produccion: "En producción", revision: "Espera tu revisión", publicando: "Publicando",
                        publicado: "Publicado", error: "Con problema", descartado: "Descartado" };

  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const dinero = (usd) => (usd > 0 && usd < 0.01 ? "<$0.01" : `$${(usd || 0).toFixed(2)}`);
  const hora = (t) => new Date(t * 1000).toLocaleTimeString("es-MX", { hour: "2-digit", minute: "2-digit" });

  async function api(ruta, datos) {
    const r = await fetch(ruta, { method: datos ? "POST" : "GET", headers: { "Content-Type": "application/json" },
                                  body: datos ? JSON.stringify(datos) : undefined });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.error || "Algo salió mal");
    if (datos) refrescar(); // ver el cambio de inmediato, sin esperar la actualización en vivo
    return j;
  }
  function refrescar() {
    fetch("/api/estado").then((r) => r.json()).then((n) => { if (!estado || n.version >= estado.version) pintar(n); }).catch(() => {});
  }

  // ---------- conexión en vivo ----------
  function conectar() {
    const fuente = new EventSource("/eventos");
    fuente.onopen = () => { $("#conexion").textContent = "● en línea"; $("#conexion").className = "conexion ok"; };
    fuente.onerror = () => { $("#conexion").textContent = "reconectando…"; $("#conexion").className = "conexion"; };
    fuente.onmessage = (e) => pintar(JSON.parse(e.data));
  }

  function pintar(nuevo) {
    estado = nuevo;
    window.Oficina.actualizar(nuevo);
    $("#modo").hidden = !nuevo.demo;
    if (nuevo.gasto) {
      $("#gasto").hidden = false;
      $("#gasto").innerHTML = `💰 Hoy <b>${dinero(nuevo.gasto.hoy)}</b>${nuevo.gasto.tope ? `<span> / tope ${dinero(nuevo.gasto.tope)}</span>` : ""} <span>· mes ${dinero(nuevo.gasto.mes)}</span>`;
      $("#gasto").classList.toggle("tope", !!nuevo.gasto.tope && nuevo.gasto.hoy >= nuevo.gasto.tope);
    }
    pintarBandeja();
    pintarProyectos();
    pintarEquipo();
    pintarChat();
  }

  // ---------- bandeja ----------
  function pintarBandeja() {
    const ideas = estado.propuestas;
    const revisar = estado.proyectos.filter((p) => p.estado === "revision");
    const errores = estado.proyectos.filter((p) => p.estado === "error");
    const total = ideas.length + revisar.length + errores.length;
    $("#cuenta").hidden = !total;
    $("#cuenta").textContent = total;

    // no repintar mientras escribes una opinión
    if (document.activeElement?.closest?.("#bandeja textarea")) return;

    let html = "";
    if (revisar.length || errores.length) {
      html += `<h3 class="seccion">Para revisar</h3>`;
      for (const p of revisar) html += `
        <article class="tarjeta tarjeta-revision">
          <div class="quien"><span class="punto" style="--c:#e84d8a"></span>Paola dice: el video está listo</div>
          <h4>${esc(p.titulo)}</h4>
          <button class="btn btn-primario ancho" data-revisar="${esc(p.id)}">Revisar video</button>
        </article>`;
      for (const p of errores) html += `
        <article class="tarjeta tarjeta-error">
          <h4>${esc(p.titulo)}</h4>
          <p class="error">${esc(p.error)}</p>
          <div class="acciones">
            <button class="btn btn-primario" data-proy="${esc(p.id)}" data-accion="reintentar">Reintentar</button>
            <button class="btn" data-proy="${esc(p.id)}" data-accion="descartar">Descartar</button>
          </div>
        </article>`;
    }
    html += `<h3 class="seccion">Ideas de Paola ${ideas.length ? `<span class="sub">¿qué opinas?</span>` : ""}
      ${ideas.length > 1 ? `<button class="btn btn-mini" id="b-limpiar">🧹 Descartar todas</button>` : ""}</h3>`;
    if (!ideas.length) {
      html += `<p class="vacio">No hay ideas pendientes. Pídele a Paola que busque apps nuevas.</p>`;
    }
    for (const i of ideas) {
      const abierto = abiertos.has(i.id);
      html += `
        <article class="tarjeta" data-idea="${esc(i.id)}">
          ${i.personalizada ? `<div class="tuya">💡 Tu idea</div>` : ""}
          <div class="cabeza"><h4>${i.num ? `<span class="num">${i.num}</span>` : ""}${esc(i.titulo)}</h4><span class="chip chip-${esc(i.potencial_vistas)}">${esc(i.potencial_vistas)}</span></div>
          <p class="angulo">🎬 ${esc(i.angulo || "")}${i.formato ? ` <span class="chip chip-formato">${esc(i.formato)}</span>` : ""}</p>
          <p class="porque">${esc(i.por_que)}</p>
          <p class="appid">${esc(i.app_id)}</p>
          ${i.comentarios?.length ? `<ul class="comentarios">${i.comentarios.map((c) => `<li>💬 ${esc(c)}</li>`).join("")}</ul>` : ""}
          <div class="acciones">
            <button class="btn btn-si" data-id="${esc(i.id)}" data-accion="aprobar">👍 Hazlo</button>
            <button class="btn" data-id="${esc(i.id)}" data-abrir="${esc(i.id)}">💬 Opinar</button>
            <button class="btn btn-no" data-id="${esc(i.id)}" data-accion="rechazar">👎 No</button>
          </div>
          <div class="opinion" ${abierto ? "" : "hidden"}>
            <textarea rows="2" data-borrador="${esc(i.id)}" placeholder="Tu opinión: qué te gusta, qué cambiarías, o por qué no…">${esc(borradores[i.id] || "")}</textarea>
            <div class="acciones">
              <button class="btn" data-id="${esc(i.id)}" data-accion="comentar">Enviar opinión</button>
              <button class="btn btn-si" data-id="${esc(i.id)}" data-accion="aprobar" data-con-texto>Aprobar con esta nota</button>
              <button class="btn btn-no" data-id="${esc(i.id)}" data-accion="rechazar" data-con-texto>Rechazar con motivo</button>
            </div>
          </div>
        </article>`;
    }
    if (estado.preferencias?.length) {
      html += `<details class="gustos"><summary>Lo que Paola aprendió de ti (${estado.preferencias.length})</summary>
        <ul>${estado.preferencias.map((p) => `<li>${esc(p)}</li>`).join("")}</ul></details>`;
    }
    $("#bandeja").innerHTML = html;
  }

  $("#bandeja").addEventListener("input", (e) => {
    if (e.target.dataset.borrador) borradores[e.target.dataset.borrador] = e.target.value;
  });

  $("#bandeja").addEventListener("click", async (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    if (b.id === "b-limpiar") {
      if (!confirm(`¿Descartar las ${estado.propuestas.length} ideas de la bandeja? Paola no lo tomará como que no te gustaron.`)) return;
      b.disabled = true;
      try { await api("/api/ideas/descartar", {}); } catch (err) { alert(err.message); b.disabled = false; }
      return;
    }
    if (b.dataset.abrir) {
      abiertos.add(b.dataset.abrir);
      const caja = b.closest(".tarjeta").querySelector(".opinion");
      caja.hidden = false;
      caja.querySelector("textarea").focus();
      return;
    }
    if (b.dataset.revisar) return abrirRevision(b.dataset.revisar);
    if (b.dataset.proy) {
      b.disabled = true;
      try { await api(`/api/proyecto/${encodeURIComponent(b.dataset.proy)}`, { accion: b.dataset.accion }); }
      catch (err) { alert(err.message); b.disabled = false; }
      return;
    }
    if (b.dataset.accion) {
      const tarjeta = b.closest(".tarjeta");
      const texto = tarjeta.querySelector("textarea")?.value.trim() || "";
      if (b.dataset.accion === "comentar" && !texto) return tarjeta.querySelector("textarea").focus();
      tarjeta.classList.add("saliendo");
      b.disabled = true;
      try {
        await api(`/api/idea/${b.dataset.id}`, { accion: b.dataset.accion, texto: b.dataset.conTexto !== undefined || b.dataset.accion === "comentar" ? texto : "" });
        abiertos.delete(b.dataset.id);
        delete borradores[b.dataset.id];
        if (document.activeElement) document.activeElement.blur();
      } catch (err) { alert(err.message); tarjeta.classList.remove("saliendo"); b.disabled = false; }
    }
  });

  $("#form-ideas").addEventListener("submit", async (e) => {
    e.preventDefault();
    const boton = e.submitter || $("#form-ideas button");
    boton.disabled = true;
    try { await api("/api/ideas", { guia: $("#guia").value.trim() }); $("#guia").value = ""; }
    catch (err) { alert(err.message); }
    setTimeout(() => (boton.disabled = false), 4000);
  });

  // ---------- proyectos ----------
  function pintarProyectos() {
    const lista = estado.proyectos.filter((p) => p.estado !== "descartado");
    const ayudaBlog = `<details class="tarjeta ayuda-blog"><summary>🔌 Plugin para el blog (si WordPress no deja publicar)</summary>
      <p>Tu hosting borra la "llave" con la que la oficina entra a tu blog. Este plugin la deja pasar, sin tocar <code>.htaccess</code>:</p>
      <ol><li><a class="btn btn-mini btn-primario" href="/descargar/autocanal-conexion.zip" download>⬇️ Bajar autocanal-conexion.zip</a></li>
      <li>En tu WordPress: <b>Plugins → Añadir nuevo → Subir plugin</b> → elige el .zip → <b>Instalar ahora</b> → <b>Activar</b>.</li>
      <li>Aquí, en el video con blog pendiente, dale <b>Subir blog</b>.</li></ol></details>`;
    if (!lista.length) { $("#proyectos").innerHTML = `<p class="vacio">Aún no hay proyectos. Aprueba una idea para arrancar.</p>${ayudaBlog}`; return; }
    const agentes = {};
    estado.agentes.forEach((a) => (agentes[a.id] = a));
    $("#proyectos").innerHTML = lista.map((p) => {
      const pasos = estado.etapas.map((et) => {
        const a = agentes[AGENTE_ETAPA[et]];
        let clase = "";
        const est = (p.etapas || {})[et];
        if (est) clase = { hecha: "hecho", trabajando: "actual", fallo: "falla", en_cola: "cola", esperando: "", cancelada: "" }[est] || "";
        if (et === "revision") clase = p.estado === "revision" ? "actual" : ["publicando", "publicado"].includes(p.estado) ? "hecho" : "";
        if (et === "publicar") clase = p.estado === "publicando" ? "actual" : p.estado === "publicado" ? "hecho" : "";
        if (et === "publicado") clase = p.estado === "publicado" ? "hecho" : "";
        if (p.estado === "error" && clase === "actual") clase = "falla";
        return `<li class="${clase}" title="${esc(ETIQUETA_ETAPA[et])} · ${esc(a?.nombre)}"><span style="--c:${a?.color}"></span>${esc(ETIQUETA_ETAPA[et])}</li>`;
      }).join("");
      const pub = p.publicado ? `<div class="enlaces"><a href="${esc(p.publicado.youtube)}" target="_blank" rel="noopener">▶ YouTube</a>
        ${p.publicado.blog?.link ? `<a href="${esc(p.publicado.blog.link)}" target="_blank" rel="noopener">✎ Blog</a>` : ""}</div>` : "";
      return `<article class="tarjeta">
        <div class="cabeza"><h4>${esc(p.titulo)}</h4><span class="chip chip-estado-${esc(p.estado)}">${esc(ESTADO_PROY[p.estado] || p.estado)}</span></div>
        <ol class="pasos">${pasos}</ol>${pub}
        ${p.publicado?.privacidad === "private" ? `<div class="pendiente-blog"><span>🔒 En YouTube quedó en <b>privado</b>${p.publicado.privacidad_pedida !== "private"
            ? " aunque pediste público (YouTube lo hace con las apps de Google que no han pasado su auditoría)" : ""}. Ábrelo en YouTube Studio → Visibilidad → Público.</span></div>` : ""}
        ${p.blog_pendiente ? `<div class="pendiente-blog">📝 El blog quedó pendiente${p.publicado?.blog_error ? `: ${esc(p.publicado.blog_error.slice(0, 160))}` : ""}
          <span class="fila"><button class="btn btn-mini btn-primario" data-subir-blog="${esc(p.id)}">Subir blog</button>
          <a class="btn btn-mini" href="/descargar/autocanal-conexion.zip" download>🔌 Plugin para el blog</a></span></div>` : ""}
        ${p.costo ? `<div class="costo">💰 ${dinero(p.costo)} <span>${Object.entries(p.costos || {}).map(([e, v]) => `${esc(ETIQUETA_ETAPA[e] || e)} ${dinero(v)}`).join(" · ")}</span></div>` : ""}
        ${["revision", "publicado"].includes(p.estado) ? `<button class="btn ancho" data-revisar="${esc(p.id)}">Ver video</button>` : ""}
      </article>`;
    }).join("") + ayudaBlog;
  }
  $("#proyectos").addEventListener("click", async (e) => {
    const sb = e.target.closest("[data-subir-blog]");
    if (sb) {
      sb.disabled = true;
      try { await api(`/api/proyecto/${encodeURIComponent(sb.dataset.subirBlog)}`, { accion: "subir_blog" }); sb.textContent = "Carla lo está subiendo…"; }
      catch (err) { alert(err.message); sb.disabled = false; }
      return;
    }
    const b = e.target.closest("[data-revisar]");
    if (b) abrirRevision(b.dataset.revisar);
  });

  // ---------- chat ----------
  function pintarChat() {
    const agentes = {};
    estado.agentes.forEach((a) => (agentes[a.id] = a));
    const lista = $("#chat");
    const abajo = lista.scrollHeight - lista.scrollTop - lista.clientHeight < 40;
    lista.innerHTML = estado.log.map((m) => {
      const a = agentes[m.quien] || { nombre: m.quien, color: "#888" };
      return `<li><span class="hora">${hora(m.t)}</span> <b style="color:${a.color === "#334155" ? "#cbd5e1" : a.color}">${esc(a.id === "jefe" ? "Tú" : a.nombre)}</b> ${esc(m.texto)}</li>`;
    }).join("");
    if (abajo) lista.scrollTop = lista.scrollHeight;
  }

  function abrirPestana(nombre) {
    document.querySelectorAll(".pestana").forEach((x) => x.classList.toggle("activa", x.dataset.tab === nombre));
    document.querySelectorAll(".contenido").forEach((c) => (c.hidden = c.id !== `tab-${nombre}`));
    if (nombre === "chat") $("#chat").scrollTop = $("#chat").scrollHeight;
    if (nombre === "equipo") pintarEquipo();
    if (nombre === "estilo") pintarEstilo();
    if (nombre === "sala" && typeof pintarSala === "function") pintarSala();
  }
  document.querySelectorAll(".pestana").forEach((p) => p.addEventListener("click", () => abrirPestana(p.dataset.tab)));

  // ---------- revisión del video ----------
  async function abrirRevision(id) {
    const d = await api(`/api/proyecto/${encodeURIComponent(id)}`);
    const p = d.proyecto;
    const [palabra, color] = VEREDICTO[d.veredicto] || ["—", "gris"];
    const editable = p.estado === "revision";
    $("#modal-cuerpo").innerHTML = `
      <h2 id="modal-titulo">${esc(p.titulo)}</h2>
      <div class="revision">
        <div class="medios">
          ${d.video ? `<video src="${esc(d.video)}" controls preload="metadata" poster="${esc(d.miniatura || "")}"></video>` : "<p>Sin video</p>"}
          ${d.miniaturas && d.miniaturas.length > 1 ? `<h3>Miniatura <small>${esc(d.miniatura_razon || "")}</small></h3>
            <div class="mini-opciones">${d.miniaturas.map((m, k) => `<button class="mini-op ${k === d.miniatura_elegida ? "sel" : ""}" data-mini="${k + 1}" ${editable ? "" : "disabled"} title="${esc(m.texto)}">
              <img src="${esc(m.url)}?v=${Date.now()}" alt="Opción ${k + 1}: ${esc(m.texto)}"><span>${k === d.miniatura_elegida ? "✓ Elegida" : `Opción ${k + 1}`}</span></button>`).join("")}</div>`
          : d.miniatura ? `<figure><img src="${esc(d.miniatura)}" alt="Miniatura del video"><figcaption>Miniatura</figcaption></figure>` : ""}
          ${d.blog_preview ? `<a class="btn ancho" href="${esc(d.blog_preview)}" target="_blank" rel="noopener">Ver borrador del blog: ${esc(d.blog_titulo)}</a>` : ""}
        </div>
        <div class="datos">
          <p><span class="sello sello-${color}">${palabra}</span></p>
          <p>${esc(d.resumen)}</p>
          ${d.pendiente.length ? `<h3>Antes de publicar, compruébalo tú</h3>
            ${editable ? `<label class="todo-check"><input type="checkbox" id="check-todo"> ✅ <b>Ya revisé todo</b> (marca todas)</label>` : ""}
            <ul class="checklist">${d.pendiente.map((x, k) => `<li><label><input type="checkbox" class="check" ${editable ? "" : "checked disabled"}> ${esc(x)}</label></li>`).join("")}
            <li><label><input type="checkbox" class="check" ${editable ? "" : "checked disabled"}> Cada afirmación del guion tiene respaldo</label></li></ul>` : ""}
          <h3>Evidencia</h3>
          <ul class="senales">${d.senales.map((s) => `<li><span class="grav grav-${esc(s.gravedad)}">${esc(s.gravedad)}</span> <b>${esc(s.senal)}</b> — ${esc(s.evidencia)} <i>(${esc(s.fuente)})</i></li>`).join("")}</ul>
          ${d.fuentes.length ? `<details><summary>Fuentes (${d.fuentes.length})</summary><ul>${d.fuentes.map((f) => `<li><a href="${esc(f.url)}" target="_blank" rel="noopener">${esc(f.titulo)}</a></li>`).join("")}</ul></details>` : ""}
          ${d.palabra_clave ? `<h3>SEO del blog</h3><p class="seo"><b>Palabra clave:</b> ${esc(d.palabra_clave)}<br>
            <b>Secundarias:</b> ${esc((d.palabras_secundarias || []).join(", "))}<br><b>Meta descripción:</b> ${esc(d.meta_descripcion || "")}</p>` : ""}
          <h3>Título</h3>
          <div class="titulos">${d.titulos.map((t, k) => `<label><input type="radio" name="titulo" value="${k + 1}" ${k ? "" : "checked"} ${editable ? "" : "disabled"}> ${esc(t)}</label>`).join("")}
            ${editable ? `<label class="titulo-libre"><input type="radio" name="titulo" value="libre"> ✍️ <b>Mi título</b></label>
            <div class="libre-caja">
              <input id="titulo-libre" maxlength="100" placeholder="Escribe tu título como lo quieras…" autocomplete="off">
              <button type="button" class="btn btn-mini" id="b-mejorar">✨ Mejorar con IA</button>
            </div>
            <div class="libre-info"><small id="largo-titulo">0 / 100</small> <small id="nota-titulo"></small></div>
            <div id="opciones-ia" class="opciones-ia"></div>` : ""}</div>
          <details><summary>Guion (${d.escenas.length} escenas)</summary><ol class="guion">${d.escenas.map((e) => `<li>${esc(e)}</li>`).join("")}</ol></details>
        </div>
      </div>
      ${editable ? `
      <div class="pie">
        <textarea id="cambios" rows="2" placeholder="¿Qué cambiarías del video? Ej. el gancho más directo… (Esto rehace el guion y el video. Para cambiar solo el título usa «✍️ Mi título» arriba.)"></textarea>
        <div class="privacidad">
          <span>En YouTube:</span>
          ${[["public", "🌎 Público"], ["unlisted", "🔗 Sin listar"], ["private", "🔒 Privado"]].map(([v, t]) =>
            `<label><input type="radio" name="privacidad" value="${v}" ${v === privacidadInicial(d) ? "checked" : ""}> ${t}</label>`).join("")}
        </div>
        <div class="acciones">
          <button class="btn" id="b-cambios">✏️ Pedir cambios</button>
          <button class="btn btn-no" id="b-descartar">Descartar</button>
          <button class="btn btn-primario" id="b-publicar" disabled>Publicar ✔</button>
        </div>
        <p class="nota" id="nota-publicar">Marca la lista de comprobación para poder publicar.</p>
      </div>` : ""}`;
    $("#modal").hidden = false;
    $("#modal-cerrar").focus();
    document.querySelectorAll("[data-mini]").forEach((b) => (b.onclick = async () => {
      try { await api(`/api/proyecto/${encodeURIComponent(id)}`, { accion: "miniatura", titulo: Number(b.dataset.mini) }); abrirRevision(id); }
      catch (err) { alert(err.message); }
    }));
    if (!editable) return;
    const checks = [...document.querySelectorAll("#modal-cuerpo input.check")];
    const todo = $("#check-todo");
    const revisarChecks = () => {
      const listo = checks.every((c) => c.checked);
      $("#b-publicar").disabled = !listo;
      $("#nota-publicar").hidden = listo;
      if (todo) todo.checked = listo;
    };
    checks.forEach((c) => c.addEventListener("change", revisarChecks));
    todo?.addEventListener("change", () => { checks.forEach((c) => (c.checked = todo.checked)); revisarChecks(); });
    revisarChecks();
    // 4ª opción: tu propio título, tal cual o mejorado con IA (sin rehacer nada del video)
    const libre = $("#titulo-libre"), radioLibre = document.querySelector("input[name=titulo][value=libre]");
    const contar = () => { $("#largo-titulo").textContent = `${libre.value.length} / 100`; };
    libre.addEventListener("input", () => { radioLibre.checked = true; contar(); });
    libre.addEventListener("focus", () => { radioLibre.checked = true; });
    $("#b-mejorar").onclick = async () => {
      const idea = libre.value.trim();
      if (idea.length < 3) { libre.focus(); $("#nota-titulo").textContent = "Escribe primero tu idea."; return; }
      const b = $("#b-mejorar");
      b.disabled = true; b.textContent = "✨ Gabi está pensando…";
      try {
        const r = await api(`/api/proyecto/${encodeURIComponent(id)}`, { accion: "mejorar_titulo", texto: idea });
        $("#opciones-ia").innerHTML = `<small>Pícale a una para usarla (puedes editarla después):</small>`
          + r.opciones.map((o) => `<button type="button" class="opcion-ia" data-titulo="${esc(o)}">${esc(o)} <small>${o.length}</small></button>`).join("");
        $("#nota-titulo").textContent = r.costo ? `costó ${dinero(r.costo)}` : "";
      } catch (err) { alert(err.message); }
      b.disabled = false; b.textContent = "✨ Mejorar con IA";
    };
    $("#opciones-ia").addEventListener("click", (e) => {
      const o = e.target.closest("[data-titulo]");
      if (!o) return;
      libre.value = o.dataset.titulo; radioLibre.checked = true; contar();
      document.querySelectorAll(".opcion-ia").forEach((x) => x.classList.toggle("sel", x === o));
    });
    const enviar = async (accion, texto = "") => {
      const elegido = document.querySelector("input[name=titulo]:checked")?.value || "1";
      const titulo_libre = elegido === "libre" ? libre.value.trim() : "";
      if (elegido === "libre" && accion === "publicar" && !titulo_libre) { libre.focus(); return alert("Escribe tu título o elige uno de los de arriba."); }
      const titulo = elegido === "libre" ? 1 : Number(elegido);
      const privacidad = document.querySelector("input[name=privacidad]:checked")?.value || "";
      try { localStorage.setItem("yt_privacidad", privacidad); } catch { /* sin almacenamiento */ }
      try { await api(`/api/proyecto/${encodeURIComponent(id)}`, { accion, texto, titulo, privacidad, titulo_libre }); cerrarModal(); }
      catch (err) { alert(err.message); }
    };
    $("#b-publicar").onclick = () => enviar("publicar");
    $("#b-descartar").onclick = () => confirm("¿Descartar este video?") && enviar("descartar");
    $("#b-cambios").onclick = () => {
      const t = $("#cambios").value.trim();
      if (!t) return $("#cambios").focus();
      enviar("cambios", t);
    };
  }

  // cómo salió la última vez (o lo que diga YT_PRIVACIDAD en el servidor)
  function privacidadInicial(d) {
    let v = "";
    try { v = localStorage.getItem("yt_privacidad") || ""; } catch { /* sin almacenamiento */ }
    return ["public", "unlisted", "private"].includes(v) ? v : (d.yt_privacidad || "private");
  }

  function cerrarModal() {
    $("#modal").hidden = true;
    $("#modal-cuerpo").querySelector("video")?.pause();
  }
  $("#modal-cerrar").addEventListener("click", cerrarModal);
  $("#modal").addEventListener("click", (e) => { if (e.target.id === "modal") cerrarModal(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") cerrarModal(); });

  // ---------- equipo: tareas de cada agente ----------
  const DESCRIPCION = {
    productora: "Busca apps en Play Store, te propone ideas, aprende de tus opiniones y coordina al equipo.",
    investigador: "Lee reseñas, busca en internet y arma el expediente de evidencia.",
    guionista: "Escribe el guion con tu estilo, los títulos y el texto de la miniatura.",
    locutor: "Narra cada escena del guion.", disenadora: "Diseña la miniatura del video.",
    editor: "Edita el video: escenas, zoom, subtítulos y música.",
    redactora: "Escribe la entrada SEO del blog con capturas.",
    community: "Publica en WordPress y YouTube y conecta uno con otro.",
    jefe: "Apruebas ideas, opinas y das el visto bueno final.",
  };
  const ESTADO_TAREA = { esperando: "Esperando", en_cola: "En fila", trabajando: "Trabajando", hecha: "Hecha",
                         fallo: "Falló", cancelada: "Cancelada" };
  let agenteVisto = null;

  const reloj = () => (estado.ahora || Date.now() / 1000) + (Date.now() - (estado._recibido || Date.now())) / 1000;
  function duracion(seg) {
    seg = Math.max(0, Math.round(seg));
    return seg < 60 ? `${seg}s` : seg < 3600 ? `${Math.floor(seg / 60)}m ${String(seg % 60).padStart(2, "0")}s` : `${Math.floor(seg / 3600)}h ${Math.floor(seg / 60) % 60}m`;
  }
  function haceCuanto(t) {
    const s = reloj() - t;
    return s < 60 ? "hace un momento" : s < 3600 ? `hace ${Math.floor(s / 60)} min` : s < 86400 ? `hace ${Math.floor(s / 3600)} h` : `hace ${Math.floor(s / 86400)} d`;
  }
  // Los dos equipos juntos (YouTube + TikTok Shop) y el filtro según el ala que estás viendo
  const esTT = (id) => id.startsWith("tt_");
  const todasLasTareas = () => [...(estado.tareas || []), ...(estadoTT?.tareas || []), ...(estadoSala?.tareas || [])];
  const tareasDe = (id) => todasLasTareas().filter((t) => t.agente === id);
  // (las tareas de los editores de la sala vienen en estadoSala.tareas)
  const equipoCompleto = () => [...estado.agentes, ...(window.Oficina.equipoTT?.() || []), ...(window.Oficina.equipoSala?.() || [])];
  function equipoVisible() {
    const ala = window.Oficina.ala?.() || "todo";
    if (ala === "edicion") return equipoCompleto().filter((a) => ["editor", "tt_editor", "jefe"].includes(a.id) || a.id.startsWith("sala_"));
    return equipoCompleto().filter((a) => ala === "todo" || a.id === "jefe" || (ala === "tiktok") === esTT(a.id));
  }
  const TITULO_ALA = { todo: "Todo el edificio", youtube: "▶ Equipo YouTube", tiktok: "🛒 Equipo TikTok Shop",
                       edicion: "🎬 Los editores (y tus compus en la pestaña Sala)" };
  function estadoAgente(a) {
    const ts = tareasDe(a.id);
    if (ts.some((t) => t.estado === "trabajando")) return ["Trabajando", "trab"];
    if (ts.some((t) => t.estado === "en_cola")) return ["Con tareas en fila", "cola"];
    if (a.ubicacion?.startsWith("visita:")) return ["Entregando trabajo", "trab"];
    if (ts.some((t) => t.estado === "esperando")) return ["Esperando a otro", "espera"];
    return ["Libre", "libre"];
  }

  let presionado = false;
  $("#equipo").addEventListener("pointerdown", () => (presionado = true));
  document.addEventListener("pointerup", () => setTimeout(() => (presionado = false), 0));

  function pintarEquipo(forzar = false) {
    if (!estado || $("#tab-equipo").hidden) return;
    // no repintar mientras se da clic o se escribe (solo cuadros de texto, no botones)
    if (presionado && !forzar) return;
    if (document.activeElement?.matches?.("#equipo input, #equipo textarea, #equipo select")) return;
    const cont = $("#equipo");
    if (!agenteVisto) {
      const terminadas = (estado.tareas || []).filter((t) => ["hecha", "fallo", "cancelada"].includes(t.estado)).length;
      const lista = equipoVisible();
      const ala = window.Oficina.ala?.() || "todo";
      cont.innerHTML = `<div class="equipo-cabeza"><p class="pista"><b>${esc(TITULO_ALA[ala])}</b> · ${lista.length} · Pícale a un agente (aquí o en la oficina) para ver sus tareas.</p>
        ${terminadas && ala !== "tiktok" ? `<button class="btn btn-mini" data-limpiar="">🧹 Borrar terminadas (${terminadas})</button>` : ""}</div>
        <div class="equipo-lista">${lista.map((a) => {
          const [txt, cls] = estadoAgente(a);
          const actual = tareasDe(a.id).find((t) => t.estado === "trabajando");
          const fila = tareasDe(a.id).filter((t) => ["en_cola", "esperando"].includes(t.estado)).length;
          return `<button class="agente-tarjeta" data-agente="${a.id}" style="--c:${a.color}">
            <canvas class="retrato" data-retrato="${a.id}" width="72" height="152"></canvas>
            <span class="agente-info">
              <b>${esc(a.id === "jefe" ? "Tú" : a.nombre)}</b> <small>${esc(a.rol)}</small>
              <span class="estado-chip ${cls}">${esc(txt)}</span>
              <span class="agente-ahora">${actual ? `${esc(actual.accion)} · ${esc(actual.titulo)}` : a.id === "jefe" ? "Revisa tu bandeja" : a.enObra ? "🚧 Su oficina está apagada" : "—"}</span>
              ${fila ? `<span class="agente-fila">${fila} en fila</span>` : ""}
            </span>
          </button>`;
        }).join("")}</div>`;
    } else {
      const a = equipoCompleto().find((x) => x.id === agenteVisto);
      if (!a) { agenteVisto = null; return pintarEquipo(true); }
      const ts = tareasDe(a.id).slice().reverse();
      const actual = ts.filter((t) => t.estado === "trabajando");
      const fila = ts.filter((t) => ["en_cola", "esperando"].includes(t.estado)).reverse();
      const hechas = ts.filter((t) => ["hecha", "fallo", "cancelada"].includes(t.estado)).slice(0, 10);
      const frases = [...estado.log, ...(estadoTT?.log || [])].filter((m) => m.quien === a.id).slice(-3).reverse();
      const [txt, cls] = estadoAgente(a);
      const tarjeta = (t, viva) => `<li class="tarea tarea-${t.estado}">
          <div class="tarea-cabeza"><b>${esc(t.accion)}</b><span class="estado-chip ${t.estado}">${esc(ESTADO_TAREA[t.estado] || t.estado)}</span></div>
          <div class="tarea-sub">${esc(t.titulo || "")}</div>
          ${t.espera ? `<div class="tarea-espera">⏳ ${esc(t.espera)}</div>` : ""}
          ${viva && t.paso ? `<div class="tarea-espera">▶ ${esc(t.paso)}</div>` : ""}
          ${viva ? `<div class="tarea-tiempo">⏱ ${duracion(reloj() - t.inicio)}${t.avance ? ` · ${Math.round(t.avance * 100)}%` : ""}</div><div class="barra-tarea"><b></b></div>` : ""}
          ${t.fin && t.inicio ? `<div class="tarea-tiempo">${t.estado === "hecha" ? "✔" : "✖"} en ${duracion(t.fin - t.inicio)} · ${haceCuanto(t.fin)}</div>` : ""}
          ${t.resultado ? `<div class="tarea-sub">${esc(t.resultado)}</div>` : ""}
          ${t.costo ? `<div class="tarea-tiempo">💰 ${dinero(t.costo)} · ${esc((t.modelo || "").replace("claude-", ""))}</div>` : ""}
          ${(t.llamadas || []).length > 1 ? `<ul class="desglose">${t.llamadas.map((l) => `<li>${esc(l.que)} <b>${dinero(l.costo)}</b> <small>${(l.entrada / 1000).toFixed(1)}k entrada · ${(l.salida / 1000).toFixed(1)}k salida</small></li>`).join("")}</ul>` : ""}
          ${t.error ? `<div class="tarea-error">${esc(t.error)}</div>` : ""}
        </li>`;
      cont.innerHTML = `<button class="btn btn-mini volver" data-volver>← Todo el equipo</button>
        <div class="agente-detalle" style="--c:${a.color}">
          <canvas class="retrato grande" data-retrato="${a.id}" width="108" height="228"></canvas>
          <div>
            <h3>${esc(a.id === "jefe" ? "Tú" : a.nombre)}</h3>
            <p class="rol">${esc(a.rol)}</p>
            <span class="estado-chip ${cls}">${esc(txt)}</span>
            <p class="desc">${esc(DESCRIPCION[a.id] || a.desc || "")}</p>
          </div>
        </div>
        ${a.id === "jefe" ? `<p class="vacio">Tus pendientes están en la Bandeja.</p>` : a.enObra ? `<p class="vacio">🚧 La oficina de TikTok Shop está apagada: ${esc(a.nombre)} trabaja cuando esté prendida.</p>` : `
        <h4 class="seccion-mini">Ahora</h4>
        ${actual.length ? `<ul class="tareas">${actual.map((t) => tarjeta(t, true)).join("")}</ul>` : `<p class="vacio">${a.estado === "libre" ? "Sin tareas: está libre." : "Entregando trabajo a un compañero."}</p>`}
        <h4 class="seccion-mini">En fila ${fila.length ? `(${fila.length})` : ""}</h4>
        ${fila.length ? `<ul class="tareas">${fila.map((t) => tarjeta(t, false)).join("")}</ul>` : `<p class="vacio">Nada en fila.</p>`}
        <h4 class="seccion-mini">Terminadas ${hechas.length && !esTT(a.id) ? `<button class="btn btn-mini" data-limpiar="${esc(a.id)}">🧹 Borrar</button>` : ""}</h4>
        ${hechas.length ? `<ul class="tareas">${hechas.map((t) => tarjeta(t, false)).join("")}</ul>` : `<p class="vacio">Todavía nada.</p>`}`}
        ${frases.length ? `<h4 class="seccion-mini">Lo último que dijo</h4><ul class="frases">${frases.map((m) => `<li>“${esc(m.texto)}” <small>${hora(m.t)}</small></li>`).join("")}</ul>` : ""}`;
      // barra de avance aproximada
      const DUR = { ficha: 25, tomas: 25, ideas: 30, investigar: 90, guion: 60, voz: 45, miniatura: 8, video: 150, blog: 60, publicar: 60 };
      cont.querySelectorAll(".tarea-trabajando .barra-tarea b").forEach((b, k) => {
        const t = actual[k];
        const av = t.avance != null ? t.avance : 1 - Math.exp(-(reloj() - t.inicio) / (DUR[t.etapa] || 60) * 1.6);
        b.style.width = `${Math.min(97, av * 100)}%`;
      });
    }
    cont.querySelectorAll("[data-retrato]").forEach((c) => window.Oficina.retrato(c.dataset.retrato, c));
  }

  function verAgente(id) {
    agenteVisto = id;
    window.Oficina.seleccionar(id);
    abrirPestana("equipo");
    pintarEquipo(true);
    $("#tab-equipo").scrollTop = 0;
  }

  $("#equipo").addEventListener("click", (e) => {
    if (e.target.closest("[data-volver]")) { agenteVisto = null; window.Oficina.seleccionar(null); return pintarEquipo(true); }
    const limpiar = e.target.closest("[data-limpiar]");
    if (limpiar) {
      const quien = limpiar.dataset.limpiar;
      if (!confirm(quien ? "¿Borrar las tareas terminadas de este agente?" : "¿Borrar las tareas terminadas de todo el equipo?")) return;
      api("/api/tareas/limpiar", { agente: quien || null }).then(() => pintarEquipo(true)).catch((err) => alert(err.message));
      return;
    }
    const t = e.target.closest("[data-agente]");
    if (t) verAgente(t.dataset.agente);
  });
  setInterval(() => { if (agenteVisto || !$("#tab-equipo").hidden) pintarEquipo(); }, 1000);
  window.addEventListener("ala", () => pintarEquipo(true));
  // A la derecha solo los menús de la oficina que estás viendo (en "Todo", todos)
  const PESTANAS_ALA = { youtube: ["bandeja", "proyectos", "estilo", "equipo", "chat"], tiktok: ["shop", "equipo", "chat"],
                         edicion: ["sala", "equipo"] };
  function menusDelAla(ala) {
    const visibles = PESTANAS_ALA[ala];
    document.querySelectorAll(".pestana").forEach((b) => (b.hidden = !!visibles && !visibles.includes(b.dataset.tab)));
    const activa = document.querySelector(".pestana.activa");
    if (activa?.hidden) abrirPestana(visibles[0]);
  }
  window.addEventListener("ala", (e) => menusDelAla(e.detail));
  menusDelAla(window.Oficina.ala?.());
  // pasar el mouse por una tarjeta del equipo marca al agente en la oficina
  $("#equipo").addEventListener("mouseover", (e) => window.Oficina.encima(e.target.closest("[data-agente]")?.dataset.agente || null));
  $("#equipo").addEventListener("mouseleave", () => window.Oficina.encima(null));

  $("#lienzo").addEventListener("click", (e) => {
    const id = window.Oficina.agenteEn(e.clientX, e.clientY);
    if (id) return verAgente(id);
    if (window.Oficina.compuEn(e.clientX, e.clientY)) abrirPestana("sala");
  });
  $("#lienzo").addEventListener("mousemove", (e) => {
    const id = window.Oficina.agenteEn(e.clientX, e.clientY);
    window.Oficina.encima(id);
    $("#lienzo").style.cursor = id || window.Oficina.compuEn(e.clientX, e.clientY) ? "pointer" : "default";
  });
  $("#lienzo").addEventListener("mouseleave", () => window.Oficina.encima(null));

  // ---------- estilo: lo que los agentes aprenden de ti ----------
  const SUBIDAS = {
    cara: ["Tu cara (PNG sin fondo)", ".png"], fuente: ["Tu tipografía (.ttf)", ".ttf,.otf"],
    musica: ["Música de fondo", ".mp3,.m4a,.wav"], whoosh: ["Sonido en cambios de escena", ".mp3,.wav,.m4a"],
    intro: ["Intro de tu canal", ".mp4,.mov,.webm"], outro: ["Cierre / outro", ".mp4,.mov,.webm"],
    referencia: ["Video de referencia (cómo te gusta la edición)", ".mp4,.mov,.webm,.mkv"],
  };

  function subida(tipo, tiene) {
    const [nombre, acepta] = SUBIDAS[tipo];
    return `<div class="subida"><span>${tiene ? "✅" : "⬜"} ${esc(nombre)}</span>
      <label class="btn btn-mini">${tiene ? "Cambiar" : "Subir"}<input type="file" accept="${acepta}" data-subir="${tipo}" hidden></label>
      ${tiene ? `<button class="btn btn-mini btn-no" data-borrar="${tipo}">Quitar</button>` : ""}</div>`;
  }

  const NOMBRE_FX = { texto_pop: "textos que saltan", contador: "contadores", sello: "sellos", cintillo: "cintillos",
    golpe_zoom: "zoom de golpe", sacudida: "sacudidas", flash: "destellos", marco_alerta: "bordes de alerta" };
  let estado_estilo = null;
  async function pintarEstilo() {
    let e;
    try { e = await api("/api/estilo"); } catch { return; }
    estado_estilo = e;
    const a = e.ajustes, m = e.miniaturas, b = e.blog;
    const sel = (k, ops) => `<select data-ajuste="${k}">${ops.map(([v, t]) => `<option value="${v}" ${String(a[k]) === String(v) ? "selected" : ""}>${t}</option>`).join("")}</select>`;
    const chk = (k, t) => `<label class="chk"><input type="checkbox" data-ajuste="${k}" ${a[k] ? "checked" : ""}> ${t}</label>`;
    $("#estilo").innerHTML = `
      <section class="tarjeta estilo-sec" style="--c:#10b981">
        <h4>🎨 Miniaturas · Dani</h4>
        <p class="pista">Sube de 3 a 10 miniaturas que te gusten (tuyas o de canales que admiras). Dani aprende el estilo y lo usa en cada video.</p>
        <div class="refs">${e.referencias.map((n) => `<figure><img src="/estilo/miniaturas/${encodeURIComponent(n)}" alt="${esc(n)}"><button class="quitar" data-borrar="miniatura" data-nombre="${esc(n)}" aria-label="Quitar">✕</button></figure>`).join("")}
          <label class="ref-nueva">＋<br><small>Subir</small><input type="file" accept="image/*" multiple data-subir="miniatura" hidden></label></div>
        ${subida("cara", e.archivos.cara)}${subida("fuente", e.archivos.fuente)}
        <div class="acciones"><button class="btn btn-primario" data-estudiar="miniaturas" ${e.referencias.length ? "" : "disabled"}>🔍 Que Dani estudie el estilo</button>
          <label class="chk">Opciones por video ${sel("opciones_miniatura", [[1, "1"], [2, "2"], [3, "3"]])}</label></div>
        ${m ? `<div class="aprendido"><b>Lo que aprendió:</b> ${esc(m.descripcion)}
          <div class="colores">${["color_fondo", "color_fondo_2", "color_texto", "color_borde_texto", "color_acento"].map((k) => `<span style="background:${esc(m[k])}" title="${k}"></span>`).join("")}</div>
          <small>Fondo: ${esc(m.fondo)} · Texto: ${esc(m.posicion_texto)}, ${esc(m.tamano_texto)}${m.mayusculas ? ", mayúsculas" : ""} · ${esc((m.elementos || []).join(", ") || "sin extras")}</small></div>` : ""}
      </section>
      <section class="tarjeta estilo-sec" style="--c:#ef4444">
        <h4>🎬 Edición · Edu</h4>
        <p class="pista">Pega el enlace de un video (YouTube, TikTok, Instagram…) o sube el archivo, con la edición que
          te gusta. Edu (30 años en motion graphics y videos de alto impacto) mide su ritmo, revisa subtítulos,
          movimientos y efectos, y ajusta todo esto solo. Con 1 o 2 minutos basta.</p>
        <input id="ref-url" type="url" placeholder="https://www.youtube.com/watch?v=…" value="${esc(e.referencia_url?.url || "")}">
        ${e.referencia_url ? `<p class="pista">🔗 Último video estudiado por enlace: ${esc(e.referencia_url.titulo || e.referencia_url.url)}</p>` : ""}
        ${subida("referencia", e.archivos.referencia && !e.referencia_url)}
        <div class="acciones"><button class="btn btn-primario" data-estudiar="video">🎞️ Que Edu estudie la edición</button></div>
        ${e.edicion ? `<div class="aprendido"><b>Lo que aprendió:</b> ${esc(e.edicion.descripcion)}
          <br><small>Ritmo: ≈${esc(e.edicion.cortes_por_minuto)} cortes por minuto${(e.edicion.efectos || []).length ? ` · Efectos: ${esc(e.edicion.efectos.map((x) => NOMBRE_FX[x] || x).join(", "))}` : ""}</small>
          ${(e.edicion.consejos || []).length ? `<details><summary>Lo que tendrías que agregar tú</summary><ul>${e.edicion.consejos.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></details>` : ""}</div>` : ""}
        <div class="ajustes">
          <label>Subtítulos ${sel("subtitulos", [["grande", "Grandes (estilo shorts)"], ["clasico", "Clásicos"]])}</label>
          <label>Transiciones ${sel("transicion", [["variado", "Variadas"], ["deslizar", "Deslizar"], ["fundido", "Fundido"], ["corte", "Corte directo"]])}</label>
          <label>Palabras por subtítulo ${sel("palabras_subtitulo", [[0, "Auto"], [1, "1"], [2, "2"], [3, "3"], [4, "4"], [5, "5"], [7, "7"]])}</label>
          <label>Posición ${sel("posicion_subtitulo", [["abajo", "Abajo"], ["centro", "Centro"]])}</label>
          <label>Movimiento ${sel("zoom", [["suave", "Suave"], ["medio", "Medio"], ["fuerte", "Fuerte"]])}</label>
          <label>Ritmo (golpes de zoom) ${sel("corte_cada", [[0, "Sin golpes"], [1.5, "Cada 1.5 s"], [2, "Cada 2 s"], [3, "Cada 3 s"], [4, "Cada 4 s"], [6, "Cada 6 s"]])}</label>
          <label>Motion graphics ${sel("motion", [["nada", "Sin efectos"], ["poco", "Pocos"], ["normal", "Normal"], ["mucho", "Muchos (alto impacto)"]])}</label>
          ${chk("karaoke", "Subtítulos karaoke (se ilumina la palabra que se dice)")}
          ${chk("mayusculas_subtitulo", "Subtítulos en MAYÚSCULAS")}
          ${chk("barra_progreso", "Barra de progreso")}${chk("sonido_cambios", "Sonido en cada cambio de escena")}
        </div>
        ${subida("musica", e.archivos.musica)}${subida("whoosh", e.archivos.whoosh)}${subida("intro", e.archivos.intro)}${subida("outro", e.archivos.outro)}
        <p class="pista">Los colores de subtítulos y barra salen del estilo de tus miniaturas. Usa música sin copyright.</p>
      </section>
      <section class="tarjeta estilo-sec" style="--c:#06b6d4">
        <h4>📝 Blog · Rosa</h4>
        <p class="pista">Pega enlaces a 3–6 de tus mejores entradas (una por línea). Rosa aprende cómo escribes y lo mejora para Google.</p>
        <textarea id="blog-urls" rows="4" placeholder="https://tublog.com/una-entrada&#10;https://tublog.com/otra-entrada">${esc((e.blog_urls || []).join("\n"))}</textarea>
        <div class="acciones"><button class="btn btn-primario" data-estudiar="blog">📖 Que Rosa estudie mis entradas</button></div>
        <p class="pista">${e.seo_google ? "✅ Cada post usa lo que la gente pregunta en Google y las búsquedas relacionadas (Serper)." : "⬜ Con la clave de Serper, cada post usaría lo que la gente pregunta en Google."}</p>
        ${b ? `<div class="aprendido"><b>Tu estilo:</b> ${esc(b.resumen)}<br><small>Tono: ${esc(b.tono)} · ~${esc(b.longitud_palabras)} palabras · leyó ${esc(b.leidas)}</small>
          <details><summary>Estructura y mejoras SEO</summary><ol>${(b.estructura || []).map((x) => `<li>${esc(x)}</li>`).join("")}</ol>
          <b>Para posicionar mejor:</b><ul>${(b.mejoras_seo || []).map((x) => `<li>${esc(x)}</li>`).join("")}</ul></details></div>` : ""}
      </section>
      <section class="tarjeta estilo-sec" style="--c:#f97316">
        <h4>📤 YouTube · Carla</h4>
        <p>${e.youtube.conectado ? "✅ Tu canal está conectado." : e.youtube.secreto ? "⬜ Falta autorizar tu canal (ver la guía)." : "⬜ Aún no está conectado (ver la guía)."}
          Los videos se suben como <b>${esc({ private: "privados", unlisted: "ocultos", public: "públicos" }[e.youtube.privacidad] || e.youtube.privacidad)}</b>.</p>
        <p class="pista">Carla sube el video cuando le das <b>Publicar</b> en la revisión, con título, descripción, etiquetas, miniatura y el enlace al blog.</p>
      </section>`;
  }

  $("#estilo").addEventListener("change", async (ev) => {
    const el = ev.target;
    if (el.dataset.subir) {
      const archivos = [...el.files];
      el.closest(".tarjeta").classList.add("saliendo");
      for (const f of archivos) {
        try {
          const r = await fetch(`/api/estilo/subir?tipo=${el.dataset.subir}&nombre=${encodeURIComponent(f.name)}`,
                                { method: "POST", headers: { "Content-Type": "application/octet-stream" }, body: f });
          const j = await r.json().catch(() => ({}));
          if (!r.ok) alert(`${f.name}: ${j.error || "no se pudo subir"}`);
        } catch (err) { alert(`${f.name}: ${err.message}`); }
      }
      return pintarEstilo();
    }
    if (el.dataset.ajuste) {
      const numericos = ["opciones_miniatura", "palabras_subtitulo", "corte_cada"];
      const v = el.type === "checkbox" ? el.checked : numericos.includes(el.dataset.ajuste) ? Number(el.value) : el.value;
      try { await api("/api/estilo/ajustes", { [el.dataset.ajuste]: v }); } catch (err) { alert(err.message); }
    }
  });

  $("#estilo").addEventListener("click", async (ev) => {
    const b = ev.target.closest("button");
    if (!b) return;
    if (b.dataset.borrar) {
      if (!confirm("¿Quitar este archivo?")) return;
      await api("/api/estilo/borrar", { tipo: b.dataset.borrar, nombre: b.dataset.nombre || "" }).catch((e) => alert(e.message));
      return pintarEstilo();
    }
    if (b.dataset.estudiar) {
      const fuente = b.dataset.estudiar === "video" ? $("#ref-url").value : $("#blog-urls").value;
      const urls = fuente.split(/\s+/).filter((u) => u.startsWith("http"));
      if (b.dataset.estudiar === "video" && !urls.length && !estado_estilo?.archivos?.referencia) return alert("Pega el enlace del video o sube el archivo.");
      try {
        await api("/api/estilo/estudiar", { que: b.dataset.estudiar, urls });
        b.textContent = { miniaturas: "Dani está estudiando…", video: "Edu está viendo el video…" }[b.dataset.estudiar] || "Rosa está leyendo…";
        b.textContent += " (míralo en la oficina)";
        b.disabled = true;
        setTimeout(pintarEstilo, 45000);
      } catch (err) { alert(err.message); }
    }
  });

  // ---------- TikTok Shop (ala derecha): su oficina corre aparte y se consulta cada 2 s ----------
  let estadoTT = null, versionTT = -1;
  const ETAPAS_TT = [["ficha", "Toño investiga"], ["guion", "Sofi escribe"], ["tomas", "Diego arma tomas"],
                     ["video", "Cris edita"], ["portada", "Vale: portada"]];
  const ESTADO_TT = { trabajando: "En proceso", listo: "Listo para grabar", error: "Con problema", video_listo: "🎬 Video listo" };
  const FORMATO_TT = { problema_solucion: "Problema → solución", antes_despues: "Antes y después", resena: "Reseña",
                       unboxing: "Unboxing", tutorial: "Tutorial", objecion: "Objeción / FAQ", asmr: "ASMR" };
  const BLOQUE_TT = { puente: "Puente", problema: "Problema", solucion: "Solución / demo", beneficios: "Beneficios", cta: "Carrito naranja" };
  const leerVistos = () => { try { return JSON.parse(localStorage.getItem("shop_vistos") || "[]"); } catch { return []; } };

  async function apiTT(ruta, datos) {
    const r = await fetch(`/tiktok${ruta}`, { method: datos ? "POST" : "GET", headers: { "Content-Type": "application/json" },
                                              body: datos ? JSON.stringify(datos) : undefined });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.error || "Algo salió mal");
    return j;
  }
  async function consultarTT() {
    try {
      const n = await apiTT("/api/estado");
      if (n.version !== versionTT || !estadoTT) {
        versionTT = n.version; estadoTT = n; window.Oficina.actualizarTT(n); pintarShop();
        const abierto = guionAbierto && n.productos.find((x) => x.id === guionAbierto.id);
        if (abierto && !Object.keys(subiendo).length && !$("#modal").hidden && $("#modal-cuerpo .guion-shop")
            && (abierto.estado !== guionAbierto.estado || JSON.stringify(abierto.etapas) !== JSON.stringify(guionAbierto.etapas))) refrescarGuionTT();
      }
    } catch {
      if (estadoTT !== null || versionTT === -1) { estadoTT = null; versionTT = -2; window.Oficina.actualizarTT(null); pintarShop(); }
    }
  }

  function pintarShop() {
    $("#shop-apagada").hidden = !!estadoTT;
    $("#form-producto").hidden = !estadoTT;
    if (!estadoTT) { $("#shop-lista").innerHTML = ""; $("#shop-gasto").textContent = ""; $("#cuenta-shop").hidden = true; return; }
    const g = estadoTT.gasto;
    const disco = estadoTT.disco || {};
    $("#shop-gasto").innerHTML = `💰 Oficina TikTok hoy <b>${dinero(g.hoy)}</b>${g.tope ? ` / tope ${dinero(g.tope)}` : ""} · mes ${dinero(g.mes)}`
      + (disco.libre_gb != null ? ` · <span class="${disco.libre_gb < 3 ? "poco-disco" : ""}" title="Clips subidos: ${disco.clips_gb} GB">💾 ${disco.libre_gb} GB libres</span>` : "")
      + (estadoTT.demo ? ` · <span class="chip chip-demo">DEMO</span>` : "")
      + (disco.libre_gb != null && disco.libre_gb < 3 ? `<br><b class="poco-disco">⚠️ Queda poco espacio en el servidor: borra clips de videos terminados o usa la carpeta de tu compu.</b>` : "");
    const vistos = new Set(leerVistos());
    const nuevos = estadoTT.productos.filter((p) => p.estado === "listo" && !vistos.has(p.id)).length;
    $("#cuenta-shop").hidden = !nuevos;
    $("#cuenta-shop").textContent = nuevos;
    if (!estadoTT.productos.length) { $("#shop-lista").innerHTML = `<p class="vacio">Todavía no hay productos. Cuando te llegue uno, ponlo arriba.</p>`; return; }
    $("#shop-lista").innerHTML = estadoTT.productos.map((p) => `<article class="tarjeta ${p.estado === "error" ? "tarjeta-error" : ""}">
        <div class="cabeza"><h4>${esc(p.nombre)}</h4><span class="chip ${["listo", "video_listo"].includes(p.estado) ? "chip-estado-publicado" : p.estado === "error" ? "chip-estado-error" : ""}">${esc(ESTADO_TT[p.estado] || p.estado)}</span></div>
        <ol class="pasos-shop">${ETAPAS_TT.filter(([e]) => !["video", "portada"].includes(e) || p.etapas?.[e]).map(([e, txt]) => `<li class="${esc(p.etapas?.[e] || "")}">${esc(txt)}</li>`).join("")}</ol>
        ${p.clips && !p.videos ? `<p class="pista">📤 ${p.clips} clip(s) subido(s)</p>` : ""}
        ${p.guion_id ? `<p class="pista">${esc(FORMATO_TT[p.formato] || p.formato || "")} · 🪝 ${p.gancho && p.gancho !== "todos" ? `Gancho ${esc(p.gancho)}` : "Los 3 ganchos"} · <code>${esc(p.guion_id)}</code></p>` : ""}
        ${p.error ? `<p class="error">${esc(p.error)}</p>` : ""}
        ${p.costo ? `<div class="costo">💰 ${dinero(p.costo)}</div>` : ""}
        <div class="fila">
          ${p.etapas?.guion === "hecha" ? `<button class="btn btn-primario" data-ver-tt="${esc(p.id)}">${p.videos ? "🎬 Ver videos" : p.estado === "listo" ? "Guion, tomas y subir clips" : "Ver guion y tomas"}</button>` : ""}
          ${p.estado !== "trabajando" ? `<button class="btn btn-mini" data-rehacer-tt="${esc(p.id)}">${p.estado === "error" ? "Reintentar" : "Otro guion"}</button>
            <button class="btn btn-mini" data-borrar-tt="${esc(p.id)}">Borrar</button>` : ""}
        </div>
      </article>`).join("");
  }

  $("#form-producto").addEventListener("submit", async (e) => {
    e.preventDefault();
    const boton = e.target.querySelector("button[type=submit]");
    boton.disabled = true;
    try {
      await apiTT("/api/producto", { nombre: $("#p-nombre").value, enlace: $("#p-enlace").value, precio: $("#p-precio").value,
                                     comision: $("#p-comision").value, notas: $("#p-notas").value,
                                     de_marca: $("#p-marca").checked, duracion: $("#p-duracion").value });
      ["#p-nombre", "#p-enlace", "#p-precio", "#p-comision", "#p-notas"].forEach((s) => ($(s).value = ""));
      window.Oficina.verAla("tiktok");
      consultarTT();
    } catch (err) { alert(err.message); }
    boton.disabled = false;
  });

  $("#shop-lista").addEventListener("click", async (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    try {
      if (b.dataset.verTt) return abrirGuionTT(b.dataset.verTt);
      if (b.dataset.rehacerTt) { b.disabled = true; await apiTT(`/api/producto/${encodeURIComponent(b.dataset.rehacerTt)}`, { accion: "rehacer" }); }
      if (b.dataset.borrarTt && confirm("¿Borrar este producto y su guion?")) await apiTT(`/api/producto/${encodeURIComponent(b.dataset.borrarTt)}`, { accion: "borrar" });
      consultarTT();
    } catch (err) { alert(err.message); b.disabled = false; }
  });

  // Guion de un producto. Se elige con cuál gancho grabar (o los 3) y la lista de tomas de Diego se ajusta.
  let guionAbierto = null;
  const letraDeToma = (x) => (/gancho\s*([abc])\b/i.exec(x.para || "")?.[1] || "").toUpperCase();

  async function abrirGuionTT(id) {
    guionAbierto = await apiTT(`/api/producto/${encodeURIComponent(id)}`);
    try { const v = new Set(leerVistos()); v.add(id); localStorage.setItem("shop_vistos", JSON.stringify([...v].slice(-200))); } catch { /* sin almacenamiento */ }
    pintarGuionTT();
    $("#modal").hidden = false;
    $("#modal-cerrar").focus();
    pintarShop();
  }

  const ruta = (pid, archivo, v) => `/tiktok/salida/${encodeURIComponent(pid)}/${encodeURIComponent(archivo)}${v ? `?v=${v}` : ""}`;
  // Casilla para subir el clip de una toma (o el video completo)
  function slotSubida(clave, c) {
    if (subiendo[clave] != null) return `<span class="subida"><span class="barra-subida"><b style="width:${subiendo[clave]}%"></b></span> ${subiendo[clave]} %</span>`;
    if (c) return `<span class="subida ok" title="${esc(c.nombre || "")}">✔ ${esc(c.segundos)} s · ${esc(c.mb)} MB
      <button type="button" class="btn btn-mini" data-quitar-clip="${esc(clave)}" aria-label="Quitar clip">✕</button></span>`;
    return `<label class="btn btn-mini subir">📤 Subir<input type="file" accept="video/*" hidden data-subir-clip="${esc(clave)}"></label>`;
  }

  function seccionEdicion(p, clips, letras) {
    const nTomas = Object.keys(clips.tomas || {}).length;
    const nLocal = Object.values(p.local?.asignacion || {}).filter(Boolean).length;
    const trabajando = p.estado === "trabajando";
    const modo = p.modo_edicion || (nLocal ? "local" : nTomas ? "tomas" : clips.completo ? "completo" : "tomas");
    const videos = p.videos || [];
    return `<div class="edicion">
      <h3>🖥️ Tus clips en tu compu <small class="pista">(no se suben: Cris edita ahí mismo)</small></h3>
      <div id="locales-tt"><p class="pista">Buscando tus compus…</p></div>
      <h3>📤 ¿Grabaste todo seguido? Sube el video completo</h3>
      <p class="pista">Cris le quita los silencios y las tomas repetidas (se queda con la última). Habla mientras haces la demo: lo que quede callado mucho rato se corta.</p>
      <p>${slotSubida("completo", clips.completo)}</p>
      <h3>✂️ Edición de Cris</h3>
      ${nTomas || clips.completo || nLocal ? `<div class="fila modos">
          <label><input type="radio" name="modo-ed" value="local" ${modo === "local" ? "checked" : ""} ${nLocal ? "" : "disabled"}> 🖥️ Clips en mi compu (${nLocal})</label>
          <label><input type="radio" name="modo-ed" value="tomas" ${modo === "tomas" ? "checked" : ""} ${nTomas ? "" : "disabled"}> Mis clips por toma (${nTomas})</label>
          <label><input type="radio" name="modo-ed" value="completo" ${modo === "completo" ? "checked" : ""} ${clips.completo ? "" : "disabled"}> Mi video completo</label>
        </div>
        <p class="pista">Va a sacar ${letras.length > 1 ? "un video por cada gancho que hayas grabado (A, B y C)" : `el video con el gancho ${esc(letras[0])}`}: vertical, con tus textos, subtítulos karaoke de tu voz y cortes rápidos. Sin música: ponle un sonido en tendencia desde TikTok.</p>
        <div class="fila botones-editar">
          <button type="button" class="btn btn-primario" data-editar ${trabajando || Object.keys(subiendo).length ? "disabled" : ""}>${trabajando ? (p.esperar_compu ? "Esperando a tu compu…" : "Cris está editando…") : videos.length ? "✂️ Volver a editar" : "✂️ Que Cris lo edite ya"}</button>
          ${hayCompus() && !trabajando ? `<button type="button" class="btn" data-editar-esperar title="Tu compu edita más rápido y con mejores subtítulos">🖥️ Esperar a mi compu</button>` : ""}
        </div>
        <p class="pista">${modo === "local" ? "Lo edita la compu donde están tus clips."
          : `«Ya»: lo edita tu compu si está prendida; si no, el servidor. ${hayCompus() ? "«Esperar a mi compu»: queda en fila y se edita cuando la prendas." : ""}`}</p>`
      : `<p class="vacio">Pasa tus clips a la carpeta de tu compu (arriba) o súbelos en la lista de tomas (📤 Subir), y aquí le das a Cris.</p>`}
      ${nTomas || clips.completo ? `<p class="pista clips-servidor">💾 Tus clips subidos ocupan espacio en el servidor${p.video_t && estadoTT?.disco?.dias
          ? `: se borran solos el ${new Date((p.video_t + estadoTT.disco.dias * 86400) * 1000).toLocaleDateString("es-MX", { day: "numeric", month: "short" })}` : " hasta unos días después de tener el video"}.
          ${videos.length && !trabajando ? `<button type="button" class="btn btn-mini" data-borrar-clips>🧹 Borrar mis clips del servidor ya</button>` : ""}</p>`
        : p.clips_borrados ? `<p class="pista">🧹 Los clips subidos ya se borraron del servidor (el video se queda). Para volver a editar, súbelos otra vez.</p>` : ""}
      ${videos.length ? `<h3>🎬 Tus videos</h3><div class="videos-tt">${videos.map((v) => `<figure class="video-tt">
          <video controls playsinline preload="metadata" poster="${v.portada ? ruta(p.id, v.portada, v.v) : ""}" src="${ruta(p.id, v.video, v.v)}"></video>
          <figcaption><span><b>${v.gancho ? `Gancho ${esc(v.gancho)}` : "Video"}</b> · ${esc(v.segundos)} s</span> <span class="id">${esc(p.guion.id)}${v.gancho ? `-${esc(v.gancho)}` : ""}</span>
            <span class="fila"><a class="btn btn-mini btn-primario" href="${ruta(p.id, v.video, v.v)}" download="${esc(p.guion.id)}${v.gancho ? `-${esc(v.gancho)}` : ""}.mp4">⬇️ Video</a>
            ${v.portada ? `<a class="btn btn-mini" href="${ruta(p.id, v.portada, v.v)}" download="${esc(p.guion.id)}${v.gancho ? `-${esc(v.gancho)}` : ""}_portada.jpg">⬇️ Portada</a>` : ""}</span>
          </figcaption></figure>`).join("")}</div>
        <p class="pista">Bájalo al cel, súbelo a TikTok, ponle el caption, fija el comentario${p.de_marca ? " y activa \"Contenido de marca\"" : ""}. Para la portada: en TikTok, "Editar portada" → sube la imagen.</p>` : ""}
    </div>`;
  }

  // Subir un clip con barra de avance (se puede seguir usando la oficina mientras sube)
  const subiendo = {};
  function subirClip(pid, clave, archivo) {
    subiendo[clave] = 0;
    pintarGuionTT();
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `/tiktok/api/subir?producto=${encodeURIComponent(pid)}&toma=${encodeURIComponent(clave)}&nombre=${encodeURIComponent(archivo.name)}`);
    xhr.setRequestHeader("Content-Type", "application/octet-stream");
    let ultimo = 0;
    xhr.upload.onprogress = (e) => {
      if (!e.lengthComputable) return;
      subiendo[clave] = Math.min(99, Math.round(e.loaded / e.total * 100));
      if (subiendo[clave] - ultimo >= 2) { ultimo = subiendo[clave]; pintarGuionTT(); }
    };
    xhr.onloadend = async () => {
      delete subiendo[clave];
      let j = {};
      try { j = JSON.parse(xhr.responseText); } catch { /* sin respuesta */ }
      if (xhr.status !== 200) alert(j.error || "No se pudo subir el clip. Revisa tu conexión y vuelve a intentar.");
      await refrescarGuionTT();
    };
    xhr.send(archivo);
  }
  async function refrescarGuionTT() {
    if (!guionAbierto) return;
    try { guionAbierto = await apiTT(`/api/producto/${encodeURIComponent(guionAbierto.id)}`); } catch { /* sigue con lo que hay */ }
    if (!$("#modal").hidden && $("#modal-cuerpo .guion-shop")) pintarGuionTT();
    consultarTT();
  }

  function pintarGuionTT() {
    const p = guionAbierto, g = p.guion, f = p.ficha || {}, t = p.tomas;
    const elegido = p.gancho || "todos";
    const letras = elegido === "todos" ? ["A", "B", "C"] : [elegido];
    const gancho = g.ganchos.find((x) => x.letra === elegido);
    const caption = `${g.caption}\n\n${(g.hashtags || []).join(" ")}`;
    const tomas = (t?.tomas || []).filter((x) => !letraDeToma(x) || letras.includes(letraDeToma(x)));
    const segundos = Math.round(tomas.reduce((s, x) => s + (Number(x.segundos) || 0), 0));
    const clips = p.clips || {};
    const fila = (c, etiqueta) => `<tr><td>${esc(c.tiempo)}<br><small>${esc(etiqueta)}</small></td><td>${esc(c.toma)}</td>
      <td class="texto-pantalla">${esc(c.texto_pantalla)}</td><td>${esc(c.voz || "(sin voz)")}</td></tr>`;
    const caja = $(".modal-caja"), scroll = caja.scrollTop;
    $("#modal-cuerpo").innerHTML = `<div class="guion-shop">
      <h2 id="modal-titulo">${esc(p.nombre)}</h2>
      <p class="id">ID: ${esc(g.id)}${gancho ? `-${esc(gancho.letra)}` : ""} · ${esc(FORMATO_TT[g.formato] || g.formato)} · ${g.duracion === "corta" ? "15–25 s" : "35–50 s"}</p>
      <p><b>Ángulo:</b> ${esc(g.angulo)}</p>
      ${g.supuestos ? `<p class="pista">Supuse: ${esc(g.supuestos)}</p>` : ""}
      ${p.de_marca ? `<p class="marca-aviso">🏷️ Al subirlo, actívale <b>"Contenido de marca"</b> en TikTok (te lo mandó una marca).</p>` : ""}
      <h3>🪝 Elige tu gancho</h3>
      <p class="pista">Pícale a uno para ver el guion completo con ese gancho y solo sus tomas, o graba los 3 para probar cuál vende más.</p>
      <div class="ganchos">${g.ganchos.map((x) => `<button type="button" class="gancho ${letras.includes(x.letra) ? "elegido" : ""}" data-gancho="${esc(x.letra)}" aria-pressed="${elegido === x.letra}">
        <b>${esc(x.letra)}</b> · ${esc(x.tipo)} ${elegido === x.letra ? `<span class="chip chip-estado-revision">Elegido</span>` : ""}
        <span class="id">${esc(g.id)}-${esc(x.letra)}</span>
        <p>🎥 ${esc(x.toma)}</p><p class="texto-pantalla">🅣 ${esc(x.texto_pantalla)}</p><p>🗣️ ${esc(x.voz || "(sin voz)")}</p></button>`).join("")}</div>
      <button type="button" class="btn btn-mini tres ${elegido === "todos" ? "btn-primario" : ""}" data-gancho="todos">🅰 🅱 🅲 Grabar los 3 (prueba cuál vende más)</button>
      <h3>${gancho ? `📜 Guion completo con el gancho ${esc(gancho.letra)}` : "📜 Cuerpo (el mismo para los 3 ganchos)"}</h3>
      <table class="tabla-shop"><thead><tr><th>Tiempo</th><th>Toma</th><th>Texto en pantalla</th><th>Voz</th></tr></thead>
        <tbody>${gancho ? fila({ tiempo: "0–3 s", ...gancho }, `Gancho ${gancho.letra}`) : ""}
        ${g.cuerpo.map((c) => fila(c, BLOQUE_TT[c.bloque] || c.bloque)).join("")}</tbody></table>
      <h3>Caption <button class="btn btn-mini" data-copiar="caption">Copiar</button></h3>
      <div class="copiable" id="copiar-caption">${esc(caption)}</div>
      <h3>Comentario fijado <button class="btn btn-mini" data-copiar="comentario">Copiar</button></h3>
      <div class="copiable" id="copiar-comentario">${esc(g.comentario_fijado)}</div>
      ${t ? `<h3>🎥 Tomas de Diego ${gancho ? `para el gancho ${esc(gancho.letra)}` : "para los 3 ganchos"}</h3>
        <p class="pista">${tomas.length} tomas · unos ${segundos} s de grabación · en orden de grabación (por lugar)</p>
        ${t.material?.length ? `<p><b>Ten a la mano:</b> ${t.material.map(esc).join(", ")}</p>` : ""}
        <ul class="tomas-lista">${tomas.map((x, k) => { const c = clips.tomas?.[x.n]; return `<li><input type="checkbox" aria-label="Toma ${k + 1} grabada" ${c ? "checked" : ""}><div>
          <b>${k + 1}. ${esc(x.que_grabar)}</b> <small>· ${esc(x.lugar)} · ${esc(x.encuadre)} · ${esc(x.segundos)} s · para ${esc(x.para)}</small>
          ${x.tip ? `<br><small>💡 ${esc(x.tip)}</small>` : ""}</div>
          ${slotSubida(String(x.n), c)}</li>`; }).join("")}</ul>
        ${t.consejos?.length ? `<ul class="fuentes">${t.consejos.map((c) => `<li>${esc(c)}</li>`).join("")}</ul>` : ""}` : ""}
      ${t ? seccionEdicion(p, clips, letras) : ""}
      <h3>🔎 Ficha de Toño</h3>
      <p>${esc(f.resumen || "")}</p>
      <p><b>Problema:</b> ${esc(f.problema || "—")} · <b>Público:</b> ${esc(f.publico || "—")} · <b>Duda principal:</b> ${esc(f.objecion || "—")}${f.precio ? ` · <b>Precio:</b> ${esc(f.precio)}` : ""}</p>
      ${f.cuidado ? `<p class="marca-aviso">⚠️ No prometer: ${esc(f.cuidado)}</p>` : ""}
      ${(f.datos || []).length || (f.opiniones || []).length ? `<ul class="fuentes">
        ${(f.datos || []).map((d) => `<li>${esc(d.dato)} — <a href="${esc(d.url)}" target="_blank" rel="noopener">fuente</a></li>`).join("")}
        ${(f.opiniones || []).map((o) => `<li>“${esc(o.texto)}” — <a href="${esc(o.url)}" target="_blank" rel="noopener">fuente</a></li>`).join("")}</ul>`
        : `<p class="pista">Sin datos de internet${f.fuentes === 0 ? " (no hubo búsqueda)" : ""}: el guion solo usa lo que tú le dijiste.</p>`}
      ${g.mejoraria ? `<p class="pista">📌 Para la siguiente versión ayudaría saber: ${esc(g.mejoraria)}</p>` : ""}
      ${p.costo ? `<p class="pista">💰 Este guion costó ${dinero(p.costo)}</p>` : ""}
    </div>`;
    caja.scrollTop = scroll;
    pintarLocales();
  }

  const hayCompus = () => (estadoSala?.compus || []).length > 0;
  // Clips que están en la carpeta "Sala de edicion" de tus compus (solo se ven sus miniaturas)
  let localesTT = null, localesDe = null;
  const carpetaNombre = (p) => `${p.nombre.replace(/[<>:"/\\|?*]+/g, " ").trim().replace(/[ .]+$/, "").slice(0, 60) || "producto"} [${p.id.slice(-4)}]`;
  async function cargarLocales() {
    if (!guionAbierto) return;
    const pid = guionAbierto.id;
    try { localesTT = await (await fetch(`/sala/api/locales/${encodeURIComponent(pid)}`)).json(); localesDe = pid; }
    catch { localesTT = { compus: [] }; localesDe = pid; }
    pintarLocales();
  }
  function pintarLocales() {
    const cont = $("#locales-tt");
    if (!cont || !guionAbierto) return;
    if (localesDe !== guionAbierto.id) { localesDe = guionAbierto.id; localesTT = null; cargarLocales(); return; }
    if (!localesTT) return;
    if (cont.contains(document.activeElement) && document.activeElement.tagName === "SELECT") return; // no estorbar mientras eliges
    const p = guionAbierto, asig = p.local?.asignacion || {};
    const compus = localesTT.compus || [];
    if (!compus.length) {
      cont.innerHTML = `<p class="pista">Instala la Sala de edición en tu compu (pestaña <b>Sala</b>) y podrás editar sin subir nada al servidor.</p>`;
      return;
    }
    const tomas = p.tomas?.tomas || [];
    const opciones = (sel) => `<option value="">— no usar —</option>`
      + tomas.map((t, k) => `<option value="${t.n}" ${sel === String(t.n) ? "selected" : ""}>Toma ${k + 1}: ${esc(t.que_grabar.slice(0, 38))} (${esc(t.para)})</option>`).join("")
      + `<option value="completo" ${sel === "completo" ? "selected" : ""}>🎞️ Video completo</option>`;
    cont.innerHTML = compus.map((c) => {
      const sep = (c.ruta || "").includes("\\") ? "\\" : "/";
      const ruta = c.ruta ? `${c.ruta}${sep}${carpetaNombre(p)}` : carpetaNombre(p);
      const mia = !p.local?.compu || p.local.compu === c.id;
      return `<div class="compu-clips ${c.viva ? "" : "apagada"}">
        <div class="compu-clips-cabeza"><b>🖥️ ${esc(c.nombre)}</b> <span class="chip ${c.viva ? "chip-estado-publicado" : ""}">${c.viva ? "Prendida" : "Apagada"}</span>
          <span class="ruta" title="Pasa aquí tus clips">📁 ${esc(ruta)}</span>
          <button type="button" class="btn btn-mini" data-copiar-ruta="${esc(ruta)}">Copiar ruta</button></div>
        ${c.clips.length ? `<div class="clips-grid">${c.clips.map((x) => `<figure class="clip-local ${mia && asig[x.nombre] ? "usado" : ""}">
            <img loading="lazy" src="/sala/api/miniatura/${encodeURIComponent(c.id)}/${encodeURIComponent(p.id)}/${encodeURIComponent(x.nombre)}" alt="">
            <figcaption title="${esc(x.nombre)}"><span class="nombre-clip">${esc(x.nombre)}</span>
              <small>${esc(x.segundos)} s · ${esc(x.mb)} MB${x.tiene_audio ? "" : " · sin audio"}</small>
              <select data-asignar="${esc(x.nombre)}" data-compu="${esc(c.id)}" aria-label="¿Qué es este clip?">${opciones(mia ? asig[x.nombre] || "" : "")}</select></figcaption>
          </figure>`).join("")}</div>
          <button type="button" class="btn btn-mini" data-auto-asignar="${esc(c.id)}">🪄 Asignar en orden de grabación</button>`
        : `<p class="pista">${c.carpeta ? "La carpeta está vacía: pasa ahí tus clips del cel." : c.viva ? "Tu compu está creando la carpeta…" : "Prende tu compu para ver la carpeta."}</p>`}
      </div>`;
    }).join("");
  }
  async function guardarLocales(compu, asignacion) {
    guionAbierto.local = { compu, asignacion };
    try { await apiTT(`/api/local/${encodeURIComponent(guionAbierto.id)}`, { compu, asignacion }); }
    catch (err) { alert(err.message); }
    refrescarGuionTT();
  }
  $("#modal-cuerpo").addEventListener("change", (e) => {
    const sel = e.target.closest("[data-asignar]");
    if (sel && guionAbierto) {
      const compu = sel.dataset.compu;
      const base = guionAbierto.local?.compu === compu ? { ...(guionAbierto.local.asignacion || {}) } : {};
      if (sel.value === "completo") for (const k of Object.keys(base)) if (base[k] === "completo") base[k] = "";
      base[sel.dataset.asignar] = sel.value;
      for (const k of Object.keys(base)) if (!base[k]) delete base[k];
      sel.blur();
      return guardarLocales(compu, base);
    }
    const input = e.target.closest("[data-subir-clip]");
    if (input?.files?.[0] && guionAbierto) subirClip(guionAbierto.id, input.dataset.subirClip, input.files[0]);
  });
  $("#modal-cuerpo").addEventListener("click", (e) => {
    const auto = e.target.closest("[data-auto-asignar]");
    if (auto && guionAbierto && localesTT) { // el cel nombra los clips por hora: en orden = en el orden de Diego
      const c = localesTT.compus.find((x) => x.id === auto.dataset.autoAsignar);
      const elegido = guionAbierto.gancho || "todos", letras = elegido === "todos" ? ["A", "B", "C"] : [elegido];
      const tomas = (guionAbierto.tomas?.tomas || []).filter((x) => !letraDeToma(x) || letras.includes(letraDeToma(x)));
      const clips = [...c.clips].sort((a, b) => a.nombre.localeCompare(b.nombre, undefined, { numeric: true }));
      if (clips.length !== tomas.length && !confirm(`Tienes ${clips.length} clips y ${tomas.length} tomas. ¿Los asigno en orden de todos modos?`)) return;
      const asignacion = {};
      clips.slice(0, tomas.length).forEach((x, k) => { asignacion[x.nombre] = String(tomas[k].n); });
      return guardarLocales(c.id, asignacion);
    }
    const copiarRuta = e.target.closest("[data-copiar-ruta]");
    if (copiarRuta) {
      navigator.clipboard?.writeText(copiarRuta.dataset.copiarRuta).then(() => { copiarRuta.textContent = "¡Copiada!"; setTimeout(() => (copiarRuta.textContent = "Copiar ruta"), 1500); });
      return;
    }
    const quitar = e.target.closest("[data-quitar-clip]");
    if (quitar && guionAbierto) {
      if (!confirm("¿Quitar este clip?")) return;
      apiTT(`/api/producto/${encodeURIComponent(guionAbierto.id)}`, { accion: "quitar_clip", desde: quitar.dataset.quitarClip })
        .then(refrescarGuionTT).catch((err) => alert(err.message));
      return;
    }
    const borrarClips = e.target.closest("[data-borrar-clips]");
    if (borrarClips && guionAbierto) {
      if (!confirm("¿Borrar del servidor los clips que subiste? El video terminado se queda. Para volver a editar habría que subirlos otra vez.")) return;
      apiTT(`/api/producto/${encodeURIComponent(guionAbierto.id)}`, { accion: "borrar_clips" })
        .then((r) => { if (r.mb) alert(`Listo: se liberaron ${Math.round(r.mb)} MB.`); return refrescarGuionTT(); }).catch((err) => alert(err.message));
      return;
    }
    const editar = e.target.closest("[data-editar], [data-editar-esperar]");
    if (editar && guionAbierto) {
      editar.disabled = true;
      const modo = $("#modal-cuerpo input[name=modo-ed]:checked")?.value || "tomas";
      apiTT(`/api/producto/${encodeURIComponent(guionAbierto.id)}`, { accion: editar.dataset.editarEsperar !== undefined ? "editar_esperar" : "editar", desde: modo })
        .then(() => { window.Oficina.verAla("tiktok"); return refrescarGuionTT(); })
        .catch((err) => { alert(err.message); editar.disabled = false; });
      return;
    }
    const gb = e.target.closest("[data-gancho]");
    if (gb && guionAbierto) {
      guionAbierto.gancho = gb.dataset.gancho;
      pintarGuionTT();
      apiTT(`/api/producto/${encodeURIComponent(guionAbierto.id)}`, { accion: "gancho", desde: gb.dataset.gancho })
        .then(consultarTT).catch((err) => alert(err.message));
      return;
    }
    const b = e.target.closest("[data-copiar]");
    if (!b) return;
    const texto = $(`#copiar-${b.dataset.copiar}`).textContent;
    navigator.clipboard?.writeText(texto).then(() => { b.textContent = "¡Copiado!"; setTimeout(() => (b.textContent = "Copiar"), 1500); })
      .catch(() => alert("No se pudo copiar; selecciónalo y cópialo a mano."));
  });

  // ---------- Sala de edición (tercera oficina): tus compus editan en lugar del servidor ----------
  let estadoSala = null, versionSala = -1, codigoSala = null;
  async function salaApi(ruta, datos) {
    const r = await fetch(`/sala${ruta}`, { method: datos ? "POST" : "GET", headers: { "Content-Type": "application/json" },
                                            body: datos ? JSON.stringify(datos) : undefined });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.error || "Algo salió mal");
    return j;
  }

  // Ventana de un proyecto: chat con su editor, versiones y clips
  let proyectoSala = null, versionVista = null;
  const SUGERENCIAS = ["Hazlo vertical con subtítulos", "Horizontal para YouTube", "Que dure 30 segundos", "Subtítulos más grandes",
                       "Quita los silencios", "Búscame música alegre", "Quita el ruido de fondo", "Estabiliza las tomas movidas", "Otra vez"];
  async function abrirProyectoSala(pid) {
    try { proyectoSala = await salaApi(`/api/proyecto/${encodeURIComponent(pid)}`); } catch (err) { return alert(err.message); }
    versionVista = null;
    $("#modal-cuerpo").innerHTML = `<div class="proyecto-ventana">
      <div id="pv-cabeza"></div>
      <div class="pv-cuerpo">
        <div class="pv-izq"><div id="pv-video"></div><div id="pv-clips"></div></div>
        <div class="pv-der">
          <h3>💬 Chat con <span id="pv-editor"></span></h3>
          <ol id="pv-chat" class="chat-sala"></ol>
          <div class="sugerencias">${SUGERENCIAS.map((x) => `<button type="button" class="btn btn-mini" data-sugerencia="${esc(x)}">${esc(x)}</button>`).join("")}</div>
          <form id="pv-form" class="chat-escribir">
            <textarea id="pv-texto" rows="2" maxlength="1500" placeholder="Pídele el video o una corrección: «quita el clip 3», «subtítulos amarillos», «más corto»…"></textarea>
            <button class="btn btn-primario" type="submit">Enviar</button>
          </form>
        </div>
      </div></div>`;
    $("#modal").hidden = false;
    pintarProyectoSala();
    $("#pv-texto").focus();
  }
  function pintarProyectoSala() {
    const p = proyectoSala;
    if (!p || !$("#pv-cabeza")) return;
    const av = Math.round((p.avance || 0) * 100);
    $("#pv-cabeza").innerHTML = `<h2 id="modal-titulo">${esc(p.nombre)}</h2>
      <p class="pista">${p.compu ? `🖥️ Clips en ${esc(nombreEditor("sala_" + p.compu))}` : "☁️ Clips en el servidor"} · encargado: <b>${esc(p.editor)}</b>
        ${p.formato ? ` · ${p.formato === "vertical" ? "▯ vertical" : "▭ horizontal"}` : ""} · ${esc(ESTADO_PROYECTO[p.estado] || p.estado)}
        <button type="button" class="btn btn-mini" data-borrar-proyecto>Borrar proyecto</button></p>
      ${p.estado === "editando" ? `<div class="linea-tiempo grande"><b style="width:${av}%"></b></div><p class="pista">✂️ ${esc(p.paso || "Editando")} · ${av} %</p>` : ""}
      ${p.error ? `<p class="error">${esc(p.error)}</p>` : ""}
      ${p.error_carpeta ? `<p class="error">📁 ${esc(p.error_carpeta)}</p>` : ""}
      ${(p.creditos || []).length ? `<details class="creditos"><summary>📝 Créditos de música para la descripción</summary>
        <div class="copiable">${p.creditos.map(esc).join("<br>")}</div></details>` : ""}`;
    $("#pv-editor").textContent = p.editor;
    const vs = p.versiones || [], v = vs.find((x) => x.n === versionVista) || vs[vs.length - 1];
    const ruta = (f) => `/sala/salida/${encodeURIComponent(p.id)}/${encodeURIComponent(f)}`;
    const videoActual = $("#pv-video video");
    if (!v) $("#pv-video").innerHTML = `<div class="pv-sin-video">🎬<br>Aquí aparece cada versión que te mande ${esc(p.editor)}.</div>`;
    else if (!videoActual || videoActual.dataset.v !== String(v.n)) {
      $("#pv-video").innerHTML = `<video controls playsinline preload="metadata" data-v="${v.n}" class="${p.formato === "horizontal" ? "horizontal" : ""}"
          ${v.cuadro ? `poster="${ruta(v.cuadro)}"` : ""} src="${ruta(v.video)}"></video>
        <div class="fila versiones">${vs.map((x) => `<button type="button" class="btn btn-mini ${x.n === v.n ? "btn-primario" : ""}" data-version="${x.n}">v${x.n}</button>`).join("")}
          <a class="btn btn-mini" href="${ruta(v.video)}" download="${esc(p.nombre)} v${v.n}.mp4">⬇️ Bajar v${v.n}</a> <small>${esc(v.segundos)} s</small></div>`;
    }
    const sep = (estadoSala?.locales?.[p.compu]?.ruta || "").includes("\\") ? "\\" : "/";
    const rutaCarpeta = p.ruta || (p.compu ? `${estadoSala?.locales?.[p.compu]?.ruta || "Videos/Sala de edicion"}${sep}${p.carpeta}` : "");
    const htmlClips = `<h3>🎞️ Clips (${p.clips.length})</h3>
      ${p.compu ? `<p class="pista ruta-proy">📁 ${esc(rutaCarpeta)} <button type="button" class="btn btn-mini" data-copiar-ruta-proy="${esc(rutaCarpeta)}">Copiar ruta</button></p>` : ""}
      <div class="clips-grid">${p.clips.map((x, k) => `<figure class="clip-local">
          ${x.donde === "compu" ? `<img loading="lazy" alt="" src="/sala/api/miniatura/${encodeURIComponent(p.compu)}/${encodeURIComponent(p.clave)}/${encodeURIComponent(x.nombre)}">` : `<div class="sin-mini">☁️</div>`}
          <figcaption><span class="nombre-clip" title="${esc(x.nombre)}">${k + 1}. ${esc(x.nombre)}</span><small>${x.segundos ? `${esc(x.segundos)} s · ` : ""}${esc(x.mb)} MB</small></figcaption>
        </figure>`).join("")}</div>
      <label class="btn btn-mini subir">📤 Subir clips<input type="file" accept="video/*" multiple hidden data-subir-sala></label>
      <label class="btn btn-mini subir">📤 Subir una carpeta<input type="file" webkitdirectory multiple hidden data-subir-sala></label>
      <span id="pv-subiendo" class="pista"></span>
      ${(p.musica || []).length ? `<p class="pista">🎵 Música disponible: ${p.musica.map(esc).join(", ")}</p>` : `<p class="pista">🎵 Para música, pon tus canciones en la carpeta <b>Musica</b> de la sala en tu compu.</p>`}`;
    if ($("#pv-clips").dataset.html !== htmlClips) { $("#pv-clips").innerHTML = htmlClips; $("#pv-clips").dataset.html = htmlClips; }
    const log = $("#pv-chat"), abajo = log.scrollHeight - log.scrollTop - log.clientHeight < 40;
    log.innerHTML = (p.mensajes || []).map(lineaChat).join("");
    if (abajo) log.scrollTop = log.scrollHeight;
  }
  setInterval(async () => {
    if (!proyectoSala || $("#modal").hidden || !$("#pv-cabeza")) return;
    try { proyectoSala = await salaApi(`/api/proyecto/${encodeURIComponent(proyectoSala.id)}`); pintarProyectoSala(); } catch { /* sigue */ }
  }, 2500);
  $("#modal-cuerpo").addEventListener("submit", async (e) => {
    if (e.target.id !== "pv-form") return;
    e.preventDefault();
    const t = $("#pv-texto"), texto = t.value.trim();
    if (!texto || !proyectoSala) return;
    t.value = "";
    try { await salaApi("/api/chat", { proyecto: proyectoSala.id, texto }); proyectoSala = await salaApi(`/api/proyecto/${encodeURIComponent(proyectoSala.id)}`); pintarProyectoSala(); }
    catch (err) { alert(err.message); t.value = texto; }
  });
  $("#modal-cuerpo").addEventListener("keydown", (e) => {
    if (e.target.id === "pv-texto" && e.key === "Enter" && !e.shiftKey) { e.preventDefault(); $("#pv-form").requestSubmit(); }
  });
  $("#modal-cuerpo").addEventListener("click", async (e) => {
    const b = e.target.closest("button");
    if (!b || !proyectoSala || !$("#pv-cabeza")) return;
    if (b.dataset.sugerencia) { $("#pv-texto").value = b.dataset.sugerencia; $("#pv-texto").focus(); }
    if (b.dataset.usarMusica) {
      b.disabled = true;
      await salaApi("/api/chat", { proyecto: proyectoSala.id, texto: `usa la música ${b.dataset.usarMusica}` }).catch((err) => alert(err.message));
      proyectoSala = await salaApi(`/api/proyecto/${encodeURIComponent(proyectoSala.id)}`); pintarProyectoSala();
    }
    if (b.dataset.version) { versionVista = Number(b.dataset.version); $("#pv-video").innerHTML = ""; pintarProyectoSala(); }
    if (b.dataset.copiarRutaProy) navigator.clipboard?.writeText(b.dataset.copiarRutaProy).then(() => { b.textContent = "¡Copiada!"; });
    if (b.dataset.borrarProyecto !== undefined && confirm(`¿Borrar el proyecto «${proyectoSala.nombre}»? (Los clips de tu compu no se tocan)`)) {
      await salaApi(`/api/proyecto/${encodeURIComponent(proyectoSala.id)}/borrar`, {}).catch((err) => alert(err.message));
      proyectoSala = null; cerrarModal(); consultarSala();
    }
  });
  $("#modal-cuerpo").addEventListener("change", async (e) => {
    const input = e.target.closest("[data-subir-sala]");
    if (!input || !proyectoSala) return;
    const archivos = [...input.files].filter((f) => /\.(mp4|mov|m4v|webm|3gp|mkv)$/i.test(f.name));
    if (!archivos.length) return alert("En esa carpeta no hay videos.");
    for (const [k, f] of archivos.entries()) {
      await new Promise((listo) => {
        const xhr = new XMLHttpRequest();
        xhr.open("POST", `/sala/api/subir?proyecto=${encodeURIComponent(proyectoSala.id)}&nombre=${encodeURIComponent(f.name)}`);
        xhr.setRequestHeader("Content-Type", "application/octet-stream");
        xhr.upload.onprogress = (ev) => { if (ev.lengthComputable && $("#pv-subiendo")) $("#pv-subiendo").textContent = `Subiendo ${k + 1} de ${archivos.length}: ${Math.round(ev.loaded / ev.total * 100)} %`; };
        xhr.onloadend = () => { if (xhr.status !== 200) alert(`No se pudo subir ${f.name}`); listo(); };
        xhr.send(f);
      });
    }
    proyectoSala = await salaApi(`/api/proyecto/${encodeURIComponent(proyectoSala.id)}`);
    pintarProyectoSala();
  });

  async function consultarSala() {
    try {
      const r = await fetch("/sala/api/estado");
      if (!r.ok) throw new Error();
      const n = await r.json();
      // cada consulta cambia "visto hace…": se repinta si cambió algo o cada ~15 s
      if (n.version !== versionSala || !estadoSala || Date.now() - (estadoSala._pintado || 0) > 15000) {
        versionSala = n.version; estadoSala = { ...n, _pintado: Date.now() }; window.Oficina.actualizarSala(n); pintarSala();
      } else window.Oficina.actualizarSala(n);
    } catch {
      if (estadoSala !== null || versionSala === -1) { estadoSala = null; versionSala = -2; window.Oficina.actualizarSala(null); pintarSala(); }
    }
  }
  const haceRato = (t) => { const s = Date.now() / 1000 - t; return s < 90 ? "hace un momento" : s < 3600 ? `hace ${Math.round(s / 60)} min` : s < 86400 ? `hace ${Math.round(s / 3600)} h` : `hace ${Math.round(s / 86400)} d`; };
  const ESTADO_TRABAJO = { en_cola: "⏳ Esperando compu", asignado: "📥 Bajando clips", trabajando: "⚙️ Editando", listo: "✔ Listo",
                           error: "✖ Falló (lo hizo el servidor)", cancelado: "↩ Lo hizo el servidor" };

  // Esqueleto fijo: el cuadro donde escribes no se borra cuando se actualiza lo demás
  function esqueletoSala() {
    const cont = $("#sala-panel");
    if (cont.querySelector("#sala-chat-form")) return;
    cont.innerHTML = `
      <section class="sala-chat">
        <h4 class="seccion-mini">💬 Chat de la sala</h4>
        <ol id="sala-chat-log" class="chat-sala"></ol>
        <form id="sala-chat-form" class="fila chat-escribir">
          <input id="sala-chat-texto" maxlength="1500" autocomplete="off" placeholder="Ej. hazme un video vertical con los clips de Viaje Monterrey, 40 s con subtítulos">
          <button class="btn btn-primario" type="submit">Enviar</button>
        </form>
      </section>
      <section>
        <div class="seccion-cabeza"><h4 class="seccion-mini">📂 Proyectos</h4>
          <button type="button" class="btn btn-mini" data-nuevo-proyecto>➕ Nuevo proyecto</button></div>
        <form id="nuevo-proyecto" class="tarjeta nuevo-proyecto" hidden>
          <input id="np-nombre" maxlength="60" placeholder="Nombre (ej. Viaje Monterrey)">
          <select id="np-donde" aria-label="En qué compu"></select>
          <div class="fila"><select id="np-carpeta" aria-label="Qué carpeta"></select>
            <button type="button" class="btn btn-mini" id="np-elegir" title="Abre en tu compu la ventana de Windows para escoger la carpeta">📂 Elegir carpeta…</button></div>
          <input id="np-ruta" maxlength="300" placeholder="Pega la ruta, ej. C:\\Users\\Miguel\\Desktop\\Viaje" hidden>
          <small class="pista" id="np-ayuda"></small>
          <button class="btn btn-primario" type="submit">Crear</button>
        </form>
        <div id="sala-proyectos"></div>
      </section>
      <section><h4 class="seccion-mini">🖥️ Tus compus</h4><div id="sala-compus"></div></section>`;
  }

  const nombreEditor = (q) => q === "jefe" ? "Tú" : q === "sala" ? "Sala" : (estadoSala?.editores || []).find((e) => e.id === q)?.nombre || "Editor";
  const colorEditor = (q) => q === "jefe" ? "#cbd5e1" : (estadoSala?.editores || []).find((e) => e.id === q)?.color || "#a78bfa";
  const lineaChat = (m) => `<li class="${m.quien === "jefe" ? "mio" : ""}"><b style="color:${colorEditor(m.quien)}">${esc(nombreEditor(m.quien))}</b>
    <span>${esc(m.texto)}</span>${m.proyecto ? ` <button type="button" class="btn btn-mini" data-abrir-sala="${esc(m.proyecto)}">Abrir →</button>` : ""}
    ${(m.musica || []).length ? `<div class="opciones-musica">${m.musica.map((o) => `<div class="pista-musica">
        <b>${o.n}. ${esc(o.titulo)}</b> <small>de ${esc(o.autor)} · ${o.segundos ? `${o.segundos} s · ` : ""}${esc((o.licencia || "").toUpperCase())}${o.fuente ? ` · ${esc(o.fuente)}` : ""}</small>
        ${o.url ? `<audio controls preload="none" src="${esc(o.url)}"></audio>` : ""}
        <span class="fila"><button type="button" class="btn btn-mini" data-usar-musica="${o.n}">🎵 Usar esta</button>
        ${o.pagina ? `<a class="btn btn-mini" href="${esc(o.pagina)}" target="_blank" rel="noopener">Ver página</a>` : ""}</span></div>`).join("")}</div>` : ""}
    <small>${hora(m.t)}</small></li>`;
  // Al crear un proyecto en una compu: carpeta nueva en la sala, una carpeta que ya tienes, o pegar la ruta
  function carpetasDeCompu() {
    const donde = $("#np-donde").value, sel = $("#np-carpeta");
    if (!sel) return;
    sel.hidden = !donde;
    $("#np-elegir").hidden = !donde;
    const lugares = estadoSala?.locales?.[donde]?.lugares || [];
    const firma = donde + "|" + lugares.map((l) => l.ruta).join("|");
    if (sel.dataset.firma !== firma) {
      const antes = sel.value;
      sel.innerHTML = `<option value="">📁 Carpeta nueva en Sala de edicion</option>`
        + (lugares.length ? `<optgroup label="Carpetas que ya tienes">${lugares.map((l) => `<option value="${esc(l.ruta)}">${esc(l.nombre)}${l.videos ? ` (${l.videos} videos)` : ""}</option>`).join("")}</optgroup>` : "")
        + `<option value="__otra">✍️ Pegar otra ruta…</option>`;
      if ([...sel.options].some((o) => o.value === antes)) sel.value = antes;
      sel.dataset.firma = firma;
    }
    $("#np-ruta").hidden = !donde || sel.value !== "__otra";
    $("#np-ayuda").textContent = !donde ? "Tus clips se suben al servidor desde la ventana del proyecto."
      : sel.value === "" ? "Se crea la carpeta en Videos → Sala de edicion de esa compu."
      : "Tus clips se quedan donde están; las versiones caen en su subcarpeta «Ediciones».";
  }
  // «📂 Elegir carpeta…»: se abre en tu compu la ventana de Windows para escogerla y la ruta llega sola
  async function elegirCarpetaEnCompu(boton) {
    const compu = $("#np-donde").value;
    if (!compu) return;
    boton.disabled = true;
    const ayuda = $("#np-ayuda");
    try {
      const { id } = await salaApi("/api/elegir_carpeta", { compu });
      ayuda.textContent = "👀 Mira tu compu: se abre una ventana para elegir la carpeta (puede tardar unos segundos)…";
      for (let i = 0; i < 90; i++) {
        await new Promise((r) => setTimeout(r, 1500));
        const x = await salaApi(`/api/elegir_carpeta/${id}`);
        if (x.estado === "elegida") {
          const sel = $("#np-carpeta");
          sel.value = [...sel.options].some((o) => o.value === x.ruta) ? x.ruta : "__otra";
          $("#np-ruta").value = x.ruta;
          if (!$("#np-nombre").value) $("#np-nombre").value = x.ruta.replace(/\\/g, "/").split("/").pop();
          carpetasDeCompu();
          ayuda.textContent = `✔ Elegiste ${x.ruta}. Dale «Crear».`;
          break;
        }
        if (x.estado === "cancelada") { ayuda.textContent = x.error || "No elegiste carpeta."; break; }
        if (i === 89) ayuda.textContent = "Tu compu no abrió la ventana. ¿Está prendida y con la sala actualizada?";
      }
    } catch (err) { alert(err.message); }
    boton.disabled = false;
  }
  const ESTADO_PROYECTO = { esperando: "Esperando tus clips/instrucciones", editando: "✂️ Editando", listo: "✔ Versión lista", error: "Con problema" };

  function pintarSala() {
    const cont = $("#sala-panel");
    if (!cont) return;
    if (!estadoSala) { cont.innerHTML = `<p class="vacio">La sala de edición está apagada en el servidor. Mientras, Cris edita en el servidor como siempre.</p>`; return; }
    esqueletoSala();
    // chat general
    const log = $("#sala-chat-log"), abajo = log.scrollHeight - log.scrollTop - log.clientHeight < 40;
    log.innerHTML = (estadoSala.chat || []).map(lineaChat).join("") || `<li class="vacio">Escríbele a la sala qué video quieres: el editor libre lo toma.</li>`;
    if (abajo) log.scrollTop = log.scrollHeight;
    // dónde crear un proyecto
    const donde = $("#np-donde"), elegido = donde.value;
    donde.innerHTML = estadoSala.compus.map((c) => `<option value="${esc(c.id)}">🖥️ En ${esc(c.nombre)} (carpeta en tu compu)</option>`).join("")
      + `<option value="">☁️ Subirlos al servidor</option>`;
    if (elegido !== "" && [...donde.options].some((o) => o.value === elegido)) donde.value = elegido;
    carpetasDeCompu();
    // proyectos
    $("#sala-proyectos").innerHTML = (estadoSala.proyectos || []).map((p) => `<button type="button" class="proyecto-sala ${esc(p.estado)}" data-abrir-sala="${esc(p.id)}">
        <span class="miniatura-proy">${p.ultima?.cuadro ? `<img alt="" loading="lazy" src="/sala/salida/${encodeURIComponent(p.id)}/${encodeURIComponent(p.ultima.cuadro)}">` : "🎞️"}</span>
        <span class="proy-txt"><b>${esc(p.nombre)}</b>
          <small>${p.compu ? `🖥️ ${esc(nombreEditor("sala_" + p.compu))}` : "☁️ servidor"} · ${p.clips} clip${p.clips === 1 ? "" : "s"}${p.formato ? ` · ${p.formato === "vertical" ? "▯ vertical" : "▭ horizontal"}` : ""}${p.versiones ? ` · v${p.versiones}` : ""}</small>
          <small class="estado-proy">${p.estado === "editando" ? `✂️ ${esc(p.paso || "Editando")} · ${Math.round((p.avance || 0) * 100)} %` : esc(ESTADO_PROYECTO[p.estado] || p.estado)}</small>
        </span></button>`).join("") || `<p class="pista">Aún no hay proyectos. Crea uno, haz una carpeta nueva en <b>Videos → Sala de edicion</b> de tu compu, o pídeselo al chat.</p>`;
    const cont2 = $("#sala-compus");
    const compus = estadoSala.compus;
    const productos = Object.fromEntries((estadoTT?.productos || []).map((p) => [p.id, p]));
    const monitor = (c) => {
      const t = c.trabajo, av = t ? Math.round((t.avance || 0) * 100) : 0;
      const loc = estadoSala.locales?.[c.id] || { carpetas: {}, muestra: {} };
      const carpetas = Object.entries(loc.carpetas || {}).filter(([pid]) => productos[pid]);
      return `<article class="pc-monitor ${t ? "editando" : c.viva ? "lista" : "apagada"}">
        <div class="pantalla">
          ${t ? `<div class="pantalla-titulo">✂️ ${esc(t.etiqueta)}</div>
              <div class="pantalla-paso">${esc(t.paso || "Editando")}</div>
              <div class="pantalla-num">${av}<small>%</small></div>
              <div class="linea-tiempo"><b style="width:${av}%"></b>${[0, 1, 2, 3, 4, 5].map((k) => `<i style="left:${k * 17 + 2}%"></i>`).join("")}</div>`
            : c.viva ? (c.estado_texto && c.estado_texto !== "Lista" ? `<div class="pantalla-num chico">⚙️</div><div class="pantalla-paso">${esc(c.estado_texto)}</div>`
              : `<div class="pantalla-num chico">💤</div><div class="pantalla-paso">Lista para editar</div>`)
            : `<div class="pantalla-num chico">⏻</div><div class="pantalla-paso">Apagada · visto ${haceRato(c.ultimo)}</div>`}
        </div>
        <div class="pc-base">
          <b>🖥️ ${esc(c.nombre)}</b>
          <span class="pc-chips"><span class="chip">${esc(c.gpu || "—")}</span>${c.nvenc ? `<span class="chip chip-estado-publicado">NVENC</span>` : ""}
            <span class="chip">👂 ${esc((c.oido || "—").replace(" (GPU)", " GPU").replace(" (CPU)", " CPU"))}</span>
            <span class="chip">🎬 ${c.editados || 0}</span></span>
        </div>
        ${carpetas.length ? `<div class="pc-carpetas"><small>📁 ${esc(loc.ruta || "Sala de edicion")}</small>
          ${carpetas.map(([pid, n]) => `<button type="button" class="pc-carpeta" data-abrir-producto="${esc(pid)}">
              <span class="tiras">${(loc.muestra?.[pid] || []).slice(0, 4).map((nombre) => `<img loading="lazy" alt="" src="/sala/api/miniatura/${encodeURIComponent(c.id)}/${encodeURIComponent(pid)}/${encodeURIComponent(nombre)}">`).join("") || "<i>vacía</i>"}</span>
              <span class="pc-carpeta-txt"><b>${esc(productos[pid].nombre)}</b><small>${n} clip${n === 1 ? "" : "s"}${productos[pid].videos ? " · 🎬 video listo" : ""}</small></span>
            </button>`).join("")}</div>` : ""}
        <div class="pc-acciones"><button class="btn btn-mini" data-quitar-compu="${esc(c.id)}">Quitar de la sala</button></div>
      </article>`;
    };
    const agregar = `
        <ol class="pasos-alta">
          <li>En esa compu, abre tu oficina en el navegador y baja el instalador:<br>
            <a class="btn btn-mini btn-primario" href="/sala/descargar/INSTALAR_SALA.bat" download>⬇️ INSTALAR_SALA.bat</a></li>
          <li>Ábrelo con doble clic. Si Windows dice "Windows protegió su PC": <b>Más información → Ejecutar de todas formas</b>.</li>
          <li>Cuando te pida el código, genéralo aquí (sirve 15 min y una sola vez):<br>
            ${codigoSala && codigoSala.vence * 1000 > Date.now() ? `<span class="codigo-sala">${esc(codigoSala.codigo.slice(0, 3))} ${esc(codigoSala.codigo.slice(3))}</span>
              <br><small>Dirección: <b>${esc(location.origin)}</b></small>` : `<button class="btn btn-mini" data-codigo-sala>🔑 Generar código</button>`}</li>
          <li>Listo: aparece aquí y en la sala del edificio, y arranca sola al prender la compu. Tus clips van en <b>Videos → Sala de edicion</b>.</li>
        </ol>`;
    cont2.innerHTML = `
      <p class="pista">🎬 Cada compu tiene su editor. Tus clips van en <b>Videos → Sala de edicion</b> (una carpeta por proyecto o producto): no se suben al servidor.</p>
      <div class="pc-lista">${compus.map(monitor).join("") || `<p class="vacio">Todavía no hay compus en la sala.</p>`}</div>
      ${compus.length ? `<details class="tarjeta"><summary>➕ Agregar otra compu (Windows)</summary>${agregar}</details>`
        : `<article class="tarjeta"><h4>➕ Agregar una compu (Windows)</h4>${agregar}</article>`}
      ${estadoSala.trabajos.length ? `<h4 class="seccion-mini">Últimos trabajos</h4><ul class="trabajos-sala">${estadoSala.trabajos.map((t) => `<li>
          <b>${esc(t.etiqueta)}</b> · ${esc(ESTADO_TRABAJO[t.estado] || t.estado)}${t.inicio && t.fin ? ` · ${duracion(t.fin - t.inicio)}` : ""} · ${haceRato(t.creado)}
          ${t.error ? `<br><small>${esc(t.error)}</small>` : ""}</li>`).join("")}</ul>` : ""}`;
  }

  $("#sala-panel").addEventListener("submit", async (e) => {
    e.preventDefault();
    if (e.target.id === "sala-chat-form") {
      const t = $("#sala-chat-texto"), texto = t.value.trim();
      if (!texto) return;
      t.value = "";
      try { await salaApi("/api/chat", { texto }); } catch (err) { alert(err.message); t.value = texto; }
      consultarSala();
    }
    if (e.target.id === "nuevo-proyecto") {
      try {
        const carpeta = $("#np-carpeta").value, donde = $("#np-donde").value;
        const ruta = !donde ? "" : carpeta === "__otra" ? $("#np-ruta").value.trim() : carpeta;
        if (!$("#np-nombre").value.trim() && !ruta) return alert("Ponle nombre al proyecto o elige una carpeta.");
        const r = await salaApi("/api/proyecto", { nombre: $("#np-nombre").value, donde, ruta });
        $("#np-nombre").value = ""; $("#np-ruta").value = ""; $("#nuevo-proyecto").hidden = true;
        await consultarSala();
        abrirProyectoSala(r.id);
      } catch (err) { alert(err.message); }
    }
  });
  $("#sala-panel").addEventListener("change", (e) => {
    if (["np-donde", "np-carpeta"].includes(e.target.id)) carpetasDeCompu();
    if (e.target.id === "np-carpeta" && e.target.value && e.target.value !== "__otra" && !$("#np-nombre").value)
      $("#np-nombre").value = e.target.value.replace(/\\/g, "/").split("/").pop();
  });
  $("#sala-panel").addEventListener("click", async (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    if (b.dataset.abrirSala) return abrirProyectoSala(b.dataset.abrirSala);
    if (b.id === "np-elegir") return elegirCarpetaEnCompu(b);
    if (b.dataset.nuevoProyecto !== undefined) { $("#nuevo-proyecto").hidden = !$("#nuevo-proyecto").hidden; return $("#np-nombre").focus(); }
    if (b.dataset.abrirProducto) return abrirGuionTT(b.dataset.abrirProducto);
    try {
      if (b.dataset.codigoSala !== undefined) {
        const r = await fetch("/sala/api/codigo", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
        if (!r.ok) throw new Error("No pude generar el código.");
        codigoSala = await r.json();
        setTimeout(pintarSala, (codigoSala.vence * 1000 - Date.now()) + 500);
      }
      if (b.dataset.quitarCompu && confirm("¿Quitar esta compu de la sala? (Para volver a usarla hay que reinstalarla con un código nuevo)")) {
        await fetch(`/sala/api/quitar/${encodeURIComponent(b.dataset.quitarCompu)}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
      }
    } catch (err) { alert(err.message); }
    pintarSala();
    consultarSala();
  });

  api("/api/estado").then(pintar).catch(() => {});
  conectar();
  consultarTT();
  setInterval(consultarTT, 2000);
  consultarSala();
  setInterval(consultarSala, 3000);
  setInterval(() => { if (!$("#modal").hidden && $("#locales-tt")) cargarLocales(); }, 5000);
})();
