import subprocess, time, urllib.request, sys
print("Starting EXE...")
process = subprocess.Popen(["dist/EmailOutreachManager/EmailOutreachManager.exe"])
time.sleep(10)
try:
    response = urllib.request.urlopen("http://127.0.0.1:8000/api/health", timeout=5)
    ok = response.getcode() == 200
except Exception:
    ok = False
process.terminate()
sys.exit(0 if ok else 1)
