"""Resolve a YouTube video ID for every movie in app/data/sources/*.json.

Each source file is one industry (bollywood.json, hollywood.json, ...). Uses
yt-dlp search (no API key) and the public oEmbed endpoint to make sure the
chosen video allows embedding. Writes app/data/movies.json.

Usage:
    python scripts/resolve_videos.py                # resolve everything
    python scripts/resolve_videos.py --only-missing # keep existing IDs
    python scripts/resolve_videos.py --only-missing --refresh "Black"
    python scripts/resolve_videos.py --only-missing --refresh "hollywood/Soldier"

A source entry may set "query" to replace the default search text, and
overrides.json maps {"industry": {"Name (Year)": "videoId"}} to fixed IDs.
"""

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
import yt_dlp

DATA_DIR = Path(__file__).resolve().parent.parent / "app" / "data"
SOURCES_DIR = DATA_DIR / "sources"
OUTPUT_PATH = DATA_DIR / "movies.json"
OVERRIDES_PATH = DATA_DIR / "overrides.json"

SEARCH_RESULTS = 5
MAX_DURATION_SECONDS = 15 * 60

DEFAULT_QUERY = {
    "kannada": "{name} {year} kannada movie trailer",
}
FALLBACK_QUERY = "{name} {year} official trailer"

YDL_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "extract_flat": True,
    "skip_download": True,
}


def load_json(path: Path, default):
    if path.exists():
        return json.loads(path.read_text())
    return default


def load_sources() -> list[dict]:
    movies = []
    for path in sorted(SOURCES_DIR.glob("*.json")):
        for movie in load_json(path, []):
            movies.append({"industry": path.stem, **movie})
    return movies


def title_key(movie: dict) -> str:
    return f"{movie['name']} ({movie['year']})"


def movie_key(movie: dict) -> str:
    return f"{movie['industry']}/{title_key(movie)}"


def is_embeddable(video_id: str) -> bool:
    try:
        resp = requests.get(
            "https://www.youtube.com/oembed",
            params={"url": f"https://www.youtube.com/watch?v={video_id}", "format": "json"},
            timeout=10,
        )
        return resp.status_code == 200
    except requests.RequestException:
        return False


def search(query: str) -> list[dict]:
    with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
        info = ydl.extract_info(f"ytsearch{SEARCH_RESULTS}:{query}", download=False)
    return info.get("entries") or []


def base_record(movie: dict) -> dict:
    return {"industry": movie["industry"], "name": movie["name"], "year": movie["year"]}


def resolve(movie: dict) -> dict:
    template = DEFAULT_QUERY.get(movie["industry"], FALLBACK_QUERY)
    query = movie.get("query") or template.format(name=movie["name"], year=movie["year"])
    result = {**base_record(movie), "videoId": None, "videoTitle": None, "query": query}
    try:
        entries = search(query)
    except Exception as exc:  # yt-dlp raises a variety of errors
        print(f"  search failed for {movie_key(movie)}: {exc}", file=sys.stderr)
        return result

    for entry in entries:
        video_id = entry.get("id")
        duration = entry.get("duration") or 0
        if not video_id or duration > MAX_DURATION_SECONDS:
            continue
        if is_embeddable(video_id):
            result["videoId"] = video_id
            result["videoTitle"] = entry.get("title")
            break
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only-missing", action="store_true", help="only resolve movies without an ID")
    parser.add_argument("--refresh", action="append", default=[], metavar="NAME",
                        help='re-resolve "Name" or "industry/Name" even with --only-missing (repeatable)')
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    source = load_sources()
    overrides = load_json(OVERRIDES_PATH, {})
    existing = {movie_key(m): m for m in load_json(OUTPUT_PATH, [])} if args.only_missing else {}
    refresh = set(args.refresh)

    todo, done = [], {}
    for movie in source:
        key = movie_key(movie)
        override = overrides.get(movie["industry"], {}).get(title_key(movie))
        wants_refresh = movie["name"] in refresh or f"{movie['industry']}/{movie['name']}" in refresh
        if override:
            done[key] = {**base_record(movie), "videoId": override, "videoTitle": None, "query": "override"}
        elif not wants_refresh and existing.get(key, {}).get("videoId"):
            done[key] = existing[key]
        else:
            todo.append(movie)

    print(f"Resolving {len(todo)} movies ({len(done)} already known)...")
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for movie in pool.map(resolve, todo):
            key = movie_key(movie)
            done[key] = movie
            status = movie["videoId"] or "NOT FOUND"
            print(f"  {key}: {status}  {movie.get('videoTitle') or ''}")

    ordered = [done[movie_key(m)] for m in source]
    OUTPUT_PATH.write_text(json.dumps(ordered, indent=2, ensure_ascii=False) + "\n")

    missing = [movie_key(m) for m in ordered if not m["videoId"]]
    print(f"\nWrote {len(ordered)} movies to {OUTPUT_PATH}; {len(missing)} missing.")
    for key in missing:
        print(f"  missing: {key}")


if __name__ == "__main__":
    main()
