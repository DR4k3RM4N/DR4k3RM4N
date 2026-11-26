// 🕵️ Pestaña Expedientes (serie «¿Quién MATÓ a…?»): importar el paquete, reporte del Detective Ramos con
// ✅/⚠️/❌, aprobar cambios (narración corregida + PDF), lista final antes de subir y chat con el equipo.
(() => {
  const $ = (s) => document.querySelector(s);
  const caja = $("#expedientes");
  if (!caja) return;
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const hora = (t) => new Date(t * 1000).toLocaleString("es-MX", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
  const leer = (k, d) => { try { return localStorage.getItem(k) ?? d; } catch { return d; } };
  const guardar = (k, v) => { try { v == null ? localStorage.removeItem(k) : localStorage.setItem(k, v); } catch { /* sin almacenamiento */ } };

  let vista = leer("exp_vista", null); // expediente abierto (null = la lista)
  let filtro = leer("exp_filtro", "revisar");
  const editando = new Set();
  let ultimo = "";
  let datosVista = null;

  const ICONO = { confirmado: "✅", corregir: "⚠️", no_confirmado: "❌", pendiente: "⏳", no_es_dato: "➖" };
  const TXT = { confirmado: "Confirmado", corregir: "Corregir", no_confirmado: "No confirmado", pendiente: "Sin revisar", no_es_dato: "No es dato" };
  const PASO = { listo: ["✅", "Listo"], espera_ok: ["👀", "Te toca"], trabajando: ["⏳", "Trabajando"], pendiente: ["○", "Pendiente"],
                 bloqueado: ["🔒", "Espera la verificación"], en_obra: ["🚧", "En obra"], error: ["✖", "Con problema"] };
  const VERIF = { sin_empezar: "Sin empezar", trabajando: "Ramos trabajando", interrumpida: "Se interrumpió", lista: "Te toca revisar",
                  aprobada: "Aprobada", error: "Con problema" };
  const FILTROS = [["revisar", "⚠️❌ Por decidir"], ["todos", "Todos"], ["confirmado", "✅ Confirmados"], ["pendiente", "⏳ Sin revisar"],
                   ["no_es_dato", "➖ No son datos"], ["a_mano", "🔎 Revísalo tú"]];

  async function api(ruta, datos) {
    const r = await fetch(ruta, { method: datos ? "POST" : "GET", headers: { "Content-Type": "application/json" },
                                  body: datos ? JSON.stringify(datos) : undefined });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.error || "Algo salió mal");
    return j;
  }

  function origen(d) {
    if (d.origen === "pantalla") return `🅣 Texto en pantalla · escena ${d.escena}`;
    if (d.origen === "grafica") return `📊 Gráfica ${esc(String(d.dato).split(" · ")[0])}`;
    if (d.origen === "previo") return `🗂️ Ya verificado en el chat${d.lista ? ` · dato #${d.lista} de la lista` : ""}${d.pendiente_original ? " · falta leer el original" : ""}`;
    if (d.origen === "lista") return `📋 Lista de datos por verificar · #${d.lista}`;
    if (d.origen === "jefe") return "✍️ Lo pediste tú";
    return `🎙️ Narración · escena ${d.escena}`;
  }
  const seAplica = (d) => (d.estado === "no_confirmado" || (d.estado === "corregir" && d.frase_nueva)) && d.frase
    && !["pantalla", "grafica"].includes(d.origen) && d.tipo !== "fuente";

  function pasos(lista) {
    return `<div class="exp-pasos">${lista.map((p) => {
      const [ico, txt] = PASO[p.estado] || ["○", p.estado];
      const titulo = p.estado === "en_obra" ? `Llega en la parte ${p.parte} de la obra` : txt;
      return `<span class="exp-paso exp-paso-${esc(p.estado)}" title="${esc(titulo)}">${ico} ${esc(p.etiqueta)}</span>`;
    }).join('<i class="exp-flecha">→</i>')}</div>`;
  }
  const cuentas = (c) => `<span class="exp-cuentas">✅ ${c.confirmado || 0} · ⚠️ ${c.corregir || 0} · ❌ ${c.no_confirmado || 0}${c.no_es_dato ? ` · ➖ ${c.no_es_dato}` : ""}${c.pendiente ? ` · ⏳ ${c.pendiente}` : ""}</span>`;

  // ---------- la lista de expedientes ----------
  function pintarLista(r) {
    caja.innerHTML = `
      <section class="tarjeta exp-portada">
        <h4>🕵️ Expedientes · «¿Quién MATÓ a…?»</h4>
        <p class="pista">Sube el paquete de producción que armas con Claude (la página HTML o el ZIP). El equipo lo separa en brief,
          guion, publicación y fuentes, y el Detective Ramos revisa cada cifra contra sus fuentes antes de que grabes.
          Nada avanza sin tu OK y todo se sube en privado.</p>
        <label class="btn btn-primario">📥 Importar paquete (HTML o ZIP)<input type="file" id="exp-archivo" accept=".html,.htm,.zip" hidden></label>
        <p class="pista" id="exp-subiendo"></p>
        ${r.demo ? `<p class="pista">🧪 Modo demo: Ramos da resultados de ejemplo (no lee páginas ni usa Claude).</p>` : ""}
        <p class="pista">🧠 ${r.plan ? "Tu plan de Claude está conectado: el equipo trabaja sin costo por token."
          : "Tu plan de Claude no está conectado en el servidor: Ramos no puede trabajar hasta conectarlo (oficina.py --configurar-suscripcion) o hasta que prendas la casilla 💳."}</p>
        <label class="chk"><input type="checkbox" id="exp-api" ${r.ajustes.api ? "checked" : ""}> 💳 Si mi plan de Claude no responde, que el equipo use la API (cuesta centavos)</label>
      </section>
      ${r.expedientes.length ? r.expedientes.map((x) => `
        <div class="tarjeta exp-item" role="button" tabindex="0" data-abrir="${esc(x.id)}">
          <div class="cabeza"><h4>#${esc(x.numero)} · ${esc(x.marca)}</h4><span class="chip">${esc(VERIF[x.verificacion] || x.verificacion)}</span></div>
          <p>${esc(x.titulo)}</p>
          ${pasos(x.pasos)}
          <p class="pista">${cuentas(x.cuenta)}</p>
        </div>`).join("") : `<p class="vacio">Todavía no hay expedientes. Importa el paquete del primero.</p>`}`;
  }

  // ---------- un expediente ----------
  function tarjetaDato(d, corriendo) {
    const enEdicion = editando.has(d.id);
    const nueva = d.frase_nueva ? `<p class="exp-nueva">→ «${esc(d.frase_nueva)}»</p>`
      : seAplica(d) && d.estado === "no_confirmado" ? `<p class="exp-nueva exp-quita">→ Se quita la frase</p>` : "";
    return `<div class="exp-dato exp-${esc(d.estado)}${seAplica(d) && !d.usar ? " exp-original" : ""}" data-dato="${esc(d.id)}">
      <div class="exp-dato-cab"><b>${ICONO[d.estado] || "•"} ${esc(TXT[d.estado] || d.estado)}</b><small>${origen(d)}</small></div>
      <p class="exp-frase">«${esc(d.frase || d.dato)}»</p>
      ${d.origen === "grafica" ? `<p class="pista">${esc(d.dato)}</p>` : ""}
      ${nueva}
      ${d.explicacion ? `<p class="pista exp-explica">${esc(d.explicacion)}</p>` : ""}
      ${d.cita ? `<blockquote class="exp-cita">“${esc(d.cita)}”${d.url ? `<br><a href="${esc(d.url)}" target="_blank" rel="noopener">${esc(d.fuente || "Abrir la fuente")} ↗</a>` : ""}</blockquote>`
        : d.url ? `<p class="pista"><a href="${esc(d.url)}" target="_blank" rel="noopener">${esc(d.fuente || "Fuente")} ↗</a></p>`
        : d.fuente ? `<p class="pista">Fuente: ${esc(d.fuente)}</p>` : ""}
      ${d.nota_editor ? `<p class="exp-nota">🎬 ${esc(d.nota_editor)}</p>` : ""}
      ${d.a_mano ? `<p class="exp-nota">🔎 Revísalo tú: Ramos no lo pudo respaldar bien (lee la explicación), así que la frase no se toca hasta que decidas.</p>` : ""}
      ${enEdicion ? `<textarea rows="3" data-nueva="${esc(d.id)}">${esc(d.frase_nueva || d.frase)}</textarea>
        <div class="acciones"><button class="btn btn-mini btn-primario" data-guardar="${esc(d.id)}">💾 Guardar</button>
          <button class="btn btn-mini" data-cancelar="${esc(d.id)}">Cancelar</button></div>
        <p class="pista">No metas cifras que no estén en la frase original o en la fuente: no se aceptan.</p>` : `
      <div class="acciones">
        ${seAplica(d) ? `<label class="chk"><input type="checkbox" data-usar="${esc(d.id)}" ${d.usar ? "checked" : ""}> Aplicar el cambio</label>` : ""}
        ${d.frase && !["pantalla", "grafica"].includes(d.origen) && d.tipo !== "fuente" && d.estado !== "pendiente" ? `<button class="btn btn-mini" data-editar="${esc(d.id)}">✏️ Editar frase</button>` : ""}
        ${corriendo ? "" : `<button class="btn btn-mini" data-reverificar="${esc(d.id)}">🔁 Que Ramos lo revise otra vez</button>`}
      </div>`}
    </div>`;
  }

  function filtrar(datos) {
    if (filtro === "todos") return datos;
    if (filtro === "revisar") return datos.filter((d) => ["corregir", "no_confirmado"].includes(d.estado));
    if (filtro === "a_mano") return datos.filter((d) => d.a_mano);
    return datos.filter((d) => d.estado === filtro);
  }

  function reporte(x) {
    const v = x.verificacion, c = x.cuenta, corriendo = x.corriendo || v.estado === "trabajando";
    const textoEstado = {
      sin_empezar: "Ramos revisa la lista de datos por verificar y cada cifra del guion (narración, texto en pantalla y gráficas) contra las fuentes del paquete. Lee la página original; si no abre, busca en Google. Tarda unos minutos y usa tu plan de Claude.",
      trabajando: "Ramos está leyendo las fuentes y revisando. Puedes cerrar la pestaña: sigue solo y te avisa.",
      interrumpida: v.error || "Se interrumpió.",
      lista: "Te toca: revisa lo ⚠️ y ❌. Puedes editar la frase nueva o dejar la original (quita la palomita). Luego dale «✅ Aprobar cambios».",
      aprobada: "Aprobada ✅. La narración corregida y su PDF están listos: ya puedes grabar tu voz. Si cambias algo, vuelve a aprobar.",
      error: v.error || "Algo falló.",
    }[v.estado] || "";
    const av = v.avance || {};
    const porc = av.total ? Math.round((av.hechos || 0) / av.total * 100) : 0;
    const fuentes = v.fuentes || [];
    const abrieron = fuentes.filter((f) => f.ok).length;
    const lista = filtrar(x.datos);
    const grupos = new Map();
    for (const d of lista) {
      const g = d.origen === "grafica" ? "zz-graficas" : d.escena ? `e${String(d.escena).padStart(2, "0")}` : "zz-general";
      if (!grupos.has(g)) grupos.set(g, []);
      grupos.get(g).push(d);
    }
    const escenas = Object.fromEntries((x.paquete.escenas || []).map((e) => [e.n, e.titulo]));
    const titulo = (g) => g === "zz-graficas" ? "📊 Gráficas" : g === "zz-general" ? "📁 Del paquete en general"
      : `Escena ${Number(g.slice(1))} · ${esc(escenas[Number(g.slice(1))] || "")}`;
    const cuantos = (f) => (f === "todos" ? x.datos.length : f === "revisar" ? (c.corregir || 0) + (c.no_confirmado || 0)
      : f === "a_mano" ? x.datos.filter((d) => d.a_mano).length : c[f] || 0);
    return `<section class="tarjeta exp-verif">
      <div class="cabeza"><h4>🔎 Verificación · Detective Ramos</h4><span class="chip exp-v-${esc(v.estado)}">${esc(VERIF[v.estado] || v.estado)}</span></div>
      <p class="pista">${esc(textoEstado)}</p>
      ${v.nota ? `<p class="exp-nota">${esc(v.nota)}</p>` : ""}
      <p>${cuentas(c)}</p>
      ${corriendo ? `<p class="pista">▶ ${esc(av.paso || "Trabajando…")}${av.total ? ` · ${av.hechos || 0} de ${av.total}` : ""}</p>
        <div class="exp-barra"><b style="width:${Math.max(4, porc)}%"></b></div>` : ""}
      <div class="acciones">
        ${!corriendo && ["sin_empezar", "interrumpida", "error"].includes(v.estado) ? `<button class="btn btn-primario" data-accion="verificar">🔎 ${v.estado === "sin_empezar" ? "Verificar" : "Seguir verificando"}</button>` : ""}
        ${!corriendo && ["lista", "aprobada"].includes(v.estado) && c.pendiente ? `<button class="btn" data-accion="verificar">🔎 Revisar los ${c.pendiente} que faltan</button>` : ""}
        ${!corriendo && v.estado === "lista" ? `<button class="btn btn-primario" data-accion="aprobar">✅ Aprobar cambios</button>` : ""}
        ${!corriendo && ["lista", "aprobada"].includes(v.estado) ? `<button class="btn" data-accion="rehacer">🔁 Revisar todo otra vez</button>` : ""}
        ${x.archivos["narracion-corregida.pdf"] ? `<a class="btn" href="/expedientes/${esc(x.paquete.id)}/narracion-corregida.pdf" target="_blank" rel="noopener">📄 PDF para leer en el cel</a>
          <a class="btn btn-mini" href="/expedientes/${esc(x.paquete.id)}/02-narracion-corregida.md" target="_blank" rel="noopener">📝 Narración (.md)</a>` : ""}
      </div>
      ${(v.fallidos || []).length ? `<p class="exp-nota">⚠️ ${v.fallidos.length} cambios no se pudieron aplicar (la frase ya no está igual): ${v.fallidos.map((f) => `«${esc(f.antes)}»`).join(", ")}</p>` : ""}
      ${fuentes.length ? `<details><summary>📚 Fuentes: ${abrieron} de ${fuentes.length} abrieron${v.busquedas ? ` · ${v.busquedas} búsquedas en Google` : ""}</summary>
        <ul class="exp-fuentes">${fuentes.map((f) => `<li>${f.ok ? "✅" : "❌"} <a href="${esc(f.url)}" target="_blank" rel="noopener">${esc(f.nombre || f.url)}</a>${f.ok ? "" : ` <small class="pista">${esc(f.error)}</small>`}</li>`).join("")}</ul></details>` : ""}
      <div class="exp-filtros">${FILTROS.map(([k, t]) => `<button class="btn btn-mini ${filtro === k ? "btn-primario" : ""}" data-filtro="${k}">${t} (${cuantos(k)})</button>`).join("")}</div>
      ${lista.length ? [...grupos.keys()].sort().map((g) => `<h5 class="exp-grupo">${titulo(g)}</h5>${grupos.get(g).map((d) => tarjetaDato(d, corriendo)).join("")}`).join("")
        : `<p class="vacio">${filtro === "revisar" ? (v.estado === "sin_empezar" ? "Dale «Verificar» para empezar." : "Nada por decidir aquí. 🎉") : "Nada en este filtro."}</p>`}
    </section>`;
  }

  function chat(x) {
    const nombres = Object.fromEntries((window.Oficina?.equipoExp?.() || []).map((a) => [a.id, a.nombre]));
    const esperando = x.chat.length && x.chat[x.chat.length - 1].quien === "jefe";
    return `<section class="tarjeta">
      <h4>💬 Chat con el equipo</h4>
      <p class="pista">Pídeles cambios como a personas: «Ramos, la frase de la isla déjala como estaba», «Nico, en la G5 el contador más lento».
        Lo que todavía no pueden hacer lo dejan anotado para cuando arranquen.</p>
      <ol class="chat-sala exp-chat">${x.chat.map((m) => `<li class="${m.quien === "jefe" ? "mio" : ""}"><small>${esc(m.quien === "jefe" ? "Tú" : nombres[m.quien] || m.quien)} · ${hora(m.t)}</small><span>${esc(m.texto)}</span></li>`).join("")
        || `<li class="vacio">Todavía no hay mensajes.</li>`}${esperando ? `<li class="vacio">✍️ El equipo está contestando…</li>` : ""}</ol>
      <form class="fila chat-escribir" id="exp-chat-form"><textarea id="exp-chat-texto" rows="2" maxlength="1500" placeholder="Escríbele al equipo…">${esc(leer(`exp_chat_${x.paquete.id}`, ""))}</textarea>
        <button class="btn btn-primario" type="submit">Enviar</button></form>
      ${x.notas.length ? `<details><summary>📌 Notas para el equipo (${x.notas.length})</summary><ul>${x.notas.map((n) => `<li><b>${esc(nombres[n.para] || n.para)}:</b> ${esc(n.texto)}</li>`).join("")}</ul></details>` : ""}
    </section>`;
  }

  function paqueteInfo(x) {
    const p = x.paquete, b = p.brief, pub = p.publicacion, id = esc(p.id);
    const partes = ["00-BRIEF-agentes.md", "01-guion-tecnico.md", "02-narracion.md", "03-publicacion.md", "04-fuentes.md"].filter((n) => x.archivos[n]);
    return `<section class="tarjeta">
      <h4>📦 El paquete</h4>
      <p class="pista">${p.escenas.length} escenas · ${p.palabras.toLocaleString("es-MX")} palabras (≈${Math.round(p.palabras / 150)} min de voz) · ${b.graficas.length} gráficas · ${b.tomas.length} tomas tuyas · ${pub.shorts.length} Shorts · ${p.fuentes.enlaces.length} fuentes</p>
      <p>${partes.map((n) => `<a class="btn btn-mini" href="/expedientes/${id}/${n}" target="_blank" rel="noopener">${esc(n)}</a>`).join(" ")}</p>
      <details><summary>🎬 Escenas</summary><ol class="exp-lista">${p.escenas.map((e) => `<li><b>${esc(e.titulo)}</b> <small class="pista">${e.palabras} palabras${e.empieza_estimado ? ` · empieza ≈ ${esc(e.empieza_estimado)}` : ""} · graba escena-${String(e.n).padStart(2, "0")}.wav</small></li>`).join("")}</ol></details>
      <details><summary>📊 Gráficas (${b.graficas.length})</summary><ul class="exp-lista">${b.graficas.map((g) => `<li><b>${esc(g.id)} · ${esc(g.nombre)}</b>: ${esc(g.datos)} <small class="pista">(escenas ${esc(g.escenas.join(", "))})</small></li>`).join("")}</ul>
        ${b.colores?.length ? `<p class="exp-colores">${b.colores.map((c) => `<span style="--c:${esc(c)}">${esc(c)}</span>`).join("")}</p>` : ""}</details>
      <details><summary>🎥 Tomas que grabas tú (${b.tomas.length})</summary><ul class="exp-lista">${b.tomas.map((t) => `<li><b>${esc(t.id)}</b> ${esc(t.toma)} <small class="pista">(escenas ${esc(t.escenas.join(", "))})${t.notas ? ` · ${esc(t.notas)}` : ""}</small></li>`).join("")}</ul></details>
      <details><summary>📤 Publicación</summary>
        <p><b>Título:</b> ${esc(p.titulo)}</p>
        <ul class="exp-lista">${pub.miniaturas.map((m) => `<li><b>Miniatura ${esc(m.letra)}${m.recomendada ? " ⭐" : ""}</b>: ${esc(m.concepto)} <i>${esc(m.texto)}</i></li>`).join("")}</ul>
        <p><b>Shorts</b></p><ul class="exp-lista">${pub.shorts.map((s) => `<li><b>${esc(s.id)}</b> «${esc(s.gancho)}» <small class="pista">${esc(s.de_donde)} · ${esc(s.texto)}</small></li>`).join("")}</ul>
        <p class="pista">${pub.capitulos.length} capítulos (se ajustan a los tiempos reales al editar) · ${pub.etiquetas.length} etiquetas</p></details>
      ${(p.avisos || []).length ? `<p class="exp-nota">${p.avisos.map(esc).join("<br>")}</p>` : ""}
    </section>`;
  }

  function pintarDetalle(x) {
    datosVista = x;
    const p = x.paquete;
    caja.innerHTML = `
      <button class="btn btn-mini volver" data-volver>← Todos los expedientes</button>
      <section class="tarjeta exp-cabeza">
        <div class="cabeza"><h4>${esc(p.titulo)}</h4><span class="chip">#${esc(p.numero)}</span></div>
        ${pasos(x.pasos)}
        <p class="pista">Los pasos con 🚧 llegan en las siguientes partes de la obra. ${x.costo ? `Gasto: $${x.costo.toFixed(3)} USD (búsquedas).` : ""}</p>
      </section>
      ${reporte(x)}
      <section class="tarjeta"><h4>📋 Lista final antes de subir</h4>
        ${x.checklist.length ? x.checklist.map((c) => `<label class="chk exp-check"><input type="checkbox" data-check="${c.i}" ${c.hecho ? "checked" : ""} ${c.auto ? "disabled" : ""}> ${esc(c.texto)}${c.auto ? ' <small class="pista">(automático)</small>' : ""}</label>`).join("")
          : `<p class="vacio">El paquete no trae la lista final.</p>`}
      </section>
      ${chat(x)}
      ${paqueteInfo(x)}
      <p><button class="btn btn-mini btn-no" data-borrar>🗑️ Borrar este expediente</button></p>`;
    const ol = caja.querySelector(".exp-chat");
    if (ol) ol.scrollTop = ol.scrollHeight;
  }

  async function pintar(forzar = false) {
    if ($("#tab-expedientes").hidden) return;
    const activo = document.activeElement;
    if (!forzar && activo?.closest?.("#expedientes") && activo.matches("textarea, input:not([type=checkbox]), select")) return;
    let r;
    const pedida = vista;
    try { r = await api(vista ? `/api/expedientes/${encodeURIComponent(vista)}` : "/api/expedientes"); } catch (err) {
      if (vista) { vista = null; guardar("exp_vista", null); return pintar(true); }
      caja.innerHTML = `<p class="error">${esc(err.message)}</p>`;
      return;
    }
    if (pedida !== vista) return; // mientras llegaba, abriste otro caso (o regresaste a la lista)
    const clave = JSON.stringify(r) + filtro + [...editando].join(",");
    if (!forzar && clave === ultimo) return;
    ultimo = clave;
    const panel = $("#tab-expedientes"), arriba = panel.scrollTop;
    if (vista) pintarDetalle(r); else pintarLista(r);
    panel.scrollTop = arriba;
  }

  async function accion(datos, boton) {
    if (boton) { boton.disabled = true; }
    try {
      const r = await api(`/api/expedientes/${encodeURIComponent(vista)}`, datos);
      if (r.confirmar) {
        if (confirm(`${r.error}\n\n¿Aprobar así de todos modos?`)) await api(`/api/expedientes/${encodeURIComponent(vista)}`, { ...datos, forzar: true });
      }
      return r;
    } catch (err) { alert(err.message); } finally { pintar(true); }
  }

  function importar(archivo) {
    const aviso = $("#exp-subiendo");
    if (archivo.size > 25 * 1024 * 1024) return alert("El paquete pesa demasiado (máx. 25 MB).");
    const x = new XMLHttpRequest();
    x.open("POST", `/api/expedientes/importar?nombre=${encodeURIComponent(archivo.name)}`);
    x.setRequestHeader("Content-Type", "application/octet-stream");
    x.upload.onprogress = (e) => { if (aviso && e.lengthComputable) aviso.textContent = `Subiendo… ${Math.round(e.loaded / e.total * 100)}%`; };
    x.onload = () => {
      let j = {};
      try { j = JSON.parse(x.responseText); } catch { /* respuesta vacía */ }
      if (x.status !== 200) { if (aviso) aviso.textContent = ""; return alert(j.error || "No se pudo importar el paquete."); }
      if (j.avisos?.length) alert("Importado, con avisos:\n\n" + j.avisos.join("\n"));
      vista = j.id; guardar("exp_vista", vista); pintar(true);
    };
    x.onerror = () => alert("Se cortó la subida. Inténtalo otra vez.");
    if (aviso) aviso.textContent = "Subiendo…";
    x.send(archivo);
  }

  caja.addEventListener("change", async (e) => {
    const t = e.target;
    if (t.id === "exp-archivo" && t.files[0]) return importar(t.files[0]);
    if (t.id === "exp-api") {
      if (t.checked && !confirm("Con esto, si tu plan de Claude no responde, el equipo de Expedientes usa la API y cuesta centavos. ¿Prenderlo?")) { t.checked = false; return; }
      try { await api("/api/expedientes/ajustes", { api: t.checked }); } catch (err) { alert(err.message); }
      return pintar(true);
    }
    if (t.dataset.usar) return accion({ accion: "usar", dato: t.dataset.usar, usar: t.checked });
    if (t.dataset.check) return accion({ accion: "check", i: Number(t.dataset.check), hecho: t.checked });
  });

  caja.addEventListener("input", (e) => {
    if (e.target.id === "exp-chat-texto" && vista) guardar(`exp_chat_${vista}`, e.target.value);
  });

  caja.addEventListener("click", async (e) => {
    const t = e.target.closest("button, [data-abrir]");
    if (!t) return;
    if (t.dataset.abrir) { vista = t.dataset.abrir; guardar("exp_vista", vista); return pintar(true); }
    if (t.hasAttribute("data-volver")) { vista = null; guardar("exp_vista", null); editando.clear(); return pintar(true); }
    if (t.dataset.filtro) { filtro = t.dataset.filtro; guardar("exp_filtro", filtro); return pintar(true); }
    if (t.dataset.editar) { editando.add(t.dataset.editar); await pintar(true); caja.querySelector(`[data-nueva="${t.dataset.editar}"]`)?.focus(); return; }
    if (t.dataset.cancelar) { editando.delete(t.dataset.cancelar); return pintar(true); }
    if (t.dataset.guardar) {
      const texto = caja.querySelector(`[data-nueva="${t.dataset.guardar}"]`)?.value ?? "";
      t.disabled = true;
      try {
        await api(`/api/expedientes/${encodeURIComponent(vista)}`, { accion: "editar", dato: t.dataset.guardar, frase_nueva: texto });
        editando.delete(t.dataset.guardar);
      } catch (err) { alert(err.message); t.disabled = false; return; }
      return pintar(true);
    }
    if (t.dataset.reverificar) return accion({ accion: "reverificar", dato: t.dataset.reverificar }, t);
    if (t.hasAttribute("data-borrar")) {
      if (!confirm("¿Borrar este expediente con todo lo que lleva (reporte, narración, chat)? Lo puedes volver a importar después.")) return;
      try { await api(`/api/expedientes/${encodeURIComponent(vista)}`, { accion: "borrar" }); } catch (err) { return alert(err.message); }
      vista = null; guardar("exp_vista", null); return pintar(true);
    }
    const a = t.dataset.accion;
    if (a === "verificar") return accion({ accion: "verificar" }, t);
    if (a === "rehacer") {
      if (!confirm("Ramos vuelve a revisar todo (menos lo que ya se verificó en el chat). Tus ediciones a mano se pueden perder. ¿Seguro?")) return;
      return accion({ accion: "verificar", rehacer: true }, t);
    }
    if (a === "aprobar") {
      const x = datosVista, c = x?.cuenta || {};
      const usar = (x?.datos || []).filter((d) => seAplica(d) && d.usar).length;
      if (!confirm(`Se aplican ${usar} cambios a la narración y se arma el PDF para que grabes.\n✅ ${c.confirmado || 0} · ⚠️ ${c.corregir || 0} · ❌ ${c.no_confirmado || 0}\n\n¿Aprobar?`)) return;
      return accion({ accion: "aprobar" }, t);
    }
  });

  caja.addEventListener("keydown", (e) => {
    const t = e.target.closest?.("[data-abrir]");
    if (t && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); t.click(); }
  });

  caja.addEventListener("submit", async (e) => {
    if (e.target.id !== "exp-chat-form") return;
    e.preventDefault();
    const area = $("#exp-chat-texto"), texto = area.value.trim();
    if (!texto) return;
    const boton = e.target.querySelector("button");
    boton.disabled = true;
    try {
      await api(`/api/expedientes/${encodeURIComponent(vista)}`, { accion: "chat", texto });
      guardar(`exp_chat_${vista}`, null);
      area.value = "";
      area.blur();
    } catch (err) { alert(err.message); }
    boton.disabled = false;
    pintar(true);
  });

  window.addEventListener("pestana", (e) => { if (e.detail === "expedientes") pintar(true); });
  // 🕵️ desde la Bandeja o el Chat de la agencia: abrir un caso directo
  window.addEventListener("exp-abrir", (e) => { vista = e.detail || null; guardar("exp_vista", vista); ultimo = ""; pintar(true); });
  let vuelta = 0;
  setInterval(() => { // cada 3 s si alguien del equipo trabaja; si no, cada 12 s
    if (document.hidden) return;
    const vivo = datosVista && vista && (datosVista.corriendo || datosVista.chat?.at(-1)?.quien === "jefe");
    if (vivo || ++vuelta % 4 === 0) pintar();
  }, 3000);
  pintar(true);
})();
