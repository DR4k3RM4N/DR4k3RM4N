# Instrucciones para Claude (léelas siempre)

Trabajas con **Miguel** (GitHub DR4k3RM4N), de México. Tiene el canal de YouTube **"Apps que sí pagan"** y el blog
**appsquesipagan.com**. Este repo tiene su "oficina" de agentes de IA que hace los videos sola (`autocanal/`).
Ahora quiere una **segunda oficina para TikTok Shop**.

**Antes de hacer nada, lee `CONTEXTO.md`.** Ahí está todo el historial, cómo está montado el servidor, qué falta
y el plan de la oficina de TikTok Shop.

## Cómo hablarle
- En español de México, casual y directo ("va", "jefe", "chido" está bien). Él no es programador.
- Paso a paso. Cada comando en su propio bloque ```bash``` para que lo copie por separado. Nada de "edita la línea 40".
- Dile qué va a ver después de cada paso y qué hacer si sale un error.
- Respuestas cortas; las explicaciones técnicas, solo si las pide.

## Reglas que ya acordamos (no las rompas)
- **Nunca le pidas que pegue claves, contraseñas o tokens en el chat.** Las claves van en el `.env` del servidor
  (`sudo nano /opt/canal/autocanal/.env`) o con los asistentes `--configurar-…` de `oficina.py`.
- **Lo más barato posible.** Modelos Haiku (`claude-haiku-5-5`) para casi todo, Sonnet solo para estudiar estilos
  una vez. Búsquedas con **Serper/Tavily** (Google), no con la búsqueda web de Claude. Él cuida mucho el gasto
  (hay tope diario `LIMITE_DIARIO`, 1 USD por defecto) y quiere ver el costo en centavos.
- **Nada inventado**: datos con fuente, comentarios de usuarios copiados tal cual, URLs que de verdad salieron.
- Antes de subir cambios: compila, y prueba en **modo demo** (`python oficina.py --demo --puerto 8787`) con
  Playwright (ya está instalado). Borra `oficina_estado_demo.json` e `historial_demo.json` antes del commit.
- El repo es **público**: no metas claves, correos ni datos personales en archivos.
- El servidor se actualiza desde la rama `claude/keen-johnson-v42a39` con
  `sudo bash /opt/canal/autocanal/despliegue/actualizar.sh`. Después: recargar la oficina con Ctrl + F5.
- Commits en español, describiendo lo que él va a notar.
