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

## Backups

- Back up `athletisync.db`
- Back up `.env`
- Back up exported Google service-account credentials from secure storage

## Lightweight Service

For a non-container deployment, run with `uvicorn` behind `systemd` and a reverse proxy.
