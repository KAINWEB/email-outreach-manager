import os, sys, logging, traceback, webbrowser, threading, time
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from backend.database import engine, Base
from backend.worker import QueueWorker

BASE_DIR = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(BASE_DIR)
os.makedirs("data", exist_ok=True)
logging.basicConfig(filename=os.path.join("data", "startup-error.log"), level=logging.ERROR)
app = FastAPI(title="Email Outreach Manager MVP")

@app.get("/api/health")
def health_check():
    return {"status": "ok", "version": "1.0.0"}

ui_path = os.path.join(getattr(sys, "_MEIPASS", BASE_DIR), "frontend_dist")
if os.path.exists(ui_path):
    assets = os.path.join(ui_path, "assets")
    if os.path.isdir(assets):
        app.mount("/assets", StaticFiles(directory=assets), name="assets")
    @app.get("/{full_path:path}")
    def serve_react_app(full_path: str):
        requested = os.path.join(ui_path, full_path)
        if full_path and os.path.isfile(requested):
            return FileResponse(requested)
        return FileResponse(os.path.join(ui_path, "index.html"))

worker = None
@app.on_event("startup")
def startup_event():
    try:
        Base.metadata.create_all(bind=engine)
        global worker
        worker = QueueWorker(); worker.start()
        if getattr(sys, 'frozen', False):
            threading.Thread(target=lambda: (time.sleep(1.5), webbrowser.open("http://127.0.0.1:8000")), daemon=True).start()
    except Exception:
        logging.error(traceback.format_exc()); raise

@app.on_event("shutdown")
def shutdown_event():
    if worker:
        worker.stop(); worker.join(timeout=5)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
