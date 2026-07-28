import os
import sqlite3
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone


os.environ.setdefault("PANDORA_SKIP_STARTUP", "1")

import main  # noqa: E402


class DatabaseMaintenanceTests(unittest.TestCase):
    def setUp(self):
        self._old_database = main.DATABASE
        self._tempdir = tempfile.TemporaryDirectory()
        main.DATABASE = os.path.join(self._tempdir.name, "maintenance.db")
        with main.get_db() as conn:
            conn.executescript(
                """
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY,
                    username TEXT,
                    xp INTEGER DEFAULT 0,
                    level INTEGER DEFAULT 1
                );
                CREATE TABLE sessions (
                    token TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    expires_at TIMESTAMP
                );
                CREATE TABLE user_stats (
                    user_id INTEGER PRIMARY KEY,
                    avatar_data TEXT
                );
                CREATE INDEX idx_user_stats_user ON user_stats(user_id);
                CREATE TABLE typing_sessions (
                    id TEXT PRIMARY KEY,
                    started_at REAL NOT NULL,
                    result_status TEXT NOT NULL
                );
                CREATE TABLE typing_integrity_incidents (
                    id INTEGER PRIMARY KEY,
                    session_id TEXT NOT NULL UNIQUE
                );
                CREATE TABLE task_attempts (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    task_id TEXT NOT NULL,
                    code TEXT,
                    result_json TEXT,
                    payload_z BLOB,
                    payload_codec TEXT,
                    passed INTEGER,
                    runtime_ms INTEGER
                );
                """
            )
            conn.execute(
                "INSERT INTO users (id, username) VALUES (1, 'live-user')"
            )
            now = time.time()
            old_iso = (
                datetime.now(timezone.utc) - timedelta(days=45)
            ).strftime("%Y-%m-%d %H:%M:%S")
            future_iso = (
                datetime.now(timezone.utc) + timedelta(days=10)
            ).strftime("%Y-%m-%d %H:%M:%S")
            conn.executemany(
                "INSERT INTO sessions (token, user_id, expires_at) VALUES (?, 1, ?)",
                [
                    ("old-epoch", int(now - 45 * 86400)),
                    ("recent-expired", int(now - 5 * 86400)),
                    ("future-epoch", int(now + 10 * 86400)),
                    ("old-iso", old_iso),
                    ("future-iso", future_iso),
                ],
            )
            conn.executemany(
                "INSERT INTO user_stats (user_id, avatar_data) VALUES (?, ?)",
                [(1, "live-avatar"), (999, "orphan-avatar")],
            )
            old = now - 45 * 86400
            conn.executemany(
                "INSERT INTO typing_sessions (id, started_at, result_status) VALUES (?, ?, ?)",
                [
                    ("old-clean", old, "clean"),
                    ("old-incident", old, "clean"),
                    ("old-penalized", old, "penalized"),
                    ("recent-clean", now, "clean"),
                ],
            )
            conn.execute(
                "INSERT INTO typing_integrity_incidents (id, session_id) VALUES (1, 'old-incident')"
            )
            conn.commit()

    def tearDown(self):
        main.DATABASE = self._old_database
        self._tempdir.cleanup()

    def test_prunes_only_expired_or_orphaned_technical_rows(self):
        with main.get_db() as conn:
            deleted = main._prune_technical_database_rows(conn.cursor())
            conn.commit()
            session_tokens = {
                row["token"]
                for row in conn.execute("SELECT token FROM sessions")
            }
            profile_ids = {
                row["user_id"]
                for row in conn.execute("SELECT user_id FROM user_stats")
            }
            typing_ids = {
                row["id"]
                for row in conn.execute("SELECT id FROM typing_sessions")
            }

        self.assertEqual(deleted["expired_sessions"], 2)
        self.assertEqual(
            session_tokens,
            {"recent-expired", "future-epoch", "future-iso"},
        )
        self.assertEqual(deleted["orphan_user_stats"], 1)
        self.assertEqual(profile_ids, {1})
        self.assertEqual(deleted["old_typing_sessions"], 1)
        self.assertEqual(
            typing_ids,
            {"old-incident", "old-penalized", "recent-clean"},
        )

    def test_drops_only_named_indexes_already_covered_by_constraints(self):
        with main.get_db() as conn:
            cursor = conn.cursor()
            dropped = main._drop_redundant_database_indexes(cursor)
            conn.commit()
            named_index = cursor.execute(
                """
                SELECT 1 FROM sqlite_master
                WHERE type = 'index' AND name = 'idx_user_stats_user'
                """
            ).fetchone()
            profile = cursor.execute(
                "SELECT avatar_data FROM user_stats WHERE user_id = 1"
            ).fetchone()

        self.assertEqual(dropped, 1)
        self.assertIsNone(named_index)
        self.assertEqual(profile["avatar_data"], "live-avatar")

    def test_task_attempt_payload_compression_is_lossless_and_bounded(self):
        attempts = [
            (1, "print('Привет 🌍')\\n", '{"passed":true,"cases":[1,2,3]}'),
            (2, None, '{"passed":false,"error":"boom"}'),
        ]
        with main.get_db() as conn:
            conn.executemany(
                """
                INSERT INTO task_attempts (
                    id, user_id, task_id, code, result_json, passed, runtime_ms
                ) VALUES (?, 1, 'task-a', ?, ?, 1, 25)
                """,
                attempts,
            )
            first_batch = main._compress_legacy_task_attempt_payloads(
                conn.cursor(),
                limit=1,
            )
            conn.commit()
            first = conn.execute(
                """
                SELECT code, result_json, payload_z, payload_codec
                FROM task_attempts WHERE id = 1
                """
            ).fetchone()
            second_raw = conn.execute(
                "SELECT code, result_json, payload_z FROM task_attempts WHERE id = 2"
            ).fetchone()

            second_batch = main._compress_legacy_task_attempt_payloads(
                conn.cursor(),
                limit=None,
            )
            conn.commit()
            second = conn.execute(
                """
                SELECT code, result_json, payload_z, payload_codec
                FROM task_attempts WHERE id = 2
                """
            ).fetchone()

        self.assertEqual(first_batch["rows"], 1)
        self.assertIsNone(first["code"])
        self.assertIsNone(first["result_json"])
        self.assertEqual(
            main._decode_task_attempt_payload(
                first["payload_z"],
                first["payload_codec"],
            ),
            attempts[0][1:],
        )
        self.assertEqual(second_raw["code"], attempts[1][1])
        self.assertIsNone(second_raw["payload_z"])
        self.assertEqual(second_batch["rows"], 1)
        self.assertIsNone(second["code"])
        self.assertIsNone(second["result_json"])
        self.assertEqual(
            main._decode_task_attempt_payload(
                second["payload_z"],
                second["payload_codec"],
            ),
            attempts[1][1:],
        )

    def test_rank_sync_preserves_existing_ids(self):
        with main.get_db() as conn:
            conn.execute(
                """
                CREATE TABLE ranks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    name_ru TEXT NOT NULL,
                    min_xp INTEGER NOT NULL,
                    badge_emoji TEXT NOT NULL,
                    color TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                INSERT INTO ranks (
                    id, name, name_ru, min_xp, badge_emoji, color
                ) VALUES (
                    7, 'Shadow Initiate', 'old', 999, '?', '#000000'
                )
                """
            )
            conn.execute(
                """
                INSERT INTO ranks (
                    id, name, name_ru, min_xp, badge_emoji, color
                ) VALUES (
                    8, 'Retired Rank', 'old', 1, '?', '#000000'
                )
                """
            )

            main._sync_ranks(conn.cursor())
            first_ids = {
                row["name"]: row["id"]
                for row in conn.execute("SELECT id, name FROM ranks")
            }
            main._sync_ranks(conn.cursor())
            second_ids = {
                row["name"]: row["id"]
                for row in conn.execute("SELECT id, name FROM ranks")
            }
            shadow = conn.execute(
                """
                SELECT id, name_ru, min_xp
                FROM ranks
                WHERE name = 'Shadow Initiate'
                """
            ).fetchone()
            conn.commit()

        self.assertEqual(shadow["id"], 7)
        self.assertEqual(shadow["name_ru"], "Тень-Посвящённый")
        self.assertEqual(shadow["min_xp"], 0)
        self.assertEqual(len(first_ids), 27)
        self.assertEqual(first_ids, second_ids)
        self.assertNotIn("Retired Rank", first_ids)


if __name__ == "__main__":
    unittest.main()
