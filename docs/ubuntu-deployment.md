# Ubuntu Deployment Guide

## Docker Compose

```bash
cp .env.example .env
docker compose up --build -d
```

## Reverse Proxy

### Caddy

```caddy
athletisync.example.org {
    reverse_proxy 127.0.0.1:8000
}
```

### Nginx

```nginx
server {
    listen 80;
    server_name athletisync.example.org;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

## Systemd + Nginx On A Single Server

This repository includes ready-to-install examples:

- `deploy/systemd/athletisync.service`
- `deploy/nginx/athletisync.conf`

Install them on Ubuntu with:

```bash
sudo cp deploy/systemd/athletisync.service /etc/systemd/system/athletisync.service
sudo cp deploy/nginx/athletisync.conf /etc/nginx/sites-available/athletisync
sudo ln -sf /etc/nginx/sites-available/athletisync /etc/nginx/sites-enabled/athletisync
sudo rm -f /etc/nginx/sites-enabled/default
sudo systemctl daemon-reload
sudo systemctl enable --now athletisync
sudo nginx -t
sudo systemctl enable --now nginx
sudo systemctl reload nginx
```

The app process stays on `127.0.0.1:8000`, while `nginx` serves plain HTTP on port `80`.

## Backups

- Back up `athletisync.db`
- Back up `.env`
- Back up exported Google service-account credentials from secure storage

## Lightweight Service

For a non-container deployment, run with `uvicorn` behind `systemd` and a reverse proxy.
