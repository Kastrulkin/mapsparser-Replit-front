import type { DragEventHandler } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { ContactPresenceBadges, StatusSummaryCard, WorkflowActionRow } from '@/components/prospecting/LeadWorkflowBlocks';

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
  pilot_cohort?: string;
  rating?: number;
  reviews_count?: number;
  parse_status?: string;
  parse_updated_at?: string;
  parse_retry_after?: string;
  parse_error?: string;
  deferred_reason?: string;
  deferred_until?: string;
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

const mutedPillClass = 'inline-flex items-center rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-[11px] font-medium text-slate-600';

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
  const hasContacts = Boolean(lead.phone || lead.email || lead.telegram_url || lead.whatsapp_url || lead.website);
  const primaryActionLabel = mode === 'raw'
    ? (!stageValue || stageValue === 'imported' ? 'В pipeline' : 'Открыть карточку')
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
      className={`rounded-2xl border border-slate-200 bg-white p-4 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md ${dragging ? 'opacity-70' : ''}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-base font-semibold text-foreground">{lead.name || 'Без названия'}</div>
          <div className="mt-1 text-sm text-slate-500">
            {lead.category || 'Без категории'} · {lead.city || '—'}
          </div>
          <div className="mt-1 line-clamp-1 text-sm text-slate-400">
            {lead.address || 'Адрес не указан'}
          </div>
        </div>
        <div className="flex flex-wrap justify-end gap-1">
          {lead.source_provider ? <Badge variant="outline">{lead.source_provider}</Badge> : null}
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
      <div className="mt-3 space-y-3">
        <StatusSummaryCard
          title="Статус"
          statusLabel={stagePresentation.label}
          statusVariant={stagePresentation.variant}
          tone={stagePresentation.tone}
          primaryText={mode === 'raw' ? stagePresentation.helper : (lead.next_best_action?.label || 'Следующий шаг пока не определён')}
          secondaryText={mode === 'raw'
            ? `Текущий этап: ${lead.partnership_stage || 'imported'}`
            : (lead.next_best_action?.hint || 'Продолжайте по текущему pipeline без лишних промежуточных шагов.')}
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
      {lead.parse_error ? <div className="mt-2 text-xs text-red-600">{lead.parse_error}</div> : null}
      <WorkflowActionRow
        primary={mode === 'raw' && (!stageValue || stageValue === 'imported')
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
            label: stageValue === 'deferred' ? 'Отложен' : 'Отложить',
            onClick: () => onDeferLead(lead, deferredPayload),
            disabled: loading,
          },
        ]}
      />
      <div className="mt-3 flex flex-wrap gap-2 text-[11px] text-muted-foreground">
        <span className={mutedPillClass}>Этап: {lead.partnership_stage || 'новый'}</span>
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
  onLoadHealth: () => void;
  onApplyBulkUpdate: () => void;
  onBulkDeferLeads: () => void;
  onBulkReturnDeferredLeads: () => void;
  onBulkReturnOverdueDeferredLeads: () => void;
  onBulkEnrichContacts: () => void;
  onNormalizeSelectedViaOpenClaw: () => void;
  onBulkDeleteLeads: () => void;
  onToggleAllLeadSelection: (checked: boolean) => void;
  onToggleLeadSelection: (leadId: string, checked: boolean) => void;
  onRunParse: (leadId: string) => void;
  onEnrichContacts: (leadId: string) => void;
  onRunAudit: (leadId: string) => void;
  onRunMatch: (leadId: string) => void;
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
  onLoadHealth,
  onApplyBulkUpdate,
  onBulkDeferLeads,
  onBulkReturnDeferredLeads,
  onBulkReturnOverdueDeferredLeads,
  onBulkEnrichContacts,
  onNormalizeSelectedViaOpenClaw,
  onBulkDeleteLeads,
  onToggleAllLeadSelection,
  onToggleLeadSelection,
  onRunParse,
  onEnrichContacts,
  onRunAudit,
  onRunMatch,
  onUpdateLeadStage,
  onDeleteLead,
  onClearLastGeoSearch,
  onMoveLastGeoSearchToPilot,
  onRunLastGeoSearchFlow,
  onPrepareLastGeoSearchBatch,
}: PartnershipPipelineListProps) => (
  <div className="rounded-3xl border border-slate-200/80 bg-white/95 p-5 shadow-sm xl:col-span-7">
    <div className="mb-5 flex flex-col gap-3">
      <div className="flex flex-col gap-1">
        <h2 className="text-xl font-semibold text-slate-950">Рабочий список партнёров</h2>
        <p className="text-sm text-slate-500">Короткий список для оператора: кто подходит, что с контактами и какое безопасное действие дальше.</p>
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
      {leadViewOptions.slice(0, 6).map((option) => (
        <Button key={`lead-chip-${option.value}`} size="sm" variant={leadView === option.value ? 'default' : 'outline'} onClick={() => onLeadViewChange(option.value)}>
          {option.label}
        </Button>
      ))}
    </div>

    <div className="mb-4 grid gap-3 md:grid-cols-3">
      <div className="rounded-2xl border border-slate-200 bg-slate-50/70 px-4 py-3">
        <div className="text-xs uppercase tracking-wide text-muted-foreground">Найдено компаний</div>
        <div className="mt-1 text-2xl font-semibold">{itemsTotal}</div>
      </div>
      <div className="rounded-2xl border border-slate-200 bg-slate-50/70 px-4 py-3">
        <div className="text-xs uppercase tracking-wide text-muted-foreground">Готовы к работе</div>
        <div className="mt-1 text-2xl font-semibold text-violet-900">{shortlistCount}</div>
      </div>
      <div className="rounded-2xl border border-amber-200 bg-amber-50/70 px-4 py-3">
        <div className="text-xs uppercase tracking-wide text-amber-700">Отложенные</div>
        <div className="mt-1 flex items-center justify-between gap-3">
          <div className="text-2xl font-semibold text-amber-900">{deferredLeadsCount}</div>
          <Button size="sm" variant={leadView === 'deferred' ? 'default' : 'outline'} onClick={() => onLeadViewChange('deferred')}>Только отложенные</Button>
        </div>
        <div className="mt-2 text-xs text-amber-800">Просрочено к возврату: <span className="font-semibold">{overdueDeferredLeadsCount}</span></div>
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
            <div className="font-medium text-sky-900">Активен фильтр по последнему geo-search: {lastGeoSearchLeadCount} лидов.</div>
            <div className="mt-1 text-[11px] text-sky-800">Можно сразу запустить цепочку: обогащение → аудит → матчинг → черновик только по этим новым лидам.</div>
            <div className="mt-1 text-[11px] text-sky-800">Источник: {lastGeoSearchSourceLabel}{lastGeoSearchMatchesBestSource ? ' · совпадает с лучшим источником недели' : ''}</div>
            {lastGeoSearchStats ? (
              <div className="mt-2 flex flex-wrap gap-2 text-[11px]">
                <span className="rounded-full border border-sky-200 bg-white px-2 py-0.5">всего {lastGeoSearchStats.total}</span>
                <span className="rounded-full border border-sky-200 bg-white px-2 py-0.5">парсинг готов {lastGeoSearchStats.parsedCompleted}</span>
                <span className="rounded-full border border-sky-200 bg-white px-2 py-0.5">обогащено {lastGeoSearchStats.enriched}</span>
                <span className="rounded-full border border-sky-200 bg-white px-2 py-0.5">с контактами {lastGeoSearchStats.withContacts}</span>
                <span className="rounded-full border border-sky-200 bg-white px-2 py-0.5">готовы к черновику {lastGeoSearchStats.readyForDraft}</span>
              </div>
            ) : null}
            {lastGeoSearchFlowSummary ? (
              <div className="mt-2 flex flex-wrap gap-2 text-[11px]">
                <span className="rounded-full border border-indigo-200 bg-white px-2 py-0.5">аудит {lastGeoSearchFlowSummary.audited}</span>
                <span className="rounded-full border border-indigo-200 bg-white px-2 py-0.5">матчинг {lastGeoSearchFlowSummary.matched}</span>
                <span className="rounded-full border border-indigo-200 bg-white px-2 py-0.5">черновик готов {lastGeoSearchFlowSummary.draftReady}</span>
                <span className="rounded-full border border-indigo-200 bg-white px-2 py-0.5">черновик утверждён {lastGeoSearchFlowSummary.draftsApproved}</span>
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
          <div className="text-xs text-muted-foreground">Выбрано: {selectedLeadIds.length}. Показываем только массовые действия, которые меняют рабочее состояние партнёров.</div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Select value={bulkStage} onValueChange={onBulkStageChange}>
            <SelectTrigger className="w-[220px] bg-white"><SelectValue placeholder="Этап для выбранных" /></SelectTrigger>
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
          <Button variant="outline" onClick={onBulkReturnDeferredLeads} disabled={loading || selectedLeadIds.length === 0}>Вернуть в работу</Button>
          <Button variant="outline" onClick={onBulkReturnOverdueDeferredLeads} disabled={loading || overdueDeferredLeadsCount === 0}>Вернуть просроченные</Button>
          <Button variant="outline" onClick={onBulkEnrichContacts} disabled={loading || selectedLeadIds.length === 0}>Обогатить контакты</Button>
          <Button variant="outline" onClick={onNormalizeSelectedViaOpenClaw} disabled={loading || selectedLeadIds.length === 0}>Подготовить черновики</Button>
          <Button variant="outline" onClick={onLoadHealth} disabled={loading}>Проверить поток</Button>
          <Button variant="outline" onClick={onBulkDeleteLeads} disabled={loading || selectedLeadIds.length === 0}>Удалить</Button>
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
            <div key={lead.id} className={`rounded-2xl border bg-white p-4 shadow-sm transition hover:shadow-md ${selectedLeadId === lead.id ? 'border-primary/70 ring-2 ring-primary/10' : 'border-slate-200'}`}>
              <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div className="flex items-start gap-3">
                  <input className="mt-1" type="checkbox" checked={selectedLeadIds.includes(lead.id)} onChange={(event) => onToggleLeadSelection(lead.id, event.target.checked)} />
                  <div className="min-w-0">
                    <div className="text-base font-semibold text-foreground">{lead.name || 'Без названия'}</div>
                    <div className="mt-1 text-sm text-slate-500">{lead.category || '—'} · {lead.city || '—'}</div>
                    <div className="mt-1 line-clamp-1 text-sm text-slate-400">{lead.address || 'Адрес не указан'}</div>
                    {lead.deferred_reason ? <div className="mt-1 rounded-md border border-amber-200 bg-amber-50 px-2 py-1 text-xs text-amber-900">Отложено: {lead.deferred_reason}</div> : null}
                    {lead.deferred_until ? <div className="mt-1 text-xs text-amber-800">Вернуться: {new Date(String(lead.deferred_until)).toLocaleDateString('ru-RU')}</div> : null}
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      <span className={mutedPillClass}>Этап: {lead.partnership_stage || 'новый'}</span>
                      <span className={mutedPillClass}>Когорта: {lead.pilot_cohort || 'резерв'}</span>
                      {lead.source_provider ? <span className={mutedPillClass}>{lead.source_provider}</span> : null}
                      {lead.rating ? <span className={mutedPillClass}>★ {lead.rating}{lead.reviews_count ? ` · ${lead.reviews_count}` : ''}</span> : null}
                    </div>
                    <div className="mt-2 flex flex-wrap gap-2 text-xs">
                      <span className={lead.phone ? 'text-emerald-700' : 'text-slate-400'}>Телефон {lead.phone ? '✓' : '—'}</span>
                      <span className={lead.email ? 'text-emerald-700' : 'text-slate-400'}>Email {lead.email ? '✓' : '—'}</span>
                      <span className={lead.telegram_url ? 'text-emerald-700' : 'text-slate-400'}>Telegram {lead.telegram_url ? '✓' : '—'}</span>
                      <span className={lead.whatsapp_url ? 'text-emerald-700' : 'text-slate-400'}>WhatsApp {lead.whatsapp_url ? '✓' : '—'}</span>
                    </div>
                    {lead.next_best_action ? (
                      <div className="mt-3 rounded-xl border border-sky-100 bg-sky-50/70 px-3 py-2">
                        <div className="text-xs font-semibold text-sky-900">Следующее действие: {lead.next_best_action.label || '—'}</div>
                        <div className="mt-0.5 text-[11px] text-sky-800">{lead.next_best_action.hint || '—'}</div>
                      </div>
                    ) : null}
                    <details className="mt-3 text-xs text-slate-500">
                      <summary className="cursor-pointer font-medium text-slate-500">Технические детали</summary>
                      <div className="mt-2 space-y-1 rounded-xl bg-slate-50 p-3">
                        <div>Парсинг: {lead.parse_status || 'не запускался'}{lead.parse_updated_at ? ` · ${new Date(lead.parse_updated_at).toLocaleString('ru-RU')}` : ''}</div>
                        {Array.isArray(lead.matching_sources_json) && lead.matching_sources_json.length > 1 ? <div>Объединено источников: {lead.matching_sources_json.length}</div> : null}
                        {lead.enrich_payload_json?.provider ? <div>Обогащение: {lead.enrich_payload_json.provider}</div> : null}
                        {lead.parse_error ? <div className="text-red-600">{lead.parse_error}</div> : null}
                        {lead.source_url ? <a href={lead.source_url} target="_blank" rel="noreferrer" className="break-all text-blue-600 underline">Открыть источник</a> : null}
                      </div>
                    </details>
                  </div>
                </div>
                <div className="flex shrink-0 flex-wrap gap-2 lg:max-w-[360px] lg:justify-end">
                  <Button variant="outline" size="sm" onClick={() => onRunParse(lead.id)} disabled={loading}>Запустить парсинг</Button>
                  <Button variant="outline" size="sm" onClick={() => onEnrichContacts(lead.id)} disabled={loading}>Обогатить контакты</Button>
                  <Button variant="outline" size="sm" onClick={() => onRunAudit(lead.id)} disabled={loading}>Аудит</Button>
                  <Button variant="outline" size="sm" onClick={() => onRunMatch(lead.id)} disabled={loading}>Матчинг</Button>
                  <Button size="sm" className="bg-slate-950 text-white hover:bg-slate-800" onClick={() => onUpdateLeadStage(lead.id, 'selected_for_outreach', 'Партнёр добавлен в работу', { deferredReason: '', deferredUntil: '' })} disabled={loading}>
                    {String(lead.partnership_stage || '').toLowerCase() === 'deferred' ? 'Вернуть в работу' : 'Сохранить'}
                  </Button>
                  <Button variant="outline" size="sm" onClick={() => onUpdateLeadStage(lead.id, 'deferred', 'Партнёр отложен на потом', { deferredReason: deferredReasonInput.trim() || lead.deferred_reason || '', deferredUntil: deferredUntilInput || String(lead.deferred_until || '').slice(0, 10) || '' })} disabled={loading}>Отложить</Button>
                  <Button variant="outline" size="sm" onClick={() => onDeleteLead(lead.id)} disabled={loading}>Удалить</Button>
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
        <Button size="sm" variant="outline" onClick={onNormalizeSelectedViaOpenClaw} disabled={loading}>Подготовить черновики</Button>
        <Button size="sm" variant="outline" onClick={onBulkDeleteLeads} disabled={loading}>Удалить</Button>
      </div>
    </div>
  );
};
