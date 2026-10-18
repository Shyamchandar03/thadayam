"""YouTube upload and comment reading (YouTube Data API v3, free quota)."""
from . import config
from .state import clean_name

SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube.force-ssl"]


def enabled() -> bool:
    return bool(config.YT_CLIENT_ID and config.YT_CLIENT_SECRET and config.YT_REFRESH_TOKEN)


def _service():
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    creds = Credentials(
        token=None, refresh_token=config.YT_REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=config.YT_CLIENT_ID, client_secret=config.YT_CLIENT_SECRET, scopes=SCOPES)
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def upload(video_path, title: str, description: str, tags: list[str]) -> str:
    from googleapiclient.http import MediaFileUpload
    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:4900],
            "tags": [t.lstrip("#") for t in tags][:15],
            "categoryId": "24",            # Entertainment
            "defaultLanguage": "ta",
            "defaultAudioLanguage": "ta",
        },
        "status": {
            "privacyStatus": config.YOUTUBE_PRIVACY,
            "selfDeclaredMadeForKids": False,
            "containsSyntheticMedia": True,  # AI voice and AI images: honest disclosure
        },
    }
    media = MediaFileUpload(str(video_path), mimetype="video/mp4", chunksize=8 * 1024 * 1024,
                            resumable=True)
    request = _service().videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    while response is None:
        _, response = request.next_chunk()
    video_id = response["id"]
    print(f"[youtube] uploaded https://youtube.com/shorts/{video_id} ({config.YOUTUBE_PRIVACY})")
    return video_id


def solvers(video_id: str, aliases: list[str], limit: int = 5) -> list[str]:
    """Names of viewers whose comment mentions the culprit. Only names are used, never
    the comment text, so nothing a viewer writes can steer the next script."""
    if not (enabled() and video_id):
        return []
    keys = [a.lower() for a in aliases if a]
    found = []
    try:
        threads = _service().commentThreads()
        req = threads.list(part="snippet", videoId=video_id, maxResults=100,
                           order="time", textFormat="plainText")
        while req is not None and len(found) < limit:
            resp = req.execute()
            for item in reversed(resp.get("items", [])):  # oldest first: first solvers win
                top = item["snippet"]["topLevelComment"]["snippet"]
                text = top.get("textDisplay", "").lower()
                name = clean_name(top.get("authorDisplayName", ""))
                if name and name not in found and any(k in text for k in keys):
                    found.append(name)
            req = threads.list_next(req, resp)
    except Exception as exc:  # comments off, private video, quota ...
        print(f"[youtube] could not read comments: {exc}")
    return found[:limit]
