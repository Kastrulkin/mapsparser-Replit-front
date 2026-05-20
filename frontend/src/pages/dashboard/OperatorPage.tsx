import { useEffect, useMemo, useState } from 'react';
import { Link, useOutletContext } from 'react-router-dom';
import {
  AlertCircle,
  Bot,
  CheckCircle2,
  Clock3,
  CreditCard,
  ExternalLink,
  Loader2,
  MessageSquareText,
  RefreshCw,
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
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadBrief = async () => {
    if (!currentBusinessId) {
      setBrief(null);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const response = await api.get('/operator/attention-brief', {
        params: { business_id: currentBusinessId },
      });
      setBrief(response.data.brief || null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось загрузить сводку');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadBrief();
  }, [currentBusinessId]);

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
        </>
      ) : null}
    </div>
  );
};
