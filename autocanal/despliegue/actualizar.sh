#!/usr/bin/env bash
# Baja la última versión del código y reinicia la oficina.   sudo bash actualizar.sh
set -euo pipefail
if [ "$(id -u)" -ne 0 ]; then echo "Córrelo con sudo:  sudo bash $0"; exit 1; fi
APP="$(cd "$(dirname "$0")/.." && pwd)"
REPO="$(cd "$APP/.." && pwd)"
sudo -u canal git -C "$REPO" pull --ff-only
sudo -u canal "$APP/.venv/bin/pip" install -q -r "$APP/requirements.txt"
# La voz gratis de Microsoft cambia seguido: edge-tts siempre en su última versión.
sudo -u canal "$APP/.venv/bin/pip" install -q --upgrade edge-tts
# Igual el que baja videos de referencia (YouTube cambia seguido).
sudo -u canal "$APP/.venv/bin/pip" install -q --upgrade yt-dlp
# Memoria de respaldo (swap) de 2 GB: evita que el video se corte si se acaba la RAM.
if ! swapon --show | grep -q .; then
  echo "  Agregando 2 GB de memoria de respaldo (swap)…"
  fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile >/dev/null && swapon /swapfile
  grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi
# Aplica cambios de configuración del servidor que vengan en la nueva versión.
URL="$(grep '^OFICINA_URL=' "$APP/.env" | cut -d= -f2- || true)"
DOMINIO="${URL#https://}"
if [ -n "$DOMINIO" ] && [ -f "$APP/despliegue/caddy.sh" ]; then bash "$APP/despliegue/caddy.sh" "$DOMINIO"; fi
systemctl restart oficina
# La oficina de TikTok Shop (ala derecha del edificio)
if [ -f "$APP/despliegue/tienda.sh" ]; then bash "$APP/despliegue/tienda.sh"; fi
# La Sala de edición (tus compus editan los videos)
if [ -f "$APP/despliegue/sala.sh" ]; then bash "$APP/despliegue/sala.sh"; fi
# Revisar que todo quedó prendido (la oficina y Caddy, que la deja entrar desde internet).
sleep 3
for servicio in oficina caddy; do
  if ! systemctl is-active --quiet "$servicio"; then
    echo "  $servicio no quedó prendido; lo vuelvo a arrancar…"
    systemctl restart "$servicio"; sleep 3
  fi
  systemctl is-active --quiet "$servicio" && echo "  ✔ $servicio funcionando" || echo "  ✖ $servicio NO arrancó: sudo journalctl -u $servicio -n 30"
done
echo "✔ Actualizado y reiniciado."
