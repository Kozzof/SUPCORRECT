#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
    echo "Run as root on web-1 or web-2." >&2
    exit 1
fi

project_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

apt-get update
apt-get install -y apache2 python3 python3-venv python3-pip
id -u supcorrect-web >/dev/null 2>&1 || useradd --system --home /nonexistent --shell /usr/sbin/nologin supcorrect-web
install -d -m 0755 /opt/supcorrect /etc/supcorrect /var/lib/supcorrect
install -d -o supcorrect-web -g supcorrect-web -m 0750 /var/lib/supcorrect/instance
cp -a "$project_root/app" /opt/supcorrect/
python3 -m venv /opt/supcorrect/venv
/opt/supcorrect/venv/bin/pip install --no-cache-dir -r "$project_root/requirements.txt"

install -m 0644 "$project_root/infra/apache/supcorrect.conf" /etc/apache2/sites-available/supcorrect.conf
install -m 0644 "$project_root/infra/apache/hardening.conf" /etc/apache2/conf-available/supcorrect-hardening.conf
install -m 0644 "$project_root/infra/apache/supcorrect-ports.conf" /etc/apache2/conf-available/supcorrect-ports.conf
install -m 0644 "$project_root/infra/systemd/supcorrect-web.service" /etc/systemd/system/supcorrect-web.service
install -m 0640 -o root -g supcorrect-web "$project_root/infra/env/app.env.example" /etc/supcorrect/app.env

a2enmod proxy proxy_http headers reqtimeout
a2enconf supcorrect-hardening
a2enconf supcorrect-ports
a2dissite 000-default
a2ensite supcorrect
systemctl daemon-reload
apache2ctl configtest
systemctl enable apache2 supcorrect-web
systemctl restart apache2
systemctl restart supcorrect-web

echo "Edit /etc/supcorrect/app.env with the real secret and MariaDB URL, then restart supcorrect-web."
