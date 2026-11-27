"""Agente 7 — YouTube: sube el video, la miniatura y los metadatos."""
from __future__ import annotations

from pathlib import Path

from . import config

SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube"]
ANALITICA = "https://www.googleapis.com/auth/yt-analytics.readonly"  # 📊 para que la oficina vea cómo le fue a cada video
SCOPES_NUEVOS = SCOPES + [ANALITICA]


def _credenciales(puerto: int = 0, abrir_navegador: bool = True, canal: str | None = None, autorizar: bool = False,
                  de_nuevo: bool = False):
    """El permiso de un canal. Los permisos viejos se usan con lo que ya tenían (pedir uno nuevo al renovarlos los
    rompería); `de_nuevo` vuelve a pedir permiso, ahora también para ver las estadísticas."""
    from . import canales
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    token = canales.token(canal)
    creds = Credentials.from_authorized_user_file(str(token)) if token.exists() and not de_nuevo else None
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:  # la primera vez abre el navegador para que autorices tu canal
            secretos = canales.secreto(canal)
            if not secretos.exists():
                raise RuntimeError(f"Falta {secretos.name}: descárgalo de Google Cloud Console y ponlo en {secretos.parent}")
            if not autorizar:  # solo se pide permiso desde «canal.py autorizar-youtube», nunca a media publicación
                raise RuntimeError(f"El canal «{canal or 'principal'}» no está autorizado (falta su youtube_token.json).")
            creds = InstalledAppFlow.from_client_secrets_file(str(secretos), SCOPES_NUEVOS).run_local_server(
                port=puerto, open_browser=abrir_navegador,
                authorization_prompt_message="Abre este enlace en tu navegador y autoriza tu canal:\n{url}\n")
        token.write_text(creds.to_json(), encoding="utf-8")
    return creds


def _servicio(puerto: int = 0, abrir_navegador: bool = True, canal: str | None = None, autorizar: bool = False,
              de_nuevo: bool = False):
    """El acceso a YouTube de un canal (cada canal tiene su permiso y su proyecto de Google)."""
    from googleapiclient.discovery import build
    return build("youtube", "v3", credentials=_credenciales(puerto, abrir_navegador, canal, autorizar, de_nuevo),
                 cache_discovery=False)


def tiene_analitica(canal: str | None = None) -> bool:
    """¿El permiso de este canal ya incluye ver estadísticas?"""
    import json
    from . import canales
    try:
        datos = json.loads(canales.token(canal).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return ANALITICA in (datos.get("scopes") or [])


def analitica(canal: str | None = None):
    """El servicio de YouTube Analytics del canal (requiere tiene_analitica)."""
    from googleapiclient.discovery import build
    return build("youtubeAnalytics", "v2", credentials=_credenciales(abrir_navegador=False, canal=canal),
                 cache_discovery=False)


PRIVACIDADES = ("public", "unlisted", "private")


def subir(video: Path, miniatura: Path | None, titulo: str, descripcion: str, etiquetas: list[str],
          sintetico: bool = True, privacidad: str | None = None, publicar_en: str | None = None,
          canal: str | None = None) -> str:
    """`publicar_en`: fecha y hora (ISO, UTC) en que YouTube lo hace público solo; mientras, queda privado."""
    from googleapiclient.http import MediaFileUpload

    yt = _servicio(canal=canal)
    cuerpo = {
        "snippet": {
            "title": titulo[:100], "description": descripcion[:5000],
            "tags": etiquetas[:30], "categoryId": config.env("YT_CATEGORIA", "28"),
            "defaultLanguage": config.CANAL_IDIOMA, "defaultAudioLanguage": config.CANAL_IDIOMA,
        },
        "status": {
            "privacyStatus": privacidad if privacidad in PRIVACIDADES else config.env("YT_PRIVACIDAD", "private"),
            "selfDeclaredMadeForKids": False,
            # Divulgación de contenido alterado o sintético (voz generada por IA) que pide YouTube.
            "containsSyntheticMedia": sintetico,
        },
    }
    if publicar_en:  # programado: YouTube exige que esté privado hasta esa hora
        cuerpo["status"]["privacyStatus"] = "private"
        cuerpo["status"]["publishAt"] = publicar_en
    req = yt.videos().insert(part="snippet,status", body=cuerpo,
                             media_body=MediaFileUpload(str(video), chunksize=-1, resumable=True))
    resp = None
    while resp is None:
        estado, resp = req.next_chunk()
        if estado:
            print(f"  · subiendo {int(estado.progress() * 100)}%")
    video_id = resp["id"]
    return f"https://youtu.be/{video_id}"


def desprogramar(url_video: str, canal: str | None = None) -> None:
    """Saca un video de la agenda: queda privado y ya no se publica solo."""
    video_id = url_video.rstrip("/").rsplit("/", 1)[-1].split("=")[-1]
    yt = _servicio(canal=canal)
    actual = yt.videos().list(part="status", id=video_id).execute().get("items", [])
    if not actual:
        raise RuntimeError("Ese video ya no está en YouTube.")
    estado = actual[0]["status"]
    estado.pop("publishAt", None)
    estado["privacyStatus"] = "private"
    yt.videos().update(part="status", body={"id": video_id, "status": estado}).execute()


def poner_miniatura(url_video: str, miniatura: Path, canal: str | None = None) -> None:
    """Pone la miniatura. YouTube solo lo permite si el canal verificó su teléfono (youtube.com/verify)."""
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload

    video_id = url_video.rstrip("/").rsplit("/", 1)[-1].split("=")[-1]
    try:
        _servicio(canal=canal).thumbnails().set(videoId=video_id, media_body=MediaFileUpload(str(miniatura))).execute()
    except HttpError as exc:
        if exc.resp.status == 403:
            raise RuntimeError("YouTube no dejó poner la miniatura: tu canal necesita verificar tu teléfono para usar "
                               "miniaturas propias (youtube.com/verify).") from exc
        raise


def privacidad_real(url_video: str, canal: str | None = None) -> str:
    """Cómo quedó de verdad el video. YouTube deja en privado lo que sube una app de Google sin auditar,
    aunque se pida público."""
    video_id = url_video.rstrip("/").split("/")[-1].split("=")[-1]
    datos = _servicio(canal=canal).videos().list(part="status", id=video_id).execute().get("items", [])
    return datos[0]["status"].get("privacyStatus", "") if datos else ""


def agregar_a_descripcion(url_video: str, texto: str, canal: str | None = None) -> None:
    """Agrega una línea al final de la descripción de un video ya subido (por ejemplo, el enlace al blog)."""
    video_id = url_video.rstrip("/").split("/")[-1].split("=")[-1]
    yt = _servicio(canal=canal)
    datos = yt.videos().list(part="snippet", id=video_id).execute().get("items", [])
    if not datos:
        raise RuntimeError("No encontré el video en tu canal.")
    snippet = datos[0]["snippet"]
    if texto in snippet.get("description", ""):
        return
    snippet["description"] = (snippet.get("description", "").rstrip() + "\n\n" + texto)[:5000]
    yt.videos().update(part="snippet", body={"id": video_id, "snippet": {
        k: snippet[k] for k in ("title", "description", "categoryId", "tags", "defaultLanguage") if k in snippet}}).execute()


def videos_del_canal(canal: str | None = None, n: int = 50) -> list[dict]:
    """Los videos del canal (también privados y programados): id, título, estado y fecha."""
    yt = _servicio(canal=canal)
    ch = yt.channels().list(part="contentDetails", mine=True).execute().get("items", [])
    if not ch:
        return []
    lista = ch[0]["contentDetails"]["relatedPlaylists"]["uploads"]
    ids, pagina = [], None
    while len(ids) < n:
        r = yt.playlistItems().list(part="contentDetails", playlistId=lista, maxResults=50, pageToken=pagina).execute()
        ids += [x["contentDetails"]["videoId"] for x in r.get("items", [])]
        pagina = r.get("nextPageToken")
        if not pagina:
            break
    salida = []
    for i in range(0, len(ids[:n]), 50):
        r = yt.videos().list(part="snippet,status", id=",".join(ids[i:i + 50])).execute()
        for v in r.get("items", []):
            salida.append({"id": v["id"], "titulo": v["snippet"]["title"], "estado": v["status"].get("privacyStatus"),
                           "programado": v["status"].get("publishAt", ""), "fecha": v["snippet"].get("publishedAt", "")[:10],
                           "url": f"https://youtu.be/{v['id']}"})
    return salida


def borrar_video(url_video: str, canal: str | None = None) -> None:
    """🗑️ Borra un video de tu canal (no se puede deshacer). Solo cuando tú lo pides."""
    video_id = url_video.rstrip("/").split("/")[-1].split("=")[-1]
    _servicio(canal=canal).videos().delete(id=video_id).execute()


def editar_video(url_video: str, titulo: str | None = None, descripcion: str | None = None,
                 etiquetas: list[str] | None = None, canal: str | None = None) -> None:
    """Cambia título, descripción o etiquetas de un video ya subido (lo demás se queda igual)."""
    video_id = url_video.rstrip("/").split("/")[-1].split("=")[-1]
    yt = _servicio(canal=canal)
    datos = yt.videos().list(part="snippet", id=video_id).execute().get("items", [])
    if not datos:
        raise RuntimeError("No encontré ese video en tu canal.")
    sn = datos[0]["snippet"]
    if titulo:
        sn["title"] = titulo[:100]
    if descripcion is not None and descripcion.strip():
        sn["description"] = descripcion[:5000]
    if etiquetas:
        sn["tags"] = etiquetas[:30]
    yt.videos().update(part="snippet", body={"id": video_id, "snippet": {
        k: sn[k] for k in ("title", "description", "categoryId", "tags", "defaultLanguage") if k in sn}}).execute()
