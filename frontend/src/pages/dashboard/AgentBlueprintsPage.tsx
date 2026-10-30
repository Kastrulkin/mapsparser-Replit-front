import { Button } from '@/components/ui/button';
import { ClientCommunicationWorkspace } from './agents/ClientCommunicationWorkspace';
import { lazy, Suspense } from 'react';
import { useOutletContext, useSearchParams } from 'react-router-dom';
import type { DashboardContext } from './agents/types';

const AgentBlueprintsWorkspace = lazy(() => import('./AgentBlueprintsWorkspace').then((module) => ({ default: module.AgentBlueprintsWorkspace })));
const DemoAgentsPage = lazy(() => import('./demo/DemoAgentsPage').then((module) => ({ default: module.DemoAgentsPage })));

const AgentWorkspaceFallback = () => (
  <div className="flex min-h-[40vh] items-center justify-center px-4 text-sm text-muted-foreground">
    Загружаем рабочее место агентов…
  </div>
);

export const AgentBlueprintsPage = () => {
  const [params, setParams] = useSearchParams();
  const communication = params.get('section') === 'clients';
  const { demoMode, currentBusinessId } = useOutletContext<DashboardContext>();
  return (
    <div className="space-y-4">
      {!demoMode && <nav aria-label="Направления автоматизации" className="flex flex-wrap gap-2">
        <Button variant={communication ? 'outline' : 'default'} aria-pressed={!communication} onClick={() => setParams({})}>Задачи и обработка данных</Button>
        <Button variant={communication ? 'default' : 'outline'} aria-pressed={communication} onClick={() => setParams({ section: 'clients' })}>Общение с клиентами</Button>
      </nav>}
    <Suspense fallback={<AgentWorkspaceFallback />}>
      {demoMode ? <DemoAgentsPage /> : communication ? <ClientCommunicationWorkspace key={currentBusinessId} /> : <AgentBlueprintsWorkspace />}
    </Suspense>
    </div>
  );
};
