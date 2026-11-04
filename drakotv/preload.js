// Puente seguro entre la ventana y el proceso principal.
const { contextBridge, ipcRenderer } = require('electron');

const call = (ch) => (...args) => ipcRenderer.invoke(ch, ...args);

contextBridge.exposeInMainWorld('api', {
  store: { getAll: call('store:getAll'), set: call('store:set') },
  net: { text: call('net:text'), json: call('net:json') },
  epg: { load: call('epg:load') },
  cache: { get: call('cache:get'), set: call('cache:set'), del: call('cache:del') },
  dialog: { openM3u: call('dialog:openM3u'), pickExe: call('dialog:pickExe') },
  player: { external: call('player:external') },
  win: {
    fullscreen: call('win:fullscreen'),
    onFullscreen: (fn) => ipcRenderer.on('fullscreen', (_e, v) => fn(v)),
  },
  app: { openExternal: call('app:openExternal'), version: call('app:version') },
});
