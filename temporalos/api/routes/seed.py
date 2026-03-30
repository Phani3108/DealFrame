"""Seed data route — populate database with demo intelligence data."""

import uuid
import logging
from datetime import datetime, timedelta
from typing import List, Dict

from fastapi import APIRouter

logger = logging.getLogger(__name__)
router = APIRouter(tags=["seed"])

# Realistic video metadata + extracted intelligence for 7 YouTube videos
SEED_VIDEOS: List[Dict] = [
    {
        "source_url": "https://youtu.be/YQkxHjPJdyo",
        "title": "Enterprise SaaS Pricing Negotiation",
        "vertical": "sales",
        "duration_ms": 847000,
        "segments": [
            {
                "timestamp": "00:00-00:45",
                "topic": "Initial pricing presentation",
                "sentiment": "neutral",
                "risk": "low",
                "risk_score": 0.15,
                "objections": [],
                "decision_signals": ["Budget allocated", "Q2 timeline confirmed"],
                "intent": "information_gathering",
                "transcript": "Let me walk you through our enterprise pricing tiers. We have three main packages designed for organizations of your size...",
                "model": "gpt-4o",
                "negotiation": {
                    "tactic": "anchoring",
                    "power_balance": 0.55,
                    "batna_strength": 0.7,
                    "concession_type": "none"
                }
            },
            {
                "timestamp": "00:45-02:15",
                "topic": "Feature comparison and ROI",
                "sentiment": "positive",
                "risk": "low",
                "risk_score": 0.2,
                "objections": ["Need to validate with engineering team"],
                "decision_signals": ["ROI framework requested", "Implementation timeline asked"],
                "intent": "evaluation",
                "transcript": "The enterprise tier includes SSO, advanced analytics, and dedicated support. Most customers see a 3x ROI within the first quarter...",
                "model": "gpt-4o",
                "negotiation": {
                    "tactic": "value_selling",
                    "power_balance": 0.6,
                    "batna_strength": 0.65,
                    "concession_type": "none"
                }
            },
            {
                "timestamp": "02:15-04:30",
                "topic": "Price pushback and discount request",
                "sentiment": "negative",
                "risk": "high",
                "risk_score": 0.78,
                "objections": ["Price is 40% above budget", "Competitor offers similar at lower price"],
                "decision_signals": ["Budget constraint mentioned", "Competitor comparison"],
                "intent": "negotiation",
                "transcript": "We appreciate the demo but frankly this is significantly over our budget. We've been evaluating two other vendors who come in at a much lower price point...",
                "model": "gpt-4o",
                "negotiation": {
                    "tactic": "competitive_leverage",
                    "power_balance": 0.4,
                    "batna_strength": 0.5,
                    "concession_type": "price_reduction_request"
                }
            },
            {
                "timestamp": "04:30-07:00",
                "topic": "Value justification and bundling",
                "sentiment": "neutral",
                "risk": "medium",
                "risk_score": 0.45,
                "objections": ["Need multi-year commitment concern"],
                "decision_signals": ["Willing to discuss annual vs monthly", "Asked about payment terms"],
                "intent": "negotiation",
                "transcript": "I understand the budget concern. Let me show you the value difference. With our platform, your team saves approximately 12 hours per week on manual reporting alone...",
                "model": "gpt-4o",
                "negotiation": {
                    "tactic": "value_reframing",
                    "power_balance": 0.5,
                    "batna_strength": 0.6,
                    "concession_type": "term_adjustment"
                }
            },
            {
                "timestamp": "07:00-09:30",
                "topic": "Contract terms and next steps",
                "sentiment": "positive",
                "risk": "medium",
                "risk_score": 0.35,
                "objections": [],
                "decision_signals": ["Verbal agreement on pilot", "Legal review scheduled", "Champion identified"],
                "intent": "commitment",
                "transcript": "Okay, I think we can make this work with the annual plan. Let me run this by our legal team and we can set up a pilot for the first 90 days...",
                "model": "gpt-4o",
                "negotiation": {
                    "tactic": "trial_close",
                    "power_balance": 0.55,
                    "batna_strength": 0.7,
                    "concession_type": "pilot_offered"
                }
            }
        ]
    },
    {
        "source_url": "https://youtube.com/shorts/OoZe67vJcSQ",
        "title": "Quick Objection Handling Tips",
        "vertical": "sales",
        "duration_ms": 58000,
        "segments": [
            {
                "timestamp": "00:00-00:30",
                "topic": "Price objection response framework",
                "sentiment": "positive",
                "risk": "low",
                "risk_score": 0.1,
                "objections": ["Too expensive"],
                "decision_signals": ["Framework shared"],
                "intent": "education",
                "transcript": "When a prospect says you're too expensive, don't discount immediately. Instead, ask what they're comparing against and reframe around total cost of ownership...",
                "model": "gpt-4o",
                "negotiation": {"tactic": "reframing", "power_balance": 0.6, "batna_strength": 0.7, "concession_type": "none"}
            },
            {
                "timestamp": "00:30-00:58",
                "topic": "Timing objection handling",
                "sentiment": "positive",
                "risk": "low",
                "risk_score": 0.15,
                "objections": ["Not the right time"],
                "decision_signals": ["Urgency creation technique"],
                "intent": "education",
                "transcript": "For timing objections, quantify the cost of delay. Show them what they lose each month by not switching. Make the status quo the expensive option...",
                "model": "gpt-4o",
                "negotiation": {"tactic": "urgency_creation", "power_balance": 0.65, "batna_strength": 0.6, "concession_type": "none"}
            }
        ]
    },
    {
        "source_url": "https://youtube.com/shorts/trZ8x8W9jNk",
        "title": "Closing Techniques Demo",
        "vertical": "sales",
        "duration_ms": 55000,
        "segments": [
            {
                "timestamp": "00:00-00:28",
                "topic": "Assumptive close technique",
                "sentiment": "positive",
                "risk": "medium",
                "risk_score": 0.3,
                "objections": ["Need to think about it"],
                "decision_signals": ["Closing signal detected"],
                "intent": "closing",
                "transcript": "Instead of asking if they want to proceed, ask when they want to start. Shift from whether to when. It's a subtle but powerful reframe...",
                "model": "gpt-4o",
                "negotiation": {"tactic": "assumptive_close", "power_balance": 0.6, "batna_strength": 0.55, "concession_type": "none"}
            },
            {
                "timestamp": "00:28-00:55",
                "topic": "Summary close with urgency",
                "sentiment": "positive",
                "risk": "low",
                "risk_score": 0.2,
                "objections": [],
                "decision_signals": ["Deal velocity signal", "Decision deadline set"],
                "intent": "closing",
                "transcript": "Recap all the value points, confirm the pain points you solve, and add a deadline incentive. This quarter's pricing expires Friday...",
                "model": "gpt-4o",
                "negotiation": {"tactic": "summary_close", "power_balance": 0.65, "batna_strength": 0.7, "concession_type": "deadline_incentive"}
            }
        ]
    },
    {
        "source_url": "https://youtube.com/shorts/JV7eeeiG-cA",
        "title": "Stakeholder Buy-in Strategy",
        "vertical": "sales",
        "duration_ms": 60000,
        "segments": [
            {
                "timestamp": "00:00-00:32",
                "topic": "Multi-threading stakeholder engagement",
                "sentiment": "neutral",
                "risk": "high",
                "risk_score": 0.65,
                "objections": ["Need VP approval", "Multiple decision makers involved"],
                "decision_signals": ["Org chart mapped", "Champion coaching needed"],
                "intent": "strategy",
                "transcript": "Single-threaded deals die. You need at least three contacts: a champion, an economic buyer, and a technical evaluator. Map the org chart early...",
                "model": "gpt-4o",
                "negotiation": {"tactic": "multi_threading", "power_balance": 0.45, "batna_strength": 0.5, "concession_type": "none"}
            },
            {
                "timestamp": "00:32-01:00",
                "topic": "Executive sponsor engagement",
                "sentiment": "positive",
                "risk": "medium",
                "risk_score": 0.4,
                "objections": ["C-suite access limited"],
                "decision_signals": ["Executive briefing requested"],
                "intent": "strategy",
                "transcript": "Get your exec to call their exec. Peer-to-peer selling at the C-level breaks through procurement bottlenecks and accelerates deal cycles by 40%...",
                "model": "gpt-4o",
                "negotiation": {"tactic": "executive_alignment", "power_balance": 0.55, "batna_strength": 0.6, "concession_type": "none"}
            }
        ]
    },
    {
        "source_url": "https://youtu.be/kojnjAYYGn0",
        "title": "Procurement Contract Review",
        "vertical": "procurement",
        "duration_ms": 623000,
        "segments": [
            {
                "timestamp": "00:00-01:30",
                "topic": "Contract terms overview",
                "sentiment": "neutral",
                "risk": "low",
                "risk_score": 0.2,
                "objections": [],
                "decision_signals": ["MSA review initiated", "Legal team engaged"],
                "intent": "evaluation",
                "transcript": "Let's go through the master service agreement section by section. The payment terms are net-30, with a 2% early payment discount...",
                "model": "gpt-4o",
                "negotiation": {"tactic": "structured_review", "power_balance": 0.5, "batna_strength": 0.6, "concession_type": "none"}
            },
            {
                "timestamp": "01:30-03:45",
                "topic": "SLA and penalty clause negotiation",
                "sentiment": "negative",
                "risk": "high",
                "risk_score": 0.82,
                "objections": ["99.9% uptime SLA insufficient", "Penalty caps too low", "Force majeure clause too broad"],
                "decision_signals": ["SLA renegotiation required", "Legal escalation"],
                "intent": "negotiation",
                "transcript": "The 99.9% SLA only covers core services, not the API layer. We need 99.95% across all endpoints. And the penalty cap at 10% of monthly fees is far too low for enterprise...",
                "model": "gpt-4o",
                "negotiation": {"tactic": "clause_by_clause", "power_balance": 0.55, "batna_strength": 0.7, "concession_type": "sla_upgrade_request"}
            },
            {
                "timestamp": "03:45-06:00",
                "topic": "Data governance and compliance",
                "sentiment": "neutral",
                "risk": "high",
                "risk_score": 0.72,
                "objections": ["GDPR compliance gaps", "Data residency requirements not met"],
                "decision_signals": ["DPA revision needed", "Compliance audit scheduled"],
                "intent": "compliance_review",
                "transcript": "Section 8 on data processing doesn't address EU data residency requirements. We need a GDPR-compliant DPA addendum and confirmation of SOC 2 Type II certification...",
                "model": "gpt-4o",
                "negotiation": {"tactic": "compliance_leverage", "power_balance": 0.6, "batna_strength": 0.75, "concession_type": "none"}
            },
            {
                "timestamp": "06:00-08:15",
                "topic": "Pricing model and volume discounts",
                "sentiment": "positive",
                "risk": "medium",
                "risk_score": 0.38,
                "objections": ["Volume tier thresholds too high"],
                "decision_signals": ["Multi-year discount agreed", "Volume commitment discussed"],
                "intent": "negotiation",
                "transcript": "We can commit to a 3-year term if you bring the volume discount threshold down from 10,000 to 5,000 seats. That gets us to the enterprise tier pricing from day one...",
                "model": "gpt-4o",
                "negotiation": {"tactic": "volume_leverage", "power_balance": 0.55, "batna_strength": 0.65, "concession_type": "volume_commitment"}
            }
        ]
    },
    {
        "source_url": "https://youtu.be/-vSAUVwi4pk",
        "title": "Customer Success QBR",
        "vertical": "customer_success",
        "duration_ms": 542000,
        "segments": [
            {
                "timestamp": "00:00-01:15",
                "topic": "Quarterly metrics review",
                "sentiment": "positive",
                "risk": "low",
                "risk_score": 0.12,
                "objections": [],
                "decision_signals": ["NPS score 72", "Usage up 34%", "ROI documented"],
                "intent": "review",
                "transcript": "Great quarter overall. Your team's adoption is up 34% quarter-over-quarter, NPS score is 72, and the automated workflows saved your ops team about 200 hours...",
                "model": "gpt-4o",
                "negotiation": {"tactic": "value_reinforcement", "power_balance": 0.6, "batna_strength": 0.8, "concession_type": "none"}
            },
            {
                "timestamp": "01:15-03:00",
                "topic": "Feature adoption gaps",
                "sentiment": "neutral",
                "risk": "medium",
                "risk_score": 0.45,
                "objections": ["Advanced reporting underutilized", "API integration stalled"],
                "decision_signals": ["Training session requested", "Technical resources needed"],
                "intent": "remediation",
                "transcript": "One area I want to flag — your team is only using 40% of the advanced reporting suite. There's significant untapped value there. I'd like to schedule a deep-dive training...",
                "model": "gpt-4o",
                "negotiation": {"tactic": "expansion_selling", "power_balance": 0.55, "batna_strength": 0.7, "concession_type": "none"}
            },
            {
                "timestamp": "03:00-05:30",
                "topic": "Renewal discussion and expansion",
                "sentiment": "positive",
                "risk": "low",
                "risk_score": 0.18,
                "objections": ["Budget freeze concerns for Q1"],
                "decision_signals": ["Renewal intent confirmed", "Expansion to 3 more teams discussed", "Executive sponsor supportive"],
                "intent": "expansion",
                "transcript": "We're definitely renewing — the platform has become essential to our workflow. We're also looking at rolling this out to the marketing and product teams next quarter...",
                "model": "gpt-4o",
                "negotiation": {"tactic": "land_and_expand", "power_balance": 0.65, "batna_strength": 0.85, "concession_type": "none"}
            }
        ]
    },
    {
        "source_url": "https://youtu.be/OXlbIS1h9vM",
        "title": "Deal Risk Assessment Workshop",
        "vertical": "sales",
        "duration_ms": 734000,
        "segments": [
            {
                "timestamp": "00:00-02:00",
                "topic": "Risk scoring methodology",
                "sentiment": "neutral",
                "risk": "low",
                "risk_score": 0.1,
                "objections": [],
                "decision_signals": ["Framework established", "Team alignment on methodology"],
                "intent": "education",
                "transcript": "Today we're going to build a deal risk scorecard. Every deal gets evaluated on five dimensions: champion strength, timeline certainty, budget confirmation, competitive threat, and technical fit...",
                "model": "gpt-4o",
                "negotiation": {"tactic": "framework_setting", "power_balance": 0.5, "batna_strength": 0.6, "concession_type": "none"}
            },
            {
                "timestamp": "02:00-04:30",
                "topic": "High-risk deal review - Acme Corp",
                "sentiment": "negative",
                "risk": "high",
                "risk_score": 0.85,
                "objections": ["Champion left the company", "Budget reallocated to different project", "No response to last 3 outreach attempts"],
                "decision_signals": ["Deal stalled 45 days", "No executive engagement", "Competitor POC in progress"],
                "intent": "risk_assessment",
                "transcript": "Let's look at the Acme deal. Our champion Sarah moved to a different company last month. The new VP hasn't responded to outreach. Budget was reallocated to their digital transformation project...",
                "model": "gpt-4o",
                "negotiation": {"tactic": "risk_analysis", "power_balance": 0.25, "batna_strength": 0.3, "concession_type": "none"}
            },
            {
                "timestamp": "04:30-07:00",
                "topic": "Recovery strategy for at-risk deals",
                "sentiment": "neutral",
                "risk": "medium",
                "risk_score": 0.55,
                "objections": ["Internal prioritization unclear"],
                "decision_signals": ["Executive intervention planned", "New champion identification started"],
                "intent": "strategy",
                "transcript": "Here's the recovery playbook. Step one: find a new champion through warm introductions. Step two: get your VP to reach their VP. Step three: create a compelling event with a deadline...",
                "model": "gpt-4o",
                "negotiation": {"tactic": "deal_rescue", "power_balance": 0.35, "batna_strength": 0.4, "concession_type": "none"}
            },
            {
                "timestamp": "07:00-09:45",
                "topic": "Pipeline cleanup and forecasting",
                "sentiment": "positive",
                "risk": "medium",
                "risk_score": 0.4,
                "objections": ["Forecast accuracy needs improvement"],
                "decision_signals": ["Pipeline audit completed", "Commit vs upside categorized", "60-day action plans set"],
                "intent": "planning",
                "transcript": "After this review, we're moving three deals from commit to upside and adding specific 60-day action plans for each at-risk opportunity. Our goal is 85% forecast accuracy this quarter...",
                "model": "gpt-4o",
                "negotiation": {"tactic": "pipeline_management", "power_balance": 0.5, "batna_strength": 0.55, "concession_type": "none"}
            }
        ]
    },
]


@router.post("/seed", status_code=201)
async def seed_demo_data() -> dict:
    """Populate the database with realistic demo data for 7 YouTube videos.

    Creates JobRecords, SearchDocRecords, and populates the in-memory caches
    so the dashboard immediately shows stats.
    """
    from ...api.routes.process import _jobs

    created_jobs = []
    total_segments = 0

    for i, video in enumerate(SEED_VIDEOS):
        job_id = str(uuid.uuid5(uuid.NAMESPACE_URL, video["source_url"]))

        # Build result segments
        segments = []
        for seg in video["segments"]:
            segments.append({
                "timestamp": seg["timestamp"],
                "topic": seg["topic"],
                "sentiment": seg.get("sentiment", "neutral"),
                "risk": seg["risk"],
                "risk_score": seg["risk_score"],
                "objections": seg.get("objections", []),
                "decision_signals": seg.get("decision_signals", []),
                "intent": seg.get("intent", ""),
                "transcript": seg.get("transcript", ""),
                "model": seg.get("model", "gpt-4o"),
                "negotiation": seg.get("negotiation", {}),
            })

        overall_risk = round(sum(s["risk_score"] for s in segments) / len(segments), 2) if segments else 0.0

        job_data = {
            "status": "completed",
            "stages_done": ["frame_extraction", "transcription", "alignment", "extraction"],
            "video_path": f"/tmp/dealframe/uploads/{job_id}.mp4",
            "frames_dir": f"/tmp/dealframe/frames/{job_id}",
            "source_url": video["source_url"],
            "result": {
                "segments": segments,
                "overall_risk_score": overall_risk,
                "segment_count": len(segments),
                "title": video["title"],
                "vertical": video.get("vertical", "sales"),
                "duration_ms": video.get("duration_ms", 0),
            }
        }

        # Update in-memory cache
        _jobs[job_id] = job_data

        # Persist to DB
        try:
            from ...db.session import get_session_factory
            sf = get_session_factory()
            if sf:
                from ...db.models import JobRecord, SearchDocRecord
                from sqlalchemy import select
                async with sf() as sess:
                    # Upsert job
                    row = (await sess.execute(
                        select(JobRecord).where(JobRecord.id == job_id)
                    )).scalar_one_or_none()
                    if row is None:
                        row = JobRecord(
                            id=job_id,
                            created_at=datetime.utcnow() - timedelta(days=7-i),
                        )
                        sess.add(row)
                    row.status = "completed"
                    row.video_path = job_data["video_path"]
                    row.frames_dir = job_data["frames_dir"]
                    row.stages_done = job_data["stages_done"]
                    row.result = job_data["result"]
                    row.error = None

                    # Create search docs
                    for seg in segments:
                        doc_id = f"{job_id}:{seg['timestamp']}"
                        doc = SearchDocRecord(
                            id=doc_id,
                            video_id=job_id,
                            timestamp_ms=0,
                            timestamp_str=seg["timestamp"],
                            topic=seg["topic"],
                            risk=seg["risk"],
                            risk_score=seg["risk_score"],
                            objections=seg.get("objections", []),
                            decision_signals=seg.get("decision_signals", []),
                            transcript=seg.get("transcript", ""),
                            model=seg.get("model", "gpt-4o"),
                        )
                        await sess.merge(doc)

                    await sess.commit()
        except Exception as exc:
            logger.warning("DB persist failed for seed job %s: %s", job_id, exc)

        # Index in search engine
        try:
            from ...search.indexer import IndexEntry, get_search_index
            idx = get_search_index()
            for seg in segments:
                entry = IndexEntry(
                    doc_id=f"{job_id}:{seg['timestamp']}",
                    video_id=job_id,
                    timestamp_ms=0,
                    timestamp_str=seg["timestamp"],
                    topic=seg["topic"],
                    risk=seg["risk"],
                    risk_score=seg["risk_score"],
                    objections=seg.get("objections", []),
                    decision_signals=seg.get("decision_signals", []),
                    transcript=seg.get("transcript", ""),
                    model=seg.get("model", "gpt-4o"),
                )
                idx.index(entry)
        except Exception:
            pass

        created_jobs.append({"job_id": job_id, "title": video["title"], "segments": len(segments)})
        total_segments += len(segments)

    return {
        "status": "seeded",
        "videos_created": len(created_jobs),
        "total_segments": total_segments,
        "jobs": created_jobs,
    }
