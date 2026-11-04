const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('app', {
  focusMain: () => ipcRenderer.send('focus-main'),
  attention: () => ipcRenderer.send('attention'),
  showWindow: () => ipcRenderer.send('show-window'),
  toggleFullscreen: () => ipcRenderer.send('toggle-fullscreen'),
  onWindowHidden: (cb) => ipcRenderer.on('window-hidden', (_e, hidden) => cb(hidden)),
  info: ipcRenderer.sendSync('app-info'),
});
