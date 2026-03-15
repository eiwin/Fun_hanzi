from __future__ import annotations

import json
import re
from datetime import datetime, UTC
from pathlib import Path
from urllib.parse import unquote


BASE_DIR = Path(__file__).resolve().parents[1]
HTML_PATH = Path("/tmp/hanzicraft_frequency.html")
CHARACTERS_PATH = BASE_DIR / "data" / "characters.json"
OUTPUT_PATH = BASE_DIR / "data" / "hanzicraft_frequency_list.json"
SOURCE_URL = "https://hanzicraft.com/lists/frequency"


def parse_frequency_html(html: str) -> list[dict]:
    matches = re.findall(
        r'<li class="list"><a href="/character/([^"]+)" target="_blank">(.+?)</a>\s*<span>(\d+)</span></li>',
        html,
        flags=re.DOTALL,
    )
    items: list[dict] = []
    for encoded_char, char_text, rank_text in matches:
        char = unquote(encoded_char)
        if len(char) != 1:
            char = char_text.strip()
        items.append(
            {
                "char": char,
                "frequencyRank": int(rank_text),
                "sourceUrl": f"https://hanzicraft.com/character/{encoded_char}",
            }
        )
    return items


def update_characters_json(frequency_items: list[dict]) -> list[dict]:
    characters = json.loads(CHARACTERS_PATH.read_text())
    rank_map = {item["char"]: item for item in frequency_items}

    for index, item in enumerate(characters):
        char = item.get("char", "")
        if char in rank_map:
            item["frequencyRank"] = rank_map[char]["frequencyRank"]
            item["sourceUrl"] = rank_map[char]["sourceUrl"]
        else:
            item["frequencyRank"] = item.get("frequencyRank") or 100000 + index

    characters.sort(key=lambda item: (int(item.get("frequencyRank", 100000)), item.get("char", "")))
    CHARACTERS_PATH.write_text(json.dumps(characters, ensure_ascii=False, indent=2) + "\n")
    return characters


def main() -> None:
    html = HTML_PATH.read_text()
    frequency_items = parse_frequency_html(html)
    if not frequency_items:
        raise RuntimeError("No frequency items found in downloaded HanziCraft HTML.")

    OUTPUT_PATH.write_text(
        json.dumps(
            {
                "source": "HanziCraft Chinese Character Frequency List",
                "sourceUrl": SOURCE_URL,
                "importedAt": datetime.now(UTC).isoformat(),
                "count": len(frequency_items),
                "items": frequency_items,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )

    updated_characters = update_characters_json(frequency_items)
    print(
        json.dumps(
            {
                "frequencyCount": len(frequency_items),
                "updatedCharacters": len(updated_characters),
                "output": str(OUTPUT_PATH),
                "charactersPath": str(CHARACTERS_PATH),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
