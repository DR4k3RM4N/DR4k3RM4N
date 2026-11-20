#!/usr/bin/env bash
# Instala (o actualiza) Claude Code en el servidor para que la oficina use tu plan de Claude.
#   sudo bash claude_code.sh
# Se instala como root (CLAUDE_INSTALL_ALLOW_SUDO=1) y se copia a /usr/local/bin/claude para el usuario de la oficina.
set -uo pipefail
if [ "$(id -u)" -ne 0 ]; then echo "Córrelo con sudo:  sudo bash $0"; exit 1; fi
# Ya instalado hace menos de 7 días: no se vuelve a bajar en cada actualización automática.
if [ -x /usr/local/bin/claude ] && [ -n "$(find /usr/local/bin/claude -mtime -7 2>/dev/null)" ] && [ "${1:-}" != "--forzar" ]; then
  echo "  ✔ Claude Code ya está instalado"; exit 0
fi
echo "  Instalando/actualizando Claude Code…"
if ! curl -fsSL https://claude.ai/install.sh | CLAUDE_INSTALL_ALLOW_SUDO=1 bash >/tmp/claude_install.log 2>&1; then
  echo "  ✖ No se pudo instalar Claude Code (detalles: /tmp/claude_install.log). La oficina sigue con la API."
  exit 0
fi
BIN="$(readlink -f /root/.local/bin/claude 2>/dev/null || true)"
if [ -z "$BIN" ] || [ ! -x "$BIN" ]; then
  echo "  ✖ No encontré el programa de Claude Code después de instalarlo. La oficina sigue con la API."
  exit 0
fi
install -m 755 "$BIN" /usr/local/bin/claude
echo "  ✔ Claude Code $(/usr/local/bin/claude --version 2>/dev/null | head -1)"
