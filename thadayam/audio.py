"""Sound for the episode: voice + a suspense score + sound effects.

Everything is composed in code with numpy (no copyright problems):
  score   - slow A-minor string pad, sparse piano notes in a reverb, a soft heartbeat pulse
  effects - whoosh (scene changes, B-roll cuts), impact (clues), thunder (hook),
            camera shutter (suspect photo), heartbeat (question), riser, bell (reveal)

Your own files win: any mp3/wav in assets/music replaces the score, and assets/sfx/<name>.wav
(or .mp3) replaces that effect. The music ducks under the voice automatically."""
import random
import subprocess
from pathlib import Path

import numpy as np

from . import config

SR = 48000


# ---------------------------------------------------------------- file helpers ----
def load(path: Path) -> np.ndarray:
    """Any audio file -> float32 stereo array (n, 2) at 48 kHz."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le", "-ac", "2",
                          "-ar", str(SR), "pipe:1"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2).copy()


def save(path: Path, x: np.ndarray) -> Path:
    pcm = (np.clip(x, -1, 1) * 32767).astype("<i2").tobytes()
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "s16le", "-ar", str(SR), "-ac", "2",
                    "-i", "pipe:0", str(path)], input=pcm, check=True)
    return path


def _t(seconds: float) -> np.ndarray:
    return np.arange(int(seconds * SR)) / SR


def _stereo(mono: np.ndarray, pan: float = 0.0) -> np.ndarray:
    left, right = np.sqrt(0.5 * (1 - pan)), np.sqrt(0.5 * (1 + pan))
    return np.stack([mono * left, mono * right], axis=1).astype(np.float32)


def _lowpass(x: np.ndarray, cutoff: float, slope: float = 2.0) -> np.ndarray:
    spec = np.fft.rfft(x, axis=0)
    f = np.fft.rfftfreq(x.shape[0], 1 / SR)
    gain = 1 / (1 + (f / cutoff) ** (2 * slope))
    return np.fft.irfft(spec * (gain if x.ndim == 1 else gain[:, None]), n=x.shape[0], axis=0)


def _bandpass(x: np.ndarray, lo: float, hi: float) -> np.ndarray:
    return _lowpass(x, hi) - _lowpass(x, lo)


def _reverb(x: np.ndarray, seconds: float = 2.2, wet: float = 0.35, seed: int = 3) -> np.ndarray:
    rng = np.random.default_rng(seed)
    n = int(seconds * SR)
    ir = rng.normal(0, 1, (n, 2)) * np.exp(-_t(seconds) * 5.5 / seconds)[:, None]
    ir = _lowpass(ir, 4500)
    ir /= np.abs(ir).sum(axis=0).max() / 6
    size = x.shape[0] + n
    out = np.fft.irfft(np.fft.rfft(x, size, axis=0) * np.fft.rfft(ir, size, axis=0), size, axis=0)
    return x * (1 - wet) + out[: x.shape[0]] * wet


def _norm(x: np.ndarray, peak: float = 0.9) -> np.ndarray:
    m = np.abs(x).max()
    return (x / m * peak).astype(np.float32) if m > 0 else x.astype(np.float32)


# ---------------------------------------------------------------- effects ---------
def whoosh(seconds: float = 0.8, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    n = int(seconds * SR)
    noise = rng.normal(0, 1, n)
    # time-varying one-pole lowpass: cutoff sweeps up then down
    pos = np.linspace(0, 1, n)
    cutoff = 300 + 5200 * np.sin(np.pi * pos) ** 2
    a = np.exp(-2 * np.pi * cutoff / SR)
    y = np.empty(n)
    acc = 0.0
    for i in range(n):
        acc = a[i] * acc + (1 - a[i]) * noise[i]
        y[i] = acc
    env = np.sin(np.pi * pos) ** 1.5
    mono = y * env
    pan = np.linspace(-0.7, 0.7, n)
    return _norm(np.stack([mono * np.sqrt(0.5 * (1 - pan)), mono * np.sqrt(0.5 * (1 + pan))], 1), 0.7)


def impact(seconds: float = 1.8, seed: int = 1) -> np.ndarray:
    t = _t(seconds)
    freq = 35 + 70 * np.exp(-t * 6)
    phase = 2 * np.pi * np.cumsum(freq) / SR
    boom = np.sin(phase) * np.exp(-t * 2.6)
    rng = np.random.default_rng(seed)
    crack = _lowpass(rng.normal(0, 1, t.size), 2500) * np.exp(-t * 28) * 0.8
    return _norm(_reverb(_stereo(np.tanh(1.8 * (boom + crack))), 1.6, 0.25), 0.95)


def thunder(seconds: float = 3.5, seed: int = 2) -> np.ndarray:
    rng = np.random.default_rng(seed)
    t = _t(seconds)
    brown = np.cumsum(rng.normal(0, 1, t.size))
    brown = _lowpass(brown - _lowpass(brown, 20), 600)
    crackles = np.zeros(t.size)
    for _ in range(14):
        s = int(rng.uniform(0, 0.9) * SR)
        ln = int(rng.uniform(0.03, 0.15) * SR)
        crackles[s:s + ln] += rng.normal(0, 1, len(crackles[s:s + ln])) * rng.uniform(0.3, 1)
    crackles = _lowpass(crackles, 3000)
    env = (1 - np.exp(-t * 40)) * np.exp(-t * 1.1)
    mono = (brown / (np.abs(brown).max() + 1e-9) + 0.5 * crackles) * env
    return _norm(_reverb(_stereo(mono), 2.5, 0.4), 0.9)


def shutter(seed: int = 4) -> np.ndarray:
    rng = np.random.default_rng(seed)
    out = np.zeros(int(0.35 * SR))
    for start, amp in ((0.0, 1.0), (0.085, 0.75)):
        s = int(start * SR)
        n = int(0.012 * SR)
        click = rng.normal(0, 1, n) * np.exp(-np.linspace(0, 6, n))
        out[s:s + n] += click * amp
    out = out - _lowpass(out, 1800)                       # thin, mechanical
    return _norm(_reverb(_stereo(out, 0.2), 0.4, 0.15), 0.8)


def heartbeat(beats: int = 3, bpm: float = 64) -> np.ndarray:
    period = 60 / bpm
    out = np.zeros(int((beats * period + 0.6) * SR))
    t = _t(0.35)
    thump = np.sin(2 * np.pi * (48 + 20 * np.exp(-t * 30)) * t) * np.exp(-t * 14)
    for b in range(beats):
        for off, amp in ((0.0, 1.0), (0.26, 0.7)):
            s = int((b * period + off) * SR)
            out[s:s + thump.size] += thump[: len(out[s:s + thump.size])] * amp
    return _norm(_stereo(np.tanh(2 * out)), 0.9)


def riser(seconds: float = 2.0, seed: int = 5) -> np.ndarray:
    rng = np.random.default_rng(seed)
    t = _t(seconds)
    pos = t / seconds
    freq = 180 * (8 ** pos)
    tone = np.sin(2 * np.pi * np.cumsum(freq) / SR) * 0.5
    air = _bandpass(rng.normal(0, 1, t.size), 1500, 7000) * 0.6
    return _norm(_stereo((tone + air) * pos ** 2.2), 0.6)


def bell(seconds: float = 3.0) -> np.ndarray:
    t = _t(seconds)
    mono = sum(a * np.sin(2 * np.pi * 440 * r * t) * np.exp(-t * d)
               for r, a, d in ((1, 1, 1.4), (2.76, 0.5, 2.5), (5.4, 0.25, 4), (8.9, 0.12, 6)))
    return _norm(_reverb(_stereo(mono), 2.8, 0.45), 0.55)


EFFECTS = {"whoosh": whoosh, "impact": impact, "thunder": thunder, "shutter": shutter,
           "heartbeat": heartbeat, "riser": riser, "bell": bell}
_fx_cache: dict = {}


def effect(name: str) -> np.ndarray:
    if name not in _fx_cache:
        custom = [p for ext in ("wav", "mp3", "ogg") for p in config.SFX_DIR.glob(f"{name}.{ext}")]
        _fx_cache[name] = _norm(load(custom[0]), 0.9) if custom else EFFECTS[name]()
    return _fx_cache[name]


# ---------------------------------------------------------------- score -----------
CHORDS = [  # A minor: i - VI - iv - V (E major for tension), frequencies of the pad notes
    (110.00, 130.81, 164.81, 220.00),
    (87.31, 110.00, 130.81, 174.61),
    (73.42, 110.00, 146.83, 174.61),
    (82.41, 103.83, 123.47, 164.81),
]
PIANO = [440.0, 523.25, 587.33, 659.25, 783.99, 880.0, 493.88]     # A minor colours


def compose(seconds: float, seed: int) -> np.ndarray:
    rnd = random.Random(seed)
    n = int(seconds * SR)
    t = np.arange(n) / SR
    pad = np.zeros(n)
    bar = 4.0
    for k in range(int(seconds / bar) + 2):
        chord = CHORDS[k % len(CHORDS)]
        s0, s1 = max(0, int((k * bar - 1.0) * SR)), min(n, int(((k + 1) * bar + 1.0) * SR))
        if s0 >= n:
            break
        seg_t = t[s0:s1]
        win = np.sin(np.pi * np.linspace(0, 1, s1 - s0)) ** 2
        for f in chord:
            for det in (-0.12, 0.0, 0.13):              # detuned saws = string section
                ph = (f * (1 + det / 100)) * seg_t + rnd.random()
                pad[s0:s1] += (2 * (ph % 1) - 1) * win * 0.18
    pad = _lowpass(pad, 850, 2.5) * (0.8 + 0.2 * np.sin(2 * np.pi * 0.11 * t))

    piano = np.zeros(n)
    nt = _t(3.0)
    tpos = 1.5
    while tpos < seconds - 1:
        f = rnd.choice(PIANO)
        note = sum(a * np.sin(2 * np.pi * f * h * nt) for h, a in ((1, 1), (2, 0.35), (3, 0.12)))
        note *= np.exp(-nt * 2.2) * (1 - np.exp(-nt * 400)) * rnd.uniform(0.5, 0.9)
        s = int(tpos * SR)
        piano[s:s + note.size] += note[: len(piano[s:s + note.size])]
        tpos += rnd.choice((1.5, 2.0, 2.0, 3.0, 4.0))
    music = _stereo(pad, 0) + _reverb(_stereo(piano * 0.32, 0.25), 2.6, 0.5)

    pulse = np.zeros(n)
    hb = heartbeat(1)[:, 0]
    for k in range(int(seconds / 2.0)):
        s = int(k * 2.0 * SR)
        pulse[s:s + hb.size] += hb[: len(pulse[s:s + hb.size])] * 0.25
    music += _stereo(pulse)
    fade = np.minimum(1, np.minimum(t / 1.5, (seconds - t) / 2.0)).clip(0, 1)
    return _norm(music * fade[:, None], 0.8)


def music_bed(seconds: float, seed: int) -> np.ndarray:
    tracks = sorted(p for ext in ("mp3", "wav", "ogg", "m4a") for p in config.MUSIC_DIR.glob(f"*.{ext}"))
    n = int(seconds * SR)
    if tracks:
        track = tracks[seed % len(tracks)]
        print(f"[audio] music: {track.name}", flush=True)
        x = load(track)
        x = np.tile(x, (n // max(1, x.shape[0]) + 1, 1))[:n]
        t = np.arange(n) / SR
        fade = np.minimum(1, np.minimum(t / 1.0, (seconds - t) / 2.0)).clip(0, 1)
        return _norm(x * fade[:, None], 0.8)
    print("[audio] music: composed in code", flush=True)
    return compose(seconds, seed)


# ---------------------------------------------------------------- mix -------------
def _place(track: np.ndarray, clip: np.ndarray, at: float, gain: float = 1.0) -> None:
    s = max(0, int(at * SR))
    if s >= track.shape[0]:
        return
    e = min(track.shape[0], s + clip.shape[0])
    track[s:e] += clip[: e - s] * gain


def _envelope(x: np.ndarray, attack: float = 0.02, release: float = 0.45) -> np.ndarray:
    """Smoothed loudness of the voice, used to duck the music."""
    level = np.abs(x).max(axis=1)
    hop = 240                                            # 5 ms blocks
    blocks = level[: level.size // hop * hop].reshape(-1, hop).max(axis=1)
    out = np.empty_like(blocks)
    acc = 0.0
    a_up, a_dn = np.exp(-hop / SR / attack), np.exp(-hop / SR / release)
    for i, v in enumerate(blocks):
        a = a_up if v > acc else a_dn
        acc = a * acc + (1 - a) * v
        out[i] = acc
    env = np.repeat(out, hop)
    return np.pad(env, (0, level.size - env.size), mode="edge")


def build(work: Path, voices: list[Path], durs: list[float], scene_types: list[str],
          events: list[tuple[float, str]], seed: int) -> Path:
    """voices are placed one after another (each scene lasts durs[i]); events are extra
    (seconds, effect name) cues from the editor, e.g. B-roll cuts and suspect photos."""
    total = sum(durs)
    n = int(total * SR) + SR
    voice = np.zeros((n, 2), np.float32)
    starts, t = [], 0.0
    for v, d in zip(voices, durs):
        starts.append(t)
        _place(voice, load(v)[: int(d * SR)], t + 0.15)
        t += d

    sfx = np.zeros((n, 2), np.float32)
    for i, (s, kind) in enumerate(zip(starts, scene_types)):
        if i > 0:
            _place(sfx, effect("whoosh"), s - 0.35, 0.55)
        if kind == "hook":
            _place(sfx, effect("thunder"), s, 0.8)
            _place(sfx, effect("impact"), s, 0.6)
        elif kind == "clue":
            _place(sfx, effect("impact"), s, 0.75)
        elif kind == "reveal":
            _place(sfx, effect("bell"), s + 0.1, 0.7)
        elif kind == "cta":
            rise = effect("riser")
            _place(sfx, rise, s - rise.shape[0] / SR, 0.5)
            _place(sfx, effect("heartbeat"), s + 0.2, 0.7)
    for at, name in events:
        _place(sfx, effect(name), at, 0.45 if name == "whoosh" else 0.8)

    music = np.zeros((n, 2), np.float32)
    _place(music, music_bed(total + 0.5, seed), 0)
    duck = 1 - 0.7 * np.clip(_envelope(voice) / 0.08, 0, 1)
    mix = voice + music * (config.MUSIC_VOLUME * 4 * duck[:, None]) + sfx * config.SFX_VOLUME * 0.5
    raw = save(work / "mix_raw.wav", (mix[: int(total * SR)] * 0.5))

    out = work / "mix.wav"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(raw), "-af",
                    "loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000", "-ac", "2", str(out)],
                   check=True, capture_output=True)
    return out
