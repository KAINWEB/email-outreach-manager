from dataclasses import dataclass
from abc import ABC, abstractmethod


class TemporaryProviderError(Exception):
    pass


class PermanentProviderError(Exception):
    pass


@dataclass
class SendResult:
    provider_message_id: str
    response: str


class EmailProvider(ABC):
    @abstractmethod
    async def check_connection(self) -> tuple[bool, str]:
        raise NotImplementedError

    @abstractmethod
    async def send(self, *, sender_email: str, sender_name: str, to_email: str, subject: str, message: str) -> SendResult:
        raise NotImplementedError
