"""Quick verification of the YouTube seed data generation."""
import sys
sys.path.insert(0, ".")

from scripts.seed_youtube_demo import generate_youtube_seed

data = generate_youtube_seed()
print(f"Generated {data['total']} demo jobs:\n")

for jid, j in data["jobs"].items():
    meta = j["_meta"]
    result = j["result"]
    segs = result["segments"]
    risk_scores = [s["extraction"]["risk_score"] for s in segs]
    avg_risk = sum(risk_scores) / len(risk_scores) if risk_scores else 0
    print(f"  {jid}: {meta['title'][:55]}")
    print(f"    company={meta['company']} | rep={meta['rep']} | segs={len(segs)} | risk={avg_risk:.2f}")

print("\nSegment sample from first job:")
first_job = list(data["jobs"].values())[0]
for s in first_job["result"]["segments"][:3]:
    ext = s["extraction"]
    print(f"  [{s['segment']['timestamp_ms']//1000}s] {ext['topic']} | {ext['sentiment']} | risk={ext['risk_score']} | obj={len(ext['objections'])} | sig={len(ext['decision_signals'])}")
