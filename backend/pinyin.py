from __future__ import annotations

import re


TONE_NAMES = {
    0: "轻声",
    1: "第一声",
    2: "第二声",
    3: "第三声",
    4: "第四声",
    5: "轻声",
}

VOWEL_MARKS = {
    "a": ["a", "ā", "á", "ǎ", "à"],
    "e": ["e", "ē", "é", "ě", "è"],
    "i": ["i", "ī", "í", "ǐ", "ì"],
    "o": ["o", "ō", "ó", "ǒ", "ò"],
    "u": ["u", "ū", "ú", "ǔ", "ù"],
    "v": ["ü", "ǖ", "ǘ", "ǚ", "ǜ"],
    "ü": ["ü", "ǖ", "ǘ", "ǚ", "ǜ"],
}


def _apply_tone(base: str, tone: int) -> str:
    if tone <= 0 or tone >= 5:
        return base.replace("v", "ü")

    syllable = base.lower().replace("u:", "v").replace("ü", "v")
    priority = ["a", "e", "o"]
    target_index = -1

    for vowel in priority:
        target_index = syllable.find(vowel)
        if target_index != -1:
            break

    if target_index == -1:
        if "iu" in syllable:
            target_index = syllable.find("u")
        elif "ui" in syllable:
            target_index = syllable.find("i")
        else:
            for index, char in enumerate(syllable):
                if char in {"i", "u", "v"}:
                    target_index = index
                    break

    if target_index == -1:
        return base.replace("v", "ü")

    vowel = syllable[target_index]
    marked = VOWEL_MARKS[vowel][tone]
    result = syllable[:target_index] + marked + syllable[target_index + 1 :]
    return result.replace("v", "ü")


def numeric_to_tone_marked(pinyin: str) -> str:
    if not pinyin:
        return ""

    parts = re.split(r"(\s+)", pinyin.strip())
    converted: list[str] = []

    for part in parts:
        if not part or part.isspace():
            converted.append(part)
            continue

        tone = 0
        base = part
        if part[-1].isdigit():
            tone = int(part[-1])
            base = part[:-1]
        converted.append(_apply_tone(base, tone))

    return "".join(converted)


def extract_tone_number(pinyin: str) -> int:
    if pinyin and pinyin[-1].isdigit():
        tone = int(pinyin[-1])
        return tone if tone in {0, 1, 2, 3, 4, 5} else 0
    return 0


def build_pronunciation_guide(text: str, pinyin: str) -> str:
    tone = extract_tone_number(pinyin)
    marked = numeric_to_tone_marked(pinyin)
    tone_name = TONE_NAMES.get(tone, "轻声")
    if not marked:
        return text
    return f"{text}，{tone_name}，{marked}"
