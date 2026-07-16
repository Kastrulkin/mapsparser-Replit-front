export type ScopeOption = {
  scope_type: string;
  scope_target_id: string;
  label: string;
  city?: string;
  address?: string;
  is_parent?: boolean;
  is_current?: boolean;
};

export type ContextPayload = {
  business?: {
    id?: string;
    name?: string;
    city?: string;
  };
  scope?: {
    scope_type?: string;
    scope_target_id?: string;
    scope_options?: ScopeOption[];
    selected_scope_label?: string;
    selected_scope_description?: string;
    network?: {
      is_network?: boolean;
      locations_count?: number;
      has_parent_scope?: boolean;
    };
  };
  subscription?: {
    tier?: string;
    allowed_horizons?: number[];
    automation_access?: boolean;
    reason?: string | null;
  };
  services?: Array<{ id: string; name: string }>;
  seo_keywords?: Array<{ keyword: string; views?: number }>;
  sales_signals?: Array<{ title: string; amount?: number }>;
  recent_news?: Array<{ id: string; text: string }>;
  audit_signals?: Array<{ title?: string; problem?: string }>;
  readiness?: {
    map_links_count?: number;
    has_map_links?: boolean;
    has_services?: boolean;
    has_seo_keywords?: boolean;
    has_sales_signals?: boolean;
    has_audit_signals?: boolean;
    missing_inputs?: string[];
    is_grounded_for_search?: boolean;
  };
};

export type PlanItem = {
  id: string;
  scheduled_for: string;
  theme: string;
  goal: string;
  source_kind: string;
  source_ref: string;
  seo_keyword: string;
  seo_views?: number;
  draft_text: string;
  status: string;
  usernews_id: string;
  content_type: string;
  business_id?: string;
  location_scope?: string;
  location_label?: string;
  location_city?: string;
  location_address?: string;
};

export type PlanPayload = {
  id: string;
  title: string;
  period_days: number;
  scope_type: string;
  scope_target_id: string;
  scope_target_label?: string;
  scope_target_city?: string;
  scope_target_address?: string;
  plan_status?: string;
  period_start?: string;
  period_end?: string;
  items: PlanItem[];
  items_count?: number;
  needs_draft_count?: number;
  ready_count?: number;
  news_count?: number;
  skipped_count?: number;
  created_at?: string;
  updated_at?: string;
};

export type SocialPost = {
  id: string;
  business_id?: string;
  content_plan_id?: string;
  content_plan_item_id: string;
  platform: string;
  platform_label?: string;
  publish_mode: string;
  status: string;
  scheduled_for?: string;
  approved_at?: string;
  published_at?: string;
  base_text?: string;
  platform_text?: string;
  provider_post_id?: string;
  provider_post_url?: string;
  automation_task_id?: string;
  last_error?: string;
  next_action?: string;
  schedule_attention?: {
    schema?: string;
    status?: string;
    requires_attention?: boolean;
    scheduled_for_is_past?: boolean;
    message_ru?: string;
    message_en?: string;
    next_action_ru?: string;
    next_action_en?: string;
  };
  publish_evidence?: SocialPublishEvidence;
  metadata_json?: SocialPostMetadata;
  views?: number;
  reach?: number;
  likes?: number;
  comments?: number;
  shares?: number;
  clicks?: number;
  inquiries?: number;
  leads?: number;
};

export type SocialPublishEvidence = {
  tone?: string;
  title_ru?: string;
  title_en?: string;
  summary_ru?: string;
  summary_en?: string;
  next_action_ru?: string;
  next_action_en?: string;
  proof_url?: string;
  proof_id?: string;
  automation_task_id?: string;
  provider_status?: string;
  proof_source?: string;
  proof_quality?: string;
  ready_for_metrics?: boolean;
  ready_for_attribution?: boolean;
  external_publish_proven?: boolean;
  manual_confirmation?: boolean;
  last_error?: string;
  target_url?: string;
  profile_hint?: string;
  copy_ready_text?: string;
  manual_checklist_ru?: string[];
  manual_checklist_en?: string[];
  stop_before_final_publish?: boolean;
  browser_final_click_allowed?: boolean;
  placement_packet?: {
    schema?: string;
    platform_label?: string;
    status?: string;
    mode?: string;
    target_url?: string;
    target_ready?: boolean;
    profile_hint?: string;
    copy_ready?: boolean;
    copy_ready_text?: string;
    checklist_ru?: string[];
    checklist_en?: string[];
    handoff_checklist_ru?: string[];
    handoff_checklist_en?: string[];
    checklist_count?: number;
    automation_task_id?: string;
    openclaw_task_requested?: boolean;
    openclaw_outbox_id?: string;
    agent_action_ledger_id?: string;
    manual_fallback_required?: boolean;
    stop_before_final_publish?: boolean;
    browser_final_click_allowed?: boolean;
    final_publish_policy?: string;
    completion_required_fields?: string[];
    done_criteria_ru?: string[];
    done_criteria_en?: string[];
    preview_required?: boolean;
    operator_next_action_ru?: string;
    operator_next_action_en?: string;
    owner_next_action_ru?: string;
    owner_next_action_en?: string;
  };
  result_packet?: {
    schema?: string;
    status?: string;
    primary_metric_ru?: string;
    primary_metric_en?: string;
    primary_result_total?: number;
    early_signal_total?: number;
    leads?: number;
    inquiries?: number;
    comments?: number;
    shares?: number;
    clicks?: number;
    likes?: number;
    views?: number;
    reach?: number;
    ready_for_recommendation?: boolean;
    owner_next_action_ru?: string;
    owner_next_action_en?: string;
  };
  recoverable?: boolean;
};

export type SocialPublishRehearsal = {
  schema?: string;
  dry_run?: boolean;
  post_id?: string;
  platform?: string;
  platform_label?: string;
  publish_mode?: string;
  current_status?: string;
  ready_for_execution?: boolean;
  external_publish_performed?: boolean;
  provider_write_performed?: boolean;
  would_external_publish?: boolean;
  would_create_supervised_task?: boolean;
  browser_final_click_allowed?: boolean;
  stop_before_final_publish?: boolean;
  summary_ru?: string;
  summary_en?: string;
  next_action_ru?: string;
  next_action_en?: string;
  blockers?: Array<{
    code?: string;
    message_ru?: string;
    message_en?: string;
  }>;
  dispatch_decision?: {
    dispatch_action?: string;
    action_label_ru?: string;
    action_label_en?: string;
    would_status?: string;
    reason_label_ru?: string;
    reason_label_en?: string;
    safety_summary_ru?: string;
    safety_summary_en?: string;
  };
};

export type SocialPublishRehearsalBulk = {
  schema?: string;
  dry_run?: boolean;
  external_publish_performed?: boolean;
  provider_write_performed?: boolean;
  rehearsals?: SocialPublishRehearsal[];
  failed?: Array<{
    id?: string;
    error?: string;
  }>;
  summary?: {
    status?: string;
    total?: number;
    ready?: number;
    blocked?: number;
    failed?: number;
    api_ready?: number;
    supervised_ready?: number;
    manual_or_blocked?: number;
    browser_final_click_allowed?: boolean;
    message_ru?: string;
    message_en?: string;
    next_action_ru?: string;
    next_action_en?: string;
  };
};

export type SocialOpenClawCapabilityStatus = {
  ready?: boolean;
  status?: string;
  source?: string;
  reason?: string;
  action_ref?: string;
  capability?: string;
  error?: string;
};

export type SocialOpenClawReadiness = {
  ready?: boolean;
  handoff_ready?: boolean;
  status?: string;
  capability?: string;
  action_ref?: string;
  source?: string;
  provider_status?: string;
  reason?: string;
  browser_final_click_allowed?: boolean;
  stop_before_final_publish?: boolean;
  requires_final_human_confirmation?: boolean;
  side_effect_policy?: string;
  final_publish_policy?: string;
  allowed_actions?: string[];
  forbidden_actions?: string[];
  manual_fallback_triggers?: string[];
  diagnostics_ru?: string[];
  diagnostics_en?: string[];
  delivery_readiness?: {
    ready?: boolean;
    status?: string;
    callback_configured?: boolean;
    callback_url_configured?: boolean;
    callback_env_var?: string;
    suggested_callback_url?: string;
    suggested_callback_blocked_reason?: string;
    outbox_available?: boolean | null;
    message_ru?: string;
    message_en?: string;
    next_action_ru?: string;
    next_action_en?: string;
  };
  message_ru?: string;
  message_en?: string;
  next_action_ru?: string;
  next_action_en?: string;
};

export type SocialSupervisedSafetyContract = {
  allowed_actions?: string[];
  forbidden_actions?: string[];
  manual_fallback_triggers?: string[];
};

export type SocialPostMetadata = {
  supervised_publish?: {
    handoff_state?: {
      state?: string;
      openclaw_ready?: boolean;
      task_payload_ready?: boolean;
      openclaw_task_requested?: boolean;
      openclaw_outbox_id?: string;
      ledger_recorded?: boolean;
      ledger_id?: string;
      owner_status_ru?: string;
      owner_status_en?: string;
      owner_next_action_ru?: string;
      owner_next_action_en?: string;
      final_publish_policy?: string;
      browser_final_click_allowed?: boolean;
    };
    instruction_ru?: string;
    instruction_en?: string;
    manual_instruction_ru?: string;
    manual_instruction_en?: string;
    operator_next_action_ru?: string;
    operator_next_action_en?: string;
    handoff_checklist_ru?: string[];
    handoff_checklist_en?: string[];
    manual_checklist_ru?: string[];
    manual_checklist_en?: string[];
    manual_handoff?: {
      instruction_ru?: string;
      instruction_en?: string;
      checklist_ru?: string[];
      checklist_en?: string[];
      copy_ready_text?: string;
      target_url?: string;
      profile_hint?: string;
      reason?: string;
    };
    copy_ready_text?: string;
    profile_hint?: string;
    platform_label?: string;
    mode?: string;
    capability?: string;
    openclaw_action_ref?: string;
    task_status?: string;
    target_url?: string;
    target_url_source?: string;
    final_publish_policy?: string;
    fallback_reasons?: string[];
    openclaw_capability_status?: string | SocialOpenClawCapabilityStatus;
    stop_before_final_publish?: boolean;
    safety_contract?: SocialSupervisedSafetyContract;
  };
  openclaw_task?: Record<string, unknown>;
  agent_action_ledger_id?: string;
  queue_preflight_ready?: boolean;
  queue_preflight_status?: string;
  queue_preflight_message_ru?: string;
  queue_preflight_message_en?: string;
  provider_status?: string;
  provider_note?: string;
};

export type SocialPostsSummary = {
  total?: number;
  needs_review?: number;
  scheduled?: number;
  needs_supervised_publish?: number;
  needs_manual_publish?: number;
  published?: number;
  failed?: number;
  by_status?: Record<string, number>;
};

export type SocialRecommendationPayload = {
  recommendation?: {
    primary_metric?: string;
    text_ru?: string;
    text_en?: string;
    leads?: number;
    inquiries?: number;
    comments?: number;
    reach?: number;
    winning_topics?: SocialRecommendationTopicInsight[];
    weak_channels?: SocialRecommendationChannelInsight[];
    no_result_topics?: SocialRecommendationTopicInsight[];
    owner_next_steps?: Array<{
      key?: string;
      priority?: number;
      ru?: string;
      en?: string;
    }>;
    cta_suggestions?: SocialRecommendationTextSuggestion[];
    frequency_suggestions?: SocialRecommendationTextSuggestion[];
    signal_priority?: Array<{
      key?: string;
      rank?: number;
      value?: number;
      label_ru?: string;
      label_en?: string;
      role_ru?: string;
      role_en?: string;
    }>;
  };
  learning_readiness?: SocialLearningReadiness;
  application_preview?: {
    schema?: string;
    scope?: string;
    total?: number;
    applicable_count?: number;
    skipped_count?: number;
    summary_ru?: string;
    summary_en?: string;
    items?: Array<{
      item_id?: string;
      theme?: string;
      applicable?: boolean;
      skip_reason?: string;
      status?: string;
      scheduled_for?: string;
      has_news?: boolean;
      label_ru?: string;
      label_en?: string;
    }>;
  };
  proposed_changes?: Array<{
    item_id?: string;
    theme?: string;
    action?: string;
    reason_ru?: string;
    reason_en?: string;
    current_goal?: string;
    proposed_goal?: string;
    metrics?: {
      leads?: number;
      inquiries?: number;
      comments?: number;
      reach?: number;
    };
    channel_breakdown?: {
      summary_ru?: string;
      summary_en?: string;
      best_channels?: SocialRecommendationChannelInsight[];
      weak_channels?: SocialRecommendationChannelInsight[];
    };
  }>;
};

export type SocialLearningReadiness = {
  status?: string;
  confidence?: string;
  total_posts?: number;
  published_posts?: number;
  posts_with_primary_result?: number;
  posts_with_early_signal?: number;
  primary_signal_total?: number;
  secondary_signal_total?: number;
  early_signal_total?: number;
  leads?: number;
  inquiries?: number;
  comments?: number;
  shares?: number;
  clicks?: number;
  likes?: number;
  reach?: number;
  pending_manual_or_supervised_posts?: number;
  failed_posts?: number;
  primary_metric_ru?: string;
  primary_metric_en?: string;
  secondary_metric_ru?: string;
  secondary_metric_en?: string;
  early_metric_ru?: string;
  early_metric_en?: string;
  summary_ru?: string;
  summary_en?: string;
  next_action_ru?: string;
  next_action_en?: string;
  apply_blocked_reason_ru?: string;
  apply_blocked_reason_en?: string;
  safe_to_apply_recommendation?: boolean;
  checklist?: Array<{
    key?: string;
    status?: 'done' | 'current' | 'attention' | 'pending' | string;
    label_ru?: string;
    label_en?: string;
    detail_ru?: string;
    detail_en?: string;
  }>;
};

export type SocialRecommendationTopicInsight = {
  item_id?: string;
  theme?: string;
  action?: string;
  metrics?: {
    leads?: number;
    inquiries?: number;
    comments?: number;
    shares?: number;
    clicks?: number;
    reach?: number;
  };
};

export type SocialRecommendationChannelInsight = {
  platform?: string;
  platform_label?: string;
  reason_ru?: string;
  reason_en?: string;
  metrics?: {
    posts?: number;
    published?: number;
    failed?: number;
    manual?: number;
    leads?: number;
    inquiries?: number;
    comments?: number;
    reach?: number;
  };
};

export type SocialRecommendationTextSuggestion = {
  ru?: string;
  en?: string;
};

export type SocialQueueGroup = {
  key: string;
  label_ru?: string;
  label_en?: string;
  next_action_ru?: string;
  next_action_en?: string;
  count: number;
  post_ids?: string[];
  item_ids?: string[];
  platforms?: Record<string, number>;
};

export type SocialDispatchPreview = {
  dry_run?: boolean;
  picked?: number;
  skipped_no_access?: number;
  batch_size?: number;
  business_scope?: string;
  by_action?: Record<string, number>;
  readiness?: {
    status?: string;
    due_count?: number;
    external_publish_count?: number;
    controlled_count?: number;
    manual_count?: number;
    skipped_no_access?: number;
    has_external_publish?: boolean;
    has_controlled_tasks?: boolean;
    has_manual_fallback?: boolean;
    safe_dry_run?: boolean;
    external_publish_requires_approval?: boolean;
    browser_final_click_allowed?: boolean;
    message_ru?: string;
    message_en?: string;
    next_action_ru?: string;
    next_action_en?: string;
    recommended_dispatch_env?: Record<string, string>;
    first_cycle_steps?: Array<{
      key?: string;
      label_ru?: string;
      label_en?: string;
      count?: number;
      external_publish?: boolean;
      requires_approval?: boolean;
      stop_before_final_publish?: boolean;
      expected_status_ru?: string;
      expected_status_en?: string;
      description_ru?: string;
      description_en?: string;
    }>;
    first_cycle_verification?: SocialFirstCycleVerification;
    first_api_proof_candidate?: {
      schema?: string;
      ready?: boolean;
      id?: string;
      platform?: string;
      platform_label?: string;
      expected_status_ru?: string;
      expected_status_en?: string;
      proof_check_ru?: string;
      proof_check_en?: string;
      metrics_followup_ru?: string;
      metrics_followup_en?: string;
      required_proof_fields?: string[];
    };
    safety_notes_ru?: string[];
    safety_notes_en?: string[];
  };
  items?: Array<{
    id?: string;
    platform?: string;
    platform_label?: string;
    dispatch_action?: string;
    would_status?: string;
    reason?: string;
    action_label_ru?: string;
    action_label_en?: string;
    reason_label_ru?: string;
    reason_label_en?: string;
    safety_summary_ru?: string;
    safety_summary_en?: string;
    external_publish?: boolean;
    stop_before_final_publish?: boolean;
  }>;
};

export type SocialDispatchExecutionReport = {
  schema?: string;
  status?: string;
  picked?: number;
  published?: number;
  supervised?: number;
  manual?: number;
  failed?: number;
  business_scope?: string;
  external_publish_only_after_approval?: boolean;
  maps_are_supervised_or_manual?: boolean;
  browser_final_click_allowed?: boolean;
  provider_write_summary?: {
    api_publish_attempted?: boolean;
    published_with_provider_proof?: number;
    supervised_tasks_created?: number;
  };
  first_api_proof_summary?: {
    schema?: string;
    ready?: boolean;
    api_posts_checked?: number;
    published_api_posts?: number;
    published_with_provider_proof?: number;
    platform?: string;
    platform_label?: string;
    post_id?: string;
    provider_post_id?: string;
    provider_post_url?: string;
    last_error?: string;
    summary_ru?: string;
    summary_en?: string;
    next_action_ru?: string;
    next_action_en?: string;
    learning_actions?: Array<{
      key?: string;
      order?: number;
      enabled?: boolean;
      label_ru?: string;
      label_en?: string;
      summary_ru?: string;
      summary_en?: string;
      primary_metric?: boolean;
    }>;
  };
  after_run_proof_packet?: {
    schema?: string;
    status?: string;
    dispatch_status?: string;
    picked?: number;
    published?: number;
    supervised?: number;
    manual?: number;
    failed?: number;
    api_proof_ready?: boolean;
    can_collect_results?: boolean;
    maps_handoff_created?: boolean;
    browser_final_click_allowed?: boolean;
    primary_metric_ru?: string;
    primary_metric_en?: string;
    title_ru?: string;
    title_en?: string;
    next_action_ru?: string;
    next_action_en?: string;
    checks_ru?: string[];
    checks_en?: string[];
  };
  post_publish_learning_gate?: {
    schema?: string;
    status?: string;
    allowed?: boolean;
    can_collect_metrics?: boolean;
    can_record_attribution?: boolean;
    api_proof_ready?: boolean;
    published_posts?: number;
    published_with_api_proof?: number;
    manual_or_supervised_posts?: number;
    failed_posts?: number;
    primary_metric_ru?: string;
    primary_metric_en?: string;
    summary_ru?: string;
    summary_en?: string;
    next_action_ru?: string;
    next_action_en?: string;
  };
  details?: Array<{
    id?: string;
    platform?: string;
    status?: string;
    action?: string;
    automation_task_id?: string;
    provider_post_id?: string;
    provider_post_url?: string;
    last_error?: string;
  }>;
  errors?: Array<{
    id?: string;
    error?: string;
  }>;
  title_ru?: string;
  title_en?: string;
  summary_ru?: string;
  summary_en?: string;
  next_action_ru?: string;
  next_action_en?: string;
};

export type SocialFirstCycleVerification = {
  log_filter?: string;
  business_scope?: string;
  expected_statuses?: Array<{
    key?: string;
    label_ru?: string;
    label_en?: string;
    expected_ru?: string;
    expected_en?: string;
  }>;
  checks_ru?: string[];
  checks_en?: string[];
};

export type SocialLaunchRunbook = {
  ready?: boolean;
  scope?: string;
  status?: string;
  title_ru?: string;
  title_en?: string;
  summary_ru?: string;
  summary_en?: string;
  steps_ru?: string[];
  steps_en?: string[];
  success_criteria_ru?: string[];
  success_criteria_en?: string[];
  blocked_reason_ru?: string;
  blocked_reason_en?: string;
};

export type SocialMetricsLearningPacket = {
  schema?: string;
  status?: string;
  collected_posts?: number;
  failed_posts?: number;
  primary_metric_ru?: string;
  primary_metric_en?: string;
  primary_result_total?: number;
  early_signal_total?: number;
  leads?: number;
  inquiries?: number;
  comments?: number;
  shares?: number;
  clicks?: number;
  likes?: number;
  views?: number;
  safe_to_recommend_next_plan?: boolean;
  safe_to_apply_without_approval?: boolean;
  external_publish_performed?: boolean;
  summary_ru?: string;
  summary_en?: string;
  next_action_ru?: string;
  next_action_en?: string;
};

export type SocialTelegramPublishTargetProbe = {
  ready?: boolean;
  status?: string;
  message_ru?: string;
  message_en?: string;
  next_action_ru?: string;
  next_action_en?: string;
  target_summary_ru?: string;
  target_summary_en?: string;
  external_post_published?: boolean;
  send_message_performed?: boolean;
  target_evidence?: {
    schema?: string;
    bot?: {
      username?: string;
      display_name?: string;
    };
    target?: {
      type?: string;
      display_name?: string;
    };
    permission?: {
      member_status?: string;
      publish_allowed?: boolean;
    };
  };
  checks?: Array<{
    key?: string;
    ok?: boolean;
    label_ru?: string;
    label_en?: string;
    detail_ru?: string;
    detail_en?: string;
  }>;
};

export type SocialLaunchPreflight = {
  business_id?: string;
  status?: string;
  safe_to_enable_scoped_dispatch?: boolean;
  workflow_stage_counts?: {
    schema?: string;
    total?: number;
    draft?: number;
    needs_review?: number;
    approved_not_queued?: number;
    queued_total?: number;
    queued_due?: number;
    queued_future?: number;
    publishing?: number;
    published?: number;
    needs_supervised_publish?: number;
    needs_manual_publish?: number;
    failed?: number;
  };
  worker_idle_reason?: {
    schema?: string;
    status?: string;
    title_ru?: string;
    title_en?: string;
    next_action_ru?: string;
    next_action_en?: string;
    count?: number;
  };
  production_readiness?: {
    schema?: string;
    status?: string;
    ready_for_first_scoped_cycle?: boolean;
    safe_to_enable_scoped_dispatch?: boolean;
    due_posts?: number;
    api_due_posts?: number;
    controlled_due_posts?: number;
    manual_due_posts?: number;
    blockers?: Array<{
      key?: string;
      area?: string;
      count?: number;
      label_ru?: string;
      label_en?: string;
      action_ru?: string;
      action_en?: string;
    }>;
    warnings?: Array<{
      key?: string;
      area?: string;
      count?: number;
      label_ru?: string;
      label_en?: string;
      action_ru?: string;
      action_en?: string;
    }>;
    title_ru?: string;
    title_en?: string;
    summary_ru?: string;
    summary_en?: string;
    next_action_ru?: string;
    next_action_en?: string;
    external_publish_requires_approval?: boolean;
    browser_final_click_allowed?: boolean;
    maps_are_supervised_or_manual?: boolean;
    workflow_stage_counts?: SocialLaunchPreflight['workflow_stage_counts'];
    worker_idle_reason?: SocialLaunchPreflight['worker_idle_reason'];
  };
  launch_gate?: {
    schema?: string;
    status?: string;
    allowed?: boolean;
    requires_human_confirmation?: boolean;
    dry_run_completed?: boolean;
    external_publish_requires_approval?: boolean;
    external_publish_confirmation_phrase?: string;
    browser_final_click_allowed?: boolean;
    maps_are_supervised_or_manual?: boolean;
    due_posts?: number;
    api_posts?: number;
    supervised_posts?: number;
    manual_posts?: number;
    blocked_posts?: number;
    title_ru?: string;
    title_en?: string;
    summary_ru?: string;
    summary_en?: string;
    next_action_ru?: string;
    next_action_en?: string;
  };
  first_api_proof_gate?: {
    schema?: string;
    status?: string;
    allowed?: boolean;
    ui_run_once_allowed?: boolean;
    background_worker_aligned?: boolean;
    requires_human_confirmation?: boolean;
    external_publish_requires_approval?: boolean;
    external_publish_performed?: boolean;
    browser_final_click_allowed?: boolean;
    blocked_posts?: number;
    title_ru?: string;
    title_en?: string;
    summary_ru?: string;
    summary_en?: string;
    next_action_ru?: string;
    next_action_en?: string;
    candidate?: {
      ready?: boolean;
      id?: string;
      platform?: string;
      platform_label?: string;
      proof_check_ru?: string;
      proof_check_en?: string;
      metrics_followup_ru?: string;
      metrics_followup_en?: string;
    };
  };
  first_cycle_proof_packet?: {
    schema?: string;
    status?: string;
    ready_to_run_once?: boolean;
    api_proof_ready?: boolean;
    background_worker_aligned?: boolean;
    ui_run_once_allowed?: boolean;
    requires_human_confirmation?: boolean;
    external_publish_requires_approval?: boolean;
    external_publish_confirmation_phrase?: string;
    external_publish_confirmation_ru?: string;
    external_publish_confirmation_en?: string;
    browser_final_click_allowed?: boolean;
    maps_are_supervised_or_manual?: boolean;
    dispatch_business_id?: string;
    metrics_business_id?: string;
    candidate_platform?: string;
    candidate_platform_label?: string;
    required_proof_fields?: string[];
    checklist_done?: number;
    checklist_total?: number;
    run_once_action_ru?: string;
    run_once_action_en?: string;
    after_run_checks_ru?: string[];
    after_run_checks_en?: string[];
    blocked_reason_ru?: string;
    blocked_reason_en?: string;
    runtime_status?: string;
  };
  proof_requirements?: {
    schema?: string;
    status?: string;
    ready_groups?: number;
    total_groups?: number;
    title_ru?: string;
    title_en?: string;
    summary_ru?: string;
    summary_en?: string;
    next_action_ru?: string;
    next_action_en?: string;
    primary_metric_ru?: string;
    primary_metric_en?: string;
    external_publish_requires_approval?: boolean;
    browser_final_click_allowed?: boolean;
    maps_are_supervised_or_manual?: boolean;
    groups?: Array<{
      key?: string;
      state?: string;
      title_ru?: string;
      title_en?: string;
      summary_ru?: string;
      summary_en?: string;
      next_action_ru?: string;
      next_action_en?: string;
      checklist_ru?: string[];
      checklist_en?: string[];
    }>;
  };
  live_validation_checklist?: Array<{
    key?: string;
    status?: 'done' | 'current' | 'attention' | 'pending' | string;
    label_ru?: string;
    label_en?: string;
    detail_ru?: string;
    detail_en?: string;
  }>;
  channel_summary?: {
    api_ready?: number;
    api_needs_attention?: number;
    controlled_or_manual?: number;
  };
  dispatch_preview?: SocialDispatchPreview;
  dispatch_readiness?: SocialDispatchPreview['readiness'];
  api_preflight?: SocialApiChannelPreflight[];
  api_preflight_summary?: {
    checked?: number;
    ready?: number;
    needs_attention?: number;
  };
  launch_rehearsal?: SocialPublishRehearsalBulk;
  api_preflight_blocked_due_posts?: Array<{
    id?: string;
    content_plan_item_id?: string;
    platform?: string;
    platform_label?: string;
    status?: string;
    message_ru?: string;
    message_en?: string;
    next_action_ru?: string;
    next_action_en?: string;
    settings_path?: string;
    recoverable?: boolean;
    safety_summary_ru?: string;
    safety_summary_en?: string;
  }>;
  first_api_publish_readiness?: {
    schema?: string;
    source?: string;
    status?: string;
    ready?: boolean;
    all_api_channels_ready?: boolean;
    recommended_start_platform?: {
      platform?: string;
      platform_label?: string;
      status?: string;
    };
    ready_platforms?: Array<{
      platform?: string;
      platform_label?: string;
      status?: string;
    }>;
    blocked_platforms?: Array<{
      platform?: string;
      platform_label?: string;
      status?: string;
      message_ru?: string;
      message_en?: string;
      next_action_ru?: string;
      next_action_en?: string;
    }>;
    fast_start_platforms?: string[];
    fast_start_ready_platforms?: Array<{
      platform?: string;
      platform_label?: string;
      status?: string;
    }>;
    fast_start_blocked_platforms?: Array<{
      platform?: string;
      platform_label?: string;
      status?: string;
      next_action_ru?: string;
      next_action_en?: string;
    }>;
    fast_start_message_ru?: string;
    fast_start_message_en?: string;
    safe_path_ru?: string[];
    safe_path_en?: string[];
    pre_proof_checks?: Array<{
      key?: string;
      platform?: string;
      label_ru?: string;
      label_en?: string;
      status?: string;
      message_ru?: string;
      message_en?: string;
      action_ru?: string;
      action_en?: string;
      settings_path?: string;
      endpoint?: string;
      external_post_published?: boolean;
      required_before_first_publish?: boolean;
    }>;
    message_ru?: string;
    message_en?: string;
    next_action_ru?: string;
    next_action_en?: string;
    first_post_checklist_ru?: string[];
    first_post_checklist_en?: string[];
    first_api_launch_plan_ru?: string[];
    first_api_launch_plan_en?: string[];
    recommended_start_reason_ru?: string;
    recommended_start_reason_en?: string;
    proof_check_ru?: string;
    proof_check_en?: string;
    metrics_followup_ru?: string;
    metrics_followup_en?: string;
    external_publish_requires_approval?: boolean;
    publish_path_ru?: string;
    publish_path_en?: string;
  };
  recommended_env?: {
    dispatch?: Record<string, string>;
    metrics?: Record<string, string>;
  };
  safety?: {
    approval_required?: boolean;
    scoped_dispatch_required?: boolean;
    external_publish_only_after_approval?: boolean;
    browser_final_click_allowed?: boolean;
    maps_are_supervised_or_manual?: boolean;
  };
  summary?: {
    due_posts?: number;
    api_due_posts?: number;
    controlled_due_posts?: number;
    manual_due_posts?: number;
    blocked_api_channels?: number;
    api_preflight_blocked_due_posts?: number;
    api_ready_channels?: number;
    api_blocked_channels?: number;
    controlled_channels?: number;
    skipped_no_access?: number;
    workflow_total_posts?: number;
    workflow_needs_review?: number;
    workflow_approved_not_queued?: number;
    workflow_queued_future?: number;
  };
  message_ru?: string;
  message_en?: string;
  next_action_ru?: string;
  next_action_en?: string;
  first_cycle_verification?: SocialFirstCycleVerification;
  runtime_alignment?: {
    schema?: string;
    business_id?: string;
    dispatch?: {
      enabled?: boolean;
      business_scope?: string;
      allow_unscoped?: boolean;
      status?: string;
      can_process_this_business?: boolean;
      message_ru?: string;
      message_en?: string;
    };
    metrics?: {
      enabled?: boolean;
      business_scope?: string;
      allow_unscoped?: boolean;
      status?: string;
      can_collect_this_business?: boolean;
      message_ru?: string;
      message_en?: string;
    };
    next_action_ru?: string;
    next_action_en?: string;
  };
  launch_runbook?: SocialLaunchRunbook;
};

export type SocialRuntimeStatus = {
  owner_status?: {
    schema?: string;
    status?: string;
    tone?: string;
    title_ru?: string;
    title_en?: string;
    summary_ru?: string;
    summary_en?: string;
    next_action_ru?: string;
    next_action_en?: string;
    metrics_status?: string;
    metrics_summary_ru?: string;
    metrics_summary_en?: string;
    external_publish_requires_approval?: boolean;
    browser_final_click_allowed?: boolean;
    maps_are_supervised_or_manual?: boolean;
  };
  dispatch?: {
    enabled?: boolean;
    interval_sec?: number;
    batch_size?: number;
    business_scope?: string;
    scoped?: boolean;
    allow_unscoped?: boolean;
    requires_business_scope?: boolean;
    blocked_without_scope?: boolean;
  };
  metrics?: {
    enabled?: boolean;
    interval_sec?: number;
    batch_size?: number;
    business_scope?: string;
    scoped?: boolean;
    allow_unscoped?: boolean;
    requires_business_scope?: boolean;
    blocked_without_scope?: boolean;
  };
  telegram_transport?: {
    schema?: string;
    ready?: boolean;
    status?: string;
    proxy_configured?: boolean;
    proxy_mode?: string;
    bot_token_present?: boolean;
    read_only_probe_enabled?: boolean;
    read_only_probe_performed?: boolean;
    http_status?: number;
    summary_ru?: string;
    summary_en?: string;
    next_action_ru?: string;
    next_action_en?: string;
  };
  approval_required?: boolean;
  browser_final_click_allowed?: boolean;
};

export type SocialChannelReadiness = {
  platform: string;
  platform_label?: string;
  publish_mode?: string;
  ready?: boolean;
  status?: string;
  message_ru?: string;
  message_en?: string;
  next_action_ru?: string;
  next_action_en?: string;
  setup_summary_ru?: string;
  setup_summary_en?: string;
  setup_steps_ru?: string[];
  setup_steps_en?: string[];
  missing_fields?: string[];
  settings_path?: string;
  connection_checks?: SocialChannelConnectionCheck[];
  target_setup?: SocialChannelTargetSetup;
};

export type SocialChannelTargetSetup = {
  schema?: string;
  platform?: string;
  status?: string;
  ready?: boolean;
  owner_telegram_present?: boolean;
  telegram_app_present?: boolean;
  supervised_transport_present?: boolean;
  target_kind?: string;
  target_label_ru?: string;
  target_label_en?: string;
  required_fields?: string[];
  not_a_target_ru?: string;
  not_a_target_en?: string;
  summary_ru?: string;
  summary_en?: string;
  steps_ru?: string[];
  steps_en?: string[];
  proof_ru?: string;
  proof_en?: string;
};

export type SocialFirstApiProofDossier = {
  schema?: string;
  status?: string;
  ready?: boolean;
  candidate_post_id?: string;
  candidate_status?: string;
  recommended_platform?: string;
  recommended_platform_label?: string;
  ready_api_channels?: Array<{
    platform?: string;
    platform_label?: string;
    status?: string;
  }>;
  blocked_api_channels?: Array<{
    platform?: string;
    platform_label?: string;
    status?: string;
    next_action_ru?: string;
    next_action_en?: string;
    settings_path?: string;
  }>;
  provider_post_id?: string;
  provider_post_url?: string;
  external_publish_requires_approval?: boolean;
  external_publish_performed?: boolean;
  browser_final_click_allowed?: boolean;
  maps_are_supervised_or_manual?: boolean;
  primary_metric_ru?: string;
  primary_metric_en?: string;
  title_ru?: string;
  title_en?: string;
  summary_ru?: string;
  summary_en?: string;
  next_action_ru?: string;
  next_action_en?: string;
  steps_ru?: string[];
  steps_en?: string[];
};

export type SocialApiChannelPreflight = {
  platform: string;
  platform_label?: string;
  publish_mode?: string;
  ready?: boolean;
  status?: string;
  message_ru?: string;
  message_en?: string;
  next_action_ru?: string;
  next_action_en?: string;
  setup_summary_ru?: string;
  setup_summary_en?: string;
  setup_steps_ru?: string[];
  setup_steps_en?: string[];
  missing_fields?: string[];
  settings_path?: string;
  connection_checks?: SocialChannelConnectionCheck[];
  read_only?: boolean;
  external_publish_performed?: boolean;
};

export type SocialChannelConnectionCheck = {
  key?: string;
  ok?: boolean;
  state?: string;
  label_ru?: string;
  label_en?: string;
  detail_ru?: string;
  detail_en?: string;
};

export type SocialPlanNextAction = 'prepare' | 'review' | 'queue' | 'supervised' | 'manual' | 'collect' | 'recommend' | 'wait' | 'none';

export type SocialPlanNextStep = {
  action: SocialPlanNextAction;
  titleRu: string;
  titleEn: string;
  descriptionRu: string;
  descriptionEn: string;
  ctaRu: string;
  ctaEn: string;
  count: number;
  disabled?: boolean;
};

export type SocialGoalStage = {
  key?: string;
  label_ru?: string;
  label_en?: string;
  labelRu?: string;
  labelEn?: string;
  status?: 'done' | 'current' | 'attention' | 'pending' | string;
  detail_ru?: string;
  detail_en?: string;
  detailRu?: string;
  detailEn?: string;
  count?: number;
};

export type SocialGoalProgress = {
  schema?: string;
  goal_ru?: string;
  goal_en?: string;
  stages?: SocialGoalStage[];
  summary?: {
    done?: number;
    total?: number;
    attention?: number;
    current_key?: string;
    current_label_ru?: string;
    current_label_en?: string;
  };
  next_action_ru?: string;
  next_action_en?: string;
  primary_metric_ru?: string;
  primary_metric_en?: string;
  approval_required?: boolean;
  maps_are_supervised_or_manual?: boolean;
};

export type SocialLaunchStage = {
  key: string;
  labelRu: string;
  labelEn: string;
  status: 'done' | 'current' | 'attention' | 'pending';
  detailRu: string;
  detailEn: string;
  count?: number;
};

export type SocialAttributionEventType = 'lead' | 'inquiry' | 'comment' | 'share' | 'click' | 'like' | 'view';

export type LearningMetricsPayload = {
  window_days: number;
  items: Array<{
    capability: string;
    generated_total: number;
    accepted_total: number;
    accepted_edited_total: number;
    skipped_total: number;
    rescheduled_total: number;
    minor_edit_total: number;
    major_rewrite_total: number;
    edited_before_accept_pct: number;
  }>;
  summary: {
    generated_total?: number;
    accepted_total?: number;
    accepted_edited_total?: number;
    skipped_total?: number;
    rescheduled_total?: number;
    minor_edit_total?: number;
    major_rewrite_total?: number;
    edited_before_accept_pct?: number;
  };
  source_kind_breakdown?: Array<{
    key: string;
    accepted_total: number;
    accepted_edited_total: number;
    edited_before_accept_pct: number;
  }>;
  content_type_breakdown?: Array<{
    key: string;
    accepted_total: number;
    accepted_edited_total: number;
    edited_before_accept_pct: number;
  }>;
  location_breakdown?: Array<{
    key: string;
    label?: string;
    accepted_total: number;
    accepted_edited_total: number;
    edited_before_accept_pct: number;
  }>;
  network_quality?: Array<{
    key: string;
    label?: string;
    accepted_total: number;
    accepted_edited_total: number;
    skipped_total: number;
    rescheduled_total: number;
    major_rewrite_total: number;
    draft_generated_total: number;
    edited_before_accept_pct: number;
    planned_activity_total: number;
    risk_score: number;
    reasons?: string[];
  }>;
  quality_insights?: Array<{
    kind: string;
    text_ru: string;
    text_en: string;
  }>;
};

export type ActionSummary = {
  tone: 'neutral' | 'success' | 'warning';
  text_ru: string;
  text_en: string;
  details_ru?: string[];
  details_en?: string[];
  focusLocationKey?: string;
  focusWeekKey?: string;
};

export type BulkNewsReview = {
  key: string;
  titleRu: string;
  titleEn: string;
  descriptionRu: string;
  descriptionEn: string;
  items: PlanItem[];
  busyAction: string;
  summaryPrefixRu?: string;
  summaryPrefixEn?: string;
  focusLocationKey?: string;
  focusWeekKey?: string;
};

export type BulkActionReview = {
  key: string;
  kind: 'skip' | 'reschedule';
  titleRu: string;
  titleEn: string;
  descriptionRu: string;
  descriptionEn: string;
  confirmLabelRu: string;
  confirmLabelEn: string;
  items: PlanItem[];
  busyAction: string;
  targetDate?: string;
  summaryPrefixRu?: string;
  summaryPrefixEn?: string;
  focusLocationKey?: string;
  focusWeekKey?: string;
};

export type SocialPreparePreview = {
  key: string;
  items: PlanItem[];
  itemIds: string[];
  busyAction: string;
  source: 'selected' | 'suggested';
  previewItemTitle: string;
  preview: {
    read_only?: boolean;
    database_write_performed?: boolean;
    external_publish_performed?: boolean;
    summary?: Record<string, unknown>;
    posts?: Array<Record<string, unknown>>;
    next_action_ru?: string;
    next_action_en?: string;
  };
};

export type SocialApprovalPreview = {
  key: string;
  posts: SocialPost[];
  postIds: string[];
  busyAction: string;
  source: 'selected' | 'single';
};

export type SocialApprovalPreviewSummary = {
  total: number;
  api: number;
  supervised: number;
  emptyText: number;
  blockedApiWarnings: Array<{ postId: string; platform: string; label: string; status: string }>;
  platformLabels: string[];
};

export type SocialQueuePreview = {
  key: string;
  posts: SocialPost[];
  postIds: string[];
  busyAction: string;
  source: 'selected' | 'visible' | 'single';
};

export type SocialQueuePreviewSummary = {
  total: number;
  api: number;
  supervised: number;
  dueNow: number;
  blockedApiWarnings: Array<{ postId: string; platform: string; label: string; status: string }>;
  platformLabels: string[];
  firstScheduledFor: string;
};

export type NetworkOperatingSlice = {
  key: string;
  label: string;
  riskScore: number;
  reasons: string[];
  total: number;
  needsDraft: number;
  readyToPublish: number;
  published: number;
  skipped: number;
  focusWeekKey: string;
  focusWeekLabel: string;
  focusWeekNeedsDraft: number;
  focusWeekReadyToPublish: number;
  recommendation: string;
};

export type OperatorInsight = {
  key: string;
  textRu: string;
  textEn: string;
};

export type ContentPlanTabProps = {
  businessId?: string;
};

export type ContentMixKey = 'services' | 'seo' | 'sales' | 'audit' | 'seasonal';

export type ContentMixState = Record<ContentMixKey, boolean>;

export type ItemFilterKey = 'all' | 'urgent' | 'has_draft';

export type SignalFilterKey = 'all' | ContentMixKey;

export type ViewPresetKey = 'overview' | 'urgent' | 'ready' | 'published' | 'focus' | 'custom';

export type QuickActionKey = 'open_week' | 'weak_locations' | 'fix_gaps' | 'repeat_template';

export type ContentPlanZone = 'overview' | 'plan' | 'queue';

export type ContentPlanMode = 'point' | 'network';

export type ContentLanguageKey = 'ru' | 'en' | 'es' | 'de' | 'fr' | 'tr' | 'it' | 'pt' | 'zh';
