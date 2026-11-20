# Usar tu plan de Claude en la oficina

Con esto la oficina usa **tu suscripción de Claude** (la misma de tus chats) en vez de los créditos de la API.
Los agentes creativos (ideas, guion, plan de efectos, blog) pasan a **Sonnet**, que escribe mejor que Haiku,
sin costo por token. Aplica a las tres: la oficina del canal, la de TikTok Shop y la sala de edición.

- Cuenta para los **límites de uso de tu plan** (los mismos del chat). Si se acaban, la oficina sigue con los
  créditos de la API (si tienes) y regresa a tu plan en una hora.
- Es para tu uso personal: no compartas la oficina con otras personas ni la vendas como servicio.

## Pasos (una sola vez)

1. Entra a tu servidor:

```bash
ssh ubuntu@51.195.201.84
```

2. Revisa que Claude Code ya esté instalado (el servidor lo instala solo al actualizarse, en unos 10 minutos):

```bash
/usr/local/bin/claude --version
```

Debe salir algo como `2.x.x (Claude Code)`. Si dice "No such file", instálalo a mano:

```bash
sudo bash /opt/canal/autocanal/despliegue/claude_code.sh --forzar
```

3. Corre el asistente:

```bash
sudo -u canal /opt/canal/autocanal/.venv/bin/python /opt/canal/autocanal/oficina.py --configurar-suscripcion
```

- Te muestra un enlace: ábrelo en tu navegador, entra con tu cuenta de Claude y autoriza.
- Te da un código: pégalo en la terminal.
- Al final te muestra un token que empieza con `sk-ant-oat…`: cópialo y pégalo cuando te lo pida
  (no se ve al pegarlo). **No lo pegues en ningún chat.**
- Debe terminar con `✔ ¡Funciona!`.

4. Reinicia la oficina:

```bash
sudo systemctl restart oficina
```

Arriba en la oficina verás **🧠 Tu plan**. En cada tarea el gasto sale en $0 con la nota de cuánto habría costado
en la API.

## Si algo sale mal
- `No encontré Claude Code`: corre el comando del paso 2 con `--forzar` y fíjate si sale un ✖.
- `El token … no sirve o caducó` o `no contestó a tiempo`: repite el paso 3.
- Volver a usar solo la API: en `sudo nano /opt/canal/autocanal/.env` pon `MOTOR_IA=api` y reinicia.
