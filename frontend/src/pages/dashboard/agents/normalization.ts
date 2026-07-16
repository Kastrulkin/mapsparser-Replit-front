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
import { humanizeMeta } from './model';

const providerRouteLabel = (state: string) => ({
  connected: 'подключено',
  available: 'доступно',
  manual: 'ручной режим',
  planned: 'позже',
  unavailable: 'недоступно',
}[state] || humanizeMeta(state || 'unknown'));

const normalizeWorkspaceMode = (value: string): AgentWorkspaceMode | undefined => {
  switch (value) {
    case 'overview':
    case 'settings':
    case 'run':
    case 'results':
    case 'connections':
    case 'voice':
    case 'advanced':
      return value;
    default:
      return undefined;
  }
};

export const getRequestErrorMessage = (requestError: unknown, fallback: string) => {
  if (requestError instanceof Error && requestError.message.trim()) {
    return requestError.message
      .replace(/^Ошибка соединения с сервером:\s*/i, '')
      .replace(/^Ошибка запроса:\s*/i, '');
  }
  return fallback;
};

export const objectValue = (value: object, key: string): unknown => {
  const entry = Object.entries(value).find(([entryKey]) => entryKey === key);
  return entry ? entry[1] : undefined;
};

export const recordValue = (value: unknown): Record<string, unknown> | null => (
  value && typeof value === 'object' && !Array.isArray(value) ? Object.fromEntries(Object.entries(value)) : null
);

export const getBlueprintMetadata = (blueprint?: AgentBlueprint | null): Record<string, unknown> => (
  recordValue(blueprint?.metadata_json) || {}
);

export const getBlueprintBuilderPreview = (blueprint?: AgentBlueprint | null): AgentBuilderPreview | null => {
  const metadata = getBlueprintMetadata(blueprint);
  const preview = recordValue(metadata.agent_builder_preview);
  return preview ? { ...preview } : null;
};

export const normalizeSpreadsheetInput = (value: string) => {
  const clean = value.trim();
  const match = clean.match(/\/spreadsheets\/d\/([A-Za-z0-9_-]+)/);
  return match?.[1] || clean;
};

export const normalizePostCreateHandoff = (value: unknown): AgentPostCreateHandoff | null => {
  if (!value || typeof value !== 'object') {
    return null;
  }
  const missingBindings = objectValue(value, 'missing_bindings');
  const items = objectValue(value, 'items');
  const connectionPlan = normalizeConnectionPlan(objectValue(value, 'connection_plan'));
  const nextBinding = normalizeConnectionPlanItem(objectValue(value, 'next_binding'));
  const nextRoute = normalizeProviderRoute(objectValue(value, 'next_route'));
  const normalizedMissingBindings = Array.isArray(missingBindings) ? missingBindings : [];
  const firstMissingBinding = normalizedMissingBindings.find((item) => item && typeof item === 'object');
  const workspaceModeValue = String(objectValue(value, 'workspace_mode') || '');
  const workspaceMode = normalizeWorkspaceMode(workspaceModeValue);
  return {
    schema: String(objectValue(value, 'schema') || ''),
    status: String(objectValue(value, 'status') || ''),
    next_step: String(objectValue(value, 'next_step') || ''),
    workspace_mode: workspaceMode,
    next_binding_key: String(objectValue(value, 'next_binding_key') || (firstMissingBinding && typeof firstMissingBinding === 'object' ? objectValue(firstMissingBinding, 'key') || '' : '')),
    next_binding: nextBinding,
    next_route: nextRoute,
    title: String(objectValue(value, 'title') || ''),
    description: String(objectValue(value, 'description') || ''),
    missing_bindings: normalizedMissingBindings,
    items: Array.isArray(items) ? items : [],
    connection_plan: connectionPlan,
  };
};

export const normalizeAgentIntegrationPreflight = (value: unknown): AgentIntegrationPreflight | undefined => {
  if (!value || typeof value !== 'object') {
    return undefined;
  }
  const missingCount = objectValue(value, 'missing_count');
  const items = objectValue(value, 'items');
  const missing = objectValue(value, 'missing');
  const ready = objectValue(value, 'ready');
  return {
    status: String(objectValue(value, 'status') || ''),
    ready: typeof ready === 'boolean' ? ready : undefined,
    missing_count: typeof missingCount === 'number' ? missingCount : undefined,
    next_action: String(objectValue(value, 'next_action') || ''),
    items: Array.isArray(items) ? items : [],
    missing: Array.isArray(missing) ? missing : [],
  };
};

export const normalizeConnectionPlan = (value: unknown): AgentConnectionPlan | null => {
  if (!value || typeof value !== 'object') {
    return null;
  }
  const items = objectValue(value, 'items');
  const missingCount = objectValue(value, 'missing_count');
  return {
    schema: String(objectValue(value, 'schema') || ''),
    status: String(objectValue(value, 'status') || ''),
    missing_count: typeof missingCount === 'number' ? missingCount : undefined,
    items: Array.isArray(items) ? items : [],
  };
};

export const normalizeConnectionPlanItem = (value: unknown): AgentConnectionPlanItem | null => {
  if (!value || typeof value !== 'object') {
    return null;
  }
  const providerRoutes = objectValue(value, 'provider_routes');
  const providerPaths = objectValue(value, 'provider_paths');
  const recommendedRoute = normalizeProviderRoute(objectValue(value, 'recommended_route'));
  const missingConfig = objectValue(value, 'missing_config');
  const existingIntegrations = objectValue(value, 'existing_integrations');
  const attachedIntegrations = objectValue(value, 'attached_integrations');
  return {
    key: String(objectValue(value, 'key') || ''),
    provider: String(objectValue(value, 'provider') || ''),
    title: String(objectValue(value, 'title') || ''),
    capability: String(objectValue(value, 'capability') || ''),
    trigger: String(objectValue(value, 'trigger') || ''),
    direction: String(objectValue(value, 'direction') || ''),
    binding_status: String(objectValue(value, 'binding_status') || ''),
    action: String(objectValue(value, 'action') || ''),
    primary_label: String(objectValue(value, 'primary_label') || ''),
    explanation: String(objectValue(value, 'explanation') || ''),
    route_state: String(objectValue(value, 'route_state') || ''),
    route_summary: String(objectValue(value, 'route_summary') || ''),
    missing_config: Array.isArray(missingConfig) ? missingConfig : [],
    approval_required: objectValue(value, 'approval_required') === true,
    existing_integrations: Array.isArray(existingIntegrations) ? existingIntegrations : [],
    attached_integrations: Array.isArray(attachedIntegrations) ? attachedIntegrations : [],
    provider_routes: Array.isArray(providerRoutes) ? providerRoutes : [],
    provider_paths: Array.isArray(providerPaths) ? providerPaths : [],
    recommended_route: recommendedRoute,
    recommended_route_reason: String(objectValue(value, 'recommended_route_reason') || ''),
  };
};

export const normalizeProviderRoute = (value: unknown) => {
  if (!value || typeof value !== 'object') {
    return null;
  }
  const providerAction = objectValue(value, 'provider_action');
  return {
    provider: String(objectValue(value, 'provider') || ''),
    label: String(objectValue(value, 'label') || ''),
    state: String(objectValue(value, 'state') || ''),
    status: String(objectValue(value, 'status') || ''),
    role: String(objectValue(value, 'role') || ''),
    kind: String(objectValue(value, 'kind') || ''),
    connect_mode: String(objectValue(value, 'connect_mode') || ''),
    primary_cta: String(objectValue(value, 'primary_cta') || ''),
    provider_action: providerAction && typeof providerAction === 'object' ? {
      kind: String(objectValue(providerAction, 'kind') || ''),
      available: objectValue(providerAction, 'available') === true,
      ui_target: String(objectValue(providerAction, 'ui_target') || ''),
      label: String(objectValue(providerAction, 'label') || ''),
      description: String(objectValue(providerAction, 'description') || ''),
      role: String(objectValue(providerAction, 'role') || ''),
    } : undefined,
  };
};

export const formatPreflightBlock = (preflight?: AgentIntegrationPreflight | null) => {
  const missing = Array.isArray(preflight?.missing) ? preflight.missing : [];
  if (!missing.length) {
    return '';
  }
  const items = missing
    .map((item) => {
      const label = humanizeMeta(item.provider || item.key || 'integration');
      const config = item.missing_config?.length ? ` (${item.missing_config.join(', ')})` : '';
      return `${label}${config}`;
    })
    .join(', ');
  const needsOnlyConfig = missing.every((item) => item.status === 'needs_config' || item.resolution?.includes('missing_config'));
  if (needsOnlyConfig) {
    return `Перед запуском нужно заполнить настройки подключений: ${items}.`;
  }
  return `Перед запуском нужно подключить или настроить: ${items}.`;
};

export const connectorLabel = (provider?: string) => ({
  google_sheets: 'Google Sheets',
  browser_use: 'Browser use',
  telegram: 'Telegram',
  whatsapp: 'WhatsApp',
  openclaw: 'защищенный способ LocalOS',
  native_localos: 'LocalOS',
  manual: 'ручной режим',
  maton: 'Maton.ai',
  localos_finance: 'Финансы LocalOS',
  composio: 'Composio',
}[provider || ''] || humanizeMeta(provider || 'подключение'));

export const userFacingAgentTechText = (value?: string) => String(value || '')
  .replace(/Выбрать маршрут выполнения/gi, 'Выбрать способ подключения')
  .replace(/маршруты выполнения/gi, 'способы подключения')
  .replace(/маршрут выполнения/gi, 'способ подключения')
  .replace(/маршрут/gi, 'способ')
  .replace(/за ручное подтверждение/gi, 'за ручным подтверждением')
  .replace(/planner\/execution boundary/gi, 'защищенный контур LocalOS')
  .replace(/LocalOS policy envelope/gi, 'правила безопасности LocalOS')
  .replace(/policy envelope/gi, 'правила безопасности LocalOS')
  .replace(/approval и audit boundary/gi, 'ручные подтверждения и журнал LocalOS')
  .replace(/audit boundary/gi, 'журнал LocalOS')
  .replace(/boundary/gi, 'защищенный контур')
  .replace(/\bpolicy\b/gi, 'правила безопасности')
  .replace(/\bbilling\b/gi, 'списания')
  .replace(/\baudit\b/gi, 'журнал')
  .replace(/approvals/gi, 'ручные подтверждения')
  .replace(/Maton key/gi, 'ключ Maton.ai')
  .replace(/draft-only/gi, 'режим черновика')
  .replace(/safe preview/gi, 'тест без отправки')
  .replace(/preview run/gi, 'тест без отправки')
  .replace(new RegExp(`Preview ${'run'}`, 'g'), 'Тест без отправки')
  .replace(/Production run/g, 'Обычный запуск')
  .replace(/\bpreview\b/gi, 'тест')
  .replace(/\bтест run\b/gi, 'тест без отправки')
  .replace(/\bsafe тест\b/gi, 'тест без отправки')
  .replace(/\brun\b/gi, 'запуск')
  .replace(/\btrigger\b/gi, 'запуск')
  .replace(/\bcapability\b/gi, 'действие')
  .replace(/\bbinding\b/gi, 'доступ')
  .replace(/\breview\b/gi, 'отзыв')
  .replace(/chat_or_channel/gi, 'чат или канал')
  .replace(/bot_mode/gi, 'режим бота')
  .replace(/\bDraft\b/g, 'Черновик')
  .replace(/\bdraft\b/g, 'черновик')
  .replace(/compiled workflow/gi, 'проверенная логика')
  .replace(/approval gate/gi, 'ручное подтверждение')
  .replace(/за ручное подтверждение/gi, 'за ручным подтверждением')
  .replace(/last run/gi, 'последний запуск')
  .replace(/OpenClaw boundary/gi, 'защищенный способ LocalOS')
  .replace(/OpenClaw/gi, 'защищенный способ LocalOS')
  .replace(/execution route/gi, 'способ выполнения')
  .replace(/provider route/gi, 'способ подключения')
  .replace(/\broute\b/gi, 'способ')
  .replace(/preflight/gi, 'проверка перед запуском')
  .replace(/Draft/g, 'Черновик')
  .replace(/schedule\.daily_at\(([^)]*)\)/gi, 'ежедневно в $1')
  .replace(/schedule\.daily/gi, 'ежедневный запуск')
  .replace(/communications\.draft/g, 'черновик сообщения')
  .replace(/telegram\.message\.received/g, 'новое сообщение в Telegram')
  .replace(/needs source upload/gi, 'нужно добавить источник')
  .replace(/needs_source_upload/gi, 'нужно добавить источник')
  .replace(/external_reviews/gi, 'отзывы')
  .replace(/business_profile/gi, 'профиль бизнеса')
  .replace(/business_cards/gi, 'карточки')
  .replace(/\bphotos\b/gi, 'фотографии')
  .replace(/\bcompetitors\b/gi, 'конкуренты')
  .replace(/customer_questions/gi, 'вопросы клиентов')
  .replace(/customer_messages/gi, 'сообщения клиентов')
  .replace(/localos_tasks/gi, 'задачи LocalOS')
  .replace(/\bteam\b/gi, 'команда')
  .replace(/\bwhatsapp\b/gi, 'WhatsApp')
  .replace(/\bseasonality\b/gi, 'сезонность')
  .replace(/\bposts\b/gi, 'посты')
  .replace(/\bschedule\b/gi, 'расписание')
  .replace(/\binventory\b/gi, 'остатки')
  .replace(/\bproducts\b/gi, 'товары')
  .replace(/\bsupplies\b/gi, 'расходники')
  .replace(/staff_schedule/gi, 'расписание смен')
  .replace(/customer_chats/gi, 'чаты с клиентами')
  .replace(/staff_profiles/gi, 'профили сотрудников')
  .replace(/price_list/gi, 'прайс')
  .replace(/\brevenue\b/gi, 'выручка')
  .replace(/map_questions/gi, 'вопросы в карточках')
  .replace(/location_descriptions/gi, 'описания филиалов')
  .replace(/localos_digest/gi, 'дайджест LocalOS')
  .replace(/outreach_drafts/gi, 'черновики сообщений партнёрам')
  .replace(/\bclients\b/gi, 'клиенты')
  .replace(/\blocations\b/gi, 'точки сети')
  .replace(/\bservices\b/gi, 'услуги')
  .replace(/collect inputs/gi, 'собрать входные данные')
  .replace(/extract context/gi, 'понять данные')
  .replace(/prepare output/gi, 'подготовить результат')
  .replace(/final_output/gi, 'итоговый результат')
  .replace(/agent_output_draft/gi, 'черновик результата')
  .replace(/manual_review_reason/gi, 'причина ручной проверки')
  .replace(/\bsupervised\b/gi, 'под ручным контролем')
  .replace(/inside_localos_policy/gi, 'внутри правил LocalOS')
  .replace(/localos_managed_защищенный контур/gi, 'под управлением LocalOS')
  .replace(/localos_managed_boundary/gi, 'под управлением LocalOS')
  .replace(/approval_required/gi, 'требует ручного подтверждения')
  .replace(/проверка перед запуском_only/gi, 'только проверка перед запуском')
  .replace(/preflight_only/gi, 'только проверка перед запуском')
  .replace(/\bavailable\b/gi, 'доступно')
  .replace(/\bpending\b/gi, 'ожидает решения')
  .replace(/\bunknown\b/gi, 'неизвестно')
  .replace(/localos_envelope/g, 'правила LocalOS')
  .replace(/openclaw_action_orchestrator/g, 'контур выполнения LocalOS')
  .replace(/_/g, ' ')
  .replace(/защищенный способ LocalOS защищенный контур/gi, 'защищенный способ LocalOS')
  .replace(/защищенный способ LocalOS внутри правил LocalOS/gi, 'внутри правил LocalOS')
  .replace(/Использовать защищенный способ LocalOS защищенный контур/gi, 'Использовать защищенный способ LocalOS');

export const agentFlowStatusLabel = (status?: string) => ({
  ready: 'можно включить',
  draft: 'черновик',
  needs_connection: 'нужно проверить подключения',
  needs_connections: 'нужно проверить подключения',
  needs_connection_choice: 'нужно выбрать подключение',
  ready_for_draft: 'готов к черновику',
  ready_for_preview: 'готов к тесту',
  ready_for_activation: 'готов к включению',
}[String(status || '')] || humanizeMeta(status || 'проверить'));

export const autoSelectBuilderConnectionBindings = (preview?: AgentBuilderPreview | null): Record<string, string> => {
  const items = preview?.connection_summary?.items || [];
  const selected: Record<string, string> = {};
  items.forEach((item) => {
    const key = item.key || '';
    const connections = item.connections || [];
    const integrationId = connections.length === 1 ? connections[0]?.id || '' : '';
    if (key && integrationId) {
      selected[key] = integrationId;
    }
  });
  return selected;
};

export const autoSelectBuilderProviderRoutes = (preview?: AgentBuilderPreview | null): Record<string, string> => {
  const selected: Record<string, string> = {};
  const select = (key?: string, route?: AgentProviderRoute | null) => {
    const bindingKey = String(key || '').trim();
    const provider = String(route?.provider || '').trim();
    if (!bindingKey || !provider || !builderRouteIsUsable(route)) {
      return;
    }
    selected[bindingKey] = provider;
  };
  (preview?.connection_readiness?.services || []).forEach((service) => {
    select(service.key, service.recommended_route || null);
  });
  (preview?.connection_plan?.items || []).forEach((item) => {
    select(item.key, item.recommended_route || null);
  });
  return selected;
};

export const builderRouteIsUsable = (route?: AgentProviderRoute | null): boolean => {
  const provider = String(route?.provider || '').trim();
  const state = String(route?.state || route?.status || '').trim();
  return Boolean(provider && ['available', 'connected', 'manual'].includes(state) && route?.provider_action?.available !== false);
};

export const builderRequiredProviderRouteKeys = (preview?: AgentBuilderPreview | null): string[] => {
  const keys = new Set<string>();
  const inspect = (key?: string, route?: AgentProviderRoute | null, routes?: AgentProviderRoute[]) => {
    const bindingKey = String(key || '').trim();
    if (!bindingKey) {
      return;
    }
    const candidates = [route, ...(routes || [])];
    if (candidates.some((candidate) => builderRouteIsUsable(candidate))) {
      keys.add(bindingKey);
    }
  };
  (preview?.connection_readiness?.services || []).forEach((service) => {
    inspect(service.key, service.recommended_route || null, undefined);
  });
  (preview?.connection_plan?.items || []).forEach((item) => {
    inspect(item.key, item.recommended_route || null, item.provider_routes || []);
  });
  return Array.from(keys);
};

export const bindingResolutionLabel = (binding: AgentIntegrationBindingStatus) => ({
  native_localos: 'внутри LocalOS',
  agent_integration: 'подключение бизнеса',
  blueprint_metadata: 'настройка агента',
  provider_route_openclaw: 'защищенный способ LocalOS',
  provider_route_maton: 'Maton.ai',
  provider_route_manual: 'ручной режим',
  provider_route_openclaw_boundary: 'защищенный способ LocalOS',
  provider_route_maton_external_account: 'Maton.ai',
  compiled_default: 'настройка агента',
  input_payload: 'данные запуска',
  missing_integration: 'нужен доступ',
}[binding.resolution || ''] || humanizeMeta(binding.resolution || binding.provider));

export const bindingUserFacingRole = (binding: AgentIntegrationBindingStatus) => {
  const direction = String(binding.direction || '').trim();
  const capability = String(binding.capability || '').trim();
  const trigger = String(binding.trigger || '').trim();
  if (binding.provider === 'google_sheets') {
    if (capability === 'google_sheets.read_rows' || direction === 'external_read') {
      return 'Источник данных: чтение строк из Google Sheets';
    }
    if (capability === 'sheets.append_row_request' || direction === 'external_write') {
      return 'Канал результата: подготовить запись в Google Sheets';
    }
    return 'Источник данных или канал результата: Google Sheets';
  }
  if (binding.provider === 'browser_use') {
    return 'Источник данных: чтение сайта через защищенный способ LocalOS';
  }
  if (binding.provider === 'telegram') {
    if (direction === 'trigger' || trigger) {
      return 'Событие запуска: сообщение или событие в Telegram';
    }
    return 'Канал результата: Telegram';
  }
  if (binding.provider === 'whatsapp') {
    if (direction === 'trigger' || trigger) {
      return 'Событие запуска: сообщение или вопрос клиента в WhatsApp';
    }
    return 'Канал результата: WhatsApp';
  }
  if (binding.provider === 'maton') {
    return 'Канал результата: Maton.ai';
  }
  if (binding.provider === 'localos_finance') {
    return 'Результат внутри LocalOS: финансы';
  }
  return humanizeMeta(binding.key || binding.trigger || binding.capability || binding.direction || binding.provider);
};

export const bindingActionHint = (binding: AgentIntegrationBindingStatus) => {
  if (binding.status === 'connected' || binding.status === 'ready') {
    return `${connectorLabel(binding.provider)} готово: ${bindingResolutionLabel(binding)}.`;
  }
  if (binding.provider === 'google_sheets') {
    return 'Выберите существующий Google-доступ или укажите таблицу и лист ниже.';
  }
  if (binding.provider === 'browser_use') {
    return 'Укажите сайт для проверки. Чтение выполняется через OpenClaw boundary внутри правил LocalOS.';
  }
  if (binding.provider === 'telegram') {
    return 'Выберите режим бота ниже, чтобы агент мог принимать события Telegram.';
  }
  if (binding.provider === 'whatsapp') {
    return 'Выберите режим WhatsApp ниже, чтобы агент мог учитывать вопросы клиентов или готовить сообщения.';
  }
  if (binding.provider === 'maton') {
    return 'Используйте сохранённый Maton.ai доступ бизнеса или добавьте ключ в интеграциях.';
  }
  if (binding.provider === 'composio') {
    return 'Composio будет доступен как OAuth-provider позже; пока используйте ручной или native путь.';
  }
  return 'Подключите источник или оставьте агент в draft-only режиме.';
};

export const connectionResourceFacts = (provider?: string, config?: Record<string, unknown> | null): string[] => {
  const data = config || {};
  if (!Object.keys(data).length) {
    return [];
  }
  if (provider === 'google_sheets') {
    return [
      String(data.spreadsheet_id || data.spreadsheet_url || '').trim() ? `таблица: ${String(data.spreadsheet_id || data.spreadsheet_url).trim()}` : '',
      String(data.sheet_name || '').trim() ? `лист: ${String(data.sheet_name).trim()}` : '',
      String(data.gid || '').trim() ? `gid: ${String(data.gid).trim()}` : '',
    ].filter(Boolean);
  }
  if (provider === 'browser_use') {
    const rawUrls = Array.isArray(data.target_urls) ? data.target_urls : [data.target_url || data.url].filter(Boolean);
    return rawUrls
      .map((item) => String(item || '').trim())
      .filter(Boolean)
      .slice(0, 3)
      .map((item) => `сайт: ${item}`);
  }
  if (provider === 'telegram') {
    return [
      String(data.telegram_target || data.chat_id || '').trim() ? `канал: ${String(data.telegram_target || data.chat_id).trim()}` : '',
      String(data.target_type || '').trim() ? userFacingAgentTechText(humanizeMeta(String(data.target_type).trim())) : '',
    ].filter(Boolean);
  }
  if (provider === 'whatsapp') {
    return [
      String(data.whatsapp_target || data.phone_id || data.channel_mode || '').trim() ? `канал: ${String(data.whatsapp_target || data.phone_id || data.channel_mode).trim()}` : '',
      String(data.target_type || '').trim() ? userFacingAgentTechText(humanizeMeta(String(data.target_type).trim())) : '',
    ].filter(Boolean);
  }
  if (provider === 'maton') {
    return [
      String(data.channel || '').trim() ? `канал: ${String(data.channel).trim()}` : '',
      String(data.auth_ref || '').trim() ? 'ключ выбран' : '',
    ].filter(Boolean);
  }
  return Object.entries(data)
    .slice(0, 3)
    .map(([key, value]) => String(value || '').trim() ? `${humanizeMeta(key)}: ${String(value).trim()}` : '')
    .filter(Boolean);
};

export const isReadyConnectionAction = (action?: string) => action === 'ready' || action === 'native_ready';

export const buildAgentConnectionDecision = (
  connectionPlan: AgentConnectionPlan | null,
  bindingStatus: AgentIntegrationBindingStatus[],
  canPreviewRun: boolean,
): AgentConnectionDecision => {
  const planItems = Array.isArray(connectionPlan?.items) ? connectionPlan.items : [];
  const nextPlanItem = planItems.find((item) => !isReadyConnectionAction(item.action));
  if (nextPlanItem) {
    const provider = connectorLabel(nextPlanItem.provider);
    const routes = nextPlanItem.provider_routes || [];
    const route = routes.find((item) => item.state === 'available') || routes[0];
    const routeAction = route?.primary_cta || providerRouteLabel(route?.state || route?.status || '');
    const title = nextPlanItem.action === 'choose_existing'
      ? `Выберите подключение ${provider}`
      : nextPlanItem.action === 'complete_config'
      ? `Заполните настройки ${provider}`
      : `Подключите ${provider}`;
    return {
      tone: nextPlanItem.action === 'choose_existing' ? 'choice' : 'needs_action',
      title,
      description: userFacingAgentTechText(nextPlanItem.route_summary || nextPlanItem.explanation || `${routeAction}. После этого LocalOS разрешит тест без отправки.`),
      action: 'configure',
      cta: userFacingAgentTechText(nextPlanItem.primary_label || routeAction || 'Настроить доступ'),
      bindingKey: nextPlanItem.key || '',
    };
  }
  const nextBinding = bindingStatus.find((binding) => binding.status !== 'connected' && binding.status !== 'ready');
  if (nextBinding) {
    return {
      tone: 'needs_action',
      title: `Настройте ${connectorLabel(nextBinding.provider)}`,
      description: bindingActionHint(nextBinding),
      action: 'configure',
      cta: 'Открыть настройку',
      bindingKey: nextBinding.key || '',
    };
  }
  if (canPreviewRun) {
    return {
      tone: 'ready',
      title: 'Подключения готовы',
      description: 'Запустите тест без отправки: LocalOS проверит доступы, лимиты и ручные подтверждения без внешней публикации.',
      action: 'preview',
      cta: 'Проверить на примере',
    };
  }
  return {
    tone: 'pending',
    title: 'Проверьте подключения',
    description: 'LocalOS покажет следующий шаг после загрузки connection plan.',
    action: 'none',
    cta: '',
  };
};

export const buildBuilderCreationDecision = ({
  preview,
  questions,
  missingConnectionChoices,
  missingProviderRouteKeys,
  missingProviderRouteConfirmation,
  canCreateDraft,
  createDraftLabel,
  previewIsStale,
}: {
  preview: AgentBuilderPreview | null;
  questions: AgentBuilderQuestion[];
  missingConnectionChoices: Array<AgentConnectionSummary['items'] extends Array<infer Item> ? Item : never>;
  missingProviderRouteKeys: string[];
  missingProviderRouteConfirmation: boolean;
  canCreateDraft: boolean;
  createDraftLabel: string;
  previewIsStale?: boolean;
}): AgentConnectionDecision => {
  const forbidden = preview?.connection_summary?.forbidden || [];
  const unsupported = preview?.connection_summary?.unsupported || [];
  if (previewIsStale) {
    return {
      tone: 'needs_action',
      title: 'Обновите понимание',
      description: 'Вы изменили запрос. Нажмите «Обновить понимание», чтобы LocalOS пересобрал сводку именно по этому тексту.',
      action: 'none',
      cta: 'Обновить понимание',
    };
  }
  if (forbidden.length || unsupported.length) {
    const reason = forbidden[0]?.reason || unsupported[0]?.reason || 'Такой способ подключения не разрешён правилами безопасности LocalOS.';
    return {
      tone: 'blocked',
      title: 'Такого агента нельзя создать',
      description: reason,
      action: 'none',
      cta: '',
    };
  }
  const blockingQuestions = builderBlockingQuestions(questions);
  if (blockingQuestions.length) {
    return {
      tone: 'needs_action',
      title: 'Ответьте на уточнение',
      description: blockingQuestions[0]?.question || 'LocalOS нужно больше деталей, чтобы собрать проверенную логику без догадок.',
      action: 'answer',
      cta: 'Отправить ответ',
    };
  }
  if (missingConnectionChoices.length) {
    const title = missingConnectionChoices[0]?.title || connectorLabel(missingConnectionChoices[0]?.provider);
    return {
      tone: 'choice',
      title: `Выберите подключение ${title}`,
      description: 'У бизнеса уже есть несколько подходящих подключений. Выберите, какое использовать для этого агента.',
      action: 'choose',
      cta: 'Выбрать ниже',
      bindingKey: missingConnectionChoices[0]?.key || '',
    };
  }
  if (missingProviderRouteKeys.length) {
    return {
      tone: 'choice',
      title: 'Выберите способ доставки',
      description: `LocalOS нашёл безопасный вариант, но нужно выбрать способ для: ${missingProviderRouteKeys.map((item) => userFacingAgentTechText(humanizeMeta(item))).join(', ')}.`,
      action: 'choose',
      cta: 'Выбрать ниже',
      bindingKey: missingProviderRouteKeys[0] || '',
    };
  }
  if (missingProviderRouteConfirmation) {
    return {
      tone: 'choice',
      title: 'Подтвердите способы подключения',
      description: 'LocalOS сохранит выбранные способы подключения и будет проверять доступы, лимиты и ручные подтверждения перед запуском.',
      action: 'choose',
      cta: 'Подтвердить ниже',
    };
  }
  if (canCreateDraft) {
    return {
      tone: preview?.setup_flow?.post_create_status === 'ready_for_preview' ? 'ready' : 'choice',
      title: preview?.setup_flow?.post_create_status === 'ready_for_preview'
        ? 'Можно создать черновик и проверить'
        : 'Можно создать черновик и подключить сервисы',
      description: userFacingAgentTechText(preview?.setup_flow?.post_create_description || preview?.setup_flow?.next_step_description || 'LocalOS сохранит проверяемую логику агента и откроет следующий безопасный шаг.'),
      action: 'create',
      cta: createDraftLabel,
    };
  }
  return {
    tone: 'pending',
    title: preview?.setup_flow?.next_step_title || 'Завершите настройку',
    description: preview?.setup_flow?.next_step_description || 'LocalOS покажет следующий шаг после уточнения задачи и проверки способов подключения.',
    action: 'none',
    cta: '',
  };
};

export const builderBlockingQuestions = (questions: AgentBuilderQuestion[]) => questions.filter((question) => {
  const reason = String(question.reason || '').trim();
  const key = String(question.key || '').trim();
  if (['connection_resolver', 'binding_config_needed', 'required_connection_missing', 'required_connection_missing_config', 'multiple_connections_available'].includes(reason)) {
    return false;
  }
  if (key.startsWith('connect_') || key.startsWith('choose_')) {
    return false;
  }
  return true;
});

export const activationBlockerText = (gate?: AgentActivationGate) => {
  const humanBlockers = gate?.human_blockers || [];
  const blockers = gate?.blockers || [];
  const labels = [
    ...humanBlockers.map((item) => item.message || item.title || connectorLabel(item.provider)),
    ...blockers.map((item) => item.message || connectorLabel(item.provider)),
  ].map((item) => item.trim()).filter(Boolean);
  return labels.slice(0, 3).join(', ');
};

export const buildActivationGateDecision = (gate?: AgentActivationGate): AgentConnectionDecision => {
  if (!gate) {
    return {
      tone: 'pending',
      title: 'Готовность к включению ещё не проверена',
      description: 'Создайте версию и запустите тест без отправки, чтобы LocalOS понял, можно ли включать агента.',
      action: 'none',
      cta: '',
    };
  }
  if (gate.can_activate) {
    return {
      tone: 'ready',
      title: 'Агента можно включить',
      description: userFacingAgentTechText(gate.summary) || 'Тест без отправки, доступы, лимиты и логика прошли проверку. Внешние действия останутся за ручным подтверждением.',
      action: 'activate',
      cta: gate.primary_action_label || 'Включить агента',
    };
  }
  if (gate.next_step === 'connect_required_integrations') {
    return {
      tone: 'needs_action',
      title: 'Нужно подключить сервисы',
      description: userFacingAgentTechText(gate.summary) || activationBlockerText(gate) || 'LocalOS понял нужные подключения, но без них нельзя пройти тест и включить агента.',
      action: 'connections',
      cta: gate.primary_action_label || 'Открыть подключения',
      bindingKey: gate.next_binding_key || '',
    };
  }
  if (gate.next_step === 'fix_compiled_workflow') {
    return {
      tone: 'blocked',
      title: 'Логику нужно исправить',
      description: userFacingAgentTechText(gate.summary) || activationBlockerText(gate) || 'Логика агента не прошла проверку. Исправьте версию перед запуском.',
      action: 'logic',
      cta: gate.primary_action_label || 'Открыть логику',
    };
  }
  if (gate.next_step === 'create_version') {
    return {
      tone: 'needs_action',
      title: 'Нужно создать версию',
      description: userFacingAgentTechText(gate.summary) || 'У агента ещё нет проверенной версии логики.',
      action: 'logic',
      cta: gate.primary_action_label || 'Создать версию',
    };
  }
  if (gate.next_step === 'run_preview') {
    return {
      tone: 'choice',
      title: 'Нужно проверить на примере',
      description: userFacingAgentTechText(gate.preview_run_status?.message || gate.summary) || 'Перед включением LocalOS должен выполнить тест без внешних действий.',
      action: 'preview',
      cta: gate.primary_action_label || 'Проверить на примере',
    };
  }
  if (gate.next_step === 'review_approvals') {
    return {
      tone: 'needs_action',
      title: 'Нужно проверить решение',
      description: userFacingAgentTechText(gate.summary) || activationBlockerText(gate) || 'Есть ручное решение, которое влияет на готовность агента.',
      action: 'results',
      cta: gate.primary_action_label || 'Открыть решения',
    };
  }
  return {
    tone: 'pending',
    title: 'Активация пока недоступна',
    description: userFacingAgentTechText(gate.summary) || activationBlockerText(gate) || 'Проверьте логику, подключения и тест без отправки.',
    action: 'none',
    cta: '',
  };
};

export const buildActivationPathSteps = (gate?: AgentActivationGate): AgentActivationPathStep[] => {
  const nextStep = gate?.next_step || '';
  const compiledReady = gate?.compiled_validation?.ready === true;
  const policyReady = gate?.approval_policy_status?.ready === true;
  const connectionsReady = gate?.preflight?.ready === true;
  const previewReady = gate?.preview_run_status?.ready === true;
  const canActivate = gate?.can_activate === true;
  return [
    {
      key: 'task',
      label: 'Задача',
      detail: gate ? 'описана' : 'нужно описание',
      status: gate ? 'done' : 'pending',
    },
    {
      key: 'compiled',
      label: 'Логика',
      detail: compiledReady ? 'проверена' : 'нужно проверить',
      status: compiledReady ? 'done' : nextStep === 'fix_compiled_workflow' || nextStep === 'create_version' ? 'current' : 'pending',
    },
    {
      key: 'policy',
      label: 'Подтверждение',
      detail: policyReady ? 'правила готовы' : 'нужно настроить',
      status: policyReady ? 'done' : nextStep === 'fix_compiled_workflow' ? 'current' : 'pending',
    },
    {
      key: 'connections',
      label: 'Доступы',
      detail: connectionsReady ? 'готовы' : 'нужно подключить',
      status: connectionsReady ? 'done' : nextStep === 'connect_required_integrations' ? 'current' : 'pending',
    },
    {
      key: 'preview',
      label: 'Тест',
      detail: previewReady ? 'пройден' : 'нужен запуск',
      status: previewReady ? 'done' : nextStep === 'run_preview' ? 'current' : 'pending',
    },
    {
      key: 'activate',
      label: 'Включение',
      detail: canActivate ? 'можно включить' : 'после проверки',
      status: canActivate ? 'current' : 'pending',
    },
  ];
};
