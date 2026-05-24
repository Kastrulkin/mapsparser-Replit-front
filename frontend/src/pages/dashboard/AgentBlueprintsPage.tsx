import type React from 'react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import {
  Bot,
  CheckCircle2,
  Clock3,
  Database,
  FileCheck2,
  FileText,
  Loader2,
  Mail,
  MessageSquareText,
  Play,
  RefreshCw,
  Send,
  ShieldCheck,
  Sparkles,
  Star,
  Upload,
  Users,
  Wrench,
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

type AgentSource = {
  id?: string;
  source_type?: string;
  name?: string;
  file_name?: string;
  internal_source?: string;
  extraction_state?: string;
  content_length?: number;
};

type AgentReviewSection = {
  title?: string;
  artifact_type?: string;
  status?: string;
  summary?: string;
  payload?: Record<string, unknown>;
};

type AgentReview = {
  has_run?: boolean;
  run_id?: string;
  run_status?: string;
  setup?: Record<string, unknown>;
  sources?: AgentSource[];
  sections?: AgentReviewSection[];
  approvals?: AgentApproval[];
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

type AgentBuilderScenario = {
  category: string;
  title: string;
  description: string;
  prompt: string;
  dataSources: string;
  extraction: string;
  processing: string;
  output: string;
  manualControl: string;
  icon: typeof FileText;
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

const agentScenarios: AgentBuilderScenario[] = [
  {
    category: 'documents',
    title: 'Документы',
    description: 'Извлечь поля, проверить правила и собрать результат по образцу.',
    prompt: 'Обработай документ, найди риски и подготовь краткий результат для проверки',
    dataSources: 'файл документа, ручной контекст, профиль бизнеса',
    extraction: 'ключевые условия, сроки, суммы, ответственность, спорные места',
    processing: 'не придумывать факты, ссылаться только на добавленный документ, отдельно показывать риски',
    output: 'краткий отчёт: summary, риски, что уточнить, черновик письма при необходимости',
    manualControl: 'перед использованием результата и перед любым внешним действием',
    icon: FileText,
  },
  {
    category: 'email',
    title: 'Письма',
    description: 'Подготовить черновик, показать на подтверждение и сохранить результат.',
    prompt: 'Подготовь письмо клиенту по моему контексту и шаблону',
    dataSources: 'ручной контекст, шаблон письма, профиль бизнеса',
    extraction: 'цель письма, адресат, факты, ограничения по тону',
    processing: 'писать коротко, без неподтверждённых обещаний, сохранять стиль бизнеса',
    output: 'тема письма и готовый черновик',
    manualControl: 'письмо только как черновик, отправка вручную после проверки',
    icon: Mail,
  },
  {
    category: 'tables',
    title: 'Таблицы',
    description: 'Разобрать строки, найти исключения и подготовить отчёт.',
    prompt: 'Разбери таблицу, найди исключения и собери отчёт',
    dataSources: 'CSV/XLSX, ручной контекст',
    extraction: 'строки, пустые поля, аномалии, суммы и статусы',
    processing: 'показывать только проверяемые исключения, группировать по причине',
    output: 'отчёт по исключениям и список строк для проверки',
    manualControl: 'перед изменением данных или отправкой отчёта',
    icon: FileCheck2,
  },
  {
    category: 'outreach',
    title: 'Поиск клиентов',
    description: 'Найти лидов, собрать shortlist и подготовить сообщения.',
    prompt: 'Найди клиентов и покажи черновики сообщений перед отправкой',
    dataSources: 'prospectingleads, профиль бизнеса, услуги',
    extraction: 'подходящие лиды, канал связи, причина релевантности',
    processing: 'не отправлять без approval, ограничить объём, сохранять источник лида',
    output: 'shortlist и черновики сообщений',
    manualControl: 'shortlist, черновики и очередь отправки подтверждаются вручную',
    icon: Users,
  },
  {
    category: 'reviews',
    title: 'Отзывы',
    description: 'Подготовить ответы в стиле бизнеса и ждать ручного подтверждения.',
    prompt: 'Подготовь ответы на отзывы в стиле моего бизнеса',
    dataSources: 'отзывы, профиль бизнеса, услуги',
    extraction: 'тон отзыва, проблема, услуга, факты для ответа',
    processing: 'не спорить, не обещать невозможное, негативные отзывы помечать отдельно',
    output: 'черновики ответов на отзывы',
    manualControl: 'публикация только вручную после проверки',
    icon: Star,
  },
  {
    category: 'partnerships',
    title: 'Партнёрства',
    description: 'Найти подходящие компании и подготовить предложение.',
    prompt: 'Подготовь партнёрское предложение для локальных компаний',
    dataSources: 'prospectingleads, услуги, профиль бизнеса',
    extraction: 'тип партнёра, пересечение аудитории, повод для предложения',
    processing: 'не отправлять наружу, сначала показать предложение',
    output: 'короткое партнёрское предложение и список адресатов',
    manualControl: 'перед отправкой и публикацией',
    icon: Sparkles,
  },
  {
    category: 'services',
    title: 'Услуги',
    description: 'Понять текущие услуги и предложить улучшения без автоприменения.',
    prompt: 'Оптимизируй описание услуг и покажи предложения перед применением',
    dataSources: 'услуги, профиль бизнеса, отзывы',
    extraction: 'названия услуг, цены, длительность, слабые описания',
    processing: 'не менять услуги без отдельного подтверждения',
    output: 'предложения по улучшению услуг',
    manualControl: 'применение изменений только вручную',
    icon: Wrench,
  },
  {
    category: 'booking',
    title: 'Бронирование',
    description: 'Собрать правила записи и подготовить сценарий общения.',
    prompt: 'Помоги настроить агента записи: вопросы клиенту, правила и ограничения',
    dataSources: 'профиль бизнеса, услуги, ручной контекст',
    extraction: 'правила записи, ограничения, обязательные вопросы, доступные услуги',
    processing: 'не подтверждать запись без понятных правил и ручного контроля',
    output: 'сценарий записи и список недостающих правил',
    manualControl: 'сложные случаи и изменения расписания подтверждаются человеком',
    icon: MessageSquareText,
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
  business_profile: 'профиль бизнеса',
  services: 'услуги',
  reviews: 'отзывы',
  external_reviews: 'отзывы',
  prospectingleads: 'лиды',
  outreach_drafts: 'черновики outreach',
  uploaded_documents: 'документы',
  uploaded_tables: 'таблицы',
  manual_context: 'ручной контекст',
  final_output: 'финальный результат',
  external_delivery: 'внешняя отправка',
  title: 'название',
  summary: 'кратко',
  risks: 'риски',
  subject: 'тема',
  body: 'текст',
  format: 'формат',
  source_name: 'источник',
  raw: 'данные',
  missing_information: 'что уточнить',
  result: 'результат',
  rules_applied: 'правила',
  feedback_notes: 'правки',
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
  const [builderCategory, setBuilderCategory] = useState('documents');
  const [builderDataSources, setBuilderDataSources] = useState('файл документа, ручной контекст, профиль бизнеса');
  const [builderExtractionRules, setBuilderExtractionRules] = useState('ключевые условия, сроки, суммы, ответственность, спорные места');
  const [builderProcessingRules, setBuilderProcessingRules] = useState('не придумывать факты, ссылаться только на добавленные данные, отдельно показывать риски');
  const [builderOutputFormat, setBuilderOutputFormat] = useState('краткий отчёт: summary, риски, что уточнить, черновик письма при необходимости');
  const [builderManualControl, setBuilderManualControl] = useState('перед использованием результата и перед любым внешним действием');
  const [builderSourceName, setBuilderSourceName] = useState('');
  const [builderSourceText, setBuilderSourceText] = useState('');
  const [builderFileSource, setBuilderFileSource] = useState<{ name: string; content: string } | null>(null);
  const [builderInternalSource, setBuilderInternalSource] = useState('business_profile');
  const [lastDraft, setLastDraft] = useState<AgentDraftSummary | null>(null);
  const [agentReview, setAgentReview] = useState<AgentReview | null>(null);
  const [setupDataSources, setSetupDataSources] = useState('профиль бизнеса, ручной контекст');
  const [setupExtractionRules, setSetupExtractionRules] = useState('');
  const [setupProcessingRules, setSetupProcessingRules] = useState('');
  const [setupOutputFormat, setSetupOutputFormat] = useState('');
  const [setupManualControl, setSetupManualControl] = useState('Показывать результат перед любым внешним действием');
  const [sourceName, setSourceName] = useState('');
  const [sourceText, setSourceText] = useState('');
  const [internalSource, setInternalSource] = useState('business_profile');
  const [feedbackText, setFeedbackText] = useState('');

  const selectedBlueprint = useMemo(
    () => blueprints.find((item) => item.id === selectedBlueprintId) || blueprints[0] || null,
    [blueprints, selectedBlueprintId],
  );

  const pendingApproval = useMemo(
    () => activeRun?.approvals?.find((item) => item.status === 'pending') || null,
    [activeRun],
  );

  const activeRunPendingApprovals = useMemo(
    () => (activeRun?.approvals || []).filter((item) => item.status === 'pending'),
    [activeRun?.approvals],
  );

  const pendingApprovals = useMemo(
    () => (blueprintDetails?.approval_queue || []).filter((item) => item.status === 'pending'),
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

  const selectedScenario = useMemo(
    () => agentScenarios.find((item) => item.category === builderCategory) || agentScenarios[0],
    [builderCategory],
  );

  const applyBuilderScenario = (scenario: AgentBuilderScenario) => {
    setBuilderCategory(scenario.category);
    setAgentPrompt(scenario.prompt);
    setBuilderDataSources(scenario.dataSources);
    setBuilderExtractionRules(scenario.extraction);
    setBuilderProcessingRules(scenario.processing);
    setBuilderOutputFormat(scenario.output);
    setBuilderManualControl(scenario.manualControl);
  };

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
        value: pendingApprovals.length || activeRunPendingApprovals.length,
        hint: pendingApprovals.length ? 'Есть ожидающие решения' : 'Нет ожидающих решений',
        tone: pendingApprovals.length || pendingApproval ? 'warning' : 'default',
      },
    ],
    [activeRun, activeRunPendingApprovals.length, blueprints.length, currentBusiness?.name, pendingApproval, pendingApprovals.length],
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
      if (selectedBlueprint?.id) {
        await loadBlueprintDetails(selectedBlueprint.id);
        await loadBlueprintReview(selectedBlueprint.id);
      }
    } catch (requestError) {
      console.error(requestError);
      setError('Не удалось загрузить запуск.');
    } finally {
      setActionLoading(false);
    }
  };

  const loadBlueprintReview = useCallback(async (blueprintId: string) => {
    try {
      const response = await api.get(`/agent-blueprints/${blueprintId}/review`);
      setAgentReview(response.data?.review || null);
    } catch (requestError) {
      console.error(requestError);
    }
  }, []);

  useEffect(() => {
    if (selectedBlueprint?.id) {
      void loadBlueprintReview(selectedBlueprint.id);
    } else {
      setAgentReview(null);
    }
  }, [loadBlueprintReview, selectedBlueprint?.id]);

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
        await loadBlueprintReview(blueprint.id);
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
        category: builderCategory,
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
        await api.post(`/agent-blueprints/${blueprint.id}/setup`, {
          workflow_description: agentPrompt.trim(),
          data_sources: builderDataSources.split(',').map((item) => item.trim()).filter(Boolean),
          extraction_rules: builderExtractionRules,
          processing_rules: builderProcessingRules,
          output_format: builderOutputFormat,
          approval_boundaries: ['final_output', 'external_delivery'],
          manual_control: builderManualControl,
        });
        if (builderSourceText.trim()) {
          await api.post(`/agent-blueprints/${blueprint.id}/sources`, {
            source_type: 'text',
            name: builderSourceName.trim() || 'Контекст для агента',
            content_text: builderSourceText,
          });
        }
        if (builderFileSource) {
          await api.post(`/agent-blueprints/${blueprint.id}/sources`, {
            source_type: 'file',
            name: builderFileSource.name,
            file_name: builderFileSource.name,
            content_text: builderFileSource.content,
          });
        }
        if (builderInternalSource !== 'none') {
          await api.post(`/agent-blueprints/${blueprint.id}/sources`, {
            source_type: 'internal',
            name: humanizeMeta(builderInternalSource),
            internal_source: builderInternalSource,
          });
        }
        setSelectedBlueprintId(blueprint.id);
        await loadBlueprintDetails(blueprint.id);
        await loadBlueprintReview(blueprint.id);
      }
      setAgentPrompt('');
      setBuilderSourceName('');
      setBuilderSourceText('');
      setBuilderFileSource(null);
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
      await loadBlueprintReview(selectedBlueprint.id);
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
      if (selectedBlueprint?.id) {
        await loadBlueprintDetails(selectedBlueprint.id);
        await loadBlueprintReview(selectedBlueprint.id);
      }
    } catch (requestError) {
      console.error(requestError);
      setError('Не удалось применить решение approval.');
    } finally {
      setActionLoading(false);
    }
  };

  const saveAgentSetup = async () => {
    if (!selectedBlueprint) {
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      await api.post(`/agent-blueprints/${selectedBlueprint.id}/setup`, {
        workflow_description: selectedBlueprint.latest_goal || selectedBlueprint.description || selectedBlueprint.name,
        data_sources: setupDataSources.split(',').map((item) => item.trim()).filter(Boolean),
        extraction_rules: setupExtractionRules,
        processing_rules: setupProcessingRules,
        output_format: setupOutputFormat,
        approval_boundaries: ['final_output', 'external_delivery'],
        manual_control: setupManualControl,
      });
      await loadBlueprintDetails(selectedBlueprint.id);
      await loadBlueprintReview(selectedBlueprint.id);
    } catch (requestError) {
      console.error(requestError);
      setError('Не удалось сохранить настройку агента.');
    } finally {
      setActionLoading(false);
    }
  };

  const addTextSource = async () => {
    if (!selectedBlueprint || !sourceText.trim()) {
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      await api.post(`/agent-blueprints/${selectedBlueprint.id}/sources`, {
        source_type: 'text',
        name: sourceName.trim() || 'Ручной контекст',
        content_text: sourceText,
      });
      setSourceName('');
      setSourceText('');
      await loadBlueprintReview(selectedBlueprint.id);
    } catch (requestError) {
      console.error(requestError);
      setError('Не удалось добавить источник данных.');
    } finally {
      setActionLoading(false);
    }
  };

  const addInternalSource = async () => {
    if (!selectedBlueprint) {
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      await api.post(`/agent-blueprints/${selectedBlueprint.id}/sources`, {
        source_type: 'internal',
        name: humanizeMeta(internalSource),
        internal_source: internalSource,
      });
      await loadBlueprintReview(selectedBlueprint.id);
    } catch (requestError) {
      console.error(requestError);
      setError('Не удалось подключить источник LocalOS.');
    } finally {
      setActionLoading(false);
    }
  };

  const addFileSource = async (file?: File | null) => {
    if (!selectedBlueprint || !file) {
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      let contentText = '';
      try {
        contentText = await file.text();
      } catch (readError) {
        console.error(readError);
      }
      await api.post(`/agent-blueprints/${selectedBlueprint.id}/sources`, {
        source_type: 'file',
        name: file.name,
        file_name: file.name,
        content_text: contentText,
      });
      await loadBlueprintReview(selectedBlueprint.id);
    } catch (requestError) {
      console.error(requestError);
      setError('Не удалось добавить файл.');
    } finally {
      setActionLoading(false);
    }
  };

  const sendRunFeedback = async () => {
    if (!activeRun || !feedbackText.trim()) {
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      await api.post(`/agent-runs/${activeRun.id}/feedback`, { feedback: feedbackText });
      setFeedbackText('');
      if (selectedBlueprint?.id) {
        await loadBlueprintDetails(selectedBlueprint.id);
        await loadBlueprintReview(selectedBlueprint.id);
      }
    } catch (requestError) {
      console.error(requestError);
      setError('Не удалось сохранить правку агента.');
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

      <AgentBuilderPanel
        prompt={agentPrompt}
        selectedScenario={selectedScenario}
        scenarios={agentScenarios}
        examples={agentPromptExamples}
        dataSources={builderDataSources}
        extractionRules={builderExtractionRules}
        processingRules={builderProcessingRules}
        outputFormat={builderOutputFormat}
        manualControl={builderManualControl}
        sourceName={builderSourceName}
        sourceText={builderSourceText}
        fileSource={builderFileSource}
        internalSource={builderInternalSource}
        actionLoading={actionLoading}
        canCreate={Boolean(currentBusinessId && agentPrompt.trim())}
        onScenarioSelect={applyBuilderScenario}
        onPromptChange={setAgentPrompt}
        onDataSourcesChange={setBuilderDataSources}
        onExtractionRulesChange={setBuilderExtractionRules}
        onProcessingRulesChange={setBuilderProcessingRules}
        onOutputFormatChange={setBuilderOutputFormat}
        onManualControlChange={setBuilderManualControl}
        onSourceNameChange={setBuilderSourceName}
        onSourceTextChange={setBuilderSourceText}
        onFileSourceChange={setBuilderFileSource}
        onInternalSourceChange={setBuilderInternalSource}
        onCreate={createAgentFromPrompt}
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
          {agentScenarios.map((template) => {
            const Icon = template.icon;
            return (
              <button
                key={template.title}
                type="button"
                className="rounded-xl border border-slate-200 bg-white px-4 py-4 text-left transition hover:border-slate-300 hover:bg-slate-50"
                onClick={() => applyBuilderScenario(template)}
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

      {selectedBlueprint ? (
        <AgentWorkspacePanel
          setupDataSources={setupDataSources}
          setupExtractionRules={setupExtractionRules}
          setupProcessingRules={setupProcessingRules}
          setupOutputFormat={setupOutputFormat}
          setupManualControl={setupManualControl}
          sourceName={sourceName}
          sourceText={sourceText}
          internalSource={internalSource}
          review={agentReview}
          actionLoading={actionLoading}
          onSetupDataSourcesChange={setSetupDataSources}
          onSetupExtractionRulesChange={setSetupExtractionRules}
          onSetupProcessingRulesChange={setSetupProcessingRules}
          onSetupOutputFormatChange={setSetupOutputFormat}
          onSetupManualControlChange={setSetupManualControl}
          onSourceNameChange={setSourceName}
          onSourceTextChange={setSourceText}
          onInternalSourceChange={setInternalSource}
          onSaveSetup={saveAgentSetup}
          onAddTextSource={addTextSource}
          onAddInternalSource={addInternalSource}
          onAddFileSource={addFileSource}
        />
      ) : null}

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
              <AgentRunReviewPanel
                review={agentReview}
                feedbackText={feedbackText}
                actionLoading={actionLoading}
                onFeedbackTextChange={setFeedbackText}
                onSubmitFeedback={sendRunFeedback}
              />
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

const AgentBuilderPanel = ({
  prompt,
  selectedScenario,
  scenarios,
  examples,
  dataSources,
  extractionRules,
  processingRules,
  outputFormat,
  manualControl,
  sourceName,
  sourceText,
  fileSource,
  internalSource,
  actionLoading,
  canCreate,
  onScenarioSelect,
  onPromptChange,
  onDataSourcesChange,
  onExtractionRulesChange,
  onProcessingRulesChange,
  onOutputFormatChange,
  onManualControlChange,
  onSourceNameChange,
  onSourceTextChange,
  onFileSourceChange,
  onInternalSourceChange,
  onCreate,
}: {
  prompt: string;
  selectedScenario: AgentBuilderScenario;
  scenarios: AgentBuilderScenario[];
  examples: string[];
  dataSources: string;
  extractionRules: string;
  processingRules: string;
  outputFormat: string;
  manualControl: string;
  sourceName: string;
  sourceText: string;
  fileSource: { name: string; content: string } | null;
  internalSource: string;
  actionLoading: boolean;
  canCreate: boolean;
  onScenarioSelect: (scenario: AgentBuilderScenario) => void;
  onPromptChange: (value: string) => void;
  onDataSourcesChange: (value: string) => void;
  onExtractionRulesChange: (value: string) => void;
  onProcessingRulesChange: (value: string) => void;
  onOutputFormatChange: (value: string) => void;
  onManualControlChange: (value: string) => void;
  onSourceNameChange: (value: string) => void;
  onSourceTextChange: (value: string) => void;
  onFileSourceChange: (value: { name: string; content: string } | null) => void;
  onInternalSourceChange: (value: string) => void;
  onCreate: () => void;
}) => {
  const handleBuilderFile = async (file?: File | null) => {
    if (!file) {
      onFileSourceChange(null);
      return;
    }
    let content = '';
    try {
      content = await file.text();
    } catch (readError) {
      console.error(readError);
    }
    onFileSourceChange({ name: file.name, content });
  };

  return (
    <DashboardSection
      title="Создать агента"
      description="Опишите задачу обычным языком, выберите тип, добавьте данные и правила. LocalOS соберёт reusable agent без внешних действий по умолчанию."
      actions={(
        <Button type="button" onClick={onCreate} disabled={actionLoading || !canCreate}>
          {actionLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Sparkles className="mr-2 h-4 w-4" />}
          Создать агента
        </Button>
      )}
    >
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.2fr)_minmax(21rem,0.8fr)]">
        <div className="space-y-4">
          <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-4">
            {scenarios.map((scenario) => {
              const Icon = scenario.icon;
              const selected = scenario.category === selectedScenario.category;
              return (
                <button
                  key={scenario.category}
                  type="button"
                  className={cn(
                    'rounded-xl border px-3 py-3 text-left transition',
                    selected ? 'border-slate-900 bg-slate-950 text-white' : 'border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50',
                  )}
                  onClick={() => onScenarioSelect(scenario)}
                >
                  <div className="flex items-center gap-2">
                    <Icon className="h-4 w-4 shrink-0" />
                    <span className="text-sm font-semibold">{scenario.title}</span>
                  </div>
                  <div className={cn('mt-1 line-clamp-2 text-xs leading-5', selected ? 'text-slate-300' : 'text-slate-500')}>
                    {scenario.description}
                  </div>
                </button>
              );
            })}
          </div>

          <textarea
            className="min-h-32 w-full resize-none rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm leading-6 text-slate-900 outline-none transition focus:border-slate-400"
            value={prompt}
            onChange={(event) => onPromptChange(event.target.value)}
            placeholder="Например: обработай договор, найди риски и подготовь письмо клиенту"
          />
          <div className="flex flex-wrap gap-2">
            {examples.map((example) => (
              <button
                key={example}
                type="button"
                className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 transition hover:border-slate-300 hover:text-slate-950"
                onClick={() => onPromptChange(example)}
              >
                {example}
              </button>
            ))}
          </div>

          <div className="grid gap-3 md:grid-cols-2">
            <WizardTextArea label="Какие данные использовать" value={dataSources} onChange={onDataSourcesChange} placeholder="Файл, текст, профиль бизнеса, услуги, отзывы" />
            <WizardTextArea label="Что агент должен извлечь или понять" value={extractionRules} onChange={onExtractionRulesChange} placeholder="Поля, риски, сроки, исключения, факты" />
            <WizardTextArea label="Какие правила применить" value={processingRules} onChange={onProcessingRulesChange} placeholder="Не придумывать факты, учитывать стиль, помечать спорное" />
            <WizardTextArea label="Какой результат подготовить" value={outputFormat} onChange={onOutputFormatChange} placeholder="Отчёт, письмо, таблица, shortlist, черновики" />
          </div>
          <WizardTextArea label="Где нужен ручной контроль" value={manualControl} onChange={onManualControlChange} placeholder="Перед отправкой, публикацией, платежом, изменением данных" />
        </div>

        <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
          <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-900">
            <Database className="h-4 w-4" />
            Данные агента при создании
          </div>
          <div className="space-y-3">
            <input
              className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400"
              value={sourceName}
              onChange={(event) => onSourceNameChange(event.target.value)}
              placeholder="Название текста или файла"
            />
            <textarea
              className="min-h-28 w-full resize-none rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400"
              value={sourceText}
              onChange={(event) => onSourceTextChange(event.target.value)}
              placeholder="Вставьте текст документа, шаблон письма, CSV или контекст задачи"
            />
            <div className="flex flex-wrap gap-2">
              <label className="inline-flex cursor-pointer items-center rounded-md border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50">
                <Upload className="mr-2 h-4 w-4" />
                {fileSource ? fileSource.name : 'Добавить файл'}
                <input
                  type="file"
                  className="hidden"
                  accept=".txt,.csv,.tsv,.md,.pdf,.docx,.xlsx"
                  onChange={(event) => {
                    void handleBuilderFile(event.target.files?.[0] || null);
                    event.target.value = '';
                  }}
                />
              </label>
              {fileSource ? (
                <Button type="button" size="sm" variant="outline" onClick={() => onFileSourceChange(null)}>
                  Убрать файл
                </Button>
              ) : null}
            </div>
            <select
              className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400"
              value={internalSource}
              onChange={(event) => onInternalSourceChange(event.target.value)}
            >
              <option value="business_profile">Профиль бизнеса</option>
              <option value="services">Услуги</option>
              <option value="reviews">Отзывы</option>
              <option value="prospectingleads">Лиды</option>
              <option value="outreach_drafts">Черновики outreach</option>
              <option value="none">Не подключать источник LocalOS</option>
            </select>
            <div className="rounded-xl border border-emerald-100 bg-white px-3 py-3 text-xs leading-5 text-slate-600">
              <div className="font-semibold text-slate-950">Безопасность v1</div>
              <div className="mt-1">Generic agents готовят результат и ждут подтверждения. Отправка, публикация, платежи и destructive actions не выполняются автоматически.</div>
            </div>
          </div>
        </div>
      </div>
    </DashboardSection>
  );
};

const AgentWorkspacePanel = ({
  setupDataSources,
  setupExtractionRules,
  setupProcessingRules,
  setupOutputFormat,
  setupManualControl,
  sourceName,
  sourceText,
  internalSource,
  review,
  actionLoading,
  onSetupDataSourcesChange,
  onSetupExtractionRulesChange,
  onSetupProcessingRulesChange,
  onSetupOutputFormatChange,
  onSetupManualControlChange,
  onSourceNameChange,
  onSourceTextChange,
  onInternalSourceChange,
  onSaveSetup,
  onAddTextSource,
  onAddInternalSource,
  onAddFileSource,
}: {
  setupDataSources: string;
  setupExtractionRules: string;
  setupProcessingRules: string;
  setupOutputFormat: string;
  setupManualControl: string;
  sourceName: string;
  sourceText: string;
  internalSource: string;
  review: AgentReview | null;
  actionLoading: boolean;
  onSetupDataSourcesChange: (value: string) => void;
  onSetupExtractionRulesChange: (value: string) => void;
  onSetupProcessingRulesChange: (value: string) => void;
  onSetupOutputFormatChange: (value: string) => void;
  onSetupManualControlChange: (value: string) => void;
  onSourceNameChange: (value: string) => void;
  onSourceTextChange: (value: string) => void;
  onInternalSourceChange: (value: string) => void;
  onSaveSetup: () => void;
  onAddTextSource: () => void;
  onAddInternalSource: () => void;
  onAddFileSource: (file?: File | null) => void;
}) => (
  <DashboardSection
    title="Настройка агента"
    description="Короткий builder: данные, правила, результат и ручной контроль. Это рабочая версия без технического JSON на первом экране."
  >
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1.2fr)_minmax(20rem,0.8fr)]">
      <div className="grid gap-3">
        <WizardTextArea label="Какие данные использовать" value={setupDataSources} onChange={onSetupDataSourcesChange} placeholder="Например: профиль бизнеса, отзывы, файл с договором" />
        <WizardTextArea label="Что извлечь или понять" value={setupExtractionRules} onChange={onSetupExtractionRulesChange} placeholder="Например: риски, сроки, суммы, обязательства сторон" />
        <WizardTextArea label="Какие правила применить" value={setupProcessingRules} onChange={onSetupProcessingRulesChange} placeholder="Например: выделять спорные условия и не придумывать факты" />
        <WizardTextArea label="Какой результат подготовить" value={setupOutputFormat} onChange={onSetupOutputFormatChange} placeholder="Например: краткий отчёт, письмо клиенту, таблица исключений" />
        <WizardTextArea label="Где нужен ручной контроль" value={setupManualControl} onChange={onSetupManualControlChange} placeholder="Например: перед отправкой письма или публикацией ответа" />
        <div>
          <Button type="button" onClick={onSaveSetup} disabled={actionLoading}>
            {actionLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <CheckCircle2 className="mr-2 h-4 w-4" />}
            Сохранить настройку
          </Button>
        </div>
      </div>
      <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
        <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-900">
          <Database className="h-4 w-4" />
          Данные агента
        </div>
        <div className="space-y-3">
          <input
            className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400"
            value={sourceName}
            onChange={(event) => onSourceNameChange(event.target.value)}
            placeholder="Название источника"
          />
          <textarea
            className="min-h-24 w-full resize-none rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400"
            value={sourceText}
            onChange={(event) => onSourceTextChange(event.target.value)}
            placeholder="Вставьте текст, шаблон письма, выдержку из документа или CSV"
          />
          <div className="flex flex-wrap gap-2">
            <Button type="button" size="sm" onClick={onAddTextSource} disabled={actionLoading || !sourceText.trim()}>
              Добавить текст
            </Button>
            <label className="inline-flex cursor-pointer items-center rounded-md border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50">
              <Upload className="mr-2 h-4 w-4" />
              Файл
              <input
                type="file"
                className="hidden"
                accept=".txt,.csv,.tsv,.md,.pdf,.docx,.xlsx"
                onChange={(event) => {
                  void onAddFileSource(event.target.files?.[0] || null);
                  event.target.value = '';
                }}
              />
            </label>
          </div>
          <div className="flex gap-2">
            <select
              className="min-w-0 flex-1 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400"
              value={internalSource}
              onChange={(event) => onInternalSourceChange(event.target.value)}
            >
              <option value="business_profile">Профиль бизнеса</option>
              <option value="services">Услуги</option>
              <option value="reviews">Отзывы</option>
              <option value="prospectingleads">Лиды</option>
              <option value="outreach_drafts">Черновики outreach</option>
            </select>
            <Button type="button" size="sm" variant="outline" onClick={onAddInternalSource} disabled={actionLoading}>
              Подключить
            </Button>
          </div>
          <AgentSourcesList sources={review?.sources || []} />
        </div>
      </div>
    </div>
  </DashboardSection>
);

const WizardTextArea = ({ label, value, onChange, placeholder }: { label: string; value: string; onChange: (value: string) => void; placeholder: string }) => (
  <label className="text-xs font-medium text-slate-600">
    {label}
    <textarea
      className="mt-1 min-h-16 w-full resize-none rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-slate-400"
      value={value}
      onChange={(event) => onChange(event.target.value)}
      placeholder={placeholder}
    />
  </label>
);

const AgentSourcesList = ({ sources }: { sources: AgentSource[] }) => (
  <div className="space-y-2">
    {sources.length ? sources.map((source) => (
      <div key={source.id || source.name || source.file_name} className="rounded-lg bg-white px-3 py-2 text-xs leading-5 text-slate-600 ring-1 ring-slate-200">
        <div className="font-medium text-slate-900">{source.name || source.file_name || source.internal_source || 'Источник'}</div>
        <div>{humanizeMeta(source.internal_source || source.source_type || 'manual_context')} · {source.extraction_state || 'ready'} · {Number(source.content_length || 0)} chars</div>
      </div>
    )) : (
      <div className="rounded-lg border border-dashed border-slate-200 bg-white px-3 py-3 text-sm text-slate-500">
        Добавьте текст, файл или источник LocalOS.
      </div>
    )}
  </div>
);

const AgentRunReviewPanel = ({
  review,
  feedbackText,
  actionLoading,
  onFeedbackTextChange,
  onSubmitFeedback,
}: {
  review: AgentReview | null;
  feedbackText: string;
  actionLoading: boolean;
  onFeedbackTextChange: (value: string) => void;
  onSubmitFeedback: () => void;
}) => (
  <div className="rounded-2xl border border-slate-200 bg-white p-4">
    <div className="mb-3 flex items-center justify-between gap-3">
      <div>
        <div className="text-sm font-semibold text-slate-950">Review результата</div>
        <div className="mt-1 text-xs text-slate-500">Входные данные, что агент понял, результат и подтверждения без JSON по умолчанию.</div>
      </div>
      {review?.run_status ? <StatusBadge status={review.run_status} /> : null}
    </div>
    <div className="mb-4 grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(16rem,0.7fr)]">
      <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-3">
        <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Как настроен агент</div>
        <div className="mt-2 space-y-1 text-sm leading-6 text-slate-700">
          <div><span className="font-medium text-slate-950">Задача:</span> {String(review?.setup?.workflow_description || 'не задана')}</div>
          <div><span className="font-medium text-slate-950">Извлечь:</span> {String(review?.setup?.extraction_rules || 'не задано')}</div>
          <div><span className="font-medium text-slate-950">Результат:</span> {String(review?.setup?.output_format || 'не задан')}</div>
        </div>
      </div>
      <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-3">
        <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Источники</div>
        <AgentSourcesList sources={review?.sources || []} />
      </div>
    </div>
    {review?.sections?.length ? (
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {review.sections.map((section) => (
          <div key={`${section.artifact_type || section.title}`} className="rounded-xl bg-slate-50 px-3 py-3 ring-1 ring-slate-200">
            <div className="text-sm font-medium text-slate-950">{section.title || 'Результат'}</div>
            <div className="mt-1 text-xs leading-5 text-slate-600">{section.summary || section.status || 'Готово'}</div>
            <HumanPayloadView payload={section.payload || {}} />
            <details className="mt-2">
              <summary className="cursor-pointer text-xs font-medium text-slate-500 hover:text-slate-900">Технический журнал</summary>
              <pre className="mt-2 max-h-56 overflow-auto rounded-lg bg-slate-950 p-3 text-[11px] leading-5 text-slate-100">
                {JSON.stringify(section.payload || {}, null, 2)}
              </pre>
            </details>
          </div>
        ))}
      </div>
    ) : (
      <DashboardEmptyState title="Review появится после запуска" description="Запустите агента, чтобы увидеть extraction, processing и output." />
    )}
    <div className="mt-4 grid gap-2 md:grid-cols-[1fr_auto]">
      <textarea
        className="min-h-20 resize-none rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400"
        value={feedbackText}
        onChange={(event) => onFeedbackTextChange(event.target.value)}
        placeholder="Что исправить в логике агента для следующей версии?"
      />
      <Button type="button" onClick={onSubmitFeedback} disabled={actionLoading || !feedbackText.trim()}>
        Создать новую версию
      </Button>
    </div>
  </div>
);

const HumanPayloadView = ({ payload }: { payload: Record<string, unknown> }) => {
  const result = payload.result && typeof payload.result === 'object' && !Array.isArray(payload.result) ? payload.result : null;
  const items = Array.isArray(payload.items) ? payload.items : [];
  const missing = Array.isArray(payload.missing_information) ? payload.missing_information : [];
  const provenance = Array.isArray(payload.provenance) ? payload.provenance : [];

  return (
    <div className="mt-3 space-y-2 text-xs leading-5 text-slate-700">
      {missing.length ? (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-2 py-2 text-amber-800">
          Нужно уточнить: {missing.map((item) => String(item)).join(', ')}
        </div>
      ) : null}
      {provenance.length ? (
        <div className="rounded-lg bg-white px-2 py-2 ring-1 ring-slate-200">
          Источники: {provenance.map((item) => String(item)).join(', ')}
        </div>
      ) : null}
      {items.length ? (
        <div className="space-y-1">
          {items.slice(0, 3).map((item, index) => (
            <div key={`payload-item-${index}`} className="rounded-lg bg-white px-2 py-2 ring-1 ring-slate-200">
              {formatPayloadItem(item)}
            </div>
          ))}
        </div>
      ) : null}
      {result ? <HumanResultView result={result} /> : null}
    </div>
  );
};

const HumanResultView = ({ result }: { result: object }) => {
  const entries = Object.entries(result).filter(([, value]) => value !== '' && value !== null && value !== undefined);
  return (
    <div className="rounded-lg bg-white px-2 py-2 ring-1 ring-slate-200">
      {entries.slice(0, 5).map(([key, value]) => (
        <div key={key} className="mt-1 first:mt-0">
          <span className="font-medium text-slate-950">{humanizeMeta(key)}:</span> {formatPayloadValue(value)}
        </div>
      ))}
    </div>
  );
};

const formatPayloadItem = (value: unknown) => {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    const entries = Object.entries(value).filter(([, itemValue]) => itemValue !== '' && itemValue !== null && itemValue !== undefined);
    return entries.slice(0, 3).map(([key, itemValue]) => `${humanizeMeta(key)}: ${formatPayloadValue(itemValue)}`).join(' · ');
  }
  return formatPayloadValue(value);
};

const formatPayloadValue = (value: unknown): string => {
  if (Array.isArray(value)) {
    return value.slice(0, 4).map((item) => formatPayloadValue(item)).join(', ');
  }
  if (value && typeof value === 'object') {
    const entries = Object.entries(value).filter(([, itemValue]) => itemValue !== '' && itemValue !== null && itemValue !== undefined);
    return entries.slice(0, 3).map(([key, itemValue]) => `${humanizeMeta(key)}: ${formatPayloadValue(itemValue)}`).join('; ');
  }
  return String(value ?? '');
};

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
