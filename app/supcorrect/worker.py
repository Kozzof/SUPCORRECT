import argparse
import json
import os
import shutil
import subprocess
import tempfile
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import create_app

class GraderError(Exception):
    pass


MAX_OUTPUT_BYTES = 64 * 1024
TECHNICAL_ERRORS = {
    "compile_timeout",
    "reference_error",
    "reference_execution_error",
    "reference_missing",
    "sandbox_unavailable",
    "unsupported_host",
    "execution_error",
    "worker_error",
}


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def execute_limited(command, workdir, timeout):
    """Execute without a shell, cap captured output, and kill all descendants on timeout."""
    with tempfile.TemporaryFile() as stdout_file, tempfile.TemporaryFile() as stderr_file:
        process = subprocess.Popen(
            command,
            cwd=workdir,
            stdin=subprocess.DEVNULL,
            stdout=stdout_file,
            stderr=stderr_file,
            start_new_session=os.name == "posix",
            env={"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"},
        )
        timed_out = False
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            if os.name == "posix":
                os.killpg(process.pid, 9)
            else:
                process.kill()
            process.wait()
        stdout_file.seek(0)
        stderr_file.seek(0)
        stdout = stdout_file.read(MAX_OUTPUT_BYTES + 1).decode("utf-8", errors="replace")
        stderr = stderr_file.read(MAX_OUTPUT_BYTES + 1).decode("utf-8", errors="replace")
    return process.returncode, stdout, stderr, timed_out


def reclaim_interrupted_jobs(database, max_attempts, lock_timeout_seconds):
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=lock_timeout_seconds)).strftime("%Y-%m-%d %H:%M:%S")
    with database.transaction(immediate=True) as connection:
        stale_jobs = database.execute(connection, "SELECT id, submission_id, attempts FROM jobs WHERE status = 'running' AND locked_at < ?", (cutoff,)).fetchall()
        for job in stale_jobs:
            if job["attempts"] >= max_attempts:
                database.execute(connection, "UPDATE jobs SET status = 'failed', completed_at = ?, lock_token = NULL, error_code = 'lock_timeout' WHERE id = ?", (now(), job["id"]))
                database.execute(connection, "UPDATE submissions SET status = 'technical_error' WHERE id = ?", (job["submission_id"],))
            else:
                database.execute(connection, "UPDATE jobs SET status = 'queued', available_at = ?, locked_at = NULL, lock_token = NULL, error_code = 'lock_timeout_requeued' WHERE id = ?", (now(), job["id"]))
                database.execute(connection, "UPDATE submissions SET status = 'queued' WHERE id = ?", (job["submission_id"],))


def claim_job(database):
    with database.transaction(immediate=True) as connection:
        if database.mysql:
            row = database.execute(connection, "SELECT id, submission_id, attempts FROM jobs WHERE status = 'queued' AND available_at <= ? ORDER BY id LIMIT 1 FOR UPDATE SKIP LOCKED", (now(),)).fetchone()
        else:
            row = database.execute(connection, "SELECT id, submission_id, attempts FROM jobs WHERE status = 'queued' AND available_at <= ? ORDER BY id LIMIT 1", (now(),)).fetchone()
        if not row:
            return None
        lock_token = uuid.uuid4().hex
        database.execute(connection, "UPDATE jobs SET status = 'running', attempts = attempts + 1, locked_at = ?, lock_token = ? WHERE id = ?", (now(), lock_token, row["id"]))
        database.execute(connection, "UPDATE submissions SET status = 'running' WHERE id = ?", (row["submission_id"],))
        claimed = dict(row)
        claimed["attempts"] += 1
        claimed["lock_token"] = lock_token
        return claimed


def load_submission(database, submission_id):
    with database.transaction() as connection:
        return database.execute(connection, "SELECT id, user_id, exercise_id, language, source_code FROM submissions WHERE id = ?", (submission_id,)).fetchone()


def run_case(command, args, workdir):
    command = sandboxed_command(command, workdir)
    returncode, stdout, _, timed_out = execute_limited(command + args, workdir, timeout=2)
    return not timed_out and returncode == 0, stdout.replace("\r\n", "\n").rstrip()


def sandboxed_command(command, workdir):
    """Run code through Bubblewrap with limits inherited from prlimit."""
    if os.name != "posix":
        raise GraderError("unsupported_host")
    bwrap = shutil.which("bwrap")
    prlimit = shutil.which("prlimit")
    if not bwrap or not prlimit:
        raise GraderError("sandbox_unavailable")
    mounts = []
    for directory in ("/usr", "/lib", "/lib64"):
        if Path(directory).exists():
            mounts.extend(["--ro-bind", directory, directory])
    mounts.extend(["--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp", "--bind", str(workdir), "/work", "--chdir", "/work"])
    rewritten = [str(value).replace(str(workdir), "/work") for value in command]
    # Bubblewrap has no --rlimit-* options.  prlimit applies kernel-enforced
    # limits before it execs bwrap, so both bwrap and the submitted process
    # receive them without unsafe preexec_fn calls from grading threads.
    limits = [
        prlimit,
        f"--as={128 * 1024 * 1024}",
        f"--fsize={MAX_OUTPUT_BYTES}",
        "--nproc=16",
        "--",
    ]
    return limits + [bwrap, "--die-with-parent", "--unshare-net", "--unshare-pid", "--new-session", "--clearenv", "--setenv", "PATH", "/usr/bin:/bin", "--setenv", "LANG", "C", "--setenv", "LC_ALL", "C"] + mounts + ["--"] + rewritten


def verify_sandbox(workdir):
    """Fail technically before compiling when this host cannot launch bwrap."""
    try:
        returncode, _, _, timed_out = execute_limited(
            sandboxed_command(["/usr/bin/true"], workdir), workdir, timeout=2
        )
    except OSError as error:
        raise GraderError("sandbox_unavailable") from error
    if timed_out or returncode != 0:
        raise GraderError("sandbox_unavailable")


def prepare_program(language, source_path, sandbox_dir, error_code):
    if language == "c":
        output_path = sandbox_dir / "program"
        returncode, _, _, timed_out = execute_limited(sandboxed_command(["/usr/bin/gcc", "-O2", "-Wall", "-Wextra", str(source_path), "-o", str(output_path)], sandbox_dir), sandbox_dir, timeout=5)
        if timed_out:
            raise GraderError("compile_timeout")
        if returncode != 0:
            raise GraderError(error_code)
        return [str(output_path)]
    if language == "python":
        return ["/usr/bin/python3", "-I", "-S", str(source_path)]
    raise GraderError("invalid_language")


def grade_submission(submission, reference_dir):
    references = Path(reference_dir)
    exercise_file = references / f"exercise_{submission['exercise_id']}.json"
    if not exercise_file.is_file():
        raise GraderError("reference_missing")
    cases = json.loads(exercise_file.read_text(encoding="utf-8"))["cases"]
    work_root = Path(os.environ.get("GRADER_WORKDIR", tempfile.gettempdir()))
    work_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="supcorrect-", dir=work_root) as directory:
        workdir = Path(directory)
        candidate_dir = workdir / "candidate"
        reference_dir = workdir / "reference"
        candidate_dir.mkdir()
        reference_dir.mkdir()
        # This has no student-controlled stderr.  It separates a broken
        # launcher/configuration from a genuine compiler diagnostic.
        verify_sandbox(candidate_dir)
        extension = ".c" if submission["language"] == "c" else ".py"
        source_path = candidate_dir / f"submission{extension}"
        source_path.write_text(submission["source_code"], encoding="utf-8")
        reference_source = references / f"exercise_{submission['exercise_id']}{extension}"
        if not reference_source.is_file():
            raise GraderError("reference_missing")
        copied_reference = reference_dir / f"reference{extension}"
        shutil.copyfile(reference_source, copied_reference)
        candidate_command = prepare_program(submission["language"], source_path, candidate_dir, "compile_error")
        reference_command = prepare_program(submission["language"], copied_reference, reference_dir, "reference_error")

        def evaluate(case):
            try:
                with ThreadPoolExecutor(max_workers=2) as executor:
                    candidate = executor.submit(run_case, candidate_command, case["args"], candidate_dir)
                    reference = executor.submit(run_case, reference_command, case["args"], reference_dir)
                    candidate_ok, candidate_output = candidate.result()
                    reference_ok, reference_output = reference.result()
            except subprocess.TimeoutExpired:
                return False
            except OSError as error:
                raise GraderError("execution_error") from error
            if not reference_ok:
                raise GraderError("reference_execution_error")
            return candidate_ok and reference_ok and candidate_output == reference_output

        passed = sum(evaluate(case) for case in cases)
        return round(passed * 100 / len(cases)), "ok"


def complete_job(database, job, submission, score, result):
    with database.transaction(immediate=True) as connection:
        graded_at = now()
        completed = database.execute(connection, "UPDATE jobs SET status = 'completed', completed_at = ?, lock_token = NULL, error_code = ? WHERE id = ? AND status = 'running' AND lock_token = ?", (graded_at, None if result == "ok" else result, job["id"], job["lock_token"]))
        if completed.rowcount != 1:
            return False
        database.execute(connection, "UPDATE submissions SET status = 'graded', score = ?, graded_at = ?, source_code = NULL WHERE id = ?", (score, graded_at, submission["id"]))
        current = database.execute(connection, "SELECT score FROM best_submissions WHERE user_id = ? AND exercise_id = ?", (submission["user_id"], submission["exercise_id"])).fetchone()
        if not current or score >= current["score"]:
            database.execute(connection, "DELETE FROM best_submissions WHERE user_id = ? AND exercise_id = ?", (submission["user_id"], submission["exercise_id"]))
            database.execute(connection, "INSERT INTO best_submissions (user_id, exercise_id, submission_id, score, graded_at) VALUES (?, ?, ?, ?, ?)", (submission["user_id"], submission["exercise_id"], submission["id"], score, graded_at))
    return True


def defer_technical_job(database, job, submission, error_code, max_attempts):
    with database.transaction(immediate=True) as connection:
        owned = database.execute(connection, "SELECT 1 FROM jobs WHERE id = ? AND status = 'running' AND lock_token = ?", (job["id"], job["lock_token"])).fetchone()
        if not owned:
            return False
        if job["attempts"] < max_attempts:
            retry_at = (datetime.now(timezone.utc) + timedelta(seconds=30)).strftime("%Y-%m-%d %H:%M:%S")
            database.execute(connection, "UPDATE jobs SET status = 'queued', available_at = ?, locked_at = NULL, lock_token = NULL, error_code = ? WHERE id = ?", (retry_at, error_code, job["id"]))
            database.execute(connection, "UPDATE submissions SET status = 'queued' WHERE id = ?", (submission["id"],))
        else:
            database.execute(connection, "UPDATE jobs SET status = 'failed', completed_at = ?, lock_token = NULL, error_code = ? WHERE id = ?", (now(), error_code, job["id"]))
            database.execute(connection, "UPDATE submissions SET status = 'technical_error' WHERE id = ?", (submission["id"],))
    return True


def process_once(app):
    database = app.extensions["db"]
    reclaim_interrupted_jobs(database, app.config["JOB_MAX_ATTEMPTS"], app.config["JOB_LOCK_TIMEOUT_SECONDS"])
    job = claim_job(database)
    if not job:
        return False
    submission = load_submission(database, job["submission_id"])
    try:
        score, result = grade_submission(submission, app.config["REFERENCE_DIR"])
    except GraderError as error:
        if str(error) in TECHNICAL_ERRORS:
            defer_technical_job(database, job, submission, str(error), app.config["JOB_MAX_ATTEMPTS"])
            return True
        score, result = 0, str(error)
    except Exception:
        defer_technical_job(database, job, submission, "worker_error", app.config["JOB_MAX_ATTEMPTS"])
        return True
    complete_job(database, job, submission, score, result)
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--poll-seconds", type=float, default=2)
    args = parser.parse_args()
    app = create_app()
    while True:
        processed = process_once(app)
        if args.once:
            break
        if not processed:
            time.sleep(args.poll_seconds)


if __name__ == "__main__":
    main()
