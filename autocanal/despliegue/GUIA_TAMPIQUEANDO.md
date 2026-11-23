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
2. En **developers.facebook.com** → Mis apps → **Crear app** (tipo Empresa). En **Configuración → Básica** están el
   **App ID** y el **App Secret** (no los pegues en ningún chat).
3. **Herramientas → Explorador de la API Graph**: elige tu app, agrega los permisos `pages_show_list`,
   `pages_manage_posts`, `pages_read_engagement`, `business_management`, `instagram_basic`,
   `instagram_content_publish` y dale **Generate Access Token** (marca tu página y tu Instagram).
4. En el servidor corre el asistente; te pide App ID, App Secret y ese token (no se ven al pegarlos), y solo saca el
   token de página que no caduca, el id de la página y el de Instagram:
   ```
   cd /opt/canal/autocanal && sudo -u canal .venv/bin/python oficina.py --configurar-tampico
   ```
5. Reinicia: `sudo systemctl restart oficina`. En la pestaña 🌮 Tampico deben salir ✅.

## TikTok
TikTok no deja publicar automático sin auditar la app (semanas). La oficina te deja el video listo con su texto:
botón «⬇ Para TikTok».

## Dron
Respeta lo de la AFAC: registro si tu dron lo requiere, máx. 120 m, siempre a la vista, nunca sobre gente, lejos del
aeropuerto de Tampico y de zonas industriales (refinería, puerto). Revisa las zonas restringidas antes de cada vuelo.
