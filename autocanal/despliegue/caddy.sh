#!/usr/bin/env bash
# Escribe la configuración de Caddy (HTTPS) para la oficina, la valida y la aplica.
# Si la nueva no es válida, deja la anterior.   sudo bash caddy.sh midominio
set -euo pipefail
DOMINIO="$1"
NUEVO="$(mktemp)"
cat > "$NUEVO" <<CADDY
$DOMINIO {
	# Las actualizaciones en vivo (/eventos) no se comprimen: comprimirlas las retrasa.
	@comprimir not path /eventos
	encode @comprimir gzip
	reverse_proxy 127.0.0.1:8765 {
		flush_interval -1
	}
}
CADDY
if caddy validate --adapter caddyfile --config "$NUEVO" >/dev/null 2>&1; then
  [ -f /etc/caddy/Caddyfile ] && cp /etc/caddy/Caddyfile /etc/caddy/Caddyfile.anterior
  install -m 644 "$NUEVO" /etc/caddy/Caddyfile
  systemctl reload caddy 2>/dev/null || systemctl restart caddy
  echo "  Caddy: configuración aplicada para $DOMINIO"
else
  echo "  Caddy: la configuración nueva no es válida, dejo la anterior:"
  caddy validate --adapter caddyfile --config "$NUEVO" 2>&1 | tail -3 || true
  [ -f /etc/caddy/Caddyfile ] || { echo "$DOMINIO {"; echo "	reverse_proxy 127.0.0.1:8765"; echo "}"; } > /etc/caddy/Caddyfile
  systemctl restart caddy
fi
rm -f "$NUEVO"
