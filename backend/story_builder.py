from __future__ import annotations

import json
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

from .pinyin import build_pronunciation_guide, numeric_to_tone_marked
from .selector import current_week_id


SCENE_TITLES = ["早晨出发", "课堂发现", "开心收尾"]
WORD_BANK_PATH = Path(__file__).resolve().parent.parent / "data" / "hsk_word_bank.json"
CHARACTER_BANK_PATH = Path(__file__).resolve().parent.parent / "data" / "characters.json"
SENTENCE_TEMPLATES = [
    "我喜欢{word}。",
    "我们一起学{word}。",
    "老师说：{word}。",
    "我会写{word}。",
]
REAL_LIFE_SCENES = [
    ("课堂互动", "小学高年级或初中预备阶段的中文课堂", "老师和学生围绕一个具体任务进行交流、观察或回答"),
    ("家庭时刻", "家里客厅、书桌边或餐桌边", "学生和家人围绕真实生活安排、表达或讨论进行互动"),
    ("出门场景", "上学路上、图书馆、商店、社区街角", "学生在真实环境里观察信息、回应问题、完成一个小目标"),
]
PHRASE_PINYIN_OVERRIDES = {
    "教室": "jiào shì",
    "打电话": "dǎ diàn huà",
    "地点": "dì diǎn",
}


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _is_cjk(char: str) -> bool:
    return "\u4e00" <= char <= "\u9fff"


def _contains_cjk(text: str) -> bool:
    return any(_is_cjk(char) for char in text)


@lru_cache(maxsize=1)
def _load_word_bank() -> list[dict]:
    if not WORD_BANK_PATH.exists():
        return []
    payload = json.loads(WORD_BANK_PATH.read_text())
    return payload.get("items", [])


@lru_cache(maxsize=1)
def _load_character_bank() -> list[dict]:
    if not CHARACTER_BANK_PATH.exists():
        return []
    payload = json.loads(CHARACTER_BANK_PATH.read_text())
    if isinstance(payload, list):
        return payload
    return payload.get("items", [])


def _join_pinyin_tokens(tokens: list[str]) -> str:
    punctuation = {"，", "。", "！", "？", "；", "：", ",", ".", "!", "?", ";", ":"}
    result = ""
    for token in tokens:
        if not token:
            continue
        if token in punctuation:
            result = result.rstrip() + token
            continue
        if result and not result.endswith(" "):
            result += " "
        result += token
    return result.strip()


def _build_text_pinyin_data(text: str, pronunciation_lookup: dict[str, str]) -> dict:
    if not any(_is_cjk(char) for char in text):
        return {
            "pinyin_text": "",
            "pronunciation_labels": [],
            "pronunciations": [],
        }

    labels: list[dict[str, str]] = []
    tokens: list[str] = []
    all_covered = True
    index = 0
    while index < len(text):
        matched_phrase = None
        for phrase in sorted(PHRASE_PINYIN_OVERRIDES, key=len, reverse=True):
            if text.startswith(phrase, index):
                matched_phrase = phrase
                break
        if matched_phrase:
            phrase_pinyin = PHRASE_PINYIN_OVERRIDES[matched_phrase].split()
            if len(phrase_pinyin) == len(matched_phrase):
                for char, pinyin in zip(matched_phrase, phrase_pinyin):
                    labels.append({"char": char, "pinyin": pinyin})
                    tokens.append(pinyin)
                index += len(matched_phrase)
                continue

        char = text[index]
        pinyin = pronunciation_lookup.get(char, "")
        if pinyin:
            labels.append({"char": char, "pinyin": pinyin})
            tokens.append(pinyin)
        elif _is_cjk(char):
            all_covered = False
        else:
            tokens.append(char)
        index += 1

    return {
        "pinyin_text": _join_pinyin_tokens(tokens) if all_covered else "",
        "pronunciation_labels": _unique(
            [f"{item['char']}({item['pinyin']})" for item in labels if item.get("char") and item.get("pinyin")]
        ),
        "pronunciations": labels,
    }


def _select_word_bank_words(selection: dict, workflow_rules: dict) -> tuple[list[str], list[str]]:
    bank = _load_word_bank()
    if not bank:
        return [], []

    new_chars = {item.get("char", "") for item in selection.get("new_chars", []) if item.get("char")}
    review_chars = {item.get("char", "") for item in selection.get("review_chars", []) if item.get("char")}
    selected_chars = new_chars | review_chars
    target_word_count = max(int(workflow_rules.get("wordTarget", 6)), 1)
    target_sentence_count = max(int(workflow_rules.get("sentenceTarget", 4)), 1)

    candidates: list[tuple[tuple[int, int, int, int], str]] = []
    for item in bank:
        word = str(item.get("word", "")).strip()
        if not word:
            continue
        overlap = [char for char in word if char in selected_chars]
        if not overlap:
            continue
        new_overlap = [char for char in word if char in new_chars]
        review_overlap = [char for char in word if char in review_chars]
        if 2 <= len(word) <= 4:
            length_priority = 0
        elif len(word) == 1:
            length_priority = 1
        else:
            length_priority = 2
        score = (
            0 if new_overlap else 1,
            -len(set(overlap)),
            length_priority,
            int(item.get("sourceOrder", 999999)),
        )
        candidates.append((score, word))

    ordered_words = _unique([word for _, word in sorted(candidates, key=lambda item: item[0])])
    words = ordered_words[:target_word_count]

    sentences: list[str] = []
    sentence_source_words = [word for word in ordered_words if len(word) > 1] or ordered_words
    for index, word in enumerate(sentence_source_words[: max(target_sentence_count * 2, target_sentence_count)]):
        if len(word) == 1:
            sentence = f"今天学{word}。"
        else:
            template = SENTENCE_TEMPLATES[index % len(SENTENCE_TEMPLATES)]
            sentence = template.format(word=word)
        if sentence not in sentences:
            sentences.append(sentence)
        if len(sentences) >= target_sentence_count:
            break

    return words, sentences


def _char_card(item: dict) -> dict:
    marked = numeric_to_tone_marked(item.get("pinyin", ""))
    return {
        "char": item.get("char", ""),
        "pinyin": marked,
        "pinyin_numeric": item.get("pinyin", ""),
        "pronunciation_guide": build_pronunciation_guide(item.get("char", ""), item.get("pinyin", "")),
        "meaning": item.get("meaning", ""),
        "radical": item.get("radical", ""),
        "stroke_count": item.get("strokeCount", ""),
        "stroke_hint": item.get("strokeHint", ""),
        "structure": item.get("structure", ""),
        "components": item.get("components", []),
        "words": item.get("words", []),
        "word_pronunciation_hints": [],
        "sentence": item.get("sentence", ""),
        "sentence_pinyin": "",
        "sentence_pronunciation_labels": [],
        "tags": item.get("tags", []),
        "audio_text": build_pronunciation_guide(item.get("char", ""), item.get("pinyin", "")),
        "audio_status": "pending",
        "audio_path": "",
    }


def _build_annotation_instruction(scene: dict) -> str:
    annotations = scene.get("focus_pronunciations", [])
    if not annotations:
        return (
            "Add correct pinyin with tone marks above each target Chinese character. "
            "Place the pinyin directly above the matching character, centered and aligned."
        )

    annotation_text = ", ".join(
        f"{item['char']}({item['pinyin']})" for item in annotations if item.get("char") and item.get("pinyin")
    )
    return (
        "Add correct pinyin with tone marks above the target Chinese characters. "
        "Place the pinyin directly above the matching character, centered and aligned. "
        f"Use these exact annotations: {annotation_text}."
    )


def _build_exact_pinyin_instruction(scene: dict) -> str:
    annotations = scene.get("focus_pronunciations", [])
    if not annotations:
        return ""

    exact_pairs = "; ".join(
        f"{item['char']} -> {item['pinyin']}" for item in annotations if item.get("char") and item.get("pinyin")
    )
    exact_labels = " | ".join(
        f"{item['char']} {item['pinyin']}" for item in annotations if item.get("char") and item.get("pinyin")
    )
    return (
        "Use the following exact pinyin spellings with tone marks and do not change them: "
        f"{exact_pairs}. "
        f"If you render teaching labels or subtitles, copy these exact forms: {exact_labels}. "
        "The Hanzi and pinyin spelling must be absolutely correct with no wrong characters, no wrong syllables, and no misplaced tone marks."
    )


def _build_video_reference_instruction(scene: dict) -> str:
    annotations = scene.get("focus_pronunciations", [])
    if not annotations:
        return ""

    exact_pairs = "; ".join(
        f"{item['char']} -> {item['pinyin']}" for item in annotations if item.get("char") and item.get("pinyin")
    )
    exact_labels = " | ".join(
        f"{item['char']} {item['pinyin']}" for item in annotations if item.get("char") and item.get("pinyin")
    )
    return (
        "Reference these exact pinyin spellings for production planning and script checking only: "
        f"{exact_pairs}. "
        f"Keep these exact Hanzi+pinyin pairs in your notes: {exact_labels}."
    )


def _build_video_dialogue_instruction(scene: dict) -> str:
    reference_pinyin = scene.get("dialogue_pinyin") or ", ".join(scene.get("pronunciation_labels", []))
    if not reference_pinyin:
        return (
            "Use the fixed spoken line provided in the script. "
            "Do not invent extra pinyin subtitles inside the video."
        )
    return (
        "Use the fixed spoken line provided in the script. "
        f"Reference pinyin for production only: {reference_pinyin}. "
        "Do not generate pinyin subtitles inside the video; the learning page will show the exact teaching pinyin separately."
    )


def _pick_scene_world(scene: dict) -> tuple[str, str, str]:
    text = f"{scene.get('text', '')} {scene.get('dialogue_line', '')} {' '.join(scene.get('focus_words', []))}"
    if any(keyword in text for keyword in ["老师", "教室", "校园", "图书角", "图书馆", "同学", "校门", "教学楼", "地图", "课堂"]):
        return ("课堂互动", "小学高年级或初中预备阶段的中文课堂或校园环境", "老师和学生围绕一个具体任务进行交流、观察或回答")
    if any(keyword in text for keyword in ["爸爸", "妈妈", "客人", "杯子", "菜", "桌子", "家里", "客厅", "餐桌", "书桌"]):
        return ("家庭时刻", "温暖真实的家庭空间", "学生和家人围绕生活安排、礼貌表达或简单分工进行互动")
    if any(keyword in text for keyword in ["北京", "商店", "超市", "买", "出租车", "医院", "学校外面", "公园", "路上", "门口", "街角"]):
        return ("出门场景", "真实的外部生活场景", "学生在现实环境里观察信息、做出回应、自然开口表达")
    return REAL_LIFE_SCENES[0]


def _build_video_story_brief(scene: dict) -> str:
    scene_type, location, relationship = _pick_scene_world(scene)
    focus_words = "、".join(scene.get("focus_words", [])) or "目标词语"
    focus_chars = "、".join(scene.get("focus_chars", [])) or "目标字"
    dialogue_line = scene.get("dialogue_line") or scene.get("text", "")
    return (
        f"Build a school-age learning micro-story instead of a dry teaching clip. "
        f"Use a believable {scene_type} in {location}. "
        f"Show {relationship}. "
        f"Let {focus_words} and the focus characters {focus_chars} appear through a tiny real-life event. "
        f"The story must contain a setup, a small task or question, a response, and a warm ending. "
        f"Keep the tone suitable for learners around ages 9-13, a little more mature and grounded than preschool material. "
        f"Make the spoken line feel natural and land clearly on “{dialogue_line}”."
    )


def _build_video_script(scene: dict) -> str:
    focus_chars = "、".join(scene.get("focus_chars", []))
    subtitle_text = scene.get("dialogue_line", scene.get("text", ""))
    dialogue_pinyin = scene.get("dialogue_pinyin") or "按学习页提供的拼音卡片展示"
    scene_type, location, relationship = _pick_scene_world(scene)
    return (
        f"场景：{scene['title']}\n"
        f"视频类型：{scene_type}\n"
        f"真实场合：{location}\n"
        f"人物关系：{relationship}\n"
        f"固定台词：{subtitle_text}\n"
        f"参考拼音：{dialogue_pinyin}\n"
        f"目标字：{focus_chars}\n"
        "剧情结构：先交代一个真实小场景，再出现一个小问题或小任务，接着通过人物互动自然说出台词，最后温暖收尾。\n"
        f"镜头1：建立真实场景，让学生一眼看懂人物在做什么，并为“{subtitle_text}”做铺垫。\n"
        f"镜头2：出现一个具体动作或小问题，把目标字 {focus_chars} 藏在物件、地点、任务或人物反应里，不要像生硬教学演示。\n"
        f"镜头3：角色在情境里自然说出固定台词“{subtitle_text}”，嘴型清楚，情绪真实，动作和台词有关联。\n"
        "镜头4：给出回应或结果，例如同学反馈、老师确认、家人回应、任务完成，让学习者感觉这个句子在真实生活里有用。\n"
        "镜头5：收尾停留 1-2 秒，保持画面温暖、真实、易懂，但不要过于幼态。\n"
        "字幕策略：视频里不强制加入拼音字幕，拼音会由学习页面单独展示；如需字幕，只保留汉字即可。"
    )


def _build_image_text_layout(scene: dict) -> str:
    title = scene.get("dialogue_line") or scene.get("text", "")
    title_pinyin = scene.get("dialogue_pinyin") or "请按学习页拼音补全"
    focus_pronunciations = scene.get("focus_pronunciations", [])
    focus_words = scene.get("focus_words", [])
    teaching_labels = " | ".join(
        f"{item['char']} {item['pinyin']}" for item in focus_pronunciations if item.get("char") and item.get("pinyin")
    ) or "请按学习页补全"
    focus_lines = "\n".join(
        f"{item['char']}\n{item['pinyin']}" for item in focus_pronunciations if item.get("char") and item.get("pinyin")
    ) or "字1\npinyin1\n\n字2\npinyin2\n\n字3\npinyin3"
    words_text = "\n".join(focus_words) or "词语1\n词语2"

    return (
        "【标题】\n"
        f"{title}\n"
        f"{title_pinyin}\n\n"
        "【重点字】\n"
        f"{focus_lines}\n\n"
        "【词语】\n"
        f"{words_text}\n\n"
        "【教学标签】\n"
        f"{teaching_labels}"
    )


def _build_image_prompt(scene: dict, image_style: str) -> str:
    scene_text = scene.get("text", "")
    scene_type, location, _relationship = _pick_scene_world(scene)
    focus_words = "、".join(scene.get("focus_words", [])) or "目标词语"
    focus_chars = "、".join(scene.get("focus_chars", [])) or "目标字"

    return (
        "Create a storybook-style learning illustration for school-age Chinese learners.\n"
        f"Style baseline: {image_style}.\n"
        f"Scene goal: {scene_text}\n"
        f"Scene type: {scene_type}\n"
        f"Location: {location}\n"
        f"Focus characters: {focus_chars}\n"
        f"Focus words: {focus_words}\n"
        "Visual direction:\n"
        "- Use soft shapes, warm light, expressive characters, and an age-appropriate atmosphere for learners around ages 9-13.\n"
        "- Build a grounded educational scene connected to real Chinese learning moments such as classroom discussion, home routines, reading, greeting, helping, planning, travel, or going out.\n"
        "- Include meaningful props related to Chinese learning, such as books, chalkboard, toys, flowers, bags, tables, cups, or other scene-appropriate objects.\n"
        "- Keep the layout clean and stable, suitable for a modern learning page or printable study material.\n"
        "Composition:\n"
        "- One clear main action, readable background, strong focal point, and enough empty space for later educational text layout.\n"
        "- Make the illustration feel polished, warm, and visually consistent with the Fun Hanzi style, without looking like preschool material.\n"
        "IMPORTANT:\n"
        "- Do NOT generate any Chinese characters, pinyin, letters, or text in the image.\n"
        "- Leave empty space where educational text can be added later.\n"
        "- Hanzi and pinyin planning notes belong in the separate text layout, not inside the image.\n"
        "- If any visible text is produced by mistake, it must be treated as an error and regenerated."
    )


def _build_video_prompt(scene: dict, video_style: str) -> str:
    scene_type, location, relationship = _pick_scene_world(scene)
    scene_text = scene.get("text", "")
    dialogue_line = scene.get("dialogue_line") or scene_text
    dialogue_pinyin = scene.get("dialogue_pinyin") or ", ".join(scene.get("pronunciation_labels", [])) or "none"
    focus_chars = "、".join(scene.get("focus_chars", [])) or "目标字"
    focus_words = "、".join(scene.get("focus_words", [])) or "目标词语"
    video_reference_instruction = _build_video_reference_instruction(scene)
    dialogue_instruction = _build_video_dialogue_instruction(scene)
    story_brief = _build_video_story_brief(scene)

    return (
        "Create an educational micro-story video for school-age Chinese learners.\n"
        f"Style baseline: {video_style}.\n"
        f"Scene title: {scene.get('title', '')}\n"
        f"Learning goal: {scene_text}\n"
        f"Real-life setting: {scene_type} / {location}\n"
        f"Character relationship: {relationship}\n"
        f"Focus characters: {focus_chars}\n"
        f"Focus words: {focus_words}\n"
        f"Fixed spoken line: {dialogue_line}\n"
        f"Reference pinyin for production only: {dialogue_pinyin}\n"
        f"Story direction: {story_brief}\n"
        "Story structure:\n"
        "- Opening: establish a real place and a clear student activity.\n"
        "- Middle beat: introduce one small task, question, or discovery connected to the target words.\n"
        "- Speaking beat: let the character say the fixed line naturally in context.\n"
        "- Ending: give a warm response or tiny success moment.\n"
        "Visual direction:\n"
        "- Keep the action grounded in family life, classroom life, going out, greeting, helping, reading, planning, traveling, or welcoming someone.\n"
        "- Use clear staging, readable props, gentle motion, and one main action per shot.\n"
        "- Keep the same characters, costume, and mood consistent with the matching image.\n"
        "Text and subtitle rules:\n"
        f"- {video_reference_instruction}\n"
        f"- {dialogue_instruction}\n"
        "- If text appears on screen, prefer Hanzi only and avoid auto-generated pinyin subtitles.\n"
        "- Hanzi writing and pinyin spelling must be absolutely correct; do not invent, simplify, misspell, or place tone marks on the wrong vowel.\n"
        "Quality bar:\n"
        "- Avoid flashcard-style pointing at words.\n"
        "- Avoid empty backgrounds or generic stock actions.\n"
        "- Make the moment feel believable, warm, story-led, and useful for a child learner."
    )


def build_prompts_for_story(
    story: list[dict], workflow_rules: dict, overwrite_existing: bool = False
) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
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
    video_tasks: list[dict] = []
    audio_tasks: list[dict] = []

    for scene in story:
        scene_text = scene["text"]
        spoken_text = scene.get("dialogue_line") or scene_text
        focus_chars = scene["focus_chars"]
        focus_words = scene.get("focus_words", [])
        generated_image_prompt = _build_image_prompt(scene, image_style)
        generated_video_prompt = (
            _build_video_prompt(scene, video_style)
        )
        image_prompt = generated_image_prompt if overwrite_existing else (scene.get("image_prompt") or generated_image_prompt)
        video_prompt = generated_video_prompt if overwrite_existing else (scene.get("video_prompt") or generated_video_prompt)
        video_script = _build_video_script(scene) if overwrite_existing else (scene.get("video_script") or _build_video_script(scene))
        image_text_layout = (
            _build_image_text_layout(scene)
            if overwrite_existing
            else (scene.get("image_text_layout") or _build_image_text_layout(scene))
        )

        scene["image_prompt"] = image_prompt
        scene["image_text_layout"] = image_text_layout
        scene["image_status"] = scene.get("image_status", "pending")
        scene["image_asset_id"] = scene.get("image_asset_id")
        scene["image_path"] = scene.get("image_path", "")
        scene["video_prompt"] = video_prompt
        scene["video_script"] = video_script
        scene["video_status"] = scene.get("video_status", "pending")
        scene["video_asset_id"] = scene.get("video_asset_id")
        scene["video_path"] = scene.get("video_path", "")
        scene["audio_text"] = spoken_text if _contains_cjk(spoken_text) else scene_text
        scene["audio_status"] = scene.get("audio_status", "pending")
        scene["audio_path"] = scene.get("audio_path", "")

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
        video_tasks.append(
            {
                "scene_id": scene["id"],
                "prompt": video_prompt,
                "status": scene["video_status"],
                "asset_id": scene.get("video_asset_id"),
                "file_path": scene.get("video_path", ""),
            }
        )
        audio_tasks.append(
            {
                "scope": "story",
                "id": scene["id"],
                "text": scene_text,
                "status": scene["audio_status"],
                "file_path": scene["audio_path"],
            }
        )

    return image_tasks, video_storyboard, video_tasks, audio_tasks


def build_weekly_pack(
    selection: dict, workflow_rules: dict, now: datetime | None = None, ai_content: dict | None = None
) -> dict:
    current_time = now or datetime.now(UTC)
    chosen = selection["all_chars"]
    pronunciation_lookup = {
        item.get("char", ""): numeric_to_tone_marked(item.get("pinyin", ""))
        for item in selection.get("character_pool", chosen)
        if item.get("char")
    }
    bank_words, bank_sentences = _select_word_bank_words(selection, workflow_rules)
    default_words = bank_words or _unique([word for item in chosen for word in item.get("words", [])])
    default_sentences = bank_sentences or _unique([item.get("sentence", "") for item in chosen])
    words = _unique(ai_content.get("words", [])) if ai_content else default_words
    sentences = _unique(ai_content.get("sentences", [])) if ai_content else default_sentences
    char_cards = [_char_card(item) for item in chosen]
    for card in char_cards:
        sentence_pinyin_data = _build_text_pinyin_data(card.get("sentence", ""), pronunciation_lookup)
        word_hints = []
        for word in card.get("words", []):
            word_pinyin_data = _build_text_pinyin_data(word, pronunciation_lookup)
            if word_pinyin_data["pinyin_text"]:
                word_hints.append(f"{word}: {word_pinyin_data['pinyin_text']}")
            elif word_pinyin_data["pronunciation_labels"]:
                word_hints.append(f"{word}: {' '.join(word_pinyin_data['pronunciation_labels'])}")
        card["word_pronunciation_hints"] = word_hints
        card["sentence_pinyin"] = sentence_pinyin_data["pinyin_text"]
        card["sentence_pronunciation_labels"] = sentence_pinyin_data["pronunciation_labels"]

    focus_chars = [item["char"] for item in chosen]
    char_lookup = {item["char"]: item for item in chosen}
    default_title = f"{''.join(focus_chars[:4]) or '汉字'}冒险周"
    new_chars = [item["char"] for item in selection["new_chars"]]
    review_chars = [item["char"] for item in selection["review_chars"]]

    if new_chars:
        default_summary = (
            f"本周会认识新字 {'、'.join(new_chars)}，再复习 {'、'.join(review_chars) or '旧字'}。"
            f"故事会围绕 {'、'.join(words[:3]) or '本周内容'} 展开。"
        )
    else:
        default_summary = (
            f"本周重点复习 {'、'.join(review_chars) or '旧字'}。"
            f"故事会围绕 {'、'.join(words[:3]) or '本周内容'} 展开。"
        )
    title = ai_content.get("title", default_title) if ai_content else default_title
    summary = ai_content.get("summary", default_summary) if ai_content else default_summary

    scene_count = min(int(workflow_rules.get("storySceneCount", 3)), max(len(sentences), 1))
    story: list[dict] = []
    ai_scenes = ai_content.get("scenes", []) if ai_content else []
    for index in range(scene_count):
        fallback = chosen[index % len(chosen)]
        ai_scene = ai_scenes[index] if index < len(ai_scenes) and isinstance(ai_scenes[index], dict) else {}
        fallback_text = (
            sentences[index] if index < len(sentences) else fallback.get("sentence") or f"{fallback['char']} 在故事里出现。"
        )
        ai_text = str(ai_scene.get("text", "")).strip()
        ai_dialogue = str(ai_scene.get("dialogue_line", "")).strip()
        text = ai_text if _contains_cjk(ai_text) else fallback_text
        dialogue_line = ai_dialogue if _contains_cjk(ai_dialogue) else text
        scene_focus = ai_scene.get("focus_chars") or [item["char"] for item in chosen[index : index + 3]] or [fallback["char"]]
        focus_words = ai_scene.get("focus_words") or words[index : index + 2]
        text_pinyin_data = _build_text_pinyin_data(text, pronunciation_lookup)
        dialogue_pinyin_data = _build_text_pinyin_data(dialogue_line, pronunciation_lookup)
        title = ai_scene.get("title") or (SCENE_TITLES[index] if index < len(SCENE_TITLES) else f"场景 {index + 1}")
        if not _contains_cjk(str(title)):
            title = SCENE_TITLES[index] if index < len(SCENE_TITLES) else f"场景 {index + 1}"
        story.append(
            {
                "id": f"scene-{index + 1}",
                "title": title,
                "text": text,
                "pinyin_text": text_pinyin_data["pinyin_text"] or dialogue_pinyin_data["pinyin_text"],
                "pronunciation_labels": text_pinyin_data["pronunciation_labels"] or dialogue_pinyin_data["pronunciation_labels"],
                "dialogue_line": dialogue_line,
                "dialogue_pinyin": dialogue_pinyin_data["pinyin_text"],
                "focus_chars": scene_focus,
                "focus_words": focus_words,
                "image_prompt": ai_scene.get("image_prompt", ""),
                "video_prompt": ai_scene.get("video_prompt", ""),
                "video_script": ai_scene.get("video_script", ""),
                "focus_pronunciations": [
                    {
                        "char": char,
                        "pinyin": numeric_to_tone_marked(char_lookup[char].get("pinyin", "")),
                    }
                    for char in scene_focus
                    if char in char_lookup
                ],
            }
        )

    image_tasks, video_storyboard, video_tasks, story_audio_tasks = build_prompts_for_story(story, workflow_rules)

    word_items = []
    for word in words[: int(workflow_rules.get("wordTarget", 6))]:
        word_pinyin_data = _build_text_pinyin_data(word, pronunciation_lookup)
        word_items.append(
            {
                "text": word,
                "pinyin_text": word_pinyin_data["pinyin_text"],
                "pronunciation_labels": word_pinyin_data["pronunciation_labels"],
                "audio_text": word,
                "audio_status": "pending",
                "audio_path": "",
            }
        )
    sentence_items = []
    for index, sentence in enumerate(sentences[: int(workflow_rules.get("sentenceTarget", 4))]):
        sentence_pinyin_data = _build_text_pinyin_data(sentence, pronunciation_lookup)
        sentence_items.append(
            {
                "id": f"sentence-{index + 1}",
                "text": sentence,
                "pinyin_text": sentence_pinyin_data["pinyin_text"],
                "pronunciation_labels": sentence_pinyin_data["pronunciation_labels"],
                "audio_text": sentence,
                "audio_status": "pending",
                "audio_path": "",
            }
        )

    audio_tasks = [
        *[
            {
                "scope": "char",
                "id": item["char"],
                "text": item["audio_text"],
                "status": item["audio_status"],
                "file_path": item["audio_path"],
            }
            for item in char_cards
        ],
        *[
            {
                "scope": "word",
                "id": f"word-{index + 1}",
                "text": item["audio_text"],
                "status": item["audio_status"],
                "file_path": item["audio_path"],
            }
            for index, item in enumerate(word_items)
        ],
        *[
            {
                "scope": "sentence",
                "id": item["id"],
                "text": item["audio_text"],
                "status": item["audio_status"],
                "file_path": item["audio_path"],
            }
            for item in sentence_items
        ],
        *story_audio_tasks,
    ]

    return {
        "week_id": current_week_id(current_time),
        "learner_id": "default",
        "generated_at": current_time.isoformat(),
        "title": title,
        "summary": summary,
        "new_chars": new_chars,
        "review_chars": review_chars,
        "char_cards": char_cards,
        "words": word_items,
        "sentences": sentence_items,
        "story": story,
        "image_tasks": image_tasks,
        "video_tasks": video_tasks,
        "video_storyboard": video_storyboard,
        "audio_tasks": audio_tasks,
        "worksheet": {
            "status": "pending",
            "file_path": "",
            "page_size": "A4",
            "entries": len(char_cards),
        },
        "status": "ready",
    }


def regenerate_pack_prompts(current_week: dict, workflow_rules: dict) -> dict:
    story = list(current_week.get("story", []))
    char_pronunciation_lookup = {
        item.get("char", ""): numeric_to_tone_marked(item.get("pinyin_numeric", ""))
        or item.get("pinyin", "")
        for item in current_week.get("char_cards", [])
        if item.get("char")
    }
    if not char_pronunciation_lookup:
        char_pronunciation_lookup = {
            item.get("char", ""): numeric_to_tone_marked(item.get("pinyin", ""))
            for item in _load_character_bank()
            if item.get("char")
        }
    else:
        for item in _load_character_bank():
            char = item.get("char", "")
            if char and char not in char_pronunciation_lookup:
                char_pronunciation_lookup[char] = numeric_to_tone_marked(item.get("pinyin", ""))

    for scene in story:
        text_pinyin_data = _build_text_pinyin_data(scene.get("text", ""), char_pronunciation_lookup)
        dialogue_pinyin_data = _build_text_pinyin_data(scene.get("dialogue_line", scene.get("text", "")), char_pronunciation_lookup)
        scene["pinyin_text"] = text_pinyin_data["pinyin_text"] or dialogue_pinyin_data["pinyin_text"]
        scene["pronunciation_labels"] = text_pinyin_data["pronunciation_labels"] or dialogue_pinyin_data["pronunciation_labels"]
        scene["dialogue_pinyin"] = dialogue_pinyin_data["pinyin_text"]
        scene["focus_pronunciations"] = [
            {"char": char, "pinyin": char_pronunciation_lookup.get(char, "")}
            for char in scene.get("focus_chars", [])
            if char_pronunciation_lookup.get(char, "")
        ]

    image_tasks, video_storyboard, video_tasks, story_audio_tasks = build_prompts_for_story(
        story,
        workflow_rules,
        overwrite_existing=True,
    )
    current_week["story"] = story
    current_week["image_tasks"] = image_tasks
    current_week["video_tasks"] = video_tasks
    current_week["video_storyboard"] = video_storyboard
    current_week["audio_tasks"] = [
        *[
            {
                "scope": "char",
                "id": item["char"],
                "text": item.get("audio_text", item.get("pronunciation_guide", item["char"])),
                "status": item.get("audio_status", "pending"),
                "file_path": item.get("audio_path", ""),
            }
            for item in current_week.get("char_cards", [])
        ],
        *[
            {
                "scope": "word",
                "id": f"word-{index + 1}",
                "text": item.get("audio_text", item.get("text", "")),
                "status": item.get("audio_status", "pending"),
                "file_path": item.get("audio_path", ""),
            }
            for index, item in enumerate(current_week.get("words", []))
        ],
        *[
            {
                "scope": "sentence",
                "id": item.get("id", f"sentence-{index + 1}"),
                "text": item.get("audio_text", item.get("text", "")),
                "status": item.get("audio_status", "pending"),
                "file_path": item.get("audio_path", ""),
            }
            for index, item in enumerate(current_week.get("sentences", []))
        ],
        *story_audio_tasks,
    ]
    current_week["generated_at"] = datetime.now(UTC).isoformat()
    current_week["status"] = "ready"
    return current_week
