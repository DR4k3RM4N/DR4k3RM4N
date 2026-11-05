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
                      no_concluyente: ["SIN PRUEBAS", "gris"] };
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
      $("#gasto").innerHTML = `💰 Hoy <b>${dinero(nuevo.gasto.hoy)}</b> <span>· mes ${dinero(nuevo.gasto.mes)}</span>`;
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
          <div class="cabeza"><h4>${i.num ? `<span class="num">${i.num}</span>` : ""}${esc(i.titulo)}</h4><span class="chip chip-${esc(i.potencial_vistas)}">${esc(i.potencial_vistas)}</span></div>
          <p class="angulo">🎬 ${esc(i.angulo || "")}</p>
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
        <a href="${esc(p.publicado.blog?.link)}" target="_blank" rel="noopener">✎ Blog</a></div>` : "";
      return `<article class="tarjeta">
        <div class="cabeza"><h4>${esc(p.titulo)}</h4><span class="chip chip-estado-${esc(p.estado)}">${esc(ESTADO_PROY[p.estado] || p.estado)}</span></div>
        <ol class="pasos">${pasos}</ol>${pub}
        ${p.costo ? `<div class="costo">💰 ${dinero(p.costo)} <span>${Object.entries(p.costos || {}).map(([e, v]) => `${esc(ETIQUETA_ETAPA[e] || e)} ${dinero(v)}`).join(" · ")}</span></div>` : ""}
        ${["revision", "publicado"].includes(p.estado) ? `<button class="btn ancho" data-revisar="${esc(p.id)}">Ver video</button>` : ""}
      </article>`;
    }).join("");
  }
  $("#proyectos").addEventListener("click", (e) => {
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
          ${d.miniatura ? `<figure><img src="${esc(d.miniatura)}" alt="Miniatura del video"><figcaption>Miniatura</figcaption></figure>` : ""}
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

  function pintarEquipo() {
    if (!estado || $("#tab-equipo").hidden || presionado) return;
    if (document.activeElement?.closest?.("#equipo")) return;
    const cont = $("#equipo");
    if (!agenteVisto) {
      cont.innerHTML = `<p class="pista">Pícale a un agente (aquí o en la oficina) para ver sus tareas.</p>
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
          ${viva ? `<div class="tarea-tiempo">⏱ ${duracion(reloj() - t.inicio)}</div><div class="barra-tarea"><b></b></div>` : ""}
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
        <h4 class="seccion-mini">Terminadas</h4>
        ${hechas.length ? `<ul class="tareas">${hechas.map((t) => tarjeta(t, false)).join("")}</ul>` : `<p class="vacio">Todavía nada.</p>`}`}
        ${frases.length ? `<h4 class="seccion-mini">Lo último que dijo</h4><ul class="frases">${frases.map((m) => `<li>“${esc(m.texto)}” <small>${hora(m.t)}</small></li>`).join("")}</ul>` : ""}`;
      // barra de avance aproximada
      const DUR = { ideas: 30, investigar: 90, guion: 60, voz: 45, miniatura: 8, video: 150, blog: 60, publicar: 60 };
      cont.querySelectorAll(".tarea-trabajando .barra-tarea b").forEach((b, k) => {
        const t = actual[k];
        const av = 1 - Math.exp(-(reloj() - t.inicio) / (DUR[t.etapa] || 60) * 1.6);
        b.style.width = `${Math.min(97, av * 100)}%`;
      });
    }
    cont.querySelectorAll("[data-retrato]").forEach((c) => window.Oficina.retrato(c.dataset.retrato, c));
  }

  function verAgente(id) {
    agenteVisto = id;
    window.Oficina.seleccionar(id);
    abrirPestana("equipo");
  }

  $("#equipo").addEventListener("click", (e) => {
    if (e.target.closest("[data-volver]")) { agenteVisto = null; window.Oficina.seleccionar(null); return pintarEquipo(); }
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

  api("/api/estado").then(pintar).catch(() => {});
  conectar();
})();
