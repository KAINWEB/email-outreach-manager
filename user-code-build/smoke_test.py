import subprocess,time,urllib.request,json,sys,os
p=subprocess.Popen(["dist/EmailOutreachManager/EmailOutreachManager.exe"]);time.sleep(10)
ok=False
try:
 def get(path):
  r=urllib.request.urlopen("http://127.0.0.1:8000"+path,timeout=5);return r.getcode(),r.read().decode("utf-8",errors="ignore")
 h,b=get("/api/health"); root,html=get("/"); d,db=get("/api/dashboard"); s,sb=get("/api/senders"); c,cb=get("/api/campaigns"); r,rb=get("/api/recipients"); l,lb=get("/api/logs"); x,xb=get("/api/suppression")
 packaged=os.path.join("dist","EmailOutreachManager","_internal","frontend_dist","index.html")
 packaged_html=open(packaged,encoding="utf-8").read()
 ok=all(v==200 for v in [h,root,d,s,c,r,l,x]) and "GROWER TEAM" in html and "Кампании" in html and "GROWER TEAM" in packaged_html and "Email Outreach Manager (MVP)" not in packaged_html and json.loads(db)["senders"]>=0
 print("ROOT_HAS_GROWER", "GROWER TEAM" in html)
 print("PACKAGED_HAS_GROWER", "GROWER TEAM" in packaged_html)
 print("PACKAGED_HAS_OLD_MVP", "Email Outreach Manager (MVP)" in packaged_html)
except Exception as e: print("SMOKE ERROR",repr(e))
p.terminate();sys.exit(0 if ok else 1)
