#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="/root/stockbacking/backing"
SYSTEMD_DIR="/etc/systemd/system"

# 构建前端生产产物以供 preview 模式服务
if [ -d "${ROOT_DIR}/frontend" ]; then
    echo "Building frontend production assets..."
    (cd "${ROOT_DIR}/frontend" && npm ci && npm run build)
fi

cp "${ROOT_DIR}/deploy/systemd/stockbacking-backend.service" "${SYSTEMD_DIR}/stockbacking-backend.service"
cp "${ROOT_DIR}/deploy/systemd/stockbacking-frontend.service" "${SYSTEMD_DIR}/stockbacking-frontend.service"
if [ -f "${ROOT_DIR}/deploy/systemd/stockbacking-maintenance.service" ]; then
    cp "${ROOT_DIR}/deploy/systemd/stockbacking-maintenance.service" "${SYSTEMD_DIR}/stockbacking-maintenance.service"
    cp "${ROOT_DIR}/deploy/systemd/stockbacking-maintenance.timer" "${SYSTEMD_DIR}/stockbacking-maintenance.timer"
fi

systemctl daemon-reload
systemctl enable stockbacking-backend.service stockbacking-frontend.service
if [ -f "${SYSTEMD_DIR}/stockbacking-maintenance.timer" ]; then
    systemctl enable --now stockbacking-maintenance.timer
fi
systemctl restart stockbacking-backend.service stockbacking-frontend.service

systemctl --no-pager --full status stockbacking-backend.service
systemctl --no-pager --full status stockbacking-frontend.service
