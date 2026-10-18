"""Central settings. Every value can be overridden with an environment variable
(GitHub Actions: repository Variables or Secrets)."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE_FILE = ROOT / "state" / "episodes.json"
SHOUTOUTS_FILE = ROOT / "state" / "shoutouts.txt"
OUT_DIR = ROOT / "out"
FONT_DIR = ROOT / "assets" / "fonts"


def env(name: str, default: str = "") -> str:
    value = os.environ.get(name, "").strip()
    return value if value else default


def env_bool(name: str, default: bool = False) -> bool:
    return env(name, "true" if default else "false").lower() in ("1", "true", "yes", "on")


# ---- Series identity -------------------------------------------------------
SERIES_NAME = env("SERIES_NAME", "மர்ம முடிச்சு")
SERIES_NAME_EN = env("SERIES_NAME_EN", "Marma Mudichu")
INVESTIGATOR = env("INVESTIGATOR_NAME", "நிழல்")
INVESTIGATOR_EN = env("INVESTIGATOR_NAME_EN", "Nizhal")

# On-screen text: "tanglish" (English letters, works on any PC) or "tamil" (Tamil script,
# needs the libraqm text-shaping library). The voice is always Tamil.
ON_SCREEN_TEXT = env("ON_SCREEN_TEXT", "tanglish").lower()
TANGLISH = ON_SCREEN_TEXT != "tamil"
TAGLINE = env("SERIES_TAGLINE", "அடுத்த துப்பறிவாளர் நீங்கள்தான்")

# ---- Video -----------------------------------------------------------------
WIDTH, HEIGHT, FPS = 1080, 1920, 30

# ---- Story engine (Gemini free tier) -----------------------------------------
GEMINI_API_KEY = env("GEMINI_API_KEY")
# Comma-separated list; the first model that answers wins.
GEMINI_MODELS = [m.strip() for m in env(
    "GEMINI_MODEL", "gemini-flash-latest,gemini-3-flash-preview,gemini-flash-lite-latest"
).split(",") if m.strip()]

# ---- Voice: tried in VOICE_ENGINES order; Edge TTS and Google TTS are always the backup ----
VOICE_ENGINES = [e.strip() for e in env("VOICE_ENGINES", "gemini,elevenlabs").split(",") if e.strip()]
# Gemini voice uses GEMINI_API_KEY. Free tier: 10 requests a day PER MODEL, so the models
# are tried in turn when one runs out.
GEMINI_TTS_MODELS = [m.strip() for m in env(
    "GEMINI_TTS_MODEL", "gemini-3.8-flash-tts,gemini-3.1-flash-tts-preview,gemini-2.5-flash-preview-tts"
).split(",") if m.strip()]
GEMINI_TTS_VOICE = env("GEMINI_TTS_VOICE", "Charon")       # deep, calm; try Algenib, Orus, Fenrir
# Empty by default: Gemini sometimes reads a style instruction aloud ("Say in a calm...")
# before the Tamil, even in the short "Say ...:" form. The voice itself sets the tone.
GEMINI_TTS_STYLE = env("GEMINI_TTS_STYLE", "")
ELEVENLABS_API_KEY = env("ELEVENLABS_API_KEY")
# "Brian": deep, calm narrator from the ElevenLabs default voices (works on the free plan).
ELEVENLABS_VOICE_ID = env("ELEVENLABS_VOICE_ID", "nPczCjzI2devNBz1zQrb")
ELEVENLABS_MODEL = env("ELEVENLABS_MODEL", "eleven_multilingual_v2")   # or eleven_v3
ELEVENLABS_STABILITY = float(env("ELEVENLABS_STABILITY", "0.45"))
ELEVENLABS_STYLE = float(env("ELEVENLABS_STYLE", "0.35"))
TTS_VOICE = env("TTS_VOICE", "ta-IN-ValluvarNeural")   # male; ta-IN-PallaviNeural = female
TTS_RATE = env("TTS_RATE", "+0%")
TTS_PITCH = env("TTS_PITCH", "-4Hz")

# ---- Stock video B-roll (free keys): shown the moment its word is spoken ----------
PEXELS_API_KEY = env("PEXELS_API_KEY")
PIXABAY_API_KEY = env("PIXABAY_API_KEY")
BROLL_SECONDS = float(env("BROLL_SECONDS", "3.2"))

# ---- Music and sound effects ---------------------------------------------------
# Drop your own royalty-free tracks into assets/music (mp3/wav) to replace the score
# composed in code; files in assets/sfx named whoosh/impact/thunder/shutter/heartbeat/riser
# replace the matching drawn-in-code effect.
MUSIC_DIR = ROOT / "assets" / "music"
SFX_DIR = ROOT / "assets" / "sfx"
MUSIC_VOLUME = float(env("MUSIC_VOLUME", "0.22"))
SFX_VOLUME = float(env("SFX_VOLUME", "0.8"))

# ---- Images (Pollinations, free) -----------------------------------------
POLLINATIONS_API_KEY = env("POLLINATIONS_API_KEY")       # optional, gives priority access
IMAGE_MODEL = env("IMAGE_MODEL", "flux")
IMAGE_STYLE = env(
    "IMAGE_STYLE",
    "cinematic film noir still, moody low-key lighting, deep shadows, rain-wet atmosphere, "
    "Tamil Nadu, South India, 35mm photography, high detail, vertical composition, "
    "no text, no watermark, no logos",
)

# ---- Publishing -------------------------------------------------------------
YT_CLIENT_ID = env("YT_CLIENT_ID")
YT_CLIENT_SECRET = env("YT_CLIENT_SECRET")
YT_REFRESH_TOKEN = env("YT_REFRESH_TOKEN")
YOUTUBE_PRIVACY = env("YOUTUBE_PRIVACY", "private")      # private | unlisted | public

IG_USER_ID = env("IG_USER_ID")
IG_ACCESS_TOKEN = env("IG_ACCESS_TOKEN")
IG_GRAPH_VERSION = env("IG_GRAPH_VERSION", "v23.0")
INSTAGRAM_AUTOPUBLISH = env_bool("INSTAGRAM_AUTOPUBLISH", False)
# Instagram-Login tokens (IGAA...) cannot upload the file directly; Instagram must fetch it
# from a public link. The video is put on a temporary host that deletes it after 24 hours.
IG_TEMP_HOST = env("IG_TEMP_HOST", "uguu,litterbox,0x0")

# ---- Run modes ---------------------------------------------------------------
MOCK = env_bool("MOCK", False)                 # offline test: sample story, no network
SKIP_UPLOAD = env_bool("SKIP_UPLOAD", False)   # build the video but do not post it
