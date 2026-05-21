#!/usr/bin/env python3
"""
Merge 20% of kahoot_1.json + 100% of kahoot_2.json into a unified quiz_bank.json.

Unified schema per item:
  id, domain, topic, difficulty (1-5), question, options [{id, text}],
  answer_index (0-based), explanation, time_limit_sec
"""
import json, random, sys, os
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

KAHOOT_1 = os.path.join(ROOT, "kahoot_1.json")
KAHOOT_2 = os.path.join(ROOT, "kahoot_2.json")
OUTPUT   = os.path.join(ROOT, "quiz_bank.json")

SAMPLE_RATIO_1 = 0.20  # 20% from kahoot_1


def _normalize_difficulty(raw) -> int:
    """Map any difficulty value to 1-5 int."""
    if isinstance(raw, int):
        return max(1, min(5, raw))
    mapping = {"beginner": 1, "easy": 2, "medium": 3, "hard": 4, "expert": 5}
    return mapping.get(str(raw).lower().strip(), 2)


def _normalize_options(opts) -> list[dict]:
    """Ensure options are [{id: 'A', text: '...'}, ...]."""
    letters = "ABCDEFGH"
    result = []
    for i, o in enumerate(opts or []):
        if isinstance(o, dict):
            result.append({"id": o.get("id", letters[i] if i < len(letters) else str(i)), "text": str(o.get("text", ""))})
        elif isinstance(o, str):
            result.append({"id": letters[i] if i < len(letters) else str(i), "text": o})
    return result


def _normalize_item(item: dict, source: str) -> dict:
    """Convert to unified schema."""
    diff = _normalize_difficulty(item.get("difficulty", 2))
    time_limit = int(item.get("time_limit_sec") or (15 + diff * 3))  # 18-30 sec
    return {
        "id": item.get("id", ""),
        "domain": item.get("domain", ""),
        "topic": item.get("topic", ""),
        "difficulty": diff,
        "question": item.get("question", ""),
        "options": _normalize_options(item.get("options")),
        "answer_index": int(item.get("answer_index", 0)),
        "explanation": item.get("explanation", ""),
        "time_limit_sec": time_limit,
        "source": source,
    }


def main():
    print("Loading kahoot_1.json ...")
    with open(KAHOOT_1, encoding="utf-8") as f:
        data1 = json.load(f)
    items1 = data1.get("items", []) if isinstance(data1, dict) else data1

    print("Loading kahoot_2.json ...")
    with open(KAHOOT_2, encoding="utf-8") as f:
        data2 = json.load(f)
    items2 = data2.get("items", []) if isinstance(data2, dict) else data2

    # Sample 20% from kahoot_1
    sample_count = int(len(items1) * SAMPLE_RATIO_1)
    sampled_1 = random.sample(items1, sample_count)
    print(f"  kahoot_1: {len(items1)} total → sampled {len(sampled_1)} ({SAMPLE_RATIO_1*100:.0f}%)")
    print(f"  kahoot_2: {len(items2)} total → 100%")

    # Normalize
    unified = []
    for item in sampled_1:
        unified.append(_normalize_item(item, "kahoot_1"))
    for item in items2:
        unified.append(_normalize_item(item, "kahoot_2"))

    # Shuffle
    random.shuffle(unified)

    # Stats
    diff_dist = {}
    domain_dist = {}
    for it in unified:
        diff_dist[it["difficulty"]] = diff_dist.get(it["difficulty"], 0) + 1
        domain_dist[it["domain"]] = domain_dist.get(it["domain"], 0) + 1

    bank = {
        "meta": {
            "total": len(unified),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "sources": {"kahoot_1_sampled": len(sampled_1), "kahoot_2_full": len(items2)},
            "difficulty_distribution": diff_dist,
            "domain_distribution": domain_dist,
        },
        "items": unified,
    }

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(bank, f, ensure_ascii=False, separators=(",", ":"))

    size_mb = os.path.getsize(OUTPUT) / 1024 / 1024
    print(f"\n✅ quiz_bank.json created: {len(unified)} questions, {size_mb:.1f} MB")
    print(f"   Difficulty: {diff_dist}")
    print(f"   Domains: {domain_dist}")


if __name__ == "__main__":
    main()
