
export type WorkstreamType = 'localos_sales' | 'client_partnership' | 'creator_collaboration';

export type SenderMode = 'localos' | 'partner_business' | 'localos_for_partner';

export interface WorkstreamState {
  code?: string;
  label?: string;
  url?: string | null;
}

export interface WorkstreamAction {
  code?: string;
  label?: string;
}

export interface RelationshipStage {
  code?: 'preparing_first_touch' | 'touch_sent' | 'responded' | 'response_touch_unknown';
  label?: string;
  touch_number?: number;
  channel?: string | null;
  occurred_at?: string | null;
}

export interface ReadinessCheck {
  code?: string;
  label?: string;
  passed?: boolean;
}

export interface ReadinessGate {
  code?: 'ready' | 'needs_attention';
  label?: string;
  checks?: ReadinessCheck[];
  blockers?: string[];
}

export interface ResearchSource {
  title?: string;
  url?: string;
  source_type?: string;
  published_at?: string;
}

export interface WorkstreamResearch {
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

export interface ContactPoint {
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

export interface MessageReadiness {
  code?: 'ready' | 'needs_contact' | 'needs_facts' | 'needs_evidence' | 'suppressed';
  label?: string;
  missing?: string[];
  missing_items?: Array<{
    code?: string;
    label?: string;
  }>;
}

export interface EnrichmentState {
  id?: string;
  status?: string;
  phase?: string;
  error?: string | null;
  updated_at?: string;
}

export const outreachDefaultsForWorkstream = (workstreamType?: string) => {
  if (workstreamType === 'creator_collaboration') {
    return {
      senderMode: 'localos_for_partner' as SenderMode,
      sequenceChannels: ['email'],
      sequenceDays: [0],
    };
  }
  return {
    senderMode: (workstreamType === 'localos_sales' ? 'localos' : 'partner_business') as SenderMode,
    sequenceChannels: ['telegram', 'email', 'max', 'vk'],
    sequenceDays: [0, 3, 7, 12],
  };
};

export interface LeadWorkstream {
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

export const workstreamLabel = (workstream: LeadWorkstream) => {
  if (workstream.workstream_type === 'localos_sales') {
    return 'Лид LocalOS';
  }
  if (workstream.workstream_type === 'creator_collaboration') {
    return 'Автор LocalOS';
  }
  return `Лид-партнёр · ${workstream.client_business_name || 'клиент'}`;
};
