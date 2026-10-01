import subprocess,time,urllib.request,json,sys
p=subprocess.Popen(["dist/EmailOutreachManager/EmailOutreachManager.exe"]);time.sleep(10)
ok=False
try:
 def get(path):
  r=urllib.request.urlopen("http://127.0.0.1:8000"+path,timeout=5);return r.getcode(),r.read().decode("utf-8",errors="ignore")
 h,b=get("/api/health"); root,html=get("/"); d,db=get("/api/dashboard"); s,sb=get("/api/senders"); c,cb=get("/api/campaigns"); r,rb=get("/api/recipients"); l,lb=get("/api/logs"); x,xb=get("/api/suppression")
 ok=all(v==200 for v in [h,root,d,s,c,r,l,x]) and "GROWER" in html and "Кампании" in html and json.loads(db)["senders"]>=0
except Exception as e: print("SMOKE ERROR",e)
p.terminate();sys.exit(0 if ok else 1)
