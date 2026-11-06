#!/usr/bin/env bash
# Instala la Oficina AutoCanal en un servidor Ubuntu (probado para 24.04 / 26.04).
#   sudo bash instalar.sh                 -> usa una dirección gratis tipo 1-2-3-4.sslip.io
#   sudo bash instalar.sh midominio.com   -> usa tu propio dominio (apúntalo antes a la IP)
# Se puede volver a correr: no borra tu .env ni tus videos.
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then echo "Córrelo con sudo:  sudo bash $0"; exit 1; fi

APP="$(cd "$(dirname "$0")/.." && pwd)"        # .../autocanal
REPO="$(cd "$APP/.." && pwd)"
USR=canal
paso() { printf '\n\033[1;33m▶ %s\033[0m\n' "$1"; }

paso "Instalando programas (Python, ffmpeg, fuentes, firewall)"
apt-get update -q
DEBIAN_FRONTEND=noninteractive apt-get install -y -q python3 python3-venv python3-pip ffmpeg \
  fonts-dejavu-core git curl ufw debian-keyring debian-archive-keyring apt-transport-https gnupg

paso "Instalando Caddy (HTTPS automático)"
if ! command -v caddy >/dev/null; then
  if ! DEBIAN_FRONTEND=noninteractive apt-get install -y -q caddy; then
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' > /etc/apt/sources.list.d/caddy-stable.list
    apt-get update -q && apt-get install -y -q caddy
  fi
fi

# Memoria de respaldo (swap) de 2 GB: evita que el video se corte si se acaba la RAM.
if ! swapon --show | grep -q .; then
  echo "  Agregando 2 GB de memoria de respaldo (swap)…"
  fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile >/dev/null && swapon /swapfile
  grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

paso "Creando el usuario '$USR' que corre la oficina"
id "$USR" >/dev/null 2>&1 || useradd --system --home-dir "$REPO" --shell /usr/sbin/nologin "$USR"
chown -R "$USR:$USR" "$REPO"

paso "Instalando librerías de Python"
sudo -u "$USR" python3 -m venv "$APP/.venv"
sudo -u "$USR" "$APP/.venv/bin/pip" install -q --upgrade pip
sudo -u "$USR" "$APP/.venv/bin/pip" install -q -r "$APP/requirements.txt"

paso "Configurando dirección y contraseña"
IP="$(curl -4 -fsS https://api.ipify.org || hostname -I | awk '{print $1}')"
if [ -z "${1:-}" ] && [ -z "$IP" ]; then echo "No pude saber la IP pública. Pásame el dominio: sudo bash $0 midominio.com"; exit 1; fi
DOMINIO="${1:-${IP//./-}.sslip.io}"
ENV="$APP/.env"
pon() { # pon CLAVE VALOR  (agrega o reemplaza en .env)
  if grep -q "^$1=" "$ENV"; then sed -i "s|^$1=.*|$1=$2|" "$ENV"; else echo "$1=$2" >> "$ENV"; fi
}
NUEVO=0
if [ ! -f "$ENV" ]; then
  cp "$APP/.env.example" "$ENV"
  NUEVO=1
  pon OFICINA_PASSWORD "$(python3 -c 'import secrets; print(secrets.token_urlsafe(15))')"
  pon OFICINA_DEMO 1   # arranca en demo hasta que pongas tus claves
fi
pon OFICINA_URL "https://$DOMINIO"
grep -q '^OFICINA_PASSWORD=.\+' "$ENV" || pon OFICINA_PASSWORD "$(python3 -c 'import secrets; print(secrets.token_urlsafe(15))')"
chown "$USR:$USR" "$ENV"
chmod 600 "$ENV"

paso "Creando el servicio (arranca solo y se reinicia si falla)"
cat > /etc/systemd/system/oficina.service <<UNIT
[Unit]
Description=Oficina AutoCanal
After=network-online.target
Wants=network-online.target

[Service]
User=$USR
WorkingDirectory=$APP
ExecStart=$APP/.venv/bin/python oficina.py --sin-navegador
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1
NoNewPrivileges=true
ProtectSystem=full
PrivateTmp=true

[Install]
WantedBy=multi-user.target
UNIT

paso "Configurando HTTPS para $DOMINIO"
bash "$APP/despliegue/caddy.sh" "$DOMINIO"

paso "Firewall: solo SSH y web"
ufw allow OpenSSH >/dev/null
ufw allow 80/tcp >/dev/null
ufw allow 443/tcp >/dev/null
ufw --force enable >/dev/null

systemctl daemon-reload
systemctl enable --now oficina >/dev/null 2>&1
systemctl restart oficina
systemctl enable caddy >/dev/null 2>&1

sleep 3
CLAVE="$(grep '^OFICINA_PASSWORD=' "$ENV" | cut -d= -f2-)"
USUARIO="$(grep '^OFICINA_USUARIO=' "$ENV" | cut -d= -f2-)"
printf '\n\033[1;32m✔ Listo\033[0m\n'
echo "  Oficina:    https://$DOMINIO   (el certificado puede tardar 1 minuto la primera vez)"
echo "  Usuario:    ${USUARIO:-jefe}"
echo "  Contraseña: $CLAVE      ← guárdala"
systemctl is-active --quiet oficina && echo "  Servicio:   funcionando" || echo "  Servicio:   NO arrancó, revisa: journalctl -u oficina -n 50"
if [ "$NUEVO" = 1 ]; then
  echo
  echo "  Está en MODO DEMO. Cuando pongas tus claves:  sudo nano $ENV"
  echo "  cambia OFICINA_DEMO=0 y reinicia:              sudo systemctl restart oficina"
fi
