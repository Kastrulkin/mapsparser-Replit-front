import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ArrowRight,
  Building2,
  Check,
  ChevronDown,
  CircleAlert,
  ExternalLink,
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
import { leadMapLink } from '../../lib/leadMapLink';
import { researchSourcePresentation } from '../../lib/researchSourcePresentation';
import { matchesSelectedSignalKeys } from '../../lib/leadSignalFilters';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { Input } from '../ui/input';
import { Checkbox } from '../ui/checkbox';
import { OutreachEmailSetup } from '../OutreachEmailSetup';
import { OutreachLearningInsights } from './OutreachLearningInsights';
import { OutreachSuppressionManager } from './OutreachSuppressionManager';
import { OutreachMessageQueue } from './OutreachMessageQueue';
import {
  buildProjectedOutreachTouches,
  defaultOutreachStartValue,
  OutreachScheduleCalendar,
  outreachStartIso,
} from './OutreachScheduleCalendar';
import {
  OutreachTouchMessageEditor,
} from './OutreachTouchMessageEditor';
import { OutreachDateTimePicker } from './OutreachDateTimePicker';
import {
  OutreachTouchMessageDraft,
  outreachTouchMessageDraft,
  outreachTouchMessageText,
} from './outreachTouchMessage';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '../ui/sheet';

type WorkstreamType = 'localos_sales' | 'client_partnership';
type SenderMode = 'localos' | 'partner_business' | 'localos_for_partner';
type RegistryView = 'leads' | 'messages' | 'results';
type ScopeFilter = 'all' | 'localos_sales' | 'client_partnership';

const outreachLocalDateTimeValue = (value?: string | null) => {
  const date = new Date(String(value || ''));
  if (Number.isNaN(date.getTime())) return '';
  const year = date.getFullYear();
  const month = `${date.getMonth() + 1}`.padStart(2, '0');
  const day = `${date.getDate()}`.padStart(2, '0');
  const hours = `${date.getHours()}`.padStart(2, '0');
  const minutes = `${date.getMinutes()}`.padStart(2, '0');
  return `${year}-${month}-${day}T${hours}:${minutes}`;
};

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

interface PartnerTypeFilterOption {
  id: string;
  label: string;
  count?: number;
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

interface RelationshipStage {
  code?: 'preparing_first_touch' | 'touch_sent' | 'responded' | 'response_touch_unknown';
  label?: string;
  touch_number?: number;
  channel?: string | null;
  occurred_at?: string | null;
}

interface ReadinessCheck {
  code?: string;
  label?: string;
  passed?: boolean;
}

interface ReadinessGate {
  code?: 'ready' | 'needs_attention';
  label?: string;
  checks?: ReadinessCheck[];
  blockers?: string[];
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
  signals?: Array<{
    signal_combo?: string;
    pattern_key?: string;
    key?: string;
    label?: string;
  }>;
  sources?: ResearchSource[];
  suggested_opener?: string;
  opener_source_url?: string;
  limitations?: string[];
  message_brief?: {
    operator_approved_reason?: string;
    operator_approved_at?: string;
    operator_approved_by?: string;
    operator_approved_source_type?: string;
    preparation_steps?: Record<string, {
      status?: 'started' | 'completed';
      label?: string;
      completed_at?: string;
      metadata?: Record<string, unknown>;
    }>;
  };
  researched_at?: string;
  stale?: boolean;
}

const outreachSignalLabels: Record<string, string> = {
  active_social_with_map_gap: 'Соцсети ведутся, карты можно усилить',
  active_external_channels_with_incomplete_map_profile: 'Внешние каналы ведутся, карточка не заполнена',
  active_social_with_service_price_gap: 'Соцсети ведутся, цены заполнены не полностью',
  active_social_with_unanswered_negative_review: 'Активные соцсети и отзыв без ответа',
  paid_map_promotion: 'Платное продвижение на картах',
  repeated_open_slots: 'Регулярно появляются свободные окна',
  repeated_discount_promotions: 'Регулярные скидки и акции',
  repeated_hiring_signals: 'Повторяющийся поиск сотрудников',
  recent_new_service_announcement: 'Запуск новой услуги',
  recent_event_announcement: 'Новое мероприятие',
  unanswered_reviews_with_active_presence: 'Отзывы без ответа при активном присутствии',
  network_profile_inconsistency: 'Различия между карточками сети',
};

const workstreamSignalKeys = (workstreams: LeadWorkstream[]) => Array.from(new Set(
  workstreams.flatMap((workstream) => (workstream.research?.signals || [])
    .map((signal) => String(signal.signal_combo || signal.pattern_key || signal.key || '').trim())
    .filter(Boolean)),
));

interface PreparationStep {
  status?: 'started' | 'completed';
  label?: string;
  completed_at?: string;
  metadata?: Record<string, unknown>;
}

const preparationStepTime = (value?: string) => {
  const date = new Date(String(value || ''));
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
};

function PreparationStepStatus({ step }: { step?: PreparationStep }) {
  if (!step?.completed_at) return null;
  const time = preparationStepTime(step.completed_at);
  return (
    <div className="mt-2 flex items-center gap-1.5 text-xs font-medium text-emerald-700">
      <Check className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
      <span>{step.label || 'Действие выполнено'}{time ? ` · ${time}` : ''}</span>
    </div>
  );
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
    source_owner_type?: 'residential_complex' | 'prospecting_recipient';
    source_owner_name?: string;
    source_owner_label?: string;
    sender_business_is_owner?: boolean;
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
    allowed_offers_json?: Array<string | { fact?: string; text?: string; status?: string }>;
    forbidden_claims_json?: Array<string | { fact?: string; text?: string; status?: string }>;
    voice_examples_json?: Array<string | { fact?: string; text?: string; status?: string }>;
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
  sender_profile_scope?: 'platform' | 'business';
  sender_mode?: SenderMode;
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
  human_language_review?: {
    passed?: boolean;
    detected_passed?: boolean;
    gate_passed?: boolean;
    verdict?: 'approve' | 'revise' | 'reject';
    reason_codes?: string[];
    enforced_reason_codes?: string[];
  };
}

interface OutreachLanguageSupport {
  status?: 'supported' | 'weak' | 'unsupported' | 'unavailable' | 'not_checked' | 'conditional_operator_approved';
  document_count?: number;
  source_count?: number;
  professional_source_count?: number;
  theme?: string;
  pain_reference_ids?: string[];
  language_reference_ids?: string[];
  pain_support_status?: string;
  language_support_status?: string;
  wording_policy?: string;
  frequency_claim_allowed?: boolean;
}

interface OutreachTouchPreview {
  id?: string;
  sequence_index: number;
  channel: string;
  contact_point_id?: string | null;
  day_offset: number;
  angle: string;
  subject?: string | null;
  text: string;
  channel_status: 'ready' | 'connect_required' | 'permission_required' | 'manual' | 'recipient_missing' | 'adapter_unavailable' | 'sender_degraded' | 'sender_paused' | 'sender_selection_required';
  quality_gate?: OutreachQualityGate;
  source_url?: string | null;
  observation?: string | null;
  problem_hypothesis?: string | null;
  pain_hypothesis?: string | null;
  pain_reference_ids?: string[];
  solution?: string | null;
  language_support?: OutreachLanguageSupport;
  pain_support?: OutreachLanguageSupport;
  relevance_bridge?: string | null;
  evidence_kind?: string | null;
  scheduled_at?: string | null;
  human_edited?: boolean;
}

interface OutreachPreview {
  status?: 'ready' | 'observe' | 'needs_contact' | 'needs_sender_setup' | 'needs_evidence' | 'needs_generation' | 'needs_revision' | 'needs_channel_setup' | 'invalid_sequence' | 'suppressed' | 'excluded';
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

interface OutreachInboundEvent {
  id: string;
  touch_id?: string | null;
  channel?: string;
  event_type?: string;
  classification?: string;
  is_human?: boolean;
  stops_campaign?: boolean;
  raw_payload_json?: Record<string, unknown>;
  occurred_at?: string;
  created_at?: string;
}

interface OutreachDelivery {
  id: string;
  touch_id?: string | null;
  channel?: string;
  delivery_status?: string;
  provider_message_id?: string | null;
  error_text?: string | null;
  scheduled_at?: string | null;
  sent_at?: string | null;
  created_at?: string;
  updated_at?: string;
}

interface SavedOutreachCampaign {
  id: string;
  version?: number;
  created_at?: string;
  status?: string;
  stop_reason?: string | null;
  last_reply_at?: string | null;
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
    channel_status?: string;
    sender_account_id?: string | null;
    contact_point_id?: string | null;
    angle_type?: string;
    scheduled_at?: string;
    subject?: string | null;
    generated_text?: string | null;
    approved_text?: string | null;
    quality_gate_json?: OutreachQualityGate;
    message_brief_json?: {
      channel_status?: string;
      source_url?: string | null;
      observation?: string | null;
      problem_hypothesis?: string | null;
      pain_hypothesis?: string | null;
      pain_reference_ids?: string[];
      solution?: string | null;
      language_support?: OutreachLanguageSupport;
      pain_support?: OutreachLanguageSupport;
      relevance_bridge?: string | null;
      evidence_kind?: string | null;
      human_edited?: boolean;
      manual_edit_review_required?: boolean;
      manual_edit_review_passed?: boolean;
      template_key?: string | null;
      template_version?: number | null;
      template_label?: string | null;
    };
  }>;
  inbound_events?: OutreachInboundEvent[];
  deliveries?: OutreachDelivery[];
}

interface OutreachCampaignSetupDraft {
  workstreamId: string;
  baseCampaignId: string;
  baseCampaignVersion: number;
  sequenceChannels: string[];
  sequenceDays: number[];
  sequenceStartAt: string;
  sequenceSenders: Record<number, string>;
  senderMode: SenderMode;
}

interface OutreachSenderAccountSummary {
  id: string;
  channel?: string;
  sender_identity?: string | null;
  display_name?: string | null;
  status?: string;
  outreach_enabled?: boolean;
  capabilities?: {
    direct_send?: boolean;
    reply_sync?: boolean;
  };
  health_status?: string;
}

const automaticOutreachChannels = new Set(['telegram', 'email', 'vk']);

const outreachSenderReady = (account: OutreachSenderAccountSummary | undefined) => Boolean(
  account
  && account.status === 'connected'
  && account.outreach_enabled
  && account.capabilities?.direct_send
  && account.capabilities?.reply_sync
  && !['blocked', 'paused', 'degraded'].includes(String(account.health_status || '')),
);

const outreachSenderStatusLabel = (account: OutreachSenderAccountSummary) => {
  if (account.status !== 'connected') return 'нужно подключить';
  if (['blocked', 'paused', 'degraded'].includes(String(account.health_status || ''))) return 'нужно проверить';
  if (!account.outreach_enabled) return 'отправка запрещена';
  if (!account.capabilities?.direct_send || !account.capabilities?.reply_sync) return 'нет безопасной отправки';
  return 'готов';
};

const internalSenderIdPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const providerSenderIdentityPattern = /^(community|group|account):[a-z0-9_-]+$/i;

const outreachSenderDisplayLabel = (account: OutreachSenderAccountSummary) => {
  const rawName = String(account.display_name || '').trim();
  const rawIdentity = String(account.sender_identity || '').trim();
  const name = internalSenderIdPattern.test(rawName) ? '' : rawName;
  const identity = internalSenderIdPattern.test(rawIdentity) || providerSenderIdentityPattern.test(rawIdentity)
    ? ''
    : rawIdentity;
  const genericNames = new Set(['Telegram-аккаунт', 'Email-аккаунт', 'VK-аккаунт', 'LocalOS']);
  const meaningfulName = genericNames.has(name) ? '' : name;

  if (meaningfulName && identity && meaningfulName !== identity) return `${meaningfulName} · ${identity}`;
  if (identity) return name && name !== identity ? `${name} · ${identity}` : identity;
  if (meaningfulName) return meaningfulName;
  if (account.channel === 'telegram') return 'Подключённый Telegram-аккаунт';
  if (account.channel === 'email') return 'Подключённая почта';
  if (account.channel === 'vk') return 'Подключённое VK-сообщество';
  return 'Подключённый аккаунт';
};

interface ChannelSetupBlocker {
  key: string;
  label: string;
  actionLabel: string;
  target: string;
  focusTarget?: string;
  actionHref?: string;
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
  relationship_stage?: RelationshipStage;
  readiness_gate?: ReadinessGate;
  research?: WorkstreamResearch | null;
  contact_points?: ContactPoint[];
  contact_summary?: { found?: number; verified?: number };
  selected_recipient?: ContactPoint | null;
  enrichment_state?: EnrichmentState | null;
  message_readiness?: MessageReadiness;
  service_compatibility_score?: number | null;
  campaign_state?: {
    id?: string;
    status?: string;
    version?: number;
    touches_count?: number;
    confirmed_touches_count?: number;
    sequence_has_gap?: boolean;
    last_confirmed_touch?: {
      id?: string;
      touch_number?: number;
      channel?: string;
      sent_at?: string;
    } | null;
    next_pending_touch?: {
      id?: string;
      touch_number?: number;
      channel?: string;
      status?: string;
      scheduled_at?: string;
    } | null;
    first_human_response?: {
      id?: string;
      touch_number?: number;
      channel?: string;
      classification?: string;
      occurred_at?: string;
    } | null;
    created_at?: string;
    updated_at?: string;
    approved_at?: string | null;
    stop_reason?: string | null;
  } | null;
  legacy?: boolean;
}

interface LeadItem {
  id: string;
  name?: string;
  category?: string;
  partner_type?: string;
  partner_type_label?: string;
  canonical_categories?: string[];
  canonical_category_labels?: string[];
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
  source_url?: string;
  rating?: number;
  reviews_count?: number;
  status?: string;
  pipeline_status?: string;
  lead_kind?: 'localos' | 'partner' | 'both';
  client_business_name?: string;
  workstreams?: LeadWorkstream[];
}

interface SearchResult extends LeadItem {
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
  SUPPRESSED_CONTACT: 'Получатель исключён из контактов',
  APPROVAL_BYPASS: 'Требуется новое ручное подтверждение',
  SENSITIVE_TARGETING: 'Сигнал нельзя безопасно использовать в сообщении',
  PAIN_SUPPORT_INSUFFICIENT: 'Для гипотезы недостаточно независимых профессиональных источников',
  PAIN_SOURCE_ROLE_INELIGIBLE: 'Источники не подтверждены как язык владельцев или специалистов',
  VOICE_SOURCE_INELIGIBLE: 'Источник нельзя использовать для проверки живого языка',
  SLOP_CLICHE: 'В тексте есть рекламный штамп или инфобизнес-формулировка',
  ABSTRACT_SOLUTION: 'Не названо конкретное действие LocalOS',
  RECIPIENT_ACTION_MISSING: 'Не названа конкретная ручная задача получателя',
  GENERIC_CTA: 'Финальный вопрос слишком общий',
  PROOF_WORDING_CHANGED: 'Подтверждённый кейс переформулирован',
  PROOF_SCOPE_MISMATCH: 'Кейс не подходит сегменту или сигналу',
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

const campaignRegistryStatusLabels: Record<string, string> = {
  draft: 'Черновик',
  approved: 'Подтверждена',
  active: 'Запущена',
  paused: 'На паузе',
  completed: 'Завершена',
  cancelled: 'Отменена',
  stopped: 'Остановлена',
};

const workstreamsForRegistry = (
  lead: LeadItem,
  scope: ScopeFilter,
  clientBusinessId: string,
) => (lead.workstreams || []).filter((workstream) => {
  if (scope !== 'all' && workstream.workstream_type !== scope) return false;
  if (clientBusinessId && workstream.client_business_id !== clientBusinessId) return false;
  return true;
});

const matchesCampaignRegistryFilter = (
  workstreams: LeadWorkstream[],
  campaignFilter: string,
) => {
  if (!campaignFilter) return true;
  const campaignStates = workstreams
    .map((workstream) => workstream.campaign_state)
    .filter((campaignState) => Boolean(campaignState));
  if (campaignFilter === 'with_campaign') return campaignStates.length > 0;
  if (campaignFilter === 'without_campaign') return campaignStates.length === 0;
  return campaignStates.some((campaignState) => campaignState?.status === campaignFilter);
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
  vk_manual: 'VK · вручную',
  instagram: 'Instagram',
  max: 'MAX',
  website_form: 'Форма на сайте',
  website: 'Сайт',
  other: 'Другой канал',
};

const recipientContactTypeForChannel = (channel: string) => channel === 'vk_manual' ? 'vk' : channel;

const outreachChannelHref = (channel: string, rawContact: string) => {
  const contact = rawContact.trim();
  if (!contact) return '';

  if (channel === 'email') {
    const email = contact.replace(/^mailto:/i, '').trim();
    return email ? `mailto:${email}` : '';
  }

  if (channel === 'phone') {
    const phone = contact.replace(/^tel:/i, '').replace(/[^\d+]/g, '');
    return phone ? `tel:${phone}` : '';
  }

  if (/^https?:\/\//i.test(contact)) return contact;
  if (/^(?:www\.)?[\w-]+(?:\.[\w-]+)+(?:[/?#].*)?$/i.test(contact)) return `https://${contact}`;
  if (channel === 'telegram' && /^@?[\w\d_]+$/.test(contact)) return `https://t.me/${contact.replace(/^@/, '')}`;
  if (channel === 'whatsapp' && /^\+?[\d\s()-]+$/.test(contact)) {
    const phone = contact.replace(/\D/g, '');
    return phone ? `https://wa.me/${phone}` : '';
  }
  return '';
};

const outreachTouchStatusLabels: Record<string, string> = {
  contact_ready: 'Контакт найден',
  recipient_missing: 'Нет контакта',
  reply: 'Есть ответ',
  draft: 'Черновик',
  approved: 'Подтверждено',
  scheduled: 'Запланировано',
  queued: 'В очереди',
  awaiting_manual_send: 'Ожидает ручной отправки',
  sent: 'Отправлено',
  delivered: 'Доставлено',
  manual_sent: 'Отправлено вручную',
  paused: 'На паузе',
  cancelled: 'Отменено',
  stopped: 'Остановлено',
  skipped: 'Пропущено',
  failed: 'Ошибка отправки',
  retry: 'Повторная попытка',
  dlq: 'Нужна помощь',
  reply_cancelled: 'Остановлено после ответа',
};

const canEditSavedTouch = (campaignStatus: string, touchStatus: string) => (
  (campaignStatus === 'draft' && touchStatus === 'draft')
  || (campaignStatus === 'paused' && touchStatus === 'paused')
);

const outreachReplyClassificationLabels: Record<string, string> = {
  interested: 'Интерес',
  question: 'Вопрос',
  not_interested: 'Не интересно',
  unsubscribe: 'Просьба не писать',
  complaint: 'Жалоба',
  human_unknown: 'Ответ получателя',
  out_of_office: 'Автоответ',
  bounce: 'Письмо не доставлено',
  temporary_delivery_failure: 'Временная ошибка доставки',
  permanent_delivery_failure: 'Контакт недоступен',
  system_acknowledgement: 'Системное уведомление',
};

const formatOutreachMoment = (value?: string | null) => {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleString('ru-RU', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  });
};

const inboundMessageText = (event: OutreachInboundEvent) => {
  const payload = event.raw_payload_json || {};
  const candidates = [payload.raw_reply, payload.reply, payload.body, payload.message_text, payload.text];
  const message = candidates.find((item) => typeof item === 'string' && item.trim());
  return typeof message === 'string' ? message.trim() : '';
};

const outreachStatusTone = (status?: string) => {
  if (status === 'reply' || ['sent', 'delivered', 'manual_sent'].includes(String(status || ''))) {
    return 'border-emerald-200 bg-emerald-50 text-emerald-800';
  }
  if (['scheduled', 'queued', 'approved'].includes(String(status || ''))) {
    return 'border-sky-200 bg-sky-50 text-sky-800';
  }
  if (status === 'failed') return 'border-rose-200 bg-rose-50 text-rose-800';
  if (['paused', 'stopped'].includes(String(status || ''))) {
    return 'border-amber-200 bg-amber-50 text-amber-800';
  }
  return 'border-slate-200 bg-white text-slate-700';
};

const manualContactOptions = [
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

const verificationLabel = (status?: string) => {
  if (status === 'verified') return 'Проверен';
  if (status === 'confirmed_source') return 'Подтверждён источником';
  if (status === 'valid_format') return 'Формат проверен';
  if (status === 'accept_all') return 'Домен принимает все адреса';
  if (status === 'invalid') return 'Не работает';
  if (status === 'stale') return 'Нужно обновить';
  if (status === 'manually_added') return 'Добавлен вручную';
  return 'Нужна проверка';
};

const contactSourceLabel = (sourceType?: string) => {
  if (sourceType === 'official_website') return 'официальный сайт';
  if (sourceType === 'hunter_public_sources') return 'публичные источники Hunter';
  if (sourceType === 'manual') return 'вручную';
  return 'карточка компании';
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

interface LeadDrawerSectionProps {
  id: string;
  title: string;
  description: string;
  status?: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}

const LeadDrawerSection = ({
  id,
  title,
  description,
  status,
  defaultOpen = false,
  children,
}: LeadDrawerSectionProps) => {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <section
      id={id}
      className="scroll-mt-28 overflow-hidden rounded-2xl bg-white shadow-[0_0_0_1px_rgba(15,23,42,0.08),0_1px_2px_-1px_rgba(15,23,42,0.06)]"
    >
      <button
        type="button"
        aria-expanded={open}
        aria-controls={`${id}-content`}
        onClick={() => setOpen((current) => !current)}
        className="flex min-h-16 w-full items-center gap-3 px-4 py-3 text-left transition-colors duration-150 hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-orange-400"
      >
        <span className="min-w-0 flex-1">
          <span className="block text-balance text-sm font-semibold text-slate-950">{title}</span>
          <span className="mt-1 block truncate text-xs leading-5 text-slate-600">{description}</span>
        </span>
        {status ? (
          <Badge variant="outline" className="hidden shrink-0 border-slate-200 bg-slate-50 text-slate-700 sm:inline-flex">
            {status}
          </Badge>
        ) : null}
        <ChevronDown className={`h-4 w-4 shrink-0 text-slate-500 transition-transform duration-200 ${open ? 'rotate-180' : ''}`} />
      </button>
      <div id={`${id}-content`} hidden={!open} className="border-t border-slate-100 p-3 sm:p-4">
        {children}
      </div>
    </section>
  );
};

const senderProfileFactLines = (
  items: Array<string | { fact?: string; text?: string }> | undefined,
) => (items || [])
  .map((item) => typeof item === 'string' ? item : String(item.fact || item.text || ''))
  .filter(Boolean)
  .join('\n');

export function AdminLeadRegistry({ businessOptions, senderBusinessLabel = 'ваш бизнес' }: AdminLeadRegistryProps) {
  const [view, setView] = useState<RegistryView>('leads');
  const [scope, setScope] = useState<ScopeFilter>('all');
  const [clientBusinessId, setClientBusinessId] = useState('');
  const [actionState, setActionState] = useState('');
  const [signalStrength, setSignalStrength] = useState('');
  const [selectedSignalKeys, setSelectedSignalKeys] = useState<string[]>([]);
  const [partnerType, setPartnerType] = useState('');
  const [campaignFilter, setCampaignFilter] = useState('');
  const [query, setQuery] = useState('');
  const [messageStatus, setMessageStatus] = useState('');
  const [messageChannel, setMessageChannel] = useState('');
  const [leads, setLeads] = useState<LeadItem[]>([]);
  const [clientFilterOptions, setClientFilterOptions] = useState<ClientFilterOption[]>([]);
  const [partnerTypeFilterOptions, setPartnerTypeFilterOptions] = useState<PartnerTypeFilterOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selectedLeadId, setSelectedLeadId] = useState<string | null>(null);
  const [selectedWorkstreamId, setSelectedWorkstreamId] = useState<string | null>(null);
  const [busyAction, setBusyAction] = useState('');
  const [notice, setNotice] = useState('');
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
  const [manualContactOpen, setManualContactOpen] = useState(false);
  const [vkHandoffContact, setVkHandoffContact] = useState(false);
  const [manualContactType, setManualContactType] = useState('telegram');
  const [manualContactValue, setManualContactValue] = useState('');
  const [manualTelegramUsage, setManualTelegramUsage] = useState('recipient');
  const [manualOwnerType, setManualOwnerType] = useState('company');
  const [manualPersonName, setManualPersonName] = useState('');
  const [manualRoleTitle, setManualRoleTitle] = useState('');
  const [manualContactError, setManualContactError] = useState('');
  const [manualOutreachReason, setManualOutreachReason] = useState('');
  const [dataPreparationMessage, setDataPreparationMessage] = useState('');
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
  const [sequenceChannels, setSequenceChannels] = useState(['telegram', 'email', 'max', 'vk']);
  const [sequenceDays, setSequenceDays] = useState([0, 3, 7, 12]);
  const [sequenceStartAt, setSequenceStartAt] = useState(defaultOutreachStartValue);
  const [sequenceSenders, setSequenceSenders] = useState<Record<number, string>>({});
  const [senderMode, setSenderMode] = useState<SenderMode>('localos');
  const [touchEdits, setTouchEdits] = useState<Record<number, OutreachTouchMessageDraft>>({});
  const [editingTouchIndex, setEditingTouchIndex] = useState<number | null>(null);
  const [touchEditsValidated, setTouchEditsValidated] = useState(false);
  const [campaignSetupDirty, setCampaignSetupDirty] = useState(false);
  const [senderAccounts, setSenderAccounts] = useState<OutreachSenderAccountSummary[]>([]);
  const [senderAccountsLoading, setSenderAccountsLoading] = useState(false);

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
      setPartnerTypeFilterOptions(
        Array.isArray(payload?.business_category_options)
          ? payload.business_category_options
          : Array.isArray(payload?.partner_type_options)
            ? payload.partner_type_options
            : [],
      );
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

  const categoryFilteredLeads = useMemo(() => {
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
      if (partnerType) {
        const canonicalCategories = lead.canonical_categories || [lead.partner_type || 'other'];
        if (!canonicalCategories.includes(partnerType)) return false;
      }
      if (signalStrength && !workstreams.some((item) => item.research?.signal_label === signalStrength)) return false;
      if (!matchesSelectedSignalKeys(workstreamSignalKeys(workstreams), selectedSignalKeys)) return false;
      if (view === 'results') {
        return workstreams.some((item) => ['replied', 'responded', 'converted', 'qualified'].includes(String(item.status || '')));
      }
      return true;
    });
  }, [leads, partnerType, query, selectedSignalKeys, signalStrength, view]);

  const signalFilterOptions = useMemo(() => {
    const counts = new Map<string, number>();
    leads.forEach((lead) => {
      workstreamSignalKeys(lead.workstreams || []).forEach((key) => {
        counts.set(key, (counts.get(key) || 0) + 1);
      });
    });
    return Array.from(counts.entries())
      .map(([key, count]) => ({
        key,
        count,
        label: outreachSignalLabels[key] || key.replaceAll('_', ' '),
      }))
      .sort((left, right) => left.label.localeCompare(right.label, 'ru'));
  }, [leads]);

  const campaignFilterCounts = useMemo(() => {
    const counts: Record<string, number> = {
      with_campaign: 0,
      without_campaign: 0,
      draft: 0,
      approved: 0,
      active: 0,
      paused: 0,
      completed: 0,
      cancelled: 0,
      stopped: 0,
    };
    categoryFilteredLeads.forEach((lead) => {
      const relevantWorkstreams = workstreamsForRegistry(lead, scope, clientBusinessId);
      const campaignStates = relevantWorkstreams
        .map((workstream) => workstream.campaign_state)
        .filter((campaignState) => Boolean(campaignState));
      if (campaignStates.length) counts.with_campaign += 1;
      else counts.without_campaign += 1;
      const statuses = new Set(campaignStates.map((campaignState) => campaignState?.status).filter(Boolean));
      statuses.forEach((status) => {
        if (status && status in counts) counts[status] += 1;
      });
    });
    return counts;
  }, [categoryFilteredLeads, clientBusinessId, scope]);

  const filteredLeads = useMemo(() => categoryFilteredLeads.filter((lead) => (
    matchesCampaignRegistryFilter(
      workstreamsForRegistry(lead, scope, clientBusinessId),
      campaignFilter,
    )
  )), [campaignFilter, categoryFilteredLeads, clientBusinessId, scope]);

  const visiblePartnerTypeOptions = partnerTypeFilterOptions;

  const selectedLead = leads.find((lead) => lead.id === selectedLeadId) || null;
  const selectedWorkstream = selectedLead?.workstreams?.find((item) => item.id === selectedWorkstreamId)
    || selectedLead?.workstreams?.[0]
    || null;
  const selectedLeadMapLink = leadMapLink([
    {
      url: selectedLead?.source_url,
      source_type: selectedLead?.source_kind,
      provider: selectedLead?.source_provider,
    },
    ...(selectedWorkstream?.research?.sources || []).map((source) => ({
      url: source.url,
      source_type: source.source_type,
    })),
  ]);
  const selectedSenderScope = selectedWorkstream?.workstream_type === 'localos_sales'
    || senderMode === 'localos_for_partner'
    ? 'platform'
    : 'business';
  const usesPlatformSender = selectedSenderScope === 'platform';
  const selectedSenderLabel = selectedWorkstream?.workstream_type === 'localos_sales'
    ? 'LocalOS'
    : senderMode === 'localos_for_partner'
      ? `${selectedWorkstream?.client_business_name || 'Бизнес партнёра'} через LocalOS`
      : selectedWorkstream?.client_business_name || 'Выбранный клиент';
  const loadSenderAccounts = useCallback(async () => {
    const businessId = selectedWorkstream?.client_business_id;
    if (selectedSenderScope === 'business' && !businessId) {
      setSenderAccounts([]);
      return;
    }
    setSenderAccountsLoading(true);
    try {
      const query = new URLSearchParams({ scope_type: selectedSenderScope });
      if (selectedSenderScope === 'business' && businessId) query.set('business_id', businessId);
      const payload = await newAuth.makeRequest(`/outreach/sender-accounts?${query.toString()}`);
      setSenderAccounts(Array.isArray(payload?.sender_accounts) ? payload.sender_accounts : []);
    } catch {
      setSenderAccounts([]);
    } finally {
      setSenderAccountsLoading(false);
    }
  }, [selectedSenderScope, selectedWorkstream?.client_business_id]);
  const connectedEmailSender = senderAccounts.find((account) => (
    account.channel === 'email' && account.status === 'connected'
  )) || null;
  const connectedEmailReady = Boolean(
    connectedEmailSender?.outreach_enabled
    && !['blocked', 'paused', 'degraded'].includes(String(connectedEmailSender.health_status || '')),
  );
  const drawerContacts = (contactIntelligence?.contacts || selectedWorkstream?.contact_points || [])
    .filter((item) => item.type !== 'website');
  const drawerTelegramSources = contactIntelligence?.telegram_sources || [];
  const drawerRecipient = contactIntelligence?.selected_recipient || selectedWorkstream?.selected_recipient || null;
  const savedOperatorReason = String(
    selectedWorkstream?.research?.message_brief?.operator_approved_reason || '',
  ).trim();
  const preparationSteps = selectedWorkstream?.research?.message_brief?.preparation_steps || {};
  const reasonPreparationStep: PreparationStep | undefined = preparationSteps.reason || (
    selectedWorkstream?.research?.message_brief?.operator_approved_at
      ? {
        status: 'completed',
        label: 'Идея подтверждена вручную',
        completed_at: selectedWorkstream.research.message_brief.operator_approved_at,
      }
      : undefined
  );
  const readyChannelCount = Object.values(outreachPreview?.channel_availability || {})
    .filter((item) => item.status === 'ready').length;
  const senderProfileChecklist = contactIntelligence?.sender_profile_completeness;
  const savedCampaignFirstScheduledAt = (savedOutreachCampaign?.touches || [])
    .map((touch) => touch.scheduled_at)
    .filter((value): value is string => Boolean(value))
    .sort((left, right) => new Date(left).getTime() - new Date(right).getTime())[0];
  const savedCampaignDisplayTouches: OutreachTouchPreview[] = (savedOutreachCampaign?.touches || [])
    .filter((touch) => Boolean(touch.generated_text || touch.approved_text))
    .sort((left, right) => Number(left.sequence_index || 0) - Number(right.sequence_index || 0))
    .map((touch) => {
      const scheduledAt = touch.scheduled_at ? new Date(touch.scheduled_at).getTime() : Number.NaN;
      const firstScheduledAt = savedCampaignFirstScheduledAt ? new Date(savedCampaignFirstScheduledAt).getTime() : Number.NaN;
      const calculatedDayOffset = Number.isFinite(scheduledAt) && Number.isFinite(firstScheduledAt)
        ? Math.max(0, Math.round((scheduledAt - firstScheduledAt) / 86_400_000))
        : Number(touch.sequence_index || 0) * 3;
      return {
        id: touch.id,
        sequence_index: Number(touch.sequence_index || 0),
        channel: String(touch.channel || 'manual'),
        contact_point_id: touch.contact_point_id,
        day_offset: calculatedDayOffset,
        angle: String(touch.angle_type || ''),
        subject: touch.subject,
        text: String(touch.approved_text || touch.generated_text || ''),
        channel_status: touch.channel_status || touch.message_brief_json?.channel_status || 'manual',
        quality_gate: touch.quality_gate_json,
        evidence_kind: touch.message_brief_json?.evidence_kind,
        source_url: touch.message_brief_json?.source_url,
        observation: touch.message_brief_json?.observation,
        problem_hypothesis: touch.message_brief_json?.problem_hypothesis,
        pain_hypothesis: touch.message_brief_json?.pain_hypothesis,
        pain_reference_ids: touch.message_brief_json?.pain_reference_ids,
        solution: touch.message_brief_json?.solution,
        language_support: touch.message_brief_json?.language_support,
        pain_support: touch.message_brief_json?.pain_support,
        relevance_bridge: touch.message_brief_json?.relevance_bridge,
        scheduled_at: touch.scheduled_at,
        human_edited: Boolean(touch.message_brief_json?.human_edited),
      };
    });
  const displayedOutreachTouches = (outreachPreview?.touches || []).length > 0
    ? outreachPreview?.touches || []
    : savedCampaignDisplayTouches;
  const chainTouchesByContactId = new Map<string, OutreachTouchPreview[]>();
  displayedOutreachTouches.forEach((touch) => {
    const contactPointId = String(touch.contact_point_id || '');
    if (!contactPointId) return;
    chainTouchesByContactId.set(contactPointId, [
      ...(chainTouchesByContactId.get(contactPointId) || []),
      touch,
    ]);
  });
  const hasTouchEdits = Object.entries(touchEdits).some(([rawIndex, draft]) => {
    const touchIndex = Number(rawIndex);
    const persistedTouch = (savedOutreachCampaign?.touches || []).find(
      (touch) => Number(touch.sequence_index || 0) === touchIndex,
    );
    if (!persistedTouch) return draft.humanEdited;
    const persistedSubject = String(persistedTouch.subject || '').trim();
    const persistedText = String(persistedTouch.approved_text || persistedTouch.generated_text || '').trim();
    return draft.subject.trim() !== persistedSubject || draft.text.trim() !== persistedText;
  });
  const savedCampaignHasHumanEdits = (savedOutreachCampaign?.touches || []).some(
    (touch) => Boolean(touch.message_brief_json?.human_edited),
  );
  const savedCampaignHasPendingReview = (savedOutreachCampaign?.touches || []).some(
    (touch) => Boolean(touch.message_brief_json?.manual_edit_review_required),
  );
  const savedCampaignQualityPassed = Boolean(
    (savedOutreachCampaign?.touches || []).length
    && (savedOutreachCampaign?.touches || []).every((touch) => Boolean(touch.quality_gate_json?.passed)),
  );
  const outreachTouchEditsStorageKey = useMemo(() => {
    const workstreamId = String(selectedWorkstream?.id || '');
    const campaignId = String(savedOutreachCampaign?.id || '');
    const campaignVersion = Number(savedOutreachCampaign?.version || 0);
    if (!workstreamId || !campaignId || !campaignVersion) return '';
    return `localos:outreach-touch-edits:${workstreamId}:${campaignId}:${campaignVersion}`;
  }, [savedOutreachCampaign?.id, savedOutreachCampaign?.version, selectedWorkstream?.id]);
  const outreachCampaignSetupStorageKey = useMemo(() => {
    const workstreamId = String(selectedWorkstream?.id || '');
    return workstreamId ? `localos:outreach-campaign-setup:${workstreamId}` : '';
  }, [selectedWorkstream?.id]);
  const persistOutreachCampaignSetup = (changes: Partial<OutreachCampaignSetupDraft>) => {
    if (!outreachCampaignSetupStorageKey || !selectedWorkstream?.id) return;
    const draft: OutreachCampaignSetupDraft = {
      workstreamId: String(selectedWorkstream.id),
      baseCampaignId: String(savedOutreachCampaign?.id || ''),
      baseCampaignVersion: Number(savedOutreachCampaign?.version || 0),
      sequenceChannels: changes.sequenceChannels || sequenceChannels,
      sequenceDays: changes.sequenceDays || sequenceDays,
      sequenceStartAt: changes.sequenceStartAt ?? sequenceStartAt,
      sequenceSenders: changes.sequenceSenders || sequenceSenders,
      senderMode: changes.senderMode || senderMode,
    };
    localStorage.setItem(outreachCampaignSetupStorageKey, JSON.stringify(draft));
  };
  const outreachCalendarTouches = (outreachPreview?.touches || []).length > 0
    ? outreachPreview?.touches || []
    : campaignSetupDirty
      ? buildProjectedOutreachTouches(sequenceChannels, sequenceDays, sequenceStartAt)
      : savedCampaignDisplayTouches.length > 0
        ? savedCampaignDisplayTouches
        : buildProjectedOutreachTouches(sequenceChannels, sequenceDays, sequenceStartAt);
  const savedConversationTouches = [...(savedOutreachCampaign?.touches || [])]
    .sort((left, right) => Number(left.sequence_index || 0) - Number(right.sequence_index || 0));
  const humanReplyEvents = (savedOutreachCampaign?.inbound_events || [])
    .filter((event) => Boolean(event.is_human))
    .sort((left, right) => {
      const leftAt = new Date(left.occurred_at || left.created_at || 0).getTime();
      const rightAt = new Date(right.occurred_at || right.created_at || 0).getTime();
      return leftAt - rightAt;
    });
  const deliveryByTouchId = new Map<string, OutreachDelivery>();
  (savedOutreachCampaign?.deliveries || []).forEach((delivery) => {
    if (delivery.touch_id) deliveryByTouchId.set(delivery.touch_id, delivery);
  });
  const conversationChannelCodes = Array.from(new Set([
    ...savedConversationTouches.map((touch) => String(touch.channel || '')).filter(Boolean),
    ...drawerContacts.map((contact) => String(contact.type || '')).filter(Boolean),
    String(selectedWorkstream?.selected_channel || ''),
  ])).filter(Boolean);
  const conversationChannels = conversationChannelCodes.map((channel) => {
    const recipientContactType = recipientContactTypeForChannel(channel);
    const contacts = drawerContacts.filter((contact) => String(contact.type || '') === recipientContactType);
    const touches = savedConversationTouches.filter((touch) => String(touch.channel || '') === channel);
    const latestTouch = touches[touches.length - 1];
    const latestDelivery = latestTouch?.id ? deliveryByTouchId.get(latestTouch.id) : undefined;
    const replyReceived = humanReplyEvents.some((event) => String(event.channel || '') === channel);
    const status = replyReceived
      ? 'reply'
      : String(latestDelivery?.delivery_status || latestTouch?.status || (contacts.length ? 'contact_ready' : 'recipient_missing'));
    const preferredContact = contacts.find((contact) => contact.id === drawerRecipient?.id) || contacts[0];
    return {
      channel,
      label: contactTypeLabels[channel] || (channel === 'manual' ? 'Ручной канал' : channel),
      contact: preferredContact?.value || '',
      status,
      touchCount: touches.length,
    };
  });
  const unlinkedReplyEvents = humanReplyEvents.filter((event) => (
    !event.touch_id || !savedConversationTouches.some((touch) => touch.id === event.touch_id)
  ));
  const sequenceAngleLabels = selectedWorkstream?.workstream_type === 'client_partnership'
    ? ['Почему пишем', 'Идея сотрудничества', 'Полезный формат', 'Завершение']
    : ['Сигнал', 'Опыт основателя', 'Кейс или материал', 'Завершение'];
  const latestCampaignFirstTouch = (savedOutreachCampaign?.touches || [])
    .find((touch) => Number(touch.sequence_index || 0) === 0);
  const projectedCampaignTouches = buildProjectedOutreachTouches(
    sequenceChannels,
    sequenceDays,
    sequenceStartAt,
  ).map((touch) => {
    const contactType = recipientContactTypeForChannel(String(touch.channel || ''));
    const selectedContact = drawerRecipient?.type === contactType
      ? drawerRecipient
      : drawerContacts.find((contact) => String(contact.type || '') === contactType);
    const channel = String(touch.channel || '');
    const channelStatus = automaticOutreachChannels.has(channel) ? '' : 'manual';
    return {
      ...touch,
      contact_point_id: selectedContact?.id || null,
      sender_account_id: sequenceSenders[Number(touch.sequence_index || 0)] || null,
      channel_status: channelStatus,
      message_brief_json: { channel_status: channelStatus },
    };
  });
  const savedCampaignChannelBlockers: ChannelSetupBlocker[] = [];
  const campaignTouchesForChannelValidation = campaignSetupDirty ? projectedCampaignTouches : savedOutreachCampaign?.touches || [];
  for (const touch of campaignTouchesForChannelValidation) {
    const channel = String(touch.channel || '');
    const channelStatus = String(touch.channel_status || touch.message_brief_json?.channel_status || '');
    const touchNumber = Number(touch.sequence_index || 0) + 1;
    const selectedSenderId = campaignSetupDirty
      ? sequenceSenders[touchNumber - 1] || ''
      : touch.sender_account_id || '';
    const selectedSender = senderAccounts.find((account) => account.id === selectedSenderId)
      || (channel === 'email' ? connectedEmailSender : undefined);
    const channelLabel = contactTypeLabels[channel] || channel.toUpperCase();
    if (['telegram', 'email', 'vk'].includes(channel)) {
      if (touch.contact_point_id && outreachSenderReady(selectedSender)) continue;
      if (channel === 'vk' && channelStatus === 'permission_required') {
        savedCampaignChannelBlockers.push({
          key: `${touchNumber}-${channel}`,
          label: `Касание ${touchNumber} · VK: VK подключён, но отправка запрещена`,
          actionLabel: 'Разрешить отправку в VK',
          target: 'sender-settings',
          actionHref: `/dashboard/settings/integrations?focus=outreach_vk&sender_scope=${selectedSenderScope}&return_to=${encodeURIComponent(`/dashboard/bazich?lead=${selectedLead?.id || ''}&workstream=${selectedWorkstream?.id || ''}`)}`,
        });
        continue;
      }
      if (!selectedSenderId) {
        savedCampaignChannelBlockers.push({
          key: `${touchNumber}-${channel}`,
          label: `Касание ${touchNumber} · ${channelLabel}: выберите отправителя`,
          actionLabel: `Выбрать отправителя для касания ${touchNumber}`,
          target: 'outreach-sequence',
          focusTarget: `touch-sender-${touchNumber - 1}`,
        });
        continue;
      }
      savedCampaignChannelBlockers.push({
        key: `${touchNumber}-${channel}`,
        label: `Касание ${touchNumber} · ${channelLabel}: канал пока не готов`,
        actionLabel: `Настроить ${channelLabel}`,
        target: 'sender-settings',
      });
      continue;
    }
    if (channelStatus !== 'manual') {
      savedCampaignChannelBlockers.push({
        key: `${touchNumber}-${channel}`,
        label: `Касание ${touchNumber} · ${channelLabel}: настройте ручную отправку`,
        actionLabel: `Проверить касание ${touchNumber}`,
        target: 'outreach-sequence',
      });
    }
  }
  const savedCampaignNeedsChannelSetup = savedCampaignChannelBlockers.length > 0;
  const pilotAlreadySent = (savedOutreachCampaign?.touches || []).some((touch) => (
    ['manual_sent', 'sent', 'delivered'].includes(String(touch.status || ''))
  ));
  const pilotReplyReceived = savedOutreachCampaign?.stop_reason === 'recipient_replied';
  const canSyncPilotReply = Boolean(
    latestCampaignFirstTouch
    && ['telegram', 'email', 'vk'].includes(String(latestCampaignFirstTouch.channel || ''))
    && pilotAlreadySent
    && !pilotReplyReceived,
  );
  const campaignStatusItems = savedConversationTouches.map((touch) => {
    const delivery = touch.id ? deliveryByTouchId.get(touch.id) : undefined;
    const channel = String(touch.channel || 'manual');
    const rawStatus = String(delivery?.delivery_status || touch.status || 'draft');
    const replyReceived = humanReplyEvents.some((event) => event.touch_id === touch.id);
    const status = replyReceived
      ? 'reply'
      : !automaticOutreachChannels.has(channel)
          && !['manual_sent', 'sent', 'delivered'].includes(rawStatus)
          && !['needs_attention', 'manual_expired'].includes(rawStatus)
        ? 'awaiting_manual_send'
        : ['approved', 'queued', 'scheduled'].includes(rawStatus)
          ? 'scheduled'
          : rawStatus;
    const contact = drawerContacts.find((item) => item.id === touch.contact_point_id)
      || drawerContacts.find((item) => String(item.type || '') === recipientContactTypeForChannel(channel));
    const sender = senderAccounts.find((account) => account.id === touch.sender_account_id)
      || (channel === 'email' ? connectedEmailSender : undefined);
    let verificationHref = '';
    let verificationLabelText = '';
    if (channel === 'email' && contact?.value) {
      const search = `in:sent to:${contact.value}`;
      const authUser = sender?.sender_identity ? `?authuser=${encodeURIComponent(sender.sender_identity)}` : '';
      verificationHref = `https://mail.google.com/mail/u/${authUser}#search/${encodeURIComponent(search)}`;
      verificationLabelText = 'Открыть отправленные';
    } else if (/^https?:\/\//i.test(String(contact?.value || ''))) {
      verificationHref = String(contact?.value || '');
      verificationLabelText = 'Открыть канал';
    }
    return {
      id: touch.id || `${touch.sequence_index}-${channel}`,
      sequenceIndex: Number(touch.sequence_index || 0),
      channel,
      channelLabel: contactTypeLabels[channel] || (channel === 'manual' ? 'Ручной канал' : channel.toUpperCase()),
      status,
      statusLabel: outreachTouchStatusLabels[status] || status,
      moment: formatOutreachMoment(delivery?.sent_at || delivery?.scheduled_at || touch.scheduled_at),
      sent: ['sent', 'delivered', 'manual_sent', 'reply'].includes(status),
      verificationHref,
      verificationLabel: verificationLabelText,
      providerMessageId: delivery?.provider_message_id || '',
      errorText: delivery?.error_text || '',
    };
  });
  const campaignNeedsAttention = campaignStatusItems.some((item) => (
    ['failed', 'dlq', 'retry', 'needs_attention', 'manual_expired'].includes(item.status)
  ));
  const nextCampaignTouch = campaignStatusItems.find((item) => ['scheduled', 'awaiting_manual_send'].includes(item.status));
  const campaignStatusLabel = pilotReplyReceived
    ? 'Ответ получен'
    : campaignNeedsAttention
      ? 'Нужно внимание'
      : savedOutreachCampaign?.status === 'approved'
        ? pilotAlreadySent ? 'В работе' : 'Запланировано'
        : savedOutreachCampaign?.status === 'draft'
          ? 'Черновик'
          : 'Не настроено';
  const campaignStatusDescription = savedOutreachCampaign
    ? `${campaignStatusItems.length} касания${nextCampaignTouch ? ` · следующее: ${nextCampaignTouch.channelLabel}${nextCampaignTouch.moment ? ` · ${nextCampaignTouch.moment}` : ''}` : ''}`
    : 'Сначала сохраните и подтвердите цепочку';

  const summaryFirstTouch = outreachCalendarTouches[0] || null;
  const summaryFirstTouchMoment = formatOutreachMoment(summaryFirstTouch?.scheduled_at);
  const summaryStatus = campaignSetupDirty
    ? 'Есть несохранённые настройки'
    : savedOutreachCampaign?.status === 'approved' && pilotReplyReceived
      ? `Версия ${Number(savedOutreachCampaign.version || 0)} · ответ получен`
      : savedOutreachCampaign?.status === 'approved' && pilotAlreadySent
        ? `Версия ${Number(savedOutreachCampaign.version || 0)} · кампания запущена, первое письмо отправлено`
        : savedOutreachCampaign?.status === 'approved'
          ? `Версия ${Number(savedOutreachCampaign.version || 0)} · подтверждена, отправка по графику`
          : savedOutreachCampaign
            ? `Версия ${Number(savedOutreachCampaign.version || 0)} · черновик`
            : 'Цепочка не сохранена';
  const summaryNextAction: { label: string; target: string; focusTarget?: string; href?: string } = !drawerRecipient
    ? { label: 'Выбрать получателя', target: 'lead-contacts' }
    : !connectedEmailSender
      ? { label: 'Подключить email', target: 'sender-settings' }
      : !connectedEmailReady
        ? { label: 'Разрешить отправку', target: 'sender-settings' }
        : savedOutreachCampaign?.requires_regeneration && savedCampaignHasHumanEdits
          ? { label: 'Проверить сохранённые сообщения', target: 'lead-conversation' }
          : savedOutreachCampaign?.requires_regeneration
            ? { label: 'Подготовить новую цепочку', target: 'outreach-sequence' }
          : campaignSetupDirty
            ? { label: 'Проверить и сохранить', target: 'outreach-sequence' }
            : pilotReplyReceived
              ? { label: 'Посмотреть ответ', target: 'lead-conversation' }
              : pilotAlreadySent
                ? { label: 'Проверить статус кампании', target: 'campaign-status' }
            : savedCampaignHasPendingReview || !savedCampaignQualityPassed
              ? { label: 'Проверить сообщения', target: 'lead-conversation' }
              : savedCampaignNeedsChannelSetup
                ? {
                    label: savedCampaignChannelBlockers[0].actionLabel,
                    target: savedCampaignChannelBlockers[0].target,
                    focusTarget: savedCampaignChannelBlockers[0].focusTarget,
                    href: savedCampaignChannelBlockers[0].actionHref,
                  }
                : savedOutreachCampaign?.status === 'draft'
                  ? { label: 'Утвердить цепочку', target: 'outreach-sequence' }
                  : { label: 'Проверить статус кампании', target: 'campaign-status' };
  const scrollToLeadSection = (target: string, focusTarget?: string) => {
    const section = document.getElementById(target);
    const toggle = section?.querySelector(`[aria-controls="${target}-content"]`);
    if (toggle instanceof HTMLButtonElement && toggle.getAttribute('aria-expanded') !== 'true') {
      toggle.click();
    }
    window.requestAnimationFrame(() => {
      const focusElement = focusTarget ? document.getElementById(focusTarget) : null;
      (focusElement || section)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      if (focusElement instanceof HTMLSelectElement) focusElement.focus({ preventScroll: true });
    });
  };

  useEffect(() => {
    if (!selectedLead) return;
    if (selectedWorkstreamId && selectedLead.workstreams?.some((item) => item.id === selectedWorkstreamId)) return;
    setSelectedWorkstreamId(selectedLead.workstreams?.[0]?.id || null);
  }, [selectedLead, selectedWorkstreamId]);

  useEffect(() => {
    void loadSenderAccounts();
  }, [loadSenderAccounts]);

  useEffect(() => {
    if (senderAccountsLoading || !selectedWorkstream?.id) return;
    const additions: Record<number, string> = {};
    sequenceChannels.forEach((channel, index) => {
      if (!automaticOutreachChannels.has(channel) || sequenceSenders[index]) return;
      const readyAccounts = senderAccounts.filter((account) => (
        account.channel === channel && outreachSenderReady(account)
      ));
      if (readyAccounts.length === 1) additions[index] = readyAccounts[0].id;
    });
    const addedIndexes = Object.keys(additions).map(Number);
    if (addedIndexes.length === 0) return;
    const nextSenders = { ...sequenceSenders, ...additions };
    setSequenceSenders(nextSenders);
    if (savedOutreachCampaign) {
      persistOutreachCampaignSetup({ sequenceSenders: nextSenders });
      const steps = addedIndexes.map((index) => index + 1).join(', ');
      setCampaignSetupDirty(true);
      setOutreachPreview(null);
      setNotice(`LocalOS выбрал единственный готовый аккаунт для касаний ${steps}. Проверьте и сохраните изменения.`);
    }
  }, [savedOutreachCampaign?.id, selectedWorkstream?.id, senderAccounts, senderAccountsLoading, sequenceChannels, sequenceSenders]);

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
          `/admin/prospecting/leads/${selectedLead.id}/contact-intelligence?workstream_id=${encodeURIComponent(selectedWorkstream.id || '')}&sender_mode=${encodeURIComponent(senderMode)}`,
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
  }, [selectedLead?.id, selectedWorkstream?.id, senderMode, contactIntelligence?.job?.id]);

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
      setSenderOffer(senderProfileFactLines(profile.allowed_offers_json));
      setSenderForbidden(senderProfileFactLines(profile.forbidden_claims_json));
      setSenderVoiceExample(senderProfileFactLines(profile.voice_examples_json));
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
    setSenderCompany(usesPlatformSender
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
  }, [contactIntelligence?.sender_profile?.id, contactIntelligence?.sender_profile_suggestions, selectedWorkstream?.id, usesPlatformSender]);

  useEffect(() => {
    setOutreachPreview(null);
    setSavedOutreachCampaign(null);
    setSenderFactsOpen(false);
    setSequenceChannels(['telegram', 'email', 'max', 'vk']);
    setSequenceDays([0, 3, 7, 12]);
    setSequenceStartAt(defaultOutreachStartValue());
    setSequenceSenders({});
    setTouchEdits({});
    setEditingTouchIndex(null);
    setTouchEditsValidated(false);
    setCampaignSetupDirty(false);
    setSenderMode(
      selectedWorkstream?.workstream_type === 'localos_sales'
        ? 'localos'
        : 'partner_business',
    );
    setManualContactOpen(false);
    setVkHandoffContact(false);
    setManualContactValue('');
    setManualContactError('');
    setManualOutreachReason(String(
      selectedWorkstream?.research?.message_brief?.operator_approved_reason || '',
    ));
    setDataPreparationMessage('');
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
        const latestTouches = [...(latestCampaign?.touches || [])]
          .sort((left, right) => Number(left.sequence_index || 0) - Number(right.sequence_index || 0));
        let restoredCampaignSetup = false;
        if (latestTouches.length > 0) {
          const nextChannels = ['telegram', 'email', 'max', 'vk'];
          const nextDays = [0, 3, 7, 12];
          const nextSenders: Record<number, string> = {};
          const firstScheduledAt = latestTouches
            .map((touch) => touch.scheduled_at)
            .filter((value): value is string => Boolean(value))
            .sort((left, right) => new Date(left).getTime() - new Date(right).getTime())[0];
          const firstScheduledTimestamp = firstScheduledAt
            ? new Date(firstScheduledAt).getTime()
            : Number.NaN;

          latestTouches.forEach((touch, position) => {
            const sequenceIndex = Number.isInteger(Number(touch.sequence_index))
              ? Number(touch.sequence_index)
              : position;
            if (sequenceIndex < 0 || sequenceIndex >= nextChannels.length) return;
            nextChannels[sequenceIndex] = String(touch.channel || nextChannels[sequenceIndex]);
            if (touch.sender_account_id) nextSenders[sequenceIndex] = touch.sender_account_id;
            const scheduledTimestamp = touch.scheduled_at
              ? new Date(touch.scheduled_at).getTime()
              : Number.NaN;
            if (Number.isFinite(firstScheduledTimestamp) && Number.isFinite(scheduledTimestamp)) {
              nextDays[sequenceIndex] = Math.max(
                0,
                Math.round((scheduledTimestamp - firstScheduledTimestamp) / 86_400_000),
              );
            }
          });

          setSequenceChannels(nextChannels);
          setSequenceDays(nextDays);
          setSequenceStartAt(outreachLocalDateTimeValue(firstScheduledAt));
          setSequenceSenders(nextSenders);
        }
        if (outreachCampaignSetupStorageKey) {
          try {
            const storedValue = localStorage.getItem(outreachCampaignSetupStorageKey);
            const parsedValue = storedValue ? JSON.parse(storedValue) : null;
            const expectedCampaignId = String(latestCampaign?.id || '');
            const expectedCampaignVersion = Number(latestCampaign?.version || 0);
            const sameBaseCampaign = Boolean(
              parsedValue
              && parsedValue.workstreamId === workstreamId
              && String(parsedValue.baseCampaignId || '') === expectedCampaignId
              && Number(parsedValue.baseCampaignVersion || 0) === expectedCampaignVersion,
            );
            const validChannels = sameBaseCampaign
              && Array.isArray(parsedValue.sequenceChannels)
              && parsedValue.sequenceChannels.length === 4
              && parsedValue.sequenceChannels.every((channel: unknown) => typeof channel === 'string');
            const validDays = sameBaseCampaign
              && Array.isArray(parsedValue.sequenceDays)
              && parsedValue.sequenceDays.length === 4
              && parsedValue.sequenceDays.every((day: unknown) => Number.isFinite(Number(day)));
            const validStartAt = sameBaseCampaign && typeof parsedValue.sequenceStartAt === 'string';
            const validSenders = sameBaseCampaign
              && parsedValue.sequenceSenders
              && typeof parsedValue.sequenceSenders === 'object'
              && !Array.isArray(parsedValue.sequenceSenders);
            const validSenderMode = ['localos', 'partner_business', 'localos_for_partner']
              .includes(String(parsedValue?.senderMode || ''));
            if (validChannels && validDays && validStartAt && validSenders && validSenderMode) {
              const restoredSenders: Record<number, string> = {};
              Object.entries(parsedValue.sequenceSenders).forEach(([rawIndex, rawSenderId]) => {
                const senderIndex = Number(rawIndex);
                if (Number.isInteger(senderIndex) && typeof rawSenderId === 'string') {
                  restoredSenders[senderIndex] = rawSenderId;
                }
              });
              setSequenceChannels(parsedValue.sequenceChannels);
              setSequenceDays(parsedValue.sequenceDays.map((day: unknown) => Number(day)));
              setSequenceStartAt(parsedValue.sequenceStartAt);
              setSequenceSenders(restoredSenders);
              setSenderMode(parsedValue.senderMode);
              restoredCampaignSetup = true;
              setNotice('Восстановили несохранённые каналы, отправителей и расписание. Проверьте и сохраните новую версию цепочки.');
            } else if (storedValue) {
              localStorage.removeItem(outreachCampaignSetupStorageKey);
            }
          } catch {
            localStorage.removeItem(outreachCampaignSetupStorageKey);
          }
        }
        setOutreachPreview(null);
        setCampaignSetupDirty(false);
        if (restoredCampaignSetup) setCampaignSetupDirty(true);
        const savedMode = latestCampaign?.policy_json?.sender_mode;
        if (
          !restoredCampaignSetup
          && (
          savedMode === 'localos'
          || savedMode === 'partner_business'
          || savedMode === 'localos_for_partner'
          )
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
  }, [outreachCampaignSetupStorageKey, selectedWorkstream?.id]);

  useEffect(() => {
    if (!outreachTouchEditsStorageKey) return;
    try {
      const storedValue = localStorage.getItem(outreachTouchEditsStorageKey);
      if (!storedValue) return;
      const parsedValue = JSON.parse(storedValue);
      if (!parsedValue || typeof parsedValue !== 'object' || Array.isArray(parsedValue)) return;
      const restoredEdits: Record<number, OutreachTouchMessageDraft> = {};
      Object.entries(parsedValue).forEach(([rawIndex, rawDraft]) => {
        const touchIndex = Number(rawIndex);
        if (!Number.isInteger(touchIndex) || !rawDraft || typeof rawDraft !== 'object' || Array.isArray(rawDraft)) return;
        const subject = typeof rawDraft.subject === 'string' ? rawDraft.subject : '';
        const text = typeof rawDraft.text === 'string' ? rawDraft.text : '';
        const originalSubject = typeof rawDraft.originalSubject === 'string' ? rawDraft.originalSubject : '';
        const originalText = typeof rawDraft.originalText === 'string' ? rawDraft.originalText : '';
        if (!text.trim()) return;
        const persistedTouch = (savedOutreachCampaign?.touches || []).find(
          (touch) => Number(touch.sequence_index || 0) === touchIndex,
        );
        const persistedSubject = String(persistedTouch?.subject || '').trim();
        const persistedText = String(
          persistedTouch?.approved_text || persistedTouch?.generated_text || '',
        ).trim();
        if (
          persistedTouch
          && subject.trim() === persistedSubject
          && text.trim() === persistedText
        ) return;
        restoredEdits[touchIndex] = {
          subject,
          text,
          originalSubject,
          originalText,
          humanEdited: subject.trim() !== originalSubject || text.trim() !== originalText,
        };
      });
      if (Object.values(restoredEdits).some((draft) => draft.humanEdited)) {
        setTouchEdits(restoredEdits);
        setTouchEditsValidated(false);
        setNotice('Восстановили несохранённые ручные правки. Проверьте их и сохраните новую версию цепочки.');
      } else {
        localStorage.removeItem(outreachTouchEditsStorageKey);
      }
    } catch {
      localStorage.removeItem(outreachTouchEditsStorageKey);
    }
  }, [outreachTouchEditsStorageKey, savedOutreachCampaign?.id, savedOutreachCampaign?.version]);

  useEffect(() => {
    if (!hasTouchEdits) return undefined;
    const warnAboutUnsavedTouchEdits = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = '';
    };
    window.addEventListener('beforeunload', warnAboutUnsavedTouchEdits);
    return () => window.removeEventListener('beforeunload', warnAboutUnsavedTouchEdits);
  }, [hasTouchEdits]);

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

  const saveManualOutreachReason = async () => {
    if (
      !selectedLead
      || !selectedWorkstream?.id
      || selectedWorkstream.workstream_type !== 'client_partnership'
    ) return;
    setBusyAction('outreach-reason');
    setNotice('');
    setDataPreparationMessage('');
    try {
      const result = await newAuth.makeRequest(
        `/admin/prospecting/leads/${selectedLead.id}/outreach-reason`,
        {
          method: 'POST',
          body: JSON.stringify({
            workstream_id: selectedWorkstream.id,
            reason: manualOutreachReason.trim(),
          }),
        },
      );
      setManualOutreachReason(String(result?.reason || manualOutreachReason.trim()));
      setOutreachPreview(null);
      if (savedOutreachCampaign) setCampaignSetupDirty(true);
      setDataPreparationMessage(
        'Причина сохранена и подтверждена человеком. Теперь LocalOS сможет подготовить новую цепочку без общего шаблона.',
      );
      await loadLeads();
    } catch (requestError) {
      setDataPreparationMessage(
        requestError instanceof Error
          ? requestError.message
          : 'Не удалось сохранить причину обращения',
      );
    } finally {
      setBusyAction('');
    }
  };

  const refreshLeadCardData = async () => {
    if (!selectedLead || !selectedWorkstream?.id) return;
    setBusyAction('parse-lead-card');
    setNotice('');
    setDataPreparationMessage('');
    try {
      await newAuth.makeRequest(`/admin/prospecting/lead/${selectedLead.id}/parse`, {
        method: 'POST',
        body: JSON.stringify({ workstream_id: selectedWorkstream.id }),
      });
      setOutreachPreview(null);
      if (savedOutreachCampaign) setCampaignSetupDirty(true);
      setDataPreparationMessage(
        'Обновление карточки запущено. Дождитесь завершения парсинга, затем создайте аудит.',
      );
      await loadLeads();
    } catch (requestError) {
      setDataPreparationMessage(
        requestError instanceof Error
          ? requestError.message
          : 'Не удалось запустить обновление карточки',
      );
    } finally {
      setBusyAction('');
    }
  };

  const createLeadAudit = async () => {
    if (
      !selectedLead
      || !selectedWorkstream?.id
      || selectedWorkstream.workstream_type !== 'client_partnership'
    ) return;
    setBusyAction('audit-lead');
    setNotice('');
    setDataPreparationMessage('');
    try {
      await newAuth.makeRequest(`/partnership/leads/${selectedLead.id}/audit`, {
        method: 'POST',
        body: JSON.stringify({
          business_id: selectedWorkstream.client_business_id,
          workstream_id: selectedWorkstream.id,
        }),
      });
      setOutreachPreview(null);
      if (savedOutreachCampaign) setCampaignSetupDirty(true);
      setDataPreparationMessage(
        'Аудит создан по текущим данным карточки. Следующий шаг — проверить совместимость.',
      );
      await loadLeads();
    } catch (requestError) {
      setDataPreparationMessage(
        requestError instanceof Error
          ? requestError.message
          : 'Не удалось создать аудит',
      );
    } finally {
      setBusyAction('');
    }
  };

  const checkLeadCompatibility = async () => {
    if (
      !selectedLead
      || !selectedWorkstream?.id
      || selectedWorkstream.workstream_type !== 'client_partnership'
    ) return;
    setBusyAction('match-lead');
    setNotice('');
    setDataPreparationMessage('');
    try {
      const result = await newAuth.makeRequest(
        `/partnership/leads/${selectedLead.id}/match`,
        {
          method: 'POST',
          body: JSON.stringify({
            business_id: selectedWorkstream.client_business_id,
            workstream_id: selectedWorkstream.id,
          }),
        },
      );
      setOutreachPreview(null);
      if (savedOutreachCampaign) setCampaignSetupDirty(true);
      setDataPreparationMessage(
        result?.status === 'needs_evidence' && !savedOperatorReason
          ? 'Проверка выполнена, но фактов пока недостаточно. Добавьте конкретную идею сотрудничества или обновите данные карточки.'
          : result?.status === 'needs_evidence' && savedOperatorReason
            ? 'Идея подтверждена вручную. Цепочку можно подготовить. Автоматическая проверка не нашла достаточно публичных данных — это останется видимым ограничением.'
          : 'Совместимость проверена. Теперь можно подготовить цепочку.',
      );
      await loadLeads();
    } catch (requestError) {
      setDataPreparationMessage(
        requestError instanceof Error
          ? requestError.message
          : 'Не удалось проверить совместимость',
      );
    } finally {
      setBusyAction('');
    }
  };

  const saveManualContact = async () => {
    if (!selectedLead || !selectedWorkstream?.id || !manualContactValue.trim()) return;
    setBusyAction('manual-contact');
    setManualContactError('');
    setNotice('');
    try {
      const result = await newAuth.makeRequest(`/admin/prospecting/leads/${selectedLead.id}/contacts`, {
        method: 'POST',
        body: JSON.stringify({
          workstream_id: selectedWorkstream.id,
          contact_type: manualContactType,
          value: manualContactValue,
          telegram_usage: manualTelegramUsage,
          owner_type: manualOwnerType,
          person_name: manualPersonName,
          role_title: manualRoleTitle,
          handoff_from_vk: vkHandoffContact,
        }),
      });
      const refreshed = await newAuth.makeRequest(
        `/admin/prospecting/leads/${selectedLead.id}/contact-intelligence?workstream_id=${encodeURIComponent(selectedWorkstream.id)}&sender_mode=${encodeURIComponent(senderMode)}`,
      );
      setContactIntelligence(refreshed);
      setManualContactValue('');
      setManualPersonName('');
      setManualRoleTitle('');
      setManualContactOpen(false);
      setVkHandoffContact(false);
      setNotice(result?.entry_kind === 'telegram_source'
        ? 'Telegram-канал добавлен в источники сигналов. Радар проверит, что канал публичный.'
        : 'Контакт добавлен вручную. Выберите его получателем, когда будете готовы.');
      await loadLeads();
    } catch (requestError) {
      setManualContactError(requestError instanceof Error ? requestError.message : 'Не удалось сохранить контакт');
    } finally {
      setBusyAction('');
    }
  };

  const selectRecipient = async (contact: ContactPoint) => {
    if (!selectedLead || !selectedWorkstream?.id) return;
    if (drawerRecipient?.id === contact.id) {
      setNotice('Этот контакт уже выбран. Чтобы изменить получателя, выберите другой контакт.');
      return;
    }
    setBusyAction(`recipient-${contact.id}`);
    setNotice('');
    try {
      const selection = await newAuth.makeRequest(`/admin/prospecting/leads/${selectedLead.id}/recipient`, {
        method: 'POST',
        body: JSON.stringify({
          workstream_id: selectedWorkstream.id,
          contact_point_id: contact.id,
        }),
      });
      setContactIntelligence((current) => ({
        ...(current || {}),
        selected_recipient: contact,
        job: selection?.job || current?.job || null,
      }));
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
          sender_mode: senderMode,
          workstream_type: usesPlatformSender ? 'localos_sales' : selectedWorkstream.workstream_type,
          client_business_id: usesPlatformSender ? null : selectedWorkstream.client_business_id,
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

  const updateSequenceChannel = (index: number, channel: string) => {
    const nextChannels = sequenceChannels.map((item, itemIndex) => itemIndex === index ? channel : item);
    const nextSenders = { ...sequenceSenders, [index]: '' };
    setSequenceChannels(nextChannels);
    setSequenceSenders(nextSenders);
    persistOutreachCampaignSetup({ sequenceChannels: nextChannels, sequenceSenders: nextSenders });
    setOutreachPreview(null);
    setCampaignSetupDirty(true);
  };

  const updateSequenceDay = (index: number, day: number) => {
    const nextDays = sequenceDays.map((item, itemIndex) => itemIndex === index ? Math.max(0, day) : item);
    setSequenceDays(nextDays);
    persistOutreachCampaignSetup({ sequenceDays: nextDays });
    setOutreachPreview(null);
    setCampaignSetupDirty(true);
  };

  const updateSequenceSender = (index: number, senderAccountId: string) => {
    const channel = sequenceChannels[index];
    const matchingIndexes = sequenceChannels
      .map((item, itemIndex) => item === channel ? itemIndex : -1)
      .filter((itemIndex) => itemIndex >= 0);
    const nextSenders = { ...sequenceSenders };
    matchingIndexes.forEach((itemIndex) => {
      nextSenders[itemIndex] = senderAccountId;
    });
    setSequenceSenders(nextSenders);
    persistOutreachCampaignSetup({ sequenceSenders: nextSenders });
    setOutreachPreview(null);
    setCampaignSetupDirty(true);
    const steps = matchingIndexes.map((itemIndex) => itemIndex + 1).join(', ');
    setNotice(senderAccountId
      ? `Отправитель выбран для всех касаний ${contactTypeLabels[channel] || channel}: ${steps}. Теперь проверьте и сохраните изменения.`
      : `Выбор отправителя снят с касаний ${steps}.`);
  };

  const updateSenderMode = (mode: SenderMode) => {
    setSenderMode(mode);
    setSequenceSenders({});
    persistOutreachCampaignSetup({ senderMode: mode, sequenceSenders: {} });
    setOutreachPreview(null);
    setCampaignSetupDirty(true);
    setNotice('Способ представления изменён. Подготовьте новый preview и проверьте всю цепочку.');
  };

  const campaignSequence = () => [
    { channel: sequenceChannels[0], day_offset: sequenceDays[0], angle: 'signal', sender_account_id: sequenceSenders[0] || undefined },
    { channel: sequenceChannels[1], day_offset: sequenceDays[1], angle: 'founder_story', sender_account_id: sequenceSenders[1] || undefined },
    { channel: sequenceChannels[2], day_offset: sequenceDays[2], angle: 'proof', sender_account_id: sequenceSenders[2] || undefined },
    { channel: sequenceChannels[3], day_offset: sequenceDays[3], angle: 'respectful_close', sender_account_id: sequenceSenders[3] || undefined },
  ];

  const campaignTouchOverrides = ({ preserveSavedCampaign = false } = {}) => {
    const savedTouchesByIndex = new Map(
      (savedOutreachCampaign?.touches || []).map((touch) => [Number(touch.sequence_index || 0), touch]),
    );
    const touchesToOverride = preserveSavedCampaign
      ? displayedOutreachTouches.filter((touch) => {
          const savedTouch = savedTouchesByIndex.get(touch.sequence_index);
          return Boolean(
            savedTouch?.message_brief_json?.human_edited
            && touch.channel === sequenceChannels[touch.sequence_index],
          );
        })
      : displayedOutreachTouches;
    return touchesToOverride.map((touch) => {
      const draft = touchEdits[touch.sequence_index];
      const savedTouch = savedTouchesByIndex.get(touch.sequence_index);
      const currentText = draft?.text.trim() || outreachTouchMessageText(touch);
      const currentSubject = draft?.subject.trim() || String(touch.subject || '').trim();
      return {
        sequence_index: touch.sequence_index,
        subject: currentSubject,
        text: currentText,
        original_subject: draft?.originalSubject || String(touch.subject || '').trim(),
        original_text: draft?.originalText || outreachTouchMessageText(touch),
        human_edited: Boolean(
          draft?.humanEdited || savedTouch?.message_brief_json?.human_edited,
        ),
      };
    });
  };

  const startTouchEdit = (touch: OutreachTouchPreview) => {
    setTouchEdits((current) => {
      const next = {
        ...current,
        [touch.sequence_index]: current[touch.sequence_index] || outreachTouchMessageDraft(touch),
      };
      if (outreachTouchEditsStorageKey) {
        localStorage.setItem(outreachTouchEditsStorageKey, JSON.stringify(next));
      }
      return next;
    });
    setEditingTouchIndex(touch.sequence_index);
  };

  const resetTouchEdit = (touchIndex: number) => {
    setTouchEdits((current) => {
      const next = { ...current };
      delete next[touchIndex];
      if (outreachTouchEditsStorageKey) {
        if (Object.keys(next).length > 0) {
          localStorage.setItem(outreachTouchEditsStorageKey, JSON.stringify(next));
        } else {
          localStorage.removeItem(outreachTouchEditsStorageKey);
        }
      }
      return next;
    });
    setEditingTouchIndex((current) => current === touchIndex ? null : current);
    setTouchEditsValidated(false);
    setOutreachPreview(null);
  };

  const acceptTouchEdit = async (touchIndex: number, draft: OutreachTouchMessageDraft) => {
    const campaignId = String(savedOutreachCampaign?.id || '');
    const campaignTouch = (savedOutreachCampaign?.touches || []).find(
      (touch) => Number(touch.sequence_index || 0) === touchIndex,
    );
    const touchId = String(campaignTouch?.id || '');
    if (!campaignId || !touchId) {
      setNotice('Сначала сохраните цепочку как черновик — после этого отдельные сообщения можно менять без новой версии.');
      return;
    }
    const busyKey = `accept-touch-${touchIndex}`;
    setBusyAction(busyKey);
    setNotice('');
    try {
      const payload = await newAuth.makeRequest(
        `/outreach/campaigns/${encodeURIComponent(campaignId)}/touches/${encodeURIComponent(touchId)}`,
        {
          method: 'PATCH',
          body: JSON.stringify({
            subject: draft.subject.trim(),
            text: draft.text.trim(),
          }),
        },
      );
      if (payload?.campaign) {
        setSavedOutreachCampaign(payload.campaign);
      } else {
        await reloadLatestOutreachCampaign();
      }
      setTouchEdits((current) => {
        const next = { ...current };
        delete next[touchIndex];
        if (outreachTouchEditsStorageKey) {
          if (Object.keys(next).length > 0) {
            localStorage.setItem(outreachTouchEditsStorageKey, JSON.stringify(next));
          } else {
            localStorage.removeItem(outreachTouchEditsStorageKey);
          }
        }
        return next;
      });
      setEditingTouchIndex(null);
      setOutreachPreview(null);
      setTouchEditsValidated(false);
      setNotice(`Изменения сохранены в версии ${Number(payload?.touch?.campaign_version || savedOutreachCampaign?.version || 1)}. Теперь проверьте сохранённые сообщения — новая версия цепочки не нужна.`);
    } catch (requestError) {
      setNotice(requestError instanceof Error ? requestError.message : 'Не удалось сохранить изменения сообщения');
    } finally {
      setBusyAction('');
    }
  };

  const reloadLatestOutreachCampaign = async () => {
    const workstreamId = String(selectedWorkstream?.id || '');
    if (!workstreamId) return;
    const payload = await newAuth.makeRequest(`/outreach/workstreams/${encodeURIComponent(workstreamId)}/campaigns`);
    const campaigns = Array.isArray(payload?.campaigns) ? payload.campaigns : [];
    setSavedOutreachCampaign(campaigns[0] || null);
  };

  const reviewSavedTouchEdits = async () => {
    const campaignId = String(savedOutreachCampaign?.id || '');
    if (!campaignId) return;
    if (hasTouchEdits) {
      setNotice('Сначала сохраните каждое изменённое сообщение кнопкой «Принять изменения».');
      return;
    }
    setBusyAction('review-saved-edits');
    setNotice('');
    try {
      const payload = await newAuth.makeRequest(
        `/outreach/campaigns/${encodeURIComponent(campaignId)}/review-edits`,
        { method: 'POST' },
      );
      setOutreachPreview(payload?.preview || null);
      if (payload?.campaign) setSavedOutreachCampaign(payload.campaign);
      setTouchEditsValidated(Boolean(payload?.review?.all_passed));
      setNotice(payload?.review?.all_passed
        ? `Все ${Number(payload?.review?.reviewed_touch_count || 0)} сообщения проверены. Версия ${Number(payload?.review?.campaign_version || savedOutreachCampaign?.version || 1)} готова к подтверждению.`
        : 'Проверка завершена. Исправьте сообщения с замечаниями и снова нажмите «Проверить сохранённые сообщения».');
    } catch (requestError) {
      setNotice(requestError instanceof Error ? requestError.message : 'Не удалось проверить сохранённые сообщения');
    } finally {
      setBusyAction('');
    }
  };

  const prepareOutreachCampaign = async (save: boolean) => {
    if (!selectedWorkstream?.id) return;
    const scheduleStart = outreachStartIso(sequenceStartAt);
    if (!scheduleStart) {
      setNotice('Выберите корректные дату и время первого касания.');
      return;
    }
    setBusyAction(save ? 'save-campaign' : 'preview-campaign');
    setNotice('');
    try {
      const payload = await newAuth.makeRequest(`/outreach/workstreams/${encodeURIComponent(selectedWorkstream.id)}/preview`, {
        method: 'POST',
        body: JSON.stringify({
          sequence: campaignSequence(),
          touch_overrides: hasTouchEdits
            ? campaignTouchOverrides()
            : campaignSetupDirty
              ? campaignTouchOverrides({ preserveSavedCampaign: true })
              : undefined,
          start_at: scheduleStart,
          save,
          sender_mode: senderMode,
        }),
      });
      const preparedPreview = payload?.preview || null;
      const preparedTouchCount = Array.isArray(preparedPreview?.touches) ? preparedPreview.touches.length : 0;
      setOutreachPreview(preparedPreview);
      setTouchEditsValidated(hasTouchEdits);
      if (!save) {
        setNotice(preparedTouchCount > 0
          ? `Цепочка подготовлена: ${preparedTouchCount} касания. Проверьте сообщения и сохраните цепочку.`
          : 'Цепочка пока не создана. LocalOS показал ниже причину и следующий шаг.');
        window.requestAnimationFrame(() => {
          document.getElementById('outreach-preview-result')?.scrollIntoView({ behavior: 'smooth', block: 'center' });
        });
      }
      if (payload?.campaign) {
        setSavedOutreachCampaign(payload.campaign);
        setCampaignSetupDirty(false);
        if (outreachCampaignSetupStorageKey) localStorage.removeItem(outreachCampaignSetupStorageKey);
        if (outreachTouchEditsStorageKey) localStorage.removeItem(outreachTouchEditsStorageKey);
        setTouchEdits({});
        setEditingTouchIndex(null);
        setTouchEditsValidated(false);
        setNotice('Тексты, каналы и расписание сохранены. Ничего не отправлено. Теперь можно утвердить цепочку для отправки.');
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
    if (campaignSetupDirty) {
      setNotice('Сначала проверьте и сохраните новую версию. Старая цепочка остаётся в истории, но подтвердить её после изменения настроек нельзя.');
      return;
    }
    setBusyAction('approve-campaign');
    setNotice('');
    try {
      const payload = await newAuth.makeRequest(`/outreach/campaigns/${encodeURIComponent(savedOutreachCampaign.id)}/approve`, { method: 'POST' });
      setSavedOutreachCampaign((current) => current ? { ...current, status: payload?.campaign?.status || 'approved' } : current);
      setNotice('Цепочка принята для отправки. LocalOS выполнит автоматические касания по графику, а ручные покажет в состоянии кампании.');
      await reloadLatestOutreachCampaign();
    } catch (requestError) {
      setNotice(requestError instanceof Error ? requestError.message : 'Цепочка не прошла preflight');
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

  const recordManualTouchEvent = async (
    touch: { id: string },
    eventType: 'sent' | 'skipped' | 'reply',
  ) => {
    if (!savedOutreachCampaign?.id || !touch.id) return;
    const note = eventType === 'reply'
      ? window.prompt('Кратко запишите ответ партнёра. Он остановит следующие касания этой цепочки.')
      : '';
    if (eventType === 'reply' && !note?.trim()) return;
    const busyKey = `manual-touch-${touch.id}-${eventType}`;
    setBusyAction(busyKey);
    setNotice('');
    try {
      await newAuth.makeRequest(
        `/outreach/campaigns/${encodeURIComponent(savedOutreachCampaign.id)}/touches/${encodeURIComponent(touch.id)}/manual-event`,
        {
          method: 'POST',
          body: JSON.stringify({ event_type: eventType, note: note?.trim() || '' }),
        },
      );
      setNotice(eventType === 'sent'
        ? 'Ручная отправка отмечена. LocalOS продолжит цепочку по расписанию.'
        : eventType === 'skipped'
          ? 'Касание пропущено.'
          : 'Ответ записан. Следующие касания остановлены.');
      await reloadLatestOutreachCampaign();
    } catch (requestError) {
      setNotice(requestError instanceof Error ? requestError.message : 'Не удалось записать ручное действие');
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
                onClick={() => {
                  setView(item.id);
                  if (item.id === 'messages') {
                    setActionState('');
                    setSignalStrength('');
                    setSelectedSignalKeys([]);
                  }
                }}
                className={`min-h-10 whitespace-nowrap rounded-md px-4 text-sm font-semibold transition-colors active:scale-[0.96] ${
                  view === item.id ? 'bg-slate-950 text-white' : 'text-slate-600 hover:bg-slate-100 hover:text-slate-950'
                }`}
              >
                {item.label}
              </button>
            ))}
          </div>
          {view === 'leads' ? (
            <Button onClick={() => setSearchOpen(true)} className="min-h-11 bg-orange-500 text-white hover:bg-orange-600">
              <Search className="mr-2 h-4 w-4" />
              Найти лидов
            </Button>
          ) : null}
        </div>

        <div className={`mt-4 grid grid-cols-[minmax(0,1fr)] gap-3 ${
          view === 'leads'
            ? 'md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-5'
            : 'lg:grid-cols-[minmax(280px,1fr)_auto_minmax(190px,240px)]'
        }`}>
          <div className="relative min-w-0">
            <Search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-slate-400" />
            <Input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder={view === 'messages' ? 'Компания, получатель или текст сообщения' : 'Компания, категория, город или контакт'}
              className="h-10 pl-9"
            />
          </div>
          <div className="flex min-w-0 gap-1 overflow-x-auto rounded-md bg-slate-100 p-1">
            {scopeOptions.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => {
                  setScope(item.id);
                  if (item.id === 'localos_sales') setClientBusinessId('');
                }}
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
            disabled={scope === 'localos_sales'}
            className="h-10 min-w-0 w-full rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-800"
            aria-label="Фильтр по клиенту"
          >
            <option value="">{scope === 'localos_sales' ? 'Клиент не применяется' : 'Все клиенты'}</option>
            {clientFilterOptions.map((business) => <option key={business.id} value={business.id}>{business.name}</option>)}
          </select>
          {view === 'leads' ? (
            <>
              <select
                value={partnerType}
                onChange={(event) => setPartnerType(event.target.value)}
                className="h-10 min-w-0 w-full rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-800"
                aria-label="Фильтр по категории бизнеса"
              >
                <option value="">Любая категория бизнеса</option>
                {visiblePartnerTypeOptions.map((option) => (
                  <option key={option.id} value={option.id}>{option.label} · {option.count}</option>
                ))}
              </select>
              <select
                value={campaignFilter}
                onChange={(event) => setCampaignFilter(event.target.value)}
                className="h-10 min-w-0 w-full rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-800"
                aria-label="Фильтр по состоянию цепочки"
              >
                <option value="">Любое состояние цепочки</option>
                <option value="with_campaign">Цепочка создана · {campaignFilterCounts.with_campaign}</option>
                <option value="without_campaign">Цепочки нет · {campaignFilterCounts.without_campaign}</option>
                {Object.entries(campaignRegistryStatusLabels).map(([status, label]) => (
                  campaignFilterCounts[status] > 0 || campaignFilter === status
                    ? <option key={status} value={status}>{label} · {campaignFilterCounts[status]}</option>
                    : null
                ))}
              </select>
              <select
                value={actionState}
                onChange={(event) => setActionState(event.target.value)}
                className="h-10 min-w-0 w-full rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-800"
                aria-label="Фильтр по следующему действию"
              >
                <option value="">Любой следующий шаг</option>
                <option value="find_contact">Найти контакт</option>
                <option value="prepare_room">Подготовить комнату</option>
                <option value="review_draft">Проверить черновик</option>
                <option value="review_message">Проверить сообщение</option>
                <option value="check_campaign">Проверить кампанию</option>
                <option value="wait_or_follow_up">Проверить ответ</option>
                <option value="record_result">Зафиксировать результат</option>
              </select>
              <details className="md:col-span-2 xl:col-span-3 2xl:col-span-5">
                <summary className="flex min-h-10 cursor-pointer list-none items-center gap-2 rounded-md px-2 text-sm font-semibold text-slate-600 hover:bg-slate-50 hover:text-slate-950">
                  Дополнительные фильтры
                  {signalStrength || selectedSignalKeys.length ? (
                    <Badge variant="outline" className="tabular-nums">
                      Выбрано: {(signalStrength ? 1 : 0) + selectedSignalKeys.length}
                    </Badge>
                  ) : null}
                </summary>
                <div className="mt-2 grid gap-3 md:grid-cols-2">
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
                  <fieldset className="rounded-md border border-slate-200 bg-white p-3">
                    <legend className="px-1 text-xs font-semibold text-slate-700">Типы сигналов</legend>
                    {signalFilterOptions.length ? (
                      <div className="mt-1 grid gap-2 sm:grid-cols-2">
                        {signalFilterOptions.map((option) => {
                          const checked = selectedSignalKeys.includes(option.key);
                          return (
                            <label
                              key={option.key}
                              className={`flex cursor-pointer items-start gap-2 rounded-md border px-3 py-2 text-sm transition-colors ${
                                checked
                                  ? 'border-orange-300 bg-orange-50 text-slate-950'
                                  : 'border-slate-100 text-slate-700 hover:border-slate-200 hover:bg-slate-50'
                              }`}
                            >
                              <Checkbox
                                checked={checked}
                                onCheckedChange={(value) => {
                                  setSelectedSignalKeys((current) => value
                                    ? [...current, option.key]
                                    : current.filter((key) => key !== option.key));
                                }}
                                aria-label={option.label}
                              />
                              <span className="flex-1 leading-5">{option.label}</span>
                              <span className="tabular-nums text-xs text-slate-500">{option.count}</span>
                            </label>
                          );
                        })}
                      </div>
                    ) : (
                      <p className="mt-1 text-sm text-slate-500">Сигналы появятся после проверки данных лидов.</p>
                    )}
                    {selectedSignalKeys.length ? (
                      <button
                        type="button"
                        onClick={() => setSelectedSignalKeys([])}
                        className="mt-3 text-xs font-semibold text-orange-700 hover:text-orange-800"
                      >
                        Сбросить выбранные сигналы
                      </button>
                    ) : null}
                  </fieldset>
                </div>
              </details>
            </>
          ) : null}
        </div>
      </div>

      {notice && (
        <div className="mx-4 mt-4 flex items-start gap-2 rounded-md bg-emerald-50 px-4 py-3 text-sm text-emerald-800 sm:mx-6">
          <Check className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{notice}</span>
        </div>
      )}

      <div className="px-4 py-3 sm:px-6">
        {view === 'messages' ? (
          <OutreachMessageQueue
            query={query}
            scope={scope}
            businessId={clientBusinessId}
            channel={messageChannel}
            status={messageStatus}
            onChannelChange={setMessageChannel}
            onStatusChange={setMessageStatus}
            onOpenLead={(leadId, workstreamId) => {
              setSelectedLeadId(leadId);
              setSelectedWorkstreamId(workstreamId);
              setNotice('');
            }}
          />
        ) : (
          <>
            {view === 'results' ? (
              <div className="pb-5">
                <OutreachLearningInsights
                  workstreamType={scope === 'client_partnership' ? 'client_partnership' : 'localos_sales'}
                  businessId={scope === 'client_partnership' ? clientBusinessId : null}
                />
              </div>
            ) : null}
            <div className="flex items-center justify-between gap-3 pb-3 text-sm text-slate-500">
              <span className="tabular-nums">
                {loading
                  ? 'Загружаем…'
                  : filteredLeads.length === leads.length
                    ? `${filteredLeads.length} компаний`
                    : `Показано ${filteredLeads.length} из ${leads.length}`}
              </span>
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
              const relevantWorkstreams = workstreamsForRegistry(lead, scope, clientBusinessId);
              const primary = relevantWorkstreams[0] || workstreams[0];
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
                    {primary?.relationship_stage ? (
                      <Badge variant="outline" className="border-emerald-200 bg-emerald-50 text-emerald-800">
                        {primary.relationship_stage.label || 'Подготовка первого касания'}
                      </Badge>
                    ) : (
                      <Badge variant="outline" className="border-slate-200 bg-slate-50 text-slate-600">
                        Цепочки нет
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
          </>
        )}
      </div>

      <Sheet open={Boolean(selectedLead)} onOpenChange={(open) => { if (!open) setSelectedLeadId(null); }}>
        <SheetContent className="w-[96vw] max-w-none overflow-y-auto sm:max-w-6xl">
          <SheetHeader className="pr-8">
            <SheetTitle className="text-wrap-balance text-xl">{selectedLead?.name || 'Карточка лида'}</SheetTitle>
            <SheetDescription>{[selectedLead?.category, selectedLead?.city || selectedLead?.address].filter(Boolean).join(' · ')}</SheetDescription>
            {selectedLeadMapLink ? (
              <a
                href={selectedLeadMapLink.url}
                target="_blank"
                rel="noreferrer"
                className="mt-1 inline-flex min-h-10 w-fit items-center gap-2 rounded-md bg-slate-50 px-3 text-sm font-semibold text-slate-700 shadow-sm shadow-slate-900/5 transition-[box-shadow,color,transform] hover:text-orange-700 hover:shadow-md active:scale-[0.96]"
              >
                <MapPin className="h-4 w-4 text-orange-600" />
                {selectedLeadMapLink.label}
                <ExternalLink className="h-3.5 w-3.5 text-slate-400" />
              </a>
            ) : null}
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
                {selectedWorkstream.relationship_stage?.label ? (
                  <Badge variant="outline" className="border-sky-200 bg-sky-50 text-sky-800">
                    {selectedWorkstream.relationship_stage.label}
                  </Badge>
                ) : null}
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

              <section className="grid gap-3 md:grid-cols-3" aria-label="Организация, контакт и рабочий контекст">
                <div className="rounded-xl bg-slate-50 p-3 shadow-[0_0_0_1px_rgba(15,23,42,0.08)]">
                  <div className="text-xs font-semibold uppercase tracking-[0.08em] text-slate-400">Организация</div>
                  <div className="mt-1 text-sm font-semibold text-slate-950">{selectedLead.name || 'Без названия'}</div>
                  <div className="mt-1 text-xs text-slate-500">{selectedLead.address || selectedLead.city || 'Адрес не указан'}</div>
                </div>
                <div className="rounded-xl bg-slate-50 p-3 shadow-[0_0_0_1px_rgba(15,23,42,0.08)]">
                  <div className="text-xs font-semibold uppercase tracking-[0.08em] text-slate-400">Контакт</div>
                  <div className="mt-1 truncate text-sm font-semibold text-slate-950">{drawerRecipient?.value || 'Не выбран'}</div>
                  <div className="mt-1 text-xs text-slate-500">
                    {drawerRecipient
                      ? [drawerRecipient.person_name, drawerRecipient.role_title].filter(Boolean).join(' · ') || 'Официальный контакт'
                      : 'Нужно найти и проверить'}
                  </div>
                </div>
                <div className="rounded-xl bg-slate-50 p-3 shadow-[0_0_0_1px_rgba(15,23,42,0.08)]">
                  <div className="text-xs font-semibold uppercase tracking-[0.08em] text-slate-400">Рабочий контекст</div>
                  <div className="mt-1 text-sm font-semibold text-slate-950">{workstreamLabel(selectedWorkstream)}</div>
                  <div className="mt-1 text-xs text-slate-500">
                    {selectedWorkstream.relationship_stage?.label || 'Подготовка первого касания'}
                  </div>
                </div>
              </section>

              <div className="grid grid-cols-5 gap-1" aria-label="Этапы подготовки цепочки обращений">
                {['Контакты', 'Получатель', 'Основание', 'Цепочка', 'Проверка'].map((label, index) => {
                  const completedSteps = [
                    drawerContacts.length > 0,
                    Boolean(drawerRecipient),
                    Boolean(selectedWorkstream.research?.why_now)
                      || (selectedWorkstream.workstream_type === 'client_partnership'
                        && selectedWorkstream.service_compatibility_score != null),
                    Boolean(savedOutreachCampaign?.touches?.length),
                    Boolean(savedCampaignQualityPassed && !savedCampaignHasPendingReview),
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

              <section className="sticky top-0 z-20 rounded-2xl bg-white/95 p-4 shadow-[0_0_0_1px_rgba(15,23,42,0.10),0_8px_24px_-12px_rgba(15,23,42,0.28)] backdrop-blur">
                <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
                  <div className="grid min-w-0 flex-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
                    <div className="min-w-0">
                      <div className="text-xs font-semibold uppercase tracking-[0.08em] text-slate-400">Получатель</div>
                      <div className="mt-1 truncate text-sm font-semibold text-slate-950">{drawerRecipient?.value || 'Не выбран'}</div>
                    </div>
                    <div className="min-w-0">
                      <div className="text-xs font-semibold uppercase tracking-[0.08em] text-slate-400">Отправитель</div>
                      <div className="mt-1 truncate text-sm font-semibold text-slate-950">
                        {senderAccountsLoading ? 'Проверяем…' : connectedEmailSender?.sender_identity || 'Email не подключён'}
                      </div>
                      {connectedEmailSender?.display_name ? <div className="mt-0.5 truncate text-xs text-slate-500">{connectedEmailSender.display_name}</div> : null}
                    </div>
                    <div className="min-w-0">
                      <div className="text-xs font-semibold uppercase tracking-[0.08em] text-slate-400">Первый шаг</div>
                      <div className="mt-1 truncate text-sm font-semibold text-slate-950">
                        {summaryFirstTouch ? `${contactTypeLabels[summaryFirstTouch.channel] || summaryFirstTouch.channel}${summaryFirstTouchMoment ? ` · ${summaryFirstTouchMoment}` : ''}` : 'Не настроен'}
                      </div>
                    </div>
                    <div className="min-w-0">
                      <div className="text-xs font-semibold uppercase tracking-[0.08em] text-slate-400">Состояние</div>
                      <div className={`mt-1 truncate text-sm font-semibold ${campaignSetupDirty ? 'text-amber-700' : 'text-slate-950'}`}>{summaryStatus}</div>
                    </div>
                  </div>
                  {summaryNextAction.href ? (
                    <Button asChild className="min-h-11 shrink-0 bg-slate-950 text-white transition-transform duration-150 active:scale-[0.96] hover:bg-slate-800">
                      <a href={summaryNextAction.href}>
                        {summaryNextAction.label}
                        <ArrowRight className="ml-2 h-4 w-4" />
                      </a>
                    </Button>
                  ) : (
                    <Button
                      type="button"
                      onClick={() => {
                        if (campaignSetupDirty && summaryNextAction.target === 'outreach-sequence') {
                          void prepareOutreachCampaign(true);
                          return;
                        }
                        scrollToLeadSection(summaryNextAction.target, summaryNextAction.focusTarget);
                      }}
                      disabled={campaignSetupDirty && Boolean(busyAction)}
                      className="min-h-11 shrink-0 bg-slate-950 text-white transition-transform duration-150 active:scale-[0.96] hover:bg-slate-800"
                    >
                      {summaryNextAction.label}
                      <ArrowRight className="ml-2 h-4 w-4" />
                    </Button>
                  )}
                </div>
                {selectedWorkstream.readiness_gate?.checks?.length ? (
                  <div className="mt-3 border-t border-slate-100 pt-3">
                    <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
                      <div className={`text-xs font-semibold uppercase tracking-[0.08em] ${selectedWorkstream.readiness_gate.code === 'ready' ? 'text-emerald-700' : 'text-amber-700'}`}>
                        {selectedWorkstream.readiness_gate.label || 'Готовность'}
                      </div>
                      {selectedWorkstream.readiness_gate.checks.map((check) => (
                        <div key={check.code || check.label} className={`inline-flex items-center gap-1.5 text-xs font-medium ${check.passed ? 'text-emerald-700' : 'text-amber-800'}`}>
                          {check.passed ? <Check className="h-3.5 w-3.5" /> : <CircleAlert className="h-3.5 w-3.5" />}
                          <span>{check.label}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}
                {savedCampaignChannelBlockers.length > 0 ? (
                  <div className="mt-3 rounded-xl bg-amber-50 p-3 shadow-[0_0_0_1px_rgba(245,158,11,0.22)]">
                    <div className="text-sm font-semibold text-amber-950">Что мешает утвердить цепочку</div>
                    <div className="mt-2 space-y-2">
                      {savedCampaignChannelBlockers.map((blocker) => (
                        <div key={blocker.key} className="flex flex-col gap-2 text-sm text-amber-950 sm:flex-row sm:items-center sm:justify-between">
                          <span className="text-pretty leading-5">{blocker.label}</span>
                          {blocker.actionHref ? (
                            <a href={blocker.actionHref} className="inline-flex min-h-10 shrink-0 items-center gap-1 font-semibold text-orange-700 transition-colors hover:text-orange-800">
                              {blocker.actionLabel}
                              <ArrowRight className="h-4 w-4" />
                            </a>
                          ) : (
                            <button type="button" onClick={() => scrollToLeadSection(blocker.target, blocker.focusTarget)} className="inline-flex min-h-10 shrink-0 items-center gap-1 font-semibold text-orange-700 transition-colors hover:text-orange-800">
                              {blocker.actionLabel}
                              <ArrowRight className="h-4 w-4" />
                            </button>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}
              </section>

              {selectedWorkstream && (
                <LeadDrawerSection
                  key={`research-${selectedWorkstream.id || 'legacy'}`}
                  id="lead-research"
                  title="Почему обращаемся"
                  description={
                    savedOperatorReason
                      || selectedWorkstream.research?.why_now
                      || 'Публичный повод не подтверждён'
                  }
                  status={savedOperatorReason
                    ? 'Подтверждено вручную'
                    : `${Number(selectedWorkstream.research?.score || 0)} баллов`}
                >
                <section className="rounded-md bg-slate-50 p-4" aria-labelledby="lead-research-title">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <h3 id="lead-research-title" className="text-sm font-semibold text-slate-950">Почему сейчас</h3>
                      <p className="mt-1 text-sm leading-6 text-slate-700">
                        {selectedWorkstream.research?.why_now || 'Публичный повод не подтверждён. Компания подходит только по общим признакам.'}
                      </p>
                    </div>
                    <span className="text-xs text-slate-500 tabular-nums">
                      {selectedWorkstream.research?.researched_at
                        ? new Date(selectedWorkstream.research.researched_at).toLocaleDateString('ru-RU')
                        : 'дата не указана'}
                    </span>
                  </div>
                  {(selectedWorkstream.research?.sources || []).length > 0 && (
                    <div className="mt-3 space-y-2">
                      {(selectedWorkstream.research?.sources || []).slice(0, 3).map((source) => {
                        const presentation = researchSourcePresentation(source);
                        return (
                          <a
                            key={`${source.url}-${source.title}`}
                            href={source.url}
                            target="_blank"
                            rel="noreferrer"
                            aria-label={`${presentation.destination}: ${presentation.context}`}
                            className="flex min-h-12 items-center justify-between gap-3 rounded-md bg-white px-3 py-2 text-slate-800 shadow-sm shadow-slate-900/5 transition-[box-shadow,color] hover:text-orange-700 hover:shadow-md"
                          >
                            <span className="min-w-0">
                              <span className="block truncate text-sm font-semibold">{presentation.destination}</span>
                              <span className="mt-0.5 block truncate text-xs font-normal text-slate-500">{presentation.context}</span>
                            </span>
                            <ExternalLink className="h-4 w-4 shrink-0 text-slate-400" />
                          </a>
                        );
                      })}
                    </div>
                  )}
                  {selectedWorkstream.research?.suggested_opener && (
                    <div className="mt-3 rounded-md bg-white p-3">
                      <div className="text-xs font-semibold uppercase tracking-[0.08em] text-slate-500">Первый абзац письма</div>
                      <p className="mt-1 text-sm leading-6 text-slate-700">{selectedWorkstream.research.suggested_opener}</p>
                      {selectedWorkstream.research?.opener_source_url ? (
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
                  {(selectedWorkstream.research?.limitations || []).length > 0 && (
                    <details className="mt-2">
                      <summary className="min-h-10 cursor-pointer py-2 text-sm font-semibold text-slate-600">Ограничения исследования</summary>
                      <ul className="space-y-1 text-sm text-slate-600">
                        {(selectedWorkstream.research?.limitations || []).map((item) => <li key={item}>{item}</li>)}
                      </ul>
                    </details>
                  )}

                  {selectedWorkstream.workstream_type === 'client_partnership' ? (
                    <div className="mt-4 rounded-md bg-white p-4 shadow-sm shadow-slate-900/5">
                      <label
                        htmlFor="manual-outreach-reason"
                        className="text-sm font-semibold text-slate-950"
                      >
                        Конкретная причина обращения
                      </label>
                      <p className="mt-1 text-pretty text-xs leading-5 text-slate-600">
                        Опишите реальную связь или идею сотрудничества. LocalOS сохранит её как подтверждённое человеком основание, а не как публичный факт.
                      </p>
                      <textarea
                        id="manual-outreach-reason"
                        value={manualOutreachReason}
                        onChange={(event) => setManualOutreachReason(event.target.value)}
                        placeholder="Например: предложить родителям после детского центра удобную детскую стрижку в соседней Весёлой расчёске."
                        rows={3}
                        maxLength={1000}
                        className="mt-3 w-full resize-y rounded-md border border-slate-200 bg-white px-3 py-2 text-sm leading-6 text-slate-900 outline-none transition-colors focus:border-orange-400 focus:ring-2 focus:ring-orange-100"
                      />
                      <div className="mt-3 flex flex-wrap items-center gap-3">
                        <Button
                          type="button"
                          variant="outline"
                          onClick={() => void saveManualOutreachReason()}
                          disabled={
                            busyAction === 'outreach-reason'
                            || manualOutreachReason.trim().length < 20
                            || manualOutreachReason.trim() === savedOperatorReason
                          }
                          className="min-h-10 bg-white transition-transform active:scale-[0.96]"
                        >
                          {busyAction === 'outreach-reason'
                            ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                            : <Check className="mr-2 h-4 w-4" />}
                          Сохранить причину обращения
                        </Button>
                        <PreparationStepStatus step={reasonPreparationStep} />
                      </div>
                    </div>
                  ) : null}

                  <div className="mt-4 rounded-md bg-white p-4 shadow-sm shadow-slate-900/5">
                    <div className="text-sm font-semibold text-slate-950">Подготовить данные</div>
                    <p className="mt-1 text-pretty text-xs leading-5 text-slate-600">
                      Рекомендуемый порядок: обновить карточку, создать аудит, затем проверить совместимость компаний.
                    </p>
                    <div className={`mt-3 grid gap-3 ${selectedWorkstream.workstream_type === 'client_partnership' ? 'sm:grid-cols-3' : ''}`}>
                      <div>
                        <Button
                          type="button"
                          variant="outline"
                          onClick={() => void refreshLeadCardData()}
                          disabled={Boolean(busyAction)}
                          className="min-h-11 w-full justify-start bg-white transition-transform active:scale-[0.96]"
                        >
                          {busyAction === 'parse-lead-card'
                            ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                            : <Search className="mr-2 h-4 w-4" />}
                          Обновить данные карточки
                        </Button>
                        <PreparationStepStatus step={preparationSteps.card_refresh} />
                      </div>
                      {selectedWorkstream.workstream_type === 'client_partnership' ? (
                        <>
                          <div>
                            <Button
                              type="button"
                              variant="outline"
                              onClick={() => void createLeadAudit()}
                              disabled={Boolean(busyAction) || !selectedWorkstream.client_business_id}
                              className="min-h-11 w-full justify-start bg-white transition-transform active:scale-[0.96]"
                            >
                              {busyAction === 'audit-lead'
                                ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                                : <ShieldCheck className="mr-2 h-4 w-4" />}
                              Создать аудит
                            </Button>
                            <PreparationStepStatus step={preparationSteps.audit} />
                          </div>
                          <div>
                            <Button
                              type="button"
                              variant="outline"
                              onClick={() => void checkLeadCompatibility()}
                              disabled={Boolean(busyAction) || !selectedWorkstream.client_business_id}
                              className="min-h-11 w-full justify-start bg-white transition-transform active:scale-[0.96]"
                            >
                              {busyAction === 'match-lead'
                                ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                                : <Users className="mr-2 h-4 w-4" />}
                              Проверить совместимость
                            </Button>
                            <PreparationStepStatus step={preparationSteps.compatibility} />
                          </div>
                        </>
                      ) : null}
                    </div>
                    {dataPreparationMessage ? (
                      <p
                        className="mt-3 rounded-md bg-sky-50 px-3 py-2 text-pretty text-sm leading-6 text-sky-900"
                        aria-live="polite"
                      >
                        {dataPreparationMessage}
                      </p>
                    ) : null}
                  </div>
                </section>
                </LeadDrawerSection>
              )}

              <LeadDrawerSection
                key={`conversation-${selectedWorkstream.id || 'legacy'}`}
                id="lead-conversation"
                title="Сообщения и каналы"
                description={savedOutreachCampaign
                  ? `${savedConversationTouches.length} касания · ${humanReplyEvents.length ? `${humanReplyEvents.length} ответов` : 'ответов пока нет'}`
                  : 'Здесь появятся сохранённые сообщения, отправки и ответы'}
                status={savedOutreachCampaign ? `Версия ${Number(savedOutreachCampaign.version || 0)}` : 'Не сохранено'}
                defaultOpen={Boolean(humanReplyEvents.length || savedCampaignHasPendingReview)}
              >
              <section
                className="grid gap-4 lg:grid-cols-[minmax(280px,0.72fr)_minmax(0,1.55fr)]"
                aria-label="Каналы и история сообщений"
              >
                <div className="rounded-2xl bg-slate-50 p-4 shadow-sm shadow-slate-900/5">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h3 className="text-sm font-semibold text-slate-950">Каналы</h3>
                      <p className="mt-1 text-pretty text-xs leading-5 text-slate-600">Контакты получателя и состояние каждого канала в текущей цепочке.</p>
                    </div>
                    <Badge variant="outline" className="shrink-0 border-slate-200 bg-white text-slate-700 tabular-nums">
                      {conversationChannels.length}
                    </Badge>
                  </div>

                  {conversationChannels.length > 0 ? (
                    <div className="mt-4 space-y-2">
                      {conversationChannels.map((item) => {
                        const href = outreachChannelHref(item.channel, item.contact);
                        const cardClassName = `block rounded-xl bg-white px-3 py-3 shadow-sm shadow-slate-900/5 ${href ? 'cursor-pointer transition-[box-shadow,transform] duration-150 hover:shadow-md hover:shadow-slate-900/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 focus-visible:ring-offset-2 active:scale-[0.96]' : ''}`;
                        const cardContent = (
                          <>
                            <div className="flex items-start justify-between gap-3">
                              <div className="min-w-0">
                                <div className="text-sm font-semibold text-slate-950">{item.label}</div>
                                <div className={`mt-1 flex min-w-0 items-center gap-1 text-xs ${href ? 'text-sky-700' : 'text-slate-500'}`}>
                                  <span className="truncate">
                                    {item.contact || (item.touchCount > 0 ? 'Добавлен в цепочку' : 'Контакт получателя не найден')}
                                  </span>
                                  {href ? <ExternalLink className="h-3.5 w-3.5 shrink-0" aria-hidden="true" /> : null}
                                </div>
                              </div>
                              <Badge variant="outline" className={`shrink-0 ${outreachStatusTone(item.status)}`}>
                                {outreachTouchStatusLabels[item.status] || item.status}
                              </Badge>
                            </div>
                            {item.touchCount > 0 ? (
                              <div className="mt-2 text-[11px] font-medium text-slate-400 tabular-nums">
                                Касаний в цепочке: {item.touchCount}
                              </div>
                            ) : null}
                          </>
                        );

                        return href ? (
                          <a
                            key={item.channel}
                            href={href}
                            target={/^https?:\/\//i.test(href) ? '_blank' : undefined}
                            rel={/^https?:\/\//i.test(href) ? 'noreferrer' : undefined}
                            aria-label={`Открыть ${item.label}: ${item.contact}`}
                            className={cardClassName}
                          >
                            {cardContent}
                          </a>
                        ) : (
                          <div key={item.channel} className={cardClassName}>
                            {cardContent}
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <div className="mt-4 rounded-xl bg-white px-3 py-4 text-pretty text-sm leading-6 text-slate-600 shadow-sm shadow-slate-900/5">
                      Каналы ещё не найдены. Запустите проверку контактов или добавьте контакт вручную.
                    </div>
                  )}
                </div>

                <div className="min-w-0 rounded-2xl bg-slate-50 p-4 shadow-sm shadow-slate-900/5">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <h3 className="text-sm font-semibold text-slate-950">История сообщений</h3>
                      <p className="mt-1 text-pretty text-xs leading-5 text-slate-600">Ответ показан прямо под тем сообщением, на которое он пришёл.</p>
                    </div>
                    {savedOutreachCampaign ? (
                      <Badge variant="outline" className={outreachStatusTone(savedOutreachCampaign.status)}>
                        Версия {savedOutreachCampaign.version || 1} · {outreachTouchStatusLabels[String(savedOutreachCampaign.status || '')] || savedOutreachCampaign.status || 'Черновик'}
                      </Badge>
                    ) : null}
                  </div>

                  {savedConversationTouches.length > 0 ? (
                    <div className="mt-4 space-y-3">
                      {savedConversationTouches.map((touch) => {
                        const delivery = touch.id ? deliveryByTouchId.get(touch.id) : undefined;
                        const replyEvents = humanReplyEvents.filter((event) => event.touch_id === touch.id);
                        const runtimeChannelStatus = String(
                          touch.channel_status || touch.message_brief_json?.channel_status || '',
                        );
                        const runtimeChannelBlocked = !['ready', 'manual'].includes(runtimeChannelStatus);
                        const status = String(
                          replyEvents.length > 0
                            ? 'reply'
                            : runtimeChannelBlocked
                              ? runtimeChannelStatus
                              : delivery?.delivery_status || touch.status || 'draft',
                        );
                        const touchIndex = Number(touch.sequence_index || 0);
                        const editableTouch = savedCampaignDisplayTouches.find((item) => item.sequence_index === touchIndex);
                        const touchCanBeEdited = canEditSavedTouch(
                          String(savedOutreachCampaign?.status || ''),
                          String(touch.status || ''),
                        );
                        const touchDraft = touchEdits[touchIndex];
                        const sentMoment = formatOutreachMoment(delivery?.sent_at);
                        const scheduledMoment = formatOutreachMoment(delivery?.scheduled_at || touch.scheduled_at);
                        const operatorApprovedIdea = touch.message_brief_json?.evidence_kind === 'operator_approved_partnership_reason';
                        return (
                          <article key={touch.id || `${touch.sequence_index}-${touch.channel}`} className="overflow-hidden rounded-xl bg-white shadow-sm shadow-slate-900/5">
                            <div className="flex flex-wrap items-center justify-between gap-2 px-4 pt-4">
                              <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.06em] text-slate-500">
                                <MessageCircle className="h-4 w-4" />
                                <span>Касание {Number(touch.sequence_index || 0) + 1} · {contactTypeLabels[String(touch.channel || '')] || touch.channel || 'Ручной канал'}</span>
                              </div>
                              <Badge variant="outline" className={outreachStatusTone(replyEvents.length > 0 ? 'reply' : status)}>
                                {replyEvents.length > 0 ? 'Есть ответ' : outreachTouchStatusLabels[status] || status}
                              </Badge>
                            </div>
                            <div className="px-4 pb-4">
                              {touch.message_brief_json?.template_label ? (
                                <p className="mt-2 text-xs font-medium text-sky-700">
                                  Основа: {touch.message_brief_json.template_label}
                                </p>
                              ) : null}
                              {touch.message_brief_json?.observation || touch.message_brief_json?.pain_hypothesis || touch.message_brief_json?.problem_hypothesis || touch.message_brief_json?.solution || touch.message_brief_json?.relevance_bridge ? (
                                <div className="mt-3 space-y-1 border-l-2 border-sky-200 pl-3 text-sm leading-6 text-slate-700">
                                  {touch.message_brief_json?.observation ? <p><span className="font-semibold text-slate-900">{operatorApprovedIdea ? 'Подтверждённая идея:' : 'Факт:'}</span> {touch.message_brief_json.observation}</p> : null}
                                  {touch.message_brief_json?.pain_hypothesis || touch.message_brief_json?.problem_hypothesis ? <p><span className="font-semibold text-slate-900">Гипотеза боли:</span> {touch.message_brief_json.pain_hypothesis || touch.message_brief_json.problem_hypothesis}</p> : null}
                                  {touch.message_brief_json?.solution ? <p><span className="font-semibold text-slate-900">Что делает LocalOS:</span> {touch.message_brief_json.solution}</p> : null}
                                  {touch.message_brief_json?.relevance_bridge ? <p><span className="font-semibold text-slate-900">{operatorApprovedIdea ? 'Почему предложение подходит:' : 'Почему это связано:'}</span> {touch.message_brief_json.relevance_bridge}</p> : null}
                                </div>
                              ) : null}
                              {touch.message_brief_json?.language_support ? (
                                <div className="mt-3 rounded-lg bg-slate-50 px-3 py-2 text-xs leading-5 text-slate-600 ring-1 ring-inset ring-slate-200">
                                  <span className="font-semibold text-slate-900">Живой язык:</span>{' '}
                                  {touch.message_brief_json.language_support.status === 'supported'
                                    ? `подтверждён ${Number(touch.message_brief_json.language_support.document_count || 0)} документами из ${Number(touch.message_brief_json.language_support.source_count || 0)} независимых источников`
                                    : touch.message_brief_json.language_support.status === 'conditional_operator_approved'
                                      ? `боль про перенос цен не подтверждена как типичная; разрешена только условная форма «если». Язык ручной работы: ${Number(touch.message_brief_json.language_support.document_count || 0)} документа, ${Number(touch.message_brief_json.language_support.source_count || 0)} источников`
                                    : touch.message_brief_json.language_support.status === 'weak'
                                      ? 'поддержка слабая — боль можно оставить только нейтральным вопросом'
                                      : touch.message_brief_json.language_support.status === 'not_checked'
                                        ? 'для этого касания отдельная проверка корпуса не нужна'
                                        : 'поддержка не подтверждена — гипотезу нельзя выдавать за типичную ситуацию'}.
                                </div>
                              ) : null}
                              {editableTouch && touchCanBeEdited ? (
                                <OutreachTouchMessageEditor
                                  touch={editableTouch}
                                  draft={touchDraft}
                                  editing={editingTouchIndex === touchIndex}
                                  disabled={Boolean(busyAction)}
                                  saving={busyAction === `accept-touch-${touchIndex}`}
                                  persisted={Boolean(touch.message_brief_json?.human_edited)}
                                  onStart={() => startTouchEdit(editableTouch)}
                                  onChange={(nextDraft) => {
                                    setTouchEdits((current) => {
                                      const next = { ...current, [touchIndex]: nextDraft };
                                      if (outreachTouchEditsStorageKey) {
                                        localStorage.setItem(outreachTouchEditsStorageKey, JSON.stringify(next));
                                      }
                                      return next;
                                    });
                                    setTouchEditsValidated(false);
                                  }}
                                  onAccept={(draft) => void acceptTouchEdit(touchIndex, draft)}
                                  onCancel={() => resetTouchEdit(touchIndex)}
                                  onReset={() => resetTouchEdit(touchIndex)}
                                />
                              ) : (
                                <>
                                  <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-slate-800">
                                    {String(touch.approved_text || touch.generated_text || 'Текст сообщения ещё не подготовлен.')}
                                  </p>
                                  {editableTouch && !['sent', 'delivered', 'read', 'replied'].includes(status) ? (
                                    <p className="mt-3 text-pretty text-xs leading-5 text-slate-500">
                                      Чтобы изменить неотправленное сообщение, сначала поставьте цепочку на паузу. Перед возобновлением текст потребует повторной проверки.
                                    </p>
                                  ) : null}
                                </>
                              )}
                              {touch.quality_gate_json && !savedOutreachCampaign?.requires_regeneration && !runtimeChannelBlocked ? (
                                <details open={!touch.quality_gate_json.passed} className="mt-3 rounded-lg bg-slate-50 px-3 py-2 ring-1 ring-inset ring-slate-200">
                                  <summary className="min-h-10 cursor-pointer select-none py-2 text-sm font-semibold text-slate-800">
                                    Почему такая оценка ·{' '}
                                    <span className="tabular-nums">
                                      {Number(touch.quality_gate_json.total_score ?? touch.quality_gate_json.score ?? 0)}/{Number(touch.quality_gate_json.max_score || 18)}
                                    </span>
                                    {' '}· {outreachQualityVerdictLabels[String(touch.quality_gate_json.verdict || '')] || 'Нужна проверка'}
                                  </summary>
                                  <div className="grid gap-x-4 gap-y-2 pb-3 sm:grid-cols-2">
                                    {Object.entries(touch.quality_gate_json.criterion_scores || {}).map(([criterion, score]) => (
                                      <div key={criterion} className="flex items-center justify-between gap-3 text-xs text-slate-600">
                                        <span>{outreachQualityCriterionLabels[criterion] || criterion}</span>
                                        <span className={`shrink-0 tabular-nums font-semibold ${Number(score) === 2 ? 'text-emerald-700' : Number(score) === 1 ? 'text-amber-700' : 'text-rose-700'}`}>
                                          {Number(score)}/2
                                        </span>
                                      </div>
                                    ))}
                                  </div>
                                  {(touch.quality_gate_json.reason_codes || []).length > 0 ? (
                                    <div className="border-t border-slate-200 py-3">
                                      <div className="text-xs font-semibold uppercase tracking-[0.06em] text-slate-500">Что исправить</div>
                                      <ul className="mt-2 space-y-1 text-sm leading-5 text-slate-700">
                                        {(touch.quality_gate_json.reason_codes || []).map((reasonCode) => (
                                          <li key={reasonCode}>• {outreachQualityReasonLabels[reasonCode] || reasonCode}</li>
                                        ))}
                                      </ul>
                                    </div>
                                  ) : (
                                    <p className="border-t border-slate-200 py-3 text-sm text-emerald-700">Критических замечаний нет.</p>
                                  )}
                                  {touch.quality_gate_json.human_language_review ? (
                                    <div className={`border-t border-slate-200 py-3 text-sm ${touch.quality_gate_json.human_language_review.passed ? 'text-emerald-700' : 'text-amber-800'}`}>
                                      <p>Язык: {touch.quality_gate_json.human_language_review.passed ? 'человеческий и конкретный' : 'нужна редактура без штампов'}.</p>
                                      {(touch.quality_gate_json.human_language_review.reason_codes || []).length > 0 ? (
                                        <p className="mt-1 text-xs">
                                          Обнаружено: {(touch.quality_gate_json.human_language_review.reason_codes || []).map((code) => outreachQualityReasonLabels[code] || code).join('; ')}
                                        </p>
                                      ) : null}
                                    </div>
                                  ) : null}
                                </details>
                              ) : null}
                              {sentMoment || scheduledMoment ? (
                                <div className="mt-3 text-xs text-slate-500 tabular-nums">
                                  {sentMoment ? `Отправлено ${sentMoment}` : `Запланировано ${scheduledMoment}`}
                                </div>
                              ) : null}
                              {delivery?.error_text ? (
                                <div className="mt-3 rounded-lg bg-rose-50 px-3 py-2 text-xs leading-5 text-rose-800">
                                  Ошибка доставки: {delivery.error_text}
                                </div>
                              ) : null}
                            </div>

                            {replyEvents.map((event) => {
                              const replyText = inboundMessageText(event);
                              return (
                                <div key={event.id} className="border-t border-emerald-100 bg-emerald-50 px-4 py-4">
                                  <div className="flex flex-wrap items-center justify-between gap-2">
                                    <div className="text-xs font-semibold uppercase tracking-[0.06em] text-emerald-800">Ответ на это сообщение</div>
                                    <div className="text-xs text-emerald-700 tabular-nums">{formatOutreachMoment(event.occurred_at || event.created_at)}</div>
                                  </div>
                                  <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-emerald-950">
                                    {replyText || 'Текст ответа не сохранён провайдером.'}
                                  </p>
                                  <div className="mt-2 text-xs font-medium text-emerald-800">
                                    {outreachReplyClassificationLabels[String(event.classification || '')] || 'Ответ получателя'}
                                    {event.stops_campaign ? ' · следующие касания остановлены' : ''}
                                  </div>
                                </div>
                              );
                            })}
                          </article>
                        );
                      })}

                      {unlinkedReplyEvents.map((event) => (
                        <div key={event.id} className="rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-950 shadow-sm shadow-slate-900/5">
                          <div className="flex flex-wrap items-center justify-between gap-2 text-xs font-semibold uppercase tracking-[0.06em] text-amber-800">
                            <span>Ответ без привязки к касанию</span>
                            <span className="tabular-nums">{formatOutreachMoment(event.occurred_at || event.created_at)}</span>
                          </div>
                          <p className="mt-2 whitespace-pre-wrap leading-6">{inboundMessageText(event) || 'Текст ответа не сохранён провайдером.'}</p>
                        </div>
                      ))}
                      {hasTouchEdits ? (
                        <div className="rounded-xl bg-orange-50 p-4 ring-1 ring-inset ring-orange-200">
                          <div className="text-sm font-semibold text-orange-950">В цепочке есть несохранённые ручные правки</div>
                          <p className="mt-1 text-pretty text-xs leading-5 text-orange-900">
                            Черновик сохранён на этом устройстве и восстановится после перезагрузки. Откройте каждое изменённое сообщение и нажмите «Принять изменения» — версия цепочки при этом не изменится.
                          </p>
                        </div>
                      ) : null}
                      {savedCampaignHasHumanEdits ? (
                        <div className={`rounded-xl p-4 ring-1 ring-inset ${savedCampaignQualityPassed
                          ? 'bg-emerald-50 ring-emerald-200'
                          : 'bg-amber-50 ring-amber-200'}`}>
                          <div className={`text-sm font-semibold ${savedCampaignQualityPassed ? 'text-emerald-950' : 'text-amber-950'}`}>
                            Результат проверки
                          </div>
                          <p className={`mt-1 text-pretty text-xs leading-5 ${savedCampaignQualityPassed ? 'text-emerald-900' : 'text-amber-900'}`}>
                            {savedCampaignHasPendingReview
                              ? 'Сохранённые сообщения изменились и ещё не проверены.'
                              : savedCampaignQualityPassed
                                ? 'Все сохранённые сообщения прошли проверку. Новая версия цепочки не создавалась.'
                                : 'Есть сообщения с замечаниями. Откройте их ниже, исправьте и повторите проверку.'}
                          </p>
                          <Button
                            type="button"
                            variant="outline"
                            onClick={() => void reviewSavedTouchEdits()}
                            disabled={Boolean(busyAction) || hasTouchEdits}
                            className="mt-3 min-h-10 bg-white transition-transform active:scale-[0.96]"
                          >
                            {busyAction === 'review-saved-edits' ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : <ShieldCheck className="mr-2 h-4 w-4" />}
                            Проверить сохранённые сообщения
                          </Button>
                        </div>
                      ) : null}
                    </div>
                  ) : (
                    <div className="mt-4 rounded-xl bg-white px-4 py-5 text-pretty text-sm leading-6 text-slate-600 shadow-sm shadow-slate-900/5">
                      Цепочка ещё не сохранена. Подготовьте её ниже — здесь появятся сообщения, статусы отправки и ответы.
                    </div>
                  )}
                </div>
              </section>
              </LeadDrawerSection>

              <LeadDrawerSection
                key={`contacts-${selectedWorkstream.id || 'legacy'}`}
                id="lead-contacts"
                title="Получатель и найденные контакты"
                description={chainTouchesByContactId.size > 0
                  ? `${chainTouchesByContactId.size} для отправки · всего найдено ${drawerContacts.length}`
                  : drawerRecipient?.value
                    ? `Выбран ${drawerRecipient.value} · всего найдено ${drawerContacts.length}`
                  : `${drawerContacts.length} найдено · выберите контакт для первого сообщения`}
                status={chainTouchesByContactId.size > 0 ? 'Для цепочки выбрано' : drawerRecipient ? 'Получатель выбран' : 'Нужно выбрать'}
                defaultOpen={!drawerRecipient || manualContactOpen}
              >
              <section className="rounded-md bg-slate-50 p-4" aria-labelledby="lead-contacts-title">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h3 id="lead-contacts-title" className="text-sm font-semibold text-slate-950">Контакты и получатель</h3>
                    <p className="mt-1 text-sm text-slate-600 tabular-nums">
                      {drawerContacts.length} найдено · {drawerContacts.filter((item) => ['verified', 'confirmed_source'].includes(String(item.verification_status || ''))).length} проверено
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      variant="outline"
                      onClick={() => {
                        setManualContactOpen((current) => !current);
                        setVkHandoffContact(false);
                        setManualContactError('');
                      }}
                      disabled={busyAction === 'manual-contact'}
                      className="min-h-10 bg-white active:scale-[0.96] transition-transform"
                    >
                      <Plus className="mr-2 h-4 w-4" />
                      Добавить вручную
                    </Button>
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
                </div>
                <p className="mt-3 text-xs font-medium text-slate-500">
                  {contactIntelligenceLoading ? 'Загружаем контакты…' : enrichmentLabel(selectedWorkstream.enrichment_state || (contactIntelligence?.job ? {
                    id: contactIntelligence.job.id,
                    status: contactIntelligence.job.status,
                    phase: contactIntelligence.job.phase,
                    error: contactIntelligence.job.error,
                  } : null))}
                </p>
                {['vk', 'vk_manual'].includes(String(selectedWorkstream.selected_channel || ''))
                  && !drawerContacts.some((contact) => ['email', 'telegram'].includes(contact.type) && ['verified', 'confirmed_source'].includes(String(contact.verification_status || ''))) ? (
                    <div className="mt-3 rounded-md border border-sky-200 bg-sky-50 p-3 text-sm text-sky-950">
                      <div className="font-semibold">Запросить рабочий email или Telegram</div>
                      <p className="mt-1 leading-6 text-sky-800">
                        Личный VK не сканируется. Получите рабочий контакт в диалоге и сохраните его здесь — дальше LocalOS будет отслеживать ответы.
                      </p>
                      <div className="mt-2 flex flex-wrap gap-2">
                        {['email', 'telegram'].map((channel) => (
                          <Button
                            key={channel}
                            type="button"
                            variant="outline"
                            className="min-h-10 bg-white"
                            onClick={() => {
                              setManualContactType(channel);
                              setManualTelegramUsage('recipient');
                              setVkHandoffContact(true);
                              setManualContactOpen(true);
                              setManualContactError('');
                            }}
                          >
                            Сохранить {channel === 'email' ? 'email' : 'Telegram'}
                          </Button>
                        ))}
                      </div>
                    </div>
                  ) : null}
                {manualContactOpen && (
                  <div className="mt-3 rounded-md bg-white p-3 shadow-sm shadow-slate-900/5">
                    <div className="grid gap-3 sm:grid-cols-2">
                      <label className="text-xs font-semibold text-slate-700" htmlFor="manual-lead-contact-type">
                        Канал
                        <select
                          id="manual-lead-contact-type"
                          value={manualContactType}
                          onChange={(event) => {
                            setManualContactType(event.target.value);
                            setManualContactError('');
                          }}
                          className="mt-1 h-11 w-full rounded-md border border-slate-200 bg-white px-3 text-sm font-normal text-slate-900 outline-none focus:border-slate-400"
                        >
                          {manualContactOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                        </select>
                      </label>
                      <label className="text-xs font-semibold text-slate-700" htmlFor="manual-lead-contact-value">
                        Контакт или ссылка
                        <Input
                          id="manual-lead-contact-value"
                          value={manualContactValue}
                          onChange={(event) => {
                            setManualContactValue(event.target.value);
                            setManualContactError('');
                          }}
                          placeholder={manualContactOptions.find((option) => option.value === manualContactType)?.placeholder || 'Укажите контакт'}
                          className="mt-1 h-11 font-normal"
                        />
                      </label>
                      {manualContactType === 'telegram' && (
                        <label className="text-xs font-semibold text-slate-700 sm:col-span-2" htmlFor="manual-telegram-usage">
                          Как использовать Telegram-ссылку
                          <select
                            id="manual-telegram-usage"
                            value={manualTelegramUsage}
                            onChange={(event) => setManualTelegramUsage(event.target.value)}
                            className="mt-1 h-11 w-full rounded-md border border-slate-200 bg-white px-3 text-sm font-normal text-slate-900 outline-none focus:border-slate-400"
                          >
                            <option value="recipient">Личный аккаунт или чат — можно выбрать получателем</option>
                            <option value="signal_source">Публичный канал — использовать для поиска сигналов</option>
                          </select>
                        </label>
                      )}
                      {!(manualContactType === 'telegram' && manualTelegramUsage === 'signal_source') && (
                        <>
                          <label className="text-xs font-semibold text-slate-700" htmlFor="manual-contact-owner-type">
                            Кому принадлежит
                            <select
                              id="manual-contact-owner-type"
                              value={manualOwnerType}
                              onChange={(event) => setManualOwnerType(event.target.value)}
                              className="mt-1 h-11 w-full rounded-md border border-slate-200 bg-white px-3 text-sm font-normal text-slate-900 outline-none focus:border-slate-400"
                            >
                              <option value="company">Компании — общий контакт</option>
                              <option value="person">Конкретному человеку</option>
                            </select>
                          </label>
                          {manualOwnerType === 'person' && (
                            <div className="grid gap-3 sm:col-span-2 sm:grid-cols-2">
                              <label className="text-xs font-semibold text-slate-700" htmlFor="manual-contact-person-name">
                                Имя человека
                                <Input id="manual-contact-person-name" value={manualPersonName} onChange={(event) => setManualPersonName(event.target.value)} placeholder="Анна" className="mt-1 h-11 font-normal" />
                              </label>
                              <label className="text-xs font-semibold text-slate-700" htmlFor="manual-contact-role-title">
                                Роль
                                <Input id="manual-contact-role-title" value={manualRoleTitle} onChange={(event) => setManualRoleTitle(event.target.value)} placeholder="Управляющая" className="mt-1 h-11 font-normal" />
                              </label>
                            </div>
                          )}
                        </>
                      )}
                    </div>
                    <p className="mt-3 text-pretty text-xs leading-5 text-slate-600">
                      {manualContactType === 'telegram' && manualTelegramUsage === 'signal_source'
                        ? 'Канал появится ниже в Telegram-источниках. Радар сначала проверит, что он публичный; канал не будет выбран как чат получателя.'
                        : 'Контакт будет помечен как добавленный вручную. LocalOS не считает его проверенным, пока формат или источник не подтверждены.'}
                    </p>
                    {manualContactError ? <div role="alert" className="mt-3 rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-800">{manualContactError}</div> : null}
                    <div className="mt-3 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
                      <Button variant="ghost" onClick={() => { setManualContactOpen(false); setVkHandoffContact(false); }} disabled={busyAction === 'manual-contact'} className="min-h-10">Отмена</Button>
                      <Button
                        onClick={() => void saveManualContact()}
                        disabled={busyAction === 'manual-contact' || !manualContactValue.trim()}
                        className="min-h-11 bg-slate-950 text-white active:scale-[0.96] transition-transform hover:bg-slate-800"
                      >
                        {busyAction === 'manual-contact' ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : <Plus className="mr-2 h-4 w-4" />}
                        {manualContactType === 'telegram' && manualTelegramUsage === 'signal_source' ? 'Добавить канал' : 'Сохранить контакт'}
                      </Button>
                    </div>
                  </div>
                )}
                <div className="mt-3 space-y-2">
                  {drawerContacts.map((contact) => {
                    const selected = drawerRecipient?.id === contact.id;
                    const chainTouches = chainTouchesByContactId.get(String(contact.id)) || [];
                    const selectedForSending = chainTouches.length > 0;
                    const invalid = contact.verification_status === 'invalid';
                    const selecting = busyAction === `recipient-${contact.id}`;
                    return (
                      <button
                        key={contact.id}
                        type="button"
                        onClick={() => selectRecipient(contact)}
                        aria-pressed={selected}
                        aria-busy={selecting}
                        disabled={invalid || selecting}
                        className={`flex min-h-14 w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left transition-[background-color,box-shadow,transform] duration-150 ease-out active:scale-[0.96] ${selectedForSending ? 'bg-emerald-50/60 shadow-[0_0_0_2px_rgba(16,185,129,0.62),0_4px_12px_-6px_rgba(5,150,105,0.28)]' : selected ? 'bg-white shadow-[0_0_0_2px_rgba(14,165,233,0.24)]' : 'bg-white shadow-[0_0_0_1px_rgba(15,23,42,0.05)] hover:bg-slate-100'} ${invalid ? 'cursor-not-allowed opacity-50' : selecting ? 'cursor-wait' : ''}`}
                      >
                        <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${selectedForSending ? 'bg-emerald-600 text-white' : selected ? 'bg-sky-50 text-sky-700' : 'bg-slate-100 text-slate-600'}`}>
                          {contact.owner_type === 'person' ? <UserRound className="h-4 w-4" /> : <MessageCircle className="h-4 w-4" />}
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1">
                            <span className="truncate text-sm font-semibold text-slate-950">{contact.person_name || contact.value || contactTypeLabels[String(contact.type || '')] || 'Контакт'}</span>
                            {selectedForSending ? (
                              <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-emerald-600 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.04em] text-white">
                                <Check className="h-3 w-3" />
                                Выбран для отправки
                              </span>
                            ) : selected ? (
                              <span className="shrink-0 text-[11px] font-semibold text-sky-700">Выбран как получатель</span>
                            ) : null}
                          </span>
                          <span className="mt-0.5 block truncate text-xs text-slate-500">
                            {[contact.role_title, contactTypeLabels[String(contact.type || '')], contact.person_name ? contact.value : ''].filter(Boolean).join(' · ')}
                          </span>
                          <span className="mt-0.5 block truncate text-xs text-slate-500">
                            {verificationLabel(contact.verification_status)} · источник {contactSourceLabel(contact.source_type)}
                          </span>
                          {selectedForSending ? (
                            <span className="mt-1 block text-pretty text-[11px] font-medium leading-4 text-emerald-800">
                              {chainTouches.map((touch) => `Шаг ${Number(touch.sequence_index || 0) + 1} · ${contactTypeLabels[String(touch.channel || '')] || touch.channel}`).join(' · ')}
                            </span>
                          ) : null}
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
                          Это публичные каналы и чаты получателя для поиска сигналов. Они не считаются каналами бизнеса-отправителя и не используются для личной отправки.
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
                        const ownerLabel = source.source_owner_label || source.source_owner_name || 'Получатель';
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
                              <span className="mt-0.5 block text-pretty text-xs leading-5 text-slate-600">Источник {ownerLabel}</span>
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
              </LeadDrawerSection>

              <LeadDrawerSection
                key={`sequence-${selectedWorkstream.id || 'legacy'}`}
                id="outreach-sequence"
                title="Цепочка, расписание и запуск"
                description={summaryFirstTouch
                  ? `Первый шаг: ${contactTypeLabels[summaryFirstTouch.channel] || summaryFirstTouch.channel}${summaryFirstTouchMoment ? ` · ${summaryFirstTouchMoment}` : ''}`
                  : 'Выберите порядок каналов, проверьте сообщения и сохраните цепочку'}
                status={campaignSetupDirty ? 'Не сохранено' : savedOutreachCampaign?.status === 'approved' ? 'Подтверждено' : 'Черновик'}
              >
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
                        <span className="block text-sm font-semibold text-slate-950">От имени бизнеса через LocalOS</span>
                        <span className="mt-1 block text-pretty text-xs leading-5 text-slate-600">Текст написан от лица {selectedWorkstream.client_business_name || 'бизнеса'}, а для доставки используется подключённый аккаунт LocalOS.</span>
                      </button>
                    </div>
                    {senderMode === 'localos_for_partner' ? (
                      <div className="mt-2 rounded-md bg-orange-50 px-3 py-2 text-pretty text-xs leading-5 text-orange-950">
                        Получатель увидит обращение от лица «{selectedWorkstream.client_business_name || 'этого бизнеса'}»: «Мы ваши соседи - …». LocalOS во внешнем тексте не упоминается. Внутри системы сохраняются технический отправитель и разрешение бизнеса.
                      </div>
                    ) : null}
                  </fieldset>
                ) : null}

                {savedOutreachCampaign?.requires_regeneration && savedCampaignHasHumanEdits ? (
                  <div className="mt-3 rounded-md bg-amber-50 p-3 text-pretty text-sm leading-6 text-amber-950">
                    <div className="font-semibold">Сохранённые правки нужно повторно проверить</div>
                    <p className="mt-1">Тексты, каналы и расписание останутся в этой же версии. LocalOS только повторит проверку качества.</p>
                    <Button variant="outline" onClick={() => scrollToLeadSection('lead-conversation')} className="mt-2 min-h-10 bg-white">
                      <ShieldCheck className="mr-2 h-4 w-4" />
                      Проверить сохранённые сообщения
                    </Button>
                  </div>
                ) : savedOutreachCampaign?.requires_regeneration ? (
                  <div className="mt-3 rounded-md bg-amber-50 p-3 text-pretty text-sm leading-6 text-amber-950">
                    <div className="font-semibold">Эту версию нельзя подтвердить</div>
                    <p className="mt-1">Она создана до текущей проверки персонализации. Покажите новую цепочку, проверьте тексты и сохраните следующую версию.</p>
                    <Button variant="outline" onClick={() => void prepareOutreachCampaign(false)} disabled={busyAction === 'preview-campaign'} className="mt-2 min-h-10 bg-white">
                      {busyAction === 'preview-campaign' ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : <Sparkles className="mr-2 h-4 w-4" />}
                      Подготовить новую цепочку
                    </Button>
                  </div>
                ) : null}

                <label className="mt-3 block rounded-md bg-white p-3 shadow-[0_0_0_1px_rgba(15,23,42,0.08),0_1px_2px_-1px_rgba(15,23,42,0.06)]">
                  <span className="text-sm font-semibold text-slate-950">Дата и время первого касания</span>
                  <span className="mt-1 block text-pretty text-xs leading-5 text-slate-600">Это начало новой версии. Остальные даты рассчитываются по интервалам и сразу видны в календаре.</span>
                  <OutreachDateTimePicker
                    ariaLabel="Дата и время первого касания"
                    value={sequenceStartAt}
                    onChange={(value) => {
                      setSequenceStartAt(value);
                      persistOutreachCampaignSetup({ sequenceStartAt: value });
                      setOutreachPreview(null);
                      setCampaignSetupDirty(true);
                    }}
                  />
                </label>

                <div className="mt-3 grid gap-2 sm:grid-cols-2">
                  {[0, 1, 2, 3].map((index) => {
                    const channel = sequenceChannels[index];
                    const accounts = senderAccounts.filter((account) => account.channel === channel);
                    const sameChannelSteps = sequenceChannels
                      .map((item, itemIndex) => item === channel ? itemIndex + 1 : -1)
                      .filter((itemIndex) => itemIndex > 0);
                    return (
                    <div key={index} className="rounded-md bg-white p-3 text-xs font-semibold text-slate-600 shadow-[0_0_0_1px_rgba(15,23,42,0.06)]">
                      <div className="flex items-center justify-between gap-2">
                        <div>{sequenceAngleLabels[index]}</div>
                        <span className="tabular-nums text-[11px] text-slate-400">Шаг {index + 1}</span>
                      </div>
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
                          <option value="vk">VK · автоматически</option>
                          <option value="vk_manual">VK · вручную</option>
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
                      {automaticOutreachChannels.has(channel) ? (
                        <label className="mt-3 block border-t border-slate-100 pt-3 text-xs font-semibold text-slate-600" htmlFor={`touch-sender-${index}`}>
                          Отправитель
                          <select
                            id={`touch-sender-${index}`}
                            aria-label={`Отправитель касания ${index + 1}`}
                            value={sequenceSenders[index] || ''}
                            onChange={(event) => updateSequenceSender(index, event.target.value)}
                            disabled={senderAccountsLoading}
                            className="mt-2 min-h-11 w-full rounded-md border border-slate-200 bg-white px-3 text-sm font-medium text-slate-900 outline-none transition-[border-color,box-shadow] duration-150 focus:border-orange-400 focus:ring-2 focus:ring-orange-100"
                          >
                            <option value="">{senderAccountsLoading ? 'Проверяем аккаунты…' : 'Выберите отправителя'}</option>
                            {accounts.map((account) => (
                              <option key={account.id} value={account.id} disabled={!outreachSenderReady(account)}>
                                {outreachSenderDisplayLabel(account)} · {outreachSenderStatusLabel(account)}
                              </option>
                            ))}
                          </select>
                          {accounts.length === 0 && !senderAccountsLoading ? (
                            <span className="mt-2 block text-pretty font-medium leading-5 text-amber-700">Нет подключённого аккаунта для этого канала.</span>
                          ) : sameChannelSteps.length > 1 ? (
                            <span className="mt-2 block text-pretty font-medium leading-5 text-slate-500">Один выбор применяется к шагам {sameChannelSteps.join(' и ')}.</span>
                          ) : null}
                        </label>
                      ) : (
                        <div className="mt-3 border-t border-slate-100 pt-3 text-pretty text-xs font-medium leading-5 text-slate-500">Отправляется вручную — аккаунт выбирать не нужно.</div>
                      )}
                    </div>
                    );
                  })}
                </div>

                <div className="mt-3">
                  <OutreachScheduleCalendar
                    touches={outreachCalendarTouches}
                    modeLabel={savedOutreachCampaign ? `Сохранённая версия ${savedOutreachCampaign.version || 1}` : 'Новая версия'}
                  />
                </div>

                {['max', 'whatsapp', 'sms', 'phone', 'manual', 'vk_manual'].includes(sequenceChannels[0]) ? (
                  <div className="mt-3 rounded-md bg-sky-50 px-3 py-3 text-pretty text-sm leading-6 text-sky-900">
                    Первое касание выполняется вручную. Кампания подождёт вашей отметки и через 48 часов перейдёт в «Нужно внимание» — автоматическое продолжение не начнётся скрытно.
                  </div>
                ) : null}

                <div id="outreach-preview-result" className="scroll-mt-28" aria-live="polite">
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
                  </div>
                ) : null}

                {outreachPreview?.status === 'observe' ? (
                  <div className="mt-3 rounded-md bg-amber-50 px-4 py-4 text-sm text-amber-950 ring-1 ring-inset ring-amber-200">
                    <div className="font-semibold">Цепочка пока не создана</div>
                    <p className="mt-1 text-pretty leading-6 text-amber-900">Не подтверждено, чем компании полезны друг другу. LocalOS не будет подставлять общий шаблон: обновите данные карточки, создайте аудит и проверьте совместимость или сохраните конкретную идею сотрудничества.</p>
                    <Button type="button" variant="outline" onClick={() => scrollToLeadSection('lead-research')} className="mt-3 min-h-10 border-amber-200 bg-white text-amber-950">
                      Проверить основание обращения
                    </Button>
                  </div>
                ) : null}
                {outreachPreview?.status === 'needs_contact' ? (
                  <div className="mt-3 rounded-md bg-amber-50 px-4 py-4 text-sm text-amber-950 ring-1 ring-inset ring-amber-200">
                    <div className="font-semibold">Цепочка пока не создана</div>
                    <p className="mt-1 text-pretty leading-6 text-amber-900">Не выбран подходящий получатель. Найдите или добавьте контакт компании, затем выберите его для первого сообщения.</p>
                    <Button type="button" variant="outline" onClick={() => scrollToLeadSection('lead-contacts')} className="mt-3 min-h-10 border-amber-200 bg-white text-amber-950">
                      Выбрать получателя
                    </Button>
                  </div>
                ) : null}
                {outreachPreview?.status === 'needs_sender_setup' ? (
                  <div className="mt-3 rounded-md bg-amber-50 px-4 py-4 text-sm text-amber-950 ring-1 ring-inset ring-amber-200">
                    <div className="font-semibold">Цепочка пока не создана</div>
                    <p className="mt-1 text-pretty leading-6 text-amber-900">Для выбранных каналов не готов отправитель или не заполнен обязательный профиль отправителя.</p>
                    <Button type="button" variant="outline" onClick={() => scrollToLeadSection('sender-settings')} className="mt-3 min-h-10 border-amber-200 bg-white text-amber-950">
                      Настроить отправителя
                    </Button>
                  </div>
                ) : null}
                {['suppressed', 'excluded'].includes(String(outreachPreview?.status || '')) ? (
                  <div className="mt-3 rounded-md bg-rose-50 px-4 py-4 text-sm text-rose-950 ring-1 ring-inset ring-rose-200">
                    <div className="font-semibold">Цепочка не создаётся</div>
                    <p className="mt-1 text-pretty leading-6 text-rose-900">Лид исключён из аутрича из-за ответа, запрета на контакт или терминального состояния. Это ограничение сильнее выбранных каналов.</p>
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

                {displayedOutreachTouches.length > 0 ? (
                  <div className="mt-3 flex flex-wrap items-center justify-between gap-3 rounded-md bg-sky-50 px-3 py-3 text-sm leading-6 text-sky-900">
                    <span>Тексты и их проверка находятся в разделе «Сообщения и каналы».</span>
                    <Button type="button" variant="outline" onClick={() => scrollToLeadSection('lead-conversation')} className="min-h-10 bg-white">
                      Открыть сообщения
                    </Button>
                  </div>
                ) : null}
                </div>

                <div className="mt-3 grid gap-2 sm:grid-cols-2">
                  {savedOutreachCampaign && !campaignSetupDirty ? (
                    <Button variant="outline" onClick={() => void reviewSavedTouchEdits()} disabled={Boolean(busyAction) || hasTouchEdits} className="min-h-11 bg-white">
                      {busyAction === 'review-saved-edits' ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : <ShieldCheck className="mr-2 h-4 w-4" />}
                      Проверить сохранённые сообщения
                    </Button>
                  ) : savedOutreachCampaign && campaignSetupDirty ? (
                    <Button onClick={() => void prepareOutreachCampaign(true)} disabled={Boolean(busyAction) || !outreachStartIso(sequenceStartAt)} className="min-h-11 bg-slate-950 text-white transition-transform duration-150 active:scale-[0.96] hover:bg-slate-800 sm:col-span-2">
                      {busyAction === 'save-campaign' ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : <ShieldCheck className="mr-2 h-4 w-4" />}
                      Проверить и сохранить изменения
                    </Button>
                  ) : (
                    <Button variant="outline" onClick={() => void prepareOutreachCampaign(false)} disabled={busyAction === 'preview-campaign' || !outreachStartIso(sequenceStartAt)} className="min-h-11 bg-white">
                      {busyAction === 'preview-campaign' ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : <Sparkles className="mr-2 h-4 w-4" />}
                      Подготовить цепочку
                    </Button>
                  )}
                  {!savedOutreachCampaign ? (
                    <Button variant="outline" onClick={() => void prepareOutreachCampaign(true)} disabled={busyAction === 'save-campaign' || !outreachStartIso(sequenceStartAt) || !['ready', 'needs_channel_setup', 'needs_evidence', 'needs_revision'].includes(String(outreachPreview?.status || ''))} className="min-h-11 bg-white">
                      {busyAction === 'save-campaign' && <RefreshCw className="mr-2 h-4 w-4 animate-spin" />}
                      Сохранить цепочку
                    </Button>
                  ) : null}
                </div>
                <p className="mt-2 text-pretty text-xs leading-5 text-slate-500">
                  Сохранятся тексты, каналы и расписание. Ничего не будет отправлено.
                </p>
                {campaignSetupDirty ? (
                  <div className="mt-3 rounded-md bg-amber-50 px-3 py-3 text-sm leading-6 text-amber-950 ring-1 ring-inset ring-amber-200">
                    <div className="font-semibold">Настройки новой версии ещё не сохранены</div>
                    <p className="mt-1 text-pretty text-amber-900">Сохранённая цепочка остаётся в истории. Календарь уже показывает новые параметры, но подтверждение и отправка заблокированы до проверки и сохранения новой версии.</p>
                  </div>
                ) : null}
                {savedOutreachCampaign?.status === 'draft' ? (
                  <Button onClick={() => void approveOutreachCampaign()} disabled={busyAction === 'approve-campaign' || campaignSetupDirty || savedOutreachCampaign.requires_regeneration || savedCampaignNeedsChannelSetup || !savedCampaignQualityPassed || savedCampaignHasPendingReview} className="mt-2 min-h-11 w-full bg-orange-500 text-white hover:bg-orange-600">
                    {busyAction === 'approve-campaign' ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : <ShieldCheck className="mr-2 h-4 w-4" />}
                    {campaignSetupDirty
                      ? 'Сначала сохраните новую версию'
                      : savedCampaignHasPendingReview
                        ? 'Сначала проверьте сохранённые сообщения'
                        : !savedCampaignQualityPassed
                          ? 'Сначала исправьте сообщения с замечаниями'
                      : savedOutreachCampaign.requires_regeneration
                      ? 'Сначала подготовьте новую цепочку'
                      : savedCampaignNeedsChannelSetup
                        ? 'Сначала настройте каналы и отправителя'
                        : 'Утвердить цепочку и перейти к отправке'}
                  </Button>
                ) : null}
                {savedOutreachCampaign?.status === 'draft' && !campaignSetupDirty ? (
                  <p className="mt-2 text-pretty text-center text-xs leading-5 text-slate-500">
                    После нажатия статус изменится с «Черновик» на «Подтверждена». Автоматические касания будут поставлены в очередь на указанные даты; перед каждым LocalOS ещё раз проверит разрешения, ответы, исключения и лимиты.
                  </p>
                ) : null}
                <p className="mt-2 text-xs leading-5 text-slate-500">Перед каждым касанием LocalOS повторно проверит approval версии, sender account, разрешение, ответ, suppression, cooldown и дневной лимит.</p>
              </section>
              </LeadDrawerSection>

              <LeadDrawerSection
                key={`sender-${selectedWorkstream.id || 'legacy'}-${selectedSenderScope}`}
                id="sender-settings"
                title="Отправитель и подключения"
                description={connectedEmailSender?.sender_identity
                  ? `${connectedEmailSender.sender_identity} · ${connectedEmailReady ? 'готов к отправке' : 'нужно проверить разрешение'}`
                  : `${selectedSenderLabel} · email не подключён`}
                status={connectedEmailReady ? 'Готово' : 'Нужно действие'}
              >
              <div className="rounded-md bg-slate-50 p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="text-xs font-semibold uppercase tracking-[0.1em] text-slate-500">Отправитель</div>
                    <div className="mt-1 font-semibold text-slate-950">{selectedSenderLabel}</div>
                    <div className="mt-1 text-sm font-medium text-slate-700">
                      {senderAccountsLoading ? 'Проверяем email…' : connectedEmailSender?.sender_identity || 'Email пока не подключён'}
                    </div>
                  </div>
                  <Badge variant="outline" className={readyChannelCount > 0
                    ? 'border-emerald-200 bg-emerald-50 text-emerald-800'
                    : 'border-amber-200 bg-amber-50 text-amber-800'}>
                    {outreachPreview
                      ? readyChannelCount > 0 ? `Готово каналов: ${readyChannelCount}` : 'Нужно подключение'
                      : 'Проверьте каналы'}
                  </Badge>
                </div>
                <p className="mt-2 text-pretty text-sm leading-6 text-slate-600">Telegram и email выбираются только из этого контура. Для VK можно выбрать автоматическую отправку от подключённого сообщества или ручную отправку по найденной ссылке. MAX и WhatsApp пока выполняются вручную.</p>
                <details className="mt-3 border-t border-slate-200 pt-2">
                  <summary className="flex min-h-11 cursor-pointer items-center text-sm font-semibold text-slate-700">Проверить или заменить email отправителя</summary>
                  <div className="pt-3">
                    <OutreachEmailSetup
                      scopeType={selectedSenderScope}
                      businessId={selectedSenderScope === 'business' ? selectedWorkstream.client_business_id : null}
                      compact
                      onChanged={() => {
                        void loadSenderAccounts();
                        setOutreachPreview(null);
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
                <a
                  href={`/dashboard/settings/integrations?focus=outreach_vk&sender_scope=${selectedSenderScope}&return_to=${encodeURIComponent(`/dashboard/bazich?lead=${selectedLead.id}&workstream=${selectedWorkstream.id || ''}`)}`}
                  className="ml-4 inline-flex min-h-10 items-center gap-2 text-sm font-semibold text-orange-700 transition-colors hover:text-orange-800"
                >
                  Разрешить отправку в VK
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
                          <div className="font-semibold text-slate-900">
                            {usesPlatformSender
                              ? 'Профиль Александра и LocalOS'
                              : 'Профиль отправителя этого бизнеса'}
                          </div>
                          <p className="mt-1 text-pretty text-xs leading-5 text-slate-600">
                            {usesPlatformSender
                              ? 'В этом режиме факты об Александре и LocalOS не попадают в сообщение: текст строится от лица выбранного бизнеса.'
                              : 'Профиль используется только в кампаниях этого бизнеса. Его факты не смешиваются с профилями других отправителей.'}
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
                    {senderMode === 'localos_for_partner' ? (
                      <div className="rounded-lg border border-sky-200 bg-sky-50 px-3 py-3 text-pretty text-xs leading-5 text-sky-950">
                        Сообщение будет написано от лица «{selectedWorkstream.client_business_name || 'бизнеса клиента'}». Название, категория, услуги, аудитория и география берутся из карточки бизнеса, аудита и проверки совместимости. Профиль Александра и LocalOS во внешний текст не подставляется.
                      </div>
                    ) : null}
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
                    <textarea value={senderOutcome} onChange={(event) => setSenderOutcome(event.target.value)} placeholder={`Какой конкретный результат даёт ${usesPlatformSender ? 'LocalOS' : senderBusinessLabel}`} rows={2} className="w-full resize-y rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 outline-none focus:border-slate-400" />
                    <textarea value={senderAudience} onChange={(event) => setSenderAudience(event.target.value)} placeholder="Целевая аудитория и её контекст" rows={2} className="w-full resize-y rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 outline-none focus:border-slate-400" />
                    <div className="grid gap-2 sm:grid-cols-2">
                      <textarea value={senderSegments} onChange={(event) => setSenderSegments(event.target.value)} placeholder="ICP / сегменты — по одному на строку" rows={3} className="w-full resize-y rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 outline-none focus:border-slate-400" />
                      <textarea value={senderRecipientRoles} onChange={(event) => setSenderRecipientRoles(event.target.value)} placeholder="Роли получателей — по одной на строку" rows={3} className="w-full resize-y rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 outline-none focus:border-slate-400" />
                    </div>
                    <Input value={senderGeography} onChange={(event) => setSenderGeography(event.target.value)} placeholder="География поиска" className="h-10 bg-white" />
                    {selectedWorkstream.workstream_type === 'client_partnership' && !usesPlatformSender ? <textarea value={senderPartnerTypes} onChange={(event) => setSenderPartnerTypes(event.target.value)} placeholder="Желаемые типы партнёров — по одному на строку" rows={2} className="w-full resize-y rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 outline-none focus:border-slate-400" /> : null}
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
              </LeadDrawerSection>

              <LeadDrawerSection
                id="campaign-status"
                title="Состояние кампании"
                description={campaignStatusDescription}
                status={campaignStatusLabel}
                defaultOpen={Boolean(savedOutreachCampaign?.status === 'approved')}
              >
                {campaignStatusItems.length > 0 ? (
                  <div className="divide-y divide-slate-200 overflow-hidden rounded-xl bg-slate-50 shadow-sm shadow-slate-900/5">
                    {campaignStatusItems.map((item) => (
                      <div key={item.id} className="flex flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
                        <div className="min-w-0">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="text-sm font-semibold text-slate-950">Шаг {item.sequenceIndex + 1} · {item.channelLabel}</span>
                            <Badge variant="outline" className={outreachStatusTone(item.status)}>
                              {item.statusLabel}
                            </Badge>
                          </div>
                          {item.moment ? (
                            <div className="mt-1 text-xs text-slate-500 tabular-nums">
                              {item.sent ? 'Отправлено' : item.status === 'awaiting_manual_send' ? 'Сделать вручную' : 'Запланировано'} {item.moment}
                            </div>
                          ) : null}
                          {item.providerMessageId ? (
                            <div className="mt-1 truncate text-xs text-slate-400">ID отправки: {item.providerMessageId}</div>
                          ) : null}
                          {item.errorText ? (
                            <div className="mt-1 text-pretty text-xs leading-5 text-rose-700">{item.errorText}</div>
                          ) : null}
                        </div>
                        <div className="flex shrink-0 flex-wrap items-center gap-2">
                          {item.verificationHref ? (
                            <a
                              href={item.verificationHref}
                              target="_blank"
                              rel="noreferrer"
                              className="inline-flex min-h-10 items-center gap-2 text-sm font-semibold text-orange-700 transition-colors hover:text-orange-800"
                            >
                              {item.verificationLabel}
                              <ExternalLink className="h-4 w-4" />
                            </a>
                          ) : null}
                          {!automaticOutreachChannels.has(item.channel)
                            && ['awaiting_manual_send', 'needs_attention', 'manual_expired'].includes(item.status) ? (
                              <>
                                <Button
                                  type="button"
                                  size="sm"
                                  onClick={() => void recordManualTouchEvent(item, 'sent')}
                                  disabled={busyAction.startsWith(`manual-touch-${item.id}-`)}
                                >
                                  Отметить отправленным
                                </Button>
                                <Button
                                  type="button"
                                  size="sm"
                                  variant="outline"
                                  onClick={() => void recordManualTouchEvent(item, 'skipped')}
                                  disabled={busyAction.startsWith(`manual-touch-${item.id}-`)}
                                >
                                  Пропустить
                                </Button>
                              </>
                            ) : null}
                          {!automaticOutreachChannels.has(item.channel)
                            && ['manual_sent', 'sent', 'delivered'].includes(item.status) ? (
                              <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                onClick={() => void recordManualTouchEvent(item, 'reply')}
                                disabled={busyAction.startsWith(`manual-touch-${item.id}-`)}
                              >
                                Записать ответ
                              </Button>
                            ) : null}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="rounded-xl bg-slate-50 px-4 py-4 text-sm leading-6 text-slate-600">
                    Касаний пока нет. Сохраните цепочку — здесь появятся даты, каналы и состояние каждого шага.
                  </div>
                )}
                <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                  <p className="text-pretty text-xs leading-5 text-slate-500">
                    Автоматические касания выполняются по графику. Любой ответ или исключение останавливает следующие шаги до отправки.
                  </p>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => void reloadLatestOutreachCampaign()}
                    disabled={Boolean(busyAction)}
                    className="min-h-10 shrink-0 bg-white"
                  >
                    <RefreshCw className="mr-2 h-4 w-4" />
                    Обновить статус
                  </Button>
                </div>
                {canSyncPilotReply ? (
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => void syncPilotReply()}
                    disabled={Boolean(busyAction)}
                    className="mt-2 min-h-10 w-full bg-white"
                  >
                    <RefreshCw className={`mr-2 h-4 w-4 ${busyAction === 'pilot-reply-sync' ? 'animate-spin' : ''}`} />
                    Проверить ответ сейчас
                  </Button>
                ) : null}
              </LeadDrawerSection>

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
                <summary className="min-h-10 cursor-pointer text-sm font-semibold text-slate-700">Исключения из контактов</summary>
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
