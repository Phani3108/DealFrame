import { useState, useEffect } from 'react'
import { Network, Search, Download, RefreshCw, Loader2, AlertCircle } from 'lucide-react'

interface KGNode {
  id: string
  label: string
  entity_type: string
  frequency: number
  jobs: string[]
}

interface KGEdge {
  source: string
  target: string
  weight: number
}

interface QueryResult {
  nodes: KGNode[]
  edges: KGEdge[]
}

interface TopEntity {
  node_id: string
  label: string
  entity_type: string
  frequency: number
}

const TYPE_COLORS: Record<string, string> = {
  person:      'bg-blue-100 text-blue-700',
  organization:'bg-violet-100 text-violet-700',
  product:     'bg-emerald-100 text-emerald-700',
  risk:        'bg-red-100 text-red-700',
  topic:       'bg-amber-100 text-amber-700',
  action:      'bg-slate-100 text-slate-700',
}

function NodeBadge({ node }: { node: KGNode }) {
  const cls = TYPE_COLORS[node.entity_type] ?? 'bg-slate-100 text-slate-700'
  return (
    <div className={`inline-block px-3 py-1.5 rounded-xl text-xs font-medium ${cls}`}>
      <span>{node.label}</span>
      <span className="ml-1.5 opacity-60">×{node.frequency}</span>
    </div>
  )
}

export function KnowledgeGraph() {
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<QueryResult | null>(null)
  const [topEntities, setTopEntities] = useState<TopEntity[]>([])
  const [topType, setTopType] = useState('')
  const [error, setError] = useState('')
  const [exportLoading, setExportLoading] = useState(false)

  useEffect(() => {
    loadTop()
  }, [])

  const loadTop = async (type = topType) => {
    const url = `/api/v1/agents/kg/top${type ? `?entity_type=${type}` : ''}`
    const r = await fetch(url).catch(() => null)
    if (!r?.ok) return
    const d = await r.json()
    setTopEntities(d.entities ?? [])
  }

  const search = async () => {
    if (!query.trim()) { setError('Enter an entity to search'); return }
    setError(''); setLoading(true); setResult(null)
    try {
      const r = await fetch(`/api/v1/agents/kg?entity=${encodeURIComponent(query.trim())}`)
      const d = await r.json()
      if (!r.ok) { setError(d.detail ?? 'Search failed'); return }
      setResult(d)
    } finally {
      setLoading(false)
    }
  }

  const exportGraph = async () => {
    setExportLoading(true)
    try {
      const r = await fetch('/api/v1/agents/kg/export')
      const blob = await r.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'knowledge-graph.json'
      a.click()
      URL.revokeObjectURL(url)
    } finally {
      setExportLoading(false)
    }
  }

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <Network className="w-6 h-6 text-indigo-500" />
            Knowledge Graph
          </h1>
          <p className="text-slate-500 mt-1 text-sm">Entity co-occurrence network across all processed videos.</p>
        </div>
        <button
          onClick={exportGraph}
          disabled={exportLoading}
          className="flex items-center gap-2 px-4 py-2 bg-slate-100 text-slate-700 rounded-xl text-sm hover:bg-slate-200 disabled:opacity-40"
        >
          {exportLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
          Export JSON
        </button>
      </div>

      {/* Search */}
      <div className="bg-white rounded-2xl border border-slate-200 p-5">
        <div className="flex gap-3">
          <input
            className="flex-1 border border-slate-200 rounded-xl px-4 py-2.5 text-sm"
            placeholder="Search entity (e.g. Acme Corp, pricing, John…)"
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && search()}
          />
          <button
            onClick={search}
            disabled={loading}
            className="px-5 py-2.5 bg-indigo-600 text-white text-sm rounded-xl hover:bg-indigo-700 disabled:opacity-40 flex items-center gap-2"
          >
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
            Query
          </button>
        </div>
        {error && <p className="mt-2 text-sm text-red-500 flex items-center gap-1.5"><AlertCircle className="w-4 h-4" />{error}</p>}
      </div>

      {/* Query results */}
      {result && (
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-white rounded-2xl border border-slate-200 p-5">
            <h3 className="font-semibold text-slate-800 mb-3 text-sm">
              Nodes <span className="text-slate-400 font-normal">({result.nodes.length})</span>
            </h3>
            <div className="flex flex-wrap gap-2">
              {result.nodes.map(n => (
                <button
                  key={n.id}
                  onClick={() => { setQuery(n.label); search() }}
                  className="cursor-pointer hover:scale-105 transition-transform"
                >
                  <NodeBadge node={n} />
                </button>
              ))}
            </div>
          </div>

          <div className="bg-white rounded-2xl border border-slate-200 p-5">
            <h3 className="font-semibold text-slate-800 mb-3 text-sm">
              Relationships <span className="text-slate-400 font-normal">({result.edges.length})</span>
            </h3>
            {result.edges.length === 0
              ? <p className="text-sm text-slate-400">No co-occurrences found</p>
              : (
                <div className="space-y-2">
                  {result.edges.slice(0, 10).map((e, i) => (
                    <div key={i} className="flex items-center gap-2 text-xs">
                      <span className="text-slate-600 font-medium">{e.source}</span>
                      <span className="text-slate-300">—</span>
                      <span className="text-slate-600 font-medium">{e.target}</span>
                      <span className="ml-auto text-slate-400">w={e.weight}</span>
                    </div>
                  ))}
                </div>
              )}
          </div>
        </div>
      )}

      {/* Top Entities */}
      <div className="bg-white rounded-2xl border border-slate-200 p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-slate-800 text-sm">Top Entities</h3>
          <div className="flex items-center gap-2">
            <select
              className="border border-slate-200 rounded-xl px-3 py-1.5 text-xs bg-white"
              value={topType}
              onChange={e => { setTopType(e.target.value); loadTop(e.target.value) }}
            >
              <option value="">All types</option>
              {Object.keys(TYPE_COLORS).map(t => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
            <button
              onClick={() => loadTop(topType)}
              className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100"
            >
              <RefreshCw className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {topEntities.length === 0
          ? (
            <div className="text-center py-8 text-slate-400">
              <Network className="w-8 h-8 mx-auto mb-2 opacity-30" />
              <p className="text-sm">No entities in graph yet. Process some videos first.</p>
            </div>
          )
          : (
            <div className="space-y-2">
              {topEntities.map((e, i) => {
                const cls = TYPE_COLORS[e.entity_type] ?? 'bg-slate-100 text-slate-700'
                const maxFreq = topEntities[0]?.frequency ?? 1
                return (
                  <div key={e.node_id} className="flex items-center gap-3">
                    <span className="text-xs text-slate-400 w-4 text-right">{i + 1}</span>
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-sm text-slate-800 font-medium">{e.label}</span>
                        <span className={`text-xs px-2 py-0.5 rounded-full ${cls}`}>{e.entity_type}</span>
                      </div>
                      <div className="w-full bg-slate-100 rounded-full h-1.5">
                        <div
                          className="h-1.5 rounded-full bg-indigo-400"
                          style={{ width: `${(e.frequency / maxFreq) * 100}%` }}
                        />
                      </div>
                    </div>
                    <span className="text-xs text-slate-400">×{e.frequency}</span>
                  </div>
                )
              })}
            </div>
          )}
      </div>
    </div>
  )
}
