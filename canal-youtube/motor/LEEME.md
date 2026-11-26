# Motor de video · serie "¿Quién MATÓ a…?"

Convierte un guion técnico en un video terminado:
- tarjetas animadas con el estilo de expediente,
- voz,
- música de fondo,
- subtítulos,
- capítulos,

todo en 1920×1080, 30 fps y audio a -14 LUFS (el estándar de YouTube).

## Lo que necesitas instalado

- Python con Pillow, NumPy y OpenCV (ya los tienes).
- ffmpeg (ya lo tienes).
- Windows con la voz "Raúl" en español de México (ya la tienes).

## Comandos

Corre todo desde la carpeta `canal-youtube`:

```powershell
python motor/motor.py 02-tupperware --hojas
```
Genera **hojas de contacto** con todas las tarjetas en `render/hojas/`, para revisarlas antes de renderizar. Tarda unos segundos.

```powershell
python motor/motor.py 02-tupperware --render --escenas 1-2
```
Renderiza una **prueba** con solo algunas escenas.

```powershell
python motor/motor.py 02-tupperware --render
```
Renderiza el **video completo**. Tarda unos 10 minutos.

## Voz realista con Azure (gratis hasta 500 mil caracteres al mes)

1. En `storyboard.py`, pon `voz_motor="azure"` y `voz="es-MX-JorgeNeural"` (u otra voz de México).
2. Crea el archivo `canal-youtube\.azure_speech` con dos renglones: la clave y la región.
3. Para escuchar muestras de todas las voces de México:
   ```powershell
   python -E -P motor/voz_azure.py muestras 02-tupperware
   ```
   Las muestras quedan en `render/muestras-voz/`.

## Cambiar la voz de computadora por la tuya

1. Graba cada escena en un archivo, leyendo `02-narracion.md`.
2. Guárdalos como `02-tupperware/voz/escena-01.wav`, `escena-02.wav` … `escena-14.wav`. Puedes grabar solo algunas escenas: las que no tengan archivo se quedan con la voz de computadora.
3. Vuelve a correr `--render`.

El motor reparte las tarjetas de cada escena según lo largo de cada frase. Lee a ritmo parejo para que coincidan con lo que dices.

## Hacer el siguiente expediente

1. Copia la carpeta del episodio (por ejemplo, `02-tupperware` → `03-blockbuster`).
2. Escribe `01-guion-tecnico.md`. Cada línea que empieza con `> ` es una frase de narración, y cada `## ESCENA N · Título` abre una escena.
3. Escribe `storyboard.py` con **una tarjeta por frase**, en el mismo orden. Los tipos de tarjeta están en `motor/sb.py`.
4. Revisa con `--hojas` y renderiza.

## Ajustes en `storyboard.py`

| Campo | Para qué |
|---|---|
| `fonetica` | Cómo debe pronunciar la voz los nombres en inglés (por ejemplo, "Tupperware" → "Táperuer") |
| `musica_vol` | Volumen de la música (0.35 por defecto) |
| `voz` | Nombre de la voz de Windows ("Raul" o "Sabina") |

## Qué genera (en `render/`)

| Archivo | Qué es |
|---|---|
| `…-BORRADOR.mp4` | El video, con los subtítulos incluidos como pista aparte |
| `…-BORRADOR.srt` | Los subtítulos para subirlos a YouTube |
| `…-capitulos.txt` | Los capítulos con sus tiempos reales, listos para pegar en la descripción |
| `miniatura-A.jpg`, `miniatura-B.jpg` | Las miniaturas (se generan con `python miniatura.py` dentro del episodio) |

La música es un fondo sintético y sencillo. Si quieres otra, cámbiala en tu editor por una de la Biblioteca de Audio de YouTube.
