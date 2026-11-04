const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('app', {
  focusMain: () => ipcRenderer.send('focus-main'),
  attention: () => ipcRenderer.send('attention'),
  showWindow: () => ipcRenderer.send('show-window'),
  toggleFullscreen: () => ipcRenderer.send('toggle-fullscreen'),
  info: ipcRenderer.sendSync('app-info'),
});
