import { useState, useEffect } from 'react'
import { MessageSquare, Send, BookOpen, AlertCircle, Loader2 } from 'lucide-react'

interface Citation {
  job_id: string
  timestamp: string
  topic: string
  risk_score: number
  excerpt: string
}

interface QAAnswer {
  question: string
  answer: string
  citations: Citation[]
  model: string
}

function RiskBadge({ score }: { score: number }) {
  const pct = Math.round(score * 100)
  const cls = pct > 60 ? 'bg-red-100 text-red-700' : pct > 30 ? 'bg-amber-100 text-amber-700' : 'bg-emerald-100 text-emerald-700'
  return <span className={`text-xs font-medium px-1.5 py-0.5 rounded ${cls}`}>{pct}%</span>
}

export function Chat() {
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [answers, setAnswers] = useState<QAAnswer[]>([])
  const [error, setError] = useState<string | null>(null)
  const [indexSize, setIndexSize] = useState<number | null>(null)

  useEffect(() => {
    fetch('/api/v1/agents/qa?q=ping')
      .then(r => r.json())
      .then(d => { /* ignore */ })
      .catch(() => { })
  }, [])

  const handleAsk = async () => {
    if (!query.trim()) return
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`/api/v1/agents/qa?q=${encodeURIComponent(query)}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data: QAAnswer = await res.json()
      setAnswers(prev => [data, ...prev])
      setQuery('')
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleAsk()
    }
  }

  const exampleQuestions = [
    'What were the top objections this month?',
    'Which deals have the highest risk?',
    'What pricing concerns came up?',
    'Summarize the last 5 calls',
  ]

  return (
    <div className="flex flex-col h-full p-6 max-w-4xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
          <MessageSquare className="w-6 h-6 text-indigo-500" />
          Ask Your Video Library
        </h1>
        <p className="text-slate-500 mt-1 text-sm">
          Natural language Q&A over all processed video intelligence. Answers include source citations.
        </p>
      </div>

      {/* Example prompts */}
      {answers.length === 0 && (
        <div className="grid grid-cols-2 gap-3 mb-6">
          {exampleQuestions.map(q => (
            <button
              key={q}
              onClick={() => setQuery(q)}
              className="text-left text-sm p-3 rounded-xl border border-slate-200 bg-white hover:border-indigo-300 hover:bg-indigo-50/50 transition-colors text-slate-600"
            >
              {q}
            </button>
          ))}
        </div>
      )}

      {/* Answers */}
      <div className="flex-1 overflow-y-auto space-y-6 mb-6">
        {answers.map((ans, i) => (
          <div key={i} className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
            <div className="px-5 py-3 bg-slate-50 border-b border-slate-100">
              <p className="text-sm font-medium text-slate-700">{ans.question}</p>
            </div>
            <div className="px-5 py-4">
              <p className="text-slate-800 leading-relaxed">{ans.answer}</p>
              {ans.citations.length > 0 && (
                <div className="mt-4">
                  <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2 flex items-center gap-1">
                    <BookOpen className="w-3.5 h-3.5" /> Sources
                  </p>
                  <div className="space-y-2">
                    {ans.citations.map((c, ci) => (
                      <div key={ci} className="flex items-start gap-3 text-sm bg-slate-50 rounded-lg px-3 py-2">
                        <div className="flex-1 min-w-0">
                          <span className="font-mono text-xs text-indigo-600">{c.job_id.slice(0, 8)}</span>
                          <span className="text-slate-400 mx-1">·</span>
                          <span className="text-slate-500">{c.timestamp}</span>
                          <span className="text-slate-400 mx-1">·</span>
                          <span className="text-slate-600 capitalize">{c.topic}</span>
                        </div>
                        <RiskBadge score={c.risk_score} />
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {error && (
        <div className="mb-4 flex items-center gap-2 text-red-600 text-sm bg-red-50 border border-red-200 rounded-lg px-4 py-3">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          {error}
        </div>
      )}

      {/* Input */}
      <div className="flex gap-3">
        <input
          className="flex-1 border border-slate-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white"
          placeholder="Ask anything about your video library…"
          value={query}
          onChange={e => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={loading}
        />
        <button
          onClick={handleAsk}
          disabled={loading || !query.trim()}
          className="px-5 py-3 bg-indigo-600 text-white rounded-xl text-sm font-medium hover:bg-indigo-700 disabled:opacity-40 transition-colors flex items-center gap-2"
        >
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
          Ask
        </button>
      </div>
    </div>
  )
}
