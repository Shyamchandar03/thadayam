"""Writes each episode with the Gemini API (free tier) as strict JSON."""
import json
import time
from . import config

SCENE_TYPES = {"reveal", "hook", "case", "suspect", "clue", "cta"}

PROMPT = """You are the head writer of "{series}" ({series_en}), a daily faceless Tamil
interactive detective series for YouTube Shorts and Instagram Reels.

THE INVESTIGATOR: {investigator} ("Shadow") narrates in first person. Calm, sharp, a little
mysterious. He always asks the audience to help him.

WRITE EPISODE #{number} (file number "கோப்பு #{number:02d}").

RULES FOR THE CASE
- A brand-new, original, FICTIONAL mystery set somewhere in Tamil Nadu (vary the city, the
  setting and the type of case: theft, missing item, fraud, sabotage, a fake alibi, a
  locked room, a poisoned recipe competition with nobody hurt, etc.).
- Family-friendly: no gore, no graphic violence, no sexual content, no harm to children,
  no real people, real brands, real businesses, castes, religions or political parties.
- Exactly 3 suspects with ordinary Tamil first names and a role each.
- Exactly 3 clues. It must be FAIR PLAY: a careful viewer can name the culprit from the
  clues alone. One clue may mislead; the decisive clue must be shown, not explained.
  Never reveal or strongly hint the answer in the narration.
- Do NOT repeat these earlier cases: {history}

LANGUAGE
- All narration and on-screen text in natural spoken Tamil (Tamil script), the way a
  storyteller from Chennai talks: simple, clear, punchy short sentences. Common English
  words people say in Tamil (CCTV, phone, office) may stay in English letters.
- Write numbers and times as words so the voice reads them correctly.
- The whole narration together must be 650 to 950 Tamil characters (about 70-85 seconds).

SCENE ORDER (the "scenes" list)
{reveal_rule}1. "hook"    - one or two gripping sentences. on_screen: a short punchy line (max 5 words).
2. "case"    - "நான் {investigator}." + place, time, what happened.
3-5. "suspect" x3 - who they are and their claim/alibi. on_screen: "சந்தேக நபர் N: name (role)".
6-8. "clue" x3   - one clue each. on_screen: "தடயம் N".
9. "cta"     - ask who did it AND which clue proves it; tell viewers to comment; promise to
   say the names of correct solvers tomorrow. on_screen: the big question (max 6 words).

{subtitle_rule}Each scene also has "image_prompt": an ENGLISH description of a single cinematic still
for that scene (places, objects, atmosphere; people only from behind or in shadow; no text
in the image).

Each "suspect" scene also has "person": {{"name": "English spelling of the name",
"gender": "male" or "female" (must match the Tamil name), "age": number,
"look": "ENGLISH portrait description: face, hair, clothing that fits the role, expression"}}.
It is drawn as the suspect's case-file photo.

Each scene also has "broll": 0 to 2 cues for real stock video shown the moment a word is
spoken. Each cue is {{"word": "one word copied EXACTLY, letter for letter, from this
scene's narration", "query": "1-3 plain English words to search a stock video site"}}.
Pick concrete, filmable things: places (palace, temple, beach, market, hospital, railway
station), weather (rain, lightning), objects (gold jewellery, old key, CCTV camera,
burning candle), city at night. Never people's faces, brands or logos. Aim for 5 to 8
cues in the whole episode, and none in the "cta" scene.

Return ONLY JSON with exactly this shape:
{{
  "title": "Tamil case title",
  "title_en": "English case title",
  "scenes": [{{"type": "...", "on_screen": "...", "narration": "...",{subtitle_key} "image_prompt": "...",
              "broll": [{{"word": "...", "query": "..."}}],
              "person": {{"name": "...", "gender": "male", "age": 34, "look": "..."}} (suspect scenes only)}}],
  "solution": {{
    "culprit": "culprit name in Tamil",
    "culprit_aliases": ["Tamil name", "English spelling", "role words viewers might use"],
    "explanation": "2-3 Tamil sentences explaining how the clues prove it",
    "key_clue": "the decisive clue, one Tamil line"
  }},
  "youtube_title": "curiosity title in Tamil, under 90 characters, ending with | {series} கோப்பு #{number:02d} #Shorts",
  "description": "2 Tamil sentences inviting viewers to solve it in the comments",
  "hashtags": ["#{series}", "#TamilMystery", "#Shorts", "... 4 more relevant tags"],
  "instagram_caption": "short Tamil caption with one question and a call to comment"
}}"""

SUBTITLE_RULE = """ON-SCREEN TEXT IS TANGLISH: write every "on_screen" in Tanglish (Tamil words in
English letters, the way Tamil people text: "Suspect 1: Karthik (photographer)", "Clue 2",
"Necklace-a eduthathu yaaru?"). Every scene also has "subtitle": the SAME sentences as its
"narration", written in Tanglish with the same meaning and order (it is shown as captions while
the Tamil voice speaks). Keep the "narration" itself in Tamil script for the voice.
"""

REVEAL_RULE = """0. "reveal"  - FIRST scene, under 25 seconds: solve YESTERDAY's case in a satisfying way.
   Yesterday's case: "{prev_title}". Culprit: {prev_culprit}. Why: {prev_explanation}
   {solver_line}
   End with a short bridge into today's case. on_screen: "நேற்றைய பதில்: {prev_culprit}".
"""


def _build_prompt(number: int, history: list[str], prev: dict | None, solvers: list[str]) -> str:
    reveal_rule = ""
    if prev and prev.get("solution"):
        if solvers:
            solver_line = ("Thank these viewers by name who solved it correctly: "
                           + ", ".join(solvers[:5]) + ".")
        else:
            solver_line = "Thank everyone who commented their guesses."
        sol = prev["solution"]
        reveal_rule = REVEAL_RULE.format(
            prev_title=prev.get("title", ""), prev_culprit=sol.get("culprit", ""),
            prev_explanation=sol.get("explanation", ""), solver_line=solver_line)
    return PROMPT.format(
        series=config.SERIES_NAME, series_en=config.SERIES_NAME_EN,
        investigator=config.INVESTIGATOR, number=number,
        history="; ".join(history[-40:]) or "none yet", reveal_rule=reveal_rule,
        subtitle_rule=SUBTITLE_RULE if config.TANGLISH else "",
        subtitle_key=' "subtitle": "...",' if config.TANGLISH else "")


def validate(ep: dict, needs_reveal: bool) -> list[str]:
    problems = []
    scenes = ep.get("scenes") or []
    types = [s.get("type") for s in scenes]
    if any(t not in SCENE_TYPES for t in types):
        problems.append(f"unknown scene types: {types}")
    if types.count("suspect") != 3 or types.count("clue") != 3:
        problems.append("need exactly 3 suspects and 3 clues")
    if not types or types[-1] != "cta":
        problems.append("last scene must be cta")
    if needs_reveal and (not types or types[0] != "reveal"):
        problems.append("first scene must be reveal")
    if config.TANGLISH and any(not s.get("subtitle", "").strip() for s in scenes):
        problems.append("every scene needs a Tanglish subtitle")
    for s in scenes:
        if not s.get("narration", "").strip() or not s.get("image_prompt", "").strip():
            problems.append("every scene needs narration and image_prompt")
            break
    for s in scenes:
        if s.get("type") == "suspect":
            person = s.get("person") or {}
            if person.get("gender") not in ("male", "female") or not person.get("look"):
                problems.append("every suspect needs person.gender (male/female) and person.look")
                break
    for s in scenes:      # drop cues whose word is not really in the narration
        s["broll"] = [c for c in (s.get("broll") or [])
                      if isinstance(c, dict) and c.get("word") and c.get("query")
                      and c["word"] in s.get("narration", "")][:2]
    chars = sum(len(s.get("narration", "")) for s in scenes if s.get("type") != "reveal")
    if not 450 <= chars <= 1300:
        problems.append(f"narration length {chars} chars is outside 450-1300")
    for key in ("title", "solution", "youtube_title", "description", "hashtags"):
        if not ep.get(key):
            problems.append(f"missing {key}")
    if not (ep.get("solution") or {}).get("culprit"):
        problems.append("missing solution.culprit")
    return problems


def generate(number: int, history: list[str], prev: dict | None, solvers: list[str]) -> dict:
    if config.MOCK:
        sample = json.loads((config.ROOT / "assets" / "sample_episode.json").read_text(encoding="utf-8"))
        return sample

    if not config.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not set (add it as a repository secret).")

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=config.GEMINI_API_KEY)
    prompt = _build_prompt(number, history, prev, solvers)
    needs_reveal = bool(prev and prev.get("solution"))
    last_error = None

    for model in config.GEMINI_MODELS:
        feedback = ""
        for attempt in range(3):
            try:
                resp = client.models.generate_content(
                    model=model,
                    contents=prompt + feedback,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json", temperature=1.0),
                )
                ep = json.loads(resp.text)
                problems = validate(ep, needs_reveal)
                if not problems:
                    print(f"[story] written by {model} (attempt {attempt + 1})")
                    return ep
                last_error = "; ".join(problems)
                print(f"[story] {model} attempt {attempt + 1} rejected: {last_error}")
                feedback = ("\n\nYOUR PREVIOUS ANSWER WAS REJECTED FOR: " + last_error
                            + ". Fix these problems and return the full JSON again.")
            except Exception as exc:  # rate limit, unknown model, bad JSON ...
                last_error = f"{type(exc).__name__}: {exc}"
                print(f"[story] {model} attempt {attempt + 1} failed: {last_error}")
                if "404" in str(exc) or "not found" in str(exc).lower():
                    break  # model name not available, try the next one
                time.sleep(20 * (attempt + 1))
    raise RuntimeError(f"Could not write the episode: {last_error}")
