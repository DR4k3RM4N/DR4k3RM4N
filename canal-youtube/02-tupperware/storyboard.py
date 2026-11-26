"""Storyboard del Expediente #002: ¿Quién MATÓ a Tupperware?  ·  Estilo "cine" (material real a pantalla completa).

Una entrada por cada frase de narración del guion técnico (líneas "> "), en el mismo orden.
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


def F(nombre):
    return f"material/fotos/{nombre}"


def V(stem):
    return f"material/videos/{stem}.mp4"


def cr(path, extra=""):
    """Crédito corto para la esquina."""
    name = Path(path).name
    c = _CRED.get(name) or _CRED.get(Path(path).stem + ".webm") or {}
    if c.get("fuente") == "Mixkit":
        return " · ".join(p for p in (extra, "Video: Mixkit") if p)
    lic = c.get("licencia") or ""
    lic = "dominio público" if lic.lower() in ("public domain", "no restrictions") else lic
    aut = (c.get("autor") or "").split(",")[0][:40]
    partes = [p for p in (extra, aut if "CC BY" in lic else "", lic, "Wikimedia Commons") if p]
    return " · ".join(partes)[:110]


def P(nombre, **k):
    f = F(nombre)
    k.setdefault("src", cr(f, k.pop("extra", "")))
    return PHOTO(f, **k)


def M(stem, **k):
    f = V(stem)
    k.setdefault("src", cr(f, k.pop("extra", "")))
    return VIDEO(f, **k)


EV = [
    (1946, "Primeros recipientes"), (1951, "Fuera de las tiendas"), (1954, "Jubileo y BusinessWeek"),
    (1958, "Corren a Wise; se vende la empresa"), (1966, "Llega a México"),
]
BOARD_LABEL = "TRES SOSPECHOSOS"

EP = dict(
    label="EXPEDIENTE #002 · TUPPERWARE",
    nombre="Expediente-002-Tupperware",
    guion="01-guion-tecnico.md",
    salida="render",
    estilo="cine",
    voz_motor="azure",
    voz="es-MX-JorgeNeural",
    voz_velocidad="+12%",
    musica_vol=0.35,
    fonetica_azure={
        "Brownie Wise": "Bráuni Uáis", "Brownie": "Bráuni", "Earl Tupper": "Erl Táper", "Tupper": "Táper",
        "Kissimmee": "Kisími", "BusinessWeek": "Bísnes Uík", "Party Products": "Párti Pródocts",
        "Hemingway": "Jéminguei", "New Hampshire": "Niu Jámpshir", "Target": "Tárguet", "Kleenex": "Klínex",
        "Fuller": "Fúler",
    },
    end=END(bg="material/fotos/toper-vintage.jpg"),
    escenas=[
        # 1 · Gancho
        dict(capitulo="Si te llevas el tóper, lo regresas", fondo=V("tetera-cocina"), cards=[
            M("tetera-cocina", speed=0.8, text="SI TE LLEVAS COMIDA EN EL TÓPER DE TU MAMÁ…\n<y>REGRESAS EL TÓPER.</y>", size=96),
            P("toper-vintage.jpg", mode="frame", side="right", label="EL TÓPER DE LA CASA",
              text="EL QUE TIENE <y>20 AÑOS</y>…", sub="El que ya no cierra bien. El que tiene tu nombre con plumón."),
            P("anuncio-tupperware.jpg", mode="frame", side="left", label="LA MARCA", text="<y>TUPPERWARE</y>",
              sub="La que le dio nombre al tóper", size=150, extra="Anuncio de los años 50"),
            [STAMP("BANCARROTA", sub="ESTADOS UNIDOS · 2024"),
             M("mk-18305", caja=("$23.5 M", "LO QUE PAGARON\nSUS ACREEDORES"), color="red", size=160, w=1.4,
               sub="más el perdón de unos 63 millones de deuda · Fortune, oct. 2024")],
            M("mk-18304", caja=("$250 M", "PAGÓ UNA EMPRESA\nDE JALISCO"), color="green", size=170,
              sub="…solo por Latinoamérica · Betterware / BeFra, 2026"),
            P("lerma-arco.jpg", label="LERMA, ESTADO DE MÉXICO", text="AQUÍ ESTÁ LA PLANTA MÁS GRANDE DE TUPPERWARE*",
              sub="Y de aquí salen tópers que se venden… en Estados Unidos.   *Según la propia marca"),
            M("mk-42357", head="¿CÓMO SE MUERE UNA MARCA\nQUE ESTÁ <y>EN EL DICCIONARIO</y>?",
              sub="¿Y qué vio México que Estados Unidos no?", size=130),
            P("anuncio-tupperware.jpg", head="¿QUIÉN <r>MATÓ</r>\nA TUPPERWARE?", size=210, sfx="boom",
              extra="Anuncio de los años 50"),
        ]),
        # 2 · Presentación del caso
        dict(capitulo="Expediente #002", fondo=F("anuncio-tupperware.jpg"), cards=[
            [FILE("TUPPERWARE", lines=["1946 – 2024", "CAUSA DE MUERTE:", "POR DETERMINAR"]),
             LIST(["UN INVENTOR QUE <y>RENUNCIÓ A SU NACIONALIDAD</y>", "UNA MUJER <y>BORRADA</y> DE LA HISTORIA",
                   "ERRORES EN LA <y>CONTABILIDAD</y>", "UNA ACCIÓN QUE SE VOLVIÓ <y>MEME</y>", "UN FINAL… <g>EN MÉXICO</g>"],
                  label="ESTE CASO TIENE DE TODO", w=1.6)],
            BOARD([False, False, False], label=BOARD_LABEL),
        ]),
        # 3 · La víctima: el inventor
        dict(capitulo="La víctima: el inventor", fondo=F("planta-quimica-1940s.jpg"), cards=[
            [PROFILE("EARL TUPPER", ["Nace en <y>1907</y> en New Hampshire, Estados Unidos",
                                     "Un inventor con libretas llenas de ideas"],
                     label="EL INVENTOR", src="Wikipedia: Earl Tupper"),
             P("gran-depresion.jpg", bw=True, label="LA GRAN DEPRESIÓN", text="SE QUEDA SIN SU NEGOCIO DE JARDINERÍA",
               pos=(0.5, 0.55), extra="Chicago, 1931 (ilustrativa)")],
            [P("dupont-planta.jpg", mode="frame", side="left", label="DUPONT", text="CONSIGUE TRABAJO EN <y>DUPONT</y>",
               sub="Una de las químicas más grandes del mundo", extra="Planta de DuPont, postal (ilustrativa)"),
             M("pellets-plastico", ss=11, len=7, speed=0.6, label="LO QUE NADIE QUERÍA", text="<y>RESIDUOS DE POLIETILENO</y>",
               sub="Un plástico nuevo que casi nadie sabía usar", src=cr(V("inyeccion-plastico"), "Plástico en bolitas (ilustrativo)"))],
            P("planta-quimica-1940s.jpg", bw=True, label="A EXPERIMENTAR", text="LIGERO · FLEXIBLE · NO SE ROMPE · SE LAVA",
              extra="Laboratorio de los años 40 (ilustrativa)"),
            [Q("<y>1946</y> · TAPA HERMÉTICA", icon="bowl", size=120,
               sub="La presionabas en el centro, sacaba el aire… y la comida duraba más"),
             P("patente-tupper.png", mode="frame", side="right", label="UNA PATENTE DE EARL TUPPER", text="SELLO <y>HERMÉTICO</y>",
               sub="Recipiente con tapa que cierra sin dejar pasar el aire (otorgada en 1954)", extra="Patente US 2,695,645")],
            P("dupont-planta.jpg", head="ERA UN INVENTO GENIAL…\n<r>Y NADIE LO COMPRABA</r>", size=150),
            LIST(["TIENDAS DEPARTAMENTALES", "FERRETERÍAS", "CATÁLOGOS", "<r>SE EMPOLVABA:</r> HABÍA QUE ENSEÑARLO"],
                 label="DÓNDE LO INTENTÓ VENDER", src="Smithsonian · PBS"),
        ]),
        # 4 · Brownie Wise y la fiesta
        dict(capitulo="Brownie Wise y la fiesta", fondo=F("brownie-wise-1954.jpg"), cards=[
            P("brownie-wise-1954.jpg", mode="frame", side="left", label="LA PROTAGONISTA", text="<y>BROWNIE WISE</y>",
              sub="Mamá divorciada. Vendía productos de limpieza en reuniones en casas.", size=130, extra="Business Week, 1954"),
            Q("LO LLENABA DE AGUA, LO TAPABA, LO VOLTEABA…\n<y>Y NO SE CAÍA NI UNA GOTA.</y>", icon="bowl_flip", size=96),
            P("fiesta-sarasota.jpg", mode="frame", side="right", label="UNA FIESTA TUPPERWARE",
              text="VENDÍAN MÁS QUE <y>TODAS LAS TIENDAS</y>", sub="Sarasota, Florida", extra="State Archives of Florida"),
            [TIMELINE(EV, hi=1, label="LA DECISIÓN"),
             P("brownie-wise-1954.jpg", pos=(0.5, 0.22), label="1951", text="TODO SE VENDE EN FIESTAS.\nBROWNIE: <y>VICEPRESIDENTA</y>",
               extra="Business Week, 1954")],
            [P("mapa-kissimmee-1953.jpg", label="KISSIMMEE, FLORIDA", text="LA NUEVA CASA DE TUPPERWARE",
               pos=(0.5, 0.45), extra="Mapa USGS de 1953"),
             STATS([("~200", "vendedoras en 1951"), ("MILES", "pocos años después")], label="KISSIMMEE, FLORIDA",
                   src="PBS · Wikipedia")],
            P("jubileo-1955.jpg", mode="frame", side="left", label="EL JUBILEO", text="TEMA: <y>LA FIEBRE DEL ORO</y>",
              sub="Enterraban premios y las vendedoras escarbaban para encontrarlos. En la foto: el público del Jubileo de 1955.",
              extra="State Archives of Florida"),
            P("brownie-wise-1954.jpg", pos=(0.5, 0.22), label="1954", text="LA PRIMERA MUJER EN LA PORTADA DE <y>BUSINESSWEEK</y>",
              extra="Business Week, 1954"),
            Q("PARA MUCHAS, VENDER TUPPERWARE FUE <y>SU PRIMER NEGOCIO</y>.", size=116,
              sub="Años 50: un ingreso propio, metas propias, premios propios"),
        ]),
        # 5 · La traición
        dict(capitulo="La traición", fondo=F("brownie-wise-1954.jpg"), cards=[
            Q("A <y>EARL TUPPER</y>\nESO NO LE GUSTABA NADA.", size=130),
            LIST(["QUE LA PRENSA LE DIERA <y>EL CRÉDITO</y> A ELLA", "LO QUE GASTABA EN <y>PREMIOS Y EVENTOS</y>",
                  "1957: EL JUBILEO <r>SALE MAL</r> POR EL MAL TIEMPO"], label="LO QUE LE MOLESTABA",
                 src="Wikipedia · Mental Floss"),
            STAMP("DESPEDIDA", sub="1958 · SIN EXPLICACIONES"),
            DOC("BROWNIE WISE", cap="Sin acciones · arreglo por <y>~1 año de sueldo</y> · borrada de los materiales",
                src="National Women's History Museum"),
            [M("mk-18296", caja=("$16 M", "TUPPER VENDE\nLA EMPRESA (1958)"), color="tape", size=170),
             LIST(["SE DIVORCIA", "<y>RENUNCIA A SU NACIONALIDAD</y> PARA NO PAGAR IMPUESTOS",
                   "SE COMPRA UNA ISLA FRENTE A COSTA RICA", "MUERE EN COSTA RICA EN 1983"], label="Y DESPUÉS…",
                  src="Wikipedia: Earl Tupper", w=1.5)],
            Q("LA EMPRESA SOBREVIVIÓ A LOS DOS.\n<y>Y LA FIESTA… SIGUIÓ.</y>", size=130),
        ]),
        # 6 · México
        dict(capitulo="Tupperware llega a México", fondo=F("lerma-iglesia.jpg"), cards=[
            P("anuncio-tupperware.jpg", mode="frame", side="right", label="AÑOS 50 Y 60",
              text="LAS FIESTAS LE DIERON <y>LA VUELTA AL MUNDO</y>", size=104, extra="Anuncio de Tupperware"),
            P("lerma-iglesia.jpg", pos=(0.5, 0.35), label="12 DE MAYO DE 1966", text="LERMA, <g>ESTADO DE MÉXICO</g>",
              sub="Tupperware llega a México e inaugura su planta. Según la marca, hoy es la más grande del mundo.",
              extra="Lerma de Villada"),
            [M("mercado-calvillo", ss=18, len=8, label="MÉXICO", text="LA FIESTA <y>ENCONTRÓ SU CASA</y>",
               extra="Calvillo, Aguascalientes"),
             LIST(["LA <y>VECINA</y> QUE VENDE", "LA <y>TÍA</y> QUE REPARTE EL CATÁLOGO", "LA <y>MAMÁ</y> DEL DINERO EXTRA",
                   "«PÁGAME EN <y>DOS QUINCENAS</y>»"], label="LA FIESTA ENCONTRÓ SU CASA", w=1.4)],
            Q("<y>FULLER</y>\nTAMBIÉN FUE DE TUPPERWARE", sub="Un imperio de venta directa", size=130, src="Bloomberg Línea"),
            M("mk-18263", caja=("$2,670 M", "VENTAS EN 2013\nSU MÁXIMO HISTÓRICO"), color="tape", size=150, sub="Statista"),
            M("mk-42357", head="A PARTIR DE AHÍ…\n<r>TODO FUE PARA ABAJO</r>", size=160),
            BOARD([False, False, False], label=BOARD_LABEL),
        ]),
        # 7 · Sospechoso #1
        dict(capitulo="Sospechoso #1: su propio nombre", fondo=F("toper-vintage.jpg"), cards=[
            BOARD([True, False, False], new=0, label=BOARD_LABEL),
            DEF("táper", "Recipiente de plástico que sirve para guardar alimentos y transportarlos.",
                origin="Viene de la marca Tupperware.", mark="tóper: forma usada sobre todo en México",
                src="RAE · DLE y DPD"),
            Q("SUENA A TRIUNFO.\n<r>ES UNA TRAMPA.</r>", size=150),
            Q("<y>KLEENEX</y> · <y>RESISTOL</y> · <y>TÓPER</y>", size=130,
              sub="Cuando tu marca se vuelve el nombre de la cosa, la gente deja de pedir tu marca"),
            [M("mercado-calvillo", ss=1, len=7, label="UN TÓPER LO ENCUENTRAS DONDE SEA",
               text="EL SÚPER · EL TIANGUIS · LA TIENDA DE <y>TODO A $10</y>", size=92,
               src="NPR · Expansión · " + cr(V("mercado-calvillo"), "video ilustrativo")),
             M("mk-4011", text="COMPETIDORES MÁS BARATOS… <y>MUCHOS HECHOS EN ASIA</y>",
               sub="Tupperware no innovó lo suficiente para explicar su precio")],
            Q("GANÓ LA GUERRA DEL <g>IDIOMA</g>…\nY PERDIÓ LA DEL <r>PRECIO</r>.", size=130),
        ]),
        # 8 · Sospechoso #2
        dict(capitulo="Sospechoso #2: la fiesta", fondo=V("target-tienda"), cards=[
            BOARD([True, True, False], new=1, label=BOARD_LABEL),
            M("mk-4857", text="EL MODELO QUE LA SALVÓ EN 1951… <r>SE VOLVIÓ SU TRAMPA</r>"),
            [LIST(["MÁS MUJERES TRABAJANDO FUERA DE CASA", "MENOS TIEMPO", "INTERNET", "AMAZON", "COMPRAS DESDE EL CELULAR"],
                  label="EL MUNDO CAMBIÓ", w=1.3),
             M("amazon-almacen", label="EL MUNDO CAMBIÓ", text="LAS COMPRAS SE FUERON A <y>INTERNET</y>",
               extra="Almacén de Amazon")],
            M("mk-4607", caja=("-18%", "VENDEDORAS\nEN 2022"), color="red", size=190, sub="NPR"),
            M("mk-918", label="2020", text="NUEVO DIRECTOR: <y>EX PRESIDENTE GLOBAL DE AVON</y>",
              sub="Tecnología para la venta directa: vuelve a ganar dinero… por un tiempo", extra="Imagen ilustrativa"),
            Q("DE FORTALEZA…\n<r>A DEBILIDAD</r>", label="LO QUE RECONOCIÓ EN SU BANCARROTA", size=130,
              sub="Depender de vendedoras en reuniones le costó su estrategia en internet", src="NPR"),
            [M("target-tienda", speed=0.8, label="OCTUBRE DE 2022", text="TUPPERWARE LLEGA A <y>TARGET</y>",
               sub="Una de las cadenas de tiendas más grandes de Estados Unidos", extra="Una tienda Target"),
             TIMELINE([(1951, "Sale de las tiendas"), (2022, "Regresa a las tiendas: Target")], hi=[0, 1],
                      label="71 AÑOS DESPUÉS", src="NPR · Expansión")],
            Q("ERA ADMITIR QUE SU MODELO\n<r>YA NO FUNCIONABA</r>.", sub="Un profesor de marketing", size=118, src="NPR"),
            M("mk-11", head="<r>Y YA ERA MUY TARDE.</r>", size=190),
        ]),
        # 9 · Sospechoso #3
        dict(capitulo="Sospechoso #3: la deuda", fondo=V("mk-18305"), cards=[
            BOARD([True, True, True], new=2, label=BOARD_LABEL),
            BARS([("2013", 2670, "tape", "$2,670 M"), ("2022", 1310, "red", "$1,310 M")], label="VENTAS DE TUPPERWARE",
                 cap="En 2022 y 2023 sus ingresos cayeron más de 16% cada año", src="Statista · Manufacturing Dive"),
            M("mk-18305", caja=("+$700 M", "DE DEUDA"), color="red", size=180, sub="Renegoció sus préstamos 7 veces"),
            [M("mk-39854", label="2023 · EL DESORDEN", text="ERRORES EN <y>IMPUESTOS</y> Y <y>RENTAS</y> · REPORTE ANUAL <r>TARDE</r>"),
             M("mk-914", text="SE FUE DEMASIADA GENTE DE <r>CONTABILIDAD</r>", sub="Bloomberg Law · SEC")],
            M("mk-221", head="«DUDAS SUSTANCIALES»\nDE QUE PUEDA <r>SEGUIR OPERANDO</r>", sub="Abril de 2023 · Fortune", size=130),
            [P("bolsa-nueva-york.jpg", bw=True, label="VERANO 2023", text="LA ACCIÓN SE VUELVE <y>MEME</y>",
               extra="Bolsa de Nueva York (ilustrativa)"),
             NUM("+", 800, "%", color="green", label="VERANO 2023 · LA ACCIÓN, EN DOS SEMANAS",
                 cap="Inversionistas de internet compraron casi por diversión, <y>como un meme</y>", src="Fortune")],
            Q("LOS MISMOS TÓPERS.\n<r>LA MISMA DEUDA.</r>", size=140),
            [P("hemingway-torre.jpg", mode="frame", side="left", label="HEMINGWAY, CAROLINA DEL SUR",
               text="CIERRA SU <r>ÚLTIMA FÁBRICA</r> EN ESTADOS UNIDOS", sub="Junio de 2024 · 148 despidos", extra="Hemingway, SC"),
             M("inyectora-telefonos", label="INYECCIÓN DE PLÁSTICO (ILUSTRATIVO)",
               text="LA PRODUCCIÓN SE VA A <g>LERMA, ESTADO DE MÉXICO</g>"),
             ROUTE(("HEMINGWAY, CAROLINA DEL SUR", "ESTADOS UNIDOS"), ("LERMA, ESTADO DE MÉXICO", "MÉXICO"),
                   over="148 DESPIDOS", cap="La producción se va a México", src="Fox Business · Retail Dive")],
            STAMP("BANCARROTA", sub="SEPTIEMBRE 2024", cap="Con unos <r>812 millones de dólares</r> de deuda",
                  src="Manufacturing Dive"),
            Q("<y>PARTY PRODUCTS</y>", label="LA EMPRESA QUE SE QUEDÓ CON LA MARCA", size=200,
              sub="Traducido: «Productos de Fiesta»", src="Fortune"),
            [TIMELINE([("NOV 2024", "Se cierra la venta a los acreedores"), (2025, "La empresa original se liquida")],
                      hi=[0, 1], src="Wikipedia: Tupperware Brands"),
             P("estacion-tupperware-2024.jpg", label="FLORIDA, 2024", text="ESTACIÓN «TUPPERWARE»",
               sub="El nombre se quedó en el mapa")],
        ]),
        # 10 · México
        dict(capitulo="Mientras tanto, en México…", fondo=V("zocalo-timelapse"), cards=[
            M("zocalo-timelapse", speed=0.5, label="ZÓCALO, CIUDAD DE MÉXICO", text="MIENTRAS TANTO,\nEN <g>MÉXICO</g>…", size=140),
            P("lerma-vias.jpg", label="MÉXICO", text="LA FILIAL MEXICANA <g>NO ENTRÓ EN LA BANCARROTA</g>",
              extra="Lerma de Villada"),
            M("cdmx-catedral", label="MÉXICO", text="NO ERA UN MERCADO MÁS.\n<g>ERA EL MÁS IMPORTANTE.</g>",
              extra="Ciudad de México"),
            BARS([("MÉXICO", 261.7, "green", "$261.7 M"), ("EE.UU.", 132.7, "red", "$132.7 M")],
                 label="VENTAS DE TUPPERWARE EN 2019",
                 cap="Casi el doble aquí que en su propio país (incluye productos de belleza)", src="SEC · 10-K 2019"),
            STATS([("+140", "distribuidores en Latinoamérica"), ("~200,000", "representantes de ventas")],
                  label="LA FIESTA SEGUÍA LLENA", src="Xataka · The Logistics World"),
            M("mk-31346", head="<y>BETTERWARE</y>", sub="El comprador", size=230),
            Q("<y>2001</y> · LUIS CAMPOS COMPRA LA OPERACIÓN DE MÉXICO Y LATINOAMÉRICA", size=104,
              sub="Según se ha contado, le costó todos sus ahorros", src="El Imparcial"),
            [M("guadalajara-catedral", label="JALISCO", text="LA CASA DE <y>BETTERWARE</y>",
               sub="Opera desde El Arenal, Jalisco", extra="Guadalajara"),
             STATS([("7 HA", "centro de distribución en El Arenal, Jalisco"), ("+4 M", "productos a la semana"),
                    ("~1.1 M", "asociados (2025)")], label="BETTERWARE HOY", src="The Logistics World · BeFra 3T 2025")],
            M("mk-42137", text="EL MISMO JUEGO: <y>CATÁLOGO + DISTRIBUIDORAS</y>", sub="En 2022 compró también Jafra"),
            [M("mk-18304", caja=("$250 M", "LA COMPRA\n19 DE ENERO DE 2026"), color="green", size=170,
               sub="$215 M en efectivo (prestado) + $35 M en acciones · Business Wire"),
             Q("MÉXICO + BRASIL\n<y>LERMA</y> Y <y>RÍO DE JANEIRO</y>", label="SE QUEDA CON", size=124)],
            Q("LICENCIA <y>PERPETUA</y>\n<y>EXCLUSIVA</y> · <y>SIN REGALÍAS</y>", size=130,
              sub="Para usar la marca Tupperware en toda Latinoamérica", src="Business Wire, 2026"),
            M("bandera-mexico", text="UNA MARCA MANEJADA POR UNA EMPRESA <g>MEXICANA</g>.\n<y>PARA SIEMPRE.</y>", size=104),
        ]),
        # 11 · Lo que hace Betterware
        dict(capitulo="Lo que Betterware hace con Tupperware", fondo=V("inyeccion-plastico"), cards=[
            M("mk-42133", head="¿Y QUÉ ESTÁ HACIENDO\nCON ELLA?", size=170),
            [M("mk-42123", text="SIN TIENDAS NI SÚPER · <y>100% CATÁLOGO</y>", sub="Expansión, sep. 2026"),
             M("mk-42136", text="VENTAS <y>EN VIVO</y> EN FACEBOOK · CATÁLOGO POR <y>WHATSAPP</y>")],
            M("mk-18264", text="LA FIESTA YA NO ES EN LA SALA.\n<y>ES EN EL CELULAR.</y>"),
            [M("mk-56", caja=("+500", "AUTOS PARA\nVENDEDORAS EN MÉXICO"), color="tape", size=190, sub="Expansión, sep. 2026"),
             P("jubileo-1955.jpg", mode="frame", side="right", label="1955 → HOY",
               text="EL JUBILEO DE BROWNIE WISE SIGUE VIVO… <g>EN MÉXICO</g>", size=84,
               extra="Jubileo de 1955, State Archives of Florida")],
            [M("inyeccion-plastico", ss=6, len=36, label="ASÍ SE INYECTA EL PLÁSTICO (ILUSTRATIVO)",
               text="VARIOS MILLONES DE PIEZAS AL AÑO"),
             DONUT(80, "SE QUEDA EN MÉXICO", "VA A ESTADOS UNIDOS", label="LA PRODUCCIÓN DE LA PLANTA",
                   note="Al anunciarse la compra trabajaba al ~65% de su capacidad.",
                   src="Expansión · The Logistics World, 2026")],
            P("lerma-calle.jpg", label="LERMA, ESTADO DE MÉXICO",
              text="HECHO EN EL <g>ESTADO DE MÉXICO</g>…\nVENDIDO EN <y>ESTADOS UNIDOS</y>."),
        ]),
        # 12 · ¿Final feliz?
        dict(capitulo="¿Tiene final feliz?", fondo=V("mercado-calvillo"), cards=[
            M("mk-11", head="¿TIENE FINAL FELIZ?", sub="Todavía no lo sabemos", size=180),
            [BARS([("2022", 404, "tape", "$404 M"), ("2025*", 278, "red", "$278 M")], label="TUPPERWARE EN LATINOAMÉRICA",
                  cap="*Proyección. Además, Betterware se endeudó para comprarla.", src="Xataka México"),
             STATS([("-9.8%", "1er trimestre"), ("-1.2%", "2º trimestre"), ("-5.3%", "3er trimestre")],
                   label="BETTERWARE MÉXICO EN 2025: VENTAS", color="red", src="BeFra, reportes 2025")],
            M("mk-4857", text="EDAD PROMEDIO DE SUS VENDEDORAS: <y>35 A 40 AÑOS</y>",
              sub="La generación Z es su reto… y lo que más compra son termos, no tópers · Expansión, sep. 2026"),
            Q("LA FIESTA SIGUE.\n<m>PERO YA NO ESTÁ TAN LLENA.</m>", size=140),
        ]),
        # 13 · Veredicto
        dict(capitulo="El veredicto", fondo=F("toper-vintage.jpg"), cards=[
            BOARD([True, True, True], label="EL VEREDICTO"),
            P("toper-vintage.jpg", pos=(0.5, 0.4), text="NO FUE UN MAL PRODUCTO…\n<y>FUE TAN BUENO QUE ESTÁ EN EL DICCIONARIO</y>"),
            LIST(["LAS <y>COPIAS BARATAS</y> QUE SE QUEDARON CON SU NOMBRE", "UNA <y>FIESTA</y> QUE NO QUISO TERMINAR A TIEMPO",
                  "UNA <y>DEUDA</y> QUE CRECIÓ EN MEDIO DEL DESORDEN"], label="LA MATARON TRES COSAS JUNTAS"),
            BOARD([True, True, True], hi=1, hi_label="EL ARMA", label="EL VEREDICTO", sfx="boom"),
            M("mercado-calvillo", ss=18, len=8, text="LA FIESTA NO ESTABA MAL…\n<y>ESTABA EN EL LUGAR EQUIVOCADO</y>",
              sub="En México, esa misma fiesta todavía vale 250 millones de dólares"),
            LIST(["¿EN TU CASA HAY <y>TUPPERWARE ORIGINAL</y> O PURO TÓPER GENÉRICO?",
                  "¿ALGUIEN DE TU FAMILIA <y>VENDIÓ TUPPERWARE</y>?", "¿QUIÉN CREES QUE <r>LO MATÓ</r>?"],
                 label="TE LEO EN LOS COMENTARIOS"),
        ]),
        # 14 · Próximo caso
        dict(capitulo="Próximo expediente", fondo=V("vhs-entra-sale"), cards=[
            M("vhs-entra-sale", label="PRÓXIMO EXPEDIENTE: #003", text="LA TIENDA DE LOS <y>VIERNES DE PELÍCULA</y>",
              sub="Media familia tardaba una hora en escoger qué rentar"),
            Q("¿TUVO <r>NETFLIX</r> EN SUS MANOS?", size=130,
              sub="Murió en Estados Unidos. En 2014, Grupo Elektra compró su operación en México.", src="Business Wire, 2014"),
            TITLE("SUSCRÍBETE", sub="Para no perderte el siguiente caso", size=220, tape=True),
        ]),
    ],
)
