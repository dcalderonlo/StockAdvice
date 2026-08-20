# Render Deployment Guide

## Prerequisites

- Render account
- GitHub repository connected to Render
- PostgreSQL managed database provisioned (Render)

## Steps

1. Create a new Web Service in Render.
2. Connect the GitHub repository and select the `main` branch.
3. Set the runtime to **Docker**.
4. Add a Render managed PostgreSQL database.
5. Configure environment variables:
   - DATABASE_URL — provided by Render PostgreSQL.
   - DJANGO_SECRET_KEY — strong random secret.
   - SENTRY_DSN — optional; activates Sentry when set.
   - REDIS_URL — optional; external Redis instance.
6. Deploy. Render builds the Dockerfile and starts Gunicorn.

## Worker Service

Django-Q2 background tasks need a separate worker:

1. Create a second service from the same repository.
2. Start command: python manage.py qcluster
3. Use the same environment variables as the web service.

## Health Check

- Path: /health/
- Expected: HTTP 200 with JSON {"web": "ok", "db": "ok", "queue": "ok"}
- On failure: HTTP 503 with the failing component details.

## Backups

- Render managed PostgreSQL has automatic daily backups with 7-day retention.
- RPO <= 1 hour, RTO < 4 hours when restoring from backup.

## Logs

- View logs in the Render dashboard.
- JSON structured logs to stdout.
- Sentry integration active when SENTRY_DSN is set.
