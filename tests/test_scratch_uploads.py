import io
import os
import tempfile
import unittest
import zipfile
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("PANDORA_SKIP_STARTUP", "1")

from fastapi.testclient import TestClient
import main


class ScratchUploadTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        temp = self.stack.enter_context(tempfile.TemporaryDirectory())
        old_cwd = os.getcwd()
        os.chdir(temp)
        self.stack.callback(os.chdir, old_cwd)
        Path("uploads").mkdir()
        self.stack.enter_context(patch.object(main, "DATABASE", str(Path(temp) / "scratch.db")))
        self.stack.enter_context(patch.dict(os.environ, {"PANDORA_MAX_UPLOAD_MB": "100"}))
        task = {"id": "scratch-test", "category": "scratch", "tier": "D"}
        for name, result in {
            "get_task": task,
            "_tasks_by_id": {task["id"]: task},
            "_completed_task_ids": set(),
            "_completed_task_ids_today": set(),
            "_unlock_state": (True, {}),
            "_maybe_assign_mini_admin_review": None,
            "_get_exam_state": {"is_active": True},
            "load_exam_tasks": [task],
            "_compute_exam_time_expired": 0,
        }.items():
            self.stack.enter_context(patch.object(main, name, return_value=result))
        with main.get_db() as conn:
            conn.executescript("""
                CREATE TABLE submissions (
                    id INTEGER PRIMARY KEY, user_id INTEGER, task_id TEXT,
                    category TEXT, tier TEXT, content TEXT, link TEXT, status TEXT,
                    feedback TEXT, review_reason TEXT, submitted_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE exam_progress (
                    user_id INTEGER, task_id TEXT, started_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    finished_at TEXT, cheated INTEGER DEFAULT 0, solution TEXT,
                    submission_link TEXT, submission_filename TEXT, score INTEGER,
                    xp_earned INTEGER, time_expired INTEGER, review_pending INTEGER,
                    review_submission_id INTEGER
                );
                INSERT INTO exam_progress (user_id, task_id) VALUES (1, 'scratch-test');
            """)
        overrides = main.app.dependency_overrides.copy()
        main.app.dependency_overrides[main.require_auth] = lambda: {"id": 1, "role": "student"}
        self.stack.callback(setattr, main.app, "dependency_overrides", overrides)
        self.client = TestClient(main.app)
        self.stack.callback(self.client.close)

    def upload(self, payload, route="/api/tasks/attempt-scratch-fast", filename="проект.SB3"):
        if route.endswith("-fast"):
            return self.client.post(route, params={"task_id": "scratch-test", "filename": filename}, content=payload)
        return self.client.post(route, data={"task_id": "scratch-test"}, files={"file": (filename, payload, "application/octet-stream")})

    def test_large_sb3_reaches_review_through_every_upload_route(self):
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as project:
            project.writestr("project.json", '{"targets": []}')
            project.writestr("sound.wav", b"x" * (11 * 1024 * 1024))
        payload = archive.getvalue()
        for route in sorted(main._SCRATCH_UPLOAD_PATHS):
            with self.subTest(route=route):
                with main.get_db() as conn:
                    conn.execute("DELETE FROM submissions")
                    conn.commit()
                response = self.upload(payload, route)
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()["status"], "pending_review")
                with main.get_db() as conn:
                    row = conn.execute("SELECT link, status FROM submissions").fetchone()
                self.assertEqual(row["status"], "pending")
                self.assertEqual(Path(row["link"].lstrip("/")).read_bytes(), payload)

    def test_custom_limit_config_and_file_boundaries(self):
        with patch.dict(os.environ, {"PANDORA_MAX_UPLOAD_MB": "2"}):
            self.assertEqual(self.client.get("/api/scratch/upload-config").json(), {"max_mb": 2, "max_bytes": 2 * 1024 * 1024})
            for route in sorted(main._SCRATCH_UPLOAD_PATHS):
                with self.subTest(route=route):
                    response = self.upload(b"x" * (2 * 1024 * 1024 + 1), route)
                    self.assertEqual(response.status_code, 413, response.text)
                    self.assertIn("2 МБ", response.json()["detail"])
                    self.assertEqual(list(Path("uploads").iterdir()), [])
            response = self.upload(b"x" * (2 * 1024 * 1024))
            self.assertEqual(response.status_code, 200, response.text)

    def test_empty_files_and_wrong_extensions_are_rejected(self):
        for route in sorted(main._SCRATCH_UPLOAD_PATHS):
            for content, filename in [(b"", "empty.sb3"), (b"x", "wrong.zip")]:
                with self.subTest(route=route, filename=filename):
                    response = self.upload(content, route, filename)
                    self.assertEqual(response.status_code, 400, response.text)
                    self.assertEqual(list(Path("uploads").iterdir()), [])

    def test_retry_is_saved_and_pending_submission_is_not_duplicated(self):
        with patch.object(main, "_completed_task_ids", return_value={"scratch-test"}):
            first = self.upload(b"project")
            self.assertEqual(first.json()["status"], "pending_review")
            second = self.upload(b"replacement")
            self.assertEqual(first.json()["submission_id"], second.json()["submission_id"])
            self.assertEqual(len(list(Path("uploads").iterdir())), 1)

    def test_other_request_bodies_keep_the_small_limit(self):
        response = self.client.post("/api/tasks/attempt", content=b"x" * (main._MAX_REQUEST_BODY_BYTES + 1))
        self.assertEqual(response.status_code, 413)

    def test_invalid_limit_configuration_uses_default(self):
        for value in ["", "invalid", "0", "-1"]:
            with self.subTest(value=value), patch.dict(os.environ, {"PANDORA_MAX_UPLOAD_MB": value}):
                self.assertEqual(main.scratch_upload_config()["max_mb"], 100)


class ScratchStreamingTests(unittest.IsolatedAsyncioTestCase):
    async def test_chunked_limit_returns_413_and_removes_partial_file(self):
        # No Content-Length: the middleware must count incoming chunks, and
        # the endpoint must clean up even when the middleware raises first.
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        path = Path(temp.name) / "project.sb3"
        with patch.object(main, "Path", return_value=Path(temp.name)), \
             patch.object(main.uuid, "uuid4", return_value="project"), \
             patch.object(main, "get_task", return_value={"category": "scratch"}), \
             patch.object(main, "_tasks_by_id", return_value={}), \
             patch.object(main, "get_db"), \
             patch.object(main, "_completed_task_ids", return_value=set()), \
             patch.object(main, "_completed_task_ids_today", return_value=set()), \
             patch.object(main, "_pending_submission_for_task", return_value=None), \
             patch.object(main, "_unlock_state", return_value=(True, {})), \
             patch.dict(os.environ, {"PANDORA_MAX_UPLOAD_MB": "1"}):
            from fastapi import FastAPI
            app = FastAPI()

            @app.post("/api/tasks/attempt-scratch-fast")
            async def upload(request: main.Request):
                return await main.attempt_scratch_task_fast(request, "test", "project.sb3", {"id": 1})

            app.add_middleware(main.RequestBodyLimitMiddleware)
            chunks = iter([b"x" * (1024 * 1024), b"x"])
            messages = []

            async def receive():
                return {"type": "http.request", "body": next(chunks), "more_body": True}

            async def send(message):
                messages.append(message)

            await app({"type": "http", "method": "POST", "path": "/api/tasks/attempt-scratch-fast", "query_string": b"", "headers": [], "scheme": "http"}, receive, send)
            self.assertEqual(messages[0]["status"], 413)
            self.assertFalse(path.exists())
