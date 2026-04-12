import React, { useEffect, useState } from 'react';
import { AlertCircle, Camera, Globe, Loader2, MessageSquare, ReceiptText, Star, TrendingUp } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';

export type LeadPreviewLead = {
  id?: string;
  name?: string;
  category?: string;
  city?: string;
  address?: string;
  phone?: string;
  website?: string;
  email?: string;
  source?: string;
  source_url?: string;
  selected_channel?: string;
  telegram_url?: string;
  whatsapp_url?: string;
  email?: string;
  public_audit_url?: string;
};

export type LeadCardPreview = {
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
    photos_state: string;
  };
  parse_context: {
    last_parse_at?: string | null;
    last_parse_status?: string | null;
    last_parse_task_id?: string | null;
    last_parse_retry_after?: string | null;
    last_parse_error?: string | null;
    no_new_services_found: boolean;
  };
  services_preview?: Array<{
    current_name: string;
    suggested_name: string;
    note: string;
  }>;
  reviews_preview?: Array<{
    review: string;
    reply_preview: string;
  }>;
  news_preview?: Array<{
    title: string;
    body: string;
  }>;
  preview_meta?: {
    business_id?: string;
    has_phone?: boolean;
    has_email?: boolean;
    has_messenger?: boolean;
    source?: string;
    source_url?: string;
  };
};

interface LeadCardPreviewPanelProps {
  lead: LeadPreviewLead;
  preview: LeadCardPreview | null;
  loading?: boolean;
  error?: string | null;
  generateBusy?: boolean;
  generateAuditPageBusy?: boolean;
  generatedAuditPageUrl?: string | null;
  auditPageLanguage?: string;
  auditPageEnabledLanguages?: string[];
  contactsBusy?: boolean;
  parseBusy?: boolean;
  parseAutoRefreshing?: boolean;
  onGenerateFromAudit?: () => void;
  onGenerateAuditPage?: () => void;
  onAuditPageLanguageChange?: (language: string) => void;
  onAuditPageEnabledLanguagesChange?: (languages: string[]) => void;
  onSaveContacts?: (payload: { telegram_url: string; whatsapp_url: string; email: string }) => void;
  onRunLiveParse?: () => void;
  onRefreshPreview?: () => void;
  onClose: () => void;
}

const healthClasses: Record<string, string> = {
  strong: 'bg-emerald-100 text-emerald-800 border-emerald-200',
  growth: 'bg-amber-100 text-amber-800 border-amber-200',
  risk: 'bg-red-100 text-red-800 border-red-200',
};

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

const catalogSectionTitle = (auditProfile?: string) => {
  switch (String(auditProfile || '').trim()) {
    case 'food':
      return 'Меню и позиции в карточке';
    case 'fitness':
      return 'Направления и абонементы';
    case 'medical':
      return 'Услуги и медицинские направления';
    case 'wellness':
      return 'Услуги и процедуры';
    case 'beauty':
      return 'Услуги и beauty-направления';
    case 'hospitality':
      return 'Что видно в карточке';
    default:
      return 'Услуги: что есть и что улучшить';
  }
};

const subscoreCards = [
  { key: 'profile', label: 'Заполнение карточки', icon: ReceiptText },
  { key: 'reputation', label: 'Репутация', icon: Star },
  { key: 'services', label: 'Услуги', icon: TrendingUp },
  { key: 'activity', label: 'Активность', icon: Camera },
] as const;

const formatMoney = (value: number) =>
  `${new Intl.NumberFormat('ru-RU').format(Math.round(value))} ₽`;

const formatDate = (value?: string | null) =>
  value ? new Date(value).toLocaleString('ru-RU') : '—';

const sourceLabel = (value?: string) => {
  switch (value) {
    case 'external_import':
      return 'Внешний импорт';
    case 'apify_yandex':
      return 'Apify Yandex';
    case 'apify_2gis':
      return 'Apify 2GIS';
    case 'apify_google':
      return 'Apify Google';
    case 'apify_apple':
      return 'Apify Apple';
    case 'openclaw':
      return 'OpenClaw';
    case 'manual':
      return 'Ручной ввод';
    default:
      return value || 'Источник не указан';
  }
};

const auditLanguageOptions = [
  { value: 'en', label: 'English' },
  { value: 'tr', label: 'Türkçe' },
  { value: 'ru', label: 'Русский' },
  { value: 'el', label: 'Ελληνικά' },
];

const LeadCardPreviewPanel: React.FC<LeadCardPreviewPanelProps> = ({
  lead,
  preview,
  loading,
  error,
  generateBusy = false,
  generateAuditPageBusy = false,
  generatedAuditPageUrl = null,
  auditPageLanguage = 'en',
  auditPageEnabledLanguages = ['en'],
  contactsBusy = false,
  parseBusy = false,
  parseAutoRefreshing = false,
  onGenerateFromAudit,
  onGenerateAuditPage,
  onAuditPageLanguageChange,
  onAuditPageEnabledLanguagesChange,
  onSaveContacts,
  onRunLiveParse,
  onRefreshPreview,
  onClose,
}) => {
  const [telegramUrl, setTelegramUrl] = useState('');
  const [whatsappUrl, setWhatsappUrl] = useState('');
  const [email, setEmail] = useState('');

  useEffect(() => {
    setTelegramUrl(String(lead.telegram_url || ''));
    setWhatsappUrl(String(lead.whatsapp_url || ''));
    setEmail(String(lead.email || ''));
  }, [lead.id, lead.telegram_url, lead.whatsapp_url, lead.email]);

  const parseStatus = (preview?.parse_context?.last_parse_status || 'lead_preview').toLowerCase();
  const parseStatusLabel = () => {
    switch (parseStatus) {
      case 'lead_preview':
      case 'preview':
        return 'Превью (без парсинга)';
      case 'pending':
      case 'queued':
        return 'В очереди';
      case 'processing':
      case 'running':
        return 'Идёт парсинг';
      case 'captcha':
        return 'Требуется капча';
      case 'completed':
      case 'done':
        return 'Завершён';
      case 'error':
      case 'failed':
        return 'Ошибка';
      default:
        return preview?.parse_context?.last_parse_status || 'lead_preview';
    }
  };
  const parseStatusBadgeClass = () => {
    if (['pending', 'queued', 'processing', 'running'].includes(parseStatus)) {
      return 'border-blue-200 bg-blue-50 text-blue-700';
    }
    if (parseStatus === 'captcha') {
      return 'border-amber-200 bg-amber-50 text-amber-700';
    }
    if (['error', 'failed'].includes(parseStatus)) {
      return 'border-red-200 bg-red-50 text-red-700';
    }
    return 'border-emerald-200 bg-emerald-50 text-emerald-700';
  };

  const parseInProgress = ['pending', 'queued', 'processing', 'running'].includes(parseStatus);
  const showInlineAudit = false;

  return (
    <Card>
      <CardHeader>
        <div className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_auto] xl:items-start">
          <div className="min-w-0">
            <CardTitle>Карточка лида</CardTitle>
            <CardDescription className="mt-1 max-w-3xl break-words leading-6">
              Управление лидом: статус, контакты, запуск парсинга и генерация публичной страницы аудита.
            </CardDescription>
          </div>
          <div className="min-w-0 w-full xl:w-auto">
            <div className="flex flex-wrap items-center gap-2 xl:justify-end">
            {onGenerateFromAudit && (
              <Button
                size="sm"
                onClick={onGenerateFromAudit}
                disabled={loading || generateBusy}
              >
                {generateBusy && <Loader2 className="mr-2 h-3 w-3 animate-spin" />}
                Сгенерировать письмо из аудита
              </Button>
            )}
            {onGenerateAuditPage && (
              <>
                <div className="rounded-md border border-slate-200 bg-white px-3 py-2 text-xs text-slate-600">
                  <div className="flex items-center gap-2">
                    <span>Основной язык</span>
                    <select
                      className="bg-transparent text-sm font-medium text-slate-900 outline-none"
                      value={auditPageLanguage}
                      onChange={(e) => {
                        const nextLanguage = e.target.value;
                        if (onAuditPageLanguageChange) {
                          onAuditPageLanguageChange(nextLanguage);
                        }
                        if (onAuditPageEnabledLanguagesChange) {
                          const nextLanguages = auditPageEnabledLanguages.filter((item) => item !== nextLanguage);
                          onAuditPageEnabledLanguagesChange([nextLanguage, ...nextLanguages]);
                        }
                      }}
                      disabled={loading || generateAuditPageBusy}
                    >
                      {auditLanguageOptions.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {auditLanguageOptions.map((option) => {
                      const checked = auditPageEnabledLanguages.includes(option.value);
                      const disabled = option.value === auditPageLanguage;
                      return (
                        <label key={option.value} className="inline-flex items-center gap-2 rounded-full border border-slate-200 px-2.5 py-1 text-xs text-slate-700">
                          <input
                            type="checkbox"
                            checked={checked}
                            disabled={disabled || loading || generateAuditPageBusy}
                            onChange={(e) => {
                              if (!onAuditPageEnabledLanguagesChange) {
                                return;
                              }
                              if (e.target.checked) {
                                onAuditPageEnabledLanguagesChange([...auditPageEnabledLanguages, option.value].filter((item, index, items) => items.indexOf(item) === index));
                                return;
                              }
                              onAuditPageEnabledLanguagesChange(auditPageEnabledLanguages.filter((item) => item !== option.value));
                            }}
                          />
                          <span>{option.label}</span>
                        </label>
                      );
                    })}
                  </div>
                  <div className="mt-2 text-[11px] leading-5 text-slate-500">
                    Будут созданы только выбранные языковые версии аудита.
                  </div>
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={onGenerateAuditPage}
                  disabled={loading || generateAuditPageBusy}
                >
                  {generateAuditPageBusy && <Loader2 className="mr-2 h-3 w-3 animate-spin" />}
                  {generatedAuditPageUrl ? 'Пересоздать страницу аудита' : 'Сгенерировать страницу аудита'}
                </Button>
              </>
            )}
            {onRunLiveParse && (
              <Button
                variant="outline"
                size="sm"
                onClick={onRunLiveParse}
                disabled={loading || parseBusy}
              >
                {parseBusy && <Loader2 className="mr-2 h-3 w-3 animate-spin" />}
                Запустить парсинг карточки
              </Button>
            )}
            {onRefreshPreview && (
              <Button
                variant="outline"
                size="sm"
                onClick={onRefreshPreview}
                disabled={loading || parseBusy || parseAutoRefreshing}
              >
                {(parseAutoRefreshing || parseBusy) && <Loader2 className="mr-2 h-3 w-3 animate-spin" />}
                Обновить статус
              </Button>
            )}
            <Button variant="outline" size="sm" onClick={onClose}>
              Закрыть
            </Button>
            </div>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="text-lg font-semibold text-slate-900">{lead.name || 'Лид'}</div>
              <div className="mt-1 text-sm text-slate-500">
                {[lead.category, lead.city].filter(Boolean).join(' • ') || 'Категория или город не указаны'}
              </div>
              {lead.address && <div className="mt-2 text-sm text-slate-700">{lead.address}</div>}
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="outline">{sourceLabel(lead.source)}</Badge>
              {lead.selected_channel && <Badge variant="secondary">Канал: {lead.selected_channel}</Badge>}
              {(lead.public_audit_url || generatedAuditPageUrl) && (
                <a
                  href={lead.public_audit_url || generatedAuditPageUrl || '#'}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700"
                >
                  <Globe className="h-3 w-3" />
                  Открыть страницу аудита
                </a>
              )}
              {(lead.source_url || preview?.preview_meta?.source_url) && (
                <a
                  href={lead.source_url || preview?.preview_meta?.source_url || '#'}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 rounded-md border px-3 py-1 text-xs font-medium text-blue-600"
                >
                  <Globe className="h-3 w-3" />
                  Открыть в Яндекс Картах
                </a>
              )}
            </div>
          </div>
        </div>

        {loading && (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {Array.from({ length: 4 }).map((_, idx) => (
              <div key={idx} className="h-28 rounded-xl bg-gray-100 animate-pulse" />
            ))}
          </div>
        )}

        {!loading && error && (
          <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            Не удалось загрузить карточку лида: {error}
          </div>
        )}

        {!loading && !error && preview && (
          <>
            <div className="rounded-2xl border border-slate-200 bg-white p-5">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <div className="text-sm font-medium text-slate-500">Краткий статус</div>
                  <div className="mt-2 text-2xl font-semibold text-slate-900">{preview.health_label}</div>
                  <div className="mt-1 text-sm text-slate-600">{preview.summary_text}</div>
                </div>
                <div className="flex flex-col gap-2 text-sm text-slate-700">
                  <div>Рейтинг: {preview.current_state.rating ?? '—'}</div>
                  <div>Отзывы: {preview.current_state.reviews_count ?? 0}</div>
                  <div>Услуги: {preview.current_state.services_count ?? 0}</div>
                  <div>Фото: {preview.current_state.photos_state || '—'}</div>
                </div>
                <div className="flex flex-col gap-2 text-xs text-slate-600">
                  <div>Последний расчёт: {formatDate(preview.parse_context.last_parse_at || null)}</div>
                  <div className={`inline-flex items-center rounded-md border px-2 py-1 font-semibold ${parseStatusBadgeClass()}`}>
                    {(parseInProgress || parseAutoRefreshing) && <Loader2 className="mr-1 h-3 w-3 animate-spin" />}
                    {parseStatusLabel()}
                  </div>
                </div>
              </div>
              <div className="mt-3 text-xs text-slate-500">
                Детальный аудит формируется на отдельной странице и доступен по ссылке «Открыть страницу аудита».
              </div>
            </div>

            {showInlineAudit && (
            <div className="grid gap-4 xl:grid-cols-[1.4fr_1fr]">
              <div className="rounded-2xl border border-slate-200 bg-gradient-to-br from-white to-slate-50 p-5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="text-sm font-medium text-slate-500">Итоговая оценка</div>
                    <div className="mt-2 text-5xl font-bold tracking-tight text-slate-900">
                      {preview.summary_score}
                    </div>
                  </div>
                  <div className={`rounded-full border px-3 py-1 text-sm font-semibold ${healthClasses[preview.health_level] || healthClasses.growth}`}>
                    {preview.health_label}
                  </div>
                </div>
                <p className="mt-4 text-sm leading-6 text-slate-700">{preview.summary_text}</p>
                <div className="mt-4 grid gap-3 sm:grid-cols-2">
                  <div className="rounded-xl border border-slate-200 bg-white p-3">
                    <div className="text-xs font-medium uppercase tracking-wide text-slate-500">Последний расчёт</div>
                    <div className="mt-1 text-sm font-semibold text-slate-900">
                      {formatDate(preview.parse_context.last_parse_at || null)}
                    </div>
                    <div className="mt-1 text-xs text-slate-500">
                      Статус очереди:
                    </div>
                    <div className={`mt-2 inline-flex items-center rounded-md border px-2 py-1 text-xs font-semibold ${parseStatusBadgeClass()}`}>
                      {(parseInProgress || parseAutoRefreshing) && <Loader2 className="mr-1 h-3 w-3 animate-spin" />}
                      {parseStatusLabel()}
                    </div>
                    {preview.parse_context.last_parse_task_id && (
                      <div className="mt-2 text-xs text-slate-500">
                        task_id: <span className="font-mono">{preview.parse_context.last_parse_task_id}</span>
                      </div>
                    )}
                    {preview.parse_context.last_parse_retry_after && (
                      <div className="mt-1 text-xs text-slate-500">
                        retry_after: {formatDate(preview.parse_context.last_parse_retry_after)}
                      </div>
                    )}
                    {preview.parse_context.last_parse_error && (
                      <div className="mt-2 text-xs text-red-700">
                        Ошибка: {preview.parse_context.last_parse_error}
                      </div>
                    )}
                    {(parseInProgress || parseAutoRefreshing) && (
                      <div className="mt-2 text-xs text-blue-700">
                        Автообновление включено до завершения парсинга.
                      </div>
                    )}
                    {preview.parse_context.no_new_services_found && (
                      <div className="mt-2 text-xs font-medium text-amber-700">
                        Услуги в карточке не найдены или заполнены слабо.
                      </div>
                    )}
                    {['lead_preview', 'preview'].includes(parseStatus) && (
                      <div className="mt-2 text-xs font-medium text-slate-600">
                        Парсинг ещё не запускался. Нажмите «Запустить парсинг карточки», чтобы подтянуть фактические услуги.
                      </div>
                    )}
                  </div>
                  <div className="rounded-xl border border-slate-200 bg-white p-3">
                    <div className="text-xs font-medium uppercase tracking-wide text-slate-500">Оценочный потенциал</div>
                    <div className="mt-1 text-sm font-semibold text-slate-900">
                      {formatMoney(preview.revenue_potential.total_min)} – {formatMoney(preview.revenue_potential.total_max)} / мес
                    </div>
                    <div className="mt-1 text-xs text-slate-500">
                      База: {formatMoney(preview.revenue_potential.baseline_monthly_revenue.value)} / мес
                    </div>
                  </div>
                </div>
              </div>

              <div className="rounded-2xl border border-slate-200 bg-slate-950 p-5 text-white">
                <div className="text-xs font-medium uppercase tracking-wide text-slate-400">Потенциал выручки</div>
                <div className="mt-3 text-4xl font-bold tracking-tight">
                  {formatMoney(preview.revenue_potential.total_min)} – {formatMoney(preview.revenue_potential.total_max)}
                </div>
                <p className="mt-3 text-sm leading-6 text-slate-300">{preview.revenue_potential.disclaimer}</p>
                <div className="mt-4 space-y-2 text-sm">
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-slate-300">Из-за рейтинга</span>
                    <span className="font-semibold">{formatMoney(preview.revenue_potential.rating_gap.min)} – {formatMoney(preview.revenue_potential.rating_gap.max)}</span>
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-slate-300">Из-за наполнения</span>
                    <span className="font-semibold">{formatMoney(preview.revenue_potential.content_gap.min)} – {formatMoney(preview.revenue_potential.content_gap.max)}</span>
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-slate-300">Из-за услуг</span>
                    <span className="font-semibold">{formatMoney(preview.revenue_potential.service_gap.min)} – {formatMoney(preview.revenue_potential.service_gap.max)}</span>
                  </div>
                </div>
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              {subscoreCards.map((item) => {
                const Icon = item.icon;
                const value = preview.subscores[item.key];
                return (
                  <div key={item.key} className="rounded-2xl border border-slate-200 bg-white p-4">
                    <div className="flex items-center gap-2 text-sm font-medium text-slate-500">
                      <Icon className="h-4 w-4" />
                      {item.label}
                    </div>
                    <div className="mt-3 text-3xl font-semibold text-slate-900">{value}</div>
                    <div className="mt-2 h-2 rounded-full bg-slate-100">
                      <div className="h-2 rounded-full bg-slate-900" style={{ width: `${Math.max(6, Math.min(100, value))}%` }} />
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
              <div className="space-y-4">
                <div className="rounded-2xl border border-slate-200 bg-white p-5">
                  <div className="mb-4 flex items-center gap-2 text-base font-semibold text-slate-900">
                    <AlertCircle className="h-5 w-5 text-amber-500" />
                    Ключевые точки роста
                  </div>
                  <div className="space-y-3">
                    {(preview.issue_blocks || []).length === 0 && preview.findings.length === 0 && (
                      <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">
                        Критичных проблем не найдено. Карточка выглядит стабильно.
                      </div>
                    )}
                    {(preview.issue_blocks || []).length > 0
                      ? (preview.issue_blocks || []).map((issue, idx) => (
                          <div key={`${issue.id || issue.title || 'issue'}-${idx}`} className={`rounded-xl border p-4 ${severityClasses[(issue.priority || 'medium').toLowerCase()] || severityClasses.low}`}>
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <div className="font-semibold">{issue.title || 'Проблема карточки'}</div>
                              <Badge variant="outline" className="border-current/30 bg-white/60">
                                {(issue.priority || 'medium').toString().toUpperCase()}
                              </Badge>
                            </div>
                            <p className="mt-2 text-sm leading-6"><span className="font-medium">Проблема:</span> {issue.problem || 'Не указана'}</p>
                            {issue.evidence ? <p className="mt-1 text-sm leading-6"><span className="font-medium">Факт:</span> {issue.evidence}</p> : null}
                            {issue.impact ? <p className="mt-1 text-sm leading-6"><span className="font-medium">Влияние:</span> {issue.impact}</p> : null}
                            {issue.fix ? <p className="mt-1 text-sm leading-6"><span className="font-medium">Что сделать:</span> {issue.fix}</p> : null}
                          </div>
                        ))
                      : preview.findings.map((finding) => (
                          <div key={finding.code} className={`rounded-xl border p-4 ${severityClasses[finding.severity] || severityClasses.low}`}>
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <div className="font-semibold">{finding.title}</div>
                              <Badge variant="outline" className="border-current/30 bg-white/60">
                                {finding.severity}
                              </Badge>
                            </div>
                            <p className="mt-2 text-sm leading-6">{finding.description}</p>
                          </div>
                        ))}
                  </div>
                </div>

                <div className="rounded-2xl border border-slate-200 bg-white p-5">
                  <div className="mb-4 flex items-center gap-2 text-base font-semibold text-slate-900">
                    <MessageSquare className="h-5 w-5 text-blue-500" />
                    Что сделать дальше
                  </div>
                  <div className="space-y-3">
                    {preview.action_plan && (
                      <div className="rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-700">
                        <div className="font-semibold text-slate-900">План действий</div>
                        <div className="mt-2">
                          <div className="font-medium text-slate-900">За 24 часа</div>
                          {(preview.action_plan.next_24h || []).slice(0, 3).map((line, idx) => <div key={`d1-${idx}`}>• {line}</div>)}
                        </div>
                        <div className="mt-2">
                          <div className="font-medium text-slate-900">За 7 дней</div>
                          {(preview.action_plan.next_7d || []).slice(0, 3).map((line, idx) => <div key={`d7-${idx}`}>• {line}</div>)}
                        </div>
                        <div className="mt-2">
                          <div className="font-medium text-slate-900">Регулярно</div>
                          {(preview.action_plan.ongoing || []).slice(0, 3).map((line, idx) => <div key={`og-${idx}`}>• {line}</div>)}
                        </div>
                      </div>
                    )}
                    {preview.recommended_actions.map((action, idx) => (
                      <div key={`${action.title}-${idx}`} className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div className="font-semibold text-slate-900">{action.title}</div>
                          <Badge className={priorityClasses[action.priority] || priorityClasses.low}>
                            {action.priority}
                          </Badge>
                        </div>
                        <p className="mt-2 text-sm leading-6 text-slate-700">{action.description}</p>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              <div className="space-y-4">
                <div className="rounded-2xl border border-slate-200 bg-white p-5">
                  <div className="mb-4 text-base font-semibold text-slate-900">Текущее состояние</div>
                  <div className="space-y-3 text-sm">
                    <div className="flex items-center justify-between gap-3 rounded-xl border border-slate-100 p-3">
                      <span className="text-slate-500">Рейтинг</span>
                      <span className="font-semibold text-slate-900">
                        {preview.current_state.rating ?? '—'} / 5
                      </span>
                    </div>
                    <div className="flex items-center justify-between gap-3 rounded-xl border border-slate-100 p-3">
                      <span className="text-slate-500">Отзывы</span>
                      <span className="font-semibold text-slate-900">{preview.current_state.reviews_count}</span>
                    </div>
                    <div className="flex items-center justify-between gap-3 rounded-xl border border-slate-100 p-3">
                      <span className="text-slate-500">Без ответа</span>
                      <span className="font-semibold text-slate-900">{preview.current_state.unanswered_reviews_count}</span>
                    </div>
                    <div className="flex items-center justify-between gap-3 rounded-xl border border-slate-100 p-3">
                      <span className="text-slate-500">Услуги</span>
                      <span className="font-semibold text-slate-900">{preview.current_state.services_count}</span>
                    </div>
                    <div className="flex items-center justify-between gap-3 rounded-xl border border-slate-100 p-3">
                      <span className="text-slate-500">Услуги с ценой</span>
                      <span className="font-semibold text-slate-900">{preview.current_state.services_with_price_count}</span>
                    </div>
                    <div className="flex items-center justify-between gap-3 rounded-xl border border-slate-100 p-3">
                      <span className="text-slate-500">Сайт</span>
                      <span className="font-semibold text-slate-900">{preview.current_state.has_website ? 'Есть' : 'Нет'}</span>
                    </div>
                    <div className="flex items-center justify-between gap-3 rounded-xl border border-slate-100 p-3">
                      <span className="text-slate-500">Активность</span>
                      <span className="font-semibold text-slate-900">{preview.current_state.has_recent_activity ? 'Есть' : 'Низкая'}</span>
                    </div>
                  </div>
                </div>

                {(
                  (preview.best_fit_customer_profile && preview.best_fit_customer_profile.length > 0) ||
                  (preview.best_fit_guest_profile && preview.best_fit_guest_profile.length > 0) ||
                  (preview.weak_fit_customer_profile && preview.weak_fit_customer_profile.length > 0) ||
                  (preview.weak_fit_guest_profile && preview.weak_fit_guest_profile.length > 0) ||
                  (preview.search_intents_to_target && preview.search_intents_to_target.length > 0) ||
                  (preview.photo_shots_missing && preview.photo_shots_missing.length > 0) ||
                  (preview.positioning_focus && preview.positioning_focus.length > 0) ||
                  (preview.strength_themes && preview.strength_themes.length > 0) ||
                  (preview.objection_themes && preview.objection_themes.length > 0)
                ) && (
                  <div className="rounded-2xl border border-slate-200 bg-white p-5">
                    <div className="mb-4 flex items-center justify-between gap-3">
                      <div className="text-base font-semibold text-slate-900">Позиционирование и сценарии поиска</div>
                      {preview.audit_profile_label ? (
                        <Badge variant="outline" className="border-slate-200 bg-slate-50 text-slate-700">
                          {preview.audit_profile_label}
                        </Badge>
                      ) : null}
                    </div>
                    <div className="space-y-4 text-sm">
                      {(preview.positioning_focus && preview.positioning_focus.length > 0) && (
                        <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                          <div className="font-semibold text-slate-900">Как лучше перепаковать карточку</div>
                          <div className="mt-2 space-y-2 text-slate-700">
                            {preview.positioning_focus.slice(0, 4).map((line, idx) => <div key={`position-${idx}`}>• {line}</div>)}
                          </div>
                        </div>
                      )}
                      {((preview.best_fit_customer_profile && preview.best_fit_customer_profile.length > 0)
                        || (preview.best_fit_guest_profile && preview.best_fit_guest_profile.length > 0)) && (
                        <div className="rounded-xl border border-emerald-200 bg-emerald-50/60 p-4">
                          <div className="font-semibold text-slate-900">Кому карточка подходит лучше всего</div>
                          <div className="mt-2 space-y-2 text-slate-700">
                            {((preview.best_fit_customer_profile && preview.best_fit_customer_profile.length > 0)
                              ? preview.best_fit_customer_profile
                              : preview.best_fit_guest_profile || []).map((line, idx) => <div key={`fit-${idx}`}>• {line}</div>)}
                          </div>
                        </div>
                      )}
                      {((preview.weak_fit_customer_profile && preview.weak_fit_customer_profile.length > 0)
                        || (preview.weak_fit_guest_profile && preview.weak_fit_guest_profile.length > 0)) && (
                        <div className="rounded-xl border border-rose-200 bg-rose-50/60 p-4">
                          <div className="font-semibold text-slate-900">Где ожидания чаще всего расходятся</div>
                          <div className="mt-2 space-y-2 text-slate-700">
                            {((preview.weak_fit_customer_profile && preview.weak_fit_customer_profile.length > 0)
                              ? preview.weak_fit_customer_profile
                              : preview.weak_fit_guest_profile || []).map((line, idx) => <div key={`weak-${idx}`}>• {line}</div>)}
                          </div>
                        </div>
                      )}
                      {(preview.search_intents_to_target && preview.search_intents_to_target.length > 0) && (
                        <div className="rounded-xl border border-sky-200 bg-sky-50/60 p-4">
                          <div className="font-semibold text-slate-900">Какие сценарии поиска надо закрыть</div>
                          <div className="mt-2 flex flex-wrap gap-2">
                            {preview.search_intents_to_target.map((line, idx) => (
                              <div key={`intent-${idx}`} className="rounded-full border border-sky-200 bg-white px-3 py-1 text-xs text-slate-700">
                                {line}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                      {(preview.photo_shots_missing && preview.photo_shots_missing.length > 0) && (
                        <div className="rounded-xl border border-amber-200 bg-amber-50/60 p-4">
                          <div className="font-semibold text-slate-900">Каких фото обычно не хватает</div>
                          <div className="mt-2 space-y-2 text-slate-700">
                            {preview.photo_shots_missing.map((line, idx) => <div key={`photo-${idx}`}>• {line}</div>)}
                          </div>
                        </div>
                      )}
                      {(preview.strength_themes && preview.strength_themes.length > 0) && (
                        <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                          <div className="font-semibold text-slate-900">Что уже работает</div>
                          <div className="mt-2 flex flex-wrap gap-2">
                            {preview.strength_themes.map((line, idx) => (
                              <div key={`strength-${idx}`} className="rounded-full border border-emerald-200 bg-white px-3 py-1 text-xs text-slate-700">
                                {line}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                      {(preview.objection_themes && preview.objection_themes.length > 0) && (
                        <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                          <div className="font-semibold text-slate-900">Какие возражения надо снять заранее</div>
                          <div className="mt-2 flex flex-wrap gap-2">
                            {preview.objection_themes.map((line, idx) => (
                              <div key={`objection-${idx}`} className="rounded-full border border-rose-200 bg-white px-3 py-1 text-xs text-slate-700">
                                {line}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            </div>

            <div className="grid gap-6 xl:grid-cols-3">
              <div className="rounded-2xl border border-slate-200 bg-white p-5">
                <div className="mb-4 flex items-center gap-2 text-base font-semibold text-slate-900">
                  <TrendingUp className="h-5 w-5 text-violet-500" />
                  {catalogSectionTitle(preview.audit_profile)}
                </div>
                <div className="space-y-3">
                  {(preview.services_preview || []).map((item, idx) => (
                    <div key={`${item.suggested_name}-${idx}`} className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                      <div className="text-xs font-medium uppercase tracking-wide text-slate-500">Сейчас</div>
                      <div className="mt-1 text-sm font-medium text-slate-700">{item.current_name}</div>
                      <div className="mt-3 text-xs font-medium uppercase tracking-wide text-slate-500">Можно показать так</div>
                      <div className="mt-1 text-sm font-semibold text-slate-900">{item.suggested_name}</div>
                      <p className="mt-2 text-xs leading-5 text-slate-600">{item.note}</p>
                    </div>
                  ))}
                  {(!preview.services_preview || preview.services_preview.length === 0) && (
                    <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
                      Услуги не заполнены или недоступны. Это одна из главных точек роста карточки.
                    </div>
                  )}
                </div>
              </div>

              <div className="rounded-2xl border border-slate-200 bg-white p-5">
                <div className="mb-4 flex items-center gap-2 text-base font-semibold text-slate-900">
                  <MessageSquare className="h-5 w-5 text-emerald-500" />
                  Отзывы и пример ответа
                </div>
                <div className="space-y-3">
                  {(preview.reviews_preview || []).map((item, idx) => (
                    <div key={`${item.review}-${idx}`} className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                      <div className="text-xs font-medium uppercase tracking-wide text-slate-500">Пример отзыва</div>
                      <p className="mt-1 text-sm leading-6 text-slate-800">{item.review}</p>
                      <div className="mt-3 text-xs font-medium uppercase tracking-wide text-slate-500">Как можно ответить</div>
                      <p className="mt-1 text-sm leading-6 text-slate-700">{item.reply_preview}</p>
                    </div>
                  ))}
                  {(!preview.reviews_preview || preview.reviews_preview.length === 0) && (
                    <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
                      Отзывы пока не подготовлены для превью.
                    </div>
                  )}
                </div>
              </div>

              <div className="rounded-2xl border border-slate-200 bg-white p-5">
                <div className="mb-4 flex items-center gap-2 text-base font-semibold text-slate-900">
                  <ReceiptText className="h-5 w-5 text-orange-500" />
                  Примеры новостей
                </div>
                <div className="space-y-3">
                  {(preview.news_preview || []).map((item, idx) => (
                    <div key={`${item.title}-${idx}`} className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                      <div className="text-sm font-semibold text-slate-900">{item.title}</div>
                      <p className="mt-2 text-sm leading-6 text-slate-700">{item.body}</p>
                    </div>
                  ))}
                  {(!preview.news_preview || preview.news_preview.length === 0) && (
                    <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
                      Для этой карточки пока нет подготовленных примеров новостей.
                    </div>
                  )}
                  </div>
                </div>
              </div>

            </div>
            )}

            <div className="rounded-2xl border border-slate-200 bg-white p-5">
              <div className="mb-3 text-base font-semibold text-slate-900">Контакты лида (ручное заполнение)</div>
              <div className="grid gap-3 md:grid-cols-3">
                <input
                  className="h-10 rounded-md border px-3 text-sm"
                  placeholder="Telegram URL, например https://t.me/..."
                  value={telegramUrl}
                  onChange={(e) => setTelegramUrl(e.target.value)}
                />
                <input
                  className="h-10 rounded-md border px-3 text-sm"
                  placeholder="WhatsApp URL, например https://wa.me/..."
                  value={whatsappUrl}
                  onChange={(e) => setWhatsappUrl(e.target.value)}
                />
                <input
                  className="h-10 rounded-md border px-3 text-sm"
                  placeholder="Email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>
              {onSaveContacts && (
                <div className="mt-3 flex justify-end">
                  <Button
                    variant="outline"
                    onClick={() => onSaveContacts({ telegram_url: telegramUrl, whatsapp_url: whatsappUrl, email })}
                    disabled={contactsBusy}
                  >
                    {contactsBusy && <Loader2 className="mr-2 h-3 w-3 animate-spin" />}
                    Сохранить контакты
                  </Button>
                </div>
              )}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
};

export default LeadCardPreviewPanel;
