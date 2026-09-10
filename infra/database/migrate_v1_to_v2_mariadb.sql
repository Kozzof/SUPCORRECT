-- Run once only on a SUPCORRECT V1 database, after a backup.
USE supcorrect;

ALTER TABLE submissions
    MODIFY status ENUM('queued', 'running', 'graded', 'technical_error') NOT NULL;

ALTER TABLE jobs
    MODIFY status ENUM('queued', 'running', 'completed', 'failed') NOT NULL;

ALTER TABLE jobs
    ADD COLUMN lock_token CHAR(32) NULL AFTER locked_at;
