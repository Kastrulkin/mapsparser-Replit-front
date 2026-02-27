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
  total_count?: number;
  limit?: number;
  offset?: number;
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

type ActionLifecycleSummaryResponse = {
  success: boolean;
  action_id?: string;
  tenant_id?: string;
  capability?: string;
  status?: string;
  trace_id?: string;
  total_events?: number;
  filtered_events?: number;
  unknown_events?: number;
  full?: boolean;
  lifecycle?: Record<string, { count?: number; last_at?: string | null }>;
  error?: string;
};

type CallbackAttemptItem = {
  id: string;
  outbox_id: string;
  action_id: string;
  tenant_id: string;
  event_type: string;
  attempt_no: number;
  success: boolean;
  http_status?: number | null;
  duration_ms?: number | null;
  error_text?: string | null;
  response_excerpt?: string | null;
  created_at: string;
};

type CallbackAttemptsResponse = {
  success: boolean;
  action_id?: string;
  tenant_id?: string;
  items?: CallbackAttemptItem[];
  limit?: number;
  offset?: number;
  total?: number;
  summary?: {
    total_attempts?: number;
    success_attempts?: number;
    failed_attempts?: number;
    avg_duration_ms?: number;
    last_success_at?: string;
    last_failed_at?: string;
  };
  event_type_breakdown?: Array<{
    event_type: string;
    total_attempts?: number;
    success_attempts?: number;
    failed_attempts?: number;
  }>;
  error?: string;
};

interface Props {
  businessId?: string;
}

const ACTION_LIFECYCLE_STATUSES = ['pending_human', 'approved', 'rejected', 'expired', 'completed'] as const;
type ActionLifecycleStatus = (typeof ACTION_LIFECYCLE_STATUSES)[number];

function getActionLifecycleStatus(event: ActionTimelineEvent): ActionLifecycleStatus | null {
  const status = String(event.status || '').toLowerCase();
  if ((ACTION_LIFECYCLE_STATUSES as readonly string[]).includes(status)) {
    return status as ActionLifecycleStatus;
  }
  const eventType = String(event.event_type || '').toLowerCase();
  if ((ACTION_LIFECYCLE_STATUSES as readonly string[]).includes(eventType)) {
    return eventType as ActionLifecycleStatus;
  }
  const toStatus = String(event.details?.to_status || '').toLowerCase();
  if ((ACTION_LIFECYCLE_STATUSES as readonly string[]).includes(toStatus)) {
    return toStatus as ActionLifecycleStatus;
  }
  return null;
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
  const [timelineLifecycleQuickFilter, setTimelineLifecycleQuickFilter] = useState<'all' | ActionLifecycleStatus>('all');
  const [timelineLifecycleOnly, setTimelineLifecycleOnly] = useState(false);
  const [timelineSearch, setTimelineSearch] = useState<string>('');
  const [timelineOnlyProblematic, setTimelineOnlyProblematic] = useState(false);
  const [timelineOffset, setTimelineOffset] = useState(0);
  const [timelineTotal, setTimelineTotal] = useState(0);
  const [actionStatusSnapshot, setActionStatusSnapshot] = useState<ActionStatusResponse | null>(null);
  const [actionBillingSnapshot, setActionBillingSnapshot] = useState<ActionBillingResponse | null>(null);
  const [actionLifecycleSummary, setActionLifecycleSummary] = useState<ActionLifecycleSummaryResponse | null>(null);
  const [actionCallbackAttempts, setActionCallbackAttempts] = useState<CallbackAttemptItem[]>([]);
  const [actionCallbackAttemptsTotal, setActionCallbackAttemptsTotal] = useState(0);
  const [actionCallbackAttemptsSummary, setActionCallbackAttemptsSummary] = useState<{
    total_attempts: number;
    success_attempts: number;
    failed_attempts: number;
    avg_duration_ms: number;
    last_success_at: string;
    last_failed_at: string;
    event_type_breakdown: Array<{
      event_type: string;
      total_attempts: number;
      success_attempts: number;
      failed_attempts: number;
    }>;
  } | null>(null);
  const [actionAttemptsLoading, setActionAttemptsLoading] = useState(false);
  const [attemptsSuccessFilter, setAttemptsSuccessFilter] = useState<'all' | 'true' | 'false'>('all');
  const [attemptsEventTypeFilter, setAttemptsEventTypeFilter] = useState<string>('all');
  const [attemptsSearch, setAttemptsSearch] = useState('');
  const [attemptsOffset, setAttemptsOffset] = useState(0);
  const [actionSnapshotLoading, setActionSnapshotLoading] = useState(false);
  const [autoRefreshEnabled, setAutoRefreshEnabled] = useState(false);
  const [autoRefreshSeconds, setAutoRefreshSeconds] = useState<'15' | '30' | '60'>('30');
  const [lastAutoRefreshAt, setLastAutoRefreshAt] = useState<string | null>(null);
  const [decisionStatus, setDecisionStatus] = useState<'approved' | 'rejected' | 'expired'>('approved');
  const [decisionReason, setDecisionReason] = useState('manual decision from support');
  const [copyMessage, setCopyMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [recovering, setRecovering] = useState(false);
  const [recoverMessage, setRecoverMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const buildTimelineParams = useCallback(
    (options?: { includeOffset?: boolean }) => {
      const includeOffset = options?.includeOffset !== false;
      const params = new URLSearchParams();
      if (businessId) {
        params.set('tenant_id', businessId);
      }
      params.set('limit', '200');
      params.set('offset', String(includeOffset ? timelineOffset : 0));
      if (timelineSourceFilter !== 'all') {
        params.set('source', timelineSourceFilter);
      }
      if (timelineEventFilter !== 'all') {
        params.set('event_type', timelineEventFilter);
      }
      if (timelineStatusFilter !== 'all') {
        params.set('status', timelineStatusFilter);
      }
      const searchText = timelineSearch.trim();
      if (searchText.length > 0) {
        params.set('search', searchText);
      }
      if (timelineOnlyProblematic) {
        params.set('only_problematic', 'true');
      }
      return params;
    },
    [
      businessId,
      timelineOffset,
      timelineSourceFilter,
      timelineEventFilter,
      timelineStatusFilter,
      timelineSearch,
      timelineOnlyProblematic,
    ]
  );

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

  const refreshActionTimeline = useCallback(async () => {
      if (!businessId || !selectedActionId) {
        setTimeline([]);
        setTimelineTotal(0);
        return;
      }
    setTimelineLoading(true);
    try {
      const token = localStorage.getItem('auth_token');
      const params = buildTimelineParams({ includeOffset: true });
      const response = await fetch(
        `/api/capabilities/actions/${encodeURIComponent(selectedActionId)}/timeline?${params.toString()}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      const json: ActionTimelineResponse = await response.json();
      if (!response.ok || !json?.success) {
        throw new Error(json?.error || `HTTP ${response.status}`);
      }
      setTimeline(json.events || []);
      setTimelineTotal(Number(json.total_count || (json.events || []).length || 0));
    } catch (e: any) {
      setTimeline([]);
      setTimelineTotal(0);
      setError(e?.message || 'Не удалось загрузить timeline действий');
    } finally {
      setTimelineLoading(false);
    }
  }, [
    businessId,
    selectedActionId,
    timelineSourceFilter,
    timelineEventFilter,
    timelineStatusFilter,
    timelineSearch,
    timelineOnlyProblematic,
    timelineOffset,
    buildTimelineParams,
  ]);

  useEffect(() => {
    refreshActionTimeline();
  }, [refreshActionTimeline]);

  useEffect(() => {
    setTimelineOffset(0);
  }, [
    selectedActionId,
    timelineSourceFilter,
    timelineEventFilter,
    timelineStatusFilter,
    timelineSearch,
    timelineOnlyProblematic,
  ]);

  useEffect(() => {
    setTimelineOffset(0);
  }, [timelineLifecycleQuickFilter, timelineLifecycleOnly]);

  const refreshActionSnapshots = useCallback(async () => {
    if (!businessId || !selectedActionId) {
      setActionStatusSnapshot(null);
      setActionBillingSnapshot(null);
      setActionLifecycleSummary(null);
      return;
    }
    setActionSnapshotLoading(true);
    try {
      const token = localStorage.getItem('auth_token');
      const [statusRes, billingRes, lifecycleRes] = await Promise.all([
        fetch(
          `/api/capabilities/actions/${encodeURIComponent(selectedActionId)}?tenant_id=${encodeURIComponent(businessId)}`,
          { headers: { Authorization: `Bearer ${token}` } }
        ),
        fetch(
          `/api/capabilities/actions/${encodeURIComponent(selectedActionId)}/billing?tenant_id=${encodeURIComponent(businessId)}`,
          { headers: { Authorization: `Bearer ${token}` } }
        ),
        fetch(
          `/api/capabilities/actions/${encodeURIComponent(selectedActionId)}/lifecycle-summary?tenant_id=${encodeURIComponent(businessId)}&full=true`,
          { headers: { Authorization: `Bearer ${token}` } }
        ),
      ]);
      const statusJson: ActionStatusResponse = await statusRes.json();
      const billingJson: ActionBillingResponse = await billingRes.json();
      const lifecycleJson: ActionLifecycleSummaryResponse = await lifecycleRes.json();
      if (!statusRes.ok || !statusJson?.success) {
        throw new Error(statusJson?.error || `status HTTP ${statusRes.status}`);
      }
      if (!billingRes.ok || !billingJson?.success) {
        throw new Error(billingJson?.error || `billing HTTP ${billingRes.status}`);
      }
      if (!lifecycleRes.ok || !lifecycleJson?.success) {
        throw new Error(lifecycleJson?.error || `lifecycle HTTP ${lifecycleRes.status}`);
      }
      setActionStatusSnapshot(statusJson);
      setActionBillingSnapshot(billingJson);
      setActionLifecycleSummary(lifecycleJson);
    } catch (e: any) {
      setError(e?.message || 'Не удалось загрузить status/billing/lifecycle action');
      setActionStatusSnapshot(null);
      setActionBillingSnapshot(null);
      setActionLifecycleSummary(null);
    } finally {
      setActionSnapshotLoading(false);
    }
  }, [businessId, selectedActionId]);

  useEffect(() => {
    refreshActionSnapshots();
  }, [refreshActionSnapshots]);

  useEffect(() => {
    setAttemptsOffset(0);
  }, [selectedActionId, attemptsSuccessFilter, attemptsEventTypeFilter]);

  const refreshActionAttempts = useCallback(async () => {
    if (!businessId || !selectedActionId) {
      setActionCallbackAttempts([]);
      setActionCallbackAttemptsTotal(0);
      setActionCallbackAttemptsSummary(null);
      return;
    }
    setActionAttemptsLoading(true);
    try {
      const token = localStorage.getItem('auth_token');
      const params = new URLSearchParams();
      params.set('limit', '20');
      params.set('offset', String(attemptsOffset));
      if (attemptsSuccessFilter !== 'all') {
        params.set('success', attemptsSuccessFilter);
      }
      if (attemptsEventTypeFilter !== 'all') {
        params.set('event_type', attemptsEventTypeFilter);
      }
      const response = await fetch(
        `/api/capabilities/actions/${encodeURIComponent(selectedActionId)}/callback-attempts?${params.toString()}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      const json: CallbackAttemptsResponse = await response.json();
      if (!response.ok || !json?.success) {
        throw new Error(json?.error || `HTTP ${response.status}`);
      }
      setActionCallbackAttempts((json.items || []).slice(0, 20));
      setActionCallbackAttemptsTotal(Number(json.total || 0));
      setActionCallbackAttemptsSummary({
        total_attempts: Number(json.summary?.total_attempts || 0),
        success_attempts: Number(json.summary?.success_attempts || 0),
        failed_attempts: Number(json.summary?.failed_attempts || 0),
        avg_duration_ms: Number(json.summary?.avg_duration_ms || 0),
        last_success_at: String(json.summary?.last_success_at || ''),
        last_failed_at: String(json.summary?.last_failed_at || ''),
        event_type_breakdown: (json.event_type_breakdown || []).map((item) => ({
          event_type: String(item.event_type || ''),
          total_attempts: Number(item.total_attempts || 0),
          success_attempts: Number(item.success_attempts || 0),
          failed_attempts: Number(item.failed_attempts || 0),
        })),
      });
    } catch (e: any) {
      setError(e?.message || 'Не удалось загрузить callback attempts action');
      setActionCallbackAttempts([]);
      setActionCallbackAttemptsTotal(0);
      setActionCallbackAttemptsSummary(null);
    } finally {
      setActionAttemptsLoading(false);
    }
  }, [businessId, selectedActionId, attemptsOffset, attemptsSuccessFilter, attemptsEventTypeFilter]);

  useEffect(() => {
    refreshActionAttempts();
  }, [refreshActionAttempts]);

  useEffect(() => {
    if (!autoRefreshEnabled || !businessId || !selectedActionId) return;
    const intervalMs = Math.max(5, Number(autoRefreshSeconds || '30')) * 1000;
    const timerId = window.setInterval(() => {
      refreshActionTimeline();
      refreshActionSnapshots();
      refreshActionAttempts();
      setLastAutoRefreshAt(new Date().toISOString());
    }, intervalMs);
    return () => window.clearInterval(timerId);
  }, [
    autoRefreshEnabled,
    autoRefreshSeconds,
    businessId,
    selectedActionId,
    refreshActionTimeline,
    refreshActionSnapshots,
    refreshActionAttempts,
  ]);

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

  const fetchDiagnosticsBundle = useCallback(async (format?: 'json' | 'markdown') => {
    if (!selectedActionId) return null;
    const token = localStorage.getItem('auth_token');
    const params = buildTimelineParams({ includeOffset: false });
    params.set('full', 'true');
    params.set('attempts_full', 'true');
    if (format === 'markdown') {
      params.set('format', 'markdown');
    }
    const response = await fetch(
      `/api/capabilities/actions/${encodeURIComponent(selectedActionId)}/diagnostics-bundle?${params.toString()}`,
      { headers: { Authorization: `Bearer ${token}` } }
    );
    const json = await response.json();
    if (!response.ok || !json?.success) {
      throw new Error(json?.error || `HTTP ${response.status}`);
    }
    return json;
  }, [selectedActionId, buildTimelineParams]);

  const exportDiagnosticsBundleJson = useCallback(async () => {
    if (!selectedActionId) return;
    try {
      const bundle = await fetchDiagnosticsBundle('json');
      if (!bundle?.success) {
        throw new Error('Diagnostics bundle недоступен');
      }
      const payload = {
        ...bundle,
        exported_at: new Date().toISOString(),
      };
      const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `action-diagnostics-bundle-${selectedActionId.slice(0, 8)}.json`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (e: any) {
      setError(e?.message || 'Не удалось экспортировать diagnostics bundle');
    }
  }, [selectedActionId, fetchDiagnosticsBundle]);

  const exportDiagnosticsBundleMarkdown = useCallback(async () => {
    if (!selectedActionId) return;
    try {
      const bundle = await fetchDiagnosticsBundle('markdown');
      if (!bundle?.success) {
        throw new Error('Diagnostics bundle недоступен');
      }
      const markdown = String(bundle?.markdown_report || '').trim();
      if (!markdown) {
        throw new Error('Markdown report не сформирован');
      }
      const blob = new Blob([markdown], { type: 'text/markdown;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `action-diagnostics-bundle-${selectedActionId.slice(0, 8)}.md`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (e: any) {
      setError(e?.message || 'Не удалось экспортировать diagnostics markdown');
    }
  }, [selectedActionId, fetchDiagnosticsBundle]);

  const exportSupportPackageJson = useCallback(async () => {
    if (!selectedActionId) return;
    try {
      const json = await fetchDiagnosticsBundle('json');
      if (!json?.success) {
        throw new Error('Support package недоступен');
      }
      const payload = {
        ...json,
        exported_at: new Date().toISOString(),
      };
      const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `action-support-package-${selectedActionId.slice(0, 8)}.json`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (e: any) {
      setError(e?.message || 'Не удалось экспортировать support package');
    }
  }, [selectedActionId, fetchDiagnosticsBundle]);

  const buildIncidentReportMarkdown = useCallback(async () => {
    if (!selectedActionId) {
      throw new Error('Action не выбран');
    }
    let diagnosticsMarkdown = '';
    try {
      const bundle = await fetchDiagnosticsBundle('markdown');
      if (bundle?.success && typeof bundle?.markdown_report === 'string') {
        diagnosticsMarkdown = String(bundle.markdown_report).trim();
      }
    } catch (_e) {
      // Fallback to local snapshot below.
    }

    const lifecycleLines = ACTION_LIFECYCLE_STATUSES.map((status) => {
      const item = actionLifecycleSummary?.lifecycle?.[status] || {};
      return `- ${status}: ${Number(item.count || 0)}${item.last_at ? ` (last: ${item.last_at})` : ''}`;
    });

    const attemptBreakdown = (actionCallbackAttemptsSummary?.event_type_breakdown || []).map((item) => {
      return `- ${item.event_type}: total=${item.total_attempts}, sent=${item.success_attempts}, failed=${item.failed_attempts}`;
    });

    const recentEvents = filteredTimeline.slice(-8).map((event) => {
      return `- ${event.occurred_at} | ${event.source}:${event.event_type} | ${event.status || '-'}`;
    });

    const sections = [
      '# OpenClaw Incident Report',
      '',
      `- action_id: \`${selectedActionId}\``,
      `- exported_at: ${new Date().toISOString()}`,
      `- status: \`${actionStatusSnapshot?.status || 'unknown'}\``,
      `- billing: reserve/settle/release = ${(actionBillingSnapshot?.summary?.reserved_tokens ?? 0)}/${(actionBillingSnapshot?.summary?.settled_tokens ?? 0)}/${(actionBillingSnapshot?.summary?.released_tokens ?? 0)}, cost=${actionBillingSnapshot?.summary?.total_cost ?? 0}`,
      '',
      '## Lifecycle summary',
      '',
      ...lifecycleLines,
      '',
      `- events: ${actionLifecycleSummary?.filtered_events ?? 0}/${actionLifecycleSummary?.total_events ?? 0}`,
      `- unknown_events: ${actionLifecycleSummary?.unknown_events ?? 0}`,
      '',
      '## Callback attempt breakdown',
      '',
      ...(attemptBreakdown.length > 0 ? attemptBreakdown : ['- no attempts']),
      '',
      '## Recent timeline',
      '',
      ...(recentEvents.length > 0 ? recentEvents : ['- no timeline events']),
    ];

    if (timelineSummary.lastErrorText) {
      sections.push('', '## Last error', '', `- ${timelineSummary.lastErrorText}`);
    }

    if (diagnosticsMarkdown) {
      sections.push('', '## Diagnostics bundle', '', diagnosticsMarkdown);
    }

    return sections.join('\n');
  }, [
    selectedActionId,
    fetchDiagnosticsBundle,
    actionLifecycleSummary,
    actionCallbackAttemptsSummary,
    filteredTimeline,
    actionStatusSnapshot,
    actionBillingSnapshot,
    timelineSummary.lastErrorText,
  ]);

  const exportIncidentReportMarkdown = useCallback(async () => {
    if (!selectedActionId) return;
    try {
      const markdown = await buildIncidentReportMarkdown();
      const blob = new Blob([markdown], { type: 'text/markdown;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `action-incident-report-${selectedActionId.slice(0, 8)}.md`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (e: any) {
      setError(e?.message || 'Не удалось экспортировать incident report');
    }
  }, [selectedActionId, buildIncidentReportMarkdown]);

  const copyIncidentReport = useCallback(async () => {
    if (!selectedActionId) return;
    try {
      const markdown = await buildIncidentReportMarkdown();
      await navigator.clipboard.writeText(markdown);
      setCopyMessage('Incident report скопирован');
      setTimeout(() => setCopyMessage(null), 2500);
    } catch (e: any) {
      setError(e?.message || 'Не удалось скопировать incident report');
    }
  }, [selectedActionId, buildIncidentReportMarkdown]);

  const copyActionDiagnostics = useCallback(async () => {
    if (!selectedActionId) return;
    const problematic = filteredTimeline.filter((event) => isProblematicTimelineEvent(event));
    const lines: string[] = [
      `action_id: ${selectedActionId}`,
      `exported_at: ${new Date().toISOString()}`,
      `status: ${actionStatusSnapshot?.status || 'unknown'}`,
      `billing reserve/settle/release: ${actionBillingSnapshot?.summary?.reserved_tokens ?? 0}/${actionBillingSnapshot?.summary?.settled_tokens ?? 0}/${actionBillingSnapshot?.summary?.released_tokens ?? 0}`,
      `billing cost: ${actionBillingSnapshot?.summary?.total_cost ?? 0}`,
      `timeline total/filtered/problematic: ${timeline.length}/${filteredTimeline.length}/${problematic.length}`,
      `filters: source=${timelineSourceFilter}, event=${timelineEventFilter}, status=${timelineStatusFilter}, search=${timelineSearch || '-'}, only_problematic=${timelineOnlyProblematic}`,
      '',
      'recent events:',
    ];
    filteredTimeline.slice(-10).forEach((event, idx) => {
      lines.push(
        `${idx + 1}. ${event.occurred_at} | ${event.source} | ${event.event_type} | ${event.status || '-'} | ${JSON.stringify(event.details || {})}`
      );
    });
    if (timelineSummary.lastErrorText) {
      lines.push('');
      lines.push(`last_error: ${timelineSummary.lastErrorText}`);
    }
    const report = lines.join('\n');
    try {
      await navigator.clipboard.writeText(report);
      setCopyMessage('Diagnostics скопированы в буфер');
      setTimeout(() => setCopyMessage(null), 2500);
    } catch (_e) {
      setError('Не удалось скопировать diagnostics в буфер');
    }
  }, [
    selectedActionId,
    filteredTimeline,
    isProblematicTimelineEvent,
    actionStatusSnapshot,
    actionBillingSnapshot,
    timeline,
    timelineSourceFilter,
    timelineEventFilter,
    timelineStatusFilter,
    timelineSearch,
    timelineOnlyProblematic,
    timelineSummary.lastErrorText,
  ]);

  const copyActionDiagnosticsTelegram = useCallback(async () => {
    if (!selectedActionId) return;
    const problematic = filteredTimeline.filter((event) => isProblematicTimelineEvent(event));
    const shortId = selectedActionId.slice(0, 8);
    const lines: string[] = [
      `OpenClaw diagnostics`,
      `action: ${shortId}`,
      `status: ${actionStatusSnapshot?.status || 'unknown'}`,
      `billing: ${actionBillingSnapshot?.summary?.reserved_tokens ?? 0}/${actionBillingSnapshot?.summary?.settled_tokens ?? 0}/${actionBillingSnapshot?.summary?.released_tokens ?? 0} (reserve/settle/release), cost=${actionBillingSnapshot?.summary?.total_cost ?? 0}`,
      `timeline: total=${timeline.length}, filtered=${filteredTimeline.length}, problematic=${problematic.length}`,
    ];
    if (timelineSummary.lastRetryDlqAt) {
      lines.push(`last_retry_dlq: ${timelineSummary.lastRetryDlqAt} (${timelineSummary.lastRetryDlqStatus || 'event'})`);
    }
    if (timelineSummary.lastErrorAt) {
      lines.push(`last_error_at: ${timelineSummary.lastErrorAt}`);
    }
    if (timelineSummary.lastErrorText) {
      lines.push(`last_error: ${timelineSummary.lastErrorText}`);
    }
    const lastEvents = filteredTimeline.slice(-3).map((event) => {
      return `- ${event.occurred_at} | ${event.source}:${event.event_type} | ${event.status || '-'}`;
    });
    if (lastEvents.length > 0) {
      lines.push(`recent:`);
      lines.push(...lastEvents);
    }
    const report = lines.join('\n');
    try {
      await navigator.clipboard.writeText(report);
      setCopyMessage('Telegram-сводка скопирована');
      setTimeout(() => setCopyMessage(null), 2500);
    } catch (_e) {
      setError('Не удалось скопировать Telegram-сводку');
    }
  }, [
    selectedActionId,
    filteredTimeline,
    isProblematicTimelineEvent,
    actionStatusSnapshot,
    actionBillingSnapshot,
    timeline.length,
    timelineSummary.lastRetryDlqAt,
    timelineSummary.lastRetryDlqStatus,
    timelineSummary.lastErrorAt,
    timelineSummary.lastErrorText,
  ]);

  const copyActionM2MCurl = useCallback(async () => {
    if (!selectedActionId || !businessId) return;
    const actionId = selectedActionId;
    const tenantId = businessId;
    const lines: string[] = [
      "# Set your token first",
      "OPENCLAW_TOKEN='<token>'",
      `TENANT_ID='${tenantId}'`,
      `ACTION_ID='${actionId}'`,
      "",
      "curl -fsS -H \"X-OpenClaw-Token: ${OPENCLAW_TOKEN}\" \\",
      "  \"http://localhost:8000/api/openclaw/capabilities/actions/${ACTION_ID}?tenant_id=${TENANT_ID}\" | jq .",
      "",
      "curl -fsS -H \"X-OpenClaw-Token: ${OPENCLAW_TOKEN}\" \\",
      "  \"http://localhost:8000/api/openclaw/capabilities/actions/${ACTION_ID}/billing?tenant_id=${TENANT_ID}\" | jq .",
      "",
      "curl -fsS -H \"X-OpenClaw-Token: ${OPENCLAW_TOKEN}\" \\",
      "  \"http://localhost:8000/api/openclaw/capabilities/actions/${ACTION_ID}/timeline?tenant_id=${TENANT_ID}&limit=200\" | jq .",
      "",
      "curl -fsS -H \"X-OpenClaw-Token: ${OPENCLAW_TOKEN}\" \\",
      "  \"http://localhost:8000/api/openclaw/capabilities/actions/${ACTION_ID}/callback-attempts?tenant_id=${TENANT_ID}&limit=200&offset=0\" | jq .",
      "",
      "curl -fsS -H \"X-OpenClaw-Token: ${OPENCLAW_TOKEN}\" \\",
      "  \"http://localhost:8000/api/openclaw/capabilities/actions/${ACTION_ID}/diagnostics-bundle?tenant_id=${TENANT_ID}&limit=200&full=true&attempts_full=true\" | jq .",
      "",
      "OPENCLAW_TOKEN='${OPENCLAW_TOKEN}' TENANT_ID='${TENANT_ID}' ACTION_ID='${ACTION_ID}' ./scripts/diagnose_openclaw_integration.sh",
    ];
    try {
      await navigator.clipboard.writeText(lines.join('\n'));
      setCopyMessage('M2M cURL-команды скопированы');
      setTimeout(() => setCopyMessage(null), 2500);
    } catch (_e) {
      setError('Не удалось скопировать M2M cURL');
    }
  }, [selectedActionId, businessId]);

  const copyActionDecisionCurl = useCallback(async () => {
    if (!selectedActionId || !businessId) return;
    const actionId = selectedActionId;
    const tenantId = businessId;
    const safeReason = (decisionReason || '').replace(/"/g, '\\"');
    const lines: string[] = [
      "OPENCLAW_TOKEN='<token>'",
      `TENANT_ID='${tenantId}'`,
      `ACTION_ID='${actionId}'`,
      '',
      "curl -fsS -X POST \\",
      "  -H \"X-OpenClaw-Token: ${OPENCLAW_TOKEN}\" \\",
      "  -H \"Content-Type: application/json\" \\",
      `  -d '{"tenant_id":"${tenantId}","decision":"${decisionStatus}","reason":"${safeReason}"}' \\`,
      "  \"http://localhost:8000/api/openclaw/capabilities/actions/${ACTION_ID}/decision\" | jq .",
    ];
    try {
      await navigator.clipboard.writeText(lines.join('\n'));
      setCopyMessage('Decision cURL скопирован');
      setTimeout(() => setCopyMessage(null), 2500);
    } catch (_e) {
      setError('Не удалось скопировать Decision cURL');
    }
  }, [selectedActionId, businessId, decisionStatus, decisionReason]);

  const copyOpenClawDiagnoseOneLiner = useCallback(async () => {
    if (!selectedActionId || !businessId) return;
    const command = [
      "cd /opt/seo-app",
      "OPENCLAW_TOKEN='<token>'",
      `TENANT_ID='${businessId}'`,
      `ACTION_ID='${selectedActionId}'`,
      "./scripts/diagnose_openclaw_integration.sh",
    ].join(" ");
    try {
      await navigator.clipboard.writeText(command);
      setCopyMessage('One-liner diagnose команда скопирована');
      setTimeout(() => setCopyMessage(null), 2500);
    } catch (_e) {
      setError('Не удалось скопировать one-liner diagnose команду');
    }
  }, [selectedActionId, businessId]);

  const copyFullSupportPackage = useCallback(async () => {
    if (!selectedActionId || !businessId) return;
    let serverSupportPackage: any = null;
    try {
      serverSupportPackage = await fetchDiagnosticsBundle('json');
    } catch (_e) {
      // Fallback to local snapshots/timeline below.
    }
    const fullTimeline = (serverSupportPackage?.support_package?.timeline?.events as ActionTimelineEvent[]) || filteredTimeline;
    const fullAttempts = (serverSupportPackage?.callback_attempts?.items as CallbackAttemptItem[]) || [];
    const problematic = fullTimeline.filter((event) => isProblematicTimelineEvent(event));
    const diagLines: string[] = [
      `action_id: ${selectedActionId}`,
      `tenant_id: ${businessId}`,
      `exported_at: ${new Date().toISOString()}`,
      `status: ${actionStatusSnapshot?.status || 'unknown'}`,
      `billing reserve/settle/release: ${actionBillingSnapshot?.summary?.reserved_tokens ?? 0}/${actionBillingSnapshot?.summary?.settled_tokens ?? 0}/${actionBillingSnapshot?.summary?.released_tokens ?? 0}`,
      `billing cost: ${actionBillingSnapshot?.summary?.total_cost ?? 0}`,
      `timeline total/problematic: ${fullTimeline.length}/${problematic.length}`,
      `callback attempts total: ${fullAttempts.length}`,
      `filters: source=${timelineSourceFilter}, event=${timelineEventFilter}, status=${timelineStatusFilter}, search=${timelineSearch || '-'}, only_problematic=${timelineOnlyProblematic}`,
      '',
      'recent events:',
    ];
    fullTimeline.slice(-10).forEach((event, idx) => {
      diagLines.push(
        `${idx + 1}. ${event.occurred_at} | ${event.source} | ${event.event_type} | ${event.status || '-'} | ${JSON.stringify(event.details || {})}`
      );
    });
    if (timelineSummary.lastErrorText) {
      diagLines.push('');
      diagLines.push(`last_error: ${timelineSummary.lastErrorText}`);
    }

    const telegramLines: string[] = [
      `OpenClaw diagnostics`,
      `action: ${selectedActionId.slice(0, 8)}`,
      `status: ${actionStatusSnapshot?.status || 'unknown'}`,
      `billing: ${actionBillingSnapshot?.summary?.reserved_tokens ?? 0}/${actionBillingSnapshot?.summary?.settled_tokens ?? 0}/${actionBillingSnapshot?.summary?.released_tokens ?? 0} (reserve/settle/release), cost=${actionBillingSnapshot?.summary?.total_cost ?? 0}`,
      `timeline: total=${fullTimeline.length}, problematic=${problematic.length}`,
      `attempts: total=${fullAttempts.length}`,
    ];
    if (timelineSummary.lastRetryDlqAt) {
      telegramLines.push(`last_retry_dlq: ${timelineSummary.lastRetryDlqAt} (${timelineSummary.lastRetryDlqStatus || 'event'})`);
    }
    if (timelineSummary.lastErrorAt) {
      telegramLines.push(`last_error_at: ${timelineSummary.lastErrorAt}`);
    }
    if (timelineSummary.lastErrorText) {
      telegramLines.push(`last_error: ${timelineSummary.lastErrorText}`);
    }
    const lastEvents = fullTimeline.slice(-3).map((event) => {
      return `- ${event.occurred_at} | ${event.source}:${event.event_type} | ${event.status || '-'}`;
    });
    if (lastEvents.length > 0) {
      telegramLines.push('recent:');
      telegramLines.push(...lastEvents);
    }

    const m2mLines: string[] = [
      "OPENCLAW_TOKEN='<token>'",
      `TENANT_ID='${businessId}'`,
      `ACTION_ID='${selectedActionId}'`,
      '',
      "curl -fsS -H \"X-OpenClaw-Token: ${OPENCLAW_TOKEN}\" \\",
      "  \"http://localhost:8000/api/openclaw/capabilities/actions/${ACTION_ID}?tenant_id=${TENANT_ID}\" | jq .",
      '',
      "curl -fsS -H \"X-OpenClaw-Token: ${OPENCLAW_TOKEN}\" \\",
      "  \"http://localhost:8000/api/openclaw/capabilities/actions/${ACTION_ID}/billing?tenant_id=${TENANT_ID}\" | jq .",
      '',
      "curl -fsS -H \"X-OpenClaw-Token: ${OPENCLAW_TOKEN}\" \\",
      "  \"http://localhost:8000/api/openclaw/capabilities/actions/${ACTION_ID}/timeline?tenant_id=${TENANT_ID}&limit=200\" | jq .",
      "",
      "curl -fsS -H \"X-OpenClaw-Token: ${OPENCLAW_TOKEN}\" \\",
      "  \"http://localhost:8000/api/openclaw/capabilities/actions/${ACTION_ID}/callback-attempts?tenant_id=${TENANT_ID}&limit=200&offset=0\" | jq .",
      "",
      "curl -fsS -H \"X-OpenClaw-Token: ${OPENCLAW_TOKEN}\" \\",
      "  \"http://localhost:8000/api/openclaw/capabilities/actions/${ACTION_ID}/diagnostics-bundle?tenant_id=${TENANT_ID}&limit=200&full=true&attempts_full=true\" | jq .",
    ];

    const decisionReasonEscaped = (decisionReason || '').replace(/"/g, '\\"');
    const decisionLines: string[] = [
      "OPENCLAW_TOKEN='<token>'",
      `TENANT_ID='${businessId}'`,
      `ACTION_ID='${selectedActionId}'`,
      '',
      "curl -fsS -X POST \\",
      "  -H \"X-OpenClaw-Token: ${OPENCLAW_TOKEN}\" \\",
      "  -H \"Content-Type: application/json\" \\",
      `  -d '{"tenant_id":"${businessId}","decision":"${decisionStatus}","reason":"${decisionReasonEscaped}"}' \\`,
      "  \"http://localhost:8000/api/openclaw/capabilities/actions/${ACTION_ID}/decision\" | jq .",
    ];

    const oneLiner = [
      'cd /opt/seo-app',
      "OPENCLAW_TOKEN='<token>'",
      `TENANT_ID='${businessId}'`,
      `ACTION_ID='${selectedActionId}'`,
      './scripts/diagnose_openclaw_integration.sh',
    ].join(' ');

    const report = [
      '# OpenClaw Full Support Package',
      '',
      '## Server support package',
      serverSupportPackage ? JSON.stringify(serverSupportPackage, null, 2) : 'not available (using local snapshots)',
      '',
      '## Diagnostics (detailed)',
      ...diagLines,
      '',
      '## Telegram short',
      ...telegramLines,
      '',
      '## M2M cURL',
      ...m2mLines,
      '',
      '## Decision cURL',
      ...decisionLines,
      '',
      '## Diagnose one-liner',
      oneLiner,
      '',
    ].join('\n');

    try {
      await navigator.clipboard.writeText(report);
      setCopyMessage('Full support package скопирован');
      setTimeout(() => setCopyMessage(null), 2500);
    } catch (_e) {
      setError('Не удалось скопировать full support package');
    }
  }, [
    selectedActionId,
    businessId,
    fetchDiagnosticsBundle,
    filteredTimeline,
    isProblematicTimelineEvent,
    actionStatusSnapshot,
    actionBillingSnapshot,
    timeline.length,
    timelineSourceFilter,
    timelineEventFilter,
    timelineStatusFilter,
    timelineSearch,
    timelineOnlyProblematic,
    timelineSummary.lastRetryDlqAt,
    timelineSummary.lastRetryDlqStatus,
    timelineSummary.lastErrorAt,
    timelineSummary.lastErrorText,
    decisionStatus,
    decisionReason,
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
    let events = timeline;
    if (timelineLifecycleOnly) {
      events = events.filter((event) => getActionLifecycleStatus(event) !== null);
    }
    if (timelineLifecycleQuickFilter !== 'all') {
      events = events.filter((event) => getActionLifecycleStatus(event) === timelineLifecycleQuickFilter);
    }
    return events;
  }, [timeline, timelineLifecycleOnly, timelineLifecycleQuickFilter]);

  const lifecycleTimelineGroups = useMemo(
    () =>
      ACTION_LIFECYCLE_STATUSES.map((status) => ({
        status,
        events: filteredTimeline.filter((event) => getActionLifecycleStatus(event) === status),
      })).filter((group) => group.events.length > 0),
    [filteredTimeline]
  );

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

  const filteredCallbackAttempts = useMemo(() => {
    const q = attemptsSearch.trim().toLowerCase();
    return actionCallbackAttempts.filter((item) => {
      if (!q) return true;
      const haystack = `${item.event_type} ${item.http_status ?? ''} ${item.error_text || ''} ${item.response_excerpt || ''}`.toLowerCase();
      return haystack.includes(q);
    });
  }, [actionCallbackAttempts, attemptsSearch]);

  const attemptsEventTypes = useMemo(
    () => Array.from(new Set(actionCallbackAttempts.map((item) => item.event_type).filter(Boolean))),
    [actionCallbackAttempts]
  );

  const deliveryAttemptSummary = useMemo(() => {
    const attempts = timeline.filter(
      (event) => event.source === 'callback_delivery' && event.event_type === 'attempt'
    );
    const attemptsTotal = attempts.length;
    const attemptsSuccess = attempts.filter((event) => String(event.status || '').toLowerCase() === 'sent').length;
    const attemptsFailed = Math.max(attemptsTotal - attemptsSuccess, 0);
    const lastAttempt = attempts.length > 0 ? attempts[attempts.length - 1] : null;
    const lastAttemptDetails = (lastAttempt?.details || {}) as Record<string, any>;
    return {
      attemptsTotal,
      attemptsSuccess,
      attemptsFailed,
      lastHttpStatus: lastAttemptDetails.http_status ?? null,
      lastError: String(lastAttemptDetails.error_text || '').trim() || null,
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
          {copyMessage && (
            <div className="mb-3 rounded-md border border-indigo-200 bg-indigo-50 px-3 py-2 text-xs text-indigo-700">
              {copyMessage}
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
          <div className="mb-3 grid grid-cols-1 gap-2 md:grid-cols-3">
            <MetricCell label="Callback attempts" value={deliveryAttemptSummary.attemptsTotal} />
            <MetricCell label="Attempts sent/failed" value={`${deliveryAttemptSummary.attemptsSuccess}/${deliveryAttemptSummary.attemptsFailed}`} />
            <MetricCell label="Last attempt HTTP" value={deliveryAttemptSummary.lastHttpStatus ?? '—'} />
          </div>
          {deliveryAttemptSummary.lastError && (
            <div className="mb-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
              Последняя ошибка попытки доставки: {deliveryAttemptSummary.lastError}
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
              <span className="text-[11px] font-semibold uppercase tracking-wide text-gray-500">Lifecycle:</span>
              <button
                type="button"
                onClick={() => setTimelineLifecycleQuickFilter('all')}
                className={`rounded-md border px-2 py-1 text-xs ${
                  timelineLifecycleQuickFilter === 'all'
                    ? 'border-indigo-300 bg-indigo-100 text-indigo-800'
                    : 'border-gray-200 bg-white text-gray-700'
                }`}
              >
                Все
              </button>
              {ACTION_LIFECYCLE_STATUSES.map((status) => (
                <button
                  key={status}
                  type="button"
                  onClick={() => setTimelineLifecycleQuickFilter(status)}
                  className={`rounded-md border px-2 py-1 text-xs ${
                    timelineLifecycleQuickFilter === status
                      ? 'border-indigo-300 bg-indigo-100 text-indigo-800'
                      : 'border-gray-200 bg-white text-gray-700'
                  }`}
                >
                  {status}
                </button>
              ))}
              <button
                type="button"
                onClick={() => setTimelineLifecycleOnly((prev) => !prev)}
                className={`rounded-md border px-2 py-1 text-xs ${
                  timelineLifecycleOnly
                    ? 'border-teal-300 bg-teal-100 text-teal-800'
                    : 'border-gray-200 bg-white text-gray-700'
                }`}
              >
                {timelineLifecycleOnly ? 'Только lifecycle: ON' : 'Только lifecycle: OFF'}
              </button>
            </div>
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={() => setAutoRefreshEnabled((prev) => !prev)}
                disabled={!selectedActionId}
                className={`rounded-md border px-2 py-1.5 text-xs disabled:opacity-60 ${
                  autoRefreshEnabled
                    ? 'border-emerald-300 bg-emerald-100 text-emerald-800'
                    : 'border-gray-200 bg-white text-gray-700'
                }`}
              >
                {autoRefreshEnabled ? 'Auto-refresh: ON' : 'Auto-refresh: OFF'}
              </button>
              <select
                value={autoRefreshSeconds}
                onChange={(e) => setAutoRefreshSeconds(e.target.value as '15' | '30' | '60')}
                disabled={!selectedActionId}
                className="rounded-md border border-gray-200 bg-white px-2 py-1.5 text-xs text-gray-700 disabled:opacity-60"
              >
                <option value="15">15s</option>
                <option value="30">30s</option>
                <option value="60">60s</option>
              </select>
              <button
                type="button"
                onClick={refreshActionTimeline}
                disabled={timelineLoading || !selectedActionId}
                className="rounded-md border border-gray-200 bg-white px-2 py-1.5 text-xs text-gray-700 disabled:opacity-60"
              >
                {timelineLoading ? 'Обновление timeline...' : 'Обновить timeline'}
              </button>
              <button
                type="button"
                onClick={refreshActionSnapshots}
                disabled={actionSnapshotLoading || !selectedActionId}
                className="rounded-md border border-gray-200 bg-white px-2 py-1.5 text-xs text-gray-700 disabled:opacity-60"
              >
                {actionSnapshotLoading ? 'Обновление...' : 'Обновить status/billing/lifecycle'}
              </button>
              <button
                type="button"
                onClick={refreshActionAttempts}
                disabled={actionAttemptsLoading || !selectedActionId}
                className="rounded-md border border-gray-200 bg-white px-2 py-1.5 text-xs text-gray-700 disabled:opacity-60"
              >
                {actionAttemptsLoading ? 'Обновление attempts...' : 'Обновить callback attempts'}
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
              <button
                type="button"
                onClick={exportSupportPackageJson}
                disabled={!selectedActionId}
                className="rounded-md border border-cyan-200 bg-cyan-50 px-2 py-1.5 text-xs text-cyan-700 disabled:opacity-60"
              >
                Экспорт support package JSON
              </button>
              <button
                type="button"
                onClick={exportDiagnosticsBundleJson}
                disabled={!selectedActionId}
                className="rounded-md border border-fuchsia-200 bg-fuchsia-50 px-2 py-1.5 text-xs text-fuchsia-700 disabled:opacity-60"
              >
                Экспорт diagnostics JSON
              </button>
              <button
                type="button"
                onClick={exportDiagnosticsBundleMarkdown}
                disabled={!selectedActionId}
                className="rounded-md border border-violet-200 bg-violet-50 px-2 py-1.5 text-xs text-violet-700 disabled:opacity-60"
              >
                Экспорт diagnostics MD
              </button>
              <button
                type="button"
                onClick={exportIncidentReportMarkdown}
                disabled={!selectedActionId}
                className="rounded-md border border-rose-200 bg-rose-50 px-2 py-1.5 text-xs text-rose-700 disabled:opacity-60"
              >
                Экспорт incident report MD
              </button>
              <button
                type="button"
                onClick={copyActionDiagnostics}
                disabled={!selectedActionId}
                className="rounded-md border border-emerald-200 bg-emerald-50 px-2 py-1.5 text-xs text-emerald-700 disabled:opacity-60"
              >
                Скопировать diagnostics
              </button>
              <button
                type="button"
                onClick={copyActionDiagnosticsTelegram}
                disabled={!selectedActionId}
                className="rounded-md border border-teal-200 bg-teal-50 px-2 py-1.5 text-xs text-teal-700 disabled:opacity-60"
              >
                Копировать для Telegram
              </button>
              <button
                type="button"
                onClick={copyIncidentReport}
                disabled={!selectedActionId}
                className="rounded-md border border-pink-200 bg-pink-50 px-2 py-1.5 text-xs text-pink-700 disabled:opacity-60"
              >
                Скопировать incident report
              </button>
              <button
                type="button"
                onClick={copyActionM2MCurl}
                disabled={!selectedActionId || !businessId}
                className="rounded-md border border-slate-200 bg-slate-50 px-2 py-1.5 text-xs text-slate-700 disabled:opacity-60"
              >
                Copy cURL (M2M)
              </button>
            </div>
            {autoRefreshEnabled && (
              <div className="mb-2 text-[11px] text-emerald-700">
                Auto-refresh каждые {autoRefreshSeconds}с
                {lastAutoRefreshAt ? ` · последнее: ${formatDateTime(lastAutoRefreshAt)}` : ''}
              </div>
            )}
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
            <div className="mb-2 rounded border border-gray-200 bg-white px-2 py-2 text-xs text-gray-700">
              <div className="mb-1 font-semibold text-gray-800">Lifecycle summary (full action)</div>
              <div className="mb-1 flex flex-wrap items-center gap-1">
                {ACTION_LIFECYCLE_STATUSES.map((status) => {
                  const item = actionLifecycleSummary?.lifecycle?.[status] || {};
                  const count = Number(item.count || 0);
                  return (
                    <span
                      key={status}
                      className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 ${
                        count > 0
                          ? 'border-indigo-200 bg-indigo-50 text-indigo-700'
                          : 'border-gray-200 bg-gray-50 text-gray-500'
                      }`}
                    >
                      <span>{status}</span>
                      <span className="font-semibold">{count}</span>
                    </span>
                  );
                })}
              </div>
              <div className="text-[11px] text-gray-500">
                events: {actionLifecycleSummary?.filtered_events ?? 0}/{actionLifecycleSummary?.total_events ?? 0}
                {' '}· unknown: {actionLifecycleSummary?.unknown_events ?? 0}
              </div>
            </div>
            <div className="mb-2 rounded border border-gray-200 bg-white px-2 py-2 text-xs text-gray-700">
              <div className="mb-1 font-semibold text-gray-800">M2M decision helper</div>
              <div className="grid grid-cols-1 gap-2 md:grid-cols-3">
                <select
                  value={decisionStatus}
                  onChange={(e) => setDecisionStatus(e.target.value as 'approved' | 'rejected' | 'expired')}
                  className="rounded-md border border-gray-200 bg-white px-2 py-1.5 text-xs text-gray-700"
                >
                  <option value="approved">approved</option>
                  <option value="rejected">rejected</option>
                  <option value="expired">expired</option>
                </select>
                <input
                  value={decisionReason}
                  onChange={(e) => setDecisionReason(e.target.value)}
                  className="rounded-md border border-gray-200 bg-white px-2 py-1.5 text-xs text-gray-700 md:col-span-2"
                  placeholder="reason..."
                />
              </div>
              <div className="mt-2">
              <button
                type="button"
                onClick={copyActionDecisionCurl}
                disabled={!selectedActionId || !businessId}
                className="rounded-md border border-orange-200 bg-orange-50 px-2 py-1.5 text-xs text-orange-700 disabled:opacity-60"
              >
                Copy cURL (M2M decision)
              </button>
              <button
                type="button"
                onClick={copyOpenClawDiagnoseOneLiner}
                disabled={!selectedActionId || !businessId}
                className="rounded-md border border-violet-200 bg-violet-50 px-2 py-1.5 text-xs text-violet-700 disabled:opacity-60"
              >
                Copy diagnose one-liner
              </button>
              <button
                type="button"
                onClick={copyFullSupportPackage}
                disabled={!selectedActionId || !businessId}
                className="rounded-md border border-fuchsia-200 bg-fuchsia-50 px-2 py-1.5 text-xs text-fuchsia-700 disabled:opacity-60"
              >
                Copy full support package
              </button>
            </div>
            </div>
            <div className="mb-2 rounded border border-gray-200 bg-white px-2 py-2 text-xs text-gray-700">
              <div className="mb-1 font-semibold text-gray-800">
                Callback attempts ({actionCallbackAttempts.length}/{actionCallbackAttemptsTotal})
              </div>
              <div className="mb-2 grid grid-cols-1 gap-2 md:grid-cols-3">
                <MetricCell label="Attempts total" value={actionCallbackAttemptsSummary?.total_attempts ?? 0} />
                <MetricCell label="Attempts sent/failed" value={`${actionCallbackAttemptsSummary?.success_attempts ?? 0}/${actionCallbackAttemptsSummary?.failed_attempts ?? 0}`} />
                <MetricCell label="Avg duration (ms)" value={actionCallbackAttemptsSummary?.avg_duration_ms ?? 0} />
              </div>
              {(actionCallbackAttemptsSummary?.last_success_at || actionCallbackAttemptsSummary?.last_failed_at) && (
                <div className="mb-2 text-[11px] text-gray-500">
                  last_success: {actionCallbackAttemptsSummary?.last_success_at || '—'} · last_failed: {actionCallbackAttemptsSummary?.last_failed_at || '—'}
                </div>
              )}
              {!!actionCallbackAttemptsSummary?.event_type_breakdown?.length && (
                <div className="mb-2 flex flex-wrap items-center gap-1">
                  {actionCallbackAttemptsSummary.event_type_breakdown.map((item) => (
                    <span
                      key={item.event_type}
                      className="inline-flex items-center gap-1 rounded-md border border-sky-200 bg-sky-50 px-2 py-0.5 text-[11px] text-sky-700"
                    >
                      <span>{item.event_type}</span>
                      <span className="font-semibold">{item.success_attempts}/{item.failed_attempts}</span>
                      <span className="text-sky-500">({item.total_attempts})</span>
                    </span>
                  ))}
                </div>
              )}
              <div className="mb-2 grid grid-cols-1 gap-2 md:grid-cols-2">
                <input
                  value={attemptsSearch}
                  onChange={(e) => setAttemptsSearch(e.target.value)}
                  className="rounded-md border border-gray-200 bg-white px-2 py-1.5 text-xs text-gray-700"
                  placeholder="Поиск по http/error/response..."
                />
                <select
                  value={attemptsSuccessFilter}
                  onChange={(e) => setAttemptsSuccessFilter(e.target.value as 'all' | 'true' | 'false')}
                  className="rounded-md border border-gray-200 bg-white px-2 py-1.5 text-xs text-gray-700"
                >
                  <option value="all">Все статусы attempts</option>
                  <option value="true">Только sent</option>
                  <option value="false">Только failed</option>
                </select>
                <select
                  value={attemptsEventTypeFilter}
                  onChange={(e) => setAttemptsEventTypeFilter(e.target.value)}
                  className="rounded-md border border-gray-200 bg-white px-2 py-1.5 text-xs text-gray-700"
                >
                  <option value="all">Все event_type</option>
                  {attemptsEventTypes.map((eventType) => (
                    <option key={eventType} value={eventType}>{eventType}</option>
                  ))}
                </select>
                <div className="text-xs text-gray-500">
                  Страница: {Math.floor(attemptsOffset / 20) + 1} / {Math.max(1, Math.ceil(actionCallbackAttemptsTotal / 20))}
                </div>
              </div>
              {actionAttemptsLoading ? (
                <div className="text-gray-500">Загрузка callback attempts...</div>
              ) : filteredCallbackAttempts.length === 0 ? (
                <div className="text-gray-500">Попытки доставки для action пока отсутствуют</div>
              ) : (
                <div className="max-h-40 overflow-y-auto">
                  {filteredCallbackAttempts.map((item) => (
                    <div key={item.id} className="mb-1 rounded border border-gray-100 bg-gray-50 px-2 py-1">
                      <div className="font-medium text-gray-800">
                        {item.created_at} · {item.event_type} · attempt #{item.attempt_no} · {item.success ? 'sent' : 'failed'}
                      </div>
                      <div className="text-gray-500">
                        http={item.http_status ?? '—'} · duration={item.duration_ms ?? '—'}ms
                      </div>
                      {item.error_text && <div className="text-amber-700">error: {item.error_text}</div>}
                    </div>
                  ))}
                </div>
              )}
              <div className="mt-2 flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setAttemptsOffset((prev) => Math.max(0, prev - 20))}
                  disabled={actionAttemptsLoading || attemptsOffset <= 0}
                  className="rounded-md border border-gray-200 bg-white px-2 py-1 text-xs text-gray-700 disabled:opacity-60"
                >
                  Prev
                </button>
                <button
                  type="button"
                  onClick={() => setAttemptsOffset((prev) => prev + 20)}
                  disabled={actionAttemptsLoading || attemptsOffset + 20 >= actionCallbackAttemptsTotal}
                  className="rounded-md border border-gray-200 bg-white px-2 py-1 text-xs text-gray-700 disabled:opacity-60"
                >
                  Next
                </button>
              </div>
            </div>
            <div className="mb-2 text-[11px] text-gray-500">
              Показано: {filteredTimeline.length} / {timelineTotal || timeline.length} ·
              {' '}Страница: {Math.floor(timelineOffset / 200) + 1} / {Math.max(1, Math.ceil((timelineTotal || timeline.length) / 200))}
            </div>
            {lifecycleTimelineGroups.length > 0 && (
              <div className="mb-2 rounded border border-gray-200 bg-white px-2 py-2 text-xs text-gray-700">
                <div className="mb-1 font-semibold text-gray-800">Lifecycle timeline (grouped)</div>
                <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
                  {lifecycleTimelineGroups.map((group) => (
                    <div key={group.status} className="rounded border border-gray-100 bg-gray-50 px-2 py-1.5">
                      <div className="mb-1 font-medium text-gray-800">
                        {group.status} · {group.events.length}
                      </div>
                      <div className="max-h-24 space-y-1 overflow-y-auto">
                        {group.events.slice(0, 6).map((event, idx) => (
                          <div key={`${group.status}:${event.occurred_at}:${idx}`} className="text-[11px] text-gray-600">
                            {event.occurred_at} · {event.source}:{event.event_type}
                          </div>
                        ))}
                        {group.events.length > 6 && (
                          <div className="text-[11px] text-gray-500">ещё {group.events.length - 6}</div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
            <div className="mb-2 flex items-center gap-2">
              <button
                type="button"
                onClick={() => setTimelineOffset((prev) => Math.max(0, prev - 200))}
                disabled={timelineLoading || timelineOffset <= 0}
                className="rounded-md border border-gray-200 bg-white px-2 py-1 text-xs text-gray-700 disabled:opacity-60"
              >
                Prev
              </button>
              <button
                type="button"
                onClick={() => setTimelineOffset((prev) => prev + 200)}
                disabled={timelineLoading || timelineOffset + 200 >= (timelineTotal || 0)}
                className="rounded-md border border-gray-200 bg-white px-2 py-1 text-xs text-gray-700 disabled:opacity-60"
              >
                Next
              </button>
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
