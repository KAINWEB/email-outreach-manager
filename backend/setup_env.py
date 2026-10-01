from pathlib import Path
from cryptography.fernet import Fernet

p = Path(__file__).with_name(".env")
example = Path(__file__).with_name(".env.example")
if not p.exists():
    p.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
text = p.read_text(encoding="utf-8")
lines=[]
found=False
for line in text.splitlines():
    if line.startswith("EMAIL_OUTREACH_SECRET_KEY="):
        found=True
        if line.strip() == "EMAIL_OUTREACH_SECRET_KEY=":
            line = "EMAIL_OUTREACH_SECRET_KEY=" + Fernet.generate_key().decode()
    lines.append(line)
if not found:
    lines.append("EMAIL_OUTREACH_SECRET_KEY=" + Fernet.generate_key().decode())
p.write_text("\n".join(lines)+"\n", encoding="utf-8")
print("backend/.env is ready")
