#!/usr/bin/env bash
# Baja la última versión del código y reinicia la oficina.   sudo bash actualizar.sh
set -euo pipefail
if [ "$(id -u)" -ne 0 ]; then echo "Córrelo con sudo:  sudo bash $0"; exit 1; fi
APP="$(cd "$(dirname "$0")/.." && pwd)"
REPO="$(cd "$APP/.." && pwd)"
sudo -u canal git -C "$REPO" pull --ff-only
# 🔑 Compus de Miguel que pueden entrar al servidor por SSH: sus llaves PÚBLICAS viven en despliegue/llaves_ssh/
# (las pone Claude en el repositorio); aquí se agregan al usuario administrador si todavía no están.
ADMIN="${ADMIN_SSH:-ubuntu}"
if id "$ADMIN" >/dev/null 2>&1 && ls "$APP/despliegue/llaves_ssh/"*.pub >/dev/null 2>&1; then
  CASA_ADMIN="$(getent passwd "$ADMIN" | cut -d: -f6)"
  install -d -m 700 -o "$ADMIN" -g "$ADMIN" "$CASA_ADMIN/.ssh"
  touch "$CASA_ADMIN/.ssh/authorized_keys"
  for llave in "$APP/despliegue/llaves_ssh/"*.pub; do
    linea="$(head -n 1 "$llave" | tr -d '\r')"
    case "$linea" in ssh-ed25519\ *|ssh-rsa\ *|ecdsa-sha2-*) ;; *) echo "  aviso: $llave no parece una llave pública"; continue ;; esac
    grep -qF "$(echo "$linea" | cut -d' ' -f2)" "$CASA_ADMIN/.ssh/authorized_keys" || { echo "$linea" >> "$CASA_ADMIN/.ssh/authorized_keys"; echo "  ✔ llave agregada: $(basename "$llave")"; }
  done
  chown "$ADMIN:$ADMIN" "$CASA_ADMIN/.ssh/authorized_keys"; chmod 600 "$CASA_ADMIN/.ssh/authorized_keys"
fi
# Para convertir en imagen las miniaturas que Claude dibuja con código
dpkg -s libcairo2 >/dev/null 2>&1 || DEBIAN_FRONTEND=noninteractive apt-get install -y -q libcairo2 >/dev/null
# Letras libres para el motor de Expedientes cuando el video lo hace el servidor (no tiene las de Windows)
dpkg -s fonts-roboto >/dev/null 2>&1 || DEBIAN_FRONTEND=noninteractive apt-get install -y -q fonts-roboto fonts-dejavu-core >/dev/null || echo "aviso: no se pudieron instalar las letras"
sudo -u canal "$APP/.venv/bin/pip" install -q -r "$APP/requirements.txt"
# La voz gratis de Microsoft cambia seguido: edge-tts siempre en su última versión.
sudo -u canal "$APP/.venv/bin/pip" install -q --upgrade edge-tts
# Igual el que baja videos de referencia (YouTube cambia seguido).
sudo -u canal "$APP/.venv/bin/pip" install -q --upgrade yt-dlp
# Whisper local (gratis) para transcribir los videos que le pasas al chat. Opcional: si falla, no detiene nada.
sudo -u canal "$APP/.venv/bin/pip" install -q "faster-whisper>=1.0" || echo "aviso: no se pudo instalar faster-whisper"
# Claude Code: para que la oficina use tu plan de Claude en vez de créditos de la API.
bash "$APP/despliegue/claude_code.sh" || true
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
# De aquí en adelante se actualiza solo (revisa GitHub cada minuto); se prende la primera vez y se vuelve a
# instalar si el reloj guardado es de una versión vieja (antes revisaba cada 10 min).
if [ -f "$APP/despliegue/autoactualizar.sh" ] && { ! systemctl is-enabled --quiet autocanal-actualizar.timer 2>/dev/null \
    || ! grep -q "OnUnitActiveSec=1min" /etc/systemd/system/autocanal-actualizar.timer 2>/dev/null; }; then
  bash "$APP/despliegue/autoactualizar.sh" --activar
fi
echo "✔ Actualizado y reiniciado."
