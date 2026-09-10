#!/usr/bin/env bash
set -euo pipefail

: "${MYSQL_ROOT_PASSWORD:?Set MYSQL_ROOT_PASSWORD in the shell.}"
: "${BACKUP_FILE:?Set BACKUP_FILE to the backup received from the primary.}"

test -r "$BACKUP_FILE"
grep -q "gtid_slave_pos" "$BACKUP_FILE" || { echo "Backup does not contain GTID state." >&2; exit 1; }
mysql -u root "-p${MYSQL_ROOT_PASSWORD}" -e "STOP SLAVE;"
mysql -u root "-p${MYSQL_ROOT_PASSWORD}" < "$BACKUP_FILE"
echo "Backup and GTID state restored on replica. Run provision-accounts.sh, then configure-replica.sh."
