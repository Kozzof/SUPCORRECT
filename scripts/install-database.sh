#!/usr/bin/env bash
set -euo pipefail

role=${1:?Usage: install-database.sh {primary|replica}}
if [[ ${EUID} -ne 0 ]]; then
    echo "Run as root on the MariaDB host." >&2
    exit 1
fi

project_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
case "$role" in
  primary) source_conf="$project_root/infra/mariadb/primary.cnf" ;;
  replica) source_conf="$project_root/infra/mariadb/replica.cnf" ;;
  *) echo "Unknown database role: $role" >&2; exit 2 ;;
esac

apt-get update
apt-get install -y mariadb-server mariadb-client
install -m 0644 "$source_conf" /etc/mysql/mariadb.conf.d/60-supcorrect.cnf
systemctl enable mariadb
systemctl restart mariadb
mysqladmin ping
echo "MariaDB installed and configured as: $role"
