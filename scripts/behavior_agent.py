#!/usr/bin/env python3
"""
PANDORA Behavior Agent — Local Noise Monitor
============================================

Captures audio from the microphone, detects disruptive noise
(screams, banging, sustained shouting) while ignoring normal speech,
and sends violation reports to the PANDORA server.

Detection is deterministic (no ML):
  1. RMS energy for overall loudness
  2. Spectral centroid for frequency content (screams = high freq)
  3. Zero-crossing rate for noise vs tonal (speech is tonal, noise is noisy)
  4. Onset strength for sudden impacts (banging)
  5. Sliding window (5s) to avoid false positives

Dependencies: pip install sounddevice numpy scipy requests

Usage:
    python behavior_agent.py --server http://192.168.1.10:8000 --token-file ../.behavior_agent_token
    python behavior_agent.py --test   # dry-run mode, prints detections to console
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
FRAME_DURATION = 1.0      # Seconds per analysis frame
CHANNELS = 1
WINDOW_SIZE = 5           # Sliding window: 5 frames (5 seconds)
COOLDOWN_SECONDS = 30     # Min gap between reports to avoid spam

# --- Thresholds (tuned for classroom environment) ---
# RMS thresholds (normalized 0-1 for 16-bit audio)
RMS_NORMAL_MAX = 0.06     # Normal speech ceiling
RMS_MEDIUM = 0.12         # Medium disruption
RMS_LOUD = 0.22           # Loud disruption
RMS_CRITICAL = 0.35       # Critical noise

# Spectral centroid thresholds (Hz)
# Normal speech: 300-3000 Hz centroid
# Screams/shrieks: centroid > 3000 Hz
CENTROID_SPEECH_MAX = 3200
CENTROID_SCREAM_MIN = 3500

# Zero-crossing rate (per second)
# Speech: ~1000-3000 ZCR/s
# Noise/screams: > 4000 ZCR/s
ZCR_NOISE_MIN = 4000

# Onset detection (sudden energy spike ratio)
ONSET_RATIO = 4.0         # Frame energy > 4x previous = impact

# Minimum sustained frames for detection
MIN_FRAMES_MEDIUM = 2     # 2s of medium noise
MIN_FRAMES_LOUD = 3       # 3s+ of loud noise or very high peak
MIN_FRAMES_CRITICAL = 5   # 5s sustained or extreme peak


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
    __slots__ = ('rms', 'centroid', 'zcr', 'flatness', 'hf_ratio', 'is_disruptive', 'disruption_score')

    def __init__(self, rms, centroid, zcr, flatness, hf_ratio):
        self.rms = rms
        self.centroid = centroid
        self.zcr = zcr
        self.flatness = flatness
        self.hf_ratio = hf_ratio
        self.is_disruptive = False
        self.disruption_score = 0.0


def classify_frame(audio: np.ndarray, sr: int, prev_rms: float = 0.0) -> FrameResult:
    """
    Classify a single audio frame as speech or disruptive noise.

    Disruptive if ANY of:
      - High RMS + high spectral centroid (screaming)
      - High RMS + high ZCR + high spectral flatness (chaotic noise)
      - Sudden onset spike (banging)
      - Very high RMS alone (extremely loud)
    """
    rms = compute_rms(audio)
    centroid = compute_spectral_centroid(audio, sr)
    zcr = compute_zcr(audio, sr)
    flatness = compute_spectral_flatness(audio)
    hf_ratio = compute_high_freq_energy_ratio(audio, sr)

    result = FrameResult(rms, centroid, zcr, flatness, hf_ratio)
    score = 0.0

    # --- Rule 1: Screaming (high energy + high frequency) ---
    if rms > RMS_NORMAL_MAX and centroid > CENTROID_SCREAM_MIN:
        score += 0.4
        if hf_ratio > 0.3:  # Lots of high-freq energy
            score += 0.2

    # --- Rule 2: Chaotic noise (high energy + noisy spectrum) ---
    if rms > RMS_NORMAL_MAX and zcr > ZCR_NOISE_MIN and flatness > 0.3:
        score += 0.3

    # --- Rule 3: Impact/banging (sudden energy spike) ---
    if prev_rms > 0 and rms > prev_rms * ONSET_RATIO and rms > RMS_MEDIUM:
        score += 0.5

    # --- Rule 4: Extremely loud (overwhelms everything) ---
    if rms > RMS_CRITICAL:
        score += 0.6
    elif rms > RMS_LOUD:
        score += 0.3
    elif rms > RMS_MEDIUM:
        score += 0.1

    # --- Speech filter: stable, moderate, tonal = NOT disruptive ---
    is_speech_like = (
        RMS_NORMAL_MAX * 0.3 < rms < RMS_MEDIUM and
        300 < centroid < CENTROID_SPEECH_MAX and
        zcr < ZCR_NOISE_MIN and
        flatness < 0.25
    )
    if is_speech_like:
        score *= 0.1  # Drastically reduce score for speech

    result.disruption_score = min(1.0, score)
    result.is_disruptive = score >= 0.25
    return result


# ==================== INCIDENT DETECTION ====================

def determine_severity(window: deque) -> tuple:
    """
    Analyze sliding window of frame results to determine incident severity.
    Returns (severity, noise_level, description) or (None, 0, '') if no incident.
    """
    disruptive_frames = [f for f in window if f.is_disruptive]
    n = len(disruptive_frames)

    if n < MIN_FRAMES_MEDIUM:
        return None, 0.0, ""

    avg_score = np.mean([f.disruption_score for f in disruptive_frames])
    max_score = max(f.disruption_score for f in disruptive_frames)
    avg_rms = np.mean([f.rms for f in disruptive_frames])
    max_centroid = max(f.centroid for f in disruptive_frames)

    # Build description
    descriptors = []
    if max_centroid > CENTROID_SCREAM_MIN:
        descriptors.append("крик/визг")
    if any(f.rms > f_prev.rms * ONSET_RATIO for f, f_prev in zip(list(window)[1:], list(window)[:-1])
           if f_prev.rms > 0):
        descriptors.append("удары/хлопки")
    if avg_rms > RMS_LOUD:
        descriptors.append("громкий шум")
    desc_text = ", ".join(descriptors) if descriptors else "устойчивый шум"
    desc = f"Обнаружено: {desc_text} ({n}с)"

    # Determine severity
    if n >= MIN_FRAMES_CRITICAL or max_score >= 0.8:
        return "critical", min(1.0, avg_score), desc
    elif n >= MIN_FRAMES_LOUD or max_score >= 0.5:
        return "loud", min(1.0, avg_score * 0.8), desc
    else:
        return "medium", min(1.0, avg_score * 0.6), desc


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
    log.info("🔊 PANDORA Behavior Agent started")
    log.info("   Server: %s", server_url if not dry_run else "(dry-run)")
    log.info("   Sample rate: %d Hz", SAMPLE_RATE)
    log.info("   Frame: %.1fs, Window: %ds", FRAME_DURATION, WINDOW_SIZE)
    log.info("   Cooldown: %ds between reports", COOLDOWN_SECONDS)
    log.info("=" * 50)

    frame_samples = int(SAMPLE_RATE * FRAME_DURATION)
    window = deque(maxlen=WINDOW_SIZE)
    last_report_time = 0.0
    prev_rms = 0.0

    while True:
        try:
            # Record one frame
            audio = sd.rec(frame_samples, samplerate=SAMPLE_RATE, channels=CHANNELS,
                           dtype='float32', blocking=True)
            audio = audio.flatten()

            # Analyze frame
            result = classify_frame(audio, SAMPLE_RATE, prev_rms)
            prev_rms = result.rms
            window.append(result)

            # Status indicator
            bar_len = int(result.rms * 50)
            bar = "█" * min(bar_len, 50)
            status = "🔴" if result.is_disruptive else "🟢"
            sys.stdout.write(f"\r{status} RMS:{result.rms:.3f} C:{result.centroid:.0f}Hz "
                             f"ZCR:{result.zcr:.0f} Score:{result.disruption_score:.2f} "
                             f"|{bar:<50}|")
            sys.stdout.flush()

            # Check for incident
            if len(window) >= MIN_FRAMES_MEDIUM:
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

def main():
    global COOLDOWN_SECONDS, RMS_NORMAL_MAX

    parser = argparse.ArgumentParser(
        description="PANDORA Behavior Agent — Local noise monitor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python behavior_agent.py --server http://192.168.1.10:8000
  python behavior_agent.py --test
  python behavior_agent.py --server http://localhost:8000 --cooldown 60
        """
    )
    parser.add_argument("--server", "-s", default="http://localhost:8000",
                        help="PANDORA server URL (default: http://localhost:8000)")
    parser.add_argument("--token-file", "-t",
                        default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                             "..", ".behavior_agent_token"),
                        help="Path to token file (default: ../.behavior_agent_token)")
    parser.add_argument("--token", help="Token value directly (overrides --token-file)")
    parser.add_argument("--test", action="store_true",
                        help="Dry-run mode: detect but don't send reports")
    parser.add_argument("--cooldown", type=int, default=COOLDOWN_SECONDS,
                        help=f"Seconds between reports (default: {COOLDOWN_SECONDS})")
    parser.add_argument("--rms-threshold", type=float, default=RMS_NORMAL_MAX,
                        help=f"Normal speech RMS ceiling (default: {RMS_NORMAL_MAX})")

    args = parser.parse_args()

    # Apply overrides
    COOLDOWN_SECONDS = args.cooldown
    RMS_NORMAL_MAX = args.rms_threshold

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
        log.info("✅ Audio device OK (recorded %d samples)", len(test.flatten()))
    except Exception as e:
        log.error("❌ Cannot access microphone: %s", e)
        log.error("   Make sure a microphone is connected and accessible.")
        sys.exit(1)

    run_monitor(args.server, token, dry_run=args.test)


if __name__ == "__main__":
    main()
