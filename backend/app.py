from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .assets import import_scene_image
from .scheduler import build_scheduler
from .selector import current_week_id, select_weekly_characters
from .storage import (
    BASE_DIR,
    append_generation_log,
    ensure_data_files,
    read_json,
    write_json,
)
from .story_builder import build_weekly_pack, regenerate_pack_prompts


FRONTEND_DIR = BASE_DIR / "frontend"
ASSET_DIR = BASE_DIR / "data" / "assets"


class SessionAnswer(BaseModel):
    char: str
    known: bool
    at: str | None = None


class SessionPayload(BaseModel):
    answers: list[SessionAnswer] = Field(default_factory=list)
    known_count: int = 0
    unknown_count: int = 0
    duration_seconds: int = 0


app = FastAPI(title="Fun Hanzi")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/assets", StaticFiles(directory=ASSET_DIR), name="assets")

scheduler = None


def _pack_is_valid(pack: dict[str, Any]) -> bool:
    required = {"week_id", "title", "summary", "story", "image_tasks", "video_storyboard", "char_cards", "status"}
    return required.issubset(pack.keys()) and bool(pack.get("week_id"))


def _update_progress_with_answers(progress: dict[str, Any], answers: list[dict[str, Any]]) -> dict[str, Any]:
    items = progress.setdefault("items", {})
    for answer in answers:
        char = answer["char"]
        entry = items.get(
            char,
            {
                "box": 0,
                "lastSeen": "",
                "correctStreak": 0,
                "wrongCount": 0,
            },
        )
        if answer["known"]:
            entry["box"] = min(int(entry.get("box", 0)) + 1, 5)
            entry["correctStreak"] = int(entry.get("correctStreak", 0)) + 1
        else:
            entry["box"] = 1
            entry["correctStreak"] = 0
            entry["wrongCount"] = int(entry.get("wrongCount", 0)) + 1
        entry["lastSeen"] = datetime.now(UTC).date().isoformat()
        items[char] = entry
    return progress


def _write_weekly_progress_metadata(progress: dict, pack: dict) -> None:
    history = list(progress.get("weeklyPacks", []))
    history = [item for item in history if item.get("weekId") != pack["week_id"]]
    history.insert(
        0,
        {
            "weekId": pack["week_id"],
            "generatedAt": pack["generated_at"],
            "title": pack["title"],
            "newChars": pack["new_chars"],
            "reviewChars": pack["review_chars"],
        },
    )
    progress["weeklyPacks"] = history[:20]


def generate_weekly_pack(force: bool = False) -> dict:
    ensure_data_files()
    current_week = read_json("current_week.json")
    now = datetime.now(UTC)
    week_id = current_week_id(now)

    if not force and current_week.get("week_id") == week_id and current_week.get("status") != "failed":
        return current_week

    characters = read_json("characters.json", [])
    progress = read_json("progress.json", {"version": 1, "items": {}, "sessionHistory": [], "weeklyPacks": []})
    workflow_rules = read_json("workflow_rules.json", {})

    selection = select_weekly_characters(characters, progress, workflow_rules, now)
    if not selection["all_chars"]:
        raise HTTPException(status_code=400, detail="No characters available to build a weekly pack.")

    pack = build_weekly_pack(selection, workflow_rules, now)
    write_json("current_week.json", pack)

    _write_weekly_progress_metadata(progress, pack)
    write_json("progress.json", progress)

    append_generation_log(
        {
            "type": "generate_week",
            "week_id": pack["week_id"],
            "ran_at": datetime.now(UTC).isoformat(),
            "status": "ready",
            "title": pack["title"],
            "new_chars": pack["new_chars"],
            "review_chars": pack["review_chars"],
            "error": "",
        }
    )
    return pack


def _ensure_current_week() -> None:
    current = read_json("current_week.json")
    if (
        current.get("week_id") != current_week_id(datetime.now(UTC))
        or current.get("status") in {"empty", "failed"}
        or not _pack_is_valid(current)
    ):
        try:
            generate_weekly_pack(force=True)
        except HTTPException as exc:
            append_generation_log(
                {
                    "type": "generate_week",
                    "week_id": current_week_id(datetime.now(UTC)),
                    "ran_at": datetime.now(UTC).isoformat(),
                    "status": "failed",
                    "title": "",
                    "new_chars": [],
                    "review_chars": [],
                    "error": exc.detail,
                }
            )


@app.on_event("startup")
def on_startup() -> None:
    global scheduler
    ensure_data_files()
    _ensure_current_week()
    scheduler = build_scheduler(lambda: generate_weekly_pack(force=True))
    scheduler.start()


@app.on_event("shutdown")
def on_shutdown() -> None:
    if scheduler:
        scheduler.shutdown(wait=False)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "learn.html")


@app.get("/learn")
def learn_page() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "learn.html")


@app.get("/admin")
def admin_page() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "admin.html")


@app.get("/api/current-week")
def get_current_week() -> dict:
    current = read_json("current_week.json")
    if not _pack_is_valid(current):
        current = generate_weekly_pack(force=True)
    return current


@app.get("/api/progress")
def get_progress() -> dict:
    progress = read_json("progress.json", {"version": 1, "items": {}, "sessionHistory": [], "weeklyPacks": []})
    return {
        "progress": progress,
        "summary": {
            "tracked_chars": len(progress.get("items", {})),
            "session_count": len(progress.get("sessionHistory", [])),
            "known_total": sum(1 for item in progress.get("items", {}).values() if int(item.get("box", 0)) >= 3),
        },
    }


@app.post("/api/progress/session")
def post_progress_session(payload: SessionPayload) -> dict:
    progress = read_json("progress.json", {"version": 1, "items": {}, "sessionHistory": [], "weeklyPacks": []})
    answers = [answer.model_dump() for answer in payload.answers]
    _update_progress_with_answers(progress, answers)

    current_week = read_json("current_week.json")
    history = list(progress.get("sessionHistory", []))
    history.insert(
        0,
        {
            "startedAt": datetime.fromtimestamp(
                (datetime.now(UTC).timestamp() - payload.duration_seconds),
                tz=UTC,
            ).isoformat(),
            "finishedAt": datetime.now(UTC).isoformat(),
            "weekId": current_week.get("week_id", ""),
            "total": len(answers),
            "knownCount": payload.known_count,
            "unknownCount": payload.unknown_count,
            "durationSeconds": payload.duration_seconds,
            "answers": answers,
        },
    )
    progress["sessionHistory"] = history[:30]
    write_json("progress.json", progress)
    return {"ok": True}


@app.post("/api/admin/generate-week")
def admin_generate_week(force: bool = Query(default=False)) -> dict:
    return generate_weekly_pack(force=force)


@app.post("/api/admin/import-image")
def admin_import_image(
    week_id: str = Form(...),
    scene_id: str = Form(...),
    file: UploadFile = File(...),
) -> dict:
    return import_scene_image(week_id, scene_id, file)


@app.post("/api/admin/regenerate-prompts")
def admin_regenerate_prompts() -> dict:
    current_week = read_json("current_week.json")
    if not current_week.get("week_id"):
        raise HTTPException(status_code=404, detail="No current week pack found.")
    workflow_rules = read_json("workflow_rules.json", {})
    updated = regenerate_pack_prompts(current_week, workflow_rules)
    write_json("current_week.json", updated)
    append_generation_log(
        {
            "type": "regenerate_prompts",
            "week_id": updated["week_id"],
            "ran_at": datetime.now(UTC).isoformat(),
            "status": "ready",
            "title": updated["title"],
            "new_chars": updated["new_chars"],
            "review_chars": updated["review_chars"],
            "error": "",
        }
    )
    return updated


@app.get("/api/admin/status")
def admin_status() -> dict:
    return read_json("generation_log.json")


@app.get("/{file_path:path}")
def static_files(file_path: str) -> FileResponse:
    target = FRONTEND_DIR / file_path
    if target.is_file():
        return FileResponse(target)
    raise HTTPException(status_code=404, detail="Not found.")
