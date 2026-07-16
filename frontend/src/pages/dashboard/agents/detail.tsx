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
  builderPreviewDataText
} from './builder_setup';
import {
  AgentConnectionsPanel,
  AgentConnectionPlanPanel
} from './connections';
import {
  AgentAdvancedPanel,
  AgentVoiceStylePanel,
  AgentWorkspacePanel
} from './workspace';
import {
  AgentRunReviewPanel,
  GenericRunProgress,
  OutreachRunProgress,
  PreviewRunSummaryPanel
} from './runs';

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

export const AgentDetailPanel = ({
  mode,
  blueprint,
  blueprintDetails,
  activeRun,
  availablePersonaAgents,
  pendingApproval,
  queuedButNotDispatched,
  agentReview,
  feedbackText,
  feedbackTrigger,
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
  onDeleteAgent,
  onFeedbackTextChange,
  onFeedbackTriggerChange,
  onSubmitFeedback,
  onActivateFeedbackVersion,
  onRollbackFeedbackVersion,
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
  onRunSourceChange,
  onRunCityChange,
  onRunCategoryChange,
  onRunLimitChange,
  onApplyFinanceRequests,
  showAdvancedTools,
}: {
  mode: AgentWorkspaceMode;
  blueprint: AgentBlueprint;
  blueprintDetails: AgentBlueprintDetails | null;
  activeRun: AgentRun | null;
  availablePersonaAgents: PersonaAgent[];
  pendingApproval: AgentApproval | null;
  queuedButNotDispatched: AgentArtifact['payload_json'] | AgentRunStep['output_json'] | null;
  agentReview: AgentReview | null;
  feedbackText: string;
  feedbackTrigger: string;
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
  onDeleteAgent: () => void;
  onFeedbackTextChange: (value: string) => void;
  onFeedbackTriggerChange: (value: string) => void;
  onSubmitFeedback: () => void;
  onActivateFeedbackVersion: (versionId: string) => void;
  onRollbackFeedbackVersion: (versionId: string) => void;
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
  onRunSourceChange: (value: string) => void;
  onRunCityChange: (value: string) => void;
  onRunCategoryChange: (value: string) => void;
  onRunLimitChange: (value: string) => void;
  onApplyFinanceRequests: (runId: string) => void;
  showAdvancedTools: boolean;
}) => {
  const latestVersionNumber = getActiveVersionNumber(blueprint, blueprintDetails);
  const activeVersionId = getActiveVersionId(blueprint, blueprintDetails);
  const activationGate = blueprintDetails?.activation_gate;
  const voiceName = getAgentVoiceName(blueprint, blueprintDetails);
  const versions = blueprintDetails?.versions || [];
  const listStatus = getAgentListStatus(blueprint);
  const settingsActive = mode === 'settings' || mode === 'connections' || mode === 'voice' || mode === 'advanced';
  const openConnectionsFromActivationGate = () => {
    if (activationGate?.next_binding_key) {
      onSelectConnectionBinding(activationGate.next_binding_key);
    }
    onModeChange('connections');
  };
  const handlePreviewNextStep = (nextStep: string) => {
    if (nextStep === 'connect_required_integrations') {
      onModeChange('connections');
      return;
    }
    if (nextStep === 'fix_preview_error') {
      onModeChange('settings');
      return;
    }
    if (nextStep === 'review_approvals') {
      onModeChange('results');
      return;
    }
    if (nextStep === 'check_activation_gate') {
      onModeChange('overview');
      return;
    }
    if (nextStep === 'review_preview') {
      onModeChange('run');
      return;
    }
    onModeChange('overview');
  };
  return (
  <DashboardSection contentClassName="px-0 py-0">
    <div className="border-b border-slate-100 px-6 py-5">
      <div className="min-w-0">
        <h2 className="max-w-5xl text-lg font-semibold leading-7 text-slate-950 sm:text-xl">
          {blueprint.name}
        </h2>
        <p className="mt-1 text-sm leading-6 text-slate-600">
          {humanizeCategory(blueprint.category)} · {latestVersionNumber ? 'рабочий сценарий опубликован' : 'рабочий сценарий ещё не включён'}{voiceName ? ` · стиль: ${voiceName}` : ''}
        </p>
      </div>
      <div className="mt-4 flex max-w-full flex-wrap gap-2">
        <Button type="button" size="sm" className="shrink-0" variant={mode === 'overview' ? 'default' : 'outline'} onClick={() => onModeChange('overview')}>Обзор</Button>
        <Button type="button" size="sm" className="shrink-0" variant={mode === 'results' ? 'default' : 'outline'} onClick={() => onModeChange('results')}>История</Button>
        <Button type="button" size="sm" className="shrink-0" variant={mode === 'run' ? 'default' : 'outline'} onClick={() => onModeChange('run')}>Сценарий</Button>
        <Button type="button" size="sm" className="shrink-0" variant={settingsActive ? 'default' : 'outline'} onClick={() => onModeChange('settings')}>Настройки</Button>
        <Button type="button" size="sm" className="shrink-0 text-red-700 hover:text-red-800" variant="outline" onClick={onDeleteAgent} disabled={actionLoading}>
          <Trash2 className="mr-2 h-4 w-4" />
          Убрать из списка
        </Button>
      </div>
    </div>
    <div className="px-6 py-5">
    {mode === 'overview' ? (
      <AgentOverviewPanel
        blueprint={blueprint}
        detailsBlueprint={blueprintDetails?.blueprint}
        latestVersionNumber={latestVersionNumber}
        voiceName={voiceName}
        listStatus={listStatus}
        pendingApproval={pendingApproval}
        review={agentReview}
        metrics={blueprintDetails?.metrics}
        activationGate={activationGate}
        bindingStatus={agentBindingStatus}
        actionLoading={actionLoading}
        onStartRun={onStartRun}
        onActivateVersion={onActivateVersion}
        onOpenLogic={() => onModeChange('settings')}
        onOpenResults={() => onModeChange('results')}
        onOpenConnections={openConnectionsFromActivationGate}
        onOpenVoice={() => onModeChange('voice')}
        onDeleteAgent={onDeleteAgent}
      />
    ) : null}

    {mode === 'settings' ? (
      <div className="space-y-4">
        <AgentWorkspacePanel
        versions={versions}
        learningEvents={blueprintDetails?.learning_events || []}
        versionEvents={blueprintDetails?.version_events || []}
        legacyMigration={blueprintDetails?.legacy_migration || {}}
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
        <AgentSettingsHub
          showAdvancedTools={showAdvancedTools}
          onOpenConnections={() => onModeChange('connections')}
          onOpenVoice={() => onModeChange('voice')}
          onOpenAdvanced={() => onModeChange('advanced')}
        />
      </div>
    ) : null}

    {mode === 'connections' ? (
      <AgentConnectionsPanel
        agentIntegrations={agentIntegrations}
        availableAgentIntegrations={availableAgentIntegrations}
        agentIntegrationCatalog={agentIntegrationCatalog}
        agentExternalAuthOptions={agentExternalAuthOptions}
        agentBindingStatus={agentBindingStatus}
        agentConnectionPlan={agentConnectionPlan}
        postCreateHandoff={postCreateHandoff}
        selectedConnectionBindingKey={selectedConnectionBindingKey}
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
        onSelectConnectionBinding={onSelectConnectionBinding}
        onSaveCustomProcess={onSaveCustomProcess}
        onRunCustomProcessPreview={onRunCustomProcessPreview}
        onPreviewRun={onStartRun}
      />
    ) : null}

    {mode === 'run' ? (
      <AgentScenarioPanel
        blueprint={blueprint}
        blueprintDetails={blueprintDetails}
        bindingStatus={agentBindingStatus}
        actionLoading={actionLoading}
        onStartRun={onStartRun}
        runSource={runSource}
        runCity={runCity}
        runCategory={runCategory}
        runLimit={runLimit}
        onRunSourceChange={onRunSourceChange}
        onRunCityChange={onRunCityChange}
        onRunCategoryChange={onRunCategoryChange}
        onRunLimitChange={onRunLimitChange}
      />
    ) : null}

    {mode === 'results' ? (
      <div className="space-y-4">
        <AgentBusinessHistoryPanel
          blueprintDetails={blueprintDetails}
          activeRun={activeRun}
        />
        {activeRun ? (
          <PreviewRunSummaryPanel
            summary={activeRun.observability?.preview_summary}
            runInput={activeRun.input_json && typeof activeRun.input_json === 'object' ? activeRun.input_json : {}}
            activationGate={activationGate}
            currentActiveVersionId={activeVersionId}
            actionLoading={actionLoading}
            onNextStepAction={handlePreviewNextStep}
            onActivateVersion={onActivateVersion}
          />
        ) : null}
        {pendingApproval ? (
          <AgentApprovalDecisionPanel
            approval={pendingApproval}
            actionLoading={actionLoading}
            onApprove={onApprove}
            onReject={onReject}
          />
        ) : null}
        {queuedButNotDispatched ? (
          <DashboardActionPanel
            title="Поставлено в очередь, но не отправлено"
            description="Агент поставил batch в безопасную очередь. Dispatcher не запускался из этого экрана."
            tone="amber"
          />
        ) : null}
        <details className="rounded-2xl border border-slate-200 bg-white px-4 py-3">
          <summary className="cursor-pointer text-sm font-semibold text-slate-700">
            Как агент дошёл до результата
          </summary>
          <div className="mt-4">
            {blueprint.category === 'outreach' ? (
              <OutreachRunProgress review={agentReview} activeRun={activeRun} />
            ) : (
              <GenericRunProgress
                category={blueprint.category}
                review={agentReview}
                activeRun={activeRun}
                pendingApproval={pendingApproval}
              />
            )}
          </div>
        </details>
        <details className="rounded-2xl border border-slate-200 bg-white px-4 py-3">
          <summary className="cursor-pointer text-sm font-semibold text-slate-700">
            Журнал и подробности
          </summary>
          <div className="mt-4">
            <AgentRunReviewPanel
              review={agentReview}
              latestVersionNumber={latestVersionNumber}
              feedbackText={feedbackText}
              feedbackTrigger={feedbackTrigger}
              feedbackVersionNotice={feedbackVersionNotice}
              actionLoading={actionLoading}
              onFeedbackTextChange={onFeedbackTextChange}
              onFeedbackTriggerChange={onFeedbackTriggerChange}
              onSubmitFeedback={onSubmitFeedback}
              onActivateFeedbackVersion={onActivateFeedbackVersion}
              onRollbackFeedbackVersion={onRollbackFeedbackVersion}
            />
          </div>
        </details>
        {activeRun ? null : (
          <DashboardEmptyState title="Нет активных запусков" description="Запустите агента из карточки, чтобы увидеть результат." />
        )}
      </div>
    ) : null}
    {mode === 'voice' ? (
      <AgentVoiceStylePanel
        blueprint={blueprint}
        availablePersonaAgents={availablePersonaAgents}
      />
    ) : null}
    {showAdvancedTools && mode === 'advanced' ? (
      <AgentAdvancedPanel
        activeRun={activeRun}
        versions={versions}
        activationGate={activationGate}
        actionLoading={actionLoading}
        onPreviewNextStepAction={handlePreviewNextStep}
        onActivateVersion={onActivateVersion}
        onApplyFinanceRequests={onApplyFinanceRequests}
      />
    ) : null}
    </div>
  </DashboardSection>
  );
};

export const AgentBusinessHistoryPanel = ({
  blueprintDetails,
  activeRun,
}: {
  blueprintDetails: AgentBlueprintDetails | null;
  activeRun: AgentRun | null;
}) => {
  const events = buildBusinessHistoryEvents(blueprintDetails, activeRun);
  return (
    <div className="rounded-2xl border border-slate-200 bg-white px-4 py-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-slate-950">История работы</div>
          <div className="mt-1 text-sm leading-6 text-slate-600">События бизнеса: что подготовлено, что ждёт решения и чем завершился запуск.</div>
        </div>
        <span className="rounded-full bg-slate-50 px-2.5 py-1 text-xs font-medium text-slate-600 ring-1 ring-slate-200">
          {events.length ? `${events.length} событий` : 'пусто'}
        </span>
      </div>
      <div className="mt-4 grid gap-2">
        {events.length ? (
          events.map((event) => (
            <div key={event.key} className="grid gap-2 rounded-xl bg-slate-50 px-3 py-3 text-sm ring-1 ring-slate-100 sm:grid-cols-[6rem_minmax(0,1fr)]">
              <div className="text-xs font-medium text-slate-500">{event.time}</div>
              <div>
                <div className="font-semibold text-slate-950">{event.title}</div>
                <div className="mt-1 leading-6 text-slate-600">{event.description}</div>
              </div>
            </div>
          ))
        ) : (
          <div className="rounded-xl bg-slate-50 px-3 py-3 text-sm leading-6 text-slate-600 ring-1 ring-slate-100">
            История появится после первого запуска или ручного решения.
          </div>
        )}
      </div>
    </div>
  );
};

export const AgentSettingsHub = ({
  showAdvancedTools,
  onOpenConnections,
  onOpenVoice,
  onOpenAdvanced,
}: {
  showAdvancedTools: boolean;
  onOpenConnections: () => void;
  onOpenVoice: () => void;
  onOpenAdvanced: () => void;
}) => (
  <div className="rounded-2xl border border-slate-200 bg-white px-4 py-4">
    <div className="text-sm font-semibold text-slate-950">Ещё настройки</div>
    <div className="mt-1 text-sm leading-6 text-slate-600">
      Подключения, голос, версии и диагностика доступны здесь, но не мешают обычному просмотру результата.
    </div>
    <div className="mt-4 grid gap-2 sm:grid-cols-3">
      <Button type="button" variant="outline" onClick={onOpenConnections}>
        <Database className="mr-2 h-4 w-4" />
        Подключения
      </Button>
      <Button type="button" variant="outline" onClick={onOpenVoice}>
        <MessageSquareText className="mr-2 h-4 w-4" />
        Голос и стиль
      </Button>
      {showAdvancedTools ? (
        <Button type="button" variant="outline" onClick={onOpenAdvanced}>
          <Wrench className="mr-2 h-4 w-4" />
          Диагностика
        </Button>
      ) : null}
    </div>
  </div>
);

export const AgentScenarioPanel = ({
  blueprint,
  blueprintDetails,
  bindingStatus,
  actionLoading,
  onStartRun,
  runSource,
  runCity,
  runCategory,
  runLimit,
  onRunSourceChange,
  onRunCityChange,
  onRunCategoryChange,
  onRunLimitChange,
}: {
  blueprint: AgentBlueprint;
  blueprintDetails: AgentBlueprintDetails | null;
  bindingStatus: AgentIntegrationBindingStatus[];
  actionLoading: boolean;
  onStartRun: () => void;
  runSource: string;
  runCity: string;
  runCategory: string;
  runLimit: string;
  onRunSourceChange: (value: string) => void;
  onRunCityChange: (value: string) => void;
  onRunCategoryChange: (value: string) => void;
  onRunLimitChange: (value: string) => void;
}) => {
  const steps = buildScenarioPipeline(blueprint, blueprintDetails, bindingStatus);
  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-slate-200 bg-white px-4 py-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <div className="text-sm font-semibold text-slate-950">Что будет делать агент</div>
            <div className="mt-1 max-w-3xl text-sm leading-6 text-slate-600">
              Это рабочий сценарий человеческим языком. Техническое представление скрыто ниже и не меняет опубликованную логику само по себе.
            </div>
          </div>
          <Button type="button" onClick={onStartRun} disabled={actionLoading}>
            {actionLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Play className="mr-2 h-4 w-4" />}
            Проверить без отправки
          </Button>
        </div>
        <div className="mt-5 grid gap-3">
          {steps.map((step, index) => (
            <div key={step.key} className="grid gap-3 rounded-xl bg-slate-50 px-3 py-3 ring-1 ring-slate-100 sm:grid-cols-[auto_minmax(0,1fr)]">
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-white text-sm font-semibold text-slate-800 ring-1 ring-slate-200">
                {index + 1}
              </div>
              <div>
                <div className="text-sm font-semibold text-slate-950">{step.title}</div>
                <div className="mt-1 text-sm leading-6 text-slate-600">{step.description}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {blueprint.category === 'outreach' ? (
        <details className="rounded-2xl border border-slate-200 bg-white px-4 py-3">
          <summary className="cursor-pointer text-sm font-semibold text-slate-700">Параметры проверки поиска</summary>
          <div className="mt-4 grid gap-3 md:grid-cols-4">
            <input className="rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-slate-400" value={runSource} onChange={(event) => onRunSourceChange(event.target.value)} placeholder="Источник" />
            <input className="rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-slate-400" value={runCity} onChange={(event) => onRunCityChange(event.target.value)} placeholder="Город" />
            <input className="rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-slate-400" value={runCategory} onChange={(event) => onRunCategoryChange(event.target.value)} placeholder="Категория" />
            <input className="rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-slate-400" value={runLimit} onChange={(event) => onRunLimitChange(event.target.value)} placeholder="Лимит" />
          </div>
        </details>
      ) : null}

      <details className="rounded-2xl border border-slate-200 bg-white px-4 py-3">
        <summary className="cursor-pointer text-sm font-semibold text-slate-700">Показать техническое представление</summary>
        <div className="mt-4 rounded-xl bg-slate-950 px-3 py-3 text-xs leading-5 text-slate-100">
          <pre className="max-h-80 overflow-auto whitespace-pre-wrap">{JSON.stringify(blueprintDetails?.active_version || blueprintDetails?.versions?.[0] || {}, null, 2)}</pre>
        </div>
      </details>
    </div>
  );
};

export const AgentApprovalDecisionPanel = ({
  approval,
  actionLoading,
  onApprove,
  onReject,
  compact = false,
}: {
  approval: AgentApproval;
  actionLoading: boolean;
  onApprove?: () => void;
  onReject?: () => void;
  compact?: boolean;
}) => {
  const labels = approvalActionLabels(approval);
  const previewItems = getApprovalPreviewItems(approval);
  return (
    <div className={cn(
      'rounded-2xl border border-amber-200 bg-amber-50 px-4 py-4 text-amber-950',
      compact ? 'text-sm' : '',
    )}>
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="text-sm font-semibold uppercase tracking-wide text-amber-700">Нужно решение человека</div>
          <h3 className="mt-1 text-lg font-semibold leading-7 text-slate-950">
            {approvalDecisionTitle(approval)}
          </h3>
          <div className="mt-2 text-sm leading-6 text-amber-900">
            {approval.title}. {explainApproval(approval)}
          </div>
        </div>
        {onApprove && onReject ? (
          <div className="flex shrink-0 flex-wrap gap-2">
            <Button type="button" onClick={onApprove} disabled={actionLoading}>
              {labels.approve}
            </Button>
            <Button type="button" variant="outline" onClick={onReject} disabled={actionLoading}>
              {labels.reject}
            </Button>
          </div>
        ) : null}
      </div>

      {previewItems.length ? (
        <div className="mt-4 grid gap-2 lg:grid-cols-2">
          {previewItems.map((item) => (
            <div key={`${item.label}-${item.value}`} className="rounded-xl bg-white/85 px-3 py-2 text-sm leading-6 text-slate-800 ring-1 ring-amber-100">
              <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">{item.label}</div>
              <div className="mt-1 line-clamp-4">{item.value}</div>
            </div>
          ))}
        </div>
      ) : (
        <div className="mt-4 rounded-xl bg-white/85 px-3 py-2 text-sm leading-6 text-slate-800 ring-1 ring-amber-100">
          <span className="font-semibold text-slate-950">Что просит агент: </span>{approval.title}. Агент не использует этот результат дальше, пока человек явно не примет решение.
        </div>
      )}

      <div className="mt-4 grid gap-2 md:grid-cols-2">
        <div className="rounded-xl bg-white/85 px-3 py-2 text-sm leading-6 text-slate-800 ring-1 ring-amber-100">
          <span className="font-semibold text-slate-950">Если нажать “Принять”: </span>{labels.approve}
        </div>
        <div className="rounded-xl bg-white/85 px-3 py-2 text-sm leading-6 text-slate-800 ring-1 ring-amber-100">
          <span className="font-semibold text-slate-950">Если нажать “Отклонить”: </span>{labels.reject}
        </div>
      </div>
    </div>
  );
};

export const AgentOverviewPanel = ({
  blueprint,
  detailsBlueprint,
  latestVersionNumber,
  voiceName,
  listStatus,
  pendingApproval,
  review,
  metrics,
  activationGate,
  bindingStatus,
  actionLoading,
  onStartRun,
  onActivateVersion,
  onOpenLogic,
  onOpenResults,
  onOpenConnections,
  onOpenVoice,
  onDeleteAgent,
}: {
  blueprint: AgentBlueprint;
  detailsBlueprint?: AgentBlueprint;
  latestVersionNumber: number | null;
  voiceName: string;
  listStatus: string;
  pendingApproval: AgentApproval | null;
  review: AgentReview | null;
  metrics?: AgentMetricsSummary;
  activationGate?: AgentActivationGate;
  bindingStatus: AgentIntegrationBindingStatus[];
  actionLoading: boolean;
  onStartRun: () => void;
  onActivateVersion: (versionId: string) => void;
  onOpenLogic: () => void;
  onOpenResults: () => void;
  onOpenConnections: () => void;
  onOpenVoice: () => void;
  onDeleteAgent: () => void;
}) => {
  const needsApproval = Boolean(pendingApproval || blueprint.pending_approvals_count);
  const compiledValid = metrics?.compiled?.validation_valid === true;
  const compiledKnown = Boolean(metrics?.compiled?.validation_status || metrics?.compiled?.candidate_status);
  const missingBindings = bindingStatus.filter((binding) => binding.status !== 'connected' && binding.status !== 'ready').length;
  const requiredBindings = bindingStatus.length || Number(metrics?.setup?.required_bindings || 0);
  const connectorsReady = requiredBindings === 0 || missingBindings === 0;
  const previewReady = activationGate?.preview_run_status?.ready === true;
  const activationVersionId = activationGate?.active_version_id || blueprint.active_version_id || '';
  const builderPreview = getBlueprintBuilderPreview(detailsBlueprint || blueprint);
  const taskAnswer = builderPreview?.understood_task || blueprint.description || blueprint.active_goal || blueprint.latest_goal || 'Настройте задачу агента.';
  const readyAnswer = needsApproval
    ? 'ждёт решения человека'
    : !connectorsReady
      ? 'нужно подключить сервисы'
      : compiledKnown && !compiledValid
        ? 'нужно исправить логику'
        : !previewReady
          ? 'готов к тесту'
          : activationGate?.can_activate
            ? 'можно включить'
            : humanizeStatus(listStatus);
  const readyTone: 'default' | 'warning' = needsApproval || !connectorsReady || (compiledKnown && !compiledValid) ? 'warning' : 'default';
  const missingAnswer = needsApproval
    ? 'одобрение перед внешним действием'
    : !connectorsReady
      ? `${missingBindings} из ${requiredBindings} подключений`
    : compiledKnown && !compiledValid
        ? 'проверенная логика'
        : !previewReady
          ? 'тест без отправки'
          : 'ничего критичного';
  const lastRunAnswer = formatLastRun(blueprint);

  return (
    <div className="space-y-4">
      {needsApproval ? (
      <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <div className="text-sm font-semibold text-slate-950">
              {pendingApproval ? approvalDecisionTitle(pendingApproval) : 'Ждёт решения человека'}
            </div>
            <div className="mt-1 text-sm leading-6 text-amber-900">
              {pendingApproval
                ? explainApproval(pendingApproval)
                : 'Проверьте ручное решение: без него агент не продолжит внешний шаг.'}
            </div>
            {pendingApproval ? (
              <div className="mt-2 grid gap-2 md:grid-cols-2">
                {getApprovalPreviewItems(pendingApproval).slice(0, 2).map((item) => (
                  <div key={`${item.label}-${item.value}`} className="rounded-xl bg-white/80 px-3 py-2 text-xs leading-5 text-amber-900 ring-1 ring-amber-100">
                    <span className="font-semibold text-slate-800">{item.label}: </span>{item.value}
                  </div>
                ))}
                <div className="rounded-xl bg-white/80 px-3 py-2 text-xs leading-5 text-amber-900 ring-1 ring-amber-100">
                  <span className="font-semibold text-slate-800">При “Принять”: </span>{approvalActionLabels(pendingApproval).approve}
                </div>
              </div>
            ) : null}
          </div>
          <div className="flex shrink-0 flex-wrap gap-2">
            <Button type="button" onClick={onOpenResults}>
              Открыть решение
            </Button>
            <Button type="button" variant="outline" onClick={onOpenLogic}>
              Изменить логику
            </Button>
          </div>
        </div>
      </div>
      ) : null}

      <AgentFourAnswerStrip
        task={taskAnswer}
        ready={readyAnswer}
        missing={missingAnswer}
        lastRun={lastRunAnswer}
        readyTone={readyTone}
        missingTone={missingAnswer === 'ничего критичного' ? 'default' : 'warning'}
      />

      <AgentProductCockpit
        blueprint={blueprint}
        preview={builderPreview}
        activationGate={activationGate}
        connectorsReady={connectorsReady}
        compiledReady={!compiledKnown || compiledValid}
        previewReady={previewReady}
        activationVersionId={activationVersionId}
        needsApproval={needsApproval}
        actionLoading={actionLoading}
        onOpenConnections={onOpenConnections}
        onOpenLogic={onOpenLogic}
        onOpenResults={onOpenResults}
        onStartRun={onStartRun}
        onActivateVersion={onActivateVersion}
      />

      <AgentConfidencePanel facts={buildConfidenceFacts(activationGate)} />

      {activationGate && !needsApproval ? (
        <ActivationGateDecisionCard
          gate={activationGate}
        />
      ) : null}

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(18rem,0.55fr)]">
        <div className="rounded-2xl border border-slate-200 bg-white px-4 py-4">
          <div className="text-sm font-semibold text-slate-950">Управление</div>
          <div className="mt-2 text-sm leading-7 text-slate-700">
            Здесь можно перейти к настройкам агента. Технические версии и журналы доступны в разделе “Техническое”.
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            <Button type="button" size="sm" variant="outline" onClick={onOpenLogic}>
              Логика и данные
            </Button>
            <Button type="button" size="sm" variant="outline" onClick={onOpenResults}>
              Запуски и обучение
            </Button>
            <Button type="button" size="sm" variant="outline" onClick={onOpenConnections}>
              Подключения
            </Button>
            <Button type="button" size="sm" variant="outline" onClick={onOpenVoice}>
              Голос и стиль
            </Button>
            <Button type="button" size="sm" variant="outline" className="text-red-700 hover:text-red-800" onClick={onDeleteAgent} disabled={actionLoading}>
              <Trash2 className="mr-2 h-4 w-4" />
              Убрать из списка
            </Button>
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white px-4 py-4">
          <div className="text-sm font-semibold text-slate-950">Стоимость</div>
          <div className="mt-2 rounded-xl bg-slate-50 px-3 py-2 text-xs leading-5 text-slate-600">
            {voiceName ? `Голос: ${voiceName}. ` : ''}
            До запуска показываем оценку, после запуска — фактическое списание за создание, тест, обычный запуск, внешнее действие и чат оператора.
          </div>
          <AgentBillingBreakdownPanel metrics={metrics} />
        </div>
      </div>
    </div>
  );
};

export const AgentProductCockpit = ({
  blueprint,
  preview,
  activationGate,
  connectorsReady,
  compiledReady,
  previewReady,
  activationVersionId,
  needsApproval,
  actionLoading,
  onOpenConnections,
  onOpenLogic,
  onOpenResults,
  onStartRun,
  onActivateVersion,
}: {
  blueprint: AgentBlueprint;
  preview: AgentBuilderPreview | null;
  activationGate?: AgentActivationGate;
  connectorsReady: boolean;
  compiledReady: boolean;
  previewReady: boolean;
  activationVersionId: string;
  needsApproval: boolean;
  actionLoading: boolean;
  onOpenConnections: () => void;
  onOpenLogic: () => void;
  onOpenResults: () => void;
  onStartRun: () => void;
  onActivateVersion: (versionId: string) => void;
}) => {
  const summary = preview?.connection_summary;
  const missingItems = (summary?.items || []).filter((item) => item.action && !['ready', 'native_ready'].includes(item.action));
  const readyItems = (summary?.items || []).filter((item) => item.action === 'ready' || item.action === 'native_ready');
  const setupFlow = preview?.setup_flow;
  const nextStep = activationGate?.next_step || setupFlow?.post_create_next_step || setupFlow?.next_step || '';
  const needsConnections = !connectorsReady || missingItems.length > 0 || nextStep === 'connect_required_integrations';
  const needsLogic = !compiledReady || nextStep === 'fix_compiled_workflow';
  const canActivate = !needsApproval && activationGate?.can_activate === true && Boolean(activationVersionId);
  const canPreview = connectorsReady && compiledReady && !previewReady;
  const primaryLabel = needsApproval
    ? 'Открыть решение'
    : canActivate
    ? 'Включить агента'
    : needsConnections
    ? 'Подключить сервисы'
    : canPreview
      ? 'Запустить тест'
      : needsLogic
        ? 'Открыть логику'
        : previewReady ? 'Открыть историю' : 'Запустить тест';
  const PrimaryIcon = needsApproval ? ShieldCheck : canActivate ? CheckCircle2 : needsConnections ? Database : canPreview ? Play : needsLogic ? Workflow : previewReady ? FileCheck2 : Play;
  const primaryAction = needsApproval ? onOpenResults : canActivate ? () => onActivateVersion(activationVersionId) : needsConnections ? onOpenConnections : canPreview ? onStartRun : needsLogic ? onOpenLogic : previewReady ? onOpenResults : onStartRun;
  const primaryVariant: 'default' | 'outline' = needsApproval || canActivate || needsConnections || canPreview || needsLogic ? 'default' : 'outline';
  const task = preview?.understood_task || blueprint.description || blueprint.active_goal || blueprint.latest_goal || 'Настройте задачу агента.';
  const uniqueReadyTitles = Array.from(new Set(readyItems.map((item) => item.title || connectorLabel(item.provider)).filter(Boolean)));
  const uniqueMissingTitles = Array.from(new Set(missingItems.map((item) => item.title || connectorLabel(item.provider)).filter(Boolean)));
  const dataText = preview?.data_sources?.length
    ? builderPreviewDataText(preview, task)
    : readyItems.length
      ? uniqueReadyTitles.join(', ')
      : 'будет видно после настройки';
  const requiredText = missingItems.length
    ? uniqueMissingTitles.join(', ')
    : connectorsReady
      ? 'подключения готовы'
      : 'проверить подключения';
  const proofHint = needsApproval
    ? 'Агент уже остановился на ручном решении. Откройте историю, проверьте результат и решите, продолжать ли следующий шаг.'
    : needsConnections
      ? 'Сначала подключите источник или канал. После этого здесь появится тестовый запуск без внешней отправки.'
      : canPreview
        ? 'Нажмите “Запустить тест”: LocalOS прочитает пример, подготовит результат и остановится перед внешним действием.'
        : previewReady
          ? 'Тест уже проходил. Откройте историю, чтобы посмотреть, что агент прочитал, что подготовил и где остановился.'
          : 'Запустите тест без внешней отправки и проверьте первый результат в истории.';
  const flowStatus = setupFlow?.status || (activationGate?.can_activate ? 'ready' : 'draft');
  return (
    <div className="rounded-2xl border border-slate-200 bg-white px-4 py-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <div className="text-sm font-semibold text-slate-950">Как проверить сейчас</div>
            <span className="rounded-full bg-slate-50 px-2 py-0.5 text-[11px] font-medium text-slate-600 ring-1 ring-slate-200">
              {agentFlowStatusLabel(flowStatus)}
            </span>
          </div>
          <div className="mt-2 text-sm leading-7 text-slate-700">{task}</div>
        </div>
        <Button type="button" variant={primaryVariant} onClick={primaryAction} disabled={actionLoading} className="shrink-0">
          {actionLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <PrimaryIcon className="mr-2 h-4 w-4" />}
          {primaryLabel}
        </Button>
      </div>
      <div className="mt-4 grid gap-2 md:grid-cols-3">
        <AgentCockpitFact icon={Database} label="1. Данные" value={dataText} ready={Boolean(preview?.data_sources?.length || readyItems.length)} />
        <AgentCockpitFact icon={ShieldCheck} label="2. Доступы" value={requiredText} ready={!needsConnections} />
        <AgentCockpitFact icon={Play} label="3. Тест" value={previewReady ? 'результат в истории' : canPreview ? 'можно запускать' : 'после подключения'} ready={previewReady || canPreview} />
      </div>
      <div className="mt-3 flex flex-col gap-3 rounded-xl bg-sky-50 px-3 py-3 text-sm leading-6 text-sky-950 ring-1 ring-sky-100 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">{proofHint}</div>
        <Button type="button" size="sm" variant="outline" onClick={onOpenResults} className="shrink-0 bg-white/80">
          История
        </Button>
      </div>
      {missingItems.length ? (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {missingItems.slice(0, 4).map((item) => (
            <button
              key={item.key || item.provider || item.title}
              type="button"
              onClick={onOpenConnections}
              className="rounded-full bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-800 ring-1 ring-amber-200 transition hover:bg-amber-100"
            >
              {userFacingAgentTechText(item.setup_cta?.label) || `Подключить ${item.title || connectorLabel(item.provider)}`}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
};

export const AgentConfidencePanel = ({ facts }: { facts: AgentConfidenceFact[] }) => (
  <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-4 text-emerald-950">
    <div className="flex items-start gap-3">
      <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-emerald-700" />
      <div className="min-w-0">
        <div className="text-sm font-semibold text-slate-950">Почему этому можно доверять</div>
        <div className="mt-1 text-sm leading-6 text-emerald-900">
          LocalOS запускает опубликованный сценарий, проверяет доступы и останавливается перед действиями, которые должен подтвердить человек.
        </div>
      </div>
    </div>
    <div className="mt-3 grid gap-2 md:grid-cols-2 xl:grid-cols-3">
      {facts.map((fact) => (
        <div key={fact.key} className="flex items-start gap-2 rounded-xl bg-white/80 px-3 py-2 text-sm leading-6 ring-1 ring-emerald-100">
          {fact.ready ? (
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
          ) : (
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
          )}
          <span className="text-slate-800">{fact.label}</span>
        </div>
      ))}
    </div>
  </div>
);

export const AgentFourAnswerStrip = ({
  task,
  ready,
  missing,
  lastRun,
  readyTone,
  missingTone,
}: {
  task: string;
  ready: string;
  missing: string;
  lastRun: string;
  readyTone: 'default' | 'warning';
  missingTone: 'default' | 'warning';
}) => (
  <div className="grid gap-3 xl:grid-cols-4">
    <AgentAnswerCard label="Что делает" value={task} />
    <AgentAnswerCard label="Готов ли" value={ready} tone={readyTone} />
    <AgentAnswerCard label="Чего не хватает" value={missing} tone={missingTone} />
    <AgentAnswerCard label="Последний запуск" value={lastRun} />
  </div>
);

export const AgentAnswerCard = ({
  label,
  value,
  tone = 'default',
}: {
  label: string;
  value: string;
  tone?: 'default' | 'warning';
}) => (
  <div className={cn(
    'rounded-2xl border px-4 py-3',
    tone === 'warning' ? 'border-amber-200 bg-amber-50' : 'border-slate-200 bg-white',
  )}>
    <div className={cn(
      'text-xs font-semibold uppercase',
      tone === 'warning' ? 'text-amber-700' : 'text-slate-500',
    )}>
      {label}
    </div>
    <div className="mt-1 line-clamp-3 text-sm font-semibold leading-6 text-slate-950">{value}</div>
  </div>
);

export const AgentCockpitFact = ({
  icon: Icon,
  label,
  value,
  ready,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
  ready: boolean;
}) => (
  <div className="rounded-xl bg-slate-50 px-3 py-3 ring-1 ring-slate-200">
    <div className="flex items-center gap-2 text-xs font-semibold uppercase text-slate-500">
      <Icon className={cn('h-4 w-4', ready ? 'text-emerald-600' : 'text-amber-600')} />
      {label}
    </div>
    <div className="mt-1 text-sm leading-6 text-slate-800">{value}</div>
  </div>
);

export const ActivationGateDecisionCard = ({
  gate,
}: {
  gate: AgentActivationGate;
}) => {
  const decision = buildActivationGateDecision(gate);
  const ready = decision.tone === 'ready';
  const choice = decision.tone === 'choice';
  const blocked = decision.tone === 'blocked';
  const needsAction = decision.tone === 'needs_action';
  const blockerText = activationBlockerText(gate);
  const pathSteps = buildActivationPathSteps(gate);
  return (
    <div className={cn(
      'rounded-2xl border px-4 py-4 text-sm leading-6',
      ready ? 'border-emerald-200 bg-emerald-50 text-emerald-950' : '',
      choice ? 'border-sky-200 bg-sky-50 text-sky-950' : '',
      needsAction ? 'border-amber-200 bg-amber-50 text-amber-950' : '',
      blocked ? 'border-rose-200 bg-rose-50 text-rose-950' : '',
      !ready && !choice && !needsAction && !blocked ? 'border-slate-200 bg-slate-50 text-slate-700' : '',
    )}>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="font-semibold">{userFacingAgentTechText(decision.title)}</div>
          <div className="mt-1 text-xs leading-5">{userFacingAgentTechText(decision.description)}</div>
          {blockerText && !ready ? (
            <div className="mt-2 rounded-xl bg-white/80 px-3 py-2 text-xs leading-5 ring-1 ring-current/10">
              Почему ждём: {userFacingAgentTechText(blockerText)}
            </div>
          ) : null}
          <div className="mt-2 flex flex-wrap gap-1.5">
            <span className="rounded-full bg-white/80 px-2 py-0.5 text-[11px] font-medium ring-1 ring-current/10">
              Тест: {gate.preview_run_status?.ready ? 'пройден' : 'нужен'}
            </span>
            <span className="rounded-full bg-white/80 px-2 py-0.5 text-[11px] font-medium ring-1 ring-current/10">
              Доступы: {gate.preflight?.ready ? 'готовы' : 'проверить'}
            </span>
            <span className="rounded-full bg-white/80 px-2 py-0.5 text-[11px] font-medium ring-1 ring-current/10">
              Логика: {gate.compiled_validation?.ready ? 'проверена' : 'проверить'}
            </span>
            <span className="rounded-full bg-white/80 px-2 py-0.5 text-[11px] font-medium ring-1 ring-current/10">
              Подтверждение: {gate.approval_policy_status?.ready ? 'готово' : 'проверить'}
            </span>
          </div>
          <AgentActivationPathStrip steps={pathSteps} />
        </div>
        <span className="rounded-full bg-white px-2.5 py-1 text-xs font-medium ring-1 ring-current/10">
          Карта готовности
        </span>
      </div>
      {!ready && gate.connection_plan ? (
        <AgentConnectionPlanPanel connectionPlan={gate.connection_plan} compact />
      ) : null}
    </div>
  );
};

export const AgentActivationPathStrip = ({ steps }: { steps: AgentActivationPathStep[] }) => (
  <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
    {steps.map((step, index) => {
      const done = step.status === 'done';
      const current = step.status === 'current';
      return (
        <div
          key={step.key}
          className={cn(
            'rounded-xl border bg-white/75 px-3 py-2 ring-1 ring-current/5',
            done ? 'border-emerald-200 text-emerald-900' : '',
            current ? 'border-sky-200 text-sky-900' : '',
            !done && !current ? 'border-slate-200 text-slate-500' : '',
          )}
        >
          <div className="flex items-center gap-2 text-xs font-semibold">
            <span className={cn(
              'flex h-5 w-5 items-center justify-center rounded-full text-[11px]',
              done ? 'bg-emerald-100 text-emerald-700' : '',
              current ? 'bg-sky-100 text-sky-700' : '',
              !done && !current ? 'bg-slate-100 text-slate-500' : '',
            )}>
              {done ? <CheckCircle2 className="h-3.5 w-3.5" /> : index + 1}
            </span>
            {step.label}
          </div>
          <div className="mt-1 text-[11px] leading-4 opacity-80">{step.detail}</div>
        </div>
      );
    })}
  </div>
);

export const AgentBillingBreakdownPanel = ({ metrics }: { metrics?: AgentMetricsSummary }) => {
  const ledger = metrics?.unified_billing_ledger;
  const items = ledger?.items || metrics?.billing_breakdown?.items || metrics?.cost_tokens?.breakdown || [];
  const visibleItems = items.filter((item) => Boolean(
    item.count
    || item.charged_credits
    || item.actual_credits
    || item.estimated_credits
    || item.estimated_tokens
    || item.actual_tokens
    || item.settled_tokens
    || item.actual_cost
    || item.total_cost,
  ));
  if (!visibleItems.length) {
    return (
      <div className="mt-3 rounded-xl bg-white px-3 py-2 text-xs leading-5 text-slate-500 ring-1 ring-slate-200">
        История списаний появится после создания, теста или обычного запуска.
      </div>
    );
  }
  return (
    <div className="mt-3 rounded-xl bg-white px-3 py-3 ring-1 ring-slate-200">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-center gap-2 text-xs font-semibold uppercase text-slate-500">
          <ReceiptText className="h-4 w-4 text-slate-500" />
          История списаний
        </div>
        <div className="text-xs leading-5 text-slate-500">
          Оценка до запуска: {formatBillingEstimateSummary(ledger)}
          <span className="mx-1 text-slate-300"> / </span>
          Факт после запуска: {formatBillingActualSummary(ledger)}
        </div>
      </div>
      <div className="mt-2 space-y-1.5">
        {visibleItems.slice(0, 5).map((item) => (
          <div key={item.key || item.label} className="grid gap-1 rounded-lg bg-slate-50 px-2.5 py-2 text-xs leading-5 sm:grid-cols-[minmax(0,1fr)_auto_auto] sm:items-center">
            <span className="min-w-0 truncate font-medium text-slate-700">{userFacingAgentTechText(item.label || humanizeMeta(item.key || 'cost'))}</span>
            <span className="text-slate-500">оценка {formatBillingEstimateValue(item)}</span>
            <span className="font-semibold text-slate-950">факт {formatBillingActualValue(item)}</span>
          </div>
        ))}
      </div>
    </div>
  );
};

export const formatBillingEstimateSummary = (ledger?: AgentUnifiedBillingLedger) => {
  const summary = ledger?.summary || {};
  const credits = Number(summary.estimated_credits || 0);
  if (!credits) {
    return 'нет';
  }
  return `${credits} кр.`;
};

export const formatBillingActualSummary = (ledger?: AgentUnifiedBillingLedger) => {
  const summary = ledger?.summary || {};
  const credits = Number(summary.actual_credits || 0);
  if (!credits) {
    return 'нет списаний';
  }
  return `${credits} кр.`;
};

export const formatBillingEstimateValue = (item: AgentBillingBreakdownItem) => {
  const credits = Number(item.estimated_credits || 0);
  if (credits) {
    return `${credits} кр.`;
  }
  return '0 кр.';
};

export const formatBillingActualValue = (item: AgentBillingBreakdownItem) => {
  const credits = Number(item.actual_credits || item.charged_credits || 0);
  if (credits) {
    return `${credits} кр.`;
  }
  return '0 кр.';
};
