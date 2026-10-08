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
  AgentMiniMetric
} from './employee';
import {
  connectionActionTone,
  providerRouteLabel,
  providerActionDescription,
  ProviderActionPill
} from './connections';

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

export const BuilderRequiredConnectionsPanel = ({
  preview,
  selectedProviderRoutes = {},
  onSelectProviderRoute,
}: {
  preview?: AgentBuilderPreview | null;
  selectedProviderRoutes?: Record<string, string>;
  onSelectProviderRoute?: (bindingKey: string, routeProvider: string) => void;
}) => {
  const planItems = preview?.connection_plan?.items || [];
  const readinessServices = preview?.connection_readiness?.services || [];
  const answerBindings = preview?.connection_answer_bindings || {};
  const items = planItems.length
    ? planItems.map((item) => ({
      key: item.key || '',
      provider: item.provider || '',
      title: item.title || connectorLabel(item.provider),
      capability: item.capability || item.trigger || item.direction || '',
      action: item.action || '',
      status: item.binding_status || '',
      route_summary: item.route_summary || item.explanation || '',
      missing_config: item.missing_config || [],
      provider_routes: item.provider_routes || [],
      recommended_route: item.recommended_route || null,
      recommended_route_reason: item.recommended_route_reason || '',
      policy_summary: item.policy_summary || '',
    }))
    : readinessServices.map((service) => ({
      key: service.key || '',
      provider: service.provider || '',
      title: service.title || connectorLabel(service.provider),
      capability: service.capability || '',
      action: service.action || service.status || '',
      status: service.status || '',
      route_summary: service.route_summary || service.explanation || '',
      missing_config: service.missing_config || [],
      provider_routes: [],
      recommended_route: service.recommended_route || null,
      recommended_route_reason: service.recommended_route_reason || '',
      policy_summary: '',
    }));
  if (!preview || !items.length) {
    return null;
  }
  const actionable = items.filter((item) => !['ready', 'native_ready'].includes(item.action));
  const blocked = actionable.some((item) => ['forbidden', 'unsupported', 'planned_provider'].includes(item.action));
  const ready = actionable.length === 0;
  const toneClass = blocked
    ? 'border-rose-200 bg-rose-50 text-rose-950'
    : ready
    ? 'border-emerald-200 bg-emerald-50 text-emerald-950'
    : 'border-amber-200 bg-amber-50 text-amber-950';
  const badgeText = ready
    ? 'доступы готовы'
    : blocked
    ? 'есть блокер'
    : `${actionable.length} нужно закрыть`;
  return (
    <div className={cn('mt-3 rounded-xl border px-3 py-3 text-xs leading-5', toneClass)}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="font-semibold">Доступы перед созданием агента</div>
          <div className="mt-1 max-w-2xl">
            LocalOS понял, какие сервисы нужны агенту. Ресурс из диалога сохраняется отдельно от доступа: перед тестом нужно выбрать способ подключения или готовое подключение.
          </div>
        </div>
        <span className="rounded-full bg-white px-2 py-0.5 font-medium ring-1 ring-current/10">
          {badgeText}
        </span>
      </div>

      <div className="mt-3 grid gap-2 md:grid-cols-2">
        {items.slice(0, 4).map((item) => {
          const bindingKey = item.key || item.provider || '';
          const recommendedProvider = item.recommended_route?.provider || '';
          const selected = Boolean(bindingKey && recommendedProvider && selectedProviderRoutes[bindingKey] === recommendedProvider);
          const resourceFacts = connectionResourceFacts(item.provider, bindingKey ? answerBindings[bindingKey] : null);
          const missingConfig = item.missing_config || [];
          return (
            <div key={`${bindingKey}-${item.provider}-${item.capability}`} className="rounded-lg bg-white px-3 py-2 text-slate-700 ring-1 ring-current/10">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="font-medium text-slate-950">{item.title || connectorLabel(item.provider)}</div>
	                  <div className="mt-0.5 text-[11px] leading-4 text-slate-500">{userFacingAgentTechText(humanizeMeta(item.capability || item.provider || 'binding'))}</div>
                </div>
                <span className={cn('rounded-full px-2 py-0.5 text-[11px] font-medium ring-1', connectionActionTone(item.action || item.status || ''))}>
                  {builderConnectionCardStatus(item.action, selected)}
                </span>
              </div>
              {resourceFacts.length ? (
                <div className="mt-2 rounded-lg bg-emerald-50 px-2 py-1.5 text-[11px] leading-4 text-emerald-800 ring-1 ring-emerald-100">
                  Ресурс из диалога: {resourceFacts.join(' · ')}
                </div>
              ) : null}
              <div className="mt-2 text-[11px] leading-4 text-slate-600">
	                {userFacingAgentTechText(item.route_summary || builderConnectionCardHint(item.action, item.provider))}
              </div>
              {missingConfig.length ? (
                <div className="mt-2 rounded-lg bg-amber-50 px-2 py-1.5 text-[11px] leading-4 text-amber-800 ring-1 ring-amber-100">
	                  Не хватает настроек: {missingConfig.map((item) => userFacingAgentTechText(humanizeMeta(item))).join(', ')}
                </div>
              ) : null}
              <RecommendedProviderRouteNote
                route={item.recommended_route}
                reason={item.recommended_route_reason}
              />
              {item.policy_summary ? (
                <div className="mt-2 rounded-lg bg-slate-50 px-2 py-1.5 text-[11px] leading-4 text-slate-600 ring-1 ring-slate-100">
	                  {userFacingAgentTechText(item.policy_summary)}
                </div>
              ) : null}
              {item.provider_routes.length ? (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {item.provider_routes.slice(0, 4).map((route) => (
                    <ProviderActionPill
                      key={`${bindingKey}-${route.provider}-${route.role}`}
                      route={route}
                      onChoose={onSelectProviderRoute && bindingKey ? () => onSelectProviderRoute(bindingKey, route.provider || '') : undefined}
                    />
                  ))}
                </div>
              ) : null}
              {bindingKey && recommendedProvider && onSelectProviderRoute && !selected ? (
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  className="mt-2 h-7 bg-white px-2 text-[11px]"
                  onClick={() => onSelectProviderRoute(bindingKey, recommendedProvider)}
                >
                  Использовать {connectorLabel(recommendedProvider)}
                </Button>
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
};

export const builderConnectionCardStatus = (action: string, selected: boolean) => {
  if (selected) {
    return 'способ выбран';
  }
  if (action === 'ready' || action === 'native_ready') {
    return 'готово';
  }
  if (action === 'choose_existing') {
    return 'выбрать доступ';
  }
  if (action === 'choose_route') {
    return 'выбрать способ';
  }
  if (action === 'connect_required') {
    return 'нужен способ';
  }
  if (action === 'planned_provider') {
    return 'позже';
  }
  if (action === 'forbidden' || action === 'unsupported') {
    return 'невозможно';
  }
  return humanizeMeta(action || 'проверить');
};

export const builderConnectionCardHint = (action: string, provider: string) => {
  if (action === 'ready' || action === 'native_ready') {
    return 'Этот доступ уже можно использовать в тесте без отправки.';
  }
  if (action === 'choose_existing') {
    return 'У бизнеса есть несколько подходящих подключений. Выберите одно для этого агента.';
  }
  if (action === 'choose_route') {
    return 'Выберите, как агенту безопасно доставлять результат или получать данные. Обычно подходит рекомендованный способ LocalOS.';
  }
  if (action === 'connect_required') {
    return `${connectorLabel(provider)} нужен агенту, но доступ ещё не выбран.`;
  }
  if (action === 'planned_provider') {
    return 'Этот способ подключения запланирован, но пока недоступен для включения агента.';
  }
  return 'LocalOS проверит этот доступ перед тестом без отправки.';
};

export const compilerPolicyItemLabel = (item?: AgentCompilerPolicyItem | null): string => {
  if (!item) {
    return '';
  }
  return String(
    item.title
    || item.message
    || item.reason
    || item.request
    || item.capability
    || item.provider
    || item.type
    || item.key
    || item.text
    || '',
  ).trim();
};

export const compilerPlanTriggerLabel = (trigger?: string) => {
  const value = String(trigger || '').trim();
  if (!value || value === 'manual.run') {
    return 'Запуск вручную';
  }
  if (value.includes('daily')) {
    const timeMatch = value.match(/at\(([^)]+)\)/);
    return `Каждый день${timeMatch?.[1] ? ` в ${timeMatch[1]}` : ''}`;
  }
  if (value.includes('schedule')) {
    return 'По расписанию';
  }
  if (value.includes('message') || value.includes('telegram')) {
    return 'Когда приходит сообщение';
  }
  return humanizeMeta(value);
};

export const compilerPlanStepCopy = (item: AgentCompilerPolicyItem, index: number) => {
  const capability = String(item.capability || item.key || item.type || '').trim();
  const provider = String(item.provider || '').trim();
  const rawLabel = compilerPolicyItemLabel(item);

  if (capability === 'google_sheets.read_rows' || provider === 'google_sheets') {
    return {
      title: 'Прочитать данные из Google Sheets',
      detail: 'Агент возьмёт строки из выбранной таблицы и вкладки. На этом шаге он только читает данные.',
    };
  }
  if (capability === 'communications.draft' || capability.includes('draft')) {
    return {
      title: 'Подготовить черновик сообщения',
      detail: 'LocalOS соберёт текст по заданному стилю. Это ещё не отправка наружу.',
    };
  }
  if (capability.includes('send') || capability.includes('publish')) {
    return {
      title: 'Попросить подтверждение перед отправкой',
      detail: 'Внешнее действие не выполняется автоматически: пользователь должен одобрить результат.',
    };
  }
  if (provider === 'telegram' || capability.includes('telegram')) {
    return {
      title: 'Передать результат в Telegram',
      detail: 'Сообщение будет доставлено через выбранный Telegram-канал после нужного подтверждения.',
    };
  }
  return {
    title: rawLabel || `Шаг ${index + 1}`,
    detail: item.reason || item.message || item.text || 'LocalOS выполнит этот шаг как часть проверяемого сценария.',
  };
};

export const builderPreviewDataText = (preview: AgentBuilderPreview | null, taskText: string) => {
  const labels: string[] = [];
  const seen = new Set<string>();
  const addLabel = (label: string) => {
    const cleanLabel = label.trim();
    const key = cleanLabel.toLowerCase();
    if (!cleanLabel || seen.has(key)) {
      return;
    }
    seen.add(key);
    labels.push(cleanLabel);
  };
  if (taskText.toLowerCase().includes('отзыв')) {
    addLabel('отзывы компании');
  }
  (preview?.data_sources || []).forEach((item) => addLabel(humanizeMeta(item)));
  return labels.join(', ') || 'ещё не выбрано';
};

export const BuilderCompilerPolicyReviewPanel = ({
  review,
  workflowDraft,
  approvalPoints,
  unsupportedRequests,
  accepted,
  onAccept,
}: {
  review?: AgentCompilerPolicyReview;
  workflowDraft?: AgentCompilerWorkflowDraft;
  approvalPoints?: AgentCompilerPolicyItem[];
  unsupportedRequests?: AgentCompilerPolicyItem[];
  accepted?: boolean;
  onAccept?: () => void;
}) => {
  const draft = workflowDraft || review?.workflow_draft || {};
  const steps = Array.isArray(draft.steps) ? draft.steps : [];
  const approvals = approvalPoints || review?.approval_points || [];
  const blockers = unsupportedRequests || review?.unsupported_requests || [];
  const hasContent = Boolean(
    review
    || steps.length
    || approvals.length
    || blockers.length
    || draft.trigger,
  );
  if (!hasContent) {
    return null;
  }
  const blocked = blockers.length > 0 || review?.status === 'blocked';
  const needsApproval = approvals.length > 0 || review?.status === 'needs_approval';
  const toneClass = blocked
    ? 'border-rose-200 bg-rose-50 text-rose-950'
    : needsApproval
    ? 'border-amber-200 bg-amber-50 text-amber-950'
    : 'border-emerald-200 bg-emerald-50 text-emerald-950';
  const badgeClass = blocked
    ? 'bg-white text-rose-700 ring-rose-200'
    : needsApproval
    ? 'bg-white text-amber-700 ring-amber-200'
    : 'bg-white text-emerald-700 ring-emerald-200';
  const statusLabel = blocked ? 'нужно изменить' : needsApproval ? 'нужны подтверждения' : 'готов к утверждению';
  const readableSteps = steps.map((step, index) => compilerPlanStepCopy(step, index));
  return (
    <div className={cn('mt-3 rounded-xl border px-3 py-3 text-sm leading-6', toneClass)}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="font-semibold">Сценарий работы агента</div>
          <div className="mt-1 max-w-2xl text-sm">
            Проверьте последовательность действий. После утверждения LocalOS сохранит её как проверяемую логику и запустит тест на примере.
          </div>
        </div>
        <span className={cn('rounded-full px-2 py-0.5 font-medium ring-1', badgeClass)}>
          {statusLabel}
        </span>
      </div>

      <div className="mt-3 grid gap-2 md:grid-cols-2">
        <AgentMiniMetric label="Когда запускать" value={compilerPlanTriggerLabel(draft.trigger)} />
        <AgentMiniMetric label="Контроль перед внешними действиями" value={approvals.length ? `${approvals.length} подтвержд.` : 'уточнить в диалоге'} />
      </div>

      {readableSteps.length ? (
        <div className="mt-3 rounded-lg bg-white p-3 text-slate-700 ring-1 ring-current/10">
          <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Что будет делать агент</div>
          <div className="mt-3 space-y-3">
            {readableSteps.slice(0, 5).map((step, index) => {
              return (
                <div key={`${step.title}-${index}`} className="grid grid-cols-[2rem_minmax(0,1fr)] gap-3">
                  <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-slate-100 text-sm font-semibold text-slate-700">
                    {index + 1}
                  </span>
                  <div className="min-w-0">
                    <div className="font-semibold text-slate-950">{step.title}</div>
                    <div className="mt-0.5 text-sm leading-6 text-slate-600">{step.detail}</div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      ) : null}

      {approvals.length ? (
        <div className="mt-3 rounded-lg bg-white px-3 py-2 text-amber-950 ring-1 ring-current/10">
          <div className="font-semibold">Что агент спросит у пользователя</div>
          <div className="mt-2 space-y-1">
            {approvals.slice(0, 3).map((item, index) => (
              <div key={`${compilerPolicyItemLabel(item)}-${index}`} className="flex gap-2 text-sm leading-6">
                <ShieldCheck className="mt-1 h-4 w-4 shrink-0" />
                <span>{compilerPolicyItemLabel(item) || 'Подтверждение перед внешним действием'}</span>
              </div>
            ))}
          </div>
        </div>
      ) : !blockers.length ? (
        <div className="mt-3 rounded-lg bg-white px-3 py-2 text-slate-700 ring-1 ring-current/10">
          <div className="font-semibold text-slate-950">Что нужно уточнить в диалоге</div>
          <div className="mt-1 text-sm leading-6">
            Подтвердите расписание и правило отправки: если агент должен публиковать или отправлять сообщение наружу, LocalOS должен сначала показать черновик и спросить разрешение.
          </div>
        </div>
      ) : null}

      {blockers.length ? (
        <div className="mt-3 rounded-lg bg-white px-3 py-2 text-rose-950 ring-1 ring-current/10">
          <div className="font-semibold">Что нужно изменить в логике</div>
          <div className="mt-2 space-y-1">
            {blockers.slice(0, 3).map((item, index) => (
              <div key={`${compilerPolicyItemLabel(item)}-${index}`} className="flex gap-2 text-[11px] leading-4">
                <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                <span>{compilerPolicyItemLabel(item) || 'Часть запроса выходит за правила безопасности LocalOS'}</span>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {!blockers.length && onAccept ? (
        <div className={cn(
          'mt-3 rounded-lg px-3 py-2 ring-1',
          accepted ? 'bg-white text-emerald-800 ring-emerald-200' : 'bg-white text-slate-700 ring-slate-200',
        )}>
          <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
            <div className="text-[11px] leading-4">
              {accepted
                ? 'Сценарий утверждён. LocalOS сможет создать черновик агента и сохранить проверяемую логику.'
                : 'Если последовательность верная, утвердите сценарий в диалоге.'}
            </div>
            <Button type="button" size="sm" variant={accepted ? 'outline' : 'default'} onClick={onAccept} disabled={accepted}>
              <CheckCircle2 className="mr-2 h-4 w-4" />
              {accepted ? 'Сценарий утверждён' : 'Утвердить сценарий'}
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
};

export const RecommendedProviderRouteNote = ({
  route,
  reason,
}: {
  route?: AgentProviderRoute | null;
  reason?: string;
}) => {
  if (!route && !reason) {
    return null;
  }
  return (
    <div className="mt-2 rounded-lg bg-white px-2 py-1.5 text-[11px] leading-4 text-slate-700 ring-1 ring-slate-200">
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="font-medium text-slate-950">Рекомендуемый способ</span>
        {route ? <ProviderActionPill route={route} /> : null}
      </div>
      {reason ? <div className="mt-1">{userFacingAgentTechText(reason)}</div> : null}
    </div>
  );
};

export const builderConnectionStatusCopy = (service: AgentConnectionReadinessService) => {
  const action = String(service.action || service.status || '').trim();
  if (action === 'ready' || action === 'native_ready') {
    return 'Можно использовать';
  }
  if (action === 'choose_existing') {
    return 'Выберите доступ';
  }
  if (action === 'choose_route') {
    return 'Выберите способ';
  }
  if (action === 'planned_provider') {
    return 'Пока недоступно';
  }
  if (action === 'forbidden' || action === 'unsupported') {
    return 'Невозможно';
  }
  if (action === 'connect_required') {
    return 'Нужно подключить';
  }
  return service.action_label || humanizeMeta(action || 'проверить');
};

export const builderConnectionNextStepCopy = (service: AgentConnectionReadinessService, selected: boolean) => {
  if (selected) {
    return 'Этот способ будет сохранён в плане агента.';
  }
  const routeDescription = providerActionDescription(service.recommended_route || null);
  if (routeDescription) {
    return routeDescription;
  }
  if (service.connections?.length) {
    return 'Можно использовать уже сохранённое подключение бизнеса.';
  }
  if (service.provider_route_cta) {
	    return userFacingAgentTechText(service.provider_route_cta);
  }
	  return userFacingAgentTechText(service.route_summary || service.explanation || 'LocalOS проверит доступ перед тестом без отправки.');
};

export const BuilderServiceIntelligencePanel = ({
  intelligence,
  selectedProviderRoutes = {},
  onSelectProviderRoute,
}: {
  intelligence?: AgentServiceIntelligence;
  selectedProviderRoutes?: Record<string, string>;
  onSelectProviderRoute?: (bindingKey: string, routeProvider: string) => void;
}) => {
  const items = intelligence?.items || [];
  if (!intelligence || !items.length) {
    return null;
  }
  const blocked = items.some((item) => item.state === 'impossible');
  const needsChoice = items.some((item) => item.state === 'multiple_routes');
  const needsConnection = items.some((item) => item.state === 'connectable' || item.state === 'planned');
  return (
    <div className={cn(
      'mt-3 rounded-xl border px-3 py-3 text-xs leading-5',
      blocked ? 'border-rose-200 bg-rose-50 text-rose-950' : '',
      !blocked && (needsChoice || needsConnection) ? 'border-amber-200 bg-amber-50 text-amber-950' : '',
      !blocked && !needsChoice && !needsConnection ? 'border-emerald-200 bg-emerald-50 text-emerald-950' : '',
    )}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="font-semibold">Что возможно</div>
	          <div className="mt-1 max-w-2xl">{userFacingAgentTechText(intelligence.headline || 'LocalOS сопоставил задачу с доступными сервисами и правилами безопасности.')}</div>
        </div>
        <span className="rounded-full bg-white px-2 py-0.5 font-medium ring-1 ring-current/10">
          {intelligence.can_activate ? 'можно проверить' : intelligence.can_create_draft ? 'можно создать черновик' : 'нельзя создать'}
        </span>
      </div>
      <div className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
        {items.slice(0, 8).map((item) => {
          const state = item.state || '';
          const provider = item.recommended_provider || item.provider || '';
          const bindingKey = item.kind === 'binding' ? item.key || '' : '';
          const route = item.recommended_route || null;
          const selected = Boolean(bindingKey && provider && selectedProviderRoutes[bindingKey] === provider);
          const canChooseRoute = Boolean(
            bindingKey
            && provider
            && route
            && ['connectable', 'multiple_routes'].includes(state)
            && ['available', 'connected', 'manual'].includes(String(route.state || route.status || ''))
            && route.provider_action?.available !== false
            && onSelectProviderRoute,
          );
          return (
            <div key={`${item.kind || 'item'}-${item.key || item.provider || item.capability}`} className="rounded-lg bg-white px-3 py-2 ring-1 ring-current/10">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <div className="font-medium text-slate-950">{item.service_label || connectorLabel(item.provider)}</div>
	                  {item.capability ? <div className="mt-0.5 text-[11px] leading-4 text-slate-500">{userFacingAgentTechText(humanizeMeta(item.capability))}</div> : null}
                </div>
                <span className={cn('rounded-full px-2 py-0.5 text-[11px] font-medium ring-1', serviceIntelligenceTone(state))}>
	                  {userFacingAgentTechText(item.state_label || humanizeMeta(state || 'проверить'))}
                </span>
              </div>
              <div className="mt-1 text-[11px] leading-4 text-slate-600">
	                {userFacingAgentTechText(item.explanation || 'LocalOS проверит этот сервис перед тестом без отправки.')}
              </div>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {provider ? (
                  <span className="rounded-full bg-sky-50 px-2 py-0.5 text-[11px] text-sky-700 ring-1 ring-sky-100">
	                    {userFacingAgentTechText(item.recommended_label || connectorLabel(provider))}
                  </span>
                ) : null}
                {item.connection_count ? (
                  <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] text-emerald-700 ring-1 ring-emerald-100">
                    {item.connection_count} доступ
                  </span>
                ) : null}
                {item.next_action ? (
                  <span className="rounded-full bg-slate-50 px-2 py-0.5 text-[11px] text-slate-600 ring-1 ring-slate-200">
	                    {userFacingAgentTechText(humanizeMeta(item.next_action))}
                  </span>
                ) : null}
              </div>
              {canChooseRoute ? (
                <Button
                  type="button"
                  size="sm"
                  variant={selected ? 'default' : 'outline'}
                  className={cn('mt-2 h-7 px-2 text-[11px]', selected ? '' : 'bg-white')}
                  onClick={() => onSelectProviderRoute?.(bindingKey, provider)}
                >
	                  {selected ? 'Способ выбран' : userFacingAgentTechText(`Использовать ${connectorLabel(provider)}`)}
                </Button>
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
};

export const serviceIntelligenceTone = (state: string) => {
  if (state === 'already_connected' || state === 'localos_native' || state === 'available_route') {
    return 'bg-emerald-50 text-emerald-700 ring-emerald-200';
  }
  if (state === 'multiple_routes') {
    return 'bg-sky-50 text-sky-700 ring-sky-200';
  }
  if (state === 'planned') {
    return 'bg-slate-50 text-slate-600 ring-slate-200';
  }
  if (state === 'impossible') {
    return 'bg-rose-50 text-rose-700 ring-rose-200';
  }
  return 'bg-amber-50 text-amber-700 ring-amber-200';
};

export const BuilderConnectionReadinessPanel = ({
  readiness,
  answerBindings = {},
  selectedProviderRoutes = {},
  acceptedProviderRoutes = false,
  missingProviderRouteKeys = [],
  onAcceptProviderRoutes,
  onSelectProviderRoute,
}: {
  readiness?: AgentConnectionReadiness;
  answerBindings?: Record<string, Record<string, unknown>>;
  selectedProviderRoutes?: Record<string, string>;
  acceptedProviderRoutes?: boolean;
  missingProviderRouteKeys?: string[];
  onAcceptProviderRoutes?: () => void;
  onSelectProviderRoute?: (bindingKey: string, routeProvider: string) => void;
}) => {
  const services = readiness?.services || [];
  const forbidden = readiness?.forbidden || [];
  const unsupported = readiness?.unsupported || [];
  if (!readiness || (!services.length && !forbidden.length && !unsupported.length)) {
    return null;
  }
  const blocked = Boolean((readiness.blocked_count || 0) > 0 || forbidden.length || unsupported.length);
  const needsAction = Boolean((readiness.missing_count || 0) > 0 || (readiness.choice_count || 0) > 0);
  const ready = !blocked && !needsAction;
  const selectableRouteKeys = services
    .map((service) => service.key || '')
    .filter((key) => key && selectedProviderRoutes[key]);
  const canConfirmRoutes = Boolean(selectableRouteKeys.length && !missingProviderRouteKeys.length && onAcceptProviderRoutes);
  const readyCopy = ready
    ? 'Все нужные сервисы можно использовать. После создания агента запустите тест без отправки.'
    : needsAction
    ? 'Выберите, как LocalOS будет подключаться к нужным сервисам.'
    : 'LocalOS проверяет, какие сервисы доступны для этого агента.';
  return (
    <div className={cn(
      'mt-3 rounded-xl border px-3 py-3 text-xs leading-5',
      blocked ? 'border-rose-200 bg-rose-50 text-rose-950' : '',
      needsAction ? 'border-amber-200 bg-amber-50 text-amber-950' : '',
      ready ? 'border-emerald-200 bg-emerald-50 text-emerald-950' : '',
      !blocked && !needsAction && !ready ? 'border-slate-200 bg-white text-slate-700' : '',
    )}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="font-semibold">Что нужно агенту для работы</div>
          <div className="mt-1 max-w-2xl">{readiness.description || readyCopy}</div>
        </div>
        <span className="rounded-full bg-white px-2 py-0.5 font-medium ring-1 ring-current/10">
          {readiness.title || (ready ? 'готово к preview' : 'нужны подключения')}
        </span>
      </div>
      <div className="mt-3 grid gap-2 sm:grid-cols-4">
        <AgentMiniMetric label="Нужно" value={String(readiness.required_count || 0)} />
        <AgentMiniMetric label="Готово" value={String(readiness.ready_count || 0)} />
        <AgentMiniMetric label="Выбрать" value={String((readiness.missing_count || 0) + (readiness.choice_count || 0))} />
        <AgentMiniMetric label="Блокеры" value={String(readiness.blocked_count || 0)} />
      </div>
      {services.length ? (
        <div className="mt-3 grid gap-2 md:grid-cols-2">
          {services.slice(0, 4).map((service) => (
            <div key={service.key || service.provider || service.title} className="rounded-lg bg-white px-3 py-2 ring-1 ring-current/10">
              {(() => {
                const bindingKey = service.key || '';
                const routeProvider = service.recommended_route?.provider || '';
                const selected = Boolean(bindingKey && routeProvider && selectedProviderRoutes[bindingKey] === routeProvider);
                const statusCopy = builderConnectionStatusCopy(service);
                const nextStepCopy = builderConnectionNextStepCopy(service, selected);
                const resourceFacts = connectionResourceFacts(service.provider, bindingKey ? answerBindings[bindingKey] : null);
                return (
                  <>
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <div className="font-medium text-slate-950">{service.title || connectorLabel(service.provider)}</div>
                  <div className="mt-0.5 text-[11px] leading-4 text-slate-500">{userFacingAgentTechText(humanizeMeta(service.capability || service.provider || 'service'))}</div>
                </div>
                <span className={cn('rounded-full px-2 py-0.5 text-[11px] font-medium ring-1', connectionActionTone(service.action || ''))}>
                  {statusCopy}
                </span>
              </div>
              <div className="mt-1 text-[11px] leading-4 text-slate-600">
                {nextStepCopy}
              </div>
              {resourceFacts.length ? (
                <div className="mt-2 rounded-lg bg-emerald-50 px-2 py-1.5 text-[11px] leading-4 text-emerald-800 ring-1 ring-emerald-100">
                  Поняли ресурс: {resourceFacts.join(' · ')}
                </div>
              ) : null}
              {service.provider_route_label || service.provider_route_cta ? (
                <div className="mt-2 rounded-lg bg-slate-50 px-2 py-1.5 text-[11px] leading-4 text-slate-700 ring-1 ring-slate-200">
	                  {service.provider_route_label ? `${userFacingAgentTechText(service.provider_route_label)}: ` : ''}
	                  {userFacingAgentTechText(service.provider_route_cta || providerRouteLabel(service.route_state || ''))}
                </div>
              ) : null}
              <RecommendedProviderRouteNote
                route={service.recommended_route}
                reason={service.recommended_route_reason}
              />
              {bindingKey && routeProvider && onSelectProviderRoute ? (
                <div className="mt-2">
                  <Button
                    type="button"
                    size="sm"
                    variant={selected ? 'default' : 'outline'}
                    className={cn('h-7 px-2 text-[11px]', selected ? '' : 'bg-white')}
                    onClick={() => onSelectProviderRoute(bindingKey, routeProvider)}
                  >
                    {selected ? 'Способ выбран' : 'Использовать этот способ'}
                  </Button>
                </div>
              ) : null}
              {service.connections?.length ? (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {service.connections.slice(0, 3).map((connection) => (
                    <span key={connection.id || connection.display_name} className="rounded-full bg-sky-50 px-2 py-0.5 text-[11px] text-sky-700 ring-1 ring-sky-100">
                      {connection.display_name || connectorLabel(connection.provider)}
                    </span>
                  ))}
                </div>
              ) : null}
                  </>
                );
              })()}
            </div>
          ))}
        </div>
      ) : null}
      {selectableRouteKeys.length ? (
        <div className={cn(
          'mt-3 rounded-lg bg-white px-3 py-2 ring-1',
          acceptedProviderRoutes ? 'text-emerald-800 ring-emerald-200' : missingProviderRouteKeys.length ? 'text-amber-900 ring-amber-200' : 'text-slate-700 ring-slate-200',
        )}>
          <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
            <div className="text-[11px] leading-4">
              {acceptedProviderRoutes
                ? 'Способы подключения подтверждены и будут сохранены в плане агента.'
                : missingProviderRouteKeys.length
                ? `Не выбран способ подключения для: ${missingProviderRouteKeys.join(', ')}.`
                : 'Подтвердите, что LocalOS должен использовать выбранные способы подключения для этого агента.'}
            </div>
            {onAcceptProviderRoutes ? (
              <Button
                type="button"
                size="sm"
                variant={acceptedProviderRoutes ? 'outline' : 'default'}
                disabled={acceptedProviderRoutes || !canConfirmRoutes}
                onClick={onAcceptProviderRoutes}
              >
                <CheckCircle2 className="mr-2 h-4 w-4" />
                {acceptedProviderRoutes ? 'Подключения подтверждены' : 'Подтвердить подключения'}
              </Button>
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  );
};

export const BuilderConnectionResolverPanel = ({ resolver }: { resolver?: AgentConnectionResolver }) => {
  const items = resolver?.items || [];
  if (!resolver || !items.length) {
    return null;
  }
  const blocked = Boolean((resolver.blocked_count || 0) > 0);
  const unresolved = Boolean((resolver.unresolved_count || 0) > 0);
  return (
    <div className={cn(
      'mt-3 rounded-xl border px-3 py-3 text-xs leading-5',
      blocked ? 'border-rose-200 bg-rose-50 text-rose-950' : unresolved ? 'border-amber-200 bg-amber-50 text-amber-950' : 'border-emerald-200 bg-emerald-50 text-emerald-950',
    )}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="font-semibold">Как LocalOS подключит сервисы</div>
          <div className="mt-1 max-w-2xl">{resolver.summary || 'LocalOS сопоставил части задачи с доступными сервисами и безопасными способами выполнения.'}</div>
        </div>
        <span className="rounded-full bg-white px-2 py-0.5 font-medium ring-1 ring-current/10">
          {resolver.next_action_label || resolver.title || 'проверить'}
        </span>
      </div>
      <div className="mt-3 grid gap-2 md:grid-cols-2">
        {items.slice(0, 6).map((item) => {
          const state = item.state || '';
          const route = item.recommended_route || null;
          const routeProvider = item.recommended_provider || route?.provider || '';
          return (
            <div key={item.key || `${item.provider}:${item.role}`} className="rounded-lg bg-white px-3 py-2 ring-1 ring-current/10">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <div className="text-[11px] font-semibold uppercase text-slate-500">{item.role_label || 'Сервис'}</div>
                  <div className="font-medium text-slate-950">{item.service_label || connectorLabel(item.provider)}</div>
                </div>
                <span className={cn('rounded-full px-2 py-0.5 text-[11px] font-medium ring-1', resolverStateTone(state))}>
                  {userFacingAgentTechText(item.state_label || humanizeMeta(state || 'проверить'))}
                </span>
              </div>
              <div className="mt-1 text-[11px] leading-4 text-slate-600">
                {item.explanation || 'LocalOS проверит этот сервис перед тестом без отправки.'}
              </div>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {routeProvider ? (
                  <span className="rounded-full bg-sky-50 px-2 py-0.5 text-[11px] text-sky-700 ring-1 ring-sky-100">
                    {item.recommended_label || connectorLabel(routeProvider)}
                  </span>
                ) : null}
                {item.connection_count ? (
                  <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] text-emerald-700 ring-1 ring-emerald-100">
                    {item.connection_count} доступ
                  </span>
                ) : null}
                {item.missing_config?.length ? (
                  <span className="rounded-full bg-amber-50 px-2 py-0.5 text-[11px] text-amber-700 ring-1 ring-amber-100">
                    нужны настройки
                  </span>
                ) : null}
              </div>
              {item.resolution_hint ? (
                <div className="mt-2 rounded-lg bg-slate-50 px-2 py-1.5 text-[11px] leading-4 text-slate-700 ring-1 ring-slate-200">
                  {item.resolution_hint}
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
};

export const resolverStateTone = (state: string) => {
  if (state === 'ready' || state === 'native_ready') {
    return 'bg-emerald-50 text-emerald-700 ring-emerald-200';
  }
  if (state === 'available' || state === 'choose_existing') {
    return 'bg-sky-50 text-sky-700 ring-sky-200';
  }
  if (state === 'planned_provider') {
    return 'bg-slate-50 text-slate-600 ring-slate-200';
  }
  return 'bg-amber-50 text-amber-700 ring-amber-200';
};

export const BuilderSetupFlowPanel = ({ setupFlow }: { setupFlow?: AgentBuilderSetupFlow }) => {
  const steps = Array.isArray(setupFlow?.steps) ? setupFlow.steps : [];
  if (!setupFlow || !steps.length) {
    return null;
  }
  const primaryActionLabel = {
    answer_question: 'Ответьте на вопрос слева',
    connect_service: 'Подключите сервис',
    choose_connection: 'Выберите подключение',
    top_up_balance: 'Пополните баланс',
    cannot_create: 'Такой агент недоступен',
    create_draft: 'Можно создать черновик',
  }[setupFlow.primary_action || ''] || 'Проверьте настройку';
  const nextStepTitle = userFacingAgentTechText(setupFlow.next_step_title || primaryActionLabel);
  const nextStepDescription = userFacingAgentTechText(setupFlow.next_step_description || setupFlow.post_create_description || '');
  return (
    <div className="mt-3 rounded-xl border border-slate-200 bg-white px-3 py-3 text-xs leading-5 text-slate-700">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <div className="font-semibold text-slate-950">Что дальше</div>
          <div className="mt-1 max-w-2xl text-[11px] leading-4 text-slate-500">
	            {nextStepDescription || 'LocalOS ведёт агента от описания к черновику, тесту без отправки и включению.'}
          </div>
        </div>
        <span className={cn('rounded-full px-2 py-0.5 font-medium ring-1', statusTone[setupFlow.status || 'pending'] || statusTone.pending)}>
          {nextStepTitle}
        </span>
      </div>
      <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7">
        {steps.map((step) => {
          const status = step.status || 'pending';
          const done = status === 'done' || status === 'ready';
          const active = status === 'active' || status === 'next';
          const blocked = status === 'blocked';
          return (
            <div
              key={step.key || step.label}
              className={cn(
                'min-h-24 rounded-lg px-2 py-2 ring-1',
                done ? 'bg-emerald-50 text-emerald-950 ring-emerald-100' : '',
                active ? 'bg-amber-50 text-amber-950 ring-amber-100' : '',
                blocked ? 'bg-slate-50 text-slate-500 ring-slate-200' : '',
                !done && !active && !blocked ? 'bg-slate-50 text-slate-700 ring-slate-200' : '',
              )}
            >
              <div className="flex items-center gap-1.5 font-medium">
                {done ? <CheckCircle2 className="h-3.5 w-3.5" /> : active ? <Clock3 className="h-3.5 w-3.5" /> : blocked ? <AlertTriangle className="h-3.5 w-3.5" /> : <Clock3 className="h-3.5 w-3.5" />}
	                <span>{userFacingAgentTechText(step.label || humanizeMeta(step.key || 'Шаг'))}</span>
              </div>
	              <div className="mt-1 text-[11px] leading-4 opacity-80">{userFacingAgentTechText(step.description || statusLabels[status] || humanizeMeta(status))}</div>
            </div>
          );
        })}
      </div>
      {setupFlow.activation_blockers?.length ? (
        <div className="mt-2 text-[11px] leading-4 text-slate-500">
	          Активация будет доступна после: {setupFlow.activation_blockers.slice(0, 3).map((item) => userFacingAgentTechText(item.message || connectorLabel(item.provider))).join(', ')}.
        </div>
      ) : null}
      {setupFlow.post_create_description ? (
        <div className="mt-2 rounded-lg bg-slate-50 px-2 py-2 text-[11px] leading-4 text-slate-600 ring-1 ring-slate-100">
	          После создания: {userFacingAgentTechText(setupFlow.post_create_description)}
        </div>
      ) : null}
    </div>
  );
};

export const BuilderConnectionSummaryPanel = ({
  summary,
  selectedBindings = {},
  onSelectBinding,
}: {
  summary?: AgentConnectionSummary;
  selectedBindings?: Record<string, string>;
  onSelectBinding?: (bindingKey: string, integrationId: string) => void;
}) => {
  const items = summary?.items || [];
  const forbidden = summary?.forbidden || [];
  const unsupported = summary?.unsupported || [];
  if (!summary || (!items.length && !forbidden.length && !unsupported.length)) {
    return null;
  }
  const blocked = Boolean((summary.blocked_count || 0) > 0 || forbidden.length || unsupported.length);
  const needsAction = Boolean((summary.missing_count || 0) > 0 || (summary.choice_count || 0) > 0);
  return (
    <div className={cn('mt-3 rounded-xl border px-3 py-3 text-xs leading-5', blocked ? 'border-rose-200 bg-rose-50 text-rose-950' : needsAction ? 'border-amber-200 bg-amber-50 text-amber-950' : 'border-emerald-200 bg-emerald-50 text-emerald-950')}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="font-semibold">Подключения для агента</div>
          <div className="mt-1 max-w-2xl">{summary.headline || 'LocalOS проверил нужные источники и каналы.'}</div>
        </div>
        <span className="rounded-full bg-white px-2 py-0.5 font-medium ring-1 ring-current/10">
          {summary.next_action_label || 'Проверить подключения'}
        </span>
      </div>
      <div className="mt-3 grid gap-2 sm:grid-cols-4">
        <AgentMiniMetric label="Готово" value={String(summary.ready_count || 0)} />
        <AgentMiniMetric label="Подключить" value={String(summary.missing_count || 0)} />
        <AgentMiniMetric label="Выбрать" value={String(summary.choice_count || 0)} />
        <AgentMiniMetric label="Блокеры" value={String(summary.blocked_count || 0)} />
      </div>
      <div className="mt-3 grid gap-2 md:grid-cols-2">
        {items.slice(0, 4).map((item) => (
          <div key={`${item.key || item.provider || item.title}`} className="rounded-lg bg-white px-3 py-2 ring-1 ring-current/10">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div className="font-medium">{item.title || connectorLabel(item.provider)}</div>
              <span className="rounded-full bg-slate-50 px-2 py-0.5 text-[11px] text-slate-600 ring-1 ring-slate-200">
                {userFacingAgentTechText(item.action_label || humanizeMeta(item.action || item.status || 'status'))}
              </span>
            </div>
            <div className="mt-1 text-[11px] leading-4 opacity-80">{item.explanation || 'Подключение будет проверено перед тестом без отправки.'}</div>
            {item.setup_cta?.mode && item.setup_cta.mode !== 'none' ? (
              <div className="mt-2 rounded-lg bg-slate-50 px-2 py-1.5 text-[11px] leading-4 text-slate-700 ring-1 ring-slate-200">
                <div className="font-medium">{item.setup_cta.label || 'Настроить подключение'}</div>
                {item.setup_cta.description ? <div className="mt-0.5">{item.setup_cta.description}</div> : null}
              </div>
            ) : null}
            {item.connections?.length ? (
              <div className="mt-2 space-y-1.5">
                <div className="text-[11px] font-medium opacity-80">
                  Доступно: {item.connections.slice(0, 2).map((connection) => connection.display_name || connectorLabel(connection.provider)).join(', ')}
                </div>
                {item.connections.length === 1 && selectedBindings[item.key || ''] === item.connections[0]?.id ? (
                  <div className="inline-flex rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] font-medium text-emerald-700 ring-1 ring-emerald-200">
                    Выбрано автоматически
                  </div>
                ) : null}
                {item.connections.length > 1 && onSelectBinding ? (
                  <div className="flex flex-wrap gap-1.5">
                    {item.connections.slice(0, 4).map((connection) => {
                      const bindingKey = item.key || item.provider || '';
                      const integrationId = connection.id || '';
                      const selected = Boolean(bindingKey && integrationId && selectedBindings[bindingKey] === integrationId);
                      return (
                        <Button
                          key={`${bindingKey}-${integrationId}`}
                          type="button"
                          size="sm"
                          variant={selected ? 'default' : 'outline'}
                          className={cn('h-7 px-2 text-[11px]', selected ? '' : 'bg-white')}
                          disabled={!bindingKey || !integrationId}
                          onClick={() => onSelectBinding(bindingKey, integrationId)}
                        >
                          {selected ? 'Выбрано' : 'Использовать'} {connection.display_name || connectorLabel(connection.provider)}
                        </Button>
                      );
                    })}
                  </div>
                ) : null}
              </div>
            ) : null}
          </div>
        ))}
      </div>
      {forbidden.length || unsupported.length ? (
        <div className="mt-3 rounded-lg bg-white px-3 py-2 text-[11px] leading-4 ring-1 ring-current/10">
          {[...forbidden.map((item) => item.reason || item.term || 'Запрещено правилами безопасности'), ...unsupported.map((item) => item.reason || item.capability || 'Нет способа подключения')].slice(0, 3).join(' · ')}
        </div>
      ) : null}
    </div>
  );
};
