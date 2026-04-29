#!/usr/bin/env python3
# coding: utf-8
from __future__ import annotations

"""
Async Gemini 3.1 TTS generator for Prag-Forge / Micro-Forge exports.

What changed vs the first standalone version
--------------------------------------------
- Async requests via asyncio + aiohttp for higher throughput.
- Concurrent item processing with configurable --concurrency.
- Voice selection is diversified and context-aware instead of mostly static.
- If a chosen voice is rejected, the item falls back to the next voice candidate.
- Still uses ONLY Gemini 3.1 Flash TTS Preview.
- Still rotates across API keys/projects on 429 and temporary failures.

Important
---------
Gemini rate limits are applied per project, not per API key.
Rotation helps only if the keys below belong to DIFFERENT Google Cloud / AI Studio projects.
"""

import argparse
import asyncio
import base64
import csv
import hashlib
import json
import os
import re
import sys
import time
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import aiohttp

# ============================================================
# CONFIG
# ============================================================
MODEL_NAME = "gemini-3.1-flash-tts-preview"
API_BASE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

DEFAULT_TIMEOUT = 180
DEFAULT_COOLDOWN_SECONDS = 75
DEFAULT_AUDIO_RATE = 24000
DEFAULT_CHANNELS = 1
DEFAULT_SAMPLE_WIDTH = 2
DEFAULT_VOICE = "Kore"
DEFAULT_CONCURRENCY = 0
DEFAULT_PER_KEY_CONCURRENCY = 1

SAFE_NAME_RE = re.compile(r"[^a-zA-Z0-9._-]+")
VOICE_ERROR_RE = re.compile(r"voice|voiceName|prebuiltVoiceConfig", re.IGNORECASE)

# Put keys from DIFFERENT projects here.
API_KEY_POOL = [
    {
        "name": "account_1_project_1",
        "api_key": "AIzaSyAI-GO-DVivLa7SNjtlIG4UFUoboaR0Gys",
        "enabled": True,
    },
    {
        "name": "account_2_project_2",
        "api_key": "AIzaSyC7EIT8bQylE7FqH_lqsh3f8_tZrgc7iPg",
        "enabled": True,
    },
    {
        "name": "account_3_project_3",
        "api_key": "AIzaSyBK3KGNzGswscQ6zY9IbyhPPm9SsAHYLb4",
        "enabled": True,
    },
    {
        "name": "account_4_project_4",
        "api_key": "AIzaSyD3L2-216FNqUvq0JDVWqC3NFczEUyfiJ8",
        "enabled": True,
    },
    {
        "name": "account_5_project_5",
        "api_key": "AIzaSyCVyO4X6GL4-OVDoxDirgugpecLOpK2ICg",
        "enabled": True,
    },
    {
        "name": "account_6_project_6",
        "api_key": "AIzaSyBKv1RkVZ6CbHEDyZQBIurQbcwoxT6ZL7Y",
        "enabled": True,
    },
    {
        "name": "account_7_project_7",
        "api_key": "AIzaSyAYVMuC7xGMNhpwVv7z8PO_CLChzfez30A",
        "enabled": True,
    },
    {
        "name": "account_8_project_8",
        "api_key": "AIzaSyAI5-O2cmv74P-sIetaXSWeg-66KzAdx-8",
        "enabled": True,
    },
    {
        "name": "account_9_project_9",
        "api_key": "AIzaSyBjeClnDEVRHZTC_alLoETQ6pn8DEv7dgE",
        "enabled": True,
    },
    {
        "name": "account_10_project_10",
        "api_key": "AIzaSyDR0NwT3nwa2vP8x4hWmvxfMQswZoztZVo",
        "enabled": True,
    },
]


def eprint(*args: Any) -> None:
    print(*args, file=sys.stderr)


@dataclass
class KeyState:
    name: str
    api_key: str
    enabled: bool = True
    cooldown_until: float = 0.0
    consecutive_failures: int = 0
    total_requests: int = 0
    total_success: int = 0
    total_rate_limits: int = 0
    last_error: str = ""
    in_flight: int = 0

    def available(self, now: Optional[float] = None, per_key_concurrency: int = 1) -> bool:
        now = time.time() if now is None else now
        return (
            self.enabled
            and bool(self.api_key.strip())
            and now >= self.cooldown_until
            and self.in_flight < max(1, per_key_concurrency)
        )


class TemporaryGeminiError(RuntimeError):
    pass


class PermanentGeminiError(RuntimeError):
    pass


class VoiceRejectedError(RuntimeError):
    pass


class KeyPoolWaiting(RuntimeError):
    def __init__(self, wait_for: float, reason: str) -> None:
        super().__init__(reason)
        self.wait_for = max(0.05, float(wait_for))
        self.reason = reason


# ============================================================
# INPUT / NORMALIZATION
# ============================================================
def normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def load_json_or_jsonl(path: Path) -> List[Dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    stripped = text.strip()
    if not stripped:
        return []

    if path.suffix.lower() == ".jsonl":
        out: List[Dict[str, Any]] = []
        for line in stripped.splitlines():
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if isinstance(obj, dict):
                out.append(obj)
        return out

    obj = json.loads(stripped)
    if isinstance(obj, list):
        return [x for x in obj if isinstance(x, dict)]
    if isinstance(obj, dict):
        if isinstance(obj.get("items"), list):
            return [x for x in obj["items"] if isinstance(x, dict)]
        return [obj]
    raise ValueError(f"Unsupported JSON structure in {path}")


def load_csv_rows(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return [dict(row) for row in reader]


def canonical_item(raw: Dict[str, Any], index: int) -> Dict[str, Any]:
    use_items = raw.get("use")
    if not isinstance(use_items, list):
        use_items = []
        if raw.get("use_1"):
            use_items.append(raw.get("use_1"))
        if raw.get("use_2"):
            use_items.append(raw.get("use_2"))
    use_items = [normalize_text(x) for x in use_items if normalize_text(x)]

    azure_tts = raw.get("azure_tts")
    if not isinstance(azure_tts, dict):
        azure_tts = {
            "style_hint": normalize_text(raw.get("tts_style_hint")),
            "rate": normalize_text(raw.get("tts_rate")),
            "pitch": normalize_text(raw.get("tts_pitch")),
            "pause_ms": normalize_text(raw.get("tts_pause_ms")),
        }

    transcript = (
        normalize_text(raw.get("etalon"))
        or normalize_text(raw.get("model_response"))
        or normalize_text(raw.get("forge_model"))
    )
    if not transcript:
        raise ValueError(f"Item {index} has no transcript/model_response/etalon")

    expected_moves = raw.get("expected_moves") if isinstance(raw.get("expected_moves"), list) else []
    forbidden_moves = raw.get("forbidden_moves") if isinstance(raw.get("forbidden_moves"), list) else []

    return {
        "index": index,
        "mode": normalize_text(raw.get("mode") or "single_turn"),
        "speech_act": normalize_text(raw.get("speech_act")),
        "register": normalize_text(raw.get("register")),
        "channel": normalize_text(raw.get("channel")),
        "domain": normalize_text(raw.get("domain")),
        "power_relation": normalize_text(raw.get("power_relation")),
        "situation": normalize_text(raw.get("situation")),
        "question": normalize_text(raw.get("question")),
        "goal": normalize_text(raw.get("goal")),
        "style": normalize_text(raw.get("style")),
        "use": use_items[:2],
        "expected_moves": [normalize_text(x) for x in expected_moves if normalize_text(x)],
        "forbidden_moves": [normalize_text(x) for x in forbidden_moves if normalize_text(x)],
        "transcript": transcript,
        "azure_tts": azure_tts,
        "raw": raw,
    }


def load_items(path: Path) -> List[Dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix in {".json", ".jsonl"}:
        raw_items = load_json_or_jsonl(path)
    elif suffix == ".csv":
        raw_items = load_csv_rows(path)
    else:
        raise ValueError(f"Unsupported input format: {path.suffix}")

    items: List[Dict[str, Any]] = []
    for idx, raw in enumerate(raw_items, 1):
        try:
            items.append(canonical_item(raw, idx))
        except Exception as exc:
            eprint(f"[skip] item {idx}: {exc}")
    return items


# ============================================================
# KEY LOADING / ROTATION
# ============================================================
def load_key_pool() -> List[KeyState]:
    states: List[KeyState] = []

    for raw in API_KEY_POOL:
        if not isinstance(raw, dict):
            continue
        states.append(
            KeyState(
                name=str(raw.get("name", f"key_{len(states)+1}")),
                api_key=str(raw.get("api_key", "")).strip(),
                enabled=bool(raw.get("enabled", True)),
            )
        )

    env_single = normalize_text(os.getenv("GEMINI_API_KEY"))
    if env_single:
        states.insert(0, KeyState(name="env_GEMINI_API_KEY", api_key=env_single, enabled=True))

    env_multi = normalize_text(os.getenv("GEMINI_API_KEYS"))
    if env_multi:
        for idx, value in enumerate([x.strip() for x in env_multi.split(",") if x.strip()], 1):
            states.append(KeyState(name=f"env_GEMINI_API_KEYS_{idx}", api_key=value, enabled=True))

    deduped: List[KeyState] = []
    seen: set[str] = set()
    for state in states:
        if not state.api_key or state.api_key == "PUT_REAL_KEY_HERE" or state.api_key in seen:
            continue
        deduped.append(state)
        seen.add(state.api_key)

    if not deduped:
        raise RuntimeError(
            "No usable API keys found. Fill API_KEY_POOL or set GEMINI_API_KEY / GEMINI_API_KEYS."
        )

    return deduped


# ============================================================
# PROMPT BUILDING / VOICES
# ============================================================
def pace_instruction(rate: str) -> str:
    rate = normalize_text(rate)
    if rate.startswith("-"):
        return "slightly slower than neutral"
    if rate.startswith("+"):
        return "slightly faster than neutral"
    return "neutral pace"


def pitch_instruction(pitch: str) -> str:
    pitch = normalize_text(pitch)
    if pitch.startswith("-"):
        return "slightly lower pitch than neutral"
    if pitch.startswith("+"):
        return "slightly higher pitch than neutral"
    return "neutral pitch"


def transcript_audio_tag(item: Dict[str, Any]) -> str:
    hint = normalize_text(item.get("azure_tts", {}).get("style_hint", "")).lower()
    if hint == "serious":
        return "[serious]"
    if hint == "friendly":
        return "[friendly]"
    if hint == "empathetic":
        return "[empathetic]"
    return ""


def director_delivery_hint(item: Dict[str, Any]) -> str:
    hint = normalize_text(item.get("azure_tts", {}).get("style_hint", "")).lower()
    if hint == "friendly":
        return "Warm, natural, lightly encouraging delivery."
    if hint == "empathetic":
        return "Gentle, reassuring delivery with steady emotional control."
    if hint == "serious":
        return "Firm, controlled delivery with no melodrama."
    return "Clear, calm, natural delivery with strong intelligibility."


def voice_seed(item: Dict[str, Any]) -> int:
    raw = "|".join(
        [
            str(item.get("speech_act", "")),
            str(item.get("register", "")),
            str(item.get("channel", "")),
            str(item.get("domain", "")),
            str(item.get("style", "")),
            str(item.get("index", "")),
        ]
    )
    return int(hashlib.md5(raw.encode("utf-8")).hexdigest(), 16)


def ordered_unique(values: Sequence[str]) -> List[str]:
    seen: set[str] = set()
    out: List[str] = []
    for value in values:
        value = normalize_text(value)
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def rotate_candidates(values: Sequence[str], seed: int) -> List[str]:
    vals = list(values)
    if not vals:
        return [DEFAULT_VOICE]
    offset = seed % len(vals)
    return vals[offset:] + vals[:offset]


def choose_voice_candidates(item: Dict[str, Any], forced_voice: Optional[str]) -> List[str]:
    if forced_voice:
        return [forced_voice]

    hint = normalize_text(item.get("azure_tts", {}).get("style_hint", "")).lower()
    register = normalize_text(item.get("register", "")).lower()
    speech_act = normalize_text(item.get("speech_act", "")).lower()
    style = normalize_text(item.get("style", "")).lower()
    channel = normalize_text(item.get("channel", "")).lower()

    # Reliability-first: keep Kore and Puck in the pool because they are explicitly shown
    # in the current Google TTS docs. Add other known Gemini voice ids as secondary options;
    # if any project rejects them, the request automatically falls back to the next voice.
    base_pool = ["Kore", "Puck", "Iapetus", "Achird", "Sulafat"]

    if hint == "empathetic" or speech_act == "reassure_without_overpromising":
        preferred = ["Sulafat", "Puck", "Kore", "Iapetus"]
    elif hint == "friendly" or register == "informal":
        preferred = ["Puck", "Achird", "Kore", "Iapetus"]
    elif hint == "serious" or register in {"formal", "professional"}:
        preferred = ["Kore", "Iapetus", "Puck", "Sulafat"]
    elif speech_act in {"request_clarification", "clarify_misunderstanding"}:
        preferred = ["Iapetus", "Kore", "Puck", "Achird"]
    elif speech_act in {"set_boundary", "professional_pushback", "soft_refusal"}:
        preferred = ["Kore", "Iapetus", "Sulafat", "Puck"]
    elif speech_act in {"soften_criticism", "concede_then_pivot", "polite_disagreement"}:
        preferred = ["Puck", "Kore", "Iapetus", "Achird"]
    else:
        preferred = ["Kore", "Puck", "Iapetus", "Achird", "Sulafat"]

    # Small tone nudges.
    if "warm" in style or "kind" in style:
        preferred = ["Puck", "Sulafat"] + preferred
    if "firm" in style or "direct" in style:
        preferred = ["Kore", "Iapetus"] + preferred
    if channel == "phone":
        preferred = ["Kore", "Puck"] + preferred

    candidates = ordered_unique(preferred + base_pool)
    return rotate_candidates(candidates, voice_seed(item))


def build_tts_prompt(item: Dict[str, Any]) -> str:
    use_anchors = item.get("use") or []
    use_text = ", ".join(use_anchors) if use_anchors else "none"
    expected_moves = ", ".join(item.get("expected_moves") or []) or "none"
    forbidden_moves = ", ".join(item.get("forbidden_moves") or []) or "none"

    tts_meta = item.get("azure_tts", {})
    tag = transcript_audio_tag(item)
    transcript = item["transcript"]
    if tag:
        transcript = f"{tag} {transcript}"

    lines = [
        "# AUDIO PROFILE: Prag-Forge reference voice",
        "A clear native-like English reference voice for a learner reviewing one best-fit response.",
        "",
        "## THE SCENE",
        "This audio belongs to an English learning card in a pragmatics-focused system.",
        "The learner hears the canonical answer after attempting their own response.",
        "",
        "### DIRECTOR'S NOTES",
        "- Synthesize speech for the transcript only.",
        "- Speak ONLY the transcript verbatim.",
        "- Do not read headings, metadata, bullet points, or notes.",
        "- Prioritize intelligibility, naturalness, and pragmatic fit.",
        f"- Delivery target: {director_delivery_hint(item)}",
        f"- Pace target: {pace_instruction(tts_meta.get('rate', '0%'))}.",
        f"- Pitch target: {pitch_instruction(tts_meta.get('pitch', '0%'))}.",
    ]

    optional_lines = [
        ("Register", item.get("register")),
        ("Speech act", item.get("speech_act")),
        ("Channel", item.get("channel")),
        ("Domain", item.get("domain")),
        ("Power relation", item.get("power_relation")),
        ("Goal", item.get("goal")),
        ("Style", item.get("style")),
        ("Question", item.get("question")),
        ("Situation", item.get("situation")),
    ]
    for label, value in optional_lines:
        value = normalize_text(value)
        if value:
            lines.append(f"- {label}: {value}")

    lines.extend(
        [
            f"- Required lexical anchors that should sound clean and noticeable but not over-emphasized: {use_text}.",
            f"- Expected pragmatic moves: {expected_moves}.",
            f"- Forbidden moves to avoid in tone: {forbidden_moves}.",
            "",
            "### SAMPLE CONTEXT",
            "The answer should sound like the best possible one-turn reply for this exact scenario,",
            "not like a generic narrator or a random sentence readout.",
            "",
            "#### TRANSCRIPT",
            transcript,
        ]
    )
    return "\n".join(lines)


def build_payload(prompt: str, voice_name: str) -> Dict[str, Any]:
    return {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt,
                    }
                ]
            }
        ],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {
                    "prebuiltVoiceConfig": {
                        "voiceName": voice_name,
                    }
                }
            },
        },
    }


# ============================================================
# FILE OUTPUT
# ============================================================
def sanitize_filename(name: str) -> str:
    name = SAFE_NAME_RE.sub("_", name).strip("._-")
    return name[:120] or "item"


def item_basename(item: Dict[str, Any]) -> str:
    stem_parts = [
        f"{int(item['index']):05d}",
        sanitize_filename(item.get("speech_act", "item")),
        sanitize_filename((item.get("transcript", "")[:42]).lower()),
    ]
    return "__".join([x for x in stem_parts if x])


def write_wav(path: Path, pcm_bytes: bytes) -> None:
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(DEFAULT_CHANNELS)
        wf.setsampwidth(DEFAULT_SAMPLE_WIDTH)
        wf.setframerate(DEFAULT_AUDIO_RATE)
        wf.writeframes(pcm_bytes)


def write_manifest_line(path: Path, payload: Dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def parse_error_message(status: int, body_text: str) -> str:
    try:
        payload = json.loads(body_text)
    except Exception:
        return body_text[:1000]
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            parts = [
                str(error.get("status", "")).strip(),
                str(error.get("message", "")).strip(),
            ]
            return " | ".join([x for x in parts if x]) or json.dumps(payload, ensure_ascii=False)
    return json.dumps(payload, ensure_ascii=False)


def parse_retry_after_seconds(response_headers: Dict[str, str], body_text: str) -> Optional[float]:
    candidates = [
        response_headers.get("Retry-After"),
        response_headers.get("retry-after"),
        response_headers.get("Retry-after"),
    ]
    for raw in candidates:
        value = normalize_text(raw)
        if not value:
            continue
        value = value.rstrip("sS")
        try:
            parsed = float(value)
        except ValueError:
            parsed = None
        if parsed is not None and parsed > 0:
            return parsed

    body_patterns = [
        r"Please retry in\s*([0-9]+(?:\.[0-9]+)?)s",
        r"retry in\s*([0-9]+(?:\.[0-9]+)?)s",
        r"Retry-After[:=]\s*([0-9]+(?:\.[0-9]+)?)",
    ]
    for pattern in body_patterns:
        m = re.search(pattern, body_text, re.IGNORECASE)
        if m:
            try:
                parsed = float(m.group(1))
            except ValueError:
                parsed = None
            if parsed is not None and parsed > 0:
                return parsed
    return None


# ============================================================
# GEMINI CLIENT
# ============================================================
class GeminiTTSClient:
    def __init__(
        self,
        keys: Sequence[KeyState],
        timeout: int = DEFAULT_TIMEOUT,
        cooldown_seconds: int = DEFAULT_COOLDOWN_SECONDS,
        per_key_concurrency: int = DEFAULT_PER_KEY_CONCURRENCY,
    ) -> None:
        self.keys: List[KeyState] = list(keys)
        self.timeout = timeout
        self.cooldown_seconds = cooldown_seconds
        self.per_key_concurrency = max(1, per_key_concurrency)
        self.cursor = 0
        self.session: Optional[aiohttp.ClientSession] = None
        self.key_lock = asyncio.Lock()
        self.key_event = asyncio.Event()
        self.key_event.set()
        self._last_wait_log_at = 0.0
        self._last_wait_reason = ""

    async def __aenter__(self) -> "GeminiTTSClient":
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        self.session = aiohttp.ClientSession(timeout=timeout)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self.session is not None:
            await self.session.close()
            self.session = None

    async def acquire_key(self) -> KeyState:
        async with self.key_lock:
            if not self.keys:
                raise RuntimeError("No API keys configured")

            now = time.time()
            for offset in range(len(self.keys)):
                idx = (self.cursor + offset) % len(self.keys)
                key = self.keys[idx]
                if key.available(now, self.per_key_concurrency):
                    key.in_flight += 1
                    self.cursor = (idx + 1) % len(self.keys)
                    return key

            enabled = [k for k in self.keys if k.enabled]
            if not enabled:
                raise RuntimeError("All API keys became disabled")

            cooled = [k for k in enabled if now >= k.cooldown_until]
            saturated = [k for k in cooled if k.in_flight >= self.per_key_concurrency]
            cooling = [k for k in enabled if now < k.cooldown_until]

            if saturated and not cooling:
                raise KeyPoolWaiting(0.10, "all available keys are busy")

            waits = []
            if cooling:
                waits.append(min(max(0.05, k.cooldown_until - now) for k in cooling))
            if saturated:
                waits.append(0.10)
            wait_for = min(waits) if waits else 0.10
            reason = "all keys cooling down" if cooling else "waiting for a free key slot"
            raise KeyPoolWaiting(wait_for, reason)

    async def release_key(self, key: KeyState) -> None:
        async with self.key_lock:
            key.in_flight = max(0, key.in_flight - 1)
            self.key_event.set()

    def backoff_key(self, key: KeyState, retry_after: Optional[float], reason: str) -> None:
        key.total_rate_limits += 1
        key.consecutive_failures += 1
        if retry_after and retry_after > 0:
            penalty = min(300.0, float(retry_after) + 1.0)
        else:
            base = float(self.cooldown_seconds)
            penalty = min(300.0, base * max(1, min(key.consecutive_failures, 4)))
        key.cooldown_until = time.time() + penalty
        key.last_error = reason
        self.key_event.set()

    def disable_key(self, key: KeyState, reason: str) -> None:
        key.enabled = False
        key.last_error = reason
        self.key_event.set()

    async def _post(self, url: str, headers: Dict[str, str], payload: Dict[str, Any]) -> Tuple[int, str, Dict[str, str]]:
        if self.session is None:
            raise RuntimeError("GeminiTTSClient session is not open")
        async with self.session.post(url, headers=headers, json=payload) as response:
            text = await response.text()
            return response.status, text, dict(response.headers)

    async def _wait_for_pool(self, exc: KeyPoolWaiting) -> None:
        now = time.time()
        if exc.reason != self._last_wait_reason or (now - self._last_wait_log_at) >= 2.0:
            eprint(f"[wait] {exc.reason}, sleeping {exc.wait_for:.1f}s")
            self._last_wait_log_at = now
            self._last_wait_reason = exc.reason

        # Important: do not set the event in a finally block here.
        # Waiters were waking each other up immediately, which caused
        # repeated wait spam and made cooldown appear stuck.
        self.key_event.clear()
        try:
            await asyncio.wait_for(self.key_event.wait(), timeout=exc.wait_for)
        except asyncio.TimeoutError:
            pass

    async def request_audio(self, item: Dict[str, Any], forced_voice: Optional[str] = None) -> Tuple[bytes, Dict[str, Any], str]:
        prompt = build_tts_prompt(item)
        voice_candidates = choose_voice_candidates(item, forced_voice)
        url = API_BASE.format(model=MODEL_NAME)

        for voice_name in voice_candidates:
            payload = build_payload(prompt, voice_name)

            while True:
                try:
                    key = await self.acquire_key()
                except KeyPoolWaiting as exc:
                    await self._wait_for_pool(exc)
                    continue

                headers = {
                    "x-goog-api-key": key.api_key,
                    "Content-Type": "application/json",
                }
                key.total_requests += 1

                try:
                    try:
                        status, body_text, response_headers = await self._post(url, headers, payload)
                    except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                        reason = f"network_error: {exc}"
                        self.backoff_key(key, retry_after=None, reason=reason)
                        eprint(f"[retry] {key.name} -> {reason}")
                        continue

                    if status == 200:
                        key.total_success += 1
                        key.consecutive_failures = 0
                        key.cooldown_until = 0.0
                        try:
                            body = json.loads(body_text)
                            b64 = body["candidates"][0]["content"]["parts"][0]["inlineData"]["data"]
                            pcm = base64.b64decode(b64)
                        except Exception as exc:
                            raise TemporaryGeminiError(f"Malformed success payload: {exc}") from exc
                        meta = {
                            "key_name": key.name,
                            "model": MODEL_NAME,
                            "voice_name": voice_name,
                            "http_status": status,
                        }
                        return pcm, meta, prompt

                    reason = parse_error_message(status, body_text)
                    retry_after = parse_retry_after_seconds(response_headers, body_text)

                    if status == 429:
                        self.backoff_key(key, retry_after=retry_after, reason=f"429 rate_limit: {reason}")
                        eprint(f"[rotate] {key.name} hit rate limit on {MODEL_NAME} using {voice_name}: {reason}")
                        continue

                    if status in {500, 502, 503, 504}:
                        self.backoff_key(key, retry_after=retry_after, reason=f"server_error_{status}: {reason}")
                        eprint(f"[retry] {key.name} temporary server error on {MODEL_NAME} using {voice_name}: {reason}")
                        continue

                    if status in {401, 403}:
                        self.disable_key(key, reason=f"auth_error_{status}: {reason}")
                        eprint(f"[disable] {key.name}: auth_error_{status}: {reason}")
                        if not any(k.enabled for k in self.keys):
                            raise RuntimeError("All API keys became disabled")
                        continue

                    if status == 404:
                        raise PermanentGeminiError(
                            f"Model {MODEL_NAME} not found or not enabled for this project: {reason}"
                        )

                    if status == 400 and VOICE_ERROR_RE.search(reason):
                        eprint(f"[voice-fallback] voice {voice_name} rejected for item {item.get('index')}: {reason}")
                        break

                    raise PermanentGeminiError(
                        f"Non-retryable Gemini error {status} on {MODEL_NAME} using {voice_name}: {reason}"
                    )
                finally:
                    await self.release_key(key)

        raise VoiceRejectedError(
            f"All voice candidates failed for item {item.get('index')} on {MODEL_NAME}"
        )


# ============================================================
# MAIN PROCESSING
# ============================================================
class Progress:
    def __init__(self, total: int) -> None:
        self.total = total
        self.done = 0
        self.skipped = 0
        self.failed = 0
        self.lock = asyncio.Lock()

    async def log(self, message: str) -> None:
        async with self.lock:
            print(message)

    async def mark_skip(self, filename: str) -> None:
        async with self.lock:
            self.done += 1
            self.skipped += 1
            print(f"[{self.done}/{self.total}] skip existing {filename}")

    async def mark_success(self, filename: str, voice_name: str, key_name: str) -> None:
        async with self.lock:
            self.done += 1
            print(f"[{self.done}/{self.total}] ok {filename} | voice={voice_name} | key={key_name}")

    async def mark_failure(self, item_index: int, exc: Exception) -> None:
        async with self.lock:
            self.done += 1
            self.failed += 1
            print(f"[{self.done}/{self.total}] fail item={item_index}: {exc}")


async def process_one_item(
    item: Dict[str, Any],
    client: GeminiTTSClient,
    out_dir: Path,
    forced_voice: Optional[str],
    force: bool,
    manifest_path: Path,
    manifest_lock: asyncio.Lock,
    progress: Progress,
    semaphore: asyncio.Semaphore,
) -> None:
    basename = item_basename(item)
    wav_path = out_dir / f"{basename}.wav"
    prompt_path = out_dir / f"{basename}.prompt.txt"

    if wav_path.exists() and not force:
        await progress.mark_skip(wav_path.name)
        return

    try:
        async with semaphore:
            pcm_bytes, meta, prompt_text = await client.request_audio(item, forced_voice=forced_voice)

        await asyncio.to_thread(prompt_path.write_text, prompt_text, "utf-8")
        await asyncio.to_thread(write_wav, wav_path, pcm_bytes)

        manifest_payload = {
            "index": item["index"],
            "file": str(wav_path.name),
            "prompt_file": str(prompt_path.name),
            "speech_act": item.get("speech_act"),
            "register": item.get("register"),
            "channel": item.get("channel"),
            "domain": item.get("domain"),
            "power_relation": item.get("power_relation"),
            "style": item.get("style"),
            "use": item.get("use"),
            "transcript": item.get("transcript"),
            "google_tts": meta,
        }
        async with manifest_lock:
            await asyncio.to_thread(write_manifest_line, manifest_path, manifest_payload)
        await progress.mark_success(wav_path.name, meta["voice_name"], meta["key_name"])
    except Exception as exc:
        await progress.mark_failure(int(item.get("index", 0)), exc)


async def process_items_async(
    items: Sequence[Dict[str, Any]],
    client: GeminiTTSClient,
    out_dir: Path,
    forced_voice: Optional[str],
    force: bool,
    start_index: int,
    limit: Optional[int],
    concurrency: int,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "tts_manifest.jsonl"
    manifest_lock = asyncio.Lock()

    selected = [x for x in items if int(x["index"]) >= start_index]
    if limit is not None:
        selected = selected[:limit]

    total = len(selected)
    if total == 0:
        print("No items selected.")
        return

    progress = Progress(total=total)
    semaphore = asyncio.Semaphore(max(1, concurrency))

    tasks = [
        asyncio.create_task(
            process_one_item(
                item=item,
                client=client,
                out_dir=out_dir,
                forced_voice=forced_voice,
                force=force,
                manifest_path=manifest_path,
                manifest_lock=manifest_lock,
                progress=progress,
                semaphore=semaphore,
            )
        )
        for item in selected
    ]

    await asyncio.gather(*tasks)

    print(
        f"Finished: total={progress.total}, failed={progress.failed}, skipped={progress.skipped}, "
        f"written={progress.total - progress.failed - progress.skipped}"
    )


def dump_stats(keys: Sequence[KeyState]) -> None:
    print("\nKey stats:")
    for key in keys:
        state = "enabled" if key.enabled else "disabled"
        cool = max(0.0, key.cooldown_until - time.time())
        print(
            f"- {key.name}: {state}, requests={key.total_requests}, success={key.total_success}, "
            f"rate_limits={key.total_rate_limits}, cooldown={cool:.1f}s, last_error={key.last_error}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate async Gemini 3.1 TTS audio for Prag-Forge items")
    parser.add_argument("--input", required=True, help="Path to Prag-Forge JSON / JSONL / CSV")
    parser.add_argument(
        "--out-dir",
        default="./prag_forge_google_tts_out",
        help="Directory for WAV files, prompts, and manifest",
    )
    parser.add_argument("--voice", default="", help="Force a specific Gemini voice name")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument("--cooldown-seconds", type=int, default=DEFAULT_COOLDOWN_SECONDS)
    parser.add_argument("--start-index", type=int, default=1)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY, help="Concurrent synth requests. 0 = auto (all keys).")
    parser.add_argument("--per-key-concurrency", type=int, default=DEFAULT_PER_KEY_CONCURRENCY, help="Max parallel requests per key/project")
    parser.add_argument("--force", action="store_true", help="Regenerate even if WAV already exists")
    return parser.parse_args()


async def main_async() -> None:
    args = parse_args()
    input_path = Path(args.input)
    out_dir = Path(args.out_dir)

    keys = load_key_pool()
    items = load_items(input_path)
    if not items:
        raise RuntimeError(f"No valid items loaded from {input_path}")

    enabled_keys = sum(1 for k in keys if k.enabled)
    per_key_concurrency = max(1, int(args.per_key_concurrency))
    effective_concurrency = int(args.concurrency)
    if effective_concurrency <= 0:
        effective_concurrency = max(1, enabled_keys * per_key_concurrency)

    async with GeminiTTSClient(
        keys=keys,
        timeout=args.timeout,
        cooldown_seconds=args.cooldown_seconds,
        per_key_concurrency=per_key_concurrency,
    ) as client:
        try:
            await process_items_async(
                items=items,
                client=client,
                out_dir=out_dir,
                forced_voice=args.voice.strip() or None,
                force=bool(args.force),
                start_index=max(1, int(args.start_index)),
                limit=args.limit,
                concurrency=max(1, effective_concurrency),
            )
        finally:
            dump_stats(keys)


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
