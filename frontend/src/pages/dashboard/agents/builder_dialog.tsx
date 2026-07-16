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
  BuilderRequiredConnectionsPanel,
  builderPreviewDataText,
  BuilderCompilerPolicyReviewPanel,
  BuilderServiceIntelligencePanel,
  BuilderConnectionReadinessPanel,
  BuilderConnectionResolverPanel,
  BuilderSetupFlowPanel,
  BuilderConnectionSummaryPanel
} from './builder_setup';
import {
  ConnectorIntelligencePanel,
  BuilderPlannerLoopPanel,
  BuilderExecutionBoundaryPanel,
  PreviewRow,
  BuilderFeasibilityPanel,
  agentExecutionModeOptions
} from './employee';
import {
  AgentConnectionPlanPanel
} from './connections';
import {
  WizardTextArea
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

export const CreateAgentWizard = ({
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
          <div className="space-y-3">
            <WizardTextArea label="Какие данные использовать" value={dataSources} onChange={onDataSourcesChange} placeholder="Файл, текст, профиль бизнеса, услуги, отзывы" />
            <div className="rounded-xl border border-slate-200 bg-white px-3 py-3 text-sm leading-6 text-slate-600">
              <div className="font-medium text-slate-950">Что уже будет подключено</div>
              <div className="mt-1">
                {[
                  sourceText.trim() ? `текст “${sourceName.trim() || 'Контекст для агента'}”` : '',
                  fileSource ? `файл ${fileSource.name}` : '',
                  internalSource !== 'none' ? humanizeMeta(internalSource) : '',
                ].filter(Boolean).join(', ') || 'пока ничего; добавьте текст, файл или источник LocalOS'}
              </div>
              <div className="mt-2 text-xs text-slate-500">
                PDF, DOCX и XLSX читаются на backend. Если текст извлечь не получится, агент покажет понятную ошибку и не запустит внешнее действие.
              </div>
            </div>
          </div>
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
            Первые версии агентов готовят результат и ждут проверки. Внешние отправки, публикации, платежи и опасные изменения не запускаются из мастера.
          </div>
        </div>
      ) : null}

      {step === 3 ? (
        <div className="grid gap-4 lg:grid-cols-[1fr_20rem]">
          <WizardTextArea label="Какой результат подготовить" value={outputFormat} onChange={onOutputFormatChange} placeholder="Отчёт, письмо, таблица, shortlist, черновики" />
          <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4 text-sm leading-6 text-slate-700">
            <div className="font-semibold text-slate-950">{selectedScenario.title}</div>
            <div className="mt-2">{prompt || selectedScenario.prompt}</div>
            <div className="mt-4 space-y-2">
              <PreviewRow label="Данные" value={dataSources || 'уточнить'} />
              <PreviewRow label="Что понял" value={extractionRules || 'уточнить'} />
              <PreviewRow label="Правила" value={processingRules || 'уточнить'} />
              <PreviewRow label="Ручной контроль" value={manualControl || 'перед внешним действием'} />
            </div>
            <div className="mt-3 text-xs text-slate-500">
              После создания LocalOS сразу откроет карточку агента. Там будут данные, активная версия, запуск и журнал результатов.
            </div>
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

export const BuilderProductSteps = ({
  hasPreview,
  readyForDraft,
  created,
}: {
  hasPreview: boolean;
  readyForDraft: boolean;
  created: boolean;
}) => {
  const steps = [
    { key: 'describe', label: 'Описание задачи', done: hasPreview || readyForDraft || created },
    { key: 'prepared', label: 'Что подготовил LocalOS', done: hasPreview || readyForDraft || created },
    { key: 'check', label: 'Проверка', done: readyForDraft || created },
    { key: 'publish', label: 'Включение', done: created },
  ];
  return (
    <div className="grid gap-2 md:grid-cols-4">
      {steps.map((step, index) => (
        <div
          key={step.key}
          className={cn(
            'rounded-xl px-3 py-2 text-sm ring-1',
            step.done ? 'bg-emerald-50 text-emerald-950 ring-emerald-100' : index === 0 ? 'bg-sky-50 text-sky-950 ring-sky-100' : 'bg-slate-50 text-slate-600 ring-slate-100',
          )}
        >
          <div className="flex items-center gap-2 font-semibold">
            <span className={cn(
              'flex h-5 w-5 items-center justify-center rounded-full text-[11px]',
              step.done ? 'bg-emerald-100 text-emerald-700' : 'bg-white text-slate-500 ring-1 ring-slate-200',
            )}>
              {step.done ? <CheckCircle2 className="h-3.5 w-3.5" /> : index + 1}
            </span>
            {step.label}
          </div>
        </div>
      ))}
    </div>
  );
};

export const BuilderTrustBlock = ({ ready }: { ready: boolean }) => (
  <div className={cn(
    'mt-4 rounded-xl px-3 py-3 text-sm leading-6 ring-1',
    ready ? 'bg-emerald-50 text-emerald-950 ring-emerald-100' : 'bg-slate-50 text-slate-700 ring-slate-100',
  )}>
    <div className="flex items-center gap-2 font-semibold text-slate-950">
      <ShieldCheck className="h-4 w-4 text-emerald-700" />
      Почему этому можно доверять
    </div>
    <div className="mt-2 grid gap-2 md:grid-cols-2">
      {[
        'Используются только разрешённые действия',
        'Подключения будут проверены перед запуском',
        'Перед внешним действием требуется подтверждение',
        'Агент будет использовать именно опубликованный сценарий',
        'Агент не изменит сценарий самостоятельно',
      ].map((item) => (
        <div key={item} className="flex items-start gap-2 rounded-lg bg-white/80 px-2.5 py-2 ring-1 ring-current/10">
          <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
          <span>{item}</span>
        </div>
      ))}
    </div>
  </div>
);

export const DialogAgentBuilder = ({
  input,
  reply,
  session,
  actionLoading,
  onInputChange,
  onReplyChange,
  onStart,
  onSendReply,
  onCreate,
  selectedConnectionBindings,
  selectedProviderRoutes,
  acceptedCompilerPlan,
  acceptedProviderRoutes,
  executionMode,
  executionModeConfirmed,
  scheduleTime,
  scheduleTimezone,
  onAcceptCompilerPlan,
  onAcceptProviderRoutes,
  onExecutionModeChange,
  onExecutionModeConfirm,
  onScheduleTimeChange,
  onScheduleTimezoneChange,
  onSelectConnectionBinding,
  onSelectProviderRoute,
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
  selectedConnectionBindings: Record<string, string>;
  selectedProviderRoutes: Record<string, string>;
  acceptedCompilerPlan: boolean;
  acceptedProviderRoutes: boolean;
  executionMode: AgentExecutionMode;
  executionModeConfirmed: boolean;
  scheduleTime: string;
  scheduleTimezone: string;
  onAcceptCompilerPlan: () => void;
  onAcceptProviderRoutes: () => void;
  onExecutionModeChange: (mode: AgentExecutionMode) => void;
  onExecutionModeConfirm: () => void;
  onScheduleTimeChange: (value: string) => void;
  onScheduleTimezoneChange: (value: string) => void;
  onSelectConnectionBinding: (bindingKey: string, integrationId: string) => void;
  onSelectProviderRoute: (bindingKey: string, routeProvider: string) => void;
}) => {
  const preview = session?.preview || null;
  const nextStepRef = useRef<HTMLDivElement | null>(null);
  const previousMessageCountRef = useRef(0);
  const questions = session?.missing_questions || [];
  const messages = session?.messages || [];
  const estimatedCredits = Number(preview?.cost_preview?.estimated_credits || 0);
  const connectionSummaryItems = preview?.connection_summary?.items || [];
  const requiredConnectionChoices = connectionSummaryItems.filter((item) => item.action === 'choose_existing' && item.key && (item.connections?.length || 0) > 1);
  const missingConnectionChoices = requiredConnectionChoices.filter((item) => !selectedConnectionBindings[item.key || '']);
  const requiredProviderRouteKeys = builderRequiredProviderRouteKeys(preview);
  const missingProviderRouteKeys = requiredProviderRouteKeys.filter((key) => !selectedProviderRoutes[key]);
  const providerRoutesRequireConfirmation = requiredProviderRouteKeys.length > 0;
  const missingProviderRouteConfirmation = providerRoutesRequireConfirmation && (!acceptedProviderRoutes || missingProviderRouteKeys.length > 0);
  const blockingQuestions = builderBlockingQuestions(questions);
  const currentInputFingerprint = input.trim().toLowerCase().slice(0, 60);
  const previewUnderstoodTask = String(preview?.understood_task || '').trim().toLowerCase();
  const previewIsStale = Boolean(
    session
    && currentInputFingerprint
    && previewUnderstoodTask
    && !previewUnderstoodTask.includes(currentInputFingerprint),
  );
  const showInlineConnectionSetup = Boolean(missingConnectionChoices.length || missingProviderRouteKeys.length || missingProviderRouteConfirmation);
  const setupFlowNextStep = String(preview?.setup_flow?.next_step || '');
  const setupFlowAllowsDraft = preview?.setup_flow?.can_create_draft !== false || setupFlowNextStep.startsWith('create_draft_then');
  const canCreateDraft = setupFlowAllowsDraft
    && !previewIsStale
    && executionModeConfirmed
    && (executionMode !== 'scheduled' || Boolean(scheduleTime && scheduleTimezone));
  const createBlockers: Array<{ key: string; label: string }> = [];
  const addCreateBlocker = (key: string, label: string) => {
    const cleanKey = key.trim();
    const cleanLabel = label.trim();
    if (!cleanKey || !cleanLabel || createBlockers.some((item) => item.key === cleanKey || item.label === cleanLabel)) {
      return;
    }
    createBlockers.push({ key: cleanKey, label: cleanLabel });
  };
  blockingQuestions.slice(0, 4).forEach((question) => {
    addCreateBlocker(`question:${question.key || question.question}`, question.question || 'Ответьте на уточнение.');
  });
  missingConnectionChoices.slice(0, 4).forEach((item) => {
    addCreateBlocker(`choice:${item.key || item.provider}`, `Выберите подключение ${item.title || connectorLabel(item.provider)}.`);
  });
  if (missingProviderRouteKeys.length) {
    addCreateBlocker('provider_route_selection', `Выберите способ доставки для: ${missingProviderRouteKeys.map((item) => userFacingAgentTechText(humanizeMeta(item))).join(', ')}.`);
  } else if (missingProviderRouteConfirmation) {
    addCreateBlocker('provider_route_confirmation', 'Подтвердите выбранные способы подключения.');
  }
  preview?.setup_flow?.activation_blockers?.slice(0, 4).forEach((item) => {
    addCreateBlocker(`blocker:${item.type || item.provider || item.message}`, item.message || connectorLabel(item.provider));
  });
  preview?.connection_summary?.forbidden?.slice(0, 2).forEach((item) => {
    addCreateBlocker(`forbidden:${item.term || item.reason}`, item.reason || 'Запрос запрещён правилами безопасности LocalOS.');
  });
  preview?.connection_summary?.unsupported?.slice(0, 2).forEach((item) => {
    addCreateBlocker(`unsupported:${item.capability || item.reason}`, item.reason || 'Нет разрешённого способа подключения.');
  });
  const createDraftLabel = preview?.setup_flow?.post_create_status === 'ready_for_preview'
    ? 'Создать агента и открыть тест'
    : missingConnectionChoices.length
      ? 'Сначала выберите подключение'
      : missingProviderRouteKeys.length
        ? 'Сначала выберите способ'
        : missingProviderRouteConfirmation
          ? 'Подтвердите способы'
          : preview?.setup_flow?.post_create_status === 'needs_connection' || preview?.setup_flow?.post_create_status === 'needs_connection_choice'
      ? 'Создать агента и подключить сервисы'
      : 'Создать агента';
  const builderDecision = buildBuilderCreationDecision({
    preview,
    questions,
    missingConnectionChoices,
    missingProviderRouteKeys,
    missingProviderRouteConfirmation,
    canCreateDraft,
    createDraftLabel,
    previewIsStale,
  });
  const firstQuestion = blockingQuestions[0] || null;
  const extraQuestions = blockingQuestions.slice(1);
  const previewTaskText = preview?.understood_task || input;
  const previewDataText = builderPreviewDataText(preview, previewTaskText);
  const previewResultText = userFacingAgentTechText(preview?.output_format || 'результат уточним после подключения данных');
  const previewControlText = userFacingAgentTechText(preview?.manual_control || 'перед внешним действием');
  const setupBlockerText = userFacingAgentTechText(previewIsStale
    ? builderDecision.description
    : firstQuestion?.question
      || missingConnectionChoices[0]?.title
      || preview?.setup_flow?.next_step_description
      || builderDecision.description);
  const canUsePrimaryAction = builderDecision.action === 'answer'
    ? Boolean(reply.trim())
    : builderDecision.action === 'create' || setupFlowAllowsDraft
      ? canCreateDraft
      : false;
  const primaryActionLabel = builderDecision.action === 'answer'
    ? 'Ответить'
    : canCreateDraft || setupFlowAllowsDraft
      ? createDraftLabel
      : builderDecision.cta || 'Продолжить настройку';
  useEffect(() => {
    const messageCount = messages.length;
    if (!session || messageCount === previousMessageCountRef.current) {
      return;
    }
    previousMessageCountRef.current = messageCount;
    window.setTimeout(() => {
      nextStepRef.current?.scrollIntoView({ block: 'start', behavior: 'smooth' });
    }, 50);
  }, [messages.length, session]);
  return (
    <div className="space-y-4 rounded-2xl border border-slate-200 bg-white p-4">
      <BuilderProductSteps
        hasPreview={Boolean(preview)}
        readyForDraft={canCreateDraft}
        created={false}
      />
      <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto]">
        <textarea
          className="min-h-28 resize-none rounded-xl border border-slate-200 px-3 py-2 text-sm leading-6 outline-none transition focus:border-slate-400"
          value={input}
          onChange={(event) => onInputChange(event.target.value)}
          placeholder="Например: мне нужен агент, который проверяет договоры, находит риски и готовит краткий отчёт"
        />
        <Button type="button" onClick={onStart} disabled={actionLoading || !input.trim()}>
          {actionLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Sparkles className="mr-2 h-4 w-4" />}
          {session ? 'Обновить понимание' : 'Начать диалог'}
        </Button>
      </div>

      {session ? (
        <div className="space-y-4">
          <section className="rounded-2xl bg-white p-4 shadow-[0_0_0_1px_rgba(15,23,42,0.10)]">
            <div className="text-sm font-semibold text-slate-950">Как запускать агента</div>
            <div className="mt-1 text-xs leading-5 text-slate-500">LocalOS предложил вариант. Подтвердите его или выберите другой.</div>
            <div className="mt-3 grid gap-2 sm:grid-cols-3">
              {agentExecutionModeOptions.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => onExecutionModeChange(option.value)}
                  className={cn('min-h-20 rounded-xl px-3 py-2 text-left shadow-[0_0_0_1px_rgba(15,23,42,0.10)] transition-[background-color,color,box-shadow] active:scale-[0.96]', executionMode === option.value ? 'bg-slate-950 text-white' : 'bg-slate-50 text-slate-950')}
                >
                  <span className="block text-sm font-semibold">{agentExecutionModeLabel(option.value)}</span>
                  <span className={cn('mt-1 block text-xs leading-5', executionMode === option.value ? 'text-slate-300' : 'text-slate-500')}>{option.description}</span>
                </button>
              ))}
            </div>
            {executionMode === 'scheduled' ? (
              <div className="mt-3 grid gap-2 sm:grid-cols-2">
                <input type="time" value={scheduleTime} onChange={(event) => onScheduleTimeChange(event.target.value)} className="min-h-10 rounded-lg px-3 shadow-[inset_0_0_0_1px_rgba(15,23,42,0.14)] outline-none" aria-label="Время запуска" />
                <select value={scheduleTimezone} onChange={(event) => onScheduleTimezoneChange(event.target.value)} className="min-h-10 rounded-lg px-3 shadow-[inset_0_0_0_1px_rgba(15,23,42,0.14)] outline-none" aria-label="Часовой пояс">
                  <option value="Europe/Tallinn">Tallinn</option>
                  <option value="Europe/Moscow">Москва</option>
                  <option value="Europe/Helsinki">Helsinki</option>
                  <option value="Europe/Riga">Riga</option>
                </select>
              </div>
            ) : null}
            <Button type="button" size="sm" variant={executionModeConfirmed ? 'outline' : 'default'} className="mt-3 active:scale-[0.96] transition-transform" onClick={onExecutionModeConfirm} disabled={executionMode === 'scheduled' && (!scheduleTime || !scheduleTimezone)}>
              <CheckCircle2 className="mr-2 h-4 w-4" />
              {executionModeConfirmed ? 'Тип подтверждён' : 'Подтвердить тип'}
            </Button>
          </section>
          <div className={cn(
            'rounded-2xl border px-4 py-4',
            canCreateDraft ? 'border-emerald-200 bg-emerald-50' : 'border-amber-200 bg-amber-50',
          )} ref={nextStepRef}>
            <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
              <div className="min-w-0">
                <div className={cn('text-xs font-semibold uppercase', canCreateDraft ? 'text-emerald-700' : 'text-amber-700')}>
                  Сейчас нужно
                </div>
                <div className={cn('mt-1 text-lg font-semibold leading-7', canCreateDraft ? 'text-emerald-950' : 'text-amber-950')}>
                  {canCreateDraft ? 'Создать черновик агента' : builderDecision.title}
                </div>
                <div className={cn('mt-2 max-w-4xl text-sm leading-6', canCreateDraft ? 'text-emerald-900' : 'text-amber-950')}>
                  {canCreateDraft ? 'LocalOS понял задачу и готов сохранить первую версию. Подключения и тест будут следующим шагом.' : setupBlockerText}
                </div>
                {extraQuestions.length ? (
                  <details className="mt-2 text-xs leading-5 text-amber-900">
                    <summary className="cursor-pointer font-medium">Ещё {extraQuestions.length} уточнения</summary>
                    <div className="mt-1 space-y-1">
                      {extraQuestions.map((question) => (
	                        <div key={question.key || question.question}>{userFacingAgentTechText(question.question)}</div>
                      ))}
                    </div>
                  </details>
                ) : null}
              </div>
              {builderDecision.action === 'answer' || (builderDecision.action === 'none' && !setupFlowAllowsDraft) ? null : (
                <Button
                  type="button"
                  onClick={() => {
                    if (canCreateDraft || setupFlowAllowsDraft || builderDecision.action === 'create') {
                      onCreate();
                    }
                  }}
                  disabled={actionLoading || !canUsePrimaryAction}
                  className="shrink-0"
                >
                  {actionLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : canCreateDraft ? <CheckCircle2 className="mr-2 h-4 w-4" /> : <MessageSquareText className="mr-2 h-4 w-4" />}
                  {primaryActionLabel}
                </Button>
              )}
            </div>
            {firstQuestion ? (
              <div className="mt-4 grid gap-2 md:grid-cols-[minmax(0,1fr)_auto]">
                <textarea
                  className="min-h-16 resize-none rounded-xl border border-amber-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-amber-400"
                  value={reply}
                  onChange={(event) => onReplyChange(event.target.value)}
                  placeholder="Ответьте одним сообщением"
                />
                <Button type="button" variant="outline" className="bg-white" onClick={onSendReply} disabled={actionLoading || !reply.trim()}>
                  Ответить
                </Button>
              </div>
            ) : null}
          </div>

          {showInlineConnectionSetup ? (
            <div className="rounded-2xl border border-sky-200 bg-sky-50/70 p-3">
              <div className="px-1 pb-1">
                <div className="text-sm font-semibold text-slate-950">Выберите способ работы агента</div>
                <div className="mt-1 text-xs leading-5 text-slate-600">
                  Это обязательный шаг перед созданием: LocalOS должен явно знать, через какой безопасный канал читать данные или доставлять результат. Рекомендованный способ уже выбран, если подходит только один вариант.
                </div>
              </div>
              <BuilderRequiredConnectionsPanel
                preview={preview}
                selectedProviderRoutes={selectedProviderRoutes}
                onSelectProviderRoute={onSelectProviderRoute}
              />
              <BuilderConnectionReadinessPanel
                readiness={preview?.connection_readiness}
                answerBindings={preview?.connection_answer_bindings}
                selectedProviderRoutes={selectedProviderRoutes}
                acceptedProviderRoutes={acceptedProviderRoutes}
                missingProviderRouteKeys={missingProviderRouteKeys}
                onAcceptProviderRoutes={onAcceptProviderRoutes}
                onSelectProviderRoute={onSelectProviderRoute}
              />
              {missingConnectionChoices.length ? (
                <div className="mt-3 rounded-xl border border-amber-200 bg-white px-3 py-2 text-xs leading-5 text-amber-950">
                  Выберите, какие уже подключённые сервисы использовать: {missingConnectionChoices.map((item) => item.title || connectorLabel(item.provider)).join(', ')}.
                </div>
              ) : null}
            </div>
          ) : null}

          <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="text-sm font-semibold text-slate-950">Что понял LocalOS</div>
                <div className="mt-1 text-xs text-slate-500">Короткая проверка перед созданием. Подробности ниже.</div>
              </div>
              <div className="flex flex-wrap gap-2">
                <span className="rounded-full bg-white px-2.5 py-1 text-xs font-medium text-slate-700 ring-1 ring-slate-200">
                  {preview?.category_label || humanizeCategory(session.category)}
                </span>
                {estimatedCredits > 0 ? (
                  <span className="rounded-full bg-sky-50 px-2.5 py-1 text-xs font-medium text-sky-700 ring-1 ring-sky-200">
                    ~{estimatedCredits} кредита
                  </span>
                ) : null}
              </div>
            </div>

            <div className="mt-4 grid gap-3 lg:grid-cols-3">
              <div className="rounded-xl bg-white px-3 py-3 ring-1 ring-slate-200">
                <div className="text-xs font-semibold uppercase text-slate-500">Задача</div>
                <div className="mt-1 line-clamp-4 text-sm leading-6 text-slate-900">{previewTaskText}</div>
              </div>
              <div className="rounded-xl bg-white px-3 py-3 ring-1 ring-slate-200">
                <div className="text-xs font-semibold uppercase text-slate-500">Данные</div>
                <div className="mt-1 line-clamp-3 text-sm leading-6 text-slate-900">{previewDataText}</div>
              </div>
              <div className="rounded-xl bg-white px-3 py-3 ring-1 ring-slate-200">
                <div className="text-xs font-semibold uppercase text-slate-500">Результат и контроль</div>
                <div className="mt-1 line-clamp-3 text-sm leading-6 text-slate-900">{previewResultText}</div>
                <div className="mt-2 rounded-lg bg-slate-50 px-2 py-1 text-xs text-slate-600 ring-1 ring-slate-100">
                  Контроль: {previewControlText}
                </div>
              </div>
            </div>

            <BuilderTrustBlock ready={canCreateDraft} />

            <details className="mt-4 rounded-xl border border-slate-200 bg-white px-3 py-3 text-sm leading-6 text-slate-700">
              <summary className="cursor-pointer font-semibold text-slate-950">Подробности проверки</summary>
              <div className="mt-3 space-y-3">
                <PreviewRow label="Что извлечь" value={preview?.extraction_rules || 'уточнить'} />
                <PreviewRow label="Правила" value={preview?.processing_rules || 'уточнить'} />
                <BuilderCreationDecisionBanner
                  decision={builderDecision}
                  actionLoading={actionLoading}
                  canSendReply={Boolean(reply.trim())}
                  canCreateDraft={canCreateDraft}
                  onSendReply={onSendReply}
                  onCreate={onCreate}
                />
                {!showInlineConnectionSetup ? (
                  <BuilderRequiredConnectionsPanel
                    preview={preview}
                    selectedProviderRoutes={selectedProviderRoutes}
                    onSelectProviderRoute={onSelectProviderRoute}
                  />
                ) : null}
                <BuilderCompilerPolicyReviewPanel
                  review={preview?.compiler_policy_review}
                  workflowDraft={preview?.compiler_workflow_draft}
                  approvalPoints={preview?.compiler_approval_points}
                  unsupportedRequests={preview?.compiler_unsupported_requests}
                  accepted={acceptedCompilerPlan}
                  onAccept={onAcceptCompilerPlan}
                />
                <BuilderServiceIntelligencePanel
                  intelligence={preview?.service_intelligence}
                  selectedProviderRoutes={selectedProviderRoutes}
                  onSelectProviderRoute={onSelectProviderRoute}
                />
                {!showInlineConnectionSetup ? (
                  <BuilderConnectionReadinessPanel
                    readiness={preview?.connection_readiness}
                    answerBindings={preview?.connection_answer_bindings}
                    selectedProviderRoutes={selectedProviderRoutes}
                    acceptedProviderRoutes={acceptedProviderRoutes}
                    missingProviderRouteKeys={missingProviderRouteKeys}
                    onAcceptProviderRoutes={onAcceptProviderRoutes}
                    onSelectProviderRoute={onSelectProviderRoute}
                  />
                ) : null}
                <BuilderConnectionResolverPanel resolver={preview?.connection_resolver} />
                <BuilderSetupFlowPanel setupFlow={preview?.setup_flow} />
                <BuilderExecutionBoundaryPanel plannerLoop={preview?.openclaw_planner_loop} />
                <BuilderConnectionSummaryPanel
                  summary={preview?.connection_summary}
                  selectedBindings={selectedConnectionBindings}
                  onSelectBinding={onSelectConnectionBinding}
                />
                {!showInlineConnectionSetup && missingConnectionChoices.length ? (
                  <div className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-950">
                    Выберите, какие уже подключённые сервисы использовать: {missingConnectionChoices.map((item) => item.title || connectorLabel(item.provider)).join(', ')}. После этого LocalOS привяжет их к агенту.
                  </div>
                ) : null}
                <BuilderTechnicalDiagnostics
                  connectorIntelligence={preview?.connector_intelligence}
                  plannerLoop={preview?.openclaw_planner_loop}
                  connectionPlan={preview?.connection_plan || null}
                  feasibility={preview?.feasibility}
                  connectors={preview?.required_connectors}
                />
                {!canCreateDraft && createBlockers.length ? (
                  <div className="rounded-xl border border-amber-200 bg-white px-3 py-3 text-xs leading-5 text-amber-950">
                    <div className="font-semibold">Почему агента пока нельзя создать</div>
                    <div className="mt-2 space-y-1">
                      {createBlockers.slice(0, 5).map((item) => (
                        <div key={item.key} className="flex gap-2">
                          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                          <span>{item.label}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}
              </div>
            </details>

            <details className="mt-3 rounded-xl border border-slate-200 bg-white px-3 py-3 text-sm leading-6 text-slate-700">
              <summary className="cursor-pointer font-semibold text-slate-950">История диалога</summary>
              <div className="mt-3 max-h-72 space-y-2 overflow-auto rounded-xl bg-slate-50 p-3">
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
            </details>
            {estimatedCredits > 0 ? (
              <div className="mt-3 rounded-xl border border-sky-200 bg-sky-50 px-3 py-2 text-xs leading-5 text-sky-900">
                Создание агента спишет примерно {estimatedCredits} кредита с баланса. Если кредитов не хватит, предложим пополнить счёт.
              </div>
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  );
};

export const BuilderTechnicalDiagnostics = ({
  connectorIntelligence,
  plannerLoop,
  connectionPlan,
  feasibility,
  connectors,
}: {
  connectorIntelligence?: AgentConnectorIntelligence;
  plannerLoop?: AgentBuilderPlannerLoop;
  connectionPlan?: AgentConnectionPlan | null;
  feasibility?: AgentBuilderFeasibility;
  connectors?: AgentBuilderConnectorPreview[];
}) => {
  const hasDetails = Boolean(
    connectorIntelligence
    || plannerLoop
    || connectionPlan
    || feasibility
    || (connectors && connectors.length),
  );
  if (!hasDetails) {
    return <CompiledBuilderFlow compact />;
  }
  return (
    <details
      className="mt-3 rounded-xl border border-slate-200 bg-white px-3 py-3 text-xs leading-5 text-slate-700"
      data-source-contract={AGENT_BLUEPRINT_LEGACY_SOURCE_CONTRACT_LABELS.join('|')}
    >
      <summary className="cursor-pointer font-semibold text-slate-950">
        Техническая диагностика
      </summary>
      <div className="mt-1 text-[11px] leading-4 text-slate-500">
        Для проверки: способы подключения, карта действий, проверка доступов и правила безопасности. Обычный следующий шаг показан выше.
      </div>
      <div className="mt-3">
        <CompiledBuilderFlow compact />
        <ConnectorIntelligencePanel intelligence={connectorIntelligence} />
        <BuilderPlannerLoopPanel plannerLoop={plannerLoop} />
        <AgentConnectionPlanPanel connectionPlan={connectionPlan || null} compact />
        <BuilderFeasibilityPanel feasibility={feasibility} connectors={connectors} />
      </div>
    </details>
  );
};

export const CompiledBuilderFlow = ({ compact = false }: { compact?: boolean }) => (
    <div
      className={cn(compact ? 'mt-0' : 'mt-4', 'rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-3 text-xs leading-5 text-emerald-950')}
      data-contract-label="LocalOS должен собрать проверяемый workflow"
    >
    <div className="font-semibold">После создания LocalOS соберёт проверяемую логику агента</div>
    <div className="mt-2 grid gap-2 sm:grid-cols-4">
      {[
        ['1', 'План', 'задача и шаги'],
        ['2', 'Проверка', 'разрешённые действия и подтверждения'],
        ['3', 'Доступы', 'что нужно подключить'],
        ['4', 'Запуск', 'только после проверки'],
      ].map(([index, title, text]) => (
        <div key={title} className="rounded-lg bg-white/70 px-2 py-2 ring-1 ring-emerald-100">
          <div className="flex items-center gap-2 font-medium">
            <span className="flex h-5 w-5 items-center justify-center rounded-full bg-emerald-100 text-[11px] text-emerald-800">{index}</span>
            {title}
          </div>
          <div className="mt-1 text-emerald-800">{text}</div>
        </div>
      ))}
    </div>
    <div className="mt-2 text-emerald-800">
      Внешние отправки, публикации, платежи и опасные изменения не запускаются из мастера. Рискованные действия требуют ручного подтверждения.
    </div>
  </div>
);

export const BuilderCreationDecisionBanner = ({
  decision,
  actionLoading,
  canSendReply,
  canCreateDraft,
  onSendReply,
  onCreate,
}: {
  decision: AgentConnectionDecision;
  actionLoading: boolean;
  canSendReply: boolean;
  canCreateDraft: boolean;
  onSendReply: () => void;
  onCreate: () => void;
}) => {
  const ready = decision.tone === 'ready';
  const choice = decision.tone === 'choice';
  const blocked = decision.tone === 'blocked';
  const needsAction = decision.tone === 'needs_action';
  const canClick = decision.action === 'answer'
    ? canSendReply
    : decision.action === 'create'
    ? canCreateDraft
    : false;
  return (
    <div className={cn(
      'mt-4 rounded-xl border px-3 py-3',
      ready ? 'border-emerald-200 bg-emerald-50' : '',
      choice ? 'border-sky-200 bg-sky-50' : '',
      needsAction ? 'border-amber-200 bg-amber-50' : '',
      blocked ? 'border-rose-200 bg-rose-50' : '',
      !ready && !choice && !needsAction && !blocked ? 'border-slate-200 bg-white' : '',
    )}>
      <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
        <div>
          <div className={cn('text-sm font-semibold', ready ? 'text-emerald-950' : choice ? 'text-sky-950' : needsAction ? 'text-amber-950' : blocked ? 'text-rose-950' : 'text-slate-950')}>
            {decision.title}
          </div>
          <div className={cn('mt-1 text-xs leading-5', ready ? 'text-emerald-800' : choice ? 'text-sky-800' : needsAction ? 'text-amber-900' : blocked ? 'text-rose-900' : 'text-slate-600')}>
            {decision.description}
          </div>
        </div>
        {decision.cta ? (
          <Button
            type="button"
            size="sm"
            variant={ready || decision.action === 'create' ? 'default' : 'outline'}
            className={cn(!(ready || decision.action === 'create') && 'bg-white')}
            disabled={actionLoading || !canClick}
            onClick={() => {
              if (decision.action === 'answer') {
                onSendReply();
                return;
              }
              if (decision.action === 'create') {
                onCreate();
              }
            }}
          >
            {actionLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : decision.action === 'answer' ? <MessageSquareText className="mr-2 h-4 w-4" /> : <CheckCircle2 className="mr-2 h-4 w-4" />}
            {decision.cta}
          </Button>
        ) : null}
      </div>
    </div>
  );
};
