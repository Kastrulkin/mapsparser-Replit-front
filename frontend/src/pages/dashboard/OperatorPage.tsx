import { useEffect, useMemo, useState } from 'react';
import { Link, useOutletContext } from 'react-router-dom';
import {
  AlertCircle,
  Bot,
  CheckCircle2,
  Clock3,
  Copy,
  CreditCard,
  ExternalLink,
  Loader2,
  MessageSquareText,
  RefreshCw,
  Send,
  ShieldCheck,
} from 'lucide-react';

import { Button } from '@/components/ui/button';
import {
  DashboardActionPanel,
  DashboardCompactMetricsRow,
  DashboardEmptyState,
  DashboardPageHeader,
  DashboardSection,
} from '@/components/dashboard/DashboardPrimitives';
import { api } from '@/services/api';
import { cn } from '@/lib/utils';

type DashboardContext = {
  currentBusinessId: string | null;
  currentBusiness?: {
    id: string;
    name?: string;
  } | null;
};

type OperatorActionClass =
  | 'free_cached'
  | 'paid_compute'
  | 'paid_external'
  | 'manual_external'
  | 'approval_required'
  | 'planned_gap';

type AttentionItem = {
  id: string;
  category: string;
  severity: 'high' | 'medium' | 'low';
  title: string;
  description: string;
  count: number;
  action_class: OperatorActionClass;
  cta?: {
    label?: string;
    href?: string;
  };
};

type PaidActionOffer = {
  action_key: string;
  label: string;
  description: string;
  action_class: OperatorActionClass;
  status: 'proposal_only';
  consent_required: boolean;
  consent_modes: string[];
  default_consent_mode: string;
  cost_source: string;
  provider: string;
  credit_multiplier: number;
  estimate_available: boolean;
  estimated_credits: number | null;
  balance_credits: number | null;
  affordable_runs_estimate: number | null;
  paid_actions_performed: boolean;
  current_consent_policy?: {
    action_key: string;
    mode: string;
    max_credits_per_action: number | null;
    max_credits_per_day: number | null;
    max_credits_per_month: number | null;
    low_balance_warning_threshold: number | null;
    execution_allowed_without_prompt: boolean;
    is_persisted: boolean;
  } | null;
  copy: {
    primary: string;
    disclosure: string;
    auto_consent_question: string;
    manual_publication_note: string;
  };
};

type ConsentDraft = {
  mode: string;
  max_credits_per_action: string;
  max_credits_per_day: string;
  max_credits_per_month: string;
  low_balance_warning_threshold: string;
};

type PreflightDraft = {
  estimated_credits: string;
  explicit_consent: boolean;
};

type PreflightResult = {
  action_key: string;
  status: 'ready' | 'blocked';
  execution_status: string;
  execution_enabled: boolean;
  would_be_allowed: boolean;
  can_execute_now: boolean;
  blocked_reasons: string[];
  warnings: string[];
  estimated_credits: number | null;
  balance_credits: number | null;
  paid_actions_performed: boolean;
  credit_charged: boolean;
  external_calls_performed: boolean;
  next_step: string;
  copy: {
    summary: string;
    ready: string;
    blocked: string;
  };
};

type ExecutionAttempt = {
  action_key: string;
  status: 'blocked';
  execution_status: string;
  execution_enabled: boolean;
  blocked_reasons: string[];
  warnings: string[];
  estimated_credits: number | null;
  balance_credits: number | null;
  paid_actions_performed: boolean;
  credit_reserved: boolean;
  credit_charged: boolean;
  external_calls_performed: boolean;
  external_writes_performed: boolean;
  parsequeue_jobs_created: boolean;
  ai_generation_performed: boolean;
  reservation_plan?: {
    status: string;
    requested_credits: number | null;
    active_reserved_credits: number | null;
    available_after_reservations: number | null;
    blocked_reasons: string[];
  };
  adapter_result?: {
    adapter_status: string;
    runtime_mode: string;
    dry_run: boolean;
    idempotency_key: string;
    stages: Array<{
      stage: string;
      status: string;
      dry_run: boolean;
    }>;
  };
  next_step: string;
  copy: {
    summary: string;
    blocked: string;
  };
};

type OperatorEvent = {
  id: string;
  event_type: string;
  risk_level: string;
  input_summary: string;
  output_summary: string;
  status: string;
  reason_code: string;
  metadata: {
    action_key?: string;
    operator_channel?: string;
    execution_status?: string;
    credit_charged?: boolean;
    external_calls_performed?: boolean;
    external_writes_performed?: boolean;
  };
  created_at: string;
};

type AttentionBrief = {
  business: {
    id: string;
    name: string;
  };
  query: string;
  action_class: OperatorActionClass;
  data_mode: 'cached';
  summary: {
    title: string;
    text: string;
    signals_count: number;
  };
  metrics: {
    reviews_total: number;
    reviews_without_response: number;
    pending_approvals: number;
    pending_news: number;
    review_reply_drafts: number;
    partnership_leads_ready: number;
  };
  freshness: {
    latest_card_at: string | null;
    latest_reviews_at: string | null;
    card_age_days: number | null;
    is_stale: boolean;
    stale_after_days: number;
    paid_refresh_required_for_fresh_data: boolean;
    message: string;
  };
  paid_action_offers?: PaidActionOffer[];
  items: AttentionItem[];
  limits: {
    external_writes_performed: boolean;
    paid_actions_performed: boolean;
    manual_publication_only: boolean;
  };
};

const severityStyles: Record<AttentionItem['severity'], string> = {
  high: 'border-rose-200 bg-rose-50/80 text-rose-900',
  medium: 'border-amber-200 bg-amber-50/80 text-amber-900',
  low: 'border-slate-200 bg-slate-50 text-slate-800',
};

const actionClassLabels: Record<OperatorActionClass, string> = {
  free_cached: 'Бесплатно, по сохранённым данным',
  paid_compute: 'Платная генерация',
  paid_external: 'Платное обновление данных',
  manual_external: 'Ручное внешнее действие',
  approval_required: 'Требует подтверждения',
  planned_gap: 'Планируемая возможность',
};

const eventLabels: Record<string, string> = {
  operator_context_built: 'Контекст Operator собран',
  operator_consent_decision: 'Consent policy изменена',
  operator_draft_created: 'Черновик создан',
  operator_execution_blocked: 'Запуск заблокирован',
  operator_manual_action_presented: 'Ручное действие показано',
  operator_manual_publish_marked: 'Отмечено ручное размещение',
  operator_message_received: 'Сообщение получено',
  operator_paid_action_estimated: 'Preflight платного действия',
  operator_review_added: 'Отзыв добавлен',
  operator_tool_executed: 'Инструмент выполнен',
  operator_usage_charged: 'Кредиты списаны',
};

const refreshJobStatusLabels: Record<'processing' | 'completed' | 'failed', string> = {
  processing: 'В работе',
  completed: 'Завершено',
  failed: 'Ошибка',
};

const refreshJobStatusStyles: Record<'processing' | 'completed' | 'failed', string> = {
  processing: 'bg-sky-50 text-sky-800 ring-sky-200',
  completed: 'bg-emerald-50 text-emerald-800 ring-emerald-200',
  failed: 'bg-rose-50 text-rose-800 ring-rose-200',
};

const contentKindLabels: Record<string, string> = {
  review_reply_draft: 'Ответы',
  news_draft: 'Новости',
  social_post_draft: 'Соцпосты',
  service_suggestion: 'Услуги',
  service_apply: 'Применено',
};

const contentKindStyles: Record<string, string> = {
  review_reply_draft: 'bg-sky-50 text-sky-800 ring-sky-200',
  news_draft: 'bg-emerald-50 text-emerald-800 ring-emerald-200',
  social_post_draft: 'bg-violet-50 text-violet-800 ring-violet-200',
  service_suggestion: 'bg-amber-50 text-amber-800 ring-amber-200',
  service_apply: 'bg-teal-50 text-teal-800 ring-teal-200',
};

const refreshBillingStyles: Record<string, string> = {
  reserved: 'bg-amber-50 text-amber-800 ring-amber-200',
  charged: 'bg-emerald-50 text-emerald-800 ring-emerald-200',
  released: 'bg-slate-100 text-slate-700 ring-slate-200',
  overage_charged: 'bg-orange-50 text-orange-800 ring-orange-200',
  not_found: 'bg-slate-100 text-slate-700 ring-slate-200',
  unavailable: 'bg-slate-100 text-slate-700 ring-slate-200',
  unknown: 'bg-slate-100 text-slate-700 ring-slate-200',
};

const refreshReliabilityStyles: Record<string, string> = {
  success: 'bg-emerald-50 text-emerald-800 ring-emerald-200',
  info: 'bg-sky-50 text-sky-800 ring-sky-200',
  warning: 'bg-amber-50 text-amber-800 ring-amber-200',
  error: 'bg-rose-50 text-rose-800 ring-rose-200',
  unknown: 'bg-slate-100 text-slate-700 ring-slate-200',
};

type OperatorChatResult = {
  status: 'completed' | 'blocked' | 'unsupported';
  intent: string;
  chat_response: string;
  queue_id?: string;
  reply_text?: string;
  news_text?: string;
  social_post_text?: string;
  billing_url?: string;
  charged_credits?: number;
  credit_charged?: boolean;
  manual_publication_only?: boolean;
  blocked_reasons?: string[];
  ui_actions?: Array<{
    action: string;
    label: string;
    href?: string;
    payload?: {
      text?: string;
      action_key?: string;
    };
  }>;
  review?: {
    id?: string;
    source?: string;
    author_name?: string;
    text?: string;
  };
  draft?: {
    id?: string;
    review_id?: string;
    status?: string;
    generated_text?: string;
  };
  news_draft?: {
    id?: string;
    status?: string;
    generated_text?: string;
    source_text?: string;
  };
  social_post_draft?: {
    id?: string;
    status?: string;
    generated_text?: string;
    source_text?: string;
  };
  optimization_job?: {
    id?: string;
    status?: string;
    selected_count?: number;
    fixed_count?: number;
    message?: string;
  };
  service_suggestions?: Array<{
    id?: string;
    service_id?: string;
    status?: string;
    before_name?: string;
    optimized_name?: string;
    seo_description?: string;
  }>;
  applied_count?: number;
  applied_items?: Array<{
    id?: string;
    service_id?: string;
    status?: string;
    before_name?: string;
    optimized_name?: string;
    seo_description?: string;
  }>;
  manual_approval_received?: boolean;
  drafts?: Array<{
    id?: string;
    review_id?: string;
    status?: string;
    generated_text?: string;
  }>;
  reviews_found?: number;
  failures?: Array<{
    review_id?: string;
    reason?: string;
  }>;
};

type RefreshReview = {
  id?: string;
  source?: string;
  external_review_id?: string;
  rating?: number;
  author_name?: string;
  text?: string;
  has_response?: boolean;
  published_at?: string;
  created_at?: string;
};

type RefreshResult = {
  status: 'completed' | 'processing' | 'failed' | 'blocked';
  queue_id?: string;
  queue_status?: string;
  billing_state?: RefreshBillingState;
  reliability_state?: RefreshReliabilityState;
  new_reviews_count?: number;
  new_unanswered_reviews_count?: number;
  new_reviews?: RefreshReview[];
  chat_response?: string;
  blocked_reasons?: string[];
};

type RefreshJob = {
  queue_id: string;
  retry_source_queue_id?: string;
  status: 'completed' | 'processing' | 'failed';
  queue_status?: string;
  created_at?: string;
  updated_at?: string;
  error_message?: string;
  new_reviews_count?: number;
  new_unanswered_reviews_count?: number;
  billing_state?: RefreshBillingState;
  reliability_state?: RefreshReliabilityState;
  new_reviews?: RefreshReview[];
  chat_response?: string;
  blocked_reasons?: string[];
};

type RefreshBillingState = {
  status: 'reserved' | 'charged' | 'released' | 'overage_charged' | 'not_found' | 'unavailable' | 'unknown' | string;
  label?: string;
  reservation_id?: string;
  reservation_status?: string;
  estimated_credits?: number;
  reserved_credits?: number;
  charged_credits?: number;
  released_credits?: number;
  outstanding_credits?: number;
  overage_credits?: number;
  provider?: string;
  provider_actual_cost?: string | number | null;
  credit_multiplier?: number;
  actual_credits?: number | string | null;
  retry_source_queue_id?: string;
  retry_source_status?: string;
  retry_requested_by_operator?: boolean;
  retry_reason_code?: string;
};

type RefreshReliabilityState = {
  status: 'ok' | 'processing' | 'retrying' | 'captcha_required' | 'failed' | 'warning' | 'paused' | 'unknown' | string;
  severity?: 'success' | 'info' | 'warning' | 'error' | string;
  reason_code?: string;
  title?: string;
  explanation?: string;
  next_step?: string;
  retry_after?: string | null;
  captcha_required?: boolean;
  captcha_status?: string;
  resume_requested?: boolean;
  warnings?: string[];
  error_message?: string;
  technical_details?: {
    queue_status?: string;
    reason_code?: string;
    retry_after?: string | null;
    captcha_required?: boolean;
    captcha_status?: string;
    resume_requested?: boolean;
    warnings_count?: number;
    attempts?: Record<string, string | number>;
  };
};

type RefreshJobs = {
  status: string;
  summary: {
    title: string;
    text: string;
    jobs_count: number;
    processing_count: number;
    completed_count: number;
    failed_count: number;
    new_reviews_count: number;
    new_unanswered_reviews_count: number;
    reserved_credits?: number;
    charged_credits?: number;
    released_credits?: number;
    overage_credits?: number;
    retrying_count?: number;
    captcha_required_count?: number;
    reliability_failed_count?: number;
    warning_count?: number;
  };
  jobs: RefreshJob[];
};

type RefreshRetryResult = {
  status: 'queued' | 'blocked' | string;
  chat_response?: string;
  new_queue_id?: string;
  reservation_id?: string;
  estimated_credits?: number;
  billing_url?: string;
  blocked_reasons?: string[];
};

type ContentHistoryItem = {
  id: string;
  kind: 'review_reply_draft' | 'news_draft' | 'social_post_draft' | 'service_suggestion' | 'service_apply' | string;
  status: string;
  title: string;
  text?: string;
  created_at?: string;
  updated_at?: string;
  href?: string;
  source?: string;
  manual_publication_only?: boolean;
  external_writes_performed?: boolean;
  metadata?: Record<string, unknown>;
};

type ContentHistory = {
  status: string;
  summary: {
    title: string;
    text: string;
    items_count: number;
    type_counts: Record<string, number>;
    status_counts: Record<string, number>;
  };
  items: ContentHistoryItem[];
};

type OperatorInboxItem = {
  id: string;
  kind: string;
  title: string;
  description: string;
  status: string;
  priority: 'high' | 'medium' | 'low';
  count?: number;
  primary_action: string;
  secondary_action?: string;
  href?: string;
  copy_text?: string;
  metadata?: {
    review_id?: string;
    author_name?: string;
    manual_publication_only?: boolean;
    external_writes_performed?: boolean;
  };
};

type OperatorInbox = {
  status: string;
  summary: {
    title: string;
    text: string;
    items_count: number;
  };
  items: OperatorInboxItem[];
  paid_generation_offers: PaidActionOffer[];
  limits: {
    external_calls_performed: boolean;
    external_writes_performed: boolean;
    manual_publication_only: boolean;
  };
};

const formatDateTime = (value: string | null) => {
  if (!value) return 'нет данных';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(parsed);
};

const renderBillingDetails = (billing: RefreshBillingState | undefined) => {
  if (!billing) return null;
  const style = refreshBillingStyles[billing.status] || refreshBillingStyles.unknown;
  return (
    <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm leading-6 text-slate-700">
      <div className="flex flex-wrap items-center gap-2">
        <span className={cn('rounded-full px-2 py-1 text-xs font-medium ring-1', style)}>
          {billing.label || billing.status}
        </span>
        {billing.provider_actual_cost !== null && billing.provider_actual_cost !== undefined ? (
          <span className="text-xs font-semibold text-slate-500">Apify: ${billing.provider_actual_cost}</span>
        ) : null}
      </div>
      <div className="mt-2 grid gap-2 sm:grid-cols-4">
        <div>Резерв: {billing.outstanding_credits || 0}</div>
        <div>Списано: {billing.charged_credits || 0}</div>
        <div>Возврат: {billing.released_credits || 0}</div>
        <div>Overage: {billing.overage_credits || 0}</div>
      </div>
    </div>
  );
};

const renderReliabilityDetails = (reliability: RefreshReliabilityState | undefined) => {
  if (!reliability) return null;
  const severity = reliability.severity || 'unknown';
  const style = refreshReliabilityStyles[severity] || refreshReliabilityStyles.unknown;
  const warnings = reliability.warnings || [];
  const details = reliability.technical_details;
  const attempts = details?.attempts || {};
  const detailRows = [
    ['Статус', details?.queue_status],
    ['Retry after', details?.retry_after ? formatDateTime(details.retry_after) : ''],
    ['Captcha', details?.captcha_required ? (details.captcha_status || 'required') : ''],
    ['Resume', details?.resume_requested ? 'requested' : ''],
    ['Warnings', details?.warnings_count ? String(details.warnings_count) : ''],
    ['Попытки', Object.entries(attempts).map(([key, value]) => `${key}: ${value}`).join(', ')],
  ].filter((row) => row[1]);
  return (
    <div className="mt-3 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm leading-6 text-slate-700">
      <div className="flex flex-wrap items-center gap-2">
        <span className={cn('rounded-full px-2 py-1 text-xs font-medium ring-1', style)}>
          {reliability.title || reliability.status}
        </span>
        {reliability.reason_code ? (
          <span className="text-xs font-semibold text-slate-500">код: {reliability.reason_code}</span>
        ) : null}
        {reliability.retry_after ? (
          <span className="text-xs font-semibold text-slate-500">retry: {formatDateTime(reliability.retry_after)}</span>
        ) : null}
      </div>
      {reliability.explanation ? <p className="mt-2">{reliability.explanation}</p> : null}
      {reliability.next_step ? <p className="mt-1 font-medium text-slate-800">{reliability.next_step}</p> : null}
      {detailRows.length > 0 ? (
        <div className="mt-3 grid gap-2 sm:grid-cols-2">
          {detailRows.map(([label, value]) => (
            <div key={label} className="rounded-lg bg-slate-50 px-2 py-1 text-xs text-slate-600">
              <span className="font-semibold text-slate-700">{label}:</span> {value}
            </div>
          ))}
        </div>
      ) : null}
      {warnings.length > 0 ? (
        <div className="mt-2 space-y-1">
          {warnings.slice(0, 3).map((warning) => (
            <div key={warning} className="rounded-lg bg-slate-50 px-2 py-1 text-xs text-slate-600">
              {warning}
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
};

const canRequestRefreshRetry = (job: RefreshJob) => {
  const reliabilityStatus = job.reliability_state?.status || '';
  return ['failed', 'captcha_required', 'paused', 'warning'].includes(reliabilityStatus);
};

const getItemIcon = (item: AttentionItem) => {
  if (item.action_class === 'approval_required') return ShieldCheck;
  if (item.action_class === 'paid_external') return CreditCard;
  if (item.category === 'reviews') return MessageSquareText;
  if (item.severity === 'high') return AlertCircle;
  return CheckCircle2;
};

export const OperatorPage = () => {
  const { currentBusinessId, currentBusiness } = useOutletContext<DashboardContext>();
  const [brief, setBrief] = useState<AttentionBrief | null>(null);
  const [inbox, setInbox] = useState<OperatorInbox | null>(null);
  const [refreshJobs, setRefreshJobs] = useState<RefreshJobs | null>(null);
  const [contentHistory, setContentHistory] = useState<ContentHistory | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savingConsentKey, setSavingConsentKey] = useState<string | null>(null);
  const [consentDrafts, setConsentDrafts] = useState<Record<string, ConsentDraft>>({});
  const [consentMessage, setConsentMessage] = useState<string | null>(null);
  const [preflightDrafts, setPreflightDrafts] = useState<Record<string, PreflightDraft>>({});
  const [preflightResults, setPreflightResults] = useState<Record<string, PreflightResult>>({});
  const [preflightingKey, setPreflightingKey] = useState<string | null>(null);
  const [executionAttempts, setExecutionAttempts] = useState<Record<string, ExecutionAttempt>>({});
  const [executingKey, setExecutingKey] = useState<string | null>(null);
  const [operatorEvents, setOperatorEvents] = useState<OperatorEvent[]>([]);
  const [chatMessage, setChatMessage] = useState(
    'Добавь новый отзыв в список и сгенерируй ответ:\n\nПопала в салон случайно - получила сертификат на массаж лица. Массаж лица очень понравился - ушла расслабленная и с рекомендациями по уходу за кожей.',
  );
  const [chatLoading, setChatLoading] = useState(false);
  const [chatResult, setChatResult] = useState<OperatorChatResult | null>(null);
  const [refreshResult, setRefreshResult] = useState<RefreshResult | null>(null);
  const [refreshChecking, setRefreshChecking] = useState(false);
  const [refreshRetryingQueueId, setRefreshRetryingQueueId] = useState<string | null>(null);
  const [refreshRetryResult, setRefreshRetryResult] = useState<RefreshRetryResult | null>(null);
  const [copiedChatReply, setCopiedChatReply] = useState(false);
  const [copiedInboxItemId, setCopiedInboxItemId] = useState<string | null>(null);
  const [bulkGeneratingKey, setBulkGeneratingKey] = useState<string | null>(null);
  const [applyingServiceJobId, setApplyingServiceJobId] = useState<string | null>(null);
  const [manualPublishDraftId, setManualPublishDraftId] = useState<string | null>(null);
  const [manualPublishMessage, setManualPublishMessage] = useState<string | null>(null);

  const loadOperatorEvents = async () => {
    if (!currentBusinessId) {
      setOperatorEvents([]);
      return;
    }
    try {
      const response = await api.get('/operator/events', {
        params: { business_id: currentBusinessId, limit: 8 },
      });
      setOperatorEvents(response.data.events || []);
    } catch (err) {
      setOperatorEvents([]);
    }
  };

  const loadBrief = async () => {
    if (!currentBusinessId) {
      setBrief(null);
      setInbox(null);
      setRefreshJobs(null);
      setContentHistory(null);
      setOperatorEvents([]);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const response = await api.get('/operator/attention-brief', {
        params: { business_id: currentBusinessId },
      });
      const nextBrief = response.data.brief || null;
      setBrief(nextBrief);
      if (nextBrief?.paid_action_offers) {
        setConsentDrafts(buildConsentDrafts(nextBrief.paid_action_offers));
        setPreflightDrafts(buildPreflightDrafts(nextBrief.paid_action_offers));
      }
      await loadOperatorEvents();
      await loadInbox();
      await loadRefreshJobs();
      await loadContentHistory();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось загрузить сводку');
    } finally {
      setLoading(false);
    }
  };

  const loadInbox = async () => {
    if (!currentBusinessId) {
      setInbox(null);
      return;
    }
    try {
      const response = await api.get('/operator/inbox', {
        params: { business_id: currentBusinessId },
      });
      setInbox(response.data.inbox || null);
    } catch (err) {
      setInbox(null);
    }
  };

  const loadRefreshJobs = async () => {
    if (!currentBusinessId) {
      setRefreshJobs(null);
      return;
    }
    try {
      const response = await api.get('/operator/reviews/refresh-jobs', {
        params: { business_id: currentBusinessId, limit: 8 },
      });
      setRefreshJobs(response.data.refresh_jobs || null);
    } catch (err) {
      setRefreshJobs(null);
    }
  };

  const loadContentHistory = async () => {
    if (!currentBusinessId) {
      setContentHistory(null);
      return;
    }
    try {
      const response = await api.get('/operator/content-history', {
        params: { business_id: currentBusinessId, limit: 20 },
      });
      setContentHistory(response.data.content_history || null);
    } catch (err) {
      setContentHistory(null);
    }
  };

  useEffect(() => {
    void loadBrief();
  }, [currentBusinessId]);

  const updateConsentDraft = (actionKey: string, patch: Partial<ConsentDraft>) => {
    setConsentDrafts((current) => {
      const currentDraft = current[actionKey] || emptyConsentDraft();
      return {
        ...current,
        [actionKey]: {
          ...currentDraft,
          ...patch,
        },
      };
    });
  };

  const saveConsentPolicy = async (offer: PaidActionOffer) => {
    if (!currentBusinessId) return;
    const draft = consentDrafts[offer.action_key] || makeConsentDraft(offer);
    setSavingConsentKey(offer.action_key);
    setConsentMessage(null);
    try {
      const response = await api.put(`/operator/consent-policy/${offer.action_key}`, {
        business_id: currentBusinessId,
        mode: draft.mode,
        max_credits_per_action: draft.max_credits_per_action,
        max_credits_per_day: draft.max_credits_per_day,
        max_credits_per_month: draft.max_credits_per_month,
        low_balance_warning_threshold: draft.low_balance_warning_threshold,
      });
      if (!response.data.success) {
        throw new Error(response.data.error || 'Не удалось сохранить policy');
      }
      setConsentMessage('Consent policy сохранена. Платные действия всё ещё не запускаются автоматически в Sprint 4.');
      await loadBrief();
      await loadOperatorEvents();
    } catch (err) {
      setConsentMessage(err instanceof Error ? err.message : 'Не удалось сохранить consent policy');
    } finally {
      setSavingConsentKey(null);
    }
  };

  const updatePreflightDraft = (actionKey: string, patch: Partial<PreflightDraft>) => {
    setPreflightDrafts((current) => {
      const currentDraft = current[actionKey] || emptyPreflightDraft();
      return {
        ...current,
        [actionKey]: {
          ...currentDraft,
          ...patch,
        },
      };
    });
  };

  const runPreflight = async (offer: PaidActionOffer) => {
    if (!currentBusinessId) return;
    const draft = preflightDrafts[offer.action_key] || makePreflightDraft(offer);
    setPreflightingKey(offer.action_key);
    setConsentMessage(null);
    try {
      const response = await api.post(`/operator/paid-actions/${offer.action_key}/preflight`, {
        business_id: currentBusinessId,
        estimated_credits: draft.estimated_credits,
        explicit_consent: draft.explicit_consent,
      });
      if (!response.data.success) {
        throw new Error(response.data.error || 'Не удалось выполнить preflight');
      }
      setPreflightResults((current) => ({
        ...current,
        [offer.action_key]: response.data.preflight,
      }));
      await loadOperatorEvents();
    } catch (err) {
      setConsentMessage(err instanceof Error ? err.message : 'Не удалось выполнить preflight');
    } finally {
      setPreflightingKey(null);
    }
  };

  const runExecutionAttempt = async (offer: PaidActionOffer) => {
    if (!currentBusinessId) return;
    const draft = preflightDrafts[offer.action_key] || makePreflightDraft(offer);
    setExecutingKey(offer.action_key);
    setConsentMessage(null);
    try {
      const response = await api.post(`/operator/paid-actions/${offer.action_key}/execute`, {
        business_id: currentBusinessId,
        estimated_credits: draft.estimated_credits,
        explicit_consent: draft.explicit_consent,
      });
      if (!response.data.success) {
        throw new Error(response.data.error || 'Не удалось проверить запуск');
      }
      setExecutionAttempts((current) => ({
        ...current,
        [offer.action_key]: response.data.execution,
      }));
      await loadOperatorEvents();
    } catch (err) {
      setConsentMessage(err instanceof Error ? err.message : 'Не удалось проверить запуск');
    } finally {
      setExecutingKey(null);
    }
  };

  const sendOperatorChatMessage = async () => {
    if (!currentBusinessId || !chatMessage.trim()) return;
    setChatLoading(true);
    setConsentMessage(null);
    setChatResult(null);
    setRefreshResult(null);
    setCopiedChatReply(false);
    try {
      const response = await api.post('/operator/chat', {
        business_id: currentBusinessId,
        message: chatMessage,
      });
      const result = response.data.operator_result || null;
      setChatResult(result);
      await loadBrief();
      await loadRefreshJobs();
      await loadContentHistory();
      await loadOperatorEvents();
    } catch (err) {
      setChatResult({
        status: 'blocked',
        intent: 'error',
        chat_response: err instanceof Error ? err.message : 'Не удалось выполнить команду Operator',
        blocked_reasons: ['operator_chat_request_failed'],
      });
    } finally {
      setChatLoading(false);
    }
  };

  const checkRefreshResult = async (queueId: string | undefined) => {
    if (!currentBusinessId || !queueId) return;
    setRefreshChecking(true);
    setConsentMessage(null);
    try {
      const response = await api.get(`/operator/reviews/refresh-results/${queueId}`, {
        params: { business_id: currentBusinessId },
      });
      const result = response.data.refresh_result || null;
      setRefreshResult(result);
      await loadBrief();
      await loadInbox();
      await loadRefreshJobs();
      await loadContentHistory();
      await loadOperatorEvents();
    } catch (err) {
      setRefreshResult({
        status: 'blocked',
        queue_id: queueId,
        chat_response: err instanceof Error ? err.message : 'Не удалось проверить результат обновления',
        blocked_reasons: ['operator_refresh_result_failed'],
      });
    } finally {
      setRefreshChecking(false);
    }
  };

  const requestRefreshRetry = async (queueId: string | undefined) => {
    if (!currentBusinessId || !queueId) return;
    setRefreshRetryingQueueId(queueId);
    setRefreshRetryResult(null);
    try {
      const response = await api.post(`/operator/reviews/refresh-jobs/${queueId}/retry`, {
        business_id: currentBusinessId,
        confirm_retry: true,
      });
      const result = response.data.retry_result || null;
      setRefreshRetryResult(result);
      if (result?.new_queue_id) {
        await checkRefreshResult(result.new_queue_id);
      }
      await loadBrief();
      await loadInbox();
      await loadRefreshJobs();
      await loadOperatorEvents();
    } catch (err) {
      setRefreshRetryResult({
        status: 'blocked',
        chat_response: err instanceof Error ? err.message : 'Не удалось запустить повтор refresh',
        blocked_reasons: ['operator_refresh_retry_failed'],
      });
    } finally {
      setRefreshRetryingQueueId(null);
    }
  };

  const copyChatReply = async () => {
    const text =
      chatResult?.reply_text ||
      chatResult?.draft?.generated_text ||
      chatResult?.news_text ||
      chatResult?.news_draft?.generated_text ||
      chatResult?.social_post_text ||
      chatResult?.social_post_draft?.generated_text ||
      '';
    if (!text.trim()) return;
    await navigator.clipboard.writeText(text);
    setCopiedChatReply(true);
    window.setTimeout(() => setCopiedChatReply(false), 2000);
  };

  const copyInboxText = async (item: OperatorInboxItem) => {
    const text = item.copy_text || '';
    if (!text.trim()) return;
    await navigator.clipboard.writeText(text);
    setCopiedInboxItemId(item.id);
    window.setTimeout(() => setCopiedInboxItemId(null), 2000);
  };

  const copyDraftText = async (draft: { id?: string; generated_text?: string }) => {
    const text = draft.generated_text || '';
    if (!text.trim() || !draft.id) return;
    await navigator.clipboard.writeText(text);
    setCopiedInboxItemId(draft.id);
    window.setTimeout(() => setCopiedInboxItemId(null), 2000);
  };

  const generateReviewReplies = async () => {
    if (!currentBusinessId) return;
    setBulkGeneratingKey('review_replies_generate');
    setConsentMessage(null);
    setChatResult(null);
    setRefreshResult(null);
    try {
      const response = await api.post('/operator/review-replies/generate', {
        business_id: currentBusinessId,
        limit: 5,
      });
      const result = response.data.operator_result || null;
      setChatResult(result);
      await loadBrief();
      await loadInbox();
      await loadContentHistory();
      await loadOperatorEvents();
    } catch (err) {
      setChatResult({
        status: 'blocked',
        intent: 'bulk_review_replies_generate',
        chat_response: err instanceof Error ? err.message : 'Не удалось сгенерировать ответы',
        blocked_reasons: ['operator_bulk_generation_failed'],
      });
    } finally {
      setBulkGeneratingKey(null);
    }
  };

  const generateNewsDraft = async () => {
    if (!currentBusinessId) return;
    const sourceText = chatMessage.trim() || 'Подготовь новость по последним изменениям бизнеса.';
    setBulkGeneratingKey('news_generate');
    setConsentMessage(null);
    setChatResult(null);
    setRefreshResult(null);
    try {
      const response = await api.post('/operator/news/generate', {
        business_id: currentBusinessId,
        message: sourceText,
      });
      const result = response.data.operator_result || null;
      setChatResult(result);
      await loadBrief();
      await loadInbox();
      await loadContentHistory();
      await loadOperatorEvents();
    } catch (err) {
      setChatResult({
        status: 'blocked',
        intent: 'news_generate',
        chat_response: err instanceof Error ? err.message : 'Не удалось сгенерировать новость',
        blocked_reasons: ['operator_news_generation_failed'],
      });
    } finally {
      setBulkGeneratingKey(null);
    }
  };

  const generateSocialPostDraft = async () => {
    if (!currentBusinessId) return;
    const sourceText = chatMessage.trim() || 'Подготовь пост для соцсетей по последним изменениям бизнеса.';
    setBulkGeneratingKey('social_post_generate');
    setConsentMessage(null);
    setChatResult(null);
    setRefreshResult(null);
    try {
      const response = await api.post('/operator/social-posts/generate', {
        business_id: currentBusinessId,
        message: sourceText,
      });
      const result = response.data.operator_result || null;
      setChatResult(result);
      await loadBrief();
      await loadInbox();
      await loadContentHistory();
      await loadOperatorEvents();
    } catch (err) {
      setChatResult({
        status: 'blocked',
        intent: 'social_post_generate',
        chat_response: err instanceof Error ? err.message : 'Не удалось сгенерировать пост',
        blocked_reasons: ['operator_social_post_generation_failed'],
      });
    } finally {
      setBulkGeneratingKey(null);
    }
  };

  const optimizeServices = async () => {
    if (!currentBusinessId) return;
    setBulkGeneratingKey('services_optimize');
    setConsentMessage(null);
    setChatResult(null);
    setRefreshResult(null);
    try {
      const response = await api.post('/operator/services/optimize', {
        business_id: currentBusinessId,
        limit: 5,
      });
      const result = response.data.operator_result || null;
      setChatResult(result);
      await loadBrief();
      await loadInbox();
      await loadContentHistory();
      await loadOperatorEvents();
    } catch (err) {
      setChatResult({
        status: 'blocked',
        intent: 'services_optimize',
        chat_response: err instanceof Error ? err.message : 'Не удалось оптимизировать услуги',
        blocked_reasons: ['operator_services_optimization_failed'],
      });
    } finally {
      setBulkGeneratingKey(null);
    }
  };

  const applyServiceSuggestions = async (jobId: string | undefined) => {
    if (!currentBusinessId || !jobId) return;
    setApplyingServiceJobId(jobId);
    setConsentMessage(null);
    setRefreshResult(null);
    try {
      const response = await api.post('/operator/services/optimize/apply', {
        business_id: currentBusinessId,
        job_id: jobId,
        limit: 5,
        confirm_apply: true,
      });
      const result = response.data.operator_result || null;
      setChatResult(result);
      await loadBrief();
      await loadInbox();
      await loadContentHistory();
      await loadOperatorEvents();
    } catch (err) {
      setChatResult({
        status: 'blocked',
        intent: 'services_optimize_apply',
        chat_response: err instanceof Error ? err.message : 'Не удалось применить предложения по услугам',
        blocked_reasons: ['operator_services_apply_failed'],
      });
    } finally {
      setApplyingServiceJobId(null);
    }
  };

  const markManualPublished = async (draftId: string | undefined) => {
    if (!currentBusinessId || !draftId) return;
    setManualPublishDraftId(draftId);
    setManualPublishMessage(null);
    try {
      const response = await api.post(`/operator/review-reply-drafts/${draftId}/mark-manual-published`, {
        business_id: currentBusinessId,
      });
      if (!response.data.success) {
        throw new Error(response.data.error || 'Не удалось отметить публикацию');
      }
      setManualPublishMessage('Отметил как опубликовано вручную. Внешней публикации LocalOS не выполнял.');
      await loadBrief();
      await loadInbox();
      await loadContentHistory();
      await loadOperatorEvents();
    } catch (err) {
      setManualPublishMessage(err instanceof Error ? err.message : 'Не удалось отметить публикацию');
    } finally {
      setManualPublishDraftId(null);
    }
  };

  const chatReviewHref =
    chatResult?.ui_actions?.find((item) => item.action === 'open_reviews')?.href ||
    '/dashboard/card?tab=reviews&review_filter=needs_reply';
  const chatNewsHref = chatResult?.ui_actions?.find((item) => item.action === 'open_news_drafts')?.href || '/dashboard/content-plan';
  const isContentDraftResult =
    Boolean(chatResult?.news_text || chatResult?.news_draft?.generated_text || chatResult?.social_post_text || chatResult?.social_post_draft?.generated_text);
  const chatSecondaryHref = isContentDraftResult ? chatNewsHref : chatReviewHref;
  const chatSecondaryLabel = isContentDraftResult ? 'Открыть черновики' : 'Открыть отзывы';

  const metrics = useMemo(() => {
    if (!brief) return [];
    return [
      {
        label: 'Отзывы без ответа',
        value: brief.metrics.reviews_without_response,
        hint: `${brief.metrics.reviews_total} отзывов в сохранённых данных`,
        tone: brief.metrics.reviews_without_response > 0 ? 'warning' : 'positive',
      },
      {
        label: 'Подтверждения',
        value: brief.metrics.pending_approvals,
        hint: 'Действия, ожидающие ручного решения',
        tone: brief.metrics.pending_approvals > 0 ? 'warning' : 'positive',
      },
      {
        label: 'Черновики',
        value: brief.metrics.pending_news + brief.metrics.review_reply_drafts,
        hint: 'Новости и ответы на отзывы',
        tone: brief.metrics.pending_news + brief.metrics.review_reply_drafts > 0 ? 'warning' : 'default',
      },
      {
        label: 'Партнёрства',
        value: brief.metrics.partnership_leads_ready,
        hint: 'Готовы к следующему шагу',
        tone: brief.metrics.partnership_leads_ready > 0 ? 'warning' : 'default',
      },
    ];
  }, [brief]);

  return (
    <div className="space-y-6">
      <DashboardPageHeader
        eyebrow="LocalOS Operator"
        title="Оператор"
        description="Главный слой управления поверх кабинета: можно смотреть разделы руками, а можно задавать рабочие команды в одном контуре."
        icon={Bot}
        actions={
          <Button type="button" variant="outline" onClick={() => void loadBrief()} disabled={loading || !currentBusinessId}>
            {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
            Обновить сводку
          </Button>
        }
      />

      <DashboardActionPanel
        title="Что требует моего внимания сегодня?"
        description={
          <div className="space-y-2">
            <p>
              Первый intent Operator работает только по сохранённым данным LocalOS. Он не запускает парсинг, не списывает кредиты и не публикует ничего во внешние системы.
            </p>
            <div className="flex flex-wrap gap-2">
              <span className="rounded-full bg-white/70 px-3 py-1 text-xs font-semibold text-slate-700 ring-1 ring-black/5">
                `free_cached`
              </span>
              <span className="rounded-full bg-white/70 px-3 py-1 text-xs font-semibold text-slate-700 ring-1 ring-black/5">
                Web chat MVP
              </span>
              <span className="rounded-full bg-white/70 px-3 py-1 text-xs font-semibold text-slate-700 ring-1 ring-black/5">
                Telegram-ready core
              </span>
            </div>
          </div>
        }
        status={
          brief ? (
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <span>{brief.summary.text}</span>
              <span className="shrink-0 text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                {brief.business.name || currentBusiness?.name || 'Бизнес'}
              </span>
            </div>
          ) : (
            <span>{currentBusinessId ? 'Готовлю сводку по бизнесу.' : 'Выберите бизнес, чтобы увидеть сводку.'}</span>
          )
        }
        tone="sky"
      />

      <DashboardSection
        title="Чат-команда"
        description="Можно вставить новый отзыв и попросить LocalOS добавить его в список и подготовить черновик ответа. Публикация в карты остаётся ручной."
      >
        <div className="grid gap-4 lg:grid-cols-[1fr_360px]">
          <div className="rounded-2xl border border-slate-200 bg-white px-4 py-4 shadow-sm">
            <textarea
              className="min-h-[180px] w-full resize-y rounded-xl border border-slate-200 bg-white px-3 py-3 text-sm leading-6 text-slate-950 outline-none ring-sky-200 placeholder:text-slate-400 focus:ring-2"
              value={chatMessage}
              onChange={(event) => setChatMessage(event.target.value)}
              placeholder="Добавь новый отзыв в список и сгенерируй ответ: ..."
            />
            <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-sm leading-6 text-slate-600">
                Если кредитов достаточно, генерация запускается без отдельного подтверждения. Если нет, LocalOS покажет ссылку на пополнение.
              </p>
              <Button type="button" onClick={() => void sendOperatorChatMessage()} disabled={chatLoading || !currentBusinessId || !chatMessage.trim()}>
                {chatLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Send className="mr-2 h-4 w-4" />}
                Отправить
              </Button>
            </div>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
            <div className="text-sm font-semibold text-slate-950">Ответ Operator</div>
            {chatResult ? (
              <div className="mt-3 space-y-3 text-sm leading-6 text-slate-700">
                <div
                  className={cn(
                    'rounded-xl border px-3 py-2',
                    chatResult.status === 'completed'
                      ? 'border-emerald-200 bg-emerald-50 text-emerald-950'
                      : 'border-amber-200 bg-amber-50 text-amber-950',
                  )}
                >
                  <div className="font-semibold">
                    {chatResult.status === 'completed' ? 'Выполнено' : chatResult.status === 'unsupported' ? 'Пока не умею' : 'Заблокировано'}
                  </div>
                  <div className="mt-2 whitespace-pre-wrap">{chatResult.chat_response}</div>
                </div>
                <div className="grid gap-2 sm:grid-cols-3">
                  <div className="rounded-xl border border-slate-200 bg-white px-3 py-2">
                    <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Кредиты</div>
                    <div className="mt-1 font-semibold text-slate-950">
                      {chatResult.credit_charged ? `Списано ${chatResult.charged_credits || 0}` : 'Не списаны'}
                    </div>
                  </div>
                  <div className="rounded-xl border border-slate-200 bg-white px-3 py-2">
                    <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Публикация</div>
                    <div className="mt-1 font-semibold text-slate-950">
                      {chatResult.manual_publication_only ? 'Вручную' : 'Нет внешнего действия'}
                    </div>
                  </div>
                  <div className="rounded-xl border border-slate-200 bg-white px-3 py-2">
                    <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Статус</div>
                    <div className="mt-1 font-semibold text-slate-950">{chatResult.status}</div>
                  </div>
                </div>
                {chatResult.reply_text ||
                chatResult.draft?.generated_text ||
                chatResult.news_text ||
                chatResult.news_draft?.generated_text ||
                chatResult.social_post_text ||
                chatResult.social_post_draft?.generated_text ? (
                  <div className="flex flex-col gap-2 sm:flex-row">
                    <Button type="button" size="sm" onClick={() => void copyChatReply()}>
                      <Copy className="mr-2 h-4 w-4" />
                      {copiedChatReply
                        ? 'Скопировано'
                        : chatResult.social_post_text || chatResult.social_post_draft?.generated_text
                          ? 'Скопировать пост'
                          : chatResult.news_text || chatResult.news_draft?.generated_text
                            ? 'Скопировать новость'
                            : 'Скопировать ответ'}
                    </Button>
                    <Button type="button" variant="outline" size="sm" asChild>
                      <Link to={chatSecondaryHref}>
                        {chatSecondaryLabel}
                        <ExternalLink className="ml-2 h-3.5 w-3.5" />
                      </Link>
                    </Button>
                  </div>
                ) : null}
                {chatResult.billing_url ? (
                  <Button type="button" variant="outline" size="sm" asChild>
                    <Link to={chatResult.billing_url}>Пополнить счёт</Link>
                  </Button>
                ) : null}
                {chatResult.queue_id ? (
                  <div className="rounded-xl border border-slate-200 bg-white px-3 py-2">
                    <div className="font-semibold">Задача обновления карты</div>
                    <div className="mt-1 text-slate-600">ID: {chatResult.queue_id}</div>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      className="mt-2"
                      onClick={() => void checkRefreshResult(chatResult.queue_id)}
                      disabled={refreshChecking}
                    >
                      {refreshChecking ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
                      Проверить результат обновления
                    </Button>
                  </div>
                ) : null}
                {refreshResult ? (
                  <div className="rounded-xl border border-slate-200 bg-white px-3 py-2">
                    <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                      <div>
                        <div className="font-semibold">Результат обновления</div>
                        <div className="mt-1 whitespace-pre-wrap text-slate-600">
                          {refreshResult.chat_response || 'Результат получен.'}
                        </div>
                      </div>
                      <span className="rounded-full bg-slate-100 px-2 py-1 text-xs font-semibold text-slate-700">
                        {refreshResult.status}
                      </span>
                    </div>
                    <div className="mt-3 grid gap-2 sm:grid-cols-2">
                      <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
                        <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Новые</div>
                        <div className="mt-1 font-semibold text-slate-950">{refreshResult.new_reviews_count || 0}</div>
                      </div>
                      <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
                        <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Без ответа</div>
                        <div className="mt-1 font-semibold text-slate-950">{refreshResult.new_unanswered_reviews_count || 0}</div>
                      </div>
                    </div>
                    {renderBillingDetails(refreshResult.billing_state)}
                    {renderReliabilityDetails(refreshResult.reliability_state)}
                    {refreshResult.new_reviews?.length ? (
                      <div className="mt-3 space-y-2">
                        {refreshResult.new_reviews.map((review) => (
                          <div key={review.id || review.external_review_id || review.text} className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="font-semibold text-slate-950">{review.author_name || 'Новый отзыв'}</span>
                              {review.rating ? <span className="text-xs font-semibold text-slate-500">{review.rating}/5</span> : null}
                              {!review.has_response ? (
                                <span className="rounded-full bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-800 ring-1 ring-amber-200">
                                  без ответа
                                </span>
                              ) : null}
                            </div>
                            <div className="mt-1 line-clamp-4 text-slate-700">{review.text}</div>
                          </div>
                        ))}
                      </div>
                    ) : null}
                    {(refreshResult.new_unanswered_reviews_count || 0) > 0 ? (
                      <Button
                        type="button"
                        size="sm"
                        className="mt-3"
                        onClick={() => void generateReviewReplies()}
                        disabled={bulkGeneratingKey === 'review_replies_generate'}
                      >
                        {bulkGeneratingKey === 'review_replies_generate' ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <MessageSquareText className="mr-2 h-4 w-4" />}
                        Подготовить ответы
                      </Button>
                    ) : null}
                  </div>
                ) : null}
                {chatResult.review?.id ? (
                  <div className="rounded-xl border border-slate-200 bg-white px-3 py-2">
                    <div className="font-semibold">Отзыв добавлен</div>
                    <div className="line-clamp-4">{chatResult.review.text}</div>
                  </div>
                ) : null}
                {chatResult.draft?.id ? (
                  <div className="rounded-xl border border-slate-200 bg-white px-3 py-2">
                    <div className="font-semibold">Черновик ответа</div>
                    <div>Статус: {chatResult.draft.status || 'draft'}</div>
                    {chatResult.charged_credits ? <div>Списано кредитов: {chatResult.charged_credits}</div> : null}
                    <div className="mt-1 text-slate-600">
                      LocalOS сохранил черновик. Чтобы ответ появился на карте, скопируйте его и вставьте в кабинете площадки.
                    </div>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      className="mt-2"
                      onClick={() => void markManualPublished(chatResult.draft?.id)}
                      disabled={manualPublishDraftId === chatResult.draft.id}
                    >
                      {manualPublishDraftId === chatResult.draft.id ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <CheckCircle2 className="mr-2 h-4 w-4" />}
                      Отметить как опубликовано вручную
                    </Button>
                  </div>
                ) : null}
                {chatResult.news_draft?.id ? (
                  <div className="rounded-xl border border-slate-200 bg-white px-3 py-2">
                    <div className="font-semibold">Черновик новости</div>
                    <div>Статус: {chatResult.news_draft.status || 'draft'}</div>
                    {chatResult.charged_credits ? <div>Списано кредитов: {chatResult.charged_credits}</div> : null}
                    <div className="mt-1 text-slate-600">
                      LocalOS сохранил черновик. Публикация не выполнялась: текст нужно скопировать и разместить вручную.
                    </div>
                  </div>
                ) : null}
                {chatResult.social_post_draft?.id ? (
                  <div className="rounded-xl border border-slate-200 bg-white px-3 py-2">
                    <div className="font-semibold">Черновик поста</div>
                    <div>Статус: {chatResult.social_post_draft.status || 'draft'}</div>
                    {chatResult.charged_credits ? <div>Списано кредитов: {chatResult.charged_credits}</div> : null}
                    <div className="mt-1 text-slate-600">
                      LocalOS сохранил черновик. Публикация не выполнялась: текст нужно скопировать и разместить вручную.
                    </div>
                  </div>
                ) : null}
                {chatResult.service_suggestions?.length ? (
                  <div className="rounded-xl border border-slate-200 bg-white px-3 py-2">
                    <div className="font-semibold">Предложения по услугам</div>
                    <div className="mt-1 text-slate-600">
                      Создано: {chatResult.service_suggestions.length}. Изменения не применялись и требуют отдельного подтверждения.
                    </div>
                    <div className="mt-3 space-y-2">
                      {chatResult.service_suggestions.map((item) => (
                        <div key={item.id || item.service_id} className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
                          <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">{item.before_name}</div>
                          <div className="mt-1 font-semibold text-slate-950">{item.optimized_name}</div>
                          {item.seo_description ? <div className="mt-1 text-slate-700">{item.seo_description}</div> : null}
                        </div>
                      ))}
                    </div>
                    {chatResult.optimization_job?.id ? (
                      <div className="mt-3 flex flex-wrap items-center gap-2">
                        <Button
                          type="button"
                          size="sm"
                          onClick={() => void applyServiceSuggestions(chatResult.optimization_job?.id)}
                          disabled={applyingServiceJobId === chatResult.optimization_job.id}
                        >
                          {applyingServiceJobId === chatResult.optimization_job.id ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <CheckCircle2 className="mr-2 h-4 w-4" />}
                          Применить предложения
                        </Button>
                        <span className="text-xs text-slate-500">Обновит только услуги в LocalOS, без публикации в карты.</span>
                      </div>
                    ) : null}
                  </div>
                ) : null}
                {chatResult.applied_items?.length ? (
                  <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-emerald-950">
                    <div className="font-semibold">Услуги обновлены</div>
                    <div className="mt-1 text-emerald-800">
                      Применено: {chatResult.applied_count || chatResult.applied_items.length}. Внешние карты не изменялись.
                    </div>
                    <div className="mt-3 space-y-2">
                      {chatResult.applied_items.map((item) => (
                        <div key={item.id || item.service_id} className="rounded-lg border border-emerald-200 bg-white px-3 py-2">
                          <div className="text-xs font-semibold uppercase tracking-[0.14em] text-emerald-700">{item.before_name}</div>
                          <div className="mt-1 font-semibold text-slate-950">{item.optimized_name}</div>
                          {item.seo_description ? <div className="mt-1 text-slate-700">{item.seo_description}</div> : null}
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}
                {chatResult.drafts?.length ? (
                  <div className="rounded-xl border border-slate-200 bg-white px-3 py-2">
                    <div className="font-semibold">Черновики ответов</div>
                    <div className="mt-1 text-slate-600">
                      Создано: {chatResult.drafts.length}. Публикация в карты выполняется вручную.
                    </div>
                    <div className="mt-3 space-y-2">
                      {chatResult.drafts.map((draft) => (
                        <div key={draft.id || draft.review_id} className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
                          <div className="whitespace-pre-wrap text-slate-700">{draft.generated_text}</div>
                          <div className="mt-2 flex flex-wrap gap-2">
                            <Button type="button" size="sm" onClick={() => void copyDraftText(draft)}>
                              <Copy className="mr-2 h-4 w-4" />
                              {copiedInboxItemId === draft.id ? 'Скопировано' : 'Скопировать'}
                            </Button>
                            <Button
                              type="button"
                              size="sm"
                              variant="outline"
                              onClick={() => void markManualPublished(draft.id)}
                              disabled={!draft.id || manualPublishDraftId === draft.id}
                            >
                              {manualPublishDraftId === draft.id ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <CheckCircle2 className="mr-2 h-4 w-4" />}
                              Отметить вручную
                            </Button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}
              </div>
            ) : (
              <p className="mt-3 text-sm leading-6 text-slate-600">
                Здесь появится ответ, готовый черновик и сведения о списании кредитов.
              </p>
            )}
          </div>
        </div>
      </DashboardSection>

      <DashboardSection
        title="Черновики и предложения"
        description="Единая история созданного контента: ответы, новости, соцпосты и изменения услуг."
      >
        {contentHistory ? (
          <div className="space-y-3">
            <div className="grid gap-3 sm:grid-cols-5">
              {['review_reply_draft', 'news_draft', 'social_post_draft', 'service_suggestion', 'service_apply'].map((kind) => (
                <div key={kind} className="rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
                  <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">{contentKindLabels[kind]}</div>
                  <div className="mt-1 text-xl font-semibold text-slate-950">{contentHistory.summary.type_counts[kind] || 0}</div>
                </div>
              ))}
            </div>
            {contentHistory.items.length > 0 ? (
              <div className="space-y-3">
                {contentHistory.items.map((item) => (
                  <div key={`${item.kind}-${item.id}`} className="rounded-2xl border border-slate-200 bg-white px-4 py-4 shadow-sm">
                    <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <h3 className="text-sm font-semibold text-slate-950">{item.title}</h3>
                          <span className={cn('rounded-full px-2 py-1 text-xs font-medium ring-1', contentKindStyles[item.kind] || 'bg-slate-100 text-slate-700 ring-slate-200')}>
                            {contentKindLabels[item.kind] || item.kind}
                          </span>
                          <span className="rounded-full bg-slate-100 px-2 py-1 text-xs font-medium text-slate-600">
                            {item.status}
                          </span>
                          {item.manual_publication_only ? (
                            <span className="rounded-full bg-sky-50 px-2 py-1 text-xs font-medium text-sky-800 ring-1 ring-sky-200">
                              ручная публикация
                            </span>
                          ) : null}
                        </div>
                        <div className="mt-2 text-sm leading-6 text-slate-600">
                          Создано: {formatDateTime(item.created_at || null)}. Обновлено: {formatDateTime(item.updated_at || null)}.
                        </div>
                        {item.text ? <p className="mt-2 line-clamp-4 text-sm leading-6 text-slate-700">{item.text}</p> : null}
                      </div>
                      {item.href ? (
                        <Button type="button" size="sm" variant="outline" className="shrink-0" asChild>
                          <Link to={item.href}>
                            Открыть
                            <ExternalLink className="ml-2 h-3.5 w-3.5" />
                          </Link>
                        </Button>
                      ) : null}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <DashboardEmptyState
                title="Черновиков пока нет"
                description="Когда Operator подготовит ответ, новость, пост или предложения по услугам, они появятся здесь отдельными типами."
              />
            )}
          </div>
        ) : (
          <DashboardEmptyState
            title="История не загружена"
            description="Выберите бизнес или обновите Operator, чтобы увидеть последние черновики."
          />
        )}
      </DashboardSection>

      <DashboardSection
        title="Обновления отзывов"
        description="Последние read-only обновления карт: статус, результат и быстрый переход к подготовке ответов."
      >
        {refreshJobs ? (
          <div className="space-y-3">
            {refreshRetryResult ? (
              <div className={cn(
                'rounded-2xl border px-4 py-3 text-sm leading-6',
                refreshRetryResult.status === 'queued'
                  ? 'border-emerald-200 bg-emerald-50 text-emerald-900'
                  : 'border-amber-200 bg-amber-50 text-amber-900',
              )}>
                <div className="font-semibold">
                  {refreshRetryResult.status === 'queued' ? 'Повтор refresh запущен' : 'Повтор refresh недоступен'}
                </div>
                {refreshRetryResult.chat_response ? <div className="mt-1 whitespace-pre-line">{refreshRetryResult.chat_response}</div> : null}
                {refreshRetryResult.blocked_reasons?.length ? (
                  <div className="mt-1 text-xs font-semibold">
                    Причины: {refreshRetryResult.blocked_reasons.join(', ')}
                  </div>
                ) : null}
              </div>
            ) : null}
            <div className="grid gap-3 sm:grid-cols-4 lg:grid-cols-6">
              <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
                <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Всего</div>
                <div className="mt-1 text-xl font-semibold text-slate-950">{refreshJobs.summary.jobs_count}</div>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
                <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">В работе</div>
                <div className="mt-1 text-xl font-semibold text-slate-950">{refreshJobs.summary.processing_count}</div>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
                <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Новые</div>
                <div className="mt-1 text-xl font-semibold text-slate-950">{refreshJobs.summary.new_reviews_count}</div>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
                <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Без ответа</div>
                <div className="mt-1 text-xl font-semibold text-slate-950">{refreshJobs.summary.new_unanswered_reviews_count}</div>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
                <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Резерв</div>
                <div className="mt-1 text-xl font-semibold text-slate-950">{refreshJobs.summary.reserved_credits || 0}</div>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
                <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Списано</div>
                <div className="mt-1 text-xl font-semibold text-slate-950">{refreshJobs.summary.charged_credits || 0}</div>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
                <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Retry</div>
                <div className="mt-1 text-xl font-semibold text-slate-950">{refreshJobs.summary.retrying_count || 0}</div>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
                <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Captcha</div>
                <div className="mt-1 text-xl font-semibold text-slate-950">{refreshJobs.summary.captcha_required_count || 0}</div>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
                <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Ошибки</div>
                <div className="mt-1 text-xl font-semibold text-slate-950">{refreshJobs.summary.reliability_failed_count || 0}</div>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
                <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Warnings</div>
                <div className="mt-1 text-xl font-semibold text-slate-950">{refreshJobs.summary.warning_count || 0}</div>
              </div>
            </div>
            {refreshJobs.jobs.length > 0 ? (
              <div className="space-y-3">
                {refreshJobs.jobs.map((job) => (
                  <div key={job.queue_id} className="rounded-2xl border border-slate-200 bg-white px-4 py-4 shadow-sm">
                    <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <h3 className="text-sm font-semibold text-slate-950">Обновление отзывов</h3>
                          <span className={cn('rounded-full px-2 py-1 text-xs font-medium ring-1', refreshJobStatusStyles[job.status])}>
                            {refreshJobStatusLabels[job.status]}
                          </span>
                          {job.queue_status ? (
                            <span className="rounded-full bg-slate-100 px-2 py-1 text-xs font-medium text-slate-600">
                              {job.queue_status}
                            </span>
                          ) : null}
                          {job.retry_source_queue_id || job.billing_state?.retry_source_queue_id ? (
                            <span className="rounded-full bg-violet-50 px-2 py-1 text-xs font-medium text-violet-800 ring-1 ring-violet-200">
                              Повтор от job {(job.retry_source_queue_id || job.billing_state?.retry_source_queue_id || '').slice(0, 8)}
                            </span>
                          ) : null}
                        </div>
                        <div className="mt-2 text-sm leading-6 text-slate-600">
                          Запуск: {formatDateTime(job.created_at || null)}. Последнее изменение: {formatDateTime(job.updated_at || null)}.
                        </div>
                        {job.chat_response ? <p className="mt-2 text-sm leading-6 text-slate-700">{job.chat_response}</p> : null}
                        {job.error_message ? <p className="mt-2 text-sm leading-6 text-rose-700">{job.error_message}</p> : null}
                        {renderBillingDetails(job.billing_state)}
                        {renderReliabilityDetails(job.reliability_state)}
                        {job.new_reviews?.length ? (
                          <div className="mt-3 space-y-2">
                            {job.new_reviews.map((review) => (
                              <div key={review.id || review.external_review_id || review.text} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
                                <div className="flex flex-wrap items-center gap-2 text-sm">
                                  <span className="font-semibold text-slate-950">{review.author_name || 'Новый отзыв'}</span>
                                  {review.rating ? <span className="text-xs font-semibold text-slate-500">{review.rating}/5</span> : null}
                                  {!review.has_response ? (
                                    <span className="rounded-full bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-800 ring-1 ring-amber-200">
                                      без ответа
                                    </span>
                                  ) : null}
                                </div>
                                {review.text ? <div className="mt-1 line-clamp-3 text-sm leading-6 text-slate-700">{review.text}</div> : null}
                              </div>
                            ))}
                          </div>
                        ) : null}
                      </div>
                      <div className="flex shrink-0 flex-col gap-2 sm:flex-row lg:justify-end">
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          onClick={() => void checkRefreshResult(job.queue_id)}
                          disabled={refreshChecking}
                        >
                          {refreshChecking ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
                          Проверить результат
                        </Button>
                        {canRequestRefreshRetry(job) ? (
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            onClick={() => void requestRefreshRetry(job.queue_id)}
                            disabled={refreshRetryingQueueId === job.queue_id}
                          >
                            {refreshRetryingQueueId === job.queue_id ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
                            Повторить refresh
                          </Button>
                        ) : null}
                        <Button type="button" size="sm" variant="outline" asChild>
                          <Link to="/dashboard/card?tab=reviews&review_filter=needs_reply">
                            Открыть отзывы
                            <ExternalLink className="ml-2 h-3.5 w-3.5" />
                          </Link>
                        </Button>
                        {(job.new_unanswered_reviews_count || 0) > 0 ? (
                          <Button
                            type="button"
                            size="sm"
                            onClick={() => void generateReviewReplies()}
                            disabled={bulkGeneratingKey === 'review_replies_generate'}
                          >
                            {bulkGeneratingKey === 'review_replies_generate' ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <MessageSquareText className="mr-2 h-4 w-4" />}
                            Подготовить ответы
                          </Button>
                        ) : null}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <DashboardEmptyState
                title="Обновлений пока нет"
                description="Когда Operator запустит проверку новых отзывов, здесь появится история задач и их результаты."
              />
            )}
          </div>
        ) : (
          <DashboardEmptyState
            title="История обновлений не загружена"
            description="Выберите бизнес или обновите сводку, чтобы увидеть последние refresh jobs."
          />
        )}
      </DashboardSection>

      {error ? (
        <DashboardEmptyState
          title="Не удалось загрузить Operator"
          description={error}
          action={
            <Button type="button" onClick={() => void loadBrief()}>
              Повторить
            </Button>
          }
        />
      ) : null}

      {brief ? (
        <>
          <DashboardCompactMetricsRow items={metrics} />

          <DashboardSection
            title="Operator Inbox"
            description="Единая очередь действий: что открыть, что скопировать и что можно отметить как выполненное вручную."
          >
            {manualPublishMessage ? (
              <div className="mb-3 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm leading-6 text-slate-700">
                {manualPublishMessage}
              </div>
            ) : null}
            {inbox ? (
              <div className="space-y-3">
                <div className="rounded-2xl border border-slate-200 bg-white px-4 py-4 shadow-sm">
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                      <div className="text-sm font-semibold text-slate-950">{inbox.summary.title}</div>
                      <p className="mt-1 text-sm leading-6 text-slate-600">{inbox.summary.text}</p>
                    </div>
                    <div className="rounded-xl bg-slate-100 px-3 py-2 text-sm font-semibold text-slate-700">
                      {inbox.summary.items_count} пунктов
                    </div>
                  </div>
                </div>
                {inbox.items.length > 0 ? (
                  inbox.items.map((item) => (
                    <div key={item.id} className="rounded-2xl border border-slate-200 bg-white px-4 py-4 shadow-sm">
                      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                        <div className="min-w-0">
                          <div className="flex flex-wrap items-center gap-2">
                            <h3 className="text-sm font-semibold text-slate-950">{item.title}</h3>
                            <span
                              className={cn(
                                'rounded-full px-2 py-1 text-xs font-medium ring-1',
                                item.priority === 'high'
                                  ? 'bg-rose-50 text-rose-800 ring-rose-200'
                                  : item.priority === 'medium'
                                    ? 'bg-amber-50 text-amber-800 ring-amber-200'
                                    : 'bg-slate-100 text-slate-700 ring-slate-200',
                              )}
                            >
                              {item.status}
                            </span>
                            {item.metadata?.manual_publication_only ? (
                              <span className="rounded-full bg-sky-50 px-2 py-1 text-xs font-medium text-sky-800 ring-1 ring-sky-200">
                                ручная публикация
                              </span>
                            ) : null}
                          </div>
                          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">{item.description}</p>
                          {item.copy_text ? (
                            <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm leading-6 text-slate-700">
                              {item.copy_text}
                            </div>
                          ) : null}
                        </div>
                        <div className="flex shrink-0 flex-col gap-2 sm:flex-row lg:justify-end">
                          {item.copy_text ? (
                            <Button type="button" size="sm" onClick={() => void copyInboxText(item)}>
                              <Copy className="mr-2 h-4 w-4" />
                              {copiedInboxItemId === item.id ? 'Скопировано' : 'Скопировать'}
                            </Button>
                          ) : null}
                          {item.secondary_action === 'mark_manual_published' ? (
                            <Button
                              type="button"
                              size="sm"
                              variant="outline"
                              onClick={() => void markManualPublished(item.id)}
                              disabled={manualPublishDraftId === item.id}
                            >
                              {manualPublishDraftId === item.id ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <CheckCircle2 className="mr-2 h-4 w-4" />}
                              Отмечено вручную
                            </Button>
                          ) : null}
                          {item.href ? (
                            <Button type="button" size="sm" variant="outline" asChild>
                              <Link to={item.href}>
                                Открыть
                                <ExternalLink className="ml-2 h-3.5 w-3.5" />
                              </Link>
                            </Button>
                          ) : null}
                        </div>
                      </div>
                    </div>
                  ))
                ) : (
                  <DashboardEmptyState
                    title="Очередь пуста"
                    description="По сохранённым данным нет срочных действий для Operator."
                  />
                )}
                {inbox.paid_generation_offers.length > 0 ? (
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
                    <div className="text-sm font-semibold text-slate-950">Платные генерации доступны через единый слой</div>
                    <div className="mt-3 grid gap-2 sm:grid-cols-2">
                      {inbox.paid_generation_offers.map((offer) => (
                        <div key={offer.action_key} className="rounded-xl border border-slate-200 bg-white px-3 py-2">
                          <div className="text-sm font-semibold text-slate-950">{offer.label}</div>
                          <div className="mt-1 text-xs leading-5 text-slate-600">
                            {offer.description} Оценка: {offer.estimated_credits ?? 'по факту'} кредит.
                          </div>
                          {offer.action_key === 'review_replies_generate' ? (
                            <Button
                              type="button"
                              size="sm"
                              className="mt-2"
                              onClick={() => void generateReviewReplies()}
                              disabled={bulkGeneratingKey === offer.action_key || !currentBusinessId}
                            >
                              {bulkGeneratingKey === offer.action_key ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <MessageSquareText className="mr-2 h-4 w-4" />}
                              Подготовить ответы
                            </Button>
                          ) : null}
                          {offer.action_key === 'news_generate' ? (
                            <Button
                              type="button"
                              size="sm"
                              className="mt-2"
                              onClick={() => void generateNewsDraft()}
                              disabled={bulkGeneratingKey === offer.action_key || !currentBusinessId}
                            >
                              {bulkGeneratingKey === offer.action_key ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <MessageSquareText className="mr-2 h-4 w-4" />}
                              Подготовить новость
                            </Button>
                          ) : null}
                          {offer.action_key === 'social_post_generate' ? (
                            <Button
                              type="button"
                              size="sm"
                              className="mt-2"
                              onClick={() => void generateSocialPostDraft()}
                              disabled={bulkGeneratingKey === offer.action_key || !currentBusinessId}
                            >
                              {bulkGeneratingKey === offer.action_key ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <MessageSquareText className="mr-2 h-4 w-4" />}
                              Подготовить пост
                            </Button>
                          ) : null}
                          {offer.action_key === 'services_optimize' ? (
                            <Button
                              type="button"
                              size="sm"
                              className="mt-2"
                              onClick={() => void optimizeServices()}
                              disabled={bulkGeneratingKey === offer.action_key || !currentBusinessId}
                            >
                              {bulkGeneratingKey === offer.action_key ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <CheckCircle2 className="mr-2 h-4 w-4" />}
                              Оптимизировать услуги
                            </Button>
                          ) : null}
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}
              </div>
            ) : (
              <DashboardEmptyState
                title="Inbox не загрузился"
                description="Можно продолжать работать через сводку и чат-команду."
              />
            )}
          </DashboardSection>

          <DashboardSection
            title="Сигналы"
            description="Пункты отсортированы так, чтобы первым был самый полезный следующий шаг."
          >
            <div className="space-y-3">
              {brief.items.map((item) => {
                const Icon = getItemIcon(item);
                return (
                  <div
                    key={item.id}
                    className="flex flex-col gap-4 rounded-2xl border border-slate-200 bg-white px-4 py-4 shadow-sm sm:flex-row sm:items-start sm:justify-between"
                  >
                    <div className="flex min-w-0 gap-3">
                      <div className={cn('flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border', severityStyles[item.severity])}>
                        <Icon className="h-5 w-5" />
                      </div>
                      <div className="min-w-0 space-y-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <h3 className="text-sm font-semibold text-slate-950">{item.title}</h3>
                          <span className="rounded-full bg-slate-100 px-2 py-1 text-xs font-medium text-slate-600">
                            {actionClassLabels[item.action_class]}
                          </span>
                        </div>
                        <p className="max-w-3xl text-sm leading-6 text-slate-600">{item.description}</p>
                      </div>
                    </div>
                    <div className="flex shrink-0 items-center gap-2 sm:justify-end">
                      {item.count > 0 ? (
                        <div className="min-w-10 rounded-xl bg-slate-950 px-3 py-2 text-center text-sm font-semibold text-white">
                          {item.count}
                        </div>
                      ) : null}
                      {item.cta?.href ? (
                        <Button type="button" variant="outline" size="sm" asChild>
                          <Link to={item.cta.href}>
                            {item.cta.label || 'Открыть'}
                            <ExternalLink className="ml-2 h-3.5 w-3.5" />
                          </Link>
                        </Button>
                      ) : null}
                    </div>
                  </div>
                );
              })}
            </div>
          </DashboardSection>

          <DashboardSection title="Свежесть данных">
            <div className="grid gap-4 lg:grid-cols-[1fr_1fr]">
              <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
                <div className="flex items-center gap-2 text-sm font-semibold text-slate-950">
                  <Clock3 className="h-4 w-4" />
                  Последнее обновление
                </div>
                <div className="mt-3 space-y-2 text-sm leading-6 text-slate-600">
                  <p>Карточка: {formatDateTime(brief.freshness.latest_card_at)}</p>
                  <p>Отзывы: {formatDateTime(brief.freshness.latest_reviews_at)}</p>
                </div>
              </div>
              <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-4 text-sm leading-6 text-amber-950">
                <div className="font-semibold">Платное обновление не запускалось</div>
                <p className="mt-2">{brief.freshness.message}</p>
              </div>
            </div>
          </DashboardSection>

          {brief.paid_action_offers && brief.paid_action_offers.length > 0 ? (
            <DashboardSection
              title="Платные действия"
              description="Operator может предложить платный шаг, сохранить consent policy и выполнить preflight. Платные действия всё ещё не запускаются и не списываются."
            >
              {consentMessage ? (
                <div className="mb-3 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm leading-6 text-slate-700">
                  {consentMessage}
                </div>
              ) : null}
              <div className="space-y-3">
                {brief.paid_action_offers.map((offer) => {
                  const draft = consentDrafts[offer.action_key] || makeConsentDraft(offer);
                  const preflightDraft = preflightDrafts[offer.action_key] || makePreflightDraft(offer);
                  const preflightResult = preflightResults[offer.action_key];
                  const executionAttempt = executionAttempts[offer.action_key];
                  const autoMode = draft.mode === 'auto_with_limits';
                  return (
                    <div key={offer.action_key} className="rounded-2xl border border-slate-200 bg-white px-4 py-4 shadow-sm">
                      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                        <div className="min-w-0">
                          <div className="flex flex-wrap items-center gap-2">
                            <h3 className="text-sm font-semibold text-slate-950">{offer.label}</h3>
                            <span className="rounded-full bg-amber-50 px-2 py-1 text-xs font-medium text-amber-800 ring-1 ring-amber-200">
                              {actionClassLabels[offer.action_class]}
                            </span>
                            <span className="rounded-full bg-slate-100 px-2 py-1 text-xs font-medium text-slate-600">
                              proposal only
                            </span>
                            {offer.current_consent_policy?.execution_allowed_without_prompt ? (
                              <span className="rounded-full bg-emerald-50 px-2 py-1 text-xs font-medium text-emerald-800 ring-1 ring-emerald-200">
                                auto with limits
                              </span>
                            ) : null}
                          </div>
                          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">{offer.copy.primary}</p>
                          <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-600">{offer.copy.disclosure}</p>
                        </div>
                        <div className="rounded-xl bg-slate-50 px-3 py-2 text-xs font-medium leading-5 text-slate-600">
                          <div>Источник стоимости: {offer.cost_source}</div>
                          <div>Провайдер: {offer.provider}</div>
                          <div>Множитель: x{offer.credit_multiplier}</div>
                        </div>
                      </div>
                      <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 px-3 py-3">
                        <div className="grid gap-3 lg:grid-cols-[1fr_1fr]">
                          <label className="space-y-1 text-sm font-medium text-slate-700">
                            <span>Режим consent</span>
                            <select
                              className="h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm text-slate-950 outline-none ring-sky-200 focus:ring-2"
                              value={draft.mode}
                              onChange={(event) => updateConsentDraft(offer.action_key, { mode: event.target.value })}
                            >
                              <option value="ask_each_time">Спрашивать каждый раз</option>
                              <option value="auto_with_limits">Разрешить в пределах лимитов</option>
                              <option value="disabled">Запретить платное действие</option>
                            </select>
                          </label>
                          <div className="text-sm leading-6 text-slate-600">
                            {autoMode
                              ? 'Для автозапуска нужны лимиты на действие и день. Без них API не сохранит режим auto_with_limits.'
                              : 'Этот режим не разрешает платный запуск без отдельного подтверждения.'}
                          </div>
                        </div>
                        {autoMode ? (
                          <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                            <ConsentLimitInput
                              label="На действие"
                              value={draft.max_credits_per_action}
                              onChange={(value) => updateConsentDraft(offer.action_key, { max_credits_per_action: value })}
                            />
                            <ConsentLimitInput
                              label="В день"
                              value={draft.max_credits_per_day}
                              onChange={(value) => updateConsentDraft(offer.action_key, { max_credits_per_day: value })}
                            />
                            <ConsentLimitInput
                              label="В месяц"
                              value={draft.max_credits_per_month}
                              onChange={(value) => updateConsentDraft(offer.action_key, { max_credits_per_month: value })}
                            />
                            <ConsentLimitInput
                              label="Предупредить при"
                              value={draft.low_balance_warning_threshold}
                              onChange={(value) => updateConsentDraft(offer.action_key, { low_balance_warning_threshold: value })}
                            />
                          </div>
                        ) : null}
                        <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                          <div className="text-sm leading-6 text-slate-700">{offer.copy.auto_consent_question}</div>
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            onClick={() => void saveConsentPolicy(offer)}
                            disabled={savingConsentKey === offer.action_key}
                          >
                            {savingConsentKey === offer.action_key ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                            Сохранить policy
                          </Button>
                        </div>
                      </div>
                      <div className="mt-3 rounded-xl border border-sky-200 bg-sky-50 px-3 py-3">
                        <div className="grid gap-3 lg:grid-cols-[1fr_1fr]">
                          <ConsentLimitInput
                            label="Оценка, кредитов"
                            value={preflightDraft.estimated_credits}
                            onChange={(value) => updatePreflightDraft(offer.action_key, { estimated_credits: value })}
                          />
                          <label className="flex items-center gap-2 pt-7 text-sm font-medium text-slate-700">
                            <input
                              type="checkbox"
                              className="h-4 w-4 rounded border-slate-300"
                              checked={preflightDraft.explicit_consent}
                              onChange={(event) => updatePreflightDraft(offer.action_key, { explicit_consent: event.target.checked })}
                            />
                            Проверить как разовое явное согласие
                          </label>
                        </div>
                        <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                          <div className="text-sm leading-6 text-slate-700">
                            Preflight проверит баланс, лимиты и consent. Запуск, Apify и списание кредитов отключены.
                          </div>
                          <div className="flex flex-col gap-2 sm:flex-row">
                            <Button
                              type="button"
                              size="sm"
                              variant="outline"
                              onClick={() => void runPreflight(offer)}
                              disabled={preflightingKey === offer.action_key}
                            >
                              {preflightingKey === offer.action_key ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                              Preflight
                            </Button>
                            <Button
                              type="button"
                              size="sm"
                              onClick={() => void runExecutionAttempt(offer)}
                              disabled={executingKey === offer.action_key}
                            >
                              {executingKey === offer.action_key ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                              Проверить execute
                            </Button>
                          </div>
                        </div>
                        {preflightResult ? (
                          <div className={cn(
                            'mt-3 rounded-xl border px-3 py-2 text-sm leading-6',
                            preflightResult.status === 'ready'
                              ? 'border-emerald-200 bg-emerald-50 text-emerald-900'
                              : 'border-amber-200 bg-amber-50 text-amber-950',
                          )}>
                            <div className="font-semibold">
                              {preflightResult.status === 'ready' ? 'Preflight пройден' : 'Preflight заблокирован'}
                            </div>
                            <div>{preflightResult.copy.summary}</div>
                            <div>
                              Оценка: {preflightResult.estimated_credits ?? 'нет'} кредитов;
                              баланс: {preflightResult.balance_credits ?? 'нет данных'}.
                            </div>
                            {preflightResult.blocked_reasons.length > 0 ? (
                              <div>Причины: {preflightResult.blocked_reasons.join(', ')}</div>
                            ) : null}
                            {preflightResult.warnings.length > 0 ? (
                              <div>Предупреждения: {preflightResult.warnings.join(', ')}</div>
                            ) : null}
                            <div>Execution status: {preflightResult.execution_status}; списаний и внешних вызовов нет.</div>
                          </div>
                        ) : null}
                        {executionAttempt ? (
                          <div className="mt-3 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm leading-6 text-rose-950">
                            <div className="font-semibold">{executionAttempt.copy.summary}</div>
                            <div>{executionAttempt.copy.blocked}</div>
                            <div>
                              Execution status: {executionAttempt.execution_status}; next step: {executionAttempt.next_step}.
                            </div>
                            <div>Причины: {executionAttempt.blocked_reasons.join(', ')}</div>
                            <div>
                              Списаний: нет; внешних вызовов: нет; parsequeue: нет; AI генерации: нет.
                            </div>
                            {executionAttempt.reservation_plan ? (
                              <div className="mt-2 rounded-lg border border-rose-200 bg-white/60 px-3 py-2">
                                <div className="font-semibold">Credit reservation: {executionAttempt.reservation_plan.status}</div>
                                <div>
                                  Запрос: {executionAttempt.reservation_plan.requested_credits ?? 'нет оценки'}; уже зарезервировано:{' '}
                                  {executionAttempt.reservation_plan.active_reserved_credits ?? 'н/д'}; доступно после резервов:{' '}
                                  {executionAttempt.reservation_plan.available_after_reservations ?? 'н/д'}.
                                </div>
                                {executionAttempt.reservation_plan.blocked_reasons.length > 0 ? (
                                  <div>Причины: {executionAttempt.reservation_plan.blocked_reasons.join(', ')}</div>
                                ) : null}
                              </div>
                            ) : null}
                            {executionAttempt.adapter_result ? (
                              <div className="mt-2 rounded-lg border border-rose-200 bg-white/60 px-3 py-2">
                                <div className="font-semibold">
                                  Adapter: {executionAttempt.adapter_result.runtime_mode}; {executionAttempt.adapter_result.adapter_status}
                                </div>
                                <div className="mt-1 flex flex-wrap gap-1.5">
                                  {executionAttempt.adapter_result.stages.map((stage) => (
                                    <span key={stage.stage} className="rounded-full bg-white px-2 py-1 text-xs font-medium text-rose-900 ring-1 ring-rose-200">
                                      {stage.stage}: {stage.status}
                                    </span>
                                  ))}
                                </div>
                              </div>
                            ) : null}
                          </div>
                        ) : null}
                      </div>
                    </div>
                  );
                })}
              </div>
            </DashboardSection>
          ) : null}

          <DashboardSection
            title="Журнал Operator"
            description="События пишутся в общий ledger наблюдаемости: brief, consent и preflight. Это не кредитный ledger и не запуск внешних инструментов."
          >
            {operatorEvents.length > 0 ? (
              <div className="space-y-3">
                {operatorEvents.map((event) => (
                  <div key={event.id} className="rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
                    <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <h3 className="text-sm font-semibold text-slate-950">{eventLabels[event.event_type] || event.event_type}</h3>
                          <span className="rounded-full bg-slate-100 px-2 py-1 text-xs font-medium text-slate-600">
                            {event.status || 'recorded'}
                          </span>
                          {event.metadata?.action_key ? (
                            <span className="rounded-full bg-sky-50 px-2 py-1 text-xs font-medium text-sky-800 ring-1 ring-sky-200">
                              {event.metadata.action_key}
                            </span>
                          ) : null}
                        </div>
                        <p className="mt-2 text-sm leading-6 text-slate-600">{event.output_summary || event.input_summary || 'Событие записано.'}</p>
                      </div>
                      <div className="shrink-0 text-xs font-medium leading-5 text-slate-500">
                        <div>{formatDateTime(event.created_at)}</div>
                        <div>risk: {event.risk_level || 'low'}</div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <DashboardEmptyState
                title="Пока нет событий"
                description="После загрузки brief, сохранения consent или preflight здесь появится короткий audit trail."
              />
            )}
          </DashboardSection>
        </>
      ) : null}
    </div>
  );
};

const emptyConsentDraft = (): ConsentDraft => ({
  mode: 'ask_each_time',
  max_credits_per_action: '',
  max_credits_per_day: '',
  max_credits_per_month: '',
  low_balance_warning_threshold: '',
});

const formatLimit = (value: number | null | undefined) => {
  if (value === null || value === undefined) return '';
  return String(value);
};

const makeConsentDraft = (offer: PaidActionOffer): ConsentDraft => {
  const policy = offer.current_consent_policy;
  return {
    mode: policy?.mode || offer.default_consent_mode || 'ask_each_time',
    max_credits_per_action: formatLimit(policy?.max_credits_per_action),
    max_credits_per_day: formatLimit(policy?.max_credits_per_day),
    max_credits_per_month: formatLimit(policy?.max_credits_per_month),
    low_balance_warning_threshold: formatLimit(policy?.low_balance_warning_threshold),
  };
};

const buildConsentDrafts = (offers: PaidActionOffer[]) => {
  const drafts: Record<string, ConsentDraft> = {};
  offers.forEach((offer) => {
    drafts[offer.action_key] = makeConsentDraft(offer);
  });
  return drafts;
};

const emptyPreflightDraft = (): PreflightDraft => ({
  estimated_credits: '',
  explicit_consent: false,
});

const makePreflightDraft = (offer: PaidActionOffer): PreflightDraft => ({
  estimated_credits: formatLimit(offer.estimated_credits),
  explicit_consent: false,
});

const buildPreflightDrafts = (offers: PaidActionOffer[]) => {
  const drafts: Record<string, PreflightDraft> = {};
  offers.forEach((offer) => {
    drafts[offer.action_key] = makePreflightDraft(offer);
  });
  return drafts;
};

type ConsentLimitInputProps = {
  label: string;
  value: string;
  onChange: (value: string) => void;
};

const ConsentLimitInput = ({ label, value, onChange }: ConsentLimitInputProps) => (
  <label className="space-y-1 text-sm font-medium text-slate-700">
    <span>{label}</span>
    <input
      type="number"
      min="0"
      inputMode="numeric"
      className="h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm text-slate-950 outline-none ring-sky-200 focus:ring-2"
      value={value}
      onChange={(event) => onChange(event.target.value)}
    />
  </label>
);
