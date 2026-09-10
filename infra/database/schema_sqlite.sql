CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS courses (
    id INTEGER PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    label TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS exercises (
    id INTEGER PRIMARY KEY,
    course_id INTEGER NOT NULL REFERENCES courses(id),
    number INTEGER NOT NULL,
    title TEXT NOT NULL,
    UNIQUE(course_id, number)
);
CREATE TABLE IF NOT EXISTS exercise_languages (
    exercise_id INTEGER NOT NULL REFERENCES exercises(id),
    language TEXT NOT NULL CHECK(language IN ('c', 'python')),
    PRIMARY KEY (exercise_id, language)
);
CREATE TABLE IF NOT EXISTS submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    exercise_id INTEGER NOT NULL REFERENCES exercises(id),
    language TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    source_code TEXT,
    status TEXT NOT NULL CHECK(status IN ('queued', 'running', 'graded', 'technical_error')),
    score INTEGER CHECK(score BETWEEN 0 AND 100),
    submitted_at TEXT NOT NULL,
    graded_at TEXT
);
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    submission_id INTEGER NOT NULL UNIQUE REFERENCES submissions(id),
    status TEXT NOT NULL CHECK(status IN ('queued', 'running', 'completed', 'failed')),
    attempts INTEGER NOT NULL DEFAULT 0,
    available_at TEXT NOT NULL,
    locked_at TEXT,
    lock_token TEXT,
    completed_at TEXT,
    error_code TEXT
);
CREATE TABLE IF NOT EXISTS best_submissions (
    user_id INTEGER NOT NULL REFERENCES users(id),
    exercise_id INTEGER NOT NULL REFERENCES exercises(id),
    submission_id INTEGER NOT NULL REFERENCES submissions(id),
    score INTEGER NOT NULL CHECK(score BETWEEN 0 AND 100),
    graded_at TEXT NOT NULL,
    PRIMARY KEY (user_id, exercise_id)
);
CREATE INDEX IF NOT EXISTS idx_jobs_claim ON jobs(status, available_at, id);
