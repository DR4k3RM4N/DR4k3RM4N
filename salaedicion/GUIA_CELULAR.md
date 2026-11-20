# 📱 El robot probador: tu Android viejo prueba las apps solo

Con el cel conectado por USB a una compu de la sala de edición, cuando la oficina va a investigar una app:
la instala de Play Store, la usa unos minutos como una persona (ve anuncios, junta monedas, busca el retiro),
**graba la pantalla**, anota de qué apps son los anuncios y te deja todo para el video. Lo maneja Claude Code
con tu plan (0 ¢).

## Preparar el cel (una sola vez, ~10 minutos)

1. **Que sea un cel solo para pruebas.** Lo ideal: restablécelo de fábrica (Ajustes → Sistema → Restablecer).
   Las apps que probamos a veces son estafas: ese cel no debe tener tu banco, tu WhatsApp ni tus fotos.
2. **Cuenta de Google nueva** (no la tuya personal), solo para entrar a Play Store.
3. **Quita el bloqueo de pantalla:** Ajustes → Seguridad → Bloqueo de pantalla → **Ninguno**.
4. **Activa las opciones de desarrollador:** Ajustes → Acerca del teléfono → toca **7 veces** "Número de
   compilación" hasta que diga "Ya eres desarrollador".
5. En **Ajustes → Sistema → Opciones de desarrollador** prende:
   - **Depuración por USB**
   - **Permanecer activo** (la pantalla no se apaga mientras carga)
   - En Xiaomi también: **Depuración USB (ajustes de seguridad)** e **Instalar vía USB**.
6. **Conéctalo con su cable a la compu de la sala** (la que tiene Claude Code). En el cel sale
   "¿Permitir depuración por USB?": marca **Permitir siempre desde esta computadora** y dale **Permitir**.
7. Volumen bajito y déjalo cargando.

## ¿Ya quedó?

En la oficina, pestaña **Sala**, tu compu muestra **📱 (modelo de tu cel)**. Si dice **📱 falta autorizar**,
desbloquea el cel y acepta el mensaje del paso 6.

La compu instala sola lo que necesita para hablar con el cel (adb) en cuanto se actualiza (unos 30 minutos).
Si tienes prisa, vuelve a correr `INSTALAR_SALA.bat`.

## Cómo se usa

No haces nada: con **📱 Si mi Android está conectado…** prendido en la pestaña **Estilo**, cada video de una app
empieza con la prueba en el cel (unos 10–15 minutos) y luego sigue el equipo como siempre. Si el cel o la compu
están apagados, el video se hace igual, sin la prueba.

## Lo que el robot nunca hace
Escribir datos reales, pagar o aceptar suscripciones, dar permisos de contactos/SMS/ubicación, instalar APKs fuera
de Play Store o completar un retiro. Si una app pide algo de eso, lo anota y termina.
