"""Run one episode on your own computer.

    python run_local.py             # make the episode and post it to YouTube + Instagram
    python run_local.py --preview   # make the video only, post nothing
    python run_local.py --mock      # offline test with the sample story, no keys needed
    python run_local.py --publish   # post the episode a --preview run already built

Keys are read from a file named .env next to this script (copy .env.example to .env).
"""
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Windows consoles default to a code page that cannot print Tamil.
for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except Exception:
        pass


def load_env(path: Path) -> None:
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def preflight(mock: bool) -> list[str]:
    problems = []
    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            problems.append(f"{tool} is not installed or not on PATH. Install FFmpeg and reopen the terminal.")
    from PIL import features
    tamil_on_screen = os.environ.get("ON_SCREEN_TEXT", "tanglish").lower() == "tamil"
    if tamil_on_screen and not features.check("raqm"):
        problems.append(
            "Pillow cannot shape Tamil text on this machine (libraqm missing), so Tamil letters would "
            "render broken. Set ON_SCREEN_TEXT=tanglish in .env, or run inside WSL (Ubuntu) with "
            "sudo apt install ffmpeg libraqm0.")
    if not mock:
        if not os.environ.get("GEMINI_API_KEY"):
            problems.append("GEMINI_API_KEY is missing from .env")
        if "--preview" not in sys.argv:
            if not all(os.environ.get(k) for k in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN")):
                print("[local] YouTube keys missing in .env: the video will not go to YouTube")
            if os.environ.get("INSTAGRAM_AUTOPUBLISH", "").lower() != "true":
                print("[local] INSTAGRAM_AUTOPUBLISH is not true in .env: the Reel will not be posted")
    return problems


def main() -> int:
    env_file = ROOT / ".env"
    if env_file.exists():
        load_env(env_file)
    elif "--mock" not in sys.argv:
        print("No .env file found. Copy .env.example to .env and fill in your keys.")
        return 1

    mock = "--mock" in sys.argv
    if mock:
        os.environ["MOCK"] = "true"
    if "--preview" in sys.argv:
        os.environ["SKIP_UPLOAD"] = "true"

    problems = preflight(mock)
    if problems:
        print("\nCannot start:\n- " + "\n- ".join(problems))
        return 1

    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    from thadayam import main as episode   # imported after .env so settings apply
    if "--publish" in sys.argv:
        return episode.publish_existing()
    code = episode.main()
    out = sorted((ROOT / "out").glob("episode_*/thadayam_*.mp4"))
    if out:
        print(f"\n[local] video: {out[-1]}")
    return code


if __name__ == "__main__":
    sys.exit(main())
