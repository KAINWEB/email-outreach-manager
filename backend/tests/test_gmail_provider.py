import base64
from email import policy
from email.parser import BytesParser
from app.providers.gmail import build_raw_message


def test_build_raw_gmail_message_is_individualized():
    raw = build_raw_message(sender_email="sender@gmail.com", sender_name="Evgeniy", to_email="lead@example.com", subject="Offer for Company A", message="Individual body A")
    msg = BytesParser(policy=policy.default).parsebytes(base64.urlsafe_b64decode(raw.encode()))
    assert msg["To"] == "lead@example.com"
    assert msg["Subject"] == "Offer for Company A"
    assert "Individual body A" in msg.get_content()
