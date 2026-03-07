from __future__ import annotations

import random
from datetime import UTC, datetime


def current_week_id(now: datetime | None = None) -> str:
    date = now or datetime.now(UTC)
    year, week_number, _ = date.isocalendar()
    return f"{year}-W{week_number:02d}"


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


def select_weekly_characters(
    characters: list[dict],
    progress: dict,
    workflow_rules: dict,
    now: datetime,
) -> dict[str, list[dict]]:
    items = progress.get("items", {})
    level = workflow_rules.get("level", 1)
    level_chars = [item for item in characters if item.get("level") == level]

    review_candidates = [item for item in level_chars if item.get("char") in items]
    review_candidates.sort(
        key=lambda item: _review_sort_key(items.get(item["char"], {}), now)
    )

    review_count = int(workflow_rules.get("weeklyReviewCount", 3))
    review_pool_size = max(review_count * 2, review_count)
    review_pool = review_candidates[:review_pool_size]
    rng = random.Random(current_week_id(now))
    rng.shuffle(review_pool)
    review = review_pool[:review_count]

    new_candidates = [item for item in level_chars if item.get("char") not in items]
    rng.shuffle(new_candidates)
    fresh = new_candidates[: int(workflow_rules.get("weeklyNewCount", 4))]

    return {
        "new_chars": fresh,
        "review_chars": review,
        "all_chars": [*fresh, *review],
    }
