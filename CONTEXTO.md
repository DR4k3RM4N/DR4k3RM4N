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
  `--configurar-telegram`, `--configurar-whatsapp`, `--probar-whatsapp`, `--probar-wordpress`.
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
