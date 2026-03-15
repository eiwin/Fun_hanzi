from __future__ import annotations

import json
import os
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


MODEL_PRESETS = [
    {"label": "自动选择", "value": "openrouter/auto"},
    {"label": "ChatGPT 4o mini", "value": "openai/gpt-4o-mini"},
    {"label": "MiniMax M2.5", "value": "minimax/minimax-m2.5"},
    {"label": "Kimi K2", "value": "moonshotai/kimi-k2"},
]


IMAGE_PROMPT_TEMPLATE = (
    "Create a polished storybook-style learning illustration for school-age Chinese learners.\n"
    "Scene goal: {scene_text}\n"
    "Creative direction: {creative_brief}\n"
    "Visual style: bright picture-book illustration, soft shapes, warm daylight, clean outlines, expressive faces, rich classroom-or-home storytelling detail, suitable for school-age learners around 9-13, cheerful, easy to read.\n"
    "Composition: one clear main action, medium-wide shot, uncluttered foreground, readable background props, strong focal point on the learning action, and enough empty space for later teaching text.\n"
    "Characters and props: include these focus characters in the scene concept: {focus_chars}. Include these focus words as meaningful story objects or cues when natural: {focus_words}.\n"
    "Text rule: do NOT generate any Chinese characters, pinyin, letters, subtitles, or visible text inside the image.\n"
    "Layout rule: leave clean empty space where teaching text can be added later in post-production.\n"
    "Correctness rule: Hanzi and pinyin planning references must be absolutely correct. Use these exact Hanzi+pinyin references only as off-image planning notes: {pinyin_labels}.\n"
    "Quality bar: consistent visual language, no extra gibberish text, no distorted hands, no broken Chinese characters, no random English labels.\n"
    "Output target: a consistent, printable, age-appropriate learning illustration that matches the Fun Hanzi visual style without looking preschool."
)

VIDEO_PROMPT_TEMPLATE = (
    "Create a short educational micro-story video concept for school-age Chinese learners.\n"
    "Scene goal: {scene_text}\n"
    "Creative direction: {creative_brief}\n"
    "Narrative rule: this should feel like a believable real-life moment for learners around ages 9-13, not a dry flashcard demo. Include a setup, a small task or question, a response, and a warm ending.\n"
    "Video style: colorful real-life learning clip, gentle camera movement, clear staging, slow enough to follow, emotionally warm and encouraging, but not preschool-like or babyish.\n"
    "Main speaking line: {dialogue_line}\n"
    "Reference pinyin for production only: {dialogue_pinyin}\n"
    "Focus characters: {focus_chars}\n"
    "Focus words: {focus_words}\n"
    "On-screen text rule: if text appears in the video, prefer Hanzi only; do not auto-generate pinyin subtitles inside the video.\n"
    "Correctness rule: any Hanzi or pinyin used in planning or visible teaching text must be absolutely correct, with exact spelling and tone marks in the correct position.\n"
    "Continuity rule: keep the same characters, clothing, mood, and setting style as the related image prompt.\n"
    "Quality bar: avoid noisy motion, avoid complex cuts, keep one clear action beat per shot, and make the action grounded in a real place or real school-age activity."
)

VIDEO_SCRIPT_TEMPLATE = (
    "场景：{title}\n"
    "固定台词：{dialogue_line}\n"
    "参考拼音：{dialogue_pinyin}\n"
    "目标字：{focus_chars}\n"
    "脚本创意：{creative_script}\n"
    "剧情要求：必须有开场、一个小任务或小问题、人物回应、温暖结果，像真实生活短片，不要像机械认字视频，也不要像幼儿园表演。\n"
    "镜头1：建立真实环境和人物关系，让学习者知道故事发生在哪里、为什么会说这句话。\n"
    "镜头2：出现一个和目标字 {focus_chars} 相关的小动作、小问题或小发现。\n"
    "镜头3：角色自然说出固定台词“{dialogue_line}”，让台词和动作、情绪对应起来。\n"
    "镜头4：给出一个清楚结果或回应，让学习者理解这句话在生活里有什么用。\n"
    "镜头5：温柔收尾，用鼓励或满足感结束，并给画面 1-2 秒停留。\n"
    "字幕策略：学习页单独展示拼音；视频里如需字幕，只保留规范汉字。"
)


def get_model_presets() -> list[dict[str, str]]:
    return MODEL_PRESETS


def resolve_api_key(ai_settings: dict[str, Any]) -> str:
    if ai_settings.get("api_key"):
        return str(ai_settings["api_key"])
    env_name = ai_settings.get("api_key_env", "OPENROUTER_API_KEY")
    return os.getenv(env_name, "")


def ai_is_enabled(ai_settings: dict[str, Any]) -> bool:
    return bool(ai_settings.get("enabled")) and bool(resolve_api_key(ai_settings))


def _extract_text(payload: dict[str, Any]) -> str:
    choices = payload.get("choices", [])
    if not choices:
        return ""
    message = choices[0].get("message", {})
    content = message.get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            part.get("text", "")
            for part in content
            if isinstance(part, dict)
        )
    return ""


def _extract_json_block(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("{") and text.endswith("}"):
        return json.loads(text)

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("No JSON object found in model response.")
    return json.loads(match.group(0))


def _contains_cjk(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in text)


def _post_openrouter(ai_settings: dict[str, Any], prompt: str) -> dict[str, Any]:
    api_key = resolve_api_key(ai_settings)
    if not api_key:
        raise RuntimeError("Missing OpenRouter API key.")

    base_url = str(ai_settings.get("base_url", "https://openrouter.ai/api/v1")).rstrip("/")
    payload = {
        "model": ai_settings.get("model", "openrouter/auto"),
        "messages": [
            {
                "role": "system",
                "content": (
                    "You generate compact JSON only for a Chinese-learning app for children. "
                    "Return valid JSON and do not include markdown fences."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.7,
    }
    request = Request(
        f"{base_url}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": ai_settings.get("site_url", "http://127.0.0.1:8000"),
            "X-Title": ai_settings.get("app_name", "Fun Hanzi"),
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=60) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"OpenRouter HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"OpenRouter request failed: {exc.reason}") from exc

    payload = json.loads(raw)
    text = _extract_text(payload)
    if not text:
        raise RuntimeError("OpenRouter returned an empty response.")
    return _extract_json_block(text)


def _labels_to_text(labels: list[str] | list[dict[str, Any]]) -> str:
    if not labels:
        return "none"
    parts: list[str] = []
    for item in labels:
        if isinstance(item, str):
            parts.append(item)
        elif isinstance(item, dict) and item.get("char") and item.get("pinyin"):
            parts.append(f"{item['char']}({item['pinyin']})")
    return " | ".join(parts) if parts else "none"


def _normalize_scene_prompts(scene: dict[str, Any], payload: dict[str, Any]) -> dict[str, str]:
    creative_image = str(payload.get("image_prompt", "")).strip() or "Show a vivid, joyful learning moment built around the target sentence, without any visible text inside the illustration."
    creative_video = str(payload.get("video_prompt", "")).strip() or "Show a real-life child moment with a small problem, a response, and a warm ending."
    creative_script = str(payload.get("video_script", "")).strip() or "Build a tiny story beat with a setup, one child action, the key line, and a warm result."

    focus_chars = "、".join(scene.get("focus_chars", [])) or "none"
    focus_words = "、".join(scene.get("focus_words", [])) or "none"
    dialogue_line = scene.get("dialogue_line") or scene.get("text", "")
    dialogue_pinyin = scene.get("dialogue_pinyin") or _labels_to_text(scene.get("pronunciation_labels", []))
    pinyin_labels = _labels_to_text(scene.get("pronunciation_labels", scene.get("focus_pronunciations", [])))

    return {
        "image_prompt": IMAGE_PROMPT_TEMPLATE.format(
            scene_text=scene.get("text", ""),
            creative_brief=creative_image,
            focus_chars=focus_chars,
            focus_words=focus_words,
            pinyin_labels=pinyin_labels,
        ),
        "video_prompt": VIDEO_PROMPT_TEMPLATE.format(
            scene_text=scene.get("text", ""),
            creative_brief=creative_video,
            dialogue_line=dialogue_line,
            dialogue_pinyin=dialogue_pinyin,
            focus_chars=focus_chars,
            focus_words=focus_words,
        ),
        "video_script": VIDEO_SCRIPT_TEMPLATE.format(
            title=scene.get("title", ""),
            dialogue_line=dialogue_line,
            dialogue_pinyin=dialogue_pinyin,
            focus_chars=focus_chars,
            creative_script=creative_script,
        ),
    }


def test_openrouter(ai_settings: dict[str, Any]) -> dict[str, Any]:
    result = _post_openrouter(
        ai_settings,
        (
            'Return JSON only: {"ok": true, "message": "connected"}'
        ),
    )
    return {
        "ok": bool(result.get("ok")),
        "message": result.get("message", "connected"),
        "model": ai_settings.get("model", ""),
    }


def generate_week_content_with_ai(
    selection: dict[str, Any],
    workflow_rules: dict[str, Any],
    ai_settings: dict[str, Any],
) -> dict[str, Any]:
    new_chars = [item["char"] for item in selection.get("new_chars", [])]
    review_chars = [item["char"] for item in selection.get("review_chars", [])]
    chosen_chars = selection.get("all_chars", [])
    char_descriptions = [
        {
            "char": item.get("char", ""),
            "pinyin": item.get("pinyin", ""),
            "meaning": item.get("meaning", ""),
            "words": item.get("words", []),
            "sentence": item.get("sentence", ""),
        }
        for item in chosen_chars
    ]
    scene_count = int(workflow_rules.get("storySceneCount", 3))
    word_target = int(workflow_rules.get("wordTarget", 6))
    sentence_target = int(workflow_rules.get("sentenceTarget", 4))
    prompt = (
        "Create one weekly content bundle for a beginner Chinese learning app aimed at school-age learners around ages 9-13.\n"
        f"New characters: {new_chars}\n"
        f"Review characters: {review_chars}\n"
        f"Character info: {json.dumps(char_descriptions, ensure_ascii=False)}\n"
        "Rules:\n"
        "- title, summary, words, sentences, scene titles, scene texts, and dialogue lines must be in Simplified Chinese only.\n"
        "- Do not use English scene titles or English descriptive prose for title, summary, sentence text, scene text, or dialogue_line.\n"
        "- Keep language short, warm, concrete, and age-appropriate for ages 9-13.\n"
        "- Prefer using both new and review characters in words, sentences, and scenes.\n"
        "- Return exactly the requested JSON shape.\n"
        "- Video should use fixed spoken lines; pinyin is for learning-page reference, not mandatory in-video subtitles.\n"
        "- Every video scene must feel like a believable little real-life story for a school-age learner, not a plain vocabulary demonstration.\n"
        "- Each video scene should contain: a real setting, a tiny action or problem, a child response, and a warm ending.\n"
        "- For image_prompt and video_prompt, give a rich creative brief in 2-4 sentences, not a short fragment.\n"
        "- Mention setting, actions, mood, camera/composition, and educational intent suitable for ages 9-13.\n"
        "- Always state that Hanzi and pinyin spelling must be absolutely correct.\n"
        "- image_prompt must explicitly say that the illustration should contain no visible text, no Hanzi, and no pinyin; text will be added later in layout.\n"
        "- For video_prompt, emphasize practical everyday situations such as home, classroom, park, shop, trip, greeting, helping, counting, eating, reading, welcoming guests, or talking with family.\n"
        "- For video_script, provide a compact but specific mini-script with story beats and shot progression, not a one-line quote.\n"
        f"- Generate {word_target} words, {sentence_target} sentences, and {scene_count} story scenes.\n"
        "Return JSON with this shape:\n"
        '{'
        '"title":"",'
        '"summary":"",'
        '"words":[""],'
        '"sentences":[""],'
        '"scenes":[{"title":"","text":"","focus_chars":[""],"focus_words":[""],"dialogue_line":"","image_prompt":"","video_prompt":"","video_script":""}]}'
    )
    raw = _post_openrouter(ai_settings, prompt)
    normalized_scenes = []
    for scene in raw.get("scenes", []):
        scene_title = str(scene.get("title", "")).strip()
        scene_text = str(scene.get("text", "")).strip()
        dialogue_line = str(scene.get("dialogue_line", scene.get("text", ""))).strip()
        normalized = _normalize_scene_prompts(scene, scene)
        normalized_scenes.append(
            {
                "title": scene_title if _contains_cjk(scene_title) else "",
                "text": scene_text if _contains_cjk(scene_text) else "",
                "focus_chars": scene.get("focus_chars", []),
                "focus_words": scene.get("focus_words", []),
                "dialogue_line": dialogue_line if _contains_cjk(dialogue_line) else "",
                "image_prompt": normalized["image_prompt"],
                "video_prompt": normalized["video_prompt"],
                "video_script": normalized["video_script"],
            }
        )
    raw["scenes"] = normalized_scenes
    return raw


def regenerate_scene_prompts_with_ai(current_week: dict[str, Any], ai_settings: dict[str, Any]) -> dict[str, Any]:
    story = current_week.get("story", [])
    if not story:
        return {"scenes": []}

    scene_payload = [
        {
            "id": scene.get("id", ""),
            "title": scene.get("title", ""),
            "text": scene.get("text", ""),
            "focus_chars": scene.get("focus_chars", []),
            "focus_words": scene.get("focus_words", []),
            "dialogue_line": scene.get("dialogue_line", scene.get("text", "")),
            "dialogue_pinyin": scene.get("dialogue_pinyin", ""),
            "pronunciation_labels": scene.get("pronunciation_labels", []),
        }
        for scene in story
    ]
    prompt = (
        "Regenerate image prompts, video prompts, and video scripts for an existing Chinese learning weekly pack.\n"
        f"Week title: {current_week.get('title', '')}\n"
        f"Week summary: {current_week.get('summary', '')}\n"
        f"Scenes: {json.dumps(scene_payload, ensure_ascii=False)}\n"
        "Rules:\n"
        "- Keep all scene ids, titles, texts, focus_chars, focus_words, and dialogue lines unchanged.\n"
        "- Only rewrite image_prompt, video_prompt, and video_script.\n"
        "- Warm, concrete, visually rich, and suitable for ages 9-13 rather than preschool tone.\n"
        "- Video uses the fixed spoken line; pinyin is reference for learning page, not mandatory in-video subtitle.\n"
        "- Rewrite video as a micro-story in a believable daily-life setting. Avoid dry teaching-demo style.\n"
        "- Each video scene must include: real setting, small action or question, child response, warm ending.\n"
        "- image_prompt and video_prompt must be detailed, consistent, and production-ready, not short plain sentences.\n"
        "- Include scene setting, character action, emotion, composition/camera guidance, and educational focus.\n"
        "- Hanzi and pinyin spelling must be absolutely correct.\n"
        "- image_prompt must clearly state that the image itself should not contain any visible Hanzi, pinyin, letters, or text.\n"
        "- video_script must include clear shot progression, a tiny narrative arc, and repetition of the fixed line.\n"
        "Return JSON only in this exact shape:\n"
        '{"scenes":[{"id":"","image_prompt":"","video_prompt":"","video_script":""}]}'
    )
    raw = _post_openrouter(ai_settings, prompt)
    normalized_scenes = []
    source_map = {scene.get("id"): scene for scene in story if scene.get("id")}
    for item in raw.get("scenes", []):
        scene_id = item.get("id")
        source_scene = source_map.get(scene_id)
        if not source_scene:
            continue
        normalized = _normalize_scene_prompts(source_scene, item)
        normalized_scenes.append({"id": scene_id, **normalized})
    return {"scenes": normalized_scenes}
