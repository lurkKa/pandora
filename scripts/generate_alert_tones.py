#!/usr/bin/env python3
"""
Generate alert tone WAV files for PANDORA behavior agent escalation levels.

Creates 3 variations per level:
  audio/пробуждение/  — soft, melodic 2-note chimes
  audio/предупреждение/ — firmer 3-note warnings
  audio/напоминание/  — urgent 4-note ascending alarms

Dependencies: numpy, scipy (already required by behavior_agent)
"""

import os
import numpy as np
from scipy.io import wavfile

SAMPLE_RATE = 44100
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
AUDIO_DIR = os.path.join(SCRIPT_DIR, "audio")

# ── Tone helpers ──────────────────────────────────────────────

def sine_tone(freq: float, duration: float, volume: float = 0.5) -> np.ndarray:
    """Pure sine tone."""
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False)
    return (volume * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def fade(audio: np.ndarray, fade_ms: int = 30) -> np.ndarray:
    """Apply fade-in/fade-out to avoid clicks."""
    n = int(SAMPLE_RATE * fade_ms / 1000)
    if n > len(audio) // 2:
        n = len(audio) // 2
    audio = audio.copy()
    audio[:n] *= np.linspace(0, 1, n).astype(np.float32)
    audio[-n:] *= np.linspace(1, 0, n).astype(np.float32)
    return audio


def silence(duration: float) -> np.ndarray:
    return np.zeros(int(SAMPLE_RATE * duration), dtype=np.float32)


def concat(*parts) -> np.ndarray:
    return np.concatenate(parts)


# ── Level 1: Пробуждение (gentle chime) ──────────────────────

def gen_awakening_1() -> np.ndarray:
    """Two soft ascending notes — C5 + E5."""
    return concat(
        fade(sine_tone(523, 0.25, 0.25)),  # C5
        silence(0.05),
        fade(sine_tone(659, 0.35, 0.30)),  # E5
        silence(0.3),
    )

def gen_awakening_2() -> np.ndarray:
    """Two soft notes — D5 + F#5."""
    return concat(
        fade(sine_tone(587, 0.25, 0.25)),  # D5
        silence(0.05),
        fade(sine_tone(740, 0.35, 0.30)),  # F#5
        silence(0.3),
    )

def gen_awakening_3() -> np.ndarray:
    """Two soft notes — E5 + G5."""
    return concat(
        fade(sine_tone(659, 0.25, 0.22)),  # E5
        silence(0.05),
        fade(sine_tone(784, 0.35, 0.28)),  # G5
        silence(0.3),
    )


# ── Level 2: Предупреждение (firm 3-note warning) ────────────

def gen_warning_1() -> np.ndarray:
    """Three firmer notes — G4, B4, D5."""
    return concat(
        fade(sine_tone(392, 0.20, 0.45)),  # G4
        silence(0.04),
        fade(sine_tone(494, 0.20, 0.50)),  # B4
        silence(0.04),
        fade(sine_tone(587, 0.30, 0.55)),  # D5
        silence(0.3),
    )

def gen_warning_2() -> np.ndarray:
    """Three notes — A4, C#5, E5."""
    return concat(
        fade(sine_tone(440, 0.20, 0.45)),  # A4
        silence(0.04),
        fade(sine_tone(554, 0.20, 0.50)),  # C#5
        silence(0.04),
        fade(sine_tone(659, 0.30, 0.55)),  # E5
        silence(0.3),
    )

def gen_warning_3() -> np.ndarray:
    """Three descending notes — E5, C5, A4 (more stern)."""
    return concat(
        fade(sine_tone(659, 0.18, 0.50)),  # E5
        silence(0.03),
        fade(sine_tone(523, 0.18, 0.50)),  # C5
        silence(0.03),
        fade(sine_tone(440, 0.30, 0.55)),  # A4
        silence(0.3),
    )


# ── Level 3: Напоминание (urgent 4-note alarm) ───────────────

def gen_reminder_1() -> np.ndarray:
    """Four urgent ascending notes with crescendo."""
    return concat(
        fade(sine_tone(440, 0.15, 0.50)),  # A4
        silence(0.03),
        fade(sine_tone(554, 0.15, 0.55)),  # C#5
        silence(0.03),
        fade(sine_tone(659, 0.15, 0.60)),  # E5
        silence(0.03),
        fade(sine_tone(880, 0.25, 0.70)),  # A5
        silence(0.2),
        # Repeat pattern for urgency
        fade(sine_tone(440, 0.12, 0.55)),
        silence(0.03),
        fade(sine_tone(554, 0.12, 0.60)),
        silence(0.03),
        fade(sine_tone(659, 0.12, 0.65)),
        silence(0.03),
        fade(sine_tone(880, 0.25, 0.75)),
        silence(0.3),
    )

def gen_reminder_2() -> np.ndarray:
    """Alternating alarm pattern."""
    parts = []
    for i in range(3):
        vol = 0.55 + i * 0.08
        parts.extend([
            fade(sine_tone(784, 0.12, vol)),    # G5
            silence(0.05),
            fade(sine_tone(988, 0.12, vol)),    # B5
            silence(0.08),
        ])
    parts.append(silence(0.3))
    return concat(*parts)

def gen_reminder_3() -> np.ndarray:
    """Descending-ascending urgency pattern."""
    return concat(
        fade(sine_tone(880, 0.15, 0.55)),  # A5
        silence(0.03),
        fade(sine_tone(659, 0.15, 0.55)),  # E5
        silence(0.03),
        fade(sine_tone(880, 0.15, 0.60)),  # A5
        silence(0.03),
        fade(sine_tone(659, 0.15, 0.60)),  # E5
        silence(0.1),
        fade(sine_tone(988, 0.25, 0.70)),  # B5 — high finish
        silence(0.3),
    )


# ── Generate and save ────────────────────────────────────────

LEVELS = {
    "пробуждение": [gen_awakening_1, gen_awakening_2, gen_awakening_3],
    "предупреждение": [gen_warning_1, gen_warning_2, gen_warning_3],
    "напоминание": [gen_reminder_1, gen_reminder_2, gen_reminder_3],
}


def main():
    for level_name, generators in LEVELS.items():
        level_dir = os.path.join(AUDIO_DIR, level_name)
        os.makedirs(level_dir, exist_ok=True)
        for i, gen_fn in enumerate(generators, start=1):
            audio = gen_fn()
            # Normalize to prevent clipping
            peak = np.max(np.abs(audio))
            if peak > 0.95:
                audio = audio * (0.95 / peak)
            filepath = os.path.join(level_dir, f"{i:02d}.wav")
            # Convert to int16 for WAV
            audio_int16 = (audio * 32767).astype(np.int16)
            wavfile.write(filepath, SAMPLE_RATE, audio_int16)
            print(f"✅ {filepath}  ({len(audio) / SAMPLE_RATE:.2f}s)")

    print(f"\nГотово! Сгенерировано {sum(len(v) for v in LEVELS.values())} аудиофайлов.")


if __name__ == "__main__":
    main()
