const { app, BrowserWindow, Menu, shell, ipcMain, screen } = require('electron');
const path = require('path');
const fs = require('fs');
const { execFile } = require('child_process');

const APP_NAME = 'RevoLabs MLT';
// Conserva la lista de lives y la sesión de TikTok de las versiones anteriores
// (que se llamaban "Monitor de Lives TikTok").
app.setPath('userData', path.join(app.getPath('appData'), 'Monitor de Lives TikTok'));
app.setName(APP_NAME);
// Necesario en Windows para que salgan los avisos de desconexión.
if (process.platform === 'win32') app.setAppUserModelId('com.revolabs.mlt');
const isMac = process.platform === 'darwin';
// Permite que la app active el sonido de los lives sin que haya que dar clic dentro de TikTok.
app.commandLine.appendSwitch('autoplay-policy', 'no-user-gesture-required');
const isWin = process.platform === 'win32';

let mainWin = null;
const minis = new Map(); // usuario -> ventana flotante

function createWindow() {
  const win = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 800,
    minHeight: 500,
    backgroundColor: '#111318',
    icon: path.join(__dirname, 'build', 'icon.png'),
    title: `${APP_NAME} · Monitor de Lives TikTok · v${app.getVersion().replace('-', '.')}`,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      webviewTag: true,
      // Que la app siga revisando los lives aunque esté minimizada.
      backgroundThrottling: false,
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  mainWin = win;
  // En Mac se deja el menú básico para que funcionen Cmd+C, Cmd+V y Cmd+Q.
  Menu.setApplicationMenu(isMac ? Menu.buildFromTemplate([{ role: 'appMenu' }, { role: 'editMenu' }, { role: 'windowMenu' }]) : null);
  win.on('page-title-updated', (e) => e.preventDefault());
  win.on('focus', () => win.flashFrame(false));
  // Avisa a la página cuando la ventana se minimiza o se restaura, para no confundir
  // el video frenado por Windows/Mac con un live caído, y para abrir o cerrar la ventana flotante.
  const vis = (hidden) => () => { if (!win.isDestroyed()) win.webContents.send('window-hidden', hidden); };
  win.on('minimize', vis(true));
  win.on('hide', vis(true));
  win.on('restore', vis(false));
  win.on('show', vis(false));
  // Al cerrar la app se cierran también las ventanas flotantes.
  win.on('closed', () => {
    mainWin = null;
    for (const m of minis.values()) if (!m.isDestroyed()) m.destroy();
    minis.clear();
  });
  win.loadFile(path.join(__dirname, 'src', 'index.html'));
}

function showMain() {
  if (!mainWin || mainWin.isDestroyed()) return;
  if (mainWin.isMinimized()) mainWin.restore();
  mainWin.show();
  mainWin.focus();
}

// Devuelve el teclado a la ventana principal. En Windows, cuando un live (webview) tenía el foco
// o se cerró, la barra de búsqueda mostraba el cursor pero no recibía las teclas.
ipcMain.on('focus-main', (e) => {
  const win = BrowserWindow.fromWebContents(e.sender);
  if (!win) return;
  win.focus();
  e.sender.focus();
});

// Alerta de desconexión: hace parpadear la app en la barra de tareas (o rebotar en el Dock).
ipcMain.on('attention', (e) => {
  const win = BrowserWindow.fromWebContents(e.sender);
  if (!win) return;
  if (isMac) app.dock && app.dock.bounce('informational');
  else if (!win.isFocused()) win.flashFrame(true);
});
ipcMain.on('show-window', () => showMain());
ipcMain.on('toggle-fullscreen', (e) => {
  const win = BrowserWindow.fromWebContents(e.sender);
  if (win) win.setFullScreen(!win.isFullScreen());
});
ipcMain.on('set-fullscreen', (e, on) => {
  const win = BrowserWindow.fromWebContents(e.sender);
  if (win) win.setFullScreen(!!on);
});

ipcMain.on('app-info', (e) => {
  e.returnValue = { name: APP_NAME, version: app.getVersion().replace('-', '.'), platform: process.platform };
});

// ---------- Ventana flotante (siempre encima, como el mini reproductor de YouTube) ----------
const boundsFile = () => path.join(app.getPath('userData'), 'ventana-flotante.json');
function loadBounds() {
  try { return JSON.parse(fs.readFileSync(boundsFile(), 'utf8')); } catch { return null; }
}
function saveBounds(b) {
  try { fs.writeFileSync(boundsFile(), JSON.stringify(b)); } catch {}
}
function defaultBounds(index) {
  const area = screen.getPrimaryDisplay().workArea;
  const w = 300, h = 520; // vertical, como se ven los lives de TikTok
  const off = index * 28;
  return { width: w, height: h, x: area.x + area.width - w - 16 - off, y: area.y + area.height - h - 16 - off };
}
function onScreen(b) {
  return screen.getAllDisplays().some((d) => {
    const a = d.workArea;
    return b.x < a.x + a.width - 40 && b.x + b.width > a.x + 40 && b.y >= a.y - 10 && b.y < a.y + a.height - 40;
  });
}

ipcMain.on('pip-open', (_e, { user, audio, auto, sink }) => {
  if (minis.has(user)) {
    const m = minis.get(user);
    m.showInactive();
    return;
  }
  const saved = minis.size === 0 ? loadBounds() : null;
  const bounds = saved && onScreen(saved) ? saved : defaultBounds(minis.size);
  const mini = new BrowserWindow({
    ...bounds,
    minWidth: 180,
    minHeight: 200,
    frame: false,
    alwaysOnTop: true,
    skipTaskbar: true,
    fullscreenable: false,
    maximizable: false,
    backgroundColor: '#000000',
    title: `@${user} · ${APP_NAME}`,
    icon: path.join(__dirname, 'build', 'icon.png'),
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      webviewTag: true,
      backgroundThrottling: false,
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  // Nivel alto para que quede encima incluso de programas en pantalla completa.
  mini.setAlwaysOnTop(true, 'screen-saver');
  if (isMac) mini.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
  mini.loadFile(path.join(__dirname, 'src', 'mini.html'), { query: { user, audio: audio ? '1' : '0', sink: sink || '' } });
  // Se muestra sin quitarle el foco a lo que estés haciendo.
  mini.once('ready-to-show', () => mini.showInactive());
  const remember = () => { if (!mini.isDestroyed()) saveBounds(mini.getBounds()); };
  mini.on('moved', remember);
  mini.on('resized', remember);
  mini.on('closed', () => {
    minis.delete(user);
    if (mainWin && !mainWin.isDestroyed()) mainWin.webContents.send('pip-closed', user);
  });
  mini.auto = !!auto;
  minis.set(user, mini);
});
ipcMain.on('pip-close', (_e, user) => {
  const m = minis.get(user);
  if (m && !m.isDestroyed()) m.close();
});
// Cierra solo las ventanas que se abrieron solas al minimizar.
ipcMain.on('pip-close-auto', () => {
  for (const m of minis.values()) if (m.auto && !m.isDestroyed()) m.close();
});
// Botón "volver a la app" de la ventana flotante.
ipcMain.on('pip-back', (e, user) => {
  showMain();
  const m = BrowserWindow.fromWebContents(e.sender);
  if (m && !m.isDestroyed()) m.close();
  if (mainWin && !mainWin.isDestroyed()) mainWin.webContents.send('pip-select', user);
});
ipcMain.on('pip-audio', (_e, { user, on }) => {
  if (mainWin && !mainWin.isDestroyed()) mainWin.webContents.send('pip-audio', { user, on });
});

// ---------- Mandar la pantalla a la TV ----------
// Windows: abre el panel "Transmitir" (lo mismo que Win+K) para elegir la TV por Miracast.
// Mac: abre Ajustes de Pantallas, donde se elige la TV por AirPlay.
const CAST_PS = `
Add-Type -Namespace W -Name K -MemberDefinition '[DllImport("user32.dll")] public static extern void keybd_event(byte b, byte s, uint f, System.UIntPtr e);'
[W.K]::keybd_event(0x5B,0,0,[UIntPtr]::Zero)
[W.K]::keybd_event(0x4B,0,0,[UIntPtr]::Zero)
[W.K]::keybd_event(0x4B,0,2,[UIntPtr]::Zero)
[W.K]::keybd_event(0x5B,0,2,[UIntPtr]::Zero)
`;
ipcMain.handle('cast', async () => {
  if (isWin) {
    return new Promise((resolve) => {
      execFile('powershell.exe', ['-NoProfile', '-NonInteractive', '-WindowStyle', 'Hidden', '-Command', CAST_PS], { windowsHide: true, timeout: 8000 }, (err) => {
        if (!err) return resolve({ ok: true, how: 'win-k' });
        // Si no se pudo, se abre la configuración de pantallas inalámbricas.
        shell.openExternal('ms-settings-connectabledevices:devicediscovery')
          .then(() => resolve({ ok: true, how: 'settings' }))
          .catch(() => shell.openExternal('ms-settings:display').then(() => resolve({ ok: true, how: 'display' }), () => resolve({ ok: false })));
      });
    });
  }
  if (isMac) {
    try { await shell.openExternal('x-apple.systempreferences:com.apple.Displays-Settings.extension'); return { ok: true, how: 'mac' }; } catch {}
    try { await shell.openExternal('x-apple.systempreferences:com.apple.preference.displays'); return { ok: true, how: 'mac' }; } catch {}
    return { ok: false };
  }
  return { ok: false };
});

// Los enlaces que TikTok intente abrir en ventana nueva se abren en el navegador normal.
app.on('web-contents-created', (_e, contents) => {
  contents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith('http')) shell.openExternal(url);
    return { action: 'deny' };
  });
});

app.whenReady().then(createWindow);
app.on('window-all-closed', () => app.quit());
