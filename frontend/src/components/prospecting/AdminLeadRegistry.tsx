import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ArrowRight,
  Building2,
  Check,
  ChevronDown,
  CircleAlert,
  ExternalLink,
  Filter,
  MapPin,
  MessageCircle,
  Plus,
  RadioTower,
  RefreshCw,
  Search,
  Send,
  ShieldCheck,
  Sparkles,
  UserRound,
  Users,
} from 'lucide-react';
import { newAuth } from '../../lib/auth_new';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { Input } from '../ui/input';
import { Checkbox } from '../ui/checkbox';
import { OutreachEmailSetup } from '../OutreachEmailSetup';
import { OutreachLearningInsights } from './OutreachLearningInsights';
import { OutreachSuppressionManager } from './OutreachSuppressionManager';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '../ui/sheet';

const LegacyProspectingManagement = React.lazy(() =>
  import('../ProspectingManagement').then((module) => ({ default: module.ProspectingManagement })),
);

type WorkstreamType = 'localos_sales' | 'client_partnership';
type SenderMode = 'localos' | 'partner_business' | 'localos_for_partner';
type RegistryView = 'leads' | 'messages' | 'results';
type ScopeFilter = 'all' | 'localos_sales' | 'client_partnership';

interface BusinessOption {
  id: string;
  name: string;
  owner: string;
  address?: string;
}

interface ClientFilterOption {
  id: string;
  name: string;
}

interface WorkstreamState {
  code?: string;
  label?: string;
  url?: string | null;
}

interface WorkstreamAction {
  code?: string;
  label?: string;
}

interface ResearchSource {
  title?: string;
  url?: string;
  source_type?: string;
  published_at?: string;
}

interface WorkstreamResearch {
  id?: string;
  score?: number;
  qualification_stage?: string;
  signal_label?: 'strong_signal' | 'reason_to_check' | 'fit_only';
  why_now?: string;
  sources?: ResearchSource[];
  suggested_opener?: string;
  opener_source_url?: string;
  limitations?: string[];
  researched_at?: string;
  stale?: boolean;
}

interface ContactPoint {
  id: string;
  type?: string;
  value?: string;
  owner_type?: 'company' | 'person';
  person_name?: string | null;
  role_title?: string | null;
  source_url?: string | null;
  source_type?: string;
  confidence?: number;
  verification_status?: string;
  observed_at?: string;
  verified_at?: string | null;
}

interface MessageReadiness {
  code?: 'ready' | 'needs_contact' | 'needs_facts' | 'needs_evidence' | 'suppressed';
  label?: string;
  missing?: string[];
  missing_items?: Array<{
    code?: string;
    label?: string;
  }>;
}

interface EnrichmentState {
  id?: string;
  status?: string;
  phase?: string;
  error?: string | null;
  updated_at?: string;
}

interface ContactIntelligence {
  contacts?: ContactPoint[];
  contact_summary?: { found?: number; verified?: number };
  telegram_sources?: Array<{
    id: string;
    title?: string;
    url?: string;
    status?: 'candidate' | 'active' | 'paused';
    sync_status?: 'idle' | 'queued' | 'syncing' | 'ready' | 'partial' | 'failed' | 'needs_account';
    reference_type?: 'public_reference_unverified' | 'public_channel' | 'personal_or_unavailable';
    permission_reason?: 'ready' | 'radar_permission_required' | 'telegram_account_required';
    documents_count?: number;
    last_collected_at?: string | null;
    error?: string | null;
  }>;
  selected_recipient?: ContactPoint | null;
  job?: {
    id?: string;
    status?: string;
    phase?: string;
    message_brief?: Record<string, unknown>;
    message_readiness?: MessageReadiness;
    result?: { draft_id?: string | null };
    error?: string | null;
  } | null;
  sender_profile?: {
    id?: string;
    display_name?: string;
    role_title?: string;
    company_name?: string;
    competence_story?: string | null;
    proof_points_json?: Array<string | { fact?: string; status?: string }>;
    verified_cases_json?: Array<string | { fact?: string; status?: string }>;
    allowed_offers_json?: string[];
    forbidden_claims_json?: string[];
    voice_examples_json?: string[];
    outreach_context_json?: {
      product_outcome?: string;
      audience?: string;
      segments?: string[];
      geography?: string;
      recipient_roles?: string[];
      desired_partner_types?: string[];
      disqualifiers?: string[];
      allowed_ctas?: string[];
    };
    confirmed_at?: string | null;
  } | null;
  sender_profile_completeness?: {
    ready?: boolean;
    status?: 'ready' | 'draft';
    completed_count?: number;
    required_count?: number;
    items?: Array<{
      code?: string;
      title?: string;
      label?: string;
      complete?: boolean;
    }>;
    missing_items?: Array<{ code?: string; label?: string }>;
  };
  sender_profile_suggestions?: {
    display_name?: string;
    company_name?: string;
    geography?: string;
    services?: string[];
    desired_partner_types?: string[];
    requires_confirmation?: boolean;
  } | null;
  first_message?: {
    id?: string;
    channel?: string;
    status?: string;
    generated_text?: string;
    edited_text?: string | null;
    approved_text?: string | null;
    message_brief_json?: Record<string, unknown>;
    quality_gate_json?: { passed?: boolean; failures?: string[]; word_count?: number };
    generation_current?: boolean;
    requires_regeneration?: boolean;
  } | null;
}

interface OutreachQualityGate {
  passed?: boolean;
  verdict?: 'approve' | 'revise' | 'reject';
  score?: number;
  total_score?: number;
  max_score?: number;
  criterion_scores?: Record<string, number>;
  reason_codes?: string[];
}

interface OutreachTouchPreview {
  sequence_index: number;
  channel: string;
  day_offset: number;
  angle: string;
  subject?: string | null;
  text: string;
  channel_status: 'ready' | 'connect_required' | 'permission_required' | 'manual' | 'recipient_missing' | 'adapter_unavailable' | 'sender_degraded' | 'sender_paused' | 'sender_selection_required';
  quality_gate?: OutreachQualityGate;
  source_url?: string | null;
  observation?: string | null;
  problem_hypothesis?: string | null;
  relevance_bridge?: string | null;
}

interface OutreachPreview {
  status?: 'ready' | 'needs_evidence' | 'needs_generation' | 'needs_revision' | 'needs_channel_setup' | 'invalid_sequence' | 'suppressed';
  missing?: string[];
  evidence?: Array<{ id?: string; fact?: string; source_url?: string; confidence?: number }>;
  generation?: { status?: string; source?: string; error?: string | null };
  quality_gate?: OutreachQualityGate;
  channel_availability?: Record<string, {
    status?: string;
    recipient?: string | null;
    sender_account_id?: string | null;
    sender_accounts?: Array<{
      id: string;
      sender_identity?: string | null;
      display_name?: string | null;
      status?: string;
    }>;
  }>;
  touches?: OutreachTouchPreview[];
  sequence_issues?: string[];
  sender_mode?: SenderMode;
  sender_scope_type?: 'platform' | 'business';
  represented_business_id?: string | null;
  represented_business_name?: string | null;
}

interface SavedOutreachCampaign {
  id: string;
  version?: number;
  status?: string;
  stop_reason?: string | null;
  generation_current?: boolean;
  requires_regeneration?: boolean;
  policy_json?: {
    sender_mode?: SenderMode;
    represented_business_id?: string | null;
  };
  touches?: Array<{
    id?: string;
    sequence_index?: number;
    channel?: string;
    status?: string;
    sender_account_id?: string | null;
    message_brief_json?: { channel_status?: string };
  }>;
}

interface PilotReadiness {
  status?: string;
  reason_code?: string;
  can_dispatch_first_touch?: boolean;
  next_action?: string;
  checks?: Array<{
    code?: string;
    label?: string;
    passed?: boolean;
  }>;
}

interface LeadWorkstream {
  id?: string | null;
  workstream_type: WorkstreamType;
  client_business_id?: string | null;
  client_business_name?: string | null;
  status?: string;
  selected_channel?: string | null;
  last_contact_at?: string | null;
  channel_state?: WorkstreamState;
  room_state?: WorkstreamState;
  next_action?: WorkstreamAction;
  research?: WorkstreamResearch | null;
  contact_points?: ContactPoint[];
  contact_summary?: { found?: number; verified?: number };
  selected_recipient?: ContactPoint | null;
  enrichment_state?: EnrichmentState | null;
  message_readiness?: MessageReadiness;
  service_compatibility_score?: number | null;
  legacy?: boolean;
}

interface LeadItem {
  id: string;
  name?: string;
  category?: string;
  city?: string;
  address?: string;
  phone?: string;
  email?: string;
  website?: string;
  telegram_url?: string;
  whatsapp_url?: string;
  source?: string;
  source_kind?: string;
  source_provider?: string;
  rating?: number;
  reviews_count?: number;
  status?: string;
  pipeline_status?: string;
  lead_kind?: 'localos' | 'partner' | 'both';
  client_business_name?: string;
  workstreams?: LeadWorkstream[];
}

interface SearchResult extends LeadItem {
  source_url?: string;
  google_id?: string;
}

interface AdminLeadRegistryProps {
  businessOptions: BusinessOption[];
  senderBusinessLabel?: string;
}

const viewOptions: Array<{ id: RegistryView; label: string }> = [
  { id: 'leads', label: 'Лиды' },
  { id: 'messages', label: 'Сообщения' },
  { id: 'results', label: 'Результаты' },
];

const scopeOptions: Array<{ id: ScopeFilter; label: string }> = [
  { id: 'all', label: 'Все' },
  { id: 'localos_sales', label: 'LocalOS' },
  { id: 'client_partnership', label: 'Партнёры клиентов' },
];

const outreachQualityCriterionLabels: Record<string, string> = {
  source_validity: 'Надёжность источника',
  observation_accuracy: 'Точность наблюдения',
  freshness_and_why_now: 'Актуальность сигнала',
  offer_bridge: 'Связь с предложением',
  recipient_specificity: 'Конкретность для получателя',
  proof_integrity: 'Подтверждение опыта',
  channel_fit: 'Естественность для канала',
  single_cta_and_length: 'Один вопрос и длина',
  state_and_suppression_safety: 'Безопасность контакта',
};

const outreachQualityReasonLabels: Record<string, string> = {
  SOURCE_MISSING: 'Не хватает подтверждённого источника',
  SOURCE_MISMATCH: 'Источник не подтверждает наблюдение',
  STALE_AS_CURRENT: 'Устаревший сигнал используется как текущий',
  INFERENCE_AS_FACT: 'Гипотеза подана как факт',
  DECORATIVE_PERSONALIZATION: 'Персонализация не меняет причину обращения',
  WEAK_OFFER_BRIDGE: 'Неясно, как сигнал связан с предложением',
  UNSUPPORTED_PROOF: 'Опыт отправителя не подтверждён',
  MULTIPLE_CTA: 'В сообщении больше одного следующего шага',
  CHANNEL_LIMIT_EXCEEDED: 'Текст не подходит выбранному каналу',
  STYLE_VIOLATION: 'Текст звучит неестественно или нарушает голос',
  TERMINAL_CONTACT_STATE: 'Контакт уже находится в конечном статусе',
  SUPPRESSED_CONTACT: 'Получатель находится в stop-list',
  APPROVAL_BYPASS: 'Требуется новое ручное подтверждение',
  SENSITIVE_TARGETING: 'Сигнал нельзя безопасно использовать в сообщении',
};

const outreachQualityVerdictLabels: Record<string, string> = {
  approve: 'Можно подтверждать',
  revise: 'Нужно исправить',
  reject: 'Нельзя использовать',
};

const statusLabels: Record<string, string> = {
  unprocessed: 'Новый',
  in_progress: 'В работе',
  contacted: 'Сообщение отправлено',
  waiting_reply: 'Ждём ответ',
  replied: 'Есть ответ',
  responded: 'Есть ответ',
  converted: 'Результат получен',
  qualified: 'Результат получен',
  postponed: 'Отложен',
  not_relevant: 'Не подходит',
  closed_lost: 'Закрыт',
};

const sourceLabel = (lead: LeadItem) => {
  const provider = String(lead.source_provider || lead.source || '').toLowerCase();
  const partner = (lead.workstreams || []).find((item) => item.workstream_type === 'client_partnership');
  if (partner?.client_business_name) {
    return `Найден рядом с ${partner.client_business_name}`;
  }
  if (provider.includes('manual')) {
    return 'Добавлен вручную';
  }
  if (provider.includes('google') || provider.includes('yandex') || provider.includes('2gis') || provider.includes('apify')) {
    return 'Найден LocalOS';
  }
  return 'Добавлен в работу';
};

const workstreamLabel = (workstream: LeadWorkstream) => {
  if (workstream.workstream_type === 'localos_sales') {
    return 'Лид LocalOS';
  }
  return `Лид-партнёр · ${workstream.client_business_name || 'клиент'}`;
};

const statusLabel = (workstream: LeadWorkstream) =>
  statusLabels[String(workstream.status || 'unprocessed')] || 'В работе';

const availableContacts = (lead: LeadItem) => [
  lead.telegram_url ? 'Telegram' : '',
  lead.whatsapp_url ? 'WhatsApp' : '',
  lead.email ? 'Email' : '',
  lead.phone ? 'Телефон' : '',
].filter(Boolean);

const contactTypeLabels: Record<string, string> = {
  phone: 'Телефон',
  email: 'Email',
  telegram: 'Telegram',
  whatsapp: 'WhatsApp',
  vk: 'VK',
  instagram: 'Instagram',
  max: 'MAX',
  website_form: 'Форма на сайте',
  website: 'Сайт',
  other: 'Другой канал',
};

const verificationLabel = (status?: string) => {
  if (status === 'verified') return 'Проверен';
  if (status === 'confirmed_source') return 'Подтверждён источником';
  if (status === 'valid_format') return 'Формат проверен';
  if (status === 'accept_all') return 'Домен принимает все адреса';
  if (status === 'invalid') return 'Не работает';
  if (status === 'stale') return 'Нужно обновить';
  return 'Нужна проверка';
};

const enrichmentLabel = (state?: EnrichmentState | null) => {
  if (!state) return 'Проверка не запускалась';
  if (state.status === 'ready') return 'Готово к проверке';
  if (state.status === 'needs_input') return 'Нужны данные';
  if (state.status === 'failed') return 'Не удалось подготовить';
  if (state.status === 'retry_wait') return 'Повторяем проверку';
  if (state.phase === 'collecting') return 'Собираем контакты';
  if (state.phase === 'verifying') return 'Проверяем контакты';
  if (state.phase === 'researching') return 'Ищем основание для обращения';
  if (state.phase === 'drafting') return 'Готовим первое письмо';
  return 'Подготовка запущена';
};

const actionTone = (code?: string) => {
  if (code === 'find_contact') return 'text-amber-700';
  if (code === 'prepare_room') return 'text-orange-700';
  if (code === 'record_result') return 'text-emerald-700';
  return 'text-slate-700';
};

const signalLabel = (research?: WorkstreamResearch | null) => {
  if (research?.stale) return 'Нужно обновить';
  if (research?.signal_label === 'strong_signal') return 'Сильный сигнал';
  if (research?.signal_label === 'reason_to_check') return 'Есть повод';
  if (research) return 'Только соответствие';
  return '';
};

const signalTone = (research?: WorkstreamResearch | null) => {
  if (research?.stale) return 'border-amber-200 bg-amber-50 text-amber-800';
  if (research?.signal_label === 'strong_signal') return 'border-emerald-200 bg-emerald-50 text-emerald-800';
  if (research?.signal_label === 'reason_to_check') return 'border-sky-200 bg-sky-50 text-sky-800';
  return 'border-slate-200 bg-slate-50 text-slate-700';
};

const strongestResearch = (workstreams: LeadWorkstream[]) => workstreams
  .map((item) => item.research)
  .filter((item): item is WorkstreamResearch => Boolean(item))
  .sort((left, right) => Number(right.score || 0) - Number(left.score || 0))[0] || null;

const wait = (milliseconds: number) => new Promise((resolve) => window.setTimeout(resolve, milliseconds));

const readinessCodeFromLegacyLabel = (label: string) => {
  const normalized = label.trim().toLowerCase();
  if (normalized.includes('профил') && normalized.includes('отправител')) return 'sender_profile';
  if (normalized.includes('опыт основателя') || normalized.includes('опыт команды')) return 'sender_experience';
  if (normalized.includes('доказательство') || normalized.includes('кейс')) return 'sender_proof';
  if (normalized.includes('совместим') || normalized.includes('полезны друг другу')) return 'partner_compatibility';
  if (normalized.includes('категори') && normalized.includes('партн')) return 'partner_category';
  if (normalized.includes('контакт')) return 'recipient_contact';
  if (normalized.includes('роль получателя')) return 'recipient_role';
  if (normalized.includes('почему сейчас') || normalized.includes('публичный сигнал')) return 'timing_signal';
  if (normalized.includes('проблем')) return 'confirmed_problem';
  if (normalized.includes('результат первого шага')) return 'first_step_result';
  if (normalized.includes('сегмент')) return 'lead_segment';
  if (normalized.includes('stop-list')) return 'suppression';
  return 'research_evidence';
};

export function AdminLeadRegistry({ businessOptions, senderBusinessLabel = 'ваш бизнес' }: AdminLeadRegistryProps) {
  const [view, setView] = useState<RegistryView>('leads');
  const [scope, setScope] = useState<ScopeFilter>('all');
  const [clientBusinessId, setClientBusinessId] = useState('');
  const [actionState, setActionState] = useState('');
  const [signalStrength, setSignalStrength] = useState('');
  const [query, setQuery] = useState('');
  const [leads, setLeads] = useState<LeadItem[]>([]);
  const [clientFilterOptions, setClientFilterOptions] = useState<ClientFilterOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selectedLeadId, setSelectedLeadId] = useState<string | null>(null);
  const [selectedWorkstreamId, setSelectedWorkstreamId] = useState<string | null>(null);
  const [busyAction, setBusyAction] = useState('');
  const [notice, setNotice] = useState('');
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchStep, setSearchStep] = useState(1);
  const [searchScope, setSearchScope] = useState<WorkstreamType>('localos_sales');
  const [searchClientId, setSearchClientId] = useState('');
  const [searchCategory, setSearchCategory] = useState('');
  const [searchLocation, setSearchLocation] = useState('');
  const [searchRadius, setSearchRadius] = useState('1000');
  const [searchSource, setSearchSource] = useState('apify_yandex');
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [selectedSearchIds, setSelectedSearchIds] = useState<string[]>([]);
  const [searchBusy, setSearchBusy] = useState(false);
  const [searchError, setSearchError] = useState('');
  const [contactIntelligence, setContactIntelligence] = useState<ContactIntelligence | null>(null);
  const [contactIntelligenceLoading, setContactIntelligenceLoading] = useState(false);
  const [senderName, setSenderName] = useState('');
  const [senderRole, setSenderRole] = useState('');
  const [senderCompany, setSenderCompany] = useState('');
  const [senderStory, setSenderStory] = useState('');
  const [senderProof, setSenderProof] = useState('');
  const [senderOffer, setSenderOffer] = useState('');
  const [senderForbidden, setSenderForbidden] = useState('');
  const [senderVoiceExample, setSenderVoiceExample] = useState('');
  const [senderOutcome, setSenderOutcome] = useState('');
  const [senderAudience, setSenderAudience] = useState('');
  const [senderSegments, setSenderSegments] = useState('');
  const [senderGeography, setSenderGeography] = useState('');
  const [senderRecipientRoles, setSenderRecipientRoles] = useState('');
  const [senderPartnerTypes, setSenderPartnerTypes] = useState('');
  const [senderDisqualifiers, setSenderDisqualifiers] = useState('');
  const [senderCtas, setSenderCtas] = useState('');
  const [senderFactsOpen, setSenderFactsOpen] = useState(false);
  const [outreachPreview, setOutreachPreview] = useState<OutreachPreview | null>(null);
  const [savedOutreachCampaign, setSavedOutreachCampaign] = useState<SavedOutreachCampaign | null>(null);
  const [pilotReadiness, setPilotReadiness] = useState<PilotReadiness | null>(null);
  const [sequenceChannels, setSequenceChannels] = useState(['telegram', 'email', 'max', 'vk']);
  const [sequenceDays, setSequenceDays] = useState([0, 3, 7, 12]);
  const [sequenceSenders, setSequenceSenders] = useState<Record<number, string>>({});
  const [senderMode, setSenderMode] = useState<SenderMode>('localos');

  const loadLeads = useCallback(async () => {
    setLoading(true);
    setError('');
    const params = new URLSearchParams({ compact: '1', include_groups: '0', include_timeline: '0' });
    if (scope !== 'all') params.set('workstream_type', scope);
    if (clientBusinessId) params.set('client_business_id', clientBusinessId);
    if (actionState) params.set('action_state', actionState);
    try {
      const payload = await newAuth.makeRequest(`/admin/prospecting/leads?${params.toString()}`);
      setLeads(Array.isArray(payload?.leads) ? payload.leads : []);
      setClientFilterOptions(Array.isArray(payload?.client_options) ? payload.client_options : []);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось загрузить лидов');
    } finally {
      setLoading(false);
    }
  }, [scope, clientBusinessId, actionState]);

  useEffect(() => {
    loadLeads();
  }, [loadLeads]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const leadId = params.get('lead');
    const workstreamId = params.get('workstream');
    if (leadId && leads.some((lead) => lead.id === leadId)) {
      setSelectedLeadId(leadId);
      setSelectedWorkstreamId(workstreamId);
    }
  }, [leads]);

  const filteredLeads = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return leads.filter((lead) => {
      if (normalized) {
        const haystack = [lead.name, lead.category, lead.city, lead.address, lead.phone, lead.email]
          .filter(Boolean)
          .join(' ')
          .toLowerCase();
        if (!haystack.includes(normalized)) return false;
      }
      const workstreams = lead.workstreams || [];
      if (signalStrength && !workstreams.some((item) => item.research?.signal_label === signalStrength)) return false;
      if (view === 'messages') {
        return workstreams.some((item) => item.channel_state?.code !== 'choose_channel' || item.room_state?.code !== 'missing');
      }
      if (view === 'results') {
        return workstreams.some((item) => ['replied', 'responded', 'converted', 'qualified'].includes(String(item.status || '')));
      }
      return true;
    });
  }, [leads, query, signalStrength, view]);

  const selectedLead = leads.find((lead) => lead.id === selectedLeadId) || null;
  const selectedWorkstream = selectedLead?.workstreams?.find((item) => item.id === selectedWorkstreamId)
    || selectedLead?.workstreams?.[0]
    || null;
  const selectedSenderScope = selectedWorkstream?.workstream_type === 'localos_sales'
    || senderMode === 'localos_for_partner'
    ? 'platform'
    : 'business';
  const selectedSenderLabel = selectedWorkstream?.workstream_type === 'localos_sales'
    ? 'LocalOS'
    : senderMode === 'localos_for_partner'
      ? `LocalOS представляет ${selectedWorkstream?.client_business_name || 'бизнес партнёра'}`
      : selectedWorkstream?.client_business_name || 'Выбранный клиент';
  const drawerContacts = (contactIntelligence?.contacts || selectedWorkstream?.contact_points || [])
    .filter((item) => item.type !== 'website');
  const drawerTelegramSources = contactIntelligence?.telegram_sources || [];
  const drawerRecipient = contactIntelligence?.selected_recipient || selectedWorkstream?.selected_recipient || null;
  const drawerReadiness = contactIntelligence?.job?.message_readiness || selectedWorkstream?.message_readiness || {};
  const drawerFirstMessage = contactIntelligence?.first_message || null;
  const drawerMessageCurrent = Boolean(drawerFirstMessage?.generation_current);
  const readinessIssues = (() => {
    const explicitIssues = (drawerReadiness.missing_items || []).length
      ? (drawerReadiness.missing_items || []).map((item) => ({
          code: String(item.code || 'research_evidence'),
          label: String(item.label || 'Добавьте подтверждённые данные'),
        }))
      : (drawerReadiness.missing || []).map((label) => ({
          code: readinessCodeFromLegacyLabel(label),
          label,
        }));
    const profileIssues = (contactIntelligence?.sender_profile_completeness?.missing_items || []).map((item) => ({
      code: String(item.code || 'sender_profile'),
      label: String(item.label || 'Дополните профиль отправителя'),
    }));
    const combinedIssues = [...explicitIssues, ...profileIssues].filter((item, index, items) => (
      items.findIndex((candidate) => candidate.code === item.code) === index
    ));
    if (combinedIssues.length || drawerFirstMessage?.generated_text) return combinedIssues;
    const inferredIssues: Array<{ code: string; label: string }> = [];
    if (!drawerRecipient) {
      inferredIssues.push({ code: 'recipient_contact', label: 'Выберите подходящий контакт' });
    }
    if (!contactIntelligence?.sender_profile?.confirmed_at) {
      inferredIssues.push({ code: 'sender_profile', label: 'Добавьте факты об отправителе' });
    }
    if (
      selectedWorkstream?.workstream_type === 'client_partnership'
      && selectedWorkstream.service_compatibility_score == null
      && !selectedWorkstream.research?.why_now
    ) {
      inferredIssues.push({
        code: 'partner_compatibility',
        label: 'Подтвердите, чем бизнес отправителя и потенциальный партнёр полезны друг другу',
      });
    }
    return inferredIssues;
  })();
  const readyChannelCount = Object.values(outreachPreview?.channel_availability || {})
    .filter((item) => item.status === 'ready').length;
  const senderProfileChecklist = contactIntelligence?.sender_profile_completeness;
  const latestCampaignFirstTouch = (savedOutreachCampaign?.touches || [])
    .find((touch) => Number(touch.sequence_index || 0) === 0);
  const savedCampaignNeedsChannelSetup = (savedOutreachCampaign?.touches || []).some((touch) => {
    const channel = String(touch.channel || '');
    const channelStatus = String(touch.message_brief_json?.channel_status || '');
    return ['telegram', 'email'].includes(channel)
      ? !touch.sender_account_id || channelStatus !== 'ready'
      : channelStatus !== 'manual';
  });
  const pilotAlreadySent = (savedOutreachCampaign?.touches || []).some((touch) => (
    ['manual_sent', 'sent', 'delivered'].includes(String(touch.status || ''))
  ));
  const pilotReplyReceived = savedOutreachCampaign?.stop_reason === 'recipient_replied';
  const canDispatchPilot = Boolean(
    savedOutreachCampaign?.status === 'approved'
    && savedOutreachCampaign?.generation_current
    && latestCampaignFirstTouch
    && ['telegram', 'email'].includes(String(latestCampaignFirstTouch.channel || ''))
    && !pilotAlreadySent
    && pilotReadiness?.can_dispatch_first_touch,
  );
  const canSyncPilotReply = Boolean(
    latestCampaignFirstTouch
    && ['telegram', 'email'].includes(String(latestCampaignFirstTouch.channel || ''))
    && pilotAlreadySent
    && !pilotReplyReceived,
  );

  useEffect(() => {
    if (!selectedLead) return;
    if (selectedWorkstreamId && selectedLead.workstreams?.some((item) => item.id === selectedWorkstreamId)) return;
    setSelectedWorkstreamId(selectedLead.workstreams?.[0]?.id || null);
  }, [selectedLead, selectedWorkstreamId]);

  useEffect(() => {
    setPilotReadiness(null);
  }, [selectedLeadId, selectedWorkstreamId]);

  useEffect(() => {
    if (!selectedLead?.id || !selectedWorkstream?.id) {
      setContactIntelligence(null);
      return undefined;
    }
    let active = true;
    let timer = 0;
    const load = async (showLoading: boolean) => {
      if (showLoading) setContactIntelligenceLoading(true);
      try {
        const payload = await newAuth.makeRequest(
          `/admin/prospecting/leads/${selectedLead.id}/contact-intelligence?workstream_id=${encodeURIComponent(selectedWorkstream.id || '')}`,
        );
        if (!active) return;
        setContactIntelligence(payload);
        const status = String(payload?.job?.status || '');
        if (['queued', 'collecting', 'verifying', 'researching', 'drafting', 'retry_wait'].includes(status)) {
          timer = window.setTimeout(() => load(false), 2500);
        }
      } catch (requestError) {
        if (active) setNotice(requestError instanceof Error ? requestError.message : 'Не удалось загрузить контакты');
      } finally {
        if (active && showLoading) setContactIntelligenceLoading(false);
      }
    };
    load(true);
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [selectedLead?.id, selectedWorkstream?.id, contactIntelligence?.job?.id]);

  useEffect(() => {
    const profile = contactIntelligence?.sender_profile;
    const suggestions = contactIntelligence?.sender_profile_suggestions;
    if (profile) {
      const context = profile.outreach_context_json || {};
      setSenderName(String(profile.display_name || ''));
      setSenderRole(String(profile.role_title || ''));
      setSenderCompany(String(profile.company_name || ''));
      setSenderStory(String(profile.competence_story || ''));
      setSenderProof((profile.proof_points_json || []).map((item) => typeof item === 'string' ? item : String(item.fact || '')).filter(Boolean).join('\n'));
      setSenderOffer((profile.allowed_offers_json || []).join('\n'));
      setSenderForbidden((profile.forbidden_claims_json || []).join('\n'));
      setSenderVoiceExample((profile.voice_examples_json || []).join('\n'));
      setSenderOutcome(String(context.product_outcome || ''));
      setSenderAudience(String(context.audience || ''));
      setSenderSegments((context.segments || []).join('\n'));
      setSenderGeography(String(context.geography || ''));
      setSenderRecipientRoles((context.recipient_roles || []).join('\n'));
      setSenderPartnerTypes((context.desired_partner_types || []).join('\n'));
      setSenderDisqualifiers((context.disqualifiers || []).join('\n'));
      setSenderCtas((context.allowed_ctas || []).join('\n'));
      return;
    }
    setSenderName(String(suggestions?.display_name || ''));
    setSenderRole('');
    setSenderCompany(selectedWorkstream?.workstream_type === 'localos_sales'
      ? 'LocalOS'
      : String(suggestions?.company_name || selectedWorkstream?.client_business_name || ''));
    setSenderStory('');
    setSenderProof('');
    setSenderOffer('');
    setSenderForbidden('');
    setSenderVoiceExample('');
    setSenderOutcome('');
    setSenderAudience('');
    setSenderSegments('');
    setSenderGeography(String(suggestions?.geography || ''));
    setSenderRecipientRoles('');
    setSenderPartnerTypes((suggestions?.desired_partner_types || []).join('\n'));
    setSenderDisqualifiers('');
    setSenderCtas('');
  }, [contactIntelligence?.sender_profile?.id, contactIntelligence?.sender_profile_suggestions, selectedWorkstream?.id]);

  useEffect(() => {
    setOutreachPreview(null);
    setSavedOutreachCampaign(null);
    setPilotReadiness(null);
    setSenderFactsOpen(false);
    setSequenceChannels(['telegram', 'email', 'max', 'vk']);
    setSequenceDays([0, 3, 7, 12]);
    setSequenceSenders({});
    setSenderMode(
      selectedWorkstream?.workstream_type === 'localos_sales'
        ? 'localos'
        : 'partner_business',
    );
  }, [selectedWorkstream?.id]);

  useEffect(() => {
    const workstreamId = String(selectedWorkstream?.id || '');
    if (!workstreamId) return undefined;
    let active = true;
    const loadCampaign = async () => {
      try {
        const payload = await newAuth.makeRequest(`/outreach/workstreams/${encodeURIComponent(workstreamId)}/campaigns`);
        if (!active) return;
        const campaigns = Array.isArray(payload?.campaigns) ? payload.campaigns : [];
        const latestCampaign = campaigns[0] || null;
        setSavedOutreachCampaign(latestCampaign);
        const savedMode = latestCampaign?.policy_json?.sender_mode;
        if (
          savedMode === 'localos'
          || savedMode === 'partner_business'
          || savedMode === 'localos_for_partner'
        ) {
          setSenderMode(savedMode);
        }
      } catch (requestError) {
        if (active) setNotice(requestError instanceof Error ? requestError.message : 'Не удалось загрузить кампанию');
      }
    };
    void loadCampaign();
    return () => {
      active = false;
    };
  }, [selectedWorkstream?.id]);

  const runAction = async (key: string, requestFactory: () => Promise<unknown>, successMessage: string) => {
    setBusyAction(key);
    setNotice('');
    try {
      await requestFactory();
      setNotice(successMessage);
      await loadLeads();
    } catch (requestError) {
      setNotice(requestError instanceof Error ? requestError.message : 'Действие не выполнено');
    } finally {
      setBusyAction('');
    }
  };

  const addLocalosWorkstream = () => {
    if (!selectedLead) return;
    runAction(
      'add-localos',
      () => newAuth.makeRequest(`/admin/prospecting/lead/${selectedLead.id}/workstreams`, {
        method: 'POST',
        body: JSON.stringify({ workstream_type: 'localos_sales' }),
      }),
      'Компания добавлена в продажи LocalOS. Партнёрский контур не изменён.',
    );
  };

  const startContactIntelligence = async () => {
    if (!selectedLead || !selectedWorkstream?.id) return;
    setBusyAction('contact-intelligence');
    setNotice('');
    try {
      const payload = await newAuth.makeRequest(`/admin/prospecting/leads/${selectedLead.id}/contact-intelligence`, {
        method: 'POST',
        body: JSON.stringify({
          workstream_id: selectedWorkstream.id,
          force: true,
          allow_paid_enrichment: ['qualified', 'converted', 'selected_for_outreach'].includes(
            String(selectedWorkstream.status || selectedLead.status || selectedLead.pipeline_status || ''),
          ),
        }),
      });
      setContactIntelligence((current) => ({ ...current, job: payload?.job || current?.job || null }));
      setNotice('Проверка запущена. Можно закрыть карточку: работа продолжится в фоне.');
      await loadLeads();
    } catch (requestError) {
      setNotice(requestError instanceof Error ? requestError.message : 'Не удалось запустить проверку');
    } finally {
      setBusyAction('');
    }
  };

  const selectRecipient = async (contact: ContactPoint) => {
    if (!selectedLead || !selectedWorkstream?.id) return;
    setBusyAction(`recipient-${contact.id}`);
    setNotice('');
    try {
      await newAuth.makeRequest(`/admin/prospecting/leads/${selectedLead.id}/recipient`, {
        method: 'POST',
        body: JSON.stringify({
          workstream_id: selectedWorkstream.id,
          contact_point_id: contact.id,
        }),
      });
      const channel = ['email', 'telegram', 'whatsapp'].includes(String(contact.type || ''))
        ? String(contact.type)
        : 'manual';
      await newAuth.makeRequest(`/admin/prospecting/lead/${selectedLead.id}/channel`, {
        method: 'POST',
        body: JSON.stringify({ channel, workstream_id: selectedWorkstream.id }),
      });
      setNotice('Получатель выбран. Письмо будет заново проверено для этого контакта.');
      await loadLeads();
    } catch (requestError) {
      setNotice(requestError instanceof Error ? requestError.message : 'Не удалось выбрать получателя');
    } finally {
      setBusyAction('');
    }
  };

  const saveSenderProfile = async () => {
    if (!selectedWorkstream?.id) return;
    setBusyAction('sender-profile');
    setNotice('');
    try {
      const payload = await newAuth.makeRequest('/admin/prospecting/sender-profiles', {
        method: 'POST',
        body: JSON.stringify({
          workstream_type: selectedWorkstream.workstream_type,
          client_business_id: selectedWorkstream.client_business_id,
          display_name: senderName,
          role_title: senderRole,
          company_name: senderCompany,
          competence_story: senderStory,
          proof_points: senderProof.split('\n').map((fact) => fact.trim()).filter(Boolean).map((fact) => ({ fact, status: 'approved' })),
          allowed_offers: senderOffer.split('\n').map((item) => item.trim()).filter(Boolean),
          forbidden_claims: senderForbidden.split('\n').map((item) => item.trim()).filter(Boolean),
          voice_examples: senderVoiceExample.split('\n').map((item) => item.trim()).filter(Boolean),
          outreach_context: {
            product_outcome: senderOutcome.trim(),
            audience: senderAudience.trim(),
            segments: senderSegments.split('\n').map((item) => item.trim()).filter(Boolean),
            geography: senderGeography.trim(),
            recipient_roles: senderRecipientRoles.split('\n').map((item) => item.trim()).filter(Boolean),
            desired_partner_types: senderPartnerTypes.split('\n').map((item) => item.trim()).filter(Boolean),
            disqualifiers: senderDisqualifiers.split('\n').map((item) => item.trim()).filter(Boolean),
            allowed_ctas: senderCtas.split('\n').map((item) => item.trim()).filter(Boolean),
          },
          confirmed: true,
        }),
      });
      const savedProfile = payload?.profile || null;
      const completeness = payload?.profile_completeness || savedProfile?.profile_completeness || {};
      setContactIntelligence((current) => current ? {
        ...current,
        sender_profile: savedProfile,
        sender_profile_completeness: completeness,
      } : current);
      if (savedProfile?.confirmed_at) {
        setNotice('Профиль отправителя подтверждён. Перезапускаем проверку письма.');
        await startContactIntelligence();
      } else {
        const missing = Array.isArray(completeness?.missing_items)
          ? completeness.missing_items.map((item: { label?: string }) => String(item.label || '')).filter(Boolean)
          : [];
        setNotice(`Черновик профиля сохранён.${missing.length ? ` Осталось: ${missing.join('; ')}.` : ''}`);
      }
    } catch (requestError) {
      setNotice(requestError instanceof Error ? requestError.message : 'Не удалось сохранить отправителя');
    } finally {
      setBusyAction('');
    }
  };

  const scrollToDrawerSection = (elementId: string) => {
    window.requestAnimationFrame(() => {
      document.getElementById(elementId)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  };

  const openSenderFacts = () => {
    setSenderFactsOpen(true);
    scrollToDrawerSection('sender-facts');
  };

  const openRecipientContacts = () => {
    scrollToDrawerSection('lead-contacts-title');
  };

  const openSuppressionList = () => {
    scrollToDrawerSection('lead-suppression-list');
  };

  const openPartnershipMatching = () => {
    if (!selectedLead?.id || !selectedWorkstream?.client_business_id) return;
    window.localStorage.setItem('admin_selected_business_id', selectedWorkstream.client_business_id);
    const params = new URLSearchParams({
      lead: selectedLead.id,
      focus: 'match',
    });
    window.location.assign(`/dashboard/partnerships?${params.toString()}`);
  };

  const updateSequenceChannel = (index: number, channel: string) => {
    setSequenceChannels((current) => current.map((item, itemIndex) => itemIndex === index ? channel : item));
    setSequenceSenders((current) => ({ ...current, [index]: '' }));
    setOutreachPreview(null);
    setSavedOutreachCampaign(null);
    setPilotReadiness(null);
  };

  const updateSequenceDay = (index: number, day: number) => {
    setSequenceDays((current) => current.map((item, itemIndex) => itemIndex === index ? Math.max(0, day) : item));
    setOutreachPreview(null);
    setSavedOutreachCampaign(null);
    setPilotReadiness(null);
  };

  const updateSenderMode = (mode: SenderMode) => {
    setSenderMode(mode);
    setSequenceSenders({});
    setOutreachPreview(null);
    setSavedOutreachCampaign(null);
    setPilotReadiness(null);
    setNotice('Способ представления изменён. Подготовьте новый preview и проверьте всю цепочку.');
  };

  const campaignSequence = () => [
    { channel: sequenceChannels[0], day_offset: sequenceDays[0], angle: 'signal', sender_account_id: sequenceSenders[0] || undefined },
    { channel: sequenceChannels[1], day_offset: sequenceDays[1], angle: 'founder_story', sender_account_id: sequenceSenders[1] || undefined },
    { channel: sequenceChannels[2], day_offset: sequenceDays[2], angle: 'proof', sender_account_id: sequenceSenders[2] || undefined },
    { channel: sequenceChannels[3], day_offset: sequenceDays[3], angle: 'respectful_close', sender_account_id: sequenceSenders[3] || undefined },
  ];

  const reloadLatestOutreachCampaign = async () => {
    const workstreamId = String(selectedWorkstream?.id || '');
    if (!workstreamId) return;
    const payload = await newAuth.makeRequest(`/outreach/workstreams/${encodeURIComponent(workstreamId)}/campaigns`);
    const campaigns = Array.isArray(payload?.campaigns) ? payload.campaigns : [];
    setSavedOutreachCampaign(campaigns[0] || null);
  };

  const prepareOutreachCampaign = async (save: boolean) => {
    if (!selectedWorkstream?.id) return;
    setPilotReadiness(null);
    setBusyAction(save ? 'save-campaign' : 'preview-campaign');
    setNotice('');
    try {
      const payload = await newAuth.makeRequest(`/outreach/workstreams/${encodeURIComponent(selectedWorkstream.id)}/preview`, {
        method: 'POST',
        body: JSON.stringify({ sequence: campaignSequence(), save, sender_mode: senderMode }),
      });
      setOutreachPreview(payload?.preview || null);
      if (payload?.campaign) {
        setSavedOutreachCampaign(payload.campaign);
        setNotice(`Версия ${payload.campaign.version} сохранена как черновик. Проверьте всю цепочку перед approval.`);
        await reloadLatestOutreachCampaign();
      }
    } catch (requestError) {
      setNotice(requestError instanceof Error ? requestError.message : 'Не удалось подготовить цепочку');
    } finally {
      setBusyAction('');
    }
  };

  const approveOutreachCampaign = async () => {
    if (!savedOutreachCampaign?.id) return;
    setPilotReadiness(null);
    setBusyAction('approve-campaign');
    setNotice('');
    try {
      const payload = await newAuth.makeRequest(`/outreach/campaigns/${encodeURIComponent(savedOutreachCampaign.id)}/approve`, { method: 'POST' });
      setSavedOutreachCampaign((current) => current ? { ...current, status: payload?.campaign?.status || 'approved' } : current);
      setNotice('Вся цепочка подтверждена. Для пилота отправьте только первое касание; остальные не запустятся скрытно.');
      await reloadLatestOutreachCampaign();
    } catch (requestError) {
      setNotice(requestError instanceof Error ? requestError.message : 'Цепочка не прошла preflight');
    } finally {
      setBusyAction('');
    }
  };

  const runPilotPreflight = async () => {
    if (!savedOutreachCampaign?.id) return;
    setBusyAction('pilot-preflight');
    setNotice('');
    try {
      const payload = await newAuth.makeRequest(`/outreach/campaigns/${encodeURIComponent(savedOutreachCampaign.id)}/pilot-preflight`, {
        method: 'POST',
      });
      const readiness: PilotReadiness = payload?.pilot_readiness || {};
      setPilotReadiness(readiness);
      if (readiness.can_dispatch_first_touch) {
        setNotice('Проверка пройдена. LocalOS готов отправить только первое касание после вашего отдельного подтверждения.');
      }
    } catch (requestError) {
      setPilotReadiness(null);
      setNotice(requestError instanceof Error ? requestError.message : 'Не удалось проверить готовность к пилоту');
    } finally {
      setBusyAction('');
    }
  };

  const dispatchPilotFirstTouch = async () => {
    if (!savedOutreachCampaign?.id) return;
    const confirmed = window.confirm(
      'Отправить только первое касание этой кампании реальному получателю? LocalOS ещё раз проверит ответы, разрешения, tenant scope, stop-list и лимиты.',
    );
    if (!confirmed) return;
    setBusyAction('pilot-dispatch');
    setNotice('');
    try {
      const payload = await newAuth.makeRequest(`/outreach/campaigns/${encodeURIComponent(savedOutreachCampaign.id)}/pilot-dispatch-first-touch`, {
        method: 'POST',
        body: JSON.stringify({ confirm_campaign_id: savedOutreachCampaign.id }),
      });
      setNotice(Number(payload?.messages_sent || 0) === 1
        ? 'Первое пилотное касание отправлено. Остальные каналы не запускались.'
        : 'Первое касание не отправлено: safety-preflight остановил операцию.');
      await reloadLatestOutreachCampaign();
    } catch (requestError) {
      setNotice(requestError instanceof Error ? requestError.message : 'Пилотное касание не отправлено');
    } finally {
      setBusyAction('');
    }
  };

  const syncPilotReply = async () => {
    if (!savedOutreachCampaign?.id) return;
    setBusyAction('pilot-reply-sync');
    setNotice('');
    try {
      const payload = await newAuth.makeRequest(`/outreach/campaigns/${encodeURIComponent(savedOutreachCampaign.id)}/pilot-reply-sync`, { method: 'POST' });
      setNotice(payload?.reply_received
        ? `Ответ получен${payload?.classification ? ` и классифицирован: ${payload.classification}` : ''}. Все следующие касания остановлены.`
        : 'Нового ответа пока нет. Проверка не отправляла сообщений.');
      await reloadLatestOutreachCampaign();
    } catch (requestError) {
      setNotice(requestError instanceof Error ? requestError.message : 'Не удалось проверить ответ');
    } finally {
      setBusyAction('');
    }
  };

  const prepareRoom = () => {
    if (!selectedLead || !selectedWorkstream?.id) return;
    const isPartner = selectedWorkstream.workstream_type === 'client_partnership';
    const endpoint = isPartner
      ? `/partnership/leads/${selectedLead.id}/prepare-room`
      : `/admin/prospecting/lead/${selectedLead.id}/prepare-room`;
    runAction(
      'prepare-room',
      () => newAuth.makeRequest(endpoint, {
        method: 'POST',
        body: JSON.stringify({
          business_id: selectedWorkstream.client_business_id,
          workstream_id: selectedWorkstream.id,
          data_mode: 'template',
          channel: selectedWorkstream.selected_channel || 'manual',
          reuse_existing: true,
        }),
      }),
      'Цифровая комната готова. Проверьте предложение перед отправкой.',
    );
  };

  const markSent = () => {
    if (!selectedLead || !selectedWorkstream?.id) return;
    const isPartner = selectedWorkstream.workstream_type === 'client_partnership';
    const endpoint = isPartner
      ? `/partnership/leads/${selectedLead.id}/manual-contact`
      : `/admin/prospecting/lead/${selectedLead.id}/manual-contact`;
    runAction(
      'mark-sent',
      () => newAuth.makeRequest(endpoint, {
        method: 'POST',
        body: JSON.stringify({
          business_id: selectedWorkstream.client_business_id,
          workstream_id: selectedWorkstream.id,
          channel: selectedWorkstream.selected_channel || 'manual',
          comment: 'Отправлено вручную после проверки',
        }),
      }),
      'Отправка отмечена. Следующий шаг — зафиксировать ответ.',
    );
  };

  const startSearch = async () => {
    if (!searchCategory.trim() || !searchLocation.trim()) {
      setSearchError('Укажите категорию и территорию поиска.');
      return;
    }
    if (searchScope === 'client_partnership' && !searchClientId) {
      setSearchError('Выберите клиента, для которого ищем партнёров.');
      return;
    }
    setSearchBusy(true);
    setSearchError('');
    try {
      const created = await newAuth.makeRequest('/admin/prospecting/search', {
        method: 'POST',
        body: JSON.stringify({
          query: searchCategory.trim(),
          location: searchLocation.trim(),
          source: searchSource,
          limit: 30,
          workstream_type: searchScope,
          client_business_id: searchClientId || null,
          radius_meters: Number(searchRadius),
        }),
      });
      const jobId = String(created?.job_id || '');
      if (!jobId) throw new Error('Поиск не запустился');
      let completedResults: SearchResult[] = [];
      for (let attempt = 0; attempt < 45; attempt += 1) {
        await wait(1500);
        const response = await newAuth.makeRequest(`/admin/prospecting/search-job/${jobId}`);
        if (response?.job?.status === 'completed') {
          completedResults = Array.isArray(response.job.results) ? response.job.results : [];
          break;
        }
        if (response?.job?.status === 'failed') {
          throw new Error(response.job.error_text || 'Поиск завершился с ошибкой');
        }
      }
      setSearchResults(completedResults);
      setSelectedSearchIds([]);
      setSearchStep(3);
      if (!completedResults.length) setSearchError('Компании не найдены. Попробуйте изменить категорию или территорию.');
    } catch (requestError) {
      setSearchError(requestError instanceof Error ? requestError.message : 'Не удалось выполнить поиск');
    } finally {
      setSearchBusy(false);
    }
  };

  const saveSearchResults = async () => {
    const selected = searchResults.filter((item) => selectedSearchIds.includes(item.id || item.google_id || item.name || ''));
    if (!selected.length) {
      setSearchError('Выберите хотя бы одну компанию.');
      return;
    }
    setSearchBusy(true);
    setSearchError('');
    try {
      for (const lead of selected) {
        await newAuth.makeRequest('/admin/prospecting/save', {
          method: 'POST',
          body: JSON.stringify({
            lead,
            workstream_type: searchScope,
            client_business_id: searchScope === 'client_partnership' ? searchClientId : null,
          }),
        });
      }
      setSearchOpen(false);
      setSearchStep(1);
      setSearchResults([]);
      setNotice(`Добавлено в работу: ${selected.length}. Уже известные компании получили новый контур без дубля.`);
      await loadLeads();
    } catch (requestError) {
      setSearchError(requestError instanceof Error ? requestError.message : 'Не удалось добавить компании');
    } finally {
      setSearchBusy(false);
    }
  };

  const selectedClient = businessOptions.find((item) => item.id === searchClientId);

  useEffect(() => {
    if (searchScope !== 'client_partnership' || !selectedClient?.address || searchLocation.trim()) return;
    setSearchLocation(selectedClient.address);
  }, [searchScope, selectedClient, searchLocation]);

  return (
    <div className="min-h-[620px] bg-white">
      <div className="border-b border-slate-200 px-4 py-4 sm:px-6">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
          <div className="flex min-w-0 items-center gap-2 overflow-x-auto pb-1 xl:pb-0">
            {viewOptions.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => setView(item.id)}
                className={`min-h-10 whitespace-nowrap rounded-md px-4 text-sm font-semibold transition-colors active:scale-[0.96] ${
                  view === item.id ? 'bg-slate-950 text-white' : 'text-slate-600 hover:bg-slate-100 hover:text-slate-950'
                }`}
              >
                {item.label}
              </button>
            ))}
          </div>
          <Button onClick={() => setSearchOpen(true)} className="min-h-11 bg-orange-500 text-white hover:bg-orange-600">
            <Search className="mr-2 h-4 w-4" />
            Найти лидов
          </Button>
        </div>

        <div className="mt-4 grid grid-cols-[minmax(0,1fr)] gap-3 lg:grid-cols-[minmax(240px,1fr)_auto_minmax(170px,220px)_minmax(180px,240px)_minmax(180px,240px)]">
          <div className="relative min-w-0">
            <Search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-slate-400" />
            <Input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Компания, категория, город или контакт"
              className="h-10 pl-9"
            />
          </div>
          <div className="flex min-w-0 gap-1 overflow-x-auto rounded-md bg-slate-100 p-1">
            {scopeOptions.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => setScope(item.id)}
                className={`min-h-8 whitespace-nowrap rounded px-3 text-xs font-semibold transition-colors ${
                  scope === item.id ? 'bg-white text-slate-950 shadow-sm' : 'text-slate-600 hover:text-slate-950'
                }`}
              >
                {item.label}
              </button>
            ))}
          </div>
          <select
            value={clientBusinessId}
            onChange={(event) => setClientBusinessId(event.target.value)}
            className="h-10 min-w-0 w-full rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-800"
            aria-label="Фильтр по клиенту"
          >
            <option value="">Все клиенты</option>
            {clientFilterOptions.map((business) => <option key={business.id} value={business.id}>{business.name}</option>)}
          </select>
          <select
            value={signalStrength}
            onChange={(event) => setSignalStrength(event.target.value)}
            className="h-10 min-w-0 w-full rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-800"
            aria-label="Фильтр по силе сигнала"
          >
            <option value="">Любой сигнал</option>
            <option value="strong_signal">Сильный сигнал</option>
            <option value="reason_to_check">Есть повод</option>
            <option value="fit_only">Только соответствие</option>
          </select>
          <select
            value={actionState}
            onChange={(event) => setActionState(event.target.value)}
            className="h-10 min-w-0 w-full rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-800"
            aria-label="Фильтр по следующему действию"
          >
            <option value="">Любое действие</option>
            <option value="find_contact">Найти контакт</option>
            <option value="prepare_room">Подготовить комнату</option>
            <option value="review_message">Проверить сообщение</option>
            <option value="wait_or_follow_up">Проверить ответ</option>
            <option value="record_result">Зафиксировать результат</option>
          </select>
        </div>
      </div>

      {notice && (
        <div className="mx-4 mt-4 flex items-start gap-2 rounded-md bg-emerald-50 px-4 py-3 text-sm text-emerald-800 sm:mx-6">
          <Check className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{notice}</span>
        </div>
      )}

      <div className="px-4 py-3 sm:px-6">
        {view === 'results' ? (
          <div className="pb-5">
            <OutreachLearningInsights
              workstreamType={scope === 'client_partnership' ? 'client_partnership' : 'localos_sales'}
              businessId={scope === 'client_partnership' ? clientBusinessId : null}
            />
          </div>
        ) : null}
        <div className="flex items-center justify-between gap-3 pb-3 text-sm text-slate-500">
          <span className="tabular-nums">{loading ? 'Загружаем…' : `${filteredLeads.length} компаний`}</span>
          <button type="button" onClick={loadLeads} className="flex min-h-10 items-center gap-2 px-2 font-medium hover:text-slate-950">
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            Обновить
          </button>
        </div>

        {error ? (
          <div className="flex min-h-40 flex-col items-center justify-center gap-3 text-center">
            <CircleAlert className="h-7 w-7 text-amber-500" />
            <p className="max-w-md text-sm text-slate-600">{error}</p>
            <Button variant="outline" onClick={loadLeads}>Повторить</Button>
          </div>
        ) : !loading && !filteredLeads.length ? (
          <div className="flex min-h-52 flex-col items-center justify-center gap-3 text-center">
            <Users className="h-8 w-8 text-slate-300" />
            <div>
              <h3 className="font-semibold text-slate-950">В этом списке пока нет компаний</h3>
              <p className="mt-1 max-w-md text-sm text-slate-500">Найдите новые компании или измените фильтры.</p>
            </div>
            <Button onClick={() => setSearchOpen(true)} className="bg-orange-500 text-white hover:bg-orange-600">Найти лидов</Button>
          </div>
        ) : (
          <div className="divide-y divide-slate-200">
            {filteredLeads.map((lead) => {
              const workstreams = lead.workstreams || [];
              const primary = workstreams[0];
              const contacts = availableContacts(lead);
              const contactSummary = primary?.contact_summary;
              const recipient = primary?.selected_recipient;
              const research = strongestResearch(workstreams);
              return (
                <button
                  key={lead.id}
                  type="button"
                  onClick={() => {
                    setSelectedLeadId(lead.id);
                    setSelectedWorkstreamId(primary?.id || null);
                    setNotice('');
                  }}
                  className="grid w-full gap-3 py-4 text-left transition-colors hover:bg-slate-50 active:scale-[0.996] md:grid-cols-[minmax(240px,1.4fr)_minmax(210px,1fr)_minmax(180px,.8fr)_minmax(180px,.8fr)_40px] md:items-center md:px-2"
                >
                  <div className="min-w-0">
                    <div className="truncate font-semibold text-slate-950">{lead.name || 'Компания без названия'}</div>
                    <div className="mt-1 flex min-w-0 items-center gap-1.5 text-xs text-slate-500">
                      <MapPin className="h-3.5 w-3.5 shrink-0" />
                      <span className="truncate">{[lead.category, lead.city || lead.address].filter(Boolean).join(' · ') || 'Данные уточняются'}</span>
                    </div>
                  </div>
                  <div className="flex min-w-0 flex-wrap gap-1.5">
                    {workstreams.map((workstream) => (
                      <Badge
                        key={workstream.id || `${workstream.workstream_type}-${workstream.client_business_id || 'localos'}`}
                        variant="outline"
                        className={workstream.workstream_type === 'localos_sales'
                          ? 'border-sky-200 bg-sky-50 text-sky-800'
                          : 'border-violet-200 bg-violet-50 text-violet-800'}
                      >
                        {workstreamLabel(workstream)}
                      </Badge>
                    ))}
                    {research && (
                      <Badge variant="outline" className={signalTone(research)}>
                        {signalLabel(research)} · {Number(research.score || 0)}
                      </Badge>
                    )}
                  </div>
                  <div className="min-w-0 text-sm">
                    <div className="font-medium text-slate-800 tabular-nums">
                      {Number(contactSummary?.found || 0) > 0
                        ? `${Number(contactSummary?.found || 0)} каналов найдено · ${Number(contactSummary?.verified || 0)} проверено`
                        : contacts.length ? `${contacts.length} каналов найдено · нужна проверка` : 'Контакта пока нет'}
                    </div>
                    <div className="mt-1 truncate text-xs text-slate-500">
                      {recipient
                        ? `${recipient.person_name || 'Компания'}${recipient.role_title ? ` · ${recipient.role_title}` : ''}`
                        : enrichmentLabel(primary?.enrichment_state)}
                    </div>
                  </div>
                  <div className="min-w-0">
                    <div className="text-xs font-semibold uppercase tracking-[0.08em] text-slate-400">Следующий шаг</div>
                    <div className={`mt-1 truncate text-sm font-semibold ${actionTone(primary?.next_action?.code)}`}>
                      {primary?.next_action?.label || 'Открыть карточку'}
                    </div>
                  </div>
                  <ArrowRight className="hidden h-4 w-4 text-slate-400 md:block" />
                </button>
              );
            })}
          </div>
        )}
      </div>

      <details
        className="border-t border-slate-200 px-4 py-4 sm:px-6"
        onToggle={(event) => setAdvancedOpen(event.currentTarget.open)}
      >
        <summary className="flex min-h-10 cursor-pointer list-none items-center gap-2 text-sm font-semibold text-slate-700">
          <Filter className="h-4 w-4" />
          Дополнительные инструменты и аналитика
          <ChevronDown className="ml-auto h-4 w-4" />
        </summary>
        {advancedOpen && (
          <div className="mt-4 border-t border-slate-200 pt-4">
            <React.Suspense fallback={<div className="py-8 text-center text-sm text-slate-500">Загружаем дополнительные инструменты…</div>}>
              <LegacyProspectingManagement />
            </React.Suspense>
          </div>
        )}
      </details>

      <Sheet open={Boolean(selectedLead)} onOpenChange={(open) => { if (!open) setSelectedLeadId(null); }}>
        <SheetContent className="w-full overflow-y-auto sm:max-w-xl">
          <SheetHeader className="pr-8">
            <SheetTitle className="text-wrap-balance text-xl">{selectedLead?.name || 'Карточка лида'}</SheetTitle>
            <SheetDescription>{[selectedLead?.category, selectedLead?.city || selectedLead?.address].filter(Boolean).join(' · ')}</SheetDescription>
          </SheetHeader>

          {selectedLead && selectedWorkstream && (
            <div className="mt-6 space-y-6">
              {(selectedLead.workstreams || []).length > 1 && (
                <div>
                  <label className="text-xs font-semibold uppercase tracking-[0.1em] text-slate-500">Сейчас работаем как</label>
                  <div className="mt-2 grid gap-2 sm:grid-cols-2">
                    {(selectedLead.workstreams || []).map((workstream) => (
                      <button
                        key={workstream.id || workstream.workstream_type}
                        type="button"
                        onClick={() => setSelectedWorkstreamId(workstream.id || null)}
                        className={`min-h-12 rounded-md px-3 text-left text-sm font-semibold transition-colors ${
                          selectedWorkstream.id === workstream.id
                            ? 'bg-slate-950 text-white'
                            : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                        }`}
                      >
                        {workstreamLabel(workstream)}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="outline" className="bg-slate-50">{workstreamLabel(selectedWorkstream)}</Badge>
                <Badge variant="outline" className="border-emerald-200 bg-emerald-50 text-emerald-800">{statusLabel(selectedWorkstream)}</Badge>
                {selectedWorkstream.research && (
                  <Badge variant="outline" className={signalTone(selectedWorkstream.research)}>
                    {signalLabel(selectedWorkstream.research)} · {Number(selectedWorkstream.research.score || 0)}
                  </Badge>
                )}
                {selectedWorkstream.workstream_type === 'client_partnership' && selectedWorkstream.service_compatibility_score != null && (
                  <Badge variant="outline" className="border-violet-200 bg-violet-50 text-violet-800">
                    Совместимость услуг · {Number(selectedWorkstream.service_compatibility_score)}
                  </Badge>
                )}
              </div>

              <div className="grid grid-cols-5 gap-1" aria-label="Этапы подготовки первого обращения">
                {['Контакты', 'Получатель', 'Почему сейчас', 'Письмо', 'Проверка'].map((label, index) => {
                  const completedSteps = [
                    drawerContacts.length > 0,
                    Boolean(drawerRecipient),
                    Boolean(selectedWorkstream.research?.why_now)
                      || (selectedWorkstream.workstream_type === 'client_partnership'
                        && selectedWorkstream.service_compatibility_score != null),
                    Boolean(drawerFirstMessage?.generated_text),
                    Boolean(drawerFirstMessage?.quality_gate_json?.passed && drawerMessageCurrent),
                  ];
                  const done = completedSteps[index];
                  return (
                    <div key={label} className="min-w-0 text-center">
                      <div className={`mx-auto flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold ${done ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-500'}`}>
                        {done ? <Check className="h-3.5 w-3.5" /> : index + 1}
                      </div>
                      <div className="mt-1 truncate text-[11px] font-medium text-slate-500">{label}</div>
                    </div>
                  );
                })}
              </div>

              <section className="rounded-md bg-slate-50 p-4" aria-labelledby="lead-contacts-title">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h3 id="lead-contacts-title" className="text-sm font-semibold text-slate-950">Контакты и получатель</h3>
                    <p className="mt-1 text-sm text-slate-600 tabular-nums">
                      {drawerContacts.length} найдено · {drawerContacts.filter((item) => ['verified', 'confirmed_source'].includes(String(item.verification_status || ''))).length} проверено
                    </p>
                  </div>
                  <Button
                    variant="outline"
                    onClick={startContactIntelligence}
                    disabled={busyAction === 'contact-intelligence' || ['queued', 'collecting', 'verifying', 'researching', 'drafting'].includes(String(contactIntelligence?.job?.status || selectedWorkstream.enrichment_state?.status || ''))}
                    className="min-h-10 bg-white"
                  >
                    {busyAction === 'contact-intelligence' || ['queued', 'collecting', 'verifying', 'researching', 'drafting'].includes(String(contactIntelligence?.job?.status || selectedWorkstream.enrichment_state?.status || ''))
                      ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                      : <Search className="mr-2 h-4 w-4" />}
                    {drawerContacts.length ? 'Проверить ещё раз' : 'Найти контакты'}
                  </Button>
                </div>
                <p className="mt-3 text-xs font-medium text-slate-500">
                  {contactIntelligenceLoading ? 'Загружаем контакты…' : enrichmentLabel(selectedWorkstream.enrichment_state || (contactIntelligence?.job ? {
                    id: contactIntelligence.job.id,
                    status: contactIntelligence.job.status,
                    phase: contactIntelligence.job.phase,
                    error: contactIntelligence.job.error,
                  } : null))}
                </p>
                <div className="mt-3 space-y-2">
                  {drawerContacts.map((contact) => {
                    const selected = drawerRecipient?.id === contact.id;
                    const invalid = contact.verification_status === 'invalid';
                    return (
                      <button
                        key={contact.id}
                        type="button"
                        onClick={() => selectRecipient(contact)}
                        disabled={invalid || busyAction === `recipient-${contact.id}`}
                        className={`flex min-h-14 w-full items-center gap-3 rounded-md px-3 text-left transition-colors active:scale-[0.96] ${selected ? 'bg-white shadow-sm ring-2 ring-emerald-200' : 'bg-white hover:bg-slate-100'} disabled:cursor-not-allowed disabled:opacity-50`}
                      >
                        <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-md ${selected ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-600'}`}>
                          {contact.owner_type === 'person' ? <UserRound className="h-4 w-4" /> : <MessageCircle className="h-4 w-4" />}
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className="flex min-w-0 items-center gap-2">
                            <span className="truncate text-sm font-semibold text-slate-950">{contact.person_name || contact.value || contactTypeLabels[String(contact.type || '')] || 'Контакт'}</span>
                            {selected && <span className="shrink-0 text-xs font-semibold text-emerald-700">Выбран</span>}
                          </span>
                          <span className="mt-0.5 block truncate text-xs text-slate-500">
                            {[contact.role_title, contactTypeLabels[String(contact.type || '')], contact.person_name ? contact.value : ''].filter(Boolean).join(' · ')}
                          </span>
                          <span className="mt-0.5 block truncate text-xs text-slate-500">
                            {verificationLabel(contact.verification_status)} · источник {contact.source_type === 'official_website' ? 'официальный сайт' : contact.source_type === 'hunter_public_sources' ? 'публичные источники Hunter' : 'карточка компании'}
                          </span>
                        </span>
                        {['verified', 'confirmed_source'].includes(String(contact.verification_status || '')) && <ShieldCheck className="h-4 w-4 shrink-0 text-emerald-600" />}
                      </button>
                    );
                  })}
                  {!contactIntelligenceLoading && !drawerContacts.length && (
                    <div className="rounded-md bg-white px-3 py-4 text-sm text-amber-700">
                      Контакты ещё не проверены. Запустите поиск: система просмотрит карточку, официальный сайт и публичные каналы.
                    </div>
                  )}
                </div>
                {drawerTelegramSources.length > 0 && (
                  <div className="mt-4 border-t border-slate-200 pt-4">
                    <div className="flex items-start gap-3">
                      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-sky-50 text-sky-700">
                        <RadioTower className="h-4 w-4" />
                      </span>
                      <div className="min-w-0">
                        <h4 className="text-balance text-sm font-semibold text-slate-950">Telegram-источники</h4>
                        <p className="mt-1 text-pretty text-xs leading-5 text-slate-600">
                          Это публичные каналы для поиска сигналов. LocalOS не использует их как чат получателя.
                        </p>
                      </div>
                    </div>
                    <div className="mt-3 space-y-2">
                      {drawerTelegramSources.map((source) => {
                        const confirmedChannel = source.reference_type === 'public_channel' && source.status === 'active';
                        const checking = ['queued', 'syncing'].includes(String(source.sync_status || ''));
                        const needsPermission = source.permission_reason === 'radar_permission_required';
                        const needsAccount = source.permission_reason === 'telegram_account_required';
                        const statusLabel = confirmedChannel
                          ? `Публичный канал · ${Number(source.documents_count || 0)} публикаций собрано`
                          : checking
                            ? 'Проверяем, что это публичный канал'
                            : needsPermission
                              ? 'Ссылка сохранена · разрешите Telegram-радар'
                              : needsAccount
                                ? 'Ссылка сохранена · подключите Telegram-радар'
                                : source.status === 'paused'
                                  ? 'Не является доступным публичным каналом'
                                  : 'Ссылка сохранена для проверки';
                        return (
                          <a
                            key={source.id}
                            href={source.url}
                            target="_blank"
                            rel="noreferrer"
                            className="flex min-h-12 items-center gap-3 rounded-md bg-white px-3 py-2 text-left shadow-sm shadow-slate-900/5 transition-[box-shadow] hover:shadow-md"
                          >
                            <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${confirmedChannel ? 'bg-emerald-500' : checking ? 'bg-sky-500' : 'bg-amber-400'}`} />
                            <span className="min-w-0 flex-1">
                              <span className="block truncate text-sm font-semibold text-slate-900">{source.title || source.url || 'Telegram'}</span>
                              <span className="mt-0.5 block text-pretty text-xs leading-5 text-slate-600 tabular-nums">{statusLabel}</span>
                            </span>
                            <ExternalLink className="h-4 w-4 shrink-0 text-slate-400" />
                          </a>
                        );
                      })}
                    </div>
                  </div>
                )}
              </section>

              {selectedWorkstream.research && (
                <section className="rounded-md bg-slate-50 p-4" aria-labelledby="lead-research-title">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <h3 id="lead-research-title" className="text-sm font-semibold text-slate-950">Почему сейчас</h3>
                      <p className="mt-1 text-sm leading-6 text-slate-700">
                        {selectedWorkstream.research.why_now || 'Публичный повод не подтверждён. Компания подходит только по общим признакам.'}
                      </p>
                    </div>
                    <span className="text-xs text-slate-500 tabular-nums">
                      {selectedWorkstream.research.researched_at
                        ? new Date(selectedWorkstream.research.researched_at).toLocaleDateString('ru-RU')
                        : 'дата не указана'}
                    </span>
                  </div>
                  {(selectedWorkstream.research.sources || []).length > 0 && (
                    <div className="mt-3 space-y-2">
                      {(selectedWorkstream.research.sources || []).slice(0, 3).map((source) => (
                        <a
                          key={`${source.url}-${source.title}`}
                          href={source.url}
                          target="_blank"
                          rel="noreferrer"
                          className="flex min-h-10 items-center justify-between gap-3 rounded-md bg-white px-3 text-sm font-medium text-slate-800 hover:text-orange-700"
                        >
                          <span className="min-w-0 truncate">{source.title || 'Открыть источник'}</span>
                          <ExternalLink className="h-4 w-4 shrink-0" />
                        </a>
                      ))}
                    </div>
                  )}
                  {selectedWorkstream.research.suggested_opener && (
                    <div className="mt-3 rounded-md bg-white p-3">
                      <div className="text-xs font-semibold uppercase tracking-[0.08em] text-slate-500">Первый абзац письма</div>
                      <p className="mt-1 text-sm leading-6 text-slate-700">{selectedWorkstream.research.suggested_opener}</p>
                      {selectedWorkstream.research.opener_source_url ? (
                        <a
                          href={selectedWorkstream.research.opener_source_url}
                          target="_blank"
                          rel="noreferrer"
                          className="mt-2 inline-flex min-h-9 items-center gap-2 text-xs font-semibold text-sky-700 hover:text-sky-900"
                        >
                          Источник вступления
                          <ExternalLink className="h-3.5 w-3.5" />
                        </a>
                      ) : (
                        <p className="mt-2 text-xs text-slate-500">Нейтральное вступление без персонального публичного сигнала.</p>
                      )}
                    </div>
                  )}
                  {(selectedWorkstream.research.limitations || []).length > 0 && (
                    <details className="mt-2">
                      <summary className="min-h-10 cursor-pointer py-2 text-sm font-semibold text-slate-600">Ограничения исследования</summary>
                      <ul className="space-y-1 text-sm text-slate-600">
                        {(selectedWorkstream.research.limitations || []).map((item) => <li key={item}>{item}</li>)}
                      </ul>
                    </details>
                  )}
                </section>
              )}

              <section className="rounded-md bg-slate-50 p-4" aria-labelledby="first-message-title">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h3 id="first-message-title" className="text-sm font-semibold text-slate-950">Первое письмо</h3>
                    <p className="mt-1 text-sm text-slate-600">
                      {drawerFirstMessage?.requires_regeneration
                        ? 'Факты сохранены, но текст нужно подготовить заново'
                        : drawerReadiness.label || 'Сначала проверим контакты и основания'}
                    </p>
                  </div>
                  <Badge variant="outline" className={drawerReadiness.code === 'ready' && drawerMessageCurrent
                    ? 'border-emerald-200 bg-emerald-50 text-emerald-800'
                    : 'border-amber-200 bg-amber-50 text-amber-800'}>
                    {drawerFirstMessage?.requires_regeneration
                      ? 'Нужно переписать'
                      : drawerReadiness.code === 'ready' && drawerMessageCurrent
                        ? 'Готово к проверке'
                        : drawerReadiness.label || 'Не готово'}
                  </Badge>
                </div>
                {drawerFirstMessage?.generated_text ? (
                  <>
                    {drawerFirstMessage.requires_regeneration ? (
                      <div className="mt-3 rounded-md bg-amber-50 p-3 text-pretty text-sm leading-6 text-amber-950">
                        <div className="font-semibold">Это письмо создано по старым правилам</div>
                        <p className="mt-1">LocalOS не позволит подтвердить его. Перегенерируйте текст: факты и выбранный контакт сохранятся, а письмо пройдёт текущую AI-проверку.</p>
                        <Button variant="outline" onClick={startContactIntelligence} disabled={busyAction === 'contact-intelligence'} className="mt-2 min-h-10 bg-white">
                          {busyAction === 'contact-intelligence' ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : <Sparkles className="mr-2 h-4 w-4" />}
                          Переписать по текущим правилам
                        </Button>
                      </div>
                    ) : null}
                    <div className="mt-3 whitespace-pre-wrap rounded-md bg-white p-4 text-sm leading-6 text-slate-800">
                      {drawerFirstMessage.edited_text || drawerFirstMessage.generated_text}
                    </div>
                    <div className="mt-3 grid gap-2 sm:grid-cols-2">
                      <div className="rounded-md bg-white p-3">
                        <div className="text-xs font-semibold uppercase tracking-[0.08em] text-slate-500">От чьего лица</div>
                        <div className="mt-1 text-sm font-medium text-slate-800">
                          {contactIntelligence?.sender_profile
                            ? `${contactIntelligence.sender_profile.display_name} · ${contactIntelligence.sender_profile.role_title}`
                            : selectedWorkstream.workstream_type === 'localos_sales' ? 'LocalOS' : selectedWorkstream.client_business_name}
                        </div>
                      </div>
                      <div className="rounded-md bg-white p-3">
                        <div className="text-xs font-semibold uppercase tracking-[0.08em] text-slate-500">Почему такой вопрос</div>
                        <div className="mt-1 text-sm font-medium text-slate-800">
                          {String(drawerFirstMessage.message_brief_json?.cta || 'Один простой следующий шаг без обязательств')}
                        </div>
                      </div>
                    </div>
                    <p className="mt-3 text-xs text-slate-500 tabular-nums">
                      {Number(drawerFirstMessage.quality_gate_json?.word_count || 0)} слов · ссылка на цифровую комнату не добавлена
                    </p>
                  </>
                ) : (
                  <div className="mt-3 rounded-lg bg-white p-4 shadow-sm shadow-slate-900/5">
                    <div className="font-semibold text-slate-900 text-wrap-balance">Для персонального письма не хватает данных</div>
                    <p className="mt-1 text-pretty text-sm leading-6 text-slate-600">
                      {drawerRecipient
                        ? 'Контакт уже выбран. Письмо появится после того, как будут подтверждены факты об отправителе и причина обратиться именно к этой компании.'
                        : 'Сначала выберите подходящий контакт, затем подтвердите факты об отправителе и причину обратиться именно к этой компании.'}
                    </p>
                    {readinessIssues.length > 0 ? (
                      <div className="mt-3 space-y-2">
                        {readinessIssues.map((issue, index) => {
                          const senderIssue = [
                            'sender_profile',
                            'sender_confirmation',
                            'sender_identity',
                            'sender_experience',
                            'sender_proof',
                            'sender_audience',
                            'sender_offer',
                            'sender_voice',
                            'sender_forbidden_claims',
                            'sender_services',
                            'desired_partner_types',
                          ].includes(issue.code);
                          const partnerIssue = ['partner_compatibility', 'partner_category'].includes(issue.code);
                          const contactIssue = ['recipient_contact', 'recipient_role'].includes(issue.code);
                          const suppressionIssue = issue.code === 'suppression';
                          const description = senderIssue
                            ? `Расскажите о ${selectedWorkstream.client_business_name || senderCompany || 'бизнесе отправителя'}: кто пишет, какой опыт подтверждён и что можно предложить партнёру.`
                            : partnerIssue
                              ? `Нужны услуги, аудитория и география обеих компаний, чтобы проверить реальную пользу и не придумать повод для партнёрства.`
                              : contactIssue
                                ? 'Выберите канал и человека или общий контакт компании, которому уместно адресовать первое сообщение.'
                                : suppressionIssue
                                  ? 'Сначала проверьте причину запрета. LocalOS не подготовит отправку, пока действует stop-list.'
                                  : 'Обновите исследование компании: LocalOS проверит карточку, сайт и доступные публичные источники.';
                          return (
                            <div key={`${issue.code}-${issue.label}`} className="rounded-md bg-slate-50 p-3">
                              <div className="flex gap-3">
                                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-amber-100 text-xs font-bold text-amber-800 tabular-nums">
                                  {index + 1}
                                </span>
                                <div className="min-w-0 flex-1">
                                  <div className="text-sm font-semibold text-slate-900">{issue.label}</div>
                                  <p className="mt-1 text-pretty text-xs leading-5 text-slate-600">{description}</p>
                                  {senderIssue ? (
                                    <Button variant="outline" onClick={openSenderFacts} className="mt-2 min-h-10 bg-white active:scale-[0.96] transition-transform">
                                      Заполнить факты об отправителе <ArrowRight className="ml-2 h-4 w-4" />
                                    </Button>
                                  ) : partnerIssue ? (
                                    <Button variant="outline" onClick={openPartnershipMatching} disabled={!selectedWorkstream.client_business_id} className="mt-2 min-h-10 bg-white active:scale-[0.96] transition-transform">
                                      Проверить совместимость <ArrowRight className="ml-2 h-4 w-4" />
                                    </Button>
                                  ) : contactIssue ? (
                                    <Button variant="outline" onClick={openRecipientContacts} className="mt-2 min-h-10 bg-white active:scale-[0.96] transition-transform">
                                      Перейти к контактам <ArrowRight className="ml-2 h-4 w-4" />
                                    </Button>
                                  ) : suppressionIssue ? (
                                    <Button variant="outline" onClick={openSuppressionList} className="mt-2 min-h-10 bg-white active:scale-[0.96] transition-transform">
                                      Открыть stop-list <ArrowRight className="ml-2 h-4 w-4" />
                                    </Button>
                                  ) : (
                                    <Button variant="outline" onClick={startContactIntelligence} disabled={busyAction === 'contact-intelligence'} className="mt-2 min-h-10 bg-white active:scale-[0.96] transition-transform">
                                      Обновить исследование <RefreshCw className={`ml-2 h-4 w-4 ${busyAction === 'contact-intelligence' ? 'animate-spin' : ''}`} />
                                    </Button>
                                  )}
                                </div>
                              </div>
                            </div>
                          );
                        })}
                        <p className="pt-1 text-xs leading-5 text-slate-500">
                          После каждого шага LocalOS повторно проверит данные и подготовит письмо только на подтверждённых фактах.
                        </p>
                      </div>
                    ) : (
                      <Button variant="outline" onClick={startContactIntelligence} disabled={busyAction === 'contact-intelligence'} className="mt-3 min-h-10 bg-white active:scale-[0.96] transition-transform">
                        Проверить данные компании
                      </Button>
                    )}
                  </div>
                )}
              </section>

              <section className="rounded-md bg-slate-50 p-4" aria-labelledby="outreach-sequence-title">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h3 id="outreach-sequence-title" className="text-sm font-semibold text-slate-950">Каналы и порядок</h3>
                    <p className="mt-1 text-sm leading-6 text-slate-600">Четыре разных угла: сигнал, опыт основателя, кейс и уважительное завершение. Любое изменение создаёт новую версию.</p>
                  </div>
                  <Badge variant="outline" className={savedOutreachCampaign?.requires_regeneration
                    ? 'border-amber-200 bg-amber-50 text-amber-800'
                    : savedOutreachCampaign?.status === 'approved'
                    ? 'border-emerald-200 bg-emerald-50 text-emerald-800'
                    : 'border-slate-200 bg-white text-slate-700'}>
                    {savedOutreachCampaign
                      ? `Версия ${savedOutreachCampaign.version} · ${savedOutreachCampaign.requires_regeneration ? 'нужно обновить' : savedOutreachCampaign.status === 'approved' ? 'подтверждена' : 'черновик'}`
                      : 'Не сохранена'}
                  </Badge>
                </div>

                {selectedWorkstream.workstream_type === 'client_partnership' ? (
                  <fieldset className="mt-3 rounded-md bg-white p-3">
                    <legend className="text-balance px-1 text-xs font-semibold uppercase tracking-[0.1em] text-slate-500">Кто обращается к партнёру</legend>
                    <div className="mt-2 grid gap-2 sm:grid-cols-2">
                      <button
                        type="button"
                        aria-pressed={senderMode === 'partner_business'}
                        onClick={() => updateSenderMode('partner_business')}
                        className={`min-h-20 rounded-md border p-3 text-left transition-[transform,background-color,border-color] active:scale-[0.96] ${senderMode === 'partner_business' ? 'border-emerald-300 bg-emerald-50' : 'border-slate-200 bg-white hover:bg-slate-50'}`}
                      >
                        <span className="block text-sm font-semibold text-slate-950">Сам бизнес</span>
                        <span className="mt-1 block text-pretty text-xs leading-5 text-slate-600">Сообщение и подключённый аккаунт принадлежат {selectedWorkstream.client_business_name || 'этому бизнесу'}.</span>
                      </button>
                      <button
                        type="button"
                        aria-pressed={senderMode === 'localos_for_partner'}
                        onClick={() => updateSenderMode('localos_for_partner')}
                        className={`min-h-20 rounded-md border p-3 text-left transition-[transform,background-color,border-color] active:scale-[0.96] ${senderMode === 'localos_for_partner' ? 'border-orange-300 bg-orange-50' : 'border-slate-200 bg-white hover:bg-slate-50'}`}
                      >
                        <span className="block text-sm font-semibold text-slate-950">LocalOS представляет бизнес</span>
                        <span className="mt-1 block text-pretty text-xs leading-5 text-slate-600">Отправляем с аккаунта LocalOS и прямо называем {selectedWorkstream.client_business_name || 'бизнес'}, который представляет LocalOS.</span>
                      </button>
                    </div>
                    {senderMode === 'localos_for_partner' ? (
                      <div className="mt-2 rounded-md bg-orange-50 px-3 py-2 text-pretty text-xs leading-5 text-orange-950">
                        В каждом сообщении будет явная фраза: LocalOS пишет от своего имени и представляет {selectedWorkstream.client_business_name || 'этот бизнес'} в партнёрском предложении. Скрытая подмена отправителя запрещена.
                      </div>
                    ) : null}
                  </fieldset>
                ) : null}

                {savedOutreachCampaign?.requires_regeneration ? (
                  <div className="mt-3 rounded-md bg-amber-50 p-3 text-pretty text-sm leading-6 text-amber-950">
                    <div className="font-semibold">Эту версию нельзя подтвердить</div>
                    <p className="mt-1">Она создана до текущей проверки персонализации. Покажите новую цепочку, проверьте тексты и сохраните следующую версию.</p>
                    <Button variant="outline" onClick={() => void prepareOutreachCampaign(false)} disabled={busyAction === 'preview-campaign'} className="mt-2 min-h-10 bg-white">
                      {busyAction === 'preview-campaign' ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : <Sparkles className="mr-2 h-4 w-4" />}
                      Подготовить новую цепочку
                    </Button>
                  </div>
                ) : null}

                <div className="mt-3 grid gap-2 sm:grid-cols-2">
                  {[0, 1, 2, 3].map((index) => (
                    <div key={index} className="rounded-md bg-white p-3 text-xs font-semibold text-slate-600">
                      <div>{['Сигнал', 'Опыт основателя', 'Кейс или материал', 'Завершение'][index]}</div>
                      <div className="mt-2 grid grid-cols-[minmax(0,1fr)_84px] gap-2">
                        <select
                          aria-label={`Канал касания ${index + 1}`}
                          value={sequenceChannels[index]}
                          onChange={(event) => updateSequenceChannel(index, event.target.value)}
                          className="min-h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm font-medium text-slate-900 outline-none focus:border-slate-400"
                        >
                          <option value="telegram">Telegram</option>
                          <option value="email">Email</option>
                          <option value="max">MAX · вручную</option>
                          <option value="vk">VK · вручную</option>
                          <option value="whatsapp">WhatsApp · вручную</option>
                          <option value="sms">SMS · вручную</option>
                        </select>
                        <label className="sr-only" htmlFor={`touch-day-${index}`}>День касания {index + 1}</label>
                        <Input
                          id={`touch-day-${index}`}
                          type="number"
                          min={index === 0 ? 0 : 1}
                          value={sequenceDays[index]}
                          disabled={index === 0}
                          onChange={(event) => updateSequenceDay(index, Number(event.target.value))}
                          className="h-10 bg-white text-center tabular-nums"
                          title="День от старта"
                        />
                      </div>
                      <div className="mt-1 text-[11px] font-medium text-slate-400">День <span className="tabular-nums">{sequenceDays[index]}</span> от старта</div>
                    </div>
                  ))}
                </div>

                {['max', 'vk', 'whatsapp', 'sms', 'manual'].includes(sequenceChannels[0]) ? (
                  <div className="mt-3 rounded-md bg-sky-50 px-3 py-3 text-pretty text-sm leading-6 text-sky-900">
                    Первое касание выполняется вручную. Кампания подождёт вашей отметки и через 48 часов перейдёт в «Нужно внимание» — автоматическое продолжение не начнётся скрытно.
                  </div>
                ) : null}

                {outreachPreview?.channel_availability ? (
                  <div className="mt-3 space-y-2">
                    <div className="flex flex-wrap gap-2">
                      {Object.entries(outreachPreview.channel_availability).map(([channel, item]) => {
                      const labels: Record<string, string> = {
                        ready: 'готов',
                        connect_required: 'нужно подключить отправителя',
                        permission_required: 'отправка запрещена',
                        manual: 'вручную',
                        recipient_missing: 'нет контакта',
                        adapter_unavailable: 'нет безопасной отправки',
                        sender_degraded: 'отправитель ограничен',
                        sender_paused: 'отправитель на паузе',
                        sender_selection_required: 'выберите отправителя',
                      };
                      return <Badge key={channel} variant="outline" className={item.status === 'ready' ? 'border-emerald-200 bg-emerald-50 text-emerald-800' : item.status === 'permission_required' ? 'border-amber-200 bg-amber-50 text-amber-800' : 'bg-white text-slate-700'}>{channel} · {labels[String(item.status || '')] || item.status}</Badge>;
                      })}
                    </div>
                    {[0, 1, 2, 3].map((touchIndex) => {
                      const channel = sequenceChannels[touchIndex];
                      const accounts = outreachPreview.channel_availability?.[channel]?.sender_accounts || [];
                      if (!['telegram', 'email'].includes(channel) || accounts.length <= 1) return null;
                      return (
                        <label key={`${channel}-${touchIndex}`} className="block rounded-md bg-amber-50 p-3 text-sm font-semibold text-amber-950">
                          Отправитель для касания {touchIndex + 1} · {channel}
                          <select
                            value={sequenceSenders[touchIndex] || ''}
                            onChange={(event) => {
                              setSequenceSenders((current) => ({ ...current, [touchIndex]: event.target.value }));
                              setOutreachPreview(null);
                              setSavedOutreachCampaign(null);
                              setPilotReadiness(null);
                              setNotice('Отправитель выбран. Обновите preview.');
                            }}
                            className="mt-2 min-h-10 w-full rounded-md border border-amber-200 bg-white px-3 text-sm font-medium text-slate-900"
                          >
                            <option value="">Выберите аккаунт</option>
                            {accounts.map((account) => (
                              <option key={account.id} value={account.id} disabled={account.status !== 'ready'}>
                                {account.display_name || account.sender_identity || account.id} · {account.status}
                              </option>
                            ))}
                          </select>
                        </label>
                      );
                    })}
                  </div>
                ) : null}

                {outreachPreview?.status === 'needs_evidence' ? (
                  <div className="mt-3 rounded-md bg-amber-50 px-3 py-3 text-sm text-amber-900">
                    Нельзя подставить общий шаблон. Не хватает: {(outreachPreview.missing || []).join(', ') || 'подтверждённых фактов для персонализации'}.
                  </div>
                ) : null}
                {outreachPreview?.status === 'needs_generation' ? (
                  <div className="mt-3 rounded-md bg-amber-50 px-3 py-3 text-pretty text-sm leading-6 text-amber-900">
                    LocalOS сохранил факты, но не смог подготовить персональный текст. Нажмите «Показать всю цепочку» ещё раз. Сохранение и отправка заблокированы.
                  </div>
                ) : null}
                {outreachPreview?.status === 'needs_revision' ? (
                  <div className="mt-3 rounded-md bg-amber-50 px-3 py-3 text-pretty text-sm leading-6 text-amber-900">
                    Текст не прошёл проверку точности и естественности. Проверьте источник и факты об отправителе, затем обновите предпросмотр.
                  </div>
                ) : null}
                {outreachPreview?.status === 'invalid_sequence' ? (
                  <div className="mt-3 rounded-md bg-rose-50 px-3 py-3 text-pretty text-sm leading-6 text-rose-900">
                    Интервалы должны идти по возрастанию и оставлять минимум сутки между касаниями. Исправьте дни и обновите предпросмотр.
                  </div>
                ) : null}
                {outreachPreview?.status === 'needs_channel_setup' ? (
                  <div className="mt-3 rounded-md bg-sky-50 px-3 py-3 text-pretty text-sm leading-6 text-sky-900">
                    Тексты и порядок готовы. Сохраните черновик версии; подтверждение и запуск останутся заблокированы, пока вы не подключите отправителя или не выберете ручной канал.
                  </div>
                ) : null}
                {outreachPreview?.generation?.status === 'ready' ? (
                  <p className="mt-3 text-pretty text-xs leading-5 text-slate-500">Персонализацию подготовил LocalOS; каждое касание проверено по источнику, фактам и тону.</p>
                ) : null}

                {outreachPreview?.quality_gate ? (
                  <div className={`mt-3 flex items-start gap-3 rounded-md p-3 ${outreachPreview.quality_gate.passed
                    ? 'bg-emerald-50 text-emerald-950 ring-1 ring-inset ring-emerald-200'
                    : 'bg-amber-50 text-amber-950 ring-1 ring-inset ring-amber-200'}`}>
                    <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0" />
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-baseline justify-between gap-2">
                        <div className="text-sm font-semibold">Проверка всей цепочки</div>
                        <div className="tabular-nums text-sm font-semibold">
                          {Number(outreachPreview.quality_gate.total_score ?? outreachPreview.quality_gate.score ?? 0)}/{Number(outreachPreview.quality_gate.max_score || 18)}
                        </div>
                      </div>
                      <p className="mt-1 text-pretty text-sm leading-6">
                        {outreachQualityVerdictLabels[String(outreachPreview.quality_gate.verdict || '')] || 'Нужна проверка'}.
                        {outreachPreview.quality_gate.passed
                          ? ' Все сообщения опираются на источники и готовы к вашему решению.'
                          : ' Откройте проверку нужного касания ниже — LocalOS покажет, что исправить.'}
                      </p>
                    </div>
                  </div>
                ) : null}

                {(outreachPreview?.touches || []).length > 0 ? (
                  <div className="mt-3 space-y-2">
                    {(outreachPreview?.touches || []).map((touch) => (
                      <article key={`${touch.sequence_index}-${touch.channel}`} className="rounded-md bg-white p-3 ring-1 ring-slate-200">
                        <div className="flex items-center justify-between gap-3 text-xs font-semibold uppercase tracking-[0.06em] text-slate-500">
                          <span>День {touch.day_offset} · {touch.channel}</span>
                          <span className={touch.quality_gate?.passed ? 'text-emerald-700' : 'text-amber-700'}>{touch.quality_gate?.passed ? 'Факты проверены' : 'Нужна проверка'}</span>
                        </div>
                        {touch.subject ? <div className="mt-2 text-sm font-semibold text-slate-950">Тема: {touch.subject}</div> : null}
                        {touch.observation || touch.problem_hypothesis || touch.relevance_bridge ? (
                          <div className="mt-3 space-y-1 border-l-2 border-sky-200 pl-3 text-sm leading-6 text-slate-700">
                            {touch.observation ? <p><span className="font-semibold text-slate-900">Факт:</span> {touch.observation}</p> : null}
                            {touch.problem_hypothesis ? <p><span className="font-semibold text-slate-900">Гипотеза:</span> {touch.problem_hypothesis}</p> : null}
                            {touch.relevance_bridge ? <p><span className="font-semibold text-slate-900">Почему это связано:</span> {touch.relevance_bridge}</p> : null}
                          </div>
                        ) : null}
                        <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-800">{touch.text}</p>
                        {touch.source_url ? <a href={touch.source_url} target="_blank" rel="noreferrer" className="mt-2 inline-flex min-h-9 items-center gap-1 text-xs font-semibold text-sky-700">Источник <ExternalLink className="h-3.5 w-3.5" /></a> : null}
                        {touch.quality_gate ? (
                          <details open={!touch.quality_gate.passed} className="mt-3 rounded-md bg-slate-50 px-3 py-2 ring-1 ring-inset ring-slate-200">
                            <summary className="min-h-10 cursor-pointer select-none py-2 text-sm font-semibold text-slate-800">
                              Почему такая оценка ·{' '}
                              <span className="tabular-nums">
                                {Number(touch.quality_gate.total_score ?? touch.quality_gate.score ?? 0)}/{Number(touch.quality_gate.max_score || 18)}
                              </span>
                              {' '}· {outreachQualityVerdictLabels[String(touch.quality_gate.verdict || '')] || 'Нужна проверка'}
                            </summary>
                            <div className="grid gap-x-4 gap-y-2 pb-3 sm:grid-cols-2">
                              {Object.entries(touch.quality_gate.criterion_scores || {}).map(([criterion, score]) => (
                                <div key={criterion} className="flex items-center justify-between gap-3 text-xs text-slate-600">
                                  <span>{outreachQualityCriterionLabels[criterion] || criterion}</span>
                                  <span className={`shrink-0 tabular-nums font-semibold ${Number(score) === 2 ? 'text-emerald-700' : Number(score) === 1 ? 'text-amber-700' : 'text-rose-700'}`}>
                                    {Number(score)}/2
                                  </span>
                                </div>
                              ))}
                            </div>
                            {(touch.quality_gate.reason_codes || []).length > 0 ? (
                              <div className="border-t border-slate-200 py-3">
                                <div className="text-xs font-semibold uppercase tracking-[0.06em] text-slate-500">Что исправить</div>
                                <ul className="mt-2 space-y-1 text-sm leading-5 text-slate-700">
                                  {(touch.quality_gate.reason_codes || []).map((reasonCode) => (
                                    <li key={reasonCode}>• {outreachQualityReasonLabels[reasonCode] || reasonCode}</li>
                                  ))}
                                </ul>
                              </div>
                            ) : (
                              <p className="border-t border-slate-200 py-3 text-sm text-emerald-700">Критических замечаний нет.</p>
                            )}
                          </details>
                        ) : null}
                      </article>
                    ))}
                  </div>
                ) : null}

                <div className="mt-3 grid gap-2 sm:grid-cols-2">
                  <Button variant="outline" onClick={() => void prepareOutreachCampaign(false)} disabled={busyAction === 'preview-campaign'} className="min-h-11 bg-white">
                    {busyAction === 'preview-campaign' ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : <Sparkles className="mr-2 h-4 w-4" />}
                    Показать всю цепочку
                  </Button>
                  <Button variant="outline" onClick={() => void prepareOutreachCampaign(true)} disabled={busyAction === 'save-campaign' || !['ready', 'needs_channel_setup'].includes(String(outreachPreview?.status || ''))} className="min-h-11 bg-white">
                    {busyAction === 'save-campaign' && <RefreshCw className="mr-2 h-4 w-4 animate-spin" />}
                    {outreachPreview?.status === 'needs_channel_setup' ? 'Сохранить черновик версии' : 'Сохранить новую версию'}
                  </Button>
                </div>
                {savedOutreachCampaign?.status === 'draft' ? (
                  <Button onClick={() => void approveOutreachCampaign()} disabled={busyAction === 'approve-campaign' || savedOutreachCampaign.requires_regeneration || savedCampaignNeedsChannelSetup} className="mt-2 min-h-11 w-full bg-orange-500 text-white hover:bg-orange-600">
                    {busyAction === 'approve-campaign' ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : <ShieldCheck className="mr-2 h-4 w-4" />}
                    {savedOutreachCampaign.requires_regeneration
                      ? 'Сначала подготовьте новую цепочку'
                      : savedCampaignNeedsChannelSetup
                        ? 'Сначала настройте каналы и отправителя'
                        : 'Подтвердить всю цепочку один раз'}
                  </Button>
                ) : null}
                {savedOutreachCampaign && !pilotAlreadySent && !pilotReplyReceived ? (
                  <section className={`mt-3 rounded-2xl p-4 ${pilotReadiness?.can_dispatch_first_touch
                    ? 'bg-emerald-50 shadow-[0_0_0_1px_rgba(16,185,129,0.22),0_1px_2px_-1px_rgba(15,23,42,0.08)]'
                    : 'bg-white shadow-[0_0_0_1px_rgba(15,23,42,0.08),0_1px_2px_-1px_rgba(15,23,42,0.06)]'}`}>
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                      <div>
                        <h4 className="text-balance text-sm font-semibold text-slate-950">Готовность к первому касанию</h4>
                        <p className="mt-1 max-w-2xl text-pretty text-sm leading-6 text-slate-600">
                          LocalOS проверит текущую версию, отправителя, контакт, ответы, stop-list и лимиты. Сообщение не отправится.
                        </p>
                      </div>
                      <Button
                        variant="outline"
                        onClick={() => void runPilotPreflight()}
                        disabled={Boolean(busyAction)}
                        className="min-h-11 shrink-0 bg-white"
                      >
                        {busyAction === 'pilot-preflight' ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : <ShieldCheck className="mr-2 h-4 w-4" />}
                        Проверить готовность
                      </Button>
                    </div>
                    {pilotReadiness ? (
                      <div className="mt-4 border-t border-slate-200/80 pt-3">
                        <ul className="grid gap-2 sm:grid-cols-2">
                          {(pilotReadiness.checks || []).map((check) => (
                            <li key={String(check.code || check.label)} className="flex items-start gap-2 text-sm leading-5 text-slate-700">
                              {check.passed
                                ? <Check className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
                                : <CircleAlert className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />}
                              <span className="text-pretty">{check.label}</span>
                            </li>
                          ))}
                        </ul>
                        <p className={`mt-3 text-pretty text-sm font-medium leading-6 ${pilotReadiness.can_dispatch_first_touch ? 'text-emerald-900' : 'text-amber-900'}`}>
                          {pilotReadiness.next_action}
                        </p>
                      </div>
                    ) : null}
                  </section>
                ) : null}
                {canDispatchPilot ? (
                  <div className="mt-3 rounded-md bg-orange-50 p-3 text-sm text-orange-950">
                    <div className="font-semibold">Следующий шаг: первое пилотное касание</div>
                    <p className="mt-1 leading-6 text-orange-900">Будет отправлено ровно одно сообщение. Остальные каналы не запустятся.</p>
                    <Button onClick={() => void dispatchPilotFirstTouch()} disabled={Boolean(busyAction)} className="mt-2 min-h-11 w-full bg-orange-500 text-white hover:bg-orange-600">
                      {busyAction === 'pilot-dispatch' ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : <ShieldCheck className="mr-2 h-4 w-4" />}
                      Отправить только первое касание
                    </Button>
                  </div>
                ) : null}
                {canSyncPilotReply || pilotReplyReceived ? (
                  <div className={`mt-3 rounded-md p-3 text-sm ${pilotReplyReceived ? 'bg-emerald-50 text-emerald-950' : 'bg-sky-50 text-sky-950'}`}>
                    <div className="font-semibold">{pilotReplyReceived ? 'Ответ получен — цепочка остановлена' : 'Ожидание ответа на пилот'}</div>
                    <p className="mt-1 leading-6">{pilotReplyReceived
                      ? 'LocalOS сохранил ответ и отменил будущие касания по всем каналам.'
                      : 'Проверка ограничена конкретной кампанией и аккаунтом отправителя.'}</p>
                    {canSyncPilotReply ? (
                      <Button variant="outline" onClick={() => void syncPilotReply()} disabled={Boolean(busyAction)} className="mt-2 min-h-11 w-full bg-white">
                        <RefreshCw className={`mr-2 h-4 w-4 ${busyAction === 'pilot-reply-sync' ? 'animate-spin' : ''}`} />
                        Проверить ответ сейчас
                      </Button>
                    ) : null}
                  </div>
                ) : null}
                <p className="mt-2 text-xs leading-5 text-slate-500">Перед каждым касанием LocalOS повторно проверит approval версии, sender account, разрешение, ответ, suppression, cooldown и дневной лимит.</p>
              </section>

              <div className="rounded-md bg-slate-50 p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="text-xs font-semibold uppercase tracking-[0.1em] text-slate-500">Отправитель</div>
                    <div className="mt-1 font-semibold text-slate-950">{selectedSenderLabel}</div>
                  </div>
                  <Badge variant="outline" className={readyChannelCount > 0
                    ? 'border-emerald-200 bg-emerald-50 text-emerald-800'
                    : 'border-amber-200 bg-amber-50 text-amber-800'}>
                    {outreachPreview
                      ? readyChannelCount > 0 ? `Готово каналов: ${readyChannelCount}` : 'Нужно подключение'
                      : 'Проверьте каналы'}
                  </Badge>
                </div>
                <p className="mt-2 text-pretty text-sm leading-6 text-slate-600">Telegram и email выбираются только из этого контура. MAX, VK и WhatsApp остаются ручными, пока для них нет проверенного adapter и синхронизации ответов.</p>
                <details className="mt-3 border-t border-slate-200 pt-2">
                  <summary className="flex min-h-10 cursor-pointer items-center text-sm font-semibold text-slate-700">Подключить или проверить email</summary>
                  <div className="pt-3">
                    <OutreachEmailSetup
                      scopeType={selectedSenderScope}
                      businessId={selectedSenderScope === 'business' ? selectedWorkstream.client_business_id : null}
                      compact
                      onChanged={() => {
                        setOutreachPreview(null);
                        setPilotReadiness(null);
                      }}
                    />
                  </div>
                </details>
                <a
                  href={`/dashboard/settings/integrations?focus=telegram&sender_scope=${selectedSenderScope}&return_to=${encodeURIComponent(`/dashboard/bazich?lead=${selectedLead.id}&workstream=${selectedWorkstream.id || ''}`)}`}
                  className="inline-flex min-h-10 items-center gap-2 text-sm font-semibold text-orange-700 transition-colors hover:text-orange-800"
                >
                  {selectedSenderScope === 'platform'
                    ? 'Настроить Telegram LocalOS'
                    : 'Настроить Telegram бизнеса'}
                  <ArrowRight className="h-4 w-4" />
                </a>
                <details
                  id="sender-facts"
                  open={senderFactsOpen}
                  onToggle={(event) => setSenderFactsOpen(event.currentTarget.open)}
                  className="mt-3 scroll-mt-6 border-t border-slate-200 pt-2"
                >
                  <summary className="flex min-h-10 cursor-pointer items-center text-sm font-semibold text-slate-700">
                    {senderProfileChecklist?.ready && contactIntelligence?.sender_profile?.confirmed_at
                      ? 'Обновить факты об отправителе'
                      : contactIntelligence?.sender_profile
                        ? 'Продолжить профиль отправителя'
                        : 'Заполнить факты об отправителе'}
                  </summary>
                  <div className="space-y-3 pt-2">
                    <div className="rounded-lg bg-slate-50 p-3 shadow-sm shadow-slate-900/5">
                      <div className="flex flex-wrap items-start justify-between gap-2">
                        <div>
                          <div className="font-semibold text-slate-900">Профиль заполняется один раз для всех кампаний этого бизнеса</div>
                          <p className="mt-1 text-pretty text-xs leading-5 text-slate-600">
                            Можно сохранить черновик. LocalOS подтвердит профиль только после заполнения обязательных фактов и не превратит пропуск в общий шаблон.
                          </p>
                        </div>
                        {senderProfileChecklist ? (
                          <Badge variant="outline" className={senderProfileChecklist.ready
                            ? 'border-emerald-200 bg-emerald-50 text-emerald-800 tabular-nums'
                            : 'border-amber-200 bg-amber-50 text-amber-800 tabular-nums'}>
                            {Number(senderProfileChecklist.completed_count || 0)} из {Number(senderProfileChecklist.required_count || 0)}
                          </Badge>
                        ) : null}
                      </div>
                      {(senderProfileChecklist?.items || []).length > 0 ? (
                        <div className="mt-3 grid gap-2 sm:grid-cols-2">
                          {(senderProfileChecklist?.items || []).map((item) => (
                            <div key={item.code} className="flex min-h-10 items-center gap-2 text-xs text-slate-700">
                              <span className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full ${item.complete ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}`}>
                                {item.complete ? <Check className="h-3.5 w-3.5" /> : <CircleAlert className="h-3.5 w-3.5" />}
                              </span>
                              <span>{item.complete ? item.title : item.label}</span>
                            </div>
                          ))}
                        </div>
                      ) : null}
                    </div>
                    {!contactIntelligence?.sender_profile && contactIntelligence?.sender_profile_suggestions?.requires_confirmation ? (
                      <div className="rounded-lg border border-sky-200 bg-sky-50 px-3 py-2 text-pretty text-xs leading-5 text-sky-900">
                        LocalOS уже подставил название, географию и типы партнёров из данных бизнеса и текущего поиска. Проверьте их; опыт, кейсы, предложение и голос добавьте только как подтверждённые факты.
                      </div>
                    ) : null}
                    <div className="grid gap-3 sm:grid-cols-2">
                      <label className="text-xs font-semibold text-slate-700">
                        Имя отправителя
                        <Input value={senderName} onChange={(event) => setSenderName(event.target.value)} placeholder="Например, Анна" className="mt-1 h-10 bg-white" />
                      </label>
                      <label className="text-xs font-semibold text-slate-700">
                        Роль
                        <Input value={senderRole} onChange={(event) => setSenderRole(event.target.value)} placeholder="Например, основатель" className="mt-1 h-10 bg-white" />
                      </label>
                    </div>
                    <label className="block text-xs font-semibold text-slate-700">
                      Компания
                      <Input value={senderCompany} onChange={(event) => setSenderCompany(event.target.value)} placeholder="Название бизнеса" className="mt-1 h-10 bg-white" />
                    </label>
                    <textarea value={senderOutcome} onChange={(event) => setSenderOutcome(event.target.value)} placeholder={`Какой конкретный результат даёт ${senderBusinessLabel}`} rows={2} className="w-full resize-y rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 outline-none focus:border-slate-400" />
                    <textarea value={senderAudience} onChange={(event) => setSenderAudience(event.target.value)} placeholder="Целевая аудитория и её контекст" rows={2} className="w-full resize-y rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 outline-none focus:border-slate-400" />
                    <div className="grid gap-2 sm:grid-cols-2">
                      <textarea value={senderSegments} onChange={(event) => setSenderSegments(event.target.value)} placeholder="ICP / сегменты — по одному на строку" rows={3} className="w-full resize-y rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 outline-none focus:border-slate-400" />
                      <textarea value={senderRecipientRoles} onChange={(event) => setSenderRecipientRoles(event.target.value)} placeholder="Роли получателей — по одной на строку" rows={3} className="w-full resize-y rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 outline-none focus:border-slate-400" />
                    </div>
                    <Input value={senderGeography} onChange={(event) => setSenderGeography(event.target.value)} placeholder="География поиска" className="h-10 bg-white" />
                    {selectedWorkstream.workstream_type === 'client_partnership' ? <textarea value={senderPartnerTypes} onChange={(event) => setSenderPartnerTypes(event.target.value)} placeholder="Желаемые типы партнёров — по одному на строку" rows={2} className="w-full resize-y rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 outline-none focus:border-slate-400" /> : null}
                    <textarea value={senderCtas} onChange={(event) => setSenderCtas(event.target.value)} placeholder="Допустимые следующие шаги — по одному на строку" rows={2} className="w-full resize-y rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 outline-none focus:border-slate-400" />
                    <textarea value={senderDisqualifiers} onChange={(event) => setSenderDisqualifiers(event.target.value)} placeholder="Кого и почему исключать — по одному условию на строку" rows={2} className="w-full resize-y rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 outline-none focus:border-slate-400" />
                    <label className="block text-xs font-semibold text-slate-700">
                      Подтверждённый опыт основателя или команды
                      <textarea
                        value={senderStory}
                        onChange={(event) => setSenderStory(event.target.value)}
                        placeholder="Что вы действительно делали и почему этот опыт относится к предложению"
                        rows={3}
                        className="mt-1 w-full resize-y rounded-md border border-slate-200 bg-white px-3 py-2 text-sm font-normal text-slate-800 outline-none focus:border-slate-400"
                      />
                    </label>
                    <label className="block text-xs font-semibold text-slate-700">
                      Подтверждённые факты и кейсы
                      <textarea value={senderProof} onChange={(event) => setSenderProof(event.target.value)} placeholder="По одному факту на строку; без неподтверждённых результатов" rows={3} className="mt-1 w-full resize-y rounded-md border border-slate-200 bg-white px-3 py-2 text-sm font-normal text-slate-800 outline-none focus:border-slate-400" />
                    </label>
                    <textarea value={senderOffer} onChange={(event) => setSenderOffer(event.target.value)} placeholder="Что можно предложить — по одному варианту на строку" rows={2} className="w-full resize-y rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 outline-none focus:border-slate-400" />
                    <textarea value={senderVoiceExample} onChange={(event) => setSenderVoiceExample(event.target.value)} placeholder="Примеры вашего живого голоса" rows={2} className="w-full resize-y rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 outline-none focus:border-slate-400" />
                    <textarea value={senderForbidden} onChange={(event) => setSenderForbidden(event.target.value)} placeholder="Что нельзя утверждать — по одному запрету на строку" rows={2} className="w-full resize-y rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 outline-none focus:border-slate-400" />
                    <Button
                      variant="outline"
                      onClick={saveSenderProfile}
                      disabled={busyAction === 'sender-profile' || !senderName.trim() || !senderRole.trim() || !senderCompany.trim()}
                      className="min-h-11 w-full bg-white active:scale-[0.96] transition-transform"
                    >
                      {busyAction === 'sender-profile' && <RefreshCw className="mr-2 h-4 w-4 animate-spin" />}
                      Сохранить и проверить готовность
                    </Button>
                    <p className="text-xs leading-5 text-slate-500">В сообщения попадут только подтверждённые факты и кейсы. Гипотезы и недостающие данные не превращаются в утверждения.</p>
                  </div>
                </details>
              </div>

              <div className="space-y-2">
                <Button onClick={prepareRoom} disabled={busyAction === 'prepare-room'} className="w-full min-h-11 bg-orange-500 text-white hover:bg-orange-600">
                  {busyAction === 'prepare-room' ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : <Sparkles className="mr-2 h-4 w-4" />}
                  {selectedWorkstream.room_state?.url ? 'Обновить цифровую комнату' : 'Подготовить цифровую комнату'}
                </Button>
                {selectedWorkstream.room_state?.url && (
                  <a href={selectedWorkstream.room_state.url} target="_blank" rel="noreferrer" className="flex min-h-11 items-center justify-center gap-2 rounded-md bg-slate-100 text-sm font-semibold text-slate-800 hover:bg-slate-200">
                    Открыть комнату <ExternalLink className="h-4 w-4" />
                  </a>
                )}
                {selectedWorkstream.room_state?.url && (
                  <Button variant="outline" onClick={markSent} disabled={busyAction === 'mark-sent'} className="w-full min-h-11">
                    <Send className="mr-2 h-4 w-4" />Отметить ручную отправку
                  </Button>
                )}
              </div>

              {selectedWorkstream.workstream_type === 'client_partnership' && selectedLead.lead_kind !== 'both' && (
                <div className="rounded-md bg-sky-50 p-4">
                  <div className="font-semibold text-sky-950">Компания интересна и для LocalOS?</div>
                  <p className="mt-1 text-sm text-sky-800">Добавьте отдельный контур продаж. Клиент не увидит эту работу, а его партнёрская история останется без изменений.</p>
                  <Button variant="outline" onClick={addLocalosWorkstream} disabled={busyAction === 'add-localos'} className="mt-3 min-h-10 border-sky-200 bg-white text-sky-900">
                    <Plus className="mr-2 h-4 w-4" />Добавить в продажи LocalOS
                  </Button>
                </div>
              )}

              <details id="lead-suppression-list" className="scroll-mt-6 border-t border-slate-200 pt-4">
                <summary className="min-h-10 cursor-pointer text-sm font-semibold text-slate-700">Stop-list и «не беспокоить»</summary>
                <div className="pt-3">
                  <OutreachSuppressionManager
                    workstreamId={selectedWorkstream.id}
                    businessId={selectedWorkstream.client_business_id}
                    scopeType={selectedWorkstream.workstream_type === 'localos_sales' ? 'platform' : 'business'}
                    onChanged={() => void loadLeads()}
                  />
                </div>
              </details>

              {notice && <div className="rounded-md bg-emerald-50 px-4 py-3 text-sm text-emerald-800">{notice}</div>}

              <details className="border-t border-slate-200 pt-4">
                <summary className="min-h-10 cursor-pointer text-sm font-semibold text-slate-600">Происхождение и технические данные</summary>
                <div className="mt-2 space-y-1 text-xs text-slate-500">
                  <p>{sourceLabel(selectedLead)}</p>
                  <p>ID компании: {selectedLead.id}</p>
                  <p>ID контура: {selectedWorkstream.id || 'legacy'}</p>
                </div>
              </details>
            </div>
          )}
        </SheetContent>
      </Sheet>

      <Sheet open={searchOpen} onOpenChange={setSearchOpen}>
        <SheetContent className="w-full overflow-y-auto sm:max-w-xl">
          <SheetHeader className="pr-8">
            <SheetTitle>Найти лидов</SheetTitle>
            <SheetDescription>Сначала выберите, для кого ищем компании. Это определит отправителя, предложение и цифровую комнату.</SheetDescription>
          </SheetHeader>

          <div className="mt-6 flex items-center gap-2 text-xs font-semibold text-slate-500">
            {[1, 2, 3].map((step) => (
              <React.Fragment key={step}>
                <span className={`flex h-7 w-7 items-center justify-center rounded-full ${searchStep >= step ? 'bg-slate-950 text-white' : 'bg-slate-100'}`}>{step}</span>
                {step < 3 && <span className={`h-px flex-1 ${searchStep > step ? 'bg-slate-950' : 'bg-slate-200'}`} />}
              </React.Fragment>
            ))}
          </div>

          {searchStep === 1 && (
            <div className="mt-6 space-y-3">
              <button type="button" onClick={() => setSearchScope('localos_sales')} className={`w-full rounded-md p-4 text-left ${searchScope === 'localos_sales' ? 'bg-sky-50 ring-2 ring-sky-300' : 'bg-slate-50 hover:bg-slate-100'}`}>
                <div className="flex items-center gap-3 font-semibold text-slate-950"><Building2 className="h-5 w-5 text-sky-600" />Для LocalOS</div>
                <p className="mt-1 pl-8 text-sm text-slate-600">Найти компании, которым LocalOS может помочь с картами, контентом и автоматизацией.</p>
              </button>
              <button type="button" onClick={() => setSearchScope('client_partnership')} className={`w-full rounded-md p-4 text-left ${searchScope === 'client_partnership' ? 'bg-violet-50 ring-2 ring-violet-300' : 'bg-slate-50 hover:bg-slate-100'}`}>
                <div className="flex items-center gap-3 font-semibold text-slate-950"><Users className="h-5 w-5 text-violet-600" />Для клиента</div>
                <p className="mt-1 pl-8 text-sm text-slate-600">Найти потенциальных партнёров рядом с точкой клиента.</p>
              </button>
              {searchScope === 'client_partnership' && (
                <select value={searchClientId} onChange={(event) => setSearchClientId(event.target.value)} className="h-11 w-full rounded-md border border-slate-200 bg-white px-3 text-sm">
                  <option value="">Выберите клиента</option>
                  {businessOptions.map((business) => <option key={business.id} value={business.id}>{business.name}</option>)}
                </select>
              )}
              <Button onClick={() => setSearchStep(2)} disabled={searchScope === 'client_partnership' && !searchClientId} className="w-full min-h-11 bg-orange-500 text-white hover:bg-orange-600">
                Указать категорию и территорию <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </div>
          )}

          {searchStep === 2 && (
            <div className="mt-6 space-y-4">
              <div>
                <label className="text-sm font-semibold text-slate-800">Кого ищем</label>
                <Input value={searchCategory} onChange={(event) => setSearchCategory(event.target.value)} placeholder="Например: стоматологии, фитнес-клубы" className="mt-2 h-11" />
              </div>
              <div>
                <label className="text-sm font-semibold text-slate-800">Где ищем</label>
                <Input value={searchLocation} onChange={(event) => setSearchLocation(event.target.value)} placeholder="Город, район или адрес точки" className="mt-2 h-11" />
              </div>
              {searchScope === 'client_partnership' && (
                <div>
                  <label className="text-sm font-semibold text-slate-800">Радиус от точки клиента</label>
                  <div className="mt-2 grid grid-cols-4 gap-2">
                    {[['500', '500 м'], ['1000', '1 км'], ['3000', '3 км'], ['5000', '5 км']].map(([value, label]) => (
                      <button key={value} type="button" onClick={() => setSearchRadius(value)} className={`min-h-10 rounded-md text-sm font-semibold ${searchRadius === value ? 'bg-slate-950 text-white' : 'bg-slate-100 text-slate-700'}`}>{label}</button>
                    ))}
                  </div>
                </div>
              )}
              <details className="rounded-md bg-slate-50 p-3">
                <summary className="cursor-pointer text-sm font-semibold text-slate-700">Дополнительные настройки</summary>
                <select value={searchSource} onChange={(event) => setSearchSource(event.target.value)} className="mt-3 h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm">
                  <option value="apify_yandex">Яндекс Карты</option>
                  <option value="apify_2gis">2ГИС</option>
                  <option value="apify_google">Google Maps</option>
                  <option value="apify_apple">Apple Maps</option>
                </select>
              </details>
              {searchError && <p className="text-sm text-red-600">{searchError}</p>}
              <div className="flex gap-2">
                <Button variant="outline" onClick={() => setSearchStep(1)} className="min-h-11">Назад</Button>
                <Button onClick={startSearch} disabled={searchBusy} className="min-h-11 flex-1 bg-orange-500 text-white hover:bg-orange-600">
                  {searchBusy ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : <Search className="mr-2 h-4 w-4" />}
                  {searchBusy ? 'Ищем компании…' : 'Найти компании'}
                </Button>
              </div>
            </div>
          )}

          {searchStep === 3 && (
            <div className="mt-6 space-y-4">
              <div>
                <h3 className="font-semibold text-slate-950">Проверьте найденные компании</h3>
                <p className="mt-1 text-sm text-slate-500">Выбранные компании попадут в {searchScope === 'localos_sales' ? 'продажи LocalOS' : `партнёры · ${selectedClient?.name || 'клиент'}`}.</p>
              </div>
              <div className="max-h-[52vh] divide-y divide-slate-200 overflow-y-auto">
                {searchResults.map((lead) => {
                  const resultId = lead.id || lead.google_id || lead.name || '';
                  const checked = selectedSearchIds.includes(resultId);
                  return (
                    <label key={resultId} className="flex cursor-pointer gap-3 py-3">
                      <Checkbox
                        checked={checked}
                        onCheckedChange={(nextChecked) => setSelectedSearchIds((current) => nextChecked
                          ? [...current, resultId]
                          : current.filter((item) => item !== resultId))}
                      />
                      <span className="min-w-0">
                        <span className="block truncate text-sm font-semibold text-slate-950">{lead.name || 'Компания'}</span>
                        <span className="mt-1 block truncate text-xs text-slate-500">{[lead.category, lead.address || lead.city].filter(Boolean).join(' · ')}</span>
                      </span>
                    </label>
                  );
                })}
              </div>
              {searchError && <p className="text-sm text-red-600">{searchError}</p>}
              <div className="flex gap-2">
                <Button variant="outline" onClick={() => setSearchStep(2)} className="min-h-11">Изменить поиск</Button>
                <Button onClick={saveSearchResults} disabled={searchBusy || !selectedSearchIds.length} className="min-h-11 flex-1 bg-orange-500 text-white hover:bg-orange-600">
                  {searchBusy ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : <Plus className="mr-2 h-4 w-4" />}
                  Добавить выбранные
                </Button>
              </div>
            </div>
          )}
        </SheetContent>
      </Sheet>
    </div>
  );
}

export default AdminLeadRegistry;
