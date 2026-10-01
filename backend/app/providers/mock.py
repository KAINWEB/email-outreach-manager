import asyncio
import uuid
from .base import EmailProvider, SendResult, PermanentProviderError, TemporaryProviderError


class MockEmailProvider(EmailProvider):
    async def check_connection(self) -> tuple[bool, str]:
        return True, "Mock provider is ready"

    async def send(self, *, sender_email: str, sender_name: str, to_email: str, subject: str, message: str) -> SendResult:
        await asyncio.sleep(0.03)
        lowered = to_email.lower()
        if "+tempfail" in lowered:
            raise TemporaryProviderError("Simulated temporary provider failure")
        if "+permfail" in lowered:
            raise PermanentProviderError("Simulated permanent provider rejection")
        msg_id = f"mock-{uuid.uuid4()}"
        return SendResult(provider_message_id=msg_id, response=f"SIMULATED_OK:{msg_id}")
