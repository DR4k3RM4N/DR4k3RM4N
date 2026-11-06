# AutoCanal — de la idea al video publicado

Automatiza el canal de **apps que prometen pagar dinero**: encuentra la app, la investiga, escribe
el guion, la narra, edita el video, hace la miniatura, escribe la entrada del blog y publica en
WordPress y YouTube.

```
 ┌──────────┐   ┌─────────────┐   ┌──────────┐   ┌──────┐   ┌────────┐   ┌───────────┐
 │ 1 Ideas  │──▶│ 2 Investiga │──▶│ 3 Guion  │──▶│4 Voz │──▶│5 Video │──▶│ 6 Miniat. │
 │PlayStore │   │ PlayStore + │   │ escenas, │   │ Edge │   │ ffmpeg │   │  Pillow   │
 │ + Claude │   │ reseñas +   │   │ títulos, │   │ o    │   │ zoom,  │   └─────┬─────┘
 └──────────┘   │ web + Claude│   │ descrip. │   │Eleven│   │ subs,  │         │
                └─────────────┘   └──────────┘   │ Labs │   │ música │         ▼
                                                 └──────┘   └────────┘   ┌───────────┐
                 ┌────────────────────────── TÚ REVISAS ◀────────────────│ 7 Blog    │
                 ▼                            REVISAR.md                 │ Claude    │
          ┌─────────────┐   ┌──────────────┐   ┌──────────────────┐      └───────────┘
          │ WordPress   │──▶│ YouTube      │──▶│ video incrustado │
          │ destacada + │   │ video+minia. │   │ en el blog       │
          │ capturas    │   │ link al blog │   └──────────────────┘
          └─────────────┘   └──────────────┘
```

Cada "agente" es un archivo en `agentes/`:

| Agente | Archivo | Qué hace |
|---|---|---|
| Buscador | `buscador.py` | Busca en Play Store ("ganar dinero", "encuestas pagadas"…) y Claude elige las que más conviene investigar. Lleva un historial para no repetir. |
| Investigador | `investigador.py` | Baja ficha, icono, portada, capturas y reseñas. Claude busca en internet (Reddit, Trustpilot, noticias) y arma un **expediente de evidencia** con veredicto y fuentes. |
| Guionista | `guionista.py` | Guion por escenas con tu estilo, 3 títulos, descripción, etiquetas y texto de miniatura. |
| Voz | `voz.py` | Narra cada escena. Gratis con Edge TTS o con **tu voz clonada** en ElevenLabs. |
| Editor | `editor.py` + `efectos.py` + `graficos.py` | Tarjetas (título, captura, reseña, dato, veredicto), zoom, tus grabaciones, motion graphics escena por escena (contadores, textos que saltan, sellos, cintillos, zoom de golpe, sacudidas, destellos), subtítulos karaoke y música. |
| Blog | `blog.py` | Entrada SEO, sube capturas dentro del texto, pone la imagen destacada de Play Store y deja un hueco para el video. |
| YouTube | `youtube.py` | Sube el video, la miniatura y los metadatos; enlaza el blog. |

## 🏢 La oficina de agentes (visual)

Tu equipo trabajando en una oficina pixel art que ves en el navegador. Cada agente tiene su
escritorio, camina a entregarle el trabajo al siguiente, y **Paola, la productora, te trae ideas
para que opines y des el visto bueno**.

```bash
python oficina.py --demo
```

`--demo` simula Claude, Play Store y la publicación (gratis, para conocerla; el video sí se edita de
verdad). Sin `--demo` usa todo lo real. Se abre en http://localhost:8765.

| Agente | Rol | Qué hace en la oficina |
|---|---|---|
| Paola | Productora | Busca apps, **te pregunta qué opinas**, aprende de tus respuestas y coordina al equipo |
| Iván | Investigador | Reseñas, internet y expediente de evidencia |
| Gabi | Guionista | Guion, títulos y texto de miniatura (con tus notas) |
| Leo | Locutor | Narración (se prende la luz "al aire") |
| Dani | Diseñadora | Miniatura |
| Edu | Editor | Video |
| Rosa | Redactora SEO | Entrada del blog |
| Carla | Community manager | Publica en WordPress y YouTube |
| Tú | Jefe | Apruebas ideas y das el visto bueno final |

Cómo trabajas con ellos:

1. **Pide ideas** en la bandeja (puedes darle una dirección: "apps de encuestas").
2. Paola camina a tu escritorio y te deja las ideas. A cada una le puedes dar **👍 Hazlo**,
   **💬 Opinar** o **👎 No** (con motivo). Lo que opinas se guarda en "Lo que Paola aprendió de ti"
   y lo usa en las siguientes búsquedas; tus notas también le llegan a Gabi para el guion.
3. Al aprobar, el proyecto pasa de escritorio en escritorio. Lo sigues en **Proyectos** y en **Chat**.
4. Cuando el video está listo, Paola te avisa. En **Revisar video** ves el video, la miniatura, el
   borrador del blog, la evidencia y los títulos. Marcas la lista de comprobación y eliges:
   **Publicar**, **Pedir cambios** (Gabi rehace el guion con tu nota y el resto del equipo vuelve a
   trabajar) o **Descartar**.

**Trabajan en paralelo.** Cada etapa arranca en cuanto tiene lo que necesita:

```
Investigación ──┬──▶ Guion ──┬──▶ Voz ──▶ Video
                │            └──▶ Miniatura
                └──▶ Blog
```

Rosa escribe el blog mientras Gabi hace el guion; Leo y Dani arrancan juntos con el guion. Si
apruebas varias ideas, cada agente atiende una tarea a la vez y las demás quedan **en fila**.

**Pestaña Equipo:** pícale a cualquier agente (en la oficina o en la lista) para ver qué está
haciendo ahora, cuánto lleva, qué tiene en fila (y qué está esperando) y lo que ya terminó.
Sobre cada agente ves un ícono de estado (🔎 trabajando, ⏳ en fila, ☕ en el café, 💤 libre) y una
barrita de avance aproximado.

### Tu estilo (pestaña Estilo)

Desde la oficina, sin terminal:

- **Miniaturas (Dani):** sube de 3 a 10 miniaturas que te gusten, tu cara (PNG sin fondo) y tu
  tipografía. Dani estudia el estilo (fondo, colores, posición del texto, flechas, marcos) y cada
  video sale con **3 opciones**; elige la más parecida a tus referencias y tú la cambias en la revisión.
- **Edición (Edu):** pega el **enlace** de un video (YouTube, TikTok…) o súbelo, con la edición que te gusta, y Edu lo estudia: mide
  su ritmo (cortes por minuto) y revisa cuadros con visión (subtítulos, colores, zoom, transiciones) para
  ajustar todo solo. También a mano: subtítulos grandes o clásicos, palabras por línea, mayúsculas,
  posición, transiciones, movimiento (suave/medio/fuerte), golpes de zoom al ritmo, barra de progreso,
  sonido en los cambios de escena, música, intro y outro.
  En cada video Edu lee el guion y arma un **plan de motion graphics** escena por escena (qué efecto y en
  qué palabra exacta, con su sonido); intensidad: sin efectos / pocos / normal / muchos. Los subtítulos son
  **karaoke**: la palabra que se dice se ilumina, con los tiempos reales de la voz.
- **Blog (Rosa):** pega enlaces a tus mejores entradas; Rosa aprende cómo escribes. Cada post usa
  investigación SEO de Google (lo que pregunta la gente, búsquedas relacionadas, competencia), elige
  palabra clave y secundarias, y enlaza 2–3 de tus otras entradas.
- **YouTube (Carla):** al darle Publicar sube el video con título, descripción, etiquetas y miniatura.
  Sin WordPress sube solo a YouTube. Conexión paso a paso: [`despliegue/GUIA_YOUTUBE.md`](despliegue/GUIA_YOUTUBE.md).

### Por Telegram o WhatsApp

Tu equipo te avisa por chat (ideas, videos listos, problemas) y tú contestas como en un chat:
*sí 1*, *no 2 ya la hicimos*, *busca apps de encuestas*, *¿cómo van?*. Los comandos simples se
entienden gratis; lo demás lo interpreta Haiku (fracción de centavo).

- **Telegram (gratis, recomendado):** ideas con botones ✅/❌ y teclado fijo. Se conecta con
  `python oficina.py --configurar-telegram` (ver la sección 5 de
  [`despliegue/GUIA_SERVIDOR.md`](despliegue/GUIA_SERVIDOR.md)).
- **WhatsApp (API oficial de Meta, cobra por mensaje):** [`despliegue/GUIA_WHATSAPP.md`](despliegue/GUIA_WHATSAPP.md).

### En un servidor (siempre activa)

Para tenerla las 24 horas en un VPS, con contraseña, HTTPS, ideas automáticas cada mañana y avisos
por Telegram, sigue [`despliegue/GUIA_SERVIDOR.md`](despliegue/GUIA_SERVIDOR.md). Se instala con un
solo comando (`despliegue/instalar.sh`).

## Instalación (una vez)

1. Instala Python 3.11+ y **ffmpeg** (Windows: `winget install ffmpeg`; Mac: `brew install ffmpeg`).
2. En esta carpeta:

```bash
pip install -r requirements.txt
```

```bash
cp .env.example .env
```

3. Llena `.env`:
   - `ANTHROPIC_API_KEY`: de console.anthropic.com.
   - WordPress: en tu blog ve a **Usuarios → Perfil → Contraseñas de aplicación**, crea una y pégala en `WP_APP_PASSWORD`.
   - YouTube: en Google Cloud Console activa **YouTube Data API v3**, crea credenciales OAuth tipo
     **App de escritorio**, descarga el JSON como `client_secret.json` en esta carpeta. La primera vez que
     publiques se abrirá el navegador para autorizar tu canal.
4. Prueba que la edición funciona (no usa APIs):

```bash
python canal.py demo
```

## Uso diario

```bash
python canal.py ideas
```

```bash
python canal.py crear com.nombre.delaapp
```

Esto deja todo en `salida/com.nombre.delaapp/`: `video.mp4`, `miniatura.jpg`, `blog_preview.html` y
**`REVISAR.md`** (veredicto, evidencia con fuentes, lo que debes comprobar tú y el guion).

```bash
python canal.py publicar com.nombre.delaapp
```

Sube el blog (como borrador si `WP_ESTADO=draft`), sube el video a YouTube (privado si
`YT_PRIVACIDAD=private`) con el enlace al blog, e incrusta el video en la entrada.

### Tus grabaciones del celular (recomendado)

Pon tus grabaciones de pantalla en `entrada/com.nombre.delaapp/` (`1.mp4`, `2.mp4`…) **antes** de
`crear`. El guionista las usa como escenas y el editor las pone sobre fondo desenfocado con tu narración.
Es lo que más diferencia tu video de uno 100% automático (ver advertencias abajo).

### Personalizar

- `assets/cara.png`: tu cara recortada (PNG transparente) → aparece en la miniatura.
- `assets/musica.mp3`: música de fondo sin copyright → se mezcla bajita.
- `assets/fuente_negrita.ttf` / `fuente.ttf`: tu tipografía.
- `CANAL_ESTILO` en `.env`: cómo hablas; el guionista lo imita.
- `--minutos 8`, `--sin-web` (más barato), `--voz elevenlabs`.
- ¿No te gustó el guion? `python canal.py crear APP --desde guion` rehace guion, voz, video y blog
  sin volver a investigar.

### Todo en automático

```bash
python canal.py automatico --n 2
```

Busca ideas y crea los 2 mejores videos (sin publicar). Puedes programarlo con el Programador de
tareas de Windows o `cron` para que cada mañana tengas videos listos para revisar.
Existe `--publicar` para saltarte la revisión, pero no lo recomiendo (ver abajo).

## Costo por video

Cada agente usa el modelo más barato que da buen resultado para su trabajo:

| Agente | Modelo | Por qué |
|---|---|---|
| Paola (ideas) | Haiku 5.5 | Elegir apps de una lista es sencillo |
| Iván (investigación) | Haiku 5.5 | Busca con Serper/Tavily y Haiku lee y arma el expediente |
| Gabi (guion) | Haiku 5.5 | Si el guion sale flojo, súbelo a Sonnet: `MODELO_GUION=claude-sonnet-5-5` |
| Rosa (blog) | Haiku 5.5 | Ordenar la investigación en un post |

**Búsqueda en Google casi gratis:** con `SERPER_API_KEY` (resultados de Google) y/o `TAVILY_API_KEY`
(texto de las páginas), Iván hace 8 búsquedas por app (¿paga?, estafa, Reddit, retiros, desarrollador…)
y Haiku las lee y saca hechos con su fuente; solo se aceptan URLs que de verdad salieron en la búsqueda.
Paola también busca en Google cuando le pides un **tema**; si le pides **una app concreta**
(*la app Cash Gato*), la busca solo en Play Store.

Además se recortó lo que se le manda a Iván (5 búsquedas, 3 capturas reducidas, 40 reseñas) y
piensan menos en las tareas fáciles. Estimado: **unos $0.15–0.35 USD por video**.

**El costo real se ve en la oficina:** arriba, lo gastado hoy y en el mes; en Proyectos, lo que
costó cada video por etapa; en Equipo, cada tarea con su modelo. Si una parte sale floja, sube
solo ese agente de modelo en `.env` (por ejemplo `MODELO_BLOG=claude-sonnet-5-5`).
- Voz: gratis con Edge; ElevenLabs según tu plan.
- WordPress y YouTube: gratis.

## ⚠️ Importante antes de automatizar al 100 %

1. **Política de YouTube de contenido "no auténtico" / repetitivo.** YouTube desmonetiza canales con
   videos producidos en masa con plantilla y voz sintética sin aporte propio. Por eso el flujo está
   pensado para que **tú** pongas lo que no se puede automatizar: tu grabación probando la app, tu
   prueba de retiro, tu opinión. La automatización te quita el trabajo pesado, no tu presencia.
2. **Difamación.** Decir que una app "es una estafa" es una afirmación seria. El investigador solo
   permite ese veredicto con evidencia fuerte, y el guionista usa "señales de alerta" en los demás
   casos. Aun así, revisa `REVISAR.md` y comprueba lo de "Antes de publicar".
3. **Voz sintética.** El video se sube marcando "contenido alterado o sintético", como pide YouTube,
   salvo que pongas `VOZ_MOTOR=propia`.
4. **Imágenes de Play Store** (icono, capturas): se usan para comentar y criticar la app, que es el
   uso habitual de este tipo de canal; no las uses como si fueran tuyas.

## Siguientes pasos posibles

- Grabación automática de la app con un emulador Android (`adb shell screenrecord`) para no grabar a mano.
- Versión vertical de 60 s para Shorts/TikTok a partir del mismo guion.
- Publicación programada (fecha y hora) en YouTube y WordPress.
