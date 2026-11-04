const STORAGE_KEY = 'tiktok-monitor-v1';
const PARTITION = 'persist:tiktok'; // sesión compartida y guardada entre todos los lives
const LOGIN = '__login__';
const MONITOR_EVERY = 20000; // cada cuánto se revisa que cada live siga transmitiendo (ms)
const RETRY_EVERY = 45000;   // cada cuánto se reintenta un live caído (ms)

const $ = (id) => document.getElementById(id);
const grid = $('grid');
const empty = $('empty');
const tpl = $('tileTpl');
const els = {
  form: $('addForm'), input: $('userInput'), cols: $('cols'), zoom: $('zoom'),
  autoReload: $('autoReload'), alerts: $('alerts'), muteAll: $('muteAll'),
  reloadAll: $('reloadAll'), login: $('login'),
  favToggle: $('favToggle'), favPanel: $('favPanel'), favList: $('favList'),
  favEmpty: $('favEmpty'), favCount: $('favCount'), alertsBox: $('alertsBox'), ghost: $('dragGhost'),
};

let state = load();
const audible = new Set(); // usuarios que se están escuchando
let expanded = null;       // usuario ampliado
let reloadTimer = null;
let offline = !navigator.onLine;
const tiles = new Map();   // usuario -> { el, webview, statusEl, wasOk, alerted, lastTime, stuck, retry }

// ---------- Datos guardados ----------
function load() {
  const base = { lives: [], favorites: [], notes: {}, cols: 'auto', zoom: 'auto', autoReload: '0', alerts: 'all', favOpen: true, v: 5 };
  try {
    const s = JSON.parse(localStorage.getItem(STORAGE_KEY));
    if (s && Array.isArray(s.lives)) {
      const merged = { ...base, ...s };
      if (!s.v) {
        // Viene de la v0.4: se pasan las notas y se activa el zoom automático.
        for (const l of s.lives) if (l.note) merged.notes[l.user] = l.note;
        merged.zoom = 'auto';
        merged.v = 5;
      }
      return merged;
    }
  } catch {}
  return base;
}
function save() {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(state)); } catch {}
}

// Acepta "@usuario", "usuario" o un enlace de tiktok.com
function parseUser(text) {
  text = text.trim();
  const m = text.match(/tiktok\.com\/@([\w.\-]+)/i);
  const user = (m ? m[1] : text.replace(/^@/, '')).trim();
  return /^[\w.\-]{2,40}$/.test(user) ? user.toLowerCase() : null;
}
const liveUrl = (user) => `https://www.tiktok.com/@${user}/live`;
const isOwnLive = (user, url) => url.toLowerCase().includes(`/@${user}/live`);
const isFav = (user) => state.favorites.includes(user);
const realUsers = () => state.lives.map((l) => l.user).filter((u) => tiles.has(u));

// Se inyecta en cada live: evita que la rueda del mouse o las flechas hagan que TikTok
// cambie al siguiente live. El chat y la página siguen pudiendo desplazarse normalmente.
const LOCK_SCRIPT = `(() => {
  if (window.__monitorLock) return;
  window.__monitorLock = true;
  const block = (e) => e.stopImmediatePropagation();
  window.addEventListener('wheel', block, { capture: true });
  window.addEventListener('keydown', (e) => {
    const t = e.target;
    const typing = t && (t.isContentEditable || /^(INPUT|TEXTAREA)$/.test(t.tagName));
    if (!typing && ['ArrowUp', 'ArrowDown', 'PageUp', 'PageDown'].includes(e.key)) block(e);
  }, { capture: true });
})(); true`;

// ---------- Casillas ----------
function addLive(user) {
  if (tiles.has(user)) return flash(user);
  const el = tpl.content.firstElementChild.cloneNode(true);
  el.dataset.user = user;
  el.querySelector('.name').textContent = '@' + user;
  el.querySelector('.name').title = '@' + user;
  const statusEl = el.querySelector('.status');
  const noteEl = el.querySelector('.note');
  noteEl.value = state.notes[user] || '';

  const webview = document.createElement('webview');
  webview.setAttribute('partition', PARTITION);
  webview.setAttribute('src', liveUrl(user));
  webview.setAttribute('allowpopups', '');
  el.insertBefore(webview, noteEl);
  const t = { el, webview, statusEl, wasOk: false, alerted: false, lastTime: null, stuck: 0, retry: 0, loading: true };

  webview.addEventListener('dom-ready', () => {
    webview.setAudioMuted(!audible.has(user));
    applyZoom(user);
    if (user !== LOGIN) webview.executeJavaScript(LOCK_SCRIPT).catch(() => {});
  });
  // Si TikTok igual cambia a otro usuario, regresamos al live de esta casilla.
  const guard = (e) => {
    if (user === LOGIN || !e.url.startsWith('http') || isOwnLive(user, e.url)) return;
    if (/tiktok\.com\/@[^/]+\/live/i.test(e.url)) {
      setStatus(user, 'Regresando…', 'loading');
      webview.loadURL(liveUrl(user));
    }
  };
  webview.addEventListener('did-navigate', guard);
  webview.addEventListener('did-navigate-in-page', guard);
  let failed = false;
  webview.addEventListener('did-start-loading', () => {
    failed = false; t.loading = true; t.lastTime = null; t.stuck = 0;
    if (t.statusEl.dataset.kind !== 'bad') setStatus(user, 'Cargando…', 'loading');
  });
  webview.addEventListener('did-stop-loading', () => { t.loading = false; if (!failed) checkLive(user); });
  webview.addEventListener('did-fail-load', (e) => {
    if (e.errorCode === -3 || !e.isMainFrame) return; // -3 = navegación cancelada, no es error real
    failed = true;
    setStatus(user, offline ? 'Sin internet' : 'Sin conexión', 'bad');
  });
  webview.addEventListener('render-process-gone', () => setStatus(user, 'Se detuvo', 'bad'));

  el.addEventListener('mousedown', () => { select(user); clearAlert(user); });
  el.querySelector('.audio').onclick = (e) => { e.stopPropagation(); toggleAudio(user, e.ctrlKey || e.metaKey || e.shiftKey); };
  el.querySelector('.reload').onclick = () => reloadLive(user);
  el.querySelector('.expand').onclick = () => toggleExpand(user);
  el.querySelector('.open').onclick = () => window.open(liveUrl(user));
  el.querySelector('.remove').onclick = () => removeLive(user);
  const star = el.querySelector('.star');
  if (user === LOGIN) star.style.display = 'none';
  star.onclick = (e) => { e.stopPropagation(); toggleFav(user); };
  // Al soltar el mouse sobre la barra de la casilla, el teclado vuelve a la app (no al live).
  el.querySelector('.bar').addEventListener('mouseup', focusApp);
  el.querySelector('.bar').addEventListener('pointerdown', (e) => startDrag(e, user));
  el.querySelector('.bar').addEventListener('dblclick', (e) => { if (!e.target.closest('button')) toggleExpand(user); });
  noteEl.addEventListener('input', () => {
    if (noteEl.value) state.notes[user] = noteEl.value; else delete state.notes[user];
    save();
  });

  grid.appendChild(el);
  tiles.set(user, t);
  if (user !== LOGIN && !state.lives.some((l) => l.user === user)) { state.lives.push({ user }); save(); }
  refresh();
}

async function removeLive(user, confirmFirst = true) {
  const t = tiles.get(user);
  if (!t) return;
  if (confirmFirst && user !== LOGIN) {
    const extra = isFav(user) ? ' Seguirá en tus favoritas.' : '';
    if (!(await ask(`¿Quitar @${user} del monitor?${extra}`))) return;
  }
  t.el.remove();
  tiles.delete(user);
  state.lives = state.lives.filter((l) => l.user !== user);
  audible.delete(user);
  if (expanded === user) expanded = null;
  dismissToast(user);
  save();
  refresh();
  applyAudio();
  focusInput();
}

function reloadLive(user) {
  const t = tiles.get(user);
  if (!t) return;
  t.webview.loadURL(user === LOGIN ? 'https://www.tiktok.com/login' : liveUrl(user));
}

// Ventana de confirmación propia. El confirm() nativo dejaba la barra sin teclado en Windows.
function ask(text) {
  const modal = $('modal');
  $('modalText').textContent = text;
  modal.hidden = false;
  return new Promise((resolve) => {
    const done = (v) => { modal.hidden = true; document.removeEventListener('keydown', onKey, true); resolve(v); };
    const onKey = (e) => {
      if (e.key === 'Escape') { e.stopPropagation(); done(false); }
      if (e.key === 'Enter') { e.stopPropagation(); done(true); }
    };
    $('modalYes').onclick = () => done(true);
    $('modalNo').onclick = () => done(false);
    document.addEventListener('keydown', onKey, true);
    focusApp();
    $('modalYes').focus();
  });
}

function focusApp() {
  if (document.activeElement && document.activeElement.tagName === 'WEBVIEW') document.activeElement.blur();
  if (window.app) window.app.focusMain();
}
function focusInput() {
  focusApp();
  setTimeout(() => els.input.focus(), 0);
}

// ---------- Estado y alertas de desconexión ----------
function setStatus(user, text, kind) {
  const t = tiles.get(user);
  if (!t) return;
  t.statusEl.textContent = text;
  t.statusEl.title = text;
  t.statusEl.dataset.kind = kind;
  if (kind === 'ok') {
    t.retry = 0;
    if (t.alerted) { t.alerted = false; t.el.classList.remove('alert'); recovered(user); }
    t.wasOk = true;
  } else if (kind === 'bad') {
    // Solo se avisa cuando un live que estaba bien se cae (no al abrir uno que ya terminó).
    if (t.wasOk && !t.alerted && user !== LOGIN) { t.alerted = true; raiseAlert(user, text); }
    t.wasOk = false;
  }
  renderFavs();
}

// Revisión aproximada: textos que TikTok muestra cuando el live terminó y si el video sigue avanzando.
const ENDED = ['live has ended', 'live ended', 'ha finalizado', 'ha terminado', 'terminó el live', 'no está en live', 'is not live', 'live is over'];
const PROBE = `(() => {
  const text = document.body ? document.body.innerText.slice(0, 20000).toLowerCase() : '';
  const v = [...document.querySelectorAll('video')].sort((a, b) => b.clientWidth - a.clientWidth)[0];
  return { text, hasVideo: !!v, time: v ? v.currentTime : null, paused: v ? v.paused : null };
})()`;
async function checkLive(user) {
  const t = tiles.get(user);
  if (!t || user === LOGIN) { if (t) setStatus(user, 'Abierto', 'ok'); return; }
  let r;
  try { r = await t.webview.executeJavaScript(PROBE); } catch { return setStatus(user, 'Abierto', 'ok'); }
  if (!tiles.has(user)) return;
  if (ENDED.some((w) => r.text.includes(w))) return setStatus(user, 'Live terminado', 'bad');
  // Video congelado: el live estaba avanzando y dejó de hacerlo en dos revisiones seguidas.
  // No se revisa si la casilla está oculta (al ampliar otra) o si alguien lo pausó.
  const visible = !t.el.classList.contains('hidden');
  if (r.hasVideo && !r.paused && visible && t.lastTime !== null && Math.abs(r.time - t.lastTime) < 0.05) {
    t.stuck++;
    if (t.stuck >= 2) return setStatus(user, 'Señal detenida', 'bad');
  } else {
    t.stuck = 0;
  }
  t.lastTime = r.hasVideo ? r.time : null;
  if (t.statusEl.dataset.kind !== 'bad' || t.stuck === 0) setStatus(user, 'En vivo', 'ok');
}

function monitor() {
  if (offline) return;
  for (const [user, t] of tiles) {
    if (user === LOGIN || t.loading) continue;
    if (t.statusEl.dataset.kind === 'bad') {
      // Live caído: se reintenta solo cada cierto tiempo para saber cuándo vuelve.
      t.retry += MONITOR_EVERY;
      if (t.retry >= RETRY_EVERY) { t.retry = 0; reloadLive(user); }
      else checkLive(user);
    } else {
      checkLive(user);
    }
  }
}

const sound = (() => {
  let ctx;
  return () => {
    try {
      ctx = ctx || new AudioContext();
      const now = ctx.currentTime;
      [0, 0.22, 0.44].forEach((d, i) => {
        const o = ctx.createOscillator();
        const g = ctx.createGain();
        o.type = 'sine';
        o.frequency.value = i % 2 ? 660 : 880;
        g.gain.setValueAtTime(0.0001, now + d);
        g.gain.exponentialRampToValueAtTime(0.35, now + d + 0.02);
        g.gain.exponentialRampToValueAtTime(0.0001, now + d + 0.18);
        o.connect(g).connect(ctx.destination);
        o.start(now + d);
        o.stop(now + d + 0.2);
      });
    } catch {}
  };
})();

function timeNow() {
  return new Date().toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit' });
}

function raiseAlert(user, text, global = false) {
  if (state.alerts === 'off') return;
  if (!global) {
    const t = tiles.get(user);
    if (t) { t.el.classList.add('alert'); flash(user); }
  }
  const title = global ? 'Sin internet' : `@${user}`;
  toast(user, 'bad', '⚠️', title, `${global ? 'Se perdió la conexión' : text} · ${timeNow()}`);
  if (state.alerts === 'all') sound();
  if (window.app) window.app.attention();
  try {
    const n = new Notification('RevoLabs MLT · Alerta', {
      body: global ? 'Se perdió la conexión a internet.' : `@${user}: ${text}`,
      icon: '../build/icon.png', silent: true,
    });
    n.onclick = () => { if (window.app) window.app.showWindow(); if (!global) select(user); };
  } catch {}
}

function recovered(user) {
  if (state.alerts === 'off') return dismissToast(user);
  toast(user, 'ok', '✅', `@${user}`, `Volvió a transmitir · ${timeNow()}`, 6000);
}

function clearAlert(user) {
  const t = tiles.get(user);
  if (t) t.el.classList.remove('alert');
  dismissToast(user);
}

function toast(key, kind, icon, title, detail, autoHide = 0) {
  dismissToast(key);
  const el = document.createElement('div');
  el.className = 'toast ' + kind;
  el.dataset.key = key;
  el.innerHTML = '<span class="ticon"></span><div class="ttext"><b></b><span></span></div>';
  el.querySelector('.ticon').textContent = icon;
  el.querySelector('b').textContent = title;
  el.querySelector('.ttext span').textContent = detail;
  if (tiles.has(key)) {
    const see = document.createElement('button');
    see.textContent = 'Ver';
    see.onclick = () => { select(key); tiles.get(key) && tiles.get(key).el.scrollIntoView({ block: 'nearest' }); flash(key); clearAlert(key); };
    el.appendChild(see);
  }
  const close = document.createElement('button');
  close.textContent = '✕';
  close.title = 'Cerrar aviso';
  close.onclick = () => clearAlert(key);
  el.appendChild(close);
  els.alertsBox.appendChild(el);
  while (els.alertsBox.children.length > 6) els.alertsBox.firstElementChild.remove();
  if (autoHide) setTimeout(() => { if (el.isConnected) el.remove(); }, autoHide);
}
function dismissToast(key) {
  for (const el of els.alertsBox.querySelectorAll('.toast')) if (el.dataset.key === key) el.remove();
}

window.addEventListener('offline', () => {
  offline = true;
  raiseAlert('__net__', '', true);
});
window.addEventListener('online', () => {
  offline = false;
  dismissToast('__net__');
  toast('__net__', 'ok', '✅', 'Internet de vuelta', `Recargando los lives · ${timeNow()}`, 6000);
  tiles.forEach((t, u) => { if (u !== LOGIN) reloadLive(u); });
});

// ---------- Audio ----------
function toggleAudio(user, additive = false) {
  if (additive) {
    if (audible.has(user)) audible.delete(user); else audible.add(user);
  } else if (audible.has(user) && audible.size === 1) {
    audible.clear();
  } else {
    audible.clear();
    audible.add(user);
  }
  applyAudio();
}
function toggleAudioAll() {
  if (audible.size) audible.clear();
  else realUsers().forEach((u) => audible.add(u));
  applyAudio();
}
function applyAudio() {
  for (const [u, t] of tiles) {
    const on = audible.has(u);
    try { t.webview.setAudioMuted(!on); } catch {}
    t.el.classList.toggle('listening', on);
    t.el.querySelector('.audio').textContent = on ? '🔊' : '🔇';
  }
  const any = audible.size > 0;
  els.muteAll.innerHTML = any ? '🔇 <span class="lbl">Silenciar todo</span>' : '🔊 <span class="lbl">Activar todo</span>';
  els.muteAll.title = any ? 'Silenciar todos los lives (M)' : 'Activar el audio de todos los lives (M)';
  els.muteAll.classList.toggle('active-all', any);
}

// ---------- Favoritas ----------
function toggleFav(user) {
  if (isFav(user)) state.favorites = state.favorites.filter((u) => u !== user);
  else state.favorites.push(user);
  save();
  renderFavs();
}
function renderFavs() {
  els.favCount.textContent = state.favorites.length;
  els.favEmpty.hidden = state.favorites.length > 0;
  els.favList.textContent = '';
  for (const user of state.favorites) {
    const t = tiles.get(user);
    const li = document.createElement('li');
    li.className = 'fav-item' + (t ? ' open' : '') + (t && t.statusEl.dataset.kind === 'bad' ? ' bad' : '');
    li.title = t ? 'Abierto · clic para cerrarlo de la cuadrícula' : 'Cerrado · clic para abrirlo';
    li.innerHTML = '<span class="state"></span><span class="fname"></span><span class="fhint"></span><button title="Quitar de favoritas">✕</button>';
    li.querySelector('.fname').textContent = '@' + user;
    li.querySelector('.fhint').textContent = t ? 'abierto' : 'cerrado';
    li.onclick = () => { if (tiles.has(user)) removeLive(user, false); else addLive(user); };
    li.querySelector('button').onclick = (e) => { e.stopPropagation(); toggleFav(user); };
    els.favList.appendChild(li);
  }
  for (const [u, t] of tiles) {
    const star = t.el.querySelector('.star');
    star.classList.toggle('on', isFav(u));
    star.textContent = isFav(u) ? '★' : '☆';
    star.title = isFav(u) ? 'Quitar de favoritas' : 'Marcar como favorita';
  }
}
function setFavPanel(open) {
  state.favOpen = open;
  save();
  els.favPanel.hidden = !open;
  els.favToggle.classList.toggle('on', open);
  layout();
}

// ---------- Arrastrar y soltar para reordenar ----------
let drag = null;
function startDrag(e, user) {
  if (e.button !== 0 || user === LOGIN || expanded || e.target.closest('button, input')) return;
  drag = { user, x: e.clientX, y: e.clientY, active: false, target: null, after: false };
  e.currentTarget.setPointerCapture(e.pointerId);
  e.currentTarget.addEventListener('pointermove', onDragMove);
  e.currentTarget.addEventListener('pointerup', endDrag, { once: true });
  e.currentTarget.addEventListener('pointercancel', endDrag, { once: true });
}
function onDragMove(e) {
  if (!drag) return;
  if (!drag.active) {
    if (Math.hypot(e.clientX - drag.x, e.clientY - drag.y) < 6) return;
    drag.active = true;
    document.body.classList.add('dragging');
    tiles.get(drag.user).el.classList.add('drag-src');
    els.ghost.textContent = '@' + drag.user;
    els.ghost.hidden = false;
  }
  els.ghost.style.left = e.clientX + 'px';
  els.ghost.style.top = e.clientY + 'px';
  clearDropMarks();
  const over = document.elementFromPoint(e.clientX, e.clientY);
  const tile = over && over.closest('.tile');
  drag.target = null;
  if (tile && tile.dataset.user !== drag.user) {
    const r = tile.getBoundingClientRect();
    drag.target = tile.dataset.user;
    drag.after = e.clientX > r.left + r.width / 2;
    tile.classList.add(drag.after ? 'drop-after' : 'drop-before');
  }
  // Si hay muchos lives y la cuadrícula tiene scroll, se desplaza al acercarse al borde.
  const g = grid.getBoundingClientRect();
  if (e.clientY > g.bottom - 40) grid.scrollTop += 12;
  else if (e.clientY < g.top + 40) grid.scrollTop -= 12;
}
function endDrag(e) {
  e.currentTarget.removeEventListener('pointermove', onDragMove);
  if (!drag) return;
  const { user, active, target, after } = drag;
  drag = null;
  document.body.classList.remove('dragging');
  els.ghost.hidden = true;
  clearDropMarks();
  const src = tiles.get(user);
  if (src) src.el.classList.remove('drag-src');
  if (!active || !target) return;
  const item = state.lives.find((l) => l.user === user);
  state.lives = state.lives.filter((l) => l.user !== user);
  const idx = state.lives.findIndex((l) => l.user === target);
  state.lives.splice(after ? idx + 1 : idx, 0, item);
  save();
  refresh();
  flash(user);
}
function clearDropMarks() {
  grid.querySelectorAll('.drop-before, .drop-after').forEach((el) => el.classList.remove('drop-before', 'drop-after'));
}

// ---------- Selección, ampliar, cuadrícula ----------
function select(user) {
  for (const [u, t] of tiles) t.el.classList.toggle('selected', u === user);
}
function selectedUser() {
  for (const [u, t] of tiles) if (t.el.classList.contains('selected')) return u;
  return null;
}
function toggleExpand(user) {
  expanded = expanded === user ? null : user;
  refresh();
}
function flash(user) {
  const t = tiles.get(user);
  if (!t) return;
  t.el.classList.remove('flash');
  void t.el.offsetWidth;
  t.el.classList.add('flash');
}

// El orden se cambia con la propiedad CSS "order" y no moviendo los elementos,
// porque mover un live en la página lo recargaría.
function refresh() {
  const order = [...state.lives.map((l) => l.user).filter((u) => tiles.has(u)), ...(tiles.has(LOGIN) ? [LOGIN] : [])];
  empty.style.display = tiles.size ? 'none' : 'flex';
  order.forEach((u, i) => {
    const t = tiles.get(u);
    t.el.style.order = i;
    t.el.querySelector('.num').textContent = i + 1;
    t.el.classList.toggle('hidden', !!expanded && u !== expanded);
    t.el.querySelector('.expand').textContent = expanded === u ? '⤡' : '⤢';
    t.el.querySelector('.expand').title = expanded === u ? 'Volver a la cuadrícula (Esc)' : 'Ampliar (F)';
  });
  renderFavs();
  layout();
}

// Elige columnas y filas para que cada live quede lo más grande posible según el tamaño de la ventana.
const MIN_TILE_H = 200;
const TILE_RATIO = 4 / 3; // proporción aproximada que mejor muestra un live con su chat
function bestCols(n, W, H) {
  let best = 1, bestScore = -1;
  for (let c = 1; c <= Math.min(n, 8); c++) {
    const r = Math.ceil(n / c);
    const w = W / c, h = H / r;
    const fitW = Math.min(w, h * TILE_RATIO);
    const score = fitW * (fitW / TILE_RATIO) - (c * r - n) * 1; // menos huecos vacíos de desempate
    if (score > bestScore) { bestScore = score; best = c; }
  }
  return best;
}
function layout() {
  const n = expanded ? 1 : [...tiles.values()].length;
  if (!n) return;
  const W = grid.clientWidth - 12, H = grid.clientHeight - 12;
  const cols = expanded ? 1 : state.cols === 'auto' ? bestCols(n, W, H) : parseInt(state.cols, 10);
  const rows = Math.max(1, Math.ceil(n / cols));
  grid.style.gridTemplateColumns = `repeat(${cols}, minmax(0, 1fr))`;
  // Si no caben todos con una altura mínima cómoda, la cuadrícula hace scroll en lugar de aplastarlos.
  grid.style.gridTemplateRows = `repeat(${rows}, minmax(${expanded ? 0 : MIN_TILE_H}px, 1fr))`;
  if (state.zoom === 'auto') tiles.forEach((_t, u) => applyZoom(u));
}

// Zoom automático: el contenido de TikTok se achica o agranda según el ancho de cada casilla.
function zoomFor(user) {
  if (state.zoom !== 'auto') return parseFloat(state.zoom);
  const t = tiles.get(user);
  const w = t ? t.el.clientWidth : 800;
  if (!w) return 0.67;
  return Math.round(Math.min(1, Math.max(0.35, w / 1100)) * 20) / 20;
}
function applyZoom(user) {
  const t = tiles.get(user);
  if (!t) return;
  const z = zoomFor(user);
  if (t.zoom === z) return;
  try { t.webview.setZoomFactor(z); t.zoom = z; } catch {}
}

let resizeRaf = 0;
new ResizeObserver(() => {
  cancelAnimationFrame(resizeRaf);
  resizeRaf = requestAnimationFrame(layout);
}).observe(grid);

function setAutoReload() {
  clearInterval(reloadTimer);
  const min = parseInt(state.autoReload, 10);
  if (min > 0) reloadTimer = setInterval(() => els.reloadAll.click(), min * 60000);
}

// ---------- Controles de la barra ----------
els.form.addEventListener('submit', (e) => {
  e.preventDefault();
  const user = parseUser(els.input.value);
  const field = els.input.parentElement;
  if (!user) { field.classList.add('error'); return; }
  field.classList.remove('error');
  els.input.value = '';
  addLive(user);
  focusInput(); // listo para escribir el siguiente usuario
});
// Hacer clic en cualquier parte de la barra devuelve el teclado a la búsqueda.
els.input.addEventListener('mousedown', focusInput);
els.input.parentElement.addEventListener('mousedown', focusInput);
// El @ ya está escrito; si alguien lo pega o lo teclea, se quita.
els.input.addEventListener('input', () => {
  if (els.input.value.startsWith('@')) els.input.value = els.input.value.replace(/^@+/, '');
});
// Ctrl+K o / desde cualquier lugar lleva a la barra de búsqueda.
document.addEventListener('keydown', (e) => {
  if (((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') || (e.key === '/' && e.target.tagName !== 'INPUT')) {
    e.preventDefault();
    focusInput();
  }
}, true);

els.cols.value = state.cols;
els.zoom.value = state.zoom;
els.autoReload.value = state.autoReload;
els.alerts.value = state.alerts;
els.cols.onchange = () => { state.cols = els.cols.value; save(); layout(); };
els.zoom.onchange = () => {
  state.zoom = els.zoom.value; save();
  tiles.forEach((_t, u) => applyZoom(u));
};
els.autoReload.onchange = () => { state.autoReload = els.autoReload.value; save(); setAutoReload(); };
els.alerts.onchange = () => {
  state.alerts = els.alerts.value; save();
  if (state.alerts === 'all') sound(); // muestra cómo suena la alerta
};
els.muteAll.onclick = toggleAudioAll;
els.reloadAll.onclick = () => tiles.forEach((_t, u) => { if (u !== LOGIN) reloadLive(u); });
els.favToggle.onclick = () => setFavPanel(els.favPanel.hidden);
$('favClose').onclick = () => setFavPanel(false);
$('favOpenAll').onclick = () => state.favorites.forEach((u) => { if (!tiles.has(u)) addLive(u); });
$('favCloseAll').onclick = () => [...tiles.keys()].forEach((u) => { if (u !== LOGIN && !isFav(u)) removeLive(u, false); });
els.login.onclick = () => {
  // Abre TikTok en una casilla temporal ampliada para iniciar sesión; la sesión se comparte con todos.
  if (tiles.has(LOGIN)) return toggleExpand(LOGIN);
  addLive(LOGIN);
  const t = tiles.get(LOGIN);
  t.webview.setAttribute('src', 'https://www.tiktok.com/login');
  t.el.querySelector('.name').textContent = 'Inicio de sesión (quítala al terminar)';
  expanded = LOGIN; refresh();
};

// Atajos de teclado (cuando el foco no está en un campo de texto)
document.addEventListener('keydown', (e) => {
  if (e.key === 'F11') { e.preventDefault(); if (window.app) window.app.toggleFullscreen(); return; }
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;
  const users = [...state.lives.map((l) => l.user).filter((u) => tiles.has(u))];
  if (/^[1-9]$/.test(e.key) && users[+e.key - 1]) { toggleAudio(users[+e.key - 1], e.ctrlKey || e.shiftKey); select(users[+e.key - 1]); }
  else if (e.key === 'f' || e.key === 'F') { const u = selectedUser(); if (u) toggleExpand(u); }
  else if (e.key === 'm' || e.key === 'M') toggleAudioAll();
  else if (e.key === 'r' || e.key === 'R') els.reloadAll.click();
  else if (e.key === 'Escape' && expanded) { expanded = null; refresh(); }
});

// ---------- Versión y "Acerca de" ----------
const info = (window.app && window.app.info) || { version: '' };
$('ver').textContent = 'v' + info.version;
$('aboutVer').textContent = info.version;
const aboutModal = $('aboutModal');
$('about').onclick = () => { focusApp(); aboutModal.hidden = false; };
$('aboutClose').onclick = () => { aboutModal.hidden = true; focusInput(); };
aboutModal.addEventListener('mousedown', (e) => { if (e.target === aboutModal) { aboutModal.hidden = true; focusInput(); } });

// ---------- Arranque ----------
els.favPanel.hidden = !state.favOpen;
els.favToggle.classList.toggle('on', state.favOpen);
state.lives = state.lives.filter((l) => l && l.user && l.user !== LOGIN);
state.lives.forEach((l) => addLive(l.user));
setAutoReload();
setInterval(monitor, MONITOR_EVERY);
refresh();
applyAudio();
focusInput();
