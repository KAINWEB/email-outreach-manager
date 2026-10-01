from __future__ import annotations
import os, sys, threading, time, webbrowser
from pathlib import Path

if getattr(sys, "frozen", False):
    root = Path(sys.executable).resolve().parent
    os.chdir(root)
    os.environ.setdefault("DATABASE_URL", f"sqlite:///{(root / 'data' / 'email_outreach.db').as_posix()}")
    os.environ.setdefault("UPLOAD_DIR", str(root / "data" / "uploads"))
    os.environ.setdefault("EXPORT_DIR", str(root / "data" / "exports"))
    os.environ.setdefault("LOG_FILE", str(root / "data" / "email_outreach.log"))
for folder in (Path("data/uploads"), Path("data/exports")):
    folder.mkdir(parents=True, exist_ok=True)
def open_ui():
    time.sleep(1.2)
    webbrowser.open("http://127.0.0.1:8000")
if __name__ == "__main__":
    import uvicorn
    threading.Thread(target=open_ui, daemon=True).start()
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, log_level="info")
