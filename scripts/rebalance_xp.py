#!/usr/bin/env python3
"""
Rebalance XP across all tasks in tasks.json and content/ files.

Tier target ranges:
  D:  15 -  40  (beginner, single concept)
  C:  40 - 100  (intermediate, requires thought)
  B: 100 - 200  (advanced, multi-step)
  A: 200 - 350  (expert, complex logic)
  S: 350 - 600  (master, final exam level)

Complexity heuristics score 0.0-1.0 within tier range:
  - Number of test cases (more = harder)
  - Description length (proxy for complexity)
  - Is boss type? (+0.15 bonus)
  - Manual engine? (fixed 0.5 — can't judge automatically)
"""

import json
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TASKS_FILE = os.path.join(BASE_DIR, "tasks.json")
CONTENT_DIR = os.path.join(BASE_DIR, "content")

# XP ranges per tier: (min, max)
TIER_RANGES = {
    "D": (15, 40),
    "C": (40, 100),
    "B": (100, 200),
    "A": (200, 350),
    "S": (350, 600),
}


def complexity_score(task: dict) -> float:
    """
    Estimate task complexity on a 0.0-1.0 scale from task metadata.
    """
    score = 0.0
    weights_total = 0.0

    logic = task.get("check_logic") or {}
    engine = (logic.get("engine") or "").lower()

    # 1. Manual tasks: use description length + campaign position
    if engine == "manual":
        desc = task.get("description", "")
        campaign = task.get("campaign") or {}
        act = campaign.get("act", 1)
        # Manual tasks scored by description and act position
        base = min(1.0, len(desc) / 150.0) * 0.4
        progress = min(1.0, (act - 1) / 4.0) * 0.4
        boss_bonus = 0.2 if campaign.get("type") == "boss" else 0.0
        return min(1.0, max(0.0, base + progress + boss_bonus))

    # 2. Number of test cases (visible + hidden)
    visible = logic.get("cases") if isinstance(logic.get("cases"), list) else []
    hidden = logic.get("hidden_cases") if isinstance(logic.get("hidden_cases"), list) else []
    total_cases = len(visible) + len(hidden)
    # Normalize: 1-2 simple, 3-4 moderate, 5+ complex
    case_score = min(1.0, max(0.0, (total_cases - 1) / 5.0))
    score += case_score * 2.5
    weights_total += 2.5

    # 3. Description length (proxy for complexity)
    desc = task.get("description", "")
    desc_len = len(desc)
    # Normalize: <30 trivial, 30-150 moderate, >150 complex
    desc_score = min(1.0, max(0.0, desc_len / 180.0))
    score += desc_score * 2.0
    weights_total += 2.0

    # 4. Initial code length (more boilerplate = more complex problem)
    initial = task.get("initial_code", "")
    code_score = min(1.0, max(0.0, len(initial) / 200.0))
    score += code_score * 1.5
    weights_total += 1.5

    # 5. Boss/campaign type bonus
    campaign = task.get("campaign") or {}
    if campaign.get("type") == "boss":
        score += 1.0 * 2.0
        weights_total += 2.0
    else:
        weights_total += 2.0  # still count for normalization

    # 6. Act/chapter (later = harder, stronger weight)
    act = campaign.get("act", 1)
    chapter = campaign.get("chapter", 1)
    progress_score = min(1.0, (act - 1) * 0.25 + (chapter - 1) * 0.08)
    score += progress_score * 1.5
    weights_total += 1.5

    # 7. Deterministic jitter based on task ID to spread ties
    task_id = task.get("id", "")
    hash_val = hash(task_id) % 1000 / 1000.0  # 0.0-1.0
    jitter = (hash_val - 0.5) * 0.15  # ±0.075
    
    if weights_total == 0:
        return 0.5

    raw = score / weights_total + jitter
    return min(1.0, max(0.0, raw))


def rebalance_xp(task: dict) -> int:
    """Calculate new balanced XP for a task based on its tier and complexity."""
    tier = (task.get("tier") or "D").upper()
    if tier not in TIER_RANGES:
        tier = "D"

    low, high = TIER_RANGES[tier]
    cx = complexity_score(task)

    # Linear interpolation within tier range
    xp = low + cx * (high - low)

    # Round to nearest 5 for cleanliness
    xp = round(xp / 5) * 5
    xp = max(low, min(high, xp))

    return int(xp)


def main():
    # Load tasks.json
    print(f"Loading {TASKS_FILE}...")
    with open(TASKS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    tasks = data.get("tasks", [])
    print(f"Found {len(tasks)} tasks")

    # Rebalance
    changes = 0
    tier_stats = {}
    for task in tasks:
        old_xp = task.get("xp", 0)
        new_xp = rebalance_xp(task)
        tier = (task.get("tier") or "D").upper()

        if tier not in tier_stats:
            tier_stats[tier] = {"count": 0, "old_xps": [], "new_xps": []}
        tier_stats[tier]["count"] += 1
        tier_stats[tier]["old_xps"].append(old_xp)
        tier_stats[tier]["new_xps"].append(new_xp)

        if old_xp != new_xp:
            changes += 1
            task["xp"] = new_xp

    # Print summary
    print(f"\n{'='*60}")
    print(f"REBALANCE SUMMARY (changed {changes}/{len(tasks)} tasks)")
    print(f"{'='*60}")
    for tier in ["D", "C", "B", "A", "S"]:
        s = tier_stats.get(tier)
        if not s:
            continue
        old = s["old_xps"]
        new = s["new_xps"]
        target = TIER_RANGES[tier]
        print(f"\nTier {tier} ({s['count']} tasks)  [target: {target[0]}-{target[1]}]")
        print(f"  Before: {min(old):4d} - {max(old):4d}  (median {sorted(old)[len(old)//2]})")
        print(f"  After:  {min(new):4d} - {max(new):4d}  (median {sorted(new)[len(new)//2]})")

    # Save tasks.json
    with open(TASKS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"\n✅ Saved {TASKS_FILE}")

    # Also update content files to stay in sync
    # Build a map of task_id -> new_xp
    xp_map = {t["id"]: t["xp"] for t in tasks}

    content_files = [
        "tasks_python.json",
        "tasks_javascript.json",
        "tasks_frontend.json",
        "tasks_scratch.json",
    ]
    for filename in content_files:
        path = os.path.join(CONTENT_DIR, filename)
        if not os.path.exists(path):
            print(f"⚠ {filename} not found, skipping")
            continue

        with open(path, "r", encoding="utf-8") as f:
            content_tasks = json.load(f)

        updated = 0
        for ct in content_tasks:
            tid = ct.get("id")
            if tid and tid in xp_map and ct.get("xp") != xp_map[tid]:
                ct["xp"] = xp_map[tid]
                updated += 1

        with open(path, "w", encoding="utf-8") as f:
            json.dump(content_tasks, f, indent=2, ensure_ascii=False)
        print(f"✅ Updated {filename}: {updated} tasks changed")

    print(f"\n🎯 Done! All tasks rebalanced.")


if __name__ == "__main__":
    main()
