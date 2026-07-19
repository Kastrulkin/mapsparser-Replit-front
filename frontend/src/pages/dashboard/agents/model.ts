import type {
  DashboardContext,
  AgentBlueprint,
  AgentVoicePersona,
  ProductAgentView,
  AgentApproval,
  AgentArtifact,
  AgentRunStep,
  AgentRunBillingAction,
  AgentRunObservability,
  AgentRun,
  AgentRunInputField,
  AgentRunInputSchema,
  AgentServerTodaySummary,
  AgentMetricsSummary,
  AgentBillingBreakdownItem,
  AgentUnifiedBillingLedger,
  AgentBlueprintDetails,
  AgentVersionDiff,
  AgentLearningLoop,
  AgentLearningEvent,
  AgentVersionEvent,
  AgentSource,
  AgentSourceCatalogItem,
  AgentIntegration,
  AgentExternalAuthOption,
  AgentIntegrationCatalogItem,
  AgentIntegrationBindingStatus,
  AgentIntegrationPreflight,
  AgentProviderAction,
  AgentProviderRoute,
  AgentConnectionPlanItem,
  AgentConnectionPlan,
  AgentConnectionDecision,
  AgentActivationGate,
  AgentActivationPathStep,
  AgentPostCreateHandoff,
  AgentReviewSection,
  AgentJournalEntry,
  AgentReview,
  AgentBuilderScenario,
  PersonaAgent,
  LegacyMigrationPlan,
  AgentWorkspaceMode,
  AgentTodaySummary,
  AgentAttentionItem,
  AgentBusinessStatus,
  EmployeeStatus,
  AgentExecutionMode,
  EmployeeNextActionKind,
  EmployeeWorkspaceState,
  AgentRegistryFilter,
  AgentRunAnimation,
  EmployeeNextAction,
  EmployeeTestResult,
  EmployeeResponsibility,
  AgentScenarioStep,
  AgentConfidenceFact,
  FeedbackVersionNotice,
  AgentBuilderMessage,
  AgentBuilderQuestion,
  AgentBuilderConnectorPreview,
  AgentBuilderFeasibility,
  AgentBuilderSetupStep,
  AgentBuilderSetupFlow,
  AgentBuilderPlannerLoop,
  AgentCompilerPolicyItem,
  AgentCompilerWorkflowDraft,
  AgentCompilerPolicyReview,
  AgentConnectorIntelligence,
  AgentConnectionSummary,
  AgentConnectionReadinessService,
  AgentConnectionReadiness,
  AgentConnectionResolverItem,
  AgentConnectionResolver,
  AgentServiceIntelligenceItem,
  AgentServiceIntelligence,
  AgentBuilderPreview,
  AgentBuilderSession
} from './types';

import {
  Database,
  FileCheck2,
  FileText,
  Mail,
  MessageSquareText,
  Search,
  Send,
  ShieldCheck,
  Sparkles,
  Star,
  Users,
  Wrench,
} from 'lucide-react';

import {
  getRequestErrorMessage,
  objectValue,
  recordValue,
  getBlueprintMetadata,
  getBlueprintBuilderPreview,
  normalizeSpreadsheetInput,
  normalizePostCreateHandoff,
  normalizeAgentIntegrationPreflight,
  normalizeConnectionPlan,
  normalizeConnectionPlanItem,
  normalizeProviderRoute,
  formatPreflightBlock,
  connectorLabel,
  userFacingAgentTechText,
  agentFlowStatusLabel,
  autoSelectBuilderConnectionBindings,
  autoSelectBuilderProviderRoutes,
  builderRouteIsUsable,
  builderRequiredProviderRouteKeys,
  bindingResolutionLabel,
  bindingUserFacingRole,
  bindingActionHint,
  connectionResourceFacts,
  isReadyConnectionAction,
  buildAgentConnectionDecision,
  buildBuilderCreationDecision,
  builderBlockingQuestions,
  activationBlockerText,
  buildActivationGateDecision,
  buildActivationPathSteps
} from './normalization';
import {
  buildConfidenceFacts,
  buildEmployeeAttentionItems,
  extractBusinessResultPayload,
  findPreparedResultPayload,
  isBusinessBlockerApproval,
  isBusinessBlockerPayload,
  resultPayloadStatus,
} from './results';

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

export const getVersionNumber = (version: Record<string, unknown> | undefined) => {
  const value = version?.version_number;
  return typeof value === 'number' ? value : null;
};

export const getLatestVersionNumber = (blueprint: AgentBlueprint, details?: AgentBlueprintDetails | null) => {
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

export const getActiveVersionNumber = (blueprint: AgentBlueprint, details?: AgentBlueprintDetails | null) => {
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
  return null;
};

export const getActiveVersionId = (blueprint: AgentBlueprint, details?: AgentBlueprintDetails | null) => {
  if (typeof details?.active_version_id === 'string' && details.active_version_id) {
    return details.active_version_id;
  }
  if (typeof blueprint.active_version_id === 'string' && blueprint.active_version_id) {
    return blueprint.active_version_id;
  }
  const active = (details?.versions || []).find((version) => version.is_active === true);
  return typeof active?.id === 'string' ? active.id : '';
};

export const getLatestVersionId = (blueprint: AgentBlueprint, details?: AgentBlueprintDetails | null) => {
  if (typeof blueprint.latest_version_id === 'string' && blueprint.latest_version_id) {
    return blueprint.latest_version_id;
  }
  const versions = details?.versions || [];
  const sorted = [...versions].sort((a, b) => (getVersionNumber(b) || 0) - (getVersionNumber(a) || 0));
  const latest = sorted[0];
  return typeof latest?.id === 'string' ? latest.id : '';
};

export const getRunnableVersionId = (blueprint: AgentBlueprint, details?: AgentBlueprintDetails | null) => (
  getActiveVersionId(blueprint, details) || getLatestVersionId(blueprint, details)
);

export const agentExecutionMode = (blueprint: AgentBlueprint, details?: AgentBlueprintDetails | null): AgentExecutionMode => (
  details?.execution_mode || blueprint.execution_mode || 'manual'
);

export const agentExecutionModeLabel = (mode: AgentExecutionMode) => ({
  one_off: 'Один раз',
  manual: 'По кнопке',
  scheduled: 'По расписанию',
}[mode]);

export const agentNextRunLabel = (blueprint: AgentBlueprint, details?: AgentBlueprintDetails | null) => {
  const nextRunAt = details?.next_run_at || blueprint.next_run_at;
  if (nextRunAt) {
    return formatShortDate(nextRunAt);
  }
  const mode = agentExecutionMode(blueprint, details);
  if (mode === 'manual') {
    return 'После запуска';
  }
  if (mode === 'one_off') {
    return (details?.lifecycle_state || blueprint.lifecycle_state) === 'completed' ? 'Задача выполнена' : 'После подтверждения';
  }
  return 'После включения';
};

export const businessResultPrimaryText = (result: Record<string, unknown>) => {
  const candidates = [result.draft_text, result.final_text, result.message_text, result.summary, result.title];
  const text = candidates.find((value) => typeof value === 'string' && value.trim());
  return typeof text === 'string' ? text : '';
};

export const estimatedAgentRunCredits = (
  details?: AgentBlueprintDetails | null,
  preview = false,
) => {
  const key = preview ? 'preview_run' : 'production_run';
  const items = details?.metrics?.unified_billing_ledger?.items
    || details?.metrics?.billing_breakdown?.items
    || details?.metrics?.cost_tokens?.breakdown
    || [];
  const item = items.find((entry) => entry.key === key);
  const explicitCredits = Number(item?.estimated_credits || 0);
  if (explicitCredits > 0) {
    return explicitCredits;
  }
  const estimatedTokens = Number(item?.estimated_tokens || 0);
  return estimatedTokens > 0 ? Math.max(1, Math.ceil(estimatedTokens / 1000)) : 0;
};

export const workflowStepsForAnimation = (
  details: AgentBlueprintDetails | null,
  kind: AgentRunAnimation['kind'],
) => {
  const contract = kind === 'test'
    ? details?.execution_contract?.candidate
    : details?.execution_contract?.active;
  const contractSteps = contract?.steps || [];
  if (contractSteps.length) {
    return contractSteps
      .filter((step) => !String(step.capability || '').match(/publish|send|dispatch/))
      .map((step) => userFacingAgentTechText(String(step.title || 'Выполняю шаг')));
  }
  const version = kind === 'test'
    ? details?.candidate_version || details?.active_version || details?.versions?.[0] || null
    : details?.active_version || details?.candidate_version || details?.versions?.[0] || null;
  const rawSteps = recordValue(version)?.steps_json;
  const steps = Array.isArray(rawSteps) ? rawSteps : [];
  const labels: string[] = [];
  const add = (label: string) => {
    if (label && !labels.includes(label)) {
      labels.push(label);
    }
  };
  steps.forEach((rawStep) => {
    const step = recordValue(rawStep);
    if (!step) {
      return;
    }
    const key = String(step.key || step.id || '').toLowerCase();
    const capability = String(step.capability || step.capability_key || '').toLowerCase();
    const title = String(step.title || step.label || '').trim();
    const external = capability.includes('publish') || capability.includes('send') || capability.includes('dispatch');
    if (external) {
      return;
    }
    if (capability === 'google_sheets.read_rows' || key.includes('google_sheet')) {
      add('Открываю Google Таблицу');
      add('Читаю строки');
    } else if (key.includes('select') || key.includes('filter') || key.includes('find')) {
      add('Выбираю нужные данные');
    } else if (capability.includes('content_plan') || key.includes('content_plan')) {
      add(kind === 'test' ? 'Проверяю сохранение результата' : 'Сохраняю результат');
    } else if (key.includes('draft') || key.includes('prepare') || key.includes('generate')) {
      add('Готовлю черновик');
    } else if (title) {
      add(userFacingAgentTechText(title));
    }
  });
  if (!labels.length) {
    add('Проверяю исходные данные');
    add('Выполняю задачу');
    add('Готовлю результат');
  }
  add(kind === 'test' ? 'Проверяю готовый результат' : 'Сохраняю результат');
  return labels.slice(0, 5);
};

export const getAgentVoiceName = (blueprint: AgentBlueprint, details?: AgentBlueprintDetails | null) => {
  const detailVoice = details?.active_version?.voice;
  if (typeof detailVoice === 'object' && detailVoice !== null) {
    const name = Reflect.get(detailVoice, 'name');
    if (typeof name === 'string') {
      return name;
    }
  }
  const voice = blueprint.voice || blueprint.persona || blueprint.product_agent?.voice || blueprint.product_agent?.persona;
  return voice?.name || '';
};

export const runStatusFilters = [
  { value: 'all', label: 'Все' },
  { value: 'running', label: 'В работе' },
  { value: 'waiting_approval', label: 'Ждёт решения' },
  { value: 'completed', label: 'Готово' },
  { value: 'failed', label: 'Ошибка' },
];

export const learningTriggerOptions = [
  { value: 'manual_edit', label: 'Ручная правка текста' },
  { value: 'approval_rejected', label: 'Отклонение' },
  { value: 'bad_outcome', label: 'Плохой результат' },
  { value: 'runtime_error', label: 'Ошибка' },
  { value: 'manual_feedback', label: 'Комментарий' },
];

export const agentPromptExamples = [
  'Каждый день собирай короткий отчёт по отзывам, новостям, услугам, партнёрствам и финансам и присылай владельцу в Telegram',
  'Если появился новый негативный отзыв, подготовь короткий ответ в стиле компании и пришли черновик владельцу в Telegram',
  'Раз в неделю подготовь 3 новости для карточек на основе услуг, отзывов, сезонности и текущих задач',
  'Проверь услуги: слабые названия, пустые описания, дубли и SEO-ключи. Подготовь список правок для проверки',
  'Найди или возьми из списка потенциальных партнёров, отсей нерелевантных и подготовь первое письмо и конкретное предложение',
  'Открывай сайт конкурента, проверяй изменения в ценах, акциях или меню и готовь короткий отчёт владельцу в Telegram',
  'Проверяй Google Sheets с заявками или заказами и присылай новые строки ответственному в Telegram',
  'Собирай повторяющиеся вопросы клиентов из WhatsApp и Telegram, группируй их и предлагай новые ответы для FAQ',
  'Читай таблицу расходов, нормализуй категории и подготовь предложения для Финансов LocalOS',
  'Каждый вечер проверяй записи на завтра: кто без предоплаты, где есть риск отмены и кому нужен ручной follow-up',
];

export const agentScenarios: AgentBuilderScenario[] = [
  {
    category: 'communications',
    title: 'Коммуникации',
    description: 'Напоминания, follow-up, возврат клиентов, пакетные предложения и ответы на входящие.',
    prompt: 'Сделай агента, который напоминает клиентам о записи и сообщает про пакетное предложение',
    dataSources: 'записи, услуги, пакеты, профиль бизнеса, история коммуникаций',
    extraction: 'триггер, аудитория, согласие, релевантная услуга, канал и лимиты частоты',
    processing: 'подготовить черновики, проверить согласие, поставить отправку только после ручного подтверждения',
    output: 'черновики, отчёт доставки и журнал outcomes',
    manualControl: 'первый запуск, шаблон и каждая массовая отправка подтверждаются человеком',
    icon: MessageSquareText,
  },
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
    processing: 'не отправлять без ручного подтверждения, ограничить объём, сохранять источник лида',
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

export const statusTone: Record<string, string> = {
  active: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  connected: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  ready: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  completed: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  running: 'bg-sky-50 text-sky-700 ring-sky-200',
  waiting_approval: 'bg-amber-50 text-amber-700 ring-amber-200',
  needs_approval: 'bg-amber-50 text-amber-700 ring-amber-200',
  failed: 'bg-rose-50 text-rose-700 ring-rose-200',
  error: 'bg-rose-50 text-rose-700 ring-rose-200',
  rejected: 'bg-slate-100 text-slate-700 ring-slate-200',
  draft: 'bg-slate-100 text-slate-700 ring-slate-200',
  paused: 'bg-slate-100 text-slate-700 ring-slate-200',
  queued_for_dispatch: 'bg-amber-50 text-amber-700 ring-amber-200',
  pending: 'bg-amber-50 text-amber-700 ring-amber-200',
  needs_connection: 'bg-amber-50 text-amber-700 ring-amber-200',
  needs_choice: 'bg-amber-50 text-amber-700 ring-amber-200',
  needs_clarification: 'bg-amber-50 text-amber-700 ring-amber-200',
  blocked: 'bg-rose-50 text-rose-700 ring-rose-200',
};

export const statusLabels: Record<string, string> = {
  active: 'Включён',
  connected: 'Готово',
  ready: 'Готово',
  completed: 'Готово',
  running: 'В работе',
  waiting_approval: 'Ждёт решения',
  needs_approval: 'Нужно решение',
  failed: 'Ошибка',
  error: 'Ошибка',
  rejected: 'Отклонён',
  draft: 'Черновик',
  paused: 'Пауза',
  queued_for_dispatch: 'В очереди',
  queued_not_dispatched: 'В очереди',
  generated: 'Подготовлено',
  approved: 'Подтверждено',
  pending: 'Ожидает',
  needs_connection: 'Подключить',
  needs_choice: 'Выбрать',
  needs_clarification: 'Уточнить',
  blocked: 'Блокер',
};

export const stepLabels: Record<string, string> = {
  source_leads: 'Найти потенциальных клиентов',
  shortlist: 'Сформировать список',
  approve_shortlist: 'Подтвердить список',
  draft_messages: 'Подготовить сообщения',
  approve_drafts: 'Подтвердить тексты',
  send_limited_batch: 'Поставить в очередь',
  record_outcomes: 'Сохранить ответы',
};

export const metaLabels: Record<string, string> = {
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
  appointments: 'записи',
  packages: 'пакеты',
  services: 'услуги',
  reviews: 'отзывы',
  external_reviews: 'отзывы',
  business_cards: 'карточки',
  photos: 'фотографии',
  competitors: 'конкуренты',
  clients: 'клиенты',
  locations: 'точки сети',
  customer_questions: 'вопросы клиентов',
  customer_messages: 'сообщения клиентов',
  localos_tasks: 'задачи LocalOS',
  team: 'команда',
  whatsapp: 'WhatsApp',
  seasonality: 'сезонность',
  posts: 'посты',
  schedule: 'расписание',
  inventory: 'остатки',
  products: 'товары',
  supplies: 'расходники',
  staff_schedule: 'расписание смен',
  customer_chats: 'чаты с клиентами',
  staff_profiles: 'профили сотрудников',
  price_list: 'прайс',
  revenue: 'выручка',
  map_questions: 'вопросы в карточках',
  location_descriptions: 'описания филиалов',
  localos_digest: 'дайджест LocalOS',
  prospectingleads: 'кандидаты',
  outreach_drafts: 'черновики сообщений партнёрам',
  uploaded_documents: 'документы',
  uploaded_tables: 'таблицы',
  manual_context: 'ручной контекст',
  goal: 'цель',
  inputs_schema: 'входные данные',
  steps: 'шаги',
  persona_agent_id: 'голос агента',
  capability_allowlist: 'разрешённые действия',
  approval_policy: 'ручной контроль',
  output_schema: 'формат результата',
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
  communications: 'коммуникации',
  documents: 'документы',
  tables: 'таблицы',
  outreach: 'outreach',
  services_optimize: 'услуги',
  telegram: 'Telegram',
  google_sheets: 'Google Sheets',
  google_sheets_read: 'чтение Google Sheets',
  google_sheets_append: 'запись в Google Sheets',
  localos_finance: 'финансы LocalOS',
  maton: 'Maton.ai',
  composio: 'Composio',
  trigger_boundary: 'граница запуска',
  approved_executor: 'исполнитель после подтверждения',
  approved_delivery_bridge: 'доставка после подтверждения',
  approved_localos_write: 'запись в LocalOS после подтверждения',
  'telegram.message.received': 'новое сообщение в Telegram',
  'google_sheets.append': 'запись строки в Google Sheets',
  'outreach.send_batch': 'отправка согласованной пачки',
  'reviews.reply.draft': 'черновик ответа на отзыв',
  'reviews.reply.publish_request': 'запрос на публикацию ответа',
  'services.optimize': 'оптимизация услуг',
  'news.generate': 'подготовка новости',
  'appointments.read': 'чтение записей',
  'appointments.create_request': 'запрос на создание записи',
  'communications.draft': 'черновик сообщения',
  'communications.send_reminder': 'напоминание клиенту',
  'communications.send_offer': 'предложение клиенту',
  'support.export': 'выгрузка для поддержки',
  'billing.reserve': 'резерв токенов',
  'billing.settle': 'списание токенов',
  not_applicable: 'не применимо',
};

export const resultFieldLabels: Record<string, string> = {
  title: 'Название результата',
  summary: 'Краткий вывод',
  risks: 'Риски',
  facts: 'Факты',
  fields: 'Поля',
  next_questions: 'Что уточнить',
  subject: 'Тема письма',
  body: 'Текст письма',
  post_text: 'Текст поста',
  draft_text: 'Черновик сообщения',
  message: 'Сообщение',
  text: 'Текст',
  checklist: 'Проверить перед использованием',
  exceptions: 'Исключения',
  rows_to_review: 'Строки к проверке',
  recommendations: 'Рекомендации',
  reply_drafts: 'Черновики ответов',
  manual_review_reasons: 'Почему нужен ручной контроль',
  manual_review_reason: 'Почему нужен ручной контроль',
  rules_applied: 'Применённые правила',
  provenance: 'Источники',
  delivery_state: 'Отправка',
  publish_state: 'Публикация',
  preparation_method: 'Как подготовлено',
};

export const outreachProgressStages = [
  { kind: 'sourcing', title: 'Нашёл лидов', detailLabel: 'Найдено лидов', icon: Search },
  { kind: 'shortlist', title: 'Собрал shortlist', detailLabel: 'Лидов в shortlist', icon: Users },
  { kind: 'drafts', title: 'Подготовил черновики', detailLabel: 'Черновиков', icon: MessageSquareText },
  { kind: 'queue', title: 'Поставил в очередь', detailLabel: 'В очереди', icon: Send },
];

export const genericRunStages = [
  { kind: 'input', title: 'Входные данные', description: 'Что агент получил на вход', icon: Database },
  { kind: 'extraction', title: 'Что понял', description: 'Что извлёк из источников', icon: Search },
  { kind: 'output', title: 'Результат', description: 'Что подготовил для проверки', icon: FileCheck2 },
  { kind: 'approval', title: 'Ручной контроль', description: 'Что требует решения человека', icon: ShieldCheck },
];

export const humanizeStatus = (status: string) => statusLabels[status] || status;
export const humanizeStep = (step: string) => stepLabels[step] || step;
export const humanizeMeta = (meta: string) => metaLabels[meta] || meta;
export const humanizeCategory = (category?: string) => ({
  communications: 'Коммуникации',
  outreach: 'Поиск клиентов',
  documents: 'Документы',
  email: 'Письма',
  tables: 'Таблицы',
  reviews: 'Отзывы',
  partnerships: 'Партнёрства',
  services: 'Услуги',
  booking: 'Бронирование',
  custom: 'Кастомная задача',
}[category || 'custom'] || category || 'Кастомная задача');

export const explainApproval = (approval?: AgentApproval | null) => {
  const approvalType = approval?.approval_type || '';
  const payload = approval?.payload_json || {};
  const draftCount = Array.isArray(payload.draft_ids) ? payload.draft_ids.length : typeof payload.count === 'number' ? payload.count : 0;
  if (approvalType === 'external_delivery' || approvalType === 'send_batch') {
    return draftCount
      ? `Агент подготовил ${draftCount} внешних отправок. Нужно подтвердить batch перед любым сообщением клиентам.`
      : 'Агент дошёл до внешнего действия. Нужен human gate перед отправкой.';
  }
  if (approvalType === 'final_output') {
    return 'Агент подготовил результат, но не использует его дальше без проверки человеком.';
  }
  if (approvalType === 'shortlist') {
    return 'Агент собрал shortlist. Нужно проверить, кого брать в работу дальше.';
  }
  if (approvalType === 'drafts') {
    return 'Агент подготовил черновики. Нужно проверить текст, тон и ограничения перед следующим шагом.';
  }
  return 'Агент остановился на безопасной границе и ждёт решение человека.';
};

export const approvalActionLabels = (approval?: AgentApproval | null) => {
  const approvalType = approval?.approval_type || '';
  if (approvalType === 'external_delivery' || approvalType === 'send_batch') {
    return {
      approve: 'Подтвердить отправку',
      reject: 'Не отправлять',
    };
  }
  if (approvalType === 'final_output') {
    return {
      approve: 'Разрешить выполнение',
      reject: 'Не использовать',
    };
  }
  if (approvalType === 'shortlist') {
    return {
      approve: 'Утвердить список',
      reject: 'Отклонить список',
    };
  }
  if (approvalType === 'drafts') {
    return {
      approve: 'Подтвердить публикацию',
      reject: 'Отклонить результат',
    };
  }
  return {
    approve: 'Разрешить выполнение',
    reject: 'Не использовать',
  };
};

export const getApprovalPreviewItems = (approval?: AgentApproval | null) => {
  const payload = approval?.payload_json || {};
  const items: Array<{ label: string; value: string }> = [];
  const addValue = (label: string, value: unknown) => {
    const text = userFacingAgentTechText(formatPayloadValue(value)).trim();
    if (text && !items.some((item) => item.label === label && item.value === text)) {
      items.push({ label, value: text });
    }
  };
  const preparedResult = extractBusinessResultPayload(payload);
  addValue('Что подготовил агент', payload.summary || payload.result_summary || payload.output_summary || payload.message_summary || payload.title);
  addValue('Черновик / результат', payload.draft_text || payload.reply || payload.message || payload.text || payload.output || preparedResult || payload.result);
  addValue('Что будет дальше', payload.next_step || payload.action || payload.delivery_state || payload.publish_state);
  if (Array.isArray(payload.reply_drafts) && payload.reply_drafts.length) {
    addValue('Черновики ответов', payload.reply_drafts);
  }
  if (Array.isArray(payload.drafts) && payload.drafts.length) {
    addValue('Черновики', payload.drafts);
  }
  if (Array.isArray(payload.items) && payload.items.length) {
    addValue('Элементы', payload.items);
  }
  if (Array.isArray(payload.manual_review_reasons) && payload.manual_review_reasons.length) {
    addValue('Почему нужна проверка', payload.manual_review_reasons);
  }
  return items.slice(0, 4);
};

export const approvalDecisionTitle = (approval?: AgentApproval | null) => {
  const approvalType = approval?.approval_type || '';
  if (approvalType === 'external_delivery' || approvalType === 'send_batch') {
    return 'Разрешить внешнюю отправку?';
  }
  if (approvalType === 'final_output') {
    return 'Можно использовать подготовленный результат?';
  }
  if (approvalType === 'shortlist') {
    return 'Утвердить список для дальнейшей работы?';
  }
  if (approvalType === 'drafts') {
    return 'Утвердить черновики?';
  }
  return 'Можно использовать текущий результат агента?';
};

export const getAgentListStatus = (blueprint: AgentBlueprint) => {
  if (Number(blueprint.pending_approvals_count || 0) > 0 || blueprint.last_run_status === 'waiting_approval') {
    return 'needs_approval';
  }
  if (blueprint.last_run_status === 'failed' || blueprint.status === 'error') {
    return 'error';
  }
  return blueprint.status || 'draft';
};

export const formatShortDate = (value?: string | null) => {
  if (!value) {
    return '';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
};

export const formatLastRun = (blueprint: AgentBlueprint) => {
  if (!blueprint.last_run_id) {
    return 'запусков ещё не было';
  }
  const date = formatShortDate(blueprint.last_run_started_at || blueprint.last_run_completed_at);
  return `${humanizeStatus(blueprint.last_run_status || 'running')}${date ? ` · ${date}` : ''}`;
};

export const isWithinLastDay = (value?: string | null) => {
  if (!value) {
    return false;
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return false;
  }
  return Date.now() - date.getTime() <= 24 * 60 * 60 * 1000;
};

export const buildTodaySummary = (
  blueprints: AgentBlueprint[],
  detailsById: Record<string, AgentBlueprintDetails>,
): AgentTodaySummary => {
  const detailValues = Object.values(detailsById);
  const runs = detailValues.flatMap((details) => details.runs || []);
  const todayRuns = runs.filter((run) => run.status !== 'superseded' && isWithinLastDay(run.completed_at || run.started_at));
  const todayApprovals = detailValues
    .flatMap((details) => details.approval_queue || [])
    .filter((approval) => isWithinLastDay(approval.requested_at || approval.run_started_at) && !isBusinessBlockerApproval(approval));
  const artifacts = detailValues.flatMap((details) => {
    const recentRuns = (details.runs || []).filter((run) => run.status !== 'superseded' && isWithinLastDay(run.completed_at || run.started_at));
    return recentRuns.flatMap((run) => run.artifacts || []);
  });
  const listFallbackRuns = blueprints.filter((blueprint) => isWithinLastDay(blueprint.last_run_completed_at || blueprint.last_run_started_at));
  const completedRuns = todayRuns.filter((run) => run.status === 'completed').length || listFallbackRuns.filter((item) => item.last_run_status === 'completed').length;
  const failedRuns = todayRuns.filter((run) => run.status === 'failed').length || listFallbackRuns.filter((item) => item.last_run_status === 'failed').length;
  const preparedArtifacts = artifacts.length || todayRuns.reduce((sum, run) => sum + Number(run.observability?.artifacts?.count || 0), 0);
  const pendingApprovals = todayApprovals.length;
  const latestEvent = todayRuns[0]?.completed_at || todayRuns[0]?.started_at || listFallbackRuns[0]?.last_run_completed_at || listFallbackRuns[0]?.last_run_started_at || '';
  return {
    completedRuns,
    preparedArtifacts,
    pendingApprovals,
    failedRuns,
    latestEvent: latestEvent ? formatShortDate(latestEvent) : '',
    empty: completedRuns + preparedArtifacts + pendingApprovals + failedRuns === 0,
  };
};

export const initialRunParameters = (
  schema: AgentRunInputSchema | undefined,
  previousInput?: Record<string, unknown>,
) => {
  const values: Record<string, unknown> = {};
  Object.entries(schema?.properties || {}).forEach(([key, field]) => {
    const previous = previousInput?.[key];
    const candidate = previous !== undefined ? previous : field.default;
    if (candidate === undefined || candidate === null) {
      return;
    }
    if (field.format === 'date' && typeof candidate === 'string') {
      const today = new Date();
      today.setHours(0, 0, 0, 0);
      const parsed = new Date(`${candidate}T00:00:00`);
      if (!Number.isNaN(parsed.getTime()) && parsed < today) {
        return;
      }
    }
    values[key] = candidate;
  });
  return values;
};

export const validateRunParameters = (
  schema: AgentRunInputSchema | undefined,
  values: Record<string, unknown>,
) => {
  const errors: Record<string, string> = {};
  (schema?.required || []).forEach((key) => {
    const value = values[key];
    if (value === undefined || value === null || value === '' || (Array.isArray(value) && value.length === 0)) {
      errors[key] = 'Заполните обязательное поле.';
    }
  });
  Object.entries(schema?.properties || {}).forEach(([key, field]) => {
    const value = values[key];
    if (field.format === 'date' && typeof value === 'string' && value) {
      const parsed = new Date(`${value}T00:00:00`);
      if (Number.isNaN(parsed.getTime())) {
        errors[key] = 'Укажите корректную дату.';
      }
    }
  });
  return errors;
};

export const buildAgentBusinessStatus = (
  blueprint: AgentBlueprint,
  details?: AgentBlueprintDetails | null,
): AgentBusinessStatus => {
  const activationGate = details?.activation_gate;
  const missingConnections = Number(activationGate?.preflight?.missing_count || 0);
  const previewReady = activationGate?.preview_run_status?.ready === true;
  const hasActiveVersion = Boolean(details?.active_version_id || blueprint.active_version_id || blueprint.active_version_number);
  const latestResult = findPreparedResultPayload(details?.runs?.[0] || null);
  if (isBusinessBlockerPayload(latestResult)) {
    return {
      status: 'needs_check',
      label: 'Нужно проверить',
      tone: 'warning',
      primaryLabel: resultPayloadStatus(latestResult) === 'needs_google_access' ? 'Починить Google' : 'Посмотреть',
      lastResult: 'Последний результат требует следующего шага',
      nextRun: 'после исправления',
    };
  }
  if (Number(blueprint.pending_approvals_count || 0) > 0 || blueprint.last_run_status === 'waiting_approval') {
    return {
      status: 'needs_approval',
      label: 'Ждёт решения',
      tone: 'warning',
      primaryLabel: 'Посмотреть',
      lastResult: 'Есть задача на ручное решение',
      nextRun: 'после решения',
    };
  }
  if (blueprint.last_run_status === 'failed' || blueprint.status === 'error') {
    return {
      status: 'error',
      label: 'Ошибка',
      tone: 'error',
      primaryLabel: 'Открыть результат',
      lastResult: 'Последний запуск завершился ошибкой',
      nextRun: 'после проверки',
    };
  }
  if (missingConnections > 0) {
    return {
      status: 'needs_connection',
      label: 'Нужны данные',
      tone: 'warning',
      primaryLabel: 'Подключить',
      lastResult: `${missingConnections} ${missingConnections === 1 ? 'доступ требует' : 'доступа требуют'} внимания`,
      nextRun: 'после подключения',
    };
  }
  if (!previewReady && hasActiveVersion) {
    return {
      status: 'needs_check',
      label: 'Нужно проверить',
      tone: 'warning',
      primaryLabel: 'Проверить',
      lastResult: formatLastRun(blueprint),
      nextRun: 'после теста',
    };
  }
  if (blueprint.status === 'draft' && !hasActiveVersion) {
    return {
      status: 'draft',
      label: 'Черновик',
      tone: 'draft',
      primaryLabel: 'Открыть',
      lastResult: 'Рабочая версия ещё не включена',
      nextRun: 'после включения',
    };
  }
  return {
    status: 'active',
    label: 'Работает',
    tone: 'ready',
    primaryLabel: 'Проверить',
    lastResult: formatLastRun(blueprint),
    nextRun: blueprint.active_version_number ? 'по сценарию агента' : 'после проверки',
  };
};

export const buildEmployeeDescription = (
  blueprint: AgentBlueprint,
  details?: AgentBlueprintDetails | null,
) => {
  const preview = getBlueprintBuilderPreview(details?.blueprint || blueprint);
  return preview?.understood_task
    || blueprint.description
    || blueprint.active_goal
    || blueprint.latest_goal
    || 'Выполняет поручение, которое вы описали при создании.';
};

export const buildEmployeeStatus = (
  blueprint: AgentBlueprint,
  details?: AgentBlueprintDetails | null,
  pendingApproval?: AgentApproval | null,
): EmployeeStatus => {
  const workspaceState = buildEmployeeWorkspaceState(blueprint, details, pendingApproval);
  if (workspaceState === 'blocked_result') {
    return {
      label: 'Нужно проверить',
      tone: 'amber',
      summary: 'Сотрудник не получил данные из источника. Нужно исправить доступ или запустить тест заново.',
    };
  }
  if (workspaceState === 'waiting_for_review') {
    return {
      label: 'Ждёт решения',
      tone: 'amber',
      summary: 'Сотрудник подготовил результат и остановился, чтобы вы его проверили.',
    };
  }
  if (workspaceState === 'error') {
    return {
      label: 'Ошибка',
      tone: 'rose',
      summary: 'Последняя работа остановилась. Нужна проверка результата.',
    };
  }
  if (workspaceState === 'needs_connection') {
    const missingConnections = Number(details?.activation_gate?.preflight?.missing_count || 0);
    return {
      label: 'Нужны данные',
      tone: 'amber',
      summary: `${missingConnections || 1} ${missingConnections === 1 ? 'подключение нужно завершить' : 'подключения нужно завершить'}.`,
    };
  }
  if (workspaceState === 'needs_mode') {
    return {
      label: 'Нужно проверить',
      tone: 'amber',
      summary: 'Выберите, как должен запускаться агент: один раз, по кнопке или по расписанию.',
    };
  }
  if (workspaceState === 'completed') {
    return {
      label: 'Выполнено',
      tone: 'emerald',
      summary: 'Разовая задача выполнена. Результат сохранён в истории.',
    };
  }
  if (workspaceState === 'draft') {
    return {
      label: 'Черновик',
      tone: 'slate',
      summary: 'Сотрудник создан, но ещё не включён в работу.',
    };
  }
  if (workspaceState === 'ready_for_test' || workspaceState === 'needs_attention') {
    return {
      label: 'Нужно проверить',
      tone: 'amber',
      summary: 'Перед включением нужен безопасный тест без внешних действий.',
    };
  }
  if (workspaceState === 'running_test') {
    return {
      label: 'Нужно проверить',
      tone: 'amber',
      summary: 'Сотрудник выполняет тестовую проверку.',
    };
  }
  return {
    label: 'Работает',
    tone: 'emerald',
    summary: 'Сотрудник готов работать по опубликованному сценарию.',
  };
};

export const buildEmployeeWorkspaceState = (
  blueprint: AgentBlueprint,
  details?: AgentBlueprintDetails | null,
  pendingApproval?: AgentApproval | null,
): EmployeeWorkspaceState => {
  if (details?.execution_mode_confirmation_required || blueprint.execution_mode_confirmation_required) {
    return 'needs_mode';
  }
  if ((details?.lifecycle_state || blueprint.lifecycle_state) === 'completed') {
    return 'completed';
  }
  const gate = details?.activation_gate;
  const missingConnections = Number(gate?.preflight?.missing_count || 0);
  const hasActiveVersion = Boolean(details?.active_version_id || blueprint.active_version_id || blueprint.active_version_number);
  const hasCandidateVersion = Boolean(details?.candidate_version_id || blueprint.latest_version_id || blueprint.latest_version_number);
  const latestRun = details?.runs?.[0] || null;
  const latestResult = findPreparedResultPayload(latestRun, pendingApproval);
  if (isBusinessBlockerPayload(latestResult)) {
    return 'blocked_result';
  }
  const hasPendingApproval = Boolean(pendingApproval || blueprint.pending_approvals_count || blueprint.last_run_status === 'waiting_approval');
  if (hasPendingApproval) {
    return 'waiting_for_review';
  }
  if (blueprint.last_run_status === 'running') {
    return 'running_test';
  }
  if (blueprint.last_run_status === 'failed' || blueprint.status === 'error') {
    return 'error';
  }
  if (missingConnections > 0) {
    return 'needs_connection';
  }
  if (gate?.preview_run_status?.ready === false) {
    return 'ready_for_test';
  }
  if (!hasActiveVersion && hasCandidateVersion && (gate?.can_activate === true || gate?.next_step === 'configure_schedule')) {
    return 'needs_attention';
  }
  if (!hasActiveVersion || blueprint.status === 'draft') {
    return 'draft';
  }
  return 'working';
};

export const buildEmployeeLastActivity = (
  blueprint: AgentBlueprint,
  details?: AgentBlueprintDetails | null,
  pendingApproval?: AgentApproval | null,
) => {
  const latestRun = details?.runs?.[0];
  if (latestRun) {
    const time = formatShortDate(latestRun.completed_at || latestRun.started_at);
    if (isBusinessBlockerPayload(findPreparedResultPayload(latestRun, pendingApproval))) {
      return `Остановился: нужен следующий шаг${time ? ` · ${time}` : ''}`;
    }
    if (latestRun.status === 'completed') {
      return `Завершил работу${time ? ` · ${time}` : ''}`;
    }
    if (latestRun.status === 'waiting_approval') {
      return `Подготовил результат и ждёт решения${time ? ` · ${time}` : ''}`;
    }
    if (latestRun.status === 'failed') {
      return `Остановился с ошибкой${time ? ` · ${time}` : ''}`;
    }
    return `${humanizeStatus(latestRun.status)}${time ? ` · ${time}` : ''}`;
  }
  return formatLastRun(blueprint);
};

export const buildEmployeeNextAction = ({
  blueprint,
  details,
  pendingApproval,
  googleAccessFreshAfterResult = false,
}: {
  blueprint: AgentBlueprint;
  details?: AgentBlueprintDetails | null;
  pendingApproval?: AgentApproval | null;
  googleAccessFreshAfterResult?: boolean;
}): EmployeeNextAction => {
  return buildEmployeePrimaryAction({ blueprint, details, pendingApproval, googleAccessFreshAfterResult });
};

export const getMissingConnectorLabel = (
  details?: AgentBlueprintDetails | null,
) => {
  const gate = details?.activation_gate;
  const missing = gate?.preflight?.missing?.[0] || gate?.preflight?.items?.find((item) => item.status !== 'ready' && item.status !== 'connected');
  const provider = missing?.provider || gate?.connection_plan?.items?.find((item) => item.binding_status !== 'ready')?.provider || '';
  return connectorLabel(provider || 'service');
};

export const buildEmployeePrimaryAction = ({
  blueprint,
  details,
  pendingApproval,
  googleAccessFreshAfterResult = false,
}: {
  blueprint: AgentBlueprint;
  details?: AgentBlueprintDetails | null;
  pendingApproval?: AgentApproval | null;
  googleAccessFreshAfterResult?: boolean;
}): EmployeeNextAction => {
  const state = buildEmployeeWorkspaceState(blueprint, details, pendingApproval);
  const gate = details?.activation_gate;
  const activationVersionId = gate?.active_version_id || details?.active_version_id || blueprint.active_version_id || '';
  const latestResult = findPreparedResultPayload(details?.runs?.[0] || null, pendingApproval);
  const userMode = buildAgentUserMode(blueprint, details);
  if (state === 'needs_mode') {
    return {
      kind: 'confirm_mode',
      label: 'Выбрать тип запуска',
      description: 'Подтвердите, будет это разовая задача, запуск по кнопке или работа по расписанию.',
      targetMode: 'settings',
    };
  }
  if (state === 'completed') {
    return {
      kind: 'run_work',
      label: 'Запустить ещё раз',
      description: 'Агент ещё раз выполнит ту же задачу и сохранит новый результат в своей истории.',
      targetMode: 'results',
      versionId: details?.active_version_id || details?.candidate_version_id || blueprint.active_version_id || blueprint.latest_version_id || '',
      secondaryAction: 'clone_agent',
    };
  }
  if (state === 'blocked_result') {
    if (resultPayloadStatus(latestResult) === 'needs_google_access') {
      if (googleAccessFreshAfterResult) {
        return {
          kind: 'run_test',
          label: 'Запустить тест',
          description: 'Google-доступ обновлён. Запустите тест ещё раз, чтобы проверить таблицу на свежем доступе.',
          targetMode: 'results',
        };
      }
      return {
        kind: 'open_result',
        label: 'Починить Google-доступ',
        description: 'Google не дал строки таблицы. Откройте результат, переподключите доступ или запустите тест после подключения.',
        targetMode: 'results',
      };
    }
    if (resultPayloadStatus(latestResult) === 'needs_sheet_tab') {
      return {
        kind: 'open_result',
        label: 'Указать лист таблицы',
        description: 'Google-доступ работает, но лист таблицы не найден. Откройте результат и укажите правильный лист.',
        targetMode: 'results',
      };
    }
    return {
      kind: 'open_result',
      label: 'Разобрать результат',
      description: 'Сотрудник остановился до готового результата. Откройте причину и исправьте следующий шаг.',
      targetMode: 'results',
    };
  }
  if (state === 'waiting_for_review') {
    return {
      kind: 'approve',
      label: approvalActionLabels(pendingApproval).approve,
      description: 'Проверьте подготовленный результат и решите, можно ли использовать его дальше.',
      targetMode: 'results',
    };
  }
  if (state === 'needs_connection') {
    const label = getMissingConnectorLabel(details);
    return {
      kind: 'connect',
      label: `Подключить ${label}`,
      description: 'Завершите одно недостающее подключение, чтобы сотрудник получил нужные данные.',
      targetMode: 'connections',
    };
  }
  if (state === 'error') {
    return {
      kind: 'open_result',
      label: 'Разобрать проблему',
      description: 'Посмотрите последний бизнес-результат и причину остановки.',
      targetMode: 'results',
    };
  }
  if (state === 'ready_for_test') {
    return {
      kind: 'run_test',
      label: 'Запустить тест',
      description: 'Запустите безопасную проверку новой версии без публикаций и внешних отправок.',
      targetMode: 'results',
    };
  }
  if (state === 'draft') {
    if (latestResult || blueprint.last_run_status === 'completed' || details?.runs?.[0]?.status === 'completed') {
      return {
        kind: 'open_result',
        label: 'Открыть последний результат',
        description: 'Откройте последний подготовленный результат сотрудника.',
        targetMode: 'results',
      };
    }
    return {
      kind: 'run_test',
      label: 'Запустить тест',
      description: 'Запустите безопасную проверку без публикаций и внешних отправок.',
      targetMode: 'results',
    };
  }
  if (state === 'running_test') {
    return {
      kind: 'view_history',
      label: 'Проверка идёт',
      description: 'Сотрудник выполняет тест. Дождитесь результата.',
      targetMode: 'results',
    };
  }
  if (state === 'needs_attention' && activationVersionId) {
    if (userMode.mode === 'one_off') {
      return {
        kind: 'run_work',
        label: 'Выполнить задачу',
        description: 'Тест пройден. Выполните задачу и сохраните рабочий результат.',
        targetMode: 'results',
        versionId: activationVersionId,
      };
    }
    if (gate?.next_step === 'configure_schedule') {
      return {
        kind: 'configure_schedule',
        label: 'Настроить расписание',
        description: 'Укажите время и часовой пояс, затем включите агента.',
        targetMode: 'advanced',
        versionId: activationVersionId,
      };
    }
    return {
      kind: 'enable',
      label: userMode.mode === 'scheduled' ? 'Включить по расписанию' : 'Включить агента',
      description: 'Включите сотрудника после успешной проверки результата.',
      targetMode: 'overview',
      versionId: activationVersionId,
    };
  }
  if (state === 'working' && userMode.mode === 'manual') {
    return {
      kind: 'run_work',
      label: 'Запустить работу',
      description: 'Агент выполнит опубликованный сценарий и сохранит новый результат.',
      targetMode: 'results',
      versionId: details?.active_version_id || blueprint.active_version_id || '',
    };
  }
  return {
    kind: 'view_history',
    label: 'Открыть последний результат',
    description: 'Сотрудник работает. Можно открыть последний сохранённый результат.',
    targetMode: 'results',
  };
};

export const pushUniqueResponsibility = (
  items: EmployeeResponsibility[],
  label: string,
  done = true,
) => {
  const normalized = label.trim();
  if (!normalized || items.some((item) => item.label.toLowerCase() === normalized.toLowerCase())) {
    return;
  }
  items.push({
    key: `${items.length}-${normalized.toLowerCase().replace(/[^a-zа-я0-9]+/gi, '-')}`,
    label: normalized,
    done,
  });
};

export const buildEmployeeResponsibilities = (
  blueprint: AgentBlueprint,
  details?: AgentBlueprintDetails | null,
): EmployeeResponsibility[] => {
  const contract = details?.execution_contract?.active || details?.execution_contract?.candidate;
  if (contract?.steps?.length) {
    return contract.steps.slice(0, 6).map((step, index) => ({
      key: String(step.key || `step-${index + 1}`),
      label: userFacingAgentTechText(String(step.title || `Шаг ${index + 1}`)),
      done: true,
    }));
  }
  const preview = getBlueprintBuilderPreview(details?.blueprint || blueprint);
  const text = [
    blueprint.name,
    blueprint.category,
    blueprint.description,
    blueprint.active_goal,
    blueprint.latest_goal,
    preview?.understood_task,
    ...(preview?.data_sources || []),
  ].filter(Boolean).join(' ').toLowerCase();
  const items: EmployeeResponsibility[] = [];
  if (text.includes('google sheet') || text.includes('таблиц')) {
    pushUniqueResponsibility(items, 'Прочитать Google-таблицу');
  }
  if (text.includes('telegram')) {
    pushUniqueResponsibility(items, 'Подготовить сообщение в Telegram');
  }
  if (text.includes('whatsapp')) {
    pushUniqueResponsibility(items, 'Разобрать вопросы из WhatsApp');
  }
  if (text.includes('поезд') || text.includes('trip') || text.includes('заказ')) {
    pushUniqueResponsibility(items, text.includes('поезд') || text.includes('trip') ? 'Найти нужную поездку' : 'Найти новые заказы');
  }
  if (blueprint.category === 'reviews' || text.includes('отзыв')) {
    pushUniqueResponsibility(items, 'Подготовить черновик ответа на отзыв');
  }
  if (blueprint.category === 'outreach' || text.includes('партн')) {
    pushUniqueResponsibility(items, 'Подготовить список и черновик сообщения');
  }
  if (blueprint.category === 'tables') {
    pushUniqueResponsibility(items, 'Сохранить данные в таблицу');
  }
  pushUniqueResponsibility(items, 'Подготовить результат для проверки владельцем');
  pushUniqueResponsibility(items, 'Остановиться перед внешним действием');
  return items.slice(0, 5);
};

export const buildEmployeeWorkspaceStory = (
  blueprint: AgentBlueprint,
  details?: AgentBlueprintDetails | null,
  pendingApproval?: AgentApproval | null,
) => {
  const state = buildEmployeeWorkspaceState(blueprint, details, pendingApproval);
  const status = buildEmployeeStatus(blueprint, details, pendingApproval);
  const attention = buildEmployeeAttentionItems(blueprint, details, pendingApproval);
  const userMode = buildAgentUserMode(blueprint, details);
  return {
    state,
    status,
    responsibilities: buildEmployeeResponsibilities(blueprint, details),
    latestWork: buildEmployeeLastActivity(blueprint, details, pendingApproval),
    nextWork: userMode.mode === 'scheduled'
      ? blueprint.status === 'active'
        ? (details?.next_run_at || blueprint.next_run_at)
          ? `Следующий запуск: ${formatShortDate(details?.next_run_at || blueprint.next_run_at)}`
          : 'Расписание включено, время следующего запуска уточняется'
        : 'После теста, настройки времени и включения'
      : userMode.mode === 'one_off'
        ? state === 'completed' ? 'Можно запустить ещё раз вручную' : 'После выполнения результат сохранится в истории'
        : blueprint.status === 'active' ? 'Когда вы нажмёте «Запустить работу»' : 'После теста и включения',
    attention,
  };
};

export const buildAgentUserMode = (
  blueprint: AgentBlueprint,
  details?: AgentBlueprintDetails | null,
) => {
  const preview = getBlueprintBuilderPreview(details?.blueprint || blueprint);
  const explicitMode = details?.execution_mode || blueprint.execution_mode;
  const trigger = String(preview?.trigger || '').trim();
  const mode = explicitMode || (trigger.includes('schedule') ? 'scheduled' : 'manual');
  if (mode === 'one_off') {
    return {
      mode,
      label: 'Разовая задача',
      flow: 'Запрос → выполнение → результат',
      description: 'Не запускается автоматически. После результата этого же агента можно запустить ещё раз вручную.',
    };
  }
  if (mode === 'scheduled') {
    return {
      mode,
      label: 'По расписанию',
      flow: 'Описание → тест → включение → расписание',
      description: 'Сотрудник запускается в указанное время. Внешние действия по-прежнему требуют подтверждения.',
    };
  }
  return {
    mode: 'manual',
    label: 'Запуск по кнопке',
    flow: 'Описание → тест → включение → запуск',
    description: 'Сотрудник выполняет задачу только когда вы нажимаете кнопку запуска.',
  };
};

export const buildReasonCard = (
  state: EmployeeWorkspaceState,
  pendingApproval?: AgentApproval | null,
) => {
  if (state === 'blocked_result') {
    return {
      title: 'Почему нельзя подтвердить результат',
      description: 'Сотрудник не получил нужные данные, поэтому подтверждать нечего. Сначала исправьте доступ или запустите тест заново.',
    };
  }
  if (state === 'waiting_for_review') {
    return {
      title: 'Почему сейчас требуется решение',
      description: pendingApproval
        ? explainApproval(pendingApproval)
        : 'Сотрудник остановился, потому что следующий шаг требует решения владельца.',
    };
  }
  if (state === 'needs_connection') {
    return {
      title: 'Почему работа не началась',
      description: 'Не хватает одного подключения или настройки источника. После подключения можно запустить безопасный тест.',
    };
  }
  if (state === 'running_test') {
    return {
      title: 'Что происходит сейчас',
      description: 'Сотрудник выполняет проверку. Внешние отправки и публикации не выполняются без вашего разрешения.',
    };
  }
  if (state === 'error') {
    return {
      title: 'Почему сотрудник остановился',
      description: 'Последняя проверка не дала готового результата. Посмотрите причину и запустите тест после исправления.',
    };
  }
  if (state === 'working') {
    return {
      title: 'Почему можно не вмешиваться',
      description: 'Сценарий включён, новых решений от владельца сейчас не требуется.',
    };
  }
  return {
    title: 'Почему следующий шаг именно такой',
    description: 'Перед включением LocalOS сначала показывает безопасный тест и результат для проверки.',
  };
};

export const buildBuildConfidenceFacts = (
  details?: AgentBlueprintDetails | null,
) => buildConfidenceFacts(details?.activation_gate, []).slice(0, 4);
