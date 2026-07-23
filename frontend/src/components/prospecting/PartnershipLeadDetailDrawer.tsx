import { ReactNode, useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { ContactPresenceBadges, StatusSummaryCard } from '@/components/prospecting/LeadWorkflowBlocks';
import { LeadDetailChipList, LeadDetailMetaList, LeadDetailSection } from '@/components/prospecting/LeadDetailSections';
import { OutreachEmailSetup } from '@/components/OutreachEmailSetup';
import { OutreachCampaignBuilder } from '@/components/prospecting/OutreachCampaignBuilder';
import { OutreachSenderProfileSetup } from '@/components/prospecting/OutreachSenderProfileSetup';
import { OutreachSuppressionManager } from '@/components/prospecting/OutreachSuppressionManager';
import {
  addPartnershipLeadContact,
  getPartnershipContactIntelligence,
} from '@/components/prospecting/partnershipApi';

type PartnershipLead = {
  id: string;
  active_workstream_id?: string | null;
  workstream_id?: string | null;
  name?: string;
  city?: string;
  category?: string;
  partnership_stage?: string;
  source_provider?: string;
  source_kind?: string;
  external_source_id?: string;
  external_place_id?: string;
  lat?: number;
  lon?: number;
  matched_sources_json?: string[] | null;
  website?: string;
  phone?: string;
  email?: string;
  telegram_url?: string;
  whatsapp_url?: string;
  selected_channel?: string;
  parse_status?: string;
  pilot_cohort?: string;
  next_best_action?: {
    label?: string;
    hint?: string;
  };
  enrich_payload_json?: {
    provider?: string;
    found_fields?: string[];
    confidence?: Record<string, number>;
  } | null;
  sales_room_status?: string;
  sales_room_data_mode?: string;
  sales_room_url?: string;
};

type LeadEditState = {
  name: string;
  city: string;
  category: string;
  address: string;
  phone: string;
  email: string;
  website: string;
  telegram_url: string;
  whatsapp_url: string;
};

type FlowStatus = {
  draftsTotal?: number;
  draftsApproved?: number;
  sentTotal?: number;
  outcomeFinal?: string | null;
};

type AuditPresentation = {
  label: string;
  variant?: 'default' | 'secondary' | 'outline' | 'destructive';
  tone?: 'default' | 'success' | 'warning' | 'info' | 'danger';
  primary: string;
  secondary?: string;
};

type StagePresentation = {
  label: string;
  variant?: 'default' | 'secondary' | 'outline' | 'destructive';
  tone?: 'default' | 'success' | 'warning' | 'info' | 'danger';
};

type MatchData = {
  match_score?: number;
  overlap?: string[];
  complement?: {
    partner_strength_tokens?: string[];
  };
  offer_angles?: string[];
  score_explanation?: string;
  reason_codes?: string[];
  readiness_code?: 'ready' | 'needs_sender_profile' | 'needs_evidence';
  next_action?: string;
  profile_completeness?: {
    completed_count?: number;
    required_count?: number;
    missing_items?: Array<{ code?: string; label?: string }>;
  };
};

type AuditData = {
  services_preview?: unknown[];
};

type CohortOption = {
  value: string;
  label: string;
};

type LeadContactPoint = {
  id: string;
  type?: string;
  value?: string;
  person_name?: string | null;
  role_title?: string | null;
  verification_status?: string;
};

type LeadTelegramSource = {
  id: string;
  title?: string;
  url?: string;
  status?: string;
  sync_status?: string;
  source_owner_type?: 'residential_complex' | 'prospecting_recipient';
  source_owner_name?: string;
  source_owner_label?: string;
  sender_business_is_owner?: boolean;
};

type PartnershipLeadDetailDrawerProps = {
  selectedLead: PartnershipLead;
  selectedLeadFlowStatus?: FlowStatus | null;
  stagePresentation: StagePresentation;
  auditPresentation: AuditPresentation;
  onClose: () => void;
  auditData?: AuditData | null;
  matchData?: MatchData | null;
  draftText?: string;
  selectedLeadLogo?: string | null;
  selectedLeadPhotos: string[];
  leadEdit: LeadEditState;
  setLeadEdit: (updater: (previous: LeadEditState) => LeadEditState) => void;
  loading?: boolean;
  onSaveLeadContacts: () => void;
  onManualContactSaved?: () => void | Promise<void>;
  onPrepareSalesRoom?: (dataMode: 'audited' | 'template') => void | Promise<void>;
  onSenderProfileChanged?: (state: { confirmed: boolean; ready: boolean }) => void;
  currentBusinessId?: string | null;
  pilotCohortOptions: CohortOption[];
  onPilotCohortChange: (value: string) => void | Promise<void>;
};

const manualChannelOptions = [
  { value: 'phone', label: 'Телефон', placeholder: '+7 999 000-00-00' },
  { value: 'email', label: 'Email', placeholder: 'hello@company.ru' },
  { value: 'telegram', label: 'Telegram', placeholder: '@username или https://t.me/channel' },
  { value: 'whatsapp', label: 'WhatsApp', placeholder: '+7 999 000-00-00 или ссылка wa.me' },
  { value: 'vk', label: 'VK', placeholder: 'https://vk.com/company' },
  { value: 'instagram', label: 'Instagram', placeholder: 'https://instagram.com/company' },
  { value: 'max', label: 'MAX', placeholder: 'https://max.ru/company' },
  { value: 'website_form', label: 'Форма на сайте', placeholder: 'https://company.ru/contacts' },
  { value: 'other', label: 'Другой канал', placeholder: 'Контакт или инструкция для связи' },
];

const manualChannelLabel = (value?: string) => (
  manualChannelOptions.find((option) => option.value === value)?.label || 'Другой канал'
);

function DrawerSection({ children }: { children: ReactNode }) {
  return <div className="space-y-4 px-5 py-5">{children}</div>;
}

function formatSourceLabel(value?: string) {
  const normalized = String(value || '').trim().toLowerCase();
  if (!normalized) return '—';
  if (normalized === 'yandex_maps') return 'Яндекс Карты';
  if (normalized === 'google_docs' || normalized === 'google_doc_partnership_import') return 'Google Docs';
  if (normalized === 'network_manual') return 'Вручную';
  if (normalized === 'manual') return 'Вручную';
  if (normalized === 'localos') return 'LocalOS';
  return value || '—';
}

function formatChannelLabel(value?: string) {
  const normalized = String(value || '').trim().toLowerCase();
  if (!normalized) return 'Канал ещё не выбран';
  if (normalized === 'email') return 'Email';
  if (normalized === 'telegram') return 'Telegram';
  if (normalized === 'whatsapp') return 'WhatsApp';
  if (normalized === 'phone') return 'Телефон';
  if (normalized === 'manual') return 'Ручной контакт';
  return value || 'Канал ещё не выбран';
}

export default function PartnershipLeadDetailDrawer({
  selectedLead,
  selectedLeadFlowStatus,
  stagePresentation,
  auditPresentation,
  onClose,
  auditData,
  matchData,
  draftText,
  selectedLeadLogo,
  selectedLeadPhotos,
  leadEdit,
  setLeadEdit,
  loading,
  onSaveLeadContacts,
  onManualContactSaved,
  onPrepareSalesRoom,
  onSenderProfileChanged,
  currentBusinessId,
  pilotCohortOptions,
  onPilotCohortChange,
}: PartnershipLeadDetailDrawerProps) {
  const workstreamId = String(selectedLead.active_workstream_id || selectedLead.workstream_id || '').trim();
  const [leadContacts, setLeadContacts] = useState<LeadContactPoint[]>([]);
  const [leadTelegramSources, setLeadTelegramSources] = useState<LeadTelegramSource[]>([]);
  const [manualContactType, setManualContactType] = useState('telegram');
  const [manualContactValue, setManualContactValue] = useState('');
  const [manualTelegramUsage, setManualTelegramUsage] = useState('recipient');
  const [manualOwnerType, setManualOwnerType] = useState('company');
  const [manualPersonName, setManualPersonName] = useState('');
  const [manualRoleTitle, setManualRoleTitle] = useState('');
  const [manualContactBusy, setManualContactBusy] = useState(false);
  const [manualContactNotice, setManualContactNotice] = useState('');
  const [manualContactError, setManualContactError] = useState('');
  const flowPrimaryText = `Этап: ${stagePresentation.label} · Канал: ${formatChannelLabel(selectedLead.selected_channel)}`;
  const flowSecondaryText = `Писем: ${selectedLeadFlowStatus?.draftsTotal ?? 0} · утверждено: ${selectedLeadFlowStatus?.draftsApproved ?? 0} · отправлено: ${selectedLeadFlowStatus?.sentTotal ?? 0} · результат: ${selectedLeadFlowStatus?.outcomeFinal || 'пока нет'}`;
  const matchNeedsSenderProfile = matchData?.readiness_code === 'needs_sender_profile'
    || Boolean(matchData?.reason_codes?.includes('SENDER_PROFILE_INCOMPLETE'));
  const matchNeedsEvidence = matchData?.readiness_code === 'needs_evidence';
  const missingProfileItems = matchData?.profile_completeness?.missing_items
    ?.map((item) => String(item.label || '').trim())
    .filter(Boolean) || [];

  const loadContactPoints = async () => {
    if (!currentBusinessId || !workstreamId) return;
    const payload = await getPartnershipContactIntelligence(currentBusinessId, selectedLead.id, workstreamId);
    setLeadContacts(Array.isArray(payload?.contacts) ? payload.contacts : []);
    setLeadTelegramSources(Array.isArray(payload?.telegram_sources) ? payload.telegram_sources : []);
  };

  useEffect(() => {
    let active = true;
    if (!currentBusinessId || !workstreamId) {
      setLeadContacts([]);
      setLeadTelegramSources([]);
      return undefined;
    }
    getPartnershipContactIntelligence(currentBusinessId, selectedLead.id, workstreamId)
      .then((payload) => {
        if (!active) return;
        setLeadContacts(Array.isArray(payload?.contacts) ? payload.contacts : []);
        setLeadTelegramSources(Array.isArray(payload?.telegram_sources) ? payload.telegram_sources : []);
      })
      .catch(() => {
        if (active) setManualContactError('Не удалось загрузить дополнительные контакты');
      });
    return () => {
      active = false;
    };
  }, [currentBusinessId, selectedLead.id, workstreamId]);

  const saveManualContact = async () => {
    if (!currentBusinessId || !workstreamId || !manualContactValue.trim()) return;
    setManualContactBusy(true);
    setManualContactNotice('');
    setManualContactError('');
    try {
      const result = await addPartnershipLeadContact(currentBusinessId, selectedLead.id, {
        workstream_id: workstreamId,
        contact_type: manualContactType,
        value: manualContactValue,
        telegram_usage: manualTelegramUsage,
        owner_type: manualOwnerType,
        person_name: manualPersonName,
        role_title: manualRoleTitle,
      });
      setManualContactValue('');
      setManualPersonName('');
      setManualRoleTitle('');
      setManualContactNotice(result?.entry_kind === 'telegram_source'
        ? 'Telegram-канал добавлен в источники. Радар проверит его и соберёт подходящие сигналы.'
        : 'Контакт сохранён. Он доступен для выбора в аутриче.');
      await loadContactPoints();
      await onManualContactSaved?.();
    } catch (requestError) {
      setManualContactError(requestError instanceof Error ? requestError.message : 'Не удалось сохранить контакт');
    } finally {
      setManualContactBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/25 backdrop-blur-sm" onClick={onClose}>
      <div
        className="absolute inset-y-0 right-0 w-full max-w-3xl overflow-y-auto border-l border-border bg-background shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="sticky top-0 z-10 border-b border-border bg-background/95 backdrop-blur">
          <div className="flex items-start justify-between gap-3 px-5 py-4">
            <div>
              <h2 className="text-xl font-semibold text-foreground">{selectedLead.name || 'Карточка лида'}</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                {selectedLead.city || '—'} · {selectedLead.category || '—'} · этап: {stagePresentation.label}
              </p>
            </div>
            <Button variant="outline" size="sm" onClick={onClose}>
              Закрыть
            </Button>
          </div>
        </div>

        <DrawerSection>
          {selectedLead.next_best_action ? (
            <StatusSummaryCard
              title="Следующий шаг"
              statusLabel="В работе"
              statusVariant="secondary"
              tone="info"
              primaryText={selectedLead.next_best_action.label || '—'}
              secondaryText={selectedLead.next_best_action.hint || '—'}
            />
          ) : null}

          <div className="grid gap-4 lg:grid-cols-2">
            <StatusSummaryCard
              title="Поток"
              statusLabel={stagePresentation.label}
              statusVariant={stagePresentation.variant}
              tone={stagePresentation.tone}
              primaryText={flowPrimaryText}
              secondaryText={flowSecondaryText}
            />
            <StatusSummaryCard
              title="Аудит"
              statusLabel={auditPresentation.label}
              statusVariant={auditPresentation.variant}
              tone={auditPresentation.tone}
              primaryText={auditPresentation.primary}
              secondaryText={auditPresentation.secondary}
            />
          </div>

          {matchData ? (
            <LeadDetailSection
              title={matchNeedsSenderProfile || matchNeedsEvidence ? 'Что нужно для проверки совместимости' : 'Совместимость бизнесов'}
              tone={matchNeedsSenderProfile || matchNeedsEvidence ? 'warning' : 'success'}
            >
              {matchNeedsSenderProfile ? (
                <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-amber-950">
                  <div className="text-sm font-semibold">Нужны факты об отправителе</div>
                  <p className="mt-1 text-sm leading-6">
                    LocalOS не будет придумывать опыт, кейсы или предложение. Заполнено {matchData.profile_completeness?.completed_count ?? 0} из {matchData.profile_completeness?.required_count ?? 9} обязательных пунктов.
                  </p>
                  {missingProfileItems.length > 0 ? (
                    <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
                      {missingProfileItems.slice(0, 5).map((item) => <li key={item}>{item}</li>)}
                    </ul>
                  ) : null}
                  <Button asChild size="sm" className="mt-3 bg-orange-500 text-white hover:bg-orange-600">
                    <a href="#sender-profile-settings">Заполнить профиль отправителя</a>
                  </Button>
                </div>
              ) : null}
              {matchNeedsEvidence ? (
                <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-950">
                  <div className="font-semibold">Нужны дополнительные факты о партнёре</div>
                  <p className="mt-1">{matchData.next_action || 'Соберите данные карточки и повторите проверку совместимости.'}</p>
                </div>
              ) : null}
              <LeadDetailMetaList
                items={[
                  {
                    label: 'Оценка совместимости',
                    value: matchNeedsSenderProfile || matchNeedsEvidence ? 'Пока не подтверждена' : `${matchData.match_score ?? 0}%`,
                  },
                  { label: 'Общие направления', value: (matchData.overlap || []).slice(0, 8).join(', ') || 'Не найдены' },
                  {
                    label: 'Чем партнёр дополняет бизнес',
                    value: ((matchData.complement || {}).partner_strength_tokens || []).slice(0, 6).join(', ') || 'Нужно уточнить',
                  },
                  { label: 'Варианты предложения', value: (matchData.offer_angles || []).slice(0, 3).join(' · ') || 'Нужно подготовить' },
                ]}
              />
              {matchData.score_explanation ? <p className="text-pretty text-sm leading-6 text-foreground">{String(matchData.score_explanation)}</p> : null}
              <LeadDetailChipList items={Array.isArray(matchData.reason_codes) ? matchData.reason_codes : []} emptyText="Дополнительных оснований пока нет." />
            </LeadDetailSection>
          ) : null}

          <LeadDetailSection title="Источник и контакты">
            <LeadDetailMetaList
              columns={2}
              items={[
                { label: 'Площадка', value: formatSourceLabel(selectedLead.source_provider) },
                { label: 'Источник', value: formatSourceLabel(selectedLead.source_kind) },
                { label: 'Внешний ID', value: selectedLead.external_source_id || '—' },
                { label: 'ID места на карте', value: selectedLead.external_place_id || '—' },
                { label: 'Координаты', value: `${selectedLead.lat ?? '—'}, ${selectedLead.lon ?? '—'}` },
                {
                  label: 'Объединённые источники',
                  value: Array.isArray(selectedLead.matched_sources_json) && selectedLead.matched_sources_json.length
                    ? selectedLead.matched_sources_json.join(', ')
                    : '—',
                },
              ]}
            />
            <ContactPresenceBadges
              website={selectedLead.website}
              phone={selectedLead.phone}
              email={selectedLead.email}
              telegramUrl={selectedLead.telegram_url}
              whatsappUrl={selectedLead.whatsapp_url}
              hasMessenger={Boolean(selectedLead.telegram_url || selectedLead.whatsapp_url)}
            />
            {(leadContacts.length > 0 || leadTelegramSources.length > 0) ? (
              <div className="space-y-2">
                {leadContacts.filter((contact) => contact.type !== 'website').map((contact) => (
                  <div key={contact.id} className="rounded-xl bg-slate-50 px-3 py-2 text-sm">
                    <div className="font-semibold text-slate-900">{contact.person_name || contact.value || manualChannelLabel(contact.type)}</div>
                    <div className="mt-0.5 text-xs text-slate-600">
                      {[contact.role_title, manualChannelLabel(contact.type), contact.person_name ? contact.value : ''].filter(Boolean).join(' · ')}
                    </div>
                  </div>
                ))}
                {leadTelegramSources.map((source) => (
                  <a key={source.id} href={source.url} target="_blank" rel="noreferrer" className="block min-h-11 rounded-xl bg-sky-50 px-3 py-2 text-sm text-sky-900">
                    <span className="font-semibold">{source.title || source.url || 'Telegram-канал'}</span>
                    <span className="mt-0.5 block text-xs">Источник {source.source_owner_label || source.source_owner_name || 'получателя'}</span>
                    <span className="mt-0.5 block text-xs">{source.status === 'active' ? 'Проверен радаром' : 'Ожидает проверки радара'}</span>
                  </a>
                ))}
              </div>
            ) : null}
            <details className="rounded-xl bg-slate-50 p-4">
              <summary className="flex min-h-10 cursor-pointer items-center text-sm font-semibold text-slate-800">
                Добавить контакт или соцсеть вручную
              </summary>
              <div className="grid gap-3 pt-3 sm:grid-cols-2">
                <label className="text-xs font-semibold text-slate-700">
                  Канал
                  <Select value={manualContactType} onValueChange={(value) => setManualContactType(value)}>
                    <SelectTrigger className="mt-1 h-11 bg-white"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {manualChannelOptions.map((option) => <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </label>
                <label className="text-xs font-semibold text-slate-700">
                  Контакт или ссылка
                  <Input
                    value={manualContactValue}
                    onChange={(event) => {
                      setManualContactValue(event.target.value);
                      setManualContactError('');
                    }}
                    placeholder={manualChannelOptions.find((option) => option.value === manualContactType)?.placeholder || 'Укажите контакт'}
                    className="mt-1 h-11 bg-white font-normal"
                  />
                </label>
                {manualContactType === 'telegram' ? (
                  <label className="text-xs font-semibold text-slate-700 sm:col-span-2">
                    Как использовать Telegram-ссылку
                    <Select value={manualTelegramUsage} onValueChange={setManualTelegramUsage}>
                      <SelectTrigger className="mt-1 h-11 bg-white"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="recipient">Личный аккаунт или чат — получатель</SelectItem>
                        <SelectItem value="signal_source">Публичный канал — источник сигналов</SelectItem>
                      </SelectContent>
                    </Select>
                  </label>
                ) : null}
                {!(manualContactType === 'telegram' && manualTelegramUsage === 'signal_source') ? (
                  <>
                    <label className="text-xs font-semibold text-slate-700 sm:col-span-2">
                      Кому принадлежит контакт
                      <Select value={manualOwnerType} onValueChange={setManualOwnerType}>
                        <SelectTrigger className="mt-1 h-11 bg-white"><SelectValue /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="company">Компании — общий контакт</SelectItem>
                          <SelectItem value="person">Конкретному человеку</SelectItem>
                        </SelectContent>
                      </Select>
                    </label>
                    {manualOwnerType === 'person' ? (
                      <>
                        <Input value={manualPersonName} onChange={(event) => setManualPersonName(event.target.value)} placeholder="Имя человека" className="h-11 bg-white" />
                        <Input value={manualRoleTitle} onChange={(event) => setManualRoleTitle(event.target.value)} placeholder="Роль, например управляющая" className="h-11 bg-white" />
                      </>
                    ) : null}
                  </>
                ) : null}
              </div>
              <p className="mt-3 text-pretty text-xs leading-5 text-slate-600">
                {manualContactType === 'telegram' && manualTelegramUsage === 'signal_source'
                  ? 'Публичный канал не станет получателем. После проверки его публикации можно использовать как подтверждённые сигналы для персонализации.'
                  : 'LocalOS сохранит контакт отдельно и не будет считать его проверенным только потому, что он добавлен вручную.'}
              </p>
              {manualContactNotice ? <div className="mt-3 rounded-xl bg-emerald-50 px-3 py-2 text-sm text-emerald-800">{manualContactNotice}</div> : null}
              {manualContactError ? <div role="alert" className="mt-3 rounded-xl bg-rose-50 px-3 py-2 text-sm text-rose-800">{manualContactError}</div> : null}
              <Button
                type="button"
                onClick={() => void saveManualContact()}
                disabled={manualContactBusy || !manualContactValue.trim() || !currentBusinessId || !workstreamId}
                className="mt-3 min-h-11 active:scale-[0.96] transition-transform"
              >
                {manualContactBusy
                  ? 'Сохраняем…'
                  : manualContactType === 'telegram' && manualTelegramUsage === 'signal_source'
                    ? 'Добавить канал'
                    : 'Сохранить контакт'}
              </Button>
            </details>
          </LeadDetailSection>

          <LeadDetailSection title="Цифровая комната">
            <div className="rounded-2xl border border-orange-200 bg-orange-50/70 p-4">
              <div className="text-sm font-semibold text-orange-900">Подготовить предложение перед первым письмом</div>
              <p className="mt-1 text-sm leading-6 text-orange-800">
                Комната нужна для предложения, чата и файлов. Подготовка данных расходует кредиты и помогает сметчить услуги,
                чтобы предложение было предметным.
              </p>
              {selectedLead.sales_room_url ? (
                <div className="mt-3 rounded-xl border border-orange-200 bg-white px-3 py-2 text-sm text-orange-900">
                  Комната готова ·{' '}
                  <a className="font-semibold underline" href={selectedLead.sales_room_url} target="_blank" rel="noreferrer">
                    открыть
                  </a>
                </div>
              ) : null}
              <div className="mt-4 flex flex-col gap-2 sm:flex-row">
                <Button
                  size="sm"
                  onClick={() => void onPrepareSalesRoom?.('audited')}
                  disabled={loading || !onPrepareSalesRoom}
                >
                  Создать комнату
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => void onPrepareSalesRoom?.('template')}
                  disabled={loading || !onPrepareSalesRoom}
                >
                  Без подготовки данных
                </Button>
              </div>
            </div>
          </LeadDetailSection>

          <LeadDetailSection title="Дополнительные данные" tone="muted">
            <LeadDetailMetaList
              items={[
                { label: 'Источник данных', value: formatSourceLabel(selectedLead.enrich_payload_json?.provider) },
                {
                  label: 'Найденные поля',
                  value: Array.isArray(selectedLead.enrich_payload_json?.found_fields) && selectedLead.enrich_payload_json.found_fields.length
                    ? selectedLead.enrich_payload_json.found_fields.join(', ')
                    : '—',
                },
                {
                  label: 'Уверенность',
                  value: selectedLead.enrich_payload_json?.confidence && Object.keys(selectedLead.enrich_payload_json.confidence).length
                    ? Object.entries(selectedLead.enrich_payload_json.confidence)
                        .map(([key, value]) => `${key} ${Math.round(Number(value || 0) * 100)}%`)
                        .join(' · ')
                    : '—',
                },
              ]}
            />
          </LeadDetailSection>

          {auditData ? (
            <LeadDetailSection title="Аудит карточки" tone="success">
              <LeadDetailMetaList items={[{ label: 'Услуг в превью', value: (auditData.services_preview || []).length || 0 }]} />
              {(selectedLeadLogo || selectedLeadPhotos.length > 0) ? (
                <div className="space-y-2">
                  {selectedLeadLogo ? (
                    <div>
                      <div className="mb-1 text-xs text-muted-foreground">Логотип</div>
                      <img
                        src={selectedLeadLogo}
                        alt="Логотип лида"
                        className="h-16 w-16 rounded-md border border-gray-200 bg-white object-cover"
                      />
                    </div>
                  ) : null}
                  {selectedLeadPhotos.length > 0 ? (
                    <div>
                      <div className="mb-1 text-xs text-muted-foreground">Фото</div>
                      <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
                        {selectedLeadPhotos.map((photo, index) => (
                          <img
                            key={`${photo}-${index}`}
                            src={photo}
                            alt={`Фото лида ${index + 1}`}
                            className="h-20 w-full rounded-md border border-gray-200 bg-white object-cover"
                          />
                        ))}
                      </div>
                    </div>
                  ) : null}
                </div>
              ) : null}
            </LeadDetailSection>
          ) : null}

          {draftText ? (
            <LeadDetailSection title="Первое письмо" tone="info">
              <Textarea value={draftText} rows={8} readOnly />
            </LeadDetailSection>
          ) : null}

          <LeadDetailSection title="Мультиканальный аутрич" tone="info">
            <details id="sender-profile-settings" className="scroll-mt-24 rounded-xl border border-slate-200 bg-slate-50 p-4" defaultOpen={matchNeedsSenderProfile}>
              <summary className="min-h-10 cursor-pointer text-sm font-semibold text-slate-800">
                Заполнить профиль отправителя
              </summary>
              <div className="pt-4">
                <OutreachSenderProfileSetup
                  businessId={currentBusinessId}
                  defaultCompanyName=""
                  onChanged={onSenderProfileChanged}
                />
              </div>
            </details>
            <OutreachCampaignBuilder
              workstreamId={selectedLead.active_workstream_id || selectedLead.workstream_id}
              businessId={currentBusinessId}
              leadSegment={selectedLead.category}
            />
            <details className="border-t border-slate-200 pt-3">
              <summary className="flex min-h-10 cursor-pointer items-center text-sm font-semibold text-slate-700">
                Подключить или проверить email
              </summary>
              <div className="pt-3">
                <OutreachEmailSetup scopeType="business" businessId={currentBusinessId} compact />
              </div>
            </details>
            <a
              href={`/dashboard/settings/integrations?focus=telegram&return_to=${encodeURIComponent('/dashboard/partnerships')}`}
              className="inline-flex min-h-10 items-center text-sm font-semibold text-orange-700 hover:text-orange-800"
            >
              Настроить Telegram бизнеса
            </a>
            <details className="border-t border-slate-200 pt-3">
              <summary className="flex min-h-10 cursor-pointer items-center text-sm font-semibold text-slate-700">
                Stop-list и запреты
              </summary>
              <div className="pt-3">
                <OutreachSuppressionManager
                  workstreamId={selectedLead.active_workstream_id || selectedLead.workstream_id}
                  businessId={currentBusinessId}
                />
              </div>
            </details>
          </LeadDetailSection>

          <LeadDetailSection title="Ручное редактирование лида">
            <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
              <Input value={leadEdit.name} onChange={(event) => setLeadEdit((previous) => ({ ...previous, name: event.target.value }))} placeholder="Название" />
              <Input value={leadEdit.category} onChange={(event) => setLeadEdit((previous) => ({ ...previous, category: event.target.value }))} placeholder="Категория" />
              <Input value={leadEdit.city} onChange={(event) => setLeadEdit((previous) => ({ ...previous, city: event.target.value }))} placeholder="Город" />
              <Input value={leadEdit.address} onChange={(event) => setLeadEdit((previous) => ({ ...previous, address: event.target.value }))} placeholder="Адрес" />
              <Input value={leadEdit.phone} onChange={(event) => setLeadEdit((previous) => ({ ...previous, phone: event.target.value }))} placeholder="Телефон" />
              <Input value={leadEdit.email} onChange={(event) => setLeadEdit((previous) => ({ ...previous, email: event.target.value }))} placeholder="Email" />
              <Input value={leadEdit.website} onChange={(event) => setLeadEdit((previous) => ({ ...previous, website: event.target.value }))} placeholder="Сайт" />
              <Input value={leadEdit.telegram_url} onChange={(event) => setLeadEdit((previous) => ({ ...previous, telegram_url: event.target.value }))} placeholder="Telegram URL" />
              <Input value={leadEdit.whatsapp_url} onChange={(event) => setLeadEdit((previous) => ({ ...previous, whatsapp_url: event.target.value }))} placeholder="WhatsApp URL" />
            </div>
            <div className="flex flex-wrap justify-end gap-2">
              <Button variant="outline" onClick={onSaveLeadContacts} disabled={loading}>
                Сохранить данные лида
              </Button>
              <Select
                value={selectedLead.pilot_cohort || 'backlog'}
                onValueChange={(value) => {
                  if (!currentBusinessId) return;
                  void onPilotCohortChange(value);
                }}
              >
                <SelectTrigger className="w-[180px] bg-white">
                  <SelectValue placeholder="Когорта" />
                </SelectTrigger>
                <SelectContent>
                  {pilotCohortOptions.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </LeadDetailSection>
        </DrawerSection>
      </div>
    </div>
  );
}
