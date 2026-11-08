"""Agente 7 — YouTube: sube el video, la miniatura y los metadatos."""
from __future__ import annotations

from pathlib import Path

from . import config

SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube"]


def _servicio(puerto: int = 0, abrir_navegador: bool = True):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    token = config.BASE / "youtube_token.json"
    creds = Credentials.from_authorized_user_file(str(token), SCOPES) if token.exists() else None
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:  # la primera vez abre el navegador para que autorices tu canal
            secretos = config.BASE / config.env("YT_CLIENT_SECRETS", "client_secret.json")
            if not secretos.exists():
                raise RuntimeError(f"Falta {secretos.name}: descárgalo de Google Cloud Console y ponlo en {config.BASE}")
            creds = InstalledAppFlow.from_client_secrets_file(str(secretos), SCOPES).run_local_server(
                port=puerto, open_browser=abrir_navegador,
                authorization_prompt_message="Abre este enlace en tu navegador y autoriza tu canal:\n{url}\n")
        token.write_text(creds.to_json(), encoding="utf-8")
    return build("youtube", "v3", credentials=creds)


PRIVACIDADES = ("public", "unlisted", "private")


def subir(video: Path, miniatura: Path | None, titulo: str, descripcion: str, etiquetas: list[str],
          sintetico: bool = True, privacidad: str | None = None) -> str:
    from googleapiclient.http import MediaFileUpload

    yt = _servicio()
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
    req = yt.videos().insert(part="snippet,status", body=cuerpo,
                             media_body=MediaFileUpload(str(video), chunksize=-1, resumable=True))
    resp = None
    while resp is None:
        estado, resp = req.next_chunk()
        if estado:
            print(f"  · subiendo {int(estado.progress() * 100)}%")
    video_id = resp["id"]
    if miniatura and miniatura.exists():
        yt.thumbnails().set(videoId=video_id, media_body=MediaFileUpload(str(miniatura))).execute()
    return f"https://youtu.be/{video_id}"


def privacidad_real(url_video: str) -> str:
    """Cómo quedó de verdad el video. YouTube deja en privado lo que sube una app de Google sin auditar,
    aunque se pida público."""
    video_id = url_video.rstrip("/").split("/")[-1].split("=")[-1]
    datos = _servicio().videos().list(part="status", id=video_id).execute().get("items", [])
    return datos[0]["status"].get("privacyStatus", "") if datos else ""


def agregar_a_descripcion(url_video: str, texto: str) -> None:
    """Agrega una línea al final de la descripción de un video ya subido (por ejemplo, el enlace al blog)."""
    video_id = url_video.rstrip("/").split("/")[-1].split("=")[-1]
    yt = _servicio()
    datos = yt.videos().list(part="snippet", id=video_id).execute().get("items", [])
    if not datos:
        raise RuntimeError("No encontré el video en tu canal.")
    snippet = datos[0]["snippet"]
    if texto in snippet.get("description", ""):
        return
    snippet["description"] = (snippet.get("description", "").rstrip() + "\n\n" + texto)[:5000]
    yt.videos().update(part="snippet", body={"id": video_id, "snippet": {
        k: snippet[k] for k in ("title", "description", "categoryId", "tags", "defaultLanguage") if k in snippet}}).execute()
