"""Quick health check for DealFrame backend + frontend proxy."""
import urllib.request
import json

BASE = "http://localhost:8000"
PROXY = "http://localhost:3000"

checks = [
    ("Health", f"{BASE}/health"),
    ("Jobs", f"{BASE}/api/v1/jobs"),
    ("Objections", f"{BASE}/api/v1/intelligence/objections"),
    ("Risk Summary", f"{BASE}/api/v1/intelligence/risk/summary"),
    ("Coaching", f"{BASE}/api/v1/agents/coaching"),
    ("Proxy→Jobs", f"{PROXY}/api/v1/jobs"),
]

for name, url in checks:
    try:
        data = json.loads(urllib.request.urlopen(url, timeout=5).read())
        if "health" in url:
            print(f"  OK  {name}: {data.get('status')}")
        elif "jobs" in url.lower():
            print(f"  OK  {name}: {data.get('total', len(data))} jobs")
        elif "objections" in url:
            print(f"  OK  {name}: {len(data.get('objections', []))} objections")
        elif "risk" in url:
            print(f"  OK  {name}: {data['video_count']} videos, avg_risk={data['avg_risk_score']}")
        elif "coaching" in url:
            reps = data.get("reps", [])
            print(f"  OK  {name}: {len(reps)} reps")
        else:
            print(f"  OK  {name}")
    except Exception as e:
        print(f"  FAIL  {name}: {e}")
