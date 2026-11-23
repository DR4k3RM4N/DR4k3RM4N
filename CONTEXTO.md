# Contexto completo del proyecto (para continuar en un chat nuevo)

Última actualización: noviembre 2026. Rama de trabajo: `claude/keen-johnson-v42a39`.

## 1. Qué es

`autocanal/` es una **agencia automática de agentes de IA** para el canal de YouTube "Apps que sí pagan"
(público de México). Busca apps que prometen pagar dinero (y desde hace poco **cualquier tema**: videojuegos,
películas, tecnología…), las investiga, escribe el guion, narra, edita el video, hace miniaturas, escribe el blog
con SEO y publica en YouTube y WordPress.

Se ve como una **oficina isométrica en pixel art** (original, parecida en espíritu a Habbo, sin copiarlo) en el
navegador, donde los agentes caminan, trabajan en paralelo, platican, se van al **patio de descanso** cuando no
tienen trabajo, y **Paola (productora) le propone ideas al jefe y le pide su opinión/aprobación**.

### El equipo
| id | Nombre | Rol |
|---|---|---|
| productora | Paola | Ideas, entiende lo que pide el jefe, propone y pregunta |
| investigador | Iván | Play Store + Google (Serper/Tavily), expediente con evidencia |
| guionista | Gabi | Guion por escenas, títulos, textos de miniatura |
| locutor | Leo | Voz (Edge TTS gratis, con tiempos por palabra; o ElevenLabs) |
| disenadora | Dani | Miniaturas (3 opciones con el estilo aprendido; elige la más parecida a tus referencias) |
| editor | Edu | Video con ffmpeg: motion graphics por escena, subtítulos karaoke, transiciones, música |
| redactora | Rosa | Blog SEO (preguntas de Google, búsquedas relacionadas, enlaces internos) |
| community | Carla | Sube a YouTube (y WordPress) |
| jefe | Tú (Miguel) | Aprueba, opina, pide cambios |

## 2. Cómo está hecho (autocanal/)
- `oficina.py`: servidor (Python stdlib, `ThreadingHTTPServer`), estado, tareas, propuestas, proyectos, gasto,
  SSE `/eventos`, contraseña (OFICINA_PASSWORD), chat por Telegram/WhatsApp, tope diario, reanudar trabajos
  interrumpidos (hasta 2 veces), agenda de ideas diaria. Flags: `--demo`, `--host`, `--puerto`,
  `--configurar-telegram`, `--configurar-whatsapp`, `--configurar-tampico`, `--probar-whatsapp`, `--probar-wordpress`.
- `canal.py`: la producción (`Produccion`) con etapas y dependencias (`DEPENDE`): investigar → {guion, blog};
  guion → {voz, miniatura}; voz → video. Varias corren al mismo tiempo. `publicar()` sigue con YouTube aunque falle
  WordPress (el blog queda pendiente con botón "Subir blog" → `publicar_blog()`).
  Ids de proyecto: `com.app` (Play Store), `com.app~2` (segundo video), `web:slug` (app fuera de Play Store),
  `tema:slug` (tema libre).
- `agentes/`:
  - `claude.py`: llamadas al API (salidas JSON estructuradas, costo por llamada, tope diario). Modelo por tarea en
    `TAREAS` (todo Haiku 5.5, `estilo` en Sonnet 5.5); se cambia con `MODELO_<TAREA>` en `.env`.
  - `buscador.py`: entiende el pedido (`idea` / `app` / `tema` de apps / `libre` = cualquier tema / general).
  - `temas.py`: temas libres: ideas con lo que se busca en Google ahora, investigación, imágenes.
  - `investigador.py`, `playstore.py`, `buscar_web.py` (Serper/Tavily: búsqueda, SEO, imágenes).
  - `guionista.py` (modo apps y modo tema), `voz.py`, `graficos.py` (tarjetas y miniaturas con Pillow),
    `editor.py` (ffmpeg; transiciones por grupos de 6 para no quedarse sin RAM; caché de escenas; avance en vivo),
    `efectos.py` (plan de motion graphics de Edu: contador, texto que salta, sello, cintillo, zoom de golpe,
    sacudida, destello, borde de alerta; con sonidos generados), `estilo.py` (estilo aprendido: miniaturas, blog,
    video de referencia por archivo o **enlace con yt-dlp**), `blog.py` (WordPress REST), `youtube.py`,
    `telegram.py`, `whatsapp.py`, `chat_jefe.py`, `simulado.py` (modo demo sin APIs).
- `oficina/`: `index.html`, `app.js` (pestañas Bandeja, Equipo, Proyectos, Estilo, Chat; revisión con 3
  miniaturas y SEO), `oficina.js` (motor isométrico en canvas + patio), `estilo.css`.
- `despliegue/`: `instalar.sh`, `actualizar.sh`, `caddy.sh`, guías `GUIA_SERVIDOR.md`, `GUIA_WHATSAPP.md`,
  `GUIA_YOUTUBE.md`.
- No se suben a GitHub: `.env`, `estilo/`, `salida/`, `entrada/`, tokens.

## 3. El servidor (ya funcionando)
- **OVH VPS-1** (Europa/UK), Ubuntu. Entra con `ssh ubuntu@51.195.201.84`.
- Código en `/opt/canal` (clon de la rama `claude/keen-johnson-v42a39`), app en `/opt/canal/autocanal`,
  usuario de servicio `canal`, servicio systemd `oficina`, **Caddy** (HTTPS) → `127.0.0.1:8765`,
  dirección `https://51-195-201-84.sslip.io`, firewall ufw, swap de 2 GB (se agregó por un corte por falta de RAM).
- `.env` en `/opt/canal/autocanal/.env` (leerlo/editarlo con `sudo`).
- Actualizar: `sudo bash /opt/canal/autocanal/despliegue/actualizar.sh` (baja código, instala dependencias,
  actualiza edge-tts y yt-dlp, revisa Caddy y la oficina).
- Logs: `sudo journalctl -u oficina -n 50` · `sudo journalctl -u caddy -n 30`.
- Conectado: Anthropic, Serper y Tavily, Telegram (chat con el equipo), YouTube (OAuth hecho, la app de Google Cloud
  ya está publicada). WhatsApp Cloud API está programado (opcional).

## 3b. Motor de IA: tu plan de Claude (desde nov 2026)
- `agentes/claude.py` llama a Claude por **dos caminos**: la suscripción de Miguel vía Claude Code (`claude -p`
  con salida JSON estructurada, token de `claude setup-token` en `CLAUDE_CODE_OAUTH_TOKEN`) o la API.
  `MOTOR_IA=auto` (por defecto) usa el plan y cae a la API si se acaba el límite (pausa 1 h) o si el token falla.
- Con el plan: Sonnet en ideas/investigar/guion/blog/edición/estilo, Haiku en lo simple
  (`SUSCRIPCION_MODELO_<TAREA>`). Gasto registrado en $0 con el "equivalente en API".
- Claude Code se instala en `/usr/local/bin/claude` con `despliegue/claude_code.sh` (lo corre actualizar.sh).
  Corre con HOME en `autocanal/.claude_casa/` y en una carpeta vacía (no lee el CLAUDE.md del repo).
- Asistente: `oficina.py --configurar-suscripcion`. Guía: `despliegue/GUIA_SUSCRIPCION.md`.
- Ojo: con un token inválido Claude Code se queda esperando; por eso hay tiempo límite y se pausa el plan.

## 3c. La "fábrica" del video de referencia (nov 2026)
Miguel vio un video de una "fábrica" de videos con Claude y pidió "haz todo, yo no quiero hacer nada". Se agregó:
- **📘 Manual del canal** (`agentes/manual.py`, `estilo/manual.md`): la "skill" del canal; la leen ideas, guion,
  plan de efectos y blog. Se escribe solo (Paola, `estudiar("manual")`) con cuadros + transcripción (faster-whisper)
  del video de referencia, lo aprendido y las preferencias; también al estudiar un video. Editable en Estilo y
  descargable como SKILL.md (`/descargar/manual-skill.md`).
- **📈 Cazador de tendencias** (`agentes/tendencias.py`): API de YouTube con el OAuth del canal (scope `youtube`),
  videos de los últimos 30 días, multiplicador = vistas ÷ suscriptores, sin Shorts; `NICHO_CONSULTAS` en .env.
  Alimenta a Paola (apps y temas); las ideas muestran "📈 Inspirada en…". VidIQ no se usa (solo existe en claude.ai).
- **Guion en tabla**: cada escena con momento (gancho/desarrollo/regancho/cierre), voz (principal/segunda) y sonido;
  gancho ≤10 palabras, re-gancho cada ~60 s, 150 palabras/min; 5 títulos (mejor primero), 6 textos de miniatura.
- **Dos voces** (ajuste `dos_voces`, por defecto sí): la segunda (`VOZ_EDGE_2`, por defecto Dalia si la principal es
  Jorge) pregunta o reacciona. **Mascota** (`estilo/mascota.png`): se mece en una esquina del video y sale en la
  miniatura si no hay cara. **Miniaturas**: hasta 10 opciones (por defecto 6).
- **🚀 Piloto automático** (casilla en Bandeja, `oficina.piloto`): tras pedir ideas, Paola arranca sola la mejor
  (la del jefe > potencial alto > inspirada en tendencia). Publicar sigue siendo un toque del jefe (los videos
  hablan de apps y estafas: se revisa antes). Con "☀️ ideas cada mañana" + piloto, sale un video al día solo.
- **Publicar a una hora** (ajuste `publicar_hora`): Carla sube privado con `publishAt` y YouTube lo hace público
  a esa hora (si la app de Google no está auditada, YouTube puede dejarlo privado).

## 3d. Prueba propia y robot del Android (nov 2026)
Miguel hacía sus videos instalando la app, grabando la pantalla (anuncios = más apps estafa) y poniendo un GIF de
fondo para llenar 16:9. Se automatizó:
- **Fase 1** (`autocanal/agentes/prueba.py`): "📱 Probé esta app" en Bandeja (`/api/grabacion?app=`) o "Subir mi
  grabación" en el proyecto (`?proyecto=`, rehace desde investigar). Grabaciones en `entrada/<id>/` y
  `salida/<id>/prueba_robot/`. Claude ve ~40 cuadros (tarea "prueba", Sonnet con el plan) → `prueba.json`
  (cómo funciona, promesa, pago mínimo, retiro, anuncios con app anunciada, momentos con segundo). Va al
  expediente (`prueba_propia`), el guion la cuenta en primera persona con escenas `grabacion` + `desde`, y las apps
  de dinero anunciadas se vuelven propuestas ("📢 Salió anunciada dentro de…"). Fondo de relleno: `estilo/fondo_relleno`
  (GIF/video/imagen, tipo "fondo"); sin fondo, la grabación desenfocada.
- **Fase 2** (`salaedicion/robot_cel.py` + `cel.py`): trabajo de sala `probar_app`; la compu lo anuncia si Claude
  Code está listo y `adb devices` muestra un cel autorizado (chip "📱 modelo" en la pestaña Sala). Graba con
  `screenrecord` en trozos de 170 s, corre Claude Code (`--allowedTools Bash(./cel:*) Read`, Sonnet) con reglas de
  seguridad en CLAUDE.md (nada de datos reales, pagos, permisos sensibles, APKs, retiros), junta la grabación,
  desinstala la app y sube `prueba.mp4` + `notas.json`. La oficina lo pide en `Produccion.investigar` si no hay
  grabación y `probar_en_cel` está prendido. adb se instala solo con winget (Google.PlatformTools).
  Guía para preparar el cel: `salaedicion/GUIA_CELULAR.md`. Probado aquí con adb y Claude simulados; falta
  probar con el cel real de Miguel.

- **⭐ Lista de deseos** (`oficina.deseos`): el robot le pica a los anuncios de apps de dinero y con
  `./cel guardar_deseo` guarda la app que abrió (paquete de Play Store vía `dumpsys activity`, o la URL), sin
  instalarla; Iván también agrega las apps de dinero que lee en las grabaciones. Bandeja → "⭐ Lista de deseos" con
  "📱 Probar ahora"/"Quitar". 🔁 Con el piloto prendido y el cel disponible, `_ciclo_deseos` prueba la siguiente
  (una a la vez, sin otros videos en producción, `DESEOS_POR_DIA`, 2 por defecto) → video → más anuncios → más deseos.

## 3e. Miniaturas ilustradas (nov 2026)
Estilo de Miguel para "Apps que sí pagan" (sus referencias: caricatura 2D vibrante, personaje expresivo con el cel,
billetes/monedas, titular enorme en pregunta a la izquierda, icono de la app en cuadro blanco arriba a la derecha,
botón SUSCRÍBETE abajo a la izquierda). `agentes/ilustrador.py`: Claude (tarea "miniatura_ia") escribe 3 conceptos
distintos (escena en inglés + titular en español + por qué sube el CTR, reglas de su prompt de Gemini); Gemini
(`GEMINI_API_KEY`, `GEMINI_MODELO_IMAGEN`, por defecto gemini-2.5-flash-image; ~$0.04/imagen, `PRECIO_IMAGEN`) dibuja
la escena SIN texto con el icono y capturas como referencia; Pillow pone titular (Luckiest Guy, Apache 2.0, en
`assets/fuentes/`), icono y botón. Solo videos de apps (no `tema:`); ajuste `miniaturas_ia`; sin clave o si falla,
las miniaturas de siempre. Prueba en el servidor: `oficina.py --probar-miniatura`.
**Miguel ya no usa Gemini**: el motor por defecto es `MINIATURA_MOTOR=claude` — Claude (tarea "miniatura_dibujo",
Sonnet con el plan, ~75 s y ~$0.12–0.17 equivalentes por dibujo) escribe la escena en SVG (sin <text>/<image>,
mitad izquierda libre, monedas y billetes obligatorios) y `cairosvg` (libcairo2) la convierte. Probado aquí con
Claude real: se ve muy parecido a sus referencias. Gemini queda como opción (`MINIATURA_MOTOR=gemini`), sin probar.

## 3f. Varios videos a la vez y 📅 agenda (nov 2026)
- **Videos a la vez** (ajuste `videos_a_la_vez`, 3; selector en Bandeja): el piloto arranca hasta N ideas (nunca dos
  de la misma app) y cada 5 min (`_ciclo_deseos`) rellena lugares libres con las mejores ideas pendientes; si no
  hay ideas, prueba la lista de deseos con el cel.
- **📅 Gestor de horarios** (`agentes/agenda.py`): al publicar en público, Carla sube privado con `publishAt` en el
  primer horario libre: ventana 8–21 h (`agenda_inicio`/`agenda_fin`), 3 h entre dos de investigación, 1 h si alguno
  lleva grabación (`prueba.json` existe), nunca dos de la misma app el mismo día, máximo `AGENDA_MAX_DIA` (5) al día
  por la cuota de YouTube (10,000 unidades/día, 1,600 por subida). Se arma con `salida/*/publicado.json`
  (`programado_utc`, `tipo_video`). Lista en Proyectos; "Sacar de la agenda" (`youtube.desprogramar`).
- **📅 Publicar solo** (ajuste `publicar_solo`, casilla en Bandeja con confirmación): al quedar listo, el video pasa
  directo a Carla (público, título 1) sin revisión del jefe. Lo pidió Miguel ("confío en que ya hace buen contenido").
- Ojo: si la app de Google del canal no pasó la auditoría de YouTube, lo programado puede quedarse privado.

## 3g. Edu edita en las compus de la sala (nov 2026)
- Antes solo había un editor: Edu tenía candado de una tarea y el servidor edita uno a la vez (`cola_video`, RAM).
- Ahora `Produccion.editar` llama `agentes/edicion_remota.editar_en_sala`: si la sala tiene compu con tipo "edu",
  hace el plan de efectos en el servidor, junta todo (audios + .palabras.json, imágenes, grabaciones, estilo,
  sfx, plan) en `salida/<id>/remota/envio` (hardlinks; la sala solo lee dentro de salida/) y crea el trabajo "edu".
  La compu (`salaedicion/compu.py:editar_edu`) acomoda los archivos según `manifiesto["mapa"]` y corre
  `python -m agentes.edicion_remota <mesa>` en el clon del repo con `AUTOCANAL_ESTILO` (= `config.ESTILO_DIR`) y
  `AUTOCANAL_SIN_COLA=1`; sube video.mp4; el .srt se hace en el servidor. Si nadie lo agarra en 5 min o falla, el
  servidor edita como siempre. `turnos["editor"]` es un semáforo de 5. Las tarjetas de Proyectos muestran
  "Edu: 🖥️ <compu>: paso · %" o "☁️ Servidor: …"; la pestaña Sala muestra "🎬 Video de YouTube".
- Probado aquí: paquete → runner → video.mp4 (sin la sala real ni Windows).

## 3h. Paola investigadora (nov 2026)
- Pedido tipo "investigar" (o "tema") → `agentes/investigadora.py`: Claude (plan) arma su plan (6–8 búsquedas de
  Google + 2–4 de YouTube, si quiere apps/temas, y `regla_permanente` si dijo "de ahora en adelante…"), investiga
  (Serper/Tavily + tendencias de YouTube) y propone ideas mixtas: APP (se resuelve con `encontrar_app`/`fuera_de_play`)
  o TEMA (`tema:` → pipeline de temas). Solo fuentes que salieron en los resultados (`fuentes` en la tarjeta).
- `oficina.reglas` (📌, persistentes, se pueden quitar en la Bandeja) van en los gustos de cada pedido como
  "REGLA PERMANENTE". Paola dice "Entendí: …". Pedido vacío = apps nuevas de Play Store como antes.
- Probado aquí con Claude real y resultados simulados: buena mezcla de temas y apps, regla bien detectada.
- **Cerebro v2 (nov 2026)**: antes de proponer, Paola ESTUDIA señales recientes en paralelo (`_juntar_senales`):
  Google del último mes (`buscar_web.buscar(reciente="m")`, tbs qdr:m / Tavily time_range), Google Noticias
  (`buscar_web.noticias`), autocompletado de Google y YouTube (`buscar_web.sugerencias`, suggestqueries, gratis),
  videos que pegan (45 días, vistas/día y multiplicador) + comentarios de los 4 que más jalan
  (`tendencias.comentarios`, 1 unidad de cuota). Luego 1 llamada: análisis (qué pega, qué pide la gente, huecos)
  + el doble de candidatas con evidencia etiquetada ([V3], [C2], [A], [N1], [G5]), puntaje 1-10 y nº de señales
  distintas; solo pasan puntaje ≥ 6 y ≥ 2 señales (si ninguna, las 3 mejores). La tarjeta muestra ⭐ puntaje,
  competencia, 📊 evidencia e 📈 inspiración; el análisis sale en el chat de la oficina. Sistema por canal
  (`_sistema()` usa el nombre/nicho del canal del trabajo).
- **🎯 Cazador de apps** (`_cazar_apps`): si el plan dice `una_app_por_video` (ej. "apps de préstamo montadeudas",
  "las peores apps de…"), Paola busca NOMBRES (Google último año con `consultas_nombres` + operadores tipo
  site:condusef.gob.mx / site:reddit.com, y Play Store con `consultas_play`), Claude extrae hasta 12 nombres que
  aparecen tal cual en los datos, y cada app se VERIFICA sin Claude (`_verificar`): Play Store (¿sigue publicada?,
  descargas, estrellas, 100+ reseñas → cuántas con `PALABRAS_QUEJA` y 3 citas textuales), 1 búsqueda de Google
  "<nombre> + amenazas/extorsión/montadeudas/fraude" y autocompletado. Luego 1 llamada califica (gravedad,
  popularidad, puntaje, nivel de evidencia) con títulos según evidencia (fuerte: «X: así te extorsiona»; media:
  «¿X es montadeudas? Esto cuentan N usuarios»; débil: se descarta). Un video por app, ordenadas según `criterio`
  (peores/mejores/populares/nuevas). Si falla, cae a ideas normales. Costo extra: ~6 + 1 por app búsquedas.

## 3i. Varios canales de YouTube (nov 2026)
- El canal "Apps que sí pagan" perdió el acceso por la web pero sigue subiendo y monetizando por API: se queda como
  canal **principal** (youtube_token.json / client_secret.json en autocanal/). Miguel abrió un canal nuevo de
  **alertas de fraude / montadeudas (México)** con cuenta y proyecto de Google nuevos.
- `agentes/canales.py`: registro en `canales.json` (id, nombre, nicho apps|fraudes|libre, blog). Canales extra en
  `canales/<id>/` (token + client_secret; ignorados en git). `claude.contexto.canal` = canal del trabajo en curso.
- Alta: `canal.py autorizar-youtube --canal <id> --nicho fraudes --puerto 8090 --sin-navegador` (toma el nombre
  real del canal de la API). YouTube por canal en `youtube.py` (`_servicio(canal=…)`, nunca pide permiso a media
  publicación); `canal.publicar` usa `origen.json["canal"]`; el blog (WordPress) solo en el principal.
- Pedido de ideas con selector "📺 Para el canal" (Bandeja); ideas y proyectos llevan `canal` (chip rosa).
  Canal de fraudes con casilla vacía → alerta de la semana (investigadora). 📌 reglas por canal ("[id] regla").
  Ideas de la mañana para cada canal conectado. 📘 manual por canal (`estilo/manual_<id>.md`; el de fraudes trae un
  manual de inicio con reglas de datos/fuentes), selector en Estilo. Agenda por canal (cuota propia por proyecto).
  Miniaturas ilustradas solo en el principal. El robot nunca pide préstamos.

## 3j. Chat en la oficina y 📚 lecciones (nov 2026)
- Pestaña Chat con caja para escribir (`/api/chat` → `_atender("oficina", …)`; Paola contesta en el log). Mismo
  cerebro que Telegram/WhatsApp (`chat_jefe.interpretar`, con lista numerada de videos y los canales).
- Acciones nuevas: "corregir" (agente + lección general + canal opcional) → `agentes/lecciones.py`
  (`estilo/lecciones.json`), que se pega en las instrucciones del agente (`lecciones.para(agente)`): Paola
  (buscador/temas/investigadora), Iván (leer web/expediente/temas), Gabi (+ las de Dani: escribe los textos de
  miniatura), Dani (ilustrador), Edu (plan de efectos), Rosa (blog). "cambios" → rehace el video N (en revisión o
  con error) con `accion_proyecto("cambios")`. Lista "📚 Lo que el equipo aprendió" con ✕ en el chat.
- Probado aquí con Claude real: entiende correcciones por agente y por canal, y cambios a un video.

- Chat (nov 2026, después): Miguel quiere resolver TODO desde el chat. Acciones extra: "miniaturas" (Carla pone
  las que faltan en videos ya subidos de todos los canales; `poner_miniaturas_faltantes`), "publicar" (video N o 0 =
  todos en revisión; privacidad en texto, por defecto público con agenda), "reintentar" (N o 0 = todos con error),
  "descartar" (N obligatorio), "piloto" on/off. Paola NO debe prometer acciones que no existen (regla en el prompt).
  El canal viejo no puede verificar teléfono → YouTube rechaza sus miniaturas (403); Cuida Tu Lana ya verificado.

## 4. Pendientes y problemas conocidos
- **✅ RESUELTO (nov 2026)**: plugin 1.3 activo + contraseña de aplicación nueva; `--probar-wordpress` da "FUNCIONA".
  Causas reales: la contraseña de aplicación vieja ya no era válida y otro plugin del blog revisaba al usuario antes
  de tiempo (WordPress lo trataba como visitante); el plugin 1.3 valida con `wp_authenticate_application_password`
  en `rest_api_init`. WP_ESTADO sigue en draft salvo que Miguel lo cambie.
- **(Arreglo, nov 2026, sin tocar .htaccess)**: plugin `autocanal/wordpress/autocanal-conexion.php`; se baja en la
  oficina (Proyectos → «Plugin para el blog») y se sube en wp-admin → Plugins → Añadir nuevo → Subir plugin. `blog.py`
  manda también la cabecera `X-AutoCanal-Auth`, que el plugin pasa a PHP_AUTH_USER/PW. Falta que Miguel lo instale.
- **WordPress da 401 `rest_cannot_create`**: el hosting le quita el encabezado `Authorization` a las peticiones.
  Arreglo: agregar al `.htaccess` del blog
  `SetEnvIf Authorization "(.*)" HTTP_AUTHORIZATION=$1`
  (o `RewriteRule .* - [E=HTTP_AUTHORIZATION:%{HTTP:Authorization}]`). **En pausa**: Miguel no puede entrar al
  administrador de archivos ahorita. Mientras, los videos se publican y el blog queda "pendiente".
  Diagnóstico: `sudo -u canal /opt/canal/autocanal/.venv/bin/python oficina.py --probar-wordpress`.
- Descargar referencias de YouTube con yt-dlp puede fallar desde el VPS ("confirma que no eres un bot"): el sistema
  avisa y se sube el archivo.
- Ideas ofrecidas y no hechas: sección "🎤 Tu forma de hablar" para Gabi (ejemplos de cómo habla Miguel + pasada
  de humor).

## 5. Lo que le gusta / no le gusta a Miguel (aprendido en el camino)
- Que todo sea **automático** y que no se detenga por una sola cosa (ej. que el blog no frene YouTube).
- Ver **qué está haciendo cada agente** en tiempo real (pestaña Equipo, avance del editor en %).
- **Gasto mínimo**: le molestó cuando la investigación costó $0.19; ahora cada video cuesta centavos.
- Que **piense lo que pide**: "hazme un video de Marvel Rivals" debe dar ideas buenas y concretas, no genéricas.
- Visual bonito, agentes que se pueden picar, oficina viva.
- Edición de alto impacto (motion graphics, karaoke), aprender estilos de referencias.

## 6. Siguiente proyecto: oficina para TikTok Shop
Miguel quiere una **segunda oficina, igual de automática, para vender productos de TikTok Shop México como
afiliado/creador**. Lo que ya se sabe y lo que conviene:

- Ya existe una skill suya, **`guion-tiktok-shop`** (en su cuenta de Claude, no en este repo), con las reglas de
  guiones que venden en Shop: estructura de 35–50 s (gancho 0–3 s con capas visual/texto/voz → puente → problema →
  solución/demo antes del segundo 30 → 2–3 beneficios con prueba social real → "pícale al carrito naranja"),
  versión corta de 15–25 s para productos de impulso, formatos (problema→solución, antes/después, reseña,
  unboxing, tutorial, objeción/FAQ, ASMR), **3 ganchos A/B/C con el mismo cuerpo** (advertencia, curiosidad, demo
  muda), cambio de toma cada 1.5–2.5 s, texto en zona segura (no arriba 15 %, abajo 20 %, derecha 15 %), que se
  entienda sin sonido, tono de recomendación a un compa en español mexicano, honesto, precios en pesos, nada de
  promesas médicas ni reseñas inventadas, marcar contenido de marca/afiliado. Entrega: ángulo, 3 ganchos, cuerpo
  en tabla, caption + hashtags, comentario fijado, ID `AAAA-MM-DD_producto_formato`. Registra resultados (vendió /
  no vendió) para aprender. **La oficina debe seguir esas reglas y aprender de lo que vende.**
- **Reutilizar el motor**: misma base de `autocanal` (oficina isométrica, agentes, tareas en paralelo, costos,
  tope diario, Telegram, voz con tiempos por palabra, editor con motion graphics y karaoke, aprendizaje de estilo).
  Hay que agregar video **vertical 1080x1920** (hoy el editor es 1920x1080).
- **Mismo VPS, separado**: otra carpeta (ej. `/opt/tiktok`), otro servicio systemd, otro puerto (ej. 8766) y otro
  sitio en Caddy (ej. `https://tiktok.51-195-201-84.sslip.io`, sslip resuelve subdominios). Su propio `.env`,
  estado y tope de gasto. Ojo con la RAM si las dos oficinas editan video a la vez (que se turnen o cola común).
- Agentes posibles: cazador de productos en tendencia (comisión, precio, ventas, reseñas), guionista de Shop
  (con la skill), director de grabación (lista de tomas para que Miguel grabe con el producto), editor vertical,
  diseñador de portada, analista de resultados (qué vendió → aprende).
- **Publicación**: subir a TikTok por API requiere aprobación de TikTok (Content Posting API con auditoría); al
  inicio lo práctico es dejar el video listo para que Miguel lo suba desde el celular, o como borrador.
- Preguntas para Miguel al arrancar: ¿graba él los productos (manos/cara/voz propia) o todo con voz IA e imágenes?,
  ¿qué nichos/productos?, ¿cuántos videos al día?, ¿cómo ve sus ventas (panel de TikTok Shop / afiliados) para
  que la oficina aprenda qué vende?, ¿repo nuevo o carpeta nueva en este repo?

### 6.1 Lo que Miguel decidió (nov 2026) y avance
- **Él graba, la IA edita**: la oficina le da la lista de tomas, él graba con el cel y sube los clips; el editor
  monta en vertical con subtítulos, efectos y voz. Productos: **los que le mandan las marcas** (marcar contenido de
  marca) + hogar/cocina y tecnología. **Solo cuando él pida** (sin agenda automática). Ventas: las ve en el
  **panel de afiliados** de TikTok Shop → botón "📊 Registrar resultado" donde copia vistas/clics/ventas/comisión.
- **Carpeta nueva en este repo** (`tiktokshop/`, misma rama), reusando el motor de `autocanal/`.
- **Un edificio, dos alas** (una dirección, una contraseña): ala izquierda YouTube, pasillo al centro con el
  despacho del jefe y la sala de juntas, ala derecha TikTok Shop, patio de descanso compartido abajo. Por dentro
  siguen siendo dos oficinas separadas (cada una con su gasto, tope y `.env`); cola común para editar video (RAM).
- **Equipo TikTok** (ids `tt_…`): Toño (cazador de productos), Sofi (guionista de Shop), Diego (director de
  grabación), **Cris (editor vertical, con lentes y copete — Miguel lo pidió así; si cambia de idea: "Cris2k")**, Vale (portadas), Ana (analista).
- Orden de trabajo: 1) edificio en demo ✅ (`oficina/oficina.js`: rejilla 31×15, mamparas de vidrio con puertas,
  botones 🏢 Todo / ▶ YouTube / 🛒 TikTok Shop; si la oficina TikTok está apagada su equipo sale "en obra")
  · 2) ala TikTok con servidor propio ✅ (gancho elegible A/B/C/los 3; Diego filtra tomas por gancho) (`tiktokshop/tienda.py` + `shop.py`; pestaña Shop con "📦 Me llegó un producto";
  Toño ficha con fuentes → Sofi guion 3 ganchos → Diego lista de tomas; `oficina.py` hace de puerta en `/tiktok/api/…`
  hacia `TIENDA_URL` y en `--demo` prende la tienda sola; el edificio consulta su estado cada 2 s)
  Sofi escribe con Opus (tarea `guion_shop`: API `claude-opus-5-5` high ~10-15 ¢; plan `opus`). Reglas en `shop.REGLAS`: escena concreta, detalles, pregunta abierta, reenganche a medio video, lista de frases prohibidas, ejemplos plano→con vida; chat `/api/chat_guion/<id>` y `reglas_guion` recordadas.
  · 3) editor vertical ✅ (Miguel habla en sus clips; sube un clip por toma O el video completo; `tiktokshop/cris.py`:
  Whisper local `faster-whisper` (WHISPER_MODELO, default small) para karaoke de su voz, piezas en orden del guion,
  cortes con acercamiento cada ~2.2 s, texto de Sofi arriba en zona segura, loudnorm, un video por gancho elegido;
  con video completo quita silencios/tomas repetidas y Haiku clasifica trozos; Vale hace portada de un cuadro limpio;
  cola común con Edu en `agentes/cola_video.py` (flock en /opt/canal/.cola_video.lock); sin música: tendencia en TikTok) · 4) registrar resultados y aprender · 5) servidor (puerto 8766,
  Caddy con ruta `/tiktok/` en el mismo sitio; **ojo: `despliegue/caddy.sh` hoy reescribe todo el Caddyfile**).

### 6.2 Sala de edición (tercera oficina) — nov 2026
- Miguel tiene 2 compus Windows (i7 + RTX 3070, Xeon + RTX 5060). `salaedicion/sala.py` (servicio `sala`, 127.0.0.1:8767)
  lleva la cola de trabajos; el edificio la pasa en `/sala/…` (pestaña **Sala**, botón 🎬 Edición, cuarto a la derecha de
  TikTok con las compus dibujadas). Las compus corren `salaedicion/compu.py` (lo instala `windows/INSTALAR_SALA.bat` →
  baja `instalar.ps1` de GitHub raw de esta rama; winget instala Git, Python 3.12 y ffmpeg; arranca sola al prender).
- Alta con código de 6 números (pestaña Sala, 15 min) → la compu guarda su llave en %LOCALAPPDATA%\SalaEdicion;
  entra en `/sala/api/maquina/…` con cabecera X-Compu-Token (sin la contraseña de la oficina). Lo interno (`/interno/…`)
  no se pasa desde internet.
- Cris primero pregunta a la sala; si hay compu prendida, el trabajo va ahí (NVENC + Whisper large-v3-turbo en GPU, si
  falla usa CPU) y Cris "camina" a la sala. Si no hay compu, nadie lo toma en 90 s, o la compu se apaga/falla → edita el
  servidor. Con video completo, la compu pide a Claude por la sala → tienda (`/interno/clasificar`), el gasto queda allá.
- Pendiente: Edu (YouTube) en las compus; pizarrón de muestras de TikTok Shop con días restantes (fecha límite copiada
  del panel de TikTok) + aviso por Telegram cada mañana. No probado en Windows real (aquí no hay Windows).

### 6.3 Publicar en YouTube (nov 2026)
- Bug arreglado: el formulario de TikTok tenía un `<label class="check">` y la revisión de YouTube contaba `.check` →
  el botón Publicar nunca se habilitaba marcando a mano. Ahora se busca `#modal-cuerpo input.check`.
- Casilla "✅ Ya revisé todo" y selector Público / Sin listar / Privado (se recuerda en el navegador; por defecto
  YT_PRIVACIDAD). Tras subir se lee la privacidad real: YouTube deja en privado lo que sube una app de Google sin
  auditar aunque se pida público → se avisa. "Reintentar" tras fallar al publicar vuelve a publicar directo.
- Título propio (nov 2026): en Revisar video hay 4ª opción "✍️ Mi título" (tal cual o "✨ Mejorar con IA" → 3 versiones
  de SU idea con Haiku, accion `mejorar_titulo`). Al publicar se agrega a guion.json `titulos` y se guarda en preferencias.
  "Pedir cambios" rehace guion y video: para el título NO usarlo (a Miguel le molestó que rediseñara todo).

### 6.4 Clips en tu compu + sala visual + menús por ala (nov 2026)
- Los clips ya NO tienen que subirse al servidor (poco espacio): cada compu tiene `Videos\Sala de edicion\<Producto [abcd]>`
  (abcd = final del id; compu.py crea la carpeta de cada producto con tomas listas, lo pide en el latido con
  `con_carpetas`). La compu reporta nombre/duración/miniatura JPG chiquita (`/maquina/carpetas`); la oficina las muestra
  en el producto (sección "🖥️ Tus clips en tu compu") y Miguel asigna cada clip a toma/video completo (o "🪄 Asignar en
  orden de grabación"). `tienda.asignar_local` guarda `p.local`; editar modo "local" manda trabajo `fija`=esa compu,
  `local.producto`; la compu edita con sus archivos y solo sube el video y el cuadro. Sin servidor de respaldo en ese modo
  (espera hasta 10 min a que se prenda la compu). Caché de Whisper en %LOCALAPPDATA%\SalaEdicion\oido.
- compu.py se actualiza solo (git fetch cada 30 min y se reinicia).
- Pestaña Sala rediseñada como monitores (avance, chips GPU/NVENC/oído, carpetas con miniaturas que abren el producto).
- A la derecha solo los menús del ala: YouTube (Bandeja, Proyectos, Estilo, Equipo, Chat), TikTok (Shop, Equipo, Chat),
  Edición (Sala, Equipo); Todo = todos.
- Subir clips con la compu apagada (nov 2026): se sigue pudiendo subir al servidor (📤 Subir / video completo). Botones
  "✂️ Que Cris lo edite ya" (compu si está prendida, si no servidor) y "🖥️ Esperar a mi compu" (`editar_esperar`: fila de
  la sala sin respaldo del servidor, espera hasta 3 días). Los clips subidos se borran solos `CLIPS_DIAS` (3) días después
  de `video_t`, o con "🧹 Borrar mis clips del servidor ya". Shop muestra el espacio libre (aviso si < 3 GB).

### 6.5 Sala de edición con editores propios, proyectos y chat (nov 2026)
- Un editor por compu (se llama como la compu; si está apagada, descansa en el patio). Edu y Cris siguen en el servidor.
- Proyectos (`salaedicion/proyectos.py`, mezclado en Sala): carpeta en la compu (Videos\Sala de edicion\<Nombre>) o clips
  subidos al servidor (`salaedicion/salida/<id>/clips`). Se crean con "➕ Nuevo proyecto", desde el chat general, o
  haciendo una carpeta nueva en la compu (se vuelve proyecto sola). Musica: carpeta `Musica` de la sala en la compu.
- Chat general (router con Haiku) → proyecto; chat de cada proyecto con su encargado (Haiku tarea "edicion" → respuesta +
  plan de edición `editor_libre.PLAN_SCHEMA`). El editor pregunta vertical/horizontal si no se sabe. Correcciones cambian
  solo lo pedido sobre el plan anterior.
- Trabajo tipo "libre" → la compu (`compu.hacer_proyecto`) baja a la carpeta lo subido, `editor_libre.render` (cortes,
  silencios, repetidas, velocidad, acercamientos, color eq, textos, karaoke, música, duración) y sube v{n}.mp4 + cuadro;
  copia en <carpeta>\Ediciones. La sala avisa en el chat con la versión. Gasto de la sala en su propio contador.
- Demo sin Claude: `_router_demo` y `_cerebro_demo`.
- Nov 2026 (2): ventanas de CMD en Windows: compu.py parchea Popen (CREATE_NO_WINDOW + SW_HIDE) y usa el ffmpeg real
  del paquete de winget (el de WinGet\Links abría ventana). Editor de la sala "con ojos y oídos": compu.analizar() por clip
  (frases de Whisper con tiempos, calidad por segundo movido/borroso/oscuro con numpy, tira de 4 cuadros JPG) → la sala la
  manda a Claude con imágenes (visión). Plan nuevo: saltar_malas, estabilizar (deshake), audio_original
  (normal/solo_voz/silenciar), reducir_ruido (afftdn); música con sidechain (baja cuando hablas). La respuesta trae
  "cambios" y "no_puedo"; si la canción no existe, avisa. Modelo propio: tarea "sala" (MODELO_SALA en .env, Haiku medium).
- Nov 2026 (3): proyectos con carpeta propia (`ruta`): al crear se elige de una lista de carpetas que la compu reporta
  (`lugares`: Escritorio, Videos, Descargas, Imágenes, Documentos con conteo de videos) o se pega la ruta; clave de clips
  `proyecto:<id>`; versiones en <ruta>\Ediciones. "Compu desconectada": compu.py ahora manda un pulso aparte cada 10 s,
  revisa carpetas/analiza clips y prepara el oído en hilos aparte, se reinicia al actualizarse con Popen+os._exit (execv
  fallaba con espacios en Windows) y reporta `estado` («Analizando…», «Preparando el oído…») que se ve en el monitor.
- Nov 2026 (4): "📂 Elegir carpeta…": la oficina pide a la compu (`/api/elegir_carpeta` → latido normal, no el pulso →
  `compu.elegir_carpeta`) que abra la ventana de Windows (tkinter askdirectory; respaldo PowerShell FolderBrowserDialog)
  y la ruta vuelve sola. "📤 Subir una carpeta" (webkitdirectory) en la ventana del proyecto. Clips de la ruta: la compu
  manda la lista con miniaturas al momento y analiza después (antes esperaba al oído → no salían). Errores de carpeta se
  ven en el proyecto. Música libre: `salaedicion/musica_libre.py` con Openverse (sin clave, license_type=commercial,
  modification, category=music); Pixabay NO tiene API de música. El editor llena `buscar_musica` (inglés), la sala enseña
  3 opciones en el chat (reproductor + "Usar esta" → "usa la música N"), baja la elegida (opcion:N) y va a la carpeta
  Musica de la compu; créditos CC BY en el proyecto. No probado contra Openverse real (sin red aquí).
- Nov 2026 (5): Miguel NO quiere subir carpetas: quitado "Subir una carpeta" (webkitdirectory). En la ventana del proyecto
  "📂 Usar una carpeta de mi compu" (ventana de Windows en la compu → `/api/proyecto/<id>/carpeta` {compu, ruta}); lo subido
  al servidor de ese proyecto se borra. "☁️ Subir clips al servidor" queda solo para cuando la compu está apagada.
- Nov 2026 (6): a Miguel no le gustaban los videos de la sala ("no entiende de edición"). Cambios: tarea "sala" ahora
  Sonnet 5.5 medium por defecto (~3-5 ¢/mensaje; MODELO_SALA=claude-haiku-5-5 para ahorrar); `proyectos.MANUAL` con
  principios de edición (gancho/desarrollo/cierre, mejores tomas, ritmo, tomas de apoyo, textos cortos, audio,
  transiciones); campo `estructura` antes del plan (se le muestra "Cómo lo armé" en la v1). Plan por pedazo: `texto` +
  `posicion_texto` (se pinta donde quedó ese pedazo tras quitar silencios), `encima` (b-roll: se ve otro clip y se oye
  el del pedazo) y `transicion` corte/fundido.
- Nov 2026 (7): "siguen mediocres" → Miguel eligió: Claude Code en su compu (plan Pro) como cerebro + manual completo +
  herramientas con oficio + que revise antes de mandar (NO "aprenda mi estilo").
  - `salaedicion/manual_edicion.py`: MANUAL largo (estructura, recetas por tipo de video, tomas, ritmo con números,
    textos, audio, movimiento, correcciones, checklist "antes de entregar") y AYUDA. Lo usan servidor y compus.
  - Herramientas nuevas en el plan (`editor_libre`): quitar_muletillas (corta "eh/mmm/este…" palabra por palabra),
    zoom_suave (zoompan lento que entra/sale), efectos_sonido (whoosh en fundidos, pop al salir un texto; generados con
    lavfi, sin archivos), al_ritmo (tomas sin voz duran golpes enteros de la música; `_pulso` detecta el BPM).
    `normalizar_plan` limpia planes que no vienen de la API. `render(..., info={})` deja lo que se oye y los pedazos.
  - Cerebro: la compu detecta Claude Code (`claude_code()`, sesión por ~/.claude/.credentials.json u oauthAccount en
    ~/.claude.json) y reporta `claude_code` ("listo"/"sin_sesion") + tipo "pensar". `proyectos._pensar` crea un trabajo
    "pensar" (hojas de cuadros como entradas, instrucciones.md + schema) → `compu.pensar` corre
    `claude -p … --output-format json --permission-mode acceptEdits --allowedTools Read,Write,Edit,Glob` en una carpeta
    temporal y devuelve respuesta.json. Si no hay compu con Claude Code, está ocupada >90 s o falla (sin sesión, límite
    del plan) → API (Sonnet) con nota en el chat. SALA_MODELO_CLAUDE (variable de entorno en la compu) elige modelo.
  - Revisión: tras renderizar, si la compu tiene Claude Code, `compu.revisar` saca ~12 cuadros del borrador + lo que se
    oye + contexto del chat, Claude Code revisa con el checklist y, si hay problemas, re-renderiza una vez con el plan
    corregido; el chat dice "🔍 Antes de mandártelo lo revisé y corregí: …". Sin Claude Code no se revisa (sería con costo).
  - Instalador: instala Claude Code (`irm https://claude.ai/install.ps1 | iex`) y abre la ventana para iniciar sesión una
    vez. En la oficina, la tarjeta de la compu muestra "🧠 Claude Code" o "🧠 sin sesión".
  - Probado aquí con Claude Code real: pensar (45 s) y revisar (≈50 s) funcionan y corrigen cosas reales.
- Nov 2026 (8): "🎵 Subir música o audio" en la ventana del proyecto (también con el video ya hecho): `/api/subir` acepta
  audio (mp3/m4a/wav/aac/ogg/flac) → `salida/<id>/musica`; el editor avisa en el chat; `musica(p)` junta lo subido + la
  carpeta Musica de la compu; al editar, la canción subida viaja como entrada a la carpeta Musica de la compu.
- Nov 2026 (9): "la sala sigue mala, quiero que Claude edite localmente y motion graphics" → **Editor IA**: Claude Code
  edita con las manos libres en la carpeta del proyecto en su compu. Modos: desde la oficina (chat del proyecto) y
  directo en la compu («Abrir editor IA.bat» en la carpeta del proyecto); comparten memoria (`--continue` en
  `<proyecto>/_editor` + `_editor/notas.md`). Motion: títulos/textos animados, producto (precio, etiquetas, flecha,
  círculo, link, contador, emoji) y subtítulos con estilo (pop/karaoke/caja).
  - `salaedicion/motion/`: proyecto Remotion 4.0.537 (composición "Video" por props.json, video base con
    OffthreadVideo + capas). La compu lo instala sola (`compu.preparar_motion`: `npm ci`, marca con firma del lock);
    necesita Node.js (el instalador lo pone con winget OpenJS.NodeJS.LTS). Remotion es gratis para personas/equipos ≤3.
  - `salaedicion/herramientas.py` (lo usa Claude Code con Bash): ficha, cuadros, transcribir, armar (motor
    editor_libre), motion, revisar, codificar. Trabaja en `SALA_EDITOR_DIR` (= _editor).
  - `salaedicion/editor_ia.py`: genera `_editor/CLAUDE.md` (guía + herramientas + motion + MANUAL), el .bat, y
    `correr()` (claude -p --continue, stream-json → progreso al monitor, Bash/Read/Write/Edit/Glob/Grep, 60 min).
  - Trabajo "claude_libre" (compu `editar_libre`): baja clips/música subidos, corre Claude Code, lee
    `_editor/resultado.json` {respuesta, video, cambios}, sube vN.mp4. Sala: `_compu_editor_ia` (compu del proyecto
    con claude_libre en tipos) → `_editar_con_ia`; `_termino_editor_ia` pone la respuesta y la versión en el chat.
    Si la compu no tiene Claude Code, sigue el flujo anterior (plan + editor_libre).
  - Probado aquí con Claude Code real: v1 de TikTok Shop con título, precio tachado y link en ~4.5 min.
- Nov 2026 (10): "que los editores aprendan de mis correcciones y mi estilo, sin comerme mi uso de Claude". NO se
  entrena el modelo (no se puede con Claude); aprenden con un **cuaderno de estilo** compartido
  (`salaedicion/aprendizaje.py`, mixin de Sala, se guarda en sala_estado.json → "estilo"):
  - reglas (las escriben los editores en `aprendido` cuando una corrección dice algo de su gusto general; si se
    repite, sube ×N; >40 reglas → Haiku las resume, tarea "sala_aprender"), notas de Miguel (mandan), calificaciones
    👍/👎 por versión con comentario (el siguiente Editor IA las convierte en reglas), recetas (plan.json+props.json
    de versiones con 👍; el editor arranca de una receta del mismo tipo).
  - Viaja con cada trabajo: Editor IA → `_editor/CLAUDE.md` (secciones estilo, recetas, "Ahorra el uso", "Aprende")
    + `_editor/recetas/*.json` + `_editor/estilo.md`; editor anterior (API) → en el system prompt + campo `aprendido`.
  - Ahorro: correcciones con `--model haiku` (SALA_MODELO_CORRECCION; si falla, reintenta con sonnet), lo nuevo con
    sonnet (SALA_MODELO_CLAUDE); "a fondo"/"desde cero"/"rehaz" fuerza el modo completo. CLAUDE.md prohíbe repetir
    ficha/hojas en correcciones. El chat muestra modelo, minutos, pasos y "equivale a X ¢ de API".
  - Oficina: 👍/👎 debajo de cada versión (pide el porqué con prompt) y «📒 Estilo» en Proyectos (notas, reglas con
    ✕, agregar regla, recetas, calificaciones). Rutas: GET/POST /api/estilo, POST /api/proyecto/<id>/calificar.
- Nov 2026 (11): el servidor se actualiza solo. `autocanal/despliegue/autoactualizar.sh` (timer systemd
  `autocanal-actualizar`, cada minuto; antes 10 min): git fetch; si hay commits nuevos en la rama y no hay video en curso
  (flock de .cola_video.lock) ni trabajos asignado/trabajando en la sala (127.0.0.1:8767/api/estado), corre
  actualizar.sh; si lleva >3 h esperando, actualiza igual. Log: /var/log/autocanal-actualizar.log; marca
  /opt/canal/.ultima_actualizacion. Lo prende actualizar.sh la primera vez y instalar.sh en servidores nuevos.
  Apagar: `sudo bash autoactualizar.sh --apagar`.
- Nov 2026 (12): Miguel pidió apagar las ideas/guiones automáticos de la mañana. `oficina.ideas_auto` (en
  oficina_estado.json, apagado por defecto) manda sobre IDEAS_HORA; casilla «☀️ Que Paola busque ideas sola cada
  mañana» bajo "Pídele ideas a Paola" (POST /api/ideas/auto {activo}). Sin IDEAS_HORA en .env la casilla sale gris.

## 3k. Resultados, variedad y empaque (nov 2026)
- **📊 Resultados** (`agentes/analitica.py`): permiso nuevo `yt-analytics.readonly` (en `youtube.SCOPES_NUEVOS`;
  los tokens viejos se cargan con SUS scopes para no romper el refresh). Alta por canal:
  `canal.py autorizar-youtube --canal <id> --de-nuevo --puerto 8090 --sin-navegador` + habilitar «YouTube Analytics
  API» en el proyecto de Google de ese canal. `youtube.tiene_analitica(canal)`.
  Cada 6 h (`Oficina._ciclo_resultados`, botón «Revisar ahora» → `/api/resultados/actualizar`): `actualizar` (vistas,
  minutos, duración media, % visto, subs, likes, comentarios, impresiones + CTR si la API los da, curva de retención →
  `_caidas`: retención a 30 s y 3 caídas mapeadas a escenas del guion por palabras), `aprender` (≥3 videos de 2+ días,
  1 vez al día: reglas para productora/guionista/disenadora/editor → se pegan en los prompts vía `lecciones.para`),
  `rescatar` (🛟 2-14 días, ≥300 impresiones, CTR < 70% de la mediana del canal → título/miniatura del paquete 2, una
  vez; ajuste `rescate_empaque`). Datos en `estilo/analitica.json` (demo: `analitica_demo.json`, números falsos).
  Pestaña 📊 Resultados (tarjetas por video, aprendizajes, pasos de permiso si falta).
- **🎲 Variedad** (`agentes/variedad.py`): Miguel quiere VOLUMEN; para no caer en «contenido repetitivo» (política
  jul 2026) cada guion recibe: tipo de gancho que toca (el menos usado; `tipo_gancho` en el schema), cómo empezaron
  los últimos 8 videos, orden de bloques reciente, muletillas (4-gramas en ≥3 guiones) prohibidas y "aporta algo propio".
  El system del guion usa el nombre del canal del video.
- **🎁 Empaque** (`agentes/empaque.py`): GUIA investigada (packaging-first, título+miniatura como unidad, ≤55 car.,
  específico, curiosidad cumplida rápido porque A/B de YouTube gana por tiempo visto, caras con emoción, 2-4 palabras,
  paquetes MUY distintos) + tips por nicho. Va en el system de Gabi y de Paola. Tras el guion, `empacar` (tarea guion):
  10 conceptos → 3 paquetes (título, texto/escena de miniatura, ángulo, puntaje) usando títulos que más/menos jalaron
  del canal y títulos recientes; reordena `titulos`/`textos_miniatura`. `ligar_miniaturas` une cada paquete con su
  miniatura y pone primero el de la miniatura elegida. Revisión: bloque 🎁 Empaque + guía de Prueba A/B en Studio
  (la API no crea pruebas A/B). Paola propone `miniatura_idea` con cada idea (tarjeta 🖼️) y va en las notas del proyecto.
- **🪪 Identidad del canal** (`agentes/identidad.py`, Estilo → sección por canal del selector del manual): genera
  portada 2560×1440 (todo en la zona segura 1546×423; mascota del canal), foto de perfil 800×800 y descripción (fija
  y revisada para «fraudes»; con Claude para los demás). «Poner en YouTube» = `channelBanners.insert` +
  `channels.update(brandingSettings)` conservando keywords/idioma/país/tráiler. La foto de perfil NO se puede por API:
  se baja y se sube en Studio. Archivos en `estilo/identidad_<canal>/`. Rutas GET/POST `/api/identidad`.
- **🎬 Analizar videos desde el chat** (`agentes/analizar_video.py`): si el mensaje del jefe (oficina, Telegram o
  WhatsApp) trae un enlace de video (YouTube, TikTok, IG, FB, X, Vimeo…; `es_video`), `Oficina._atender` lo manda a
  `_analizar_video` (tarea "analisis", hasta 3 enlaces; el resto del mensaje es la pregunta). Baja hasta 30 min a
  ≤480p con yt-dlp + subtítulos (es/en, auto) + miniatura; transcripción = subtítulos (`_vtt`, sin repeticiones) o
  Whisper local (`faster-whisper`, instalado opcional en actualizar.sh; modelo `WHISPER_MODELO`, "small"); 16 cuadros
  + miniatura a Claude (tarea estilo): resumen, estructura con tiempos, gancho, por qué funciona, visual, empaque,
  qué copiar para el canal y respuesta a la pregunta. Transcripción completa en `estilo/analisis/*.txt` (enlace
  📄 en el chat). Aquí no se pudo probar con YouTube real (red bloqueada); probado con video y subtítulos locales.
  YouTube frena las descargas desde el servidor («not a bot»): NO se le da la vuelta (se intentó bajar en las compus
  de la sala y se descartó por ir contra el bloqueo de YouTube). Con enlace de YouTube bloqueado → `_sin_video`: API
  oficial (título, descripción/capítulos, números, miniatura, comentarios). Análisis completo: 📎 en el chat sube
  el archivo (`/api/chat/video` → `entrada/_analizar/`, se borra al terminar) → `analizar(archivo=…)`.

## 3l. Claude edita los videos de YouTube en la pc de Miguel (nov 2026)
- Miguel sentía los videos "básicos y aburridos" (plantilla ffmpeg de Edu). Nuevo trabajo de sala **`edu_ia`**:
  `edicion_remota.editar_en_sala` lo usa si el ajuste `editor_claude` (Estilo, prendido por defecto) y hay compu con
  Claude Code + Remotion listos (`compu.py` anuncia `edu_ia`); si no, `edu` (plantilla) como siempre.
- Kit Remotion `salaedicion/motion/src/Edu.tsx` (composición "Edu", 1920x1080): escenas que duran lo que su audio
  (la voz nunca se desfasa) + fondo (imagen con movimiento/contener/desenfocar, video, degradado) + capas: texto
  cinético (pop/golpe/maquina), titulo_seccion, dato (contador), celular, chat WhatsApp, resena, lista, comparativa,
  alerta, sello, imagen, mascota (con globo), emoji, flecha, circulo, cintillo; efectos zoom_golpe, sacudida,
  destello; transiciones; sfx por escena; subtítulos pop/karaoke/caja; música; barra. Probado aquí con render real.
- `salaedicion/editor_youtube.py`: arma `materiales.md` (duración exacta por escena, lo que se dice, sugerencias del
  guion, imágenes, clips, mascota, sfx, datos del expediente, momentos de la prueba) y `edu.json` borrador; escribe
  CLAUDE.md (dirección: gancho, algo cambia cada 2-4 s, lo que se dice se ve, nada inventado + manual/lecciones del
  canal) y corre Claude Code (`editor_ia.correr`, 90 min). Claude renderiza con `herramientas.py edu edu.json
  SALIDA [DESDE HASTA]` y revisa. Si `video_final.mp4` falta o no dura lo de la narración → plantilla en la misma compu.
- El servidor manda además: todas las caras de la mascota (`mascota/*.png`), `canal_nombre`, `acento`, `direccion`,
  `datos` y `prueba.momentos`.
- **📱 Formato 100% grabación (Apps que sí pagan)**: ajuste `solo_grabacion` (prendido). `Produccion.solo_grabacion()`
  = video de app + canal principal (+ no demo: `AUTOCANAL_DEMO`). Fuerza la prueba del robot; si no hay grabación →
  error claro ("revisa el cel / sube tu grabación"). Guion con `guionista.SOLO_GRABACION` (todas las escenas
  "grabacion", en orden, narración en 1a persona y presente, gancho con el momento más fuerte, minutos ≈ largo de la
  grabación, 3-8). Edición: `SOLO_GRABACION_EDICION` al inicio de la dirección del editor IA (fondo video
  `ajuste: contener` = grabación completa al centro sobre su versión desenfocada; capas solo a los lados). Música:
  si no hay `estilo/musica.mp3`, `_musica_libre` baja una pista CC0/dominio público de Openverse a `salida/<id>/musica.mp3`
  (el editor y el paquete de la sala la usan).
- **📱 Robot paso a paso (nov 2026)**: en la pc de Miguel el robot con Claude Code no movía el cel (el `./cel` corría
  con pythonw = sin salida, a ciegas; además stdin abierto y tubos sin leer podían trabarlo). Arreglado eso, y además
  el robot ahora corre por defecto **sin Claude Code**: `robot_cel._bucle` (la compu) toma pantalla + lista de
  elementos (cel.py), manda foto JPG + historial a `sala /robot/<tid>` → la sala la reenvía al `clasificar` del trabajo
  = `oficina /interno/robot/<app>` (solo local, sin X-Forwarded-For) → `agentes/robot_cerebro.decidir` (tarea
  "robot": Sonnet por suscripción, Haiku por API) regresa UNA acción (tocar n | x y, tocar_texto, escribir, deslizar,
  atras, inicio, esperar, tienda, buscar_tienda, abrir, anuncio, nota, guardar_deseo, terminar) que se ejecuta con
  `cel.main()`. `ROBOT_MODO=claude_code` vuelve al modo anterior. Si el robot no hizo nada útil → error con motivo
  (`prueba.ULTIMO_ERROR` llega al mensaje del proyecto) y NO se entrega grabación vacía. Piloto no arranca videos de
  apps del canal principal sin cel listo.
- **Carril del cel**: la compu anuncia `libre_cel` en sus latidos; la sala asigna `probar_app` en `c["trabajo_cel"]`
  (aparte de `c["trabajo"]`), y la compu lo corre en otro hilo (`atender_cel`), así edita mientras el robot graba.
  Compus viejas (sin `libre_cel`) siguen con un solo carril. `probar_app` ya no exige Claude Code en la compu.
- **Robot más humano**: `robot_cerebro` regresa `luego` (hasta 4 acciones encadenadas sin nueva foto) y recibe
  `misma_pantalla` (segundos sin cambio, por huella en grises). Reglas: videos máx. ~15 s y deslizar (copyright),
  juegos se juegan de verdad, no quedarse parado >20 s, explorar secciones clave.
- **🔁 Cadena de anuncios**: `_ciclo_deseos` (cada 2 min, piloto prendido) ya no espera a que se acaben las ideas:
  en cuanto el cel queda libre (`_cel_ocupado`: ningún video de app del principal en "investigar") y hay lugar
  (`en_produccion < a_la_vez + 2`), prueba la siguiente app de ⭐ deseos (primero las que tienen paquete), hasta
  `deseos_por_dia` (ajuste, 6 por defecto, selector en la Bandeja; `DESEOS_POR_DIA` en .env manda).
- **⏳ Límite de subidas de YouTube** (`uploadLimitExceeded`, tope diario por canal; se libera solo ~24 h): `_publicar`
  ya no lo marca como error: `_esperar_cupo` deja el video en "revision" con `p["cupo"]` (reintento) y
  `cupo_lleno[canal]` = ahora + 3 h (no se intentan más subidas a ese canal). `_reintentar_cupo` (cada 10 min en
  `_agenda`) prueba UN video por canal; si entra, los demás de la fila siguen enseguida. Un solo aviso al jefe.
- **🖥️ Varias ediciones a la vez por compu**: la compu manda `capacidad` (auto: 3 con NVENC, 2 con ≥12 hilos, 1; o
  `SALA_A_LA_VEZ`) y `libres`; la sala le asigna varios trabajos en `c["activos"]` y responde `trabajos` (lista); la
  compu corre cada uno en su hilo (`arrancar`). Sala/compu viejas siguen con un trabajo. El servidor ya no se lleva
  un video en fila mientras haya una compu prendida para ese tipo (`compus_libres(tipo)`); solo si no hay ninguna
  por 3 min. Chip «⚡ N a la vez» en Sala.

## 3m. 🌮 Tampiqueando (foodie de Tampico, nov 2026)
- Miguel quiere hacer crecer «Tampiqueando» (comida en Tampico/Madero/Altamira) en Facebook, Instagram y TikTok;
  eligió **envío automático** a negocios y **publicación automática**. Vive dentro de la oficina principal:
  `agentes/tampico.py` (datos en `estilo/tampico.json`, medios en `estilo/tampico_medios/`), pestaña «🌮 Tampico».
- Lupita: `buscar_negocios` (Serper /places, sin repetir por cid o nombre+dirección; WhatsApp MX 52+10). Toño:
  `enviar_pendientes` (cada 15 min, `_ciclo_tampico`; plantilla `TAMPICO_WA_PLANTILLA` con {{1}}=negocio, tope
  diario, lun-sáb 10-19 h) y `respuesta_negocio` (WhatsApp de un número que no es el jefe → si es de un negocio,
  Claude responde dentro de la ventana de 24 h sin prometer más que `ajustes.propuesta`; «no gracias» = baja; aviso al
  jefe). Fer: `plan_visita` (formato, gancho, guion, tomas por equipo, preguntas, textos por red) + proyecto en la
  sala con el guion. Dron: `planear_dron` (lugares de resultados de Google, sin repetir, precauciones AFAC).
  `proponer_formatos` (qué hacen los foodies locales → 5 formatos, uno elegido). `ideas_remarketing`.
  Publicar: Facebook (/videos o /photos) e Instagram (Reels vía `video_url` pública `/publico/tampico/<token>/…`,
  3 días) con `TAMPICO_FB_PAGINA`, `TAMPICO_FB_TOKEN`, `TAMPICO_IG_ID`; TikTok = descargar. Guía:
  `despliegue/GUIA_TAMPIQUEANDO.md`. Demo con `AUTOCANAL_DEMO` (negocios de ejemplo).
- **Sala visual de Tampiqueando** (oficina.js): `COLS` 38→48, ala nueva desde `ALA_TAMP = 38` (mampara en x=38): piso de
  barro con mosaico, muro amarillo/turquesa, papel picado, letrero «TAMPIQUEANDO», cuadro de jaiba, mapa con pines,
  tele con negocios por estado (`estado.tampico`), mesa de platillos (jaiba, tacos, salsas con vapor), dron que vuela
  cuando Paco trabaja, palmeras; entrada al patio en x=42-43. Equipo `tp_*` (Lupita negocios, Chuy WhatsApp, Fer
  producción, Paco dron, Mar redes; Chuy = el antes llamado Toño de tampico.py). Estado desde `estado.tampico_agentes`
  (oficina `_tamp`, marcado por `tampico_accion`). Botón de ala «🌮 Tampiqueando» (pestañas tampico, equipo, chat).
- **🔑 SSH desde las compus de Miguel**: llaves PÚBLICAS en `autocanal/despliegue/llaves_ssh/*.pub` (sin nombre de
  usuario/compu); `actualizar.sh` (root) las agrega a `~ubuntu/.ssh/authorized_keys` sin duplicar. Trabajo de sala
  fijo `probar_ssh` (la compu corre solo `ssh -o BatchMode=yes ubuntu@HOST echo ENTRE_OK`); botón «🔑 Probar SSH»
  en Sala → `/api/sala/probar_ssh` (host: `SSH_HOST` o el de `OFICINA_URL` sslip). La sala acepta hasta 12 tipos.
