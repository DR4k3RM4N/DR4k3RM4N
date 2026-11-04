// DrakoTV - proceso principal de Electron.
// Se encarga de: ventana, guardar datos en disco, descargar listas/guias sin
// problemas de CORS, y abrir reproductores externos (VLC / mpv).
const { app, BrowserWindow, ipcMain, dialog, shell, session, net } = require('electron');
const path = require('path');
const fs = require('fs');
const zlib = require('zlib');
const { spawn } = require('child_process');

// Permite elegir pista de audio (idioma) en peliculas MP4/MKV.
app.commandLine.appendSwitch('enable-blink-features', 'AudioVideoTracks');

const DEFAULT_UA = 'VLC/3.0.20 LibVLC/3.0.20';
let win = null;
let userAgent = DEFAULT_UA;

const dataDir = () => app.getPath('userData');
const storeFile = () => path.join(dataDir(), 'drakotv-data.json');
const cacheDir = () => path.join(dataDir(), 'cache');

// ---------- almacenamiento simple en JSON ----------
function readStore() {
  try { return JSON.parse(fs.readFileSync(storeFile(), 'utf8')); } catch { return {}; }
}
let store = null;
let saveTimer = null;
function saveStoreSoon() {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => {
    const tmp = storeFile() + '.tmp';
    fs.writeFileSync(tmp, JSON.stringify(store));
    fs.renameSync(tmp, storeFile());
  }, 300);
}

// ---------- descargas ----------
async function download(url, { timeoutMs = 60000 } = {}) {
  if (/^file:/i.test(url)) return fs.readFileSync(new URL(url));
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await net.fetch(url, { headers: { 'User-Agent': userAgent }, signal: ctrl.signal });
    if (!res.ok) throw new Error(`El servidor respondió ${res.status} ${res.statusText}`);
    return Buffer.from(await res.arrayBuffer());
  } catch (e) {
    if (e.name === 'AbortError') throw new Error('Tiempo de espera agotado al conectar con el servidor');
    throw e;
  } finally { clearTimeout(t); }
}
function bufToText(buf) {
  if (buf.length > 2 && buf[0] === 0x1f && buf[1] === 0x8b) buf = zlib.gunzipSync(buf);
  return buf.toString('utf8');
}

// ---------- guia XMLTV ----------
// Se parsea aqui (no en la ventana) porque las guias pueden pesar cientos de MB.
const unescapeXml = (s) => s
  .replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, '$1')
  .replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"')
  .replace(/&apos;/g, "'").replace(/&#(\d+);/g, (_, n) => String.fromCodePoint(+n))
  .replace(/&amp;/g, '&');
function parseXmltvDate(s) {
  const m = /^(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})?\s*([+-]\d{4})?/.exec(s || '');
  if (!m) return 0;
  let t = Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +(m[6] || 0));
  if (m[7]) {
    const sign = m[7][0] === '-' ? -1 : 1;
    t -= sign * (+m[7].slice(1, 3) * 60 + +m[7].slice(3, 5)) * 60000;
  }
  return t;
}
function parseXmltv(xml) {
  const now = Date.now();
  const from = now - 6 * 3600e3, to = now + 36 * 3600e3;
  const channels = {}; // id -> {name, icon}
  const chRe = /<channel\s+id="([^"]*)"[^>]*>([\s\S]*?)<\/channel>/g;
  let m;
  while ((m = chRe.exec(xml))) {
    const name = /<display-name[^>]*>([\s\S]*?)<\/display-name>/.exec(m[2]);
    const icon = /<icon\s+src="([^"]*)"/.exec(m[2]);
    channels[unescapeXml(m[1])] = { name: name ? unescapeXml(name[1]).trim() : '', icon: icon ? unescapeXml(icon[1]) : '' };
  }
  const programmes = {}; // id -> [{s,e,t,d}]
  const prRe = /<programme\b([^>]*)>([\s\S]*?)<\/programme>/g;
  while ((m = prRe.exec(xml))) {
    const attrs = m[1];
    const start = parseXmltvDate((/start="([^"]*)"/.exec(attrs) || [])[1]);
    const stop = parseXmltvDate((/stop="([^"]*)"/.exec(attrs) || [])[1]);
    if (!start || stop < from || start > to) continue;
    const ch = unescapeXml((/channel="([^"]*)"/.exec(attrs) || [])[1] || '');
    const title = /<title[^>]*>([\s\S]*?)<\/title>/.exec(m[2]);
    const desc = /<desc[^>]*>([\s\S]*?)<\/desc>/.exec(m[2]);
    (programmes[ch] ||= []).push({
      s: start, e: stop || start + 3600e3,
      t: title ? unescapeXml(title[1]).trim() : '',
      d: desc ? unescapeXml(desc[1]).trim().slice(0, 600) : '',
    });
  }
  for (const k in programmes) programmes[k].sort((a, b) => a.s - b.s);
  return { channels, programmes, loadedAt: now };
}

// ---------- ventana ----------
function createWindow() {
  win = new BrowserWindow({
    width: 1400, height: 860, minWidth: 980, minHeight: 600,
    backgroundColor: '#0b0d12',
    title: 'DrakoTV',
    icon: path.join(__dirname, 'build', 'icon.png'),
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });
  win.loadFile(path.join(__dirname, 'src', 'index.html'));
  win.on('enter-full-screen', () => win.webContents.send('fullscreen', true));
  win.on('leave-full-screen', () => win.webContents.send('fullscreen', false));
  // los enlaces externos se abren en el navegador
  win.webContents.setWindowOpenHandler(({ url }) => { shell.openExternal(url); return { action: 'deny' }; });
  win.webContents.on('will-navigate', (e, url) => { if (!url.startsWith('file:')) e.preventDefault(); });
}

function setupNetwork() {
  const ses = session.defaultSession;
  // Muchos servidores IPTV solo aceptan reproductores conocidos: usamos el User-Agent configurado.
  ses.webRequest.onBeforeSendHeaders((details, cb) => {
    const h = details.requestHeaders;
    if (/^https?:/i.test(details.url)) {
      h['User-Agent'] = userAgent;
      delete h['Origin'];
    }
    cb({ requestHeaders: h });
  });
  // Los streams casi nunca envian cabeceras CORS; las agregamos para que hls.js / mpegts.js funcionen.
  ses.webRequest.onHeadersReceived((details, cb) => {
    if (!/^https?:/i.test(details.url)) return cb({});
    const h = details.responseHeaders || {};
    for (const k of Object.keys(h)) if (/^access-control-allow-/i.test(k)) delete h[k];
    h['Access-Control-Allow-Origin'] = ['*'];
    h['Access-Control-Allow-Headers'] = ['*'];
    h['Access-Control-Allow-Methods'] = ['GET, HEAD, OPTIONS'];
    cb({ responseHeaders: h });
  });
}

// ---------- IPC ----------
function setupIpc() {
  ipcMain.handle('store:getAll', () => store);
  ipcMain.handle('store:set', (_e, key, value) => {
    store[key] = value;
    if (key === 'settings' && value && value.userAgent !== undefined) userAgent = value.userAgent || DEFAULT_UA;
    saveStoreSoon();
    return true;
  });

  ipcMain.handle('net:text', async (_e, url, opts) => bufToText(await download(url, opts)));
  ipcMain.handle('net:json', async (_e, url, opts) => {
    const txt = bufToText(await download(url, opts));
    try { return JSON.parse(txt); } catch { throw new Error('El servidor no devolvió datos válidos (revisa usuario, clave y URL)'); }
  });
  // Guia: se guarda en cache en disco y se reusa mientras tenga menos de maxAgeMs.
  ipcMain.handle('epg:load', async (_e, url, key, maxAgeMs = 6 * 3600e3, force = false) => {
    const file = path.join(cacheDir(), `${key}-epg.json`);
    if (!force) {
      try {
        const st = fs.statSync(file);
        if (Date.now() - st.mtimeMs < maxAgeMs) return JSON.parse(fs.readFileSync(file, 'utf8'));
      } catch {}
    }
    const epg = parseXmltv(bufToText(await download(url, { timeoutMs: 180000 })));
    fs.mkdirSync(cacheDir(), { recursive: true });
    fs.writeFileSync(file, JSON.stringify(epg));
    return epg;
  });

  ipcMain.handle('cache:get', (_e, key) => {
    try { return JSON.parse(fs.readFileSync(path.join(cacheDir(), key + '.json'), 'utf8')); } catch { return null; }
  });
  ipcMain.handle('cache:set', (_e, key, value) => {
    fs.mkdirSync(cacheDir(), { recursive: true });
    fs.writeFileSync(path.join(cacheDir(), key + '.json'), JSON.stringify(value));
    return true;
  });
  ipcMain.handle('cache:del', (_e, key) => {
    for (const f of fs.existsSync(cacheDir()) ? fs.readdirSync(cacheDir()) : []) {
      if (f.startsWith(key)) fs.rmSync(path.join(cacheDir(), f), { force: true });
    }
    return true;
  });

  ipcMain.handle('dialog:openM3u', async () => {
    const r = await dialog.showOpenDialog(win, {
      title: 'Elegir lista M3U',
      filters: [{ name: 'Listas M3U', extensions: ['m3u', 'm3u8', 'txt'] }, { name: 'Todos', extensions: ['*'] }],
      properties: ['openFile'],
    });
    if (r.canceled || !r.filePaths[0]) return null;
    return { path: r.filePaths[0], text: fs.readFileSync(r.filePaths[0], 'utf8') };
  });
  ipcMain.handle('dialog:pickExe', async () => {
    const r = await dialog.showOpenDialog(win, { title: 'Elegir reproductor (vlc.exe / mpv.exe)', properties: ['openFile'] });
    return r.canceled ? null : r.filePaths[0];
  });

  ipcMain.handle('player:external', (_e, exe, url, title) => {
    const candidates = exe ? [exe] : (process.platform === 'win32'
      ? ['C:\\Program Files\\VideoLAN\\VLC\\vlc.exe', 'C:\\Program Files (x86)\\VideoLAN\\VLC\\vlc.exe']
      : ['vlc', 'mpv']);
    const bin = candidates.find((c) => !path.isAbsolute(c) || fs.existsSync(c));
    if (!bin) throw new Error('No se encontró VLC. Instala VLC o elige el reproductor en Ajustes.');
    const isMpv = /mpv/i.test(path.basename(bin));
    const args = isMpv
      ? [`--user-agent=${userAgent}`, `--force-media-title=${title || ''}`, url]
      : [`--http-user-agent=${userAgent}`, `--meta-title=${title || ''}`, url];
    const child = spawn(bin, args, { detached: true, stdio: 'ignore' });
    child.on('error', () => {});
    child.unref();
    return true;
  });

  ipcMain.handle('win:fullscreen', (_e, on) => {
    win.setFullScreen(on === undefined ? !win.isFullScreen() : !!on);
    return win.isFullScreen();
  });
  ipcMain.handle('app:openExternal', (_e, url) => { if (/^https?:/i.test(url)) shell.openExternal(url); });
  ipcMain.handle('app:version', () => app.getVersion());
}

app.whenReady().then(() => {
  store = readStore();
  userAgent = (store.settings && store.settings.userAgent) || DEFAULT_UA;
  setupNetwork();
  setupIpc();
  createWindow();
  app.on('activate', () => { if (BrowserWindow.getAllWindows().length === 0) createWindow(); });
});
app.on('window-all-closed', () => {
  if (saveTimer) { clearTimeout(saveTimer); fs.writeFileSync(storeFile(), JSON.stringify(store)); }
  if (process.platform !== 'darwin') app.quit();
});
