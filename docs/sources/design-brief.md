# StockAdvice — Design Brief

**Living document.** Updated as design decisions are made during development. The canonical proposal lives at `openspec/changes/automotive-stock-advisor/proposal.md` — this document complements it with technical decisions, stack, architecture, and chronological log.

---

## 1. Project overview

StockAdvice is an **advisory replenishment system for multi-sector inventory**. v1 is configured by default for the **automotive aftermarket (dealerships)** sector; other sectors (pharmaceutical, hardware store, manufacturing, etc.) are supported via the `sector-configuration` capability.

- **Mode**: advisory layer **read-only** over the existing DMS/ERP. It never writes stock.
- **Multi-tenant-ready**: single-tenant v1 with `tenant_id` from day 1.
- **Development context**: small team (potentially a single developer). Stack prioritizes simplicity, documentation, low operational burden.

---

## 2. Core methodology (sector-agnostic)

Standard inventory management formulas (universal, not proprietary):

- **Planning Target** = (monthly_sales / 30) × period_days
- **Reorder Point** = Planning Target + Lead Time
- **Order Quantity** = Planning Target − Available Stock − In Transit Stock
- **Excess stock** (for inter-branch transfers) = Current Stock − Reorder Point
- **Volume Class (VC1–VC8)**: by annual sales volume
- **Lifecycle Stage**: New, Active, Pre-Obsolete, Obsolete, Inactive

---

## 3. Constraints (from proposal)

- **Multi-sector by design, automotive by default** (configurable via `sector-configuration`)
- **No confirmed pilot client** — developed for an eventual first tenant
- **Solo development** (potentially single developer) — stack favors simplicity
- **Implementation-assisted onboarding** (no self-service in v1)
- **Read-only from DMS** (no stock writes)
- **Formula coverage is sector-agnostic** — labels (Volume Class, Lifecycle Stage) are configurable; the math is not

---

## 4. Design decisions (TBD)

> This section is populated as decisions are made. Each decision has date, choice, and rationale.

### 4.1 Stack selection — [DECIDED: 2026-08-08]

**Decision**: **Python 3.12+ / Django 5.1+ / PostgreSQL 16+**

| Component | Choice | Brief reason |
|---|---|---|
| Language | Python 3.12+ | Ubiquitous, readable, massive ecosystem, no build step |
| Web framework | Django 5.1+ (LTS) | Batteries-included: ORM, auth, admin, templates, migrations, email. **Admin panel saves weeks of CRUD** |
| Database | PostgreSQL 16+ | Rich types (JSONB, arrays, enums), window functions for velocity, mature replication |
| ORM | Django ORM (built-in) | Zero-setup, migrations included, expressive query API |
| Migrations | Django migrations (built-in) | Auto-generated, reversible |
| Task queue | Django-Q2 + Redis | Lightweight for Django. DB-backed in dev, Redis in prod. Cron + async |
| Email | `django.core.mail` + Anymail | Anymail unifies SendGrid/SES/Postmark/Mailgun. Swap via env var |
| Auth | Django sessions + allauth | Server-side sessions, simpler than JWT for server-rendered UI |
| Frontend | Django templates (Jinja2) + HTMX | Server-rendered. HTMX for partial updates without SPA complexity |
| Testing | pytest + pytest-django + factory_boy | pytest + fixtures for realistic tests |
| Logging | structlog | JSON structured logs to stdout, ship to any aggregator later |
| Deployment | Render (PaaS) or Docker on single VPS | Render zero-ops for solo dev. Docker Compose as fallback for VPS |

**Rejected alternatives**:
- Ruby on Rails: equally productive; Python chosen for its broader ecosystem. Django admin is the tiebreaker.
- FastAPI + SQLAlchemy: too unopinionated for solo dev. Auth, admin, templates all from third parties.
- Node.js + NestJS: NestJS is enterprise-grade, heavy boilerplate. JS fragmentation adds decision fatigue.
- .NET 8 + ASP.NET Core + EF Core: excellent tooling (Rider/VS), very powerful LINQ for queries, fastest web framework, large enterprise talent pool. NOT chosen because: (1) does not have an admin panel comparable to Django admin (would require ABP/Orchard or custom); (2) the Spanish-speaking dev community leans more toward Python/JS; (3) Python + Django faster to prototype in solo dev. Revisit if the target market shifts to enterprise clients with .NET stack, or if hiring becomes a priority.
- SQLite for production: does not scale concurrent writes, lacks JSONB/window function parity with Postgres.

**Full details**: see `openspec/changes/automotive-stock-advisor/design.md` §1.

### 4.2 DMS integration pattern — [PENDING]

**Options**:
- Direct DB connection (driver per DMS) — v1 default (per proposal)
- API integration
- File-based (CSV/XLS upload)
- ETL batch

**Status**: pending. The proposal assumes **direct DB connection** (per proposal §6 and prior integration decision). Need to choose **which DMS target** for the first adapter (open question in design).

**Adapter pattern details**: see `openspec/changes/automotive-stock-advisor/design.md` §4. `BaseDMSAdapter` interface with methods `read_parts()`, `read_stock()`, `read_sales()`, `read_purchase_orders()`. Each DMS implements its own class.

### 4.3 Deployment model — [DECIDED: 2026-08-08]

**Decision**: **Render (PaaS) as default, with Docker Compose as fallback for VPS**

- **Render**: zero-ops for solo dev. Deploy with `git push` or button. SSL, DB, logs included. Initial free plan.
- **Docker Compose (fallback)**: if Render doesn't fit (costs, latency, compliance), a `Dockerfile` + `docker-compose.yml` runs the system on any VPS (DigitalOcean, Hetzner, etc.). The project includes both setups.
- **Self-hosted on tenant infra**: deferred to v2+ (when there's a client with specific infra).

**Reason**: Render minimizes operational burden for a solo dev. Docker fallback covers the case "I need to run it on my own infra".

### 4.4 Database — [DECIDED: 2026-08-08]

**Decision**: **PostgreSQL 16+**

**Reasons**:
- JSONB for `sector-configuration` (flexible key-value)
- Window functions for weighted velocity calculation
- Native arrays and enums (useful for Volume Class / Lifecycle Stage codes)
- Mature replication and backup
- Default choice; no reason to deviate

**SQLite discarded**: doesn't scale concurrent writes, lacks JSONB/window function parity with Postgres.

**Options**:
- PostgreSQL (standard, full-featured)
- MySQL/MariaDB (also full-featured, slightly simpler)
- SQLite (dev/local only, not recommended for prod)

**Status**: pending.

### 4.5 Background jobs / scheduling — [DECIDED: 2026-08-08]

**Decision**: **Django-Q2 + Redis**

- **Django-Q2**: Django-specific scheduler and task queue. Less overhead than Celery for solo dev.
- **Redis**: production broker. In dev, Django-Q2 can use the DB as broker (no Redis needed).
- **Defined jobs**:
  - `replenishment_run` (per branch, per schedule)
  - `classification_pass` (periodic, monthly)
  - `notification_dispatch` (sends pending notifications)
  - `audit_log_cleanup` (optional, for retention)
- **Idempotency**: each job has a lock-key to avoid duplicate concurrent executions.
- **Future migration**: if job volume grows significantly (hundreds of branches, thousands of SKUs), migrate to Celery in v1.5. It's a relatively clean swap since both use Python.

### 4.6 Authentication — [DECIDED: 2026-08-08]

**Decision**: **Django sessions + django-allauth (email + password)**, OAuth as v2+

- **Server-side sessions**: signed cookies, simple for server-rendered UI. More secure and simpler than JWT for v1.
- **allauth**: handles email verification, password reset, invite flow, social accounts (ready for future OAuth).
- **Password hashing**: PBKDF2 by Django default (configurable to Argon2).
- **Multi-role**: union of permissions (non-exclusive). Audit log records which role was used for each action.
- **OAuth (Google/Microsoft)**: deferred to v2. The allauth model supports it, just needs to be activated.
- **Magic link**: discarded for v1 (adds complexity to invitation flow; admin invites by email with normal link).

### 4.7 Notifications — [DECIDED: 2026-08-08]

**Decision**: **Django email + Anymail** (provider-agnostic)

- **Anymail**: unified API for SendGrid, Postmark, AWS SES, Mailgun. Swap via env var.
- **Specific provider**: chosen at implementation. For Render, SendGrid or Postmark are easiest. For self-hosted, generic SMTP.
- **Templates**:
  - Recommendation pending (branch manager)
  - Recommendation pending (coordinator, escalation)
  - Recommendation pending (gerente, cross-coordinator)
  - Partial fulfillment alert
  - Lifecycle transition request (gerente)
  - User invitation
  - Password reset
- **In-app dashboard**: in addition to email, dashboard shows in-app notifications.
- **Throttling**: digest per day instead of one email per recommendation. Configurable.

### 4.8 Observability — [DECIDED: 2026-08-08]

**Decision**:
- **Logs**: structlog (structured JSON to stdout). On Render, logs go to their native dashboard. On VPS, journald or similar.
- **Error tracking**: Sentry (self-hosted or SaaS, decided at implementation). Sentry.io free tier is sufficient for v1.
- **Metrics**: basic via Django-debug-toolbar in dev, and a simple admin dashboard (`/admin/`) with counters (recommendations generated, approved, etc.) in prod. Prometheus + Grafana deferred to v1.5+.

---

## 5. Architecture

> Populated as the design phase progresses.

### 5.1 Module structure
*(PENDING)*

### 5.2 Data model (high level)
*(PENDING)*

### 5.3 API surface
*(PENDING)*

### 5.4 DMS adapter pattern
*(PENDING)*

---

## 6. Open questions (deferred)

> Questions the design phase must resolve, or deferred to v2+.

### 6.1 For design phase
- **Exact weighted velocity formula**: linear decay, exponential smoothing, custom weights per month
- **Default escalation thresholds**: industry-standard, configurable per tenant
- **Classification pass frequency**: separate job vs. part of the replenishment run
- **Cron schedule default**: what time of day does the scheduled job run? configurable per branch?
- **Lead time source**: per-supplier config, per-product config, derived from PO history?
- **Notification channels**: email + in-app only, or also SMS/push?
- **Dashboard rendering**: server-side rendering (templates) or SPA (React/Vue)?

### 6.2 Deferred to v2+
- Multi-tenant SaaS completo
- Multi-region deployment
- Self-service onboarding
- Automated seasonal adjustment
- Automated obsoletion detection (without admin/gerente review)
- External supplier identification (system names specific supplier)
- System-owned catalog enrichment
- Branch proximity metadata for transfer optimization
- Advanced analytics (forecast accuracy, recommendation quality)
- Multi-level DCs (DC depending on another DC)
- Native mobile app

---

## 7. Decisions log (chronological)

> Chronological log of design decisions made during development.

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-07-29 | Multi-sector scope, automotive default | Commercial viability, broader market |
| 2026-07-29 | Remove LPR / Star Cooperation references | IP / trademark concerns for commercialization |
| 2026-07-29 | Adjust for solo development | First client declined; project continues with solo dev |
| 2026-07-29 | MVP-first approach (Phase 0 spike, Phase 1 MVP) | Reduce risk with minimal initial investment |
| 2026-07-29 | Create design brief (this file) | Living document for technical decisions |
| 2026-08-08 | **Stack: Python 3.12+ / Django 5.1+ / PostgreSQL 16+** | Django admin (CRUD) + mature ecosystem + solo-dev friendly. See design §1 |
| 2026-08-08 | **Database: PostgreSQL 16+** | JSONB, window functions, enums. No reason to deviate |
| 2026-08-08 | **Background jobs: Django-Q2 + Redis** | Lighter than Celery for solo dev. Migratable to Celery if growth |
| 2026-08-08 | **Auth: Django sessions + allauth (email/password)** | Simple for server-rendered. OAuth deferred to v2 |
| 2026-08-08 | **Notifications: Django email + Anymail (provider-agnostic)** | Provider swap via env var. SendGrid/Postmark/SES/Mailgun |
| 2026-08-08 | **Frontend: Django templates + HTMX** | Server-rendered, no JS build step. Pico.css for styling |
| 2026-08-08 | **Deployment: Render (default) or Docker Compose (fallback)** | Render zero-ops for solo dev. Docker for VPS |
| 2026-08-08 | **Observability: structlog + Sentry** | JSON logs + error tracking. Basic metrics via admin |
| 2026-08-08 | **Architecture: Django monolith with service layer, 9 apps** | Single Django app, no microservices. Apps: core, accounts, branches, catalog, inventory, classification, replenishment, notifications, dashboard |
| 2026-08-08 | **Data model: 13 main entities** | See design §3. Covers multi-tenant, multi-role, multi-coordinator, DC topology, state machine, audit log |
| 2026-08-08 | **Roadmap: Phase 0 spike (3-5 days) + Phase 1 MVP (10 weekly increments)** | Spike validates formulas before building Django app. Phase 1 prioritizes by dependencies |
| 2026-08-08 | **Formula convention: adopt material interpretation (lead time INCLUDED in Planning Target)** | Spike found discrepancy: material example gives 37/47/12, proposal formula gave 30/36.67/5. User chose material's convention. Planning Target = (v/30) × (period + security + lead). PP = PT + lead_time_days (raw, matches material). **All 51 tests passing on updated formulas**. Spike validated end-to-end with 30 SKUs. |

---

## 8. MVP-first roadmap (from proposal §12)

> Reminder of the recommended approach. Update as executed.

- **Phase 0 (spike)** — Days, not months. Small script that runs the core flow end-to-end: reads a small dataset → calculates Reorder Point → generates a recommendation → shows it in console or simple HTML. Validates the methodology with the developer as first "user".
- **Phase 1 (v1 MVP)** — 2-3 months. Full v1 scope but with simple tooling, basic UI, most important features first. Defer the rest (advanced analytics, complex multi-coordinator, etc.) to v1.5 or v2.
- **Phase 2+ (v1 full + v2)** — Complete v1 + add v2+ features + production hardening.

---

## 9. References

- **Proposal (canonical)**: `openspec/changes/automotive-stock-advisor/proposal.md` — source of truth for the WHAT of the system
- **Source material (internal)**: `docs/sources/Material_LPR_Basics_dia3.md` — Star Cooperation LPR Basics, day 3 (internal reference; NOT cited in commercial proposal)
- **Engram memory**: project context, decisions, traceability by topic_key `stockadvice-v1/*` and `sdd/automotive-stock-advisor/*`

---

## 10. Conventions

- **Markdown** for this document (readable in any editor / viewer).
- **Dates** in ISO format (YYYY-MM-DD).
- **Decisions** are numbered: D-001, D-002, ... (when formalized)
- **Open questions** are numbered: Q-001, Q-002, ...
- **Major changes** are marked with `**Status**: DECIDED` or `**Status**: PENDING`.
