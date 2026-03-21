"""Demo seed generator — populates the system with realistic demo data.

Creates 5 companies, 8 reps, ~20 calls with full intelligence data.
Seeds: dashboard, coaching, risk alerts, KG, and Q&A index.
"""
from __future__ import annotations

import hashlib
import logging
import random
import time
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

COMPANIES = [
    {"name": "Acme Corp", "contact": "John Davis", "deal_id": "acme-2026"},
    {"name": "TechFlow Inc", "contact": "Sarah Chen", "deal_id": "techflow-q1"},
    {"name": "RetailMax", "contact": "Mike Johnson", "deal_id": "retailmax-ent"},
    {"name": "CloudSync", "contact": "Emily Park", "deal_id": "cloudsync-pro"},
    {"name": "DataVault", "contact": "Alex Rivera", "deal_id": "datavault-pilot"},
]

REPS = ["Alice Wong", "Bob Martin", "Carol Lee", "Dave Singh",
        "Eva Brown", "Frank Kim", "Grace Liu", "Henry Chen"]

TOPICS = ["pricing", "demo", "integration", "security", "onboarding",
          "competition", "timeline", "features", "contract", "support"]

OBJECTIONS = [
    "Price seems high compared to competitors",
    "We need to check with legal first",
    "Timeline is too aggressive",
    "Integration with our existing tools is a concern",
    "We're still evaluating other options",
    "Budget hasn't been approved yet",
    "Not sure about data security compliance",
    "Our team needs more training time",
    "The contract terms need revision",
    "We had issues with a similar product before",
]

SIGNALS = [
    "Can you send a proposal by Friday?",
    "Let me bring in our VP of Engineering",
    "We'd like to start a pilot program",
    "This looks promising for Q2 rollout",
    "Can we schedule a technical deep dive?",
    "I'll present this to the board next week",
    "What does the enterprise plan include?",
    "We're ready to move forward",
    "Let me check budget availability",
    "Can we get a custom quote?",
]

TRANSCRIPTS = [
    "So let me walk you through our enterprise tier. We've seen great results with similar companies.",
    "I understand the pricing concern. Let me show you the ROI calculator we built.",
    "The integration is straightforward. We have a REST API and pre-built connectors.",
    "Security is our top priority. We're SOC 2 Type II certified and GDPR compliant.",
    "For onboarding, we provide dedicated support for the first 90 days.",
    "Compared to the alternatives, our platform handles real-time processing which others don't.",
    "We can meet your Q2 timeline. Let me lay out the implementation plan.",
    "The new features launching next month include automated reporting and custom dashboards.",
    "The contract is flexible. We offer monthly and annual options with volume discounts.",
    "Our support team has a 2-hour SLA for enterprise customers.",
]


def _generate_job_id(company: str, rep: str, call_num: int) -> str:
    """Deterministic job ID from inputs."""
    seed = f"{company}-{rep}-{call_num}"
    return f"demo-{hashlib.md5(seed.encode()).hexdigest()[:8]}"


def _generate_intel(
    company: str,
    rep: str,
    call_num: int,
    rng: random.Random,
) -> Dict[str, Any]:
    """Generate a realistic intel dict for a single call."""
    num_segments = rng.randint(3, 8)
    segments = []
    base_risk = rng.uniform(0.1, 0.85)

    for i in range(num_segments):
        ts_ms = i * 30_000
        topic = rng.choice(TOPICS)
        risk_score = max(0.0, min(1.0, base_risk + rng.uniform(-0.2, 0.2)))
        sentiment = rng.choice(["positive", "neutral", "negative", "hesitant"])

        obj = rng.sample(OBJECTIONS, k=rng.randint(0, 2))
        sig = rng.sample(SIGNALS, k=rng.randint(0, 2))
        transcript = rng.choice(TRANSCRIPTS)

        segments.append({
            "timestamp_str": f"{ts_ms // 60000:02d}:{(ts_ms // 1000) % 60:02d}",
            "timestamp_ms": ts_ms,
            "transcript": transcript,
            "extraction": {
                "topic": topic,
                "sentiment": sentiment,
                "risk": "high" if risk_score > 0.65 else "medium" if risk_score > 0.3 else "low",
                "risk_score": round(risk_score, 3),
                "objections": obj,
                "decision_signals": sig,
                "confidence": round(rng.uniform(0.6, 0.95), 2),
            },
        })

    overall_risk = sum(s["extraction"]["risk_score"] for s in segments) / len(segments)

    return {
        "overall_risk_score": round(overall_risk, 3),
        "duration_ms": num_segments * 30_000,
        "segments": segments,
        "speaker_intelligence": {
            "talk_ratio": {
                "SPEAKER_A": round(rng.uniform(0.35, 0.65), 2),
                "SPEAKER_B": round(rng.uniform(0.35, 0.65), 2),
            },
            "speaker_stats": {
                "SPEAKER_A": {
                    "words_per_minute": round(rng.uniform(110, 170), 1),
                    "filler_rate": round(rng.uniform(0.01, 0.06), 3),
                    "question_count": rng.randint(2, 12),
                },
            },
        },
    }


def generate_seed_data(seed: int = 42) -> Dict[str, Any]:
    """Generate complete demo seed data.

    Returns {jobs, companies, reps} where jobs is a dict of job_id → {intel, company, rep, ...}.
    """
    rng = random.Random(seed)
    jobs: Dict[str, Dict[str, Any]] = {}
    company_calls: Dict[str, int] = {}

    for company_info in COMPANIES:
        company = company_info["name"]
        contact = company_info["contact"]
        deal_id = company_info["deal_id"]
        num_calls = rng.randint(3, 6)

        for call_num in range(num_calls):
            rep = rng.choice(REPS)
            job_id = _generate_job_id(company, rep, call_num)
            intel = _generate_intel(company, rep, call_num, rng)

            jobs[job_id] = {
                "intelligence": intel,
                "company": company,
                "contact": contact,
                "deal_id": deal_id,
                "rep": rep,
                "status": "completed",
                "filename": f"{company.lower().replace(' ', '_')}_call_{call_num + 1}.mp4",
                "created_at": time.time() - rng.randint(86400, 86400 * 30),
            }
            company_calls[company] = company_calls.get(company, 0) + 1

    return {
        "jobs": jobs,
        "companies": [c["name"] for c in COMPANIES],
        "reps": REPS,
        "total_calls": len(jobs),
        "company_calls": company_calls,
    }


def seed_agents(seed_data: Dict[str, Any]) -> Dict[str, Any]:
    """Index seed data into all agents: Q&A, Risk, Coaching, KG, Meeting Prep."""
    from temporalos.agents.qa_agent import get_qa_agent
    from temporalos.agents.coaching import get_coaching_engine
    from temporalos.agents.knowledge_graph import get_knowledge_graph
    from temporalos.agents.meeting_prep import get_meeting_prep_agent
    from temporalos.agents.risk_agent import get_risk_agent

    qa = get_qa_agent()
    risk = get_risk_agent()
    coaching = get_coaching_engine()
    kg = get_knowledge_graph()
    prep = get_meeting_prep_agent()

    stats = {"qa_indexed": 0, "risk_alerts": 0, "coaching_reps": set(),
             "kg_entities": 0, "prep_indexed": 0}

    for job_id, job in seed_data["jobs"].items():
        intel = job["intelligence"]
        company = job["company"]
        contact = job["contact"]
        rep = job["rep"]

        # Q&A
        stats["qa_indexed"] += qa.index_job(job_id, intel)

        # Risk
        alerts = risk.record_job(job_id, intel, company, job.get("deal_id", ""))
        stats["risk_alerts"] += len(alerts)

        # Coaching
        coaching.record_call(rep, job_id, intel)
        stats["coaching_reps"].add(rep)

        # KG
        stats["kg_entities"] += kg.add_video(job_id, intel)

        # Meeting Prep
        prep.index_job(job_id, intel, company=company, contact=contact)
        stats["prep_indexed"] += 1

    stats["coaching_reps"] = len(stats["coaching_reps"])
    return stats


def seed_all(seed: int = 42) -> Dict[str, Any]:
    """Generate and seed everything. Returns summary stats."""
    data = generate_seed_data(seed)
    stats = seed_agents(data)
    logger.info(
        "Demo seed complete: %d jobs, %d QA docs, %d risk alerts, "
        "%d coaching reps, %d KG entities",
        data["total_calls"], stats["qa_indexed"],
        stats["risk_alerts"], stats["coaching_reps"],
        stats["kg_entities"],
    )
    return {"seed_data": data, "stats": stats}
