#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
    echo "Run as root on the HAProxy host." >&2
    exit 1
fi

project_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
apt-get update
apt-get install -y haproxy
install -d -m 0750 /etc/haproxy/certs
install -m 0644 "$project_root/infra/haproxy/haproxy.cfg" /etc/haproxy/haproxy.cfg
echo "Install the certificate and private key concatenated in /etc/haproxy/certs/supcorrect.pem (root:haproxy, 0640)."
echo "Then validate with: haproxy -c -f /etc/haproxy/haproxy.cfg"
