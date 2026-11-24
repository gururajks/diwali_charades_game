# Diwali Games - Guru, Suhasini & Arnav

Mobile-friendly party games. Switch games from the left sidebar (the ☰ button
on phones):

- **Charades**: each round shows a movie name and an embedded YouTube clip.
- **Lost in Translation — Famous Hits Edition**: 25 famous Hindi and Kannada
  movie and song titles, translated literally into English. Guess the original.
- **Guess the Song**: 500 popular Bollywood and Kannada film songs from the
  80s to today. The song plays with the video covered; guess it, then reveal.

FastAPI backend, plain HTML/JS frontend, no database, no API keys. Runs on
Google Cloud Run.

## Charades

Pick a language:

| Language  | Movies | Years     |
|-----------|--------|-----------|
| Bollywood | 226    | 1990-2026 |
| English   | 200    | 1990-2009 |
| Kannada   | 102    | 1990-2026 |

How to play:

1. Pick a language (Bollywood, English, Kannada) and optionally an era.
2. Hand the phone to the actor and tap **Next movie**. The card is covered and
   the clip starts playing.
3. The actor taps **Tap to show**, watches the clip and reads the name, then taps
   **Hide** so nobody else can peek.
4. Start the timer and act it out.

Movies don't repeat on a device until every movie in that language and era has
been shown. On phones that block autoplay with sound, the clip starts muted with
a **Tap for sound** button.

## Lost in Translation

Each card shows the category and the English clue. Tap **Reveal** on a card to
show its answer, or use **Reveal all** and **Hide all answers**. The clues and
answers live in `app/data/lost_in_translation.json`; edit that file to change
the questions.

## Guess the Song

Pick Bollywood or Kannada and optionally a decade. Each language has 50 songs
per decade (80s, 90s, 2000s, 2010s, 2020s).

1. Tap play. The official song video plays from the start, covered so the title
   and actors stay hidden. **Restart** and **Skip 10s** help with slow intros.
2. Once everyone has guessed, tap **Reveal answer** to show the song, film,
   year, music director and singers, and uncover the video.
3. Tap **Play next song**.

Songs don't repeat on a device until every song in that language has played.

The songs were picked from Wikipedia soundtrack listings (titles, singers and
music directors) ranked by YouTube views, then checked by hand.

## Project layout

```
app/
  main.py                  FastAPI app (API + static files)
  data/sources/*.json      curated movie lists, one file per language
                           (name, year, optional "query")
  data/movies.json         generated: all movies with YouTube video IDs
  data/overrides.json      manual {"language": {"Name (Year)": "videoId"}} fixes
  data/lost_in_translation.json  Lost in Translation clues and answers
  data/song_sources/*.json curated song lists, one file per language
                           (title, film, year, music, singers, optional "query")
  data/songs.json          generated: all songs with YouTube video IDs
  data/song_overrides.json manual {"language": {"Title (Film)": "videoId"}} fixes
  static/                  index.html, styles.css, nav.js (sidebar and game
                           switching), youtube.js (shared YouTube API loader),
                           app.js (Charades), translation.js, songs.js
scripts/resolve_videos.py  finds movie clip IDs with yt-dlp (no API key)
scripts/resolve_songs.py   finds official song video IDs with yt-dlp
```

## Run locally

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/uvicorn app.main:app --reload --port 8080
```

Open http://localhost:8080. To try it on your phone, use your computer's LAN IP
and add `--host 0.0.0.0`.

## Adding movies or fixing clips

1. Add `{"name": "...", "year": 2026}` to the right file in `app/data/sources/`
   (`bollywood.json`, `hollywood.json` or `kannada.json`). A new file such as
   `tamil.json` adds a new language; give it a label in `INDUSTRY_LABELS` in
   `app/main.py`.
2. Resolve only what's new:

   ```bash
   .venv/bin/python scripts/resolve_videos.py --only-missing
   ```

If a clip is wrong, either:

- add a `"query"` to that movie in its source file (e.g. include the lead
  actors) and rerun with `--only-missing --refresh "Movie Name"` (use
  `--refresh "kannada/Movie Name"` if the name exists in more than one language), or
- pin a specific video in `app/data/overrides.json`, e.g.
  `{"kannada": {"Duniya (2007)": "X8pMaICmsJE"}}`, then rerun with `--only-missing`.

The resolver only keeps videos whose owners allow embedding (checked through
YouTube's oEmbed endpoint).

## Adding songs or fixing song videos

Songs work the same way. Add `{"title": "...", "film": "...", "year": 2026,
"music": "...", "singers": ["..."]}` to `app/data/song_sources/bollywood.json`
or `kannada.json`, then run:

```bash
.venv/bin/python scripts/resolve_songs.py --only-missing
```

The song resolver skips remixes, covers, jukeboxes, dubbed versions and remakes,
and prefers official label uploads that name the film. At the end it lists songs
it couldn't find and songs worth a manual check (the video title doesn't name
the film, or the channel isn't a known music label). To fix one, add a `"query"`
and rerun with `--only-missing --refresh "Song Title"`, or pin a video in
`app/data/song_overrides.json`, e.g. `{"kannada": {"Anisuthide (Mungaru Male)": "videoId"}}`.

## Deploy to Cloud Run

One-time setup:

```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com
```

Deploy (builds from the `Dockerfile` with Cloud Build):

```bash
gcloud run deploy diwali-charades \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --min-instances 0 \
  --max-instances 3 \
  --memory 256Mi
```

The command prints the public URL. Redeploy with the same command after any change.

A Cloud Build trigger on this repo runs the same deploy from `cloudbuild.yaml`
on every push to `main`.

## Docker (optional local check)

```bash
docker build -t diwali-charades .
docker run --rm -p 8080:8080 diwali-charades
```
