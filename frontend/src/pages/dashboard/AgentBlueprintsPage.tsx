import type React from 'react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import {
  Bot,
  CheckCircle2,
  Clock3,
  FileText,
  Loader2,
  Play,
  RefreshCw,
  Send,
  ShieldCheck,
  Workflow,
} from 'lucide-react';

import { Button } from '@/components/ui/button';
import {
  DashboardActionPanel,
  DashboardCompactMetricsRow,
  DashboardEmptyState,
  DashboardPageHeader,
  DashboardSection,
} from '@/components/dashboard/DashboardPrimitives';
import { api } from '@/services/api';
import { cn } from '@/lib/utils';

type DashboardContext = {
  currentBusinessId: string | null;
  currentBusiness?: {
    id: string;
    name?: string;
  } | null;
};

type AgentBlueprint = {
  id: string;
  business_id: string;
  name: string;
  category: string;
  description?: string | null;
  status: string;
  latest_version_id?: string | null;
  latest_version_number?: number | null;
  latest_goal?: string | null;
};

type AgentApproval = {
  id: string;
  run_id?: string;
  status: string;
  approval_type: string;
  title: string;
  payload_json?: Record<string, unknown>;
  decision_reason?: string | null;
  requested_at?: string | null;
  run_status?: string | null;
};

type AgentArtifact = {
  id: string;
  artifact_type: string;
  title: string;
  payload_json?: {
    status?: string;
    source?: string;
    count?: number;
    items?: Array<Record<string, unknown>>;
    external_dispatch_performed?: boolean;
    next_step?: string;
    queue_count?: number;
    draft_ids?: string[];
    [key: string]: unknown;
  };
};

type AgentRunStep = {
  id: string;
  step_key: string;
  step_type: string;
  status: string;
  output_json?: {
    status?: string;
    external_dispatch_performed?: boolean;
    queue_count?: number;
    orchestrator?: {
      result?: {
        status?: string;
        external_dispatch_performed?: boolean;
        queue_count?: number;
        [key: string]: unknown;
      };
      [key: string]: unknown;
    };
    [key: string]: unknown;
  };
  error_text?: string | null;
};

type AgentRun = {
  id: string;
  status: string;
  blueprint_id: string;
  steps?: AgentRunStep[];
  artifacts?: AgentArtifact[];
  approvals?: AgentApproval[];
  error_text?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
};

type AgentBlueprintDetails = {
  versions: Array<Record<string, unknown>>;
  runs: AgentRun[];
  approval_queue?: AgentApproval[];
};

const runStatusFilters = [
  { value: 'all', label: 'Все' },
  { value: 'running', label: 'Running' },
  { value: 'waiting_approval', label: 'Approval' },
  { value: 'completed', label: 'Completed' },
  { value: 'failed', label: 'Failed' },
];

const statusTone: Record<string, string> = {
  completed: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  running: 'bg-sky-50 text-sky-700 ring-sky-200',
  waiting_approval: 'bg-amber-50 text-amber-700 ring-amber-200',
  failed: 'bg-rose-50 text-rose-700 ring-rose-200',
  rejected: 'bg-slate-100 text-slate-700 ring-slate-200',
};

const StatusBadge = ({ status }: { status: string }) => (
  <span className={cn('inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ring-1', statusTone[status] || 'bg-slate-50 text-slate-600 ring-slate-200')}>
    {status}
  </span>
);

export const AgentBlueprintsPage = () => {
  const { currentBusinessId, currentBusiness } = useOutletContext<DashboardContext>();
  const [blueprints, setBlueprints] = useState<AgentBlueprint[]>([]);
  const [selectedBlueprintId, setSelectedBlueprintId] = useState<string | null>(null);
  const [blueprintDetails, setBlueprintDetails] = useState<AgentBlueprintDetails | null>(null);
  const [activeRun, setActiveRun] = useState<AgentRun | null>(null);
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [runStatusFilter, setRunStatusFilter] = useState('all');

  const selectedBlueprint = useMemo(
    () => blueprints.find((item) => item.id === selectedBlueprintId) || blueprints[0] || null,
    [blueprints, selectedBlueprintId],
  );

  const pendingApproval = useMemo(
    () => activeRun?.approvals?.find((item) => item.status === 'pending') || null,
    [activeRun],
  );

  const pendingApprovals = useMemo(
    () => blueprintDetails?.approval_queue || [],
    [blueprintDetails?.approval_queue],
  );

  const queuedButNotDispatched = useMemo(() => {
    const artifact = (activeRun?.artifacts || []).find((item) => {
      const payload = item.payload_json || {};
      return payload.status === 'queued_for_dispatch' && payload.external_dispatch_performed === false;
    });
    if (artifact?.payload_json) {
      return artifact.payload_json;
    }
    const step = (activeRun?.steps || []).find((item) => {
      const output = item.output_json?.orchestrator?.result || item.output_json || {};
      return output.status === 'queued_for_dispatch' && output.external_dispatch_performed === false;
    });
    return step?.output_json?.orchestrator?.result || step?.output_json || null;
  }, [activeRun?.artifacts, activeRun?.steps]);

  const metrics = useMemo(
    () => [
      {
        label: 'Workflow agents',
        value: blueprints.length,
        hint: currentBusiness?.name || 'Текущий бизнес',
      },
      {
        label: 'Текущий запуск',
        value: activeRun ? <StatusBadge status={activeRun.status} /> : 'нет',
        hint: activeRun ? activeRun.id.slice(0, 8) : 'Запустите blueprint',
        tone: activeRun?.status === 'waiting_approval' ? 'warning' as const : 'default' as const,
      },
      {
        label: 'Artifacts',
        value: activeRun?.artifacts?.length || 0,
        hint: 'Сохраненные результаты шагов',
      },
      {
        label: 'Approvals',
        value: pendingApprovals.length || activeRun?.approvals?.length || 0,
        hint: pendingApprovals.length ? 'Есть ожидающие решения' : 'Нет ожидающих решений',
        tone: pendingApprovals.length || pendingApproval ? 'warning' as const : 'default' as const,
      },
    ],
    [activeRun, blueprints.length, currentBusiness?.name, pendingApproval, pendingApprovals.length],
  );

  const loadBlueprints = useCallback(async () => {
    if (!currentBusinessId) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const response = await api.get('/agent-blueprints', { params: { business_id: currentBusinessId } });
      const items = Array.isArray(response.data?.blueprints) ? response.data.blueprints : [];
      setBlueprints(items);
      if (!selectedBlueprintId && items.length > 0) {
        setSelectedBlueprintId(items[0].id);
      }
    } catch (requestError) {
      console.error(requestError);
      setError('Не удалось загрузить workflow agents.');
    } finally {
      setLoading(false);
    }
  }, [currentBusinessId, selectedBlueprintId]);

  useEffect(() => {
    void loadBlueprints();
  }, [loadBlueprints]);

  const loadBlueprintDetails = useCallback(async (blueprintId: string) => {
    setError(null);
    try {
      const params = runStatusFilter === 'all' ? {} : { run_status: runStatusFilter };
      const response = await api.get(`/agent-blueprints/${blueprintId}`, { params });
      const details = {
        versions: Array.isArray(response.data?.versions) ? response.data.versions : [],
        runs: Array.isArray(response.data?.runs) ? response.data.runs : [],
        approval_queue: Array.isArray(response.data?.approval_queue) ? response.data.approval_queue : [],
      };
      setBlueprintDetails(details);
    } catch (requestError) {
      console.error(requestError);
      setError('Не удалось загрузить историю blueprint.');
    }
  }, [runStatusFilter]);

  useEffect(() => {
    if (selectedBlueprint?.id) {
      void loadBlueprintDetails(selectedBlueprint.id);
    } else {
      setBlueprintDetails(null);
      setActiveRun(null);
    }
  }, [loadBlueprintDetails, selectedBlueprint?.id]);

  const loadRun = async (runId: string) => {
    setActionLoading(true);
    setError(null);
    try {
      const response = await api.get(`/agent-runs/${runId}`);
      setActiveRun(response.data?.run || null);
    } catch (requestError) {
      console.error(requestError);
      setError('Не удалось загрузить запуск.');
    } finally {
      setActionLoading(false);
    }
  };

  const createDefaultBlueprint = async () => {
    if (!currentBusinessId) {
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      const response = await api.post('/agent-blueprints', {
        business_id: currentBusinessId,
        name: 'Supervised Outreach Agent',
        category: 'outreach',
        description: 'Ищет лиды, готовит shortlist и черновики, внешние отправки только через approval.',
        status: 'active',
        template: 'supervised_outreach',
      });
      const blueprint = response.data?.blueprint;
      await loadBlueprints();
      if (blueprint?.id) {
        setSelectedBlueprintId(blueprint.id);
        await loadBlueprintDetails(blueprint.id);
      }
    } catch (requestError) {
      console.error(requestError);
      setError('Не удалось создать supervised outreach blueprint.');
    } finally {
      setActionLoading(false);
    }
  };

  const startRun = async () => {
    if (!selectedBlueprint) {
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      const response = await api.post(`/agent-blueprints/${selectedBlueprint.id}/runs`, {
        input: {
          source: 'dashboard',
          business_id: currentBusinessId,
          limit: 30,
        },
      });
      setActiveRun(response.data?.run || null);
      await loadBlueprintDetails(selectedBlueprint.id);
    } catch (requestError) {
      console.error(requestError);
      setError('Не удалось запустить blueprint.');
    } finally {
      setActionLoading(false);
    }
  };

  const decideApproval = async (decision: 'approve' | 'reject') => {
    if (!activeRun || !pendingApproval) {
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      const response = await api.post(`/agent-runs/${activeRun.id}/approvals/${pendingApproval.id}/${decision}`, {
        reason: decision === 'approve' ? 'Approved from dashboard' : 'Rejected from dashboard',
      });
      setActiveRun(response.data?.run || null);
    } catch (requestError) {
      console.error(requestError);
      setError('Не удалось применить решение approval.');
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <DashboardPageHeader
        eyebrow="Agent Blueprint Layer"
        title="Workflow agents"
        description="Исполняемые агенты с шагами, артефактами и ручными подтверждениями. Chat persona agents остаются отдельной настройкой голоса."
        icon={Bot}
        actions={(
          <>
            <Button type="button" variant="outline" onClick={loadBlueprints} disabled={loading || !currentBusinessId}>
              <RefreshCw className={cn('mr-2 h-4 w-4', loading && 'animate-spin')} />
              Обновить
            </Button>
            <Button type="button" onClick={createDefaultBlueprint} disabled={actionLoading || !currentBusinessId}>
              {actionLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <ShieldCheck className="mr-2 h-4 w-4" />}
              Создать Outreach Agent
            </Button>
          </>
        )}
      />

      <DashboardCompactMetricsRow items={metrics} />

      {error ? (
        <DashboardActionPanel
          title="Ошибка"
          description={error}
          tone="amber"
        />
      ) : null}

      {!currentBusinessId ? (
        <DashboardEmptyState
          title="Сначала выберите бизнес"
          description="Workflow agents всегда привязаны к конкретному бизнесу и его правам доступа."
        />
      ) : null}

      <div className="grid gap-6 xl:grid-cols-[minmax(20rem,0.9fr)_minmax(0,1.4fr)]">
        <DashboardSection title="Blueprints" description="Это рабочие процессы. Они могут использовать chat persona как голос, но сами отвечают за шаги и approvals.">
          {loading ? (
            <div className="flex items-center gap-2 text-sm text-slate-500">
              <Loader2 className="h-4 w-4 animate-spin" />
              Загружаем agents...
            </div>
          ) : blueprints.length === 0 ? (
            <DashboardEmptyState
              title="Workflow agents пока нет"
              description="Создайте первый Supervised Outreach Agent, чтобы увидеть run timeline, artifacts и approval queue."
            />
          ) : (
            <div className="space-y-3">
              {blueprints.map((blueprint) => {
                const selected = selectedBlueprint?.id === blueprint.id;
                return (
                  <button
                    key={blueprint.id}
                    type="button"
                    className={cn(
                      'w-full rounded-2xl border p-4 text-left transition',
                      selected
                        ? 'border-slate-900 bg-slate-950 text-white shadow-sm'
                        : 'border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50',
                    )}
                    onClick={() => {
                      setSelectedBlueprintId(blueprint.id);
                      setActiveRun(null);
                    }}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="truncate text-sm font-semibold">{blueprint.name}</div>
                        <div className={cn('mt-1 text-xs', selected ? 'text-slate-300' : 'text-slate-500')}>
                          {blueprint.category} · v{blueprint.latest_version_number || '—'}
                        </div>
                      </div>
                      <StatusBadge status={blueprint.status || 'draft'} />
                    </div>
                    {blueprint.latest_goal ? (
                      <div className={cn('mt-3 line-clamp-2 text-sm leading-6', selected ? 'text-slate-200' : 'text-slate-600')}>
                        {blueprint.latest_goal}
                      </div>
                    ) : null}
                  </button>
                );
              })}
            </div>
          )}
        </DashboardSection>

        <DashboardSection
          title="Run timeline"
          description="Запуск идет последовательно, показывает артефакты из outreach pipeline и останавливается на ручном подтверждении."
          actions={(
            <Button type="button" onClick={startRun} disabled={!selectedBlueprint || actionLoading}>
              {actionLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Play className="mr-2 h-4 w-4" />}
              Запустить
            </Button>
          )}
        >
          {!activeRun ? (
            <DashboardEmptyState
              title="Запусков в этой сессии нет"
              description="Выберите blueprint и запустите его или откройте один из последних запусков."
            />
          ) : (
            <div className="space-y-5">
              <DashboardActionPanel
                title={`Run ${activeRun.id.slice(0, 8)}`}
                description={activeRun.error_text || 'История шагов, артефактов и approvals для текущего запуска.'}
                status={<StatusBadge status={activeRun.status} />}
                tone={activeRun.status === 'waiting_approval' ? 'amber' : 'default'}
                actions={pendingApproval ? (
                  <>
                    <Button type="button" variant="outline" onClick={() => decideApproval('reject')} disabled={actionLoading}>
                      Отклонить
                    </Button>
                    <Button type="button" onClick={() => decideApproval('approve')} disabled={actionLoading}>
                      Подтвердить
                    </Button>
                  </>
                ) : null}
              />

              {queuedButNotDispatched ? (
                <DashboardActionPanel
                  title="Queued but not dispatched"
                  description={`Send step поставил batch в очередь: ${Number(queuedButNotDispatched.queue_count || 0)} items. Внешняя отправка не запускалась внутри blueprint runtime.`}
                  status={<StatusBadge status="queued_for_dispatch" />}
                  tone="amber"
                  actions={<Send className="h-4 w-4 text-amber-600" />}
                />
              ) : null}

              <div className="grid gap-4 lg:grid-cols-3">
                <RunColumn title="Steps" icon={Clock3}>
                  {(activeRun.steps || []).map((step) => (
                    <TimelineItem
                      key={step.id}
                      title={step.step_key}
                      meta={step.error_text || step.step_type}
                      status={step.status}
                    />
                  ))}
                </RunColumn>
                <RunColumn title="Artifacts" icon={FileText}>
                  {(activeRun.artifacts || []).map((artifact) => (
                    <ArtifactItem key={artifact.id} artifact={artifact} />
                  ))}
                </RunColumn>
                <RunColumn title="Approvals" icon={CheckCircle2}>
                  {(activeRun.approvals || []).map((approval) => (
                    <TimelineItem
                      key={approval.id}
                      title={approval.title}
                      meta={approval.decision_reason || approval.approval_type}
                      status={approval.status}
                    />
                  ))}
                </RunColumn>
              </div>
            </div>
          )}
        </DashboardSection>
      </div>

      {selectedBlueprint ? (
        <DashboardSection
          title="Run history"
          description="Последние запуски выбранного workflow agent. Откройте run, чтобы увидеть steps, artifacts и approvals."
          actions={(
            <div className="flex flex-wrap gap-2">
              {runStatusFilters.map((filter) => (
                <Button
                  key={filter.value}
                  type="button"
                  size="sm"
                  variant={runStatusFilter === filter.value ? 'default' : 'outline'}
                  onClick={() => setRunStatusFilter(filter.value)}
                >
                  {filter.label}
                </Button>
              ))}
            </div>
          )}
        >
          {blueprintDetails?.runs?.length ? (
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {blueprintDetails.runs.map((run) => (
                <button
                  key={run.id}
                  type="button"
                  className={cn(
                    'rounded-xl border px-4 py-3 text-left transition',
                    activeRun?.id === run.id ? 'border-slate-900 bg-slate-950 text-white' : 'border-slate-200 bg-white hover:border-slate-300',
                  )}
                  onClick={() => void loadRun(run.id)}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex min-w-0 items-center gap-2">
                      <Workflow className="h-4 w-4 shrink-0" />
                      <span className="truncate text-sm font-semibold">Run {run.id.slice(0, 8)}</span>
                    </div>
                    <StatusBadge status={run.status} />
                  </div>
                  <div className={cn('mt-2 text-xs', activeRun?.id === run.id ? 'text-slate-300' : 'text-slate-500')}>
                    {run.started_at || 'started_at unavailable'}
                  </div>
                </button>
              ))}
            </div>
          ) : (
            <DashboardEmptyState
              title="История пуста"
              description="Запустите blueprint, чтобы здесь появились последние runs."
            />
          )}
        </DashboardSection>
      ) : null}

      {selectedBlueprint ? (
        <DashboardSection
          title="Approval queue"
          description="Все pending approvals по выбранному workflow agent, отдельно от истории запусков."
        >
          {pendingApprovals.length ? (
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {pendingApprovals.map((approval) => (
                <button
                  key={approval.id}
                  type="button"
                  className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-left transition hover:border-amber-300"
                  onClick={() => approval.run_id ? void loadRun(approval.run_id) : undefined}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="truncate text-sm font-semibold text-slate-950">{approval.title}</div>
                      <div className="mt-1 text-xs text-amber-700">
                        Run {approval.run_id ? approval.run_id.slice(0, 8) : 'unknown'} · {approval.approval_type}
                      </div>
                    </div>
                    <StatusBadge status={approval.status} />
                  </div>
                  <div className="mt-2 text-xs text-slate-500">{approval.requested_at || approval.run_status || 'pending'}</div>
                </button>
              ))}
            </div>
          ) : (
            <DashboardEmptyState
              title="Очередь approval пуста"
              description="Когда workflow agent остановится на ручном подтверждении, решение появится здесь."
            />
          )}
        </DashboardSection>
      ) : null}
    </div>
  );
};

const RunColumn = ({
  title,
  icon: Icon,
  children,
}: {
  title: string;
  icon: typeof Clock3;
  children: React.ReactNode;
}) => (
  <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
    <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-900">
      <Icon className="h-4 w-4" />
      {title}
    </div>
    <div className="space-y-2">
      {children || <div className="text-sm text-slate-500">Пока пусто</div>}
    </div>
  </div>
);

const TimelineItem = ({ title, meta, status }: { title: string; meta: string; status: string }) => (
  <div className="rounded-xl bg-white px-3 py-3 shadow-sm ring-1 ring-slate-200">
    <div className="flex items-start justify-between gap-3">
      <div className="min-w-0">
        <div className="truncate text-sm font-medium text-slate-900">{title}</div>
        <div className="mt-1 text-xs text-slate-500">{meta}</div>
      </div>
      <StatusBadge status={status} />
    </div>
  </div>
);

const ArtifactItem = ({ artifact }: { artifact: AgentArtifact }) => {
  const payload = artifact.payload_json || {};
  const items = Array.isArray(payload.items) ? payload.items : [];
  const preview = items.slice(0, 3);
  return (
    <div className="rounded-xl bg-white px-3 py-3 shadow-sm ring-1 ring-slate-200">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="truncate text-sm font-medium text-slate-900">{artifact.title}</div>
          <div className="mt-1 text-xs text-slate-500">
            {payload.source || artifact.artifact_type} · {payload.count ?? items.length} items
          </div>
        </div>
        <StatusBadge status={typeof payload.status === 'string' ? payload.status : 'completed'} />
      </div>
      {preview.length ? (
        <div className="mt-3 space-y-2">
          {preview.map((item, index) => (
            <div key={`${artifact.id}-${index}`} className="rounded-lg bg-slate-50 px-2 py-2 text-xs leading-5 text-slate-600">
              {String(item.name || item.lead_name || item.status || item.delivery_status || item.id || 'item')}
            </div>
          ))}
        </div>
      ) : null}
      <details className="mt-3">
        <summary className="cursor-pointer text-xs font-medium text-slate-500 hover:text-slate-900">
          Full payload
        </summary>
        <pre className="mt-2 max-h-72 overflow-auto rounded-lg bg-slate-950 p-3 text-[11px] leading-5 text-slate-100">
          {JSON.stringify(payload, null, 2)}
        </pre>
      </details>
    </div>
  );
};
