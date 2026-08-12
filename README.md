# StockAdvice

StockAdvice is a scheduled stock-replenishment advisory service for multi-branch organizations. It reads live catalog and stock data from an existing DMS/ERP, calculates Volume Class, Lifecycle Stage, velocity, Planning Target, Punto de Pedido, and Cantidad de Pedido, then produces human-approved recommendations.

This repository is the foundation (WU-01): Django 5.1+ project scaffold, the `core` app with the `Tenant` model, tenant middleware, and the `accounts` app with user/role models.

## Stack

- Python 3.12+
- Django 5.1+
- PostgreSQL 16+
- structlog, pytest, factory_boy
- Docker / Docker Compose for local development

## Setup

### With Docker Compose (recommended)

```bash
cp .env.example .env
docker compose up --build
```

Then open http://localhost:8000/admin/.

### Without Docker

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

## Tests

```bash
pytest
```

## Project structure

- `config/` — Django settings (base/dev/prod/test), URLs, WSGI/ASGI.
- `apps/core/` — Tenant model, tenant middleware, context, admin.
- `apps/accounts/` — User, Role, and UserRole models.
- `templates/` — Django templates (login/logout).
- `spike/` — Phase 0 formula-validation script.
- `openspec/changes/automotive-stock-advisor/` — proposal, design, specs, tasks.

## Documentation

- Proposal: `openspec/changes/automotive-stock-advisor/proposal.md`
- Design: `openspec/changes/automotive-stock-advisor/design.md`
- Tasks: `openspec/changes/automotive-stock-advisor/tasks.md`
