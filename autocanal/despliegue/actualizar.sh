#!/usr/bin/env bash
# Baja la última versión del código y reinicia la oficina.   sudo bash actualizar.sh
set -euo pipefail
if [ "$(id -u)" -ne 0 ]; then echo "Córrelo con sudo:  sudo bash $0"; exit 1; fi
APP="$(cd "$(dirname "$0")/.." && pwd)"
REPO="$(cd "$APP/.." && pwd)"
sudo -u canal git -C "$REPO" pull --ff-only
sudo -u canal "$APP/.venv/bin/pip" install -q -r "$APP/requirements.txt"
# Aplica cambios de configuración del servidor que vengan en la nueva versión.
URL="$(grep '^OFICINA_URL=' "$APP/.env" | cut -d= -f2- || true)"
DOMINIO="${URL#https://}"
if [ -n "$DOMINIO" ] && [ -f "$APP/despliegue/caddy.sh" ]; then bash "$APP/despliegue/caddy.sh" "$DOMINIO"; fi
systemctl restart oficina
echo "✔ Actualizado y reiniciado."
