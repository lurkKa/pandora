#!/usr/bin/env python3
"""
PANDORA Behavior Agent — Local Noise Monitor v2
================================================

Captures audio from the microphone, detects disruptive noise
(screams, banging, whistling, sustained shouting) while ignoring normal speech,
and sends violation reports to the PANDORA server.

v2 changes:
  - 250ms frames (was 1s) — catches millisecond-level spikes
  - Sub-frame peak detection (50ms chunks inside each frame)
  - Single-frame immediate reporting for loud spikes
  - Lower thresholds for higher sensitivity
  - Default server URL: https://pandora-academy.onrender.com

Dependencies: pip install sounddevice numpy scipy requests

Usage:
    python behavior_agent.py                                    # default: render server
    python behavior_agent.py --server https://pandora-academy.onrender.com
    python behavior_agent.py --test                             # dry-run mode
"""

import argparse
import json
import logging
import os
import sys
import time
from collections import deque
from pathlib import Path

import numpy as np

try:
    import sounddevice as sd
except ImportError:
    print("ERROR: sounddevice not installed. Run: pip install sounddevice")
    sys.exit(1)

try:
    from scipy import signal as scipy_signal
    from scipy.fft import rfft, rfftfreq
except ImportError:
    print("ERROR: scipy not installed. Run: pip install scipy")
    sys.exit(1)

try:
    import requests
except ImportError:
    print("ERROR: requests not installed. Run: pip install requests")
    sys.exit(1)


# ==================== CONFIG ====================

SAMPLE_RATE = 16000       # 16kHz — sufficient for voice/noise
FRAME_DURATION = 0.25     # 250ms per analysis frame (was 1s — now 4x faster)
CHANNELS = 1
WINDOW_SIZE = 20          # 20 frames × 0.25s = 5 seconds total window
COOLDOWN_SECONDS = 25     # Min gap between reports
SUBFRAME_MS = 50          # Sub-frame peak detection: 50ms chunks

# --- Thresholds (tuned for classroom — ignores speech, catches screams/banging) ---
RMS_QUIET = 0.015         # Below this = silence
RMS_NORMAL_MAX = 0.07     # Normal speech ceiling
RMS_MEDIUM = 0.14         # Medium disruption
RMS_LOUD = 0.22           # Loud disruption
RMS_CRITICAL = 0.33       # Critical noise

# Spectral centroid thresholds (Hz)
CENTROID_SPEECH_MAX = 3200
CENTROID_SCREAM_MIN = 3500  # Screams/whistling

# Zero-crossing rate (per second)
ZCR_NOISE_MIN = 4000       # Noise vs speech boundary

# Onset detection
ONSET_RATIO = 3.5          # Sudden energy spike ratio

# Minimum frames to trigger report
MIN_FRAMES_FOR_REPORT = 1  # Single frame can trigger if score is high enough
MIN_FRAMES_SUSTAINED = 4   # 4 frames (1s) for medium-score sustained events


logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("behavior_agent")


# ==================== AUDIO ANALYSIS ====================

def compute_rms(audio: np.ndarray) -> float:
    """Root Mean Square energy, normalized to [0, 1]."""
    return float(np.sqrt(np.mean(audio.astype(np.float64) ** 2)))


def compute_peak_rms(audio: np.ndarray, sr: int, subframe_ms: int = 50) -> float:
    """Peak RMS across sub-frames (catches millisecond spikes)."""
    chunk_size = int(sr * subframe_ms / 1000)
    if chunk_size < 1 or len(audio) < chunk_size:
        return compute_rms(audio)
    peak = 0.0
    for i in range(0, len(audio) - chunk_size + 1, chunk_size):
        chunk_rms = compute_rms(audio[i:i + chunk_size])
        if chunk_rms > peak:
            peak = chunk_rms
    return peak


def compute_spectral_centroid(audio: np.ndarray, sr: int) -> float:
    """Frequency-weighted average (spectral centroid) in Hz."""
    spectrum = np.abs(rfft(audio))
    freqs = rfftfreq(len(audio), d=1.0 / sr)
    if spectrum.sum() < 1e-10:
        return 0.0
    return float(np.sum(freqs * spectrum) / np.sum(spectrum))


def compute_zcr(audio: np.ndarray, sr: int) -> float:
    """Zero-crossing rate per second."""
    signs = np.sign(audio)
    crossings = np.sum(np.abs(np.diff(signs)) > 0)
    duration = len(audio) / sr
    return float(crossings / duration) if duration > 0 else 0.0


def compute_spectral_flatness(audio: np.ndarray) -> float:
    """Spectral flatness (Wiener entropy). 1.0 = white noise, 0.0 = tonal."""
    spectrum = np.abs(rfft(audio))
    spectrum = spectrum[spectrum > 1e-10]
    if len(spectrum) < 2:
        return 0.0
    log_spectrum = np.log(spectrum + 1e-10)
    geo_mean = np.exp(np.mean(log_spectrum))
    arith_mean = np.mean(spectrum)
    if arith_mean < 1e-10:
        return 0.0
    return float(geo_mean / arith_mean)


def compute_high_freq_energy_ratio(audio: np.ndarray, sr: int, cutoff: float = 3000.0) -> float:
    """Ratio of energy above cutoff frequency to total energy."""
    spectrum = np.abs(rfft(audio)) ** 2
    freqs = rfftfreq(len(audio), d=1.0 / sr)
    total = np.sum(spectrum)
    if total < 1e-10:
        return 0.0
    high = np.sum(spectrum[freqs >= cutoff])
    return float(high / total)


# ==================== FRAME CLASSIFICATION ====================

class FrameResult:
    """Analysis result for a single audio frame."""
    __slots__ = ('rms', 'peak_rms', 'centroid', 'zcr', 'flatness', 'hf_ratio',
                 'is_disruptive', 'disruption_score')

    def __init__(self, rms, peak_rms, centroid, zcr, flatness, hf_ratio):
        self.rms = rms
        self.peak_rms = peak_rms
        self.centroid = centroid
        self.zcr = zcr
        self.flatness = flatness
        self.hf_ratio = hf_ratio
        self.is_disruptive = False
        self.disruption_score = 0.0


def classify_frame(audio: np.ndarray, sr: int, prev_rms: float = 0.0) -> FrameResult:
    """
    Classify a single audio frame. Uses BOTH average RMS and sub-frame peak RMS
    so that even a brief 50ms spike inside a 250ms frame gets detected.
    """
    rms = compute_rms(audio)
    peak_rms = compute_peak_rms(audio, sr, SUBFRAME_MS)
    centroid = compute_spectral_centroid(audio, sr)
    zcr = compute_zcr(audio, sr)
    flatness = compute_spectral_flatness(audio)
    hf_ratio = compute_high_freq_energy_ratio(audio, sr)

    # Use the higher of average and peak for threshold comparisons
    effective_rms = max(rms, peak_rms * 0.8)

    result = FrameResult(rms, peak_rms, centroid, zcr, flatness, hf_ratio)
    score = 0.0

    # --- Rule 1: Screaming / whistling (energy + high frequency) ---
    if effective_rms > RMS_NORMAL_MAX and centroid > CENTROID_SCREAM_MIN:
        score += 0.4
        if hf_ratio > 0.25:
            score += 0.2

    # --- Rule 2: Chaotic noise (energy + noisy spectrum) ---
    if effective_rms > RMS_NORMAL_MAX and zcr > ZCR_NOISE_MIN and flatness > 0.25:
        score += 0.3

    # --- Rule 3: Impact/banging (sudden energy spike) ---
    if prev_rms > 0 and peak_rms > prev_rms * ONSET_RATIO and peak_rms > RMS_MEDIUM:
        score += 0.5

    # --- Rule 4: Loud noise by raw level ---
    if effective_rms > RMS_CRITICAL:
        score += 0.7
    elif effective_rms > RMS_LOUD:
        score += 0.4
    elif effective_rms > RMS_MEDIUM:
        score += 0.15

    # --- Rule 5: Sub-frame spike much louder than average (transient) ---
    if peak_rms > rms * 2.5 and peak_rms > RMS_MEDIUM:
        score += 0.3

    # --- Speech filter: stable, moderate, tonal = NOT disruptive ---
    is_speech_like = (
        RMS_QUIET < effective_rms < RMS_MEDIUM and
        300 < centroid < CENTROID_SPEECH_MAX and
        zcr < ZCR_NOISE_MIN and
        flatness < 0.25 and
        peak_rms < rms * 2.0  # No sub-frame spikes
    )
    if is_speech_like:
        score *= 0.05  # Aggressively suppress speech

    result.disruption_score = min(1.0, score)
    result.is_disruptive = score >= 0.30  # Only real disruptions
    return result


# ==================== INCIDENT DETECTION ====================

def determine_severity(window: deque) -> tuple:
    """
    Analyze sliding window of frame results to determine incident severity.
    Returns (severity, noise_level, description) or (None, 0, '') if no incident.

    Key change: a SINGLE high-score frame can trigger a report immediately.
    """
    disruptive_frames = [f for f in window if f.is_disruptive]
    n = len(disruptive_frames)

    if n == 0:
        return None, 0.0, ""

    avg_score = float(np.mean([f.disruption_score for f in disruptive_frames]))
    max_score = float(max(f.disruption_score for f in disruptive_frames))
    max_peak_rms = float(max(f.peak_rms for f in disruptive_frames))

    # For sustained low-intensity noise, require multiple frames
    if n < MIN_FRAMES_SUSTAINED and max_score < 0.45:
        return None, 0.0, ""

    # Single frame with score >= 0.45 is enough (a loud clap, whistle, scream)

    avg_rms = float(np.mean([f.rms for f in disruptive_frames]))
    max_centroid = float(max(f.centroid for f in disruptive_frames))

    # Build description
    descriptors = []
    if max_centroid > CENTROID_SCREAM_MIN and max_score > 0.3:
        descriptors.append("крик/визг/свист")
    if any(f.peak_rms > f.rms * 2.5 for f in disruptive_frames):
        descriptors.append("удары/хлопки")
    if avg_rms > RMS_LOUD:
        descriptors.append("громкий шум")
    elif avg_rms > RMS_MEDIUM:
        descriptors.append("повышенный шум")
    desc_text = ", ".join(descriptors) if descriptors else "устойчивый шум"
    duration_s = n * FRAME_DURATION
    desc = f"Обнаружено: {desc_text} ({duration_s:.1f}с)"

    # Determine severity
    if n >= 12 or max_score >= 0.75 or max_peak_rms > RMS_CRITICAL:
        return "critical", min(1.0, avg_score), desc
    elif n >= 6 or max_score >= 0.45 or max_peak_rms > RMS_LOUD:
        return "loud", min(1.0, avg_score * 0.85), desc
    else:
        return "medium", min(1.0, avg_score * 0.65), desc


# ==================== REPORTING ====================

def send_report(server_url: str, token: str, severity: str, noise_level: float, description: str) -> bool:
    """Send noise violation report to PANDORA server."""
    url = f"{server_url.rstrip('/')}/api/behavior/report"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "severity": severity,
        "noise_level": round(noise_level, 3),
        "description": description
    }
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            log.info("✅ Report sent: id=%s, severity=%s, suggested_xp=%s",
                     data.get("id"), severity, data.get("suggested_xp"))
            return True
        else:
            log.error("❌ Server returned %d: %s", resp.status_code, resp.text[:200])
            return False
    except requests.RequestException as e:
        log.error("❌ Connection error: %s", e)
        return False


# ==================== MAIN LOOP ====================

def run_monitor(server_url: str, token: str, dry_run: bool = False):
    """Main monitoring loop."""
    log.info("=" * 50)
    log.info("🔊 PANDORA Behavior Agent v2 started")
    log.info("   Server: %s", server_url if not dry_run else "(dry-run)")
    log.info("   Sample rate: %d Hz", SAMPLE_RATE)
    log.info("   Frame: %.0fms, Window: %.1fs, Sub-frame: %dms",
             FRAME_DURATION * 1000, WINDOW_SIZE * FRAME_DURATION, SUBFRAME_MS)
    log.info("   Cooldown: %ds between reports", COOLDOWN_SECONDS)
    log.info("=" * 50)

    frame_samples = int(SAMPLE_RATE * FRAME_DURATION)
    window = deque(maxlen=WINDOW_SIZE)
    last_report_time = 0.0
    prev_rms = 0.0

    while True:
        try:
            # Record one frame (250ms)
            audio = sd.rec(frame_samples, samplerate=SAMPLE_RATE, channels=CHANNELS,
                           dtype='float32', blocking=True)
            audio = audio.flatten()

            # Analyze frame
            result = classify_frame(audio, SAMPLE_RATE, prev_rms)
            prev_rms = result.rms
            window.append(result)

            # Status indicator
            bar_len = int(min(result.peak_rms * 80, 50))
            bar = "█" * bar_len
            status = "🔴" if result.is_disruptive else "🟢"
            sys.stdout.write(f"\r{status} RMS:{result.rms:.3f} Peak:{result.peak_rms:.3f} "
                             f"C:{result.centroid:.0f}Hz "
                             f"Score:{result.disruption_score:.2f} "
                             f"|{bar:<50}|")
            sys.stdout.flush()

            # Check for incident — EVERY frame, not just after N frames
            severity, noise_level, description = determine_severity(window)

            if severity:
                now = time.time()
                if now - last_report_time >= COOLDOWN_SECONDS:
                    print()  # New line after progress bar
                    log.warning("⚠️  Disruption detected: %s (level=%.2f) — %s",
                                severity, noise_level, description)

                    if dry_run:
                        log.info("   [DRY-RUN] Would send: severity=%s, noise=%.3f",
                                 severity, noise_level)
                        last_report_time = now
                        window.clear()
                    else:
                        if send_report(server_url, token, severity, noise_level, description):
                            last_report_time = now
                            window.clear()  # Reset window after report
                else:
                    remaining = int(COOLDOWN_SECONDS - (now - last_report_time))
                    if result.is_disruptive:
                        sys.stdout.write(f" [cooldown {remaining}s]")

        except KeyboardInterrupt:
            print("\n")
            log.info("🛑 Agent stopped by user")
            break
        except sd.PortAudioError as e:
            log.error("Audio error: %s. Retrying in 3s...", e)
            time.sleep(3)
        except Exception as e:
            log.error("Unexpected error: %s", e)
            time.sleep(1)


# ==================== CLI ====================

DEFAULT_SERVER = "https://pandora-academy.onrender.com"

def main():
    global COOLDOWN_SECONDS, RMS_NORMAL_MAX

    parser = argparse.ArgumentParser(
        description="PANDORA Behavior Agent v2 — Local noise monitor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python behavior_agent.py                                          # default server
  python behavior_agent.py --server https://pandora-academy.onrender.com
  python behavior_agent.py --test
  python behavior_agent.py --cooldown 60
        """
    )
    parser.add_argument("--server", "-s", default=DEFAULT_SERVER,
                        help=f"PANDORA server URL (default: {DEFAULT_SERVER})")
    parser.add_argument("--token-file", "-t",
                        default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                             "..", ".behavior_agent_token"),
                        help="Path to token file (default: ../.behavior_agent_token)")
    parser.add_argument("--token", help="Token value directly (overrides --token-file)")
    parser.add_argument("--test", action="store_true",
                        help="Dry-run mode: detect but don't send reports")
    parser.add_argument("--cooldown", type=int, default=COOLDOWN_SECONDS,
                        help=f"Seconds between reports (default: {COOLDOWN_SECONDS})")
    parser.add_argument("--sensitivity", type=float, default=1.0,
                        help="Sensitivity multiplier: >1 = more sensitive, <1 = less (default: 1.0)")

    args = parser.parse_args()

    # Apply overrides
    COOLDOWN_SECONDS = args.cooldown
    if args.sensitivity != 1.0:
        s = args.sensitivity
        RMS_NORMAL_MAX /= s
        log.info("Sensitivity multiplier: %.1f (RMS threshold: %.3f)", s, RMS_NORMAL_MAX)

    # Load token
    token = ""
    if args.token:
        token = args.token
    else:
        token_path = Path(args.token_file).resolve()
        if token_path.exists():
            token = token_path.read_text().strip()
            log.info("Token loaded from %s", token_path)
        else:
            log.warning("Token file not found: %s", token_path)

    if not token and not args.test:
        log.error("No token provided. Use --token, --token-file, or --test mode.")
        sys.exit(1)

    # Test audio device
    try:
        log.info("Testing audio device...")
        test = sd.rec(int(SAMPLE_RATE * 0.5), samplerate=SAMPLE_RATE,
                      channels=CHANNELS, dtype='float32', blocking=True)
        peak = float(np.max(np.abs(test)))
        log.info("✅ Audio device OK (peak=%.4f)", peak)
    except Exception as e:
        log.error("❌ Cannot access microphone: %s", e)
        log.error("   Make sure a microphone is connected and accessible.")
        sys.exit(1)

    run_monitor(args.server, token, dry_run=args.test)


if __name__ == "__main__":
    main()
