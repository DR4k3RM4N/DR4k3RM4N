# Oficina de TikTok Shop (ala derecha del edificio)

Toño investiga el producto en Google (solo guarda datos y opiniones con su enlace), Sofi escribe el guion con
3 ganchos A/B/C siguiendo las reglas de "guion-tiktok-shop", y Diego arma la lista de tomas para grabarlo con
el celular en una sola sesión. Luego subes tus clips (uno por toma o el video completo): Cris los edita en
vertical con tu voz, textos en zona segura y subtítulos karaoke (Whisper, gratis en el servidor; `WHISPER_MODELO=base`
en `tiktokshop/.env` si el servidor anda corto de memoria) y Vale hace la portada. Todo con Claude Haiku: centavos por producto.

- Corre aparte (`python tienda.py`, puerto 8766, solo en 127.0.0.1) con su propio estado, gasto y tope diario.
- Se entra por el edificio: la oficina de YouTube la conecta en `/tiktok/` con la misma contraseña.
- Configuración propia opcional en `tiktokshop/.env` (por ejemplo `LIMITE_DIARIO=0.5`); lo demás (claves de
  Claude, Serper, Tavily) se toma de `autocanal/.env`.
- Modo demo: `python oficina.py --demo` en `autocanal/` prende también esta oficina en demo.
