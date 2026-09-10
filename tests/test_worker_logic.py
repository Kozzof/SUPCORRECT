import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.supcorrect import worker
from app.supcorrect.worker import GraderError, grade_submission


class WorkerLogicTest(unittest.TestCase):
    def setUp(self):
        self.references = Path(__file__).resolve().parent / "reference"
        self.submission = {
            "id": 1,
            "user_id": 1,
            "exercise_id": 1,
            "language": "python",
            "source_code": "print('unused in this unit test')",
        }

    def test_score_compares_candidate_to_reference_for_each_case(self):
        expected = {
            ("1", "2"): "3",
            ("-4", "9"): "5",
            ("0", "0"): "0",
            ("123", "456"): "579",
        }

        def fake_prepare(language, source_path, sandbox_dir, error_code):
            return ["candidate"] if source_path.name.startswith("submission") else ["reference"]

        def fake_run(command, args, workdir):
            if command[0] == "reference":
                return True, expected[tuple(args)]
            if tuple(args) == ("-4", "9"):
                return True, "incorrect"
            return True, expected[tuple(args)]

        with tempfile.TemporaryDirectory() as work_root:
            with patch.dict("os.environ", {"GRADER_WORKDIR": work_root}):
                with patch("app.supcorrect.worker.prepare_program", side_effect=fake_prepare):
                    with patch("app.supcorrect.worker.run_case", side_effect=fake_run):
                        score, result = grade_submission(self.submission, self.references)

        self.assertEqual(result, "ok")
        self.assertEqual(score, 75)

    def test_missing_reference_is_rejected(self):
        submission = dict(self.submission, exercise_id=99)
        with self.assertRaises(GraderError) as error:
            grade_submission(submission, self.references)
        self.assertEqual(str(error.exception), "reference_missing")

    def test_bubblewrap_mounts_are_complete_triplets(self):
        with patch("app.supcorrect.worker.os.name", "posix"):
            with patch("app.supcorrect.worker.shutil.which", return_value="/usr/bin/bwrap"):
                with patch("app.supcorrect.worker.Path.exists", return_value=True):
                    command = worker.sandboxed_command(["/usr/bin/python3", "/tmp/work/submission.py"], Path("/tmp/work"))

        for index, token in enumerate(command):
            if token == "--ro-bind":
                self.assertNotEqual(command[index + 1], "--ro-bind")
                self.assertNotEqual(command[index + 2], "--ro-bind")
        self.assertIn(["--ro-bind", "/usr", "/usr"], [command[index:index + 3] for index in range(len(command) - 2)])
        self.assertIn(["--ro-bind", "/lib", "/lib"], [command[index:index + 3] for index in range(len(command) - 2)])
        self.assertIn("--unshare-pid", command)

    def test_system_launch_error_is_technical_error(self):
        with tempfile.TemporaryDirectory() as work_root:
            with patch.dict("os.environ", {"GRADER_WORKDIR": work_root}):
                with patch("app.supcorrect.worker.prepare_program", return_value=["program"]):
                    with patch("app.supcorrect.worker.run_case", side_effect=OSError("launch failed")):
                        with self.assertRaises(GraderError) as error:
                            grade_submission(self.submission, self.references)
        self.assertEqual(str(error.exception), "execution_error")

    def test_student_stderr_does_not_trigger_sandbox_error(self):
        with patch("app.supcorrect.worker.sandboxed_command", return_value=["program"]):
            with patch("app.supcorrect.worker.execute_limited", return_value=(0, "ok\n", "bwrap: student text", False)):
                success, output = worker.run_case(["program"], [], Path("."))
        self.assertTrue(success)
        self.assertEqual(output, "ok")


if __name__ == "__main__":
    unittest.main()
