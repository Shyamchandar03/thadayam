"""Episode history kept in state/episodes.json and committed back by the workflow,
so tomorrow's run knows yesterday's case, its answer and its YouTube video."""
import json
import re
from . import config


def load() -> dict:
    if config.STATE_FILE.exists():
        return json.loads(config.STATE_FILE.read_text(encoding="utf-8"))
    return {"episodes": []}


def save(state: dict) -> None:
    config.STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    config.STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def last_episode(state: dict):
    return state["episodes"][-1] if state["episodes"] else None


def next_number(state: dict) -> int:
    return (state["episodes"][-1]["number"] + 1) if state["episodes"] else 1


def clean_name(name: str) -> str:
    """Keep viewer names short and harmless before they go into a script."""
    name = re.sub(r"https?://\S+", "", name or "").lstrip("@").strip()
    name = re.sub(r"[^\w\s.\-஀-௿]", "", name)
    return name[:24].strip()


def manual_shoutouts() -> list[str]:
    """Names typed into state/shoutouts.txt (one per line) or the SHOUTOUTS input."""
    names = []
    if config.SHOUTOUTS_FILE.exists():
        names += config.SHOUTOUTS_FILE.read_text(encoding="utf-8").splitlines()
    names += config.env("SHOUTOUTS").split(",")
    return [n for n in (clean_name(x) for x in names) if n]


def clear_manual_shoutouts() -> None:
    if config.SHOUTOUTS_FILE.exists():
        config.SHOUTOUTS_FILE.write_text("", encoding="utf-8")
