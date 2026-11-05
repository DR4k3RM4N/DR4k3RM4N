# Montar la oficina en tu VPS de OVH

Al terminar tendrás la oficina en una dirección `https://…` con contraseña, funcionando las 24 horas.
Paola buscará ideas sola cada mañana y te avisará por Telegram.

Tiempo: unos 30 minutos. Todo se hace desde **PowerShell** en tu computadora (en Windows: tecla
Windows → escribe "PowerShell" → Enter).

> En los comandos, cambia `TU_IP` por la IP que te mandó OVH por correo (algo como `51.68.10.20`).

---

## 1. Entrar al servidor

```bash
ssh ubuntu@TU_IP
```

- La primera vez te pregunta si confías en el servidor: escribe `yes`.
- Te pide la contraseña del correo de OVH. **Al escribirla no se ve nada; es normal.**
- Si te pide cambiarla, pon una nueva y vuelve a entrar con `ssh ubuntu@TU_IP`.

Sabes que entraste cuando ves algo como `ubuntu@vps-xxxx:~$`.

## 2. Instalar todo (un solo paso)

Copia y pega estos tres comandos, uno por uno:

```bash
sudo apt-get update && sudo apt-get install -y git
```

```bash
sudo git clone -b claude/keen-johnson-v42a39 https://github.com/DR4k3RM4N/DR4k3RM4N.git /opt/canal
```

```bash
sudo bash /opt/canal/autocanal/despliegue/instalar.sh
```

Tarda unos minutos. Al final te muestra:

```
✔ Listo
  Oficina:    https://51-68-10-20.sslip.io
  Usuario:    jefe
  Contraseña: xxxxxxxxxxxxxxxxxxxx      ← guárdala
```

Abre esa dirección en tu navegador o en tu celular, pon el usuario y la contraseña, y vas a ver la
oficina **en modo demo** (simulada, no gasta nada). Si no carga a la primera, espera un minuto: el
certificado HTTPS se genera la primera vez.

> La dirección `…sslip.io` es gratis y funciona sin comprar dominio. Si después compras uno (por
> ejemplo `oficina.tucanal.com`), apúntalo a `TU_IP` y corre
> `sudo bash /opt/canal/autocanal/despliegue/instalar.sh oficina.tucanal.com`.

## 3. Poner tus claves

```bash
sudo nano /opt/canal/autocanal/.env
```

Se abre un editor. Muévete con las flechas y llena:

| Clave | De dónde sale |
|---|---|
| `ANTHROPIC_API_KEY` | console.anthropic.com → API Keys |
| `CANAL_NOMBRE`, `CANAL_ESTILO` | Tu canal y cómo hablas |
| `WP_URL`, `WP_USUARIO`, `WP_APP_PASSWORD` | Tu WordPress → Usuarios → Perfil → Contraseñas de aplicación |
| `IDEAS_HORA` | A qué hora busca ideas Paola sola (ej. `09:00`, hora de México) |
| `OFICINA_DEMO` | Cámbialo a `0` para que trabajen de verdad |

Guarda con **Ctrl+O**, Enter, y sal con **Ctrl+X**. Luego reinicia la oficina:

```bash
sudo systemctl restart oficina
```

## 4. Conectar YouTube

**a) En Google Cloud Console** (console.cloud.google.com):
1. Crea un proyecto y activa **YouTube Data API v3**.
2. En **Pantalla de consentimiento de OAuth**, agrega tu correo y luego dale a **Publicar app**
   para que quede **"En producción"**. ⚠️ Si la dejas en "Prueba", el permiso caduca cada 7 días
   y la publicación deja de funcionar sola. Para uso propio no necesitas que Google la verifique.
3. En **Credenciales → Crear credenciales → ID de cliente de OAuth → App de escritorio**.
   Descarga el JSON y renómbralo `client_secret.json`.

**b) Súbelo al servidor.** En una ventana **nueva** de PowerShell (en tu computadora, no en el
servidor), cambiando la ruta por donde lo descargaste:

```bash
scp C:\Users\TU_USUARIO\Downloads\client_secret.json ubuntu@TU_IP:/tmp/
```

**c) Autoriza tu canal.** Conéctate con este comando especial (abre un "túnel" para el permiso):

```bash
ssh -L 8090:localhost:8090 ubuntu@TU_IP
```

Y ya dentro del servidor:

```bash
sudo install -o canal -g canal -m 600 /tmp/client_secret.json /opt/canal/autocanal/
```

```bash
cd /opt/canal/autocanal && sudo -u canal .venv/bin/python canal.py autorizar-youtube --puerto 8090 --sin-navegador
```

Te muestra un enlace largo. **Cópialo y ábrelo en el navegador de tu computadora**, elige tu canal
y acepta. Al final dice `✔ Listo, autorizado el canal: …`. Ya puedes cerrar esa ventana.

## 5. Chat con tu equipo por Telegram (gratis, 5 minutos)

1. En Telegram busca **@BotFather**, escríbele `/newbot`, ponle un nombre (ej. "Oficina de mi canal")
   y un usuario que termine en `bot`. Te da un **token**: cópialo.
2. En el servidor corre el asistente y pega el token cuando te lo pida:

```bash
cd /opt/canal/autocanal && sudo -u canal .venv/bin/python oficina.py --configurar-telegram
```

3. Te dice que abras tu bot en Telegram y le des **INICIAR**. Al hacerlo, el asistente te reconoce,
   guarda todo y te manda un mensaje de bienvenida.
4. Reinicia la oficina:

```bash
sudo systemctl restart oficina
```

Desde ahora Paola te manda las ideas con botones **✅ / ❌**, te avisa cuando un video está listo y le
puedes escribir: *¿cómo van?*, *pendientes*, *busca apps de encuestas*, *no 2 ya la hicimos*… Abajo del
chat tienes botones fijos para lo más común. Solo obedece mensajes tuyos.

(¿Prefieres WhatsApp? Funciona igual pero Meta cobra por mensaje y pide más pasos:
[`GUIA_WHATSAPP.md`](GUIA_WHATSAPP.md).)

---

## Para el día a día

Ver qué está pasando (Ctrl+C para salir):

```bash
sudo journalctl -u oficina -f
```

Reiniciar la oficina:

```bash
sudo systemctl restart oficina
```

Actualizar a la última versión del código:

```bash
sudo bash /opt/canal/autocanal/despliegue/actualizar.sh
```

Ver cuánto disco queda:

```bash
df -h /
```

Ver tu contraseña de la oficina:

```bash
sudo grep OFICINA_PASSWORD /opt/canal/autocanal/.env
```

## Bueno saber

- **Siempre activa:** si el servidor se reinicia, la oficina arranca sola. Si algo falla, se
  reinicia en 5 segundos. Un video que se quedó a medias aparece en tu bandeja con **Reintentar**.
- **Disco:** al terminar cada video se borran los pedazos intermedios, y 30 días después de
  publicar se borra el video del servidor (ya está en YouTube); se cambia con `LIMPIAR_DIAS`.
  La miniatura, el guion y la evidencia se quedan.
- **Seguridad:** el firewall solo deja pasar SSH y la web; la oficina pide usuario y contraseña.
  Nunca compartas el archivo `.env` ni lo subas a GitHub (ya está excluido).
- **Respaldo:** tu VPS tiene backup diario de OVH. Todo lo importante vive en
  `/opt/canal/autocanal` (`.env`, `salida/`, `oficina_estado.json`, `historial.json`,
  `youtube_token.json`), así que mudarte a otro servidor es copiar esa carpeta.
