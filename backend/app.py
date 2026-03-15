from __future__ import annotations

import threading
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
from .pinyin import numeric_to_tone_marked


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


class LearnSettingsPayload(BaseModel):
    game_mode: str = "mixed"
    fall_speed: str = "slow"


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


def _ensure_current_week_background() -> None:
    try:
        _ensure_current_week()
    except Exception as exc:  # noqa: BLE001
        append_generation_log(
            {
                "type": "startup_refresh",
                "week_id": current_week_id(datetime.now(UTC)),
                "ran_at": datetime.now(UTC).isoformat(),
                "status": "failed",
                "title": "",
                "new_chars": [],
                "review_chars": [],
                "error": str(exc),
                "generation_mode": "template",
            }
        )


@app.on_event("startup")
def on_startup() -> None:
    global scheduler
    ensure_data_files()
    scheduler = build_scheduler(lambda: generate_weekly_pack(force=True))
    scheduler.start()
    threading.Thread(target=_ensure_current_week_background, daemon=True).start()


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


@app.get("/api/learn-settings")
def get_learn_settings() -> dict:
    settings = read_json("learn_settings.json", {"game_mode": "mixed", "fall_speed": "slow"})
    return {"settings": settings}


@app.post("/api/admin/learn-settings")
def post_learn_settings(payload: LearnSettingsPayload) -> dict:
    allowed_modes = {"mixed", "new_only", "review_only"}
    allowed_speeds = {"slow", "medium", "fast"}
    settings = payload.model_dump()
    if settings["game_mode"] not in allowed_modes:
        raise HTTPException(status_code=400, detail="Invalid game mode.")
    if settings["fall_speed"] not in allowed_speeds:
        raise HTTPException(status_code=400, detail="Invalid fall speed.")
    write_json("learn_settings.json", settings)
    return {"ok": True, "settings": settings}


@app.post("/api/admin/test-ai")
def post_test_ai() -> dict:
    settings = read_json("ai_settings.json", {})
    return test_openrouter(settings)


@app.get("/api/progress")
def get_progress() -> dict:
    progress = read_json("progress.json", {"version": 1, "items": {}, "sessionHistory": [], "weeklyPacks": []})
    characters = read_json("characters.json", [])
    return {
        "progress": progress,
        "summary": {
            "tracked_chars": len(progress.get("items", {})),
            "session_count": len(progress.get("sessionHistory", [])),
            "known_total": sum(1 for item in progress.get("items", {}).values() if int(item.get("box", 0)) >= 3),
        },
        "learned_characters": _build_learned_characters(characters, progress),
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


def _level_sequence(workflow_rules: dict) -> list[int]:
    sequence = workflow_rules.get("levelSequence")
    if isinstance(sequence, list) and sequence:
        return [int(level) for level in sequence if isinstance(level, int) or str(level).isdigit()]
    level = workflow_rules.get("level", 1)
    return [int(level)]


def _character_sort_key(item: dict, fallback_rank: int, level_index: dict[int, int], strategy: str) -> tuple[int, int]:
    level = int(item.get("level", 99) or 99)
    level_rank = level_index.get(level, len(level_index))
    if strategy == "hsk_level_order":
        return (level_rank, int(item.get("hskOrder", fallback_rank) or fallback_rank))
    return (level_rank, int(item.get("frequencyRank", fallback_rank) or fallback_rank))


def _build_learning_progress(target_pack: dict, characters: list[dict], progress: dict, workflow_rules: dict) -> dict:
    if not target_pack:
        return {}

    strategy = workflow_rules.get("newCharStrategy", "frequency_order")
    level_sequence = _level_sequence(workflow_rules)
    level_index = {level: index for index, level in enumerate(level_sequence)}
    ordered_characters = sorted(
        characters,
        key=lambda item: _character_sort_key(item, characters.index(item) + 1, level_index, strategy),
    )
    char_lookup = {item.get("char", ""): item for item in ordered_characters if item.get("char")}

    new_chars = target_pack.get("new_chars", []) or []
    review_chars = target_pack.get("review_chars", []) or []
    pack_chars = new_chars or review_chars
    if not pack_chars:
        return {}

    primary_char = next((char for char in pack_chars if char_lookup.get(char)), "")
    primary_level = int(char_lookup.get(primary_char, {}).get("level", level_sequence[0] if level_sequence else 1) or 1)
    level_chars = [item for item in ordered_characters if int(item.get("level", 0) or 0) == primary_level]
    level_positions = {item.get("char", ""): index + 1 for index, item in enumerate(level_chars) if item.get("char")}
    new_positions = [level_positions[char] for char in new_chars if char in level_positions]

    weekly_packs = progress.get("weeklyPacks", []) or []
    studied_from_weeks: set[str] = set()
    for weekly in weekly_packs:
        for char in weekly.get("newChars", []) or []:
            if char:
                studied_from_weeks.add(char)

    studied_from_sessions: set[str] = set()
    total_answers = 0
    for session in progress.get("sessionHistory", []) or []:
        answers = session.get("answers", []) or []
        total_answers += len(answers)
        for answer in answers:
            char = answer.get("char")
            if char:
                studied_from_sessions.add(char)

    studied_chars = studied_from_weeks | studied_from_sessions
    items = progress.get("items", {}) or {}
    mastered_chars = [
        char
        for char, item in items.items()
        if isinstance(item, dict) and (int(item.get("box", 0) or 0) >= 2 or int(item.get("correctStreak", 0) or 0) >= 2)
    ]

    return {
        "current_level": primary_level,
        "current_level_label": f"HSK {primary_level}",
        "level_total_chars": len(level_chars),
        "level_position_start": min(new_positions) if new_positions else None,
        "level_position_end": max(new_positions) if new_positions else None,
        "level_new_char_count": len(new_positions),
        "studied_char_count": len(studied_chars),
        "mastered_char_count": len(set(mastered_chars)),
        "tracked_item_count": len(items),
        "session_count": len(progress.get("sessionHistory", []) or []),
        "answer_count": total_answers,
    }


def _build_learned_characters(characters: list[dict], progress: dict) -> list[dict[str, Any]]:
    char_lookup = {item.get("char", ""): item for item in characters if item.get("char")}
    learned_chars: set[str] = set()

    for char in (progress.get("items", {}) or {}).keys():
        if char:
            learned_chars.add(char)

    for weekly in progress.get("weeklyPacks", []) or []:
        for char in (weekly.get("newChars", []) or []):
            if char:
                learned_chars.add(char)
        for char in (weekly.get("reviewChars", []) or []):
            if char:
                learned_chars.add(char)

    result: list[dict[str, Any]] = []
    for char in learned_chars:
        item = char_lookup.get(char)
        if not item:
            continue
        result.append(
            {
                "char": char,
                "pinyin": numeric_to_tone_marked(item.get("pinyin", "")),
                "pinyin_numeric": item.get("pinyin", ""),
                "meaning": item.get("meaning", ""),
                "level": item.get("level", 0),
                "hskOrder": item.get("hskOrder", 0),
            }
        )

    return sorted(
        result,
        key=lambda item: (
            int(item.get("level", 99) or 99),
            int(item.get("hskOrder", 999999) or 999999),
            item.get("char", ""),
        ),
    )


@app.get("/api/admin/status")
def admin_status(week_id: str | None = Query(default=None)) -> dict:
    payload = read_json("generation_log.json")
    workflow_rules = read_json("workflow_rules.json", {})
    characters = read_json("characters.json", [])
    progress = read_json("progress.json", {"version": 1, "items": {}, "sessionHistory": [], "weeklyPacks": []})
    current_week = read_json("current_week.json", {})
    target_pack = current_week
    if week_id and current_week.get("week_id") != week_id:
        try:
            target_pack = read_week_pack(week_id)
        except FileNotFoundError:
            target_pack = current_week
    word_bank = read_json("hsk_word_bank.json", {"count": 0, "levels": []})
    payload["library_info"] = {
        "base": "HSK 1-4",
        "levels": workflow_rules.get("levelSequence", [workflow_rules.get("level", 1)]),
        "character_count": len(characters),
        "word_count": int(word_bank.get("count", 0) or 0),
        "strategy": workflow_rules.get("newCharStrategy", "frequency_order"),
    }
    payload["learning_progress"] = _build_learning_progress(target_pack, characters, progress, workflow_rules)
    return payload


@app.get("/{file_path:path}")
def static_files(file_path: str) -> FileResponse:
    target = FRONTEND_DIR / file_path
    if target.is_file():
        return FileResponse(target)
    raise HTTPException(status_code=404, detail="Not found.")
