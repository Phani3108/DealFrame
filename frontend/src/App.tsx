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
        </Routes>
      </Layout>
    </BrowserRouter>
  )
}
