# RevoLabs MLT · Monitor de Lives de TikTok

Versión **0.5.1** · © 2026 Revo Labs · Uso interno.

## Novedades de la v0.5.1

- **Chat y espectadores visibles:** nueva opción **Vista** en la barra. "Video + chat" (viene activada por defecto) hace que TikTok muestre los comentarios y los espectadores junto al video; "Solo video" lo muestra más grande. Cada live puede cambiar su propia vista con el botón 💬. Si el texto se ve muy chico, usa menos columnas o amplía el live (⤢ o doble clic).
- **Guías de encuadre:** opción **Guías** en la barra (Tercios + centro, Solo centro o Cuadrícula fina) o tecla G. Las líneas se dibujan justo sobre la imagen del video para ver si el live está derecho y centrado. El botón 📐 de cada live prende o apaga las guías solo en ese live.
- **Menos falsas alarmas:** un live tiene que seguir caído unos 45 segundos antes de avisar, y uno congelado necesita alrededor de 1 minuto sin avanzar. Los cortes cortos ya no avisan.
- **Sin avalancha al minimizar:** con la app minimizada ya no se revisa si el video está congelado, porque Windows y Mac lo frenan. Varias alertas juntas se agrupan en un solo aviso, el sonido no se repite más de una vez cada 15 segundos, y un corte breve de internet tampoco avisa.

## Novedades de la v0.5

- **Mover lives arrastrando:** toma un live desde ⠿ (en su barra) y suéltalo donde quieras. El orden se guarda y los atajos 1–9 siguen el nuevo orden.
- **Favoritas:** pulsa ☆ en la barra de un live para guardarlo. En el panel **⭐ Favoritas** das clic en una cuenta para abrirla o cerrarla. Con **Abrir todas** abres tus favoritas, y con **Solo favoritas** cierras las demás. Quitar un live de la cuadrícula no lo borra de favoritas.
- **Silenciar / Activar todo:** el mismo botón silencia todos los lives o activa el audio de todos (tecla M). El 🔊 de cada live sigue dejando escuchar solo ese; con Ctrl+clic lo sumas a los que ya suenan.
- **Alertas de desconexión:** si un live que estaba transmitiendo se cae, termina, se congela o se pierde el internet, verás un aviso abajo a la derecha, la casilla en rojo y un aviso de Windows o Mac, y sonará una alerta. Cuando el live vuelve, también te avisa. En **Alertas** eliges "Sonido y aviso", "Solo aviso" o "Apagadas".
- **Ventanas más responsive:** las columnas se calculan según el tamaño de la ventana, el zoom "Auto" ajusta el contenido de TikTok al tamaño de cada casilla, y en ventanas o casillas chicas se ocultan los textos y botones menos usados. Si hay muchos lives, la cuadrícula hace scroll en vez de aplastarlos.
- **Extras:** doble clic en la barra de un live lo amplía, y F11 activa la pantalla completa.

Tu lista de lives, tus notas y tu sesión de las versiones anteriores se conservan.

## Instalar

- **Windows:** extrae `RevoLabs-MLT-0.5.1-Windows.zip` y abre `RevoLabs-MLT-0.5.1.exe`. Si sale "Windows protegió su PC", pulsa "Más información" y luego "Ejecutar de todas formas".
- **Mac Apple Silicon (M1–M4):** `RevoLabs-MLT-0.5.1-Mac-arm64.zip`.
- **Mac Intel:** `RevoLabs-MLT-0.5.1-Mac-x64.zip`.
  La primera vez ve a Ajustes del Sistema → Privacidad y seguridad → "Abrir de todas formas". Si dice que la app "está dañada", abre Terminal y ejecuta `xattr -cr "/Applications/RevoLabs MLT.app"`.

## Para desarrolladores

```bash
npm install
npm start          # abrir en modo desarrollo
npm run dist:win   # genera dist/RevoLabs-MLT-<versión>.exe
npm run dist:mac   # genera los zip de Mac (Apple Silicon e Intel)
```

`scripts/afterPack.js` pone el icono y los datos de versión del .exe sin necesitar Windows.
