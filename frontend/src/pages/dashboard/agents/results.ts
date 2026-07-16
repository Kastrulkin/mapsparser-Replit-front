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
  getVersionNumber,
  getLatestVersionNumber,
  getActiveVersionNumber,
  getActiveVersionId,
  getLatestVersionId,
  getRunnableVersionId,
  agentExecutionMode,
  agentExecutionModeLabel,
  agentNextRunLabel,
  businessResultPrimaryText,
  estimatedAgentRunCredits,
  workflowStepsForAnimation,
  getAgentVoiceName,
  runStatusFilters,
  learningTriggerOptions,
  agentPromptExamples,
  agentScenarios,
  statusTone,
  statusLabels,
  stepLabels,
  metaLabels,
  resultFieldLabels,
  outreachProgressStages,
  genericRunStages,
  humanizeStatus,
  humanizeStep,
  humanizeMeta,
  humanizeCategory,
  explainApproval,
  approvalActionLabels,
  getApprovalPreviewItems,
  approvalDecisionTitle,
  getAgentListStatus,
  formatShortDate,
  formatLastRun,
  isWithinLastDay,
  buildTodaySummary,
  initialRunParameters,
  validateRunParameters,
  buildAgentBusinessStatus,
  buildEmployeeDescription,
  buildEmployeeStatus,
  buildEmployeeWorkspaceState,
  buildEmployeeLastActivity,
  buildEmployeeNextAction,
  getMissingConnectorLabel,
  buildEmployeePrimaryAction,
  pushUniqueResponsibility,
  buildEmployeeResponsibilities,
  buildEmployeeWorkspaceStory,
  buildAgentUserMode,
  buildReasonCard,
  buildBuildConfidenceFacts
} from './model';

export const stringifyBusinessValue = (value: unknown): string => {
  if (value === null || value === undefined) {
    return '';
  }
  if (typeof value === 'string') {
    return value;
  }
  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  if (Array.isArray(value)) {
    return value
      .slice(0, 4)
      .map((item) => stringifyBusinessValue(item))
      .filter(Boolean)
      .join('; ');
  }
  if (typeof value === 'object') {
    const entries = Object.entries(value).slice(0, 6);
    return entries
      .map(([key, entryValue]) => {
        const text = stringifyBusinessValue(entryValue);
        return text ? `${humanizeMeta(key)}: ${text}` : '';
      })
      .filter(Boolean)
      .join('; ');
  }
  return '';
};

export const isTechnicalApprovalPayload = (value: unknown): boolean => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return false;
  }
  const keys = Object.keys(value);
  return keys.some((key) => [
    'approval_required',
    'dispatch_state',
    'external_dispatch_performed',
    'approval_state',
    'artifact_type',
  ].includes(key)) || keys.some((key) => key.endsWith('_json'));
};

export const toPlainRecord = (value: unknown): Record<string, unknown> | null => {
  if (typeof value === 'string') {
    try {
      const parsed = JSON.parse(value);
      return toPlainRecord(parsed);
    } catch {
      return null;
    }
  }
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return null;
  }
  return Object.fromEntries(Object.entries(value));
};

export const meaningfulResultKeys = [
  'post_text',
  'draft_text',
  'message',
  'text',
  'body',
  'subject',
  'title',
  'summary',
  'result',
  'items',
  'facts',
  'recommendations',
  'reply_drafts',
  'rows_to_review',
  'preparation_method',
];

export const extractBusinessResultPayload = (value: unknown): Record<string, unknown> | null => {
  const record = toPlainRecord(value);
  if (!record) {
    return null;
  }
  const nestedResult = toPlainRecord(record.result);
  if (nestedResult) {
    return nestedResult;
  }
  const nestedArtifact = toPlainRecord(record.artifact);
  if (nestedArtifact) {
    const artifactResult = extractBusinessResultPayload(nestedArtifact);
    if (artifactResult) {
      return artifactResult;
    }
  }
  const hasMeaningfulResult = meaningfulResultKeys.some((key) => record[key] !== undefined && record[key] !== null && record[key] !== '');
  if (!hasMeaningfulResult || isTechnicalApprovalPayload(record)) {
    return null;
  }
  return Object.fromEntries(
    Object.entries(record).filter(([key, entryValue]) => (
      meaningfulResultKeys.includes(key)
      && entryValue !== ''
      && entryValue !== null
      && entryValue !== undefined
    )),
  );
};

export const findPreparedResultPayload = (
  activeRun: AgentRun | null,
  pendingApproval?: AgentApproval | null,
): Record<string, unknown> | null => {
  if (activeRun?.business_result && Object.keys(activeRun.business_result).length > 0) {
    return activeRun.business_result;
  }
  const artifacts = activeRun?.artifacts || [];
  const priority = activeRun?.status === 'completed'
    ? ['agent_final_result', 'agent_output_draft', 'telegram_post_draft']
    : ['agent_output_draft', 'telegram_post_draft', 'agent_final_result'];
  const preferredArtifact = priority
    .map((artifactType) => artifacts.find((item) => item.artifact_type === artifactType))
    .find(Boolean)
    || artifacts.find((item) => extractBusinessResultPayload(item.payload_json));
  const artifactResult = extractBusinessResultPayload(preferredArtifact?.payload_json || null);
  if (artifactResult) {
    return artifactResult;
  }
  if (pendingApproval?.run_id && activeRun?.id && pendingApproval.run_id !== activeRun.id) {
    return null;
  }
  return extractBusinessResultPayload(pendingApproval?.payload_json || null);
};

export const hasPreparedMessageText = (result: Record<string, unknown> | null): boolean => {
  if (!result) {
    return false;
  }
  return ['post_text', 'draft_text', 'message', 'text', 'body'].some((key) => {
    const value = result[key];
    return typeof value === 'string' && value.trim().length > 0;
  });
};

export const resultPayloadStatus = (result: Record<string, unknown> | null): string => {
  const status = result?.status;
  return typeof status === 'string' ? status.trim().toLowerCase() : '';
};

export const isBusinessBlockerPayload = (result: Record<string, unknown> | null): boolean => {
  const status = resultPayloadStatus(result);
  return [
    'needs_source_data',
    'needs_clarification',
    'needs_source_upload',
    'needs_config',
    'validation_error',
    'provider_read_required',
    'needs_google_access',
    'needs_google_api_enabled',
    'needs_sheet_tab',
    'blocked',
  ].includes(status);
};

export const isBusinessBlockerApproval = (approval?: AgentApproval | null): boolean => (
  isBusinessBlockerPayload(extractBusinessResultPayload(approval?.payload_json || null))
);

export const buildEmployeeTestResult = (
  activeRun: AgentRun | null,
  pendingApproval?: AgentApproval | null,
): EmployeeTestResult => {
  const approvalItems = pendingApproval ? getApprovalPreviewItems(pendingApproval) : [];
  const resultPayload = findPreparedResultPayload(activeRun, pendingApproval);
  const blocker = isBusinessBlockerPayload(resultPayload);
  const hasStructuredResult = Boolean(resultPayload && !blocker);
  const output = hasStructuredResult
    ? ''
    : blocker
      ? ''
      : activeRun?.status === 'failed'
        ? 'Проверка остановилась до сохранения результата. Посмотрите причину в настройках и запустите тест ещё раз.'
        : '';
  const status = activeRun?.status || pendingApproval?.run_status || '';
  const isWorkRun = activeRun?.input_json?.preview_mode === false;
  const summary = blocker
    ? 'Нужен следующий шаг перед результатом'
    : pendingApproval
    ? hasPreparedMessageText(resultPayload)
      ? 'Проверьте подготовленный пост'
      : approvalDecisionTitle(pendingApproval)
    : status === 'completed'
      ? isWorkRun ? 'Работа завершена. Сотрудник сохранил результат.' : 'Тест завершён. Сотрудник подготовил результат.'
      : status === 'failed'
        ? 'Тест остановился. Результат требует проверки.'
        : activeRun
          ? 'Тест выполнен. Ниже бизнес-результат.'
          : 'После теста здесь появится подготовленный результат.';
  const state: EmployeeTestResult['state'] = hasStructuredResult
    ? 'result'
    : blocker
      ? 'blocker'
      : output
        ? 'missing'
        : 'missing';
  return {
    summary,
    output: output || (blocker
      ? ''
      : pendingApproval
        ? resultPayload
          ? 'Агент подготовил результат, но отдельный текст результата не был сохранён.'
          : 'Агент дошёл до проверки, но не сохранил результат. Запустите тест ещё раз или уточните формат результата.'
        : 'Результат не был сохранён. Запустите тест ещё раз.'),
    state,
    resultPayload,
    previewItems: approvalItems,
    hasResult: Boolean(activeRun || pendingApproval || output || resultPayload || approvalItems.length),
  };
};

export const versionHasGoogleSheetsReadStep = (version?: Record<string, unknown> | null) => {
  const versionRecord = recordValue(version);
  const rawSteps = versionRecord ? versionRecord.steps_json : null;
  const steps = Array.isArray(rawSteps) ? rawSteps : [];
  return steps.some((step) => {
    const stepRecord = recordValue(step);
    if (!stepRecord) {
      return false;
    }
    const key = String(stepRecord.key || stepRecord.id || '').toLowerCase();
    const capability = String(stepRecord.capability || stepRecord.capability_key || '').toLowerCase();
    return key.includes('read_google_sheets') || capability === 'google_sheets.read_rows';
  });
};

export const detailsHaveGoogleSheetsReadStep = (details?: AgentBlueprintDetails | null) => {
  if (!details) {
    return false;
  }
  if (versionHasGoogleSheetsReadStep(details.active_version)) {
    return true;
  }
  const latestVersion = [...(details.versions || [])].sort((a, b) => (getVersionNumber(b) || 0) - (getVersionNumber(a) || 0))[0] || null;
  return versionHasGoogleSheetsReadStep(latestVersion);
};

export const needsScenarioRebuildForSourceResult = (
  activeRun: AgentRun | null,
  pendingApproval?: AgentApproval | null,
  details?: AgentBlueprintDetails | null,
) => {
  const resultPayload = findPreparedResultPayload(activeRun, pendingApproval);
  if (!isBusinessBlockerPayload(resultPayload)) {
    return false;
  }
  const sourceChain = activeRun?.observability?.source_result_chain || {};
  const text = stringifyBusinessValue(resultPayload).toLowerCase();
  const mentionsSheets = text.includes('google sheets') || text.includes('таблиц');
  if (!mentionsSheets) {
    return false;
  }
  if (sourceChain.source_step_present === false) {
    return true;
  }
  if (sourceChain.source_step_present === true) {
    return false;
  }
  return !detailsHaveGoogleSheetsReadStep(details);
};

export const needsGoogleSheetsSourceSetup = (activeRun: AgentRun | null, pendingApproval?: AgentApproval | null) => {
  const resultPayload = findPreparedResultPayload(activeRun, pendingApproval);
  if (!isBusinessBlockerPayload(resultPayload)) {
    return false;
  }
  const text = stringifyBusinessValue(resultPayload).toLowerCase();
  if (resultPayloadStatus(resultPayload) === 'needs_google_access') {
    return text.includes('unable to parse range');
  }
  if (resultPayloadStatus(resultPayload) === 'needs_google_api_enabled') {
    return false;
  }
  if (resultPayloadStatus(resultPayload) === 'needs_sheet_tab') {
    return true;
  }
  return text.includes('google sheets') || text.includes('таблиц');
};

export const needsGoogleAccessReconnect = (activeRun: AgentRun | null, pendingApproval?: AgentApproval | null) => {
  const resultPayload = findPreparedResultPayload(activeRun, pendingApproval);
  if (resultPayloadStatus(resultPayload) !== 'needs_google_access') {
    return false;
  }
  return !stringifyBusinessValue(resultPayload).toLowerCase().includes('unable to parse range');
};

export const hasFreshGoogleSheetsAccessAfterResult = (
  authOptions: AgentExternalAuthOption[],
  activeRun: AgentRun | null,
  pendingApproval?: AgentApproval | null,
) => {
  const resultTimeRaw = activeRun?.completed_at || activeRun?.started_at || pendingApproval?.requested_at || pendingApproval?.run_started_at || '';
  const resultTime = resultTimeRaw ? new Date(resultTimeRaw).getTime() : 0;
  if (!resultTime || Number.isNaN(resultTime)) {
    return false;
  }
  return authOptions.some((option) => {
    const source = String(option.source || '').trim();
    const provider = String(option.provider || '').trim();
    if (!['google_business', 'google_sheets'].includes(source) && provider !== 'google_sheets') {
      return false;
    }
    const updatedAt = option.updated_at ? new Date(option.updated_at).getTime() : 0;
    return Boolean(updatedAt && !Number.isNaN(updatedAt) && updatedAt > resultTime);
  });
};

export const buildEmployeeHistoryStory = (
  details: AgentBlueprintDetails | null,
  activeRun: AgentRun | null,
) => buildBusinessHistoryEvents(details, activeRun).map((event) => ({
  ...event,
  title: event.title === 'Запуск завершён' ? 'Выполнил задачу' : event.title,
  description: userFacingAgentTechText(event.description),
}));

export const buildEmployeeAttentionItems = (
  blueprint: AgentBlueprint,
  details?: AgentBlueprintDetails | null,
  pendingApproval?: AgentApproval | null,
) => {
  const items: Array<{ key: string; title: string; description: string; tone: 'amber' | 'rose' }> = [];
  const missingConnections = Number(details?.activation_gate?.preflight?.missing_count || 0);
  const latestResult = findPreparedResultPayload(details?.runs?.[0] || null, pendingApproval);
  const blocker = isBusinessBlockerPayload(latestResult);
  if (blocker) {
    const needsGoogle = resultPayloadStatus(latestResult) === 'needs_google_access';
    items.push({
      key: needsGoogle ? 'google-access' : 'blocked-result',
      title: needsGoogle ? 'Нужен Google-доступ к таблице' : 'Нужен следующий шаг перед результатом',
      description: needsGoogle
        ? 'Google не дал строки таблицы. Переподключите доступ или запустите тест после подключения.'
        : 'Сотрудник остановился до готового результата. Откройте причину и исправьте следующий шаг.',
      tone: 'amber',
    });
  }
  if (!blocker && (pendingApproval || Number(blueprint.pending_approvals_count || 0) > 0)) {
    items.push({
      key: 'approval',
      title: 'Нужно ваше решение',
      description: pendingApproval ? explainApproval(pendingApproval) : 'Сотрудник ждёт подтверждения результата.',
      tone: 'amber',
    });
  }
  if (missingConnections > 0) {
    items.push({
      key: 'connections',
      title: 'Не хватает подключения',
      description: `${missingConnections} ${missingConnections === 1 ? 'сервис нужно подключить' : 'сервиса нужно подключить'}, чтобы сотрудник мог работать.`,
      tone: 'amber',
    });
  }
  if (blueprint.last_run_status === 'failed' || blueprint.status === 'error') {
    items.push({
      key: 'failed',
      title: 'Последняя работа остановилась',
      description: 'Откройте результат и повторите тест после исправления.',
      tone: 'rose',
    });
  }
  return items;
};

export const buildAttentionInbox = ({
  blueprints,
  selectedBlueprint,
  selectedDetails,
  selectedPendingApproval,
  onOpenResults,
  onOpenConnections,
  onStartRun,
  onSelectBlueprint,
}: {
  blueprints: AgentBlueprint[];
  selectedBlueprint: AgentBlueprint | null;
  selectedDetails: AgentBlueprintDetails | null;
  selectedPendingApproval: AgentApproval | null;
  onOpenResults: () => void;
  onOpenConnections: () => void;
  onStartRun: () => void;
  onSelectBlueprint: (blueprint: AgentBlueprint, mode: AgentWorkspaceMode) => void;
}): AgentAttentionItem[] => {
  const items: AgentAttentionItem[] = [];
  const selectedLatestResult = findPreparedResultPayload(selectedDetails?.runs?.[0] || null, selectedPendingApproval);
  const selectedBlocker = isBusinessBlockerPayload(selectedLatestResult);
  if (selectedBlueprint && selectedBlocker) {
    const needsGoogle = resultPayloadStatus(selectedLatestResult) === 'needs_google_access';
    items.push({
      key: `${needsGoogle ? 'google-access' : 'blocked-result'}-${selectedBlueprint.id}`,
      tone: 'amber',
      problem: needsGoogle ? 'Нужен Google-доступ к таблице' : 'Нужен следующий шаг перед результатом',
      reason: needsGoogle
        ? `${selectedBlueprint.name}: Google не дал строки таблицы.`
        : `${selectedBlueprint.name}: сотрудник остановился до готового результата.`,
      actionLabel: needsGoogle ? 'Починить Google' : 'Посмотреть',
      action: onOpenResults,
    });
  }
  if (!selectedBlocker && selectedPendingApproval) {
    items.push({
      key: `approval-${selectedPendingApproval.id}`,
      tone: 'amber',
      problem: approvalDecisionTitle(selectedPendingApproval),
      reason: explainApproval(selectedPendingApproval),
      actionLabel: 'Посмотреть',
      action: onOpenResults,
    });
  }
  const missingCount = Number(selectedDetails?.activation_gate?.preflight?.missing_count || 0);
  if (selectedBlueprint && missingCount > 0) {
    items.push({
      key: `connections-${selectedBlueprint.id}`,
      tone: 'amber',
      problem: 'Нужно подключить данные',
      reason: `${selectedBlueprint.name}: ${missingCount} ${missingCount === 1 ? 'доступ ещё не готов' : 'доступа ещё не готовы'}.`,
      actionLabel: 'Подключить',
      action: onOpenConnections,
    });
  }
  if (selectedBlueprint?.last_run_status === 'failed') {
    items.push({
      key: `failed-${selectedBlueprint.id}`,
      tone: 'rose',
      problem: 'Последний запуск завершился ошибкой',
      reason: `${selectedBlueprint.name}: откройте результат и причину остановки.`,
      actionLabel: 'Открыть результат',
      action: onOpenResults,
    });
  }
  if (selectedBlueprint && selectedDetails?.activation_gate?.preview_run_status?.ready === false && !missingCount) {
    items.push({
      key: `preview-${selectedBlueprint.id}`,
      tone: 'sky',
      problem: 'Агент готов к безопасной проверке',
      reason: `${selectedBlueprint.name}: можно проверить сценарий без внешней отправки.`,
      actionLabel: 'Проверить',
      action: onStartRun,
    });
  }
  blueprints
    .filter((blueprint) => blueprint.id !== selectedBlueprint?.id)
    .filter((blueprint) => Number(blueprint.pending_approvals_count || 0) > 0 || blueprint.last_run_status === 'failed')
    .slice(0, Math.max(0, 4 - items.length))
    .forEach((blueprint) => {
      const failed = blueprint.last_run_status === 'failed';
      items.push({
        key: `list-${blueprint.id}`,
        tone: failed ? 'rose' : 'amber',
        problem: failed ? 'Ошибка в агенте' : 'Решение ждёт человека',
        reason: blueprint.name,
        actionLabel: failed ? 'Открыть результат' : 'Посмотреть',
        action: () => onSelectBlueprint(blueprint, 'results'),
      });
    });
  return items.slice(0, 4);
};

export const buildConfidenceFacts = (
  gate?: AgentActivationGate,
  integrations: AgentIntegration[] = [],
): AgentConfidenceFact[] => {
  const hasExternalApproval = gate?.approval_policy_status?.ready !== false;
  return [
    {
      key: 'logic',
      label: gate?.compiled_validation?.ready === false ? 'Сценарий нужно проверить' : 'Сценарий проверен',
      ready: gate?.compiled_validation?.ready !== false,
    },
    {
      key: 'connections',
      label: gate?.preflight?.ready === false ? 'Подключения требуют внимания' : 'Подключения проверены',
      ready: gate?.preflight?.ready !== false,
    },
    {
      key: 'approval',
      label: hasExternalApproval ? 'Перед внешним действием требуется подтверждение' : 'Нужно добавить ручное подтверждение',
      ready: hasExternalApproval,
    },
    {
      key: 'stable',
      label: 'Агент использует опубликованный сценарий и не меняет его сам',
      ready: true,
    },
    {
      key: 'integrations',
      label: integrations.length ? `${integrations.length} ${integrations.length === 1 ? 'доступ подключён' : 'доступа подключены'}` : 'Можно работать без лишних доступов',
      ready: true,
    },
  ];
};

export const buildScenarioPipeline = (
  blueprint: AgentBlueprint,
  details?: AgentBlueprintDetails | null,
  bindings: AgentIntegrationBindingStatus[] = [],
): AgentScenarioStep[] => {
  const preview = getBlueprintBuilderPreview(details?.blueprint || blueprint);
  const sourceText = preview?.data_sources?.length
    ? preview.data_sources.map((item) => userFacingAgentTechText(humanizeMeta(String(item || '')))).join(', ')
    : bindings.length
      ? Array.from(new Set(bindings.map((item) => connectorLabel(item.provider)))).join(', ')
      : 'данные бизнеса';
  const trigger = userFacingAgentTechText(String(preview?.trigger || (details?.active_version as Record<string, unknown> | null)?.trigger || 'manual.run'));
  const output = blueprint.category === 'outreach'
    ? 'подготовить список и черновики сообщений'
    : blueprint.category === 'reviews'
      ? 'подготовить ответы и решения по отзывам'
      : blueprint.category === 'services'
        ? 'подготовить предложения по услугам'
        : 'подготовить результат для проверки';
  return [
    {
      key: 'when',
      title: trigger || 'По запуску пользователя',
      description: 'LocalOS начинает работу только по опубликованному сценарию.',
    },
    {
      key: 'read',
      title: `Получить данные: ${sourceText}`,
      description: 'Агент берёт только разрешённые источники этого бизнеса.',
    },
    {
      key: 'prepare',
      title: userFacingAgentTechText(output),
      description: blueprint.description || blueprint.active_goal || blueprint.latest_goal || 'Собрать итог, который можно проверить.',
    },
    {
      key: 'approval',
      title: 'Попросить подтверждение перед внешним действием',
      description: 'Публикация, отправка и записи во внешние сервисы не выполняются без решения человека.',
    },
    {
      key: 'record',
      title: 'Сохранить результат и историю',
      description: 'Итог, решения и ошибки остаются в истории агента.',
    },
  ];
};

export const buildBusinessHistoryEvents = (
  details: AgentBlueprintDetails | null,
  activeRun: AgentRun | null,
) => {
  const events: Array<{ key: string; time: string; title: string; description: string; sort: number }> = [];
  const add = (key: string, dateValue: string | null | undefined, title: string, description: string) => {
    const date = dateValue ? new Date(dateValue) : null;
    events.push({
      key,
      time: dateValue ? formatShortDate(dateValue) : 'сейчас',
      title,
      description,
      sort: date && !Number.isNaN(date.getTime()) ? date.getTime() : Date.now(),
    });
  };
  (details?.runs || []).filter((run) => run.status !== 'superseded').slice(0, 8).forEach((run) => {
    const artifactCount = Number(run.observability?.artifacts?.count || run.artifacts?.length || 0);
    if (run.status === 'completed') {
      add(`run-${run.id}`, run.completed_at || run.started_at, 'Запуск завершён', artifactCount ? `Подготовлено результатов: ${artifactCount}.` : 'Агент сохранил итог работы.');
      return;
    }
    if (run.status === 'waiting_approval') {
      add(`run-${run.id}`, run.started_at, 'Ждёт решения человека', 'Агент остановился перед действием, которое нужно подтвердить.');
      return;
    }
    if (run.status === 'failed') {
      add(`run-${run.id}`, run.completed_at || run.started_at, 'Запуск остановился с ошибкой', run.error_text || 'Откройте технические подробности, если нужна диагностика.');
      return;
    }
    add(`run-${run.id}`, run.started_at, humanizeStatus(run.status), 'Агент обновил состояние работы.');
  });
  (details?.approval_queue || []).slice(0, 5).forEach((approval) => {
    add(`approval-${approval.id}`, approval.requested_at || approval.run_started_at, approvalDecisionTitle(approval), explainApproval(approval));
  });
  (activeRun?.artifacts || []).slice(0, 5).forEach((artifact) => {
    add(`artifact-${artifact.id}`, activeRun.completed_at || activeRun.started_at, artifact.title || 'Подготовлен результат', userFacingAgentTechText(humanizeMeta(artifact.artifact_type || 'result')));
  });
  (activeRun?.steps || []).forEach((step) => {
    if (step.status !== 'completed') {
      return;
    }
    if (step.step_key === 'read_google_sheets') {
      add(`step-${step.id}`, activeRun.completed_at || activeRun.started_at, 'Прочитал таблицу поездок', 'Получил строки из подключённой Google-таблицы.');
    }
    if (step.step_key === 'prepare_output') {
      add(`step-${step.id}`, activeRun.completed_at || activeRun.started_at, 'Подготовил результат', 'Собрал текст только из данных выбранной строки.');
    }
    if (step.step_key === 'save_content_plan_draft') {
      add(`step-${step.id}`, activeRun.completed_at || activeRun.started_at, 'Сохранил черновик', 'Добавил результат в контент-план LocalOS.');
    }
  });
  return events
    .sort((a, b) => b.sort - a.sort)
    .slice(0, 12);
};

export const humanizeSourceType = (sourceType?: string) => ({
  text: 'Текст',
  file: 'Файл',
  internal: 'Источник LocalOS',
}[sourceType || ''] || 'Источник');

export const humanizeSourceState = (state?: string) => ({
  ready: 'готово',
  available: 'доступно',
  empty: 'нет данных',
  unsupported_file_type: 'неподдерживаемый файл',
  needs_text_export: 'нужно извлечь текст',
  extraction_failed: 'не удалось прочитать',
}[state || ''] || state || 'готово');

export const formatSourceSize = (chars?: number, bytes?: number) => {
  if (typeof chars === 'number' && chars > 0) {
    return `${chars} знаков`;
  }
  if (typeof bytes === 'number' && bytes > 0) {
    return bytes >= 1024 ? `${Math.round(bytes / 1024)} KB` : `${bytes} B`;
  }
  return 'без текста';
};
