#!/usr/bin/env bash
set -euo pipefail
# Run with sudo after the private configuration and healthy services exist.
root=/home/yanxx/backing
touch "$root/ops/sync.log" "$root/ops/backup.log"
chown yanxx:yanxx "$root/ops/sync.log" "$root/ops/backup.log"
chmod 600 "$root/ops/sync.log" "$root/ops/backup.log"
for unit in backing-sync.service backing-sync.timer backing-backup.service backing-backup.timer; do
  install -m 644 "$root/source/deploy/production/$unit" "/etc/systemd/system/$unit"
done
systemctl daemon-reload
install -m 644 "$root/source/deploy/production/logrotate.conf" /etc/logrotate.d/backing
systemd-analyze calendar 'Mon..Fri *-*-* 16:30:00 Asia/Shanghai'
systemd-analyze calendar '*-*-* 03:30:00 Asia/Shanghai'
systemctl enable --now backing-sync.timer backing-backup.timer
