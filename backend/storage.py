from __future__ import annotations

import json
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
ASSETS_DIR = DATA_DIR / "assets"
IMAGES_DIR = ASSETS_DIR / "images"
VIDEOS_DIR = ASSETS_DIR / "videos"
WORKSHEETS_DIR = ASSETS_DIR / "worksheets"
WEEKS_DIR = DATA_DIR / "weeks"


DEFAULT_CURRENT_WEEK = {
    "week_id": "",
    "learner_id": "default",
    "generated_at": "",
    "updated_at": "",
    "published_at": "",
    "title": "",
    "summary": "",
    "new_chars": [],
    "review_chars": [],
    "char_cards": [],
    "words": [],
    "sentences": [],
    "story": [],
    "image_tasks": [],
    "video_tasks": [],
    "video_storyboard": [],
    "audio_tasks": [],
    "worksheet": {
        "status": "pending",
        "file_path": "",
        "page_size": "A4",
        "entries": 0,
    },
    "status": "empty",
}

DEFAULT_ASSETS_MANIFEST = {"version": 1, "assets": []}

DEFAULT_GENERATION_LOG = {
    "version": 1,
    "last_run": None,
    "history": [],
}

DEFAULT_AI_SETTINGS = {
    "provider": "openrouter",
    "enabled": False,
    "base_url": "https://openrouter.ai/api/v1",
    "model": "openrouter/auto",
    "api_key": "",
    "api_key_env": "OPENROUTER_API_KEY",
    "site_url": "http://127.0.0.1:8000",
    "app_name": "Fun Hanzi",
}


def ensure_data_files() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    WORKSHEETS_DIR.mkdir(parents=True, exist_ok=True)
    WEEKS_DIR.mkdir(parents=True, exist_ok=True)

    defaults = {
        "current_week.json": DEFAULT_CURRENT_WEEK,
        "assets_manifest.json": DEFAULT_ASSETS_MANIFEST,
        "generation_log.json": DEFAULT_GENERATION_LOG,
        "ai_settings.json": DEFAULT_AI_SETTINGS,
    }

    for file_name, payload in defaults.items():
        file_path = DATA_DIR / file_name
        if not file_path.exists():
            write_json(file_name, payload)


def data_path(file_name: str) -> Path:
    return DATA_DIR / file_name


def read_json(file_name: str, default: Any | None = None) -> Any:
    file_path = data_path(file_name)
    if not file_path.exists():
        if default is None:
            raise FileNotFoundError(file_name)
        return default

    with file_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(file_name: str, payload: Any) -> None:
    file_path = data_path(file_name)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = file_path.with_suffix(f"{file_path.suffix}.tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    temp_path.replace(file_path)


def append_generation_log(entry: dict[str, Any]) -> None:
    log = read_json("generation_log.json", DEFAULT_GENERATION_LOG.copy())
    history = list(log.get("history", []))
    history.insert(0, entry)
    log["history"] = history[:20]
    log["last_run"] = entry
    write_json("generation_log.json", log)


def week_pack_path(week_id: str) -> Path:
    return WEEKS_DIR / f"{week_id}.json"


def save_week_pack(pack: dict[str, Any], set_current: bool = True) -> None:
    week_id = pack.get("week_id")
    if not week_id:
        raise ValueError("week_id is required to save a week pack")

    if set_current:
        write_json("current_week.json", pack)

    file_path = week_pack_path(week_id)
    temp_path = file_path.with_suffix(".json.tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        json.dump(pack, handle, ensure_ascii=False, indent=2)
    temp_path.replace(file_path)


def read_week_pack(week_id: str) -> dict[str, Any]:
    file_path = week_pack_path(week_id)
    if not file_path.exists():
        raise FileNotFoundError(week_id)
    with file_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def list_week_pack_summaries() -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for file_path in sorted(WEEKS_DIR.glob("*.json"), reverse=True):
        try:
            with file_path.open("r", encoding="utf-8") as handle:
                pack = json.load(handle)
        except json.JSONDecodeError:
            continue
        summaries.append(
            {
                "week_id": pack.get("week_id", file_path.stem),
                "generated_at": pack.get("generated_at", ""),
                "updated_at": pack.get("updated_at", ""),
                "published_at": pack.get("published_at", ""),
                "title": pack.get("title", ""),
                "summary": pack.get("summary", ""),
                "new_chars": pack.get("new_chars", []),
                "review_chars": pack.get("review_chars", []),
                "status": pack.get("status", "unknown"),
            }
        )
    return summaries
