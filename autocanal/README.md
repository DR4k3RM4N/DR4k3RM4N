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
| Editor | `editor.py` + `graficos.py` | Tarjetas (título, captura, reseña, dato, veredicto), zoom suave, tus grabaciones, subtítulos y música. |
| Blog | `blog.py` | Entrada SEO, sube capturas dentro del texto, pone la imagen destacada de Play Store y deja un hueco para el video. |
| YouTube | `youtube.py` | Sube el video, la miniatura y los metadatos; enlaza el blog. |

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

## Costo aproximado por video

- Claude (investigación con búsqueda web + guion + blog): del orden de 1–2 USD con `claude-opus-5-5`.
  Puedes bajarlo con `--sin-web` o usando `AI_MODEL=claude-sonnet-5-5` en `.env`.
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
