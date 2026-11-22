import json
import random
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).resolve().parent
MOVIES_PATH = BASE_DIR / "data" / "movies.json"
STATIC_DIR = BASE_DIR / "static"

INDUSTRY_LABELS = {
    "bollywood": "Bollywood",
    "hollywood": "English",
    "kannada": "Kannada",
}


def load_movies() -> list[dict]:
    movies = json.loads(MOVIES_PATH.read_text())
    return [
        {"industry": m["industry"], "name": m["name"], "year": m["year"], "videoId": m["videoId"]}
        for m in movies
        if m.get("videoId")
    ]


MOVIES = load_movies()

app = FastAPI(title="Diwali Potluck Charades")


@app.middleware("http")
async def revalidate_static(request: Request, call_next):
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache"
    return response


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok", "movies": len(MOVIES)}


@app.get("/api/catalog")
def catalog() -> dict:
    industries = []
    for industry_id, label in INDUSTRY_LABELS.items():
        years = sorted({m["year"] for m in MOVIES if m["industry"] == industry_id})
        if years:
            count = sum(1 for m in MOVIES if m["industry"] == industry_id)
            industries.append({"id": industry_id, "label": label, "count": count, "years": years})
    return {"industries": industries}


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
    if not in_range:
        raise HTTPException(status_code=404, detail="No movies for that language and era")

    seen = set(filter(None, exclude.split(",")))
    pool = [m for m in in_range if m["videoId"] not in seen]
    exhausted = not pool
    movie = random.choice(pool or in_range)
    return {**movie, "remaining": max(len(pool) - 1, 0), "total": len(in_range), "exhausted": exhausted}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
