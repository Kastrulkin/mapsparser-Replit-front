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
  ShieldCheck,
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
  status: string;
  approval_type: string;
  title: string;
};

type AgentArtifact = {
  id: string;
  artifact_type: string;
  title: string;
};

type AgentRunStep = {
  id: string;
  step_key: string;
  step_type: string;
  status: string;
};

type AgentRun = {
  id: string;
  status: string;
  blueprint_id: string;
  steps?: AgentRunStep[];
  artifacts?: AgentArtifact[];
  approvals?: AgentApproval[];
  error_text?: string | null;
};

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
  const [activeRun, setActiveRun] = useState<AgentRun | null>(null);
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedBlueprint = useMemo(
    () => blueprints.find((item) => item.id === selectedBlueprintId) || blueprints[0] || null,
    [blueprints, selectedBlueprintId],
  );

  const pendingApproval = useMemo(
    () => activeRun?.approvals?.find((item) => item.status === 'pending') || null,
    [activeRun],
  );

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
        value: activeRun?.approvals?.length || 0,
        hint: pendingApproval ? 'Есть ожидающее подтверждение' : 'Нет ожидающих решений',
        tone: pendingApproval ? 'warning' as const : 'default' as const,
      },
    ],
    [activeRun, blueprints.length, currentBusiness?.name, pendingApproval],
  );

  const loadBlueprints = useCallback(async () => {
    if (!currentBusinessId) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const response = await api.get('/api/agent-blueprints', { params: { business_id: currentBusinessId } });
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

  const createDefaultBlueprint = async () => {
    if (!currentBusinessId) {
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      const response = await api.post('/api/agent-blueprints', {
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
      const response = await api.post(`/api/agent-blueprints/${selectedBlueprint.id}/runs`, {
        input: {
          source: 'dashboard',
          business_id: currentBusinessId,
          limit: 30,
        },
      });
      setActiveRun(response.data?.run || null);
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
      const response = await api.post(`/api/agent-runs/${activeRun.id}/approvals/${pendingApproval.id}/${decision}`, {
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
                    onClick={() => setSelectedBlueprintId(blueprint.id)}
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
          description="Запуск идет последовательно и останавливается на ручном подтверждении."
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
              description="Выберите blueprint и запустите его. Первый outreach run дойдет до approval shortlist и остановится."
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

              <div className="grid gap-4 lg:grid-cols-3">
                <RunColumn title="Steps" icon={Clock3}>
                  {(activeRun.steps || []).map((step) => (
                    <TimelineItem key={step.id} title={step.step_key} meta={step.step_type} status={step.status} />
                  ))}
                </RunColumn>
                <RunColumn title="Artifacts" icon={FileText}>
                  {(activeRun.artifacts || []).map((artifact) => (
                    <TimelineItem key={artifact.id} title={artifact.title} meta={artifact.artifact_type} status="completed" />
                  ))}
                </RunColumn>
                <RunColumn title="Approvals" icon={CheckCircle2}>
                  {(activeRun.approvals || []).map((approval) => (
                    <TimelineItem key={approval.id} title={approval.title} meta={approval.approval_type} status={approval.status} />
                  ))}
                </RunColumn>
              </div>
            </div>
          )}
        </DashboardSection>
      </div>
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
