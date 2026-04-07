"""Quick API smoke test — hit all major endpoints and report status."""
import urllib.request
import json
import sys

BASE = "http://localhost:8000"

endpoints = [
    # Core
    ("GET", "/health"),
    ("GET", "/health/ready"),
    ("GET", "/health/live"),
    ("GET", "/docs"),
    ("GET", "/openapi.json"),
    # Processing
    ("GET", "/api/v1/jobs"),
    # Search
    ("GET", "/api/v1/search?q=test"),
    ("GET", "/api/v1/search/index/stats"),
    ("GET", "/api/v1/search/insights/patterns"),
    ("GET", "/api/v1/search/insights/reps"),
    ("GET", "/api/v1/search/insights/velocity"),
    # Intelligence
    ("GET", "/api/v1/intelligence/objections"),
    ("GET", "/api/v1/intelligence/topics/trend"),
    ("GET", "/api/v1/intelligence/risk/summary"),
    # Schemas
    ("GET", "/api/v1/schemas"),
    # Webhooks
    ("GET", "/api/v1/webhooks"),
    ("GET", "/api/v1/webhooks/events/types"),
    # Auth (expects 401)
    ("GET", "/api/v1/auth/me"),
    # Notifications
    ("GET", "/api/v1/notifications"),
    # Audit
    ("GET", "/api/v1/audit"),
    ("GET", "/api/v1/audit/stats"),
    # Admin
    ("GET", "/api/v1/admin/tenants"),
    ("GET", "/api/v1/admin/users"),
    ("GET", "/api/v1/admin/settings"),
    ("GET", "/api/v1/admin/stats"),
    ("GET", "/api/v1/admin/roles"),
    # Patterns
    ("GET", "/api/v1/patterns"),
    ("GET", "/api/v1/patterns/summary"),
    # Metrics
    ("GET", "/api/v1/metrics"),
    # Observability
    ("GET", "/api/v1/observability/drift"),
    # Observatory
    ("GET", "/api/v1/observatory/sessions"),
    # Fine-tuning
    ("GET", "/api/v1/finetuning/runs"),
    ("GET", "/api/v1/finetuning/best"),
    ("GET", "/api/v1/finetuning/dataset/stats"),
    # Copilot
    ("GET", "/api/v1/copilot/config"),
    # Local SLM
    ("GET", "/api/v1/local/status"),
    # Batch
    ("GET", "/api/v1/batch"),
    # Summary types
    ("GET", "/api/v1/summaries/types/list"),
    # Diff engine
    ("GET", "/api/v1/diff/jobs"),
    # Active Learning
    ("GET", "/api/v1/active-learning/queue"),
    ("GET", "/api/v1/active-learning/metrics"),
    # Review
    ("GET", "/api/v1/review/queue"),
]

ok = 0
fail = 0
for method, path in endpoints:
    url = f"{BASE}{path}"
    try:
        r = urllib.request.urlopen(url, timeout=5)
        body = r.read().decode()[:100]
        print(f"  ✓ {method} {path} → {r.status}")
        ok += 1
    except urllib.error.HTTPError as e:
        code = e.code
        body = ""
        try:
            body = e.read().decode()[:80]
        except Exception:
            pass
        if code in (401, 403):
            print(f"  ⚠ {method} {path} → {code} (auth required)")
            ok += 1
        else:
            print(f"  ✗ {method} {path} → {code} | {body}")
            fail += 1
    except Exception as e:
        print(f"  ✗ {method} {path} → ERROR: {e}")
        fail += 1

print(f"\n{'='*50}")
print(f"Results: {ok} OK, {fail} FAILED out of {len(endpoints)} endpoints")

# Test POST /api/v1/process with a dummy (expects file upload)
try:
    req = urllib.request.Request(f"{BASE}/api/v1/process", method="POST")
    urllib.request.urlopen(req, timeout=5)
except urllib.error.HTTPError as e:
    if e.code == 422:
        print(f"  ✓ POST /api/v1/process → 422 (validation error, as expected without file)")
        ok += 1
    else:
        print(f"  ✗ POST /api/v1/process → {e.code}")
        fail += 1
except Exception as e:
    print(f"  ℹ POST /api/v1/process → {e}")

print(f"\nFinal: {ok} OK, {fail} FAILED")
sys.exit(1 if fail > 0 else 0)
