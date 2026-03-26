"""Generate a demo supplier negotiation video for Jaggaer pitch.

Creates a synthetic video with burned-in captions simulating a procurement
negotiation call between a buyer and a chemical raw-material supplier.
Uses FFmpeg — no external assets needed.

Usage:
    python scripts/demo_procurement.py
    # produces demo_procurement_negotiation.mp4 in project root
"""
from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

# Each segment: (start_sec, duration_sec, speaker, text, color_hex)
SEGMENTS = [
    # --- Opening / RFP review stage ---
    (0, 8, "BUYER — Maria (Category Mgr)",
     "Thanks for joining.  We received your response to our RFP for industrial "
     "adhesives.  Your pricing came in at $4.20 per unit for the RA-500 line.  "
     "I want to walk through a few areas before we finalize.",
     "3B82F6"),  # blue

    (8, 7, "SUPPLIER — James (Account Exec)",
     "Absolutely.  The $4.20 reflects our standard volume pricing at 10,000 "
     "units per quarter.  We can do $3.95 if you commit to 25,000.",
     "10B981"),  # green

    # --- Pricing negotiation ---
    (15, 7, "BUYER — Maria",
     "We have other suppliers quoting between $3.60 and $3.80.  At $4.20 you're "
     "above market.  What flexibility do you have?",
     "3B82F6"),

    (22, 8, "SUPPLIER — James",
     "I understand the competitive landscape.  We could go down to $3.85 at "
     "15,000 units with a two-year commitment.  That includes the sustainability "
     "certification your ESG team requires.",
     "10B981"),

    # --- Delivery risk discussion ---
    (30, 7, "BUYER — Maria",
     "Your lead times last quarter averaged 18 days versus the 12-day SLA.  "
     "We had two production stoppages.  What's changed?",
     "3B82F6"),

    (37, 8, "SUPPLIER — James",
     "We've invested in a secondary production line.  We can confirm 10-day "
     "lead times with a 99.5% on-time delivery KPI going forward.  We will "
     "include a penalty clause — 2% credit per late shipment.",
     "10B981"),

    # --- Contract clause objection ---
    (45, 7, "BUYER — Maria",
     "On the contract terms — we can't accept the auto-renewal clause or the "
     "limitation of liability cap at $50,000.  Our legal team will redline "
     "both sections.",
     "3B82F6"),

    (52, 6, "SUPPLIER — James",
     "We could consider removing auto-renewal.  The liability cap is subject "
     "to approval from our legal — let me check and get back to you.",
     "10B981"),

    # --- Compliance / ESG ---
    (58, 7, "BUYER — Maria",
     "We need ISO 14001 and your carbon footprint audit by Q3.  Our board "
     "has an ESG mandate — non-negotiable.",
     "3B82F6"),

    (65, 6, "SUPPLIER — James",
     "ISO 14001 is confirmed — certificate is attached.  Carbon audit is "
     "in progress, estimated completion by end of Q2.  We guarantee delivery.",
     "10B981"),

    # --- Total cost of ownership ---
    (71, 7, "BUYER — Maria",
     "I need the total cost picture — shipping, storage, and integration cost "
     "included.  The hidden costs last year added 12% on top of unit price.",
     "3B82F6"),

    (78, 7, "SUPPLIER — James",
     "We'll include DDP shipping and provide a dedicated storage allocation at "
     "our regional warehouse.  Total cost of ownership should drop below $4.10 "
     "all-in at 20,000 units.",
     "10B981"),

    # --- Verbal agreement / closing ---
    (85, 7, "BUYER — Maria",
     "If you can lock in $3.85 per unit, 10-day lead times with penalty, remove "
     "auto-renewal, and deliver the carbon audit by Q2 — we have a deal.  I'll "
     "start the contract in Jaggaer.",
     "3B82F6"),

    (92, 8, "SUPPLIER — James",
     "Agreed.  I'll send the revised terms by Friday.  Looking forward to a "
     "strong partnership.  Thank you, Maria.",
     "10B981"),
]


def generate_demo_video(output_path: str = "demo_procurement_negotiation.mp4") -> Path:
    """Build a synthetic negotiation video with FFmpeg.

    Uses color fields only (no drawtext, which requires libfreetype).
    Alternates blue (buyer) and green (supplier) backgrounds.
    """
    total_duration = max(s + d for s, d, *_ in SEGMENTS) + 2

    # Build concat filter: alternate blue/green color segments for buyer/supplier
    inputs = []
    concat_parts = []
    for i, (start, dur, speaker, text, color) in enumerate(SEGMENTS):
        inputs.extend(["-f", "lavfi", "-i",
                       f"color=c=0x{color}30:s=1280x720:d={dur}:r=24"])
        concat_parts.append(f"[{i + 2}:v]")

    # Base dark background for full duration (input 0 = video, 1 = audio)
    concat_filter = "".join(concat_parts) + f"concat=n={len(SEGMENTS)}:v=1:a=0[outv]"

    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=c=0x1E293B:s=1280x720:d={total_duration}:r=24",
        "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo:d={total_duration}",
        *inputs,
        "-filter_complex", concat_filter,
        "-map", "[outv]", "-map", "1:a",
        "-c:v", "libx264", "-preset", "ultrafast",
        "-c:a", "aac", "-shortest",
        "-t", str(total_duration),
        output_path,
    ]

    print(f"Generating {output_path} ({total_duration}s)...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        # Fallback: simplest possible video
        print("Complex filter failed, using simple fallback...")
        cmd_simple = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"color=c=0x1E293B:s=1280x720:d={total_duration}:r=24",
            "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo:d={total_duration}",
            "-c:v", "libx264", "-preset", "ultrafast",
            "-c:a", "aac", "-shortest",
            "-t", str(total_duration),
            output_path,
        ]
        subprocess.run(cmd_simple, check=True, capture_output=True)
    out = Path(output_path)
    print(f"Done: {out.resolve()} ({out.stat().st_size / 1024:.0f} KB)")
    return out


# Also export the transcript for testing
TRANSCRIPT_TEXT = "\n".join(
    f"[{s}s-{s+d}s] {speaker}: {text}"
    for s, d, speaker, text, _ in SEGMENTS
)


if __name__ == "__main__":
    generate_demo_video()
    print("\nFull transcript:")
    print(TRANSCRIPT_TEXT)
