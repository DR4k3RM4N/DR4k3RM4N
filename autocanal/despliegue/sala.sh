#!/usr/bin/env bash
# Prende (o reinicia) la Sala de edición como servicio: tus compus editan en lugar del servidor.
# Solo escucha dentro del servidor (127.0.0.1:8767); tus compus entran por el edificio con su propia llave.
#   sudo bash sala.sh
set -euo pipefail
if [ "$(id -u)" -ne 0 ]; then echo "Córrelo con sudo:  sudo bash $0"; exit 1; fi
APP="$(cd "$(dirname "$0")/.." && pwd)"
REPO="$(cd "$APP/.." && pwd)"
SALA="$REPO/salaedicion"
USR="$(stat -c %U "$APP")"
[ -f "$SALA/sala.py" ] || { echo "  No encontré $SALA/sala.py (¿falta actualizar el código?)"; exit 1; }
cat > /etc/systemd/system/sala.service <<UNIT
[Unit]
Description=Sala de edicion (tus compus editan los videos)
After=network-online.target
Wants=network-online.target

[Service]
User=$USR
WorkingDirectory=$SALA
ExecStart=$APP/.venv/bin/python sala.py
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
systemctl enable sala >/dev/null 2>&1
systemctl restart sala
sleep 2
if systemctl is-active --quiet sala; then
  echo "  ✔ sala (Sala de edición) funcionando"
else
  echo "  ✖ sala NO arrancó: sudo journalctl -u sala -n 30"
fi
