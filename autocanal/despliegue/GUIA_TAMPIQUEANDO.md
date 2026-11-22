# 🌮 Conectar Tampiqueando (una sola vez)

Las claves van en el servidor (`sudo nano /opt/canal/autocanal/.env`), nunca en el chat.

## 1. WhatsApp: plantilla para el primer mensaje a los negocios
WhatsApp solo deja escribirle primero a alguien con una **plantilla aprobada por Meta**.
1. En **business.facebook.com → WhatsApp Manager → Plantillas de mensajes → Crear plantilla**.
2. Categoría **Marketing**, nombre `tampiqueando_colaboracion`, idioma **Español (México)**.
3. Cuerpo (ejemplo; el `{{1}}` es el nombre del negocio):
   > ¡Hola, {{1}}! Soy Miguel de Tampiqueando 🌮, una cuenta de comida de Tampico y Madero en Facebook, Instagram y
   > TikTok. Nos encantaría hacerles un video. ¿Les gustaría que les platique la idea?
   Agrega un botón de respuesta rápida «No, gracias» (así quien no quiera se da de baja solo).
4. Cuando Meta la apruebe, en el `.env`:
   ```
   TAMPICO_WA_PLANTILLA=tampiqueando_colaboracion
   ```
Usa el mismo número de WhatsApp de la oficina (ya configurado). Empieza con pocos mensajes al día (5-8): si muchos
bloquean o reportan, Meta baja la calidad del número.

## 2. Facebook (página) e Instagram (empresa)
1. Tu Instagram debe ser **cuenta de empresa o creador** y estar **vinculado a la página de Facebook** de Tampiqueando.
2. En **developers.facebook.com** crea una app (tipo Empresa) y agrega los productos **Facebook Login** e
   **Instagram Graph API**.
3. En **Herramientas → Explorador de la API Graph**: elige tu app, pide los permisos `pages_show_list`,
   `pages_manage_posts`, `pages_read_engagement`, `instagram_basic`, `instagram_content_publish`, y genera el token.
4. Cámbialo por un token de **larga duración** y saca el **token de página** (en el explorador: `me/accounts`).
   Ahí mismo ves el **id de la página**. El id de Instagram sale con `PAGINA_ID?fields=instagram_business_account`.
5. En el `.env`:
   ```
   TAMPICO_FB_PAGINA=id_de_la_pagina
   TAMPICO_FB_TOKEN=token_de_pagina
   TAMPICO_IG_ID=id_de_instagram
   ```
   (Instagram necesita también `OFICINA_URL` con la dirección pública de tu oficina; ya la tienes.)
6. Reinicia la oficina (`sudo bash /opt/canal/autocanal/despliegue/actualizar.sh`). En la pestaña 🌮 Tampico deben
   salir ✅.

## TikTok
TikTok no deja publicar automático sin auditar la app (semanas). La oficina te deja el video listo con su texto:
botón «⬇ Para TikTok».

## Dron
Respeta lo de la AFAC: registro si tu dron lo requiere, máx. 120 m, siempre a la vista, nunca sobre gente, lejos del
aeropuerto de Tampico y de zonas industriales (refinería, puerto). Revisa las zonas restringidas antes de cada vuelo.
