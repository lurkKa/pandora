import json
import os
import sqlite3
import tempfile
import time
import unittest


os.environ.setdefault("PANDORA_SKIP_STARTUP", "1")

import main  # noqa: E402


def _human_metrics(chars: int = 80) -> dict:
    metrics = main._typing_empty_metrics()
    # Deliberately varied human-like rhythm (roughly 420–650 CPM).
    pattern = [92, 137, 108, 181, 116, 149, 101, 164, 124, 143]
    events = [
        {
            "kind": "insert",
            "dt_ms": 0 if i == 0 else pattern[i % len(pattern)],
            "chars": 1,
            "trusted": True,
        }
        for i in range(chars)
    ]
    return main._aggregate_typing_events(metrics, events)


def _fixed_typer_metrics(chars: int = 100, dt_ms: int = 80) -> dict:
    metrics = main._typing_empty_metrics()
    events = [
        {
            "kind": "insert",
            "dt_ms": 0 if i == 0 else dt_ms,
            "chars": 1,
            "trusted": True,
        }
        for i in range(chars)
    ]
    main._aggregate_typing_events(metrics, events)
    # Server receipts arrive with the same cadence as 16-character typer
    # batches; this is independent of the client-reported per-key intervals.
    for _ in range(4):
        gap = 16 * dt_ms
        metrics["server_gap_count"] += 1
        metrics["server_gap_sum_ms"] += gap
        metrics["server_gap_sq_sum_ms"] += gap * gap
    return metrics


class TypingRiskScoreTests(unittest.TestCase):
    def test_human_rhythm_is_not_penalized(self):
        score = main._score_typing_integrity(
            "alextype",
            _human_metrics(),
            server_active_s=10.5,
            server_session_s=12.0,
            content_chars=80,
            batch_count=6,
            claimed_keystrokes=80,
        )
        self.assertFalse(score["high_confidence"])
        self.assertEqual(score["penalty_xp"], 0)

    def test_receipt_timing_divergence_alone_does_not_penalize_human_rhythm(self):
        score = main._score_typing_integrity(
            "alextype",
            _human_metrics(),
            server_active_s=0.5,
            server_session_s=11.0,
            content_chars=80,
            batch_count=6,
            claimed_keystrokes=80,
        )
        self.assertIn("extreme_server_speed", score["signals"])
        self.assertIn("client_server_timing_divergence", score["signals"])
        self.assertFalse(score["high_confidence"])
        self.assertEqual(score["penalty_xp"], 0)

    def test_fixed_rate_typer_is_detected_even_below_extreme_cpm(self):
        score = main._score_typing_integrity(
            "task",
            _fixed_typer_metrics(dt_ms=80),
            server_active_s=8.0,
            server_session_s=9.0,
            content_chars=100,
            expected_insertions=100,
            batch_count=7,
        )
        self.assertTrue(score["high_confidence"])
        self.assertIn("machine_uniform_intervals", score["signals"])
        self.assertIn("uniform_server_batch_cadence", score["signals"])
        self.assertGreaterEqual(score["penalty_xp"], 50)
        self.assertLessEqual(score["penalty_xp"], 500)

    def test_extreme_uniform_typer_gets_max_bounded_penalty(self):
        score = main._score_typing_integrity(
            "alextype",
            _fixed_typer_metrics(dt_ms=5),
            server_active_s=0.55,
            server_session_s=0.8,
            content_chars=100,
            batch_count=7,
            claimed_keystrokes=100,
        )
        self.assertTrue(score["high_confidence"])
        self.assertEqual(score["penalty_xp"], 500)
        self.assertIn("extreme_server_speed", score["signals"])
        self.assertIn("machine_uniform_intervals", score["signals"])

    def test_direct_programmatic_editor_fill_combines_source_and_server_speed(self):
        metrics = main._typing_empty_metrics()
        metrics["programmatic_chars"] = 140
        score = main._score_typing_integrity(
            "task",
            metrics,
            server_active_s=0.2,
            server_session_s=0.3,
            content_chars=140,
            expected_insertions=0,
            batch_count=1,
        )
        self.assertTrue(score["high_confidence"])
        self.assertIn("extreme_server_speed", score["signals"])
        self.assertIn("non_keyboard_burst", score["signals"])

    def test_short_single_batch_uses_interval_elapsed_not_near_zero_receipt_span(self):
        metrics = _human_metrics(chars=30)
        score = main._score_typing_integrity(
            "alextype",
            metrics,
            server_active_s=0.01,
            server_session_s=5.0,
            content_chars=30,
            batch_count=1,
            claimed_keystrokes=30,
        )
        self.assertLess(score["evidence"]["server_cpm"], 900)
        self.assertFalse(score["high_confidence"])

    def test_missing_or_sparse_telemetry_cannot_create_penalty(self):
        score = main._score_typing_integrity(
            "task",
            main._typing_empty_metrics(),
            server_active_s=0.01,
            server_session_s=0.01,
            content_chars=500,
            expected_insertions=500,
            batch_count=0,
        )
        self.assertFalse(score["high_confidence"])
        self.assertEqual(score["risk_score"], 55)  # speed alone is insufficient
        self.assertEqual(score["penalty_xp"], 0)

    def test_untrusted_auto_event_does_not_count_as_trusted_keyboard_input(self):
        metrics = main._aggregate_typing_events(
            main._typing_empty_metrics(),
            [{"kind": "auto", "dt_ms": 0, "chars": 4, "trusted": False}],
        )
        self.assertEqual(metrics["inserted_chars"], 4)
        self.assertEqual(metrics["trusted_inserted_chars"], 0)
        self.assertEqual(metrics["programmatic_chars"], 4)


class TypingPenaltyLedgerTests(unittest.TestCase):
    def setUp(self):
        self._old_database = main.DATABASE
        self._tempdir = tempfile.TemporaryDirectory()
        main.DATABASE = os.path.join(self._tempdir.name, "typing-test.db")
        conn = sqlite3.connect(main.DATABASE)
        conn.executescript(
            """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                username TEXT,
                display_name TEXT,
                role TEXT,
                xp INTEGER DEFAULT 0,
                level INTEGER DEFAULT 1
            );
            CREATE TABLE xp_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                xp_change INTEGER NOT NULL,
                reason TEXT,
                task_id TEXT,
                logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE typing_sessions (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                scope TEXT NOT NULL,
                task_id TEXT,
                level TEXT,
                expected_length INTEGER DEFAULT 0,
                content_hash TEXT,
                receipt_hash TEXT NOT NULL,
                last_sequence INTEGER DEFAULT 0,
                batch_count INTEGER DEFAULT 0,
                event_count INTEGER DEFAULT 0,
                metrics_json TEXT DEFAULT '{}',
                started_at REAL NOT NULL,
                first_event_at REAL,
                last_event_at REAL,
                expires_at REAL NOT NULL,
                finalized_at REAL,
                result_status TEXT DEFAULT 'active',
                risk_score INTEGER DEFAULT 0,
                penalty_xp INTEGER DEFAULT 0
            );
            CREATE TABLE typing_integrity_incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL UNIQUE,
                user_id INTEGER NOT NULL,
                scope TEXT NOT NULL,
                task_id TEXT,
                confidence REAL NOT NULL,
                risk_score INTEGER NOT NULL,
                signals_json TEXT NOT NULL,
                evidence_json TEXT NOT NULL,
                penalty_xp INTEGER NOT NULL,
                applied_xp INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE typing_telemetry_batches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                sequence INTEGER NOT NULL,
                received_at REAL NOT NULL,
                event_count INTEGER NOT NULL,
                payload_hash TEXT NOT NULL,
                summary_json TEXT DEFAULT '{}',
                UNIQUE(session_id, sequence)
            );
            CREATE TABLE audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor_user_id INTEGER,
                actor_username TEXT,
                action TEXT NOT NULL,
                target_user_id INTEGER,
                target_task_id TEXT,
                delta_xp INTEGER,
                meta_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        conn.execute(
            "INSERT INTO users (id, username, display_name, role, xp, level) VALUES (1, 'student', 'Student', 'student', 1000, 5)"
        )
        conn.execute(
            "INSERT INTO users (id, username, display_name, role, xp, level) VALUES (2, 'other', 'Other', 'student', 1000, 5)"
        )
        conn.commit()
        conn.close()

    def tearDown(self):
        main.DATABASE = self._old_database
        self._tempdir.cleanup()

    def test_finalize_is_single_use_and_penalty_is_applied_once(self):
        receipt = "server-one-time-receipt"
        now = time.time()
        metrics = _fixed_typer_metrics(dt_ms=5)
        with main.get_db() as conn:
            conn.execute(
                """
                INSERT INTO typing_sessions (
                    id, user_id, scope, task_id, expected_length, receipt_hash,
                    batch_count, event_count, metrics_json, started_at,
                    first_event_at, last_event_at, expires_at
                ) VALUES (?, 1, 'alextype', NULL, 100, ?, 7, 100, ?, ?, ?, ?, ?)
                """,
                (
                    "typing-session-1",
                    main._typing_receipt_hash(receipt),
                    json.dumps(metrics),
                    now - 1.0,
                    now - 0.55,
                    now - 0.05,
                    now + 600,
                ),
            )
            conn.commit()

        user = {"id": 1, "username": "student", "role": "student"}
        with main.get_db() as conn:
            cursor = conn.cursor()
            first = main._finalize_typing_session(
                cursor,
                user=user,
                scope="alextype",
                session_id="typing-session-1",
                receipt=receipt,
                content_chars=100,
                expected_length=100,
                claimed_keystrokes=100,
            )
            conn.commit()

        self.assertTrue(first["high_confidence"])
        self.assertEqual(first["penalty_xp"], 500)
        self.assertEqual(first["applied_xp"], 500)

        with main.get_db() as conn:
            cursor = conn.cursor()
            second = main._finalize_typing_session(
                cursor,
                user=user,
                scope="alextype",
                session_id="typing-session-1",
                receipt=receipt,
                content_chars=100,
                expected_length=100,
                claimed_keystrokes=100,
            )
            conn.commit()
            xp = conn.execute("SELECT xp FROM users WHERE id = 1").fetchone()["xp"]
            incidents = conn.execute(
                "SELECT COUNT(*) AS cnt FROM typing_integrity_incidents"
            ).fetchone()["cnt"]
            penalties = conn.execute(
                "SELECT COUNT(*) AS cnt FROM xp_log WHERE reason = 'typing_integrity:alextype'"
            ).fetchone()["cnt"]

        self.assertFalse(second["verified"])
        self.assertEqual(second["status"], "already_finalized")
        self.assertEqual(xp, 500)
        self.assertEqual(incidents, 1)
        self.assertEqual(penalties, 1)

    def test_penalty_is_capped_by_balance_and_ledger_records_actual_delta(self):
        receipt = "low-balance-receipt"
        now = time.time()
        metrics = _fixed_typer_metrics(dt_ms=5)
        with main.get_db() as conn:
            conn.execute("UPDATE users SET xp = 35, level = 1 WHERE id = 1")
            conn.execute(
                """
                INSERT INTO typing_sessions (
                    id, user_id, scope, expected_length, receipt_hash,
                    batch_count, event_count, metrics_json, started_at,
                    first_event_at, last_event_at, expires_at
                ) VALUES (?, 1, 'alextype', 100, ?, 7, 100, ?, ?, ?, ?, ?)
                """,
                (
                    "low-balance-session",
                    main._typing_receipt_hash(receipt),
                    json.dumps(metrics),
                    now - 1,
                    now - 0.55,
                    now - 0.05,
                    now + 600,
                ),
            )
            result = main._finalize_typing_session(
                conn.cursor(),
                user={"id": 1, "username": "student", "role": "student"},
                scope="alextype",
                session_id="low-balance-session",
                receipt=receipt,
                content_chars=100,
                expected_length=100,
                claimed_keystrokes=100,
            )
            conn.commit()
            xp = conn.execute("SELECT xp FROM users WHERE id = 1").fetchone()["xp"]
            log_delta = conn.execute(
                """
                SELECT xp_change
                FROM xp_log
                WHERE reason = 'typing_integrity:alextype'
                """
            ).fetchone()["xp_change"]
            incident = conn.execute(
                """
                SELECT penalty_xp, applied_xp
                FROM typing_integrity_incidents
                WHERE session_id = 'low-balance-session'
                """
            ).fetchone()

        self.assertEqual(result["penalty_xp"], 500)
        self.assertEqual(result["applied_xp"], 35)
        self.assertEqual(xp, 0)
        self.assertEqual(log_delta, -35)
        self.assertEqual(incident["penalty_xp"], 500)
        self.assertEqual(incident["applied_xp"], 35)

    def test_session_is_bound_to_user_scope_and_task(self):
        receipt = "task-bound-receipt"
        now = time.time()
        with main.get_db() as conn:
            conn.execute(
                """
                INSERT INTO typing_sessions (
                    id, user_id, scope, task_id, receipt_hash, metrics_json,
                    started_at, expires_at
                ) VALUES (?, 1, 'task', 'task-a', ?, ?, ?, ?)
                """,
                (
                    "task-bound-session",
                    main._typing_receipt_hash(receipt),
                    json.dumps(main._typing_empty_metrics()),
                    now - 1,
                    now + 600,
                ),
            )
            conn.commit()

        owner = {"id": 1, "username": "student", "role": "student"}
        mismatched_contexts = [
            ({"id": 2, "username": "other", "role": "student"}, "task", "task-a"),
            (owner, "alextype", None),
            (owner, "task", "task-b"),
        ]
        with main.get_db() as conn:
            cursor = conn.cursor()
            for user, scope, task_id in mismatched_contexts:
                result = main._finalize_typing_session(
                    cursor,
                    user=user,
                    scope=scope,
                    session_id="task-bound-session",
                    receipt=receipt,
                    task_id=task_id,
                    content_chars=40,
                    expected_length=40,
                    expected_insertions=40,
                )
                self.assertEqual(result["status"], "context_mismatch")

            session = cursor.execute(
                """
                SELECT result_status, finalized_at
                FROM typing_sessions
                WHERE id = 'task-bound-session'
                """
            ).fetchone()
            self.assertEqual(session["result_status"], "active")
            self.assertIsNone(session["finalized_at"])

            valid = main._finalize_typing_session(
                cursor,
                user=owner,
                scope="task",
                session_id="task-bound-session",
                receipt=receipt,
                task_id="task-a",
                content_chars=40,
                expected_insertions=40,
            )
            conn.commit()

        self.assertTrue(valid["verified"])
        self.assertEqual(valid["status"], "clean")

    def test_missing_telemetry_never_applies_a_penalty(self):
        user = {"id": 1, "username": "student", "role": "student"}
        with main.get_db() as conn:
            result = main._finalize_typing_session(
                conn.cursor(),
                user=user,
                scope="task",
                session_id=None,
                receipt=None,
                task_id="task-a",
                content_chars=500,
                expected_insertions=500,
            )
            conn.commit()
            xp = conn.execute("SELECT xp FROM users WHERE id = 1").fetchone()["xp"]
            incidents = conn.execute(
                "SELECT COUNT(*) AS cnt FROM typing_integrity_incidents"
            ).fetchone()["cnt"]
            penalties = conn.execute(
                "SELECT COUNT(*) AS cnt FROM xp_log WHERE reason LIKE 'typing_integrity:%'"
            ).fetchone()["cnt"]

        self.assertFalse(result["verified"])
        self.assertEqual(result["status"], "missing")
        self.assertEqual(result["penalty_xp"], 0)
        self.assertEqual(result["applied_xp"], 0)
        self.assertEqual(xp, 1000)
        self.assertEqual(incidents, 0)
        self.assertEqual(penalties, 0)

    def test_server_rotates_receipts_and_rejects_replay(self):
        user = {"id": 1, "username": "student", "role": "student"}
        started = main.start_typing_session(
            main.TypingSessionStartRequest(
                scope="alextype",
                level="D",
                text_length=40,
                content_hash="context-only",
            ),
            user=user,
        )
        first = main.append_typing_events(
            started["session_id"],
            main.TypingTelemetryBatchRequest(
                sequence=1,
                receipt=started["receipt"],
                events=[
                    main.TypingTelemetryEvent(
                        kind="insert", dt_ms=0, chars=1, trusted=True
                    )
                ],
            ),
            user=user,
        )
        self.assertNotEqual(first["receipt"], started["receipt"])

        with self.assertRaises(main.HTTPException) as repeated_sequence:
            main.append_typing_events(
                started["session_id"],
                main.TypingTelemetryBatchRequest(
                    sequence=1,
                    receipt=first["receipt"],
                    events=[
                        main.TypingTelemetryEvent(
                            kind="insert", dt_ms=120, chars=1, trusted=True
                        )
                    ],
                ),
                user=user,
            )
        self.assertEqual(repeated_sequence.exception.status_code, 409)

        with self.assertRaises(main.HTTPException) as replay:
            main.append_typing_events(
                started["session_id"],
                main.TypingTelemetryBatchRequest(
                    sequence=2,
                    receipt=started["receipt"],
                    events=[
                        main.TypingTelemetryEvent(
                            kind="insert", dt_ms=120, chars=1, trusted=True
                        )
                    ],
                ),
                user=user,
            )
        self.assertEqual(replay.exception.status_code, 409)

        second = main.append_typing_events(
            started["session_id"],
            main.TypingTelemetryBatchRequest(
                sequence=2,
                receipt=first["receipt"],
                events=[
                    main.TypingTelemetryEvent(
                        kind="insert", dt_ms=120, chars=1, trusted=True
                    )
                ],
            ),
            user=user,
        )
        self.assertEqual(second["next_sequence"], 3)

        with main.get_db() as conn:
            result = main._finalize_typing_session(
                conn.cursor(),
                user=user,
                scope="alextype",
                session_id=started["session_id"],
                receipt=second["receipt"],
                content_chars=2,
                expected_length=40,
                claimed_keystrokes=2,
            )
            conn.commit()
        self.assertTrue(result["verified"])
        self.assertTrue(result["usable"])
        self.assertFalse(result["high_confidence"])


if __name__ == "__main__":
    unittest.main()
