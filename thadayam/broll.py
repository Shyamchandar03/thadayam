"""Real stock video B-roll (Pexels first, Pixabay as backup, both free with an API key).
Gemini marks words in the narration ("அரண்மனை" -> "palace"); the editor shows the clip
the moment the voice says that word."""
from pathlib import Path

import requests

from . import config

_used: set = set()                 # never show the same clip twice in one episode


def enabled() -> bool:
    return bool(config.PEXELS_API_KEY or config.PIXABAY_API_KEY) and not config.MOCK


def _pexels(query: str) -> list[tuple[str, str]]:
    r = requests.get("https://api.pexels.com/videos/search", timeout=30,
                     headers={"Authorization": config.PEXELS_API_KEY},
                     params={"query": query, "orientation": "portrait", "size": "medium",
                             "per_page": 15})
    r.raise_for_status()
    found = []
    for v in r.json().get("videos", []):
        if v.get("duration", 0) < 3:
            continue
        files = [f for f in v.get("video_files", []) if f.get("file_type") == "video/mp4"
                 and (f.get("height") or 0) >= 1280 and (f.get("height") or 0) > (f.get("width") or 0)]
        if files:      # smallest file that is still full HD tall
            best = min(files, key=lambda f: abs((f.get("height") or 0) - 1920))
            found.append((f"pexels-{v['id']}", best["link"]))
    return found


def _pixabay(query: str) -> list[tuple[str, str]]:
    r = requests.get("https://pixabay.com/api/videos/", timeout=30,
                     params={"key": config.PIXABAY_API_KEY, "q": query, "safesearch": "true",
                             "per_page": 15})
    r.raise_for_status()
    found = []
    for v in r.json().get("hits", []):
        if v.get("duration", 0) < 3:
            continue
        vids = v.get("videos", {})
        f = vids.get("large") if (vids.get("large") or {}).get("url") else vids.get("medium")
        if f and f.get("url") and (f.get("height") or 0) >= 720:
            portrait = (f.get("height") or 0) > (f.get("width") or 0)
            found.append((portrait, f"pixabay-{v['id']}", f["url"]))
    # Pixabay has no orientation filter: try vertical clips first, landscape ones get cropped
    found.sort(key=lambda x: not x[0])
    return [(clip_id, url) for _, clip_id, url in found]


def fetch(query: str, path: Path) -> bool:
    """Download one fitting portrait clip for the query. False when none was found."""
    if not enabled():
        return False
    sources = []
    if config.PEXELS_API_KEY:
        sources.append(_pexels)
    if config.PIXABAY_API_KEY:
        sources.append(_pixabay)
    for search in sources:
        try:
            for clip_id, url in search(query):
                if clip_id in _used:
                    continue
                r = requests.get(url, timeout=120)
                if r.ok and len(r.content) > 50_000:
                    path.write_bytes(r.content)
                    _used.add(clip_id)
                    print(f"[broll] '{query}': {clip_id}", flush=True)
                    return True
        except Exception as exc:
            print(f"[broll] {search.__name__[1:]} '{query}' failed: {exc}", flush=True)
    print(f"[broll] '{query}': nothing found, keeping the still", flush=True)
    return False
