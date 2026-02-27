import { useCallback, useEffect, useMemo, useState } from 'react';
import { AlertTriangle, CheckCircle2, RefreshCcw, Wrench } from 'lucide-react';

type HealthResponse = {
  success: boolean;
  status?: 'ready' | 'degraded' | string;
  ready?: boolean;
  checks?: {
    token_configured: boolean;
    callbacks_enabled: boolean;
    dlq_count: number;
    retry_backlog: number;
    stuck_retry: number;
  };
  metrics?: {
    sent: number;
    retry: number;
    dlq: number;
    pending: number;
    sending: number;
    stuck_retry: number;
    total_recent: number;
    delivery_success_rate: number;
  };
  alerts?: Array<{
    code: string;
    severity: string;
    message: string;
  }>;
  snapshot_id?: string | null;
  window_minutes?: number;
  error?: string;
};

type HealthTrendItem = {
  id: string;
  status: 'ready' | 'degraded' | string;
  ready: boolean;
  captured_at: string;
  checks?: {
    dlq_count?: number;
    stuck_retry?: number;
  };
};

type TrendResponse = {
  success: boolean;
  items?: HealthTrendItem[];
  count?: number;
  error?: string;
};

type BillingReconcileIssueItem = {
  action_id: string;
  status?: string;
  issues?: string[];
};

type BillingReconcileResponse = {
  success: boolean;
  summary?: {
    actions_checked?: number;
    actions_with_issues?: number;
    issue_count?: number;
    tokenusage_minus_settled?: number;
  };
  items?: BillingReconcileIssueItem[];
  error?: string;
};

type ActionListItem = {
  action_id: string;
  capability?: string;
  status?: string;
  created_at?: string;
};

type ActionListResponse = {
  success: boolean;
  items?: ActionListItem[];
  error?: string;
};

type ActionTimelineEvent = {
  occurred_at: string;
  source: string;
  event_type: string;
  status?: string | null;
  details?: Record<string, any>;
};

type ActionTimelineResponse = {
  success: boolean;
  action_id?: string;
  capability?: string;
  status?: string;
  events?: ActionTimelineEvent[];
  error?: string;
};

type ActionStatusResponse = {
  success: boolean;
  status?: string;
  error?: string;
  error_code?: string;
  action_id?: string;
};

type ActionBillingResponse = {
  success: boolean;
  summary?: {
    reserved_tokens?: number;
    settled_tokens?: number;
    released_tokens?: number;
    inflight_reserved_tokens?: number;
    total_cost?: number;
  };
  error?: string;
};

interface Props {
  businessId?: string;
}

export default function OpenClawOutboxMetrics({ businessId }: Props) {
  const [data, setData] = useState<HealthResponse | null>(null);
  const [trend, setTrend] = useState<HealthTrendItem[]>([]);
  const [billing, setBilling] = useState<BillingReconcileResponse | null>(null);
  const [actions, setActions] = useState<ActionListItem[]>([]);
  const [selectedActionId, setSelectedActionId] = useState<string>('');
  const [timeline, setTimeline] = useState<ActionTimelineEvent[]>([]);
  const [timelineLoading, setTimelineLoading] = useState(false);
  const [timelineSourceFilter, setTimelineSourceFilter] = useState<string>('all');
  const [timelineEventFilter, setTimelineEventFilter] = useState<string>('all');
  const [timelineStatusFilter, setTimelineStatusFilter] = useState<string>('all');
  const [timelineSearch, setTimelineSearch] = useState<string>('');
  const [timelineOnlyProblematic, setTimelineOnlyProblematic] = useState(false);
  const [actionStatusSnapshot, setActionStatusSnapshot] = useState<ActionStatusResponse | null>(null);
  const [actionBillingSnapshot, setActionBillingSnapshot] = useState<ActionBillingResponse | null>(null);
  const [actionSnapshotLoading, setActionSnapshotLoading] = useState(false);
  const [loading, setLoading] = useState(false);
  const [recovering, setRecovering] = useState(false);
  const [recoverMessage, setRecoverMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!businessId) return;
    setLoading(true);
    setError(null);
    try {
      const token = localStorage.getItem('auth_token');
      const [healthRes, trendRes, billingRes, actionsRes] = await Promise.all([
        fetch(
          `/api/capabilities/health?tenant_id=${encodeURIComponent(businessId)}&window_minutes=60`,
          { headers: { Authorization: `Bearer ${token}` } }
        ),
        fetch(
          `/api/capabilities/health/trend?tenant_id=${encodeURIComponent(businessId)}&window_minutes=720&limit=24`,
          { headers: { Authorization: `Bearer ${token}` } }
        ),
        fetch(
          `/api/capabilities/billing/reconcile?tenant_id=${encodeURIComponent(businessId)}&window_minutes=1440&limit=50`,
          { headers: { Authorization: `Bearer ${token}` } }
        ),
        fetch(
          `/api/capabilities/actions?tenant_id=${encodeURIComponent(businessId)}&limit=20&offset=0`,
          { headers: { Authorization: `Bearer ${token}` } }
        ),
      ]);

      const healthJson: HealthResponse = await healthRes.json();
      const trendJson: TrendResponse = await trendRes.json();
      const billingData: BillingReconcileResponse = await billingRes.json();
      const actionsData: ActionListResponse = await actionsRes.json();

      if (!healthRes.ok || !healthJson?.success) {
        throw new Error(healthJson?.error || `HTTP ${healthRes.status}`);
      }
      if (!trendRes.ok || !trendJson?.success) {
        throw new Error(trendJson?.error || `HTTP ${trendRes.status}`);
      }
      if (!billingRes.ok || !billingData?.success) {
        throw new Error(billingData?.error || `HTTP ${billingRes.status}`);
      }
      if (!actionsRes.ok || !actionsData?.success) {
        throw new Error(actionsData?.error || `HTTP ${actionsRes.status}`);
      }

      setData(healthJson);
      setTrend((trendJson.items || []).slice(0, 24));
      setBilling(billingData || null);
      const items = (actionsData.items || []).slice(0, 20);
      setActions(items);
      setSelectedActionId((prev) => {
        if (prev && items.some((x) => x.action_id === prev)) return prev;
        return items[0]?.action_id || '';
      });
    } catch (e: any) {
      setError(e?.message || 'Не удалось загрузить состояние интеграции ИИ-агентов');
    } finally {
      setLoading(false);
    }
  }, [businessId]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    const loadTimeline = async () => {
      if (!businessId || !selectedActionId) {
        setTimeline([]);
        return;
      }
      setTimelineLoading(true);
      try {
        const token = localStorage.getItem('auth_token');
        const response = await fetch(
          `/api/capabilities/actions/${encodeURIComponent(selectedActionId)}/timeline?tenant_id=${encodeURIComponent(businessId)}&limit=200`,
          { headers: { Authorization: `Bearer ${token}` } }
        );
        const json: ActionTimelineResponse = await response.json();
        if (!response.ok || !json?.success) {
          throw new Error(json?.error || `HTTP ${response.status}`);
        }
        setTimeline(json.events || []);
      } catch (e: any) {
        setTimeline([]);
        setError(e?.message || 'Не удалось загрузить timeline действий');
      } finally {
        setTimelineLoading(false);
      }
    };
    loadTimeline();
  }, [businessId, selectedActionId]);

  const refreshActionSnapshots = useCallback(async () => {
    if (!businessId || !selectedActionId) {
      setActionStatusSnapshot(null);
      setActionBillingSnapshot(null);
      return;
    }
    setActionSnapshotLoading(true);
    try {
      const token = localStorage.getItem('auth_token');
      const [statusRes, billingRes] = await Promise.all([
        fetch(
          `/api/capabilities/actions/${encodeURIComponent(selectedActionId)}?tenant_id=${encodeURIComponent(businessId)}`,
          { headers: { Authorization: `Bearer ${token}` } }
        ),
        fetch(
          `/api/capabilities/actions/${encodeURIComponent(selectedActionId)}/billing?tenant_id=${encodeURIComponent(businessId)}`,
          { headers: { Authorization: `Bearer ${token}` } }
        ),
      ]);
      const statusJson: ActionStatusResponse = await statusRes.json();
      const billingJson: ActionBillingResponse = await billingRes.json();
      if (!statusRes.ok || !statusJson?.success) {
        throw new Error(statusJson?.error || `status HTTP ${statusRes.status}`);
      }
      if (!billingRes.ok || !billingJson?.success) {
        throw new Error(billingJson?.error || `billing HTTP ${billingRes.status}`);
      }
      setActionStatusSnapshot(statusJson);
      setActionBillingSnapshot(billingJson);
    } catch (e: any) {
      setError(e?.message || 'Не удалось загрузить status/billing action');
      setActionStatusSnapshot(null);
      setActionBillingSnapshot(null);
    } finally {
      setActionSnapshotLoading(false);
    }
  }, [businessId, selectedActionId]);

  useEffect(() => {
    refreshActionSnapshots();
  }, [refreshActionSnapshots]);

  const recoverDelivery = useCallback(async () => {
    if (!businessId) return;
    setRecovering(true);
    setRecoverMessage(null);
    setError(null);
    try {
      const token = localStorage.getItem('auth_token');
      const replayRes = await fetch('/api/capabilities/callbacks/outbox/replay', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          tenant_id: businessId,
          include_retry: true,
          limit: 200,
        }),
      });
      const replayJson = await replayRes.json();
      if (!replayRes.ok || !replayJson?.success) {
        throw new Error(replayJson?.error || `Replay failed (${replayRes.status})`);
      }

      const dispatchRes = await fetch('/api/capabilities/callbacks/dispatch', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          tenant_id: businessId,
          batch_size: 200,
        }),
      });
      const dispatchJson = await dispatchRes.json();
      if (!dispatchRes.ok || !dispatchJson?.success) {
        throw new Error(dispatchJson?.error || `Dispatch failed (${dispatchRes.status})`);
      }

      const replayedCount = Number(replayJson?.replayed_count || 0);
      const sent = Number(dispatchJson?.sent || 0);
      const retried = Number(dispatchJson?.retried || 0);
      const dlq = Number(dispatchJson?.dlq || 0);
      setRecoverMessage(`Recovery выполнен: replay=${replayedCount}, sent=${sent}, retried=${retried}, dlq=${dlq}`);
      await load();
    } catch (e: any) {
      setError(e?.message || 'Не удалось выполнить recovery callback-доставки');
    } finally {
      setRecovering(false);
    }
  }, [businessId, load]);

  const exportTimelineJson = useCallback(() => {
    if (!selectedActionId) return;
    const payload = {
      action_id: selectedActionId,
      exported_at: new Date().toISOString(),
      count: filteredTimeline.length,
      events: filteredTimeline,
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `action-timeline-${selectedActionId.slice(0, 8)}.json`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }, [selectedActionId, filteredTimeline]);

  const exportActionBundleJson = useCallback(() => {
    if (!selectedActionId) return;
    const payload = {
      action_id: selectedActionId,
      exported_at: new Date().toISOString(),
      filters: {
        source: timelineSourceFilter,
        event_type: timelineEventFilter,
        status: timelineStatusFilter,
        search: timelineSearch,
        only_problematic: timelineOnlyProblematic,
      },
      action_status: actionStatusSnapshot,
      action_billing: actionBillingSnapshot,
      timeline: {
        total_count: timeline.length,
        filtered_count: filteredTimeline.length,
        events: filteredTimeline,
      },
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `action-bundle-${selectedActionId.slice(0, 8)}.json`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }, [
    selectedActionId,
    timelineSourceFilter,
    timelineEventFilter,
    timelineStatusFilter,
    timelineSearch,
    timelineOnlyProblematic,
    actionStatusSnapshot,
    actionBillingSnapshot,
    timeline,
    filteredTimeline,
  ]);

  const metrics = data?.metrics;
  const checks = data?.checks;
  const alerts = data?.alerts || [];
  const hasAlerts = alerts.length > 0;
  const billingIssues = Number(billing?.summary?.actions_with_issues || 0);
  const billingIssueCount = Number(billing?.summary?.issue_count || 0);
  const isReady = data?.status === 'ready' && !hasAlerts && billingIssues === 0;
  const statusLabel = isReady ? 'Готово к работе' : 'Требует внимания';
  const statusClass = isReady
    ? 'bg-emerald-50 border-emerald-200 text-emerald-700'
    : 'bg-amber-50 border-amber-200 text-amber-800';

  const timelineSources = useMemo(
    () => Array.from(new Set(timeline.map((e) => e.source).filter(Boolean))),
    [timeline]
  );
  const timelineEventTypes = useMemo(
    () => Array.from(new Set(timeline.map((e) => e.event_type).filter(Boolean))),
    [timeline]
  );
  const timelineStatuses = useMemo(
    () => Array.from(new Set(timeline.map((e) => String(e.status || '')).filter((x) => x.length > 0))),
    [timeline]
  );

  const isProblematicTimelineEvent = useCallback((event: ActionTimelineEvent): boolean => {
    const status = String(event.status || '').toLowerCase();
    const eventType = String(event.event_type || '').toLowerCase();
    const details = event.details || {};
    if (status === 'failed' || status === 'retry' || status === 'dlq' || status === 'rejected' || status === 'expired') {
      return true;
    }
    if (eventType === 'retry' || eventType === 'dlq' || eventType === 'failed') {
      return true;
    }
    return Boolean(details.last_error);
  }, []);

  const filteredTimeline = useMemo(() => {
    const q = timelineSearch.trim().toLowerCase();
    return timeline.filter((event) => {
      if (timelineSourceFilter !== 'all' && event.source !== timelineSourceFilter) return false;
      if (timelineEventFilter !== 'all' && event.event_type !== timelineEventFilter) return false;
      if (timelineStatusFilter !== 'all' && String(event.status || '') !== timelineStatusFilter) return false;
      if (timelineOnlyProblematic && !isProblematicTimelineEvent(event)) return false;
      if (!q) return true;
      const haystack = `${event.occurred_at} ${event.source} ${event.event_type} ${event.status || ''} ${JSON.stringify(event.details || {})}`.toLowerCase();
      return haystack.includes(q);
    });
  }, [
    timeline,
    timelineSourceFilter,
    timelineEventFilter,
    timelineStatusFilter,
    timelineOnlyProblematic,
    timelineSearch,
    isProblematicTimelineEvent,
  ]);

  const timelineSummary = useMemo(() => {
    const reversed = [...timeline].reverse();
    const isSuccess = (event: ActionTimelineEvent) => {
      const status = String(event.status || '').toLowerCase();
      return status === 'completed' || status === 'sent' || status === 'approved';
    };
    const isRetryDlq = (event: ActionTimelineEvent) => {
      const status = String(event.status || '').toLowerCase();
      const eventType = String(event.event_type || '').toLowerCase();
      return status === 'retry' || status === 'dlq' || eventType === 'retry' || eventType === 'dlq';
    };
    const lastSuccess = reversed.find((event) => isSuccess(event));
    const lastRetryDlq = reversed.find((event) => isRetryDlq(event));
    const lastErrorEvent = reversed.find((event) => Boolean((event.details || {}).last_error));
    const lastErrorText = String((lastErrorEvent?.details || {}).last_error || '').trim();
    return {
      lastSuccessAt: lastSuccess?.occurred_at || null,
      lastRetryDlqAt: lastRetryDlq?.occurred_at || null,
      lastRetryDlqStatus: lastRetryDlq?.status || lastRetryDlq?.event_type || null,
      lastErrorAt: lastErrorEvent?.occurred_at || null,
      lastErrorText: lastErrorText || null,
    };
  }, [timeline]);

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-gray-900">Связь ИИ-агентов с системой</div>
          <div className="text-xs text-gray-500">Статус интеграции OpenClaw ↔ LocalOS и доставка callback-событий</div>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={recoverDelivery}
            disabled={loading || recovering || !businessId}
            className="inline-flex items-center gap-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-1.5 text-xs text-amber-800 hover:bg-amber-100 disabled:opacity-60"
          >
            <Wrench className={`h-3.5 w-3.5 ${recovering ? 'animate-pulse' : ''}`} />
            {recovering ? 'Recovery...' : 'Восстановить доставку'}
          </button>
          <button
            type="button"
            onClick={load}
            disabled={loading || recovering}
            className="inline-flex items-center gap-2 rounded-md border border-gray-200 px-3 py-1.5 text-xs text-gray-700 hover:bg-gray-50 disabled:opacity-60"
          >
            <RefreshCcw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
            Обновить
          </button>
        </div>
      </div>

      {error ? (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>
      ) : (
        <>
          {recoverMessage && (
            <div className="mb-3 rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-xs text-blue-700">
              {recoverMessage}
            </div>
          )}
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <div className={`inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-xs font-medium ${statusClass}`}>
              {isReady ? <CheckCircle2 className="h-4 w-4" /> : <AlertTriangle className="h-4 w-4" />}
              {statusLabel}
            </div>
            {data?.snapshot_id && (
              <div className="text-[11px] text-gray-500">snapshot: {String(data.snapshot_id).slice(0, 8)}</div>
            )}
          </div>
          <div className="mb-3 grid grid-cols-1 gap-2 md:grid-cols-3">
            <MetricCell
              label="Последний успешный callback"
              value={timelineSummary.lastSuccessAt || '—'}
            />
            <MetricCell
              label="Последний retry/dlq"
              value={
                timelineSummary.lastRetryDlqAt
                  ? `${timelineSummary.lastRetryDlqAt} (${timelineSummary.lastRetryDlqStatus || 'event'})`
                  : '—'
              }
            />
            <MetricCell
              label="Последняя ошибка"
              value={timelineSummary.lastErrorAt || '—'}
            />
          </div>
          {timelineSummary.lastErrorText && (
            <div className="mb-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
              Последняя ошибка callback: {timelineSummary.lastErrorText}
            </div>
          )}

          <div className="grid grid-cols-2 gap-2 md:grid-cols-6">
            <MetricCell label="Sent" value={metrics?.sent ?? 0} />
            <MetricCell label="Retry" value={metrics?.retry ?? 0} />
            <MetricCell label="DLQ" value={metrics?.dlq ?? 0} />
            <MetricCell label="Pending" value={metrics?.pending ?? 0} />
            <MetricCell label="Stuck" value={metrics?.stuck_retry ?? 0} />
            <MetricCell label="Success %" value={`${metrics?.delivery_success_rate ?? 0}%`} />
          </div>

          <div className="mt-3 rounded-md border border-gray-100 bg-gray-50 px-3 py-2">
            <div className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-gray-500">Тренд состояния (последние 24 замера)</div>
            <div className="flex items-center gap-1 overflow-x-auto pb-1">
              {trend.length === 0 ? (
                <span className="text-xs text-gray-500">Нет данных тренда</span>
              ) : (
                trend.map((item) => {
                  const degraded = item.status !== 'ready' || Number(item.checks?.dlq_count || 0) > 0 || Number(item.checks?.stuck_retry || 0) > 0;
                  return (
                    <div
                      key={item.id}
                      title={`${item.captured_at} · ${item.status}`}
                      className={`h-5 w-3 rounded-sm ${degraded ? 'bg-amber-500' : 'bg-emerald-500'}`}
                    />
                  );
                })
              )}
            </div>
          </div>

          <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-3">
            <MetricCell label="Token auth" value={checks?.token_configured ? 'ok' : 'missing'} />
            <MetricCell label="Dispatch" value={checks?.callbacks_enabled ? 'enabled' : 'disabled'} />
            <MetricCell label="DLQ / Stuck" value={`${checks?.dlq_count ?? 0} / ${checks?.stuck_retry ?? 0}`} />
          </div>

          <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-4">
            <MetricCell label="Billing actions" value={billing?.summary?.actions_checked ?? 0} />
            <MetricCell label="Billing issues" value={billingIssues} />
            <MetricCell label="Issue count" value={billingIssueCount} />
            <MetricCell label="Token delta" value={billing?.summary?.tokenusage_minus_settled ?? 0} />
          </div>

          <div className="mt-3">
            {hasAlerts ? (
              <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                <div className="mb-1 flex items-center gap-2 font-medium">
                  <AlertTriangle className="h-4 w-4" />
                  Алерты callback доставки
                </div>
                <ul className="space-y-1">
                  {alerts.map((a) => (
                    <li key={`${a.code}:${a.message}`}>[{a.severity}] {a.message}</li>
                  ))}
                </ul>
              </div>
            ) : (
              <div className="inline-flex items-center gap-2 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-700">
                <CheckCircle2 className="h-4 w-4" />
                Callback доставка в норме
              </div>
            )}
          </div>

          <div className="mt-3">
            {billingIssues > 0 ? (
              <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                <div className="mb-1 flex items-center gap-2 font-medium">
                  <AlertTriangle className="h-4 w-4" />
                  Алерты billing reconciliation
                </div>
                <ul className="space-y-1">
                  {(billing?.items || [])
                    .filter((x) => (x.issues || []).length > 0)
                    .slice(0, 5)
                    .map((item) => (
                      <li key={item.action_id}>
                        action {item.action_id.slice(0, 8)} ({item.status || 'unknown'}): {(item.issues || []).join(', ')}
                      </li>
                    ))}
                </ul>
              </div>
            ) : (
              <div className="inline-flex items-center gap-2 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-700">
                <CheckCircle2 className="h-4 w-4" />
                Billing reconciliation в норме
              </div>
            )}
          </div>

          <div className="mt-3 rounded-md border border-gray-100 bg-gray-50 px-3 py-3">
            <div className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-gray-500">Audit trail callbacks/actions</div>
            <div className="mb-2 flex flex-col gap-2 md:flex-row md:items-center">
              <label className="text-xs text-gray-600">Action</label>
              <select
                value={selectedActionId}
                onChange={(e) => setSelectedActionId(e.target.value)}
                className="rounded-md border border-gray-200 bg-white px-2 py-1.5 text-xs text-gray-800"
              >
                {actions.length === 0 && <option value="">Нет действий</option>}
                {actions.map((item) => (
                  <option key={item.action_id} value={item.action_id}>
                    {item.capability || 'action'} · {item.status || 'unknown'} · {String(item.action_id).slice(0, 8)}
                  </option>
                ))}
              </select>
            </div>
            <div className="mb-2 grid grid-cols-1 gap-2 md:grid-cols-5">
              <select
                value={timelineSourceFilter}
                onChange={(e) => setTimelineSourceFilter(e.target.value)}
                className="rounded-md border border-gray-200 bg-white px-2 py-1.5 text-xs text-gray-700"
              >
                <option value="all">Источник: все</option>
                {timelineSources.map((source) => (
                  <option key={source} value={source}>{source}</option>
                ))}
              </select>
              <select
                value={timelineEventFilter}
                onChange={(e) => setTimelineEventFilter(e.target.value)}
                className="rounded-md border border-gray-200 bg-white px-2 py-1.5 text-xs text-gray-700"
              >
                <option value="all">Событие: все</option>
                {timelineEventTypes.map((eventType) => (
                  <option key={eventType} value={eventType}>{eventType}</option>
                ))}
              </select>
              <select
                value={timelineStatusFilter}
                onChange={(e) => setTimelineStatusFilter(e.target.value)}
                className="rounded-md border border-gray-200 bg-white px-2 py-1.5 text-xs text-gray-700"
              >
                <option value="all">Статус: все</option>
                {timelineStatuses.map((status) => (
                  <option key={status} value={status}>{status}</option>
                ))}
              </select>
              <input
                value={timelineSearch}
                onChange={(e) => setTimelineSearch(e.target.value)}
                className="rounded-md border border-gray-200 bg-white px-2 py-1.5 text-xs text-gray-700"
                placeholder="Поиск по деталям..."
              />
              <button
                type="button"
                onClick={() => setTimelineOnlyProblematic((prev) => !prev)}
                className={`rounded-md border px-2 py-1.5 text-xs ${
                  timelineOnlyProblematic
                    ? 'border-amber-300 bg-amber-100 text-amber-900'
                    : 'border-gray-200 bg-white text-gray-700'
                }`}
              >
                {timelineOnlyProblematic ? 'Проблемные: ON' : 'Проблемные: OFF'}
              </button>
            </div>
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={refreshActionSnapshots}
                disabled={actionSnapshotLoading || !selectedActionId}
                className="rounded-md border border-gray-200 bg-white px-2 py-1.5 text-xs text-gray-700 disabled:opacity-60"
              >
                {actionSnapshotLoading ? 'Обновление...' : 'Обновить status/billing'}
              </button>
              <button
                type="button"
                onClick={exportTimelineJson}
                disabled={!selectedActionId}
                className="rounded-md border border-blue-200 bg-blue-50 px-2 py-1.5 text-xs text-blue-700 disabled:opacity-60"
              >
                Экспорт timeline JSON
              </button>
              <button
                type="button"
                onClick={exportActionBundleJson}
                disabled={!selectedActionId}
                className="rounded-md border border-indigo-200 bg-indigo-50 px-2 py-1.5 text-xs text-indigo-700 disabled:opacity-60"
              >
                Экспорт action bundle
              </button>
            </div>
            <div className="mb-2 grid grid-cols-1 gap-2 md:grid-cols-2">
              <div className="rounded border border-gray-200 bg-white px-2 py-1.5 text-xs text-gray-700">
                <div className="font-semibold text-gray-800">Action status</div>
                <div>{actionStatusSnapshot?.status || '—'}</div>
                {actionStatusSnapshot?.error_code && <div>code: {actionStatusSnapshot.error_code}</div>}
              </div>
              <div className="rounded border border-gray-200 bg-white px-2 py-1.5 text-xs text-gray-700">
                <div className="font-semibold text-gray-800">Action billing</div>
                <div>
                  reserve/settle/release:{' '}
                  {(actionBillingSnapshot?.summary?.reserved_tokens ?? 0)}/
                  {(actionBillingSnapshot?.summary?.settled_tokens ?? 0)}/
                  {(actionBillingSnapshot?.summary?.released_tokens ?? 0)}
                </div>
                <div>cost: {actionBillingSnapshot?.summary?.total_cost ?? 0}</div>
              </div>
            </div>
            <div className="mb-2 text-[11px] text-gray-500">
              Показано: {filteredTimeline.length} / {timeline.length}
            </div>
            <div className="max-h-52 space-y-1 overflow-y-auto pr-1">
              {timelineLoading ? (
                <div className="text-xs text-gray-500">Загрузка timeline...</div>
              ) : filteredTimeline.length === 0 ? (
                <div className="text-xs text-gray-500">Для выбранного action нет событий</div>
              ) : (
                filteredTimeline.map((event, idx) => (
                  <div
                    key={`${event.occurred_at}:${event.source}:${event.event_type}:${idx}`}
                    className={`rounded border px-2 py-1.5 text-xs ${
                      isProblematicTimelineEvent(event)
                        ? 'border-amber-300 bg-amber-50'
                        : 'border-gray-200 bg-white'
                    }`}
                  >
                    <div className="font-medium text-gray-800">
                      {event.occurred_at} · {event.source} · {event.event_type}
                      {event.status ? ` · ${event.status}` : ''}
                    </div>
                    <div className="mt-0.5 text-gray-500">
                      {JSON.stringify(event.details || {})}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function MetricCell({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-md border border-gray-100 bg-gray-50 px-2 py-2">
      <div className="text-[11px] uppercase tracking-wide text-gray-500">{label}</div>
      <div className="text-base font-semibold text-gray-900">{value}</div>
    </div>
  );
}
