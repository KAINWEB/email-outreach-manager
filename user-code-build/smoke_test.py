import subprocess, time, urllib.request, sys
print("Starting EXE...")
process = subprocess.Popen(["dist/EmailOutreachManager/EmailOutreachManager.exe"])
time.sleep(10)
try:
    health = urllib.request.urlopen("http://127.0.0.1:8000/api/health", timeout=5)
    root = urllib.request.urlopen("http://127.0.0.1:8000/", timeout=5)
    body = root.read().decode("utf-8", errors="ignore")
    ok = health.getcode() == 200 and root.getcode() == 200 and "Email Outreach Manager" in body
except Exception as e:
    print(e); ok = False
process.terminate()
sys.exit(0 if ok else 1)
