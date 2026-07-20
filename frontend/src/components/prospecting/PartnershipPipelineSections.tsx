import { useEffect, useState } from 'react';
import type { DragEventHandler } from 'react';
import { AlertCircle, CheckCircle2, Circle, Loader2 } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { ContactPresenceBadges, WorkflowActionRow } from '@/components/prospecting/LeadWorkflowBlocks';

type WorkflowBadgeVariant = 'default' | 'secondary' | 'outline' | 'destructive';
type WorkflowTone = 'default' | 'success' | 'warning' | 'info' | 'danger';

type PipelineLead = {
  id: string;
  name?: string;
  address?: string;
  city?: string;
  category?: string;
  source_url?: string;
  source_kind?: string;
  source_provider?: string;
  client_business_name?: string;
  matching_sources_json?: string[] | null;
  enrich_payload_json?: {
    provider?: string;
    found_fields?: string[];
  } | null;
  phone?: string;
  email?: string;
  website?: string;
  telegram_url?: string;
  whatsapp_url?: string;
  partnership_stage?: string;
  pipeline_status?: string;
  pilot_cohort?: string;
  rating?: number;
  reviews_count?: number;
  parse_status?: string;
  parse_updated_at?: string;
  parse_retry_after?: string;
  parse_error?: string;
  audit_ready?: boolean;
  match_summary_json?: {
    match_score?: number;
    score_explanation?: string;
    overlap?: string[];
    offer_angles?: string[];
    readiness_code?: 'ready' | 'needs_sender_profile' | 'needs_evidence';
    next_action?: string;
    reason_codes?: string[];
    profile_completeness?: {
      completed_count?: number;
      required_count?: number;
    };
  } | null;
  artifact_updated_at?: string;
  deferred_reason?: string;
  deferred_until?: string;
  sales_room_status?: string;
  sales_room_data_mode?: string;
  sales_room_url?: string;
  next_best_action?: {
    label?: string;
    hint?: string;
  };
};

type PipelineBoardColumn = {
  id: string;
  label: string;
  description: string;
  leads: PipelineLead[];
};

type StagePresentation = {
  label: string;
  helper: string;
  variant: WorkflowBadgeVariant;
  tone: WorkflowTone;
};

type AuditPresentation = {
  label: string;
  primary: string;
  secondary: string;
  variant: WorkflowBadgeVariant;
  tone: WorkflowTone;
};

type Option = {
  value: string;
  label: string;
};

type DeferredPayload = {
  deferredReason: string;
  deferredUntil: string;
};

type LeadBasicsPatch = {
  name: string;
  category: string;
  city: string;
  address: string;
};

type LeadActionKind = 'parse' | 'enrich' | 'audit' | 'match';

type LeadActionState = {
  leadId: string;
  action: LeadActionKind;
};

const mutedPillClass = 'inline-flex max-w-full items-center rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-[11px] font-medium text-slate-600';
const compactMetaClass = 'truncate text-[11px] text-slate-500';

const shortStatusLabel = (value?: string) => {
  const normalized = String(value || '').trim().toLowerCase();
  if (!normalized || normalized === 'unprocessed' || normalized === 'imported') return 'Кандидат';
  if (normalized === 'in_progress' || normalized === 'qualified') return 'В работе';
  if (normalized === 'contacted') return 'Письмо 1 отправлено';
  if (normalized === 'second_message_sent') return 'КП отправлено';
  if (normalized === 'replied') return 'Есть ответ';
  if (normalized === 'converted') return 'Партнёр';
  if (normalized === 'postponed' || normalized === 'deferred') return 'Отложен';
  if (normalized === 'not_relevant' || normalized === 'disqualified') return 'Неактуален';
  return value || '—';
};

const sourceProviderLabel = (value?: string) => {
  const normalized = String(value || '').trim().toLowerCase();
  if (!normalized) return '';
  if (normalized === 'yandex_maps' || normalized.includes('yandex')) return 'Яндекс Карты';
  if (normalized === 'two_gis' || normalized === '2gis' || normalized.includes('2gis')) return '2ГИС';
  if (normalized.includes('google_doc')) return 'Google Docs';
  if (normalized.includes('google')) return 'Google Maps';
  if (normalized.includes('manual') || normalized.includes('localos')) return 'Ручной ввод';
  if (normalized.includes('file')) return 'Файл';
  return String(value || '').trim();
};

const isPlaceholderPartnerName = (value?: string) => {
  const normalized = String(value || '').trim().toLowerCase();
  return !normalized || normalized === 'новый партнёр' || normalized === 'новый партнер' || normalized === 'без названия';
};

const getLeadBasicsDraft = (lead: PipelineLead): LeadBasicsPatch => ({
  name: String(lead.name || '').trim(),
  category: String(lead.category || '').trim(),
  city: String(lead.city || '').trim(),
  address: String(lead.address || '').trim(),
});

const completedAuditStages = new Set([
  'audited',
  'matched',
  'proposal_draft_ready',
  'selected_for_outreach',
  'channel_selected',
  'proposal_approved',
  'approved_for_send',
  'queued_for_send',
  'sent',
]);

const completedMatchStages = new Set([
  'matched',
  'proposal_draft_ready',
  'selected_for_outreach',
  'channel_selected',
  'proposal_approved',
  'approved_for_send',
  'queued_for_send',
  'sent',
]);

const leadHasMatchResult = (lead: PipelineLead) => (
  Boolean(
    lead.match_summary_json
    && (!lead.match_summary_json.readiness_code || lead.match_summary_json.readiness_code === 'ready')
  ) || completedMatchStages.has(String(lead.partnership_stage || '').toLowerCase())
);

const preparationStepIcon = (state: 'complete' | 'active' | 'waiting' | 'error') => {
  if (state === 'complete') return <CheckCircle2 className="h-5 w-5 text-emerald-600" />;
  if (state === 'active') return <Loader2 className="h-5 w-5 animate-spin text-sky-600" />;
  if (state === 'error') return <AlertCircle className="h-5 w-5 text-red-600" />;
  return <Circle className="h-5 w-5 text-slate-300" />;
};

const LeadPreparationGuide = ({
  lead,
  loading,
  activeLeadAction,
  onRunParse,
  onRunAudit,
  onRunMatch,
  onOpenLead,
}: {
  lead: PipelineLead;
  loading: boolean;
  activeLeadAction: LeadActionState | null;
  onRunParse: (leadId: string) => void;
  onRunAudit: (leadId: string) => void;
  onRunMatch: (leadId: string) => void;
  onOpenLead: (leadId: string) => void;
}) => {
  const stage = String(lead.partnership_stage || '').toLowerCase();
  const parseStatus = String(lead.parse_status || '').toLowerCase();
  const isThisLeadBusy = activeLeadAction?.leadId === lead.id;
  const runningAction = isThisLeadBusy ? activeLeadAction.action : null;
  const parseRunning = ['pending', 'processing', 'captcha', 'retry_wait'].includes(parseStatus) || runningAction === 'parse';
  const parseFailed = parseStatus === 'error' || parseStatus === 'failed';
  const terminalClosed = lead.next_best_action?.code === 'mark_closed_not_relevant';
  const identityMismatch = lead.next_best_action?.code === 'repair_recipient_identity_mapping';
  const auditComplete = Boolean(lead.audit_ready) || completedAuditStages.has(stage);
  const matchAssessment = lead.match_summary_json;
  const matchNeedsSenderProfile = matchAssessment?.readiness_code === 'needs_sender_profile'
    || Boolean(matchAssessment?.reason_codes?.includes('SENDER_PROFILE_INCOMPLETE'));
  const matchNeedsEvidence = matchAssessment?.readiness_code === 'needs_evidence';
  const matchComplete = leadHasMatchResult(lead);
  const dataComplete = !identityMismatch && (['completed', 'done'].includes(parseStatus) || auditComplete || matchComplete);
  const matchScore = lead.match_summary_json?.match_score;
  const offerAngles = Array.isArray(lead.match_summary_json?.offer_angles)
    ? lead.match_summary_json.offer_angles.filter(Boolean).slice(0, 3)
    : [];

  const steps: Array<{
    label: string;
    description: string;
    state: 'complete' | 'active' | 'waiting' | 'error';
  }> = [
    {
      label: 'Данные компании',
      description: dataComplete
        ? 'Карточка и открытые данные собраны'
        : identityMismatch
          ? 'Найдена карточка другой компании — нужно повторить поиск'
          : parseRunning
            ? 'Собираем данные — статус обновится автоматически'
            : parseFailed
              ? terminalClosed
                ? 'Публичная карточка сообщает, что компания закрыта'
                : 'Сбор не завершён — можно повторить'
              : 'Нужно собрать карточку, услуги и контакты',
      state: dataComplete ? 'complete' : parseRunning ? 'active' : parseFailed ? 'error' : 'waiting',
    },
    {
      label: 'Разбор карточки',
      description: auditComplete
        ? 'Сильные стороны и факты для предложения найдены'
        : runningAction === 'audit'
          ? 'Анализируем карточку'
          : 'После сбора данных LocalOS найдёт факты для предложения',
      state: auditComplete ? 'complete' : runningAction === 'audit' ? 'active' : 'waiting',
    },
    {
      label: 'Совместимость',
      description: matchComplete
        ? matchScore === undefined
          ? 'Совместимость рассчитана'
          : `Совместимость: ${matchScore}%`
        : runningAction === 'match'
          ? 'Сопоставляем услуги и аудитории'
          : matchNeedsSenderProfile
            ? `Нужны факты об отправителе: ${matchAssessment?.profile_completeness?.completed_count ?? 0} из ${matchAssessment?.profile_completeness?.required_count ?? 9}`
            : matchNeedsEvidence
              ? 'Нужно собрать больше публичных фактов о партнёре'
          : 'Проверим, чем бизнесы полезны друг другу',
      state: matchComplete ? 'complete' : runningAction === 'match' ? 'active' : 'waiting',
    },
  ];

  const nextAction = terminalClosed || parseRunning
    ? null
    : !dataComplete
      ? {
          label: identityMismatch
            ? 'Найти правильную карточку'
            : parseFailed
              ? 'Повторить сбор данных'
              : lead.next_best_action?.code === 'resolve_and_parse'
                ? 'Найти карточку и собрать данные'
                : 'Собрать данные о компании',
          onClick: () => onRunParse(lead.id),
        }
      : !auditComplete
        ? { label: 'Разобрать карточку', onClick: () => onRunAudit(lead.id) }
        : matchNeedsSenderProfile
          ? { label: 'Заполнить профиль отправителя', onClick: () => onOpenLead(lead.id) }
          : matchNeedsEvidence
            ? { label: 'Собрать недостающие факты', onClick: () => onRunParse(lead.id) }
            : !matchComplete
              ? { label: 'Проверить совместимость', onClick: () => onRunMatch(lead.id) }
          : null;

  return (
    <section className="mt-3 rounded-2xl bg-slate-50 p-4 shadow-[inset_0_0_0_1px_rgba(15,23,42,0.08)]">
      <div className="flex flex-col gap-1">
        <div className="text-sm font-semibold text-slate-950">Подготовка предложения</div>
        <p className="text-pretty text-xs leading-5 text-slate-600">Пройдите три шага. LocalOS покажет результат здесь и предложит, что делать дальше.</p>
      </div>

      <ol className="mt-4 grid gap-3 lg:grid-cols-3">
        {steps.map((step, index) => (
          <li key={step.label} className="flex min-w-0 gap-2.5">
            <span className="relative mt-0.5 shrink-0" aria-hidden="true">{preparationStepIcon(step.state)}</span>
            <div className="min-w-0">
              <div className="text-xs font-semibold text-slate-900">{index + 1}. {step.label}</div>
              <div className="mt-0.5 text-pretty text-[11px] leading-4 text-slate-500">{step.description}</div>
            </div>
          </li>
        ))}
      </ol>

      {terminalClosed ? (
        <div className="mt-4 rounded-xl bg-amber-50 p-3 text-xs leading-5 text-amber-900 shadow-[inset_0_0_0_1px_rgba(217,119,6,0.2)]">
          Публичная карточка сообщает, что компания закрыта. Повторный сбор не запускается — используйте действие «Неактуален» в карточке лида.
        </div>
      ) : null}

      {matchComplete ? (
        <div className="mt-4 rounded-xl bg-emerald-50 p-3 shadow-[inset_0_0_0_1px_rgba(5,150,105,0.16)]">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div className="min-w-0">
              <div className="text-sm font-semibold text-emerald-950">
                {matchScore === undefined ? 'Совместимость рассчитана' : `Совместимость ${matchScore}%`}
              </div>
              <p className="mt-1 text-pretty text-xs leading-5 text-emerald-900">
                {lead.match_summary_json?.score_explanation || 'LocalOS нашёл основание для совместного предложения. Откройте результат, чтобы посмотреть факты и варианты оффера.'}
              </p>
              {offerAngles.length > 0 ? (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {offerAngles.map((angle) => <span key={angle} className="rounded-full bg-white px-2 py-1 text-[11px] text-emerald-900 shadow-[inset_0_0_0_1px_rgba(5,150,105,0.16)]">{angle}</span>)}
                </div>
              ) : null}
            </div>
            <Button size="sm" variant="outline" onClick={() => onOpenLead(lead.id)} className="min-h-10 shrink-0 bg-white active:scale-[0.96] transition-transform">
              Посмотреть результат
            </Button>
          </div>
        </div>
      ) : matchNeedsSenderProfile || matchNeedsEvidence ? (
        <div className="mt-4 rounded-xl bg-amber-50 p-3 shadow-[inset_0_0_0_1px_rgba(217,119,6,0.2)]">
          <div className="text-sm font-semibold text-amber-950">
            {matchNeedsSenderProfile ? 'Нужны факты об отправителе' : 'Нужны факты о партнёре'}
          </div>
          <p className="mt-1 text-pretty text-xs leading-5 text-amber-900">
            {matchAssessment?.next_action || 'LocalOS сохранил результат проверки и показывает, чего не хватает для следующего шага.'}
          </p>
          {nextAction ? (
            <Button onClick={nextAction.onClick} disabled={loading} className="mt-3 min-h-10 bg-orange-500 text-white hover:bg-orange-600 active:scale-[0.96] transition-transform">
              {nextAction.label}
            </Button>
          ) : null}
        </div>
      ) : (
        <div className="mt-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-xs text-slate-500">
            {parseRunning ? 'Можно заниматься другими лидами — статус обновится сам.' : 'Сейчас нужен только один следующий шаг.'}
          </p>
          {nextAction ? (
            <Button onClick={nextAction.onClick} disabled={loading} className="min-h-10 bg-orange-500 text-white hover:bg-orange-600 active:scale-[0.96] transition-transform">
              {nextAction.label}
            </Button>
          ) : parseRunning ? (
            <Button disabled className="min-h-10 bg-sky-100 text-sky-800">
              <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Собираем данные
            </Button>
          ) : null}
        </div>
      )}
    </section>
  );
};

const EditableLeadBasics = ({
  lead,
  loading,
  onSave,
}: {
  lead: PipelineLead;
  loading: boolean;
  onSave: (leadId: string, patch: LeadBasicsPatch) => Promise<void>;
}) => {
  const shouldStartEditing = isPlaceholderPartnerName(lead.name);
  const [isEditing, setIsEditing] = useState(shouldStartEditing);
  const [draft, setDraft] = useState<LeadBasicsPatch>(() => getLeadBasicsDraft(lead));

  useEffect(() => {
    setDraft(getLeadBasicsDraft(lead));
  }, [lead.id, lead.name, lead.category, lead.city, lead.address]);

  useEffect(() => {
    if (shouldStartEditing) setIsEditing(true);
  }, [lead.id, shouldStartEditing]);

  const hasChanges =
    draft.name !== String(lead.name || '').trim() ||
    draft.category !== String(lead.category || '').trim() ||
    draft.city !== String(lead.city || '').trim() ||
    draft.address !== String(lead.address || '').trim();

  const save = async () => {
    await onSave(lead.id, draft);
    setIsEditing(false);
  };

  if (!isEditing) {
    return (
      <div className="min-w-0">
        <div className="flex min-w-0 items-start gap-2">
          <div className="min-w-0 flex-1">
            <div className="break-words text-base font-semibold leading-snug text-foreground">{lead.name || 'Без названия'}</div>
            <div className="mt-1 line-clamp-2 text-sm text-slate-500">{lead.category || '—'} · {lead.city || '—'}</div>
            <div className="mt-1 line-clamp-1 text-sm text-slate-400">{lead.address || 'Адрес не указан'}</div>
          </div>
          <Button size="sm" variant="ghost" onClick={() => setIsEditing(true)} disabled={loading} className="shrink-0 text-slate-500">
            Править
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-sky-200 bg-sky-50/70 p-3">
      <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-sky-900">
        Данные партнёра
      </div>
      <div className="grid gap-2 md:grid-cols-2">
        <Input
          value={draft.name}
          onChange={(event) => setDraft((previous) => ({ ...previous, name: event.target.value }))}
          placeholder="Название партнёра"
          className="bg-white"
        />
        <Input
          value={draft.category}
          onChange={(event) => setDraft((previous) => ({ ...previous, category: event.target.value }))}
          placeholder="Категория"
          className="bg-white"
        />
        <Input
          value={draft.city}
          onChange={(event) => setDraft((previous) => ({ ...previous, city: event.target.value }))}
          placeholder="Город"
          className="bg-white"
        />
        <Input
          value={draft.address}
          onChange={(event) => setDraft((previous) => ({ ...previous, address: event.target.value }))}
          placeholder="Адрес"
          className="bg-white"
        />
      </div>
      <div className="mt-2 flex flex-wrap justify-end gap-2">
        {!shouldStartEditing ? (
          <Button size="sm" variant="ghost" onClick={() => { setDraft(getLeadBasicsDraft(lead)); setIsEditing(false); }} disabled={loading}>
            Отмена
          </Button>
        ) : null}
        <Button size="sm" onClick={() => void save()} disabled={loading || !draft.name.trim() || !hasChanges} className="bg-slate-950 text-white hover:bg-slate-800">
          Сохранить данные
        </Button>
      </div>
    </div>
  );
};

type PartnershipLeadCardProps = {
  lead: PipelineLead;
  mode: 'raw' | 'pipeline';
  dragging: boolean;
  loading: boolean;
  nextStage: string;
  deferredReasonInput: string;
  deferredUntilInput: string;
  stagePresentation: StagePresentation;
  auditPresentation: AuditPresentation;
  onDragStart?: DragEventHandler<HTMLDivElement>;
  onDragEnd?: DragEventHandler<HTMLDivElement>;
  onMoveToPipeline: (leadId: string) => void;
  onMoveToStage: (leadId: string, stage: string, deferred: DeferredPayload) => void;
  onOpenLead: (leadId: string) => void;
  onDeferLead: (lead: PipelineLead, deferred: DeferredPayload) => void;
};

export const PartnershipLeadCard = ({
  lead,
  mode,
  dragging,
  loading,
  nextStage,
  deferredReasonInput,
  deferredUntilInput,
  stagePresentation,
  auditPresentation,
  onDragStart,
  onDragEnd,
  onMoveToPipeline,
  onMoveToStage,
  onOpenLead,
  onDeferLead,
}: PartnershipLeadCardProps) => {
  const stageValue = String(lead.partnership_stage || '').toLowerCase();
  const pipelineStatus = String(lead.pipeline_status || '').toLowerCase();
  const isUnprocessed = !pipelineStatus || pipelineStatus === 'unprocessed' || pipelineStatus === 'qualified' || (!stageValue || stageValue === 'imported');
  const hasContacts = Boolean(lead.phone || lead.email || lead.telegram_url || lead.whatsapp_url || lead.website);
  const primaryActionLabel = mode === 'raw'
    ? (isUnprocessed ? 'В pipeline' : 'Открыть карточку')
    : nextStage
      ? 'Дальше'
      : 'Открыть карточку';
  const parseStatusLabel = String(lead.parse_status || '').toLowerCase() === 'completed'
    ? 'Парсинг готов'
    : String(lead.parse_status || '').toLowerCase() === 'error'
      ? 'Ошибка парсинга'
      : lead.parse_status || 'Парсинг не запускался';
  const deferredPayload = {
    deferredReason: deferredReasonInput.trim() || lead.deferred_reason || '',
    deferredUntil: deferredUntilInput || String(lead.deferred_until || '').slice(0, 10) || '',
  };

  return (
    <div
      draggable={mode === 'pipeline'}
      onDragStart={mode === 'pipeline' ? onDragStart : undefined}
      onDragEnd={mode === 'pipeline' ? onDragEnd : undefined}
      className={`overflow-hidden rounded-2xl border border-slate-200 bg-white p-3 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md ${dragging ? 'opacity-70' : ''}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="break-words text-base font-semibold leading-snug text-foreground">{lead.name || 'Без названия'}</div>
          <div className="mt-1 line-clamp-2 text-sm text-slate-500">
            {lead.category || 'Без категории'} · {lead.city || '—'}
          </div>
          <div className="mt-1 line-clamp-1 text-sm text-slate-400">
            {lead.address || 'Адрес не указан'}
          </div>
          {lead.client_business_name ? (
            <Badge variant="outline" className="mt-2 max-w-full truncate">Лид-партнёр · {lead.client_business_name}</Badge>
          ) : null}
        </div>
        <div className="flex max-w-[45%] shrink-0 flex-wrap justify-end gap-1">
          {lead.source_provider ? <Badge variant="outline" className="max-w-full truncate">{sourceProviderLabel(lead.source_provider)}</Badge> : null}
          {lead.rating ? <Badge variant="secondary">★ {lead.rating}{lead.reviews_count ? ` (${lead.reviews_count})` : ''}</Badge> : null}
        </div>
      </div>
      <div className="mt-3 flex flex-wrap gap-2 text-xs text-muted-foreground">
        <ContactPresenceBadges
          website={lead.website}
          phone={lead.phone}
          email={lead.email}
          telegramUrl={lead.telegram_url}
          whatsappUrl={lead.whatsapp_url}
          hasMessenger={Boolean(lead.telegram_url || lead.whatsapp_url)}
        />
      </div>
      <div className={`mt-3 grid gap-2 text-xs text-slate-600 ${mode === 'raw' ? '' : 'sm:grid-cols-2'}`}>
        <div className="min-w-0 rounded-xl border border-slate-200 bg-slate-50/80 px-3 py-2">
          <div className="flex items-center justify-between gap-2">
            <span className="font-medium uppercase text-slate-400">Статус</span>
            <Badge variant={stagePresentation.variant} className="max-w-[55%] truncate">{stagePresentation.label}</Badge>
          </div>
          <div className="mt-1 line-clamp-2 font-medium text-slate-900">
            {mode === 'raw' ? stagePresentation.helper : (lead.next_best_action?.label || 'Следующий шаг не определён')}
          </div>
          <div className={compactMetaClass}>
            {shortStatusLabel(lead.pipeline_status || 'unprocessed')} · {shortStatusLabel(lead.partnership_stage || 'imported')}
          </div>
        </div>
        {mode === 'pipeline' ? (
        <div className="min-w-0 rounded-xl border border-slate-200 bg-slate-50/80 px-3 py-2">
          <div className="flex items-center justify-between gap-2">
            <span className="font-medium uppercase text-slate-400">Аудит</span>
            <Badge variant={auditPresentation.variant} className="max-w-[55%] truncate">{auditPresentation.label}</Badge>
          </div>
          <div className="mt-1 line-clamp-2 font-medium text-slate-900">{auditPresentation.primary}</div>
          <div className={compactMetaClass}>{auditPresentation.secondary}</div>
        </div>
        ) : null}
      </div>
      {lead.parse_error ? <div className="mt-2 text-xs text-red-600">{lead.parse_error}</div> : null}
      <WorkflowActionRow
        primary={mode === 'raw' && isUnprocessed
          ? {
              label: primaryActionLabel,
              onClick: () => onMoveToPipeline(lead.id),
              disabled: loading,
            }
          : mode === 'pipeline' && nextStage
            ? {
                label: primaryActionLabel,
                onClick: () => onMoveToStage(lead.id, nextStage, { deferredReason: '', deferredUntil: '' }),
                disabled: loading,
              }
            : {
                label: primaryActionLabel,
                variant: 'outline',
                onClick: () => onOpenLead(lead.id),
              }}
        secondary={[
          { label: 'Карточка', onClick: () => onOpenLead(lead.id) },
          ...(lead.source_url ? [{ label: 'Источник', href: lead.source_url }] : []),
          {
            label: 'Неактуален',
            onClick: () => onMoveToStage(lead.id, 'not_relevant', { deferredReason: '', deferredUntil: '' }),
            disabled: loading,
          },
          ...(mode === 'pipeline' ? [{
            label: stageValue === 'deferred' ? 'Отложен' : 'Отложить',
            onClick: () => onDeferLead(lead, deferredPayload),
            disabled: loading,
          }] : []),
        ]}
      />
      <div className="mt-3 flex flex-wrap gap-2 text-[11px] text-muted-foreground">
        <span className={mutedPillClass}><span className="truncate">Воронка: {shortStatusLabel(lead.pipeline_status || 'unprocessed')}</span></span>
        {mode === 'pipeline' ? <span className={mutedPillClass}><span className="truncate">Этап: {shortStatusLabel(lead.partnership_stage || 'новый')}</span></span> : null}
        <span>{parseStatusLabel}</span>
        <span>{hasContacts ? 'контакты есть' : 'контактов мало'}</span>
      </div>
    </div>
  );
};

type PartnershipPipelineBoardProps = {
  columns: PipelineBoardColumn[];
  dropColumnId: string | null;
  draggingLeadId: string | null;
  loading: boolean;
  deferredReasonInput: string;
  deferredUntilInput: string;
  getStagePresentation: (lead: PipelineLead) => StagePresentation;
  getAuditPresentation: (lead: PipelineLead) => AuditPresentation;
  getNextStage: (lead: PipelineLead) => string;
  onColumnDragOver: (columnId: string) => DragEventHandler<HTMLDivElement>;
  onColumnDragLeave: () => void;
  onColumnDrop: (columnId: string) => DragEventHandler<HTMLDivElement>;
  onLeadDragStart: (leadId: string) => DragEventHandler<HTMLDivElement>;
  onLeadDragEnd: DragEventHandler<HTMLDivElement>;
  onMoveToPipeline: (leadId: string) => void;
  onMoveToStage: (leadId: string, stage: string, deferred: DeferredPayload) => void;
  onOpenLead: (leadId: string) => void;
  onDeferLead: (lead: PipelineLead, deferred: DeferredPayload) => void;
};

export const PartnershipPipelineBoard = ({
  columns,
  dropColumnId,
  draggingLeadId,
  loading,
  deferredReasonInput,
  deferredUntilInput,
  getStagePresentation,
  getAuditPresentation,
  getNextStage,
  onColumnDragOver,
  onColumnDragLeave,
  onColumnDrop,
  onLeadDragStart,
  onLeadDragEnd,
  onMoveToPipeline,
  onMoveToStage,
  onOpenLead,
  onDeferLead,
}: PartnershipPipelineBoardProps) => (
  <div className="flex gap-4 overflow-x-auto pb-2">
    {columns.map((column) => (
      <div
        key={column.id}
        onDragOver={onColumnDragOver(column.id)}
        onDragLeave={onColumnDragLeave}
        onDrop={onColumnDrop(column.id)}
        className={`min-w-[310px] flex-1 rounded-3xl border border-slate-200 bg-slate-50/70 p-3 transition ${dropColumnId === column.id ? 'ring-2 ring-primary/40' : ''}`}
      >
        <div className="flex items-start justify-between gap-2 px-1 pb-2">
          <div>
            <div className="text-sm font-semibold">{column.label}</div>
            <div className="text-xs text-muted-foreground">{column.description}</div>
          </div>
          <Badge variant="secondary">{column.leads.length}</Badge>
        </div>
        <div className="mt-3 space-y-3">
          {column.leads.length === 0 ? (
            <div className="rounded-lg border border-dashed border-border bg-background p-4 text-xs text-muted-foreground">
              Здесь пока нет лидов.
            </div>
          ) : (
            column.leads.map((lead) => (
              <PartnershipLeadCard
                key={lead.id}
                lead={lead}
                mode="pipeline"
                dragging={draggingLeadId === lead.id}
                loading={loading}
                nextStage={getNextStage(lead)}
                deferredReasonInput={deferredReasonInput}
                deferredUntilInput={deferredUntilInput}
                stagePresentation={getStagePresentation(lead)}
                auditPresentation={getAuditPresentation(lead)}
                onDragStart={onLeadDragStart(lead.id)}
                onDragEnd={onLeadDragEnd}
                onMoveToPipeline={onMoveToPipeline}
                onMoveToStage={onMoveToStage}
                onOpenLead={onOpenLead}
                onDeferLead={onDeferLead}
              />
            ))
          )}
        </div>
      </div>
    ))}
  </div>
);

type PartnershipPipelineListProps = {
  query: string;
  onQueryChange: (value: string) => void;
  stage: string;
  onStageChange: (value: string) => void;
  stageOptions: readonly Option[];
  pilotCohort: string;
  onPilotCohortChange: (value: string) => void;
  pilotCohortOptions: readonly Option[];
  leadView: string;
  onLeadViewChange: (value: string) => void;
  leadViewOptions: readonly Option[];
  leadBucket: 'active' | 'deferred';
  onLeadBucketChange: (value: 'active' | 'deferred') => void;
  loading: boolean;
  itemsTotal: number;
  shortlistCount: number;
  deferredLeadsCount: number;
  overdueDeferredLeadsCount: number;
  preferredSourceLabel: string | null;
  lastGeoSearchLeadCount: number;
  lastGeoSearchSourceLabel: string;
  lastGeoSearchMatchesBestSource: boolean;
  lastGeoSearchStats: Record<string, number> | null;
  lastGeoSearchFlowSummary: Record<string, number> | null;
  selectedLeadIds: string[];
  visibleLeads: PipelineLead[];
  selectedLeadId: string | null;
  activeLeadAction: LeadActionState | null;
  bulkStage: string;
  onBulkStageChange: (value: string) => void;
  bulkStageOptions: readonly Option[];
  bulkChannel: string;
  onBulkChannelChange: (value: string) => void;
  channelOptions: readonly Option[];
  bulkPilotCohort: string;
  onBulkPilotCohortChange: (value: string) => void;
  deferredReasonInput: string;
  onDeferredReasonInputChange: (value: string) => void;
  deferredUntilInput: string;
  onDeferredUntilInputChange: (value: string) => void;
  onRefreshLeads: () => void;
  onApplyBulkUpdate: () => void;
  onBulkDeferLeads: () => void;
  onBulkReturnDeferredLeads: () => void;
  onBulkReturnOverdueDeferredLeads: () => void;
  onBulkEnrichContacts: () => void;
  onBulkMarkNotRelevant: () => void;
  onNormalizeSelectedViaOpenClaw: () => void;
  onToggleAllLeadSelection: (checked: boolean) => void;
  onToggleLeadSelection: (leadId: string, checked: boolean) => void;
  onRunParse: (leadId: string) => void;
  onEnrichContacts: (leadId: string) => void;
  onRunAudit: (leadId: string) => void;
  onRunMatch: (leadId: string) => void;
  onOpenLead: (leadId: string) => void;
  onPrepareSalesRoom: (leadId: string, dataMode: 'audited' | 'template') => void;
  onMarkManualContact: (leadId: string) => void;
  onSaveLeadBasics: (leadId: string, patch: LeadBasicsPatch) => Promise<void>;
  onUpdateLeadStage: (leadId: string, stage: string, message: string, deferred: DeferredPayload) => void;
  onDeleteLead: (leadId: string) => void;
  onClearLastGeoSearch: () => void;
  onMoveLastGeoSearchToPilot: () => void;
  onRunLastGeoSearchFlow: () => void;
  onPrepareLastGeoSearchBatch: () => void;
};

export const PartnershipPipelineList = ({
  query,
  onQueryChange,
  stage,
  onStageChange,
  stageOptions,
  pilotCohort,
  onPilotCohortChange,
  pilotCohortOptions,
  leadView,
  onLeadViewChange,
  leadViewOptions,
  leadBucket,
  onLeadBucketChange,
  loading,
  itemsTotal,
  shortlistCount,
  deferredLeadsCount,
  overdueDeferredLeadsCount,
  preferredSourceLabel,
  lastGeoSearchLeadCount,
  lastGeoSearchSourceLabel,
  lastGeoSearchMatchesBestSource,
  lastGeoSearchStats,
  lastGeoSearchFlowSummary,
  selectedLeadIds,
  visibleLeads,
  selectedLeadId,
  activeLeadAction,
  bulkStage,
  onBulkStageChange,
  bulkStageOptions,
  bulkChannel,
  onBulkChannelChange,
  channelOptions,
  bulkPilotCohort,
  onBulkPilotCohortChange,
  deferredReasonInput,
  onDeferredReasonInputChange,
  deferredUntilInput,
  onDeferredUntilInputChange,
  onRefreshLeads,
  onApplyBulkUpdate,
  onBulkDeferLeads,
  onBulkReturnDeferredLeads,
  onBulkReturnOverdueDeferredLeads,
  onBulkEnrichContacts,
  onBulkMarkNotRelevant,
  onNormalizeSelectedViaOpenClaw,
  onToggleAllLeadSelection,
  onToggleLeadSelection,
  onRunParse,
  onEnrichContacts,
  onRunAudit,
  onRunMatch,
  onOpenLead,
  onPrepareSalesRoom,
  onMarkManualContact,
  onSaveLeadBasics,
  onUpdateLeadStage,
  onDeleteLead,
  onClearLastGeoSearch,
  onMoveLastGeoSearchToPilot,
  onRunLastGeoSearchFlow,
  onPrepareLastGeoSearchBatch,
}: PartnershipPipelineListProps) => (
  <div className="rounded-3xl border border-slate-200/80 bg-white/95 p-5 shadow-sm xl:col-span-12">
    <div className="mb-5 flex flex-col gap-3">
      <div className="flex flex-col gap-1">
        <h2 className="text-xl font-semibold text-slate-950">Отбор партнёров</h2>
        <p className="text-sm text-slate-500">Выберите подходящих, закрепите канал и подготовьте письмо. Технические детали спрятаны внутри карточки.</p>
      </div>
      <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_220px_180px_240px_auto]">
      <Input value={query} onChange={(event) => onQueryChange(event.target.value)} placeholder="Поиск по названию/ссылке" />
      <Select value={stage} onValueChange={onStageChange}>
        <SelectTrigger>
          <SelectValue placeholder="Этап" />
        </SelectTrigger>
        <SelectContent>
          {stageOptions.map((option) => <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>)}
        </SelectContent>
      </Select>
      <Select value={pilotCohort} onValueChange={onPilotCohortChange}>
        <SelectTrigger><SelectValue placeholder="Когорта" /></SelectTrigger>
        <SelectContent>
          {pilotCohortOptions.map((option) => <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>)}
        </SelectContent>
      </Select>
      <Select value={leadView} onValueChange={onLeadViewChange}>
        <SelectTrigger><SelectValue placeholder="Фильтр" /></SelectTrigger>
        <SelectContent>
          {leadViewOptions.map((option) => <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>)}
        </SelectContent>
      </Select>
      <Button variant="outline" onClick={onRefreshLeads} disabled={loading}>Обновить</Button>
      </div>
    </div>

    <div className="mb-3 flex flex-wrap gap-2">
      <Button size="sm" variant={leadBucket === 'active' ? 'default' : 'outline'} onClick={() => onLeadBucketChange('active')}>В работе</Button>
      <Button size="sm" variant={leadBucket === 'deferred' ? 'default' : 'outline'} onClick={() => onLeadBucketChange('deferred')}>Отложенные</Button>
      {leadViewOptions.filter((option) => ['all', 'ready_for_letter', 'with_contacts', 'deferred', 'errors'].includes(option.value)).map((option) => (
        <Button key={`lead-chip-${option.value}`} size="sm" variant={leadView === option.value ? 'default' : 'outline'} onClick={() => onLeadViewChange(option.value)}>
          {option.label}
        </Button>
      ))}
    </div>

    <div className="mb-4 rounded-2xl border border-slate-200 bg-slate-50/70 px-4 py-3">
      <div className="flex flex-wrap items-center gap-3 text-sm text-slate-600">
        <span>Всего: <span className="font-semibold text-slate-950">{itemsTotal}</span></span>
        <span>В работе: <span className="font-semibold text-slate-950">{shortlistCount}</span></span>
        <span>Отложены: <span className="font-semibold text-amber-800">{deferredLeadsCount}</span></span>
        {overdueDeferredLeadsCount > 0 ? (
          <Button size="sm" variant="outline" onClick={onBulkReturnOverdueDeferredLeads} disabled={loading}>Вернуть просроченные: {overdueDeferredLeadsCount}</Button>
        ) : null}
      </div>
    </div>

    {leadView === 'best_source' && preferredSourceLabel ? (
      <div className="mb-4 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-800">
        Активен фильтр по лучшему источнику недели: {preferredSourceLabel}
      </div>
    ) : null}

    {leadView === 'last_geo_search' ? (
      <div className="mb-4 rounded-lg border border-sky-200 bg-sky-50 px-3 py-3 text-xs text-sky-800">
        <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
          <div>
            <div className="font-medium text-sky-900">Активен фильтр по последнему поиску на картах: {lastGeoSearchLeadCount} лидов.</div>
            <div className="mt-1 text-[11px] text-sky-800">Можно сразу запустить цепочку: обогащение → аудит → подбор оффера → письмо только по этим новым лидам.</div>
            <div className="mt-1 text-[11px] text-sky-800">Источник: {lastGeoSearchSourceLabel}{lastGeoSearchMatchesBestSource ? ' · совпадает с лучшим источником недели' : ''}</div>
            {lastGeoSearchStats ? (
              <div className="mt-2 flex flex-wrap gap-2 text-[11px]">
                <span className="rounded-full border border-sky-200 bg-white px-2 py-0.5">всего {lastGeoSearchStats.total}</span>
                <span className="rounded-full border border-sky-200 bg-white px-2 py-0.5">парсинг готов {lastGeoSearchStats.parsedCompleted}</span>
                <span className="rounded-full border border-sky-200 bg-white px-2 py-0.5">обогащено {lastGeoSearchStats.enriched}</span>
                <span className="rounded-full border border-sky-200 bg-white px-2 py-0.5">с контактами {lastGeoSearchStats.withContacts}</span>
                <span className="rounded-full border border-sky-200 bg-white px-2 py-0.5">готовы к письму {lastGeoSearchStats.readyForDraft}</span>
              </div>
            ) : null}
            {lastGeoSearchFlowSummary ? (
              <div className="mt-2 flex flex-wrap gap-2 text-[11px]">
                <span className="rounded-full border border-indigo-200 bg-white px-2 py-0.5">аудит {lastGeoSearchFlowSummary.audited}</span>
                <span className="rounded-full border border-indigo-200 bg-white px-2 py-0.5">оффер подобран {lastGeoSearchFlowSummary.matched}</span>
                <span className="rounded-full border border-indigo-200 bg-white px-2 py-0.5">письмо готово {lastGeoSearchFlowSummary.draftReady}</span>
                <span className="rounded-full border border-indigo-200 bg-white px-2 py-0.5">письмо утверждено {lastGeoSearchFlowSummary.draftsApproved}</span>
                <span className="rounded-full border border-indigo-200 bg-white px-2 py-0.5">в очереди {lastGeoSearchFlowSummary.queued}</span>
                <span className="rounded-full border border-indigo-200 bg-white px-2 py-0.5">отправлено {lastGeoSearchFlowSummary.sent}</span>
                <span className="rounded-full border border-indigo-200 bg-white px-2 py-0.5">интерес {lastGeoSearchFlowSummary.positive}</span>
              </div>
            ) : null}
          </div>
          <div className="flex flex-wrap gap-2">
            <Button size="sm" variant="outline" onClick={onBulkEnrichContacts} disabled={loading || selectedLeadIds.length === 0}>Обогатить контакты</Button>
            <Button size="sm" variant="outline" onClick={onMoveLastGeoSearchToPilot} disabled={loading || lastGeoSearchLeadCount === 0}>В пилотную группу</Button>
            <Button size="sm" variant="outline" onClick={onRunLastGeoSearchFlow} disabled={loading || lastGeoSearchLeadCount === 0}>Быстрый сценарий</Button>
            <Button size="sm" variant="outline" onClick={onPrepareLastGeoSearchBatch} disabled={loading || lastGeoSearchLeadCount === 0}>Подготовить очередь</Button>
            <Button size="sm" variant="outline" onClick={onClearLastGeoSearch} disabled={loading}>Сбросить фильтр</Button>
          </div>
        </div>
      </div>
    ) : null}

    <div className="mb-4 rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
      <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
        <div>
          <div className="text-sm font-semibold text-foreground">Действия с выбранными</div>
          <div className="text-xs text-muted-foreground">Выбрано: {selectedLeadIds.length}. Основные действия оставлены на виду, остальное доступно внутри карточки.</div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Select value={bulkStage} onValueChange={onBulkStageChange}>
            <SelectTrigger className="w-[220px] bg-white"><SelectValue placeholder="Статус воронки" /></SelectTrigger>
            <SelectContent>{bulkStageOptions.map((option) => <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>)}</SelectContent>
          </Select>
          <Select value={bulkChannel} onValueChange={onBulkChannelChange}>
            <SelectTrigger className="w-[200px] bg-white"><SelectValue placeholder="Канал для выбранных" /></SelectTrigger>
            <SelectContent>{channelOptions.map((option) => <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>)}</SelectContent>
          </Select>
          <Select value={bulkPilotCohort} onValueChange={onBulkPilotCohortChange}>
            <SelectTrigger className="w-[180px] bg-white"><SelectValue placeholder="Когорта" /></SelectTrigger>
            <SelectContent>{pilotCohortOptions.filter((option) => option.value !== 'all').map((option) => <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>)}</SelectContent>
          </Select>
          <Button variant="outline" onClick={onApplyBulkUpdate} disabled={loading || selectedLeadIds.length === 0}>Применить к выбранным</Button>
          <Button variant="outline" onClick={onBulkDeferLeads} disabled={loading || selectedLeadIds.length === 0}>Отложить выбранные</Button>
          <Button variant="outline" onClick={onNormalizeSelectedViaOpenClaw} disabled={loading || selectedLeadIds.length === 0}>Подготовить письма</Button>
          <Button variant="outline" onClick={onBulkMarkNotRelevant} disabled={loading || selectedLeadIds.length === 0}>Неактуальны</Button>
        </div>
      </div>
      <div className="mt-3 grid gap-2 md:grid-cols-[minmax(0,1fr)_220px_auto]">
        <Input value={deferredReasonInput} onChange={(event) => onDeferredReasonInputChange(event.target.value)} placeholder="Причина откладывания: например, не сезон, вернуться через 2 недели, нужен другой оффер" className="bg-white" />
        <Input type="date" value={deferredUntilInput} onChange={(event) => onDeferredUntilInputChange(event.target.value)} className="bg-white" />
        <div className="self-center text-xs text-muted-foreground">Используется для массового и одиночного откладывания</div>
      </div>
    </div>

    <div className="space-y-3">
      {visibleLeads.length === 0 ? (
        <p className="text-sm text-muted-foreground">Список пуст.</p>
      ) : (
        <>
          <label className="flex items-center gap-2 text-sm text-muted-foreground">
            <input type="checkbox" checked={visibleLeads.length > 0 && visibleLeads.every((lead) => selectedLeadIds.includes(lead.id))} onChange={(event) => onToggleAllLeadSelection(event.target.checked)} />
            Выбрать все в текущем фильтре
          </label>
          {visibleLeads.map((lead) => (
            <div key={lead.id} className={`overflow-hidden rounded-2xl border bg-white p-4 shadow-sm transition hover:shadow-md ${selectedLeadId === lead.id ? 'border-primary/70 ring-2 ring-primary/10' : 'border-slate-200'}`}>
              <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div className="flex min-w-0 flex-1 items-start gap-3">
                  <input className="mt-1" type="checkbox" checked={selectedLeadIds.includes(lead.id)} onChange={(event) => onToggleLeadSelection(lead.id, event.target.checked)} />
                  <div className="min-w-0 flex-1">
                    <EditableLeadBasics lead={lead} loading={loading} onSave={onSaveLeadBasics} />
                    {lead.deferred_reason ? <div className="mt-1 rounded-md border border-amber-200 bg-amber-50 px-2 py-1 text-xs text-amber-900">Отложено: {lead.deferred_reason}</div> : null}
                    {lead.deferred_until ? <div className="mt-1 text-xs text-amber-800">Вернуться: {new Date(String(lead.deferred_until)).toLocaleDateString('ru-RU')}</div> : null}
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      <span className={mutedPillClass}><span className="truncate">Воронка: {shortStatusLabel(lead.pipeline_status || 'unprocessed')}</span></span>
                      <span className={mutedPillClass}><span className="truncate">Этап: {shortStatusLabel(lead.partnership_stage || 'новый')}</span></span>
                      <span className={mutedPillClass}><span className="truncate">Когорта: {lead.pilot_cohort || 'резерв'}</span></span>
                      {lead.client_business_name ? <span className={mutedPillClass}><span className="max-w-[220px] truncate">Лид-партнёр · {lead.client_business_name}</span></span> : null}
                      {lead.source_provider ? <span className={mutedPillClass}><span className="max-w-[180px] truncate">{sourceProviderLabel(lead.source_provider)}</span></span> : null}
                      {lead.rating ? <span className={mutedPillClass}>★ {lead.rating}{lead.reviews_count ? ` · ${lead.reviews_count}` : ''}</span> : null}
                    </div>
                    <div className="mt-2 flex flex-wrap gap-2 text-xs">
                      <span className={lead.phone ? 'text-emerald-700' : 'text-slate-400'}>Телефон {lead.phone ? '✓' : '—'}</span>
                      <span className={lead.email ? 'text-emerald-700' : 'text-slate-400'}>Email {lead.email ? '✓' : '—'}</span>
                      <span className={lead.telegram_url ? 'text-emerald-700' : 'text-slate-400'}>Telegram {lead.telegram_url ? '✓' : '—'}</span>
                      <span className={lead.whatsapp_url ? 'text-emerald-700' : 'text-slate-400'}>WhatsApp {lead.whatsapp_url ? '✓' : '—'}</span>
                    </div>
                    <LeadPreparationGuide
                      lead={lead}
                      loading={loading}
                      activeLeadAction={activeLeadAction}
                      onRunParse={onRunParse}
                      onRunAudit={onRunAudit}
                      onRunMatch={onRunMatch}
                      onOpenLead={onOpenLead}
                    />
                    {leadHasMatchResult(lead) ? <div className="mt-3 rounded-xl bg-orange-50/70 px-3 py-3 shadow-[inset_0_0_0_1px_rgba(249,115,22,0.18)]">
                      <div className="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
                        <div>
                          <div className="text-xs font-semibold uppercase tracking-wide text-orange-800">Следующий шаг</div>
                          <div className="mt-1 text-sm font-semibold text-orange-950">Подготовить предложение для партнёра</div>
                          <div className="mt-1 text-[11px] leading-relaxed text-orange-800">
                            LocalOS соберёт найденные факты, совместимость и следующий шаг в одну страницу. Перед отправкой вы всё проверите.
                          </div>
                          {lead.sales_room_status ? (
                            <div className="mt-1 text-[11px] font-medium text-emerald-700">Предложение уже подготовлено</div>
                          ) : null}
                        </div>
                        <div className="flex flex-wrap gap-2 xl:justify-end">
                          {lead.sales_room_url ? (
                            <Button size="sm" variant="outline" onClick={() => window.open(lead.sales_room_url, '_blank', 'noopener,noreferrer')} disabled={loading}>
                              Открыть комнату
                            </Button>
                          ) : null}
                          <Button size="sm" onClick={() => onPrepareSalesRoom(lead.id, 'audited')} disabled={loading} className="min-h-10 bg-orange-500 text-white hover:bg-orange-600 active:scale-[0.96] transition-transform">
                            Подготовить предложение
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            className="min-h-10 bg-white"
                            onClick={() => onMarkManualContact(lead.id)}
                            disabled={loading}
                          >
                            Отправлено вручную
                          </Button>
                        </div>
                      </div>
                    </div> : null}
                    <details className="mt-3 text-xs text-slate-500">
                      <summary className="flex min-h-10 cursor-pointer items-center font-medium text-slate-500">Дополнительные действия и технические детали</summary>
                      <div className="mt-2 space-y-1 rounded-xl bg-slate-50 p-3">
                        <div>Парсинг: {lead.parse_status || 'не запускался'}{lead.parse_updated_at ? ` · ${new Date(lead.parse_updated_at).toLocaleString('ru-RU')}` : ''}</div>
                        {Array.isArray(lead.matching_sources_json) && lead.matching_sources_json.length > 1 ? <div>Объединено источников: {lead.matching_sources_json.length}</div> : null}
                        {lead.enrich_payload_json?.provider ? <div>Источник данных: {lead.enrich_payload_json.provider}</div> : null}
                        {lead.parse_error ? <div className="text-red-600">{lead.parse_error}</div> : null}
                        {lead.source_url ? <a href={lead.source_url} target="_blank" rel="noreferrer" className="break-all text-blue-600 underline">Открыть источник</a> : null}
                        <div className="flex flex-wrap gap-2 pt-3">
                          <Button variant="outline" size="sm" onClick={() => onPrepareSalesRoom(lead.id, 'template')} disabled={loading}>Предложение без подготовки данных</Button>
                          <Button variant="outline" size="sm" onClick={() => onUpdateLeadStage(lead.id, 'postponed', 'Партнёр отложен на потом', { deferredReason: deferredReasonInput.trim() || lead.deferred_reason || '', deferredUntil: deferredUntilInput || String(lead.deferred_until || '').slice(0, 10) || '' })} disabled={loading}>Отложить</Button>
                          <Button variant="outline" size="sm" onClick={() => onUpdateLeadStage(lead.id, 'not_relevant', 'Партнёр помечен как неактуальный', { deferredReason: '', deferredUntil: '' })} disabled={loading}>Неактуален</Button>
                          <Button variant="outline" size="sm" onClick={() => onDeleteLead(lead.id)} disabled={loading}>Удалить</Button>
                        </div>
                      </div>
                    </details>
                  </div>
                </div>
                <div className="flex shrink-0 flex-wrap gap-2 lg:max-w-[360px] lg:justify-end">
                  <Button variant="outline" size="sm" className="min-h-10" onClick={() => onOpenLead(lead.id)} disabled={loading}>Вся информация</Button>
                  <Button variant="outline" size="sm" className="min-h-10" onClick={() => onEnrichContacts(lead.id)} disabled={loading}>
                    {activeLeadAction?.leadId === lead.id && activeLeadAction.action === 'enrich' ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                    Найти контакты
                  </Button>
                  {['', 'unprocessed', 'postponed'].includes(String(lead.pipeline_status || '').toLowerCase()) || String(lead.partnership_stage || '').toLowerCase() === 'deferred' ? (
                    <Button size="sm" className="min-h-10 bg-slate-950 text-white hover:bg-slate-800" onClick={() => onUpdateLeadStage(lead.id, 'in_progress', 'Партнёр добавлен в работу', { deferredReason: '', deferredUntil: '' })} disabled={loading}>
                      {String(lead.pipeline_status || '').toLowerCase() === 'postponed' || String(lead.partnership_stage || '').toLowerCase() === 'deferred' ? 'Вернуть в работу' : 'Взять в работу'}
                    </Button>
                  ) : null}
                </div>
              </div>
            </div>
          ))}
        </>
      )}
    </div>
  </div>
);

type PartnershipPipelineBulkBarProps = {
  selectedCount: number;
  loading: boolean;
  canApplyStageOrChannel: boolean;
  onBulkRunParse: () => void;
  onBulkEnrichContacts: () => void;
  onBulkRunMatch: () => void;
  onApplyBulkUpdate: () => void;
  onNormalizeSelectedViaOpenClaw: () => void;
  onBulkPrepareCommercialOffers: () => void;
  onBulkDeleteLeads: () => void;
};

export const PartnershipPipelineBulkBar = ({
  selectedCount,
  loading,
  canApplyStageOrChannel,
  onBulkRunParse,
  onBulkEnrichContacts,
  onBulkRunMatch,
  onApplyBulkUpdate,
  onNormalizeSelectedViaOpenClaw,
  onBulkPrepareCommercialOffers,
  onBulkDeleteLeads,
}: PartnershipPipelineBulkBarProps) => {
  if (selectedCount === 0) return null;

  return (
    <div className="fixed inset-x-0 bottom-0 z-40 border-t border-amber-200 bg-amber-50/95 backdrop-blur">
      <div className="mx-auto flex max-w-[1400px] flex-wrap items-center gap-2 px-4 py-3">
        <span className="text-sm font-medium text-foreground">Выбрано: {selectedCount}</span>
        <Button size="sm" variant="outline" onClick={onBulkRunParse} disabled={loading}>Парсинг</Button>
        <Button size="sm" variant="outline" onClick={onBulkEnrichContacts} disabled={loading}>Обогатить</Button>
        <Button size="sm" variant="outline" onClick={onBulkRunMatch} disabled={loading}>Матчинг</Button>
        <Button size="sm" variant="outline" onClick={onApplyBulkUpdate} disabled={loading || !canApplyStageOrChannel}>Применить этап/канал</Button>
        <Button size="sm" variant="outline" onClick={onNormalizeSelectedViaOpenClaw} disabled={loading}>Подготовить письма</Button>
        <Button size="sm" variant="outline" onClick={onBulkPrepareCommercialOffers} disabled={loading}>Подготовить КП</Button>
        <Button size="sm" variant="outline" onClick={onBulkDeleteLeads} disabled={loading}>Удалить</Button>
      </div>
    </div>
  );
};
