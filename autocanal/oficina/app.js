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
    if (!lista.length) { $("#proyectos").innerHTML = `<p class="vacio">Aún no hay proyectos. Aprueba una idea para arrancar.</p>`; return; }
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
        ${p.blog_pendiente ? `<div class="pendiente-blog">📝 El blog quedó pendiente${p.publicado?.blog_error ? `: ${esc(p.publicado.blog_error.slice(0, 120))}` : ""}
          <button class="btn btn-mini btn-primario" data-subir-blog="${esc(p.id)}">Subir blog</button></div>` : ""}
        ${p.costo ? `<div class="costo">💰 ${dinero(p.costo)} <span>${Object.entries(p.costos || {}).map(([e, v]) => `${esc(ETIQUETA_ETAPA[e] || e)} ${dinero(v)}`).join(" · ")}</span></div>` : ""}
        ${["revision", "publicado"].includes(p.estado) ? `<button class="btn ancho" data-revisar="${esc(p.id)}">Ver video</button>` : ""}
      </article>`;
    }).join("");
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
            <ul class="checklist">${d.pendiente.map((x, k) => `<li><label><input type="checkbox" class="check" ${editable ? "" : "checked disabled"}> ${esc(x)}</label></li>`).join("")}
            <li><label><input type="checkbox" class="check" ${editable ? "" : "checked disabled"}> Cada afirmación del guion tiene respaldo</label></li></ul>` : ""}
          <h3>Evidencia</h3>
          <ul class="senales">${d.senales.map((s) => `<li><span class="grav grav-${esc(s.gravedad)}">${esc(s.gravedad)}</span> <b>${esc(s.senal)}</b> — ${esc(s.evidencia)} <i>(${esc(s.fuente)})</i></li>`).join("")}</ul>
          ${d.fuentes.length ? `<details><summary>Fuentes (${d.fuentes.length})</summary><ul>${d.fuentes.map((f) => `<li><a href="${esc(f.url)}" target="_blank" rel="noopener">${esc(f.titulo)}</a></li>`).join("")}</ul></details>` : ""}
          ${d.palabra_clave ? `<h3>SEO del blog</h3><p class="seo"><b>Palabra clave:</b> ${esc(d.palabra_clave)}<br>
            <b>Secundarias:</b> ${esc((d.palabras_secundarias || []).join(", "))}<br><b>Meta descripción:</b> ${esc(d.meta_descripcion || "")}</p>` : ""}
          <h3>Título</h3>
          <div class="titulos">${d.titulos.map((t, k) => `<label><input type="radio" name="titulo" value="${k + 1}" ${k ? "" : "checked"} ${editable ? "" : "disabled"}> ${esc(t)}</label>`).join("")}</div>
          <details><summary>Guion (${d.escenas.length} escenas)</summary><ol class="guion">${d.escenas.map((e) => `<li>${esc(e)}</li>`).join("")}</ol></details>
        </div>
      </div>
      ${editable ? `
      <div class="pie">
        <textarea id="cambios" rows="2" placeholder="¿Qué cambiarías? Ej. el gancho más directo, menciona el pago mínimo antes…"></textarea>
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
    const checks = [...document.querySelectorAll(".check")];
    const revisarChecks = () => {
      const listo = checks.every((c) => c.checked);
      $("#b-publicar").disabled = !listo;
      $("#nota-publicar").hidden = listo;
    };
    checks.forEach((c) => c.addEventListener("change", revisarChecks));
    revisarChecks();
    const enviar = async (accion, texto = "") => {
      const titulo = Number(document.querySelector("input[name=titulo]:checked")?.value || 1);
      try { await api(`/api/proyecto/${encodeURIComponent(id)}`, { accion, texto, titulo }); cerrarModal(); }
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
  const tareasDe = (id) => (estado.tareas || []).filter((t) => t.agente === id);
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
      cont.innerHTML = `<div class="equipo-cabeza"><p class="pista">Pícale a un agente (aquí o en la oficina) para ver sus tareas.</p>
        ${terminadas ? `<button class="btn btn-mini" data-limpiar="">🧹 Borrar terminadas (${terminadas})</button>` : ""}</div>
        <div class="equipo-lista">${estado.agentes.map((a) => {
          const [txt, cls] = estadoAgente(a);
          const actual = tareasDe(a.id).find((t) => t.estado === "trabajando");
          const fila = tareasDe(a.id).filter((t) => ["en_cola", "esperando"].includes(t.estado)).length;
          return `<button class="agente-tarjeta" data-agente="${a.id}" style="--c:${a.color}">
            <canvas class="retrato" data-retrato="${a.id}" width="72" height="152"></canvas>
            <span class="agente-info">
              <b>${esc(a.id === "jefe" ? "Tú" : a.nombre)}</b> <small>${esc(a.rol)}</small>
              <span class="estado-chip ${cls}">${esc(txt)}</span>
              <span class="agente-ahora">${actual ? `${esc(actual.accion)} · ${esc(actual.titulo)}` : a.id === "jefe" ? "Revisa tu bandeja" : "—"}</span>
              ${fila ? `<span class="agente-fila">${fila} en fila</span>` : ""}
            </span>
          </button>`;
        }).join("")}</div>`;
    } else {
      const a = estado.agentes.find((x) => x.id === agenteVisto);
      const ts = tareasDe(a.id).slice().reverse();
      const actual = ts.filter((t) => t.estado === "trabajando");
      const fila = ts.filter((t) => ["en_cola", "esperando"].includes(t.estado)).reverse();
      const hechas = ts.filter((t) => ["hecha", "fallo", "cancelada"].includes(t.estado)).slice(0, 10);
      const frases = estado.log.filter((m) => m.quien === a.id).slice(-3).reverse();
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
            <p class="desc">${esc(DESCRIPCION[a.id] || "")}</p>
          </div>
        </div>
        ${a.id === "jefe" ? `<p class="vacio">Tus pendientes están en la Bandeja.</p>` : `
        <h4 class="seccion-mini">Ahora</h4>
        ${actual.length ? `<ul class="tareas">${actual.map((t) => tarjeta(t, true)).join("")}</ul>` : `<p class="vacio">${a.estado === "libre" ? "Sin tareas: está libre." : "Entregando trabajo a un compañero."}</p>`}
        <h4 class="seccion-mini">En fila ${fila.length ? `(${fila.length})` : ""}</h4>
        ${fila.length ? `<ul class="tareas">${fila.map((t) => tarjeta(t, false)).join("")}</ul>` : `<p class="vacio">Nada en fila.</p>`}
        <h4 class="seccion-mini">Terminadas ${hechas.length ? `<button class="btn btn-mini" data-limpiar="${esc(a.id)}">🧹 Borrar</button>` : ""}</h4>
        ${hechas.length ? `<ul class="tareas">${hechas.map((t) => tarjeta(t, false)).join("")}</ul>` : `<p class="vacio">Todavía nada.</p>`}`}
        ${frases.length ? `<h4 class="seccion-mini">Lo último que dijo</h4><ul class="frases">${frases.map((m) => `<li>“${esc(m.texto)}” <small>${hora(m.t)}</small></li>`).join("")}</ul>` : ""}`;
      // barra de avance aproximada
      const DUR = { ideas: 30, investigar: 90, guion: 60, voz: 45, miniatura: 8, video: 150, blog: 60, publicar: 60 };
      cont.querySelectorAll(".tarea-trabajando .barra-tarea b").forEach((b, k) => {
        const t = actual[k];
        const av = t.avance != null ? t.avance : 1 - Math.exp(-(reloj() - t.inicio) / (DUR[t.etapa] || 60) * 1.6);
        b.style.width = `${Math.min(97, av * 100)}%`;
      });
    }
    cont.querySelectorAll("[data-retrato]").forEach((c) => window.Oficina.retrato(c.dataset.retrato, c));
  }

  function verAgente(id) {
    const fichaTT = !estado?.agentes.some((a) => a.id === id) && (estadoTT?.agentes.find((a) => a.id === id) || window.Oficina.ficha(id));
    if (fichaTT) return verAgenteEnObra(fichaTT);
    agenteVisto = id;
    window.Oficina.seleccionar(id);
    abrirPestana("equipo");
    pintarEquipo(true);
    $("#tab-equipo").scrollTop = 0;
  }

  // El equipo de TikTok Shop todavía no tiene su oficina conectada: se muestra su ficha
  function verAgenteEnObra(a) {
    $("#modal-cuerpo").innerHTML = `
      <div class="obra" style="--c:${a.color}">
        <canvas class="retrato grande" data-retrato="${esc(a.id)}" width="108" height="228"></canvas>
        <div>
          <h2 id="modal-titulo">${esc(a.nombre)}</h2>
          <p class="rol">${esc(a.rol)} · Ala TikTok Shop</p>
          <p class="desc">${esc(a.desc)}</p>
          ${a.enObra ? `<p class="aviso">🚧 La oficina de TikTok Shop está apagada. ${esc(a.nombre)} trabaja cuando esté prendida.</p>`
            : tareaTT(a.id)}
        </div>
      </div>`;
    window.Oficina.retrato(a.id, $("#modal-cuerpo canvas"));
    $("#modal").hidden = false;
    $("#modal-cerrar").focus();
  }

  function tareaTT(id) {
    const ts = (estadoTT?.tareas || []).filter((t) => t.agente === id);
    const ahora = ts.find((t) => t.estado === "trabajando");
    const ultimas = ts.filter((t) => t.estado !== "trabajando").slice(-3).reverse();
    return `<p><b>${ahora ? `Ahora: ${esc(ahora.accion)} · ${esc(ahora.titulo)}` : "Libre"}</b></p>
      ${ultimas.length ? `<ul class="frases">${ultimas.map((t) => `<li>${t.estado === "hecha" ? "✔" : "✖"} ${esc(t.accion)} · ${esc(t.titulo)}
        ${t.costo ? `<small>💰 ${dinero(t.costo)}</small>` : ""}${t.error ? `<br><small>${esc(t.error)}</small>` : ""}</li>`).join("")}</ul>` : ""}`;
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

  $("#lienzo").addEventListener("click", (e) => {
    const id = window.Oficina.agenteEn(e.clientX, e.clientY);
    if (id) verAgente(id);
  });
  $("#lienzo").addEventListener("mousemove", (e) => {
    const id = window.Oficina.agenteEn(e.clientX, e.clientY);
    window.Oficina.encima(id);
    $("#lienzo").style.cursor = id ? "pointer" : "default";
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
  const ETAPAS_TT = [["ficha", "Toño investiga"], ["guion", "Sofi escribe"], ["tomas", "Diego arma tomas"]];
  const ESTADO_TT = { trabajando: "En proceso", listo: "Listo para grabar", error: "Con problema" };
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
      if (n.version !== versionTT || !estadoTT) { versionTT = n.version; estadoTT = n; window.Oficina.actualizarTT(n); pintarShop(); }
    } catch {
      if (estadoTT !== null || versionTT === -1) { estadoTT = null; versionTT = -2; window.Oficina.actualizarTT(null); pintarShop(); }
    }
  }

  function pintarShop() {
    $("#shop-apagada").hidden = !!estadoTT;
    $("#form-producto").hidden = !estadoTT;
    if (!estadoTT) { $("#shop-lista").innerHTML = ""; $("#shop-gasto").textContent = ""; $("#cuenta-shop").hidden = true; return; }
    const g = estadoTT.gasto;
    $("#shop-gasto").innerHTML = `💰 Oficina TikTok hoy <b>${dinero(g.hoy)}</b>${g.tope ? ` / tope ${dinero(g.tope)}` : ""} · mes ${dinero(g.mes)}`
      + (estadoTT.demo ? ` · <span class="chip chip-demo">DEMO</span>` : "");
    const vistos = new Set(leerVistos());
    const nuevos = estadoTT.productos.filter((p) => p.estado === "listo" && !vistos.has(p.id)).length;
    $("#cuenta-shop").hidden = !nuevos;
    $("#cuenta-shop").textContent = nuevos;
    if (!estadoTT.productos.length) { $("#shop-lista").innerHTML = `<p class="vacio">Todavía no hay productos. Cuando te llegue uno, ponlo arriba.</p>`; return; }
    $("#shop-lista").innerHTML = estadoTT.productos.map((p) => `<article class="tarjeta ${p.estado === "error" ? "tarjeta-error" : ""}">
        <div class="cabeza"><h4>${esc(p.nombre)}</h4><span class="chip ${p.estado === "listo" ? "chip-estado-publicado" : p.estado === "error" ? "chip-estado-error" : ""}">${esc(ESTADO_TT[p.estado] || p.estado)}</span></div>
        <ol class="pasos-shop">${ETAPAS_TT.map(([e, txt]) => `<li class="${esc(p.etapas?.[e] || "")}">${esc(txt)}</li>`).join("")}</ol>
        ${p.guion_id ? `<p class="pista">${esc(FORMATO_TT[p.formato] || p.formato || "")} · <code>${esc(p.guion_id)}</code></p>` : ""}
        ${p.error ? `<p class="error">${esc(p.error)}</p>` : ""}
        ${p.costo ? `<div class="costo">💰 ${dinero(p.costo)}</div>` : ""}
        <div class="fila">
          ${p.etapas?.guion === "hecha" ? `<button class="btn btn-primario" data-ver-tt="${esc(p.id)}">Ver guion y tomas</button>` : ""}
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

  async function abrirGuionTT(id) {
    const p = await apiTT(`/api/producto/${encodeURIComponent(id)}`);
    const g = p.guion, f = p.ficha || {}, t = p.tomas;
    try { const v = new Set(leerVistos()); v.add(id); localStorage.setItem("shop_vistos", JSON.stringify([...v].slice(-200))); } catch { /* sin almacenamiento */ }
    const caption = `${g.caption}\n\n${(g.hashtags || []).join(" ")}`;
    $("#modal-cuerpo").innerHTML = `<div class="guion-shop">
      <h2 id="modal-titulo">${esc(p.nombre)}</h2>
      <p class="id">ID: ${esc(g.id)} · ${esc(FORMATO_TT[g.formato] || g.formato)} · ${g.duracion === "corta" ? "15–25 s" : "35–50 s"}</p>
      <p><b>Ángulo:</b> ${esc(g.angulo)}</p>
      ${g.supuestos ? `<p class="pista">Supuse: ${esc(g.supuestos)}</p>` : ""}
      ${p.de_marca ? `<p class="marca-aviso">🏷️ Al subirlo, actívale <b>"Contenido de marca"</b> en TikTok (te lo mandó una marca).</p>` : ""}
      <h3>3 ganchos (mismo cuerpo)</h3>
      <div class="ganchos">${g.ganchos.map((x) => `<div class="gancho"><b>${esc(x.letra)}</b> · ${esc(x.tipo)} <small class="id">${esc(g.id)}-${esc(x.letra)}</small>
        <p>🎥 ${esc(x.toma)}</p><p class="texto-pantalla">🅣 ${esc(x.texto_pantalla)}</p><p>🗣️ ${esc(x.voz || "(sin voz)")}</p></div>`).join("")}</div>
      <h3>Cuerpo</h3>
      <table class="tabla-shop"><thead><tr><th>Tiempo</th><th>Toma</th><th>Texto en pantalla</th><th>Voz</th></tr></thead>
        <tbody>${g.cuerpo.map((c) => `<tr><td>${esc(c.tiempo)}<br><small>${esc(BLOQUE_TT[c.bloque] || c.bloque)}</small></td><td>${esc(c.toma)}</td>
          <td class="texto-pantalla">${esc(c.texto_pantalla)}</td><td>${esc(c.voz)}</td></tr>`).join("")}</tbody></table>
      <h3>Caption <button class="btn btn-mini" data-copiar="caption">Copiar</button></h3>
      <div class="copiable" id="copiar-caption">${esc(caption.replace("\\n", "\n"))}</div>
      <h3>Comentario fijado <button class="btn btn-mini" data-copiar="comentario">Copiar</button></h3>
      <div class="copiable" id="copiar-comentario">${esc(g.comentario_fijado)}</div>
      ${t ? `<h3>🎥 Lista de tomas de Diego (en orden de grabación)</h3>
        ${t.material?.length ? `<p><b>Ten a la mano:</b> ${t.material.map(esc).join(", ")}</p>` : ""}
        <ul class="tomas-lista">${t.tomas.map((x) => `<li><input type="checkbox" aria-label="Toma ${x.n} grabada"><div>
          <b>${x.n}. ${esc(x.que_grabar)}</b> <small>· ${esc(x.lugar)} · ${esc(x.encuadre)} · ${esc(x.segundos)} s · para ${esc(x.para)}</small>
          ${x.tip ? `<br><small>💡 ${esc(x.tip)}</small>` : ""}</div></li>`).join("")}</ul>
        ${t.consejos?.length ? `<ul class="fuentes">${t.consejos.map((c) => `<li>${esc(c)}</li>`).join("")}</ul>` : ""}` : ""}
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
    $("#modal").hidden = false;
    $("#modal-cerrar").focus();
    pintarShop();
  }
  $("#modal-cuerpo").addEventListener("click", (e) => {
    const b = e.target.closest("[data-copiar]");
    if (!b) return;
    const texto = $(`#copiar-${b.dataset.copiar}`).textContent;
    navigator.clipboard?.writeText(texto).then(() => { b.textContent = "¡Copiado!"; setTimeout(() => (b.textContent = "Copiar"), 1500); })
      .catch(() => alert("No se pudo copiar; selecciónalo y cópialo a mano."));
  });

  api("/api/estado").then(pintar).catch(() => {});
  conectar();
  consultarTT();
  setInterval(consultarTT, 2000);
})();
