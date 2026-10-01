from __future__ import annotations
import os
import sys
import threading
import time
import traceback
import webbrowser
from pathlib import Path

def app_root() -> Path:
    return Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent

root = app_root()
os.chdir(root)
data_dir = root / "data"
(data_dir / "uploads").mkdir(parents=True, exist_ok=True)
(data_dir / "exports").mkdir(parents=True, exist_ok=True)
os.environ.setdefault("DATABASE_URL", f"sqlite:///{(data_dir / 'email_outreach.db').as_posix()}")
os.environ.setdefault("UPLOAD_DIR", str(data_dir / "uploads"))
os.environ.setdefault("EXPORT_DIR", str(data_dir / "exports"))
os.environ.setdefault("LOG_FILE", str(data_dir / "email_outreach.log"))

def open_ui() -> None:
    time.sleep(1.5)
    webbrowser.open("http://127.0.0.1:8000")

def write_crash(exc: BaseException) -> Path:
    path = data_dir / "startup-error.log"
    path.write_text("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)), encoding="utf-8")
    return path

if __name__ == "__main__":
    try:
        import uvicorn
        from app.main import app
        threading.Thread(target=open_ui, daemon=True).start()
        uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
    except BaseException as exc:
        path = write_crash(exc)
        print("\nEmail Outreach Manager could not start.")
        print(f"Diagnostic log: {path}")
        traceback.print_exc()
        try:
            input("\nPress Enter to close...")
        except EOFError:
            pass
        raise SystemExit(1)
