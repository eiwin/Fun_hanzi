from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
HSK_DIR = BASE_DIR / "hskhsk.com-main" / "data" / "lists"
CEDICT_PATH = BASE_DIR / "hskhsk.com-main" / "hanzigraphs" / "data" / "cedict_ts.u8"
CHARACTERS_PATH = BASE_DIR / "data" / "characters.json"
WORD_BANK_PATH = BASE_DIR / "data" / "hsk_word_bank.json"
CHAR_ORDER_PATH = BASE_DIR / "data" / "hsk_characters_l1_l4.json"

LEVELS = [1, 2, 3, 4]


def parse_hsk_definition_files() -> list[dict]:
    items: list[dict] = []
    order = 1
    for level in LEVELS:
        path = HSK_DIR / f"HSK Official With Definitions 2012 L{level}.txt"
        with path.open("r", encoding="utf-8-sig") as handle:
            for line in handle:
                parts = line.rstrip("\n").split("\t")
                if len(parts) < 5:
                    continue
                simplified, traditional, pinyin_numeric, pinyin_marked, meaning = [part.strip() for part in parts[:5]]
                if not simplified:
                    continue
                items.append(
                    {
                        "word": simplified,
                        "traditional": traditional,
                        "pinyin": pinyin_numeric,
                        "pinyinMarked": pinyin_marked,
                        "meaning": meaning,
                        "level": level,
                        "sourceOrder": order,
                    }
                )
                order += 1
    return items


def parse_single_char_lookup() -> dict[str, dict]:
    lookup: dict[str, dict] = {}
    csv_path = HSK_DIR / "New_HSK_2010.csv"
    with csv_path.open("r", encoding="utf-8-sig", errors="ignore") as handle:
        reader = csv.reader(handle)
        for row in reader:
            if len(row) < 4:
                continue
            level_text, word, pinyin, meaning = row[:4]
            if len(word) != 1 or word in lookup:
                continue
            level = int(level_text) if level_text.isdigit() else 0
            lookup[word] = {
                "pinyin": pinyin.strip(),
                "meaning": meaning.strip(),
                "level": level,
            }
    return lookup


def parse_cedict_lookup() -> dict[str, dict]:
    lookup: dict[str, dict] = {}
    pattern = re.compile(r"([^ ]+) ([^ ]+) \[([^\]]+)\] /(.*)/")
    with CEDICT_PATH.open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            if line.startswith("#"):
                continue
            match = pattern.match(line.strip())
            if not match:
                continue
            traditional, simplified, pinyin, meaning = match.groups()
            if len(simplified) != 1 or simplified in lookup:
                continue
            lookup[simplified] = {
                "traditional": traditional,
                "pinyin": pinyin.replace(" ", ""),
                "meaning": meaning.split("/")[0].strip(),
            }
    return lookup


def build_character_entries(
    words: list[dict],
    existing_characters: list[dict],
    single_char_lookup: dict[str, dict],
    cedict_lookup: dict[str, dict],
) -> list[dict]:
    existing_map = {item.get("char"): item for item in existing_characters if item.get("char")}
    char_words: dict[str, list[str]] = defaultdict(list)
    char_level: dict[str, int] = {}
    char_order: dict[str, int] = {}
    char_meaning_fallback: dict[str, str] = {}

    order = 1
    for word in words:
        simplified = word["word"]
        for char in simplified:
            if char not in char_order:
                char_order[char] = order
                char_level[char] = word["level"]
                order += 1
            if simplified not in char_words[char]:
                char_words[char].append(simplified)
            char_meaning_fallback.setdefault(char, word["meaning"])

    records: list[dict] = []
    for char, source_order in sorted(char_order.items(), key=lambda item: item[1]):
        existing = dict(existing_map.get(char, {}))
        single = single_char_lookup.get(char, {})
        cedict = cedict_lookup.get(char, {})
        words_for_char = char_words.get(char, [])

        pinyin = (
            existing.get("pinyin")
            or single.get("pinyin")
            or cedict.get("pinyin", "")
        )
        meaning = (
            existing.get("meaning")
            or single.get("meaning")
            or cedict.get("meaning")
            or char_meaning_fallback.get(char, "")
        )

        sample_words = existing.get("words") or words_for_char[:6]
        sample_sentence = existing.get("sentence")
        if not sample_sentence:
            if words_for_char:
                sample_sentence = f"我们学习“{words_for_char[0]}”。"
            else:
                sample_sentence = char

        record = {
            "char": char,
            "pinyin": pinyin,
            "meaning": meaning,
            "hskOrder": source_order,
            "frequencyRank": source_order,
            "level": char_level[char],
            "words": sample_words,
            "sentence": sample_sentence,
            "tags": sorted(set((existing.get("tags") or []) + ["hsk", f"hsk{char_level[char]}"])),
            "source": "hskhsk",
            "sourceUrl": "",
        }

        for field in ["radical", "strokeCount", "strokeHint", "structure", "components"]:
            if field in existing:
                record[field] = existing[field]

        records.append(record)
    return records


def main() -> None:
    words = parse_hsk_definition_files()
    existing_characters = json.loads(CHARACTERS_PATH.read_text())
    single_char_lookup = parse_single_char_lookup()
    cedict_lookup = parse_cedict_lookup()

    characters = build_character_entries(words, existing_characters, single_char_lookup, cedict_lookup)

    WORD_BANK_PATH.write_text(
        json.dumps(
            {
                "source": "hskhsk.com",
                "importedAt": datetime.now(UTC).isoformat(),
                "levels": LEVELS,
                "count": len(words),
                "items": words,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )

    CHAR_ORDER_PATH.write_text(
        json.dumps(
            {
                "source": "hskhsk.com",
                "importedAt": datetime.now(UTC).isoformat(),
                "levels": LEVELS,
                "count": len(characters),
                "items": characters,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )

    CHARACTERS_PATH.write_text(json.dumps(characters, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "words": len(words),
                "characters": len(characters),
                "wordBankPath": str(WORD_BANK_PATH),
                "characterPath": str(CHARACTERS_PATH),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
