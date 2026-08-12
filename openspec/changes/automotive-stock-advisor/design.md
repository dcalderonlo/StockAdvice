# Design: Automotive Stock Advisor

## Metadata

| Field | Value |
|-------|-------|
| Change slug | `automotive-stock-advisor` |
| Status | draft |
| Date | 2026-08-08 |
| Stack | Python 3.12+ / Django 5.1+ / PostgreSQL 16+ |
| Artifact store | hybrid (engram + openspec) |

## 1. Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Language | Python 3.12+ | Ubiquitous, readable, massive ecosystem. No build step. |
| Web framework | Django 5.1+ (LTS) | Batteries-included: ORM, auth, admin, templates, migrations, email. Admin panel alone saves weeks of CRUD UI for a solo dev. |
| Database | PostgreSQL 16+ | Rich types (JSONB, arrays, enums), window functions for time-series velocity calc, mature replication/backup. Default choice; no reason to deviate. |
| ORM | Django ORM (built-in) | Zero-setup, migrations included, expressive query API. Complex aggregations (window functions for velocity) via `RawSQL` or `Window` expressions. |
| Migrations | Django migrations (built-in) | Auto-generated from models, reversible, integrated. |
| Task queue | Django-Q2 + Redis | Lightweight scheduler for Django. DB-backed for dev (no Redis needed), Redis for prod. Supports cron schedules, async tasks, result hooks. |
| Email | Django `django.core.mail` + Anymail | Anymail provides unified API for SendGrid/SES/Postmark/Mailgun. Swap provider via env var. |
| Auth | Django `django.contrib.auth` (sessions) + `django-allauth` | Server-side sessions (simpler than JWT for server-rendered UI). Allauth handles email verification, password reset, invite flow. bcrypt via Django's default PBKDF2 (configurable to Argon2). |
| Frontend | Django templates (Jinja2) + HTMX | Server-rendered. HTMX for partial updates (approve/reject, dashboard refresh) without SPA complexity. No JS build step. |
| Testing | pytest + pytest-django + factory_boy | pytest for flexibility, factory_boy for test fixtures, pytest-django for DB access. |
| Logging | structlog | Structured JSON logs to stdout. Ship to any aggregator later (Sentry, Papertrail, etc.). |
| Deployment | Render (PaaS) or Docker on single VPS | Render: zero-ops for solo dev. Docker Compose as fallback for VPS. `Dockerfile` + `docker-compose.yml` included for either path. |

**Alternatives considered and rejected**:

| Option | Rejected because |
|--------|-----------------|
| Ruby on Rails | Equal in productivity; Python chosen for broader ecosystem familiarity. Django admin is the tiebreaker. |
| FastAPI + SQLAlchemy | Too unopinionated for solo dev. Admin panel, auth, templates all require third-party assembly. |
| Node.js + NestJS | NestJS is enterprise-grade boilerplate-heavy. JS ecosystem fragmentation adds decision fatigue for one person. |
| .NET 8 + ASP.NET Core + EF Core | Strong tooling (Rider/VS), excellent LINQ for data queries, fastest web framework, large enterprise talent pool. NOT chosen because: (1) no built-in admin comparable to Django admin (would need ABP/Orchard or custom); (2) Spanish-speaking dev community skews Python/JS; (3) Python + Django faster to prototype for solo dev. Revisit if the target market shifts to enterprise clients with .NET stack or if hiring becomes a priority. |
| SQLite for prod | No concurrent write scaling; no JSONB/window-function parity with PostgreSQL. |

## 2. Architecture

**Monolith by deliberate choice.** Single Django app deployed as one process. No microservices, no message broker beyond Redis for task queue. Background workers run as a separate process (`python manage.py qcluster`) on the same host.

### Module structure

```
stockadvice/
├── config/              # Django settings, urls, wsgi/asgi
├── apps/
│   ├── core/            # Tenant, SectorConfiguration, base models
│   ├── accounts/        # User, Role, UserRole, invitation flow
│   ├── branches/        # Branch, BranchHierarchy
│   ├── catalog/         # Part, CrossReference, DMS adapter interface
│   ├── inventory/       # StockLevel, StockMovement, StockEnTransito
│   ├── classification/  # ClassificationEngine, ClassificationResult
│   ├── replenishment/   # ReplenishmentEngine, Recommendation, Override
│   ├── notifications/   # Email templates, NotificationDispatch
│   └── dashboard/       # Role-scoped views, KPI queries, CSV export
├── adapters/            # DMS adapter implementations
│   ├── base.py          # Abstract interface
│   └── autologica/      # First DMS adapter (placeholder)
├── jobs/                # Scheduled job definitions
├── templates/           # Jinja2 templates
├── static/              # HTMX + minimal CSS (Pico.css)
└── Dockerfile
```

### Request flow

```
Browser (HTMX) → Django View → Service Layer → Repository (Django ORM)
                                                      ↓
                                              PostgreSQL / DMS adapter
```

- **Views**: thin — extract params, call service, render template or return HTMX partial.
- **Services**: business logic — `ReplenishmentService.run(branch_id)`, `ClassificationService.classify_all()`.
- **Repositories**: Django ORM querysets, encapsulated in model managers.
- **Adapters**: DMS reads go through `adapters/base.py` → concrete implementation.

### Auth flow

Session-based. Login → Django session cookie. Every request checks `request.user`. Multi-role: `request.user.userrole_set.active()` returns all roles. Views check `User.has_perm(perm)` which unions all role permissions. Audit log records `(user_id, role_id_used, action, timestamp, metadata_json)`.

## 3. Data Model (major entities)

| Entity | Key fields | Relationships |
|--------|-----------|---------------|
| **Tenant** | id, name, config_json | Has many Users, Branches |
| **User** | id, email, password_hash, is_active | Has many UserRoles |
| **Role** | id, name (admin/gerente/coordinator/warehouse_manager) | Has many UserRoles |
| **UserRole** | id, user_id, role_id, branch_id (optional), scope_json | FK→User, FK→Role, FK→Branch(nullable) |
| **Branch** | id, tenant_id, name, branch_type (sucursal/centro_distribucion), parent_branch_id | FK→Tenant, self-referential FK |
| **Part** | id, tenant_id, internal_sku_code, primary_mfr_code, alt_mfr_codes (JSONB), description, lead_time_days | FK→Tenant |
| **CrossReference** | id, part_id, related_part_id, relation_type (substitute/alternative/successor), source_dms | FK→Part×2 |
| **StockLevel** | id, branch_id, part_id, stock_disponible, stock_en_transito, last_synced_at | FK→Branch, FK→Part |
| **StockMovement** | id, branch_id, part_id, movement_type (sale/purchase/transfer), quantity, date | FK→Branch, FK→Part |
| **Recommendation** | id, branch_id, part_id, quantity, source_type (transfer/supplier), source_branch_id, state (pending/approved/rejected/handled/ordered), classification_code, created_at | FK→Branch, FK→Part |
| **DemandOverride** | id, part_id, branch_id, override_type (persistent/per_run/with_expiry), quantity, expires_at, created_by | FK→Part, FK→Branch, FK→User |
| **ClassificationResult** | id, part_id, volume_class (VC1–VC8), lifecycle_stage (N1–N3/OBS-S/OBS-N/OBS-P/OBS-R/Inactive/NS-C/NS-NS), classified_at | FK→Part |
| **AuditLog** | id, user_id, role_used_id, action, entity_type, entity_id, metadata_json, created_at | FK→User, FK→Role |
| **SectorConfiguration** | id, tenant_id, sector_key, config_json (terminology, thresholds, classification labels, lifecycle rules) | FK→Tenant |

**Branch → Branch (self-referential)** supports DC topology: `parent_branch_id` links a `sucursal` to its `centro_distribucion`. DCs have `parent_branch_id = NULL`.

## 4. DMS Integration

```
# adapters/base.py — Abstract interface
class BaseDMSAdapter(ABC):
    @abstractmethod
    def read_parts(self, tenant_id) -> Iterator[PartData]: ...
    @abstractmethod
    def read_stock(self, branch_id) -> Iterator[StockData]: ...
    @abstractmethod
    def read_sales(self, branch_id, since_date) -> Iterator[SalesData]: ...
    @abstractmethod
    def read_cross_references(self, tenant_id) -> Iterator[CrossRefData]: ...
    @abstractmethod
    def read_branches(self, tenant_id) -> Iterator[BranchData]: ...
```

- **Implementation**: one class per DMS (e.g., `AutologicaAdapter`, `SAPAdapter`). Each handles schema variability internally via column mapping or API normalization.
- **Retry/timeout**: 3 retries with exponential backoff (1s/2s/4s), 30s per-call timeout. Wrapped in `@retry` decorator from `tenacity`.
- **Live read**: confirmed — no caching. Every replenishment run pulls fresh DMS data. This is per proposal §6 "Sync frequency: per-run." The system's own DB persists derived metrics (classification, velocity), not DMS snapshots.
- **First DMS**: deferred to implementation (open question). First adapter built against whichever DMS the first tenant uses. Adapter interface is designed to be generic.

## 5. Scheduled Jobs

| Job | Schedule | Idempotency key |
|-----|----------|-----------------|
| `replenishment_run` | Per-branch cron (weekly by default) via Django-Q2 `schedule` | `(branch_id, run_date)` — dedupe at job start |
| `classification_pass` | Monthly (`@cron 0 3 1 * *`) | `(tenant_id, month_key)` — runs once per month |
| `notification_dispatch` | Every 15 min, processes pending queue | `SELECT ... FOR UPDATE SKIP LOCKED` to avoid double-send |
| `audit_log_cleanup` | Weekly | Soft-delete logs >12 months old |

**Scheduling**: Django-Q2's built-in scheduler reads from `django_q.Schedule` model. Cron-like syntax. No external scheduler needed.

**Idempotency**: `replenishment_run` checks for existing `Recommendation` with same `(branch_id, part_id, run_date)` before inserting. `classification_pass` upserts by `(part_id, classified_at_month)`.

**Failure**: 3 retries with 5min delay. Dead tasks visible in Django-Q2 admin. Alert via Sentry (or stdout log + developer check for v1).

## 6. Auth & Authorization

| Decision | Choice |
|----------|--------|
| Session type | Server-side Django sessions (DB-backed). Expiry: 2h idle, 24h absolute. |
| Password storage | Django's PBKDF2 (default). Configurable to Argon2id via `PASSWORD_HASHERS`. |
| Multi-role resolution | `User.get_all_permissions()` unions all assigned roles. Audit log records `role_used_id` per action. |
| Permission model | Deny-by-default. Explicit grants per role. Django's `auth.Permission` + custom `can_approve_cross_coordinator` etc. |
| Session expiry | Idle: 2h (renewable). Absolute: 24h (re-login required). |

**Permission matrix**:

| Action | Admin | Gerente | Coordinator | Branch Manager |
|--------|-------|---------|-------------|----------------|
| Configure system | ✅ | — | — | — |
| Manage users (all) | ✅ | below only | scope only | — |
| View global KPIs | ✅ | ✅ | scope only | own branch |
| Approve recommendations | — | cross-coord only | scope only | own branch |
| Escalate recommendation | — | ✅ | ✅ | ✅ |
| Review classification | — | ✅ (+ delegate) | if delegated | view only |
| Apply demand override | — | — | — | ✅ (own branch) |
| Set escalation thresholds | ✅ | — | scope only | — |

## 7. Notifications

| Template | Trigger | Recipients |
|----------|---------|------------|
| `recommendation_pending` | Replenishment run completes with new recs | Branch manager |
| `recommendation_escalated` | Recommendation crosses threshold | Coordinator (+ gerente if cross-coordinator) |
| `partial_fulfillment` | Excess stock insufficient for full transfer | Branch manager + coordinator(s) + gerente |
| `cold_start_flag` | SKU with zero history flagged | Branch manager |
| `classification_review` | Monthly classification pass complete | Gerente (or delegated coordinator) |
| `dc_stock_critical` | DC stock below critical threshold | DC branch manager + dependent coordinators + gerente |

**Throttling**: One digest email per run (not one per recommendation). In-app notifications are real-time per item; email is batched. Daily digest at 8AM for all pending items.

## 8. Dashboard

- **Rendering**: Server-side Django templates + HTMX. Pico.css for styling (minimal, classless, no build step).
- **Role-based views**: template conditionals (`{% if user.is_gerente %}`) render different widgets per role.
- **Widgets per role**: Branch manager sees: pending recs count, KPIs (Stock Total, Rotación, Cobertura, Stock Obsoleto, Stock Excesivo), override log, classification results. Coordinator sees: aggregated KPIs for scope, escalated items, branch activity. Gerente sees: org-wide KPIs, cross-coordinator transfers, classification review queue. Admin sees: all of the above + config panels.
- **Refresh**: HTMX `hx-trigger="every 60s"` for KPI tiles. Approval actions refresh inline.
- **Export**: CSV download for recommendation tables, KPI data. `django-import-export` or plain `csv.writer` via `HttpResponse`.

## 9. Configuration

| Config layer | Mechanism |
|-------------|-----------|
| Per-tenant settings | `Tenant.config_json` (JSONField) — thresholds, schedules, terminology labels |
| Sector configuration | `SectorConfiguration` model — `sector_key` + `config_json` with classification labels, lifecycle rules, terminology. Automotive is default; others added via admin. |
| Thresholds | Stored in `Tenant.config_json` (escalation thresholds, lead time defaults). Overridable per-branch via `Branch.config_json`. |
| Feature flags | None for v1. Simple boolean config keys in `config_json` if needed later. |
| Environment vars | `DATABASE_URL`, `SECRET_KEY`, `EMAIL_URL`, `REDIS_URL`, `SENTRY_DSN` (all via `.env` / `django-environ`). |

## 10. Deployment

| Concern | Approach |
|---------|----------|
| Target | **Render** (PaaS) — web service + worker service + PostgreSQL managed. Zero-ops. Fallback: single VPS (Hetzner $4/mo) with Docker Compose. |
| Containerization | `Dockerfile` (multi-stage: python:slim, gunicorn + whitenoise for static) + `docker-compose.yml` (app + db + redis + worker). |
| CI/CD | GitHub Actions: lint (ruff), test (pytest), build Docker image, push to registry. Render auto-deploys on push. |
| Backups | PostgreSQL managed backups (Render) or `pg_dump` cron + S3/rsync (VPS). Daily full, hourly WAL. |
| DR | Single-server: restore from latest backup. RPO: 1 hour, RTO: < 4 hours. |
| Local dev | `docker-compose up` runs everything. `make reset-db` for fresh start. `make seed` for demo data. |

## 11. Observability

| Signal | Tool | Approach |
|--------|------|----------|
| Logs | structlog → stdout | JSON structured. Fields: `timestamp`, `level`, `logger`, `event`, `request_id`, `user_id`, `branch_id`. |
| Errors | Sentry (optional, env var) | Django integration catches unhandled exceptions. V1 fallback: stdout logs are enough. |
| Metrics | Custom counters in DB | `MetricSnapshot` table: `recommendations_generated`, `recommendations_approved`, `job_runs`, `job_failures`. Simple admin dashboard reads these. No Prometheus for v1. |
| Alerts | Sentry alerts (if configured) | Alert on: job failure >3 consecutive, 500-rate spike, DB connection loss. |

## 12. Testing

| Layer | Tool | Approach |
|-------|------|----------|
| Unit | pytest | Service logic, classification formulas, velocity calc. Target: ≥80% on services. |
| Integration | pytest-django + factory_boy | View tests (request→response), DMS adapter with mock adapter returning fixtures. |
| E2E | Deferred to v1.5 | Playwright or manual testing. |
| Manual | Developer as first user | Run replenishment against seed data, verify dashboard, approve/reject recs. |
| Test data | Factory boy + `make seed` | `factory_boy` generates realistic Parts, StockLevels, Movements. A management command seeds a demo tenant with 50 SKUs, 4 branches, 12 months of sales. |

## 13. Security & Compliance

| Concern | Approach |
|---------|----------|
| Password policy | Minimum 8 chars, Django's default validators. Rate-limit login (5 attempts/15 min per IP). |
| Data at rest | PostgreSQL encryption-at-rest (Render managed or LUKS/dm-crypt for VPS). |
| Data in transit | HTTPS only (TLS 1.3). HSTS, secure cookies, CSP headers. |
| PII | Email addresses, names, branch assignments. Stored in DB; no sensitive financial data. |
| Audit log | Immutable: append-only, no update/delete on `AuditLog` rows (enforced at application layer). Hash chain optional for v2. |
| Sector compliance | Pharmaceutical (GMP traceability), financial (SOX) — v2 only. V1 is automotive default with no regulatory burden. |

## 14. Threat Matrix

**N/A** — this design introduces no routing, shell commands, subprocesses, VCS/PR automation, executable-file classification, or process-integration boundary. The system is a standard web application reading from external databases; no dynamic path resolution, git operations, or command composition at runtime.

## 15. Open Questions

| ID | Question | Resolution criteria |
|----|----------|---------------------|
| Q-001 | Exact weighted velocity formula | Choose during Phase 0 spike: test linear decay vs. exponential smoothing against seed data. Pick the one that produces stabler Punto de Pedido. |
| Q-002 | Default escalation thresholds | Set initial values during Phase 1 based on automotive aftermarket industry averages (e.g., €5K value threshold, 50-unit volume threshold). Configurable per tenant. |
| Q-003 | Classification pass: separate or part of run? | Separate (monthly). Replenishment runs weekly; reclassifying on every run is wasteful and produces noise. |
| Q-004 | First DMS to build adapter for | Deferred until first tenant signs. The `BaseDMSAdapter` interface is designed to be generic; first implementation will validate it. |
| Q-005 | Email provider | Anymail supports SendGrid/SES/Postmark/Mailgun. Pick the cheapest with adequate deliverability in the tenant's region. SendGrid free tier is enough for v1. |
| Q-006 | Specific CSS framework or design system | Pico.css is proposed for v1 (classless, minimal). Evaluate Tailwind or Bootstrap if custom designs are needed for client demos. |
| Q-007 | Notification throttling strategy | Start with one digest per run + daily 8AM summary. Tune based on user feedback. |
| Q-008 | Log aggregation tool | stdout for v1 development. Add Papertrail, Logtail, or self-hosted Grafana Loki when first tenant goes live. |

## 16. Implementation Roadmap

### Phase 0 — Spike (3–5 days)

Validate the core methodology. No Django. No database. One Python script.

1. **`spike.py`**: Read from a CSV/JSON fixture (50 SKUs, 12 months of sales) → calculate Volume Class + Lifecycle Stage → calculate weighted velocity → calculate Punto de Pedido + Cantidad de Pedido → print recommendations to console.
2. **Goal**: Does the algorithm produce sensible recommendations? Tune formulas here, not in Phase 1.
3. **Deliverable**: A Python script + fixture data + a 1-page README with findings.

### Phase 1 — MVP (6–10 weeks)

Build in dependency order. Each phase produces a working, demo-able system.

| Week | Deliverable | Capabilities |
|------|-------------|-------------|
| 1 | Django scaffold + `core` + `accounts` | User, Role, UserRole, auth flow, admin panel. Login/logout works. |
| 2 | `branches` + `catalog` | Branch model, Part model, DMS adapter interface + mock adapter. Admin can create branches and upload parts CSV. |
| 3 | `inventory` | StockLevel, StockMovement, StockEnTransito. Mock adapter seeds 12 months of sales. |
| 4 | `classification` | ClassificationEngine: VC1–VC8 and Lifecycle Stage derivation. ClassificationResult visible in dashboard. |
| 5 | `replenishment` (engine) | Planning Target, Punto de Pedido, Cantidad de Pedido calculation. Manual trigger from admin panel. |
| 6 | `replenishment` (recs + source) | Recommendation generation, inter-branch transfer logic, excess stock calculation. |
| 7 | `replenishment` (workflow) | Approval state machine, escalation, demand override UX with type selection. HTMX interactions. |
| 8 | `notifications` + `dashboard` | Email templates, in-app notifications, role-based dashboard with KPIs. |
| 9 | Scheduling + hardening | Django-Q2 scheduled jobs. CSV export. Audit log. Error handling. |
| 10 | Polish + demo data | `make seed` for demo tenant. Manual testing pass. README + deployment docs. |

### Phase 2+ (v1.5 → v2, deferred)

- Multi-tenant SaaS activation
- Automated seasonal adjustment
- Supplier identification in recommendations
- Vehicle compatibility (automotive)
- Branch proximity metadata for transfer optimization
- Advanced analytics dashboard
- E2E tests (Playwright)
- Self-service onboarding

## Open Questions

- [ ] Q-001: Exact weighted velocity formula (see §15)
- [ ] Q-003: First DMS adapter target
- [ ] Q-005: Email provider selection
- [ ] Q-006: CSS framework final choice
