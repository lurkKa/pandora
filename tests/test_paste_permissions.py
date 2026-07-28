import os
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor


os.environ.setdefault("PANDORA_SKIP_STARTUP", "1")

import main  # noqa: E402


class PastePermissionTests(unittest.TestCase):
    def setUp(self):
        self._old_database = main.DATABASE
        self._tempdir = tempfile.TemporaryDirectory()
        main.DATABASE = os.path.join(self._tempdir.name, "paste-test.db")

        conn = sqlite3.connect(main.DATABASE)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                username TEXT,
                display_name TEXT,
                role TEXT
            )
        """)
        conn.executemany(
            "INSERT INTO users (id, username, display_name, role) VALUES (?, ?, ?, ?)",
            [
                (1, "student", "Student", "student"),
                (2, "admin", "Admin", "admin"),
            ],
        )
        # Start from the legacy schema to exercise the production migration.
        conn.execute("""
            CREATE TABLE paste_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                task_id TEXT NOT NULL,
                task_title TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                resolved_at TIMESTAMP
            )
        """)
        conn.executemany(
            """
            INSERT INTO paste_requests (user_id, task_id, status)
            VALUES (1, ?, ?)
            """,
            [("legacy-approved", "approved"), ("legacy-pending", "pending")],
        )
        main._migrate_paste_requests(conn.cursor())
        conn.commit()
        conn.close()

        self.student = {"id": 1, "username": "student", "role": "student"}
        self.admin = {"id": 2, "username": "admin", "role": "admin"}

    def tearDown(self):
        main.DATABASE = self._old_database
        self._tempdir.cleanup()

    def _request(self, task_id="task-a", session_id="editor_session_0001"):
        return main.create_paste_request(
            main.PasteRequest(
                task_id=task_id,
                task_title=task_id,
                client_session_id=session_id,
            ),
            user=self.student,
        )

    def _status(self, request):
        return main.check_paste_request_status(
            task_id=request["task_id"],
            request_id=request["request_id"],
            request_token=request["request_token"],
            client_session_id=request["client_session_id"],
            user=self.student,
        )

    def _consume(self, request):
        return main.consume_paste_request(
            request["request_id"],
            main.PasteConsumeRequest(
                task_id=request["task_id"],
                request_token=request["request_token"],
                client_session_id=request["client_session_id"],
            ),
            user=self.student,
        )

    def test_migration_revokes_all_legacy_live_rows(self):
        with main.get_db() as conn:
            rows = conn.execute(
                "SELECT status, request_token, client_session_id FROM paste_requests ORDER BY id"
            ).fetchall()
        self.assertEqual([row["status"] for row in rows], ["expired", "expired"])
        self.assertTrue(all(row["request_token"] is None for row in rows))
        self.assertTrue(all(row["client_session_id"] is None for row in rows))

    def test_grant_is_bound_to_task_request_and_editor_session(self):
        request = self._request()
        main.approve_paste_request(request["request_id"], user=self.admin)
        self.assertTrue(self._status(request)["approved"])

        with self.assertRaises(main.HTTPException) as wrong_task:
            main.check_paste_request_status(
                task_id="task-b",
                request_id=request["request_id"],
                request_token=request["request_token"],
                client_session_id=request["client_session_id"],
                user=self.student,
            )
        self.assertEqual(wrong_task.exception.status_code, 404)

        with self.assertRaises(main.HTTPException) as wrong_session:
            main.check_paste_request_status(
                task_id=request["task_id"],
                request_id=request["request_id"],
                request_token=request["request_token"],
                client_session_id="different_session_0002",
                user=self.student,
            )
        self.assertEqual(wrong_session.exception.status_code, 404)

        with self.assertRaises(main.HTTPException) as wrong_user:
            main.check_paste_request_status(
                task_id=request["task_id"],
                request_id=request["request_id"],
                request_token=request["request_token"],
                client_session_id=request["client_session_id"],
                user=self.admin,
            )
        self.assertEqual(wrong_user.exception.status_code, 404)

    def test_new_task_request_supersedes_previous_approval(self):
        first = self._request("task-a", "editor_session_0001")
        main.approve_paste_request(first["request_id"], user=self.admin)
        second = self._request("task-b", "editor_session_0002")

        first_status = self._status(first)
        self.assertEqual(first_status["status"], "superseded")
        self.assertFalse(first_status["approved"])
        self.assertTrue(second["pending"])

    def test_consume_is_atomic_and_one_shot(self):
        request = self._request()
        main.approve_paste_request(request["request_id"], user=self.admin)

        def consume_once():
            try:
                self._consume(request)
                return 200
            except main.HTTPException as exc:
                return exc.status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = sorted(pool.map(lambda _: consume_once(), range(2)))

        self.assertEqual(results, [200, 409])
        status = self._status(request)
        self.assertTrue(status["consumed"])
        self.assertFalse(status["approved"])

    def test_parallel_create_is_idempotent_for_same_session(self):
        def create_once(_):
            return self._request()["request_id"]

        with ThreadPoolExecutor(max_workers=6) as pool:
            request_ids = list(pool.map(create_once, range(6)))

        self.assertEqual(len(set(request_ids)), 1)
        with main.get_db() as conn:
            active_count = conn.execute("""
                SELECT COUNT(*)
                FROM paste_requests
                WHERE user_id = 1 AND status IN ('pending', 'approved')
            """).fetchone()[0]
        self.assertEqual(active_count, 1)

    def test_admin_resolution_is_compare_and_set(self):
        request = self._request()

        def approve_once():
            try:
                main.approve_paste_request(request["request_id"], user=self.admin)
                return 200
            except main.HTTPException as exc:
                return exc.status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = sorted(pool.map(lambda _: approve_once(), range(2)))

        self.assertEqual(results, [200, 409])
        self.assertTrue(self._status(request)["approved"])

    def test_expired_approval_cannot_be_consumed(self):
        request = self._request()
        main.approve_paste_request(request["request_id"], user=self.admin)
        with main.get_db() as conn:
            conn.execute(
                "UPDATE paste_requests SET expires_at = datetime('now', '-1 second') WHERE id = ?",
                (request["request_id"],),
            )
            conn.commit()

        self.assertEqual(self._status(request)["status"], "expired")
        with self.assertRaises(main.HTTPException) as expired:
            self._consume(request)
        self.assertEqual(expired.exception.status_code, 409)


if __name__ == "__main__":
    unittest.main()
