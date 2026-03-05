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
  contactsBusy?: boolean;
  parseBusy?: boolean;
  onGenerateFromAudit?: () => void;
  onSaveContacts?: (payload: { telegram_url: string; whatsapp_url: string; email: string }) => void;
  onRunLiveParse?: () => void;
  onClose: () => void;
}

const healthClasses: Record<string, string> = {
  strong: 'bg-emerald-100 text-emerald-800 border-emerald-200',
  growth: 'bg-amber-100 text-amber-800 border-amber-200',
  risk: 'bg-red-100 text-red-800 border-red-200',
};

const severityClasses: Record<string, string> = {
  high: 'border-orange-200 bg-orange-50 text-orange-800',
  medium: 'border-amber-200 bg-amber-50 text-amber-800',
  low: 'border-slate-200 bg-slate-50 text-slate-800',
};

const priorityClasses: Record<string, string> = {
  high: 'bg-red-100 text-red-800',
  medium: 'bg-amber-100 text-amber-800',
  low: 'bg-slate-100 text-slate-700',
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
    case 'openclaw':
      return 'OpenClaw';
    case 'manual':
      return 'Ручной ввод';
    default:
      return value || 'Источник не указан';
  }
};

const LeadCardPreviewPanel: React.FC<LeadCardPreviewPanelProps> = ({
  lead,
  preview,
  loading,
  error,
  generateBusy = false,
  contactsBusy = false,
  parseBusy = false,
  onGenerateFromAudit,
  onSaveContacts,
  onRunLiveParse,
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

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div>
            <CardTitle>Аудит карточки лида</CardTitle>
            <CardDescription>
              Демо-экран для разговора: текущее состояние карточки, потенциал роста и конкретные точки улучшения.
            </CardDescription>
          </div>
          <div className="flex items-center gap-2">
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
            <Button variant="outline" size="sm" onClick={onClose}>
              Закрыть
            </Button>
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
            Не удалось загрузить демо-аудит: {error}
          </div>
        )}

        {!loading && !error && preview && (
          <>
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
                      Статус: {preview.parse_context.last_parse_status || 'lead_preview'}
                    </div>
                    {preview.parse_context.no_new_services_found && (
                      <div className="mt-2 text-xs font-medium text-amber-700">
                        Услуги в карточке не найдены или заполнены слабо.
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
                    {preview.findings.length === 0 && (
                      <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">
                        Критичных проблем не найдено. Карточка выглядит стабильно.
                      </div>
                    )}
                    {preview.findings.map((finding) => (
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
              </div>
            </div>

            <div className="grid gap-6 xl:grid-cols-3">
              <div className="rounded-2xl border border-slate-200 bg-white p-5">
                <div className="mb-4 flex items-center gap-2 text-base font-semibold text-slate-900">
                  <TrendingUp className="h-5 w-5 text-violet-500" />
                  Услуги: что есть и что улучшить
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
