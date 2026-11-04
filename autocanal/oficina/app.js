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
  const hora = (t) => new Date(t * 1000).toLocaleTimeString("es-MX", { hour: "2-digit", minute: "2-digit" });

  async function api(ruta, datos) {
    const r = await fetch(ruta, { method: datos ? "POST" : "GET", headers: { "Content-Type": "application/json" },
                                  body: datos ? JSON.stringify(datos) : undefined });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.error || "Algo salió mal");
    return j;
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
    pintarBandeja();
    pintarProyectos();
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
    html += `<h3 class="seccion">Ideas de Paola ${ideas.length ? `<span class="sub">¿qué opinas?</span>` : ""}</h3>`;
    if (!ideas.length) {
      html += `<p class="vacio">No hay ideas pendientes. Pídele a Paola que busque apps nuevas.</p>`;
    }
    for (const i of ideas) {
      const abierto = abiertos.has(i.id);
      html += `
        <article class="tarjeta" data-idea="${esc(i.id)}">
          <div class="cabeza"><h4>${esc(i.titulo)}</h4><span class="chip chip-${esc(i.potencial_vistas)}">${esc(i.potencial_vistas)}</span></div>
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
      const i = estado.etapas.indexOf(p.etapa);
      const pasos = estado.etapas.map((et, k) => {
        const a = agentes[AGENTE_ETAPA[et]];
        const clase = k < i || p.estado === "publicado" ? "hecho" : k === i ? (p.estado === "error" ? "falla" : "actual") : "";
        return `<li class="${clase}" title="${esc(ETIQUETA_ETAPA[et])} · ${esc(a?.nombre)}"><span style="--c:${a?.color}"></span>${esc(ETIQUETA_ETAPA[et])}</li>`;
      }).join("");
      const pub = p.publicado ? `<div class="enlaces"><a href="${esc(p.publicado.youtube)}" target="_blank" rel="noopener">▶ YouTube</a>
        <a href="${esc(p.publicado.blog?.link)}" target="_blank" rel="noopener">✎ Blog</a></div>` : "";
      return `<article class="tarjeta">
        <div class="cabeza"><h4>${esc(p.titulo)}</h4><span class="chip chip-estado-${esc(p.estado)}">${esc(ESTADO_PROY[p.estado] || p.estado)}</span></div>
        <ol class="pasos">${pasos}</ol>${pub}
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

  document.querySelectorAll(".pestana").forEach((p) => p.addEventListener("click", () => {
    document.querySelectorAll(".pestana").forEach((x) => x.classList.toggle("activa", x === p));
    document.querySelectorAll(".contenido").forEach((c) => (c.hidden = c.id !== `tab-${p.dataset.tab}`));
    if (p.dataset.tab === "chat") $("#chat").scrollTop = $("#chat").scrollHeight;
  }));

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
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") { cerrarModal(); $("#ficha").hidden = true; } });

  // ---------- ficha de agente al hacer clic ----------
  $("#lienzo").addEventListener("click", (e) => {
    const id = window.Oficina.agenteEn(e.clientX, e.clientY);
    const ficha = $("#ficha");
    if (!id || !estado) { ficha.hidden = true; return; }
    const a = estado.agentes.find((x) => x.id === id);
    const proyecto = estado.proyectos.find((p) => p.id === a.proyecto);
    const frases = estado.log.filter((m) => m.quien === id).slice(-4).reverse();
    const descripcion = {
      productora: "Busca apps en Play Store, te propone ideas, aprende de tus opiniones y coordina al equipo.",
      investigador: "Lee reseñas, busca en internet y arma el expediente de evidencia.",
      guionista: "Escribe el guion con tu estilo, los títulos y el texto de la miniatura.",
      locutor: "Narra cada escena del guion.", disenadora: "Diseña la miniatura.",
      editor: "Edita el video: escenas, zoom, subtítulos y música.",
      redactora: "Escribe la entrada SEO del blog con capturas.",
      community: "Publica en WordPress y YouTube y conecta uno con otro.",
      jefe: "Apruebas ideas, opinas y das el visto bueno final.",
    }[id];
    ficha.innerHTML = `<div class="cabeza"><span class="punto" style="--c:${a.color}"></span><b>${esc(id === "jefe" ? "Tú" : a.nombre)}</b> · ${esc(a.rol)}</div>
      <p>${esc(descripcion)}</p>
      <p class="estado-agente">${a.estado === "trabajando" ? `Trabajando en <b>${esc(proyecto?.titulo || "algo")}</b>` : "Libre"}</p>
      ${frases.length ? `<ul>${frases.map((m) => `<li>“${esc(m.texto)}”</li>`).join("")}</ul>` : ""}`;
    ficha.style.left = `${Math.min(e.clientX + 12, window.innerWidth - 300)}px`;
    ficha.style.top = `${Math.min(e.clientY + 12, window.innerHeight - 220)}px`;
    ficha.hidden = false;
  });
  $("#lienzo").addEventListener("mousemove", (e) => {
    $("#lienzo").style.cursor = window.Oficina.agenteEn(e.clientX, e.clientY) ? "pointer" : "default";
  });
  document.addEventListener("click", (e) => { if (!e.target.closest("#ficha, #lienzo")) $("#ficha").hidden = true; });

  api("/api/estado").then(pintar).catch(() => {});
  conectar();
})();
