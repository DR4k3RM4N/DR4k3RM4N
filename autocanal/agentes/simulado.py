"""Modo demo de la oficina: simula Play Store, Claude y la publicación (sin APIs ni costos).

La edición de video sí es real (ffmpeg), con voz en silencio.
"""
from __future__ import annotations

import json
import os
import random
import time
from pathlib import Path

from . import buscador, claude, config, playstore

APPS = [
    ("com.demo.cashgato", "Cash Gato: Gana Jugando", (255, 170, 40)),
    ("com.demo.monedasfelices", "Monedas Felices", (80, 200, 120)),
    ("com.demo.pagaya", "PagaYa Encuestas", (90, 140, 255)),
    ("com.demo.caminaygana", "Camina y Gana MX", (240, 90, 120)),
    ("com.demo.ruedapro", "Rueda de la Fortuna Pro", (180, 100, 240)),
    ("com.demo.tikcash", "VideoCash: Gana Viendo", (40, 200, 220)),
    ("com.demo.bloquesoro", "Bloques de Oro", (230, 200, 60)),
]
ANGULOS = ["Probé {t} 7 días: ¿cuánto me pagó?", "{t}: la verdad del pago mínimo",
           "¿{t} paga o es pérdida de tiempo?", "Le pedí el retiro a {t} y pasó esto"]
RAZONES = ["Subió al top de descargas esta semana y las reseñas de 1★ dicen que no paga.",
           "Promete 500 pesos al día; el desarrollador no tiene sitio web.",
           "Mucha gente la está buscando y nadie en YouTube la ha analizado.",
           "Pago mínimo de 50 USD y muchos anuncios: buena para un video de prueba."]


def _pausa(a=3.0, b=6.0):
    time.sleep(random.uniform(a, b))


def _datos(app_id: str):
    for a in APPS:
        if a[0] == app_id:
            return a
    return (app_id, app_id.split(".")[-1].title(), (200, 120, 60))


def ideas(cuantas: int = 5, guia: str = "", pedido: str = "") -> list[dict]:
    _pausa(4, 7)
    if pedido and ("video" in pedido.lower() or "?" in pedido or "por qu" in pedido.lower()):
        app_id, titulo, _ = random.choice(APPS)
        return [{"app_id": app_id, "titulo": titulo, "angulo": f"Tu idea: {pedido}", "por_que": f"💡 Idea tuya: {pedido}",
                 "potencial_vistas": "alto", "personalizada": True, "idea_jefe": pedido}]
    hechas = set(buscador.historial())
    pool = [a for a in APPS if a[0] not in hechas] or APPS
    salida = []
    for app_id, titulo, _ in random.sample(pool, min(cuantas, len(pool))):
        salida.append({"app_id": app_id, "titulo": titulo, "por_que": random.choice(RAZONES),
                       "angulo": random.choice(ANGULOS).format(t=titulo),
                       "potencial_vistas": random.choice(["alto", "alto", "medio", "bajo"])})
    return salida


def ficha(app_id: str) -> dict:
    _, titulo, _ = _datos(app_id)
    return {"appId": app_id, "title": titulo, "summary": "¡Gana dinero real todos los días!",
            "developer": "Lucky Fun Studio", "installs": "1,000,000+", "score": 4.2,
            "developerWebsite": None, "screenshots": ["1", "2", "3"], "icon": "x", "headerImage": None}


def resenas(app_id: str) -> list[dict]:
    return [
        {"usuario": "Laura M.", "estrellas": 1, "fecha": "2026-10-21", "likes": 312, "respuesta_dev": "",
         "texto": "Llegué a los 50 dólares y al querer retirar me pidió ver 200 anuncios más. Nunca pagó."},
        {"usuario": "Jorge R.", "estrellas": 1, "fecha": "2026-10-18", "likes": 128, "respuesta_dev": "",
         "texto": "Al principio subes rápido y luego te dan centavos. Pura publicidad."},
        {"usuario": "Ana P.", "estrellas": 5, "fecha": "2026-10-02", "likes": 3, "respuesta_dev": "",
         "texto": "Muy divertida, todavía no retiro pero se ve bien."},
    ]


def descargar_imagenes(datos: dict, carpeta: Path, max_capturas: int = 8) -> dict:
    from PIL import Image, ImageDraw

    from . import graficos

    _, titulo, color = _datos(datos["appId"])
    img = carpeta / "img"
    img.mkdir(parents=True, exist_ok=True)
    icono = Image.new("RGB", (512, 512), color)
    d = ImageDraw.Draw(icono)
    d.rounded_rectangle([96, 96, 416, 416], 60, fill=(255, 255, 255))
    d.text((150, 170), "$", font=graficos.fuente(220), fill=color)
    icono.save(img / "icono.png")
    caps = []
    textos = ["GANA $500\nAL DÍA", "RETIRA A\nPAYPAL", "¡BONO DE\nBIENVENIDA!"]
    for i, t in enumerate(textos, 1):
        c = Image.new("RGB", (1080, 2340), tuple(max(0, v - 40 * i) for v in color))
        ImageDraw.Draw(c).text((120, 900), t, font=graficos.fuente(140), fill=(255, 255, 255))
        c.save(img / f"captura_{i}.png")
        caps.append(str(img / f"captura_{i}.png"))
    return {"icono": str(img / "icono.png"), "portada": None, "capturas": caps}


COSTO_DEMO = {"ideas": 0.002, "investigar": 0.06, "guion": 0.05, "blog": 0.004}


def _gasto_demo(tarea: str, que: str | None = None) -> None:
    if claude.al_gastar:
        modelo, _ = claude.modelo_de(tarea)
        claude.al_gastar(getattr(claude.contexto, "proyecto", None), getattr(claude.contexto, "etapa", None),
                         modelo, COSTO_DEMO.get(tarea, 0.01) * random.uniform(0.7, 1.3), 0, 0, que or tarea)


def json_estructurado(system, contenido, schema, tarea="guion", effort=None, que=None) -> dict:
    _pausa()
    _gasto_demo(tarea, que)
    props = schema["properties"]
    texto = contenido if isinstance(contenido, str) else json.dumps(contenido[-1], ensure_ascii=False)
    nombre = next((t for _, t, _ in APPS if t in texto), "esta app")
    if "fondo" in props and "lado_icono" in props:
        return {"descripcion": "Fondo degradado morado, texto blanco enorme con borde, icono a la derecha y flecha amarilla (demo).",
                "fondo": "degradado", "color_fondo": "#1B1035", "color_fondo_2": "#7B2CBF", "color_texto": "#FFFFFF",
                "color_borde_texto": "#3C096C", "color_acento": "#FFD60A", "posicion_texto": "izquierda", "mayusculas": True,
                "tamano_texto": "enorme", "lado_icono": "derecha", "lado_cara": "ninguno", "elementos": ["flecha", "marco"],
                "palabras_max": 4, "inclinacion_icono": 8, "consejos_texto": "Preguntas cortas y directas."}
    if "tono" in props and "mejoras_seo" in props:
        return {"resumen": "Escribe directo, de tú, con humor y mucha prueba (demo).", "tono": "cercano", "estructura": ["Gancho", "Qué es", "Prueba", "Veredicto"],
                "longitud_palabras": 1100, "como_empieza": "Con una pregunta", "como_cierra": "Con recomendación", "recursos": ["listas", "tablas"],
                "frases_tipicas": ["No te dejes engañar"], "mejoras_seo": ["Poner la palabra clave en el título", "Agregar preguntas frecuentes"]}
    if "palabras_subtitulo" in props:
        return {"descripcion": "Edición rápida, subtítulos amarillos en mayúsculas de 2 palabras al centro, zoom fuerte (demo).",
                "subtitulos": "grande", "mayusculas_subtitulo": True, "palabras_subtitulo": 2, "posicion_subtitulo": "centro",
                "color_subtitulo": "#FFE600", "color_borde_subtitulo": "#000000", "transicion": "corte", "zoom": "fuerte",
                "barra_progreso": False, "karaoke": True, "color_resaltado": "#22C55E",
                "efectos": ["texto_pop", "golpe_zoom", "sello", "sacudida"], "intensidad_motion": "mucho", "consejos": ["Usa memes y b-roll entre explicaciones", "Cámara en mano en las pruebas"]}
    if "plan" in props:  # Edu: motion graphics por escena
        return {"plan": [
            {"escena": 1, "efectos": [{"tipo": "contador", "palabra": "quinientos", "texto": "$500", "sonido": True},
                                      {"tipo": "golpe_zoom", "palabra": "cierto", "texto": "", "sonido": True}]},
            {"escena": 2, "efectos": [{"tipo": "cintillo", "palabra": "monedas", "texto": "Monedas por todos lados", "sonido": True}]},
            {"escena": 3, "efectos": [{"tipo": "marco_alerta", "palabra": "usuarios", "texto": "", "sonido": True},
                                      {"tipo": "texto_pop", "palabra": "mira", "texto": "¡MIRA ESTO!", "sonido": True}]},
            {"escena": 4, "efectos": [{"tipo": "sacudida", "palabra": "cincuenta", "texto": "", "sonido": True},
                                      {"tipo": "flash", "palabra": "mínimo", "texto": "", "sonido": True}]},
            {"escena": 5, "efectos": [{"tipo": "sello", "palabra": "veredicto", "texto": "NO PAGA", "sonido": True}]},
        ]}
    if "opcion" in props:
        return {"opcion": random.randint(1, 3), "razon": "Se parece más a tus referencias (demo)."}
    if "acciones" in props:
        return {"respuesta": "¡Va, jefe! (modo demo: aquí te contestaría Haiku)", "acciones": []}
    if "veredicto" in props:
        return {"veredicto": random.choice(["senales_de_alerta", "estafa_comprobada", "paga_pero_no_vale_la_pena"]),
                "resumen": "Muchas quejas de que no paga al llegar al mínimo.", "que_promete": "500 pesos al día",
                "como_dice_que_paga": "PayPal", "pago_minimo": "50 USD",
                "senales": [{"senal": "Pago mínimo inalcanzable", "evidencia": "50 USD; usuarios reportan centavos por día",
                             "fuente": "resenas", "gravedad": "alta"},
                            {"senal": "Desarrollador sin sitio web", "evidencia": "Ficha sin web ni dirección",
                             "fuente": "playstore", "gravedad": "media"}],
                "resenas_destacadas": [0, 1], "capturas": [{"indice": 1, "muestra": "pantalla de inicio"}],
                "pendiente_de_probar": ["Intentar retirar", "Contar anuncios en 10 minutos"],
                "alternativas_reales": ["Encuestas con pago mínimo bajo"]}
    if "escenas" in props:
        cambio = "INDICACIONES DEL JEFE" in texto
        return {"titulos": [f"¿{nombre} paga? Lo probé", f"{nombre}: la verdad", f"No descargues {nombre} sin ver esto"],
                "descripcion": "Análisis completo en el blog: {{BLOG_URL}}", "etiquetas": ["apps", "ganar dinero"],
                "texto_miniatura": "¿Te paga?" if not cambio else "¡No paga!",
                "textos_miniatura": ["¿Te paga?", "Lo probé 7 días", "¡Cuidado con esta app!"],
                "sello_miniatura": "CUIDADO" if not cambio else "NO PAGA",
                "escenas": [
                    {"narracion": f"{nombre} promete quinientos pesos al día. ¿Será cierto?", "visual": "titulo", "indice": 0, "texto": "¿500 al día?"},
                    {"narracion": "Así se ve por dentro: monedas y premios por todos lados.", "visual": "captura", "indice": 1, "texto": ""},
                    {"narracion": "Pero mira lo que dicen los usuarios.", "visual": "resena", "indice": 0, "texto": ""},
                    {"narracion": "El pago mínimo es de cincuenta dólares.", "visual": "dato", "indice": 0, "texto": "Pago mínimo: 50 USD"},
                    {"narracion": "Mi veredicto: no pierdas tu tiempo.", "visual": "veredicto", "indice": 0, "texto": "No pierdas tu tiempo"},
                ]}
    return {"titulo": f"¿{nombre} paga o es estafa? Análisis 2026", "slug": "analisis", "meta_descripcion": "Probamos la app.",
            "extracto": "Probamos la app.", "html": "<p>{{video}}</p><h2>Qué es</h2><p>{{captura_1}}</p>",
            "etiquetas": ["apps"], "alt_capturas": ["inicio"], "palabra_clave": f"{nombre} paga o es estafa",
            "palabras_secundarias": [f"{nombre} opiniones", f"{nombre} pago mínimo"], "enlaces_internos": []}


def investigar_web(system, pregunta, tarea="investigar", max_busquedas=5):
    _pausa(5, 8)
    _gasto_demo("investigar", "búsqueda web")
    return "Usuarios en foros reportan que no paga.", [{"titulo": "Reddit: ¿alguien cobró?", "url": "https://reddit.com/r/ejemplo"}]


def publicar(app_id: str, titulo_n: int = 1) -> dict:
    from . import buscador as b

    _pausa(4, 6)
    if os.environ.get("DEMO_BLOG_FALLA") == "1":
        pub = {"blog": None, "blog_error": "WordPress 401: no tienes permisos (demo)",
               "youtube": f"https://youtu.be/demo-{app_id.split('.')[-1]}", "demo": True}
    else:
        pub = {"blog": {"id": 1, "link": f"https://tublog.com/{app_id.split('.')[-1]}", "estado": "draft"},
               "youtube": f"https://youtu.be/demo-{app_id.split('.')[-1]}", "video_en_blog": True, "demo": True}
    (config.SALIDA / app_id / "publicado.json").write_text(json.dumps(pub, indent=2), encoding="utf-8")
    b.marcar_hecha(app_id)
    return pub


def publicar_blog(app_id: str) -> dict:
    _pausa(2, 3)
    pub = json.loads((config.SALIDA / app_id / "publicado.json").read_text(encoding="utf-8"))
    pub.update(blog={"id": 1, "link": f"https://tublog.com/{app_id.split('.')[-1]}", "estado": "draft"}, video_en_blog=True)
    pub.pop("blog_error", None)
    (config.SALIDA / app_id / "publicado.json").write_text(json.dumps(pub, indent=2), encoding="utf-8")
    return pub


def activar() -> None:
    import canal

    os.environ["VOZ_MOTOR"] = "silencio"
    config.HISTORIAL = config.BASE / "historial_demo.json"
    buscador.ideas = ideas
    playstore.ficha, playstore.resenas, playstore.descargar_imagenes = ficha, resenas, descargar_imagenes
    claude.json_estructurado, claude.investigar_web = json_estructurado, investigar_web
    canal.publicar = publicar
    canal.publicar_blog = publicar_blog
