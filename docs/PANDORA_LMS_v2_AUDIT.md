   # PANDORA LMS v2.0 — Comprehensive Audit (Baseline v1.x)

Date: 2026-02-04  
Scope: `main.py`, `index.html`, `admin.html`, `tasks.json` as found in this workspace before refactoring.  
Note on line numbers: `File:Line` references correspond to the baseline snapshot prior to the v2 refactor. After refactoring, line numbers will differ.

---

## Executive Summary

PANDORA’s current build delivers a compelling dark-fantasy UI theme and a sizeable quest catalog, but it has several **critical security flaws** that allow trivial XP/progression manipulation and expose sensitive files (including the SQLite database) over HTTP. The backend also contains **logic bugs** that break expected account flows (notably: password change and logout).

From a learning-science and product standpoint, the platform’s biggest missed opportunity is the lack of a deterministic, server-trustworthy verification pipeline and a true roadmap/skill-tree unlock system. The current “anti-cheat” measures (paste blocking, client-side tests) are easily bypassed and create accessibility friction without materially improving integrity.

---

## 0–10 Scores (Baseline)

1) **Security & Anti-Cheat: 2/10**  
   Client-controlled XP awards + static file exposure make integrity and confidentiality fail in default configuration.

2) **Task System Architecture: 4/10**  
   Clear task schema and decent breadth, but significant non-deterministic/weak tests exist and there is no prerequisite unlocking enforcement.

3) **IDE Experience: 3/10**  
   Basic textarea editor, no line numbers/syntax highlighting, limited ergonomics; output is plain text without structured test visualization.

4) **Gamification Effectiveness: 6/10**  
   Ranks/achievements/events exist and are motivational, but XP balance and progression curve are inconsistent across tiers and easily exploitable.

5) **Review & Quality System: 4/10**  
   Manual review exists for Scratch, but tier-based review gating is incomplete; admin review math caps XP and lacks audit-grade submission integrity.

---

## Critical Issues (Security)

| Issue | File:Line | Severity | Exploit Scenario | Fix Direction |
|---|---:|---|---|---|
| **Project root served as static files** | `main.py:1941` | Critical | Student downloads `/academy.db`, logs, source, tasks; can read/alter data offline | Serve only explicit public assets; never mount `.` |
| **Client-controlled XP awarded by server** | `main.py:1473` + `index.html:2206` | Critical | Call `/api/progress/complete` with `xp_earned: 999999` or complete locked tasks | Server computes XP from task definitions + verification result |
| **Client-side verification is authoritative** | `index.html:1988`..`2238` | Critical | Bypass tests by calling `completeQuest()` or direct API call | Introduce server-trustworthy verification and/or mandatory review tiers |
| **Duplicate FastAPI app initialization** | `main.py:216` and `main.py:893` | High | Earlier middleware/handlers/startup hooks silently ignored; inconsistent behavior | Single app factory; remove dead app definition |
| **CORS misconfiguration (wildcard + credentials)** | `main.py:903`..`909` | High | Unnecessary cross-origin exposure; browser may reject; expands attack surface | Restrict origins (LAN + `null`), disable credentials by default |
| **Hardcoded weak default admin credential** | `main.py:1965` | High | Anyone on LAN can log in as admin if unchanged | Generate on first run or require env; force change flow |
| **Logout is ineffective (no session tracking)** | `main.py:1001`..`1009` | High | Stolen JWT remains valid until expiry | Add token revocation/session table enforcement or short-lived tokens + refresh |
| **Scratch `.sb3` upload lacks size/zip-bomb defenses** | `main.py:1495`..`1634` | High | Malicious upload consumes disk/CPU; potential DoS | Enforce max size, zip entry limits, timeouts; store outside web root |
| **Untrusted client IP from `X-Forwarded-For`** | `main.py:158`..`164` | Medium | Student spoofs IP to bypass rate limits/audit trails | Trust proxy headers only behind a configured reverse proxy |

---

## Bugs & Defects (Code-Level)

| Bug | File:Line | Impact | Fix Direction |
|---|---:|---|---|
| **Password change always fails** (`bcrypt` re-hash compare) | `main.py:1032`..`1056` | Users cannot change their password; admin can’t self-harden | Use `verify_password()`; then replace hash with `hash_password()` |
| **Session table unused** | `main.py:326` + `main.py:1001`..`1009` | Logout doesn’t revoke JWT; “sessions” is dead code | Either remove sessions or enforce them in auth |
| **Admin review XP is capped at 100** | `main.py:1379` | High-tier tasks can never award full XP | Use task XP (or policy cap by tier), not hard-coded 100 |
| **Admin XP adjustment doesn’t recompute level** | `main.py:1829`..`1834` | XP/level drift → inconsistent UI/leaderboards | Recompute level after XP change |
| **`allow_origins=["*"]` used despite `ALLOWED_ORIGINS`** | `main.py:51`..`57` + `main.py:903`..`909` | Intended config ignored | Use explicit origin list/regex |

---

## Task Validation Gaps (Determinism & Bypass)

| Gap | File:Line | Example | Why it Fails | Fix Direction |
|---|---:|---|---|---|
| **Non-deterministic or weak JS tests** | `tasks.json:2949`..`2965` | `js_48_math_random`: `roll() < 2` | Passes with incorrect implementations; doesn’t prove `Math.random()` usage | Stub `Math.random` deterministically in the test expression |
| **Time-based tasks not pinned** | `tasks.json:2930`..`2946` | `js_47_date_now` checks only type | Doesn’t validate `Date.now()` usage | Stub `Date.now` and assert value |
| **Frontend validation is string-contains** | `index.html:2060`..`2169` | `content_contain` checks | Easy to satisfy with comments/irrelevant placement | Parse/validate DOM/CSS properties deterministically |

---

## UX/UI Problems (with “Screenshot-style” Descriptions)

1) **Editor ergonomics** (`index.html:1593`..`1596`)  
   Screenshot description: Quest modal shows a plain multiline textarea without line numbers, syntax highlighting, indentation support, or “Run” keyboard shortcut hints.

2) **Test results readability** (`index.html:2001`..`2038`)  
   Screenshot description: Console area prints raw “PASS/FAIL” lines; no grouping per case, no diff/expected vs actual view, no summary badge.

3) **Mobile layout stress**  
   Screenshot description: On narrow screens the quest grid and side panels compete for space; modal editor + console stack becomes cramped with limited affordances.

4) **Anti-paste hurts accessibility** (`index.html:1945`..`1949`)  
   Screenshot description: Pasting is blocked with an alert, preventing assistive workflows (screen readers, dictation tools, IME corrections) while not preventing cheating.

---

## Missing Features vs Industry Leaders

- **Skill tree / roadmap** with prerequisites, recommended paths, and milestone “boss” nodes.
- **Attempt history** per task with diffs, timing, and structured feedback.
- **Deterministic grading harness** with seed control, pinned clocks, and stable snapshots.
- **Plagiarism/similarity detection** and fraud signals (suspiciously fast solves, identical fingerprints).
- **Accessibility hardening**: consistent ARIA patterns in complex widgets (modals, tabs), reduced-motion mode, and focus traps.
- **Admin analytics**: item difficulty/abandon rate, median attempts/time-to-solve, cohort progression.

---

## Refactor Goals (v2.0 Target)

- Make the backend the source of truth for XP, unlocks, and verification outcomes.
- Add deterministic, reproducible test harnessing; tier-based review gating (D/C auto; B/A/S manual).
- Implement plagiarism/similarity signals + an audit trail for all XP-affecting actions.
- Upgrade the student IDE UX (line numbers, better console, structured test visualization, responsive split panes).
- Enhance admin review workflow (queue, code view/diff, analytics dashboards).

