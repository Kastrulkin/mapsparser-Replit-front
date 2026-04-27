import React from 'react';
import { AlertCircle, ArrowUpRight, Camera, Globe, MessageSquare, ReceiptText, Star, TrendingUp } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { useApiData } from '@/hooks/useApiData';
import { useLanguage } from '@/i18n/LanguageContext';

interface CardAuditPanelProps {
  businessId?: string | null;
  refreshKey?: number;
}

interface CardAuditResponse {
  success: boolean;
  audit: {
    business?: {
      id: string;
      name: string;
      business_type?: string | null;
      city?: string | null;
    };
    summary_score: number;
    health_level: 'strong' | 'growth' | 'risk';
    health_label: string;
    summary_text: string;
    findings: Array<{
      code: string;
      severity: 'high' | 'medium' | 'low';
      title: string;
      description: string;
    }>;
    issue_blocks?: Array<{
      id?: string;
      section?: string;
      priority?: 'critical' | 'high' | 'medium' | 'low' | string;
      title?: string;
      problem?: string;
      evidence?: string;
      impact?: string;
      fix?: string;
    }>;
    top_3_issues?: Array<{
      id?: string;
      title?: string;
      priority?: string;
      problem?: string;
    }>;
    action_plan?: {
      next_24h?: string[];
      next_7d?: string[];
      ongoing?: string[];
    };
    audit_profile?: string;
    audit_profile_label?: string;
    best_fit_customer_profile?: string[];
    weak_fit_customer_profile?: string[];
    best_fit_guest_profile?: string[];
    weak_fit_guest_profile?: string[];
    search_intents_to_target?: string[];
    photo_shots_missing?: string[];
    positioning_focus?: string[];
    strength_themes?: string[];
    objection_themes?: string[];
    subscores: {
      profile: number;
      reputation: number;
      services: number;
      activity: number;
    };
    revenue_potential: {
      mode: string;
      baseline_monthly_revenue: {
        value: number;
        source: string;
      };
      rating_gap: { min: number; max: number };
      content_gap: { min: number; max: number };
      service_gap: { min: number; max: number };
      total_min: number;
      total_max: number;
      confidence: 'low' | 'medium' | 'high';
      disclaimer: string;
    };
    recommended_actions: Array<{
      priority: 'high' | 'medium' | 'low';
      title: string;
      description: string;
    }>;
    current_state: {
      rating: number | null;
      reviews_count: number;
      unanswered_reviews_count: number;
      services_count: number;
      services_with_price_count: number;
      has_website: boolean;
      has_recent_activity: boolean;
      photos_state: 'good' | 'weak' | 'missing' | string;
    };
    parse_context: {
      last_parse_at?: string | null;
      last_parse_status?: string | null;
      last_successful_parse_at?: string | null;
      has_successful_parse?: boolean;
      no_new_services_found: boolean;
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
  critical: 'bg-red-200 text-red-900',
  high: 'bg-red-100 text-red-800',
  medium: 'bg-amber-100 text-amber-800',
  low: 'bg-slate-100 text-slate-700',
};

const healthClasses: Record<string, string> = {
  strong: 'bg-emerald-100 text-emerald-800 border-emerald-200',
  growth: 'bg-amber-100 text-amber-800 border-amber-200',
  risk: 'bg-red-100 text-red-800 border-red-200',
};

const confidenceLabels: Record<string, string> = {
  high: 'Высокая',
  medium: 'Средняя',
  low: 'Низкая',
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

const parseStatusLabel = (value?: string | null) => {
  if (!value) return '—';
  if (value === 'completed' || value === 'success') return 'Успешно';
  if (value === 'captcha') return 'Требуется капча';
  if (value === 'processing' || value === 'running') return 'В процессе';
  if (value === 'failed' || value === 'error') return 'С ошибкой';
  return value;
};

const revenueSourceLabel = (value: string) => {
  switch (value) {
    case 'actual':
      return 'Фактическая выручка';
    case 'estimated_from_average_check':
      return 'Оценка по среднему чеку';
    case 'category_baseline':
      return 'База по типу бизнеса';
    default:
      return 'Базовая модель';
  }
};

const photosStateLabel = (value: string) => {
  switch (value) {
    case 'good':
      return 'Достаточно';
    case 'weak':
      return 'Мало';
    case 'missing':
      return 'Нет или не найдены';
    default:
      return 'Неизвестно';
  }
};

const CardAuditPanel: React.FC<CardAuditPanelProps> = ({ businessId, refreshKey = 0 }) => {
  const { language } = useLanguage();
  const isRu = language === 'ru';
  const { data, loading, error } = useApiData<CardAuditResponse>(
    businessId ? `${window.location.origin}/api/business/${businessId}/card-audit?refresh=${refreshKey}` : null
  );

  const audit = data?.audit;
  const hasSuccessfulParse = Boolean(audit?.parse_context?.has_successful_parse);
  const showPreParsePlaceholder = !loading && !error && audit && !hasSuccessfulParse;

  return (
    <Card>
      <CardHeader>
        <CardTitle>{isRu ? 'Аудит карточки' : 'Card audit'}</CardTitle>
        <CardDescription>
          {isRu
            ? 'Текущее состояние карточки, ключевые точки роста и ориентировочный потенциал выручки.'
            : 'Current listing state, key growth opportunities, and estimated revenue potential.'}
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
            {isRu ? 'Не удалось загрузить аудит карточки:' : 'Could not load the card audit:'} {error}
          </div>
        )}

        {showPreParsePlaceholder && (
          <div className="rounded-xl border border-sky-200 bg-sky-50 p-5 text-sm text-sky-900">
            <div className="font-semibold">
              {isRu ? 'Аудит появится после первого успешного сбора данных' : 'The audit will appear after the first successful data collection'}
            </div>
            <div className="mt-2 leading-6">
              {isRu
                ? 'Сначала перейдите во вкладку «Работа с картами» и запустите «Обновить данные карточки». Пока сбор не завершён, здесь не показываем полноценный аудит, чтобы не вводить в заблуждение.'
                : 'First go to “Maps Management” and run “Refresh card data”. Until that collection finishes, we do not show a full audit here to avoid misleading first-time users.'}
            </div>
          </div>
        )}

        {!loading && !error && audit && hasSuccessfulParse && (
          <>
            {Array.isArray(audit.top_3_issues) && audit.top_3_issues.length > 0 && (
              <div className="rounded-2xl border border-amber-200 bg-amber-50/70 p-5">
                <div className="text-sm font-semibold text-slate-900">Топ-3 главные проблемы карточки</div>
                <div className="mt-3 grid gap-3 md:grid-cols-3">
                  {audit.top_3_issues.map((item, idx) => (
                    <div key={`${item.id || item.title || 'top'}-${idx}`} className="rounded-xl border border-amber-200 bg-white p-3">
                      <div className="flex items-center justify-between gap-2">
                        <div className="text-sm font-semibold text-slate-900">{item.title || 'Проблема'}</div>
                        <div className={`rounded-full px-2 py-1 text-xs font-medium ${priorityClasses[item.priority || 'medium'] || priorityClasses.medium}`}>
                          {String(item.priority || 'medium').toUpperCase()}
                        </div>
                      </div>
                      <div className="mt-2 text-xs leading-5 text-slate-600">{item.problem || 'Требуется проверка карточки.'}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="grid gap-4 xl:grid-cols-[1.4fr_1fr]">
              <div className="rounded-2xl border border-slate-200 bg-gradient-to-br from-white to-slate-50 p-5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="text-sm font-medium text-slate-500">Итоговая оценка</div>
                    <div className="mt-2 text-5xl font-bold tracking-tight text-slate-900">
                      {audit.summary_score}
                    </div>
                    {(audit.business?.business_type || audit.business?.city) && (
                      <div className="mt-2 text-xs font-medium uppercase tracking-wide text-slate-500">
                        {[audit.business?.business_type, audit.business?.city].filter(Boolean).join(' • ')}
                      </div>
                    )}
                  </div>
                  <div className={`rounded-full border px-3 py-1 text-sm font-semibold ${healthClasses[audit.health_level] || healthClasses.growth}`}>
                    {audit.health_label}
                  </div>
                </div>
                <p className="mt-4 text-sm leading-6 text-slate-700">{audit.summary_text}</p>
                {(
                  (audit.best_fit_customer_profile && audit.best_fit_customer_profile.length > 0) ||
                  (audit.best_fit_guest_profile && audit.best_fit_guest_profile.length > 0) ||
                  (audit.weak_fit_customer_profile && audit.weak_fit_customer_profile.length > 0) ||
                  (audit.weak_fit_guest_profile && audit.weak_fit_guest_profile.length > 0) ||
                  (audit.search_intents_to_target && audit.search_intents_to_target.length > 0) ||
                  (audit.photo_shots_missing && audit.photo_shots_missing.length > 0) ||
                  (audit.positioning_focus && audit.positioning_focus.length > 0) ||
                  (audit.strength_themes && audit.strength_themes.length > 0) ||
                  (audit.objection_themes && audit.objection_themes.length > 0)
                ) && (
                  <div className="mt-4 rounded-xl border border-slate-200 bg-white p-4">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="text-sm font-semibold text-slate-900">Позиционирование и сценарии поиска</div>
                      <div className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-medium text-slate-700">
                        {audit.audit_profile_label || audit.audit_profile || 'Локальный бизнес'}
                      </div>
                    </div>
                    {(audit.positioning_focus || []).length > 0 && (
                      <div className="mt-3 space-y-1 text-sm text-slate-700">
                        {(audit.positioning_focus || []).slice(0, 3).map((line, idx) => <div key={`position-${idx}`}>• {line}</div>)}
                      </div>
                    )}
                    {(audit.search_intents_to_target || []).length > 0 && (
                      <div className="mt-3 flex flex-wrap gap-2">
                        {(audit.search_intents_to_target || []).slice(0, 5).map((line, idx) => (
                          <div key={`intent-${idx}`} className="rounded-full border border-sky-200 bg-sky-50 px-3 py-1 text-xs text-slate-700">
                            {line}
                          </div>
                        ))}
                      </div>
                    )}
                    {(((audit.weak_fit_customer_profile || []).length > 0) || ((audit.weak_fit_guest_profile || []).length > 0)) && (
                      <div className="mt-3 rounded-xl border border-rose-200 bg-rose-50/60 p-4 text-sm text-slate-700">
                        <div className="font-semibold text-slate-900">Где ожидания чаще всего расходятся</div>
                        <div className="mt-2 space-y-1">
                          {(((audit.weak_fit_customer_profile || []).length > 0) ? (audit.weak_fit_customer_profile || []) : (audit.weak_fit_guest_profile || [])).slice(0, 4).map((line, idx) => (
                            <div key={`weak-${idx}`}>• {line}</div>
                          ))}
                        </div>
                      </div>
                    )}
                    {(audit.photo_shots_missing || []).length > 0 && (
                      <div className="mt-3 rounded-xl border border-amber-200 bg-amber-50/60 p-4 text-sm text-slate-700">
                        <div className="font-semibold text-slate-900">Каких фото не хватает</div>
                        <div className="mt-2 space-y-1">
                          {(audit.photo_shots_missing || []).slice(0, 5).map((line, idx) => (
                            <div key={`photo-${idx}`}>• {line}</div>
                          ))}
                        </div>
                      </div>
                    )}
                    {((audit.strength_themes || []).length > 0 || (audit.objection_themes || []).length > 0) && (
                      <div className="mt-3 grid gap-3 md:grid-cols-2">
                        {(audit.strength_themes || []).length > 0 && (
                          <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                            <div className="font-semibold text-slate-900">Что уже работает</div>
                            <div className="mt-2 flex flex-wrap gap-2">
                              {(audit.strength_themes || []).slice(0, 6).map((line, idx) => (
                                <div key={`strength-${idx}`} className="rounded-full border border-emerald-200 bg-white px-3 py-1 text-xs text-slate-700">
                                  {line}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                        {(audit.objection_themes || []).length > 0 && (
                          <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                            <div className="font-semibold text-slate-900">Что нужно снять заранее</div>
                            <div className="mt-2 flex flex-wrap gap-2">
                              {(audit.objection_themes || []).slice(0, 6).map((line, idx) => (
                                <div key={`objection-${idx}`} className="rounded-full border border-rose-200 bg-white px-3 py-1 text-xs text-slate-700">
                                  {line}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
                <div className="mt-4 grid gap-3 sm:grid-cols-2">
                  <div className="rounded-xl border border-slate-200 bg-white p-3">
                    <div className="text-xs font-medium uppercase tracking-wide text-slate-500">Последний парсинг карточки</div>
                    <div className="mt-1 text-sm font-semibold text-slate-900">
                      {formatDate(audit.parse_context.last_parse_at)}
                    </div>
                    <div className="mt-1 text-xs text-slate-500">
                      Статус: {parseStatusLabel(audit.parse_context.last_parse_status)}
                    </div>
                    {audit.parse_context.no_new_services_found && (
                      <div className="mt-2 text-xs font-medium text-amber-700">
                        Парсинг обновил карточку, но новых услуг не найдено.
                      </div>
                    )}
                  </div>
                  <div className="rounded-xl border border-slate-200 bg-white p-3">
                    <div className="text-xs font-medium uppercase tracking-wide text-slate-500">База оценки</div>
                    <div className="mt-1 text-sm font-semibold text-slate-900">
                      {formatMoney(audit.revenue_potential.baseline_monthly_revenue.value)} / мес
                    </div>
                    <div className="mt-1 text-xs text-slate-500">
                      {revenueSourceLabel(audit.revenue_potential.baseline_monthly_revenue.source)}
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
                <div className="mt-4 rounded-xl border border-orange-100 bg-white/80 p-3">
                  <div className="text-xs uppercase tracking-wide text-slate-500">Уверенность</div>
                  <div className="mt-1 text-sm font-semibold text-slate-900">
                    {confidenceLabels[audit.revenue_potential.confidence] || 'Средняя'}
                  </div>
                  <div className="mt-2 text-xs leading-5 text-slate-500">
                    {audit.revenue_potential.disclaimer}
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
                  {(audit.issue_blocks || []).length === 0 && audit.findings.length === 0 ? (
                    <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">
                      Критичных проблем не найдено. Карточка выглядит стабильно.
                    </div>
                  ) : (audit.issue_blocks || []).length > 0 ? (
                    (audit.issue_blocks || []).map((issue, idx) => (
                      <div
                        key={`${issue.id || issue.title || 'issue'}-${idx}`}
                        className={`rounded-xl border p-4 ${severityClasses[(issue.priority || 'medium').toLowerCase()] || severityClasses.medium}`}
                      >
                        <div className="flex items-center justify-between gap-3">
                          <div className="text-sm font-semibold">{issue.title || 'Проблема карточки'}</div>
                          <div className={`rounded-full px-2 py-1 text-xs font-medium ${priorityClasses[(issue.priority || 'medium').toLowerCase()] || priorityClasses.medium}`}>
                            {String(issue.priority || 'medium').toUpperCase()}
                          </div>
                        </div>
                        <div className="mt-2 text-sm leading-6">
                          <span className="font-medium">Проблема:</span> {issue.problem || 'Не указана'}
                        </div>
                        <div className="mt-1 text-sm leading-6">
                          <span className="font-medium">Факт:</span> {issue.evidence || 'Нет данных'}
                        </div>
                        <div className="mt-1 text-sm leading-6">
                          <span className="font-medium">Влияние:</span> {issue.impact || 'Требуется проверка'}
                        </div>
                        <div className="mt-1 text-sm leading-6">
                          <span className="font-medium">Что сделать:</span> {issue.fix || 'Нет рекомендации'}
                        </div>
                      </div>
                    ))
                  ) : (
                    audit.findings.map((finding) => (
                      <div
                        key={finding.code}
                        className={`rounded-xl border p-4 ${severityClasses[finding.severity] || severityClasses.medium}`}
                      >
                        <div className="text-sm font-semibold">{finding.title}</div>
                        <div className="mt-1 text-sm leading-6">{finding.description}</div>
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
                  {audit.action_plan && (
                    <div className="rounded-xl border border-slate-200 p-4">
                      <div className="text-sm font-semibold text-slate-900">План действий</div>
                      <div className="mt-3 space-y-3 text-sm text-slate-700">
                        <div>
                          <div className="font-medium text-slate-900">За 24 часа</div>
                          <div className="mt-1 space-y-1">
                            {(audit.action_plan.next_24h || []).map((line, idx) => (
                              <div key={`d1-${idx}`}>• {line}</div>
                            ))}
                          </div>
                        </div>
                        <div>
                          <div className="font-medium text-slate-900">За 7 дней</div>
                          <div className="mt-1 space-y-1">
                            {(audit.action_plan.next_7d || []).map((line, idx) => (
                              <div key={`d7-${idx}`}>• {line}</div>
                            ))}
                          </div>
                        </div>
                        <div>
                          <div className="font-medium text-slate-900">Регулярно</div>
                          <div className="mt-1 space-y-1">
                            {(audit.action_plan.ongoing || []).map((line, idx) => (
                              <div key={`ongoing-${idx}`}>• {line}</div>
                            ))}
                          </div>
                        </div>
                      </div>
                    </div>
                  )}
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
                        <div className="mt-2 text-sm leading-6 text-slate-600">{action.description}</div>
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
                  <div className="mt-1 text-sm text-slate-600">С ценами: {audit.current_state.services_with_price_count}</div>
                  <div className="mt-1 text-sm text-slate-600">
                    Структура: {audit.current_state.services_count > 0 ? 'Есть базовое наполнение' : 'Не заполнено'}
                  </div>
                </div>
                <div className="rounded-xl bg-slate-50 p-4">
                  <div className="text-xs uppercase tracking-wide text-slate-500">Контент</div>
                  <div className="mt-2 flex items-center gap-2 text-sm font-semibold text-slate-900">
                    <Globe className="h-4 w-4" />
                    {audit.current_state.has_website ? 'Сайт указан' : 'Сайт не указан'}
                  </div>
                  <div className="mt-1 text-sm text-slate-600">Фото: {photosStateLabel(audit.current_state.photos_state)}</div>
                  <div className="mt-1 text-sm text-slate-600">
                    Активность: {audit.current_state.has_recent_activity ? 'Есть свежие обновления' : 'Карточка неактивна'}
                  </div>
                </div>
                <div className="rounded-xl bg-slate-50 p-4">
                  <div className="text-xs uppercase tracking-wide text-slate-500">Итог</div>
                  <div className="mt-2 text-sm font-semibold text-slate-900">{audit.health_label}</div>
                  <div className="mt-1 text-sm text-slate-600">Баланс факторов: {audit.summary_score}/100</div>
                  <div className="mt-1 text-sm text-slate-600">
                    Модель: deterministic audit v1
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
