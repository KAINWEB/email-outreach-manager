# Technical plan

## Goal
A single-user local Windows MVP for campaign-based, recipient-specific email outreach. Reliability and provider-limit compliance take precedence over throughput.

## Architecture
- **Frontend:** React + Vite SPA. Dashboard, campaign wizard, accounts, recipients, history, suppressions, settings.
- **API:** FastAPI. Thin HTTP layer over isolated services.
- **Database:** SQLite + SQLAlchemy. A future PostgreSQL migration remains possible because business logic does not use raw SQLite-only SQL.
- **ImportService:** XLSX/CSV inspection, field mapping, validation, duplicate detection, suppression checks.
- **CampaignService:** campaign state, sender selection, safe confirmation, Test Mode, durable job creation.
- **Queue/Worker:** durable `SendJob` rows in SQLite and one local async worker. Rate/daily limits are checked before sends; retries are bounded and use exponential backoff.
- **EmailProvider:** provider interface with Mock plus Gmail API/OAuth implementation. Microsoft Graph can be added behind the same interface later.
- **Secrets:** no mailbox passwords. Future OAuth credentials are encrypted at rest with a Fernet key supplied through environment configuration.

## Core safety invariants
1. The subject/body come from each recipient row; no broadcast template substitution is performed.
2. A suppressed address is checked during import, queueing, and immediately before provider send.
3. Test Mode redirects only the provider target and never mutates/consumes the real lead record.
4. A campaign needs explicit `confirmed=true` before real jobs are queued.
5. Daily/rate limits are never bypassed.
6. Retries are bounded; permanent failures are not retried.

## MVP boundaries
- Gmail OAuth sending is implemented but requires the user's own Google Cloud OAuth client; Microsoft Graph is not implemented yet.
- Single local worker / single user.
- Automatic unsubscribe ingestion and reply processing are extension points, not implemented in v0.1.
