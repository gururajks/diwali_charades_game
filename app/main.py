import json
import random
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).resolve().parent
MOVIES_PATH = BASE_DIR / "data" / "movies.json"
SONGS_PATH = BASE_DIR / "data" / "songs.json"
TRANSLATION_PATH = BASE_DIR / "data" / "lost_in_translation.json"
STATIC_DIR = BASE_DIR / "static"

INDUSTRY_LABELS = {
    "bollywood": "Bollywood",
    "hollywood": "English",
    "kannada": "Kannada",
}

LANGUAGE_LABELS = {
    "bollywood": "Bollywood",
    "kannada": "Kannada",
}

SONG_FIELDS = ("language", "title", "film", "year", "music", "singers", "videoId")


def load_movies() -> list[dict]:
    movies = json.loads(MOVIES_PATH.read_text())
    return [
        {"industry": m["industry"], "name": m["name"], "year": m["year"], "videoId": m["videoId"]}
        for m in movies
        if m.get("videoId")
    ]


def load_songs() -> list[dict]:
    songs = json.loads(SONGS_PATH.read_text())
    return [{field: s[field] for field in SONG_FIELDS} for s in songs if s.get("videoId")]


MOVIES = load_movies()
SONGS = load_songs()
TRANSLATION_GAME = json.loads(TRANSLATION_PATH.read_text())


def summarize(items: list[dict], key: str, labels: dict[str, str]) -> list[dict]:
    groups = []
    for group_id, label in labels.items():
        years = sorted({item["year"] for item in items if item[key] == group_id})
        if years:
            count = sum(1 for item in items if item[key] == group_id)
            groups.append({"id": group_id, "label": label, "count": count, "years": years})
    return groups


def pick_unseen(candidates: list[dict], exclude: str, not_found: str) -> dict:
    if not candidates:
        raise HTTPException(status_code=404, detail=not_found)
    seen = set(filter(None, exclude.split(",")))
    pool = [item for item in candidates if item["videoId"] not in seen]
    exhausted = not pool
    item = random.choice(pool or candidates)
    return {**item, "remaining": max(len(pool) - 1, 0), "total": len(candidates), "exhausted": exhausted}


app = FastAPI(title="Diwali Games - Guru, Suhasini & Arnav")


@app.middleware("http")
async def revalidate_static(request: Request, call_next):
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache"
    return response


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok", "movies": len(MOVIES), "songs": len(SONGS)}


@app.get("/api/catalog")
def catalog() -> dict:
    return {"industries": summarize(MOVIES, "industry", INDUSTRY_LABELS)}


@app.get("/api/movie/random")
def random_movie(
    industry: str = Query("bollywood"),
    exclude: str = Query("", description="Comma-separated video IDs already seen"),
    min_year: int = Query(1900, alias="minYear"),
    max_year: int = Query(2100, alias="maxYear"),
) -> dict:
    in_range = [
        m for m in MOVIES
        if m["industry"] == industry and min_year <= m["year"] <= max_year
    ]
    return pick_unseen(in_range, exclude, "No movies for that language and era")


@app.get("/api/songs/catalog")
def songs_catalog() -> dict:
    return {"languages": summarize(SONGS, "language", LANGUAGE_LABELS)}


@app.get("/api/song/random")
def random_song(
    language: str = Query("bollywood"),
    exclude: str = Query("", description="Comma-separated video IDs already played"),
    min_year: int = Query(1900, alias="minYear"),
    max_year: int = Query(2100, alias="maxYear"),
) -> dict:
    in_range = [
        s for s in SONGS
        if s["language"] == language and min_year <= s["year"] <= max_year
    ]
    return pick_unseen(in_range, exclude, "No songs for that language and decade")


@app.get("/api/lost-in-translation")
def lost_in_translation() -> dict:
    return TRANSLATION_GAME


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
