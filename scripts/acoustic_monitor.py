#!/usr/bin/env python3
"""
Acoustic Incident Monitor
=========================

A robust local microphone monitor for:
  - elevated noise
  - scream-like / shriek-like events
  - impact-like events (bangs, slams, claps)
  - sustained shouting-like / chaotic noise

Important:
  - This script is for acoustic event monitoring, not for judging "behavior".
  - It estimates relative loudness in dBFS and dB above background floor.
  - It is much more robust than a simple threshold script because it uses:
      * short frames
      * adaptive noise floor
      * calibration
      * event state machine with hysteresis
      * multiple spectral features
      * cooldown and confidence scoring

Dependencies:
    pip install sounddevice numpy scipy requests

Examples:
    python acoustic_monitor.py --test
    python acoustic_monitor.py --server http://localhost:8000 --token-file ../.acoustic_agent_token
    python acoustic_monitor.py --list-devices
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import queue
import sys
import threading
import time
from collections import Counter, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Deque, Dict, List, Optional

import numpy as np

try:
    import sounddevice as sd
except ImportError:
    print("ERROR: sounddevice not installed. Run: pip install sounddevice")
    sys.exit(1)

try:
    import requests
except ImportError:
    print("ERROR: requests not installed. Run: pip install requests")
    sys.exit(1)

try:
    from scipy import signal as scipy_signal
    from scipy.fft import rfft, rfftfreq
except ImportError:
    print("ERROR: scipy not installed. Run: pip install scipy")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class Config:
    sample_rate: int = 16000
    channels: int = 1
    frame_duration: float = 0.20            # 200 ms for much better time resolution
    calibrate_seconds: float = 8.0
    cooldown_seconds: float = 20.0
    min_event_seconds: float = 0.40
    hangover_frames: int = 3               # keep event alive through brief dips
    baseline_alpha: float = 0.03           # adaptive floor update speed
    floor_margin_quiet_db: float = 6.0     # frames within this margin may update floor
    min_floor_dbfs: float = -70.0
    max_floor_dbfs: float = -18.0

    # Absolute guardrails (dBFS, not SPL)
    min_interest_dbfs: float = -42.0       # below this, we mostly ignore
    impact_start_db_delta: float = 10.0    # sudden jump from previous frame
    impact_crest_db_min: float = 10.0
    scream_centroid_hz: float = 2400.0
    scream_hf_ratio: float = 0.25
    chaotic_flatness: float = 0.22
    chaotic_zcr_per_s: float = 2400.0
    loud_above_floor_db: float = 10.0
    very_loud_above_floor_db: float = 18.0

    # Reporting
    endpoint_path: str = "/api/behavior/report"
    request_timeout: float = 10.0


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("acoustic_monitor")


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

EPS = 1e-10


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def safe_db(x: float) -> float:
    return 20.0 * math.log10(max(float(x), EPS))


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def lin_score(x: float, start: float, stop: float) -> float:
    """Linear score from 0..1 between start and stop."""
    if stop <= start:
        return 1.0 if x >= stop else 0.0
    return clamp((x - start) / (stop - start), 0.0, 1.0)


# ---------------------------------------------------------------------------
# Signal processing
# ---------------------------------------------------------------------------

def make_highpass_sos(sr: int, cutoff_hz: float = 80.0):
    return scipy_signal.butter(4, cutoff_hz, btype="highpass", fs=sr, output="sos")


def preprocess_audio(audio: np.ndarray, hp_sos) -> np.ndarray:
    x = np.asarray(audio, dtype=np.float64).reshape(-1)
    if x.size == 0:
        return x
    x = x - np.mean(x)  # remove DC
    x = scipy_signal.sosfilt(hp_sos, x)
    return x


def compute_rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(x)) + EPS))


def compute_peak(x: np.ndarray) -> float:
    return float(np.max(np.abs(x)) + EPS)


def compute_spectral_centroid(x: np.ndarray, sr: int) -> float:
    spectrum = np.abs(rfft(x))
    if spectrum.size == 0 or float(np.sum(spectrum)) < EPS:
        return 0.0
    freqs = rfftfreq(len(x), d=1.0 / sr)
    return float(np.sum(freqs * spectrum) / np.sum(spectrum))


def compute_spectral_flatness(x: np.ndarray) -> float:
    spectrum = np.abs(rfft(x)) + EPS
    geo = float(np.exp(np.mean(np.log(spectrum))))
    arith = float(np.mean(spectrum))
    return float(geo / arith) if arith > EPS else 0.0


def compute_high_freq_energy_ratio(x: np.ndarray, sr: int, cutoff_hz: float = 3000.0) -> float:
    power = np.square(np.abs(rfft(x)))
    if power.size == 0:
        return 0.0
    freqs = rfftfreq(len(x), d=1.0 / sr)
    total = float(np.sum(power))
    if total < EPS:
        return 0.0
    high = float(np.sum(power[freqs >= cutoff_hz]))
    return high / total


def compute_zcr_per_second(x: np.ndarray, sr: int) -> float:
    if x.size < 2:
        return 0.0
    signs = np.signbit(x)
    crossings = np.count_nonzero(signs[1:] != signs[:-1])
    duration = len(x) / float(sr)
    return float(crossings / duration) if duration > 0 else 0.0


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class FrameFeatures:
    ts: float
    rms: float
    peak: float
    dbfs: float
    peak_dbfs: float
    crest_db: float
    centroid_hz: float
    flatness: float
    hf_ratio: float
    zcr_per_s: float
    floor_dbfs: float
    db_above_floor: float
    onset_db: float
    scores: Dict[str, float]
    speech_like: float
    total_score: float
    label: str


@dataclass
class EventSummary:
    event_type: str
    severity: str
    confidence: float
    noise_level: float
    description: str
    started_at: str
    ended_at: str
    duration_sec: float
    peak_dbfs: float
    peak_above_floor_db: float
    mean_above_floor_db: float
    frame_count: int
    metrics: Dict[str, float] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Adaptive background floor
# ---------------------------------------------------------------------------

class NoiseFloorTracker:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.floor_dbfs: float = -55.0
        self.calibration_values: List[float] = []
        self.calibrated: bool = False

    def feed_calibration(self, dbfs: float):
        self.calibration_values.append(dbfs)

    def finalize_calibration(self):
        if not self.calibration_values:
            self.floor_dbfs = -55.0
        else:
            # Robust estimate: median of quieter half
            values = np.array(self.calibration_values, dtype=np.float64)
            median = float(np.median(values))
            lower_half = values[values <= median]
            base = float(np.median(lower_half)) if lower_half.size else median
            self.floor_dbfs = clamp(base, self.cfg.min_floor_dbfs, self.cfg.max_floor_dbfs)
        self.calibrated = True
        log.info("Calibration complete. Estimated noise floor: %.1f dBFS", self.floor_dbfs)

    def maybe_update(self, frame_dbfs: float, total_score: float):
        if not self.calibrated:
            return
        if total_score > 0.25:
            return
        if frame_dbfs <= self.floor_dbfs + self.cfg.floor_margin_quiet_db:
            alpha = self.cfg.baseline_alpha
            self.floor_dbfs = clamp(
                (1.0 - alpha) * self.floor_dbfs + alpha * frame_dbfs,
                self.cfg.min_floor_dbfs,
                self.cfg.max_floor_dbfs,
            )


# ---------------------------------------------------------------------------
# Frame classifier
# ---------------------------------------------------------------------------

class FrameClassifier:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.prev_dbfs: float = -90.0

    def classify(self, ts: float, x: np.ndarray, floor_dbfs: float, sr: int) -> FrameFeatures:
        rms = compute_rms(x)
        peak = compute_peak(x)
        dbfs = safe_db(rms)
        peak_dbfs = safe_db(peak)
        crest_db = peak_dbfs - dbfs
        centroid = compute_spectral_centroid(x, sr)
        flatness = compute_spectral_flatness(x)
        hf_ratio = compute_high_freq_energy_ratio(x, sr, cutoff_hz=3000.0)
        zcr = compute_zcr_per_second(x, sr)

        db_above_floor = dbfs - floor_dbfs
        onset_db = dbfs - self.prev_dbfs
        self.prev_dbfs = dbfs

        loudness = max(
            lin_score(db_above_floor, self.cfg.loud_above_floor_db - 2.0, self.cfg.very_loud_above_floor_db + 6.0),
            lin_score(dbfs, self.cfg.min_interest_dbfs, -18.0),
        )

        scream_like = (
            0.45 * lin_score(db_above_floor, 8.0, 18.0) +
            0.25 * lin_score(centroid, self.cfg.scream_centroid_hz, 4200.0) +
            0.20 * lin_score(hf_ratio, self.cfg.scream_hf_ratio, 0.65) +
            0.10 * lin_score(flatness, 0.12, 0.38)
        )

        chaotic_noise = (
            0.35 * lin_score(db_above_floor, 9.0, 20.0) +
            0.25 * lin_score(flatness, self.cfg.chaotic_flatness, 0.60) +
            0.20 * lin_score(zcr, self.cfg.chaotic_zcr_per_s, 6000.0) +
            0.20 * lin_score(hf_ratio, 0.18, 0.55)
        )

        impact_like = (
            0.40 * lin_score(onset_db, self.cfg.impact_start_db_delta, 20.0) +
            0.30 * lin_score(crest_db, self.cfg.impact_crest_db_min, 20.0) +
            0.20 * lin_score(db_above_floor, 10.0, 22.0) +
            0.10 * lin_score(peak_dbfs, -18.0, -3.0)
        )

        speech_like = (
            0.30 * (1.0 - lin_score(abs(centroid - 1400.0), 800.0, 2200.0)) +
            0.25 * (1.0 - lin_score(flatness, 0.18, 0.45)) +
            0.20 * (1.0 - lin_score(hf_ratio, 0.18, 0.45)) +
            0.15 * (1.0 - lin_score(abs(zcr - 1800.0), 1000.0, 3500.0)) +
            0.10 * (1.0 - lin_score(db_above_floor, 16.0, 28.0))
        )
        speech_like = clamp(speech_like, 0.0, 1.0)

        # Global score with speech penalty, but do not suppress clear impacts.
        raw_total = max(
            loudness * 0.75,
            scream_like,
            chaotic_noise,
            impact_like,
        )
        if impact_like < 0.60:
            raw_total *= (1.0 - 0.55 * speech_like)

        raw_total = clamp(raw_total, 0.0, 1.0)

        scores = {
            "elevated_noise": loudness,
            "scream_like": scream_like,
            "chaotic_noise": chaotic_noise,
            "impact_like": impact_like,
        }

        label = max(scores, key=scores.get)
        if raw_total < 0.38:
            label = "background"

        return FrameFeatures(
            ts=ts,
            rms=rms,
            peak=peak,
            dbfs=dbfs,
            peak_dbfs=peak_dbfs,
            crest_db=crest_db,
            centroid_hz=centroid,
            flatness=flatness,
            hf_ratio=hf_ratio,
            zcr_per_s=zcr,
            floor_dbfs=floor_dbfs,
            db_above_floor=db_above_floor,
            onset_db=onset_db,
            scores=scores,
            speech_like=speech_like,
            total_score=raw_total,
            label=label,
        )


# ---------------------------------------------------------------------------
# Event aggregation
# ---------------------------------------------------------------------------

class EventAggregator:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.active_frames: List[FrameFeatures] = []
        self.quiet_run: int = 0
        self.last_sent_ts: float = 0.0

    def ingest(self, frame: FrameFeatures) -> Optional[EventSummary]:
        start_trigger = frame.total_score >= 0.58 or frame.scores["impact_like"] >= 0.72
        continue_trigger = frame.total_score >= 0.34 or frame.scores["impact_like"] >= 0.52

        if not self.active_frames:
            if start_trigger:
                self.active_frames = [frame]
                self.quiet_run = 0
            return None

        self.active_frames.append(frame)

        if continue_trigger:
            self.quiet_run = 0
            return None

        self.quiet_run += 1
        if self.quiet_run < self.cfg.hangover_frames:
            return None

        event = self._finalize_event()
        self.active_frames = []
        self.quiet_run = 0
        return event

    def flush(self) -> Optional[EventSummary]:
        if not self.active_frames:
            return None
        event = self._finalize_event()
        self.active_frames = []
        self.quiet_run = 0
        return event

    def _finalize_event(self) -> Optional[EventSummary]:
        frames = self.active_frames[:]
        if not frames:
            return None

        frame_duration = self.cfg.frame_duration
        duration = len(frames) * frame_duration
        if duration < self.cfg.min_event_seconds:
            return None

        score_counter: Dict[str, float] = Counter()
        for f in frames:
            for k, v in f.scores.items():
                score_counter[k] += float(v)

        event_type = max(score_counter, key=score_counter.get)
        peak_dbfs = max(f.peak_dbfs for f in frames)
        peak_above_floor = max(f.db_above_floor for f in frames)
        mean_above_floor = float(np.mean([f.db_above_floor for f in frames]))
        mean_score = float(np.mean([f.total_score for f in frames]))
        max_score = max(f.total_score for f in frames)

        severity_points = (
            0.45 * lin_score(peak_above_floor, 10.0, 28.0) +
            0.25 * lin_score(duration, 0.5, 5.0) +
            0.30 * max_score
        )
        severity_points = clamp(severity_points, 0.0, 1.0)

        if peak_above_floor >= 24.0 or severity_points >= 0.82:
            severity = "critical"
        elif peak_above_floor >= 16.0 or severity_points >= 0.58:
            severity = "loud"
        else:
            severity = "medium"

        confidence = clamp(0.55 * max_score + 0.45 * mean_score, 0.0, 1.0)
        noise_level = clamp(peak_above_floor / 28.0, 0.0, 1.0)

        descriptions = {
            "impact_like": "Обнаружен импульсный ударный шум",
            "scream_like": "Обнаружен крикоподобный/визгоподобный шум",
            "chaotic_noise": "Обнаружен хаотичный громкий шум",
            "elevated_noise": "Обнаружен устойчивый повышенный шум",
        }
        desc = (
            f"{descriptions.get(event_type, 'Обнаружен акустический инцидент')}: "
            f"{severity}, длительность {duration:.1f}с, "
            f"пик {peak_above_floor:.1f} дБ над фоном"
        )

        return EventSummary(
            event_type=event_type,
            severity=severity,
            confidence=confidence,
            noise_level=noise_level,
            description=desc,
            started_at=datetime.fromtimestamp(frames[0].ts, tz=timezone.utc).isoformat(),
            ended_at=datetime.fromtimestamp(frames[-1].ts, tz=timezone.utc).isoformat(),
            duration_sec=duration,
            peak_dbfs=peak_dbfs,
            peak_above_floor_db=peak_above_floor,
            mean_above_floor_db=mean_above_floor,
            frame_count=len(frames),
            metrics={
                "max_total_score": round(max_score, 3),
                "mean_total_score": round(mean_score, 3),
                "peak_above_floor_db": round(peak_above_floor, 2),
                "mean_above_floor_db": round(mean_above_floor, 2),
            },
        )

    def in_cooldown(self) -> bool:
        return (time.time() - self.last_sent_ts) < self.cfg.cooldown_seconds

    def mark_sent(self):
        self.last_sent_ts = time.time()


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def load_token(args) -> str:
    if args.token:
        return args.token.strip()

    token_path = Path(args.token_file).resolve()
    if token_path.exists():
        token = token_path.read_text(encoding="utf-8").strip()
        log.info("Token loaded from %s", token_path)
        return token

    log.warning("Token file not found: %s", token_path)
    return ""


def send_report(server_url: str, token: str, event: EventSummary, cfg: Config, dry_run: bool = False) -> bool:
    payload = {
        # backward-compatible core fields
        "severity": event.severity,
        "noise_level": round(event.noise_level, 3),
        "description": event.description,

        # richer fields
        "event_type": event.event_type,
        "confidence": round(event.confidence, 3),
        "started_at": event.started_at,
        "ended_at": event.ended_at,
        "duration_sec": round(event.duration_sec, 2),
        "peak_dbfs": round(event.peak_dbfs, 2),
        "peak_above_floor_db": round(event.peak_above_floor_db, 2),
        "mean_above_floor_db": round(event.mean_above_floor_db, 2),
        "frame_count": event.frame_count,
        "metrics": event.metrics,
    }

    if dry_run:
        log.info("[DRY-RUN] %s", json.dumps(payload, ensure_ascii=False))
        return True

    url = f"{server_url.rstrip('/')}{cfg.endpoint_path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=cfg.request_timeout)
        if resp.ok:
            log.info("Report sent successfully: %s %s", event.event_type, event.severity)
            return True
        log.error("Server returned %s: %s", resp.status_code, resp.text[:300])
        return False
    except requests.RequestException as e:
        log.error("Connection error: %s", e)
        return False


# ---------------------------------------------------------------------------
# Audio stream
# ---------------------------------------------------------------------------

class AudioStreamReader:
    def __init__(self, cfg: Config, device: Optional[int] = None):
        self.cfg = cfg
        self.device = device
        self.blocksize = int(round(cfg.sample_rate * cfg.frame_duration))
        self.q: "queue.Queue[np.ndarray]" = queue.Queue(maxsize=32)
        self.stop_event = threading.Event()
        self.stream = None

    def callback(self, indata, frames, time_info, status):
        if status:
            log.warning("Audio status: %s", status)
        if self.stop_event.is_set():
            return
        try:
            block = np.asarray(indata, dtype=np.float32).copy().reshape(-1)
            self.q.put_nowait(block)
        except queue.Full:
            # Drop oldest pressure by discarding this block; better than blocking audio callback.
            pass

    def __enter__(self):
        self.stream = sd.InputStream(
            samplerate=self.cfg.sample_rate,
            channels=self.cfg.channels,
            dtype="float32",
            blocksize=self.blocksize,
            device=self.device,
            callback=self.callback,
        )
        self.stream.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.stop_event.set()
        if self.stream is not None:
            try:
                self.stream.stop()
            finally:
                self.stream.close()

    def read(self, timeout: float = 1.0) -> Optional[np.ndarray]:
        try:
            return self.q.get(timeout=timeout)
        except queue.Empty:
            return None


# ---------------------------------------------------------------------------
# Main monitoring logic
# ---------------------------------------------------------------------------

def print_status(frame: FrameFeatures):
    type_short = {
        "background": "bg",
        "elevated_noise": "noise",
        "impact_like": "impact",
        "scream_like": "scream",
        "chaotic_noise": "chaos",
    }.get(frame.label, frame.label)

    bar_len = int(clamp(frame.db_above_floor, 0.0, 30.0) / 30.0 * 40)
    bar = "█" * bar_len + " " * (40 - bar_len)
    msg = (
        f"\r[{type_short:6}] "
        f"dbfs:{frame.dbfs:6.1f} "
        f"floor:{frame.floor_dbfs:6.1f} "
        f"+bg:{frame.db_above_floor:5.1f}dB "
        f"cent:{frame.centroid_hz:5.0f} "
        f"flat:{frame.flatness:4.2f} "
        f"score:{frame.total_score:4.2f} "
        f"|{bar}|"
    )
    sys.stdout.write(msg)
    sys.stdout.flush()


def run_monitor(args):
    cfg = Config(
        sample_rate=args.sample_rate,
        channels=1,
        frame_duration=args.frame_duration,
        calibrate_seconds=args.calibrate_seconds,
        cooldown_seconds=args.cooldown,
        endpoint_path=args.endpoint,
    )

    hp_sos = make_highpass_sos(cfg.sample_rate, cutoff_hz=80.0)
    tracker = NoiseFloorTracker(cfg)
    classifier = FrameClassifier(cfg)
    aggregator = EventAggregator(cfg)

    token = load_token(args)
    if not token and not args.test:
        log.error("No token provided. Use --token, --token-file, or --test mode.")
        sys.exit(1)

    if args.device is not None:
        log.info("Using input device index: %s", args.device)

    calibration_frames = max(1, int(round(cfg.calibrate_seconds / cfg.frame_duration)))
    log.info("Starting monitor")
    log.info("Sample rate=%d Hz, frame=%.2fs, calibration=%.1fs, cooldown=%.1fs",
             cfg.sample_rate, cfg.frame_duration, cfg.calibrate_seconds, cfg.cooldown_seconds)

    with AudioStreamReader(cfg, device=args.device) as reader:
        # Calibration phase
        log.info("Calibration started. Keep the environment in its normal background state.")
        seen = 0
        while seen < calibration_frames:
            block = reader.read(timeout=2.0)
            if block is None:
                continue
            x = preprocess_audio(block, hp_sos)
            dbfs = safe_db(compute_rms(x))
            tracker.feed_calibration(dbfs)
            seen += 1
            progress = int((seen / calibration_frames) * 30)
            sys.stdout.write(f"\rCalibrating [{'#' * progress}{'.' * (30 - progress)}] {seen}/{calibration_frames}")
            sys.stdout.flush()
        print()
        tracker.finalize_calibration()

        log.info("Monitoring started. Press Ctrl+C to stop.")
        try:
            while True:
                block = reader.read(timeout=2.0)
                if block is None:
                    continue

                ts = time.time()
                x = preprocess_audio(block, hp_sos)
                frame = classifier.classify(ts, x, tracker.floor_dbfs, cfg.sample_rate)
                tracker.maybe_update(frame.dbfs, frame.total_score)
                frame.floor_dbfs = tracker.floor_dbfs
                frame.db_above_floor = frame.dbfs - tracker.floor_dbfs

                print_status(frame)

                event = aggregator.ingest(frame)
                if event is None:
                    continue

                print()
                if aggregator.in_cooldown():
                    remaining = cfg.cooldown_seconds - (time.time() - aggregator.last_sent_ts)
                    log.info(
                        "Event detected but in cooldown (%.0fs left): %s / %s",
                        max(0.0, remaining),
                        event.event_type,
                        event.severity,
                    )
                    continue

                log.warning(
                    "Acoustic incident: type=%s severity=%s confidence=%.2f duration=%.1fs peak_above_floor=%.1fdB",
                    event.event_type,
                    event.severity,
                    event.confidence,
                    event.duration_sec,
                    event.peak_above_floor_db,
                )

                if send_report(args.server, token, event, cfg, dry_run=args.test):
                    aggregator.mark_sent()

        except KeyboardInterrupt:
            print()
            pending = aggregator.flush()
            if pending and not aggregator.in_cooldown():
                log.info("Flushing final pending event before shutdown")
                send_report(args.server, token, pending, cfg, dry_run=args.test)
            log.info("Stopped by user")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def list_input_devices():
    devices = sd.query_devices()
    for idx, d in enumerate(devices):
        if int(d["max_input_channels"]) > 0:
            print(f"[{idx}] {d['name']} (inputs={d['max_input_channels']}, sr={d['default_samplerate']})")


def test_microphone(device: Optional[int], sample_rate: int):
    try:
        duration = 0.5
        frames = int(sample_rate * duration)
        rec = sd.rec(frames, samplerate=sample_rate, channels=1, dtype="float32", device=device, blocking=True)
        peak = float(np.max(np.abs(rec)))
        log.info("Microphone OK. Test capture peak=%.5f", peak)
    except Exception as e:
        log.error("Cannot access microphone: %s", e)
        sys.exit(1)


def build_parser():
    parser = argparse.ArgumentParser(
        description="Robust acoustic incident monitor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Recommended use:
  1) Start in --test mode
  2) Let calibration run in the normal room background
  3) Create a few test sounds (normal speech, clap, shout, door slam)
  4) Adjust endpoint / cooldown if needed
        """,
    )
    parser.add_argument("--server", "-s", default="http://localhost:8000",
                        help="Server base URL")
    parser.add_argument("--endpoint", default="/api/behavior/report",
                        help="POST endpoint path (default: /api/behavior/report)")
    parser.add_argument("--token-file", "-t",
                        default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".behavior_agent_token"),
                        help="Path to token file (default: ../.behavior_agent_token)")
    parser.add_argument("--token", help="Token value directly (overrides --token-file)")
    parser.add_argument("--test", action="store_true",
                        help="Dry-run mode: do not send network reports")
    parser.add_argument("--device", type=int, default=None,
                        help="Input device index")
    parser.add_argument("--list-devices", action="store_true",
                        help="List input devices and exit")
    parser.add_argument("--sample-rate", type=int, default=16000,
                        help="Sample rate in Hz (default: 16000)")
    parser.add_argument("--frame-duration", type=float, default=0.20,
                        help="Frame duration in seconds (default: 0.20)")
    parser.add_argument("--calibrate-seconds", type=float, default=8.0,
                        help="Initial calibration duration in seconds (default: 8)")
    parser.add_argument("--cooldown", type=float, default=20.0,
                        help="Cooldown between reports in seconds (default: 20)")
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.list_devices:
        list_input_devices()
        return

    test_microphone(args.device, args.sample_rate)
    run_monitor(args)


if __name__ == "__main__":
    main()
