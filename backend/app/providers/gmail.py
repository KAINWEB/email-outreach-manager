from __future__ import annotations
import base64
import json
import time
from email.message import EmailMessage
from email.utils import formataddr
import httpx
from .base import EmailProvider, SendResult, PermanentProviderError, TemporaryProviderError
from ..config import settings
from ..security import decrypt_secret, encrypt_secret

GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"
TOKEN_URL = "https://oauth2.googleapis.com/token"
PROFILE_URL = "https://gmail.googleapis.com/gmail/v1/users/me/profile"
SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"


def build_raw_message(*, sender_email: str, sender_name: str, to_email: str, subject: str, message: str) -> str:
    mime = EmailMessage()
    mime["From"] = formataddr((sender_name, sender_email)) if sender_name else sender_email
    mime["To"] = to_email
    mime["Subject"] = subject
    mime.set_content(message)
    return base64.urlsafe_b64encode(mime.as_bytes()).decode()


class GmailApiProvider(EmailProvider):
    def __init__(self, account):
        if account is None:
            raise PermanentProviderError("Gmail provider requires a sender account")
        self.account = account

    def _load_tokens(self) -> dict:
        if not self.account.encrypted_credentials:
            raise PermanentProviderError("Gmail account is not connected. Complete OAuth first.")
        try:
            return json.loads(decrypt_secret(self.account.encrypted_credentials))
        except Exception as exc:
            raise PermanentProviderError(f"Cannot read Gmail OAuth credentials: {exc}") from exc

    async def _access_token(self) -> str:
        tokens = self._load_tokens()
        access_token = tokens.get("access_token")
        expires_at = float(tokens.get("expires_at") or 0)
        if access_token and expires_at > time.time() + 60:
            return access_token
        refresh_token = tokens.get("refresh_token")
        if not refresh_token:
            raise PermanentProviderError("Gmail OAuth refresh token is missing. Reconnect the account.")
        if not settings.google_client_id or not settings.google_client_secret:
            raise PermanentProviderError("GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET are not configured")
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(TOKEN_URL, data={
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            })
        if resp.status_code >= 500 or resp.status_code == 429:
            raise TemporaryProviderError(f"Google token endpoint temporary error: {resp.status_code}")
        if resp.status_code >= 400:
            raise PermanentProviderError(f"Google token refresh failed: {resp.status_code} {resp.text[:300]}")
        data = resp.json()
        tokens["access_token"] = data["access_token"]
        tokens["expires_at"] = time.time() + int(data.get("expires_in", 3600))
        if data.get("refresh_token"):
            tokens["refresh_token"] = data["refresh_token"]
        self.account.encrypted_credentials = encrypt_secret(json.dumps(tokens))
        return tokens["access_token"]

    async def check_connection(self) -> tuple[bool, str]:
        token = await self._access_token()
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(PROFILE_URL, headers={"Authorization": f"Bearer {token}"})
        if resp.status_code == 200:
            email = resp.json().get("emailAddress", "")
            return True, f"Connected as {email or self.account.email}"
        if resp.status_code >= 500 or resp.status_code == 429:
            raise TemporaryProviderError(f"Gmail temporary error: {resp.status_code}")
        raise PermanentProviderError(f"Gmail connection check failed: {resp.status_code} {resp.text[:300]}")

    async def send(self, *, sender_email: str, sender_name: str, to_email: str, subject: str, message: str) -> SendResult:
        token = await self._access_token()
        raw = build_raw_message(sender_email=sender_email, sender_name=sender_name, to_email=to_email, subject=subject, message=message)
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(SEND_URL, headers={"Authorization": f"Bearer {token}"}, json={"raw": raw})
        if resp.status_code == 429 or resp.status_code >= 500:
            raise TemporaryProviderError(f"Gmail temporary send error: {resp.status_code} {resp.text[:300]}")
        if resp.status_code >= 400:
            raise PermanentProviderError(f"Gmail send failed: {resp.status_code} {resp.text[:300]}")
        data = resp.json()
        message_id = str(data.get("id", "unknown"))
        return SendResult(provider_message_id=message_id, response=f"GMAIL_OK:{message_id}")
