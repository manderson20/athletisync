#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="/home/itadmin/athletisync"
SERVICE_SRC="$REPO_DIR/deploy/systemd/athletisync.service"
NGINX_SRC="$REPO_DIR/deploy/nginx/athletisync.conf"

if [[ ! -f "$SERVICE_SRC" ]]; then
    echo "Missing $SERVICE_SRC" >&2
    exit 1
fi

if [[ ! -f "$NGINX_SRC" ]]; then
    echo "Missing $NGINX_SRC" >&2
    exit 1
fi

apt update
apt install -y nginx

cp "$SERVICE_SRC" /etc/systemd/system/athletisync.service
cp "$NGINX_SRC" /etc/nginx/sites-available/athletisync
ln -sf /etc/nginx/sites-available/athletisync /etc/nginx/sites-enabled/athletisync
rm -f /etc/nginx/sites-enabled/default

systemctl daemon-reload
systemctl enable --now athletisync
nginx -t
systemctl enable --now nginx
systemctl reload nginx

echo "AthletiSync should now be available at http://$(hostname -I | awk '{print $1}')/login"
