import { Suspense, lazy, useEffect, useMemo, useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import { newAuth } from '@/lib/auth_new';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { ProspectingIntakePanel } from '@/components/prospecting/ProspectingWorkspaceChrome';
import { getRequestErrorMessage, runLoadingAction } from '@/components/prospecting/prospectingAsync';
import { collectLeadIdsForSource, preparePartnershipBatch, runPartnershipPilotFlow, sourceMatchesDescriptor } from '@/components/prospecting/partnershipFlowHelpers';
import { usePartnershipWorkspaceDerivedData } from '@/components/prospecting/usePartnershipWorkspaceDerivedData';
import {
  buildOperatorSnapshotMarkdown,
  buildOperatorSnapshotPayload,
  buildPartnershipCsvTemplate,
  downloadTextFile,
} from '@/components/prospecting/partnershipExport';
import { PartnershipWorkspaceOverview } from '@/components/prospecting/PartnershipWorkspaceOverview';
import { PartnershipRawIntakeControls } from '@/components/prospecting/PartnershipRawIntakeControls';
import {
  PartnershipDraftsSection,
  PartnershipQueueSection,
  PartnershipSentSection,
} from '@/components/prospecting/PartnershipOperationalSections';
import {
  PartnershipLeadCard,
  PartnershipPipelineBoard,
  PartnershipPipelineBulkBar,
  PartnershipPipelineList,
} from '@/components/prospecting/PartnershipPipelineSections';
import { PartnershipAnalyticsWorkspace } from '@/components/prospecting/PartnershipAnalyticsWorkspace';
import {
  approvePartnershipBatch,
  approvePartnershipDraft,
  bulkDeletePartnershipLeads,
  bulkEnrichPartnershipContacts,
  bulkMatchPartnershipLeads,
  bulkUpdatePartnershipLeads,
  confirmPartnershipReaction,
  createPartnershipBatch,
  deletePartnershipDraft,
  deletePartnershipLead,
  deletePartnershipQueueItem,
  exportPartnershipData,
  getStringIds,
  importPartnershipFile,
  importPartnershipLinks,
  loadPartnershipBatches,
  loadPartnershipBlockers,
  loadPartnershipDrafts,
  loadPartnershipFunnel,
  loadPartnershipHealth,
  loadPartnershipLeads,
  loadPartnershipLearningMetrics,
  loadPartnershipOutcomes,
  loadPartnershipRalphLoop,
  loadPartnershipSourceQuality,
  normalizePartnershipLeads,
  patchPartnershipLead,
  recordPartnershipReaction,
  runPartnershipGeoSearch,
  runPartnershipLeadAction,
  updatePartnershipQueueDelivery,
} from '@/components/prospecting/partnershipApi';

const RalphLoopAnalyticsPanel = lazy(() =>
  import('@/components/prospecting/PartnershipAnalyticsPanels').then((module) => ({
    default: module.RalphLoopAnalyticsPanel,
  })),
);

const PartnershipLeadDetailDrawer = lazy(() => import('@/components/prospecting/PartnershipLeadDetailDrawer'));

type PartnershipLead = {
  id: string;
  name?: string;
  address?: string;
  city?: string;
  category?: string;
  source_url?: string;
  source?: string;
  source_kind?: string;
  source_provider?: string;
  external_place_id?: string;
  external_source_id?: string;
  dedupe_key?: string;
  lat?: number;
  lon?: number;
  search_payload_json?: Record<string, any> | null;
  enrich_payload_json?: {
    provider?: string;
    found_fields?: string[];
    confidence?: Record<string, number>;
    contacts?: Record<string, string | null>;
    raw?: Record<string, any>;
  } | null;
  matched_sources_json?: string[] | null;
  phone?: string;
  email?: string;
  website?: string;
  telegram_url?: string;
  whatsapp_url?: string;
  status?: string;
  partnership_stage?: string;
  pilot_cohort?: string;
  selected_channel?: string;
  updated_at?: string;
  rating?: number;
  reviews_count?: number;
  parse_task_id?: string;
  parse_status?: string;
  parse_updated_at?: string;
  parse_retry_after?: string;
  parse_error?: string;
  deferred_reason?: string;
  deferred_until?: string;
  next_best_action?: {
    code?: string;
    label?: string;
    hint?: string;
    priority?: 'low' | 'medium' | 'high';
  };
};

type PartnershipDraft = {
  id: string;
  lead_id: string;
  lead_name?: string;
  channel?: string;
  status?: string;
  generated_text?: string;
  edited_text?: string;
  approved_text?: string;
  updated_at?: string;
};

type PartnershipBatch = {
  id: string;
  status: string;
  batch_date?: string;
  created_at?: string;
  updated_at?: string;
  items?: Array<{
    id: string;
    lead_name?: string;
    delivery_status?: string;
    error_text?: string;
    channel?: string;
    latest_outcome?: string | null;
    latest_human_outcome?: string | null;
    latest_raw_reply?: string | null;
  }>;
};

type PartnershipReaction = {
  id: string;
  queue_id: string;
  lead_id: string;
  lead_name?: string;
  batch_id?: string;
  channel?: string;
  delivery_status?: string;
  raw_reply?: string | null;
  classified_outcome?: string | null;
  human_confirmed_outcome?: string | null;
};

type PartnershipLearningMetric = {
  capability: string;
  accepted_total: number;
  accepted_raw_total: number;
  accepted_edited_total: number;
  accepted_raw_pct: number;
  edited_before_accept_pct: number;
};

type PartnershipHealth = {
  openclaw?: {
    enabled?: boolean;
    caps_endpoint_configured?: boolean;
    token_configured?: boolean;
  };
  counts?: {
    leads_total?: number;
    drafts_total?: number;
    batches_total?: number;
    reactions_total?: number;
  };
};

type PartnershipFunnelStage = {
  key: string;
  label: string;
  count: number;
  conversion_from_prev_pct?: number;
};

type PartnershipFunnel = {
  window_days?: number;
  funnel?: PartnershipFunnelStage[];
  summary?: {
    import_to_sent_pct?: number;
    imported_count?: number;
    sent_count?: number;
  };
};

type PartnershipOutcomeSummary = {
  total_reactions?: number;
  positive_count?: number;
  question_count?: number;
  no_response_count?: number;
  hard_no_count?: number;
  positive_rate_pct?: number;
  question_rate_pct?: number;
  no_response_rate_pct?: number;
  hard_no_rate_pct?: number;
};

type PartnershipOutcomes = {
  window_days?: number;
  summary?: PartnershipOutcomeSummary;
  by_channel?: Array<{
    channel?: string;
    total?: number;
    positive_count?: number;
    question_count?: number;
    no_response_count?: number;
    hard_no_count?: number;
  }>;
};

type PartnershipSourceQualityItem = {
  source_kind?: string;
  source_provider?: string;
  leads_total?: number;
  audited_count?: number;
  matched_count?: number;
  draft_count?: number;
  sent_count?: number;
  positive_count?: number;
  audit_rate_pct?: number;
  match_rate_pct?: number;
  draft_rate_pct?: number;
  sent_rate_pct?: number;
  positive_rate_pct?: number;
  lead_to_positive_pct?: number;
};

type PartnershipSourceQuality = {
  window_days?: number;
  items?: PartnershipSourceQualityItem[];
};

type PartnershipBlocker = {
  key: string;
  label: string;
  count: number;
  severity?: 'info' | 'warning' | 'danger';
  hint?: string;
};

type PartnershipBlockers = {
  window_days?: number;
  summary?: Record<string, number>;
  blockers?: PartnershipBlocker[];
};

type PartnershipRalphLoop = {
  window_days?: number;
  pilot_cohort?: string;
  summary?: {
    leads_total?: number;
    parsed_completed_count?: number;
    audited_count?: number;
    matched_count?: number;
    drafts_total?: number;
    drafts_approved_count?: number;
    sent_total?: number;
    positive_count?: number;
    question_count?: number;
    no_response_count?: number;
    hard_no_count?: number;
    positive_rate_pct?: number;
  };
  baseline?: {
    window_days?: number;
    sent_total?: number;
    positive_count?: number;
    positive_rate_pct?: number;
    deltas?: {
      sent_total?: number;
      positive_count?: number;
      positive_rate_pct?: number;
    };
  };
  top_channels?: Array<{
    channel?: string;
    total?: number;
    positive_count?: number;
    positive_rate_pct?: number;
  }>;
  source_performance?: Array<{
    source_kind?: string;
    source_provider?: string;
    leads_total?: number;
    audited_count?: number;
    matched_count?: number;
    draft_count?: number;
    sent_count?: number;
    positive_count?: number;
    audit_rate_pct?: number;
    match_rate_pct?: number;
    draft_rate_pct?: number;
    sent_rate_pct?: number;
    positive_rate_pct?: number;
    lead_to_positive_pct?: number;
  }>;
  learning?: Array<{
    capability?: string;
    accepted_total?: number;
    accepted_edited_total?: number;
    edited_before_accept_pct?: number;
    prompt_key?: string;
    prompt_version?: string;
  }>;
  prompt_performance?: Array<{
    prompt_key?: string;
    prompt_version?: string;
    drafts_total?: number;
    approved_total?: number;
    edited_approved_total?: number;
    edited_before_accept_pct?: number;
    sent_total?: number;
    positive_count?: number;
    positive_rate_pct?: number;
  }>;
  recommended_prompt_version?: {
    prompt_key?: string;
    prompt_version?: string;
    drafts_total?: number;
    approved_total?: number;
    edited_approved_total?: number;
    edited_before_accept_pct?: number;
    sent_total?: number;
    positive_count?: number;
    positive_rate_pct?: number;
  } | null;
  blockers?: string[];
  recommendations?: string[];
  edit_insights?: {
    edited_accepts_total?: number;
    avg_generated_len?: number;
    avg_final_len?: number;
    expanded_count?: number;
    shortened_count?: number;
    unchanged_count?: number;
  };
};

const STAGE_OPTIONS = [
  { value: 'all', label: 'Все этапы' },
  { value: 'imported', label: 'Импортировано' },
  { value: 'deferred', label: 'Отложено' },
  { value: 'audited', label: 'Аудит готов' },
  { value: 'matched', label: 'Матчинг готов' },
  { value: 'proposal_draft_ready', label: 'Черновик оффера готов' },
];
const BULK_STAGE_OPTIONS = [
  { value: 'imported', label: 'Импортировано' },
  { value: 'deferred', label: 'Отложено' },
  { value: 'audited', label: 'Аудит готов' },
  { value: 'matched', label: 'Матчинг готов' },
  { value: 'proposal_draft_ready', label: 'Черновик оффера готов' },
  { value: 'selected_for_outreach', label: 'Выбрано для контакта' },
  { value: 'channel_selected', label: 'Канал выбран' },
  { value: 'approved_for_send', label: 'Готово к отправке' },
  { value: 'sent', label: 'Отправлено' },
];
const CHANNEL_OPTIONS = [
  { value: 'telegram', label: 'Telegram' },
  { value: 'whatsapp', label: 'WhatsApp' },
  { value: 'email', label: 'Email' },
  { value: 'manual', label: 'Вручную' },
];
const OUTCOME_OPTIONS = ['positive', 'question', 'no_response', 'hard_no'] as const;
const LEAD_VIEW_OPTIONS = [
  { value: 'all', label: 'Все лиды' },
  { value: 'deferred', label: 'Только отложенные' },
  { value: 'overdue_return', label: 'Просрочено к возврату' },
  { value: 'no_parse', label: 'Без парсинга' },
  { value: 'ready_for_letter', label: 'Готовы к письму' },
  { value: 'errors', label: 'Ошибки' },
  { value: 'last_geo_search', label: 'Последний geo-search' },
  { value: 'requires_action', label: 'Требуют действия' },
  { value: 'ready_next_step', label: 'Готовы к следующему шагу' },
  { value: 'parsed', label: 'Парсинг завершён' },
  { value: 'with_contacts', label: 'С контактами' },
  { value: 'best_source', label: 'Лучший источник недели' },
] as const;
const PARTNERSHIP_WORKSPACE_OPTIONS = [
  { value: 'raw', label: 'Собранные' },
  { value: 'pipeline', label: 'Pipeline' },
  { value: 'analytics', label: 'Аналитика' },
  { value: 'drafts', label: 'Письма' },
  { value: 'queue', label: 'Отправка' },
  { value: 'sent', label: 'Отправлено' },
] as const;
type PartnershipWorkspaceView = (typeof PARTNERSHIP_WORKSPACE_OPTIONS)[number]['value'];
type PartnershipBoardColumnId = 'new' | 'in_progress' | 'contacted' | 'deferred';
type LeadView = (typeof LEAD_VIEW_OPTIONS)[number]['value'];
type WorkflowBadgeVariant = 'default' | 'secondary' | 'outline' | 'destructive';
type WorkflowTone = 'default' | 'success' | 'warning' | 'info' | 'danger';

const toPartnershipWorkspaceView = (value: string): PartnershipWorkspaceView => {
  const matched = PARTNERSHIP_WORKSPACE_OPTIONS.find((option) => option.value === value);
  return matched ? matched.value : 'raw';
};

const toLeadView = (value: string): LeadView => {
  const matched = LEAD_VIEW_OPTIONS.find((option) => option.value === value);
  return matched ? matched.value : 'all';
};

const partnershipBoardColumnIds: PartnershipBoardColumnId[] = ['new', 'in_progress', 'contacted', 'deferred'];

const partnershipBoardColumnMeta: Record<PartnershipBoardColumnId, { label: string; description: string; stageToSet: string }> = {
  new: {
    label: 'Новые',
    description: 'Уже перенесены в рабочий pipeline, но ещё не доведены до контакта.',
    stageToSet: 'selected_for_outreach',
  },
  in_progress: {
    label: 'В работе',
    description: 'Идёт аудит, матчинг, подготовка оффера и выбор канала.',
    stageToSet: 'channel_selected',
  },
  contacted: {
    label: 'Контактированы',
    description: 'Черновик утверждён и лид уже доведён до отправки или в доставке.',
    stageToSet: 'approved_for_send',
  },
  deferred: {
    label: 'Отложенные',
    description: 'Сейчас не берём в работу, но держим на потом.',
    stageToSet: 'deferred',
  },
};

const leadToPartnershipBoardColumn = (lead: PartnershipLead): PartnershipBoardColumnId => {
  const stageValue = String(lead.partnership_stage || '').toLowerCase();
  if (stageValue === 'deferred') {
    return 'deferred';
  }
  if (['approved_for_send', 'sent'].includes(stageValue)) {
    return 'contacted';
  }
  if (['audited', 'matched', 'proposal_draft_ready', 'channel_selected'].includes(stageValue)) {
    return 'in_progress';
  }
  return 'new';
};

const nextPartnershipBoardColumn = (columnId: PartnershipBoardColumnId): PartnershipBoardColumnId | null => {
  if (columnId === 'new') return 'in_progress';
  if (columnId === 'in_progress') return 'contacted';
  return null;
};

const partnershipStagePresentation = (lead: PartnershipLead): {
  label: string;
  variant: WorkflowBadgeVariant;
  tone: WorkflowTone;
  helper: string;
} => {
  const stageValue = String(lead.partnership_stage || '').toLowerCase();
  if (!stageValue || stageValue === 'imported') {
    return {
      label: 'Новый сырой',
      variant: 'outline',
      tone: 'default',
      helper: 'Лид ещё не перенесён в рабочий pipeline.',
    };
  }
  if (stageValue === 'deferred') {
    return {
      label: 'Отложен',
      variant: 'outline',
      tone: 'warning',
      helper: 'Лид сохранён на потом и сейчас не в активной работе.',
    };
  }
  if (['rejected', 'shortlist_rejected'].includes(stageValue)) {
    return {
      label: 'Отклонён',
      variant: 'destructive',
      tone: 'danger',
      helper: 'Лид уже был снят с потока и не требует действий.',
    };
  }
  if (['approved_for_send', 'sent'].includes(stageValue)) {
    return {
      label: 'Контактирован',
      variant: 'secondary',
      tone: 'success',
      helper: 'Лид уже дошёл до отправки или находится в доставке.',
    };
  }
  if (['audited', 'matched', 'proposal_draft_ready', 'channel_selected', 'selected_for_outreach'].includes(stageValue)) {
    return {
      label: 'Уже в pipeline',
      variant: 'secondary',
      tone: 'info',
      helper: 'Лид уже взят в работу: идёт аудит, матчинг или подготовка контакта.',
    };
  }
  return {
    label: 'В работе',
    variant: 'secondary',
    tone: 'info',
    helper: 'Лид уже находится внутри операторского процесса.',
  };
};

const partnershipAuditPresentation = (lead: PartnershipLead): {
  label: string;
  variant: WorkflowBadgeVariant;
  tone: WorkflowTone;
  primary: string;
  secondary: string;
} => {
  const stageValue = String(lead.partnership_stage || '').toLowerCase();
  if (['audited', 'matched', 'proposal_draft_ready', 'selected_for_outreach', 'channel_selected', 'approved_for_send', 'sent'].includes(stageValue)) {
    return {
      label: 'Готов',
      variant: 'secondary',
      tone: 'success',
      primary: 'Аудит уже собран и доступен для следующего шага.',
      secondary: lead.parse_updated_at
        ? `Последнее обновление данных: ${new Date(lead.parse_updated_at).toLocaleString('ru-RU')}`
        : 'Можно продолжать матчинг, оффер и выбор канала.',
    };
  }
  if (String(lead.parse_status || '').toLowerCase() === 'completed') {
    return {
      label: 'Данные готовы',
      variant: 'outline',
      tone: 'info',
      primary: 'Парсинг завершён, аудит можно запускать без ожидания.',
      secondary: 'Следующий шаг — собрать аудит и перейти к матчингу.',
    };
  }
  if (String(lead.parse_status || '').toLowerCase() === 'error') {
    return {
      label: 'Есть ошибка',
      variant: 'destructive',
      tone: 'danger',
      primary: 'Сначала нужно разобраться с ошибкой парсинга.',
      secondary: lead.parse_error || 'Аудит лучше запускать после успешного сбора данных.',
    };
  }
  return {
    label: 'Не создан',
    variant: 'outline',
    tone: 'default',
    primary: 'Аудит ещё не запускался.',
    secondary: 'Сначала enrich/парсинг, затем аудит и матчинг.',
  };
};
const DRAFT_VIEW_OPTIONS = [
  { value: 'all', label: 'Все черновики' },
  { value: 'needs_approval', label: 'Ждут утверждения' },
  { value: 'approved', label: 'Утверждённые' },
] as const;
const QUEUE_VIEW_OPTIONS = [
  { value: 'all', label: 'Вся очередь' },
  { value: 'needs_approval', label: 'Batch ждёт утверждения' },
  { value: 'waiting_delivery', label: 'Ждут доставки' },
  { value: 'waiting_outcome', label: 'Ждут outcome' },
  { value: 'failed', label: 'С ошибкой доставки' },
] as const;
const REACTION_VIEW_OPTIONS = [
  { value: 'all', label: 'Все реакции' },
  { value: 'needs_confirmation', label: 'Требуют подтверждения' },
  { value: 'positive', label: 'Positive' },
  { value: 'question', label: 'Question' },
  { value: 'no_response', label: 'No response' },
  { value: 'hard_no', label: 'Hard no' },
] as const;
const PILOT_COHORT_OPTIONS = [
  { value: 'all', label: 'Все когорты' },
  { value: 'pilot', label: 'Пилот' },
  { value: 'backlog', label: 'Backlog' },
  { value: 'watchlist', label: 'Watchlist' },
] as const;

type DraftView = (typeof DRAFT_VIEW_OPTIONS)[number]['value'];
type QueueView = (typeof QUEUE_VIEW_OPTIONS)[number]['value'];
type ReactionView = (typeof REACTION_VIEW_OPTIONS)[number]['value'];
type PilotCohort = (typeof PILOT_COHORT_OPTIONS)[number]['value'];

const toDraftView = (value: string): DraftView => {
  const matched = DRAFT_VIEW_OPTIONS.find((option) => option.value === value);
  return matched ? matched.value : 'all';
};

const toQueueView = (value: string): QueueView => {
  const matched = QUEUE_VIEW_OPTIONS.find((option) => option.value === value);
  return matched ? matched.value : 'all';
};

const toReactionView = (value: string): ReactionView => {
  const matched = REACTION_VIEW_OPTIONS.find((option) => option.value === value);
  return matched ? matched.value : 'all';
};

const toPilotCohort = (value: string): PilotCohort => {
  const matched = PILOT_COHORT_OPTIONS.find((option) => option.value === value);
  return matched ? matched.value : 'all';
};

export const PartnershipSearchPage: React.FC = () => {
  const { currentBusinessId } = useOutletContext<any>();
  const [loading, setLoading] = useState(false);
  const [draggingLeadId, setDraggingLeadId] = useState<string | null>(null);
  const [dropColumnId, setDropColumnId] = useState<PartnershipBoardColumnId | null>(null);
  const [linksText, setLinksText] = useState('');
  const [importFileName, setImportFileName] = useState('');
  const [importFileContent, setImportFileContent] = useState('');
  const [importFileFormat, setImportFileFormat] = useState<'csv' | 'json' | 'jsonl' | ''>('');
  const [importFileErrors, setImportFileErrors] = useState<Array<{ row?: number; error?: string }>>([]);
  const [geoCity, setGeoCity] = useState('');
  const [geoCategory, setGeoCategory] = useState('');
  const [geoQuery, setGeoQuery] = useState('');
  const [geoProvider, setGeoProvider] = useState<'google' | 'yandex' | 'both'>('google');
  const [geoRadiusKm, setGeoRadiusKm] = useState('5');
  const [geoLimit, setGeoLimit] = useState('25');
  const [stage, setStage] = useState('all');
  const [pilotCohort, setPilotCohort] = useState<PilotCohort>('all');
  const [query, setQuery] = useState('');
  const [workspaceView, setWorkspaceView] = useState<PartnershipWorkspaceView>('raw');
  const [items, setItems] = useState<PartnershipLead[]>([]);
  const [selectedLeadId, setSelectedLeadId] = useState<string | null>(null);
  const [selectedLeadIds, setSelectedLeadIds] = useState<string[]>([]);
  const [leadView, setLeadView] = useState<LeadView>('all');
  const [leadBucket, setLeadBucket] = useState<'active' | 'deferred'>('active');
  const [lastGeoSearchLeadIds, setLastGeoSearchLeadIds] = useState<string[]>([]);
  const [preferredSourceFilter, setPreferredSourceFilter] = useState<{ source_kind?: string; source_provider?: string } | null>(null);
  const [bulkStage, setBulkStage] = useState('');
  const [bulkChannel, setBulkChannel] = useState('');
  const [bulkPilotCohort, setBulkPilotCohort] = useState('');
  const [auditData, setAuditData] = useState<any>(null);
  const [matchData, setMatchData] = useState<any>(null);
  const [draftText, setDraftText] = useState('');
  const [drafts, setDrafts] = useState<PartnershipDraft[]>([]);
  const [selectedDraftIds, setSelectedDraftIds] = useState<string[]>([]);
  const [draftView, setDraftView] = useState<(typeof DRAFT_VIEW_OPTIONS)[number]['value']>('all');
  const [batches, setBatches] = useState<PartnershipBatch[]>([]);
  const [selectedQueueIds, setSelectedQueueIds] = useState<string[]>([]);
  const [bulkQueueStatus, setBulkQueueStatus] = useState('');
  const [queueView, setQueueView] = useState<(typeof QUEUE_VIEW_OPTIONS)[number]['value']>('all');
  const [queueReadyDrafts, setQueueReadyDrafts] = useState<PartnershipDraft[]>([]);
  const [reactions, setReactions] = useState<PartnershipReaction[]>([]);
  const [reactionView, setReactionView] = useState<(typeof REACTION_VIEW_OPTIONS)[number]['value']>('all');
  const [sendQueueBusy, setSendQueueBusy] = useState<Record<string, string>>({});
  const [reactionBusy, setReactionBusy] = useState<Record<string, string>>({});
  const [learningMetrics, setLearningMetrics] = useState<PartnershipLearningMetric[]>([]);
  const [health, setHealth] = useState<PartnershipHealth | null>(null);
  const [funnel, setFunnel] = useState<PartnershipFunnel | null>(null);
  const [blockers, setBlockers] = useState<PartnershipBlockers | null>(null);
  const [outcomes, setOutcomes] = useState<PartnershipOutcomes | null>(null);
  const [sourceQuality, setSourceQuality] = useState<PartnershipSourceQuality | null>(null);
  const [ralphLoop, setRalphLoop] = useState<PartnershipRalphLoop | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [deferredReasonInput, setDeferredReasonInput] = useState('');
  const [deferredUntilInput, setDeferredUntilInput] = useState('');
  const [leadEdit, setLeadEdit] = useState<{
    name: string;
    city: string;
    category: string;
    address: string;
    phone: string;
    email: string;
    website: string;
    telegram_url: string;
    whatsapp_url: string;
  }>({
    name: '',
    city: '',
    category: '',
    address: '',
    phone: '',
    email: '',
    website: '',
    telegram_url: '',
    whatsapp_url: '',
  });

  const {
    selectedLead,
    selectedLeadLogo,
    selectedLeadPhotos,
    visibleLeads,
    bestSourceThisWeek,
    lastGeoSearchSourceSummary,
    lastGeoSearchMatchesBestSource,
    lastGeoSearchStats,
    allQueueItems,
    lastGeoSearchFlowSummary,
    selectedLeadFlowStatus,
    visibleDrafts,
    visibleBatches,
    visibleReactions,
    pilotSummary,
    deferredLeadsCount,
    overdueDeferredLeadsCount,
    activeLeadsCount,
    rawLeads,
    rawLeadCount,
    pipelineLeads,
    pipelineLeadCount,
    lastGeoSearchLeadCount,
    pipelineSummary,
    rawLeadStatusSummary,
  } = usePartnershipWorkspaceDerivedData({
    items,
    selectedLeadId,
    auditData,
    leadView,
    leadBucket,
    preferredSourceFilter,
    lastGeoSearchLeadIds,
    ralphLoop,
    batches,
    drafts,
    reactions,
    draftView,
    queueView,
    reactionView,
    outcomes,
  });

  const partnershipBoardColumns = useMemo(() => {
    const buckets: Record<PartnershipBoardColumnId, PartnershipLead[]> = {
      new: [],
      in_progress: [],
      contacted: [],
      deferred: [],
    };
    for (const item of pipelineLeads) {
      buckets[leadToPartnershipBoardColumn(item)].push(item);
    }
    return partnershipBoardColumnIds.map((id) => ({
      id,
      label: partnershipBoardColumnMeta[id].label,
      description: partnershipBoardColumnMeta[id].description,
      leads: buckets[id],
    }));
  }, [pipelineLeads]);

  useEffect(() => {
    if (!selectedLead) {
      setLeadEdit({
        name: '',
        city: '',
        category: '',
        address: '',
        phone: '',
        email: '',
        website: '',
        telegram_url: '',
        whatsapp_url: '',
      });
      return;
    }
    setLeadEdit({
      name: selectedLead.name || '',
      city: selectedLead.city || '',
      category: selectedLead.category || '',
      address: selectedLead.address || '',
      phone: selectedLead.phone || '',
      email: selectedLead.email || '',
      website: selectedLead.website || '',
      telegram_url: selectedLead.telegram_url || '',
      whatsapp_url: selectedLead.whatsapp_url || '',
    });
  }, [selectedLeadId, selectedLead, items]);

  const loadLeads = async () => {
    if (!currentBusinessId) return;
    try {
      setLoading(true);
      setError(null);
      const data = await loadPartnershipLeads({ businessId: currentBusinessId, stage, pilotCohort, query });
      setItems(Array.isArray(data.items) ? data.items : []);
      setSelectedLeadIds((prev) => prev.filter((id) => (data.items || []).some((x: any) => x.id === id)));
      if (selectedLeadId && !(data.items || []).some((x: any) => x.id === selectedLeadId)) {
        setSelectedLeadId(null);
      }
    } catch (e: any) {
      setError(e.message || 'Не удалось загрузить список партнёров');
    } finally {
      setLoading(false);
    }
  };

  const loadRalphLoop = async () => {
    if (!currentBusinessId) return;
    try {
      const data = await loadPartnershipRalphLoop(currentBusinessId, pilotCohort);
      setRalphLoop(data || null);
    } catch {
      setRalphLoop(null);
    }
  };

  const loadDrafts = async () => {
    if (!currentBusinessId) return;
    const data = await loadPartnershipDrafts(currentBusinessId);
    setDrafts(Array.isArray(data.drafts) ? data.drafts : []);
    setSelectedDraftIds((prev) => prev.filter((id) => (data.drafts || []).some((x: any) => x.id === id)));
  };

  const loadBatches = async () => {
    if (!currentBusinessId) return;
    const data = await loadPartnershipBatches(currentBusinessId);
    setBatches(Array.isArray(data.batches) ? data.batches : []);
    const queueIds = (Array.isArray(data.batches) ? data.batches : [])
      .flatMap((batch: any) => (Array.isArray(batch.items) ? batch.items : []))
      .map((item: any) => item.id);
    setSelectedQueueIds((prev) => prev.filter((id) => queueIds.includes(id)));
    setQueueReadyDrafts(Array.isArray(data.ready_drafts) ? data.ready_drafts : []);
    setReactions(Array.isArray(data.reactions) ? data.reactions : []);
  };

  const loadLearningMetrics = async () => {
    try {
      const data = await loadPartnershipLearningMetrics();
      setLearningMetrics(Array.isArray(data.items) ? data.items : []);
    } catch {
      setLearningMetrics([]);
    }
  };

  const loadHealth = async () => {
    if (!currentBusinessId) return;
    try {
      const data = await loadPartnershipHealth(currentBusinessId);
      setHealth(data || null);
    } catch {
      setHealth(null);
    }
  };

  const loadFunnel = async () => {
    if (!currentBusinessId) return;
    try {
      const data = await loadPartnershipFunnel(currentBusinessId);
      setFunnel(data || null);
    } catch {
      setFunnel(null);
    }
  };

  const loadBlockers = async () => {
    if (!currentBusinessId) return;
    try {
      const data = await loadPartnershipBlockers(currentBusinessId);
      setBlockers(data || null);
    } catch {
      setBlockers(null);
    }
  };

  const loadOutcomes = async () => {
    if (!currentBusinessId) return;
    try {
      const data = await loadPartnershipOutcomes(currentBusinessId);
      setOutcomes(data || null);
    } catch {
      setOutcomes(null);
    }
  };

  const loadSourceQuality = async () => {
    if (!currentBusinessId) return;
    try {
      const data = await loadPartnershipSourceQuality(currentBusinessId);
      setSourceQuality(data || null);
    } catch {
      setSourceQuality(null);
    }
  };

  const refreshInsightsData = async () => {
    await Promise.all([
      loadLearningMetrics(),
      loadHealth(),
      loadFunnel(),
      loadBlockers(),
      loadOutcomes(),
      loadSourceQuality(),
      loadRalphLoop(),
    ]);
  };

  const refreshOperationalData = async () => {
    await Promise.all([
      loadLeads(),
      loadDrafts(),
      loadBatches(),
    ]);
  };

  const refreshAllPartnershipData = async () => {
    await refreshOperationalData();
    await refreshInsightsData();
  };

  const runPartnershipAction = async (fallback: string, action: () => Promise<void>) => {
    await runLoadingAction(setLoading, setError, fallback, action);
  };

  const runBulkLeadUpdate = async (
    payload: Record<string, unknown>,
    options: {
      fallback: string;
      message: (updatedCount: number) => string;
      afterSuccess?: () => Promise<void>;
    },
  ) => {
    if (!currentBusinessId || selectedLeadIds.length === 0) {
      return;
    }
    await runPartnershipAction(options.fallback, async () => {
      const data = await bulkUpdatePartnershipLeads(currentBusinessId, selectedLeadIds, payload);
      setMessage(options.message(Number(data?.updated_count || 0)));
      setSelectedLeadIds([]);
      if (options.afterSuccess) {
        await options.afterSuccess();
      }
    });
  };

  useEffect(() => {
    void refreshOperationalData();
    void refreshInsightsData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentBusinessId, stage, pilotCohort]);

  const handleImportLinks = async () => {
    if (!currentBusinessId) return;
    const links = linksText
      .split('\n')
      .map((line) => line.trim())
      .filter(Boolean);
    if (links.length === 0) {
      setError('Добавьте минимум одну ссылку');
      return;
    }
    try {
      setLoading(true);
      setError(null);
      const data = await importPartnershipLinks(currentBusinessId, links);
      setMessage(`Импортировано: ${data.imported_count || 0}, пропущено: ${data.skipped_count || 0}`);
      setLinksText('');
      await refreshOperationalData();
      await Promise.all([loadHealth(), loadFunnel(), loadOutcomes(), loadSourceQuality()]);
    } catch (error: unknown) {
      setError(getRequestErrorMessage(error, 'Не удалось импортировать ссылки'));
    } finally {
      setLoading(false);
    }
  };

  const handleImportFilePick = async (file?: File | null) => {
    if (!file) return;
    const name = file.name || 'partners-import';
    const lower = name.toLowerCase();
    const format: 'csv' | 'json' | 'jsonl' | '' =
      lower.endsWith('.csv') ? 'csv' : lower.endsWith('.jsonl') ? 'jsonl' : lower.endsWith('.json') ? 'json' : '';
    const text = await file.text();
    setImportFileName(name);
    setImportFileFormat(format);
    setImportFileContent(text);
    setImportFileErrors([]);
    setMessage(`Файл загружен: ${name}`);
  };

  const handleImportFile = async () => {
    if (!currentBusinessId) return;
    if (!importFileContent.trim()) {
      setError('Выберите CSV/JSON файл для импорта');
      return;
    }
    await runPartnershipAction('Не удалось импортировать файл партнёров', async () => {
      const data = await importPartnershipFile(currentBusinessId, {
        filename: importFileName || 'partners-import',
        format: importFileFormat || undefined,
        content: importFileContent,
      });
      setImportFileErrors(Array.isArray(data.errors) ? data.errors : []);
      setMessage(
        `Импорт файла: ${data.imported_count || 0} добавлено, ${data.skipped_count || 0} пропущено, строк: ${data.rows_total || 0}`
      );
      await refreshAllPartnershipData();
    });
  };

  const handleGeoSearch = async () => {
    if (!currentBusinessId) return;
    const city = geoCity.trim();
    const category = geoCategory.trim();
    const q = geoQuery.trim();
    const radiusKm = Number.parseInt(geoRadiusKm, 10);
    const limit = Number.parseInt(geoLimit, 10);
    if (!city && !q) {
      setError('Укажите город или поисковый запрос для гео-поиска');
      return;
    }
    await runPartnershipAction('Не удалось выполнить гео-поиск', async () => {
      const data = await runPartnershipGeoSearch({
        businessId: currentBusinessId,
        provider: geoProvider,
        city,
        category,
        query: q,
        radiusKm,
        limit,
      });
      const providerLabel =
        geoProvider === 'google' ? 'Google' : geoProvider === 'yandex' ? 'Яндекс' : 'Google + Яндекс';
      const baseMsg = `${providerLabel}: импортировано ${data.imported_count || 0}, объединено ${data.merged_count || 0}, пропущено ${data.skipped_count || 0}, найдено источником ${data.source_total || 0}`;
      const importedLeadIds = getStringIds(data.lead_ids);
      setLastGeoSearchLeadIds(importedLeadIds);
      if (importedLeadIds.length > 0) {
        setLeadView('last_geo_search');
        setSelectedLeadIds(importedLeadIds);
      }
      setMessage(
        data.warning
          ? `${baseMsg}. ${data.warning}${importedLeadIds.length > 0 ? ` Показаны новые лиды: ${importedLeadIds.length}.` : ''}`
          : `${baseMsg}${importedLeadIds.length > 0 ? `. Показаны новые лиды: ${importedLeadIds.length}.` : ''}`
      );
      await refreshAllPartnershipData();
    });
  };

  const normalizeSelectedViaOpenClaw = async () => {
    if (!currentBusinessId || selectedLeadIds.length === 0) return;
    const selectedLeads = items.filter((item) => selectedLeadIds.includes(item.id));
    if (selectedLeads.length === 0) {
      setMessage('Для нормализации не выбраны лиды.');
      return;
    }
    await runPartnershipAction('Не удалось нормализовать выбранные лиды через OpenClaw', async () => {
      const data = await normalizePartnershipLeads(currentBusinessId, {
        city: geoCity.trim(),
        category: geoCategory.trim(),
        query: geoQuery.trim(),
        items: selectedLeads.map((item) => ({
            name: item.name,
            source_url: item.source_url,
            city: item.city,
            category: item.category,
            address: item.address,
            phone: item.phone,
            email: item.email,
            website: item.website,
            telegram_url: item.telegram_url,
            whatsapp_url: item.whatsapp_url,
            rating: item.rating,
            reviews_count: item.reviews_count,
            source_kind: item.source_kind,
            source_provider: item.source_provider,
            lat: item.lat,
            lon: item.lon,
        })),
      });
      const importedLeadIds = getStringIds(data.lead_ids);
      if (importedLeadIds.length > 0) {
        setLastGeoSearchLeadIds(importedLeadIds);
        setLeadView('last_geo_search');
        setSelectedLeadIds(importedLeadIds);
      }
      setMessage(
        `OpenClaw нормализовал список: импортировано ${data.imported_count || 0}, объединено ${data.merged_count || 0}, пропущено ${data.skipped_count || 0}, найдено ${data.source_total || 0}.`
      );
      await refreshAllPartnershipData();
    });
  };

  const runAudit = async (leadId: string) => {
    if (!currentBusinessId) return;
    await runPartnershipAction('Не удалось выполнить аудит', async () => {
      setMatchData(null);
      setDraftText('');
      const lead = items.find((x) => x.id === leadId);
      const parseStatus = String(lead?.parse_status || '').toLowerCase();
      if (['pending', 'processing', 'captcha'].includes(parseStatus)) {
        throw new Error('Парсинг ещё не завершён. Дождитесь статуса completed/error и обновите список.');
      }
      const data = await runPartnershipLeadAction(currentBusinessId, leadId, 'audit');
      setAuditData(data.snapshot || null);
      setSelectedLeadId(leadId);
      await refreshAllPartnershipData();
    });
  };

  const runParse = async (leadId: string) => {
    if (!currentBusinessId) return;
    await runPartnershipAction('Не удалось запустить парсинг', async () => {
      const data = await runPartnershipLeadAction(currentBusinessId, leadId, 'parse');
      const task = data?.parse_task;
      if (task?.id) {
        setMessage(`Парсинг запущен: ${task.id} (${task.status || 'pending'})`);
      } else {
        setMessage('Парсинг запрошен');
      }
      await refreshOperationalData();
    });
  };

  const runMatch = async (leadId: string) => {
    if (!currentBusinessId) return;
    await runPartnershipAction('Не удалось выполнить матчинг', async () => {
      setDraftText('');
      const data = await runPartnershipLeadAction(currentBusinessId, leadId, 'match');
      setMatchData(data.result || null);
      setSelectedLeadId(leadId);
      await refreshAllPartnershipData();
    });
  };

  const enrichContacts = async (leadId: string) => {
    if (!currentBusinessId) return;
    await runPartnershipAction('Не удалось обогатить контакты', async () => {
      await runPartnershipLeadAction(currentBusinessId, leadId, 'enrich-contacts');
      setMessage('Контакты лида обновлены');
      await refreshOperationalData();
    });
  };

  const runDraft = async (leadId: string) => {
    if (!currentBusinessId) return;
    await runPartnershipAction('Не удалось сгенерировать первое письмо', async () => {
      const data = await runPartnershipLeadAction(currentBusinessId, leadId, 'draft-offer', {
        channel: 'telegram',
        tone: 'профессиональный',
      });
      setDraftText(data.text || '');
      setSelectedLeadId(leadId);
      await refreshAllPartnershipData();
    });
  };

  const saveLeadContacts = async () => {
    if (!currentBusinessId || !selectedLeadId) return;
    await runPartnershipAction('Не удалось сохранить данные лида', async () => {
      await patchPartnershipLead(currentBusinessId, selectedLeadId, leadEdit);
      setMessage('Данные лида сохранены');
      await refreshOperationalData();
    });
  };

  const toggleLeadSelection = (leadId: string, checked: boolean) => {
    setSelectedLeadIds((prev) => {
      if (checked) return prev.includes(leadId) ? prev : [...prev, leadId];
      return prev.filter((id) => id !== leadId);
    });
  };

  const toggleAllLeadSelection = (checked: boolean) => {
    setSelectedLeadIds(checked ? visibleLeads.map((item) => item.id) : []);
  };

  const applyBulkUpdate = async () => {
    if (!currentBusinessId || selectedLeadIds.length === 0) return;
    if (!bulkStage && !bulkChannel) {
      setError('Выберите этап или канал для массового применения');
      return;
    }
    await runBulkLeadUpdate(
      {
        partnership_stage: bulkStage || undefined,
        selected_channel: bulkChannel || undefined,
        pilot_cohort: bulkPilotCohort || undefined,
      },
      {
        fallback: 'Не удалось массово обновить лиды',
        message: (updatedCount) => `Обновлено лидов: ${updatedCount}`,
        afterSuccess: refreshOperationalData,
      },
    );
  };

  const bulkDeleteLeads = async () => {
    if (!currentBusinessId || selectedLeadIds.length === 0) return;
    const ok = window.confirm(`Удалить выбранные лиды (${selectedLeadIds.length})?`);
    if (!ok) return;
    const deletingIds = new Set(selectedLeadIds);
    try {
      setLoading(true);
      setError(null);
      const data = await bulkDeletePartnershipLeads(currentBusinessId, selectedLeadIds);
      if (selectedLeadId && deletingIds.has(selectedLeadId)) {
        setSelectedLeadId(null);
        setAuditData(null);
        setMatchData(null);
        setDraftText('');
      }
      setMessage(`Удалено лидов: ${data.deleted_count || 0}`);
      setSelectedLeadIds([]);
      await loadLeads();
      await loadDrafts();
      await loadBatches();
    } catch (e: any) {
      setError(e.message || 'Не удалось удалить выбранные лиды');
    } finally {
      setLoading(false);
    }
  };

  const bulkDeferLeads = async () => {
    if (!currentBusinessId || selectedLeadIds.length === 0) return;
    await runBulkLeadUpdate(
      {
        partnership_stage: 'deferred',
        deferred_reason: deferredReasonInput.trim() || undefined,
        deferred_until: deferredUntilInput || '',
      },
      {
        fallback: 'Не удалось отложить выбранные лиды',
        message: (updatedCount) => `Отложено лидов: ${updatedCount}`,
        afterSuccess: async () => {
          setLeadBucket('deferred');
          await refreshOperationalData();
        },
      },
    );
  };

  const bulkReturnDeferredLeads = async () => {
    if (!currentBusinessId || selectedLeadIds.length === 0) return;
    await runBulkLeadUpdate(
      {
        partnership_stage: 'selected_for_outreach',
        deferred_reason: '',
        deferred_until: '',
      },
      {
        fallback: 'Не удалось вернуть выбранные лиды в работу',
        message: (updatedCount) => `Возвращено в работу: ${updatedCount}`,
        afterSuccess: async () => {
          setLeadBucket('active');
          await refreshOperationalData();
        },
      },
    );
  };

  const bulkReturnOverdueDeferredLeads = async () => {
    if (!currentBusinessId) return;
    const todayIso = new Date().toISOString().slice(0, 10);
    const overdueIds = items
      .filter((item) => {
        const stageValue = String(item.partnership_stage || '').toLowerCase();
        const deferredUntil = String(item.deferred_until || '').slice(0, 10);
        return stageValue === 'deferred' && Boolean(deferredUntil) && deferredUntil <= todayIso;
      })
      .map((item) => item.id);
    if (overdueIds.length === 0) {
      setMessage('Просроченных отложенных лидов нет');
      return;
    }
    await runPartnershipAction('Не удалось вернуть просроченные лиды в работу', async () => {
      const data = await bulkUpdatePartnershipLeads(currentBusinessId, overdueIds, {
        partnership_stage: 'selected_for_outreach',
        deferred_reason: '',
        deferred_until: '',
      });
      setMessage(`Возвращено в работу по сроку: ${data.updated_count || 0}`);
      setLeadBucket('active');
      setLeadView('all');
      await refreshOperationalData();
    });
  };

  const bulkEnrichContacts = async () => {
    if (!currentBusinessId || selectedLeadIds.length === 0) return;
    await runPartnershipAction('Не удалось массово обогатить контакты', async () => {
      const data = await bulkEnrichPartnershipContacts(currentBusinessId, selectedLeadIds);
      setMessage(
        `Контакты обогащены: ${data.updated_count || 0}, пропущено: ${data.skipped_count || 0}${
          Array.isArray(data.errors) && data.errors.length ? `, ошибок: ${data.errors.length}` : ''
        }`
      );
      await refreshOperationalData();
    });
  };

  const bulkRunParse = async () => {
    if (!currentBusinessId || selectedLeadIds.length === 0) return;
    let started = 0;
    const errors: string[] = [];
    await runPartnershipAction('Не удалось массово запустить парсинг', async () => {
      for (const leadId of selectedLeadIds) {
        try {
          await runPartnershipLeadAction(currentBusinessId, leadId, 'parse');
          started += 1;
        } catch (e: any) {
          errors.push(`${leadId}: ${e?.message || 'ошибка'}`);
        }
      }
      setMessage(
        `Парсинг запущен для ${started} лидов` +
          (errors.length ? `, ошибок: ${errors.length}` : '')
      );
      await refreshOperationalData();
    });
  };

  const bulkRunMatch = async () => {
    if (!currentBusinessId || selectedLeadIds.length === 0) return;
    await runPartnershipAction('Не удалось запустить массовый матчинг', async () => {
      const data = await bulkMatchPartnershipLeads(currentBusinessId, selectedLeadIds);
      const matched = Number(data?.matched_count || 0);
      const skipped = Number(data?.skipped_count || 0);
      const errs = Array.isArray(data?.errors) ? data.errors.length : 0;
      setMessage(
        `Матчинг выполнен: ${matched}` +
          (skipped ? `, пропущено: ${skipped}` : '') +
          (errs ? `, ошибок: ${errs}` : '')
      );
      await refreshAllPartnershipData();
    });
  };

  const prepareLastGeoSearchBatch = async () => {
    if (!currentBusinessId || lastGeoSearchLeadIds.length === 0) {
      setMessage('Для последнего geo-search пока нет лидов для batch prep.');
      return;
    }

    const lastGeoLeadSet = new Set(lastGeoSearchLeadIds);
    const targetDrafts = drafts.filter((draft) => lastGeoLeadSet.has(String(draft.lead_id || '')));
    if (targetDrafts.length === 0) {
      setMessage('Для последнего geo-search ещё нет черновиков. Сначала запустите быстрый сценарий.');
      return;
    }

    await runPartnershipAction('Не удалось подготовить batch для последнего geo-search', async () => {
      const batchPrep = await preparePartnershipBatch(newAuth.makeRequest, currentBusinessId, targetDrafts);
      if (!batchPrep.batchId) {
        setMessage(`Для последнего geo-search не удалось подготовить черновики.${batchPrep.errors.length ? ` Ошибок: ${batchPrep.errors.length}` : ''}`);
        await loadDrafts();
        return;
      }
      setMessage(
        [
          `Последний geo-search batch prep`,
          `approve ${batchPrep.approvedCount}`,
          `в batch ${batchPrep.queuedCount}`,
          batchPrep.batchId ? `batch ${batchPrep.batchId}` : '',
          batchPrep.errors.length ? `ошибок: ${batchPrep.errors.length}` : '',
        ]
          .filter(Boolean)
          .join(' · ')
      );
      await refreshAllPartnershipData();
    });
  };

  const runLastGeoSearchFlow = async () => {
    if (!currentBusinessId) return;
    const sourceLeads = items.filter((item) => lastGeoSearchLeadIds.includes(item.id));
    if (sourceLeads.length === 0) {
      setMessage('Для последнего geo-search пока нет лидов.');
      return;
    }

    await runPartnershipAction('Не удалось выполнить быстрый сценарий для последнего geo-search', async () => {
      const leadIds = sourceLeads.map((item) => item.id);
      const pilotFlow = await runPartnershipPilotFlow(newAuth.makeRequest, currentBusinessId, sourceLeads);
      setSelectedLeadIds(leadIds);
      const summaryParts = [
        `Последний geo-search: ${sourceLeads.length} лидов`,
        `enrich ${pilotFlow.enrichedCount}`,
        `audit ${pilotFlow.auditedCount}`,
        `match ${pilotFlow.matchedCount}`,
        `draft ${pilotFlow.draftedCount}`,
      ];
      if (pilotFlow.skippedParseCount > 0) {
        summaryParts.push(`пропущено без parse completed: ${pilotFlow.skippedParseCount}`);
      }
      if (pilotFlow.errors.length > 0) {
        summaryParts.push(`ошибок: ${pilotFlow.errors.length}`);
      }
      setMessage(summaryParts.join(' · '));
      await refreshAllPartnershipData();
    });
  };

  const moveLastGeoSearchToPilot = async () => {
    if (!currentBusinessId || lastGeoSearchLeadIds.length === 0) {
      setMessage('Для последнего geo-search нет лидов для перевода в pilot cohort.');
      return;
    }
    await runPartnershipAction('Не удалось перевести последний geo-search в pilot cohort', async () => {
      const data = await bulkUpdatePartnershipLeads(currentBusinessId, lastGeoSearchLeadIds, {
        pilot_cohort: 'pilot',
      });
      setSelectedLeadIds(lastGeoSearchLeadIds);
      setMessage(`В pilot cohort переведено ${data.updated_count || 0} лидов из последнего geo-search`);
      await refreshOperationalData();
      await loadRalphLoop();
    });
  };

  const focusBestSourceLeads = () => {
    if (!bestSourceThisWeek) return;
    setPreferredSourceFilter({
      source_kind: bestSourceThisWeek.source_kind,
      source_provider: bestSourceThisWeek.source_provider,
    });
    setLeadView('best_source');
    setSelectedLeadIds(
      items
        .filter((item) => sourceMatchesDescriptor(item, bestSourceThisWeek))
        .map((item) => item.id)
    );
    setMessage(
      `Показаны лиды из лучшего источника: ${bestSourceThisWeek.source_kind || 'unknown'} / ${bestSourceThisWeek.source_provider || 'unknown'}`
    );
  };

  const moveBestSourceToPilot = async () => {
    if (!currentBusinessId || !bestSourceThisWeek) return;
    const candidateIds = collectLeadIdsForSource(items, bestSourceThisWeek, { onlyOutsidePilot: true });
    if (candidateIds.length === 0) {
      setMessage('Для лучшего источника уже нет лидов вне pilot cohort.');
      return;
    }
    await runPartnershipAction('Не удалось перевести лучший источник в pilot cohort', async () => {
      const data = await bulkUpdatePartnershipLeads(currentBusinessId, candidateIds, {
        pilot_cohort: 'pilot',
      });
      setMessage(
        `В pilot cohort переведено ${data.updated_count || 0} лидов из источника ${bestSourceThisWeek.source_kind || 'unknown'} / ${bestSourceThisWeek.source_provider || 'unknown'}`
      );
      setSelectedLeadIds(candidateIds);
      await refreshOperationalData();
      await loadRalphLoop();
    });
  };

  const runBestSourcePilotFlow = async () => {
    if (!currentBusinessId || !bestSourceThisWeek) return;
    const sourceLeads = items.filter(
      (item) =>
        String(item.source_kind || '').toLowerCase() === String(bestSourceThisWeek.source_kind || '').toLowerCase() &&
        String(item.source_provider || '').toLowerCase() === String(bestSourceThisWeek.source_provider || '').toLowerCase()
    );
    if (sourceLeads.length === 0) {
      setMessage('Для лучшего источника пока нет лидов.');
      return;
    }

    await runPartnershipAction('Не удалось выполнить pilot run для лучшего источника', async () => {
      const pilotFlow = await runPartnershipPilotFlow(newAuth.makeRequest, currentBusinessId, sourceLeads);
      setSelectedLeadIds(sourceLeads.map((item) => item.id));
      const summaryParts = [
        `Источник: ${bestSourceThisWeek.source_kind || 'unknown'} / ${bestSourceThisWeek.source_provider || 'unknown'}`,
        `enrich ${pilotFlow.enrichedCount}`,
        `audit ${pilotFlow.auditedCount}`,
        `match ${pilotFlow.matchedCount}`,
        `draft ${pilotFlow.draftedCount}`,
      ];
      if (pilotFlow.skippedParseCount > 0) {
        summaryParts.push(`пропущено без parse completed: ${pilotFlow.skippedParseCount}`);
      }
      if (pilotFlow.errors.length > 0) {
        summaryParts.push(`ошибок: ${pilotFlow.errors.length}`);
      }
      setMessage(summaryParts.join(' · '));
      await refreshAllPartnershipData();
    });
  };

  const prepareBestSourceBatch = async () => {
    if (!currentBusinessId || !bestSourceThisWeek) return;
    const sourceLeadIds = new Set(collectLeadIdsForSource(items, bestSourceThisWeek));
    if (sourceLeadIds.size === 0) {
      setMessage('Для лучшего источника пока нет лидов.');
      return;
    }

    const relatedDrafts = drafts.filter((draft) => sourceLeadIds.has(draft.lead_id));
    if (relatedDrafts.length === 0) {
      setMessage('Для лучшего источника пока нет черновиков для batch.');
      return;
    }

    await runPartnershipAction('Не удалось подготовить batch для лучшего источника', async () => {
      const batchPrep = await preparePartnershipBatch(newAuth.makeRequest, currentBusinessId, relatedDrafts);
      if (!batchPrep.batchId) {
        setMessage('После подготовки у лучшего источника не осталось approved draft для batch.');
        return;
      }
      setMessage(
        `Batch подготовлен для ${bestSourceThisWeek.source_kind || 'unknown'} / ${bestSourceThisWeek.source_provider || 'unknown'} · approve ${batchPrep.approvedCount} · в batch ${batchPrep.queuedCount}${batchPrep.errors.length ? ` · ошибок ${batchPrep.errors.length}` : ''}`
      );
      await refreshAllPartnershipData();
    });
  };

  const deleteLead = async (leadId: string) => {
    if (!currentBusinessId) return;
    const ok = window.confirm('Удалить этого партнёра из списка?');
    if (!ok) return;
    await runPartnershipAction('Не удалось удалить лида', async () => {
      await deletePartnershipLead(currentBusinessId, leadId);
      if (selectedLeadId === leadId) {
        setSelectedLeadId(null);
        setAuditData(null);
        setMatchData(null);
        setDraftText('');
      }
      setMessage('Лид удалён');
      await refreshOperationalData();
    });
  };

  const updateLeadStage = async (
    leadId: string,
    partnershipStage: string,
    successMessage: string,
    options?: { deferredReason?: string | null; deferredUntil?: string | null }
  ) => {
    if (!currentBusinessId) return;
    await runPartnershipAction('Не удалось обновить этап партнёра', async () => {
      await patchPartnershipLead(currentBusinessId, leadId, {
        partnership_stage: partnershipStage,
        deferred_reason: options?.deferredReason !== undefined ? options?.deferredReason : undefined,
        deferred_until: options?.deferredUntil !== undefined ? options?.deferredUntil : undefined,
      });
      setMessage(successMessage);
      if (partnershipStage === 'deferred') {
        setLeadBucket('deferred');
      }
      if (partnershipStage === 'selected_for_outreach') {
        setLeadBucket('active');
      }
      await refreshOperationalData();
    });
  };

  const updateLeadStageOptimistic = async (
    leadId: string,
    partnershipStage: string,
    options?: { deferredReason?: string | null; deferredUntil?: string | null }
  ) => {
    if (!currentBusinessId) return;
    const previousItems = items;
    setItems((prev) =>
      prev.map((item) =>
        item.id === leadId
          ? {
              ...item,
              partnership_stage: partnershipStage,
              deferred_reason: options?.deferredReason !== undefined ? options.deferredReason || undefined : item.deferred_reason,
              deferred_until: options?.deferredUntil !== undefined ? options.deferredUntil || undefined : item.deferred_until,
            }
          : item
      )
    );
    try {
      await patchPartnershipLead(currentBusinessId, leadId, {
        partnership_stage: partnershipStage,
        deferred_reason: options?.deferredReason !== undefined ? options?.deferredReason : undefined,
        deferred_until: options?.deferredUntil !== undefined ? options?.deferredUntil : undefined,
      });
    } catch (e: any) {
      setItems(previousItems);
      setError(e.message || 'Не удалось обновить этап партнёра');
    }
  };

  const handleLeadDragStart = (leadId: string) => (event: React.DragEvent<HTMLDivElement>) => {
    event.dataTransfer.setData('text/plain', leadId);
    event.dataTransfer.effectAllowed = 'move';
    setDraggingLeadId(leadId);
  };

  const handleLeadDragEnd = () => {
    setDraggingLeadId(null);
    setDropColumnId(null);
  };

  const handleColumnDragOver = (columnId: PartnershipBoardColumnId) => (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    if (dropColumnId !== columnId) {
      setDropColumnId(columnId);
    }
  };

  const handleColumnDrop = (columnId: PartnershipBoardColumnId) => async (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    const leadId = event.dataTransfer.getData('text/plain');
    setDraggingLeadId(null);
    setDropColumnId(null);
    if (!leadId) return;
    const lead = items.find((item) => item.id === leadId);
    if (!lead) return;
    const nextStage = partnershipBoardColumnMeta[columnId].stageToSet;
    if (String(lead.partnership_stage || '').toLowerCase() === nextStage) {
      return;
    }
    await updateLeadStageOptimistic(
      leadId,
      nextStage,
      columnId === 'deferred'
        ? {
            deferredReason: deferredReasonInput.trim() || lead.deferred_reason || '',
            deferredUntil: deferredUntilInput || String(lead.deferred_until || '').slice(0, 10) || '',
          }
        : { deferredReason: '', deferredUntil: '' }
    );
  };

  const approveDraft = async (draftId: string, text: string) => {
    if (!currentBusinessId) return;
    try {
      setLoading(true);
      setError(null);
      await approvePartnershipDraft(currentBusinessId, draftId, text);
      setMessage('Черновик утверждён');
      await loadDrafts();
      await loadBatches();
      await loadLeads();
      await loadFunnel();
      await loadOutcomes();
    } catch (e: any) {
      setError(e.message || 'Не удалось утвердить черновик');
    } finally {
      setLoading(false);
    }
  };

  const toggleDraftSelection = (draftId: string, checked: boolean) => {
    setSelectedDraftIds((prev) => {
      if (checked) return prev.includes(draftId) ? prev : [...prev, draftId];
      return prev.filter((id) => id !== draftId);
    });
  };

  const toggleAllDraftSelection = (checked: boolean) => {
    setSelectedDraftIds(checked ? visibleDrafts.map((draft) => draft.id) : []);
  };

  const bulkApproveDrafts = async () => {
    if (!currentBusinessId || selectedDraftIds.length === 0) return;
    try {
      setLoading(true);
      setError(null);
      await Promise.all(
        selectedDraftIds.map((draftId) => {
          const draft = drafts.find((item) => item.id === draftId);
          const text = draft?.approved_text || draft?.edited_text || draft?.generated_text || '';
          return approvePartnershipDraft(currentBusinessId, draftId, text);
        })
      );
      setMessage(`Утверждено черновиков: ${selectedDraftIds.length}`);
      setSelectedDraftIds([]);
      await loadDrafts();
      await loadBatches();
      await loadLeads();
    } catch (e: any) {
      setError(e.message || 'Не удалось массово утвердить черновики');
    } finally {
      setLoading(false);
    }
  };

  const bulkDeleteDrafts = async () => {
    if (!currentBusinessId || selectedDraftIds.length === 0) return;
    const ok = window.confirm(`Удалить выбранные черновики (${selectedDraftIds.length})?`);
    if (!ok) return;
    try {
      setLoading(true);
      setError(null);
      await Promise.all(
        selectedDraftIds.map((draftId) =>
          deletePartnershipDraft(currentBusinessId, draftId)
        )
      );
      setMessage(`Удалено черновиков: ${selectedDraftIds.length}`);
      setSelectedDraftIds([]);
      await loadDrafts();
      await loadBatches();
    } catch (e: any) {
      setError(e.message || 'Не удалось массово удалить черновики');
    } finally {
      setLoading(false);
    }
  };

  const createBatch = async () => {
    if (!currentBusinessId) return;
    try {
      setLoading(true);
      setError(null);
      const data = await createPartnershipBatch(currentBusinessId);
      if (data.batch?.id) {
        setMessage(`Batch создан: ${data.batch.id}`);
      } else {
        setMessage('Batch создан');
      }
      await loadBatches();
      await loadLeads();
      await loadFunnel();
      await loadOutcomes();
    } catch (e: any) {
      setError(e.message || 'Не удалось создать batch');
    } finally {
      setLoading(false);
    }
  };

  const approveBatch = async (batchId: string) => {
    if (!currentBusinessId) return;
    try {
      setLoading(true);
      setError(null);
      await approvePartnershipBatch(currentBusinessId, batchId);
      setMessage(`Batch утверждён: ${batchId}`);
      await loadBatches();
      await loadLeads();
      await loadFunnel();
      await loadOutcomes();
    } catch (e: any) {
      setError(e.message || 'Не удалось утвердить batch');
    } finally {
      setLoading(false);
    }
  };

  const toggleQueueSelection = (queueId: string, checked: boolean) => {
    setSelectedQueueIds((prev) => {
      if (checked) return prev.includes(queueId) ? prev : [...prev, queueId];
      return prev.filter((id) => id !== queueId);
    });
  };

  const toggleAllQueueSelection = (checked: boolean) => {
    const ids = visibleBatches.flatMap((batch) => (batch.items || []).map((item) => item.id));
    setSelectedQueueIds(checked ? ids : []);
  };

  const bulkUpdateQueueDelivery = async () => {
    if (!currentBusinessId || selectedQueueIds.length === 0) return;
    if (!bulkQueueStatus) {
      setError('Выберите delivery-статус для очереди');
      return;
    }
    try {
      setLoading(true);
      setError(null);
      await Promise.all(
        selectedQueueIds.map((queueId) =>
          updatePartnershipQueueDelivery(currentBusinessId, queueId, bulkQueueStatus)
        )
      );
      setMessage(`Обновлено queue-элементов: ${selectedQueueIds.length}`);
      setSelectedQueueIds([]);
      await loadBatches();
      await loadLeads();
      await loadOutcomes();
    } catch (e: any) {
      setError(e.message || 'Не удалось обновить очередь');
    } finally {
      setLoading(false);
    }
  };

  const bulkDeleteQueueItems = async () => {
    if (!currentBusinessId || selectedQueueIds.length === 0) return;
    const ok = window.confirm(`Удалить выбранные queue-элементы (${selectedQueueIds.length})?`);
    if (!ok) return;
    try {
      setLoading(true);
      setError(null);
      await Promise.all(
        selectedQueueIds.map((queueId) =>
          deletePartnershipQueueItem(currentBusinessId, queueId)
        )
      );
      setMessage(`Удалено queue-элементов: ${selectedQueueIds.length}`);
      setSelectedQueueIds([]);
      await loadBatches();
      await loadLeads();
    } catch (e: any) {
      setError(e.message || 'Не удалось удалить queue-элементы');
    } finally {
      setLoading(false);
    }
  };

  const recordReaction = async (
    queueId: string,
    outcome?: (typeof OUTCOME_OPTIONS)[number]
  ) => {
    if (!currentBusinessId) return;
    setSendQueueBusy((prev) => ({ ...prev, [queueId]: `reaction:${outcome || 'auto'}` }));
    try {
      await recordPartnershipReaction(currentBusinessId, queueId, outcome);
      setMessage('Реакция сохранена');
      await loadBatches();
      await loadLeads();
      await loadFunnel();
      await loadOutcomes();
    } catch (e: any) {
      setError(e.message || 'Не удалось сохранить реакцию');
    } finally {
      setSendQueueBusy((prev) => {
        const next = { ...prev };
        delete next[queueId];
        return next;
      });
    }
  };

  const confirmReaction = async (reactionId: string, outcome: (typeof OUTCOME_OPTIONS)[number]) => {
    if (!currentBusinessId) return;
    setReactionBusy((prev) => ({ ...prev, [reactionId]: outcome }));
    try {
      await confirmPartnershipReaction(currentBusinessId, reactionId, outcome);
      setMessage('Outcome подтверждён');
      await loadBatches();
      await loadLeads();
      await loadFunnel();
      await loadOutcomes();
    } catch (e: any) {
      setError(e.message || 'Не удалось подтвердить outcome');
    } finally {
      setReactionBusy((prev) => {
        const next = { ...prev };
        delete next[reactionId];
        return next;
      });
    }
  };

  const buildCurrentOperatorSnapshot = () => buildOperatorSnapshotPayload({
    business_id: currentBusinessId,
    pilot_summary: pilotSummary,
    ralph_loop: ralphLoop,
    blockers,
    funnel,
    outcomes,
    health,
    source_quality: sourceQuality,
  });

  const buildCurrentOperatorSnapshotMarkdown = () => buildOperatorSnapshotMarkdown(buildCurrentOperatorSnapshot());

  const exportWeeklyReview = () => {
    if (!currentBusinessId) return;
    try {
      setError(null);
      const stamp = new Date().toISOString().replace(/[:.]/g, '-');
      downloadTextFile(
        `partnership-weekly-review-${currentBusinessId}-${stamp}.md`,
        buildCurrentOperatorSnapshotMarkdown(),
        'text/markdown;charset=utf-8'
      );
      setMessage('Weekly review сформирован');
    } catch (e: any) {
      setError(e.message || 'Не удалось сформировать weekly review');
    }
  };

  const exportPartnershipReport = async (format: 'json' | 'markdown') => {
    if (!currentBusinessId) return;
    try {
      setLoading(true);
      setError(null);
      const data = await exportPartnershipData(currentBusinessId, format);
      const stamp = new Date().toISOString().replace(/[:.]/g, '-');
      if (format === 'markdown') {
        const md = `${String(data?.markdown_report || '')}\n\n---\n\n${buildCurrentOperatorSnapshotMarkdown()}`;
        downloadTextFile(`partnership-export-${currentBusinessId}-${stamp}.md`, md, 'text/markdown;charset=utf-8');
      } else {
        const payload = {
          ...(data || {}),
          operator_snapshot: buildCurrentOperatorSnapshot(),
        };
        downloadTextFile(
          `partnership-export-${currentBusinessId}-${stamp}.json`,
          JSON.stringify(payload, null, 2),
          'application/json;charset=utf-8'
        );
      }
      setMessage(`Экспорт (${format}) сформирован`);
    } catch (e: any) {
      setError(e.message || 'Не удалось экспортировать отчёт');
    } finally {
      setLoading(false);
    }
  };

  const downloadPartnershipCsvTemplate = () => {
    downloadTextFile('partnership-import-template.csv', buildPartnershipCsvTemplate(), 'text/csv;charset=utf-8');
  };

  const getNextPipelineStage = (item: PartnershipLead) => {
    const boardColumn = leadToPartnershipBoardColumn(item);
    const nextColumn = nextPartnershipBoardColumn(boardColumn);
    return nextColumn ? partnershipBoardColumnMeta[nextColumn].stageToSet : '';
  };

  const moveLeadToPipeline = (leadId: string) => {
    void updateLeadStageOptimistic(leadId, partnershipBoardColumnMeta.new.stageToSet, { deferredReason: '', deferredUntil: '' });
  };

  const moveLeadToStage = (leadId: string, stageValue: string, deferred: { deferredReason: string; deferredUntil: string }) => {
    void updateLeadStageOptimistic(leadId, stageValue, deferred);
  };

  const deferLeadFromCard = (lead: PartnershipLead, deferred: { deferredReason: string; deferredUntil: string }) => {
    void updateLeadStageOptimistic(lead.id, 'deferred', deferred);
  };


  return (
    <div className="space-y-6 pb-24">
      <PartnershipWorkspaceOverview
        workspaceView={workspaceView}
        currentBusinessId={currentBusinessId}
        rawLeadCount={rawLeadCount}
        pipelineLeadCount={pipelineLeadCount}
        visibleDraftsCount={visibleDrafts.length}
        visibleBatchesCount={visibleBatches.length}
        visibleReactionsCount={visibleReactions.length}
        onWorkspaceChange={(value) => setWorkspaceView(toPartnershipWorkspaceView(value))}
      />

      {!currentBusinessId ? (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          Сначала выберите бизнес в переключателе сверху.
        </div>
      ) : (
        <>
          {workspaceView === 'raw' ? (
          <>
          <PartnershipRawIntakeControls
            loading={loading}
            linksText={linksText}
            onLinksTextChange={setLinksText}
            onImportLinks={handleImportLinks}
            onRefreshLeads={() => void loadLeads()}
            importFileContent={importFileContent}
            importFileName={importFileName}
            importFileFormat={importFileFormat}
            importFileErrors={importFileErrors}
            onImportFilePick={(file) => void handleImportFilePick(file)}
            onImportFile={handleImportFile}
            onDownloadCsvTemplate={downloadPartnershipCsvTemplate}
            geoProvider={geoProvider}
            onGeoProviderChange={setGeoProvider}
            geoCity={geoCity}
            onGeoCityChange={setGeoCity}
            geoCategory={geoCategory}
            onGeoCategoryChange={setGeoCategory}
            geoQuery={geoQuery}
            onGeoQueryChange={setGeoQuery}
            geoRadiusKm={geoRadiusKm}
            onGeoRadiusKmChange={setGeoRadiusKm}
            geoLimit={geoLimit}
            onGeoLimitChange={setGeoLimit}
            onGeoSearch={handleGeoSearch}
            onResetGeoSearch={() => {
              setGeoProvider('google');
              setGeoCity('');
              setGeoCategory('');
              setGeoQuery('');
              setGeoRadiusKm('5');
              setGeoLimit('25');
            }}
          />
          <ProspectingIntakePanel
            title="Собранные лиды"
            description="Полный входящий поток geo-search и импорта. Здесь видно, кто ещё сырой, кого уже взяли в pipeline, кого отложили и кого отклонили."
            badges={[
              { label: 'Всего', value: rawLeadCount },
              { label: 'Сырые', value: rawLeadStatusSummary.imported },
              { label: 'В pipeline', value: rawLeadStatusSummary.inPipeline },
              { label: 'Отложены', value: rawLeadStatusSummary.deferred },
              { label: 'Отклонены', value: rawLeadStatusSummary.rejected },
              { label: 'Последний geo-search', value: lastGeoSearchLeadCount },
            ]}
          >
            {rawLeads.length === 0 ? (
              <div className="rounded-lg border border-dashed border-gray-300 bg-gray-50 p-4 text-sm text-muted-foreground">
                Сырых лидов пока нет. Запусти geo-search по радиусу, импортируй список или добавь ссылки вручную.
              </div>
            ) : (
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                {rawLeads.map((item) => (
                  <PartnershipLeadCard
                    key={item.id}
                    lead={item}
                    mode="raw"
                    dragging={false}
                    loading={loading}
                    nextStage={getNextPipelineStage(item)}
                    deferredReasonInput={deferredReasonInput}
                    deferredUntilInput={deferredUntilInput}
                    stagePresentation={partnershipStagePresentation(item)}
                    auditPresentation={partnershipAuditPresentation(item)}
                    onMoveToPipeline={moveLeadToPipeline}
                    onMoveToStage={moveLeadToStage}
                    onOpenLead={setSelectedLeadId}
                    onDeferLead={deferLeadFromCard}
                  />
                ))}
              </div>
            )}
          </ProspectingIntakePanel>
          </>
          ) : null}

          {workspaceView === 'analytics' ? (
            <PartnershipAnalyticsWorkspace
              loading={loading}
              health={health}
              pilotSummary={pilotSummary}
              bestSourceThisWeek={bestSourceThisWeek}
              ralphLoopPanel={(
                <Suspense
                  fallback={(
                    <div className="rounded-xl border bg-white p-4 text-sm text-muted-foreground">
                      Загружаем Ralph loop аналитики...
                    </div>
                  )}
                >
                  <RalphLoopAnalyticsPanel
                    loading={loading}
                    ralphLoop={ralphLoop}
                    onRefresh={() => void loadRalphLoop()}
                    onFocusBestSource={focusBestSourceLeads}
                    onMoveBestSourceToPilot={() => void moveBestSourceToPilot()}
                    onRunBestSourcePilotFlow={() => void runBestSourcePilotFlow()}
                    onPrepareBestSourceBatch={() => void prepareBestSourceBatch()}
                    hasBestSource={Boolean(bestSourceThisWeek)}
                  />
                </Suspense>
              )}
              funnel={funnel}
              sourceQuality={sourceQuality}
              blockers={blockers}
              outcomes={outcomes}
              onExportWeeklyReview={exportWeeklyReview}
              onExportReport={(format) => void exportPartnershipReport(format)}
              onLoadHealth={() => void loadHealth()}
              onFocusBestSourceLeads={focusBestSourceLeads}
              onMoveBestSourceToPilot={() => void moveBestSourceToPilot()}
              onRunBestSourcePilotFlow={() => void runBestSourcePilotFlow()}
              onPrepareBestSourceBatch={() => void prepareBestSourceBatch()}
              onLoadFunnel={() => void loadFunnel()}
              onLoadSourceQuality={() => void loadSourceQuality()}
              onLoadBlockers={() => void loadBlockers()}
              onLoadOutcomes={() => void loadOutcomes()}
            />
          ) : null}

          {workspaceView === 'pipeline' ? (
          <>
          <div className="rounded-xl border bg-white p-4 space-y-4">
            <div className="flex items-center justify-between gap-2">
              <div>
                <h2 className="text-lg font-semibold">Pipeline партнёрств</h2>
                <p className="text-sm text-muted-foreground">Рабочая доска по партнёрским лидам: от новых до контакта и отложенных.</p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Badge variant="secondary">С аудитом: {pipelineSummary.withAudit}</Badge>
                <Badge variant="secondary">Готово к контакту: {pipelineSummary.readyToContact}</Badge>
                <Badge variant="secondary">Отложено: {pipelineSummary.deferred}</Badge>
              </div>
            </div>
            <PartnershipPipelineBoard
              columns={partnershipBoardColumns}
              dropColumnId={dropColumnId}
              draggingLeadId={draggingLeadId}
              loading={loading}
              deferredReasonInput={deferredReasonInput}
              deferredUntilInput={deferredUntilInput}
              getStagePresentation={partnershipStagePresentation}
              getAuditPresentation={partnershipAuditPresentation}
              getNextStage={getNextPipelineStage}
              onColumnDragOver={handleColumnDragOver}
              onColumnDragLeave={() => setDropColumnId(null)}
              onColumnDrop={handleColumnDrop}
              onLeadDragStart={handleLeadDragStart}
              onLeadDragEnd={handleLeadDragEnd}
              onMoveToPipeline={moveLeadToPipeline}
              onMoveToStage={moveLeadToStage}
              onOpenLead={setSelectedLeadId}
              onDeferLead={deferLeadFromCard}
            />
          </div>
          <div className="grid gap-4 xl:grid-cols-12">
            <PartnershipPipelineList
              query={query}
              onQueryChange={setQuery}
              stage={stage}
              onStageChange={setStage}
              stageOptions={STAGE_OPTIONS}
              pilotCohort={pilotCohort}
              onPilotCohortChange={(value) => setPilotCohort(toPilotCohort(value))}
              pilotCohortOptions={PILOT_COHORT_OPTIONS}
              leadView={leadView}
              onLeadViewChange={(value) => setLeadView(toLeadView(value))}
              leadViewOptions={LEAD_VIEW_OPTIONS}
              leadBucket={leadBucket}
              onLeadBucketChange={(value) => {
                setLeadBucket(value);
                if (value === 'deferred') setLeadView('all');
              }}
              loading={loading}
              itemsTotal={items.length}
              shortlistCount={items.filter((item) => String(item.partnership_stage || '').toLowerCase() === 'selected_for_outreach').length}
              deferredLeadsCount={deferredLeadsCount}
              overdueDeferredLeadsCount={overdueDeferredLeadsCount}
              preferredSourceLabel={preferredSourceFilter ? `${preferredSourceFilter.source_kind || 'unknown'} / ${preferredSourceFilter.source_provider || 'unknown'}` : null}
              lastGeoSearchLeadCount={lastGeoSearchLeadCount}
              lastGeoSearchSourceLabel={`${lastGeoSearchSourceSummary?.source_kind || '—'} / ${lastGeoSearchSourceSummary?.source_provider || '—'}`}
              lastGeoSearchMatchesBestSource={lastGeoSearchMatchesBestSource}
              lastGeoSearchStats={lastGeoSearchStats}
              lastGeoSearchFlowSummary={lastGeoSearchFlowSummary}
              selectedLeadIds={selectedLeadIds}
              visibleLeads={visibleLeads}
              selectedLeadId={selectedLeadId}
              bulkStage={bulkStage}
              onBulkStageChange={setBulkStage}
              bulkStageOptions={BULK_STAGE_OPTIONS}
              bulkChannel={bulkChannel}
              onBulkChannelChange={setBulkChannel}
              channelOptions={CHANNEL_OPTIONS}
              bulkPilotCohort={bulkPilotCohort}
              onBulkPilotCohortChange={setBulkPilotCohort}
              deferredReasonInput={deferredReasonInput}
              onDeferredReasonInputChange={setDeferredReasonInput}
              deferredUntilInput={deferredUntilInput}
              onDeferredUntilInputChange={setDeferredUntilInput}
              onRefreshLeads={() => void loadLeads()}
              onLoadHealth={() => void loadHealth()}
              onApplyBulkUpdate={applyBulkUpdate}
              onBulkDeferLeads={bulkDeferLeads}
              onBulkReturnDeferredLeads={bulkReturnDeferredLeads}
              onBulkReturnOverdueDeferredLeads={bulkReturnOverdueDeferredLeads}
              onBulkEnrichContacts={() => void bulkEnrichContacts()}
              onNormalizeSelectedViaOpenClaw={normalizeSelectedViaOpenClaw}
              onBulkDeleteLeads={bulkDeleteLeads}
              onToggleAllLeadSelection={toggleAllLeadSelection}
              onToggleLeadSelection={toggleLeadSelection}
              onRunParse={(leadId) => void runParse(leadId)}
              onEnrichContacts={(leadId) => void enrichContacts(leadId)}
              onRunAudit={(leadId) => void runAudit(leadId)}
              onRunMatch={(leadId) => void runMatch(leadId)}
              onUpdateLeadStage={(leadId, stageValue, successMessage, deferred) => void updateLeadStage(leadId, stageValue, successMessage, deferred)}
              onDeleteLead={(leadId) => void deleteLead(leadId)}
              onClearLastGeoSearch={() => {
                setLeadView('all');
                setLastGeoSearchLeadIds([]);
                setSelectedLeadIds([]);
              }}
              onMoveLastGeoSearchToPilot={() => void moveLastGeoSearchToPilot()}
              onRunLastGeoSearchFlow={() => void runLastGeoSearchFlow()}
              onPrepareLastGeoSearchBatch={() => void prepareLastGeoSearchBatch()}
            />

            <div className="space-y-4 xl:col-span-5">
              <div className="rounded-xl border bg-white p-4 space-y-3">
                <div className="flex items-center justify-between gap-2">
                  <h2 className="text-lg font-semibold">Метрики обучения (30 дней)</h2>
                  <Button variant="outline" onClick={() => void loadLearningMetrics()} disabled={loading}>
                    Обновить
                  </Button>
                </div>
                {learningMetrics.length === 0 ? (
                  <p className="text-sm text-muted-foreground">Метрики пока недоступны.</p>
                ) : (
                  <div className="grid gap-2 md:grid-cols-2">
                    {learningMetrics.map((metric) => (
                      <div key={metric.capability} className="rounded-lg border border-gray-200 p-3 bg-gray-50">
                        <div className="text-sm font-semibold text-foreground">{metric.capability}</div>
                        <div className="text-xs text-muted-foreground mt-1">
                          Принято: {metric.accepted_total} · без правок: {metric.accepted_raw_total} ({metric.accepted_raw_pct}%)
                        </div>
                        <div className="text-xs text-muted-foreground">
                          С правками: {metric.accepted_edited_total} ({metric.edited_before_accept_pct}%)
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
          </>
          ) : null}

          {(workspaceView === 'drafts' || workspaceView === 'queue') ? (
          <>
          {workspaceView === 'drafts' ? (
          <PartnershipDraftsSection
            drafts={visibleDrafts}
            selectedDraftIds={selectedDraftIds}
            draftView={draftView}
            draftViewOptions={DRAFT_VIEW_OPTIONS}
            loading={loading}
            onDraftViewChange={(value) => setDraftView(toDraftView(value))}
            onRefresh={() => void loadDrafts()}
            onBulkApprove={bulkApproveDrafts}
            onBulkDelete={bulkDeleteDrafts}
            onToggleAll={toggleAllDraftSelection}
            onToggleDraft={toggleDraftSelection}
            onDraftTextChange={(draftId, value) =>
              setDrafts((prev) =>
                prev.map((item) => (item.id === draftId ? { ...item, approved_text: value } : item))
              )
            }
            onApproveDraft={(draftId, text) => void approveDraft(draftId, text)}
          />
          ) : null}

          {workspaceView === 'queue' ? (
          <PartnershipQueueSection
            batches={visibleBatches}
            selectedQueueIds={selectedQueueIds}
            queueView={queueView}
            queueViewOptions={QUEUE_VIEW_OPTIONS}
            bulkQueueStatus={bulkQueueStatus}
            queueReadyDraftsCount={queueReadyDrafts.length}
            loading={loading}
            sendQueueBusy={sendQueueBusy}
            outcomeOptions={OUTCOME_OPTIONS}
            onQueueViewChange={(value) => setQueueView(toQueueView(value))}
            onRefresh={() => void loadBatches()}
            onCreateBatch={createBatch}
            onBulkQueueStatusChange={setBulkQueueStatus}
            onBulkUpdateDelivery={bulkUpdateQueueDelivery}
            onBulkDeleteQueueItems={bulkDeleteQueueItems}
            onToggleAll={toggleAllQueueSelection}
            onToggleQueueItem={toggleQueueSelection}
            onApproveBatch={(batchId) => void approveBatch(batchId)}
            onRecordReaction={(queueId, outcome) => void recordReaction(queueId, outcome)}
          />
          ) : null}
          </>
          ) : null}

          {workspaceView === 'sent' ? (
          <PartnershipSentSection
            reactions={visibleReactions}
            reactionView={reactionView}
            reactionViewOptions={REACTION_VIEW_OPTIONS}
            loading={loading}
            reactionBusy={reactionBusy}
            outcomeOptions={OUTCOME_OPTIONS}
            onReactionViewChange={(value) => setReactionView(toReactionView(value))}
            onRefresh={() => void loadBatches()}
            onConfirmReaction={(reactionId, outcome) => void confirmReaction(reactionId, outcome)}
          />
          ) : null}

          {selectedLead ? (
            <Suspense
              fallback={
                <div className="fixed inset-0 z-50 bg-black/25 backdrop-blur-sm">
                  <div className="absolute inset-y-0 right-0 w-full max-w-3xl overflow-y-auto border-l border-border bg-background shadow-2xl">
                    <div className="px-5 py-5 text-sm text-muted-foreground">Загружаем карточку партнёрского лида...</div>
                  </div>
                </div>
              }
            >
              <PartnershipLeadDetailDrawer
                selectedLead={selectedLead}
                selectedLeadFlowStatus={selectedLeadFlowStatus}
                stagePresentation={partnershipStagePresentation(selectedLead)}
                auditPresentation={partnershipAuditPresentation(selectedLead)}
                onClose={() => setSelectedLeadId(null)}
                auditData={auditData}
                matchData={matchData}
                draftText={draftText}
                selectedLeadLogo={selectedLeadLogo}
                selectedLeadPhotos={selectedLeadPhotos}
                leadEdit={leadEdit}
                setLeadEdit={setLeadEdit}
                loading={loading}
                onSaveLeadContacts={() => void saveLeadContacts()}
                currentBusinessId={currentBusinessId}
                pilotCohortOptions={PILOT_COHORT_OPTIONS.filter((option) => option.value !== 'all')}
                onPilotCohortChange={async (value) => {
                  if (!currentBusinessId || !selectedLead) return;
                  try {
                    setLoading(true);
                    setError(null);
                    await patchPartnershipLead(currentBusinessId, selectedLead.id, { pilot_cohort: value });
                    setMessage(`Когорта обновлена: ${value}`);
                    await loadLeads();
                    await loadRalphLoop();
                  } catch (error: unknown) {
                    const message = error instanceof Error ? error.message : 'Не удалось обновить когорту';
                    setError(message);
                  } finally {
                    setLoading(false);
                  }
                }}
              />
            </Suspense>
          ) : null}

          {workspaceView === 'pipeline' ? (
            <PartnershipPipelineBulkBar
              selectedCount={selectedLeadIds.length}
              loading={loading}
              canApplyStageOrChannel={Boolean(bulkStage || bulkChannel)}
              onBulkRunParse={bulkRunParse}
              onBulkEnrichContacts={() => void bulkEnrichContacts()}
              onBulkRunMatch={bulkRunMatch}
              onApplyBulkUpdate={applyBulkUpdate}
              onNormalizeSelectedViaOpenClaw={normalizeSelectedViaOpenClaw}
              onBulkDeleteLeads={bulkDeleteLeads}
            />
          ) : null}
        </>
      )}

      {message && (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-2 text-sm text-emerald-800">
          {message}
        </div>
      )}
      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">
          {error}
        </div>
      )}
    </div>
  );
};
