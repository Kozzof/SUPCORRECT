import tempfile
import unittest
import os
from pathlib import Path
from unittest.mock import patch

from app.supcorrect import create_app
from app.supcorrect.worker import GraderError, now, process_once, reclaim_interrupted_jobs


class WebFlowTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        database_url = f"sqlite:///{Path(self.directory.name) / 'test.db'}"
        self.app = create_app({"TESTING": True, "DATABASE_URL": database_url, "SECRET_KEY": "test-secret", "SESSION_COOKIE_SECURE": False, "JOB_MAX_ATTEMPTS": 3})
        schema = Path(__file__).resolve().parents[1] / "infra" / "database" / "schema_sqlite.sql"
        database = self.app.extensions["db"]
        with database.transaction() as connection:
            database.script(connection, schema.read_text(encoding="utf-8"))
            database.execute(connection, "INSERT INTO courses (id, code, label) VALUES (1, 'INIT', 'Initiation')")
            database.execute(connection, "INSERT INTO exercises (id, course_id, number, title) VALUES (1, 1, 1, 'Somme')")
            database.execute(connection, "INSERT INTO exercise_languages (exercise_id, language) VALUES (1, 'python')")
        self.client = self.app.test_client()

    def tearDown(self):
        self.directory.cleanup()

    def token(self):
        with self.client.session_transaction() as session:
            return session["csrf_token"]

    def test_register_login_and_queue_submission(self):
        self.client.get("/register")
        response = self.client.post("/register", data={"csrf_token": self.token(), "email": "student@example.test", "password": "long-enough-password"}, follow_redirects=True)
        self.assertIn(b"Compte cree", response.data)

        self.client.get("/login")
        response = self.client.post("/login", data={"csrf_token": self.token(), "email": "student@example.test", "password": "long-enough-password"}, follow_redirects=True)
        self.assertIn(b"Mes exercices", response.data)

        response = self.client.post("/submit", data={"csrf_token": self.token(), "exercise_id": "1", "language": "python", "source": (Path(__file__).resolve().parent / "fixtures" / "sum_correct.py", "sum.py")}, content_type="multipart/form-data", follow_redirects=True)
        self.assertIn(b"attente de correction", response.data)

        database = self.app.extensions["db"]
        with database.transaction() as connection:
            job = database.execute(connection, "SELECT status FROM jobs").fetchone()
        self.assertEqual(job["status"], "queued")

        with patch("app.supcorrect.worker.grade_submission", return_value=(75, "ok")):
            self.assertTrue(process_once(self.app))

        with database.transaction() as connection:
            submission = database.execute(connection, "SELECT status, score, source_code FROM submissions").fetchone()
            best = database.execute(connection, "SELECT score FROM best_submissions").fetchone()
        self.assertEqual(submission["status"], "graded")
        self.assertEqual(submission["score"], 75)
        self.assertIsNone(submission["source_code"])
        self.assertEqual(best["score"], 75)

        with database.transaction() as connection:
            submitted_at = now()
            cursor = database.execute(connection, "INSERT INTO submissions (user_id, exercise_id, language, original_filename, source_code, status, submitted_at) VALUES (1, 1, 'python', 'retry.py', 'print(0)', 'queued', ?)", (submitted_at,))
            retry_id = cursor.lastrowid
            database.execute(connection, "INSERT INTO jobs (submission_id, status, attempts, available_at) VALUES (?, 'queued', 0, ?)", (retry_id, submitted_at))
        with patch("app.supcorrect.worker.grade_submission", return_value=(40, "ok")):
            self.assertTrue(process_once(self.app))
        with database.transaction() as connection:
            best = database.execute(connection, "SELECT score FROM best_submissions").fetchone()
        self.assertEqual(best["score"], 75)

    def test_csrf_requires_a_non_empty_matching_token(self):
        response = self.client.post("/register", data={"email": "student@example.test", "password": "long-enough-password"})
        self.assertEqual(response.status_code, 400)

        self.client.get("/register")
        response = self.client.post("/register", data={"csrf_token": "invalid", "email": "student@example.test", "password": "long-enough-password"})
        self.assertEqual(response.status_code, 400)

        response = self.client.post("/register", data={"csrf_token": self.token(), "email": "student@example.test", "password": "long-enough-password"}, follow_redirects=True)
        self.assertIn(b"Compte cree", response.data)

    def test_production_session_cookie_is_secure_by_default(self):
        with patch.dict(os.environ, {"FLASK_SESSION_COOKIE_SECURE": "true"}):
            production_app = create_app({"DATABASE_URL": "mysql://user:password@db.example/supcorrect"})
        self.assertTrue(production_app.config["SESSION_COOKIE_SECURE"])

    def test_health_returns_unavailable_when_database_cannot_be_reached(self):
        unavailable_app = create_app({"TESTING": True, "DATABASE_URL": "mysql://user:password@127.0.0.1:1/supcorrect"})
        response = unavailable_app.test_client().get("/health")
        self.assertEqual(response.status_code, 503)

    def test_technical_error_preserves_source_and_requeues(self):
        self.client.get("/register")
        self.client.post("/register", data={"csrf_token": self.token(), "email": "student@example.test", "password": "long-enough-password"})
        self.client.get("/login")
        self.client.post("/login", data={"csrf_token": self.token(), "email": "student@example.test", "password": "long-enough-password"})
        self.client.post("/submit", data={"csrf_token": self.token(), "exercise_id": "1", "language": "python", "source": (Path(__file__).resolve().parent / "fixtures" / "sum_correct.py", "sum.py")}, content_type="multipart/form-data")

        with patch("app.supcorrect.worker.grade_submission", side_effect=GraderError("sandbox_unavailable")):
            self.assertTrue(process_once(self.app))

        database = self.app.extensions["db"]
        with database.transaction() as connection:
            submission = database.execute(connection, "SELECT status, score, source_code FROM submissions").fetchone()
            job = database.execute(connection, "SELECT status, error_code FROM jobs").fetchone()
        self.assertEqual(submission["status"], "queued")
        self.assertIsNone(submission["score"])
        self.assertIsNotNone(submission["source_code"])
        self.assertEqual(job["status"], "queued")
        self.assertEqual(job["error_code"], "sandbox_unavailable")

    def test_internal_worker_error_preserves_source_and_requeues(self):
        database = self.app.extensions["db"]
        with database.transaction() as connection:
            database.execute(connection, "INSERT INTO users (id, email, password_hash, created_at) VALUES (1, 'student@example.test', 'hash', ?)", (now(),))
            cursor = database.execute(connection, "INSERT INTO submissions (user_id, exercise_id, language, original_filename, source_code, status, submitted_at) VALUES (1, 1, 'python', 'broken.py', 'print(0)', 'queued', ?)", (now(),))
            database.execute(connection, "INSERT INTO jobs (submission_id, status, attempts, available_at) VALUES (?, 'queued', 0, ?)", (cursor.lastrowid, now()))

        with patch("app.supcorrect.worker.grade_submission", side_effect=RuntimeError("database lost")):
            self.assertTrue(process_once(self.app))

        with database.transaction() as connection:
            submission = database.execute(connection, "SELECT status, score, source_code FROM submissions").fetchone()
            job = database.execute(connection, "SELECT status, error_code FROM jobs").fetchone()
        self.assertEqual(submission["status"], "queued")
        self.assertIsNone(submission["score"])
        self.assertEqual(submission["source_code"], "print(0)")
        self.assertEqual(job["status"], "queued")
        self.assertEqual(job["error_code"], "worker_error")

    def test_stale_running_job_is_requeued(self):
        database = self.app.extensions["db"]
        with database.transaction() as connection:
            database.execute(connection, "INSERT INTO users (id, email, password_hash, created_at) VALUES (1, 'student@example.test', 'hash', ?)", (now(),))
            cursor = database.execute(connection, "INSERT INTO submissions (user_id, exercise_id, language, original_filename, source_code, status, submitted_at) VALUES (1, 1, 'python', 'retry.py', 'print(0)', 'running', ?)", (now(),))
            database.execute(connection, "INSERT INTO jobs (submission_id, status, attempts, available_at, locked_at) VALUES (?, 'running', 1, ?, '2000-01-01 00:00:00')", (cursor.lastrowid, now()))
        reclaim_interrupted_jobs(database, max_attempts=3, lock_timeout_seconds=1)
        with database.transaction() as connection:
            submission = database.execute(connection, "SELECT status FROM submissions").fetchone()
            job = database.execute(connection, "SELECT status, error_code FROM jobs").fetchone()
        self.assertEqual(submission["status"], "queued")
        self.assertEqual(job["status"], "queued")
        self.assertEqual(job["error_code"], "lock_timeout_requeued")

    def test_dashboard_prefers_newest_submission_when_timestamps_match(self):
        database = self.app.extensions["db"]
        with database.transaction() as connection:
            database.execute(connection, "INSERT INTO users (id, email, password_hash, created_at) VALUES (1, 'student@example.test', 'hash', ?)", (now(),))
            timestamp = now()
            database.execute(connection, "INSERT INTO submissions (user_id, exercise_id, language, original_filename, source_code, status, score, submitted_at) VALUES (1, 1, 'python', 'old.py', NULL, 'graded', 100, ?)", (timestamp,))
            database.execute(connection, "INSERT INTO submissions (user_id, exercise_id, language, original_filename, source_code, status, submitted_at) VALUES (1, 1, 'python', 'new.py', 'print(0)', 'queued', ?)", (timestamp,))
        with self.client.session_transaction() as session:
            session["user_id"] = 1
        response = self.client.get("/")
        self.assertIn("en attente de correction", response.get_data(as_text=True))

if __name__ == "__main__":
    unittest.main()
