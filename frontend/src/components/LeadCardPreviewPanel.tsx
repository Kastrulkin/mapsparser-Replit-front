import React, { useEffect, useState } from 'react';
import { Globe, Loader2, X } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ContactPresenceBadges, StatusSummaryCard, WorkflowActionRow } from '@/components/prospecting/LeadWorkflowBlocks';
import { LeadDetailMetaList, LeadDetailSection } from '@/components/prospecting/LeadDetailSections';
import AdminAuditEditorPanel from '@/components/AdminAuditEditorPanel';

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
  preferred_language?: string | null;
  enabled_languages?: string[] | null;
  groups?: Array<{
    id?: string;
    name?: string;
    status?: string;
    channel_hint?: string | null;
    city_hint?: string | null;
  }>;
  group_count?: number;
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
  generateAuditPageBusy?: boolean;
  generatedAuditPageUrl?: string | null;
  contactsBusy?: boolean;
  parseBusy?: boolean;
  parseAutoRefreshing?: boolean;
  onGenerateAuditPage?: () => void;
  onAuditEditorPublished?: () => void;
  onSaveContacts?: (payload: { telegram_url: string; whatsapp_url: string; email: string }) => void;
  onRunLiveParse?: () => void;
  onRefreshPreview?: () => void;
  onMoveToPostponed?: () => void;
  onMoveToNotRelevant?: () => void;
  onMarkManualContact?: () => void;
  onCreateLeadGroup?: () => void;
  onAddToExistingGroup?: () => void;
  onRemoveFromGroup?: (groupId: string) => void;
  onClose: () => void;
}

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

const buildAuditLanguageLinks = (
  baseUrl?: string | null,
  enabledLanguages?: string[] | null,
) => {
  const normalizedBase = String(baseUrl || '').trim();
  if (!normalizedBase) return [];
  const raw = Array.isArray(enabledLanguages) ? enabledLanguages : [];
  const normalized = raw
    .map((item) => String(item || '').trim().toLowerCase())
    .filter(Boolean);
  const languages = normalized.length > 0 ? normalized : ['en'];
  return languages.map((language) => {
    const url = new URL(normalizedBase, window.location.origin);
    url.searchParams.set('lang', language);
    return {
      language,
      href: url.toString(),
      label: language.toUpperCase(),
    };
  });
};

const LeadCardPreviewPanel: React.FC<LeadCardPreviewPanelProps> = ({
  lead,
  preview,
  loading,
  error,
  generateAuditPageBusy = false,
  generatedAuditPageUrl = null,
  contactsBusy = false,
  parseBusy = false,
  parseAutoRefreshing = false,
  onGenerateAuditPage,
  onAuditEditorPublished,
  onSaveContacts,
  onRunLiveParse,
  onRefreshPreview,
  onMoveToPostponed,
  onMoveToNotRelevant,
  onMarkManualContact,
  onCreateLeadGroup,
  onAddToExistingGroup,
  onRemoveFromGroup,
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
  const canonicalAuditUrl = String(lead.public_audit_url || generatedAuditPageUrl || '').trim();
  const auditLinks = buildAuditLanguageLinks(
    canonicalAuditUrl,
    lead.enabled_languages,
  );
  const auditPrimaryText = canonicalAuditUrl
    ? `Основной язык: ${(lead.preferred_language || auditLinks[0]?.language || 'en').toString().toUpperCase()}`
    : 'Страница аудита ещё не создана.';
  const auditSecondaryText = canonicalAuditUrl
    ? auditLinks.length > 1
      ? `Ещё ${auditLinks.length - 1} язык(а) доступно · обновлено ${formatDate(preview?.parse_context?.last_parse_at || null)}`
      : `Только 1 языковая версия · обновлено ${formatDate(preview?.parse_context?.last_parse_at || null)}`
    : 'Создайте аудит, чтобы получить публичную страницу и языковые версии.';

  const topActions: Parameters<typeof WorkflowActionRow>[0]['secondary'] = [];
  if (onGenerateAuditPage) {
    topActions.push({
      label: generatedAuditPageUrl ? 'Пересоздать страницу аудита' : 'Создать страницу аудита',
      onClick: onGenerateAuditPage,
      disabled: Boolean(loading || generateAuditPageBusy),
      icon: generateAuditPageBusy ? <Loader2 className="h-3 w-3 animate-spin" /> : undefined,
    });
  }
  if (onRunLiveParse) {
    topActions.push({
      label: 'Запустить парсинг карточки',
      onClick: onRunLiveParse,
      disabled: Boolean(loading || parseBusy),
      icon: parseBusy ? <Loader2 className="h-3 w-3 animate-spin" /> : undefined,
    });
  }
  if (onRefreshPreview) {
    topActions.push({
      label: 'Обновить статус',
      onClick: onRefreshPreview,
      disabled: Boolean(loading || parseBusy || parseAutoRefreshing),
      icon: parseAutoRefreshing || parseBusy ? <Loader2 className="h-3 w-3 animate-spin" /> : undefined,
    });
  }
  topActions.push({ label: 'Закрыть', onClick: onClose });
  const leadGroups = Array.isArray(lead.groups) ? lead.groups.filter((group) => group?.id) : [];

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
          <div className="min-w-0 flex-1">
            <CardTitle>Карточка лида</CardTitle>
            <CardDescription className="mt-1 max-w-3xl text-sm leading-6">
              Управление лидом: статус, контакты, запуск парсинга и генерация публичной страницы аудита.
            </CardDescription>
          </div>
          <div className="w-full xl:w-auto xl:max-w-[70%]">
            <WorkflowActionRow
              primary={{
                label: canonicalAuditUrl ? 'Открыть аудит' : 'Карточка лида',
                href: canonicalAuditUrl || undefined,
                onClick: canonicalAuditUrl ? undefined : onClose,
              }}
              secondary={topActions}
              className="w-full xl:justify-end"
            />
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        <LeadDetailSection title="Обзор лида">
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
            <div className="mt-3">
              <ContactPresenceBadges
                title="Каналы связи"
                website={lead.website}
                phone={lead.phone}
                email={lead.email}
                telegramUrl={lead.telegram_url}
                whatsappUrl={lead.whatsapp_url}
                hasMessenger={Boolean(lead.telegram_url || lead.whatsapp_url)}
              />
            </div>
            <LeadDetailMetaList
              columns={2}
              items={[
                { label: 'Телефон', value: lead.phone || '' },
                { label: 'Email', value: lead.email || '' },
                {
                  label: 'Telegram',
                  value: lead.telegram_url ? (
                    <a href={lead.telegram_url} target="_blank" rel="noreferrer" className="text-blue-600 underline">
                      {lead.telegram_url}
                    </a>
                  ) : '',
                },
                {
                  label: 'WhatsApp',
                  value: lead.whatsapp_url ? (
                    <a href={lead.whatsapp_url} target="_blank" rel="noreferrer" className="text-blue-600 underline">
                      {lead.whatsapp_url}
                    </a>
                  ) : '',
                },
                {
                  label: 'Сайт',
                  value: lead.website ? (
                    <a href={lead.website} target="_blank" rel="noreferrer" className="text-blue-600 underline">
                      {lead.website}
                    </a>
                  ) : '',
                },
              ]}
            />
        </LeadDetailSection>

        <LeadDetailSection title="Быстрые действия">
          <div className="flex flex-wrap gap-2">
            {canonicalAuditUrl ? (
              <Button asChild>
                <a href={canonicalAuditUrl} target="_blank" rel="noreferrer">
                  Открыть аудит
                </a>
              </Button>
            ) : null}
            {onMarkManualContact ? (
              <Button variant="outline" onClick={onMarkManualContact}>
                Отправлено вручную
              </Button>
            ) : null}
            {onMoveToPostponed ? (
              <Button variant="outline" onClick={onMoveToPostponed}>
                Отложить
              </Button>
            ) : null}
            {onMoveToNotRelevant ? (
              <Button variant="destructive" onClick={onMoveToNotRelevant}>
                Неактуален
              </Button>
            ) : null}
            {onCreateLeadGroup ? (
              <Button variant="outline" onClick={onCreateLeadGroup}>
                Новая группа
              </Button>
            ) : null}
            {onAddToExistingGroup ? (
              <Button variant="outline" onClick={onAddToExistingGroup}>
                Добавить в группу
              </Button>
            ) : null}
          </div>
          {leadGroups.length > 0 ? (
            <div className="mt-4 space-y-2">
              <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Состоит в группах
              </div>
              <div className="flex flex-wrap gap-2">
                {leadGroups.map((group) => (
                  <div
                    key={group.id}
                    className="inline-flex items-center gap-2 rounded-full border bg-muted/30 px-3 py-1.5 text-xs"
                  >
                    <span>{group.name || 'Группа без названия'}</span>
                    {group.id && onRemoveFromGroup ? (
                      <button
                        type="button"
                        onClick={() => onRemoveFromGroup(group.id || '')}
                        className="inline-flex h-4 w-4 items-center justify-center rounded-full text-muted-foreground transition hover:bg-background hover:text-foreground"
                        aria-label={`Удалить из группы ${group.name || ''}`}
                      >
                        <X className="h-3 w-3" />
                      </button>
                    ) : null}
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="mt-3 text-sm text-muted-foreground">
              Лид пока не добавлен ни в одну группу.
            </div>
          )}
        </LeadDetailSection>

        <StatusSummaryCard
          title="Аудит"
          statusLabel={canonicalAuditUrl ? 'Готов' : 'Не создан'}
          statusVariant={canonicalAuditUrl ? 'secondary' : 'outline'}
          tone={canonicalAuditUrl ? 'success' : 'default'}
          primaryText={auditPrimaryText}
          secondaryText={auditSecondaryText}
        />

        {canonicalAuditUrl && (
          <LeadDetailSection title="Страница аудита" tone="success">
            <div>
              <a
                href={canonicalAuditUrl}
                target="_blank"
                rel="noreferrer"
                className="block break-all text-sm font-medium text-emerald-700 underline"
              >
                {canonicalAuditUrl}
              </a>
            </div>
            {auditLinks.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-2">
                {auditLinks.map((item) => (
                  <a
                    key={item.language}
                    href={item.href}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 rounded-md border border-emerald-200 bg-white px-3 py-1.5 text-xs font-medium text-emerald-700 hover:bg-emerald-100"
                  >
                    <Globe className="h-3 w-3" />
                    Открыть аудит {item.label}
                  </a>
                ))}
              </div>
            )}
          </LeadDetailSection>
        )}

        <LeadDetailSection title="Ручная редактура аудита">
          <AdminAuditEditorPanel
            leadId={lead.id}
            enabled={Boolean(canonicalAuditUrl)}
            onPublished={onAuditEditorPublished}
          />
        </LeadDetailSection>

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
            <LeadDetailSection title="Контакты лида (ручное заполнение)">
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
            </LeadDetailSection>

            <LeadDetailSection title="Сводка по карточке">
              <div className="grid gap-4 lg:grid-cols-3">
                <StatusSummaryCard
                  title="Краткий статус"
                  statusLabel={preview.health_label}
                  statusVariant="secondary"
                  tone="info"
                  primaryText={preview.summary_text}
                  secondaryText={`Профиль аудита: ${preview.audit_profile_label || preview.audit_profile || '—'}`}
                />
                <StatusSummaryCard
                  title="Карточка"
                  statusLabel="Данные"
                  statusVariant="outline"
                  primaryText={`Рейтинг: ${preview.current_state.rating ?? '—'} · отзывы: ${preview.current_state.reviews_count ?? 0}`}
                  secondaryText={`Услуги: ${preview.current_state.services_count ?? 0} · фото: ${preview.current_state.photos_state || '—'}`}
                />
                <StatusSummaryCard
                  title="Парсинг"
                  statusLabel={parseStatusLabel()}
                  statusVariant="outline"
                  tone={parseStatus === 'error' || parseStatus === 'failed' ? 'danger' : parseStatus === 'captcha' ? 'warning' : 'success'}
                  primaryText={`Последний расчёт: ${formatDate(preview.parse_context.last_parse_at || null)}`}
                  secondaryText={preview.parse_context.last_parse_error || 'Детальный аудит формируется на отдельной странице и доступен по ссылкам выше.'}
                />
              </div>
              <LeadDetailMetaList
                columns={2}
                items={[
                  { label: 'Профиль аудита', value: preview.audit_profile_label || preview.audit_profile || '—' },
                  { label: 'Рейтинг', value: preview.current_state.rating ?? '—' },
                  { label: 'Отзывы', value: preview.current_state.reviews_count ?? 0 },
                  { label: 'Услуги', value: preview.current_state.services_count ?? 0 },
                  { label: 'Услуги с ценой', value: preview.current_state.services_with_price_count ?? 0 },
                  { label: 'Фото', value: preview.current_state.photos_state || '—' },
                ]}
              />
            </LeadDetailSection>
          </>
        )}
      </CardContent>
    </Card>
  );
};

export default LeadCardPreviewPanel;
