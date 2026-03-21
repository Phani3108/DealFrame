import { lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { Layout } from './components/Layout'
import { Dashboard } from './pages/Dashboard'
import { Upload } from './pages/Upload'
import { Results } from './pages/Results'
import { Observatory } from './pages/Observatory'
import { Finetuning } from './pages/Finetuning'
import { LocalPipeline } from './pages/LocalPipeline'
import { Observability } from './pages/Observability'
import { Search } from './pages/Search'
import { Streaming } from './pages/Streaming'
import { Chat } from './pages/Chat'
import { Coaching } from './pages/Coaching'
import { SchemaBuilder } from './pages/SchemaBuilder'
import { Integrations } from './pages/Integrations'
import { Batch } from './pages/Batch'
import { MeetingPrep } from './pages/MeetingPrep'
import { KnowledgeGraph } from './pages/KnowledgeGraph'
import { Annotations } from './pages/Annotations'
import { ReviewQueue } from './pages/ReviewQueue'
import { AuditLog } from './pages/AuditLog'
import { DiffView } from './pages/DiffView'
import { PatternMiner } from './pages/PatternMiner'
import { LiveCopilot } from './pages/LiveCopilot'
import { Admin } from './pages/Admin'
import { SettingsPage } from './pages/SettingsPage'

// Lazy-load Recharts-heavy Intelligence page to avoid headless/SSR crashes
const Intelligence = lazy(() => import('./pages/Intelligence').then(m => ({ default: m.Intelligence })))

export default function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/upload" element={<Upload />} />
          <Route path="/results/:jobId" element={<Results />} />
          <Route path="/observatory" element={<Observatory />} />
          <Route path="/intelligence" element={
            <Suspense fallback={<div className="p-8 text-slate-400">Loading analytics…</div>}>
              <Intelligence />
            </Suspense>
          } />
          <Route path="/finetuning" element={<Finetuning />} />
          <Route path="/local" element={<LocalPipeline />} />
          <Route path="/observability" element={<Observability />} />
          <Route path="/search" element={<Search />} />
          <Route path="/streaming" element={<Streaming />} />
          <Route path="/chat" element={<Chat />} />
          <Route path="/coaching" element={<Coaching />} />
          <Route path="/schema-builder" element={<SchemaBuilder />} />
          <Route path="/integrations" element={<Integrations />} />
          <Route path="/batch" element={<Batch />} />
          <Route path="/meeting-prep" element={<MeetingPrep />} />
          <Route path="/knowledge-graph" element={<KnowledgeGraph />} />
          <Route path="/annotations" element={<Annotations />} />
          <Route path="/review-queue" element={<ReviewQueue />} />
          <Route path="/audit-log" element={<AuditLog />} />
          <Route path="/diff" element={<DiffView />} />
          <Route path="/patterns" element={<PatternMiner />} />
          <Route path="/copilot" element={<LiveCopilot />} />
          <Route path="/admin" element={<Admin />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  )
}
