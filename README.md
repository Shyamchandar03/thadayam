# தடயம் (Thadayam): automatic daily Tamil detective Shorts

Every day GitHub Actions runs this project and makes one finished episode:

1. **Story:** Gemini (free tier) writes a new fair-play mystery in spoken Tamil. It has 3 suspects, 3 clues and a question to the audience. From episode 2 on, it opens by revealing yesterday's answer and thanking the viewers who solved it.
2. **Voice:** Gemini's voice (`Charon`, deep and calm) reads it as நிழல், using the same `GEMINI_API_KEY`. The free tier allows 10 voice requests a day per model, so when one model runs out the next is used (3.8 → 3.1 → 2.5). After that it tries ElevenLabs (if `ELEVENLABS_API_KEY` is set), then Microsoft Edge TTS, then Google TTS. Change the voice with `GEMINI_TTS_VOICE` (e.g. Algenib, Orus, Fenrir) and the delivery with `GEMINI_TTS_STYLE`; keep the style short ("Say in a … voice"), because a long instruction gets read aloud.
3. **Images:** Pollinations generates a free AI still for every scene, plus a gender-matched portrait for each suspect, shown as a case-file photo. If the image service is down, a drawn backdrop and a drawn man or woman figure are used instead.
   **Stock video:** Gemini marks concrete words in the narration (palace, temple, rain, key...). The matching Pexels or Pixabay clip cuts in the moment the voice says that word.
4. **Edit:** Pillow draws the Tamil text and FFmpeg builds the video:
   - camera moves (push, pull, pan, tilt) with a handheld drift, falling rain, film grain, light flicker
   - subtitles timed to the voice
   - suspect photo cards that slide in, suspect and clue tags
   - a progress bar
   - a suspense score and sound effects composed in code (whoosh, impact, thunder, camera click, heartbeat, riser), so there are no copyright issues. Put your own tracks in `assets/music/` or effects in `assets/sfx/` (`whoosh.wav`, `impact.wav`...) to replace them
   - loudness set to −14 LUFS
5. **Publish:** uploads to YouTube Shorts and, if enabled, posts to Instagram Reels.
6. **Remember:** saves the case and its secret answer in `state/episodes.json` for tomorrow's reveal.

Total cost: ₹0.

---

## Setup (about 30 minutes, one time)

### 1. Create the repository
- Create a **private** GitHub repository. It must be private: `state/episodes.json` holds each case's answer, and viewers must not find it.
- Upload this folder to the repository.
- A daily run takes about 6–10 minutes. Private repositories get 2,000 free Actions minutes a month, so this uses well under half.

### 2. Gemini API key (story writer)
1. Go to https://aistudio.google.com/apikey and click **Create API key**.
2. In the repository, go to **Settings → Secrets and variables → Actions → New repository secret**.
3. Add the key with the name `GEMINI_API_KEY`.

### 2b. Optional keys (better video)
| Secret | Where | What it adds |
|---|---|---|
| `ELEVENLABS_API_KEY` | elevenlabs.io → Profile → API keys | The best narrator voice. The free plan has 10,000 credits a month (about 8–10 episodes); after that Edge TTS takes over by itself |
| `PEXELS_API_KEY` | pexels.com/api | Real stock video on spoken words |
| `PIXABAY_API_KEY` | pixabay.com/api/docs | Backup source for stock video |

### 3. YouTube upload
1. Go to https://console.cloud.google.com and create a new project.
2. Enable **YouTube Data API v3**.
3. Set up the **OAuth consent screen**:
   - choose **External**,
   - add your Gmail as a test user,
   - then click **Publish app** so the status is **In production**. If you skip this, the token stops working after 7 days.
4. Go to **Credentials → Create credentials → OAuth client ID → Desktop app**, then download the JSON file.
5. On your PC, run:
   ```
   pip install google-auth-oauthlib
   python tools/get_youtube_token.py client_secret_xxx.json
   ```
   When Google shows an "unverified app" warning, click **Advanced → Continue**. This is your own app.
6. Add the three printed values as secrets: `YT_CLIENT_ID`, `YT_CLIENT_SECRET` and `YT_REFRESH_TOKEN`.

> **Important: YouTube's private lock.** YouTube keeps every video uploaded through a new, unaudited API project **private**, and you cannot switch those videos to public. To lift the lock, submit the free **YouTube API Services audit** form (search "YouTube API Services Audit and Quota Extension Form"). Describe the project honestly: "uploads my own channel's daily original Tamil mystery Shorts". Until the audit is approved, use one of these options:
> - download the video from the run's **Artifacts** and post it from the YouTube app, or
> - leave the YouTube secrets empty and post manually.

### 4. Instagram Reels (optional)
1. Switch your Instagram account to **Professional (Creator)**.
2. Link it to a Facebook Page.
3. Create an app at https://developers.facebook.com and add the Instagram API.
4. Get a long-lived access token. A System User token from Meta Business settings does not expire.
5. Add the secrets `IG_USER_ID` and `IG_ACCESS_TOKEN`.
   - Tokens from **Instagram Login** (they start with `IGAA`) cannot send the file directly; Instagram must download it from a link. The video is therefore placed on a temporary public host (uguu.se, then litterbox.catbox.moe, then 0x0.st) that deletes it within 24 hours. Set `IG_TEMP_HOST` to change the order, or `IG_VIDEO_URL` if you host the file yourself.
6. Under **Variables**, set `INSTAGRAM_AUTOPUBLISH` = `true`. It is off by default because Instagram posts go public right away. Watch your first few episodes before you turn it on.

### 5. Test it
1. Open the **Actions** tab and select **Daily Thadayam episode**.
2. Click **Run workflow** and tick **mock**.
3. This builds the sample episode without any keys. Download it from **Artifacts** and watch it.
4. Then run it again without mock, with **skip_upload** ticked. This tests the real story, voice and images without posting anything.

After that it runs by itself every day at about **5 PM IST**. To change the time, edit the `cron` line in `.github/workflows/daily-episode.yml`. The cron time is in UTC; IST is UTC + 5:30.

---

## Daily routine (optional, 1 minute)
- Solvers are thanked automatically: the next episode scans the previous YouTube video's comments for the culprit's name.
- If someone solved it on Instagram, you can thank them too. Either:
  - type their names into `state/shoutouts.txt` (one per line, works from the GitHub mobile app), or
  - enter them in the **shoutouts** box when you start a run manually.

  The names are cleared after they are used.

## Settings (repository Variables)
| Variable | Default | What it does |
|---|---|---|
| `YOUTUBE_PRIVACY` | `private` | Set to `public` once your API audit is approved |
| `INSTAGRAM_AUTOPUBLISH` | `false` | Set to `true` to auto-post Reels |
| `TTS_VOICE` | `ta-IN-ValluvarNeural` | Use `ta-IN-PallaviNeural` for a female narrator |
| `GEMINI_MODEL` | `gemini-flash-latest,…` | Comma-separated list of models; the first one that works is used |

## Staying monetizable
YouTube penalizes mass-produced "inauthentic" content. To stay on the right side of that:
- **Every case is original.** The prompt bans repeats of earlier cases.
- **Viewer participation is real.** Solvers are thanked by name.
- **AI use is disclosed.** The upload marks the video as synthetic media.
- **Review before publishing.** Watch the first episodes yourself, and improve the prompt in `thadayam/story.py` whenever a story feels weak.

## Files
```
thadayam/story.py      Gemini prompt + validation (edit this to change the show's style)
thadayam/voice.py      Tamil voice
thadayam/images.py     AI stills + noir grade + fallback backdrop
thadayam/render.py     the automatic editor (text layers, motion, music, mix)
thadayam/youtube.py    upload + solver detection
thadayam/instagram.py  Reels publishing
thadayam/main.py       runs everything in order
state/episodes.json    episode history (secret answers live here)
assets/fonts/          Noto Sans Tamil (SIL Open Font License)
```

## Run on your PC (Windows)
The on-screen text is **Tanglish** by default (`ON_SCREEN_TEXT=tanglish`), so it runs on plain Windows. The narration voice stays Tamil.

1. Install **Python 3.11+** from python.org. Tick "Add to PATH" during setup.
2. Install FFmpeg: open PowerShell, run `winget install Gyan.FFmpeg`, then **close and reopen** VS Code.
3. In the VS Code terminal, inside the project folder, run:
   ```
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   copy .env.example .env
   ```
4. Open `.env` and paste in your keys.
5. Run it with one of these:
   - `python run_local.py --mock` makes an offline test video with no keys.
   - `python run_local.py --preview` makes the real episode but posts nothing.
   - `python run_local.py` makes the episode and posts it to YouTube and Instagram.

Turn off the GitHub schedule so episodes aren't posted twice. Go to **Actions → the workflow → ⋯ → Disable workflow**. Episode history is kept in `state/episodes.json` on your PC.
