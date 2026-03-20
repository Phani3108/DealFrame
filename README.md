<div align="center">

# TemporalOS

**Video → Structured Decision Intelligence Engine**

*Convert sales calls, demos, and walkthroughs into machine-queryable intelligence*

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)](https://fastapi.tiangolo.com)
[![Tests](https://img.shields.io/badge/tests-34%20passing-brightgreen.svg)](#testing)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

</div>

---

## What is TemporalOS?

Video is wasted data. A sales call contains timestamped objections, decision signals, pricing reactions, and competitive mentions — all buried in an unstructured mp4. TemporalOS extracts it into a structured, queryable intelligence graph.

**Input**: a sales call video  
**Output**:
```json
{
  "segments": [
    {
      "timestamp": "12:32",
      "topic": "pricing",
      "customer_sentiment": "hesitant",
      "risk": "high",
      "risk_score": 0.75,
      "objections": ["The price seems high compared to competitors"],
      "decision_signals": ["Can you send a proposal?"],
      "model": "gpt4o"
    }
  ],
  "overall_risk_score": 0.67
}
```

---

## Architecture

```
Video File / Live Stream
        │
   ┌────▼─────┐      ┌──────────────┐
   │  FFmpeg  │      │   Whisper    │
   │  Frames  │      │  Transcript  │
   └────┬─────┘      └──────┬───────┘
        │                   │
        └──────────┬─────────┘
                   │
          ┌────────▼────────┐
          │    Temporal     │
          │    Alignment    │   ← frame ↔ transcript fusion
          └────────┬────────┘
                   │
          ┌────────▼────────┐
          │   Structured    │
          │   Extraction    │   ← GPT-4o / Claude / Qwen2.5-VL / fine-tuned
          └────────┬────────┘
                   │
          ┌────────▼────────┐
          │  FastAPI  JSON  │
          └─────────────────┘

    ════════════════════════════════
    ║     Observability Layer      ║   ← OpenTelemetry spans on every stage
    ════════════════════════════════
```

---

## Core Learning Goals

This project is intentionally scoped around three deep skill areas:

| Goal | What We Build |
|------|--------------|
| **Monitoring & Observability** | OpenTelemetry on every pipeline stage, accuracy tracking, drift detection |
| **Real-time Multimodal** | Streaming ASR + live frame capture + incremental extraction |
| **Fine-tuning** | Full LoRA arc: dataset collection → training → eval → deploy |

---

## Project Phases

| Phase | Name | Status |
|-------|------|--------|
| **0** | Project Scaffold | ✅ Done |
| **1** | Walking Skeleton (FFmpeg + Whisper + GPT-4o) | ✅ Done |
| **2** | Comparative Model Observatory (GPT-4o vs Claude vs Qwen2.5-VL) | 🔜 Next |
| **3** | Multi-video Intelligence (portfolio analytics) | 📅 Planned |
| **4** | Fine-tuning Arc (LoRA on Mistral-7B) | 📅 Planned |
| **5** | Local SLM Pipeline (zero API calls) | 📅 Planned |

---

## Quick Start

### Prerequisites

- Python 3.11+
- [FFmpeg](https://ffmpeg.org/download.html) (`brew install ffmpeg` on macOS)
- PostgreSQL (via Docker — included)
- OpenAI API key (for Phase 1/2 extraction)

### Setup

```bash
# Clone
git clone https://github.com/Phani3108/TemporalOS.git
cd TemporalOS

# Environment
cp .env.example .env
# Edit .env — set OPENAI_API_KEY, optionally set AUDIO__WHISPER_MODEL=base for fast dev

# Install
pip install -e ".[audio,dev]"

# Start Postgres
make db-up

# Start API
make dev
# → http://localhost:8000
# → http://localhost:8000/docs
```

### Process a video

```bash
# Via Makefile
make process VIDEO=my_call.mp4

# Or directly
curl -X POST http://localhost:8000/api/v1/process \
  -F "file=@my_call.mp4"
# → {"job_id": "abc-123", "status": "pending"}

curl http://localhost:8000/api/v1/jobs/abc-123
# → {"status": "completed", "result": {...}}
```

---

## Testing

End-to-end tests are **mandatory** after every phase (see [claude.md](claude.md) §0).  
Tests generate synthetic videos via FFmpeg — no external assets required.  
External API calls are mocked.

```bash
# Unit tests (fast)
make test
# → 25 passed

# End-to-end tests (tests the full pipeline)
make test-e2e
# → 9 passed

# All tests
make test-all
```

**Current test status**: `34 passed, 0 failed`

---

## Project Structure

```
TemporalOS/
├── temporalos/
│   ├── api/            # FastAPI app + routes
│   ├── alignment/      # Temporal frame↔transcript fusion
│   ├── audio/          # Whisper batch transcription
│   ├── core/           # Shared types (Frame, Word, AlignedSegment, ExtractionResult)
│   ├── db/             # SQLAlchemy models + async session
│   ├── extraction/     # BaseExtractionModel + adapters (GPT-4o, Claude, fine-tuned)
│   ├── ingestion/      # FFmpeg frame extraction
│   ├── intelligence/   # Multi-video aggregation (Phase 3)
│   ├── local/          # Local SLM pipeline (Phase 5)
│   ├── observatory/    # Multi-model comparison framework (Phase 2)
│   ├── observability/  # OpenTelemetry telemetry singleton
│   └── vision/         # BaseVisionModel + adapters (Phase 2)
├── tests/
│   ├── conftest.py     # Shared fixtures (synthetic test video, sample data)
│   ├── unit/           # Unit tests per module
│   └── e2e/            # End-to-end pipeline tests (one file per phase)
├── evals/              # DeepEval evaluation suite
├── config/
│   └── settings.yaml   # Default configuration
├── claude.md           # Project rules & conventions (read this first)
├── planning.md         # Architecture, decisions, phased roadmap
├── tasks.md            # Complete task audit log
├── Makefile            # dev / test / test-e2e / process / db-up
├── docker-compose.yml  # PostgreSQL service
└── pyproject.toml      # Dependencies (core, audio, vision, finetuning, dev)
```

---

## Configuration

All settings live in `config/settings.yaml` and can be overridden via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | — | OpenAI API key (required for gpt4o mode) |
| `ANTHROPIC_API_KEY` | — | Anthropic API key (Phase 2) |
| `TEMPORALOS_MODE` | `api` | `api` (cloud models) or `local` (offline, Phase 5) |
| `AUDIO__WHISPER_MODEL` | `large-v3` | Whisper model size (`base` for fast dev) |
| `VIDEO__FRAME_INTERVAL_SECONDS` | `2` | Frame extraction frequency |
| `DATABASE_URL` | postgres://... | PostgreSQL connection string |

---

## Observability

Every pipeline stage emits OpenTelemetry spans:

```
pipeline.run
  ├── ingestion.extract_frames    (duration, frame_count)
  ├── audio.transcribe            (duration, word_count, model)
  ├── alignment.align             (frame_count, non_empty_segments)
  └── extraction.gpt4o            (duration, latency_ms, timestamp_ms)
```

Set `TELEMETRY__OTLP_ENDPOINT=http://localhost:4317` to send traces to any OTEL-compatible backend (Jaeger, Grafana Tempo, etc.). Defaults to console output in development.

---

## Roadmap: Expansion Beyond the Skeleton

### Phase 2 — Comparative Model Observatory
Run the same video through GPT-4o Vision, Claude Sonnet Vision, and Qwen2.5-VL simultaneously. Get a benchmark report: accuracy per model, latency, cost per 1000 frames, and a disagreement heatmap showing exactly where models diverge.

### Phase 3 — Multi-video Intelligence
Portfolio-level analytics across a library of calls:
- "What are the top 5 objections this quarter?"
- Risk score trends over time
- Topic frequency heatmaps
- Competitor mention counts

### Phase 4 — Full LoRA Fine-tuning Arc
Collect annotations from Observatory outputs → fine-tune Mistral-7B-Instruct with LoRA (PEFT + Unsloth) → evaluate against GPT-4o teacher → deploy as a 1/20th cost replacement.

### Phase 5 — Local SLM Pipeline
Complete offline pipeline: Whisper + Qwen2.5-VL + fine-tuned model. Zero API calls. Designed to run on an M-series Mac or any CUDA GPU. Full cost/accuracy benchmark vs the cloud pipeline.

---

## Key Files

- [claude.md](claude.md) — Project rules, conventions, strict requirements (read first)
- [planning.md](planning.md) — Full architecture, design decisions, decision log
- [tasks.md](tasks.md) — Complete audit trail of every task and prompt

---

## License

MIT
