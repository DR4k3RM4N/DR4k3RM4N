// Sonido de los lives: se usa en la ventana principal y en la ventana flotante.
//
// 1) TikTok deja su video en silencio por su cuenta. La app ya controla qué live suena,
//    así que dentro de la página el video se deja siempre con sonido y volumen al 100%.
// 2) Salida de audio: si Windows/Mac no manda el sonido a la TV, aquí se puede elegir
//    a qué dispositivo va (por nombre, porque cada página ve identificadores distintos).
window.MLT_AUDIO = {
  pageScript(label) {
    return `(() => {
      window.__mltSink = ${JSON.stringify(label || '')};
      if (!window.__mltAudio) {
        window.__mltAudio = true;
        const apply = async () => {
          const media = [...document.querySelectorAll('video, audio')];
          for (const m of media) {
            if (m.muted) m.muted = false;
            if (m.volume < 1) m.volume = 1;
          }
          if (!media.length || !navigator.mediaDevices || !HTMLMediaElement.prototype.setSinkId) return;
          let id = '';
          if (window.__mltSink) {
            try {
              const devs = await navigator.mediaDevices.enumerateDevices();
              const d = devs.find((x) => x.kind === 'audiooutput' && x.label === window.__mltSink);
              if (d) id = d.deviceId;
            } catch {}
          }
          for (const m of media) if (m.sinkId !== id) m.setSinkId(id).catch(() => {});
        };
        window.__mltAudioApply = apply;
        setInterval(apply, 2000);
      }
      window.__mltAudioApply();
      return true;
    })()`;
  },

  async outputs() {
    try {
      const devs = await navigator.mediaDevices.enumerateDevices();
      return devs.filter((d) => d.kind === 'audiooutput' && d.deviceId !== 'default' && d.deviceId !== 'communications' && d.label);
    } catch { return []; }
  },

  // Tono de prueba, por la salida elegida (o la del sistema).
  async testTone(label) {
    const ctx = new AudioContext();
    if (label && ctx.setSinkId) {
      const d = (await this.outputs()).find((x) => x.label === label);
      if (d) { try { await ctx.setSinkId(d.deviceId); } catch {} }
    }
    const now = ctx.currentTime;
    [523, 659, 784, 1047].forEach((f, i) => {
      const o = ctx.createOscillator();
      const g = ctx.createGain();
      o.frequency.value = f;
      g.gain.setValueAtTime(0.0001, now + i * 0.25);
      g.gain.exponentialRampToValueAtTime(0.4, now + i * 0.25 + 0.02);
      g.gain.exponentialRampToValueAtTime(0.0001, now + i * 0.25 + 0.24);
      o.connect(g).connect(ctx.destination);
      o.start(now + i * 0.25);
      o.stop(now + i * 0.25 + 0.25);
    });
    setTimeout(() => ctx.close(), 1500);
  },
};
