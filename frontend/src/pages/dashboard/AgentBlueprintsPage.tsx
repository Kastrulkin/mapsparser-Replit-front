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
  Search,
  Send,
  ShieldCheck,
  Sparkles,
  Star,
  Upload,
  Users,
  Wrench,
  Workflow,
  Zap,
} from 'lucide-react';

import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  DashboardActionPanel,
  DashboardCompactMetricsRow,
  DashboardEmptyState,
  DashboardPageHeader,
  DashboardSection,
} from '@/components/dashboard/DashboardPrimitives';
import { AIAgentSettings } from '@/components/AIAgentSettings';
import { newAuth } from '@/lib/auth_new';
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
  active_version_id?: string | null;
  active_version_number?: number | null;
  active_goal?: string | null;
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
  active_version?: Record<string, unknown> | null;
  active_version_id?: string;
  active_version_number?: number;
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

type AgentSourceCatalogItem = {
  key: string;
  title: string;
  description?: string;
  available_count?: number;
  connected?: boolean;
  preview?: string[];
  state?: string;
};

type AgentReviewSection = {
  title?: string;
  artifact_type?: string;
  status?: string;
  summary?: string;
  payload?: Record<string, unknown>;
};

type AgentJournalEntry = {
  kind?: string;
  title?: string;
  status?: string;
  summary?: string;
  details?: Array<{ label?: string; value?: string }>;
  payload?: Record<string, unknown>;
};

type AgentReview = {
  has_run?: boolean;
  run_id?: string;
  run_status?: string;
  setup?: Record<string, unknown>;
  sources?: AgentSource[];
  sections?: AgentReviewSection[];
  journal?: AgentJournalEntry[];
  approvals?: AgentApproval[];
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

type PersonaAgent = {
  id: string;
  name?: string;
  type?: string;
  description?: string;
  task?: string;
  identity?: string;
  is_active?: boolean;
};

type AgentWorkspaceMode = 'settings' | 'run' | 'results';

type FeedbackVersionNotice = {
  version_number?: number;
  feedback?: string;
  next_run_note?: string;
};

type AgentBuilderMessage = {
  role: 'user' | 'assistant';
  content: string;
};

type AgentBuilderQuestion = {
  key?: string;
  question: string;
};

type AgentBuilderPreview = {
  understood_task?: string;
  category?: string;
  category_label?: string;
  agent_name?: string;
  data_sources?: string[];
  extraction_rules?: string;
  processing_rules?: string;
  output_format?: string;
  manual_control?: string;
  approval_boundaries?: string[];
  external_dispatch_performed?: boolean;
};

type AgentBuilderSession = {
  id: string;
  business_id: string;
  status: string;
  category: string;
  messages?: AgentBuilderMessage[];
  preview?: AgentBuilderPreview;
  missing_questions?: AgentBuilderQuestion[];
  blueprint_id?: string | null;
};

const getRequestErrorMessage = (requestError: unknown, fallback: string) => {
  if (requestError instanceof Error && requestError.message.trim()) {
    return requestError.message
      .replace(/^Ошибка соединения с сервером:\s*/i, '')
      .replace(/^Ошибка запроса:\s*/i, '');
  }
  return fallback;
};

const getVersionNumber = (version: Record<string, unknown> | undefined) => {
  const value = version?.version_number;
  return typeof value === 'number' ? value : null;
};

const getLatestVersionNumber = (blueprint: AgentBlueprint, details?: AgentBlueprintDetails | null) => {
  if (typeof blueprint.latest_version_number === 'number') {
    return blueprint.latest_version_number;
  }
  const versionNumbers: number[] = [];
  (details?.versions || []).forEach((version) => {
    const versionNumber = getVersionNumber(version);
    if (typeof versionNumber === 'number') {
      versionNumbers.push(versionNumber);
    }
  });
  return versionNumbers.length ? Math.max(...versionNumbers) : null;
};

const getActiveVersionNumber = (blueprint: AgentBlueprint, details?: AgentBlueprintDetails | null) => {
  if (typeof details?.active_version_number === 'number' && details.active_version_number > 0) {
    return details.active_version_number;
  }
  if (typeof blueprint.active_version_number === 'number' && blueprint.active_version_number > 0) {
    return blueprint.active_version_number;
  }
  const active = (details?.versions || []).find((version) => version.is_active === true);
  const activeNumber = getVersionNumber(active);
  if (typeof activeNumber === 'number') {
    return activeNumber;
  }
  return getLatestVersionNumber(blueprint, details);
};

const getActiveVersionId = (blueprint: AgentBlueprint, details?: AgentBlueprintDetails | null) => {
  if (typeof details?.active_version_id === 'string' && details.active_version_id) {
    return details.active_version_id;
  }
  if (typeof blueprint.active_version_id === 'string' && blueprint.active_version_id) {
    return blueprint.active_version_id;
  }
  const active = (details?.versions || []).find((version) => version.is_active === true);
  return typeof active?.id === 'string' ? active.id : '';
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
  input: 'входные данные',
  output: 'результат',
  extraction: 'извлечение',
  final: 'принятый итог',
  sourcing: 'поиск лидов',
  shortlist: 'список клиентов',
  drafts: 'черновики сообщений',
  queue: 'очередь',
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
  rules_applied: 'правила',
  feedback_notes: 'правки',
};

const outreachProgressStages = [
  { kind: 'sourcing', title: 'Нашёл лидов', detailLabel: 'Найдено лидов', icon: Search },
  { kind: 'shortlist', title: 'Собрал shortlist', detailLabel: 'Лидов в shortlist', icon: Users },
  { kind: 'drafts', title: 'Подготовил черновики', detailLabel: 'Черновиков', icon: MessageSquareText },
  { kind: 'queue', title: 'Поставил в очередь', detailLabel: 'В очереди', icon: Send },
];

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

const parseAgentConfig = (business?: DashboardContext['currentBusiness']) => {
  const rawConfig = business?.ai_agents_config;
  if (!rawConfig) {
    return {};
  }
  try {
    const parsed = typeof rawConfig === 'string' ? JSON.parse(rawConfig) : rawConfig;
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      return {};
    }
    const normalized: Record<string, { enabled?: boolean }> = {};
    Object.entries(parsed).forEach(([key, value]) => {
      if (value && typeof value === 'object' && !Array.isArray(value)) {
        const enabledEntry = Object.entries(value).find(([entryKey]) => entryKey === 'enabled');
        normalized[key] = { enabled: Boolean(enabledEntry ? enabledEntry[1] : false) };
      }
    });
    return normalized;
  } catch {
    return {};
  }
};

const uploadAgentSource = async (blueprintId: string, file: File, name: string) => {
  const token = newAuth.getToken();
  if (!token) {
    throw new Error('Authorization required');
  }
  const formData = new FormData();
  formData.append('file', file);
  formData.append('name', name || file.name);
  const response = await fetch(`/api/agent-blueprints/${blueprintId}/sources/upload`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: formData,
  });
  const data = await response.json();
  if (!response.ok || !data.success) {
    throw new Error(data.error || 'Не удалось прочитать файл');
  }
  return data;
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
  const [createWizardOpen, setCreateWizardOpen] = useState(false);
  const [createWizardStep, setCreateWizardStep] = useState(0);
  const [systemSettingsOpen, setSystemSettingsOpen] = useState(false);
  const [workspaceMode, setWorkspaceMode] = useState<AgentWorkspaceMode>('run');
  const [availablePersonaAgents, setAvailablePersonaAgents] = useState<PersonaAgent[]>([]);
  const [agentPrompt, setAgentPrompt] = useState('');
  const [builderCategory, setBuilderCategory] = useState('documents');
  const [builderDataSources, setBuilderDataSources] = useState('файл документа, ручной контекст, профиль бизнеса');
  const [builderExtractionRules, setBuilderExtractionRules] = useState('ключевые условия, сроки, суммы, ответственность, спорные места');
  const [builderProcessingRules, setBuilderProcessingRules] = useState('не придумывать факты, ссылаться только на добавленные данные, отдельно показывать риски');
  const [builderOutputFormat, setBuilderOutputFormat] = useState('краткий отчёт: summary, риски, что уточнить, черновик письма при необходимости');
  const [builderManualControl, setBuilderManualControl] = useState('перед использованием результата и перед любым внешним действием');
  const [builderSourceName, setBuilderSourceName] = useState('');
  const [builderSourceText, setBuilderSourceText] = useState('');
  const [builderFileSource, setBuilderFileSource] = useState<File | null>(null);
  const [builderInternalSource, setBuilderInternalSource] = useState('business_profile');
  const [dialogBuilderInput, setDialogBuilderInput] = useState('');
  const [dialogBuilderReply, setDialogBuilderReply] = useState('');
  const [dialogBuilderSession, setDialogBuilderSession] = useState<AgentBuilderSession | null>(null);
  const [agentReview, setAgentReview] = useState<AgentReview | null>(null);
  const [sourceCatalog, setSourceCatalog] = useState<AgentSourceCatalogItem[]>([]);
  const [setupDataSources, setSetupDataSources] = useState('профиль бизнеса, ручной контекст');
  const [setupExtractionRules, setSetupExtractionRules] = useState('');
  const [setupProcessingRules, setSetupProcessingRules] = useState('');
  const [setupOutputFormat, setSetupOutputFormat] = useState('');
  const [setupManualControl, setSetupManualControl] = useState('Показывать результат перед любым внешним действием');
  const [sourceName, setSourceName] = useState('');
  const [sourceText, setSourceText] = useState('');
  const [internalSource, setInternalSource] = useState('business_profile');
  const [feedbackText, setFeedbackText] = useState('');
  const [feedbackVersionNotice, setFeedbackVersionNotice] = useState<FeedbackVersionNotice | null>(null);
  const [systemAgentConfig, setSystemAgentConfig] = useState<Record<string, { enabled?: boolean }>>({});

  useEffect(() => {
    setSystemAgentConfig(parseAgentConfig(currentBusiness));
  }, [currentBusiness]);

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

  const systemAgents = useMemo(() => [
    {
      key: 'booking_agent',
      title: 'Агент записи',
      description: 'Помогает с правилами записи, вопросами клиенту и сценарием общения.',
      icon: Bot,
      enabled: Boolean(systemAgentConfig.booking_agent?.enabled),
    },
    {
      key: 'marketing_agent',
      title: 'Маркетинговый агент',
      description: 'Готовит идеи, тексты и маркетинговые черновики в стиле бизнеса.',
      icon: Zap,
      enabled: Boolean(systemAgentConfig.marketing_agent?.enabled),
    },
  ], [systemAgentConfig]);

  const activeAgentsCount = useMemo(
    () => systemAgents.filter((item) => item.enabled).length + blueprints.filter((item) => item.status === 'active').length,
    [blueprints, systemAgents],
  );

  const lastArtifactsCount = activeRun?.artifacts?.length || 0;

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
        label: 'Активны',
        value: activeAgentsCount,
        hint: `${systemAgents.length + blueprints.length} всего`,
      },
      {
        label: 'Ждут решения',
        value: pendingApprovals.length || activeRunPendingApprovals.length,
        hint: pendingApprovals.length ? 'Есть ожидающие решения' : 'Нет ожидающих решений',
        tone: pendingApprovals.length || pendingApproval ? 'warning' : 'default',
      },
      {
        label: 'Последние результаты',
        value: lastArtifactsCount,
        hint: activeRun ? `Запуск ${activeRun.id.slice(0, 8)}` : 'Нет активных запусков',
      },
      {
        label: 'Пользовательские агенты',
        value: blueprints.length + availablePersonaAgents.length,
        hint: currentBusiness?.name || 'Текущий бизнес',
      },
    ],
    [activeAgentsCount, activeRun, activeRunPendingApprovals.length, availablePersonaAgents.length, blueprints.length, currentBusiness?.name, lastArtifactsCount, pendingApproval, pendingApprovals.length, systemAgents.length],
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

  const loadPersonaAgents = useCallback(async () => {
    if (!currentBusinessId) {
      setAvailablePersonaAgents([]);
      return;
    }
    try {
      const token = newAuth.getToken();
      if (!token) {
        setAvailablePersonaAgents([]);
        return;
      }
      const response = await fetch(`/api/business/${currentBusinessId}/ai-agents/manage`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) {
        setAvailablePersonaAgents([]);
        return;
      }
      const data = await response.json();
      const agents = Array.isArray(data.agents) ? data.agents : [];
      const normalized = agents
        .filter((agent) => agent && typeof agent === 'object')
        .map((agent) => ({
          id: String(agent.id || ''),
          name: typeof agent.name === 'string' ? agent.name : '',
          type: typeof agent.type === 'string' ? agent.type : '',
          description: typeof agent.description === 'string' ? agent.description : '',
          task: typeof agent.task === 'string' ? agent.task : '',
          identity: typeof agent.identity === 'string' ? agent.identity : '',
          is_active: agent.is_active !== false,
        }))
        .filter((agent) => agent.id);
      setAvailablePersonaAgents(normalized);
    } catch (requestError) {
      console.error(requestError);
      setAvailablePersonaAgents([]);
    }
  }, [currentBusinessId]);

  useEffect(() => {
    void loadPersonaAgents();
  }, [loadPersonaAgents]);

  const loadBlueprintDetails = useCallback(async (blueprintId: string) => {
    setError(null);
    try {
      const params = runStatusFilter === 'all' ? {} : { run_status: runStatusFilter };
      const response = await api.get(`/agent-blueprints/${blueprintId}`, { params });
      const details = {
        versions: Array.isArray(response.data?.versions) ? response.data.versions : [],
        runs: Array.isArray(response.data?.runs) ? response.data.runs : [],
        approval_queue: Array.isArray(response.data?.approval_queue) ? response.data.approval_queue : [],
        active_version: response.data?.active_version || null,
        active_version_id: typeof response.data?.active_version_id === 'string' ? response.data.active_version_id : '',
        active_version_number: typeof response.data?.active_version_number === 'number' ? response.data.active_version_number : 0,
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
      setWorkspaceMode('results');
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

  const loadSourceCatalog = useCallback(async (blueprintId: string) => {
    try {
      const response = await api.get(`/agent-blueprints/${blueprintId}/sources/catalog`);
      const catalog = Array.isArray(response.data?.catalog) ? response.data.catalog : [];
      setSourceCatalog(catalog);
    } catch (requestError) {
      console.error(requestError);
      setSourceCatalog([]);
    }
  }, []);

  useEffect(() => {
    if (selectedBlueprint?.id) {
      void loadBlueprintReview(selectedBlueprint.id);
      void loadSourceCatalog(selectedBlueprint.id);
    } else {
      setAgentReview(null);
      setSourceCatalog([]);
    }
  }, [loadBlueprintReview, loadSourceCatalog, selectedBlueprint?.id]);

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
        await loadSourceCatalog(blueprint.id);
      }
    } catch (requestError) {
      console.error(requestError);
      setError('Не удалось создать supervised outreach blueprint.');
    } finally {
      setActionLoading(false);
    }
  };

  const startDialogBuilderSession = async () => {
    if (!currentBusinessId || !dialogBuilderInput.trim()) {
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      const response = await api.post('/agent-builder/sessions', {
        business_id: currentBusinessId,
        message: dialogBuilderInput.trim(),
      });
      setDialogBuilderSession(response.data?.session || null);
      setAgentPrompt(dialogBuilderInput.trim());
      const preview = response.data?.session?.preview || {};
      if (typeof preview.category === 'string') {
        setBuilderCategory(preview.category);
      }
      if (Array.isArray(preview.data_sources)) {
        setBuilderDataSources(preview.data_sources.join(', '));
      }
      if (typeof preview.extraction_rules === 'string') {
        setBuilderExtractionRules(preview.extraction_rules);
      }
      if (typeof preview.processing_rules === 'string') {
        setBuilderProcessingRules(preview.processing_rules);
      }
      if (typeof preview.output_format === 'string') {
        setBuilderOutputFormat(preview.output_format);
      }
      if (typeof preview.manual_control === 'string') {
        setBuilderManualControl(preview.manual_control);
      }
    } catch (requestError) {
      console.error(requestError);
      setError(getRequestErrorMessage(requestError, 'Не удалось начать диалог создания агента.'));
    } finally {
      setActionLoading(false);
    }
  };

  const sendDialogBuilderReply = async () => {
    if (!dialogBuilderSession || !dialogBuilderReply.trim()) {
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      const response = await api.post(`/agent-builder/sessions/${dialogBuilderSession.id}/message`, {
        message: dialogBuilderReply.trim(),
      });
      setDialogBuilderSession(response.data?.session || null);
      setDialogBuilderReply('');
    } catch (requestError) {
      console.error(requestError);
      setError(getRequestErrorMessage(requestError, 'Не удалось отправить уточнение агенту.'));
    } finally {
      setActionLoading(false);
    }
  };

  const createAgentFromDialogSession = async () => {
    if (!dialogBuilderSession) {
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      const response = await api.post(`/agent-builder/sessions/${dialogBuilderSession.id}/create-blueprint`, {});
      const blueprint = response.data?.blueprint;
      await loadBlueprints();
      if (blueprint?.id) {
        setSelectedBlueprintId(blueprint.id);
        await loadBlueprintDetails(blueprint.id);
        await loadBlueprintReview(blueprint.id);
      }
      setDialogBuilderInput('');
      setDialogBuilderReply('');
      setDialogBuilderSession(null);
      setCreateWizardOpen(false);
      setWorkspaceMode('settings');
    } catch (requestError) {
      console.error(requestError);
      setError(getRequestErrorMessage(requestError, 'Не удалось создать агента из диалога.'));
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
          await uploadAgentSource(blueprint.id, builderFileSource, builderSourceName.trim() || builderFileSource.name);
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
      setCreateWizardOpen(false);
      setCreateWizardStep(0);
      setWorkspaceMode('settings');
    } catch (requestError) {
      console.error(requestError);
      setError(getRequestErrorMessage(requestError, 'Не удалось собрать черновик агента.'));
    } finally {
      setActionLoading(false);
    }
  };

  const startRun = async (blueprintToRun?: AgentBlueprint | null, blueprintVersionId = '') => {
    const targetBlueprint = blueprintToRun || selectedBlueprint;
    if (!targetBlueprint) {
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      const response = await api.post(`/agent-blueprints/${targetBlueprint.id}/runs`, {
        blueprint_version_id: blueprintVersionId || undefined,
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
      setWorkspaceMode('results');
      await loadBlueprintDetails(targetBlueprint.id);
      await loadBlueprintReview(targetBlueprint.id);
    } catch (requestError) {
      console.error(requestError);
      setError('Не удалось запустить blueprint.');
    } finally {
      setActionLoading(false);
    }
  };

  const activateVersion = async (versionId: string, action: 'activate' | 'rollback') => {
    if (!selectedBlueprint || !versionId) {
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      await api.post(`/agent-blueprints/${selectedBlueprint.id}/versions/${versionId}/${action}`, {
        reason: action === 'rollback' ? 'Rollback from dashboard' : 'Activated from dashboard',
      });
      await loadBlueprints();
      await loadBlueprintDetails(selectedBlueprint.id);
      await loadBlueprintReview(selectedBlueprint.id);
    } catch (requestError) {
      console.error(requestError);
      setError(action === 'rollback' ? 'Не удалось откатить версию агента.' : 'Не удалось активировать версию агента.');
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
      await loadSourceCatalog(selectedBlueprint.id);
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
      await loadSourceCatalog(selectedBlueprint.id);
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
      await loadSourceCatalog(selectedBlueprint.id);
    } catch (requestError) {
      console.error(requestError);
      setError('Не удалось подключить источник LocalOS.');
    } finally {
      setActionLoading(false);
    }
  };

  const addInternalSourceByKey = async (sourceKey: string) => {
    if (!selectedBlueprint || !sourceKey) {
      return;
    }
    setInternalSource(sourceKey);
    setActionLoading(true);
    setError(null);
    try {
      await api.post(`/agent-blueprints/${selectedBlueprint.id}/sources`, {
        source_type: 'internal',
        name: humanizeMeta(sourceKey),
        internal_source: sourceKey,
      });
      await loadBlueprintReview(selectedBlueprint.id);
      await loadSourceCatalog(selectedBlueprint.id);
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
      await uploadAgentSource(selectedBlueprint.id, file, file.name);
      await loadBlueprintReview(selectedBlueprint.id);
      await loadSourceCatalog(selectedBlueprint.id);
    } catch (requestError) {
      console.error(requestError);
      setError(getRequestErrorMessage(requestError, 'Не удалось добавить файл.'));
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
      const response = await api.post(`/agent-runs/${activeRun.id}/feedback`, { feedback: feedbackText });
      const version = response.data?.version || {};
      setFeedbackVersionNotice({
        version_number: typeof version.version_number === 'number' ? version.version_number : undefined,
        feedback: feedbackText,
        next_run_note: 'Эта версия стала активной для следующих запусков; старые запуски остаются привязаны к версии, на которой были созданы.',
      });
      setFeedbackText('');
      if (selectedBlueprint?.id) {
        await loadBlueprintDetails(selectedBlueprint.id);
        await loadBlueprintReview(selectedBlueprint.id);
      }
    } catch (requestError) {
      console.error(requestError);
      setError(getRequestErrorMessage(requestError, 'Не удалось сохранить правку агента.'));
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <DashboardPageHeader
        eyebrow="LocalOS"
        title="Агенты"
        description="Центр управления системными и пользовательскими агентами."
        icon={Bot}
        actions={(
          <>
            <Button type="button" variant="outline" onClick={loadBlueprints} disabled={loading || !currentBusinessId}>
              <RefreshCw className={cn('mr-2 h-4 w-4', loading && 'animate-spin')} />
              Обновить
            </Button>
            <Button type="button" onClick={() => setCreateWizardOpen(true)} disabled={actionLoading || !currentBusinessId}>
              <Sparkles className="mr-2 h-4 w-4" />
              Создать агента
            </Button>
          </>
        )}
      />

      <Dialog open={createWizardOpen} onOpenChange={setCreateWizardOpen}>
        <DialogContent className="max-h-[88vh] max-w-5xl overflow-y-auto rounded-2xl">
          <DialogHeader>
            <DialogTitle>Создать агента</DialogTitle>
            <DialogDescription>
              Опишите задачу обычным языком. LocalOS уточнит недостающие детали и покажет preview агента перед созданием.
            </DialogDescription>
          </DialogHeader>
          <DialogAgentBuilder
            input={dialogBuilderInput}
            reply={dialogBuilderReply}
            session={dialogBuilderSession}
            actionLoading={actionLoading}
            onInputChange={setDialogBuilderInput}
            onReplyChange={setDialogBuilderReply}
            onStart={startDialogBuilderSession}
            onSendReply={sendDialogBuilderReply}
            onCreate={createAgentFromDialogSession}
          />
          <details className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
            <summary className="cursor-pointer text-sm font-medium text-slate-700">
              Открыть ручной мастер
            </summary>
            <div className="mt-4">
          <CreateAgentWizard
            step={createWizardStep}
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
            onStepChange={setCreateWizardStep}
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
            </div>
          </details>
        </DialogContent>
      </Dialog>

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
          title="Системные агенты"
          description="Предустановленные агенты LocalOS. Они включаются и настраиваются отдельно от workflow-запусков."
          actions={(
            <Button type="button" variant="outline" onClick={() => setSystemSettingsOpen(true)}>
              Настроить системных
            </Button>
          )}
        >
          <div className="grid gap-4 md:grid-cols-2">
            {systemAgents.map((agent) => (
              <SystemAgentCard
                key={agent.key}
                title={agent.title}
                description={agent.description}
                icon={agent.icon}
                enabled={agent.enabled}
                onConfigure={() => setSystemSettingsOpen(true)}
              />
            ))}
          </div>
        </DashboardSection>
      ) : null}

      <Dialog open={systemSettingsOpen} onOpenChange={setSystemSettingsOpen}>
        <DialogContent className="max-h-[88vh] max-w-6xl overflow-y-auto rounded-2xl p-0">
          <DialogHeader className="px-6 pt-6">
            <DialogTitle>Системные агенты</DialogTitle>
            <DialogDescription>Настройки агента записи, маркетингового агента и persona/chat поведения.</DialogDescription>
          </DialogHeader>
          <AIAgentSettings businessId={currentBusinessId} business={currentBusiness} />
        </DialogContent>
      </Dialog>

      <DashboardSection
        title="Пользовательские агенты"
        description="Процессные агенты запускают задачи, агенты голоса задают стиль общения."
      >
        <div className="space-y-6">
          {loading ? (
            <div className="flex items-center gap-2 text-sm text-slate-500">
              <Loader2 className="h-4 w-4 animate-spin" />
              Загружаем агентов...
            </div>
          ) : blueprints.length === 0 && availablePersonaAgents.length === 0 ? (
            <DashboardEmptyState
              title="Пользовательских агентов пока нет"
              description="Создайте агента через мастер или добавьте persona для голоса общения."
            />
          ) : (
            <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
              {blueprints.map((blueprint) => {
                const selected = selectedBlueprint?.id === blueprint.id;
                return (
                    <BlueprintAgentCard
                    key={blueprint.id}
                    blueprint={blueprint}
                    latestVersionNumber={getActiveVersionNumber(blueprint, selected ? blueprintDetails : null)}
                    selected={selected}
                    onSelect={() => {
                      setSelectedBlueprintId(blueprint.id);
                      setActiveRun(null);
                    }}
                    onConfigure={() => {
                      setSelectedBlueprintId(blueprint.id);
                      setActiveRun(null);
                      setWorkspaceMode('settings');
                    }}
                    onRun={() => {
                      setSelectedBlueprintId(blueprint.id);
                      setWorkspaceMode('run');
                      void startRun(blueprint);
                    }}
                    onResults={() => {
                      setSelectedBlueprintId(blueprint.id);
                      setWorkspaceMode('results');
                    }}
                  />
                );
              })}
              {availablePersonaAgents.map((agent) => (
                <PersonaAgentCard key={agent.id} agent={agent} onConfigure={() => setSystemSettingsOpen(true)} />
              ))}
            </div>
          )}
        </div>
      </DashboardSection>

      {selectedBlueprint ? (
        <AgentDetailPanel
          mode={workspaceMode}
          blueprint={selectedBlueprint}
          blueprintDetails={blueprintDetails}
          activeRun={activeRun}
          pendingApproval={pendingApproval}
          queuedButNotDispatched={queuedButNotDispatched}
          agentReview={agentReview}
          feedbackText={feedbackText}
          feedbackVersionNotice={feedbackVersionNotice}
          actionLoading={actionLoading}
          setupDataSources={setupDataSources}
          setupExtractionRules={setupExtractionRules}
          setupProcessingRules={setupProcessingRules}
          setupOutputFormat={setupOutputFormat}
          setupManualControl={setupManualControl}
          sourceName={sourceName}
          sourceText={sourceText}
          internalSource={internalSource}
          sourceCatalog={sourceCatalog}
          runSource={runSource}
          runCity={runCity}
          runCategory={runCategory}
          runLimit={runLimit}
          onModeChange={setWorkspaceMode}
          onStartRun={() => startRun(selectedBlueprint)}
          onStartVersionRun={(versionId) => startRun(selectedBlueprint, versionId)}
          onActivateVersion={(versionId) => activateVersion(versionId, 'activate')}
          onRollbackVersion={(versionId) => activateVersion(versionId, 'rollback')}
          onApprove={() => decideApproval('approve')}
          onReject={() => decideApproval('reject')}
          onFeedbackTextChange={setFeedbackText}
          onSubmitFeedback={sendRunFeedback}
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
          onAddCatalogSource={addInternalSourceByKey}
          onAddFileSource={addFileSource}
          onRunSourceChange={setRunSource}
          onRunCityChange={setRunCity}
          onRunCategoryChange={setRunCategory}
          onRunLimitChange={setRunLimit}
        />
      ) : null}

      {selectedBlueprint ? (
        <DashboardSection
          title="Последние запуски"
          description="Короткая история выбранного агента."
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
          title="Ждут решения"
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

const CreateAgentWizard = ({
  step,
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
  onStepChange,
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
  step: number;
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
  fileSource: File | null;
  internalSource: string;
  actionLoading: boolean;
  canCreate: boolean;
  onStepChange: (value: number) => void;
  onScenarioSelect: (scenario: AgentBuilderScenario) => void;
  onPromptChange: (value: string) => void;
  onDataSourcesChange: (value: string) => void;
  onExtractionRulesChange: (value: string) => void;
  onProcessingRulesChange: (value: string) => void;
  onOutputFormatChange: (value: string) => void;
  onManualControlChange: (value: string) => void;
  onSourceNameChange: (value: string) => void;
  onSourceTextChange: (value: string) => void;
  onFileSourceChange: (value: File | null) => void;
  onInternalSourceChange: (value: string) => void;
  onCreate: () => void;
}) => {
  const steps = ['Тип агента', 'Данные', 'Правила и контроль', 'Результат'];
  const handleBuilderFile = async (file?: File | null) => {
    if (!file) {
      onFileSourceChange(null);
      return;
    }
    onFileSourceChange(file);
  };

  return (
    <div className="space-y-5">
      <div className="grid gap-2 md:grid-cols-4">
        {steps.map((label, index) => (
          <button
            key={label}
            type="button"
            className={cn(
              'rounded-xl border px-3 py-2 text-left text-sm font-medium transition',
              step === index ? 'border-slate-900 bg-slate-950 text-white' : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300',
            )}
            onClick={() => onStepChange(index)}
          >
            <span className="mr-2 inline-flex h-5 w-5 items-center justify-center rounded-full bg-white/15 text-xs">{index + 1}</span>
            {label}
          </button>
        ))}
      </div>

      {step === 0 ? (
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
            placeholder="Опишите, какого агента хотите создать"
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
        </div>
      ) : null}

      {step === 1 ? (
        <div className="grid gap-4 lg:grid-cols-[1fr_20rem]">
          <WizardTextArea label="Какие данные использовать" value={dataSources} onChange={onDataSourcesChange} placeholder="Файл, текст, профиль бизнеса, услуги, отзывы" />
          <div className="space-y-3 rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
            <input
              className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400"
              value={sourceName}
              onChange={(event) => onSourceNameChange(event.target.value)}
              placeholder="Название источника"
            />
            <textarea
              className="min-h-28 w-full resize-none rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400"
              value={sourceText}
              onChange={(event) => onSourceTextChange(event.target.value)}
              placeholder="Вставьте текст, CSV или контекст задачи"
            />
            <div className="flex flex-wrap gap-2">
              <label className="inline-flex cursor-pointer items-center rounded-md border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50">
                <Upload className="mr-2 h-4 w-4" />
                {fileSource ? fileSource.name : 'Файл'}
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
                  Убрать
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
          </div>
        </div>
      ) : null}

      {step === 2 ? (
        <div className="grid gap-3 md:grid-cols-2">
          <WizardTextArea label="Что агент должен извлечь или понять" value={extractionRules} onChange={onExtractionRulesChange} placeholder="Поля, риски, сроки, исключения, факты" />
          <WizardTextArea label="Какие правила применить" value={processingRules} onChange={onProcessingRulesChange} placeholder="Не придумывать факты, учитывать стиль, помечать спорное" />
          <WizardTextArea label="Где нужен ручной контроль" value={manualControl} onChange={onManualControlChange} placeholder="Перед отправкой, публикацией, платежом, изменением данных" />
          <div className="rounded-xl border border-emerald-100 bg-emerald-50 px-4 py-4 text-sm leading-6 text-emerald-900">
            Generic agents в v1 готовят результат и ждут проверки. Внешние отправки, публикации, платежи и destructive actions не запускаются из wizard.
          </div>
        </div>
      ) : null}

      {step === 3 ? (
        <div className="grid gap-4 lg:grid-cols-[1fr_20rem]">
          <WizardTextArea label="Какой результат подготовить" value={outputFormat} onChange={onOutputFormatChange} placeholder="Отчёт, письмо, таблица, shortlist, черновики" />
          <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4 text-sm leading-6 text-slate-700">
            <div className="font-semibold text-slate-950">{selectedScenario.title}</div>
            <div className="mt-2">{prompt || selectedScenario.prompt}</div>
            <div className="mt-3 text-xs text-slate-500">После создания агент появится в “Пользовательских агентах”. Запуск будет из карточки агента.</div>
          </div>
        </div>
      ) : null}

      <DialogFooter className="gap-2 sm:justify-between">
        <Button type="button" variant="outline" onClick={() => onStepChange(Math.max(0, step - 1))} disabled={step === 0}>
          Назад
        </Button>
        {step < 3 ? (
          <Button type="button" onClick={() => onStepChange(Math.min(3, step + 1))}>
            Далее
          </Button>
        ) : (
          <Button type="button" onClick={onCreate} disabled={actionLoading || !canCreate}>
            {actionLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Sparkles className="mr-2 h-4 w-4" />}
            Создать агента
          </Button>
        )}
      </DialogFooter>
    </div>
  );
};

const DialogAgentBuilder = ({
  input,
  reply,
  session,
  actionLoading,
  onInputChange,
  onReplyChange,
  onStart,
  onSendReply,
  onCreate,
}: {
  input: string;
  reply: string;
  session: AgentBuilderSession | null;
  actionLoading: boolean;
  onInputChange: (value: string) => void;
  onReplyChange: (value: string) => void;
  onStart: () => void;
  onSendReply: () => void;
  onCreate: () => void;
}) => {
  const preview = session?.preview || null;
  const questions = session?.missing_questions || [];
  const messages = session?.messages || [];
  return (
    <div className="space-y-4 rounded-2xl border border-slate-200 bg-white p-4">
      <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto]">
        <textarea
          className="min-h-28 resize-none rounded-xl border border-slate-200 px-3 py-2 text-sm leading-6 outline-none transition focus:border-slate-400"
          value={input}
          onChange={(event) => onInputChange(event.target.value)}
          placeholder="Например: мне нужен агент, который проверяет договоры, находит риски и готовит краткий отчёт"
        />
        <Button type="button" onClick={onStart} disabled={actionLoading || !input.trim()}>
          {actionLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Sparkles className="mr-2 h-4 w-4" />}
          Начать диалог
        </Button>
      </div>

      {session ? (
        <div className="grid gap-4 lg:grid-cols-[minmax(0,0.95fr)_minmax(20rem,1.05fr)]">
          <div className="space-y-3">
            <div className="text-sm font-semibold text-slate-950">Диалог настройки</div>
            <div className="max-h-72 space-y-2 overflow-auto rounded-xl bg-slate-50 p-3">
              {messages.slice(-6).map((message, index) => (
                <div
                  key={`${message.role}-${index}-${message.content.slice(0, 12)}`}
                  className={cn(
                    'rounded-xl px-3 py-2 text-sm leading-6',
                    message.role === 'user' ? 'ml-8 bg-slate-950 text-white' : 'mr-8 bg-white text-slate-700 ring-1 ring-slate-200',
                  )}
                >
                  {message.content}
                </div>
              ))}
            </div>
            {questions.length ? (
              <div className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-3">
                <div className="text-sm font-semibold text-amber-900">Нужно уточнить</div>
                <div className="mt-2 space-y-1">
                  {questions.map((question) => (
                    <div key={question.key || question.question} className="text-sm leading-6 text-amber-900">
                      {question.question}
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-3 text-sm text-emerald-900">
                Данных достаточно для первого blueprint. После создания можно добавить файлы и источники.
              </div>
            )}
            <div className="grid gap-2 md:grid-cols-[1fr_auto]">
              <textarea
                className="min-h-16 resize-none rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none transition focus:border-slate-400"
                value={reply}
                onChange={(event) => onReplyChange(event.target.value)}
                placeholder="Ответьте на уточнение или добавьте правило"
              />
              <Button type="button" variant="outline" onClick={onSendReply} disabled={actionLoading || !reply.trim()}>
                Ответить
              </Button>
            </div>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="text-sm font-semibold text-slate-950">Preview будущего агента</div>
                <div className="mt-1 text-xs text-slate-500">Проверьте задачу, данные, правила и ручной контроль перед созданием.</div>
              </div>
              <span className="rounded-full bg-white px-2.5 py-1 text-xs font-medium text-slate-700 ring-1 ring-slate-200">
                {preview?.category_label || humanizeCategory(session.category)}
              </span>
            </div>
            <div className="mt-4 space-y-3 text-sm leading-6 text-slate-700">
              <PreviewRow label="Понял задачу так" value={preview?.understood_task || input} />
              <PreviewRow label="Данные" value={(preview?.data_sources || []).map((item) => humanizeMeta(item)).join(', ') || 'уточнить'} />
              <PreviewRow label="Что извлечь" value={preview?.extraction_rules || 'уточнить'} />
              <PreviewRow label="Правила" value={preview?.processing_rules || 'уточнить'} />
              <PreviewRow label="Результат" value={preview?.output_format || 'уточнить'} />
              <PreviewRow label="Ручной контроль" value={preview?.manual_control || 'перед внешним действием'} />
            </div>
            <div className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs leading-5 text-emerald-900">
              Внешние отправки, публикации, платежи и destructive actions не запускаются из builder. Рискованные действия требуют approval.
            </div>
            <div className="mt-4 flex justify-end">
              <Button type="button" onClick={onCreate} disabled={actionLoading}>
                {actionLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <CheckCircle2 className="mr-2 h-4 w-4" />}
                Создать из preview
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
};

const PreviewRow = ({ label, value }: { label: string; value: string }) => (
  <div className="rounded-xl bg-white px-3 py-2 ring-1 ring-slate-200">
    <div className="text-xs font-semibold uppercase text-slate-500">{label}</div>
    <div className="mt-1 text-slate-800">{value}</div>
  </div>
);

const SystemAgentCard = ({
  title,
  description,
  icon: Icon,
  enabled,
  onConfigure,
}: {
  title: string;
  description: string;
  icon: typeof Bot;
  enabled: boolean;
  onConfigure: () => void;
}) => (
  <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
    <div className="flex items-start justify-between gap-3">
      <div className="flex min-w-0 items-start gap-3">
        <div className="rounded-xl bg-slate-100 p-2 text-slate-700">
          <Icon className="h-5 w-5" />
        </div>
        <div className="min-w-0">
          <div className="text-sm font-semibold text-slate-950">{title}</div>
          <div className="mt-1 text-sm leading-6 text-slate-600">{description}</div>
        </div>
      </div>
      <span className={cn('shrink-0 rounded-full px-2.5 py-1 text-xs font-medium ring-1', enabled ? 'bg-emerald-50 text-emerald-700 ring-emerald-200' : 'bg-slate-100 text-slate-600 ring-slate-200')}>
        {enabled ? 'Включён' : 'Выключен'}
      </span>
    </div>
    <div className="mt-4 flex justify-end">
      <Button type="button" size="sm" variant="outline" onClick={onConfigure}>
        Настроить
      </Button>
    </div>
  </div>
);

const BlueprintAgentCard = ({
  blueprint,
  latestVersionNumber,
  selected,
  onSelect,
  onConfigure,
  onRun,
  onResults,
}: {
  blueprint: AgentBlueprint;
  latestVersionNumber: number | null;
  selected: boolean;
  onSelect: () => void;
  onConfigure: () => void;
  onRun: () => void;
  onResults: () => void;
}) => (
  <div className={cn('rounded-2xl border bg-white p-4 shadow-sm transition', selected ? 'border-slate-900' : 'border-slate-200 hover:border-slate-300')}>
    <button type="button" className="w-full text-left" onClick={onSelect}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold text-slate-950">{blueprint.name}</div>
          <div className="mt-1 text-xs font-medium text-slate-500">
            {humanizeCategory(blueprint.category)} · {latestVersionNumber ? `активная версия v${latestVersionNumber}` : 'версия ещё не создана'}
          </div>
        </div>
        <StatusBadge status={blueprint.status || 'draft'} />
      </div>
      <div className="mt-3 line-clamp-3 text-sm leading-6 text-slate-600">
        {blueprint.description || blueprint.latest_goal || 'Пользовательский агент с настройками, запусками и результатами.'}
      </div>
    </button>
    <div className="mt-4 flex flex-wrap gap-2">
      <Button type="button" size="sm" variant="outline" onClick={onConfigure}>
        Настроить
      </Button>
      <Button type="button" size="sm" onClick={onRun}>
        <Play className="mr-2 h-4 w-4" />
        Запустить
      </Button>
      <Button type="button" size="sm" variant="ghost" onClick={onResults}>
        Результаты
      </Button>
    </div>
  </div>
);

const PersonaAgentCard = ({ agent, onConfigure }: { agent: PersonaAgent; onConfigure: () => void }) => (
  <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
    <div className="flex items-start justify-between gap-3">
      <div className="min-w-0">
        <div className="truncate text-sm font-semibold text-slate-950">{agent.name || 'Persona agent'}</div>
        <div className="mt-1 text-xs font-medium text-slate-500">Голос и стиль общения</div>
      </div>
      <span className={cn('rounded-full px-2.5 py-1 text-xs font-medium ring-1', agent.is_active ? 'bg-emerald-50 text-emerald-700 ring-emerald-200' : 'bg-slate-100 text-slate-600 ring-slate-200')}>
        {agent.is_active ? 'Включён' : 'Выключен'}
      </span>
    </div>
    <div className="mt-3 line-clamp-3 text-sm leading-6 text-slate-600">
      {agent.description || agent.task || agent.identity || 'Настраивает тон, стиль и ограничения общения. Не является workflow runtime.'}
    </div>
    <div className="mt-4 flex justify-end">
      <Button type="button" size="sm" variant="outline" onClick={onConfigure}>
        Открыть настройки
      </Button>
    </div>
  </div>
);

const AgentDetailPanel = ({
  mode,
  blueprint,
  blueprintDetails,
  activeRun,
  pendingApproval,
  queuedButNotDispatched,
  agentReview,
  feedbackText,
  feedbackVersionNotice,
  actionLoading,
  setupDataSources,
  setupExtractionRules,
  setupProcessingRules,
  setupOutputFormat,
  setupManualControl,
  sourceName,
  sourceText,
  internalSource,
  sourceCatalog,
  runSource,
  runCity,
  runCategory,
  runLimit,
  onModeChange,
  onStartRun,
  onStartVersionRun,
  onActivateVersion,
  onRollbackVersion,
  onApprove,
  onReject,
  onFeedbackTextChange,
  onSubmitFeedback,
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
  onAddCatalogSource,
  onAddFileSource,
  onRunSourceChange,
  onRunCityChange,
  onRunCategoryChange,
  onRunLimitChange,
}: {
  mode: AgentWorkspaceMode;
  blueprint: AgentBlueprint;
  blueprintDetails: AgentBlueprintDetails | null;
  activeRun: AgentRun | null;
  pendingApproval: AgentApproval | null;
  queuedButNotDispatched: AgentArtifact['payload_json'] | AgentRunStep['output_json'] | null;
  agentReview: AgentReview | null;
  feedbackText: string;
  feedbackVersionNotice: FeedbackVersionNotice | null;
  actionLoading: boolean;
  setupDataSources: string;
  setupExtractionRules: string;
  setupProcessingRules: string;
  setupOutputFormat: string;
  setupManualControl: string;
  sourceName: string;
  sourceText: string;
  internalSource: string;
  sourceCatalog: AgentSourceCatalogItem[];
  runSource: string;
  runCity: string;
  runCategory: string;
  runLimit: string;
  onModeChange: (mode: AgentWorkspaceMode) => void;
  onStartRun: () => void;
  onStartVersionRun: (versionId: string) => void;
  onActivateVersion: (versionId: string) => void;
  onRollbackVersion: (versionId: string) => void;
  onApprove: () => void;
  onReject: () => void;
  onFeedbackTextChange: (value: string) => void;
  onSubmitFeedback: () => void;
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
  onAddCatalogSource: (sourceKey: string) => void;
  onAddFileSource: (file?: File | null) => void;
  onRunSourceChange: (value: string) => void;
  onRunCityChange: (value: string) => void;
  onRunCategoryChange: (value: string) => void;
  onRunLimitChange: (value: string) => void;
}) => {
  const latestVersionNumber = getActiveVersionNumber(blueprint, blueprintDetails);
  const activeVersionId = getActiveVersionId(blueprint, blueprintDetails);
  const versions = blueprintDetails?.versions || [];
  return (
  <DashboardSection
    title={blueprint.name}
    description={`${humanizeCategory(blueprint.category)} · ${latestVersionNumber ? `активная версия v${latestVersionNumber}` : 'нет активной версии'} · ${mode === 'settings' ? 'настройка агента' : mode === 'run' ? 'запуск из карточки' : 'сохранённые результаты'}`}
    actions={(
      <div className="flex flex-wrap gap-2">
        <Button type="button" size="sm" variant={mode === 'settings' ? 'default' : 'outline'} onClick={() => onModeChange('settings')}>Настроить</Button>
        <Button type="button" size="sm" variant={mode === 'run' ? 'default' : 'outline'} onClick={() => onModeChange('run')}>Запуск</Button>
        <Button type="button" size="sm" variant={mode === 'results' ? 'default' : 'outline'} onClick={() => onModeChange('results')}>Сохранённые результаты</Button>
      </div>
    )}
  >
    {mode === 'settings' ? (
        <AgentWorkspacePanel
        versions={versions}
        latestVersionNumber={latestVersionNumber}
        activeVersionId={activeVersionId}
        setupDataSources={setupDataSources}
        setupExtractionRules={setupExtractionRules}
        setupProcessingRules={setupProcessingRules}
        setupOutputFormat={setupOutputFormat}
        setupManualControl={setupManualControl}
        sourceName={sourceName}
        sourceText={sourceText}
        internalSource={internalSource}
        sourceCatalog={sourceCatalog}
        review={agentReview}
        actionLoading={actionLoading}
        onSetupDataSourcesChange={onSetupDataSourcesChange}
        onSetupExtractionRulesChange={onSetupExtractionRulesChange}
        onSetupProcessingRulesChange={onSetupProcessingRulesChange}
        onSetupOutputFormatChange={onSetupOutputFormatChange}
        onSetupManualControlChange={onSetupManualControlChange}
        onSourceNameChange={onSourceNameChange}
        onSourceTextChange={onSourceTextChange}
        onInternalSourceChange={onInternalSourceChange}
        onSaveSetup={onSaveSetup}
        onStartVersionRun={onStartVersionRun}
        onActivateVersion={onActivateVersion}
        onRollbackVersion={onRollbackVersion}
        onAddTextSource={onAddTextSource}
        onAddInternalSource={onAddInternalSource}
        onAddCatalogSource={onAddCatalogSource}
        onAddFileSource={onAddFileSource}
      />
    ) : null}

    {mode === 'run' ? (
      <div className="rounded-2xl border border-slate-200 bg-white p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="text-sm font-semibold text-slate-950">Запуск агента</div>
            <div className="mt-1 text-sm leading-6 text-slate-600">
              Запуск открывается из карточки конкретного агента. Для outreach показываем поля поиска, для остальных типов используем подключённые данные агента.
            </div>
          </div>
          <Button type="button" onClick={onStartRun} disabled={actionLoading}>
            {actionLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Play className="mr-2 h-4 w-4" />}
            Запустить
          </Button>
        </div>
        {blueprint.category === 'outreach' ? (
          <div className="mt-4 grid gap-3 md:grid-cols-4">
            <input className="rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-slate-400" value={runSource} onChange={(event) => onRunSourceChange(event.target.value)} placeholder="Источник" />
            <input className="rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-slate-400" value={runCity} onChange={(event) => onRunCityChange(event.target.value)} placeholder="Город" />
            <input className="rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-slate-400" value={runCategory} onChange={(event) => onRunCategoryChange(event.target.value)} placeholder="Категория" />
            <input className="rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-slate-400" value={runLimit} onChange={(event) => onRunLimitChange(event.target.value)} placeholder="Лимит" />
          </div>
        ) : (
          <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm leading-6 text-slate-600">
            Этот агент возьмёт данные из блока “Данные агента” и подготовит результат без внешней отправки.
          </div>
        )}
      </div>
    ) : null}

    {mode === 'results' ? (
      <div className="space-y-4">
        {blueprint.category === 'outreach' ? (
          <OutreachRunProgress review={agentReview} activeRun={activeRun} />
        ) : null}
        {queuedButNotDispatched ? (
          <DashboardActionPanel
            title="Поставлено в очередь, но не отправлено"
            description="Агент поставил batch в безопасную очередь. Dispatcher не запускался из этого экрана."
            tone="amber"
          />
        ) : null}
        {pendingApproval ? (
          <DashboardActionPanel
            title="Ждёт решения"
            description={pendingApproval.title}
            tone="amber"
            actions={(
              <div className="flex flex-wrap gap-2">
                <Button type="button" onClick={onApprove} disabled={actionLoading}>Принять</Button>
                <Button type="button" variant="outline" onClick={onReject} disabled={actionLoading}>Отклонить</Button>
              </div>
            )}
          />
        ) : null}
        {activeRun ? (
          <div className="grid gap-4 xl:grid-cols-3">
            <RunColumn title="Что сделал агент" icon={Clock3}>
              {(activeRun.steps || []).map((step) => (
                <TimelineItem key={step.id} title={humanizeStep(step.step_key)} meta={humanizeMeta(step.step_type)} status={step.status} />
              ))}
            </RunColumn>
            <RunColumn title="Сохранённые результаты" icon={FileCheck2}>
              {(activeRun.artifacts || []).map((artifact) => <ArtifactItem key={artifact.id} artifact={artifact} />)}
            </RunColumn>
            <RunColumn title="Ручной контроль" icon={ShieldCheck}>
              {(activeRun.approvals || []).map((approval) => (
                <TimelineItem key={approval.id} title={approval.title} meta={humanizeMeta(approval.approval_type)} status={approval.status} />
              ))}
            </RunColumn>
          </div>
        ) : (
          <DashboardEmptyState title="Нет активных запусков" description="Запустите агента из карточки, чтобы увидеть результат." />
        )}
        <AgentRunReviewPanel
          review={agentReview}
          latestVersionNumber={latestVersionNumber}
          feedbackText={feedbackText}
          feedbackVersionNotice={feedbackVersionNotice}
          actionLoading={actionLoading}
          onFeedbackTextChange={onFeedbackTextChange}
          onSubmitFeedback={onSubmitFeedback}
        />
      </div>
    ) : null}
  </DashboardSection>
  );
};

const AgentWorkspacePanel = ({
  versions,
  latestVersionNumber,
  activeVersionId,
  setupDataSources,
  setupExtractionRules,
  setupProcessingRules,
  setupOutputFormat,
  setupManualControl,
  sourceName,
  sourceText,
  internalSource,
  sourceCatalog,
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
  onStartVersionRun,
  onActivateVersion,
  onRollbackVersion,
  onAddTextSource,
  onAddInternalSource,
  onAddCatalogSource,
  onAddFileSource,
}: {
  versions: Array<Record<string, unknown>>;
  latestVersionNumber: number | null;
  activeVersionId: string;
  setupDataSources: string;
  setupExtractionRules: string;
  setupProcessingRules: string;
  setupOutputFormat: string;
  setupManualControl: string;
  sourceName: string;
  sourceText: string;
  internalSource: string;
  sourceCatalog: AgentSourceCatalogItem[];
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
  onStartVersionRun: (versionId: string) => void;
  onActivateVersion: (versionId: string) => void;
  onRollbackVersion: (versionId: string) => void;
  onAddTextSource: () => void;
  onAddInternalSource: () => void;
  onAddCatalogSource: (sourceKey: string) => void;
  onAddFileSource: (file?: File | null) => void;
}) => (
  <DashboardSection
    title="Настройка агента"
    description="Короткий builder: данные, правила, результат и ручной контроль. Это рабочая версия без технического JSON на первом экране."
  >
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1.2fr)_minmax(20rem,0.8fr)]">
      <div className="grid gap-3">
        <VersionSummary
          versions={versions}
          latestVersionNumber={latestVersionNumber}
          activeVersionId={activeVersionId}
          onStartVersionRun={onStartVersionRun}
          onActivateVersion={onActivateVersion}
          onRollbackVersion={onRollbackVersion}
        />
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
          <DatahubCatalogList
            catalog={sourceCatalog}
            actionLoading={actionLoading}
            onConnect={onAddCatalogSource}
          />
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

const DatahubCatalogList = ({
  catalog,
  actionLoading,
  onConnect,
}: {
  catalog: AgentSourceCatalogItem[];
  actionLoading: boolean;
  onConnect: (sourceKey: string) => void;
}) => (
  <div className="space-y-2 rounded-xl border border-slate-200 bg-white p-3">
    <div className="flex items-center justify-between gap-3">
      <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Datahub LocalOS</div>
      <span className="text-xs text-slate-400">{catalog.length ? `${catalog.length} источников` : 'источники не загружены'}</span>
    </div>
    {catalog.length ? catalog.map((item) => (
      <div key={item.key} className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="text-sm font-medium text-slate-950">{item.title || humanizeMeta(item.key)}</div>
            <div className="mt-1 text-xs leading-5 text-slate-500">{item.description || 'Источник данных LocalOS'}</div>
          </div>
          <span className={cn(
            'shrink-0 rounded-full px-2 py-1 text-xs font-medium ring-1',
            item.connected ? 'bg-emerald-50 text-emerald-700 ring-emerald-200' : item.available_count ? 'bg-white text-slate-700 ring-slate-200' : 'bg-slate-100 text-slate-500 ring-slate-200',
          )}>
            {item.connected ? 'подключено' : item.available_count ? `${item.available_count}` : 'пусто'}
          </span>
        </div>
        {item.preview?.length ? (
          <div className="mt-2 space-y-1">
            {item.preview.slice(0, 2).map((line, index) => (
              <div key={`${item.key}-${index}`} className="truncate rounded-md bg-white px-2 py-1 text-xs text-slate-600 ring-1 ring-slate-100">
                {line}
              </div>
            ))}
          </div>
        ) : null}
        <div className="mt-2 flex justify-end">
          <Button
            type="button"
            size="sm"
            variant={item.connected ? 'outline' : 'default'}
            onClick={() => onConnect(item.key)}
            disabled={actionLoading || Boolean(item.connected) || item.state === 'empty'}
          >
            {item.connected ? 'Уже подключено' : 'Подключить'}
          </Button>
        </div>
      </div>
    )) : (
      <div className="rounded-lg border border-dashed border-slate-200 px-3 py-3 text-sm text-slate-500">
        Каталог появится после выбора агента.
      </div>
    )}
  </div>
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

const VersionSummary = ({
  versions,
  latestVersionNumber,
  activeVersionId,
  onStartVersionRun,
  onActivateVersion,
  onRollbackVersion,
}: {
  versions: Array<Record<string, unknown>>;
  latestVersionNumber: number | null;
  activeVersionId: string;
  onStartVersionRun: (versionId: string) => void;
  onActivateVersion: (versionId: string) => void;
  onRollbackVersion: (versionId: string) => void;
}) => {
  const newestVersions = versions.slice(0, 5);
  return (
    <div className="rounded-xl border border-slate-200 bg-white px-3 py-3 text-sm leading-6 text-slate-700">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="font-semibold text-slate-950">Версия агента</div>
        <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700 ring-1 ring-emerald-200">
          {latestVersionNumber ? `Активна v${latestVersionNumber}` : 'Нет активной версии'}
        </span>
      </div>
      <div className="mt-1 text-xs text-slate-500">
        Новые запуски используют активную версию. Старые результаты остаются привязаны к версии, на которой были созданы.
      </div>
      {newestVersions.length ? (
        <div className="mt-3 space-y-2">
          {newestVersions.map((version) => {
            const versionNumber = getVersionNumber(version);
            const versionId = typeof version.id === 'string' ? version.id : '';
            const isActive = Boolean(version.is_active) || Boolean(versionId && versionId === activeVersionId);
            const summaryValue = version.diff_from_previous && typeof version.diff_from_previous === 'object' && 'summary' in version.diff_from_previous
              ? version.diff_from_previous.summary
              : '';
            const summary = typeof summaryValue === 'string' ? summaryValue : '';
            return (
              <div key={String(version.id || versionNumber || 'version')} className="rounded-lg bg-slate-50 px-2 py-2 text-xs text-slate-600">
                <div className="flex items-center justify-between gap-3">
                  <span className="font-medium text-slate-900">{versionNumber ? `v${versionNumber}` : 'версия'}</span>
                  <span>{isActive ? 'используется сейчас' : 'не активна'}</span>
                </div>
                {summary ? <div className="mt-1 text-slate-500">{summary}</div> : null}
                <div className="mt-2 flex flex-wrap gap-2">
                  <Button type="button" size="sm" variant="outline" onClick={() => onStartVersionRun(versionId)} disabled={!versionId}>
                    Запустить эту версию
                  </Button>
                  {!isActive ? (
                    <Button type="button" size="sm" variant="outline" onClick={() => onActivateVersion(versionId)} disabled={!versionId}>
                      Сделать активной
                    </Button>
                  ) : null}
                  {!isActive && versionNumber && latestVersionNumber && versionNumber < latestVersionNumber ? (
                    <Button type="button" size="sm" variant="outline" onClick={() => onRollbackVersion(versionId)} disabled={!versionId}>
                      Откатиться
                    </Button>
                  ) : null}
                </div>
              </div>
            );
          })}
        </div>
      ) : null}
    </div>
  );
};

const AgentRunReviewPanel = ({
  review,
  latestVersionNumber,
  feedbackText,
  feedbackVersionNotice,
  actionLoading,
  onFeedbackTextChange,
  onSubmitFeedback,
}: {
  review: AgentReview | null;
  latestVersionNumber: number | null;
  feedbackText: string;
  feedbackVersionNotice: FeedbackVersionNotice | null;
  actionLoading: boolean;
  onFeedbackTextChange: (value: string) => void;
  onSubmitFeedback: () => void;
}) => {
  const journal = review?.journal && review.journal.length ? review.journal : buildJournalFromSections(review?.sections || []);
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-slate-950">Журнал запуска</div>
          <div className="mt-1 text-xs text-slate-500">
            Входные данные, что агент извлёк, какие правила применил, результат и ручной контроль.
            {latestVersionNumber ? ` Следующий запуск пойдёт на v${latestVersionNumber}.` : ''}
          </div>
        </div>
        {review?.run_status ? <StatusBadge status={review.run_status} /> : null}
      </div>
      <div className="mb-4 grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(16rem,0.7fr)]">
        <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-3">
          <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Как настроен агент</div>
          <div className="mt-2 space-y-1 text-sm leading-6 text-slate-700">
            <div><span className="font-medium text-slate-950">Задача:</span> {String(review?.setup?.workflow_description || 'не задана')}</div>
            <div><span className="font-medium text-slate-950">Извлечь:</span> {String(review?.setup?.extraction_rules || 'не задано')}</div>
            <div><span className="font-medium text-slate-950">Правила:</span> {String(review?.setup?.processing_rules || 'не заданы')}</div>
            <div><span className="font-medium text-slate-950">Результат:</span> {String(review?.setup?.output_format || 'не задан')}</div>
          </div>
        </div>
        <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-3">
          <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Источники</div>
          <AgentSourcesList sources={review?.sources || []} />
        </div>
      </div>
      {journal.length ? (
        <div className="space-y-3">
          {journal.map((entry, index) => <JournalEntryCard key={`${entry.kind || 'entry'}-${entry.title || index}`} entry={entry} />)}
        </div>
      ) : (
        <DashboardEmptyState title="Журнал появится после запуска" description="Запустите агента, чтобы увидеть extraction, processing и output." />
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
      {feedbackVersionNotice ? (
        <div className="mt-3 rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-3 text-sm leading-6 text-emerald-900">
          <div className="font-semibold">
            Новая активная версия {feedbackVersionNotice.version_number ? `v${feedbackVersionNotice.version_number}` : 'агента'} готова
          </div>
          <div className="mt-1">Правка: {feedbackVersionNotice.feedback}</div>
          <div className="mt-1">Что изменится: следующие запуски будут учитывать эту правку в правилах результата.</div>
          <div className="mt-1 text-xs">{feedbackVersionNotice.next_run_note}</div>
        </div>
      ) : null}
    </div>
  );
};

const buildJournalFromSections = (sections: AgentReviewSection[]) => sections.map((section) => ({
  kind: humanizeMeta(section.artifact_type || 'artifact'),
  title: section.title || 'Результат',
  status: section.status || 'completed',
  summary: section.summary || '',
  details: [],
  payload: section.payload || {},
}));

const OutreachRunProgress = ({ review, activeRun }: { review: AgentReview | null; activeRun: AgentRun | null }) => {
  const journal = review?.journal && review.journal.length ? review.journal : [];
  const completedStepKeys = new Set((activeRun?.steps || []).filter((step) => step.status === 'completed').map((step) => step.step_key));
  const hasAnyStage = outreachProgressStages.some((stage) => journal.some((entry) => entry.kind === stage.kind));

  if (!activeRun && !hasAnyStage) {
    return null;
  }

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-slate-950">Путь outreach-агента</div>
          <div className="mt-1 text-sm leading-6 text-slate-600">
            Агент проходит этапы по порядку: лиды, shortlist, черновики и безопасная очередь.
          </div>
        </div>
        {activeRun?.status ? <StatusBadge status={activeRun.status} /> : null}
      </div>
      <div className="mt-4 grid gap-3 lg:grid-cols-4">
        {outreachProgressStages.map((stage) => {
          const entry = journal.find((item) => item.kind === stage.kind);
          const detailValue = findJournalDetailValue(entry, stage.detailLabel);
          const boundary = stage.kind === 'queue' ? findJournalDetailValue(entry, 'Внешняя отправка') : '';
          const isDone = Boolean(entry) || (
            stage.kind === 'sourcing' && completedStepKeys.has('source_leads')
          ) || (
            stage.kind === 'shortlist' && completedStepKeys.has('shortlist')
          ) || (
            stage.kind === 'drafts' && completedStepKeys.has('draft_messages')
          ) || (
            stage.kind === 'queue' && completedStepKeys.has('send_limited_batch')
          );
          const Icon = stage.icon;
          return (
            <div
              key={stage.kind}
              className={cn(
                'rounded-xl border px-3 py-3',
                isDone ? 'border-emerald-200 bg-emerald-50/60' : 'border-slate-200 bg-slate-50',
              )}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex min-w-0 items-center gap-2">
                  <span className={cn(
                    'flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ring-1',
                    isDone ? 'bg-white text-emerald-700 ring-emerald-200' : 'bg-white text-slate-500 ring-slate-200',
                  )}>
                    <Icon className="h-4 w-4" />
                  </span>
                  <div className="min-w-0">
                    <div className="text-sm font-semibold text-slate-950">{stage.title}</div>
                    <div className="mt-0.5 text-xs text-slate-500">{isDone ? 'готово' : 'ещё не выполнено'}</div>
                  </div>
                </div>
                {entry?.status ? <StatusBadge status={entry.status} /> : null}
              </div>
              <div className="mt-3 text-sm font-semibold text-slate-950">{detailValue || '0'}</div>
              {entry?.summary ? <div className="mt-1 line-clamp-2 text-xs leading-5 text-slate-600">{entry.summary}</div> : null}
              {boundary ? <div className="mt-2 rounded-lg bg-white px-2 py-1.5 text-xs font-medium text-amber-700 ring-1 ring-amber-200">{boundary}</div> : null}
            </div>
          );
        })}
      </div>
    </div>
  );
};

const findJournalDetailValue = (entry: AgentJournalEntry | undefined, label: string) => {
  if (!entry || !Array.isArray(entry.details)) {
    return '';
  }
  const detail = entry.details.find((item) => item.label === label);
  return detail?.value || '';
};

const JournalEntryCard = ({ entry }: { entry: AgentJournalEntry }) => {
  const payload = entry.payload || {};
  const details = Array.isArray(entry.details) ? entry.details : [];
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full bg-white px-2 py-1 text-xs font-medium text-slate-600 ring-1 ring-slate-200">
              {humanizeMeta(entry.kind || 'step')}
            </span>
            <div className="text-sm font-semibold text-slate-950">{entry.title || 'Шаг запуска'}</div>
          </div>
          {entry.summary ? <div className="mt-2 text-sm leading-6 text-slate-600">{entry.summary}</div> : null}
        </div>
        {entry.status ? <StatusBadge status={entry.status} /> : null}
      </div>
      {details.length ? (
        <div className="mt-3 grid gap-2 md:grid-cols-2">
          {details.map((detail) => (
            <div key={`${detail.label || ''}-${detail.value || ''}`} className="rounded-lg bg-white px-3 py-2 text-xs leading-5 ring-1 ring-slate-200">
              <div className="font-medium text-slate-950">{detail.label || 'Деталь'}</div>
              <div className="mt-1 text-slate-600">{detail.value || ''}</div>
            </div>
          ))}
        </div>
      ) : null}
      <HumanPayloadView payload={payload} />
      <details className="mt-3">
        <summary className="cursor-pointer text-xs font-medium text-slate-500 hover:text-slate-900">Технический журнал</summary>
        <pre className="mt-2 max-h-72 overflow-auto rounded-lg bg-slate-950 p-3 text-[11px] leading-5 text-slate-100">
          {JSON.stringify(payload, null, 2)}
        </pre>
      </details>
    </div>
  );
};

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
