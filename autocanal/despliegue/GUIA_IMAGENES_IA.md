# 🖼️ Imágenes realistas para las miniaturas (Mina)

Mina hace la escena realista de la miniatura (una persona con cara seria frente al lugar del caso) con IA. Hay dos
opciones; la oficina usa **Cloudflare primero (gratis)** y **Gemini de respaldo** si lo conectas.

| | Cloudflare Workers AI (FLUX) | Gemini (Google) |
|---|---|---|
| Costo | **Gratis** (cuota diaria, sin tarjeta) | ~4 a 7 centavos de dólar por imagen |
| Calidad | Fotos realistas muy buenas | Muy buena |
| Necesita | Cuenta gratis de Cloudflare | Cuenta de Google con facturación activada |

Las claves van en el `.env` del servidor, **nunca en el chat**.

## Opción 1 (recomendada): Cloudflare, gratis

1. Entra a **dash.cloudflare.com** y crea una cuenta gratis (no pide tarjeta).
2. En el menú de la izquierda: **AI → Workers AI**.
3. Dale **Use REST API**. Ahí ves tu **Account ID** (cópialo).
4. En esa misma pantalla: **Create a Workers AI API Token → Create API Token**. Copia el token (solo se ve una vez).
5. En el servidor:
   ```
   sudo nano /opt/canal/autocanal/.env
   ```
   Hasta abajo agrega (con tus datos):
   ```
   CLOUDFLARE_ACCOUNT_ID=tu_account_id
   CLOUDFLARE_AI_TOKEN=tu_token
   ```
   Guarda con Ctrl + O, Enter, y sal con Ctrl + X.
6. Reinicia la oficina:
   ```
   sudo systemctl restart oficina
   ```
7. En `/expedientes`, la tarjeta 🏭 de la Bandeja dice **«🖼️ Imágenes realistas: Cloudflare (gratis)»**.

## Opción 2: Gemini (de paga, de respaldo)

1. Entra a **aistudio.google.com** → **Get API key → Create API key**.
2. Las imágenes por API **no son gratis**: en ese proyecto activa la facturación (**Set up billing**).
3. En el `.env` del servidor agrega `GEMINI_API_KEY=tu_clave` y reinicia con `sudo systemctl restart oficina`.
4. Opcional: `GEMINI_MODELO_IMAGEN=gemini-3.1-flash-image-preview` (si no lo pones, la oficina prueba ese y luego el
   anterior).

Si tienes las dos, Mina usa Cloudflare y solo si falla usa Gemini. Sin ninguna, usa la mejor foto real del material.
