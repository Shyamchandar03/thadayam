"""Instagram Reels publishing (Instagram Graph API, free). Requires a Professional
(Creator/Business) account.

Facebook-Page tokens (EAA...) can send the file straight from the runner (resumable upload).
Instagram-Login tokens (IGAA...) cannot: Instagram answers "The parameter video_url is
required" and must download the video itself. For those, the video is put on a temporary
public host for 24 hours and that link is handed to Instagram."""
import subprocess
import time
from pathlib import Path

import requests

from . import config


def _host() -> str:
    """Tokens from "Instagram API with Instagram Login" start with IG and use
    graph.instagram.com; Facebook-Page tokens (EAA...) use graph.facebook.com."""
    forced = config.env("IG_GRAPH_HOST")
    if forced:
        return forced
    return "graph.instagram.com" if config.IG_ACCESS_TOKEN.startswith("IG") else "graph.facebook.com"


def enabled() -> bool:
    return bool(config.IG_USER_ID and config.IG_ACCESS_TOKEN and config.INSTAGRAM_AUTOPUBLISH)


def _api(path: str) -> str:
    return f"https://{_host()}/{config.IG_GRAPH_VERSION}/{path}"


def _check(r: requests.Response, step: str) -> dict:
    """raise_for_status() hides Instagram's reason; show the real error message instead."""
    try:
        body = r.json()
    except ValueError:
        body = {"raw": r.text[:500]}
    if not r.ok or "error" in body:
        err = body.get("error", body)
        msg = err.get("message", err) if isinstance(err, dict) else err
        raise RuntimeError(f"{step} failed (HTTP {r.status_code}): {msg}")
    return body


# ------------------------------------------------------------ temporary hosting ----
def _litterbox(video: Path) -> str:
    with video.open("rb") as fh:
        r = requests.post("https://litterbox.catbox.moe/resources/internals/api.php", timeout=600,
                          data={"reqtype": "fileupload", "time": "24h"},
                          files={"fileToUpload": (video.name, fh, "video/mp4")})
    url = r.text.strip()
    if not (r.ok and url.startswith("https://")):
        raise RuntimeError(f"HTTP {r.status_code}: {url[:200]}")
    return url


def _uguu(video: Path) -> str:
    """uguu.se: direct links, files up to 128 MB, deleted after 3 hours."""
    with video.open("rb") as fh:
        r = requests.post("https://uguu.se/upload", timeout=600,
                          files={"files[]": (video.name, fh, "video/mp4")})
    body = r.json()
    if not body.get("success"):
        raise RuntimeError(f"HTTP {r.status_code}: {str(body)[:200]}")
    return body["files"][0]["url"]


def _0x0(video: Path) -> str:
    with video.open("rb") as fh:
        r = requests.post("https://0x0.st", timeout=600, data={"expires": "24"},
                          headers={"User-Agent": "thadayam-reel-uploader/1.0"},
                          files={"file": (video.name, fh, "video/mp4")})
    url = r.text.strip()
    if not (r.ok and url.startswith("http")):
        raise RuntimeError(f"HTTP {r.status_code}: {url[:200]}")
    return url


# tmpfiles.org was dropped: its "direct" /dl/ link now redirects to an HTML page, so
# Instagram downloaded a web page and failed with status ERROR.
TEMP_HOSTS = {"litterbox": _litterbox, "uguu": _uguu, "0x0": _0x0}


def _serves_video(url: str) -> str | None:
    """None when the link really returns the MP4 itself; otherwise the reason it does not."""
    r = requests.get(url, timeout=60, stream=True, allow_redirects=True,
                     headers={"Range": "bytes=0-31", "User-Agent": "facebookexternalhit/1.1"})
    head = next(r.iter_content(32), b"")
    r.close()
    kind = r.headers.get("content-type", "")
    if r.status_code not in (200, 206):
        return f"link answered HTTP {r.status_code}"
    if b"ftyp" not in head[:12]:
        return f"link serves {kind or 'unknown content'}, not the video file"
    return None


def _public_url(video: Path) -> str:
    forced = config.env("IG_VIDEO_URL")            # your own hosting, if you have it
    if forced:
        return forced
    errors = []
    for name in [h.strip() for h in config.IG_TEMP_HOST.split(",") if h.strip()]:
        if name not in TEMP_HOSTS:
            continue
        try:
            url = TEMP_HOSTS[name](video)
            problem = _serves_video(url)
            if problem is None:
                print(f"[instagram] video hosted for Instagram at {url} ({name})")
                return url
            errors.append(f"{name}: {problem}")
        except Exception as exc:
            errors.append(f"{name}: {exc}")
        print(f"[instagram] {errors[-1]}", flush=True)
    raise RuntimeError("could not host the video for Instagram: " + "; ".join(errors))


# ------------------------------------------------------------------- publishing ----
def _container_resumable(video: Path, caption: str) -> str | None:
    """Direct upload. Returns None when this token type does not support it."""
    token = config.IG_ACCESS_TOKEN
    r = requests.post(_api(f"{config.IG_USER_ID}/media"), timeout=60, data={
        "media_type": "REELS", "upload_type": "resumable", "caption": caption,
        "share_to_feed": "true", "access_token": token})
    if r.status_code == 400 and "video_url" in r.text:
        return None
    body = _check(r, "create container")
    container = body["id"]
    upload_uri = body.get("uri") or \
        f"https://rupload.facebook.com/ig-api-upload/{config.IG_GRAPH_VERSION}/{container}"
    data = video.read_bytes()
    up = requests.post(upload_uri, data=data, timeout=600, headers={
        "Authorization": f"OAuth {token}", "offset": "0", "file_size": str(len(data))})
    _check(up, "video upload")
    return container


def _container_from_url(video: Path, caption: str) -> str:
    url = _public_url(video)
    r = requests.post(_api(f"{config.IG_USER_ID}/media"), timeout=120, data={
        "media_type": "REELS", "video_url": url, "caption": caption,
        "share_to_feed": "true", "access_token": config.IG_ACCESS_TOKEN})
    return _check(r, "create container")["id"]


def _light_copy(video: Path) -> Path:
    """Instagram re-encodes every Reel anyway; send a ~7 Mbit/s copy instead of the large
    master so the upload is quick and fits the temporary hosts (tmpfiles takes 100 MB)."""
    if video.stat().st_size < 90 * 1024 * 1024:
        return video
    small = video.with_name(video.stem + "_instagram.mp4")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(video), "-c:v", "libx264",
                    "-preset", "medium", "-crf", "24", "-maxrate", "7M", "-bufsize", "14M",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-ar", "48000",
                    "-movflags", "+faststart", str(small)], check=True, capture_output=True)
    print(f"[instagram] upload copy {small.stat().st_size / 1e6:.0f} MB "
          f"(master {video.stat().st_size / 1e6:.0f} MB)", flush=True)
    return small


def publish_reel(video: Path, caption: str) -> str:
    token = config.IG_ACCESS_TOKEN
    caption = caption[:2100]
    video = _light_copy(video)
    container = _container_resumable(video, caption)
    if container is None:
        print("[instagram] this token needs a public video link, hosting it temporarily")
        container = _container_from_url(video, caption)

    for _ in range(60):                      # wait up to ~10 minutes for processing
        s = requests.get(_api(container), timeout=30,
                         params={"fields": "status_code,status", "access_token": token}).json()
        code = s.get("status_code")
        if code == "FINISHED":
            break
        if code in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram processing failed: {s}")
        time.sleep(10)
    else:
        raise RuntimeError("Instagram processing timed out")

    p = requests.post(_api(f"{config.IG_USER_ID}/media_publish"), timeout=60,
                      data={"creation_id": container, "access_token": token})
    media_id = _check(p, "publish")["id"]
    print(f"[instagram] published reel {media_id}")
    return media_id
