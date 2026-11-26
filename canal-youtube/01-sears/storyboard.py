"""Storyboard del Expediente #001: ¿Quién MATÓ a Sears?  ·  Estilo "cine" (material real a pantalla completa).

Una entrada por cada frase de narración del guion (líneas "> "), en el mismo orden.
Si una frase lleva varias tarjetas, va una lista; "w" reparte el tiempo entre ellas.
"""
import json
from pathlib import Path

from sb import *  # noqa: F401,F403

AQUI = Path(__file__).parent
_CRED = {}
for _sub in ("fotos", "videos"):
    _c = AQUI / "material" / _sub / "creditos.json"
    if _c.exists():
        _CRED.update(json.loads(_c.read_text(encoding="utf-8")))


def F(stem):
    """Foto descargada (busca la extensión)."""
    for p in sorted((AQUI / "material" / "fotos").glob(stem + ".*")):
        if p.suffix != ".json":
            return f"material/fotos/{p.name}"
    raise SystemExit(f"No encuentro la foto {stem}")


def V(stem):
    return f"material/videos/{stem}.mp4"


def cr(path, extra=""):
    """Crédito corto para la esquina."""
    c = _CRED.get(Path(path).name, {})
    if c.get("fuente") == "Mixkit":
        return " · ".join(p for p in (extra, "Video: Mixkit") if p)
    lic = c.get("licencia") or ""
    lic = "dominio público" if lic.lower() in ("public domain", "no restrictions") else lic
    aut = (c.get("autor") or "").split(",")[0][:40]
    partes = [p for p in (extra, aut if "CC BY" in lic else "", lic, "Wikimedia Commons") if p]
    return " · ".join(partes)[:110]


def P(stem, **k):
    f = F(stem)
    k.setdefault("src", cr(f, k.pop("extra", "")))
    return PHOTO(f, **k)


def M(stem, **k):
    f = V(stem)
    k.setdefault("src", cr(f, k.pop("extra", "")))
    return VIDEO(f, **k)


SOSP = ["LOS BARATOS", "LA PROPIA SEARS", "EL INTERNET", "EDDIE LAMPERT"]


def TAB(reveal, **k):
    return BOARD(reveal, labels=SOSP, label=k.pop("label", "CUATRO SOSPECHOSOS"), **k)


EP = dict(
    label="EXPEDIENTE #001 · SEARS",
    nombre="Expediente-001-Sears",
    guion="01-guion-tecnico.md",
    salida="render",
    estilo="cine",
    voz_motor="azure",
    voz="es-MX-JorgeNeural",
    voz_velocidad="+12%",
    musica_vol=0.35,
    fonetica_azure={
        "Sears, Roebuck and Company": "Sírs Róbuk an Cómpani", "Sears": "Sírs", "Roebuck": "Róbuk",
        "Kmart": "Keimart", "Kenmore": "Kénmor", "DieHard": "Dai Jard", "Allstate": "Olstéit",
        "Dean Witter": "Din Uíter", "Coldwell Banker": "Cóldwel Bánker", "Jeff Bezos": "Yef Bésos",
        "Eddie Lampert": "Édi Lámpert", "Lampert": "Lámpert", "Ayn Rand": "Ein Rand", "Paul Krugman": "Pol Crúgman",
        "Seritage": "Sériteich", "Willis Tower": "Uílis Táuer", "Bloomberg Businessweek": "Blúmberg Bísnes Uík",
        "JC Penney": "Yei Si Péni", "Lands' End": "Lands End", "The Washington Post": "el Uáshington Póust",
        "Goldman Sachs": "Góldman Saks", "Alvah Roebuck": "Álva Róbuk",
    },
    end=END(title="¿QUIÉN <y>MATÓ</y> A…?", sub="SUSCRÍBETE PARA EL PRÓXIMO EXPEDIENTE", bg="material/fotos/sears-perisur.jpg"),
    escenas=[
        # 1 · Gancho
        dict(capitulo="5 tiendas allá, más de 90 aquí", fondo=V("mk-11"), cards=[
            [P("sears-cerrado-cicatriz", text="SEARS, ESTADOS UNIDOS", w=0.8),
             P("sears-cerrado-minnesota", caja=("~5", "TIENDAS SEARS\nQUEDAN EN EE.UU."), color="red")],
            [P("plaza-insurgentes", label="CIUDAD DE MÉXICO", text="PERO EN CUALQUIER PLAZA DE MÉXICO…"),
             P("sears-perisur", caja=("90+", "TIENDAS SEARS\nEN MÉXICO"), color="green")],
            [P("kmart-abandonado", label="1997", text="UNA CADENA GRINGA SE VA DE MÉXICO… DERROTADA"),
             P("carlos-slim", label="1997", text="ESE MISMO AÑO, <y>CARLOS SLIM</y> COMPRA SEARS MÉXICO", pos=(0.5, 0.25)),
             P("kmart-noche", text="Y AÑOS DESPUÉS, ESA CADENA… <r>SE QUEDÓ CON SEARS</r>")],
            SPLIT(F("sears-cerrado-plaza"), F("sears-perisur"), la="ESTADOS UNIDOS", lb="MÉXICO",
                  head="MISMA MARCA. <y>DOS DESTINOS.</y>", src="Wikimedia Commons"),
            P("sears-cerrado-cicatriz", head="¿QUIÉN <r>MATÓ</r>\nA SEARS?", sfx="boom"),
        ]),
        # 2 · Presentación
        dict(capitulo="Expediente #001", fondo=F("catalogo-1902-organo"), cards=[
            [M("mk-42121", text="EL <y>AMAZON</y> DE SU ÉPOCA…"),
             P("catalogo-1902-organo", pos=(0.5, 0.3), text="…CIEN AÑOS ANTES DE AMAZON", extra="Catálogo de Sears, 1902")],
            TAB([False] * 4),
        ]),
        # 3 · Los relojes
        dict(capitulo="La víctima: los relojes que nadie quiso", fondo=F("anuncio-relojes-1888"), cards=[
            [P("richard-sears", mode="frame", side="left", label="1886 · MINNESOTA", text="RICHARD <y>SEARS</y>",
               sub="Agente de una estación de tren"),
             P("anuncio-relojes-1888", mode="frame", side="right", label="ANUNCIO DE 1888",
               text="UN CARGAMENTO DE RELOJES QUE <y>NADIE QUISO</y>")],
            P("alvah-roebuck", mode="frame", side="left", label="EL RELOJERO", text="ALVAH <y>ROEBUCK</y>",
              sub="Así nace Sears, Roebuck and Company"),
            [P("complejo-chicago", pos=(0.5, 0.35), label="CHICAGO", text="SE MUDAN A CHICAGO…", extra="Complejo de Sears en Chicago"),
             P("catalogo-1902-organo", pos=(0.5, 0.2), head="EL <y>CATÁLOGO</y>")],
        ]),
        # 4 · El catálogo
        dict(capitulo="El catálogo que llegaba a todos lados", fondo=F("correo-rural-minnesota"), cards=[
            P("catalogo-1902-organo", pos=(0.5, 0.45), label="CATÁLOGO DE SEARS, 1902",
              text="ROPA · HERRAMIENTAS · JUGUETES · ESTUFAS · MEDICINAS"),
            [P("correo-rural-minnesota", label="CORREO RURAL · MINNESOTA", text="EL CORREO LLEGA HASTA LAS GRANJAS"),
             P("paqueteria-1913", mode="frame", side="left", label="1913", text="Y EMPIEZA A ENTREGAR <y>PAQUETES</y>",
               sub="Para millones de familias, el catálogo era la tienda")],
            P("paqueteria-1913", caja=("+50 M", "CATÁLOGOS AL AÑO\nEN 1916"), extra="Paquetería, 1913"),
            [P("sears-escritorio-1906", mode="frame", side="right", label="1906", text="SEARS SALE A LA <y>BOLSA</y>",
               sub="Con Goldman Sachs: de las primeras grandes salidas a bolsa de una tienda"),
             P("bolsa-nueva-york", bw=True, text="UNA DE LAS PRIMERAS GRANDES SALIDAS A BOLSA DE UNA TIENDA",
               extra="Bolsa de Nueva York (ilustrativa)")],
        ]),
        # 5 · El imperio
        dict(capitulo="Un imperio que vendía hasta casas", fondo=F("casa-sears-greensburg"), cards=[
            [P("casas-catalogo-1918", mode="frame", side="left", label="1908 – 1940",
               text="MÁS DE <y>70 MIL CASAS</y> POR CATÁLOGO"),
             P("casa-sears-greensburg", text="TE LLEGABA EN PIEZAS POR TREN… <y>Y LA ARMABAS</y>")],
            [P("tienda-minneapolis", mode="frame", side="right", label="1925", text="SU PRIMERA <y>TIENDA</y>",
               sub="En la foto: tienda de Sears en Minneapolis (postal)"),
             M("mk-56", text="Y SE VA CON LAS FAMILIAS A LOS <y>SUBURBIOS</y>")],
            [P("kenmore-sears", label="KENMORE", text="ELECTRODOMÉSTICOS"),
             P("craftsman-llaves", label="CRAFTSMAN", text="HERRAMIENTAS"),
             Q("DIEHARD: <y>BATERÍAS</y>\nALLSTATE: <y>SEGUROS (1931)</y>", size=110)],
            P("torre-sears-2006", pos=(0.5, 0.25), label="1973 · CHICAGO", text="LA <y>TORRE SEARS</y>",
              sub="El edificio más alto del mundo durante unos 25 años"),
            M("mk-1755", head="<y>INTOCABLE</y>…", sub="o eso creía"),
        ]),
        # 6 · Latinoamérica
        dict(capitulo="Sears llega a Latinoamérica", fondo=F("habana-1945"), cards=[
            P("habana-1945", label="LA HABANA, CUBA", text="1942: SU PRIMERA TIENDA EN <y>LATINOAMÉRICA</y>",
              extra="La Habana, años 40 (postal)"),
            P("plaza-insurgentes-2", label="27 DE FEBRERO DE 1947", text="SEARS LLEGA A <g>MÉXICO</g>",
              sub="Su primera tienda, en avenida Insurgentes, Ciudad de México", extra="Plaza Insurgentes hoy"),
            LIST(["ESPAÑA: <r>CIERRA EN 1983</r>", "VENEZUELA: VENDIDA, <r>CIERRA EN 1997</r>"],
                 label="NO A TODOS LES FUE IGUAL", src="Wikipedia: Sears in Latin America"),
            M("mk-11", text="MÉXICO IBA A TENER UNA HISTORIA <g>MUY DISTINTA</g>"),
        ]),
        # 7 · Sospechoso #1
        dict(capitulo="Sospechoso #1: los baratos", fondo=F("walmart"), cards=[
            TAB([True, False, False, False], new=0),
            SPLIT(F("walmart"), F("kmart-abandonado"), la="WALMART", lb="KMART", head="<y>1962</y>",
                  col_a="tape", col_b="red", src="Wikimedia Commons"),
            [M("mk-4705", text="MÁS BARATO · EN PUEBLOS CHICOS"),
             M("mk-31346", text="CON ALMACENES Y CAMIONES <y>SÚPER EFICIENTES</y>")],
            P("walmart", caja=("1990", "WALMART LE QUITA\nLA CORONA"), color="tape",
              sub="En los 80, Kmart ya le había ganado en ventas"),
            M("mk-42357", head="EL <r>PRIMER</r> GOLPE"),
        ]),
        # 8 · Sospechoso #2
        dict(capitulo="Sospechoso #2: la propia Sears", fondo=V("mk-18304"), cards=[
            TAB([True, True, False, False], new=1),
            M("mk-18304", head="JUGABA AL <y>BANCO</y>"),
            [M("mk-4809", label="1981", text="COMPRA UNA <y>CASA DE BOLSA</y> Y UNA <y>INMOBILIARIA</y>",
               sub="Dean Witter y Coldwell Banker"),
             P("discover-tarjeta", mode="frame", side="right", label="1985", text="LANZA SU TARJETA:\n<y>DISCOVER</y>")],
            M("mk-42648", caja=("“", "CALCETINES\nY ACCIONES"), size=220),
            M("mk-39854", text="A PRINCIPIOS DE LOS 90 SE DESHACE DE CASI TODO… <r>PERO YA IBA TARDE</r>"),
        ]),
        # 9 · Sospechoso #3
        dict(capitulo="Sospechoso #3: el internet", fondo=F("catalogo-1902-organo"), cards=[
            TAB([True, True, True, False], new=2, label="Y EL ERROR MÁS IRÓNICO DE LA HISTORIA"),
            STAMP("FIN DEL CATÁLOGO", sub="25 DE ENERO DE 1993", cap="113 tiendas cerradas · 50 mil empleos menos",
                  src="History.com"),
            P("caja-amazon", label="JULIO DE 1994", text="NACE <y>AMAZON</y>",
              sub="Vender por internet… y mandar por correo"),
            M("mk-42121", text="EXACTAMENTE LO QUE HACÍA EL CATÁLOGO… <y>PERO EN INTERNET</y>"),
            [M("mk-31155", text="MARCA · EXPERIENCIA · ALMACENES · ENTREGAS"),
             M("mk-42130", text="Y CERRÓ EL CATÁLOGO <r>JUSTO ANTES</r> DE QUE NACIERA AMAZON")],
        ]),
        # 10 · 1997
        dict(capitulo="1997: el año que lo cambió todo", fondo=F("comercial-mexicana"), cards=[
            P("comercial-mexicana", head="<y>1997</y>", sub="Guarda este dato"),
            [P("kmart-abandonado", caja=("5", "TIENDAS ABIERTAS\nDE LAS 50 PROMETIDAS"), color="red",
               sub="Kmart llega a México en 1994, en sociedad con Liverpool"),
             P("comercial-mexicana", label="1997", text="KMART SE VA Y LE VENDE SUS TIENDAS A <y>COMERCIAL MEXICANA</y>")],
            [P("sears-perisur", label="SEARS MÉXICO, 1997", text="UNAS 40 TIENDAS… <r>PERDIENDO DINERO</r>",
               extra="Sears Perisur (foto actual)"),
             P("carlos-slim", pos=(0.5, 0.25), label="28 DE ABRIL DE 1997", text="GRUPO CARSO COMPRA EL <y>85%</y>")],
            SPLIT(F("kmart-noche"), F("carlos-slim"), la="UN GRINGO QUE SE VA", lb="UN MEXICANO QUE LLEGA",
                  pos_b=(0.5, 0.2), col_a="red", col_b="green", src="Wikimedia Commons"),
        ]),
        # 11 · Sospechoso #4
        dict(capitulo="Sospechoso #4: el hombre del cuchillo", fondo=V("mk-18305"), cards=[
            TAB([True, True, True, True], new=3, label="EL HOMBRE DEL CUCHILLO"),
            [M("mk-11", text="CIENTOS DE TIENDAS · MARCAS FAMOSAS · TERRENOS MILLONARIOS"),
             M("mk-18305", head="EDDIE <r>LAMPERT</r>")],
            M("mk-221", text="GOLDMAN SACHS · SU PROPIO <y>FONDO DE INVERSIÓN</y>", extra="Imagen ilustrativa"),
            Q("ADMIRADOR DE <y>AYN RAND</y>", sub="La escritora de la competencia sin límites", size=150),
            [P("kmart-noche", label="2002", text="KMART SE DECLARA EN <r>QUIEBRA</r>"),
             M("mk-18296", text="LAMPERT COMPRA SU DEUDA… <y>Y SE QUEDA CON KMART</y>")],
            [SPLIT(F("kmart-abandonado"), F("torre-sears-2006"), la="KMART", lb="SEARS", head="<y>2005</y>",
                   col_a="red", col_b="tape", src="Wikimedia Commons"),
             M("mk-18305", caja=("$11 MIL M", "KMART\nCOMPRA A SEARS"), size=150)],
        ]),
        # 12 · Lo que pasó después
        dict(capitulo="Lo que pasó después", fondo=V("mk-918"), cards=[
            M("mk-914", head="LO QUE PASÓ <r>DESPUÉS</r>"),
            P("sears-cerrado-cicatriz", label="UNO", text="LAS TIENDAS <r>SE QUEDARON VIEJAS</r>"),
            [M("mk-4809", caja=("40", "UNIDADES PELEANDO\nPOR EL DINERO"), sub="Bloomberg Businessweek, 2013"),
             M("mk-4607", text="ÁREAS QUE DEBÍAN AYUDARSE… <r>SE PELEABAN</r>")],
            Q("SI CADA PARTE NO TIENE NADA EN COMÚN…\n<y>¿PARA QUÉ EXISTE SEARS?</y>", sub="Paul Krugman, economista", size=110),
            [P("lands-end", label="2014", text="SEPARA <y>LANDS' END</y>"),
             P("sears-cerrado-plaza", caja=("230+", "TIENDAS VENDIDAS\nA SERITAGE (2015)"), color="red"),
             Q("¿QUIÉN PRESIDÍA SERITAGE?\n<r>EL MISMO LAMPERT</r>", size=130)],
            P("craftsman-llaves", caja=("$900 M", "VENDE CRAFTSMAN\n(2017)"), color="red"),
            M("mk-18304", text="EL DUEÑO TAMBIÉN ERA <r>EL PRESTAMISTA</r>"),
            BARS([("2007", 53, "tape", "$53 MIL M"), ("2017", 16.7, "red", "$16.7 MIL M")], label="VENTAS DE SEARS AL AÑO",
                 src="Expansión, 2018"),
        ]),
        # 13 · La caída
        dict(capitulo="La caída", fondo=F("sears-cerrado-minnesota"), cards=[
            STAMP("BANCARROTA", sub="15 DE OCTUBRE DE 2018", cap="Le quedaban unas 700 tiendas", src="Axios · Fortune"),
            [M("mk-18296", label="2019", text="SU PROPIO FONDO COMPRA LO QUE QUEDA"),
             Q("LO DEMANDAN POR SACAR\n<r>~$2 MIL MILLONES</r>", sub="Lampert siempre negó haber hecho algo indebido",
               size=120, src="Chain Store Age")],
            Q("DIEHARD: <r>VENDIDA</r>", sub="Diciembre de 2019 · 200 millones de dólares", size=150, src="CBS News"),
            P("willis-tower-2016", pos=(0.5, 0.2), label="2009", text="LA TORRE SEARS AHORA SE LLAMA <y>WILLIS TOWER</y>"),
            [P("kmart-abandonado", caja=("2,000+", "TIENDAS KMART\nLLEGÓ A TENER"), color="tape"),
             P("kmart-noche", text="OCTUBRE DE 2024: CIERRA SU ÚLTIMA TIENDA GRANDE… <r>QUEDA UNA EN MIAMI</r>")],
            P("sears-cerrado-minnesota", head="QUEDAN <r>5</r>", sub="tiendas Sears en Estados Unidos"),
        ]),
        # 14 · México
        dict(capitulo="Mientras tanto, en México…", fondo=F("sears-perisur"), cards=[
            [P("azulejos-1900", bw=True, label="REGRESEMOS A 1997", text="SLIM YA CONOCÍA EL NEGOCIO",
               extra="Casa de los Azulejos, c. 1900"),
             P("sanborns-azulejos", label="DESDE 1985", text="ERA DUEÑO DE <y>SANBORNS</y>")],
            P("carlos-slim", pos=(0.5, 0.25), caja=("<1", "AÑO PARA VOLVER\nA GANAR DINERO"), color="green",
              sub="Según Expansión"),
            P("plaza-insurgentes-2", label="2003", text="COMPRA 6 TIENDAS DE <y>JC PENNEY</y> Y LAS VUELVE SEARS"),
            SPLIT(F("sears-cerrado-plaza"), F("sears-perisur"), la="EL BARCO QUE SE HUNDE", lb="EL QUE YA NO IBA EN ÉL",
                  col_a="red", col_b="green", src="Wikimedia Commons"),
            P("sears-perisur", caja=("+50%", "DE LOS INGRESOS\nDE GRUPO SANBORNS"), color="green",
              sub="Más de 90 tiendas en México"),
        ]),
        # 15 · ¿Por qué aquí sí?
        dict(capitulo="¿Por qué aquí sí funcionó?", fondo=F("plaza-insurgentes"), cards=[
            P("plaza-insurgentes", head="¿POR QUÉ AQUÍ <g>SÍ</g> FUNCIONÓ?"),
            P("carlos-slim", pos=(0.5, 0.25), label="1", text="UN DUEÑO QUE LA <g>OPERÓ</g>, NO QUE LA DESARMÓ"),
            P("plaza-insurgentes-2", label="2", text="LAS PLAZAS: <y>EL PASEO DEL FIN DE SEMANA</y>"),
            [M("mk-43033", label="3", text="EL REFRI, LA LAVADORA, LA PANTALLA… <y>A MESES</y>"),
             M("mk-18264", text="Y LA TARJETA SEARS SE PAGA <y>POR QUINCENA</y>")],
            [P("kenmore-sears", label="4", text="KENMORE Y CRAFTSMAN"),
             P("craftsman-llaves", text="SIGUEN EN EL PISO DE VENTA")],
            M("mk-42136", label="5", text="LAS COMPRAS POR INTERNET LLEGARON <y>MÁS TARDE</y>"),
        ]),
        # 16 · ¿Final feliz?
        dict(capitulo="¿Final feliz?", fondo=F("sears-perisur"), cards=[
            M("mk-42357", head="¿INVENCIBLE?\n<r>TAMPOCO</r>"),
            [Q("XALAPA: CIERRA DESPUÉS DE\n<r>69 AÑOS</r>", sub="Enero de 2026", size=130, src="La Silla Rota"),
             STATS([("96", "tiendas (3er trimestre de 2025)"), ("93", "tiendas (1er trimestre de 2026)")],
                   label="SEARS MÉXICO", color="red", src="Grupo Carso vía Expansión · Merca2.0")],
            M("mk-42123", text="LIVERPOOL · PALACIO DE HIERRO · AMAZON · MERCADO LIBRE",
              sub="Los mismos enemigos que la mataron allá"),
            P("sears-perisur", head="«SEARS NO ESTÁ MUERTA…\n<g>ESTÁ VIVA EN MÉXICO</g>»",
              sub="The Washington Post, septiembre de 2026", size=150),
        ]),
        # 17 · Veredicto
        dict(capitulo="El veredicto", fondo=F("sears-cerrado-cicatriz"), cards=[
            TAB([True] * 4, label="EL VEREDICTO"),
            LIST(["WALMART Y KMART: <y>EL PRIMER GOLPE</y>", "SU AVENTURA COMO BANCO: <y>LA DEBILITÓ</y>",
                  "EL INTERNET: <y>LA AGARRÓ SIN CATÁLOGO</y>"], label="LOS SOSPECHOSOS"),
            TAB([True] * 4, hi=3, hi_label="¿CULPABLE?", label="CUANDO LLEGÓ, SEARS SEGUÍA VIVA", sfx="boom"),
            [SPLIT(F("sears-cerrado-plaza"), F("sears-perisur"), la="OTRO DUEÑO…", lb="…OTRO DESTINO",
                   col_a="red", col_b="green", src="Wikimedia Commons"),
             SPLIT(F("kmart-noche"), F("torre-sears-2006"), la="SE FUE DE MÉXICO EN 1997…", lb="…Y SE QUEDÓ CON SEARS",
                   col_a="red", col_b="tape", src="Wikimedia Commons")],
            P("sears-perisur", text="¿QUIÉN CREES QUE MATÓ A SEARS?\n<y>TE LEO EN LOS COMENTARIOS</y>", size=110),
        ]),
        # 18 · Próximo caso
        dict(capitulo="Próximo expediente", fondo=V("mk-43033"), cards=[
            M("mk-43033", label="PRÓXIMO EXPEDIENTE: #002", text="UNA MARCA QUE MURIÓ ALLÁ… Y AQUÍ SIGUE"),
            P("toper-vintage", mode="frame", side="right", label="SU NOMBRE SE VOLVIÓ PALABRA", text="«<y>TÓPER</y>»",
              sub="Quebró en Estados Unidos en 2024… y se la quedó una empresa mexicana", size=160),
            TITLE("SUSCRÍBETE", sub="Para no perderte el siguiente expediente", size=220, tape=True),
        ]),
    ],
)
