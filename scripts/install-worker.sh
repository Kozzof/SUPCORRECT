#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
    echo "Run as root on the dedicated worker host." >&2
    exit 1
fi

project_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

apt-get update
apt-get install -y bubblewrap build-essential util-linux python3 python3-venv python3-pip
id -u grader >/dev/null 2>&1 || useradd --system --home /nonexistent --shell /usr/sbin/nologin grader
install -d -o grader -g grader -m 0700 /var/lib/supcorrect/work /var/lib/supcorrect/instance
install -d -m 0755 /opt/supcorrect /etc/supcorrect
cp -a "$project_root/app" "$project_root/tests" /opt/supcorrect/
python3 -m venv /opt/supcorrect/venv
/opt/supcorrect/venv/bin/pip install --no-cache-dir -r "$project_root/requirements.txt"
install -m 0644 "$project_root/infra/systemd/supcorrect-worker.service" /etc/systemd/system/supcorrect-worker.service
install -m 0640 -o root -g grader "$project_root/infra/env/worker.env.example" /etc/supcorrect/app.env

systemctl daemon-reload
systemctl enable supcorrect-worker
echo "Edit /etc/supcorrect/app.env with the worker MariaDB URL, then start supcorrect-worker."
