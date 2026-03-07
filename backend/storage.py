from __future__ import annotations

import json
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
ASSETS_DIR = DATA_DIR / "assets"
IMAGES_DIR = ASSETS_DIR / "images"


DEFAULT_CURRENT_WEEK = {
    "week_id": "",
    "learner_id": "default",
    "generated_at": "",
    "title": "",
    "summary": "",
    "new_chars": [],
    "review_chars": [],
    "char_cards": [],
    "words": [],
    "sentences": [],
    "story": [],
    "image_tasks": [],
    "video_storyboard": [],
    "status": "empty",
}

DEFAULT_ASSETS_MANIFEST = {"version": 1, "assets": []}

DEFAULT_GENERATION_LOG = {
    "version": 1,
    "last_run": None,
    "history": [],
}


def ensure_data_files() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    defaults = {
        "current_week.json": DEFAULT_CURRENT_WEEK,
        "assets_manifest.json": DEFAULT_ASSETS_MANIFEST,
        "generation_log.json": DEFAULT_GENERATION_LOG,
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
