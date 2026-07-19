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
  AgentSummaryPill
} from './employee';
import {
  providerActionDescription,
  ProviderActionPill
} from './connections';
import {
  AgentRunObservabilityPanel,
  RunColumn,
  TimelineItem,
  ArtifactItem
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

export const AgentAdvancedPanel = ({
  activeRun,
  versions,
  activationGate,
  actionLoading,
  onPreviewNextStepAction,
  onActivateVersion,
  onApplyFinanceRequests,
}: {
  activeRun: AgentRun | null;
  versions: Array<Record<string, unknown>>;
  activationGate?: AgentActivationGate;
  actionLoading: boolean;
  onPreviewNextStepAction: (nextStep: string) => void;
  onActivateVersion: (versionId: string) => void;
  onApplyFinanceRequests: (runId: string) => void;
}) => (
  <div className="space-y-4">
    <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
      <div className="text-sm font-semibold text-slate-950">Технический запуск</div>
      <div className="mt-1 max-w-3xl text-sm leading-6 text-slate-600">
        Технический слой для superadmin/debug: версии логики, журнал действий, списания, артефакты, подтверждения и экспорт поддержки.
      </div>
    </div>
    {activeRun ? (
      <>
        <AgentRunObservabilityPanel
          run={activeRun}
          activationGate={activationGate}
          actionLoading={actionLoading}
          onPreviewNextStepAction={onPreviewNextStepAction}
          onActivateVersion={onActivateVersion}
          onApplyFinanceRequests={onApplyFinanceRequests}
        />
        <div className="grid gap-4 xl:grid-cols-3">
          <RunColumn title="Шаги выполнения" icon={Clock3}>
            {(activeRun.steps || []).map((step) => (
              <TimelineItem key={step.id} title={humanizeStep(step.step_key)} meta={humanizeMeta(step.step_type)} status={step.status} />
            ))}
          </RunColumn>
          <RunColumn title="Сохранённые результаты" icon={FileCheck2}>
            {(activeRun.artifacts || []).map((artifact) => <ArtifactItem key={artifact.id} artifact={artifact} />)}
          </RunColumn>
          <RunColumn title="Решения" icon={ShieldCheck}>
            {(activeRun.approvals || []).map((approval) => (
              <TimelineItem key={approval.id} title={approval.title} meta={humanizeMeta(approval.approval_type)} status={approval.status} />
            ))}
          </RunColumn>
        </div>
      </>
    ) : (
      <DashboardEmptyState
        title="Нет выбранного запуска"
        description="Запустите агента или откройте результат, чтобы увидеть технический журнал и экспорт поддержки."
      />
    )}
    <details className="rounded-2xl border border-slate-200 bg-white px-4 py-3">
      <summary className="cursor-pointer text-sm font-semibold text-slate-700 hover:text-slate-950">
        Raw versions payload
      </summary>
      <pre className="mt-3 max-h-96 overflow-auto rounded-xl bg-slate-950 p-3 text-[11px] leading-5 text-slate-100">
        {JSON.stringify(versions.slice(0, 5), null, 2)}
      </pre>
    </details>
  </div>
);

export const AgentVoiceStylePanel = ({
  blueprint,
  availablePersonaAgents,
}: {
  blueprint: AgentBlueprint;
  availablePersonaAgents: PersonaAgent[];
}) => {
  const voiceName = getAgentVoiceName(blueprint);
  const productAgent = blueprint.product_agent || {};
  const personaId = blueprint.active_persona_agent_id || blueprint.latest_persona_agent_id || productAgent.persona_agent_id || '';
  return (
    <div className="space-y-4">
      <div className="grid gap-4 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
        <div className="rounded-2xl border border-slate-200 bg-white p-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="text-sm font-semibold text-slate-950">Голос выбранного агента</div>
              <div className="mt-1 text-sm leading-6 text-slate-600">
                Голос задаёт стиль общения. Логика, ручные подтверждения и разрешённые действия остаются в настройках агента.
              </div>
            </div>
            <StatusBadge status={voiceName ? 'active' : 'draft'} />
          </div>
          <div className="mt-4 grid gap-2">
            <AgentSummaryPill label="Текущий голос" value={voiceName || 'не привязан'} />
            <AgentSummaryPill label="Связь" value={String(personaId || 'нет связи')} />
            <AgentSummaryPill label="Источник" value="старый голос AIAgents" />
          </div>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-4">
          <div className="text-sm font-semibold text-slate-950">Доступные голоса</div>
          <div className="mt-1 text-sm leading-6 text-slate-600">
            Эти записи больше не отдельные пользовательские агенты. Они ждут привязки как “Голос агента”.
          </div>
          <div className="mt-4 grid gap-2 md:grid-cols-2">
            {availablePersonaAgents.length ? availablePersonaAgents.map((agent) => (
              <div key={agent.id} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="truncate text-sm font-semibold text-slate-950">{agent.name || 'Голос агента'}</div>
                    <div className="mt-1 text-xs text-slate-500">{agent.type || 'голос'} · {agent.is_active === false ? 'выключен' : 'доступен'}</div>
                  </div>
                  {agent.id === personaId ? <StatusBadge status="active" /> : null}
                </div>
                <div className="mt-2 line-clamp-2 text-xs leading-5 text-slate-600">
                  {agent.description || agent.task || agent.identity || 'Стиль общения без отдельной логики запуска.'}
                </div>
              </div>
            )) : (
              <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50 px-3 py-3 text-sm text-slate-500">
                Старых голосов пока нет. Их можно создать отдельно и потом привязать к версии агента.
              </div>
            )}
          </div>
        </div>
      </div>
      <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4">
        <div className="text-sm font-semibold text-amber-950">Старая логика больше не основной редактор</div>
        <div className="mt-1 text-sm leading-6 text-amber-900">
          AIAgents показываются как голоса. Логика агента редактируется через версии, diff, активацию и откат.
        </div>
      </div>
    </div>
  );
};

export const AgentWorkspacePanel = ({
  versions,
  learningEvents,
  versionEvents,
  legacyMigration,
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
  learningEvents: AgentLearningEvent[];
  versionEvents: AgentVersionEvent[];
  legacyMigration: Record<string, unknown>;
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
    description="Данные, правила, результат и ручной контроль. Технический JSON спрятан в расширенном режиме."
  >
    <div className="grid gap-5 2xl:grid-cols-[minmax(0,1.2fr)_minmax(20rem,0.8fr)]">
      <div className="grid gap-3">
        <VersionSummary
          versions={versions}
          latestVersionNumber={latestVersionNumber}
          activeVersionId={activeVersionId}
          onStartVersionRun={onStartVersionRun}
          onActivateVersion={onActivateVersion}
          onRollbackVersion={onRollbackVersion}
        />
        <LearningHistoryPanel
          learningEvents={learningEvents}
          versionEvents={versionEvents}
          legacyMigration={legacyMigration}
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

export const WizardTextArea = ({ label, value, onChange, placeholder }: { label: string; value: string; onChange: (value: string) => void; placeholder: string }) => (
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

export const DatahubCatalogList = ({
  catalog,
  actionLoading,
  onConnect,
}: {
  catalog: AgentSourceCatalogItem[];
  actionLoading: boolean;
  onConnect: (sourceKey: string) => void;
}) => {
  const connected = catalog.filter((item) => item.connected);
  const available = catalog.filter((item) => !item.connected);
  return (
    <div className="space-y-3 rounded-xl border border-slate-200 bg-white p-3">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Данные агента</div>
          <div className="mt-1 text-xs text-slate-500">Сначала подключённые источники, ниже доступные источники LocalOS.</div>
        </div>
        <span className="text-xs text-slate-400">{catalog.length ? `${catalog.length} источников` : 'источники не загружены'}</span>
      </div>
      {catalog.length ? (
        <>
          <DatahubCatalogGroup
            title="Подключено к агенту"
            emptyText="У агента пока нет подключённых источников."
            items={connected}
            actionLoading={actionLoading}
            onConnect={onConnect}
          />
          <DatahubCatalogGroup
            title="Доступно в LocalOS"
            emptyText="Доступных источников LocalOS пока нет."
            items={available}
            actionLoading={actionLoading}
            onConnect={onConnect}
          />
        </>
      ) : (
        <div className="rounded-lg border border-dashed border-slate-200 px-3 py-3 text-sm text-slate-500">
          Каталог появится после выбора агента.
        </div>
      )}
    </div>
  );
};

export const DatahubCatalogGroup = ({
  title,
  emptyText,
  items,
  actionLoading,
  onConnect,
}: {
  title: string;
  emptyText: string;
  items: AgentSourceCatalogItem[];
  actionLoading: boolean;
  onConnect: (sourceKey: string) => void;
}) => (
  <div className="space-y-2">
    <div className="text-xs font-semibold text-slate-700">{title}</div>
    {items.length ? items.map((item) => (
      <DatahubCatalogItem key={item.key} item={item} actionLoading={actionLoading} onConnect={onConnect} />
    )) : (
      <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-3 py-3 text-xs text-slate-500">
        {emptyText}
      </div>
    )}
  </div>
);

export const DatahubCatalogItem = ({
  item,
  actionLoading,
  onConnect,
}: {
  item: AgentSourceCatalogItem;
  actionLoading: boolean;
  onConnect: (sourceKey: string) => void;
}) => {
  const state = item.extraction_state || item.state;
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-sm font-medium text-slate-950">{item.title || humanizeMeta(item.key)}</div>
          <div className="mt-1 text-xs leading-5 text-slate-500">{item.description || 'Источник данных LocalOS'}</div>
        </div>
        <span className={cn(
          'shrink-0 rounded-full px-2 py-1 text-xs font-medium ring-1',
          item.connected ? 'bg-emerald-50 text-emerald-700 ring-emerald-200' : item.available_count ? 'bg-white text-slate-700 ring-slate-200' : 'bg-slate-100 text-slate-500 ring-slate-200',
        )}>
          {item.connected ? humanizeSourceState(state) : item.available_count ? `${item.available_count}` : humanizeSourceState(state)}
        </span>
      </div>
      {item.error ? (
        <div className="mt-2 rounded-md border border-amber-200 bg-amber-50 px-2 py-1 text-xs text-amber-800">
          {item.error}
        </div>
      ) : null}
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
  );
};

export const AgentSourcesList = ({ sources, compact = false }: { sources: AgentSource[]; compact?: boolean }) => (
  <div className={cn('space-y-2', compact && 'space-y-1')}>
    {sources.length ? sources.map((source) => (
      <div key={source.id || source.name || source.file_name || source.internal_source} className={cn('rounded-lg bg-white px-3 py-2 text-xs leading-5 text-slate-600 ring-1 ring-slate-200', compact && 'bg-emerald-50 ring-emerald-100')}>
        <div className="font-medium text-slate-900">{source.name || source.file_name || source.internal_source || 'Источник'}</div>
        <div>
          {source.internal_source ? humanizeMeta(source.internal_source) : humanizeSourceType(source.source_type)}
          {' · '}
          {humanizeSourceState(source.extraction_state)}
          {' · '}
          {formatSourceSize(source.content_length, source.file_size_bytes)}
        </div>
        {source.extraction_error ? (
          <div className="mt-1 rounded-md border border-amber-200 bg-amber-50 px-2 py-1 text-amber-800">
            {source.extraction_error}
          </div>
        ) : null}
      </div>
    )) : (
      <div className="rounded-lg border border-dashed border-slate-200 bg-white px-3 py-3 text-sm text-slate-500">
        Добавьте текст, файл или источник LocalOS.
      </div>
    )}
  </div>
);

export const AgentConnectionDecisionBanner = ({
  decision,
  actionLoading,
  onConfigure,
  onPreview,
}: {
  decision: AgentConnectionDecision;
  actionLoading: boolean;
  onConfigure: (bindingKey: string) => void;
  onPreview: () => void;
}) => {
  const ready = decision.tone === 'ready';
  const choice = decision.tone === 'choice';
  const blocked = decision.tone === 'needs_action';
  const canClick = decision.action === 'preview' || (decision.action === 'configure' && Boolean(decision.bindingKey));
  return (
    <div className={cn(
      'rounded-xl border px-3 py-3',
      ready ? 'border-emerald-200 bg-emerald-50' : '',
      choice ? 'border-sky-200 bg-sky-50' : '',
      blocked ? 'border-amber-200 bg-amber-50' : '',
      !ready && !choice && !blocked ? 'border-slate-200 bg-slate-50' : '',
    )}>
      <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
        <div>
          <div className={cn('text-sm font-semibold', ready ? 'text-emerald-950' : choice ? 'text-sky-950' : blocked ? 'text-amber-950' : 'text-slate-950')}>
            {decision.title}
          </div>
          <div className={cn('mt-1 text-xs leading-5', ready ? 'text-emerald-800' : choice ? 'text-sky-800' : blocked ? 'text-amber-900' : 'text-slate-600')}>
            {decision.description}
          </div>
        </div>
        {decision.cta ? (
          <Button
            type="button"
            size="sm"
            variant={ready ? 'default' : 'outline'}
            className={cn(!ready && 'bg-white')}
            disabled={actionLoading || !canClick}
            onClick={() => {
              if (decision.action === 'preview') {
                onPreview();
                return;
              }
              if (decision.bindingKey) {
                onConfigure(decision.bindingKey);
              }
            }}
          >
            {actionLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : ready ? <Play className="mr-2 h-4 w-4" /> : <Zap className="mr-2 h-4 w-4" />}
            {decision.cta}
          </Button>
        ) : null}
      </div>
    </div>
  );
};

export const AgentIntegrationsPanel = ({
  integrations,
  availableIntegrations,
  providerCatalog,
  authOptions,
  bindingStatus,
  connectionPlan,
  selectedBindingKey,
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
  onSelectBinding,
  onSaveCustomProcess,
  onRunCustomProcessPreview,
  onPreviewRun,
}: {
  integrations: AgentIntegration[];
  availableIntegrations: AgentIntegration[];
  providerCatalog: AgentIntegrationCatalogItem[];
  authOptions: AgentExternalAuthOption[];
  bindingStatus: AgentIntegrationBindingStatus[];
  connectionPlan: AgentConnectionPlan | null;
  selectedBindingKey: string;
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
  onSelectBinding: (bindingKey: string) => void;
  onSaveCustomProcess: () => void;
  onRunCustomProcessPreview: () => void;
  onPreviewRun: () => void;
}) => {
  const sheetIntegration = integrations.find((item) => item.provider === 'google_sheets');
  const browserIntegration = integrations.find((item) => item.provider === 'browser_use');
  const telegramIntegration = integrations.find((item) => item.provider === 'telegram');
  const whatsappIntegration = integrations.find((item) => item.provider === 'whatsapp');
  const matonIntegration = integrations.find((item) => item.provider === 'maton');
  const selectedPlanItem = (connectionPlan?.items || []).find((item) => item.key === selectedBindingKey);
  const needsBrowserUse = bindingStatus.some((binding) => binding.provider === 'browser_use');
  const needsTelegram = bindingStatus.some((binding) => binding.provider === 'telegram');
  const needsWhatsapp = bindingStatus.some((binding) => binding.provider === 'whatsapp');
  const needsMaton = bindingStatus.some((binding) => binding.provider === 'maton') || (selectedPlanItem?.provider_routes || []).some((route) => route.provider === 'maton');
  const needsSheetsRead = bindingStatus.some((binding) => binding.provider === 'google_sheets' && binding.capability === 'google_sheets.read_rows');
  const needsSheetsAppend = bindingStatus.some((binding) => binding.provider === 'google_sheets' && binding.capability === 'sheets.append_row_request');
  const needsSheets = needsSheetsRead || needsSheetsAppend || bindingStatus.some((binding) => binding.provider === 'google_sheets');
  const isTelegramToSheetsProcess = needsTelegram && needsSheetsAppend;
  const sheetsTitle = needsSheetsRead && needsSheetsAppend ? 'Google Sheets: чтение и запись' : needsSheetsRead ? 'Google Sheets: источник данных' : 'Google Sheets: запись результата';
  const connectedBindings = bindingStatus.filter((binding) => binding.status === 'connected' || binding.status === 'ready').length;
  const missingBindings = bindingStatus.filter((binding) => binding.status !== 'connected' && binding.status !== 'ready').length;
  const canPreviewRun = !bindingStatus.length || missingBindings === 0;
  const connectionDecision = buildAgentConnectionDecision(connectionPlan, bindingStatus, canPreviewRun);
  const selectedBinding = bindingStatus.find((binding) => binding.key === selectedBindingKey)
    || bindingStatus.find((binding) => binding.status !== 'connected' && binding.status !== 'ready')
    || bindingStatus[0];
  const selectedProvider = selectedBinding?.provider || '';
  const hasRequiredBindings = bindingStatus.length > 0;
  const showBrowserUseForm = needsBrowserUse && (!hasRequiredBindings || selectedProvider === 'browser_use');
  const showTelegramForm = (needsTelegram || !hasRequiredBindings) && (!hasRequiredBindings || selectedProvider === 'telegram');
  const showWhatsappForm = needsWhatsapp && (!hasRequiredBindings || selectedProvider === 'whatsapp');
  const showMatonForm = needsMaton && (!hasRequiredBindings || selectedProvider === 'maton');
  const showSheetsForm = (needsSheets || !hasRequiredBindings) && (!hasRequiredBindings || selectedProvider === 'google_sheets');
  const showCustomProcessForm = isTelegramToSheetsProcess && !hasRequiredBindings;
  const otherBindings = bindingStatus.filter((binding) => binding.key !== selectedBinding?.key);
  return (
    <div className="space-y-3 rounded-2xl border border-slate-200 bg-white p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Источники и каналы</div>
          <div className="mt-1 text-xs leading-5 text-slate-500">Что запускает агента, откуда он берёт данные и куда готовит результат после подтверждения.</div>
        </div>
        <span className="shrink-0 text-xs text-slate-400">{bindingStatus.length ? `${connectedBindings}/${bindingStatus.length}` : `${integrations.length}/${providerCatalog.length || 2}`}</span>
      </div>

      <AgentConnectionDecisionBanner
        decision={connectionDecision}
        actionLoading={actionLoading}
        onConfigure={onSelectBinding}
        onPreview={onPreviewRun}
      />

      {bindingStatus.length ? (
        <div className={cn('rounded-lg px-3 py-2 text-xs leading-5 ring-1', missingBindings ? 'bg-amber-50 text-amber-900 ring-amber-200' : 'bg-emerald-50 text-emerald-900 ring-emerald-200')}>
	          {missingBindings ? `Нужно подключить ${missingBindings} ${missingBindings === 1 ? 'доступ' : 'доступа'}, прежде чем включать агента.` : 'Все обязательные подключения готовы. Можно проверять агента на примере и включать его.'}
        </div>
      ) : null}

      {!hasRequiredBindings ? (
      <div className={cn('rounded-lg px-3 py-3 ring-1', canPreviewRun ? 'bg-emerald-50 text-emerald-950 ring-emerald-200' : 'bg-slate-50 text-slate-600 ring-slate-200')}>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
	            <div className="text-sm font-semibold">Тест без отправки</div>
	            <div className="mt-1 text-xs leading-5">
	              {canPreviewRun
	                ? 'Проверим доступы, лимиты и ручные подтверждения. Ничего не отправим наружу.'
	                : 'Сначала заполните обязательные подключения. После этого станет доступна проверка на примере.'}
            </div>
          </div>
          <Button type="button" size="sm" onClick={onPreviewRun} disabled={actionLoading || !canPreviewRun}>
            {actionLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Play className="mr-2 h-4 w-4" />}
            Проверить на примере
          </Button>
        </div>
      </div>
      ) : null}

      {!hasRequiredBindings ? (
      <div className="grid gap-2">
        {needsBrowserUse ? <AgentIntegrationStatusItem integration={browserIntegration} provider="browser_use" fallbackTitle="Browser use" /> : null}
        {needsTelegram || !bindingStatus.length ? <AgentIntegrationStatusItem integration={telegramIntegration} provider="telegram" fallbackTitle="Telegram" /> : null}
        {needsWhatsapp ? <AgentIntegrationStatusItem integration={whatsappIntegration} provider="whatsapp" fallbackTitle="WhatsApp" /> : null}
        {needsMaton ? <AgentIntegrationStatusItem integration={matonIntegration} provider="maton" fallbackTitle="Maton.ai bridge" /> : null}
        {needsSheets || !bindingStatus.length ? <AgentIntegrationStatusItem integration={sheetIntegration} provider="google_sheets" fallbackTitle={sheetsTitle} /> : null}
      </div>
      ) : null}

      {showCustomProcessForm ? (
      <div className="space-y-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-3">
        <div className="flex items-center gap-2 text-sm font-medium text-slate-950">
          <Workflow className="h-4 w-4" />
          Логика канала Telegram → Google Sheets
        </div>
        <textarea
          className="min-h-20 w-full resize-none rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400"
          value={processRowValues}
          onChange={(event) => onProcessRowValuesChange(event.target.value)}
          placeholder="{{received_at}}, {{telegram_username}}, {{message_text}}"
        />
        <div className="text-xs leading-5 text-slate-500">
          Значения идут в строку таблицы по порядку. Сохранение создаёт новую активную версию агента.
        </div>
        <textarea
          className="min-h-20 w-full resize-none rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400"
          value={processPreviewMessage}
          onChange={(event) => onProcessPreviewMessageChange(event.target.value)}
          placeholder="Новая заявка: Анна, телефон +7..."
        />
        <div className="flex flex-wrap gap-2">
          <Button type="button" size="sm" onClick={onSaveCustomProcess} disabled={actionLoading}>
            Сохранить логику канала
          </Button>
          <Button type="button" size="sm" variant="outline" onClick={onRunCustomProcessPreview} disabled={actionLoading}>
            Проверить на примере
          </Button>
        </div>
      </div>
      ) : null}

      {showBrowserUseForm ? (
      <div className={cn('space-y-2 rounded-lg border px-3 py-3', selectedProvider === 'browser_use' ? 'border-sky-200 bg-sky-50' : 'border-slate-200 bg-slate-50')}>
        <div className="flex items-center gap-2 text-sm font-medium text-slate-950">
          <Workflow className="h-4 w-4" />
          Browser use
        </div>
        <div className="rounded-lg bg-white px-3 py-2 text-xs leading-5 text-slate-600 ring-1 ring-slate-200">
          Чтение сайтов идёт через защищенный способ LocalOS/OpenClaw. Агент готовит результат, внешние действия требуют подтверждения.
        </div>
        <textarea
          className="min-h-20 w-full resize-none rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400"
          value={browserTargetUrls}
          onChange={(event) => onBrowserTargetUrlsChange(event.target.value)}
          placeholder="https://example.com"
        />
        <input
          className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400"
          value={browserDailyCap}
          onChange={(event) => onBrowserDailyCapChange(event.target.value)}
          placeholder="Лимит проверок страниц в день"
          inputMode="numeric"
        />
        <Button type="button" size="sm" variant="outline" onClick={onSaveBrowserUseIntegration} disabled={actionLoading || !browserTargetUrls.trim()}>
          {selectedProvider === 'browser_use' ? 'Сохранить Browser use для выбранного шага' : 'Сохранить Browser use'}
        </Button>
      </div>
      ) : null}

      {showTelegramForm ? (
      <div className={cn('space-y-2 rounded-lg border px-3 py-3', selectedProvider === 'telegram' ? 'border-sky-200 bg-sky-50' : 'border-slate-200 bg-slate-50')}>
        <div className="flex items-center gap-2 text-sm font-medium text-slate-950">
          <MessageSquareText className="h-4 w-4" />
          Telegram
        </div>
        <select
          className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400"
          value={telegramBotMode}
          onChange={(event) => onTelegramBotModeChange(event.target.value)}
        >
          <option value="business_bot">Бот бизнеса</option>
          <option value="global_control_bot">Глобальный control bot</option>
        </select>
        <input
          className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400"
          value={telegramDailyCap}
          onChange={(event) => onTelegramDailyCapChange(event.target.value)}
          placeholder="Лимит сообщений в день"
          inputMode="numeric"
        />
        <Button type="button" size="sm" variant="outline" onClick={onSaveTelegramIntegration} disabled={actionLoading}>
          {selectedProvider === 'telegram' ? 'Сохранить Telegram для выбранного шага' : 'Подключить Telegram'}
        </Button>
      </div>
      ) : null}

      {showWhatsappForm ? (
      <div className={cn('space-y-2 rounded-lg border px-3 py-3', selectedProvider === 'whatsapp' ? 'border-sky-200 bg-sky-50' : 'border-slate-200 bg-slate-50')}>
        <div className="flex items-center gap-2 text-sm font-medium text-slate-950">
          <MessageSquareText className="h-4 w-4" />
          WhatsApp
        </div>
        <select
          className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400"
          value={whatsappChannelMode}
          onChange={(event) => onWhatsappChannelModeChange(event.target.value)}
        >
          <option value="whatsapp_business">WhatsApp Business</option>
          <option value="manual_whatsapp">Ручная отправка через WhatsApp</option>
        </select>
        <input
          className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400"
          value={whatsappDailyCap}
          onChange={(event) => onWhatsappDailyCapChange(event.target.value)}
          placeholder="Лимит сообщений в день"
          inputMode="numeric"
        />
        <Button type="button" size="sm" variant="outline" onClick={onSaveWhatsappIntegration} disabled={actionLoading}>
          {selectedProvider === 'whatsapp' ? 'Сохранить WhatsApp для выбранного шага' : 'Подключить WhatsApp'}
        </Button>
      </div>
      ) : null}

      {showMatonForm ? (
      <div className={cn('space-y-2 rounded-lg border px-3 py-3', selectedProvider === 'maton' ? 'border-sky-200 bg-sky-50' : 'border-slate-200 bg-slate-50')}>
        <div className="flex items-center gap-2 text-sm font-medium text-slate-950">
          <Workflow className="h-4 w-4" />
          Maton.ai bridge
        </div>
        <div className="rounded-lg bg-white px-3 py-2 text-xs leading-5 text-slate-600 ring-1 ring-slate-200">
          Используем сохранённый Maton.ai API key как delivery/provider bridge за LocalOS approval и audit boundary.
        </div>
        <select
          className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400"
          value={matonAuthRef}
          onChange={(event) => onMatonAuthRefChange(event.target.value)}
        >
          <option value="">Maton key не выбран</option>
          {authOptions.filter((option) => option.source === 'maton').map((option) => (
            <option key={option.id} value={option.id}>
              {option.display_name || 'Maton.ai'} · {option.id.slice(0, 8)}
            </option>
          ))}
        </select>
        <div className="grid gap-2 sm:grid-cols-2">
          <input
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400"
            value={matonChannel}
            onChange={(event) => onMatonChannelChange(event.target.value)}
            placeholder="maton_bridge"
          />
          <input
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400"
            value={matonDailyCap}
            onChange={(event) => onMatonDailyCapChange(event.target.value)}
            placeholder="Лимит действий в день"
            inputMode="numeric"
          />
        </div>
        <Button type="button" size="sm" onClick={onSaveMatonIntegration} disabled={actionLoading || !matonAuthRef.trim()}>
          {selectedProvider === 'maton' ? 'Сохранить Maton для выбранного шага' : 'Подключить Maton.ai'}
        </Button>
      </div>
      ) : null}

      {showSheetsForm ? (
      <div className={cn('space-y-3 rounded-lg border px-3 py-3', selectedProvider === 'google_sheets' ? 'border-sky-200 bg-sky-50' : 'border-slate-200 bg-slate-50')}>
        <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-start">
          <div>
            <div className="flex items-center gap-2 text-sm font-semibold text-slate-950">
              <Database className="h-4 w-4" />
              Подключите таблицу с поездками
            </div>
            <div className="mt-1 text-xs leading-5 text-slate-600">
              LocalOS прочитает строки и подготовит результат. Наружу ничего не отправится.
            </div>
          </div>
          <span className="rounded-full bg-white px-2.5 py-1 text-xs font-medium text-sky-800 ring-1 ring-sky-200">
            {needsSheetsRead && needsSheetsAppend ? 'чтение и запись' : needsSheetsRead ? 'чтение строк' : 'запись строк'}
          </span>
        </div>
        <label className="block text-xs font-medium text-slate-700">
          Ссылка на таблицу или ID
          <input
            className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-normal outline-none transition focus:border-slate-400"
            value={sheetSpreadsheetId}
            onChange={(event) => onSheetSpreadsheetIdChange(event.target.value)}
            placeholder="https://docs.google.com/spreadsheets/d/..."
          />
        </label>
        <div className="grid gap-2 sm:grid-cols-2">
          <label className="block text-xs font-medium text-slate-700">
            Лист
            <input
              className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-normal outline-none transition focus:border-slate-400"
              value={sheetName}
              onChange={(event) => onSheetNameChange(event.target.value)}
              placeholder="Sheet1"
            />
          </label>
          <label className="block text-xs font-medium text-slate-700">
            Лимит в день
            <input
              className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-normal outline-none transition focus:border-slate-400"
              value={sheetDailyCap}
              onChange={(event) => onSheetDailyCapChange(event.target.value)}
              placeholder="50"
              inputMode="numeric"
            />
          </label>
        </div>
        <label className="block text-xs font-medium text-slate-700">
          Google-доступ
          <select
            className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-normal outline-none transition focus:border-slate-400"
            value={sheetAuthRef}
            onChange={(event) => onSheetAuthRefChange(event.target.value)}
          >
            <option value="">Выбрать доступ автоматически</option>
            {authOptions.map((option) => (
              <option key={option.id} value={option.id}>
                {option.display_name || humanizeMeta(option.source)} · {option.id.slice(0, 8)}
              </option>
            ))}
          </select>
        </label>
        <Button type="button" size="sm" className="w-full sm:w-fit" onClick={onSaveSheetIntegration} disabled={actionLoading || !sheetSpreadsheetId.trim()}>
          {actionLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Database className="mr-2 h-4 w-4" />}
          {selectedProvider === 'google_sheets' ? 'Сохранить и перейти к тесту' : 'Сохранить таблицу'}
        </Button>
      </div>
      ) : null}

      {hasRequiredBindings ? (
      <div className={cn('rounded-lg px-3 py-3 ring-1', canPreviewRun ? 'bg-emerald-50 text-emerald-950 ring-emerald-200' : 'bg-slate-50 text-slate-600 ring-slate-200')}>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="text-sm font-semibold">Тест без отправки</div>
            <div className="mt-1 text-xs leading-5">
              {canPreviewRun
                ? 'Проверим доступы, лимиты и ручные подтверждения. Ничего не отправим наружу.'
                : 'Сначала заполните обязательные подключения. После этого станет доступна проверка на примере.'}
            </div>
          </div>
          <Button type="button" size="sm" onClick={onPreviewRun} disabled={actionLoading || !canPreviewRun}>
            {actionLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Play className="mr-2 h-4 w-4" />}
            Проверить на примере
          </Button>
        </div>
      </div>
      ) : null}

      {bindingStatus.length ? (
        <details className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-3">
          <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wide text-slate-500">Другие подключения</summary>
          <div className="mt-2 space-y-2">
          {(otherBindings.length ? otherBindings : bindingStatus).map((binding) => {
            const resourceFacts = connectionResourceFacts(binding.provider, binding.answer_config || null);
            return (
              <div
                key={binding.key || binding.provider}
                className={cn(
                  'rounded-lg bg-white px-3 py-2 text-xs ring-1',
                  selectedBindingKey && binding.key === selectedBindingKey ? 'ring-sky-300' : 'ring-slate-200',
                )}
              >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="font-medium text-slate-900">{connectorLabel(binding.provider)}</div>
                  <div className="mt-1 text-slate-500">
                    {bindingUserFacingRole(binding)}
                  </div>
                </div>
                <StatusBadge status={binding.status} />
              </div>
              <div className="mt-1 text-slate-600">{bindingActionHint(binding)}</div>
              {resourceFacts.length ? (
                <div className="mt-2 rounded-lg bg-emerald-50 px-2 py-1.5 text-emerald-800 ring-1 ring-emerald-100">
                  Ресурс из диалога: {resourceFacts.join(' · ')}
                </div>
              ) : null}
              {binding.missing_config?.length ? (
                <div className="mt-1 text-amber-700">Нужно заполнить: {binding.missing_config.join(', ')}</div>
              ) : null}
              {binding.approval_required ? (
                <div className="mt-1 text-slate-500">Перед внешним действием агент остановится и попросит подтверждение.</div>
              ) : null}
              {binding.status !== 'connected' && binding.status !== 'ready' ? (
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  className="mt-2"
                  onClick={() => onSelectBinding(binding.key || '')}
                  disabled={!binding.key}
                >
                  Настроить этот доступ
                </Button>
              ) : null}
              </div>
            );
          })}
          </div>
        </details>
      ) : null}

      {selectedBinding ? (
        <details className="rounded-lg border border-sky-200 bg-sky-50 px-3 py-2 text-xs leading-5 text-sky-950">
          <summary className="cursor-pointer font-semibold">Технические детали</summary>
          <div className="mt-2 font-semibold">Сейчас настраивается: {connectorLabel(selectedBinding.provider)}</div>
            <div className="mt-1">
            {bindingUserFacingRole(selectedBinding)}
            {selectedBinding.missing_config?.length ? ` · заполните: ${selectedBinding.missing_config.join(', ')}` : ''}
          </div>
          {selectedPlanItem?.route_summary ? (
            <div className="mt-2 rounded-lg bg-white/80 px-2 py-1.5 text-sky-900 ring-1 ring-sky-100">
              {userFacingAgentTechText(selectedPlanItem.route_summary)}
            </div>
          ) : null}
          {selectedPlanItem?.provider_routes?.length ? (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {selectedPlanItem.provider_routes.slice(0, 5).map((route) => (
                <ProviderActionPill
                  key={`${selectedPlanItem.key}-${route.provider}-${route.role}`}
                  route={route}
                  disabled={actionLoading || !selectedPlanItem.key}
                  onChoose={() => onChooseProviderRoute(selectedPlanItem.key || '', route)}
                />
              ))}
            </div>
          ) : null}
          {selectedPlanItem?.provider_routes?.length ? (
            <div className="mt-2 rounded-lg bg-white/80 px-2 py-1.5 text-sky-900 ring-1 ring-sky-100">
              {userFacingAgentTechText(providerActionDescription(selectedPlanItem.provider_routes.find((route) => route.state === 'available') || selectedPlanItem.provider_routes[0]) || 'Выберите доступный способ подключения для этого шага.')}
            </div>
          ) : null}
        </details>
      ) : null}

      {availableIntegrations.length ? (
        <details className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-3">
          <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wide text-slate-500">Уже подключены в бизнесе</summary>
          <div className="mt-2 space-y-1">
          {availableIntegrations.slice(0, 3).map((integration) => (
            <div key={integration.id} className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto]">
              <AgentIntegrationStatusItem integration={integration} provider={integration.provider} fallbackTitle={integration.display_name || integration.provider_label || integration.provider} />
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={() => onAttachExistingIntegration(integration, selectedProvider === integration.provider ? selectedBindingKey : '')}
                disabled={actionLoading}
              >
                {selectedProvider === integration.provider ? 'Использовать для шага' : 'Использовать'}
              </Button>
            </div>
          ))}
          </div>
        </details>
      ) : null}
    </div>
  );
};

export const AgentIntegrationStatusItem = ({
  integration,
  provider,
  fallbackTitle,
}: {
  integration?: AgentIntegration;
  provider: string;
  fallbackTitle: string;
}) => {
  const boundary = integration?.execution_boundary || {};
  const operation = String(integration?.config?.operation || '');
  const googleSheetsMode = operation === 'read_rows' ? 'Чтение строк' : operation === 'read_write' ? 'Чтение и запись после подтверждения' : 'Запись после подтверждения';
  const boundaryItems = [
    ...(boundary.triggers || []),
    ...(boundary.capabilities || []),
  ];
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-3 py-2">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="truncate text-sm font-medium text-slate-950">{integration?.display_name || integration?.provider_label || fallbackTitle}</div>
          <div className="mt-1 text-xs text-slate-500">{provider === 'google_sheets' ? googleSheetsMode : 'Когда запускать и куда отвечать'}</div>
        </div>
        <StatusBadge status={integration?.status || 'draft'} />
      </div>
      <div className="mt-2 text-xs leading-5 text-slate-600">
        {boundaryItems.length ? boundaryItems.slice(0, 3).map((item) => humanizeMeta(item)).join(', ') : 'Действие пока не подключено'}
      </div>
      {integration?.has_auth_ref ? (
        <div className="mt-1 text-xs text-emerald-700">Доступ подключён</div>
      ) : provider === 'google_sheets' ? (
        <div className="mt-1 text-xs text-amber-700">Нужен доступ к Google Sheets перед записью</div>
      ) : null}
    </div>
  );
};

export const VersionSummary = ({
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
  const activeVersion = versions.find((version) => version.is_active === true || (activeVersionId && version.id === activeVersionId));
  const activeVersionNumber = getVersionNumber(activeVersion);
  return (
    <div className="rounded-xl border border-slate-200 bg-white px-3 py-3 text-sm leading-6 text-slate-700">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="font-semibold text-slate-950">Версии агента</div>
        <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700 ring-1 ring-emerald-200">
          {activeVersionNumber ? `Рабочая версия v${activeVersionNumber}` : 'Рабочая версия не включена'}
        </span>
      </div>
      <div className="mt-1 text-xs text-slate-500">
        Новые запуски используют активную версию. Старые результаты остаются привязаны к версии, на которой были созданы.
      </div>
      {newestVersions.length ? (
        <div className="mt-3 space-y-2">
          {newestVersions.map((version, index) => {
            const versionNumber = getVersionNumber(version);
            const versionId = typeof version.id === 'string' ? version.id : '';
            const isActive = Boolean(version.is_active) || Boolean(versionId && versionId === activeVersionId);
            const summaryValue = version.diff_from_previous && typeof version.diff_from_previous === 'object' && 'summary' in version.diff_from_previous
              ? version.diff_from_previous.summary
              : '';
            const summary = typeof summaryValue === 'string' ? summaryValue : '';
            const diffValue = version.diff_from_previous && typeof version.diff_from_previous === 'object' ? version.diff_from_previous : {};
            const changedFieldsValue = 'changed_fields' in diffValue ? diffValue.changed_fields : [];
            const changedFields = Array.isArray(changedFieldsValue) ? changedFieldsValue.map((item) => humanizeMeta(String(item))) : [];
            const createdAt = typeof version.created_at === 'string' ? version.created_at : '';
            const versionRole = isActive ? 'Рабочая версия' : index === 0 ? 'Тестируемая версия' : 'Предыдущая версия';
            return (
              <div key={String(version.id || versionNumber || 'version')} className={cn('rounded-lg px-2 py-2 text-xs text-slate-600 ring-1', isActive ? 'bg-emerald-50 ring-emerald-200' : 'bg-slate-50 ring-slate-200')}>
                <div className="flex items-center justify-between gap-3">
                  <span className="font-medium text-slate-900">{versionNumber ? `v${versionNumber}` : 'версия'}</span>
                  <span>{versionRole}</span>
                </div>
                {summary ? <div className="mt-1 text-slate-500">{summary}</div> : null}
                {changedFields.length ? (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {changedFields.slice(0, 4).map((field) => (
                      <span key={`${versionId}-${field}`} className="rounded-full bg-white px-2 py-0.5 text-[11px] text-slate-600 ring-1 ring-slate-200">
                        {field}
                      </span>
                    ))}
                  </div>
                ) : null}
                {createdAt ? <div className="mt-1 text-[11px] text-slate-400">Создана: {createdAt}</div> : null}
                <div className="mt-2 flex flex-wrap gap-2">
                  <Button type="button" size="sm" variant="outline" onClick={() => onStartVersionRun(versionId)} disabled={!versionId}>
                    Проверить на примере
                  </Button>
                  {!isActive ? (
                    <Button type="button" size="sm" onClick={() => onActivateVersion(versionId)} disabled={!versionId}>
                      Активировать
                    </Button>
                  ) : null}
                  {!isActive && versionNumber && latestVersionNumber && versionNumber < latestVersionNumber ? (
                    <Button type="button" size="sm" variant="outline" onClick={() => onRollbackVersion(versionId)} disabled={!versionId}>
                      Вернуть эту версию
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

export const LearningHistoryPanel = ({
  learningEvents,
  versionEvents,
  legacyMigration,
}: {
  learningEvents: AgentLearningEvent[];
  versionEvents: AgentVersionEvent[];
  legacyMigration: Record<string, unknown>;
}) => {
  const legacySource = typeof legacyMigration.source === 'string' ? legacyMigration.source : '';
  const latestLearning = learningEvents.slice(-5).reverse();
  const latestVersionEvents = versionEvents.slice(-5).reverse();
  return (
    <div className="rounded-xl border border-slate-200 bg-white px-3 py-3 text-sm leading-6 text-slate-700">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="font-semibold text-slate-950">Обучение и версии</div>
        <span className="rounded-full bg-slate-50 px-2.5 py-1 text-xs font-medium text-slate-600 ring-1 ring-slate-200">
          {learningEvents.length} событий
        </span>
      </div>
      {legacySource ? (
        <div className="mt-2 rounded-lg border border-amber-200 bg-amber-50 px-2 py-2 text-xs text-amber-900">
          Мигрировано из {legacySource}. Старая логика больше не является активной логикой агента.
        </div>
      ) : null}
      <div className="mt-3 grid gap-3 md:grid-cols-2">
        <div className="space-y-2">
          <div className="text-xs font-semibold uppercase text-slate-500">История обучения</div>
          {latestLearning.length ? latestLearning.map((event) => (
            <div key={`${event.run_id || 'run'}-${event.candidate_version_id || event.created_at}`} className="rounded-lg bg-slate-50 px-3 py-2 text-xs">
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium text-slate-900">{humanizeLearningTrigger(event.trigger_type)}</span>
                <span className="text-slate-500">{event.candidate_version_number ? `v${event.candidate_version_number}` : humanizeVersionState(event.activation_state)}</span>
              </div>
              <div className="mt-1 line-clamp-2 text-slate-600">{event.feedback || 'обратная связь сохранена'}</div>
              <div className="mt-1 text-[11px] text-slate-400">{event.created_at || ''}</div>
            </div>
          )) : (
            <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-3 py-3 text-xs text-slate-500">
              История обучения появится после правки, отклонения, плохого результата или ошибки.
            </div>
          )}
        </div>
        <div className="space-y-2">
          <div className="text-xs font-semibold uppercase text-slate-500">История версий</div>
          {latestVersionEvents.length ? latestVersionEvents.map((event) => (
            <div key={`${event.action || 'event'}-${event.created_at || event.active_version_id}`} className="rounded-lg bg-slate-50 px-3 py-2 text-xs">
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium text-slate-900">{humanizeVersionAction(event.action)}</span>
                <span className="text-slate-500">{event.active_version_number ? `v${event.active_version_number}` : ''}</span>
              </div>
              <div className="mt-1 line-clamp-2 text-slate-600">{event.reason || 'событие версии'}</div>
              <div className="mt-1 text-[11px] text-slate-400">{event.created_at || ''}</div>
            </div>
          )) : (
            <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-3 py-3 text-xs text-slate-500">
              История активации и отката появится после смены активной версии.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export const humanizeLearningTrigger = (trigger?: string) => ({
  manual_edit: 'Ручная правка',
  approval_rejected: 'Отклонение',
  bad_outcome: 'Плохой результат',
  runtime_error: 'Ошибка',
  manual_feedback: 'Комментарий',
  run_review: 'Проверка запуска',
}[trigger || ''] || trigger || 'Событие обучения');

export const humanizeVersionAction = (action?: string) => ({
  created: 'Создана версия',
  setup_updated: 'Обновлена логика',
  activated: 'Активирована',
  rollback: 'Откат',
  feedback_applied: 'Обратная связь применена',
  legacy_migration_created: 'Создано миграцией',
}[action || ''] || action || 'Событие версии');

export const humanizeVersionState = (state?: string) => ({
  candidate: 'кандидатная версия',
  active: 'активная',
  rolled_back: 'откачена',
  archived: 'в архиве',
}[state || ''] || state || 'кандидатная версия');
