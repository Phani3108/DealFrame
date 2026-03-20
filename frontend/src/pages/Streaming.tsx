import { useState, useEffect, useRef } from 'react'
import { Radio, Wifi, WifiOff, Loader2, Mic, AlertCircle } from 'lucide-react'

type ConnectionState = 'disconnected' | 'connecting' | 'live' | 'error'

interface TranscriptEntry {
  timestamp: number
  text: string
  confidence: number
  is_final: boolean
  id: number
}

interface ExtractionEntry {
  topic: string
  risk: string
  risk_score: number
  objections: string[]
  decision_signals: string[]
  timestamp: number
  id: number
}

function RiskBadge({ risk }: { risk: string }) {
  const cls =
    risk === 'high' ? 'bg-red-50 text-red-700 border-red-200' :
    risk === 'medium' ? 'bg-amber-50 text-amber-700 border-amber-200' :
    'bg-emerald-50 text-emerald-700 border-emerald-200'
  return <span className={`text-xs font-semibold px-2 py-0.5 rounded-full border ${cls}`}>{risk}</span>
}

function ConnectionBadge({ state }: { state: ConnectionState }) {
  if (state === 'live') return (
    <span className="flex items-center gap-1.5 text-xs font-semibold text-emerald-600 bg-emerald-50 px-3 py-1 rounded-full">
      <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
      LIVE
    </span>
  )
  if (state === 'connecting') return (
    <span className="flex items-center gap-1.5 text-xs font-medium text-amber-600 bg-amber-50 px-3 py-1 rounded-full">
      <Loader2 className="w-3 h-3 animate-spin" />
      Connecting…
    </span>
  )
  if (state === 'error') return (
    <span className="flex items-center gap-1.5 text-xs font-medium text-red-600 bg-red-50 px-3 py-1 rounded-full">
      <AlertCircle className="w-3 h-3" />
      Error
    </span>
  )
  return (
    <span className="flex items-center gap-1.5 text-xs font-medium text-slate-500 bg-slate-100 px-3 py-1 rounded-full">
      <WifiOff className="w-3 h-3" />
      Disconnected
    </span>
  )
}

let _msgId = 0

export function Streaming() {
  const [state, setConnState] = useState<ConnectionState>('disconnected')
  const [sessionId, setSessionId] = useState<string>('')
  const [transcripts, setTranscripts] = useState<TranscriptEntry[]>([])
  const [extractions, setExtractions] = useState<ExtractionEntry[]>([])
  const wsRef = useRef<WebSocket | null>(null)
  const transcriptEndRef = useRef<HTMLDivElement>(null)
  const extractEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    return () => { wsRef.current?.close() }
  }, [])

  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [transcripts])

  useEffect(() => {
    extractEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [extractions])

  const connect = () => {
    if (wsRef.current) return
    setConnState('connecting')
    setTranscripts([])
    setExtractions([])
    const sid = `session-${Date.now()}`
    setSessionId(sid)

    const ws = new WebSocket('ws://localhost:8000/ws/stream')
    wsRef.current = ws

    ws.onopen = () => setConnState('live')

    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data)
        if (msg.type === 'result') {
          const chunk = msg.chunk
          if (chunk) {
            setTranscripts(prev => [...prev, {
              timestamp: Date.now(),
              text: chunk.text ?? '',
              confidence: chunk.confidence ?? 0,
              is_final: chunk.is_final ?? false,
              id: ++_msgId,
            }])
          }
          const ext = msg.extraction
          if (ext) {
            setExtractions(prev => [...prev, {
              topic: ext.topic ?? 'unknown',
              risk: ext.risk ?? 'low',
              risk_score: ext.risk_score ?? 0,
              objections: ext.objections ?? [],
              decision_signals: ext.decision_signals ?? [],
              timestamp: Date.now(),
              id: ++_msgId,
            }])
          }
        } else if (msg.type === 'done') {
          setConnState('disconnected')
          wsRef.current = null
        }
      } catch { /* non-JSON frame */ }
    }

    ws.onerror = () => setConnState('error')

    ws.onclose = () => {
      setConnState(prev => prev === 'live' ? 'disconnected' : prev)
      wsRef.current = null
    }
  }

  const disconnect = () => {
    if (!wsRef.current) return
    wsRef.current.send(JSON.stringify({ type: 'end' }))
    wsRef.current.close()
    wsRef.current = null
    setConnState('disconnected')
  }

  const sendDemoAudio = () => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return
    // Send 640 bytes of silence (16kHz 16-bit mono PCM, ~20ms)
    const buf = new ArrayBuffer(640)
    for (let i = 0; i < 20; i++) {
      wsRef.current.send(buf)
    }
  }

  return (
    <div className="p-8 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-start justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <Radio className="w-6 h-6 text-indigo-600" />
            Live Streaming
          </h1>
          <p className="text-slate-500 mt-1 text-sm">
            Real-time audio transcription and extraction via WebSocket
          </p>
        </div>
        <div className="flex items-center gap-3">
          <ConnectionBadge state={state} />
          {state === 'disconnected' || state === 'error' ? (
            <button
              onClick={connect}
              className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-xl text-sm font-semibold hover:bg-indigo-700 transition-colors"
            >
              <Wifi className="w-4 h-4" />
              Connect
            </button>
          ) : (
            <div className="flex gap-2">
              <button
                onClick={sendDemoAudio}
                disabled={state !== 'live'}
                className="flex items-center gap-2 px-4 py-2 bg-white border border-indigo-300 text-indigo-700 rounded-xl text-sm font-semibold hover:bg-indigo-50 disabled:opacity-40 transition-colors"
              >
                <Mic className="w-4 h-4" />
                Send Demo Audio
              </button>
              <button
                onClick={disconnect}
                className="flex items-center gap-2 px-4 py-2 bg-white border border-red-300 text-red-600 rounded-xl text-sm font-semibold hover:bg-red-50 transition-colors"
              >
                <WifiOff className="w-4 h-4" />
                Disconnect
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Session info */}
      {sessionId && (
        <div className="mb-4 px-4 py-2 bg-slate-800 rounded-lg inline-flex items-center gap-2">
          <span className="text-xs text-slate-400">Session</span>
          <code className="text-xs text-indigo-300">{sessionId}</code>
        </div>
      )}

      <div className="grid grid-cols-2 gap-6">
        {/* Transcript feed */}
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden flex flex-col" style={{ height: 420 }}>
          <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-slate-900">Transcript Feed</h2>
            <span className="text-xs text-slate-400">{transcripts.length} chunks</span>
          </div>
          <div className="flex-1 overflow-y-auto p-4 space-y-2 font-mono">
            {transcripts.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-slate-400">
                <Mic className="w-8 h-8 mb-2 opacity-30" />
                <p className="text-xs">Waiting for audio…</p>
              </div>
            ) : (
              transcripts.map(t => (
                <div key={t.id} className="text-xs">
                  <span className="text-slate-400 select-none">
                    {new Date(t.timestamp).toLocaleTimeString('en', { hour12: false })}
                  </span>
                  <span className={`ml-2 ${t.is_final ? 'text-slate-800' : 'text-slate-500 italic'}`}>{t.text}</span>
                  <span className="ml-1.5 text-slate-300 text-[10px]">{(t.confidence * 100).toFixed(0)}%</span>
                </div>
              ))
            )}
            <div ref={transcriptEndRef} />
          </div>
        </div>

        {/* Extraction results */}
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden flex flex-col" style={{ height: 420 }}>
          <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-slate-900">Extraction Results</h2>
            <span className="text-xs text-slate-400">{extractions.length} segments</span>
          </div>
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {extractions.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-slate-400">
                <AlertCircle className="w-8 h-8 mb-2 opacity-30" />
                <p className="text-xs">Extractions appear here in real-time</p>
              </div>
            ) : (
              extractions.map(e => (
                <div key={e.id} className="p-3 bg-slate-50 rounded-lg border border-slate-100">
                  <div className="flex items-center gap-2 mb-2">
                    <RiskBadge risk={e.risk} />
                    <span className="text-xs font-medium text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded-full">
                      {e.topic}
                    </span>
                    <span className="text-xs text-slate-400 ml-auto">risk {e.risk_score.toFixed(2)}</span>
                  </div>
                  {e.objections.length > 0 && (
                    <div className="text-xs text-slate-600">
                      <span className="text-slate-400">Objections:</span> {e.objections.join(' · ')}
                    </div>
                  )}
                  {e.decision_signals.length > 0 && (
                    <div className="text-xs text-slate-600 mt-0.5">
                      <span className="text-slate-400">Signals:</span> {e.decision_signals.join(' · ')}
                    </div>
                  )}
                </div>
              ))
            )}
            <div ref={extractEndRef} />
          </div>
        </div>
      </div>

      {/* Protocol info */}
      <div className="mt-6 bg-slate-800 rounded-xl p-5">
        <h3 className="text-sm font-semibold text-white mb-3">WebSocket Protocol</h3>
        <div className="space-y-1.5 text-xs font-mono">
          <p className="text-slate-400"># Connect</p>
          <p className="text-emerald-400">ws://localhost:8000/ws/stream</p>
          <p className="text-slate-400 mt-3"># Send audio frames (binary)</p>
          <p className="text-blue-300">ArrayBuffer  — 16 kHz, 16-bit, mono PCM</p>
          <p className="text-slate-400 mt-3"># Signal end of stream</p>
          <p className="text-amber-300">{'{"type": "end"}'}</p>
          <p className="text-slate-400 mt-3"># Receive messages</p>
          <p className="text-purple-300">{'{"type": "result", "chunk": {...}, "extraction": {...}}'}</p>
          <p className="text-purple-300">{'{"type": "done"}'}</p>
        </div>
      </div>
    </div>
  )
}
