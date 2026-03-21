import { useState, useEffect } from 'react'
import {
  Layers, Plus, Trash2, Edit3, Play, ChevronDown, ChevronUp,
  CheckCircle, AlertCircle, Loader2, Settings,
} from 'lucide-react'

interface FieldDef {
  name: string
  type: string
  description: string
  required: boolean
  options: string[]
}

interface Schema {
  id: string
  name: string
  vertical: string
  fields: FieldDef[]
  created_at: string
}

const FIELD_TYPES = ['string', 'category', 'boolean', 'number', 'list_string', 'list_category']
const VERTICALS = ['', 'sales', 'ux_research', 'customer_success', 'real_estate', 'legal', 'custom']

function FieldEditor({
  field, onChange, onRemove,
}: {
  field: FieldDef
  onChange: (f: FieldDef) => void
  onRemove: () => void
}) {
  return (
    <div className="border border-slate-200 rounded-xl p-4 bg-slate-50 space-y-3">
      <div className="flex gap-3">
        <input
          className="flex-1 border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white"
          placeholder="Field name (snake_case)"
          value={field.name}
          onChange={e => onChange({ ...field, name: e.target.value })}
        />
        <select
          className="border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white"
          value={field.type}
          onChange={e => onChange({ ...field, type: e.target.value })}
        >
          {FIELD_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
        </select>
        <button onClick={onRemove} className="p-2 text-red-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors">
          <Trash2 className="w-4 h-4" />
        </button>
      </div>
      <input
        className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white"
        placeholder="Description (helps the AI extract this field)"
        value={field.description}
        onChange={e => onChange({ ...field, description: e.target.value })}
      />
      {(field.type === 'category' || field.type === 'list_category') && (
        <input
          className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white"
          placeholder="Options (comma-separated, e.g. low,medium,high)"
          value={field.options.join(',')}
          onChange={e => onChange({ ...field, options: e.target.value.split(',').map(s => s.trim()).filter(Boolean) })}
        />
      )}
      <label className="flex items-center gap-2 text-sm text-slate-600 cursor-pointer">
        <input
          type="checkbox"
          checked={field.required}
          onChange={e => onChange({ ...field, required: e.target.checked })}
          className="accent-indigo-600"
        />
        Required field
      </label>
    </div>
  )
}

function SchemaCard({ schema, onDelete }: { schema: Schema; onDelete: () => void }) {
  const [expanded, setExpanded] = useState(false)
  return (
    <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
      <div className="px-5 py-4 flex items-center justify-between cursor-pointer" onClick={() => setExpanded(v => !v)}>
        <div>
          <p className="font-semibold text-slate-900">{schema.name}</p>
          <p className="text-xs text-slate-400 mt-0.5">
            {schema.fields.length} field{schema.fields.length !== 1 ? 's' : ''}
            {schema.vertical ? ` · ${schema.vertical}` : ''}
            {' · '}
            <span className="font-mono">{schema.id.slice(0, 8)}</span>
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={e => { e.stopPropagation(); onDelete() }}
            className="p-1.5 text-slate-400 hover:text-red-500 rounded-lg transition-colors"
          >
            <Trash2 className="w-4 h-4" />
          </button>
          {expanded ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
        </div>
      </div>
      {expanded && (
        <div className="px-5 pb-5 space-y-2 border-t border-slate-100 pt-4">
          {schema.fields.map((f, i) => (
            <div key={i} className="flex items-center gap-3 text-sm">
              <span className="font-mono text-slate-700 w-36 truncate">{f.name}</span>
              <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-500 text-xs">{f.type}</span>
              {f.required && <span className="text-red-500 text-xs">required</span>}
              <span className="text-slate-400 truncate flex-1">{f.description}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export function SchemaBuilder() {
  const [schemas, setSchemas] = useState<Schema[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [name, setName] = useState('')
  const [vertical, setVertical] = useState('')
  const [fields, setFields] = useState<FieldDef[]>([
    { name: 'topic', type: 'string', description: 'Main topic of the segment', required: true, options: [] },
    { name: 'sentiment', type: 'category', description: 'Sentiment tone', required: false, options: ['positive', 'neutral', 'negative'] },
  ])
  const [success, setSuccess] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => { loadSchemas() }, [])

  const loadSchemas = async () => {
    setLoading(true)
    try {
      const r = await fetch('/api/v1/schemas')
      const d = await r.json()
      setSchemas(d.schemas ?? [])
    } finally {
      setLoading(false)
    }
  }

  const addField = () => setFields(prev => [
    ...prev,
    { name: '', type: 'string', description: '', required: false, options: [] },
  ])

  const saveSchema = async () => {
    if (!name.trim()) return setError('Schema name is required')
    if (fields.some(f => !f.name.trim())) return setError('All fields must have a name')
    setSaving(true)
    setError(null)
    try {
      const r = await fetch('/api/v1/schemas', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, vertical, fields }),
      })
      if (!r.ok) throw new Error(await r.text())
      await loadSchemas()
      setName(''); setVertical(''); setSuccess(true)
      setTimeout(() => setSuccess(false), 3000)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  const deleteSchema = async (id: string) => {
    await fetch(`/api/v1/schemas/${id}`, { method: 'DELETE' })
    setSchemas(prev => prev.filter(s => s.id !== id))
  }

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
          <Layers className="w-6 h-6 text-indigo-500" />
          Schema Builder
        </h1>
        <p className="text-slate-500 mt-1 text-sm">Define custom extraction schemas for any industry or use case.</p>
      </div>

      {/* Create new */}
      <div className="bg-white rounded-2xl border border-slate-200 p-6 mb-8">
        <h2 className="font-semibold text-slate-900 mb-4 flex items-center gap-2">
          <Settings className="w-4 h-4 text-slate-400" /> Create Schema
        </h2>
        <div className="flex gap-3 mb-4">
          <input
            className="flex-1 border border-slate-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            placeholder="Schema name (e.g. Legal Deposition Extractor)"
            value={name}
            onChange={e => setName(e.target.value)}
          />
          <select
            className="border border-slate-200 rounded-xl px-4 py-2.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
            value={vertical}
            onChange={e => setVertical(e.target.value)}
          >
            {VERTICALS.map(v => <option key={v} value={v}>{v || '— No vertical —'}</option>)}
          </select>
        </div>
        <div className="space-y-3 mb-4">
          {fields.map((f, i) => (
            <FieldEditor
              key={i}
              field={f}
              onChange={updated => setFields(prev => prev.map((x, j) => j === i ? updated : x))}
              onRemove={() => setFields(prev => prev.filter((_, j) => j !== i))}
            />
          ))}
        </div>
        <div className="flex gap-3">
          <button
            onClick={addField}
            className="flex items-center gap-2 px-4 py-2 text-sm border border-slate-200 rounded-xl hover:bg-slate-50"
          >
            <Plus className="w-4 h-4" /> Add Field
          </button>
          <button
            onClick={saveSchema}
            disabled={saving}
            className="flex items-center gap-2 px-5 py-2 bg-indigo-600 text-white text-sm rounded-xl hover:bg-indigo-700 disabled:opacity-40"
          >
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
            Save Schema
          </button>
          {success && <span className="flex items-center gap-1.5 text-sm text-emerald-600"><CheckCircle className="w-4 h-4" /> Saved!</span>}
          {error && <span className="flex items-center gap-1.5 text-sm text-red-600"><AlertCircle className="w-4 h-4" /> {error}</span>}
        </div>
      </div>

      {/* Existing schemas */}
      <h2 className="font-semibold text-slate-800 mb-3">Saved Schemas ({schemas.length})</h2>
      {loading ? (
        <div className="text-center py-10 text-slate-400"><Loader2 className="w-6 h-6 animate-spin mx-auto" /></div>
      ) : schemas.length === 0 ? (
        <div className="text-center py-10 text-slate-400 text-sm">No schemas yet. Create one above.</div>
      ) : (
        <div className="space-y-3">
          {schemas.map(s => <SchemaCard key={s.id} schema={s} onDelete={() => deleteSchema(s.id)} />)}
        </div>
      )}
    </div>
  )
}
