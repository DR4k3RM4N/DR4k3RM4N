// Reproductor: HLS (hls.js), MPEG-TS/FLV (mpegts.js) y nativo (MP4, WebM, MKV).
// Si un motor falla prueba el siguiente; en vivo se reconecta solo.
'use strict';

const ICONS = {
  play: '<svg viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>',
  pause: '<svg viewBox="0 0 24 24"><path d="M6 5h4v14H6zM14 5h4v14h-4z"/></svg>',
  back: '<svg viewBox="0 0 24 24"><path d="M15.4 7.4 14 6l-6 6 6 6 1.4-1.4L10.8 12z"/></svg>',
  close: '<svg viewBox="0 0 24 24"><path d="M19 6.4 17.6 5 12 10.6 6.4 5 5 6.4 10.6 12 5 17.6 6.4 19 12 13.4 17.6 19 19 17.6 13.4 12z"/></svg>',
  rew: '<svg viewBox="0 0 24 24"><path d="M12 5V1L7 6l5 5V7a6 6 0 1 1-6 6H4a8 8 0 1 0 8-8z"/><text x="12" y="16.5" font-size="6.5" text-anchor="middle" font-family="sans-serif" font-weight="700">10</text></svg>',
  fwd: '<svg viewBox="0 0 24 24"><path d="M12 5V1l5 5-5 5V7a6 6 0 1 0 6 6h2a8 8 0 1 1-8-8z"/><text x="12" y="16.5" font-size="6.5" text-anchor="middle" font-family="sans-serif" font-weight="700">10</text></svg>',
  up: '<svg viewBox="0 0 24 24"><path d="M7.4 15.4 12 10.8l4.6 4.6L18 14l-6-6-6 6z"/></svg>',
  down: '<svg viewBox="0 0 24 24"><path d="M7.4 8.6 12 13.2l4.6-4.6L18 10l-6 6-6-6z"/></svg>',
  vol: '<svg viewBox="0 0 24 24"><path d="M3 9v6h4l5 5V4L7 9zm13.5 3A4.5 4.5 0 0 0 14 8v8a4.5 4.5 0 0 0 2.5-4zM14 3.2v2.1a7 7 0 0 1 0 13.4v2.1a9 9 0 0 0 0-17.6z"/></svg>',
  mute: '<svg viewBox="0 0 24 24"><path d="M16.5 12A4.5 4.5 0 0 0 14 8v2.2l2.5 2.5zM19 12a7 7 0 0 1-.6 2.8l1.5 1.5A9 9 0 0 0 14 3.2v2.1A7 7 0 0 1 19 12zM4.3 3 3 4.3 7.7 9H3v6h4l5 5v-6.7l4.3 4.3a7 7 0 0 1-2.3 1.2v2.1a9 9 0 0 0 3.7-1.8l2 2 1.3-1.3zM12 4 9.9 6.1 12 8.2z"/></svg>',
  list: '<svg viewBox="0 0 24 24"><path d="M3 5h2v2H3zm4 0h14v2H7zM3 11h2v2H3zm4 0h14v2H7zm-4 6h2v2H3zm4 0h14v2H7z"/></svg>',
  gear: '<svg viewBox="0 0 24 24"><path d="M19.4 13a7.5 7.5 0 0 0 0-2l2.1-1.6-2-3.5-2.5 1a7.3 7.3 0 0 0-1.7-1L15 3h-4l-.4 2.9a7.3 7.3 0 0 0-1.7 1l-2.5-1-2 3.5L6.6 11a7.5 7.5 0 0 0 0 2l-2.1 1.6 2 3.5 2.5-1a7.3 7.3 0 0 0 1.7 1L11 21h4l.4-2.9a7.3 7.3 0 0 0 1.7-1l2.5 1 2-3.5zM13 15.5a3.5 3.5 0 1 1 0-7 3.5 3.5 0 0 1 0 7z" transform="translate(-1 0)"/></svg>',
  ext: '<svg viewBox="0 0 24 24"><path d="M14 3v2h3.6l-9.8 9.8 1.4 1.4L19 6.4V10h2V3zM19 19H5V5h7V3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7h-2z"/></svg>',
  pip: '<svg viewBox="0 0 24 24"><path d="M19 11h-8v6h8zm4 8V5a2 2 0 0 0-2-2H3a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h18a2 2 0 0 0 2-2zm-2 0H3V5h18z"/></svg>',
  expand: '<svg viewBox="0 0 24 24"><path d="M7 14H5v5h5v-2H7zm-2-4h2V7h3V5H5zm12 7h-3v2h5v-5h-2zM14 5v2h3v3h2V5z"/></svg>',
  shrink: '<svg viewBox="0 0 24 24"><path d="M5 16h3v3h2v-5H5zm3-8H5v2h5V5H8zm6 11h2v-3h3v-2h-5zm2-11V5h-2v5h5V8z"/></svg>',
  heart: '<svg viewBox="0 0 24 24"><path d="M12 21.4 10.6 20C5.4 15.4 2 12.3 2 8.5 2 5.4 4.4 3 7.5 3c1.7 0 3.4.8 4.5 2.1A6 6 0 0 1 16.5 3C19.6 3 22 5.4 22 8.5c0 3.8-3.4 6.9-8.6 11.5z"/></svg>',
  heartO: '<svg viewBox="0 0 24 24"><path d="M16.5 3A6 6 0 0 0 12 5.1 6 6 0 0 0 7.5 3 5.5 5.5 0 0 0 2 8.5c0 3.8 3.4 6.9 8.6 11.5l1.4 1.3 1.4-1.3c5.2-4.6 8.6-7.7 8.6-11.5A5.5 5.5 0 0 0 16.5 3zm-4.4 15.6-.1.1-.1-.1C7.1 14.2 4 11.4 4 8.5 4 6.5 5.5 5 7.5 5c1.5 0 3 1 3.6 2.4h1.9C13.5 6 15 5 16.5 5c2 0 3.5 1.5 3.5 3.5 0 2.9-3.1 5.7-7.9 10.1z"/></svg>',
};

const fmtTime = (s) => {
  if (!isFinite(s) || s < 0) s = 0;
  s = Math.floor(s);
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
  return (h ? h + ':' + String(m).padStart(2, '0') : m) + ':' + String(sec).padStart(2, '0');
};
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

class Player {
  constructor(root, opts = {}) {
    this.root = root;
    this.opts = opts; // {getSettings, saveSettings, onClose, onExternal, onFavorite}
    this.ctx = null;
    this.mode = 'hidden';
    this.engine = null;
    this.hls = null;
    this.mpegts = null;
    this.tried = [];
    this.retries = 0;
    this.playingOnce = false;
    this.numBuffer = '';
    this.root.innerHTML = `
      <video playsinline></video>
      <div class="p-shade"></div>
      <div class="p-loading"><div class="spinner"></div><div class="p-loading-txt">Cargando...</div></div>
      <div class="p-error hidden"><div class="p-error-box">
        <div class="p-error-title">No se pudo reproducir</div>
        <div class="p-error-msg"></div>
        <div class="p-error-actions">
          <button class="btn primary" data-a="retry">Reintentar</button>
          <button class="btn" data-a="external">Abrir en VLC</button>
          <button class="btn ghost" data-a="close">Cerrar</button>
        </div></div></div>
      <div class="p-top">
        <button class="p-ib" data-a="close" title="Volver (Esc)">${ICONS.back}</button>
        <img class="p-logo hidden" alt="">
        <div class="p-titles"><div class="p-title"></div><div class="p-sub"></div></div>
        <button class="p-ib p-fav hidden" data-a="fav" title="Favorito">${ICONS.heartO}</button>
        <div class="p-clock"></div>
      </div>
      <div class="p-bottom">
        <div class="p-epg hidden">
          <div class="p-epg-now"><span class="badge onair">EN VIVO</span><span class="p-epg-title"></span><span class="p-epg-time"></span></div>
          <div class="p-epg-bar"><i></i></div>
          <div class="p-epg-next"></div>
        </div>
        <div class="p-seek hidden">
          <span class="p-cur">0:00</span>
          <div class="p-track"><div class="p-buf"></div><div class="p-fill"></div><div class="p-hover-t hidden"></div><input type="range" min="0" max="1000" value="0" step="1" aria-label="Posición"></div>
          <span class="p-dur">0:00</span>
        </div>
        <div class="p-ctrls">
          <div class="p-left">
            <button class="p-ib live-only" data-a="prev" title="Canal anterior (Flecha arriba)">${ICONS.up}</button>
            <button class="p-ib big" data-a="toggle" title="Pausa (Espacio)">${ICONS.pause}</button>
            <button class="p-ib live-only" data-a="next" title="Canal siguiente (Flecha abajo)">${ICONS.down}</button>
            <button class="p-ib vod-only" data-a="rew" title="-10 s (Flecha izquierda)">${ICONS.rew}</button>
            <button class="p-ib vod-only" data-a="fwd" title="+10 s (Flecha derecha)">${ICONS.fwd}</button>
            <div class="p-vol"><button class="p-ib" data-a="mute" title="Silencio (M)">${ICONS.vol}</button><input type="range" min="0" max="100" value="100" aria-label="Volumen"></div>
            <span class="p-quality"></span>
          </div>
          <div class="p-right">
            <button class="p-ib live-only" data-a="list" title="Lista de canales (L)">${ICONS.list}</button>
            <button class="p-ib" data-a="menu" title="Audio, subtítulos, calidad...">${ICONS.gear}</button>
            <button class="p-ib" data-a="external" title="Abrir en VLC">${ICONS.ext}</button>
            <button class="p-ib" data-a="pip" title="Imagen en imagen">${ICONS.pip}</button>
            <button class="p-ib" data-a="full" title="Pantalla completa (F)">${ICONS.expand}</button>
          </div>
        </div>
      </div>
      <div class="p-menu hidden"></div>
      <div class="p-side hidden"><div class="p-side-head"></div><div class="p-side-list"></div></div>
      <div class="p-num hidden"></div>
      <div class="p-toast hidden"></div>
      <div class="p-next hidden"><div class="p-next-txt"></div><div class="p-next-actions"><button class="btn primary" data-a="nextNow">Ver ahora</button><button class="btn ghost" data-a="nextCancel">Cancelar</button></div></div>
      <button class="p-mini-expand" data-a="expandMini" title="Ver en grande (Enter)">${ICONS.expand}</button>
    `;
    this.v = root.querySelector('video');
    this.$ = (s) => root.querySelector(s);
    this.bind();
    this.applyVolume();
    setInterval(() => this.tick(), 1000);
  }

  // ---------- API ----------
  play(ctx) {
    this.stopEngines();
    this.clearNext();
    this.ctx = ctx;
    this.tried = [];
    this.errors = [];
    this.retries = 0;
    this.playingOnce = false;
    this.urls = [ctx.url, ...(ctx.altUrls || [])].filter(Boolean);
    this.urlIndex = 0;
    this.root.classList.toggle('is-live', !!ctx.live);
    this.root.classList.toggle('is-vod', !ctx.live);
    this.$('.p-title').textContent = ctx.title || '';
    this.$('.p-sub').textContent = ctx.subtitle || '';
    const logo = this.$('.p-logo');
    if (ctx.logo) { logo.src = ctx.logo; logo.classList.remove('hidden'); logo.onerror = () => logo.classList.add('hidden'); }
    else logo.classList.add('hidden');
    this.$('.p-epg').classList.toggle('hidden', !ctx.live);
    this.$('.p-seek').classList.toggle('hidden', !!ctx.live);
    this.$('.p-quality').textContent = '';
    this.updateFav();
    this.closeMenu();
    this.hideError();
    this.setLoading(true, 'Conectando...');
    this.applyAspect();
    this.v.playbackRate = 1;
    this.startUrl();
    this.renderEpg();
    this.poke();
  }

  stop() {
    this.saveProgress();
    this.stopEngines();
    this.clearNext();
    this.ctx = null;
    this.setLoading(false);
    this.hideError();
  }

  setMode(mode, rect) {
    this.mode = mode;
    this.root.dataset.mode = mode;
    if (mode === 'mini' && rect) this.place(rect);
    if (mode !== 'full') { this.$('.p-side').classList.add('hidden'); this.closeMenu(); }
    this.$('[data-a="full"]').innerHTML = ICONS.expand;
    this.poke();
  }
  place(rect) {
    Object.assign(this.root.style, { left: rect.left + 'px', top: rect.top + 'px', width: rect.width + 'px', height: rect.height + 'px' });
  }
  get active() { return !!this.ctx; }

  // ---------- motores ----------
  enginesFor(url) {
    const p = url.split('?')[0].toLowerCase();
    if (p.endsWith('.m3u8') || p.endsWith('.m3u') || /\/hls\//.test(p) || /m3u8/.test(url)) return ['hls', 'native', 'mpegts'];
    if (p.endsWith('.ts') || p.endsWith('.mpegts')) return ['mpegts', 'hls', 'native'];
    if (p.endsWith('.flv')) return ['mpegts-flv', 'native'];
    if (/\.(mp4|m4v|webm|mkv|mov|mp3|aac|ogg|avi|wmv|mpg|mpeg)$/.test(p)) return ['native', 'hls'];
    return this.ctx && this.ctx.live ? ['hls', 'mpegts', 'native'] : ['native', 'hls', 'mpegts'];
  }
  startUrl() {
    this.engines = this.enginesFor(this.urls[this.urlIndex]);
    this.engineIndex = 0;
    this.startEngine();
  }
  startEngine() {
    this.stopEngines();
    const url = this.urls[this.urlIndex];
    let name = this.engines[this.engineIndex];
    if (name === 'hls' && !(window.Hls && Hls.isSupported())) name = 'native';
    if (name.startsWith('mpegts') && !(window.mpegts && mpegts.isSupported())) name = 'native';
    this.engine = name;
    const v = this.v;
    const s = this.opts.getSettings ? this.opts.getSettings() : {};
    clearTimeout(this.startTimer);
    this.startTimer = setTimeout(() => { if (!this.isPlaying()) this.fail('El canal no responde (tiempo de espera agotado)'); }, (s.timeoutSec || 25) * 1000);

    if (name === 'hls') {
      const hls = new Hls({
        enableWorker: true, lowLatencyMode: false, backBufferLength: 30,
        maxBufferLength: s.bufferSec || 30, startPosition: this.ctx.live ? -1 : (this.ctx.startAt || 0),
        manifestLoadingMaxRetry: 2, levelLoadingMaxRetry: 3, fragLoadingMaxRetry: 4,
        renderTextTracksNatively: true,
      });
      this.hls = hls;
      let mediaRecover = 0;
      hls.on(Hls.Events.ERROR, (_e, d) => {
        if (!d.fatal) return;
        if (d.type === Hls.ErrorTypes.MEDIA_ERROR && mediaRecover < 2) {
          mediaRecover++;
          if (mediaRecover === 2) hls.swapAudioCodec();
          hls.recoverMediaError();
          return;
        }
        const code = d.response && d.response.code;
        this.fail(code ? `El servidor respondió ${code} (${d.details})` : `Error de reproducción (${d.details})`);
      });
      hls.on(Hls.Events.MANIFEST_PARSED, () => { this.tryPlay(); this.updateQualityLabel(); });
      hls.on(Hls.Events.LEVEL_SWITCHED, () => this.updateQualityLabel());
      hls.loadSource(url);
      hls.attachMedia(v);
    } else if (name.startsWith('mpegts')) {
      const p = mpegts.createPlayer(
        { type: name === 'mpegts-flv' ? 'flv' : 'mpegts', isLive: !!this.ctx.live, url },
        { enableWorker: true, lazyLoad: !this.ctx.live, liveBufferLatencyChasing: !!this.ctx.live,
          liveBufferLatencyMaxLatency: 6, liveBufferLatencyMinRemain: 1.5, autoCleanupSourceBuffer: true },
      );
      this.mpegts = p;
      p.on(mpegts.Events.ERROR, (type, detail, info) => {
        this.fail(`Error de ${type === 'NetworkError' ? 'red' : 'video'} (${(info && info.msg) || detail})`);
      });
      p.attachMediaElement(v);
      p.load();
      if (!this.ctx.live && this.ctx.startAt) v.currentTime = this.ctx.startAt;
      this.tryPlay();
    } else {
      v.src = url;
      if (!this.ctx.live && this.ctx.startAt) {
        v.addEventListener('loadedmetadata', () => { try { v.currentTime = this.ctx.startAt; } catch {} }, { once: true });
      }
      this.tryPlay();
    }
  }
  stopEngines() {
    clearTimeout(this.startTimer);
    clearTimeout(this.retryTimer);
    if (this.hls) { try { this.hls.destroy(); } catch {} this.hls = null; }
    if (this.mpegts) { try { this.mpegts.destroy(); } catch {} this.mpegts = null; }
    const v = this.v;
    v.pause();
    v.removeAttribute('src');
    try { v.load(); } catch {}
    this.engine = null;
  }
  tryPlay() {
    const p = this.v.play();
    if (p && p.catch) p.catch(() => {});
  }
  isPlaying() { return this.playingOnce && !this.v.paused; }

  fail(msg) {
    if (!this.ctx) return;
    clearTimeout(this.startTimer);
    if (msg) this.errors.push(msg);
    // ya se habia reproducido: reconectar (en vivo) en vez de cambiar de motor
    if (this.playingOnce && this.ctx.live && this.retries < 6) {
      this.retries++;
      this.setLoading(true, `Reconectando (${this.retries})...`);
      this.stopEngines();
      this.retryTimer = setTimeout(() => this.startEngine(), 1500 * this.retries);
      return;
    }
    if (!this.playingOnce) {
      if (this.engineIndex < this.engines.length - 1) {
        this.engineIndex++;
        this.setLoading(true, 'Probando otro formato...');
        this.startEngine();
        return;
      }
      if (this.urlIndex < this.urls.length - 1) {
        this.urlIndex++;
        this.setLoading(true, 'Probando enlace alternativo...');
        this.startUrl();
        return;
      }
    }
    this.stopEngines();
    this.setLoading(false);
    // el error del servidor (404, 403...) explica mas que "formato no compatible"
    const best = this.errors.find((m) => /servidor respondi|espera|red/i.test(m)) || msg;
    this.showError(best || 'El contenido no está disponible.');
  }

  // ---------- UI ----------
  bind() {
    const v = this.v;
    v.addEventListener('playing', () => {
      this.playingOnce = true;
      clearTimeout(this.startTimer);
      this.setLoading(false);
      this.hideError();
      this.updatePlayIcon();
      clearTimeout(this.okTimer);
      this.okTimer = setTimeout(() => { this.retries = 0; }, 30000);
    });
    v.addEventListener('waiting', () => { if (this.ctx) this.setLoading(true, 'Cargando...'); });
    v.addEventListener('canplay', () => { if (!v.paused) this.setLoading(false); });
    v.addEventListener('pause', () => this.updatePlayIcon());
    v.addEventListener('play', () => this.updatePlayIcon());
    v.addEventListener('error', () => {
      if (this.engine !== 'native' || !this.ctx) return;
      const code = v.error && v.error.code;
      this.fail(code === 4 ? 'Formato no compatible con el reproductor interno. Prueba "Abrir en VLC".' : 'Error al cargar el video');
    });
    v.addEventListener('ended', () => {
      if (!this.ctx) return;
      if (this.ctx.live) { this.fail('La transmisión se corto'); return; }
      this.saveProgress(true);
      if (this.ctx.onEnded) this.ctx.onEnded();
    });
    v.addEventListener('loadedmetadata', () => { this.renderSeek(); this.updateQualityLabel(); });
    v.addEventListener('volumechange', () => this.updateVolIcon());
    v.addEventListener('dblclick', () => this.act('full'));
    v.addEventListener('click', () => {
      if (this.mode === 'mini') { this.act('expandMini'); return; }
      if (this.$('.p-menu').classList.contains('hidden')) this.act('toggle'); else this.closeMenu();
    });

    this.root.addEventListener('click', (e) => {
      const b = e.target.closest('[data-a]');
      if (b && this.root.contains(b)) { e.stopPropagation(); this.act(b.dataset.a, b); }
    });
    this.root.addEventListener('mousemove', () => this.poke());

    // barra de avance
    const range = this.$('.p-seek input');
    range.addEventListener('input', () => {
      this.seeking = true;
      const d = this.duration();
      this.$('.p-fill').style.width = range.value / 10 + '%';
      this.$('.p-cur').textContent = fmtTime((range.value / 1000) * d);
    });
    range.addEventListener('change', () => {
      const d = this.duration();
      if (d) v.currentTime = (range.value / 1000) * d;
      this.seeking = false;
    });
    range.addEventListener('mousemove', (e) => {
      const r = range.getBoundingClientRect();
      const f = Math.min(1, Math.max(0, (e.clientX - r.left) / r.width));
      const t = this.$('.p-hover-t');
      t.textContent = fmtTime(f * this.duration());
      t.style.left = f * 100 + '%';
      t.classList.remove('hidden');
    });
    range.addEventListener('mouseleave', () => this.$('.p-hover-t').classList.add('hidden'));
    v.addEventListener('timeupdate', () => { if (!this.seeking) this.renderSeek(); });
    v.addEventListener('progress', () => this.renderSeek());

    const vol = this.$('.p-vol input');
    vol.addEventListener('input', () => {
      v.volume = vol.value / 100;
      v.muted = vol.value == 0;
      this.saveVolume();
    });
  }

  act(a, el) {
    const v = this.v;
    const ctx = this.ctx;
    switch (a) {
      case 'toggle':
        if (!ctx) return;
        if (v.paused) this.tryPlay(); else v.pause();
        this.flash(v.paused ? 'Pausa' : 'Reproduciendo');
        break;
      case 'close': if (this.opts.onClose) this.opts.onClose(); break;
      case 'rew': if (!ctx.live) v.currentTime = Math.max(0, v.currentTime - 10); break;
      case 'fwd': if (!ctx.live) v.currentTime = Math.min(this.duration() || 1e9, v.currentTime + 10); break;
      case 'prev': if (ctx && ctx.onStep) ctx.onStep(-1); break;
      case 'next': if (ctx && ctx.onStep) ctx.onStep(1); break;
      case 'mute': v.muted = !v.muted; this.saveVolume(); break;
      case 'list': this.toggleSide(); break;
      case 'menu': this.toggleMenu(); break;
      case 'retry': this.hideError(); this.setLoading(true, 'Conectando...'); this.tried = []; this.errors = []; this.urlIndex = 0; this.playingOnce = false; this.retries = 0; this.startUrl(); break;
      case 'external': if (ctx && this.opts.onExternal) { v.pause(); this.opts.onExternal(this.urls[this.urlIndex] || ctx.url, ctx.title); } break;
      case 'pip':
        if (document.pictureInPictureElement) document.exitPictureInPicture();
        else v.requestPictureInPicture().catch(() => this.flash('Imagen en imagen no disponible'));
        break;
      case 'full':
        if (this.mode === 'mini') { this.act('expandMini'); break; }
        window.api.win.fullscreen();
        break;
      case 'expandMini': if (this.opts.onExpand) this.opts.onExpand(); break;
      case 'fav': if (ctx && ctx.onFav) { ctx.onFav(); this.updateFav(); } break;
      case 'nextNow': { const fn = this.nextFn; this.clearNext(); if (fn) fn(); break; }
      case 'nextCancel': this.clearNext(); break;
      case 'opt': this.applyOption(el.dataset.k, el.dataset.v); break;
    }
    this.poke();
  }

  onFullscreen(on) {
    this.isWinFull = on;
    this.$('[data-a="full"]').innerHTML = on ? ICONS.shrink : ICONS.expand;
  }

  key(e) {
    if (!this.ctx || this.mode === 'hidden') return false;
    const k = e.key;
    const live = this.ctx.live;
    // en la vista previa las flechas mueven la lista de canales, no el reproductor
    if (this.mode === 'mini' && !['Enter', ' ', 'f', 'F', 'm', 'M'].includes(k)) return false;
    if (/^\d$/.test(k) && live && this.ctx.onNumber) { this.typeNumber(k); return true; }
    switch (k) {
      case ' ': case 'k': this.act('toggle'); return true;
      case 'ArrowUp':
        if (this.sideOpen()) return false;
        if (live) this.act('prev'); else { this.v.volume = Math.min(1, this.v.volume + 0.05); this.v.muted = false; this.saveVolume(); this.flash(`Volumen ${Math.round(this.v.volume * 100)}%`); }
        return true;
      case 'ArrowDown':
        if (this.sideOpen()) return false;
        if (live) this.act('next'); else { this.v.volume = Math.max(0, this.v.volume - 0.05); this.saveVolume(); this.flash(`Volumen ${Math.round(this.v.volume * 100)}%`); }
        return true;
      case 'ArrowLeft': if (!live) { this.act('rew'); this.flash('-10 s'); return true; } return false;
      case 'ArrowRight': if (!live) { this.act('fwd'); this.flash('+10 s'); return true; } return false;
      case 'f': case 'F': this.act('full'); return true;
      case 'm': case 'M': this.act('mute'); this.flash(this.v.muted ? 'Silencio' : 'Sonido'); return true;
      case 'l': case 'L': if (live && this.mode === 'full') { this.act('list'); return true; } return false;
      case 'i': case 'I': this.poke(6000); return true;
      case 'Enter':
        if (this.mode === 'mini') { this.act('expandMini'); return true; }
        if (live && this.mode === 'full' && !this.sideOpen()) { this.toggleSide(); return true; }
        return false;
      case 'Escape': case 'Backspace':
        if (!this.$('.p-menu').classList.contains('hidden')) { this.closeMenu(); return true; }
        if (this.sideOpen()) { this.toggleSide(false); return true; }
        if (this.mode !== 'full') return false;
        if (document.fullscreenElement || this.isWinFull) { window.api.win.fullscreen(false); return true; }
        this.act('close');
        return true;
    }
    return false;
  }

  typeNumber(d) {
    this.numBuffer = (this.numBuffer + d).slice(-4);
    const el = this.$('.p-num');
    el.textContent = this.numBuffer;
    el.classList.remove('hidden');
    clearTimeout(this.numTimer);
    this.numTimer = setTimeout(() => {
      el.classList.add('hidden');
      const n = +this.numBuffer;
      this.numBuffer = '';
      if (this.ctx && this.ctx.onNumber && !this.ctx.onNumber(n)) this.flash(`No existe el canal ${n}`);
    }, 1400);
  }

  poke(ms = 3200) {
    this.root.classList.add('ui-on');
    clearTimeout(this.uiTimer);
    this.uiTimer = setTimeout(() => {
      if (this.v.paused && this.ctx && this.playingOnce) return; // en pausa deja los controles visibles
      if (!this.$('.p-menu').classList.contains('hidden')) return;
      this.root.classList.remove('ui-on');
    }, ms);
  }
  flash(msg) {
    const t = this.$('.p-toast');
    t.textContent = msg;
    t.classList.remove('hidden');
    clearTimeout(this.toastTimer);
    this.toastTimer = setTimeout(() => t.classList.add('hidden'), 1200);
  }
  setLoading(on, txt) {
    this.root.classList.toggle('loading', !!on);
    if (txt) this.$('.p-loading-txt').textContent = txt;
  }
  showError(msg) {
    this.$('.p-error-msg').textContent = msg;
    this.$('.p-error').classList.remove('hidden');
  }
  hideError() { this.$('.p-error').classList.add('hidden'); }
  updatePlayIcon() { this.$('[data-a="toggle"]').innerHTML = this.v.paused ? ICONS.play : ICONS.pause; }
  updateVolIcon() {
    const v = this.v;
    this.$('[data-a="mute"]').innerHTML = v.muted || v.volume === 0 ? ICONS.mute : ICONS.vol;
    this.$('.p-vol input').value = v.muted ? 0 : Math.round(v.volume * 100);
  }
  applyVolume() {
    const s = this.opts.getSettings ? this.opts.getSettings() : {};
    this.v.volume = s.volume ?? 1;
    this.v.muted = !!s.muted;
    this.updateVolIcon();
  }
  saveVolume() {
    if (this.opts.saveSettings) this.opts.saveSettings({ volume: this.v.volume, muted: this.v.muted });
  }
  updateFav() {
    const b = this.$('.p-fav');
    const ctx = this.ctx;
    if (!ctx || !ctx.isFav) { b.classList.add('hidden'); return; }
    b.classList.remove('hidden');
    const on = ctx.isFav();
    b.innerHTML = on ? ICONS.heart : ICONS.heartO;
    b.classList.toggle('on', on);
  }
  duration() {
    const d = this.v.duration;
    if (isFinite(d) && d > 0) return d;
    return (this.ctx && this.ctx.duration) || 0;
  }
  renderSeek() {
    if (!this.ctx || this.ctx.live) return;
    const v = this.v, d = this.duration();
    const f = d ? v.currentTime / d : 0;
    this.$('.p-fill').style.width = f * 100 + '%';
    this.$('.p-seek input').value = Math.round(f * 1000);
    this.$('.p-cur').textContent = fmtTime(v.currentTime);
    this.$('.p-dur').textContent = d ? fmtTime(d) : '--:--';
    let buf = 0;
    for (let i = 0; i < v.buffered.length; i++) if (v.buffered.start(i) <= v.currentTime + 1) buf = v.buffered.end(i);
    this.$('.p-buf').style.width = d ? Math.min(100, (buf / d) * 100) + '%' : '0';
  }
  updateQualityLabel() {
    const v = this.v;
    const h = v.videoHeight;
    this.$('.p-quality').textContent = h ? (h >= 2000 ? '4K' : h >= 1000 ? 'FHD' : h >= 700 ? 'HD' : 'SD') + ` · ${v.videoWidth}x${h}` : '';
  }

  tick() {
    const now = new Date();
    this.$('.p-clock').textContent = now.toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit' });
    if (!this.ctx) return;
    if (this.ctx.live) this.renderEpg();
    else if (!this.v.paused) {
      this.sinceSave = (this.sinceSave || 0) + 1;
      if (this.sinceSave >= 10) { this.sinceSave = 0; this.saveProgress(); }
    }
    if (this.v.videoHeight && !this.$('.p-quality').textContent) this.updateQualityLabel();
  }
  saveProgress(ended) {
    const ctx = this.ctx;
    if (!ctx || ctx.live || !ctx.onProgress || !this.playingOnce) return;
    ctx.onProgress(ended ? this.duration() : this.v.currentTime, this.duration(), !!ended);
  }
  renderEpg() {
    const ctx = this.ctx;
    if (!ctx || !ctx.live) return;
    const e = ctx.epg ? ctx.epg() : null;
    const box = this.$('.p-epg');
    if (!e || !e.now) {
      this.$('.p-epg-title').textContent = 'Sin información de programación';
      this.$('.p-epg-time').textContent = '';
      this.$('.p-epg-bar i').style.width = '0';
      this.$('.p-epg-next').textContent = '';
      box.classList.add('no-epg');
      return;
    }
    box.classList.remove('no-epg');
    const t = (ms) => new Date(ms).toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit' });
    this.$('.p-epg-title').textContent = e.now.t;
    this.$('.p-epg-time').textContent = `${t(e.now.s)} - ${t(e.now.e)}`;
    this.$('.p-epg-bar i').style.width = Math.min(100, ((Date.now() - e.now.s) / (e.now.e - e.now.s)) * 100) + '%';
    this.$('.p-epg-next').textContent = e.next ? `Después: ${t(e.next.s)} ${e.next.t}` : '';
  }

  // ---------- panel lateral de canales (modo grande, en vivo) ----------
  sideOpen() { return !this.$('.p-side').classList.contains('hidden'); }
  toggleSide(force) {
    const el = this.$('.p-side');
    const open = force ?? el.classList.contains('hidden');
    el.classList.toggle('hidden', !open);
    if (open && this.ctx && this.ctx.renderSide) this.ctx.renderSide(this.$('.p-side-head'), this.$('.p-side-list'), () => this.toggleSide(false));
  }

  // ---------- menu de opciones ----------
  toggleMenu() {
    const m = this.$('.p-menu');
    if (!m.classList.contains('hidden')) { this.closeMenu(); return; }
    this.renderMenu();
    m.classList.remove('hidden');
    this.poke(60000);
  }
  closeMenu() { this.$('.p-menu').classList.add('hidden'); }
  renderMenu() {
    const v = this.v, hls = this.hls;
    const s = this.opts.getSettings ? this.opts.getSettings() : {};
    const sec = (title, k, opts, cur) => opts.length < 2 ? '' : `
      <div class="pm-sec"><div class="pm-h">${title}</div><div class="pm-opts">
      ${opts.map((o) => `<button class="chip ${String(o.v) === String(cur) ? 'on' : ''}" data-a="opt" data-k="${k}" data-v="${esc(o.v)}">${esc(o.label)}</button>`).join('')}
      </div></div>`;
    let html = '';
    // audio
    if (hls && hls.audioTracks && hls.audioTracks.length > 1) {
      html += sec('Audio', 'audio', hls.audioTracks.map((t, i) => ({ v: i, label: t.name || t.lang || `Pista ${i + 1}` })), hls.audioTrack);
    } else if (v.audioTracks && v.audioTracks.length > 1) {
      const list = [...v.audioTracks];
      html += sec('Audio', 'audio', list.map((t, i) => ({ v: i, label: t.label || t.language || `Pista ${i + 1}` })), list.findIndex((t) => t.enabled));
    }
    // subtitulos
    if (hls && hls.subtitleTracks && hls.subtitleTracks.length) {
      html += sec('Subtítulos', 'sub', [{ v: -1, label: 'Desactivados' }, ...hls.subtitleTracks.map((t, i) => ({ v: i, label: t.name || t.lang || `Subtítulo ${i + 1}` }))], hls.subtitleTrack);
    } else if (v.textTracks && v.textTracks.length) {
      const list = [...v.textTracks];
      html += sec('Subtítulos', 'sub', [{ v: -1, label: 'Desactivados' }, ...list.map((t, i) => ({ v: i, label: t.label || t.language || `Subtítulo ${i + 1}` }))], list.findIndex((t) => t.mode === 'showing'));
    }
    // calidad
    if (hls && hls.levels && hls.levels.length > 1) {
      const lv = hls.levels.map((l, i) => ({ v: i, label: l.height ? `${l.height}p` : `${Math.round((l.bitrate || 0) / 1000)} kbps` }));
      html += sec('Calidad', 'level', [{ v: -1, label: 'Automática' }, ...lv], hls.manualLevel ?? -1);
    }
    html += sec('Pantalla', 'aspect', [
      { v: 'contain', label: 'Ajustar' }, { v: 'cover', label: 'Llenar (recortar)' }, { v: 'fill', label: 'Estirar' },
      { v: '16:9', label: '16:9' }, { v: '4:3', label: '4:3' },
    ], s.aspect || 'contain');
    if (this.ctx && !this.ctx.live) {
      html += sec('Velocidad', 'rate', [0.5, 0.75, 1, 1.25, 1.5, 2].map((r) => ({ v: r, label: r === 1 ? 'Normal' : r + 'x' })), v.playbackRate);
    }
    html += `<div class="pm-sec pm-info">Motor: ${esc(this.engineName())}${v.videoHeight ? ` · ${v.videoWidth}x${v.videoHeight}` : ''}</div>`;
    this.$('.p-menu').innerHTML = html;
  }
  engineName() {
    return { hls: 'HLS', mpegts: 'MPEG-TS', 'mpegts-flv': 'FLV', native: 'Nativo' }[this.engine] || '-';
  }
  applyOption(k, val) {
    const v = this.v, hls = this.hls;
    const n = Number(val);
    if (k === 'audio') {
      if (hls && hls.audioTracks.length > 1) hls.audioTrack = n;
      else if (v.audioTracks) [...v.audioTracks].forEach((t, i) => { t.enabled = i === n; });
    } else if (k === 'sub') {
      if (hls && hls.subtitleTracks.length) { hls.subtitleTrack = n; hls.subtitleDisplay = n >= 0; }
      else [...v.textTracks].forEach((t, i) => { t.mode = i === n ? 'showing' : 'disabled'; });
    } else if (k === 'level') {
      if (hls) { hls.currentLevel = n; hls.manualLevel = n; }
    } else if (k === 'aspect') {
      if (this.opts.saveSettings) this.opts.saveSettings({ aspect: val });
      this.applyAspect(val);
    } else if (k === 'rate') {
      v.playbackRate = n;
    }
    this.renderMenu();
  }
  applyAspect(val) {
    const s = this.opts.getSettings ? this.opts.getSettings() : {};
    val = val || s.aspect || 'contain';
    const v = this.v;
    v.style.objectFit = ['cover', 'fill'].includes(val) ? val : 'contain';
    v.style.aspectRatio = '';
    v.classList.toggle('forced-ar', val === '16:9' || val === '4:3');
    if (val === '16:9' || val === '4:3') { v.style.objectFit = 'fill'; v.style.aspectRatio = val.replace(':', ' / '); }
  }

  // ---------- siguiente episodio ----------
  offerNext(label, fn, secs = 10) {
    this.clearNext();
    this.nextFn = fn;
    let left = secs;
    const box = this.$('.p-next');
    const txt = this.$('.p-next-txt');
    const upd = () => { txt.innerHTML = `Siguiente: <b>${esc(label)}</b><br><span>Empieza en ${left} s</span>`; };
    upd();
    box.classList.remove('hidden');
    this.nextTimer = setInterval(() => {
      left--;
      if (left <= 0) { const f = this.nextFn; this.clearNext(); if (f) f(); } else upd();
    }, 1000);
  }
  clearNext() {
    clearInterval(this.nextTimer);
    this.nextFn = null;
    this.$('.p-next').classList.add('hidden');
  }
}
