import React from 'react';
import { AlertCircle, ArrowUpRight, Camera, MessageSquare, ReceiptText, Star, TrendingUp } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { useApiData } from '@/hooks/useApiData';

interface CardAuditPanelProps {
  businessId?: string | null;
}

interface CardAuditResponse {
  success: boolean;
  audit: {
    summary_score: number;
    health_level: 'strong' | 'growth' | 'risk';
    health_label: string;
    summary_text: string;
    findings: Array<{
      key: string;
      severity: 'critical' | 'high' | 'medium' | 'low';
      title: string;
      detail: string;
    }>;
    subscores: {
      profile: number;
      reputation: number;
      services: number;
      activity: number;
    };
    revenue_potential: {
      baseline_revenue: number;
      rating_gap: { min: number; max: number };
      content_gap: { min: number; max: number };
      service_gap: { min: number; max: number };
      total_min: number;
      total_max: number;
      currency: string;
      model: string;
    };
    recommended_actions: Array<{
      priority: 'high' | 'medium' | 'low';
      title: string;
      detail: string;
    }>;
    current_state: {
      rating: number | null;
      reviews_count: number;
      unanswered_reviews_count: number;
      services_count: number;
      priced_services_count: number;
      photos_count: number;
      news_count: number;
      last_parse_date?: string | null;
      last_parse_status?: string | null;
      last_card_update?: string | null;
      last_service_update?: string | null;
    };
  };
}

const severityClasses: Record<string, string> = {
  critical: 'border-red-200 bg-red-50 text-red-800',
  high: 'border-orange-200 bg-orange-50 text-orange-800',
  medium: 'border-amber-200 bg-amber-50 text-amber-800',
  low: 'border-slate-200 bg-slate-50 text-slate-800',
};

const priorityClasses: Record<string, string> = {
  high: 'bg-red-100 text-red-800',
  medium: 'bg-amber-100 text-amber-800',
  low: 'bg-slate-100 text-slate-700',
};

const healthClasses: Record<string, string> = {
  strong: 'bg-emerald-100 text-emerald-800 border-emerald-200',
  growth: 'bg-amber-100 text-amber-800 border-amber-200',
  risk: 'bg-red-100 text-red-800 border-red-200',
};

const formatMoney = (value: number) =>
  `${new Intl.NumberFormat('ru-RU').format(Math.round(value))} ₽`;

const formatDate = (value?: string | null) =>
  value ? new Date(value).toLocaleString('ru-RU') : '—';

const subscoreCards = [
  { key: 'profile', label: 'Заполнение карточки', icon: ReceiptText },
  { key: 'reputation', label: 'Репутация', icon: Star },
  { key: 'services', label: 'Услуги', icon: TrendingUp },
  { key: 'activity', label: 'Активность', icon: Camera },
] as const;

const CardAuditPanel: React.FC<CardAuditPanelProps> = ({ businessId }) => {
  const { data, loading, error } = useApiData<CardAuditResponse>(
    businessId ? `${window.location.origin}/api/business/${businessId}/card-audit` : null
  );

  const audit = data?.audit;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Аудит карточки</CardTitle>
        <CardDescription>
          Текущее состояние карточки, ключевые точки роста и ориентировочный потенциал выручки.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {loading && (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {Array.from({ length: 4 }).map((_, idx) => (
              <div key={idx} className="h-28 rounded-xl bg-gray-100 animate-pulse" />
            ))}
          </div>
        )}

        {!loading && error && (
          <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            Не удалось загрузить аудит карточки: {error}
          </div>
        )}

        {!loading && !error && audit && (
          <>
            <div className="grid gap-4 xl:grid-cols-[1.4fr_1fr]">
              <div className="rounded-2xl border border-slate-200 bg-gradient-to-br from-white to-slate-50 p-5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="text-sm font-medium text-slate-500">Итоговая оценка</div>
                    <div className="mt-2 text-5xl font-bold tracking-tight text-slate-900">
                      {audit.summary_score}
                    </div>
                  </div>
                  <div className={`rounded-full border px-3 py-1 text-sm font-semibold ${healthClasses[audit.health_level] || healthClasses.growth}`}>
                    {audit.health_label}
                  </div>
                </div>
                <p className="mt-4 text-sm leading-6 text-slate-700">{audit.summary_text}</p>
                <div className="mt-4 grid gap-3 sm:grid-cols-2">
                  <div className="rounded-xl border border-slate-200 bg-white p-3">
                    <div className="text-xs font-medium uppercase tracking-wide text-slate-500">Последний парсинг</div>
                    <div className="mt-1 text-sm font-semibold text-slate-900">
                      {formatDate(audit.current_state.last_parse_date)}
                    </div>
                    <div className="mt-1 text-xs text-slate-500">
                      Статус: {audit.current_state.last_parse_status || '—'}
                    </div>
                  </div>
                  <div className="rounded-xl border border-slate-200 bg-white p-3">
                    <div className="text-xs font-medium uppercase tracking-wide text-slate-500">База оценки</div>
                    <div className="mt-1 text-sm font-semibold text-slate-900">
                      {formatMoney(audit.revenue_potential.baseline_revenue)} / мес
                    </div>
                    <div className="mt-1 text-xs text-slate-500">
                      Модель: {audit.revenue_potential.model}
                    </div>
                  </div>
                </div>
              </div>

              <div className="rounded-2xl border border-orange-200 bg-gradient-to-br from-orange-50 via-white to-amber-50 p-5">
                <div className="flex items-center gap-2 text-sm font-medium text-orange-700">
                  <ArrowUpRight className="h-4 w-4" />
                  Потенциал выручки
                </div>
                <div className="mt-3 text-2xl font-bold text-slate-900">
                  {formatMoney(audit.revenue_potential.total_min)} – {formatMoney(audit.revenue_potential.total_max)}
                </div>
                <div className="mt-1 text-sm text-slate-600">Ориентировочный недобор в текущем виде карточки</div>
                <div className="mt-4 space-y-3">
                  <div className="rounded-xl bg-white p-3">
                    <div className="text-xs uppercase tracking-wide text-slate-500">Из-за рейтинга</div>
                    <div className="mt-1 text-sm font-semibold text-slate-900">
                      {formatMoney(audit.revenue_potential.rating_gap.min)} – {formatMoney(audit.revenue_potential.rating_gap.max)}
                    </div>
                  </div>
                  <div className="rounded-xl bg-white p-3">
                    <div className="text-xs uppercase tracking-wide text-slate-500">Из-за неполной карточки</div>
                    <div className="mt-1 text-sm font-semibold text-slate-900">
                      {formatMoney(audit.revenue_potential.content_gap.min)} – {formatMoney(audit.revenue_potential.content_gap.max)}
                    </div>
                  </div>
                  <div className="rounded-xl bg-white p-3">
                    <div className="text-xs uppercase tracking-wide text-slate-500">Из-за услуг</div>
                    <div className="mt-1 text-sm font-semibold text-slate-900">
                      {formatMoney(audit.revenue_potential.service_gap.min)} – {formatMoney(audit.revenue_potential.service_gap.max)}
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              {subscoreCards.map(({ key, label, icon: Icon }) => (
                <div key={key} className="rounded-2xl border border-slate-200 bg-white p-4">
                  <div className="flex items-center gap-2 text-sm font-medium text-slate-600">
                    <Icon className="h-4 w-4" />
                    {label}
                  </div>
                  <div className="mt-2 text-3xl font-bold text-slate-900">
                    {audit.subscores[key]}
                  </div>
                  <div className="mt-1 text-xs text-slate-500">из 100</div>
                </div>
              ))}
            </div>

            <div className="grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
              <div className="rounded-2xl border border-slate-200 bg-white p-5">
                <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                  <AlertCircle className="h-4 w-4 text-amber-500" />
                  Ключевые точки роста
                </div>
                <div className="mt-4 space-y-3">
                  {audit.findings.length === 0 ? (
                    <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">
                      Критичных проблем не найдено. Карточка выглядит стабильно.
                    </div>
                  ) : (
                    audit.findings.map((finding) => (
                      <div
                        key={finding.key}
                        className={`rounded-xl border p-4 ${severityClasses[finding.severity] || severityClasses.medium}`}
                      >
                        <div className="text-sm font-semibold">{finding.title}</div>
                        <div className="mt-1 text-sm leading-6">{finding.detail}</div>
                      </div>
                    ))
                  )}
                </div>
              </div>

              <div className="rounded-2xl border border-slate-200 bg-white p-5">
                <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                  <MessageSquare className="h-4 w-4 text-blue-500" />
                  Что сделать дальше
                </div>
                <div className="mt-4 space-y-3">
                  {audit.recommended_actions.length === 0 ? (
                    <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
                      Сейчас карточка не требует срочных действий.
                    </div>
                  ) : (
                    audit.recommended_actions.map((action, idx) => (
                      <div key={`${action.title}-${idx}`} className="rounded-xl border border-slate-200 p-4">
                        <div className="flex items-center justify-between gap-3">
                          <div className="text-sm font-semibold text-slate-900">{action.title}</div>
                          <div className={`rounded-full px-2 py-1 text-xs font-medium ${priorityClasses[action.priority] || priorityClasses.medium}`}>
                            {action.priority === 'high' ? 'Срочно' : action.priority === 'medium' ? 'Быстрый эффект' : 'Планово'}
                          </div>
                        </div>
                        <div className="mt-2 text-sm leading-6 text-slate-600">{action.detail}</div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-white p-5">
              <div className="text-sm font-semibold text-slate-900">Текущее состояние карточки</div>
              <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                <div className="rounded-xl bg-slate-50 p-4">
                  <div className="text-xs uppercase tracking-wide text-slate-500">Репутация</div>
                  <div className="mt-2 text-sm font-semibold text-slate-900">
                    Рейтинг: {audit.current_state.rating !== null ? audit.current_state.rating.toFixed(1) : '—'}
                  </div>
                  <div className="mt-1 text-sm text-slate-600">Отзывов: {audit.current_state.reviews_count}</div>
                  <div className="mt-1 text-sm text-slate-600">Без ответа: {audit.current_state.unanswered_reviews_count}</div>
                </div>
                <div className="rounded-xl bg-slate-50 p-4">
                  <div className="text-xs uppercase tracking-wide text-slate-500">Услуги</div>
                  <div className="mt-2 text-sm font-semibold text-slate-900">Активных: {audit.current_state.services_count}</div>
                  <div className="mt-1 text-sm text-slate-600">С ценами: {audit.current_state.priced_services_count}</div>
                  <div className="mt-1 text-sm text-slate-600">
                    Обновление: {formatDate(audit.current_state.last_service_update)}
                  </div>
                </div>
                <div className="rounded-xl bg-slate-50 p-4">
                  <div className="text-xs uppercase tracking-wide text-slate-500">Контент</div>
                  <div className="mt-2 text-sm font-semibold text-slate-900">Фото: {audit.current_state.photos_count}</div>
                  <div className="mt-1 text-sm text-slate-600">Новости: {audit.current_state.news_count}</div>
                  <div className="mt-1 text-sm text-slate-600">
                    Карточка: {formatDate(audit.current_state.last_card_update)}
                  </div>
                </div>
                <div className="rounded-xl bg-slate-50 p-4">
                  <div className="text-xs uppercase tracking-wide text-slate-500">Итог</div>
                  <div className="mt-2 text-sm font-semibold text-slate-900">{audit.health_label}</div>
                  <div className="mt-1 text-sm text-slate-600">Баланс факторов: {audit.summary_score}/100</div>
                  <div className="mt-1 text-sm text-slate-600">
                    Модель: deterministic rules + numeric bands
                  </div>
                </div>
              </div>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
};

export default CardAuditPanel;
