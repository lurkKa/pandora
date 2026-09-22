import os
import sqlite3
import tempfile
import unittest


os.environ.setdefault("PANDORA_SKIP_STARTUP", "1")

import main  # noqa: E402


class HeistProgressTests(unittest.TestCase):
    def setUp(self):
        self._old_database = main.DATABASE
        self._tempdir = tempfile.TemporaryDirectory()
        main.DATABASE = os.path.join(self._tempdir.name, "heist-test.db")
        with main.get_db() as conn:
            conn.executescript(
                """
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY,
                    username TEXT NOT NULL,
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
                CREATE TABLE heist_round_completions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    round_number INTEGER NOT NULL,
                    rating TEXT NOT NULL DEFAULT 'C',
                    xp_earned INTEGER NOT NULL DEFAULT 0,
                    completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, round_number)
                );
                INSERT INTO users (id, username) VALUES (1, 'agent');
                """
            )
            conn.commit()
        self.user = {"id": 1, "username": "agent", "role": "student"}

    def tearDown(self):
        main.DATABASE = self._old_database
        self._tempdir.cleanup()

    def test_rewards_are_sequential_increasing_and_one_shot(self):
        with self.assertRaises(main.HTTPException) as skipped:
            main.heist_complete(
                main.HeistCompletionRequest(round_number=2, rating="S"),
                self.user,
            )
        self.assertEqual(skipped.exception.status_code, 409)

        first = main.heist_complete(
            main.HeistCompletionRequest(round_number=1, rating="S"),
            self.user,
        )
        replay = main.heist_complete(
            main.HeistCompletionRequest(round_number=1, rating="S"),
            self.user,
        )
        second = main.heist_complete(
            main.HeistCompletionRequest(round_number=2, rating="A"),
            self.user,
        )

        self.assertEqual(first["awarded"], main.HEIST_ROUND_XP[0])
        self.assertEqual(replay["awarded"], 0)
        self.assertTrue(replay["already_completed"])
        self.assertGreater(second["awarded"], first["awarded"])
        self.assertEqual(second["max_round_completed"], 2)
        with main.get_db() as conn:
            xp = conn.execute("SELECT xp FROM users WHERE id = 1").fetchone()["xp"]
            claims = conn.execute(
                "SELECT COUNT(*) AS count FROM heist_round_completions WHERE user_id = 1"
            ).fetchone()["count"]
            heist_xp = conn.execute(
                "SELECT SUM(xp_change) AS value FROM xp_log WHERE reason LIKE 'bank_heist:%'"
            ).fetchone()["value"]
        expected_heist_xp = main.HEIST_ROUND_XP[0] + main.HEIST_ROUND_XP[1]
        self.assertEqual(heist_xp, expected_heist_xp)
        self.assertGreaterEqual(xp, expected_heist_xp)  # rank milestones may add a bonus
        self.assertEqual(claims, 2)

    def test_status_exposes_reward_ladder(self):
        status = main.heist_status(self.user)
        self.assertEqual(status["max_round_completed"], 0)
        self.assertEqual(status["next_round"], 1)
        self.assertEqual(status["round_rewards"], list(main.HEIST_ROUND_XP))
        self.assertTrue(all(a < b for a, b in zip(main.HEIST_ROUND_XP, main.HEIST_ROUND_XP[1:])))


if __name__ == "__main__":
    unittest.main()
