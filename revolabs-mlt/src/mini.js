// Ventana flotante: muestra un solo live, siempre encima de las demás ventanas.
const params = new URLSearchParams(location.search);
const user = params.get('user');
let audioOn = params.get('audio') === '1';
let videoOnly = true;
const liveUrl = `https://www.tiktok.com/@${user}/live`;

document.getElementById('name').textContent = '@' + user;
document.title = `@${user} · RevoLabs MLT`;

const webview = document.createElement('webview');
webview.setAttribute('partition', 'persist:tiktok');
webview.setAttribute('webpreferences', 'backgroundThrottling=no');
webview.setAttribute('src', liveUrl);
document.body.prepend(webview);

// Evita que la rueda del mouse o las flechas cambien a otro live (igual que en la cuadrícula).
const LOCK_SCRIPT = `(() => {
  if (window.__monitorLock) return true;
  window.__monitorLock = true;
  const block = (e) => e.stopImmediatePropagation();
  window.addEventListener('wheel', block, { capture: true });
  window.addEventListener('keydown', (e) => {
    const t = e.target;
    const typing = t && (t.isContentEditable || /^(INPUT|TEXTAREA)$/.test(t.tagName));
    if (!typing && ['ArrowUp', 'ArrowDown', 'PageUp', 'PageDown'].includes(e.key)) block(e);
  }, { capture: true });
  return true;
})()`;

// "Solo video": el video del live ocupa toda la ventanita, sin el resto de la página.
const PIN_SCRIPT = `(() => {
  if (!window.__mltPin) {
    const st = document.createElement('style');
    st.id = '__mlt_pin_style';
    window.__mltPin = { on: false, st };
    setInterval(() => window.__mltPin.apply(), 800);
    window.__mltPin.apply = () => {
      const p = window.__mltPin;
      if (!p.st.isConnected && document.head) document.head.appendChild(p.st);
      const vids = [...document.querySelectorAll('video')].filter((x) => x.clientWidth > 30);
      const v = vids.sort((a, b) => b.clientWidth * b.clientHeight - a.clientWidth * a.clientHeight)[0];
      document.querySelectorAll('[data-mlt-pin]').forEach((x) => { if (x !== v) x.removeAttribute('data-mlt-pin'); });
      if (v) v.setAttribute('data-mlt-pin', '');
      p.st.textContent = p.on ? 'html,body{overflow:hidden!important;background:#000!important}' +
        '[data-mlt-pin]{position:fixed!important;inset:0!important;width:100vw!important;height:100vh!important;' +
        'max-width:none!important;max-height:none!important;object-fit:contain!important;z-index:2147483646!important;' +
        'background:#000!important;transform:none!important;border-radius:0!important}' : '';
    };
  }
  return true;
})()`;
const setPin = () => webview.executeJavaScript(`${PIN_SCRIPT}; window.__mltPin.on = ${videoOnly}; window.__mltPin.apply(); true`).catch(() => {});

webview.addEventListener('dom-ready', () => {
  webview.setAudioMuted(!audioOn);
  webview.setZoomFactor(0.5);
  webview.executeJavaScript(LOCK_SCRIPT).catch(() => {});
  webview.executeJavaScript(window.MLT_AUDIO.pageScript(params.get('sink') || '')).catch(() => {});
  setPin();
});
// Si TikTok cambia a otro usuario, se regresa a este live.
const guard = (e) => {
  const url = (e.url || '').toLowerCase();
  if (/tiktok\.com\/@[^/]+\/live/.test(url) && !url.includes(`/@${user}/live`)) webview.loadURL(liveUrl);
};
webview.addEventListener('did-navigate', guard);
webview.addEventListener('did-navigate-in-page', guard);

const audioBtn = document.getElementById('audio');
const paintAudio = () => { audioBtn.textContent = audioOn ? '🔊' : '🔇'; };
paintAudio();
audioBtn.onclick = () => {
  audioOn = !audioOn;
  try { webview.setAudioMuted(!audioOn); } catch {}
  paintAudio();
  window.app.pipAudio(user, audioOn);
};
document.getElementById('fit').onclick = () => { videoOnly = !videoOnly; setPin(); };
document.getElementById('back').onclick = () => window.app.pipBack(user);
document.getElementById('close').onclick = () => window.close();

// Los controles se ven unos segundos al abrir y luego solo al pasar el mouse.
setTimeout(() => document.body.classList.remove('show'), 3000);
