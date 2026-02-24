"""
Anime Code Adventures - Sensei Node Server v3.0
================================================
Features:
- SQLite database for users and progress
- JWT tokens with expiration (bcrypt + python-jose)
- Rate limiting for auth endpoints (slowapi)
- Achievement system  
- Admin endpoints for student management
- Submission tracking for Scratch reviews
- Comprehensive logging system
"""

import json
import asyncio
import os
import sys
import random
import secrets
import sqlite3
import logging
import traceback
import subprocess
import io
import tokenize
import keyword
import time
import html
import tempfile
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Optional, List
from contextlib import contextmanager
from logging.handlers import RotatingFileHandler

from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, Header, Query, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from starlette.background import BackgroundTask
from pydantic import BaseModel, validator
import bcrypt
from jose import jwt, JWTError
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import re
import shutil
import zipfile
import uuid
import hashlib
from pathlib import Path

# ==================== SECURITY CONFIG ====================

# IMPORTANT: Use a stable secret across restarts (env var recommended).
JWT_SECRET = os.getenv("PANDORA_JWT_SECRET") or ""
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 24
# Emergency fallback for constrained hosting:
# skip DB-backed session revocation and rely on JWT expiry only.
STATELESS_AUTH = (os.getenv("PANDORA_STATELESS_AUTH") or "0") == "1"

# Rate limiter
limiter = Limiter(key_func=get_remote_address)

# Allowed origins (configurable)
ALLOWED_ORIGINS = [
    "http://localhost:*",
    "http://127.0.0.1:*",
    "http://192.168.*.*:*",
    "file://*"
]
TRUST_PROXY_HEADERS = (os.getenv("PANDORA_TRUST_PROXY_HEADERS") or "0") == "1"
DISPLAY_NAME_MAX_LEN = 50

# ==================== LOGGING SETUP ====================

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

# Main application logger
logger = logging.getLogger("academy")
logger.setLevel(logging.DEBUG)

# Security audit logger (separate)
security_logger = logging.getLogger("academy.security")
security_logger.setLevel(logging.INFO)

# File handler with rotation (max 10MB, keep 5 backups)
file_handler = RotatingFileHandler(
    f"{LOG_DIR}/academy.log",
    maxBytes=10*1024*1024,  # 10 MB
    backupCount=5,
    encoding="utf-8"
)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter(
    "[%(asctime)s] %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
))

# Security audit log (SIEM-compatible JSON-like format)
security_handler = RotatingFileHandler(
    f"{LOG_DIR}/security.log",
    maxBytes=10*1024*1024,
    backupCount=20,  # Keep more security logs
    encoding="utf-8"
)
security_handler.setLevel(logging.INFO)
security_handler.setFormatter(logging.Formatter(
    '[%(asctime)s] %(levelname)s | %(message)s',
    datefmt="%Y-%m-%d %H:%M:%S"
))
security_logger.addHandler(security_handler)

# Console handler (minimal output)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.WARNING)
console_handler.setFormatter(logging.Formatter(
    "%(levelname)s: %(message)s"
))

logger.addHandler(file_handler)
logger.addHandler(console_handler)

# Suppress uvicorn access logs to reduce noise
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

def log_security(event_type: str, user: str = "SYSTEM", details: str = "", ip: str = "unknown"):
    """Helper to log security events."""
    msg = f"[{event_type}] User: {user} | {details} | IP: {ip}"
    security_logger.info(msg)

# ==================== SECURITY EVENT TYPES ====================
class SecurityEvent:
    # Authentication events
    LOGIN_SUCCESS = "AUTH_LOGIN_SUCCESS"
    LOGIN_FAILED = "AUTH_LOGIN_FAILED"
    LOGIN_RATE_LIMITED = "AUTH_RATE_LIMITED"
    LOGOUT = "AUTH_LOGOUT"
    TOKEN_EXPIRED = "AUTH_TOKEN_EXPIRED"
    TOKEN_INVALID = "AUTH_TOKEN_INVALID"
    
    # Admin events
    ADMIN_LOGIN = "ADMIN_LOGIN"
    ADMIN_CREATE_USER = "ADMIN_CREATE_USER"
    ADMIN_DELETE_USER = "ADMIN_DELETE_USER"
    ADMIN_RESET_PASSWORD = "ADMIN_RESET_PASSWORD"
    ADMIN_AWARD_XP = "ADMIN_AWARD_XP"
    ADMIN_REVIEW_SUBMISSION = "ADMIN_REVIEW_SUBMISSION"
    ADMIN_SET_PRIORITIES = "ADMIN_SET_PRIORITIES"
    ADMIN_CREATE_REWARD = "ADMIN_CREATE_REWARD"
    ADMIN_CREATE_EVENT = "ADMIN_CREATE_EVENT"
    
    # User events  
    USER_REGISTER = "USER_REGISTER"
    USER_COMPLETE_TASK = "USER_COMPLETE_TASK"
    USER_SUBMIT_WORK = "USER_SUBMIT_WORK"
    USER_PROFILE_UPDATE = "USER_PROFILE_UPDATE"
    USER_ACHIEVEMENT = "USER_ACHIEVEMENT"
    
    # Security threats
    THREAT_SQL_INJECTION = "THREAT_SQL_INJECTION"
    THREAT_XSS_ATTEMPT = "THREAT_XSS_ATTEMPT"
    THREAT_PATH_TRAVERSAL = "THREAT_PATH_TRAVERSAL"
    THREAT_BRUTE_FORCE = "THREAT_BRUTE_FORCE"
    THREAT_UNAUTHORIZED_ACCESS = "THREAT_UNAUTHORIZED"

def get_client_ip(request) -> str:
    """Extract client IP from request, handling proxies."""
    forwarded = request.headers.get("X-Forwarded-For")
    if TRUST_PROXY_HEADERS and forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

def log_security_event(event: str, request=None, user_id: int = None, 
                       username: str = None, details: str = "", 
                       severity: str = "INFO"):
    """Log security event in SIEM-compatible format."""
    ip = get_client_ip(request) if request else "internal"
    user_agent = request.headers.get("User-Agent", "unknown")[:100] if request else "internal"
    
    log_entry = (
        f"event={event} | "
        f"ip={ip} | "
        f"user_id={user_id or 'none'} | "
        f"username={username or 'anonymous'} | "
        f"user_agent={user_agent} | "
        f"details={details}"
    )
    
    if severity == "CRITICAL":
        security_logger.critical(log_entry)
    elif severity == "WARNING":
        security_logger.warning(log_entry)
    else:
        security_logger.info(log_entry)
    
    # Also log threats to main logger
    if event.startswith("THREAT_"):
        logger.warning(f"🚨 SECURITY: {log_entry}")

def log_action(user_id: int, username: str, action: str, details: str = ""):
    """Log user action for audit trail."""
    logger.info(f"ACTION | user_id={user_id} user={username} | {action} | {details}")

def log_error(context: str, error: Exception):
    """Log error with traceback."""
    logger.error(f"ERROR | {context} | {str(error)}\n{traceback.format_exc()}")

def detect_threats(text: str) -> list:
    """Detect potential attack patterns in input."""
    threats = []
    text_lower = text.lower()
    
    # SQL injection patterns
    sql_patterns = ["'--", "'; drop", "union select", "1=1", "or 1=", "' or '"]
    if any(p in text_lower for p in sql_patterns):
        threats.append(SecurityEvent.THREAT_SQL_INJECTION)
    
    # XSS patterns
    xss_patterns = ["<script", "javascript:", "onerror=", "onload=", "<img src"]
    if any(p in text_lower for p in xss_patterns):
        threats.append(SecurityEvent.THREAT_XSS_ATTEMPT)
    
    # Path traversal  
    if "../" in text or "..%2f" in text_lower or "..\\" in text:
        threats.append(SecurityEvent.THREAT_PATH_TRAVERSAL)
    
    return threats

# ==================== DATABASE ====================

DATABASE = "academy.db"
SQLITE_TIMEOUT_S = float(os.getenv("PANDORA_SQLITE_TIMEOUT_S", "8.0"))
SQLITE_BUSY_TIMEOUT_MS = int(os.getenv("PANDORA_SQLITE_BUSY_TIMEOUT_MS", "3000"))
AUTH_TRACE = (os.getenv("PANDORA_AUTH_TRACE") or "0") == "1"


def _auth_trace(message: str, *args):
    if AUTH_TRACE:
        logger.warning("AUTH_TRACE " + message, *args)

@contextmanager
def get_db():
    """Database connection context manager."""
    conn = sqlite3.connect(DATABASE, timeout=max(1.0, SQLITE_TIMEOUT_S), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(f"PRAGMA busy_timeout = {max(500, SQLITE_BUSY_TIMEOUT_MS)}")
    except sqlite3.Error:
        # Best-effort; don't fail app startup for PRAGMA issues.
        pass
    try:
        yield conn
    finally:
        conn.close()

def _sync_ranks(cursor):
    """Replace ranks table with full professional progression (30 tiers, up to level 1000).

    XP thresholds use progressive formula: total_xp(L) = 25 * L * (L - 1).
    """
    ranks_data = [
        # (name,              name_ru,                  min_xp,    emoji,  color)
        # --- Tier 0-1: Тень-Посвящение (Levels 1-5) ---
        ("Shadow Initiate",   "Тень-Посвящённый",       0,         "🗡️",   "#4ade80"),   # Level 1
        ("Eagle Bearer",      "Носитель Орла",          50,        "🦅",   "#86efac"),   # Level 2
        # --- Tier 2: Скрытые клинки (Levels 5-10) ---
        ("Hidden Blade",      "Скрытый Клинок",         500,       "🔪",   "#60a5fa"),   # Level 5
        ("Rift Walker",       "Странник Разлома",       2250,      "🌀",   "#93c5fd"),   # Level 10
        # --- Tier 3: Восхождение (Levels 15-25) ---
        ("Soul Keeper",       "Хранитель Душ",          5250,      "👁️",   "#a78bfa"),   # Level 15
        ("Gryphon Knight",    "Рыцарь Грифона",         9500,      "🦅",   "#c4b5fd"),   # Level 20
        ("Storm Warden",      "Страж Бури",             15000,     "⛈️",   "#818cf8"),   # Level 25
        # --- Tier 4: Тайные стражи (Levels 30-50) ---
        ("Arcane Sentinel",   "Тайный Страж",           21750,     "🔮",   "#f472b6"),   # Level 30
        ("Blood Templar",     "Кровавый Храмовник",     38000,     "⚔️",   "#fb7185"),   # Level 40
        ("Astral Blade",      "Астральный Клинок",      61250,     "✨",   "#fbbf24"),   # Level 50
        # --- Tier 5: Высшие (Levels 60-100) ---
        ("Dragon Rider",      "Наездник Драконов",      88500,     "🐉",   "#fcd34d"),   # Level 60
        ("Shadow Monarch",    "Теневой Монарх",         119750,    "👑",   "#f97316"),   # Level 70
        ("Archmage",          "Архимаг",                160000,    "📜",   "#fb923c"),   # Level 80
        ("Phoenix Lord",      "Повелитель Фениксов",    200250,    "🔥",   "#ea580c"),   # Level 90
        ("Archangel",         "Архангел",               247500,    "🏆",   "#ef4444"),   # Level 100
        # --- Tier 6: Легенда (Levels 120-200) ---
        ("Void Emperor",      "Император Пустоты",      357000,    "🏛️",   "#dc2626"),   # Level 120
        ("Seraph Sovereign",  "Серафим-Властелин",      497500,    "🎭",   "#e11d48"),   # Level 142
        ("Ascended Lich",     "Вознесённый Лич",        995000,    "👑",   "#be123c"),   # Level 200
        # --- Tier 7: Мифический (Levels 250-400) ---
        ("Azure Dragon",      "Лазурный Дракон",        1556250,   "🐉",   "#9333ea"),   # Level 250
        ("Chaos Overlord",    "Повелитель Хаоса",       2495000,   "⚡",   "#7c3aed"),   # Level 317
        ("Titan of Erathia",  "Титан Эрафии",           3990000,   "🔱",   "#6d28d9"),   # Level 400
        # --- Tier 8: Бессмертный (Levels 500-700) ---
        ("Dimension Lord",    "Повелитель Измерений",   6237500,   "✨",   "#c026d3"),   # Level 500
        ("Isu Ascendant",     "Вознесённый Ису",        8722500,   "💫",   "#a21caf"),   # Level 591
        ("Precursor God",     "Бог-Предтеча",           12247500,  "🌌",   "#86198f"),   # Level 700
        # --- Tier 9: Абсолют (Levels 800-1000) ---
        ("World Eater",       "Пожиратель Миров",       15980000,  "🌠",   "#b91c1c"),   # Level 800
        ("Creator Genesis",   "Создатель-Генезис",      20247500,  "💎",   "#991b1b"),   # Level 900
        ("Pandora Architect", "Архитектор Пандоры",      24975000,  "🌟",   "#fef08a"),   # Level 1000
    ]

    cursor.execute("DELETE FROM ranks")
    cursor.executemany(
        "INSERT INTO ranks (name, name_ru, min_xp, badge_emoji, color) VALUES (?, ?, ?, ?, ?)",
        ranks_data,
    )


def init_db():
    """Initialize database tables."""
    with get_db() as conn:
        cursor = conn.cursor()
        # WAL mode dramatically reduces reader/writer blocking on SQLite.
        try:
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA wal_autocheckpoint=1000")
        except sqlite3.Error:
            pass
        
        # Users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                display_name TEXT NOT NULL,
                role TEXT DEFAULT 'student',
                xp INTEGER DEFAULT 0,
                level INTEGER DEFAULT 1,
                avatar_key TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Completed tasks
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS completed_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                task_id TEXT NOT NULL,
                completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                solution TEXT,
                xp_earned INTEGER DEFAULT 0,
                is_valid INTEGER DEFAULT 1,
                code_simhash TEXT,
                comment_bonus_status TEXT DEFAULT 'none', -- none|pending|approved|rejected
                comment_bonus_proposed INTEGER DEFAULT 0,
                comment_bonus_awarded INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(id),
                UNIQUE(user_id, task_id)
            )
        """)
        
        # Submissions (manual review, integrity review, Scratch artifacts)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                task_id TEXT NOT NULL,
                category TEXT,
                tier TEXT,
                code TEXT,
                code_language TEXT,
                code_hash TEXT,
                code_simhash TEXT,
                content TEXT,
                link TEXT,
                auto_result TEXT,
                plagiarism_score REAL,
                flags TEXT,
                comment_bonus_proposed INTEGER DEFAULT 0,
                comment_bonus_awarded INTEGER DEFAULT 0,
                reviewer_id INTEGER,
                review_reason TEXT,
                status TEXT DEFAULT 'pending',
                feedback TEXT,
                score INTEGER,
                max_score INTEGER DEFAULT 10,
                submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                reviewed_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        
        # Sessions
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                ip TEXT,
                user_agent TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        
        # Ranks table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ranks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                name_ru TEXT NOT NULL,
                min_xp INTEGER NOT NULL,
                badge_emoji TEXT NOT NULL,
                color TEXT NOT NULL
            )
        """)
        
        # Events table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                bonus_type TEXT NOT NULL,
                bonus_value REAL NOT NULL,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # User stats table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_stats (
                user_id INTEGER PRIMARY KEY,
                total_quests INTEGER DEFAULT 0,
                streak_days INTEGER DEFAULT 0,
                best_streak INTEGER DEFAULT 0,
                last_active DATE,
                avatar_data TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        
        # User learning priorities table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_priorities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                scratch_priority INTEGER DEFAULT 25,
                frontend_priority INTEGER DEFAULT 25,
                javascript_priority INTEGER DEFAULT 25,
                python_priority INTEGER DEFAULT 25,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        
        # Rewards table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rewards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                icon TEXT NOT NULL,
                title TEXT NOT NULL,
                comment TEXT,
                awarded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                awarded_by INTEGER,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (awarded_by) REFERENCES users(id)
            )
        """)
        
        # XP log for progress tracking
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS xp_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                xp_change INTEGER NOT NULL,
                reason TEXT,
                task_id TEXT,
                logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        
        # Achievements definition table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS achievements (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                name_ru TEXT NOT NULL,
                description TEXT NOT NULL,
                icon TEXT NOT NULL,
                condition_type TEXT NOT NULL,
                condition_value INTEGER NOT NULL,
                xp_bonus INTEGER DEFAULT 0,
                rarity TEXT DEFAULT 'common'
            )
        """)
        
        # User achievements (unlocked)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_achievements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                achievement_id TEXT NOT NULL,
                unlocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (achievement_id) REFERENCES achievements(id),
                UNIQUE(user_id, achievement_id)
            )
        """)
        
        # Chat messages table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id INTEGER NOT NULL,
                message TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (sender_id) REFERENCES users(id)
            )
        """)

        # Guild chat messages
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS guild_chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                sender_id INTEGER NOT NULL,
                message TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE,
                FOREIGN KEY (sender_id) REFERENCES users(id)
            )
        """)
        
        # XP history for progress graph
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS xp_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                xp_amount INTEGER NOT NULL,
                total_xp INTEGER NOT NULL,
                source TEXT NOT NULL,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        # Verification/attempt ledger (anti-fraud + analytics)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS task_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                task_id TEXT NOT NULL,
                category TEXT,
                tier TEXT,
                code TEXT,
                code_language TEXT,
                code_hash TEXT,
                code_simhash TEXT,
                result_json TEXT,
                passed INTEGER,
                runtime_ms INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        # Security-grade audit log for XP-affecting and review actions
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor_user_id INTEGER,
                actor_username TEXT,
                action TEXT NOT NULL,
                target_user_id INTEGER,
                target_task_id TEXT,
                delta_xp INTEGER,
                meta_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Daily missions tracking
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_missions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                mission_type TEXT NOT NULL,
                progress INTEGER DEFAULT 0,
                target INTEGER NOT NULL,
                claimed INTEGER DEFAULT 0,
                xp_reward INTEGER NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id),
                UNIQUE(user_id, date, mission_type)
            )
        """)
        
        # Bonus quests (10% spawn chance after completion)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bonus_quests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                task_id TEXT NOT NULL,
                xp_multiplier REAL DEFAULT 1.5,
                expires_at TIMESTAMP NOT NULL,
                claimed INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        
        # Paste permission requests
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS paste_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                task_id TEXT NOT NULL,
                task_title TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                resolved_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        # Homework sets assigned by admin to students.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS homework_sets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                created_by INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                deadline_at TIMESTAMP NOT NULL,
                status TEXT DEFAULT 'active',
                FOREIGN KEY (created_by) REFERENCES users(id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS homework_set_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                homework_set_id INTEGER NOT NULL,
                task_id TEXT NOT NULL,
                task_xp INTEGER NOT NULL,
                FOREIGN KEY (homework_set_id) REFERENCES homework_sets(id) ON DELETE CASCADE,
                UNIQUE(homework_set_id, task_id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS homework_targets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                homework_set_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                penalty_applied INTEGER DEFAULT 0,
                penalty_amount INTEGER DEFAULT 0,
                penalty_applied_at TIMESTAMP,
                notified INTEGER DEFAULT 0,
                notified_at TIMESTAMP,
                FOREIGN KEY (homework_set_id) REFERENCES homework_sets(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id),
                UNIQUE(homework_set_id, user_id)
            )
        """)

        # ========== GUILD SYSTEM ==========
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS guilds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                description TEXT DEFAULT '',
                avatar_emoji TEXT DEFAULT '🛡️',
                created_by INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                disbanded_at TIMESTAMP,
                FOREIGN KEY (created_by) REFERENCES users(id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS guild_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                role TEXT DEFAULT 'developer',
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (guild_id) REFERENCES guilds(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id),
                UNIQUE(user_id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS guild_titles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_guild_id INTEGER NOT NULL,
                to_guild_id INTEGER NOT NULL,
                title_text TEXT NOT NULL,
                effect_type TEXT NOT NULL,
                effect_value REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                FOREIGN KEY (from_guild_id) REFERENCES guilds(id) ON DELETE CASCADE,
                FOREIGN KEY (to_guild_id) REFERENCES guilds(id) ON DELETE CASCADE
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS guild_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS guild_invitations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                from_user_id INTEGER NOT NULL,
                to_user_id INTEGER NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                resolved_at TIMESTAMP,
                FOREIGN KEY (guild_id) REFERENCES guilds(id),
                FOREIGN KEY (from_user_id) REFERENCES users(id),
                FOREIGN KEY (to_user_id) REFERENCES users(id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS guild_member_titles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_guild_id INTEGER NOT NULL,
                to_user_id INTEGER NOT NULL,
                title_text TEXT NOT NULL,
                effect_type TEXT NOT NULL,
                effect_value REAL NOT NULL,
                effect_meta TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                FOREIGN KEY (from_guild_id) REFERENCES guilds(id) ON DELETE CASCADE,
                FOREIGN KEY (to_user_id) REFERENCES users(id)
            )
        """)

        # Migration: add avatar_url to guilds
        try:
            cursor.execute("ALTER TABLE guilds ADD COLUMN avatar_url TEXT DEFAULT NULL")
        except Exception:
            pass  # column already exists

        # Migration: add custom_role_name to guild_members
        try:
            cursor.execute("ALTER TABLE guild_members ADD COLUMN custom_role_name TEXT DEFAULT NULL")
        except Exception:
            pass  # column already exists

        # ========== TIME TRACKING ==========
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS time_tracking (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                total_seconds INTEGER DEFAULT 0,
                task_seconds INTEGER DEFAULT 0,
                alextype_seconds INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(id),
                UNIQUE(user_id, date)
            )
        """)

        # Performance indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_xp ON users(xp DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_stats_user ON user_stats(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_completed_tasks_user ON completed_tasks(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_completed_tasks_valid ON completed_tasks(user_id, is_valid)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_submissions_user_task_status ON submissions(user_id, task_id, status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_task_attempts_user_task_time ON task_attempts(user_id, task_id, created_at DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_messages_time ON chat_messages(created_at DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_paste_requests_status ON paste_requests(status, user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_achievements_user ON user_achievements(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_homework_sets_deadline ON homework_sets(deadline_at, status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_homework_targets_user ON homework_targets(user_id, homework_set_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_guilds_active ON guilds(disbanded_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_guild_members_guild ON guild_members(guild_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_guild_members_user ON guild_members(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_guild_titles_to ON guild_titles(to_guild_id, expires_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_guild_invitations_to ON guild_invitations(to_user_id, status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_guild_invitations_guild ON guild_invitations(guild_id, status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_guild_chat_guild ON guild_chat_messages(guild_id, created_at DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_guild_member_titles_user ON guild_member_titles(to_user_id, expires_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_guild_member_titles_guild ON guild_member_titles(from_guild_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_time_tracking_user_date ON time_tracking(user_id, date)")
        
        conn.commit()
        
        # Populate default achievements if empty
        cursor.execute("SELECT COUNT(*) FROM achievements")
        if cursor.fetchone()[0] == 0:
            achievements_data = [
                # First steps
                ("first_quest", "First Steps", "Первые шаги", "Complete your first quest", "🎯", "quests_completed", 1, 5, "common"),
                ("apprentice", "Apprentice", "Подмастерье", "Complete 5 quests", "📚", "quests_completed", 5, 10, "common"),
                ("journeyman", "Journeyman", "Странник", "Complete 10 quests", "🗺️", "quests_completed", 10, 20, "uncommon"),
                ("veteran", "Veteran", "Ветеран", "Complete 25 quests", "⚔️", "quests_completed", 25, 50, "rare"),
                ("master", "Master", "Мастер", "Complete 50 quests", "🏅", "quests_completed", 50, 100, "epic"),
                ("grandmaster", "Grandmaster", "Грандмастер", "Complete 100 quests", "👑", "quests_completed", 100, 200, "legendary"),
                # Streaks
                ("streak_3", "Dedicated", "Целеустремлённый", "3-day streak", "🔥", "streak_days", 3, 15, "common"),
                ("streak_7", "Persistent", "Упорный", "7-day streak", "💪", "streak_days", 7, 30, "uncommon"),
                ("streak_14", "Unstoppable", "Неудержимый", "14-day streak", "⚡", "streak_days", 14, 60, "rare"),
                ("streak_30", "Legend", "Легенда", "30-day streak", "🌟", "streak_days", 30, 150, "legendary"),
                # XP milestones
                ("xp_100", "Rising Star", "Восходящая звезда", "Earn 100 XP", "⭐", "total_xp", 100, 0, "common"),
                ("xp_500", "Shining Star", "Сияющая звезда", "Earn 500 XP", "🌟", "total_xp", 500, 0, "uncommon"),
                ("xp_1000", "Superstar", "Суперзвезда", "Earn 1000 XP", "✨", "total_xp", 1000, 0, "rare"),
                ("xp_5000", "Galaxy", "Галактика", "Earn 5000 XP", "🌌", "total_xp", 5000, 0, "legendary"),
                # Category specialists
                ("python_5", "Snake Charmer", "Заклинатель Змей", "Complete 5 Python quests", "🐍", "category_python", 5, 25, "uncommon"),
                ("js_5", "Script Wizard", "Маг Скриптов", "Complete 5 JavaScript quests", "⚡", "category_javascript", 5, 25, "uncommon"),
                ("frontend_5", "Pixel Artist", "Пиксельный Художник", "Complete 5 Frontend quests", "🎨", "category_frontend", 5, 25, "uncommon"),
                ("scratch_5", "Cat Whisperer", "Кошачий Шёпот", "Complete 5 Scratch quests", "🐱", "category_scratch", 5, 25, "uncommon"),
                # Tier completions
                ("tier_d_all", "D-Tier Hunter", "Охотник D-ранга", "Complete all D-tier quests", "🥉", "tier_d", 100, 50, "rare"),
                ("tier_c_all", "C-Tier Hunter", "Охотник C-ранга", "Complete all C-tier quests", "🥈", "tier_c", 100, 75, "rare"),
                ("tier_b_all", "B-Tier Hunter", "Охотник B-ранга", "Complete all B-tier quests", "🥇", "tier_b", 100, 100, "epic"),
                # Speed
                ("speedrun_3", "Quick Learner", "Быстрый Ученик", "Complete 3 quests in one day", "🏃", "daily_quests", 3, 20, "uncommon"),
            ]
            cursor.executemany(
                "INSERT INTO achievements (id, name, name_ru, description, icon, condition_type, condition_value, xp_bonus, rarity) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                achievements_data
            )
            conn.commit()
            print("✓ Achievements initialized")

        # Ensure achievements are up-to-date (names, new achievements, corrected thresholds)
        try:
            sync_achievements(cursor)
            conn.commit()
        except Exception as e:
            log_error("Achievement sync failed", e)
        
        # Add new columns to existing tables (safe migration)
        try:
            cursor.execute("ALTER TABLE submissions ADD COLUMN score INTEGER")
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        try:
            cursor.execute("ALTER TABLE submissions ADD COLUMN max_score INTEGER DEFAULT 10")
        except sqlite3.OperationalError:
            pass

        # New submission metadata (v2.0)
        for stmt in [
            "ALTER TABLE submissions ADD COLUMN category TEXT",
            "ALTER TABLE submissions ADD COLUMN tier TEXT",
            "ALTER TABLE submissions ADD COLUMN code TEXT",
            "ALTER TABLE submissions ADD COLUMN code_language TEXT",
            "ALTER TABLE submissions ADD COLUMN code_hash TEXT",
            "ALTER TABLE submissions ADD COLUMN code_simhash TEXT",
            "ALTER TABLE submissions ADD COLUMN auto_result TEXT",
            "ALTER TABLE submissions ADD COLUMN plagiarism_score REAL",
            "ALTER TABLE submissions ADD COLUMN flags TEXT",
            "ALTER TABLE submissions ADD COLUMN comment_bonus_proposed INTEGER DEFAULT 0",
            "ALTER TABLE submissions ADD COLUMN comment_bonus_awarded INTEGER DEFAULT 0",
            "ALTER TABLE submissions ADD COLUMN reviewer_id INTEGER",
            "ALTER TABLE submissions ADD COLUMN review_reason TEXT",
        ]:
            try:
                cursor.execute(stmt)
            except sqlite3.OperationalError:
                pass
        
        try:
            cursor.execute("ALTER TABLE completed_tasks ADD COLUMN solution TEXT")
        except sqlite3.OperationalError:
            pass
        
        try:
            cursor.execute("ALTER TABLE completed_tasks ADD COLUMN xp_earned INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass
        
        try:
            cursor.execute("ALTER TABLE completed_tasks ADD COLUMN is_valid INTEGER DEFAULT 1")
        except sqlite3.OperationalError:
            pass

        for stmt in [
            "ALTER TABLE completed_tasks ADD COLUMN code_simhash TEXT",
            "ALTER TABLE completed_tasks ADD COLUMN comment_bonus_status TEXT DEFAULT 'none'",
            "ALTER TABLE completed_tasks ADD COLUMN comment_bonus_proposed INTEGER DEFAULT 0",
            "ALTER TABLE completed_tasks ADD COLUMN comment_bonus_awarded INTEGER DEFAULT 0",
        ]:
            try:
                cursor.execute(stmt)
            except sqlite3.OperationalError:
                pass

        for stmt in [
            "ALTER TABLE sessions ADD COLUMN expires_at TIMESTAMP",
            "ALTER TABLE sessions ADD COLUMN ip TEXT",
            "ALTER TABLE sessions ADD COLUMN user_agent TEXT",
        ]:
            try:
                cursor.execute(stmt)
            except sqlite3.OperationalError:
                pass

        try:
            cursor.execute("ALTER TABLE users ADD COLUMN avatar_key TEXT")
        except sqlite3.OperationalError:
            pass

        # Online tracking: precise last-seen timestamp
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN last_seen_at TIMESTAMP")
        except sqlite3.OperationalError:
            pass
        
        conn.commit()
        
        # Populate / sync ranks (always update to latest progression)
        _sync_ranks(cursor)
        conn.commit()

        # Migration: recalculate all user levels with progressive formula
        import math as _math
        cursor.execute("SELECT id, xp FROM users")
        for u in cursor.fetchall():
            new_lvl = compute_level(u["xp"])
            cursor.execute("UPDATE users SET level = ? WHERE id = ? AND level != ?", (new_lvl, u["id"], new_lvl))
        conn.commit()
        print("✓ Ranks synced")
        
        # Create bootstrap admin if none exists (first run).
        # Prefer setting PANDORA_BOOTSTRAP_ADMIN_PASSWORD in production.
        cursor.execute("SELECT id FROM users WHERE role = 'admin' LIMIT 1")
        if not cursor.fetchone():
            desired_username = os.getenv("PANDORA_BOOTSTRAP_ADMIN_USER", "admin")
            desired_display = os.getenv("PANDORA_BOOTSTRAP_ADMIN_DISPLAY", "Sensei")
            password = os.getenv("PANDORA_BOOTSTRAP_ADMIN_PASSWORD") or secrets.token_urlsafe(12)

            username = desired_username
            cursor.execute("SELECT 1 FROM users WHERE username = ?", (username,))
            if cursor.fetchone():
                username = f"{desired_username}_{secrets.token_hex(2)}"

            password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
            cursor.execute(
                "INSERT INTO users (username, password_hash, display_name, role) VALUES (?, ?, ?, ?)",
                (username, password_hash, desired_display, "admin"),
            )
            conn.commit()
            logger.warning("✓ Bootstrap admin created: %s / %s  (change ASAP)", username, password)

# NOTE: DB initialization runs in the FastAPI startup event.

# ==================== HELPERS ====================

def hash_password(password: str) -> str:
    """Hash password with bcrypt (secure, salted)."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed: str) -> bool:
    """Verify password against bcrypt hash. Also supports legacy SHA256 for migration."""
    _auth_trace("verify_password start hash_prefix=%s", (hashed or "")[:7])
    # Guard against pathological bcrypt costs that can freeze single-worker hosts.
    if isinstance(hashed, str) and hashed.startswith("$2"):
        try:
            parts = hashed.split("$")
            cost = int(parts[2])
            _auth_trace("verify_password bcrypt_cost=%s", cost)
            if cost > 14:
                logger.error("Refusing bcrypt hash with excessive cost=%s", cost)
                return False
        except Exception:
            pass
    try:
        ok = bcrypt.checkpw(password.encode(), hashed.encode())
        _auth_trace("verify_password done ok=%s", ok)
        return ok
    except ValueError:
        # Legacy SHA256 fallback for existing users
        import hashlib
        ok = hashlib.sha256(password.encode()).hexdigest() == hashed
        _auth_trace("verify_password legacy_sha256 ok=%s", ok)
        return ok

def compute_level(total_xp: int) -> int:
    """Compute level from total XP using progressive curve.

    Each level L requires 50*L XP to advance to level L+1.
    Total XP needed for level L:  25 * L * (L - 1)
    Inverse:  L = floor((1 + sqrt(1 + 4*xp/25)) / 2)

    Examples:
        Level  1 =       0 XP
        Level  2 =      50 XP
        Level  5 =     500 XP
        Level 10 =   2,250 XP
        Level 20 =   9,500 XP
        Level 50 =  61,250 XP
        Level100 = 247,500 XP
        Level200 = 995,000 XP
    """
    import math
    safe_xp = max(0, int(total_xp or 0))
    if safe_xp == 0:
        return 1
    level = int((1 + math.sqrt(1 + 4 * safe_xp / 25)) / 2)
    # Clamp: verify we haven't overshot due to floating point
    while 25 * level * (level - 1) > safe_xp:
        level -= 1
    return max(1, level)

def apply_xp_change(cursor, user_id: int, delta_xp: int, reason: str, task_id: str = None) -> tuple[int, int]:
    """
    Apply an XP delta and keep `users.level` consistent.

    Returns (new_total_xp, new_level).
    """
    delta = int(delta_xp or 0)

    # --- Guild XP bonus ---
    if delta > 0:
        try:
            cursor.execute(
                "SELECT gm.role FROM guild_members gm "
                "JOIN guilds g ON g.id = gm.guild_id "
                "WHERE gm.user_id = ? AND g.disbanded_at IS NULL",
                (user_id,),
            )
            gm_row = cursor.fetchone()
            if gm_row:
                bonus_pct = {"president": 0.10, "chairman": 0.05}.get(gm_row["role"], 0)
                if bonus_pct:
                    delta = int(delta * (1 + bonus_pct))
            # Guild title debuff (guild-level)
            cursor.execute(
                "SELECT gt.effect_value FROM guild_titles gt "
                "JOIN guild_members gm ON gm.guild_id = gt.to_guild_id "
                "WHERE gm.user_id = ? AND gt.expires_at > CURRENT_TIMESTAMP",
                (user_id,),
            )
            for title_row in cursor.fetchall():
                delta = int(delta * (1 + title_row["effect_value"]))
            # Per-member titles (guild_member_titles)
            cursor.execute(
                "SELECT mt.effect_type, mt.effect_value, mt.effect_meta FROM guild_member_titles mt "
                "WHERE mt.to_user_id = ? AND mt.expires_at > CURRENT_TIMESTAMP",
                (user_id,),
            )
            for mt in cursor.fetchall():
                etype = mt["effect_type"]
                if etype == "xp_buff":
                    delta = int(delta * (1 + mt["effect_value"]))
                elif etype == "xp_debuff":
                    delta = int(delta * (1 + mt["effect_value"]))
                elif etype == "xp_cooldown":
                    # Check if user earned XP in last N hours
                    cooldown_h = int(mt["effect_value"] or 24)
                    cursor.execute(
                        "SELECT id FROM xp_log WHERE user_id = ? AND xp_change > 0 "
                        "AND logged_at > datetime('now', ? || ' hours')",
                        (user_id, str(-cooldown_h)),
                    )
                    if cursor.fetchone():
                        delta = 0  # XP frozen
                elif etype == "category_block":
                    import json as _json
                    try:
                        meta = _json.loads(mt["effect_meta"] or "{}")
                        blocked_cat = meta.get("category", "")
                        if task_id and blocked_cat:
                            # Check if this task belongs to the blocked category
                            tasks_data = load_tasks()
                            for t in tasks_data.get("tasks", []):
                                if t.get("id") == task_id and (t.get("category") or "").lower() == blocked_cat.lower():
                                    delta = 0
                                    break
                    except Exception:
                        pass
        except Exception:
            pass  # guild tables may not exist yet on first run

    cursor.execute("SELECT xp FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")

    new_xp = max(0, int(row["xp"] or 0) + delta)
    new_level = compute_level(new_xp)

    cursor.execute("UPDATE users SET xp = ?, level = ? WHERE id = ?", (new_xp, new_level, user_id))
    cursor.execute(
        "INSERT INTO xp_log (user_id, xp_change, reason, task_id) VALUES (?, ?, ?, ?)",
        (user_id, delta, reason, task_id),
    )
    return new_xp, new_level

def sync_achievements(cursor) -> None:
    """
    Ensure baseline achievements exist and have correct, Russian-first copy.

    Notes:
    - This is intentionally idempotent (safe to call at startup).
    - We avoid deleting achievements to preserve history.
    """
    tasks_data = load_tasks()
    tasks = tasks_data.get("tasks", [])

    tier_totals = Counter((t.get("tier") or "D") for t in tasks)
    category_totals = Counter((t.get("category") or "unknown") for t in tasks)

    desired = [
        # Core progression
        ("first_quest", "First Blood", "Первая кровь", "Завершите свой первый квест.", "🗡️", "quests_completed", 1, 5, "common"),
        ("apprentice", "Apprentice", "Подмастерье", "Завершите 5 квестов.", "📚", "quests_completed", 5, 10, "common"),
        ("journeyman", "Journeyman", "Странник", "Завершите 10 квестов.", "🗺️", "quests_completed", 10, 20, "uncommon"),
        ("veteran", "Veteran", "Ветеран", "Завершите 25 квестов.", "⚔️", "quests_completed", 25, 50, "rare"),
        ("master", "Master", "Мастер", "Завершите 50 квестов.", "🏅", "quests_completed", 50, 100, "epic"),
        ("grandmaster", "Grandmaster", "Грандмастер", "Завершите 100 квестов.", "👑", "quests_completed", 100, 200, "legendary"),

        # Streaks
        ("streak_3", "Dedicated", "Целеустремлённый", "Учитесь 3 дня подряд.", "🔥", "streak_days", 3, 15, "common"),
        ("streak_7", "Streak Master", "Мастер страйка", "Учитесь 7 дней подряд.", "🔥", "streak_days", 7, 30, "uncommon"),
        ("streak_14", "Unstoppable", "Неудержимый", "Учитесь 14 дней подряд.", "⚡", "streak_days", 14, 60, "rare"),
        ("streak_30", "Legend", "Легенда", "Учитесь 30 дней подряд.", "🌟", "streak_days", 30, 150, "legendary"),

        # XP / Levels
        ("xp_100", "Rising Star", "Восходящая звезда", "Наберите 100 XP.", "⭐", "total_xp", 100, 0, "common"),
        ("xp_500", "Shining Star", "Сияющая звезда", "Наберите 500 XP.", "🌟", "total_xp", 500, 0, "uncommon"),
        ("xp_1000", "Superstar", "Суперзвезда", "Наберите 1000 XP.", "✨", "total_xp", 1000, 0, "rare"),
        ("xp_5000", "Galaxy", "Галактика", "Наберите 5000 XP.", "🌌", "total_xp", 5000, 0, "legendary"),
        ("level_10", "Level 10", "Уровень 10", "Достигните 10 уровня.", "🌠", "level", 10, 25, "uncommon"),
        ("level_50", "Level 50", "Уровень 50", "Достигните 50 уровня.", "👑", "level", 50, 200, "legendary"),

        # Category specialists
        ("python_5", "Snake Charmer", "Охотник на гоблинов", "Завершите 5 квестов Python.", "🐍", "category_python", 5, 25, "uncommon"),
        ("python_10", "Python Slayer", "Истребитель гоблинов", "Завершите 10 квестов Python.", "🐍", "category_python", 10, 50, "rare"),
        ("js_5", "Script Wizard", "Маг скриптов", "Завершите 5 квестов JavaScript.", "⚡", "category_javascript", 5, 25, "uncommon"),
        ("js_10", "Code Mage", "Маг кода", "Завершите 10 квестов JavaScript.", "🔮", "category_javascript", 10, 50, "rare"),
        ("frontend_5", "Pixel Artist", "Пиксельный художник", "Завершите 5 квестов Frontend.", "🎨", "category_frontend", 5, 25, "uncommon"),
        ("frontend_10", "Artificer", "Художник", "Завершите 10 квестов Frontend.", "🎨", "category_frontend", 10, 50, "rare"),
        ("scratch_5", "Cat Whisperer", "Кошачий шёпот", "Завершите 5 квестов Scratch.", "🐱", "category_scratch", 5, 25, "uncommon"),
        ("scratch_10", "Scratch Master", "Мастер Scratch", "Завершите 10 квестов Scratch.", "🐱", "category_scratch", 10, 50, "rare"),

        # Multi-profile / perfection
        ("multi_5_each", "Multiclass Warrior", "Многопрофильный воин", "Завершите по 5 квестов в каждой категории.", "🏆", "multi_category_min", 5, 75, "epic"),
        ("perfectionist", "Perfectionist", "Перфекционист", "Завершите 100% квестов хотя бы в одной категории.", "💯", "any_category_complete", 100, 150, "legendary"),

        # Tier completions (dynamic totals used by logic)
        ("tier_d_all", "D-Tier Hunter", "Охотник D-ранга", "Завершите все квесты ранга D.", "🥉", "tier_d", int(tier_totals.get("D", 0)), 50, "rare"),
        ("tier_c_all", "C-Tier Hunter", "Охотник C-ранга", "Завершите все квесты ранга C.", "🥈", "tier_c", int(tier_totals.get("C", 0)), 75, "rare"),
        ("tier_b_all", "B-Tier Hunter", "Охотник B-ранга", "Завершите все квесты ранга B.", "🥇", "tier_b", int(tier_totals.get("B", 0)), 100, "epic"),

        # Speed
        ("speedrun_3", "Quick Learner", "Быстрый ученик", "Завершите 3 квеста за один день.", "🏃", "daily_quests", 3, 20, "uncommon"),
        
        # Special / Fun
        ("chatterbox", "Chatterbox", "Болтун", "Слишком много говоришь в чате! 🤭", "🗣️", "special", 1, 0, "common"),
    ]

    # Upsert
    for (
        ach_id,
        name,
        name_ru,
        description,
        icon,
        condition_type,
        condition_value,
        xp_bonus,
        rarity,
    ) in desired:
        cursor.execute("SELECT id FROM achievements WHERE id = ?", (ach_id,))
        if cursor.fetchone():
            cursor.execute(
                """
                UPDATE achievements
                SET name = ?, name_ru = ?, description = ?, icon = ?, condition_type = ?, condition_value = ?, xp_bonus = ?, rarity = ?
                WHERE id = ?
                """,
                (name, name_ru, description, icon, condition_type, int(condition_value or 0), int(xp_bonus or 0), rarity, ach_id),
            )
        else:
            cursor.execute(
                """
                INSERT INTO achievements (id, name, name_ru, description, icon, condition_type, condition_value, xp_bonus, rarity)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (ach_id, name, name_ru, description, icon, condition_type, int(condition_value or 0), int(xp_bonus or 0), rarity),
            )

def create_jwt_token(user_id: int, username: str, role: str) -> tuple[str, int]:
    """Create JWT token with expiration. Returns (token, expires_at_epoch)."""
    expire = datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS)
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "exp": expire
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token, int(expire.timestamp())

def decode_jwt_token(token: str) -> Optional[dict]:
    """Decode and validate JWT token."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError:
        return None

def _token_hash(token: str) -> str:
    """Hash raw bearer tokens before storing in DB (prevents token reuse if DB leaks)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

def process_task_completion(
    cursor,
    user_id: int,
    task_id: str,
    base_xp: int,
    solution: str = None,
    code_simhash: str = None,
    is_retry: bool = False,
) -> dict:
    """
    Centralized logic to award XP, update level, handling streaks and events.
    On retry: if new XP > previous XP, awards delta only.
    Returns dict with update details.
    """
    # 1. Mark as completed (or handle retry)
    retry_delta = 0
    try:
        cursor.execute(
            "INSERT INTO completed_tasks (user_id, task_id, solution, xp_earned, code_simhash) VALUES (?, ?, ?, ?, ?)",
            (user_id, task_id, solution, base_xp, code_simhash)
        )
    except sqlite3.IntegrityError:
        if not is_retry:
            return {"status": "already_completed", "xp_earned": 0}
        # Retry: check if improvement
        cursor.execute(
            "SELECT xp_earned FROM completed_tasks WHERE user_id = ? AND task_id = ? AND is_valid != 0",
            (user_id, task_id),
        )
        prev_row = cursor.fetchone()
        prev_xp = int(prev_row["xp_earned"] or 0) if prev_row else 0
        # base_xp here is pre-bonus; we'll calculate final_xp below and compare there
        # For now, store it for comparison after bonus calculation
        retry_delta = -1  # sentinel: will be recalculated after bonuses

    # 3. Calculate Bonuses
    bonus_multiplier = 1.0
    cursor.execute("SELECT * FROM events WHERE is_active = 1")
    events = cursor.fetchall()
    
    # XP Multipliers
    for event in events:
        if event["bonus_type"] == "xp_multiplier":
            bonus_multiplier *= event["bonus_value"]
    
    # Streak Bonus
    cursor.execute("SELECT streak_days FROM user_stats WHERE user_id = ?", (user_id,))
    streak_row = cursor.fetchone()
    streak_days = streak_row["streak_days"] if streak_row else 0
    
    if streak_days > 0:
        for event in events:
            if event["bonus_type"] == "streak_bonus":
                bonus_multiplier += (streak_days * event["bonus_value"])
    
    # Penalty for multiple failed attempts (-5% per failed attempt, max -50%)
    cursor.execute(
        "SELECT COUNT(*) as cnt FROM task_attempts WHERE user_id = ? AND task_id = ? AND passed = 0",
        (user_id, task_id)
    )
    failed_attempts = cursor.fetchone()["cnt"]
    attempt_penalty = min(failed_attempts * 0.05, 0.50)  # Max 50% penalty
    
    final_xp = int(base_xp * bonus_multiplier * (1.0 - attempt_penalty))
    final_xp = max(1, final_xp)  # Minimum 1 XP

    # Handle retry: only award delta if improved
    if retry_delta == -1:
        # Recalculate with actual prev_xp
        cursor.execute(
            "SELECT xp_earned FROM completed_tasks WHERE user_id = ? AND task_id = ? AND is_valid != 0",
            (user_id, task_id),
        )
        prev_row = cursor.fetchone()
        prev_xp = int(prev_row["xp_earned"] or 0) if prev_row else 0
        if final_xp <= prev_xp:
            # No improvement — return without XP change
            return {
                "status": "retry_no_improvement",
                "xp_earned": 0,
                "prev_xp_earned": prev_xp,
                "new_xp_earned": final_xp,
                "bonus_applied": bonus_multiplier > 1.0,
                "new_xp": int(cursor.execute("SELECT xp FROM users WHERE id = ?", (user_id,)).fetchone()["xp"]),
                "new_level": int(cursor.execute("SELECT level FROM users WHERE id = ?", (user_id,)).fetchone()["level"]),
            }
        # Improved! Award only the delta
        retry_delta = final_xp - prev_xp
        final_xp = retry_delta  # award only the delta
        # Update the stored xp_earned to the new higher value
        cursor.execute(
            "UPDATE completed_tasks SET xp_earned = ?, solution = ?, code_simhash = ?, completed_at = CURRENT_TIMESTAMP WHERE user_id = ? AND task_id = ?",
            (prev_xp + retry_delta, solution, code_simhash, user_id, task_id),
        )
    
    # 4. Apply XP (keeps level consistent) + audit log
    reason = "task_retry_improvement" if retry_delta > 0 else "task_completed"
    new_xp, new_level = apply_xp_change(cursor, user_id, final_xp, reason, task_id)
    
    # Update xp_earned in completed_tasks with final (bonus-adjusted) value (first completion only)
    if retry_delta == 0:
        cursor.execute(
            "UPDATE completed_tasks SET xp_earned = ? WHERE user_id = ? AND task_id = ?",
            (final_xp, user_id, task_id)
        )
    
    # 5. Update Streak & Stats
    today = datetime.now().date().isoformat()
    cursor.execute(
        "INSERT OR IGNORE INTO user_stats (user_id, last_active) VALUES (?, ?)",
        (user_id, today)
    )
    cursor.execute(
        "SELECT last_active, streak_days, best_streak, total_quests FROM user_stats WHERE user_id = ?",
        (user_id,)
    )
    stats = cursor.fetchone()
    
    new_streak = stats["streak_days"]
    if stats["last_active"] != today:
        yesterday = (datetime.now().date() - __import__('datetime').timedelta(days=1)).isoformat()
        if stats["last_active"] == yesterday:
            new_streak += 1
        else:
            new_streak = 1
    
    # Increment total quests
    new_total = (stats["total_quests"] or 0) + 1
    best_streak = max(stats["best_streak"] or 0, new_streak)
    
    cursor.execute("""
        UPDATE user_stats 
        SET streak_days = ?, best_streak = ?, last_active = ?, total_quests = ? 
        WHERE user_id = ?
    """, (new_streak, best_streak, today, new_total, user_id))

    # Keep daily mission progress in sync with real task completions.
    _sync_daily_missions_progress(cursor, user_id)
    
    # Check for new achievements (may award XP bonuses)
    new_achievements = check_achievements(cursor, user_id, task_id, new_xp, new_total, new_streak)

    # Re-read in case achievements changed XP/level.
    cursor.execute("SELECT xp, level FROM users WHERE id = ?", (user_id,))
    final_user = cursor.fetchone()
    if final_user:
        new_xp = final_user["xp"]
        new_level = final_user["level"]

    return {
        "status": "success",
        "xp_earned": final_xp,
        "new_xp": new_xp,
        "new_level": new_level,
        "bonus_applied": bonus_multiplier > 1.0,
        "failed_attempts": failed_attempts,
        "attempt_penalty": round(attempt_penalty * 100),  # as percentage
        "new_achievements": new_achievements
    }

def check_achievements(cursor, user_id: int, task_id: str, total_xp: int, total_quests: int, streak_days: int) -> List[dict]:
    """Check and unlock achievements based on current stats. Returns list of newly unlocked achievements."""
    unlocked = []
    
    # Get all achievements user doesn't have yet
    cursor.execute("""
        SELECT a.* FROM achievements a
        WHERE a.id NOT IN (SELECT achievement_id FROM user_achievements WHERE user_id = ?)
    """, (user_id,))
    available = cursor.fetchall()
    
    # Get category completion counts
    cursor.execute("""
        SELECT task_id FROM completed_tasks WHERE user_id = ? AND is_valid != 0
    """, (user_id,))
    completed_tasks = [row["task_id"] for row in cursor.fetchall()]
    
    # Load tasks to check categories
    tasks_data = load_tasks()
    tasks_map = {t["id"]: t for t in tasks_data.get("tasks", [])}
    
    category_counts = {"python": 0, "javascript": 0, "frontend": 0, "scratch": 0}
    tier_counts = Counter()
    for tid in completed_tasks:
        task = tasks_map.get(tid, {})
        cat = task.get("category", "")
        tier = (task.get("tier") or "").upper()
        if cat in category_counts:
            category_counts[cat] += 1
        if tier:
            tier_counts[tier] += 1

    tier_totals = Counter((t.get("tier") or "").upper() for t in tasks_map.values())
    category_totals = Counter((t.get("category") or "") for t in tasks_map.values())
    
    # Check each achievement
    for ach in available:
        condition_type = ach["condition_type"]
        condition_value = ach["condition_value"]
        earned = False
        
        if condition_type == "quests_completed" and total_quests >= condition_value:
            earned = True
        elif condition_type == "streak_days" and streak_days >= condition_value:
            earned = True
        elif condition_type == "total_xp" and total_xp >= condition_value:
            earned = True
        elif condition_type == "category_python" and category_counts["python"] >= condition_value:
            earned = True
        elif condition_type == "category_javascript" and category_counts["javascript"] >= condition_value:
            earned = True
        elif condition_type == "category_frontend" and category_counts["frontend"] >= condition_value:
            earned = True
        elif condition_type == "category_scratch" and category_counts["scratch"] >= condition_value:
            earned = True
        elif condition_type == "daily_quests":
            # Check quests completed today
            cursor.execute("""
                SELECT COUNT(*) FROM completed_tasks 
                WHERE user_id = ? AND DATE(completed_at) = DATE('now')
            """, (user_id,))
            today_count = cursor.fetchone()[0]
            if today_count >= condition_value:
                earned = True
        elif condition_type == "level":
            if compute_level(total_xp) >= condition_value:
                earned = True
        elif condition_type.startswith("tier_"):
            tier_letter = condition_type.split("_", 1)[1].upper()
            total_in_tier = int(tier_totals.get(tier_letter, 0))
            if total_in_tier > 0 and int(tier_counts.get(tier_letter, 0)) >= total_in_tier:
                earned = True
        elif condition_type == "multi_category_min":
            # Complete at least N quests in each category
            if min(category_counts.values() or [0]) >= condition_value:
                earned = True
        elif condition_type == "any_category_complete":
            # 100% completion in any category
            for cat, total in category_totals.items():
                if not total:
                    continue
                if int(category_counts.get(cat, 0)) >= int(total):
                    earned = True
                    break
        
        if earned:
            # Unlock achievement
            try:
                cursor.execute(
                    "INSERT INTO user_achievements (user_id, achievement_id) VALUES (?, ?)",
                    (user_id, ach["id"])
                )
                # Award bonus XP if any
                if ach["xp_bonus"] > 0:
                    apply_xp_change(cursor, user_id, ach["xp_bonus"], f"achievement:{ach['id']}", task_id)
                
                unlocked.append({
                    "id": ach["id"],
                    "name": ach["name"],
                    "name_ru": ach["name_ru"],
                    "icon": ach["icon"],
                    "rarity": ach["rarity"],
                    "xp_bonus": ach["xp_bonus"]
                })
            except sqlite3.IntegrityError:
                pass  # Already has this achievement
    
    return unlocked

def verify_token(authorization: Optional[str] = Header(None)):
    """Verify JWT token from Authorization header and check session revocation."""
    if not authorization:
        return None

    if not authorization.startswith("Bearer "):
        return None

    token = authorization[len("Bearer "):].strip()
    _auth_trace("verify_token start")
    payload = decode_jwt_token(token)
    if not payload:
        _auth_trace("verify_token decode failed")
        return None

    now_epoch = int(datetime.now(timezone.utc).timestamp())
    token_hash = _token_hash(token)

    try:
        with get_db() as conn:
            cursor = conn.cursor()

            if not STATELESS_AUTH:
                # Enforce revocation via sessions table (logout deletes session).
                cursor.execute("SELECT user_id, expires_at FROM sessions WHERE token = ?", (token_hash,))
                session = cursor.fetchone()
                if not session:
                    _auth_trace("verify_token no session")
                    return None
                if int(session["user_id"]) != int(payload["sub"]):
                    _auth_trace("verify_token session mismatch")
                    return None
                expires_at = session["expires_at"]
                try:
                    if expires_at is not None and now_epoch > int(expires_at):
                        cursor.execute("DELETE FROM sessions WHERE token = ?", (token_hash,))
                        conn.commit()
                        return None
                except (TypeError, ValueError):
                    # If an old session row doesn't have a parseable expiry, treat it as invalid.
                    cursor.execute("DELETE FROM sessions WHERE token = ?", (token_hash,))
                    conn.commit()
                    return None

            # Get fresh user data from DB
            cursor.execute("SELECT * FROM users WHERE id = ?", (int(payload["sub"]),))
            user = cursor.fetchone()
            _auth_trace("verify_token done user_found=%s", bool(user))
            return dict(user) if user else None
    except sqlite3.OperationalError as e:
        message = str(e).lower()
        logger.error("verify_token sqlite operational error: %s", e)
        if STATELESS_AUTH:
            # Last-resort fallback: trust JWT claims to avoid full platform outage.
            _auth_trace("verify_token fallback to jwt claims due sqlite error")
            return {
                "id": int(payload.get("sub")),
                "username": payload.get("username", "user"),
                "display_name": payload.get("username", "user"),
                "role": payload.get("role", "student"),
                "xp": 0,
                "level": 1,
                "avatar_key": None,
            }
        if "locked" in message or "busy" in message:
            raise HTTPException(status_code=503, detail="Database is busy. Retry in a few seconds.")
        raise

def require_auth(authorization: Optional[str] = Header(None)):
    """Require valid JWT authentication."""
    user = verify_token(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated or token expired")
    return user

def require_admin(authorization: Optional[str] = Header(None)):
    """Require admin role."""
    user = require_auth(authorization)
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user

# ==================== MODELS ====================

class LoginRequest(BaseModel):
    username: str
    password: str


def _validate_display_name_value(value: str) -> str:
    name = (value or "").strip()
    if not name:
        raise ValueError("Display name cannot be empty")
    if len(name) > DISPLAY_NAME_MAX_LEN:
        raise ValueError(f"Display name must be at most {DISPLAY_NAME_MAX_LEN} characters")
    return name

class RegisterRequest(BaseModel):
    username: str
    password: str
    display_name: str
    
    @validator('password')
    def password_strength(cls, v):
        if len(v) < 6:
            raise ValueError('Password must be at least 6 characters')
        if v.lower() in ['password', '123456', 'qwerty', 'admin123']:
            raise ValueError('Password is too common')
        return v
    
    @validator('username')
    def username_valid(cls, v):
        if len(v) < 3:
            raise ValueError('Username must be at least 3 characters')
        if not re.match(r'^[a-zA-Z0-9_]+$', v):
            raise ValueError('Username can only contain letters, numbers, and underscores')
        return v

    @validator('display_name')
    def display_name_valid(cls, v):
        return _validate_display_name_value(v)

class TaskCompletion(BaseModel):
    task_id: str
    xp_earned: int

class TaskAttemptRequest(BaseModel):
    task_id: str
    code: str

class SubmissionRequest(BaseModel):
    task_id: str
    content: Optional[str] = None
    link: Optional[str] = None

class ReviewRequest(BaseModel):
    status: str  # 'approved' or 'rejected'
    score: Optional[int] = None  # 0-10, where 10 = full XP
    feedback: Optional[str] = None

class ChangePasswordRequest(BaseModel):
    current_password: Optional[str] = None  # Required for self-change
    new_password: str

class ResetPasswordRequest(BaseModel):
    user_id: int
    new_password: str

class ProfileUpdateRequest(BaseModel):
    display_name: Optional[str] = None
    avatar_data: Optional[str] = None  # Emoji or base64 data URL (legacy/custom)
    avatar_key: Optional[str] = None   # Built-in avatar id (preferred)

    @validator('display_name')
    def display_name_valid(cls, v):
        if v is None:
            return v
        return _validate_display_name_value(v)

class EventCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    bonus_type: str  # 'xp_multiplier' or 'streak_bonus'
    bonus_value: float  # e.g., 1.5 for 50% bonus

class PriorityRequest(BaseModel):
    scratch_priority: int = 25
    frontend_priority: int = 25
    javascript_priority: int = 25
    python_priority: int = 25

class RewardRequest(BaseModel):
    user_id: int
    icon: str  # emoji
    title: str
    comment: Optional[str] = None

class XPAdjustRequest(BaseModel):
    new_score: int  # 0-10, where 0 = cancel all XP
    reason: Optional[str] = None

class CommentBonusDecision(BaseModel):
    status: str  # 'approved' | 'rejected'
    awarded: Optional[int] = None
    feedback: Optional[str] = None

class HomeworkAssignRequest(BaseModel):
    title: Optional[str] = None
    task_ids: Optional[List[str]] = None
    user_ids: Optional[List[int]] = None

class AlexTypeCompleteRequest(BaseModel):
    level: str  # D, C, B, A, S
    chars_typed: int
    accuracy: float  # 0.0 - 1.0
    text_length: int
    cpm: int = 0  # chars per minute
    elapsed_ms: int = 0  # milliseconds from first keystroke to completion
    keystrokes: int = 0  # total keydown events counted client-side

class AdminXPAdjustRequest(BaseModel):
    user_id: int
    delta_xp: int  # positive to add, negative to remove
    reason: str = "Ручная корректировка Sensei"

# ==================== AUTH ROUTES ====================

app = FastAPI(
    title="Академия Pandora",
    description="Sensei Node API - Gamified LMS with Achievements",
    version="3.0.0"
)

# Rate limiter setup
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS: support LAN + file:// (Origin: null) without opening the world.
# NOTE: Browsers send Origin: "null" for file:// pages.
_cors_origin_regex = os.getenv(
    "PANDORA_CORS_ORIGIN_REGEX",
    r"^https?://(localhost|127\.0\.0\.1|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+)(:\d+)?$",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["null"],
    allow_origin_regex=_cors_origin_regex,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=["X-Server-Type"],
)

# Serve uploads directory statically
Path("uploads").mkdir(exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Serve safe static assets (avatars, icons, etc.)
Path("static").mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.exception_handler(Exception)
def global_exception_handler(request: Request, exc: Exception):
    """Catch all unhandled exceptions and log them without leaking details to clients."""
    client_ip = get_client_ip(request)
    log_error(f"Unhandled exception on {request.method} {request.url.path} from {client_ip}", exc)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})

@app.on_event("startup")
async def _startup() -> None:
    """Initialize DB and ensure stable JWT secret."""
    # When running under uWSGI/PA, startup is handled synchronously by the WSGI file.
    if os.environ.get("PANDORA_SKIP_STARTUP"):
        logger.info("PANDORA_SKIP_STARTUP set — skipping async startup.")
        return

    global JWT_SECRET

    # Ensure stable JWT secret across restarts (env var recommended for production).
    if not JWT_SECRET:
        secret_file = os.getenv("PANDORA_JWT_SECRET_FILE", ".pandora_jwt_secret")
        try:
            secret_path = Path(secret_file)
            if secret_path.exists():
                JWT_SECRET = secret_path.read_text(encoding="utf-8").strip()
            else:
                JWT_SECRET = secrets.token_urlsafe(48)
                secret_path.write_text(JWT_SECRET, encoding="utf-8")
                try:
                    os.chmod(secret_path, 0o600)
                except OSError:
                    pass
            logger.warning("PANDORA_JWT_SECRET is not set; using secret from %s", secret_path)
        except Exception as e:
            JWT_SECRET = secrets.token_urlsafe(48)
            logger.warning("Failed to persist JWT secret; tokens will reset on restart (%s)", e)

    init_db()
    logger.info("SERVER STARTUP | PANDORA Sensei Node v3.0")

@app.api_route("/", methods=["GET", "HEAD", "OPTIONS"], include_in_schema=False)
def serve_index():
    """Serve the student UI (same-origin hosting is optional; file:// works too)."""
    return FileResponse("index.html")

@app.get("/alextype", include_in_schema=False)
def serve_alextype():
    """Serve Alextype JS trainer UI."""
    return FileResponse("alextype.html")

# AlexType last-reward timestamps per user (in-memory cooldown)
_alextype_last_reward: dict[int, float] = {}
_ALEXTYPE_COOLDOWN_S = 30
_ALEXTYPE_DIFFICULTY_MULT = {"D": 0.50, "C": 0.70, "B": 1.00, "A": 1.29, "S": 2.00}
_ALEXTYPE_MAX_XP = {"D": 30, "C": 60, "B": 120, "A": 165, "S": 250}  # Per-rank caps (15% reduction + S>A fix)

@app.post("/api/alextype/complete")
def alextype_complete(data: AlexTypeCompleteRequest, user: dict = Depends(require_auth)):
    """Award XP for completing an AlexType typing session."""
    uid = int(user["id"])
    now = time.monotonic()

    # Cooldown check
    last = _alextype_last_reward.get(uid, 0)
    if now - last < _ALEXTYPE_COOLDOWN_S:
        wait = max(1, int(_ALEXTYPE_COOLDOWN_S - (now - last)))
        raise HTTPException(status_code=429, detail=f"Подожди {wait} сек. перед следующей наградой")

    # Validate
    level = (data.level or "D").upper()
    if level not in _ALEXTYPE_DIFFICULTY_MULT:
        raise HTTPException(status_code=400, detail="Invalid level")
    if data.accuracy < 0.8:
        return {"xp_awarded": 0, "message": "Точность ниже 80%, XP не начислен. Попробуй точнее!"}
    if data.chars_typed < 10:
        return {"xp_awarded": 0, "message": "Слишком мало символов"}
    if data.chars_typed > data.text_length * 1.5:
        return {"xp_awarded": 0, "message": "Невалидные данные"}

    # ===== SERVER-SIDE ANTI-CHEAT: Typing speed validation =====
    _MAX_HUMAN_CPM = 800  # World record ~750 CPM; above this = cheat
    _MIN_ELAPSED_MS = 3000  # At least 3 seconds of typing required

    if data.elapsed_ms > 0:
        elapsed_min = data.elapsed_ms / 60000.0
        if elapsed_min > 0:
            server_cpm = data.chars_typed / elapsed_min
            if server_cpm > _MAX_HUMAN_CPM:
                return {"xp_awarded": 0, "message": "⚠️ Слишком быстро. Печатай сам!"}
        if data.elapsed_ms < _MIN_ELAPSED_MS:
            return {"xp_awarded": 0, "message": "⚠️ Слишком быстро. Печатай сам!"}
    else:
        # No elapsed_ms provided — legacy client or cheat; reject if chars > 20
        if data.chars_typed > 20:
            return {"xp_awarded": 0, "message": "Обнови страницу AlexType"}

    # Keystroke sanity: keystrokes must be ≥ 70% of chars_typed
    # Voice input = 0 keystrokes; paste bypass = very few keystrokes
    if data.chars_typed > 5 and data.keystrokes < data.chars_typed * 0.7:
        return {"xp_awarded": 0, "message": "⚠️ Невалидные данные набора"}

    # XP formula: chars × accuracy × difficulty_multiplier / divisor
    mult = _ALEXTYPE_DIFFICULTY_MULT[level]
    raw_xp = (data.chars_typed * data.accuracy * mult) / 2.0
    cap = _ALEXTYPE_MAX_XP.get(level, 120)
    xp = min(int(raw_xp), cap)
    xp = max(1, xp)

    # ===== ALEX EXCLUSIVE 15% BOOST =====
    username = user.get("username", "")
    alex_boost_applied = False
    if username == "Alex":
        xp = int(xp * 1.15)
        alex_boost_applied = True

    with get_db() as conn:
        cursor = conn.cursor()
        new_xp, new_level = apply_xp_change(
            cursor, uid, xp, f"AlexType {level} ({data.chars_typed} символов, {int(data.accuracy*100)}%)"
        )
        conn.commit()

    _alextype_last_reward[uid] = now

    return {
        "xp_awarded": xp,
        "alex_boost": alex_boost_applied,
        "new_total_xp": new_xp,
        "new_level": new_level,
        "message": f"+{xp} XP за набор текста!",
    }

@app.get("/admin", include_in_schema=False)
def serve_admin():
    """Serve the admin UI."""
    return FileResponse("admin.html")

@app.get("/admin/", include_in_schema=False)
def serve_admin_slash():
    """Serve admin UI for trailing-slash routes (PythonAnywhere-friendly)."""
    return FileResponse("admin.html")

@app.get("/admin.html", include_in_schema=False)
def serve_admin_html():
    """Serve admin UI when static-like path is used."""
    return FileResponse("admin.html")

@app.get("/api/status")
def status():
    """Machine-readable status endpoint."""
    return {"name": "Академия Pandora", "version": "3.0.0", "status": "online"}

@app.api_route("/ping", methods=["GET", "HEAD", "OPTIONS"])
@app.api_route("/health", methods=["GET", "HEAD", "OPTIONS"], include_in_schema=False)
def ping():
    """Auto-discovery/health endpoint."""
    return JSONResponse(
        content={"status": "online", "server": "PANDORA", "version": "3.0.0"},
        headers={"X-Server-Type": "SenseiNode"}
    )

@app.post("/api/auth/login")
def login(request: Request, data: LoginRequest):
    """Authenticate user and return JWT token. Rate limited to 5 attempts/minute."""
    t0 = time.monotonic()
    _auth_trace("login start username=%s", data.username)
    
    # Check for attack patterns in input
    threats = detect_threats(data.username) + detect_threats(data.password)
    if threats:
        for threat in threats:
            log_security_event(threat, request, details=f"username_attempt={data.username}")
        raise HTTPException(status_code=400, detail="Invalid input")
    
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            t_db_open = time.monotonic()
            cursor.execute("SELECT * FROM users WHERE username = ?", (data.username,))
            user = cursor.fetchone()
            t_user_loaded = time.monotonic()
            _auth_trace("login user_fetch done found=%s", bool(user))
            
            if not user or not verify_password(data.password, user["password_hash"]):
                log_security_event(
                    SecurityEvent.LOGIN_FAILED, request,
                    username=data.username,
                    details="Invalid credentials",
                    severity="WARNING"
                )
                raise HTTPException(status_code=401, detail="Invalid credentials")
            
            # Upgrade legacy SHA256 password hashes to bcrypt on successful login
            stored_hash = user["password_hash"] or ""
            if re.fullmatch(r"[a-fA-F0-9]{64}", stored_hash):
                cursor.execute(
                    "UPDATE users SET password_hash = ? WHERE id = ?",
                    (hash_password(data.password), user["id"]),
                )

            # Create JWT token + persist session (revocation support, optional).
            token, expires_at = create_jwt_token(user["id"], user["username"], user["role"])
            if not STATELESS_AUTH:
                token_hash = _token_hash(token)
                cursor.execute(
                    "INSERT OR REPLACE INTO sessions (token, user_id, expires_at, ip, user_agent) VALUES (?, ?, ?, ?, ?)",
                    (
                        token_hash,
                        user["id"],
                        expires_at,
                        get_client_ip(request),
                        (request.headers.get("User-Agent", "") or "")[:200],
                    ),
                )
            conn.commit()
            t_session_saved = time.monotonic()
            _auth_trace("login session saved")
            
            # Log successful login
            event = SecurityEvent.ADMIN_LOGIN if user["role"] == "admin" else SecurityEvent.LOGIN_SUCCESS
            log_security_event(
                event, request,
                user_id=user["id"],
                username=user["username"],
                details=f"role={user['role']}"
            )
            
            # Get completed tasks
            cursor.execute(
                "SELECT task_id FROM completed_tasks WHERE user_id = ? AND is_valid != 0",
                (user["id"],)
            )
            completed = [row["task_id"] for row in cursor.fetchall()]
            
            # Get achievements
            cursor.execute(
                "SELECT achievement_id FROM user_achievements WHERE user_id = ?",
                (user["id"],)
            )
            achievements = [row["achievement_id"] for row in cursor.fetchall()]
            t_done = time.monotonic()
            logger.info(
                "LOGIN_TIMING username=%s db_open=%.1fms user_fetch=%.1fms save_session=%.1fms post_fetch=%.1fms total=%.1fms",
                data.username,
                (t_db_open - t0) * 1000,
                (t_user_loaded - t_db_open) * 1000,
                (t_session_saved - t_user_loaded) * 1000,
                (t_done - t_session_saved) * 1000,
                (t_done - t0) * 1000,
            )
            _auth_trace("login done total_ms=%.1f", (t_done - t0) * 1000)
            
            return {
                "token": token,
                "expires_in": JWT_EXPIRE_HOURS * 3600,
                "user": {
                    "id": user["id"],
                    "username": user["username"],
                    "display_name": user["display_name"],
                    "role": user["role"],
                    "xp": user["xp"],
                    "level": user["level"],
                    "avatar_key": user["avatar_key"] if "avatar_key" in user.keys() else None,
                    "completed_tasks": completed,
                    "achievements": achievements
                }
            }
    except sqlite3.OperationalError as e:
        message = str(e).lower()
        logger.error("LOGIN sqlite operational error for username=%s: %s", data.username, e)
        if "locked" in message or "busy" in message:
            raise HTTPException(status_code=503, detail="Database is busy. Retry in a few seconds.")
        raise

@app.post("/api/auth/logout")
def logout(user: dict = Depends(require_auth), authorization: str = Header(None)):
    """Invalidate session token."""
    if STATELESS_AUTH:
        return {"message": "Logged out"}
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=400, detail="Missing bearer token")
    token = authorization[len("Bearer "):].strip()
    token_hash = _token_hash(token)
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sessions WHERE token = ?", (token_hash,))
        conn.commit()
    return {"message": "Logged out"}

@app.get("/api/auth/me")
def get_current_user(user: dict = Depends(require_auth)):
    """Get current user info."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT task_id FROM completed_tasks WHERE user_id = ? AND is_valid != 0",
            (user["id"],)
        )
        completed = [row["task_id"] for row in cursor.fetchall()]
    
    return {
        "id": user["id"],
        "username": user["username"],
        "display_name": user["display_name"],
        "role": user["role"],
        "xp": user["xp"],
        "level": user["level"],
        "avatar_key": user.get("avatar_key"),
        "completed_tasks": completed
    }

@app.post("/api/auth/change-password")
def change_password(data: ChangePasswordRequest, user: dict = Depends(require_auth)):
    """Change own password (requires current password)."""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Verify current password
        cursor.execute(
            "SELECT password_hash FROM users WHERE id = ?",
            (user["id"],)
        )
        row = cursor.fetchone()

        if not row or not verify_password(data.current_password or "", row["password_hash"]):
            raise HTTPException(status_code=400, detail="Current password is incorrect")
        
        # Update password
        cursor.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (hash_password(data.new_password), user["id"])
        )
        # Revoke all sessions (force re-login everywhere)
        if not STATELESS_AUTH:
            cursor.execute("DELETE FROM sessions WHERE user_id = ?", (user["id"],))
        conn.commit()
    
    log_security("PASSWORD_CHANGED", user=user["username"], details="Self-change")
    return {"message": "Password changed successfully"}

@app.post("/api/admin/reset-password")
def reset_user_password(data: ResetPasswordRequest, admin: dict = Depends(require_admin)):
    """Reset any user's password (Admin only)."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (hash_password(data.new_password), data.user_id)
        )
        if not STATELESS_AUTH:
            cursor.execute("DELETE FROM sessions WHERE user_id = ?", (data.user_id,))
        conn.commit()
        
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="User not found")
    
    log_security("PASSWORD_RESET", user=admin["username"], details=f"Reset user_id={data.user_id}")
    return {"message": "Password reset successfully"}

@app.post("/api/admin/adjust-xp")
def admin_adjust_xp(data: AdminXPAdjustRequest, admin: dict = Depends(require_admin)):
    """Manually add or remove XP from any student (Admin only)."""
    if data.delta_xp == 0:
        raise HTTPException(status_code=400, detail="delta_xp must be non-zero")

    with get_db() as conn:
        cursor = conn.cursor()
        # Verify target user exists
        cursor.execute("SELECT id, display_name, xp FROM users WHERE id = ?", (data.user_id,))
        target = cursor.fetchone()
        if not target:
            raise HTTPException(status_code=404, detail="User not found")

        reason = f"Sensei ({admin['display_name']}): {data.reason}"
        new_xp, new_level = apply_xp_change(cursor, data.user_id, data.delta_xp, reason)
        conn.commit()

    action = "added" if data.delta_xp > 0 else "removed"
    log_security(
        "XP_ADJUST", user=admin["username"],
        details=f"{action} {abs(data.delta_xp)} XP for user_id={data.user_id} reason={data.reason}"
    )
    return {
        "message": f"XP {action}: {abs(data.delta_xp)}",
        "new_xp": new_xp,
        "new_level": new_level,
        "user_display_name": target['display_name'],
    }

# ==================== GAMIFICATION ROUTES ====================

@app.get("/api/ranks")
def get_ranks():
    """Get all ranks with their requirements."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM ranks ORDER BY min_xp")
        ranks = [dict(row) for row in cursor.fetchall()]
    return {"ranks": ranks}

@app.get("/api/achievements")
def get_all_achievements():
    """Get all available achievements."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM achievements ORDER BY condition_value")
        achievements = [dict(row) for row in cursor.fetchall()]
    return {"achievements": achievements}

@app.get("/api/user/achievements")
def get_user_achievements(user: dict = Depends(require_auth)):
    """Get user's unlocked achievements."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT a.*, ua.unlocked_at 
            FROM achievements a
            JOIN user_achievements ua ON a.id = ua.achievement_id
            WHERE ua.user_id = ?
            ORDER BY ua.unlocked_at DESC
        """, (user["id"],))
        unlocked = [dict(row) for row in cursor.fetchall()]
        
        # Get total count
        cursor.execute("SELECT COUNT(*) FROM achievements")
        total = cursor.fetchone()[0]
        
    return {
        "unlocked": unlocked,
        "total": total,
        "progress": len(unlocked) / total if total > 0 else 0
    }

@app.get("/api/achievements/status")
def get_achievement_status(user: dict = Depends(require_auth)):
    """Get all achievements with unlocked state + per-achievement progress for the current user."""
    tasks_data = load_tasks()
    tasks_map = {t.get("id"): t for t in tasks_data.get("tasks", []) if t.get("id")}
    category_totals = Counter((t.get("category") or "") for t in tasks_map.values())
    tier_totals = Counter((t.get("tier") or "").upper() for t in tasks_map.values())

    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM achievements ORDER BY rarity, condition_value")
        achievements = [dict(r) for r in cursor.fetchall()]

        cursor.execute("SELECT achievement_id, unlocked_at FROM user_achievements WHERE user_id = ?", (user["id"],))
        unlocked_map = {r["achievement_id"]: r["unlocked_at"] for r in cursor.fetchall()}

        # Core stats
        cursor.execute("SELECT COUNT(*) FROM completed_tasks WHERE user_id = ? AND is_valid != 0", (user["id"],))
        total_quests = int(cursor.fetchone()[0])

        cursor.execute("SELECT streak_days FROM user_stats WHERE user_id = ?", (user["id"],))
        row = cursor.fetchone()
        streak_days = int(row["streak_days"]) if row and row["streak_days"] is not None else 0

        cursor.execute(
            "SELECT COUNT(*) FROM completed_tasks WHERE user_id = ? AND DATE(completed_at) = DATE('now') AND is_valid != 0",
            (user["id"],),
        )
        daily_quests = int(cursor.fetchone()[0])

        cursor.execute("SELECT task_id FROM completed_tasks WHERE user_id = ? AND is_valid != 0", (user["id"],))
        completed_ids = [r["task_id"] for r in cursor.fetchall()]

    category_counts = Counter()
    tier_counts = Counter()
    for tid in completed_ids:
        t = tasks_map.get(tid) or {}
        category_counts[(t.get("category") or "")] += 1
        tier_counts[(t.get("tier") or "").upper()] += 1

    def _progress_item(ach: dict) -> dict:
        ach_id = ach.get("id")
        ctype = ach.get("condition_type")
        target = int(ach.get("condition_value") or 0)

        current = 0
        total = max(1, target)
        label_ru = ""

        if ctype == "quests_completed":
            current = total_quests
            total = max(1, target)
            label_ru = f"{min(current, total)}/{total} квестов"
        elif ctype == "streak_days":
            current = streak_days
            total = max(1, target)
            label_ru = f"{min(current, total)}/{total} дней подряд"
        elif ctype == "daily_quests":
            current = daily_quests
            total = max(1, target)
            label_ru = f"{min(current, total)}/{total} квеста сегодня"
        elif ctype == "total_xp":
            current = int(user.get("xp") or 0)
            total = max(1, target)
            label_ru = f"{min(current, total)}/{total} XP"
        elif ctype == "level":
            current = int(user.get("level") or compute_level(int(user.get("xp") or 0)))
            total = max(1, target)
            label_ru = f"Уровень {min(current, total)}/{total}"
        elif ctype in ("category_python", "category_javascript", "category_frontend", "category_scratch"):
            cat = ctype.replace("category_", "")
            current = int(category_counts.get(cat, 0))
            total = max(1, target)
            label_ru = f"{min(current, total)}/{total} в категории «{cat}»"
        elif isinstance(ctype, str) and ctype.startswith("tier_"):
            tier_letter = ctype.split("_", 1)[1].upper()
            total = int(tier_totals.get(tier_letter, 0)) or 1
            current = int(tier_counts.get(tier_letter, 0))
            label_ru = f"{min(current, total)}/{total} квестов ранга {tier_letter}"
        elif ctype == "multi_category_min":
            # Progress is the weakest category
            current = min([int(category_counts.get(c, 0)) for c in ("python", "javascript", "frontend", "scratch")])
            total = max(1, target)
            label_ru = f"{min(current, total)}/{total} в каждой категории"
        elif ctype == "any_category_complete":
            best_cat = None
            best_ratio = 0.0
            best_current = 0
            best_total = 1
            for cat in ("python", "javascript", "frontend", "scratch"):
                total_cat = int(category_totals.get(cat, 0))
                if total_cat <= 0:
                    continue
                cur_cat = int(category_counts.get(cat, 0))
                ratio = cur_cat / total_cat
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_cat = cat
                    best_current = cur_cat
                    best_total = total_cat
            current = best_current
            total = best_total
            label_ru = f"{min(current, total)}/{total} в лучшей категории ({best_cat or '—'})"
        else:
            current = 0
            total = max(1, target)
            label_ru = "0/0"

        is_unlocked = ach_id in unlocked_map
        if is_unlocked:
            current = total

        ratio = min(1.0, (current / total) if total else 0.0)

        return {
            "id": ach_id,
            "name": ach.get("name"),
            "name_ru": ach.get("name_ru"),
            "description": ach.get("description"),
            "icon": ach.get("icon"),
            "rarity": ach.get("rarity") or "common",
            "xp_bonus": int(ach.get("xp_bonus") or 0),
            "condition_type": ctype,
            "condition_value": target,
            "unlocked": bool(is_unlocked),
            "unlocked_at": unlocked_map.get(ach_id),
            "progress_current": int(current),
            "progress_total": int(total),
            "progress_ratio": ratio,
            "progress_label_ru": label_ru,
        }

    items = [_progress_item(a) for a in achievements]
    unlocked_count = sum(1 for a in items if a["unlocked"])
    return {
        "achievements": items,
        "summary": {
            "unlocked": unlocked_count,
            "total": len(items),
            "ratio": (unlocked_count / len(items)) if items else 0.0,
        },
    }

@app.get("/api/events/active")
def get_active_events():
    """Get all currently active events."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM events WHERE is_active = 1")
        events = [dict(row) for row in cursor.fetchall()]
    return {"events": events}

@app.get("/api/leaderboard")
def get_leaderboard(limit: int = Query(20, le=100)):
    """Get top students by XP (optimized - no heavy avatar data)."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT u.id, u.username, u.display_name, u.xp, u.level,
                   r.name_ru as rank_name, r.badge_emoji as rank_badge, r.color as rank_color,
                   COALESCE(u.avatar_key, '') as avatar_key,
                   CASE WHEN s.avatar_data IS NOT NULL AND s.avatar_data != '' THEN 1 ELSE 0 END as has_avatar,
                   gm.guild_id as guild_id,
                   g.name as guild_name,
                   gm.role as guild_role
            FROM users u
            LEFT JOIN ranks r ON u.xp >= r.min_xp
            LEFT JOIN user_stats s ON u.id = s.user_id
            LEFT JOIN guild_members gm ON gm.user_id = u.id
            LEFT JOIN guilds g ON g.id = gm.guild_id AND g.disbanded_at IS NULL
            WHERE u.role = 'student'
            AND r.min_xp = (SELECT MAX(min_xp) FROM ranks WHERE min_xp <= u.xp)
            ORDER BY u.xp DESC
            LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()

        # Fetch active positive titles for all users
        cursor.execute("""
            SELECT mt.to_user_id, mt.title_text, mt.effect_type, mt.effect_value
            FROM guild_member_titles mt
            WHERE mt.expires_at > CURRENT_TIMESTAMP AND mt.effect_type = 'xp_buff'
        """)
        user_titles = {}
        for t in cursor.fetchall():
            uid = t["to_user_id"]
            if uid not in user_titles:
                user_titles[uid] = []
            user_titles[uid].append({
                "title_text": t["title_text"],
                "effect_type": t["effect_type"],
                "effect_value": t["effect_value"],
            })

        leaders = []
        for i, row in enumerate(rows, 1):
            uid = row["id"]
            is_alex = row["username"] == "Alex"
            entry = {
                "position": i,
                "id": uid,
                "display_name": row["display_name"],
                "xp": row["xp"],
                "level": row["level"],
                "rank_name": row["rank_name"],
                "rank_badge": row["rank_badge"],
                "rank_color": row["rank_color"],
                "avatar_key": row["avatar_key"] or None,
                "has_avatar": bool(row["has_avatar"]),
                "guild_id": row["guild_id"],
                "guild_name": row["guild_name"],
                "guild_role": row["guild_role"],
                "alex_boost": is_alex,
                "active_titles": user_titles.get(uid, []),
            }
            leaders.append(entry)
    return {"leaderboard": leaders}

@app.get("/api/avatar/{user_id}")
def get_user_avatar(user_id: int):
    """Get user's avatar data (for lazy loading)."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT avatar_data FROM user_stats WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if row and row["avatar_data"]:
            return {"avatar_data": row["avatar_data"]}
        return {"avatar_data": None}

@app.get("/api/user/{user_id}/public")
def get_public_profile(user_id: int, current_user: dict = Depends(require_auth)):
    """Get public profile of any user (visible to logged-in users)."""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Get user basic info
        cursor.execute("""
            SELECT u.id, u.display_name, u.xp, u.level, u.created_at,
                   r.name_ru as rank_name, r.badge_emoji as rank_badge, r.color as rank_color
            FROM users u
            LEFT JOIN ranks r ON r.min_xp = (SELECT MAX(min_xp) FROM ranks WHERE min_xp <= u.xp)
            WHERE u.id = ?
        """, (user_id,))
        user = cursor.fetchone()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get user stats
        cursor.execute("""
            SELECT total_quests, streak_days, avatar_data
            FROM user_stats WHERE user_id = ?
        """, (user_id,))
        stats = cursor.fetchone()
        
        # Get achievements
        cursor.execute("""
            SELECT a.name_ru, a.description, a.icon, a.rarity, ua.unlocked_at
            FROM user_achievements ua
            JOIN achievements a ON ua.achievement_id = a.id
            WHERE ua.user_id = ?
            ORDER BY ua.unlocked_at DESC
        """, (user_id,))
        achievements = [dict(row) for row in cursor.fetchall()]
        
        # Get completed quests count by category
        cursor.execute("""
            SELECT COUNT(*) as count FROM completed_tasks WHERE user_id = ? AND is_valid = 1
        """, (user_id,))
        completed_count = cursor.fetchone()["count"]
        
        # Get leaderboard position
        cursor.execute("""
            SELECT COUNT(*) + 1 as position FROM users 
            WHERE role = 'student' AND xp > (SELECT xp FROM users WHERE id = ?)
        """, (user_id,))
        position = cursor.fetchone()["position"]
        
    return {
        "id": user["id"],
        "display_name": user["display_name"],
        "xp": user["xp"],
        "level": user["level"],
        "member_since": user["created_at"],
        "rank": {
            "name": user["rank_name"],
            "badge": user["rank_badge"],
            "color": user["rank_color"]
        },
        "stats": {
            "total_quests": stats["total_quests"] if stats else 0,
            "streak_days": stats["streak_days"] if stats else 0,
            "completed_tasks": completed_count
        },
        "avatar_data": stats["avatar_data"] if stats else None,
        "achievements": achievements,
        "leaderboard_position": position
    }

# ==================== CAMPAIGN SYSTEM ====================

@app.get("/api/campaign/progress")
def get_campaign_progress(user: dict = Depends(require_auth)):
    """Get user's campaign progress through acts and chapters."""
    tasks_data = load_tasks()
    all_tasks = tasks_data.get("tasks", [])
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT task_id FROM completed_tasks WHERE user_id = ? AND is_valid != 0",
            (user["id"],)
        )
        completed_ids = {row["task_id"] for row in cursor.fetchall()}
    
    # Build campaign structure
    acts = {}
    for task in all_tasks:
        campaign = task.get("campaign")
        if not campaign:
            continue
        
        act_num = campaign.get("act", 1)
        chapter_num = campaign.get("chapter", 1)
        task_type = campaign.get("type", "quest")
        task_id = task.get("id")
        
        if act_num not in acts:
            acts[act_num] = {"act": act_num, "chapters": {}, "total": 0, "completed": 0}
        
        if chapter_num not in acts[act_num]["chapters"]:
            acts[act_num]["chapters"][chapter_num] = {
                "chapter": chapter_num,
                "quests": [], "bosses": [], "side_quests": [],
                "total": 0, "completed": 0
            }
        
        chapter = acts[act_num]["chapters"][chapter_num]
        is_completed = task_id in completed_ids
        
        task_info = {
            "id": task_id,
            "title": task.get("title"),
            "xp": task.get("xp"),
            "completed": is_completed,
            "order": campaign.get("order", 1)
        }
        
        if task_type == "boss":
            chapter["bosses"].append(task_info)
        elif task_type == "side":
            chapter["side_quests"].append(task_info)
        else:
            chapter["quests"].append(task_info)
        
        chapter["total"] += 1
        acts[act_num]["total"] += 1
        if is_completed:
            chapter["completed"] += 1
            acts[act_num]["completed"] += 1
    
    # Convert to sorted list
    result = []
    for act_num in sorted(acts.keys()):
        act = acts[act_num]
        chapters = []
        for ch_num in sorted(act["chapters"].keys()):
            ch = act["chapters"][ch_num]
            # Sort by order
            ch["quests"].sort(key=lambda x: x["order"])
            ch["bosses"].sort(key=lambda x: x["order"])
            ch["side_quests"].sort(key=lambda x: x["order"])
            chapters.append(ch)
        
        result.append({
            "act": act_num,
            "total": act["total"],
            "completed": act["completed"],
            "progress": act["completed"] / act["total"] if act["total"] > 0 else 0,
            "chapters": chapters
        })
    
    total_campaign = sum(a["total"] for a in result)
    completed_campaign = sum(a["completed"] for a in result)
    
    return {
        "acts": result,
        "total_tasks": total_campaign,
        "completed_tasks": completed_campaign,
        "overall_progress": completed_campaign / total_campaign if total_campaign > 0 else 0
    }

# ==================== DAILY MISSIONS ====================

MISSION_TYPES = [
    {"type": "complete_any", "name": "Путь Воина", "name_ru": "Путь Воина", "target": 3, "xp": 25, "description": "Выполни 3 любых квеста"},
    {"type": "complete_category", "name": "Фокус силы", "name_ru": "Фокус силы", "target": 2, "xp": 20, "description": "Выполни 2 квеста в одной категории"},
    {"type": "streak_login", "name": "Стойкость", "name_ru": "Стойкость", "target": 1, "xp": 10, "description": "Войди в систему сегодня"},
]

def _generate_daily_missions(cursor, user_id: int, today: str):
    """Generate new daily missions for user if needed."""
    cursor.execute(
        "SELECT COUNT(*) FROM daily_missions WHERE user_id = ? AND date = ?",
        (user_id, today)
    )
    if cursor.fetchone()[0] > 0:
        return  # Already generated
    
    # Create 3 missions for today
    for mission in MISSION_TYPES:
        cursor.execute("""
            INSERT OR IGNORE INTO daily_missions (user_id, date, mission_type, progress, target, claimed, xp_reward)
            VALUES (?, ?, ?, 0, ?, 0, ?)
        """, (user_id, today, mission["type"], mission["target"], mission["xp"]))

def _update_mission_progress(cursor, user_id: int, mission_type: str, increment: int = 1):
    """Update progress for a specific mission type."""
    today = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("""
        UPDATE daily_missions 
        SET progress = MIN(progress + ?, target)
        WHERE user_id = ? AND date = ? AND mission_type = ? AND claimed = 0
    """, (increment, user_id, today, mission_type))


def _sync_daily_missions_progress(cursor, user_id: int):
    """Recompute daily mission progress from canonical data (completions + login)."""
    today = datetime.now().strftime("%Y-%m-%d")
    _generate_daily_missions(cursor, user_id, today)

    cursor.execute(
        """
        SELECT task_id
        FROM completed_tasks
        WHERE user_id = ? AND DATE(completed_at) = DATE('now') AND is_valid != 0
        """,
        (user_id,),
    )
    todays_task_ids = [row["task_id"] for row in cursor.fetchall()]
    total_today = len(todays_task_ids)

    # complete_any: absolute count today
    cursor.execute(
        """
        UPDATE daily_missions
        SET progress = MIN(target, ?)
        WHERE user_id = ? AND date = ? AND mission_type = 'complete_any' AND claimed = 0
        """,
        (total_today, user_id, today),
    )

    # streak_login: completed when user has reached the app today.
    cursor.execute(
        """
        UPDATE daily_missions
        SET progress = 1
        WHERE user_id = ? AND date = ? AND mission_type = 'streak_login' AND claimed = 0
        """,
        (user_id, today),
    )

    # complete_category: max number of completed tasks today within any one category.
    max_in_category = 0
    if todays_task_ids:
        tasks_data = load_tasks()
        tasks_map = {t.get("id"): t for t in tasks_data.get("tasks", []) if t.get("id")}
        cat_counts = Counter()
        for tid in todays_task_ids:
            cat = (tasks_map.get(tid) or {}).get("category") or "unknown"
            cat_counts[cat] += 1
        max_in_category = max(cat_counts.values()) if cat_counts else 0

    cursor.execute(
        """
        UPDATE daily_missions
        SET progress = MIN(target, ?)
        WHERE user_id = ? AND date = ? AND mission_type = 'complete_category' AND claimed = 0
        """,
        (max_in_category, user_id, today),
    )

@app.get("/api/missions/daily")
def get_daily_missions(user: dict = Depends(require_auth)):
    """Get today's daily missions for current user."""
    today = datetime.now().strftime("%Y-%m-%d")
    
    with get_db() as conn:
        cursor = conn.cursor()
        _sync_daily_missions_progress(cursor, user["id"])
        conn.commit()
        
        cursor.execute("""
            SELECT mission_type, progress, target, claimed, xp_reward
            FROM daily_missions WHERE user_id = ? AND date = ?
        """, (user["id"], today))
        
        missions = []
        for row in cursor.fetchall():
            mission_info = next((m for m in MISSION_TYPES if m["type"] == row["mission_type"]), {})
            missions.append({
                "type": row["mission_type"],
                "name": mission_info.get("name_ru", row["mission_type"]),
                "description": mission_info.get("description", ""),
                "progress": row["progress"],
                "target": row["target"],
                "completed": row["progress"] >= row["target"],
                "claimed": bool(row["claimed"]),
                "xp_reward": row["xp_reward"]
            })
    
    return {"missions": missions, "date": today}

@app.post("/api/missions/claim/{mission_type}")
def claim_mission_reward(mission_type: str, user: dict = Depends(require_auth)):
    """Claim XP reward for a completed daily mission."""
    today = datetime.now().strftime("%Y-%m-%d")
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, progress, target, claimed, xp_reward
            FROM daily_missions 
            WHERE user_id = ? AND date = ? AND mission_type = ?
        """, (user["id"], today, mission_type))
        
        mission = cursor.fetchone()
        if not mission:
            raise HTTPException(status_code=404, detail="Mission not found")
        
        if mission["claimed"]:
            raise HTTPException(status_code=400, detail="Already claimed")
        
        if mission["progress"] < mission["target"]:
            raise HTTPException(status_code=400, detail="Mission not completed")
        
        # Award XP
        xp_reward = mission["xp_reward"]
        new_xp, new_level = apply_xp_change(cursor, user["id"], int(xp_reward or 0), f"daily_mission:{mission_type}")
        cursor.execute(
            "UPDATE daily_missions SET claimed = 1 WHERE id = ?",
            (mission["id"],)
        )
        conn.commit()
    
    return {"message": "Reward claimed", "xp_awarded": xp_reward, "new_xp": new_xp, "new_level": new_level}

# ==================== BONUS QUESTS ====================

import random

BONUS_SPAWN_CHANCE = 0.10  # 10% chance
BONUS_XP_MULTIPLIER = 1.5
BONUS_EXPIRY_HOURS = 2

def spawn_bonus_quest(cursor, user_id: int, completed_task_id: str) -> dict | None:
    """Attempt to spawn a bonus quest (10% chance). Returns bonus info if spawned."""
    if random.random() > BONUS_SPAWN_CHANCE:
        return None
    
    # Pick a random uncompleted task in same tier
    tasks_data = load_tasks()
    completed_task = next((t for t in tasks_data.get("tasks", []) if t.get("id") == completed_task_id), None)
    if not completed_task:
        return None
    
    tier = completed_task.get("tier", "D")
    available = [
        t for t in tasks_data.get("tasks", [])
        if t.get("tier") == tier and t.get("id") != completed_task_id
        and t.get("category") != "scratch"  # No manual review tasks
    ]
    
    if not available:
        return None
    
    bonus_task = random.choice(available)
    expires_at = datetime.now() + timedelta(hours=BONUS_EXPIRY_HOURS)
    
    cursor.execute("""
        INSERT INTO bonus_quests (user_id, task_id, xp_multiplier, expires_at)
        VALUES (?, ?, ?, ?)
    """, (user_id, bonus_task["id"], BONUS_XP_MULTIPLIER, expires_at.isoformat()))
    
    return {
        "task_id": bonus_task["id"],
        "task_title": bonus_task.get("title"),
        "xp_multiplier": BONUS_XP_MULTIPLIER,
        "expires_at": expires_at.isoformat()
    }

@app.get("/api/bonus-quest")
def get_active_bonus_quest(user: dict = Depends(require_auth)):
    """Get current active bonus quest if any."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, task_id, xp_multiplier, expires_at, claimed
            FROM bonus_quests 
            WHERE user_id = ? AND claimed = 0 AND expires_at > datetime('now')
            ORDER BY created_at DESC LIMIT 1
        """, (user["id"],))
        
        bonus = cursor.fetchone()
        if not bonus:
            return {"active": False, "bonus": None}
        
        tasks_data = load_tasks()
        task = next((t for t in tasks_data.get("tasks", []) if t.get("id") == bonus["task_id"]), None)
        
        return {
            "active": True,
            "bonus": {
                "id": bonus["id"],
                "task_id": bonus["task_id"],
                "task_title": task.get("title") if task else "Unknown",
                "xp_multiplier": bonus["xp_multiplier"],
                "expires_at": bonus["expires_at"]
            }
        }

@app.get("/api/profile")
def get_profile(user: dict = Depends(require_auth)):
    """Get current user's full profile with stats."""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Get user rank
        cursor.execute("""
            SELECT * FROM ranks WHERE min_xp <= ? ORDER BY min_xp DESC LIMIT 1
        """, (user["xp"],))
        current_rank = dict(cursor.fetchone())
        
        # Get next rank
        cursor.execute("""
            SELECT * FROM ranks WHERE min_xp > ? ORDER BY min_xp ASC LIMIT 1
        """, (user["xp"],))
        next_rank_row = cursor.fetchone()
        next_rank = dict(next_rank_row) if next_rank_row else None
        
        # Get user stats
        cursor.execute("SELECT * FROM user_stats WHERE user_id = ?", (user["id"],))
        stats_row = cursor.fetchone()
        if stats_row:
            stats = dict(stats_row)
        else:
            stats = {"total_quests": 0, "streak_days": 0, "best_streak": 0, "avatar_data": ""}
        
        # Get completed tasks count
        cursor.execute("SELECT COUNT(*) FROM completed_tasks WHERE user_id = ? AND is_valid != 0", (user["id"],))
        stats["total_quests"] = cursor.fetchone()[0]
        
        # Get position in leaderboard
        cursor.execute("""
            SELECT COUNT(*) + 1 FROM users WHERE role = 'student' AND xp > ?
        """, (user["xp"],))
        position = cursor.fetchone()[0]

        # ---- XP Breakdown: tasks / AlexType / expert-polymath ----
        # AlexType XP (reason starts with 'AlexType')
        cursor.execute("""
            SELECT COALESCE(SUM(xp_change), 0) FROM xp_log
            WHERE user_id = ? AND reason LIKE 'AlexType%'
        """, (user["id"],))
        xp_alextype = max(0, cursor.fetchone()[0])

        # Task XP (from completed_tasks table, only valid)
        cursor.execute("""
            SELECT COALESCE(SUM(xp_earned), 0) FROM completed_tasks
            WHERE user_id = ? AND is_valid != 0
        """, (user["id"],))
        xp_tasks = max(0, cursor.fetchone()[0])

        tasks_completed = stats["total_quests"]

        # Expert Polymath XP = total - tasks - alextype (achievements, bonuses, admin, etc.)
        total_xp = max(0, int(user.get("xp", 0)))
        xp_expert = max(0, total_xp - xp_tasks - xp_alextype)

        xp_breakdown = {
            "tasks_completed": tasks_completed,
            "xp_tasks": xp_tasks,
            "xp_alextype": xp_alextype,
            "xp_expert": xp_expert,
        }

    avatar_key = user.get("avatar_key")
    avatar_url = f"/static/avatars/{avatar_key}.svg" if avatar_key else None

    return {
        "id": user["id"],
        "username": user["username"],
        "display_name": user["display_name"],
        "xp": user["xp"],
        "level": user["level"],
        "avatar_key": avatar_key,
        "avatar_url": avatar_url,
        "current_rank": current_rank,
        "next_rank": next_rank,
        "stats": stats,
        "leaderboard_position": position,
        "xp_breakdown": xp_breakdown
    }

@app.put("/api/profile")
def update_profile(data: ProfileUpdateRequest, user: dict = Depends(require_auth)):
    """Update user profile (display name, avatar)."""
    with get_db() as conn:
        cursor = conn.cursor()
        
        if data.display_name is not None:
            cursor.execute(
                "UPDATE users SET display_name = ? WHERE id = ?",
                (data.display_name, user["id"])
            )
        
        if data.avatar_data is not None:
            # Limit avatar payload size (base64 images can get large)
            if len(data.avatar_data) > 200_000:
                raise HTTPException(status_code=413, detail="Avatar too large")

            # Ensure user_stats exists
            cursor.execute(
                "INSERT OR IGNORE INTO user_stats (user_id) VALUES (?)",
                (user["id"],)
            )
            cursor.execute(
                "UPDATE user_stats SET avatar_data = ? WHERE user_id = ?",
                (data.avatar_data, user["id"])
            )

            # If a custom avatar is provided, clear built-in selection
            cursor.execute("UPDATE users SET avatar_key = NULL WHERE id = ?", (user["id"],))

        if data.avatar_key is not None:
            # Built-in avatars are served from /static/avatars/{key}.svg
            key = (data.avatar_key or "").strip()
            if not re.fullmatch(r"[a-z0-9_\\-]{1,32}", key):
                raise HTTPException(status_code=400, detail="Invalid avatar_key")

            cursor.execute("UPDATE users SET avatar_key = ? WHERE id = ?", (key, user["id"]))
        
        conn.commit()
    
    return {"message": "Profile updated"}

@app.post("/api/admin/events")
def create_event(data: EventCreateRequest, admin: dict = Depends(require_admin)):
    """Create a new event (Admin only)."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO events (name, description, bonus_type, bonus_value) VALUES (?, ?, ?, ?)",
            (data.name, data.description, data.bonus_type, data.bonus_value)
        )
        conn.commit()
        return {"message": "Event created", "id": cursor.lastrowid}

@app.put("/api/admin/events/{event_id}")
def toggle_event(event_id: int, admin: dict = Depends(require_admin)):
    """Toggle event active status (Admin only)."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE events SET is_active = NOT is_active WHERE id = ?",
            (event_id,)
        )
        conn.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Event not found")
    return {"message": "Event toggled"}

@app.delete("/api/admin/events/{event_id}")
def delete_event(event_id: int, admin: dict = Depends(require_admin)):
    """Delete an event (Admin only)."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM events WHERE id = ?", (event_id,))
        conn.commit()
    return {"message": "Event deleted"}

# ==================== ADMIN ROUTES ====================

@app.post("/api/admin/users")
def create_user(request: Request, data: RegisterRequest, admin: dict = Depends(require_admin)):
    """Create a new student account (Admin only)."""
    # Check for attack patterns
    threats = detect_threats(data.username) + detect_threats(data.display_name)
    if threats:
        for threat in threats:
            log_security_event(threat, request, user_id=admin["id"], 
                             username=admin["username"], 
                             details=f"attempted_username={data.username}",
                             severity="CRITICAL")
        raise HTTPException(status_code=400, detail="Invalid input detected")
    
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO users (username, password_hash, display_name) VALUES (?, ?, ?)",
                (data.username, hash_password(data.password), data.display_name)
            )
            conn.commit()
            log_security_event(
                SecurityEvent.ADMIN_CREATE_USER, request,
                user_id=admin["id"],
                username=admin["username"],
                details=f"created_user={data.username} user_id={cursor.lastrowid}"
            )
            return {"message": f"User '{data.username}' created", "id": cursor.lastrowid}
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=400, detail="Username already exists")

@app.get("/api/admin/users")
def list_users(admin: dict = Depends(require_admin)):
    """List all users (Admin only)."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, username, display_name, role, xp, level, created_at
            FROM users ORDER BY xp DESC
        """)
        users = [dict(row) for row in cursor.fetchall()]
    return {"users": users}

@app.delete("/api/admin/users/{user_id}")
def delete_user(user_id: int, admin: dict = Depends(require_admin)):
    """Delete a user (Admin only)."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        cursor.execute("DELETE FROM completed_tasks WHERE user_id = ?", (user_id,))
        cursor.execute("DELETE FROM submissions WHERE user_id = ?", (user_id,))
        cursor.execute("DELETE FROM users WHERE id = ? AND role != 'admin'", (user_id,))
        conn.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="User not found or cannot delete admin")
    
    log_security("USER_DELETED", user=admin["username"], details=f"Deleted user_id={user_id}")
    return {"message": "User deleted"}

@app.get("/api/admin/submissions")
def get_submissions(
    status: Optional[str] = Query(None),
    compact_duplicates: bool = Query(True),
    admin: dict = Depends(require_admin)
):
    """Get all submissions for review (Admin only)."""
    with get_db() as conn:
        cursor = conn.cursor()
        query = """
            SELECT s.*, u.username, u.display_name
            FROM submissions s
            JOIN users u ON s.user_id = u.id
        """
        if status:
            query += " WHERE s.status = ?"
            cursor.execute(query + " ORDER BY s.submitted_at DESC", (status,))
        else:
            cursor.execute(query + " ORDER BY s.submitted_at DESC")
        
        rows = [dict(row) for row in cursor.fetchall()]

    if not compact_duplicates:
        return {"submissions": rows, "meta": {"pending_duplicates_hidden": 0}}

    # Collapse duplicate pending reviews for the same student+task, keeping the newest one.
    pending_groups: dict[tuple[int, str], list[int]] = {}
    for sub in rows:
        if sub.get("status") != "pending":
            continue
        key = (int(sub.get("user_id") or 0), str(sub.get("task_id") or ""))
        pending_groups.setdefault(key, []).append(int(sub.get("id")))

    collapsed: list[dict] = []
    hidden_count = 0
    seen_pending: set[tuple[int, str]] = set()
    for sub in rows:
        if sub.get("status") != "pending":
            collapsed.append(sub)
            continue

        key = (int(sub.get("user_id") or 0), str(sub.get("task_id") or ""))
        if key in seen_pending:
            hidden_count += 1
            continue
        seen_pending.add(key)

        dup_ids = pending_groups.get(key) or []
        sub["pending_duplicates"] = max(0, len(dup_ids) - 1)
        sub["pending_duplicate_ids"] = dup_ids[1:] if len(dup_ids) > 1 else []
        collapsed.append(sub)

    return {"submissions": collapsed, "meta": {"pending_duplicates_hidden": hidden_count}}


@app.post("/api/admin/submissions/cleanup-duplicates")
def cleanup_duplicate_submissions(admin: dict = Depends(require_admin)):
    """Auto-close duplicated pending submissions (same user + task, keep newest)."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, user_id, task_id
            FROM submissions
            WHERE status = 'pending'
            ORDER BY submitted_at DESC, id DESC
            """
        )
        rows = [dict(r) for r in cursor.fetchall()]

        seen: set[tuple[int, str]] = set()
        duplicate_ids: list[int] = []
        for row in rows:
            key = (int(row["user_id"]), str(row["task_id"]))
            if key in seen:
                duplicate_ids.append(int(row["id"]))
            else:
                seen.add(key)

        cleaned = 0
        if duplicate_ids:
            placeholders = ",".join(["?"] * len(duplicate_ids))
            message = "Auto-closed duplicate pending submission"
            review_reason = json.dumps({"reason": "duplicate_pending_cleanup"}, ensure_ascii=False)
            cursor.execute(
                f"""
                UPDATE submissions
                SET status = 'rejected',
                    feedback = CASE
                        WHEN feedback IS NULL OR feedback = '' THEN ?
                        ELSE feedback || ' | ' || ?
                    END,
                    reviewed_at = CURRENT_TIMESTAMP,
                    reviewer_id = ?,
                    review_reason = ?
                WHERE id IN ({placeholders}) AND status = 'pending'
                """,
                [message, message, int(admin["id"]), review_reason, *duplicate_ids],
            )
            cleaned = int(cursor.rowcount or 0)
            conn.commit()

        cursor.execute(
            """
            INSERT INTO audit_log (actor_user_id, actor_username, action, target_user_id, target_task_id, delta_xp, meta_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(admin["id"]),
                admin.get("username"),
                "SUBMISSIONS_DUPLICATES_CLEANUP",
                None,
                None,
                0,
                json.dumps({"cleaned": cleaned}, ensure_ascii=False),
            ),
        )
        conn.commit()

    return {"message": "Duplicate pending submissions cleaned", "cleaned": cleaned}

@app.put("/api/admin/submissions/{submission_id}")
def review_submission(
    submission_id: int,
    data: ReviewRequest,
    admin: dict = Depends(require_admin)
):
    """Review a submission with score-based XP (Admin only)."""
    if data.status not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="Invalid review status")

    score = int(data.score) if data.score is not None else (10 if data.status == "approved" else 0)
    if score < 0 or score > 10:
        raise HTTPException(status_code=400, detail="Score must be in range 0..10")

    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id, user_id, task_id, status, COALESCE(code, content) as solution, code_simhash
            FROM submissions
            WHERE id = ?
            """,
            (submission_id,),
        )
        sub = cursor.fetchone()
        if not sub:
            raise HTTPException(status_code=404, detail="Submission not found")
        if sub["status"] != "pending":
            raise HTTPException(status_code=409, detail="Submission is already reviewed")

        cursor.execute(
            """
            UPDATE submissions
            SET status = ?, feedback = ?, score = ?, reviewed_at = CURRENT_TIMESTAMP, reviewer_id = ?, review_reason = ?
            WHERE id = ? AND status = 'pending'
            """,
            (data.status, data.feedback, score, admin["id"], data.feedback, submission_id),
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=409, detail="Submission is already reviewed")

        xp_awarded = 0
        target_user_id = sub["user_id"]
        target_task_id = sub["task_id"]
        if data.status == "approved":
            data_json = load_tasks()
            task = next((t for t in data_json.get("tasks", []) if t["id"] == sub["task_id"]), None)
            max_xp = int(task.get("xp", 0)) if task else 0
            base_xp = int(max_xp * score / 10)

            res = process_task_completion(cursor, sub["user_id"], sub["task_id"], base_xp, sub["solution"], sub["code_simhash"])
            if res["status"] == "success":
                xp_awarded = int(res.get("xp_earned") or 0)
                log_security(
                    "SUBMISSION_APPROVED",
                    user=admin["username"],
                    details=f"submission_id={submission_id}, score={score}, xp={xp_awarded}",
                )
            else:
                xp_awarded = 0

        cursor.execute(
            """
            INSERT INTO audit_log (actor_user_id, actor_username, action, target_user_id, target_task_id, delta_xp, meta_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                admin["id"],
                admin.get("username"),
                "SUBMISSION_REVIEWED",
                target_user_id,
                target_task_id,
                xp_awarded,
                json.dumps({"submission_id": submission_id, "status": data.status, "score": score}, ensure_ascii=False),
            ),
        )

        conn.commit()
    return {"message": "Submission reviewed", "score": score, "xp_awarded": xp_awarded}

@app.get("/api/admin/stats")
def get_stats(admin: dict = Depends(require_admin)):
    """Get system statistics (Admin only)."""
    with get_db() as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) as count FROM users WHERE role = 'student'")
        student_count = cursor.fetchone()["count"]
        
        cursor.execute("SELECT COUNT(*) as count FROM completed_tasks")
        completed_count = cursor.fetchone()["count"]
        
        cursor.execute("SELECT COUNT(*) as count FROM submissions WHERE status = 'pending'")
        pending_count = cursor.fetchone()["count"]
        
        cursor.execute("""
            SELECT u.display_name, u.xp, u.level
            FROM users u WHERE u.role = 'student'
            ORDER BY u.xp DESC LIMIT 5
        """)
        leaderboard = [dict(row) for row in cursor.fetchall()]
    
    return {
        "students": student_count,
        "completed_tasks": completed_count,
        "pending_reviews": pending_count,
        "leaderboard": leaderboard
    }


@app.get("/api/admin/backup/sqlite")
def download_sqlite_backup(admin: dict = Depends(require_admin)):
    """Create and download a consistent SQLite snapshot (Admin only)."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_name = f"academy_backup_{timestamp}.db"
    fd, temp_path = tempfile.mkstemp(prefix="pandora_backup_", suffix=".db")
    os.close(fd)

    try:
        with sqlite3.connect(DATABASE, timeout=max(1.0, SQLITE_TIMEOUT_S), check_same_thread=False) as src_conn:
            with sqlite3.connect(temp_path) as dst_conn:
                src_conn.backup(dst_conn)
                dst_conn.commit()
    except Exception as e:
        try:
            os.remove(temp_path)
        except OSError:
            pass
        log_error("Failed to create SQLite backup", e)
        raise HTTPException(status_code=500, detail="Backup creation failed")

    return FileResponse(
        temp_path,
        media_type="application/octet-stream",
        filename=backup_name,
        headers={"Cache-Control": "no-store"},
        background=BackgroundTask(os.remove, temp_path),
    )

# ==================== TASK ROUTES ====================

_TASKS_CACHE: dict = {"mtime": None, "legacy_mtime": None, "data": None}

ARCHIVED_TASK_ID_PREFIXES: tuple[str, ...] = (
    # Legacy packs: generic/duplicate content and (historically) mixed schemas.
    "py_nova_",
    "js_nova_",
    "fe_nova_",
    "sc_nova_",
    "py_v3_",
    "js_v3_",
    "fe_v3_",
    "sc_v3_",
)

def is_archived_task_id(task_id: str) -> bool:
    tid = str(task_id or "")
    return any(tid.startswith(p) for p in ARCHIVED_TASK_ID_PREFIXES)

def _dedupe_resources(items: list[dict]) -> list[dict]:
    """Deduplicate resources by URL, preserving order."""
    seen: set[str] = set()
    out: list[dict] = []
    for it in items or []:
        if not isinstance(it, dict):
            continue
        url = str(it.get("url") or "").strip()
        title = str(it.get("title") or "").strip()
        if not url:
            continue
        if url in seen:
            continue
        seen.add(url)
        out.append({"title": title or url, "url": url})
    return out

_DEFAULT_RESOURCES: dict[str, dict[str, list[dict]]] = {
    "python": {
        "docs": [
            {"title": "Python: tutorial (EN)", "url": "https://docs.python.org/3/tutorial/index.html"},
        ],
        "videos": [
            {"title": "Python: основы (freeCodeCamp, EN)", "url": "https://www.youtube.com/watch?v=rfscVS0vtbw"},
        ],
    },
    "javascript": {
        "docs": [
            {"title": "MDN: руководство по JavaScript (RU)", "url": "https://developer.mozilla.org/ru/docs/Web/JavaScript/Guide"},
        ],
        "videos": [
            {"title": "JavaScript: основы (freeCodeCamp, EN)", "url": "https://www.youtube.com/watch?v=PkZNo7MFNFg"},
        ],
    },
    "frontend": {
        "docs": [
            {"title": "MDN: HTML основы (RU)", "url": "https://developer.mozilla.org/ru/docs/Learn/Getting_started_with_the_web/HTML_basics"},
            {"title": "MDN: CSS основы (RU)", "url": "https://developer.mozilla.org/ru/docs/Learn/Getting_started_with_the_web/CSS_basics"},
        ],
        "videos": [
            {"title": "HTML: полный курс (freeCodeCamp, EN)", "url": "https://www.youtube.com/watch?v=pQN-pnXPaVg"},
            {"title": "CSS: crash course (Traversy Media, EN)", "url": "https://www.youtube.com/watch?v=yfoY53QXEnI"},
        ],
    },
    "scratch": {
        "docs": [
            {"title": "Scratch: идеи и туториалы", "url": "https://scratch.mit.edu/ideas"},
            {"title": "Scratch Wiki: блоки", "url": "https://en.scratch-wiki.info/wiki/Blocks"},
        ],
        "videos": [
            {"title": "Scratch Team: видео", "url": "https://www.youtube.com/@ScratchTeam/videos"},
        ],
    },
}

def resources_for_task(task: dict) -> dict:
    """
    Build per-task learning resources (docs + videos).
    Stored server-side so the client stays dumb and tasks.json stays schema-compatible.
    """
    category = str(task.get("category") or "").lower()
    explicit = task.get("resources") if isinstance(task.get("resources"), dict) else {}
    explicit_docs = explicit.get("docs") if isinstance(explicit.get("docs"), list) else []
    explicit_videos = explicit.get("videos") if isinstance(explicit.get("videos"), list) else []

    # If tasks.json provides resources explicitly (and both groups are non-empty),
    # treat them as authoritative.
    if explicit_docs and explicit_videos:
        return {"docs": _dedupe_resources(explicit_docs), "videos": _dedupe_resources(explicit_videos)}

    text = " ".join(
        [
            str(task.get("title") or ""),
            str(task.get("story") or ""),
            str(task.get("description") or ""),
            str(task.get("initial_code") or ""),
        ]
    ).lower()

    docs: list[dict] = []
    videos: list[dict] = []

    if explicit_docs:
        docs.extend(explicit_docs)
    if explicit_videos:
        videos.extend(explicit_videos)

    defaults = _DEFAULT_RESOURCES.get(category) or {}
    docs.extend(defaults.get("docs") or [])
    videos.extend(defaults.get("videos") or [])

    # Concept-sensitive docs (best-effort keyword matching; falls back to defaults).
    if category == "python":
        if any(k in text for k in ("регуляр", "regex", "re.")):
            docs.insert(0, {"title": "Python: re module (EN)", "url": "https://docs.python.org/3/library/re.html"})
        elif any(k in text for k in ("словар", "dict", "ключ", "{")):
            docs.insert(0, {"title": "Python: dictionaries (EN)", "url": "https://docs.python.org/3/tutorial/datastructures.html#dictionaries"})
        elif any(k in text for k in ("спис", "list", "[")):
            docs.insert(0, {"title": "Python: lists (EN)", "url": "https://docs.python.org/3/tutorial/introduction.html#lists"})
        elif any(k in text for k in ("цикл", "for ", "while ")):
            docs.insert(0, {"title": "Python: control flow (EN)", "url": "https://docs.python.org/3/tutorial/controlflow.html"})
        elif "функц" in text or "def " in text:
            docs.insert(0, {"title": "Python: defining functions (EN)", "url": "https://docs.python.org/3/tutorial/controlflow.html#defining-functions"})
        elif any(k in text for k in ("строк", "string", "split", "join")):
            docs.insert(0, {"title": "Python: strings (EN)", "url": "https://docs.python.org/3/tutorial/introduction.html#strings"})
        elif any(k in text for k in ("random", "случайн")):
            docs.insert(0, {"title": "Python: random module (EN)", "url": "https://docs.python.org/3/library/random.html"})
        elif any(k in text for k in ("множ", "set(")):
            docs.insert(0, {"title": "Python: sets (EN)", "url": "https://docs.python.org/3/tutorial/datastructures.html#sets"})

    elif category == "javascript":
        if any(k in text for k in ("регуляр", "regex", "/g", "regexp")):
            docs.insert(0, {"title": "MDN: регулярные выражения (RU)", "url": "https://developer.mozilla.org/ru/docs/Web/JavaScript/Guide/Regular_Expressions"})
        elif any(k in text for k in ("массив", "array", "[")):
            docs.insert(0, {"title": "MDN: Array (RU)", "url": "https://developer.mozilla.org/ru/docs/Web/JavaScript/Reference/Global_Objects/Array"})
        elif any(k in text for k in ("объект", "object", "{")):
            docs.insert(0, {"title": "MDN: объекты (RU)", "url": "https://developer.mozilla.org/ru/docs/Web/JavaScript/Guide/Working_with_objects"})
        elif "функц" in text or "function" in text or "=>" in text:
            docs.insert(0, {"title": "MDN: функции (RU)", "url": "https://developer.mozilla.org/ru/docs/Web/JavaScript/Guide/Functions"})
        elif any(k in text for k in ("строк", "string", ".split", ".join")):
            docs.insert(0, {"title": "MDN: String (RU)", "url": "https://developer.mozilla.org/ru/docs/Web/JavaScript/Reference/Global_Objects/String"})
        elif any(k in text for k in ("math", "случайн", "random")):
            docs.insert(0, {"title": "MDN: Math (RU)", "url": "https://developer.mozilla.org/ru/docs/Web/JavaScript/Reference/Global_Objects/Math"})
        elif "date" in text or "время" in text:
            docs.insert(0, {"title": "MDN: Date (RU)", "url": "https://developer.mozilla.org/ru/docs/Web/JavaScript/Reference/Global_Objects/Date"})

    elif category == "frontend":
        if "grid" in text:
            docs.insert(0, {"title": "MDN: CSS Grid (RU)", "url": "https://developer.mozilla.org/ru/docs/Learn/CSS/CSS_layout/Grids"})
        if "flex" in text:
            docs.insert(0, {"title": "MDN: Flexbox (RU)", "url": "https://developer.mozilla.org/ru/docs/Learn/CSS/CSS_layout/Flexbox"})
        if any(k in text for k in ("@media", "адаптив", "responsive", "768px")):
            docs.insert(0, {"title": "MDN: media queries (RU)", "url": "https://developer.mozilla.org/ru/docs/Web/CSS/Media_Queries/Using_media_queries"})
        if any(k in text for k in ("--", ":root", "переменн")):
            docs.insert(0, {"title": "MDN: CSS-переменные (RU)", "url": "https://developer.mozilla.org/ru/docs/Web/CSS/Using_CSS_custom_properties"})
        if any(k in text for k in ("position", "absolute", "relative", "fixed", "sticky")):
            docs.insert(0, {"title": "MDN: position (RU)", "url": "https://developer.mozilla.org/ru/docs/Web/CSS/position"})
        if any(k in text for k in ("margin", "padding", "border", "box")):
            docs.insert(0, {"title": "MDN: блочная модель (RU)", "url": "https://developer.mozilla.org/ru/docs/Learn/CSS/Building_blocks/The_box_model"})

    elif category == "scratch":
        if any(k in text for k in ("движ", "шаг", "поверн", "координат")):
            docs.insert(0, {"title": "Scratch Wiki: Motion Blocks", "url": "https://en.scratch-wiki.info/wiki/Motion_Blocks"})
        elif any(k in text for k in ("костюм", "сказать", "говор", "внешн")):
            docs.insert(0, {"title": "Scratch Wiki: Looks Blocks", "url": "https://en.scratch-wiki.info/wiki/Looks_Blocks"})
        elif any(k in text for k in ("звук", "громк")):
            docs.insert(0, {"title": "Scratch Wiki: Sound Blocks", "url": "https://en.scratch-wiki.info/wiki/Sound_Blocks"})
        elif any(k in text for k in ("флаж", "клик", "клавиш", "сообщен", "broadcast")):
            docs.insert(0, {"title": "Scratch Wiki: Events Blocks", "url": "https://en.scratch-wiki.info/wiki/Events_Blocks"})
        elif any(k in text for k in ("всегда", "повтор", "если", "таймер", "клон")):
            docs.insert(0, {"title": "Scratch Wiki: Control Blocks", "url": "https://en.scratch-wiki.info/wiki/Control_Blocks"})
        elif any(k in text for k in ("спрос", "касается", "сенсор")):
            docs.insert(0, {"title": "Scratch Wiki: Sensing Blocks", "url": "https://en.scratch-wiki.info/wiki/Sensing_Blocks"})
        elif any(k in text for k in ("переменн", "score", "level")):
            docs.insert(0, {"title": "Scratch Wiki: Variables Blocks", "url": "https://en.scratch-wiki.info/wiki/Variables_Blocks"})
        elif any(k in text for k in (">", "<", "=", "оператор")):
            docs.insert(0, {"title": "Scratch Wiki: Operators Blocks", "url": "https://en.scratch-wiki.info/wiki/Operators_Blocks"})

    return {"docs": _dedupe_resources(docs), "videos": _dedupe_resources(videos)}

def load_tasks() -> dict:
    """Load tasks.json (+ optional tasks_legacy.json) with a simple mtime-based cache."""
    tasks_path = Path("tasks.json")
    legacy_path = Path("tasks_legacy.json")
    try:
        mtime = tasks_path.stat().st_mtime
        legacy_mtime = legacy_path.stat().st_mtime if legacy_path.exists() else None

        if (
            _TASKS_CACHE["data"] is None
            or _TASKS_CACHE["mtime"] != mtime
            or _TASKS_CACHE["legacy_mtime"] != legacy_mtime
        ):
            curated = json.loads(tasks_path.read_text(encoding="utf-8"))
            curated_tasks = curated.get("tasks", []) if isinstance(curated, dict) else []

            legacy_tasks = []
            if legacy_path.exists():
                try:
                    legacy = json.loads(legacy_path.read_text(encoding="utf-8"))
                    legacy_tasks = legacy.get("tasks", []) if isinstance(legacy, dict) else []
                except Exception as e:
                    log_error("Failed to load tasks_legacy.json", e)
                    legacy_tasks = []

            combined = {
                "meta": curated.get("meta", {}) if isinstance(curated, dict) else {},
                "categories": curated.get("categories", []) if isinstance(curated, dict) else [],
                "tasks": (curated_tasks if isinstance(curated_tasks, list) else [])
                + (legacy_tasks if isinstance(legacy_tasks, list) else []),
            }
            _TASKS_CACHE["data"] = combined
            _TASKS_CACHE["mtime"] = mtime
            _TASKS_CACHE["legacy_mtime"] = legacy_mtime

        return _TASKS_CACHE["data"] or {"meta": {}, "categories": [], "tasks": []}
    except FileNotFoundError:
        return {"meta": {}, "categories": [], "tasks": []}
    except Exception as e:
        log_error("Failed to load tasks.json", e)
        return {"meta": {}, "categories": [], "tasks": []}

def get_task(task_id: str) -> Optional[dict]:
    data = load_tasks()
    for t in data.get("tasks", []):
        if t.get("id") == task_id:
            return t
    return None

def public_task(task: dict) -> dict:
    """Return a safe task payload for students (no expected answers)."""
    logic = task.get("check_logic") or {}
    cases = logic.get("cases") or []
    return {
        "id": task.get("id"),
        "category": task.get("category"),
        "tier": task.get("tier"),
        "xp": task.get("xp"),
        "title": task.get("title"),
        "story": task.get("story"),
        "description": task.get("description"),
        "initial_code": task.get("initial_code"),
        "resources": resources_for_task(task),
        "prerequisites": task.get("prerequisites") or [],
        "check": {
            "engine": logic.get("engine"),
            "case_count": len(cases),
        },
    }

TIER_PREV = {"C": "D", "B": "C", "A": "B", "S": "A"}
DEFAULT_UNLOCK_REQUIREMENTS = {"C": 3, "B": 3, "A": 3, "S": 3}  # 3:1 ratio by default

def _completed_task_ids(cursor, user_id: int) -> set:
    cursor.execute("SELECT task_id FROM completed_tasks WHERE user_id = ? AND is_valid != 0", (user_id,))
    return {row["task_id"] for row in cursor.fetchall()}

def _counts_by_category_and_tier(tasks_by_id: dict, completed_ids: set) -> dict:
    counts: dict = {}
    for tid in completed_ids:
        t = tasks_by_id.get(tid) or {}
        cat = t.get("category") or "unknown"
        tier = t.get("tier") or "D"
        counts.setdefault(cat, {})
        counts[cat][tier] = counts[cat].get(tier, 0) + 1
    return counts

def _unlock_state(task: dict, completed_ids: set, counts: dict) -> tuple[bool, dict]:
    """Return (unlocked, info)."""
    prereq = task.get("prerequisites") or []
    if prereq:
        missing = [p for p in prereq if p not in completed_ids]
        return (len(missing) == 0), {"type": "explicit", "missing": missing}

    tier = task.get("tier") or "D"
    if tier == "D":
        return True, {"type": "tier_gate", "requirement": None}

    prev = TIER_PREV.get(tier)
    if not prev:
        return True, {"type": "tier_gate", "requirement": None}

    category = task.get("category") or "unknown"
    need = int(DEFAULT_UNLOCK_REQUIREMENTS.get(tier, 0))
    have = int(counts.get(category, {}).get(prev, 0))
    unlocked = have >= need
    return unlocked, {
        "type": "tier_gate",
        "category": category,
        "tier": tier,
        "requires": {"tier": prev, "count": need},
        "progress": {"count": have},
    }


def _is_top7_task_by_tier(tasks_by_id: dict, task_id: str) -> bool:
    """Old-review algorithm: top 7 tasks per tier (by XP desc) go to admin review."""
    task = tasks_by_id.get(task_id) or {}
    tier = (task.get("tier") or "").upper()
    if tier not in {"D", "C", "B", "A", "S"}:
        return False
    same_tier = [t for t in tasks_by_id.values() if (t.get("tier") or "").upper() == tier]
    same_tier.sort(key=lambda t: (-int(t.get("xp") or 0), str(t.get("id") or "")))
    top_ids = {str(t.get("id")) for t in same_tier[:7]}
    return str(task_id) in top_ids


def _utc_now_sql() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _default_homework_task_ids(tasks_raw: list[dict], min_count: int = 3) -> list[str]:
    cat_weight = {"python": 0, "javascript": 1, "frontend": 2, "scratch": 3}
    tier_weight = {"D": 0, "C": 1, "B": 2, "A": 3, "S": 4}
    candidates = [
        t
        for t in tasks_raw
        if t.get("id") and not is_archived_task_id(t.get("id")) and t.get("category") in cat_weight
    ]
    candidates.sort(
        key=lambda t: (
            cat_weight.get(t.get("category"), 9),
            tier_weight.get((t.get("tier") or "D").upper(), 9),
            int(t.get("xp") or 0),
        )
    )
    return [t["id"] for t in candidates[: max(min_count, 3)]]


def _smart_select_homework_tasks(
    tasks_raw: list[dict],
    completed_ids: set[str],
    user_level: int,
    count: int = 4,
    tasks_by_id: dict | None = None,
) -> list[str]:
    """
    Personalized homework per student.

    Algorithm:
    - Only pick tasks that are UNLOCKED for this student (via _unlock_state)
    - Only pick tasks the student has NOT completed
    - Pick category where the student has the MOST completed tasks (their focus area)
    - Mix: 2 easy + 1 medium + 1 hard (relative to student's actual position)
    - Fallback: any unlocked uncompleted task
    """
    if tasks_by_id is None:
        tasks_by_id = {t.get("id"): t for t in tasks_raw if t.get("id")}

    counts = _counts_by_category_and_tier(tasks_by_id, completed_ids)
    tier_order = {"D": 0, "C": 1, "B": 2, "A": 3, "S": 4}

    # Filter: uncompleted + unlocked for this student
    candidates = []
    for t in tasks_raw:
        tid = t.get("id")
        if not tid or tid in completed_ids:
            continue
        if is_archived_task_id(tid):
            continue
        cat = t.get("category")
        if cat not in ("python", "javascript", "frontend", "scratch"):
            continue
        unlocked, _ = _unlock_state(t, completed_ids, counts)
        if unlocked:
            candidates.append(t)

    if not candidates:
        return []

    # Pick category where student has MOST completed tasks (their focus)
    completed_per_cat: dict[str, int] = {}
    for tid in completed_ids:
        ct = tasks_by_id.get(tid)
        if ct:
            c = ct.get("category", "other")
            completed_per_cat[c] = completed_per_cat.get(c, 0) + 1

    # Among candidates, group by category
    by_cat: dict[str, list[dict]] = {}
    for t in candidates:
        cat = t.get("category", "other")
        by_cat.setdefault(cat, []).append(t)

    # Prefer the category the student has progressed most in
    # If student has no completions yet, pick category with most easy tasks
    if completed_per_cat:
        best_cat = max(
            by_cat.keys(),
            key=lambda c: completed_per_cat.get(c, 0)
        )
    else:
        best_cat = max(by_cat, key=lambda c: len(by_cat[c]))

    pool = by_cat[best_cat]

    # Sort by tier (easier first), then by xp
    pool.sort(key=lambda t: (tier_order.get((t.get("tier") or "D").upper(), 0), int(t.get("xp") or 0)))

    # Split into easy / medium / hard by position in the pool
    n = len(pool)
    if n <= count:
        return [t["id"] for t in pool]

    # Split thirds: easy = first 50%, medium = next 30%, hard = last 20%
    cut1 = max(1, n * 50 // 100)
    cut2 = max(cut1 + 1, n * 80 // 100)
    easy = pool[:cut1]
    medium = pool[cut1:cut2]
    hard = pool[cut2:]

    if not medium:
        medium = easy[-1:]
        easy = easy[:-1]
    if not hard and len(medium) > 1:
        hard = medium[-1:]
        medium = medium[:-1]

    # Pick: 2 easy, 1 medium, 1 hard
    selected: list[str] = []
    for t in easy[:2]:
        selected.append(t["id"])
    for t in medium[:1]:
        selected.append(t["id"])
    for t in hard[:1]:
        selected.append(t["id"])

    # Pad if needed
    if len(selected) < count:
        for t in pool:
            if t["id"] not in selected:
                selected.append(t["id"])
            if len(selected) >= count:
                break

    return selected[:count]


def _auto_generate_homework_for_user(
    cursor, user_id: int, tasks_raw: list[dict], tasks_by_id: dict
) -> bool:
    """
    Auto-generate homework if user has no active homework set.
    Creates a set with 3-4 smart-selected tasks, 2-day deadline.
    Returns True if homework was created.
    """
    # Expire old auto-generated homework that contains locked tasks
    # so the new algorithm kicks in
    cursor.execute(
        """
        SELECT hs.id FROM homework_targets ht
        JOIN homework_sets hs ON hs.id = ht.homework_set_id
        WHERE ht.user_id = ? AND hs.status = 'active'
        AND hs.title = 'Автоматическое ДЗ'
        """,
        (user_id,),
    )
    auto_hw_ids = [row["id"] for row in cursor.fetchall()]

    completed_ids = _completed_task_ids(cursor, user_id)
    counts = _counts_by_category_and_tier(tasks_by_id, completed_ids)

    for hw_id in auto_hw_ids:
        cursor.execute(
            "SELECT task_id FROM homework_set_tasks WHERE homework_set_id = ?",
            (hw_id,),
        )
        hw_task_ids = [r["task_id"] for r in cursor.fetchall()]
        # Check if any task in this homework set is locked for this student
        has_locked = False
        for tid in hw_task_ids:
            task = tasks_by_id.get(tid)
            if task:
                unlocked, _ = _unlock_state(task, completed_ids, counts)
                if not unlocked:
                    has_locked = True
                    break
        if has_locked:
            cursor.execute(
                "UPDATE homework_sets SET status = 'expired' WHERE id = ?", (hw_id,)
            )

    # Check if user already has active homework
    cursor.execute(
        """
        SELECT COUNT(*) as cnt FROM homework_targets ht
        JOIN homework_sets hs ON hs.id = ht.homework_set_id
        WHERE ht.user_id = ? AND hs.status = 'active'
        AND hs.deadline_at > datetime('now')
        """,
        (user_id,),
    )
    active_count = int(cursor.fetchone()["cnt"])
    if active_count > 0:
        return False  # Already has active homework

    # Get user level
    cursor.execute("SELECT level FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    user_level = int(row["level"]) if row else 1

    # Smart select tasks
    task_ids = _smart_select_homework_tasks(tasks_raw, completed_ids, user_level, count=4, tasks_by_id=tasks_by_id)
    if len(task_ids) < 3:
        return False  # Not enough uncompleted tasks

    # Create homework set
    title = "Автоматическое ДЗ"
    deadline_at = (datetime.now(timezone.utc) + timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")

    # Use user_id 0 as system auto-created
    cursor.execute(
        """
        INSERT INTO homework_sets (title, created_by, deadline_at, status)
        VALUES (?, ?, ?, 'active')
        """,
        (title, user_id, deadline_at),  # created_by = user themselves (auto)
    )
    set_id = int(cursor.lastrowid)

    for tid in task_ids:
        task_xp = int((tasks_by_id.get(tid) or {}).get("xp") or 0)
        cursor.execute(
            "INSERT INTO homework_set_tasks (homework_set_id, task_id, task_xp) VALUES (?, ?, ?)",
            (set_id, tid, task_xp),
        )

    cursor.execute(
        "INSERT OR IGNORE INTO homework_targets (homework_set_id, user_id) VALUES (?, ?)",
        (set_id, user_id),
    )

    logger.info("Auto-generated homework set #%d for user %d with %d tasks", set_id, user_id, len(task_ids))
    return True


def _apply_homework_penalties_for_user(cursor, user_id: int, tasks_by_id: dict) -> list[dict]:
    cursor.execute(
        """
        SELECT ht.id as target_id, hs.id as set_id, hs.title, hs.deadline_at
        FROM homework_targets ht
        JOIN homework_sets hs ON hs.id = ht.homework_set_id
        WHERE ht.user_id = ?
          AND ht.penalty_applied = 0
          AND hs.status = 'active'
          AND hs.deadline_at <= datetime('now')
        ORDER BY hs.deadline_at ASC
        """,
        (user_id,),
    )
    rows = cursor.fetchall()
    if not rows:
        return []

    penalties = []
    for row in rows:
        set_id = int(row["set_id"])
        deadline_at = str(row["deadline_at"] or "")
        cursor.execute(
            "SELECT task_id, task_xp FROM homework_set_tasks WHERE homework_set_id = ?",
            (set_id,),
        )
        set_tasks = [dict(r) for r in cursor.fetchall()]
        if not set_tasks:
            cursor.execute(
                "UPDATE homework_targets SET penalty_applied = 1, penalty_amount = 0, penalty_applied_at = ?, notified = 0 WHERE id = ?",
                (_utc_now_sql(), int(row["target_id"])),
            )
            continue

        task_ids = [str(t["task_id"]) for t in set_tasks]
        placeholders = ",".join(["?"] * len(task_ids))
        cursor.execute(
            f"""
            SELECT task_id
            FROM completed_tasks
            WHERE user_id = ?
              AND is_valid != 0
              AND completed_at <= ?
              AND task_id IN ({placeholders})
            """,
            [user_id, deadline_at, *task_ids],
        )
        done_by_deadline = {str(r["task_id"]) for r in cursor.fetchall()}

        missed_xp = 0
        missed_tasks = []
        for t in set_tasks:
            task_id = str(t["task_id"])
            if task_id in done_by_deadline:
                continue
            xp_val = int(t.get("task_xp") or int((tasks_by_id.get(task_id) or {}).get("xp") or 0))
            missed_xp += max(0, xp_val)
            missed_tasks.append(task_id)

        penalty = max(0, missed_xp // 4)  # 25% of missed XP
        if penalty > 0:
            new_xp, new_level = apply_xp_change(
                cursor,
                user_id,
                -penalty,
                "homework_penalty",
                None,
            )
        else:
            cursor.execute("SELECT xp, level FROM users WHERE id = ?", (user_id,))
            u = cursor.fetchone()
            new_xp = int(u["xp"]) if u else 0
            new_level = int(u["level"]) if u else 1

        cursor.execute(
            """
            UPDATE homework_targets
            SET penalty_applied = 1,
                penalty_amount = ?,
                penalty_applied_at = ?,
                notified = ?,
                notified_at = ?
            WHERE id = ?
            """,
            (penalty, _utc_now_sql(), 1 if penalty > 0 else 0, _utc_now_sql() if penalty > 0 else None, int(row["target_id"])),
        )
        if penalty > 0:
            penalties.append(
                {
                    "homework_set_id": set_id,
                    "title": row["title"],
                    "missed_tasks": missed_tasks,
                    "missed_xp_sum": missed_xp,
                    "penalty": penalty,
                    "new_xp": new_xp,
                    "new_level": new_level,
                }
            )

    return penalties


def _homework_items_for_user(cursor, user_id: int, tasks_by_id: dict) -> list[dict]:
    cursor.execute(
        """
        SELECT hs.id, hs.title, hs.created_at, hs.deadline_at, hs.status,
               ht.penalty_applied, ht.penalty_amount
        FROM homework_targets ht
        JOIN homework_sets hs ON hs.id = ht.homework_set_id
        WHERE ht.user_id = ? AND hs.status = 'active'
        ORDER BY hs.deadline_at ASC, hs.id DESC
        """,
        (user_id,),
    )
    sets = [dict(r) for r in cursor.fetchall()]
    if not sets:
        return []

    completed_ids = _completed_task_ids(cursor, user_id)
    items = []
    for hs in sets:
        hs_id = int(hs["id"])
        cursor.execute(
            "SELECT task_id, task_xp FROM homework_set_tasks WHERE homework_set_id = ? ORDER BY id ASC",
            (hs_id,),
        )
        tasks_rows = [dict(r) for r in cursor.fetchall()]
        task_entries = []
        for tr in tasks_rows:
            task = tasks_by_id.get(tr["task_id"]) or {}
            task_entries.append(
                {
                    "task_id": tr["task_id"],
                    "title": task.get("title", tr["task_id"]),
                    "category": task.get("category"),
                    "tier": task.get("tier"),
                    "xp": int(tr.get("task_xp") or task.get("xp") or 0),
                    "completed": tr["task_id"] in completed_ids,
                }
            )
        items.append(
            {
                "id": hs_id,
                "title": hs["title"],
                "created_at": hs["created_at"],
                "deadline_at": hs["deadline_at"],
                "overdue": str(hs["deadline_at"] or "") <= _utc_now_sql(),
                "penalty_applied": bool(hs.get("penalty_applied")),
                "penalty_amount": int(hs.get("penalty_amount") or 0),
                "tasks": task_entries,
            }
        )
    return items

@app.get("/api/roadmap")
def get_roadmap(user: dict = Depends(require_auth)):
    """Return tasks annotated with completion + unlock state for the current user."""
    data = load_tasks()
    tasks_raw = data.get("tasks", [])
    tasks_by_id = {t.get("id"): t for t in tasks_raw if t.get("id")}

    with get_db() as conn:
        cursor = conn.cursor()
        completed_ids = _completed_task_ids(cursor, user["id"])
        
        # Get pending review task IDs
        cursor.execute(
            "SELECT task_id FROM submissions WHERE user_id = ? AND status = 'pending'",
            (user["id"],)
        )
        pending_ids = set(row["task_id"] for row in cursor.fetchall())
        
        # Include archived tasks if they are explicitly assigned as active homework
        cursor.execute(
            """
            SELECT DISTINCT hst.task_id
            FROM homework_targets ht
            JOIN homework_sets hs ON hs.id = ht.homework_set_id
            JOIN homework_set_tasks hst ON hst.homework_set_id = hs.id
            WHERE ht.user_id = ?
              AND hs.status = 'active'
            """,
            (user["id"],),
        )
        homework_ids = {str(row["task_id"]) for row in cursor.fetchall()}

    counts = _counts_by_category_and_tier(tasks_by_id, completed_ids)

    tasks = []
    for t in tasks_raw:
        tid = str(t.get("id") or "")
        if is_archived_task_id(tid) and tid not in homework_ids:
            continue
        unlocked, unlock_info = _unlock_state(t, completed_ids, counts)
        pt = public_task(t)
        pt["completed"] = pt["id"] in completed_ids
        pt["locked"] = not unlocked and not pt["completed"]
        pt["pending_review"] = pt["id"] in pending_ids
        pt["unlock"] = unlock_info
        tasks.append(pt)

    return {"meta": data.get("meta", {}), "categories": data.get("categories", []), "tasks": tasks, "counts": counts}


@app.get("/api/user/homework")
def get_my_homework(user: dict = Depends(require_auth)):
    """Return active homework sets for current user + apply overdue penalties once.
    Auto-generates homework if user has no active sets."""
    data = load_tasks()
    tasks_raw = data.get("tasks", [])
    tasks_by_id = {t.get("id"): t for t in tasks_raw if t.get("id")}

    with get_db() as conn:
        cursor = conn.cursor()
        # Auto-generate homework if none exists
        _auto_generate_homework_for_user(cursor, int(user["id"]), tasks_raw, tasks_by_id)
        penalties = _apply_homework_penalties_for_user(cursor, int(user["id"]), tasks_by_id)
        items = _homework_items_for_user(cursor, int(user["id"]), tasks_by_id)
        conn.commit()

    return {"items": items, "penalties_applied": penalties}


@app.get("/api/admin/homework")
def list_homework_sets(admin: dict = Depends(require_admin)):
    """Admin list for created homework sets."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT hs.id, hs.title, hs.created_at, hs.deadline_at, hs.status,
                   u.display_name as created_by_name
            FROM homework_sets hs
            LEFT JOIN users u ON u.id = hs.created_by
            ORDER BY hs.id DESC
            """
        )
        sets = [dict(r) for r in cursor.fetchall()]
        for hs in sets:
            cursor.execute("SELECT COUNT(*) as cnt FROM homework_set_tasks WHERE homework_set_id = ?", (int(hs["id"]),))
            hs["task_count"] = int(cursor.fetchone()["cnt"])
            cursor.execute("SELECT COUNT(*) as cnt FROM homework_targets WHERE homework_set_id = ?", (int(hs["id"]),))
            hs["target_count"] = int(cursor.fetchone()["cnt"])
    return {"items": sets}


@app.post("/api/admin/homework")
def create_homework_set(data: HomeworkAssignRequest, admin: dict = Depends(require_admin)):
    """
    Create homework set:
    - at least 3 tasks
    - deadline = 2 days
    - default targets = all students
    """
    tasks_data = load_tasks()
    tasks_raw = tasks_data.get("tasks", [])
    tasks_by_id = {t.get("id"): t for t in tasks_raw if t.get("id")}

    chosen_ids = [str(tid) for tid in (data.task_ids or []) if str(tid).strip()]
    if not chosen_ids:
        chosen_ids = _default_homework_task_ids(tasks_raw, min_count=3)
    # de-dup while preserving order
    uniq = []
    seen = set()
    for tid in chosen_ids:
        if tid in seen:
            continue
        seen.add(tid)
        uniq.append(tid)
    chosen_ids = uniq

    if len(chosen_ids) < 3:
        raise HTTPException(status_code=400, detail="Homework must include at least 3 tasks")
    missing = [tid for tid in chosen_ids if tid not in tasks_by_id]
    if missing:
        raise HTTPException(status_code=400, detail={"missing_task_ids": missing})

    title = (data.title or "").strip() or f"ДЗ #{_utc_now_sql()} (2 дня)"
    deadline_at = (datetime.now(timezone.utc) + timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")

    with get_db() as conn:
        cursor = conn.cursor()
        if data.user_ids:
            target_ids = [int(x) for x in data.user_ids]
        else:
            cursor.execute("SELECT id FROM users WHERE role = 'student'")
            target_ids = [int(r["id"]) for r in cursor.fetchall()]

        if not target_ids:
            raise HTTPException(status_code=400, detail="No target students found")

        cursor.execute(
            "INSERT INTO homework_sets (title, created_by, deadline_at, status) VALUES (?, ?, ?, 'active')",
            (title, int(admin["id"]), deadline_at),
        )
        set_id = int(cursor.lastrowid)

        for tid in chosen_ids:
            task_xp = int((tasks_by_id.get(tid) or {}).get("xp") or 0)
            cursor.execute(
                "INSERT INTO homework_set_tasks (homework_set_id, task_id, task_xp) VALUES (?, ?, ?)",
                (set_id, tid, task_xp),
            )

        for uid in target_ids:
            cursor.execute(
                "INSERT OR IGNORE INTO homework_targets (homework_set_id, user_id) VALUES (?, ?)",
                (set_id, uid),
            )

        cursor.execute(
            """
            INSERT INTO audit_log (actor_user_id, actor_username, action, target_user_id, target_task_id, delta_xp, meta_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(admin["id"]),
                admin.get("username"),
                "HOMEWORK_CREATED",
                None,
                None,
                0,
                json.dumps({"homework_set_id": set_id, "task_ids": chosen_ids, "targets": len(target_ids)}, ensure_ascii=False),
            ),
        )
        conn.commit()

    return {"message": "Homework assigned", "homework_set_id": set_id, "deadline_at": deadline_at, "task_count": len(chosen_ids), "target_count": len(target_ids)}

# ==================== INTEGRITY SIGNALS (PLAGIARISM + COMMENT BONUS) ====================

def code_sha256(code: str) -> str:
    return hashlib.sha256((code or "").encode("utf-8")).hexdigest()

def _simhash_from_features(features: list[str]) -> int:
    if not features:
        return 0
    vector = [0] * 64
    for feat in features:
        h = int.from_bytes(hashlib.blake2b(feat.encode("utf-8"), digest_size=8).digest(), "big", signed=False)
        for i in range(64):
            vector[i] += 1 if ((h >> i) & 1) else -1
    out = 0
    for i, score in enumerate(vector):
        if score > 0:
            out |= (1 << i)
    return out

def _python_features(code: str) -> list[str]:
    import io as _io

    tokens: list[str] = []
    try:
        for tok in tokenize.generate_tokens(_io.StringIO(code or "").readline):
            if tok.type in (tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT, tokenize.ENDMARKER):
                continue
            if tok.type == tokenize.COMMENT:
                continue
            if tok.type == tokenize.STRING:
                tokens.append("STR")
            elif tok.type == tokenize.NUMBER:
                tokens.append("NUM")
            elif tok.type == tokenize.NAME:
                tokens.append(tok.string if tok.string in keyword.kwlist else "ID")
            else:
                tokens.append(tok.string)
    except tokenize.TokenError:
        # Fall back to raw text fingerprinting if tokenization fails
        tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_]*|\\d+|\\S", code or "")

    # 3-grams are more robust than unigrams
    if len(tokens) >= 3:
        return [" ".join(tokens[i : i + 3]) for i in range(len(tokens) - 2)]
    return tokens

_JS_KEYWORDS = {
    "break","case","catch","class","const","continue","debugger","default","delete","do","else","export","extends",
    "finally","for","function","if","import","in","instanceof","let","new","return","super","switch","this","throw",
    "try","typeof","var","void","while","with","yield","await","async","true","false","null","undefined",
}

def _js_features(code: str) -> list[str]:
    src = code or ""
    # Strip comments (best-effort)
    src = re.sub(r"/\\*.*?\\*/", " ", src, flags=re.S)
    src = re.sub(r"//.*?$", " ", src, flags=re.M)
    # Replace strings with STR
    src = re.sub(r"(['\\\"]).*?(?<!\\\\)\\1", " STR ", src, flags=re.S)
    # Tokenize
    raw = re.findall(r"[A-Za-z_$][A-Za-z0-9_$]*|\\d+(?:\\.\\d+)?|==|!=|<=|>=|=>|\\S", src)
    tokens: list[str] = []
    for t in raw:
        if re.fullmatch(r"\\d+(?:\\.\\d+)?", t):
            tokens.append("NUM")
        elif re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*", t):
            tokens.append(t if t in _JS_KEYWORDS else "ID")
        elif t == "STR":
            tokens.append("STR")
        else:
            tokens.append(t)
    if len(tokens) >= 3:
        return [" ".join(tokens[i : i + 3]) for i in range(len(tokens) - 2)]
    return tokens

def code_simhash_hex(code: str, language: str) -> str:
    lang = (language or "").lower()
    if lang in ("python", "py"):
        features = _python_features(code)
    elif lang in ("javascript", "js"):
        features = _js_features(code)
    elif lang in ("frontend", "html", "css"):
        features = re.findall(r"[A-Za-z_][A-Za-z0-9_-]*|\\d+|\\S", code or "")
    else:
        features = re.findall(r"\\S+", code or "")
    return f"{_simhash_from_features(features):016x}"

def _hamming_distance_hex(a_hex: str, b_hex: str) -> int:
    try:
        a = int(a_hex, 16)
        b = int(b_hex, 16)
    except (TypeError, ValueError):
        return 64
    return (a ^ b).bit_count()

def plagiarism_score_for_task(cursor, task_id: str, simhash_hex: str, exclude_user_id: int) -> tuple[float, Optional[int]]:
    """
    Returns (score_0_to_1, matched_user_id).
    Score is derived from the closest simhash match across other users for the same task.
    """
    if not simhash_hex:
        return 0.0, None

    best_dist = 64
    best_uid = None

    for table in ("completed_tasks", "submissions"):
        cursor.execute(
            f"SELECT user_id, code_simhash FROM {table} WHERE task_id = ? AND user_id != ? AND code_simhash IS NOT NULL",
            (task_id, exclude_user_id),
        )
        for row in cursor.fetchall():
            dist = _hamming_distance_hex(simhash_hex, row["code_simhash"])
            if dist < best_dist:
                best_dist = dist
                best_uid = row["user_id"]

    score = 1.0 - (best_dist / 64.0) if best_uid is not None else 0.0
    return max(0.0, min(1.0, score)), best_uid

def propose_comment_bonus(task_xp: int, code: str, language: str) -> int:
    """Heuristic comment bonus proposal (admin-reviewed)."""
    base = int(task_xp or 0)
    if base <= 0:
        return 0
    lines = (code or "").splitlines()
    if len(lines) < 6:
        return 0

    lang = (language or "").lower()
    comment_lines = 0
    for line in lines:
        s = line.strip()
        if not s:
            continue
        if lang in ("python", "py") and s.startswith("#"):
            comment_lines += 1
        elif lang in ("javascript", "js") and (s.startswith("//") or s.startswith("/*") or s.startswith("*")):
            comment_lines += 1
        elif lang in ("frontend", "html", "css") and ("/*" in s or "<!--" in s):
            comment_lines += 1

    ratio = comment_lines / max(1, len(lines))
    if comment_lines < 2 or ratio < 0.06:
        return 0

    return min(max(1, int(base * 0.10)), 25)

def _normalize_code_for_template_compare(code: str) -> str:
    src = (code or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in src.split("\n")]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def _looks_like_unmodified_template(task: dict, submitted_code: str) -> bool:
    template_code = task.get("initial_code")
    if not isinstance(template_code, str) or not template_code.strip():
        return False
    return _normalize_code_for_template_compare(submitted_code) == _normalize_code_for_template_compare(template_code)

# ==================== SERVER-SIDE VERIFICATION ====================

RUNNERS_DIR = Path(__file__).resolve().parent / "runners"
PY_HARNESS = RUNNERS_DIR / "python_harness.py"
JS_HARNESS = RUNNERS_DIR / "js_harness.js"

RUNNER_MODE = (os.getenv("PANDORA_RUNNER_MODE") or "docker").lower()  # docker|local
PY_RUNNER_IMAGE = os.getenv("PANDORA_PY_RUNNER_IMAGE", "python:3.11-slim")
JS_RUNNER_IMAGE = os.getenv("PANDORA_JS_RUNNER_IMAGE", "node:24-slim")
STRICT_DOCKER_RUNNERS = (os.getenv("PANDORA_STRICT_DOCKER_RUNNERS") or "0") == "1"
LOW_RESOURCE_MODE = (os.getenv("PANDORA_LOW_RESOURCE_MODE") or "0") == "1"
SKIP_AUTOCHECK_REVIEWABLE_ON_LOW_RESOURCE = (os.getenv("PANDORA_SKIP_AUTOCHECK_REVIEWABLE_ON_LOW_RESOURCE") or "0") == "1"

_default_runner_timeout = "4.5" if LOW_RESOURCE_MODE else "12.0"
_default_docker_timeout = "1.5" if LOW_RESOURCE_MODE else "3.0"
RUNNER_TIMEOUT_S = float(os.getenv("PANDORA_RUNNER_TIMEOUT_S", _default_runner_timeout))
DOCKER_RUN_TIMEOUT_S = float(os.getenv("PANDORA_DOCKER_RUN_TIMEOUT_S", _default_docker_timeout))
PY_EXEC_TIMEOUT_MS = int(os.getenv("PANDORA_PY_EXEC_TIMEOUT_MS", "2500"))
PY_CASE_TIMEOUT_MS = int(os.getenv("PANDORA_PY_CASE_TIMEOUT_MS", "1200"))
JS_VM_TIMEOUT_MS = int(os.getenv("PANDORA_JS_VM_TIMEOUT_MS", "1500"))
RUNNER_MEMORY = os.getenv("PANDORA_RUNNER_MEMORY", "256m")
RUNNER_CPUS = os.getenv("PANDORA_RUNNER_CPUS", "0.5")
RUNNER_CONCURRENCY = int(os.getenv("PANDORA_RUNNER_CONCURRENCY", "1" if LOW_RESOURCE_MODE else "2"))
ALLOW_UNSAFE_LOCAL_RUNNERS = (os.getenv("PANDORA_ALLOW_UNSAFE_LOCAL_RUNNERS") or "0") == "1"

RUNNER_SEMAPHORE = __import__('threading').Semaphore(max(1, RUNNER_CONCURRENCY))
_DOCKER_HEALTH_CACHE: dict[str, float | bool] = {"checked_at": 0.0, "ok": False}
_DOCKER_HEALTH_TTL_S = float(os.getenv("PANDORA_DOCKER_HEALTH_TTL_S", "30"))
_DOCKER_IMAGE_CACHE: dict[str, dict[str, float | bool]] = {}
_DOCKER_IMAGE_TTL_S = float(os.getenv("PANDORA_DOCKER_IMAGE_TTL_S", "60"))
_LOCAL_FALLBACK_WARNED: set[str] = set()

def _docker_available() -> bool:
    return shutil.which("docker") is not None


def _docker_healthy() -> bool:
    """Fast health probe for Docker daemon availability."""
    if not _docker_available():
        return False

    now = time.monotonic()
    checked_at = float(_DOCKER_HEALTH_CACHE.get("checked_at") or 0.0)
    if (now - checked_at) < _DOCKER_HEALTH_TTL_S:
        return bool(_DOCKER_HEALTH_CACHE.get("ok"))

    ok = False
    try:
        probe = subprocess.run(
            ["docker", "info", "--format", "{{.ServerVersion}}"],
            capture_output=True,
            timeout=1.5,
            check=False,
        )
        ok = probe.returncode == 0 and bool((probe.stdout or b"").strip())
    except Exception:
        ok = False

    _DOCKER_HEALTH_CACHE["checked_at"] = now
    _DOCKER_HEALTH_CACHE["ok"] = ok
    return ok


def _docker_image_ready(image: str) -> bool:
    """Check that a Docker image is already present locally (no pull on request path)."""
    if not _docker_available():
        return False
    key = str(image or "")
    if not key:
        return False

    now = time.monotonic()
    cached = _DOCKER_IMAGE_CACHE.get(key)
    if cached and (now - float(cached.get("checked_at") or 0.0)) < _DOCKER_IMAGE_TTL_S:
        return bool(cached.get("ok"))

    ok = False
    try:
        probe = subprocess.run(
            ["docker", "image", "inspect", key],
            capture_output=True,
            timeout=1.5,
            check=False,
        )
        ok = probe.returncode == 0
    except Exception:
        ok = False

    _DOCKER_IMAGE_CACHE[key] = {"checked_at": now, "ok": ok}
    return ok


def _effective_timeout_for_cmd(cmd: list[str]) -> float:
    if cmd and cmd[0] == "docker":
        return max(0.8, float(DOCKER_RUN_TIMEOUT_S))
    return max(0.8, float(RUNNER_TIMEOUT_S))

def _run_harness_subprocess(cmd: list[str], payload: dict, timeout_s: float) -> tuple[dict, int, str]:
    """Return (result_json, runtime_ms, stderr_text)."""
    started = time.monotonic()
    try:
        res = subprocess.run(
            cmd,
            input=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            capture_output=True,
            timeout=timeout_s,
            check=False,
        )
        runtime_ms = int((time.monotonic() - started) * 1000)
    except subprocess.TimeoutExpired:
        runtime_ms = int((time.monotonic() - started) * 1000)
        return (
            {"passed": False, "exec_error": {"type": "Timeout", "message": "Verification timed out", "trace": ""}, "stdout": "", "cases": []},
            runtime_ms,
            "",
        )
    except Exception as e:  # noqa: BLE001
        runtime_ms = int((time.monotonic() - started) * 1000)
        return (
            {"passed": False, "exec_error": {"type": type(e).__name__, "message": str(e), "trace": ""}, "stdout": "", "cases": []},
            runtime_ms,
            "",
        )

    stderr = (res.stderr or b"").decode("utf-8", errors="replace")[:4000]
    stdout_text = (res.stdout or b"").decode("utf-8", errors="replace")
    try:
        parsed = json.loads(stdout_text or "{}")
        if not isinstance(parsed, dict):
            raise ValueError("Harness output is not an object")
        return parsed, runtime_ms, stderr
    except Exception:
        return (
            {
                "passed": False,
                "exec_error": {"type": "HarnessError", "message": "Invalid harness output", "trace": ""},
                "stdout": (stdout_text or "")[:4000],
                "cases": [],
            },
            runtime_ms,
            stderr,
        )

def _docker_cmd_base() -> list[str]:
    return [
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "--memory",
        RUNNER_MEMORY,
        "--cpus",
        RUNNER_CPUS,
        "--pids-limit",
        "64",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--tmpfs",
        "/tmp:rw,nosuid,nodev,size=64m",
        "--ulimit",
        "nofile=64:64",
        "--ulimit",
        "fsize=1048576:1048576",
        "-v",
        f"{RUNNERS_DIR}:/runner:ro",
    ]

def verify_python_sync(code: str, cases: list[dict]) -> tuple[dict, int]:
    payload = {
        "code": code or "",
        "cases": cases or [],
        "max_stdout": 4000,
        "exec_timeout_ms": max(250, int(PY_EXEC_TIMEOUT_MS)),
        "case_timeout_ms": max(150, int(PY_CASE_TIMEOUT_MS)),
    }

    cmd: Optional[list[str]] = None
    if RUNNER_MODE == "docker":
        if _docker_healthy() and _docker_image_ready(PY_RUNNER_IMAGE):
            cmd = _docker_cmd_base() + [PY_RUNNER_IMAGE, "python3", "-I", "-S", "/runner/python_harness.py"]
        elif STRICT_DOCKER_RUNNERS and not ALLOW_UNSAFE_LOCAL_RUNNERS:
            return (
                {"passed": False, "exec_error": {"type": "RunnerUnavailable", "message": "Docker runner is not healthy", "trace": ""}, "stdout": "", "cases": []},
                0,
            )
        else:
            if "python" not in _LOCAL_FALLBACK_WARNED:
                logger.warning("Docker runner unavailable; falling back to local Python harness")
                _LOCAL_FALLBACK_WARNED.add("python")
            cmd = [sys.executable, "-I", "-S", str(PY_HARNESS)]
    else:
        cmd = [sys.executable, "-I", "-S", str(PY_HARNESS)]

    result, runtime_ms, _stderr = _run_harness_subprocess(cmd, payload, _effective_timeout_for_cmd(cmd))

    # If Docker runner stalled/timed out, degrade gracefully to local harness for this and next attempts.
    if (
        cmd
        and cmd[0] == "docker"
        and (result.get("exec_error") or {}).get("type") == "Timeout"
        and not (STRICT_DOCKER_RUNNERS and not ALLOW_UNSAFE_LOCAL_RUNNERS)
    ):
        _DOCKER_HEALTH_CACHE["checked_at"] = time.monotonic()
        _DOCKER_HEALTH_CACHE["ok"] = False
        if "python-timeout-fallback" not in _LOCAL_FALLBACK_WARNED:
            logger.warning("Docker Python runner timed out; switching to local harness fallback")
            _LOCAL_FALLBACK_WARNED.add("python-timeout-fallback")
        local_cmd = [sys.executable, "-I", "-S", str(PY_HARNESS)]
        result, runtime_ms, _stderr = _run_harness_subprocess(local_cmd, payload, _effective_timeout_for_cmd(local_cmd))
    return result, runtime_ms

def verify_javascript_sync(code: str, cases: list[dict]) -> tuple[dict, int]:
    payload = {"code": code or "", "cases": cases or [], "timeout_ms": max(250, int(JS_VM_TIMEOUT_MS))}

    cmd: Optional[list[str]] = None
    if RUNNER_MODE == "docker":
        if _docker_healthy() and _docker_image_ready(JS_RUNNER_IMAGE):
            cmd = _docker_cmd_base() + [
                JS_RUNNER_IMAGE,
                "node",
                "--permission",
                "--allow-fs-read=/runner",
                "/runner/js_harness.js",
            ]
        elif STRICT_DOCKER_RUNNERS and not ALLOW_UNSAFE_LOCAL_RUNNERS:
            return (
                {"passed": False, "exec_error": {"type": "RunnerUnavailable", "message": "Docker runner is not healthy", "trace": ""}, "stdout": "", "cases": []},
                0,
            )
        else:
            if "javascript" not in _LOCAL_FALLBACK_WARNED:
                logger.warning("Docker runner unavailable; falling back to local JS harness")
                _LOCAL_FALLBACK_WARNED.add("javascript")
            cmd = ["node", "--permission", f"--allow-fs-read={RUNNERS_DIR}", str(JS_HARNESS)]
    else:
        cmd = ["node", "--permission", f"--allow-fs-read={RUNNERS_DIR}", str(JS_HARNESS)]

    result, runtime_ms, _stderr = _run_harness_subprocess(cmd, payload, _effective_timeout_for_cmd(cmd))

    if (
        cmd
        and cmd[0] == "docker"
        and (result.get("exec_error") or {}).get("type") == "Timeout"
        and not (STRICT_DOCKER_RUNNERS and not ALLOW_UNSAFE_LOCAL_RUNNERS)
    ):
        _DOCKER_HEALTH_CACHE["checked_at"] = time.monotonic()
        _DOCKER_HEALTH_CACHE["ok"] = False
        if "javascript-timeout-fallback" not in _LOCAL_FALLBACK_WARNED:
            logger.warning("Docker JS runner timed out; switching to local harness fallback")
            _LOCAL_FALLBACK_WARNED.add("javascript-timeout-fallback")
        local_cmd = ["node", "--permission", f"--allow-fs-read={RUNNERS_DIR}", str(JS_HARNESS)]
        result, runtime_ms, _stderr = _run_harness_subprocess(local_cmd, payload, _effective_timeout_for_cmd(local_cmd))
    return result, runtime_ms

def verify_frontend_sync(code: str, logic: dict) -> tuple[dict, int]:
    started = time.monotonic()
    src = code or ""
    # Strip HTML/CSS comments (best-effort) to reduce trivial bypasses
    src_no_comments = re.sub(r"/\*.*?\*/", " ", src, flags=re.S)
    src_no_comments = re.sub(r"<!--.*?-->", " ", src_no_comments, flags=re.S)
    text_only = html.unescape(re.sub(r"<[^>]+>", " ", src_no_comments))

    def _norm(s: str) -> str:
        return re.sub(r"\s+", " ", (s or "").strip()).lower()

    def _selector_exists(selector: str) -> bool:
        sel = (selector or "").strip()
        if not sel:
            return False
        if sel.startswith("."):
            cls = re.escape(sel[1:])
            return bool(re.search(rf"class\s*=\s*[\"'][^\"']*\b{cls}\b[^\"']*[\"']", src_no_comments, flags=re.I))
        if sel.startswith("#"):
            sid = re.escape(sel[1:])
            return bool(re.search(rf"id\s*=\s*[\"']{sid}[\"']", src_no_comments, flags=re.I))
        return bool(re.search(rf"<\s*{re.escape(sel)}(?:\s|>)", src_no_comments, flags=re.I))

    def _css_property(selector: str, prop: str) -> Optional[str]:
        sel = (selector or "").strip()
        prop_name = (prop or "").strip()
        if not sel or not prop_name:
            return None

        sel_pattern = re.escape(sel)
        prop_pattern = re.escape(prop_name)

        # Look in CSS rules first.
        for block in re.findall(rf"{sel_pattern}\s*\{{(.*?)\}}", src_no_comments, flags=re.I | re.S):
            m = re.search(rf"{prop_pattern}\s*:\s*([^;\}}]+)", block, flags=re.I)
            if m:
                return m.group(1).strip()

        # Fallback: look in inline style for simple selectors.
        if sel.startswith("."):
            cls = re.escape(sel[1:])
            pat = rf"<[^>]*class\s*=\s*[\"'][^\"']*\b{cls}\b[^\"']*[\"'][^>]*style\s*=\s*[\"']([^\"']+)[\"']"
        elif sel.startswith("#"):
            sid = re.escape(sel[1:])
            pat = rf"<[^>]*id\s*=\s*[\"']{sid}[\"'][^>]*style\s*=\s*[\"']([^\"']+)[\"']"
        else:
            tag = re.escape(sel)
            pat = rf"<\s*{tag}[^>]*style\s*=\s*[\"']([^\"']+)[\"']"

        for inline_style in re.findall(pat, src_no_comments, flags=re.I):
            m = re.search(rf"{prop_pattern}\s*:\s*([^;]+)", inline_style, flags=re.I)
            if m:
                return m.group(1).strip()
        return None

    cases = (logic or {}).get("cases") or []
    if not cases and (logic or {}).get("content_contain"):
        cases = [{"type": "content_contain", "expected": (logic or {}).get("content_contain")}]

    results = []
    passed = True
    for c in cases:
        expected = (c or {}).get("expected")
        label = expected if isinstance(expected, str) else json.dumps(expected, ensure_ascii=False)
        ok = False
        err = None
        actual = None
        try:
            case_type = (c or {}).get("type") or "content_contain"
            if case_type == "content_contain" and isinstance(expected, str):
                ok = expected in src_no_comments
            elif case_type == "content_regex" and isinstance(expected, str):
                ok = bool(re.search(expected, src_no_comments, flags=re.I | re.S))
            elif case_type == "selector_exists" and isinstance(expected, str):
                ok = _selector_exists(expected)
            elif case_type == "text_contains" and isinstance(expected, str):
                actual = _norm(text_only)
                ok = _norm(expected) in actual
            elif case_type == "css_property" and isinstance(expected, dict):
                selector = str(expected.get("selector") or "")
                prop = str(expected.get("property") or "")
                exp_val = str(expected.get("value") or "")
                actual = _css_property(selector, prop)
                ok = actual is not None and (
                    _norm(actual) == _norm(exp_val)
                    or _norm(exp_val) in _norm(actual)
                )
            elif isinstance(expected, str):
                ok = expected in src_no_comments
            else:
                err = "Unsupported frontend case"
                ok = False
        except Exception as e:  # noqa: BLE001
            err = f"{type(e).__name__}: {e}"
            ok = False
        if not ok:
            passed = False
        results.append({"label": str(label)[:200], "passed": bool(ok), "expected": expected, "actual": actual, "error": err})

    runtime_ms = int((time.monotonic() - started) * 1000)
    return {"passed": bool(passed), "exec_error": None, "stdout": "", "cases": results}, runtime_ms

# ==================== ANTI-CHEAT: HARDCODE DETECTION ====================

import re as _re_anticheat

def _detect_hardcoded_solution(code: str, language: str) -> list[str]:
    """
    Static analysis: detect if code contains hardcoded return values
    without actually using function parameters.
    Returns list of integrity flags (empty = clean).
    """
    flags = []
    code_stripped = code.strip()

    if language in ("python",):
        # Find all function defs and check if params are used in body
        func_pattern = _re_anticheat.compile(
            r'def\s+(\w+)\s*\(([^)]*)\)\s*:', _re_anticheat.MULTILINE
        )
        for m in func_pattern.finditer(code_stripped):
            fname = m.group(1)
            params_str = m.group(2).strip()
            if not params_str or params_str == "self":
                continue
            # Extract param names
            params = [p.strip().split("=")[0].strip().split(":")[0].strip()
                      for p in params_str.split(",") if p.strip() and p.strip() != "self"]
            params = [p for p in params if p and p != "*" and not p.startswith("*")]
            if not params:
                continue
            # Get function body (everything after the def until next def or end)
            body_start = m.end()
            next_def = _re_anticheat.search(r'\ndef\s+\w+\s*\(', code_stripped[body_start:])
            body = code_stripped[body_start:body_start + next_def.start()] if next_def else code_stripped[body_start:]
            # Remove comments and strings for analysis
            body_clean = _re_anticheat.sub(r'#[^\n]*', '', body)
            body_clean = _re_anticheat.sub(r'"""[\s\S]*?"""', '', body_clean)
            body_clean = _re_anticheat.sub(r"'''[\s\S]*?'''", '', body_clean)
            # Check if ANY parameter is referenced in the body
            params_used = any(
                _re_anticheat.search(r'\b' + _re_anticheat.escape(p) + r'\b', body_clean)
                for p in params
            )
            if not params_used:
                flags.append(f"params_unused:{fname}")
            # Check for pure hardcoded return (only returns a literal)
            returns = _re_anticheat.findall(r'return\s+(.+)', body_clean)
            if returns:
                for ret_val in returns:
                    ret_val = ret_val.strip().rstrip(";")
                    # Check if return value is just a string/number literal
                    if (_re_anticheat.match(r'^["\'].*["\']$', ret_val) or
                        _re_anticheat.match(r'^-?\d+\.?\d*$', ret_val) or
                        ret_val in ('True', 'False', 'None', '[]', '{}', '()')):
                        if not params_used:
                            flags.append(f"hardcoded_return:{fname}")

    elif language in ("javascript",):
        # Find function declarations and arrow functions
        func_patterns = [
            _re_anticheat.compile(r'function\s+(\w+)\s*\(([^)]*)\)\s*\{', _re_anticheat.MULTILINE),
            _re_anticheat.compile(r'(?:const|let|var)\s+(\w+)\s*=\s*(?:function)?\s*\(([^)]*)\)\s*(?:=>)?\s*\{', _re_anticheat.MULTILINE),
        ]
        for pattern in func_patterns:
            for m in pattern.finditer(code_stripped):
                fname = m.group(1)
                params_str = m.group(2).strip()
                if not params_str:
                    continue
                params = [p.strip().split("=")[0].strip() for p in params_str.split(",") if p.strip()]
                params = [p for p in params if p and not p.startswith("...")]
                if not params:
                    continue
                # Get function body
                body_start = m.end()
                brace_count = 1
                i = body_start
                while i < len(code_stripped) and brace_count > 0:
                    if code_stripped[i] == '{':
                        brace_count += 1
                    elif code_stripped[i] == '}':
                        brace_count -= 1
                    i += 1
                body = code_stripped[body_start:i-1] if i <= len(code_stripped) else code_stripped[body_start:]
                body_clean = _re_anticheat.sub(r'//[^\n]*', '', body)
                body_clean = _re_anticheat.sub(r'/\*[\s\S]*?\*/', '', body_clean)
                params_used = any(
                    _re_anticheat.search(r'\b' + _re_anticheat.escape(p) + r'\b', body_clean)
                    for p in params
                )
                if not params_used:
                    flags.append(f"params_unused:{fname}")
                returns = _re_anticheat.findall(r'return\s+(.+?)(?:;|\s*$|\s*})', body_clean)
                if returns:
                    for ret_val in returns:
                        ret_val = ret_val.strip().rstrip(";")
                        if (_re_anticheat.match(r'^["\'].*["\']$', ret_val) or
                            _re_anticheat.match(r'^`[^$]*`$', ret_val) or
                            _re_anticheat.match(r'^-?\d+\.?\d*$', ret_val) or
                            ret_val in ('true', 'false', 'null', 'undefined', '[]', '{}')):
                            if not params_used:
                                flags.append(f"hardcoded_return:{fname}")

    return list(set(flags))


def _generate_fuzz_cases(cases: list[dict], language: str) -> list[dict]:
    """
    Generate randomized fuzz test cases by mutating existing case inputs.
    These cases use different arguments to verify that code actually processes them,
    not just returns hardcoded values.
    """
    import random as _fuzz_random
    _fuzz_random.seed()  # True randomness for fuzz

    fuzz_cases = []
    for case in cases:
        if case.get("type") == "variable_value":
            continue  # Can't fuzz variable checks
        expr = case.get("code", "")
        if not expr:
            continue

        # Extract function call pattern: funcName(args)
        call_match = _re_anticheat.match(r'^(\w+)\s*\((.+)\)$', expr.strip())
        if not call_match:
            # Try IIFE or chained calls - skip fuzzing for complex expressions
            continue

        func_name = call_match.group(1)
        args_str = call_match.group(2).strip()

        # Generate fuzzed calls based on argument patterns
        fuzz_calls = []
        fuzz_expected = []

        # Simple numeric arguments: replace with random numbers
        if _re_anticheat.match(r'^-?\d+(?:\s*,\s*-?\d+)*$', args_str):
            nums = [int(x.strip()) for x in args_str.split(",")]
            for _ in range(2):
                new_nums = [_fuzz_random.randint(-99, 99) for _ in nums]
                fuzz_calls.append(f"{func_name}({', '.join(str(n) for n in new_nums)})")
        # String arguments
        elif _re_anticheat.match(r"""^['"][^'"]*['"]$""", args_str):
            rand_strs = [''.join(_fuzz_random.choices('abcdefghij', k=_fuzz_random.randint(2, 6))) for _ in range(2)]
            for s in rand_strs:
                fuzz_calls.append(f"{func_name}('{s}')")
        # Array arguments: [1,2,3]
        elif args_str.startswith('['):
            for _ in range(2):
                new_arr = [_fuzz_random.randint(0, 50) for _ in range(_fuzz_random.randint(2, 5))]
                fuzz_calls.append(f"{func_name}([{', '.join(str(n) for n in new_arr)}])")
        # Object arguments: {key: val}
        elif args_str.startswith('{'):
            keys = ['alpha', 'beta', 'gamma', 'delta', 'omega']
            for _ in range(2):
                k = _fuzz_random.choice(keys)
                v = _fuzz_random.randint(1, 100)
                fuzz_calls.append(f"{func_name}({{{k}: {v}}})")

        # We don't know expected values for fuzz cases, so we run them in a special mode:
        # The harness will run the fuzz call and verify it doesn't crash + doesn't match
        # the original hardcoded output (if it always returns the same thing regardless of input).
        for fc in fuzz_calls:
            fuzz_cases.append({
                "code": fc,
                "_fuzz": True,  # Marker for anti-cheat fuzz case
                "_original_expected": case.get("expected"),  # What the hardcoder would return
            })

    return fuzz_cases


def verify_task(task: dict, code: str) -> tuple[dict, int]:
    """Synchronous wrapper with concurrency limit for heavy runners + anti-cheat."""
    logic = task.get("check_logic") or {}
    engine = (logic.get("engine") or "").lower()
    visible_cases = logic.get("cases") or []
    hidden_cases = logic.get("hidden_cases") or []
    all_cases = (visible_cases if isinstance(visible_cases, list) else []) + (hidden_cases if isinstance(hidden_cases, list) else [])

    # --- ANTI-CHEAT: static analysis ---
    code_lang = "python" if engine in ("pyodide", "python") else "javascript" if engine in ("javascript", "js") else ""
    integrity_flags = _detect_hardcoded_solution(code, code_lang) if code_lang else []

    # --- Standard verification ---
    result = None
    runtime_ms = 0

    if engine in ("pyodide", "python"):
        with RUNNER_SEMAPHORE:
            result, runtime_ms = verify_python_sync(code, all_cases)
    elif engine in ("javascript", "js"):
        with RUNNER_SEMAPHORE:
            result, runtime_ms = verify_javascript_sync(code, all_cases)
    elif engine in ("iframe", "frontend"):
        return verify_frontend_sync(code, logic)
    else:
        return (
            {"passed": False, "exec_error": {"type": "Manual", "message": "This task requires manual review", "trace": ""}, "stdout": "", "cases": []},
            0,
        )

    # --- ANTI-CHEAT: fuzz test injection ---
    # Only run fuzz tests if main tests passed and static analysis found suspicious patterns
    if result and result.get("passed") and integrity_flags and engine in ("pyodide", "python", "javascript", "js"):
        fuzz_cases = _generate_fuzz_cases(visible_cases, code_lang)
        if fuzz_cases:
            # Run fuzz cases: each fuzz case should NOT return the same value as the original
            # We need to eval them and check if output varies with input
            fuzz_test_cases = []
            for fc in fuzz_cases:
                # Create test case that simply calls the function; we expect it NOT to throw
                fuzz_test_cases.append({
                    "code": fc["code"],
                    "expected": fc.get("_original_expected"),
                    "_anticheat_fuzz": True,
                })

            fuzz_result = None
            if engine in ("pyodide", "python"):
                with RUNNER_SEMAPHORE:
                    fuzz_result, _ = verify_python_sync(code, fuzz_test_cases)
            elif engine in ("javascript", "js"):
                with RUNNER_SEMAPHORE:
                    fuzz_result, _ = verify_javascript_sync(code, fuzz_test_cases)

            if fuzz_result:
                fuzz_case_results = fuzz_result.get("cases", [])
                # Check: if ALL fuzz cases pass (return same value as original expected),
                # the code is hardcoded - it returns the same thing regardless of input
                all_fuzz_same = all(c.get("passed") for c in fuzz_case_results) if fuzz_case_results else False
                if all_fuzz_same and len(fuzz_case_results) >= 2:
                    integrity_flags.append("fuzz_all_same_output")

    # Attach integrity flags to result
    if integrity_flags:
        result["integrity_flags"] = integrity_flags
        # If hardcoding detected: don't auto-pass, require manual review
        if any("hardcoded_return" in f or "fuzz_all_same_output" in f for f in integrity_flags):
            result["passed"] = False
            result["manual_review_required"] = True
            result["exec_error"] = {
                "type": "IntegrityCheck",
                "message": "Код выглядит захардкоженным. Решение должно обрабатывать входные данные, а не возвращать фиксированный ответ. Попробуй использовать аргументы функции.",
                "trace": "",
            }
            logger.warning(
                "Anti-cheat: hardcoded solution detected for task %s, flags: %s",
                task.get("id", "?"), integrity_flags,
            )

    return result, runtime_ms


@app.get("/api/tasks")
def get_tasks(
    category: Optional[str] = Query(None),
    tier: Optional[str] = Query(None),
    shuffle: bool = Query(False)
):
    """Get all tasks with optional filtering (public payload)."""
    data = load_tasks()
    tasks = [public_task(t) for t in data.get("tasks", []) if not is_archived_task_id(t.get("id"))]
    
    if category:
        tasks = [t for t in tasks if t.get("category") == category]
    if tier:
        tasks = [t for t in tasks if t.get("tier") == tier]
    if shuffle:
        tasks = tasks.copy()
        random.shuffle(tasks)
    
    return {"meta": data.get("meta", {}), "categories": data.get("categories", []), "tasks": tasks}

@app.get("/api/tasks/random")
def get_random_task(
    category: Optional[str] = Query(None),
    tier: Optional[str] = Query(None)
):
    """Get a single random task."""
    data = load_tasks()
    tasks = [public_task(t) for t in data.get("tasks", []) if not is_archived_task_id(t.get("id"))]
    
    if category:
        tasks = [t for t in tasks if t.get("category") == category]
    if tier:
        tasks = [t for t in tasks if t.get("tier") == tier]
    
    if not tasks:
        return {"task": None}
    return {"task": random.choice(tasks)}

# ==================== PROGRESS ROUTES ====================

@app.post("/api/progress/complete")
def complete_task(data: TaskCompletion, user: dict = Depends(require_auth)):
    """Deprecated: use /api/tasks/attempt (server-side verification + anti-cheat)."""
    raise HTTPException(status_code=410, detail="Deprecated endpoint. Use POST /api/tasks/attempt")


PLAGIARISM_THRESHOLD = float(os.getenv("PANDORA_PLAGIARISM_THRESHOLD", "0.92"))
MAX_CODE_CHARS = int(os.getenv("PANDORA_MAX_CODE_CHARS", "60000"))
ATTEMPT_COOLDOWN_S = float(os.getenv("PANDORA_ATTEMPT_COOLDOWN_S", "2.0"))
REVIEWABLE_TIERS = {"B", "A", "S"}
REVIEW_ONLY_MODE = (os.getenv("PANDORA_REVIEW_ONLY_MODE") or "0") == "1"
FORCE_AUTOCHECK = (os.getenv("PANDORA_FORCE_AUTOCHECK") or "1") == "1"
MANUAL_REVIEW_FOR_REVIEWABLE_TIERS = (os.getenv("PANDORA_MANUAL_REVIEW_FOR_REVIEWABLE_TIERS") or "0") == "1"


def _manual_verification_placeholder(reason: str) -> dict:
    """Build a synthetic verification payload when auto-check is intentionally skipped."""
    return {
        "passed": False,
        "exec_error": None,
        "stdout": "",
        "cases": [],
        "note": reason,
        "manual_review_required": True,
    }


def _seconds_since_last_task_attempt(cursor, user_id: int, task_id: str) -> Optional[float]:
    cursor.execute(
        """
        SELECT CAST((julianday('now') - julianday(created_at)) * 86400.0 AS REAL) AS age_s
        FROM task_attempts
        WHERE user_id = ? AND task_id = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (user_id, task_id),
    )
    row = cursor.fetchone()
    if not row:
        return None
    try:
        return float(row["age_s"])
    except (TypeError, ValueError):
        return None


def _pending_submission_for_task(cursor, user_id: int, task_id: str) -> Optional[dict]:
    cursor.execute(
        """
        SELECT id, submitted_at
        FROM submissions
        WHERE user_id = ? AND task_id = ? AND status = 'pending'
        ORDER BY submitted_at DESC
        LIMIT 1
        """,
        (user_id, task_id),
    )
    row = cursor.fetchone()
    return dict(row) if row else None


@app.post("/api/tasks/attempt")
def attempt_task(request: Request, data: TaskAttemptRequest, user: dict = Depends(require_auth)):
    """
    Verify a code task and (if eligible) award XP.

    Policy:
    - Auto-verify code tasks when tests pass and integrity checks are clean.
    - Queue pending review for policy/manual-skip cases, top-7 tasks per rank, or integrity flags.
    """
    task = get_task(data.task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    category = task.get("category")
    tier = task.get("tier") or "D"
    if category == "scratch":
        raise HTTPException(status_code=400, detail="Scratch tasks require /api/tasks/attempt-scratch")

    code = (data.code or "").replace("\r\n", "\n")
    if len(code) > MAX_CODE_CHARS:
        raise HTTPException(status_code=413, detail=f"Code too large (max {MAX_CODE_CHARS} chars)")

    # Unlock enforcement + already-completed check
    tasks_data = load_tasks()
    tasks_by_id = {t.get("id"): t for t in tasks_data.get("tasks", []) if t.get("id")}
    with get_db() as conn:
        cursor = conn.cursor()
        completed_ids = _completed_task_ids(cursor, user["id"])
        counts = _counts_by_category_and_tier(tasks_by_id, completed_ids)
        unlocked, unlock_info = _unlock_state(task, completed_ids, counts)
        last_attempt_age = _seconds_since_last_task_attempt(cursor, user["id"], data.task_id)
        if (
            ATTEMPT_COOLDOWN_S > 0
            and last_attempt_age is not None
            and last_attempt_age < ATTEMPT_COOLDOWN_S
        ):
            wait_for = max(0.1, ATTEMPT_COOLDOWN_S - last_attempt_age)
            raise HTTPException(
                status_code=429,
                detail=f"Слишком частые попытки. Подождите {wait_for:.1f} c.",
            )
        is_retry = data.task_id in completed_ids
        if not unlocked:
            raise HTTPException(status_code=403, detail={"status": "locked", "unlock": unlock_info})

    # Verification (sandboxed runner).
    # Hard stop for untouched templates to prevent accidental auto-completion.
    force_pending_review = False
    if _looks_like_unmodified_template(task, code):
        verification = {
            "passed": False,
            "exec_error": {
                "type": "TemplateUnchanged",
                "message": "Измени стартовый шаблон перед проверкой.",
                "trace": "",
            },
            "stdout": "",
            "cases": [],
        }
        runtime_ms = 0
    else:
        # Safe mode for public deployments: never execute untrusted user code on server.
        if REVIEW_ONLY_MODE and not FORCE_AUTOCHECK:
            verification = _manual_verification_placeholder(
                "Auto-verification disabled by server policy; queued for manual review"
            )
            runtime_ms = 0
            force_pending_review = True
        # Optional legacy behavior: skip auto-check for reviewable tiers on low-resource hosts.
        # Disabled by default to keep deterministic auto-verification.
        elif LOW_RESOURCE_MODE and SKIP_AUTOCHECK_REVIEWABLE_ON_LOW_RESOURCE and tier in REVIEWABLE_TIERS:
            verification = _manual_verification_placeholder(
                "Auto-verification skipped in low-resource mode; queued for review"
            )
            runtime_ms = 0
        else:
            verification, runtime_ms = verify_task(task, code)
    passed = bool(verification.get("passed"))
    manual_review_required = bool(verification.get("manual_review_required"))

    # Safety gate: code tasks can be completed only when runner returned real cases
    # and every case passed. Prevents false-positive passes from malformed payloads.
    logic = task.get("check_logic") or {}
    engine = (logic.get("engine") or "").lower()
    verification_cases = verification.get("cases") if isinstance(verification, dict) else []
    visible_cases = logic.get("cases") if isinstance(logic.get("cases"), list) else []
    hidden_cases = logic.get("hidden_cases") if isinstance(logic.get("hidden_cases"), list) else []
    expected_cases = visible_cases + hidden_cases
    expected_case_count = len(expected_cases)
    has_cases = isinstance(verification_cases, list) and len(verification_cases) > 0
    valid_case_payload = has_cases and all(isinstance(c, dict) for c in verification_cases)
    case_count_matches = valid_case_payload and len(verification_cases) == expected_case_count
    all_cases_passed = valid_case_payload and all(bool(c.get("passed")) for c in verification_cases)
    if engine in ("python", "pyodide", "javascript", "js") and not manual_review_required:
        passed = bool(passed and all_cases_passed and case_count_matches)
        if (not has_cases or not valid_case_payload or not case_count_matches) and not verification.get("exec_error"):
            verification["passed"] = False
            verification["exec_error"] = {
                "type": "InvalidVerification",
                "message": "Invalid or incomplete test cases payload",
                "trace": "",
            }

    code_language = "python" if category == "python" else "javascript" if category == "javascript" else "frontend"
    code_hash = code_sha256(code)
    simhash_hex = code_simhash_hex(code, code_language)

    with get_db() as conn:
        cursor = conn.cursor()

        # Record attempt
        cursor.execute(
            """
            INSERT INTO task_attempts (user_id, task_id, category, tier, code, code_language, code_hash, code_simhash, result_json, passed, runtime_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user["id"],
                data.task_id,
                category,
                tier,
                code,
                code_language,
                code_hash,
                simhash_hex,
                json.dumps(verification, ensure_ascii=False),
                1 if passed else 0,
                runtime_ms,
            ),
        )
        attempt_id = cursor.lastrowid

        if not passed:
            conn.commit()
            return {"status": "failed", "attempt_id": attempt_id, "verification": verification}

        task_xp = int(task.get("xp") or 0)
        top7_review_required = _is_top7_task_by_tier(tasks_by_id, data.task_id)
        plagiarism_score, matched_user_id = plagiarism_score_for_task(cursor, data.task_id, simhash_hex, user["id"])
        flags = []
        if matched_user_id is not None and plagiarism_score >= PLAGIARISM_THRESHOLD:
            flags.append(f"plagiarism_match:{matched_user_id}")

        # Pending review only for explicit policy/manual-skip, top-7 tier tasks, or integrity flags.
        if passed and (
            force_pending_review
            or manual_review_required
            or top7_review_required
            or (MANUAL_REVIEW_FOR_REVIEWABLE_TIERS and tier in REVIEWABLE_TIERS)
            or flags
        ):
            pending_feedback = (
                "Auto-verification disabled by policy; waiting for Sensei review"
                if force_pending_review
                else "Auto-check skipped by server policy; waiting for Sensei review"
                if manual_review_required
                else "Top-7 rank task: waiting for Sensei review"
                if top7_review_required
                else "Tier policy review required"
                if (MANUAL_REVIEW_FOR_REVIEWABLE_TIERS and tier in REVIEWABLE_TIERS)
                else "Flagged for integrity review"
            )
            existing_pending = _pending_submission_for_task(cursor, user["id"], data.task_id)
            if existing_pending:
                conn.commit()
                return {
                    "status": "pending_review",
                    "attempt_id": attempt_id,
                    "submission_id": existing_pending["id"],
                    "verification": verification,
                    "flags": flags,
                    "plagiarism_score": plagiarism_score,
                    "message": "Submission already pending review",
                }
            cursor.execute(
                """
                INSERT INTO submissions (
                    user_id, task_id, category, tier, code, code_language, code_hash, code_simhash,
                    status, feedback, auto_result, plagiarism_score, flags
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user["id"],
                    data.task_id,
                    category,
                    tier,
                    code,
                    code_language,
                    code_hash,
                    simhash_hex,
                    "pending",
                    pending_feedback,
                    json.dumps(verification, ensure_ascii=False),
                    plagiarism_score,
                    json.dumps(flags, ensure_ascii=False),
                ),
            )
            submission_id = cursor.lastrowid
            conn.commit()
            return {
                "status": "pending_review",
                "attempt_id": attempt_id,
                "submission_id": submission_id,
                "verification": verification,
                "flags": flags,
                "plagiarism_score": plagiarism_score,
            }

        # Tier D/C auto-award
        result = process_task_completion(cursor, user["id"], data.task_id, task_xp, code, simhash_hex, is_retry=is_retry)
        if result["status"] == "already_completed":
            conn.commit()
            return {"status": "already_completed"}
        if result["status"] == "retry_no_improvement":
            conn.commit()
            return {
                "status": "retry_no_improvement",
                "verification": verification,
                "prev_xp": result.get("prev_xp_earned", 0),
                "message": f"Задача решена, но XP не улучшился (текущий: {result.get('prev_xp_earned', 0)})",
            }

        proposed_bonus = propose_comment_bonus(task_xp, code, code_language)
        if proposed_bonus > 0:
            cursor.execute(
                """
                UPDATE completed_tasks
                SET comment_bonus_status = 'pending', comment_bonus_proposed = ?
                WHERE user_id = ? AND task_id = ?
                """,
                (proposed_bonus, user["id"], data.task_id),
            )

        cursor.execute(
            """
            INSERT INTO audit_log (actor_user_id, actor_username, action, target_user_id, target_task_id, delta_xp, meta_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user["id"],
                user.get("username"),
                "TASK_AUTO_VERIFIED",
                user["id"],
                data.task_id,
                int(result.get("xp_earned") or 0),
                json.dumps({"ip": get_client_ip(request), "runtime_ms": runtime_ms}, ensure_ascii=False),
            ),
        )

        conn.commit()

        return {
            "status": "completed",
            "attempt_id": attempt_id,
            "verification": verification,
            "xp": result["new_xp"],
            "level": result["new_level"],
            "xp_earned": result["xp_earned"],
            "bonus_applied": result["bonus_applied"],
            "comment_bonus_proposed": proposed_bonus,
            "new_achievements": result.get("new_achievements") or [],
            "is_retry": is_retry,
        }

@app.post("/api/tasks/attempt-scratch")
def attempt_scratch_task(
    request: Request,
    task_id: str = Form(...),
    content: str = Form(None),
    link: str = Form(None),
    file: UploadFile = File(None),
    user: dict = Depends(require_auth)
):
    """Submit a Scratch artifact/link for manual review (optional auto-check)."""
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.get("category") != "scratch":
        raise HTTPException(status_code=400, detail="Not a Scratch task")

    tier = task.get("tier") or "D"

    # Unlock enforcement + already-completed check
    tasks_data = load_tasks()
    tasks_by_id = {t.get("id"): t for t in tasks_data.get("tasks", []) if t.get("id")}
    with get_db() as conn:
        cursor = conn.cursor()
        completed_ids = _completed_task_ids(cursor, user["id"])
        counts = _counts_by_category_and_tier(tasks_by_id, completed_ids)
        unlocked, unlock_info = _unlock_state(task, completed_ids, counts)
        existing_pending = _pending_submission_for_task(cursor, user["id"], task_id)
        if existing_pending:
            return {
                "status": "pending_review",
                "submission_id": existing_pending["id"],
                "message": "Submission already pending review",
            }
        is_retry_scratch = task_id in completed_ids
        if not unlocked:
            raise HTTPException(status_code=403, detail={"status": "locked", "unlock": unlock_info})

    verification_log = ""
    uploaded_size_bytes = 0

    # Save file (if present) with size limit
    if file is not None:
        original_filename = (file.filename or "").strip()
        if original_filename and not original_filename.lower().endswith(".sb3"):
            raise HTTPException(status_code=400, detail="Only .sb3 files are supported")

        max_mb = int(os.getenv("PANDORA_MAX_UPLOAD_MB", "10"))
        max_bytes = max_mb * 1024 * 1024
        try:
            upload_chunk_kb = int(os.getenv("PANDORA_UPLOAD_CHUNK_KB", "4096"))
        except (TypeError, ValueError):
            upload_chunk_kb = 4096
        upload_chunk_kb = max(256, upload_chunk_kb)
        upload_chunk_bytes = upload_chunk_kb * 1024
        filename = f"{uuid.uuid4()}.sb3"
        file_path = Path("uploads") / filename

        written = 0
        with open(file_path, "wb") as buffer:
            while True:
                chunk = file.file.read(upload_chunk_bytes)
                if not chunk:
                    break
                written += len(chunk)
                if written > max_bytes:
                    try:
                        file_path.unlink(missing_ok=True)
                    except Exception:
                        pass
                    raise HTTPException(status_code=413, detail=f"File too large (max {max_mb} MB)")
                buffer.write(chunk)

        uploaded_size_bytes = written
        link = f"/uploads/{filename}"

        # Optional opcode auto-check (helps reviewer; does not auto-award XP)
        required_blocks = (task.get("check_logic") or {}).get("required_blocks") or []
        auto_check_mode = (os.getenv("PANDORA_SCRATCH_AUTOCHECK_MODE") or "off").strip().lower()
        try:
            auto_check_max_mb = float(os.getenv("PANDORA_SCRATCH_AUTOCHECK_MAX_MB", "3"))
        except (TypeError, ValueError):
            auto_check_max_mb = 3.0
        auto_check_max_mb = max(0.0, auto_check_max_mb)
        auto_check_max_bytes = max(1, int(auto_check_max_mb * 1024 * 1024))
        should_auto_check = bool(required_blocks) and uploaded_size_bytes <= auto_check_max_bytes and auto_check_mode == "inline"

        if required_blocks and auto_check_mode != "inline":
            verification_log = "Auto-Check: skipped for fast upload mode"
        elif required_blocks and not should_auto_check:
            verification_log = f"Auto-Check: skipped (file too large: {uploaded_size_bytes // (1024 * 1024)} MB)"
        elif required_blocks and should_auto_check:
            try:
                is_valid, accuracy, missing = check_scratch_file(str(file_path), required_blocks)
                verification_log = f"Auto-Check: {accuracy}% (missing: {', '.join(missing) if missing else 'none'})"
                if not is_valid:
                    verification_log += " [LOW_ACCURACY]"
            except Exception as e:  # noqa: BLE001
                verification_log = f"Auto-Check Error: {type(e).__name__}: {e}"

    # Insert submission
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO submissions (user_id, task_id, category, tier, content, link, status, feedback, review_reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user["id"],
                task_id,
                "scratch",
                tier,
                content,
                link,
                "pending",
                verification_log,
                json.dumps({"ip": get_client_ip(request)}, ensure_ascii=False),
            ),
        )
        submission_id = cursor.lastrowid
        conn.commit()

    return {"status": "pending_review", "submission_id": submission_id, "message": verification_log}


@app.post("/api/tasks/attempt-scratch-fast")
async def attempt_scratch_task_fast(
    request: Request,
    task_id: str = Query(...),
    filename: str = Query("project.sb3"),
    user: dict = Depends(require_auth),
):
    """
    Fast path for Scratch uploads: raw binary body (no multipart parsing).
    This keeps request handling lightweight on slower hardware.
    """
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.get("category") != "scratch":
        raise HTTPException(status_code=400, detail="Not a Scratch task")

    tier = task.get("tier") or "D"

    # Unlock enforcement + already-completed check
    tasks_data = load_tasks()
    tasks_by_id = {t.get("id"): t for t in tasks_data.get("tasks", []) if t.get("id")}
    with get_db() as conn:
        cursor = conn.cursor()
        completed_ids = _completed_task_ids(cursor, user["id"])
        counts = _counts_by_category_and_tier(tasks_by_id, completed_ids)
        unlocked, unlock_info = _unlock_state(task, completed_ids, counts)
        existing_pending = _pending_submission_for_task(cursor, user["id"], task_id)
        if existing_pending:
            return {
                "status": "pending_review",
                "submission_id": existing_pending["id"],
                "message": "Submission already pending review",
            }
        if task_id in completed_ids:
            return {"status": "already_completed"}
        if not unlocked:
            raise HTTPException(status_code=403, detail={"status": "locked", "unlock": unlock_info})

    clean_name = (filename or "project.sb3").strip()
    if not clean_name.lower().endswith(".sb3"):
        raise HTTPException(status_code=400, detail="Only .sb3 files are supported")

    max_mb = int(os.getenv("PANDORA_MAX_UPLOAD_MB", "10"))
    max_bytes = max_mb * 1024 * 1024
    try:
        server_chunk_bytes = int(os.getenv("PANDORA_FAST_UPLOAD_CHUNK_BYTES", str(4 * 1024 * 1024)))
    except (TypeError, ValueError):
        server_chunk_bytes = 4 * 1024 * 1024
    server_chunk_bytes = max(256 * 1024, server_chunk_bytes)
    stored_name = f"{uuid.uuid4()}.sb3"
    file_path = Path("uploads") / stored_name
    written = 0

    try:
        with open(file_path, "wb") as buffer:
            async for chunk in request.stream():
                if not chunk:
                    continue
                written += len(chunk)
                if written > max_bytes:
                    try:
                        file_path.unlink(missing_ok=True)
                    except Exception:
                        pass
                    raise HTTPException(status_code=413, detail=f"File too large (max {max_mb} MB)")
                # Defensive split for very large ASGI chunks.
                if len(chunk) <= server_chunk_bytes:
                    buffer.write(chunk)
                else:
                    for i in range(0, len(chunk), server_chunk_bytes):
                        buffer.write(chunk[i : i + server_chunk_bytes])
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        try:
            file_path.unlink(missing_ok=True)
        except Exception:
            pass
        raise HTTPException(status_code=400, detail=f"Upload failed: {type(e).__name__}")

    if written <= 0:
        try:
            file_path.unlink(missing_ok=True)
        except Exception:
            pass
        raise HTTPException(status_code=400, detail="Empty upload")

    link = f"/uploads/{stored_name}"
    verification_log = "Auto-Check: skipped for fast upload mode"

    # Optional inline auto-check (disabled by default for latency).
    required_blocks = (task.get("check_logic") or {}).get("required_blocks") or []
    auto_check_mode = (os.getenv("PANDORA_SCRATCH_AUTOCHECK_MODE") or "off").strip().lower()
    try:
        auto_check_max_mb = float(os.getenv("PANDORA_SCRATCH_AUTOCHECK_MAX_MB", "3"))
    except (TypeError, ValueError):
        auto_check_max_mb = 3.0
    auto_check_max_mb = max(0.0, auto_check_max_mb)
    auto_check_max_bytes = max(1, int(auto_check_max_mb * 1024 * 1024))
    should_auto_check = bool(required_blocks) and written <= auto_check_max_bytes and auto_check_mode == "inline"
    if required_blocks and should_auto_check:
        try:
            is_valid, accuracy, missing = check_scratch_file(str(file_path), required_blocks)
            verification_log = f"Auto-Check: {accuracy}% (missing: {', '.join(missing) if missing else 'none'})"
            if not is_valid:
                verification_log += " [LOW_ACCURACY]"
        except Exception as e:  # noqa: BLE001
            verification_log = f"Auto-Check Error: {type(e).__name__}: {e}"

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO submissions (user_id, task_id, category, tier, content, link, status, feedback, review_reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user["id"],
                task_id,
                "scratch",
                tier,
                None,
                link,
                "pending",
                verification_log,
                json.dumps({"ip": get_client_ip(request), "fast_upload": True}, ensure_ascii=False),
            ),
        )
        submission_id = cursor.lastrowid
        conn.commit()

    return {"status": "pending_review", "submission_id": submission_id, "message": verification_log}


@app.post("/api/progress/submit")
def submit_for_review(
    request: Request,
    task_id: str = Form(...),
    content: str = Form(None),
    link: str = Form(None),
    file: UploadFile = File(None),
    user: dict = Depends(require_auth),
):
    """Backward-compatible alias for Scratch submissions."""
    return attempt_scratch_task(request, task_id=task_id, content=content, link=link, file=file, user=user)

def check_scratch_file(file_path: str, required_blocks: list) -> tuple:
    """
    Parse local .sb3 file (zip) and check for blocks.
    Returns (is_valid, accuracy_percent, missing_blocks)
    """
    try:
        with zipfile.ZipFile(file_path, "r") as z:
            # Basic zip-bomb defenses
            infos = z.infolist()
            if len(infos) > 5000:
                raise Exception("Invalid .sb3 file (too many entries)")
            try:
                project_info = z.getinfo("project.json")
            except KeyError:
                raise Exception("Invalid .sb3 file (missing project.json)")
            if project_info.file_size > 5 * 1024 * 1024:
                raise Exception("Invalid .sb3 file (project.json too large)")
            with z.open(project_info) as f:
                raw = f.read(5 * 1024 * 1024 + 1)
                if len(raw) > 5 * 1024 * 1024:
                    raise Exception("Invalid .sb3 file (project.json too large)")
                project_data = json.loads(raw.decode("utf-8", errors="replace"))
    except Exception:
        raise Exception("Invalid .sb3 file")
    
    # Extract all opcodes from targets
    found_opcodes = set()
    for target in project_data.get("targets", []):
        for block_id, block in target.get("blocks", {}).items():
            if isinstance(block, dict) and "opcode" in block:
                found_opcodes.add(block["opcode"])
    
    # Check requirements
    missing = [block for block in required_blocks if block not in found_opcodes]
    found_count = len(required_blocks) - len(missing)
    accuracy = int((found_count / len(required_blocks)) * 100) if required_blocks else 100
    
    return accuracy >= 50, accuracy, missing

# REMOVED OLD check_scratch_project async function as it is replaced by file check

# ==================== USER: OWN PRIORITIES ====================

@app.get("/api/user/priorities")
def get_own_priorities(user: dict = Depends(require_auth)):
    """Get learning priorities for current user (student can access own)."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM user_priorities WHERE user_id = ?", (user["id"],))
        row = cursor.fetchone()
        if row:
            return dict(row)
        else:
            return {
                "user_id": user["id"],
                "scratch_priority": 25,
                "frontend_priority": 25,
                "javascript_priority": 25,
                "python_priority": 25
            }

# ==================== PASTE REQUEST SYSTEM ====================

class PasteRequest(BaseModel):
    task_id: str
    task_title: str = None

@app.post("/api/paste-request")
def create_paste_request(data: PasteRequest, user: dict = Depends(require_auth)):
    """Student requests paste permission from admin."""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Check if already has pending request for this task
        cursor.execute("""
            SELECT id FROM paste_requests 
            WHERE user_id = ? AND task_id = ? AND status = 'pending'
        """, (user["id"], data.task_id))
        
        if cursor.fetchone():
            return {"message": "Request already pending"}
        
        cursor.execute("""
            INSERT INTO paste_requests (user_id, task_id, task_title, status)
            VALUES (?, ?, ?, 'pending')
        """, (user["id"], data.task_id, data.task_title))
        conn.commit()
        
        return {"message": "Request submitted", "request_id": cursor.lastrowid}

@app.get("/api/paste-request/status")
def check_paste_request_status(task_id: str, user: dict = Depends(require_auth)):
    """Check if paste request was approved."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT status FROM paste_requests 
            WHERE user_id = ? AND task_id = ?
            ORDER BY created_at DESC LIMIT 1
        """, (user["id"], task_id))
        
        row = cursor.fetchone()
        if not row:
            return {"pending": False, "approved": False, "rejected": False}
        
        status = row["status"]
        return {
            "pending": status == "pending",
            "approved": status == "approved",
            "rejected": status == "rejected"
        }

@app.get("/api/paste-requests/pending")
def get_pending_paste_requests(user: dict = Depends(require_admin)):
    """Admin: Get all pending paste requests."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT pr.id, pr.task_id, pr.task_title, pr.created_at,
                   u.display_name, u.username
            FROM paste_requests pr
            JOIN users u ON pr.user_id = u.id
            WHERE pr.status = 'pending'
            ORDER BY pr.created_at ASC
        """)
        requests = [dict(row) for row in cursor.fetchall()]
    return {"requests": requests}

@app.post("/api/paste-request/{request_id}/approve")
def approve_paste_request(request_id: int, user: dict = Depends(require_admin)):
    """Admin: Approve paste request."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE paste_requests 
            SET status = 'approved', resolved_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (request_id,))
        conn.commit()
    return {"message": "Request approved"}

@app.post("/api/paste-request/{request_id}/reject")
def reject_paste_request(request_id: int, user: dict = Depends(require_admin)):
    """Admin: Reject paste request."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE paste_requests 
            SET status = 'rejected', resolved_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (request_id,))
        conn.commit()
    return {"message": "Request rejected"}

# ==================== CHAT SYSTEM ====================

class ChatMessage(BaseModel):
    message: str

@app.get("/api/chat")
def get_chat_messages(limit: int = 50, user: dict = Depends(require_auth)):
    """Get recent chat messages."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT cm.id, cm.message, cm.created_at, 
                   u.id as sender_id, u.username, u.display_name, u.role,
                   COALESCE(us.avatar_data, '') as avatar_data
            FROM chat_messages cm
            JOIN users u ON cm.sender_id = u.id
            LEFT JOIN user_stats us ON u.id = us.user_id
            ORDER BY cm.created_at DESC
            LIMIT ?
        """, (limit,))
        messages = []
        for row in cursor.fetchall():
            messages.append({
                "id": row["id"],
                "message": row["message"],
                "created_at": row["created_at"],
                "sender": {
                    "id": row["sender_id"],
                    "username": row["username"],
                    "display_name": row["display_name"],
                    "role": row["role"],
                    "avatar_data": row["avatar_data"] or None
                }
            })
        return {"messages": messages[::-1]}  # Reverse to chronological order

@app.post("/api/chat")
def send_chat_message(request: Request, data: ChatMessage, user: dict = Depends(require_auth)):
    """Send a chat message."""
    # Check for attack patterns
    threats = detect_threats(data.message)
    if threats:
        for threat in threats:
            log_security_event(threat, request, user_id=user["id"], 
                             username=user["username"],
                             details=f"blocked_message={data.message[:50]}",
                             severity="CRITICAL")
        raise HTTPException(status_code=400, detail="Message contains invalid content")
    
    # Limit message length
    if len(data.message) > 500:
        raise HTTPException(status_code=400, detail="Message too long (max 500 chars)")
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Anti-spam: check messages in last 60 seconds
        cursor.execute("""
            SELECT COUNT(*) as cnt FROM chat_messages 
            WHERE sender_id = ? AND created_at > datetime('now', '-60 seconds')
        """, (user["id"],))
        msg_count = cursor.fetchone()["cnt"]
        
        # Spam detection: >10 messages in 60 seconds
        SPAM_THRESHOLD = 10
        if msg_count >= SPAM_THRESHOLD:
            # Award "Болтун" achievement if not already awarded
            cursor.execute("""
                SELECT 1 FROM user_achievements WHERE user_id = ? AND achievement_id = 'chatterbox'
            """, (user["id"],))
            if not cursor.fetchone():
                cursor.execute("""
                    INSERT OR IGNORE INTO user_achievements (user_id, achievement_id, unlocked_at)
                    VALUES (?, 'chatterbox', datetime('now'))
                """, (user["id"],))
                conn.commit()
                log_security_event("SPAM_DETECTED", request, user_id=user["id"],
                                 username=user["username"],
                                 details=f"messages_in_60s={msg_count}, awarded_chatterbox")
            raise HTTPException(status_code=429, detail="🗣️ Тише, Болтун! Подожди 30 секунд")
        
        cursor.execute(
            "INSERT INTO chat_messages (sender_id, message) VALUES (?, ?)",
            (user["id"], data.message)
        )
        conn.commit()
        
        log_security_event(
            "CHAT_MESSAGE", request,
            user_id=user["id"],
            username=user["username"],
            details=f"message_len={len(data.message)}"
        )
        
        return {"success": True, "message_id": cursor.lastrowid}

# ==================== XP HISTORY (PROGRESS GRAPH) ====================

@app.get("/api/user/xp-history")
def get_xp_history(user: dict = Depends(require_auth)):
    """Get XP history for progress graph."""
    with get_db() as conn:
        cursor = conn.cursor()
        # Get XP history from completed tasks
        cursor.execute("""
            SELECT ct.completed_at as date, ct.xp_earned as xp, 
                   (SELECT SUM(xp_earned) FROM completed_tasks 
                    WHERE user_id = ? AND is_valid != 0 AND completed_at <= ct.completed_at) as cumulative_xp
            FROM completed_tasks ct
            WHERE ct.user_id = ? AND ct.is_valid != 0
            ORDER BY ct.completed_at
        """, (user["id"], user["id"]))
        
        history = []
        for row in cursor.fetchall():
            history.append({
                "date": row["date"],
                "xp": row["xp"],
                "total": row["cumulative_xp"]
            })
        
        return {"history": history, "current_xp": user.get("xp", 0)}

# ==================== ADMIN: PRIORITIES ====================

@app.get("/api/admin/priorities/{user_id}")
def get_priorities(user_id: int, admin: dict = Depends(require_admin)):
    """Get learning priorities for a user."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM user_priorities WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        else:
            return {
                "user_id": user_id,
                "scratch_priority": 25,
                "frontend_priority": 25,
                "javascript_priority": 25,
                "python_priority": 25
            }

@app.put("/api/admin/priorities/{user_id}")
def set_priorities(user_id: int, data: PriorityRequest, admin: dict = Depends(require_admin)):
    """Set learning priorities for a user."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO user_priorities (user_id, scratch_priority, frontend_priority, javascript_priority, python_priority)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                scratch_priority = excluded.scratch_priority,
                frontend_priority = excluded.frontend_priority,
                javascript_priority = excluded.javascript_priority,
                python_priority = excluded.python_priority,
                updated_at = CURRENT_TIMESTAMP
        """, (user_id, data.scratch_priority, data.frontend_priority, data.javascript_priority, data.python_priority))
        conn.commit()
    return {"message": "Priorities updated"}

# ==================== ADMIN: REWARDS ====================

@app.post("/api/admin/rewards")
def give_reward(data: RewardRequest, admin: dict = Depends(require_admin)):
    """Give a reward to a user."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO rewards (user_id, icon, title, comment, awarded_by)
            VALUES (?, ?, ?, ?, ?)
        """, (data.user_id, data.icon, data.title, data.comment, admin["id"]))
        conn.commit()
    log_security("REWARD_GIVEN", user=admin["username"], details=f"user_id={data.user_id}, reward={data.title}")
    return {"message": "Reward given"}

@app.get("/api/admin/rewards/{user_id}")
def get_user_rewards(user_id: int, admin: dict = Depends(require_admin)):
    """Get all rewards for a user."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT r.*, u.display_name as awarded_by_name
            FROM rewards r
            LEFT JOIN users u ON r.awarded_by = u.id
            WHERE r.user_id = ?
            ORDER BY r.awarded_at DESC
        """, (user_id,))
        rewards = [dict(row) for row in cursor.fetchall()]
    return {"rewards": rewards}

# ==================== ADMIN: COMPLETIONS HISTORY ====================

@app.get("/api/admin/users/{user_id}/completions")
def get_user_completions(user_id: int, admin: dict = Depends(require_admin)):
    """Get all completed tasks for a user with code/solution."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT c.*, s.content as submission_content, s.link, s.feedback, s.score
            FROM completed_tasks c
            LEFT JOIN submissions s ON c.user_id = s.user_id AND c.task_id = s.task_id
            WHERE c.user_id = ?
            ORDER BY c.completed_at DESC
        """, (user_id,))
        completions = [dict(row) for row in cursor.fetchall()]
        
        # Enrich with task info
        tasks_data = load_tasks()
        tasks_map = {t["id"]: t for t in tasks_data.get("tasks", [])}
        
        for c in completions:
            task = tasks_map.get(c["task_id"], {})
            c["task_title"] = task.get("title", c["task_id"])
            c["task_category"] = task.get("category", "unknown")
            c["max_xp"] = task.get("xp", 0)
    
    return {"completions": completions}

@app.put("/api/admin/completions/{completion_id}/adjust")
def adjust_completion_xp(completion_id: int, data: XPAdjustRequest, admin: dict = Depends(require_admin)):
    """Adjust or cancel XP for a completed task."""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Get completion info
        cursor.execute("SELECT * FROM completed_tasks WHERE id = ?", (completion_id,))
        completion = cursor.fetchone()
        if not completion:
            raise HTTPException(status_code=404, detail="Completion not found")
        
        original_xp = completion["xp_earned"] or 0
        
        # Calculate XP adjustment
        if data.new_score == 0:
            # Full cancellation
            xp_change = -original_xp
            new_xp_earned = 0
        else:
            # Proportional adjustment
            new_xp_earned = int(original_xp * data.new_score / 10)
            xp_change = new_xp_earned - original_xp
        
        # Update user XP (keeps level consistent)
        apply_xp_change(
            cursor,
            completion["user_id"],
            xp_change,
            f"admin_adjustment:{data.reason or ('score ' + str(data.new_score))}",
            completion["task_id"],
        )
        
        # Update completion record
        cursor.execute("UPDATE completed_tasks SET xp_earned = ?, is_valid = ? WHERE id = ?", 
                      (new_xp_earned, 1 if data.new_score > 0 else 0, completion_id))
        
        conn.commit()
    
    log_security("XP_ADJUSTED", user=admin["username"], 
                details=f"completion_id={completion_id}, change={xp_change}")
    return {"message": "XP adjusted", "xp_change": xp_change}

# ==================== ADMIN: COMMENT BONUS REVIEW ====================

@app.get("/api/admin/comment-bonuses")
def list_comment_bonuses(admin: dict = Depends(require_admin)):
    """List pending comment-bonus requests (auto-verified tasks)."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT c.id as completion_id, c.user_id, c.task_id, c.comment_bonus_proposed, c.completed_at,
                   u.username, u.display_name
            FROM completed_tasks c
            JOIN users u ON u.id = c.user_id
            WHERE c.comment_bonus_status = 'pending' AND (c.comment_bonus_proposed or 0) > 0
            ORDER BY c.completed_at DESC
            """
        )
        rows = [dict(r) for r in cursor.fetchall()]

    tasks_data = load_tasks()
    tasks_map = {t.get("id"): t for t in tasks_data.get("tasks", []) if t.get("id")}
    for r in rows:
        t = tasks_map.get(r["task_id"], {}) or {}
        r["task_title"] = t.get("title", r["task_id"])
        r["task_xp"] = int(t.get("xp") or 0)
        r["tier"] = t.get("tier")
        r["category"] = t.get("category")

    return {"items": rows}


@app.put("/api/admin/comment-bonuses/{completion_id}")
def decide_comment_bonus(
    completion_id: int,
    data: CommentBonusDecision,
    admin: dict = Depends(require_admin),
):
    """Approve/reject a pending comment bonus."""
    if data.status not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="Invalid status")

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM completed_tasks WHERE id = ?", (completion_id,))
        c = cursor.fetchone()
        if not c:
            raise HTTPException(status_code=404, detail="Completion not found")
        if (c["comment_bonus_status"] or "none") != "pending":
            raise HTTPException(status_code=400, detail="No pending comment bonus for this completion")

        proposed = int(c["comment_bonus_proposed"] or 0)
        awarded = 0
        if data.status == "approved":
            awarded = int(data.awarded) if data.awarded is not None else proposed
            awarded = max(0, min(awarded, proposed))
            if awarded > 0:
                apply_xp_change(cursor, c["user_id"], awarded, "comment_bonus", c["task_id"])

        cursor.execute(
            """
            UPDATE completed_tasks
            SET comment_bonus_status = ?, comment_bonus_awarded = ?
            WHERE id = ?
            """,
            (data.status, awarded, completion_id),
        )
        cursor.execute(
            """
            INSERT INTO audit_log (actor_user_id, actor_username, action, target_user_id, target_task_id, delta_xp, meta_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                admin["id"],
                admin.get("username"),
                "COMMENT_BONUS_DECISION",
                c["user_id"],
                c["task_id"],
                awarded,
                json.dumps({"completion_id": completion_id, "status": data.status, "awarded": awarded, "feedback": data.feedback}, ensure_ascii=False),
            ),
        )
        conn.commit()

    return {"message": "Comment bonus updated", "status": data.status, "awarded": awarded}

# ==================== ADMIN: PROGRESS CHARTS ====================

@app.get("/api/admin/progress")
def get_progress_data(
    user_id: Optional[int] = Query(None),
    all_users: bool = Query(False),
    admin: dict = Depends(require_admin)
):
    """Get progress data for charts."""
    with get_db() as conn:
        cursor = conn.cursor()
        
        result = {"users": []}
        
        if all_users:
            cursor.execute("SELECT id, display_name FROM users WHERE role = 'student'")
            users = cursor.fetchall()
        elif user_id:
            cursor.execute("SELECT id, display_name FROM users WHERE id = ?", (user_id,))
            users = cursor.fetchall()
        else:
            return {"users": []}
        
        for user in users:
            uid = user["id"]
            # Get cumulative XP over time
            cursor.execute("""
                SELECT DATE(logged_at) as date, SUM(xp_change) as xp_gain
                FROM xp_log
                WHERE user_id = ?
                GROUP BY DATE(logged_at)
                ORDER BY date
            """, (uid,))
            daily_data = cursor.fetchall()
            
            # Calculate cumulative XP
            cumulative = 0
            timeline = []
            for row in daily_data:
                cumulative += row["xp_gain"]
                timeline.append({
                    "date": row["date"],
                    "xp": cumulative
                })
            
            result["users"].append({
                "id": uid,
                "display_name": user["display_name"],
                "timeline": timeline
            })
    
    return result

# ==================== USER: OWN SUBMISSIONS & REWARDS ====================

@app.get("/api/user/submissions")
def get_my_submissions(user: dict = Depends(require_auth)):
    """Get own submissions with reviews."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM submissions WHERE user_id = ? ORDER BY submitted_at DESC
        """, (user["id"],))
        submissions = [dict(row) for row in cursor.fetchall()]
        
        # Enrich with task info
        tasks_data = load_tasks()
        tasks_map = {t["id"]: t for t in tasks_data.get("tasks", [])}
        
        for s in submissions:
            task = tasks_map.get(s["task_id"], {})
            s["task_title"] = task.get("title", s["task_id"])
            s["max_xp"] = task.get("xp", 0)
    
    return {"submissions": submissions}

@app.get("/api/user/rewards")
def get_my_rewards(user: dict = Depends(require_auth)):
    """Get own rewards."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT r.*, u.display_name as awarded_by_name
            FROM rewards r
            LEFT JOIN users u ON r.awarded_by = u.id
            WHERE r.user_id = ?
            ORDER BY r.awarded_at DESC
        """, (user["id"],))
        rewards = [dict(row) for row in cursor.fetchall()]
    return {"rewards": rewards}

# ==================== GUILD SYSTEM ====================

_GUILD_AVATARS = ["🛡️", "⚔️", "🐉", "🔥", "🌟", "💎", "🏰", "🦅", "🐺", "🦁", "👑", "🎯", "💀", "🌙", "⚡", "🔱"]

_GUILD_TITLE_PRESETS = {
    "curse": {"title_text": "Проклятие", "effect_type": "xp_debuff", "effect_value": -0.03},
    "weakness": {"title_text": "Слабость", "effect_type": "xp_debuff", "effect_value": -0.02},
    "shame": {"title_text": "Позор", "effect_type": "xp_debuff", "effect_value": -0.05},
}

_GUILD_MEMBER_TITLE_PRESETS = {
    # Positive titles only (for own members)
    "blessing": {"title_text": "Благословение", "effect_type": "xp_buff", "effect_value": 0.05, "duration": "+1 day", "positive": True, "icon": "✨"},
    "inspiration": {"title_text": "Вдохновение", "effect_type": "xp_buff", "effect_value": 0.10, "duration": "+12 hours", "positive": True, "icon": "🔥"},
    "typing_master": {"title_text": "Мастер Набора", "effect_type": "xp_buff", "effect_value": 0.08, "duration": "+12 hours", "positive": True, "icon": "⌨️"},
    "quest_champion": {"title_text": "Чемпион Квестов", "effect_type": "xp_buff", "effect_value": 0.08, "duration": "+12 hours", "positive": True, "icon": "🏆"},
}

_MAX_ACTIVE_MEMBER_TITLES = 5

class GuildCreateRequest(BaseModel):
    name: str
    description: str = ""
    avatar_emoji: str = "🛡️"

class GuildTitleRequest(BaseModel):
    to_guild_id: int
    preset: str  # curse, weakness, shame

class GuildMemberTitleRequest(BaseModel):
    to_user_id: int
    preset: str  # blessing, inspiration, hex, slow, xp_cooldown, category_block
    category: str = None  # required for category_block

class GuildRoleRequest(BaseModel):
    role: str  # president, chairman, developer

class GuildSettingsRequest(BaseModel):
    max_guilds: int = 2


def _get_max_guilds(cursor) -> int:
    cursor.execute("SELECT value FROM guild_settings WHERE key = 'max_guilds'")
    row = cursor.fetchone()
    return int(row["value"]) if row else 2


def _guild_ranking_score(cursor, guild_id: int) -> dict:
    """Calculate a guild's ranking score."""
    cursor.execute("""
        SELECT COUNT(*) as cnt FROM guild_members WHERE guild_id = ?
    """, (guild_id,))
    member_count = cursor.fetchone()["cnt"]

    cursor.execute("""
        SELECT COALESCE(SUM(u.xp), 0) as total_xp
        FROM guild_members gm JOIN users u ON u.id = gm.user_id
        WHERE gm.guild_id = ?
    """, (guild_id,))
    total_xp = cursor.fetchone()["total_xp"]

    cursor.execute("""
        SELECT COUNT(*) as cnt
        FROM completed_tasks ct
        JOIN guild_members gm ON gm.user_id = ct.user_id
        WHERE gm.guild_id = ? AND ct.is_valid = 1
    """, (guild_id,))
    total_tasks = cursor.fetchone()["cnt"]

    score = (total_tasks * 2) + int(total_xp * 0.01) + (member_count * 5)
    return {
        "member_count": member_count,
        "total_xp": total_xp,
        "total_tasks": total_tasks,
        "score": score,
    }


@app.post("/api/guilds")
def create_guild(data: GuildCreateRequest, user: dict = Depends(require_auth)):
    """Create a new guild — the creator becomes president."""
    name = data.name.strip()
    if not name or len(name) < 2 or len(name) > 30:
        raise HTTPException(400, "Название гильдии: 2-30 символов")
    if data.avatar_emoji not in _GUILD_AVATARS:
        data.avatar_emoji = "🛡️"
    uid = user["id"]

    with get_db() as conn:
        cursor = conn.cursor()
        # Check if already in a guild
        cursor.execute("SELECT guild_id FROM guild_members WHERE user_id = ?", (uid,))
        if cursor.fetchone():
            raise HTTPException(400, "Вы уже состоите в гильдии")

        # Check max guilds
        max_guilds = _get_max_guilds(cursor)
        cursor.execute("SELECT COUNT(*) as cnt FROM guilds WHERE disbanded_at IS NULL")
        if cursor.fetchone()["cnt"] >= max_guilds:
            raise HTTPException(400, f"Достигнут лимит гильдий ({max_guilds})")

        # Check unique name
        cursor.execute("SELECT id FROM guilds WHERE name = ? AND disbanded_at IS NULL", (name,))
        if cursor.fetchone():
            raise HTTPException(400, "Гильдия с таким именем уже существует")

        cursor.execute(
            "INSERT INTO guilds (name, description, avatar_emoji, created_by) VALUES (?, ?, ?, ?)",
            (name, data.description[:200], data.avatar_emoji, uid),
        )
        guild_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO guild_members (guild_id, user_id, role) VALUES (?, ?, 'president')",
            (guild_id, uid),
        )
        conn.commit()

    return {"guild_id": guild_id, "message": f"Гильдия «{name}» создана!"}


@app.get("/api/guilds")
def list_guilds(user: dict = Depends(require_auth)):
    """List all active guilds."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT g.*, u.display_name as creator_name
            FROM guilds g
            JOIN users u ON u.id = g.created_by
            WHERE g.disbanded_at IS NULL
            ORDER BY g.created_at
        """)
        guilds = []
        for row in cursor.fetchall():
            g = dict(row)
            stats = _guild_ranking_score(cursor, g["id"])
            g.update(stats)
            guilds.append(g)
    return {"guilds": guilds}


@app.get("/api/guilds/my")
def get_my_guild(user: dict = Depends(require_auth)):
    """Get current user's guild."""
    uid = user["id"]
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT g.*, gm.role as my_role, u.display_name as creator_name
            FROM guild_members gm
            JOIN guilds g ON g.id = gm.guild_id
            JOIN users u ON u.id = g.created_by
            WHERE gm.user_id = ? AND g.disbanded_at IS NULL
        """, (uid,))
        row = cursor.fetchone()
        if not row:
            return {"guild": None}

        guild = dict(row)
        stats = _guild_ranking_score(cursor, guild["id"])
        guild.update(stats)

        # Members with online status and avatar info
        cursor.execute("""
            SELECT gm.user_id, gm.role, gm.custom_role_name, gm.joined_at,
                   u.display_name, u.xp, u.level, u.avatar_key, u.last_seen_at,
                   CASE WHEN s.avatar_data IS NOT NULL AND s.avatar_data != '' THEN 1 ELSE 0 END as has_avatar,
                   COALESCE(s.total_quests, 0) as total_quests,
                   COALESCE(s.streak_days, 0) as streak_days
            FROM guild_members gm
            JOIN users u ON u.id = gm.user_id
            LEFT JOIN user_stats s ON s.user_id = u.id
            WHERE gm.guild_id = ?
            ORDER BY CASE gm.role
                WHEN 'president' THEN 1
                WHEN 'chairman' THEN 2
                ELSE 3
            END, u.xp DESC
        """, (guild["id"],))
        guild["members"] = [dict(m) for m in cursor.fetchall()]

        # Active titles on this guild
        cursor.execute("""
            SELECT gt.*, fg.name as from_guild_name
            FROM guild_titles gt
            JOIN guilds fg ON fg.id = gt.from_guild_id
            WHERE gt.to_guild_id = ? AND gt.expires_at > CURRENT_TIMESTAMP
        """, (guild["id"],))
        guild["active_titles"] = [dict(t) for t in cursor.fetchall()]

    return {"guild": guild}


@app.get("/api/guilds/rankings")
def guild_rankings(user: dict = Depends(require_auth)):
    """Get guild rankings sorted by score."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT g.id, g.name, g.avatar_emoji, g.avatar_url, g.created_at
            FROM guilds g
            WHERE g.disbanded_at IS NULL
        """)
        guilds = []
        for row in cursor.fetchall():
            g = dict(row)
            stats = _guild_ranking_score(cursor, g["id"])
            g.update(stats)
            guilds.append(g)
        guilds.sort(key=lambda x: x["score"], reverse=True)
        for i, g in enumerate(guilds):
            g["rank"] = i + 1

        # Active titles
        cursor.execute("""
            SELECT gt.to_guild_id, gt.title_text, gt.effect_type, gt.effect_value,
                   fg.name as from_guild_name
            FROM guild_titles gt
            JOIN guilds fg ON fg.id = gt.from_guild_id
            WHERE gt.expires_at > CURRENT_TIMESTAMP
        """)
        titles = {}
        for t in cursor.fetchall():
            gid = t["to_guild_id"]
            if gid not in titles:
                titles[gid] = []
            titles[gid].append(dict(t))

        for g in guilds:
            g["titles"] = titles.get(g["id"], [])

    return {"rankings": guilds}


@app.get("/api/guilds/titles")
def get_active_titles(user: dict = Depends(require_auth)):
    """Get all active titles."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT gt.*, fg.name as from_guild_name, tg.name as to_guild_name
            FROM guild_titles gt
            JOIN guilds fg ON fg.id = gt.from_guild_id
            JOIN guilds tg ON tg.id = gt.to_guild_id
            WHERE gt.expires_at > CURRENT_TIMESTAMP
            ORDER BY gt.created_at DESC
        """)
        titles = [dict(t) for t in cursor.fetchall()]
    return {"titles": titles}


@app.get("/api/guilds/{guild_id}")
def get_guild(guild_id: int, user: dict = Depends(require_auth)):
    """Get guild detail."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT g.*, u.display_name as creator_name
            FROM guilds g
            JOIN users u ON u.id = g.created_by
            WHERE g.id = ? AND g.disbanded_at IS NULL
        """, (guild_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(404, "Гильдия не найдена")
        guild = dict(row)
        stats = _guild_ranking_score(cursor, guild_id)
        guild.update(stats)

        cursor.execute("""
            SELECT gm.user_id, gm.role, gm.custom_role_name, gm.joined_at,
                   u.display_name, u.xp, u.level, u.avatar_key,
                   CASE WHEN s.avatar_data IS NOT NULL AND s.avatar_data != '' THEN 1 ELSE 0 END as has_avatar
            FROM guild_members gm
            JOIN users u ON u.id = gm.user_id
            LEFT JOIN user_stats s ON s.user_id = u.id
            WHERE gm.guild_id = ?
            ORDER BY CASE gm.role
                WHEN 'president' THEN 1
                WHEN 'chairman' THEN 2
                ELSE 3
            END, u.xp DESC
        """, (guild_id,))
        guild["members"] = [dict(m) for m in cursor.fetchall()]

        # Active titles on this guild
        cursor.execute("""
            SELECT gt.*, fg.name as from_guild_name
            FROM guild_titles gt
            JOIN guilds fg ON fg.id = gt.from_guild_id
            WHERE gt.to_guild_id = ? AND gt.expires_at > CURRENT_TIMESTAMP
        """, (guild_id,))
        guild["active_titles"] = [dict(t) for t in cursor.fetchall()]

    return {"guild": guild}


@app.post("/api/guilds/{guild_id}/join")
def join_guild(guild_id: int, user: dict = Depends(require_auth)):
    """Join a guild."""
    uid = user["id"]
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT guild_id FROM guild_members WHERE user_id = ?", (uid,))
        if cursor.fetchone():
            raise HTTPException(400, "Вы уже состоите в гильдии")
        cursor.execute("SELECT id FROM guilds WHERE id = ? AND disbanded_at IS NULL", (guild_id,))
        if not cursor.fetchone():
            raise HTTPException(404, "Гильдия не найдена")
        cursor.execute(
            "INSERT INTO guild_members (guild_id, user_id, role) VALUES (?, ?, 'developer')",
            (guild_id, uid),
        )
        conn.commit()
    return {"message": "Вы вступили в гильдию!"}


@app.post("/api/guilds/{guild_id}/leave")
def leave_guild(guild_id: int, user: dict = Depends(require_auth)):
    """Leave a guild. Presidents must transfer or disband."""
    uid = user["id"]
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT role FROM guild_members WHERE guild_id = ? AND user_id = ?",
            (guild_id, uid),
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(400, "Вы не состоите в этой гильдии")
        if row["role"] == "president":
            raise HTTPException(400, "Президент не может покинуть гильдию. Передайте роль или расформируйте.")
        cursor.execute(
            "DELETE FROM guild_members WHERE guild_id = ? AND user_id = ?",
            (guild_id, uid),
        )
        conn.commit()
    return {"message": "Вы покинули гильдию"}


@app.post("/api/guilds/{guild_id}/disband")
def disband_guild(guild_id: int, user: dict = Depends(require_auth)):
    """Disband a guild (president only)."""
    uid = user["id"]
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT role FROM guild_members WHERE guild_id = ? AND user_id = ?",
            (guild_id, uid),
        )
        row = cursor.fetchone()
        if not row or row["role"] != "president":
            raise HTTPException(403, "Только президент может расформировать гильдию")
        cursor.execute(
            "UPDATE guilds SET disbanded_at = CURRENT_TIMESTAMP WHERE id = ?",
            (guild_id,),
        )
        cursor.execute("DELETE FROM guild_members WHERE guild_id = ?", (guild_id,))
        cursor.execute("DELETE FROM guild_titles WHERE from_guild_id = ? OR to_guild_id = ?", (guild_id, guild_id))
        conn.commit()
    return {"message": "Гильдия расформирована"}


@app.post("/api/guilds/{guild_id}/members/{member_id}/role")
def set_member_role(guild_id: int, member_id: int, data: GuildRoleRequest, user: dict = Depends(require_auth)):
    """Set a member's role (president only)."""
    uid = user["id"]
    if data.role not in ("president", "chairman", "developer"):
        raise HTTPException(400, "Недопустимая роль")
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT role FROM guild_members WHERE guild_id = ? AND user_id = ?",
            (guild_id, uid),
        )
        row = cursor.fetchone()
        if not row or row["role"] != "president":
            raise HTTPException(403, "Только президент может менять роли")
        cursor.execute(
            "SELECT id FROM guild_members WHERE guild_id = ? AND user_id = ?",
            (guild_id, member_id),
        )
        if not cursor.fetchone():
            raise HTTPException(404, "Участник не найден")

        if data.role == "president":
            # Transfer presidency
            cursor.execute(
                "UPDATE guild_members SET role = 'chairman' WHERE guild_id = ? AND user_id = ?",
                (guild_id, uid),
            )
        cursor.execute(
            "UPDATE guild_members SET role = ? WHERE guild_id = ? AND user_id = ?",
            (data.role, guild_id, member_id),
        )
        conn.commit()
    role_emoji = {"president": "👑", "chairman": "🎖️", "developer": "💻"}.get(data.role, "")
    return {"message": f"Роль изменена на {role_emoji} {data.role}"}


@app.post("/api/guilds/{guild_id}/kick/{member_id}")
def kick_member(guild_id: int, member_id: int, user: dict = Depends(require_auth)):
    """Kick a member (president/chairman can kick developers)."""
    uid = user["id"]
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT role FROM guild_members WHERE guild_id = ? AND user_id = ?",
            (guild_id, uid),
        )
        caller = cursor.fetchone()
        if not caller or caller["role"] not in ("president", "chairman"):
            raise HTTPException(403, "Недостаточно прав")
        cursor.execute(
            "SELECT role FROM guild_members WHERE guild_id = ? AND user_id = ?",
            (guild_id, member_id),
        )
        target = cursor.fetchone()
        if not target:
            raise HTTPException(404, "Участник не найден")
        if target["role"] == "president":
            raise HTTPException(400, "Нельзя исключить президента")
        if target["role"] == "chairman" and caller["role"] != "president":
            raise HTTPException(403, "Только президент может исключить председателя")
        cursor.execute(
            "DELETE FROM guild_members WHERE guild_id = ? AND user_id = ?",
            (guild_id, member_id),
        )
        conn.commit()
    return {"message": "Участник исключён"}


@app.post("/api/guilds/{guild_id}/titles")
def assign_title(guild_id: int, data: GuildTitleRequest, user: dict = Depends(require_auth)):
    """Top-1 guild president can assign debuff titles to other guilds."""
    uid = user["id"]
    if data.preset not in _GUILD_TITLE_PRESETS:
        raise HTTPException(400, "Неизвестный тип титула")

    with get_db() as conn:
        cursor = conn.cursor()
        # Verify user is president of the requesting guild
        cursor.execute(
            "SELECT role FROM guild_members WHERE guild_id = ? AND user_id = ?",
            (guild_id, uid),
        )
        row = cursor.fetchone()
        if not row or row["role"] != "president":
            raise HTTPException(403, "Только президент может назначать титулы")

        # Verify this guild is #1
        cursor.execute("SELECT id FROM guilds WHERE disbanded_at IS NULL")
        all_ids = [r["id"] for r in cursor.fetchall()]
        ranked = sorted(all_ids, key=lambda gid: _guild_ranking_score(cursor, gid)["score"], reverse=True)
        if not ranked or ranked[0] != guild_id:
            raise HTTPException(403, "Только гильдия №1 может назначать титулы")

        if data.to_guild_id == guild_id:
            raise HTTPException(400, "Нельзя назначить титул своей гильдии")

        # Check target guild exists
        cursor.execute("SELECT id FROM guilds WHERE id = ? AND disbanded_at IS NULL", (data.to_guild_id,))
        if not cursor.fetchone():
            raise HTTPException(404, "Целевая гильдия не найдена")

        # Check cooldown — max 1 title per day per target
        cursor.execute("""
            SELECT id FROM guild_titles
            WHERE from_guild_id = ? AND to_guild_id = ?
              AND created_at > datetime('now', '-1 day')
        """, (guild_id, data.to_guild_id))
        if cursor.fetchone():
            raise HTTPException(429, "Можно назначать титул одной гильдии раз в сутки")

        preset = _GUILD_TITLE_PRESETS[data.preset]
        cursor.execute("""
            INSERT INTO guild_titles (from_guild_id, to_guild_id, title_text, effect_type, effect_value, expires_at)
            VALUES (?, ?, ?, ?, ?, datetime('now', '+1 day'))
        """, (guild_id, data.to_guild_id, preset["title_text"], preset["effect_type"], preset["effect_value"]))
        conn.commit()

    return {"message": f"Титул «{preset['title_text']}» назначен!"}


@app.post("/api/guilds/{guild_id}/member-titles")
def assign_member_title(guild_id: int, data: GuildMemberTitleRequest, user: dict = Depends(require_auth)):
    """Top-1 guild president can assign per-member titles: positive to own members, negative to enemies."""
    uid = user["id"]
    if data.preset not in _GUILD_MEMBER_TITLE_PRESETS:
        raise HTTPException(400, "Неизвестный тип титула")

    preset = _GUILD_MEMBER_TITLE_PRESETS[data.preset]

    with get_db() as conn:
        cursor = conn.cursor()
        # Verify user is president of the requesting guild
        cursor.execute(
            "SELECT role FROM guild_members WHERE guild_id = ? AND user_id = ?",
            (guild_id, uid),
        )
        row = cursor.fetchone()
        if not row or row["role"] != "president":
            raise HTTPException(403, "Только президент может назначать титулы")

        # Verify this guild is #1
        cursor.execute("SELECT id FROM guilds WHERE disbanded_at IS NULL")
        all_ids = [r["id"] for r in cursor.fetchall()]
        ranked = sorted(all_ids, key=lambda gid: _guild_ranking_score(cursor, gid)["score"], reverse=True)
        if not ranked or ranked[0] != guild_id:
            raise HTTPException(403, "Только гильдия №1 может назначать титулы")

        # Check target user exists
        cursor.execute("SELECT id FROM users WHERE id = ?", (data.to_user_id,))
        if not cursor.fetchone():
            raise HTTPException(404, "Пользователь не найден")

        # All titles are now positive → only own members
        cursor.execute(
            "SELECT guild_id FROM guild_members WHERE user_id = ?",
            (data.to_user_id,),
        )
        target_membership = cursor.fetchone()
        is_own_member = target_membership and target_membership["guild_id"] == guild_id

        if not is_own_member:
            raise HTTPException(400, "Титулы можно давать только своим участникам")

        # For category_block, require a category
        effect_meta = None
        if data.preset == "category_block":
            if not data.category or data.category.lower() not in ("python", "javascript", "frontend", "scratch"):
                raise HTTPException(400, "Укажите категорию: python, javascript, frontend, scratch")
            import json as _json
            effect_meta = _json.dumps({"category": data.category.lower()})

        # Check cooldown — 1 title per user per day
        cursor.execute("""
            SELECT id FROM guild_member_titles
            WHERE from_guild_id = ? AND to_user_id = ?
              AND created_at > datetime('now', '-1 day')
        """, (guild_id, data.to_user_id))
        if cursor.fetchone():
            raise HTTPException(429, "Можно назначать титул одному игроку раз в сутки")

        # Check active title limit
        cursor.execute("""
            SELECT COUNT(*) as cnt FROM guild_member_titles
            WHERE from_guild_id = ? AND expires_at > CURRENT_TIMESTAMP
        """, (guild_id,))
        if cursor.fetchone()["cnt"] >= _MAX_ACTIVE_MEMBER_TITLES:
            raise HTTPException(400, f"Максимум {_MAX_ACTIVE_MEMBER_TITLES} активных титулов одновременно")

        cursor.execute("""
            INSERT INTO guild_member_titles
                (from_guild_id, to_user_id, title_text, effect_type, effect_value, effect_meta, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now', ?))
        """, (guild_id, data.to_user_id, preset["title_text"], preset["effect_type"],
              preset["effect_value"], effect_meta, preset["duration"]))
        conn.commit()

    return {"message": f"{preset['icon']} Титул «{preset['title_text']}» назначен!"}


@app.get("/api/guilds/my-titles")
def get_my_member_titles(user: dict = Depends(require_auth)):
    """Get active per-member titles for current user."""
    uid = user["id"]
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT mt.*, g.name as from_guild_name
            FROM guild_member_titles mt
            JOIN guilds g ON g.id = mt.from_guild_id
            WHERE mt.to_user_id = ? AND mt.expires_at > CURRENT_TIMESTAMP
            ORDER BY mt.created_at DESC
        """, (uid,))
        titles = [dict(t) for t in cursor.fetchall()]
    return {"titles": titles}


# ==================== GUILD: TITLE RENAME ====================

class TitleRenameRequest(BaseModel):
    title_text: str

@app.put("/api/guilds/{guild_id}/member-titles/{title_id}/rename")
def rename_member_title(guild_id: int, title_id: int, data: TitleRenameRequest, user: dict = Depends(require_auth)):
    """President can rename active member titles."""
    uid = user["id"]
    new_name = data.title_text.strip()
    if not new_name or len(new_name) < 2 or len(new_name) > 30:
        raise HTTPException(400, "Название титула: 2—30 символов")

    with get_db() as conn:
        cursor = conn.cursor()
        # Verify president
        cursor.execute(
            "SELECT role FROM guild_members WHERE guild_id = ? AND user_id = ?",
            (guild_id, uid),
        )
        row = cursor.fetchone()
        if not row or row["role"] != "president":
            raise HTTPException(403, "Только президент может переименовывать титулы")

        # Verify title belongs to this guild and is active
        cursor.execute(
            "SELECT id FROM guild_member_titles WHERE id = ? AND from_guild_id = ? AND expires_at > CURRENT_TIMESTAMP",
            (title_id, guild_id),
        )
        if not cursor.fetchone():
            raise HTTPException(404, "Титул не найден или истёк")

        cursor.execute(
            "UPDATE guild_member_titles SET title_text = ? WHERE id = ?",
            (new_name, title_id),
        )
        conn.commit()
    return {"message": f"Титул переименован в «{new_name}»"}


# ==================== GUILD: RANK NAME CUSTOMIZATION ====================

class RoleNameRequest(BaseModel):
    custom_role_name: str

@app.put("/api/guilds/{guild_id}/members/{member_id}/role-name")
def set_custom_role_name(guild_id: int, member_id: int, data: RoleNameRequest, user: dict = Depends(require_auth)):
    """Rename guild rank display name. President can rename anyone, members can rename only themselves."""
    uid = user["id"]
    new_name = data.custom_role_name.strip()
    if not new_name or len(new_name) < 2 or len(new_name) > 30:
        raise HTTPException(400, "Название ранга: 2—30 символов")

    with get_db() as conn:
        cursor = conn.cursor()

        # Check caller is in guild
        cursor.execute(
            "SELECT role FROM guild_members WHERE guild_id = ? AND user_id = ?",
            (guild_id, uid),
        )
        caller = cursor.fetchone()
        if not caller:
            raise HTTPException(403, "Вы не в этой гильдии")

        is_president = caller["role"] == "president"

        # Non-presidents can only rename themselves
        if not is_president and member_id != uid:
            raise HTTPException(403, "Вы можете переименовать только свой ранг")

        # Verify target is in guild
        cursor.execute(
            "SELECT id FROM guild_members WHERE guild_id = ? AND user_id = ?",
            (guild_id, member_id),
        )
        if not cursor.fetchone():
            raise HTTPException(404, "Участник не найден")

        cursor.execute(
            "UPDATE guild_members SET custom_role_name = ? WHERE guild_id = ? AND user_id = ?",
            (new_name, guild_id, member_id),
        )
        conn.commit()
    return {"message": f"Ранг переименован в «{new_name}»"}


# ==================== ADMIN: TIME TRACKING ====================

@app.get("/api/admin/time-tracking")
def admin_time_tracking(days: int = Query(7, le=365), admin: dict = Depends(require_admin)):
    """Get time tracking data for all students."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT u.id, u.display_name,
                   COALESCE(SUM(tt.total_seconds), 0) as total_seconds,
                   COALESCE(SUM(tt.task_seconds), 0) as task_seconds,
                   COALESCE(SUM(tt.alextype_seconds), 0) as alextype_seconds
            FROM users u
            LEFT JOIN time_tracking tt ON tt.user_id = u.id
            WHERE u.role = 'student'
            GROUP BY u.id
            ORDER BY total_seconds DESC
        """)
        students = [dict(r) for r in cursor.fetchall()]

        # Daily breakdown for requested period
        cursor.execute("""
            SELECT tt.user_id, tt.date, tt.total_seconds, tt.task_seconds, tt.alextype_seconds
            FROM time_tracking tt
            JOIN users u ON u.id = tt.user_id AND u.role = 'student'
            WHERE tt.date >= date('now', ? || ' days')
            ORDER BY tt.date ASC
        """, (str(-days),))
        daily_data = {}
        for r in cursor.fetchall():
            uid = r["user_id"]
            if uid not in daily_data:
                daily_data[uid] = []
            daily_data[uid].append(dict(r))

        for s in students:
            s["daily"] = daily_data.get(s["id"], [])

    return {"students": students}


# ==================== GUILD: MEMBER TIME TRACKING ====================

@app.get("/api/guilds/{guild_id}/members/{member_id}/time-tracking")
def guild_member_time_tracking(guild_id: int, member_id: int, days: int = Query(7, le=365), user: dict = Depends(require_auth)):
    """Get time tracking for a guild member. President and the member themselves can view."""
    uid = user["id"]
    with get_db() as conn:
        cursor = conn.cursor()

        # Check caller is in guild
        cursor.execute(
            "SELECT role FROM guild_members WHERE guild_id = ? AND user_id = ?",
            (guild_id, uid),
        )
        caller = cursor.fetchone()
        if not caller:
            raise HTTPException(403, "Вы не в этой гильдии")

        is_president = caller["role"] == "president"
        if not is_president and member_id != uid:
            raise HTTPException(403, "Только президент может просматривать время других участников")

        # Verify target is in guild
        cursor.execute(
            "SELECT id FROM guild_members WHERE guild_id = ? AND user_id = ?",
            (guild_id, member_id),
        )
        if not cursor.fetchone():
            raise HTTPException(404, "Участник не найден")

        # Aggregated totals
        cursor.execute("""
            SELECT COALESCE(SUM(total_seconds), 0) as total_seconds,
                   COALESCE(SUM(task_seconds), 0) as task_seconds,
                   COALESCE(SUM(alextype_seconds), 0) as alextype_seconds
            FROM time_tracking WHERE user_id = ?
        """, (member_id,))
        totals = dict(cursor.fetchone())

        # Daily breakdown for requested period
        cursor.execute("""
            SELECT date, total_seconds, task_seconds, alextype_seconds
            FROM time_tracking
            WHERE user_id = ? AND date >= date('now', ? || ' days')
            ORDER BY date ASC
        """, (member_id, str(-days)))
        daily = [dict(r) for r in cursor.fetchall()]

    return {"totals": totals, "daily": daily}


# ==================== ADMIN: GUILD MANAGEMENT ====================

@app.post("/api/admin/guilds/settings")
def update_guild_settings(data: GuildSettingsRequest, admin: dict = Depends(require_admin)):
    """Update guild settings (max guilds, etc.)."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO guild_settings (key, value) VALUES ('max_guilds', ?)",
            (str(data.max_guilds),),
        )
        conn.commit()
    return {"message": f"Лимит гильдий: {data.max_guilds}"}


@app.get("/api/admin/guilds/settings")
def get_guild_settings(admin: dict = Depends(require_admin)):
    """Get guild settings."""
    with get_db() as conn:
        cursor = conn.cursor()
        max_guilds = _get_max_guilds(cursor)
    return {"max_guilds": max_guilds}


@app.post("/api/admin/guilds/{guild_id}/disband")
def admin_disband_guild(guild_id: int, admin: dict = Depends(require_admin)):
    """Admin force-disband a guild."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM guilds WHERE id = ? AND disbanded_at IS NULL", (guild_id,))
        if not cursor.fetchone():
            raise HTTPException(404, "Гильдия не найдена")
        cursor.execute(
            "UPDATE guilds SET disbanded_at = CURRENT_TIMESTAMP WHERE id = ?",
            (guild_id,),
        )
        cursor.execute("DELETE FROM guild_members WHERE guild_id = ?", (guild_id,))
        cursor.execute("DELETE FROM guild_titles WHERE from_guild_id = ? OR to_guild_id = ?", (guild_id, guild_id))
        conn.commit()
    return {"message": "Гильдия расформирована администратором"}


@app.get("/api/admin/guilds/rankings")
def admin_guild_rankings(admin: dict = Depends(require_admin)):
    """Get guild rankings for admin panel with historical data."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT g.id, g.name, g.avatar_emoji, g.avatar_url, g.created_at FROM guilds g WHERE g.disbanded_at IS NULL")
        guilds = []
        for row in cursor.fetchall():
            g = dict(row)
            stats = _guild_ranking_score(cursor, g["id"])
            g.update(stats)
            guilds.append(g)
        guilds.sort(key=lambda x: x["score"], reverse=True)
        for i, g in enumerate(guilds):
            g["rank"] = i + 1
    return {"rankings": guilds}


# ==================== HEARTBEAT ====================

class HeartbeatRequest(BaseModel):
    context: str = "general"  # "general", "tasks", "alextype"

_HEARTBEAT_INTERVAL_S = 30  # Expected heartbeat interval

@app.post("/api/heartbeat")
def heartbeat(body: HeartbeatRequest = HeartbeatRequest(), user: dict = Depends(require_auth)):
    """Update user's last_seen_at and track time on platform."""
    uid = user["id"]
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    ctx = body.context if body.context in ("general", "tasks", "alextype") else "general"

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET last_seen_at = CURRENT_TIMESTAMP WHERE id = ?",
            (uid,),
        )
        # Upsert time tracking
        cursor.execute("""
            INSERT INTO time_tracking (user_id, date, total_seconds, task_seconds, alextype_seconds)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id, date) DO UPDATE SET
                total_seconds = total_seconds + ?,
                task_seconds = task_seconds + ?,
                alextype_seconds = alextype_seconds + ?
        """, (
            uid, today,
            _HEARTBEAT_INTERVAL_S,
            _HEARTBEAT_INTERVAL_S if ctx == "tasks" else 0,
            _HEARTBEAT_INTERVAL_S if ctx == "alextype" else 0,
            _HEARTBEAT_INTERVAL_S,
            _HEARTBEAT_INTERVAL_S if ctx == "tasks" else 0,
            _HEARTBEAT_INTERVAL_S if ctx == "alextype" else 0,
        ))
        conn.commit()
    return {"ok": True}


# ==================== GUILD: MEMBER DETAIL ====================

@app.get("/api/guilds/{guild_id}/members/{member_id}/detail")
def get_guild_member_detail(guild_id: int, member_id: int, user: dict = Depends(require_auth)):
    """Get detailed stats for a guild member. President sees full stats."""
    uid = user["id"]
    with get_db() as conn:
        cursor = conn.cursor()

        # Verify requester is in the guild
        cursor.execute(
            "SELECT role FROM guild_members WHERE guild_id = ? AND user_id = ?",
            (guild_id, uid),
        )
        my_row = cursor.fetchone()
        if not my_row:
            raise HTTPException(403, "Вы не в этой гильдии")

        is_president = my_row["role"] == "president"

        # Verify target is in the guild
        cursor.execute(
            "SELECT role FROM guild_members WHERE guild_id = ? AND user_id = ?",
            (guild_id, member_id),
        )
        if not cursor.fetchone():
            raise HTTPException(404, "Участник не найден")

        # Basic info
        cursor.execute("""
            SELECT u.id, u.display_name, u.xp, u.level, u.created_at, u.last_seen_at,
                   COALESCE(s.total_quests, 0) as total_quests,
                   COALESCE(s.streak_days, 0) as streak_days,
                   COALESCE(s.best_streak, 0) as best_streak,
                   gm.role, gm.custom_role_name, gm.joined_at
            FROM users u
            LEFT JOIN user_stats s ON s.user_id = u.id
            JOIN guild_members gm ON gm.user_id = u.id AND gm.guild_id = ?
            WHERE u.id = ?
        """, (guild_id, member_id))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(404, "Пользователь не найден")

        detail = dict(row)

        # Rank
        cursor.execute(
            "SELECT name_ru, badge_emoji, color FROM ranks WHERE min_xp <= ? ORDER BY min_xp DESC LIMIT 1",
            (detail["xp"],),
        )
        rank = cursor.fetchone()
        if rank:
            detail["rank_name"] = rank["name_ru"]
            detail["rank_badge"] = rank["badge_emoji"]
            detail["rank_color"] = rank["color"]

        # Recent completions (last 10)
        cursor.execute("""
            SELECT task_id, completed_at, xp_earned
            FROM completed_tasks
            WHERE user_id = ? AND is_valid = 1
            ORDER BY completed_at DESC
            LIMIT 10
        """, (member_id,))
        detail["recent_completions"] = [dict(r) for r in cursor.fetchall()]

        # Category breakdown (from submissions if available)
        try:
            cursor.execute("""
                SELECT category, COUNT(*) as count, SUM(xp_earned) as total_xp
                FROM completed_tasks
                WHERE user_id = ? AND is_valid = 1 AND category IS NOT NULL
                GROUP BY category
            """, (member_id,))
            detail["category_stats"] = [dict(r) for r in cursor.fetchall()]
        except Exception:
            detail["category_stats"] = []

        # President-only: XP log (last 20 entries)
        if is_president:
            cursor.execute("""
                SELECT xp_change, reason, logged_at
                FROM xp_log
                WHERE user_id = ?
                ORDER BY logged_at DESC
                LIMIT 20
            """, (member_id,))
            detail["xp_log"] = [dict(r) for r in cursor.fetchall()]

            # Today's activity (XP earned today)
            cursor.execute("""
                SELECT COALESCE(SUM(xp_change), 0) as today_xp
                FROM xp_log
                WHERE user_id = ? AND DATE(logged_at) = DATE('now')
                AND xp_change > 0
            """, (member_id,))
            detail["today_xp"] = cursor.fetchone()["today_xp"]

        detail["is_president_view"] = is_president

    return detail


# ==================== GUILD: PRESIDENT XP ADJUST ====================

class GuildXpAdjust(BaseModel):
    delta_xp: int
    reason: str = ""


@app.post("/api/guilds/{guild_id}/members/{member_id}/xp")
def president_adjust_xp(guild_id: int, member_id: int, body: GuildXpAdjust, user: dict = Depends(require_auth)):
    """President adjusts member XP. Daily limit: ±200 total."""
    uid = user["id"]
    delta = body.delta_xp

    if delta == 0:
        raise HTTPException(400, "Значение не может быть 0")

    with get_db() as conn:
        cursor = conn.cursor()

        # Check president
        cursor.execute(
            "SELECT role FROM guild_members WHERE guild_id = ? AND user_id = ?",
            (guild_id, uid),
        )
        row = cursor.fetchone()
        if not row or row["role"] != "president":
            raise HTTPException(403, "Только президент может изменять XP")

        # Check target is in guild and not self
        if member_id == uid:
            raise HTTPException(400, "Нельзя изменять свой XP")

        cursor.execute(
            "SELECT id FROM guild_members WHERE guild_id = ? AND user_id = ?",
            (guild_id, member_id),
        )
        if not cursor.fetchone():
            raise HTTPException(404, "Участник не найден")

        # Daily limit: sum of absolute adjustments today by this president
        cursor.execute("""
            SELECT COALESCE(SUM(ABS(xp_change)), 0) as used
            FROM xp_log
            WHERE user_id = ? AND reason LIKE 'guild_president_adjust%'
            AND DATE(logged_at) = DATE('now')
        """, (member_id,))
        used_today = cursor.fetchone()["used"]
        remaining = 200 - used_today

        if abs(delta) > remaining:
            raise HTTPException(
                400,
                f"Дневной лимит 200 XP. Использовано {used_today}, осталось {remaining}",
            )

        reason = f"guild_president_adjust: {body.reason}" if body.reason else "guild_president_adjust"
        new_xp, new_level = apply_xp_change(cursor, member_id, delta, reason)
        conn.commit()

    sign = "+" if delta > 0 else ""
    return {"message": f"XP изменён на {sign}{delta} (осталось {remaining - abs(delta)}/200 на сегодня)", "new_xp": new_xp, "new_level": new_level}


# ==================== GUILD: CHAT ====================

@app.get("/api/guilds/{guild_id}/chat")
def get_guild_chat(guild_id: int, limit: int = Query(50, le=100), user: dict = Depends(require_auth)):
    """Get guild chat messages."""
    uid = user["id"]
    with get_db() as conn:
        cursor = conn.cursor()
        # Verify membership
        cursor.execute(
            "SELECT id FROM guild_members WHERE guild_id = ? AND user_id = ?",
            (guild_id, uid),
        )
        if not cursor.fetchone():
            raise HTTPException(403, "Вы не в этой гильдии")

        cursor.execute("""
            SELECT gcm.id, gcm.message, gcm.created_at,
                   gcm.sender_id, u.display_name, gm.role
            FROM guild_chat_messages gcm
            JOIN users u ON u.id = gcm.sender_id
            JOIN guild_members gm ON gm.user_id = gcm.sender_id AND gm.guild_id = ?
            WHERE gcm.guild_id = ?
            ORDER BY gcm.created_at DESC
            LIMIT ?
        """, (guild_id, guild_id, limit))
        messages = [dict(m) for m in cursor.fetchall()]
        messages.reverse()  # chronological order
    return {"messages": messages}


class GuildChatMessage(BaseModel):
    message: str


@app.post("/api/guilds/{guild_id}/chat")
def send_guild_chat(guild_id: int, msg: GuildChatMessage, user: dict = Depends(require_auth)):
    """Send message to guild chat."""
    uid = user["id"]
    text = msg.message.strip()
    if not text or len(text) > 500:
        raise HTTPException(400, "Сообщение от 1 до 500 символов")

    with get_db() as conn:
        cursor = conn.cursor()
        # Verify membership
        cursor.execute(
            "SELECT id FROM guild_members WHERE guild_id = ? AND user_id = ?",
            (guild_id, uid),
        )
        if not cursor.fetchone():
            raise HTTPException(403, "Вы не в этой гильдии")

        # Rate limit: 1 msg/sec
        cursor.execute("""
            SELECT COUNT(*) as cnt FROM guild_chat_messages
            WHERE guild_id = ? AND sender_id = ?
            AND created_at > datetime('now', '-1 second')
        """, (guild_id, uid))
        if cursor.fetchone()["cnt"] > 0:
            raise HTTPException(429, "Подождите секунду")

        cursor.execute(
            "INSERT INTO guild_chat_messages (guild_id, sender_id, message) VALUES (?, ?, ?)",
            (guild_id, uid, text),
        )
        conn.commit()
    return {"message": "ok"}


# ==================== GUILD: AVATAR UPLOAD ====================

@app.post("/api/guilds/{guild_id}/avatar")
async def upload_guild_avatar(guild_id: int, file: UploadFile = File(...), user: dict = Depends(require_auth)):
    """Upload guild avatar image. President only. Max 2MB."""
    uid = user["id"]
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT role FROM guild_members WHERE guild_id = ? AND user_id = ?",
            (guild_id, uid),
        )
        row = cursor.fetchone()
        if not row or row["role"] != "president":
            raise HTTPException(403, "Только президент может загружать фото гильдии")

        # Validate file
        if not file.content_type or not file.content_type.startswith("image/"):
            raise HTTPException(400, "Файл должен быть изображением")

        contents = await file.read()
        if len(contents) > 2 * 1024 * 1024:
            raise HTTPException(400, "Максимальный размер 2 МБ")

        ext = file.filename.rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else "png"
        if ext not in ("png", "jpg", "jpeg", "webp", "gif"):
            ext = "png"

        filename = f"guild_{guild_id}.{ext}"
        file_path = Path("uploads") / filename
        with open(file_path, "wb") as f:
            f.write(contents)

        avatar_url = f"/uploads/{filename}"
        cursor.execute("UPDATE guilds SET avatar_url = ? WHERE id = ?", (avatar_url, guild_id))
        conn.commit()

    return {"avatar_url": avatar_url}


# ==================== GUILD: INVITE SYSTEM ====================

@app.post("/api/guilds/{guild_id}/invite/{user_id}")
def send_guild_invite(guild_id: int, user_id: int, user: dict = Depends(require_auth)):
    """Send guild invitation. Chairman or President only."""
    uid = user["id"]
    with get_db() as conn:
        cursor = conn.cursor()

        # Check sender is chairman+
        cursor.execute(
            "SELECT role FROM guild_members WHERE guild_id = ? AND user_id = ?",
            (guild_id, uid),
        )
        row = cursor.fetchone()
        if not row or row["role"] not in ("president", "chairman"):
            raise HTTPException(403, "Только председатель или президент может приглашать")

        # Check guild is active
        cursor.execute("SELECT id FROM guilds WHERE id = ? AND disbanded_at IS NULL", (guild_id,))
        if not cursor.fetchone():
            raise HTTPException(404, "Гильдия не найдена")

        # Check target is not self
        if user_id == uid:
            raise HTTPException(400, "Нельзя пригласить себя")

        # Check target exists and is student
        cursor.execute("SELECT id FROM users WHERE id = ? AND role = 'student'", (user_id,))
        if not cursor.fetchone():
            raise HTTPException(404, "Пользователь не найден")

        # Check target is not already in a guild
        cursor.execute("""
            SELECT gm.id FROM guild_members gm
            JOIN guilds g ON g.id = gm.guild_id
            WHERE gm.user_id = ? AND g.disbanded_at IS NULL
        """, (user_id,))
        if cursor.fetchone():
            raise HTTPException(400, "Пользователь уже в гильдии")

        # Check no pending invite already exists from this guild
        cursor.execute("""
            SELECT id FROM guild_invitations
            WHERE guild_id = ? AND to_user_id = ? AND status = 'pending'
        """, (guild_id, user_id))
        if cursor.fetchone():
            raise HTTPException(400, "Приглашение уже отправлено")

        cursor.execute("""
            INSERT INTO guild_invitations (guild_id, from_user_id, to_user_id)
            VALUES (?, ?, ?)
        """, (guild_id, uid, user_id))
        conn.commit()

    return {"message": "Приглашение отправлено"}


@app.get("/api/guilds/invitations/my")
def get_my_invitations(user: dict = Depends(require_auth)):
    """Get pending invitations for current user."""
    uid = user["id"]
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT gi.id, gi.guild_id, gi.from_user_id, gi.created_at,
                   g.name as guild_name, g.avatar_emoji, g.avatar_url,
                   u.display_name as from_user_name
            FROM guild_invitations gi
            JOIN guilds g ON g.id = gi.guild_id AND g.disbanded_at IS NULL
            JOIN users u ON u.id = gi.from_user_id
            WHERE gi.to_user_id = ? AND gi.status = 'pending'
            ORDER BY gi.created_at DESC
        """, (uid,))
        invitations = [dict(r) for r in cursor.fetchall()]
    return {"invitations": invitations}


@app.post("/api/guilds/invitations/{invite_id}/accept")
def accept_invitation(invite_id: int, user: dict = Depends(require_auth)):
    """Accept guild invitation and join the guild."""
    uid = user["id"]
    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT gi.*, g.name as guild_name
            FROM guild_invitations gi
            JOIN guilds g ON g.id = gi.guild_id AND g.disbanded_at IS NULL
            WHERE gi.id = ? AND gi.to_user_id = ? AND gi.status = 'pending'
        """, (invite_id, uid))
        inv = cursor.fetchone()
        if not inv:
            raise HTTPException(404, "Приглашение не найдено или истекло")

        # Check user not already in a guild
        cursor.execute("""
            SELECT gm.id FROM guild_members gm
            JOIN guilds g ON g.id = gm.guild_id
            WHERE gm.user_id = ? AND g.disbanded_at IS NULL
        """, (uid,))
        if cursor.fetchone():
            raise HTTPException(400, "Вы уже в гильдии")

        # Join
        cursor.execute(
            "INSERT INTO guild_members (guild_id, user_id, role) VALUES (?, ?, 'developer')",
            (inv["guild_id"], uid),
        )

        # Mark invite accepted
        cursor.execute(
            "UPDATE guild_invitations SET status = 'accepted', resolved_at = CURRENT_TIMESTAMP WHERE id = ?",
            (invite_id,),
        )

        # Decline all other pending invites for this user
        cursor.execute(
            "UPDATE guild_invitations SET status = 'declined', resolved_at = CURRENT_TIMESTAMP WHERE to_user_id = ? AND status = 'pending' AND id != ?",
            (uid, invite_id),
        )

        conn.commit()
    return {"message": f"Вы вступили в гильдию «{inv['guild_name']}»!"}


@app.post("/api/guilds/invitations/{invite_id}/decline")
def decline_invitation(invite_id: int, user: dict = Depends(require_auth)):
    """Decline guild invitation."""
    uid = user["id"]
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM guild_invitations WHERE id = ? AND to_user_id = ? AND status = 'pending'",
            (invite_id, uid),
        )
        if not cursor.fetchone():
            raise HTTPException(404, "Приглашение не найдено")

        cursor.execute(
            "UPDATE guild_invitations SET status = 'declined', resolved_at = CURRENT_TIMESTAMP WHERE id = ?",
            (invite_id,),
        )
        conn.commit()
    return {"message": "Приглашение отклонено"}


# ==================== STARTUP ====================

if __name__ == "__main__":
    import uvicorn
    import socket
    
    def get_local_ip():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"
    
    local_ip = get_local_ip()
    
    print("\n" + "═"*60)
    print("  ⚔️  PANDORA - CODE ADVENTURES | SENSEI NODE v3.0")
    print("═"*60)
    print(f"\n  📡  Server:  http://{local_ip}:8000")
    print("  🔑  Admin:   created on first run (see server logs)")
    print(f"\n  📋  Tell students to enter IP: {local_ip}")
    print("\n" + "═"*60 + "\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
