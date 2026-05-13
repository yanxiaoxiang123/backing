#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="/root/stockbacking/backing"
SYSTEMD_DIR="/etc/systemd/system"

cp "${ROOT_DIR}/deploy/systemd/stockbacking-backend.service" "${SYSTEMD_DIR}/stockbacking-backend.service"
cp "${ROOT_DIR}/deploy/systemd/stockbacking-frontend.service" "${SYSTEMD_DIR}/stockbacking-frontend.service"

systemctl daemon-reload
systemctl enable stockbacking-backend.service stockbacking-frontend.service
systemctl restart stockbacking-backend.service stockbacking-frontend.service

systemctl --no-pager --full status stockbacking-backend.service
systemctl --no-pager --full status stockbacking-frontend.service
