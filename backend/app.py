from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .ai_provider import (
    ai_is_enabled,
    generate_week_content_with_ai,
    get_model_presets,
    regenerate_scene_prompts_with_ai,
    test_openrouter,
)
from .assets import import_scene_image, import_scene_video
from .scheduler import build_scheduler
from .selector import current_week_id, select_weekly_characters, shift_week_id, week_id_to_datetime
from .storage import (
    BASE_DIR,
    append_generation_log,
    ensure_data_files,
    list_week_pack_summaries,
    read_week_pack,
    read_json,
    save_week_pack,
    write_json,
)
from .story_builder import build_weekly_pack, regenerate_pack_prompts
from .worksheet import generate_handwriting_worksheet


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
    week_id: str = ""


class AISettingsPayload(BaseModel):
    provider: str = "openrouter"
    enabled: bool = False
    base_url: str = "https://openrouter.ai/api/v1"
    model: str = "openrouter/auto"
    api_key: str = ""
    api_key_env: str = "OPENROUTER_API_KEY"
    site_url: str = "http://127.0.0.1:8000"
    app_name: str = "Fun Hanzi"


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
    required = {
        "week_id",
        "title",
        "summary",
        "story",
        "image_tasks",
        "video_tasks",
        "video_storyboard",
        "audio_tasks",
        "char_cards",
        "worksheet",
        "status",
    }
    if not (required.issubset(pack.keys()) and bool(pack.get("week_id"))):
        return False

    story = pack.get("story", [])
    words = pack.get("words", [])
    char_cards = pack.get("char_cards", [])
    return all(
        [
            not story or "dialogue_line" in story[0],
            not words or ("pinyin_text" in words[0] or "pronunciation_labels" in words[0]),
            not char_cards or "sentence_pinyin" in char_cards[0],
        ]
    )


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


def generate_weekly_pack(force: bool = False, week_offset: int = 0, base_week_id: str | None = None) -> dict:
    ensure_data_files()
    current_week = read_json("current_week.json")
    if base_week_id:
        week_id = shift_week_id(base_week_id, week_offset)
        now = week_id_to_datetime(week_id)
    else:
        now = datetime.now(UTC) + timedelta(weeks=week_offset)
        week_id = current_week_id(now)

    if not force:
        if current_week.get("week_id") == week_id and current_week.get("status") != "failed":
            return current_week
        try:
            existing = read_week_pack(week_id)
        except FileNotFoundError:
            existing = None
        if existing and existing.get("status") != "failed":
            save_week_pack(existing)
            return existing

    characters = read_json("characters.json", [])
    progress = read_json("progress.json", {"version": 1, "items": {}, "sessionHistory": [], "weeklyPacks": []})
    workflow_rules = read_json("workflow_rules.json", {})
    ai_settings = read_json("ai_settings.json", {})

    selection = select_weekly_characters(characters, progress, workflow_rules, now)
    selection["character_pool"] = characters
    if not selection["all_chars"]:
        raise HTTPException(status_code=400, detail="No characters available to build a weekly pack.")

    ai_content = None
    ai_error = ""
    if ai_is_enabled(ai_settings):
        try:
            ai_content = generate_week_content_with_ai(selection, workflow_rules, ai_settings)
        except Exception as exc:  # noqa: BLE001
            ai_error = str(exc)

    pack = build_weekly_pack(selection, workflow_rules, now, ai_content=ai_content)
    pack["worksheet"] = generate_handwriting_worksheet(pack)
    pack["generation_mode"] = "ai" if ai_content else "template"
    pack["updated_at"] = datetime.now(UTC).isoformat()
    if ai_error:
        pack["generation_warning"] = ai_error
    save_week_pack(pack)

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
            "error": ai_error,
            "generation_mode": pack.get("generation_mode", "template"),
        }
    )
    return pack


def publish_week_pack(week_id: str) -> dict:
    try:
        pack = read_week_pack(week_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Week pack not found.") from exc

    now = datetime.now(UTC).isoformat()
    pack["updated_at"] = now
    pack["published_at"] = now
    save_week_pack(pack, set_current=True)
    append_generation_log(
        {
            "type": "publish_week",
            "week_id": pack["week_id"],
            "ran_at": now,
            "published_at": now,
            "status": "ready",
            "title": pack["title"],
            "new_chars": pack["new_chars"],
            "review_chars": pack["review_chars"],
            "error": "",
            "generation_mode": pack.get("generation_mode", "template"),
        }
    )
    return pack


def generate_multiple_weeks(
    *,
    count: int,
    force: bool = False,
    start_week_offset: int = 1,
    base_week_id: str | None = None,
) -> list[dict]:
    packs: list[dict] = []
    for step in range(count):
        packs.append(
            generate_weekly_pack(
                force=force,
                week_offset=start_week_offset + step,
                base_week_id=base_week_id,
            )
        )
    return packs


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
    elif current.get("week_id"):
        save_week_pack(current, set_current=False)


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


@app.get("/favicon.ico")
def favicon_ico() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "favicon.svg", media_type="image/svg+xml")


@app.get("/api/current-week")
def get_current_week(week_id: str | None = Query(default=None)) -> dict:
    if week_id:
        try:
            pack = read_week_pack(week_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Week pack not found.") from exc
        if not _pack_is_valid(pack):
            raise HTTPException(status_code=400, detail="Week pack is incomplete.")
        return pack

    current = read_json("current_week.json")
    if not _pack_is_valid(current):
        current = generate_weekly_pack(force=True)
    return current


@app.get("/api/weeks")
def get_weeks() -> dict:
    return {"weeks": list_week_pack_summaries()}


@app.get("/api/admin/ai-settings")
def get_ai_settings() -> dict:
    return {
        "settings": read_json("ai_settings.json", {}),
        "model_presets": get_model_presets(),
    }


@app.post("/api/admin/ai-settings")
def post_ai_settings(payload: AISettingsPayload) -> dict:
    settings = payload.model_dump()
    write_json("ai_settings.json", settings)
    return {
        "ok": True,
        "settings": settings,
        "model_presets": get_model_presets(),
    }


@app.post("/api/admin/test-ai")
def post_test_ai() -> dict:
    settings = read_json("ai_settings.json", {})
    return test_openrouter(settings)


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
    active_week_id = payload.week_id or current_week.get("week_id", "")
    history = list(progress.get("sessionHistory", []))
    history.insert(
        0,
        {
            "startedAt": datetime.fromtimestamp(
                (datetime.now(UTC).timestamp() - payload.duration_seconds),
                tz=UTC,
            ).isoformat(),
            "finishedAt": datetime.now(UTC).isoformat(),
            "weekId": active_week_id,
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
def admin_generate_week(
    force: bool = Query(default=False),
    week_offset: int = Query(default=0),
    count: int = Query(default=1),
    base_week_id: str | None = Query(default=None),
) -> dict:
    if count <= 1:
        return generate_weekly_pack(force=force, week_offset=week_offset, base_week_id=base_week_id)

    packs = generate_multiple_weeks(
        count=count,
        force=force,
        start_week_offset=week_offset,
        base_week_id=base_week_id,
    )
    return {
        "packs": packs,
        "last_week_id": packs[-1]["week_id"] if packs else "",
    }


@app.post("/api/admin/publish-week")
def admin_publish_week(week_id: str = Query(...)) -> dict:
    return publish_week_pack(week_id)


@app.post("/api/admin/import-image")
def admin_import_image(
    week_id: str = Form(...),
    scene_id: str = Form(...),
    file: UploadFile = File(...),
) -> dict:
    return import_scene_image(week_id, scene_id, file)


@app.post("/api/admin/import-video")
def admin_import_video(
    week_id: str = Form(...),
    scene_id: str = Form(...),
    file: UploadFile = File(...),
) -> dict:
    return import_scene_video(week_id, scene_id, file)


@app.post("/api/admin/regenerate-prompts")
def admin_regenerate_prompts(week_id: str | None = Query(default=None)) -> dict:
    current_week = read_json("current_week.json")
    target_week_id = week_id or current_week.get("week_id")
    if not target_week_id:
        raise HTTPException(status_code=404, detail="No current week pack found.")
    try:
        target_pack = current_week if current_week.get("week_id") == target_week_id else read_week_pack(target_week_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Week pack not found.") from exc
    workflow_rules = read_json("workflow_rules.json", {})
    ai_settings = read_json("ai_settings.json", {})
    ai_error = ""
    if ai_is_enabled(ai_settings):
        try:
            ai_payload = regenerate_scene_prompts_with_ai(target_pack, ai_settings)
            scene_map = {scene.get("id"): scene for scene in ai_payload.get("scenes", []) if scene.get("id")}
            for scene in target_pack.get("story", []):
                update = scene_map.get(scene.get("id"))
                if not update:
                    continue
                scene["image_prompt"] = update.get("image_prompt", scene.get("image_prompt", ""))
                scene["video_prompt"] = update.get("video_prompt", scene.get("video_prompt", ""))
                scene["video_script"] = update.get("video_script", scene.get("video_script", ""))
        except Exception as exc:  # noqa: BLE001
            ai_error = str(exc)
    updated = regenerate_pack_prompts(target_pack, workflow_rules)
    updated["updated_at"] = datetime.now(UTC).isoformat()
    save_week_pack(updated, set_current=current_week.get("week_id") == target_week_id)
    append_generation_log(
        {
            "type": "regenerate_prompts",
            "week_id": updated["week_id"],
            "ran_at": datetime.now(UTC).isoformat(),
            "status": "ready",
            "title": updated["title"],
            "new_chars": updated["new_chars"],
            "review_chars": updated["review_chars"],
            "error": ai_error,
            "generation_mode": "ai" if ai_is_enabled(ai_settings) and not ai_error else "template",
        }
    )
    return updated


@app.post("/api/admin/generate-worksheet")
def admin_generate_worksheet(week_id: str | None = Query(default=None)) -> dict:
    current_week = read_json("current_week.json")
    target_week_id = week_id or current_week.get("week_id")
    if not target_week_id:
        raise HTTPException(status_code=404, detail="No current week pack found.")
    try:
        target_pack = current_week if current_week.get("week_id") == target_week_id else read_week_pack(target_week_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Week pack not found.") from exc
    target_pack["worksheet"] = generate_handwriting_worksheet(target_pack)
    target_pack["updated_at"] = datetime.now(UTC).isoformat()
    save_week_pack(target_pack, set_current=current_week.get("week_id") == target_week_id)
    return target_pack["worksheet"]


@app.get("/api/admin/status")
def admin_status() -> dict:
    payload = read_json("generation_log.json")
    workflow_rules = read_json("workflow_rules.json", {})
    characters = read_json("characters.json", [])
    word_bank = read_json("hsk_word_bank.json", {"count": 0, "levels": []})
    payload["library_info"] = {
        "base": "HSK 1-4",
        "levels": workflow_rules.get("levelSequence", [workflow_rules.get("level", 1)]),
        "character_count": len(characters),
        "word_count": int(word_bank.get("count", 0) or 0),
        "strategy": workflow_rules.get("newCharStrategy", "frequency_order"),
    }
    return payload


@app.get("/{file_path:path}")
def static_files(file_path: str) -> FileResponse:
    target = FRONTEND_DIR / file_path
    if target.is_file():
        return FileResponse(target)
    raise HTTPException(status_code=404, detail="Not found.")
