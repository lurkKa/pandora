#!/usr/bin/env python3
# coding: utf-8
"""
Generate Russian voice alerts for PANDORA Behavior Agent escalation system
using Gemini 3.1 Flash TTS (same API/key pool as prag_forge).

Outputs:
  scripts/audio/пробуждение/01.wav … 03.wav   — gentle reminders
  scripts/audio/предупреждение/01.wav … 03.wav — firm warnings
  scripts/audio/напоминание/01.wav … 03.wav    — final stern alerts

Dependencies: pip install aiohttp
"""

from __future__ import annotations

import asyncio
import base64
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
# CONFIG (mirrored from prag_forge)
# ============================================================
MODEL_NAME = "gemini-3.1-flash-tts-preview"
API_BASE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
AUDIO_RATE = 24000
CHANNELS = 1
SAMPLE_WIDTH = 2
TIMEOUT = 120

VOICE_ERROR_RE = re.compile(r"voice|voiceName|prebuiltVoiceConfig", re.IGNORECASE)

# Same key pool as prag_forge
API_KEY_POOL = [
    {"api_key": "AIzaSyAI-GO-DVivLa7SNjtlIG4UFUoboaR0Gys"},
    {"api_key": "AIzaSyC7EIT8bQylE7FqH_lqsh3f8_tZrgc7iPg"},
    {"api_key": "AIzaSyBK3KGNzGswscQ6zY9IbyhPPm9SsAHYLb4"},
    {"api_key": "AIzaSyD3L2-216FNqUvq0JDVWqC3NFczEUyfiJ8"},
    {"api_key": "AIzaSyCVyO4X6GL4-OVDoxDirgugpecLOpK2ICg"},
    {"api_key": "AIzaSyBKv1RkVZ6CbHEDyZQBIurQbcwoxT6ZL7Y"},
    {"api_key": "AIzaSyAYVMuC7xGMNhpwVv7z8PO_CLChzfez30A"},
    {"api_key": "AIzaSyAI5-O2cmv74P-sIetaXSWeg-66KzAdx-8"},
    {"api_key": "AIzaSyBjeClnDEVRHZTC_alLoETQ6pn8DEv7dgE"},
    {"api_key": "AIzaSyDR0NwT3nwa2vP8x4hWmvxfMQswZoztZVo"},
]

SCRIPT_DIR = Path(__file__).resolve().parent
AUDIO_DIR = SCRIPT_DIR / "audio"

# ============================================================
# ALERT DEFINITIONS
# ============================================================
# Each level has 3 variations with:
#   - transcript: what the voice says (Russian)
#   - voice: Gemini voice name (Kore=firm, Puck=warm)
#   - prompt: full director prompt for tone/delivery

ALERTS = {
    "пробуждение": [
        {
            "file": "01.wav",
            "voice": "Puck",
            "transcript": "Внимание. Уровень шума повышен. Пожалуйста, соблюдайте тишину.",
            "tone": "gentle, calm, like a kind teacher giving a soft nudge",
        },
        {
            "file": "02.wav",
            "voice": "Sulafat",
            "transcript": "Тише, пожалуйста. Давайте сосредоточимся на работе.",
            "tone": "warm, encouraging, supportive teacher voice",
        },
        {
            "file": "03.wav",
            "voice": "Puck",
            "transcript": "Небольшое напоминание: давайте работать тише. Спасибо.",
            "tone": "friendly, non-threatening, a gentle reminder",
        },
    ],
    "предупреждение": [
        {
            "file": "01.wav",
            "voice": "Kore",
            "transcript": "Это второе предупреждение. Шум продолжается. Прошу немедленно прекратить.",
            "tone": "firm, serious, authoritative but still respectful",
        },
        {
            "file": "02.wav",
            "voice": "Iapetus",
            "transcript": "Повторное нарушение тишины. Следующее нарушение будет зафиксировано в системе.",
            "tone": "strict, clear warning, no warmth, business-like",
        },
        {
            "file": "03.wav",
            "voice": "Kore",
            "transcript": "Предупреждение. Уровень шума недопустим. Это ваш последний шанс исправиться.",
            "tone": "stern, controlled authority, like a principal giving a formal warning",
        },
    ],
    "напоминание": [
        {
            "file": "01.wav",
            "voice": "Kore",
            "transcript": "Финальное предупреждение. Нарушение зафиксировано и отправлено в систему. Будут применены штрафные баллы.",
            "tone": "very firm, final, no warmth at all, cold authority — the matter is now escalated",
        },
        {
            "file": "02.wav",
            "voice": "Iapetus",
            "transcript": "Третье нарушение подряд. Инцидент зарегистрирован. Ожидайте снижение баллов за поведение.",
            "tone": "cold, official, factual announcement — consequences are now in effect",
        },
        {
            "file": "03.wav",
            "voice": "Kore",
            "transcript": "Нарушение записано. Отчёт отправлен преподавателю. Штрафные баллы будут начислены автоматически.",
            "tone": "absolute authority, calm but unmistakably final, like a system announcement",
        },
    ],
}


def build_prompt(transcript: str, tone: str) -> str:
    """Build a Gemini TTS prompt optimized for Russian classroom alerts."""
    return f"""# AUDIO PROFILE: PANDORA Classroom Alert Voice

A clear, authoritative Russian voice for a classroom behavior monitoring system.
The voice must sound natural, human-like, and appropriate for a school environment.

## THE SCENE
This is an automated alert played through classroom speakers when students are too loud.
The alert must command attention without being scary or robotic.

### DIRECTOR'S NOTES
- Speak ONLY the transcript below, nothing else.
- Language: Russian. Pronunciation must be native-quality, clear, and crisp.
- Delivery target: {tone}
- Pace: measured, slightly slower than normal conversational speed for maximum clarity.
- Pitch: steady, controlled. No dramatic inflections.
- Articulation: every word must be crystal clear — this plays on classroom speakers.
- Do NOT sound robotic or synthetic. Sound like a real person making an announcement.
- Do NOT add any sounds, music, or effects. Voice only.
- Brief natural pause (200-300ms) after the first sentence for emphasis.

#### TRANSCRIPT
{transcript}"""


def build_payload(prompt: str, voice_name: str) -> Dict[str, Any]:
    return {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {
                    "prebuiltVoiceConfig": {"voiceName": voice_name}
                }
            },
        },
    }


def write_wav(path: Path, pcm_bytes: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(SAMPLE_WIDTH)
        wf.setframerate(AUDIO_RATE)
        wf.writeframes(pcm_bytes)


async def generate_one(
    session: aiohttp.ClientSession,
    level_name: str,
    alert: Dict[str, str],
    key_index: int,
) -> bool:
    """Generate a single alert WAV. Returns True on success."""
    out_path = AUDIO_DIR / level_name / alert["file"]

    prompt = build_prompt(alert["transcript"], alert["tone"])
    payload = build_payload(prompt, alert["voice"])
    url = API_BASE.format(model=MODEL_NAME)

    # Try keys starting from key_index, rotating on failure
    for attempt in range(len(API_KEY_POOL)):
        ki = (key_index + attempt) % len(API_KEY_POOL)
        api_key = API_KEY_POOL[ki]["api_key"]
        headers = {
            "x-goog-api-key": api_key,
            "Content-Type": "application/json",
        }

        try:
            timeout = aiohttp.ClientTimeout(total=TIMEOUT)
            async with session.post(url, headers=headers, json=payload, timeout=timeout) as resp:
                body_text = await resp.text()

                if resp.status == 200:
                    body = json.loads(body_text)
                    b64 = body["candidates"][0]["content"]["parts"][0]["inlineData"]["data"]
                    pcm = base64.b64decode(b64)
                    write_wav(out_path, pcm)
                    dur = len(pcm) / (AUDIO_RATE * SAMPLE_WIDTH * CHANNELS)
                    print(f"  ✅ {level_name}/{alert['file']}  ({dur:.1f}s, voice={alert['voice']}, key={ki+1})")
                    return True

                if resp.status == 429:
                    print(f"  ⏳ Rate limited on key {ki+1}, trying next...")
                    await asyncio.sleep(2)
                    continue

                if resp.status == 400 and VOICE_ERROR_RE.search(body_text):
                    # Try fallback voice
                    fallback = "Puck" if alert["voice"] != "Puck" else "Kore"
                    print(f"  ⚠️ Voice {alert['voice']} rejected, trying {fallback}...")
                    payload = build_payload(prompt, fallback)
                    continue

                print(f"  ❌ Error {resp.status}: {body_text[:200]}")
                continue

        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            print(f"  ⚠️ Network error on key {ki+1}: {e}, retrying...")
            await asyncio.sleep(1)
            continue

    print(f"  ❌ FAILED: {level_name}/{alert['file']} — all keys exhausted")
    return False


async def main():
    total = sum(len(alerts) for alerts in ALERTS.values())
    print(f"🎙️ Generating {total} Russian voice alerts via Gemini TTS...")
    print(f"   Output: {AUDIO_DIR}/")
    print()

    async with aiohttp.ClientSession() as session:
        key_idx = 0
        ok = 0
        fail = 0

        for level_name, alerts in ALERTS.items():
            print(f"📂 {level_name}/")
            for alert in alerts:
                success = await generate_one(session, level_name, alert, key_idx)
                if success:
                    ok += 1
                else:
                    fail += 1
                key_idx = (key_idx + 1) % len(API_KEY_POOL)
                # Small delay between requests to be polite
                await asyncio.sleep(1)
            print()

    print(f"Готово: {ok} успешно, {fail} ошибок из {total}")


if __name__ == "__main__":
    asyncio.run(main())
