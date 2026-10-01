# Windows setup from zero

Prerequisites:
- Python 3.11+ (3.12 recommended)
- Node.js 20+

## 1. Backend
Open PowerShell in the project folder:

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python setup_env.py
python -m app.init_db
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Backend API: http://127.0.0.1:8000
Swagger: http://127.0.0.1:8000/docs

## 2. Frontend
Open a second PowerShell window:

```powershell
cd frontend
npm install
npm run dev
```

Open: http://127.0.0.1:5173

## 3. Tests
From `backend` with the venv activated:

```powershell
pytest -q
```

## First safe test
1. Open **Sender accounts** and create a Mock account.
2. Create a campaign.
3. Upload `backend/tests/fixtures/sample_leads.xlsx` if present, or your own XLSX/CSV.
4. Map the columns and import.
5. Review validation results.
6. In Test Mode enter only email addresses that belong to you.
7. Confirm and queue the campaign.
8. The Mock provider records a successful simulated send; it does not contact external email servers.

## Environment
`backend/.env.example` documents the settings. Do not commit real OAuth client secrets or access/refresh tokens.

## Optional: connect Gmail for real sending
1. In Google Cloud, enable the Gmail API.
2. Create an OAuth 2.0 **Web application** client.
3. Add this authorized redirect URI exactly: `http://127.0.0.1:8000/api/oauth/gmail/callback`.
4. Put the client ID and secret into `backend/.env` as `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`.
5. Restart the backend.
6. In **Sender accounts**, add the Gmail address with provider `gmail`, then click **OAuth** and complete Google's consent screen.

The app never asks for or stores the Gmail password. OAuth tokens are encrypted locally using `EMAIL_OUTREACH_SECRET_KEY`.
