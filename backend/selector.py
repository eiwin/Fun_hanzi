from __future__ import annotations

import random
import re
from datetime import datetime, timedelta


def current_week_id(now: datetime | None = None) -> str:
    date = now.astimezone() if now else datetime.now().astimezone()
    year, week_number, _ = date.isocalendar()
    return f"{year}-W{week_number:02d}"


def week_id_to_datetime(week_id: str) -> datetime:
    match = re.fullmatch(r"(\d{4})-W(\d{2})", week_id)
    if not match:
        raise ValueError(f"Invalid week_id: {week_id}")
    year = int(match.group(1))
    week = int(match.group(2))
    base = datetime.fromisocalendar(year, week, 1)
    local_tz = datetime.now().astimezone().tzinfo
    return base.replace(tzinfo=local_tz)


def shift_week_id(week_id: str, offset: int) -> str:
    shifted = week_id_to_datetime(week_id) + timedelta(weeks=offset)
    return current_week_id(shifted)


def _days_since(last_seen: str, now: datetime) -> int:
    if not last_seen:
        return 999
    try:
        seen_date = datetime.fromisoformat(last_seen).date()
    except ValueError:
        return 999
    return max((now.date() - seen_date).days, 0)


def _review_sort_key(progress_entry: dict, now: datetime) -> tuple[int, int, int]:
    box = int(progress_entry.get("box", 0))
    wrong_count = int(progress_entry.get("wrongCount", 0))
    days = _days_since(progress_entry.get("lastSeen", ""), now)
    return (box, -wrong_count, -days)


def _frequency_rank(item: dict, fallback_rank: int) -> int:
    rank = item.get("frequencyRank")
    if isinstance(rank, int) and rank > 0:
        return rank
    return fallback_rank


def _level_sequence(workflow_rules: dict) -> list[int]:
    sequence = workflow_rules.get("levelSequence")
    if isinstance(sequence, list):
        parsed = [int(level) for level in sequence if str(level).isdigit()]
        if parsed:
            return parsed

    level = workflow_rules.get("level")
    if isinstance(level, int):
        return [level]
    if isinstance(level, str) and level.isdigit():
        return [int(level)]
    return [1]


def _character_sort_key(item: dict, fallback_rank: int, workflow_rules: dict, level_index: dict[int, int]) -> tuple[int, int]:
    strategy = workflow_rules.get("newCharStrategy", "frequency_order")
    if strategy == "hsk_level_order":
        return (
            level_index.get(int(item.get("level", 999)), 999),
            int(item.get("hskOrder") or item.get("sourceOrder") or fallback_rank),
        )
    return (
        level_index.get(int(item.get("level", 999)), 999),
        _frequency_rank(item, fallback_rank),
    )


def _introduced_chars(progress: dict) -> set[str]:
    introduced: set[str] = set(progress.get("items", {}).keys())
    for pack in progress.get("weeklyPacks", []):
        introduced.update(pack.get("newChars", []))
        introduced.update(pack.get("reviewChars", []))
    return {char for char in introduced if char}


def select_weekly_characters(
    characters: list[dict],
    progress: dict,
    workflow_rules: dict,
    now: datetime,
) -> dict[str, list[dict]]:
    items = progress.get("items", {})
    introduced_chars = _introduced_chars(progress)
    allowed_levels = _level_sequence(workflow_rules)
    level_index = {level: index for index, level in enumerate(allowed_levels)}
    level_chars = [item for item in characters if int(item.get("level", 0) or 0) in level_index]
    ordered_level_chars = sorted(
        level_chars,
        key=lambda item: _character_sort_key(item, characters.index(item) + 1, workflow_rules, level_index),
    )

    review_candidates = [item for item in ordered_level_chars if item.get("char") in introduced_chars]
    review_candidates.sort(
        key=lambda item: _review_sort_key(items.get(item["char"], {}), now)
    )

    review_count = int(workflow_rules.get("weeklyReviewCount", 3))
    review_pool_size = max(review_count * 2, review_count)
    review_pool = review_candidates[:review_pool_size]
    rng = random.Random(current_week_id(now))
    rng.shuffle(review_pool)
    review = review_pool[:review_count]

    new_candidates = [item for item in ordered_level_chars if item.get("char") not in introduced_chars]
    fresh = new_candidates[: int(workflow_rules.get("weeklyNewCount", 5))]

    return {
        "new_chars": fresh,
        "review_chars": review,
        "all_chars": [*fresh, *review],
        "character_pool": ordered_level_chars,
    }
