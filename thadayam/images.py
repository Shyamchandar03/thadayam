"""Scene stills and suspect photos: free AI images from Pollinations, graded to one
consistent noir look. If the image service is down, a designed noir backdrop (or a backlit
shadow figure for suspects) is used instead, so the daily run never fails because
of images."""
import io
import random
import re
import time
import urllib.parse
from pathlib import Path

import numpy as np
import requests
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from . import config

W, H = config.WIDTH, config.HEIGHT
# Accent glow per scene type for the fallback backdrop (R, G, B).
ACCENTS = {"reveal": (60, 140, 120), "hook": (170, 30, 30), "case": (40, 70, 140),
           "suspect": (120, 80, 30), "clue": (190, 140, 40), "cta": (150, 30, 40)}


# Without a key Pollinations allows 1 image every 45 s per IP, so a full episode
# (~12 images) needs about 10 minutes. A free key from enter.pollinations.ai removes the wait.
IMAGE_BUDGET = float(config.env("IMAGE_BUDGET_SECONDS", "1080"))  # all AI images together
FREE_GAP = 46.0
_start = time.monotonic()
_last_request = 0.0
_failures_in_a_row = 0

PORTRAIT_STYLE = config.env(
    "PORTRAIT_STYLE",
    "photorealistic portrait photograph, head and shoulders, looking at the camera, "
    "low-key film noir side lighting, dark background, Canon EOS R5, 85mm f1.4, sharp focus, "
    "natural skin texture with pores, documentary photo, not illustration, not cartoon, "
    "not 3d render, no text, no watermark")


def _time_left() -> float:
    return IMAGE_BUDGET - (time.monotonic() - _start)


def _wait_turn() -> None:
    """Keep to the free limit instead of being refused (refusals used to end in drawings)."""
    if config.POLLINATIONS_API_KEY:
        return
    wait = FREE_GAP - (time.monotonic() - _last_request)
    if wait > 0:
        print(f"[images] waiting {wait:.0f}s for the free image limit", flush=True)
        time.sleep(wait)


def _fetch(prompt: str, seed: int, size: tuple[int, int] = (W, H),
           style: str | None = None) -> Image.Image | None:
    global _last_request
    full = f"{prompt}, {style or config.IMAGE_STYLE}"
    q = urllib.parse.quote(full, safe="")
    params = {"width": size[0], "height": size[1], "seed": seed, "nologo": "true",
              "model": config.IMAGE_MODEL}
    headers = {}
    if config.POLLINATIONS_API_KEY:
        url = f"https://gen.pollinations.ai/image/{q}"
        headers["Authorization"] = f"Bearer {config.POLLINATIONS_API_KEY}"
        params["key"] = config.POLLINATIONS_API_KEY
    else:
        url = f"https://image.pollinations.ai/prompt/{q}"
    for attempt in range(3):
        if _time_left() < FREE_GAP + 30:
            print("[images] time budget used up", flush=True)
            return None
        _wait_turn()
        try:
            _last_request = time.monotonic()
            r = requests.get(url, params=params, headers=headers, timeout=min(120, _time_left()))
            if r.ok and r.headers.get("content-type", "").startswith("image"):
                img = Image.open(io.BytesIO(r.content)).convert("RGB")
                if img.width >= 400:
                    # the free endpoint can ignore nologo: cut off the watermark strip
                    return img.crop((0, 0, img.width, int(img.height * 0.93)))
            retry = re.search(r"[Rr]etry after (\d+)", r.text)
            print(f"[images] HTTP {r.status_code} {r.text[:80]}", flush=True)
            if retry:
                time.sleep(int(retry.group(1)) + 2)
        except Exception as exc:
            print(f"[images] request failed: {exc}", flush=True)
    return None


def _try_fetch(prompt: str, seed: int, **kw) -> Image.Image | None:
    """_fetch, but give up for the rest of the run once the service looks down."""
    global _failures_in_a_row
    if config.MOCK or _failures_in_a_row >= 3:
        return None
    img = _fetch(prompt, seed, **kw)
    _failures_in_a_row = 0 if img is not None else _failures_in_a_row + 1
    return img


def _cover(img: Image.Image, w: int = W, h: int = H) -> Image.Image:
    """Scale and centre-crop to fill w x h."""
    scale = max(w / img.width, h / img.height)
    img = img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)
    left, top = (img.width - w) // 2, (img.height - h) // 2
    return img.crop((left, top, left + w, top + h))


def _vignette_and_grain(img: Image.Image, seed: int) -> Image.Image:
    arr = np.asarray(img).astype(np.float32)
    yy, xx = np.mgrid[0:H, 0:W]
    d = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 1.6)) ** 2)
    mask = np.clip(1.15 - 0.55 * d ** 1.6, 0.25, 1.0)[..., None]
    arr *= mask
    rng = np.random.default_rng(seed)
    arr += rng.normal(0, 7, arr.shape[:2])[..., None]
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def grade(img: Image.Image, seed: int) -> Image.Image:
    """Consistent series look: muted colour, punchy contrast, cool shadows, vignette, grain."""
    img = _cover(img)
    img = ImageEnhance.Color(img).enhance(0.55)
    img = ImageEnhance.Contrast(img).enhance(1.18)
    img = ImageEnhance.Brightness(img).enhance(0.88)
    arr = np.asarray(img).astype(np.float32)
    lum = arr.mean(axis=2, keepdims=True) / 255.0
    tint = np.array([-8, 2, 14], dtype=np.float32) * (1 - lum) + np.array([10, 4, -6], dtype=np.float32) * lum
    img = Image.fromarray(np.clip(arr + tint, 0, 255).astype(np.uint8))
    return _vignette_and_grain(img, seed)


def backdrop(scene_type: str, seed: int) -> Image.Image:
    """Drawn noir backdrop: dark gradient, accent glow, light beam, rain streaks."""
    rnd = random.Random(seed)
    acc = np.array(ACCENTS.get(scene_type, (90, 90, 120)), dtype=np.float32)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    base = np.zeros((H, W, 3), np.float32) + np.array([10, 11, 16], np.float32)
    cx, cy = rnd.uniform(0.25, 0.75) * W, rnd.uniform(0.2, 0.45) * H
    glow = np.exp(-(((xx - cx) / (W * 0.55)) ** 2 + ((yy - cy) / (H * 0.35)) ** 2))[..., None]
    base += glow * acc * 0.9
    # diagonal light beam
    angle = rnd.uniform(-0.35, 0.35)
    dist = np.abs((xx - W / 2) * np.cos(angle) + (yy - H * 0.1) * np.sin(angle))
    base += (np.exp(-(dist / 120) ** 2) * (1 - yy / H) * 38)[..., None]
    img = Image.fromarray(np.clip(base, 0, 255).astype(np.uint8))
    rain = Image.new("L", (W, H), 0)
    px = rain.load()
    for _ in range(900):
        x, y, ln = rnd.randrange(W), rnd.randrange(H), rnd.randrange(20, 70)
        for k in range(ln):
            yk, xk = y + k, x + k // 6
            if 0 <= yk < H and 0 <= xk < W:
                px[xk, yk] = 70
    rain = rain.filter(ImageFilter.GaussianBlur(1))
    img = Image.composite(Image.new("RGB", (W, H), (190, 200, 215)), img, rain.point(lambda v: v // 3))
    return _vignette_and_grain(img, seed)


def make_scene_image(scene: dict, index: int, episode: int, path: Path) -> bool:
    """Returns True when an AI image was used, False when the drawn backdrop was."""
    seed = episode * 100 + index
    img = _try_fetch(scene["image_prompt"], seed)
    print(f"[images] scene {index + 1}: {'AI image' if img is not None else 'drawn backdrop'}", flush=True)
    if img is not None:
        grade(img, seed).save(path, quality=92)
        return True
    backdrop(scene.get("type", ""), seed).save(path, quality=92)
    return False


# ---------------------------------------------------------------- suspects ----------
CARD_W, CARD_H = 600, 720            # photo area inside the case-file card


def gender_of(person: dict) -> str:
    return "female" if str(person.get("gender", "")).lower().startswith(("f", "w", "g")) else "male"


def _silhouette(gender: str, seed: int) -> Image.Image:
    """Last-resort case-file photo when no AI portrait could be made: a backlit shadow
    figure (no drawn face, so it never looks like a cartoon). Long hair for a woman."""
    rnd = random.Random(seed)
    w, h = CARD_W, CARD_H
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    cx = w * rnd.uniform(0.45, 0.55)
    glow = np.exp(-(((xx - cx) / (w * 0.55)) ** 2 + ((yy - h * 0.3) / (h * 0.45)) ** 2))
    base = np.zeros((h, w, 3), np.float32) + np.array([14, 15, 20], np.float32)
    base += glow[..., None] * np.array([150, 120, 85], np.float32)
    img = Image.fromarray(np.clip(base, 0, 255).astype(np.uint8))

    fig = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(fig)
    hx, hy, hw, hh = int(cx), int(h * 0.36), 100, 128
    if gender == "female":
        d.rounded_rectangle((hx - hw - 30, hy - hh + 10, hx + hw + 30, hy + hh + 190), radius=120, fill=255)
    d.rectangle((hx - 50, hy + hh - 40, hx + 50, hy + hh + 70), fill=255)
    d.ellipse((hx - 280, hy + hh + 40, hx + 280, h + 360), fill=255)
    d.ellipse((hx - hw, hy - hh, hx + hw, hy + hh), fill=255)
    fig = fig.filter(ImageFilter.GaussianBlur(2.5))
    img = Image.composite(Image.new("RGB", (w, h), (8, 8, 10)), img, fig)
    rng = np.random.default_rng(seed)                      # film grain, like a real print
    arr = np.asarray(img, np.float32) + rng.normal(0, 9, (h, w))[..., None]
    return Image.fromarray(arr.clip(0, 255).astype(np.uint8))


def _card(photo: Image.Image, name: str, number: int, stamp_text: str | None = None,
          stamp_colour: tuple = (205, 30, 30)) -> Image.Image:
    """Polaroid-style case-file card with a stamp (SUSPECT n / DETECTIVE), slightly tilted."""
    from .render import font             # same font as the rest of the video
    pad, foot = 26, 120
    card = Image.new("RGBA", (CARD_W + pad * 2, CARD_H + pad + foot), (236, 230, 216, 255))
    card.paste(photo, (pad, pad))
    d = ImageDraw.Draw(card)
    label = name.upper()
    f = font(54, 800)
    while f.getlength(label) > CARD_W - 20 and f.size > 30:
        f = font(f.size - 4, 800)
    d.text(((card.width - f.getlength(label)) / 2, CARD_H + pad + 24), label, font=f, fill=(25, 22, 20))

    txt = stamp_text or f"SUSPECT {number}"
    sf = font(52, 800)
    sw = int(sf.getlength(txt)) + 60
    stamp = Image.new("RGBA", (sw, 112), (0, 0, 0, 0))
    sd = ImageDraw.Draw(stamp)
    sd.rounded_rectangle((4, 4, sw - 4, 108), radius=10, outline=stamp_colour + (235,), width=8)
    sd.text((30, 20), txt, font=sf, fill=stamp_colour + (235,))
    stamp = stamp.rotate(14, expand=True, resample=Image.BICUBIC)
    card.alpha_composite(stamp, (card.width - stamp.width - 6, CARD_H - 130))

    out = Image.new("RGBA", (card.width + 60, card.height + 70), (0, 0, 0, 0))
    ImageDraw.Draw(out).rectangle((30, 44, card.width + 30, card.height + 44), fill=(0, 0, 0, 170))
    out = out.filter(ImageFilter.GaussianBlur(14))
    out.alpha_composite(card, (30, 30))
    return out.rotate(-3 if number % 2 else 3, expand=True, resample=Image.BICUBIC)


def _photo_finish(photo: Image.Image) -> Image.Image:
    photo = ImageEnhance.Color(_cover(photo, CARD_W, CARD_H)).enhance(0.8)
    return ImageEnhance.Contrast(photo).enhance(1.08)


def make_suspect_card(person: dict, number: int, episode: int, path: Path) -> bool:
    """Gender-matched photorealistic AI portrait on a case-file card. True = AI portrait."""
    gender = gender_of(person)
    seed = episode * 100 + 50 + number
    who = "Tamil woman" if gender == "female" else "Tamil man"
    prompt = (f"photorealistic portrait photograph of a {person.get('age', 35)} year old {who} "
              f"from Tamil Nadu, {person.get('look', '')}")
    photo = _try_fetch(prompt, seed, size=(768, 920), style=PORTRAIT_STYLE)
    ai = photo is not None
    photo = _photo_finish(photo) if ai else _silhouette(gender, seed)
    print(f"[images] suspect {number} ({gender}): {'AI portrait' if ai else 'shadow figure'}", flush=True)
    _card(photo, person.get("name") or f"Suspect {number}", number).save(path)
    return ai


# ---------------------------------------------------------------- Nizhal ------------
# One fixed portrait, made once and kept in assets/, so the detective has the same face in
# every episode. Replace assets/characters/nizhal.jpg with any photo you prefer.
NIZHAL_PHOTO = config.ROOT / "assets" / "characters" / "nizhal.jpg"
NIZHAL_PROMPT = config.env(
    "NIZHAL_PROMPT",
    "photorealistic portrait photograph of a 42 year old Tamil man, a private detective from "
    "Chennai, short black hair with grey at the temples, neatly trimmed beard, calm sharp "
    "intelligent eyes, dark charcoal shirt under a long dark trench coat, rain on a window behind")


def make_nizhal_card(path: Path) -> bool:
    """Case-file card of the detective. False when there is no portrait yet and none could
    be made (the scene then simply has no card)."""
    if not NIZHAL_PHOTO.exists():
        photo = _try_fetch(NIZHAL_PROMPT, 4201, size=(896, 1152), style=PORTRAIT_STYLE)
        if photo is None:
            print("[images] no Nizhal portrait yet", flush=True)
            return False
        NIZHAL_PHOTO.parent.mkdir(parents=True, exist_ok=True)
        photo.save(NIZHAL_PHOTO, quality=95)
        print(f"[images] Nizhal portrait saved to {NIZHAL_PHOTO} (kept for every episode)", flush=True)
    photo = _photo_finish(Image.open(NIZHAL_PHOTO).convert("RGB"))
    _card(photo, f"Detective {config.INVESTIGATOR_EN}", 2, stamp_text="DETECTIVE",
          stamp_colour=(40, 110, 95)).save(path)
    return True


# ---------------------------------------------------------------- rain layer --------
def rain_texture(path: Path, seed: int = 7) -> Path:
    """RGBA rain streaks, W x 2H, the top half equal to the bottom half so the editor can
    scroll it down forever without a seam."""
    if path.exists():
        return path
    rnd = random.Random(seed)
    layer = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(layer)
    for _ in range(480):
        x, y, ln = rnd.randrange(W), rnd.randrange(H), rnd.randrange(40, 120)
        a = rnd.randrange(35, 110)
        wd = rnd.choice((1, 1, 2))
        for dy in (0, -H):                          # wrapped copy so the tile loops
            d.line((x, y + dy, x + ln // 7, y + dy + ln), fill=a, width=wd)
    layer = layer.filter(ImageFilter.GaussianBlur(0.7))
    alpha = Image.new("L", (W, H * 2))
    alpha.paste(layer, (0, 0))
    alpha.paste(layer, (0, H))
    rgba = Image.new("RGBA", (W, H * 2), (205, 215, 230, 0))
    rgba.putalpha(alpha)
    rgba.save(path)
    return path
