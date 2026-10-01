# Email Outreach Manager

Local MVP for importing individualized outreach emails from XLSX/CSV, validating recipients, safely queueing sends, and tracking results.

The MVP ships with a **Mock** provider for safe development and an optional **Gmail API OAuth** provider for real sending from your own Gmail account. Microsoft Graph can be added later behind the same provider interface.

## Features
- Campaigns and recipient-level individualized subject/message
- XLSX/CSV upload, column inspection and manual field mapping
- Email validation, duplicate detection, suppression list, missing-text checks
- Editable recipients before sending
- Multiple sender accounts with daily/rate limits
- SQLite-backed queue with retry/backoff and provider abstraction
- Test Mode that redirects selected messages to addresses you own **without consuming/changing the real lead**
- Dashboard, history, suppression list, CSV/XLSX exports
- FastAPI backend + React/Vite frontend
- Optional Gmail API OAuth connection; no mailbox passwords stored

## Quick start (Windows, PowerShell)
See `WINDOWS_SETUP.md`.
