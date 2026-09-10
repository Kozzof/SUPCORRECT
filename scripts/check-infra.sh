#!/usr/bin/env bash
set -euo pipefail

role=${1:?Usage: check-infra.sh {web|worker|load-balancer}}

case "$role" in
  web)
    apache2ctl configtest
    systemd-analyze verify /etc/systemd/system/supcorrect-web.service
    ;;
  worker)
    command -v bwrap >/dev/null
    command -v gcc >/dev/null
    systemd-analyze verify /etc/systemd/system/supcorrect-worker.service
    ;;
  load-balancer)
    haproxy -c -f /etc/haproxy/haproxy.cfg
    ;;
  *)
    echo "Unknown role: $role" >&2
    exit 2
    ;;
esac

echo "Infrastructure check passed for role: $role"
