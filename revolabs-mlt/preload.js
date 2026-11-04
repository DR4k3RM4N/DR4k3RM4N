const { contextBridge, ipcRenderer } = require('electron');

const on = (channel) => (cb) => ipcRenderer.on(channel, (_e, data) => cb(data));

contextBridge.exposeInMainWorld('app', {
  focusMain: () => ipcRenderer.send('focus-main'),
  attention: () => ipcRenderer.send('attention'),
  showWindow: () => ipcRenderer.send('show-window'),
  toggleFullscreen: () => ipcRenderer.send('toggle-fullscreen'),
  setFullscreen: (v) => ipcRenderer.send('set-fullscreen', v),
  onWindowHidden: on('window-hidden'),
  // Ventana flotante
  pipOpen: (user, audio, auto, sink) => ipcRenderer.send('pip-open', { user, audio, auto, sink }),
  pipClose: (user) => ipcRenderer.send('pip-close', user),
  pipCloseAuto: () => ipcRenderer.send('pip-close-auto'),
  pipBack: (user) => ipcRenderer.send('pip-back', user),
  pipAudio: (user, isOn) => ipcRenderer.send('pip-audio', { user, on: isOn }),
  onPipClosed: on('pip-closed'),
  onPipSelect: on('pip-select'),
  onPipAudio: on('pip-audio'),
  // TV
  cast: () => ipcRenderer.invoke('cast'),
  info: ipcRenderer.sendSync('app-info'),
});
