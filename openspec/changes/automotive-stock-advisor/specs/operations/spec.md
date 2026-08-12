# operations — Specification

## Purpose

Covers deployment, monitoring, logging, and basic system alerting for the system itself (not the inventory domain). v1 should be deployable on a single server or basic PaaS with minimal infrastructure. Multi-server, microservices, and complex orchestration are v2+.

## Requirements

### REQ-OP-001: Deployment
The system **shall** be deployable on Render (PaaS) as the default target, with Docker Compose as a fallback for single VPS deployment.

#### Scenario: Render deployment
- GIVEN a developer pushes to the main branch
- WHEN the CI/CD pipeline completes
- THEN Render auto-deploys the web service and worker service
- AND the PostgreSQL managed database is provisioned or connected

#### Scenario: Docker Compose deployment
- GIVEN a developer wants to deploy on a single VPS
- WHEN the developer runs `docker-compose up -d`
- THEN the app, worker, database, and Redis containers start
- AND the system is accessible on the configured port

### REQ-OP-002: Logging
The system **shall** produce structured JSON logs to stdout with fields: timestamp, level, logger, event, request_id, user_id, branch_id.

#### Scenario: Request logged
- GIVEN a user makes a request to the dashboard
- WHEN the request is processed
- THEN a log entry is written with: timestamp, level=INFO, event="request_completed", request_id, user_id, branch_id

#### Scenario: Error logged
- GIVEN an unhandled exception occurs
- WHEN the error is caught
- THEN a log entry is written with: level=ERROR, event="unhandled_exception", request_id, and the exception details

#### Scenario: Job execution logged
- GIVEN a replenishment run job starts
- WHEN the job begins execution
- THEN a log entry is written with: level=INFO, event="job_started", job_name="replenishment_run", branch_id

### REQ-OP-003: Error tracking
The system **shall** integrate with Sentry (or equivalent) for error tracking when configured via environment variable.

#### Scenario: Sentry integration active
- GIVEN SENTRY_DSN is configured
- WHEN an unhandled exception occurs
- THEN the error is reported to Sentry with stack trace, user context, and request data

#### Scenario: Sentry not configured
- GIVEN SENTRY_DSN is not set
- WHEN an unhandled exception occurs
- THEN the error is logged to stdout only
- AND no external service is contacted

### REQ-OP-004: Health check
The system **shall** expose a health check endpoint that returns the status of the web service, database connection, and task queue.

#### Scenario: Healthy system
- GIVEN all components are running normally
- WHEN a health check request is made
- THEN the response is HTTP 200 with status: {"web": "ok", "db": "ok", "queue": "ok"}

#### Scenario: Database connection lost
- GIVEN the database is unreachable
- WHEN a health check request is made
- THEN the response is HTTP 503 with status: {"web": "ok", "db": "error", "queue": "ok"}

### REQ-OP-005: Backup and recovery
The system **shall** support database backups with a target RPO of 1 hour and RTO of less than 4 hours.

#### Scenario: Managed backup (Render)
- GIVEN the system is deployed on Render
- WHEN a backup is needed
- THEN Render's managed PostgreSQL backup is used
- AND the latest backup can be restored via Render's dashboard

#### Scenario: Manual backup (VPS)
- GIVEN the system is deployed on a single VPS
- WHEN the backup cron runs
- THEN pg_dump creates a full backup
- AND the backup is stored in S3 or via rsync to a remote location

### REQ-OP-006: System alerting
The system **shall** alert on: job failure (3 consecutive failures), 500-rate spike, and database connection loss.

#### Scenario: Job failure alert
- GIVEN a scheduled job fails 3 consecutive times
- WHEN the third failure occurs
- THEN an alert is sent to the operations team
- AND the alert includes the job name, error message, and timestamp

#### Scenario: Database connection loss
- GIVEN the database becomes unreachable
- WHEN the health check detects the failure
- THEN an alert is sent to the operations team
- AND the system returns 503 for health check requests

### REQ-OP-007: CI/CD pipeline
The system **shall** include a CI/CD pipeline that runs linting (ruff), tests (pytest), and builds a Docker image on every push.

#### Scenario: CI pipeline on push
- GIVEN a developer pushes to the main branch
- WHEN the CI pipeline triggers
- THEN ruff linting runs
- AND pytest runs with the test suite
- AND a Docker image is built and pushed to the registry
- AND Render auto-deploys if all steps pass

#### Scenario: CI pipeline failure
- GIVEN a test fails in the CI pipeline
- WHEN the pipeline runs
- THEN the pipeline fails at the test step
- AND no Docker image is built
- AND no deployment occurs

### REQ-OP-008: Local development
The system **shall** support local development with a single command that starts all required services (app, database, worker).

#### Scenario: Local development setup
- GIVEN a developer clones the repository
- WHEN the developer runs `docker-compose up`
- THEN the app, database, Redis, and worker containers start
- AND the developer can access the app at localhost
- AND `make reset-db` resets the database to a clean state
- AND `make seed` populates demo data

## Edge cases

- Deployment with insufficient disk space (system should fail gracefully with clear error)
- Database backup fails (system should alert and retry)
- Health check endpoint itself fails (system should still log the failure)
- CI/CD pipeline times out (system should fail the build, not deploy partial code)
- Local development on a machine without Docker (system should provide a non-Docker alternative)
- Sentry rate limit exceeded (system should stop sending and log locally)
- Render service unavailable (system should failover to nothing — no automatic failover in v1)

## Acceptance criteria

- AC-1: System deploys on Render with zero manual configuration beyond environment variables
- AC-2: Docker Compose starts all services with a single command
- AC-3: Structured JSON logs include timestamp, level, event, request_id, user_id, branch_id
- AC-4: Health check endpoint returns status of web, db, and queue components
- AC-5: Database backup RPO ≤ 1 hour, RTO < 4 hours
- AC-6: Alerts fire on 3 consecutive job failures, 500-rate spike, or DB connection loss
- AC-7: CI/CD pipeline runs lint, test, and build on every push
- AC-8: Local development environment starts with one command

## Notes

- v1 deployment: single server or basic PaaS (Render)
- v2+: multi-server, microservices, Kubernetes (deferred)
- Logging: structlog → stdout (JSON structured)
- Error tracking: Sentry (optional, via SENTRY_DSN env var)
- Metrics: custom counters in DB (no Prometheus for v1)
