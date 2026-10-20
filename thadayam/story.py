"""Writes each episode with the Gemini API (free tier) as strict JSON."""
import json
import re
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
- Exactly 3 clues.
- Do NOT repeat these earlier cases: {history}

DIFFICULTY (this is a HARD puzzle: most viewers should guess WRONG; only a viewer who
pauses, replays and thinks should solve it)
- FAIR PLAY STILL: every fact needed to solve it is said out loud in the episode. No
  secret twins, hidden passages, or facts that appear only in the solution.
- NO SINGLE CLUE SOLVES IT. The answer appears only when the viewer COMBINES two pieces:
  a clue plus a small detail a suspect said in their own alibi, or two clues together
  (time arithmetic, a sequence of events, cause and effect).
- The giveaway is a quiet, ordinary-sounding detail, not a dramatic one. Good kinds of
  giveaway: a suspect's alibi mentions something they could only know if they were at the
  scene; a time that does not add up when you do the maths; physical common sense (ice
  melts, wet paint, tea goes cold, mud dries, a phone at five percent battery, a power cut
  stops a fan, a train or bus time, a temple bell or a festival on a fixed day, which side
  the sun rises); something that should have happened but did NOT (the dog did not bark).
- Plant the giveaway early, inside a SUSPECT scene, buried mid-sentence among other
  harmless details, so viewers have forgotten it by the clues.
- EVERY suspect has a motive AND a real opportunity, and each looks guilty for a moment.
- RED HERRING: one clue must point strongly at an INNOCENT suspect, and should be the
  most memorable clue. The culprit is never the person who held the key, was last seen
  near the item, had the weakest alibi, or seems the "obvious" choice.
- The culprit should seem the LEAST likely at first glance (helpful, has a strong alibi,
  or even the one who reported the crime), but never chosen at random: the logic must
  point to them and only them.
- The decisive clue must NOT be the third (last) clue, must NOT name the culprit, and
  must be narrated in exactly the same flat tone as the other clues.
- NEVER hint in the narration: no "கவனிச்சீங்களா", "ஏதோ ஒன்னு இடிக்குது", "something is
  off", "இது முக்கியம்", "நான் கவனமா பார்த்தேன்", no stressing a word, no rhetorical
  question that points at a clue. Shadow states facts; he does not comment on them.
- Before answering, test it yourself: if a viewer remembers only ONE clue, who would they
  accuse? That person must be innocent. If the answer is obvious within 10 seconds of the
  clues, make it harder.

LANGUAGE
- All narration and on-screen text in natural spoken Tamil (Tamil script), the way a
  storyteller from Chennai talks: simple, clear, punchy short sentences. Common English
  words people say in Tamil (CCTV, phone, office) may stay in English letters.
- Write numbers and times as words so the voice reads them correctly.
- The whole narration together must be 650 to 950 Tamil characters (about 70-85 seconds).

SCENE ORDER (the "scenes" list)
1. "hook"    - ALWAYS the very first scene. See THE HOOK below.
{reveal_rule}2. "case"    - "நான் {investigator}." + place, time, what happened.
3-5. "suspect" x3 - who they are and their claim/alibi. on_screen: "சந்தேக நபர் N: name (role)".
6-8. "clue" x3   - one clue each. on_screen: "தடயம் N".
9. "cta"     - ask who did it AND which clue proves it; tell viewers to comment; promise to
   say the names of correct solvers tomorrow. on_screen: the big question (max 6 words).

THE HOOK (the most important part: viewers decide in the first 3 seconds whether to swipe)
- The FIRST sentence is spoken in under 3 seconds: at most 6 Tamil words / 40 characters.
  It must land the single most shocking, impossible or high-stakes fact of today's case.
- Start in the middle of the action. NEVER open with a greeting, the series name, the
  investigator's name, "ஒரு ஊர்ல", "இன்னைக்கு", a date, a place description or any setup.
- Then 1 or 2 more very short sentences (whole hook at most 150 characters) that open a loop
  the viewer can only close by watching to the end: a contradiction, a ticking clock, an
  impossible detail, or a direct challenge to the viewer.
- Today's hook style: {hook_style}
- on_screen: the hook's core in at most 5 words, readable in one glance (a number, a
  contradiction or a question works best). The youtube_title should use the same hook.

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
    "key_clue": "the decisive clue, one Tamil line",
    "deduction_steps": ["2 to 4 short ENGLISH steps: which two facts combine and why"],
    "red_herring": "ENGLISH: which clue points at which innocent suspect, and why it is wrong",
    "why_not_others": "ENGLISH: one line per innocent suspect proving they could not have done it"
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

REVEAL_RULE = """1b. "reveal" - SECOND scene, right after the hook, under 15 seconds: solve YESTERDAY's case.
   Open it with one bridge line like "ஆனா முதல்ல, நேற்றைய கேஸ்..." so it does not break
   the hook's tension. Yesterday's case: "{prev_title}". Culprit: {prev_culprit}.
   Why: {prev_explanation}
   {solver_line}
   End by jumping back into today's case. on_screen: "நேற்றைய பதில்: {prev_culprit}".
"""

# Rotated by episode number so the openings don't all sound alike.
HOOK_STYLES = [
    "an impossible fact (something that cannot have happened, but did)",
    "a ticking clock (a number of minutes or seconds that changed everything)",
    "a direct challenge to the viewer (most people miss the clue in this case; will you?)",
    "a contradiction (two facts that cannot both be true)",
    "the stakes first (what was lost and what it was worth, in one breath)",
    "a strange object or detail found at the scene that makes no sense yet",
]

HOOK_FIRST_SENTENCE_MAX = 55      # characters; the prompt asks for 40, this leaves slack
HOOK_MAX = 190

# Narrator comments that give the puzzle away (Tamil script and Tanglish subtitles).
HINT_PHRASES = ["இடிக்குது", "கவனிச்சீங்களா", "கவனமா பார்த்தேன்", "இது முக்கியம்",
                "idikkudhu", "idikudhu", "kavanichingala", "kavanamaa paarthen",
                "kavanama parthen", "idhu mukkiyam", "something is off"]


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
        hook_style=HOOK_STYLES[number % len(HOOK_STYLES)],
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
    if not types or types[0] != "hook":
        problems.append("first scene must be hook")
    else:
        hook = scenes[0].get("narration", "").strip()
        first = re.split(r"[.?!।]", hook, maxsplit=1)[0].strip()
        if len(first) > HOOK_FIRST_SENTENCE_MAX:
            problems.append(f"the hook's first sentence is {len(first)} characters; it must be "
                            f"spoken in under 3 seconds (at most 40 characters)")
        if len(hook) > HOOK_MAX:
            problems.append(f"the hook is {len(hook)} characters; keep it under 150")
        if config.INVESTIGATOR in first or config.SERIES_NAME in first:
            problems.append("the hook must not open with the series or investigator name")
    if needs_reveal and (len(types) < 2 or types[1] != "reveal"):
        problems.append("second scene must be reveal (right after the hook)")
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
    sol = ep.get("solution") or {}
    if not sol.get("culprit"):
        problems.append("missing solution.culprit")
    if len(sol.get("deduction_steps") or []) < 2 or not sol.get("red_herring"):
        problems.append("solution needs deduction_steps (2+ steps combining facts) and red_herring")
    told = " ".join(s.get("narration", "") + " " + s.get("subtitle", "")
                    for s in scenes if s.get("type") in ("suspect", "clue")).lower()
    hints = [h for h in HINT_PHRASES if h in told]
    if hints:
        problems.append(f"the narration hints at the answer ({', '.join(hints)}); state the "
                        f"facts flatly with no comments")
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
