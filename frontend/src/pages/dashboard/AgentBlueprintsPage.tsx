import { lazy, Suspense } from 'react';
import { useOutletContext } from 'react-router-dom';
import type { DashboardContext } from './agents/types';

const AgentBlueprintsWorkspace = lazy(() => import('./AgentBlueprintsWorkspace').then((module) => ({ default: module.AgentBlueprintsWorkspace })));
const DemoAgentsPage = lazy(() => import('./demo/DemoAgentsPage').then((module) => ({ default: module.DemoAgentsPage })));

const AgentWorkspaceFallback = () => (
  <div className="flex min-h-[40vh] items-center justify-center px-4 text-sm text-muted-foreground">
    Загружаем рабочее место агентов…
  </div>
);

export const AgentBlueprintsPage = () => {
  const { demoMode } = useOutletContext<DashboardContext>();
  return (
    <Suspense fallback={<AgentWorkspaceFallback />}>
      {demoMode ? <DemoAgentsPage /> : <AgentBlueprintsWorkspace />}
    </Suspense>
  );
};
