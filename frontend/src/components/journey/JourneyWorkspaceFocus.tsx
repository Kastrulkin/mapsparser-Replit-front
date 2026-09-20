import { useCallback, useEffect, useLayoutEffect, useRef, useState, type ReactNode } from 'react';
import { useOutletContext, useSearchParams } from 'react-router-dom';
import { RefreshCw } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { HttpError, newAuth } from '@/lib/auth_new';
import type { JourneyAction } from '@/lib/leadJourney';
import { JourneyActionCard } from './JourneyActionCard';

type WorkspaceContext = { currentBusinessId?: string | null };
type ActionHandoff = { key: string; action: JourneyAction };

export const JourneyWorkspaceFocus = ({ children }: { children: ReactNode }) => {
  const { currentBusinessId } = useOutletContext<WorkspaceContext>();
  const [searchParams, setSearchParams] = useSearchParams();
  const actionId = searchParams.get('journey_action') || '';
  const intentKey = JSON.stringify([currentBusinessId, actionId]);
  const [handoff, setHandoff] = useState<ActionHandoff | null>(null);
  const latestRoute = useRef({ key: intentKey, searchParams });

  useLayoutEffect(() => {
    latestRoute.current = { key: intentKey, searchParams };
  }, [intentKey, searchParams]);

  useLayoutEffect(() => {
    // The keyed panel consumes the command result once, never on a later revisit.
    setHandoff(null);
  }, [intentKey]);

  const continueWith = (nextAction: JourneyAction) => {
    if (latestRoute.current.key !== intentKey || !currentBusinessId) return;
    const nextKey = JSON.stringify([currentBusinessId, nextAction.id]);
    if (nextKey !== intentKey) setHandoff({ key: nextKey, action: nextAction });
    const nextParams = new URLSearchParams(latestRoute.current.searchParams);
    nextParams.set('journey_action', nextAction.id);
    setSearchParams(nextParams, { replace: true });
  };

  return (
    <div className="space-y-5">
      {actionId && currentBusinessId ? <JourneyFocusPanel
        key={intentKey}
        actionId={actionId}
        businessId={currentBusinessId}
        initialAction={handoff?.key === intentKey ? handoff.action : null}
        onContinue={continueWith}
      /> : null}
      {children}
    </div>
  );
};

type JourneyFocusPanelProps = {
  actionId: string;
  businessId: string;
  initialAction: JourneyAction | null;
  onContinue: (action: JourneyAction) => void;
};

const JourneyFocusPanel = ({ actionId, businessId, initialAction, onContinue }: JourneyFocusPanelProps) => {
  const [action, setAction] = useState<JourneyAction | null>(initialAction);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const trackedAction = useRef('');
  const requestScope = useRef({ active: false, generation: 0 });

  useLayoutEffect(() => {
    const scope = { active: true, generation: 0 };
    requestScope.current = scope;
    return () => { scope.active = false; };
  }, []);

  const load = useCallback(() => {
    const scope = requestScope.current;
    if (!scope.active) return;
    const generation = ++scope.generation;
    const isCurrent = () => scope.active && scope.generation === generation;
    setLoading(true);
    setError('');
    void newAuth.makeRequest(`/journey-actions/${encodeURIComponent(actionId)}?business_id=${encodeURIComponent(businessId)}`)
      .then((data) => { if (isCurrent()) setAction(data.action || null); })
      .catch((caught) => {
        if (!isCurrent()) return;
        if (caught instanceof HttpError && (caught.status === 401 || caught.status === 403 || caught.status === 404)) setAction(null);
        setError(caught instanceof Error ? caught.message : 'Не удалось открыть выбранное действие');
      })
      .finally(() => { if (isCurrent()) setLoading(false); });
  }, [actionId, businessId]);

  useEffect(load, [load]);

  useEffect(() => {
    if (!action || trackedAction.current === action.id) return;
    trackedAction.current = action.id;
    void newAuth.makeRequest('/product/events', {
      method: 'POST',
      body: JSON.stringify({
        event_name: 'journey_workspace_opened', surface: 'web', business_id: businessId,
        journey_id: action.journey_id, action_id: action.id, flow_type: action.flow_type,
        entity_type: action.entity_type, entity_id: action.entity_id,
      }),
    }).catch(() => undefined);
  }, [action, businessId]);

  return (
    <>
      {loading ? <section className="h-36 animate-pulse rounded-[24px] bg-slate-100" aria-label="Загружаем выбранное действие" /> : null}
      {error ? <section className="rounded-[24px] bg-red-50 p-5 shadow-[0_0_0_1px_rgba(185,28,28,0.12)]"><h2 className="text-balance font-semibold text-red-950">Не удалось продолжить персональный сценарий</h2><p className="mt-2 text-pretty text-sm text-red-800">{error}</p><Button type="button" variant="outline" onClick={load} className="mt-4 min-h-11 gap-2 transition-transform active:scale-[0.96]"><RefreshCw className="h-4 w-4" />Повторить</Button></section> : null}
      {action ? <section aria-label="Выбранное действие"><JourneyActionCard action={action} businessId={businessId} onUpdated={(nextAction) => {
        const scope = requestScope.current;
        if (!scope.active) return;
        if (!nextAction) {
          load();
          return;
        }
        scope.generation += 1;
        setAction(nextAction);
        setLoading(false);
        setError('');
        onContinue(nextAction);
      }} /></section> : null}
    </>
  );
};
