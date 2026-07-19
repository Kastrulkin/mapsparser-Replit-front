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

import { newAuth } from '@/lib/auth_new';
import { api } from '@/services/api';

export const parseAgentConfig = (business?: DashboardContext['currentBusiness']) => {
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

export const uploadAgentSource = async (blueprintId: string, file: File, name: string) => {
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
    const code = String(data.code || data.error_code || '');
    const friendlyMessage = code === 'FILE_TOO_LARGE'
      ? 'Файл слишком большой. Загрузите файл меньшего размера или вставьте текст вручную.'
      : code === 'UNSUPPORTED_FILE_TYPE'
        ? 'Этот тип файла пока не поддерживается. Поддерживаются TXT, CSV, TSV, MD, PDF, DOCX и XLSX.'
        : code === 'EMPTY_FILE'
          ? 'Файл пустой. Добавьте файл с текстом или вставьте контекст вручную.'
          : data.error || 'Не удалось извлечь текст из файла. Попробуйте другой файл или вставьте текст вручную.';
    throw new Error(friendlyMessage);
  }
  return data;
};

export const fetchLatestAgentRunId = async (blueprintId: string, fallbackRunId = '') => {
  if (!blueprintId) {
    return fallbackRunId;
  }
  const response = await api.get(`/agent-blueprints/${blueprintId}`, {
    params: { run_status: 'all' },
  });
  const latestRun = Array.isArray(response.data?.runs) ? response.data.runs[0] : null;
  return String(latestRun?.id || fallbackRunId || '');
};
