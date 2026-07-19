import type React from 'react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useOutletContext } from 'react-router-dom';
import {
  Activity,
  AlertTriangle,
  Archive,
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
  Upload,
  Users,
  Wrench,
  Workflow,
  Zap,
} from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
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
  isAgentWorkRun,
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
  fetchLatestAgentRunId,
  parseAgentConfig,
  uploadAgentSource
} from './api';

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

import {
  CreateAgentWizard,
  BuilderProductSteps,
  BuilderTrustBlock,
  DialogAgentBuilder,
  BuilderTechnicalDiagnostics,
  CompiledBuilderFlow,
  BuilderCreationDecisionBanner
} from './builder_dialog';
import {
  BuilderRequiredConnectionsPanel,
  builderConnectionCardStatus,
  builderConnectionCardHint,
  compilerPolicyItemLabel,
  compilerPlanTriggerLabel,
  compilerPlanStepCopy,
  builderPreviewDataText,
  BuilderCompilerPolicyReviewPanel,
  RecommendedProviderRouteNote,
  builderConnectionStatusCopy,
  builderConnectionNextStepCopy,
  BuilderServiceIntelligencePanel,
  serviceIntelligenceTone,
  BuilderConnectionReadinessPanel,
  BuilderConnectionResolverPanel,
  resolverStateTone,
  BuilderSetupFlowPanel,
  BuilderConnectionSummaryPanel
} from './builder_setup';
import {
  AgentMiniMetric,
  ConnectorIntelligencePanel,
  BuilderPlannerLoopPanel,
  BuilderExecutionBoundaryPanel,
  PreviewRow,
  BuilderFeasibilityPanel,
  SystemAgentCard,
  AgentsTodaySection,
  TodayFact,
  AgentsAttentionInbox,
  AgentCommandCenter,
  BlueprintAgentCard,
  employeeToneClass,
  EmployeeStatusPill,
  AgentRunProgressPanel,
  EmployeeAgentsList,
  EmployeeAnswerCard,
  EmployeeRunningPanel,
  EmployeeTestResultPanel,
  EmployeeHistoryPanel,
  EmployeeWorkspaceSection,
  EmployeeResponsibilitiesList,
  agentExecutionModeOptions,
  AgentExecutionModePanel,
  AgentScheduleSetupPanel,
  employeeStateTitle,
  AgentRunParametersPanel,
  EmployeeAgentOverviewPanel,
  EmployeeAgentScenarioPanel,
  AgentCockpitPanel,
  CockpitTile,
  AgentSummaryPill,
  PersonaAgentCard
} from './employee';
import {
  AgentDetailPanel,
  AgentBusinessHistoryPanel,
  AgentSettingsHub,
  AgentScenarioPanel,
  AgentApprovalDecisionPanel,
  AgentOverviewPanel,
  AgentProductCockpit,
  AgentConfidencePanel,
  AgentFourAnswerStrip,
  AgentAnswerCard,
  AgentCockpitFact,
  ActivationGateDecisionCard,
  AgentActivationPathStrip,
  AgentBillingBreakdownPanel,
  formatBillingEstimateSummary,
  formatBillingActualSummary,
  formatBillingEstimateValue,
  formatBillingActualValue
} from './detail';
import {
  AgentConnectionsPanel,
  AgentConnectionPlanPanel,
  connectionActionTone,
  agentPolicyFacts,
  providerRouteLabel,
  providerRouteTone,
  providerActionLabel,
  providerActionDescription,
  ProviderActionPill
} from './connections';
import {
  AgentAdvancedPanel,
  AgentVoiceStylePanel,
  AgentWorkspacePanel,
  WizardTextArea,
  DatahubCatalogList,
  DatahubCatalogGroup,
  DatahubCatalogItem,
  AgentSourcesList,
  AgentConnectionDecisionBanner,
  AgentIntegrationsPanel,
  AgentIntegrationStatusItem,
  VersionSummary,
  LearningHistoryPanel,
  humanizeLearningTrigger,
  humanizeVersionAction,
  humanizeVersionState
} from './workspace';
import {
  AgentRunReviewPanel,
  buildJournalFromSections,
  GenericRunProgress,
  buildStepStatusMap,
  findJournalEntryForGenericStage,
  getGenericStageStatus,
  getGenericStageDetail,
  getOutputStageDetail,
  labelCount,
  compactJoin,
  OutreachRunProgress,
  findJournalDetailValue,
  JournalEntryCard,
  HumanPayloadView,
  toRecordOrNull,
  HumanResultView,
  formatPayloadItem,
  formatPayloadValue,
  AgentRunObservabilityPanel,
  DomainRequestItem,
  AgentObservabilityMetric,
  PreviewRunSummaryPanel,
  OpenClawPreviewActionPlanPanel,
  previewNextStepActionLabel,
  CompiledPreviewSimulationPanel,
  previewSimulationTone,
  PreviewSummaryList,
  PreviewRunFact,
  RunColumn,
  TimelineItem,
  BillingActionItem,
  compactValue,
  ArtifactSourceSummary,
  ApprovalPayloadSummary,
  ArtifactItem
} from './runs';


export const AgentBlueprintsView = ({ scope }) => {
  const {
    location, currentBusinessId, blueprints, selectedBlueprintId, setSelectedBlueprintId, blueprintDetails,
    agentDetailsById, activeRun, setActiveRun, loading, actionLoading, error,
    agentSearch, setAgentSearch, agentRegistryFilter, setAgentRegistryFilter, runAnimation, runStatusFilter,
    setRunStatusFilter, runSource, setRunSource, runCity, setRunCity, runCategory,
    setRunCategory, runLimit, setRunLimit, runParameters, setRunParameters, runParameterErrors,
    setRunParameterErrors, createWizardOpen, setCreateWizardOpen, createWizardStep, setCreateWizardStep, workspaceMode,
    setWorkspaceMode, availablePersonaAgents, agentPrompt, setAgentPrompt, setBuilderCategory, builderDataSources,
    setBuilderDataSources, builderExtractionRules, setBuilderExtractionRules, builderProcessingRules, setBuilderProcessingRules, builderOutputFormat,
    setBuilderOutputFormat, builderManualControl, setBuilderManualControl, builderExecutionMode, setBuilderExecutionMode, builderExecutionModeConfirmed,
    setBuilderExecutionModeConfirmed, cloneFromBlueprintId, setCloneFromBlueprintId, builderSourceName, setBuilderSourceName, builderSourceText,
    setBuilderSourceText, builderFileSource, setBuilderFileSource, builderInternalSource, setBuilderInternalSource, dialogBuilderInput,
    setDialogBuilderInput, dialogBuilderReply, setDialogBuilderReply, dialogBuilderSession, setDialogBuilderSession, selectedBuilderConnectionBindings,
    setSelectedBuilderConnectionBindings, selectedBuilderProviderRoutes, setSelectedBuilderProviderRoutes, acceptedBuilderCompilerPlan, setAcceptedBuilderCompilerPlan, acceptedBuilderProviderRoutes,
    setAcceptedBuilderProviderRoutes, agentReview, sourceCatalog, setupDataSources, setSetupDataSources, setupExtractionRules,
    setSetupExtractionRules, setupProcessingRules, setSetupProcessingRules, setupOutputFormat, setSetupOutputFormat, setupManualControl,
    setSetupManualControl, sourceName, setSourceName, sourceText, setSourceText, internalSource,
    setInternalSource, agentIntegrations, availableAgentIntegrations, agentIntegrationCatalog, agentExternalAuthOptions, agentBindingStatus,
    agentConnectionPlan, selectedConnectionBindingKey, setSelectedConnectionBindingKey, sheetSpreadsheetId, setSheetSpreadsheetId, sheetName,
    setSheetName, sheetAuthRef, setSheetAuthRef, sheetDailyCap, setSheetDailyCap, browserTargetUrls,
    setBrowserTargetUrls, browserDailyCap, setBrowserDailyCap, telegramBotMode, setTelegramBotMode, telegramDailyCap,
    setTelegramDailyCap, whatsappChannelMode, setWhatsappChannelMode, whatsappDailyCap, setWhatsappDailyCap, matonAuthRef,
    setMatonAuthRef, matonChannel, setMatonChannel, matonDailyCap, setMatonDailyCap, processRowValues,
    setProcessRowValues, processPreviewMessage, setProcessPreviewMessage, scheduleTime, setScheduleTime, scheduleTimezone,
    setScheduleTimezone, selectedExecutionMode, setSelectedExecutionMode, feedbackText, setFeedbackText, feedbackTrigger,
    setFeedbackTrigger, feedbackVersionNotice, legacyMigrationPlan, legacyMigrationNotice, recentCreatedAgentName, setRecentCreatedAgentName,
    recentPostCreateHandoff, setRecentPostCreateHandoff, showAdvancedAgentTools, deleteCandidate, setDeleteCandidate, decisionNotice,
    setDecisionNotice, googleAccessJustConnected, selectedBlueprint, pendingApproval, pendingApprovals, selectedPendingApproval,
    queuedButNotDispatched, selectedScenario, systemAgents, migrationStats, applyBuilderScenario, loadBlueprints,
    loadRun, startDialogBuilderSession, sendDialogBuilderReply, createAgentFromDialogSession, createAgentFromPrompt, startRun,
    executeRun, saveSchedule, saveExecutionMode, rebuildScenarioAndRun, rebuildScenario, activateVersion, deleteAgent,
    requestDeleteAgent, deleteSelectedAgent, decideApproval, saveAgentSetup, addTextSource, addInternalSource,
    addInternalSourceByKey, addFileSource, saveSheetIntegration, saveBrowserUseIntegration, saveTelegramIntegration, saveWhatsappIntegration,
    saveMatonIntegration, chooseProviderRoute, attachExistingAgentIntegration, saveCustomProcess, runCustomProcessPreview, applyLegacyMigration,
    sendRunFeedback, postCreateReadyForRun, showPostCreateConnectionDetails, todaySummary, employeeListDetailsById, filteredBlueprints,
    selectedEmployeeAction, selectedResultRun, resultNeedsScenarioRebuild, resultNeedsGoogleSheetsSetup, resultNeedsGoogleAccessReconnect, resultGoogleAccessReconnected,
    openGoogleSheetsSourceSetup, openGoogleAccessReconnect, openSelectedAgentClone, runEmployeePrimaryAction, applyFinanceRequests
  } = scope;
  const [archiveReasonCode, setArchiveReasonCode] = useState('no_longer_needed');
  const archiveReasonOptions = [
    { value: 'no_longer_needed', label: 'Задача больше не нужна' },
    { value: 'no_useful_result', label: 'Не получил полезного результата' },
    { value: 'created_by_mistake', label: 'Создан по ошибке' },
    { value: 'replaced_by_another_agent', label: 'Заменён другим агентом' },
  ];
  const openLatestRunResults = async () => {
    try {
      const latestRunId = await fetchLatestAgentRunId(selectedBlueprint?.id || '', selectedBlueprint?.last_run_id || '');
      if (latestRunId && activeRun?.id !== latestRunId) {
        await loadRun(latestRunId);
        return;
      }
    } catch (requestError) {
      console.error(requestError);
    }
    setWorkspaceMode('results');
  };
  return (
    <div className="space-y-5">
      <DashboardPageHeader
        eyebrow="LocalOS"
        title="Агенты"
        description="Задачи, которые LocalOS выполняет один раз, по кнопке или по расписанию."
        icon={Bot}
        actions={(
          <>
            <span className="inline-flex min-h-8 items-center rounded-full bg-slate-100 px-3 text-xs font-semibold text-slate-600 ring-1 ring-slate-200">Beta</span>
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

      <Dialog open={createWizardOpen} onOpenChange={(open) => {
        setCreateWizardOpen(open);
        if (!open && !actionLoading) {
          setDialogBuilderInput('');
          setDialogBuilderReply('');
          setDialogBuilderSession(null);
          setSelectedBuilderConnectionBindings({});
          setSelectedBuilderProviderRoutes({});
          setAcceptedBuilderCompilerPlan(false);
          setAcceptedBuilderProviderRoutes(false);
          setBuilderExecutionMode('manual');
          setBuilderExecutionModeConfirmed(false);
          setCloneFromBlueprintId('');
          setAgentPrompt('');
          setCreateWizardStep(0);
          setBuilderCategory('documents');
          setBuilderDataSources('файл документа, ручной контекст, профиль бизнеса');
          setBuilderExtractionRules('ключевые условия, сроки, суммы, ответственность, спорные места');
          setBuilderProcessingRules('не придумывать факты, ссылаться только на добавленные данные, отдельно показывать риски');
          setBuilderOutputFormat('краткий отчёт: summary, риски, что уточнить, черновик письма при необходимости');
          setBuilderManualControl('перед использованием результата и перед любым внешним действием');
          setBuilderSourceName('');
          setBuilderSourceText('');
          setBuilderFileSource(null);
          setBuilderInternalSource('business_profile');
        }
      }}>
        <DialogContent className="max-h-[88vh] max-w-5xl overflow-y-auto rounded-2xl">
          <DialogHeader>
            <DialogTitle>{cloneFromBlueprintId ? 'Создать копию агента' : 'Создать агента'}</DialogTitle>
            <DialogDescription>
              {cloneFromBlueprintId
                ? 'LocalOS создаст нового агента с теми же источниками и правилами. История запусков, результаты и решения не копируются.'
                : 'Опишите задачу обычным языком. LocalOS уточнит недостающие детали и покажет понятную проверку перед созданием.'}
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
            selectedConnectionBindings={selectedBuilderConnectionBindings}
            selectedProviderRoutes={selectedBuilderProviderRoutes}
            acceptedCompilerPlan={acceptedBuilderCompilerPlan}
            acceptedProviderRoutes={acceptedBuilderProviderRoutes}
            executionMode={builderExecutionMode}
            executionModeConfirmed={builderExecutionModeConfirmed}
            scheduleTime={scheduleTime}
            scheduleTimezone={scheduleTimezone}
            onExecutionModeChange={(mode) => {
              setBuilderExecutionMode(mode);
              setBuilderExecutionModeConfirmed(false);
            }}
            onExecutionModeConfirm={() => setBuilderExecutionModeConfirmed(true)}
            onScheduleTimeChange={setScheduleTime}
            onScheduleTimezoneChange={setScheduleTimezone}
            onAcceptCompilerPlan={() => setAcceptedBuilderCompilerPlan(true)}
            onAcceptProviderRoutes={() => setAcceptedBuilderProviderRoutes(true)}
            onSelectConnectionBinding={(bindingKey, integrationId) => {
              setSelectedBuilderConnectionBindings((current) => ({
                ...current,
                [bindingKey]: integrationId,
              }));
            }}
            onSelectProviderRoute={(bindingKey, routeProvider) => {
              setAcceptedBuilderProviderRoutes(false);
              setSelectedBuilderProviderRoutes((current) => ({
                ...current,
                [bindingKey]: routeProvider,
              }));
            }}
          />
          <details className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
            <summary className="cursor-pointer text-sm font-medium text-slate-700">
              Расширенная ручная настройка
            </summary>
            <div className="mt-4">
          <AgentExecutionModePanel
            mode={builderExecutionMode}
            confirmationRequired={!builderExecutionModeConfirmed}
            time={scheduleTime}
            timezone={scheduleTimezone}
            actionLoading={false}
            onModeChange={(mode) => {
              setBuilderExecutionMode(mode);
              setBuilderExecutionModeConfirmed(false);
            }}
            onTimeChange={setScheduleTime}
            onTimezoneChange={setScheduleTimezone}
            onSave={() => setBuilderExecutionModeConfirmed(true)}
          />
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
            canCreate={Boolean(currentBusinessId && agentPrompt.trim() && builderExecutionModeConfirmed)}
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

      <Dialog open={Boolean(deleteCandidate)} onOpenChange={(open) => {
        if (!open && !actionLoading) {
          setDeleteCandidate(null);
          setArchiveReasonCode('no_longer_needed');
        }
      }}>
        <DialogContent className="max-w-lg rounded-2xl">
          <DialogHeader>
            <DialogTitle>Архивировать агента?</DialogTitle>
            <DialogDescription>
              Агент “{deleteCandidate?.name || 'выбранный агент'}” перестанет запускаться и исчезнет из рабочего списка. Сценарий, история и результаты сохранятся для анализа.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div className="text-sm font-semibold text-slate-950">Почему архивируете?</div>
            <RadioGroup value={archiveReasonCode} onValueChange={setArchiveReasonCode} className="gap-2">
              {archiveReasonOptions.map((option) => (
                <Label
                  key={option.value}
                  htmlFor={`archive-reason-${option.value}`}
                  className="flex min-h-11 cursor-pointer items-center gap-3 rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium leading-5 text-slate-800 transition-colors hover:bg-slate-50"
                >
                  <RadioGroupItem id={`archive-reason-${option.value}`} value={option.value} />
                  {option.label}
                </Label>
              ))}
            </RadioGroup>
          </div>
          <div className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm leading-6 text-amber-950">
            {deleteCandidate?.last_business_result
              ? 'У агента есть сохранённый рабочий результат. LocalOS отметит это при архивировании.'
              : 'Сохранённый рабочий результат не найден. LocalOS отметит, что агент архивирован без результата или только после теста.'}
          </div>
          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <Button type="button" variant="outline" onClick={() => {
              setDeleteCandidate(null);
              setArchiveReasonCode('no_longer_needed');
            }} disabled={actionLoading}>
              Отмена
            </Button>
            <Button
              type="button"
              className="bg-red-600 text-white hover:bg-red-700"
              onClick={() => deleteAgent(deleteCandidate, archiveReasonCode)}
              disabled={actionLoading || !deleteCandidate}
            >
              {actionLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Archive className="mr-2 h-4 w-4" />}
              Архивировать
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {error ? (
        <div className="space-y-2">
          <DashboardActionPanel
            title="Ошибка"
            description={error}
            tone="amber"
          />
          {error.toLowerCase().includes('кредит') ? (
            <Button type="button" variant="outline" onClick={() => { window.location.href = '/dashboard/profile?focus=subscription#subscription'; }}>
              <ReceiptText className="mr-2 h-4 w-4" />
              Пополнить кредиты
            </Button>
          ) : null}
        </div>
      ) : null}

      {decisionNotice ? (
        <DashboardActionPanel
          title="Готово"
          description={decisionNotice}
          tone="sky"
        />
      ) : null}

      {false && recentCreatedAgentName ? (
        <div className="space-y-3">
          <DashboardActionPanel
            title={userFacingAgentTechText(recentPostCreateHandoff?.title || 'Агент создан')}
            description={userFacingAgentTechText(recentPostCreateHandoff?.description || `${recentCreatedAgentName} выбран ниже. Проверьте данные агента, активную версию и запустите его из карточки.`)}
            tone={recentPostCreateHandoff?.status === 'needs_connections' ? 'amber' : 'sky'}
            actions={(
              <div className="flex flex-wrap gap-2">
                {recentPostCreateHandoff?.workspace_mode === 'connections' ? (
                  <Button type="button" size="sm" onClick={() => setWorkspaceMode('connections')}>
                    Открыть подключения
                  </Button>
                ) : null}
                {postCreateReadyForRun ? (
                  <Button type="button" size="sm" onClick={() => (selectedBlueprint ? startRun(selectedBlueprint) : setWorkspaceMode('run'))}>
                    Запустить тест
                  </Button>
                ) : null}
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    setRecentCreatedAgentName('');
                    setRecentPostCreateHandoff(null);
                  }}
                >
                  Понятно
                </Button>
              </div>
            )}
	          />
	          {showPostCreateConnectionDetails && recentPostCreateHandoff?.next_binding ? (
	            <div className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-3 text-xs leading-5 text-amber-950">
	              <div className="font-semibold">
	                Следующий доступ: {recentPostCreateHandoff.next_binding.title || connectorLabel(recentPostCreateHandoff.next_binding.provider)}
	              </div>
	              <div className="mt-1">
	                {userFacingAgentTechText(recentPostCreateHandoff.next_binding.route_summary || recentPostCreateHandoff.next_binding.explanation || 'Откройте подключения и завершите настройку этого шага.')}
	              </div>
	              {recentPostCreateHandoff.next_route?.label || recentPostCreateHandoff.next_route?.primary_cta ? (
	                <div className="mt-2 rounded-lg bg-white/80 px-2 py-1.5 text-amber-900 ring-1 ring-amber-100">
	                  <ProviderActionPill
	                    route={recentPostCreateHandoff.next_route}
	                    disabled={actionLoading || !recentPostCreateHandoff.next_binding_key}
	                    onChoose={recentPostCreateHandoff.next_binding_key ? () => chooseProviderRoute(recentPostCreateHandoff.next_binding_key || '', recentPostCreateHandoff.next_route || {}) : undefined}
	                  />
	                  {providerActionDescription(recentPostCreateHandoff.next_route) ? (
	                    <div className="mt-1">{userFacingAgentTechText(providerActionDescription(recentPostCreateHandoff.next_route))}</div>
	                  ) : null}
	                </div>
	              ) : null}
	            </div>
	          ) : null}
	          {showPostCreateConnectionDetails ? (
	            <AgentConnectionPlanPanel
	              connectionPlan={recentPostCreateHandoff?.connection_plan || agentConnectionPlan}
              availableIntegrations={availableAgentIntegrations}
              actionLoading={actionLoading}
              onAttachExistingIntegration={attachExistingAgentIntegration}
              onConfigureBinding={setSelectedConnectionBindingKey}
              onChooseProviderRoute={chooseProviderRoute}
            />
	          ) : null}
        </div>
      ) : null}

      {!currentBusinessId ? (
        <DashboardEmptyState
          title="Сначала выберите бизнес"
          description="Агенты всегда привязаны к конкретному бизнесу и его правам доступа."
        />
      ) : null}

      {currentBusinessId ? (
        <div className="space-y-4">
          <section className="rounded-2xl bg-white px-4 py-3 shadow-[0_1px_2px_rgba(15,23,42,0.06),0_0_0_1px_rgba(15,23,42,0.08)]">
            <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-sm text-slate-600">
              <span className="font-semibold text-slate-950">Сегодня</span>
              <span><strong className="tabular-nums text-slate-950">{todaySummary.completedRuns}</strong> выполнено</span>
              <span><strong className="tabular-nums text-slate-950">{todaySummary.preparedArtifacts}</strong> результатов</span>
              <span><strong className="tabular-nums text-slate-950">{todaySummary.pendingApprovals}</strong> ждут решения</span>
              {todaySummary.failedRuns ? <span className="text-rose-700"><strong className="tabular-nums">{todaySummary.failedRuns}</strong> ошибок</span> : null}
            </div>
          </section>
          <section className="rounded-2xl bg-white p-3 shadow-[0_1px_2px_rgba(15,23,42,0.06),0_0_0_1px_rgba(15,23,42,0.08)]">
            <div className="grid gap-3 lg:grid-cols-[minmax(16rem,1fr)_auto] lg:items-center">
              <label className="relative block">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                <input
                  type="search"
                  value={agentSearch}
                  onChange={(event) => setAgentSearch(event.target.value)}
                  placeholder="Найти агента"
                  className="min-h-10 w-full rounded-lg bg-slate-50 pl-10 pr-3 text-sm text-slate-950 outline-none shadow-[inset_0_0_0_1px_rgba(15,23,42,0.08)] focus:shadow-[inset_0_0_0_2px_rgba(249,115,22,0.55)]"
                />
              </label>
              <div className="grid grid-cols-2 gap-1 rounded-xl bg-slate-100 p-1 sm:flex">
                {([
                  ['all', 'Все'],
                  ['working', 'Работают'],
                  ['attention', 'Нужны действия'],
                  ['completed', 'Выполненные'],
                ]).map(([value, label]) => (
                  <button
                    key={value}
                    type="button"
                    onClick={() => setAgentRegistryFilter(value === 'working' || value === 'attention' || value === 'completed' ? value : 'all')}
                    className={cn('min-h-9 rounded-lg px-3 text-xs font-semibold transition-[background-color,color,box-shadow] active:scale-[0.96]', agentRegistryFilter === value ? 'bg-white text-slate-950 shadow-sm' : 'text-slate-600 hover:text-slate-950')}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>
          </section>
          <div className="grid gap-5 lg:grid-cols-[28rem_minmax(0,1fr)]">
            <EmployeeAgentsList
              blueprints={filteredBlueprints}
              detailsById={employeeListDetailsById}
              selectedBlueprintId={selectedBlueprint?.id || null}
              selectedActiveRun={activeRun}
              selectedPendingApproval={selectedPendingApproval}
              loading={loading}
              onOpen={(blueprint) => {
                setSelectedBlueprintId(blueprint.id);
                setActiveRun(null);
                setDecisionNotice(null);
                setWorkspaceMode('overview');
                setRecentCreatedAgentName('');
                setRecentPostCreateHandoff(null);
              }}
            />

            <main className="min-w-0 space-y-4">
              {selectedBlueprint && selectedEmployeeAction && !runAnimation ? (
                <nav className="flex gap-1 overflow-x-auto rounded-xl bg-slate-100 p-1" aria-label="Разделы агента">
                  {([
                    ['overview', 'Обзор'],
                    ['results', 'История'],
                    ['scenario', 'Сценарий'],
                    ['settings', 'Настройки'],
                  ]).map(([value, label]) => (
                    <button
                      key={value}
                      type="button"
                      onClick={() => value === 'results'
                        ? void openLatestRunResults()
                        : setWorkspaceMode(value === 'scenario' || value === 'settings' ? value : 'overview')}
                      className={cn('min-h-10 shrink-0 rounded-lg px-4 text-sm font-semibold transition-[background-color,color,box-shadow] active:scale-[0.96]', workspaceMode === value || (value === 'overview' && workspaceMode === 'run') ? 'bg-white text-slate-950 shadow-sm' : 'text-slate-600 hover:text-slate-950')}
                    >
                      {label}
                    </button>
                  ))}
                </nav>
              ) : null}
              {selectedBlueprint && selectedEmployeeAction ? (
                runAnimation?.blueprintId === selectedBlueprint.id ? (
                  <AgentRunProgressPanel
                    animation={runAnimation}
                    onRetry={() => runAnimation.kind === 'work'
                      ? executeRun(selectedBlueprint, selectedEmployeeAction.versionId || '')
                      : startRun(selectedBlueprint)}
                  />
                ) : workspaceMode === 'overview' || workspaceMode === 'run' ? (
                  <div className="space-y-4">
                    <EmployeeAgentOverviewPanel
                      blueprint={selectedBlueprint}
                      details={blueprintDetails}
                      activeRun={activeRun}
                      pendingApproval={selectedPendingApproval}
                      action={selectedEmployeeAction}
                      actionLoading={actionLoading}
                      onPrimaryAction={['open_result', 'view_history', 'approve'].includes(selectedEmployeeAction.kind)
                        ? () => void openLatestRunResults()
                        : runEmployeePrimaryAction}
                      onCloneAgent={openSelectedAgentClone}
                      onOpenAdvanced={() => setWorkspaceMode('settings')}
                      onOpenResults={() => void openLatestRunResults()}
                    />
                    <AgentRunParametersPanel
                      schema={selectedEmployeeAction.kind === 'run_test'
                        ? blueprintDetails?.candidate_run_input_schema || blueprintDetails?.run_input_schema
                        : blueprintDetails?.active_run_input_schema || blueprintDetails?.candidate_run_input_schema || blueprintDetails?.run_input_schema}
                      values={runParameters}
                      errors={runParameterErrors}
                      onChange={(key, value) => {
                        setRunParameters((current) => ({ ...current, [key]: value }));
                        setRunParameterErrors((current) => {
                          if (!current[key]) {
                            return current;
                          }
                          const next = { ...current };
                          delete next[key];
                          return next;
                        });
                      }}
                    />
                    {selectedEmployeeAction.kind === 'configure_schedule' ? (
                      <AgentScheduleSetupPanel
                        time={scheduleTime}
                        timezone={scheduleTimezone}
                        actionLoading={actionLoading}
                        onTimeChange={setScheduleTime}
                        onTimezoneChange={setScheduleTimezone}
                        onSave={saveSchedule}
                      />
                    ) : null}
                    {selectedEmployeeAction.kind === 'confirm_mode' ? (
                      <AgentExecutionModePanel
                        mode={selectedExecutionMode}
                        confirmationRequired={Boolean(blueprintDetails?.execution_mode_confirmation_required || selectedBlueprint.execution_mode_confirmation_required)}
                        time={scheduleTime}
                        timezone={scheduleTimezone}
                        actionLoading={actionLoading}
                        onModeChange={setSelectedExecutionMode}
                        onTimeChange={setScheduleTime}
                        onTimezoneChange={setScheduleTimezone}
                        onSave={saveExecutionMode}
                      />
                    ) : null}
                  </div>
                ) : workspaceMode === 'scenario' ? (
                  <EmployeeAgentScenarioPanel
                    blueprint={selectedBlueprint}
                    details={blueprintDetails}
                    actionLoading={actionLoading}
                    onRebuildScenario={rebuildScenario}
                  />
                ) : workspaceMode === 'results' ? (
                  <div className="space-y-4">
                    <section className="rounded-2xl bg-white px-4 py-4 shadow-[0_1px_2px_rgba(15,23,42,0.06),0_0_0_1px_rgba(15,23,42,0.08)]">
                      <div className="flex items-center justify-between gap-3">
                        <div>
                          <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">История</div>
                          <h2 className="mt-1 text-lg font-semibold leading-7 text-slate-950">Запуски агента</h2>
                        </div>
                        <span className="text-xs font-medium tabular-nums text-slate-500">
                          {(blueprintDetails?.runs || []).length} всего
                        </span>
                      </div>
                      <div className="mt-3 divide-y divide-slate-100 overflow-hidden rounded-xl ring-1 ring-slate-200">
                        {(blueprintDetails?.runs || []).length ? (blueprintDetails?.runs || []).map((run) => {
                          const selected = selectedResultRun?.id === run.id;
                          const runDate = run.completed_at || run.started_at || run.queued_at || '';
                          return (
                            <button
                              key={run.id}
                              type="button"
                              aria-current={selected ? 'true' : undefined}
                              onClick={() => void loadRun(run.id)}
                              className={cn(
                                'flex min-h-12 w-full items-center justify-between gap-3 px-3 py-2 text-left transition-[background-color,color] active:scale-[0.99]',
                                selected ? 'bg-slate-950 text-white' : 'bg-white text-slate-800 hover:bg-slate-50',
                              )}
                            >
                              <span className="min-w-0">
                                <span className="block text-sm font-semibold">{isAgentWorkRun(run) ? 'Рабочий запуск' : 'Проверка'}</span>
                                <span className={cn('block truncate text-xs', selected ? 'text-slate-300' : 'text-slate-500')}>
                                  {runDate ? formatShortDate(runDate) : 'Дата не сохранена'}
                                </span>
                              </span>
                              <span className={cn('shrink-0 text-xs font-medium', selected ? 'text-slate-200' : 'text-slate-500')}>
                                {humanizeStatus(run.status)}
                              </span>
                            </button>
                          );
                        }) : (
                          <div className="px-3 py-4 text-sm text-slate-600">История появится после первого запуска.</div>
                        )}
                      </div>
                    </section>
                    {selectedResultRun || selectedPendingApproval ? (
                      <EmployeeTestResultPanel
                        activeRun={selectedResultRun}
                        pendingApproval={selectedPendingApproval}
                        actionLoading={actionLoading}
                        needsScenarioRebuild={resultNeedsScenarioRebuild}
                        needsGoogleSheetsSetup={resultNeedsGoogleSheetsSetup}
                        needsGoogleAccessReconnect={resultNeedsGoogleAccessReconnect}
                        googleAccessJustConnected={resultGoogleAccessReconnected}
                        estimatedRunCredits={estimatedAgentRunCredits(blueprintDetails, selectedEmployeeAction.kind === 'run_test')}
                        onApprove={() => decideApproval('approve')}
                        onReject={() => decideApproval('reject')}
                        onRunAgain={() => {
                          const workRun = isAgentWorkRun(selectedResultRun);
                          const schema = workRun
                            ? blueprintDetails?.active_run_input_schema || blueprintDetails?.run_input_schema
                            : blueprintDetails?.candidate_run_input_schema || blueprintDetails?.run_input_schema;
                          const parameters = initialRunParameters(schema, selectedResultRun?.input_json);
                          return workRun
                            ? executeRun(selectedBlueprint, selectedResultRun?.blueprint_version_id || '', parameters)
                            : startRun(selectedBlueprint, selectedResultRun?.blueprint_version_id || '', parameters);
                        }}
                        onRebuildScenario={rebuildScenarioAndRun}
                        onOpenGoogleSheetsSetup={openGoogleSheetsSourceSetup}
                        onOpenGoogleAccessReconnect={openGoogleAccessReconnect}
                      />
                    ) : (
                      <EmployeeHistoryPanel details={blueprintDetails} activeRun={activeRun} />
                    )}
                  </div>
                ) : workspaceMode === 'settings' ? (
                  <div className="space-y-4">
                    <AgentExecutionModePanel
                      mode={selectedExecutionMode}
                      confirmationRequired={Boolean(blueprintDetails?.execution_mode_confirmation_required || selectedBlueprint.execution_mode_confirmation_required)}
                      time={scheduleTime}
                      timezone={scheduleTimezone}
                      actionLoading={actionLoading}
                      onModeChange={setSelectedExecutionMode}
                      onTimeChange={setScheduleTime}
                      onTimezoneChange={setScheduleTimezone}
                      onSave={saveExecutionMode}
                    />
                    <AgentDetailPanel
                  mode={workspaceMode}
                  blueprint={selectedBlueprint}
                  blueprintDetails={blueprintDetails}
                  activeRun={activeRun}
                  availablePersonaAgents={availablePersonaAgents}
                  pendingApproval={selectedPendingApproval}
                  queuedButNotDispatched={queuedButNotDispatched}
                  agentReview={agentReview}
                  feedbackText={feedbackText}
                  feedbackTrigger={feedbackTrigger}
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
                  agentIntegrations={agentIntegrations}
                  availableAgentIntegrations={availableAgentIntegrations}
                  agentIntegrationCatalog={agentIntegrationCatalog}
                  agentExternalAuthOptions={agentExternalAuthOptions}
                  agentBindingStatus={agentBindingStatus}
                  agentConnectionPlan={agentConnectionPlan}
                  postCreateHandoff={recentPostCreateHandoff}
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
                  onDeleteAgent={deleteSelectedAgent}
                  onFeedbackTextChange={setFeedbackText}
                  onFeedbackTriggerChange={setFeedbackTrigger}
                  onSubmitFeedback={sendRunFeedback}
                  onActivateFeedbackVersion={(versionId) => activateVersion(versionId, 'activate')}
                  onRollbackFeedbackVersion={(versionId) => activateVersion(versionId, 'rollback')}
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
                  onSheetSpreadsheetIdChange={setSheetSpreadsheetId}
                  onSheetNameChange={setSheetName}
                  onSheetAuthRefChange={setSheetAuthRef}
                  onSheetDailyCapChange={setSheetDailyCap}
                  onBrowserTargetUrlsChange={setBrowserTargetUrls}
                  onBrowserDailyCapChange={setBrowserDailyCap}
                  onTelegramBotModeChange={setTelegramBotMode}
                  onTelegramDailyCapChange={setTelegramDailyCap}
                  onWhatsappChannelModeChange={setWhatsappChannelMode}
                  onWhatsappDailyCapChange={setWhatsappDailyCap}
                  onMatonAuthRefChange={setMatonAuthRef}
                  onMatonChannelChange={setMatonChannel}
                  onMatonDailyCapChange={setMatonDailyCap}
                  onProcessRowValuesChange={setProcessRowValues}
                  onProcessPreviewMessageChange={setProcessPreviewMessage}
                  onSaveSheetIntegration={saveSheetIntegration}
                  onSaveBrowserUseIntegration={saveBrowserUseIntegration}
                  onSaveTelegramIntegration={saveTelegramIntegration}
                  onSaveWhatsappIntegration={saveWhatsappIntegration}
                  onSaveMatonIntegration={saveMatonIntegration}
                  onChooseProviderRoute={chooseProviderRoute}
                  onAttachExistingIntegration={attachExistingAgentIntegration}
                  onSelectConnectionBinding={setSelectedConnectionBindingKey}
                  onSaveCustomProcess={saveCustomProcess}
                  onRunCustomProcessPreview={runCustomProcessPreview}
                  onRunSourceChange={setRunSource}
                  onRunCityChange={setRunCity}
                  onRunCategoryChange={setRunCategory}
                  onRunLimitChange={setRunLimit}
                  onApplyFinanceRequests={applyFinanceRequests}
                  showAdvancedTools={showAdvancedAgentTools}
                />
                  </div>
                ) : (
                  <AgentDetailPanel
                  mode={workspaceMode}
                  blueprint={selectedBlueprint}
                  blueprintDetails={blueprintDetails}
                  activeRun={activeRun}
                  availablePersonaAgents={availablePersonaAgents}
                  pendingApproval={selectedPendingApproval}
                  queuedButNotDispatched={queuedButNotDispatched}
                  agentReview={agentReview}
                  feedbackText={feedbackText}
                  feedbackTrigger={feedbackTrigger}
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
                  agentIntegrations={agentIntegrations}
                  availableAgentIntegrations={availableAgentIntegrations}
                  agentIntegrationCatalog={agentIntegrationCatalog}
                  agentExternalAuthOptions={agentExternalAuthOptions}
                  agentBindingStatus={agentBindingStatus}
                  agentConnectionPlan={agentConnectionPlan}
                  postCreateHandoff={recentPostCreateHandoff}
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
                  onDeleteAgent={deleteSelectedAgent}
                  onFeedbackTextChange={setFeedbackText}
                  onFeedbackTriggerChange={setFeedbackTrigger}
                  onSubmitFeedback={sendRunFeedback}
                  onActivateFeedbackVersion={(versionId) => activateVersion(versionId, 'activate')}
                  onRollbackFeedbackVersion={(versionId) => activateVersion(versionId, 'rollback')}
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
                  onSheetSpreadsheetIdChange={setSheetSpreadsheetId}
                  onSheetNameChange={setSheetName}
                  onSheetAuthRefChange={setSheetAuthRef}
                  onSheetDailyCapChange={setSheetDailyCap}
                  onBrowserTargetUrlsChange={setBrowserTargetUrls}
                  onBrowserDailyCapChange={setBrowserDailyCap}
                  onTelegramBotModeChange={setTelegramBotMode}
                  onTelegramDailyCapChange={setTelegramDailyCap}
                  onWhatsappChannelModeChange={setWhatsappChannelMode}
                  onWhatsappDailyCapChange={setWhatsappDailyCap}
                  onMatonAuthRefChange={setMatonAuthRef}
                  onMatonChannelChange={setMatonChannel}
                  onMatonDailyCapChange={setMatonDailyCap}
                  onProcessRowValuesChange={setProcessRowValues}
                  onProcessPreviewMessageChange={setProcessPreviewMessage}
                  onSaveSheetIntegration={saveSheetIntegration}
                  onSaveBrowserUseIntegration={saveBrowserUseIntegration}
                  onSaveTelegramIntegration={saveTelegramIntegration}
                  onSaveWhatsappIntegration={saveWhatsappIntegration}
                  onSaveMatonIntegration={saveMatonIntegration}
                  onChooseProviderRoute={chooseProviderRoute}
                  onAttachExistingIntegration={attachExistingAgentIntegration}
                  onSelectConnectionBinding={setSelectedConnectionBindingKey}
                  onSaveCustomProcess={saveCustomProcess}
                  onRunCustomProcessPreview={runCustomProcessPreview}
                  onRunSourceChange={setRunSource}
                  onRunCityChange={setRunCity}
                  onRunCategoryChange={setRunCategory}
                  onRunLimitChange={setRunLimit}
                  onApplyFinanceRequests={applyFinanceRequests}
                  showAdvancedTools={showAdvancedAgentTools}
                />
                )
              ) : (
                <DashboardEmptyState
                  title="Создайте первого сотрудника"
                  description="После создания LocalOS сразу откроет карточку и покажет один следующий шаг."
                />
              )}
            </main>
          </div>
        </div>
      ) : null}

      {false && currentBusinessId ? (
        <div className="space-y-5">
          <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="text-sm font-semibold text-slate-950">Агенты</div>
                <div className="mt-1 text-xs leading-5 text-slate-500">
                  Выберите работу, которую LocalOS должен вести для бизнеса.
                </div>
              </div>
              <span className="rounded-full bg-slate-50 px-2.5 py-1 text-xs font-medium text-slate-600 ring-1 ring-slate-200">
                {blueprints.length} всего
              </span>
            </div>
            <div className="mt-4 grid max-h-[28rem] gap-3 overflow-y-auto pr-1 lg:grid-cols-2 2xl:grid-cols-3">
              {loading ? (
                <div className="flex items-center gap-2 rounded-xl bg-slate-50 px-3 py-4 text-sm text-slate-500">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Загружаем агентов...
                </div>
              ) : blueprints.length === 0 ? (
                <DashboardEmptyState
                  title="Агентов пока нет"
                  description="Создайте первого агента через мастер. Голос и стиль подключаются позже."
                />
              ) : (
                blueprints.map((blueprint) => {
                  const selected = selectedBlueprint?.id === blueprint.id;
                  return (
                    <BlueprintAgentCard
                      key={blueprint.id}
                      blueprint={blueprint}
                      latestVersionNumber={getActiveVersionNumber(blueprint, selected ? blueprintDetails : null)}
                      selected={selected}
                      businessStatus={buildAgentBusinessStatus(blueprint, selected ? blueprintDetails : agentDetailsById[blueprint.id])}
                      onSelect={() => {
                        setSelectedBlueprintId(blueprint.id);
                        setActiveRun(null);
                        setWorkspaceMode('overview');
                      }}
                      onConfigure={() => {
                        setSelectedBlueprintId(blueprint.id);
                        setActiveRun(null);
                        setWorkspaceMode('settings');
                      }}
                      onRun={() => {
                        setSelectedBlueprintId(blueprint.id);
                        setWorkspaceMode('results');
                        void startRun(blueprint);
                      }}
                      onResults={() => {
                        setSelectedBlueprintId(blueprint.id);
                        setWorkspaceMode('results');
                      }}
                      onVoice={() => {
                        setSelectedBlueprintId(blueprint.id);
                        setActiveRun(null);
                        setWorkspaceMode('voice');
                      }}
                      onDelete={() => requestDeleteAgent(blueprint)}
                      actionLoading={actionLoading}
                    />
                  );
                })
              )}
            </div>
          </section>

          <div className="min-w-0">
            {selectedBlueprint ? (
              <AgentDetailPanel
                mode={workspaceMode}
                blueprint={selectedBlueprint}
                blueprintDetails={blueprintDetails}
                activeRun={activeRun}
                availablePersonaAgents={availablePersonaAgents}
                pendingApproval={selectedPendingApproval}
                queuedButNotDispatched={queuedButNotDispatched}
                agentReview={agentReview}
                feedbackText={feedbackText}
                feedbackTrigger={feedbackTrigger}
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
                agentIntegrations={agentIntegrations}
                availableAgentIntegrations={availableAgentIntegrations}
                agentIntegrationCatalog={agentIntegrationCatalog}
                agentExternalAuthOptions={agentExternalAuthOptions}
                agentBindingStatus={agentBindingStatus}
                agentConnectionPlan={agentConnectionPlan}
                postCreateHandoff={recentPostCreateHandoff}
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
                onDeleteAgent={deleteSelectedAgent}
                onFeedbackTextChange={setFeedbackText}
                onFeedbackTriggerChange={setFeedbackTrigger}
                onSubmitFeedback={sendRunFeedback}
                onActivateFeedbackVersion={(versionId) => activateVersion(versionId, 'activate')}
                onRollbackFeedbackVersion={(versionId) => activateVersion(versionId, 'rollback')}
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
                onSheetSpreadsheetIdChange={setSheetSpreadsheetId}
                onSheetNameChange={setSheetName}
                onSheetAuthRefChange={setSheetAuthRef}
                onSheetDailyCapChange={setSheetDailyCap}
                onBrowserTargetUrlsChange={setBrowserTargetUrls}
                onBrowserDailyCapChange={setBrowserDailyCap}
                onTelegramBotModeChange={setTelegramBotMode}
                onTelegramDailyCapChange={setTelegramDailyCap}
                onWhatsappChannelModeChange={setWhatsappChannelMode}
                onWhatsappDailyCapChange={setWhatsappDailyCap}
                onMatonAuthRefChange={setMatonAuthRef}
                onMatonChannelChange={setMatonChannel}
                onMatonDailyCapChange={setMatonDailyCap}
                onProcessRowValuesChange={setProcessRowValues}
                onProcessPreviewMessageChange={setProcessPreviewMessage}
                onSaveSheetIntegration={saveSheetIntegration}
                onSaveBrowserUseIntegration={saveBrowserUseIntegration}
                onSaveTelegramIntegration={saveTelegramIntegration}
                onSaveWhatsappIntegration={saveWhatsappIntegration}
                onSaveMatonIntegration={saveMatonIntegration}
                onChooseProviderRoute={chooseProviderRoute}
                onAttachExistingIntegration={attachExistingAgentIntegration}
                onSelectConnectionBinding={setSelectedConnectionBindingKey}
                onSaveCustomProcess={saveCustomProcess}
                onRunCustomProcessPreview={runCustomProcessPreview}
                onRunSourceChange={setRunSource}
                onRunCityChange={setRunCity}
                onRunCategoryChange={setRunCategory}
                onRunLimitChange={setRunLimit}
                onApplyFinanceRequests={applyFinanceRequests}
                showAdvancedTools={showAdvancedAgentTools}
              />
            ) : (
              <DashboardEmptyState
                title="Выберите агента"
                description="Откройте существующего агента или создайте нового через кнопку сверху."
              />
            )}
          </div>
        </div>
      ) : null}

      {currentBusinessId && showAdvancedAgentTools ? (
        <details className="min-w-0 overflow-hidden rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
          <summary className="cursor-pointer text-sm font-semibold text-slate-800">
            Служебные инструменты миграции и поддержки
          </summary>
          <div className="mt-4 min-w-0 space-y-5">
            <AgentCockpitPanel
              blueprints={blueprints}
              systemAgents={systemAgents}
              migrationPlan={legacyMigrationPlan}
              migrationStats={migrationStats}
              migrationNotice={legacyMigrationNotice}
              actionLoading={actionLoading}
              onApplyMigration={applyLegacyMigration}
              onOpenLegacySettings={() => setWorkspaceMode('voice')}
            />

            {availablePersonaAgents.length ? (
              <DashboardActionPanel
                title="Голоса и стиль перенесены внутрь агента"
                description={`${availablePersonaAgents.length} старых голосов доступны во вкладке “Голос и стиль” выбранного агента. Отдельный редактор старой логики больше не используется как основной вход.`}
                tone="sky"
              />
            ) : null}

            {selectedBlueprint ? (
              <div className="grid gap-5 xl:grid-cols-2">
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
                    <div className="grid gap-3">
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

                <DashboardSection
                  title="Ждут решения"
                  description="Решения, без которых агент не продолжит рискованное действие."
                >
                  {pendingApprovals.length ? (
                    <div className="grid gap-3">
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
                          <div className="mt-2 rounded-lg bg-white/70 px-2 py-2 text-xs leading-5 text-amber-900 ring-1 ring-amber-100">
                            {explainApproval(approval)}
                          </div>
                          <ApprovalPayloadSummary approval={approval} />
                        </button>
                      ))}
                    </div>
                  ) : (
                    <DashboardEmptyState
                      title="Очередь решений пуста"
                      description="Когда агент остановится на ручном подтверждении, решение появится здесь."
                    />
                  )}
                </DashboardSection>
              </div>
            ) : null}
          </div>
        </details>
      ) : null}
    </div>
  );
};
