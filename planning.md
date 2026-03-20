# TemporalOS — Planning & Architecture

> Last updated: 2026-03-20

---

## 1. Vision Statement

Transform raw video into structured, queryable decision intelligence. A sales call isn't just audio — it's a timestamped graph of intent, objection, sentiment, and visual context. TemporalOS makes that graph machine-consumable.

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        INPUT LAYER                              │
│  Video File (.mp4/.webm) OR Live Stream (RTMP/WebRTC)          │
└──────────────┬──────────────────────────────────┬───────────────┘
               │                                  │
       ┌───────▼────────┐                ┌────────▼───────┐
       │ VIDEO PIPELINE  │                │ AUDIO PIPELINE │
       │                 │                │                │
       │ • Frame extract │                │ • Deepgram     │
       │   (FFmpeg)      │                │   streaming    │
       │ • Scene detect  │                │ • Whisper      │
       │ • Keyframe      │                │   (local/batch)│
       │   selection     │                │ • Diarization  │
       └───────┬─────────┘                └────────┬───────┘
               │                                   │
       ┌───────▼─────────┐                ┌────────▼───────┐
       │ VISION ANALYSIS  │                │ TRANSCRIPT     │
       │                  │                │ PROCESSOR      │
       │ • Slide detect   │                │                │
       │ • OCR extraction │                │ • Chunking     │
       │ • UI recognition │                │ • Speaker ID   │
       │ • Chart/table    │                │ • Sentence     │
       │   parsing        │                │   boundaries   │
       └───────┬──────────┘                └────────┬───────┘
               │                                    │
               └──────────────┬─────────────────────┘
                              │
                   ┌──────────▼──────────┐
                   │ TEMPORAL ALIGNMENT   │
                   │                      │
                   │ • Frame ↔ Transcript │
                   │ • Multimodal fusion  │
                   │ • Timeline graph     │
                   └──────────┬───────────┘
                              │
                   ┌──────────▼──────────┐
                   │ STRUCTURED           │
                   │ EXTRACTION           │
                   │                      │
                   │ • LoRA fine-tuned    │
                   │   model              │
                   │ • Prompt-based       │
                   │   (zero-shot backup) │
                   │ • Schema validation  │
                   └──────────┬───────────┘
                              │
                   ┌──────────▼──────────┐
                   │ OUTPUT / API         │
                   │                      │
                   │ • Structured JSON    │
                   │ • Dashboard          │
                   │ • Webhooks           │
                   │ • Search index       │
                   └─────────────────────┘

              ═══════════════════════════════
              ║    OBSERVABILITY LAYER      ║
              ║                             ║
              ║ • OpenTelemetry traces      ║
              ║ • Pipeline latency metrics  ║
              ║ • Extraction accuracy       ║
              ║ • Model drift detection     ║
              ║ • Cost tracking (API calls) ║
              ═══════════════════════════════
```

---

## 3. Module Deep Dive

### 3.1 Video Processing Module
**Purpose**: Extract analyzable frames from video input

| Component | Tool | Notes |
|-----------|------|-------|
| Frame extraction | FFmpeg | Extract every N seconds OR on scene change |
| Scene detection | PySceneDetect | Content-aware cuts, threshold-based |
| Keyframe selection | Custom | Reduce redundant frames (similarity hash) |
| Format handling | FFmpeg | Support mp4, webm, mkv, mov |

**Key decisions**:
- Fixed-interval vs adaptive frame extraction? → Start with fixed (1 frame/2sec), add adaptive later
- Resolution for vision models? → Resize to 1024px max dimension to balance quality/cost

### 3.2 Vision + OCR Module
**Purpose**: Extract visual information from frames

| Component | Approach | Notes |
|-----------|----------|-------|
| Slide detection | Classification model or heuristic | Detect presentation slides vs face vs screen |
| OCR | EasyOCR (local) / GPT-4o vision | Structured text extraction |
| UI recognition | Vision LLM | Identify software interfaces, forms |
| Chart/table parsing | Vision LLM + custom | Extract data from visible charts |

**Expansion opportunity**: 
- Compare GPT-4o vs Claude Vision vs Qwen2.5-VL vs LLaVA for accuracy/cost
- Build a **vision model benchmark** specific to sales/demo video content
- Table structure recognition is a hard sub-problem worth isolating

### 3.3 Audio Pipeline Module
**Purpose**: Convert speech to timestamped text

| Component | Tool | Notes |
|-----------|------|-------|
| Batch ASR | Whisper (local) | whisper-large-v3, insanely-fast-whisper |
| Streaming ASR | Deepgram Nova-2 | Real-time with word-level timestamps |
| Speaker diarization | pyannote-audio | Who said what |
| Language detection | Whisper built-in | Multi-language support |

**Key decisions**:
- Streaming vs batch? → Support both. Batch for uploaded files, streaming for live
- Word-level vs sentence-level timestamps? → Word-level, aggregate to sentences

### 3.4 Temporal Alignment Module (THE HARD PART)
**Purpose**: Fuse visual and audio streams into a unified timeline

This is the core differentiator. At any timestamp `t`, you need:
```
{
  "t": "12:32",
  "frame": { "type": "slide", "ocr_text": "Enterprise Plan: $499/mo", "objects": [...] },
  "transcript": { "speaker": "sales_rep", "text": "So this is our enterprise tier..." },
  "audio_features": { "pace": "slow", "confidence": 0.8 }
}
```

**Alignment strategies**:
1. **Timestamp-based join** (simple) — nearest-neighbor match of frame timestamps to transcript word timestamps
2. **Cross-modal attention** (advanced) — model learns to attend across modalities
3. **Event-based anchor points** — use slide transitions or speaker changes as alignment anchors

**Start with #1, evolve to #3, research #2.**

### 3.5 Structured Extraction Module (FINE-TUNING FOCUS)
**Purpose**: Extract business intelligence from aligned multimodal segments

**What to extract**:
- Objections ("That's too expensive", "We're already using X")
- Decision signals ("Let me bring in my manager", "Can you send a proposal?")
- Sentiment per segment (positive/neutral/negative/hesitant)
- Topics (pricing, features, competition, timeline, security)
- Risk indicators (ghosting risk, champion loss, competitor mention)
- Action items mentioned

**Fine-tuning approach**:
1. **Phase 1**: Prompt engineering with GPT-4o / Claude — establish baseline
2. **Phase 2**: Collect annotations, build dataset (100-500 examples)
3. **Phase 3**: LoRA fine-tune Mistral-7B or Llama-3-8B using PEFT
4. **Phase 4**: Distill to smaller model for production (Phi-3, Qwen2.5-3B)

**Dataset structure**:
```json
{
  "input": "<aligned_segment with visual + transcript context>",
  "output": {
    "topic": "pricing",
    "sentiment": "hesitant",
    "objections": ["Price is higher than competitor"],
    "decision_signals": [],
    "risk_level": "high"
  }
}
```

### 3.6 Observability Module
**Purpose**: Production-grade monitoring of the entire pipeline

| Metric | Type | Tool |
|--------|------|------|
| Pipeline latency (per stage) | Histogram | OpenTelemetry + Prometheus |
| ASR word error rate | Gauge | Custom eval against ground truth |
| Extraction accuracy (precision/recall) | Gauge | DeepEval + custom |
| Model confidence distribution | Histogram | Custom |
| Drift detection | Alert | Evidently AI / custom |
| API cost per video | Counter | Custom middleware |
| Frame processing throughput | Counter | OpenTelemetry |
| Queue depth (async pipeline) | Gauge | Celery/Temporal metrics |

**Key observability features to build**:
- **Confidence calibration** — is model's 0.8 confidence actually 80% accurate?
- **Drift detection** — statistical tests on extraction distribution over time
- **Human-in-the-loop feedback** — flag low-confidence extractions for review
- **A/B comparison** — run two models side-by-side, compare outputs

---

## 4. Phased Roadmap

### Phase 1: Foundation (Weeks 1-2)
- [ ] Project scaffolding (Python package structure, configs, CI)
- [ ] FFmpeg video → frame extraction pipeline
- [ ] Whisper batch transcription pipeline
- [ ] Basic timestamp alignment (nearest-neighbor)
- [ ] Prompt-based extraction (GPT-4o/Claude) — no fine-tuning yet
- [ ] Basic FastAPI endpoint: upload video → get JSON
- [ ] OpenTelemetry instrumentation from day one

### Phase 2: Vision & Multimodal (Weeks 3-4)
- [ ] Vision model integration (GPT-4o vision / Claude Vision)
- [ ] Slide detection + OCR pipeline
- [ ] UI screen recognition
- [ ] Vision model benchmarking (compare 3-4 models)
- [ ] Enhanced temporal alignment with visual anchors
- [ ] Dashboard for visualizing aligned timeline

### Phase 3: Real-time Streaming (Weeks 5-6)
- [ ] Deepgram streaming ASR integration
- [ ] Real-time frame capture from live stream
- [ ] WebSocket API for streaming results
- [ ] Partial/incremental structured extraction
- [ ] Streaming observability (latency percentiles, buffer health)

### Phase 4: Fine-tuning (Weeks 7-9)
- [ ] Annotation tool / pipeline for labeling segments
- [ ] Dataset creation from prompt-based extractions (bootstrap)
- [ ] LoRA fine-tune Mistral/Llama on extraction task
- [ ] Evaluation framework: accuracy, latency, cost comparison
- [ ] Model versioning and A/B testing infrastructure

### Phase 5: Production Observability (Weeks 10-11)
- [ ] Drift detection pipeline (Evidently AI or custom)
- [ ] Confidence calibration analysis
- [ ] Grafana dashboards for all metrics
- [ ] Alerting on accuracy degradation
- [ ] Human-in-the-loop review queue
- [ ] Cost optimization analysis (local vs API models)

### Phase 6: Polish & Expand (Week 12+)
- [ ] Local SLM option (Phi-3 / Qwen2.5 running locally)
- [ ] Multi-language support
- [ ] Batch processing (process video library)
- [ ] Export to CRM integrations
- [ ] Documentation and demo videos

---

## 5. Expansion Ideas (Beyond Core)

### 5.1 Competitive Intelligence Mode
Instead of sales calls, point it at **product demo videos of competitors**. Extract feature comparisons, positioning, pricing signals.

### 5.2 Training & Coaching
Use extraction outputs to build a **sales coaching engine** — identify what top reps do differently (talk/listen ratio, objection handling speed, demo flow).

### 5.3 Meeting Intelligence (General)
Expand beyond sales to any meeting: board meetings, engineering standups, customer support calls. Different extraction schemas per domain.

### 5.4 Video Search Engine
Build a semantic search layer over extracted data. "Find all moments where a customer mentioned a competitor" → returns timestamped clips.

### 5.5 Multi-Camera / Multi-Stream
Handle Zoom recordings with gallery view — detect and track multiple participants, extract individual reactions.

### 5.6 Synthetic Data Generation
Use the extraction pipeline in reverse — generate training data by creating synthetic sales call videos with known ground truth.

---

## 6. Key Technical Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Temporal alignment accuracy | Core functionality breaks | Start simple, iterate with evaluation |
| Vision model costs at scale | Budget blowout | Local models (Qwen-VL, LLaVA) as fallback |
| ASR accuracy on noisy calls | Bad downstream extraction | Multi-model ensemble, confidence filtering |
| Fine-tuning data quality | Model doesn't improve | Active learning loop, quality annotations |
| Real-time latency budget | Streaming unusable | Profile early, optimize critical path |

---

## 7. Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-03-20 | Python as primary language | ML ecosystem, team expertise |
| 2026-03-20 | Start with batch, add streaming later | Reduce early complexity |
| 2026-03-20 | OpenTelemetry from day one | Observability is a core learning goal |
| 2026-03-20 | Prompt-based extraction first, fine-tune later | Need data before fine-tuning |
| 2026-03-20 | DeepEval for evaluation framework | Already initialized in project |
