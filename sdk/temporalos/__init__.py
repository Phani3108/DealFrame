"""TemporalOS Python SDK — official client library.

Install:
    pip install temporalos-sdk

Quick start:
    from temporalos import TemporalOSClient
    client = TemporalOSClient(base_url="http://localhost:8000")
    job = client.process("https://example.com/call.mp4")
    intel = client.get_intelligence(job["job_id"])
    answer = client.ask("What were the top objections?")
"""
from temporalos.sdk.client import TemporalOSClient
from temporalos.sdk.types import (
    Job, Intelligence, SearchResult, QAAnswer, RiskAlert,
    CoachingCard, MeetingBrief, BatchJob, Webhook, Schema,
)

__version__ = "0.1.0"
__all__ = [
    "TemporalOSClient",
    "Job", "Intelligence", "SearchResult", "QAAnswer", "RiskAlert",
    "CoachingCard", "MeetingBrief", "BatchJob", "Webhook", "Schema",
]
