// 🧭 Menú de oficinas: una barra a la izquierda (abajo en el cel) para brincar entre todas tus oficinas.
// Cada oficina vive en su propia página; agrega aquí las nuevas.
(() => {
  if (window.self !== window.top) { // dentro de la sala central: sin menú ni encabezado repetidos
    const e = document.createElement("style");
    e.textContent = "header.barra { display: none !important; }";
    document.head.appendChild(e);
    return;
  }
  const OFICINAS = [
    { url: "/", ico: "🏢", nombre: "Edificio", sub: "YouTube y tu despacho" },
    { url: "/director", ico: "🎯", nombre: "Director", sub: "Prioridades, enfoque e informe" },
    { url: "/edicion", ico: "🎬", nombre: "Sala central", sub: "Edición: compus y servidor" },
    { url: "/expedientes", ico: "🕵️", nombre: "Expedientes", sub: "¿Quién MATÓ a…?" },
    { url: "/tiktok-shop", ico: "🛒", nombre: "TikTok Shop", sub: "Guiones y tomas" },
    { url: "/tampico", ico: "🌮", nombre: "Tampiqueando", sub: "Foodie de Tampico" },
  ];
  const aqui = location.pathname.replace(/\/+$/, "") || "/";
  // la misma app del edificio sirve TikTok Shop: que el título diga en qué oficina estás
  const titulos = { tiktok: ["🛒", "TikTok Shop"], sala: ["🎬", "Cuarto de edición"] };
  const t = titulos[document.body?.dataset.oficina];
  if (t) {
    document.title = t[1];
    const n = document.getElementById("nombre-oficina"), logo = document.querySelector(".marca .logo");
    if (n) n.textContent = t[1];
    if (logo) logo.textContent = t[0];
  }
  const css = `
  :root { --nav-ancho: 76px; }
  body { padding-left: var(--nav-ancho) !important; }
  .nav-oficinas { position: fixed; z-index: 50; left: 0; top: 0; bottom: 0; width: var(--nav-ancho); background: #0b0d12;
    border-right: 1px solid #262b36; display: flex; flex-direction: column; gap: 4px; padding: max(10px, env(safe-area-inset-top, 0px)) 6px 10px max(6px, env(safe-area-inset-left, 0px));
    font: 500 11px/1.2 Inter, system-ui, sans-serif; color-scheme: dark; }
  .nav-oficinas a { position: relative; display: flex; flex-direction: column; align-items: center; gap: 3px; padding: 9px 2px; border-radius: 12px;
    color: #9aa4b2; text-decoration: none; text-align: center; transition: background .15s, color .15s; }
  .nav-oficinas a span.ico { font-size: 22px; line-height: 1; }
  .nav-oficinas a:hover, .nav-oficinas a:focus-visible { background: #171b24; color: #fff; outline: none; }
  .nav-oficinas a.aqui { background: #1d2535; color: #fff; box-shadow: inset 3px 0 0 #ffd23f; }
  .nav-oficinas a .tip { position: absolute; left: calc(100% + 8px); top: 50%; transform: translateY(-50%); white-space: nowrap; background: #11151d;
    border: 1px solid #2b3240; color: #e8edf3; padding: 6px 9px; border-radius: 8px; font-size: 12px; pointer-events: none; opacity: 0; transition: opacity .12s; }
  .nav-oficinas a .tip small { display: block; color: #8b97a6; font-size: 11px; }
  .nav-oficinas a:hover .tip { opacity: 1; }
  @media (max-width: 760px) {
    body { padding-left: 0 !important; padding-bottom: calc(64px + env(safe-area-inset-bottom, 0px)) !important; }
    .nav-oficinas { top: auto; right: 0; width: auto; height: calc(62px + env(safe-area-inset-bottom, 0px)); flex-direction: row;
      justify-content: space-around; border-right: 0; border-top: 1px solid #262b36;
      padding: 4px max(6px, env(safe-area-inset-right, 0px)) env(safe-area-inset-bottom, 0px) max(6px, env(safe-area-inset-left, 0px)); }
    .nav-oficinas a { flex: 1; padding: 6px 2px; font-size: 10px; }
    .nav-oficinas a.aqui { box-shadow: inset 0 3px 0 #ffd23f; }
    .nav-oficinas a .tip { display: none; }
  }
  @media (prefers-reduced-motion: reduce) { .nav-oficinas a, .nav-oficinas a .tip { transition: none; } }`;
  const estilo = document.createElement("style");
  estilo.textContent = css;
  document.head.appendChild(estilo);
  const nav = document.createElement("nav");
  nav.className = "nav-oficinas";
  nav.setAttribute("aria-label", "Tus oficinas");
  nav.innerHTML = OFICINAS.map((o) => {
    const activa = o.url === aqui;
    return `<a href="${o.url}" class="${activa ? "aqui" : ""}" ${activa ? 'aria-current="page"' : ""}>
      <span class="ico" aria-hidden="true">${o.ico}</span>${o.nombre.split(" ")[0]}
      <span class="tip">${o.nombre}<small>${o.sub}</small></span></a>`;
  }).join("");
  const poner = () => document.body.prepend(nav);
  if (document.body) poner(); else document.addEventListener("DOMContentLoaded", poner);
})();
