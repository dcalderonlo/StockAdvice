# StockAdvice

> Scheduled, multi-sector stock-replenishment advisory service. Reads your existing
> DMS/ERP, computes velocity and reorder thresholds (Punto de Pedido), and emits
> human-approved recommendations — no autonomous purchasing.

[![CI](https://github.com/dcalderonlo/StockAdvice/actions/workflows/ci.yml/badge.svg)](https://github.com/dcalderonlo/StockAdvice/actions)
[![Docker](https://github.com/dcalderonlo/StockAdvice/actions/workflows/docker-build.yml/badge.svg)](https://github.com/dcalderonlo/StockAdvice/actions)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Django 5.1](https://img.shields.io/badge/Django-5.1-green.svg)](https://www.djangoproject.com/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

StockAdvice is a **scheduled, advisory** inventory-replenishment system for
multi-branch organizations. It does not replace your DMS/ERP or place
purchase orders autonomously — it **reads** from them and proposes
human-approved recommendations to the branch manager, coordinator, or
gerente.

The default sector is **automotive aftermarket** (concesionarios, repuestos),
but the system is designed to be configurable for **other sectors**
(pharmaceutical, hardware, manufacturing) via the `sector-configuration`
capability.

## How it works

```
DMS/ERP ──> [DMS Adapter] ──> [Ingestion] ──> [Velocity Calc] ──>
[Classification] ──> [Planning Calc] ──> [Recommendation Engine] ──>
[Source Resolution] ──> [Approval Workflow] ──> [Notification] ──> Branch Manager
```

1. **Read** the catalog, current stock, and 12+ months of sales history from the DMS.
2. **Compute** per-part metrics:
   - **Velocity** (weighted average favoring recent months)
   - **Volume Class** (VC1–VC8 by sales volume)
   - **Lifecycle Stage** (New / Active / Pre-Obsolete / Obsolete / Inactive)
   - **Planning Target**, **Punto de Pedido**, **Cantidad de Pedido**
3. **Generate** recommendations when stock ≤ Punto de Pedido (multi-branch transfer first, external supplier as fallback).
4. **Approve** via role-based workflow (manager → coordinator → gerente for cross-coordinator cases).
5. **Notify** the relevant people (email + in-app).

## Features

- 🏢 **Multi-tenant** ready (`tenant_id` from day 1)
- 🌍 **Multi-sector** configuration (default: automotive aftermarket)
- ⚙️ **DMS-agnostic** via pluggable adapter (Mock included for dev)
- 📊 **Material-aligned formulas**: Planning Target includes lead time (per Star Cooperation LPR methodology, validated in Phase 0 spike)
- 🏪 **Distribution Center** support (a DC supplies dependent branches)
- 🔁 **Inter-branch transfer** with greedy multi-source allocation
- 👤 **4-tier role model**: Admin → Gerente → Coordinator → Manager, with multi-role support and scope-aware access
- ⏰ **Scheduled jobs** via Django-Q2 (weekly replenishment, monthly classification, notifications every 15 min)
- 📋 **Full audit log** (every state transition tracked with role used)
- 🔌 **Onboarding flow** (5-step checklist: DMS → backfill → manager → test run → go-live)
- 🐳 **Docker Compose** for local dev (Postgres + Redis + Django)
- 🚀 **Render-ready** (see [`docs/render-deploy.md`](docs/render-deploy.md))

## Stack

| Layer | Technology |
|---|---|
| Language | Python 3.12+ |
| Web framework | Django 5.1 |
| Database | PostgreSQL 16 |
| Cache / queue | Redis 7 |
| Task scheduler | Django-Q2 |
| Async tasks | Django-Q2 (in-process worker, Redis broker) |
| Frontend | Django templates + HTMX (server-rendered, no SPA) |
| Email | django.core.mail + Anymail (provider-agnostic) |
| Auth | django.contrib.auth + django-allauth |
| Logging | structlog + python-json-logger (JSON to stdout) |
| Errors | Sentry (optional, activated by `SENTRY_DSN` env var) |
| CI/CD | GitHub Actions (lint, test, Docker build) |

## Quick start

### With Docker Compose (recommended)

```bash
git clone https://github.com/dcalderonlo/StockAdvice.git
cd StockAdvice
cp .env.example .env
docker compose up --build
```

Open <http://localhost:8000/admin/> and log in with the superuser you created during onboarding.

### Without Docker

```bash
python -m venv .venv
source .venv/binactivate
pip install -r requirements.txt -r requirements-dev.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

### Onboarding a un primer tenant

```bash
python manage.py onboard_tenant \
  --tenant-slug=<slug> \
  --dms-adapter=mock \
  --dms-config='{}' \
  --auto-go-live
```

Sigue el flujo de 5 pasos: DMS connection → Sales backfill (12+ meses) → Branch manager assignment → Test run → Go-live.

## Tests

```bash
# All tests
pytest

# Just the spike (formula validation)
cd spike && pytest

# With coverage
pytest --cov=apps
```

**Test counts**: 490 Django tests + 51 spike tests = 541 total.

## Project structure

```
StockAdvice/
├── apps/
│   ├── core/                # Tenant model, middleware, AuditLog
│   ├── accounts/            # User, Role, UserRole + invitation flow
│   ├── branches/            # Branch (with DC topology)
│   ├── catalog/             # Part, CrossReference, DMS adapter, overrides, classification
│   ├── inventory/           # StockLevel, StockMovement, StockEnTransito + ingestion
│   ├── recommendations/     # Recommendation model, state machine, source resolution
│   ├── notifications/       # Notification service + event triggers
│   ├── dashboard/           # Role-based dashboards (manager/coordinator/gerente/admin)
│   ├── sector/              # Sector configuration (multi-sector support)
│   ├── onboarding/          # 5-step onboarding flow
│   ├── scheduling/          # Django-Q2 jobs (weekly/monthly)
│   └── operations/          # Health check + structured logging
├── config/
│   └── settings/            # base / dev / prod / test
├── templates/               # Django templates (auth, dashboard, etc.)
├── spike/                   # Phase 0 formula validation (pure Python, 51 tests)
├── openspec/
│   └── changes/automotive-stock-advisor/
│       ├── proposal.md      # 408 lines
│       ├── design.md        # 298 lines
│       ├── specs/           # 13 given-when-then specs
│       └── tasks.md         # 87 tasks across 20 WUs
├── docs/
│   └── render-deploy.md     # Render deployment guide
├── .github/workflows/        # CI (lint + test) + Docker build
├── docker-compose.yml       # Postgres + Redis + Django dev server
├── Dockerfile               # Multi-stage production image
└── requirements.txt         # Pinned production deps
```

## Documentation

| Document | Path | Description |
|---|---|---|
| **Proposal** | `openspec/changes/automotive-stock-advisor/proposal.md` | What we're building (multi-sector, 4-tier roles, 14 business rules, 21 capabilities) |
| **Design** | `openspec/changes/automotive-stock-advisor/design.md` | Stack, architecture, data model, integrations |
| **Specs** | `openspec/changes/automotive-stock-advisor/specs/` | 13 Given-When-Then specs (one per capability) |
| **Tasks** | `openspec/changes/automotive-stock-advisor/tasks.md` | 87 tasks across 20 work units |
| **Design brief** | `docs/sources/design-brief.md` | Living document of design decisions and stack criteria |
| **Render deploy** | `docs/render-deploy.md` | Step-by-step deployment guide |

## Phase 1 MVP status

**✅ Complete** as of the latest commit on `main`. All 20 work units + CI/CD are implemented:

| WU | Capability | Status |
|---|---|---|
| WU-01 | Django Foundation & Core Models | ✅ |
| WU-02 | User Management & Invitation Flow | ✅ |
| WU-03 | Branch & Catalog Models + DMS adapter | ✅ |
| WU-04 | DMS Adapter Retry Mechanism | ✅ |
| WU-05 | Inventory Models & Data Ingestion | ✅ |
| WU-06 | Velocity Calculation Engine | ✅ |
| WU-07 | Classification Engine (VC + Lifecycle) | ✅ |
| WU-08 | Planning Calculation Engine | ✅ |
| WU-09 | Recommendation Engine (core) | ✅ |
| WU-10 | Source Resolution (inter-branch / external) | ✅ |
| WU-11 | Approval Workflow + Audit Log | ✅ |
| WU-12 | Escalation + Cross-Coordinator | ✅ |
| WU-13 | Demand Override (3 types) | ✅ |
| WU-14 | Notification Service (email + in-app) | ✅ |
| WU-15 | Branch Manager Dashboard | ✅ |
| WU-16 | Coordinator/Gerente/Admin Dashboards | ✅ |
| WU-17 | Sector Configuration | ✅ |
| WU-18 | Onboarding Flow | ✅ |
| WU-19 | Scheduling (Django-Q2) | ✅ |
| WU-20 | Operations (logging, Sentry, health) | ✅ |

## Roadmap

**Phase 2** (v2 features, not yet started):
- Automated obsoletion detection (lifecycle transitions without admin review)
- Seasonal adjustment (Ciclo Temporal from the source material)
- Multi-tenant SaaS activation (with self-service onboarding)
- Multi-region deployment
- Advanced analytics (forecast accuracy, recommendation quality scoring)
- External supplier identification in recommendations

## License

MIT — see [LICENSE](LICENSE).

## Contributing

The full Phase 1 MVP is implemented in this single repository via 20 chained PRs. For Phase 2 or feature work, the recommended workflow is:

1. Branch off `main`: `git checkout -b feature/<name>`
2. Implement + commit
3. Push + open a PR against `main`
4. CI runs lint + tests
5. Merge once CI passes

If you're a real pilot organization looking to deploy, contact the maintainers via the issues tab.
