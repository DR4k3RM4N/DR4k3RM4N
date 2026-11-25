# 🕵️ Pedido: oficina "Expedientes" (serie «¿Quién MATÓ a…?»)

> Copia TODO este archivo y pégalo en un chat nuevo de Claude Code sobre el repo DR4k3RM4N/DR4k3RM4N,
> rama `claude/keen-johnson-v42a39`. Adjunta también el HTML del paquete del expediente (o su enlace de Artifact).

---

Hola. Soy Miguel. Antes de nada lee `CLAUDE.md` y `CONTEXTO.md` del repo: ahí están las reglas de siempre
(español de México, paso a paso, nada de claves en el chat, lo más barato posible, nada inventado, probar en modo
demo con Playwright antes de subir, commits en español, el servidor se actualiza solo desde esta rama).

## Qué quiero

Una oficina nueva llamada **🕵️ Expedientes** dentro de la oficina que ya tengo (`autocanal/oficina.py`). Que sea
**una pestaña y un botón de ala más**, como Tampiqueando, pero **SIN dibujar otro cuarto en el edificio**: el
edificio ya está pesado. Solo panel, agentes en la pestaña y su chat.

Sirve para producir los videos largos de la serie **«¿Quién MATÓ a [Marca]?»**: documentales de ~15–20 min sobre
marcas que murieron (o están por morir) y qué pasó con ellas en México. Cada video es un "expediente" (#001, #002…).
La plantilla del título NO cambia nunca: «¿Quién MATÓ a [Marca]?».

## La entrada: el paquete de producción

Yo (con Claude en el chat) armo un **paquete** por expediente, en una página HTML (Artifact de claude.ai) o ZIP con
estas partes. La oficina debe poder **importarlo** (subir el HTML/ZIP desde la pestaña) y separarlo en:
- `00-BRIEF-agentes`: entregables, especificaciones, tareas en orden, guía de estilo, **lista de gráficas G1…Gn con
  datos exactos**, tomas que grabo yo (T1…Tn), reglas.
- `01-guion-tecnico`: escenas numeradas; cada una con **Visual** (etiquetas PROPIA / STOCK "términos" / ARCHIVO /
  GRÁFICA G#), **Texto en pantalla**, **Audio** (música y efectos) y la **narración** (párrafos de voz).
- `03-publicacion`: título, conceptos de miniatura A/B/C, descripción con capítulos, etiquetas, comentario fijado,
  pantalla final y **5 Shorts** (gancho, de qué escena sale, texto en pantalla).
- `04-fuentes`: fuentes (URLs) por escena y la **lista de datos por verificar**.
Guarda todo como proyecto en `autocanal/expedientes/<numero>-<marca>/` (paquete.json + archivos).

## El equipo (nombres sugeridos, cámbialos si quieres)
- 🔎 **Detective Ramos** (verificación): revisa la lista de datos por verificar y CADA cifra del guion contra sus
  fuentes. Lee la página original; si no puede, busca con Serper. Por cada dato: ✅ confirmado (con enlace y cita),
  ⚠️ corregir (con la frase nueva propuesta) o ❌ no confirmado (propone quitarlo o suavizarlo). **Nunca agrega
  cifras que no estén en las fuentes.** Me entrega el reporte y la **narración corregida** para grabar. Nada avanza
  sin mi OK.
- 📊 **Gráficas** (G1…Gn): las anima con datos exactos y la guía de estilo del paquete (fondo #121212 con textura,
  amarillo #FFD60A, rojo #E63946, verde #2DC653, blanco #F5F5F5, Bebas Neue + Inter, fuente de cada cifra abajo a
  la izquierda, barras que crecen 0.6 s, contadores, zoom 105 %). Usa el proyecto Remotion que ya existe
  (`salaedicion/motion`, composición nueva tipo "Expediente") y renderiza en mis compus de la sala de edición. La
  carátula/tablero del expediente (G14 en el #002) es plantilla **reutilizable** de la serie.
- 🎞️ **Archivista** (stock y archivo): busca por los términos STOCK de cada escena SOLO en Pexels, Pixabay, Mixkit y
  Wikimedia Commons (solo licencia libre o dominio público; música/efectos de la Biblioteca de Audio de YouTube los
  bajo yo). Usa las APIs oficiales de Pexels y Pixabay (claves en `.env`: `PEXELS_API_KEY`, `PIXABAY_API_KEY`). Me
  deja escoger en la pestaña. Todo queda en `licencias.csv` (archivo, fuente, URL, licencia, escena). Prohibido:
  comerciales, noticieros, documentales, fotos sin licencia clara (se reemplazan por ilustración o silueta).
  Titulares de noticias: captura chica en marco.
- 🖼️ **Miniaturas**: conceptos A y B del paquete, 1280×720 JPG < 2 MB, foto real (mía o stock libre), no IA.
- ✂️ **Editor**: arma el video escena por escena con MI voz (subo `escena-01.wav`…`escena-14.wav` desde la pestaña),
  1920×1080, 30 fps, H.264 16–20 Mbps, AAC 48 kHz, mezcla ≈ −14 LUFS, música 25–30 dB abajo con ducking, cambio
  visual cada 3–6 s (nunca > 8 s fija), texto en pantalla máx. 6 palabras, 20 s de pantalla final. Edita en mis
  compus (sala de edición) si están prendidas.
- 💬 **Subtítulos y Shorts**: `.srt` con Whisper local (gratis) desde el audio final, y me deja revisarlo a mano en
  la pestaña (lista de palabras difíciles del brief). Los 5 Shorts 1080×1920 < 60 s, subtítulos grandes quemados,
  gancho en los primeros 2 s y "Video completo en el canal".
- 📤 **Publicación**: sube a YouTube en **PRIVADO** (usa `agentes/youtube.py`, ya fuerza privado) con título,
  descripción, capítulos ajustados a los tiempos reales, etiquetas, miniatura y subtítulos. Me manda el enlace por
  WhatsApp/Telegram. **Solo yo lo hago público.** Pregúntame a qué canal sube (la oficina ya maneja varios canales en
  `agentes/canales.py`; quizá este sea un canal nuevo).

## La pestaña 🕵️ Expedientes
- Lista de expedientes con su avance por pasos: Verificación → Voz → Gráficas → Stock → Edición → Subtítulos →
  Shorts → Subida (privado) → Miniaturas.
- Botón "📥 Importar paquete" (HTML o ZIP).
- Reporte de verificación con ✅/⚠️/❌ y botón "Aprobar cambios" que genera la narración corregida (y su PDF para
  leerla en el cel, como el PDF de guiones de TikTok Shop).
- Subir voz por escena, ver gráficas, escoger stock, ver el armado, revisar subtítulos, ver Shorts.
- La lista final antes de subir (checklist del brief) visible.
- Chat con el equipo para pedir cambios (como el chat de Sofi en TikTok Shop).

## Reglas que no se rompen
1. Ningún dato sin fuente: todo sale de `04-fuentes`.
2. Nada público sin mi OK. Siempre privado.
3. La voz final es la mía (TTS solo para borradores llamados `BORRADOR-NO-PUBLICAR`).
4. Solo material con licencia libre, todo en `licencias.csv`.
5. Análisis y opinión: no se acusa a nadie de delitos; aviso en la descripción.
6. La plantilla del título no cambia.
7. **Costo cero en Claude**: todo con mi plan de Claude (Opus), como la oficina de TikTok Shop (`claude.SOLO_PLAN`);
   la API solo si prendo una casilla 💳. Búsquedas con Serper.
8. Las claves solo en el `.env` del servidor (`sudo nano /opt/canal/autocanal/.env`), nunca en el chat ni en el repo.

## Red (para el chat nuevo)
La sesión de Claude en la nube necesita poder abrir: las páginas de las fuentes de cada expediente (Wikipedia,
Business Wire, SEC, medios), `api.pexels.com`, `pixabay.com`, `commons.wikimedia.org`, `upload.wikimedia.org`.
Si no puede, que me lo pida con el botón de permisos (yo apruebo) o que use búsquedas.

## Estado del Expediente #002 · Tupperware (para no repetir)
Paquete: https://claude.ai/artifact/1RJzQzCHWyMK3pVhWxY18R (lo lees con la herramienta Artifact, action "read").
Verificación ya hecha con búsquedas (falta leer originales donde se indica):
- ✅ Bancarrota 17 sep 2024 (SEC 8-K, Delaware).
- ✅ Lerma = "Toluca" de Expansión (Parque Industrial Lerma, junto a Toluca). Decir siempre Lerma.
- ✅ Betterware llegó en 1995 (Wikipedia, befra.com).
- ✅ LatAm 404 M en 2022 (Xataka, El Ceo). 278 M era proyección (anuncio ene 2026); el cierre (2 jun 2026) da
  ~270 M reales en 2025 → propuesta: "$404 M → $270 M" (confirmar leyendo el comunicado de cierre).
- ⚠️ Isla: era Isla San José, **Panamá** (Islas de las Perlas); murió en Costa Rica en 1983. Renunció a la
  nacionalidad en fecha incierta (60s–1973) → "Después se divorció, renunció… y se compró una isla en Panamá. Murió
  en Costa Rica en 1983."
- ⚠️ "Planta más grande del mundo": solo comunicados del 80 aniversario; tupperware.com.mx dice "una de las cinco
  más grandes" → "una de las plantas más grandes de Tupperware en el mundo, según la propia marca".
- ❌ "200 vendedoras en 1951": sin fuente → "Empezó con un puñado de vendedoras. En pocos años eran miles."
- ❌ "Más de 500 autos según Expansión": es un comunicado de Tupperware México (sep 2026): 500 autos a Líderes de
  Unidad Vanguardia durante 2026 → "este año, la marca dice que entregó quinientos autos a sus líderes de venta".
- ❓ "~1 millón de asociados" (BeFra 3T25: 1,099,550): no se pudo ver si incluye Jafra → mientras, "cientos de miles
  de asociados".
- Extra: escena 12 dice que la red de asociados se achicó, pero en 3T25 creció 2.1 % → quitar esa frase.
  El enlace de Expansión en Fuentes (2026/09/28) parece ser el del 26/09/2026.
Falta que yo apruebe estas propuestas antes de grabar.

## Cómo quiero que trabajes
1. Primero dime en 5–8 pasos cómo lo vas a armar y qué piezas existentes reusas. Espera mi "va".
2. Constrúyelo por partes (importar + verificación primero; luego gráficas/stock; luego edición/subtítulos/Shorts;
   al final subida). Cada parte probada en modo demo con Playwright antes de subirla a la rama.
3. Al terminar cada parte, explícame corto qué cambió y qué voy a ver (recargo con Ctrl + F5 en ~2 min).
