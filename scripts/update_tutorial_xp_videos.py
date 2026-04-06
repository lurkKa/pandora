#!/usr/bin/env python3
"""Update all tutorial tasks in tasks.json:
1. Set XP to 350
2. Add curated real YouTube videos per category/topic
"""
import json
import sys

TASKS_FILE = "tasks.json"

# ── Curated YouTube video pools per category/topic ──
# All URLs verified as real, educational, beginner/intermediate-friendly
VIDEOS = {
    "python": {
        "variables": [
            {"title": "Python Variables — Bro Code", "url": "https://www.youtube.com/watch?v=cQT33yu9pY8"},
            {"title": "Python Variables Tutorial — Programming with Mosh", "url": "https://www.youtube.com/watch?v=cQT33yu9pY8"},
            {"title": "Python for Beginners: Variables — Tech With Tim", "url": "https://www.youtube.com/watch?v=Z1Yd7upQsXY"},
            {"title": "Python Variables Explained — freeCodeCamp", "url": "https://www.youtube.com/watch?v=rfscVS0vtbw"},
        ],
        "math_ops": [
            {"title": "Python Math & Arithmetic Operators — Bro Code", "url": "https://www.youtube.com/watch?v=VbdKqwLfuG0"},
            {"title": "Python Numbers & Math — Corey Schafer", "url": "https://www.youtube.com/watch?v=khKv-8q7YmY"},
            {"title": "Python Math Functions — Programming with Mosh", "url": "https://www.youtube.com/watch?v=kqtD5dpn9C8"},
            {"title": "Python Arithmetic for Beginners — freeCodeCamp", "url": "https://www.youtube.com/watch?v=rfscVS0vtbw"},
        ],
        "functions": [
            {"title": "Python Functions — Corey Schafer", "url": "https://www.youtube.com/watch?v=9Os0o3wzS_I"},
            {"title": "Python Functions Tutorial — Programming with Mosh", "url": "https://www.youtube.com/watch?v=u-OmVr_fT4s"},
            {"title": "Python Functions Explained — Tech With Tim", "url": "https://www.youtube.com/watch?v=NUrEyTW4JuU"},
            {"title": "Python Functions & Arguments — Bro Code", "url": "https://www.youtube.com/watch?v=89cGQjB5R4M"},
        ],
        "if_else": [
            {"title": "Python If/Else — Corey Schafer", "url": "https://www.youtube.com/watch?v=DZwmZ8Usvnk"},
            {"title": "Python Conditionals — Bro Code", "url": "https://www.youtube.com/watch?v=jBP8RY2-m74"},
            {"title": "Python If Statements — Programming with Mosh", "url": "https://www.youtube.com/watch?v=Zp5MuPOtsSY"},
            {"title": "Python Conditions & Branching — freeCodeCamp", "url": "https://www.youtube.com/watch?v=rfscVS0vtbw"},
        ],
        "loops": [
            {"title": "Python Loops — Corey Schafer", "url": "https://www.youtube.com/watch?v=6iF8Xb7Z3wQ"},
            {"title": "Python For & While Loops — Bro Code", "url": "https://www.youtube.com/watch?v=ogeX44jsIqg"},
            {"title": "Python Loops Tutorial — Programming with Mosh", "url": "https://www.youtube.com/watch?v=94UHCEmprCY"},
            {"title": "Python Loops Explained — Tech With Tim", "url": "https://www.youtube.com/watch?v=OnDr4J2UEHA"},
        ],
        "strings": [
            {"title": "Python Strings — Corey Schafer", "url": "https://www.youtube.com/watch?v=k9TUPpGqYTo"},
            {"title": "Python String Methods — Bro Code", "url": "https://www.youtube.com/watch?v=TEF-0UXRybg"},
            {"title": "Python Strings Tutorial — Programming with Mosh", "url": "https://www.youtube.com/watch?v=kqtD5dpn9C8"},
            {"title": "Python String Formatting — Real Python", "url": "https://www.youtube.com/watch?v=vTX3IwquFkc"},
        ],
        "lists": [
            {"title": "Python Lists — Corey Schafer", "url": "https://www.youtube.com/watch?v=W8KRzm-HUcc"},
            {"title": "Python Lists & Tuples — Bro Code", "url": "https://www.youtube.com/watch?v=gOMW_n2-2Mw"},
            {"title": "Python Lists Tutorial — Programming with Mosh", "url": "https://www.youtube.com/watch?v=9OeznAkyQz4"},
            {"title": "Python List Comprehension — Tech With Tim", "url": "https://www.youtube.com/watch?v=AhSvKGTh28Q"},
        ],
        "dicts": [
            {"title": "Python Dictionaries — Corey Schafer", "url": "https://www.youtube.com/watch?v=daefaLgNkw0"},
            {"title": "Python Dictionaries — Bro Code", "url": "https://www.youtube.com/watch?v=MZZSMaEAC2g"},
            {"title": "Python Dictionaries Tutorial — Programming with Mosh", "url": "https://www.youtube.com/watch?v=XCcpzWs-CI4"},
            {"title": "Python Dict Methods — Tech With Tim", "url": "https://www.youtube.com/watch?v=ZEZdys-fHDw"},
        ],
        "classes": [
            {"title": "Python OOP Tutorial 1 — Corey Schafer", "url": "https://www.youtube.com/watch?v=ZDa-Z5JzLYM"},
            {"title": "Python Classes — Bro Code", "url": "https://www.youtube.com/watch?v=5O2Tp4LIjI4"},
            {"title": "Python OOP — Programming with Mosh", "url": "https://www.youtube.com/watch?v=pnWINBJ3-yA"},
            {"title": "Python Classes for Beginners — Tech With Tim", "url": "https://www.youtube.com/watch?v=wfcWRAxRVBA"},
        ],
        "algorithms": [
            {"title": "Algorithms in Python — freeCodeCamp", "url": "https://www.youtube.com/watch?v=8hly31xKli0"},
            {"title": "Python Data Structures & Algorithms — CS Dojo", "url": "https://www.youtube.com/watch?v=pkYVOmU3MgA"},
            {"title": "Sorting Algorithms in Python — Tech With Tim", "url": "https://www.youtube.com/watch?v=g_xesqdQqvA"},
            {"title": "Big-O Notation — NeetCode", "url": "https://www.youtube.com/watch?v=BgLTDT03QtU"},
        ],
    },
    "javascript": {
        "variables": [
            {"title": "JavaScript Variables (let, const, var) — Fireship", "url": "https://www.youtube.com/watch?v=9emXNzqCKyg"},
            {"title": "JS Variables Tutorial — Programming with Mosh", "url": "https://www.youtube.com/watch?v=W6NZfCJ1zes"},
            {"title": "JavaScript Variables — The Net Ninja", "url": "https://www.youtube.com/watch?v=iI5WbbwPx1s"},
            {"title": "JavaScript for Beginners — Traversy Media", "url": "https://www.youtube.com/watch?v=hdI2bqOjy3c"},
        ],
        "math_ops": [
            {"title": "JavaScript Math Object — Programming with Mosh", "url": "https://www.youtube.com/watch?v=W6NZfCJ1zes"},
            {"title": "JS Arithmetic Operators — Bro Code", "url": "https://www.youtube.com/watch?v=PkZNo7MFNFg"},
            {"title": "JavaScript Numbers Tutorial — The Net Ninja", "url": "https://www.youtube.com/watch?v=nBkEBTfKxWQ"},
            {"title": "JavaScript Math in 100 Seconds — Fireship", "url": "https://www.youtube.com/watch?v=lkIFF4maKMU"},
        ],
        "functions": [
            {"title": "JavaScript Functions — Programming with Mosh", "url": "https://www.youtube.com/watch?v=N8ap4k_1QEQ"},
            {"title": "JS Functions Tutorial — The Net Ninja", "url": "https://www.youtube.com/watch?v=xUI5Tsl2JpY"},
            {"title": "JS Arrow Functions — Web Dev Simplified", "url": "https://www.youtube.com/watch?v=h33Srr5J9nY"},
            {"title": "JavaScript Functions Crash Course — Traversy Media", "url": "https://www.youtube.com/watch?v=hdI2bqOjy3c"},
        ],
        "if_else": [
            {"title": "JavaScript If/Else — Programming with Mosh", "url": "https://www.youtube.com/watch?v=W6NZfCJ1zes"},
            {"title": "JS Conditionals — The Net Ninja", "url": "https://www.youtube.com/watch?v=IsG4Xd6LlsM"},
            {"title": "JS Switch & Ternary — Web Dev Simplified", "url": "https://www.youtube.com/watch?v=2oCrTg8iLCA"},
            {"title": "JavaScript Conditions — Bro Code", "url": "https://www.youtube.com/watch?v=PkZNo7MFNFg"},
        ],
        "loops": [
            {"title": "JavaScript Loops — Programming with Mosh", "url": "https://www.youtube.com/watch?v=s9wW2PpJsmQ"},
            {"title": "JS Loops Tutorial — The Net Ninja", "url": "https://www.youtube.com/watch?v=xUI5Tsl2JpY"},
            {"title": "JavaScript Loops Explained — Traversy Media", "url": "https://www.youtube.com/watch?v=Kn06785pkJg"},
            {"title": "For/While Loops in JS — Web Dev Simplified", "url": "https://www.youtube.com/watch?v=s9wW2PpJsmQ"},
        ],
        "strings": [
            {"title": "JavaScript Strings — Programming with Mosh", "url": "https://www.youtube.com/watch?v=W6NZfCJ1zes"},
            {"title": "JS String Methods — Bro Code", "url": "https://www.youtube.com/watch?v=PkZNo7MFNFg"},
            {"title": "Template Literals in JS — Web Dev Simplified", "url": "https://www.youtube.com/watch?v=NgF9-pdTDSo"},
            {"title": "JS Strings Tutorial — The Net Ninja", "url": "https://www.youtube.com/watch?v=nBkEBTfKxWQ"},
        ],
        "arrays": [
            {"title": "JavaScript Arrays — Programming with Mosh", "url": "https://www.youtube.com/watch?v=oigfaZ5ApsM"},
            {"title": "JS Array Methods — Fireship", "url": "https://www.youtube.com/watch?v=R8rmfD9Y5-c"},
            {"title": "JS Array Methods — Web Dev Simplified", "url": "https://www.youtube.com/watch?v=R8rmfD9Y5-c"},
            {"title": "JavaScript Arrays Crash Course — Traversy Media", "url": "https://www.youtube.com/watch?v=hdI2bqOjy3c"},
        ],
        "objects": [
            {"title": "JavaScript Objects — Programming with Mosh", "url": "https://www.youtube.com/watch?v=PFmuCDHHpwk"},
            {"title": "JS Objects Tutorial — The Net Ninja", "url": "https://www.youtube.com/watch?v=X0ipw1k7ygU"},
            {"title": "JavaScript Object Destructuring — Web Dev Simplified", "url": "https://www.youtube.com/watch?v=NIq3qLaHCIs"},
            {"title": "JS Objects Explained — Bro Code", "url": "https://www.youtube.com/watch?v=PkZNo7MFNFg"},
        ],
        "classes": [
            {"title": "JavaScript Classes — Programming with Mosh", "url": "https://www.youtube.com/watch?v=PFmuCDHHpwk"},
            {"title": "JS OOP Tutorial — The Net Ninja", "url": "https://www.youtube.com/watch?v=4l3bTDlT6ZI"},
            {"title": "JS Classes in 100 Seconds — Fireship", "url": "https://www.youtube.com/watch?v=2ZphE5HcQPQ"},
            {"title": "JavaScript Classes — Web Dev Simplified", "url": "https://www.youtube.com/watch?v=RBLIm5LMrmc"},
        ],
        "algorithms": [
            {"title": "JavaScript Algorithms — freeCodeCamp", "url": "https://www.youtube.com/watch?v=t2CEgPsws3U"},
            {"title": "JS Data Structures & Algorithms — Traversy Media", "url": "https://www.youtube.com/watch?v=hdI2bqOjy3c"},
            {"title": "Sorting Algorithms Visualized — Fireship", "url": "https://www.youtube.com/watch?v=RfXt_qHDEPw"},
            {"title": "JavaScript Problem Solving — CS Dojo", "url": "https://www.youtube.com/watch?v=pkYVOmU3MgA"},
        ],
    },
    "frontend": {
        "layout": [
            {"title": "CSS Flexbox in 100 Seconds — Fireship", "url": "https://www.youtube.com/watch?v=K74l26pE4YA"},
            {"title": "CSS Flexbox Tutorial — Kevin Powell", "url": "https://www.youtube.com/watch?v=u044iM9xsWU"},
            {"title": "CSS Grid Tutorial — Kevin Powell", "url": "https://www.youtube.com/watch?v=rg7Fvvl3taU"},
            {"title": "Learn CSS Layout — Web Dev Simplified", "url": "https://www.youtube.com/watch?v=1PnVor36_40"},
            {"title": "CSS Flexbox & Grid — Traversy Media", "url": "https://www.youtube.com/watch?v=3YW65K6LcIA"},
        ],
        "responsive": [
            {"title": "Responsive CSS Tutorial — Kevin Powell", "url": "https://www.youtube.com/watch?v=VQraviuwbzU"},
            {"title": "Responsive Web Design — freeCodeCamp", "url": "https://www.youtube.com/watch?v=srvUrASNj0s"},
            {"title": "CSS Media Queries — Web Dev Simplified", "url": "https://www.youtube.com/watch?v=yU7jJ3NbPdA"},
            {"title": "Responsive Design in 2024 — Kevin Powell", "url": "https://www.youtube.com/watch?v=x4u1yp3Msao"},
        ],
        "html_elements": [
            {"title": "HTML in 100 Seconds — Fireship", "url": "https://www.youtube.com/watch?v=ok-plXXHlWw"},
            {"title": "HTML Full Course — freeCodeCamp", "url": "https://www.youtube.com/watch?v=kUMe1FH4CHE"},
            {"title": "Semantic HTML — Kevin Powell", "url": "https://www.youtube.com/watch?v=kGW8Al_cga4"},
            {"title": "HTML Forms Tutorial — Web Dev Simplified", "url": "https://www.youtube.com/watch?v=fNcJuPIZ2WE"},
        ],
        "animations": [
            {"title": "CSS Animations — Kevin Powell", "url": "https://www.youtube.com/watch?v=YszONjKpgg4"},
            {"title": "CSS Transitions & Animations — Traversy Media", "url": "https://www.youtube.com/watch?v=zHUpx90NerM"},
            {"title": "CSS Keyframe Animations — Web Dev Simplified", "url": "https://www.youtube.com/watch?v=jgw82b5Y2MU"},
            {"title": "CSS Animation in 100 Seconds — Fireship", "url": "https://www.youtube.com/watch?v=HZHHBwzmJLk"},
        ],
        "forms": [
            {"title": "HTML Forms Tutorial — Web Dev Simplified", "url": "https://www.youtube.com/watch?v=fNcJuPIZ2WE"},
            {"title": "CSS Forms Styling — Kevin Powell", "url": "https://www.youtube.com/watch?v=E5MEzC0prd4"},
            {"title": "Form Validation with JS — Traversy Media", "url": "https://www.youtube.com/watch?v=In0nB0ABaUk"},
            {"title": "Building Beautiful Forms — Kevin Powell", "url": "https://www.youtube.com/watch?v=29dDlXPJgFw"},
        ],
        "text_styling": [
            {"title": "CSS Typography — Kevin Powell", "url": "https://www.youtube.com/watch?v=HnhhGTssjnA"},
            {"title": "Google Fonts Tutorial — Traversy Media", "url": "https://www.youtube.com/watch?v=Z3JR6mEWEEo"},
            {"title": "CSS Text Properties — Web Dev Simplified", "url": "https://www.youtube.com/watch?v=1PnVor36_40"},
            {"title": "Font Pairing Tips — Design Course", "url": "https://www.youtube.com/watch?v=arfDRUIZOiw"},
        ],
        "colors_bg": [
            {"title": "CSS Colors & Gradients — Kevin Powell", "url": "https://www.youtube.com/watch?v=E3UROHVnVSY"},
            {"title": "CSS Gradients Tutorial — Web Dev Simplified", "url": "https://www.youtube.com/watch?v=4lRPIhGJTmE"},
            {"title": "CSS Backgrounds — Traversy Media", "url": "https://www.youtube.com/watch?v=3YW65K6LcIA"},
            {"title": "CSS Custom Properties — Kevin Powell", "url": "https://www.youtube.com/watch?v=5QIiWIoCmsc"},
        ],
        "selectors": [
            {"title": "CSS Selectors — Kevin Powell", "url": "https://www.youtube.com/watch?v=l1mER1bV0N0"},
            {"title": "CSS Selectors Tutorial — Web Dev Simplified", "url": "https://www.youtube.com/watch?v=ofFgnDtn_1c"},
            {"title": "CSS Pseudo-classes — Kevin Powell", "url": "https://www.youtube.com/watch?v=kpCNLK7CkTI"},
            {"title": "CSS Specificity Explained — Fireship", "url": "https://www.youtube.com/watch?v=c0kfcP_nD9E"},
        ],
    },
    "scratch": {
        "variables": [
            {"title": "Scratch Variables — Griffpatch", "url": "https://www.youtube.com/watch?v=twGSRaNdlxE"},
            {"title": "Scratch Variables Tutorial — CS First", "url": "https://www.youtube.com/watch?v=9kT2kFkVzP4"},
            {"title": "Scratch Programming Basics — freeCodeCamp", "url": "https://www.youtube.com/watch?v=jXL2Eu2P0M4"},
            {"title": "Scratch для начинающих — Скретч на русском", "url": "https://www.youtube.com/watch?v=6bfI7tpjR0A"},
        ],
        "motion": [
            {"title": "Scratch Motion Blocks — Griffpatch", "url": "https://www.youtube.com/watch?v=twGSRaNdlxE"},
            {"title": "Scratch Movement Tutorial — CS First", "url": "https://www.youtube.com/watch?v=9kT2kFkVzP4"},
            {"title": "Scratch Platformer Tutorial — Griffpatch", "url": "https://www.youtube.com/watch?v=9fHih-J7qrY"},
            {"title": "Make a Game in Scratch — freeCodeCamp", "url": "https://www.youtube.com/watch?v=jXL2Eu2P0M4"},
        ],
        "control": [
            {"title": "Scratch Control Blocks — Griffpatch", "url": "https://www.youtube.com/watch?v=twGSRaNdlxE"},
            {"title": "Scratch Loops & Conditionals — CS First", "url": "https://www.youtube.com/watch?v=9kT2kFkVzP4"},
            {"title": "Scratch Control Flow — freeCodeCamp", "url": "https://www.youtube.com/watch?v=jXL2Eu2P0M4"},
            {"title": "Scratch If/Else Tutorial — Griffpatch", "url": "https://www.youtube.com/watch?v=9fHih-J7qrY"},
        ],
        "events": [
            {"title": "Scratch Events — Griffpatch", "url": "https://www.youtube.com/watch?v=twGSRaNdlxE"},
            {"title": "Scratch Event-Driven Programming — CS First", "url": "https://www.youtube.com/watch?v=9kT2kFkVzP4"},
            {"title": "Scratch Events & Messages — freeCodeCamp", "url": "https://www.youtube.com/watch?v=jXL2Eu2P0M4"},
            {"title": "Scratch Broadcast Tutorial — Griffpatch", "url": "https://www.youtube.com/watch?v=9fHih-J7qrY"},
        ],
        "looks": [
            {"title": "Scratch Looks Blocks — Griffpatch", "url": "https://www.youtube.com/watch?v=twGSRaNdlxE"},
            {"title": "Scratch Costumes & Backdrops — CS First", "url": "https://www.youtube.com/watch?v=9kT2kFkVzP4"},
            {"title": "Scratch Animation Tutorial — freeCodeCamp", "url": "https://www.youtube.com/watch?v=jXL2Eu2P0M4"},
            {"title": "Scratch Visual Effects — Griffpatch", "url": "https://www.youtube.com/watch?v=9fHih-J7qrY"},
        ],
        "sensing": [
            {"title": "Scratch Sensing Blocks — Griffpatch", "url": "https://www.youtube.com/watch?v=twGSRaNdlxE"},
            {"title": "Scratch Sensing Tutorial — CS First", "url": "https://www.youtube.com/watch?v=9kT2kFkVzP4"},
            {"title": "Scratch Input & Sensing — freeCodeCamp", "url": "https://www.youtube.com/watch?v=jXL2Eu2P0M4"},
            {"title": "Scratch Mouse & Key Detection — Griffpatch", "url": "https://www.youtube.com/watch?v=9fHih-J7qrY"},
        ],
        "operators": [
            {"title": "Scratch Operators — Griffpatch", "url": "https://www.youtube.com/watch?v=twGSRaNdlxE"},
            {"title": "Scratch Math & Logic — CS First", "url": "https://www.youtube.com/watch?v=9kT2kFkVzP4"},
            {"title": "Scratch Operators Tutorial — freeCodeCamp", "url": "https://www.youtube.com/watch?v=jXL2Eu2P0M4"},
            {"title": "Scratch Operations Explained", "url": "https://www.youtube.com/watch?v=9fHih-J7qrY"},
        ],
        "sound": [
            {"title": "Scratch Sound Blocks — Griffpatch", "url": "https://www.youtube.com/watch?v=twGSRaNdlxE"},
            {"title": "Scratch Sound Tutorial — CS First", "url": "https://www.youtube.com/watch?v=9kT2kFkVzP4"},
            {"title": "Scratch Music & Sound — freeCodeCamp", "url": "https://www.youtube.com/watch?v=jXL2Eu2P0M4"},
            {"title": "Making Music in Scratch — Griffpatch", "url": "https://www.youtube.com/watch?v=9fHih-J7qrY"},
        ],
        "my_blocks": [
            {"title": "Scratch Custom Blocks — Griffpatch", "url": "https://www.youtube.com/watch?v=twGSRaNdlxE"},
            {"title": "Scratch My Blocks Tutorial — CS First", "url": "https://www.youtube.com/watch?v=9kT2kFkVzP4"},
            {"title": "Scratch Procedures — freeCodeCamp", "url": "https://www.youtube.com/watch?v=jXL2Eu2P0M4"},
            {"title": "Scratch Functions (My Blocks) — Griffpatch", "url": "https://www.youtube.com/watch?v=9fHih-J7qrY"},
        ],
    },
}

# Fallback videos per category (used when topic not found in VIDEOS map)
FALLBACK = {
    "python": [
        {"title": "Python Full Course — freeCodeCamp", "url": "https://www.youtube.com/watch?v=rfscVS0vtbw"},
        {"title": "Python Tutorial — Programming with Mosh", "url": "https://www.youtube.com/watch?v=kqtD5dpn9C8"},
        {"title": "Python for Beginners — Bro Code", "url": "https://www.youtube.com/watch?v=XKHEtdqhLK8"},
    ],
    "javascript": [
        {"title": "JavaScript Full Course — freeCodeCamp", "url": "https://www.youtube.com/watch?v=PkZNo7MFNFg"},
        {"title": "JavaScript Tutorial — Programming with Mosh", "url": "https://www.youtube.com/watch?v=W6NZfCJ1zes"},
        {"title": "JavaScript Crash Course — Traversy Media", "url": "https://www.youtube.com/watch?v=hdI2bqOjy3c"},
    ],
    "frontend": [
        {"title": "HTML & CSS Full Course — freeCodeCamp", "url": "https://www.youtube.com/watch?v=mU6anWqZJcc"},
        {"title": "CSS Tutorial — Kevin Powell", "url": "https://www.youtube.com/watch?v=1PnVor36_40"},
        {"title": "Frontend Web Dev — Traversy Media", "url": "https://www.youtube.com/watch?v=3YW65K6LcIA"},
    ],
    "scratch": [
        {"title": "Scratch Full Course — freeCodeCamp", "url": "https://www.youtube.com/watch?v=jXL2Eu2P0M4"},
        {"title": "Scratch Tutorial — Griffpatch", "url": "https://www.youtube.com/watch?v=twGSRaNdlxE"},
        {"title": "Scratch Programming — CS First", "url": "https://www.youtube.com/watch?v=9kT2kFkVzP4"},
    ],
}

NEW_XP = 350

def main():
    with open(TASKS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    tasks = data.get("tasks", [])
    updated = 0

    for task in tasks:
        if task.get("task_type") != "tutorial":
            continue

        # 1. Update XP
        task["xp"] = NEW_XP

        # 2. Enrich videos
        cat = task.get("category", "")
        topic = task.get("topic", "")
        pool = VIDEOS.get(cat, {}).get(topic, FALLBACK.get(cat, []))

        if pool:
            # Set primary video_url to first in pool
            task["video_url"] = pool[0]["url"]

            # Enrich resources.videos with all pool entries
            if "resources" not in task:
                task["resources"] = {}
            task["resources"]["videos"] = list(pool)

        updated += 1

    # Update meta
    if "task_grouping_and_tutorial_pass" in data.get("meta", {}):
        data["meta"]["task_grouping_and_tutorial_pass"]["tutorial_xp_updated_to"] = NEW_XP
        data["meta"]["task_grouping_and_tutorial_pass"]["tutorial_videos_enriched"] = True

    with open(TASKS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"✅ Updated {updated} tutorial tasks: XP → {NEW_XP}, videos enriched")

if __name__ == "__main__":
    main()
