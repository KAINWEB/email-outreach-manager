from cryptography.fernet import Fernet, InvalidToken
from .config import settings


def _fernet() -> Fernet:
    if not settings.email_outreach_secret_key:
        raise RuntimeError("EMAIL_OUTREACH_SECRET_KEY is required before storing provider credentials")
    return Fernet(settings.email_outreach_secret_key.encode())


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt_secret(value: str) -> str:
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken as exc:
        raise RuntimeError("Unable to decrypt stored provider credentials") from exc
