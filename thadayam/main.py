"""One run = one episode: write -> voice -> images -> edit -> publish -> remember.

    python -m thadayam.main            # real run (needs API keys)
    MOCK=true python -m thadayam.main  # offline test with the sample story
"""
import datetime as dt
import json
import os
import shutil
import sys

from . import audio, broll, config, images, instagram, render, state, story, voice, youtube


def description_text(ep: dict, number: int, stock: bool = False) -> str:
    lines = [ep.get("description", ""), ""]
    clues = [s.get("narration", "") for s in ep["scenes"] if s.get("type") == "clue"]
    if clues:
        lines.append("🔍 தடயங்கள்:")
        lines += [f"{i}. {c}" for i, c in enumerate(clues, 1)]
        lines.append("")
    lines += [f"❓ குற்றவாளி யார்? எந்த தடயம் சொல்லுது? கமெண்ட்ல சொல்லுங்க.",
              f"✅ பதில் நாளைய எபிசோடில், சரியா சொன்னவங்க பேரோட!",
              "", f"{config.SERIES_NAME} ({config.SERIES_NAME_EN}) · கோப்பு #{number:02d}",
              "AI-assisted voice and visuals. All characters and events are fictional.",
              *(["Stock footage: Pexels / Pixabay."] if stock else []),
              "", " ".join(ep.get("hashtags", []))]
    return "\n".join(lines)


def publish(final, ep: dict, desc: str, record: dict) -> list[str]:
    """Post to YouTube and Instagram; fills record's ids and returns the error messages."""
    errors = []
    if record.get("youtube_id"):
        print(f"[main] already on YouTube: {record['youtube_id']}")
    elif youtube.enabled():
        try:
            record["youtube_id"] = youtube.upload(final, ep["youtube_title"], desc, ep.get("hashtags", []))
        except Exception as exc:
            errors.append(f"YouTube: {exc}")
    else:
        print("[main] YouTube secrets not set, skipping")
    if record.get("instagram_id"):
        print(f"[main] already on Instagram: {record['instagram_id']}")
    elif instagram.enabled():
        try:
            caption = ep.get("instagram_caption", "") + "\n\n" + " ".join(ep.get("hashtags", []))
            record["instagram_id"] = instagram.publish_reel(final, caption)
        except Exception as exc:
            errors.append(f"Instagram: {exc}")
    else:
        print("[main] Instagram auto-publish off, skipping")
    return errors


def publish_existing() -> int:
    """Post an episode that is already built, unchanged, instead of making a new one.

    - The last remembered episode is missing a platform (e.g. Instagram failed): retry only
      that platform, so YouTube does not get a second copy.
    - Otherwise: post the episode a --preview run built (out/episode_NNN) and remember it."""
    st = state.load()
    last = state.last_episode(st)
    retry = bool(last and not (last.get("youtube_id") and last.get("instagram_id"))
                 and ((youtube.enabled() and not last.get("youtube_id"))
                      or (instagram.enabled() and not last.get("instagram_id"))))
    number = last["number"] if retry else state.next_number(st)
    work = config.OUT_DIR / f"episode_{number:03d}"
    final = work / f"thadayam_{number:03d}.mp4"
    if not (final.exists() and (work / "script.json").exists()):
        print(f"[main] no finished video at {final}. Run with --preview first.")
        return 1
    ep = json.loads((work / "script.json").read_text(encoding="utf-8"))
    if retry:
        record = last
        missing = [p for p, k in (("YouTube", "youtube_id"), ("Instagram", "instagram_id")) if not record.get(k)]
        print(f"=== retrying {' + '.join(missing)} for episode #{number}: {ep['title']} ===")
    else:
        today = dt.datetime.now(dt.timezone(dt.timedelta(hours=5, minutes=30))).date().isoformat()
        print(f"=== publishing the existing episode #{number}: {ep['title']} ===")
        record = {"number": number, "date": today, "title": ep["title"], "title_en": ep.get("title_en", ""),
                  "solution": ep["solution"], "youtube_id": None, "instagram_id": None,
                  "suspects": [s.get("person") for s in ep["scenes"] if s.get("type") == "suspect"],
                  "solvers_thanked": []}
    stock = any(work.glob("broll_*.mp4"))
    errors = publish(final, ep, description_text(ep, number, stock=stock), record)
    if retry:
        state.save(st)                                       # record is the stored entry
    elif record["youtube_id"] or record["instagram_id"]:     # posted somewhere: remember it
        st["episodes"].append(record)
        state.save(st)
        state.clear_manual_shoutouts()
    else:
        print("[main] nothing was posted, so the episode is not saved to the history")
    yt = f"https://youtube.com/shorts/{record['youtube_id']}" if record["youtube_id"] else "not uploaded"
    summary(f"## Published #{number:02d}: {ep['title']}\n- YouTube: {yt}\n"
            f"- Instagram: {record['instagram_id'] or 'not posted'}")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    return 0


def clear_folder(work) -> None:
    """Empty the episode folder. On Windows, OneDrive or an open Explorer / video player
    can lock the folder itself, so files are removed one by one and the folder is reused."""
    work.mkdir(parents=True, exist_ok=True)
    for item in work.iterdir():
        try:
            shutil.rmtree(item) if item.is_dir() else item.unlink()
        except OSError as exc:
            # a locked old file is overwritten later anyway; only warn
            print(f"[main] could not delete {item.name} ({exc.strerror}), will overwrite it")


def summary(md: str) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(md + "\n")
    print(md)


def main() -> int:
    st = state.load()
    number = state.next_number(st)
    prev = state.last_episode(st)
    today = dt.datetime.now(dt.timezone(dt.timedelta(hours=5, minutes=30))).date().isoformat()
    print(f"=== {config.SERIES_NAME_EN} episode #{number} ({today}) mock={config.MOCK} ===")

    # 1. Who solved yesterday's case?
    solvers = state.manual_shoutouts()
    if prev and prev.get("youtube_id") and not config.MOCK:
        aliases = (prev.get("solution") or {}).get("culprit_aliases") or \
                  [(prev.get("solution") or {}).get("culprit", "")]
        for name in youtube.solvers(prev["youtube_id"], aliases):
            if name not in solvers:
                solvers.append(name)
    print(f"[main] solvers: {solvers or 'none'}")

    # 2. Story
    history = [e.get("title_en") or e.get("title", "") for e in st["episodes"]]
    ep = story.generate(number, history, prev, solvers)
    if config.MOCK and number > 1:
        ep["youtube_title"] = ep["youtube_title"].replace("#01", f"#{number:02d}")

    work = config.OUT_DIR / f"episode_{number:03d}"
    clear_folder(work)
    (work / "script.json").write_text(json.dumps(ep, ensure_ascii=False, indent=2), encoding="utf-8")

    # 3. Voice (with timing, so cuts can land on spoken words)
    scenes = ep["scenes"]
    voices, speeches = [], []
    for i, scene in enumerate(scenes):
        path = work / f"voice_{i:02d}.mp3"
        speeches.append(voice.synthesize(
            scene["narration"], path,
            previous=scenes[i - 1]["narration"] if i else "",
            following=scenes[i + 1]["narration"] if i + 1 < len(scenes) else ""))
        voices.append(speeches[-1].path)
    n = len(scenes)
    sdurs = [render.scene_duration(s.duration, i == n - 1) for i, s in enumerate(speeches)]
    total = sum(sdurs)
    print(f"[main] runtime {total:.1f}s")

    # 4. Images. People first (Nizhal, then the suspects) so they get the free image quota
    # before the backgrounds; then scene stills and stock video on spoken words.
    cards = [None] * n
    nizhal_card = work / "nizhal.png"
    if images.make_nizhal_card(nizhal_card):
        for i, scene in enumerate(scenes):
            if scene.get("type") == "case":          # "நான் நிழல்": he introduces himself
                cards[i] = nizhal_card
    suspect_no = 0
    for i, scene in enumerate(scenes):
        if scene.get("type") == "suspect":
            suspect_no += 1
            cards[i] = work / f"suspect_{suspect_no}.png"
            images.make_suspect_card(scene.get("person") or {}, suspect_no, number, cards[i])
    ai_count = 0
    stills, brolls = [], []
    for i, scene in enumerate(scenes):
        path = work / f"image_{i:02d}.jpg"
        ai_count += images.make_scene_image(scene, i, number, path)
        stills.append(path)
        cuts = []
        for c_i, cue in enumerate(scene.get("broll") or []):
            pos = scene["narration"].find(cue["word"])
            clip = work / f"broll_{i:02d}_{c_i}.mp4"
            if pos >= 0 and broll.fetch(cue["query"], clip):
                cuts.append((0.15 + speeches[i].time_at(pos), clip))
        brolls.append(cuts)
    print(f"[main] AI images: {ai_count}/{n}, stock clips: {sum(map(len, brolls))}")

    # 5. Edit
    clips, events, start = [], [], 0.0
    for i, scene in enumerate(scenes):
        clip, d, cues = render.render_scene(work, i, scene, stills[i], speeches[i], start, total,
                                            number, i == n - 1, card=cards[i], brolls=brolls[i])
        clips.append(clip)
        events += [(start + at, name) for at, name in cues]
        start += d
    mix = audio.build(work, voices, sdurs, [s["type"] for s in scenes], events, seed=number)
    final = work / f"thadayam_{number:03d}.mp4"
    render.assemble(work, clips, mix, final)
    render.thumbnail(final, work / "thumbnail.jpg")
    print(f"[main] video ready: {final}")

    # 6. Publish
    record = {"number": number, "date": today, "title": ep["title"], "title_en": ep.get("title_en", ""),
              "solution": ep["solution"], "youtube_id": None, "instagram_id": None,
              "suspects": [s.get("person") for s in scenes if s.get("type") == "suspect"],
              "solvers_thanked": solvers}
    desc = description_text(ep, number, stock=any(brolls))
    if config.SKIP_UPLOAD or config.MOCK:
        print("[main] upload skipped")
        errors = []
    else:
        errors = publish(final, ep, desc, record)

    # 7. Remember (even if an upload failed, so the story continues tomorrow). A preview
    # (SKIP_UPLOAD) is not remembered: nobody saw it, so tomorrow must not reveal it.
    if not (config.MOCK or config.SKIP_UPLOAD):
        st["episodes"].append(record)
        state.save(st)
        state.clear_manual_shoutouts()

    yt = f"https://youtube.com/shorts/{record['youtube_id']}" if record["youtube_id"] else "not uploaded"
    summary(f"## {config.SERIES_NAME} கோப்பு #{number:02d}: {ep['title']}\n"
            f"- Runtime: {total:.0f}s, AI images {ai_count}/{n}\n- YouTube: {yt}\n"
            f"- Instagram: {record['instagram_id'] or 'not posted'}\n"
            f"- Answer (secret): {ep['solution']['culprit']}\n"
            f"- Download the video from this run's **Artifacts**.")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
