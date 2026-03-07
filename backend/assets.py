from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile

from .storage import IMAGES_DIR, read_json, write_json


def _safe_extension(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".webp"}:
        return suffix
    return ".png"


def import_scene_image(week_id: str, scene_id: str, upload: UploadFile) -> dict:
    if not upload.filename:
        raise HTTPException(status_code=400, detail="Missing image filename.")

    current_week = read_json("current_week.json")
    if current_week.get("week_id") != week_id:
        raise HTTPException(status_code=404, detail="Week pack not found.")

    story = current_week.get("story", [])
    scene = next((item for item in story if item.get("id") == scene_id), None)
    if scene is None:
        raise HTTPException(status_code=404, detail="Scene not found.")

    extension = _safe_extension(upload.filename)
    asset_id = f"asset-{uuid4().hex[:10]}"
    week_dir = IMAGES_DIR / week_id
    week_dir.mkdir(parents=True, exist_ok=True)
    destination = week_dir / f"{scene_id}{extension}"

    with destination.open("wb") as handle:
        shutil.copyfileobj(upload.file, handle)

    manifest = read_json("assets_manifest.json", {"version": 1, "assets": []})
    assets = [item for item in manifest.get("assets", []) if item.get("asset_id") != asset_id]
    asset_record = {
        "asset_id": asset_id,
        "week_id": week_id,
        "scene_id": scene_id,
        "type": "image",
        "source": "manual",
        "status": "ready",
        "file_path": str(destination.relative_to(destination.parents[2])),
        "prompt": scene.get("image_prompt", ""),
        "imported_at": datetime.now(UTC).isoformat(),
        "error": "",
    }
    assets.insert(0, asset_record)
    manifest["assets"] = assets[:100]
    write_json("assets_manifest.json", manifest)

    scene["image_status"] = "ready"
    scene["image_asset_id"] = asset_id
    scene["image_path"] = f"/assets/{asset_record['file_path']}"
    for task in current_week.get("image_tasks", []):
        if task.get("scene_id") == scene_id:
            task["status"] = "ready"
            task["asset_id"] = asset_id
            task["file_path"] = scene["image_path"]

    write_json("current_week.json", current_week)
    return asset_record
