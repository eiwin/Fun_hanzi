from __future__ import annotations

from datetime import UTC, datetime

from .selector import current_week_id


SCENE_TITLES = ["早晨出发", "课堂发现", "开心收尾"]


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _char_card(item: dict) -> dict:
    return {
        "char": item.get("char", ""),
        "pinyin": item.get("pinyin", ""),
        "meaning": item.get("meaning", ""),
        "words": item.get("words", []),
        "sentence": item.get("sentence", ""),
        "tags": item.get("tags", []),
    }


def build_prompts_for_story(story: list[dict], workflow_rules: dict) -> tuple[list[dict], list[dict]]:
    image_style = workflow_rules.get(
        "imageStyle",
        "storybook illustration, soft shapes, warm light, expressive characters",
    )
    video_style = workflow_rules.get(
        "videoStyle",
        "8-second short clip, gentle camera move, kid-safe, colorful classroom adventure",
    )

    image_tasks: list[dict] = []
    video_storyboard: list[dict] = []

    for scene in story:
        scene_text = scene["text"]
        focus_chars = scene["focus_chars"]
        focus_words = scene.get("focus_words", [])
        image_prompt = (
            f"Create a {image_style} scene for children. "
            f"Scene: {scene_text}. "
            f"Include focus characters {', '.join(focus_chars)} and words {', '.join(focus_words)}."
        )
        video_prompt = (
            f"Create a {video_style} clip. "
            f"Scene: {scene_text}. Keep the motion simple, cheerful, and easy for children to follow."
        )
        video_script = (
            f"{scene['title']}：先展示 {scene_text}，"
            f"再慢慢突出汉字 {'、'.join(focus_chars)}，"
            "最后用一句温柔的鼓励收尾。"
        )

        scene["image_prompt"] = image_prompt
        scene["image_status"] = scene.get("image_status", "pending")
        scene["image_asset_id"] = scene.get("image_asset_id")
        scene["image_path"] = scene.get("image_path", "")
        scene["video_prompt"] = video_prompt
        scene["video_script"] = video_script

        image_tasks.append(
            {
                "scene_id": scene["id"],
                "prompt": image_prompt,
                "status": scene["image_status"],
                "asset_id": scene.get("image_asset_id"),
                "file_path": scene.get("image_path", ""),
            }
        )
        video_storyboard.append(
            {
                "scene_id": scene["id"],
                "title": scene["title"],
                "prompt": video_prompt,
                "script": video_script,
            }
        )

    return image_tasks, video_storyboard


def build_weekly_pack(selection: dict, workflow_rules: dict, now: datetime | None = None) -> dict:
    current_time = now or datetime.now(UTC)
    chosen = selection["all_chars"]
    words = _unique([word for item in chosen for word in item.get("words", [])])
    sentences = _unique([item.get("sentence", "") for item in chosen])
    char_cards = [_char_card(item) for item in chosen]

    focus_chars = [item["char"] for item in chosen]
    title = f"{''.join(focus_chars[:4]) or '汉字'}冒险周"
    new_chars = [item["char"] for item in selection["new_chars"]]
    review_chars = [item["char"] for item in selection["review_chars"]]

    if new_chars:
        summary = (
            f"本周会认识新字 {'、'.join(new_chars)}，再复习 {'、'.join(review_chars) or '旧字'}。"
            f"故事会围绕 {'、'.join(words[:3]) or '本周内容'} 展开。"
        )
    else:
        summary = (
            f"本周重点复习 {'、'.join(review_chars) or '旧字'}。"
            f"故事会围绕 {'、'.join(words[:3]) or '本周内容'} 展开。"
        )

    scene_count = min(int(workflow_rules.get("storySceneCount", 3)), max(len(sentences), 1))
    story: list[dict] = []
    for index in range(scene_count):
        fallback = chosen[index % len(chosen)]
        text = sentences[index] if index < len(sentences) else fallback.get("sentence") or f"{fallback['char']} 在故事里出现。"
        scene_focus = [item["char"] for item in chosen[index : index + 3]] or [fallback["char"]]
        focus_words = words[index : index + 2]
        story.append(
            {
                "id": f"scene-{index + 1}",
                "title": SCENE_TITLES[index] if index < len(SCENE_TITLES) else f"场景 {index + 1}",
                "text": text,
                "focus_chars": scene_focus,
                "focus_words": focus_words,
            }
        )

    image_tasks, video_storyboard = build_prompts_for_story(story, workflow_rules)

    return {
        "week_id": current_week_id(current_time),
        "learner_id": "default",
        "generated_at": current_time.isoformat(),
        "title": title,
        "summary": summary,
        "new_chars": new_chars,
        "review_chars": review_chars,
        "char_cards": char_cards,
        "words": words[: int(workflow_rules.get("wordTarget", 6))],
        "sentences": sentences[: int(workflow_rules.get("sentenceTarget", 4))],
        "story": story,
        "image_tasks": image_tasks,
        "video_storyboard": video_storyboard,
        "status": "ready",
    }


def regenerate_pack_prompts(current_week: dict, workflow_rules: dict) -> dict:
    story = list(current_week.get("story", []))
    image_tasks, video_storyboard = build_prompts_for_story(story, workflow_rules)
    current_week["story"] = story
    current_week["image_tasks"] = image_tasks
    current_week["video_storyboard"] = video_storyboard
    current_week["generated_at"] = datetime.now(UTC).isoformat()
    current_week["status"] = "ready"
    return current_week
