#!/usr/bin/env bash
# Se actualiza solo: cada 10 minutos revisa si hay versión nueva en GitHub y, si nadie está editando, la instala.
# Lo corre el reloj del servidor (autocanal-actualizar.timer). Para prenderlo una vez:  sudo bash autoactualizar.sh --activar
# Para apagarlo:  sudo bash autoactualizar.sh --apagar      Para ver qué ha hecho:  sudo tail -n 30 /var/log/autocanal-actualizar.log
set -uo pipefail
if [ "$(id -u)" -ne 0 ]; then echo "Córrelo con sudo:  sudo bash $0 ${1:-}"; exit 1; fi
APP="$(cd "$(dirname "$0")/.." && pwd)"
REPO="$(cd "$APP/.." && pwd)"
USR="$(stat -c %U "$APP")"
LOG=/var/log/autocanal-actualizar.log

if [ "${1:-}" = "--activar" ]; then
  cat > /etc/systemd/system/autocanal-actualizar.service <<UNIT
[Unit]
Description=AutoCanal: instala la versión nueva si hay
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/bin/env bash $APP/despliegue/autoactualizar.sh
UNIT
  cat > /etc/systemd/system/autocanal-actualizar.timer <<UNIT
[Unit]
Description=AutoCanal: revisa cada 10 minutos si hay versión nueva

[Timer]
OnBootSec=3min
OnUnitActiveSec=10min
RandomizedDelaySec=60

[Install]
WantedBy=timers.target
UNIT
  systemctl daemon-reload
  systemctl enable --now autocanal-actualizar.timer >/dev/null 2>&1
  echo "  ✔ Se actualiza solo: revisa GitHub cada 10 minutos (si están editando, espera a que terminen)."
  exit 0
fi
if [ "${1:-}" = "--apagar" ]; then
  systemctl disable --now autocanal-actualizar.timer >/dev/null 2>&1
  echo "  ✔ Apagado: ya no se actualiza solo (usa actualizar.sh a mano)."
  exit 0
fi

anota() { echo "$(date '+%Y-%m-%d %H:%M:%S')  $*" >> "$LOG"; }
[ -f "$LOG" ] && [ "$(stat -c %s "$LOG")" -gt 1000000 ] && mv -f "$LOG" "$LOG.anterior"

# ¿Hay versión nueva?
if ! sudo -u "$USR" git -C "$REPO" fetch -q 2>>"$LOG"; then anota "No pude revisar GitHub (¿sin internet?)."; exit 0; fi
ACTUAL="$(sudo -u "$USR" git -C "$REPO" rev-parse HEAD)"
NUEVA="$(sudo -u "$USR" git -C "$REPO" rev-parse '@{u}' 2>/dev/null || echo "$ACTUAL")"
[ "$ACTUAL" = "$NUEVA" ] && exit 0

# ¿Alguien está trabajando? Entonces espero a la siguiente vuelta (para no cortar un video a la mitad).
ESPERA="$REPO/.autoactualizar_esperando"
ocupado=""
if [ -f "$REPO/.cola_video.lock" ] && ! flock -n "$REPO/.cola_video.lock" true; then ocupado="se está haciendo un video"; fi
if [ -z "$ocupado" ] && curl -fsS -m 5 http://127.0.0.1:8767/api/estado 2>/dev/null \
    | grep -qE '"estado": ?"(asignado|trabajando)"'; then ocupado="la sala de edición está editando"; fi
if [ -n "$ocupado" ]; then
  # tope: si lleva más de 3 horas esperando, se actualiza de todos modos
  if [ ! -f "$ESPERA" ]; then date +%s > "$ESPERA"; fi
  if [ $(( $(date +%s) - $(cat "$ESPERA") )) -lt 10800 ]; then anota "Hay versión nueva, pero $ocupado: espero."; exit 0; fi
  anota "Llevo 3 horas esperando: actualizo de todos modos."
fi
rm -f "$ESPERA"

anota "Versión nueva ($(sudo -u "$USR" git -C "$REPO" log -1 --format=%s '@{u}' | cut -c1-90)): actualizando…"
if bash "$APP/despliegue/actualizar.sh" >> "$LOG" 2>&1; then
  anota "✔ Actualizado a $(sudo -u "$USR" git -C "$REPO" rev-parse --short HEAD)."
  date '+%Y-%m-%d %H:%M' > "$REPO/.ultima_actualizacion"
  chown "$USR" "$REPO/.ultima_actualizacion"
else
  anota "✖ La actualización falló (arriba está el error). Se reintenta en la siguiente vuelta."
fi
