#!/usr/bin/env bash
# Baja la última versión del código y reinicia la oficina.   sudo bash actualizar.sh
set -euo pipefail
if [ "$(id -u)" -ne 0 ]; then echo "Córrelo con sudo:  sudo bash $0"; exit 1; fi
APP="$(cd "$(dirname "$0")/.." && pwd)"
REPO="$(cd "$APP/.." && pwd)"
sudo -u canal git -C "$REPO" pull --ff-only
sudo -u canal "$APP/.venv/bin/pip" install -q -r "$APP/requirements.txt"
systemctl restart oficina
echo "✔ Actualizado y reiniciado."
