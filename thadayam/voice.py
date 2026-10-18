"""Tamil narration with word timing. Engines are tried in config.VOICE_ENGINES order:

- gemini      Gemini voice (realistic, free with GEMINI_API_KEY, 10 a day per model;
              timing taken from the pauses in the audio)
- elevenlabs  ElevenLabs (needs ELEVENLABS_API_KEY, character-level timestamps)
then always: Microsoft Edge neural voice (free, word timestamps), Google Translate TTS.

The timing lets the editor cut to B-roll on the exact word ("palace" -> palace video)
and keep subtitles in step with pauses."""
import asyncio
import base64
import bisect
import re
import subprocess
import wave
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import requests

from . import config

_eleven_dead = False        # quota used up / bad key: stop trying for the rest of the run


@dataclass
class Speech:
    duration: float
    marks: list = field(default_factory=list)     # [(char_index, seconds)] ascending
    text_len: int = 1
    path: Path | None = None                      # the audio file that was written

    def time_at(self, char_index: int) -> float:
        """When the voice reaches this character of the narration."""
        if not self.marks:
            return self.duration * min(1.0, char_index / max(1, self.text_len))
        idx = [m[0] for m in self.marks]
        k = bisect.bisect_right(idx, char_index) - 1
        if k < 0:
            return self.marks[0][1]
        if k + 1 < len(self.marks):
            (c0, t0), (c1, t1) = self.marks[k], self.marks[k + 1]
            return t0 + (t1 - t0) * (char_index - c0) / max(1, c1 - c0)
        return self.marks[k][1]


def duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True, check=True).stdout.strip()
    return float(out)


# ------------------------------------------------------------------ ElevenLabs ----
# ------------------------------------------------------------------ Gemini --------
_gemini_spent: set = set()      # models whose daily quota ran out during this run


def _pause_marks(pcm: np.ndarray, rate: int, text: str) -> list:
    """Gemini gives no timestamps. Line up the sentence ends in the text with the longest
    pauses in the audio, so cuts and subtitles still follow the voice."""
    hop = rate // 100                                         # 10 ms blocks
    level = np.abs(pcm[: pcm.size // hop * hop].reshape(-1, hop)).max(axis=1)
    quiet = level < max(300, level.max() * 0.04)
    gaps, start = [], None                                    # (length, middle in seconds)
    for i, q in enumerate(quiet):
        if q and start is None:
            start = i
        elif not q and start is not None:
            if i - start >= 12 and start > 0:                 # pauses of 120 ms or more
                gaps.append((i - start, (start + i) / 2 / 100))
            start = None
    # Commas pause too when the voice made enough pauses; otherwise only full stops count.
    breaks = [m.end() for m in re.finditer(r"[.?!,]+\s+", text)]
    if len(gaps) < len(breaks):
        breaks = [m.end() for m in re.finditer(r"[.?!]+\s+", text)]
    if not breaks or len(gaps) < len(breaks):
        return []                                             # cannot match: even spacing
    take = sorted(sorted(gaps, reverse=True)[: len(breaks)], key=lambda g: g[1])
    voiced = np.nonzero(~quiet)[0]
    first = voiced[0] / 100 if voiced.size else 0.0
    return [(0, first)] + [(b, t) for b, (_, t) in zip(breaks, take)]


def _gemini(text: str, path: Path) -> Speech:
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=config.GEMINI_API_KEY)
    errors = []
    for model in config.GEMINI_TTS_MODELS:
        if model in _gemini_spent:
            continue
        try:
            r = client.models.generate_content(
                model=model, contents=f"{config.GEMINI_TTS_STYLE}:\n{text}",
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=config.GEMINI_TTS_VOICE)))))
            part = r.candidates[0].content.parts[0].inline_data
            rate = int((re.search(r"rate=(\d+)", part.mime_type or "") or [0, 24000])[1])
            pcm = np.frombuffer(part.data, "<i2")
            path = path.with_suffix(".wav")
            if pcm.size < rate:                               # under a second: broken answer
                raise RuntimeError("audio too short")
            with wave.open(str(path), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(rate)
                w.writeframes(part.data)
            print(f"[voice] Gemini {model} {pcm.size / rate:.1f}s", flush=True)
            return Speech(pcm.size / rate, _pause_marks(pcm.astype(np.float32), rate, text),
                          len(text), path)
        except Exception as exc:
            msg = str(exc)
            if "429" in msg or "RESOURCE_EXHAUSTED" in msg or "404" in msg:
                _gemini_spent.add(model)                       # quota used up: next model
            errors.append(f"{model}: {msg[:120]}")
    raise RuntimeError("; ".join(errors) or "all Gemini voice models used up today")


def _eleven(text: str, path: Path, previous: str, following: str) -> Speech:
    url = (f"https://api.elevenlabs.io/v1/text-to-speech/{config.ELEVENLABS_VOICE_ID}"
           "/with-timestamps?output_format=mp3_44100_128")
    body = {"text": text, "model_id": config.ELEVENLABS_MODEL,
            "voice_settings": {"stability": config.ELEVENLABS_STABILITY, "similarity_boost": 0.8,
                               "style": config.ELEVENLABS_STYLE, "use_speaker_boost": True}}
    if config.ELEVENLABS_MODEL != "eleven_v3":      # v3 does not take request stitching
        body.update(previous_text=previous[-400:] or None, next_text=following[:400] or None)
    r = requests.post(url, json=body, timeout=180,
                      headers={"xi-api-key": config.ELEVENLABS_API_KEY})
    if not r.ok:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
    data = r.json()
    path.write_bytes(base64.b64decode(data["audio_base64"]))
    al = data.get("alignment") or data.get("normalized_alignment") or {}
    starts = al.get("character_start_times_seconds") or []
    marks = []
    if starts:
        scale = len(text) / len(starts)            # alignment can differ slightly in length
        marks = [(round(i * scale), t) for i, t in enumerate(starts)]
    return Speech(duration(path), marks, len(text), path)


# ------------------------------------------------------------------ Edge TTS ------
async def _edge_stream(text: str, path: Path) -> list:
    import edge_tts
    communicate = edge_tts.Communicate(text, config.TTS_VOICE, rate=config.TTS_RATE,
                                       pitch=config.TTS_PITCH, boundary="WordBoundary")
    marks, cursor = [], 0
    with path.open("wb") as fh:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                fh.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                pos = text.find(chunk["text"], cursor)
                if pos >= 0:
                    marks.append((pos, chunk["offset"] / 1e7))
                    cursor = pos + len(chunk["text"])
    return marks


def _edge(text: str, path: Path) -> Speech:
    marks = asyncio.run(asyncio.wait_for(_edge_stream(text, path), timeout=90))
    if not path.exists() or path.stat().st_size < 1000:
        raise RuntimeError("empty audio")
    return Speech(duration(path), marks, len(text), path)


def _gtts(text: str, path: Path) -> Speech:
    from gtts import gTTS
    gTTS(text=text, lang="ta").save(str(path))
    return Speech(duration(path), [], len(text), path)


def _silence(text: str, path: Path) -> Speech:
    """Mock mode: silent track as long as the line would roughly take to read."""
    seconds = max(2.0, len(text) / 12.0)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                    "anullsrc=r=48000:cl=stereo", "-t", f"{seconds:.2f}", str(path)], check=True)
    return Speech(duration(path), [], len(text), path)


def synthesize(text: str, path: Path, previous: str = "", following: str = "") -> Speech:
    """path is a suggestion: Gemini writes .wav next to it. Use the returned Speech.path."""
    global _eleven_dead
    if config.MOCK:
        return _silence(text, path)
    for engine in config.VOICE_ENGINES:
        if engine == "gemini" and config.GEMINI_API_KEY:
            if len(_gemini_spent) < len(config.GEMINI_TTS_MODELS):
                try:
                    return _gemini(text, path)
                except Exception as exc:
                    print(f"[voice] Gemini failed: {exc}", flush=True)
        elif engine == "elevenlabs" and config.ELEVENLABS_API_KEY and not _eleven_dead:
            for attempt in range(2):
                try:
                    speech = _eleven(text, path, previous, following)
                    print(f"[voice] ElevenLabs {speech.duration:.1f}s", flush=True)
                    return speech
                except Exception as exc:
                    print(f"[voice] ElevenLabs attempt {attempt + 1} failed: {exc}", flush=True)
                    if any(k in str(exc) for k in ("401", "402", "quota", "credits")):
                        _eleven_dead = True
                        break
    for attempt in range(3):
        try:
            return _edge(text, path)
        except Exception as exc:
            print(f"[voice] edge-tts attempt {attempt + 1} failed: {exc}", flush=True)
    print("[voice] falling back to Google TTS")
    return _gtts(text, path)
