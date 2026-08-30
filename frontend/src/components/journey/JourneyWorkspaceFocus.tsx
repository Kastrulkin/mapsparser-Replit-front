import { useEffect, useRef, useState, type ReactNode } from 'react';
import { useOutletContext, useSearchParams } from 'react-router-dom';
import { RefreshCw } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { newAuth } from '@/lib/auth_new';
import type { JourneyAction } from '@/lib/leadJourney';
import { JourneyActionCard } from './JourneyActionCard';

type WorkspaceContext = { currentBusinessId?: string | null };

export const JourneyWorkspaceFocus = ({ children }: { children: ReactNode }) => {
  const { currentBusinessId } = useOutletContext<WorkspaceContext>();
  const [searchParams, setSearchParams] = useSearchParams();
  const actionId = searchParams.get('journey_action') || '';
  const [action, setAction] = useState<JourneyAction | null>(null);
  const [loading, setLoading] = useState(Boolean(actionId));
  const [error, setError] = useState('');
  const trackedAction = useRef('');

  const load = () => {
    if (!actionId || !currentBusinessId) {
      setAction(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError('');
    void newAuth.makeRequest(`/journey-actions/${encodeURIComponent(actionId)}?business_id=${encodeURIComponent(currentBusinessId)}`)
      .then((data) => setAction(data.action || null))
      .catch((caught) => setError(caught instanceof Error ? caught.message : 'Не удалось открыть выбранное действие'))
      .finally(() => setLoading(false));
  };

  useEffect(load, [actionId, currentBusinessId]);

  useEffect(() => {
    if (!action || !currentBusinessId || trackedAction.current === action.id) return;
    trackedAction.current = action.id;
    void newAuth.makeRequest('/product/events', {
      method: 'POST',
      body: JSON.stringify({
        event_name: 'journey_workspace_opened', surface: 'web', business_id: currentBusinessId,
        journey_id: action.journey_id, action_id: action.id, flow_type: action.flow_type,
        entity_type: action.entity_type, entity_id: action.entity_id,
      }),
    }).catch(() => undefined);
  }, [action, currentBusinessId]);

  return (
    <div className="space-y-5">
      {loading ? <section className="h-36 animate-pulse rounded-[24px] bg-slate-100" aria-label="Загружаем выбранное действие" /> : null}
      {error ? <section className="rounded-[24px] bg-red-50 p-5 shadow-[0_0_0_1px_rgba(185,28,28,0.12)]"><h2 className="text-balance font-semibold text-red-950">Не удалось продолжить персональный сценарий</h2><p className="mt-2 text-pretty text-sm text-red-800">{error}</p><Button type="button" variant="outline" onClick={load} className="mt-4 min-h-11 gap-2 transition-transform active:scale-[0.96]"><RefreshCw className="h-4 w-4" />Повторить</Button></section> : null}
      {action && currentBusinessId ? <section aria-label="Выбранное действие"><JourneyActionCard action={action} businessId={currentBusinessId} onUpdated={(nextAction) => {
        if (!nextAction) {
          load();
          return;
        }
        setAction(nextAction);
        const nextParams = new URLSearchParams(searchParams);
        nextParams.set('journey_action', nextAction.id);
        setSearchParams(nextParams, { replace: true });
      }} /></section> : null}
      {children}
    </div>
  );
};
