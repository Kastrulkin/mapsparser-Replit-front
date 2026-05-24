import { useState } from 'react';
import { Link, useOutletContext } from 'react-router-dom';
import {
  Bot,
  CheckCircle2,
  Copy,
  ExternalLink,
  Loader2,
  MessageSquareText,
  RefreshCw,
  Send,
} from 'lucide-react';

import { Button } from '@/components/ui/button';
import { DashboardPageHeader } from '@/components/dashboard/DashboardPrimitives';
import { api } from '@/services/api';
import { cn } from '@/lib/utils';

type DashboardContext = {
  currentBusinessId: string | null;
  currentBusiness?: {
    id: string;
    name?: string;
  } | null;
};

type OperatorChatResult = {
  status: 'completed' | 'blocked' | 'unsupported' | string;
  intent?: string;
  chat_response?: string;
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
      action_key?: string;
      text?: string;
    };
  }>;
  review?: {
    id?: string;
    author_name?: string;
    text?: string;
  };
  draft?: {
    id?: string;
    status?: string;
    generated_text?: string;
  };
  news_draft?: {
    id?: string;
    status?: string;
    generated_text?: string;
  };
  social_post_draft?: {
    id?: string;
    status?: string;
    generated_text?: string;
  };
  optimization_job?: {
    id?: string;
    status?: string;
    selected_count?: number;
  };
  service_suggestions?: Array<{
    id?: string;
    service_id?: string;
    before_name?: string;
    optimized_name?: string;
    seo_description?: string;
  }>;
  applied_count?: number;
  applied_items?: Array<{
    id?: string;
    service_id?: string;
    before_name?: string;
    optimized_name?: string;
    seo_description?: string;
  }>;
  drafts?: Array<{
    id?: string;
    review_id?: string;
    status?: string;
    generated_text?: string;
  }>;
};

type RefreshResult = {
  status: 'completed' | 'processing' | 'failed' | 'blocked' | string;
  queue_id?: string;
  queue_status?: string;
  billing_state?: {
    label?: string;
    explanation?: string;
    charged_credits?: number;
    released_credits?: number;
    outstanding_credits?: number;
    overage_credits?: number;
    provider_actual_cost?: string | number | null;
  };
  reliability_state?: {
    title?: string;
    explanation?: string;
    next_step?: string;
  };
  new_reviews_count?: number;
  new_unanswered_reviews_count?: number;
  result_summary?: {
    title?: string;
    text?: string;
  };
  new_reviews?: Array<{
    id?: string;
    external_review_id?: string;
    rating?: number;
    author_name?: string;
    text?: string;
    has_response?: boolean;
  }>;
  chat_response?: string;
  blocked_reasons?: string[];
};

type ChatMessage = {
  id: string;
  role: 'user' | 'operator';
  text: string;
  result?: OperatorChatResult | RefreshResult;
};

const exampleCommands = [
  'Что ты умеешь?',
  'У нас есть неотвеченные отзывы сейчас в базе?',
  'Проверь новые отзывы',
  'Подготовь ответы на отзывы',
  'Добавь новый отзыв в список и сгенерируй ответ: ...',
  'Подготовь новость для карточки',
  'Подготовь пост для соцсетей',
  'Оптимизируй услуги',
];

const resultText = (result: OperatorChatResult | RefreshResult | null) => {
  if (!result) return '';
  return result.chat_response || result.result_summary?.title || 'Готово.';
};

const draftText = (result: OperatorChatResult | RefreshResult | null) => {
  if (!result) return '';
  return (
    ('reply_text' in result && result.reply_text) ||
    ('draft' in result && result.draft?.generated_text) ||
    ('news_text' in result && result.news_text) ||
    ('news_draft' in result && result.news_draft?.generated_text) ||
    ('social_post_text' in result && result.social_post_text) ||
    ('social_post_draft' in result && result.social_post_draft?.generated_text) ||
    ''
  );
};

export const OperatorPage = () => {
  const { currentBusinessId, currentBusiness } = useOutletContext<DashboardContext>();
  const [chatMessage, setChatMessage] = useState('');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [chatLoading, setChatLoading] = useState(false);
  const [refreshCheckingQueueId, setRefreshCheckingQueueId] = useState<string | null>(null);
  const [bulkGeneratingKey, setBulkGeneratingKey] = useState<string | null>(null);
  const [applyingServiceJobId, setApplyingServiceJobId] = useState<string | null>(null);
  const [manualPublishDraftId, setManualPublishDraftId] = useState<string | null>(null);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  const appendPair = (userText: string, result: OperatorChatResult) => {
    const stamp = String(Date.now());
    setMessages((current) => [
      ...current,
      { id: `${stamp}-user`, role: 'user', text: userText },
      { id: `${stamp}-operator`, role: 'operator', text: resultText(result), result },
    ]);
  };

  const appendOperatorResult = (result: OperatorChatResult | RefreshResult, suffix: string) => {
    setMessages((current) => [
      ...current,
      {
        id: `${Date.now()}-${suffix}`,
        role: 'operator',
        text: resultText(result),
        result,
      },
    ]);
  };

  const sendOperatorChatMessage = async (overrideText?: string) => {
    const text = (overrideText || chatMessage).trim();
    if (!currentBusinessId || !text) return;
    setChatLoading(true);
    try {
      const response = await api.post('/operator/chat', {
        business_id: currentBusinessId,
        message: text,
      });
      const result = response.data.operator_result || {
        status: 'blocked',
        chat_response: 'Не получил ответ Operator.',
      };
      appendPair(text, result);
      if (!overrideText) setChatMessage('');
    } catch (err) {
      appendPair(text, {
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
    setRefreshCheckingQueueId(queueId);
    try {
      const response = await api.get(`/operator/reviews/refresh-results/${queueId}`, {
        params: { business_id: currentBusinessId },
      });
      appendOperatorResult(response.data.refresh_result || { status: 'blocked', chat_response: 'Результат не найден.' }, 'refresh');
    } catch (err) {
      appendOperatorResult(
        {
          status: 'blocked',
          queue_id: queueId,
          chat_response: err instanceof Error ? err.message : 'Не удалось проверить результат обновления',
          blocked_reasons: ['operator_refresh_result_failed'],
        },
        'refresh-error',
      );
    } finally {
      setRefreshCheckingQueueId(null);
    }
  };

  const generateReviewReplies = async () => {
    if (!currentBusinessId) return;
    setBulkGeneratingKey('review_replies_generate');
    try {
      const response = await api.post('/operator/review-replies/generate', {
        business_id: currentBusinessId,
        limit: 5,
      });
      appendOperatorResult(response.data.operator_result || { status: 'blocked', chat_response: 'Не удалось подготовить ответы.' }, 'replies');
    } catch (err) {
      appendOperatorResult(
        {
          status: 'blocked',
          intent: 'bulk_review_replies_generate',
          chat_response: err instanceof Error ? err.message : 'Не удалось сгенерировать ответы',
        },
        'replies-error',
      );
    } finally {
      setBulkGeneratingKey(null);
    }
  };

  const applyServiceSuggestions = async (jobId: string | undefined) => {
    if (!currentBusinessId || !jobId) return;
    setApplyingServiceJobId(jobId);
    try {
      const response = await api.post('/operator/services/optimize/apply', {
        business_id: currentBusinessId,
        job_id: jobId,
        limit: 5,
        confirm_apply: true,
      });
      appendOperatorResult(response.data.operator_result || { status: 'blocked', chat_response: 'Не удалось применить предложения.' }, 'services');
    } catch (err) {
      appendOperatorResult(
        {
          status: 'blocked',
          intent: 'services_optimize_apply',
          chat_response: err instanceof Error ? err.message : 'Не удалось применить предложения по услугам',
        },
        'services-error',
      );
    } finally {
      setApplyingServiceJobId(null);
    }
  };

  const markManualPublished = async (draftId: string | undefined) => {
    if (!currentBusinessId || !draftId) return;
    setManualPublishDraftId(draftId);
    try {
      const response = await api.post(`/operator/review-reply-drafts/${draftId}/mark-manual-published`, {
        business_id: currentBusinessId,
      });
      appendOperatorResult(
        {
          status: response.data.success ? 'completed' : 'blocked',
          chat_response: response.data.success
            ? 'Отметил как опубликовано вручную. LocalOS ничего не публиковал во внешние карты.'
            : response.data.error || 'Не удалось отметить публикацию.',
        },
        'manual-publish',
      );
    } catch (err) {
      appendOperatorResult(
        {
          status: 'blocked',
          chat_response: err instanceof Error ? err.message : 'Не удалось отметить публикацию',
        },
        'manual-publish-error',
      );
    } finally {
      setManualPublishDraftId(null);
    }
  };

  const copyText = async (key: string, text: string) => {
    if (!text.trim()) return;
    await navigator.clipboard.writeText(text);
    setCopiedKey(key);
    window.setTimeout(() => setCopiedKey(null), 2000);
  };

  return (
    <div className="space-y-5">
      <DashboardPageHeader
        eyebrow="LocalOS Operator"
        title="Оператор"
        description="Управление LocalOS через чат: напишите, что нужно сделать с отзывами, картами, услугами, новостями или постами."
        icon={Bot}
      />

      <div className="rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="border-b border-slate-200 px-4 py-3">
          <div className="text-sm font-semibold text-slate-950">
            {currentBusiness?.name || 'Выбранный бизнес'}
          </div>
          <div className="mt-1 text-sm leading-6 text-slate-600">
            Команды выполняются внутри LocalOS. Публикация во внешние карты остаётся ручной.
          </div>
        </div>

        <div className="min-h-[420px] space-y-4 bg-slate-50/70 px-4 py-4">
          {messages.length === 0 ? (
            <div className="mx-auto flex min-h-[320px] max-w-2xl flex-col items-center justify-center text-center">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-950 text-white">
                <Bot className="h-6 w-6" />
              </div>
              <h2 className="mt-4 text-lg font-semibold text-slate-950">Напишите команду</h2>
              <p className="mt-2 text-sm leading-6 text-slate-600">
                Например: “есть ли отзывы без ответа”, “проверь новые отзывы”, “подготовь ответы” или “оптимизируй услуги”.
              </p>
              <div className="mt-4 flex flex-wrap justify-center gap-2">
                {exampleCommands.map((command) => (
                  <button
                    key={command}
                    type="button"
                    className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 shadow-sm hover:border-slate-300 hover:bg-slate-50"
                    onClick={() => setChatMessage(command)}
                  >
                    {command}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((message) => (
              <div key={message.id} className={cn('flex', message.role === 'user' ? 'justify-end' : 'justify-start')}>
                <div
                  className={cn(
                    'max-w-3xl rounded-2xl px-4 py-3 text-sm leading-6 shadow-sm',
                    message.role === 'user'
                      ? 'bg-slate-950 text-white'
                      : 'border border-slate-200 bg-white text-slate-800',
                  )}
                >
                  <div className="whitespace-pre-wrap">{message.text}</div>
                  {message.role === 'operator' && message.result ? (
                    <OperatorResultActions
                      result={message.result}
                      copiedKey={copiedKey}
                      loading={{
                        refreshCheckingQueueId,
                        bulkGeneratingKey,
                        applyingServiceJobId,
                        manualPublishDraftId,
                      }}
                      onCopy={copyText}
                      onCheckRefresh={checkRefreshResult}
                      onGenerateReplies={generateReviewReplies}
                      onApplyServices={applyServiceSuggestions}
                      onMarkManualPublished={markManualPublished}
                    />
                  ) : null}
                </div>
              </div>
            ))
          )}
        </div>

        <div className="border-t border-slate-200 bg-white px-4 py-4">
          <div className="flex flex-col gap-3 lg:flex-row">
            <textarea
              className="min-h-[96px] flex-1 resize-y rounded-xl border border-slate-200 bg-white px-3 py-3 text-sm leading-6 text-slate-950 outline-none ring-sky-200 placeholder:text-slate-400 focus:ring-2"
              value={chatMessage}
              onChange={(event) => setChatMessage(event.target.value)}
              placeholder="Напишите команду: проверь новые отзывы, подготовь ответы, добавь отзыв..."
              onKeyDown={(event) => {
                if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
                  void sendOperatorChatMessage();
                }
              }}
            />
            <Button
              type="button"
              className="h-12 lg:self-end"
              onClick={() => void sendOperatorChatMessage()}
              disabled={chatLoading || !currentBusinessId || !chatMessage.trim()}
            >
              {chatLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Send className="mr-2 h-4 w-4" />}
              Отправить
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};

type OperatorResultActionsProps = {
  result: OperatorChatResult | RefreshResult;
  copiedKey: string | null;
  loading: {
    refreshCheckingQueueId: string | null;
    bulkGeneratingKey: string | null;
    applyingServiceJobId: string | null;
    manualPublishDraftId: string | null;
  };
  onCopy: (key: string, text: string) => Promise<void>;
  onCheckRefresh: (queueId: string | undefined) => Promise<void>;
  onGenerateReplies: () => Promise<void>;
  onApplyServices: (jobId: string | undefined) => Promise<void>;
  onMarkManualPublished: (draftId: string | undefined) => Promise<void>;
};

const OperatorResultActions = ({
  result,
  copiedKey,
  loading,
  onCopy,
  onCheckRefresh,
  onGenerateReplies,
  onApplyServices,
  onMarkManualPublished,
}: OperatorResultActionsProps) => {
  const textToCopy = draftText(result);
  const hasNewUnansweredReviews =
    'new_unanswered_reviews_count' in result && Number(result.new_unanswered_reviews_count || 0) > 0;
  const draftId = 'draft' in result ? result.draft?.id : undefined;
  const optimizationJobId = 'optimization_job' in result ? result.optimization_job?.id : undefined;
  const serviceSuggestions = 'service_suggestions' in result ? result.service_suggestions || [] : [];
  const appliedItems = 'applied_items' in result ? result.applied_items || [] : [];
  const drafts = 'drafts' in result ? result.drafts || [] : [];
  const billingUrl = 'billing_url' in result ? result.billing_url : undefined;
  const queueId = result.queue_id;
  const status = result.status || '';

  return (
    <div className="mt-3 space-y-3">
      <div className="flex flex-wrap items-center gap-2 text-xs font-medium text-slate-500">
        <span
          className={cn(
            'rounded-full px-2 py-1 ring-1',
            status === 'completed'
              ? 'bg-emerald-50 text-emerald-800 ring-emerald-200'
              : status === 'processing'
                ? 'bg-sky-50 text-sky-800 ring-sky-200'
                : 'bg-amber-50 text-amber-800 ring-amber-200',
          )}
        >
          {status || 'operator'}
        </span>
        {'credit_charged' in result && result.credit_charged ? <span>Списано {result.charged_credits || 0} кредитов</span> : null}
        {'manual_publication_only' in result && result.manual_publication_only ? <span>Публикация вручную</span> : null}
        {'billing_state' in result && result.billing_state?.label ? <span>{result.billing_state.label}</span> : null}
      </div>

      {textToCopy ? (
        <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
          <div className="whitespace-pre-wrap text-slate-700">{textToCopy}</div>
          <Button type="button" size="sm" className="mt-2" onClick={() => void onCopy(`copy-${textToCopy.length}`, textToCopy)}>
            <Copy className="mr-2 h-4 w-4" />
            {copiedKey === `copy-${textToCopy.length}` ? 'Скопировано' : 'Скопировать'}
          </Button>
        </div>
      ) : null}

      {'result_summary' in result && result.result_summary ? (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-emerald-950">
          <div className="font-semibold">{result.result_summary.title}</div>
          <div>{result.result_summary.text}</div>
        </div>
      ) : null}

      {'reliability_state' in result && result.reliability_state?.title ? (
        <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-slate-700">
          <div className="font-semibold text-slate-950">{result.reliability_state.title}</div>
          {result.reliability_state.explanation ? <div>{result.reliability_state.explanation}</div> : null}
          {result.reliability_state.next_step ? <div className="mt-1 font-medium">{result.reliability_state.next_step}</div> : null}
        </div>
      ) : null}

      {'new_reviews' in result && result.new_reviews?.length ? (
        <div className="space-y-2">
          {result.new_reviews.map((review) => (
            <div key={review.id || review.external_review_id || review.text} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-semibold text-slate-950">{review.author_name || 'Новый отзыв'}</span>
                {review.rating ? <span className="text-xs font-semibold text-slate-500">{review.rating}/5</span> : null}
                {!review.has_response ? (
                  <span className="rounded-full bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-800 ring-1 ring-amber-200">
                    без ответа
                  </span>
                ) : null}
              </div>
              {review.text ? <div className="mt-1 text-slate-700">{review.text}</div> : null}
            </div>
          ))}
        </div>
      ) : null}

      {serviceSuggestions.length > 0 ? (
        <div className="space-y-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
          <div className="font-semibold text-slate-950">Предложения по услугам</div>
          {serviceSuggestions.map((item) => (
            <div key={item.id || item.service_id} className="rounded-lg bg-white px-3 py-2">
              <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">{item.before_name}</div>
              <div className="font-semibold text-slate-950">{item.optimized_name}</div>
              {item.seo_description ? <div className="text-slate-700">{item.seo_description}</div> : null}
            </div>
          ))}
        </div>
      ) : null}

      {appliedItems.length > 0 ? (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-emerald-950">
          <div className="font-semibold">Услуги обновлены</div>
          <div>Применено: {'applied_count' in result ? result.applied_count || appliedItems.length : appliedItems.length}</div>
        </div>
      ) : null}

      {drafts.length > 0 ? (
        <div className="space-y-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
          <div className="font-semibold text-slate-950">Черновики ответов</div>
          {drafts.map((draft) => (
            <div key={draft.id || draft.review_id} className="rounded-lg bg-white px-3 py-2">
              <div className="whitespace-pre-wrap text-slate-700">{draft.generated_text}</div>
              <div className="mt-2 flex flex-wrap gap-2">
                {draft.generated_text ? (
                  <Button type="button" size="sm" onClick={() => void onCopy(`draft-${draft.id}`, draft.generated_text || '')}>
                    <Copy className="mr-2 h-4 w-4" />
                    {copiedKey === `draft-${draft.id}` ? 'Скопировано' : 'Скопировать'}
                  </Button>
                ) : null}
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() => void onMarkManualPublished(draft.id)}
                  disabled={!draft.id || loading.manualPublishDraftId === draft.id}
                >
                  {loading.manualPublishDraftId === draft.id ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <CheckCircle2 className="mr-2 h-4 w-4" />}
                  Отметить вручную
                </Button>
              </div>
            </div>
          ))}
        </div>
      ) : null}

      <div className="flex flex-wrap gap-2">
        {queueId ? (
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => void onCheckRefresh(queueId)}
            disabled={loading.refreshCheckingQueueId === queueId}
          >
            {loading.refreshCheckingQueueId === queueId ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
            Проверить результат
          </Button>
        ) : null}

        {hasNewUnansweredReviews ? (
          <Button
            type="button"
            size="sm"
            onClick={() => void onGenerateReplies()}
            disabled={loading.bulkGeneratingKey === 'review_replies_generate'}
          >
            {loading.bulkGeneratingKey === 'review_replies_generate' ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <MessageSquareText className="mr-2 h-4 w-4" />}
            Подготовить ответы
          </Button>
        ) : null}

        {optimizationJobId ? (
          <Button
            type="button"
            size="sm"
            onClick={() => void onApplyServices(optimizationJobId)}
            disabled={loading.applyingServiceJobId === optimizationJobId}
          >
            {loading.applyingServiceJobId === optimizationJobId ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <CheckCircle2 className="mr-2 h-4 w-4" />}
            Применить предложения
          </Button>
        ) : null}

        {draftId ? (
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => void onMarkManualPublished(draftId)}
            disabled={loading.manualPublishDraftId === draftId}
          >
            {loading.manualPublishDraftId === draftId ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <CheckCircle2 className="mr-2 h-4 w-4" />}
            Отметить вручную
          </Button>
        ) : null}

        {billingUrl ? (
          <Button type="button" size="sm" variant="outline" asChild>
            <Link to={billingUrl}>
              Пополнить счёт
              <ExternalLink className="ml-2 h-3.5 w-3.5" />
            </Link>
          </Button>
        ) : null}
      </div>
    </div>
  );
};
