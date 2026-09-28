import os
import tempfile
import unittest
from unittest.mock import patch

import bcrypt
from fastapi.testclient import TestClient

os.environ.setdefault("PANDORA_SKIP_STARTUP", "1")

import main  # noqa: E402


class ProfileThemeTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        database = patch.object(main, "DATABASE", os.path.join(self.tempdir.name, "themes.db"))
        database.start()
        self.addCleanup(database.stop)
        secret = patch.object(main, "JWT_SECRET", "profile-theme-test-secret-do-not-use-in-production")
        secret.start()
        self.addCleanup(secret.stop)
        security_log = patch.object(main, "log_security_event")
        security_log.start()
        self.addCleanup(security_log.stop)

        # A legacy users table proves the real startup migration supports
        # existing profiles without resetting their names, avatars or XP.
        with main.get_db() as conn:
            conn.executescript("""
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
                    display_name TEXT NOT NULL, role TEXT DEFAULT 'student',
                    xp INTEGER DEFAULT 0, level INTEGER DEFAULT 1,
                    avatar_key TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            password_hash = bcrypt.hashpw(b"test-password", bcrypt.gensalt(rounds=4)).decode()
            conn.executemany(
                "INSERT INTO users (id, username, password_hash, display_name, role, avatar_key) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                [
                    (1, "alice", password_hash, "Алиса", "student", "mage"),
                    (2, "boris", password_hash, "Борис", "student", "robot"),
                    (3, "teacher", password_hash, "Учитель", "admin", None),
                ],
            )
            conn.commit()
        main.init_db()
        self.client = TestClient(main.app)
        self.addCleanup(self.client.close)

    def login(self, username="alice"):
        response = self.client.post(
            "/api/auth/login", json={"username": username, "password": "test-password"}
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def headers(self, username="alice"):
        return {"Authorization": f"Bearer {self.login(username)['token']}"}

    def test_migration_is_repeatable_and_retains_selected_theme(self):
        with main.get_db() as conn:
            self.assertEqual(conn.execute("SELECT ui_theme FROM users WHERE id=1").fetchone()[0], "modern")
            conn.execute("UPDATE users SET ui_theme='classic' WHERE id=1")
            conn.commit()
        main.init_db()
        with main.get_db() as conn:
            alice = dict(conn.execute("SELECT * FROM users WHERE id=1").fetchone())
            self.assertEqual(alice["ui_theme"], "classic")
            self.assertEqual(alice["display_name"], "Алиса")
            self.assertEqual(alice["avatar_key"], "mage")
            conn.execute(
                "INSERT INTO users (username,password_hash,display_name) VALUES ('new','hash','New')"
            )
            self.assertEqual(conn.execute("SELECT ui_theme FROM users WHERE username='new'").fetchone()[0], "modern")

    def test_preference_survives_new_login_in_both_auth_modes(self):
        for stateless in (False, True):
            with self.subTest(stateless=stateless), patch.object(main, "STATELESS_AUTH", stateless):
                headers = self.headers()
                response = self.client.put("/api/profile", headers=headers, json={"ui_theme": "classic"})
                self.assertEqual(response.status_code, 200, response.text)
                # Fresh authentication models another browser/device.
                login = self.login()
                self.assertEqual(login["user"]["ui_theme"], "classic")
                fresh_headers = {"Authorization": f"Bearer {login['token']}"}
                for endpoint in ("/api/auth/me", "/api/profile"):
                    profile = self.client.get(endpoint, headers=fresh_headers)
                    self.assertEqual(profile.status_code, 200, profile.text)
                    self.assertEqual(profile.json()["ui_theme"], "classic")
                    self.assertEqual(profile.json()["display_name"], "Алиса")
                    self.assertEqual(profile.json()["avatar_key"], "mage")
                response = self.client.put("/api/profile", headers=fresh_headers, json={"ui_theme": "modern"})
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(self.client.get("/api/profile", headers=fresh_headers).json()["ui_theme"], "modern")

    def test_partial_updates_and_accounts_are_independent(self):
        headers = self.headers()
        self.assertEqual(self.client.put("/api/profile", headers=headers, json={"ui_theme": "classic"}).status_code, 200)
        for payload in ({"display_name": "Алиса новая"}, {"avatar_key": "fox"}, {}):
            response = self.client.put("/api/profile", headers=headers, json=payload)
            self.assertEqual(response.status_code, 200, response.text)
        alice = self.client.get("/api/profile", headers=headers).json()
        self.assertEqual((alice["ui_theme"], alice["display_name"], alice["avatar_key"]),
                         ("classic", "Алиса новая", "fox"))
        boris = self.client.get("/api/profile", headers=self.headers("boris")).json()
        self.assertEqual((boris["ui_theme"], boris["display_name"], boris["avatar_key"]),
                         ("modern", "Борис", "robot"))

    def test_invalid_preferences_cannot_change_other_profile_fields(self):
        headers = self.headers()
        for invalid in ("dark", "CLASSIC", "", None, 1, ["classic"]):
            with self.subTest(invalid=invalid):
                response = self.client.put(
                    "/api/profile", headers=headers,
                    json={"ui_theme": invalid, "display_name": "Не сохранять"},
                )
                self.assertEqual(response.status_code, 422, response.text)
        profile = self.client.get("/api/profile", headers=headers).json()
        self.assertEqual((profile["ui_theme"], profile["display_name"]), ("modern", "Алиса"))

    def test_anonymous_request_cannot_change_preference(self):
        response = self.client.put("/api/profile", json={"ui_theme": "classic"})
        self.assertEqual(response.status_code, 401)
        with main.get_db() as conn:
            self.assertEqual(conn.execute("SELECT ui_theme FROM users WHERE id=1").fetchone()[0], "modern")


if __name__ == "__main__":
    unittest.main()
