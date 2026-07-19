import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useOutletContext } from 'react-router-dom';
import { Bot, Zap } from 'lucide-react';
import { newAuth } from '@/lib/auth_new';
import { api } from '@/services/api';
import type {
  DashboardContext, AgentBlueprint, AgentRun, AgentServerTodaySummary, AgentBlueprintDetails, AgentLearningLoop,
  AgentSourceCatalogItem, AgentIntegration, AgentExternalAuthOption, AgentIntegrationCatalogItem, AgentIntegrationBindingStatus, AgentProviderRoute,
  AgentConnectionPlan, AgentPostCreateHandoff, AgentReview, AgentBuilderScenario, PersonaAgent, LegacyMigrationPlan,
  AgentWorkspaceMode, AgentExecutionMode, AgentRegistryFilter, AgentRunAnimation, FeedbackVersionNotice, AgentBuilderSession
} from './agents/types';
import {
  getRequestErrorMessage, recordValue, normalizeSpreadsheetInput, normalizePostCreateHandoff, normalizeAgentIntegrationPreflight, normalizeConnectionPlan,
  formatPreflightBlock, connectorLabel, autoSelectBuilderConnectionBindings, autoSelectBuilderProviderRoutes
} from './agents/normalization';
import {
  getPreviewVersionId, agentExecutionMode, workflowStepsForAnimation, learningTriggerOptions, agentScenarios, humanizeMeta,
  getAgentListStatus, buildTodaySummary, initialRunParameters, validateRunParameters, buildEmployeeDescription, buildEmployeeWorkspaceState,
  buildEmployeeNextAction
} from './agents/model';
import { isAgentWorkRun, isBusinessBlockerApproval, needsScenarioRebuildForSourceResult, needsGoogleSheetsSourceSetup, needsGoogleAccessReconnect, hasFreshGoogleSheetsAccessAfterResult } from './agents/results';
import { parseAgentConfig, uploadAgentSource } from './agents/api';
import { AgentBlueprintsView } from './agents/view';

export const AgentBlueprintsPage = () => {
  const location = useLocation();
  const { currentBusinessId, currentBusiness } = useOutletContext<DashboardContext>();
  const [blueprints, setBlueprints] = useState<AgentBlueprint[]>([]);
  const [selectedBlueprintId, setSelectedBlueprintId] = useState<string | null>(null);
  const [blueprintDetails, setBlueprintDetails] = useState<AgentBlueprintDetails | null>(null);
  const [agentDetailsById, setAgentDetailsById] = useState<Record<string, AgentBlueprintDetails>>({});
  const [serverTodaySummary, setServerTodaySummary] = useState<AgentServerTodaySummary | null>(null);
  const [activeRun, setActiveRun] = useState<AgentRun | null>(null);
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [agentSearch, setAgentSearch] = useState('');
  const [agentRegistryFilter, setAgentRegistryFilter] = useState<AgentRegistryFilter>('all');
  const [runAnimation, setRunAnimation] = useState<AgentRunAnimation | null>(null);
  const [runStatusFilter, setRunStatusFilter] = useState('all');
  const [runSource, setRunSource] = useState('dashboard');
  const [runCity, setRunCity] = useState('');
  const [runCategory, setRunCategory] = useState('');
  const [runLimit, setRunLimit] = useState('30');
  const [runParameters, setRunParameters] = useState<Record<string, unknown>>({});
  const [runParameterErrors, setRunParameterErrors] = useState<Record<string, string>>({});
  const [createWizardOpen, setCreateWizardOpen] = useState(false);
  const [createWizardStep, setCreateWizardStep] = useState(0);
  const [workspaceMode, setWorkspaceMode] = useState<AgentWorkspaceMode>('overview');
  const [availablePersonaAgents, setAvailablePersonaAgents] = useState<PersonaAgent[]>([]);
  const [agentPrompt, setAgentPrompt] = useState('');
  const [builderCategory, setBuilderCategory] = useState('documents');
  const [builderDataSources, setBuilderDataSources] = useState('файл документа, ручной контекст, профиль бизнеса');
  const [builderExtractionRules, setBuilderExtractionRules] = useState('ключевые условия, сроки, суммы, ответственность, спорные места');
  const [builderProcessingRules, setBuilderProcessingRules] = useState('не придумывать факты, ссылаться только на добавленные данные, отдельно показывать риски');
  const [builderOutputFormat, setBuilderOutputFormat] = useState('краткий отчёт: summary, риски, что уточнить, черновик письма при необходимости');
  const [builderManualControl, setBuilderManualControl] = useState('перед использованием результата и перед любым внешним действием');
  const [builderExecutionMode, setBuilderExecutionMode] = useState<AgentExecutionMode>('manual');
  const [builderExecutionModeConfirmed, setBuilderExecutionModeConfirmed] = useState(false);
  const [cloneFromBlueprintId, setCloneFromBlueprintId] = useState('');
  const [builderSourceName, setBuilderSourceName] = useState('');
  const [builderSourceText, setBuilderSourceText] = useState('');
  const [builderFileSource, setBuilderFileSource] = useState<File | null>(null);
  const [builderInternalSource, setBuilderInternalSource] = useState('business_profile');
  const [dialogBuilderInput, setDialogBuilderInput] = useState('');
  const [dialogBuilderReply, setDialogBuilderReply] = useState('');
  const [dialogBuilderSession, setDialogBuilderSession] = useState<AgentBuilderSession | null>(null);
  const [selectedBuilderConnectionBindings, setSelectedBuilderConnectionBindings] = useState<Record<string, string>>({});
  const [selectedBuilderProviderRoutes, setSelectedBuilderProviderRoutes] = useState<Record<string, string>>({});
  const [acceptedBuilderCompilerPlan, setAcceptedBuilderCompilerPlan] = useState(false);
  const [acceptedBuilderProviderRoutes, setAcceptedBuilderProviderRoutes] = useState(false);
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
  const [agentIntegrations, setAgentIntegrations] = useState<AgentIntegration[]>([]);
  const [availableAgentIntegrations, setAvailableAgentIntegrations] = useState<AgentIntegration[]>([]);
  const [agentIntegrationCatalog, setAgentIntegrationCatalog] = useState<AgentIntegrationCatalogItem[]>([]);
  const [agentExternalAuthOptions, setAgentExternalAuthOptions] = useState<AgentExternalAuthOption[]>([]);
  const [agentBindingStatus, setAgentBindingStatus] = useState<AgentIntegrationBindingStatus[]>([]);
  const [agentConnectionPlan, setAgentConnectionPlan] = useState<AgentConnectionPlan | null>(null);
  const [selectedConnectionBindingKey, setSelectedConnectionBindingKey] = useState('');
  const [sheetSpreadsheetId, setSheetSpreadsheetId] = useState('');
  const [sheetName, setSheetName] = useState('Sheet1');
  const [sheetAuthRef, setSheetAuthRef] = useState('');
  const [sheetDailyCap, setSheetDailyCap] = useState('50');
  const [browserTargetUrls, setBrowserTargetUrls] = useState('');
  const [browserDailyCap, setBrowserDailyCap] = useState('50');
  const [telegramBotMode, setTelegramBotMode] = useState('business_bot');
  const [telegramDailyCap, setTelegramDailyCap] = useState('50');
  const [whatsappChannelMode, setWhatsappChannelMode] = useState('whatsapp_business');
  const [whatsappDailyCap, setWhatsappDailyCap] = useState('50');
  const [matonAuthRef, setMatonAuthRef] = useState('');
  const [matonChannel, setMatonChannel] = useState('maton_bridge');
  const [matonDailyCap, setMatonDailyCap] = useState('50');
  const [processRowValues, setProcessRowValues] = useState('{{received_at}}, {{telegram_username}}, {{message_text}}');
  const [processPreviewMessage, setProcessPreviewMessage] = useState('Новая заявка: Анна, телефон +7 900 000-00-00, хочет консультацию');
  const [scheduleTime, setScheduleTime] = useState('09:00');
  const [scheduleTimezone, setScheduleTimezone] = useState('Europe/Moscow');
  const [selectedExecutionMode, setSelectedExecutionMode] = useState<AgentExecutionMode>('manual');
  const [feedbackText, setFeedbackText] = useState('');
  const [feedbackTrigger, setFeedbackTrigger] = useState('manual_edit');
  const [feedbackVersionNotice, setFeedbackVersionNotice] = useState<FeedbackVersionNotice | null>(null);
  const [systemAgentConfig, setSystemAgentConfig] = useState<Record<string, { enabled?: boolean }>>({});
  const [legacyMigrationPlan, setLegacyMigrationPlan] = useState<LegacyMigrationPlan | null>(null);
  const [legacyMigrationNotice, setLegacyMigrationNotice] = useState('');
  const [recentCreatedAgentName, setRecentCreatedAgentName] = useState('');
  const [recentPostCreateHandoff, setRecentPostCreateHandoff] = useState<AgentPostCreateHandoff | null>(null);
  const [showAdvancedAgentTools, setShowAdvancedAgentTools] = useState(false);
  const [deleteCandidate, setDeleteCandidate] = useState<AgentBlueprint | null>(null);
  const [decisionNotice, setDecisionNotice] = useState<string | null>(null);
  const googleAuthStatus = useMemo(() => {
    const params = new URLSearchParams(location.search);
    return params.get('google_auth');
  }, [location.search]);
  const googleAccessJustConnected = googleAuthStatus === 'success';

  useEffect(() => {
    setSystemAgentConfig(parseAgentConfig(currentBusiness));
  }, [currentBusiness]);

  useEffect(() => {
    let mounted = true;
    const syncUserRole = async () => {
      const cachedUser = newAuth.getCurrentUserSync();
      if (mounted) {
        setShowAdvancedAgentTools(Boolean(cachedUser?.is_superadmin));
      }
      const user = await newAuth.getCurrentUser();
      if (mounted) {
        setShowAdvancedAgentTools(Boolean(user?.is_superadmin));
      }
    };
    void syncUserRole();
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    if (!showAdvancedAgentTools && workspaceMode === 'advanced') {
      setWorkspaceMode('overview');
    }
  }, [showAdvancedAgentTools, workspaceMode]);

  useEffect(() => {
    if (!googleAccessJustConnected) {
      return;
    }
    setDecisionNotice('Google-доступ подключён. Теперь запустите тест ещё раз, чтобы проверить таблицу на свежем доступе.');
    setWorkspaceMode((currentMode) => (currentMode === 'overview' ? 'results' : currentMode));
  }, [googleAccessJustConnected]);

  const selectedBlueprint = useMemo(
    () => blueprints.find((item) => item.id === selectedBlueprintId) || blueprints[0] || null,
    [blueprints, selectedBlueprintId],
  );

  useEffect(() => {
    const metadata = selectedBlueprint?.metadata_json;
    const customProcess = recordValue(metadata?.custom_process);
    const schedule = recordValue(customProcess?.schedule);
    if (schedule && typeof schedule.time === 'string' && schedule.time) {
      setScheduleTime(schedule.time);
    }
    if (schedule && typeof schedule.timezone === 'string' && schedule.timezone && schedule.timezone !== 'business_timezone') {
      setScheduleTimezone(schedule.timezone);
    } else if ((currentBusiness?.name || '').toLowerCase().includes('tallinn')) {
      setScheduleTimezone('Europe/Tallinn');
    }
    if (selectedBlueprint) {
      setSelectedExecutionMode(agentExecutionMode(selectedBlueprint, blueprintDetails));
    }
  }, [blueprintDetails?.execution_mode, currentBusiness?.name, selectedBlueprint]);

  const pendingApproval = useMemo(
    () => activeRun?.approvals?.find((item) => item.status === 'pending') || null,
    [activeRun],
  );

  const activeRunPendingApprovals = useMemo(
    () => (activeRun?.approvals || []).filter((item) => item.status === 'pending' && !isBusinessBlockerApproval(item)),
    [activeRun?.approvals],
  );

  const actionablePendingApproval = activeRunPendingApprovals[0] || null;

  const rawPendingApprovals = useMemo(
    () => {
      const latestRunId = blueprintDetails?.runs?.[0]?.id || '';
      return (blueprintDetails?.approval_queue || []).filter((item) => (
        item.status === 'pending' && (!latestRunId || item.run_id === latestRunId)
      ));
    },
    [blueprintDetails?.approval_queue, blueprintDetails?.runs],
  );

  const pendingApprovals = useMemo(
    () => rawPendingApprovals.filter((item) => !isBusinessBlockerApproval(item)),
    [rawPendingApprovals],
  );

  const selectedPendingApproval = useMemo(
    () => pendingApproval || rawPendingApprovals[0] || null,
    [pendingApproval, rawPendingApprovals],
  );

  const selectedActionablePendingApproval = useMemo(
    () => actionablePendingApproval || pendingApprovals[0] || null,
    [actionablePendingApproval, pendingApprovals],
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
    () => systemAgents.filter((item) => item.enabled).length + blueprints.filter((item) => getAgentListStatus(item) === 'active').length,
    [blueprints, systemAgents],
  );

  const totalPendingApprovals = useMemo(
    () => blueprints.reduce((sum, item) => sum + Number(item.pending_approvals_count || 0), 0),
    [blueprints],
  );

  const migrationStats = useMemo(() => {
    const legacyAgents = legacyMigrationPlan?.legacy_agents || [];
    const businessFields = legacyMigrationPlan?.business_settings?.fields || {};
    return {
      totalLegacyAgents: legacyAgents.length,
      linkedVoices: legacyAgents.filter((item) => item.action === 'use_as_persona').length,
      needsBlueprint: legacyAgents.filter((item) => item.action === 'create_blueprint_candidate').length,
      archiveCandidates: legacyAgents.filter((item) => item.action === 'archive_candidate').length,
      deprecatedFieldsPresent: Object.values(businessFields).filter((item) => item.present).length,
      legacyWorkflowPresent: legacyAgents.filter((item) => item.legacy_workflow?.present).length,
    };
  }, [legacyMigrationPlan]);

  const applyBuilderScenario = (scenario: AgentBuilderScenario) => {
    setBuilderCategory(scenario.category);
    setAgentPrompt(scenario.prompt);
    setBuilderDataSources(scenario.dataSources);
    setBuilderExtractionRules(scenario.extraction);
    setBuilderProcessingRules(scenario.processing);
    setBuilderOutputFormat(scenario.output);
    setBuilderManualControl(scenario.manualControl);
  };

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
      setServerTodaySummary(response.data?.today_summary && typeof response.data.today_summary === 'object'
        ? response.data.today_summary
        : null);
      if (!selectedBlueprintId && items.length > 0) {
        setSelectedBlueprintId(items[0].id);
      }
    } catch (requestError) {
      console.error(requestError);
      setError('Не удалось загрузить агентов.');
    } finally {
      setLoading(false);
    }
  }, [currentBusinessId, selectedBlueprintId]);

  useEffect(() => {
    void loadBlueprints();
  }, [loadBlueprints]);

  const loadLegacyMigrationPlan = useCallback(async () => {
    if (!currentBusinessId) {
      setLegacyMigrationPlan(null);
      return;
    }
    try {
      const response = await api.get('/agent-blueprints/legacy-migration-plan', { params: { business_id: currentBusinessId } });
      setLegacyMigrationPlan(response.data?.migration_plan || null);
    } catch (requestError) {
      console.error(requestError);
      setLegacyMigrationPlan(null);
    }
  }, [currentBusinessId]);

  useEffect(() => {
    void loadLegacyMigrationPlan();
  }, [loadLegacyMigrationPlan]);

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
        blueprint: response.data?.blueprint && typeof response.data.blueprint === 'object' ? response.data.blueprint : undefined,
        versions: Array.isArray(response.data?.versions) ? response.data.versions : [],
        runs: Array.isArray(response.data?.runs) ? response.data.runs : [],
        approval_queue: Array.isArray(response.data?.approval_queue) ? response.data.approval_queue : [],
        active_version: response.data?.active_version || null,
        active_version_id: typeof response.data?.active_version_id === 'string' ? response.data.active_version_id : '',
        active_version_number: typeof response.data?.active_version_number === 'number' ? response.data.active_version_number : 0,
        candidate_version: response.data?.candidate_version || null,
        candidate_version_id: typeof response.data?.candidate_version_id === 'string' ? response.data.candidate_version_id : '',
        run_input_schema: response.data?.run_input_schema && typeof response.data.run_input_schema === 'object' ? response.data.run_input_schema : undefined,
        candidate_run_input_schema: response.data?.candidate_run_input_schema && typeof response.data.candidate_run_input_schema === 'object' ? response.data.candidate_run_input_schema : undefined,
        active_run_input_schema: response.data?.active_run_input_schema && typeof response.data.active_run_input_schema === 'object' ? response.data.active_run_input_schema : undefined,
        execution_mode: response.data?.execution_mode,
        execution_mode_source: response.data?.execution_mode_source,
        execution_mode_confirmation_required: response.data?.execution_mode_confirmation_required === true,
        lifecycle_state: response.data?.lifecycle_state,
        last_business_result: response.data?.last_business_result && typeof response.data.last_business_result === 'object' ? response.data.last_business_result : null,
        next_run_at: typeof response.data?.next_run_at === 'string' ? response.data.next_run_at : null,
        learning_events: Array.isArray(response.data?.learning_events) ? response.data.learning_events : [],
        version_events: Array.isArray(response.data?.version_events) ? response.data.version_events : [],
        feedback_history: Array.isArray(response.data?.feedback_history) ? response.data.feedback_history : [],
        legacy_migration: response.data?.legacy_migration || {},
        metrics: response.data?.metrics && typeof response.data.metrics === 'object' ? response.data.metrics : undefined,
        activation_gate: response.data?.activation_gate && typeof response.data.activation_gate === 'object' ? response.data.activation_gate : undefined,
        execution_contract: response.data?.execution_contract && typeof response.data.execution_contract === 'object' ? response.data.execution_contract : undefined,
      };
      setBlueprintDetails(details);
      setAgentDetailsById((current) => ({
        ...current,
        [blueprintId]: details,
      }));
    } catch (requestError) {
      console.error(requestError);
      setError('Не удалось загрузить историю агента.');
    }
  }, [runStatusFilter]);

  useEffect(() => {
    if (selectedBlueprint?.id) {
      setBlueprintDetails(null);
      setActiveRun(null);
      void loadBlueprintDetails(selectedBlueprint.id);
    } else {
      setBlueprintDetails(null);
      setActiveRun(null);
    }
  }, [loadBlueprintDetails, selectedBlueprint?.id]);

  useEffect(() => {
    const previousWorkRun = (blueprintDetails?.runs || []).find((run) => isAgentWorkRun(run));
    const schema = blueprintDetails?.active_version_id
      ? blueprintDetails.active_run_input_schema
      : blueprintDetails?.candidate_run_input_schema || blueprintDetails?.run_input_schema;
    setRunParameters(initialRunParameters(schema, previousWorkRun?.input_json));
    setRunParameterErrors({});
  }, [blueprintDetails?.candidate_version_id, blueprintDetails?.active_version_id, selectedBlueprint?.id]);

  useEffect(() => {
    if (!currentBusinessId || !blueprints.length) {
      return;
    }
    const missing = blueprints
      .slice(0, 6)
      .filter((blueprint) => !agentDetailsById[blueprint.id])
      .map((blueprint) => blueprint.id);
    if (!missing.length) {
      return;
    }
    let cancelled = false;
    const loadRecentDetails = async () => {
      try {
        const responses = await Promise.all(
          missing.map((blueprintId) => api.get(`/agent-blueprints/${blueprintId}`, { params: { run_status: 'all' } })),
        );
        if (cancelled) {
          return;
        }
        setAgentDetailsById((current) => {
          const next = { ...current };
          responses.forEach((response, index) => {
            const blueprintId = missing[index];
            next[blueprintId] = {
              blueprint: response.data?.blueprint && typeof response.data.blueprint === 'object' ? response.data.blueprint : undefined,
              versions: Array.isArray(response.data?.versions) ? response.data.versions : [],
              runs: Array.isArray(response.data?.runs) ? response.data.runs : [],
              approval_queue: Array.isArray(response.data?.approval_queue) ? response.data.approval_queue : [],
              active_version: response.data?.active_version || null,
              active_version_id: typeof response.data?.active_version_id === 'string' ? response.data.active_version_id : '',
              active_version_number: typeof response.data?.active_version_number === 'number' ? response.data.active_version_number : 0,
              candidate_version: response.data?.candidate_version || null,
              candidate_version_id: typeof response.data?.candidate_version_id === 'string' ? response.data.candidate_version_id : '',
              run_input_schema: response.data?.run_input_schema && typeof response.data.run_input_schema === 'object' ? response.data.run_input_schema : undefined,
              candidate_run_input_schema: response.data?.candidate_run_input_schema && typeof response.data.candidate_run_input_schema === 'object' ? response.data.candidate_run_input_schema : undefined,
              active_run_input_schema: response.data?.active_run_input_schema && typeof response.data.active_run_input_schema === 'object' ? response.data.active_run_input_schema : undefined,
              execution_mode: response.data?.execution_mode,
              execution_mode_source: response.data?.execution_mode_source,
              execution_mode_confirmation_required: response.data?.execution_mode_confirmation_required === true,
              lifecycle_state: response.data?.lifecycle_state,
              last_business_result: response.data?.last_business_result && typeof response.data.last_business_result === 'object' ? response.data.last_business_result : null,
              next_run_at: typeof response.data?.next_run_at === 'string' ? response.data.next_run_at : null,
              learning_events: Array.isArray(response.data?.learning_events) ? response.data.learning_events : [],
              version_events: Array.isArray(response.data?.version_events) ? response.data.version_events : [],
              feedback_history: Array.isArray(response.data?.feedback_history) ? response.data.feedback_history : [],
              legacy_migration: response.data?.legacy_migration || {},
              metrics: response.data?.metrics && typeof response.data.metrics === 'object' ? response.data.metrics : undefined,
              activation_gate: response.data?.activation_gate && typeof response.data.activation_gate === 'object' ? response.data.activation_gate : undefined,
              execution_contract: response.data?.execution_contract && typeof response.data.execution_contract === 'object' ? response.data.execution_contract : undefined,
            };
          });
          return next;
        });
      } catch (requestError) {
        console.error(requestError);
      }
    };
    void loadRecentDetails();
    return () => {
      cancelled = true;
    };
  }, [agentDetailsById, blueprints, currentBusinessId]);

  const loadRun = async (runId: string, options: { openResults?: boolean; showLoading?: boolean } = {}) => {
    const openResults = options.openResults !== false;
    const showLoading = options.showLoading !== false;
    if (showLoading) {
      setActionLoading(true);
    }
    setError(null);
    try {
      const response = await api.get(`/agent-runs/${runId}`);
      setActiveRun(response.data?.run || null);
      if (openResults) {
        setWorkspaceMode('results');
      }
      if (selectedBlueprint?.id) {
        await loadBlueprintDetails(selectedBlueprint.id);
        await loadBlueprintReview(selectedBlueprint.id);
      }
    } catch (requestError) {
      console.error(requestError);
      setError('Не удалось загрузить запуск.');
    } finally {
      if (showLoading) {
        setActionLoading(false);
      }
    }
  };

  useEffect(() => {
    if (runAnimation || !selectedBlueprint?.id) return;
    const inflight = (blueprintDetails?.runs || []).find((run) => ['queued', 'running', 'retry_wait'].includes(String(run.status || '')));
    if (!inflight?.id) return;
    let cancelled = false;
    void api.get(`/agent-runs/${inflight.id}`).then((response) => {
      if (cancelled) return;
      const run: AgentRun | null = response.data?.run && typeof response.data.run === 'object' ? response.data.run : null;
      if (!run) return;
      const kind: AgentRunAnimation['kind'] = isAgentWorkRun(run) ? 'work' : 'test';
      const steps = workflowStepsForAnimation(blueprintDetails, kind);
      const total = Math.max(steps.length, Number(run.progress?.total_steps || 0), 1);
      const completed = Math.min(total, Math.max(0, Number(run.progress?.completed_steps || 0)));
      const currentIndex = Math.min(total - 1, Math.max(0, Number(run.progress?.current_step_index ?? completed)));
      setActiveRun(run);
      setRunAnimation({
        kind,
        blueprintId: selectedBlueprint.id,
        runId: run.id,
        startedAt: Date.parse(String(run.queued_at || run.started_at || '')) || Date.now(),
        progress: Math.max(8, Math.min(92, Math.round((completed / total) * 92))),
        stepIndex: currentIndex,
        steps,
        status: 'running',
        serverCompletedSteps: completed,
        serverCurrentStepIndex: currentIndex,
        queueState: String(run.progress?.state || run.status || 'queued'),
        recoveredFromReload: true,
      });
    }).catch((requestError) => console.error(requestError));
    return () => { cancelled = true; };
  }, [blueprintDetails?.runs, runAnimation, selectedBlueprint?.id]);

  const loadBlueprintReview = useCallback(async (blueprintId: string) => {
    try {
      const response = await api.get(`/agent-blueprints/${blueprintId}/review`);
      setAgentReview(response.data?.review || null);
    } catch (requestError) {
      console.error(requestError);
    }
  }, []);

  useEffect(() => {
    const latestRun = blueprintDetails?.runs?.[0];
    if (!latestRun?.id || activeRun) {
      return;
    }
    if (!['completed', 'waiting_approval', 'failed'].includes(latestRun.status || '')) {
      return;
    }
    void loadRun(latestRun.id, { openResults: false, showLoading: false });
  }, [activeRun, blueprintDetails?.runs]);

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

  const loadAgentIntegrations = useCallback(async (blueprintId: string) => {
    try {
      const response = await api.get(`/agent-blueprints/${blueprintId}/integrations`);
      const integrations = Array.isArray(response.data?.integrations) ? response.data.integrations : [];
      const available = Array.isArray(response.data?.available_integrations) ? response.data.available_integrations : [];
      const providerCatalog = Array.isArray(response.data?.provider_catalog) ? response.data.provider_catalog : [];
      const authOptions = Array.isArray(response.data?.external_auth_options) ? response.data.external_auth_options : [];
      const bindingStatus = Array.isArray(response.data?.binding_status) ? response.data.binding_status : [];
      const connectionPlan = normalizeConnectionPlan(response.data?.connection_plan);
      const customProcess = response.data?.custom_process && typeof response.data.custom_process === 'object' ? response.data.custom_process : {};
      setAgentIntegrations(integrations);
      setAvailableAgentIntegrations(available);
      setAgentIntegrationCatalog(providerCatalog);
      setAgentExternalAuthOptions(authOptions);
      setAgentBindingStatus(bindingStatus);
      setAgentConnectionPlan(connectionPlan);
      const selectedBindingStillExists = bindingStatus.some((binding) => binding.key === selectedConnectionBindingKey);
      if (selectedConnectionBindingKey && !selectedBindingStillExists) {
        setSelectedConnectionBindingKey('');
      }
      if (Array.isArray(customProcess.row_values)) {
        setProcessRowValues(customProcess.row_values.map((item) => String(item || '').trim()).filter(Boolean).join(', '));
      }
      const sheet = integrations.find((item) => item.provider === 'google_sheets') || available.find((item) => item.provider === 'google_sheets');
      if (sheet) {
        setSheetSpreadsheetId(String(sheet.config?.spreadsheet_id || ''));
        setSheetName(String(sheet.config?.sheet_name || 'Sheet1'));
        setSheetAuthRef(String(sheet.auth_ref || ''));
        setSheetDailyCap(String(sheet.limits?.daily_append_cap || 50));
      }
      const telegram = integrations.find((item) => item.provider === 'telegram') || available.find((item) => item.provider === 'telegram');
      if (telegram) {
        setTelegramBotMode(String(telegram.config?.bot_mode || 'business_bot'));
        setTelegramDailyCap(String(telegram.limits?.daily_message_cap || 50));
      }
      const maton = integrations.find((item) => item.provider === 'maton') || available.find((item) => item.provider === 'maton');
      const matonAuth = authOptions.find((item) => item.source === 'maton');
      if (maton || matonAuth) {
        setMatonAuthRef(String(maton?.auth_ref || matonAuth?.id || ''));
        setMatonChannel(String(maton?.config?.channel || 'maton_bridge'));
        setMatonDailyCap(String(maton?.limits?.daily_message_cap || 50));
      }
    } catch (requestError) {
      console.error(requestError);
      setAgentIntegrations([]);
      setAvailableAgentIntegrations([]);
      setAgentIntegrationCatalog([]);
      setAgentExternalAuthOptions([]);
      setAgentBindingStatus([]);
      setAgentConnectionPlan(null);
      setSelectedConnectionBindingKey('');
    }
  }, [selectedConnectionBindingKey]);

  const applyPostConnectHandoff = (value: unknown) => {
    const handoff = normalizePostCreateHandoff(value);
    if (!handoff) {
      return;
    }
    setRecentPostCreateHandoff(handoff);
    if (handoff.workspace_mode === 'run') {
      setSelectedConnectionBindingKey('');
      setWorkspaceMode('run');
    } else if (handoff.workspace_mode === 'connections') {
      if (handoff.next_binding_key) {
        setSelectedConnectionBindingKey(handoff.next_binding_key);
      }
      setWorkspaceMode('connections');
    }
  };

  useEffect(() => {
    if (selectedBlueprint?.id) {
      void loadBlueprintReview(selectedBlueprint.id);
      void loadSourceCatalog(selectedBlueprint.id);
      void loadAgentIntegrations(selectedBlueprint.id);
    } else {
      setAgentReview(null);
      setSourceCatalog([]);
      setAgentIntegrations([]);
      setAvailableAgentIntegrations([]);
      setAgentIntegrationCatalog([]);
      setAgentExternalAuthOptions([]);
      setAgentBindingStatus([]);
      setSelectedConnectionBindingKey('');
    }
  }, [loadAgentIntegrations, loadBlueprintReview, loadSourceCatalog, selectedBlueprint?.id]);

  const createDefaultBlueprint = async (requestText = '') => {
    if (!currentBusinessId) {
      return;
    }
    setActionLoading(true);
    setError(null);
    setDecisionNotice(null);
    try {
      const response = await api.post('/agent-blueprints', {
        business_id: currentBusinessId,
        name: requestText.trim() ? requestText.trim().slice(0, 80) : 'Агент поиска клиентов',
        category: 'outreach',
        description: requestText.trim() || 'Ищет лиды, готовит список и черновики, внешние отправки только через ручное подтверждение.',
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
        await loadAgentIntegrations(blueprint.id);
        setRecentCreatedAgentName(String(blueprint.name || 'Новый агент'));
        setWorkspaceMode('overview');
      }
    } catch (requestError) {
      console.error(requestError);
      setError('Не удалось создать агента поиска клиентов.');
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
    setDecisionNotice(null);
    try {
      const response = await api.post('/agent-builder/sessions', {
        business_id: currentBusinessId,
        message: dialogBuilderInput.trim(),
        use_ai_compiler: true,
      });
      const preview = response.data?.session?.preview || null;
      const autoProviderRoutes = autoSelectBuilderProviderRoutes(preview);
      setDialogBuilderSession(response.data?.session || null);
      setSelectedBuilderConnectionBindings(autoSelectBuilderConnectionBindings(preview));
      setSelectedBuilderProviderRoutes(autoProviderRoutes);
      setAcceptedBuilderCompilerPlan(false);
      setAcceptedBuilderProviderRoutes(Object.keys(autoProviderRoutes).length > 0);
      setBuilderExecutionMode(String(preview?.compiler_workflow_draft?.trigger || '').includes('schedule') ? 'scheduled' : 'manual');
      setBuilderExecutionModeConfirmed(false);
      setAgentPrompt(dialogBuilderInput.trim());
      if (preview && typeof preview.category === 'string') {
        setBuilderCategory(preview.category);
      }
      if (preview && Array.isArray(preview.data_sources)) {
        setBuilderDataSources(preview.data_sources.join(', '));
      }
      if (preview && typeof preview.extraction_rules === 'string') {
        setBuilderExtractionRules(preview.extraction_rules);
      }
      if (preview && typeof preview.processing_rules === 'string') {
        setBuilderProcessingRules(preview.processing_rules);
      }
      if (preview && typeof preview.output_format === 'string') {
        setBuilderOutputFormat(preview.output_format);
      }
      if (preview && typeof preview.manual_control === 'string') {
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
        use_ai_compiler: true,
      });
      const preview = response.data?.session?.preview || null;
      const autoProviderRoutes = autoSelectBuilderProviderRoutes(preview);
      setDialogBuilderSession(response.data?.session || null);
      setSelectedBuilderConnectionBindings(autoSelectBuilderConnectionBindings(preview));
      setSelectedBuilderProviderRoutes(autoProviderRoutes);
      setAcceptedBuilderCompilerPlan(false);
      setAcceptedBuilderProviderRoutes(Object.keys(autoProviderRoutes).length > 0);
      setBuilderExecutionMode(String(preview?.compiler_workflow_draft?.trigger || '').includes('schedule') ? 'scheduled' : builderExecutionMode);
      setBuilderExecutionModeConfirmed(false);
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
      const response = await api.post(`/agent-builder/sessions/${dialogBuilderSession.id}/create-blueprint`, {
        use_ai_compiler: true,
        selected_connection_bindings: selectedBuilderConnectionBindings,
        selected_provider_routes: acceptedBuilderProviderRoutes ? selectedBuilderProviderRoutes : {},
        accepted_compiler_plan: acceptedBuilderCompilerPlan,
        accepted_provider_routes: acceptedBuilderProviderRoutes,
        execution_mode: builderExecutionMode,
        schedule_time: builderExecutionMode === 'scheduled' ? scheduleTime : undefined,
        schedule_timezone: builderExecutionMode === 'scheduled' ? scheduleTimezone : undefined,
        clone_from_blueprint_id: cloneFromBlueprintId || undefined,
      });
      const blueprint = response.data?.blueprint;
      const handoff = normalizePostCreateHandoff(response.data?.post_create_handoff);
      await loadBlueprints();
      if (blueprint?.id) {
        setSelectedBlueprintId(blueprint.id);
        await loadBlueprintDetails(blueprint.id);
        await loadBlueprintReview(blueprint.id);
        await loadSourceCatalog(blueprint.id);
        await loadAgentIntegrations(blueprint.id);
        setRecentCreatedAgentName(String(blueprint.name || 'Новый агент'));
        setRecentPostCreateHandoff(handoff);
        if (handoff?.workspace_mode === 'run') {
          setSelectedConnectionBindingKey('');
        } else if (handoff?.next_binding_key) {
          setSelectedConnectionBindingKey(handoff.next_binding_key);
        }
        setWorkspaceMode('overview');
      }
      setDialogBuilderInput('');
      setDialogBuilderReply('');
      setDialogBuilderSession(null);
      setSelectedBuilderConnectionBindings({});
      setSelectedBuilderProviderRoutes({});
      setAcceptedBuilderCompilerPlan(false);
      setAcceptedBuilderProviderRoutes(false);
      setBuilderExecutionModeConfirmed(false);
      setCloneFromBlueprintId('');
      setCreateWizardOpen(false);
      setWorkspaceMode('overview');
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
        execution_mode: builderExecutionMode,
        schedule_time: builderExecutionMode === 'scheduled' ? scheduleTime : undefined,
        schedule_timezone: builderExecutionMode === 'scheduled' ? scheduleTimezone : undefined,
        clone_from_blueprint_id: cloneFromBlueprintId || undefined,
      });
      const blueprint = response.data?.blueprint;
      const handoff = normalizePostCreateHandoff(response.data?.post_create_handoff);
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
        await loadSourceCatalog(blueprint.id);
        await loadAgentIntegrations(blueprint.id);
        setRecentCreatedAgentName(String(blueprint.name || 'Новый агент'));
        setRecentPostCreateHandoff(handoff);
        if (handoff?.workspace_mode === 'connections') {
          if (handoff.next_binding_key) {
            setSelectedConnectionBindingKey(handoff.next_binding_key);
          }
        } else if (handoff?.workspace_mode === 'run') {
          setSelectedConnectionBindingKey('');
        }
        setWorkspaceMode('overview');
      }
      setAgentPrompt('');
      setBuilderSourceName('');
      setBuilderSourceText('');
      setBuilderFileSource(null);
      setBuilderExecutionModeConfirmed(false);
      setCloneFromBlueprintId('');
      setCreateWizardOpen(false);
      setCreateWizardStep(0);
    } catch (requestError) {
      console.error(requestError);
      setError(getRequestErrorMessage(requestError, 'Не удалось собрать черновик агента.'));
    } finally {
      setActionLoading(false);
    }
  };

  useEffect(() => {
    if (!runAnimation || runAnimation.status !== 'running') {
      return;
    }
    const timer = window.setInterval(() => {
      setRunAnimation((current) => {
        if (!current || current.status !== 'running') {
          return current;
        }
        const total = Math.max(current.steps.length, 1);
        const completed = Math.max(0, current.serverCompletedSteps || 0);
        const cap = current.queueState === 'queued'
          ? 12
          : Math.min(92, Math.round(((completed + 0.85) / total) * 92));
        const progress = Math.min(cap, current.progress + 3);
        return { ...current, progress, stepIndex: Math.min(total - 1, current.serverCurrentStepIndex ?? completed) };
      });
    }, 500);
    return () => window.clearInterval(timer);
  }, [runAnimation?.blueprintId, runAnimation?.startedAt, runAnimation?.status]);

  const beginRunAnimation = (blueprintId: string, kind: AgentRunAnimation['kind']) => {
    const animation: AgentRunAnimation = {
      kind,
      blueprintId,
      startedAt: Date.now(),
      progress: 8,
      stepIndex: 0,
      steps: workflowStepsForAnimation(blueprintDetails, kind),
      status: 'running',
      serverCompletedSteps: 0,
      serverCurrentStepIndex: 0,
      queueState: 'queued',
    };
    setRunAnimation(animation);
    return animation.startedAt;
  };

  const finishRunAnimation = async (startedAt: number) => {
    const waitMs = Math.max(0, 6500 - (Date.now() - startedAt));
    if (waitMs > 0) {
      await new Promise<void>((resolve) => window.setTimeout(resolve, waitMs));
    }
    setRunAnimation((current) => current ? {
      ...current,
      progress: 100,
      stepIndex: Math.max(0, current.steps.length - 1),
      status: 'finishing',
    } : current);
    await new Promise<void>((resolve) => window.setTimeout(resolve, 360));
  };

  const failRunAnimation = (message: string) => {
    setRunAnimation((current) => current ? { ...current, status: 'error', error: message } : current);
  };

  const syncRunAnimation = (run: AgentRun | null) => {
    if (!run) return;
    setRunAnimation((current) => {
      if (!current || current.blueprintId !== run.blueprint_id) return current;
      const total = Math.max(current.steps.length, Number(run.progress?.total_steps || 0), 1);
      const completed = Math.min(total, Math.max(0, Number(run.progress?.completed_steps || 0)));
      const currentIndex = Math.min(total - 1, Math.max(0, Number(run.progress?.current_step_index ?? completed)));
      const floor = Math.min(92, Math.round((completed / total) * 92));
      return {
        ...current,
        runId: run.id,
        queueState: String(run.progress?.state || run.status || 'queued'),
        serverCompletedSteps: completed,
        serverCurrentStepIndex: currentIndex,
        stepIndex: currentIndex,
        progress: Math.max(current.progress, floor),
      };
    });
  };

  const validatedRunParameters = (preview: boolean, parameterOverrides?: Record<string, unknown>) => {
    const schema = preview
      ? blueprintDetails?.candidate_run_input_schema || blueprintDetails?.run_input_schema
      : blueprintDetails?.active_run_input_schema || blueprintDetails?.candidate_run_input_schema || blueprintDetails?.run_input_schema;
    const parameters = parameterOverrides || runParameters;
    const errors = validateRunParameters(schema, parameters);
    setRunParameterErrors(errors);
    if (Object.keys(errors).length > 0) {
      setWorkspaceMode('overview');
      setError('Заполните параметры задачи перед запуском.');
      return null;
    }
    return parameters;
  };

  const waitForAgentRun = async (runId: string) => {
    for (let attempt = 0; attempt < 600; attempt += 1) {
      const response = await api.get(`/agent-runs/${runId}`);
      const run = response.data?.run && typeof response.data.run === 'object' ? response.data.run : null;
      if (run) {
        setActiveRun(run);
        syncRunAnimation(run);
        if (['completed', 'waiting_approval', 'failed', 'rejected', 'superseded'].includes(String(run.status || ''))) {
          return run;
        }
      }
      await new Promise<void>((resolve) => window.setTimeout(resolve, 1000));
    }
    throw new Error('Агент продолжает работу дольше ожидаемого. Результат появится в истории после завершения.');
  };

  useEffect(() => {
    if (!runAnimation?.recoveredFromReload || !runAnimation.runId) return;
    let cancelled = false;
    const runId = runAnimation.runId;
    const startedAt = runAnimation.startedAt;
    void waitForAgentRun(runId).then(async (run) => {
      if (cancelled) return;
      if (run?.status === 'failed') {
        failRunAnimation(run.error_text || 'Агент не смог завершить задачу.');
        return;
      }
      await finishRunAnimation(startedAt);
      if (cancelled) return;
      setRunAnimation(null);
      setWorkspaceMode('results');
      if (selectedBlueprint?.id) await loadBlueprintDetails(selectedBlueprint.id);
    }).catch((requestError) => {
      if (!cancelled) failRunAnimation(getRequestErrorMessage(requestError, 'Не удалось продолжить отслеживание задачи.'));
    });
    return () => { cancelled = true; };
  }, [runAnimation?.recoveredFromReload, runAnimation?.runId]);

  const startRun = async (
    blueprintToRun?: AgentBlueprint | null,
    blueprintVersionId = '',
    parameterOverrides?: Record<string, unknown>,
  ) => {
    const targetBlueprint = blueprintToRun || selectedBlueprint;
    if (!targetBlueprint) {
      return;
    }
    const parameters = validatedRunParameters(true, parameterOverrides);
    if (!parameters) {
      return;
    }
    setActionLoading(true);
    setError(null);
    setDecisionNotice(null);
    const animationStartedAt = beginRunAnimation(targetBlueprint.id, 'test');
    try {
      const selectedVersionId = blueprintVersionId || getPreviewVersionId(targetBlueprint, blueprintDetails);
      const runInput = {
        schema: 'localos_agent_preview_input_v1',
        preview_mode: true,
        source: 'agent_preview',
        dashboard_source: runSource.trim() || 'dashboard',
        city: runCity.trim(),
        category: runCategory.trim(),
        goal: targetBlueprint.description || targetBlueprint.latest_goal || '',
        intent: 'agent_preview',
        business_id: currentBusinessId,
        blueprint_id: targetBlueprint.id,
        blueprint_version_id: selectedVersionId,
        external_side_effects_allowed: false,
        approval_required_for_external_actions: true,
        limit: Number(runLimit) > 0 ? Math.min(Number(runLimit), 100) : 30,
        ...parameters,
      };
      const preflightResponse = await api.post(`/agent-blueprints/${targetBlueprint.id}/preflight`, {
        blueprint_version_id: selectedVersionId || undefined,
        input: runInput,
      });
      const preflight = normalizeAgentIntegrationPreflight(preflightResponse.data?.preflight);
      if (preflightResponse.data?.can_start === false || preflight?.ready === false) {
        const connectionPlan = normalizeConnectionPlan(preflightResponse.data?.connection_plan);
        if (connectionPlan) {
          setAgentConnectionPlan(connectionPlan);
        }
        const nextBindingKey = String(preflightResponse.data?.next_binding_key || '');
        if (nextBindingKey) {
          setSelectedConnectionBindingKey(nextBindingKey);
        }
        setWorkspaceMode('overview');
        const message = formatPreflightBlock(preflight) || 'Перед запуском нужно подключить источники агента.';
        setError(message);
        failRunAnimation(message);
        await loadBlueprintDetails(targetBlueprint.id);
        return;
      }
      const response = await api.post(`/agent-blueprints/${targetBlueprint.id}/runs`, {
        idempotency_key: window.crypto.randomUUID(),
        blueprint_version_id: selectedVersionId || undefined,
        input: runInput,
      });
      let nextRun = response.data?.run || null;
      setActiveRun(nextRun);
      syncRunAnimation(nextRun);
      if (nextRun?.id && ['queued', 'running', 'retry_wait'].includes(String(nextRun.status || ''))) {
        nextRun = await waitForAgentRun(nextRun.id);
      }
      if (nextRun?.status === 'failed') {
        throw new Error(nextRun.error_text || 'Агент не смог завершить тест.');
      }
      await finishRunAnimation(animationStartedAt);
      setRunAnimation(null);
      setWorkspaceMode('results');
      setDecisionNotice(nextRun?.id ? 'Тест запущен заново. Ниже показан свежий результат проверки.' : 'Тест запущен заново.');
      await loadBlueprintDetails(targetBlueprint.id);
      await loadBlueprintReview(targetBlueprint.id);
    } catch (requestError) {
      console.error(requestError);
      const message = getRequestErrorMessage(requestError, 'Не удалось запустить агента.');
      setError(message);
      failRunAnimation(message);
    } finally {
      setActionLoading(false);
    }
  };

  const executeRun = async (
    blueprintToRun?: AgentBlueprint | null,
    blueprintVersionId = '',
    parameterOverrides?: Record<string, unknown>,
  ) => {
    const targetBlueprint = blueprintToRun || selectedBlueprint;
    if (!targetBlueprint) {
      return;
    }
    const parameters = validatedRunParameters(false, parameterOverrides);
    if (!parameters) {
      return;
    }
    setActionLoading(true);
    setError(null);
    setDecisionNotice(null);
    const animationStartedAt = beginRunAnimation(targetBlueprint.id, 'work');
    try {
      const selectedVersionId = blueprintVersionId || blueprintDetails?.active_version_id || blueprintDetails?.candidate_version_id || '';
      const response = await api.post(`/agent-blueprints/${targetBlueprint.id}/runs`, {
        idempotency_key: window.crypto.randomUUID(),
        blueprint_version_id: selectedVersionId || undefined,
        input: {
          preview_mode: false,
          source: 'dashboard_work_run',
          dashboard_source: 'dashboard',
          business_id: currentBusinessId,
          external_side_effects_allowed: false,
          approval_required_for_external_actions: true,
          limit: Number(runLimit) > 0 ? Math.min(Number(runLimit), 100) : 30,
          ...parameters,
        },
      });
      let nextRun = response.data?.run || null;
      setActiveRun(nextRun);
      syncRunAnimation(nextRun);
      if (nextRun?.id && ['queued', 'running', 'retry_wait'].includes(String(nextRun.status || ''))) {
        nextRun = await waitForAgentRun(nextRun.id);
      }
      if (nextRun?.status === 'failed') {
        throw new Error(nextRun.error_text || 'Агент не смог завершить задачу.');
      }
      await finishRunAnimation(animationStartedAt);
      setRunAnimation(null);
      setWorkspaceMode('results');
      setDecisionNotice(nextRun?.id ? 'Работа выполнена. Ниже показан свежий сохранённый результат.' : 'Работа запущена.');
      await loadBlueprintDetails(targetBlueprint.id);
      await loadBlueprintReview(targetBlueprint.id);
    } catch (requestError) {
      console.error(requestError);
      const message = getRequestErrorMessage(requestError, 'Не удалось выполнить задачу агента.');
      setError(message);
      failRunAnimation(message);
    } finally {
      setActionLoading(false);
    }
  };

  const saveSchedule = async () => {
    if (!selectedBlueprint) {
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      await api.post(`/agent-blueprints/${selectedBlueprint.id}/schedule`, {
        time: scheduleTime,
        timezone: scheduleTimezone,
      });
      setDecisionNotice('Расписание сохранено. Теперь включите агента.');
      await loadBlueprints();
      await loadBlueprintDetails(selectedBlueprint.id);
    } catch (requestError) {
      console.error(requestError);
      setError(getRequestErrorMessage(requestError, 'Не удалось сохранить расписание.'));
    } finally {
      setActionLoading(false);
    }
  };

  const saveExecutionMode = async () => {
    if (!selectedBlueprint) {
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      await api.post(`/agent-blueprints/${selectedBlueprint.id}/execution-mode`, {
        execution_mode: selectedExecutionMode,
        time: selectedExecutionMode === 'scheduled' ? scheduleTime : undefined,
        timezone: selectedExecutionMode === 'scheduled' ? scheduleTimezone : undefined,
      });
      setDecisionNotice(selectedExecutionMode === 'scheduled'
        ? 'Тип запуска и расписание сохранены. После успешного теста агента можно включить.'
        : 'Тип запуска сохранён. Теперь можно проверить агента.');
      await loadBlueprints();
      await loadBlueprintDetails(selectedBlueprint.id);
      setWorkspaceMode('overview');
    } catch (requestError) {
      console.error(requestError);
      setError(getRequestErrorMessage(requestError, 'Не удалось сохранить тип запуска.'));
    } finally {
      setActionLoading(false);
    }
  };

  const rebuildScenarioAndRun = async () => {
    if (!selectedBlueprint) {
      return;
    }
    setActionLoading(true);
    setError(null);
    setDecisionNotice(null);
    try {
      const description = selectedBlueprint.description || selectedBlueprint.latest_goal || selectedBlueprint.name || '';
      const response = await api.post(`/agent-blueprints/${selectedBlueprint.id}/versions`, {
        rebuild_from_description: true,
        description,
        category: selectedBlueprint.category || 'custom',
        reason: 'Rebuilt from dashboard because the previous scenario had no source read step.',
      });
      const versionId = response.data?.version?.id || response.data?.candidate_version?.id || '';
      await loadBlueprintDetails(selectedBlueprint.id);
      setDecisionNotice('Сценарий пересобран. Запускаю тест по новой версии.');
      await startRun(selectedBlueprint, versionId);
    } catch (requestError) {
      console.error(requestError);
      setError(getRequestErrorMessage(requestError, 'Не удалось пересобрать сценарий агента.'));
      setActionLoading(false);
    }
  };

  const rebuildScenario = async () => {
    if (!selectedBlueprint) {
      return;
    }
    setActionLoading(true);
    setError(null);
    setDecisionNotice(null);
    try {
      await api.post(`/agent-blueprints/${selectedBlueprint.id}/versions`, {
        rebuild_from_description: true,
        description: selectedBlueprint.description || selectedBlueprint.latest_goal || selectedBlueprint.name || '',
        category: selectedBlueprint.category || 'custom',
        reason: 'Updated from the saved agent goal in the scenario tab.',
      });
      await loadBlueprintDetails(selectedBlueprint.id);
      await loadBlueprintReview(selectedBlueprint.id);
      setDecisionNotice('Сценарий обновлён по цели. Проверьте шаги и запустите тест на примере.');
      setWorkspaceMode('scenario');
    } catch (requestError) {
      console.error(requestError);
      setError(getRequestErrorMessage(requestError, 'Не удалось обновить сценарий агента.'));
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
        reason: action === 'rollback' ? 'Откат из карточки агента' : 'Активировано из карточки агента',
      });
      if (feedbackVersionNotice?.version_id === versionId) {
        setFeedbackVersionNotice({
          ...feedbackVersionNotice,
          activation_state: action === 'rollback' ? 'rolled_back' : 'active',
          next_run_note: action === 'rollback'
            ? 'Активная версия возвращена к выбранной версии. История feedback сохранена.'
            : 'Candidate-версия активирована. Следующие запуски будут использовать её.',
        });
      }
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

  const deleteAgent = async (blueprint: AgentBlueprint | null, reasonCode = 'no_longer_needed') => {
    if (!blueprint) {
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      await api.delete(`/agent-blueprints/${blueprint.id}`, {
        body: { reason_code: reasonCode },
      });
      const remaining = blueprints.filter((item) => item.id !== blueprint.id);
      setSelectedBlueprintId(remaining[0]?.id || null);
      setBlueprintDetails(null);
      setActiveRun(null);
      setWorkspaceMode('overview');
      setDeleteCandidate(null);
      await loadBlueprints();
    } catch (requestError) {
      console.error(requestError);
      setError(getRequestErrorMessage(requestError, 'Не удалось архивировать агента.'));
    } finally {
      setActionLoading(false);
    }
  };

  const requestDeleteAgent = (blueprint: AgentBlueprint | null) => {
    if (!blueprint) {
      return;
    }
    setDeleteCandidate(blueprint);
  };

  const deleteSelectedAgent = async () => {
    requestDeleteAgent(selectedBlueprint);
  };

  const decideApproval = async (decision: 'approve' | 'reject') => {
    const approval = selectedActionablePendingApproval;
    const runId = approval?.run_id || activeRun?.id || selectedBlueprint?.last_run_id || '';
    if (!approval || !runId) {
      setError('Не удалось найти запуск для этого решения. Обновите страницу и попробуйте снова.');
      return;
    }
    if (isBusinessBlockerApproval(approval)) {
      setError('Это не готовый результат, а причина остановки. Исправьте следующий шаг и запустите тест ещё раз.');
      setWorkspaceMode('results');
      return;
    }
    setActionLoading(true);
    setError(null);
    setDecisionNotice(null);
    try {
      const response = await api.post(`/agent-runs/${runId}/approvals/${approval.id}/${decision}`, {
        reason: decision === 'approve' ? 'Approved from dashboard' : 'Rejected from dashboard',
      });
      const updatedRun = response.data?.run || null;
      if (updatedRun) {
        setActiveRun(updatedRun);
      } else {
        await loadRun(runId);
      }
      if (selectedBlueprint?.id) {
        await loadBlueprintDetails(selectedBlueprint.id);
        await loadBlueprintReview(selectedBlueprint.id);
      }
      await loadBlueprints();
      setDecisionNotice(decision === 'approve' ? 'Решение принято. Агент продолжил работу.' : 'Результат отклонён. Агент остановлен для правки.');
      setWorkspaceMode('results');
    } catch (requestError) {
      console.error(requestError);
      setError(getRequestErrorMessage(requestError, 'Не удалось применить решение.'));
    } finally {
      setActionLoading(false);
    }
  };

  const applyFinanceRequests = async (runId: string) => {
    setActionLoading(true);
    setError(null);
    try {
      const response = await api.post(`/agent-runs/${runId}/finance-requests/apply`, {
        reason: 'Applied from agent run dashboard',
      });
      setActiveRun(response.data?.run || null);
      if (selectedBlueprint?.id) {
        await loadBlueprintDetails(selectedBlueprint.id);
        await loadBlueprintReview(selectedBlueprint.id);
      }
    } catch (requestError) {
      console.error(requestError);
      setError(getRequestErrorMessage(requestError, 'Не удалось применить операции в финансы.'));
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

  const saveSheetIntegration = async () => {
    if (!selectedBlueprint || !sheetSpreadsheetId.trim()) {
      return;
    }
    const selectedBinding = agentBindingStatus.find((item) => item.key === selectedConnectionBindingKey && item.provider === 'google_sheets');
    const existing = [...agentIntegrations, ...availableAgentIntegrations].find((item) => item.provider === 'google_sheets');
    const needsRead = agentBindingStatus.some((item) => item.provider === 'google_sheets' && item.capability === 'google_sheets.read_rows');
    const needsAppend = agentBindingStatus.some((item) => item.provider === 'google_sheets' && item.capability === 'sheets.append_row_request');
    const selectedCapability = selectedBinding?.capability || '';
    const operation = selectedCapability === 'google_sheets.read_rows'
      ? 'read_rows'
      : selectedCapability === 'sheets.append_row_request'
        ? 'append_row'
        : needsRead && needsAppend ? 'read_write' : needsRead ? 'read_rows' : 'append_row';
    setActionLoading(true);
    setError(null);
    try {
      const response = await api.post(`/agent-blueprints/${selectedBlueprint.id}/integrations`, {
        integration_id: existing?.id,
        binding_key: selectedBinding?.key || '',
        provider: 'google_sheets',
        status: 'active',
        display_name: 'Google Sheets',
        auth_ref: sheetAuthRef.trim(),
        config: {
          spreadsheet_id: normalizeSpreadsheetInput(sheetSpreadsheetId),
          sheet_name: sheetName.trim() || 'Sheet1',
          operation,
        },
        limits: {
          daily_append_cap: Number(sheetDailyCap) > 0 ? Number(sheetDailyCap) : 50,
          frequency_cap_minutes: 0,
        },
      });
      await loadAgentIntegrations(selectedBlueprint.id);
      await loadBlueprintDetails(selectedBlueprint.id);
      const handoff = normalizePostCreateHandoff(response.data?.post_connect_handoff);
      applyPostConnectHandoff(handoff);
      if (handoff?.status === 'ready_for_preview') {
        setDecisionNotice('Таблица сохранена. Теперь запустите безопасный тест.');
      } else if (handoff?.status === 'needs_connections') {
        const nextTitle = handoff.next_binding?.title || connectorLabel(handoff.next_binding?.provider);
        setDecisionNotice(`Таблица сохранена. Остался следующий доступ: ${nextTitle}.`);
      } else {
        setDecisionNotice('Таблица сохранена.');
      }
    } catch (requestError) {
      console.error(requestError);
      setError(getRequestErrorMessage(requestError, 'Не удалось подключить Google Sheets.'));
    } finally {
      setActionLoading(false);
    }
  };

  const saveBrowserUseIntegration = async () => {
    if (!selectedBlueprint || !browserTargetUrls.trim()) {
      return;
    }
    const selectedBinding = agentBindingStatus.find((item) => item.key === selectedConnectionBindingKey && item.provider === 'browser_use');
    const existing = [...agentIntegrations, ...availableAgentIntegrations].find((item) => item.provider === 'browser_use');
    setActionLoading(true);
    setError(null);
    try {
      const response = await api.post(`/agent-blueprints/${selectedBlueprint.id}/integrations`, {
        integration_id: existing?.id,
        binding_key: selectedBinding?.key || '',
        provider: 'browser_use',
        status: 'active',
        display_name: 'Browser use',
        config: {
          target_urls: browserTargetUrls,
        },
        limits: {
          daily_page_check_cap: Number(browserDailyCap) > 0 ? Number(browserDailyCap) : 50,
          frequency_cap_minutes: 60,
        },
      });
      await loadAgentIntegrations(selectedBlueprint.id);
      await loadBlueprintDetails(selectedBlueprint.id);
      applyPostConnectHandoff(response.data?.post_connect_handoff);
    } catch (requestError) {
      console.error(requestError);
      setError(getRequestErrorMessage(requestError, 'Не удалось подключить Browser use.'));
    } finally {
      setActionLoading(false);
    }
  };

  const saveTelegramIntegration = async () => {
    if (!selectedBlueprint) {
      return;
    }
    const selectedBinding = agentBindingStatus.find((item) => item.key === selectedConnectionBindingKey && item.provider === 'telegram');
    const existing = [...agentIntegrations, ...availableAgentIntegrations].find((item) => item.provider === 'telegram');
    setActionLoading(true);
    setError(null);
    try {
      const response = await api.post(`/agent-blueprints/${selectedBlueprint.id}/integrations`, {
        integration_id: existing?.id,
        binding_key: selectedBinding?.key || '',
        provider: 'telegram',
        status: 'active',
        display_name: 'Telegram',
        config: {
          bot_mode: telegramBotMode,
        },
        limits: {
          daily_message_cap: Number(telegramDailyCap) > 0 ? Number(telegramDailyCap) : 50,
          frequency_cap_minutes: 30,
        },
      });
      await loadAgentIntegrations(selectedBlueprint.id);
      await loadBlueprintDetails(selectedBlueprint.id);
      applyPostConnectHandoff(response.data?.post_connect_handoff);
    } catch (requestError) {
      console.error(requestError);
      setError(getRequestErrorMessage(requestError, 'Не удалось подключить Telegram.'));
    } finally {
      setActionLoading(false);
    }
  };

  const saveWhatsappIntegration = async () => {
    if (!selectedBlueprint) {
      return;
    }
    const selectedBinding = agentBindingStatus.find((item) => item.key === selectedConnectionBindingKey && item.provider === 'whatsapp');
    const existing = [...agentIntegrations, ...availableAgentIntegrations].find((item) => item.provider === 'whatsapp');
    setActionLoading(true);
    setError(null);
    try {
      const response = await api.post(`/agent-blueprints/${selectedBlueprint.id}/integrations`, {
        integration_id: existing?.id,
        binding_key: selectedBinding?.key || '',
        provider: 'whatsapp',
        status: 'active',
        display_name: 'WhatsApp',
        config: {
          channel_mode: whatsappChannelMode,
        },
        limits: {
          daily_message_cap: Number(whatsappDailyCap) > 0 ? Number(whatsappDailyCap) : 50,
          frequency_cap_minutes: 30,
        },
      });
      await loadAgentIntegrations(selectedBlueprint.id);
      await loadBlueprintDetails(selectedBlueprint.id);
      applyPostConnectHandoff(response.data?.post_connect_handoff);
    } catch (requestError) {
      console.error(requestError);
      setError(getRequestErrorMessage(requestError, 'Не удалось подключить WhatsApp.'));
    } finally {
      setActionLoading(false);
    }
  };

  const saveMatonIntegration = async () => {
    if (!selectedBlueprint) {
      return;
    }
    const selectedBinding = agentBindingStatus.find((item) => item.key === selectedConnectionBindingKey && item.provider === 'maton');
    const existing = [...agentIntegrations, ...availableAgentIntegrations].find((item) => item.provider === 'maton');
    setActionLoading(true);
    setError(null);
    try {
      const response = await api.post(`/agent-blueprints/${selectedBlueprint.id}/integrations`, {
        integration_id: existing?.id,
        binding_key: selectedBinding?.key || '',
        provider: 'maton',
        status: 'active',
        display_name: 'Maton.ai',
        auth_ref: matonAuthRef.trim(),
        config: {
          channel: matonChannel.trim() || 'maton_bridge',
        },
        limits: {
          daily_message_cap: Number(matonDailyCap) > 0 ? Number(matonDailyCap) : 50,
          frequency_cap_minutes: 30,
        },
      });
      await loadAgentIntegrations(selectedBlueprint.id);
      await loadBlueprintDetails(selectedBlueprint.id);
      applyPostConnectHandoff(response.data?.post_connect_handoff);
    } catch (requestError) {
      console.error(requestError);
      setError(getRequestErrorMessage(requestError, 'Не удалось подключить Maton.ai.'));
    } finally {
      setActionLoading(false);
    }
  };

  const chooseProviderRoute = async (bindingKey: string, route: AgentProviderRoute) => {
    if (!selectedBlueprint || !bindingKey || !route.provider) {
      return;
    }
    if (route.provider === 'maton' && !matonAuthRef.trim()) {
      setSelectedConnectionBindingKey(bindingKey);
      setWorkspaceMode('connections');
      setError('Выберите сохранённый Maton.ai key для этого шага.');
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      const response = await api.post(`/agent-blueprints/${selectedBlueprint.id}/provider-routes`, {
        binding_key: bindingKey,
        route_provider: route.provider,
        external_account_id: route.provider === 'maton' ? matonAuthRef.trim() : '',
      });
      await loadAgentIntegrations(selectedBlueprint.id);
      await loadBlueprintDetails(selectedBlueprint.id);
      await loadBlueprintReview(selectedBlueprint.id);
      applyPostConnectHandoff(response.data?.post_connect_handoff);
    } catch (requestError) {
      console.error(requestError);
      setError(getRequestErrorMessage(requestError, 'Не удалось выбрать способ подключения для агента.'));
    } finally {
      setActionLoading(false);
    }
  };

  const attachExistingAgentIntegration = async (integration: AgentIntegration, bindingKey = '') => {
    if (!selectedBlueprint || !integration?.id || !integration.provider) {
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      const response = await api.post(`/agent-blueprints/${selectedBlueprint.id}/integrations`, {
        integration_id: integration.id,
        binding_key: bindingKey,
        provider: integration.provider,
        status: 'active',
        display_name: integration.display_name || integration.provider_label || humanizeMeta(integration.provider),
        auth_ref: integration.auth_ref || '',
        config: integration.config || {},
        limits: integration.limits || {},
      });
      await loadAgentIntegrations(selectedBlueprint.id);
      await loadBlueprintDetails(selectedBlueprint.id);
      applyPostConnectHandoff(response.data?.post_connect_handoff);
    } catch (requestError) {
      console.error(requestError);
      setError(getRequestErrorMessage(requestError, 'Не удалось подключить существующий доступ к агенту.'));
    } finally {
      setActionLoading(false);
    }
  };

  const saveCustomProcess = async () => {
    if (!selectedBlueprint) {
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      await api.post(`/agent-blueprints/${selectedBlueprint.id}/custom-process`, {
        trigger: 'telegram.message.received',
        target: 'google_sheets.append_row',
        row_values: processRowValues,
        integration_id: agentIntegrations.find((item) => item.provider === 'google_sheets')?.id || '',
        spreadsheet_id: normalizeSpreadsheetInput(sheetSpreadsheetId),
        sheet_name: sheetName.trim() || 'Leads',
        daily_append_cap: Number(sheetDailyCap) > 0 ? Number(sheetDailyCap) : 50,
      });
      await loadAgentIntegrations(selectedBlueprint.id);
      await loadBlueprintDetails(selectedBlueprint.id);
      await loadBlueprintReview(selectedBlueprint.id);
    } catch (requestError) {
      console.error(requestError);
      setError(getRequestErrorMessage(requestError, 'Не удалось сохранить процесс агента.'));
    } finally {
      setActionLoading(false);
    }
  };

  const runCustomProcessPreview = async () => {
    if (!selectedBlueprint) {
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      const response = await api.post(`/agent-blueprints/${selectedBlueprint.id}/custom-process/preview`, {
        message_text: processPreviewMessage.trim() || 'Новая заявка для проверки',
        telegram_username: 'preview_user',
      });
      setActiveRun(response.data?.run || null);
      setWorkspaceMode('results');
      await loadBlueprintDetails(selectedBlueprint.id);
      await loadBlueprintReview(selectedBlueprint.id);
    } catch (requestError) {
      console.error(requestError);
      setError(getRequestErrorMessage(requestError, 'Не удалось проверить процесс на примере.'));
    } finally {
      setActionLoading(false);
    }
  };

  const applyLegacyMigration = async () => {
    if (!currentBusinessId) {
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      const response = await api.post('/agent-blueprints/legacy-migration/apply', {
        business_id: currentBusinessId,
      });
      const migration = response.data?.migration || {};
      const appliedCount = typeof migration.applied_count === 'number' ? migration.applied_count : 0;
      const skippedCount = typeof migration.skipped_count === 'number' ? migration.skipped_count : 0;
      setLegacyMigrationNotice(`Миграция выполнена: создано ${appliedCount}, пропущено ${skippedCount}. Legacy поля не удалялись.`);
      await loadBlueprints();
      await loadLegacyMigrationPlan();
      if (selectedBlueprint?.id) {
        await loadBlueprintDetails(selectedBlueprint.id);
      }
    } catch (requestError) {
      console.error(requestError);
      setError(getRequestErrorMessage(requestError, 'Не удалось применить legacy migration.'));
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
      const response = await api.post(`/agent-runs/${activeRun.id}/feedback`, {
        feedback: feedbackText,
        trigger_type: feedbackTrigger,
        auto_activate: false,
      });
      const version = response.data?.version || {};
      const learning: AgentLearningLoop = response.data?.learning || {};
      setFeedbackVersionNotice({
        version_id: typeof version.id === 'string' ? version.id : learning.candidate_version_id,
        previous_version_id: learning.previous_version_id,
        version_number: typeof version.version_number === 'number' ? version.version_number : undefined,
        feedback: feedbackText,
        activation_state: learning.activation_state || 'candidate',
        trigger_label: learning.trigger_label || learningTriggerOptions.find((item) => item.value === feedbackTrigger)?.label || 'Обратная связь',
        diff: learning.diff || response.data?.diff || undefined,
        next_run_note: 'Это кандидатная версия. Она сохранена с diff, но не станет активной, пока человек не активирует её.',
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

  const postCreateReadyForRun = recentPostCreateHandoff?.workspace_mode === 'run'
    || recentPostCreateHandoff?.status === 'ready_for_preview';
  const showPostCreateConnectionDetails = Boolean(recentPostCreateHandoff)
    && !postCreateReadyForRun
    && (recentPostCreateHandoff?.workspace_mode === 'connections' || recentPostCreateHandoff?.status === 'needs_connections');
  const todaySummary = useMemo(
    () => {
      if (!serverTodaySummary) {
        return buildTodaySummary(blueprints, agentDetailsById);
      }
      const completedRuns = Number(serverTodaySummary.completed_runs || 0);
      const preparedArtifacts = Number(serverTodaySummary.prepared_results || 0);
      const pendingApprovals = Number(serverTodaySummary.pending_approvals || 0);
      const failedRuns = Number(serverTodaySummary.failed_runs || 0);
      return {
        completedRuns,
        preparedArtifacts,
        pendingApprovals,
        failedRuns,
        latestEvent: '',
        empty: completedRuns + preparedArtifacts + pendingApprovals + failedRuns === 0,
      };
    },
    [agentDetailsById, blueprints, serverTodaySummary],
  );
  const employeeListDetailsById = useMemo(() => {
    if (!selectedBlueprint?.id || !blueprintDetails) {
      return agentDetailsById;
    }
    const selectedDetails = (() => {
      if (!activeRun?.id) {
        return blueprintDetails;
      }
      const runs = blueprintDetails.runs || [];
      const runBelongsToSelectedBlueprint = activeRun.blueprint_id === selectedBlueprint.id
        || activeRun.id === runs[0]?.id
        || activeRun.id === selectedBlueprint.last_run_id;
      if (!runBelongsToSelectedBlueprint) {
        return blueprintDetails;
      }
      return {
        ...blueprintDetails,
        runs: [activeRun, ...runs.filter((run) => run.id !== activeRun.id)],
      };
    })();
    return {
      ...agentDetailsById,
      [selectedBlueprint.id]: selectedDetails,
    };
  }, [activeRun, agentDetailsById, blueprintDetails, selectedBlueprint?.id, selectedBlueprint?.last_run_id]);
  const filteredBlueprints = useMemo(() => {
    const query = agentSearch.trim().toLowerCase();
    return blueprints.filter((blueprint) => {
      const details = employeeListDetailsById[blueprint.id];
      const state = buildEmployeeWorkspaceState(blueprint, details);
      const matchesSearch = !query || [blueprint.name, buildEmployeeDescription(blueprint, details)]
        .some((value) => String(value || '').toLowerCase().includes(query));
      if (!matchesSearch) {
        return false;
      }
      if (agentRegistryFilter === 'working') {
        return state === 'working';
      }
      if (agentRegistryFilter === 'completed') {
        return state === 'completed';
      }
      if (agentRegistryFilter === 'attention') {
        return ['needs_mode', 'needs_connection', 'ready_for_test', 'waiting_for_review', 'blocked_result', 'needs_attention', 'error'].includes(state);
      }
      return true;
    });
  }, [agentRegistryFilter, agentSearch, blueprints, employeeListDetailsById]);
  const selectedEmployeeAction = useMemo(
    () => selectedBlueprint
      ? buildEmployeeNextAction({
        blueprint: selectedBlueprint,
        details: blueprintDetails,
        pendingApproval: selectedPendingApproval,
        googleAccessFreshAfterResult: hasFreshGoogleSheetsAccessAfterResult(
          agentExternalAuthOptions,
          activeRun || blueprintDetails?.runs?.[0] || null,
          selectedPendingApproval,
        ),
      })
      : null,
    [activeRun, agentExternalAuthOptions, blueprintDetails, selectedBlueprint, selectedPendingApproval],
  );
  const selectedResultRun = activeRun || blueprintDetails?.runs?.[0] || null;
  const resultNeedsScenarioRebuild = needsScenarioRebuildForSourceResult(selectedResultRun, selectedPendingApproval, blueprintDetails);
  const resultNeedsGoogleSheetsSetup = needsGoogleSheetsSourceSetup(selectedResultRun, selectedPendingApproval);
  const resultNeedsGoogleAccessReconnect = needsGoogleAccessReconnect(selectedResultRun, selectedPendingApproval);
  const resultGoogleAccessReconnected = resultNeedsGoogleAccessReconnect && (
    googleAccessJustConnected
    || hasFreshGoogleSheetsAccessAfterResult(agentExternalAuthOptions, selectedResultRun, selectedPendingApproval)
  );
  const openGoogleSheetsSourceSetup = () => {
    const sheetBinding = agentBindingStatus.find((binding) => binding.provider === 'google_sheets' && binding.capability === 'google_sheets.read_rows')
      || agentBindingStatus.find((binding) => binding.provider === 'google_sheets')
      || null;
    if (sheetBinding?.key) {
      setSelectedConnectionBindingKey(sheetBinding.key);
    }
    setDecisionNotice('Укажите Google-таблицу и лист со списком поездок, затем сохраните источник и запустите тест ещё раз.');
    setWorkspaceMode('connections');
  };
  const openGoogleAccessReconnect = () => {
    const params = new URLSearchParams({
      focus: 'google_sheets',
      return_to: '/dashboard/agents',
    });
    window.location.href = `/dashboard/settings/integrations?${params.toString()}`;
  };
  const openSelectedAgentClone = () => {
    if (!selectedBlueprint) {
      return;
    }
    setCloneFromBlueprintId(selectedBlueprint.id);
    setDialogBuilderInput(selectedBlueprint.description || selectedBlueprint.latest_goal || selectedBlueprint.name);
    setAgentPrompt(selectedBlueprint.description || selectedBlueprint.latest_goal || selectedBlueprint.name);
    setBuilderExecutionMode(agentExecutionMode(selectedBlueprint, blueprintDetails));
    setBuilderExecutionModeConfirmed(false);
    setCreateWizardOpen(true);
  };
  const runEmployeePrimaryAction = () => {
    if (!selectedBlueprint || !selectedEmployeeAction) {
      return;
    }
    if (selectedEmployeeAction.kind === 'run_test') {
      void startRun(selectedBlueprint);
      return;
    }
    if (selectedEmployeeAction.kind === 'run_work') {
      void executeRun(selectedBlueprint, selectedEmployeeAction.versionId || '');
      return;
    }
    if (selectedEmployeeAction.kind === 'run_similar') {
      openSelectedAgentClone();
      return;
    }
    if (selectedEmployeeAction.kind === 'confirm_mode') {
      setWorkspaceMode('settings');
      return;
    }
    if (selectedEmployeeAction.kind === 'enable' && selectedEmployeeAction.versionId) {
      void activateVersion(selectedEmployeeAction.versionId, 'activate');
      return;
    }
    if (selectedEmployeeAction.kind === 'configure_schedule') {
      setWorkspaceMode('overview');
      return;
    }
    setWorkspaceMode(selectedEmployeeAction.targetMode);
  };

  return (
    <AgentBlueprintsView
      scope={{
      location, currentBusinessId, blueprints, selectedBlueprintId, setSelectedBlueprintId, blueprintDetails, agentDetailsById, activeRun, setActiveRun, loading,
      actionLoading, error, agentSearch, setAgentSearch, agentRegistryFilter, setAgentRegistryFilter, runAnimation, runStatusFilter, setRunStatusFilter, runSource,
      setRunSource, runCity, setRunCity, runCategory, setRunCategory, runLimit, setRunLimit, runParameters, setRunParameters, runParameterErrors,
      setRunParameterErrors, createWizardOpen, setCreateWizardOpen, createWizardStep, setCreateWizardStep, workspaceMode, setWorkspaceMode, availablePersonaAgents, agentPrompt, setAgentPrompt,
      setBuilderCategory, builderDataSources, setBuilderDataSources, builderExtractionRules, setBuilderExtractionRules, builderProcessingRules, setBuilderProcessingRules, builderOutputFormat, setBuilderOutputFormat, builderManualControl,
      setBuilderManualControl, builderExecutionMode, setBuilderExecutionMode, builderExecutionModeConfirmed, setBuilderExecutionModeConfirmed, cloneFromBlueprintId, setCloneFromBlueprintId, builderSourceName, setBuilderSourceName, builderSourceText,
      setBuilderSourceText, builderFileSource, setBuilderFileSource, builderInternalSource, setBuilderInternalSource, dialogBuilderInput, setDialogBuilderInput, dialogBuilderReply, setDialogBuilderReply, dialogBuilderSession,
      setDialogBuilderSession, selectedBuilderConnectionBindings, setSelectedBuilderConnectionBindings, selectedBuilderProviderRoutes, setSelectedBuilderProviderRoutes, acceptedBuilderCompilerPlan, setAcceptedBuilderCompilerPlan, acceptedBuilderProviderRoutes, setAcceptedBuilderProviderRoutes, agentReview,
      sourceCatalog, setupDataSources, setSetupDataSources, setupExtractionRules, setSetupExtractionRules, setupProcessingRules, setSetupProcessingRules, setupOutputFormat, setSetupOutputFormat, setupManualControl,
      setSetupManualControl, sourceName, setSourceName, sourceText, setSourceText, internalSource, setInternalSource, agentIntegrations, availableAgentIntegrations, agentIntegrationCatalog,
      agentExternalAuthOptions, agentBindingStatus, agentConnectionPlan, selectedConnectionBindingKey, setSelectedConnectionBindingKey, sheetSpreadsheetId, setSheetSpreadsheetId, sheetName, setSheetName, sheetAuthRef,
      setSheetAuthRef, sheetDailyCap, setSheetDailyCap, browserTargetUrls, setBrowserTargetUrls, browserDailyCap, setBrowserDailyCap, telegramBotMode, setTelegramBotMode, telegramDailyCap,
      setTelegramDailyCap, whatsappChannelMode, setWhatsappChannelMode, whatsappDailyCap, setWhatsappDailyCap, matonAuthRef, setMatonAuthRef, matonChannel, setMatonChannel, matonDailyCap,
      setMatonDailyCap, processRowValues, setProcessRowValues, processPreviewMessage, setProcessPreviewMessage, scheduleTime, setScheduleTime, scheduleTimezone, setScheduleTimezone, selectedExecutionMode,
      setSelectedExecutionMode, feedbackText, setFeedbackText, feedbackTrigger, setFeedbackTrigger, feedbackVersionNotice, legacyMigrationPlan, legacyMigrationNotice, recentCreatedAgentName, setRecentCreatedAgentName,
      recentPostCreateHandoff, setRecentPostCreateHandoff, showAdvancedAgentTools, deleteCandidate, setDeleteCandidate, decisionNotice, setDecisionNotice, googleAccessJustConnected, selectedBlueprint, pendingApproval,
      pendingApprovals, selectedPendingApproval, queuedButNotDispatched, selectedScenario, systemAgents, migrationStats, applyBuilderScenario, loadBlueprints, loadRun, startDialogBuilderSession,
      sendDialogBuilderReply, createAgentFromDialogSession, createAgentFromPrompt, startRun, executeRun, saveSchedule, saveExecutionMode, rebuildScenarioAndRun, rebuildScenario, activateVersion, deleteAgent,
      requestDeleteAgent, deleteSelectedAgent, decideApproval, saveAgentSetup, addTextSource, addInternalSource, addInternalSourceByKey, addFileSource, saveSheetIntegration, saveBrowserUseIntegration,
      saveTelegramIntegration, saveWhatsappIntegration, saveMatonIntegration, chooseProviderRoute, attachExistingAgentIntegration, saveCustomProcess, runCustomProcessPreview, applyLegacyMigration, sendRunFeedback, postCreateReadyForRun,
      showPostCreateConnectionDetails, todaySummary, employeeListDetailsById, filteredBlueprints, selectedEmployeeAction, selectedResultRun, resultNeedsScenarioRebuild, resultNeedsGoogleSheetsSetup, resultNeedsGoogleAccessReconnect, resultGoogleAccessReconnected,
      openGoogleSheetsSourceSetup, openGoogleAccessReconnect, openSelectedAgentClone, runEmployeePrimaryAction, applyFinanceRequests
      }}
    />
  );
};
