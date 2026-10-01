# Verification report

## Passed in this environment
- `python -m compileall -q app tests`
- `pytest -q`: **6 passed**
- FastAPI application startup
- `GET /api/health`: HTTP 200
- SQLite database initialization
- SQLite WAL / foreign-key / busy-timeout configuration loaded at runtime
- XLSX inspection and field auto-mapping
- XLSX import with individualized subject/message
- Invalid email detection
- In-campaign duplicate detection
- Suppression detection during import
- Suppression re-check after queueing and immediately before send
- Semicolon-delimited cp1251 CSV inspection
- Mock sender account creation and connection check
- Campaign creation
- Test Mode queueing to a user-owned override address
- Test Mode does not overwrite or consume the real lead recipient
- Real queue after Test Mode
- Background worker processing
- SENT history event generation
- CSV/XLSX result export
- Gmail MIME/base64url message generation unit test
- Gmail account can be created as DISCONNECTED; OAuth start correctly refuses to proceed until local Google client credentials are configured
- Rotating file logging writes to the data directory

## Live smoke-test result
A two-row XLSX was uploaded and imported. One Test Mode job was simulated to `owner@example.com`; both real recipients remained `READY`. A subsequent real (Mock provider) launch queued both recipients and both finished as `SENT`.

## Not executable in this sandbox
`npm install` / Vite build could not be completed because this execution environment cannot reach the npm registry (DNS/network access is unavailable). The React/Vite project and pinned dependencies are included. Run `npm install && npm run dev` on a normal Windows machine with internet access for the first dependency install.

No real external email was sent during verification.
