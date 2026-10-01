@echo off
start "Email Outreach Backend" cmd /k "cd /d %~dp0backend && if not exist .venv (py -m venv .venv) && call .venv\Scripts\activate && pip install -r requirements.txt && python setup_env.py && python -m app.init_db && uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"
start "Email Outreach Frontend" cmd /k "cd /d %~dp0frontend && npm install && npm run dev"
