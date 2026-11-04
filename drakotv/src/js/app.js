// DrakoTV - interfaz principal.
'use strict';

// ======================================================================
// Estado
// ======================================================================
const DEFAULT_SETTINGS = {
  liveFormat: 'm3u8', userAgent: '', externalPlayer: '', bufferSec: 30, timeoutSec: 25,
  aspect: 'contain', volume: 1, muted: false, autoplayNext: true, refreshHours: 24, epgOffsetMin: 0,
  parental: { enabled: true, pin: '0000', locked: {} },
};
const ADULT_RE = /(adult|xxx|\+ ?18|18 ?\+|porn|erotic|for adults|adultos|caliente|hot ?club)/i;

const FREE_LISTS = [
  { name: 'México', url: 'https://iptv-org.github.io/iptv/countries/mx.m3u' },
  { name: 'En español (todos los países)', url: 'https://iptv-org.github.io/iptv/languages/spa.m3u' },
  { name: 'España', url: 'https://iptv-org.github.io/iptv/countries/es.m3u' },
  { name: 'Argentina', url: 'https://iptv-org.github.io/iptv/countries/ar.m3u' },
  { name: 'Colombia', url: 'https://iptv-org.github.io/iptv/countries/co.m3u' },
  { name: 'Chile', url: 'https://iptv-org.github.io/iptv/countries/cl.m3u' },
  { name: 'Perú', url: 'https://iptv-org.github.io/iptv/countries/pe.m3u' },
  { name: 'Estados Unidos', url: 'https://iptv-org.github.io/iptv/countries/us.m3u' },
  { name: 'Noticias (mundial)', url: 'https://iptv-org.github.io/iptv/categories/news.m3u' },
  { name: 'Deportes (mundial)', url: 'https://iptv-org.github.io/iptv/categories/sports.m3u' },
  { name: 'Infantil (mundial)', url: 'https://iptv-org.github.io/iptv/categories/kids.m3u' },
  { name: 'Música (mundial)', url: 'https://iptv-org.github.io/iptv/categories/music.m3u' },
  { name: 'Todo el mundo (+10,000 canales)', url: 'https://iptv-org.github.io/iptv/index.m3u' },
];

const S = {
  data: { sources: [], activeId: null, favorites: {}, history: {}, settings: { ...DEFAULT_SETTINGS } },
  src: null,          // fuente activa
  cat: null,          // catalogo de la fuente activa
  catAt: 0,
  epg: null,          // { programmes, byName }
  epgState: 'none',   // none | loading | ok | error
  view: 'home',
  unlocked: false,    // control parental desbloqueado en esta sesion
  playing: null,      // { type, item, ... }
  live: { cat: '__all', filter: '', sel: 0, list: [] },
  vod: { movie: { cat: '__all', filter: '', sort: 'added' }, series: { cat: '__all', filter: '', sort: 'added' } },
  guide: { cat: null },
  search: '',
  loading: false,
};
const settings = () => S.data.settings;
const save = (key) => window.api.store.set(key, S.data[key]);

// ======================================================================
// Utilidades
// ======================================================================
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const h = (html) => { const t = document.createElement('template'); t.innerHTML = html.trim(); return t.content.firstElementChild; };
const norm = (s) => String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
const normName = (s) => norm(s).replace(/\b(hd|fhd|uhd|sd|4k|hevc|h265|\d{3,4}p)\b/g, '').replace(/[^a-z0-9]/g, '');
const hhmm = (ms) => new Date(ms).toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit' });
const initials = (s) => (String(s || '?').replace(/[^\p{L}\p{N} ]/gu, '').trim().split(/\s+/).slice(0, 2).map((w) => w[0]).join('') || '?').toUpperCase();
const debounce = (fn, ms) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };
const plural = (n, a, b) => `${n.toLocaleString('es-MX')} ${n === 1 ? a : b}`;
const uid = () => Date.now().toString(36) + Math.random().toString(36).slice(2, 7);

function toast(msg, type = '') {
  const el = $('#toast');
  const t = h(`<div class="toast ${type}">${esc(msg)}</div>`);
  el.appendChild(t);
  setTimeout(() => t.classList.add('out'), 3200);
  setTimeout(() => t.remove(), 3600);
}

function modal(html, { wide = false, onClose } = {}) {
  const root = $('#modal-root');
  const m = h(`<div class="modal-bg"><div class="modal ${wide ? 'wide' : ''}" role="dialog" aria-modal="true">
    <button class="icon-btn modal-x" data-close title="Cerrar (Esc)">${ICONS.close}</button>${html}</div></div>`);
  const close = () => { m.remove(); if (onClose) onClose(); };
  m.addEventListener('mousedown', (e) => { if (e.target === m) close(); });
  m.addEventListener('click', (e) => { if (e.target.closest('[data-close]')) close(); });
  m.close = close;
  root.appendChild(m);
  const f = m.querySelector('[autofocus]');
  if (f) setTimeout(() => f.focus(), 30);
  return m;
}
const topModal = () => $$('#modal-root .modal-bg').pop();

function askPin(title = 'Control parental') {
  return new Promise((resolve) => {
    let done = false;
    const m = modal(`<h2>${esc(title)}</h2><p class="muted">Escribe tu PIN para continuar.</p>
      <form class="pin-form"><input class="input pin" type="password" inputmode="numeric" maxlength="8" autofocus placeholder="PIN">
      <div class="row end"><button type="button" class="btn ghost" data-close>Cancelar</button><button class="btn primary">Aceptar</button></div></form>`,
    { onClose: () => { if (!done) resolve(false); } });
    $('form', m).addEventListener('submit', (e) => {
      e.preventDefault();
      if ($('input', m).value === settings().parental.pin) { done = true; S.unlocked = true; m.close(); resolve(true); }
      else { $('input', m).value = ''; $('input', m).classList.add('shake'); setTimeout(() => $('input', m).classList.remove('shake'), 400); toast('PIN incorrecto', 'err'); }
    });
  });
}

function confirmBox(msg, okLabel = 'Aceptar', danger = false) {
  return new Promise((resolve) => {
    let done = false;
    const m = modal(`<h2>Confirmar</h2><p>${esc(msg)}</p><div class="row end">
      <button class="btn ghost" data-close>Cancelar</button><button class="btn ${danger ? 'danger' : 'primary'}" data-ok>${esc(okLabel)}</button></div>`,
    { onClose: () => { if (!done) resolve(false); } });
    $('[data-ok]', m).addEventListener('click', () => { done = true; m.close(); resolve(true); });
  });
}

// Lista virtual: solo dibuja las filas visibles (para listas de miles de canales).
function vlist(container, items, rowH, renderRow) {
  container.classList.add('vlist');
  container.innerHTML = '';
  const pad = document.createElement('div');
  pad.className = 'vl-pad';
  pad.style.height = items.length * rowH + 'px';
  container.appendChild(pad);
  let last = '';
  const draw = (force) => {
    const top = container.scrollTop, hgt = container.clientHeight || 600;
    const start = Math.max(0, Math.floor(top / rowH) - 6);
    const end = Math.min(items.length, Math.ceil((top + hgt) / rowH) + 6);
    const key = start + ':' + end;
    if (!force && key === last) return;
    last = key;
    let html = '';
    for (let i = start; i < end; i++) html += renderRow(items[i], i, `top:${i * rowH}px;height:${rowH}px`);
    pad.innerHTML = html;
  };
  container.onscroll = () => draw();
  draw(true);
  return {
    refresh: () => draw(true),
    scrollTo(i) {
      const top = i * rowH, hgt = container.clientHeight;
      if (top < container.scrollTop) container.scrollTop = top;
      else if (top + rowH > container.scrollTop + hgt) container.scrollTop = top + rowH - hgt;
      draw(true);
    },
  };
}

// Rejilla con carga progresiva (posters).
function pagedGrid(container, items, renderCard, page = 90) {
  container.innerHTML = '';
  let shown = 0;
  const sentinel = h('<div class="grid-sentinel"></div>');
  const more = () => {
    const chunk = items.slice(shown, shown + page);
    shown += chunk.length;
    sentinel.insertAdjacentHTML('beforebegin', chunk.map(renderCard).join(''));
    if (shown >= items.length) { io.disconnect(); sentinel.remove(); }
  };
  const io = new IntersectionObserver((en) => { if (en[0].isIntersecting) more(); }, { rootMargin: '800px' });
  container.appendChild(sentinel);
  more();
  if (shown < items.length) io.observe(sentinel);
}

document.addEventListener('error', (e) => {
  if (e.target && e.target.tagName === 'IMG') e.target.classList.add('broken');
}, true);

// ======================================================================
// Control parental, favoritos e historial
// ======================================================================
function catById(type, id) { return S.cat && S.cat[type].cats.find((c) => c.id === id); }
function isCatLocked(type, cat) {
  const p = settings().parental;
  if (!p.enabled || !cat) return false;
  const k = `${S.src.id}|${type}|${cat.id}`;
  return p.locked[k] ?? ADULT_RE.test(cat.name);
}
function lockedCatIds(type) {
  if (!S.cat || S.unlocked) return new Set();
  return new Set(S.cat[type].cats.filter((c) => isCatLocked(type, c)).map((c) => c.id));
}
function visibleItems(type) {
  const locked = lockedCatIds(type);
  return locked.size ? S.cat[type].items.filter((i) => !locked.has(i.cat)) : S.cat[type].items;
}

const favKey = (type, id, srcId = S.src.id) => `${srcId}|${type}|${id}`;
const isFav = (type, item) => !!S.data.favorites[favKey(type, item.id)];
function snapshot(type, item) {
  const { episodes, ...rest } = item; // no guardamos todos los episodios de listas M3U
  return type === 'series' && episodes ? { ...rest, m3u: true } : rest;
}
function toggleFav(type, item) {
  const k = favKey(type, item.id);
  if (S.data.favorites[k]) { delete S.data.favorites[k]; toast('Quitado de favoritos'); }
  else { S.data.favorites[k] = { type, srcId: S.src.id, at: Date.now(), item: snapshot(type, item) }; toast('Agregado a favoritos'); }
  save('favorites');
  return !!S.data.favorites[k];
}
function favList(type) {
  return Object.values(S.data.favorites)
    .filter((f) => f.srcId === S.src.id && f.type === type)
    .sort((a, b) => b.at - a.at)
    .map((f) => resolveItem(type, f.item));
}
// usa la version actual del catalogo si existe (por si cambio la URL o el logo)
function resolveItem(type, snap) {
  if (!S.cat) return snap;
  return S.cat[type].items.find((i) => i.id === snap.id) || snap;
}

const histKey = (type, id) => `${S.src.id}|${type}|${id}`;
function hist(type, id) { return S.data.history[histKey(type, id)]; }
const saveHistory = debounce(() => save('history'), 800);
function putHistory(type, id, val) {
  S.data.history[histKey(type, id)] = { ...val, srcId: S.src.id, type, at: Date.now() };
  const keys = Object.keys(S.data.history);
  if (keys.length > 600) {
    keys.sort((a, b) => S.data.history[a].at - S.data.history[b].at).slice(0, keys.length - 600)
      .forEach((k) => delete S.data.history[k]);
  }
  saveHistory();
}
function historyList(types) {
  return Object.values(S.data.history)
    .filter((x) => x.srcId === S.src.id && types.includes(x.type))
    .sort((a, b) => b.at - a.at);
}
function continueList() {
  return historyList(['movie', 'series']).filter((x) => {
    if (x.done) return false;
    const pos = x.pos || 0, dur = x.dur || 0;
    return pos > 20 && (!dur || pos < dur - 90);
  });
}
const progressPct = (x) => (x && x.dur ? Math.min(100, (x.pos / x.dur) * 100) : 0);

// ======================================================================
// Carga de fuentes y guia
// ======================================================================
function setStatus(msg) {
  const el = $('#src-status');
  el.textContent = msg || '';
  el.classList.toggle('busy', !!msg);
}

async function activateSource(id, { force = false } = {}) {
  stopPlayback();
  const src = S.data.sources.find((s) => s.id === id);
  if (!src) return;
  S.src = src;
  S.data.activeId = id;
  save('activeId');
  S.cat = null; S.epg = null; S.epgState = 'none'; S.unlocked = false;
  S.live = { cat: '__all', filter: '', sel: 0, list: [] };
  S.vod.movie.cat = '__all'; S.vod.series.cat = '__all';
  renderSourceSwitch();

  const cached = force ? null : await window.api.cache.get(`${id}-catalog`);
  if (cached && cached.catalog) {
    S.cat = cached.catalog; S.catAt = cached.at;
    render();
    loadEpg();
    const maxAge = (settings().refreshHours || 24) * 3600e3;
    if (Date.now() - cached.at > maxAge) refreshCatalog(true);
    return;
  }
  await refreshCatalog(false);
}

async function refreshCatalog(background) {
  const src = S.src;
  if (!src || S.loading) return;
  S.loading = true;
  if (!background) renderLoading('Cargando contenido...');
  try {
    if (src.type === 'm3u-file' && !src.content) {
      const f = await window.api.cache.get(`${src.id}-file`);
      src.content = f && f.text;
      if (!src.content) throw new Error('No se encontró el archivo de la lista. Vuelve a agregarlo.');
    }
    const cat = await Sources.buildCatalog(src, (m) => { setStatus(m); if (!background) renderLoading(m); });
    if (src.type === 'm3u-file') delete src.content;
    if (S.src !== src) return;
    S.cat = cat; S.catAt = Date.now();
    await window.api.cache.set(`${src.id}-catalog`, { at: S.catAt, catalog: cat });
    if (cat.account) { src.account = cat.account; save('sources'); }
    setStatus('');
    if (background) toast('Contenido actualizado');
    render();
    loadEpg(true);
  } catch (e) {
    setStatus('');
    if (src.type === 'm3u-file') delete src.content;
    if (background) toast('No se pudo actualizar: ' + cleanErr(e), 'err');
    else renderError(cleanErr(e));
  } finally {
    S.loading = false;
  }
}
const cleanErr = (e) => String((e && e.message) || e).replace(/^Error invoking remote method '[^']+': (Error: )?/, '');

async function loadEpg(force = false) {
  const src = S.src;
  const url = (src.epgUrl || '').trim() || (S.cat && S.cat.header && S.cat.header.epgUrl) || '';
  if (!url || !S.cat || !S.cat.live.items.length) { S.epgState = 'none'; return; }
  S.epgState = 'loading';
  setStatus('Cargando guía de programación...');
  try {
    const epg = await window.api.epg.load(url, src.id, 6 * 3600e3, force);
    if (S.src !== src) return;
    const byName = {};
    for (const [id, c] of Object.entries(epg.channels || {})) {
      const n = normName(c.name);
      if (n && !byName[n]) byName[n] = id;
      const n2 = normName(id.replace(/\.[a-z]{2}$/i, ''));
      if (n2 && !byName[n2]) byName[n2] = id;
    }
    S.epg = { programmes: epg.programmes || {}, byName };
    S.epgState = 'ok';
    epgCache.clear();
    setStatus('');
    if (['live', 'guide', 'home'].includes(S.view)) render();
  } catch (e) {
    S.epgState = 'error';
    setStatus('');
    console.warn('EPG', e);
  }
}

const epgCache = new Map();
function progsFor(item) {
  if (!S.epg || !item) return [];
  if (epgCache.has(item.id)) return epgCache.get(item.id);
  const P = S.epg.programmes;
  let list = (item.epgId && (P[item.epgId] || P[item.epgId.toLowerCase()])) || null;
  if (!list) { const id = S.epg.byName[normName(item.name)]; list = id ? P[id] : null; }
  const off = (settings().epgOffsetMin || 0) * 60000;
  const out = list ? (off ? list.map((p) => ({ ...p, s: p.s + off, e: p.e + off })) : list) : [];
  epgCache.set(item.id, out);
  return out;
}
function nowNext(item) {
  const list = progsFor(item);
  const t = Date.now();
  const i = list.findIndex((p) => p.s <= t && p.e > t);
  if (i < 0) { const n = list.find((p) => p.s > t); return { now: null, next: n || null }; }
  return { now: list[i], next: list[i + 1] || null };
}

// ======================================================================
// Reproduccion
// ======================================================================
const player = new Player($('#player'), {
  getSettings: settings,
  saveSettings: (patch) => { Object.assign(S.data.settings, patch); saveSettingsSoon(); },
  onClose: () => closePlayer(),
  onExpand: () => expandPlayer(),
  onExternal: (url, title) => openExternal(url, title),
});
const saveSettingsSoon = debounce(() => save('settings'), 500);

function openExternal(url, title) {
  window.api.player.external(settings().externalPlayer, url, title)
    .then(() => toast('Abriendo en reproductor externo...'))
    .catch((e) => toast(cleanErr(e), 'err'));
}

function expandPlayer() {
  player.setMode('full');
  document.body.classList.add('player-full');
}
function closePlayer() {
  if (player.isWinFull) window.api.win.fullscreen(false);
  document.body.classList.remove('player-full');
  if (S.playing && S.playing.type === 'live' && S.view === 'live' && $('.preview-slot')) {
    player.setMode('mini', $('.preview-slot').getBoundingClientRect());
    renderLiveInfo();
    return;
  }
  stopPlayback();
}
function stopPlayback() {
  player.stop();
  player.setMode('hidden');
  document.body.classList.remove('player-full');
  S.playing = null;
  if (S.view === 'live') { renderLiveInfo(); markPlaying(); }
  if (S.view === 'home') renderHome();
}
function syncMini() {
  if (player.mode !== 'mini') return;
  const slot = $('.preview-slot');
  if (!slot || S.view !== 'live') { stopPlayback(); return; }
  player.place(slot.getBoundingClientRect());
}
window.addEventListener('resize', syncMini);

function playLive(item, { full = false, list } = {}) {
  if (list) S.live.list = list;
  const zapList = () => (S.live.list.length ? S.live.list : visibleItems('live'));
  S.playing = { type: 'live', item };
  putHistory('live', item.id, { item: snapshot('live', item) });
  const alt = Sources.altLiveUrl(S.src, item, settings());
  player.play({
    live: true, url: Sources.streamUrl(S.src, 'live', item, settings()), altUrls: alt ? [alt] : [],
    title: `${item.num ? item.num + '  ' : ''}${item.name}`,
    subtitle: (catById('live', item.cat) || {}).name || '',
    logo: item.logo,
    epg: () => nowNext(item),
    isFav: () => isFav('live', item),
    onFav: () => { toggleFav('live', item); if (S.view === 'live') renderLiveList(); },
    onStep: (dir) => {
      const l = zapList();
      let i = l.findIndex((x) => x.id === item.id);
      i = (i + dir + l.length) % l.length;
      if (l[i]) { playLive(l[i]); selectLive(l[i]); }
    },
    onNumber: (n) => {
      const ch = visibleItems('live').find((x) => +x.num === n);
      if (ch) { playLive(ch); selectLive(ch); }
      return !!ch;
    },
    renderSide: (head, body, close) => renderSideList(head, body, item, close),
  });
  if (full || player.mode === 'full') expandPlayer();
  else if (S.view === 'live' && $('.preview-slot')) player.setMode('mini', $('.preview-slot').getBoundingClientRect());
  else expandPlayer();
  if (S.view === 'live') { markPlaying(); renderLiveInfo(); }
}
function selectLive(item) {
  if (S.view !== 'live') return;
  const i = S.live.list.findIndex((x) => x.id === item.id);
  if (i >= 0) { S.live.sel = i; if (liveVL) liveVL.scrollTo(i); markPlaying(); }
}
function renderSideList(head, body, current, close) {
  const list = S.live.list.length ? S.live.list : visibleItems('live');
  const c = catById('live', S.live.cat);
  head.innerHTML = `<b>${esc(S.live.cat === '__fav' ? 'Favoritos' : S.live.cat === '__recent' ? 'Recientes' : c ? c.name : 'Todos los canales')}</b><span class="muted">${plural(list.length, 'canal', 'canales')}</span>`;
  const vl = vlist(body, list, 58, (it, i, style) => {
    const nn = nowNext(it);
    return `<div class="side-row ${S.playing && S.playing.item.id === it.id ? 'on' : ''}" data-i="${i}" style="${style}">
      <span class="ch-num">${esc(it.num || '')}</span>${logoHtml(it.logo, it.name, 'ch-logo')}
      <div class="ch-txt"><div class="ch-name">${esc(it.name)}</div><div class="ch-now">${esc(nn.now ? nn.now.t : '')}</div></div></div>`;
  });
  const idx = list.findIndex((x) => x.id === current.id);
  if (idx >= 0) setTimeout(() => { body.scrollTop = Math.max(0, idx * 58 - body.clientHeight / 2); vl.refresh(); }, 0);
  body.onclick = (e) => {
    const r = e.target.closest('.side-row');
    if (!r) return;
    const it = list[+r.dataset.i];
    playLive(it); selectLive(it); close();
  };
}

function playMovie(item, { fromStart = false } = {}) {
  const h0 = hist('movie', item.id);
  const startAt = !fromStart && h0 && !h0.done && h0.pos > 20 ? h0.pos : 0;
  S.playing = { type: 'movie', item };
  player.play({
    live: false, url: Sources.streamUrl(S.src, 'movie', item), title: item.name,
    subtitle: [item.year, (catById('movie', item.cat) || {}).name].filter(Boolean).join(' · '),
    startAt,
    isFav: () => isFav('movie', item),
    onFav: () => toggleFav('movie', item),
    onProgress: (pos, dur, ended) => putHistory('movie', item.id, { item: snapshot('movie', item), pos, dur, done: ended || (dur && pos > dur - 90) }),
    onEnded: () => { toast('Película terminada'); closePlayer(); },
  });
  expandPlayer();
}

function playEpisode(series, seasons, ep, { fromStart = false } = {}) {
  const he = hist('ep', ep.id);
  const startAt = !fromStart && he && !he.done && he.pos > 20 ? he.pos : 0;
  const season = seasons.find((s) => s.episodes.includes(ep));
  const flat = seasons.flatMap((s) => s.episodes.map((e) => ({ e, s: s.n })));
  const idx = flat.findIndex((x) => x.e.id === ep.id);
  const next = flat[idx + 1];
  S.playing = { type: 'episode', item: ep, series };
  const label = `T${season ? season.n : '?'} E${ep.n} · ${ep.title}`;
  player.play({
    live: false, url: Sources.streamUrl(S.src, 'episode', ep), title: series.name, subtitle: label, startAt,
    isFav: () => isFav('series', series),
    onFav: () => toggleFav('series', series),
    onProgress: (pos, dur, ended) => {
      const done = ended || (dur && pos > dur - 90);
      putHistory('ep', ep.id, { pos, dur, done });
      putHistory('series', series.id, {
        item: snapshot('series', series), pos, dur, done: done && !next,
        ep: { id: ep.id, n: ep.n, season: season ? season.n : 1, title: ep.title },
      });
    },
    onEnded: () => {
      if (next && settings().autoplayNext) {
        player.offerNext(`T${next.s} E${next.e.n} · ${next.e.title}`, () => playEpisode(series, seasons, next.e, { fromStart: true }));
      } else { closePlayer(); }
    },
  });
  expandPlayer();
}

// ======================================================================
// Render general
// ======================================================================
const VIEWS = {
  home: { title: 'Inicio', render: () => renderHome() },
  live: { title: 'TV en vivo', render: () => renderLive() },
  guide: { title: 'Guía de TV', render: () => renderGuide() },
  movie: { title: 'Películas', render: () => renderVod('movie') },
  series: { title: 'Series', render: () => renderVod('series') },
  favorites: { title: 'Mis favoritos', render: () => renderFavorites() },
  search: { title: 'Buscar', render: () => renderSearch() },
  settings: { title: 'Ajustes', render: () => renderSettings() },
};

function go(view) {
  if (S.view === 'live' && view !== 'live' && S.playing && S.playing.type === 'live' && player.mode === 'mini') stopPlayback();
  S.view = view;
  $$('.nav-btn').forEach((b) => b.classList.toggle('on', b.dataset.view === view));
  if (view !== 'search') { $('#search').value = ''; S.search = ''; }
  else setTimeout(() => $('#search').focus(), 0);
  render();
}

function render() {
  const v = VIEWS[S.view] || VIEWS.home;
  $('#view-title').textContent = v.title;
  const el = $('#view');
  el.className = 'view view-' + S.view;
  if (!S.data.sources.length && S.view !== 'settings') { renderWelcome(); return; }
  if (!S.cat && S.view !== 'settings') { if (!S.loading) renderLoading('Cargando...'); return; }
  v.render();
}
function renderLoading(msg) {
  if (S.view === 'settings') return;
  $('#view').innerHTML = `<div class="center-state"><div class="spinner"></div><div>${esc(msg)}</div></div>`;
}
function renderError(msg) {
  $('#view').innerHTML = `<div class="center-state"><div class="state-ico">!</div><h2>No se pudo cargar el contenido</h2>
    <p class="muted">${esc(msg)}</p><div class="row"><button class="btn primary" data-act="retry">Reintentar</button>
    <button class="btn" data-act="edit-src">Revisar datos de la fuente</button></div></div>`;
}

function logoHtml(src, name, cls) {
  return `<span class="${cls}">${src ? `<img loading="lazy" src="${esc(src)}" alt="">` : ''}<i>${esc(initials(name))}</i></span>`;
}

function renderSourceSwitch() {
  const el = $('#src-switch');
  const s = S.src;
  el.innerHTML = s
    ? `<span class="src-dot ${s.type}"></span><span class="src-name">${esc(s.name)}</span><span class="src-type">${{ xtream: 'Xtream', 'm3u-url': 'M3U', 'm3u-file': 'Archivo' }[s.type]}</span>`
    : '<span class="src-name muted">Sin fuente</span>';
}

// ======================================================================
// Bienvenida
// ======================================================================
function renderWelcome() {
  $('#view').innerHTML = `
  <div class="welcome">
    <div class="welcome-hero">
      <div class="brand-big">Drako<b>TV</b></div>
      <p>Tu TV en vivo, películas y series en la PC. Agrega una lista para empezar.</p>
    </div>
    <div class="welcome-grid">
      <button class="wcard" data-act="add-src" data-type="xtream">
        <div class="wcard-ico">XC</div><h3>Cuenta Xtream Codes</h3>
        <p>Servidor, usuario y contraseña que te dio tu proveedor. Trae TV, películas, series y guía.</p></button>
      <button class="wcard" data-act="add-src" data-type="m3u-url">
        <div class="wcard-ico">URL</div><h3>Lista M3U por enlace</h3>
        <p>Pega el enlace .m3u / .m3u8 de tu lista.</p></button>
      <button class="wcard" data-act="add-src" data-type="m3u-file">
        <div class="wcard-ico">M3U</div><h3>Archivo M3U</h3>
        <p>Elige un archivo de lista guardado en tu PC.</p></button>
      <button class="wcard accent" data-act="add-src" data-type="free">
        <div class="wcard-ico">FREE</div><h3>Canales gratuitos</h3>
        <p>Canales públicos y gratuitos de todo el mundo (directorio iptv-org). Ideal para probar.</p></button>
    </div>
    <p class="muted small center">DrakoTV es un reproductor: no incluye ni vende canales. Usa solo listas que tengas derecho a ver.</p>
  </div>`;
}

// ======================================================================
// Inicio
// ======================================================================
function renderHome() {
  if (S.view !== 'home' || !S.cat) return;
  const cont = continueList().slice(0, 20);
  const recentLive = historyList(['live']).slice(0, 20).map((x) => resolveItem('live', x.item));
  const favLive = favList('live').slice(0, 30);
  const lockedM = lockedCatIds('movie'), lockedS = lockedCatIds('series');
  const newMovies = S.cat.movie.items.some((m) => m.added)
    ? [...S.cat.movie.items].filter((m) => !lockedM.has(m.cat)).sort((a, b) => b.added - a.added).slice(0, 30) : visibleItems('movie').slice(0, 30);
  const newSeries = S.cat.series.items.some((m) => m.added)
    ? [...S.cat.series.items].filter((m) => !lockedS.has(m.cat)).sort((a, b) => b.added - a.added).slice(0, 30) : visibleItems('series').slice(0, 30);
  const favMovies = favList('movie').slice(0, 30);
  const favSeries = favList('series').slice(0, 30);
  const c = S.cat;
  const acc = c.account;
  const row = (title, items, cardFn, more) => !items.length ? '' : `
    <section class="row-sec"><div class="row-head"><h2>${title}</h2>${more ? `<button class="link" data-act="go" data-view="${more}">Ver todo</button>` : ''}</div>
    <div class="hscroll">${items.map(cardFn).join('')}</div></section>`;

  const hero = cont[0];
  $('#view').innerHTML = `
    <div class="home">
      <div class="stats">
        <button class="stat" data-act="go" data-view="live"><b>${c.live.items.length.toLocaleString('es-MX')}</b><span>Canales en vivo</span></button>
        <button class="stat" data-act="go" data-view="movie"><b>${c.movie.items.length.toLocaleString('es-MX')}</b><span>Películas</span></button>
        <button class="stat" data-act="go" data-view="series"><b>${c.series.items.length.toLocaleString('es-MX')}</b><span>Series</span></button>
        <div class="stat info"><b>${acc && acc.expires ? new Date(acc.expires).toLocaleDateString('es-MX', { day: 'numeric', month: 'short', year: 'numeric' }) : 'Sin vencimiento'}</b>
          <span>${acc ? `Vence la cuenta${acc.maxConnections ? ` · ${acc.maxConnections} pantallas` : ''}` : 'Lista ' + esc(S.src.name)}</span></div>
      </div>
      ${hero ? `<div class="hero" data-act="resume" data-key="${esc(heroKey(hero))}">
        <div class="hero-txt"><span class="eyebrow">Seguir viendo</span><h1>${esc(hero.item.name)}</h1>
        <p>${hero.ep ? `T${hero.ep.season} E${hero.ep.n} · ${esc(hero.ep.title)} · ` : ''}${Math.round(progressPct(hero))}% visto</p>
        <button class="btn primary big" data-act="resume" data-key="${esc(heroKey(hero))}">${ICONS.play} Continuar</button></div>
        ${hero.item.poster ? `<img class="hero-img" src="${esc(hero.item.poster)}" alt="">` : ''}</div>` : ''}
      ${row('Seguir viendo', cont, contCard)}
      ${row('Canales recientes', recentLive, chCard, 'live')}
      ${row('Canales favoritos', favLive, chCard, 'favorites')}
      ${row('Películas agregadas recientemente', newMovies, (m) => posterCard('movie', m), 'movie')}
      ${row('Series agregadas recientemente', newSeries, (m) => posterCard('series', m), 'series')}
      ${row('Películas favoritas', favMovies, (m) => posterCard('movie', m), 'favorites')}
      ${row('Series favoritas', favSeries, (m) => posterCard('series', m), 'favorites')}
      ${!c.live.items.length && !c.movie.items.length && !c.series.items.length ? '<div class="center-state"><h2>Esta lista está vacía</h2></div>' : ''}
    </div>`;
}
const heroKey = (x) => `${x.type}|${x.item.id}`;
function contCard(x) {
  const it = x.item;
  const sub = x.ep ? `T${x.ep.season} E${x.ep.n}` : (it.year || 'Película');
  return `<button class="ccard" data-act="resume" data-key="${esc(heroKey(x))}">
    <div class="ccard-img">${it.poster ? `<img loading="lazy" src="${esc(it.poster)}" alt="">` : ''}<i>${esc(initials(it.name))}</i>
    <span class="play-ov">${ICONS.play}</span></div>
    <div class="bar"><i style="width:${progressPct(x)}%"></i></div>
    <div class="ccard-t">${esc(it.name)}</div><div class="ccard-s">${esc(sub)}</div></button>`;
}
function chCard(it) {
  const nn = nowNext(it);
  return `<button class="chcard" data-act="play-live" data-id="${esc(it.id)}">
    ${logoHtml(it.logo, it.name, 'chcard-logo')}
    <div class="chcard-t">${esc(it.name)}</div><div class="chcard-s">${esc(nn.now ? nn.now.t : (catById('live', it.cat) || {}).name || '')}</div></button>`;
}
function posterCard(type, it) {
  const hx = type === 'movie' ? hist('movie', it.id) : hist('series', it.id);
  const pct = hx && !hx.done ? progressPct(hx) : 0;
  return `<button class="pcard" data-act="open-${type}" data-id="${esc(it.id)}" title="${esc(it.name)}">
    <div class="pcard-img">${it.poster ? `<img loading="lazy" src="${esc(it.poster)}" alt="">` : ''}<i>${esc(initials(it.name))}</i>
      ${it.rating ? `<span class="rating">★ ${(+it.rating).toFixed(1)}</span>` : ''}
      ${isFav(type, it) ? `<span class="fav-dot">${ICONS.heart}</span>` : ''}
      ${pct ? `<div class="bar"><i style="width:${pct}%"></i></div>` : ''}</div>
    <div class="pcard-t">${esc(it.name)}</div>${it.year ? `<div class="pcard-s">${esc(it.year)}</div>` : ''}</button>`;
}

// ======================================================================
// TV en vivo
// ======================================================================
let liveVL = null;
function liveListFor(catId) {
  const f = norm(S.live.filter);
  let list;
  if (catId === '__fav') list = favList('live');
  else if (catId === '__recent') list = historyList(['live']).slice(0, 50).map((x) => resolveItem('live', x.item));
  else if (catId === '__all') list = visibleItems('live');
  else list = S.cat.live.items.filter((i) => i.cat === catId);
  if (f) list = list.filter((i) => norm(i.name).includes(f) || String(i.num) === f);
  return list;
}
function renderLive() {
  const c = S.cat.live;
  if (!c.items.length) {
    $('#view').innerHTML = '<div class="center-state"><h2>Esta fuente no tiene canales en vivo</h2><p class="muted">Revisa Películas o Series.</p></div>';
    return;
  }
  const counts = {};
  for (const i of c.items) counts[i.cat] = (counts[i.cat] || 0) + 1;
  const catRow = (id, name, n, locked) => `<button class="cat ${S.live.cat === id ? 'on' : ''}" data-act="live-cat" data-id="${esc(id)}">
    <span>${locked ? '🔒 ' : ''}${esc(name)}</span><em>${n ?? ''}</em></button>`;
  $('#view').innerHTML = `
  <div class="live">
    <div class="col cats">
      <div class="col-head">Categorías</div>
      <div class="cat-list">
        ${catRow('__all', 'Todos los canales', visibleItems('live').length)}
        ${catRow('__fav', '★ Favoritos', favList('live').length)}
        ${catRow('__recent', 'Vistos recientemente', '')}
        <div class="sep"></div>
        ${c.cats.filter((k) => counts[k.id]).map((k) => catRow(k.id, k.name, counts[k.id], isCatLocked('live', k) && !S.unlocked)).join('')}
      </div>
    </div>
    <div class="col chans">
      <div class="col-head"><input class="input sm" id="live-filter" placeholder="Filtrar canales o escribir número..." value="${esc(S.live.filter)}"></div>
      <div class="ch-list" tabindex="0"></div>
    </div>
    <div class="col info">
      <div class="preview-slot"><div class="preview-empty">${ICONS.play}<span>Elige un canal para verlo aquí.<br><small>Doble clic o Enter para pantalla completa</small></span></div></div>
      <div class="live-info"></div>
    </div>
  </div>`;
  renderLiveList();
  renderLiveInfo();
  $('#live-filter').addEventListener('input', debounce((e) => { S.live.filter = e.target.value; S.live.sel = 0; renderLiveList(); }, 150));
  const ro = new ResizeObserver(() => { syncMini(); if (liveVL) liveVL.refresh(); });
  ro.observe($('.preview-slot'));
  if (S.playing && S.playing.type === 'live') player.setMode(player.mode === 'full' ? 'full' : 'mini', $('.preview-slot').getBoundingClientRect());
}
function renderLiveList() {
  const box = $('.ch-list');
  if (!box) return;
  const list = liveListFor(S.live.cat);
  S.live.list = list;
  if (!list.length) {
    liveVL = null;
    box.innerHTML = `<div class="empty-small">${S.live.cat === '__fav' ? 'Aún no tienes canales favoritos. Usa el corazón para agregarlos.' : 'No hay canales aquí.'}</div>`;
    return;
  }
  const showEpg = S.epgState === 'ok';
  liveVL = vlist(box, list, 62, (it, i, style) => {
    const nn = showEpg ? nowNext(it) : {};
    const pct = nn.now ? ((Date.now() - nn.now.s) / (nn.now.e - nn.now.s)) * 100 : 0;
    const on = S.playing && S.playing.item.id === it.id;
    return `<div class="ch-row ${i === S.live.sel ? 'sel' : ''} ${on ? 'playing' : ''}" data-i="${i}" style="${style}">
      <span class="ch-num">${esc(it.num || '')}</span>${logoHtml(it.logo, it.name, 'ch-logo')}
      <div class="ch-txt"><div class="ch-name">${esc(it.name)}</div>
      ${nn.now ? `<div class="ch-now">${esc(nn.now.t)}</div><div class="ch-bar"><i style="width:${pct}%"></i></div>` : ''}</div>
      <button class="ch-fav ${isFav('live', it) ? 'on' : ''}" data-fav="${i}" title="Favorito">${isFav('live', it) ? ICONS.heart : ICONS.heartO}</button></div>`;
  });
  liveVL.scrollTo(Math.min(S.live.sel, list.length - 1));
  box.onclick = (e) => {
    const fav = e.target.closest('[data-fav]');
    if (fav) { e.stopPropagation(); toggleFav('live', list[+fav.dataset.fav]); liveVL.refresh(); return; }
    const r = e.target.closest('.ch-row');
    if (!r) return;
    S.live.sel = +r.dataset.i;
    playLive(list[S.live.sel], { list });
  };
  box.ondblclick = (e) => {
    const r = e.target.closest('.ch-row');
    if (r) { S.live.sel = +r.dataset.i; if (!S.playing || S.playing.item.id !== list[S.live.sel].id) playLive(list[S.live.sel], { list }); expandPlayer(); }
  };
}
function markPlaying() { if (liveVL) liveVL.refresh(); }
function renderLiveInfo() {
  const box = $('.live-info');
  if (!box) return;
  const it = (S.playing && S.playing.type === 'live' && S.playing.item) || S.live.list[S.live.sel];
  if (!it) { box.innerHTML = ''; return; }
  const progs = progsFor(it);
  const t = Date.now();
  const upcoming = progs.filter((p) => p.e > t).slice(0, 12);
  const nn = nowNext(it);
  box.innerHTML = `
    <div class="li-head">${logoHtml(it.logo, it.name, 'li-logo')}
      <div><h2>${esc(it.name)}</h2><div class="muted">${it.num ? 'Canal ' + esc(it.num) + ' · ' : ''}${esc((catById('live', it.cat) || {}).name || '')}</div></div>
      <div class="li-actions">
        <button class="icon-btn ${isFav('live', it) ? 'on' : ''}" data-act="fav-live" data-id="${esc(it.id)}" title="Favorito">${isFav('live', it) ? ICONS.heart : ICONS.heartO}</button>
        <button class="icon-btn" data-act="ext-live" data-id="${esc(it.id)}" title="Abrir en VLC">${ICONS.ext}</button>
        <button class="btn primary sm" data-act="full-live" data-id="${esc(it.id)}">${ICONS.expand} Pantalla grande</button>
      </div></div>
    ${nn.now ? `<div class="now-card"><span class="badge onair">AHORA</span> <b>${esc(nn.now.t)}</b> <span class="muted">${hhmm(nn.now.s)} - ${hhmm(nn.now.e)}</span>
      <div class="ch-bar"><i style="width:${((t - nn.now.s) / (nn.now.e - nn.now.s)) * 100}%"></i></div>
      ${nn.now.d ? `<p>${esc(nn.now.d)}</p>` : ''}</div>` : ''}
    ${upcoming.length > 1 ? `<div class="sched"><div class="col-head">Programacion</div>
      ${upcoming.map((p) => `<div class="sched-row ${p.s <= t ? 'now' : ''}"><span>${hhmm(p.s)}</span><b>${esc(p.t)}</b></div>`).join('')}</div>` : ''}
    ${!progs.length ? `<p class="muted small">${S.epgState === 'loading' ? 'Cargando guía de programación...' : 'Sin guía de programación para este canal.'}</p>` : ''}`;
}

// ======================================================================
// Guia (EPG en rejilla)
// ======================================================================
function renderGuide() {
  const c = S.cat.live;
  if (!c.items.length) { $('#view').innerHTML = '<div class="center-state"><h2>No hay canales en vivo</h2></div>'; return; }
  if (S.epgState !== 'ok') {
    $('#view').innerHTML = `<div class="center-state">${S.epgState === 'loading' ? '<div class="spinner"></div><h2>Cargando guía...</h2><p class="muted">Las guias grandes pueden tardar un poco la primera vez.</p>'
      : `<h2>Sin guia de programacion</h2><p class="muted">Esta fuente no trae guia (EPG). Puedes agregar una URL de guia XMLTV en Ajustes &gt; Fuentes.</p>
         <div class="row"><button class="btn" data-act="go" data-view="settings">Ir a Ajustes</button>${S.epgState === 'error' ? '<button class="btn primary" data-act="reload-epg">Reintentar</button>' : ''}</div>`}</div>`;
    return;
  }
  const locked = lockedCatIds('live');
  const cats = c.cats.filter((k) => !locked.has(k.id) && c.items.some((i) => i.cat === k.id));
  if (!S.guide.cat || !cats.find((k) => k.id === S.guide.cat)) {
    const withEpg = cats.find((k) => c.items.some((i) => i.cat === k.id && progsFor(i).length));
    S.guide.cat = (withEpg || cats[0] || {}).id;
  }
  const onlyEpg = S.guide.onlyEpg !== false;
  let chans = S.guide.cat === '__fav' ? favList('live') : c.items.filter((i) => i.cat === S.guide.cat);
  if (onlyEpg) chans = chans.filter((i) => progsFor(i).length);
  const PX = 4; // px por minuto
  const t0 = new Date(); t0.setMinutes(t0.getMinutes() < 30 ? 0 : 30, 0, 0);
  const start = t0.getTime() - 30 * 60000, hours = 12, end = start + hours * 3600e3;
  const W = hours * 60 * PX, ROW = 60, CH = 210;
  const ticks = [];
  for (let t = start; t < end; t += 30 * 60000) ticks.push(`<span style="left:${CH + ((t - start) / 60000) * PX}px">${hhmm(t)}</span>`);
  $('#view').innerHTML = `
  <div class="guide">
    <div class="guide-bar">
      <select class="input sm" id="guide-cat">
        <option value="__fav" ${S.guide.cat === '__fav' ? 'selected' : ''}>★ Favoritos</option>
        ${cats.map((k) => `<option value="${esc(k.id)}" ${k.id === S.guide.cat ? 'selected' : ''}>${esc(k.name)}</option>`).join('')}
      </select>
      <label class="check"><input type="checkbox" id="guide-only" ${onlyEpg ? 'checked' : ''}> Solo canales con guía</label>
      <span class="muted small">${plural(chans.length, 'canal', 'canales')}</span>
    </div>
    <div class="guide-scroll">
      <div class="guide-inner" style="width:${CH + W}px;height:${40 + chans.length * ROW}px">
        <div class="guide-times" style="width:${CH + W}px">${ticks.join('')}</div>
        <div class="guide-now" style="left:${CH + ((Date.now() - start) / 60000) * PX}px;height:${40 + chans.length * ROW}px"></div>
        <div class="guide-rows"></div>
      </div>
    </div>
  </div>`;
  $('#guide-cat').onchange = (e) => { S.guide.cat = e.target.value; renderGuide(); };
  $('#guide-only').onchange = (e) => { S.guide.onlyEpg = e.target.checked; renderGuide(); };
  const sc = $('.guide-scroll'), rows = $('.guide-rows');
  const now = Date.now();
  const draw = () => {
    const a = Math.max(0, Math.floor(sc.scrollTop / ROW) - 4), b = Math.min(chans.length, Math.ceil((sc.scrollTop + sc.clientHeight) / ROW) + 4);
    let html = '';
    for (let i = a; i < b; i++) {
      const it = chans[i];
      const progs = progsFor(it).filter((p) => p.e > start && p.s < end);
      html += `<div class="g-row" style="top:${40 + i * ROW}px;width:${CH + W}px;height:${ROW}px">
        <div class="g-ch" data-act="play-live" data-id="${esc(it.id)}" style="width:${CH}px">${logoHtml(it.logo, it.name, 'ch-logo')}<span>${esc(it.name)}</span></div>
        ${progs.map((p) => {
          const l = CH + Math.max(0, (p.s - start) / 60000) * PX;
          const w = ((Math.min(p.e, end) - Math.max(p.s, start)) / 60000) * PX;
          return `<div class="g-prog ${p.s <= now && p.e > now ? 'now' : ''} ${p.e <= now ? 'past' : ''}" style="left:${l}px;width:${Math.max(0, w - 3)}px"
            data-act="g-prog" data-id="${esc(it.id)}" data-s="${p.s}" title="${esc(p.t)}"><b>${esc(p.t)}</b><span>${hhmm(p.s)} - ${hhmm(p.e)}</span></div>`;
        }).join('')}</div>`;
    }
    rows.innerHTML = html;
  };
  sc.onscroll = draw;
  draw();
  sc.scrollLeft = Math.max(0, ((now - start) / 60000) * PX - 120);
}

// ======================================================================
// Peliculas y series
// ======================================================================
function renderVod(type) {
  const st = S.vod[type];
  const c = S.cat[type];
  const label = type === 'movie' ? 'películas' : 'series';
  if (!c.items.length) {
    $('#view').innerHTML = `<div class="center-state"><h2>Esta fuente no tiene ${label}</h2>
      <p class="muted">${S.src.type === 'xtream' ? 'Tu cuenta no incluye este contenido.' : 'Las listas M3U normalmente solo traen TV en vivo.'}</p></div>`;
    return;
  }
  const counts = {};
  for (const i of c.items) counts[i.cat] = (counts[i.cat] || 0) + 1;
  const catRow = (id, name, n, locked) => `<button class="cat ${st.cat === id ? 'on' : ''}" data-act="vod-cat" data-type="${type}" data-id="${esc(id)}">
    <span>${locked ? '🔒 ' : ''}${esc(name)}</span><em>${n ?? ''}</em></button>`;
  $('#view').innerHTML = `
  <div class="vod">
    <div class="col cats">
      <div class="col-head">Categorías</div>
      <div class="cat-list">
        ${catRow('__all', 'Todas', visibleItems(type).length)}
        ${catRow('__fav', '★ Favoritos', favList(type).length)}
        ${catRow('__cont', 'Seguir viendo', '')}
        <div class="sep"></div>
        ${c.cats.filter((k) => counts[k.id]).map((k) => catRow(k.id, k.name, counts[k.id], isCatLocked(type, k) && !S.unlocked)).join('')}
      </div>
    </div>
    <div class="vod-main">
      <div class="vod-bar">
        <input class="input sm" id="vod-filter" placeholder="Filtrar ${label}..." value="${esc(st.filter)}">
        <select class="input sm" id="vod-sort">
          <option value="added" ${st.sort === 'added' ? 'selected' : ''}>Recientes</option>
          <option value="name" ${st.sort === 'name' ? 'selected' : ''}>A - Z</option>
          <option value="rating" ${st.sort === 'rating' ? 'selected' : ''}>Mejor calificadas</option>
          <option value="year" ${st.sort === 'year' ? 'selected' : ''}>Año</option>
        </select>
        <span class="muted small" id="vod-count"></span>
      </div>
      <div class="grid" id="vod-grid"></div>
    </div>
  </div>`;
  const draw = () => {
    let list;
    if (st.cat === '__fav') list = favList(type);
    else if (st.cat === '__cont') list = continueList().filter((x) => x.type === type).map((x) => resolveItem(type, x.item));
    else if (st.cat === '__all') list = visibleItems(type);
    else list = c.items.filter((i) => i.cat === st.cat);
    const f = norm(st.filter);
    if (f) list = list.filter((i) => norm(i.name).includes(f));
    if (!['__fav', '__cont'].includes(st.cat)) {
      list = [...list];
      if (st.sort === 'name') list.sort((a, b) => a.name.localeCompare(b.name, 'es'));
      else if (st.sort === 'rating') list.sort((a, b) => (b.rating || 0) - (a.rating || 0));
      else if (st.sort === 'year') list.sort((a, b) => String(b.year || '').localeCompare(String(a.year || '')));
      else if (list.some((i) => i.added)) list.sort((a, b) => (b.added || 0) - (a.added || 0));
    }
    $('#vod-count').textContent = plural(list.length, type === 'movie' ? 'película' : 'serie', label);
    const grid = $('#vod-grid');
    if (!list.length) { grid.innerHTML = `<div class="empty-small">No hay ${label} aquí.</div>`; return; }
    pagedGrid(grid, list, (it) => posterCard(type, it));
    grid.scrollTop = 0;
  };
  draw();
  $('#vod-filter').addEventListener('input', debounce((e) => { st.filter = e.target.value; draw(); }, 200));
  $('#vod-sort').onchange = (e) => { st.sort = e.target.value; draw(); };
}

async function openMovie(item) {
  const m = modal(`<div class="detail"><div class="center-state"><div class="spinner"></div></div></div>`, { wide: true });
  let info = {};
  try { info = await Sources.movieInfo(S.src, item); } catch (e) { info = {}; }
  if (!m.isConnected) return;
  const hx = hist('movie', item.id);
  const canResume = hx && !hx.done && hx.pos > 20;
  const fav = isFav('movie', item);
  const backdrop = info.backdrop || '';
  $('.detail', m).outerHTML = `<div class="detail">
    ${backdrop ? `<div class="detail-bd" style="background-image:url('${esc(backdrop).replace(/'/g, '%27')}')"></div>` : ''}
    <div class="detail-body">
      <div class="detail-poster">${(info.poster || item.poster) ? `<img src="${esc(info.poster || item.poster)}" alt="">` : ''}<i>${esc(initials(item.name))}</i></div>
      <div class="detail-txt">
        <h1>${esc(item.name)}</h1>
        <div class="meta">${[info.year, info.duration, info.genre].filter(Boolean).map(esc).join(' · ')}${info.rating ? ` · <span class="star">★ ${(+info.rating).toFixed(1)}</span>` : ''}</div>
        ${info.plot ? `<p class="plot">${esc(info.plot)}</p>` : ''}
        ${info.director ? `<p class="small"><span class="muted">Direccion:</span> ${esc(info.director)}</p>` : ''}
        ${info.cast ? `<p class="small"><span class="muted">Reparto:</span> ${esc(info.cast)}</p>` : ''}
        ${canResume ? `<div class="bar wide"><i style="width:${progressPct(hx)}%"></i></div>` : ''}
        <div class="row">
          ${canResume ? `<button class="btn primary big" data-m="resume">${ICONS.play} Continuar (${fmtTime(hx.pos)})</button>
            <button class="btn big" data-m="start">Desde el inicio</button>`
            : `<button class="btn primary big" data-m="start">${ICONS.play} Reproducir</button>`}
          <button class="icon-btn big ${fav ? 'on' : ''}" data-m="fav" title="Favorito">${fav ? ICONS.heart : ICONS.heartO}</button>
          <button class="icon-btn big" data-m="ext" title="Abrir en VLC">${ICONS.ext}</button>
          ${info.trailer ? `<button class="btn ghost" data-m="tráiler">Ver trailer</button>` : ''}
        </div>
      </div>
    </div></div>`;
  m.onclick = (e) => {
    const b = e.target.closest('[data-m]');
    if (!b) return;
    const a = b.dataset.m;
    if (a === 'resume') { m.close(); playMovie(item); }
    if (a === 'start') { m.close(); playMovie(item, { fromStart: true }); }
    if (a === 'fav') { const on = toggleFav('movie', item); b.classList.toggle('on', on); b.innerHTML = on ? ICONS.heart : ICONS.heartO; refreshCards(); }
    if (a === 'ext') openExternal(Sources.streamUrl(S.src, 'movie', item), item.name);
    if (a === 'tráiler') window.api.app.openExternal(/^https?:/.test(info.trailer) ? info.trailer : `https://www.youtube.com/watch?v=${info.trailer}`);
  };
}

async function openSeries(item, { autoResume = false } = {}) {
  if (item.m3u) item = resolveItem('series', item);
  const m = modal(`<div class="detail"><div class="center-state"><div class="spinner"></div></div></div>`, { wide: true });
  let info;
  try { info = await Sources.seriesInfo(S.src, item); }
  catch (e) { if (m.isConnected) $('.detail', m).innerHTML = `<div class="center-state"><h2>No se pudo cargar la serie</h2><p class="muted">${esc(cleanErr(e))}</p></div>`; return; }
  if (!m.isConnected) return;
  const seasons = info.seasons || [];
  if (!seasons.length) { $('.detail', m).innerHTML = '<div class="center-state"><h2>Esta serie no tiene episodios disponibles</h2></div>'; return; }
  const hs = hist('series', item.id);
  let lastEp = hs && hs.ep && seasons.flatMap((s) => s.episodes).find((e) => e.id === hs.ep.id);
  if (autoResume && lastEp) { m.close(); playEpisode(item, seasons, lastEp); return; }
  let curSeason = (hs && hs.ep && seasons.find((s) => s.n === hs.ep.season)) || seasons[0];
  const fav = isFav('series', item);
  const backdrop = info.backdrop || '';
  $('.detail', m).outerHTML = `<div class="detail">
    ${backdrop ? `<div class="detail-bd" style="background-image:url('${esc(backdrop).replace(/'/g, '%27')}')"></div>` : ''}
    <div class="detail-body">
      <div class="detail-poster">${(info.poster || item.poster) ? `<img src="${esc(info.poster || item.poster)}" alt="">` : ''}<i>${esc(initials(item.name))}</i></div>
      <div class="detail-txt">
        <h1>${esc(item.name)}</h1>
        <div class="meta">${[info.year, plural(seasons.length, 'temporada', 'temporadas'), info.genre].filter(Boolean).map(esc).join(' · ')}${info.rating ? ` · <span class="star">★ ${(+info.rating).toFixed(1)}</span>` : ''}</div>
        ${info.plot ? `<p class="plot">${esc(info.plot)}</p>` : ''}
        ${info.cast ? `<p class="small"><span class="muted">Reparto:</span> ${esc(info.cast)}</p>` : ''}
        <div class="row">
          ${lastEp ? `<button class="btn primary big" data-m="resume">${ICONS.play} Continuar T${hs.ep.season} E${hs.ep.n}</button>` : `<button class="btn primary big" data-m="first">${ICONS.play} Ver T${seasons[0].n} E${seasons[0].episodes[0].n}</button>`}
          <button class="icon-btn big ${fav ? 'on' : ''}" data-m="fav" title="Favorito">${fav ? ICONS.heart : ICONS.heartO}</button>
          ${info.trailer ? `<button class="btn ghost" data-m="tráiler">Ver trailer</button>` : ''}
        </div>
      </div>
    </div>
    <div class="seasons"><div class="season-tabs"></div><div class="eps"></div></div>
  </div>`;
  const drawSeason = () => {
    $('.season-tabs', m).innerHTML = seasons.map((s) => `<button class="chip ${s === curSeason ? 'on' : ''}" data-season="${s.n}">Temporada ${s.n}</button>`).join('');
    $('.eps', m).innerHTML = curSeason.episodes.map((e, i) => {
      const he = hist('ep', e.id);
      return `<div class="ep ${he && he.done ? 'seen' : ''}" data-ep="${i}">
        <div class="ep-img">${e.img ? `<img loading="lazy" src="${esc(e.img)}" alt="">` : ''}<i>E${e.n}</i><span class="play-ov">${ICONS.play}</span>
          ${he && he.dur ? `<div class="bar"><i style="width:${he.done ? 100 : progressPct(he)}%"></i></div>` : ''}</div>
        <div class="ep-txt"><b>${e.n}. ${esc(e.title)}</b>${e.dur ? `<span class="muted small">${esc(e.dur)}</span>` : ''}
        ${e.plot ? `<p>${esc(e.plot)}</p>` : ''}</div>
        <button class="icon-btn" data-ext="${i}" title="Abrir en VLC">${ICONS.ext}</button></div>`;
    }).join('');
  };
  drawSeason();
  m.onclick = (e) => {
    const sb = e.target.closest('[data-season]');
    if (sb) { curSeason = seasons.find((s) => s.n === +sb.dataset.season); drawSeason(); return; }
    const ext = e.target.closest('[data-ext]');
    if (ext) { const ep = curSeason.episodes[+ext.dataset.ext]; openExternal(Sources.streamUrl(S.src, 'episode', ep), `${item.name} - ${ep.title}`); return; }
    const ep = e.target.closest('[data-ep]');
    if (ep) { m.close(); playEpisode(item, seasons, curSeason.episodes[+ep.dataset.ep]); return; }
    const b = e.target.closest('[data-m]');
    if (!b) return;
    if (b.dataset.m === 'resume') { m.close(); playEpisode(item, seasons, lastEp); }
    if (b.dataset.m === 'first') { m.close(); playEpisode(item, seasons, seasons[0].episodes[0]); }
    if (b.dataset.m === 'fav') { const on = toggleFav('series', item); b.classList.toggle('on', on); b.innerHTML = on ? ICONS.heart : ICONS.heartO; refreshCards(); }
    if (b.dataset.m === 'tráiler') window.api.app.openExternal(/^https?:/.test(info.trailer) ? info.trailer : `https://www.youtube.com/watch?v=${info.trailer}`);
  };
}
function refreshCards() { if (['home', 'favorites'].includes(S.view)) render(); }

// ======================================================================
// Favoritos y busqueda
// ======================================================================
function renderFavorites() {
  const live = favList('live'), movies = favList('movie'), series = favList('series');
  if (!live.length && !movies.length && !series.length) {
    $('#view').innerHTML = `<div class="center-state"><div class="state-ico">${ICONS.heartO}</div><h2>Aún no tienes favoritos</h2>
      <p class="muted">Toca el corazón en un canal, película o serie para guardarlo aquí.</p></div>`;
    return;
  }
  $('#view').innerHTML = `<div class="stack">
    ${live.length ? `<section><h2>Canales</h2><div class="ch-grid">${live.map(chCard).join('')}</div></section>` : ''}
    ${movies.length ? `<section><h2>Peliculas</h2><div class="grid static">${movies.map((m) => posterCard('movie', m)).join('')}</div></section>` : ''}
    ${series.length ? `<section><h2>Series</h2><div class="grid static">${series.map((m) => posterCard('series', m)).join('')}</div></section>` : ''}
  </div>`;
}

function renderSearch() {
  const q = norm(S.search.trim());
  if (q.length < 2) {
    $('#view').innerHTML = '<div class="center-state"><h2>Busca canales, películas y series</h2><p class="muted">Escribe al menos 2 letras en el buscador de arriba.</p></div>';
    return;
  }
  const words = q.split(/\s+/);
  const match = (i) => { const n = norm(i.name); return words.every((w) => n.includes(w)); };
  const live = visibleItems('live').filter(match).slice(0, 60);
  const movies = visibleItems('movie').filter(match).slice(0, 120);
  const series = visibleItems('series').filter(match).slice(0, 120);
  if (!live.length && !movies.length && !series.length) {
    $('#view').innerHTML = `<div class="center-state"><h2>Sin resultados para "${esc(S.search)}"</h2></div>`;
    return;
  }
  $('#view').innerHTML = `<div class="stack">
    ${live.length ? `<section><h2>Canales <span class="muted">${live.length}</span></h2><div class="ch-grid">${live.map(chCard).join('')}</div></section>` : ''}
    ${movies.length ? `<section><h2>Peliculas <span class="muted">${movies.length}</span></h2><div class="grid static">${movies.map((m) => posterCard('movie', m)).join('')}</div></section>` : ''}
    ${series.length ? `<section><h2>Series <span class="muted">${series.length}</span></h2><div class="grid static">${series.map((m) => posterCard('series', m)).join('')}</div></section>` : ''}
  </div>`;
}

// ======================================================================
// Ajustes
// ======================================================================
async function renderSettings() {
  const s = settings();
  const ver = await window.api.app.version();
  if (S.view !== 'settings') return;
  const fmtDate = (ms) => ms ? new Date(ms).toLocaleDateString('es-MX', { day: 'numeric', month: 'long', year: 'numeric' }) : 'Sin vencimiento';
  const srcCard = (src) => `
    <div class="src-card ${S.src && S.src.id === src.id ? 'on' : ''}">
      <div class="src-main"><span class="src-dot ${src.type}"></span>
        <div><b>${esc(src.name)}</b><div class="muted small">${{ xtream: 'Xtream Codes · ' + esc(src.server || ''), 'm3u-url': 'Lista M3U · ' + esc((src.url || '').slice(0, 60)), 'm3u-file': 'Archivo M3U · ' + esc(src.fileName || '') }[src.type]}</div>
        ${src.account ? `<div class="small acc">Vence: <b>${fmtDate(src.account.expires)}</b>${src.account.maxConnections ? ` · Pantallas: <b>${esc(src.account.activeConnections || 0)}/${esc(src.account.maxConnections)}</b>` : ''}${src.account.trial ? ' · <b>Prueba</b>' : ''}</div>` : ''}
        </div></div>
      <div class="row">
        ${S.src && S.src.id === src.id ? `<span class="badge">En uso</span><button class="btn sm" data-act="refresh">Actualizar</button>` : `<button class="btn sm primary" data-act="use-src" data-id="${src.id}">Usar</button>`}
        <button class="btn sm ghost" data-act="edit-src" data-id="${src.id}">Editar</button>
        <button class="btn sm ghost danger-txt" data-act="del-src" data-id="${src.id}">Eliminar</button>
      </div>
    </div>`;
  $('#view').innerHTML = `<div class="settings">
    <section class="card">
      <div class="card-head"><h2>Fuentes de contenido</h2><button class="btn primary sm" data-act="add-src">+ Agregar fuente</button></div>
      ${S.data.sources.length ? S.data.sources.map(srcCard).join('') : '<p class="muted">Aún no agregas ninguna lista.</p>'}
      ${S.catAt ? `<p class="muted small">Ultima actualizacion: ${new Date(S.catAt).toLocaleString('es-MX')}</p>` : ''}
    </section>

    <section class="card">
      <h2>Reproducción</h2>
      <div class="form-grid">
        <label>Formato de TV en vivo (Xtream)
          <select class="input" data-set="liveFormat"><option value="m3u8" ${s.liveFormat === 'm3u8' ? 'selected' : ''}>HLS (.m3u8) - recomendado</option><option value="ts" ${s.liveFormat === 'ts' ? 'selected' : ''}>MPEG-TS (.ts)</option></select></label>
        <label>Búfer (segundos)
          <input class="input" type="number" min="5" max="120" data-set="bufferSec" value="${s.bufferSec}"></label>
        <label>Tiempo de espera al conectar (segundos)
          <input class="input" type="number" min="5" max="120" data-set="timeoutSec" value="${s.timeoutSec}"></label>
        <label>Actualizar listas automáticamente cada (horas)
          <input class="input" type="number" min="1" max="720" data-set="refreshHours" value="${s.refreshHours}"></label>
        <label class="check"><input type="checkbox" data-set="autoplayNext" ${s.autoplayNext ? 'checked' : ''}> Reproducir el siguiente episodio automáticamente</label>
      </div>
      <div class="form-grid">
        <label>User-Agent (si tu proveedor lo pide)
          <input class="input" data-set="userAgent" placeholder="VLC/3.0.20 LibVLC/3.0.20" value="${esc(s.userAgent)}"></label>
        <label>Reproductor externo (VLC o mpv)
          <div class="row nowrap"><input class="input" data-set="externalPlayer" placeholder="Se detecta VLC automáticamente" value="${esc(s.externalPlayer)}"><button class="btn sm" data-act="pick-exe">Elegir...</button></div></label>
      </div>
    </section>

    <section class="card">
      <h2>Guía de programación</h2>
      <div class="form-grid">
        <label>Ajuste de horario de la guía (minutos)
          <input class="input" type="number" step="30" data-set="epgOffsetMin" value="${s.epgOffsetMin}"></label>
        <div class="row"><button class="btn" data-act="reload-epg">Recargar guía ahora</button>
        <span class="muted small">Estado: ${{ none: 'sin guía', loading: 'cargando...', ok: 'cargada', error: 'error al cargar' }[S.epgState]}</span></div>
      </div>
    </section>

    <section class="card">
      <h2>Control parental</h2>
      <label class="check"><input type="checkbox" data-set="parental.enabled" ${s.parental.enabled ? 'checked' : ''}> Bloquear categorías para adultos con PIN</label>
      <div class="row"><button class="btn sm" data-act="change-pin">Cambiar PIN</button>
        ${S.cat ? '<button class="btn sm" data-act="lock-cats">Elegir categorías bloqueadas</button>' : ''}
        ${S.unlocked ? '<button class="btn sm ghost" data-act="relock">Volver a bloquear</button>' : ''}</div>
      <p class="muted small">El PIN inicial es <b>0000</b>. Cámbialo para que sirva de algo.</p>
    </section>

    <section class="card">
      <h2>Datos</h2>
      <div class="row">
        <button class="btn" data-act="clear-history">Borrar historial de reproducción</button>
        <button class="btn" data-act="clear-cache">Borrar cache de listas y guía</button>
      </div>
    </section>

    <section class="card about">
      <h2>Acerca de</h2>
      <p>DrakoTV ${esc(ver)} · Reproductor IPTV de escritorio.</p>
      <p class="muted small">DrakoTV no incluye, aloja ni vende canales ni contenido. Solo reproduce las listas que tu agregas. Usa listas de proveedores legales o canales de acceso libre.</p>
      <p class="muted small">Atajos: Espacio pausa · F pantalla completa · M silencio · Flechas arriba/abajo cambiar canal · Numeros ir a canal · L lista de canales · Flechas izq/der adelantar · Esc volver · Ctrl+F buscar.</p>
    </section>
  </div>`;
  $$('[data-set]').forEach((el) => el.addEventListener('change', () => {
    const k = el.dataset.set;
    let v = el.type === 'checkbox' ? el.checked : el.type === 'number' ? +el.value : el.value.trim();
    if (k === 'parental.enabled') s.parental.enabled = v;
    else s[k] = v;
    save('settings');
    toast('Ajuste guardado');
    if (k === 'epgOffsetMin') epgCache.clear();
  }));
}

function sourceForm(existing, presetType) {
  const type = existing ? existing.type : presetType && presetType !== 'free' ? presetType : presetType === 'free' ? 'free' : 'xtream';
  const ex = existing || {};
  const tabs = existing ? '' : `<div class="tabs">
    ${[['xtream', 'Xtream Codes'], ['m3u-url', 'Lista M3U (URL)'], ['m3u-file', 'Archivo M3U'], ['free', 'Canales gratuitos']]
      .map(([k, l]) => `<button type="button" class="tab ${k === type ? 'on' : ''}" data-tab="${k}">${l}</button>`).join('')}</div>`;
  const m = modal(`<h2>${existing ? 'Editar fuente' : 'Agregar fuente'}</h2>${tabs}
    <form class="src-form" autocomplete="off">
      <div class="pane" data-pane="xtream">
        <label>Nombre<input class="input" name="name_xtream" placeholder="Mi proveedor" value="${esc(ex.type === 'xtream' ? ex.name : '')}"></label>
        <label>Servidor (URL)<input class="input" name="server" placeholder="http://servidor.com:8080" value="${esc(ex.server || '')}"></label>
        <div class="row2"><label>Usuario<input class="input" name="username" value="${esc(ex.username || '')}"></label>
        <label>Contraseña<input class="input" name="password" type="password" value="${esc(ex.password || '')}"></label></div>
      </div>
      <div class="pane" data-pane="m3u-url">
        <label>Nombre<input class="input" name="name_m3u-url" placeholder="Mi lista" value="${esc(ex.type === 'm3u-url' ? ex.name : '')}"></label>
        <label>Enlace de la lista M3U<input class="input" name="url" placeholder="https://..../lista.m3u" value="${esc(ex.url || '')}"></label>
      </div>
      <div class="pane" data-pane="m3u-file">
        <label>Nombre<input class="input" name="name_m3u-file" placeholder="Mi lista" value="${esc(ex.type === 'm3u-file' ? ex.name : '')}"></label>
        <div class="row"><button type="button" class="btn" data-pick>Elegir archivo...</button><span class="muted small file-name">${esc(ex.fileName || 'Ningún archivo elegido')}</span></div>
      </div>
      <div class="pane" data-pane="free">
        <p class="muted small">Canales de TV abierta y gratuitos, recopilados por el proyecto público iptv-org. Algunos pueden no funcionar en tu región.</p>
        <div class="free-list">${FREE_LISTS.map((f, i) => `<label class="radio"><input type="radio" name="free" value="${i}" ${i === 0 ? 'checked' : ''}> ${esc(f.name)}</label>`).join('')}</div>
      </div>
      <details class="adv" ${ex.epgUrl ? 'open' : ''}><summary>Opciones avanzadas</summary>
        <label>URL de guía XMLTV (opcional)<input class="input" name="epgUrl" placeholder="Se usa la de la lista si existe" value="${esc(ex.epgUrl || '')}"></label>
      </details>
      <div class="form-err hidden"></div>
      <div class="row end"><button type="button" class="btn ghost" data-close>Cancelar</button><button class="btn primary" type="submit">${existing ? 'Guardar' : 'Agregar y cargar'}</button></div>
    </form>`);
  let cur = type;
  let file = null;
  const show = () => {
    $$('.pane', m).forEach((p) => p.classList.toggle('hidden', p.dataset.pane !== cur));
    $$('.tab', m).forEach((t) => t.classList.toggle('on', t.dataset.tab === cur));
    $('.adv', m).classList.toggle('hidden', cur === 'free');
  };
  show();
  m.addEventListener('click', async (e) => {
    const t = e.target.closest('[data-tab]');
    if (t) { cur = t.dataset.tab; show(); }
    if (e.target.closest('[data-pick]')) {
      const r = await window.api.dialog.openM3u();
      if (r) {
        file = r;
        const nm = r.path.split(/[\\/]/).pop();
        $('.file-name', m).textContent = nm;
        const nameInput = $('[name="name_m3u-file"]', m);
        if (!nameInput.value) nameInput.value = nm.replace(/\.[^.]+$/, '');
      }
    }
  });
  $('form', m).addEventListener('submit', async (e) => {
    e.preventDefault();
    const f = new FormData(e.target);
    const err = $('.form-err', m);
    const fail = (msg) => { err.textContent = msg; err.classList.remove('hidden'); };
    err.classList.add('hidden');
    const src = existing ? { ...existing } : { id: uid(), addedAt: Date.now() };
    src.type = cur === 'free' ? 'm3u-url' : cur;
    src.epgUrl = (f.get('epgUrl') || '').trim();
    if (cur === 'xtream') {
      src.server = (f.get('server') || '').trim();
      src.username = (f.get('username') || '').trim();
      src.password = (f.get('password') || '').trim();
      if (!src.server || !src.username || !src.password) return fail('Llena servidor, usuario y contraseña.');
      src.name = (f.get('name_xtream') || '').trim() || src.server.replace(/^https?:\/\//, '').split(/[:/]/)[0];
      const btn = $('[type="submit"]', m);
      btn.disabled = true; btn.textContent = 'Verificando...';
      try { src.account = await Sources.xtLogin(src); }
      catch (x) { btn.disabled = false; btn.textContent = existing ? 'Guardar' : 'Agregar y cargar'; return fail(cleanErr(x)); }
    } else if (cur === 'm3u-url') {
      src.url = (f.get('url') || '').trim();
      if (!/^https?:\/\//i.test(src.url)) return fail('Escribe un enlace válido que empiece con http:// o https://');
      src.name = (f.get('name_m3u-url') || '').trim() || 'Lista M3U';
    } else if (cur === 'm3u-file') {
      if (!file && !existing) return fail('Elige un archivo de lista.');
      src.name = (f.get('name_m3u-file') || '').trim() || 'Lista M3U';
      if (file) {
        try { Sources.parseM3U(file.text).entries.length || (() => { throw 0; })(); } catch { return fail('El archivo no parece una lista M3U válida.'); }
        src.fileName = file.path.split(/[\\/]/).pop();
        await window.api.cache.set(`${src.id}-file`, { text: file.text });
      }
    } else if (cur === 'free') {
      const pick = FREE_LISTS[+f.get('free')];
      src.url = pick.url;
      src.name = 'Gratis: ' + pick.name;
    }
    const i = S.data.sources.findIndex((x) => x.id === src.id);
    if (i >= 0) S.data.sources[i] = src; else S.data.sources.push(src);
    save('sources');
    m.close();
    if (existing) { await window.api.cache.del(src.id + '-catalog'); await window.api.cache.del(src.id + '-epg'); }
    const isActive = S.src && S.src.id === src.id;
    if (!existing || isActive || !S.src) {
      if (!existing && S.view === 'settings') go('home');
      await activateSource(src.id, { force: true });
    }
    if (S.view === 'settings') renderSettings();
  });
}

function lockCatsModal() {
  const p = settings().parental;
  const types = [['live', 'TV en vivo'], ['movie', 'Películas'], ['series', 'Series']];
  const m = modal(`<h2>Categorías bloqueadas</h2><p class="muted small">Las categorías marcadas pedirán PIN.</p>
    <input class="input sm" placeholder="Filtrar..." data-f>
    <div class="lock-list">${types.map(([t, l]) => S.cat[t].cats.length ? `<h3>${l}</h3>${S.cat[t].cats.map((c) =>
      `<label class="check" data-n="${esc(norm(c.name))}"><input type="checkbox" data-t="${t}" data-id="${esc(c.id)}" ${isCatLocked(t, c) ? 'checked' : ''}> ${esc(c.name)}</label>`).join('')}` : '').join('')}</div>
    <div class="row end"><button class="btn primary" data-close>Listo</button></div>`, { onClose: () => render() });
  $('[data-f]', m).addEventListener('input', (e) => {
    const q = norm(e.target.value);
    $$('.lock-list label', m).forEach((l) => l.classList.toggle('hidden', !!q && !l.dataset.n.includes(q)));
  });
  m.addEventListener('change', (e) => {
    const cb = e.target.closest('input[data-t]');
    if (!cb) return;
    p.locked[`${S.src.id}|${cb.dataset.t}|${cb.dataset.id}`] = cb.checked;
    save('settings');
  });
}

// ======================================================================
// Acciones (delegacion de clics)
// ======================================================================
document.addEventListener('click', async (e) => {
  const el = e.target.closest('[data-act]');
  if (!el) return;
  const a = el.dataset.act, id = el.dataset.id;
  switch (a) {
    case 'go': go(el.dataset.view); break;
    case 'retry': refreshCatalog(false); break;
    case 'refresh': await window.api.cache.del(S.src.id + '-catalog'); refreshCatalog(S.view === 'settings'); break;
    case 'add-src': sourceForm(null, el.dataset.type); break;
    case 'edit-src': sourceForm(S.data.sources.find((s) => s.id === (id || (S.src && S.src.id)))); break;
    case 'use-src': await activateSource(id); renderSettings(); break;
    case 'del-src': {
      const src = S.data.sources.find((s) => s.id === id);
      if (!(await confirmBox(`Eliminar la fuente "${src.name}"? Se borrarán también sus favoritos e historial.`, 'Eliminar', true))) break;
      S.data.sources = S.data.sources.filter((s) => s.id !== id);
      for (const k of Object.keys(S.data.favorites)) if (k.startsWith(id + '|')) delete S.data.favorites[k];
      for (const k of Object.keys(S.data.history)) if (k.startsWith(id + '|')) delete S.data.history[k];
      save('sources'); save('favorites'); save('history');
      await window.api.cache.del(id);
      if (S.src && S.src.id === id) {
        S.src = null; S.cat = null; S.catAt = 0;
        if (S.data.sources[0]) await activateSource(S.data.sources[0].id);
        else { S.data.activeId = null; save('activeId'); renderSourceSwitch(); }
      }
      renderSettings();
      break;
    }
    case 'pick-exe': {
      const p = await window.api.dialog.pickExe();
      if (p) { settings().externalPlayer = p; save('settings'); renderSettings(); }
      break;
    }
    case 'reload-epg': loadEpg(true).then(() => { if (S.view === 'settings') renderSettings(); }); if (S.view === 'settings') renderSettings(); break;
    case 'change-pin': changePin(); break;
    case 'lock-cats': if (await ensurePin()) lockCatsModal(); break;
    case 'relock': S.unlocked = false; toast('Control parental bloqueado'); renderSettings(); break;
    case 'clear-history':
      if (await confirmBox('Borrar todo el historial de reproducción y "seguir viendo"?', 'Borrar', true)) {
        S.data.history = {}; save('history'); toast('Historial borrado');
      }
      break;
    case 'clear-cache':
      for (const s of S.data.sources) await window.api.cache.del(s.id + '-catalog'), await window.api.cache.del(s.id + '-epg');
      toast('Cache borrada. Se volverá a descargar todo.');
      if (S.src) refreshCatalog(true);
      break;
    case 'live-cat': {
      const c = catById('live', id);
      if (c && isCatLocked('live', c) && !S.unlocked && !(await askPin())) break;
      S.live.cat = id; S.live.sel = 0; S.live.filter = '';
      renderLive();
      break;
    }
    case 'vod-cat': {
      const t = el.dataset.type;
      const c = catById(t, id);
      if (c && isCatLocked(t, c) && !S.unlocked && !(await askPin())) break;
      S.vod[t].cat = id; S.vod[t].filter = '';
      renderVod(t);
      break;
    }
    case 'play-live': {
      const it = S.cat.live.items.find((x) => x.id === id) || favList('live').find((x) => x.id === id);
      if (!it) { toast('Ese canal ya no está en la lista', 'err'); break; }
      if (S.view === 'live') { selectLive(it); playLive(it); }
      else playLive(it, { full: true, list: S.view === 'guide' ? [] : undefined });
      break;
    }
    case 'g-prog': {
      const it = S.cat.live.items.find((x) => x.id === id);
      const p = progsFor(it).find((x) => x.s === +el.dataset.s);
      if (p && p.s <= Date.now() && p.e > Date.now()) { playLive(it, { full: true }); break; }
      if (p) modal(`<h2>${esc(p.t)}</h2><p class="muted">${esc(it.name)} · ${new Date(p.s).toLocaleDateString('es-MX', { weekday: 'long', day: 'numeric', month: 'long' })} · ${hhmm(p.s)} - ${hhmm(p.e)}</p>
        ${p.d ? `<p>${esc(p.d)}</p>` : ''}<div class="row end"><button class="btn" data-close>Cerrar</button><button class="btn primary" data-close data-act="play-live" data-id="${esc(it.id)}">Ver canal ahora</button></div>`);
      break;
    }
    case 'fav-live': case 'ext-live': case 'full-live': {
      const it = S.cat.live.items.find((x) => x.id === id) || (S.playing && S.playing.item);
      if (!it) break;
      if (a === 'fav-live') { toggleFav('live', it); renderLiveInfo(); markPlaying(); }
      if (a === 'ext-live') { if (S.playing) stopPlayback(); openExternal(Sources.streamUrl(S.src, 'live', it, settings()), it.name); }
      if (a === 'full-live') { if (!S.playing || S.playing.item.id !== it.id) playLive(it, { full: true }); else expandPlayer(); }
      break;
    }
    case 'open-movie': {
      const it = S.cat.movie.items.find((x) => x.id === id) || favList('movie').find((x) => x.id === id);
      if (it) openMovie(it);
      break;
    }
    case 'open-series': {
      const it = S.cat.series.items.find((x) => x.id === id) || favList('series').find((x) => x.id === id);
      if (it) openSeries(it);
      break;
    }
    case 'resume': {
      e.stopPropagation();
      const [type, iid] = el.dataset.key.split('|');
      const x = hist(type, iid);
      if (!x) break;
      const it = resolveItem(type, x.item);
      if (type === 'movie') playMovie(it);
      else openSeries(it, { autoResume: true });
      break;
    }
  }
});

async function ensurePin() { return S.unlocked || askPin(); }
async function changePin() {
  if (!(await ensurePin())) return;
  const m = modal(`<h2>Nuevo PIN</h2><form><input class="input pin" type="password" inputmode="numeric" maxlength="8" minlength="4" autofocus placeholder="4 a 8 dígitos" pattern="\\d{4,8}" required>
    <div class="row end"><button type="button" class="btn ghost" data-close>Cancelar</button><button class="btn primary">Guardar</button></div></form>`);
  $('form', m).addEventListener('submit', (e) => {
    e.preventDefault();
    settings().parental.pin = $('input', m).value;
    save('settings');
    toast('PIN actualizado');
    m.close();
  });
}

// ======================================================================
// Teclado
// ======================================================================
document.addEventListener('keydown', (e) => {
  const inInput = /^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName);
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'f') { e.preventDefault(); $('#search').focus(); $('#search').select(); return; }
  const tm = topModal();
  if (tm) { if (e.key === 'Escape') tm.close(); return; }
  if (e.key === 'F11') { e.preventDefault(); window.api.win.fullscreen(); return; }
  if (inInput) {
    if (e.key === 'Escape') e.target.blur();
    if (S.view === 'live' && e.target.id === 'live-filter' && ['ArrowDown', 'Enter'].includes(e.key)) { e.preventDefault(); e.target.blur(); $('.ch-list').focus(); }
    return;
  }
  if (player.mode !== 'hidden' && player.key(e)) { e.preventDefault(); return; }
  if (S.view === 'live' && S.live.list.length) {
    const n = S.live.list.length;
    const step = { ArrowDown: 1, ArrowUp: -1, PageDown: 10, PageUp: -10 }[e.key];
    if (step) {
      e.preventDefault();
      S.live.sel = Math.max(0, Math.min(n - 1, S.live.sel + step));
      liveVL && liveVL.scrollTo(S.live.sel);
      if (!S.playing) renderLiveInfo();
      return;
    }
    if (e.key === 'Enter') {
      e.preventDefault();
      const it = S.live.list[S.live.sel];
      if (S.playing && S.playing.item.id === it.id) expandPlayer(); else playLive(it);
      return;
    }
    if (/^\d$/.test(e.key) && S.playing && S.playing.type === 'live') { player.typeNumber(e.key); return; }
  }
});

// ======================================================================
// Inicio de la app
// ======================================================================
async function init() {
  const data = await window.api.store.getAll();
  S.data.sources = data.sources || [];
  S.data.favorites = data.favorites || {};
  S.data.history = data.history || {};
  S.data.settings = { ...DEFAULT_SETTINGS, ...(data.settings || {}) };
  S.data.settings.parental = { ...DEFAULT_SETTINGS.parental, ...(S.data.settings.parental || {}) };
  S.data.activeId = data.activeId || null;

  $('.nav').addEventListener('click', (e) => { const b = e.target.closest('.nav-btn'); if (b) go(b.dataset.view); });
  $('#search').addEventListener('input', debounce((e) => {
    S.search = e.target.value;
    if (S.search.trim().length >= 2 && S.view !== 'search') { S.view = 'search'; $$('.nav-btn').forEach((b) => b.classList.toggle('on', b.dataset.view === 'search')); }
    if (S.view === 'search') render();
  }, 250));
  $('#src-switch').addEventListener('click', () => sourcePicker());
  $('#btn-refresh').addEventListener('click', () => { if (S.src) { toast('Actualizando contenido...'); refreshCatalog(true); } });
  window.api.win.onFullscreen((on) => { player.onFullscreen(on); document.body.classList.toggle('win-full', on); setTimeout(syncMini, 50); });
  window.addEventListener('beforeunload', () => player.stop());

  renderSourceSwitch();
  const active = S.data.sources.find((s) => s.id === S.data.activeId) || S.data.sources[0];
  render();
  if (active) await activateSource(active.id);
}

function sourcePicker() {
  const m = modal(`<h2>Cambiar de fuente</h2><div class="pick-list">
    ${S.data.sources.map((s) => `<button class="pick ${S.src && S.src.id === s.id ? 'on' : ''}" data-id="${s.id}"><span class="src-dot ${s.type}"></span>${esc(s.name)}</button>`).join('')}
    </div><div class="row end"><button class="btn ghost" data-close data-act="add-src">+ Agregar fuente</button></div>`);
  m.addEventListener('click', async (e) => {
    const b = e.target.closest('.pick');
    if (!b) return;
    m.close();
    if (!S.src || S.src.id !== b.dataset.id) { await activateSource(b.dataset.id); if (S.view === 'settings') renderSettings(); }
  });
}

init();
