import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch


os.environ.setdefault("PANDORA_SKIP_STARTUP", "1")

import main  # noqa: E402


class ParentPanelTests(unittest.TestCase):
    def setUp(self):
        self._old_database = main.DATABASE
        self._tempdir = tempfile.TemporaryDirectory()
        main.DATABASE = os.path.join(self._tempdir.name, "parents-test.db")
        with main.get_db() as conn:
            conn.executescript(
                """
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    role TEXT DEFAULT 'student',
                    xp INTEGER DEFAULT 0,
                    level INTEGER DEFAULT 1,
                    avatar_key TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_seen_at TIMESTAMP
                );
                CREATE TABLE parent_child_links (
                    parent_id INTEGER NOT NULL,
                    child_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (parent_id, child_id)
                );
                CREATE TABLE parent_xp_actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    parent_id INTEGER NOT NULL, child_id INTEGER NOT NULL,
                    delta_xp INTEGER NOT NULL, applied_xp INTEGER NOT NULL DEFAULT 0,
                    reason TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE completed_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL, task_id TEXT NOT NULL,
                    completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    solution TEXT, xp_earned INTEGER DEFAULT 0,
                    is_valid INTEGER DEFAULT 1,
                    comment_bonus_status TEXT DEFAULT 'none',
                    comment_bonus_awarded INTEGER DEFAULT 0
                );
                CREATE TABLE task_solution_methods (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER, task_id TEXT, method_index INTEGER,
                    code_language TEXT, solution TEXT, xp_earned INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE task_attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER, task_id TEXT, category TEXT, tier TEXT,
                    code TEXT, payload_z BLOB, payload_codec TEXT,
                    result_json TEXT, passed INTEGER, runtime_ms INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE time_tracking (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER, date TEXT, total_seconds INTEGER DEFAULT 0,
                    task_seconds INTEGER DEFAULT 0, alextype_seconds INTEGER DEFAULT 0
                );
                CREATE TABLE user_stats (
                    user_id INTEGER PRIMARY KEY, streak_days INTEGER DEFAULT 0,
                    best_streak INTEGER DEFAULT 0
                );
                CREATE TABLE submissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER, task_id TEXT, status TEXT,
                    score INTEGER, max_score INTEGER DEFAULT 10, feedback TEXT,
                    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    reviewed_at TIMESTAMP, reviewer_id INTEGER
                );
                CREATE TABLE mini_admin_reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    submission_id INTEGER, mini_admin_id INTEGER, score INTEGER,
                    admin_final_score INTEGER, admin_approved INTEGER DEFAULT 0,
                    reviewed_at TIMESTAMP
                );
                CREATE TABLE ranks (
                    id INTEGER PRIMARY KEY, name_ru TEXT, badge_emoji TEXT, min_xp INTEGER
                );
                CREATE TABLE xp_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER, xp_change INTEGER, reason TEXT,
                    logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE sessions (token TEXT PRIMARY KEY, user_id INTEGER);
                """
            )
            conn.executemany(
                """
                INSERT INTO users (id, username, password_hash, display_name, role, xp, level)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (1, "admin", "x", "Admin", "admin", 0, 1),
                    (2, "child", "x", "Child One", "student", 750, 5),
                    (3, "other", "x", "Child Two", "student", 100, 2),
                ],
            )
            conn.execute("INSERT INTO ranks VALUES (1, 'Ученик', '🌱', 0)")
            conn.execute(
                "INSERT INTO completed_tasks (user_id, task_id, solution, xp_earned) VALUES (2, 'task-1', 'print(1)', 100)"
            )
            conn.execute(
                "INSERT INTO task_attempts (user_id, task_id, category, code, passed, runtime_ms) VALUES (2, 'task-1', 'python', 'print(1)', 1, 15)"
            )
            conn.execute(
                "INSERT INTO time_tracking (user_id, date, total_seconds, task_seconds) VALUES (2, date('now'), 3600, 2400)"
            )
            conn.execute("INSERT INTO user_stats VALUES (2, 3, 7)")
            conn.execute("INSERT INTO xp_log (user_id, xp_change, reason) VALUES (2, 100, 'task')")
            conn.commit()
        self.admin = {"id": 1, "username": "admin", "role": "admin"}

    def tearDown(self):
        main.DATABASE = self._old_database
        self._tempdir.cleanup()

    def _create_parent(self):
        return main.admin_create_parent(
            None,
            main.ParentCreateRequest(
                username="parent_one",
                password="secret1",
                display_name="Parent One",
                child_id=2,
            ),
            self.admin,
        )

    def test_admin_can_create_reassign_and_delete_parent(self):
        created = self._create_parent()
        parent_id = created["id"]
        listed = main.admin_list_parents(self.admin)
        self.assertEqual(listed["parents"][0]["children"][0]["id"], 2)

        main.admin_set_parent_child(
            parent_id,
            main.ParentChildRequest(child_id=3),
            self.admin,
        )
        listed = main.admin_list_parents(self.admin)
        self.assertEqual(listed["parents"][0]["children"][0]["id"], 3)

        main.admin_delete_parent(parent_id, self.admin)
        self.assertEqual(main.admin_list_parents(self.admin)["parents"], [])

    def test_parent_dashboard_is_scoped_to_assigned_child(self):
        parent_id = self._create_parent()["id"]
        parent = {"id": parent_id, "username": "parent_one", "role": "parent"}
        catalog = {
            "tasks": [
                {"id": "task-1", "title": "Первая задача", "category": "python", "tier": "D", "xp": 100},
                {"id": "task-2", "title": "Вторая задача", "category": "python", "tier": "D", "xp": 100},
            ]
        }
        with patch.object(main, "load_tasks", return_value=catalog):
            data = main.parent_dashboard(None, parent)
            tasks = main.parent_completions(None, 50, 0, parent)

        self.assertEqual(data["child"]["id"], 2)
        self.assertEqual(data["summary"]["completed_tasks"], 1)
        self.assertEqual(data["summary"]["time"]["total_seconds"], 3600)
        self.assertEqual(data["summary"]["dominant_mode"], "tasks")
        self.assertEqual(tasks["completions"][0]["solution"], "print(1)")
        with patch.object(main, "load_tasks", return_value=catalog):
            with self.assertRaises(main.HTTPException) as denied:
                main.parent_dashboard(3, parent)
        self.assertEqual(denied.exception.status_code, 404)

    def test_alextype_becomes_primary_when_it_has_most_time(self):
        parent_id = self._create_parent()["id"]
        parent = {"id": parent_id, "username": "parent_one", "role": "parent"}
        with main.get_db() as conn:
            conn.execute(
                "UPDATE time_tracking SET total_seconds = 5000, task_seconds = 500, alextype_seconds = 4000 WHERE user_id = 2"
            )
            conn.execute(
                "INSERT INTO xp_log (user_id, xp_change, reason) VALUES (2, 240, 'AlexType C (180 символов, 96%)')"
            )
            conn.commit()
        with patch.object(main, "load_tasks", return_value={"tasks": []}):
            data = main.parent_dashboard(None, parent)
        alex = data["summary"]["alextype"]
        self.assertEqual(data["summary"]["dominant_mode"], "alextype")
        self.assertEqual(alex["time_seconds"], 4000)
        self.assertEqual(alex["xp"], 240)
        self.assertEqual(alex["average_accuracy"], 96.0)
        self.assertEqual(alex["best_level"], "C")

    def test_admin_and_parent_can_change_parent_password(self):
        parent_id = self._create_parent()["id"]
        parent = {"id": parent_id, "username": "parent_one", "role": "parent"}
        main.reset_user_password(
            main.ResetPasswordRequest(user_id=parent_id, new_password="admin-set-2"),
            self.admin,
        )
        main.change_password(
            main.ChangePasswordRequest(
                current_password="admin-set-2",
                new_password="parent-set-3",
            ),
            parent,
        )
        with main.get_db() as conn:
            password_hash = conn.execute(
                "SELECT password_hash FROM users WHERE id = ?", (parent_id,)
            ).fetchone()["password_hash"]
        self.assertTrue(main.verify_password("parent-set-3", password_hash))

    def test_parent_can_adjust_only_linked_child_with_daily_cap(self):
        parent_id = self._create_parent()["id"]
        parent = {"id": parent_id, "username": "parent_one", "role": "parent"}
        reward = main.parent_xp_action(
            main.ParentXPActionRequest(delta_xp=3000, reason="Отличная самостоятельная работа"),
            None,
            parent,
        )
        penalty = main.parent_xp_action(
            main.ParentXPActionRequest(delta_xp=-2000, reason="Не выполнена договорённость"),
            None,
            parent,
        )
        self.assertEqual(reward["applied_xp"], 3000)
        self.assertEqual(penalty["applied_xp"], -2000)
        self.assertEqual(penalty["remaining_today"], 0)
        with self.assertRaises(main.HTTPException) as capped:
            main.parent_xp_action(
                main.ParentXPActionRequest(delta_xp=1, reason="Ещё один бонус"),
                None,
                parent,
            )
        self.assertEqual(capped.exception.status_code, 409)
        with self.assertRaises(main.HTTPException) as denied:
            main.parent_xp_action(
                main.ParentXPActionRequest(delta_xp=10, reason="Чужой ребёнок"),
                3,
                parent,
            )
        self.assertEqual(denied.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
