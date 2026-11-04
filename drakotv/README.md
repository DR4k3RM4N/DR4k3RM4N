# DrakoTV

Reproductor IPTV para PC (Windows, también Mac y Linux) al estilo de las apps de TV para el celular:
TV en vivo con guía, películas, series, favoritos, "seguir viendo" y control parental.

> DrakoTV es **solo un reproductor**. No incluye, aloja ni vende canales. Tú agregas tus listas:
> una cuenta de un proveedor (Xtream Codes), una lista M3U o los canales gratuitos y públicos
> del directorio iptv-org que vienen como opción para probar.

## Cómo abrirla en Windows

1. Instala [Node.js](https://nodejs.org/es/download) (versión LTS). Solo la primera vez.
2. Doble clic en **`INICIAR_WINDOWS.bat`**. La primera vez descarga los componentes (unos minutos);
   después abre directo.

### Crear el instalador `.exe`

- **Opción fácil:** cada vez que se sube un cambio a GitHub, la acción *"DrakoTV - instalador Windows"*
  crea el instalador. Entra a la pestaña **Actions** del repositorio, abre la última ejecución y
  descarga **DrakoTV-Windows** (trae el instalador y una versión portable que no necesita instalarse).
- **En tu PC:** doble clic en **`CREAR_INSTALADOR.bat`**. Los `.exe` quedan en la carpeta `dist`.

### En Mac o Linux

```bash
npm install
npm start
```

## Qué trae

| Sección | Funciones |
| --- | --- |
| **Inicio** | Seguir viendo, canales recientes y favoritos, películas y series recién agregadas, fecha de vencimiento y pantallas de la cuenta |
| **TV en vivo** | Categorías, buscador de canales, vista previa, programa actual con barra de progreso, programación del día, pantalla completa, cambiar de canal con flechas o escribiendo el número, lista de canales encima del video (tecla L) |
| **Guía** | Rejilla de programación de 12 horas por categoría, con la línea de "ahora" |
| **Películas** | Categorías, orden por recientes, A-Z, calificación o año, ficha con sinopsis, reparto y tráiler, continuar donde te quedaste |
| **Series** | Temporadas y episodios, marca de vistos, continuar el último episodio y reproducción automática del siguiente |
| **Favoritos y búsqueda** | Favoritos de canales, películas y series; búsqueda en todo el contenido (Ctrl+F) |
| **Reproductor** | HLS, MPEG-TS, MP4, MKV y WebM; cambia de formato solo si uno falla y se reconecta solo en vivo; elegir audio, subtítulos y calidad; ajustar, llenar o estirar la imagen, 16:9 y 4:3; velocidad; imagen en imagen; abrir en VLC |
| **Ajustes** | Varias fuentes, formato en vivo (m3u8/ts), User-Agent, búfer, guía XMLTV propia y ajuste de horario, control parental con PIN (las categorías de adultos se bloquean solas; el PIN inicial es 0000) |

### Atajos de teclado

`Espacio` pausa · `F` / `F11` pantalla completa · `M` silencio · `↑ ↓` cambiar canal (en películas: volumen) ·
`← →` atrasar/adelantar 10 s · números = ir al canal · `L` lista de canales · `Enter` pantalla grande ·
`Esc` volver · `Ctrl+F` buscar

## Fuentes compatibles

- **Xtream Codes:** servidor, usuario y contraseña. Trae TV, películas, series, guía y datos de la cuenta.
- **Lista M3U por enlace** o **archivo M3U**. Si la lista trae `url-tvg`, la guía se carga sola.
  Las películas y series se detectan por la extensión del archivo y por nombres tipo `S01E02`.
- **Canales gratuitos:** listas públicas de [iptv-org](https://github.com/iptv-org/iptv) por país
  o por tema. Algunos canales pueden no funcionar en tu región.

## Estructura

```
main.js            proceso principal: ventana, descargas sin CORS, guía XMLTV, caché, VLC
preload.js         puente seguro entre la ventana y el proceso principal
src/index.html     interfaz
src/styles.css     diseño
src/js/sources.js  lectura de M3U y API de Xtream Codes
src/js/player.js   reproductor (hls.js, mpegts.js y nativo)
src/js/app.js      pantallas, favoritos, historial y control parental
```

Tus datos (fuentes, favoritos, historial, ajustes) se guardan en tu PC, en
`%APPDATA%\DrakoTV` en Windows.
