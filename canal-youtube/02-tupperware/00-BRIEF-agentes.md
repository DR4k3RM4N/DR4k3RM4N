# BRIEF · Expediente #002: ¿Quién MATÓ a Tupperware?

**Para:** el equipo (agentes) que va a producir el video.
**Dueño y aprobador:** Miguel. **Nada se publica en público sin su aprobación.**

## 1. Qué vamos a entregar

| Entregable | Especificación |
|---|---|
| Video largo | 1920×1080 (16:9), 30 fps, MP4 H.264 a 16–20 Mbps, audio AAC 48 kHz. **Duración aproximada: 19 minutos.** |
| Subtítulos | Archivo `.srt` en español, sincronizado con la narración final |
| Miniaturas | Conceptos A y B de `03-publicacion.md`, en 1280×720 JPG de menos de 2 MB |
| Shorts | Los 5 (S1 a S5) de `03-publicacion.md`, en 1080×1920 y menos de 60 segundos |
| Registro de licencias | `licencias.csv` con columnas archivo, fuente, URL, licencia y escena |
| Datos para subir | Título, descripción, capítulos ajustados, etiquetas y comentario fijado (de `03-publicacion.md`) |

## 2. Archivos de este paquete

| Archivo | Para qué sirve |
|---|---|
| `00-BRIEF-agentes.md` | Este documento: tareas, reglas y especificaciones |
| `01-guion-tecnico.md` | **La biblia de la edición.** 14 escenas con narración, visual, texto en pantalla y audio |
| `02-narracion.md` | Solo el texto que se graba (para Miguel) |
| `03-publicacion.md` | Título, miniaturas, descripción, capítulos, etiquetas y Shorts |
| `04-fuentes.md` | Fuentes por escena y lista de datos por verificar |
| `version-corta-11min.md` | Versión anterior de 11 min. **No usar**; solo de referencia |

## 3. Tareas, en orden

```
1. Verificación ──► 2. Voz (Miguel) ──► 5. Edición ──► 6. Subtítulos ──► 7. Shorts ──► 8. Subida en privado
                    3. Gráficas  ─────┘
                    4. Visuales/stock ┘
                    9. Miniaturas (en paralelo, en cualquier momento)
```

### Tarea 1 · Verificación de datos (antes de grabar)
- Revisa los 9 datos de la "Lista de datos por verificar" en `04-fuentes.md`.
- Si un dato se confirma, márcalo como confirmado y anota el enlace. Si no se confirma, **propón cómo quitarlo o suavizarlo en el guion y avísale a Miguel** antes de que grabe.
- **Prohibido agregar cifras que no estén en `04-fuentes.md`.**

### Tarea 2 · Voz (la hace Miguel)
- La narración final es **la voz de Miguel**. No usamos voz de IA en la versión que se publica, porque YouTube puede quitar la monetización a los canales que considere "contenido repetitivo" o poco auténtico.
- Si un agente necesita una voz temporal para armar el ritmo (animatic), puede usar TTS, pero el archivo debe llamarse `BORRADOR-NO-PUBLICAR`.
- Miguel graba por escena (`escena-01.wav` a `escena-14.wav`) siguiendo los consejos de `02-narracion.md`.

### Tarea 3 · Gráficas (G1 a G14)

**Guía de estilo**
- Fondo negro carbón `#121212`, con textura sutil de papel o expediente.
- Colores:
  - Amarillo cinta `#FFD60A`: títulos y sospechosos.
  - Rojo `#E63946`: caídas, deuda, Estados Unidos en las comparaciones.
  - Verde `#2DC653`: México y lo que crece.
  - Blanco `#F5F5F5`: texto general.
- Tipografías gratis de Google Fonts: **Bebas Neue** para títulos y **Inter** para datos.
- Cada cifra lleva su fuente abajo a la izquierda, en texto chico (por ejemplo, "Fuente: SEC, 10-K 2019").
- Animación: barras que crecen en 0.6 segundos, contadores de números y zoom lento (105%) en fotos.

**Lista de gráficas**

| # | Gráfica | Datos exactos | Escenas |
|---|---|---|---|
| G1 | Contraste de montos | $23.5 M (rojo) contra $250 M (verde) | 1 |
| G2 | Línea de tiempo | 1946 primeros recipientes · 1951 sale de tiendas · 1954 Jubileo y BusinessWeek · 1958 corren a Wise y se vende la empresa · 1966 llega a México (Lerma) · 2013 máximo de $2,670 M · 2022 Target · 2023 alerta y meme · 2024 bancarrota · 2026 Betterware | 6, 8 |
| G3 | Ventas globales | 2013: $2,670 M · 2022: $1,310 M | 6, 9 |
| G4 | Fuerza de ventas | -18% en 2022 (siluetas que desaparecen) | 8 |
| G5 | Deuda | Contador hasta $812 M · "7 renegociaciones" | 9 |
| G6 | La acción meme | "+800% en 2 semanas (verano de 2023)", flecha estilizada, sin gráfica real de precios | 9 |
| G7 | Mapa de la fábrica | Hemingway, Carolina del Sur → Lerma, Estado de México · "148 despidos" | 9 |
| G8 | México vs. EE.UU. (2019) | México $261.7 M (verde) · EE.UU. $132.7 M (rojo) · nota: "incluye productos de belleza" | 10 |
| G9 | La compra | $250 M = $215 M en efectivo (prestado) + $35 M en acciones · México + Brasil · licencia perpetua, exclusiva y sin regalías | 10 |
| G10 | Betterware | CEDIS de 7 hectáreas en El Arenal, Jalisco · +4 M de productos por semana · ~1.1 M de asociados (3T 2025) | 10 |
| G11 | Tupperware Latinoamérica | 2022: $404 M · 2025 (proyectado): $278 M | 12 |
| G12 | Producción de la planta | ~80% se queda en México · el resto va a EE.UU. (dona) | 11 |
| G13 | Tarjeta de la RAE | "táper… procede de las marcas registradas Tupperware® o Tupper®", con "tóper: sobre todo en México" resaltado | 7 |
| G14 | Expediente y tablero | Carátula "EXPEDIENTE #002 · TUPPERWARE · 1946–2024" · tablero con 3 siluetas que se destapan: #1 Su propio nombre, #2 La fiesta, #3 La deuda | 2, 7, 8, 9, 13 |

**Importante:** G14 (la carátula del expediente y el tablero) es la identidad de la serie. Guárdalo como plantilla editable para reutilizarlo en todos los videos.

### Tarea 4 · Visuales de stock y archivo
- Sigue las etiquetas [STOCK] y [ARCHIVO] de cada escena del guion técnico.
- **Fuentes permitidas:**
  - Pexels, Pixabay y Mixkit para video e imagen.
  - Wikimedia Commons, solo con licencia libre o de dominio público.
  - Biblioteca de Audio de YouTube para música y efectos.
- **No permitido:**
  - Comerciales completos de marcas, clips de noticieros o fragmentos de documentales.
  - Fotos sin licencia clara. Si una foto histórica no tiene licencia libre, se reemplaza con una ilustración o silueta.
- Los titulares de noticias se muestran como captura pequeña, dentro de un marco y con la narración comentándolos.
- Registra cada archivo en `licencias.csv`.

### Tarea 5 · Edición
- Arma el video siguiendo `01-guion-tecnico.md`, escena por escena.
- **Ritmo:** cambio visual cada 3 a 6 segundos, y nunca más de 8 segundos con la misma imagen fija.
- **Audio:**
  - La voz se normaliza para que la mezcla final quede cerca de **-14 LUFS**.
  - La música va de 25 a 30 dB por debajo de la voz, bajando sola cuando hay voz (ducking).
  - Los efectos van sutiles.
- **Música por escenas:**
  - Misterio para la escena 1, la 2 y de la 7 a la 9.
  - Nostalgia para la 3.
  - Swing suave de los 50 para la 4.
  - Cálida para la 6.
  - Esperanza con un toque mexicano para la 10 y la 11.
  - Reflexiva para la 12.
  - La música de cierre de la serie para la 14.
- **Texto en pantalla:** lo indicado en cada escena, máximo 6 palabras por frase.
- Deja 20 segundos al final para la pantalla final.
- Exporta con las especificaciones de la sección 1.

### Tarea 6 · Subtítulos
- `.srt` generado del audio final y **revisado a mano**. Ojo con estas palabras: tóper, táper, Tupperware, Betterware, Brownie Wise, Kissimmee, Lerma, Hemingway, Jafra, BeFra.
- Se suben como subtítulos aparte; no van quemados en el video largo.

### Tarea 7 · Shorts
- Los 5 Shorts de `03-publicacion.md`, recortados del video final y reencuadrados a vertical.
- Llevan subtítulos grandes y quemados, el gancho en los primeros 2 segundos y al final "Video completo en el canal".

### Tarea 8 · Subida
- Sube el video como **PRIVADO** u **OCULTO**, con título, descripción, capítulos ajustados, etiquetas, miniatura, subtítulos y pantalla final.
- Avísale a Miguel con el enlace para que lo revise. **Solo Miguel lo cambia a público.**

### Tarea 9 · Miniaturas
- Los conceptos A y B de `03-publicacion.md`.
- Usa una foto real de un tóper (de las tomas de Miguel o de stock libre), no imagen generada con IA.

## 4. Tomas que tiene que grabar Miguel

| # | Toma | Escena | Notas |
|---|---|---|---|
| T1 | Mano que deja un tóper con frijoles sobre la mesa de la cocina | 1, 13 | Primer plano, luz cálida |
| T2 | Tóper viejo con un nombre escrito con plumón | 1 | Macro |
| T3 | Recipiente lleno de agua que se voltea sin derramarse | 4 | Hay que probar antes con un tóper hermético |
| T4 | Pasillo de recipientes en un súper | 7 | Pide permiso o graba discreto, sin caras |
| T5 | Puesto de tianguis con tópers y precios | 7, 10 | Sin caras reconocibles |
| T6 | Un Kleenex y un Resistol | 7 | Primer plano |
| T7 | Catálogos de venta directa sobre una mesa | 6, 10 | Manos que pasan las páginas |
| T8 | Celular con un catálogo en WhatsApp | 10, 11 | **Sin nombres ni números visibles** |
| T9 | Tóper volteado que muestra "Hecho en México" en la base | 11 | Solo si el tuyo lo trae |
| T10 | Corredor industrial Lerma–Toluca, de lejos | 1, 6 | ⚠️ **El aeropuerto de Toluca está muy cerca de Lerma: no vueles el dron ahí sin revisar las zonas restringidas de la AFAC.** Mejor grábalo desde el piso o usa stock |
| T11 | Caja de VHS con luz azul y amarilla | 14 | Adelanto del próximo expediente |

## 5. Reglas que no se rompen

1. **Ningún dato sin fuente.** Todo sale de `04-fuentes.md`.
2. **Nada se publica en público sin el OK de Miguel.**
3. **La voz final es la de Miguel.**
4. **Solo material con licencia libre**, y todo queda registrado en `licencias.csv`.
5. **Opinión, no acusación.** El video analiza decisiones de negocio públicas; no acusa a nadie de delitos. Se mantiene el aviso de "análisis y opinión" en la descripción.
6. **La plantilla del título no cambia:** "¿Quién MATÓ a [Marca]?"

## 6. Lista final antes de subir

- [ ] Los 9 datos verificados, o quitados del guion
- [ ] Voz de Miguel en todas las escenas
- [ ] Gráficas G1 a G14 con su fuente en pantalla
- [ ] `licencias.csv` completo
- [ ] Audio cerca de -14 LUFS, sin picos
- [ ] Subtítulos `.srt` revisados a mano
- [ ] Capítulos ajustados a los tiempos reales
- [ ] Miniaturas A y B
- [ ] Subido en privado y enlace enviado a Miguel
- [ ] Shorts S1 a S5 listos para programarse uno por día
