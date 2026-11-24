"""Resolve an official YouTube song video for every song in app/data/song_sources/*.json.

Each source file is one language (bollywood.json, kannada.json) holding
{"title", "film", "year", "music", "singers": [...]} entries. Searches with
yt-dlp (no API key), skips remixes, covers, jukeboxes, dubbed versions and the
like, prefers official label uploads that name the film, and checks that the
video allows embedding. Writes app/data/songs.json.

Usage:
    python scripts/resolve_songs.py                 # resolve everything
    python scripts/resolve_songs.py --only-missing  # keep existing IDs
    python scripts/resolve_songs.py --only-missing --refresh "Tujhe Dekha To"
    python scripts/resolve_songs.py --only-missing --refresh "kannada/Anisuthide"

A source entry may set "query" to replace the default search text, and
song_overrides.json maps {"language": {"Title (Film)": "videoId"}} to fixed IDs.
Songs whose video title doesn't name the film, or that aren't from a known
label channel, are listed at the end so they can be checked by hand.
"""

import argparse
import json
import math
import re
import sys
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from difflib import SequenceMatcher
from pathlib import Path

import yt_dlp

from resolve_videos import YDL_OPTS, is_embeddable, load_json

DATA_DIR = Path(__file__).resolve().parent.parent / "app" / "data"
SOURCES_DIR = DATA_DIR / "song_sources"
OUTPUT_PATH = DATA_DIR / "songs.json"
OVERRIDES_PATH = DATA_DIR / "song_overrides.json"

SEARCH_RESULTS = 8
MIN_DURATION_SECONDS = 90
MAX_DURATION_SECONDS = 10 * 60

DEFAULT_QUERY = {
    "kannada": "{title} {film} kannada video song",
}
FALLBACK_QUERY = "{title} {film} video song"

REJECT_WORDS = (
    "jukebox", "trailer", "teaser", "full movie", "scene", "reaction", "cover", "karaoke",
    "instrumental", "remix", "mix", "2 0", "3 0", "mashup", "slowed", "reverb", "lofi", "lo fi", "8d", "shorts",
    "status", "bgm", "unplugged", "recreated", "reprise", "making", "behind the scenes",
    "rehearsal", "live", "concert", "tutorial", "piano", "guitar", "flute", "violin",
    "ringtone", "whatsapp", "medley", "nonstop", "non stop", "back to back", "dj",
    "female", "male", "sad version", "dance video", "choreography", "years of",
)
OTHER_LANGUAGES = {
    "bollywood": ("tamil", "telugu", "kannada", "malayalam"),
    "kannada": ("tamil", "telugu", "hindi", "malayalam"),
}
OFFICIAL_CHANNELS = (
    "t series", "tseries", "saregama", "sony music", "sonymusic", "zee music", "tips", "yrf",
    "yash raj", "eros now", "shemaroo", "venus", "ultra", "rajshri", "times music",
    "universal music", "junglee music", "speed records", "dharma", "red chillies", "excel",
    "anand audio", "lahari", "prk audio", "sgv", "sri ganesh", "mrt music", "jhankar",
    "akash audio", "ashwini", "d beats", "a2 music", "hombale", "paramvah", "siri music",
    "aananda audio", "puneeth rajkumar", "kvn", "jayanna", "rockline",
)
VIDEO_WORDS = ("video song", "full video", "official video", "full song", "video")
# Splits "Song Name | Film | Cast - Label" into its parts.
SEPARATORS = r"\|\||[|:()\[\]\"“”‘’•/]|\s[-–—]\s|\s[-–]|[-–]\s"
FILLER_WORDS = {"and", "the", "kannada", "hindi", "movie", "film", "song", "songs", "video", "full", "hd",
                "4k", "8k", "official", "lyrical", "title", "track", "2"}


def norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text.lower()).split())


def has_phrase(text: str, phrase: str) -> bool:
    return f" {phrase} " in f" {text} "


def same_word(word: str, token: str) -> bool:
    # Tolerates transliteration differences such as "naaraz"/"naraz" or "jyothi"/"jyoti".
    if token == word or (len(word) >= 4 and token.startswith(word[:4])):
        return True
    return len(word) >= 4 and SequenceMatcher(None, word, token).ratio() >= 0.8


def words_match(name: str, text: str, share: float) -> bool:
    words = [w for w in norm(name).split() if len(w) > 2] or norm(name).split()
    tokens = norm(text).split()
    hits = sum(1 for w in words if any(same_word(w, t) for t in tokens))
    return hits >= max(1, math.ceil(len(words) * share))


def is_title_track(song: dict) -> bool:
    words = set(norm(song["title"]).split()) - FILLER_WORDS
    return bool(words) and words <= set(norm(song["film"]).split())


def names_song(song: dict, video_title: str) -> bool:
    """True if one part of the video title is the song name (not just the film name).

    A title track shares its name with the film, so its name must come first;
    otherwise "Other Song | Film" would count.
    """
    film_words = set(norm(song["film"]).split()) | FILLER_WORDS
    title_track = is_title_track(song)
    name = re.sub(r"\(?title (?:track|song)\)?", "", song["title"], flags=re.I)
    for part in re.split(SEPARATORS, video_title):
        words = set(norm(part).split())
        if not words or words <= FILLER_WORDS or (not title_track and words <= film_words):
            continue
        if words_match(name, part, 0.75):
            return True
        if title_track:
            return False
    return False


def load_sources() -> list[dict]:
    songs = []
    for path in sorted(SOURCES_DIR.glob("*.json")):
        for song in load_json(path, []):
            songs.append({"language": path.stem, **song})
    return songs


def title_key(song: dict) -> str:
    return f"{song['title']} ({song['film']})"


def song_key(song: dict) -> str:
    return f"{song['language']}/{title_key(song)}"


def search(query: str) -> list[dict]:
    with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
        info = ydl.extract_info(f"ytsearch{SEARCH_RESULTS}:{query}", download=False)
    return info.get("entries") or []


def rejected(song: dict, video_title: str) -> bool:
    own = norm(f"{song['title']} {song['film']}")
    bad = REJECT_WORDS + OTHER_LANGUAGES.get(song["language"], ())
    if any(has_phrase(video_title, w) and not has_phrase(own, w) for w in bad):
        return True
    # A different year in the title usually means a remake or a later re-recording.
    years = {int(y) for y in re.findall(r"\b(19[4-9]\d|20[0-3]\d)\b", video_title)} - {int(y) for y in re.findall(r"\d{4}", own)}
    return any(abs(y - song["year"]) > 1 for y in years)


def score(song: dict, entry: dict) -> tuple[float, bool, bool] | None:
    raw_title = entry.get("title") or ""
    video_title = norm(raw_title)
    duration = entry.get("duration") or 0
    if not (MIN_DURATION_SECONDS <= duration <= MAX_DURATION_SECONDS):
        return None
    if rejected(song, video_title) or not names_song(song, raw_title):
        return None
    channel = norm(entry.get("channel") or "")
    film_named = words_match(song["film"], video_title, 0.5)
    official = any(has_phrase(channel, c) or channel.replace(" ", "").startswith(c.replace(" ", "")) for c in OFFICIAL_CHANNELS)
    points = math.log10((entry.get("view_count") or 0) + 1)
    points += 3 if film_named else 0
    points += 3 if official else 0
    points += 2 if any(has_phrase(video_title, w) for w in VIDEO_WORDS) else 0
    points -= 1 if has_phrase(video_title, "lyrical") or has_phrase(video_title, "lyric") else 0
    return points, film_named, official


def base_record(song: dict) -> dict:
    return {
        "language": song["language"],
        "title": song["title"],
        "film": song["film"],
        "year": song["year"],
        "music": song["music"],
        "singers": song["singers"],
    }


def resolve(song: dict) -> dict:
    template = DEFAULT_QUERY.get(song["language"], FALLBACK_QUERY)
    query = song.get("query") or template.format(title=song["title"], film=song["film"])
    result = {**base_record(song), "videoId": None, "videoTitle": None, "channel": None, "query": query, "check": None}
    try:
        entries = search(query)
    except Exception as exc:  # yt-dlp raises a variety of errors
        print(f"  search failed for {song_key(song)}: {exc}", file=sys.stderr)
        return result

    ranked = sorted(
        ((s, e) for e in entries if e.get("id") and (s := score(song, e))),
        key=lambda pair: pair[0][0],
        reverse=True,
    )
    for (_, film_named, official), entry in ranked:
        if is_embeddable(entry["id"]):
            result["videoId"] = entry["id"]
            result["videoTitle"] = entry.get("title")
            result["channel"] = entry.get("channel")
            missing = [label for label, ok in (("film not in title", film_named), ("unknown channel", official)) if not ok]
            result["check"] = ", ".join(missing) or None
            break
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only-missing", action="store_true", help="only resolve songs without an ID")
    parser.add_argument("--refresh", action="append", default=[], metavar="TITLE",
                        help='re-resolve "Title" or "language/Title" even with --only-missing (repeatable)')
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    source = load_sources()
    overrides = load_json(OVERRIDES_PATH, {})
    existing = {song_key(s): s for s in load_json(OUTPUT_PATH, [])} if args.only_missing else {}
    refresh = set(args.refresh)

    todo, done = [], {}
    for song in source:
        key = song_key(song)
        override = overrides.get(song["language"], {}).get(title_key(song))
        wants_refresh = song["title"] in refresh or f"{song['language']}/{song['title']}" in refresh
        if override:
            done[key] = {**base_record(song), "videoId": override, "videoTitle": None, "channel": None,
                         "query": "override", "check": None}
        elif not wants_refresh and existing.get(key, {}).get("videoId"):
            done[key] = {**existing[key], **base_record(song)}
        else:
            todo.append(song)

    print(f"Resolving {len(todo)} songs ({len(done)} already known)...")
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for song in pool.map(resolve, todo):
            key = song_key(song)
            done[key] = song
            print(f"  {key}: {song['videoId'] or 'NOT FOUND'}  {song.get('videoTitle') or ''}")

    ordered = [done[song_key(s)] for s in source]
    OUTPUT_PATH.write_text(json.dumps(ordered, indent=2, ensure_ascii=False) + "\n")

    missing = [song_key(s) for s in ordered if not s["videoId"]]
    to_check = [s for s in ordered if s["videoId"] and s.get("check")]
    by_video = {}
    for s in ordered:
        if s["videoId"]:
            by_video.setdefault(s["videoId"], []).append(song_key(s))
    shared = [keys for keys in by_video.values() if len(keys) > 1]
    print(f"\nWrote {len(ordered)} songs to {OUTPUT_PATH}; {len(missing)} missing, {len(to_check)} to check, "
          f"{len(shared)} videos used twice.")
    for key in missing:
        print(f"  missing: {key}")
    for keys in shared:
        print(f"  same video: {', '.join(keys)}")
    for s in to_check:
        print(f"  check ({s['check']}): {song_key(s)} -> {s['videoTitle']} [{s['channel']}]")


if __name__ == "__main__":
    main()
