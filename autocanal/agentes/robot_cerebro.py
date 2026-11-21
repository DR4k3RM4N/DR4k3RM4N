"""📱 El cerebro del robot probador: tu compu le manda la foto de la pantalla del cel (y la lista de botones) y aquí
Claude decide UNA acción. La compu la ejecuta, toma otra foto y vuelve a preguntar.

Así la compu no necesita a Claude Code: solo adb y esta plática con la oficina (tu plan de Claude; con la API,
Haiku). Las reglas de seguridad son las mismas de siempre (nada de datos reales, pagos, préstamos ni permisos).
"""
from __future__ import annotations

from . import claude

ACCIONES = ["tocar", "tocar_texto", "escribir", "deslizar", "atras", "inicio", "esperar", "tienda", "buscar_tienda",
            "abrir", "anuncio", "nota", "guardar_deseo", "terminar"]

SCHEMA = {
    "type": "object",
    "properties": {
        "veo": {"type": "string", "description": "Qué hay en la pantalla, en una frase"},
        "por_que": {"type": "string", "description": "Qué vas a hacer y por qué, en una frase (se muestra en la oficina)"},
        "accion": {"type": "string", "enum": ACCIONES},
        "args": {"type": "array", "items": {"type": "string"},
                 "description": "tocar: [número de la lista] o [x, y] · tocar_texto: [texto] · escribir: [texto] · "
                                "deslizar: [abajo|arriba|izquierda|derecha] · esperar: [segundos] · tienda/abrir: "
                                "[paquete] · buscar_tienda: [nombre] · anuncio: [app anunciada, qué promete] · nota: "
                                "[texto] · guardar_deseo: [nombre, qué promete] · terminar: [resumen de 3-5 frases] · "
                                "atras/inicio: []"},
    },
    "required": ["veo", "por_que", "accion", "args"],
    "additionalProperties": False,
}

SISTEMA = """Eres el probador de apps del canal "Apps que sí pagan". Manejas un celular Android de PRUEBAS: cada turno
ves la foto de la pantalla y la lista numerada de botones/textos, y eliges UNA acción. La pantalla se está grabando
para un video de YouTube: muévete como una persona curiosa (sin prisas raras) que quiere saber si la app paga.

MISIÓN (en orden):
0. Presenta la app: su página de Play Store unos 10-15 s (nombre, estrellas, descargas), baja una vez para que se
   vean capturas y descripción, y regresa arriba. Anota con `nota` "FICHA: nombre, estrellas, descargas, qué promete".
1. Si no está instalada, "Instalar" desde esa página y espera (esperar 8-10) hasta que diga "Abrir"; ábrela.
2. Úsala unos {minutos} minutos: haz lo que pida para "ganar" (ver videos, juegos, ruletas, encuestas sencillas),
   recoge recompensas y ve los anuncios cuando los ofrezca (los anuncios son lo que más importa).
3. CADA anuncio: `anuncio` [app o producto, qué promete]. Si es de OTRA app que promete dinero, tócale para ver cuál es
   y en Play Store/página usa `guardar_deseo` [nombre, promesa]; NO la instales; regresa (atras) a la app de hoy.
   Si no es de dinero, ciérralo (X, "Cerrar", o atras; a veces hay que esperar unos segundos).
4. `nota` con lo importante: saldo, cuánto promete pagar, cada cuánto sale un anuncio.
5. Al final busca retirar/cobrar/canjear: `nota` con el pago mínimo y lo que pide. NO completes un retiro.
6. `terminar` [resumen de lo que viste en 3-5 frases].

REGLAS DE SEGURIDAD (no se negocian):
- NUNCA escribas datos reales (nombres, correos, teléfonos, datos bancarios o de PayPal). Si un paso los exige, `nota`
  y sigue por otro lado o termina.
- NUNCA pagues, compres, ni aceptes suscripciones o pruebas gratis. NUNCA pidas préstamos ni llenes solicitudes.
- Permisos: niega contactos, SMS, llamadas, ubicación y archivos ("No permitir"/"Denegar").
- NUNCA instales nada fuera de Play Store, ni las apps de los anuncios.
- Si pide iniciar sesión con Google/Facebook busca "invitado"/"saltar"; si no hay, `nota` y termina.
- Captcha o verificación de cara: `nota` y termina.
- Si llevas 3 intentos sin que algo cambie, haz otra cosa (atras, deslizar, otra sección).
- Prefiere `tocar` con el número de la lista; si lo que quieres no está en la lista (juegos, anuncios), usa
  coordenadas [x, y] de la foto en píxeles REALES del cel (te digo su tamaño)."""


def decidir(datos: dict) -> dict:
    """datos: app, paquete, minutos, transcurrido (min), ya_instalada, ancho, alto, pantalla (jpg base64),
    elementos (texto), historial [{accion, args, resultado, por_que}], notas (resumen)."""
    minutos = int(datos.get("minutos") or 8)
    trans = float(datos.get("transcurrido") or 0)
    historial = datos.get("historial") or []
    texto = (f"APP DE HOY: {datos.get('app')} · paquete de Play Store: {datos.get('paquete') or '(no tiene: búscala por nombre)'}"
             + ("\nOJO: el jefe YA la tiene instalada: preséntala en Play Store (dirá «Abrir») y ábrela; NO la desinstales."
                if datos.get("ya_instalada") else "")
             + f"\nLLEVAS {trans:.1f} min de {minutos}"
             + (" — YA CASI: ve al retiro/cobrar, anota el pago mínimo y termina." if trans >= minutos - 1 else "")
             + (" — SE ACABÓ EL TIEMPO: termina ya." if trans >= minutos + 3 else "")
             + f"\nCELULAR: {datos.get('ancho') or '?'}x{datos.get('alto') or '?'} px (coordenadas para tocar)"
             + f"\nLO QUE LLEVAS ANOTADO: {datos.get('notas') or '(nada)'}"
             + "\nÚLTIMAS ACCIONES (de la más vieja a la más nueva):\n"
             + ("\n".join(f"- {h.get('accion')} {h.get('args') or ''} → {h.get('resultado', '')[:120]}"
                          for h in historial[-14:]) or "(ninguna: empieza)")
             + f"\n\nBOTONES Y TEXTOS DE LA PANTALLA:\n{(datos.get('elementos') or '')[:5000]}")
    contenido = [{"type": "text", "text": texto}]
    if datos.get("pantalla"):
        contenido.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                                      "data": datos["pantalla"]}})
    contenido.append({"type": "text", "text": "¿Qué haces ahora? Una sola acción."})
    r = claude.json_estructurado(SISTEMA.format(minutos=minutos), contenido, SCHEMA, tarea="robot",
                                 que="robot: siguiente paso")
    if r["accion"] not in ACCIONES:
        r["accion"] = "esperar"
    return r
