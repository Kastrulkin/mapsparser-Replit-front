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
  ExternalLink,
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
  formatBillingEstimateSummary,
  formatBillingActualSummary,
  formatBillingEstimateValue,
  formatBillingActualValue
} from './detail';
import {
  AgentSourcesList
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

export const AgentRunReviewPanel = ({
  review,
  latestVersionNumber,
  feedbackText,
  feedbackTrigger,
  feedbackVersionNotice,
  actionLoading,
  onFeedbackTextChange,
  onFeedbackTriggerChange,
  onSubmitFeedback,
  onActivateFeedbackVersion,
  onRollbackFeedbackVersion,
}: {
  review: AgentReview | null;
  latestVersionNumber: number | null;
  feedbackText: string;
  feedbackTrigger: string;
  feedbackVersionNotice: FeedbackVersionNotice | null;
  actionLoading: boolean;
  onFeedbackTextChange: (value: string) => void;
  onFeedbackTriggerChange: (value: string) => void;
  onSubmitFeedback: () => void;
  onActivateFeedbackVersion: (versionId: string) => void;
  onRollbackFeedbackVersion: (versionId: string) => void;
}) => {
  const journal = review?.journal && review.journal.length ? review.journal : buildJournalFromSections(review?.sections || []);
  const noticeVersionId = feedbackVersionNotice?.version_id || '';
  const previousVersionId = feedbackVersionNotice?.previous_version_id || '';
  const noticeState = feedbackVersionNotice?.activation_state || 'candidate';
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-slate-950">Журнал запуска</div>
          <div className="mt-1 text-xs text-slate-500">
            Входные данные, что агент извлёк, какие правила применил, результат и ручной контроль.
            {latestVersionNumber ? ` Следующий запуск пойдёт на v${latestVersionNumber}.` : ''}
          </div>
        </div>
        {review?.run_status ? <StatusBadge status={review.run_status} /> : null}
      </div>
      <div className="mb-4 grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(16rem,0.7fr)]">
        <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-3">
          <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Как настроен агент</div>
          <div className="mt-2 space-y-1 text-sm leading-6 text-slate-700">
            <div><span className="font-medium text-slate-950">Задача:</span> {userFacingAgentTechText(String(review?.setup?.workflow_description || 'не задана'))}</div>
            <div><span className="font-medium text-slate-950">Извлечь:</span> {userFacingAgentTechText(String(review?.setup?.extraction_rules || 'не задано'))}</div>
            <div><span className="font-medium text-slate-950">Правила:</span> {userFacingAgentTechText(String(review?.setup?.processing_rules || 'не заданы'))}</div>
            <div><span className="font-medium text-slate-950">Результат:</span> {userFacingAgentTechText(String(review?.setup?.output_format || 'не задан'))}</div>
          </div>
        </div>
        <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-3">
          <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Источники</div>
          {review?.used_sources?.length ? (
            <div className="mb-3">
              <div className="mb-2 text-xs font-medium text-slate-700">Использовано в последнем запуске</div>
              <AgentSourcesList sources={review.used_sources} compact />
            </div>
          ) : null}
          <div className="mb-2 text-xs font-medium text-slate-700">Подключено к агенту</div>
          <AgentSourcesList sources={review?.sources || []} />
        </div>
      </div>
      {journal.length ? (
        <div className="space-y-3">
          {journal.map((entry, index) => <JournalEntryCard key={`${entry.kind || 'entry'}-${entry.title || index}`} entry={entry} />)}
        </div>
      ) : (
        <DashboardEmptyState title="Журнал появится после запуска" description="Запустите агента, чтобы увидеть входные данные, выводы, правила и результат." />
      )}
      <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 px-3 py-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="text-sm font-semibold text-slate-950">Улучшение версии</div>
            <div className="mt-1 text-xs leading-5 text-slate-500">
              Правка, отклонение, плохой результат или ошибка сохраняются как обратная связь и создают новую версию со списком изменений. Активирует её человек.
            </div>
          </div>
          <span className="rounded-full bg-white px-2.5 py-1 text-xs font-medium text-slate-700 ring-1 ring-slate-200">
            версионное улучшение
          </span>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          {learningTriggerOptions.map((option) => (
            <Button
              key={option.value}
              type="button"
              size="sm"
              variant={feedbackTrigger === option.value ? 'default' : 'outline'}
              onClick={() => onFeedbackTriggerChange(option.value)}
            >
              {option.label}
            </Button>
          ))}
        </div>
        <div className="mt-3 grid gap-2 md:grid-cols-[1fr_auto]">
          <textarea
            className="min-h-20 resize-none rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400"
            value={feedbackText}
            onChange={(event) => onFeedbackTextChange(event.target.value)}
            placeholder="Что исправить в логике агента для следующей версии?"
          />
          <Button type="button" onClick={onSubmitFeedback} disabled={actionLoading || !feedbackText.trim()}>
            Зафиксировать улучшение
          </Button>
        </div>
      </div>
      {feedbackVersionNotice ? (
        <div className={cn('mt-3 rounded-xl border px-3 py-3 text-sm leading-6', noticeState === 'active' ? 'border-emerald-200 bg-emerald-50 text-emerald-900' : 'border-amber-200 bg-amber-50 text-amber-950')}>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="font-semibold">
                Candidate-версия {feedbackVersionNotice.version_number ? `v${feedbackVersionNotice.version_number}` : 'агента'} готова
              </div>
              <div className="mt-1 text-xs">
                {feedbackVersionNotice.trigger_label || 'Обратная связь'} · {noticeState === 'active' ? 'активирована' : noticeState === 'rolled_back' ? 'откат выполнен' : 'ждёт решения'}
              </div>
            </div>
            <StatusBadge status={noticeState === 'active' ? 'active' : noticeState === 'rolled_back' ? 'paused' : 'needs_approval'} />
          </div>
          <div className="mt-1">Правка: {feedbackVersionNotice.feedback}</div>
          {feedbackVersionNotice.diff?.summary ? (
            <div className="mt-1">Diff: {feedbackVersionNotice.diff.summary}</div>
          ) : null}
          {feedbackVersionNotice.diff?.changed_fields?.length ? (
            <div className="mt-2 flex flex-wrap gap-1">
              {feedbackVersionNotice.diff.changed_fields.slice(0, 5).map((field) => (
                <span key={`${noticeVersionId}-${field}`} className="rounded-full bg-white px-2 py-0.5 text-[11px] text-slate-700 ring-1 ring-slate-200">
                  {humanizeMeta(field)}
                </span>
              ))}
            </div>
          ) : null}
          <div className="mt-1 text-xs">{feedbackVersionNotice.next_run_note}</div>
          {noticeVersionId && noticeState === 'candidate' ? (
            <div className="mt-3 flex flex-wrap gap-2">
              <Button type="button" size="sm" onClick={() => onActivateFeedbackVersion(noticeVersionId)} disabled={actionLoading}>
                Активировать версию
              </Button>
            </div>
          ) : null}
          {noticeState === 'active' && previousVersionId ? (
            <div className="mt-3 flex flex-wrap gap-2">
              <Button type="button" size="sm" variant="outline" onClick={() => onRollbackFeedbackVersion(previousVersionId)} disabled={actionLoading}>
                Откатиться к прошлой версии
              </Button>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
};

export const buildJournalFromSections = (sections: AgentReviewSection[]) => sections.map((section) => ({
  kind: humanizeMeta(section.artifact_type || 'artifact'),
  title: section.title || 'Результат',
  status: section.status || 'completed',
  summary: section.summary || '',
  details: [],
  payload: section.payload || {},
}));

export const GenericRunProgress = ({
  category,
  review,
  activeRun,
  pendingApproval,
}: {
  category: string;
  review: AgentReview | null;
  activeRun: AgentRun | null;
  pendingApproval: AgentApproval | null;
}) => {
  const journal = review?.journal && review.journal.length ? review.journal : buildJournalFromSections(review?.sections || []);
  const stepStatuses = buildStepStatusMap(activeRun?.steps || []);
  const hasRunData = Boolean(activeRun || journal.length || review?.has_run);

  if (!hasRunData) {
    return null;
  }

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-slate-950">Путь {humanizeCategory(category).toLowerCase()}-агента</div>
          <div className="mt-1 text-sm leading-6 text-slate-600">
            Агент проходит понятный цикл: данные, понимание, результат и ручной контроль. Технические детали спрятаны ниже.
          </div>
        </div>
        {activeRun?.status || review?.run_status ? <StatusBadge status={activeRun?.status || review?.run_status || ''} /> : null}
      </div>
      <div className="mt-4 grid gap-3 lg:grid-cols-4">
        {genericRunStages.map((stage) => {
          const entry = findJournalEntryForGenericStage(journal, stage.kind);
          const stageStatus = getGenericStageStatus(stage.kind, entry, stepStatuses, pendingApproval);
          const detail = getGenericStageDetail(stage.kind, entry, category, pendingApproval);
          const Icon = stage.icon;
          return (
            <div
              key={stage.kind}
              className={cn(
                'rounded-xl border px-3 py-3',
                stageStatus === 'completed' || stageStatus === 'approved' || stageStatus === 'generated'
                  ? 'border-emerald-200 bg-emerald-50/60'
                  : stageStatus === 'waiting_approval' || stageStatus === 'pending'
                    ? 'border-amber-200 bg-amber-50/60'
                    : 'border-slate-200 bg-slate-50',
              )}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex min-w-0 items-center gap-2">
                  <span className={cn(
                    'flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white ring-1',
                    stageStatus === 'completed' || stageStatus === 'approved' || stageStatus === 'generated'
                      ? 'text-emerald-700 ring-emerald-200'
                      : stageStatus === 'waiting_approval' || stageStatus === 'pending'
                        ? 'text-amber-700 ring-amber-200'
                        : 'text-slate-500 ring-slate-200',
                  )}>
                    <Icon className="h-4 w-4" />
                  </span>
                  <div className="min-w-0">
                    <div className="text-sm font-semibold text-slate-950">{stage.title}</div>
                    <div className="mt-0.5 text-xs text-slate-500">{stage.description}</div>
                  </div>
                </div>
                {stageStatus ? <StatusBadge status={stageStatus} /> : null}
              </div>
              {detail ? <div className="mt-3 text-sm leading-6 text-slate-700">{detail}</div> : null}
            </div>
          );
        })}
      </div>
    </div>
  );
};

export const buildStepStatusMap = (steps: AgentRunStep[]) => {
  const statuses: Record<string, string> = {};
  steps.forEach((step) => {
    if (step.step_key && step.status) {
      statuses[step.step_key] = step.status;
    }
  });
  return statuses;
};

export const findJournalEntryForGenericStage = (journal: AgentJournalEntry[], kind: string) => {
  if (kind === 'approval') {
    return journal.find((entry) => entry.kind === 'approval');
  }
  return journal.find((entry) => entry.kind === kind);
};

export const getGenericStageStatus = (
  kind: string,
  entry: AgentJournalEntry | undefined,
  stepStatuses: Record<string, string>,
  pendingApproval: AgentApproval | null,
) => {
  if (kind === 'approval' && pendingApproval) {
    return 'waiting_approval';
  }
  if (entry?.status) {
    return entry.status;
  }
  if (kind === 'input') {
    return stepStatuses.collect_inputs || '';
  }
  if (kind === 'extraction') {
    return stepStatuses.extract_context || '';
  }
  if (kind === 'output') {
    return stepStatuses.prepare_output || '';
  }
  if (kind === 'approval') {
    return stepStatuses.approve_output || '';
  }
  return '';
};

export const getGenericStageDetail = (
  kind: string,
  entry: AgentJournalEntry | undefined,
  category: string,
  pendingApproval: AgentApproval | null,
) => {
  if (kind === 'input') {
    return findJournalDetailValue(entry, 'Подключено источников') || findJournalDetailValue(entry, 'Источники') || 'Данные агента подключены к запуску.';
  }
  if (kind === 'extraction') {
    return findJournalDetailValue(entry, 'Извлечено элементов') || findJournalDetailValue(entry, 'Что обработано') || entry?.summary || 'Агент разобрал источники.';
  }
  if (kind === 'output') {
    return getOutputStageDetail(entry, category);
  }
  if (kind === 'approval') {
    if (pendingApproval) {
      return explainApproval(pendingApproval);
    }
    return findJournalDetailValue(entry, 'Статус') || entry?.summary || 'Решения сохранены в журнале.';
  }
  return '';
};

export const getOutputStageDetail = (entry: AgentJournalEntry | undefined, category: string) => {
  if (!entry) {
    return 'Результат появится после запуска.';
  }
  if (category === 'documents') {
    return compactJoin([
      labelCount('Фактов', findJournalDetailValue(entry, 'Фактов')),
      labelCount('Рисков', findJournalDetailValue(entry, 'Рисков')),
      findJournalDetailValue(entry, 'Внешняя отправка'),
    ]);
  }
  if (category === 'email') {
    return compactJoin([
      findJournalDetailValue(entry, 'Тема письма'),
      labelCount('Пунктов чеклиста', findJournalDetailValue(entry, 'Чеклист')),
      findJournalDetailValue(entry, 'Внешняя отправка'),
    ]);
  }
  if (category === 'tables') {
    return compactJoin([
      labelCount('Исключений', findJournalDetailValue(entry, 'Исключений')),
      labelCount('Строк к проверке', findJournalDetailValue(entry, 'Строк к проверке')),
      findJournalDetailValue(entry, 'Внешняя отправка'),
    ]);
  }
  if (category === 'reviews') {
    return compactJoin([
      labelCount('Черновиков ответов', findJournalDetailValue(entry, 'Черновиков ответов')),
      labelCount('Причин ручной проверки', findJournalDetailValue(entry, 'Причин ручной проверки')),
      findJournalDetailValue(entry, 'Публикация'),
    ]);
  }
  return entry.summary || 'Агент подготовил результат.';
};

export const labelCount = (label: string, value: string) => (value ? `${label}: ${value}` : '');
export const compactJoin = (items: string[]) => items.filter((item) => item.trim()).join(' · ');

export const OutreachRunProgress = ({ review, activeRun }: { review: AgentReview | null; activeRun: AgentRun | null }) => {
  const journal = review?.journal && review.journal.length ? review.journal : [];
  const completedStepKeys = new Set((activeRun?.steps || []).filter((step) => step.status === 'completed').map((step) => step.step_key));
  const hasAnyStage = outreachProgressStages.some((stage) => journal.some((entry) => entry.kind === stage.kind));

  if (!activeRun && !hasAnyStage) {
    return null;
  }

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-slate-950">Путь outreach-агента</div>
          <div className="mt-1 text-sm leading-6 text-slate-600">
            Агент проходит этапы по порядку: лиды, shortlist, черновики и безопасная очередь.
          </div>
        </div>
        {activeRun?.status ? <StatusBadge status={activeRun.status} /> : null}
      </div>
      <div className="mt-4 grid gap-3 lg:grid-cols-4">
        {outreachProgressStages.map((stage) => {
          const entry = journal.find((item) => item.kind === stage.kind);
          const detailValue = findJournalDetailValue(entry, stage.detailLabel);
          const boundary = stage.kind === 'queue' ? findJournalDetailValue(entry, 'Внешняя отправка') : '';
          const isDone = Boolean(entry) || (
            stage.kind === 'sourcing' && completedStepKeys.has('source_leads')
          ) || (
            stage.kind === 'shortlist' && completedStepKeys.has('shortlist')
          ) || (
            stage.kind === 'drafts' && completedStepKeys.has('draft_messages')
          ) || (
            stage.kind === 'queue' && completedStepKeys.has('send_limited_batch')
          );
          const Icon = stage.icon;
          return (
            <div
              key={stage.kind}
              className={cn(
                'rounded-xl border px-3 py-3',
                isDone ? 'border-emerald-200 bg-emerald-50/60' : 'border-slate-200 bg-slate-50',
              )}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex min-w-0 items-center gap-2">
                  <span className={cn(
                    'flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ring-1',
                    isDone ? 'bg-white text-emerald-700 ring-emerald-200' : 'bg-white text-slate-500 ring-slate-200',
                  )}>
                    <Icon className="h-4 w-4" />
                  </span>
                  <div className="min-w-0">
                    <div className="text-sm font-semibold text-slate-950">{stage.title}</div>
                    <div className="mt-0.5 text-xs text-slate-500">{isDone ? 'готово' : 'ещё не выполнено'}</div>
                  </div>
                </div>
                {entry?.status ? <StatusBadge status={entry.status} /> : null}
              </div>
              <div className="mt-3 text-sm font-semibold text-slate-950">{detailValue || '0'}</div>
              {entry?.summary ? <div className="mt-1 line-clamp-2 text-xs leading-5 text-slate-600">{entry.summary}</div> : null}
              {boundary ? <div className="mt-2 rounded-lg bg-white px-2 py-1.5 text-xs font-medium text-amber-700 ring-1 ring-amber-200">{boundary}</div> : null}
            </div>
          );
        })}
      </div>
    </div>
  );
};

export const findJournalDetailValue = (entry: AgentJournalEntry | undefined, label: string) => {
  if (!entry || !Array.isArray(entry.details)) {
    return '';
  }
  const detail = entry.details.find((item) => item.label === label);
  return detail?.value || '';
};

export const JournalEntryCard = ({ entry }: { entry: AgentJournalEntry }) => {
  const payload = entry.payload || {};
  const details = Array.isArray(entry.details) ? entry.details : [];
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full bg-white px-2 py-1 text-xs font-medium text-slate-600 ring-1 ring-slate-200">
              {humanizeMeta(entry.kind || 'step')}
            </span>
            <div className="text-sm font-semibold text-slate-950">{entry.title || 'Шаг запуска'}</div>
          </div>
          {entry.summary ? <div className="mt-2 text-sm leading-6 text-slate-600">{userFacingAgentTechText(entry.summary)}</div> : null}
        </div>
        {entry.status ? <StatusBadge status={entry.status} /> : null}
      </div>
      {details.length ? (
        <div className="mt-3 grid gap-2 md:grid-cols-2">
          {details.map((detail) => (
            <div key={`${detail.label || ''}-${detail.value || ''}`} className="rounded-lg bg-white px-3 py-2 text-xs leading-5 ring-1 ring-slate-200">
              <div className="font-medium text-slate-950">{detail.label || 'Деталь'}</div>
              <div className="mt-1 text-slate-600">{detail.value || ''}</div>
            </div>
          ))}
        </div>
      ) : null}
      <HumanPayloadView payload={payload} />
      <details className="mt-3">
        <summary className="cursor-pointer text-xs font-medium text-slate-500 hover:text-slate-900">Технический журнал</summary>
        <pre className="mt-2 max-h-72 overflow-auto rounded-lg bg-slate-950 p-3 text-[11px] leading-5 text-slate-100">
          {JSON.stringify(payload, null, 2)}
        </pre>
      </details>
    </div>
  );
};

export const HumanPayloadView = ({ payload }: { payload: Record<string, unknown> }) => {
  const result = toRecordOrNull(payload.result);
  const items = Array.isArray(payload.items) ? payload.items : [];
  const missing = Array.isArray(payload.missing_information) ? payload.missing_information : [];
  const provenance = Array.isArray(payload.provenance) ? payload.provenance : [];

  return (
    <div className="mt-3 space-y-2 text-xs leading-5 text-slate-700">
      {missing.length ? (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-2 py-2 text-amber-800">
          Нужно уточнить: {missing.map((item) => String(item)).join(', ')}
        </div>
      ) : null}
      {provenance.length ? (
        <div className="rounded-lg bg-white px-2 py-2 ring-1 ring-slate-200">
          Источники: {provenance.map((item) => String(item)).join(', ')}
        </div>
      ) : null}
      {items.length ? (
        <div className="space-y-1">
          {items.slice(0, 3).map((item, index) => (
            <div key={`payload-item-${index}`} className="rounded-lg bg-white px-2 py-2 ring-1 ring-slate-200">
              {formatPayloadItem(item)}
            </div>
          ))}
        </div>
      ) : null}
      {result ? <HumanResultView result={result} /> : null}
    </div>
  );
};

export const toRecordOrNull = (value: unknown): Record<string, unknown> | null => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return null;
  }
  return Object.fromEntries(Object.entries(value));
};

type HumanResultPrimaryItem = {
  label: string;
  text: string;
  context?: string;
};

const nonEmptyText = (value: unknown) => String(value || '').trim();

const resultReplyDraftValues = (result: Record<string, unknown>): unknown[] => {
  if (Array.isArray(result.reply_drafts)) return result.reply_drafts;
  return toRecordOrNull(result.reply_drafts) ? [result.reply_drafts] : [];
};

const resultPrimaryItems = (result: Record<string, unknown>): HumanResultPrimaryItem[] => {
  const replyDrafts = resultReplyDraftValues(result);
  const replies = replyDrafts.flatMap((value, index) => {
    if (typeof value === 'string' && value.trim()) {
      return [{
        label: replyDrafts.length > 1 ? `Готовый ответ ${index + 1}` : 'Готовый ответ',
        text: value.trim(),
      }];
    }
    const item = toRecordOrNull(value);
    if (!item) return [];
    const text = nonEmptyText(item.reply || item.draft_text || item.text || item.message || item.body);
    if (!text) return [];
    const context = nonEmptyText(item.review_text || item.review || item.recipient || item.author_name);
    return [{
      label: replyDrafts.length > 1 ? `Готовый ответ ${index + 1}` : 'Готовый ответ',
      text,
      context: context ? `Для: ${context}` : undefined,
    }];
  });
  if (replies.length) return replies;

  const directCandidates = [
    { key: 'post_text', label: 'Готовый текст поста' },
    { key: 'draft_text', label: 'Готовый черновик' },
    { key: 'reply', label: 'Готовый ответ' },
    { key: 'body', label: 'Готовое письмо' },
    { key: 'message', label: 'Готовое сообщение' },
    { key: 'text', label: 'Готовый результат' },
  ];
  for (const candidate of directCandidates) {
    const text = nonEmptyText(result[candidate.key]);
    if (!text) continue;
    const subject = candidate.key === 'body' ? nonEmptyText(result.subject) : '';
    return [{ label: candidate.label, text, context: subject ? `Тема: ${subject}` : undefined }];
  }
  return [];
};

const resultDestination = (result: Record<string, unknown>) => {
  const savedDestination = toRecordOrNull(result.saved_destination) || {};
  const urlKeys = ['content_plan_url', 'localos_url', 'result_url', 'item_url', 'message_url', 'telegram_url', 'url'];
  let url = '';
  for (const key of urlKeys) {
    url = nonEmptyText(savedDestination[key] || result[key]);
    if (url) break;
  }
  if (url && !url.startsWith('/') && !url.startsWith('https://') && !url.startsWith('http://')) {
    url = '';
  }
  const status = nonEmptyText(savedDestination.status || result.destination_status || result.status).toLowerCase();
  const provider = nonEmptyText(savedDestination.provider || result.provider).toLowerCase();
  const externalDispatchPerformed = result.external_dispatch_performed === true || savedDestination.external_dispatch_performed === true;
  const localWritePerformed = result.localos_write_performed === true || savedDestination.localos_write_performed === true;
  const isContentPlan = Boolean(savedDestination.content_plan_url) || url.includes('/dashboard/content');
  const isReviews = url.includes('/dashboard/card') && url.includes('tab=reviews');
  const isTelegram = provider === 'telegram' || url.includes('t.me/') || url.includes('telegram');
  const isSaved = status === 'draft_saved' || localWritePerformed || Boolean(url && !isTelegram);

  if (status === 'needs_future_date') {
    return {
      tone: 'warning',
      title: 'Результат пока не сохранён',
      detail: nonEmptyText(savedDestination.message) || 'Выберите новую дату для сохранения результата.',
      url: '',
      cta: '',
    };
  }
  if (isContentPlan) {
    return {
      tone: 'success',
      title: 'Черновик сохранён в контент-план',
      detail: nonEmptyText(savedDestination.scheduled_for) ? `Дата: ${nonEmptyText(savedDestination.scheduled_for)}` : 'Результат находится в разделе «Контент».',
      url,
      cta: 'Открыть в контент-плане',
    };
  }
  if (isReviews) {
    return {
      tone: 'success',
      title: 'Черновик сохранён в разделе «Отзывы»',
      detail: 'Публикация не выполнялась. Проверьте ответ перед использованием.',
      url,
      cta: 'Открыть отзывы',
    };
  }
  if (isTelegram && externalDispatchPerformed) {
    return {
      tone: 'success',
      title: 'Сообщение отправлено в Telegram',
      detail: 'Отправка выполнена после подтверждения.',
      url,
      cta: 'Открыть сообщение',
    };
  }
  if (isTelegram) {
    return {
      tone: 'neutral',
      title: 'Сообщение подготовлено, но не отправлено',
      detail: 'Проверьте текст перед отправкой в Telegram.',
      url,
      cta: url ? 'Открыть черновик' : '',
    };
  }
  if (isSaved) {
    return {
      tone: 'success',
      title: 'Результат сохранён в LocalOS',
      detail: 'Откройте запись, чтобы продолжить работу с результатом.',
      url,
      cta: url ? 'Открыть сохранённый результат' : '',
    };
  }
  return null;
};

export const HumanResultView = ({
  result,
  resultState,
}: {
  result: Record<string, unknown>;
  resultState?: 'missing' | 'prepared' | 'saved' | 'blocked';
}) => {
  const savedDestination = toRecordOrNull(result.saved_destination);
  const destinationStatus = String(savedDestination?.status || '').toLowerCase();
  const primaryItems = resultPrimaryItems(result);
  const destination = resultDestination(result);
  const technicalKeys = new Set([
    'status', 'schema', 'provider', 'capability', 'trace_id', 'run_id', 'step_id', 'source_run_id',
    'external_dispatch_performed', 'dispatch_state', 'raw', 'payload', 'metadata', 'sentiment',
    'localos_write_performed', 'provider_write_performed', 'destination_status',
    'technical_reason', 'error_code', 'provider_error', 'provider_error_message', 'llm_error',
    'analysis_source', 'analysis_prompt_key', 'analysis_prompt_version', 'llm_analysis_used',
    'feedback_notes', 'format',
    'content_plan_url', 'localos_url', 'result_url', 'item_url', 'message_url', 'telegram_url', 'url',
  ]);
  const hasBusinessValue = (key: string, value: unknown) => {
    if (key === 'sentiment' && String(value || '').toLowerCase() === 'unknown') return false;
    if (
      (key === 'delivery_state' || key === 'publish_state')
      && ['not_dispatched', 'not_published', 'not_sent'].includes(String(value || '').toLowerCase())
    ) return false;
    if (technicalKeys.has(key) || key.endsWith('_json') || key.endsWith('_id')) return false;
    if (Array.isArray(value) && value.length === 0) return false;
    if (value && typeof value === 'object' && !Array.isArray(value) && Object.keys(value).length === 0) return false;
    return value !== '' && value !== null && value !== undefined;
  };
  const consumedKeys = new Set([
    'saved_destination', 'title', 'draft_text', 'post_text', 'reply', 'message', 'text', 'body', 'subject',
    'reply_drafts', 'manual_review_reasons', 'manual_review_reason', 'rules_applied',
    'preparation_method', 'summary', 'risks', 'facts', 'fields', 'next_questions', 'checklist', 'exceptions',
    'rows_to_review', 'recommendations', 'provenance', 'delivery_state', 'publish_state',
  ]);
  const entries = Object.entries(result).filter(([key, value]) => !consumedKeys.has(key) && hasBusinessValue(key, value));
  const secondaryKeys = [
    'preparation_method',
    'summary',
    'risks',
    'facts',
    'fields',
    'next_questions',
    'checklist',
    'exceptions',
    'rows_to_review',
    'recommendations',
    'provenance',
    'delivery_state',
    'publish_state',
  ];
  const secondaryEntries = secondaryKeys
    .map((key) => ({ key, value: result[key] }))
    .filter((entry) => hasBusinessValue(entry.key, entry.value));
  const nestedReviewReasons = resultReplyDraftValues(result)
    .map((value) => toRecordOrNull(value))
    .map((value) => nonEmptyText(value?.manual_review_reason))
    .filter(Boolean);
  const reviewReason = nonEmptyText(result.manual_review_reason)
    || (Array.isArray(result.manual_review_reasons) ? result.manual_review_reasons.map(nonEmptyText).filter(Boolean).join(' ') : '')
    || nestedReviewReasons.join(' ');
  const resultTitle = nonEmptyText(result.title);
  return (
    <div className="space-y-4">
      {resultTitle ? <div className="text-sm font-semibold text-slate-700">{resultTitle}</div> : null}

      {primaryItems.length ? (
        <section className="overflow-hidden rounded-xl bg-white shadow-[0_8px_24px_rgba(15,23,42,0.06),0_0_0_1px_rgba(15,23,42,0.1)]">
          {primaryItems.map((item, index) => (
            <div key={`${item.label}-${index}`} className={cn('px-4 py-4 sm:px-5', index > 0 && 'border-t border-slate-100')}>
              <div className="text-xs font-semibold uppercase text-emerald-700">{item.label}</div>
              {item.context ? <div className="mt-2 text-xs leading-5 text-slate-500">{item.context}</div> : null}
              <div className="mt-2 whitespace-pre-wrap text-base font-medium leading-7 text-slate-950 [text-wrap:pretty]">{item.text}</div>
            </div>
          ))}
        </section>
      ) : null}

      {destination ? (
        <div className={cn(
          'rounded-xl px-4 py-3 text-sm leading-6 shadow-[inset_0_0_0_1px_rgba(15,23,42,0.08)]',
          destination.tone === 'success' && 'bg-emerald-50 text-emerald-950',
          destination.tone === 'warning' && 'bg-amber-50 text-amber-950',
          destination.tone === 'neutral' && 'bg-sky-50 text-slate-900',
        )}>
          <div className="font-semibold">{destination.title}</div>
          <div className="mt-1">{destination.detail}</div>
          {destination.url && destination.cta ? (
            <a className="mt-2 inline-flex min-h-10 items-center gap-2 font-semibold underline underline-offset-4" href={destination.url} target={destination.url.startsWith('http') ? '_blank' : undefined} rel={destination.url.startsWith('http') ? 'noreferrer' : undefined}>
              {destination.cta}
              <ExternalLink className="h-4 w-4" />
            </a>
          ) : null}
        </div>
      ) : null}

      {!destination && primaryItems.length && resultState ? (
        <div className="rounded-xl bg-slate-100 px-4 py-3 text-sm leading-6 text-slate-700">
          {resultState === 'saved'
            ? 'Результат сохранён в истории этой работы.'
            : resultState === 'blocked'
              ? 'Результат подготовлен, но следующий шаг остановлен до вашего решения.'
              : 'Результат подготовлен и сохранён в истории. Наружу ничего не отправлялось.'}
        </div>
      ) : null}

      {reviewReason ? (
        <div className="rounded-xl bg-amber-50 px-4 py-3 text-sm leading-6 text-amber-950 shadow-[inset_0_0_0_1px_rgba(217,119,6,0.18)]">
          <div className="font-semibold">Проверьте перед использованием</div>
          <div className="mt-1">{reviewReason}</div>
        </div>
      ) : null}

      {secondaryEntries.length ? (
        <div className="divide-y divide-slate-100 rounded-xl bg-white px-4 shadow-[inset_0_0_0_1px_rgba(15,23,42,0.08)]">
          {secondaryEntries.slice(0, 5).map(({ key, value }) => (
            <div key={key} className="py-3">
              <div className="text-xs font-semibold uppercase text-slate-500">{resultFieldLabels[key] || humanizeMeta(key)}</div>
              <div className="mt-1 text-sm leading-6 text-slate-700">{formatPayloadValue(value)}</div>
            </div>
          ))}
        </div>
      ) : null}

      {primaryItems.length ? null : entries.length ? (
        <div className="rounded-xl bg-white px-4 py-3 text-sm leading-6 text-slate-700 shadow-[inset_0_0_0_1px_rgba(15,23,42,0.08)]">
          {entries.slice(0, 5).map(([key, value]) => (
            <div key={key} className="mt-2 first:mt-0">
              <span className="font-semibold text-slate-950">{humanizeMeta(key)}:</span> {formatPayloadValue(value)}
            </div>
          ))}
        </div>
      ) : null}

      {primaryItems.length || entries.length || destinationStatus === 'needs_future_date' ? null : (
        <div className="rounded-xl bg-white px-4 py-3 text-sm leading-6 text-slate-600 shadow-[inset_0_0_0_1px_rgba(15,23,42,0.08)]">
          Агент завершил шаги, но не сохранил отдельный бизнес-результат. Откройте технические детали запуска для диагностики.
        </div>
      )}

      {result.rules_applied ? (
        <details>
          <summary className="min-h-10 cursor-pointer py-2 text-sm font-medium text-slate-500 hover:text-slate-900">Как агент подготовил результат</summary>
          <div className="pb-2 text-sm leading-6 text-slate-600">{formatPayloadValue(result.rules_applied)}</div>
        </details>
      ) : null}
    </div>
  );
};

export const formatPayloadItem = (value: unknown) => {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    const entries = Object.entries(value).filter(([, itemValue]) => itemValue !== '' && itemValue !== null && itemValue !== undefined);
    return entries.slice(0, 3).map(([key, itemValue]) => `${humanizeMeta(key)}: ${formatPayloadValue(itemValue)}`).join(' · ');
  }
  return formatPayloadValue(value);
};

export const formatPayloadValue = (value: unknown): string => {
  if (Array.isArray(value)) {
    return value.slice(0, 4).map((item) => formatPayloadValue(item)).join(', ');
  }
  if (value && typeof value === 'object') {
    const entries = Object.entries(value).filter(([, itemValue]) => itemValue !== '' && itemValue !== null && itemValue !== undefined);
    return entries.slice(0, 3).map(([key, itemValue]) => `${humanizeMeta(key)}: ${formatPayloadValue(itemValue)}`).join('; ');
  }
  return String(value ?? '');
};

export const AgentRunObservabilityPanel = ({
  run,
  activationGate,
  actionLoading,
  onPreviewNextStepAction,
  onActivateVersion,
  onApplyFinanceRequests,
}: {
  run: AgentRun;
  activationGate?: AgentActivationGate;
  actionLoading: boolean;
  onPreviewNextStepAction: (nextStep: string) => void;
  onActivateVersion: (versionId: string) => void;
  onApplyFinanceRequests: (runId: string) => void;
}) => {
  const [downloading, setDownloading] = useState(false);
  const observability = run.observability || {};
  const billingLedger = observability.billing_ledger || {};
  const unifiedBillingLedger = observability.unified_billing_ledger || {};
  const billingSummary = unifiedBillingLedger.summary || {};
  const billingActions = billingLedger.actions || [];
  const billingEntries = billingLedger.entries || [];
  const delivery = observability.delivery_status || {};
  const sourceChain = observability.source_result_chain || {};
  const sourceReadValue = sourceChain.provider_read_performed
    ? 'реально'
    : sourceChain.provider_read_attempted
      ? 'пример'
      : 'не было';
  const sourceReadHint = sourceChain.provider_read_performed
    ? `${sourceChain.rows_returned_count || 0} строк из таблицы`
    : sourceChain.provider_read_attempted
      ? 'нет подтверждённого чтения Google Sheets'
      : `${sourceChain.rows_returned_count || 0} строк`;
  const sourceProofValue = sourceChain.chain_verified
    ? 'доказано'
    : sourceChain.result_generated
      ? 'не доказано'
      : 'нет результата';
  const sourceProofHint = sourceChain.chain_verified
    ? 'источник → результат связан'
    : sourceChain.blocker_code === 'SOURCE_NOT_VERIFIED'
      ? 'результат есть, но источник не подтверждён'
      : sourceChain.result_generated
        ? 'проверьте источник'
        : 'результат не собран';
  const ledgerItems = observability.action_ledger?.items || [];
  const domainRequests = observability.domain_requests?.items || [];
  const errors = observability.errors || [];
  const recoveryActions = observability.recovery_actions || [];
  const runInput = run.input_json && typeof run.input_json === 'object' ? run.input_json : {};
  const rawSupportEndpoint = observability.support_export?.endpoint || `/api/agent-runs/${run.id}/support-export`;
  const supportEndpoint = rawSupportEndpoint.startsWith('/api/') ? rawSupportEndpoint.slice(4) : rawSupportEndpoint;

  const downloadSupportExport = async () => {
    setDownloading(true);
    try {
      const response = await api.get(supportEndpoint, {
        params: { format: 'json' },
      });
      const content = JSON.stringify(response.data, null, 2);
      const blob = new Blob([content], { type: 'application/json;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `agent-run-${run.id}-support.json`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className="mt-4 space-y-4">
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
        <AgentObservabilityMetric icon={Activity} label="История запуска" value={run.status} hint={`${observability.step_history?.count || run.steps?.length || 0} шагов`} />
        <AgentObservabilityMetric
          icon={ReceiptText}
          label="Списания"
          value={formatBillingActualSummary(unifiedBillingLedger)}
          hint={`оценка ${formatBillingEstimateSummary({ summary: billingSummary })}`}
        />
        <AgentObservabilityMetric icon={Send} label="Доставка" value={humanizeMeta(delivery.state || 'not_applicable')} hint={`${delivery.attempts_success || 0}/${delivery.attempts_total || 0} попыток`} />
        <AgentObservabilityMetric icon={ShieldCheck} label="Подтверждения" value={String(observability.domain_requests?.pending || observability.approvals?.pending || 0)} hint={`${observability.domain_requests?.count || 0} запросов`} />
        <AgentObservabilityMetric icon={AlertTriangle} label="Ошибки" value={String(errors.length)} hint={errors.length ? 'нужна проверка' : 'нет ошибок'} />
      </div>

      <PreviewRunSummaryPanel
        summary={observability.preview_summary}
        runInput={runInput}
        activationGate={activationGate}
        actionLoading={actionLoading}
        onNextStepAction={onPreviewNextStepAction}
        onActivateVersion={onActivateVersion}
      />

      <div className="rounded-2xl bg-white p-4 shadow-[0_0_0_1px_rgba(15,23,42,0.08)]">
        <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Source To Result</div>
        <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <AgentObservabilityMetric icon={Database} label="Источник" value={sourceChain.source_step_present ? 'есть' : 'нет'} hint={sourceChain.provider_connected ? 'подключение готово' : 'подключение не подтверждено'} />
          <AgentObservabilityMetric icon={ArrowDownUp} label="Чтение" value={sourceReadValue} hint={sourceReadHint} />
          <AgentObservabilityMetric icon={FileText} label="Связка" value={sourceProofValue} hint={sourceProofHint} />
          <AgentObservabilityMetric icon={AlertTriangle} label="Blocker" value={String(sourceChain.blocker_code || 'none')} hint="где оборвалась цепочка" />
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-5">
        <RunColumn title="Журнал действий" icon={ReceiptText}>
          {ledgerItems.map((item) => (
            <TimelineItem
              key={item.action_id || item.trace_id || item.capability || 'action'}
              title={item.capability || item.action_id || 'Действие'}
              meta={item.action_id || 'действие агента'}
              status={item.status || (item.error ? 'failed' : 'linked')}
            />
          ))}
        </RunColumn>
		        <RunColumn title="Списания" icon={ReceiptText}>
	          {(unifiedBillingLedger.items || []).map((item) => (
	            <TimelineItem
	              key={item.key || item.label || 'unified-billing'}
	              title={item.label || humanizeMeta(item.key || 'billing')}
	              meta={`оценка ${formatBillingEstimateValue(item)} · факт ${formatBillingActualValue(item)}`}
	              status={item.status || 'billing'}
	            />
	          ))}
	          {billingActions.map((item) => (
	            <BillingActionItem key={item.action_id || item.capability || 'billing'} item={item} />
	          ))}
          {billingEntries.slice(0, 3).map((entry, index) => (
            <TimelineItem
              key={`${entry.action_id || 'entry'}-${entry.entry_type || index}-${entry.created_at || index}`}
              title={humanizeMeta(entry.entry_type || 'billing_entry')}
              meta={`${entry.action_id || entry.capability || 'действие'} · ${entry.cost ? `${entry.cost} кр.` : 'без списания'}`}
              status={entry.entry_type || 'billing'}
            />
          ))}
        </RunColumn>
        <RunColumn title="Ожидают подтверждения" icon={ShieldCheck}>
          {domainRequests.map((item) => (
            <DomainRequestItem
              key={`${item.kind || 'request'}-${item.id || item.action_id || item.review_id || item.title}`}
              item={item}
              runId={run.id}
              actionLoading={actionLoading}
              onApplyFinanceRequests={onApplyFinanceRequests}
            />
          ))}
        </RunColumn>
        <RunColumn title="Ошибки и статусы" icon={AlertTriangle}>
          {errors.map((item, index) => (
            <TimelineItem
              key={`${item.source || 'error'}-${item.action_id || item.step_key || index}`}
              title={item.error_text || item.step_key || item.action_id || 'Ошибка выполнения'}
              meta={item.source || item.status || 'выполнение агента'}
              status={item.status || 'failed'}
            />
          ))}
        </RunColumn>
        <RunColumn title="Recovery / support" icon={LifeBuoy}>
          {recoveryActions.map((item) => (
            <TimelineItem key={item.code || item.label || 'recovery'} title={item.label || item.code || 'Recovery action'} meta={item.target || 'support boundary'} status="needs_approval" />
          ))}
          <Button type="button" variant="outline" size="sm" onClick={downloadSupportExport} disabled={downloading}>
            {downloading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Download className="mr-2 h-4 w-4" />}
            Support export
          </Button>
        </RunColumn>
      </div>
    </div>
  );
};

export const DomainRequestItem = ({
  item,
  runId,
  actionLoading,
  onApplyFinanceRequests,
}: {
  item: NonNullable<NonNullable<AgentRunObservability['domain_requests']>['items']>[number];
  runId: string;
  actionLoading: boolean;
  onApplyFinanceRequests: (runId: string) => void;
}) => {
  const isFinanceRequest = item.kind === 'finance_transaction_request';
  const canApplyFinance = isFinanceRequest && item.can_apply === true && item.apply_state === 'apply_ready';
  const detailEntries = [
    item.why_waiting ? ['why_waiting', item.why_waiting] : null,
    isFinanceRequest ? ['finance_rows', {
      prepared: item.proposal_count || item.rows_total || 0,
      imported: item.rows_imported || 0,
      skipped: item.rows_skipped || 0,
      failed: item.rows_failed || 0,
    }] : null,
    item.limits ? ['limits', item.limits] : null,
    item.consent ? ['consent', item.consent] : null,
    item.delivery_journal ? ['delivery_journal', item.delivery_journal] : null,
    item.publish_requests ? ['publish_requests', item.publish_requests] : null,
    item.provider_handoff ? ['provider_handoff', item.provider_handoff] : null,
    item.error ? ['error', item.error] : null,
    item.row_values?.length ? ['row_values', item.row_values] : null,
    item.visual_diff?.length ? ['visual_diff', item.visual_diff] : null,
    item.suggestions?.length ? ['suggestions', item.suggestions] : null,
  ].filter((entry): entry is [string, unknown] => Boolean(entry));
  return (
    <div className="rounded-xl bg-white px-3 py-3 shadow-sm ring-1 ring-slate-200">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="truncate text-sm font-medium text-slate-900">{item.title || humanizeMeta(item.kind || 'domain request')}</div>
          <div className="mt-1 text-xs text-slate-500">{item.summary || item.id || 'domain request'}</div>
        </div>
        <StatusBadge status={item.approval_state || item.apply_state || item.delivery_state || item.status || 'pending'} />
      </div>
      {detailEntries.length ? (
        <div className="mt-2 space-y-1 text-xs leading-5 text-slate-600">
          {detailEntries.slice(0, 3).map(([key, value]) => (
            <div key={key}>
              <span className="font-medium text-slate-800">{humanizeMeta(key)}:</span> {formatPayloadValue(value)}
            </div>
          ))}
        </div>
      ) : null}
      {canApplyFinance ? (
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <Button
            type="button"
            size="sm"
            onClick={() => onApplyFinanceRequests(runId)}
            disabled={actionLoading}
          >
            {actionLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <ReceiptText className="mr-2 h-4 w-4" />}
            Применить в финансы
          </Button>
          <span className="text-[11px] leading-4 text-slate-500">
            Запись в LocalOS Finance выполнится только после этого действия.
          </span>
        </div>
      ) : null}
    </div>
  );
};

export const AgentObservabilityMetric = ({
  icon: Icon,
  label,
  value,
  hint,
}: {
  icon: typeof Clock3;
  label: string;
  value: string;
  hint: string;
}) => (
  <div className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3">
    <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-slate-500">
      <Icon className="h-4 w-4" />
      {label}
    </div>
    <div className="mt-2 text-lg font-semibold text-slate-950">{value}</div>
    <div className="mt-1 text-xs text-slate-500">{hint}</div>
  </div>
);

export const PreviewRunSummaryPanel = ({
  summary,
  runInput,
  activationGate,
  currentActiveVersionId = '',
  actionLoading = false,
  onNextStepAction,
  onActivateVersion,
}: {
  summary?: Record<string, unknown>;
  runInput: Record<string, unknown>;
  activationGate?: AgentActivationGate;
  currentActiveVersionId?: string;
  actionLoading?: boolean;
  onNextStepAction?: (nextStep: string) => void;
  onActivateVersion?: (versionId: string) => void;
}) => {
  const inputPreviewContext = runInput.preview_context && typeof runInput.preview_context === 'object' ? toRecordOrNull(runInput.preview_context) || {} : {};
  const isPreview = Boolean(summary?.is_preview || runInput.preview_mode);
  if (!isPreview) {
    return null;
  }
  const dataSources = Array.isArray(summary?.data_sources)
    ? summary.data_sources.map((item) => String(item || '')).filter(Boolean)
    : [];
  const completedSteps = Array.isArray(summary?.completed_steps)
    ? summary.completed_steps.map((item) => String(item || '')).filter(Boolean)
    : [];
  const artifacts = Array.isArray(summary?.artifacts) ? summary.artifacts : [];
  const pendingApprovalsValue = summary?.pending_approvals;
  const waitingActionsValue = summary?.waiting_actions;
  const pendingApprovals = Array.isArray(pendingApprovalsValue) ? pendingApprovalsValue : [];
  const waitingActions = Array.isArray(waitingActionsValue) ? waitingActionsValue : [];
  const summaryActionPlan = Array.isArray(summary?.openclaw_action_plan) ? summary.openclaw_action_plan : [];
  const inputActionPlan = Array.isArray(runInput.openclaw_action_plan) ? runInput.openclaw_action_plan : [];
  const openClawActionPlan = summaryActionPlan.length ? summaryActionPlan : inputActionPlan;
  const policyEnvelope = toRecordOrNull(summary?.policy_envelope) || toRecordOrNull(runInput.policy_envelope) || {};
  const approvalGate = toRecordOrNull(summary?.approval_gate) || {};
  const providerBindings = Array.isArray(runInput.provider_bindings) ? runInput.provider_bindings : [];
  const understoodTask = String(summary?.understood_task || objectValue(inputPreviewContext, 'understood_task') || objectValue(runInput, 'goal') || 'LocalOS проверяет агента на безопасном примере.');
  const manualControl = String(summary?.manual_control || objectValue(inputPreviewContext, 'manual_control') || 'Перед внешним действием нужен approval.');
  const safePreview = summary?.safe_preview !== false && runInput.external_side_effects_allowed === false;
  const nextStep = String(summary?.next_step || 'review_preview');
  const nextStepLabel = String(summary?.next_step_label || 'Проверить preview');
  const nextStepDescription = String(summary?.next_step_description || summary?.activation_hint || 'Проверьте результат preview и следующий шаг агента.');
  const activationVersionId = String(activationGate?.active_version_id || runInput.blueprint_version_id || '');
  const isCurrentVersionAlreadyActive = Boolean(activationVersionId && currentActiveVersionId && activationVersionId === currentActiveVersionId);
  const canActivateFromPreview = activationGate?.can_activate === true && Boolean(activationVersionId);
  const needsHumanDecision = pendingApprovals.length > 0 || waitingActions.length > 0 || nextStep === 'review_approvals';
  const sourceEvent = toRecordOrNull(runInput.source_event) || {};
  const eventType = String(sourceEvent.event_type || runInput.trigger || 'manual.preview');
  const compiledStepsValue = objectValue(inputPreviewContext, 'steps');
  const compiledSteps = Array.isArray(compiledStepsValue) ? compiledStepsValue : [];
  const simulationSteps = [
    {
      key: 'input',
      title: 'Входные данные',
      status: safePreview ? 'completed' : 'pending',
      detail: eventType,
    },
    {
      key: 'preflight',
      title: 'Проверка доступов',
      status: summary?.preflight_ready === false ? 'blocked' : 'completed',
      detail: summary?.preflight_ready === false ? 'нужны подключения' : 'подключения, лимиты и правила безопасности проверены',
    },
    {
      key: 'workflow',
      title: 'Проверенная логика',
      status: completedSteps.length ? 'completed' : 'pending',
      detail: completedSteps.length
        ? `${completedSteps.length} шагов выполнено`
        : compiledSteps.length
        ? `${compiledSteps.length} шагов в плане`
        : 'шаги появятся после запуска',
    },
    {
      key: 'approval',
      title: 'Ручное подтверждение',
      status: pendingApprovals.length || waitingActions.length ? 'waiting_approval' : 'completed',
      detail: pendingApprovals.length || waitingActions.length
        ? 'внешнее действие остановлено до решения человека'
        : 'ручной контроль проверен',
    },
    {
      key: 'activation',
      title: 'Готовность к включению',
      status: canActivateFromPreview ? 'completed' : 'pending',
      detail: canActivateFromPreview ? 'версию можно активировать' : nextStepDescription,
    },
  ];
  const actionLabel = canActivateFromPreview
    ? needsHumanDecision
      ? 'Проверить решение'
      : isCurrentVersionAlreadyActive
        ? 'Версия уже активна'
        : String(activationGate?.primary_action_label || 'Активировать версию')
    : previewNextStepActionLabel(nextStep, nextStepLabel);
  return (
    <div className="rounded-2xl border border-sky-200 bg-sky-50 px-4 py-4 text-sm leading-6 text-sky-950">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="font-semibold">Что показал тест без отправки</div>
          <div className="mt-1 max-w-3xl text-xs leading-5 text-sky-800">
            {userFacingAgentTechText(String(summary?.headline || 'Тест без отправки выполнен без внешних действий.'))}
          </div>
        </div>
        <span className="rounded-full bg-white px-2.5 py-1 text-xs font-medium text-sky-700 ring-1 ring-sky-200">
          {safePreview ? 'Тест без внешних действий' : 'проверьте внешние действия'}
        </span>
      </div>

      <div className="mt-3 grid gap-2 md:grid-cols-3">
        <PreviewRunFact label="Задача" value={userFacingAgentTechText(understoodTask)} />
        <PreviewRunFact label="Данные" value={userFacingAgentTechText(dataSources.length ? dataSources.join(', ') : providerBindings.length ? providerBindings.map((item) => formatPayloadValue(item)).join(' · ') : 'доступы проверены')} />
        <PreviewRunFact label="Ручной контроль" value={userFacingAgentTechText(manualControl)} />
      </div>

      <details className="mt-3 rounded-xl border border-sky-100 bg-white/70 px-3 py-2">
        <summary className="cursor-pointer text-xs font-semibold text-sky-800">
          Подробности теста
        </summary>
        <div className="mt-3 space-y-3">
          <CompiledPreviewSimulationPanel steps={simulationSteps} safePreview={safePreview} externalActionsPerformed={Boolean(summary?.external_actions_performed)} />

          <OpenClawPreviewActionPlanPanel
            actions={openClawActionPlan}
            policyEnvelope={policyEnvelope}
            approvalGate={approvalGate}
            safePreview={safePreview}
          />

          <div className="grid gap-2 lg:grid-cols-3">
            <PreviewSummaryList
              title="Шаги"
              items={completedSteps.length ? completedSteps.slice(0, 5).map((item) => userFacingAgentTechText(humanizeMeta(item))) : ['Шаги будут видны после теста без отправки.']}
            />
            <PreviewSummaryList
              title="Результаты"
              items={artifacts.length ? artifacts.slice(0, 4).map((item) => {
                const record = toRecordOrNull(item) || {};
                return userFacingAgentTechText(`${String(record.title || humanizeMeta(String(record.type || 'artifact')))}: ${String(record.summary || 'сохранён для проверки')}`);
              }) : ['Результат появится после подготовки.']}
            />
            <PreviewSummaryList
              title="Ручной контроль"
              items={
                pendingApprovals.length
                  ? pendingApprovals.slice(0, 4).map((item) => {
                    const record = toRecordOrNull(item) || {};
                    return userFacingAgentTechText(`${String(record.title || record.approval_type || 'Решение')}: ${humanizeMeta(String(record.status || 'pending'))}`);
                  })
                  : waitingActions.length
                    ? waitingActions.slice(0, 4).map((item) => {
                      const record = toRecordOrNull(item) || {};
                      return userFacingAgentTechText(`${humanizeMeta(String(record.kind || 'external_action'))}: ${String(record.why || record.state || 'ждёт approval')}`);
                    })
                    : ['Внешние действия останутся за ручным подтверждением.']
              }
            />
          </div>
        </div>
      </details>

      <div className="mt-3 rounded-xl bg-white px-3 py-2 text-xs leading-5 text-sky-800 ring-1 ring-sky-100">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <div className="font-semibold text-sky-900">
              Следующий шаг: {needsHumanDecision ? 'проверить решение' : isCurrentVersionAlreadyActive ? 'версия уже активна' : userFacingAgentTechText(nextStepLabel)}
            </div>
            <div className="mt-1">
              {needsHumanDecision
                ? 'Агент подготовил результат и остановился. Решите, можно ли использовать его дальше.'
                : isCurrentVersionAlreadyActive
                  ? 'Эта версия уже активна. Следующее действие - принять или отклонить подготовленный результат, если он ждёт решения.'
                  : userFacingAgentTechText(nextStepDescription)}
            </div>
            {canActivateFromPreview && !needsHumanDecision && !isCurrentVersionAlreadyActive ? (
              <div className="mt-1 font-medium text-emerald-700">Готовность подтверждена: тест без отправки, доступы и логика прошли проверку.</div>
            ) : null}
          </div>
          {needsHumanDecision && onNextStepAction ? (
            <Button type="button" size="sm" className="shrink-0" onClick={() => onNextStepAction('review_approvals')} disabled={actionLoading}>
              {actionLabel}
            </Button>
          ) : canActivateFromPreview && onActivateVersion && !isCurrentVersionAlreadyActive ? (
            <Button type="button" size="sm" className="shrink-0" onClick={() => onActivateVersion(activationVersionId)} disabled={actionLoading}>
              {actionLabel}
            </Button>
          ) : onNextStepAction ? (
            <Button type="button" size="sm" variant="outline" className="shrink-0 bg-white" onClick={() => onNextStepAction(nextStep)} disabled={actionLoading}>
              {actionLabel}
            </Button>
          ) : null}
        </div>
      </div>
    </div>
  );
};

export const OpenClawPreviewActionPlanPanel = ({
  actions,
  policyEnvelope,
  approvalGate,
  safePreview,
}: {
  actions: unknown[];
  policyEnvelope: Record<string, unknown>;
  approvalGate: Record<string, unknown>;
  safePreview: boolean;
}) => {
  const boundary = userFacingAgentTechText(String(policyEnvelope.execution_boundary || 'openclaw_action_orchestrator'));
  const approvalOwner = String(policyEnvelope.approval_owner || 'LocalOS');
  const billingOwner = String(policyEnvelope.billing_owner || policyEnvelope.cost_owner || 'LocalOS');
  const externalSideEffectsAllowed = policyEnvelope.external_side_effects_allowed_in_preview === true;
  const waitingCount = Number(approvalGate.waiting_actions_count || 0);
  const pendingApprovalsCount = Number(approvalGate.pending_approvals_count || 0);
  const visibleActions = actions.slice(0, 4).map((item) => toRecordOrNull(item) || {});
  if (!visibleActions.length && !Object.keys(policyEnvelope).length) {
    return null;
  }
  return (
    <div className="mt-3 rounded-xl bg-white px-3 py-3 text-xs leading-5 text-sky-800 ring-1 ring-sky-100">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <div className="font-semibold text-sky-950">План внешних действий в тесте</div>
          <div className="mt-1 text-sky-700">
            LocalOS показывает будущие действия, но оставляет исполнение за правилами безопасности, лимитами, списаниями и журналом.
          </div>
        </div>
        <span className={cn('rounded-full px-2 py-0.5 font-medium ring-1', safePreview && !externalSideEffectsAllowed ? 'bg-emerald-50 text-emerald-700 ring-emerald-200' : 'bg-amber-50 text-amber-700 ring-amber-200')}>
          {safePreview && !externalSideEffectsAllowed ? 'внешние действия выключены' : 'нужна проверка внешних действий'}
        </span>
      </div>

      <div className="mt-3 grid gap-2 md:grid-cols-3">
        <PreviewRunFact label="Граница выполнения" value={boundary} />
        <PreviewRunFact label="Подтверждение и списания" value={`${approvalOwner} подтверждения · ${billingOwner} списания`} />
        <PreviewRunFact label="Ожидание" value={`${pendingApprovalsCount} подтверждений · ${waitingCount} действий ждут`} />
      </div>

      {visibleActions.length ? (
        <div className="mt-3 grid gap-2 md:grid-cols-2">
          {visibleActions.map((action, index) => {
            const title = userFacingAgentTechText(String(action.title || action.provider_action_ref || action.capability || `Действие ${index + 1}`));
            const meta = [
              action.provider_action_ref ? userFacingAgentTechText(String(action.provider_action_ref)) : '',
              action.capability ? userFacingAgentTechText(String(action.capability)) : '',
              action.provider_policy ? userFacingAgentTechText(String(action.provider_policy)) : 'правила LocalOS',
            ].filter(Boolean).join(' · ');
            const requiresApproval = action.requires_approval === true || Boolean(action.approval_class);
            return (
              <div key={`${title}-${index}`} className="rounded-lg bg-sky-50 px-2.5 py-2 ring-1 ring-sky-100">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="line-clamp-1 font-semibold text-sky-950">{title}</div>
                    <div className="mt-1 line-clamp-2 text-sky-700">{meta || 'Действие останется внутри правил LocalOS'}</div>
                  </div>
                  <span className={cn('shrink-0 rounded-full px-2 py-0.5 font-medium ring-1', requiresApproval ? 'bg-amber-50 text-amber-700 ring-amber-200' : 'bg-emerald-50 text-emerald-700 ring-emerald-200')}>
                    {requiresApproval ? 'нужно решение' : 'безопасно'}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="mt-3 rounded-lg bg-sky-50 px-2.5 py-2 text-sky-700 ring-1 ring-sky-100">
          План внешних действий появится после подготовки логики или повторного теста без отправки.
        </div>
      )}
    </div>
  );
};

export const previewNextStepActionLabel = (nextStep: string, fallback: string) => {
  const labels: Record<string, string> = {
    connect_required_integrations: 'Открыть подключения',
    fix_preview_error: 'Открыть логику',
    review_approvals: 'Открыть решения',
    check_activation_gate: 'Проверить активацию',
    review_preview: 'Открыть запуск',
  };
  return labels[nextStep] || fallback || 'Открыть следующий шаг';
};

export const CompiledPreviewSimulationPanel = ({
  steps,
  safePreview,
  externalActionsPerformed,
}: {
  steps: Array<{ key: string; title: string; status: string; detail: string }>;
  safePreview: boolean;
  externalActionsPerformed: boolean;
}) => (
  <div className="mt-3 rounded-xl bg-white px-3 py-3 text-xs leading-5 text-sky-800 ring-1 ring-sky-100">
    <div className="flex flex-wrap items-start justify-between gap-2">
      <div>
        <div className="font-semibold text-sky-950">Симуляция проверки</div>
        <div className="mt-1 text-sky-700">
          Тест показывает, как агент пройдёт входные данные, проверку доступов, шаги, подтверждения и готовность к включению.
        </div>
      </div>
      <span className={cn('rounded-full px-2 py-0.5 font-medium ring-1', safePreview && !externalActionsPerformed ? 'bg-emerald-50 text-emerald-700 ring-emerald-200' : 'bg-amber-50 text-amber-700 ring-amber-200')}>
        {safePreview && !externalActionsPerformed ? 'внешних действий не было' : 'проверьте внешние действия'}
      </span>
    </div>
    <div className="mt-3 grid gap-2 md:grid-cols-5">
      {steps.map((step, index) => (
        <div key={step.key} className={cn('rounded-lg px-2 py-2 ring-1', previewSimulationTone(step.status))}>
          <div className="flex items-center gap-2">
            <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-white text-[11px] font-semibold ring-1 ring-current/10">
              {index + 1}
            </span>
            <div className="min-w-0 font-semibold">{step.title}</div>
          </div>
          <div className="mt-1 line-clamp-3 text-[11px] leading-4">{step.detail}</div>
        </div>
      ))}
    </div>
  </div>
);

export const previewSimulationTone = (status: string) => {
  if (status === 'completed') {
    return 'bg-emerald-50 text-emerald-800 ring-emerald-100';
  }
  if (status === 'waiting_approval') {
    return 'bg-amber-50 text-amber-800 ring-amber-100';
  }
  if (status === 'blocked' || status === 'failed') {
    return 'bg-rose-50 text-rose-800 ring-rose-100';
  }
  return 'bg-slate-50 text-slate-600 ring-slate-200';
};

export const PreviewSummaryList = ({ title, items }: { title: string; items: string[] }) => (
  <div className="rounded-xl bg-white px-3 py-2 text-xs leading-5 ring-1 ring-sky-100">
    <div className="font-semibold text-sky-900">{title}</div>
    <div className="mt-1 space-y-1 text-sky-700">
      {items.map((item, index) => (
        <div key={`${title}-${index}`} className="line-clamp-2">{item}</div>
      ))}
    </div>
  </div>
);

export const PreviewRunFact = ({ label, value }: { label: string; value: string }) => (
  <div className="rounded-xl bg-white px-3 py-2 text-xs leading-5 ring-1 ring-sky-100">
    <div className="font-semibold text-sky-900">{label}</div>
    <div className="mt-1 text-sky-700">{value || 'не указано'}</div>
  </div>
);

export const RunColumn = ({
  title,
  icon: Icon,
  children,
}: {
  title: string;
  icon: typeof Clock3;
  children: React.ReactNode;
}) => (
  <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
    <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-900">
      <Icon className="h-4 w-4" />
      {title}
    </div>
    <div className="space-y-2">
      {children || <div className="text-sm text-slate-500">Пока пусто</div>}
    </div>
  </div>
);

export const TimelineItem = ({ title, meta, status }: { title: string; meta: string; status: string }) => (
  <div className="rounded-xl bg-white px-3 py-3 shadow-sm ring-1 ring-slate-200">
    <div className="flex items-start justify-between gap-3">
      <div className="min-w-0">
        <div className="truncate text-sm font-medium text-slate-900">{title}</div>
        <div className="mt-1 text-xs text-slate-500">{meta}</div>
      </div>
      <StatusBadge status={status} />
    </div>
  </div>
);

export const BillingActionItem = ({
  item,
}: {
  item: AgentRunBillingAction;
}) => {
  const cost = Number(item.total_cost || 0);
  const entryCount = Number(item.entry_count || 0);
  return (
    <div className="rounded-xl bg-white px-3 py-3 shadow-sm ring-1 ring-slate-200">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="truncate text-sm font-medium text-slate-900">{item.capability || item.action_id || 'billing action'}</div>
          <div className="mt-1 text-xs text-slate-500">{item.action_id || 'no action id'}</div>
        </div>
        <StatusBadge status={item.status || 'settled'} />
      </div>
      <div className="mt-2 grid grid-cols-2 gap-2 text-xs">
        <div className="rounded-lg bg-slate-50 px-2 py-2">
          <div className="font-semibold text-slate-900">{cost ? `${cost} кр.` : 'без списания'}</div>
          <div className="text-slate-500">стоимость</div>
        </div>
        <div className="rounded-lg bg-slate-50 px-2 py-2">
          <div className="font-semibold text-slate-900">{entryCount}</div>
          <div className="text-slate-500">событий</div>
        </div>
      </div>
    </div>
  );
};

export const compactValue = (value: unknown) => {
  if (Array.isArray(value)) {
    return value.length ? value.join(', ') : 'any';
  }
  if (typeof value === 'number') {
    return String(value);
  }
  if (typeof value === 'string' && value.trim()) {
    return value.trim();
  }
  return 'any';
};

export const ArtifactSourceSummary = ({ payload }: { payload: AgentArtifact['payload_json'] }) => {
  const filters = payload?.filters || {};
  const filterEntries = Object.entries(filters).filter(([, value]) => {
    if (Array.isArray(value)) {
      return value.length > 0;
    }
    return value !== '' && value !== null && value !== undefined;
  });
  if (payload?.source !== 'prospectingleads' && !payload?.source_artifact && filterEntries.length === 0) {
    return null;
  }
  return (
    <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs leading-5 text-slate-600">
      {payload?.source === 'prospectingleads' ? (
        <div className="font-medium text-slate-800">Источник лидов: prospectingleads</div>
      ) : null}
      {payload?.source_artifact ? (
        <div>Сформировано из: {payload.source_artifact}</div>
      ) : null}
      {filterEntries.length ? (
        <div className="mt-1 flex flex-wrap gap-1.5">
          {filterEntries.map(([key, value]) => (
            <span key={key} className="rounded-md bg-white px-2 py-1 ring-1 ring-slate-200">
              {key}: {compactValue(value)}
            </span>
          ))}
        </div>
      ) : null}
    </div>
  );
};

export const ApprovalPayloadSummary = ({ approval }: { approval: AgentApproval }) => {
  const payload = approval.payload_json || {};
  const count = typeof payload.count === 'number' ? payload.count : null;
  const artifactType = typeof payload.artifact_type === 'string' ? payload.artifact_type : '';
  if (!artifactType && count === null) {
    return null;
  }
  return (
    <div className="mt-3 rounded-lg bg-white/80 px-3 py-2 text-xs leading-5 text-slate-600 ring-1 ring-amber-100">
      {artifactType ? <div>Результат: {artifactType}</div> : null}
      {count !== null ? <div>Ожидают решения: {count}</div> : null}
    </div>
  );
};

export const ArtifactItem = ({ artifact }: { artifact: AgentArtifact }) => {
  const payload = artifact.payload_json || {};
  const items = Array.isArray(payload.items) ? payload.items : [];
  const preview = items.slice(0, 3);
  return (
    <div className="rounded-xl bg-white px-3 py-3 shadow-sm ring-1 ring-slate-200">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="truncate text-sm font-medium text-slate-900">{artifact.title}</div>
          <div className="mt-1 text-xs text-slate-500">
            {payload.source || artifact.artifact_type} · {payload.count ?? items.length} items
          </div>
        </div>
        <StatusBadge status={typeof payload.status === 'string' ? payload.status : 'completed'} />
      </div>
      <ArtifactSourceSummary payload={payload} />
      {preview.length ? (
        <div className="mt-3 space-y-2">
          {preview.map((item, index) => (
            <div key={`${artifact.id}-${index}`} className="rounded-lg bg-slate-50 px-2 py-2 text-xs leading-5 text-slate-600">
              {String(item.name || item.lead_name || item.status || item.delivery_status || item.id || 'item')}
            </div>
          ))}
        </div>
      ) : null}
      <details className="mt-3">
        <summary className="cursor-pointer text-xs font-medium text-slate-500 hover:text-slate-900">
          Технический журнал
        </summary>
        <pre className="mt-2 max-h-72 overflow-auto rounded-lg bg-slate-950 p-3 text-[11px] leading-5 text-slate-100">
          {JSON.stringify(payload, null, 2)}
        </pre>
      </details>
    </div>
  );
};
