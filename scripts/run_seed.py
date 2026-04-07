"""Directly seed YouTube demo data into the database.

Run: python3 scripts/run_seed.py
"""
import asyncio
import sys
import os
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./dealframe_dev.db")

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

from scripts.seed_youtube_demo import generate_youtube_seed, seed_agents, seed_search_index, _ms_to_ts


async def main():
    # Init DB
    from temporalos.db.session import init_db, get_session_factory
    await init_db()
    sf = get_session_factory()
    if not sf:
        print("ERROR: No DB session factory available")
        return

    from temporalos.db.models import (
        JobRecord, SearchDocRecord, Video, VideoStatus, Segment, Extraction,
    )
    from sqlalchemy import select

    data = generate_youtube_seed()
    print(f"\nSeeding {data['total']} YouTube demo jobs into DB...")

    async with sf() as sess:
        for job_id, job in data["jobs"].items():
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

            # ── Video / Segment / Extraction tables (for intelligence endpoints) ──
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
                await sess.flush()  # get video_row.id

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
                    await sess.flush()  # get seg_row.id

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

            print(f"  OK  {job_id}: {meta['title'][:55]}")

        await sess.commit()

    seg_count = sum(len(j['result']['segments']) for j in data['jobs'].values())
    print(f"\nDB seeded: {data['total']} jobs, {seg_count} segments (Video+Segment+Extraction + JobRecord + SearchDoc)")

    # Seed agents (in-memory)
    print("\nSeeding agents (Q&A, risk, coaching, KG, meeting prep)...")
    agent_stats = seed_agents(data)
    print(f"  QA indexed: {agent_stats['qa_indexed']}")
    print(f"  Risk alerts: {agent_stats['risk_alerts']}")
    print(f"  Coaching reps: {agent_stats['coaching_reps']}")
    print(f"  KG entities: {agent_stats['kg_entities']}")
    print(f"  Meeting prep: {agent_stats['prep_indexed']}")

    # Seed search index
    print("\nSeeding search index...")
    search_count = seed_search_index(data)
    print(f"  Search docs: {search_count}")

    print("\n=== YouTube Demo Seed Complete ===")


asyncio.run(main())
