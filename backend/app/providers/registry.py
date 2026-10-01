from .base import EmailProvider
from .mock import MockEmailProvider
from .gmail import GmailApiProvider


def get_provider(name: str, account=None) -> EmailProvider:
    if name == "mock":
        return MockEmailProvider()
    if name == "gmail":
        return GmailApiProvider(account)
    raise ValueError(f"Provider '{name}' is not implemented in this MVP")
