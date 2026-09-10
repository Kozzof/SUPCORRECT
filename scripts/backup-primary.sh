#!/usr/bin/env bash
set -euo pipefail

: "${PRIMARY_HOST:?Set PRIMARY_HOST.}"
: "${MYSQL_BACKUP_USER:?Set MYSQL_BACKUP_USER.}"
: "${MYSQL_BACKUP_PASSWORD:?Set MYSQL_BACKUP_PASSWORD.}"
: "${BACKUP_FILE:?Set BACKUP_FILE to an explicit destination file.}"

umask 077
temporary_backup=$(mktemp "${BACKUP_FILE}.tmp.XXXXXX")
trap 'rm -f "$temporary_backup"' EXIT
mariadb-dump --host="$PRIMARY_HOST" --user="$MYSQL_BACKUP_USER" --password="$MYSQL_BACKUP_PASSWORD" \
  --single-transaction --master-data=2 --gtid --databases supcorrect > "$temporary_backup"
grep -q "gtid_slave_pos" "$temporary_backup"
mv "$temporary_backup" "$BACKUP_FILE"
trap - EXIT
echo "Consistent SUPCORRECT backup created: $BACKUP_FILE"
