import { useLanguage } from '@/i18n/LanguageContext.logic';
import { workCoherenceCopy } from '@/i18n/workCoherenceCopy';
import { EmployeeChatTest } from './ChatsPage';
import { Button } from '@/components/ui/button';
import { lazy, Suspense } from 'react';
import { Link, useOutletContext, useSearchParams } from 'react-router-dom';
import type { DashboardContext } from './agents/types';

const AgentBlueprintsWorkspace = lazy(() => import('./AgentBlueprintsWorkspace').then((module) => ({ default: module.AgentBlueprintsWorkspace })));
const DemoAgentsPage = lazy(() => import('./demo/DemoAgentsPage').then((module) => ({ default: module.DemoAgentsPage })));

const AgentWorkspaceFallback = () => (
  <div className="flex min-h-[40vh] items-center justify-center px-4 text-sm text-muted-foreground">
    Загружаем рабочее место агентов…
  </div>
);

export const AgentBlueprintsPage = () => {
  const [params] = useSearchParams();
  const { language } = useLanguage(); const copy = workCoherenceCopy(language);
  const { demoMode } = useOutletContext<DashboardContext>();
  if (params.get('test') === 'dialog') return <div className="space-y-4"><Button variant="outline" asChild><Link to="/dashboard/agents">{copy.backEmployees}</Link></Button><EmployeeChatTest /></div>;
  return (
    <Suspense fallback={<AgentWorkspaceFallback />}>
      {demoMode ? <DemoAgentsPage /> : <><AgentBlueprintsWorkspace /><details className="mt-6"><summary className="min-h-11 cursor-pointer py-2">{copy.testEmployee}</summary><Button variant="outline" asChild><Link to="/dashboard/agents?test=dialog">{copy.testEmployee}</Link></Button></details></>}
    </Suspense>
  );
};
