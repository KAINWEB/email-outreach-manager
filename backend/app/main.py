from __future__ import annotations
import asyncio
import csv
import html
import json
import logging
import secrets
import shutil
import time
from datetime import timedelta, timezone
from urllib.parse import urlencode
from contextlib import asynccontextmanager
from pathlib import Path
from logging.handlers import RotatingFileHandler
from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from openpyxl import Workbook
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from .config import settings
from .db import Base, engine, get_db
from .models import Campaign, OAuthState, Recipient, SenderAccount, SendEvent, SendJob, SuppressionEntry, utcnow
from .providers.registry import get_provider
from .providers.gmail import GMAIL_SEND_SCOPE, PROFILE_URL, TOKEN_URL
from .security import encrypt_secret
from .schemas import CampaignCreate, CampaignOut, LaunchRequest, MappingRequest, RecipientOut, RecipientUpdate, SenderAccountCreate, SenderAccountOut, SenderAccountUpdate, SuppressionCreate
from .services.campaign_service import campaign_summary, queue_campaign
from .services.import_service import inspect_file, import_campaign, revalidate_recipient
from .worker import worker_loop

Path(settings.log_file).parent.mkdir(parents=True, exist_ok=True)
_log_format = logging.Formatter("%(asctime)s %(levelname)s %(name)s - %(message)s")
_console = logging.StreamHandler(); _console.setFormatter(_log_format)
_file = RotatingFileHandler(settings.log_file, maxBytes=2_000_000, backupCount=3, encoding="utf-8"); _file.setFormatter(_log_format)
logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO), handlers=[_console, _file])
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    stop_event = asyncio.Event()
    task = asyncio.create_task(worker_loop(stop_event))
    app.state.worker_stop = stop_event
    app.state.worker_task = task
    yield
    stop_event.set()
    await task


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.get("/api/health")
def health():
    return {"status": "ok", "provider_mode": "mock-first"}


@app.get("/api/dashboard")
def dashboard(db: Session = Depends(get_db)):
    today = __import__("datetime").date.today().isoformat()
    sent_today = db.scalar(select(func.coalesce(func.sum(SenderAccount.sent_today), 0)).where(SenderAccount.sent_today_date == today)) or 0
    success = db.scalar(select(func.count()).select_from(SendEvent).where(SendEvent.status == "SENT")) or 0
    errors = db.scalar(select(func.count()).select_from(SendEvent).where(SendEvent.status == "FAILED")) or 0
    queued = db.scalar(select(func.count()).select_from(Recipient).where(Recipient.status == "QUEUED")) or 0
    active = db.scalar(select(func.count()).select_from(Campaign).where(Campaign.status == "RUNNING")) or 0
    return {"sent_today": sent_today, "success": success, "errors": errors, "queued": queued, "active_campaigns": active}


@app.get("/api/accounts", response_model=list[SenderAccountOut])
def list_accounts(db: Session = Depends(get_db)):
    return db.scalars(select(SenderAccount).order_by(SenderAccount.id.desc())).all()


@app.post("/api/accounts", response_model=SenderAccountOut)
def create_account(payload: SenderAccountCreate, db: Session = Depends(get_db)):
    if payload.provider not in {"mock", "gmail"}:
        raise HTTPException(400, "Provider must be 'mock' or 'gmail'")
    status = "CONNECTED" if payload.provider == "mock" else "DISCONNECTED"
    account = SenderAccount(**payload.model_dump(), connection_status=status, sent_today_date=__import__("datetime").date.today().isoformat())
    db.add(account)
    try:
        db.commit(); db.refresh(account)
    except Exception as exc:
        db.rollback(); raise HTTPException(400, str(exc))
    return account


@app.patch("/api/accounts/{account_id}", response_model=SenderAccountOut)
def update_account(account_id: int, payload: SenderAccountUpdate, db: Session = Depends(get_db)):
    account = db.get(SenderAccount, account_id)
    if not account:
        raise HTTPException(404, "Account not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(account, key, value)
    db.commit(); db.refresh(account)
    return account


@app.post("/api/accounts/{account_id}/check")
async def check_account(account_id: int, db: Session = Depends(get_db)):
    account = db.get(SenderAccount, account_id)
    if not account: raise HTTPException(404, "Account not found")
    try:
        ok, msg = await get_provider(account.provider, account).check_connection()
        account.connection_status = "CONNECTED" if ok else "ERROR"
        account.last_error = None if ok else msg
        db.commit()
        return {"ok": ok, "message": msg}
    except Exception as exc:
        account.connection_status = "ERROR"; account.last_error = str(exc); db.commit()
        raise HTTPException(400, str(exc))


@app.post("/api/accounts/{account_id}/toggle", response_model=SenderAccountOut)
def toggle_account(account_id: int, db: Session = Depends(get_db)):
    account = db.get(SenderAccount, account_id)
    if not account: raise HTTPException(404, "Account not found")
    account.enabled = not account.enabled
    db.commit(); db.refresh(account)
    return account


@app.post("/api/accounts/{account_id}/oauth/gmail/start")
def gmail_oauth_start(account_id: int, db: Session = Depends(get_db)):
    account = db.get(SenderAccount, account_id)
    if not account:
        raise HTTPException(404, "Account not found")
    if account.provider != "gmail":
        raise HTTPException(400, "This account is not a Gmail provider account")
    if not settings.email_outreach_secret_key:
        raise HTTPException(400, "EMAIL_OUTREACH_SECRET_KEY is not configured")
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(400, "GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be configured in backend/.env")
    token = secrets.token_urlsafe(32)
    db.add(OAuthState(token=token, provider="gmail", sender_account_id=account.id, expires_at=utcnow() + timedelta(minutes=10)))
    db.commit()
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": GMAIL_SEND_SCOPE,
        "access_type": "offline",
        "include_granted_scopes": "true",
        "prompt": "consent",
        "state": token,
    }
    return {"authorization_url": "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)}


@app.get("/api/oauth/gmail/callback", response_class=HTMLResponse)
async def gmail_oauth_callback(code: str | None = None, state: str | None = None, error: str | None = None, db: Session = Depends(get_db)):
    if error:
        return HTMLResponse(f"<h2>Gmail OAuth was not completed</h2><p>{html.escape(error)}</p>", status_code=400)
    if not code or not state:
        return HTMLResponse("<h2>Missing OAuth code/state</h2>", status_code=400)
    row = db.scalar(select(OAuthState).where(OAuthState.token == state, OAuthState.provider == "gmail"))
    if not row or row.used or (row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=timezone.utc)) < utcnow():
        return HTMLResponse("<h2>Invalid or expired OAuth state</h2>", status_code=400)
    account = db.get(SenderAccount, row.sender_account_id)
    if not account:
        return HTMLResponse("<h2>Sender account no longer exists</h2>", status_code=400)
    async with __import__('httpx').AsyncClient(timeout=20) as client:
        token_resp = await client.post(TOKEN_URL, data={
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": settings.google_redirect_uri,
        })
    if token_resp.status_code >= 400:
        account.connection_status = "ERROR"
        account.last_error = f"OAuth token exchange failed: {token_resp.status_code}"
        db.commit()
        return HTMLResponse("<h2>Google token exchange failed</h2><p>Check backend logs and OAuth settings.</p>", status_code=400)
    tokens = token_resp.json()
    if not tokens.get("refresh_token") and account.encrypted_credentials:
        try:
            from .security import decrypt_secret
            old = json.loads(decrypt_secret(account.encrypted_credentials))
            tokens["refresh_token"] = old.get("refresh_token")
        except Exception:
            pass
    tokens["expires_at"] = time.time() + int(tokens.get("expires_in", 3600))
    access_token = tokens.get("access_token")
    async with __import__('httpx').AsyncClient(timeout=20) as client:
        profile = await client.get(PROFILE_URL, headers={"Authorization": f"Bearer {access_token}"})
    if profile.status_code != 200:
        return HTMLResponse("<h2>Could not verify Gmail profile</h2>", status_code=400)
    connected_email = profile.json().get("emailAddress", "").lower()
    if connected_email and connected_email != account.email.lower():
        return HTMLResponse(f"<h2>Wrong Gmail account</h2><p>Expected {html.escape(account.email)}, connected {html.escape(connected_email)}.</p>", status_code=400)
    try:
        account.encrypted_credentials = encrypt_secret(json.dumps(tokens))
    except Exception as exc:
        return HTMLResponse(f"<h2>Could not encrypt OAuth credentials</h2><p>{html.escape(str(exc))}</p>", status_code=500)
    account.connection_status = "CONNECTED"
    account.last_error = None
    row.used = True
    db.commit()
    return HTMLResponse("<h2>Gmail connected</h2><p>You can close this tab and return to Email Outreach Manager.</p>")


@app.get("/api/campaigns", response_model=list[CampaignOut])
def list_campaigns(db: Session = Depends(get_db)):
    return db.scalars(select(Campaign).order_by(Campaign.id.desc())).all()


@app.post("/api/campaigns", response_model=CampaignOut)
def create_campaign(payload: CampaignCreate, db: Session = Depends(get_db)):
    campaign = Campaign(name=payload.name)
    db.add(campaign); db.commit(); db.refresh(campaign)
    return campaign


@app.get("/api/campaigns/{campaign_id}/summary")
def get_campaign_summary(campaign_id: int, db: Session = Depends(get_db)):
    if not db.get(Campaign, campaign_id): raise HTTPException(404, "Campaign not found")
    return campaign_summary(db, campaign_id)


@app.post("/api/campaigns/{campaign_id}/upload")
async def upload_campaign_file(campaign_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    campaign = db.get(Campaign, campaign_id)
    if not campaign: raise HTTPException(404, "Campaign not found")
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".xlsx", ".csv"}: raise HTTPException(400, "Only .xlsx and .csv are supported")
    safe_name = f"campaign_{campaign_id}{suffix}"
    destination = Path(settings.upload_dir) / safe_name
    with destination.open("wb") as out:
        shutil.copyfileobj(file.file, out)
    campaign.source_filename = file.filename
    campaign.source_path = str(destination)
    campaign.status = "MAPPING"
    db.commit()
    try:
        return inspect_file(str(destination))
    except Exception as exc:
        raise HTTPException(400, f"Cannot inspect file: {exc}")


@app.post("/api/campaigns/{campaign_id}/import")
def run_import(campaign_id: int, payload: MappingRequest, db: Session = Depends(get_db)):
    campaign = db.get(Campaign, campaign_id)
    if not campaign: raise HTTPException(404, "Campaign not found")
    if db.scalar(select(func.count()).select_from(SendJob).where(SendJob.campaign_id == campaign_id)):
        raise HTTPException(400, "Cannot re-import a campaign after test/send jobs exist. Create a new campaign instead.")
    try:
        return import_campaign(db, campaign, payload.mapping)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@app.get("/api/campaigns/{campaign_id}/recipients", response_model=list[RecipientOut])
def list_recipients(campaign_id: int, status: str | None = None, db: Session = Depends(get_db)):
    stmt = select(Recipient).where(Recipient.campaign_id == campaign_id).order_by(Recipient.row_number)
    if status: stmt = stmt.where(Recipient.status == status)
    return db.scalars(stmt).all()


@app.patch("/api/recipients/{recipient_id}", response_model=RecipientOut)
def edit_recipient(recipient_id: int, payload: RecipientUpdate, db: Session = Depends(get_db)):
    recipient = db.get(Recipient, recipient_id)
    if not recipient: raise HTTPException(404, "Recipient not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(recipient, key, value)
    return revalidate_recipient(db, recipient)


@app.post("/api/campaigns/{campaign_id}/launch")
def launch_campaign(campaign_id: int, payload: LaunchRequest, db: Session = Depends(get_db)):
    if not payload.confirmed: raise HTTPException(400, "Manual confirmation is required")
    campaign = db.get(Campaign, campaign_id)
    if not campaign: raise HTTPException(404, "Campaign not found")
    try:
        return queue_campaign(db, campaign, payload.sender_account_ids, test_mode=payload.test_mode, test_addresses=[str(x) for x in payload.test_addresses])
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@app.get("/api/history")
def history(status: str | None = Query(default=None), db: Session = Depends(get_db)):
    results = []
    if status not in {"SKIPPED", "UNSUBSCRIBED"}:
        stmt = select(SendEvent, Campaign.name, Recipient.email, SenderAccount.email).join(Campaign, Campaign.id == SendEvent.campaign_id).join(Recipient, Recipient.id == SendEvent.recipient_id).join(SenderAccount, SenderAccount.id == SendEvent.sender_account_id).order_by(SendEvent.timestamp.desc()).limit(1000)
        if status:
            stmt = stmt.where(SendEvent.status == status)
        for ev, cname, remail, semail in db.execute(stmt).all():
            results.append({"id": f"event-{ev.id}", "timestamp": ev.timestamp, "campaign": cname, "recipient": remail, "sender": semail, "subject": ev.subject, "status": ev.status, "provider_response": ev.provider_response})
    if status in {None, "SKIPPED", "UNSUBSCRIBED"}:
        stmt = select(Recipient, Campaign.name, Campaign.created_at).join(Campaign, Campaign.id == Recipient.campaign_id).where(Recipient.status.in_(["SKIPPED", "UNSUBSCRIBED"]))
        if status:
            stmt = stmt.where(Recipient.status == status)
        for recipient, cname, created_at in db.execute(stmt).all():
            results.append({"id": f"recipient-{recipient.id}", "timestamp": created_at, "campaign": cname, "recipient": recipient.email, "sender": None, "subject": recipient.subject, "status": recipient.status, "provider_response": recipient.validation_error})
    results.sort(key=lambda x: x["timestamp"], reverse=True)
    return results[:1000]


@app.get("/api/suppressions")
def list_suppressions(db: Session = Depends(get_db)):
    rows = db.scalars(select(SuppressionEntry).order_by(SuppressionEntry.id.desc())).all()
    return [{"id": x.id, "email": x.email, "reason": x.reason, "created_at": x.created_at} for x in rows]


@app.post("/api/suppressions")
def add_suppression(payload: SuppressionCreate, db: Session = Depends(get_db)):
    email = str(payload.email).lower()
    existing = db.scalar(select(SuppressionEntry).where(SuppressionEntry.email == email))
    if existing: return {"id": existing.id, "email": existing.email, "reason": existing.reason, "created_at": existing.created_at}
    row = SuppressionEntry(email=email, reason=payload.reason)
    db.add(row); db.commit(); db.refresh(row)
    return {"id": row.id, "email": row.email, "reason": row.reason, "created_at": row.created_at}


@app.delete("/api/suppressions/{entry_id}")
def delete_suppression(entry_id: int, db: Session = Depends(get_db)):
    row = db.get(SuppressionEntry, entry_id)
    if not row: raise HTTPException(404, "Suppression not found")
    db.delete(row); db.commit(); return {"deleted": True}


@app.get("/api/campaigns/{campaign_id}/export/{fmt}")
def export_campaign(campaign_id: int, fmt: str, db: Session = Depends(get_db)):
    campaign = db.get(Campaign, campaign_id)
    if not campaign: raise HTTPException(404, "Campaign not found")
    rows = db.scalars(select(Recipient).where(Recipient.campaign_id == campaign_id).order_by(Recipient.row_number)).all()
    fields = ["email", "company", "name", "subject", "message", "status", "validation_error", "sender_account_id"]
    if fmt == "csv":
        path = Path(settings.export_dir) / f"campaign_{campaign_id}_results.csv"
        with path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields); writer.writeheader()
            for r in rows: writer.writerow({k: getattr(r, k) for k in fields})
        return FileResponse(path, filename=path.name)
    if fmt == "xlsx":
        path = Path(settings.export_dir) / f"campaign_{campaign_id}_results.xlsx"
        wb = Workbook(); ws = wb.active; ws.title = "Results"; ws.append(fields)
        for r in rows: ws.append([getattr(r, k) for k in fields])
        wb.save(path)
        return FileResponse(path, filename=path.name)
    raise HTTPException(400, "Format must be csv or xlsx")

# Production/EXE frontend: Vite build is copied into app/static by the Windows build workflow.
from fastapi.staticfiles import StaticFiles
_static_dir = Path(__file__).resolve().parent / "static"
if _static_dir.exists():
    app.mount("/", StaticFiles(directory=str(_static_dir), html=True), name="frontend")
