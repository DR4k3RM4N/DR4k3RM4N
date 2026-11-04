const { app, BrowserWindow, Menu, shell, ipcMain } = require('electron');
const path = require('path');

const APP_NAME = 'RevoLabs MLT';
// Conserva la lista de lives y la sesión de TikTok de las versiones anteriores
// (que se llamaban "Monitor de Lives TikTok").
app.setPath('userData', path.join(app.getPath('appData'), 'Monitor de Lives TikTok'));
app.setName(APP_NAME);
// Necesario en Windows para que salgan los avisos de desconexión.
if (process.platform === 'win32') app.setAppUserModelId('com.revolabs.mlt');
const isMac = process.platform === 'darwin';

function createWindow() {
  const win = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 800,
    minHeight: 500,
    backgroundColor: '#111318',
    icon: path.join(__dirname, 'build', 'icon.png'),
    title: `${APP_NAME} · Monitor de Lives TikTok · v${app.getVersion()}`,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      webviewTag: true,
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  // En Mac se deja el menú básico para que funcionen Cmd+C, Cmd+V y Cmd+Q.
  Menu.setApplicationMenu(isMac ? Menu.buildFromTemplate([{ role: 'appMenu' }, { role: 'editMenu' }, { role: 'windowMenu' }]) : null);
  win.on('page-title-updated', (e) => e.preventDefault());
  win.on('focus', () => win.flashFrame(false));
  win.loadFile(path.join(__dirname, 'src', 'index.html'));
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
ipcMain.on('show-window', (e) => {
  const win = BrowserWindow.fromWebContents(e.sender);
  if (!win) return;
  if (win.isMinimized()) win.restore();
  win.show();
  win.focus();
});
ipcMain.on('toggle-fullscreen', (e) => {
  const win = BrowserWindow.fromWebContents(e.sender);
  if (win) win.setFullScreen(!win.isFullScreen());
});

ipcMain.on('app-info', (e) => {
  e.returnValue = { name: APP_NAME, version: app.getVersion(), platform: process.platform };
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
