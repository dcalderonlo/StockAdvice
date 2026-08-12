# StockAdvice — Design Brief

**Living document.** Se actualiza a medida que tomamos decisiones de diseño durante el desarrollo. La propuesta canónica vive en `openspec/changes/automotive-stock-advisor/proposal.md` — este documento la complementa con decisiones técnicas, stack, arquitectura, y registro cronológico.

---

## 1. Project overview

StockAdvice es un sistema de **asesoría de reposición de inventario multi-sector**. v1 se configura por defecto para el sector **automotriz aftermarket (concesionarios)**; otros sectores (farmacéutico, ferretero, manufactura, etc.) se soportan vía la capability `sector-configuration`.

- **Modo**: capa de asesoría **read-only** sobre el DMS/ERP existente. No escribe stock.
- **Multi-tenant-ready**: single-tenant v1 con `tenant_id` desde el día 1.
- **Contexto de desarrollo**: equipo chico (potentially un solo developer). Stack prioriza simplicidad, documentación, baja carga operacional.

---

## 2. Core methodology (sector-agnostic)

Fórmulas estándar de gestión de inventario (universales, no propietarias):

- **Planning Target** = (ventas_mensuales / 30) × días_del_periodo
- **Punto de Pedido** = Planning Target + Lead Time (Tiempo de Pedido)
- **Cantidad de Pedido** = Planning Target − Stock Disponible − Stock en Tránsito
- **Excess stock** (para transferencias inter-sucursal) = Stock Actual − Punto de Pedido
- **Volume Class (VC1–VC8)**: por volumen de ventas anual
- **Lifecycle Stage**: New, Active, Pre-Obsolete, Obsolete, Inactive

---

## 3. Constraints (from proposal)

- **Multi-sector by design, automotive by default** (configurable via `sector-configuration`)
- **No hay cliente piloto confirmado** — desarrollado para un eventual primer tenant
- **Desarrollo en solitario** (potentially single developer) — stack favorece simplicidad
- **Onboarding implementation-assisted** (no self-service en v1)
- **Read-only del DMS** (no escribe stock)
- **Cobertura de fórmulas sector-agnostic** — los labels (Volume Class, Lifecycle Stage) son configurables; las matemáticas no

---

## 4. Design decisions (TBD)

> Esta sección se llena a medida que se toman decisiones. Cada decisión tiene fecha, elección, y racional.

### 4.1 Stack selection — [DECIDED: 2026-08-08]

**Decisión**: **Python 3.12+ / Django 5.1+ / PostgreSQL 16+**

| Componente | Elección | Razón breve |
|---|---|---|
| Lenguaje | Python 3.12+ | Ubicuo, legible, ecosistema masivo, sin build step |
| Web framework | Django 5.1+ (LTS) | Batteries-included: ORM, auth, admin, templates, migrations, email. **El admin panel ahorra semanas de CRUD** |
| Database | PostgreSQL 16+ | Tipos ricos (JSONB, arrays, enums), window functions para velocity, replicación madura |
| ORM | Django ORM (built-in) | Zero-setup, migrations incluidas, query API expresivo |
| Migrations | Django migrations (built-in) | Auto-generadas, reversibles |
| Task queue | Django-Q2 + Redis | Ligero para Django. DB-backed en dev, Redis en prod. Cron + async |
| Email | `django.core.mail` + Anymail | Anymail unifica SendGrid/SES/Postmark/Mailgun. Swap via env var |
| Auth | Django sessions + allauth | Sessions server-side, más simple que JWT para server-rendered UI |
| Frontend | Django templates (Jinja2) + HTMX | Server-rendered. HTMX para partial updates sin SPA complexity |
| Testing | pytest + pytest-django + factory_boy | pytest + fixtures para tests realistas |
| Logging | structlog | JSON estructurado a stdout, ship a cualquier aggregator después |
| Deployment | Render (PaaS) o Docker en single VPS | Render zero-ops para solo dev. Docker Compose como fallback para VPS |

**Alternativas rechazadas**:
- Ruby on Rails: igual de productivo; Python elegido por ecosistema más amplio. Django admin es el desempate.
- FastAPI + SQLAlchemy: demasiado unopinionated para solo dev. Auth, admin, templates todos de terceros.
- Node.js + NestJS: NestJS es enterprise-grade, mucho boilerplate. Fragmentación de JS añade decision fatigue.
- .NET 8 + ASP.NET Core + EF Core: tooling excelente (Rider/VS), LINQ muy potente para queries, framework web más rápido, gran pool de talento enterprise. NO elegido porque: (1) no tiene admin panel comparable a Django admin (requeriría ABP/Orchard o custom); (2) la comunidad dev hispanohablante se inclina más a Python/JS; (3) Python + Django más rápido para prototipar en solo dev. Revisitar si el mercado objetivo cambia a clientes enterprise con stack .NET, o si la contratación se vuelve prioridad.
- SQLite para prod: no escala concurrent writes, no tiene JSONB/window functions de Postgres.

**Detalles completos**: ver `openspec/changes/automotive-stock-advisor/design.md` §1.

### 4.2 DMS integration pattern — [PENDING]

**Opciones**:
- Conexión directa a DB (driver por DMS) — v1 default (per proposal)
- API integration
- File-based (CSV/XLS upload)
- ETL batch

**Status**: pendiente. La propuesta asume **conexión directa a DB** (per §6 del proposal y decisión previa de integración). Falta elegir **qué DMS target** para el primer adapter (open question en el design).

**Detalles del adapter pattern**: ver `openspec/changes/automotive-stock-advisor/design.md` §4. Interface `BaseDMSAdapter` con métodos `read_parts()`, `read_stock()`, `read_sales()`, `read_purchase_orders()`. Cada DMS implementa su propia clase.

### 4.3 Deployment model — [DECIDED: 2026-08-08]

**Decisión**: **Render (PaaS) como default, con Docker Compose como fallback para VPS**

- **Render**: zero-ops para solo dev. Deploy con `git push` o botón. SSL, DB, logs incluidos. Plan gratis inicial.
- **Docker Compose (fallback)**: si Render no encaja (costos, latencia, compliance), un `Dockerfile` + `docker-compose.yml` corre el sistema en cualquier VPS (DigitalOcean, Hetzner, etc.). El proyecto incluye ambos setups.
- **Self-hosted en infra del tenant**: queda para v2+ (cuando haya un cliente con infra específica).

**Razón**: Render minimiza la carga operacional para un solo dev. Docker fallback cubre el caso "necesito correrlo en mi propia infra".

### 4.4 Database — [DECIDED: 2026-08-08]

**Decisión**: **PostgreSQL 16+**

**Razones**:
- JSONB para `sector-configuration` (key-value flexible)
- Window functions para weighted velocity calculation
- Arrays y enums nativos (útil para Volume Class / Lifecycle Stage codes)
- Mature replication y backup
- Default choice; ninguna razón para desviarse

**SQLite descartado**: no escala concurrent writes, no tiene JSONB/window function parity con Postgres.

**Opciones**:
- PostgreSQL (estándar, full-featured)
- MySQL/MariaDB (también full-featured, ligeramente más simple)
- SQLite (solo dev/local, no recomendado para prod)

**Status**: pendiente.

### 4.5 Background jobs / scheduling — [DECIDED: 2026-08-08]

**Decisión**: **Django-Q2 + Redis**

- **Django-Q2**: scheduler y task queue específico para Django. Menos overhead que Celery para un solo dev.
- **Redis**: broker para producción. En dev, Django-Q2 puede usar la DB como broker (no requiere Redis corriendo).
- **Jobs definidos**:
  - `replenishment_run` (per branch, per schedule)
  - `classification_pass` (periodic, monthly)
  - `notification_dispatch` (envía notificaciones pendientes)
  - `audit_log_cleanup` (opcional, para retención)

**Idempotencia**: cada job tiene un lock-key para evitar ejecuciones concurrentes duplicadas.

**Migración futura**: si el volumen de jobs crece mucho (cientos de branches, miles de SKUs), migrar a Celery en v1.5. Es un swap relativamente limpio porque ambos usan Python.

### 4.6 Authentication — [DECIDED: 2026-08-08]

**Decisión**: **Django sessions + django-allauth (email + password)**, OAuth como v2+

- **Sessions server-side**: cookies firmadas, simple para server-rendered UI. Más seguro y simple que JWT para v1.
- **allauth**: maneja email verification, password reset, invite flow, social accounts (preparado para OAuth futuro).
- **Password hashing**: PBKDF2 por default de Django (configurable a Argon2).
- **Multi-role**: union de permisos (no exclusivo). Audit log registra qué rol usó en cada acción.
- **OAuth (Google/Microsoft)**: deferred a v2. El modelo de allauth lo soporta, solo hay que activarlo.

**Magic link**: descartado para v1 (anadiria complejidad al flujo de invitación; el admin invita por email con link normal).

### 4.7 Notifications — [DECIDED: 2026-08-08]

**Decisión**: **Django email + Anymail** (provider-agnostic)

- **Anymail**: unified API para SendGrid, Postmark, AWS SES, Mailgun. Swap via env var.
- **Provider específico**: se elige en implementación. Para Render, SendGrid o Postmark son los más fáciles de integrar. Para self-hosted, SMTP genérico.
- **Templates**:
  - Recommendation pending (branch manager)
  - Recommendation pending (coordinator, escalación)
  - Recommendation pending (gerente, cross-coordinator)
  - Partial fulfillment alert
  - Lifecycle transition request (gerente)
  - User invitation
  - Password reset
- **In-app dashboard**: además de email, el dashboard muestra notificaciones in-app.
- **Throttling**: digest por día en lugar de email individual por cada recomendación. Configurable.

### 4.8 Observability — [DECIDED: 2026-08-08]

**Decisión**:
- **Logs**: structlog (JSON estructurado a stdout). En Render, los logs van a su dashboard nativo. En VPS, journald o similar.
- **Error tracking**: Sentry (self-hosted o SaaS, decisión en implementación). Free tier de Sentry.io es suficiente para v1.
- **Métricas**: básicas via Django-debug-toolbar en dev, y un dashboard simple en admin (`/admin/`) con contadores (recommendations generated, approved, etc.) en prod. Prometheus + Grafana deferred a v1.5+.

---

## 5. Architecture

> Se llena a medida que la design phase progresa.

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

> Preguntas que la design phase tiene que resolver, o que se difieren a v2+.

### 6.1 Para design phase
- **Fórmula exacta de weighted velocity**: linear decay, exponential smoothing, custom weights per month
- **Default escalation thresholds**: industry-standard, configurable per tenant
- **Classification pass frequency**: separate job vs. parte del replenishment run
- **Cron schedule default**: ¿qué hora del día corre la scheduled job? ¿configurable per branch?
- **Lead time source**: ¿per-supplier config, per-product config, derivado de PO history?
- **Notification channels**: ¿email + in-app only, o también SMS/push?
- **Dashboard rendering**: ¿server-side rendering (templates) o SPA (React/Vue)?

### 6.2 Deferred to v2+
- Multi-tenant SaaS completo
- Multi-region deployment
- Self-service onboarding
- Automated seasonal adjustment
- Automated obsoletion detection (sin admin/gerente review)
- External supplier identification (sistema nombra proveedor específico)
- System-owned catalog enrichment
- Branch proximity metadata para transferencia optimization
- Advanced analytics (forecast accuracy, recommendation quality)
- Multi-level DCs (DC que depende de otro DC)
- Mobile app nativa

---

## 7. Decisions log (cronológico)

> Log cronológico de decisiones de diseño tomadas durante el desarrollo.

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-07-29 | Multi-sector scope, automotive default | Viabilidad comercial, mercado más amplio |
| 2026-07-29 | Remove LPR / Star Cooperation references | IP / trademark concerns para comercialización |
| 2026-07-29 | Adjust para desarrollo en solitario | First client declined; project continues con solo dev |
| 2026-07-29 | MVP-first approach (Phase 0 spike, Phase 1 MVP) | Reduce risk con mínima inversión inicial |
| 2026-07-29 | Create design brief (this file) | Living document para decisiones técnicas |
| 2026-08-08 | **Stack: Python 3.12+ / Django 5.1+ / PostgreSQL 16+** | Django admin (CRUD) + ecosystem maduro + solo-dev friendly. Ver design §1 |
| 2026-08-08 | **Database: PostgreSQL 16+** | JSONB, window functions, enums. Sin razón para desviarse |
| 2026-08-08 | **Background jobs: Django-Q2 + Redis** | Más ligero que Celery para solo dev. Migrable a Celery si crece |
| 2026-08-08 | **Auth: Django sessions + allauth (email/password)** | Simple para server-rendered. OAuth deferred a v2 |
| 2026-08-08 | **Notifications: Django email + Anymail (provider-agnostic)** | Swap de provider via env var. SendGrid/Postmark/SES/Mailgun |
| 2026-08-08 | **Frontend: Django templates + HTMX** | Server-rendered, sin JS build step. Pico.css para styling |
| 2026-08-08 | **Deployment: Render (default) o Docker Compose (fallback)** | Render zero-ops para solo dev. Docker para VPS |
| 2026-08-08 | **Observability: structlog + Sentry** | JSON logs + error tracking. Métricas básicas via admin |
| 2026-08-08 | **Architecture: Django monolith con service layer, 9 apps** | Una sola app Django, sin microservicios. Apps: core, accounts, branches, catalog, inventory, classification, replenishment, notifications, dashboard |
| 2026-08-08 | **Data model: 13 entidades principales** | Ver design §3. Cubre multi-tenant, multi-role, multi-coordinator, DC topology, state machine, audit log |
| 2026-08-08 | **Roadmap: Phase 0 spike (3-5 days) + Phase 1 MVP (10 weekly increments)** | Spike valida formulas antes de construir el Django app. Phase 1 prioriza por dependencias |
| 2026-08-08 | **Formula convention: adopt material interpretation (lead time INCLUDED in Planning Target)** | Spike found discrepancy: material example gives 37/47/12, proposal formula gave 30/36.67/5. User chose material's convention. Planning Target = (v/30) × (period + security + lead). PP = PT + lead_time_days (raw, matches material). **All 51 tests passing on updated formulas**. Spike validated end-to-end with 30 SKUs. |

---

## 8. MVP-first roadmap (de proposal §12)

> Recordatorio del approach recomendado. Actualizar a medida que se ejecuta.

- **Phase 0 (spike)** — Días, no meses. Script chico que hace el core flow end-to-end: lee un dataset pequeño → calcula Punto de Pedido → genera una recomendación → la muestra en consola o HTML simple. Valida la metodología con el developer como primer "user".
- **Phase 1 (v1 MVP)** — 2-3 meses. Scope completo de v1 pero con tooling simple, UI básica, features más importantes primero. Difiero el resto (analytics avanzado, multi-coordinator complejo, etc.) a v1.5 o v2.
- **Phase 2+ (v1 full + v2)** — Completo el v1 + agrego v2+ features + hardening para producción.

---

## 9. References

- **Proposal (canónica)**: `openspec/changes/automotive-stock-advisor/proposal.md` — source of truth para el QUÉ del sistema
- **Source material (interno)**: `docs/sources/Material_LPR_Basics_dia3.md` — Star Cooperation LPR Basics, día 3 (referencia interna; NO se cita en proposal comercial)
- **Engram memory**: project context, decisions, traceability por topic_key `stockadvice-v1/*` y `sdd/automotive-stock-advisor/*`

---

## 10. Conventions

- **Markdown** para este documento (legible en cualquier editor / visor).
- **Fechas** en formato ISO (YYYY-MM-DD).
- **Decisiones** se numeran: D-001, D-002, ... (cuando se formalicen)
- **Open questions** se numeran: Q-001, Q-002, ...
- **Cambios importantes** se marcan con `**Status**: DECIDED` o `**Status**: PENDING`.
