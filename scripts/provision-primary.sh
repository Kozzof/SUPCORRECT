#!/usr/bin/env bash
set -euo pipefail

: "${MYSQL_ROOT_PASSWORD:?Set MYSQL_ROOT_PASSWORD in the shell.}"
: "${APP_PASSWORD:?Set APP_PASSWORD in the shell.}"
: "${WORKER_PASSWORD:?Set WORKER_PASSWORD in the shell.}"
: "${REPLICATION_PASSWORD:?Set REPLICATION_PASSWORD in the shell.}"
: "${BACKUP_PASSWORD:?Set BACKUP_PASSWORD in the shell.}"

project_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
mysql=(mysql -u root "-p${MYSQL_ROOT_PASSWORD}")

"${mysql[@]}" < "$project_root/infra/database/schema_mariadb.sql"
"${mysql[@]}" < "$project_root/infra/database/seed_data.sql"
bash "$project_root/scripts/provision-accounts.sh"

echo "Primary schema and least-privilege accounts created."
