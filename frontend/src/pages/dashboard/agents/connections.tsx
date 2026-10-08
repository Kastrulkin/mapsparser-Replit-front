import type React from 'react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useOutletContext } from 'react-router-dom';
import {
  Activity,
  AlertTriangle,
  ArrowDownUp,
  Bot,
  CheckCircle2,
  Clock3,
  Copy,
  Database,
  Download,
  FileCheck2,
  FileText,
  LifeBuoy,
  Loader2,
  Mail,
  MessageSquareText,
  Play,
  ReceiptText,
  RefreshCw,
  Search,
  Send,
  ShieldCheck,
  Sparkles,
  Star,
  Trash2,
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
  DashboardEmptyState,
  DashboardPageHeader,
  DashboardSection,
} from '@/components/dashboard/DashboardPrimitives';
import { newAuth } from '@/lib/auth_new';
import { api } from '@/services/api';
import { cn } from '@/lib/utils';
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
import {
  stringifyBusinessValue,
  isTechnicalApprovalPayload,
  toPlainRecord,
  meaningfulResultKeys,
  extractBusinessResultPayload,
  findPreparedResultPayload,
  hasPreparedMessageText,
  resultPayloadStatus,
  isBusinessBlockerPayload,
  isBusinessBlockerApproval,
  buildEmployeeTestResult,
  versionHasGoogleSheetsReadStep,
  detailsHaveGoogleSheetsReadStep,
  needsScenarioRebuildForSourceResult,
  needsGoogleSheetsSourceSetup,
  needsGoogleAccessReconnect,
  hasFreshGoogleSheetsAccessAfterResult,
  buildEmployeeHistoryStory,
  buildEmployeeAttentionItems,
  buildAttentionInbox,
  buildConfidenceFacts,
  buildScenarioPipeline,
  buildBusinessHistoryEvents,
  humanizeSourceType,
  humanizeSourceState,
  formatSourceSize
} from './results';
import {
  parseAgentConfig,
  uploadAgentSource
} from './api';

import {
  RecommendedProviderRouteNote
} from './builder_setup';
import {
  AgentIntegrationsPanel
} from './workspace';

const AGENT_BLUEPRINT_LEGACY_SOURCE_CONTRACT_LABELS = [
  'Preflight и preview run',
  'Тест без отправки',
  'Архивировать',
  'Запустить preview',
  'OpenClaw planner',
  'Техническая диагностика LocalOS/OpenClaw',
  'Принять план',
  'План принят',
  'План агента',
  'compiled workflow candidate',
  'Создать агента и открыть preview',
  'У бизнеса уже есть несколько подходящих коннектов',
  'Запустите безопасный тест',
  'Последний run',
  'Симуляция compiled workflow',
  'workflow проверен',
  'Единый billing ledger',
  'без решения человека агент не продолжит внешний шаг',
  "Preview: {gate.preview_run_status?.ready ? 'пройден' : 'нужен'}",
  "Preflight: {gate.preflight?.ready ? 'готов' : 'проверить'}",
  "Compiled: {gate.compiled_validation?.ready ? 'валиден' : 'проверить'}",
  "Policy: {gate.approval_policy_status?.ready ? 'готова' : 'проверить'}",
  'approvals и limits готовы',
  'нужен human gate',
  'Activation gate',
  'Что показал preview run',
  'Activation gate готов',
  'Action ledger',
  'reserve ${item.billing_summary?.reserved_tokens',
];

const StatusBadge = ({ status }: { status: string }) => (
  <span className={cn('inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ring-1', statusTone[status] || 'bg-slate-50 text-slate-600 ring-slate-200')}>
    {userFacingAgentTechText(humanizeStatus(status))}
  </span>
);

export const AgentConnectionsPanel = ({
  agentIntegrations,
  availableAgentIntegrations,
  agentIntegrationCatalog,
  agentExternalAuthOptions,
  agentBindingStatus,
  agentConnectionPlan,
  postCreateHandoff,
  selectedConnectionBindingKey,
  sheetSpreadsheetId,
  sheetName,
  sheetAuthRef,
  sheetDailyCap,
  browserTargetUrls,
  browserDailyCap,
  telegramBotMode,
  telegramDailyCap,
  whatsappChannelMode,
  whatsappDailyCap,
  matonAuthRef,
  matonChannel,
  matonDailyCap,
  processRowValues,
  processPreviewMessage,
  actionLoading,
  onSheetSpreadsheetIdChange,
  onSheetNameChange,
  onSheetAuthRefChange,
  onSheetDailyCapChange,
  onBrowserTargetUrlsChange,
  onBrowserDailyCapChange,
  onTelegramBotModeChange,
  onTelegramDailyCapChange,
  onWhatsappChannelModeChange,
  onWhatsappDailyCapChange,
  onMatonAuthRefChange,
  onMatonChannelChange,
  onMatonDailyCapChange,
  onProcessRowValuesChange,
  onProcessPreviewMessageChange,
  onSaveSheetIntegration,
  onSaveBrowserUseIntegration,
  onSaveTelegramIntegration,
  onSaveWhatsappIntegration,
  onSaveMatonIntegration,
  onChooseProviderRoute,
  onAttachExistingIntegration,
  onSelectConnectionBinding,
  onSaveCustomProcess,
  onRunCustomProcessPreview,
  onPreviewRun,
}: {
  agentIntegrations: AgentIntegration[];
  availableAgentIntegrations: AgentIntegration[];
  agentIntegrationCatalog: AgentIntegrationCatalogItem[];
  agentExternalAuthOptions: AgentExternalAuthOption[];
  agentBindingStatus: AgentIntegrationBindingStatus[];
  agentConnectionPlan: AgentConnectionPlan | null;
  postCreateHandoff: AgentPostCreateHandoff | null;
  selectedConnectionBindingKey: string;
  sheetSpreadsheetId: string;
  sheetName: string;
  sheetAuthRef: string;
  sheetDailyCap: string;
  browserTargetUrls: string;
  browserDailyCap: string;
  telegramBotMode: string;
  telegramDailyCap: string;
  whatsappChannelMode: string;
  whatsappDailyCap: string;
  matonAuthRef: string;
  matonChannel: string;
  matonDailyCap: string;
  processRowValues: string;
  processPreviewMessage: string;
  actionLoading: boolean;
  onSheetSpreadsheetIdChange: (value: string) => void;
  onSheetNameChange: (value: string) => void;
  onSheetAuthRefChange: (value: string) => void;
  onSheetDailyCapChange: (value: string) => void;
  onBrowserTargetUrlsChange: (value: string) => void;
  onBrowserDailyCapChange: (value: string) => void;
  onTelegramBotModeChange: (value: string) => void;
  onTelegramDailyCapChange: (value: string) => void;
  onWhatsappChannelModeChange: (value: string) => void;
  onWhatsappDailyCapChange: (value: string) => void;
  onMatonAuthRefChange: (value: string) => void;
  onMatonChannelChange: (value: string) => void;
  onMatonDailyCapChange: (value: string) => void;
  onProcessRowValuesChange: (value: string) => void;
  onProcessPreviewMessageChange: (value: string) => void;
  onSaveSheetIntegration: () => void;
  onSaveBrowserUseIntegration: () => void;
  onSaveTelegramIntegration: () => void;
  onSaveWhatsappIntegration: () => void;
  onSaveMatonIntegration: () => void;
  onChooseProviderRoute: (bindingKey: string, route: AgentProviderRoute) => void;
  onAttachExistingIntegration: (integration: AgentIntegration, bindingKey?: string) => void;
  onSelectConnectionBinding: (bindingKey: string) => void;
  onSaveCustomProcess: () => void;
  onRunCustomProcessPreview: () => void;
  onPreviewRun: () => void;
}) => (
  <div className="space-y-4">
    {postCreateHandoff?.status === 'needs_connections' ? (
      <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm leading-6 text-amber-950">
        <div className="font-semibold">{userFacingAgentTechText(postCreateHandoff.title || 'Остались подключения')}</div>
        <div className="mt-1">{userFacingAgentTechText(postCreateHandoff.description || 'Заполните обязательные подключения, затем проверьте агента на примере.')}</div>
        {postCreateHandoff.missing_bindings?.length ? (
          <div className="mt-2 flex flex-wrap gap-2">
            {postCreateHandoff.missing_bindings.slice(0, 4).map((binding) => (
              <span key={binding.key || binding.provider} className="rounded-full bg-white px-2.5 py-1 text-xs font-medium text-amber-900 ring-1 ring-amber-200">
                {connectorLabel(binding.provider)}{binding.missing_config?.length ? `: ${binding.missing_config.map((item) => userFacingAgentTechText(humanizeMeta(item))).join(', ')}` : ''}
              </span>
            ))}
          </div>
        ) : null}
      </div>
    ) : null}
    <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
      <div className="text-sm font-semibold text-slate-950">Подключения агента</div>
          <div className="mt-1 max-w-3xl text-sm leading-6 text-slate-600">
	        Настройте один следующий доступ. После сохранения LocalOS покажет тест без внешних действий.
      </div>
    </div>
    <AgentIntegrationsPanel
      integrations={agentIntegrations}
      availableIntegrations={availableAgentIntegrations}
      providerCatalog={agentIntegrationCatalog}
      authOptions={agentExternalAuthOptions}
      bindingStatus={agentBindingStatus}
      connectionPlan={agentConnectionPlan}
      selectedBindingKey={selectedConnectionBindingKey}
      sheetSpreadsheetId={sheetSpreadsheetId}
      sheetName={sheetName}
      sheetAuthRef={sheetAuthRef}
      sheetDailyCap={sheetDailyCap}
      browserTargetUrls={browserTargetUrls}
      browserDailyCap={browserDailyCap}
      telegramBotMode={telegramBotMode}
      telegramDailyCap={telegramDailyCap}
      whatsappChannelMode={whatsappChannelMode}
      whatsappDailyCap={whatsappDailyCap}
      matonAuthRef={matonAuthRef}
      matonChannel={matonChannel}
      matonDailyCap={matonDailyCap}
      processRowValues={processRowValues}
      processPreviewMessage={processPreviewMessage}
      actionLoading={actionLoading}
      onSheetSpreadsheetIdChange={onSheetSpreadsheetIdChange}
      onSheetNameChange={onSheetNameChange}
      onSheetAuthRefChange={onSheetAuthRefChange}
      onSheetDailyCapChange={onSheetDailyCapChange}
      onBrowserTargetUrlsChange={onBrowserTargetUrlsChange}
      onBrowserDailyCapChange={onBrowserDailyCapChange}
      onTelegramBotModeChange={onTelegramBotModeChange}
      onTelegramDailyCapChange={onTelegramDailyCapChange}
      onWhatsappChannelModeChange={onWhatsappChannelModeChange}
      onWhatsappDailyCapChange={onWhatsappDailyCapChange}
      onMatonAuthRefChange={onMatonAuthRefChange}
      onMatonChannelChange={onMatonChannelChange}
      onMatonDailyCapChange={onMatonDailyCapChange}
      onProcessRowValuesChange={onProcessRowValuesChange}
      onProcessPreviewMessageChange={onProcessPreviewMessageChange}
        onSaveSheetIntegration={onSaveSheetIntegration}
        onSaveBrowserUseIntegration={onSaveBrowserUseIntegration}
        onSaveTelegramIntegration={onSaveTelegramIntegration}
        onSaveWhatsappIntegration={onSaveWhatsappIntegration}
        onSaveMatonIntegration={onSaveMatonIntegration}
        onChooseProviderRoute={onChooseProviderRoute}
      onAttachExistingIntegration={onAttachExistingIntegration}
      onSelectBinding={onSelectConnectionBinding}
      onSaveCustomProcess={onSaveCustomProcess}
      onRunCustomProcessPreview={onRunCustomProcessPreview}
      onPreviewRun={onPreviewRun}
    />
    <details className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
      <summary className="cursor-pointer text-sm font-semibold text-slate-950">Технические детали</summary>
      <div className="mt-3">
        <AgentConnectionPlanPanel
          connectionPlan={agentConnectionPlan}
          availableIntegrations={availableAgentIntegrations}
          actionLoading={actionLoading}
          onAttachExistingIntegration={onAttachExistingIntegration}
          onConfigureBinding={onSelectConnectionBinding}
          onChooseProviderRoute={onChooseProviderRoute}
        />
      </div>
    </details>
  </div>
);

export const AgentConnectionPlanPanel = ({
  connectionPlan,
  compact = false,
  availableIntegrations = [],
  actionLoading = false,
  onAttachExistingIntegration,
  onConfigureBinding,
  onChooseProviderRoute,
}: {
  connectionPlan: AgentConnectionPlan | null;
  compact?: boolean;
  availableIntegrations?: AgentIntegration[];
  actionLoading?: boolean;
  onAttachExistingIntegration?: (integration: AgentIntegration, bindingKey?: string) => void;
  onConfigureBinding?: (bindingKey: string) => void;
  onChooseProviderRoute?: (bindingKey: string, route: AgentProviderRoute) => void;
}) => {
  const items = Array.isArray(connectionPlan?.items) ? connectionPlan.items : [];
  if (!items.length) {
    return null;
  }
  const missingCount = typeof connectionPlan?.missing_count === 'number'
    ? connectionPlan.missing_count
    : items.filter((item) => !['ready', 'native_ready'].includes(item.action || '')).length;
  return (
    <div className={cn(compact ? 'mt-3 rounded-xl border px-3 py-3' : 'rounded-2xl border px-4 py-4', missingCount ? 'border-amber-200 bg-amber-50/70' : 'border-emerald-200 bg-emerald-50/70')}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-slate-950">План подключений</div>
          <div className="mt-1 text-xs leading-5 text-slate-600">
            {missingCount ? 'LocalOS понял, какие доступы нужны агенту. Завершите пункты ниже перед включением.' : 'Все обязательные доступы готовы для проверки и включения.'}
          </div>
        </div>
        <span className={cn('rounded-full px-2.5 py-1 text-xs font-medium ring-1', missingCount ? 'bg-white text-amber-800 ring-amber-200' : 'bg-white text-emerald-800 ring-emerald-200')}>
          {missingCount ? `${missingCount} действий` : 'готово'}
        </span>
      </div>
      <div className={cn('mt-3 grid gap-2', compact ? 'sm:grid-cols-1' : 'lg:grid-cols-2')}>
        {(compact ? items.slice(0, 3) : items).map((item) => {
          const matchingExisting = (item.existing_integrations || [])
            .map((summary) => availableIntegrations.find((integration) => integration.id === summary.id))
            .filter((integration) => Boolean(integration));
          return (
          <div key={item.key || item.provider || item.title} className="rounded-xl bg-white px-3 py-3 text-sm ring-1 ring-slate-200">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="font-semibold text-slate-950">{item.title || connectorLabel(item.provider)}</div>
                <div className="mt-1 text-xs leading-5 text-slate-500">
	                  {userFacingAgentTechText(humanizeMeta(item.capability || item.trigger || item.direction || item.provider || 'binding'))}
                </div>
              </div>
              <span className={cn('shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ring-1', connectionActionTone(item.action || ''))}>
	                {userFacingAgentTechText(item.primary_label || humanizeMeta(item.action || 'проверить'))}
              </span>
            </div>
	            <div className="mt-2 text-xs leading-5 text-slate-600">{userFacingAgentTechText(item.route_summary || item.explanation || bindingActionHint({ key: item.key || '', provider: item.provider || '', status: item.binding_status || '' }))}</div>
            {item.why_blocked && item.action !== 'ready' && item.action !== 'native_ready' ? (
              <div className="mt-2 rounded-lg bg-amber-50 px-2.5 py-2 text-xs leading-5 text-amber-900 ring-1 ring-amber-100">
	                Чего не хватает: {userFacingAgentTechText(item.why_blocked)}
              </div>
            ) : null}
            {item.policy_summary ? (
              <div className="mt-2 rounded-lg bg-slate-50 px-2.5 py-2 text-xs leading-5 text-slate-700 ring-1 ring-slate-100">
	                {userFacingAgentTechText(item.policy_summary)}
              </div>
            ) : null}
            {agentPolicyFacts(item).length ? (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {agentPolicyFacts(item).map((fact) => (
                  <span key={`${item.key}-${fact}`} className="rounded-full bg-slate-50 px-2 py-0.5 text-[11px] font-medium text-slate-600 ring-1 ring-slate-200">
                    {userFacingAgentTechText(humanizeMeta(fact))}
                  </span>
                ))}
              </div>
            ) : null}
            {item.provider_routes?.length ? (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {item.provider_routes.slice(0, 5).map((route) => (
                  <ProviderActionPill
                    key={`${item.key}-${route.provider}-${route.role}`}
                    route={route}
                    disabled={actionLoading || !item.key}
                    onChoose={compact ? undefined : onChooseProviderRoute ? () => onChooseProviderRoute(item.key || '', route) : undefined}
                  />
                ))}
              </div>
            ) : null}
            <RecommendedProviderRouteNote
              route={item.recommended_route}
              reason={item.recommended_route_reason}
            />
            {item.existing_integrations?.length ? (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {item.existing_integrations.slice(0, 3).map((integration) => (
                  <span key={integration.id || integration.display_name} className="rounded-full bg-sky-50 px-2 py-0.5 text-[11px] font-medium text-sky-700 ring-1 ring-sky-100">
                    {integration.display_name || connectorLabel(integration.provider)}
                  </span>
                ))}
              </div>
            ) : null}
            {!compact && item.action === 'choose_existing' && matchingExisting.length && onAttachExistingIntegration ? (
              <div className="mt-2 flex flex-wrap gap-2">
                {matchingExisting.slice(0, 3).map((integration) => integration ? (
                  <Button
                    key={integration.id}
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() => onAttachExistingIntegration(integration, item.key || '')}
                    disabled={actionLoading}
                  >
                    Использовать {integration.display_name || connectorLabel(integration.provider)}
                  </Button>
                ) : null)}
              </div>
            ) : null}
            {!compact && item.action !== 'ready' && item.action !== 'native_ready' && onConfigureBinding ? (
              <div className="mt-2">
                <Button
                  type="button"
                  size="sm"
                  variant={item.action === 'choose_existing' ? 'outline' : 'default'}
                  onClick={() => onConfigureBinding(item.key || '')}
                  disabled={actionLoading || !item.key}
                >
                  {userFacingAgentTechText(item.setup_cta?.label || `Настроить ${connectorLabel(item.provider)}`)}
                </Button>
              </div>
            ) : null}
            {item.provider_paths?.length ? (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {item.provider_paths.slice(0, 4).map((path) => (
                  <span key={`${path.provider}-${path.status}`} className="rounded-full bg-slate-50 px-2 py-0.5 text-[11px] text-slate-600 ring-1 ring-slate-200">
                    {userFacingAgentTechText(path.label || connectorLabel(path.provider))}: {userFacingAgentTechText(humanizeMeta(path.status || 'unknown'))}
                  </span>
                ))}
              </div>
            ) : null}
          </div>
          );
        })}
      </div>
      {compact && items.length > 3 ? (
        <div className="mt-2 text-[11px] leading-4 text-slate-500">Ещё {items.length - 3} подключений будут видны после создания черновика.</div>
      ) : null}
    </div>
  );
};

export const connectionActionTone = (action: string) => {
  if (action === 'ready' || action === 'native_ready') {
    return 'bg-emerald-50 text-emerald-700 ring-emerald-200';
  }
  if (action === 'choose_existing' || action === 'choose_route') {
    return 'bg-sky-50 text-sky-700 ring-sky-200';
  }
  if (action === 'planned_provider') {
    return 'bg-slate-50 text-slate-600 ring-slate-200';
  }
  return 'bg-amber-50 text-amber-700 ring-amber-200';
};

export const agentPolicyFacts = (item: AgentConnectionPlanItem) => {
  const rawFacts = [
    item.autonomy_level,
    item.execution_boundary,
    item.credential_state,
    item.approval_state,
    item.next_action_label,
  ];
  const facts: string[] = [];
  rawFacts.forEach((fact) => {
    const normalized = String(fact || '').trim();
    if (normalized && !facts.includes(normalized)) {
      facts.push(normalized);
    }
  });
  return facts.slice(0, 5);
};

export const providerRouteLabel = (state: string) => ({
  connected: 'подключено',
  available: 'доступно',
  manual: 'ручной режим',
  planned: 'позже',
  unavailable: 'недоступно',
}[state] || humanizeMeta(state || 'unknown'));

export const providerRouteTone = (state: string) => {
  if (state === 'connected' || state === 'available') {
    return 'bg-emerald-50 text-emerald-700 ring-emerald-200';
  }
  if (state === 'manual') {
    return 'bg-sky-50 text-sky-700 ring-sky-200';
  }
  if (state === 'planned') {
    return 'bg-slate-50 text-slate-600 ring-slate-200';
  }
  return 'bg-rose-50 text-rose-700 ring-rose-200';
};

export const providerActionLabel = (route?: AgentProviderRoute | null) => {
  const action = route?.provider_action;
  if (action?.label) {
    return userFacingAgentTechText(action.label);
  }
  return userFacingAgentTechText(route?.primary_cta || providerRouteLabel(route?.state || route?.status || ''));
};

export const providerActionDescription = (route?: AgentProviderRoute | null) => {
  const action = route?.provider_action;
  if (action?.description) {
    return userFacingAgentTechText(action.description);
  }
  if (route?.connect_mode === 'openclaw_policy_boundary') {
    return 'Этот способ работает внутри правил безопасности, ручных подтверждений, журнала и лимитов LocalOS.';
  }
  if (route?.connect_mode === 'external_account_key') {
    return 'Выберите сохранённый ключ доступа или добавьте его в интеграциях бизнеса.';
  }
  if (route?.connect_mode === 'planned_oauth_connector') {
    return 'Подключение через OAuth запланировано, но пока не позволяет включить агента.';
  }
  return '';
};

export const ProviderActionPill = ({
  route,
  onChoose,
  disabled = false,
}: {
  route?: AgentProviderRoute | null;
  onChoose?: () => void;
  disabled?: boolean;
}) => {
  if (!route) {
    return null;
  }
  const state = route.state || route.status || '';
  const canChoose = Boolean(onChoose && ['openclaw', 'maton', 'manual'].includes(route.provider || '') && route.provider_action?.available !== false && ['available', 'connected', 'manual'].includes(state));
  const className = cn(
    'rounded-full px-2 py-0.5 text-[11px] font-medium ring-1',
    providerRouteTone(state),
    canChoose ? 'transition hover:shadow-sm disabled:cursor-not-allowed disabled:opacity-60' : '',
  );
  const label = `${userFacingAgentTechText(route.label || connectorLabel(route.provider))} · ${providerActionLabel(route)}`;
  if (canChoose) {
    return (
      <button type="button" className={className} onClick={onChoose} disabled={disabled}>
        {label}
      </button>
    );
  }
  return (
    <span className={className}>
      {label}
    </span>
  );
};
