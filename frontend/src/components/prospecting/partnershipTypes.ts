export type PartnershipLead = {
  id: string;
  name?: string;
  address?: string;
  city?: string;
  category?: string;
  source_url?: string;
  source?: string;
  source_kind?: string;
  source_provider?: string;
  client_business_name?: string;
  external_place_id?: string;
  external_source_id?: string;
  dedupe_key?: string;
  lat?: number;
  lon?: number;
  search_payload_json?: Record<string, unknown> | null;
  enrich_payload_json?: {
    provider?: string;
    found_fields?: string[];
    confidence?: Record<string, number>;
    contacts?: Record<string, string | null>;
    raw?: Record<string, unknown>;
  } | null;
  matched_sources_json?: string[] | null;
  phone?: string;
  email?: string;
  website?: string;
  telegram_url?: string;
  whatsapp_url?: string;
  status?: string;
  partnership_stage?: string;
  pipeline_status?: string;
  catalog_shortlisted?: boolean;
  pilot_cohort?: string;
  selected_channel?: string;
  active_workstream_id?: string | null;
  workstream_id?: string | null;
  workstream_lifecycle_status?: string | null;
  workstream_status_reason?: string | null;
  sales_room_status?: string;
  sales_room_data_mode?: string;
  sales_room_url?: string;
  contact_guard?: {
    blocked?: boolean;
    reason?: string | null;
    display_status?: string;
    warning?: string | null;
    last_contact_at?: string | null;
    last_contact_channel?: string | null;
    last_message_excerpt?: string | null;
  };
  updated_at?: string;
  rating?: number;
  reviews_count?: number;
  parse_task_id?: string;
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
  } | null;
  artifact_updated_at?: string;
  deferred_reason?: string;
  deferred_until?: string;
  next_best_action?: {
    code?: string;
    label?: string;
    hint?: string;
    priority?: 'low' | 'medium' | 'high';
  };
};

export type PartnershipDraft = {
  id: string;
  lead_id: string;
  created_at?: string;
  lead_name?: string;
  channel?: string;
  status?: string;
  lead_status?: string;
  lead_pipeline_status?: string;
  lead_partnership_stage?: string;
  generated_text?: string;
  edited_text?: string;
  approved_text?: string;
  updated_at?: string;
  email?: string;
  recipient?: string;
  recipient_name?: string;
  sender_name?: string;
  scheduled_at?: string;
  review_digest?: string;
};

export type PartnershipBatch = {
  id: string;
  status: string;
  batch_date?: string;
  created_at?: string;
  updated_at?: string;
  items?: Array<{
    id: string;
    lead_id?: string;
    lead_name?: string;
    delivery_status?: string;
    error_text?: string;
    channel?: string;
    latest_outcome?: string | null;
    latest_human_outcome?: string | null;
    latest_raw_reply?: string | null;
  }>;
};

export type PartnershipReaction = {
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

export type PartnershipLearningMetric = {
  capability: string;
  accepted_total: number;
  accepted_raw_total: number;
  accepted_edited_total: number;
  accepted_raw_pct: number;
  edited_before_accept_pct: number;
};

export type PartnershipHealth = {
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

export type PartnershipFunnelStage = {
  key: string;
  label: string;
  count: number;
  conversion_from_prev_pct?: number;
};

export type PartnershipFunnel = {
  window_days?: number;
  funnel?: PartnershipFunnelStage[];
  summary?: {
    work_to_contact_pct?: number;
    reply_to_conversion_pct?: number;
    total_count?: number;
    contacted_count?: number;
    converted_count?: number;
  };
};

export type PartnershipOutcomeSummary = {
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

export type PartnershipOutcomes = {
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

export type PartnershipSourceQualityItem = {
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

export type PartnershipSourceQuality = {
  window_days?: number;
  items?: PartnershipSourceQualityItem[];
};

export type PartnershipBlocker = {
  key: string;
  label: string;
  count: number;
  severity?: 'info' | 'warning' | 'danger';
  hint?: string;
};

export type PartnershipBlockers = {
  window_days?: number;
  summary?: Record<string, number>;
  blockers?: PartnershipBlocker[];
};

export type PartnershipRalphLoop = {
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
