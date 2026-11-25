"""🔎 Verificaciones que ya se hicieron antes de importar un expediente (en el chat con Claude, con búsquedas).

Al importar el paquete, Ramos arranca con esto para no repetir: lo que ya quedó (✅/⚠️/❌) se queda como propuesta y
solo vuelve a leer las fuentes originales donde dice `pendiente_original`. Nada de esto se aplica sin el OK de
Miguel («Aprobar cambios»).

Cada dato: `contiene` = pedazo de la narración (tal cual) para ubicar la frase; `frase_nueva` = cómo quedaría
("" = se quita); `lista` = número en la «Lista de datos por verificar» del paquete; `url` solo si está en Fuentes.
"""
from __future__ import annotations

ORIGEN = "Verificación anterior en el chat con Claude (con búsquedas)"

PREVIOS: dict[str, list[dict]] = {
    "002-tupperware": [
        {"lista": 9, "dato": "Bancarrota el 17 de septiembre de 2024", "estado": "confirmado",
         "fuente": "SEC, formulario 8-K (tribunal de Delaware)",
         "explicacion": "Confirmado: el 17 de septiembre de 2024 (8-K ante la SEC, tribunal de quiebras de Delaware)."},
        {"lista": 3, "dato": "La planta de Lerma es la misma que la de «Toluca» de Expansión", "estado": "confirmado",
         "fuente": "Expansión", "explicacion": "Es la misma: Parque Industrial Lerma, junto a Toluca.",
         "nota_editor": "Decir siempre «Lerma» (en voz, textos y gráficas)."},
        {"lista": 6, "dato": "Betterware llegó en los noventa", "estado": "confirmado",
         "contiene": "Betterware llegó a México en los noventa", "fuente": "Wikipedia y befra.com",
         "url": "https://en.wikipedia.org/wiki/Betterware",
         "explicacion": "Confirmado: llegó en 1995, así que «en los noventa» está bien."},
        {"lista": 8, "dato": "Ventas de Latinoamérica: 404 y 278 millones", "estado": "corregir",
         "contiene": "de unos 404 millones de dólares en 2022 a unos 278 millones proyectados para 2025",
         "frase_nueva": "de unos 404 millones de dólares en 2022 a unos 270 millones en 2025",
         "fuente": "Xataka, El Ceo y el comunicado de cierre de la compra (2 de junio de 2026)",
         "url": ("https://www.businesswire.com/news/home/20260602629361/en/Betterware-de-Mxico-Completes-Acquisition"
                 "-of-Tupperwares-Operations-in-Latin-America"),
         "pendiente_original": True,
         "explicacion": ("404 M en 2022 está confirmado. Los 278 M eran una proyección (anuncio de enero de 2026); el "
                         "cierre del 2 de junio de 2026 da unos 270 M reales en 2025. Falta confirmarlo leyendo el "
                         "comunicado de cierre."),
         "nota_editor": "Gráfica G11: «$404 M → $270 M» (cuando Ramos lo confirme leyendo el comunicado)."},
        {"lista": 5, "dato": "La isla de Tupper «frente a Costa Rica»", "estado": "corregir",
         "contiene": ("Se divorció, renunció a su nacionalidad estadounidense para no pagar impuestos y se compró una "
                      "isla frente a Costa Rica."),
         "frase_nueva": ("Después se divorció, renunció a su nacionalidad estadounidense para no pagar impuestos y se "
                         "compró una isla en Panamá."),
         "fuente": "Earl Tupper en Wikipedia", "url": "https://en.wikipedia.org/wiki/Earl_Tupper",
         "explicacion": ("La isla era Isla San José, en Panamá (Islas de las Perlas); murió en Costa Rica en 1983. La "
                         "fecha en que renunció a la nacionalidad es incierta (entre los 60 y 1973): por eso «Después»."),
         "nota_editor": "Escena 5: el STOCK «Costa Rica island aerial» ya no va; busca una isla tropical genérica o de Panamá."},
        {"lista": 1, "dato": "Lerma es «la planta más grande del mundo» (escena 1)", "estado": "corregir",
         "contiene": "La planta más grande de Tupperware en el mundo, según la propia marca, no está en Estados Unidos.",
         "frase_nueva": ("Una de las plantas más grandes de Tupperware en el mundo, según la propia marca, no está en "
                         "Estados Unidos."),
         "fuente": "tupperware.com.mx y comunicados del 80 aniversario",
         "explicacion": ("«La más grande del mundo» solo sale en comunicados del 80 aniversario; tupperware.com.mx dice "
                         "«una de las cinco más grandes».")},
        {"lista": 1, "dato": "Lerma es «la planta más grande del mundo» (escena 6)", "estado": "corregir",
         "contiene": "Según la propia marca, hoy es su planta más grande del mundo.",
         "frase_nueva": "Según la propia marca, hoy es una de las plantas más grandes de Tupperware en el mundo.",
         "fuente": "tupperware.com.mx y comunicados del 80 aniversario",
         "explicacion": "Igual que en la escena 1: «una de las plantas más grandes», según la propia marca.",
         "nota_editor": "Escena 6: el texto en pantalla «SU PLANTA MÁS GRANDE DEL MUNDO» cambia a «UNA DE SUS PLANTAS MÁS GRANDES»."},
        {"lista": 4, "dato": "«Unas 200 vendedoras en 1951»", "estado": "no_confirmado",
         "contiene": "En 1951 tenía unas doscientas vendedoras.",
         "frase_nueva": "Empezó con un puñado de vendedoras.",
         "explicacion": "Sin fuente: se suaviza sin cifra («Empezó con un puñado de vendedoras. En pocos años eran miles.»).",
         "nota_editor": "Escena 4: el texto en pantalla «200 → MILES» ya no va (sin cifra: «DE UN PUÑADO A MILES»)."},
        {"lista": 2, "dato": "«Más de 500 autos» según Expansión", "estado": "no_confirmado",
         "contiene": "Según Expansión, la marca ha entregado más de quinientos autos nuevos a vendedoras en México como premio.",
         "frase_nueva": "Este año, la marca dice que entregó quinientos autos a sus líderes de venta en México.",
         "fuente": "Comunicado de Tupperware México (septiembre de 2026)",
         "explicacion": ("No es de Expansión: es un comunicado de Tupperware México de septiembre de 2026 (500 autos a "
                         "Líderes de Unidad Vanguardia durante 2026). Se atribuye a la marca.")},
        {"lista": 7, "dato": "«Alrededor de un millón de asociados» de Betterware", "estado": "no_confirmado",
         "contiene": "con una red de alrededor de un millón de asociados.",
         "frase_nueva": "con una red de cientos de miles de asociados.",
         "fuente": "BeFra, resultados del 3T de 2025",
         "url": "https://www.businesswire.com/news/home/20251023355046/en", "pendiente_original": True,
         "explicacion": ("BeFra reporta 1,099,550 asociados en el 3T de 2025, pero no se pudo ver si incluye a Jafra. "
                         "Mientras se confirma: «cientos de miles de asociados»."),
         "nota_editor": "Gráfica G10: «~1.1 M de asociados» espera a que Ramos lo confirme."},
        {"dato": "Escena 12: «su red de asociados se hizo más chica»", "estado": "corregir",
         "contiene": ("Y la propia Betterware tuvo un 2025 difícil en México: sus ventas cayeron en varios trimestres "
                      "por el consumo débil, y su red de asociados se hizo más chica."),
         "frase_nueva": ("Y la propia Betterware tuvo un 2025 difícil en México: sus ventas cayeron en varios trimestres "
                         "por el consumo débil."),
         "fuente": "BeFra, resultados del 3T de 2025", "url": "https://www.businesswire.com/news/home/20251023355046/en",
         "explicacion": "En el 3T de 2025 la red de asociados creció 2.1 %: esa parte de la frase se quita."},
        {"dato": "Enlace de Expansión en Fuentes (28/09/2026)", "estado": "pendiente", "tipo": "fuente",
         "url": "https://expansion.mx/empresas/2026/09/28/tupperware-venta-catalogo-nuevas-generaciones",
         "pendiente_original": True,
         "explicacion": "Parece que el artículo es del 26/09/2026, no del 28: hay que abrir el enlace y corregirlo en Fuentes."},
    ],
}
