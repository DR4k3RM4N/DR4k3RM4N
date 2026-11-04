const STORAGE_KEY = 'tiktok-monitor-v1';
const PARTITION = 'persist:tiktok'; // sesión compartida y guardada entre todos los lives
const LOGIN = '__login__';
const MONITOR_EVERY = 15000; // cada cuánto se revisa que cada live siga transmitiendo (ms)
const ALERT_AFTER = 45000;   // un live debe seguir mal este tiempo antes de avisar (ms)
const FREEZE_CHECKS = 4;     // revisiones seguidas con el video detenido para considerarlo congelado (~1 min)
const RETRY_EVERY = 60000;   // cada cuánto se reintenta un live caído (ms)
const RETRY_ENDED = 120000;  // cada cuánto se revisa si un live terminado volvió (ms)

const $ = (id) => document.getElementById(id);
const grid = $('grid');
const empty = $('empty');
const tpl = $('tileTpl');
const els = {
  form: $('addForm'), input: $('userInput'), cols: $('cols'), zoom: $('zoom'),
  autoReload: $('autoReload'), alerts: $('alerts'), view: $('view'), guides: $('guides'), autoPip: $('autoPip'), muteAll: $('muteAll'),
  reloadAll: $('reloadAll'), login: $('login'),
  favToggle: $('favToggle'), favPanel: $('favPanel'), favList: $('favList'),
  favEmpty: $('favEmpty'), favCount: $('favCount'), alertsBox: $('alertsBox'), ghost: $('dragGhost'),
};

let state = load();
const audible = new Set(); // usuarios que se están escuchando
let expanded = null;       // usuario ampliado
let reloadTimer = null;
let offline = !navigator.onLine;
const tiles = new Map();   // usuario -> { el, webview, statusEl, armed, alerted, badSince, lastTime, stuck, retry }

// ---------- Datos guardados ----------
function load() {
  const base = { lives: [], favorites: [], notes: {}, cols: 'auto', zoom: 'auto', autoReload: '0', alerts: 'all', favOpen: true, view: 'chat', tileView: {}, guides: 'off', tileGuides: {}, autoPip: 'on', audioOut: '', v: 5 };
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
  webview.setAttribute('webpreferences', 'backgroundThrottling=no');
  el.insertBefore(webview, noteEl);
  const t = { el, webview, statusEl, armed: false, alerted: false, badSince: null, lastTime: null, stuck: 0, retry: 0, loading: true };

  webview.addEventListener('dom-ready', () => {
    webview.setAudioMuted(!audible.has(user) || pipOpen.has(user));
    applyZoom(user);
    if (user !== LOGIN) {
      webview.executeJavaScript(LOCK_SCRIPT).catch(() => {});
      webview.executeJavaScript(window.MLT_AUDIO.pageScript(state.audioOut)).catch(() => {});
      webview.executeJavaScript(GUIDES_SCRIPT).then(() => applyGuides(user)).catch(() => {});
    }
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
  el.querySelector('.view').onclick = () => toggleTileView(user);
  el.querySelector('.pip').onclick = () => togglePip(user);
  el.querySelector('.guides').onclick = () => toggleTileGuides(user);
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
  if (pipOpen.has(user) && window.app) window.app.pipClose(user);
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
// Para evitar falsas alarmas, un live tiene que seguir mal durante ALERT_AFTER antes de avisar.
// Los cortes cortos (buffering, recargas, un segundo sin internet) ya no disparan alertas.
function setStatus(user, text, kind) {
  const t = tiles.get(user);
  if (!t) return;
  t.statusEl.textContent = text;
  t.statusEl.title = text;
  t.statusEl.dataset.kind = kind;
  if (kind === 'ok') {
    t.retry = 0;
    t.badSince = null;
    t.stuck = 0;
    if (t.alerted) { t.alerted = false; t.el.classList.remove('alert'); recovered(user); }
    t.armed = true; // estaba transmitiendo bien: si se cae, sí hay que avisar
  } else if (kind === 'bad') {
    if (!t.badSince) t.badSince = Date.now();
  }
  renderFavs();
}

// Revisión: textos que TikTok muestra cuando el live terminó y si el video sigue avanzando.
const ENDED = ['live has ended', 'live ended', 'ha finalizado', 'ha terminado', 'terminó el live', 'no está en live', 'is not live', 'live is over'];
const PROBE = `(() => {
  const text = document.body ? document.body.innerText.slice(0, 20000).toLowerCase() : '';
  const vids = [...document.querySelectorAll('video')].filter((v) => v.clientWidth > 50);
  const v = vids.sort((a, b) => b.clientWidth * b.clientHeight - a.clientWidth * a.clientHeight)[0];
  return { text, hasVideo: !!v, time: v ? v.currentTime : null, paused: v ? v.paused : null, ended: v ? v.ended : null };
})()`;
async function checkLive(user) {
  const t = tiles.get(user);
  if (!t || user === LOGIN) { if (t) setStatus(user, 'Abierto', 'ok'); return; }
  let r;
  try { r = await t.webview.executeJavaScript(PROBE); } catch { return; }
  if (!tiles.has(user) || t.loading) return;
  const advancing = r.hasVideo && t.lastTime !== null && Math.abs(r.time - t.lastTime) >= 0.05;
  const prevTime = t.lastTime;
  t.lastTime = r.hasVideo ? r.time : null;
  // "Terminado" solo cuenta si además no hay un video transmitiendo
  // (TikTok muestra textos de otros lives terminados en las recomendaciones).
  const playing = r.hasVideo && !r.paused && !r.ended;
  if (ENDED.some((w) => r.text.includes(w)) && !(playing && advancing)) return setStatus(user, 'Live terminado', 'bad');
  // Video congelado: solo se revisa con la app visible, la casilla a la vista y el video sin pausar.
  // Con la app minimizada Windows/Mac frenan el video y eso no es una caída.
  const visible = !appHidden() && !t.el.classList.contains('hidden');
  if (playing && visible && prevTime !== null && !advancing) {
    t.stuck++;
    if (t.stuck >= FREEZE_CHECKS) return setStatus(user, 'Señal detenida', 'bad');
    return; // todavía no se decide: se vuelve a revisar en la siguiente vuelta
  }
  t.stuck = 0;
  setStatus(user, 'En vivo', 'ok');
}

function monitor() {
  const now = Date.now();
  for (const [user, t] of tiles) {
    if (user === LOGIN) continue;
    const bad = t.statusEl.dataset.kind === 'bad';
    if (bad && t.badSince && t.armed && !t.alerted && now - t.badSince >= ALERT_AFTER && !offline) {
      t.alerted = true;
      t.armed = false;
      raiseAlert(user, t.statusEl.textContent);
    }
    if (offline || t.loading) continue;
    if (bad && t.badSince && now - t.badSince >= ALERT_AFTER) {
      // Live caído: se reintenta cada cierto tiempo para saber cuándo vuelve.
      t.retry += MONITOR_EVERY;
      const every = t.statusEl.textContent === 'Live terminado' ? RETRY_ENDED : RETRY_EVERY;
      if (t.retry >= every) { t.retry = 0; reloadLive(user); continue; }
    }
    checkLive(user);
  }
}

// Al volver a mostrar la app (después de minimizarla) se empieza a medir de cero.
let winHidden = false;
const appHidden = () => winHidden || document.hidden;
function resetFreeze() { tiles.forEach((t) => { t.lastTime = null; t.stuck = 0; }); }
document.addEventListener('visibilitychange', () => { if (!document.hidden) resetFreeze(); });
if (window.app && window.app.onWindowHidden) {
  window.app.onWindowHidden((hidden) => {
    winHidden = hidden;
    if (!hidden) resetFreeze();
    autoPip(hidden);
  });
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

// Las alertas que llegan casi juntas se agrupan en un solo sonido y un solo aviso del sistema,
// y el sonido no se repite más de una vez cada SOUND_GAP.
const SOUND_GAP = 15000;
let lastSound = 0;
let pending = [];
let pendingTimer = 0;
function raiseAlert(user, text, global = false) {
  if (state.alerts === 'off') return;
  if (!global) {
    const t = tiles.get(user);
    if (t) { t.el.classList.add('alert'); flash(user); }
  }
  const title = global ? 'Sin internet' : `@${user}`;
  toast(user, 'bad', '⚠️', title, `${global ? 'Se perdió la conexión' : text} · ${timeNow()}`);
  pending.push(global ? 'Se perdió la conexión a internet' : `@${user}: ${text}`);
  clearTimeout(pendingTimer);
  pendingTimer = setTimeout(flushAlerts, 1500);
}
function flushAlerts() {
  const items = pending;
  pending = [];
  if (!items.length || state.alerts === 'off') return;
  if (state.alerts === 'all' && Date.now() - lastSound > SOUND_GAP) { lastSound = Date.now(); sound(); }
  if (window.app) window.app.attention();
  try {
    const body = items.length === 1 ? items[0] : `${items.length} lives con problemas:\n${items.slice(0, 4).join('\n')}${items.length > 4 ? '\n…' : ''}`;
    const n = new Notification('RevoLabs MLT · Alerta', { body, icon: '../build/icon.png', silent: true });
    n.onclick = () => { if (window.app) window.app.showWindow(); };
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

// Internet: solo se avisa si la falta de conexión dura más de unos segundos.
let offlineTimer = 0;
let offlineAlerted = false;
window.addEventListener('offline', () => {
  offline = true;
  clearTimeout(offlineTimer);
  offlineTimer = setTimeout(() => { if (offline) { offlineAlerted = true; raiseAlert('__net__', '', true); } }, 15000);
});
window.addEventListener('online', () => {
  offline = false;
  clearTimeout(offlineTimer);
  dismissToast('__net__');
  if (offlineAlerted) toast('__net__', 'ok', '✅', 'Internet de vuelta', `Recargando los lives caídos · ${timeNow()}`, 6000);
  offlineAlerted = false;
  // Solo se recargan los lives que quedaron mal, no todos.
  tiles.forEach((t, u) => { if (u !== LOGIN && t.statusEl.dataset.kind === 'bad') reloadLive(u); });
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
    // Si el live está en la ventana flotante, el audio sale de ahí y no de la cuadrícula.
    try { t.webview.setAudioMuted(!on || pipOpen.has(u)); } catch {}
    t.el.classList.toggle('listening', on);
    t.el.querySelector('.audio').textContent = on ? '🔊' : '🔇';
  }
  const any = audible.size > 0;
  els.muteAll.innerHTML = any ? '🔇 <span class="lbl">Silenciar todo</span>' : '🔊 <span class="lbl">Activar todo</span>';
  els.muteAll.title = any ? 'Silenciar todos los lives (M)' : 'Activar el audio de todos los lives (M)';
  els.muteAll.classList.toggle('active-all', any);
  paintTvAudio();
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
  renderTileButtons();
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

// Zoom automático: TikTok acomoda su página según el ancho que "ve". Con la vista "Video + chat"
// se le hace creer que la casilla mide al menos VIEW_WIDTH.chat px, para que muestre el chat y
// los espectadores junto al video. Con "Solo video" se usa menos ancho y el video se ve más grande.
const VIEW_WIDTH = { chat: 1440, video: 900 };
const viewOf = (user) => state.tileView[user] || state.view;
function zoomFor(user) {
  if (state.zoom !== 'auto') return parseFloat(state.zoom);
  const t = tiles.get(user);
  const w = t ? t.webview.clientWidth || t.el.clientWidth : 800;
  if (!w) return 0.6;
  const target = VIEW_WIDTH[viewOf(user)] || VIEW_WIDTH.chat;
  return Math.round(Math.min(1, Math.max(0.25, w / target)) * 40) / 40;
}
function applyZoom(user) {
  const t = tiles.get(user);
  if (!t) return;
  const z = zoomFor(user);
  if (t.zoom === z) return;
  try { t.webview.setZoomFactor(z); t.zoom = z; } catch {}
}
function toggleTileView(user) {
  const next = viewOf(user) === 'chat' ? 'video' : 'chat';
  if (next === state.view) delete state.tileView[user]; else state.tileView[user] = next;
  if (state.zoom !== 'auto') { state.zoom = 'auto'; els.zoom.value = 'auto'; }
  save();
  renderTileButtons();
  applyZoom(user);
}

// ---------- Guías de encuadre ----------
// Se dibujan dentro de la página de TikTok, justo encima de la imagen del video
// (descontando las franjas negras), para revisar si el live está derecho y centrado.
const GUIDES_SCRIPT = `(() => {
  if (window.__mltGuides) return true;
  const box = document.createElement('div');
  box.id = '__mlt_guides';
  box.style.cssText = 'position:fixed;pointer-events:none;z-index:2147483647;display:none;outline:1px solid rgba(37,244,238,.9);';
  let mode = 'off';
  const line = (css) => '<div style="position:absolute;' + css + '"></div>';
  const C = 'rgba(37,244,238,.85)', F = 'rgba(255,255,255,.35)';
  const draw = () => {
    let h = '';
    const v = (p, c, w) => line('top:0;bottom:0;left:' + p + '%;width:' + (w || 1) + 'px;background:' + c);
    const hz = (p, c, w) => line('left:0;right:0;top:' + p + '%;height:' + (w || 1) + 'px;background:' + c);
    if (mode === 'grid') for (let i = 1; i < 10; i++) if (i !== 5) { h += v(i * 10, F); h += hz(i * 10, F); }
    if (mode === 'thirds' || mode === 'grid') { h += v(33.333, C); h += v(66.666, C); h += hz(33.333, C); h += hz(66.666, C); }
    if (mode === 'center' || mode === 'thirds' || mode === 'grid') {
      h += v(50, 'rgba(254,44,85,.9)'); h += hz(50, 'rgba(254,44,85,.9)');
      h += line('left:50%;top:50%;width:26px;height:26px;margin:-13px 0 0 -13px;border:1px solid rgba(254,44,85,.9);border-radius:50%');
    }
    box.innerHTML = h;
  };
  const place = () => {
    if (mode === 'off') { box.style.display = 'none'; return; }
    const vids = [...document.querySelectorAll('video')].filter((x) => x.clientWidth > 50);
    const vid = vids.sort((a, b) => b.clientWidth * b.clientHeight - a.clientWidth * a.clientHeight)[0];
    if (!vid) { box.style.display = 'none'; return; }
    const r = vid.getBoundingClientRect();
    let x = r.left, y = r.top, w = r.width, hh = r.height;
    const vw = vid.videoWidth, vh = vid.videoHeight;
    const fit = getComputedStyle(vid).objectFit;
    if (vw && vh && fit !== 'fill') {
      const sc = fit === 'cover' ? Math.max(w / vw, hh / vh) : Math.min(w / vw, hh / vh);
      const cw = vw * sc, ch = vh * sc;
      x += (w - cw) / 2; y += (hh - ch) / 2; w = cw; hh = ch;
      // Si la imagen se recorta (cover), las guías se limitan a lo que se ve.
      if (fit === 'cover') { const L = Math.max(x, r.left), T = Math.max(y, r.top); w = Math.min(x + w, r.right) - L; hh = Math.min(y + hh, r.bottom) - T; x = L; y = T; }
    }
    Object.assign(box.style, { display: 'block', left: x + 'px', top: y + 'px', width: w + 'px', height: hh + 'px' });
    if (!box.isConnected && document.body) document.body.appendChild(box);
  };
  setInterval(place, 400);
  window.__mltGuides = (m) => { mode = m; draw(); place(); };
  return true;
})()`;
const guidesOf = (user) => state.tileGuides[user] || state.guides;
function applyGuides(user) {
  const t = tiles.get(user);
  if (!t || user === LOGIN) return;
  t.webview.executeJavaScript(`window.__mltGuides && window.__mltGuides(${JSON.stringify(guidesOf(user))})`).catch(() => {});
}
function toggleTileGuides(user) {
  // En una casilla, el botón 📐 prende o apaga sus guías sin tocar las demás.
  const cur = guidesOf(user);
  const next = cur === 'off' ? (state.guides !== 'off' ? state.guides : 'thirds') : 'off';
  if (next === state.guides) delete state.tileGuides[user]; else state.tileGuides[user] = next;
  save();
  renderTileButtons();
  applyGuides(user);
}
function renderTileButtons() {
  for (const [u, t] of tiles) {
    const view = t.el.querySelector('.view');
    const chat = viewOf(u) === 'chat';
    view.classList.toggle('on', chat);
    view.title = chat ? 'Vista: video + chat y espectadores. Clic para ver solo el video más grande' : 'Vista: solo video. Clic para ver también el chat y los espectadores';
    const pip = t.el.querySelector('.pip');
    pip.classList.toggle('on', pipOpen.has(u));
    t.el.classList.toggle('in-pip', pipOpen.has(u));
    pip.title = pipOpen.has(u) ? 'Cerrar la ventana flotante' : 'Ventana flotante: siempre encima de todo';
    if (u === LOGIN) pip.style.display = 'none';
    const g = t.el.querySelector('.guides');
    const on = guidesOf(u) !== 'off';
    g.classList.toggle('on', on);
    g.title = on ? 'Ocultar guías de encuadre en este live (G: todas)' : 'Mostrar guías de encuadre en este live (G: todas)';
  }
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
els.view.value = state.view;
els.autoPip.value = state.autoPip;
els.autoPip.onchange = () => { state.autoPip = els.autoPip.value; save(); };
els.guides.value = state.guides;
els.view.onchange = () => {
  state.view = els.view.value;
  state.tileView = {};
  if (state.zoom !== 'auto') { state.zoom = 'auto'; els.zoom.value = 'auto'; }
  save();
  renderTileButtons();
  tiles.forEach((_t, u) => applyZoom(u));
};
els.guides.onchange = () => setGuides(els.guides.value);
function setGuides(mode) {
  state.guides = mode;
  state.tileGuides = {};
  els.guides.value = mode;
  save();
  renderTileButtons();
  tiles.forEach((_t, u) => applyGuides(u));
}
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
  else if (e.key === 't' || e.key === 'T') setTvMode(!tvMode);
  else if (e.key === 'Escape' && tvMode && !expanded) setTvMode(false);
  else if (e.key === 'g' || e.key === 'G') setGuides(state.guides === 'off' ? 'thirds' : 'off');
  else if (e.key === 'r' || e.key === 'R') els.reloadAll.click();
  else if (e.key === 'Escape' && expanded) { expanded = null; refresh(); }
});

// ---------- Ventana flotante ----------
const pipOpen = new Set();   // lives que están en ventana flotante
const pipAudio = new Map();  // usuario -> si la ventana flotante tiene el audio activado
function togglePip(user) {
  if (!window.app || user === LOGIN) return;
  if (pipOpen.has(user)) { window.app.pipClose(user); return; }
  openPip(user, false);
}
function openPip(user, auto) {
  const withAudio = audible.has(user);
  pipOpen.add(user);
  pipAudio.set(user, withAudio);
  window.app.pipOpen(user, withAudio, auto, state.audioOut);
  applyAudio();
  renderTileButtons();
}
// Al minimizar la app, el live que estás escuchando (o el seleccionado, o el primero) sale en ventana flotante.
function autoPip(hidden) {
  if (!window.app) return;
  if (!hidden) { window.app.pipCloseAuto(); return; }
  if (state.autoPip !== 'on' || pipOpen.size) return;
  const order = state.lives.map((l) => l.user).filter((u) => tiles.has(u));
  const pick = order.find((u) => audible.has(u)) || (selectedUser() !== LOGIN && selectedUser()) || order[0];
  if (pick) openPip(pick, true);
}
if (window.app && window.app.onPipClosed) {
  window.app.onPipClosed((user) => {
    pipOpen.delete(user);
    // Si en la ventana flotante estaba sonando, el audio regresa a la cuadrícula.
    if (pipAudio.get(user)) audible.add(user); else audible.delete(user);
    pipAudio.delete(user);
    applyAudio();
    renderTileButtons();
  });
  window.app.onPipAudio(({ user, on }) => pipAudio.set(user, on));
  window.app.onPipSelect((user) => { select(user); flash(user); });
}

// ---------- Ver en la TV y modo TV ----------
const isMacApp = window.app && window.app.info && window.app.info.platform === 'darwin';
const castModal = $('castModal');
function castSteps() {
  const steps = isMacApp ? [
    'Enciende la TV y en el control pulsa <b>Entrada / Input</b> → <b>AirPlay</b> o <b>Screen Mirroring</b> (en Hisense también aparece como <b>Anyview Cast</b>).',
    'En la Mac abre el <b>Centro de control</b> (arriba a la derecha) → <b>Duplicar pantalla</b> y elige tu TV Hisense.',
    'Si la TV muestra un código, escríbelo en la Mac.',
    'Pulsa <b>📺 Modo TV</b> para ver los lives en pantalla completa y con letra grande.',
    'Activa el audio del live que quieras oír (🔊 o teclas 1–9). Si no se escucha en la TV, elige la TV en <b>Salida de audio</b> y pulsa <b>Probar sonido</b>.',
  ] : [
    'Enciende la TV y en el control pulsa <b>Entrada / Input</b> → <b>Anyview Cast</b> (o <b>Screen Mirroring</b>). La TV y la PC deben estar en la misma red Wi-Fi.',
    'En la PC se abrió el panel <b>Transmitir</b> (abajo a la derecha). Elige tu TV Hisense en la lista. Si no se abrió, pulsa <b>Windows + K</b>.',
    'Si la TV pregunta, acepta la conexión con el control.',
    'Pulsa <b>📺 Modo TV</b> para ver los lives en pantalla completa y con letra grande.',
    'Activa el audio del live que quieras oír (🔊 o teclas 1–9). Si no se escucha en la TV, elige tu TV en <b>Salida de audio</b> y pulsa <b>Probar sonido</b>. También revisa que la TV no esté en silencio.',
  ];
  $('castSteps').innerHTML = steps.map((x) => `<li>${x}</li>`).join('');
  $('castTip').textContent = isMacApp
    ? 'No todas las TV Hisense tienen AirPlay. Si la tuya no aparece, conéctala a la Mac con un cable HDMI.'
    : 'Si se traba o se ve con retraso, acércate al módem o usa un cable HDMI (lo más estable). Para dejar de transmitir: Windows + K → Desconectar.';
}
async function fillAudioOut() {
  const sel = $('audioOut');
  const outs = await window.MLT_AUDIO.outputs();
  sel.length = 1;
  for (const d of outs) sel.add(new Option(d.label, d.label));
  // Si el dispositivo guardado ya no está conectado, se muestra igual para no perder la elección.
  if (state.audioOut && !outs.some((d) => d.label === state.audioOut)) sel.add(new Option(state.audioOut + ' (no conectado)', state.audioOut));
  sel.value = state.audioOut;
}
function setAudioOut(label) {
  state.audioOut = label;
  save();
  const code = window.MLT_AUDIO.pageScript(label);
  tiles.forEach((t, u) => { if (u !== LOGIN) t.webview.executeJavaScript(code).catch(() => {}); });
  // Las ventanas flotantes abiertas se reabren para tomar la nueva salida.
  [...pipOpen].forEach((u) => { const a = pipAudio.get(u); window.app.pipClose(u); setTimeout(() => { if (tiles.has(u)) { if (a) audible.add(u); openPip(u, false); } }, 400); });
}
$('audioOut').onchange = () => setAudioOut($('audioOut').value);
$('testTone').onclick = () => window.MLT_AUDIO.testTone(state.audioOut);
if (navigator.mediaDevices) navigator.mediaDevices.addEventListener('devicechange', () => { if (!castModal.hidden) fillAudioOut(); });
async function openCast() {
  castSteps();
  fillAudioOut();
  focusApp();
  castModal.hidden = false;
  if (window.app && window.app.cast) {
    try { await window.app.cast(); } catch {}
  }
}
$('castBtn').onclick = openCast;
$('castAgain').onclick = () => { if (window.app) window.app.cast(); };
$('castClose').onclick = () => { castModal.hidden = true; focusInput(); };
$('castTv').onclick = () => { castModal.hidden = true; setTvMode(true); };
castModal.addEventListener('mousedown', (e) => { if (e.target === castModal) { castModal.hidden = true; focusInput(); } });

let tvMode = false;
let tvTimer = 0;
let revealTimer = 0;
function setTvMode(on) {
  tvMode = on;
  document.body.classList.toggle('tv', on);
  $('tvHud').hidden = !on;
  if (window.app && window.app.setFullscreen) window.app.setFullscreen(on);
  clearInterval(tvTimer);
  if (on) { updateHud(); tvTimer = setInterval(updateHud, 1000); reveal(); }
  else document.body.classList.remove('reveal');
  setTimeout(layout, 300);
}
function paintTvAudio() {
  const b = $('tvAudio');
  if (!b) return;
  const on = [...audible];
  b.textContent = on.length ? `🔊 ${on.length === 1 ? '@' + on[0] : on.length + ' lives'}` : '🔇 Sin audio';
  b.classList.toggle('off', !on.length);
}
$('tvAudio').onclick = () => {
  // Sin audio: activa el live seleccionado (o el primero). Con audio: lo silencia.
  if (audible.size) { audible.clear(); applyAudio(); return; }
  const order = state.lives.map((l) => l.user).filter((u) => tiles.has(u));
  const u = (selectedUser() && selectedUser() !== LOGIN && selectedUser()) || order[0];
  if (u) toggleAudio(u);
};
function updateHud() {
  $('tvClock').textContent = new Date().toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit' });
  let ok = 0, bad = 0;
  tiles.forEach((t, u) => { if (u === LOGIN) return; if (t.statusEl.dataset.kind === 'bad') bad++; else if (t.statusEl.dataset.kind === 'ok') ok++; });
  $('tvSummary').innerHTML = `<span class="ok">${ok} en vivo</span>` + (bad ? ` · <span class="bad">${bad} con problemas</span>` : '');
}
// En modo TV los controles aparecen al mover el mouse y se esconden solos a los 3 segundos.
function reveal() {
  if (!tvMode) return;
  document.body.classList.add('reveal');
  clearTimeout(revealTimer);
  revealTimer = setTimeout(() => document.body.classList.remove('reveal'), 3000);
}
document.addEventListener('mousemove', reveal);
$('tvExit').onclick = () => setTvMode(false);

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
