import { RiderraAcquisitionAutomation } from './agents/RiderraAcquisitionAutomation';
import { useLanguage } from '@/i18n/LanguageContext.logic';
import { workCoherenceCopy } from '@/i18n/workCoherenceCopy';
import { EmployeeChatTest } from './ChatsPage';
import { ClientCommunicationWorkspace } from './agents/ClientCommunicationWorkspace';
import { Button } from '@/components/ui/button';
import { lazy, Suspense } from 'react';
import { Link, useOutletContext, useSearchParams } from 'react-router-dom';
import type { DashboardContext } from './agents/types';
import { GoogleContentAutomation } from './agents/GoogleContentAutomation';

const AgentBlueprintsWorkspace = lazy(() => import('./AgentBlueprintsWorkspace').then((module) => ({ default: module.AgentBlueprintsWorkspace })));
const DemoAgentsPage = lazy(() => import('./demo/DemoAgentsPage').then((module) => ({ default: module.DemoAgentsPage })));

const AgentWorkspaceFallback = () => (
  <div className="flex min-h-[40vh] items-center justify-center px-4 text-sm text-muted-foreground">
    Загружаем рабочее место агентов…
  </div>
);

export const AgentBlueprintsPage = () => {
  const [params, setParams] = useSearchParams();
  const { language } = useLanguage(); const copy = workCoherenceCopy(language);
  const { demoMode, currentBusinessId } = useOutletContext<DashboardContext>();
  const googleAutomationBusiness = currentBusinessId && ['d4354347-4ac7-4f49-b682-7eac9fd78a76','ac19d7c3-53eb-4bc2-9dbe-d41a062864b4','aafc48df-58fd-4de5-9fd6-11cf2cd9a73a','b3fa40f5-2072-4db7-9c40-35b94659163b','97f44bd2-5f24-45b7-b7c3-dfd14d494eba','edbd961a-273f-4f15-836e-33aacc0aa0e3'].includes(currentBusinessId) ? currentBusinessId : null;
  if (params.get('test') === 'dialog') return <div className="space-y-4"><Button variant="outline" asChild><Link to="/dashboard/agents">{copy.backEmployees}</Link></Button><EmployeeChatTest /></div>;
  const communication = params.get('section') === 'clients';
  const selectSection = (clients: boolean) => {
    const next = new URLSearchParams(params);
    if (clients) next.set('section', 'clients'); else next.delete('section');
    next.delete('view');
    setParams(next);
  };
  return (
    <div className="space-y-4">
      {!demoMode && <nav aria-label="Направления автоматизации" className="flex flex-wrap gap-2">
        <Button variant={communication ? 'outline' : 'default'} aria-pressed={!communication} onClick={() => selectSection(false)}>Задачи и обработка данных</Button>
        <Button variant={communication ? 'default' : 'outline'} aria-pressed={communication} onClick={() => selectSection(true)}>Общение с клиентами</Button>
      </nav>}
    <Suspense fallback={<AgentWorkspaceFallback />}>
      {demoMode ? <DemoAgentsPage /> : communication ? <ClientCommunicationWorkspace key={currentBusinessId} /> : <>{googleAutomationBusiness && <GoogleContentAutomation businessId={googleAutomationBusiness}/>}{currentBusinessId === 'edbd961a-273f-4f15-836e-33aacc0aa0e3' && <RiderraAcquisitionAutomation key={currentBusinessId} businessId={currentBusinessId}/>}<AgentBlueprintsWorkspace /><details className="mt-6"><summary className="min-h-11 cursor-pointer py-2">{copy.testEmployee}</summary><Button variant="outline" asChild><Link to="/dashboard/agents?test=dialog">{copy.testEmployee}</Link></Button></details></>}
    </Suspense>
    </div>
  );
};
