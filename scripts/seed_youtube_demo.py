"""Seed demo data from real YouTube video URLs.

Creates realistic processed-job data for 11 sales/negotiation videos,
with approximate scores, segments, speaker intelligence, etc.
Seeds into: _jobs cache, DB, search index, QA, risk, coaching, KG, meeting prep.

Usage:
    python -m scripts.seed_youtube_demo          # seed all
    python -m scripts.seed_youtube_demo --reset   # clear + reseed
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import random
import time
import uuid
from typing import Any

logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────────────────────
# 11 YouTube videos with handcrafted realistic metadata
# ────────────────────────────────────────────────────────────────────────────
YOUTUBE_DEMOS: list[dict[str, Any]] = [
    {
        "url": "https://www.youtube.com/watch?v=DLhDul9GUUM",
        "title": "Enterprise SaaS Sales Call — Acme Cloud Platform",
        "company": "NovaTech Solutions",
        "contact": "Rachel Kim",
        "deal_id": "novatech-ent-2026",
        "rep": "James Weston",
        "duration_ms": 1_820_000,   # ~30 min
        "scenario": "enterprise_saas",
        "segments": [
            {"ts": 0,      "topic": "onboarding",   "sentiment": "positive", "risk_score": 0.15, "transcript": "Thanks for taking the time today Rachel. I'd love to walk you through how our platform can streamline your team's workflow and save about 30% on operational costs.",                      "objections": [],                                                           "signals": ["Sounds great, we've been looking for something like this"]},
            {"ts": 45000,  "topic": "features",     "sentiment": "positive", "risk_score": 0.10, "transcript": "The dashboard gives you real-time visibility into all your pipelines. Everything is customizable — you can drag and drop widgets, set alerts, and export to CSV or PDF.",                     "objections": [],                                                           "signals": ["Can we get a sandbox to test this?"]},
            {"ts": 120000, "topic": "integration",   "sentiment": "neutral",  "risk_score": 0.35, "transcript": "We integrate natively with Salesforce, HubSpot, and Slack. For your custom ERP, we'd use our REST API — most teams get it running in about two sprint cycles.",                          "objections": ["Our ERP is heavily customized, integrations have failed before"], "signals": []},
            {"ts": 210000, "topic": "pricing",       "sentiment": "hesitant", "risk_score": 0.55, "transcript": "The enterprise tier is $85 per user per month, billed annually. That includes unlimited integrations, priority support, and dedicated success manager.",                                  "objections": ["That's higher than what we budgeted for this quarter"],      "signals": []},
            {"ts": 330000, "topic": "security",      "sentiment": "positive", "risk_score": 0.20, "transcript": "We're SOC 2 Type II certified, GDPR compliant, and we just completed our FedRAMP authorization. All data is encrypted at rest and in transit with AES-256.",                             "objections": [],                                                           "signals": ["That checks our compliance boxes"]},
            {"ts": 480000, "topic": "competition",    "sentiment": "hesitant", "risk_score": 0.60, "transcript": "I understand you've been evaluating Datadog and Splunk as well. Where we differentiate is the unified sales intelligence layer — it's not just monitoring, it's actionable insights.",    "objections": ["Splunk is offering us a significant discount"],              "signals": ["Your AI features are more advanced though"]},
            {"ts": 600000, "topic": "timeline",       "sentiment": "neutral",  "risk_score": 0.30, "transcript": "We can have you onboarded and running in production within 6 weeks. The first two weeks are dedicated to integration setup with your engineering team.",                                 "objections": [],                                                           "signals": ["Let me check with our CTO on the timeline"]},
            {"ts": 780000, "topic": "pricing",       "sentiment": "hesitant", "risk_score": 0.50, "transcript": "If you commit to the annual plan for 200 seats, I can offer a 15% volume discount. That brings it down to about $72 per user.",                                                        "objections": ["We need to run this by procurement"],                        "signals": ["Can you send a formal proposal by Friday?"]},
            {"ts": 960000, "topic": "support",       "sentiment": "positive", "risk_score": 0.15, "transcript": "Enterprise customers get a 2-hour SLA for critical issues, dedicated Slack channel, and quarterly business reviews with your success team.",                                             "objections": [],                                                           "signals": ["That's exactly what we need"]},
            {"ts": 1080000,"topic": "contract",      "sentiment": "neutral",  "risk_score": 0.25, "transcript": "The contract is pretty standard — annual commitment with a 30-day out clause after the first year. We're flexible on payment terms.",                                                   "objections": [],                                                           "signals": ["Send it over, I'll have legal review it"]},
        ],
    },
    {
        "url": "https://www.youtube.com/watch?v=NxsVb08vDmI",
        "title": "Product Demo — AI Analytics Platform",
        "company": "Meridian Health Systems",
        "contact": "Dr. Sarah Patel",
        "deal_id": "meridian-health-q1",
        "rep": "Elena Rodriguez",
        "duration_ms": 1_440_000,   # 24 min
        "scenario": "healthcare_analytics",
        "segments": [
            {"ts": 0,      "topic": "demo",         "sentiment": "positive", "risk_score": 0.10, "transcript": "Let me show you how our AI platform processes patient flow data in real-time to predict bottlenecks and optimize scheduling across all your facilities.",                                  "objections": [],                                                           "signals": ["This is exactly the pain point we described"]},
            {"ts": 90000,  "topic": "features",     "sentiment": "positive", "risk_score": 0.12, "transcript": "The predictive model uses 3 years of historical data to forecast patient volumes with 94% accuracy. It also factors in seasonal patterns, weather, and local events.",                    "objections": [],                                                           "signals": ["How quickly can we start seeing predictions?"]},
            {"ts": 180000, "topic": "security",      "sentiment": "neutral",  "risk_score": 0.40, "transcript": "HIPAA compliance is baked into every layer. PHI is tokenized at ingestion, stored in dedicated tenants, and all access is audit-logged with immutable trails.",                          "objections": ["We need BAA agreements and a full security review"],         "signals": []},
            {"ts": 300000, "topic": "integration",   "sentiment": "hesitant", "risk_score": 0.55, "transcript": "We connect with Epic and Cerner via HL7 FHIR. The integration typically takes 8-12 weeks depending on your system configuration.",                                                      "objections": ["Our Epic instance is 3 versions behind", "12 weeks is too long"], "signals": []},
            {"ts": 420000, "topic": "pricing",       "sentiment": "hesitant", "risk_score": 0.65, "transcript": "The healthcare tier is a flat $50K per facility per year. For a 12-facility system like yours, we offer tiered pricing at $42K per facility.",                                           "objections": ["That's over $500K annually, we need to justify this to the board"], "signals": []},
            {"ts": 540000, "topic": "features",     "sentiment": "positive", "risk_score": 0.15, "transcript": "The staffing optimizer alone saved Cleveland Medical $2.3M in their first year. I can connect you with their CMO for a reference call.",                                                  "objections": [],                                                           "signals": ["Yes, a reference call would be very helpful"]},
            {"ts": 720000, "topic": "timeline",       "sentiment": "neutral",  "risk_score": 0.35, "transcript": "Realistically, you'd see initial dashboard results within 4 weeks, and full predictive capabilities after the 12-week integration window.",                                             "objections": [],                                                           "signals": ["Let's set up a meeting with our IT director"]},
            {"ts": 900000, "topic": "contract",      "sentiment": "neutral",  "risk_score": 0.30, "transcript": "We offer 3-year terms with guaranteed price locks. Given the integration investment, most health systems prefer the longer commitment.",                                                 "objections": ["Board approval process takes 6-8 weeks minimum"],            "signals": ["I'll start the internal paperwork this week"]},
        ],
    },
    {
        "url": "https://www.youtube.com/watch?v=0CdixDzE7I0",
        "title": "SaaS Pricing Negotiation — Mid-Market Deal",
        "company": "Vertex Financial",
        "contact": "Marcus Chen",
        "deal_id": "vertex-fin-2026",
        "rep": "Priya Sharma",
        "duration_ms": 960_000,     # 16 min
        "scenario": "pricing_negotiation",
        "segments": [
            {"ts": 0,      "topic": "pricing",       "sentiment": "neutral",  "risk_score": 0.40, "transcript": "Marcus, thanks for coming back for round two. I've prepared a revised proposal based on your feedback about the pricing structure.",                                                     "objections": [],                                                           "signals": []},
            {"ts": 60000,  "topic": "pricing",       "sentiment": "hesitant", "risk_score": 0.70, "transcript": "We're looking at $45 per seat for 150 users. With the add-ons you need — SSO, audit log, custom reporting — that jumps to $62 per seat.",                                               "objections": ["$62 is 38% over our approved budget", "Other vendors include SSO in base price"], "signals": []},
            {"ts": 180000, "topic": "competition",    "sentiment": "negative", "risk_score": 0.80, "transcript": "I have to be transparent — we received a very competitive offer from your main competitor at $38 per seat, all features included.",                                                      "objections": ["Your competitor includes what you charge extra for"],         "signals": []},
            {"ts": 270000, "topic": "features",     "sentiment": "neutral",  "risk_score": 0.45, "transcript": "I understand. Let me show you the compliance automation engine — it alone replaces a $200K annual manual process. That's ROI within 4 months.",                                           "objections": [],                                                           "signals": ["The compliance automation is compelling"]},
            {"ts": 360000, "topic": "pricing",       "sentiment": "hesitant", "risk_score": 0.60, "transcript": "What if I bundle SSO into the base tier and offer $52 per seat for a 2-year commitment? That's a 16% reduction plus the SSO value.",                                                     "objections": ["Still need to get below $50"],                               "signals": ["Getting closer to where we need to be"]},
            {"ts": 480000, "topic": "contract",      "sentiment": "neutral",  "risk_score": 0.35, "transcript": "For a 3-year deal with 150+ seats, I can go to $48 per seat with SSO and audit log included. That's my best offer.",                                                                    "objections": [],                                                           "signals": ["$48 works if you include the custom reporting too"]},
            {"ts": 600000, "topic": "timeline",       "sentiment": "positive", "risk_score": 0.20, "transcript": "Great. I'll send the updated proposal today. If you can get legal review done by next Friday, we can hit your Q1 deployment target.",                                                    "objections": [],                                                           "signals": ["Let's do it — send the 3-year proposal at $48"]},
        ],
    },
    {
        "url": "https://www.youtube.com/watch?v=kwfJifxukZ0",
        "title": "Discovery Call — Manufacturing IoT Platform",
        "company": "Pacific Manufacturing Group",
        "contact": "Tom Nakamura",
        "deal_id": "pacific-mfg-iot",
        "rep": "David Park",
        "duration_ms": 1_260_000,   # 21 min
        "scenario": "discovery_call",
        "segments": [
            {"ts": 0,      "topic": "onboarding",   "sentiment": "positive", "risk_score": 0.10, "transcript": "Tom, I appreciate you making time. Before I show anything, I'd love to understand your current setup and where you're feeling the most friction.",                                        "objections": [],                                                           "signals": []},
            {"ts": 90000,  "topic": "features",     "sentiment": "neutral",  "risk_score": 0.20, "transcript": "So you're running 340 CNC machines across 4 plants, and your downtime prediction is basically reactive? That's actually a perfect use case for our platform.",                             "objections": [],                                                           "signals": ["We're losing $2M annually to unplanned downtime"]},
            {"ts": 180000, "topic": "demo",         "sentiment": "positive", "risk_score": 0.15, "transcript": "Here's a live view from one of our customers — a similar-sized operation. See how the model flags bearing degradation 72 hours before failure?",                                          "objections": [],                                                           "signals": ["That's incredible. Our maintenance team would love this"]},
            {"ts": 300000, "topic": "integration",   "sentiment": "hesitant", "risk_score": 0.50, "transcript": "The challenge is your Siemens PLCs are running an older protocol. We'd need to install edge gateways — about $2K per machine for the converter hardware.",                                "objections": ["$680K in gateway hardware is a big ask on top of software"],  "signals": []},
            {"ts": 420000, "topic": "pricing",       "sentiment": "hesitant", "risk_score": 0.55, "transcript": "The platform license is $150K per plant annually. Including the gateway hardware on a 3-year amortized plan, you're looking at $825K for the first year.",                                "objections": ["We need to stay under $600K for this fiscal year"],           "signals": []},
            {"ts": 540000, "topic": "timeline",       "sentiment": "neutral",  "risk_score": 0.30, "transcript": "We could phase the rollout — start with your highest-value plant, prove the ROI, then expand. First plant goes live in 8 weeks.",                                                       "objections": [],                                                           "signals": ["A phased approach makes sense for us"]},
            {"ts": 660000, "topic": "features",     "sentiment": "positive", "risk_score": 0.12, "transcript": "The ROI calculator shows that with your downtime costs, you'd break even in 7 months on the first plant alone.",                                                                          "objections": [],                                                           "signals": ["Can you send that ROI model to our CFO?"]},
            {"ts": 780000, "topic": "support",       "sentiment": "positive", "risk_score": 0.10, "transcript": "We include 24/7 monitoring and on-site support for the first 90 days. After that, your team manages it with our remote support SLA.",                                                     "objections": [],                                                           "signals": ["Let's schedule a site visit next week"]},
        ],
    },
    {
        "url": "https://www.youtube.com/watch?v=bgz2vNMTpxQ",
        "title": "Competitive Displacement Call — CRM Switch",
        "company": "Atlas Retail",
        "contact": "Jennifer Park",
        "deal_id": "atlas-crm-switch",
        "rep": "Michael Torres",
        "duration_ms": 1_080_000,   # 18 min
        "scenario": "competitive_displacement",
        "segments": [
            {"ts": 0,      "topic": "competition",    "sentiment": "negative", "risk_score": 0.45, "transcript": "Jennifer, you mentioned your current CRM vendor raised prices 40% at renewal. Let's look at what a migration to our platform would look like.",                                          "objections": [],                                                           "signals": ["We're actively looking to switch before Q2"]},
            {"ts": 90000,  "topic": "features",     "sentiment": "positive", "risk_score": 0.15, "transcript": "Unlike legacy CRMs, our platform includes AI-powered lead scoring, automated follow-ups, and predictive pipeline reporting — all in the base tier.",                                       "objections": [],                                                           "signals": ["The AI lead scoring is a game-changer for us"]},
            {"ts": 180000, "topic": "integration",   "sentiment": "hesitant", "risk_score": 0.65, "transcript": "The data migration from your current system typically takes 4-6 weeks. We handle it end-to-end, but there's usually a 2-week parallel run period.",                                      "objections": ["We can't afford any downtime during migration", "Our sales team resists tool changes"], "signals": []},
            {"ts": 300000, "topic": "pricing",       "sentiment": "neutral",  "risk_score": 0.30, "transcript": "We're offering $35 per user for 500 seats — that's 45% less than what you're paying now. And that price is locked for 3 years.",                                                         "objections": [],                                                           "signals": ["The pricing is very competitive"]},
            {"ts": 420000, "topic": "security",      "sentiment": "neutral",  "risk_score": 0.25, "transcript": "We match every compliance certification your current vendor has — SOC 2, ISO 27001, GDPR. Plus we offer zero-trust architecture as standard.",                                           "objections": [],                                                           "signals": []},
            {"ts": 540000, "topic": "onboarding",   "sentiment": "hesitant", "risk_score": 0.50, "transcript": "We provide dedicated migration specialists and 10 hours of live training per team. The adoption rate across retail clients averages 89% within 30 days.",                                  "objections": ["Last migration took 6 months and was painful"],              "signals": ["If you can guarantee 6 weeks, we're interested"]},
            {"ts": 660000, "topic": "contract",      "sentiment": "positive", "risk_score": 0.15, "transcript": "We'll include a migration guarantee in the contract — if we don't hit the 6-week target, you get 3 months free. That's how confident we are.",                                           "objections": [],                                                           "signals": ["Send the proposal to me and our COO"]},
        ],
    },
    {
        "url": "https://www.youtube.com/shorts/D75HvLsUvq8",
        "title": "Quick Sales Tip — Handling Budget Objections",
        "company": "Pinnacle Corp",
        "contact": "Lisa Wang",
        "deal_id": "pinnacle-quick",
        "rep": "Sarah Johnson",
        "duration_ms": 58_000,     # ~1 min short
        "scenario": "budget_objection",
        "segments": [
            {"ts": 0,      "topic": "pricing",       "sentiment": "hesitant", "risk_score": 0.70, "transcript": "When a prospect says 'we don't have the budget,' don't panic. Ask: 'Is it a budget issue or a priority issue?' That reframes the entire conversation.",                                   "objections": ["Budget hasn't been allocated for this"],                      "signals": []},
            {"ts": 30000,  "topic": "pricing",       "sentiment": "positive", "risk_score": 0.35, "transcript": "Then show the cost of inaction. If they're losing $50K monthly to the problem you solve, the $30K annual investment sells itself.",                                                      "objections": [],                                                           "signals": ["That makes sense, let me reconsider the timeline"]},
        ],
    },
    {
        "url": "https://youtu.be/WZVrK-CoBno?si=Aq8dOE67OdVBmUOU",
        "title": "Technical Deep Dive — DevSecOps Platform Demo",
        "company": "Quantum Labs",
        "contact": "Alex Volkov",
        "deal_id": "quantum-devsecops",
        "rep": "Chris Anderson",
        "duration_ms": 2_100_000,   # 35 min
        "scenario": "technical_deepdive",
        "segments": [
            {"ts": 0,      "topic": "demo",         "sentiment": "positive", "risk_score": 0.10, "transcript": "Alex, I know your team has deep technical requirements. Let me walk through the architecture — we're running on Kubernetes with auto-scaling pods per pipeline.",                            "objections": [],                                                           "signals": ["Our VP of Engineering is also on this call"]},
            {"ts": 120000, "topic": "security",      "sentiment": "positive", "risk_score": 0.20, "transcript": "Every container image is scanned at build time. We integrate with Snyk, Trivy, and our own ML-based vulnerability detector that catches zero-days 48 hours faster.",                     "objections": [],                                                           "signals": ["The zero-day detection is very interesting"]},
            {"ts": 240000, "topic": "integration",   "sentiment": "neutral",  "risk_score": 0.30, "transcript": "We support GitHub, GitLab, Bitbucket, and Azure DevOps natively. Your CI/CD pipelines don't change — we plug in as a scanning stage.",                                                   "objections": [],                                                           "signals": []},
            {"ts": 420000, "topic": "features",     "sentiment": "positive", "risk_score": 0.15, "transcript": "The compliance dashboard shows your SBOM across all services. Every dependency is tracked, versioned, and mapped to CVE databases in real-time.",                                          "objections": [],                                                           "signals": ["This solves our audit reporting problem"]},
            {"ts": 600000, "topic": "security",      "sentiment": "hesitant", "risk_score": 0.45, "transcript": "Where does scan data live? We have strict data residency requirements — nothing can leave our AWS us-east-1 region.",                                                                     "objections": ["Data residency is non-negotiable for our compliance team"],  "signals": []},
            {"ts": 780000, "topic": "pricing",       "sentiment": "neutral",  "risk_score": 0.35, "transcript": "The enterprise plan is $120 per developer per month. For your 80-person team, that's $115K annually. We include unlimited scans and repos.",                                             "objections": [],                                                           "signals": ["That's within our security budget"]},
            {"ts": 960000, "topic": "features",     "sentiment": "positive", "risk_score": 0.10, "transcript": "One more thing — our AI-powered fix suggestions. When we find a vulnerability, we don't just flag it. We auto-generate the remediation PR with the exact dependency update.",              "objections": [],                                                           "signals": ["That would save our team hours every week"]},
            {"ts": 1140000,"topic": "competition",    "sentiment": "neutral",  "risk_score": 0.30, "transcript": "Compared to Snyk standalone, we offer the full pipeline — scanning, monitoring, auto-fix, AND compliance reporting in one platform. Fewer vendor contracts to manage.",                   "objections": [],                                                           "signals": ["Let's set up a POC for our platform team"]},
            {"ts": 1380000,"topic": "timeline",       "sentiment": "positive", "risk_score": 0.15, "transcript": "POC typically runs 2 weeks. We'll give you full access — just point it at your most complex repo and let it rip. No commitment required.",                                               "objections": [],                                                           "signals": ["I'll get the POC approved by end of week"]},
        ],
    },
    {
        "url": "https://youtu.be/z3U0FRb9yr4?si=10jwrK7e_tV_r_P-",
        "title": "Upsell Call — Expanding From Pro to Enterprise",
        "company": "Zenith Media Group",
        "contact": "Diana Foster",
        "deal_id": "zenith-upsell-ent",
        "rep": "James Weston",
        "duration_ms": 1_140_000,   # 19 min
        "scenario": "upsell_expansion",
        "segments": [
            {"ts": 0,      "topic": "onboarding",   "sentiment": "positive", "risk_score": 0.08, "transcript": "Diana, congratulations on hitting 200 active users on the Pro plan! That's amazing growth. I wanted to chat about what Enterprise unlocks for teams at your scale.",                       "objections": [],                                                           "signals": ["We're definitely feeling the limits of Pro"]},
            {"ts": 90000,  "topic": "features",     "sentiment": "positive", "risk_score": 0.10, "transcript": "Enterprise gives you SSO integration, advanced analytics, custom workflows, and — the big one — API access for your internal tools.",                                                      "objections": [],                                                           "signals": ["API access is exactly what our dev team has been requesting"]},
            {"ts": 210000, "topic": "pricing",       "sentiment": "hesitant", "risk_score": 0.50, "transcript": "The upgrade from Pro at $29/user to Enterprise at $59/user represents a $72K annual increase for your 200 seats.",                                                                       "objections": ["That's almost double — hard sell to our CFO"],               "signals": []},
            {"ts": 330000, "topic": "features",     "sentiment": "positive", "risk_score": 0.15, "transcript": "Let me quantify the value. The advanced analytics alone saved Horizon Media 15 hours per week across their ops team. At your team size, that's roughly $180K in productivity.",              "objections": [],                                                           "signals": ["Those efficiency numbers are impressive"]},
            {"ts": 450000, "topic": "pricing",       "sentiment": "neutral",  "risk_score": 0.35, "transcript": "Because you're an existing customer with great usage metrics, I can offer a loyalty upgrade: $49/user on a 2-year Enterprise commitment. That's a 17% discount.",                        "objections": [],                                                           "signals": ["$49 is more palatable"]},
            {"ts": 570000, "topic": "contract",      "sentiment": "neutral",  "risk_score": 0.25, "transcript": "The transition is seamless — no data migration, same login, just enhanced capabilities. Your team sees the new features the day the upgrade goes live.",                                  "objections": [],                                                           "signals": ["Can we do a trial month of Enterprise before committing?"]},
            {"ts": 690000, "topic": "support",       "sentiment": "positive", "risk_score": 0.10, "transcript": "Enterprise also includes a dedicated customer success manager — that's me, by the way. Monthly check-ins, roadmap previews, and priority feature requests.",                               "objections": [],                                                           "signals": ["Let me bring our VP in for the next call to finalize"]},
        ],
    },
    {
        "url": "https://youtu.be/ea-fUHCfgtI?si=fua4DTSAevWvLv-l",
        "title": "Cold Outreach — First Meeting with Prospect",
        "company": "Brightstar Logistics",
        "contact": "Kevin O'Brien",
        "deal_id": "brightstar-cold",
        "rep": "Priya Sharma",
        "duration_ms": 780_000,     # 13 min
        "scenario": "cold_outreach",
        "segments": [
            {"ts": 0,      "topic": "onboarding",   "sentiment": "neutral",  "risk_score": 0.30, "transcript": "Kevin, thanks for taking my call. I noticed Brightstar is expanding to 3 new distribution centers. That usually creates fleet management headaches — is that something you're dealing with?", "objections": [],                                                          "signals": []},
            {"ts": 60000,  "topic": "features",     "sentiment": "neutral",  "risk_score": 0.25, "transcript": "Our platform consolidates route optimization, fuel tracking, and driver scheduling into one dashboard. Companies like yours typically save 22% on fleet operating costs.",                   "objections": [],                                                           "signals": ["We're spending way too much on diesel right now"]},
            {"ts": 150000, "topic": "demo",         "sentiment": "positive", "risk_score": 0.15, "transcript": "Here's a quick look — this is anonymized data from a logistics company your size. See how the AI reroutes in real-time based on traffic, weather, and delivery windows?",                  "objections": [],                                                           "signals": ["That's impressive — our dispatchers do this manually today"]},
            {"ts": 240000, "topic": "pricing",       "sentiment": "hesitant", "risk_score": 0.55, "transcript": "We're $12 per vehicle per month. For your fleet of 800 vehicles, you're looking at $115K annually.",                                                                                      "objections": ["We haven't budgeted for fleet tech this year"],              "signals": []},
            {"ts": 360000, "topic": "competition",    "sentiment": "neutral",  "risk_score": 0.40, "transcript": "I know you've looked at Samsara. The key difference is our AI optimization — Samsara tracks, we track AND optimize. That optimization is where the 22% savings comes from.",              "objections": ["We had a demo with Samsara last month"],                     "signals": ["The optimization angle is different"]},
            {"ts": 480000, "topic": "timeline",       "sentiment": "neutral",  "risk_score": 0.35, "transcript": "Given your expansion timeline, starting a pilot with one distribution center in the next 3 weeks would give you real data before the full rollout in Q3.",                                "objections": [],                                                           "signals": ["A pilot could work — send me the details"]},
        ],
    },
    {
        "url": "https://youtu.be/Z3HJCQJ2Lmo?si=lsdEA2_kLwdUiT_g",
        "title": "Renewal Risk Call — At-Risk Enterprise Account",
        "company": "Silverline Insurance",
        "contact": "Patricia Myers",
        "deal_id": "silverline-renewal",
        "rep": "Elena Rodriguez",
        "duration_ms": 1_500_000,   # 25 min
        "scenario": "renewal_risk",
        "segments": [
            {"ts": 0,      "topic": "support",       "sentiment": "negative", "risk_score": 0.75, "transcript": "Patricia, I want to address your concerns head-on. I know the last quarter has been frustrating with the support ticket response times.",                                                 "objections": ["Three critical tickets took over 48 hours to get a response"], "signals": []},
            {"ts": 120000, "topic": "features",     "sentiment": "negative", "risk_score": 0.70, "transcript": "The reporting module you requested 8 months ago still hasn't shipped. Your team built a manual workaround that takes 5 hours weekly.",                                                     "objections": ["We were promised this feature in the last renewal", "Our team has lost faith in your roadmap"], "signals": []},
            {"ts": 240000, "topic": "support",       "sentiment": "neutral",  "risk_score": 0.55, "transcript": "I've assigned a dedicated senior support engineer to your account — Maria, who you'll meet tomorrow. She'll personally handle all escalations going forward.",                            "objections": [],                                                           "signals": ["That's a step in the right direction"]},
            {"ts": 360000, "topic": "features",     "sentiment": "neutral",  "risk_score": 0.45, "transcript": "The reporting module is now in beta and will GA in 6 weeks. I'm offering your team early access starting next Monday so you can validate it meets your requirements.",                     "objections": ["We've heard timelines before"],                              "signals": ["Early access would help rebuild trust"]},
            {"ts": 480000, "topic": "pricing",       "sentiment": "hesitant", "risk_score": 0.60, "transcript": "Given everything you've experienced, I'm proposing a 20% discount on the renewal PLUS 3 months free while we deliver the reporting module.",                                              "objections": ["A discount doesn't fix operational issues"],                 "signals": []},
            {"ts": 600000, "topic": "contract",      "sentiment": "neutral",  "risk_score": 0.50, "transcript": "I'll also include quarterly SLA reviews with executive sponsorship from our VP of Customer Success. If we miss SLA three times, you can exit penalty-free.",                              "objections": [],                                                           "signals": ["The performance guarantee is meaningful"]},
            {"ts": 780000, "topic": "competition",    "sentiment": "negative", "risk_score": 0.80, "transcript": "I'll be honest — we've had preliminary conversations with two other vendors. But switching mid-cycle has its own costs.",                                                                "objections": ["We need to see real change, not just promises"],             "signals": []},
            {"ts": 900000, "topic": "timeline",       "sentiment": "neutral",  "risk_score": 0.40, "transcript": "Here's my proposal: 90-day action plan with monthly checkpoints. Each checkpoint has specific deliverables. If we miss any, the exit clause activates immediately.",                     "objections": [],                                                           "signals": ["Put that in writing and I'll present it to our executive team"]},
            {"ts": 1080000,"topic": "support",       "sentiment": "neutral",  "risk_score": 0.35, "transcript": "Maria will reach out tomorrow with an immediate remediation plan for the open tickets. We'll have all 7 resolved by end of next week.",                                                  "objections": [],                                                           "signals": ["Actions speak louder than words — we'll see"]},
        ],
    },
    {
        "url": "https://youtu.be/txJLCdn0ahA?si=pqMjZhZn_KSA8th0",
        "title": "Procurement Negotiation — Multi-Year Enterprise License",
        "company": "GlobalServe Technologies",
        "contact": "Robert Chang",
        "deal_id": "globalserve-proc",
        "rep": "Michael Torres",
        "duration_ms": 1_680_000,   # 28 min
        "scenario": "procurement_negotiation",
        "segments": [
            {"ts": 0,      "topic": "contract",      "sentiment": "neutral",  "risk_score": 0.30, "transcript": "Robert, I have the revised MSA based on your procurement team's redlines. Let me walk through the key changes we've accepted and where we have counter-proposals.",                      "objections": [],                                                           "signals": []},
            {"ts": 90000,  "topic": "legal",         "sentiment": "neutral",  "risk_score": 0.40, "transcript": "We've accepted the liability cap at 12 months of fees, the data processing addendum, and the audit rights clause. The IP indemnification clause needs discussion.",                       "objections": ["Our legal team insists on unlimited liability for IP claims"], "signals": []},
            {"ts": 210000, "topic": "pricing",       "sentiment": "hesitant", "risk_score": 0.55, "transcript": "For the 5-year term with 1000 seats, we're at $42 per seat. Your team requested $35 — we can meet at $38 with a minimum commitment of 800 seats.",                                      "objections": ["$38 is still above our benchmark", "We need flexibility to scale down"], "signals": []},
            {"ts": 360000, "topic": "contract",      "sentiment": "neutral",  "risk_score": 0.35, "transcript": "On the scale-down clause — we'll allow a 10% annual seat reduction without penalty. Larger reductions trigger a price recalculation.",                                                    "objections": [],                                                           "signals": ["10% gives us some flexibility"]},
            {"ts": 480000, "topic": "security",      "sentiment": "neutral",  "risk_score": 0.25, "transcript": "We've updated our data processing agreement to include all requirements from your DPO. Sub-processor notifications will be sent 30 days in advance.",                                   "objections": [],                                                           "signals": ["Our DPO has reviewed and is satisfied"]},
            {"ts": 600000, "topic": "pricing",       "sentiment": "neutral",  "risk_score": 0.45, "transcript": "Let me propose this: $38 per seat for years 1-3, then a CPI-capped increase for years 4-5 not to exceed 3% annually. That gives you cost predictability.",                               "objections": [],                                                           "signals": ["CPI cap at 3% works for our finance team"]},
            {"ts": 780000, "topic": "support",       "sentiment": "positive", "risk_score": 0.15, "transcript": "Enterprise SLA includes 99.95% uptime guarantee with financial credits at 99.9%. Dedicated support pod mean same engineers every time you call.",                                         "objections": [],                                                           "signals": ["That's better than our current vendor's SLA"]},
            {"ts": 900000, "topic": "timeline",       "sentiment": "neutral",  "risk_score": 0.25, "transcript": "If we can finalize legal on the IP clause this week, we're looking at contract execution by end of month and phased deployment starting April 1st.",                                     "objections": [],                                                           "signals": ["Let me schedule a call with our legal team and yours"]},
            {"ts": 1080000,"topic": "contract",      "sentiment": "positive", "risk_score": 0.20, "transcript": "I think we're 90% there. The three open items are IP indemnification scope, minimum seat commitment at 800 vs 750, and the payment terms.",                                               "objections": [],                                                           "signals": ["Agreed — let's close these in the next session"]},
        ],
    },
]


def _youtube_id(url: str) -> str:
    """Extract a short deterministic id from a YouTube URL."""
    h = hashlib.sha256(url.encode()).hexdigest()[:12]
    return f"yt-{h}"


def _build_job_result(video: dict[str, Any], rng: random.Random) -> dict[str, Any]:
    """Build a complete job result dict matching the SegmentPair[] schema the frontend expects."""
    segments = []
    for seg in video["segments"]:
        risk_score = seg["risk_score"]
        risk = "high" if risk_score > 0.6 else "medium" if risk_score > 0.3 else "low"
        segments.append({
            "segment": {
                "timestamp_ms": seg["ts"],
                "transcript": seg["transcript"],
            },
            "extraction": {
                "topic": seg["topic"],
                "sentiment": seg["sentiment"],
                "risk": risk,
                "risk_score": round(risk_score, 3),
                "objections": seg.get("objections", []),
                "decision_signals": seg.get("signals", []),
                "confidence": round(rng.uniform(0.72, 0.96), 2),
                "model_name": rng.choice(["gpt4o", "claude-sonnet"]),
                "latency_ms": rng.randint(800, 3200),
            },
        })

    risk_scores = [s["extraction"]["risk_score"] for s in segments]
    overall_risk = round(sum(risk_scores) / len(risk_scores), 3) if risk_scores else 0.0

    # Speaker intelligence
    rep_talk = round(rng.uniform(0.35, 0.55), 2)
    return {
        "video_path": video["url"],
        "duration_ms": video["duration_ms"],
        "overall_risk_score": overall_risk,
        "segment_count": len(segments),
        "segments": segments,
        "speaker_intelligence": {
            "talk_ratio": {
                "SPEAKER_A": rep_talk,
                "SPEAKER_B": round(1.0 - rep_talk, 2),
            },
            "speaker_stats": {
                "SPEAKER_A": {
                    "words_per_minute": round(rng.uniform(120, 165), 1),
                    "filler_rate": round(rng.uniform(0.01, 0.05), 3),
                    "question_count": rng.randint(3, 15),
                },
                "SPEAKER_B": {
                    "words_per_minute": round(rng.uniform(110, 150), 1),
                    "filler_rate": round(rng.uniform(0.02, 0.07), 3),
                    "question_count": rng.randint(2, 10),
                },
            },
        },
    }


def _flat_segments_for_agents(result: dict) -> dict:
    """Convert SegmentPair[] result into flat-segment format expected by agents."""
    flat_segs = []
    for pair in result["segments"]:
        seg = pair["segment"]
        ext = pair["extraction"]
        flat_segs.append({
            "timestamp_str": _ms_to_ts(seg["timestamp_ms"]),
            "timestamp_ms": seg["timestamp_ms"],
            "transcript": seg["transcript"],
            "extraction": {
                "topic": ext["topic"],
                "sentiment": ext["sentiment"],
                "risk": ext["risk"],
                "risk_score": ext["risk_score"],
                "objections": ext["objections"],
                "decision_signals": ext["decision_signals"],
                "confidence": ext["confidence"],
            },
        })
    return {
        "overall_risk_score": result["overall_risk_score"],
        "duration_ms": result["duration_ms"],
        "segments": flat_segs,
        "speaker_intelligence": result["speaker_intelligence"],
    }


def _ms_to_ts(ms: int) -> str:
    total_s = ms // 1000
    m = total_s // 60
    s = total_s % 60
    return f"{m:02d}:{s:02d}"


def generate_youtube_seed(seed: int = 123) -> dict[str, Any]:
    """Generate job data for all 11 YouTube videos.

    Returns: {jobs: {job_id: {...}}, videos: [...], total: int}
    """
    rng = random.Random(seed)
    jobs: dict[str, dict[str, Any]] = {}

    for video in YOUTUBE_DEMOS:
        job_id = _youtube_id(video["url"])
        result = _build_job_result(video, rng)

        jobs[job_id] = {
            "status": "completed",
            "video_path": video["url"],
            "frames_dir": "",
            "stages_done": [
                "frame_extraction", "transcription", "diarization",
                "speaker_intelligence", "alignment", "extraction",
            ],
            "result": result,
            "error": None,
            # Extra metadata for agents
            "_meta": {
                "title": video["title"],
                "company": video["company"],
                "contact": video["contact"],
                "deal_id": video["deal_id"],
                "rep": video["rep"],
                "url": video["url"],
                "scenario": video["scenario"],
                "created_at": time.time() - rng.randint(86400, 86400 * 45),
            },
        }

    return {
        "jobs": jobs,
        "videos": [v["title"] for v in YOUTUBE_DEMOS],
        "total": len(jobs),
    }


def seed_into_jobs_cache(seed_data: dict[str, Any]) -> int:
    """Inject generated jobs into the in-memory _jobs cache used by the API."""
    from temporalos.api.routes.process import _jobs
    count = 0
    for job_id, job in seed_data["jobs"].items():
        _jobs[job_id] = {
            "status": job["status"],
            "video_path": job["video_path"],
            "frames_dir": job["frames_dir"],
            "stages_done": job["stages_done"],
            "result": job["result"],
            "error": job["error"],
        }
        count += 1
    return count


async def seed_into_db(seed_data: dict[str, Any]) -> int:
    """Persist jobs + search index + Video/Segment/Extraction to the database."""
    try:
        from temporalos.db.session import get_session_factory
        sf = get_session_factory()
        if not sf:
            logger.warning("No DB session — skipping DB persistence")
            return 0

        from temporalos.db.models import (
            JobRecord, SearchDocRecord, Video, VideoStatus, Segment, Extraction,
        )
        from sqlalchemy import select

        count = 0
        async with sf() as sess:
            for job_id, job in seed_data["jobs"].items():
                # Upsert JobRecord
                row = (await sess.execute(
                    select(JobRecord).where(JobRecord.id == job_id)
                )).scalar_one_or_none()

                if row is None:
                    row = JobRecord(id=job_id)
                    sess.add(row)

                row.status = "completed"
                row.video_path = job["video_path"]
                row.frames_dir = ""
                row.stages_done = job["stages_done"]
                row.result = job["result"]
                row.error = None

                meta = job["_meta"]
                result = job["result"]

                # ── Video / Segment / Extraction (for intelligence endpoints) ──
                existing_video = (await sess.execute(
                    select(Video).where(Video.filename == meta["title"])
                )).scalar_one_or_none()

                if existing_video is None:
                    video_row = Video(
                        filename=meta["title"],
                        file_path=meta["url"],
                        status=VideoStatus.COMPLETED,
                        duration_ms=result["duration_ms"],
                        overall_risk_score=result["overall_risk_score"],
                    )
                    sess.add(video_row)
                    await sess.flush()

                    for pair in result["segments"]:
                        seg = pair["segment"]
                        ext = pair["extraction"]
                        ts_str = _ms_to_ts(seg["timestamp_ms"])

                        seg_row = Segment(
                            video_id=video_row.id,
                            timestamp_ms=seg["timestamp_ms"],
                            timestamp_str=ts_str,
                            transcript=seg["transcript"],
                            frame_path="",
                        )
                        sess.add(seg_row)
                        await sess.flush()

                        ext_row = Extraction(
                            segment_id=seg_row.id,
                            model_name=ext["model_name"],
                            topic=ext["topic"],
                            sentiment=ext["sentiment"],
                            risk=ext["risk"],
                            risk_score=ext["risk_score"],
                            objections=ext["objections"],
                            decision_signals=ext["decision_signals"],
                            confidence=ext["confidence"],
                            latency_ms=ext["latency_ms"],
                        )
                        sess.add(ext_row)

                # Search index entries
                for pair in result["segments"]:
                    seg = pair["segment"]
                    ext = pair["extraction"]
                    ts_str = _ms_to_ts(seg["timestamp_ms"])
                    doc_id = f"{job_id}:{ts_str}"
                    doc = SearchDocRecord(
                        id=doc_id,
                        video_id=job_id,
                        timestamp_ms=seg["timestamp_ms"],
                        timestamp_str=ts_str,
                        topic=ext["topic"],
                        risk=ext["risk"],
                        risk_score=ext["risk_score"],
                        objections=ext["objections"],
                        decision_signals=ext["decision_signals"],
                        transcript=seg["transcript"],
                        model=ext["model_name"],
                    )
                    await sess.merge(doc)

                count += 1
            await sess.commit()
        return count
    except Exception as exc:
        logger.warning("DB seed failed: %s", exc)
        return 0


def seed_agents(seed_data: dict[str, Any]) -> dict[str, Any]:
    """Index YouTube demo data into all intelligence agents."""
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

    stats = {
        "qa_indexed": 0, "risk_alerts": 0, "coaching_reps": set(),
        "kg_entities": 0, "prep_indexed": 0,
    }

    for job_id, job in seed_data["jobs"].items():
        meta = job["_meta"]
        intel = _flat_segments_for_agents(job["result"])

        # Q&A index
        stats["qa_indexed"] += qa.index_job(job_id, intel)

        # Risk alerts
        alerts = risk.record_job(
            job_id, intel, meta["company"], meta["deal_id"],
        )
        stats["risk_alerts"] += len(alerts)

        # Coaching
        coaching.record_call(meta["rep"], job_id, intel)
        stats["coaching_reps"].add(meta["rep"])

        # Knowledge graph
        stats["kg_entities"] += kg.add_video(job_id, intel)

        # Meeting prep
        prep.index_job(
            job_id, intel,
            company=meta["company"], contact=meta["contact"],
        )
        stats["prep_indexed"] += 1

    stats["coaching_reps"] = len(stats["coaching_reps"])
    return stats


def seed_search_index(seed_data: dict[str, Any]) -> int:
    """Populate the in-memory TF-IDF search index."""
    try:
        from temporalos.search.indexer import IndexEntry, get_search_index
        idx = get_search_index()
        count = 0
        for job_id, job in seed_data["jobs"].items():
            for pair in job["result"]["segments"]:
                seg = pair["segment"]
                ext = pair["extraction"]
                entry = IndexEntry(
                    doc_id=f"{job_id}:{_ms_to_ts(seg['timestamp_ms'])}",
                    video_id=job_id,
                    timestamp_ms=seg["timestamp_ms"],
                    timestamp_str=_ms_to_ts(seg["timestamp_ms"]),
                    topic=ext["topic"],
                    risk=ext["risk"],
                    risk_score=ext["risk_score"],
                    objections=ext["objections"],
                    decision_signals=ext["decision_signals"],
                    transcript=seg["transcript"],
                    model=ext["model_name"],
                )
                idx.index(entry)
                count += 1
        return count
    except Exception as exc:
        logger.warning("Search index seed failed: %s", exc)
        return 0


async def seed_all(seed: int = 123) -> dict[str, Any]:
    """Generate + seed everything: cache, DB, agents, search."""
    data = generate_youtube_seed(seed)

    cache_count = seed_into_jobs_cache(data)
    db_count = await seed_into_db(data)
    agent_stats = seed_agents(data)
    search_count = seed_search_index(data)

    summary = {
        "jobs_seeded": data["total"],
        "cache_loaded": cache_count,
        "db_persisted": db_count,
        "search_indexed": search_count,
        **agent_stats,
    }

    logger.info(
        "YouTube demo seed complete: %d jobs, %d cached, %d DB, "
        "%d search docs, %d QA, %d risk alerts, %d reps, %d KG entities",
        data["total"], cache_count, db_count, search_count,
        agent_stats["qa_indexed"], agent_stats["risk_alerts"],
        agent_stats["coaching_reps"], agent_stats["kg_entities"],
    )
    return summary


# ── CLI entry point ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

    reset = "--reset" in sys.argv

    if reset:
        logger.info("Resetting: clearing _jobs cache before seeding")
        from temporalos.api.routes.process import _jobs
        _jobs.clear()

    result = asyncio.run(seed_all())
    print("\n=== YouTube Demo Seed Results ===")
    for k, v in result.items():
        print(f"  {k}: {v}")
