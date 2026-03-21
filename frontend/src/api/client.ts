// ─── Types ────────────────────────────────────────────────────────────────────

export interface ExtractionResult {
  topic: string
  sentiment: string
  risk: 'low' | 'medium' | 'high'
  risk_score: number
  objections: string[]
  decision_signals: string[]
  confidence: number
  model_name: string
  latency_ms: number
}

export interface AlignedSegment {
  timestamp_ms: number
  transcript: string
}

export interface SegmentPair {
  segment: AlignedSegment
  extraction: ExtractionResult
}

export interface VideoIntelligence {
  video_path: string
  duration_ms: number
  overall_risk_score: number
  segments: SegmentPair[]
}

export interface Job {
  job_id: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  created_at?: string
  result?: VideoIntelligence
  error?: string
}

export interface Objection {
  text: string
  count: number
  risk_avg: number
}

export interface TopicTrend {
  topic: string
  daily_counts: Record<string, number>
}

export interface RiskSummary {
  high: number
  medium: number
  low: number
  average_score: number
}

export interface LocalStatus {
  whisper_available: boolean
  whisper_model: string
  qwen_vl_available: boolean
  finetuned_adapter_available: boolean
  adapter_path: string | null
  active_extractor: string
  cost_per_video_usd: number
}

export interface ObservatorySession {
  session_id: string
  status: string
  models?: string[]
  agreement_score?: number
  report?: {
    overall_agreement: number
    pairwise_topic_agreement: Record<string, number>
    model_stats: Record<string, { avg_confidence: number; avg_latency_ms: number }>
  }
  created_at?: string
}

export interface FinetuningRun {
  id: string
  name: string
  status: string
  created_at: string
  adapter_path?: string
  dataset_path?: string
  training_metrics?: {
    train_loss: number
    val_loss: number
    epochs_completed: number
    total_steps: number
  }
  error?: string
}

export interface BenchmarkComparison {
  local: { total_latency_ms: number; model_name: string }
  api: { total_latency_ms: number; model_name: string }
  latency_ratio: number
  local_is_faster: boolean
  cost_savings_usd: number
  verdict: string
}

// ─── HTTP helper ─────────────────────────────────────────────────────────────

const BASE = '/api/v1'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, options)
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(`${res.status}: ${text}`)
  }
  return res.json() as Promise<T>
}

// ─── Process ──────────────────────────────────────────────────────────────────

export const processVideo = (file: File, useVision = false) => {
  const form = new FormData()
  form.append('file', file)
  return request<{ job_id: string; status: string }>(
    `/process?use_vision=${useVision}`,
    { method: 'POST', body: form },
  )
}

export const getJob = (jobId: string) => request<Job>(`/jobs/${jobId}`)

export const listJobs = () =>
  request<{ jobs: Job[]; total: number }>('/jobs')

// ─── Observatory ─────────────────────────────────────────────────────────────

export const startObservatory = (file: File) => {
  const form = new FormData()
  form.append('file', file)
  return request<{ session_id: string; status: string }>(
    '/observatory/compare',
    { method: 'POST', body: form },
  )
}

export const getObservatorySession = (id: string) =>
  request<ObservatorySession>(`/observatory/sessions/${id}`)

export const listObservatorySessions = () =>
  request<{ sessions: ObservatorySession[]; total: number }>('/observatory/sessions')

// ─── Intelligence ─────────────────────────────────────────────────────────────

export const getObjections = (limit = 10) =>
  request<{ objections: Objection[] }>(`/intelligence/objections?limit=${limit}`)

export const getTopicTrends = () =>
  request<{ topics: TopicTrend[] }>('/intelligence/topics/trend')

export const getRiskSummary = () =>
  request<RiskSummary>('/intelligence/risk/summary')

// ─── Fine-tuning ─────────────────────────────────────────────────────────────

export const getDatasetStats = () =>
  request<{
    total_examples: number
    class_distribution: Record<string, Record<string, number>>
  }>('/finetuning/dataset/stats')

export const startTraining = (
  name: string,
  trainPath: string,
  valPath: string,
  dryRun = false,
) => request<{ experiment_id: string; status: string }>(
  `/finetuning/train?name=${encodeURIComponent(name)}&train_path=${encodeURIComponent(trainPath)}&val_path=${encodeURIComponent(valPath)}&dry_run=${dryRun}`,
  { method: 'POST' },
)

export const listFinetuningRuns = () =>
  request<{ experiments: FinetuningRun[]; total: number }>('/finetuning/runs')

export const getFinetuningRun = (id: string) =>
  request<FinetuningRun>(`/finetuning/runs/${id}`)

export const getBestModel = () =>
  request<FinetuningRun>('/finetuning/best')

export const activateModel = (id: string) =>
  request<{ activated: boolean; adapter_path: string }>(
    `/finetuning/runs/${id}/activate`,
    { method: 'POST' },
  )

// ─── Local pipeline ──────────────────────────────────────────────────────────

export const getLocalStatus = () =>
  request<LocalStatus>('/local/status')

export const processLocally = (file: File) => {
  const form = new FormData()
  form.append('file', file)
  return request<{ job_id: string; status: string }>(
    '/local/process',
    { method: 'POST', body: form },
  )
}

export const getLocalJob = (jobId: string) =>
  request<{ status: string; result?: Record<string, unknown>; error?: string }>(
    `/local/process/${jobId}`,
  )

export const listLocalJobs = () =>
  request<{ jobs: Array<{ job_id: string; status: string }>; total: number }>(
    '/local/jobs',
  )

export const runBenchmark = (file: File) => {
  const form = new FormData()
  form.append('file', file)
  return request<{ job_id: string; status: string }>(
    '/local/benchmark',
    { method: 'POST', body: form },
  )
}

// ─── Observability (Phase 7) ─────────────────────────────────────────────────

export interface DriftAlert {
  metric: string
  current_mean: number
  baseline_mean: number
  drift_score: number
  is_drifted: boolean
  message: string
}

export interface DriftReport {
  any_drift: boolean
  window_size: number
  baseline_size: number
  total_recorded: number
  baseline_frozen: boolean
  alerts: DriftAlert[]
}

export interface CalibrationBin {
  lower: number
  upper: number
  count: number
  mean_confidence: number
  accuracy: number
}

export interface CalibrationReport {
  ece: number
  total_samples: number
  bins: CalibrationBin[]
}

export const getDriftReport = () =>
  request<DriftReport>('/observability/drift')

export const getCalibrationReport = () =>
  request<CalibrationReport>('/observability/calibration')

export const getReviewQueue = (maxConfidence = 0.5) =>
  request<{
    queue_depth: number
    threshold: number
    items: unknown[]
    drift_status: { any_drift: boolean; alert_count: number }
  }>(`/review/queue?max_confidence=${maxConfidence}`)

// ─── Search (Phase 10) ────────────────────────────────────────────────────────

export interface SearchResultItem {
  doc_id: string
  video_id: string
  timestamp_ms: number
  timestamp_str: string
  topic: string
  risk: string
  risk_score: number
  transcript_snippet: string
  objections: string[]
  decision_signals: string[]
  score: number
}

export const searchSegments = (
  q: string,
  risk?: string,
  topic?: string,
  limit = 20,
) => {
  const params = new URLSearchParams({ q, limit: String(limit) })
  if (risk) params.set('risk', risk)
  if (topic) params.set('topic', topic)
  return request<{ query: string; total: number; results: SearchResultItem[]; filters: Record<string, string | null> }>(
    `/search?${params}`,
  )
}

export const getSearchIndexStats = () =>
  request<{ document_count: number }>('/search/index/stats')

export const getWinLossPatterns = () =>
  request<{
    high_risk_objections: string[]
    low_risk_topics: string[]
    avg_risk_score: number
    risk_distribution: Record<string, number>
  }>('/search/insights/patterns')

export const getObjectionVelocity = (period: 'week' | 'month' = 'week') =>
  request<{
    period: string
    total: number
    items: Array<{
      objection: string
      trend: string
      counts_by_period: Array<{ period: string; count: number }>
    }>
  }>(`/search/insights/velocity?period=${period}`)

// ─── Summaries ───────────────────────────────────────────────────────────────
export const getSummary = (jobId: string, type = 'executive') =>
  request<{ job_id: string; summary_type: string; content: string; word_count: number }>(
    `/summaries/${jobId}?type=${type}`,
  )

export const createSummary = (jobId: string, type = 'executive') =>
  request<{ job_id: string; summary_type: string; content: string; word_count: number }>(
    `/summaries/${jobId}`,
    { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ summary_type: type }) },
  )

// ─── Diarization ─────────────────────────────────────────────────────────────
export const getSpeakers = (jobId: string) =>
  request<{ job_id: string; speakers: Array<{ speaker: string; turns: number; words: number; percentage: number }> }>(
    `/diarization/${jobId}/speakers`,
  )

export const getDiarizationSegments = (jobId: string) =>
  request<{ job_id: string; segments: Array<{ speaker: string; start_ms: number; end_ms: number; text: string }> }>(
    `/diarization/${jobId}/segments`,
  )

// ─── Clips ───────────────────────────────────────────────────────────────────
export const listClips = (jobId: string) =>
  request<{ job_id: string; clips: Array<{ filename: string; segment_index: number; url: string }> }>(
    `/clips/${jobId}`,
  )

export const extractSignificantClips = (jobId: string, n = 3) =>
  request<{ job_id: string; clips: unknown[] }>(`/clips/${jobId}/significant?n=${n}`, { method: 'POST' })

// ─── Agents: Q&A ─────────────────────────────────────────────────────────────
export interface QAAnswer {
  question: string
  answer: string
  model: string
  citations: Array<{ job_id: string; segment_index: number; timestamp: string; topic: string; risk_score: number; excerpt: string }>
}

export const askQA = (question: string, jobId?: string) => {
  const params = new URLSearchParams({ question })
  if (jobId) params.set('job_id', jobId)
  return request<{ answer: QAAnswer }>(`/agents/qa?${params}`)
}

export const indexJobForQA = (jobId: string) =>
  request<{ message: string; doc_count: number }>(`/agents/qa/index/${jobId}`, { method: 'POST' })

// ─── Agents: Risk ─────────────────────────────────────────────────────────────
export const getRiskAlerts = () =>
  request<{ alerts: Array<{ job_id: string; alert_type: string; risk_score: number; company: string; message: string }> }>(
    '/agents/risk/alerts',
  )

export const recordRisk = (jobId: string, company: string, dealId?: string) =>
  request<{ alerts: unknown[] }>(
    `/agents/risk/record/${jobId}`,
    { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ company, deal_id: dealId }) },
  )

// ─── Agents: Coaching ────────────────────────────────────────────────────────
export interface CoachingCard {
  rep_id: string
  calls_analyzed: number
  overall_score: number
  grade: string
  dimensions: Array<{ name: string; score: number; value: number; benchmark: number; verdict: string; tip: string }>
  strengths: string[]
  improvements: string[]
}

export const getCoachingCard = (repId: string) =>
  request<{ card: CoachingCard }>(`/agents/coaching/${repId}`)

export const recordCallForCoaching = (jobId: string, repId: string, speakerLabel?: string) =>
  request<{ message: string }>(
    `/agents/coaching/record/${jobId}`,
    { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ rep_id: repId, speaker_label: speakerLabel }) },
  )

// ─── Agents: Meeting Prep ────────────────────────────────────────────────────
export const getMeetingBrief = (company: string, contact?: string) =>
  request<{ brief: unknown }>(
    '/agents/meeting-prep',
    { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ company, contact }) },
  )

// ─── Agents: Knowledge Graph ─────────────────────────────────────────────────
export const queryKG = (entity: string, limit = 20) =>
  request<{ nodes: unknown[]; edges: unknown[] }>(`/agents/kg?entity=${encodeURIComponent(entity)}&limit=${limit}`)

export const getTopEntities = (entityType?: string, limit = 20) => {
  const params = new URLSearchParams({ limit: String(limit) })
  if (entityType) params.set('entity_type', entityType)
  return request<{ entities: unknown[] }>(`/agents/kg/top?${params}`)
}

export const exportKG = () =>
  request<{ nodes: unknown[]; edges: unknown[] }>('/agents/kg/export')

// ─── Webhooks ────────────────────────────────────────────────────────────────
export const listWebhooks = () =>
  request<{ webhooks: Array<{ id: string; url: string; events: string[]; active: boolean }> }>('/webhooks')

export const createWebhook = (url: string, events: string[], secret?: string) =>
  request<{ webhook: unknown }>(
    '/webhooks',
    { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ url, events, secret }) },
  )

export const deleteWebhook = (webhookId: string) =>
  request<{ message: string }>(`/webhooks/${webhookId}`, { method: 'DELETE' })

// ─── Schemas ─────────────────────────────────────────────────────────────────
export const listSchemas = () =>
  request<{ schemas: Array<{ schema_id: string; name: string; vertical: string }> }>('/schemas')

export const createSchema = (name: string, fields: unknown[], vertical?: string) =>
  request<{ schema: unknown }>(
    '/schemas',
    { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name, fields, vertical }) },
  )

// ─── Batch ───────────────────────────────────────────────────────────────────
export const submitBatch = (urls: string[], vertical?: string, schemaId?: string, priority = 5) =>
  request<{ batch: unknown }>(
    '/batch',
    { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ urls, vertical, schema_id: schemaId, priority }) },
  )

export const getBatch = (batchId: string) =>
  request<{ batch: unknown }>(`/batch/${batchId}`)

export const listBatches = (limit = 20) =>
  request<{ batches: unknown[] }>(`/batch?limit=${limit}`)

// ─── Integrations ────────────────────────────────────────────────────────────
export const getIntegrationStatus = () =>
  request<Record<string, { configured: boolean }>>('/integrations/status')

export const syncToSalesforce = (jobId: string, payload: { access_token: string; instance_url: string; who_id?: string; what_id?: string }) =>
  request<{ message: string; task_id: string }>(
    `/integrations/salesforce/sync/${jobId}`,
    { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) },
  )

export const syncToHubspot = (jobId: string, payload: { access_token: string; contact_ids?: string[]; deal_ids?: string[] }) =>
  request<{ message: string; engagement_id: string }>(
    `/integrations/hubspot/sync/${jobId}`,
    { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) },
  )

export const exportToNotion = (jobId: string, payload: { token: string; database_id: string }) =>
  request<{ message: string; page_id: string; url: string }>(
    `/integrations/notion/export/${jobId}`,
    { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) },
  )
