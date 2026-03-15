from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile

from .storage import IMAGES_DIR, VIDEOS_DIR, read_json, read_week_pack, save_week_pack, write_json


def _safe_image_extension(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".webp"}:
        return suffix
    return ".png"


def _safe_video_extension(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix in {".mp4", ".mov", ".m4v", ".webm"}:
        return suffix
    return ".mp4"


def _import_scene_media(week_id: str, scene_id: str, upload: UploadFile, media_type: str) -> dict:
    if not upload.filename:
        raise HTTPException(status_code=400, detail="Missing media filename.")

    current_week = read_json("current_week.json")
    if current_week.get("week_id") == week_id:
        target_week = current_week
    else:
        try:
            target_week = read_week_pack(week_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Week pack not found.") from exc

    story = target_week.get("story", [])
    scene = next((item for item in story if item.get("id") == scene_id), None)
    if scene is None:
        raise HTTPException(status_code=404, detail="Scene not found.")

    extension = _safe_image_extension(upload.filename) if media_type == "image" else _safe_video_extension(upload.filename)
    asset_id = f"asset-{uuid4().hex[:10]}"
    week_dir = (IMAGES_DIR if media_type == "image" else VIDEOS_DIR) / week_id
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
        "type": media_type,
        "source": "manual",
        "status": "ready",
        "file_path": str(destination.relative_to(destination.parents[2])),
        "prompt": scene.get("image_prompt", "") if media_type == "image" else scene.get("video_prompt", ""),
        "imported_at": datetime.now(UTC).isoformat(),
        "error": "",
    }
    assets.insert(0, asset_record)
    manifest["assets"] = assets[:100]
    write_json("assets_manifest.json", manifest)

    scene[f"{media_type}_status"] = "ready"
    scene[f"{media_type}_asset_id"] = asset_id
    scene[f"{media_type}_path"] = f"/assets/{asset_record['file_path']}"
    task_key = "image_tasks" if media_type == "image" else "video_tasks"
    for task in target_week.get(task_key, []):
        if task.get("scene_id") == scene_id:
            task["status"] = "ready"
            task["asset_id"] = asset_id
            task["file_path"] = scene[f"{media_type}_path"]

    save_week_pack(target_week, set_current=current_week.get("week_id") == week_id)
    return asset_record


def import_scene_image(week_id: str, scene_id: str, upload: UploadFile) -> dict:
    return _import_scene_media(week_id, scene_id, upload, "image")


def import_scene_video(week_id: str, scene_id: str, upload: UploadFile) -> dict:
    return _import_scene_media(week_id, scene_id, upload, "video")
