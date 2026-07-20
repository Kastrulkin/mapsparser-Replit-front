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
  parseAgentConfig,
  uploadAgentSource
} from './api';

import {
  RecommendedProviderRouteNote
} from './builder_setup';
import {
  connectionActionTone,
  providerRouteLabel,
  ProviderActionPill
} from './connections';
import {
  HumanResultView
} from './runs';
import { TimezoneSelect } from './timezone-select';

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

const creditWord = (value: number) => {
  const lastTwoDigits = value % 100;
  const lastDigit = value % 10;
  if (lastTwoDigits >= 11 && lastTwoDigits <= 14) return 'кредитов';
  if (lastDigit === 1) return 'кредит';
  if (lastDigit >= 2 && lastDigit <= 4) return 'кредита';
  return 'кредитов';
};

const StatusBadge = ({ status }: { status: string }) => (
  <span className={cn('inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ring-1', statusTone[status] || 'bg-slate-50 text-slate-600 ring-slate-200')}>
    {userFacingAgentTechText(humanizeStatus(status))}
  </span>
);

export const AgentMiniMetric = ({ label, value }: { label: string; value: string }) => (
  <div className="rounded-lg bg-white px-3 py-2 ring-1 ring-current/10">
    <div className="text-[11px] font-medium opacity-70">{label}</div>
    <div className="mt-1 text-base font-semibold">{value}</div>
  </div>
);

export const ConnectorIntelligencePanel = ({ intelligence }: { intelligence?: AgentConnectorIntelligence }) => {
  const bindings = intelligence?.bindings || [];
  const capabilities = intelligence?.capabilities || [];
  const providerPaths = intelligence?.provider_paths || [];
  const forbidden = intelligence?.forbidden || [];
  const unsupported = intelligence?.unsupported || [];
  if (!intelligence || (!bindings.length && !capabilities.length && !forbidden.length && !unsupported.length)) {
    return null;
  }
  const blocked = Boolean(forbidden.length || unsupported.length);
  const needsAction = bindings.some((item) => !['ready', 'native_ready'].includes(item.action || ''));
  return (
    <div className={cn('mt-3 rounded-xl border px-3 py-3 text-xs leading-5', blocked ? 'border-rose-200 bg-rose-50 text-rose-950' : needsAction ? 'border-amber-200 bg-amber-50 text-amber-950' : 'border-emerald-200 bg-emerald-50 text-emerald-950')}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="font-semibold">Доступность сервисов</div>
          <div className="mt-1 max-w-2xl">
	            {userFacingAgentTechText(intelligence.headline || 'LocalOS проверил нужные подключения и способы подключения.')}
          </div>
        </div>
        <span className={cn('rounded-full bg-white px-2.5 py-1 font-medium ring-1', blocked ? 'text-rose-700 ring-rose-200' : needsAction ? 'text-amber-800 ring-amber-200' : 'text-emerald-800 ring-emerald-200')}>
	          {blocked ? 'нельзя создать' : needsAction ? 'нужно действие' : 'готово к тесту'}
        </span>
      </div>

      {bindings.length ? (
        <div className="mt-3 grid gap-2 md:grid-cols-2">
          {bindings.slice(0, 4).map((item) => (
            <div key={item.key || item.provider} className="rounded-lg bg-white px-2 py-2 ring-1 ring-black/5">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="font-medium text-slate-950">{item.title || connectorLabel(item.provider)}</div>
	                  <div className="mt-0.5 text-[11px] text-slate-500">{userFacingAgentTechText(humanizeMeta(item.capability || item.provider || 'capability'))}</div>
                </div>
                <span className={cn('shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium ring-1', connectionActionTone(item.action || ''))}>
	                  {userFacingAgentTechText(item.action_label || humanizeMeta(item.action || item.status || ''))}
                </span>
              </div>
	              <div className="mt-1 text-[11px] leading-4 text-slate-600">{userFacingAgentTechText(item.route_summary || item.explanation || 'Будет проверено перед запуском.')}</div>
              {item.connections?.length ? (
                <div className="mt-1 flex flex-wrap gap-1">
                  {item.connections.slice(0, 2).map((connection) => (
                    <span key={connection.id || connection.display_name} className="rounded-full bg-sky-50 px-1.5 py-0.5 text-[10px] text-sky-700 ring-1 ring-sky-100">
                      {connection.display_name || connectorLabel(connection.provider)}
                    </span>
                  ))}
                </div>
              ) : null}
              {item.provider_routes?.length ? (
                <div className="mt-2 flex flex-wrap gap-1">
                  {item.provider_routes.slice(0, 4).map((route) => (
                    <ProviderActionPill key={`${item.key}-${route.provider}-${route.role}`} route={route} />
                  ))}
                </div>
              ) : null}
              <RecommendedProviderRouteNote
                route={item.recommended_route}
                reason={item.recommended_route_reason}
              />
            </div>
          ))}
        </div>
      ) : null}

      {capabilities.length ? (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {capabilities.slice(0, 5).map((item) => (
            <span key={item.capability} className="rounded-full bg-white px-2 py-0.5 text-[11px] text-slate-700 ring-1 ring-black/5">
              {userFacingAgentTechText(humanizeMeta(item.capability || ''))}
              {item.route_state ? ` · ${userFacingAgentTechText(providerRouteLabel(item.route_state))}` : ''}
              {item.openclaw_actions?.length ? ` · действий LocalOS ${item.openclaw_actions.length}` : ''}
            </span>
          ))}
        </div>
      ) : null}

      {providerPaths.length ? (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {providerPaths.slice(0, 6).map((item) => (
            <span key={`${item.provider}-${item.status}-${item.source}`} className="rounded-full bg-white/80 px-2 py-0.5 text-[11px] text-slate-600 ring-1 ring-black/5">
              {userFacingAgentTechText(item.label || connectorLabel(item.provider))}: {userFacingAgentTechText(humanizeMeta(item.status || 'unknown'))}
            </span>
          ))}
        </div>
      ) : null}
    </div>
  );
};

export const BuilderPlannerLoopPanel = ({ plannerLoop }: { plannerLoop?: AgentBuilderPlannerLoop }) => {
  if (!plannerLoop) {
    return null;
  }
  const capabilities = plannerLoop.capability_plan || [];
  const actionRefs = plannerLoop.workflow_proposal?.openclaw_action_refs || [];
  const providerPaths = plannerLoop.workflow_proposal?.provider_paths || [];
  return (
    <div className="mt-3 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs leading-5 text-slate-600">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="font-semibold text-slate-950">Планировщик действий</div>
        <span className="rounded-full bg-slate-50 px-2 py-0.5 font-medium text-slate-600 ring-1 ring-slate-200">
          {plannerLoop.catalog_source === 'openclaw' ? 'живой каталог' : 'резервный каталог'}
        </span>
      </div>
      <div className="mt-1">
        Проверены разрешённые действия: {capabilities.length || 0}, способы подключения: {providerPaths.length || 0}, ссылки на действия: {actionRefs.length || 0}. Инструменты не выполняются в мастере; LocalOS сохранит проверяемую логику.
      </div>
    </div>
  );
};

export const BuilderExecutionBoundaryPanel = ({ plannerLoop }: { plannerLoop?: AgentBuilderPlannerLoop }) => {
  if (!plannerLoop) {
    return null;
  }
  const actionRefs = plannerLoop.workflow_proposal?.openclaw_action_refs || [];
  const providerPaths = plannerLoop.workflow_proposal?.provider_paths || [];
  const capabilities = plannerLoop.capability_plan || [];
  const contract = plannerLoop.planner_contract || {};
  if (!actionRefs.length && !capabilities.length && !providerPaths.length) {
    return null;
  }
  const mayExecuteTools = plannerLoop.may_execute_tools === true || contract.tool_execution_allowed === true;
  const externalSideEffects = contract.external_side_effects_allowed === true;
  return (
    <div
      className="mt-3 rounded-xl border border-sky-200 bg-sky-50 px-3 py-3 text-xs leading-5 text-sky-950"
      data-contract-label="Execution boundary"
      data-contract-openclaw-action-refs="OpenClaw action refs"
      data-contract-safe-preview-copy="OpenClaw actions в safe preview; side effects выключены"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="font-semibold">Граница исполнения</div>
          <div className="mt-1 max-w-2xl text-sky-800">
            Действия можно предложить и исполнить только внутри правил безопасности, списаний, журнала и ручных подтверждений LocalOS.
          </div>
        </div>
        <span className="rounded-full bg-white px-2 py-0.5 font-medium text-sky-700 ring-1 ring-sky-200">
          {plannerLoop.catalog_source === 'openclaw' ? 'Каталог действий' : 'Резервный каталог'}
        </span>
      </div>
      <div className="mt-3 grid gap-2 sm:grid-cols-3">
        <AgentMiniMetric label="Инструменты" value={mayExecuteTools ? 'разрешены' : 'запрещены'} />
        <AgentMiniMetric label="Внешние действия" value={externalSideEffects ? 'есть риск' : 'нет в тесте'} />
        <AgentMiniMetric label="Владелец логики" value={contract.compiled_workflow_owner || (plannerLoop.must_compile_in_localos ? 'LocalOS' : 'LocalOS')} />
      </div>
      {actionRefs.length ? (
        <div className="mt-3 rounded-lg bg-white px-2 py-2 ring-1 ring-sky-100">
          <div className="font-semibold text-sky-900">Ссылки на действия</div>
          <div className="mt-1 flex flex-wrap gap-1.5">
            {actionRefs.slice(0, 6).map((actionRef) => (
              <span key={actionRef} className="rounded-full bg-slate-50 px-2 py-0.5 font-mono text-[11px] text-slate-700 ring-1 ring-slate-200">
                {actionRef}
              </span>
            ))}
          </div>
        </div>
      ) : null}
      {capabilities.length ? (
        <div className="mt-2 grid gap-2 md:grid-cols-2">
          {capabilities.slice(0, 4).map((item) => {
            const refs = item.openclaw_actions?.map((action) => action.openclaw_action_ref).filter(Boolean) || [];
            return (
              <div key={item.capability || refs.join(':')} className="rounded-lg bg-white px-2 py-2 ring-1 ring-sky-100">
                <div className="font-medium text-slate-950">{userFacingAgentTechText(humanizeMeta(item.capability || 'capability'))}</div>
                <div className="mt-1 text-[11px] leading-4 text-slate-600">
                  {refs.length ? refs.slice(0, 2).join(' · ') : 'Действие не выбрано'}
                </div>
              </div>
            );
          })}
        </div>
      ) : null}
      {contract.must_not?.length ? (
        <div className="mt-2 rounded-lg bg-white/80 px-2 py-1.5 text-[11px] leading-4 text-sky-800 ring-1 ring-sky-100">
          Нельзя: {contract.must_not.slice(0, 4).map((item) => userFacingAgentTechText(humanizeMeta(item))).join(', ')}.
        </div>
      ) : null}
    </div>
  );
};

export const PreviewRow = ({ label, value }: { label: string; value: string }) => (
  <div className="rounded-xl bg-white px-3 py-2 ring-1 ring-slate-200">
    <div className="text-xs font-semibold uppercase text-slate-500">{label}</div>
    <div className="mt-1 text-slate-800">{value}</div>
  </div>
);

export const BuilderFeasibilityPanel = ({ feasibility, connectors }: { feasibility?: AgentBuilderFeasibility; connectors?: AgentBuilderConnectorPreview[] }) => {
  const status = feasibility?.status || 'ready';
  const items = connectors || [];
  const forbidden = feasibility?.forbidden || [];
  const unsupported = feasibility?.unsupported || [];
  const isProblem = status === 'forbidden' || status === 'unsupported';
  const isReady = status === 'ready';
  const tone = isReady
    ? 'border-emerald-200 bg-emerald-50 text-emerald-950'
    : isProblem
      ? 'border-red-200 bg-red-50 text-red-950'
      : 'border-amber-200 bg-amber-50 text-amber-950';
  const title = status === 'ready'
    ? 'Подключения готовы'
    : status === 'needs_choice'
      ? 'Нужно выбрать подключение'
      : status === 'needs_connection'
        ? 'Нужно подключить сервисы'
        : status === 'forbidden'
          ? 'Нельзя создать в LocalOS'
          : status === 'unsupported'
            ? 'Нет разрешённого способа'
            : 'Нужно проверить ограничения';
  if (!items.length && !forbidden.length && !unsupported.length && isReady) {
    return null;
  }
  return (
    <div className={cn('mt-3 rounded-xl border px-3 py-3 text-xs leading-5', tone)}>
      <div className="font-semibold">{title}</div>
      {items.length ? (
        <div className="mt-2 grid gap-2 sm:grid-cols-2">
          {items.map((item) => (
            <div key={`${item.key || item.provider || item.title}`} className="rounded-lg bg-white/70 px-2 py-2 ring-1 ring-black/5">
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium">{item.title || connectorLabel(item.provider)}</span>
                <span className="rounded-full bg-white px-2 py-0.5 text-[11px] font-medium ring-1 ring-black/10">
                  {userFacingAgentTechText(statusLabels[item.status || ''] || humanizeMeta(item.status || 'ожидает'))}
                </span>
              </div>
              {item.status === 'missing' ? (
                <div className="mt-1 opacity-80">{item.action?.description || 'Подключите доступ перед активацией агента.'}</div>
              ) : null}
              {item.status === 'needs_choice' ? (
                <div className="mt-1 opacity-80">{item.action?.description || `Найдено подключений: ${item.connection_count || 0}. Нужно выбрать одно.`}</div>
              ) : null}
              {item.status === 'ready' ? (
                <div className="mt-1 opacity-80">{item.action?.description || 'Подключение готово.'}</div>
              ) : null}
              {item.connections?.length ? (
                <div className="mt-2 flex flex-wrap gap-1">
                  {item.connections.slice(0, 2).map((connection) => (
                    <span key={connection.id || connection.display_name} className="rounded-full bg-white px-2 py-0.5 text-[11px] ring-1 ring-black/10">
                      {connection.display_name || connectorLabel(connection.provider)}
                    </span>
                  ))}
                </div>
              ) : null}
              {item.action?.label && item.status !== 'ready' ? (
                <div className="mt-2 inline-flex rounded-full bg-white px-2 py-0.5 text-[11px] font-medium ring-1 ring-black/10">
                  {item.action.label}
                </div>
              ) : null}
            </div>
          ))}
        </div>
      ) : null}
      {forbidden.length ? (
        <div className="mt-2 space-y-2">
          {forbidden.map((item) => (
            <div key={`${item.term || item.reason}`} className="rounded-lg bg-white/70 px-2 py-2 ring-1 ring-red-100">
              {item.reason || 'Действие запрещено политикой LocalOS.'}
            </div>
          ))}
        </div>
      ) : null}
      {unsupported.length ? (
        <div className="mt-2 space-y-2">
          {unsupported.map((item) => (
            <div key={`${item.capability || item.reason}`} className="rounded-lg bg-white/70 px-2 py-2 ring-1 ring-red-100">
              {item.reason || 'Нет разрешённого способа подключения.'}
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
};

export const SystemAgentCard = ({
  title,
  description,
  icon: Icon,
  enabled,
  onConfigure,
}: {
  title: string;
  description: string;
  icon: typeof Bot;
  enabled: boolean;
  onConfigure: () => void;
}) => (
  <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
    <div className="flex items-start justify-between gap-3">
      <div className="flex min-w-0 items-start gap-3">
        <div className="rounded-xl bg-slate-100 p-2 text-slate-700">
          <Icon className="h-5 w-5" />
        </div>
        <div className="min-w-0">
          <div className="text-sm font-semibold text-slate-950">{title}</div>
          <div className="mt-1 text-sm leading-6 text-slate-600">{description}</div>
        </div>
      </div>
      <span className={cn('shrink-0 rounded-full px-2.5 py-1 text-xs font-medium ring-1', enabled ? 'bg-emerald-50 text-emerald-700 ring-emerald-200' : 'bg-slate-100 text-slate-600 ring-slate-200')}>
        {enabled ? 'Включён' : 'Выключен'}
      </span>
    </div>
    <div className="mt-4 flex justify-end">
      <Button type="button" size="sm" variant="outline" onClick={onConfigure}>
        Настроить
      </Button>
    </div>
  </div>
);

export const AgentsTodaySection = ({
  summary,
  loading,
  onOpenToday,
}: {
  summary: AgentTodaySummary;
  loading: boolean;
  onOpenToday: () => void;
}) => (
  <section className="rounded-2xl border border-slate-200 bg-white px-5 py-5 shadow-sm">
    <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
      <div>
        <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Сегодня</div>
        <h2 className="mt-2 text-xl font-semibold leading-7 text-slate-950">Что сделали ИИ-сотрудники за последние 24 часа</h2>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
          {summary.empty
            ? 'За сегодня агенты ещё ничего не запускали.'
            : summary.latestEvent
              ? `Последнее событие: ${summary.latestEvent}.`
              : 'LocalOS собрал свежую сводку по агентам.'}
        </p>
      </div>
      <Button type="button" variant="outline" onClick={onOpenToday} disabled={loading}>
        Подробнее
      </Button>
    </div>
    <div className="mt-5 grid gap-3 md:grid-cols-4">
      <TodayFact icon={CheckCircle2} label="Выполнено работ" value={summary.completedRuns} tone="emerald" />
      <TodayFact icon={FileCheck2} label="Подготовлено результатов" value={summary.preparedArtifacts} tone="sky" />
      <TodayFact icon={ShieldCheck} label="Ждут решения" value={summary.pendingApprovals} tone={summary.pendingApprovals ? 'amber' : 'slate'} />
      <TodayFact icon={AlertTriangle} label="Нужно проверить" value={summary.failedRuns} tone={summary.failedRuns ? 'rose' : 'slate'} />
    </div>
  </section>
);

export const TodayFact = ({
  icon: Icon,
  label,
  value,
  tone,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: number;
  tone: 'emerald' | 'sky' | 'amber' | 'rose' | 'slate';
}) => (
  <div className={cn(
    'rounded-xl px-3 py-3 ring-1',
    tone === 'emerald' ? 'bg-emerald-50 text-emerald-950 ring-emerald-100' : '',
    tone === 'sky' ? 'bg-sky-50 text-sky-950 ring-sky-100' : '',
    tone === 'amber' ? 'bg-amber-50 text-amber-950 ring-amber-100' : '',
    tone === 'rose' ? 'bg-rose-50 text-rose-950 ring-rose-100' : '',
    tone === 'slate' ? 'bg-slate-50 text-slate-700 ring-slate-100' : '',
  )}>
    <div className="flex items-center justify-between gap-3">
      <Icon className="h-4 w-4" />
      <span className="tabular-nums text-lg font-semibold">{value}</span>
    </div>
    <div className="mt-2 text-xs font-medium leading-5">{label}</div>
  </div>
);

export const AgentsAttentionInbox = ({
  items,
  loading,
}: {
  items: AgentAttentionItem[];
  loading: boolean;
}) => (
  <section className="rounded-2xl border border-slate-200 bg-white px-5 py-5 shadow-sm">
    <div className="flex items-start justify-between gap-3">
      <div>
        <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Требует внимания</div>
        <h2 className="mt-2 text-lg font-semibold leading-7 text-slate-950">Следующие решения и настройки</h2>
      </div>
      <span className="rounded-full bg-slate-50 px-2.5 py-1 text-xs font-medium text-slate-600 ring-1 ring-slate-200">
        {items.length ? `${items.length} задач` : 'спокойно'}
      </span>
    </div>
    <div className="mt-4 grid gap-3">
      {loading ? (
        <div className="rounded-xl bg-slate-50 px-3 py-3 text-sm text-slate-500 ring-1 ring-slate-100">Проверяем, где нужен человек...</div>
      ) : items.length ? (
        items.map((item) => (
          <div
            key={item.key}
            className={cn(
              'grid gap-3 rounded-xl px-3 py-3 ring-1 md:grid-cols-[minmax(0,1fr)_auto] md:items-center',
              item.tone === 'amber' ? 'bg-amber-50 text-amber-950 ring-amber-100' : '',
              item.tone === 'rose' ? 'bg-rose-50 text-rose-950 ring-rose-100' : '',
              item.tone === 'sky' ? 'bg-sky-50 text-sky-950 ring-sky-100' : '',
            )}
          >
            <div className="min-w-0">
              <div className="text-sm font-semibold text-slate-950">{item.problem}</div>
              <div className="mt-1 line-clamp-2 text-sm leading-6 opacity-85">{item.reason}</div>
            </div>
            <Button type="button" size="sm" onClick={item.action}>
              {item.actionLabel}
            </Button>
          </div>
        ))
      ) : (
        <div className="rounded-xl bg-emerald-50 px-3 py-3 text-sm leading-6 text-emerald-950 ring-1 ring-emerald-100">
          Всё работает. Новых действий не требуется.
        </div>
      )}
    </div>
  </section>
);

export const AgentCommandCenter = ({
  activeAgentsCount,
  totalAgents,
  pendingApprovals,
  selectedBlueprint,
  loading,
  actionLoading,
  onCreate,
  onConfigureSelected,
  onOpenApprovals,
}: {
  activeAgentsCount: number;
  totalAgents: number;
  pendingApprovals: number;
  selectedBlueprint: AgentBlueprint | null;
  loading: boolean;
  actionLoading: boolean;
  onCreate: () => void;
  onConfigureSelected: () => void;
  onOpenApprovals: () => void;
}) => (
  <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
    <div className="grid gap-3 lg:grid-cols-3">
      <button
        type="button"
        className="group rounded-xl border border-slate-900 bg-slate-950 px-4 py-4 text-left text-white transition hover:bg-slate-900"
        onClick={onCreate}
        disabled={actionLoading}
      >
        <div className="flex items-center justify-between gap-3">
          <Sparkles className="h-5 w-5" />
          <span className="text-xs font-medium text-slate-300">{totalAgents} всего</span>
        </div>
        <div className="mt-4 text-sm font-semibold">Создать агента</div>
        <div className="mt-1 text-sm leading-6 text-slate-300">
          Опишите задачу, проверьте будущую логику, затем подключите данные.
        </div>
      </button>

      <button
        type="button"
        className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-4 text-left transition hover:border-slate-300 hover:bg-white"
        onClick={onConfigureSelected}
        disabled={!selectedBlueprint || loading}
      >
        <div className="flex items-center justify-between gap-3">
          <Workflow className="h-5 w-5 text-slate-600" />
          <span className="text-xs font-medium text-slate-500">{activeAgentsCount} активны</span>
        </div>
        <div className="mt-4 text-sm font-semibold text-slate-950">Настроить выбранного</div>
        <div className="mt-1 line-clamp-2 text-sm leading-6 text-slate-600">
          {selectedBlueprint ? selectedBlueprint.name : 'Сначала выберите агента в списке.'}
        </div>
      </button>

      <button
        type="button"
        className={cn(
          'rounded-xl border px-4 py-4 text-left transition',
          pendingApprovals ? 'border-amber-200 bg-amber-50 hover:border-amber-300' : 'border-slate-200 bg-slate-50 hover:border-slate-300 hover:bg-white',
        )}
        onClick={onOpenApprovals}
        disabled={!selectedBlueprint}
      >
        <div className="flex items-center justify-between gap-3">
          <ShieldCheck className={cn('h-5 w-5', pendingApprovals ? 'text-amber-700' : 'text-slate-600')} />
          <span className={cn('text-xs font-medium', pendingApprovals ? 'text-amber-800' : 'text-slate-500')}>
            {pendingApprovals} ждут
          </span>
        </div>
        <div className="mt-4 text-sm font-semibold text-slate-950">Проверить решения</div>
        <div className={cn('mt-1 text-sm leading-6', pendingApprovals ? 'text-amber-900' : 'text-slate-600')}>
          Ручные решения, журнал и результаты открываются внутри выбранного агента.
        </div>
      </button>
    </div>
  </section>
);

export const BlueprintAgentCard = ({
  blueprint,
  latestVersionNumber,
  selected,
  businessStatus,
  onSelect,
  onConfigure,
  onRun,
  onResults,
  onVoice,
  onDelete,
  actionLoading,
}: {
  blueprint: AgentBlueprint;
  latestVersionNumber: number | null;
  selected: boolean;
  businessStatus: AgentBusinessStatus;
  onSelect: () => void;
  onConfigure: () => void;
  onRun: () => void;
  onResults: () => void;
  onVoice: () => void;
  onDelete: () => void;
  actionLoading: boolean;
}) => {
  const toneClass = {
    ready: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
    warning: 'bg-amber-50 text-amber-700 ring-amber-200',
    error: 'bg-rose-50 text-rose-700 ring-rose-200',
    draft: 'bg-slate-100 text-slate-700 ring-slate-200',
  }[businessStatus.tone];
  return (
  <div className={cn('rounded-xl border bg-white p-3 transition', selected ? 'border-slate-900 shadow-sm' : 'border-slate-200 hover:border-slate-300')}>
    <button type="button" className="w-full text-left" onClick={onSelect}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold text-slate-950">{blueprint.name}</div>
          <div className="mt-1 text-xs font-medium text-slate-500">
            {humanizeCategory(blueprint.category)}{latestVersionNumber ? ` · рабочая версия ${latestVersionNumber}` : ''}
          </div>
        </div>
        <span className={cn('shrink-0 rounded-full px-2.5 py-1 text-xs font-medium ring-1', toneClass)}>
          {businessStatus.label}
        </span>
      </div>
      <div className="mt-3 line-clamp-3 text-sm leading-6 text-slate-600">
        {blueprint.description || blueprint.latest_goal || 'Пользовательский агент с настройками, запусками и результатами.'}
      </div>
      <div className="mt-3 grid gap-2 text-xs text-slate-600 sm:grid-cols-2">
        <div className="rounded-lg bg-slate-50 px-2.5 py-2 ring-1 ring-slate-100">
          <div className="font-semibold text-slate-800">Последний результат</div>
          <div className="mt-1 line-clamp-2">{businessStatus.lastResult}</div>
        </div>
        <div className="rounded-lg bg-slate-50 px-2.5 py-2 ring-1 ring-slate-100">
          <div className="font-semibold text-slate-800">Следующий запуск</div>
          <div className="mt-1 line-clamp-2">{businessStatus.nextRun}</div>
        </div>
      </div>
    </button>
    <div className="mt-3 grid grid-cols-[1fr_auto] gap-2">
      <Button type="button" size="sm" variant={selected ? 'default' : 'outline'} onClick={onConfigure}>
        Настроить
      </Button>
      <Button type="button" size="sm" variant="outline" onClick={onRun}>
        <Play className="mr-2 h-4 w-4" />
        {businessStatus.primaryLabel}
      </Button>
    </div>
    <div className="mt-2 flex gap-1.5">
      <Button type="button" size="sm" variant="ghost" className="h-8 px-2 text-xs" onClick={onResults}>История</Button>
      <Button type="button" size="sm" variant="ghost" className="h-8 px-2 text-xs" onClick={onVoice}>Голос</Button>
      <Button
        type="button"
        size="sm"
        variant="ghost"
        className="h-8 px-2 text-xs text-red-700 hover:text-red-800"
        onClick={onDelete}
        disabled={actionLoading}
      >
        <Archive className="mr-1.5 h-3.5 w-3.5" />
        Архивировать агента
      </Button>
    </div>
  </div>
  );
};

export const employeeToneClass = {
  emerald: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  amber: 'bg-amber-50 text-amber-800 ring-amber-200',
  rose: 'bg-rose-50 text-rose-700 ring-rose-200',
  slate: 'bg-slate-100 text-slate-700 ring-slate-200',
};

export const EmployeeStatusPill = ({ status }: { status: EmployeeStatus }) => (
  <span className={cn('inline-flex min-h-8 items-center rounded-full px-3 py-1 text-xs font-semibold ring-1', employeeToneClass[status.tone])}>
    {status.label}
  </span>
);

export const AgentRunProgressPanel = ({
  animation,
  onRetry,
}: {
  animation: AgentRunAnimation;
  onRetry: () => void;
}) => {
  const failed = animation.status === 'error';
  const currentStep = animation.queueState === 'queued'
    ? 'Задача поставлена в очередь'
    : animation.queueState === 'retry_wait'
      ? 'Повторю текущий шаг после временной ошибки'
      : animation.queueState === 'waiting_approval'
        ? 'Жду вашего решения перед следующим действием'
        : animation.steps[animation.stepIndex] || 'Выполняю задачу';
  return (
    <section className="overflow-hidden rounded-2xl bg-white shadow-[0_18px_48px_rgba(15,23,42,0.08),0_0_0_1px_rgba(15,23,42,0.08)]">
      <div className="bg-slate-950 px-5 py-5 text-white sm:px-7 sm:py-7">
        <div className="flex items-start gap-4">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-white/10">
            {failed ? <AlertTriangle className="h-5 w-5 text-rose-300" /> : <Loader2 className="h-5 w-5 animate-spin motion-reduce:animate-none" />}
          </div>
          <div className="min-w-0 flex-1">
            <div className="text-xs font-semibold uppercase text-slate-400">{animation.kind === 'test' ? 'Безопасный тест' : 'Рабочий запуск'}</div>
            <h2 className="mt-1 text-2xl font-semibold leading-8 [text-wrap:balance]">{failed ? 'Работа остановилась' : 'Агент выполняет задачу'}</h2>
            <p className="mt-2 text-sm leading-6 text-slate-300 [text-wrap:pretty]">{failed ? animation.error : currentStep}</p>
          </div>
          <span className="shrink-0 text-sm font-semibold tabular-nums text-slate-300">{animation.progress}%</span>
        </div>
        <div className="mt-5 h-2 overflow-hidden rounded-full bg-white/10">
          <div
            className={cn('h-full rounded-full transition-[width] duration-500 ease-out motion-reduce:transition-none', failed ? 'bg-rose-400' : 'bg-orange-400')}
            style={{ width: `${animation.progress}%` }}
          />
        </div>
      </div>
      <div className="px-5 py-5 sm:px-7">
        <ol className="grid gap-2">
          {animation.steps.map((step, index) => {
            const done = animation.status === 'finishing' || index < (animation.serverCompletedSteps || 0);
            const current = index === animation.stepIndex;
            return (
              <li
                key={`${index}-${step}`}
                className={cn(
                  'flex min-h-11 items-center gap-3 rounded-xl px-3 text-sm transition-[background-color,color,opacity] duration-300 motion-reduce:transition-none',
                  done ? 'bg-emerald-50 text-emerald-900' : current ? failed ? 'bg-rose-50 text-rose-900' : 'bg-orange-50 text-orange-950' : 'text-slate-400',
                )}
              >
                <span className={cn(
                  'flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold ring-1',
                  done ? 'bg-emerald-600 text-white ring-emerald-600' : current ? failed ? 'bg-rose-100 text-rose-700 ring-rose-200' : 'bg-orange-100 text-orange-700 ring-orange-200' : 'bg-slate-50 text-slate-400 ring-slate-200',
                )}>
                  {done ? <CheckCircle2 className="h-4 w-4" /> : index + 1}
                </span>
                <span className="font-medium [text-wrap:pretty]">{step}</span>
              </li>
            );
          })}
        </ol>
        {failed ? (
          <Button type="button" className="mt-4 min-h-10 active:scale-[0.96] transition-transform" onClick={onRetry}>
            <RefreshCw className="mr-2 h-4 w-4" />
            Запустить ещё раз
          </Button>
        ) : (
          <p className="mt-4 text-xs leading-5 text-slate-500">Можно оставить страницу открытой: результат появится здесь сразу после завершения.</p>
        )}
      </div>
    </section>
  );
};

export const EmployeeAgentsList = ({
  blueprints,
  detailsById,
  selectedBlueprintId,
  selectedActiveRun,
  selectedPendingApproval,
  loading,
  onOpen,
}: {
  blueprints: AgentBlueprint[];
  detailsById: Record<string, AgentBlueprintDetails>;
  selectedBlueprintId: string | null;
  selectedActiveRun?: AgentRun | null;
  selectedPendingApproval?: AgentApproval | null;
  loading: boolean;
  onOpen: (blueprint: AgentBlueprint) => void;
}) => (
  <aside className="rounded-2xl bg-white p-3 shadow-[0_1px_2px_rgba(15,23,42,0.06),0_0_0_1px_rgba(15,23,42,0.08)] lg:sticky lg:top-4">
    <div className="flex items-center justify-between gap-3 px-1">
      <div>
        <h2 className="text-sm font-semibold leading-6 text-slate-950">Сотрудники</h2>
        <p className="text-xs leading-5 text-slate-500">Тип, состояние и следующий шаг</p>
      </div>
      <span className="inline-flex min-h-7 items-center rounded-full bg-slate-50 px-2.5 py-0.5 text-xs font-medium tabular-nums text-slate-600 ring-1 ring-slate-200">
        {blueprints.length}
      </span>
    </div>

    <div className="mt-3 max-h-[calc(100vh-18rem)] min-h-72 overflow-y-auto pr-1">
      {loading ? (
        <div className="flex min-h-20 items-center gap-2 rounded-xl bg-slate-50 px-3 py-3 text-sm text-slate-500 ring-1 ring-slate-100">
          <Loader2 className="h-4 w-4 animate-spin" />
          Загружаем сотрудников...
        </div>
      ) : blueprints.length === 0 ? (
        <div className="rounded-xl bg-slate-50 px-3 py-4 text-sm leading-6 text-slate-600 ring-1 ring-slate-100">
          Создайте первого сотрудника.
        </div>
      ) : (
        blueprints.map((blueprint) => {
          const selected = selectedBlueprintId === blueprint.id;
          const baseDetails = detailsById[blueprint.id];
          const details = selected && selectedActiveRun
            ? {
              ...baseDetails,
              runs: [
                selectedActiveRun,
                ...(baseDetails?.runs || []).filter((run) => run.id !== selectedActiveRun.id),
              ],
            }
            : baseDetails;
          const pendingApproval = selected
            ? selectedPendingApproval || (details?.approval_queue || []).find((item) => item.status === 'pending') || null
            : (details?.approval_queue || []).find((item) => item.status === 'pending') || null;
          const status = buildEmployeeStatus(blueprint, details, pendingApproval);
          const state = buildEmployeeWorkspaceState(blueprint, details, pendingApproval);
          const mode = agentExecutionMode(blueprint, details);
          const lastResult = blueprint.last_business_result || details?.last_business_result;
          const resultText = lastResult ? businessResultPrimaryText(lastResult) : '';
          return (
            <button
              key={blueprint.id}
              type="button"
              onClick={() => onOpen(blueprint)}
              className={cn(
                'mb-2 grid min-h-[7.5rem] w-full gap-3 rounded-xl px-3 py-3 text-left transition-[box-shadow,background-color,color] active:scale-[0.99]',
                selected ? 'bg-slate-950 text-white shadow-[0_0_0_1px_rgba(15,23,42,1)]' : 'bg-white shadow-[0_0_0_1px_rgba(15,23,42,0.08)] hover:shadow-[0_6px_18px_rgba(15,23,42,0.08),0_0_0_1px_rgba(15,23,42,0.12)]',
                !selected && (state === 'waiting_for_review' || state === 'needs_connection' || state === 'needs_attention') ? 'bg-amber-50/60' : '',
                !selected && state === 'error' ? 'bg-rose-50/70' : '',
              )}
            >
              <div className="min-w-0">
                <div className="flex min-w-0 items-start justify-between gap-2">
                  <div className={cn('line-clamp-2 text-sm font-semibold leading-5', selected ? 'text-white' : 'text-slate-950')}>
                    {blueprint.name}
                  </div>
                  <span className={cn('shrink-0 rounded-full px-2 py-0.5 text-[11px] font-semibold ring-1', selected ? 'bg-white/10 text-slate-200 ring-white/15' : 'bg-sky-50 text-sky-700 ring-sky-100')}>
                    {agentExecutionModeLabel(mode)}
                  </span>
                </div>
                <div className={cn('mt-1 line-clamp-1 text-xs leading-5', selected ? 'text-slate-300' : 'text-slate-500')}>
                  {buildEmployeeDescription(blueprint, details)}
                </div>
              </div>
              <div className="grid gap-1">
                <div className="flex items-center justify-between gap-2">
                  <span className={cn('inline-flex min-h-7 items-center rounded-full px-2 py-0.5 text-[11px] font-semibold ring-1', employeeToneClass[status.tone])}>{status.label}</span>
                  <span className={cn('text-[11px] tabular-nums', selected ? 'text-slate-300' : 'text-slate-500')}>{agentNextRunLabel(blueprint, details)}</span>
                </div>
                <div className={cn('line-clamp-1 text-xs leading-5', selected ? 'text-slate-300' : 'text-slate-500')}>
                  {resultText || buildEmployeeLastActivity(blueprint, details, pendingApproval)}
                </div>
              </div>
            </button>
          );
        })
      )}
    </div>
  </aside>
);

export const EmployeeAnswerCard = ({
  label,
  value,
  tone = 'slate',
}: {
  label: string;
  value: string;
  tone?: 'slate' | 'emerald' | 'amber' | 'rose';
}) => (
  <div className={cn(
    'rounded-xl px-4 py-4 shadow-[0_0_0_1px_rgba(15,23,42,0.08)]',
    tone === 'emerald' ? 'bg-emerald-50 text-emerald-950' : '',
    tone === 'amber' ? 'bg-amber-50 text-amber-950' : '',
    tone === 'rose' ? 'bg-rose-50 text-rose-950' : '',
    tone === 'slate' ? 'bg-slate-50 text-slate-950' : '',
  )}>
    <div className="text-xs font-semibold uppercase tracking-wide opacity-60">{label}</div>
    <div className="mt-2 text-sm font-medium leading-6 [text-wrap:pretty]">{value}</div>
  </div>
);

export const EmployeeRunningPanel = ({
  blueprint,
  details,
  pendingApproval,
}: {
  blueprint: AgentBlueprint;
  details: AgentBlueprintDetails | null;
  pendingApproval: AgentApproval | null;
}) => {
  const attentionItems = buildEmployeeAttentionItems(blueprint, details, pendingApproval);
  const healthy = attentionItems.length === 0;
  return (
    <div className={cn(
      'rounded-2xl bg-white p-5 shadow-[0_1px_2px_rgba(15,23,42,0.06),0_0_0_1px_rgba(15,23,42,0.08)]',
      healthy ? 'lg:max-w-3xl' : '',
    )}>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex items-center gap-2 text-sm font-semibold text-emerald-700">
            <CheckCircle2 className="h-4 w-4" />
            Работает
          </div>
          <h3 className="mt-2 text-xl font-semibold leading-7 text-slate-950 [text-wrap:balance]">{blueprint.name}</h3>
          <p className="mt-2 text-sm leading-6 text-slate-600 [text-wrap:pretty]">
            {healthy ? 'Сотрудник работает. Когда всё спокойно, здесь остаётся только короткий статус.' : 'Есть вопросы, которые требуют вашего внимания.'}
          </p>
        </div>
      </div>

      <div className={cn('mt-5 grid gap-3', healthy ? 'sm:grid-cols-2' : 'lg:grid-cols-3')}>
        <EmployeeAnswerCard label="Следующий запуск" value={blueprint.active_version_number ? 'По расписанию сотрудника' : 'После включения'} tone="emerald" />
        <EmployeeAnswerCard label="Последняя задача" value={buildEmployeeLastActivity(blueprint, details || undefined, pendingApproval)} />
        {!healthy ? (
          <EmployeeAnswerCard label="Требует внимания" value={`${attentionItems.length} ${attentionItems.length === 1 ? 'задача' : 'задачи'}`} tone="amber" />
        ) : null}
      </div>

      {!healthy ? (
        <div className="mt-4 grid gap-2">
          {attentionItems.map((item) => (
            <div key={item.key} className={cn('rounded-xl px-3 py-3 text-sm leading-6 ring-1', item.tone === 'rose' ? 'bg-rose-50 text-rose-950 ring-rose-100' : 'bg-amber-50 text-amber-950 ring-amber-100')}>
              <div className="font-semibold text-slate-950">{item.title}</div>
              <div className="mt-1">{item.description}</div>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
};

export const EmployeeTestResultPanel = ({
  activeRun,
  pendingApproval,
  actionLoading,
  needsScenarioRebuild = false,
  needsGoogleSheetsSetup = false,
  needsGoogleAccessReconnect = false,
  googleAccessJustConnected = false,
  estimatedRunCredits = 0,
  onApprove,
  onReject,
  onRunAgain,
  onRebuildScenario,
  onOpenGoogleSheetsSetup,
  onOpenGoogleAccessReconnect,
}: {
  activeRun: AgentRun | null;
  pendingApproval: AgentApproval | null;
  actionLoading: boolean;
  needsScenarioRebuild?: boolean;
  needsGoogleSheetsSetup?: boolean;
  needsGoogleAccessReconnect?: boolean;
  googleAccessJustConnected?: boolean;
  estimatedRunCredits?: number;
  onApprove: () => void;
  onReject: () => void;
  onRunAgain: () => void;
  onRebuildScenario?: () => void;
  onOpenGoogleSheetsSetup?: () => void;
  onOpenGoogleAccessReconnect?: () => void;
}) => {
  const result = buildEmployeeTestResult(activeRun, pendingApproval);
  const isWorkRun = isAgentWorkRun(activeRun);
  const [evaluation, setEvaluation] = useState<AgentRun['evaluation']>(activeRun?.evaluation || null);
  const [evaluationLoading, setEvaluationLoading] = useState(false);
  const [evaluationError, setEvaluationError] = useState('');
  const chargedCredits = Number(activeRun?.run_billing?.actual_credits || activeRun?.run_billing?.charge_credits || 0);
  const labels = approvalActionLabels(pendingApproval);
  const isBlocked = result.state === 'blocker';
  const canApprove = Boolean(pendingApproval && !isBlocked);
  const canReject = Boolean(pendingApproval && !isBlocked);
  const canRebuildScenario = Boolean(needsScenarioRebuild && onRebuildScenario);
  const canRunAfterGoogleReconnect = Boolean(!canRebuildScenario && googleAccessJustConnected && needsGoogleAccessReconnect);
  const canOpenGoogleAccessReconnect = Boolean(!canRunAfterGoogleReconnect && !canRebuildScenario && needsGoogleAccessReconnect && onOpenGoogleAccessReconnect);
  const canOpenGoogleSheetsSetup = Boolean(!canRebuildScenario && !canOpenGoogleAccessReconnect && needsGoogleSheetsSetup && onOpenGoogleSheetsSetup);
  const canEvaluate = Boolean(isWorkRun && activeRun?.status === 'completed');
  useEffect(() => {
    setEvaluation(activeRun?.evaluation || null);
    setEvaluationError('');
  }, [activeRun?.id, activeRun?.evaluation?.rating, activeRun?.evaluation?.feedback]);
  const submitEvaluation = async (rating: 'useful' | 'not_useful') => {
    if (!activeRun?.id || evaluationLoading) {
      return;
    }
    setEvaluationLoading(true);
    setEvaluationError('');
    try {
      const response = await api.post(`/agent-runs/${activeRun.id}/feedback`, {
        trigger_type: 'run_review',
        rating,
        feedback: rating === 'useful' ? 'Результат полезен' : 'Результат нужно улучшить',
      });
      const savedEvaluation = response.data?.evaluation;
      setEvaluation({
        rating: savedEvaluation?.rating === 'not_useful' ? 'not_useful' : 'useful',
        feedback: typeof savedEvaluation?.feedback === 'string' ? savedEvaluation.feedback : '',
        created_at: typeof savedEvaluation?.created_at === 'string' ? savedEvaluation.created_at : '',
      });
    } catch (requestError) {
      setEvaluationError(getRequestErrorMessage(requestError, 'Не удалось сохранить оценку результата.'));
    } finally {
      setEvaluationLoading(false);
    }
  };
  const rerunLabel = canRebuildScenario
    ? 'Пересобрать сценарий'
    : canRunAfterGoogleReconnect
      ? 'Запустить тест'
      : canOpenGoogleAccessReconnect
        ? 'Переподключить Google-доступ'
        : canOpenGoogleSheetsSetup
          ? 'Указать Google-таблицу'
          : isWorkRun ? 'Повторить с этими параметрами' : 'Повторить тест с этими параметрами';
  const handleRerun = () => {
    if (canRebuildScenario && onRebuildScenario) {
      onRebuildScenario();
      return;
    }
    if (canOpenGoogleAccessReconnect && onOpenGoogleAccessReconnect) {
      onOpenGoogleAccessReconnect();
      return;
    }
    if (canOpenGoogleSheetsSetup && onOpenGoogleSheetsSetup) {
      onOpenGoogleSheetsSetup();
      return;
    }
    onRunAgain();
  };
  return (
    <div className="rounded-2xl bg-white p-5 shadow-[0_1px_2px_rgba(15,23,42,0.06),0_0_0_1px_rgba(15,23,42,0.08)]">
      <div className="space-y-4">
        <div className="min-w-0 max-w-4xl">
          <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">{isWorkRun ? 'Результат работы' : 'Результат проверки'}</div>
          <h2 className="mt-2 max-w-3xl text-2xl font-semibold leading-8 text-slate-950 [text-wrap:balance]">{result.summary}</h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600 [text-wrap:pretty]">
            Это только бизнес-результат. Технические подробности находятся в расширенных настройках.
          </p>
        </div>
        <div className="flex min-w-0 flex-wrap gap-2">
          {canApprove ? (
            <Button type="button" className="min-h-10 whitespace-nowrap active:scale-[0.96] transition-transform" onClick={onApprove} disabled={actionLoading}>
              {actionLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <CheckCircle2 className="mr-2 h-4 w-4" />}
              {labels.approve}
            </Button>
          ) : null}
          {canReject ? (
            <Button type="button" variant="outline" className="min-h-10 whitespace-nowrap active:scale-[0.96] transition-transform" onClick={onReject} disabled={actionLoading}>
              {labels.reject}
            </Button>
          ) : null}
          {!pendingApproval || canRebuildScenario || canRunAfterGoogleReconnect || canOpenGoogleAccessReconnect || canOpenGoogleSheetsSetup ? (
            <Button
              type="button"
              variant="outline"
              className="min-h-10 whitespace-nowrap active:scale-[0.96] transition-transform"
              onClick={handleRerun}
              disabled={actionLoading}
            >
              {actionLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : canRunAfterGoogleReconnect ? <Play className="mr-2 h-4 w-4" /> : canOpenGoogleAccessReconnect || canOpenGoogleSheetsSetup ? <Database className="mr-2 h-4 w-4" /> : <RefreshCw className="mr-2 h-4 w-4" />}
              {rerunLabel}
            </Button>
          ) : null}
          {isWorkRun && estimatedRunCredits ? (
            <div className="w-full text-right text-xs font-medium tabular-nums text-slate-500">
              Повтор: примерно {estimatedRunCredits} {creditWord(estimatedRunCredits)}
            </div>
          ) : null}
          {activeRun?.id ? (
            <div className="w-full text-right text-xs font-medium tabular-nums text-slate-500">
              {isWorkRun
                ? chargedCredits > 0
                  ? `За эту работу списано: ${chargedCredits} ${creditWord(chargedCredits)}`
                  : 'Списание не потребовалось'
                : 'Проверка выполнена бесплатно'}
            </div>
          ) : null}
        </div>
      </div>

      {result.resultPayload ? (
        <div className={cn(
          'mt-5 rounded-2xl px-4 py-4 shadow-[inset_0_0_0_1px_rgba(15,23,42,0.08)]',
          result.state === 'blocker' ? 'bg-amber-50' : 'bg-slate-50',
        )}>
          <div className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-500">
            {result.state === 'blocker' ? 'Что мешает продолжить' : 'Подготовленный результат'}
          </div>
          <HumanResultView result={result.resultPayload} resultState={activeRun?.result_state} />
          {needsScenarioRebuild ? (
            <div className="mt-3 rounded-xl bg-white px-3 py-3 text-sm leading-6 text-amber-950 shadow-[inset_0_0_0_1px_rgba(217,119,6,0.18)]">
              Этот агент создан старой версией сценария: в нём нет шага чтения Google Sheets. Пересоберите сценарий, и LocalOS сразу запустит тест по новой версии.
            </div>
          ) : null}
          {needsGoogleSheetsSetup && !needsScenarioRebuild ? (
            <div className="mt-3 rounded-xl bg-white px-3 py-3 text-sm leading-6 text-amber-950 shadow-[inset_0_0_0_1px_rgba(217,119,6,0.18)]">
              Нужно указать конкретную таблицу и лист со списком поездок. Нажмите “Указать Google-таблицу” — откроется раздел источников этого сотрудника.
            </div>
          ) : null}
          {needsGoogleAccessReconnect && !needsScenarioRebuild ? (
            <div className="mt-3 rounded-xl bg-white px-3 py-3 text-sm leading-6 text-amber-950 shadow-[inset_0_0_0_1px_rgba(217,119,6,0.18)]">
              {googleAccessJustConnected
                ? 'Google-доступ подключён. Этот результат был получен до переподключения, поэтому запустите тест ещё раз.'
                : 'Google-доступ для чтения таблицы больше не работает. Нажмите “Переподключить Google-доступ” — откроется экран подключений с Google Таблицами.'}
            </div>
          ) : null}
        </div>
      ) : null}

      {result.output ? (
        <div className={cn(
          'rounded-xl px-4 py-4 text-sm leading-7 text-slate-700 shadow-[inset_0_0_0_1px_rgba(15,23,42,0.08)] whitespace-pre-wrap',
          result.resultPayload ? 'mt-3 bg-white' : 'mt-5 bg-slate-50',
        )}>
          {result.output}
        </div>
      ) : null}

      {!result.resultPayload && !result.output ? (
        <div className="mt-5 rounded-xl bg-slate-50 px-4 py-4 text-sm leading-7 text-slate-700 shadow-[inset_0_0_0_1px_rgba(15,23,42,0.08)]">
          Результат не был сохранён. Запустите тест ещё раз или откройте настройки для диагностики.
        </div>
      ) : null}

      {canEvaluate ? (
        <div className="mt-4 rounded-xl bg-emerald-50 px-4 py-4 shadow-[inset_0_0_0_1px_rgba(5,150,105,0.16)]">
          <div className="text-sm font-semibold text-slate-950">Помог ли результат?</div>
          <div className="mt-1 text-sm leading-6 text-slate-600">
            Оценка относится только к этой работе и не изменяет сценарий агента.
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            <Button
              type="button"
              size="sm"
              variant={evaluation?.rating === 'useful' ? 'default' : 'outline'}
              onClick={() => submitEvaluation('useful')}
              disabled={actionLoading || evaluationLoading}
            >
              {evaluationLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <CheckCircle2 className="mr-2 h-4 w-4" />}
              Да, результат полезен
            </Button>
            <Button
              type="button"
              size="sm"
              variant={evaluation?.rating === 'not_useful' ? 'default' : 'outline'}
              onClick={() => submitEvaluation('not_useful')}
              disabled={actionLoading || evaluationLoading}
            >
              Нужно улучшить
            </Button>
          </div>
          {evaluation?.rating ? (
            <div className="mt-3 text-xs font-medium text-emerald-800">Спасибо. Оценка сохранена.</div>
          ) : null}
          {evaluationError ? (
            <div className="mt-3 text-sm text-rose-700">{evaluationError}</div>
          ) : null}
        </div>
      ) : null}

      {result.previewItems.length ? (
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          {result.previewItems.map((item) => (
            <div key={`${item.label}-${item.value}`} className="rounded-xl bg-white px-4 py-3 shadow-[0_0_0_1px_rgba(15,23,42,0.08)]">
              <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">{item.label}</div>
              <div className="mt-2 line-clamp-5 text-sm leading-6 text-slate-800">{item.value}</div>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
};

export const EmployeeHistoryPanel = ({
  details,
  activeRun,
}: {
  details: AgentBlueprintDetails | null;
  activeRun: AgentRun | null;
}) => {
  const events = buildEmployeeHistoryStory(details, activeRun);
  return (
    <div className="rounded-2xl bg-white p-5 shadow-[0_1px_2px_rgba(15,23,42,0.06),0_0_0_1px_rgba(15,23,42,0.08)]">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">История</div>
          <h2 className="mt-2 text-xl font-semibold leading-7 text-slate-950 [text-wrap:balance]">Что сотрудник делал раньше</h2>
        </div>
        <span className="inline-flex min-h-8 items-center rounded-full bg-slate-50 px-3 py-1 text-xs font-medium text-slate-600 ring-1 ring-slate-200">
          {events.length ? `${events.length} событий` : 'пусто'}
        </span>
      </div>
      <div className="mt-5 grid gap-3">
        {events.length ? (
          events.map((event) => (
            <div key={event.key} className="grid gap-3 rounded-xl bg-slate-50 px-4 py-4 ring-1 ring-slate-100 sm:grid-cols-[7rem_minmax(0,1fr)]">
              <div className="text-sm font-medium tabular-nums text-slate-500">{event.time}</div>
              <div>
                <div className="text-sm font-semibold text-slate-950">{event.title}</div>
                <div className="mt-1 text-sm leading-6 text-slate-600">{event.description}</div>
              </div>
            </div>
          ))
        ) : (
          <div className="rounded-xl bg-slate-50 px-4 py-4 text-sm leading-6 text-slate-600 ring-1 ring-slate-100">
            История появится после первого теста или результата.
          </div>
        )}
      </div>
    </div>
  );
};

export const EmployeeWorkspaceSection = ({
  title,
  children,
  tone = 'default',
}: {
  title: string;
  children: React.ReactNode;
  tone?: 'default' | 'quiet' | 'attention' | 'error';
}) => (
  <section className={cn(
    'rounded-2xl px-4 py-4 shadow-[0_1px_2px_rgba(15,23,42,0.04),0_0_0_1px_rgba(15,23,42,0.08)]',
    tone === 'default' ? 'bg-white' : '',
    tone === 'quiet' ? 'bg-slate-50' : '',
    tone === 'attention' ? 'bg-amber-50 text-amber-950 shadow-[0_1px_2px_rgba(120,53,15,0.05),0_0_0_1px_rgba(245,158,11,0.25)]' : '',
    tone === 'error' ? 'bg-rose-50 text-rose-950 shadow-[0_1px_2px_rgba(127,29,29,0.05),0_0_0_1px_rgba(244,63,94,0.24)]' : '',
  )}>
    <div className="text-xs font-semibold uppercase tracking-wide opacity-60">{title}</div>
    <div className="mt-2">{children}</div>
  </section>
);

export const EmployeeResponsibilitiesList = ({ items }: { items: EmployeeResponsibility[] }) => (
  <div className="grid gap-2 sm:grid-cols-2">
    {items.map((item) => (
      <div key={item.key} className="flex min-h-10 items-start gap-2 rounded-xl bg-slate-50 px-3 py-2 text-sm leading-6 text-slate-800 shadow-[inset_0_0_0_1px_rgba(15,23,42,0.06)]">
        <CheckCircle2 className={cn('mt-1 h-4 w-4 shrink-0', item.done === false ? 'text-slate-300' : 'text-emerald-600')} />
        <span>{item.label}</span>
      </div>
    ))}
  </div>
);

export const agentExecutionModeOptions: Array<{ value: AgentExecutionMode; label: string; description: string }> = [
  { value: 'one_off', label: 'Сделать один раз', description: 'После выполнения задача попадёт в завершённые.' },
  { value: 'manual', label: 'Запускать по кнопке', description: 'Вы запускаете работу, когда она нужна.' },
  { value: 'scheduled', label: 'По расписанию', description: 'Агент запускается в указанное время.' },
];

export const AgentExecutionModePanel = ({
  mode,
  confirmationRequired,
  time,
  timezone,
  actionLoading,
  onModeChange,
  onTimeChange,
  onTimezoneChange,
  onSave,
}: {
  mode: AgentExecutionMode;
  confirmationRequired: boolean;
  time: string;
  timezone: string;
  actionLoading: boolean;
  onModeChange: (mode: AgentExecutionMode) => void;
  onTimeChange: (value: string) => void;
  onTimezoneChange: (value: string) => void;
  onSave: () => void;
}) => (
  <section className={cn(
    'rounded-2xl bg-white p-5 shadow-[0_1px_2px_rgba(15,23,42,0.06),0_0_0_1px_rgba(15,23,42,0.08)]',
    confirmationRequired ? 'shadow-[0_0_0_2px_rgba(249,115,22,0.25)]' : '',
  )}>
    <div className="max-w-3xl">
      <div className="text-xs font-semibold uppercase text-slate-500">Как запускается</div>
      <h2 className="mt-2 text-xl font-semibold leading-7 text-slate-950 [text-wrap:balance]">
        {confirmationRequired ? 'Подтвердите тип агента' : 'Тип запуска'}
      </h2>
      <p className="mt-1 text-sm leading-6 text-slate-600 [text-wrap:pretty]">
        Выбор меняет только способ запуска. Он не включает агента и не запускает работу.
      </p>
    </div>
    <div className="mt-4 grid gap-2 sm:grid-cols-3">
      {agentExecutionModeOptions.map(({ value, label, description }) => (
        <button
          key={value}
          type="button"
          onClick={() => onModeChange(value)}
          className={cn(
            'min-h-24 rounded-xl px-4 py-3 text-left shadow-[0_0_0_1px_rgba(15,23,42,0.10)] transition-[box-shadow,background-color,color] active:scale-[0.96] motion-reduce:transition-none',
            mode === value ? 'bg-slate-950 text-white shadow-[0_0_0_2px_rgba(15,23,42,1)]' : 'bg-white text-slate-950 hover:bg-slate-50',
          )}
        >
          <span className="block text-sm font-semibold">{label}</span>
          <span className={cn('mt-1 block text-xs leading-5', mode === value ? 'text-slate-300' : 'text-slate-500')}>{description}</span>
        </button>
      ))}
    </div>
    {mode === 'scheduled' ? (
      <div className="mt-4 grid gap-3 sm:grid-cols-[10rem_minmax(0,16rem)]">
        <label className="text-sm font-medium text-slate-800">
          Время
          <input type="time" value={time} onChange={(event) => onTimeChange(event.target.value)} className="mt-1 min-h-10 w-full rounded-lg bg-white px-3 shadow-[inset_0_0_0_1px_rgba(15,23,42,0.14)] outline-none" />
        </label>
        <div className="text-sm font-medium text-slate-800">
          Часовой пояс
          <TimezoneSelect value={timezone} onChange={onTimezoneChange} className="mt-1" />
        </div>
      </div>
    ) : null}
    <Button type="button" className="mt-4 min-h-10 active:scale-[0.96] transition-transform" onClick={onSave} disabled={actionLoading || (mode === 'scheduled' && (!time || !timezone))}>
      {actionLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <CheckCircle2 className="mr-2 h-4 w-4" />}
      {confirmationRequired ? 'Подтвердить тип запуска' : 'Сохранить'}
    </Button>
  </section>
);

export const AgentScheduleSetupPanel = ({
  time,
  timezone,
  actionLoading,
  onTimeChange,
  onTimezoneChange,
  onSave,
}: {
  time: string;
  timezone: string;
  actionLoading: boolean;
  onTimeChange: (value: string) => void;
  onTimezoneChange: (value: string) => void;
  onSave: () => void;
}) => (
  <section className="rounded-2xl bg-amber-50 p-5 shadow-[0_0_0_1px_rgba(217,119,6,0.2)]">
    <div className="max-w-3xl">
      <div className="text-xs font-semibold uppercase tracking-wide text-amber-700">Расписание</div>
      <h2 className="mt-2 text-xl font-semibold leading-7 text-amber-950 [text-wrap:balance]">Когда агент должен начинать работу</h2>
      <p className="mt-1 text-sm leading-6 text-amber-900 [text-wrap:pretty]">Время хранится вместе с часовым поясом, поэтому запуск не сдвинется при переходе на летнее время.</p>
    </div>
    <div className="mt-4 grid gap-3 sm:grid-cols-[10rem_minmax(0,16rem)_auto] sm:items-end">
      <label className="block text-sm font-medium text-amber-950">
        Время
        <input
          type="time"
          value={time}
          onChange={(event) => onTimeChange(event.target.value)}
          className="mt-1 min-h-10 w-full rounded-lg bg-white px-3 text-sm text-slate-950 shadow-[inset_0_0_0_1px_rgba(15,23,42,0.14)] outline-none focus:shadow-[inset_0_0_0_2px_rgba(249,115,22,0.65)]"
        />
      </label>
      <div className="block text-sm font-medium text-amber-950">
        Часовой пояс
        <TimezoneSelect value={timezone} onChange={onTimezoneChange} className="mt-1 focus-visible:ring-2 focus-visible:ring-orange-400" />
      </div>
      <Button type="button" className="min-h-10 active:scale-[0.96] transition-transform" onClick={onSave} disabled={actionLoading || !time || !timezone}>
        {actionLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Clock3 className="mr-2 h-4 w-4" />}
        Сохранить расписание
      </Button>
    </div>
  </section>
);

export const employeeStateTitle = (state: EmployeeWorkspaceState) => ({
  draft: 'Черновик',
  needs_mode: 'Выберите тип запуска',
  needs_connection: 'Не хватает подключения',
  ready_for_test: 'Готов к проверке',
  running_test: 'Проверка идёт',
  waiting_for_review: 'Ждёт вашего решения',
  blocked_result: 'Нужен следующий шаг',
  working: 'Работает',
  completed: 'Выполнено',
  needs_attention: 'Нужно включить',
  error: 'Ошибка',
}[state]);

export const AgentRunParametersPanel = ({
  schema,
  values,
  errors,
  onChange,
}: {
  schema?: AgentRunInputSchema;
  values: Record<string, unknown>;
  errors: Record<string, string>;
  onChange: (key: string, value: unknown) => void;
}) => {
  const fields = Object.entries(schema?.properties || {});
  if (!fields.length) {
    return null;
  }
  const required = new Set(schema?.required || []);
  return (
    <section className="rounded-2xl bg-white px-5 py-5 shadow-sm ring-1 ring-slate-200">
      <div className="text-sm font-semibold text-slate-950">Параметры этой работы</div>
      <p className="mt-1 text-sm leading-6 text-slate-600">Проверьте значения перед тестом или рабочим запуском.</p>
      <div className="mt-4 grid gap-4 md:grid-cols-2">
        {fields.map(([key, field]) => {
          const label = field.title || key.replaceAll('_', ' ');
          const value = values[key];
          const inputClassName = cn(
            'mt-1 min-h-10 w-full rounded-lg border bg-white px-3 py-2 text-sm text-slate-950 outline-none focus:ring-2',
            errors[key] ? 'border-rose-300 focus:border-rose-400 focus:ring-rose-100' : 'border-slate-200 focus:border-slate-400 focus:ring-slate-100',
          );
          return (
            <label key={key} className={cn('text-sm text-slate-700', field.format === 'textarea' || field.type === 'array' ? 'md:col-span-2' : '')}>
              <span className="font-medium text-slate-900">{label}{required.has(key) ? ' *' : ''}</span>
              {field.enum?.length ? (
                <select className={inputClassName} value={String(value ?? '')} onChange={(event) => onChange(key, event.target.value)}>
                  <option value="">Выберите</option>
                  {field.enum.map((option) => <option key={String(option)} value={String(option)}>{String(option)}</option>)}
                </select>
              ) : field.type === 'boolean' ? (
                <span className="mt-2 flex min-h-10 items-center gap-2">
                  <input type="checkbox" checked={Boolean(value)} onChange={(event) => onChange(key, event.target.checked)} />
                  <span>{Boolean(value) ? 'Да' : 'Нет'}</span>
                </span>
              ) : field.format === 'textarea' || field.type === 'array' ? (
                <textarea
                  className={cn(inputClassName, 'min-h-24 resize-y')}
                  value={Array.isArray(value) ? value.join('\n') : String(value ?? '')}
                  onChange={(event) => onChange(key, event.target.value)}
                />
              ) : (
                <input
                  className={inputClassName}
                  type={field.format === 'date' ? 'date' : field.format === 'time' ? 'time' : field.format === 'date-time' ? 'datetime-local' : field.type === 'number' || field.type === 'integer' ? 'number' : 'text'}
                  min={field.format === 'date' ? new Date().toISOString().slice(0, 10) : undefined}
                  step={field.type === 'integer' ? '1' : undefined}
                  value={String(value ?? '')}
                  placeholder={field.example === undefined ? undefined : String(field.example)}
                  onInput={(event) => onChange(key, event.currentTarget.value)}
                  onChange={(event) => onChange(key, event.target.value)}
                  onBlur={(event) => onChange(key, event.currentTarget.value)}
                />
              )}
              {field.description ? <span className="mt-1 block text-xs leading-5 text-slate-500">{field.description}</span> : null}
              {errors[key] ? <span className="mt-1 block text-xs font-medium text-rose-700">{errors[key]}</span> : null}
            </label>
          );
        })}
      </div>
    </section>
  );
};


export const EmployeeAgentOverviewPanel = ({
  blueprint,
  details,
  activeRun,
  pendingApproval,
  action,
  actionLoading,
  onPrimaryAction,
  onCloneAgent,
  onOpenAdvanced,
  onOpenResults,
}: {
  blueprint: AgentBlueprint;
  details: AgentBlueprintDetails | null;
  activeRun: AgentRun | null;
  pendingApproval: AgentApproval | null;
  action: EmployeeNextAction;
  actionLoading: boolean;
  onPrimaryAction: () => void;
  onCloneAgent: () => void;
  onOpenAdvanced: () => void;
  onOpenResults: () => void;
}) => {
  const story = buildEmployeeWorkspaceStory(blueprint, details, pendingApproval);
  const latestRun = details?.runs?.[0] || null;
  const detailedLatestRun = activeRun?.id && activeRun.id === latestRun?.id ? activeRun : latestRun;
  const latestResult = findPreparedResultPayload(detailedLatestRun, pendingApproval)
    || details?.last_business_result
    || blueprint.last_business_result
    || null;
  const healthy = story.state === 'working' && story.attention.length === 0;
  const problem = story.state === 'error' || story.state === 'waiting_for_review' || story.state === 'blocked_result' || story.state === 'needs_connection' || story.state === 'needs_attention';
  const actionDisabled = actionLoading || story.state === 'running_test';
  const userMode = buildAgentUserMode(blueprint, details);
  const actionCredits = action.kind === 'run_work' ? estimatedAgentRunCredits(details) : 0;
  const goal = String(
    details?.execution_contract?.original_request
    || details?.execution_contract?.active?.goal
    || details?.execution_contract?.candidate?.goal
    || buildEmployeeDescription(blueprint, details),
  );
  const tested = Boolean(details?.execution_contract?.candidate?.validation?.tested);
  const enabled = Boolean(details?.execution_contract?.active?.version_id && blueprint.status === 'active');
  const hasWorkRun = Boolean((details?.runs || []).some((run) => isAgentWorkRun(run) && run.status === 'completed'));
  const lifecycle = [
    { label: 'Описан', done: true },
    { label: 'Проверен', done: tested },
    { label: 'Включён', done: enabled },
    { label: 'Работает', done: hasWorkRun || story.state === 'working' },
  ];
  return (
    <div className={cn('space-y-4', healthy ? 'max-w-4xl' : 'max-w-5xl')}>
      <section className={cn(
        'rounded-3xl p-5 shadow-[0_18px_48px_rgba(15,23,42,0.08),0_0_0_1px_rgba(15,23,42,0.08)]',
        problem ? 'bg-white' : 'bg-white',
      )}>
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <EmployeeStatusPill status={story.status} />
              <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-600">
                {employeeStateTitle(story.state)}
              </span>
              <span className="rounded-full bg-sky-50 px-2.5 py-1 text-xs font-medium text-sky-700 ring-1 ring-sky-100">
                {userMode.label}
              </span>
            </div>
            <h1 className="mt-3 text-3xl font-semibold leading-9 text-slate-950 [text-wrap:balance]">{blueprint.name}</h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600 [text-wrap:pretty]">{story.status.summary}</p>
          </div>
          <div className="shrink-0">
            <Button
              type="button"
              className={cn(
                'min-h-12 w-full px-5 active:scale-[0.96] transition-transform',
                story.state === 'error' ? 'bg-rose-600 text-white hover:bg-rose-700' : '',
              )}
              onClick={onPrimaryAction}
              disabled={actionDisabled}
            >
              {actionLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : action.kind === 'connect' ? <Database className="mr-2 h-4 w-4" /> : action.kind === 'approve' ? <ShieldCheck className="mr-2 h-4 w-4" /> : action.kind === 'enable' ? <CheckCircle2 className="mr-2 h-4 w-4" /> : <Play className="mr-2 h-4 w-4" />}
              {action.label}
            </Button>
            {actionCredits ? (
              <div className="mt-2 text-center text-xs font-medium tabular-nums text-slate-500">
                Примерно {actionCredits} {creditWord(actionCredits)} за запуск
              </div>
            ) : action.kind === 'run_test' ? (
              <div className="mt-2 text-center text-xs font-medium text-slate-500">
                Проверка выполняется бесплатно
              </div>
            ) : null}
          </div>
        </div>
        <details className="mt-4 border-t border-slate-100 pt-3">
          <summary className="cursor-pointer text-sm font-medium text-slate-500 hover:text-slate-900">Другие действия</summary>
          <div className="mt-3 flex flex-wrap gap-2">
            <Button type="button" variant="outline" className="min-h-10" onClick={onCloneAgent} disabled={actionLoading}>
              <Copy className="mr-2 h-4 w-4" />
              Создать копию агента
            </Button>
            <Button type="button" variant="outline" className="min-h-10" onClick={onOpenAdvanced}>
              Открыть настройки
            </Button>
          </div>
        </details>
      </section>

      <EmployeeWorkspaceSection title="Цель агента">
        <p className="whitespace-pre-wrap text-base leading-7 text-slate-800 [text-wrap:pretty]">{goal}</p>
      </EmployeeWorkspaceSection>

      <EmployeeWorkspaceSection title="Готовность процесса" tone={problem ? 'attention' : 'quiet'}>
        <ol className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {lifecycle.map((item) => (
            <li key={item.label} className={cn('flex min-h-11 items-center gap-2 rounded-lg px-3 text-sm font-medium ring-1', item.done ? 'bg-emerald-50 text-emerald-900 ring-emerald-200' : 'bg-slate-50 text-slate-500 ring-slate-200')}>
              {item.done ? <CheckCircle2 className="h-4 w-4 shrink-0" /> : <span className="h-2 w-2 shrink-0 rounded-full bg-slate-300" />}
              {item.label}
            </li>
          ))}
        </ol>
        <div className="mt-3 text-sm leading-6 text-slate-600"><span className="font-semibold text-slate-800">{userMode.label}.</span> {userMode.description}</div>
      </EmployeeWorkspaceSection>

      <div className="grid gap-4 lg:grid-cols-2">
        <EmployeeWorkspaceSection title="Последняя работа" tone={healthy ? 'quiet' : 'default'}>
          <div className="text-sm font-semibold leading-6 text-slate-950">{story.latestWork}</div>
        </EmployeeWorkspaceSection>
        <EmployeeWorkspaceSection title="Следующая работа" tone={healthy ? 'quiet' : 'default'}>
          <div className="text-sm font-semibold leading-6 text-slate-950">{story.nextWork}</div>
        </EmployeeWorkspaceSection>
      </div>

      {latestResult ? (
        <EmployeeWorkspaceSection title="Последний результат" tone="default">
          <div className="rounded-xl bg-slate-50 px-4 py-4 shadow-[inset_0_0_0_1px_rgba(15,23,42,0.08)]">
            <p className="line-clamp-3 text-sm leading-6 text-slate-700">{businessResultPrimaryText(latestResult) || 'Результат сохранён и доступен в истории запуска.'}</p>
            <Button type="button" variant="outline" className="mt-3 min-h-10" onClick={onOpenResults}>Открыть результат</Button>
          </div>
        </EmployeeWorkspaceSection>
      ) : details?.runs?.[0]?.status === 'completed' ? (
        <EmployeeWorkspaceSection title="Последний результат" tone="attention">
          <div className="text-sm leading-6 text-slate-700">
            Сотрудник завершил тест, но не сохранил текст результата. Уточните формат результата и запустите тест ещё раз.
          </div>
        </EmployeeWorkspaceSection>
      ) : null}

      {story.attention.length ? (
        <EmployeeWorkspaceSection title="Требует вашего внимания" tone={story.state === 'error' ? 'error' : 'attention'}>
          <div className="grid gap-2">
            {story.attention.map((item) => (
              <div key={item.key} className="rounded-xl bg-white/70 px-3 py-3 text-sm leading-6 shadow-[inset_0_0_0_1px_rgba(15,23,42,0.08)]">
                <div className="font-semibold text-slate-950">{item.title}</div>
                <div className="mt-1 opacity-80">{item.description}</div>
              </div>
            ))}
          </div>
        </EmployeeWorkspaceSection>
      ) : null}

    </div>
  );
};

export const EmployeeAgentScenarioPanel = ({
  blueprint,
  details,
  actionLoading,
  onRebuildScenario,
}: {
  blueprint: AgentBlueprint;
  details: AgentBlueprintDetails | null;
  actionLoading: boolean;
  onRebuildScenario: () => void;
}) => {
  const contract = details?.execution_contract;
  const working = contract?.candidate || contract?.active;
  const inputs = Object.entries(working?.inputs_schema?.properties || {});
  const approvals = working?.approval_boundaries || [];
  const expectedProperties = recordValue(working?.expected_result?.properties);
  const resultFields = Object.keys(expectedProperties || working?.expected_result || {}).filter((key) => !['schema', 'trigger', 'schedule', 'type', 'properties'].includes(key));
  const businessResultFields = resultFields.filter((key) => !['approval_required', 'artifacts', 'result'].includes(key));
  const savedResultDescription = businessResultFields.length
    ? `${businessResultFields.map((key) => resultFieldLabels[key] || humanizeMeta(key)).join(', ')}. История выполненных шагов сохраняется автоматически.`
    : 'Готовый результат и материалы этой работы. История выполненных шагов сохраняется автоматически.';
  const sourceLabels = (working?.sources || []).map((source) => {
    if (typeof source === 'string') return connectorLabel(source);
    const item = recordValue(source);
    return connectorLabel(String(item?.label || item?.provider || item?.key || 'Источник данных'));
  });
  const connectionLabels = Object.keys(working?.connections || {}).map((key) => connectorLabel(key));
  const sources = Array.from(new Set([...sourceLabels, ...connectionLabels]));
  const mode = buildAgentUserMode(blueprint, details);
  return (
    <div className="space-y-4 max-w-5xl">
      {contract?.has_unpublished_changes ? (
        <div className="flex flex-col gap-3 rounded-xl bg-amber-50 px-4 py-3 text-sm leading-6 text-amber-950 ring-1 ring-amber-200 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="font-semibold">Есть сценарий для проверки</div>
            <div>{contract.active ? 'Рабочие запуски продолжат использовать прежнюю версию, пока вы явно не включите изменения.' : 'Сначала проверьте сценарий на примере, затем явно включите его в работу.'}</div>
          </div>
          <Button type="button" variant="outline" className="min-h-10 shrink-0 bg-white" onClick={onRebuildScenario} disabled={actionLoading}>
            {actionLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
            Обновить по цели
          </Button>
        </div>
      ) : (
        <div className="flex justify-end">
          <Button type="button" variant="outline" className="min-h-10" onClick={onRebuildScenario} disabled={actionLoading}>
            {actionLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
            Обновить сценарий по цели
          </Button>
        </div>
      )}
      <EmployeeWorkspaceSection title="Исходное поручение">
        <p className="whitespace-pre-wrap text-base leading-7 text-slate-800 [text-wrap:pretty]">{contract?.original_request || blueprint.description || 'Полное поручение не сохранилось у этого старого агента.'}</p>
        {!contract?.description_complete ? <p className="mt-2 text-sm text-amber-800">Описание собрано из старой версии и может быть неполным.</p> : null}
      </EmployeeWorkspaceSection>
      <div className="grid gap-4 lg:grid-cols-2">
        <EmployeeWorkspaceSection title="Рабочая цель">
          <p className="text-sm leading-6 text-slate-700">{working?.goal || blueprint.active_goal || blueprint.latest_goal || blueprint.description}</p>
        </EmployeeWorkspaceSection>
        <EmployeeWorkspaceSection title="Когда запускается">
          <div className="text-sm font-semibold text-slate-900">{mode.label}</div>
          <div className="mt-1 text-sm leading-6 text-slate-600">{working?.schedule?.time ? `${working.schedule.time} · ${working.schedule.timezone}` : mode.description}</div>
        </EmployeeWorkspaceSection>
      </div>
      <EmployeeWorkspaceSection title="Источники и доступы">
        {sources.length ? <div className="flex flex-wrap gap-2">{sources.map((source) => <span key={source} className="rounded-full bg-sky-50 px-3 py-1.5 text-sm font-medium text-sky-800 ring-1 ring-sky-200">{source}</span>)}</div> : <p className="text-sm text-slate-600">Агент использует данные LocalOS и введённые параметры.</p>}
      </EmployeeWorkspaceSection>
      <EmployeeWorkspaceSection title="Как выполняется">
        <div className="grid gap-2">
          {(working?.steps || []).map((step, index) => (
            <div key={step.key || index} className="flex min-h-12 items-center gap-3 rounded-xl bg-slate-50 px-3 py-2 ring-1 ring-slate-200">
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-slate-900 text-xs font-semibold text-white">{index + 1}</span>
              <span className="text-sm font-medium text-slate-800">{step.title || `Шаг ${index + 1}`}</span>
              {step.requires_approval ? <span className="ml-auto text-xs font-medium text-amber-700">Попросит решение</span> : null}
            </div>
          ))}
          {!working?.steps?.length ? <p className="text-sm text-amber-800">Для старой версии нет полного списка шагов. Пересоберите сценарий перед включением.</p> : null}
        </div>
      </EmployeeWorkspaceSection>
      <div className="grid gap-4 lg:grid-cols-2">
        <EmployeeWorkspaceSection title="Что получает на вход">
          {inputs.length ? <ul className="space-y-2 text-sm text-slate-700">{inputs.map(([key, field]) => <li key={key}><span className="font-semibold text-slate-900">{field.title || key}</span>{field.description ? ` — ${field.description}` : ''}</li>)}</ul> : <p className="text-sm text-slate-600">Дополнительные параметры не требуются.</p>}
        </EmployeeWorkspaceSection>
        <EmployeeWorkspaceSection title="Что сохраняет">
          <p className="text-sm leading-6 text-slate-700">{savedResultDescription}</p>
        </EmployeeWorkspaceSection>
      </div>
      <EmployeeWorkspaceSection title="Ручной контроль" tone={approvals.length ? 'attention' : 'quiet'}>
        <p className="text-sm leading-6 text-slate-700">{approvals.length ? `Агент остановится перед: ${approvals.map((item) => item.title || 'внешним действием').join(', ')}.` : 'Сценарий не выполняет внешние действия без отдельного подтверждения.'}</p>
      </EmployeeWorkspaceSection>
    </div>
  );
};

export const AgentCockpitPanel = ({
  blueprints,
  systemAgents,
  migrationPlan,
  migrationStats,
  migrationNotice,
  actionLoading,
  onApplyMigration,
  onOpenLegacySettings,
}: {
  blueprints: AgentBlueprint[];
  systemAgents: Array<{ key: string; title: string; description: string; icon: typeof Bot; enabled: boolean }>;
  migrationPlan: LegacyMigrationPlan | null;
  migrationStats: {
    totalLegacyAgents: number;
    linkedVoices: number;
    needsBlueprint: number;
    archiveCandidates: number;
    deprecatedFieldsPresent: number;
    legacyWorkflowPresent: number;
  };
  migrationNotice: string;
  actionLoading: boolean;
  onApplyMigration: () => void;
  onOpenLegacySettings: () => void;
}) => {
  const activeBlueprints = blueprints.filter((item) => getAgentListStatus(item) === 'active').length;
  const pendingBlueprints = blueprints.filter((item) => getAgentListStatus(item) === 'needs_approval').length;
  const deprecatedFields = migrationPlan?.business_settings?.fields || {};
  return (
    <div className="space-y-4">
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <CockpitTile icon={Bot} label="Агенты продукта" value={`${activeBlueprints}/${blueprints.length}`} hint="включены / всего" />
        <CockpitTile icon={ShieldCheck} label="Ручные решения" value={String(pendingBlueprints)} hint="агенты ждут человека" tone={pendingBlueprints ? 'warning' : 'default'} />
        <CockpitTile icon={RefreshCw} label="Старые обёртки" value={String(migrationStats.needsBlueprint)} hint={`${migrationStats.linkedVoices} голосов привязано`} tone={migrationStats.needsBlueprint ? 'warning' : 'default'} />
        <CockpitTile icon={AlertTriangle} label="Устаревшие поля" value={String(migrationStats.deprecatedFieldsPresent)} hint="старые настройки бизнеса" tone={migrationStats.deprecatedFieldsPresent ? 'warning' : 'default'} />
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(20rem,0.75fr)]">
        <div className="rounded-2xl border border-slate-200 bg-white p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="text-sm font-semibold text-slate-950">Состояние миграции</div>
              <div className="mt-1 text-sm leading-6 text-slate-600">
                Старые AIAgents остаются голосом и стилем. Активная логика агента хранится в версиях blueprint.
              </div>
            </div>
            <Button type="button" onClick={onApplyMigration} disabled={actionLoading || !migrationStats.needsBlueprint}>
              {actionLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
              Применить миграцию
            </Button>
          </div>
          {migrationNotice ? (
            <div className="mt-3 rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-900">
              {migrationNotice}
            </div>
          ) : null}
          <div className="mt-4 grid gap-2 md:grid-cols-2">
            {(migrationPlan?.legacy_agents || []).slice(0, 6).map((agent) => (
              <div key={agent.agent_id || agent.name} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="truncate font-medium text-slate-950">{agent.name || 'Старый голос'}</div>
                    <div className="mt-1 text-xs text-slate-500">{agent.reason || 'решение миграции'}</div>
                  </div>
                  <StatusBadge status={agent.action === 'use_as_persona' ? 'active' : agent.action === 'create_blueprint_candidate' ? 'needs_approval' : 'paused'} />
                </div>
                {agent.legacy_workflow?.present ? (
                  <div className="mt-2 rounded-md border border-amber-200 bg-amber-50 px-2 py-1 text-xs text-amber-900">
                    AIAgents.workflow: {agent.legacy_workflow.status || 'deprecated'}
                  </div>
                ) : null}
              </div>
            ))}
          </div>
        </div>

        <div className="space-y-4">
          <div className="rounded-2xl border border-slate-200 bg-white p-4">
            <div className="text-sm font-semibold text-slate-950">Устаревшие настройки бизнеса</div>
            <div className="mt-3 space-y-2">
              {Object.entries(deprecatedFields).map(([field, info]) => (
                <div key={field} className="flex items-center justify-between gap-3 rounded-lg bg-slate-50 px-3 py-2 text-xs">
                  <div>
                    <div className="font-medium text-slate-800">{field}</div>
                    <div className="text-slate-500">{info.target || 'agent_blueprints'}</div>
                  </div>
                  <StatusBadge status={info.present ? 'needs_approval' : 'completed'} />
                </div>
              ))}
            </div>
          </div>
          <div className="grid gap-3">
            {systemAgents.map((agent) => (
              <SystemAgentCard
                key={agent.key}
                title={agent.title}
                description={agent.description}
                icon={agent.icon}
                enabled={agent.enabled}
                onConfigure={onOpenLegacySettings}
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export const CockpitTile = ({
  icon: Icon,
  label,
  value,
  hint,
  tone = 'default',
}: {
  icon: typeof Bot;
  label: string;
  value: string;
  hint: string;
  tone?: 'default' | 'warning';
}) => (
  <div className={cn('rounded-2xl border p-4', tone === 'warning' ? 'border-amber-200 bg-amber-50' : 'border-slate-200 bg-white')}>
    <div className="flex items-center justify-between gap-3">
      <div className="text-xs font-semibold uppercase text-slate-500">{label}</div>
      <Icon className={cn('h-4 w-4', tone === 'warning' ? 'text-amber-700' : 'text-slate-500')} />
    </div>
    <div className="mt-2 text-2xl font-semibold text-slate-950">{value}</div>
    <div className="mt-1 text-xs text-slate-500">{hint}</div>
  </div>
);

export const AgentSummaryPill = ({ label, value, tone = 'default' }: { label: string; value: string; tone?: 'default' | 'warning' }) => (
  <div className={cn('rounded-lg px-3 py-2 ring-1', tone === 'warning' ? 'bg-amber-50 text-amber-900 ring-amber-200' : 'bg-slate-50 text-slate-700 ring-slate-200')}>
    <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">{label}</div>
    <div className="mt-1 truncate text-xs font-medium">{value}</div>
  </div>
);

export const PersonaAgentCard = ({ agent, onConfigure }: { agent: PersonaAgent; onConfigure: () => void }) => (
  <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
    <div className="flex items-start justify-between gap-3">
      <div className="min-w-0">
        <div className="truncate text-sm font-semibold text-slate-950">{agent.name || 'Persona agent'}</div>
        <div className="mt-1 text-xs font-medium text-slate-500">Голос и стиль общения</div>
      </div>
      <span className={cn('rounded-full px-2.5 py-1 text-xs font-medium ring-1', agent.is_active ? 'bg-emerald-50 text-emerald-700 ring-emerald-200' : 'bg-slate-100 text-slate-600 ring-slate-200')}>
        {agent.is_active ? 'Включён' : 'Выключен'}
      </span>
    </div>
    <div className="mt-3 line-clamp-3 text-sm leading-6 text-slate-600">
      {agent.description || agent.task || agent.identity || 'Настраивает тон, стиль и ограничения общения. Не является отдельной логикой запуска.'}
    </div>
    <div className="mt-4 flex justify-end">
      <Button type="button" size="sm" variant="outline" onClick={onConfigure}>
        Открыть настройки
      </Button>
    </div>
  </div>
);
