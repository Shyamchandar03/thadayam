
"""The automatic editor: Tamil text layers drawn with Pillow (Raqm shaping, so Tamil
letters join correctly); camera motion, rain, B-roll cuts and suspect cards done by FFmpeg.
The sound mix lives in audio.py."""
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from . import config, images

W, H, FPS = config.WIDTH, config.HEIGHT, config.FPS
AMBER = (232, 176, 74)
RED = (192, 48, 43)
STEEL = (46, 74, 122)
TEAL = (38, 128, 112)
WHITE = (245, 245, 245)
INK = (14, 14, 18)
SAFE_X = 64                      # left/right margin
TEXT_W = W - SAFE_X * 2 - 60     # keep clear of the Shorts/Reels side buttons
FADE = 0.22
TAIL = 0.45                      # silence after each scene's voice


# ---------------------------------------------------------------- fonts -------
def _font_path() -> tuple[Path, bool]:
    for p in [Path("/usr/share/fonts/truetype/noto/NotoSansTamil-Bold.ttf"),
              *Path("/usr/share/fonts").rglob("NotoSansTamil-Bold.ttf")]:
        if p.exists():
            return p, False
    return config.FONT_DIR / "NotoSansTamil-Variable.ttf", True


_FONT_PATH, _VARIABLE = _font_path()
_cache: dict = {}


def font(size: int, weight: int = 700) -> ImageFont.FreeTypeFont:
    key = (size, weight)
    if key not in _cache:
        from PIL import features
        use_raqm = features.check("raqm") and config.env("FORCE_BASIC_TEXT") != "true"
        engine = ImageFont.Layout.RAQM if use_raqm else ImageFont.Layout.BASIC
        f = ImageFont.truetype(str(_FONT_PATH), size, layout_engine=engine)
        if _VARIABLE:
            axes = f.get_variation_axes()
            f.set_variation_by_axes([weight if a["name"] == b"Weight" else a["default"] for a in axes])
        _cache[key] = f
    return _cache[key]


# ---------------------------------------------------------------- text --------
def wrap(text: str, f, max_w: int) -> list[str]:
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if f.getlength(trial) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def chunk_narration(text: str, f, max_w: int) -> list[str]:
    """Split narration into subtitle cards of at most two lines, breaking at sentence ends."""
    chunks, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if cur and f.getlength(trial) > max_w * 1.75:
            chunks.append(cur)
            cur = word
        else:
            cur = trial
        if cur and cur[-1] in ".?!" and f.getlength(cur) > max_w * 0.6:
            chunks.append(cur)
            cur = ""
    if cur:
        chunks.append(cur)
    return chunks


def _draw_lines(d: ImageDraw.ImageDraw, lines, f, cx, top, fill, stroke=0, align="center",
                left=SAFE_X, gap=1.28):
    lh = int(f.size * gap)
    for i, line in enumerate(lines):
        x = cx - f.getlength(line) / 2 if align == "center" else left
        d.text((x, top + i * lh), line, font=f, fill=fill, stroke_width=stroke,
               stroke_fill=(0, 0, 0))
    return top + len(lines) * lh


def _tag(d, text, top, bg, fg):
    f = font(46, 700)
    lines = wrap(text, f, TEXT_W - 60)[:2]
    lh = int(f.size * 1.32)
    w = max(f.getlength(l) for l in lines) + 56
    h = lh * len(lines) + 36
    d.rounded_rectangle((SAFE_X, top, SAFE_X + w, top + h), radius=14, fill=bg + (235,))
    d.rectangle((SAFE_X, top, SAFE_X + 10, top + h), fill=(0, 0, 0, 120))
    _draw_lines(d, lines, f, 0, top + 14, fg, align="left", left=SAFE_X + 34, gap=1.32)


def overlay(scene: dict, sub: str | None, episode: int) -> Image.Image:
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    stype = scene.get("type", "")
    label = (scene.get("on_screen") or "").strip()

    # Series badge
    d.rectangle((SAFE_X, 150, SAFE_X + 8, 262), fill=RED + (255,))
    series = config.SERIES_NAME_EN.upper() if config.TANGLISH else config.SERIES_NAME
    d.text((SAFE_X + 28, 140), series, font=font(68, 800), fill=AMBER,
           stroke_width=3, stroke_fill=(0, 0, 0))
    file_line = (f"File #{episode:02d}  ·  Detective {config.INVESTIGATOR_EN}" if config.TANGLISH
                 else f"கோப்பு #{episode:02d}  ·  {config.INVESTIGATOR}")
    d.text((SAFE_X + 30, 228), file_line,
           font=font(32, 600), fill=(225, 225, 225), stroke_width=2, stroke_fill=(0, 0, 0))

    # Scene label
    if label:
        if stype in ("hook", "cta", "reveal"):
            f = font(94 if stype != "reveal" else 78, 800)
            lines = wrap(label, f, TEXT_W)[:3]
            colour = (120, 220, 190) if stype == "reveal" else AMBER
            _draw_lines(d, lines, f, W // 2 - 20, 640, colour, stroke=6)
        else:
            bg, fg = {"suspect": (AMBER, INK), "clue": (RED, WHITE)}.get(stype, (STEEL, WHITE))
            _tag(d, label, 330, bg, fg)

    # Subtitle card
    if sub:
        f = font(60, 700)
        lines = wrap(sub, f, TEXT_W)[:3]
        lh = int(f.size * 1.34)
        block_h = lh * len(lines)
        top = 1310 - block_h // 2
        bw = max(f.getlength(l) for l in lines)
        cx = W // 2 - 20
        d.rounded_rectangle((cx - bw / 2 - 34, top - 26, cx + bw / 2 + 34, top + block_h + 18),
                            radius=22, fill=(0, 0, 0, 150))
        _draw_lines(d, lines, f, cx, top, WHITE, stroke=4, gap=1.34)

    if stype == "cta":
        msg = ("Comment-la unga answer sollunga" if config.TANGLISH
               else "கமெண்ட்ல உங்க பதிலை சொல்லுங்க")
        size = 50
        while font(size, 700).getlength(msg) > TEXT_W - 80 and size > 28:
            size -= 2
        f = font(size, 700)
        y = 1560
        bw = f.getlength(msg)
        d.rounded_rectangle((W // 2 - 20 - bw / 2 - 30, y - 14, W // 2 - 20 + bw / 2 + 30, y + 80),
                            radius=40, fill=RED + (240,))
        d.text((W // 2 - 20 - bw / 2, y), msg, font=f, fill=WHITE)
    return img


# ---------------------------------------------------------------- ffmpeg ------
def run(cmd: list[str]) -> None:
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"ffmpeg failed:\n{' '.join(cmd)}\n{res.stderr[-3000:]}")


def _subtitle_times(chunks: list[str], shown: str, narration: str, speech, dur: float) -> list:
    """When each subtitle card starts and ends. Uses the voice's own timing, so the cards
    wait through pauses instead of drifting. Tanglish captions are mapped onto the Tamil
    narration by position."""
    starts, pos = [], 0
    for c in chunks:
        k = shown.find(c, pos)
        k = pos if k < 0 else k
        frac = k / max(1, len(shown))
        starts.append(0.15 + speech.time_at(round(frac * len(narration))))
        pos = k + len(c)
    starts[0] = 0.15
    times = [(a, b) for a, b in zip(starts, starts[1:] + [dur])]
    return [(a, max(b, a + 0.4)) for a, b in times]


# Camera moves, cycled per scene: (zoom expression, x expression, y expression).
# "on" is the frame number, F the number of frames in the scene.
MOVES = [
    ("1+0.16*on/F", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),                     # push in
    ("1.16-0.16*on/F", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),                  # pull out
    ("1.14", "(iw-iw/zoom)*on/F", "ih/2-(ih/zoom/2)"),                          # pan right
    ("1.14", "iw/2-(iw/zoom/2)", "(ih-ih/zoom)*(1-on/F)"),                      # tilt up
    ("1+0.18*on/F", "iw/2-(iw/zoom/2)", "(ih/3)-(ih/zoom/3)"),                  # push to face height
    ("1.14", "(iw-iw/zoom)*(1-on/F)", "ih/2-(ih/zoom/2)"),                      # pan left
]


def render_scene(work: Path, idx: int, scene: dict, image: Path, speech, start: float,
                 total: float, episode: int, last: bool, card: Path | None = None,
                 brolls: list | None = None) -> tuple[Path, float, list]:
    """One scene clip. brolls = [(seconds into the scene, clip path)].
    Returns (clip, duration, sound cues [(seconds into the scene, effect name)])."""
    dur = scene_duration(speech.duration, last)
    f = font(60, 700)
    shown = scene.get("subtitle") if config.TANGLISH and scene.get("subtitle") else scene["narration"]
    chunks = chunk_narration(shown, f, TEXT_W)
    times = _subtitle_times(chunks, shown, scene["narration"], speech, dur)
    cues = []

    inputs = ["-loop", "1", "-framerate", str(FPS), "-t", f"{dur:.3f}", "-i", str(image)]
    n_in = 1

    def add_input(*args) -> int:
        nonlocal n_in
        inputs.extend(args)
        n_in += 1
        return n_in - 1

    frames = max(1, round(dur * FPS))
    zoom, px, py = (e.replace("F", str(frames)) for e in MOVES[(idx + episode) % len(MOVES)])
    stype = scene.get("type", "")
    fil = [f"[0:v]scale={W * 2}:{H * 2},zoompan=z='{zoom}':x='{px}':y='{py}':d=1:"
           f"s={W + 48}x{H + 48}:fps={FPS},"
           # handheld camera: slow drifting crop
           f"crop={W}:{H}:x='24+16*sin(2*PI*t*0.37)+6*sin(2*PI*t*1.3)':"
           f"y='24+14*cos(2*PI*t*0.29)+5*sin(2*PI*t*1.7)',setsar=1[bg0]"]
    prev = "bg0"

    # Stock video cut in on the spoken word
    for b_i, (at, clip) in enumerate(brolls or []):
        bd = min(config.BROLL_SECONDS, dur - at - 0.15)
        if bd < 1.2:
            continue
        k = add_input("-t", f"{bd + 0.5:.3f}", "-i", str(clip))
        fil.append(f"[{k}:v]trim=0:{bd:.3f},setpts=PTS-STARTPTS,fps={FPS},"
                   f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,"
                   f"zoompan=z='1+0.06*on/{round(bd * FPS)}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                   f":d=1:s={W}x{H}:fps={FPS},"
                   "eq=saturation=0.6:contrast=1.12:brightness=-0.04,"
                   "colorbalance=bs=0.06:rh=0.04,format=yuva420p,"
                   f"fade=t=in:st=0:d=0.18:alpha=1,fade=t=out:st={bd - 0.25:.3f}:d=0.25:alpha=1,"
                   f"setpts=PTS+{at:.3f}/TB[br{b_i}]")
        fil.append(f"[{prev}][br{b_i}]overlay=0:0:eof_action=pass[vb{b_i}]")
        prev = f"vb{b_i}"
        cues.append((at - 0.2, "whoosh"))

    # Rain falling across the frame, film grain, and a nervous light flicker on key beats
    k = add_input("-loop", "1", "-framerate", str(FPS), "-t", f"{dur:.3f}", "-i",
                  str(images.rain_texture(work.parent / "rain.png")))
    speed = 1500 + 300 * (idx % 3)
    fil.append(f"[{prev}][{k}:v]overlay=x=0:y='mod(t*{speed}\\,{H})-{H}':shortest=1,"
               "noise=alls=9:allf=t+u" +
               (",eq=brightness='0.035*sin(t*29)*sin(t*7.3)':eval=frame" if stype in ("hook", "clue", "cta") else "")
               + "[fx]")
    prev = "fx"

    # Suspect case-file photo slides in from the right and lands with a camera click
    if card is not None:
        k = add_input("-loop", "1", "-framerate", str(FPS), "-t", f"{dur:.3f}", "-i", str(card))
        land_x = "(W-w)/2-10"
        fil.append(f"[{k}:v]scale=iw*0.72:-1,format=rgba[card]")
        fil.append(f"[{prev}][card]overlay=x='{land_x}+(W-({land_x}))*pow(1-min(1\\,max(0\\,(t-0.3)/0.45))\\,3)'"
                   f":y=450:enable='gte(t,0.3)'[vc]")
        prev = "vc"
        cues.append((0.72, "shutter"))

    first_text = n_in
    for c_i, chunk in enumerate(chunks):
        p = work / f"ov_{idx:02d}_{c_i:02d}.png"
        overlay(scene, chunk, episode).save(p)
        add_input("-i", str(p))
    bar_idx = add_input("-f", "lavfi", "-i", f"color=c=0xE8B04A:s={W}x10:r={FPS}")

    for c_i, (a, b) in enumerate(times):
        fil.append(f"[{prev}][{first_text + c_i}:v]overlay=0:0:enable='between(t,{a:.3f},{b:.3f})'[v{c_i}]")
        prev = f"v{c_i}"
    fil.append(f"[{prev}][{bar_idx}:v]overlay=x='-w+w*(t+{start:.3f})/{total:.3f}':y=0:shortest=1[vbar]")
    fade = f"fade=t=in:st=0:d={FADE}," if idx > 0 else ""
    fil.append(f"[vbar]{fade}fade=t=out:st={dur - FADE:.3f}:d={FADE},format=yuv420p[out]")

    out = work / f"scene_{idx:02d}.mp4"
    run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", ";".join(fil),
         "-map", "[out]", "-t", f"{dur:.3f}", "-r", str(FPS), "-c:v", "libx264",
         "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", str(out)])
    return out, dur, cues


def scene_duration(voice_dur: float, last: bool) -> float:
    return voice_dur + TAIL + (0.6 if last else 0)


def assemble(work: Path, scenes: list[Path], audio: Path, out: Path) -> Path:
    lst = work / "video_list.txt"
    lst.write_text("".join(f"file '{p.name}'\n" for p in scenes))
    silent = work / "video.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
         "-c", "copy", str(silent)])
    run(["ffmpeg", "-y", "-v", "error", "-i", str(silent), "-i", str(audio),
         "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
         "-shortest", "-movflags", "+faststart", str(out)])
    return out


def thumbnail(video: Path, out: Path, at: float = 1.2) -> Path:
    run(["ffmpeg", "-y", "-v", "error", "-ss", f"{at}", "-i", str(video), "-frames:v", "1",
         "-q:v", "3", str(out)])
    return out
