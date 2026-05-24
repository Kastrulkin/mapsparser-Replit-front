import type React from 'react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import {
  Bot,
  CheckCircle2,
  Clock3,
  FileCheck2,
  FileText,
  Loader2,
  Mail,
  Play,
  RefreshCw,
  Send,
  ShieldCheck,
  Sparkles,
  Star,
  Users,
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
import { AIAgentSettings } from '@/components/AIAgentSettings';
import { api } from '@/services/api';
import { cn } from '@/lib/utils';

type DashboardContext = {
  currentBusinessId: string | null;
  currentBusiness?: ({ id?: string; name?: string } & Record<string, unknown>) | null;
};

type DashboardMetricItem = {
  label: string;
  value: React.ReactNode;
  hint?: string;
  tone?: 'default' | 'positive' | 'warning';
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
    dispatch_state?: string;
    operator_note?: string;
    next_step?: string;
    source_artifact?: string;
    filters?: Record<string, unknown>;
    queue_count?: number;
    queued_count?: number;
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
    dispatch_state?: string;
    external_dispatch_performed?: boolean;
    queue_count?: number;
    orchestrator?: {
      result?: {
        status?: string;
        dispatch_state?: string;
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

type AgentDraftSummary = {
  category?: string;
  sources?: string[];
  outputs?: string[];
  approval_boundaries?: string[];
  steps?: Array<{
    key?: string;
    title?: string;
    type?: string;
  }>;
};

const runStatusFilters = [
  { value: 'all', label: 'Все' },
  { value: 'running', label: 'В работе' },
  { value: 'waiting_approval', label: 'Ждёт решения' },
  { value: 'completed', label: 'Готово' },
  { value: 'failed', label: 'Ошибка' },
];

const agentPromptExamples = [
  'Подготовь письмо клиентам по шаблону',
  'Обработай документ и найди риски',
  'Найди клиентов и покажи черновики сообщений',
  'Отвечай на отзывы в моём стиле',
];

const agentTemplates = [
  {
    title: 'Документы',
    description: 'Извлечь поля, проверить правила и собрать результат по образцу.',
    icon: FileText,
  },
  {
    title: 'Письма',
    description: 'Подготовить черновик, показать на подтверждение и сохранить результат.',
    icon: Mail,
  },
  {
    title: 'Таблицы',
    description: 'Разобрать строки, найти исключения и подготовить отчёт.',
    icon: FileCheck2,
  },
  {
    title: 'Поиск клиентов',
    description: 'Найти лидов, собрать shortlist и подготовить сообщения.',
    icon: Users,
  },
  {
    title: 'Отзывы',
    description: 'Подготовить ответы в стиле бизнеса и ждать ручного подтверждения.',
    icon: Star,
  },
  {
    title: 'Партнёрства',
    description: 'Найти подходящие компании и подготовить предложение.',
    icon: Sparkles,
  },
];

const statusTone: Record<string, string> = {
  active: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  completed: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  running: 'bg-sky-50 text-sky-700 ring-sky-200',
  waiting_approval: 'bg-amber-50 text-amber-700 ring-amber-200',
  failed: 'bg-rose-50 text-rose-700 ring-rose-200',
  rejected: 'bg-slate-100 text-slate-700 ring-slate-200',
  draft: 'bg-slate-100 text-slate-700 ring-slate-200',
  queued_for_dispatch: 'bg-amber-50 text-amber-700 ring-amber-200',
  pending: 'bg-amber-50 text-amber-700 ring-amber-200',
};

const statusLabels: Record<string, string> = {
  active: 'Включён',
  completed: 'Готово',
  running: 'В работе',
  waiting_approval: 'Ждёт решения',
  failed: 'Ошибка',
  rejected: 'Отклонён',
  draft: 'Черновик',
  queued_for_dispatch: 'В очереди',
  queued_not_dispatched: 'В очереди',
  generated: 'Подготовлено',
  approved: 'Подтверждено',
  pending: 'Ожидает',
};

const stepLabels: Record<string, string> = {
  source_leads: 'Найти потенциальных клиентов',
  shortlist: 'Сформировать список',
  approve_shortlist: 'Подтвердить список',
  draft_messages: 'Подготовить сообщения',
  approve_drafts: 'Подтвердить тексты',
  send_limited_batch: 'Поставить в очередь',
  record_outcomes: 'Сохранить ответы',
};

const metaLabels: Record<string, string> = {
  artifact: 'результат',
  approval: 'требуется подтверждение',
  capability: 'действие через безопасный контур',
  shortlist: 'список клиентов',
  drafts: 'черновики сообщений',
};

const humanizeStatus = (status: string) => statusLabels[status] || status;
const humanizeStep = (step: string) => stepLabels[step] || step;
const humanizeMeta = (meta: string) => metaLabels[meta] || meta;
const humanizeCategory = (category?: string) => ({
  outreach: 'Поиск клиентов',
  documents: 'Документы',
  email: 'Письма',
  tables: 'Таблицы',
  reviews: 'Отзывы',
  partnerships: 'Партнёрства',
  custom: 'Кастомная задача',
}[category || 'custom'] || category || 'Кастомная задача');

const StatusBadge = ({ status }: { status: string }) => (
  <span className={cn('inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ring-1', statusTone[status] || 'bg-slate-50 text-slate-600 ring-slate-200')}>
    {humanizeStatus(status)}
  </span>
);

const normalizeStringList = (value: unknown) => (
  Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : []
);

const normalizeDraftSteps = (value: unknown): AgentDraftSummary['steps'] => {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .filter((item): item is Record<string, unknown> => item !== null && typeof item === 'object')
    .map((item) => ({
      key: typeof item.key === 'string' ? item.key : undefined,
      title: typeof item.title === 'string' ? item.title : undefined,
      type: typeof item.type === 'string' ? item.type : undefined,
    }));
};

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
  const [runSource, setRunSource] = useState('dashboard');
  const [runCity, setRunCity] = useState('');
  const [runCategory, setRunCategory] = useState('');
  const [runLimit, setRunLimit] = useState('30');
  const [agentPrompt, setAgentPrompt] = useState('');
  const [lastDraft, setLastDraft] = useState<AgentDraftSummary | null>(null);

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
      return payload.dispatch_state === 'queued_not_dispatched' || (
        payload.status === 'queued_for_dispatch' && payload.external_dispatch_performed === false
      );
    });
    if (artifact?.payload_json) {
      return artifact.payload_json;
    }
    const step = (activeRun?.steps || []).find((item) => {
      const output = item.output_json?.orchestrator?.result || item.output_json || {};
      return output.dispatch_state === 'queued_not_dispatched' || (
        output.status === 'queued_for_dispatch' && output.external_dispatch_performed === false
      );
    });
    return step?.output_json?.orchestrator?.result || step?.output_json || null;
  }, [activeRun?.artifacts, activeRun?.steps]);

  const metrics = useMemo<DashboardMetricItem[]>(
    () => [
      {
        label: 'Мои агенты',
        value: blueprints.length,
        hint: currentBusiness?.name || 'Текущий бизнес',
      },
      {
        label: 'Активный запуск',
        value: activeRun ? <StatusBadge status={activeRun.status} /> : 'нет',
        hint: activeRun ? `Журнал ${activeRun.id.slice(0, 8)}` : 'Запустите агента',
        tone: activeRun?.status === 'waiting_approval' ? 'warning' : 'default',
      },
      {
        label: 'Результаты',
        value: activeRun?.artifacts?.length || 0,
        hint: 'Сохранённые находки, списки и черновики',
      },
      {
        label: 'Подтверждения',
        value: pendingApprovals.length || activeRun?.approvals?.length || 0,
        hint: pendingApprovals.length ? 'Есть ожидающие решения' : 'Нет ожидающих решений',
        tone: pendingApprovals.length || pendingApproval ? 'warning' : 'default',
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

  const createDefaultBlueprint = async (requestText = '') => {
    if (!currentBusinessId) {
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      const response = await api.post('/agent-blueprints', {
        business_id: currentBusinessId,
        name: requestText.trim() ? requestText.trim().slice(0, 80) : 'Агент поиска клиентов',
        category: 'outreach',
        description: requestText.trim() || 'Ищет лиды, готовит shortlist и черновики, внешние отправки только через approval.',
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

  const createAgentFromPrompt = async () => {
    if (!currentBusinessId || !agentPrompt.trim()) {
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      const response = await api.post('/agent-blueprints/draft', {
        business_id: currentBusinessId,
        description: agentPrompt.trim(),
      });
      const blueprint = response.data?.blueprint;
      const summary = response.data?.draft?.summary;
      if (summary && typeof summary === 'object') {
        setLastDraft({
          category: typeof summary.category === 'string' ? summary.category : undefined,
          sources: normalizeStringList(summary.sources),
          outputs: normalizeStringList(summary.outputs),
          approval_boundaries: normalizeStringList(summary.approval_boundaries),
          steps: normalizeDraftSteps(summary.steps),
        });
      } else {
        setLastDraft(null);
      }
      await loadBlueprints();
      if (blueprint?.id) {
        setSelectedBlueprintId(blueprint.id);
        await loadBlueprintDetails(blueprint.id);
      }
      setAgentPrompt('');
    } catch (requestError) {
      console.error(requestError);
      setError('Не удалось собрать черновик агента.');
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
          source: runSource.trim() || 'dashboard',
          city: runCity.trim(),
          category: runCategory.trim(),
          intent: 'client_outreach',
          business_id: currentBusinessId,
          limit: Number(runLimit) > 0 ? Math.min(Number(runLimit), 100) : 30,
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
        eyebrow="LocalOS"
        title="Агенты"
        description="Готовые помощники, пользовательские агенты, запуски и ручные подтверждения в одном разделе."
        icon={Bot}
        actions={(
          <>
            <Button type="button" variant="outline" onClick={loadBlueprints} disabled={loading || !currentBusinessId}>
              <RefreshCw className={cn('mr-2 h-4 w-4', loading && 'animate-spin')} />
              Обновить
            </Button>
            <Button type="button" onClick={() => createDefaultBlueprint()} disabled={actionLoading || !currentBusinessId}>
              {actionLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <ShieldCheck className="mr-2 h-4 w-4" />}
              Добавить агента поиска клиентов
            </Button>
          </>
        )}
      />

      <DashboardActionPanel
        title="Опишите, какого агента хотите создать"
        description="LocalOS сохранит задачу как повторяемый агент: входные данные, шаги, результаты и места, где нужен ручной контроль."
        tone="sky"
        status={(
          <div className="grid gap-3">
            <textarea
              className="min-h-28 w-full resize-none rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm leading-6 text-slate-900 outline-none transition focus:border-slate-400"
              value={agentPrompt}
              onChange={(event) => setAgentPrompt(event.target.value)}
              placeholder="Например: найди клиентов в моём городе, подготовь короткие сообщения и покажи мне перед отправкой"
            />
            <div className="flex flex-wrap gap-2">
              {agentPromptExamples.map((example) => (
                <button
                  key={example}
                  type="button"
                  className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 transition hover:border-slate-300 hover:text-slate-950"
                  onClick={() => setAgentPrompt(example)}
                >
                  {example}
                </button>
              ))}
            </div>
          </div>
        )}
        actions={(
          <Button type="button" onClick={createAgentFromPrompt} disabled={actionLoading || !currentBusinessId || !agentPrompt.trim()}>
            {actionLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Sparkles className="mr-2 h-4 w-4" />}
            Создать агента
          </Button>
        )}
      />

      {lastDraft ? <AgentDraftPreview draft={lastDraft} /> : null}

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
          description="Агенты всегда привязаны к конкретному бизнесу и его правам доступа."
        />
      ) : null}

      {currentBusinessId ? (
        <DashboardSection
          title="Готовые агенты и поведение"
          description="Агент для записи, маркетинговый агент и persona-настройки теперь находятся здесь, рядом с кастомными агентами."
          contentClassName="p-0"
        >
          <AIAgentSettings businessId={currentBusinessId} business={currentBusiness} />
        </DashboardSection>
      ) : null}

      <DashboardSection
        title="Шаблоны"
        description="Быстрые стартовые точки для агентов по документам, письмам, таблицам и поиску клиентов."
      >
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {agentTemplates.map((template) => {
            const Icon = template.icon;
            return (
              <button
                key={template.title}
                type="button"
                className="rounded-xl border border-slate-200 bg-white px-4 py-4 text-left transition hover:border-slate-300 hover:bg-slate-50"
                onClick={() => setAgentPrompt(`${template.title}: ${template.description}`)}
              >
                <div className="flex items-start gap-3">
                  <div className="rounded-lg bg-slate-100 p-2 text-slate-700">
                    <Icon className="h-4 w-4" />
                  </div>
                  <div>
                    <div className="text-sm font-semibold text-slate-950">{template.title}</div>
                    <div className="mt-1 text-sm leading-6 text-slate-600">{template.description}</div>
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      </DashboardSection>

      <div className="grid gap-6 xl:grid-cols-[minmax(20rem,0.9fr)_minmax(0,1.4fr)]">
        <DashboardSection title="Мои кастомные агенты" description="Сохранённые процессы, которые можно запускать повторно и контролировать через подтверждения.">
          {loading ? (
            <div className="flex items-center gap-2 text-sm text-slate-500">
              <Loader2 className="h-4 w-4 animate-spin" />
              Загружаем агентов...
            </div>
          ) : blueprints.length === 0 ? (
            <DashboardEmptyState
              title="Кастомных агентов пока нет"
              description="Опишите задачу сверху или добавьте агента поиска клиентов."
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
                          {blueprint.category || 'custom'} · версия {blueprint.latest_version_number || '—'}
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
          title="Запуск агента"
          description="Агент идёт по шагам, показывает результаты и останавливается там, где нужно ваше решение."
          actions={(
            <Button type="button" onClick={startRun} disabled={!selectedBlueprint || actionLoading}>
              {actionLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Play className="mr-2 h-4 w-4" />}
              Запустить
            </Button>
          )}
        >
          <div className="mb-4 grid gap-3 rounded-xl border border-slate-200 bg-slate-50/70 p-4 md:grid-cols-[1fr_1fr_1fr_8rem]">
            <label className="text-xs font-medium text-slate-600">
              Источник
              <input
                className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-slate-400"
                value={runSource}
                onChange={(event) => setRunSource(event.target.value)}
                placeholder="dashboard"
              />
            </label>
            <label className="text-xs font-medium text-slate-600">
              Город
              <input
                className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-slate-400"
                value={runCity}
                onChange={(event) => setRunCity(event.target.value)}
                placeholder="Москва"
              />
            </label>
            <label className="text-xs font-medium text-slate-600">
              Категория
              <input
                className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-slate-400"
                value={runCategory}
                onChange={(event) => setRunCategory(event.target.value)}
                placeholder="beauty"
              />
            </label>
            <label className="text-xs font-medium text-slate-600">
              Лимит
              <input
                className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-slate-400"
                inputMode="numeric"
                value={runLimit}
                onChange={(event) => setRunLimit(event.target.value)}
              />
            </label>
          </div>
          {!activeRun ? (
              <DashboardEmptyState
                title="Запусков в этой сессии нет"
                description="Выберите агента и запустите его или откройте один из последних запусков."
              />
          ) : (
            <div className="space-y-5">
              <DashboardActionPanel
                title="Текущий запуск"
                description={activeRun.error_text || 'Что агент уже сделал, какие результаты подготовил и где ждёт подтверждение.'}
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
                  title="Поставлено в очередь, но не отправлено"
                  description={`${queuedButNotDispatched.operator_note || 'Агент подготовил очередь, но внешняя отправка запускается отдельным контуром.'} В очереди: ${Number(queuedButNotDispatched.queue_count || queuedButNotDispatched.queued_count || 0)}.`}
                  status={<StatusBadge status="queued_for_dispatch" />}
                  tone="amber"
                  actions={<Send className="h-4 w-4 text-amber-600" />}
                />
              ) : null}

              <div className="grid gap-4 lg:grid-cols-3">
                <RunColumn title="Шаги" icon={Clock3}>
                  {(activeRun.steps || []).map((step) => (
                    <TimelineItem
                      key={step.id}
                      title={humanizeStep(step.step_key)}
                      meta={humanizeMeta(step.error_text || step.step_type)}
                      status={step.status}
                    />
                  ))}
                </RunColumn>
                <RunColumn title="Результаты" icon={FileText}>
                  {(activeRun.artifacts || []).map((artifact) => (
                    <ArtifactItem key={artifact.id} artifact={artifact} />
                  ))}
                </RunColumn>
                <RunColumn title="Подтверждения" icon={CheckCircle2}>
                  {(activeRun.approvals || []).map((approval) => (
                    <TimelineItem
                      key={approval.id}
                      title={approval.title}
                      meta={approval.decision_reason || humanizeMeta(approval.approval_type)}
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
          title="История запусков"
          description="Последние запуски выбранного агента. Откройте запуск, чтобы увидеть шаги, результаты и подтверждения."
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
                      <span className="truncate text-sm font-semibold">Запуск {run.id.slice(0, 8)}</span>
                    </div>
                    <StatusBadge status={run.status} />
                  </div>
                  <div className={cn('mt-2 text-xs', activeRun?.id === run.id ? 'text-slate-300' : 'text-slate-500')}>
                    {run.started_at || 'Дата запуска недоступна'}
                  </div>
                </button>
              ))}
            </div>
          ) : (
            <DashboardEmptyState
              title="История пуста"
              description="Запустите агента, чтобы здесь появилась история."
            />
          )}
        </DashboardSection>
      ) : null}

      {selectedBlueprint ? (
        <DashboardSection
          title="Ожидают подтверждения"
          description="Решения, без которых агент не продолжит рискованное действие."
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
                        Запуск {approval.run_id ? approval.run_id.slice(0, 8) : 'неизвестен'} · {humanizeMeta(approval.approval_type)}
                      </div>
                    </div>
                    <StatusBadge status={approval.status} />
                  </div>
                  <div className="mt-2 text-xs text-slate-500">{approval.requested_at || humanizeStatus(approval.run_status || 'pending')}</div>
                  <ApprovalPayloadSummary approval={approval} />
                </button>
              ))}
            </div>
          ) : (
            <DashboardEmptyState
              title="Очередь approval пуста"
              description="Когда агент остановится на ручном подтверждении, решение появится здесь."
            />
          )}
        </DashboardSection>
      ) : null}
    </div>
  );
};

const AgentDraftPreview = ({ draft }: { draft: AgentDraftSummary }) => (
  <DashboardSection
    title="Черновик агента создан"
    description={`Тип: ${humanizeCategory(draft.category)}. Проверьте шаги и запустите агента, когда будете готовы.`}
    actions={<StatusBadge status="draft" />}
    className="border-emerald-200/80 bg-emerald-50/70"
  >
    <div className="grid gap-3 md:grid-cols-3">
      <DraftPreviewBlock title="Данные" items={draft.sources || []} empty="Нужно будет добавить контекст" />
      <DraftPreviewBlock title="Результат" items={draft.outputs || []} empty="Результат задаётся в настройках" />
      <DraftPreviewBlock title="Ручной контроль" items={draft.approval_boundaries || []} empty="Безопасные действия без отправки" />
    </div>
    {draft.steps?.length ? (
      <div className="mt-4 grid gap-2 md:grid-cols-2 xl:grid-cols-3">
        {draft.steps.map((step, index) => (
          <div key={`${step.key || step.title || 'step'}-${index}`} className="rounded-xl bg-white px-3 py-3 text-sm ring-1 ring-emerald-100">
            <div className="font-medium text-slate-950">{step.title || humanizeStep(step.key || 'step')}</div>
            <div className="mt-1 text-xs text-slate-500">{humanizeMeta(step.type || 'artifact')}</div>
          </div>
        ))}
      </div>
    ) : null}
  </DashboardSection>
);

const DraftPreviewBlock = ({ title, items, empty }: { title: string; items: string[]; empty: string }) => (
  <div className="rounded-xl bg-white px-3 py-3 ring-1 ring-emerald-100">
    <div className="text-xs font-semibold uppercase tracking-wide text-emerald-700">{title}</div>
    <div className="mt-2 flex flex-wrap gap-1.5">
      {items.length ? items.map((item) => (
        <span key={item} className="rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-800 ring-1 ring-emerald-100">
          {humanizeMeta(item)}
        </span>
      )) : (
        <span className="text-sm text-slate-500">{empty}</span>
      )}
    </div>
  </div>
);

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

const compactValue = (value: unknown) => {
  if (Array.isArray(value)) {
    return value.length ? value.join(', ') : 'any';
  }
  if (typeof value === 'number') {
    return String(value);
  }
  if (typeof value === 'string' && value.trim()) {
    return value.trim();
  }
  return 'any';
};

const ArtifactSourceSummary = ({ payload }: { payload: AgentArtifact['payload_json'] }) => {
  const filters = payload?.filters || {};
  const filterEntries = Object.entries(filters).filter(([, value]) => {
    if (Array.isArray(value)) {
      return value.length > 0;
    }
    return value !== '' && value !== null && value !== undefined;
  });
  if (payload?.source !== 'prospectingleads' && !payload?.source_artifact && filterEntries.length === 0) {
    return null;
  }
  return (
    <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs leading-5 text-slate-600">
      {payload?.source === 'prospectingleads' ? (
        <div className="font-medium text-slate-800">Источник лидов: prospectingleads</div>
      ) : null}
      {payload?.source_artifact ? (
        <div>Сформировано из: {payload.source_artifact}</div>
      ) : null}
      {filterEntries.length ? (
        <div className="mt-1 flex flex-wrap gap-1.5">
          {filterEntries.map(([key, value]) => (
            <span key={key} className="rounded-md bg-white px-2 py-1 ring-1 ring-slate-200">
              {key}: {compactValue(value)}
            </span>
          ))}
        </div>
      ) : null}
    </div>
  );
};

const ApprovalPayloadSummary = ({ approval }: { approval: AgentApproval }) => {
  const payload = approval.payload_json || {};
  const count = typeof payload.count === 'number' ? payload.count : null;
  const artifactType = typeof payload.artifact_type === 'string' ? payload.artifact_type : '';
  if (!artifactType && count === null) {
    return null;
  }
  return (
    <div className="mt-3 rounded-lg bg-white/80 px-3 py-2 text-xs leading-5 text-slate-600 ring-1 ring-amber-100">
      {artifactType ? <div>Результат: {artifactType}</div> : null}
      {count !== null ? <div>Ожидают решения: {count}</div> : null}
    </div>
  );
};

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
      <ArtifactSourceSummary payload={payload} />
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
          Технический журнал
        </summary>
        <pre className="mt-2 max-h-72 overflow-auto rounded-lg bg-slate-950 p-3 text-[11px] leading-5 text-slate-100">
          {JSON.stringify(payload, null, 2)}
        </pre>
      </details>
    </div>
  );
};
