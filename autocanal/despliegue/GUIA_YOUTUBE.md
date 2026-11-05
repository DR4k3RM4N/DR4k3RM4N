# Que Carla suba los videos a tu canal de YouTube

Carla (community manager) ya sabe subir el video cuando le das **Publicar** en la revisión: sube el
video con título, descripción (con el enlace al blog), etiquetas y la miniatura que elegiste, y luego
pone el video dentro de la entrada del blog. Solo falta darle permiso a tu canal.

## ⚠️ Lo que debes saber antes

YouTube pide que las apps que suben videos por su API pasen una **revisión (auditoría)**. Mientras tu
proyecto no la pase, **todo lo que se suba por la API queda en "Privado"**, aunque pidas público.

- Para empezar no es problema: Carla lo sube **privado**, tú lo ves en YouTube Studio y lo cambias a
  **Público** (o lo programas) con un clic. Es buena práctica de todos modos: es tu última revisión.
- Si quieres que se publique solo, en público, solicita la auditoría desde la consola de Google
  (formulario "YouTube API Services - Audit and Quota Extension"). Es gratis y tarda días o semanas.
- La cuota gratis permite unas **6 subidas al día**, de sobra para tu ritmo.

## 1. Crea las credenciales (10 min)

En **console.cloud.google.com**:

1. Arriba, **Seleccionar proyecto → Proyecto nuevo** (nombre: `oficina-canal`).
2. **APIs y servicios → Biblioteca** → busca **YouTube Data API v3** → **Habilitar**.
3. **APIs y servicios → Pantalla de consentimiento de OAuth**:
   - Tipo **Externo**, nombre de la app, tu correo.
   - En **Usuarios de prueba** agrega el correo de la cuenta de Google de tu canal.
   - Después dale **Publicar app** para que quede **"En producción"**. ⚠️ Si se queda en "Prueba", el
     permiso caduca cada 7 días y Carla dejaría de poder subir. (No necesitas que Google la verifique
     para usarla tú.)
4. **APIs y servicios → Credenciales → Crear credenciales → ID de cliente de OAuth**:
   tipo **App de escritorio** → **Crear** → **Descargar JSON**.
5. Renombra el archivo descargado a `client_secret.json`.

## 2. Súbelo al servidor

En una ventana de PowerShell **en tu computadora** (cambia la ruta por donde lo guardaste):

```bash
scp C:\Users\TU_USUARIO\Downloads\client_secret.json ubuntu@51.195.201.84:/tmp/
```

## 3. Autoriza tu canal

Conéctate con este comando especial (abre un túnel para el permiso):

```bash
ssh -L 8090:localhost:8090 ubuntu@51.195.201.84
```

Y ya dentro del servidor:

```bash
sudo install -o canal -g canal -m 600 /tmp/client_secret.json /opt/canal/autocanal/
```

```bash
cd /opt/canal/autocanal && sudo -u canal .venv/bin/python canal.py autorizar-youtube --puerto 8090 --sin-navegador
```

Te muestra un enlace: **ábrelo en el navegador de tu computadora**, elige la cuenta de tu canal y
acepta. Si dice "Google no verificó esta app", dale **Configuración avanzada → Ir a oficina-canal**
(es tu propia app). Al final aparece `✔ Listo, autorizado el canal: …`.

## 4. Ajustes (opcional) en `.env`

```
YT_PRIVACIDAD=private   # private · unlisted (oculto) · public (requiere la auditoría)
YT_CATEGORIA=28         # 28 = Ciencia y tecnología · 22 = Gente y blogs · 26 = Consejos y estilo
```

Reinicia después de cambiarlos: `sudo systemctl restart oficina`.

En la pestaña **Estilo → YouTube** de la oficina verás si tu canal ya está conectado.
