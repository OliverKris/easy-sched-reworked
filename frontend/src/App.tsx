import { useEffect, useState } from 'react'
import type { DatasetKey, DatasetResponse } from './types'
import { fetchDataset } from './lib/api'
import { Header } from './components/Header'
import { Tabs, type ViewKey } from './components/Tabs'
import { SectionsView } from './components/SectionsView'
import { ApplicantsView } from './components/ApplicantsView'
import { EligibilityView } from './components/EligibilityView'
import { SolverView } from './components/SolverView'
import { BoardView } from './components/BoardView'
import { EmptyState } from './components/ui'

function App() {
  const [dataset, setDataset] = useState<DatasetKey>("extended");
  const [view, setView] = useState<ViewKey>("sections");
  const [data, setData] = useState<DatasetResponse | null>(null);
  const [error, setError ] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    // Clearing any stale error from a previous dataset before refetching.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setError(null);
    fetchDataset(dataset)
      .then((res) => !cancelled && setData(res))
      .catch((e) => !cancelled && setError(e instanceof Error ? e.message : "Failed to load dataset"));
    return () => {
      cancelled = true;
    };
  }, [dataset]);

  return (
    <div className="min-h-screen font-sans text-sm text-ink">
      <Header dataset={dataset} onChange={setDataset} />
      <Tabs active={view} onChange={setView} />

      <main className="px-10 py-7 pb-16 max-w-5xl mx-auto">
        {error && (
          <EmptyState>
            Couldn't reach the API ({error}). Is the FastAPI backend running on port 8000?
          </EmptyState>
        )}
        {!error && !data && <EmptyState>Loading...</EmptyState>}
        {!error && data && (
          <>
            {view === "sections" && <SectionsView sections={data.sections} />}
            {view === "applicants" && <ApplicantsView applicants={data.applicants} />}
            {view === "eligibility" && <EligibilityView dataset={dataset} sections={data.sections} />}
            {view === "solver" && <SolverView dataset={dataset} />}
            {view === "board" && <BoardView dataset={dataset} sections={data.sections} applicants={data.applicants} />}
          </>
        )}
      </main>
    </div>
  )
}

export default App
