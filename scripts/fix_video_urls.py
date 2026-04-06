#!/usr/bin/env python3
"""Fix primary video_url for all tutorials: set to first Russian video from resources.videos."""
import json

TASKS_FILE = "tasks.json"

def main():
    with open(TASKS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    updated = 0
    for task in data.get("tasks", []):
        if task.get("task_type") != "tutorial":
            continue
        videos = task.get("resources", {}).get("videos", [])
        if videos:
            first_url = videos[0].get("url", "")
            if first_url and task.get("video_url") != first_url:
                task["video_url"] = first_url
                updated += 1

    with open(TASKS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"✅ Updated {updated} tutorial video_url fields to Russian videos")

    # Verify
    with open(TASKS_FILE) as f:
        check = json.load(f)
    tuts = [t for t in check["tasks"] if t.get("task_type") == "tutorial"]
    mismatched = 0
    for t in tuts:
        vids = t.get("resources", {}).get("videos", [])
        if vids and t.get("video_url") != vids[0].get("url"):
            mismatched += 1
    print(f"Remaining mismatches: {mismatched}")

if __name__ == "__main__":
    main()
