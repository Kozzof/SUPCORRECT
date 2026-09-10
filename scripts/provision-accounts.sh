#!/usr/bin/env bash
set -euo pipefail

: "${MYSQL_ROOT_PASSWORD:?Set MYSQL_ROOT_PASSWORD in the shell.}"
: "${APP_PASSWORD:?Set APP_PASSWORD in the shell.}"
: "${WORKER_PASSWORD:?Set WORKER_PASSWORD in the shell.}"
: "${REPLICATION_PASSWORD:?Set REPLICATION_PASSWORD in the shell.}"
: "${BACKUP_PASSWORD:?Set BACKUP_PASSWORD in the shell.}"

db_client_cidr=${DB_CLIENT_CIDR:-10.0.0.%}
mysql -u root "-p${MYSQL_ROOT_PASSWORD}" <<SQL
CREATE USER IF NOT EXISTS 'supcorrect_app'@'${db_client_cidr}' IDENTIFIED BY '${APP_PASSWORD}';
CREATE USER IF NOT EXISTS 'supcorrect_worker'@'${db_client_cidr}' IDENTIFIED BY '${WORKER_PASSWORD}';
CREATE USER IF NOT EXISTS 'supcorrect_repl'@'${db_client_cidr}' IDENTIFIED BY '${REPLICATION_PASSWORD}';
CREATE USER IF NOT EXISTS 'supcorrect_backup'@'${db_client_cidr}' IDENTIFIED BY '${BACKUP_PASSWORD}';
GRANT SELECT, INSERT, UPDATE, DELETE ON supcorrect.* TO 'supcorrect_app'@'${db_client_cidr}';
GRANT SELECT, UPDATE ON supcorrect.submissions TO 'supcorrect_worker'@'${db_client_cidr}';
GRANT SELECT, UPDATE ON supcorrect.jobs TO 'supcorrect_worker'@'${db_client_cidr}';
GRANT SELECT, INSERT, UPDATE, DELETE ON supcorrect.best_submissions TO 'supcorrect_worker'@'${db_client_cidr}';
GRANT SELECT ON supcorrect.exercises TO 'supcorrect_worker'@'${db_client_cidr}';
GRANT REPLICATION SLAVE ON *.* TO 'supcorrect_repl'@'${db_client_cidr}';
GRANT REPLICATION CLIENT ON *.* TO 'supcorrect_backup'@'${db_client_cidr}';
GRANT SELECT, SHOW VIEW, TRIGGER, LOCK TABLES ON supcorrect.* TO 'supcorrect_backup'@'${db_client_cidr}';
FLUSH PRIVILEGES;
SQL

echo "SUPCORRECT application, replication, and backup accounts created for ${db_client_cidr}."
