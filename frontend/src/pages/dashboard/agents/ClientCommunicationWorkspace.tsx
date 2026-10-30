import { AIAgentSettings } from '@/components/AIAgentSettings';
import { Button } from '@/components/ui/button';
import type { DashboardOutletContext } from '@/types/business';
import { useOutletContext, useSearchParams } from 'react-router-dom';
import { ChatsPage, EmployeeChatTest } from '../ChatsPage';

export const ClientCommunicationWorkspace = () => {
  const { currentBusinessId, currentBusiness, updateBusiness } = useOutletContext<DashboardOutletContext>();
  const [params, setParams] = useSearchParams();
  const view = params.get('view') || 'settings';
  if (!currentBusinessId || !currentBusiness || currentBusiness.id !== currentBusinessId) {
    return <p role="status">Выберите бизнес для настройки общения с клиентами.</p>;
  }
  const selectView = (value: string) => {
    const next = new URLSearchParams(params);
    next.set('view', value);
    setParams(next);
  };
  return <section className="space-y-4" aria-label="Общение с клиентами">
    <header>
      <h1 className="text-2xl font-semibold">Общение с клиентами</h1>
      <p className="text-muted-foreground">Настройте ответы и правила работы, проверьте агента в тестовом разговоре, затем управляйте клиентскими диалогами.</p>
      <p className="mt-2 text-sm text-muted-foreground">Агент отвечает по ходу разговора и учитывает его историю. Подключение CRM и доступность записи проверяются отдельно.</p>
    </header>
    <nav aria-label="Управление общением" className="flex flex-wrap gap-2">
      {[
        { value: 'settings', label: 'Поведение и включение' },
        { value: 'test', label: 'Проверка ответов' },
        { value: 'conversations', label: 'Диалоги' },
      ].map(item => <Button key={item.value} variant={view === item.value ? 'default' : 'outline'} aria-pressed={view === item.value} onClick={() => selectView(item.value)}>{item.label}</Button>)}
    </nav>
    {view === 'test' ? <EmployeeChatTest key={currentBusinessId} /> : view === 'conversations' ? <ChatsPage key={currentBusinessId} /> : <AIAgentSettings key={currentBusinessId} businessId={currentBusinessId} business={currentBusiness} onSaved={(config) => updateBusiness(currentBusinessId, { ai_agents_config: config })} />}
  </section>;
};
