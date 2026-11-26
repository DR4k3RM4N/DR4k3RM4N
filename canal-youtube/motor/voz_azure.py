"""Voz neuronal de Azure (Microsoft) para el motor.

Credenciales: archivo canal-youtube/.azure_speech con dos renglones:
  1) la clave (KEY 1 del recurso de Voz)
  2) la región (por ejemplo: eastus)
La clave nunca se imprime.

Muestras para elegir voz:
  python -E -P motor/voz_azure.py muestras 02-tupperware
"""
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

RAIZ = Path(__file__).resolve().parent.parent
_ULTIMA = [0.0]
PAUSA = 3.2  # el plan gratis (F0) admite ~20 peticiones por minuto


def credenciales():
    f = RAIZ / ".azure_speech"
    if not f.exists():
        raise SystemExit("Falta canal-youtube/.azure_speech (renglón 1: clave, renglón 2: región).")
    lines = [ln.strip() for ln in f.read_text(encoding="utf-8-sig").splitlines() if ln.strip()]
    if len(lines) < 2:
        raise SystemExit("El archivo .azure_speech debe tener 2 renglones: la clave y la región.")
    return lines[0], lines[1].lower().replace(" ", "")


def ssml(texto_xml, voz, velocidad="0%"):
    """texto_xml ya viene escapado y puede traer <break/>."""
    loc = "-".join(voz.split("-")[:2])
    return (f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
            f'xmlns:mstts="https://www.w3.org/2001/mstts" xml:lang="{loc}">'
            f'<voice name="{voz}"><prosody rate="{velocidad}">{texto_xml}</prosody></voice></speak>')


def sintetizar(doc_ssml, salida):
    key, region = credenciales()
    url = f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1"
    headers = {"Ocp-Apim-Subscription-Key": key, "Content-Type": "application/ssml+xml",
               "X-Microsoft-OutputFormat": "riff-48khz-16bit-mono-pcm", "User-Agent": "ExpedienteMotor"}
    for intento in range(6):
        espera = PAUSA - (time.time() - _ULTIMA[0])
        if espera > 0:
            time.sleep(espera)
        _ULTIMA[0] = time.time()
        req = urllib.request.Request(url, data=doc_ssml.encode("utf-8"), method="POST", headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                Path(salida).write_bytes(r.read())
                return
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 503) and intento < 5:
                time.sleep(int(e.headers.get("Retry-After") or 10 * (intento + 1)))
                continue
            detalle = e.read()[:300].decode("utf-8", "replace")
            raise SystemExit(f"Azure respondió {e.code}. {detalle}")


def voces(locale="es-MX"):
    key, region = credenciales()
    req = urllib.request.Request(f"https://{region}.tts.speech.microsoft.com/cognitiveservices/voices/list",
                                 headers={"Ocp-Apim-Subscription-Key": key, "User-Agent": "ExpedienteMotor"})
    data = json.loads(urllib.request.urlopen(req, timeout=60).read())
    return [v for v in data if v.get("Locale") == locale]


MUESTRA = ("En México hay una ley que nadie escribió pero todos respetamos: si te llevas comida en el tóper de tu mamá"
           "<break time=\"450ms\"/> regresas el tóper. Ese recipiente se llama así por una marca: Tupperware. "
           "En 1954, Bráuni Uáis se convirtió en la primera mujer en salir en la portada de la revista Bísnes Uík. "
           "Y en 2026, una empresa de Jalisco pagó 250 millones de dólares<break time=\"450ms\"/> nada más por la parte de Latinoamérica.")


def muestras(ep_dir):
    out = Path(ep_dir) / "render" / "muestras-voz"
    out.mkdir(parents=True, exist_ok=True)
    vs = voces("es-MX")
    sys.stdout.reconfigure(encoding="utf-8")
    print(f"{len(vs)} voces de México disponibles:")
    elegidas = []
    for v in vs:
        tipo = v.get("VoiceType", "")
        print(f"  {v['ShortName']:28} {v.get('Gender', ''):7} {tipo}")
        if tipo == "Neural" and "HD" not in v["ShortName"] and "Multilingual" not in v["ShortName"]:
            elegidas.append(v["ShortName"])
    for nombre in elegidas[:6]:
        f = out / f"{nombre}.wav"
        if not f.exists():
            sintetizar(ssml(MUESTRA, nombre), f)
        print("muestra:", f)


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "muestras":
        muestras(sys.argv[2])
    else:
        print(__doc__)
