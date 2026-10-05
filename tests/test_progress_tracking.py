import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

os.environ.setdefault("PANDORA_SKIP_STARTUP", "1")

import main  # noqa: E402


class ProgressTrackingTests(unittest.TestCase):
    def setUp(self):
        self.old_database = main.DATABASE
        self.tempdir = tempfile.TemporaryDirectory()
        main.DATABASE = os.path.join(self.tempdir.name, "progress.db")
        main._most_active_cache["expires"] = 0
        with main.get_db() as conn:
            conn.executescript("""
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY, username TEXT, display_name TEXT,
                    role TEXT, xp INTEGER DEFAULT 0, level INTEGER DEFAULT 1,
                    last_seen_at TIMESTAMP, avatar_key TEXT
                );
                CREATE TABLE heartbeat_state (
                    user_id INTEGER PRIMARY KEY, last_seen_at REAL,
                    context TEXT, is_active INTEGER
                );
                CREATE TABLE time_tracking_v2 (
                    user_id INTEGER, date TEXT, total_seconds INTEGER DEFAULT 0,
                    task_seconds INTEGER DEFAULT 0, alextype_seconds INTEGER DEFAULT 0,
                    PRIMARY KEY (user_id, date)
                );
                CREATE TABLE completed_tasks (
                    user_id INTEGER, task_id TEXT, is_valid INTEGER DEFAULT 1,
                    completed_at TIMESTAMP, PRIMARY KEY (user_id, task_id)
                );
                CREATE TABLE xp_log (
                    user_id INTEGER, xp_change INTEGER, reason TEXT,
                    task_id TEXT, logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE ranks (min_xp INTEGER, name_ru TEXT, badge_emoji TEXT);
                CREATE TABLE user_stats (user_id INTEGER, avatar_data TEXT);
                CREATE TABLE guilds (id INTEGER PRIMARY KEY, name TEXT, disbanded_at TIMESTAMP);
                CREATE TABLE guild_members (guild_id INTEGER, user_id INTEGER, role TEXT);
                CREATE TABLE guild_titles (to_guild_id INTEGER, effect_value REAL, expires_at TIMESTAMP);
                CREATE TABLE guild_member_titles (
                    to_user_id INTEGER, effect_type TEXT, effect_value REAL,
                    effect_meta TEXT, expires_at TIMESTAMP
                );
                INSERT INTO users (id, username, display_name, role) VALUES
                    (1, 'one', 'One', 'student'),
                    (2, 'two', 'Two', 'student');
                INSERT INTO ranks VALUES (0, 'Ученик', '🌱');
            """)
            conn.commit()

    def tearDown(self):
        main.DATABASE = self.old_database
        main._most_active_cache["expires"] = 0
        self.tempdir.cleanup()

    def test_two_day_streak_grace(self):
        today = datetime.now().date()
        self.assertEqual(main._current_streak_days(4, (today - timedelta(days=2)).isoformat()), 4)
        self.assertEqual(main._current_streak_days(4, (today - timedelta(days=3)).isoformat()), 0)
        self.assertEqual(main._next_streak_days(4, (today - timedelta(days=2)).isoformat(), today), 5)
        self.assertEqual(main._next_streak_days(4, (today - timedelta(days=3)).isoformat(), today), 1)

    def test_weekly_ranking_counts_unique_valid_quests_and_reports_max(self):
        monday = (datetime.now(timezone.utc).date() - timedelta(days=datetime.now(timezone.utc).weekday()))
        with main.get_db() as conn:
            conn.executemany(
                "INSERT INTO completed_tasks VALUES (?, ?, ?, ?)",
                [
                    (1, "old", 1, (monday - timedelta(days=1)).isoformat()),
                    (1, "a", 1, monday.isoformat()),
                    (1, "b", 1, monday.isoformat()),
                    (1, "invalid", 0, monday.isoformat()),
                    (2, "c", 1, monday.isoformat()),
                ],
            )
            conn.executemany(
                "INSERT INTO xp_log (user_id, xp_change, reason, logged_at) VALUES (?, ?, ?, ?)",
                [(1, 20, "task_completed", monday.isoformat()),
                 (2, 1000, "task_completed", monday.isoformat()),
                 (1, 500, "admin_bonus", monday.isoformat())],
            )
            conn.commit()
        with patch.object(main, "_tasks_by_id", return_value={}):
            result = main.get_leaderboard_week(20)
        self.assertEqual(result["week_start"], monday.isoformat())
        self.assertEqual(result["max_stars_week"], 2)
        self.assertEqual([row["id"] for row in result["leaderboard"]], [1, 2])
        self.assertEqual(result["leaderboard"][0]["xp_week"], 20)

    def test_weekly_stars_weight_tiers_before_ranking_and_limit(self):
        today = datetime.now(timezone.utc).date()
        monday = today - timedelta(days=today.weekday())
        tasks = {tier: {"id": tier, "tier": tier} for tier in ("S", "A", "B", "C", "D")}
        tasks["invalid"] = {"tier": "S"}
        tasks["old"] = {"tier": "S"}
        with main.get_db() as conn:
            conn.executemany("INSERT INTO completed_tasks VALUES (?, ?, ?, ?)", [
                (1, "C", 1, today.isoformat()),
                (1, "D", 1, today.isoformat()),
                (1, "removed-task", 1, today.isoformat()),
                (1, "invalid", 0, today.isoformat()),
                (1, "old", 1, (monday - timedelta(days=1)).isoformat()),
                (2, "S", 1, today.isoformat()),
            ])
            conn.commit()
        with patch.object(main, "_tasks_by_id", return_value=tasks):
            result = main.get_leaderboard_week(1)
            self.assertEqual(result["max_stars_week"], 4)
            self.assertEqual([row["id"] for row in result["leaderboard"]], [2])
            with main.get_db() as conn:
                conn.executemany("INSERT INTO completed_tasks VALUES (2, ?, 1, ?)", [("A", today.isoformat()), ("B", today.isoformat())])
                conn.commit()
            result = main.get_leaderboard_week(20)
        self.assertEqual([row["stars_week"] for row in result["leaderboard"]], [9, 3])

    def test_guild_stars_use_same_weights_and_keep_task_counts(self):
        today = datetime.now(timezone.utc).date().isoformat()
        tasks = [{"id": tier, "tier": tier, "category": "scratch"} for tier in ("S", "A", "B", "C", "D")]
        with main.get_db() as conn:
            conn.executescript("""
                ALTER TABLE completed_tasks ADD COLUMN xp_earned INTEGER DEFAULT 0;
                ALTER TABLE guilds ADD COLUMN created_at TEXT;
                ALTER TABLE user_stats ADD COLUMN streak_days INTEGER DEFAULT 0;
                ALTER TABLE user_stats ADD COLUMN best_streak INTEGER DEFAULT 0;
                INSERT INTO guilds (id, name) VALUES (1, 'Test');
                INSERT INTO guild_members VALUES (1, 1, 'leader'), (1, 2, 'member');
            """)
            conn.executemany("INSERT INTO completed_tasks (user_id, task_id, is_valid, completed_at) VALUES (1, ?, 1, ?)", [(task["id"], today) for task in tasks])
            conn.commit()
        with patch.object(main, "load_tasks", return_value={"tasks": tasks}):
            result = main.get_guild_stats(1, {"id": 1})
        self.assertEqual(result["overview"]["total_tasks"], 5)
        first, second = result["members_stars"]
        self.assertEqual((first["stars_1d"], first["stars_2d"], first["stars_week"]), (11, 11, 11))
        self.assertEqual((second["stars_1d"], second["stars_2d"], second["stars_week"]), (0, 0, 0))

    def test_heartbeat_credits_only_elapsed_active_time_and_mvp(self):
        with patch.object(main.time, "time", side_effect=[1000, 1030, 1060, 1090, 1200, 1300]):
            main.heartbeat(main.HeartbeatRequest(context="tasks", active=True), {"id": 1})
            main.heartbeat(main.HeartbeatRequest(context="general", active=True), {"id": 1})
            main.heartbeat(main.HeartbeatRequest(context="general", active=False), {"id": 1})
            main.heartbeat(main.HeartbeatRequest(context="general", active=False), {"id": 1})
            main.heartbeat(main.HeartbeatRequest(context="tasks", active=True), {"id": 1})
            main.heartbeat(main.HeartbeatRequest(context="tasks", active=True), {"id": 1})
        with main.get_db() as conn:
            row = conn.execute("SELECT * FROM time_tracking_v2 WHERE user_id = 1").fetchone()
            self.assertEqual((row["total_seconds"], row["task_seconds"]), (60, 30))
            self.assertEqual(main._get_most_active_student_id(conn.cursor()), 1)
            conn.execute(
                "INSERT INTO time_tracking_v2 VALUES (2, date('now'), 50, 50, 0)"
            )
            conn.commit()
            main._most_active_cache["expires"] = 0
            self.assertEqual(main._get_most_active_student_id(conn.cursor()), 2)

    def test_category_title_only_boosts_matching_quest(self):
        with main.get_db() as conn:
            conn.execute("""
                INSERT INTO guild_member_titles VALUES
                    (1, 'category_xp_buff', 0.2, '{"category":"python"}', datetime('now', '+3 hours'))
            """)
            with patch.object(main, "get_task", side_effect=lambda task_id: {"category": task_id}):
                main.apply_xp_change(conn.cursor(), 1, 100, "task_completed", "python")
                main.apply_xp_change(conn.cursor(), 1, 100, "task_completed", "javascript")
                main.apply_xp_change(conn.cursor(), 1, 100, "admin_bonus", "python")
            changes = [row[0] for row in conn.execute("SELECT xp_change FROM xp_log ORDER BY rowid")]
        self.assertEqual(changes[:3], [120, 100, 100])


if __name__ == "__main__":
    unittest.main()
