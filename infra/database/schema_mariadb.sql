CREATE DATABASE IF NOT EXISTS supcorrect CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE supcorrect;

CREATE TABLE IF NOT EXISTS users (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(254) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at DATETIME NOT NULL
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS courses (
    id BIGINT UNSIGNED PRIMARY KEY,
    code VARCHAR(32) NOT NULL UNIQUE,
    label VARCHAR(128) NOT NULL
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS exercises (
    id BIGINT UNSIGNED PRIMARY KEY,
    course_id BIGINT UNSIGNED NOT NULL,
    number INT UNSIGNED NOT NULL,
    title VARCHAR(128) NOT NULL,
    UNIQUE KEY uq_course_number (course_id, number),
    CONSTRAINT fk_exercise_course FOREIGN KEY (course_id) REFERENCES courses(id)
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS exercise_languages (
    exercise_id BIGINT UNSIGNED NOT NULL,
    language ENUM('c', 'python') NOT NULL,
    PRIMARY KEY (exercise_id, language),
    CONSTRAINT fk_language_exercise FOREIGN KEY (exercise_id) REFERENCES exercises(id)
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS submissions (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT UNSIGNED NOT NULL,
    exercise_id BIGINT UNSIGNED NOT NULL,
    language ENUM('c', 'python') NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    source_code MEDIUMTEXT NULL,
    status ENUM('queued', 'running', 'graded', 'technical_error') NOT NULL,
    score TINYINT UNSIGNED NULL,
    submitted_at DATETIME NOT NULL,
    graded_at DATETIME NULL,
    CONSTRAINT fk_submission_user FOREIGN KEY (user_id) REFERENCES users(id),
    CONSTRAINT fk_submission_exercise FOREIGN KEY (exercise_id) REFERENCES exercises(id)
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS jobs (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    submission_id BIGINT UNSIGNED NOT NULL UNIQUE,
    status ENUM('queued', 'running', 'completed', 'failed') NOT NULL,
    attempts INT UNSIGNED NOT NULL DEFAULT 0,
    available_at DATETIME NOT NULL,
    locked_at DATETIME NULL,
    lock_token CHAR(32) NULL,
    completed_at DATETIME NULL,
    error_code VARCHAR(64) NULL,
    KEY idx_jobs_claim (status, available_at, id),
    CONSTRAINT fk_job_submission FOREIGN KEY (submission_id) REFERENCES submissions(id)
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS best_submissions (
    user_id BIGINT UNSIGNED NOT NULL,
    exercise_id BIGINT UNSIGNED NOT NULL,
    submission_id BIGINT UNSIGNED NOT NULL,
    score TINYINT UNSIGNED NOT NULL,
    graded_at DATETIME NOT NULL,
    PRIMARY KEY (user_id, exercise_id),
    CONSTRAINT fk_best_user FOREIGN KEY (user_id) REFERENCES users(id),
    CONSTRAINT fk_best_exercise FOREIGN KEY (exercise_id) REFERENCES exercises(id),
    CONSTRAINT fk_best_submission FOREIGN KEY (submission_id) REFERENCES submissions(id)
) ENGINE=InnoDB;
