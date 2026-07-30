import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  AlertCircle,
  CalendarClock,
  CheckCheck,
  CircleDashed,
  Clock3,
  ExternalLink,
  Eye,
  LoaderCircle,
  MessageCircleReply,
  PauseCircle,
  RefreshCw,
  Send,
} from 'lucide-react';
import { newAuth } from '../../lib/auth_new';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';

export interface OutreachMessageQueueItem {
  touch_id: string;
  sequence_index?: number;
  channel?: string;
  scheduled_at?: string | null;
  subject?: string | null;
  message_text?: string;
  campaign_id?: string;
  campaign_version?: number;
  campaign_status?: string;
  workstream_id: string;
  workstream_type?: string;
  client_business_id?: string | null;
  client_business_name?: string | null;
  lead_id: string;
  lead_name?: string;
  lead_category?: string | null;
  recipient?: string | null;
  sender_identity?: string | null;
  sender_display_name?: string | null;
  delivery_status?: string | null;
  provider_message_id?: string | null;
  error_text?: string | null;
  sent_at?: string | null;
  replied_at?: string | null;
  reply_payload_json?: Record<string, unknown> | null;
  receipt_at?: string | null;
  status: string;
}

interface OutreachMessageQueueProps {
  query: string;
  scope: 'all' | 'localos_sales' | 'client_partnership';
  businessId?: string;
  channel: string;
  status: string;
  onChannelChange: (value: string) => void;
  onStatusChange: (value: string) => void;
  onOpenLead: (leadId: string, workstreamId: string) => void;
}

interface QueuePayload {
  items?: OutreachMessageQueueItem[];
  total?: number;
  summary?: Record<string, number>;
}

const channelLabels: Record<string, string> = {
  email: 'Email',
  telegram: 'Telegram',
  vk: 'VK',
  vk_manual: 'VK · вручную',
  whatsapp: 'WhatsApp',
  max: 'MAX',
  manual: 'Вручную',
};

const statusLabels: Record<string, string> = {
  draft: 'Черновик',
  scheduled: 'Запланировано',
  queued: 'В очереди',
  sending: 'Отправляется',
  sent: 'Отправлено',
  delivered: 'Доставлено',
  read: 'Прочитано',
  replied: 'Получен ответ',
  awaiting_manual_send: 'Нужно отправить вручную',
  paused: 'На паузе',
  cancelled: 'Отменено',
  skipped: 'Пропущено',
  reply_cancelled: 'Остановлено после ответа',
  failed: 'Ошибка отправки',
};

const statusTone: Record<string, string> = {
  draft: 'border-slate-200 bg-slate-50 text-slate-700',
  scheduled: 'border-blue-200 bg-blue-50 text-blue-700',
  queued: 'border-indigo-200 bg-indigo-50 text-indigo-700',
  sending: 'border-indigo-200 bg-indigo-50 text-indigo-700',
  sent: 'border-sky-200 bg-sky-50 text-sky-700',
  delivered: 'border-emerald-200 bg-emerald-50 text-emerald-700',
  read: 'border-teal-200 bg-teal-50 text-teal-700',
  replied: 'border-green-200 bg-green-50 text-green-800',
  awaiting_manual_send: 'border-amber-200 bg-amber-50 text-amber-800',
  paused: 'border-slate-200 bg-slate-50 text-slate-600',
  cancelled: 'border-slate-200 bg-slate-50 text-slate-500',
  skipped: 'border-slate-200 bg-slate-50 text-slate-500',
  reply_cancelled: 'border-slate-200 bg-slate-50 text-slate-600',
  failed: 'border-rose-200 bg-rose-50 text-rose-700',
};

const summaryStatuses = [
  { value: '', label: 'Все' },
  { value: 'draft', label: 'Черновики' },
  { value: 'scheduled', label: 'Запланировано' },
  { value: 'awaiting_manual_send', label: 'Вручную' },
  { value: 'sent', label: 'Отправлено' },
  { value: 'delivered', label: 'Доставлено' },
  { value: 'read', label: 'Прочитано' },
  { value: 'replied', label: 'Ответы' },
  { value: 'failed', label: 'Ошибки' },
];

const messageMoment = (item: OutreachMessageQueueItem) => {
  const rawValue = item.replied_at || item.receipt_at || item.sent_at || item.scheduled_at;
  const value = new Date(String(rawValue || ''));
  if (Number.isNaN(value.getTime())) return 'Время не указано';
  return new Intl.DateTimeFormat('ru-RU', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  }).format(value);
};

const replyText = (item: OutreachMessageQueueItem) => {
  const payload = item.reply_payload_json;
  if (!payload) return '';
  const rawReply = payload.raw_reply;
  if (typeof rawReply === 'string') return rawReply;
  const text = payload.text;
  return typeof text === 'string' ? text : '';
};

const verificationLink = (item: OutreachMessageQueueItem) => {
  const recipient = String(item.recipient || '').trim();
  const channel = String(item.channel || '').trim().toLowerCase();
  if (channel === 'email' && recipient) {
    const authUser = item.sender_identity ? `?authuser=${encodeURIComponent(item.sender_identity)}` : '';
    return {
      href: `https://mail.google.com/mail/u/${authUser}#search/${encodeURIComponent(`in:sent to:${recipient}`)}`,
      label: 'Проверить в почте',
    };
  }
  if (/^https?:\/\//i.test(recipient)) {
    return { href: recipient, label: 'Открыть канал' };
  }
  return null;
};

const StatusIcon = ({ status }: { status: string }) => {
  const className = 'h-4 w-4';
  if (status === 'scheduled') return <CalendarClock className={className} />;
  if (status === 'queued') return <Clock3 className={className} />;
  if (status === 'sending') return <LoaderCircle className={`${className} animate-spin`} />;
  if (status === 'sent') return <Send className={className} />;
  if (status === 'delivered') return <CheckCheck className={className} />;
  if (status === 'read') return <Eye className={className} />;
  if (status === 'replied') return <MessageCircleReply className={className} />;
  if (status === 'failed') return <AlertCircle className={className} />;
  if (status === 'paused' || status === 'reply_cancelled') return <PauseCircle className={className} />;
  return <CircleDashed className={className} />;
};

export function OutreachMessageQueue({
  query,
  scope,
  businessId,
  channel,
  status,
  onChannelChange,
  onStatusChange,
  onOpenLead,
}: OutreachMessageQueueProps) {
  const [items, setItems] = useState<OutreachMessageQueueItem[]>([]);
  const [summary, setSummary] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const loadMessages = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const params = new URLSearchParams({ limit: '500' });
      if (query.trim()) params.set('q', query.trim());
      if (scope !== 'all') params.set('workstream_type', scope);
      if (businessId) params.set('business_id', businessId);
      if (channel) params.set('channel', channel);
      if (status) params.set('status', status);
      const payload: QueuePayload = await newAuth.makeRequest(`/outreach/messages?${params.toString()}`);
      setItems(Array.isArray(payload?.items) ? payload.items : []);
      setSummary(payload?.summary || {});
    } catch (requestError) {
      setItems([]);
      setSummary({});
      setError(requestError instanceof Error ? requestError.message : 'Не удалось загрузить сообщения');
    } finally {
      setLoading(false);
    }
  }, [businessId, channel, query, scope, status]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadMessages();
    }, query.trim() ? 250 : 0);
    return () => window.clearTimeout(timer);
  }, [loadMessages, query]);

  const visibleCount = useMemo(() => items.length, [items]);

  return (
    <section aria-labelledby="outreach-message-queue-title" className="pb-6">
      <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h2 id="outreach-message-queue-title" className="text-wrap-balance text-lg font-semibold text-slate-950">
            Очередь сообщений
          </h2>
          <p className="mt-1 max-w-2xl text-wrap-pretty text-sm text-slate-500">
            Все касания текущих цепочек: что готовится, когда отправится, что уже доставлено и на что ответили.
          </p>
        </div>
        <div className="flex min-h-10 items-center gap-2">
          <select
            value={channel}
            onChange={(event) => onChannelChange(event.target.value)}
            className="h-10 rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-800"
            aria-label="Канал сообщения"
          >
            <option value="">Все каналы</option>
            {Object.entries(channelLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
          <Button variant="outline" onClick={() => void loadMessages()} className="min-h-10 active:scale-[0.96]">
            <RefreshCw className={`mr-2 h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            Обновить
          </Button>
        </div>
      </div>

      <div className="mb-4 flex gap-2 overflow-x-auto pb-1" aria-label="Фильтр по статусу">
        {summaryStatuses.map((item) => {
          const countKey = item.value || 'all';
          const count = Number(summary[countKey] || 0);
          const selected = status === item.value;
          return (
            <button
              key={countKey}
              type="button"
              onClick={() => onStatusChange(item.value)}
              className={`flex min-h-10 shrink-0 items-center gap-2 rounded-md px-3 text-sm font-medium transition-colors active:scale-[0.96] ${
                selected
                  ? 'bg-slate-950 text-white shadow-sm'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200 hover:text-slate-950'
              }`}
            >
              <span>{item.label}</span>
              <span className={`tabular-nums ${selected ? 'text-slate-300' : 'text-slate-400'}`}>{count}</span>
            </button>
          );
        })}
      </div>

      {error ? (
        <div className="flex min-h-52 flex-col items-center justify-center gap-3 rounded-lg bg-rose-50 px-6 text-center shadow-[inset_0_0_0_1px_rgba(244,63,94,0.14)]">
          <AlertCircle className="h-7 w-7 text-rose-500" />
          <p className="max-w-md text-sm text-rose-700">{error}</p>
          <Button variant="outline" onClick={() => void loadMessages()}>Повторить</Button>
        </div>
      ) : !loading && !items.length ? (
        <div className="flex min-h-52 flex-col items-center justify-center gap-2 rounded-lg bg-slate-50 px-6 text-center shadow-[inset_0_0_0_1px_rgba(15,23,42,0.06)]">
          <MessageCircleReply className="h-8 w-8 text-slate-300" />
          <h3 className="font-semibold text-slate-950">По этим условиям сообщений нет</h3>
          <p className="max-w-lg text-sm text-slate-500">
            Измените фильтр или подготовьте и сохраните цепочку в карточке лида.
          </p>
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl bg-white shadow-[0_1px_2px_rgba(15,23,42,0.05),0_0_0_1px_rgba(15,23,42,0.08)]">
          <div className="hidden grid-cols-[minmax(250px,1.2fr)_minmax(180px,.7fr)_minmax(145px,.55fr)_minmax(160px,.6fr)_auto] gap-4 bg-slate-50 px-4 py-3 text-xs font-semibold uppercase tracking-[0.08em] text-slate-500 lg:grid">
            <span>Сообщение</span>
            <span>Получатель</span>
            <span>Когда</span>
            <span>Статус</span>
            <span className="sr-only">Действия</span>
          </div>
          <div className="divide-y divide-slate-100">
            {loading ? (
              <div className="flex min-h-40 items-center justify-center gap-2 text-sm text-slate-500">
                <LoaderCircle className="h-5 w-5 animate-spin" />
                Загружаем сообщения…
              </div>
            ) : items.map((item) => {
              const externalLink = verificationLink(item);
              const response = replyText(item);
              return (
                <article
                  key={item.touch_id}
                  className="grid gap-3 px-4 py-4 transition-colors hover:bg-slate-50 lg:grid-cols-[minmax(250px,1.2fr)_minmax(180px,.7fr)_minmax(145px,.55fr)_minmax(160px,.6fr)_auto] lg:items-center lg:gap-4"
                >
                  <div className="min-w-0">
                    <div className="flex min-w-0 items-center gap-2">
                      <Badge variant="outline" className="shrink-0 border-slate-200 bg-white text-slate-600">
                        {channelLabels[String(item.channel || '')] || String(item.channel || 'Канал')}
                      </Badge>
                      <span className="truncate text-xs text-slate-400">
                        Шаг {Number(item.sequence_index || 0) + 1} · версия {Number(item.campaign_version || 0)}
                      </span>
                    </div>
                    {item.subject ? <p className="mt-2 truncate text-sm font-semibold text-slate-950">{item.subject}</p> : null}
                    <p className="mt-1 line-clamp-2 text-wrap-pretty text-sm leading-5 text-slate-600">
                      {response || item.message_text || 'Текст сообщения пока не подготовлен'}
                    </p>
                    {response ? <p className="mt-1 text-xs font-medium text-emerald-700">Ответ получателя</p> : null}
                  </div>

                  <div className="min-w-0">
                    <button
                      type="button"
                      onClick={() => onOpenLead(item.lead_id, item.workstream_id)}
                      className="min-h-10 max-w-full text-left active:scale-[0.96]"
                    >
                      <span className="block truncate text-sm font-semibold text-slate-950">{item.lead_name || 'Компания'}</span>
                      <span className="mt-0.5 block truncate text-xs text-slate-500">{item.recipient || 'Получатель не выбран'}</span>
                      {item.sender_display_name || item.sender_identity ? (
                        <span className="mt-1 block truncate text-xs text-slate-400">
                          От: {item.sender_display_name || item.sender_identity}
                        </span>
                      ) : null}
                      {item.client_business_name ? (
                        <span className="mt-1 block truncate text-xs text-slate-400">Для: {item.client_business_name}</span>
                      ) : null}
                    </button>
                  </div>

                  <div className="tabular-nums text-sm text-slate-600">
                    <span className="lg:hidden">Когда: </span>{messageMoment(item)}
                  </div>

                  <div className="min-w-0">
                    <Badge variant="outline" className={`gap-1.5 whitespace-nowrap ${statusTone[item.status] || statusTone.draft}`}>
                      <StatusIcon status={item.status} />
                      {statusLabels[item.status] || item.status}
                    </Badge>
                    {item.provider_message_id ? (
                      <p className="mt-1 truncate font-mono text-[11px] text-slate-400" title={item.provider_message_id}>
                        ID: {item.provider_message_id}
                      </p>
                    ) : null}
                    {item.error_text ? <p className="mt-1 line-clamp-2 text-xs text-rose-600">{item.error_text}</p> : null}
                  </div>

                  <div className="flex min-w-[132px] items-center justify-end gap-1">
                    {externalLink ? (
                      <a
                        href={externalLink.href}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex min-h-10 items-center gap-1.5 rounded-md px-2 text-xs font-semibold text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-950 active:scale-[0.96]"
                      >
                        {externalLink.label}
                        <ExternalLink className="h-3.5 w-3.5" />
                      </a>
                    ) : null}
                    <button
                      type="button"
                      onClick={() => onOpenLead(item.lead_id, item.workstream_id)}
                      className="min-h-10 rounded-md px-2 text-xs font-semibold text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-950 active:scale-[0.96]"
                    >
                      Открыть лид
                    </button>
                  </div>
                </article>
              );
            })}
          </div>
        </div>
      )}

      {!loading && visibleCount > 0 ? (
        <p className="mt-3 text-right text-xs text-slate-400">
          Показано: <span className="tabular-nums">{visibleCount}</span>
        </p>
      ) : null}
    </section>
  );
}

export default OutreachMessageQueue;
