# Canal "¿Quién MATÓ a…?" · Guía para Claude

Lee esto antes de trabajar en esta carpeta. Aquí está la idea del canal, cómo se hacen los videos y las reglas que Miguel ya decidió. Háblale a Miguel en español de México, claro y directo.

## La idea

- **Qué es:** un canal de YouTube en español (México) que investiga, como si fuera un caso policiaco, **quién mató a una marca** famosa de Estados Unidos, México o Latinoamérica.
- **El sello propio:** cuando aplica, el giro de **"murió allá… y en México sigue viva / la rescató alguien de aquí"**.
- **Referencia de estilo:** el canal "Se Lo Buscaron" (por ejemplo, su video de Starbucks). Miguel quiere ese estilo de edición.
- **Título fijo de la serie, sin cambiarlo:** `¿Quién MATÓ a [Marca]?`
- **Duración:** de 15 a 20 minutos de video. Miguel pidió entre 15 y 30.

## Estructura de cada guion

1. **Gancho**, de 30 a 60 segundos: el contraste más fuerte, con cifras. Por ejemplo, "quedan 5 tiendas allá, más de 90 aquí".
2. **Presentación del caso:** "Expediente #00X" y el tablero de sospechosos, 3 o 4.
3. **La víctima:** el origen y la época de gloria, con anécdotas reales.
4. **Los sospechosos, uno por uno:** cada uno con datos y fechas.
5. **El giro de México:** qué pasó aquí y por qué.
6. **"¿Final feliz?":** los riesgos actuales, para ser honestos y no vender humo.
7. **Veredicto:** la opinión, presentada como opinión, y la pregunta al público para los comentarios.
8. **Adelanto del siguiente expediente.**

Tono narrativo, frases cortas, palabras de México ("tóper", "plaza", "a meses", "quincena").

## Estilo visual: `estilo="cine"`

- **Material real a pantalla completa** casi todo el tiempo: fotos y videos.
- **Texto encima del material:**
  - abajo a la izquierda, con etiqueta amarilla
  - cajas con número grande (`caja=("90+", "TIENDAS\nEN MÉXICO")`)
  - titulares enormes en rojo y blanco sobre imagen en blanco y negro (`head=`)
- **Pantalla dividida en diagonal** (`SPLIT`) para comparar, por ejemplo EE.UU. contra México.
- **Gráficas** (barras, cifras, tablero de sospechosos, sellos) **sobre video desenfocado**, nunca sobre fondo negro vacío. Se logra con `fondo=` en cada escena del storyboard.
- **Ritmo:** cambiar de imagen cada 3 a 5 segundos; si una frase es larga, se le ponen varias tarjetas.
- **Créditos chiquitos** abajo a la izquierda, en cada foto o video.

## Proceso (todo se hace con el motor en `motor/`)

1. **Investigar:** fuentes reales, con una fuente para cada cifra. Marcar lo que esté dudoso.
2. **Guion técnico** en `0X-marca/01-guion-tecnico.md`: cada `## ESCENA N · Título` abre una escena y cada línea `> ` es una frase de narración.
3. **Material:**
   - `python -E -P motor/fuentes_libres.py commons "busqueda"`: Wikimedia Commons.
   - Mixkit: solo los clips con **"Free License"**; los "Restricted" no sirven.
   - Descargar con `motor/fuentes_libres.py descargar <manifiesto.json> <carpeta>`. Los créditos se guardan solos.
4. **Storyboard** en `0X-marca/storyboard.py`: una tarjeta (o lista de tarjetas) por frase, en el mismo orden. Usa como modelos `01-sears/storyboard.py` y `02-tupperware/storyboard.py`.
5. **Revisar las tarjetas:** `python -E -P motor/motor.py 0X-marca --hojas`, y mirar `render/hojas/*.jpg`.
6. **Renderizar:** `python -E -P motor/motor.py 0X-marca --render`. Genera la voz, la música, los subtítulos, los capítulos, los créditos y el MP4 a -14 LUFS.
7. **Miniaturas:** `miniatura.py` en cada episodio. Pantalla dividida con fotos reales y 1 o 2 palabras gigantes ("MURIÓ / VIVE", "5 contra 90+", "QUEBRÓ / LO COMPRÓ MÉXICO").

Detalles técnicos del motor en `motor/LEEME.md`. Usa siempre `python -E -P`, no `-I`, porque OpenCV está en los paquetes del usuario.

## Voz

- **Azure**, voz **es-MX-JorgeNeural**, con `voz_velocidad="+12%"`. A Miguel la velocidad normal le pareció lenta.
- La clave está en `canal-youtube/.azure_speech`: renglón 1 la clave, renglón 2 la región (`eastus`). **Nunca la imprimas.**
- Es el plan gratis (F0): 500 mil caracteres al mes, y cada video gasta unos 15 a 20 mil.
- Si una voz lee mal un nombre en inglés, agrégalo en `fonetica_azure` del storyboard. Por ejemplo, "Sears" → "Sírs".
- La voz de Windows ("Raúl") le pareció horrible a Miguel. No la uses.

## Reglas que no se rompen

- **Material (decisión de Miguel, nov 2026):** fotos de **cualquier sitio** (Google Imágenes, noticias, la marca,
  Wikimedia), siempre con crédito de la fuente en pantalla y sin fotos con marca de agua de bancos de imágenes. Videos:
  solo **cortos** de stock (Pexels/Mixkit/Wikimedia); nada de videos largos, clips de YouTube, noticieros ni comerciales.
- **Datos:** ninguna cifra sin fuente. Cada episodio tiene su `04-fuentes.md` con la lista de "datos por verificar".
- **Personas:** no uses fotos de personas privadas (por ejemplo, credenciales con nombre). Si un video de stock con una persona podría confundirse con el protagonista real, márcalo como "(ilustrativo)" o usa otra imagen.
- **Opinión, no acusación:** el veredicto es opinión; si hubo demanda, se dice también lo que respondió el acusado.
- **Wikimedia limita descargas:** usa miniaturas de 1920 px y videos convertidos (`commons_thumbs`, `commons_video_transcode`). Si responde 429, más calma.
- **Mixkit** tiene protección anti-bots: no la evadas. Revisa pocas páginas a la vez.
- **Nada se publica sin que Miguel lo apruebe.**

## Estado de los episodios

| # | Marca | Carpeta | Estado |
|---|---|---|---|
| 001 | Sears | `01-sears/` | Video listo (15:27), estilo cine. Faltan 8 datos por verificar |
| 002 | Tupperware | `02-tupperware/` | Video listo, estilo cine. Faltan 9 datos por verificar |
| 003 | Blockbuster | — | Siguiente. Gancho: Elektra compró Blockbuster México en 2014 |

En `plan-del-canal.md` hay 24 temas más. Antes de publicar cada video, pega en la descripción: los capítulos (`render/*-capitulos.txt`), los créditos (`render/*-creditos.txt`) y el aviso de "análisis y opinión".
