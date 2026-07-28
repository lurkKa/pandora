import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone


os.environ.setdefault("PANDORA_SKIP_STARTUP", "1")

import main  # noqa: E402


class EventEngineTests(unittest.TestCase):
    def setUp(self):
        self._old_database = main.DATABASE
        self._tempdir = tempfile.TemporaryDirectory()
        main.DATABASE = os.path.join(self._tempdir.name, "events-test.db")

        conn = sqlite3.connect(main.DATABASE)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(
            """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                username TEXT NOT NULL,
                display_name TEXT NOT NULL,
                role TEXT NOT NULL,
                xp INTEGER DEFAULT 0,
                level INTEGER DEFAULT 1,
                avatar_key TEXT
            );
            CREATE TABLE events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                bonus_type TEXT NOT NULL,
                bonus_value REAL NOT NULL,
                is_active INTEGER DEFAULT 0,
                color TEXT DEFAULT '#7c3aed',
                template_key TEXT DEFAULT 'custom',
                event_type TEXT DEFAULT 'standard',
                status TEXT DEFAULT 'draft',
                duration_hours INTEGER DEFAULT 24,
                theme_key TEXT DEFAULT 'arcane',
                starts_at TIMESTAMP,
                ends_at TIMESTAMP,
                ended_at TIMESTAMP,
                created_by INTEGER,
                finalized_at TIMESTAMP,
                winner_user_id INTEGER,
                winner_event_xp INTEGER DEFAULT 0,
                winner_tasks_count INTEGER DEFAULT 0,
                reward_xp INTEGER DEFAULT 0,
                reward_min INTEGER DEFAULT 10000,
                reward_max INTEGER DEFAULT 100000,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE event_progress (
                event_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                event_xp INTEGER DEFAULT 0,
                tasks_solved INTEGER DEFAULT 0,
                first_earned_at TIMESTAMP,
                last_earned_at TIMESTAMP,
                PRIMARY KEY (event_id, user_id)
            );
            CREATE TABLE event_task_completions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                task_id TEXT NOT NULL,
                xp_earned INTEGER NOT NULL,
                completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(event_id, user_id, task_id)
            );
            CREATE TABLE xp_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                xp_change INTEGER NOT NULL,
                reason TEXT,
                task_id TEXT,
                logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE rewards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                icon TEXT NOT NULL,
                title TEXT NOT NULL,
                comment TEXT,
                awarded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                awarded_by INTEGER
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
        conn.executemany(
            """
            INSERT INTO users (id, username, display_name, role, xp, level)
            VALUES (?, ?, ?, ?, 0, 1)
            """,
            [
                (1, "alice", "Alice", "student"),
                (2, "bob", "Bob", "student"),
                (9, "admin", "Admin", "admin"),
            ],
        )
        conn.commit()
        conn.close()
        self.admin = {"id": 9, "username": "admin", "display_name": "Admin", "role": "admin"}

    def tearDown(self):
        main.DATABASE = self._old_database
        self._tempdir.cleanup()

    def _insert_active_judgment(self, ends_at="2099-01-01 00:00:00"):
        with main.get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO events (
                    name, description, bonus_type, bonus_value, is_active,
                    template_key, event_type, status, duration_hours, theme_key,
                    starts_at, ends_at, reward_min, reward_max
                )
                VALUES (
                    'Судный день', 'test', 'event_score', 1, 1,
                    'judgment_day', 'judgment_day', 'active', 96, 'judgment',
                    '2020-01-01 00:00:00', ?, 10000, 100000
                )
                """,
                (ends_at,),
            )
            event_id = cursor.lastrowid
            conn.commit()
            return event_id

    def test_judgment_uses_isolated_score_and_unique_task_ledger(self):
        event_id = self._insert_active_judgment()
        with main.get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET xp = 4321, level = 7 WHERE id = 1")
            first = main._record_active_event_task_progress(cursor, 1, "task-a", 120)
            duplicate = main._record_active_event_task_progress(cursor, 1, "task-a", 999)
            second = main._record_active_event_task_progress(cursor, 1, "task-b", 80)
            conn.commit()

            self.assertEqual(first["event_id"], event_id)
            self.assertEqual(duplicate["event_xp"], 120)
            self.assertEqual(second["event_xp"], 200)
            self.assertEqual(second["tasks_solved"], 2)
            self.assertEqual(
                cursor.execute("SELECT COUNT(*) FROM event_task_completions").fetchone()[0],
                2,
            )
            # Recording event progress never resets or mutates permanent XP.
            self.assertEqual(cursor.execute("SELECT xp FROM users WHERE id = 1").fetchone()[0], 4321)

    def test_finish_picks_leader_by_score_then_tasks_and_rewards_once(self):
        event_id = self._insert_active_judgment()
        with main.get_db() as conn:
            conn.executemany(
                """
                INSERT INTO event_progress (
                    event_id, user_id, event_xp, tasks_solved, first_earned_at, last_earned_at
                )
                VALUES (?, ?, 500, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                [(event_id, 1, 3), (event_id, 2, 4)],
            )
            conn.commit()

        first = main.stop_event(event_id, admin=self.admin)["event"]
        second = main.stop_event(event_id, admin=self.admin)["event"]

        self.assertEqual(first["winner_user_id"], 2)
        self.assertEqual(first["winner_event_xp"], 500)
        self.assertEqual(first["winner_tasks_count"], 4)
        self.assertEqual(first["reward_xp"], 14500)
        self.assertTrue(second["already_finalized"])

        with main.get_db() as conn:
            self.assertEqual(conn.execute("SELECT xp FROM users WHERE id = 2").fetchone()[0], 14500)
            self.assertEqual(
                conn.execute(
                    "SELECT COUNT(*) FROM xp_log WHERE reason = ?",
                    (f"event_reward:judgment_day:{event_id}",),
                ).fetchone()[0],
                1,
            )
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM rewards").fetchone()[0], 1)

    def test_template_creates_draft_and_judgment_start_is_exactly_four_days(self):
        with main.get_db() as conn:
            conn.execute("UPDATE users SET xp = 321 WHERE id = 1")
            conn.execute("UPDATE users SET xp = 654 WHERE id = 2")
            conn.commit()

        created = main.create_event(
            main.EventCreateRequest(template_key="judgment_day"),
            admin=self.admin,
        )
        event_id = created["id"]
        self.assertEqual(created["event"]["status"], "draft")
        self.assertFalse(created["event"]["is_active"])

        started = main.start_event(event_id, admin=self.admin)["event"]
        starts_at = datetime.fromisoformat(started["starts_at"].replace("Z", "+00:00"))
        ends_at = datetime.fromisoformat(started["ends_at"].replace("Z", "+00:00"))
        self.assertEqual((ends_at - starts_at).total_seconds(), 4 * 24 * 60 * 60)
        self.assertEqual(started["status"], "active")

        with main.get_db() as conn:
            # Launching the visual fresh-score mode preserves every user's XP.
            self.assertEqual(
                conn.execute(
                    "SELECT SUM(xp) FROM users WHERE role = 'student'"
                ).fetchone()[0],
                975,
            )

    def test_expired_event_auto_finalizes_and_does_not_repeat_reward(self):
        event_id = self._insert_active_judgment(ends_at="2020-01-02 00:00:00")
        with main.get_db() as conn:
            conn.execute(
                """
                INSERT INTO event_progress (
                    event_id, user_id, event_xp, tasks_solved, first_earned_at, last_earned_at
                )
                VALUES (?, 1, 900, 2, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                (event_id,),
            )
            conn.commit()

        first = main._finalize_expired_events()
        second = main._finalize_expired_events()
        self.assertEqual(len(first), 1)
        self.assertEqual(second, [])
        self.assertEqual(first[0]["winner_user_id"], 1)
        self.assertEqual(first[0]["reward_xp"], 11500)
        with main.get_db() as conn:
            self.assertEqual(conn.execute("SELECT xp FROM users WHERE id = 1").fetchone()[0], 11500)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM rewards").fetchone()[0], 1)

    def test_only_one_event_can_be_active_and_repeated_start_is_idempotent(self):
        first_id = main.create_event(
            main.EventCreateRequest(template_key="double_xp_24h"),
            admin=self.admin,
        )["id"]
        second_id = main.create_event(
            main.EventCreateRequest(template_key="xp_marathon_7d"),
            admin=self.admin,
        )["id"]

        first_start = main.start_event(first_id, admin=self.admin)["event"]
        repeated_start = main.start_event(first_id, admin=self.admin)["event"]
        self.assertTrue(repeated_start["already_active"])
        self.assertEqual(repeated_start["starts_at"], first_start["starts_at"])
        self.assertEqual(repeated_start["ends_at"], first_start["ends_at"])

        with self.assertRaises(main.HTTPException) as conflict:
            main.start_event(second_id, admin=self.admin)
        self.assertEqual(conflict.exception.status_code, 409)
        with main.get_db() as conn:
            self.assertEqual(
                conn.execute(
                    "SELECT COUNT(*) FROM events WHERE status = 'active' AND is_active = 1"
                ).fetchone()[0],
                1,
            )

    def test_prize_formula_is_bounded(self):
        self.assertEqual(main._event_reward_for_tasks(0, 10000, 100000), 0)
        self.assertEqual(main._event_reward_for_tasks(1, 10000, 100000), 10000)
        self.assertEqual(main._event_reward_for_tasks(4, 10000, 100000), 14500)
        self.assertEqual(main._event_reward_for_tasks(10000, 10000, 100000), 100000)


if __name__ == "__main__":
    unittest.main()
