// Fuentes de contenido: listas M3U y cuentas Xtream Codes.
// Todo se normaliza al mismo "catalogo":
//   { live:   { cats:[{id,name}], items:[{id,name,logo,cat,url?,epgId,num}] },
//     movie:  { cats, items:[{id,name,poster,cat,url?,ext,rating,added,year}] },
//     series: { cats, items:[{id,name,poster,cat,rating,added,year,episodes?}] },
//     header: {...}, account?: {...} }
'use strict';

const Sources = (() => {
  const VOD_EXT = /\.(mp4|mkv|avi|mov|wmv|webm|m4v|mpg|mpeg|divx|xvid)$/i;
  const EP_RE = /^(.*?)[\s._\-|:]*\bS(\d{1,2})\s*[ _.-]?\s*E(\d{1,3})\b/i;

  const hash = (str) => {
    let h1 = 0x811c9dc5, h2 = 5381;
    for (let i = 0; i < str.length; i++) {
      const c = str.charCodeAt(i);
      h1 = Math.imul(h1 ^ c, 16777619);
      h2 = (Math.imul(h2, 33) + c) | 0;
    }
    return (h1 >>> 0).toString(36) + (h2 >>> 0).toString(36);
  };

  // ---------------- M3U ----------------
  function parseAttrs(s) {
    const out = {};
    const re = /([\w-]+)=("([^"]*)"|'([^']*)'|([^\s,]+))/g;
    let m;
    while ((m = re.exec(s))) out[m[1].toLowerCase()] = (m[3] ?? m[4] ?? m[5] ?? '').trim();
    return out;
  }
  // la coma que separa atributos del nombre (fuera de comillas)
  function titleComma(line) {
    let q = null;
    for (let i = 8; i < line.length; i++) {
      const c = line[i];
      if (q) { if (c === q) q = null; }
      else if (c === '"') q = c;
      else if (c === ',') return i;
    }
    return -1;
  }
  function parseM3U(text) {
    const lines = text.replace(/^﻿/, '').split(/\r?\n/);
    let header = {};
    const entries = [];
    let cur = null;
    for (const raw of lines) {
      const line = raw.trim();
      if (!line) continue;
      if (line.startsWith('#EXTM3U')) { header = parseAttrs(line.slice(7)); continue; }
      if (line.startsWith('#EXTINF')) {
        const ci = titleComma(line);
        cur = ci < 0
          ? { attrs: parseAttrs(line.slice(8)), name: '' }
          : { attrs: parseAttrs(line.slice(8, ci)), name: line.slice(ci + 1).trim() };
        continue;
      }
      if (line.startsWith('#EXTGRP:')) { if (cur) cur.group = line.slice(8).trim(); continue; }
      if (line.startsWith('#')) continue;
      if (!/^(https?|rtmp|rtsp|udp|rtp|mms|file):/i.test(line)) { cur = null; continue; }
      const e = cur || { attrs: {}, name: '' };
      const pipe = line.indexOf('|');
      e.url = pipe > 0 ? line.slice(0, pipe) : line;
      if (!e.name) e.name = e.attrs['tvg-name'] || e.url.split('/').pop();
      entries.push(e);
      cur = null;
    }
    return { header, entries };
  }

  function classify(e) {
    const path = e.url.split('?')[0].toLowerCase();
    if (/\/series\//.test(path)) return 'series';
    if (/\/movie\//.test(path)) return EP_RE.test(e.name) ? 'series' : 'movie';
    if (VOD_EXT.test(path)) return EP_RE.test(e.name) ? 'series' : 'movie';
    return 'live';
  }

  function buildFromM3U(text) {
    const { header, entries } = parseM3U(text);
    if (!entries.length) throw new Error('La lista no tiene canales (o no es un archivo M3U válido)');
    const cat = { live: { cats: new Map(), items: [] }, movie: { cats: new Map(), items: [] }, series: { cats: new Map(), items: [] } };
    const seriesMap = new Map();
    let num = 0;
    for (const e of entries) {
      const type = classify(e);
      const group = (e.attrs['group-title'] || e.group || 'Sin categoría').trim() || 'Sin categoría';
      const cid = hash(group);
      const bucket = cat[type];
      if (!bucket.cats.has(cid)) bucket.cats.set(cid, { id: cid, name: group });
      const logo = e.attrs['tvg-logo'] || e.attrs['logo'] || '';
      if (type === 'live') {
        num++;
        bucket.items.push({
          id: hash(e.url + '|' + e.name), name: e.name, logo, cat: cid, url: e.url,
          epgId: e.attrs['tvg-id'] || '', num: +e.attrs['tvg-chno'] || num,
        });
      } else if (type === 'movie') {
        const y = /\((\d{4})\)/.exec(e.name);
        bucket.items.push({ id: hash(e.url), name: e.name, poster: logo, cat: cid, url: e.url, year: y ? y[1] : '', added: 0 });
      } else {
        const m = EP_RE.exec(e.name);
        const show = (m ? m[1] : e.name).replace(/[\s._\-|:]+$/, '').trim() || e.name;
        const key = cid + '|' + show.toLowerCase();
        let s = seriesMap.get(key);
        if (!s) {
          s = { id: hash(key), name: show, poster: logo, cat: cid, episodes: [], added: 0 };
          seriesMap.set(key, s);
          bucket.items.push(s);
        }
        s.episodes.push({
          id: hash(e.url), season: m ? +m[2] : 1, episode: m ? +m[3] : s.episodes.length + 1,
          title: e.name, url: e.url, img: logo,
        });
      }
    }
    const out = {};
    for (const t of ['live', 'movie', 'series']) out[t] = { cats: [...cat[t].cats.values()], items: cat[t].items };
    out.header = { epgUrl: (header['url-tvg'] || header['x-tvg-url'] || '').split(',')[0].trim() };
    return out;
  }

  // ---------------- Xtream Codes ----------------
  function xtBase(src) {
    let s = (src.server || '').trim().replace(/\/+$/, '').replace(/\/(player_api|get)\.php.*$/i, '');
    if (!/^https?:\/\//i.test(s)) s = 'http://' + s;
    return s;
  }
  function xtUrl(src, action, params = {}) {
    const q = new URLSearchParams({ username: src.username, password: src.password });
    if (action) q.set('action', action);
    for (const [k, v] of Object.entries(params)) q.set(k, v);
    return `${xtBase(src)}/player_api.php?${q}`;
  }
  const xt = (src, action, params) => window.api.net.json(xtUrl(src, action, params));
  const arr = (x) => (Array.isArray(x) ? x : x && typeof x === 'object' ? Object.values(x) : []);

  async function xtLogin(src) {
    const d = await xt(src);
    if (!d || !d.user_info || String(d.user_info.auth) === '0') throw new Error('Usuario o contraseña incorrectos');
    const u = d.user_info;
    if (u.status && !/active/i.test(u.status)) throw new Error(`La cuenta no está activa (estado: ${u.status})`);
    return {
      status: u.status || '', expires: u.exp_date ? +u.exp_date * 1000 : 0,
      maxConnections: u.max_connections || '', activeConnections: u.active_cons || '',
      createdAt: u.created_at ? +u.created_at * 1000 : 0, trial: String(u.is_trial) === '1',
      timezone: (d.server_info && d.server_info.timezone) || '',
    };
  }

  async function buildFromXtream(src, onProgress = () => {}) {
    onProgress('Iniciando sesión...');
    const account = await xtLogin(src);
    onProgress('Descargando canales, películas y series...');
    const calls = ['get_live_categories', 'get_live_streams', 'get_vod_categories', 'get_vod_streams', 'get_series_categories', 'get_series'];
    const res = await Promise.allSettled(calls.map((a) => xt(src, a)));
    const [lc, ls, vc, vs, sc, ss] = res.map((r) => (r.status === 'fulfilled' ? arr(r.value) : []));
    if (res[1].status === 'rejected' && res[3].status === 'rejected') throw res[1].reason;
    const cats = (list) => list.map((c) => ({ id: String(c.category_id), name: c.category_name || 'Sin nombre' }));
    const fixCat = (c) => (c === null || c === undefined ? '0' : String(c));
    const withOrphans = (catList, items) => {
      const ids = new Set(catList.map((c) => c.id));
      if (items.some((i) => !ids.has(i.cat))) catList.push({ id: '0', name: 'Sin categoría' });
      items.forEach((i) => { if (!ids.has(i.cat)) i.cat = '0'; });
      return catList;
    };
    const live = ls.map((s, i) => ({
      id: String(s.stream_id), name: s.name || '', logo: s.stream_icon || '', cat: fixCat(s.category_id),
      epgId: s.epg_channel_id || '', num: +s.num || i + 1, archive: +s.tv_archive || 0,
    }));
    const movies = vs.map((s) => ({
      id: String(s.stream_id), name: s.name || '', poster: s.stream_icon || '', cat: fixCat(s.category_id),
      ext: s.container_extension || 'mp4', rating: parseFloat(s.rating) || 0, added: +s.added || 0,
      year: (/\((\d{4})\)/.exec(s.name || '') || [])[1] || s.year || '',
    }));
    const series = ss.map((s) => ({
      id: String(s.series_id), name: s.name || '', poster: s.cover || '', cat: fixCat(s.category_id),
      rating: parseFloat(s.rating) || 0, added: +s.last_modified || 0,
      year: (s.releaseDate || s.release_date || '').slice(0, 4), plot: s.plot || '',
    }));
    return {
      live: { cats: withOrphans(cats(lc), live), items: live },
      movie: { cats: withOrphans(cats(vc), movies), items: movies },
      series: { cats: withOrphans(cats(sc), series), items: series },
      header: { epgUrl: `${xtBase(src)}/xmltv.php?username=${encodeURIComponent(src.username)}&password=${encodeURIComponent(src.password)}` },
      account,
    };
  }

  // ---------------- API comun ----------------
  async function buildCatalog(src, onProgress) {
    if (src.type === 'xtream') return buildFromXtream(src, onProgress);
    onProgress && onProgress('Descargando lista...');
    const text = src.type === 'm3u-file' ? src.content : await window.api.net.text(src.url, { timeoutMs: 120000 });
    onProgress && onProgress('Procesando lista...');
    return buildFromM3U(text);
  }

  function streamUrl(src, type, item, settings = {}) {
    if (src.type !== 'xtream') return item.url;
    const u = encodeURIComponent(src.username), p = encodeURIComponent(src.password), b = xtBase(src);
    if (type === 'live') return `${b}/live/${u}/${p}/${item.id}.${settings.liveFormat === 'ts' ? 'ts' : 'm3u8'}`;
    if (type === 'movie') return `${b}/movie/${u}/${p}/${item.id}.${item.ext || 'mp4'}`;
    if (type === 'episode') return `${b}/series/${u}/${p}/${item.id}.${item.ext || 'mp4'}`;
    return '';
  }
  // URL alternativa (otro formato) para cuando la primera no reproduce
  function altLiveUrl(src, item, settings = {}) {
    if (src.type !== 'xtream') return null;
    return streamUrl(src, 'live', item, { liveFormat: settings.liveFormat === 'ts' ? 'm3u8' : 'ts' });
  }

  const fmtDur = (secs) => {
    secs = +secs || 0;
    if (!secs) return '';
    const h = Math.floor(secs / 3600), m = Math.round((secs % 3600) / 60);
    return h ? `${h} h ${m} min` : `${m} min`;
  };
  const toSecs = (d) => {
    if (!d) return 0;
    if (/^\d+$/.test(String(d))) return +d;
    const p = String(d).split(':').map(Number);
    return p.length === 3 ? p[0] * 3600 + p[1] * 60 + p[2] : p.length === 2 ? p[0] * 60 + p[1] : 0;
  };
  const firstOf = (x) => (Array.isArray(x) ? x[0] : x) || '';

  async function movieInfo(src, item) {
    if (src.type !== 'xtream') return { plot: '', year: item.year };
    const d = await xt(src, 'get_vod_info', { vod_id: item.id });
    const i = (d && d.info) || {};
    return {
      plot: i.plot || i.description || '', cast: i.cast || i.actors || '', director: i.director || '',
      genre: i.genre || '', year: (i.releasedate || i.release_date || '').slice(0, 4) || item.year,
      duration: fmtDur(i.duration_secs || toSecs(i.duration)), rating: parseFloat(i.rating) || item.rating || 0,
      backdrop: firstOf(i.backdrop_path) || i.cover_big || i.movie_image || '',
      poster: i.movie_image || i.cover_big || item.poster, trailer: i.youtube_trailer || '',
    };
  }

  async function seriesInfo(src, item) {
    if (src.type !== 'xtream') {
      const bySeason = new Map();
      for (const e of item.episodes || []) {
        if (!bySeason.has(e.season)) bySeason.set(e.season, []);
        bySeason.get(e.season).push({ id: e.id, n: e.episode, title: e.title, url: e.url, img: e.img, plot: '', dur: '' });
      }
      const seasons = [...bySeason.entries()].sort((a, b) => a[0] - b[0])
        .map(([n, eps]) => ({ n, episodes: eps.sort((a, b) => a.n - b.n) }));
      return { plot: '', seasons };
    }
    const d = await xt(src, 'get_series_info', { series_id: item.id });
    const i = (d && d.info) || {};
    const eps = d && d.episodes ? d.episodes : {};
    const seasons = Object.keys(eps).map((k) => ({
      n: +k,
      episodes: arr(eps[k]).map((e) => ({
        id: String(e.id), n: +e.episode_num || 0, title: e.title || `Episodio ${e.episode_num}`,
        ext: e.container_extension || 'mp4', plot: (e.info && e.info.plot) || '',
        img: (e.info && (e.info.movie_image || e.info.cover_big)) || '',
        dur: fmtDur((e.info && (e.info.duration_secs || toSecs(e.info.duration))) || 0),
      })).sort((a, b) => a.n - b.n),
    })).sort((a, b) => a.n - b.n);
    return {
      plot: i.plot || item.plot || '', cast: i.cast || '', director: i.director || '', genre: i.genre || '',
      year: (i.releaseDate || i.release_date || '').slice(0, 4) || item.year, rating: parseFloat(i.rating) || item.rating || 0,
      backdrop: firstOf(i.backdrop_path) || i.cover || '', poster: i.cover || item.poster, trailer: i.youtube_trailer || '',
      seasons,
    };
  }

  return { buildCatalog, streamUrl, altLiveUrl, movieInfo, seriesInfo, xtLogin, parseM3U, buildFromM3U, hash };
})();
