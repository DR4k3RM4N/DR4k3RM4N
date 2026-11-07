#!/usr/bin/env bash
# Prende (o reinicia) la oficina de TikTok Shop como servicio: arranca sola y se reinicia si falla.
# Solo escucha dentro del servidor (127.0.0.1:8766); se entra por el edificio con la misma contraseña.
#   sudo bash tienda.sh
set -euo pipefail
if [ "$(id -u)" -ne 0 ]; then echo "Córrelo con sudo:  sudo bash $0"; exit 1; fi
APP="$(cd "$(dirname "$0")/.." && pwd)"
REPO="$(cd "$APP/.." && pwd)"
TIENDA="$REPO/tiktokshop"
USR="$(stat -c %U "$APP")"
[ -f "$TIENDA/tienda.py" ] || { echo "  No encontré $TIENDA/tienda.py (¿falta actualizar el código?)"; exit 1; }
# El "oído" de Cris (Whisper) para los subtítulos karaoke con tu voz. La primera vez baja ~500 MB.
if [ -f "$TIENDA/requirements.txt" ]; then
  echo "  Instalando lo que necesita la oficina de TikTok (la primera vez tarda unos minutos)…"
  sudo -u "$USR" "$APP/.venv/bin/pip" install -q -r "$TIENDA/requirements.txt" || echo "  ⚠ No se pudo instalar Whisper: Cris editará sin subtítulos."
fi
cat > /etc/systemd/system/tienda.service <<UNIT
[Unit]
Description=Oficina TikTok Shop
After=network-online.target
Wants=network-online.target

[Service]
User=$USR
WorkingDirectory=$TIENDA
ExecStart=$APP/.venv/bin/python tienda.py
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1
NoNewPrivileges=true
ProtectSystem=full
PrivateTmp=true

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable tienda >/dev/null 2>&1
systemctl restart tienda
sleep 3
if systemctl is-active --quiet tienda; then
  echo "  ✔ tienda (oficina TikTok Shop) funcionando"
else
  echo "  ✖ tienda NO arrancó: sudo journalctl -u tienda -n 30"
fi
