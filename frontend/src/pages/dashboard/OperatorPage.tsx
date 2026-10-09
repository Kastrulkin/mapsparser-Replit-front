import { useChatAutoScroll } from '@/components/operator/useChatAutoScroll';
import { OutreachChatSummary } from '@/components/operator/OutreachChatSummary';
import { OperatorActivity, OperatorReply } from '@/components/operator/OperatorActivity';
import { OutreachGroupCard, type GroupPresentation } from '@/components/prospecting/OutreachGroupCard';
import { OperatorRequestHistory } from '@/components/operator/OperatorRequestHistory';
import { OperatorSpeech, OperatorVoiceInput, VoiceSubmission } from '@/components/operator/OperatorVoice';
import { voiceHeaders, waitForOperatorResult } from '@/components/operator/OperatorVoice.logic';
import { OperatorWorkdayInput } from '@/components/operator/OperatorWorkdayInput';
import {
	Bot,
	CheckCircle2,
	ChevronDown,
	Copy,
	ExternalLink,
	Loader2,
	MessageSquareText,
  MoreHorizontal,
  ListTodo,
  ArrowDown,
	RefreshCw,
	Send,
} from 'lucide-react';
import { useEffect, useLayoutEffect, useId, useRef, useState } from 'react';
import { Link, useOutletContext, useSearchParams } from 'react-router-dom';

import { BetaFeedbackBanner } from '@/components/dashboard/BetaFeedbackBanner';
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from '@/components/ui/sheet';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { Button } from '@/components/ui/button';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { useLanguage } from '@/i18n/LanguageContext.logic';
import { cn } from '@/lib/utils';
import { api } from '@/services/api';
import {
	localizeDemoBusinessName,
	operatorPageCopyForLanguage,
} from './operatorPageCopy';

type DashboardContext = {
  currentBusinessId: string | null;
  currentBusiness?: {
    id: string;
    name?: string;
  } | null;
};

type OperatorChatResult = {
  message_id?: string;
  input_type?: string;
  status: 'completed' | 'blocked' | 'unsupported' | string;
  delivery_status?: string;
  search_started?: boolean;
  task?: {
    id: string;
    presentation?: GroupPresentation;
    revision?: string;
    business_id?: string;
    status: string;
    display_name?: string;
    stage?: string;
    created_at?: string;
    updated_at?: string;
    config?: { target_count?: number; max_candidates?: number; max_search_calls?: number };
    state?: { search_calls?: number };
    report?: { found?: number; imported?: number; awaiting_check?: number; checking?: number; verification_failed?: number; excluded?: number; duplicates?: number; eligible?: number; shortfall?: number; credit_limit?: number; credits_charged?: number };
  };
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
  conversation_id?: string;
  capability?: string;
  capability_status?: string;
  capabilities?: string[];
  capability_catalog?: Array<{
    name?: string;
    title?: string;
    status?: string;
    unavailable_reason?: string;
    examples?: string[];
  }>;
  summary?: string;
  result_ref?: {
    entity_type?: string;
    entity_id?: string | null;
    label?: string;
    href?: string;
  };
  clarification?: {
    question?: string;
  };
  approval?: {
    status?: string;
    action_id?: string;
    summary?: string;
    capability?: string;
  };
  credit_quote?: { total_max?: number };
  ai_router?: {
    status?: string;
    intent?: string;
    charged_credits?: number;
    credit_charged?: boolean;
  };
  ui_actions?: Array<{
    action: string;
    label: string;
    href?: string;
    payload?: {
      action_key?: string;
      action_id?: string;
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
  services?: Array<{
    id?: string;
    category?: string;
    name?: string;
    price?: string;
    description?: string;
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
  message_id?: string;
  input_type?: string;
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
    status?: string;
    title?: string;
    explanation?: string;
    next_step?: string;
  };
  recovery_result?: {
    status?: string;
    retry_allowed?: boolean;
    release_allowed?: boolean;
    reservation_id?: string | null;
    outstanding_credits?: number;
    blocked_reasons?: string[];
    side_effects?: {
      reservation_released?: boolean;
    };
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
  ai_router?: {
    status?: string;
    intent?: string;
    charged_credits?: number;
    credit_charged?: boolean;
  };
};

type ChatMessage = {
  id: string;
  role: 'user' | 'operator';
  text: string;
  fresh?: boolean;
  result?: OperatorChatResult | RefreshResult;
};

const resultText = (result: OperatorChatResult | RefreshResult | null) => {
  if (!result) return '';
  return (
    ('chat_response' in result && result.chat_response) ||
    ('result_summary' in result && result.result_summary?.title) ||
    'Готово.'
  );
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

const mapStoredMessages = (items: Array<{
  id?: string;
  role?: string;
  content?: string;
  result_json?: OperatorChatResult;
}>): ChatMessage[] => items.map((item) => ({
  id: item.id || `${Date.now()}-${Math.random()}`,
  role: item.role === 'user' ? 'user' : 'operator',
  text: item.content || '',
  result: item.role === 'operator' ? item.result_json : undefined,
}));

export const OperatorPage = () => {
  const { currentBusinessId, currentBusiness } = useOutletContext<DashboardContext>();
  const { language } = useLanguage();
  const copy = operatorPageCopyForLanguage(language);
  const businessName = localizeDemoBusinessName(currentBusiness?.name || '', language) || copy.selectedBusiness;
  const activeBusiness = useRef(currentBusinessId);
  activeBusiness.current = currentBusinessId;
  const [chatMessage, setChatMessage] = useState('');
  const chatInputRef = useRef<HTMLTextAreaElement>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [chatLoading, setChatLoading] = useState(false);
  const [pendingChatMessage, setPendingChatMessage] = useState<string | null>(null);
  const [pendingChatPhase, setPendingChatPhase] = useState('Отправляем команду…');
  const [commandWaiting, setCommandWaiting] = useState(false);
  const [commandAccepted, setCommandAccepted] = useState(false);
  const chatScroll = useChatAutoScroll(currentBusinessId, messages.length + (pendingChatMessage ? 1 : 0));
  const workspaceRef = useRef<HTMLDivElement>(null);
  const [workspaceHeight, setWorkspaceHeight] = useState<number>();
  const menuTriggerRef = useRef<HTMLButtonElement>(null);
  const [tasksOpen, setTasksOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const [feedbackOpen, setFeedbackOpen] = useState(false);
  useLayoutEffect(() => {
    const resize = () => {
      const node = workspaceRef.current;
      if (!node) return;
      const viewport = window.visualViewport;
      setWorkspaceHeight(Math.max(160, (viewport?.height || window.innerHeight) + (viewport?.offsetTop || 0) - node.getBoundingClientRect().top - 12 - (window.matchMedia("(max-width: 767px)").matches ? 40 : 0)));
    };
    resize();
    const observer = new ResizeObserver(resize);
    if (workspaceRef.current?.parentElement) observer.observe(workspaceRef.current.parentElement);
    observer.observe(document.body);
    const shellHeader = document.querySelector("header");
    if (shellHeader) observer.observe(shellHeader);
    window.addEventListener("resize", resize);
    window.visualViewport?.addEventListener("resize", resize);
    window.visualViewport?.addEventListener("scroll", resize);
    return () => { observer.disconnect(); window.removeEventListener("resize", resize); window.visualViewport?.removeEventListener("resize", resize); window.visualViewport?.removeEventListener("scroll", resize); };
  }, []);
  useLayoutEffect(() => {
    const input = chatInputRef.current;
    if (input) { input.style.height = "auto"; input.style.height = `${Math.min(144, input.scrollHeight)}px`; }
  }, [chatMessage]);
  const chatSendInFlightRef = useRef(false);
  const pendingRequest = useRef({ businessId: "", text: "", groupId: "", id: "" });
  const [refreshCheckingQueueId, setRefreshCheckingQueueId] = useState<string | null>(null);
  const [bulkGeneratingKey, setBulkGeneratingKey] = useState<string | null>(null);
  const [applyingServiceJobId, setApplyingServiceJobId] = useState<string | null>(null);
  const [manualPublishDraftId, setManualPublishDraftId] = useState<string | null>(null);
  const [recoveringQueueId, setRecoveringQueueId] = useState<string | null>(null);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [historyLoading, setHistoryLoading] = useState(false);
  const historyVersion = useRef(0);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [historyRetry, setHistoryRetry] = useState(0);
  const [confirmingActionId, setConfirmingActionId] = useState<string | null>(null);
  const [rejectingActionId, setRejectingActionId] = useState<string | null>(null);
  const [searchParams, setSearchParams] = useSearchParams();
  const [searchTasks, setSearchTasks] = useState<NonNullable<OperatorChatResult['task']>[]>([]);
  const requestedSearchId = searchParams.get('search_task_id') || '';
  const [selectedSearchId, setSelectedSearchId] = useState(requestedSearchId);
  useEffect(() => { setSelectedSearchId(requestedSearchId); }, [requestedSearchId]);
  const suggestedCommand = searchParams.get('command');
  useEffect(() => { if (suggestedCommand) setChatMessage(suggestedCommand); }, [suggestedCommand]);
  useEffect(() => { setTasksOpen(false); setHistoryOpen(false); setHelpOpen(false); setFeedbackOpen(false); }, [currentBusinessId]);
  const [savedSearchTask, setSavedSearchTask] = useState<OperatorChatResult['task']>();
  const activeSearchTask = selectedSearchId ? searchTasks.find(task => task.id === selectedSearchId && task.business_id === currentBusinessId) || (savedSearchTask?.id === selectedSearchId && savedSearchTask?.business_id === currentBusinessId ? savedSearchTask : undefined) : undefined;
  useEffect(() => {
    setSearchTasks([]); setSavedSearchTask(undefined);
    if (!currentBusinessId) return;
    let live = true;
    const refresh = async () => {
      try {
        const response = await api.get('/partnership/continuations', { params: { business_id: currentBusinessId } });
        if (live) setSearchTasks(response.data?.items || []);
      } catch { if (live) setSavedSearchTask(undefined); }
    };
    void refresh();
    return () => { live = false; };
  }, [currentBusinessId]);
  useEffect(() => {
    if (!currentBusinessId) {
      setConversationId(null);
      setMessages([]);
      return;
    }
    setMessages([]); setConversationId(null); setPendingChatMessage(null);
    chatSendInFlightRef.current = false; setChatLoading(false); setConfirmingActionId(null); setRejectingActionId(null);
    const storageKey = `localos_operator_conversation_${currentBusinessId}`;
    const storedConversationId = window.localStorage.getItem(storageKey);
    let cancelled = false;
    const version = ++historyVersion.current;
    setHistoryLoading(true);
    setHistoryError(null);
    const request = storedConversationId
      ? api.get(`/operator/conversations/${encodeURIComponent(storedConversationId)}/messages`, {
          params: { business_id: currentBusinessId, limit: 100 },
        })
      : api.get('/operator/conversations/current', {
          params: { business_id: currentBusinessId, channel: 'web', limit: 100 },
        });
    request.then((response) => {
      if (cancelled || version !== historyVersion.current) return;
      const storedMessages = Array.isArray(response.data.messages) ? response.data.messages : [];
      const loadedConversationId = storedConversationId || response.data.conversation?.id || null;
      setConversationId(loadedConversationId);
      setMessages(mapStoredMessages(storedMessages));
      if (loadedConversationId) window.localStorage.setItem(storageKey, loadedConversationId);
    }).catch((error: unknown) => {
      if (cancelled) return;
      const status = (
        typeof error === 'object'
        && error !== null
        && 'response' in error
        && typeof error.response === 'object'
        && error.response !== null
        && 'status' in error.response
        && typeof error.response.status === 'number'
      ) ? error.response.status : null;
      if (status === 404 && storedConversationId) {
        window.localStorage.removeItem(storageKey);
        setConversationId(null);
        setMessages([]);
        setHistoryError('Предыдущая переписка больше недоступна. Можно начать новую задачу.');
        return;
      }
      if (status === 403) {
        window.localStorage.removeItem(storageKey);
        setConversationId(null);
        setMessages([]);
        setHistoryError('Нет доступа к этой истории. Проверьте выбранный бизнес или обратитесь к владельцу.');
        return;
      }
      setHistoryError('Не удалось обновить историю. Последние сообщения сохранены на экране.');
    }).finally(() => {
      if (!cancelled) setHistoryLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, [currentBusinessId, historyRetry]);


  const appendPair = (userText: string, result: OperatorChatResult) => {
    const stamp = String(Date.now());
    setMessages((current) => [
      ...current,
      { id: `${stamp}-user`, role: 'user', text: userText },
      { id: `${stamp}-operator`, role: 'operator', text: resultText(result), fresh: true, result },
    ]);
  };

  const appendOperatorResult = (result: OperatorChatResult | RefreshResult, suffix: string) => {
    if ('task' in result && result.task?.id && (!result.task.business_id || result.task.business_id === currentBusinessId)) {
      setSavedSearchTask({ ...result.task, business_id: currentBusinessId });
      setSelectedSearchId(result.task.id);
      setSearchParams(current => {
        const next = new URLSearchParams(current);
        next.set('search_task_id', result.task.id);
        next.set('business_id', currentBusinessId);
        return next;
      }, { replace: true });
    }
    setMessages((current) => [
      ...current,
      {
        id: `${Date.now()}-${suffix}`,
        role: 'operator',
        text: resultText(result),
        fresh: true,
        result,
      },
    ]);
  };

  const sendOperatorChatMessage = async (overrideText?: string, source?: VoiceSubmission) => {
    const text = (overrideText || chatMessage).trim();
    if (!currentBusinessId || !text || chatSendInFlightRef.current) return;
    if (pendingRequest.current.businessId !== currentBusinessId || pendingRequest.current.text !== text || pendingRequest.current.groupId !== selectedSearchId) pendingRequest.current = { businessId: currentBusinessId, text, groupId: selectedSearchId, id: crypto.randomUUID() };
    historyVersion.current++;
    setHistoryLoading(false);
    chatSendInFlightRef.current = true;
    setPendingChatMessage(text);
    setPendingChatPhase('Отправляем команду…');
    setCommandAccepted(false);
    setCommandWaiting(false);
    setChatLoading(true);
    try {
      const response = await api.post('/operator/chat', {
        business_id: currentBusinessId,
        message: text,
        conversation_id: conversationId,
        channel: 'web',
        search_task_id: selectedSearchId || null,
        request_id: pendingRequest.current.id,
        ...source,
      });
      if (activeBusiness.current !== currentBusinessId) return;
      const initialResult = response.data.operator_result || {
        status: 'blocked',
        chat_response: 'Не получил ответ Operator.',
      };
      setCommandAccepted(true);
      setPendingChatPhase('Готовим ответ…');
      const result=await waitForOperatorResult(initialResult,currentBusinessId,voiceHeaders,()=>activeBusiness.current===currentBusinessId, job => {
        setCommandWaiting(job.status === 'queued' || job.status === 'waiting_for_review');
        if (job.status === 'queued') setPendingChatPhase('Команда в очереди · ждёт запуска');
        else if (job.status === 'running') setPendingChatPhase(job.stage || 'Выполняем команду…');
        else if (job.status === 'waiting_for_review') setPendingChatPhase('Нужно ваше подтверждение');
      });
      if(activeBusiness.current!==currentBusinessId)return;
      pendingRequest.current = { businessId: "", text: "", groupId: "", id: "" };
      appendPair(text, result);
      if (result.task?.id && (!result.task.business_id || result.task.business_id === currentBusinessId)) {
        setSavedSearchTask({...result.task, business_id: currentBusinessId});
        setSelectedSearchId(result.task.id);
        setSearchParams(current => { const next = new URLSearchParams(current); next.set('search_task_id', result.task.id); next.set('business_id', currentBusinessId); return next; }, { replace: true });
      }
      const nextConversationId = response.data.conversation_id || result.conversation_id;
      if (nextConversationId) {
        setConversationId(nextConversationId);
        window.localStorage.setItem(`localos_operator_conversation_${currentBusinessId}`, nextConversationId);
      }
      if (!overrideText) setChatMessage((current) => current.trim() === text ? '' : current);
    } catch (err) {
      if (activeBusiness.current !== currentBusinessId) return;
      if (source) throw err;
      appendPair(text, {
        status: 'blocked',
        intent: 'error',
        chat_response: err instanceof Error ? err.message : 'Не удалось выполнить команду Operator',
        blocked_reasons: ['operator_chat_request_failed'],
      });
    } finally {
      if (activeBusiness.current === currentBusinessId) {
        chatSendInFlightRef.current = false;
        setPendingChatMessage(null);
        setChatLoading(false);
      }
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

  const recoverRefreshJob = async (queueId: string | undefined, confirmRelease = false) => {
    if (!currentBusinessId || !queueId) return;
    setRecoveringQueueId(queueId);
    try {
      const response = confirmRelease
        ? await api.post(`/operator/reviews/refresh-jobs/${queueId}/recovery`, {
            business_id: currentBusinessId,
            confirm_release: true,
          })
        : await api.get(`/operator/reviews/refresh-jobs/${queueId}/recovery`, {
            params: { business_id: currentBusinessId },
          });
      const recovery = response.data.recovery_result || {};
      appendOperatorResult(
        {
          status: recovery.status || 'blocked',
          queue_id: queueId,
          chat_response:
            recovery.status === 'released'
              ? 'Зарезервированные кредиты по failed refresh возвращены. Внешних публикаций не было.'
              : recovery.release_allowed
                ? `Recovery доступен: можно вернуть ${recovery.outstanding_credits || 0} зарезервированных кредитов.`
                : 'Для этой задачи нет доступного recovery-действия.',
          recovery_result: recovery,
          blocked_reasons: recovery.blocked_reasons || [],
          manual_publication_only: true,
        },
        confirmRelease ? 'recovery-release' : 'recovery-plan',
      );
    } catch (err) {
      appendOperatorResult(
        {
          status: 'blocked',
          queue_id: queueId,
          chat_response: err instanceof Error ? err.message : 'Не удалось выполнить recovery refresh job',
          blocked_reasons: ['operator_refresh_recovery_failed'],
        },
        'recovery-error',
      );
    } finally {
      setRecoveringQueueId(null);
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

  const confirmOperatorAction = async (actionId: string | undefined) => {
    if (!currentBusinessId || !actionId) return;
    setConfirmingActionId(actionId);
    try {
      const response = await api.post(`/operator/actions/${encodeURIComponent(actionId)}/confirm`, {
        business_id: currentBusinessId,
      });
      if (activeBusiness.current !== currentBusinessId) return;
      appendOperatorResult(
        response.data.operator_result || { status: 'blocked', chat_response: 'Не удалось выполнить подтверждённое действие.' },
        'approval',
      );
    } catch (err) {
      if (activeBusiness.current !== currentBusinessId) return;
      appendOperatorResult(
        {
          status: 'blocked',
          chat_response: err instanceof Error ? err.message : 'Не удалось подтвердить действие',
        },
        'approval-error',
      );
    } finally {
      if (activeBusiness.current === currentBusinessId) setConfirmingActionId(null);
    }
  };

  const rejectOperatorAction = async (actionId: string | undefined) => {
    if (!currentBusinessId || !actionId) return;
    setRejectingActionId(actionId);
    try {
      const response = await api.post(`/operator/actions/${encodeURIComponent(actionId)}/reject`, {
        business_id: currentBusinessId,
      });
      if (activeBusiness.current !== currentBusinessId) return;
      appendOperatorResult(
        response.data.operator_result || { status: 'blocked', chat_response: 'Не удалось отклонить действие.' },
        'rejection',
      );
    } catch (err) {
      if (activeBusiness.current !== currentBusinessId) return;
      appendOperatorResult(
        {
          status: 'blocked',
          chat_response: err instanceof Error ? err.message : 'Не удалось отклонить действие',
        },
        'rejection-error',
      );
    } finally {
      if (activeBusiness.current === currentBusinessId) setRejectingActionId(null);
    }
  };

  const copyText = async (key: string, text: string) => {
    if (!text.trim()) return;
    await navigator.clipboard.writeText(text);
    setCopiedKey(key);
    window.setTimeout(() => setCopiedKey(null), 2000);
  };

  return (
    <div ref={workspaceRef} style={{ height: workspaceHeight }} className="flex min-h-0 min-w-0 flex-col gap-2" data-tour-target="operator-overview">
      <header className="flex shrink-0 items-center justify-between gap-2">
        <div className="flex items-center gap-2"><h1 className="text-xl font-semibold">{copy.title}</h1><span className="rounded-full bg-muted px-2 py-1 text-xs text-muted-foreground">Beta</span></div>
        <div className="flex items-center gap-1">
          <Sheet open={tasksOpen} onOpenChange={setTasksOpen}>
            <SheetTrigger asChild><Button variant="ghost"><ListTodo aria-hidden="true" />Задачи</Button></SheetTrigger>
            <SheetContent className="flex w-full max-w-full flex-col sm:max-w-md">
              <SheetHeader><SheetTitle>Задачи</SheetTitle><SheetDescription>Выберите поиск, чтобы продолжить работу в чате.</SheetDescription></SheetHeader>
              <div className="min-h-0 space-y-2 overflow-y-auto py-4">
                <Button className="w-full justify-start" variant="ghost" onClick={() => { setSelectedSearchId(''); const next = new URLSearchParams(searchParams); next.delete('search_task_id'); setSearchParams(next, { replace: true }); setTasksOpen(false); }}>Без выбранного поиска</Button>
                {!searchTasks.length && <p className="text-sm text-muted-foreground">Поисков пока нет. Опишите задачу в чате.</p>}
                {searchTasks.map(task => <button key={task.id} type="button" aria-pressed={selectedSearchId === task.id} className="w-full rounded-lg border border-input p-3 text-left hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" onClick={() => {
                  setSelectedSearchId(task.id); const next = new URLSearchParams(searchParams); next.set('search_task_id', task.id); if (currentBusinessId) next.set('business_id', currentBusinessId); setSearchParams(next, { replace: true }); setTasksOpen(false);
                }}><span className="block break-words font-medium">{task.display_name || 'Поиск компаний'}</span><span className="mt-1 block text-xs text-muted-foreground">{task.presentation?.label || 'Открыть состояние'}{(task.updated_at || task.created_at) && ` · ${new Date(task.updated_at || task.created_at || '').toLocaleDateString()}`}</span></button>)}
              </div>
            </SheetContent>
          </Sheet>
          <DropdownMenu><DropdownMenuTrigger asChild><Button ref={menuTriggerRef} size="icon" variant="ghost" aria-label="Меню Оператора"><MoreHorizontal aria-hidden="true" /></Button></DropdownMenuTrigger><DropdownMenuContent align="end">
            <DropdownMenuItem onSelect={() => setFeedbackOpen(true)}>Сообщить о проблеме</DropdownMenuItem>
            <DropdownMenuItem onSelect={() => setHistoryOpen(true)}>История обращений</DropdownMenuItem>
            <DropdownMenuItem onSelect={() => setHelpOpen(true)}>Как пользоваться</DropdownMenuItem>
          </DropdownMenuContent></DropdownMenu>
        </div>
      </header>
      <BetaFeedbackBanner dialogOnly onCloseAutoFocus={event => { event.preventDefault(); menuTriggerRef.current?.focus(); }} open={feedbackOpen} onOpenChange={setFeedbackOpen} area="operator" title={copy.title} description={copy.betaDescription} businessId={currentBusinessId} businessName={businessName} />
      <Dialog open={historyOpen} onOpenChange={setHistoryOpen}><DialogContent onCloseAutoFocus={event => { event.preventDefault(); menuTriggerRef.current?.focus(); }} className="max-h-[90dvh] max-w-3xl overflow-y-auto"><DialogHeader><DialogTitle>История обращений</DialogTitle><DialogDescription>Сохранённые команды, ответы и распознавание голоса.</DialogDescription></DialogHeader>{historyOpen && currentBusinessId && <OperatorRequestHistory key={currentBusinessId} initiallyOpen businessId={currentBusinessId} language={language} />}</DialogContent></Dialog>
      <Dialog open={helpOpen} onOpenChange={setHelpOpen}><DialogContent onCloseAutoFocus={event => { event.preventDefault(); menuTriggerRef.current?.focus(); }}><DialogHeader><DialogTitle>Как пользоваться</DialogTitle><DialogDescription>Напишите задачу обычным языком или запишите голосом.</DialogDescription></DialogHeader><p className="text-sm">Оператор покажет результат или уточнит недостающее. Для продолжения поиска выберите его в «Задачах». Отправка писем и другие внешние действия требуют подтверждения.</p></DialogContent></Dialog>
      <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden rounded-xl border border-border bg-background shadow-sm">
        {currentBusinessId && activeSearchTask?.id && <div className="shrink-0 border-b border-border px-3 py-2"><OutreachTaskStatus key={`${currentBusinessId}:${activeSearchTask.id}`} businessId={currentBusinessId} initialTask={activeSearchTask} onChange={() => setTasksOpen(true)} onContinue={command => {
          setSelectedSearchId(activeSearchTask.id);
          setChatMessage(command);
          chatInputRef.current?.focus();
        }} /></div>}
        <div ref={chatScroll.ref} data-testid="operator-message-list" className="min-h-0 min-w-0 flex-1 space-y-4 overflow-y-auto overscroll-contain bg-muted/30 px-3 py-4 [overflow-wrap:anywhere]">
          {historyError ? (
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-950" role="status">
              <span>{historyError}</span>
              <Button size="sm" variant="outline" onClick={() => setHistoryRetry((current) => current + 1)} disabled={historyLoading}>
                <RefreshCw className="mr-2 h-4 w-4" />
                Повторить
              </Button>
            </div>
          ) : null}
          {historyLoading && messages.length === 0 ? (
            <div className="flex min-h-full items-center justify-center text-sm text-slate-500">
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              <span translate="no" className="notranslate">{copy.loadingHistory}</span>
            </div>
          ) : messages.length === 0 && !pendingChatMessage ? (
            <div className="mx-auto flex min-h-full max-w-2xl flex-col items-center justify-center text-center">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-950 text-white">
                <Bot className="h-6 w-6" />
              </div>
              <h2 className="mt-4 text-lg font-semibold text-slate-950">{copy.emptyTitle}</h2>
              <p className="mt-2 text-pretty text-sm leading-6 text-slate-600">
                {"Опишите, что нужно сделать. Можно начать с примера."}
              </p>
              <div className="mt-4 flex flex-wrap justify-center gap-2">
                {['Найди 3 компании для сотрудничества', 'Подготовь пост о наших услугах', 'Покажи отзывы без ответа'].map((command) => (
                  <button
                    key={command}
                    type="button"
                    className="min-h-10 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 shadow-sm transition-[background-color,border-color,transform] active:scale-[0.96] hover:border-slate-300 hover:bg-slate-50"
                    onClick={() => setChatMessage(command)}
                  >
                    {command}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((message, index) => (
              <div key={message.id} className={cn('flex', message.role === 'user' ? 'justify-end' : 'justify-start')}>
                <div
                  className={cn(
                    'min-w-0 max-w-full lg:max-w-3xl [&_button]:max-w-full [&_button]:whitespace-normal [&_a]:max-w-full [&_a]:whitespace-normal rounded-2xl px-4 py-3 text-sm leading-6 shadow-sm',
                    message.role === 'user'
                      ? 'bg-slate-950 text-white'
                      : 'border border-slate-200 bg-white text-slate-800',
                  )}
                >
                  {message.role === 'operator' ? <OperatorReply animate={message.fresh} text={message.result && 'approval' in message.result && message.result.approval?.capability === 'partnerships.continue_outreach' && !('credit_quote' in message.result && message.result.credit_quote)
                    ? 'Прежние условия поиска устарели. Откройте актуальную стоимость в кредитах LocalOS.'
                    : message.text.replace(/DeepSeek/gi, 'ИИ')} /> : <div className="whitespace-pre-wrap">{message.text}</div>}
                  {message.role === 'operator' && currentBusinessId && message.result && 'task' in message.result && message.result.task?.id && message.result.task.id !== selectedSearchId && (!message.result.task.business_id || message.result.task.business_id === currentBusinessId) && <Button size="sm" variant="ghost" onClick={() => {
                    const task = searchTaskFromResult(message.result); if (!task) return;
                    setSavedSearchTask({ ...task, business_id: currentBusinessId }); setSelectedSearchId(task.id);
                    const next = new URLSearchParams(searchParams); next.set('search_task_id', task.id); next.set('business_id', currentBusinessId); setSearchParams(next, { replace: true });
                  }}>Показать текущий результат поиска</Button>}
                  {message.role === 'operator' && currentBusinessId && <OperatorSpeech key={`${currentBusinessId}:${message.id}`} businessId={currentBusinessId} messageId={message.result?.message_id || message.id} prepare={message.result?.input_type === 'voice'} />}
                  {message.role === 'operator' && message.result ? (
                    <OperatorResultActions
                      result={message.result}
                      businessId={currentBusinessId}
                      canStartPreview={index === messages.length - 1}
                      copiedKey={copiedKey}
                      loading={{
                        refreshCheckingQueueId,
                        bulkGeneratingKey,
                        applyingServiceJobId,
                        manualPublishDraftId,
                        recoveringQueueId,
                        confirmingActionId,
                        rejectingActionId,
                      }}
                      onCopy={copyText}
                      onCheckRefresh={checkRefreshResult}
                      onGenerateReplies={generateReviewReplies}
                      onRecoverRefresh={recoverRefreshJob}
                      onApplyServices={applyServiceSuggestions}
                      onMarkManualPublished={markManualPublished}
                      onConfirmOperatorAction={confirmOperatorAction}
                      onRejectOperatorAction={rejectOperatorAction}
                      onSendCommand={sendOperatorChatMessage}
                      onEditPreview={() => setChatMessage('Измени условия последнего поиска: ')}
                    />
                  ) : null}
                </div>
              </div>
            ))
          )}
          {pendingChatMessage && <div className="flex justify-end">
            <div className="max-w-3xl rounded-2xl bg-slate-950 px-4 py-3 text-sm leading-6 text-white shadow-sm">
              <div className="whitespace-pre-wrap">{pendingChatMessage}</div>

            </div>
          </div>}
          {pendingChatMessage && <OperatorActivity phase={pendingChatPhase} accepted={commandAccepted} waiting={commandWaiting} />}
        </div>

        {chatScroll.readingHistory && <div className="flex shrink-0 justify-center border-t border-border py-1"><Button size="sm" variant="ghost" onClick={chatScroll.scrollToLatest}><ArrowDown aria-hidden="true" />{chatScroll.hasNewMessages ? 'Новые сообщения · К последним' : 'К последним сообщениям'}</Button></div>}
        <div className="shrink-0 space-y-2 border-t border-border bg-background px-3 py-2 pb-[max(0.5rem,env(safe-area-inset-bottom))]">
          <div className="flex max-h-[30dvh] flex-wrap items-start gap-2 overflow-y-auto">
            {currentBusinessId && <OperatorVoiceInput compact key={currentBusinessId} businessId={currentBusinessId} channel="web" conversationId={conversationId} disabled={chatLoading || historyLoading} onSubmit={sendOperatorChatMessage} />}
            {currentBusinessId && <OperatorWorkdayInput compact key={`inputs:${currentBusinessId}`} businessId={currentBusinessId} channel="web" conversationId={conversationId} disabled={chatLoading || historyLoading} onConversation={setConversationId} />}
          </div>
          <div className="flex min-w-0 items-end gap-2">
            <textarea
              ref={chatInputRef}
              rows={1}
              aria-label="Задача для Оператора"
              className="min-h-12 max-h-36 min-w-0 flex-1 resize-none overflow-y-auto rounded-xl border border-input bg-background px-3 py-3 text-sm leading-6 text-foreground outline-none placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring"
              value={chatMessage}
              onChange={(event) => setChatMessage(event.target.value)}
              placeholder="Напишите, что нужно сделать…"
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
                  event.preventDefault();
                  void sendOperatorChatMessage();
                }
              }}
            />
            <TooltipProvider delayDuration={180}>
              <Tooltip>
                <TooltipTrigger asChild>
                  <span className="block shrink-0">
                    <Button
                      type="button"
                      className="btn-iridescent h-12 w-12 p-0 sm:w-auto sm:px-4"
                      aria-label={copy.send}
                      onClick={() => void sendOperatorChatMessage()}
                      disabled={chatLoading || !currentBusinessId || !chatMessage.trim()}
                    >
                      {chatLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Send className="mr-2 h-4 w-4" />}
                      <span className="hidden sm:inline">{copy.send}</span>
                    </Button>
                  </span>
                </TooltipTrigger>
                <TooltipContent side="top" className="space-y-1 text-xs leading-5">
                  <div><kbd className="font-semibold">Enter</kbd> — {copy.sendHint}</div>
                  <div><kbd className="font-semibold">Shift + Enter</kbd> — {copy.newlineHint}</div>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>
        </div>
      </div>
    </div>
  );
};

type OutreachTask = NonNullable<OperatorChatResult['task']>;

function searchTaskFromResult(result?: OperatorChatResult | RefreshResult) {
  return result && 'task' in result ? result.task : undefined;
}

function OutreachTaskStatus({ businessId, initialTask, onContinue, onChange }: { businessId: string; initialTask: OutreachTask; onContinue?: (command: string) => void; onChange?: () => void }) {
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [refreshVersion, setRefreshVersion] = useState(0);
  const [task, setTask] = useState(initialTask);
  const [refreshError, setRefreshError] = useState(false);
  const [actionBusy, setActionBusy] = useState(false);
  const actionInFlight = useRef(false);
  useEffect(() => {
    let active = true;
    let working = !!initialTask.presentation?.active;
    let inFlight = false;
    const refresh = async () => {
      if (inFlight) return;
      inFlight = true;
      try {
        const response = await api.get(`/partnership/continuations/${encodeURIComponent(initialTask.id)}`, { params: { business_id: businessId } });
        if (!active) return;
        const current: OutreachTask | undefined = response.data;
        if (current) { working = !!current.presentation?.active; setTask(current); }
        setRefreshError(!current);
      } catch {
        if (active) setRefreshError(true);
      } finally { inFlight = false; }
    };
    void refresh();
    let lastRefresh = Date.now();
    const timer = window.setInterval(() => {
      if (Date.now() - lastRefresh >= (working && !document.hidden ? 3000 : 15000)) { lastRefresh = Date.now(); void refresh(); }
    }, 1000);
    const focusRefresh = () => { if (!document.hidden) { lastRefresh = Date.now(); void refresh(); } };
    document.addEventListener('visibilitychange', focusRefresh);
    window.addEventListener('focus', focusRefresh);
    return () => { active = false; window.clearInterval(timer); document.removeEventListener('visibilitychange', focusRefresh); window.removeEventListener('focus', focusRefresh); };
  }, [businessId, initialTask.id, refreshVersion]);
  return <div className="space-y-2">
    {onContinue ? <OutreachChatSummary name={task.display_name || 'Выбранный поиск'} presentation={task.presentation} onContinue={onContinue} onChange={onChange} onDetails={() => setDetailsOpen(true)} /> : <OutreachGroupCard compact name={task.display_name || 'Выбранный поиск'} presentation={task.presentation} busy={actionBusy} onAction={async action => {
      if (actionInFlight.current) return;
      actionInFlight.current = true; setActionBusy(true);
      try {
        await api.post(`/partnership/continuations/${task.id}`, { business_id: businessId, revision: task.revision, action: action.kind === 'draft_resume' ? 'resume_letters' : action.action });
        const response = await api.get(`/partnership/continuations/${task.id}`, { params: { business_id: businessId } });
        setTask(response.data); setRefreshError(false);
      } catch { setRefreshError(true); }
      finally { actionInFlight.current = false; setActionBusy(false); }
    }} />}
    <Dialog open={detailsOpen} onOpenChange={setDetailsOpen}><DialogContent className="max-h-[85dvh] overflow-y-auto"><DialogHeader><DialogTitle>Подробности поиска</DialogTitle><DialogDescription>{task.display_name || "Выбранный поиск"}</DialogDescription></DialogHeader><OutreachGroupCard name={task.display_name || "Выбранный поиск"} presentation={task.presentation} /><details><summary className="cursor-pointer py-2 text-sm">Условия поиска</summary><p className="text-sm text-muted-foreground">Цель: {task.config?.target_count ?? "не указана"} · До {task.config?.max_candidates ?? "—"} кандидатов · До {task.config?.max_search_calls ?? "—"} поисковых запросов</p></details><Button variant="outline" asChild><Link to={`/dashboard/partnerships?search_task_id=${encodeURIComponent(task.id)}&business_id=${encodeURIComponent(businessId)}`}>Компании и история поиска</Link></Button></DialogContent></Dialog>
    {refreshError && <p role="alert" className="text-sm text-destructive">Не удалось обновить состояние. Показаны последние сохранённые данные{task.presentation?.updated_at ? ` · ${new Date(task.presentation.updated_at).toLocaleTimeString()}` : ""}. <Button size="sm" variant="ghost" onClick={() => setRefreshVersion(value => value + 1)}>Повторить</Button></p>}
  </div>;
}

type OperatorResultActionsProps = {
  result: OperatorChatResult | RefreshResult;
  businessId: string;
  canStartPreview: boolean;
  copiedKey: string | null;
  loading: {
    refreshCheckingQueueId: string | null;
    bulkGeneratingKey: string | null;
    applyingServiceJobId: string | null;
    manualPublishDraftId: string | null;
    recoveringQueueId: string | null;
    confirmingActionId: string | null;
    rejectingActionId: string | null;
  };
  onCopy: (key: string, text: string) => Promise<void>;
  onCheckRefresh: (queueId: string | undefined) => Promise<void>;
  onGenerateReplies: () => Promise<void>;
  onRecoverRefresh: (queueId: string | undefined, confirmRelease?: boolean) => Promise<void>;
  onApplyServices: (jobId: string | undefined) => Promise<void>;
  onMarkManualPublished: (draftId: string | undefined) => Promise<void>;
  onConfirmOperatorAction: (actionId: string | undefined) => Promise<void>;
  onRejectOperatorAction: (actionId: string | undefined) => Promise<void>;
  onSendCommand: (text: string) => Promise<void>;
  onEditPreview: () => void;
};

const OperatorResultActions = ({
  result,
  businessId,
  canStartPreview,
  copiedKey,
  loading,
  onCopy,
  onCheckRefresh,
  onGenerateReplies,
  onRecoverRefresh,
  onApplyServices,
  onMarkManualPublished,
  onConfirmOperatorAction,
  onRejectOperatorAction,
  onSendCommand,
  onEditPreview,
}: OperatorResultActionsProps) => {
  const capabilityPanelId = useId();
  const [capabilitiesOpen, setCapabilitiesOpen] = useState(false);
  const textToCopy = draftText(result);
  const hasNewUnansweredReviews =
    'new_unanswered_reviews_count' in result && Number(result.new_unanswered_reviews_count || 0) > 0;
  const draftId = 'draft' in result ? result.draft?.id : undefined;
  const optimizationJobId = 'optimization_job' in result ? result.optimization_job?.id : undefined;
  const serviceSuggestions = 'service_suggestions' in result ? result.service_suggestions || [] : [];
  const services = 'services' in result ? result.services || [] : [];
  const appliedItems = 'applied_items' in result ? result.applied_items || [] : [];
  const drafts = 'drafts' in result ? result.drafts || [] : [];
  const billingUrl = 'billing_url' in result ? result.billing_url : undefined;
  const savedResultRef = 'result_ref' in result ? result.result_ref : undefined;
  const resultRef = 'capability' in result && result.capability === 'communications.control_email' && savedResultRef?.entity_id
    ? { ...savedResultRef, href: `/dashboard/partnerships?section=send&business_id=${encodeURIComponent(businessId)}&campaign_id=${encodeURIComponent(savedResultRef.entity_id)}` } : savedResultRef;
  const searchPreview = 'capability' in result && ['partnerships.prepare_message', 'partnerships.continue_outreach'].includes(result.capability || '')
    && 'search_started' in result && result.search_started === false;
  const searchTask = 'task' in result ? result.task : undefined;
  const approval = 'approval' in result ? result.approval : undefined;
  const outdatedOutreachApproval = approval?.capability === 'partnerships.continue_outreach'
    && !('credit_quote' in result && result.credit_quote?.total_max !== undefined);
  const capabilityCatalog = 'capability_catalog' in result ? result.capability_catalog || [] : [];
  const capabilityExamples = 'capabilities' in result ? result.capabilities || [] : [];
  const isOperatorHelp =
    ('intent' in result && result.intent === 'operator_help') || capabilityCatalog.length > 0 || capabilityExamples.length > 0;
  const hasUsefulResultRef = !searchPreview && (!('capability' in result) || result.capability !== 'communications.control_email' || Boolean(resultRef?.entity_id)) && Boolean(resultRef?.href && resultRef.href !== '/dashboard/operator');
  const aiRouter = result.ai_router;
  const queueId = result.queue_id;
  const status = result.status || '';
  const reliabilityStatus = 'reliability_state' in result ? result.reliability_state?.status || '' : '';
  const outstandingCredits = 'billing_state' in result ? Number(result.billing_state?.outstanding_credits || 0) : 0;
  const showRecoveryActions =
    Boolean(queueId) &&
    (outstandingCredits > 0 || ['failed', 'captcha_required', 'paused', 'warning'].includes(reliabilityStatus));
  const recoveryResult = 'recovery_result' in result ? result.recovery_result : undefined;

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
          {searchPreview ? 'Ожидает запуска' : searchTask?.id
            ? status === 'approval_required' ? 'Ожидает подтверждения запуска' : 'Поиск сохранён'
            : status === 'clarification_required' ? 'Нужно уточнение' : status === 'unsupported' ? 'Не выполнено' : status === 'blocked' ? 'Требуется действие' : status === 'approval_required' ? 'Ожидает подтверждения' : ('delivery_status' in result && result.delivery_status === 'queued') ? 'В очереди' : ({ completed: 'Выполнено', processing: 'Выполняется', received: 'Команда получена', failed: 'Ошибка', cancelled: 'Отменено', rejected: 'Отклонено', history: 'Из истории' }[status] || 'Результат')}
        </span>
        {'credit_charged' in result && result.credit_charged ? <span>Списано {result.charged_credits || 0} кредитов</span> : null}
        {'manual_publication_only' in result && result.manual_publication_only ? <span>Публикация вручную</span> : null}
        {'billing_state' in result && result.billing_state?.label ? <span>{result.billing_state.label}</span> : null}
        {aiRouter?.credit_charged ? (
          <span className="rounded-full bg-sky-50 px-2 py-1 text-sky-800 ring-1 ring-sky-200">
            AI-разбор команды: -{aiRouter.charged_credits || 1} кредит
          </span>
        ) : null}
      </div>

      {searchPreview && canStartPreview && !approval?.action_id ? (
        <div className="rounded-xl border border-sky-200 bg-sky-50 px-3 py-3 text-sky-950">
          <p className="font-medium">Поиск ещё не начался</p>
          <p className="mt-1">Условия и лимиты показаны выше. Подтвердите запуск.</p>
          <Button type="button" size="sm" className="mt-2" onClick={() => void onSendCommand('Начни поиск по показанным условиям')}>
            Начать поиск
          </Button>
        </div>
      ) : null}

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

      {recoveryResult ? (
        <div className="rounded-xl border border-sky-200 bg-sky-50 px-3 py-2 text-sky-950">
          <div className="font-semibold">Recovery refresh job</div>
          <div>
            Статус: {recoveryResult.status || 'blocked'}
            {typeof recoveryResult.outstanding_credits === 'number'
              ? `; резерв к возврату: ${recoveryResult.outstanding_credits}`
              : ''}
          </div>
          {recoveryResult.blocked_reasons?.length ? (
            <div className="mt-1 text-sky-800">Причины: {recoveryResult.blocked_reasons.join(', ')}</div>
          ) : null}
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

      {services.length > 0 ? (
        <div className="space-y-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
          <div className="font-semibold text-slate-950">Услуги из списка</div>
          {services.map((service, index) => (
            <div key={service.id || `${service.name}-${index}`} className="rounded-lg bg-white px-3 py-2 shadow-sm ring-1 ring-slate-950/5">
              <div className="flex items-start gap-3">
                <span className="min-w-5 pt-0.5 text-right text-xs font-semibold tabular-nums text-slate-400">{index + 1}</span>
                <div className="min-w-0 flex-1">
                  {service.category ? <div className="text-xs font-medium text-slate-500">{service.category}</div> : null}
                  <div className="text-pretty font-semibold text-slate-950">{service.name || 'Без названия'}</div>
                </div>
                <div className="shrink-0 font-semibold tabular-nums text-slate-700">
                  {service.price ? `${service.price} ₽` : 'Цена не указана'}
                </div>
              </div>
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
        {approval?.action_id && approval.status === 'pending' && outdatedOutreachApproval ? (
          <div className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-950">
            Условия этого подтверждения устарели. Стоимость поиска теперь указана в кредитах LocalOS.
            <Button type="button" size="sm" variant="outline" className="mt-2 block" onClick={() => void onSendCommand('Покажи актуальные условия и стоимость в кредитах для последнего поручения по поиску компаний и подготовь новое подтверждение запуска')}>
              Показать актуальные условия
            </Button>
          </div>
        ) : null}
        {approval?.action_id && approval.status === 'pending' && !outdatedOutreachApproval ? (
          <>
            <Button
              type="button"
              size="sm"
              onClick={() => void onConfirmOperatorAction(approval.action_id)}
              disabled={loading.confirmingActionId === approval.action_id || loading.rejectingActionId === approval.action_id}
            >
              {loading.confirmingActionId === approval.action_id ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <CheckCircle2 className="mr-2 h-4 w-4" />}
              {searchPreview ? 'Начать поиск' : 'Подтвердить'}
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => { if (searchPreview) onEditPreview(); else void onRejectOperatorAction(approval.action_id); }}
              disabled={loading.confirmingActionId === approval.action_id || loading.rejectingActionId === approval.action_id}
            >
              {loading.rejectingActionId === approval.action_id ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
              {searchPreview ? 'Изменить условия' : 'Отклонить'}
            </Button>
          </>
        ) : null}
        {isOperatorHelp ? (
          <Button
            type="button"
            size="sm"
            aria-expanded={capabilitiesOpen}
            aria-controls={capabilityPanelId}
            onClick={() => setCapabilitiesOpen((current) => !current)}
          >
            {capabilitiesOpen ? 'Скрыть возможности' : resultRef?.label || 'Открыть возможности оператора'}
            <ChevronDown
              className={cn(
                'ml-2 h-4 w-4 transition-transform duration-200',
                capabilitiesOpen && 'rotate-180',
              )}
            />
          </Button>
        ) : hasUsefulResultRef && resultRef?.href ? (
          <Button type="button" size="sm" asChild>
            <Link to={resultRef.href}>
              {resultRef.label || 'Открыть результат'}
              <ExternalLink className="ml-2 h-3.5 w-3.5" />
            </Link>
          </Button>
        ) : null}
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

        {showRecoveryActions ? (
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => void onRecoverRefresh(queueId, false)}
            disabled={loading.recoveringQueueId === queueId}
          >
            {loading.recoveringQueueId === queueId ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
            Проверить recovery
          </Button>
        ) : null}

        {showRecoveryActions && outstandingCredits > 0 ? (
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => void onRecoverRefresh(queueId, true)}
            disabled={loading.recoveringQueueId === queueId}
          >
            {loading.recoveringQueueId === queueId ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <CheckCircle2 className="mr-2 h-4 w-4" />}
            Вернуть резерв
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

      {isOperatorHelp && capabilitiesOpen ? (
        <OperatorCapabilitiesPanel
          id={capabilityPanelId}
          capabilities={capabilityCatalog}
          fallbackItems={capabilityExamples}
        />
      ) : null}
    </div>
  );
};

type OperatorCapabilityItem = {
  name?: string;
  title?: string;
  status?: string;
  unavailable_reason?: string;
  examples?: string[];
};

const capabilityGroup = (status: string | undefined) => {
  if (status === 'disabled') return 'disabled';
  if (status === 'request_only' || status === 'manual') return 'section';
  if (status === 'gap') return 'manual';
  return 'chat';
};

const capabilityStatusLabel = (status: string | undefined) => {
  if (status === 'disabled') return 'Недоступно';
  if (status === 'draft_only') return 'Готовлю черновик';
  if (status === 'approval_required') return 'После подтверждения';
  if (status === 'request_only' || status === 'manual') return 'Открою раздел';
  if (status === 'gap') return 'Только вручную';
  return 'Выполняю';
};

const OperatorCapabilitiesPanel = ({
  id,
  capabilities,
  fallbackItems,
}: {
  id: string;
  capabilities: OperatorCapabilityItem[];
  fallbackItems: string[];
}) => {
  const groups = [
    { key: 'chat', title: 'Могу выполнить в чате' },
    { key: 'section', title: 'Открою нужный раздел' },
    { key: 'manual', title: 'Пока только вручную' },
    { key: 'disabled', title: 'Не включено для этого бизнеса' },
  ];

  return (
    <div id={id} className="border-t border-slate-200 pt-3">
      {capabilities.length > 0 ? (
        <div className="space-y-4">
          {groups.map((group) => {
            const items = capabilities.filter((item) => capabilityGroup(item.status) === group.key);
            if (items.length === 0) return null;
            return (
              <section key={group.key} aria-labelledby={`${id}-${group.key}`}>
                <h3 id={`${id}-${group.key}`} className="mb-2 text-xs font-semibold uppercase text-slate-500">
                  {group.title}
                </h3>
                <div className="divide-y divide-slate-100">
                  {items.map((item) => (
                    <div key={item.name || item.title} className="flex flex-col gap-1 py-2 first:pt-0 sm:flex-row sm:items-start sm:justify-between sm:gap-4">
                      <div className="min-w-0">
                        <div className="font-medium text-slate-950">{item.title || 'Возможность LocalOS'}</div>
                        {item.unavailable_reason && <p className="text-xs text-slate-500">{item.unavailable_reason}</p>}
                        {item.examples?.[0] ? (
                          <div className="text-pretty text-xs text-slate-500">Например: «{item.examples[0]}»</div>
                        ) : null}
                      </div>
                      <span className="shrink-0 text-xs font-medium text-slate-500">
                        {capabilityStatusLabel(item.status)}
                      </span>
                    </div>
                  ))}
                </div>
              </section>
            );
          })}
        </div>
      ) : (
        <ul className="space-y-2 text-sm text-slate-700">
          {fallbackItems.map((item) => (
            <li key={item} className="flex gap-2">
              <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

