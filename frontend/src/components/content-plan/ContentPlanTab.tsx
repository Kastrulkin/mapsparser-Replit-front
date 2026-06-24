import React, { useEffect, useMemo, useState } from 'react';
import { CalendarDays, CheckSquare, Globe, Lock, MapPinned, MoreHorizontal, Sparkles, Trash2, Wand2 } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { useLanguage } from '@/i18n/LanguageContext';
import { newAuth } from '@/lib/auth_new';

type ScopeOption = {
  scope_type: string;
  scope_target_id: string;
  label: string;
  city?: string;
  address?: string;
  is_parent?: boolean;
  is_current?: boolean;
};

type ContextPayload = {
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

type PlanItem = {
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

type PlanPayload = {
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

type SocialPost = {
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

type SocialPublishEvidence = {
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

type SocialPublishRehearsal = {
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

type SocialPublishRehearsalBulk = {
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

type SocialOpenClawCapabilityStatus = {
  ready?: boolean;
  status?: string;
  source?: string;
  reason?: string;
  action_ref?: string;
  capability?: string;
  error?: string;
};

type SocialOpenClawReadiness = {
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

type SocialSupervisedSafetyContract = {
  allowed_actions?: string[];
  forbidden_actions?: string[];
  manual_fallback_triggers?: string[];
};

type SocialPostMetadata = {
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

type SocialPostsSummary = {
  total?: number;
  needs_review?: number;
  scheduled?: number;
  needs_supervised_publish?: number;
  needs_manual_publish?: number;
  published?: number;
  failed?: number;
  by_status?: Record<string, number>;
};

type SocialRecommendationPayload = {
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

type SocialLearningReadiness = {
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

type SocialRecommendationTopicInsight = {
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

type SocialRecommendationChannelInsight = {
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

type SocialRecommendationTextSuggestion = {
  ru?: string;
  en?: string;
};

type SocialQueueGroup = {
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

type SocialDispatchPreview = {
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

type SocialDispatchExecutionReport = {
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

type SocialFirstCycleVerification = {
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

type SocialLaunchRunbook = {
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

type SocialMetricsLearningPacket = {
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

type SocialLaunchPreflight = {
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

type SocialRuntimeStatus = {
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

type SocialChannelReadiness = {
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

type SocialChannelTargetSetup = {
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

type SocialFirstApiProofDossier = {
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

type SocialApiChannelPreflight = {
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

type SocialChannelConnectionCheck = {
  key?: string;
  ok?: boolean;
  state?: string;
  label_ru?: string;
  label_en?: string;
  detail_ru?: string;
  detail_en?: string;
};

type SocialPlanNextAction = 'prepare' | 'review' | 'queue' | 'supervised' | 'manual' | 'collect' | 'recommend' | 'wait' | 'none';

type SocialPlanNextStep = {
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

type SocialGoalStage = {
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

type SocialGoalProgress = {
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

type SocialLaunchStage = {
  key: string;
  labelRu: string;
  labelEn: string;
  status: 'done' | 'current' | 'attention' | 'pending';
  detailRu: string;
  detailEn: string;
  count?: number;
};

type SocialAttributionEventType = 'lead' | 'inquiry' | 'comment' | 'share' | 'click' | 'like' | 'view';

type LearningMetricsPayload = {
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

type ActionSummary = {
  tone: 'neutral' | 'success' | 'warning';
  text_ru: string;
  text_en: string;
  details_ru?: string[];
  details_en?: string[];
  focusLocationKey?: string;
  focusWeekKey?: string;
};

type BulkNewsReview = {
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

type BulkActionReview = {
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

type SocialPreparePreview = {
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

type SocialApprovalPreview = {
  key: string;
  posts: SocialPost[];
  postIds: string[];
  busyAction: string;
  source: 'selected' | 'single';
};

type SocialApprovalPreviewSummary = {
  total: number;
  api: number;
  supervised: number;
  emptyText: number;
  blockedApiWarnings: Array<{ postId: string; platform: string; label: string; status: string }>;
  platformLabels: string[];
};

type SocialQueuePreview = {
  key: string;
  posts: SocialPost[];
  postIds: string[];
  busyAction: string;
  source: 'selected' | 'visible' | 'single';
};

type SocialQueuePreviewSummary = {
  total: number;
  api: number;
  supervised: number;
  dueNow: number;
  blockedApiWarnings: Array<{ postId: string; platform: string; label: string; status: string }>;
  platformLabels: string[];
  firstScheduledFor: string;
};

type NetworkOperatingSlice = {
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

type OperatorInsight = {
  key: string;
  textRu: string;
  textEn: string;
};

const PERIOD_OPTIONS = [30, 60, 90];

const DENSITY_OPTIONS = [
  { value: 'light', labelRu: 'Спокойно', labelEn: 'Light' },
  { value: 'standard', labelRu: 'Стандартно', labelEn: 'Standard' },
  { value: 'active', labelRu: 'Активно', labelEn: 'Active' },
];

type ContentPlanTabProps = {
  businessId?: string;
};

type ContentMixKey = 'services' | 'seo' | 'sales' | 'audit' | 'seasonal';

type ContentMixState = Record<ContentMixKey, boolean>;
type ItemFilterKey = 'all' | 'urgent' | 'has_draft';
type SignalFilterKey = 'all' | ContentMixKey;
type ViewPresetKey = 'overview' | 'urgent' | 'ready' | 'published' | 'focus' | 'custom';
type QuickActionKey = 'open_week' | 'weak_locations' | 'fix_gaps' | 'repeat_template';
type ContentPlanZone = 'overview' | 'plan' | 'queue';
type ContentPlanMode = 'point' | 'network';
type ContentLanguageKey = 'ru' | 'en' | 'es' | 'de' | 'fr' | 'tr' | 'it' | 'pt' | 'zh';

const CONTENT_MIX_OPTIONS: Array<{ key: ContentMixKey; labelRu: string; labelEn: string }> = [
  { key: 'services', labelRu: 'Услуги', labelEn: 'Services' },
  { key: 'seo', labelRu: 'SEO', labelEn: 'SEO' },
  { key: 'sales', labelRu: 'Продажи', labelEn: 'Sales' },
  { key: 'audit', labelRu: 'Аудит', labelEn: 'Audit' },
  { key: 'seasonal', labelRu: 'Сезонность', labelEn: 'Seasonal' },
];
const CONTENT_LANGUAGE_OPTIONS: Array<{ value: ContentLanguageKey; label: string }> = [
  { value: 'ru', label: 'Русский' },
  { value: 'en', label: 'English' },
  { value: 'es', label: 'Español' },
  { value: 'de', label: 'Deutsch' },
  { value: 'fr', label: 'Français' },
  { value: 'tr', label: 'Türkçe' },
  { value: 'it', label: 'Italiano' },
  { value: 'pt', label: 'Português' },
  { value: 'zh', label: '中文' },
];
const ITEM_FILTER_OPTIONS: ItemFilterKey[] = ['all', 'has_draft', 'urgent'];
const SIGNAL_FILTER_OPTIONS: SignalFilterKey[] = ['all', 'seo', 'services', 'sales', 'audit', 'seasonal'];
const CONTENT_PLAN_PREFERENCES_KEY = 'content_plan_preferences_v1';

export default function ContentPlanTab({ businessId }: ContentPlanTabProps) {
  const navigate = useNavigate();
  const { language } = useLanguage();
  const isRu = language === 'ru';
  const [context, setContext] = useState<ContextPayload | null>(null);
  const [plans, setPlans] = useState<PlanPayload[]>([]);
  const [currentPlan, setCurrentPlan] = useState<PlanPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [metricsLoading, setMetricsLoading] = useState(false);
  const [error, setError] = useState('');
  const [learningMetrics, setLearningMetrics] = useState<LearningMetricsPayload | null>(null);
  const [selectedScopeKey, setSelectedScopeKey] = useState('');
  const [selectedPeriod, setSelectedPeriod] = useState('30');
  const [selectedDensity, setSelectedDensity] = useState('standard');
  const [contentMix, setContentMix] = useState<ContentMixState>({
    services: true,
    seo: true,
    sales: true,
    audit: true,
    seasonal: true,
  });
  const [draftEdits, setDraftEdits] = useState<Record<string, string>>({});
  const [themeEdits, setThemeEdits] = useState<Record<string, string>>({});
  const [dateEdits, setDateEdits] = useState<Record<string, string>>({});
  const [busyItemId, setBusyItemId] = useState('');
  const [bulkBusyAction, setBulkBusyAction] = useState('');
  const [actionSummary, setActionSummary] = useState<ActionSummary | null>(null);
  const [selectedItemFilter, setSelectedItemFilter] = useState<ItemFilterKey>('all');
  const [selectedSignalFilter, setSelectedSignalFilter] = useState<SignalFilterKey>('all');
  const [selectedPlanTargetKey, setSelectedPlanTargetKey] = useState('all');
  const [selectedItemLocationKey, setSelectedItemLocationKey] = useState('all');
  const [selectedWeekKey, setSelectedWeekKey] = useState('all');
  const [selectedChannelFilter, setSelectedChannelFilter] = useState<'all' | 'social' | 'maps'>('all');
  const [dateFromFilter, setDateFromFilter] = useState('');
  const [dateToFilter, setDateToFilter] = useState('');
  const [sortMode, setSortMode] = useState<'priority' | 'date'>('date');
  const [selectedViewPreset, setSelectedViewPreset] = useState<ViewPresetKey>('overview');
  const [lastFocusLocationKey, setLastFocusLocationKey] = useState('all');
  const [lastFocusWeekKey, setLastFocusWeekKey] = useState('all');
  const [showAdvancedControls, setShowAdvancedControls] = useState(false);
  const [showPlanSetupDetails, setShowPlanSetupDetails] = useState(false);
  const [showLearningDetails, setShowLearningDetails] = useState(false);
  const [showContextDetails, setShowContextDetails] = useState(false);
  const [bulkTargetDate, setBulkTargetDate] = useState(() => _shiftIsoDate('', 7));
  const [expandedDuplicateItemId, setExpandedDuplicateItemId] = useState('');
  const [duplicateTargetSelections, setDuplicateTargetSelections] = useState<Record<string, string[]>>({});
  const [duplicateDateOverrides, setDuplicateDateOverrides] = useState<Record<string, string>>({});
  const [bulkNewsReview, setBulkNewsReview] = useState<BulkNewsReview | null>(null);
  const [bulkActionReview, setBulkActionReview] = useState<BulkActionReview | null>(null);
  const [recentGeneratedItemId, setRecentGeneratedItemId] = useState('');
  const [socialPostsByItem, setSocialPostsByItem] = useState<Record<string, SocialPost[]>>({});
  const [socialSummary, setSocialSummary] = useState<SocialPostsSummary | null>(null);
  const [socialQueueGroups, setSocialQueueGroups] = useState<SocialQueueGroup[]>([]);
  const [socialChannelReadiness, setSocialChannelReadiness] = useState<SocialChannelReadiness[]>([]);
  const [socialApiPreflight, setSocialApiPreflight] = useState<SocialApiChannelPreflight[]>([]);
  const [socialOpenClawReadiness, setSocialOpenClawReadiness] = useState<SocialOpenClawReadiness | null>(null);
  const [socialRecommendation, setSocialRecommendation] = useState<SocialRecommendationPayload | null>(null);
  const [socialGoalProgress, setSocialGoalProgress] = useState<SocialGoalProgress | null>(null);
  const [socialFirstApiProofDossier, setSocialFirstApiProofDossier] = useState<SocialFirstApiProofDossier | null>(null);
  const [socialRecommendationApproved, setSocialRecommendationApproved] = useState(false);
  const [socialDispatchPreview, setSocialDispatchPreview] = useState<SocialDispatchPreview | null>(null);
  const [socialDispatchExecutionReport, setSocialDispatchExecutionReport] = useState<SocialDispatchExecutionReport | null>(null);
  const [socialMetricsLearningPacket, setSocialMetricsLearningPacket] = useState<SocialMetricsLearningPacket | null>(null);
  const [socialLaunchPreflight, setSocialLaunchPreflight] = useState<SocialLaunchPreflight | null>(null);
  const [socialRuntimeStatus, setSocialRuntimeStatus] = useState<SocialRuntimeStatus | null>(null);
  const [socialPostsLoading, setSocialPostsLoading] = useState(false);
  const [socialTextEdits, setSocialTextEdits] = useState<Record<string, string>>({});
  const [manualPublishRefs, setManualPublishRefs] = useState<Record<string, { url: string; id: string }>>({});
  const [socialPublishRehearsals, setSocialPublishRehearsals] = useState<Record<string, SocialPublishRehearsal>>({});
  const [socialBulkPublishRehearsal, setSocialBulkPublishRehearsal] = useState<SocialPublishRehearsalBulk | null>(null);
  const [socialPreparePreview, setSocialPreparePreview] = useState<SocialPreparePreview | null>(null);
  const [socialApprovalPreview, setSocialApprovalPreview] = useState<SocialApprovalPreview | null>(null);
  const [socialQueuePreview, setSocialQueuePreview] = useState<SocialQueuePreview | null>(null);
  const [socialBusyAction, setSocialBusyAction] = useState('');
  const [activeZone, setActiveZone] = useState<ContentPlanZone>('overview');
  const [contentMode, setContentMode] = useState<ContentPlanMode>('point');
  const [contentLanguage, setContentLanguage] = useState<ContentLanguageKey>(() => _normalizeContentLanguage(language));
  const [selectedQueueItemId, setSelectedQueueItemId] = useState('');
  const [editorItemId, setEditorItemId] = useState('');
  const [queueSearch, setQueueSearch] = useState('');
  const [showSelectedItemDetails, setShowSelectedItemDetails] = useState(false);
  const [selectedItemIds, setSelectedItemIds] = useState<Record<string, boolean>>({});
  const [showRecentPlans, setShowRecentPlans] = useState(false);

  const allowedHorizons = useMemo(() => context?.subscription?.allowed_horizons || [30], [context?.subscription?.allowed_horizons]);
  const scopeOptions = useMemo(() => context?.scope?.scope_options || [], [context?.scope?.scope_options]);
  const isNetworkContext = Boolean(context?.scope?.network?.is_network);
  const selectedScopeDescription = context?.scope?.selected_scope_description || '';
  const selectedScopeLabel = context?.scope?.selected_scope_label || '';
  const readiness = context?.readiness || null;
  const missingInputs = useMemo(() => (
    Array.isArray(readiness?.missing_inputs) ? readiness.missing_inputs : []
  ), [readiness?.missing_inputs]);
  const mapLinksCount = Number(readiness?.map_links_count || 0);
  const servicesCount = context?.services?.length || 0;
  const seoKeywordsCount = context?.seo_keywords?.length || 0;
  const networkLocationsCount = context?.scope?.network?.locations_count || 0;
  const hasSearchFoundation = mapLinksCount > 0 && seoKeywordsCount > 0;
  const hasOnlyServicesGap = missingInputs.length === 1 && missingInputs.includes('services');
  const networkHasSearchPlanFoundation = isNetworkContext && hasSearchFoundation && hasOnlyServicesGap;
  const isNetworkMode = contentMode === 'network' && isNetworkContext;
  const networkScopeOption = useMemo(() => (
    scopeOptions.find((item) => item.scope_type === 'network_parent') || null
  ), [scopeOptions]);
  const pointScopeOption = useMemo(() => (
    scopeOptions.find((item) => item.is_current)
    || scopeOptions.find((item) => item.scope_type !== 'network_parent')
    || scopeOptions[0]
    || null
  ), [scopeOptions]);

  const selectedScopeOption = useMemo(() => (
    scopeOptions.find((item) => `${item.scope_type}:${item.scope_target_id}` === selectedScopeKey) || null
  ), [scopeOptions, selectedScopeKey]);
  const filteredItems = useMemo(() => {
    const items = currentPlan?.items || [];
    return items.filter((item) => (
      _matchesItemFilter(item, selectedItemFilter)
      && _matchesSignalFilter(item, selectedSignalFilter)
      && _matchesItemLocationFilter(item, selectedItemLocationKey)
    ));
  }, [currentPlan?.items, selectedItemFilter, selectedSignalFilter, selectedItemLocationKey]);
  const availableWeeks = useMemo(() => {
    const seen = new Set<string>();
    const options: Array<{ key: string; label: string }> = [
      { key: 'all', label: isRu ? 'Все недели' : 'All weeks' },
    ];
    for (const item of filteredItems) {
      const key = _weekBucketKey(item.scheduled_for);
      if (!key || seen.has(key)) continue;
      seen.add(key);
      options.push({
        key,
        label: _weekBucketLabel(key, isRu),
      });
    }
    return options;
  }, [filteredItems, isRu]);
  const weekSummary = useMemo(() => {
    const buckets = new Map<string, { key: string; label: string; total: number; needsDraft: number; readyToPublish: number }>();
    for (const item of filteredItems) {
      if (String(item.status || '').trim() === 'skipped') continue;
      const key = _weekBucketKey(item.scheduled_for);
      if (!key) continue;
      const existing = buckets.get(key) || {
        key,
        label: _weekBucketLabel(key, isRu),
        total: 0,
        needsDraft: 0,
        readyToPublish: 0,
      };
      existing.total += 1;
      const hasDraft = Boolean(String(item.draft_text || '').trim());
      const hasNews = Boolean(String(item.usernews_id || '').trim());
      if (!hasDraft) {
        existing.needsDraft += 1;
      }
      if (hasDraft && !hasNews) {
        existing.readyToPublish += 1;
      }
      buckets.set(key, existing);
    }
    return Array.from(buckets.values()).sort((left, right) => left.key.localeCompare(right.key));
  }, [filteredItems, isRu]);
  const visibleItems = useMemo(() => (
    filteredItems
      .filter((item) => selectedWeekKey === 'all' || _weekBucketKey(item.scheduled_for) === selectedWeekKey)
      .filter((item) => _matchesChannelFilter(item, socialPostsByItem, selectedChannelFilter))
      .filter((item) => _matchesDateRange(item.scheduled_for, dateFromFilter, dateToFilter))
      .filter((item) => {
        const query = queueSearch.trim().toLowerCase();
        if (!query) return true;
        return [
          item.theme,
          item.goal,
          item.draft_text,
          item.source_ref,
          item.seo_keyword,
          item.location_label,
        ].some((value) => String(value || '').toLowerCase().includes(query));
      })
      .slice()
      .sort((left, right) => {
        if (recentGeneratedItemId) {
          if (left.id === recentGeneratedItemId && right.id !== recentGeneratedItemId) return -1;
          if (right.id === recentGeneratedItemId && left.id !== recentGeneratedItemId) return 1;
        }
        if (sortMode === 'priority') {
          const priorityDiff = _itemPriorityRank(left) - _itemPriorityRank(right);
          if (priorityDiff !== 0) return priorityDiff;
        }
        const dateDiff = _inputDateValue(left.scheduled_for).localeCompare(_inputDateValue(right.scheduled_for));
        if (dateDiff !== 0) return dateDiff;
        return String(left.theme || '').localeCompare(String(right.theme || ''));
      })
  ), [dateFromFilter, dateToFilter, filteredItems, queueSearch, recentGeneratedItemId, selectedChannelFilter, selectedWeekKey, socialPostsByItem, sortMode]);
  const selectedQueueItem = useMemo(() => (
    visibleItems.find((item) => item.id === selectedQueueItemId) || visibleItems[0] || null
  ), [selectedQueueItemId, visibleItems]);
  const editorItem = useMemo(() => (
    visibleItems.find((item) => item.id === editorItemId)
    || currentPlan?.items?.find((item) => item.id === editorItemId)
    || null
  ), [currentPlan?.items, editorItemId, visibleItems]);
  const itemFilterCounts = useMemo(() => {
    const items = currentPlan?.items || [];
    return ITEM_FILTER_OPTIONS.reduce<Record<ItemFilterKey, number>>((acc, filterKey) => {
      acc[filterKey] = items.filter((item) => _matchesItemFilter(item, filterKey)).length;
      return acc;
    }, {
      all: 0,
      urgent: 0,
      has_draft: 0,
    });
  }, [currentPlan?.items]);
  const signalFilterCounts = useMemo(() => {
    const items = currentPlan?.items || [];
    return SIGNAL_FILTER_OPTIONS.reduce<Record<SignalFilterKey, number>>((acc, filterKey) => {
      acc[filterKey] = items.filter((item) => _matchesSignalFilter(item, filterKey)).length;
      return acc;
    }, {
      all: 0,
      seo: 0,
      services: 0,
      sales: 0,
      audit: 0,
      seasonal: 0,
    });
  }, [currentPlan?.items]);
  const availableItemLocations = useMemo(() => {
    const seen = new Set<string>();
    const options: Array<{ key: string; label: string }> = [
      { key: 'all', label: isRu ? 'Все точки' : 'All locations' },
    ];
    for (const item of currentPlan?.items || []) {
      const key = String(item.location_scope || item.business_id || '').trim();
      if (!key || seen.has(key)) continue;
      seen.add(key);
      options.push({
        key,
        label: _itemLocationLabel(item, isRu),
      });
    }
    return options;
  }, [currentPlan?.items, isRu]);
  const itemLocationSummary = useMemo(() => {
    const counts = new Map<string, { label: string; count: number }>();
    for (const item of currentPlan?.items || []) {
      const key = String(item.location_scope || item.business_id || '').trim();
      if (!key) continue;
      const existing = counts.get(key);
      if (existing) {
        existing.count += 1;
        continue;
      }
      counts.set(key, {
        label: _itemLocationLabel(item, isRu),
        count: 1,
      });
    }
    return Array.from(counts.values()).sort((left, right) => right.count - left.count);
  }, [currentPlan?.items, isRu]);
  const locationOperationalSummary = useMemo(() => {
    const buckets = new Map<string, { key: string; label: string; total: number; needsDraft: number; readyToPublish: number }>();
    for (const item of filteredItems) {
      if (String(item.status || '').trim() === 'skipped') continue;
      const key = String(item.location_scope || item.business_id || '').trim();
      if (!key) continue;
      const existing = buckets.get(key) || {
        key,
        label: _itemLocationLabel(item, isRu),
        total: 0,
        needsDraft: 0,
        readyToPublish: 0,
      };
      existing.total += 1;
      const hasDraft = Boolean(String(item.draft_text || '').trim());
      const hasNews = Boolean(String(item.usernews_id || '').trim());
      if (!hasDraft) {
        existing.needsDraft += 1;
      }
      if (hasDraft && !hasNews) {
        existing.readyToPublish += 1;
      }
      buckets.set(key, existing);
    }
    return Array.from(buckets.values()).sort((left, right) => right.total - left.total);
  }, [filteredItems, isRu]);
  const availablePlanTargets = useMemo(() => {
    const seen = new Set<string>();
    const options: Array<{ key: string; label: string }> = [
      { key: 'all', label: isRu ? 'Все планы' : 'All plans' },
    ];
    for (const plan of plans) {
      const key = `${plan.scope_type}:${plan.scope_target_id}`;
      if (seen.has(key)) continue;
      seen.add(key);
      options.push({
        key,
        label: _planTargetLabel(plan, isRu),
      });
    }
    return options;
  }, [plans, isRu]);
  const visiblePlans = useMemo(() => {
    if (selectedPlanTargetKey === 'all') return plans;
    return plans.filter((plan) => `${plan.scope_type}:${plan.scope_target_id}` === selectedPlanTargetKey);
  }, [plans, selectedPlanTargetKey]);
  const bulkDraftCandidates = useMemo(() => (
    visibleItems.filter((item) => !String(item.draft_text || '').trim() && !String(item.usernews_id || '').trim())
  ), [visibleItems]);
  const bulkNewsCandidates = useMemo(() => (
    visibleItems.filter((item) => String(item.draft_text || '').trim() && !String(item.usernews_id || '').trim())
  ), [visibleItems]);
  const selectedItems = useMemo(() => (
    visibleItems.filter((item) => Boolean(selectedItemIds[item.id]))
  ), [selectedItemIds, visibleItems]);
  const selectedDraftCandidates = useMemo(() => (
    selectedItems.filter((item) => !String(item.draft_text || '').trim() && !String(item.usernews_id || '').trim())
  ), [selectedItems]);
  const selectedNewsCandidates = useMemo(() => (
    selectedItems.filter((item) => String(item.draft_text || '').trim() && !String(item.usernews_id || '').trim())
  ), [selectedItems]);
  const selectedSocialPosts = useMemo(() => (
    selectedItems.flatMap((item) => socialPostsByItem[item.id] || [])
  ), [selectedItems, socialPostsByItem]);
  const selectedSocialNeedsReview = useMemo(() => (
    selectedSocialPosts.filter((post) => post.status === 'draft' || post.status === 'needs_review')
  ), [selectedSocialPosts]);
  const selectedSocialDirtyReviewPosts = useMemo(() => (
    selectedSocialNeedsReview.filter((post) => (
      Object.prototype.hasOwnProperty.call(socialTextEdits, post.id)
      && String(socialTextEdits[post.id] ?? '').trim() !== String(post.platform_text || '').trim()
    ))
  ), [selectedSocialNeedsReview, socialTextEdits]);
  const selectedSocialCanQueue = useMemo(() => (
    selectedSocialPosts.filter((post) => post.status === 'approved')
  ), [selectedSocialPosts]);
  const selectedSocialCanMarkPublished = useMemo(() => (
    selectedSocialPosts.filter((post) => post.status === 'needs_supervised_publish' || post.status === 'needs_manual_publish')
  ), [selectedSocialPosts]);
  const selectedSocialCanRecordResults = useMemo(() => (
    selectedSocialPosts.filter((post) => post.status === 'published')
  ), [selectedSocialPosts]);
  const allSocialPosts = useMemo(() => (
    Object.values(socialPostsByItem).flat()
  ), [socialPostsByItem]);
  const allSocialNeedsReview = useMemo(() => (
    allSocialPosts.filter((post) => post.status === 'draft' || post.status === 'needs_review')
  ), [allSocialPosts]);
  const allSocialCanQueue = useMemo(() => (
    allSocialPosts.filter((post) => post.status === 'approved')
  ), [allSocialPosts]);
  const visibleSocialPosts = useMemo(() => (
    visibleItems.flatMap((item) => socialPostsByItem[item.id] || [])
  ), [socialPostsByItem, visibleItems]);
  const socialMetricsSourceSummary = useMemo(() => {
    const byPlatform = new Map<string, { platform: string; label: string; posts: number; published: number; sourceRu: string; sourceEn: string }>();
    for (const post of visibleSocialPosts) {
      const platform = String(post.platform || '').trim();
      if (!platform) continue;
      const existing = byPlatform.get(platform) || {
        platform,
        label: post.platform_label || _socialPlatformLabel(platform, isRu),
        posts: 0,
        published: 0,
        sourceRu: _socialMetricsSourceText(platform, true),
        sourceEn: _socialMetricsSourceText(platform, false),
      };
      existing.posts += 1;
      if (post.status === 'published') existing.published += 1;
      byPlatform.set(platform, existing);
    }
    return Array.from(byPlatform.values()).sort((left, right) => left.label.localeCompare(right.label));
  }, [isRu, visibleSocialPosts]);
  const visibleSocialNeedsReview = useMemo(() => (
    visibleSocialPosts.filter((post) => post.status === 'draft' || post.status === 'needs_review')
  ), [visibleSocialPosts]);
  const visibleSocialCanQueue = useMemo(() => (
    visibleSocialPosts.filter((post) => post.status === 'approved')
  ), [visibleSocialPosts]);
  const visibleSocialNeedsSupervised = useMemo(() => (
    visibleSocialPosts.filter((post) => post.status === 'needs_supervised_publish')
  ), [visibleSocialPosts]);
  const visibleSocialNeedsManual = useMemo(() => (
    visibleSocialPosts.filter((post) => post.status === 'needs_manual_publish')
  ), [visibleSocialPosts]);
  const visibleSocialPublishedPosts = useMemo(() => (
    visibleSocialPosts.filter((post) => post.status === 'published')
  ), [visibleSocialPosts]);
  const visibleSocialPublishedWithoutPrimaryResult = useMemo(() => (
    visibleSocialPublishedPosts.filter((post) => Number(post.leads || 0) + Number(post.inquiries || 0) === 0)
  ), [visibleSocialPublishedPosts]);
  const socialResultSummary = useMemo(() => (
    visibleSocialPosts.reduce((acc, post) => {
      acc.leads += Number(post.leads || 0);
      acc.inquiries += Number(post.inquiries || 0);
      acc.comments += Number(post.comments || 0);
      acc.shares += Number(post.shares || 0);
      acc.clicks += Number(post.clicks || 0);
      acc.likes += Number(post.likes || 0);
      acc.views += Number(post.views || post.reach || 0);
      return acc;
    }, {
      leads: 0,
      inquiries: 0,
      comments: 0,
      shares: 0,
      clicks: 0,
      likes: 0,
      views: 0,
    })
  ), [visibleSocialPosts]);
  const socialPrimaryResultCount = socialResultSummary.leads + socialResultSummary.inquiries;
  const socialEarlySignalCount = socialResultSummary.comments + socialResultSummary.shares + socialResultSummary.clicks + socialResultSummary.likes + socialResultSummary.views;
  const socialLearningLoopStatus = useMemo(() => {
    const published = Number(socialSummary?.published || 0);
    const pending = Number(socialSummary?.needs_supervised_publish || 0) + Number(socialSummary?.needs_manual_publish || 0);
    const failed = Number(socialSummary?.failed || 0);
    if (failed > 0 || pending > 0) {
      return {
        action: 'open_results',
        tone: 'warning',
        titleRu: 'Сначала закрыть публикации',
        titleEn: 'Finish publishing first',
        textRu: `Нужно закрыть ручное/контролируемое размещение или ошибки: ${pending + failed}. После этого LocalOS сможет честно сравнить результат.`,
        textEn: `Manual/supervised placement or failures still need action: ${pending + failed}. After that, LocalOS can compare results honestly.`,
        ctaRu: 'Открыть публикации',
        ctaEn: 'Open posts',
      };
    }
    if (socialPrimaryResultCount > 0) {
      return {
        action: 'recommend',
        tone: 'success',
        titleRu: 'Есть главный результат',
        titleEn: 'Primary results recorded',
        textRu: `Заявки и обращения: ${socialPrimaryResultCount}. Можно предлагать изменения следующего плана, но применять только после подтверждения.`,
        textEn: `Leads and inquiries: ${socialPrimaryResultCount}. You can suggest next-plan changes, but apply only after approval.`,
        ctaRu: 'Предложить изменения',
        ctaEn: 'Suggest changes',
      };
    }
    if (socialEarlySignalCount > 0) {
      return {
        action: 'recommend',
        tone: 'caution',
        titleRu: 'Есть ранние сигналы',
        titleEn: 'Early signals recorded',
        textRu: `Ранние сигналы: ${socialEarlySignalCount}. Перед применением изменений отметьте заявки/обращения, если они были.`,
        textEn: `Early signals: ${socialEarlySignalCount}. Before applying changes, record leads/inquiries if any happened.`,
        ctaRu: 'Предложить изменения',
        ctaEn: 'Suggest changes',
      };
    }
    if (published > 0) {
      return {
        action: 'collect',
        tone: 'caution',
        titleRu: 'Нужно собрать реакции',
        titleEn: 'Collect reactions next',
        textRu: `Опубликовано: ${published}. Соберите реакции или отметьте заявки вручную, затем предложите изменения следующего плана.`,
        textEn: `Published: ${published}. Collect reactions or record leads manually, then suggest next-plan changes.`,
        ctaRu: 'Собрать реакции',
        ctaEn: 'Collect reactions',
      };
    }
    return {
      action: 'open_results',
      tone: 'neutral',
      titleRu: 'Результаты появятся после публикаций',
      titleEn: 'Results appear after publishing',
      textRu: 'Сначала подготовьте, утвердите и поставьте посты в расписание. После публикаций здесь появятся реакции, заявки и следующий шаг.',
      textEn: 'Prepare, approve, and queue posts first. After publishing, reactions, leads, and the next action will appear here.',
      ctaRu: 'Открыть очередь',
      ctaEn: 'Open queue',
    };
  }, [
    socialEarlySignalCount,
    socialPrimaryResultCount,
    socialSummary?.failed,
    socialSummary?.needs_manual_publish,
    socialSummary?.needs_supervised_publish,
    socialSummary?.published,
  ]);
  const socialDispatchEnabled = Boolean(socialRuntimeStatus?.dispatch?.enabled);
  const socialDispatchBlockedWithoutScope = Boolean(socialRuntimeStatus?.dispatch?.blocked_without_scope);
  const socialDispatchScopeMismatch = Boolean(
    socialRuntimeStatus?.dispatch?.scoped
    && businessId
    && String(socialRuntimeStatus.dispatch.business_scope || '').trim()
    && String(socialRuntimeStatus.dispatch.business_scope || '').trim() !== String(businessId || '').trim(),
  );
  const socialQueueExecutionNotice = useMemo(() => {
    if (socialDispatchBlockedWithoutScope) {
      return {
        tone: 'warning',
        titleRu: 'Расписание включено, но остановлено защитой',
        titleEn: 'Dispatch is enabled but guarded',
        textRu: 'LocalOS не запустит публикации, пока не выбран конкретный бизнес для первого цикла. Укажите SOCIAL_POST_DISPATCH_BUSINESS_ID для тестового бизнеса или включите явное allow-all.',
        textEn: 'LocalOS will not publish until a business scope is set. Set SOCIAL_POST_DISPATCH_BUSINESS_ID for the test business or enable explicit allow-all.',
      };
    }
    if (socialDispatchScopeMismatch) {
      return {
        tone: 'warning',
        titleRu: 'Расписание включено для другого бизнеса',
        titleEn: 'Dispatch is scoped to another business',
        textRu: `Исполнитель расписания сейчас ограничен бизнесом ${String(socialRuntimeStatus?.dispatch?.business_scope || '')}. Посты этого бизнеса можно готовить и ставить в расписание, но они не уйдут, пока область запуска не совпадёт.`,
        textEn: `The worker is currently scoped to business ${String(socialRuntimeStatus?.dispatch?.business_scope || '')}. You can prepare and queue this business posts, but they will not publish until the scope matches.`,
      };
    }
    if (socialDispatchEnabled) {
      return {
        tone: 'ok',
        titleRu: 'Публикация по расписанию включена',
        titleEn: 'Publishing worker is enabled',
        textRu: 'Посты в расписании будут обработаны по дате: API-каналы уйдут через подключённые интеграции, карты перейдут в контролируемое или ручное размещение.',
        textEn: 'Scheduled posts will be processed by date: API channels use adapters, maps move to supervised placement or manual handoff.',
      };
    }
    return {
      tone: 'warning',
      titleRu: 'Публикация по расписанию сейчас выключена',
      titleEn: 'Publishing worker is currently disabled',
      textRu: 'Можно готовить, проверять и ставить посты в расписание, но исполнение не начнётся до включения фонового запуска. Для Яндекс/2ГИС останется контролируемое или ручное размещение.',
      textEn: 'You can prepare, review, and queue posts, but automatic execution will not start until dispatch is enabled. Yandex/2GIS remain supervised handoff.',
    };
  }, [socialDispatchBlockedWithoutScope, socialDispatchEnabled, socialDispatchScopeMismatch, socialRuntimeStatus?.dispatch?.business_scope]);
  const socialQueueResultSummary = (selectedOnly: boolean) => {
    const subjectRu = selectedOnly ? 'Выбранные публикации поставлены в расписание.' : 'Утверждённые публикации поставлены в расписание.';
    const subjectEn = selectedOnly ? 'Selected posts are queued.' : 'Approved posts are queued.';
    if (socialDispatchBlockedWithoutScope) {
      return {
        tone: 'success',
        text_ru: `${subjectRu} Расписание сохранено, но LocalOS не запустит внешнее исполнение без SOCIAL_POST_DISPATCH_BUSINESS_ID или явного allow-all.`,
        text_en: `${subjectEn} The queue is saved, but LocalOS will not start the external worker without SOCIAL_POST_DISPATCH_BUSINESS_ID or explicit allow-all.`,
      };
    }
    if (socialDispatchScopeMismatch) {
      return {
        tone: 'success',
        text_ru: `${subjectRu} Расписание сохранено, но текущий исполнитель смотрит другой business scope и не обработает эти посты.`,
        text_en: `${subjectEn} The queue is saved, but the current worker is scoped to another business and will not process these posts.`,
      };
    }
    if (socialDispatchEnabled) {
      return {
        tone: 'success',
        text_ru: `${subjectRu} Исполнитель обработает их по дате: API-каналы пойдут через интеграции, Яндекс/2ГИС - в контролируемое размещение.`,
        text_en: `${subjectEn} The worker will process them on schedule: API channels use adapters, Yandex/2GIS move to supervised placement.`,
      };
    }
    return {
      tone: 'success',
      text_ru: `${subjectRu} Фоновый запуск выключен: расписание сохранено, но внешнее исполнение начнётся только после включения исполнителя.`,
      text_en: `${subjectEn} Dispatch is disabled: the queue is saved, but external execution starts only after the worker is enabled.`,
    };
  };
  const socialPlanNextStep = useMemo<SocialPlanNextStep>(() => {
    if (!currentPlan?.items?.length) {
      return {
        action: 'none',
        titleRu: 'Сначала нужен контент-план',
        titleEn: 'Start with a content plan',
        descriptionRu: 'После создания плана здесь появится очередь постов для карт и соцсетей.',
        descriptionEn: 'After creating a plan, this area will show map and social posts.',
        ctaRu: 'Создать план',
        ctaEn: 'Create plan',
        count: 0,
        disabled: true,
      };
    }
    if (Number(socialSummary?.total || 0) === 0) {
      return {
        action: 'prepare',
        titleRu: 'Подготовьте посты для каналов',
        titleEn: 'Prepare channel posts',
        descriptionRu: 'LocalOS разложит темы на Яндекс Карты, 2ГИС, Google, Telegram, VK, Instagram и Facebook. Наружу ничего не отправится.',
        descriptionEn: 'LocalOS will split topics into Yandex Maps, 2GIS, Google, Telegram, VK, Instagram, and Facebook. Nothing is sent externally.',
        ctaRu: selectedItems.length > 0 ? 'Подготовить выбранные' : 'Подготовить ближайшие темы',
        ctaEn: selectedItems.length > 0 ? 'Prepare selected' : 'Prepare nearest topics',
        count: selectedItems.length || Math.min(visibleItems.length, 5),
        disabled: visibleItems.length === 0,
      };
    }
    if (visibleSocialNeedsReview.length > 0) {
      return {
        action: 'review',
        titleRu: 'Проверьте тексты перед подтверждением',
        titleEn: 'Review copy before approval',
        descriptionRu: 'Это безопасный предпросмотр: текст можно поправить, а внешняя публикация ещё не запускается.',
        descriptionEn: 'This is the safe preview step: copy can be edited and external publishing is not started yet.',
        ctaRu: 'Открыть на проверку',
        ctaEn: 'Open review',
        count: visibleSocialNeedsReview.length,
      };
    }
    if (visibleSocialCanQueue.length > 0) {
      return {
        action: 'queue',
        titleRu: socialDispatchBlockedWithoutScope
          ? 'Поставьте в расписание, затем выберите бизнес для запуска'
          : socialDispatchScopeMismatch
            ? 'Поставьте в расписание, затем исправьте область запуска'
            : socialDispatchEnabled ? 'Поставьте утверждённое в расписание' : 'Поставьте в расписание, затем включите фоновый запуск',
        titleEn: socialDispatchBlockedWithoutScope
          ? 'Queue posts, then set business scope'
          : socialDispatchScopeMismatch
            ? 'Queue posts, then fix dispatch scope'
            : socialDispatchEnabled ? 'Queue approved posts' : 'Queue posts, then enable dispatch',
        descriptionRu: socialDispatchBlockedWithoutScope
          ? 'Расписание зафиксирует подтверждение и даты, но исполнитель не начнёт внешние действия, пока фоновый запуск включён без SOCIAL_POST_DISPATCH_BUSINESS_ID.'
          : socialDispatchScopeMismatch
            ? 'Расписание зафиксирует подтверждение и даты, но исполнитель сейчас смотрит другой бизнес и не обработает эти посты.'
            : socialDispatchEnabled
              ? 'Исполнитель сможет по дате отправить API-каналы, а карты перевести в контролируемое размещение.'
              : 'Расписание зафиксирует подтверждение и даты, но внешнее исполнение не стартует, пока фоновый запуск выключен.',
        descriptionEn: socialDispatchBlockedWithoutScope
          ? 'Queueing records approval and dates, but the worker will not start external actions while dispatch is enabled without SOCIAL_POST_DISPATCH_BUSINESS_ID.'
          : socialDispatchScopeMismatch
            ? 'Queueing records approval and dates, but the worker is scoped to another business and will not process these posts.'
            : socialDispatchEnabled
              ? 'The worker can publish API channels on schedule and move maps to supervised placement.'
              : 'Queueing records approval and dates, but external execution will not start while worker dispatch is disabled.',
        ctaRu: 'Поставить в расписание',
        ctaEn: 'Queue on schedule',
        count: visibleSocialCanQueue.length,
      };
    }
    if (visibleSocialNeedsSupervised.length > 0) {
      return {
        action: 'supervised',
        titleRu: 'Завершите контролируемое размещение',
        titleEn: 'Finish supervised placement',
        descriptionRu: 'Яндекс/2ГИС не считаются стабильным API publish. Откройте задачу, проверьте текст и отметьте размещение.',
        descriptionEn: 'Yandex/2GIS are not treated as stable API publish. Open the task, verify copy, and mark placement.',
        ctaRu: 'Открыть задачу',
        ctaEn: 'Open task',
        count: visibleSocialNeedsSupervised.length,
      };
    }
    if (visibleSocialNeedsManual.length > 0) {
      return {
        action: 'manual',
        titleRu: 'Подключите канал или разместите вручную',
        titleEn: 'Connect the channel or publish manually',
        descriptionRu: 'Этот статус означает не OpenClaw-задачу, а отсутствие ключей/прав или ручной режим. Исправьте подключение либо отметьте размещение вручную.',
        descriptionEn: 'This status is not an OpenClaw task: keys/permissions are missing or manual fallback is needed. Fix the connection or mark manual placement.',
        ctaRu: 'Открыть публикацию',
        ctaEn: 'Open post',
        count: visibleSocialNeedsManual.length,
      };
    }
    if (Number(socialSummary?.published || 0) > 0) {
      if (!socialPrimaryResultCount && !socialEarlySignalCount && !socialRecommendation?.learning_readiness) {
        return {
          action: 'collect',
          titleRu: 'Соберите реакции после публикаций',
          titleEn: 'Collect reactions after publishing',
          descriptionRu: 'Опубликованные посты уже есть. Сначала обновите реакции и ручные заявки, затем LocalOS предложит изменения следующей недели.',
          descriptionEn: 'Published posts exist. First update reactions and manual leads, then LocalOS will suggest next-week changes.',
          ctaRu: 'Собрать реакции',
          ctaEn: 'Collect reactions',
          count: Number(socialSummary?.published || 0),
        };
      }
      return {
        action: 'recommend',
        titleRu: 'Соберите выводы для следующего плана',
        titleEn: 'Collect next-plan learnings',
        descriptionRu: 'LocalOS сравнит заявки, обращения и реакции, но изменения в будущий план применит только после подтверждения.',
        descriptionEn: 'LocalOS compares leads, inquiries, and reactions, but applies next-plan changes only after approval.',
        ctaRu: 'Предложить изменения',
        ctaEn: 'Suggest changes',
        count: Number(socialSummary?.published || 0),
      };
    }
    if (Number(socialSummary?.scheduled || 0) > 0) {
      return {
        action: 'wait',
        titleRu: 'Публикации ждут дату',
        titleEn: 'Posts are waiting for schedule',
        descriptionRu: 'Исполнитель возьмёт только подтверждённые посты, когда наступит дата. Если канал не готов, конкретный пост получит понятный статус.',
        descriptionEn: 'The worker picks only due approved posts. If a channel is not ready, that post gets a clear status.',
        ctaRu: 'Обновить очередь',
        ctaEn: 'Refresh queue',
        count: Number(socialSummary?.scheduled || 0),
      };
    }
    return {
      action: 'none',
      titleRu: 'Очередь под контролем',
      titleEn: 'Queue is under control',
      descriptionRu: 'Подготовьте новые темы или дождитесь результатов опубликованных постов.',
      descriptionEn: 'Prepare new topics or wait for results from published posts.',
      ctaRu: 'Обновить',
      ctaEn: 'Refresh',
      count: Number(socialSummary?.total || 0),
    };
  }, [
    currentPlan?.items?.length,
    selectedItems.length,
    socialDispatchBlockedWithoutScope,
    socialDispatchEnabled,
    socialDispatchScopeMismatch,
    socialSummary?.published,
    socialSummary?.scheduled,
    socialSummary?.total,
    visibleItems.length,
    visibleSocialCanQueue.length,
    visibleSocialNeedsManual.length,
    visibleSocialNeedsReview.length,
    visibleSocialNeedsSupervised.length,
  ]);
  const socialReadinessSummary = useMemo(() => {
    let apiReady = 0;
    let needsAttention = 0;
    let supervisedOrManual = 0;
    const blockedApiChannels: SocialChannelReadiness[] = [];
    for (const channel of socialChannelReadiness) {
      const mode = String(channel.publish_mode || '').trim();
      if (mode === 'openclaw_browser' || mode === 'local_supervised_browser' || mode === 'manual') {
        supervisedOrManual += 1;
      }
      if (mode === 'api' && channel.ready) {
        apiReady += 1;
      }
      if (!channel.ready) {
        needsAttention += 1;
        if (mode === 'api') blockedApiChannels.push(channel);
      }
    }
    return {
      apiReady,
      needsAttention,
      supervisedOrManual,
      blockedApiChannels,
    };
  }, [socialChannelReadiness]);
  const socialOverviewChannelHighlights = useMemo(() => {
    return [...socialChannelReadiness]
      .sort((a, b) => {
        const aMode = String(a.publish_mode || '').trim();
        const bMode = String(b.publish_mode || '').trim();
        const aControlled = aMode === 'openclaw_browser' || aMode === 'local_supervised_browser' || aMode === 'manual';
        const bControlled = bMode === 'openclaw_browser' || bMode === 'local_supervised_browser' || bMode === 'manual';
        const aRank = !a.ready && aMode === 'api' ? 0 : aControlled ? 1 : a.ready ? 2 : 3;
        const bRank = !b.ready && bMode === 'api' ? 0 : bControlled ? 1 : b.ready ? 2 : 3;
        return aRank - bRank;
      })
      .slice(0, 4);
  }, [socialChannelReadiness]);
  const socialReadinessSetupPath = useMemo(() => {
    const firstBlocked = socialReadinessSummary.blockedApiChannels[0];
    if (!firstBlocked) return '/dashboard/settings?focus=integrations';
    return firstBlocked.settings_path || _socialSettingsPathForPlatform(String(firstBlocked.platform || ''));
  }, [socialReadinessSummary.blockedApiChannels]);
  const socialChannelConnectionGuide = useMemo(() => {
    const apiChannels = socialChannelReadiness
      .filter((channel) => String(channel.publish_mode || '').trim() === 'api')
      .sort(_socialChannelSetupSort);
    const readyApiChannels = apiChannels.filter((channel) => Boolean(channel.ready));
    const blockedApiChannels = apiChannels.filter((channel) => !Boolean(channel.ready));
    const supervisedChannels = socialChannelReadiness
      .filter((channel) => String(channel.publish_mode || '').trim() !== 'api')
      .sort(_socialChannelSetupSort);
    const firstBlocked = blockedApiChannels[0] || null;
    const quickStartCandidate = readyApiChannels.find((channel) => (
      String(channel.platform || '').trim() === 'telegram'
      || String(channel.platform || '').trim() === 'vk'
    )) || readyApiChannels[0] || null;
    const recommendedSetup = blockedApiChannels.find((channel) => (
      String(channel.platform || '').trim() === 'telegram'
      || String(channel.platform || '').trim() === 'vk'
    )) || firstBlocked;
    return {
      apiChannels,
      readyApiChannels,
      blockedApiChannels,
      supervisedChannels,
      firstBlocked,
      quickStartCandidate,
      recommendedSetup,
      readyToStart: readyApiChannels.length > 0,
    };
  }, [socialChannelReadiness]);
  const socialChannelReadinessByPlatform = useMemo(() => {
    const byPlatform: Record<string, SocialChannelReadiness> = {};
    for (const item of socialChannelReadiness) {
      const platform = String(item.platform || '').trim();
      if (platform) byPlatform[platform] = item;
    }
    return byPlatform;
  }, [socialChannelReadiness]);
  const socialApiPreflightByPlatform = useMemo(() => {
    const byPlatform: Record<string, SocialApiChannelPreflight> = {};
    for (const item of socialApiPreflight) {
      const platform = String(item.platform || '').trim();
      if (platform) byPlatform[platform] = item;
    }
    return byPlatform;
  }, [socialApiPreflight]);
  const socialApiPreflightSummary = useMemo(() => {
    const ready = socialApiPreflight.filter((item) => Boolean(item.ready));
    const needsAttention = socialApiPreflight.filter((item) => !Boolean(item.ready));
    return {
      checked: socialApiPreflight.length,
      ready,
      needsAttention,
    };
  }, [socialApiPreflight]);
  const socialFirstApiPublishReadiness = useMemo(() => {
    const apiChannels = socialChannelReadiness.filter((channel) => String(channel.publish_mode || '').trim() === 'api');
    const readyChannels = apiChannels.filter((channel) => Boolean(channel.ready));
    const blockedChannels = apiChannels.filter((channel) => !Boolean(channel.ready));
    const liveReady = socialApiPreflight.filter((item) => Boolean(item.ready));
    const liveBlocked = socialApiPreflight.filter((item) => !Boolean(item.ready));
    const primaryReady = liveReady.length > 0 ? liveReady : readyChannels;
    const primaryBlocked = liveBlocked.length > 0 ? liveBlocked : blockedChannels;
    const firstReady = primaryReady[0];
    const firstBlocked = primaryBlocked[0];
    const readyLabels = primaryReady.map((item) => String(item.platform_label || _socialPlatformLabel(String(item.platform || ''), isRu)));
    const blockedLabels = primaryBlocked.map((item) => String(item.platform_label || _socialPlatformLabel(String(item.platform || ''), isRu)));
    const fastStartPlatforms = ['telegram', 'vk'];
    const fastStartReady = primaryReady.filter((item) => fastStartPlatforms.includes(String(item.platform || '').trim()));
    const fastStartBlocked = primaryBlocked.filter((item) => fastStartPlatforms.includes(String(item.platform || '').trim()));
    const fastStartReadyLabels = fastStartReady.map((item) => String(item.platform_label || _socialPlatformLabel(String(item.platform || ''), isRu)));
    const fastStartBlockedLabels = fastStartBlocked.map((item) => String(item.platform_label || _socialPlatformLabel(String(item.platform || ''), isRu)));
    const setupFocus = fastStartBlocked[0] || firstBlocked;
    const setupFocusStepsSource = isRu
      ? setupFocus?.setup_steps_ru
      : setupFocus?.setup_steps_en;
    const setupFocusSteps = Array.isArray(setupFocusStepsSource)
      ? setupFocusStepsSource.filter(Boolean).map(String).slice(0, 4)
      : [];
    const setupFocusChecks = Array.isArray(setupFocus?.connection_checks)
      ? setupFocus.connection_checks.filter((item) => !Boolean(item.ok)).slice(0, 4)
      : [];
    const setupFocusMissingFields = Array.isArray(setupFocus?.missing_fields)
      ? setupFocus.missing_fields.filter(Boolean).map(String).slice(0, 4)
      : [];
    return {
      apiChannels,
      readyChannels,
      blockedChannels,
      liveReady,
      liveBlocked,
      firstReady,
      firstBlocked,
      readyLabels,
      blockedLabels,
      fastStartReady,
      fastStartBlocked,
      fastStartReadyLabels,
      fastStartBlockedLabels,
      setupFocus,
      setupFocusSteps,
      setupFocusChecks,
      setupFocusMissingFields,
      hasLiveCheck: socialApiPreflight.length > 0,
      readyForFirstApiPublish: primaryReady.length > 0 && primaryBlocked.length === 0,
      hasAnyReadyApi: primaryReady.length > 0,
    };
  }, [isRu, socialApiPreflight, socialChannelReadiness]);
  const socialFirstApiBlockerCard = useMemo(() => {
    const totalPosts = Number(socialSummary?.total || 0);
    const needsReview = Math.max(visibleSocialNeedsReview.length, Number(socialSummary?.needs_review || 0));
    const approvedNotQueued = visibleSocialCanQueue.length;
    const queued = Number(socialSummary?.scheduled || 0);
    const firstBlocked = socialFirstApiPublishReadiness.firstBlocked;
    const firstBlockedPlatform = String(firstBlocked?.platform || '').trim();
    const firstBlockedLabel = firstBlocked
      ? String(firstBlocked.platform_label || _socialPlatformLabel(firstBlockedPlatform, isRu))
      : 'Telegram';
    const firstBlockedStatus = String(firstBlocked?.status || '').trim();
    const channelLineRu = socialFirstApiPublishReadiness.hasAnyReadyApi
      ? `Канал: готово ${socialFirstApiPublishReadiness.readyLabels.join(', ')}.`
      : `Канал: ${firstBlockedLabel} - нужны ключи или права.`;
    const channelLineEn = socialFirstApiPublishReadiness.hasAnyReadyApi
      ? `Channel: ready ${socialFirstApiPublishReadiness.readyLabels.join(', ')}.`
      : `Channel: ${firstBlockedLabel} needs keys or permissions.`;
    const textLineRu = socialPostsLoading
      ? 'Посты: обновляем очередь публикаций по этому плану.'
      : totalPosts > 0
      ? `Посты: ${needsReview} на проверке, ${approvedNotQueued} утверждено, ${queued} в расписании.`
      : 'Посты: сначала подготовьте публикации из тем контент-плана.';
    const textLineEn = socialPostsLoading
      ? 'Posts: refreshing the publishing queue for this plan.'
      : totalPosts > 0
      ? `Posts: ${needsReview} in review, ${approvedNotQueued} approved, ${queued} queued.`
      : 'Posts: first prepare publications from content-plan topics.';
    let status: 'connect' | 'prepare' | 'review' | 'queue' | 'wait' | 'ready' = 'ready';
    let titleRu = 'Первый рабочий запуск почти готов';
    let titleEn = 'First working launch is almost ready';
    let nextRu = 'Проверьте запуск по расписанию и после публикации соберите реакции/заявки.';
    let nextEn = 'Check scheduled launch and collect reactions/leads after publishing.';
    let ctaRu = 'Проверить запуск';
    let ctaEn = 'Check launch';

    if (socialPostsLoading) {
      status = 'prepare';
      titleRu = 'Обновляем очередь публикаций';
      titleEn = 'Refreshing the publishing queue';
      nextRu = 'Подождите пару секунд: LocalOS сверяет готовые тексты, подтверждения и расписание.';
      nextEn = 'Wait a moment: LocalOS is checking prepared copy, approvals, and schedule.';
      ctaRu = 'Обновляем';
      ctaEn = 'Refreshing';
    } else if (!socialFirstApiPublishReadiness.hasAnyReadyApi) {
      status = 'connect';
      titleRu = 'Первый запуск ждёт подключение канала';
      titleEn = 'First launch is waiting for channel setup';
      const permissionsIssue = firstBlockedStatus.includes('permission') || firstBlockedStatus.includes('forbidden');
      nextRu = permissionsIssue
        ? `Проверьте права ${firstBlockedLabel}, затем вернитесь к проверке текстов и расписанию.`
        : `Подключите ${firstBlockedLabel}, затем вернитесь к проверке текстов и расписанию.`;
      nextEn = permissionsIssue
        ? `Check ${firstBlockedLabel} permissions, then return to copy review and queueing.`
        : `Connect ${firstBlockedLabel}, then return to copy review and queueing.`;
      ctaRu = 'Открыть настройку канала';
      ctaEn = 'Open channel setup';
    } else if (totalPosts === 0) {
      status = 'prepare';
      titleRu = 'Первый запуск ждёт подготовку постов';
      titleEn = 'First launch is waiting for post preparation';
      nextRu = 'Подготовьте каналы из ближайших тем; наружу на этом шаге ничего не отправится.';
      nextEn = 'Prepare channel posts from the next topics; nothing is sent externally at this step.';
      ctaRu = 'Подготовить посты';
      ctaEn = 'Prepare posts';
    } else if (needsReview > 0) {
      status = 'review';
      titleRu = 'Первый запуск ждёт проверку текстов';
      titleEn = 'First launch is waiting for copy review';
      nextRu = 'Откройте предпросмотр, поправьте текст и подтвердите публикации отдельной кнопкой.';
      nextEn = 'Open the preview, edit copy, and approve publications with a separate button.';
      ctaRu = 'Открыть проверку';
      ctaEn = 'Open review';
    } else if (approvedNotQueued > 0) {
      status = 'queue';
      titleRu = 'Первый запуск ждёт расписание';
      titleEn = 'First launch is waiting for queueing';
      nextRu = 'Поставьте утверждённые посты в расписание; исполнитель возьмёт их только по дате.';
      nextEn = 'Queue approved posts; the worker will pick them only when due.';
      ctaRu = 'Поставить в расписание';
      ctaEn = 'Queue on schedule';
    } else if (queued > 0) {
      status = 'wait';
      titleRu = 'Первый запуск ждёт дату публикации';
      titleEn = 'First launch is waiting for the publish date';
      nextRu = 'Когда наступит дата, API-каналы пойдут через интеграции, а Яндекс/2ГИС останутся контролируемыми.';
      nextEn = 'When due, API channels use integrations while Yandex/2GIS stay supervised.';
      ctaRu = 'Проверить запуск';
      ctaEn = 'Check launch';
    }

    return {
      status,
      tone: status === 'connect' || status === 'review' ? 'warning' : status === 'ready' || status === 'wait' ? 'success' : 'neutral',
      firstBlockedPlatform,
      titleRu,
      titleEn,
      factsRu: [
        channelLineRu,
        textLineRu,
        'Карты: Яндекс/2ГИС только через контролируемое размещение или ручной режим.',
      ],
      factsEn: [
        channelLineEn,
        textLineEn,
        'Maps: Yandex/2GIS only use supervised placement or manual mode.',
      ],
      nextRu,
      nextEn,
      ctaRu,
      ctaEn,
    };
  }, [
    isRu,
    socialFirstApiPublishReadiness.firstBlocked,
    socialFirstApiPublishReadiness.hasAnyReadyApi,
    socialFirstApiPublishReadiness.readyLabels,
    socialPostsLoading,
    socialSummary?.needs_review,
    socialSummary?.scheduled,
    socialSummary?.total,
    visibleSocialCanQueue.length,
    visibleSocialNeedsReview.length,
  ]);
  const selectedSocialQueueApiWarnings = useMemo(() => (
    _socialApiQueueWarnings(selectedSocialCanQueue, socialApiPreflightByPlatform, socialChannelReadinessByPlatform, isRu)
  ), [isRu, selectedSocialCanQueue, socialApiPreflightByPlatform, socialChannelReadinessByPlatform]);
  const socialApprovalPreviewSummary = useMemo(() => {
    if (!socialApprovalPreview) return null;
    return _socialApprovalSummary(socialApprovalPreview.posts, socialApiPreflightByPlatform, socialChannelReadinessByPlatform, isRu);
  }, [isRu, socialApiPreflightByPlatform, socialApprovalPreview, socialChannelReadinessByPlatform]);
  const socialQueuePreviewSummary = useMemo(() => {
    if (!socialQueuePreview) return null;
    return _socialQueueSummary(socialQueuePreview.posts, socialApiPreflightByPlatform, socialChannelReadinessByPlatform, isRu);
  }, [isRu, socialApiPreflightByPlatform, socialQueuePreview, socialChannelReadinessByPlatform]);
  const localSocialLaunchStages = useMemo<SocialLaunchStage[]>(() => {
    const totalPosts = Number(socialSummary?.total || 0);
    const needsReview = visibleSocialNeedsReview.length;
    const canQueue = visibleSocialCanQueue.length;
    const scheduled = Number(socialSummary?.scheduled || 0);
    const supervised = visibleSocialNeedsSupervised.length;
    const manual = visibleSocialNeedsManual.length;
    const published = Number(socialSummary?.published || 0);
    const failed = Number(socialSummary?.failed || 0);
    const hasPlan = Boolean(currentPlan?.items?.length);
    const hasRecommendation = Number(socialRecommendation?.proposed_changes?.length || 0) > 0;
    const channelsPrepared = totalPosts > 0;

    return [
      {
        key: 'plan',
        labelRu: 'План есть',
        labelEn: 'Plan exists',
        status: hasPlan ? 'done' : 'current',
        detailRu: hasPlan
          ? `Тем в плане: ${Number(currentPlan?.items?.length || 0)}`
          : 'Создайте контент-план, потом LocalOS разложит темы по каналам.',
        detailEn: hasPlan
          ? `Plan items: ${Number(currentPlan?.items?.length || 0)}`
          : 'Create a content plan, then LocalOS will split topics by channel.',
        count: Number(currentPlan?.items?.length || 0),
      },
      {
        key: 'channels',
        labelRu: channelsPrepared ? 'Каналы подготовлены' : 'Подготовить каналы',
        labelEn: channelsPrepared ? 'Channels prepared' : 'Prepare channels',
        status: !hasPlan ? 'pending' : channelsPrepared ? 'done' : 'current',
        detailRu: channelsPrepared
          ? `Публикаций по каналам: ${totalPosts}`
          : 'Нажмите “Подготовить каналы”, внешних публикаций на этом шаге нет.',
        detailEn: channelsPrepared
          ? `Channel posts: ${totalPosts}`
          : 'Click “Prepare channels”; no external publishing happens at this step.',
        count: totalPosts,
      },
      {
        key: 'review',
        labelRu: 'Тексты проверены',
        labelEn: 'Copy reviewed',
        status: totalPosts === 0 ? 'pending' : needsReview > 0 ? 'current' : 'done',
        detailRu: needsReview > 0
          ? `Нужно проверить перед подтверждением: ${needsReview}`
          : 'Предпросмотр и подтверждение отделены от постановки в расписание.',
        detailEn: needsReview > 0
          ? `Needs review before approval: ${needsReview}`
          : 'Preview and approval are separate from queueing.',
        count: needsReview,
      },
      {
        key: 'schedule',
        labelRu: 'Поставлено в расписание',
        labelEn: 'Queued on schedule',
        status: canQueue > 0
          ? 'current'
          : scheduled > 0 || published > 0 || supervised > 0 || manual > 0
            ? 'done'
            : totalPosts > 0
              ? 'pending'
              : 'pending',
        detailRu: canQueue > 0
          ? `Утверждено, но ещё не в расписании: ${canQueue}`
          : scheduled > 0
            ? `Ждёт даты публикации: ${scheduled}`
            : 'После подтверждения нажмите “Поставить в расписание”.',
        detailEn: canQueue > 0
          ? `Approved but not queued: ${canQueue}`
          : scheduled > 0
            ? `Waiting for publish date: ${scheduled}`
            : 'After approval, click “Queue on schedule”.',
        count: canQueue || scheduled,
      },
      {
        key: 'execution',
        labelRu: 'Исполнение понятно',
        labelEn: 'Execution is clear',
        status: failed > 0
          ? 'attention'
          : supervised > 0 || manual > 0
            ? 'current'
            : published > 0
              ? 'done'
              : scheduled > 0
                ? 'current'
                : 'pending',
        detailRu: failed > 0
          ? `Есть ошибки: ${failed}. Откройте карточку и выберите повтор/ручной режим.`
          : supervised > 0
            ? `Яндекс/2ГИС ждут контролируемое размещение: ${supervised}`
            : manual > 0
              ? `Нужен ручной режим или подключение: ${manual}`
              : published > 0
                ? `Опубликовано: ${published}`
                : 'API уйдут по расписанию; карты останутся в контролируемом или ручном режиме.',
        detailEn: failed > 0
          ? `Failures: ${failed}. Open the post and retry or switch to manual mode.`
          : supervised > 0
            ? `Yandex/2GIS await supervised placement: ${supervised}`
            : manual > 0
              ? `Manual fallback or connection needed: ${manual}`
              : published > 0
                ? `Published: ${published}`
                : 'API channels run through the worker; maps stay supervised/manual.',
        count: failed || supervised || manual || published || scheduled,
      },
      {
        key: 'learning',
        labelRu: 'План улучшается',
        labelEn: 'Plan improves',
        status: hasRecommendation
          ? 'current'
          : published > 0
            ? 'current'
            : 'pending',
        detailRu: hasRecommendation
          ? 'Есть предложения к следующему плану. Применение только после подтверждения.'
          : published > 0
            ? 'Обновите реакции и заявки, затем предложите изменения следующей недели.'
            : 'После публикаций LocalOS ранжирует заявки и обращения выше охватов.',
        detailEn: hasRecommendation
          ? 'Next-plan changes are ready. Applying still requires confirmation.'
          : published > 0
            ? 'Update reactions and leads, then suggest next-week changes.'
            : 'After publishing, LocalOS ranks leads and inquiries above reach.',
        count: Number(socialRecommendation?.proposed_changes?.length || 0),
      },
    ];
  }, [
    currentPlan?.items?.length,
    socialRecommendation?.proposed_changes?.length,
    socialSummary?.failed,
    socialSummary?.published,
    socialSummary?.scheduled,
    socialSummary?.total,
    socialRecommendation?.learning_readiness,
    socialEarlySignalCount,
    socialPrimaryResultCount,
    visibleSocialCanQueue.length,
    visibleSocialNeedsManual.length,
    visibleSocialNeedsReview.length,
    visibleSocialNeedsSupervised.length,
  ]);
  const socialLaunchStages = useMemo<SocialLaunchStage[]>(() => {
    const apiStages = Array.isArray(socialGoalProgress?.stages) ? socialGoalProgress?.stages || [] : [];
    const normalizedStages = apiStages
      .map((stage) => _normalizeSocialGoalStage(stage))
      .filter((stage): stage is SocialLaunchStage => Boolean(stage));
    return normalizedStages.length > 0 ? normalizedStages : localSocialLaunchStages;
  }, [localSocialLaunchStages, socialGoalProgress?.stages]);
  const socialLaunchChecklistSummary = useMemo(() => {
    const done = socialLaunchStages.filter((stage) => stage.status === 'done').length;
    const attention = socialLaunchStages.filter((stage) => stage.status === 'attention').length;
    const current = socialLaunchStages.find((stage) => stage.status === 'attention')
      || socialLaunchStages.find((stage) => stage.status === 'current')
      || socialLaunchStages.find((stage) => stage.status === 'pending')
      || socialLaunchStages[socialLaunchStages.length - 1];
    return {
      done,
      total: socialLaunchStages.length,
      attention,
      current,
    };
  }, [socialLaunchStages]);
  const missingDateCandidates = useMemo(() => (
    visibleItems.filter((item) => !_inputDateValue(item.scheduled_for) && !String(item.usernews_id || '').trim())
  ), [visibleItems]);
  const planOperationalSummary = useMemo(() => {
    const items = currentPlan?.items || [];
    return items.reduce(
      (acc, item) => {
        const status = String(item.status || '').trim();
        const hasDraft = Boolean(String(item.draft_text || '').trim());
        const hasNews = Boolean(String(item.usernews_id || '').trim());
        acc.total += 1;
        if (status === 'skipped') {
          acc.skipped += 1;
          return acc;
        }
        if (!hasDraft) acc.needsDraft += 1;
        if (hasDraft && !hasNews) acc.readyToPublish += 1;
        if (hasNews) acc.published += 1;
        return acc;
      },
      {
        total: 0,
        needsDraft: 0,
        readyToPublish: 0,
        published: 0,
        skipped: 0,
      },
    );
  }, [currentPlan?.items]);
  const overviewRiskScore = useMemo(() => {
    const networkRisk = Math.max(...(learningMetrics?.network_quality || []).map((item) => Number(item.risk_score || 0)), 0);
    const skippedRisk = planOperationalSummary.skipped > 0 ? Math.min(100, planOperationalSummary.skipped * 12) : 0;
    const emptyRisk = planOperationalSummary.total > 0 && planOperationalSummary.needsDraft === planOperationalSummary.total ? 35 : 0;
    return Math.max(networkRisk, skippedRisk, emptyRisk);
  }, [learningMetrics?.network_quality, planOperationalSummary.needsDraft, planOperationalSummary.skipped, planOperationalSummary.total]);
  const repeatTemplateCandidate = useMemo(() => (
    (currentPlan?.items || []).find((item) => (
      Boolean(String(item.draft_text || item.usernews_id || '').trim())
      && availableItemLocations.length > 2
    )) || null
  ), [currentPlan?.items, availableItemLocations.length]);
  const viewPresets = useMemo<Array<{ key: ViewPresetKey; label: string }>>(() => ([
    {
      key: 'overview',
      label: isRu ? 'Обзор' : 'Overview',
    },
    {
      key: 'ready',
      label: isRu ? 'Тексты готовы' : 'Drafts ready',
    },
    {
      key: 'urgent',
      label: isRu ? 'Срочное' : 'Urgent',
    },
  ]), [
    isRu,
  ]);
  const activeLocationLabel = useMemo(() => {
    const activeLocation = availableItemLocations.find((item) => item.key === selectedItemLocationKey);
    return activeLocation?.label || (isRu ? 'Все точки' : 'All locations');
  }, [availableItemLocations, selectedItemLocationKey, isRu]);
  const activeWeekLabel = useMemo(() => {
    const activeWeek = availableWeeks.find((item) => item.key === selectedWeekKey);
    return activeWeek?.label || (isRu ? 'Все недели' : 'All weeks');
  }, [availableWeeks, selectedWeekKey, isRu]);
  const locationWeekFocusSummary = useMemo(() => {
    const buckets = new Map<string, {
      key: string;
      locationKey: string;
      weekKey: string;
      locationLabel: string;
      weekLabel: string;
      total: number;
      needsDraft: number;
      readyToPublish: number;
    }>();
    for (const item of currentPlan?.items || []) {
      if (String(item.status || '').trim() === 'skipped') continue;
      const locationKey = String(item.location_scope || item.business_id || '').trim();
      const weekKey = _weekBucketKey(item.scheduled_for);
      if (!locationKey || !weekKey) continue;
      const bucketKey = `${locationKey}::${weekKey}`;
      const existing = buckets.get(bucketKey) || {
        key: bucketKey,
        locationKey,
        weekKey,
        locationLabel: _itemLocationLabel(item, isRu),
        weekLabel: _weekBucketLabel(weekKey, isRu),
        total: 0,
        needsDraft: 0,
        readyToPublish: 0,
      };
      existing.total += 1;
      const hasDraft = Boolean(String(item.draft_text || '').trim());
      const hasNews = Boolean(String(item.usernews_id || '').trim());
      if (!hasDraft) {
        existing.needsDraft += 1;
      }
      if (hasDraft && !hasNews) {
        existing.readyToPublish += 1;
      }
      buckets.set(bucketKey, existing);
    }
    return Array.from(buckets.values())
      .filter((item) => item.needsDraft > 0 || item.readyToPublish > 0)
      .sort((left, right) => {
        const needsDraftDiff = right.needsDraft - left.needsDraft;
        if (needsDraftDiff !== 0) return needsDraftDiff;
        const readyDiff = right.readyToPublish - left.readyToPublish;
        if (readyDiff !== 0) return readyDiff;
        return right.total - left.total;
      })
      .slice(0, 6);
  }, [currentPlan?.items, isRu]);
  const networkOperatingSlices = useMemo<NetworkOperatingSlice[]>(() => {
    if (!isNetworkMode || !currentPlan?.items?.length) return [];
    const qualityByLocation = new Map<string, NonNullable<LearningMetricsPayload['network_quality']>[number]>();
    for (const item of learningMetrics?.network_quality || []) {
      const key = String(item.key || '').trim();
      if (key) qualityByLocation.set(key, item);
    }
    const locationKeys = new Set<string>();
    for (const item of currentPlan.items) {
      const key = String(item.location_scope || item.business_id || '').trim();
      if (key) locationKeys.add(key);
    }
    const slices: NetworkOperatingSlice[] = [];
    for (const locationKey of Array.from(locationKeys)) {
      const locationItems = currentPlan.items.filter((item) => String(item.location_scope || item.business_id || '').trim() === locationKey);
      if (locationItems.length === 0) continue;
      const quality = qualityByLocation.get(locationKey);
      const firstItem = locationItems[0];
      let needsDraft = 0;
      let readyToPublish = 0;
      let published = 0;
      let skipped = 0;
      const weekBuckets = new Map<string, { key: string; needsDraft: number; readyToPublish: number; total: number }>();
      for (const item of locationItems) {
        const status = String(item.status || '').trim();
        const hasDraft = Boolean(String(item.draft_text || '').trim());
        const hasNews = Boolean(String(item.usernews_id || '').trim());
        if (status === 'skipped') {
          skipped += 1;
          continue;
        }
        if (!hasDraft) needsDraft += 1;
        if (hasDraft && !hasNews) readyToPublish += 1;
        if (hasNews) published += 1;
        const weekKey = _weekBucketKey(item.scheduled_for);
        if (!weekKey) continue;
        const existing = weekBuckets.get(weekKey) || { key: weekKey, needsDraft: 0, readyToPublish: 0, total: 0 };
        existing.total += 1;
        if (!hasDraft) existing.needsDraft += 1;
        if (hasDraft && !hasNews) existing.readyToPublish += 1;
        weekBuckets.set(weekKey, existing);
      }
      const focusWeek = Array.from(weekBuckets.values())
        .filter((item) => item.needsDraft > 0 || item.readyToPublish > 0)
        .sort((left, right) => {
          const urgentDiff = (right.needsDraft + right.readyToPublish) - (left.needsDraft + left.readyToPublish);
          if (urgentDiff !== 0) return urgentDiff;
          return left.key.localeCompare(right.key);
        })[0] || Array.from(weekBuckets.values()).sort((left, right) => left.key.localeCompare(right.key))[0];
      const reasons = quality?.reasons && Array.isArray(quality.reasons) ? quality.reasons : [];
      slices.push({
        key: locationKey,
        label: String(quality?.label || _itemLocationLabel(firstItem, isRu) || locationKey),
        riskScore: Number(quality?.risk_score || 0),
        reasons,
        total: locationItems.length,
        needsDraft,
        readyToPublish,
        published,
        skipped,
        focusWeekKey: focusWeek?.key || 'all',
        focusWeekLabel: focusWeek?.key ? _weekBucketLabel(focusWeek.key, isRu) : (isRu ? 'Все недели' : 'All weeks'),
        focusWeekNeedsDraft: focusWeek?.needsDraft || 0,
        focusWeekReadyToPublish: focusWeek?.readyToPublish || 0,
        recommendation: _networkOperatingRecommendation(reasons, isRu),
      });
    }
    return slices
      .sort((left, right) => {
        const riskDiff = right.riskScore - left.riskScore;
        if (riskDiff !== 0) return riskDiff;
        const urgentDiff = (right.needsDraft + right.readyToPublish + right.skipped) - (left.needsDraft + left.readyToPublish + left.skipped);
        if (urgentDiff !== 0) return urgentDiff;
        return right.total - left.total;
      })
      .slice(0, 5);
  }, [currentPlan?.items, isNetworkMode, isRu, learningMetrics?.network_quality]);
  const quickActions = useMemo(() => {
    const weakLocation = (learningMetrics?.network_quality || [])[0];
    const focusSlice = locationWeekFocusSummary[0];
    const actions: Array<{
      key: QuickActionKey;
      title: string;
      description: string;
      metric: string;
      disabled: boolean;
    }> = [
      {
        key: 'open_week',
        title: isRu ? 'Открыть эту неделю' : 'Open this week',
        description: focusSlice
          ? `${focusSlice.locationLabel} · ${focusSlice.weekLabel}`
          : (isRu ? 'Показать ближайший рабочий срез.' : 'Show the nearest operating slice.'),
        metric: focusSlice ? `${focusSlice.needsDraft + focusSlice.readyToPublish}` : `${visibleItems.length}`,
        disabled: !currentPlan || (!focusSlice && visibleItems.length === 0),
      },
      {
        key: 'weak_locations',
        title: isRu ? 'Показать слабые точки' : 'Show weak locations',
        description: weakLocation
          ? `${String(weakLocation.label || weakLocation.key)} · ${isRu ? 'риск' : 'risk'} ${Number(weakLocation.risk_score || 0).toFixed(0)}`
          : (isRu ? 'Когда накопятся правки, здесь появятся проблемные точки.' : 'Risky locations appear here after edits accumulate.'),
        metric: `${learningMetrics?.network_quality?.length || 0}`,
        disabled: !weakLocation,
      },
      {
        key: 'fix_gaps',
        title: isRu ? 'Открыть темы без текста' : 'Open empty topics',
        description: isRu
          ? 'Это не создаёт новый план. Откроется текущая очередь с темами, где ещё нет текста.'
          : 'This does not create a new plan. It opens the current queue items that still need text.',
        metric: `${planOperationalSummary.needsDraft + planOperationalSummary.readyToPublish}`,
        disabled: !currentPlan || planOperationalSummary.needsDraft + planOperationalSummary.readyToPublish === 0,
      },
      {
        key: 'repeat_template',
        title: isRu ? 'Повторить удачную тему' : 'Repeat a winning template',
        description: repeatTemplateCandidate
          ? String(repeatTemplateCandidate.theme || '').trim()
          : (isRu ? 'Нужен хотя бы один готовый черновик и несколько точек.' : 'Needs one ready draft and multiple locations.'),
        metric: `${Math.max(availableItemLocations.length - 2, 0)}`,
        disabled: !repeatTemplateCandidate,
      },
    ];
    return actions;
  }, [
    availableItemLocations.length,
    currentPlan,
    isRu,
    learningMetrics?.network_quality,
    locationWeekFocusSummary,
    planOperationalSummary.needsDraft,
    planOperationalSummary.readyToPublish,
    repeatTemplateCandidate,
    visibleItems.length,
  ]);
  const operatorQualityInsights = useMemo(() => {
    const insights: OperatorInsight[] = [];
    for (const item of learningMetrics?.quality_insights || []) {
      const textRu = String(item.text_ru || '').trim();
      const textEn = String(item.text_en || '').trim();
      if (!textRu && !textEn) continue;
      insights.push({
        key: `metric:${item.kind}:${textRu}:${textEn}`,
        textRu,
        textEn,
      });
    }
    const weakSlice = networkOperatingSlices.find((item) => Number(item.riskScore || 0) >= 35);
    if (weakSlice) {
      insights.push({
        key: `network:${weakSlice.key}`,
        textRu: `${weakSlice.label}: точка требует внимания. ${weakSlice.recommendation}`,
        textEn: `${weakSlice.label}: this location needs attention. ${weakSlice.recommendation}`,
      });
    }
    if (planOperationalSummary.needsDraft > 0) {
      insights.push({
        key: 'plan:no-draft',
        textRu: `В плане ${planOperationalSummary.needsDraft} тем без текста. Начните с них, иначе план останется календарём идей, а не публикациями.`,
        textEn: `${planOperationalSummary.needsDraft} plan items have no draft. Start there or the plan stays a calendar of ideas, not publications.`,
      });
    }
    if (planOperationalSummary.readyToPublish > 0) {
      insights.push({
        key: 'plan:ready',
        textRu: `${planOperationalSummary.readyToPublish} черновиков уже готовы как текст. Следующий шаг — разложить их по каналам и проверить предпросмотр.`,
        textEn: `${planOperationalSummary.readyToPublish} drafts are ready as copy. Next, turn them into channel posts and review the preview.`,
      });
    }
    if (Number(learningMetrics?.summary?.edited_before_accept_pct || 0) >= 35) {
      insights.push({
        key: 'quality:edited-before-accept',
        textRu: 'Черновики часто правят перед публикацией. Значит генератору нужны более конкретные услуги, SEO-сценарии или примеры удачных тем.',
        textEn: 'Drafts are often edited before publishing. The generator needs more concrete services, SEO scenarios, or examples of good topics.',
      });
    }
    if (missingInputs.includes('seo_keywords')) {
      insights.push({
        key: 'input:seo',
        textRu: 'Плану не хватает SEO-ключей по реальному спросу. Без них темы слабее закрывают поисковые сценарии на картах.',
        textEn: 'The plan lacks real-demand SEO keywords. Without them, topics cover map search scenarios less precisely.',
      });
    }
    if (missingInputs.includes('services')) {
      insights.push({
        key: 'input:services',
        textRu: networkHasSearchPlanFoundation
          ? 'Для сети уже есть карты и SEO-спрос. Следующее усиление — добавить меню, товары или ключевые услуги, чтобы публикации были не только поисковыми, но и коммерческими.'
          : 'Плану не хватает списка услуг. Добавьте услуги, чтобы новости были не общими, а привязанными к конкретному выбору клиента.',
        textEn: networkHasSearchPlanFoundation
          ? 'The network already has map listings and SEO demand. The next upgrade is adding menu items, products, or key services so posts become commercial, not only search-driven.'
          : 'The plan lacks a service list. Add services so news posts are tied to concrete customer choices.',
      });
    }
    if (!context?.sales_signals?.length) {
      insights.push({
        key: 'input:sales',
        textRu: 'В плане пока нет продажных сигналов. Когда появятся продажи/популярные услуги, темы можно будет ранжировать по реальному спросу.',
        textEn: 'There are no sales signals yet. Once sales or popular services appear, topics can be ranked by real demand.',
      });
    }
    if (Number(learningMetrics?.summary?.skipped_total || 0) > 0) {
      insights.push({
        key: 'quality:skipped',
        textRu: `Пропущено тем: ${learningMetrics?.summary?.skipped_total || 0}. Это сигнал, что часть тем слишком абстрактная или неудобная для быстрой публикации.`,
        textEn: `${learningMetrics?.summary?.skipped_total || 0} topics were skipped. That usually means some topics are too abstract or hard to publish quickly.`,
      });
    }
    return insights.slice(0, 4);
  }, [
    context?.sales_signals?.length,
    learningMetrics?.quality_insights,
    learningMetrics?.summary?.skipped_total,
    learningMetrics?.summary?.edited_before_accept_pct,
    missingInputs,
    networkHasSearchPlanFoundation,
    networkOperatingSlices,
    planOperationalSummary.needsDraft,
    planOperationalSummary.readyToPublish,
  ]);

  const loadPlans = async () => {
    if (!businessId) return;
    const response = await newAuth.makeRequest(`/content-plans?business_id=${encodeURIComponent(businessId)}`, {
      method: 'GET',
    });
    const nextPlans = Array.isArray(response.plans) ? response.plans : [];
    setPlans(nextPlans);
    if (nextPlans.length > 0) {
      const latestPlan = nextPlans[0];
      const fullPlanResponse = await newAuth.makeRequest(`/content-plans/${encodeURIComponent(latestPlan.id)}`, {
        method: 'GET',
      });
      setCurrentPlan(fullPlanResponse.plan || null);
    } else {
      setCurrentPlan(null);
    }
  };

  const openPlan = async (planId: string) => {
    if (!planId) return;
    setError('');
    setActionSummary(null);
    try {
      const response = await newAuth.makeRequest(`/content-plans/${encodeURIComponent(planId)}`, { method: 'GET' });
      setCurrentPlan(response.plan || null);
      setActiveZone('queue');
      setShowRecentPlans(true);
      setEditorItemId('');
      setSelectedQueueItemId('');
      clearSelectedItems();
      setDraftEdits({});
      setThemeEdits({});
      setDateEdits({});
    } catch (planError) {
      const message = planError instanceof Error ? planError.message : (isRu ? 'Не удалось открыть план' : 'Could not open plan');
      setError(message);
    }
  };

  const deletePlan = async (planId: string) => {
    if (!planId) return;
    const confirmed = typeof window === 'undefined' ? true : window.confirm(isRu
      ? 'Удалить выбранный контент-план целиком? Темы внутри плана тоже будут удалены.'
      : 'Delete this content plan entirely? All topics inside it will also be deleted.');
    if (!confirmed) return;
    setError('');
    setActionSummary(null);
    try {
      await newAuth.makeRequest(`/content-plans/${encodeURIComponent(planId)}`, { method: 'DELETE' });
      const response = await newAuth.makeRequest(`/content-plans?business_id=${encodeURIComponent(businessId || '')}`, {
        method: 'GET',
      });
      const nextPlans = Array.isArray(response.plans) ? response.plans : [];
      setPlans(nextPlans);
      if (currentPlan?.id === planId) {
        if (nextPlans.length > 0) {
          const fullPlanResponse = await newAuth.makeRequest(`/content-plans/${encodeURIComponent(nextPlans[0].id)}`, {
            method: 'GET',
          });
          setCurrentPlan(fullPlanResponse.plan || null);
        } else {
          setCurrentPlan(null);
        }
      }
      setEditorItemId('');
      clearSelectedItems();
      setActionSummary({
        tone: 'success',
        text_ru: 'План удалён.',
        text_en: 'Plan deleted.',
      });
    } catch (deleteError) {
      const message = deleteError instanceof Error ? deleteError.message : (isRu ? 'Не удалось удалить план' : 'Could not delete plan');
      setError(message);
    }
  };

  const loadLearningMetrics = async () => {
    if (!businessId) return;
    setMetricsLoading(true);
    try {
      const response = await newAuth.makeRequest(`/content-plans/learning-metrics?business_id=${encodeURIComponent(businessId)}`, {
        method: 'GET',
      });
      setLearningMetrics(response || null);
    } catch {
      setLearningMetrics(null);
    } finally {
      setMetricsLoading(false);
    }
  };

  const loadSocialRuntimeStatus = async () => {
    try {
      const response = await newAuth.makeRequest('/social-posts/runtime-status', {
        method: 'GET',
      });
      setSocialRuntimeStatus({
        dispatch: response.dispatch || {},
        metrics: response.metrics || {},
        approval_required: Boolean(response.approval_required),
        browser_final_click_allowed: Boolean(response.browser_final_click_allowed),
      });
    } catch {
      setSocialRuntimeStatus(null);
    }
  };

  const loadSocialPosts = async (planId: string) => {
    if (!planId) return;
    setSocialPostsLoading(true);
    try {
      const response = await newAuth.makeRequest(`/content-plans/${encodeURIComponent(planId)}/social-posts`, {
        method: 'GET',
      });
      const posts = Array.isArray(response.posts) ? response.posts : [];
      const grouped: Record<string, SocialPost[]> = {};
      for (const post of posts) {
        const itemId = String(post.content_plan_item_id || '').trim();
        if (!itemId) continue;
        grouped[itemId] = [...(grouped[itemId] || []), post];
      }
      setSocialPostsByItem(grouped);
      setSocialSummary(response.summary || null);
      setSocialQueueGroups(Array.isArray(response.queue_groups) ? response.queue_groups : []);
      setSocialChannelReadiness(Array.isArray(response.channel_readiness) ? response.channel_readiness : []);
      setSocialGoalProgress(response.goal_progress && typeof response.goal_progress === 'object'
        ? response.goal_progress
        : null);
      setSocialFirstApiProofDossier(response.first_api_proof_dossier && typeof response.first_api_proof_dossier === 'object'
        ? response.first_api_proof_dossier
        : null);
      setSocialOpenClawReadiness(response.openclaw_browser_readiness && typeof response.openclaw_browser_readiness === 'object'
        ? response.openclaw_browser_readiness
        : null);
      setSocialRecommendation(response.recommendation || response.learning_readiness ? {
        recommendation: response.recommendation || {},
        learning_readiness: response.learning_readiness || undefined,
      } : null);
      setSocialRecommendationApproved(false);
    } catch {
      setSocialPostsByItem({});
      setSocialSummary(null);
      setSocialQueueGroups([]);
      setSocialChannelReadiness([]);
      setSocialGoalProgress(null);
      setSocialFirstApiProofDossier(null);
      setSocialOpenClawReadiness(null);
      setSocialRecommendation(null);
      setSocialRecommendationApproved(false);
      setSocialDispatchPreview(null);
      setSocialDispatchExecutionReport(null);
      setSocialLaunchPreflight(null);
    } finally {
      setSocialPostsLoading(false);
    }
  };

  const loadContext = async (scopeKey?: string) => {
    if (!businessId) return;
    setLoading(true);
    setError('');
    try {
      const scopeValue = scopeKey || selectedScopeKey;
      let scopeType = '';
      let scopeTargetId = '';
      if (scopeValue) {
        const separatorIndex = scopeValue.indexOf(':');
        if (separatorIndex >= 0) {
          scopeType = scopeValue.slice(0, separatorIndex);
          scopeTargetId = scopeValue.slice(separatorIndex + 1);
        }
      }
      const query = new URLSearchParams({ business_id: businessId });
      if (scopeType) query.set('scope_type', scopeType);
      if (scopeTargetId) query.set('scope_target_id', scopeTargetId);
      const response = await newAuth.makeRequest(`/content-plans/context?${query.toString()}`, { method: 'GET' });
      const nextContext = response.context || null;
      setContext(nextContext);
      const nextScopeOptions = nextContext?.scope?.scope_options || [];
      if (!scopeValue && nextScopeOptions.length > 0) {
        const preferred = nextScopeOptions.find((item: ScopeOption) => item.is_current) || nextScopeOptions[0];
        if (preferred) {
          setSelectedScopeKey(`${preferred.scope_type}:${preferred.scope_target_id}`);
        }
      }
      const nextAllowedHorizons = nextContext?.subscription?.allowed_horizons || [30];
      if (!nextAllowedHorizons.includes(Number(selectedPeriod))) {
        setSelectedPeriod(String(nextAllowedHorizons[0] || 30));
      }
    } catch (loadError) {
      const message = loadError instanceof Error ? loadError.message : (isRu ? 'Не удалось загрузить контекст' : 'Could not load context');
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadContext();
    void loadPlans();
    void loadLearningMetrics();
    void loadSocialRuntimeStatus();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [businessId]);

  useEffect(() => {
    if (!currentPlan?.id) {
      setSocialPostsByItem({});
      setSocialSummary(null);
      setSocialQueueGroups([]);
      setSocialPostsLoading(false);
      return;
    }
    void loadSocialPosts(currentPlan.id);
  }, [currentPlan?.id]);

  useEffect(() => {
    if (!businessId) return;
    if (!selectedScopeKey) return;
    void loadContext(selectedScopeKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedScopeKey, businessId]);

  useEffect(() => {
    if (!scopeOptions.length) return;
    if (contentMode === 'network' && networkScopeOption) {
      const nextKey = `${networkScopeOption.scope_type}:${networkScopeOption.scope_target_id}`;
      if (selectedScopeKey !== nextKey) setSelectedScopeKey(nextKey);
      return;
    }
    if (contentMode === 'point' && pointScopeOption) {
      const nextKey = `${pointScopeOption.scope_type}:${pointScopeOption.scope_target_id}`;
      if (selectedScopeKey !== nextKey) setSelectedScopeKey(nextKey);
    }
  }, [contentMode, networkScopeOption, pointScopeOption, scopeOptions.length, selectedScopeKey]);

  useEffect(() => {
    if (availableWeeks.some((week) => week.key === selectedWeekKey)) return;
    setSelectedWeekKey('all');
  }, [availableWeeks, selectedWeekKey]);

  useEffect(() => {
    if (visibleItems.length === 0) {
      if (selectedQueueItemId) setSelectedQueueItemId('');
      if (editorItemId) setEditorItemId('');
      return;
    }
    if (selectedQueueItemId && visibleItems.some((item) => item.id === selectedQueueItemId)) return;
    setSelectedQueueItemId(visibleItems[0].id);
  }, [editorItemId, selectedQueueItemId, visibleItems]);

  useEffect(() => {
    if (!editorItemId) return;
    if (visibleItems.some((item) => item.id === editorItemId)) return;
    setEditorItemId('');
  }, [editorItemId, visibleItems]);

  useEffect(() => {
    setSelectedItemIds((prev) => {
      const visibleIds = new Set(visibleItems.map((item) => item.id));
      const next: Record<string, boolean> = {};
      for (const [itemId, isSelected] of Object.entries(prev)) {
        if (isSelected && visibleIds.has(itemId)) next[itemId] = true;
      }
      return next;
    });
  }, [visibleItems]);

  useEffect(() => {
    if (!businessId) return;
    const stored = _readStoredPreferences(businessId);
    if (!stored) return;
    if (_isValidItemFilterKey(stored.selectedItemFilter)) {
      setSelectedItemFilter(stored.selectedItemFilter);
    }
    if (typeof stored.dateFromFilter === 'string' && stored.dateFromFilter.trim()) {
      setDateFromFilter(stored.dateFromFilter.slice(0, 10));
    }
    if (typeof stored.dateToFilter === 'string' && stored.dateToFilter.trim()) {
      setDateToFilter(stored.dateToFilter.slice(0, 10));
    }
    if (typeof stored.lastFocusLocationKey === 'string' && stored.lastFocusLocationKey.trim()) {
      setLastFocusLocationKey(stored.lastFocusLocationKey);
    }
    if (typeof stored.lastFocusWeekKey === 'string' && stored.lastFocusWeekKey.trim()) {
      setLastFocusWeekKey(stored.lastFocusWeekKey);
    }
    if (stored.sortMode === 'priority' || stored.sortMode === 'date') {
      setSortMode(stored.sortMode);
    }
    if (_isValidContentLanguageKey(stored.contentLanguage)) {
      setContentLanguage(stored.contentLanguage);
    }
    if (_isValidViewPresetKey(stored.selectedViewPreset)) {
      setSelectedViewPreset(stored.selectedViewPreset);
    }
  }, [businessId]);

  useEffect(() => {
    if (selectedViewPreset !== 'focus') return;
    if (selectedItemLocationKey !== 'all') {
      setLastFocusLocationKey(selectedItemLocationKey);
    }
    if (selectedWeekKey !== 'all') {
      setLastFocusWeekKey(selectedWeekKey);
    }
  }, [selectedViewPreset, selectedItemLocationKey, selectedWeekKey]);

  useEffect(() => {
    setSelectedViewPreset(_inferViewPresetKey({
      selectedItemFilter,
      selectedSignalFilter,
      selectedPlanTargetKey,
      selectedItemLocationKey,
      selectedWeekKey,
      dateFromFilter,
      dateToFilter,
      sortMode,
    }));
  }, [
    selectedItemFilter,
    selectedSignalFilter,
    selectedPlanTargetKey,
    selectedItemLocationKey,
    selectedWeekKey,
    dateFromFilter,
    dateToFilter,
    sortMode,
  ]);

  useEffect(() => {
    if (!businessId) return;
    _writeStoredPreferences(businessId, {
      selectedViewPreset,
      lastFocusLocationKey,
      lastFocusWeekKey,
      selectedItemFilter,
      selectedSignalFilter,
      selectedPlanTargetKey,
      selectedItemLocationKey,
      selectedWeekKey,
      dateFromFilter,
      dateToFilter,
      sortMode,
      contentLanguage,
    });
  }, [
    businessId,
    selectedViewPreset,
    lastFocusLocationKey,
    lastFocusWeekKey,
    selectedItemFilter,
    selectedSignalFilter,
    selectedPlanTargetKey,
    selectedItemLocationKey,
    selectedWeekKey,
    dateFromFilter,
    dateToFilter,
    sortMode,
    contentLanguage,
  ]);

  const toggleMix = (key: ContentMixKey) => {
    setContentMix((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const toggleSelectedItem = (itemId: string) => {
    setSelectedItemIds((prev) => {
      const next = { ...prev };
      if (next[itemId]) {
        delete next[itemId];
      } else {
        next[itemId] = true;
      }
      return next;
    });
  };

  const clearSelectedItems = () => {
    setSelectedItemIds({});
  };

  const generatePlan = async (periodOverride?: string) => {
    if (!businessId || !selectedScopeOption) return;
    if (currentPlan?.items?.length && typeof window !== 'undefined') {
      const confirmed = window.confirm(isRu
        ? 'У вас уже есть контент-план. Создать новый план? Старый не удалится, но в списке появится ещё один план.'
        : 'You already have a content plan. Create a new one? The old plan will stay, but another plan will appear in the list.');
      if (!confirmed) {
        setActiveZone('queue');
        return;
      }
    }
    setGenerating(true);
    setError('');
    setActionSummary(null);
    try {
      const response = await newAuth.makeRequest('/content-plans/generate', {
        method: 'POST',
        body: JSON.stringify({
          business_id: businessId,
          scope_type: selectedScopeOption.scope_type,
          scope_target_id: selectedScopeOption.scope_target_id,
          period_days: Number(periodOverride || selectedPeriod),
          density: selectedDensity,
          content_mix: contentMix,
        }),
      });
      setCurrentPlan(response.plan || null);
      setActiveZone('queue');
      if (businessId) {
        const plansResponse = await newAuth.makeRequest(`/content-plans?business_id=${encodeURIComponent(businessId)}`, {
          method: 'GET',
        });
        setPlans(Array.isArray(plansResponse.plans) ? plansResponse.plans : []);
      }
      await loadLearningMetrics();
    } catch (generationError) {
      const message = generationError instanceof Error ? generationError.message : (isRu ? 'Не удалось собрать план' : 'Could not generate plan');
      setError(message);
    } finally {
      setGenerating(false);
    }
  };

  const saveItem = async (itemId: string) => {
    setBusyItemId(itemId);
    setActionSummary(null);
    try {
      await persistItemEdits(itemId);
    } finally {
      setBusyItemId('');
    }
  };

  const generateDraft = async (itemId: string) => {
    setBusyItemId(itemId);
    setError('');
    setActionSummary(null);
    try {
      const response = await newAuth.makeRequest(`/content-plans/items/${encodeURIComponent(itemId)}/generate-draft`, {
        method: 'POST',
        body: JSON.stringify({ language: contentLanguage }),
      });
      setCurrentPlan(response.plan || null);
      setDraftEdits((prev) => _removeRecordKeys(prev, [itemId]));
      setRecentGeneratedItemId(itemId);
      await loadLearningMetrics();
      setActionSummary({
        tone: 'success',
        text_ru: 'Черновик сгенерирован для выбранной публикации.',
        text_en: 'Draft generated for the selected item.',
      });
    } catch (draftError) {
      const message = draftError instanceof Error ? draftError.message : (isRu ? 'Не удалось сгенерировать черновик' : 'Could not generate draft');
      setError(message);
    } finally {
      setBusyItemId('');
    }
  };

  const createNews = async (itemId: string) => {
    setBusyItemId(itemId);
    setError('');
    setActionSummary(null);
    try {
      await persistItemEdits(itemId);
      const response = await newAuth.makeRequest(`/content-plans/items/${encodeURIComponent(itemId)}/create-news`, {
        method: 'POST',
        body: JSON.stringify({ language: contentLanguage }),
      });
      setCurrentPlan(response.plan || null);
      await loadLearningMetrics();
      setActionSummary({
        tone: 'success',
        text_ru: 'Новость создана из выбранного элемента плана.',
        text_en: 'News item created from the selected plan item.',
      });
    } catch (publishError) {
      const message = publishError instanceof Error ? publishError.message : (isRu ? 'Не удалось создать новость' : 'Could not create news');
      setError(message);
    } finally {
      setBusyItemId('');
    }
  };

  const prepareSocialPosts = async (itemId: string) => {
    setSocialBusyAction(`prepare:${itemId}`);
    setError('');
    setActionSummary(null);
    try {
      await persistItemEdits(itemId);
      const item = visibleItems.find((planItem) => planItem.id === itemId)
        || currentPlan?.items?.find((planItem) => planItem.id === itemId);
      if (!item) {
        throw new Error(isRu ? 'Тема плана не найдена' : 'Plan item not found');
      }
      await openSocialPreparePreview([item], 'selected', `single-social-prepare:${itemId}`);
    } catch (socialError) {
      const message = socialError instanceof Error ? socialError.message : (isRu ? 'Не удалось подготовить каналы' : 'Could not prepare channels');
      setError(message);
    } finally {
      setSocialBusyAction('');
    }
  };

  const openSocialApprovalPreview = (posts: SocialPost[], source: 'selected' | 'single', busyAction: string) => {
    const postIds = posts
      .map((post) => String(post.id || '').trim())
      .filter(Boolean);
    if (postIds.length === 0) return;
    setSocialPreparePreview(null);
    setSocialQueuePreview(null);
    setSocialApprovalPreview({
      key: `${source}:${postIds.join(':')}`,
      posts,
      postIds,
      busyAction,
      source,
    });
    setActionSummary({
      tone: 'neutral',
      text_ru: 'Предпросмотр подтверждения готов. Проверьте, что именно подтверждаете: это только проверка текста, без внешней публикации.',
      text_en: 'Approval preview is ready. Review exactly what you approve: this only confirms copy, without external publishing.',
    });
  };

  const approveSocialPostItem = (post: SocialPost) => {
    openSocialApprovalPreview([post], 'single', `approve:${post.id}`);
  };

  const executeSocialApprovalPreview = async () => {
    const preview = socialApprovalPreview;
    if (!preview || preview.postIds.length === 0) return;
    const summary = _socialApprovalSummary(preview.posts, socialApiPreflightByPlatform, socialChannelReadinessByPlatform, isRu);
    if (summary.emptyText > 0) {
      setActionSummary({
        tone: 'warning',
        text_ru: `Перед подтверждением заполните текст: ${summary.emptyText}. Пустой пост нельзя подтверждать к исполнению.`,
        text_en: `Add copy before approval: ${summary.emptyText}. Empty posts cannot be approved for execution.`,
      });
      return;
    }
    setBulkBusyAction(preview.busyAction);
    setError('');
    setActionSummary(null);
    try {
      await newAuth.makeRequest('/social-posts/bulk-approve', {
        method: 'POST',
        body: JSON.stringify({ post_ids: preview.postIds }),
      });
      if (currentPlan?.id) await loadSocialPosts(currentPlan.id);
      setSocialApprovalPreview(null);
      setActionSummary({
        tone: 'success',
        text_ru: preview.source === 'single'
          ? 'Пост подтверждён человеком. Внешняя публикация ещё не запускалась.'
          : 'Выбранные публикации подтверждены. Внешняя публикация ещё не запускалась.',
        text_en: preview.source === 'single'
          ? 'Post approved by a human. External publishing has not started yet.'
          : 'Selected posts approved. External publishing has not started yet.',
        details_ru: [
          'Следующий шаг - “Поставить в расписание”.',
          'API-каналы пойдут в исполнение только после постановки в расписание и даты публикации.',
          'Яндекс/2ГИС после постановки в расписание останутся контролируемым или ручным размещением.',
        ],
        details_en: [
          'Next step: “Queue on schedule”.',
          'API channels go to the worker only after queueing and the scheduled date.',
          'Yandex/2GIS stay supervised or manual after queueing.',
        ],
      });
    } catch (approveError) {
      const message = approveError instanceof Error ? approveError.message : (isRu ? 'Не удалось подтвердить публикацию' : 'Could not approve post');
      setError(message);
    } finally {
      setBulkBusyAction('');
    }
  };

  const saveSocialPostText = async (post: SocialPost, fallbackText: string) => {
    const nextText = String(socialTextEdits[post.id] ?? post.platform_text ?? fallbackText ?? '').trim();
    setSocialBusyAction(`save-text:${post.id}`);
    setError('');
    setActionSummary(null);
    try {
      await newAuth.makeRequest(`/social-posts/${encodeURIComponent(post.id)}`, {
        method: 'PATCH',
        body: JSON.stringify({
          platform_text: nextText,
          base_text: fallbackText,
        }),
      });
      if (currentPlan?.id) await loadSocialPosts(currentPlan.id);
      setActionSummary({
        tone: 'success',
        text_ru: 'Текст канала сохранён. Перед публикацией снова проверьте и подтвердите его.',
        text_en: 'Channel copy saved. Review and approve it again before publishing.',
      });
    } catch (saveError) {
      const message = saveError instanceof Error ? saveError.message : (isRu ? 'Не удалось сохранить текст канала' : 'Could not save channel copy');
      setError(message);
    } finally {
      setSocialBusyAction('');
    }
  };

  const openSocialQueuePreview = (posts: SocialPost[], source: 'selected' | 'visible' | 'single', busyAction: string) => {
    const postIds = posts
      .map((post) => String(post.id || '').trim())
      .filter(Boolean);
    if (postIds.length === 0) return;
    setSocialPreparePreview(null);
    setSocialApprovalPreview(null);
    setSocialQueuePreview({
      key: `${source}:${postIds.join(':')}`,
      posts,
      postIds,
      busyAction,
      source,
    });
    setActionSummary({
      tone: 'neutral',
      text_ru: 'Предпросмотр расписания готов. Проверьте, что именно разрешаете выполнить по дате.',
      text_en: 'Queue preview is ready. Review exactly what you allow the worker to execute on schedule.',
    });
  };

  const queueSocialPostItem = (post: SocialPost) => {
    openSocialQueuePreview([post], 'single', `queue:${post.id}`);
  };

  const executeSocialQueuePreview = async () => {
    const preview = socialQueuePreview;
    if (!preview || preview.postIds.length === 0) return;
    setBulkBusyAction(preview.busyAction);
    setError('');
    setActionSummary(null);
    try {
      await newAuth.makeRequest('/social-posts/bulk-queue', {
        method: 'POST',
        body: JSON.stringify({ post_ids: preview.postIds }),
      });
      if (currentPlan?.id) await loadSocialPosts(currentPlan.id);
      setSocialQueuePreview(null);
      setActionSummary(socialQueueResultSummary(preview.source === 'selected' || preview.source === 'single'));
    } catch (queueError) {
      const message = queueError instanceof Error ? queueError.message : (isRu ? 'Не удалось поставить публикацию в расписание' : 'Could not queue post');
      setError(message);
    } finally {
      setBulkBusyAction('');
    }
  };

  const markSocialPostPublished = async (post: SocialPost) => {
    setSocialBusyAction(`manual:${post.id}`);
    setError('');
    setActionSummary(null);
    const refs = manualPublishRefs[post.id] || { url: '', id: '' };
    try {
      await newAuth.makeRequest(`/social-posts/${encodeURIComponent(post.id)}/mark-manual-published`, {
        method: 'POST',
        body: JSON.stringify({
          provider_post_url: String(refs.url || '').trim(),
          provider_post_id: String(refs.id || '').trim(),
        }),
      });
      if (currentPlan?.id) await loadSocialPosts(currentPlan.id);
      setManualPublishRefs((prev) => {
        const next = { ...prev };
        delete next[post.id];
        return next;
      });
      setActionSummary({
        tone: 'success',
        text_ru: refs.url || refs.id
          ? 'Публикация отмечена как размещённая, ссылка/ID сохранены.'
          : 'Публикация отмечена как размещённая.',
        text_en: refs.url || refs.id
          ? 'Post marked as published and URL/ID saved.'
          : 'Post marked as published.',
      });
    } catch (manualError) {
      const message = manualError instanceof Error ? manualError.message : (isRu ? 'Не удалось отметить публикацию' : 'Could not mark post as published');
      setError(message);
    } finally {
      setSocialBusyAction('');
    }
  };

  const rehearseSocialPostPublish = async (post: SocialPost) => {
    setSocialBusyAction(`rehearsal:${post.id}`);
    setError('');
    setActionSummary(null);
    try {
      const response = await newAuth.makeRequest(`/social-posts/${encodeURIComponent(post.id)}/publish-rehearsal`, {
        method: 'POST',
      });
      const rehearsal = response.rehearsal && typeof response.rehearsal === 'object'
        ? response.rehearsal
        : {};
      setSocialPublishRehearsals((prev) => ({
        ...prev,
        [post.id]: rehearsal,
      }));
      const ready = Boolean(rehearsal.ready_for_execution);
      setActionSummary({
        tone: ready ? 'success' : 'warning',
        text_ru: String(rehearsal.summary_ru || (ready ? 'Проверка запуска пройдена.' : 'Проверка нашла блокер перед запуском.')),
        text_en: String(rehearsal.summary_en || (ready ? 'Launch check passed.' : 'The launch check found a blocker.')),
      });
    } catch (rehearsalError) {
      const message = rehearsalError instanceof Error ? rehearsalError.message : (isRu ? 'Не удалось проверить запуск публикации' : 'Could not check publish readiness');
      setError(message);
    } finally {
      setSocialBusyAction('');
    }
  };

  const rehearseSelectedSocialPosts = async () => {
    const postIds = selectedSocialPosts
      .map((post) => String(post.id || '').trim())
      .filter(Boolean);
    if (postIds.length === 0) return;
    setBulkBusyAction('selected-social-rehearsal');
    setError('');
    setActionSummary(null);
    try {
      const response = await newAuth.makeRequest('/social-posts/bulk-publish-rehearsal', {
        method: 'POST',
        body: JSON.stringify({ post_ids: postIds }),
      });
      const rehearsals = Array.isArray(response.rehearsals) ? response.rehearsals : [];
      const summary = response.summary && typeof response.summary === 'object' ? response.summary : {};
      const failed = Array.isArray(response.failed) ? response.failed : [];
      const bulkPayload: SocialPublishRehearsalBulk = {
        schema: String(response.schema || 'localos_social_publish_rehearsal_bulk_v1'),
        dry_run: Boolean(response.dry_run),
        external_publish_performed: Boolean(response.external_publish_performed),
        provider_write_performed: Boolean(response.provider_write_performed),
        rehearsals,
        failed,
        summary,
      };
      setSocialBulkPublishRehearsal(bulkPayload);
      setSocialPublishRehearsals((prev) => {
        const next = { ...prev };
        for (const rehearsal of rehearsals) {
          const postId = String(rehearsal.post_id || '').trim();
          if (postId) next[postId] = rehearsal;
        }
        return next;
      });
      const ready = Number(summary.ready || 0);
      const blocked = Number(summary.manual_or_blocked || 0);
      setActionSummary({
        tone: blocked > 0 ? 'warning' : 'success',
        text_ru: String(summary.message_ru || `Проверка выбранных завершена: готово ${ready}, требуют внимания ${blocked}.`),
        text_en: String(summary.message_en || `Selected launch check finished: ready ${ready}, need attention ${blocked}.`),
      });
    } catch (rehearsalError) {
      const message = rehearsalError instanceof Error ? rehearsalError.message : (isRu ? 'Не удалось проверить выбранные посты' : 'Could not check selected posts');
      setError(message);
    } finally {
      setBulkBusyAction('');
    }
  };

  const markSupervisedPostBlocked = async (post: SocialPost) => {
    setSocialBusyAction(`blocked:${post.id}`);
    setError('');
    setActionSummary(null);
    const reason = isRu
      ? 'Контролируемое размещение заблокировано: нужен ручной режим (логин, капча или изменённый интерфейс площадки).'
      : 'Supervised placement is blocked: manual fallback is needed (login, captcha, or changed platform UI).';
    try {
      await newAuth.makeRequest(`/social-posts/${encodeURIComponent(post.id)}/mark-supervised-blocked`, {
        method: 'POST',
        body: JSON.stringify({
          reason,
          blocked_source: 'localos_ui',
        }),
      });
      if (currentPlan?.id) await loadSocialPosts(currentPlan.id);
      setActionSummary({
        tone: 'warning',
        text_ru: 'Пост переведён в ручной режим. Текст и ссылка на площадку остались доступны, план не сорван.',
        text_en: 'Post moved to manual fallback. Copy and platform link remain available, and the plan is not blocked.',
      });
    } catch (blockedError) {
      const message = blockedError instanceof Error ? blockedError.message : (isRu ? 'Не удалось перевести пост в ручной режим' : 'Could not move post to manual fallback');
      setError(message);
    } finally {
      setSocialBusyAction('');
    }
  };

  const createSupervisedPostTask = async (post: SocialPost) => {
    if (typeof window !== 'undefined') {
      const confirmed = window.confirm(
        isRu
          ? 'Подготовить контролируемое размещение для Яндекс/2ГИС? LocalOS соберёт текст, ссылку на площадку и инструкцию. Финальную кнопку публикации он не нажимает.'
          : 'Prepare supervised placement for Yandex/2GIS? LocalOS will prepare copy, the platform link, and instructions. It will not click the final publish button.'
      );
      if (!confirmed) return;
    }
    setSocialBusyAction(`supervised-task:${post.id}`);
    setError('');
    setActionSummary(null);
    try {
      const response = await newAuth.makeRequest(`/social-posts/${encodeURIComponent(post.id)}/supervised-task`, {
        method: 'POST',
        body: JSON.stringify({ approved: true }),
      });
      if (currentPlan?.id) await loadSocialPosts(currentPlan.id);
      const updatedPost = response.post && typeof response.post === 'object' ? response.post : {};
      const status = String(updatedPost.status || '').trim();
      setActionSummary({
        tone: status === 'needs_manual_publish' ? 'warning' : 'success',
        text_ru: status === 'needs_manual_publish'
          ? 'Контролируемое размещение подготовлено как ручной режим: браузерное размещение OpenClaw сейчас недоступно или не подтверждено.'
          : 'Контролируемое размещение подготовлено. Проверьте инструкцию, откройте площадку и завершите размещение только после проверки предпросмотра.',
        text_en: status === 'needs_manual_publish'
          ? 'Supervised placement was prepared as manual fallback: OpenClaw browser-use is unavailable or not confirmed.'
          : 'Supervised placement prepared. Review the instructions, open the platform, and finish placement only after preview review.',
      });
    } catch (taskError) {
      const message = taskError instanceof Error ? taskError.message : (isRu ? 'Не удалось подготовить контролируемое размещение' : 'Could not prepare supervised placement');
      setError(message);
    } finally {
      setSocialBusyAction('');
    }
  };

  const checkOpenClawBrowserReadiness = async () => {
    if (!businessId) return;
    setSocialBusyAction('openclaw-check');
    setError('');
    setActionSummary(null);
    try {
      const response = await newAuth.makeRequest(`/business/${encodeURIComponent(businessId)}/social-posts/openclaw-browser-check`, {
        method: 'GET',
      });
      const readiness = response.openclaw_browser_readiness && typeof response.openclaw_browser_readiness === 'object'
        ? response.openclaw_browser_readiness
        : null;
      setSocialOpenClawReadiness(readiness);
      setActionSummary({
        tone: readiness?.ready ? 'success' : 'warning',
        text_ru: readiness?.ready
          ? 'Браузерное размещение OpenClaw подтверждено. Яндекс/2ГИС можно вести через контролируемое размещение без финального клика.'
          : 'Браузерное размещение OpenClaw не подтверждено. Яндекс/2ГИС останутся в ручном режиме, план не будет сорван.',
        text_en: readiness?.ready
          ? 'OpenClaw browser-use is confirmed. Yandex/2GIS can use supervised placement without the final click.'
          : 'OpenClaw browser-use is not confirmed. Yandex/2GIS will stay in manual fallback, and the plan will not be blocked.',
        details_ru: _socialOpenClawReadinessDetails(readiness, true),
        details_en: _socialOpenClawReadinessDetails(readiness, false),
      });
    } catch (checkError) {
      const message = checkError instanceof Error ? checkError.message : (isRu ? 'Не удалось проверить браузерное размещение OpenClaw' : 'Could not check OpenClaw browser-use');
      setError(message);
    } finally {
      setSocialBusyAction('');
    }
  };

  const checkApiChannelPreflight = async () => {
    if (!businessId) return;
    setSocialBusyAction('api-channel-preflight');
    setError('');
    setActionSummary(null);
    try {
      const response = await newAuth.makeRequest(`/business/${encodeURIComponent(businessId)}/social-posts/api-channel-preflight`, {
        method: 'GET',
      });
      const preflight = Array.isArray(response.api_preflight) ? response.api_preflight : [];
      setSocialApiPreflight(preflight);
      const readyCount = Number(response.summary?.ready || 0);
      const attentionCount = Number(response.summary?.needs_attention || 0);
      setActionSummary({
        tone: attentionCount > 0 ? 'warning' : 'success',
        text_ru: attentionCount > 0
          ? `API-каналы проверены без публикации: готовы ${readyCount}, требуют внимания ${attentionCount}. Исправьте ключи/права до расписания.`
          : `API-каналы проверены без публикации: готовы ${readyCount}. Публикация всё равно начнётся только после подтверждения и расписания.`,
        text_en: attentionCount > 0
          ? `API channels checked without publishing: ready ${readyCount}, need attention ${attentionCount}. Fix keys/permissions before scheduling.`
          : `API channels checked without publishing: ready ${readyCount}. Publishing still starts only after approval and queueing.`,
      });
    } catch (preflightError) {
      const message = preflightError instanceof Error ? preflightError.message : (isRu ? 'Не удалось проверить API-каналы' : 'Could not check API channels');
      setError(message);
    } finally {
      setSocialBusyAction('');
    }
  };

  const copySocialPostText = async (post: SocialPost, text: string) => {
    const value = String(text || post.platform_text || post.base_text || '').trim();
    if (!value) return;
    setError('');
    try {
      await copyTextToClipboard(value);
      setActionSummary({
        tone: 'success',
        text_ru: 'Текст скопирован. Теперь откройте площадку и вставьте его в форму публикации.',
        text_en: 'Post text copied. Open the platform and paste it into the publication form.',
      });
    } catch {
      setError(isRu ? 'Не удалось скопировать текст' : 'Could not copy text');
    }
  };

  const copySocialWorkerEnv = async () => {
    const dispatchEnv = socialLaunchPreflight?.recommended_env?.dispatch || {};
    const metricsEnv = socialLaunchPreflight?.recommended_env?.metrics || {};
    const lines = _socialWorkerEnvLines(dispatchEnv, metricsEnv);
    if (!lines.length) return;
    const runbookLines = _socialLaunchRunbookClipboardLines(socialLaunchPreflight?.launch_runbook, isRu);
    setError('');
    try {
      await copyTextToClipboard([...lines, ...runbookLines].join('\n'));
      setActionSummary({
        tone: 'success',
        text_ru: 'Настройки и чеклист первого цикла скопированы. Включайте запуск только для выбранного бизнеса и проверьте логи после одного цикла.',
        text_en: 'Scoped dispatch env and first-cycle runbook copied. Enable the worker only for the selected business and check logs after one cycle.',
      });
    } catch {
      setError(isRu ? 'Не удалось скопировать настройки запуска' : 'Could not copy worker env');
    }
  };

  const recordSocialPostAttribution = async (post: SocialPost, eventType: SocialAttributionEventType) => {
    setSocialBusyAction(`attribute:${eventType}:${post.id}`);
    setError('');
    setActionSummary(null);
    try {
      const response = await newAuth.makeRequest(`/social-posts/${encodeURIComponent(post.id)}/attribution-events`, {
        method: 'POST',
        body: JSON.stringify({
          event_type: eventType,
          value: 1,
          event_source: 'manual_content_plan',
          metadata: {
            platform: post.platform,
            content_plan_item_id: post.content_plan_item_id,
          },
        }),
      });
      const nextPost = response?.post && typeof response.post === 'object' ? response.post : null;
      if (nextPost) {
        const itemId = String(nextPost.content_plan_item_id || post.content_plan_item_id || '').trim();
        setSocialPostsByItem((prev) => {
          const currentPosts = prev[itemId] || [];
          const nextPosts = currentPosts.map((existing) => (
            existing.id === post.id ? { ...existing, ...nextPost } : existing
          ));
          return {
            ...prev,
            [itemId]: nextPosts.length ? nextPosts : [{ ...post, ...nextPost }],
          };
        });
      } else if (currentPlan?.id) {
        await loadSocialPosts(currentPlan.id);
      }
      let recommendationPayload: SocialRecommendationPayload | null = null;
      let recommendationError = '';
      if (currentPlan?.id) {
        try {
          recommendationPayload = await fetchSocialPlanRecommendation(currentPlan.id);
        } catch (recommendErrorCaught) {
          recommendationError = recommendErrorCaught instanceof Error
            ? recommendErrorCaught.message
            : (isRu ? 'Не удалось пересчитать рекомендации' : 'Could not recalculate recommendations');
          setSocialRecommendation(null);
          setSocialRecommendationApproved(false);
        }
      } else {
        setSocialRecommendation(null);
        setSocialRecommendationApproved(false);
      }
      const feedback = _socialAttributionFeedback(eventType);
      const metrics = response?.metrics && typeof response.metrics === 'object' ? response.metrics : {};
      const leads = Number(metrics.leads || nextPost?.leads || post.leads || 0);
      const inquiries = Number(metrics.inquiries || nextPost?.inquiries || post.inquiries || 0);
      const comments = Number(metrics.comments || nextPost?.comments || post.comments || 0);
      const reach = Number(metrics.reach || metrics.views || nextPost?.reach || nextPost?.views || post.reach || post.views || 0);
      const proposedCount = Number(recommendationPayload?.proposed_changes?.length || 0);
      const readiness = recommendationPayload?.learning_readiness;
      const readinessSummaryRu = String(readiness?.summary_ru || '').trim();
      const readinessSummaryEn = String(readiness?.summary_en || '').trim();
      setActionSummary({
        tone: recommendationError ? 'warning' : 'success',
        text_ru: feedback.ru,
        text_en: feedback.en,
        details_ru: [
          `Итого по посту: заявки ${leads}, обращения ${inquiries}, комментарии ${comments}, охват ${reach}.`,
          recommendationError
            ? `Рекомендации сброшены: результат сохранён, но новый предпросмотр не пересчитался: ${recommendationError}`
            : proposedCount > 0
              ? `LocalOS сразу подготовил предложения к следующему плану: ${proposedCount}. Они не применены автоматически.`
              : 'LocalOS пересчитал рекомендации, но пока не нашёл изменений для применения.',
          readinessSummaryRu || 'Главная метрика - заявки и обращения; изменения требуют отдельного подтверждения.',
        ],
        details_en: [
          `Post totals: leads ${leads}, inquiries ${inquiries}, comments ${comments}, reach ${reach}.`,
          recommendationError
            ? `The result was saved, but recommendations were not recalculated: ${recommendationError}`
            : proposedCount > 0
              ? `LocalOS immediately prepared next-plan proposals: ${proposedCount}. They were not applied automatically.`
              : 'LocalOS recalculated recommendations, but found no changes to apply yet.',
          readinessSummaryEn || 'The main metric is leads and inquiries; changes require separate approval.',
        ],
      });
    } catch (attributeError) {
      const message = attributeError instanceof Error ? attributeError.message : (isRu ? 'Не удалось отметить результат публикации' : 'Could not record post result');
      setError(message);
    } finally {
      setSocialBusyAction('');
    }
  };

  const openSocialPreparePreview = async (
    itemsToPrepare: PlanItem[],
    source: 'selected' | 'suggested',
    busyAction: string,
  ) => {
    const firstItem = itemsToPrepare[0];
    if (!firstItem) return false;
    setBulkBusyAction(busyAction);
    setError('');
    setActionSummary(null);
    setSocialApprovalPreview(null);
    setSocialQueuePreview(null);
    try {
    const response = await newAuth.makeRequest(`/content-plans/items/${encodeURIComponent(firstItem.id)}/social-posts/prepare-preview`, {
      method: 'POST',
      body: JSON.stringify({}),
    });
    const item = response.item && typeof response.item === 'object' ? response.item : {};
    const fallbackTitle = isRu ? 'выбранная тема' : 'selected topic';
    const title = String(item.theme || firstItem.theme || firstItem.goal || fallbackTitle).trim();
      setSocialPreparePreview({
        key: `${source}:${firstItem.id}:${Date.now()}`,
        items: itemsToPrepare,
        itemIds: itemsToPrepare.map((prepareItem) => prepareItem.id),
        busyAction,
        source,
        previewItemTitle: title,
        preview: {
          read_only: Boolean(response.read_only),
          database_write_performed: Boolean(response.database_write_performed),
          external_publish_performed: Boolean(response.external_publish_performed),
          summary: response.summary && typeof response.summary === 'object' ? response.summary : {},
          posts: Array.isArray(response.posts) ? response.posts : [],
          next_action_ru: String(response.next_action_ru || ''),
          next_action_en: String(response.next_action_en || ''),
        },
      });
      setActionSummary({
        tone: 'neutral',
        text_ru: 'Предпросмотр подготовки каналов готов. Проверьте сводку и подтвердите создание черновиков отдельной кнопкой.',
        text_en: 'Channel preparation preview is ready. Review the summary and confirm draft creation with a separate button.',
      });
      return false;
    } catch (previewError) {
      const message = previewError instanceof Error ? previewError.message : (isRu ? 'Не удалось открыть предпросмотр подготовки каналов' : 'Could not open channel preparation preview');
      setError(message);
      return false;
    } finally {
      setBulkBusyAction('');
    }
  };

  const prepareSelectedSocialPosts = async () => {
    if (!selectedItems.length) return;
    await openSocialPreparePreview(selectedItems, 'selected', 'selected-social-prepare');
  };

  const prepareSuggestedSocialPosts = async () => {
    const itemsToPrepare = selectedItems.length > 0 ? selectedItems : visibleItems.slice(0, 5);
    if (itemsToPrepare.length === 0) return;
    await openSocialPreparePreview(itemsToPrepare, selectedItems.length > 0 ? 'selected' : 'suggested', 'suggested-social-prepare');
  };

  const executeSocialPreparePreview = async () => {
    const preview = socialPreparePreview;
    if (!preview || preview.itemIds.length === 0) return;
    setBulkBusyAction(preview.busyAction);
    setError('');
    setActionSummary(null);
    try {
      await newAuth.makeRequest('/content-plans/social-posts/bulk-prepare', {
        method: 'POST',
        body: JSON.stringify({ item_ids: preview.itemIds }),
      });
      if (currentPlan?.id) await loadSocialPosts(currentPlan.id);
      setSelectedItemIds(preview.items.reduce<Record<string, boolean>>((acc, item) => {
        acc[item.id] = true;
        return acc;
      }, {}));
      setSocialPreparePreview(null);
      setActionSummary({
        tone: 'success',
        text_ru: preview.source === 'selected'
          ? 'Каналы подготовлены для выбранных тем. Следующий шаг - проверить тексты.'
          : 'Каналы подготовлены. Следующий безопасный шаг - открыть предпросмотр и проверить тексты.',
        text_en: preview.source === 'selected'
          ? 'Channels prepared for selected items. Next step: review copy.'
          : 'Channels prepared. Next safe step: open preview and review copy.',
        details_ru: [
          preview.source === 'selected'
            ? 'Выбранные темы остались отмечены. В панели ниже откройте предпросмотр, сохраните правки и нажмите “Подтвердить посты”.'
            : 'LocalOS отметил подготовленные темы, чтобы массовое подтверждение было видно сразу.',
          'Наружу ничего не отправлено: подтверждение и постановка в расписание идут отдельными шагами.',
        ],
        details_en: [
          preview.source === 'selected'
            ? 'Selected topics stayed checked. In the panel below, open preview, save edits, and click “Approve posts”.'
            : 'LocalOS selected the prepared topics so bulk approval is visible immediately.',
          'Nothing was sent externally: approval and queueing stay separate steps.',
        ],
      });
    } catch (bulkError) {
      const message = bulkError instanceof Error ? bulkError.message : (isRu ? 'Не удалось подготовить каналы' : 'Could not prepare channels');
      setError(message);
    } finally {
      setBulkBusyAction('');
    }
  };

  const approveSelectedSocialPosts = async () => {
    if (!selectedSocialNeedsReview.length) return;
    if (selectedSocialDirtyReviewPosts.length > 0) {
      setActionSummary({
        tone: 'warning',
        text_ru: `Сначала сохраните правки текста: ${selectedSocialDirtyReviewPosts.length}. Массовое подтверждение не подтвердит несохранённый предпросмотр.`,
        text_en: `Save copy edits first: ${selectedSocialDirtyReviewPosts.length}. Bulk approval will not approve unsaved preview text.`,
      });
      return;
    }
    openSocialApprovalPreview(selectedSocialNeedsReview, 'selected', 'selected-social-approve');
  };

  const queueVisibleApprovedSocialPosts = async () => {
    if (!visibleSocialCanQueue.length) return;
    openSocialQueuePreview(visibleSocialCanQueue, 'visible', 'visible-social-queue');
  };

  const queueSelectedSocialPosts = async () => {
    if (!selectedSocialCanQueue.length) return;
    openSocialQueuePreview(selectedSocialCanQueue, 'selected', 'selected-social-queue');
  };

  const selectPublishedSocialPostsForResult = () => {
    const itemIds = visibleSocialPublishedPosts
      .map((post) => String(post.content_plan_item_id || '').trim())
      .filter(Boolean);
    const uniqueItemIds = Array.from(new Set(itemIds));
    if (!uniqueItemIds.length) return;
    setSelectedItemIds(uniqueItemIds.reduce<Record<string, boolean>>((acc, itemId) => {
      acc[itemId] = true;
      return acc;
    }, {}));
    setSelectedQueueItemId(uniqueItemIds[0]);
    setEditorItemId(uniqueItemIds[0]);
    setActiveZone('queue');
    setActionSummary({
      tone: 'neutral',
      text_ru: `Выбраны опубликованные темы: ${uniqueItemIds.length}. Теперь можно отметить заявки, обращения или ранние реакции.`,
      text_en: `Published topics selected: ${uniqueItemIds.length}. You can now record leads, inquiries, or early reactions.`,
      details_ru: [
        'Это не публикует ничего наружу и не меняет план автоматически.',
        'После отметки результата LocalOS пересчитает предложения следующего плана.',
      ],
      details_en: [
        'This does not publish externally and does not change the plan automatically.',
        'After result marking, LocalOS recalculates next-plan proposals.',
      ],
    });
  };

  const markSelectedSocialPostsPublished = async () => {
    if (!selectedSocialCanMarkPublished.length) return;
    setBulkBusyAction('selected-social-manual');
    setError('');
    setActionSummary(null);
    try {
      await newAuth.makeRequest('/social-posts/bulk-mark-manual-published', {
        method: 'POST',
        body: JSON.stringify({ post_ids: selectedSocialCanMarkPublished.map((post) => post.id) }),
      });
      if (currentPlan?.id) await loadSocialPosts(currentPlan.id);
      setActionSummary({
        tone: 'success',
        text_ru: 'Выбранные ручные/контролируемые публикации отмечены как размещённые.',
        text_en: 'Selected manual/supervised posts marked as published.',
      });
    } catch (bulkError) {
      const message = bulkError instanceof Error ? bulkError.message : (isRu ? 'Не удалось отметить выбранные публикации' : 'Could not mark selected posts');
      setError(message);
    } finally {
      setBulkBusyAction('');
    }
  };

  const recordSelectedSocialPostAttribution = async (eventType: SocialAttributionEventType) => {
    if (!selectedSocialCanRecordResults.length) return;
    setBulkBusyAction(`selected-social-attribute-${eventType}`);
    setError('');
    setActionSummary(null);
    try {
      await newAuth.makeRequest('/social-posts/bulk-attribution-events', {
        method: 'POST',
        body: JSON.stringify({
          post_ids: selectedSocialCanRecordResults.map((post) => post.id),
          event_type: eventType,
          value: 1,
          event_source: 'manual_content_plan_bulk',
          metadata: {
            selected_bulk: true,
          },
        }),
      });
      if (currentPlan?.id) {
        await loadSocialPosts(currentPlan.id);
        try {
          await fetchSocialPlanRecommendation(currentPlan.id);
        } catch (recommendError) {
          setActionSummary({
            tone: 'warning',
            text_ru: 'Результаты сохранены, но рекомендации следующего плана не пересчитались.',
            text_en: 'Results were saved, but next-plan recommendations were not recalculated.',
            details_ru: [recommendError instanceof Error ? recommendError.message : 'Повторите пересчёт рекомендаций позже.'],
            details_en: [recommendError instanceof Error ? recommendError.message : 'Run recommendation refresh again later.'],
          });
          return;
        }
      }
      const feedback = _socialAttributionFeedback(eventType);
      const isPrimaryResult = eventType === 'lead' || eventType === 'inquiry';
      setActionSummary({
        tone: 'success',
        text_ru: isPrimaryResult
          ? `${feedback.ru} Массово отмечено: ${selectedSocialCanRecordResults.length}. LocalOS пересчитал рекомендации, но не применил изменения автоматически.`
          : `${feedback.ru} Массово отмечено: ${selectedSocialCanRecordResults.length}. LocalOS пересчитал рекомендации, но заявки и обращения остаются главным KPI.`,
        text_en: isPrimaryResult
          ? `${feedback.en} Bulk recorded: ${selectedSocialCanRecordResults.length}. LocalOS recalculated recommendations but did not apply changes automatically.`
          : `${feedback.en} Bulk recorded: ${selectedSocialCanRecordResults.length}. LocalOS recalculated recommendations, while leads and inquiries remain the main KPI.`,
        details_ru: ['Главная метрика - заявки и обращения; комментарии, репосты, клики, охваты и лайки остаются ранними сигналами.'],
        details_en: ['The main metric is leads and inquiries; comments, shares, clicks, reach, and likes remain early signals.'],
      });
    } catch (bulkError) {
      const message = bulkError instanceof Error ? bulkError.message : (isRu ? 'Не удалось отметить результат выбранных публикаций' : 'Could not record selected post results');
      setError(message);
    } finally {
      setBulkBusyAction('');
    }
  };

  const fetchSocialPlanRecommendation = async (planId: string) => {
    const response = await newAuth.makeRequest(`/content-plans/${encodeURIComponent(planId)}/social-posts/recommend-next-plan`, {
      method: 'POST',
      body: JSON.stringify({}),
    });
    const payload: SocialRecommendationPayload = {
      recommendation: response.recommendation || {},
      learning_readiness: response.learning_readiness || undefined,
      application_preview: response.application_preview && typeof response.application_preview === 'object'
        ? response.application_preview
        : undefined,
      proposed_changes: Array.isArray(response.proposed_changes) ? response.proposed_changes : [],
    };
    setSocialRecommendation(payload);
    setSocialRecommendationApproved(false);
    return payload;
  };

  const collectSocialPostMetricsForBusiness = async () => {
    if (!businessId || !currentPlan?.id) return;
    if (typeof window !== 'undefined') {
      const confirmed = window.confirm(
        isRu
          ? 'Собрать реакции один раз для опубликованных постов текущего бизнеса? Это не публикует новые посты и только обновляет метрики/заявки для рекомендаций.'
          : 'Collect reactions once for published posts in the current business? This will not publish new posts and only updates metrics/leads for recommendations.'
      );
      if (!confirmed) return;
    }
    setSocialBusyAction('collect-metrics');
    setError('');
    setActionSummary(null);
    try {
      const response = await newAuth.makeRequest('/social-posts/metrics/run-once', {
        method: 'POST',
        body: JSON.stringify({ business_id: businessId, batch_size: 25, approved: true }),
      });
      if (currentPlan?.id) await loadSocialPosts(currentPlan.id);
      const result = response.metrics_result && typeof response.metrics_result === 'object'
        ? response.metrics_result
        : {};
      setSocialMetricsLearningPacket(
        response.metrics_learning_packet && typeof response.metrics_learning_packet === 'object'
          ? response.metrics_learning_packet
          : null
      );
      const collected = Number(result.collected || 0);
      const picked = Number(result.picked || 0);
      const failed = Number(result.failed || 0);
      const resultSummariesRu = Array.isArray(result.result_summaries_ru)
        ? result.result_summaries_ru.map(String).filter(Boolean)
        : [];
      const resultSummariesEn = Array.isArray(result.result_summaries_en)
        ? result.result_summaries_en.map(String).filter(Boolean)
        : [];
      let recommendationPayload: SocialRecommendationPayload | null = null;
      let recommendationError = '';
      try {
        recommendationPayload = await fetchSocialPlanRecommendation(currentPlan.id);
      } catch (recommendErrorCaught) {
        recommendationError = recommendErrorCaught instanceof Error
          ? recommendErrorCaught.message
          : (isRu ? 'Не удалось пересчитать рекомендации' : 'Could not recalculate recommendations');
        setSocialRecommendation(null);
        setSocialRecommendationApproved(false);
      }
      const proposedCount = Number(recommendationPayload?.proposed_changes?.length || 0);
      const readiness = recommendationPayload?.learning_readiness;
      const readinessSummaryRu = String(readiness?.summary_ru || '').trim();
      const readinessSummaryEn = String(readiness?.summary_en || '').trim();
      setActionSummary({
        tone: failed > 0 || recommendationError ? 'warning' : 'success',
        text_ru: String(response.message_ru || `Сбор реакций выполнен: проверено ${picked}, обновлено ${collected}, ошибок ${failed}.`),
        text_en: String(response.message_en || `Metrics collection finished: checked ${picked}, updated ${collected}, failed ${failed}.`),
        details_ru: [
          ...resultSummariesRu,
          recommendationError
            ? `Рекомендации сброшены: реакции сохранены, но новый предпросмотр не пересчитался: ${recommendationError}`
            : proposedCount > 0
              ? `LocalOS сразу подготовил предложения к следующему плану: ${proposedCount}. Они не применены автоматически.`
              : 'LocalOS пересчитал рекомендации, но пока не нашёл изменений для применения.',
          readinessSummaryRu || 'Главная метрика - заявки и обращения; изменения требуют отдельного подтверждения.',
        ].slice(0, 7),
        details_en: [
          ...resultSummariesEn,
          recommendationError
            ? `Recommendations were reset: reactions were saved, but the new preview was not recalculated: ${recommendationError}`
            : proposedCount > 0
              ? `LocalOS immediately prepared next-plan proposals: ${proposedCount}. They were not applied automatically.`
              : 'LocalOS recalculated recommendations, but found no changes to apply yet.',
          readinessSummaryEn || 'The main metric is leads and inquiries; changes require separate approval.',
        ].slice(0, 7),
      });
    } catch (collectError) {
      const message = collectError instanceof Error ? collectError.message : (isRu ? 'Не удалось обновить реакции' : 'Could not update reactions');
      setError(message);
    } finally {
      setSocialBusyAction('');
    }
  };

  const previewSocialDispatch = async (scrollToPreview = false) => {
    setSocialBusyAction('dispatch-preview');
    setError('');
    setActionSummary(null);
    try {
      const response = await newAuth.makeRequest('/social-posts/dispatch/preview', {
        method: 'POST',
        body: JSON.stringify({ batch_size: 10, business_id: businessId }),
      });
      const preview: SocialDispatchPreview = {
        dry_run: Boolean(response.dry_run),
        picked: Number(response.picked || 0),
        skipped_no_access: Number(response.skipped_no_access || 0),
        batch_size: Number(response.batch_size || 10),
        business_scope: String(response.business_scope || ''),
        by_action: response.by_action && typeof response.by_action === 'object' ? response.by_action : {},
        readiness: response.readiness && typeof response.readiness === 'object' ? response.readiness : {},
        items: Array.isArray(response.items) ? response.items : [],
      };
      setSocialDispatchPreview(preview);
      const apiCount = Number(preview.readiness?.external_publish_count ?? preview.by_action?.publish_api ?? 0);
      const supervisedCount = Number(preview.readiness?.controlled_count ?? preview.by_action?.create_supervised_task ?? 0);
      const manualCount = Number(preview.readiness?.manual_count ?? preview.by_action?.manual_handoff ?? 0);
      const dryRunMessageRu = String(preview.readiness?.message_ru || '');
      const dryRunMessageEn = String(preview.readiness?.message_en || '');
      setActionSummary({
        tone: manualCount > 0 || Number(preview.skipped_no_access || 0) > 0 ? 'warning' : 'success',
        text_ru: `Проверка расписания по текущему бизнесу: пора публиковать ${preview.picked || 0}, API ${apiCount}, контролируемое размещение ${supervisedCount}, вручную ${manualCount}. Наружу ничего не отправлено.`,
        text_en: `Schedule dry-run for the current business: due posts ${preview.picked || 0}, API ${apiCount}, supervised ${supervisedCount}, manual ${manualCount}. Nothing was sent externally.`,
        details_ru: dryRunMessageRu ? [dryRunMessageRu] : [],
        details_en: dryRunMessageEn ? [dryRunMessageEn] : [],
      });
      if (scrollToPreview && typeof window !== 'undefined') {
        window.setTimeout(() => {
          document
            .querySelector('[data-testid="social-dispatch-preview-panel"]')
            ?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }, 50);
      }
    } catch (previewError) {
      const message = previewError instanceof Error ? previewError.message : (isRu ? 'Не удалось проверить расписание' : 'Could not preview schedule');
      setError(message);
    } finally {
      setSocialBusyAction('');
    }
  };

  const checkSocialLaunchPreflight = async () => {
    if (!businessId) return;
    setSocialBusyAction('launch-preflight');
    setError('');
    setActionSummary(null);
    try {
      const response = await newAuth.makeRequest(`/business/${encodeURIComponent(businessId)}/social-posts/launch-preflight`, {
        method: 'GET',
      });
      const dispatchPreview = response.dispatch_preview && typeof response.dispatch_preview === 'object'
        ? {
          dry_run: Boolean(response.dispatch_preview.dry_run),
          picked: Number(response.dispatch_preview.picked || 0),
          skipped_no_access: Number(response.dispatch_preview.skipped_no_access || 0),
          batch_size: Number(response.dispatch_preview.batch_size || 10),
          business_scope: String(response.dispatch_preview.business_scope || ''),
          by_action: response.dispatch_preview.by_action && typeof response.dispatch_preview.by_action === 'object' ? response.dispatch_preview.by_action : {},
          readiness: response.dispatch_preview.readiness && typeof response.dispatch_preview.readiness === 'object' ? response.dispatch_preview.readiness : {},
          items: Array.isArray(response.dispatch_preview.items) ? response.dispatch_preview.items : [],
        }
        : null;
      const preflight: SocialLaunchPreflight = {
        business_id: String(response.business_id || businessId),
        status: String(response.status || ''),
        safe_to_enable_scoped_dispatch: Boolean(response.safe_to_enable_scoped_dispatch),
        production_readiness: response.production_readiness && typeof response.production_readiness === 'object'
          ? response.production_readiness
          : undefined,
        launch_gate: response.launch_gate && typeof response.launch_gate === 'object'
          ? response.launch_gate
          : undefined,
        first_api_proof_gate: response.first_api_proof_gate && typeof response.first_api_proof_gate === 'object'
          ? response.first_api_proof_gate
          : undefined,
        first_cycle_proof_packet: response.first_cycle_proof_packet && typeof response.first_cycle_proof_packet === 'object'
          ? response.first_cycle_proof_packet
          : undefined,
        proof_requirements: response.proof_requirements && typeof response.proof_requirements === 'object'
          ? response.proof_requirements
          : undefined,
        workflow_stage_counts: response.workflow_stage_counts && typeof response.workflow_stage_counts === 'object'
          ? response.workflow_stage_counts
          : undefined,
        worker_idle_reason: response.worker_idle_reason && typeof response.worker_idle_reason === 'object'
          ? response.worker_idle_reason
          : undefined,
        live_validation_checklist: Array.isArray(response.live_validation_checklist)
          ? response.live_validation_checklist
          : [],
        channel_summary: response.channel_summary && typeof response.channel_summary === 'object' ? response.channel_summary : {},
        dispatch_preview: dispatchPreview || undefined,
        dispatch_readiness: response.dispatch_readiness && typeof response.dispatch_readiness === 'object' ? response.dispatch_readiness : {},
        api_preflight: Array.isArray(response.api_preflight) ? response.api_preflight : [],
        api_preflight_summary: response.api_preflight_summary && typeof response.api_preflight_summary === 'object' ? response.api_preflight_summary : {},
        launch_rehearsal: response.launch_rehearsal && typeof response.launch_rehearsal === 'object'
          ? {
            schema: String(response.launch_rehearsal.schema || 'localos_social_publish_rehearsal_bulk_v1'),
            dry_run: Boolean(response.launch_rehearsal.dry_run),
            external_publish_performed: Boolean(response.launch_rehearsal.external_publish_performed),
            provider_write_performed: Boolean(response.launch_rehearsal.provider_write_performed),
            rehearsals: Array.isArray(response.launch_rehearsal.rehearsals) ? response.launch_rehearsal.rehearsals : [],
            failed: Array.isArray(response.launch_rehearsal.failed) ? response.launch_rehearsal.failed : [],
            summary: response.launch_rehearsal.summary && typeof response.launch_rehearsal.summary === 'object' ? response.launch_rehearsal.summary : {},
          }
          : undefined,
        api_preflight_blocked_due_posts: Array.isArray(response.api_preflight_blocked_due_posts) ? response.api_preflight_blocked_due_posts : [],
        first_api_publish_readiness: response.first_api_publish_readiness && typeof response.first_api_publish_readiness === 'object'
          ? response.first_api_publish_readiness
          : undefined,
        recommended_env: response.recommended_env && typeof response.recommended_env === 'object' ? response.recommended_env : {},
        safety: response.safety && typeof response.safety === 'object' ? response.safety : {},
        summary: response.summary && typeof response.summary === 'object' ? response.summary : {},
        message_ru: String(response.message_ru || ''),
        message_en: String(response.message_en || ''),
        next_action_ru: String(response.next_action_ru || ''),
        next_action_en: String(response.next_action_en || ''),
        launch_runbook: response.launch_runbook && typeof response.launch_runbook === 'object' ? response.launch_runbook : undefined,
        runtime_alignment: response.runtime_alignment && typeof response.runtime_alignment === 'object' ? response.runtime_alignment : undefined,
      };
      setSocialLaunchPreflight(preflight);
      if (dispatchPreview) {
        setSocialDispatchPreview(dispatchPreview);
      }
      setActionSummary({
        tone: preflight.production_readiness?.ready_for_first_scoped_cycle || preflight.safe_to_enable_scoped_dispatch ? 'success' : 'warning',
        text_ru: preflight.production_readiness?.summary_ru || preflight.message_ru || 'Проверка запуска по расписанию готова.',
        text_en: preflight.production_readiness?.summary_en || preflight.message_en || 'Worker launch preflight is ready.',
        details_ru: [
          `Пора публиковать: ${Number(preflight.summary?.due_posts || 0)} · API: ${Number(preflight.summary?.api_due_posts || 0)} · контролируемо: ${Number(preflight.summary?.controlled_due_posts || 0)} · вручную: ${Number(preflight.summary?.manual_due_posts || 0)}.`,
          preflight.worker_idle_reason?.next_action_ru || '',
          preflight.production_readiness?.next_action_ru || '',
          preflight.next_action_ru || 'Следующий шаг появится в блоке запуска.',
        ].filter(Boolean),
        details_en: [
          `Due: ${Number(preflight.summary?.due_posts || 0)} · API: ${Number(preflight.summary?.api_due_posts || 0)} · supervised: ${Number(preflight.summary?.controlled_due_posts || 0)} · manual: ${Number(preflight.summary?.manual_due_posts || 0)}.`,
          preflight.worker_idle_reason?.next_action_en || '',
          preflight.production_readiness?.next_action_en || '',
          preflight.next_action_en || 'The next step is shown in the launch block.',
        ].filter(Boolean),
      });
    } catch (preflightError) {
      const message = preflightError instanceof Error ? preflightError.message : (isRu ? 'Не удалось проверить запуск по расписанию' : 'Could not check worker launch');
      setError(message);
    } finally {
      setSocialBusyAction('');
    }
  };

  const runSocialDispatchOnce = async () => {
    if (!businessId) return;
    const apiDuePosts = Number(
      socialLaunchPreflight?.summary?.api_due_posts
      ?? socialLaunchPreflight?.launch_gate?.api_posts
      ?? socialDispatchPreview?.readiness?.external_publish_count
      ?? 0
    );
    const externalPublishPhrase = String(
      socialLaunchPreflight?.launch_gate?.external_publish_confirmation_phrase
      || 'ПУБЛИКУЮ'
    );
    let approvalText = '';
    if (typeof window !== 'undefined') {
      if (apiDuePosts > 0) {
        const typed = window.prompt(
          isRu
            ? `Этот запуск может опубликовать API-посты: ${apiDuePosts}. Чтобы подтвердить внешний publish, введите: ${externalPublishPhrase}`
            : `This run may publish API posts: ${apiDuePosts}. To confirm external publishing, type: ${externalPublishPhrase}`,
          ''
        );
        if (typed === null) return;
        approvalText = typed;
      } else {
        const confirmed = window.confirm(
          isRu
            ? 'Запустить один scoped цикл для текущего бизнеса? Яндекс/2ГИС перейдут в контролируемое или ручное размещение без финального клика.'
            : 'Run one scoped cycle for the current business? Yandex/2GIS will move to supervised placement without the final click.'
        );
        if (!confirmed) return;
      }
    }
    setSocialBusyAction('dispatch-run-once');
    setError('');
    setActionSummary(null);
    try {
      const response = await newAuth.makeRequest('/social-posts/dispatch/run-once', {
        method: 'POST',
        body: JSON.stringify({
          business_id: businessId,
          batch_size: 10,
          approved: true,
          approval_text: approvalText,
        }),
      });
      const result = response.dispatch_result && typeof response.dispatch_result === 'object'
        ? response.dispatch_result
        : {};
      const executionReport: SocialDispatchExecutionReport | null = response.execution_report && typeof response.execution_report === 'object'
        ? response.execution_report
        : null;
      const followupRu = Array.isArray(result.followup_actions_ru)
        ? result.followup_actions_ru.map(String).filter(Boolean)
        : [];
      const followupEn = Array.isArray(result.followup_actions_en)
        ? result.followup_actions_en.map(String).filter(Boolean)
        : [];
      const resultSummariesRu = Array.isArray(result.result_summaries_ru)
        ? result.result_summaries_ru.map(String).filter(Boolean)
        : [];
      const resultSummariesEn = Array.isArray(result.result_summaries_en)
        ? result.result_summaries_en.map(String).filter(Boolean)
        : [];
      setActionSummary({
        tone: Number(result.failed || 0) > 0 || Number(result.manual || 0) > 0 ? 'warning' : 'success',
        text_ru: String(response.message_ru || `Первый scoped цикл выполнен: взято ${Number(result.picked || 0)}, опубликовано ${Number(result.published || 0)}, контролируемое размещение ${Number(result.supervised || 0)}, вручную ${Number(result.manual || 0)}, ошибок ${Number(result.failed || 0)}.`),
        text_en: String(response.message_en || `First scoped cycle finished: picked ${Number(result.picked || 0)}, published ${Number(result.published || 0)}, supervised ${Number(result.supervised || 0)}, manual ${Number(result.manual || 0)}, failed ${Number(result.failed || 0)}.`),
        details_ru: [
          ...resultSummariesRu,
          ...(followupRu.length ? followupRu : [
            'Проверьте карточки постов: API должны показать ссылку/ID или понятную ошибку, карты - контролируемое или ручное размещение.',
          ]),
        ].slice(0, 7),
        details_en: [
          ...resultSummariesEn,
          ...(followupEn.length ? followupEn : [
            'Check post cards: API posts should show a URL/ID or a clear error, maps should show supervised placement or manual handoff.',
          ]),
        ].slice(0, 7),
      });
      if (currentPlan?.id) {
        await loadSocialPosts(currentPlan.id);
      }
      await loadSocialRuntimeStatus();
      setSocialDispatchExecutionReport(executionReport);
      setSocialDispatchPreview(null);
      setSocialLaunchPreflight(null);
    } catch (dispatchError) {
      const message = dispatchError instanceof Error ? dispatchError.message : (isRu ? 'Не удалось запустить scoped цикл' : 'Could not run scoped cycle');
      setError(message);
      try {
        await checkSocialLaunchPreflight();
      } catch {
        // The visible recovery summary below is enough if refresh also fails.
      }
      setActionSummary({
        tone: 'warning',
        text_ru: 'Первый цикл не запущен: LocalOS остановил внешнее исполнение.',
        text_en: 'The first cycle did not run: LocalOS stopped external execution.',
        details_ru: [
          message,
          apiDuePosts > 0
            ? `Если это API-публикация, повторите запуск только после dry-run и введите фразу подтверждения: ${externalPublishPhrase}.`
            : 'Повторите безопасную проверку запуска: она ничего не публикует и покажет текущий блокер.',
          'Яндекс/2ГИС всё равно остаются контролируемым или ручным размещением без финального автоклика.',
        ],
        details_en: [
          message,
          apiDuePosts > 0
            ? `If this is API publishing, rerun only after the dry-run and type the confirmation phrase: ${externalPublishPhrase}.`
            : 'Run the safe launch check again: it publishes nothing and shows the current blocker.',
          'Yandex/2GIS still stay supervised or manual without the final auto-click.',
        ],
      });
    } finally {
      setSocialBusyAction('');
    }
  };

  const recommendNextSocialPlan = async () => {
    if (!currentPlan?.id) return;
    setSocialBusyAction('recommend');
    setError('');
    setActionSummary(null);
    try {
      const recommendationPayload = await fetchSocialPlanRecommendation(currentPlan.id);
      const proposedCount = Number(recommendationPayload.proposed_changes?.length || 0);
      setActionSummary({
        tone: 'success',
        text_ru: proposedCount > 0
          ? `LocalOS подготовил предложения для корректировки плана: ${proposedCount}. Они не применены автоматически.`
          : 'LocalOS пересчитал рекомендации, но пока не нашёл изменений для применения.',
        text_en: proposedCount > 0
          ? `LocalOS prepared plan adjustment proposals: ${proposedCount}. They were not applied automatically.`
          : 'LocalOS recalculated recommendations, but found no changes to apply yet.',
      });
    } catch (recommendError) {
      const message = recommendError instanceof Error ? recommendError.message : (isRu ? 'Не удалось подготовить рекомендации' : 'Could not prepare recommendations');
      setError(message);
    } finally {
      setSocialBusyAction('');
    }
  };

  const applySocialPlanRecommendation = async () => {
    if (!currentPlan?.id) return;
    setSocialBusyAction('apply-recommendation');
    setError('');
    setActionSummary(null);
    try {
      const response = await newAuth.makeRequest(`/content-plans/${encodeURIComponent(currentPlan.id)}/social-posts/apply-recommendation`, {
        method: 'POST',
        body: JSON.stringify({ approved: true }),
      });
      await loadPlans();
      if (currentPlan?.id) {
        const planResponse = await newAuth.makeRequest(`/content-plans/${encodeURIComponent(currentPlan.id)}`, {
          method: 'GET',
        });
        setCurrentPlan(planResponse.plan || currentPlan);
        await loadSocialPosts(currentPlan.id);
      }
      const approvalRecord = response.approval_record && typeof response.approval_record === 'object'
        ? response.approval_record
        : {};
      const approvedAt = String(approvalRecord.approved_at || '').trim();
      setActionSummary({
        tone: 'success',
        text_ru: `Корректировка применена после подтверждения: ${Number(response.applied_count || 0)} пунктов плана. Изменялись только будущие неопубликованные пункты${approvedAt ? ` · ${approvedAt}` : ''}.`,
        text_en: `Recommendation applied after approval: ${Number(response.applied_count || 0)} plan items. Only future unpublished items were changed${approvedAt ? ` · ${approvedAt}` : ''}.`,
      });
      setSocialRecommendationApproved(false);
    } catch (applyError) {
      const message = applyError instanceof Error ? applyError.message : (isRu ? 'Не удалось применить рекомендации' : 'Could not apply recommendations');
      setError(message);
    } finally {
      setSocialBusyAction('');
    }
  };

  const persistItemEdits = async (itemId: string) => {
    setError('');
    const payload: Record<string, string> = {};
    if (themeEdits[itemId] !== undefined) payload.theme = themeEdits[itemId];
    if (dateEdits[itemId] !== undefined) payload.scheduled_for = dateEdits[itemId];
    if (draftEdits[itemId] !== undefined) payload.draft_text = draftEdits[itemId];
    if (Object.keys(payload).length === 0) {
      return currentPlan;
    }
    const response = await newAuth.makeRequest(`/content-plans/items/${encodeURIComponent(itemId)}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
    const nextPlan = response.plan || null;
    setCurrentPlan(nextPlan);
    return nextPlan;
  };

  const deleteItem = async (itemId: string) => {
    if (!itemId) return;
    const confirmed = typeof window === 'undefined' ? true : window.confirm(isRu
      ? 'Удалить эту тему из выбранного плана?'
      : 'Delete this topic from the selected plan?');
    if (!confirmed) return;
    setBusyItemId(itemId);
    setError('');
    setActionSummary(null);
    try {
      const response = await newAuth.makeRequest(`/content-plans/items/${encodeURIComponent(itemId)}`, {
        method: 'DELETE',
      });
      setCurrentPlan(response.plan || null);
      setEditorItemId('');
      setSelectedQueueItemId('');
      setDraftEdits((prev) => _removeRecordKeys(prev, [itemId]));
      setThemeEdits((prev) => _removeRecordKeys(prev, [itemId]));
      setDateEdits((prev) => _removeRecordKeys(prev, [itemId]));
      clearSelectedItems();
      await loadPlans();
      setActionSummary({
        tone: 'success',
        text_ru: 'Тема удалена из плана.',
        text_en: 'Topic deleted from the plan.',
      });
    } catch (deleteError) {
      const message = deleteError instanceof Error ? deleteError.message : (isRu ? 'Не удалось удалить тему' : 'Could not delete topic');
      setError(message);
    } finally {
      setBusyItemId('');
    }
  };

  const runBulkGenerateDrafts = async () => {
    if (bulkDraftCandidates.length === 0) return;
    setBulkBusyAction('drafts');
    setError('');
    setActionSummary(null);
    try {
      let nextPlan = currentPlan;
      let generatedCount = 0;
      let failedCount = 0;
      const failedThemes: string[] = [];
      const generatedIds: string[] = [];
      for (const item of bulkDraftCandidates) {
        try {
          const response = await newAuth.makeRequest(`/content-plans/items/${encodeURIComponent(item.id)}/generate-draft`, {
            method: 'POST',
            body: JSON.stringify({ language: contentLanguage }),
          });
          nextPlan = response.plan || null;
          setCurrentPlan(nextPlan);
          generatedCount += 1;
          generatedIds.push(item.id);
        } catch {
          failedCount += 1;
          failedThemes.push(String(item.theme || item.goal || item.id || '').trim());
        }
      }
      if (generatedIds.length > 0) {
        setDraftEdits((prev) => _removeRecordKeys(prev, generatedIds));
      }
      await loadLearningMetrics();
      setActionSummary({
        tone: failedCount > 0 ? 'warning' : 'success',
        text_ru: _bulkResultText('drafts', generatedCount, failedCount, true),
        text_en: _bulkResultText('drafts', generatedCount, failedCount, false),
        details_ru: _bulkResultDetails(failedThemes, true),
        details_en: _bulkResultDetails(failedThemes, false),
      });
    } catch (draftError) {
      const message = draftError instanceof Error ? draftError.message : (isRu ? 'Не удалось сгенерировать черновики' : 'Could not generate drafts');
      setError(message);
    } finally {
      setBulkBusyAction('');
    }
  };

  const runSelectedGenerateDrafts = async () => {
    if (selectedDraftCandidates.length === 0) return;
    setBulkBusyAction('selected-drafts');
    setError('');
    setActionSummary(null);
    try {
      let generatedCount = 0;
      let failedCount = 0;
      const failedThemes: string[] = [];
      const generatedIds: string[] = [];
      for (const item of selectedDraftCandidates) {
        try {
          const response = await newAuth.makeRequest(`/content-plans/items/${encodeURIComponent(item.id)}/generate-draft`, {
            method: 'POST',
            body: JSON.stringify({ language: contentLanguage }),
          });
          setCurrentPlan(response.plan || null);
          generatedCount += 1;
          generatedIds.push(item.id);
        } catch {
          failedCount += 1;
          failedThemes.push(String(item.theme || item.goal || item.id || '').trim());
        }
      }
      if (generatedIds.length > 0) {
        setDraftEdits((prev) => _removeRecordKeys(prev, generatedIds));
      }
      await loadLearningMetrics();
      clearSelectedItems();
      setActionSummary({
        tone: failedCount > 0 ? 'warning' : 'success',
        text_ru: _bulkResultText('drafts', generatedCount, failedCount, true),
        text_en: _bulkResultText('drafts', generatedCount, failedCount, false),
        details_ru: _bulkResultDetails(failedThemes, true),
        details_en: _bulkResultDetails(failedThemes, false),
      });
    } catch (draftError) {
      const message = draftError instanceof Error ? draftError.message : (isRu ? 'Не удалось сгенерировать тексты' : 'Could not generate texts');
      setError(message);
    } finally {
      setBulkBusyAction('');
    }
  };

  const runSelectedCreateNews = () => {
    if (selectedNewsCandidates.length === 0) return;
    setBulkNewsReview({
      key: 'selected',
      titleRu: 'Создать выбранные новости',
      titleEn: 'Create selected news',
      descriptionRu: 'Будут созданы новости только из отмеченных тем. Проверьте выборку перед запуском.',
      descriptionEn: 'News will be created only from selected topics. Review the selection before continuing.',
      items: selectedNewsCandidates,
      busyAction: 'selected-news',
    });
  };

  const runBulkCreateNews = async () => {
    if (bulkNewsCandidates.length === 0) return;
    setBulkNewsReview({
      key: 'filtered',
      titleRu: 'Проверить новости перед созданием',
      titleEn: 'Review news before creating',
      descriptionRu: 'Будут созданы новости только из текущей выборки: с учётом точки, недели и фильтров сверху.',
      descriptionEn: 'News will be created only from the current view: respecting location, week, and filters above.',
      items: bulkNewsCandidates,
      busyAction: 'news',
    });
  };

  const runBulkAutofillDates = async () => {
    if (missingDateCandidates.length === 0) return;
    setBulkBusyAction('autofill-dates');
    setError('');
    setActionSummary(null);
    try {
      let nextPlan = currentPlan;
      let updatedCount = 0;
      let failedCount = 0;
      const failedThemes: string[] = [];
      for (let index = 0; index < missingDateCandidates.length; index += 1) {
        const item = missingDateCandidates[index];
        try {
          const nextDate = _autoScheduledDate(index);
          const response = await newAuth.makeRequest(`/content-plans/items/${encodeURIComponent(item.id)}`, {
            method: 'PUT',
            body: JSON.stringify({ scheduled_for: nextDate, status: 'planned' }),
          });
          nextPlan = response.plan || null;
          setCurrentPlan(nextPlan);
          setDateEdits((prev) => ({ ...prev, [item.id]: nextDate }));
          updatedCount += 1;
        } catch {
          failedCount += 1;
          failedThemes.push(String(item.theme || item.goal || item.id || '').trim());
        }
      }
      setActionSummary({
        tone: failedCount > 0 ? 'warning' : 'success',
        text_ru: `Даты расставлены автоматически: ${updatedCount}${failedCount > 0 ? `, не получилось ${failedCount}` : ''}`,
        text_en: `Dates assigned automatically: ${updatedCount}${failedCount > 0 ? `, failed ${failedCount}` : ''}`,
        details_ru: _bulkResultDetails(failedThemes, true),
        details_en: _bulkResultDetails(failedThemes, false),
      });
    } catch (dateError) {
      const message = dateError instanceof Error ? dateError.message : (isRu ? 'Не удалось расставить даты' : 'Could not assign dates');
      setError(message);
    } finally {
      setBulkBusyAction('');
    }
  };

  const executeBulkNewsReview = async () => {
    const review = bulkNewsReview;
    if (!review || review.items.length === 0) return;
    if (review.focusLocationKey && review.focusWeekKey) {
      applyLocationWeekFocus(review.focusLocationKey, review.focusWeekKey);
    }
    setBulkBusyAction(review.busyAction);
    setError('');
    setActionSummary(null);
    try {
      let nextPlan = currentPlan;
      let createdCount = 0;
      let failedCount = 0;
      const failedThemes: string[] = [];
      for (const item of review.items) {
        try {
          await persistItemEdits(item.id);
          const response = await newAuth.makeRequest(`/content-plans/items/${encodeURIComponent(item.id)}/create-news`, {
            method: 'POST',
            body: JSON.stringify({ language: contentLanguage }),
          });
          nextPlan = response.plan || null;
          setCurrentPlan(nextPlan);
          createdCount += 1;
        } catch {
          failedCount += 1;
          failedThemes.push(String(item.theme || item.goal || item.id || '').trim());
        }
      }
      await loadLearningMetrics();
      const textRu = _bulkResultText('news', createdCount, failedCount, true);
      const textEn = _bulkResultText('news', createdCount, failedCount, false);
      setActionSummary({
        tone: failedCount > 0 ? 'warning' : 'success',
        text_ru: review.summaryPrefixRu ? `${review.summaryPrefixRu}: ${textRu}` : textRu,
        text_en: review.summaryPrefixEn ? `${review.summaryPrefixEn}: ${textEn}` : textEn,
        details_ru: _bulkResultDetails(failedThemes, true),
        details_en: _bulkResultDetails(failedThemes, false),
        focusLocationKey: review.focusLocationKey,
        focusWeekKey: review.focusWeekKey,
      });
      setBulkNewsReview(null);
    } catch (publishError) {
      const message = publishError instanceof Error ? publishError.message : (isRu ? 'Не удалось создать новости' : 'Could not create news items');
      setError(message);
    } finally {
      setBulkBusyAction('');
    }
  };

  const executeBulkActionReview = async () => {
    const review = bulkActionReview;
    if (!review || review.items.length === 0) return;
    if (review.focusLocationKey && review.focusWeekKey) {
      applyLocationWeekFocus(review.focusLocationKey, review.focusWeekKey);
    }
    setBulkBusyAction(review.busyAction);
    setError('');
    setActionSummary(null);
    try {
      let nextPlan = currentPlan;
      let processedCount = 0;
      let failedCount = 0;
      const failedThemes: string[] = [];
      for (const item of review.items) {
        try {
          const payload: Record<string, string> = {};
          if (review.kind === 'skip') {
            payload.status = 'skipped';
          } else {
            payload.scheduled_for = String(review.targetDate || '').slice(0, 10);
            payload.status = 'planned';
          }
          const response = await newAuth.makeRequest(`/content-plans/items/${encodeURIComponent(item.id)}`, {
            method: 'PUT',
            body: JSON.stringify(payload),
          });
          nextPlan = response.plan || null;
          setCurrentPlan(nextPlan);
          if (review.kind === 'reschedule') {
            setDateEdits((prev) => ({ ...prev, [item.id]: String(review.targetDate || '').slice(0, 10) }));
          }
          processedCount += 1;
        } catch {
          failedCount += 1;
          failedThemes.push(String(item.theme || item.goal || item.id || '').trim());
        }
      }
      await loadLearningMetrics();
      const actionTextRu = review.kind === 'skip'
        ? `пропущено тем ${processedCount}${failedCount > 0 ? `, не получилось ${failedCount}` : ''}`
        : `перенесено на ${String(review.targetDate || '').slice(0, 10)} тем ${processedCount}${failedCount > 0 ? `, не получилось ${failedCount}` : ''}`;
      const actionTextEn = review.kind === 'skip'
        ? `skipped ${processedCount}${failedCount > 0 ? `, failed ${failedCount}` : ''}`
        : `moved to ${String(review.targetDate || '').slice(0, 10)}: ${processedCount}${failedCount > 0 ? `, failed ${failedCount}` : ''}`;
      setActionSummary({
        tone: failedCount > 0 ? 'warning' : 'success',
        text_ru: review.summaryPrefixRu ? `${review.summaryPrefixRu}: ${actionTextRu}` : actionTextRu,
        text_en: review.summaryPrefixEn ? `${review.summaryPrefixEn}: ${actionTextEn}` : actionTextEn,
        details_ru: _bulkResultDetails(failedThemes, true),
        details_en: _bulkResultDetails(failedThemes, false),
        focusLocationKey: review.focusLocationKey,
        focusWeekKey: review.kind === 'reschedule' && review.targetDate ? _weekBucketKey(review.targetDate) : review.focusWeekKey,
      });
      setBulkActionReview(null);
    } catch (bulkError) {
      const message = bulkError instanceof Error ? bulkError.message : (isRu ? 'Не удалось выполнить массовое действие' : 'Could not run bulk action');
      setError(message);
    } finally {
      setBulkBusyAction('');
    }
  };

  const resetViewState = () => {
    setSelectedViewPreset('overview');
    setSelectedItemFilter('all');
    setSelectedSignalFilter('all');
    setSelectedPlanTargetKey('all');
    setSelectedItemLocationKey('all');
    setSelectedWeekKey('all');
    setDateFromFilter('');
    setDateToFilter('');
    setSortMode('date');
  };

  const applyViewPreset = (preset: ViewPresetKey) => {
    if (preset === 'overview') {
      resetViewState();
      return;
    }
    setSelectedViewPreset(preset);
    setSelectedSignalFilter('all');
    setSelectedItemLocationKey('all');
    setSelectedWeekKey('all');
    setDateFromFilter('');
    setDateToFilter('');
    if (preset === 'urgent') {
      setSelectedItemFilter('urgent');
      setSortMode('date');
      return;
    }
    if (preset === 'ready') {
      setSelectedItemFilter('has_draft');
      setSortMode('date');
      return;
    }
    if (preset === 'focus') {
      setSelectedItemFilter('urgent');
      setSortMode('date');
      if (lastFocusLocationKey !== 'all') {
        setSelectedItemLocationKey(lastFocusLocationKey);
      }
      if (lastFocusWeekKey !== 'all') {
        setSelectedWeekKey(lastFocusWeekKey);
      }
      return;
    }
    setSelectedItemFilter('all');
    setSortMode('date');
  };

  const applyLocationWeekFocus = (locationKey: string, weekKey: string) => {
    setSelectedViewPreset('focus');
    setLastFocusLocationKey(locationKey);
    setLastFocusWeekKey(weekKey);
    setSelectedItemFilter('urgent');
    setSelectedSignalFilter('all');
    setSelectedItemLocationKey(locationKey);
    setSelectedWeekKey(weekKey);
    setSortMode('date');
  };

  const getLocationWeekFocusItems = (locationKey: string, weekKey: string) => (
    (currentPlan?.items || []).filter((item) => {
      const itemLocationKey = String(item.location_scope || item.business_id || '').trim();
      return itemLocationKey === locationKey && _weekBucketKey(item.scheduled_for) === weekKey;
    })
  );

  const getDuplicateTargetLocationOptions = (item: PlanItem) => {
    const sourceLocationKey = String(item.location_scope || item.business_id || '').trim();
    return availableItemLocations.filter((location) => location.key !== 'all' && location.key !== sourceLocationKey);
  };

  const openDuplicateTargetPicker = (item: PlanItem) => {
    const targetOptions = getDuplicateTargetLocationOptions(item);
    setExpandedDuplicateItemId((prev) => (prev === item.id ? '' : item.id));
    setDuplicateDateOverrides((prev) => ({
      ...prev,
      [item.id]: prev[item.id] || _inputDateValue(item.scheduled_for) || _shiftIsoDate('', 7),
    }));
    setDuplicateTargetSelections((prev) => ({
      ...prev,
      [item.id]: prev[item.id]?.length ? prev[item.id] : targetOptions.map((location) => location.key),
    }));
  };

  const toggleDuplicateTargetLocation = (itemId: string, locationKey: string) => {
    setDuplicateTargetSelections((prev) => {
      const current = Array.isArray(prev[itemId]) ? prev[itemId] : [];
      const exists = current.includes(locationKey);
      return {
        ...prev,
        [itemId]: exists
          ? current.filter((key) => key !== locationKey)
          : [...current, locationKey],
      };
    });
  };

  const runLocationWeekFocusDrafts = async (locationKey: string, weekKey: string) => {
    const focusCandidates = getLocationWeekFocusItems(locationKey, weekKey)
      .filter((item) => !String(item.draft_text || '').trim() && !String(item.usernews_id || '').trim());
    if (focusCandidates.length === 0) return;
    applyLocationWeekFocus(locationKey, weekKey);
    setBulkBusyAction(`focus-drafts:${locationKey}:${weekKey}`);
    setError('');
    setActionSummary(null);
    try {
      let nextPlan = currentPlan;
      let generatedCount = 0;
      let failedCount = 0;
      const failedThemes: string[] = [];
      const generatedIds: string[] = [];
      for (const item of focusCandidates) {
        try {
          const response = await newAuth.makeRequest(`/content-plans/items/${encodeURIComponent(item.id)}/generate-draft`, {
            method: 'POST',
            body: JSON.stringify({ language: contentLanguage }),
          });
          nextPlan = response.plan || null;
          setCurrentPlan(nextPlan);
          generatedCount += 1;
          generatedIds.push(item.id);
        } catch {
          failedCount += 1;
          failedThemes.push(String(item.theme || item.goal || item.id || '').trim());
        }
      }
      if (generatedIds.length > 0) {
        setDraftEdits((prev) => _removeRecordKeys(prev, generatedIds));
      }
      await loadLearningMetrics();
      const locationLabel = _locationLabelByKey(currentPlan?.items || [], locationKey, isRu);
      const weekLabel = _weekBucketLabel(weekKey, isRu);
      setActionSummary({
        tone: failedCount > 0 ? 'warning' : 'success',
        text_ru: `${locationLabel} · ${weekLabel}: ${_bulkResultText('drafts', generatedCount, failedCount, true)}`,
        text_en: `${locationLabel} · ${weekLabel}: ${_bulkResultText('drafts', generatedCount, failedCount, false)}`,
        details_ru: _bulkResultDetails(failedThemes, true),
        details_en: _bulkResultDetails(failedThemes, false),
        focusLocationKey: locationKey,
        focusWeekKey: weekKey,
      });
    } catch (draftError) {
      const message = draftError instanceof Error ? draftError.message : (isRu ? 'Не удалось сгенерировать черновики' : 'Could not generate drafts');
      setError(message);
    } finally {
      setBulkBusyAction('');
    }
  };

  const runLocationWeekFocusNews = async (locationKey: string, weekKey: string) => {
    const focusCandidates = getLocationWeekFocusItems(locationKey, weekKey)
      .filter((item) => String(item.draft_text || '').trim() && !String(item.usernews_id || '').trim());
    if (focusCandidates.length === 0) return;
    applyLocationWeekFocus(locationKey, weekKey);
    const locationLabel = _locationLabelByKey(currentPlan?.items || [], locationKey, isRu);
    const weekLabel = _weekBucketLabel(weekKey, isRu);
    setBulkNewsReview({
      key: `focus:${locationKey}:${weekKey}`,
      titleRu: 'Проверить новости по срезу',
      titleEn: 'Review slice news',
      descriptionRu: `${locationLabel} · ${weekLabel}. Будут созданы новости только из готовых черновиков этого среза.`,
      descriptionEn: `${locationLabel} · ${weekLabel}. News will be created only from ready drafts in this slice.`,
      items: focusCandidates,
      busyAction: `focus-news:${locationKey}:${weekKey}`,
      summaryPrefixRu: `${locationLabel} · ${weekLabel}`,
      summaryPrefixEn: `${locationLabel} · ${weekLabel}`,
      focusLocationKey: locationKey,
      focusWeekKey: weekKey,
    });
  };

  const runLocationWeekSkip = async (locationKey: string, weekKey: string) => {
    const focusCandidates = getLocationWeekFocusItems(locationKey, weekKey)
      .filter((item) => String(item.status || '').trim() !== 'skipped' && !String(item.usernews_id || '').trim());
    if (focusCandidates.length === 0) return;
    applyLocationWeekFocus(locationKey, weekKey);
    setError('');
    setActionSummary(null);
    const locationLabel = _locationLabelByKey(currentPlan?.items || [], locationKey, isRu);
    const weekLabel = _weekBucketLabel(weekKey, isRu);
    setBulkActionReview({
      key: `skip:${locationKey}:${weekKey}`,
      kind: 'skip',
      titleRu: 'Проверить пропуск пачки',
      titleEn: 'Review batch skip',
      descriptionRu: `${locationLabel} · ${weekLabel}. Эти темы будут помечены как пропущенные и уйдут из рабочего среза.`,
      descriptionEn: `${locationLabel} · ${weekLabel}. These items will be marked as skipped and removed from the active slice.`,
      confirmLabelRu: 'Подтвердить пропуск',
      confirmLabelEn: 'Confirm skip',
      items: focusCandidates,
      busyAction: `focus-skip:${locationKey}:${weekKey}`,
      summaryPrefixRu: `${locationLabel} · ${weekLabel}`,
      summaryPrefixEn: `${locationLabel} · ${weekLabel}`,
      focusLocationKey: locationKey,
      focusWeekKey: weekKey,
    });
  };

  const runLocationWeekReschedule = async (locationKey: string, weekKey: string, daysDelta: number) => {
    const focusCandidates = getLocationWeekFocusItems(locationKey, weekKey)
      .filter((item) => String(item.status || '').trim() !== 'skipped' && !String(item.usernews_id || '').trim());
    if (focusCandidates.length === 0) return;
    applyLocationWeekFocus(locationKey, weekKey);
    setBulkBusyAction(`focus-reschedule:${locationKey}:${weekKey}`);
    setError('');
    setActionSummary(null);
    try {
      let movedCount = 0;
      let failedCount = 0;
      const failedThemes: string[] = [];
      for (const item of focusCandidates) {
        try {
          const nextDate = _shiftIsoDate(item.scheduled_for, daysDelta);
          const response = await newAuth.makeRequest(`/content-plans/items/${encodeURIComponent(item.id)}`, {
            method: 'PUT',
            body: JSON.stringify({ scheduled_for: nextDate, status: 'planned' }),
          });
          setCurrentPlan(response.plan || null);
          movedCount += 1;
        } catch {
          failedCount += 1;
          failedThemes.push(String(item.theme || item.goal || item.id || '').trim());
        }
      }
      await loadLearningMetrics();
      const locationLabel = _locationLabelByKey(currentPlan?.items || [], locationKey, isRu);
      const weekLabel = _weekBucketLabel(weekKey, isRu);
      setActionSummary({
        tone: failedCount > 0 ? 'warning' : 'success',
        text_ru: `${locationLabel} · ${weekLabel}: перенесено тем ${movedCount}${failedCount > 0 ? `, не получилось ${failedCount}` : ''}`,
        text_en: `${locationLabel} · ${weekLabel}: rescheduled ${movedCount}${failedCount > 0 ? `, failed ${failedCount}` : ''}`,
        details_ru: _bulkResultDetails(failedThemes, true),
        details_en: _bulkResultDetails(failedThemes, false),
        focusLocationKey: locationKey,
        focusWeekKey: _weekBucketKey(_shiftIsoDate(weekKey, daysDelta)),
      });
    } catch (rescheduleError) {
      const message = rescheduleError instanceof Error ? rescheduleError.message : (isRu ? 'Не удалось перенести срез' : 'Could not reschedule slice');
      setError(message);
    } finally {
      setBulkBusyAction('');
    }
  };

  const runLocationWeekRescheduleToDate = async (locationKey: string, weekKey: string, targetDate: string) => {
    const normalizedTargetDate = String(targetDate || '').slice(0, 10);
    if (!normalizedTargetDate) {
      setError(isRu ? 'Выберите дату переноса' : 'Select a target date');
      return;
    }
    const focusCandidates = getLocationWeekFocusItems(locationKey, weekKey)
      .filter((item) => String(item.status || '').trim() !== 'skipped' && !String(item.usernews_id || '').trim());
    if (focusCandidates.length === 0) return;
    applyLocationWeekFocus(locationKey, weekKey);
    setError('');
    setActionSummary(null);
    const locationLabel = _locationLabelByKey(currentPlan?.items || [], locationKey, isRu);
    const weekLabel = _weekBucketLabel(weekKey, isRu);
    setBulkActionReview({
      key: `reschedule:${locationKey}:${weekKey}:${normalizedTargetDate}`,
      kind: 'reschedule',
      titleRu: 'Проверить перенос пачки',
      titleEn: 'Review batch move',
      descriptionRu: `${locationLabel} · ${weekLabel}. Все элементы среза будут перенесены на ${normalizedTargetDate}.`,
      descriptionEn: `${locationLabel} · ${weekLabel}. All slice items will be moved to ${normalizedTargetDate}.`,
      confirmLabelRu: 'Подтвердить перенос',
      confirmLabelEn: 'Confirm move',
      items: focusCandidates,
      busyAction: `focus-reschedule-date:${locationKey}:${weekKey}`,
      targetDate: normalizedTargetDate,
      summaryPrefixRu: `${locationLabel} · ${weekLabel}`,
      summaryPrefixEn: `${locationLabel} · ${weekLabel}`,
      focusLocationKey: locationKey,
      focusWeekKey: weekKey,
    });
  };

  const runItemSkip = async (itemId: string) => {
    setBusyItemId(itemId);
    setError('');
    setActionSummary(null);
    try {
      const response = await newAuth.makeRequest(`/content-plans/items/${encodeURIComponent(itemId)}`, {
        method: 'PUT',
        body: JSON.stringify({ status: 'skipped' }),
      });
      setCurrentPlan(response.plan || null);
      await loadLearningMetrics();
      setActionSummary({
        tone: 'success',
        text_ru: 'Элемент помечен как пропущенный.',
        text_en: 'The item was marked as skipped.',
      });
    } catch (skipError) {
      const message = skipError instanceof Error ? skipError.message : (isRu ? 'Не удалось пропустить элемент' : 'Could not skip item');
      setError(message);
    } finally {
      setBusyItemId('');
    }
  };

  const runItemReschedule = async (itemId: string, scheduledFor: string, daysDelta: number) => {
    setBusyItemId(itemId);
    setError('');
    setActionSummary(null);
    try {
      const nextDate = _shiftIsoDate(scheduledFor, daysDelta);
      const response = await newAuth.makeRequest(`/content-plans/items/${encodeURIComponent(itemId)}`, {
        method: 'PUT',
        body: JSON.stringify({ scheduled_for: nextDate, status: 'planned' }),
      });
      setCurrentPlan(response.plan || null);
      await loadLearningMetrics();
      setDateEdits((prev) => ({ ...prev, [itemId]: nextDate }));
      setActionSummary({
        tone: 'success',
        text_ru: `Элемент перенесён на ${nextDate}.`,
        text_en: `The item was rescheduled to ${nextDate}.`,
      });
    } catch (rescheduleError) {
      const message = rescheduleError instanceof Error ? rescheduleError.message : (isRu ? 'Не удалось перенести элемент' : 'Could not reschedule item');
      setError(message);
    } finally {
      setBusyItemId('');
    }
  };

  const runItemDuplicate = async (itemId: string) => {
    setBusyItemId(itemId);
    setError('');
    setActionSummary(null);
    try {
      const response = await newAuth.makeRequest(`/content-plans/items/${encodeURIComponent(itemId)}/duplicate`, {
        method: 'POST',
      });
      setCurrentPlan(response.plan || null);
      await loadLearningMetrics();
      setActionSummary({
        tone: 'success',
        text_ru: 'Элемент продублирован и добавлен в план.',
        text_en: 'The item was duplicated and added to the plan.',
      });
    } catch (duplicateError) {
      const message = duplicateError instanceof Error ? duplicateError.message : (isRu ? 'Не удалось дублировать элемент' : 'Could not duplicate item');
      setError(message);
    } finally {
      setBusyItemId('');
    }
  };

  const runItemDuplicateToOtherLocations = async (item: PlanItem) => {
    const sourceLocationKey = String(item.location_scope || item.business_id || '').trim();
    const targetLocationScopes = availableItemLocations
      .map((location) => location.key)
      .filter((key) => key !== 'all' && key !== sourceLocationKey);
    if (targetLocationScopes.length === 0) return;
    setBusyItemId(item.id);
    setError('');
    setActionSummary(null);
    try {
      const response = await newAuth.makeRequest(`/content-plans/items/${encodeURIComponent(item.id)}/duplicate-to-locations`, {
        method: 'POST',
        body: JSON.stringify({
          target_location_scopes: targetLocationScopes,
          scheduled_for: item.scheduled_for,
        }),
      });
      setCurrentPlan(response.plan || null);
      await loadLearningMetrics();
      setActionSummary({
        tone: 'success',
        text_ru: `Шаблон размножен на другие точки: ${targetLocationScopes.length}.`,
        text_en: `Template duplicated to other locations: ${targetLocationScopes.length}.`,
      });
    } catch (duplicateError) {
      const message = duplicateError instanceof Error ? duplicateError.message : (isRu ? 'Не удалось размножить шаблон' : 'Could not duplicate template');
      setError(message);
    } finally {
      setBusyItemId('');
    }
  };

  const runItemDuplicateToSelectedLocations = async (item: PlanItem) => {
    const targetLocationScopes = (duplicateTargetSelections[item.id] || [])
      .map((key) => String(key || '').trim())
      .filter(Boolean);
    if (targetLocationScopes.length === 0) {
      setError(isRu ? 'Выберите хотя бы одну точку для дублирования' : 'Select at least one target location');
      return;
    }
    setBusyItemId(item.id);
    setError('');
    setActionSummary(null);
    try {
      const response = await newAuth.makeRequest(`/content-plans/items/${encodeURIComponent(item.id)}/duplicate-to-locations`, {
        method: 'POST',
        body: JSON.stringify({
          target_location_scopes: targetLocationScopes,
          scheduled_for: duplicateDateOverrides[item.id] || item.scheduled_for,
        }),
      });
      setCurrentPlan(response.plan || null);
      await loadLearningMetrics();
      setExpandedDuplicateItemId('');
      setActionSummary({
        tone: 'success',
        text_ru: `Шаблон размножен на выбранные точки: ${targetLocationScopes.length}.`,
        text_en: `Template duplicated to selected locations: ${targetLocationScopes.length}.`,
      });
    } catch (duplicateError) {
      const message = duplicateError instanceof Error ? duplicateError.message : (isRu ? 'Не удалось размножить шаблон' : 'Could not duplicate template');
      setError(message);
    } finally {
      setBusyItemId('');
    }
  };

  const runQuickAction = (actionKey: QuickActionKey) => {
    if (actionKey === 'open_week') {
      const focusSlice = locationWeekFocusSummary[0];
      if (focusSlice) {
        applyLocationWeekFocus(focusSlice.locationKey, focusSlice.weekKey);
        return;
      }
      if (availableWeeks[1]) {
        setSelectedWeekKey(availableWeeks[1].key);
      }
      return;
    }
    if (actionKey === 'weak_locations') {
      const weakLocation = (learningMetrics?.network_quality || [])[0];
      const weakLocationKey = String(weakLocation?.key || '').trim();
      if (weakLocationKey) {
        setSelectedViewPreset('focus');
        setSelectedItemFilter('urgent');
        setSelectedItemLocationKey(weakLocationKey);
        setSelectedWeekKey('all');
        setSortMode('priority');
      }
      return;
    }
    if (actionKey === 'fix_gaps') {
      applyViewPreset('urgent');
      return;
    }
    if (repeatTemplateCandidate) {
      void runItemDuplicateToOtherLocations(repeatTemplateCandidate);
    }
  };

  const runSocialPlanNextStep = () => {
    setActiveZone('queue');
    if (socialPlanNextStep.action === 'prepare') {
      void prepareSuggestedSocialPosts();
      return;
    }
    if (socialPlanNextStep.action === 'review') {
      const itemIds = visibleSocialNeedsReview
        .map((post) => String(post.content_plan_item_id || '').trim())
        .filter(Boolean);
      const uniqueItemIds = Array.from(new Set(itemIds));
      if (uniqueItemIds.length > 0) {
        setSelectedItemIds(uniqueItemIds.reduce<Record<string, boolean>>((acc, itemId) => {
          acc[itemId] = true;
          return acc;
        }, {}));
        setSelectedQueueItemId(uniqueItemIds[0]);
        setEditorItemId(uniqueItemIds[0]);
      }
      if (visibleSocialNeedsReview.length > 0) {
        openSocialApprovalPreview(visibleSocialNeedsReview, 'selected', 'selected-social-approve');
        setActionSummary({
          tone: 'neutral',
          text_ru: `Выделили темы с постами на проверку: ${uniqueItemIds.length}. Проверьте предпросмотр и подтвердите тексты отдельной кнопкой.`,
          text_en: `Selected topics with posts to review: ${uniqueItemIds.length}. Review the preview and approve copy with a separate button.`,
          details_ru: [
            'Наружу ничего не публикуется на этом шаге.',
            'После подтверждения следующим шагом будет “Поставить в расписание”.',
          ],
          details_en: [
            'Nothing is published externally at this step.',
            'After approval, the next step is “Queue on schedule”.',
          ],
        });
        if (typeof window !== 'undefined') {
          window.setTimeout(() => {
            document
              .querySelector('[data-testid="social-approval-preview-panel"]')
              ?.scrollIntoView({ behavior: 'smooth', block: 'start' });
          }, 50);
        }
      }
      return;
    }
    if (socialPlanNextStep.action === 'queue') {
      void queueVisibleApprovedSocialPosts();
      return;
    }
    if (socialPlanNextStep.action === 'supervised') {
      const post = visibleSocialNeedsSupervised[0];
      const itemId = String(post?.content_plan_item_id || '').trim();
      if (itemId) {
        setSelectedQueueItemId(itemId);
        setEditorItemId(itemId);
      }
      return;
    }
    if (socialPlanNextStep.action === 'manual') {
      const post = visibleSocialNeedsManual[0];
      const itemId = String(post?.content_plan_item_id || '').trim();
      if (itemId) {
        setSelectedQueueItemId(itemId);
        setEditorItemId(itemId);
      }
      return;
    }
    if (socialPlanNextStep.action === 'collect') {
      void collectSocialPostMetricsForBusiness();
      return;
    }
    if (socialPlanNextStep.action === 'recommend') {
      void recommendNextSocialPlan();
      return;
    }
    if (currentPlan?.id) {
      void loadSocialPosts(currentPlan.id);
    }
  };

  const openSocialPostsWaitingForReview = () => {
    setActiveZone('queue');
    applyViewPreset('overview');
    const reviewPosts = allSocialNeedsReview.length > 0 ? allSocialNeedsReview : visibleSocialNeedsReview;
    const itemIds = reviewPosts
      .map((post) => String(post.content_plan_item_id || '').trim())
      .filter(Boolean);
    const uniqueItemIds = Array.from(new Set(itemIds));
    if (uniqueItemIds.length > 0) {
      setSelectedItemIds(uniqueItemIds.reduce<Record<string, boolean>>((acc, itemId) => {
        acc[itemId] = true;
        return acc;
      }, {}));
      setSelectedQueueItemId(uniqueItemIds[0]);
      setEditorItemId(uniqueItemIds[0]);
    }
    if (reviewPosts.length > 0) {
      openSocialApprovalPreview(reviewPosts, 'selected', 'selected-social-approve');
      setActionSummary({
        tone: 'neutral',
        text_ru: `Открыли посты на проверку: ${reviewPosts.length}. Проверьте предпросмотр, затем подтвердите тексты отдельной кнопкой.`,
        text_en: `Opened posts for review: ${reviewPosts.length}. Review the preview, then approve copy with a separate button.`,
        details_ru: [
          'Наружу ничего не публикуется на этом шаге.',
          'После подтверждения worker сможет поставить посты в расписание и исполнить API-каналы.',
        ],
        details_en: [
          'Nothing is published externally at this step.',
          'After approval, the worker can queue posts and execute API channels.',
        ],
      });
      if (typeof window !== 'undefined') {
        window.setTimeout(() => {
          document
            .querySelector('[data-testid="social-approval-preview-panel"]')
            ?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }, 50);
      }
    }
  };

  const openSocialPostsWaitingForQueue = () => {
    setActiveZone('queue');
    applyViewPreset('overview');
    const queuePosts = allSocialCanQueue.length > 0 ? allSocialCanQueue : visibleSocialCanQueue;
    const itemIds = queuePosts
      .map((post) => String(post.content_plan_item_id || '').trim())
      .filter(Boolean);
    const uniqueItemIds = Array.from(new Set(itemIds));
    if (uniqueItemIds.length > 0) {
      setSelectedItemIds(uniqueItemIds.reduce<Record<string, boolean>>((acc, itemId) => {
        acc[itemId] = true;
        return acc;
      }, {}));
      setSelectedQueueItemId(uniqueItemIds[0]);
      setEditorItemId(uniqueItemIds[0]);
    }
    if (queuePosts.length > 0) {
      openSocialQueuePreview(queuePosts, 'selected', 'selected-social-queue');
      setActionSummary({
        tone: 'neutral',
        text_ru: `Открыли утверждённые посты: ${queuePosts.length}. Проверьте расписание и подтвердите постановку отдельной кнопкой.`,
        text_en: `Opened approved posts: ${queuePosts.length}. Review the schedule and confirm queueing with a separate button.`,
        details_ru: [
          'Это ещё не мгновенная публикация всех каналов.',
          'После постановки в расписание API-каналы пойдут по дате, а Яндекс/2ГИС останутся контролируемыми или ручными.',
        ],
        details_en: [
          'This is not instant publishing for every channel.',
          'After queueing, API channels run by date while Yandex/2GIS stay supervised or manual.',
        ],
      });
      if (typeof window !== 'undefined') {
        window.setTimeout(() => {
          document
            .querySelector('[data-testid="social-queue-preview-panel"]')
            ?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }, 50);
      }
    }
  };

  const contentPlanZones: Array<{ key: ContentPlanZone; titleRu: string; titleEn: string; hintRu: string; hintEn: string }> = [
    { key: 'overview', titleRu: 'Обзор', titleEn: 'Overview', hintRu: 'Состояние и следующий шаг', hintEn: 'Status and next step' },
    { key: 'plan', titleRu: 'План', titleEn: 'Plan', hintRu: 'Создание и источники', hintEn: 'Creation and inputs' },
    { key: 'queue', titleRu: 'Готовая очередь по плану', titleEn: 'Plan queue', hintRu: 'Темы, тексты и публикации', hintEn: 'Topics, drafts, and publishing' },
  ];

  if (!businessId) {
    return (
      <div className="rounded-2xl border border-dashed border-gray-200 bg-gray-50 px-6 py-8 text-sm text-gray-600">
        {isRu ? 'Сначала выберите бизнес, чтобы собрать контент-план.' : 'Select a business first to build a content plan.'}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-sm font-semibold uppercase tracking-[0.18em] text-slate-500">
              <CalendarDays className="h-4 w-4" />
              {isRu ? 'Контент-план' : 'Content plan'}
            </div>
            <h4 className="text-xl font-semibold text-slate-950">
              {isRu ? 'Новости, сторис и контент-план' : 'News, stories, and content plan'}
            </h4>
            <p className="max-w-3xl text-sm leading-6 text-slate-600">
              {isRu
                ? 'Один рабочий экран: понять состояние, собрать план, разобрать очередь и довести выбранную тему до публикации.'
                : 'One workspace: understand status, build the plan, work the queue, and turn one selected topic into a publication.'}
            </p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700">
            <div className="font-semibold text-slate-900">
              {isRu ? 'Тариф' : 'Plan access'}
            </div>
            <div className="mt-1">
              {(context?.subscription?.tier || 'trial').toString()}
            </div>
          </div>
        </div>
      </div>

      <div className="rounded-[28px] border border-slate-200 bg-white p-2 shadow-sm">
        <div className="grid gap-2 md:grid-cols-3">
          {contentPlanZones.map((zone) => (
            <button
              key={zone.key}
              type="button"
              onClick={() => setActiveZone(zone.key)}
              className={[
                'rounded-3xl px-4 py-4 text-left transition-colors',
                activeZone === zone.key
                  ? 'bg-slate-950 text-white shadow-sm'
                  : 'bg-transparent text-slate-600 hover:bg-slate-50',
              ].join(' ')}
            >
              <div className="text-lg font-semibold">{isRu ? zone.titleRu : zone.titleEn}</div>
              <div className={['mt-1 text-sm leading-5', activeZone === zone.key ? 'text-slate-300' : 'text-slate-500'].join(' ')}>
                {isRu ? zone.hintRu : zone.hintEn}
              </div>
            </button>
          ))}
        </div>
      </div>

      <div className="flex flex-col gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="text-sm font-semibold text-slate-950">
            {isRu ? 'Режим работы' : 'Mode'}
          </div>
          <div className="text-sm text-slate-500">
            {isRu
              ? 'В точке показываем только локальную работу. В сети — операционный обзор по точкам.'
              : 'Location mode shows local work. Network mode shows the operating view across locations.'}
          </div>
        </div>
        <div className="grid w-full grid-cols-2 rounded-2xl bg-slate-100 p-1 sm:w-[260px]">
          <button
            type="button"
            onClick={() => setContentMode('point')}
            className={[
              'rounded-xl px-4 py-2 text-sm font-medium transition-colors',
              contentMode === 'point' ? 'bg-white text-slate-950 shadow-sm' : 'text-slate-600 hover:text-slate-950',
            ].join(' ')}
          >
            {isRu ? 'Точка' : 'Location'}
          </button>
          <button
            type="button"
            onClick={() => setContentMode('network')}
            disabled={!isNetworkContext}
            className={[
              'rounded-xl px-4 py-2 text-sm font-medium transition-colors',
              contentMode === 'network' ? 'bg-white text-slate-950 shadow-sm' : 'text-slate-600 hover:text-slate-950',
              !isNetworkContext ? 'cursor-not-allowed opacity-50' : '',
            ].join(' ')}
          >
            {isRu ? 'Сеть' : 'Network'}
          </button>
        </div>
      </div>

      <div className={activeZone === 'overview' ? 'space-y-6' : 'hidden'}>
        <div className="rounded-[28px] border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <div className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-500">
                {isRu ? 'Обзор' : 'Overview'}
              </div>
              <div className="mt-2 text-2xl font-semibold tracking-tight text-slate-950">
                {currentPlan?.items?.length
                  ? (planOperationalSummary.needsDraft > 0
                    ? (isRu ? 'Сначала допишите пустые темы' : 'Start by filling empty topics')
                    : planOperationalSummary.readyToPublish > 0
                      ? (isRu ? 'Готовые тексты можно разложить по каналам' : 'Ready drafts can become channel posts')
                      : (isRu ? 'План выглядит спокойно' : 'The plan looks calm'))
                  : (isRu ? 'Соберите первый план публикаций' : 'Build the first content plan')}
              </div>
            <div className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
              {isRu
                ? 'Здесь короткая сводка: сколько тем уже есть, сколько текстов готово, сколько ещё надо дописать и что делать следующим шагом.'
                : 'A short summary: how many topics exist, how many drafts are ready, how many still need text, and the next step.'}
            </div>
            </div>
            {!currentPlan?.items?.length ? (
              <Button onClick={() => setActiveZone('plan')} disabled={loading}>
                <Sparkles className="mr-2 h-4 w-4" />
                {isRu ? 'Перейти к плану' : 'Go to plan'}
              </Button>
            ) : planOperationalSummary.needsDraft > 0 ? (
              <Button onClick={() => { applyViewPreset('urgent'); setActiveZone('queue'); }}>
                {isRu ? 'Открыть темы без текста' : 'Open empty topics'}
              </Button>
            ) : planOperationalSummary.readyToPublish > 0 ? (
              <Button onClick={() => { applyViewPreset('ready'); setActiveZone('queue'); }}>
                {isRu ? 'Открыть готовые тексты' : 'Open ready drafts'}
              </Button>
            ) : (
              <Button onClick={() => setActiveZone('plan')}>
                {isRu ? 'Собрать новый план' : 'Build a new plan'}
              </Button>
            )}
          </div>

          <div className="mt-6 grid gap-3 md:grid-cols-5">
            <div className="rounded-2xl bg-blue-50 px-4 py-4">
              <div className="text-2xl font-semibold text-blue-950">{planOperationalSummary.total}</div>
              <div className="mt-1 text-sm text-blue-800">{isRu ? 'Всего тем' : 'Plan topics'}</div>
            </div>
            <div className="rounded-2xl bg-emerald-50 px-4 py-4">
              <div className="text-2xl font-semibold text-emerald-950">{planOperationalSummary.readyToPublish}</div>
              <div className="mt-1 text-sm text-emerald-800">{isRu ? 'Текст готов' : 'Draft ready'}</div>
            </div>
            <div className="rounded-2xl bg-amber-50 px-4 py-4">
              <div className="text-2xl font-semibold text-amber-950">{planOperationalSummary.needsDraft}</div>
              <div className="mt-1 text-sm text-amber-800">{isRu ? 'Без текста' : 'No text'}</div>
            </div>
            <div className="rounded-2xl bg-slate-50 px-4 py-4">
              <div className="text-2xl font-semibold text-slate-950">{planOperationalSummary.published}</div>
              <div className="mt-1 text-sm text-slate-600">{isRu ? 'Новости созданы' : 'News created'}</div>
            </div>
            <div className="rounded-2xl bg-rose-50 px-4 py-4">
              <div className="text-2xl font-semibold text-rose-950">{Number(overviewRiskScore || 0).toFixed(0)}</div>
              <div className="mt-1 text-sm text-rose-800">{isRu ? 'Риск / слабые точки' : 'Risk / weak spots'}</div>
            </div>
          </div>

          <div
            data-testid="social-owner-simple-goal"
            className="mt-5 rounded-2xl border border-blue-100 bg-blue-50 px-4 py-4"
          >
            <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <div className="text-xs font-semibold uppercase tracking-[0.14em] text-blue-700">
                  {isRu ? 'Цель сейчас' : 'Current goal'}
                </div>
                <div className="mt-1 text-lg font-semibold text-blue-950">
                  {isRu
                    ? 'Довести тему до публикации и результата'
                    : 'Move a topic to publishing and results'}
                </div>
                <div className="mt-1 max-w-3xl text-sm leading-6 text-blue-900">
                  {isRu
                    ? 'Простой путь: подготовить посты из контент-плана, проверить тексты, подтвердить, поставить в расписание, закрыть Яндекс/2ГИС контролируемо и отметить заявки.'
                    : 'Simple path: prepare posts from the content plan, review copy, approve, queue, finish Yandex/2GIS supervised placement, and record leads.'}
                </div>
              </div>
              <Button
                type="button"
                onClick={runSocialPlanNextStep}
                disabled={Boolean(bulkBusyAction) || Boolean(socialBusyAction) || Boolean(socialPlanNextStep.disabled)}
                className="shrink-0 bg-blue-700 text-white hover:bg-blue-800"
              >
                {Boolean(bulkBusyAction) || Boolean(socialBusyAction)
                  ? (isRu ? 'Выполняем...' : 'Working...')
                  : (isRu ? socialPlanNextStep.ctaRu : socialPlanNextStep.ctaEn)}
              </Button>
            </div>
            <div className="mt-3 grid gap-2 text-sm leading-6 md:grid-cols-3">
              <div className="rounded-xl bg-white px-3 py-3 text-blue-900">
                <div className="font-semibold text-blue-950">
                  {isRu ? '1. Что делать первым' : '1. First action'}
                </div>
                <div className="mt-1">
                  {isRu ? socialPlanNextStep.descriptionRu : socialPlanNextStep.descriptionEn}
                </div>
              </div>
              <div className="rounded-xl bg-white px-3 py-3 text-blue-900">
                <div className="font-semibold text-blue-950">
                  {isRu ? '2. Что не произойдёт само' : '2. What will not happen silently'}
                </div>
                <div className="mt-1">
                  {isRu
                    ? 'Наружу ничего не уйдёт без предпросмотра, подтверждения и расписания. Финальный клик в Яндекс/2ГИС остаётся за человеком.'
                    : 'Nothing goes external without preview, approval, and queueing. The final Yandex/2GIS click stays human-controlled.'}
                </div>
              </div>
              <div className="rounded-xl bg-white px-3 py-3 text-blue-900">
                <div className="font-semibold text-blue-950">
                  {isRu ? '3. Как понять успех' : '3. Success signal'}
                </div>
                <div className="mt-1">
                  {isRu
                    ? 'Есть опубликованные посты, закрытые ручные задачи и отмеченные заявки/обращения. После этого LocalOS предлагает изменения следующего плана.'
                    : 'Posts are published, manual tasks are closed, and leads/inquiries are recorded. Then LocalOS suggests next-plan changes.'}
                </div>
              </div>
            </div>
            {socialLaunchStages.length > 0 ? (
              <div
                data-testid="social-owner-goal-progress"
                className="mt-3 rounded-xl border border-blue-100 bg-white px-3 py-3 text-sm leading-6 text-blue-900"
              >
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                  <div>
                    <div className="font-semibold text-blue-950">
                      {isRu ? 'Где мы сейчас' : 'Where we are now'}
                    </div>
                    <div className="mt-1">
                      {String(
                        (isRu ? socialGoalProgress?.summary?.current_label_ru : socialGoalProgress?.summary?.current_label_en)
                        || (socialLaunchChecklistSummary.current
                          ? (isRu ? socialLaunchChecklistSummary.current.labelRu : socialLaunchChecklistSummary.current.labelEn)
                          : (isRu ? 'Следующий шаг' : 'Next step'))
                      )}
                      {' · '}
                      {String(
                        (isRu ? socialGoalProgress?.next_action_ru : socialGoalProgress?.next_action_en)
                        || (socialLaunchChecklistSummary.current
                          ? (isRu
                            ? socialLaunchChecklistSummary.current.detailRu
                            : socialLaunchChecklistSummary.current.detailEn)
                          : (isRu
                            ? 'Откройте очередь публикаций и подготовьте первый канал.'
                            : 'Open the publishing queue and prepare the first channel.'))
                      )}
                    </div>
                  </div>
                  <div className="grid gap-2 text-xs sm:grid-cols-3 lg:min-w-[420px]">
                    <div className="rounded-lg bg-blue-50 px-2 py-1.5">
                      <div className="font-semibold text-blue-950">
                        {Number(socialLaunchChecklistSummary.done || 0)}
                        /
                        {Number(socialLaunchChecklistSummary.total || socialLaunchStages.length || 0)}
                      </div>
                      <div>{isRu ? 'этапов готово' : 'steps done'}</div>
                    </div>
                    <div className="rounded-lg bg-amber-50 px-2 py-1.5 text-amber-800">
                      <div className="font-semibold text-amber-950">
                        {Math.max(0, Number(socialLaunchChecklistSummary.attention || 0))}
                      </div>
                      <div>{isRu ? 'требует внимания' : 'need attention'}</div>
                    </div>
                    <div className="rounded-lg bg-emerald-50 px-2 py-1.5 text-emerald-800">
                      <div className="font-semibold text-emerald-950">
                        {Math.max(
                          0,
                          Number(socialLaunchChecklistSummary.total || socialLaunchStages.length || 0)
                            - Number(socialLaunchChecklistSummary.done || 0),
                        )}
                      </div>
                      <div>{isRu ? 'осталось до loop' : 'left to loop'}</div>
                    </div>
                  </div>
                </div>
              </div>
            ) : null}
          </div>

          <div
            data-testid="social-quick-launch"
            className="mt-5 rounded-2xl border border-slate-900 bg-slate-950 px-4 py-4 text-white"
          >
            <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">
                  {isRu ? 'Быстрый запуск публикаций' : 'Quick publishing launch'}
                </div>
                <div className="mt-2 text-lg font-semibold">
                  {isRu ? socialPlanNextStep.titleRu : socialPlanNextStep.titleEn}
                </div>
                <div className="mt-2 max-w-3xl text-sm leading-6 text-slate-300">
                  {isRu ? socialPlanNextStep.descriptionRu : socialPlanNextStep.descriptionEn}
                </div>
                <SocialOwnerLaunchPath
                  isRu={isRu}
                  currentAction={socialPlanNextStep.action}
                />
                <div className="mt-3 grid gap-2 text-xs text-slate-300 sm:grid-cols-3">
                  <div className="rounded-xl bg-white/10 px-3 py-2">
                    <div className="text-base font-semibold text-white">{socialReadinessSummary.apiReady}</div>
                    <div>{isRu ? 'API-каналы готовы' : 'API channels ready'}</div>
                  </div>
                  <div className="rounded-xl bg-white/10 px-3 py-2">
                    <div className="text-base font-semibold text-white">{socialReadinessSummary.supervisedOrManual}</div>
                    <div>{isRu ? 'Яндекс/2ГИС под контролем' : 'Yandex/2GIS supervised'}</div>
                  </div>
                  <div className="rounded-xl bg-white/10 px-3 py-2">
                    <div className="text-base font-semibold text-white">{socialReadinessSummary.needsAttention}</div>
                    <div>{isRu ? 'нужны ключи или права' : 'need keys or rights'}</div>
                  </div>
                </div>
                <div
                  data-testid="social-overview-first-api-readiness"
                  className={[
                    'mt-3 rounded-xl border px-3 py-3 text-xs leading-5',
                    socialFirstApiPublishReadiness.hasAnyReadyApi
                      ? 'border-emerald-300/30 bg-emerald-400/10 text-emerald-50'
                      : 'border-amber-300/30 bg-amber-400/10 text-amber-50',
                  ].join(' ')}
                >
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <div className="font-semibold text-white">
                        {isRu ? 'Первый API-пост' : 'First API post'}
                        {' · '}
                        {socialFirstApiPublishReadiness.hasAnyReadyApi
                          ? (isRu ? 'есть готовый канал' : 'ready channel exists')
                          : (isRu ? 'нужны ключи' : 'needs keys')}
                      </div>
                      <div className="mt-1 text-slate-200">
                        {socialFirstApiPublishReadiness.hasAnyReadyApi
                          ? (isRu
                            ? `Можно начинать с API-каналов: ${socialFirstApiPublishReadiness.readyLabels.join(', ')}.`
                            : `You can start with API channels: ${socialFirstApiPublishReadiness.readyLabels.join(', ')}.`)
                          : (isRu
                            ? 'Пока нет готового API-канала: подключите Telegram или VK, чтобы первый пост вышел по расписанию.'
                            : 'No API channel is ready yet: connect Telegram or VK so the first post can publish on schedule.')}
                      </div>
                      <div className="mt-1 text-slate-300">
                        {isRu
                          ? 'Наружу только после предпросмотра, подтверждения, расписания и даты публикации.'
                          : 'External publishing happens only after preview, human approval, queueing, and the due date.'}
                      </div>
                      <div
                        data-testid="social-overview-fast-api-start"
                        className="mt-2 rounded-lg bg-white/10 px-2.5 py-2 text-slate-100"
                      >
                        <div className="font-semibold text-white">
                          {isRu ? 'Быстрый API старт: Telegram/VK' : 'Fast API start: Telegram/VK'}
                        </div>
                        <div className="mt-1">
                          {socialFirstApiPublishReadiness.fastStartReadyLabels.length > 0
                            ? (isRu
                              ? `Начните proof с ${socialFirstApiPublishReadiness.fastStartReadyLabels.join(', ')}; это самый короткий путь до первого опубликованного API-поста.`
                              : `Start the proof with ${socialFirstApiPublishReadiness.fastStartReadyLabels.join(', ')}; this is the shortest path to the first published API post.`)
                            : socialFirstApiPublishReadiness.fastStartBlockedLabels.length > 0
                              ? (isRu
                                ? `Сначала подключите ${socialFirstApiPublishReadiness.fastStartBlockedLabels.join(', ')}: это быстрее, чем ждать Meta/Google permissions.`
                                : `Connect ${socialFirstApiPublishReadiness.fastStartBlockedLabels.join(', ')} first: this is faster than waiting for Meta/Google permissions.`)
                              : (isRu
                                ? 'Если Telegram/VK не выбраны в плане, первый API-proof можно начать с готового канала, но Telegram/VK остаются самым быстрым MVP-путём.'
                                : 'If Telegram/VK are not selected for the plan, start the first API proof with any ready channel, while Telegram/VK remain the fastest MVP path.')}
                        </div>
                        <div className="mt-1 text-slate-300">
                          {isRu
                            ? 'Безопасный порядок: проверить API-канал без публикации → открыть preview → утвердить человеком → поставить в расписание.'
                            : 'Safe order: check the API channel without publishing → open preview → human approval → queue it.'}
                        </div>
                      </div>
                      {socialFirstApiPublishReadiness.setupFocus?.target_setup?.schema ? (
                        <div
                          data-testid={`social-overview-channel-target-setup-${String(socialFirstApiPublishReadiness.setupFocus.platform || '')}`}
                          data-schema={String(socialFirstApiPublishReadiness.setupFocus.target_setup.schema || 'localos_social_channel_target_setup_v1')}
                          className="mt-2 rounded-lg border border-white/10 bg-white/10 px-2.5 py-2 text-slate-100"
                        >
                          <div className="font-semibold text-white">
                            {isRu
                              ? String(socialFirstApiPublishReadiness.setupFocus.target_setup.target_label_ru || 'Цель публикации')
                              : String(socialFirstApiPublishReadiness.setupFocus.target_setup.target_label_en || 'Publish target')}
                          </div>
                          {socialFirstApiPublishReadiness.setupFocus.target_setup.owner_telegram_present ? (
                            <div
                              data-testid="social-overview-owner-telegram-linked"
                              className="mt-1 inline-flex rounded-full bg-sky-400/20 px-2 py-0.5 text-[11px] font-semibold text-sky-50"
                            >
                              {isRu ? 'Владелец подключён в Telegram' : 'Owner Telegram is linked'}
                            </div>
                          ) : null}
                          {socialFirstApiPublishReadiness.setupFocus.target_setup.telegram_app_present ? (
                            <div
                              data-testid="social-overview-telegram-app-linked"
                              className="ml-1 mt-1 inline-flex rounded-full bg-violet-400/20 px-2 py-0.5 text-[11px] font-semibold text-violet-50"
                            >
                              {isRu ? 'Telegram app подключён' : 'Telegram app linked'}
                            </div>
                          ) : null}
                          <div className="mt-1">
                            {isRu
                              ? String(socialFirstApiPublishReadiness.setupFocus.target_setup.summary_ru || '')
                              : String(socialFirstApiPublishReadiness.setupFocus.target_setup.summary_en || '')}
                          </div>
                          <div className="mt-1 text-slate-300">
                            {isRu
                              ? String(socialFirstApiPublishReadiness.setupFocus.target_setup.not_a_target_ru || '')
                              : String(socialFirstApiPublishReadiness.setupFocus.target_setup.not_a_target_en || '')}
                          </div>
                          <div className="mt-1 font-medium text-white">
                            {isRu
                              ? String(socialFirstApiPublishReadiness.setupFocus.target_setup.proof_ru || '')
                              : String(socialFirstApiPublishReadiness.setupFocus.target_setup.proof_en || '')}
                          </div>
                        </div>
                      ) : null}
                      {socialFirstApiPublishReadiness.blockedLabels.length > 0 ? (
                        <div className="mt-1 text-amber-100">
                          <span className="font-semibold">{isRu ? 'Сначала исправить: ' : 'Fix first: '}</span>
                          {socialFirstApiPublishReadiness.blockedLabels.slice(0, 3).join(', ')}
                        </div>
                      ) : null}
                    </div>
                    {socialFirstApiPublishReadiness.firstBlocked ? (
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => navigate(_socialSettingsPathForPlatform(String(socialFirstApiPublishReadiness.firstBlocked?.platform || '')))}
                        className="h-8 shrink-0 border-white/20 bg-white/10 px-3 text-xs text-white hover:bg-white/20 hover:text-white"
                      >
                        {isRu ? 'Открыть настройку' : 'Open setup'}
                      </Button>
                    ) : null}
                  </div>
                </div>
                <div
                  data-testid="social-first-api-blocker-card"
                  className={[
                    'mt-3 rounded-xl border px-3 py-3 text-xs leading-5',
                    socialFirstApiBlockerCard.tone === 'success'
                      ? 'border-emerald-300/30 bg-emerald-400/10 text-emerald-50'
                      : socialFirstApiBlockerCard.tone === 'warning'
                        ? 'border-amber-300/30 bg-amber-400/10 text-amber-50'
                        : 'border-sky-300/30 bg-sky-400/10 text-sky-50',
                  ].join(' ')}
                >
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <div className="font-semibold text-white">
                        {isRu ? socialFirstApiBlockerCard.titleRu : socialFirstApiBlockerCard.titleEn}
                      </div>
                      <ul className="mt-2 space-y-1 text-slate-100">
                        {(isRu ? socialFirstApiBlockerCard.factsRu : socialFirstApiBlockerCard.factsEn).map((line) => (
                          <li key={`first-api-blocker-fact:${line}`} className="flex gap-1.5">
                            <span className="font-semibold text-white">•</span>
                            <span>{line}</span>
                          </li>
                        ))}
                      </ul>
                      <div className="mt-2 font-medium text-white">
                        {isRu ? 'Следующий безопасный шаг: ' : 'Next safe step: '}
                        {isRu ? socialFirstApiBlockerCard.nextRu : socialFirstApiBlockerCard.nextEn}
                      </div>
                    </div>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      disabled={socialFirstApiBlockerCard.status === 'prepare' && socialPostsLoading}
                      onClick={() => {
                        if (socialFirstApiBlockerCard.status === 'connect') {
                          navigate(_socialSettingsPathForPlatform(socialFirstApiBlockerCard.firstBlockedPlatform || 'telegram'));
                          return;
                        }
                        runSocialPlanNextStep();
                      }}
                      className="h-8 shrink-0 border-white/20 bg-white/10 px-3 text-xs text-white hover:bg-white/20 hover:text-white"
                    >
                      {isRu ? socialFirstApiBlockerCard.ctaRu : socialFirstApiBlockerCard.ctaEn}
                    </Button>
                  </div>
                </div>
                <div
                  data-testid="social-owner-publishing-path"
                  className="mt-3 rounded-xl border border-white/10 bg-white/10 px-3 py-3"
                >
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">
                        {isRu ? 'Маршрут поста' : 'Post path'}
                      </div>
                      <div className="mt-1 text-sm font-semibold text-white">
                        {isRu
                          ? 'Подготовить, проверить, подтвердить и только потом исполнить'
                          : 'Prepare, review, approve, then execute'}
                      </div>
                    </div>
                    <div className="rounded-lg bg-white/10 px-2 py-1.5 text-xs font-semibold text-emerald-100">
                      {isRu ? 'Финальный клик на картах — за человеком' : 'Map final click stays human'}
                    </div>
                  </div>
                  <div className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
                    {[
                      {
                        labelRu: '1. Подготовить каналы',
                        labelEn: '1. Prepare channels',
                        detailRu: 'Из темы создаются тексты для карт и соцсетей.',
                        detailEn: 'A plan topic becomes map and social drafts.',
                      },
                      {
                        labelRu: '2. Проверить тексты',
                        labelEn: '2. Review drafts',
                        detailRu: 'Предпросмотр показывает канал, текст, дату и ограничения.',
                        detailEn: 'Preview shows channel, copy, date, and limits.',
                      },
                      {
                        labelRu: '3. Подтвердить',
                        labelEn: '3. Approve',
                        detailRu: 'Подтверждение фиксирует согласие, но ещё ничего не публикует.',
                        detailEn: 'Approval records consent and still publishes nothing.',
                      },
                      {
                        labelRu: '4. Поставить в расписание',
                        labelEn: '4. Queue on schedule',
                        detailRu: 'Исполнитель возьмёт только подтверждённые API-посты, когда наступит дата.',
                        detailEn: 'The worker can execute only approved due API posts.',
                      },
                      {
                        labelRu: '5. Контролируемое размещение',
                        labelEn: '5. Supervised placement',
                        detailRu: 'Яндекс/2ГИС получают задачу с предпросмотром, без тихого автоклика.',
                        detailEn: 'Yandex/2GIS get a preview task, without hidden auto-clicks.',
                      },
                      {
                        labelRu: '6. Сбор реакций и заявок',
                        labelEn: '6. Collect results',
                        detailRu: 'Главный сигнал для следующего плана — заявки и обращения.',
                        detailEn: 'Leads and inquiries are the main signal for the next plan.',
                      },
                    ].map((step) => (
                      <div
                        key={isRu ? step.labelRu : step.labelEn}
                        className="rounded-lg bg-slate-950/50 px-3 py-2 text-xs leading-5 text-slate-300"
                      >
                        <div className="font-semibold text-white">{isRu ? step.labelRu : step.labelEn}</div>
                        <div className="mt-1">{isRu ? step.detailRu : step.detailEn}</div>
                      </div>
                    ))}
                  </div>
                </div>
                {socialFirstApiProofDossier ? (
                  <div
                    data-testid="social-first-api-proof-dossier"
                    data-schema="localos_social_first_api_proof_dossier_v1"
                    className={[
                      'mt-3 rounded-xl border px-3 py-3 text-xs leading-5',
                      socialFirstApiProofDossier.ready
                        ? 'border-emerald-300/30 bg-emerald-400/10 text-emerald-50'
                        : 'border-sky-300/30 bg-sky-400/10 text-sky-50',
                    ].join(' ')}
                  >
                    <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                      <div>
                        <div className="font-semibold text-white">
                          {isRu ? socialFirstApiProofDossier.title_ru : socialFirstApiProofDossier.title_en}
                        </div>
                        <div className="mt-1 text-slate-200">
                          {isRu ? socialFirstApiProofDossier.summary_ru : socialFirstApiProofDossier.summary_en}
                        </div>
                      </div>
                      <div className="rounded-lg bg-white/10 px-2 py-1.5 text-[11px] font-semibold text-white">
                        {isRu ? socialFirstApiProofDossier.primary_metric_ru : socialFirstApiProofDossier.primary_metric_en}
                      </div>
                    </div>
                    <div className="mt-2 rounded-lg bg-white/10 px-2 py-2">
                      <div className="font-semibold text-white">
                        {isRu ? 'Следующий шаг: ' : 'Next step: '}
                        {isRu ? socialFirstApiProofDossier.next_action_ru : socialFirstApiProofDossier.next_action_en}
                      </div>
                      {(
                        isRu
                          ? socialFirstApiProofDossier.steps_ru
                          : socialFirstApiProofDossier.steps_en
                      )?.length ? (
                        <ol className="mt-2 space-y-1">
                          {(
                            isRu
                              ? socialFirstApiProofDossier.steps_ru
                              : socialFirstApiProofDossier.steps_en
                          )?.slice(0, 3).map((step, index) => (
                            <li key={`first-api-proof-dossier-step:${index}:${step}`} className="flex gap-1.5 text-slate-100">
                              <span className="font-semibold text-white">{index + 1}.</span>
                              <span>{step}</span>
                            </li>
                          ))}
                        </ol>
                      ) : null}
                    </div>
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      <span className="rounded-full bg-white/10 px-2 py-0.5 font-medium text-slate-100">
                        {isRu ? 'подтверждение обязательно' : 'approval required'}
                      </span>
                      <span className="rounded-full bg-white/10 px-2 py-0.5 font-medium text-slate-100">
                        {isRu ? 'публикация только по расписанию' : 'publish only through queue/due'}
                      </span>
                      <span className="rounded-full bg-white/10 px-2 py-0.5 font-medium text-slate-100">
                        {isRu ? 'карты без финального автоклика' : 'maps without final auto-click'}
                      </span>
                    </div>
                  </div>
                ) : null}
                <SocialLaunchChecklist
                  isRu={isRu}
                  stages={socialLaunchStages}
                  summary={socialLaunchChecklistSummary}
                />
                <div
                  data-testid="social-overview-learning-loop-status"
                  className={[
                    'mt-3 rounded-xl border px-3 py-3 text-xs leading-5',
                    socialLearningLoopStatus.tone === 'success'
                      ? 'border-emerald-300/40 bg-emerald-400/10 text-emerald-50'
                      : socialLearningLoopStatus.tone === 'warning'
                        ? 'border-amber-300/40 bg-amber-400/10 text-amber-50'
                        : socialLearningLoopStatus.tone === 'caution'
                          ? 'border-sky-300/40 bg-sky-400/10 text-sky-50'
                          : 'border-white/10 bg-white/10 text-slate-200',
                  ].join(' ')}
                >
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <div className="font-semibold text-white">
                        {isRu ? 'Learning loop' : 'Learning loop'} · {isRu ? socialLearningLoopStatus.titleRu : socialLearningLoopStatus.titleEn}
                      </div>
                      <div className="mt-1 text-slate-200">
                        {isRu ? socialLearningLoopStatus.textRu : socialLearningLoopStatus.textEn}
                      </div>
                    </div>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        if (socialLearningLoopStatus.action === 'collect') {
                          void collectSocialPostMetricsForBusiness();
                          return;
                        }
                        if (socialLearningLoopStatus.action === 'recommend') {
                          void recommendNextSocialPlan();
                          return;
                        }
                        setActiveZone('queue');
                      }}
                      disabled={
                        (socialLearningLoopStatus.action === 'collect' && socialBusyAction === 'collect-metrics')
                        || (socialLearningLoopStatus.action === 'recommend' && socialBusyAction === 'recommend')
                      }
                      data-testid="social-overview-learning-loop-action"
                      className="h-8 shrink-0 border-white/20 bg-white/10 px-3 text-xs text-white hover:bg-white/20 hover:text-white"
                    >
                      {socialLearningLoopStatus.action === 'collect' && socialBusyAction === 'collect-metrics'
                        ? (isRu ? 'Собираем...' : 'Collecting...')
                        : socialLearningLoopStatus.action === 'recommend' && socialBusyAction === 'recommend'
                          ? (isRu ? 'Считаем...' : 'Calculating...')
                          : (isRu ? socialLearningLoopStatus.ctaRu : socialLearningLoopStatus.ctaEn)}
                    </Button>
                  </div>
                </div>
                {socialOverviewChannelHighlights.length > 0 ? (
                  <div className="mt-3 rounded-xl bg-white/10 px-3 py-3">
                    <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">
                      {isRu ? 'Каналы: что сделать' : 'Channels: next actions'}
                    </div>
                    <div className="mt-2 grid gap-2 md:grid-cols-2">
                      {socialOverviewChannelHighlights.map((channel) => {
                        const mode = String(channel.publish_mode || '').trim();
                        const isControlled = mode === 'openclaw_browser' || mode === 'local_supervised_browser' || mode === 'manual';
                        const badge = channel.ready
                          ? (isRu ? 'готов' : 'ready')
                          : isControlled
                            ? (isRu ? 'контроль' : 'supervised')
                            : (isRu ? 'нужно внимание' : 'needs attention');
                        const line = String(
                          (isRu
                            ? channel.setup_summary_ru || channel.next_action_ru || channel.message_ru
                            : channel.setup_summary_en || channel.next_action_en || channel.message_en) || ''
                        ).trim();
                        return (
                          <div key={`overview-channel-${channel.platform}`} className="rounded-lg bg-white/10 px-3 py-2 text-xs leading-5 text-slate-200">
                            <div className="flex items-center justify-between gap-2">
                              <span className="font-semibold text-white">
                                {channel.platform_label || _socialPlatformLabel(channel.platform, isRu)}
                              </span>
                              <span className={channel.ready || isControlled ? 'text-sky-200' : 'text-amber-200'}>
                                {badge}
                              </span>
                            </div>
                            <div className="mt-1 line-clamp-2 text-slate-300">
                              {line || _socialPublishModeLabel(channel.publish_mode || '', isRu)}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                    {socialReadinessSummary.blockedApiChannels.length > 0 ? (
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => navigate(socialReadinessSetupPath)}
                        className="mt-3 h-8 border-white/20 bg-white/10 px-3 text-xs text-white hover:bg-white/20 hover:text-white"
                      >
                        {isRu ? 'Открыть настройку канала' : 'Open channel setup'}
                      </Button>
                    ) : null}
                  </div>
                ) : null}
                <div className="mt-3 rounded-xl bg-white/10 px-3 py-2 text-xs leading-5 text-slate-200">
                  <div>
                    {isRu
                      ? 'Внешние публикации идут только после предпросмотра и подтверждения. Для Яндекс/2ГИС LocalOS готовит контролируемое размещение, а не скрытую автопубликацию.'
                      : 'External publishing runs only after preview and approval. For Yandex/2GIS, LocalOS prepares supervised placement, not hidden autopublish.'}
                  </div>
                  <div className="mt-2 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                    <div className="text-slate-300">
                      {isRu
                        ? 'Готовность OpenClaw для Яндекс/2ГИС проверяется отдельно: если внешний исполнитель недоступен, будет ручной режим без срыва плана.'
                        : 'OpenClaw readiness for Yandex/2GIS is checked separately: if the receiver is unreachable, LocalOS keeps manual fallback without blocking the plan.'}
                    </div>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => { void checkOpenClawBrowserReadiness(); }}
                      disabled={socialBusyAction === 'openclaw-check'}
                      className="h-7 shrink-0 border-white/20 bg-white/10 px-2.5 text-[11px] text-white hover:bg-white/20 hover:text-white"
                    >
                      {socialBusyAction === 'openclaw-check'
                        ? (isRu ? 'Проверяем...' : 'Checking...')
                        : (isRu ? 'Проверить OpenClaw' : 'Check OpenClaw')}
                    </Button>
                  </div>
                </div>
              </div>
              <div className="flex flex-col gap-2 sm:min-w-[260px]">
                <Button
                  type="button"
                  onClick={runSocialPlanNextStep}
                  disabled={Boolean(bulkBusyAction) || Boolean(socialBusyAction) || Boolean(socialPlanNextStep.disabled)}
                  className="bg-white text-slate-950 hover:bg-slate-100"
                >
                  {Boolean(bulkBusyAction) || Boolean(socialBusyAction)
                    ? (isRu ? 'Выполняем...' : 'Working...')
                    : `${isRu ? socialPlanNextStep.ctaRu : socialPlanNextStep.ctaEn} · ${socialPlanNextStep.count}`}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setActiveZone('queue')}
                  className="border-white/20 bg-transparent text-white hover:bg-white/10 hover:text-white"
                >
                  {isRu ? 'Открыть очередь и предпросмотр' : 'Open queue and preview'}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => { void previewSocialDispatch(); }}
                  disabled={Boolean(bulkBusyAction) || Boolean(socialBusyAction)}
                  className="border-white/20 bg-transparent text-white hover:bg-white/10 hover:text-white"
                >
                  {socialBusyAction === 'dispatch-preview'
                    ? (isRu ? 'Проверяем...' : 'Checking...')
                    : (isRu ? 'Проверить расписание' : 'Preview schedule')}
                </Button>
              </div>
            </div>
          </div>

          {socialLaunchStages.length > 0 ? (
            <div className="mt-5 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
              <div className="flex flex-col gap-2 lg:flex-row lg:items-start lg:justify-between">
                <div>
                  <div className="text-sm font-semibold text-slate-950">
                    {isRu ? 'Цель публикаций' : 'Publishing goal'}
                  </div>
                  <div className="mt-1 max-w-3xl text-xs leading-5 text-slate-500">
                    {String(
                      (isRu ? socialGoalProgress?.goal_ru : socialGoalProgress?.goal_en)
                      || (isRu
                        ? 'Дойти от темы в контент-плане до публикации, результата и корректировки следующей недели. Карты идут через контролируемое или ручное размещение, API-каналы — только после подтверждения.'
                        : 'Move from a content-plan topic to publishing, results, and next-week correction. Maps stay supervised; API channels run only after approval.')
                    )}
                  </div>
                  <div className="mt-2 flex flex-wrap gap-1.5 text-[11px] font-medium">
                    <span className="rounded-full bg-white px-2 py-0.5 text-slate-700">
                      {isRu ? 'Главный KPI: ' : 'Main KPI: '}
                      {String((isRu ? socialGoalProgress?.primary_metric_ru : socialGoalProgress?.primary_metric_en) || (isRu ? 'заявки и обращения' : 'leads and inquiries'))}
                    </span>
                    <span className="rounded-full bg-white px-2 py-0.5 text-slate-700">
                      {socialGoalProgress?.approval_required === false
                        ? (isRu ? 'подтверждение не требуется' : 'approval not required')
                        : (isRu ? 'подтверждение обязательно' : 'approval required')}
                    </span>
                    <span className="rounded-full bg-white px-2 py-0.5 text-slate-700">
                      {socialGoalProgress?.maps_are_supervised_or_manual === false
                        ? (isRu ? 'карты требуют проверки режима' : 'map mode needs review')
                        : (isRu ? 'Яндекс/2ГИС: контроль/вручную' : 'Yandex/2GIS: supervised/manual')}
                    </span>
                  </div>
                </div>
                <div className="flex flex-col gap-2 sm:flex-row sm:items-start lg:max-w-[520px]">
                  <div
                    data-testid="social-goal-current-step"
                    className={[
                      'rounded-xl border bg-white px-3 py-2 text-xs leading-5',
                      socialLaunchChecklistSummary.attention > 0
                        ? 'border-red-100 text-red-800'
                        : socialLaunchChecklistSummary.current?.status === 'current'
                          ? 'border-sky-100 text-sky-800'
                          : 'border-slate-200 text-slate-600',
                    ].join(' ')}
                  >
                    <div className="font-semibold text-slate-950">
                      {isRu
                        ? `Этап ${Math.max(1, socialLaunchChecklistSummary.done + 1)} из ${socialLaunchChecklistSummary.total || socialLaunchStages.length}`
                        : `Step ${Math.max(1, socialLaunchChecklistSummary.done + 1)} of ${socialLaunchChecklistSummary.total || socialLaunchStages.length}`}
                    </div>
                    <div className="mt-0.5 font-medium">
                      {String(
                        (isRu ? socialGoalProgress?.summary?.current_label_ru : socialGoalProgress?.summary?.current_label_en)
                        || (socialLaunchChecklistSummary.current
                          ? (isRu ? socialLaunchChecklistSummary.current.labelRu : socialLaunchChecklistSummary.current.labelEn)
                          : (isRu ? 'Следующий шаг' : 'Next step'))
                      )}
                    </div>
                    <div className="mt-0.5">
                      {String(
                        (isRu ? socialGoalProgress?.next_action_ru : socialGoalProgress?.next_action_en)
                        || (socialLaunchChecklistSummary.current
                          ? (isRu
                            ? socialLaunchChecklistSummary.current.detailRu
                            : socialLaunchChecklistSummary.current.detailEn)
                          : (isRu
                            ? 'Откройте очередь публикаций и подготовьте первый канал.'
                            : 'Open the publishing queue and prepare the first channel.'))
                      )}
                    </div>
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="bg-white"
                    onClick={() => setActiveZone('queue')}
                  >
                    {isRu ? 'Открыть очередь' : 'Open queue'}
                  </Button>
                </div>
              </div>
              <div
                data-testid="social-goal-remaining-work"
                className="mt-3 grid gap-2 text-xs leading-5 sm:grid-cols-3"
              >
                <div className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-slate-600">
                  <div className="font-semibold text-slate-950">
                    {isRu ? '1. Подготовить и утвердить' : '1. Prepare and approve'}
                  </div>
                  <div className="mt-1">
                    {isRu
                      ? 'Посты появляются из контент-плана LocalOS, проходят предпросмотр и подтверждение.'
                      : 'Posts come from the LocalOS content plan, then pass preview and approval.'}
                  </div>
                </div>
                <div className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-slate-600">
                  <div className="font-semibold text-slate-950">
                    {isRu ? '2. Исполнить безопасно' : '2. Execute safely'}
                  </div>
                  <div className="mt-1">
                    {isRu
                      ? 'API-каналы идут по расписанию; Яндекс/2ГИС остаются контролируемыми или ручными.'
                      : 'API channels run on schedule; Yandex/2GIS stay supervised or manual.'}
                  </div>
                </div>
                <div className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-slate-600">
                  <div className="font-semibold text-slate-950">
                    {isRu ? '3. Улучшить следующий план' : '3. Improve the next plan'}
                  </div>
                  <div className="mt-1">
                    {isRu
                      ? 'Система ранжирует заявки и обращения выше охватов и ждёт подтверждения перед применением.'
                      : 'The system ranks leads and inquiries above reach and waits for confirmation before applying changes.'}
                  </div>
                </div>
              </div>
              <div className="mt-3 grid gap-2 md:grid-cols-2 xl:grid-cols-3">
                {socialLaunchStages.map((stage) => (
                  <div
                    key={`overview-${stage.key}`}
                    className={[
                      'rounded-xl border bg-white px-3 py-3',
                      stage.status === 'done'
                        ? 'border-emerald-100'
                        : stage.status === 'current'
                          ? 'border-sky-200'
                          : stage.status === 'attention'
                            ? 'border-red-200'
                            : 'border-slate-200',
                    ].join(' ')}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div
                        className={[
                          'text-xs font-semibold',
                          stage.status === 'done'
                            ? 'text-emerald-800'
                            : stage.status === 'current'
                              ? 'text-sky-800'
                              : stage.status === 'attention'
                                ? 'text-red-800'
                                : 'text-slate-600',
                        ].join(' ')}
                      >
                        {isRu ? stage.labelRu : stage.labelEn}
                      </div>
                      <span
                        className={[
                          'shrink-0 rounded-full px-2 py-0.5 text-[11px] font-semibold',
                          stage.status === 'done'
                            ? 'bg-emerald-50 text-emerald-700'
                            : stage.status === 'current'
                              ? 'bg-sky-50 text-sky-700'
                              : stage.status === 'attention'
                                ? 'bg-red-50 text-red-700'
                                : 'bg-slate-100 text-slate-500',
                        ].join(' ')}
                      >
                        {stage.status === 'done'
                          ? (isRu ? 'готово' : 'done')
                          : stage.status === 'current'
                            ? (isRu ? 'сейчас' : 'now')
                            : stage.status === 'attention'
                              ? (isRu ? 'внимание' : 'attention')
                              : (isRu ? 'позже' : 'later')}
                      </span>
                    </div>
                    <div className="mt-1 text-xs leading-5 text-slate-500">
                      {isRu ? stage.detailRu : stage.detailEn}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          <div className="mt-5 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
            <button
              type="button"
              onClick={() => setShowLearningDetails((prev) => !prev)}
              className="flex w-full items-center justify-between gap-3 text-left text-sm font-semibold text-slate-900"
            >
              <span>{isRu ? 'Что система уже поняла' : 'What the system already learned'}</span>
              <span className="text-xs text-slate-500">{showLearningDetails ? (isRu ? 'Скрыть' : 'Hide') : (isRu ? 'Показать' : 'Show')}</span>
            </button>
            {showLearningDetails ? (
              <div className="mt-3 grid gap-2 lg:grid-cols-2">
                {(operatorQualityInsights.length > 0 ? operatorQualityInsights : [{
                  key: 'empty-learning',
                  textRu: 'Пока мало истории. После публикаций здесь появятся подсказки по темам и источникам.',
                  textEn: 'There is not enough history yet. Topic and source hints will appear after publications.',
                }]).map((item) => (
                  <div key={item.key} className="rounded-xl bg-white px-3 py-2 text-sm leading-6 text-slate-700">
                    {isRu ? item.textRu : item.textEn}
                  </div>
                ))}
              </div>
            ) : null}
          </div>
        </div>
      </div>

      <div className={activeZone === 'plan' ? 'space-y-6' : 'hidden'}>
      {selectedScopeDescription ? (
        <div className="rounded-2xl border border-indigo-100 bg-indigo-50/70 px-5 py-4 text-sm text-indigo-950">
          <div className="font-semibold">
            {selectedScopeLabel || (isRu ? 'Выбранный сценарий' : 'Selected scope')}
          </div>
          <div className="mt-1 leading-6 text-indigo-900/90">
            {selectedScopeDescription}
          </div>
        </div>
      ) : null}

      {readiness && !readiness.is_grounded_for_search ? (
        <div
          className={[
            'rounded-2xl border px-5 py-4 text-sm',
            networkHasSearchPlanFoundation
              ? 'border-emerald-200 bg-emerald-50 text-emerald-950'
              : 'border-amber-200 bg-amber-50 text-amber-950',
          ].join(' ')}
        >
          <div className="font-semibold">
            {networkHasSearchPlanFoundation
              ? (isRu ? 'Сеть готова для поискового контент-плана' : 'The network is ready for a search-driven content plan')
              : (isRu ? 'План пока строится не на полном наборе данных' : 'The plan is not yet using the full data set')}
          </div>
          <div
            className={[
              'mt-1 leading-6',
              networkHasSearchPlanFoundation ? 'text-emerald-900/90' : 'text-amber-900/90',
            ].join(' ')}
          >
            {networkHasSearchPlanFoundation
              ? (isRu
                ? `Есть ${mapLinksCount} ссылок на карты и ${seoKeywordsCount} SEO-ключей. Можно строить план по спросу; меню, товары или услуги добавят темам коммерческую конкретику.`
                : `There are ${mapLinksCount} map listings and ${seoKeywordsCount} SEO keywords. You can build demand-driven posts now; menu items, products, or services will make topics more commercial.`)
              : (isRu
                ? 'Сейчас контент-план опирается в основном на аудит и сезонные поводы. Чтобы получить темы по реальному спросу, добавьте карту и услуги.'
                : 'Right now the plan relies mostly on audit signals and seasonal prompts. Add a map listing and services to ground it in real demand.')}
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {missingInputs.includes('map_links') ? (
              <span className="rounded-full border border-amber-300 bg-white/80 px-3 py-1 text-xs font-medium text-amber-800">
                {isRu ? 'Нет ссылки на карту' : 'No map listing yet'}
              </span>
            ) : null}
            {missingInputs.includes('services') ? (
              <span
                className={[
                  'rounded-full border bg-white/80 px-3 py-1 text-xs font-medium',
                  networkHasSearchPlanFoundation
                    ? 'border-emerald-300 text-emerald-800'
                    : 'border-amber-300 text-amber-800',
                ].join(' ')}
              >
                {isNetworkContext
                  ? (isRu ? 'Нет меню, товаров или услуг' : 'No menu, products, or services yet')
                  : (isRu ? 'Нет услуг в карточке' : 'No services yet')}
              </span>
            ) : null}
            {missingInputs.includes('seo_keywords') ? (
              <span className="rounded-full border border-amber-300 bg-white/80 px-3 py-1 text-xs font-medium text-amber-800">
                {isRu ? 'Нет SEO-ключей по реальному спросу' : 'No grounded SEO keywords yet'}
              </span>
            ) : null}
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            {missingInputs.includes('map_links') ? (
              <Button
                type="button"
                variant="outline"
                className="border-amber-300 bg-white text-amber-900 hover:bg-amber-100"
                onClick={() => navigate('/dashboard/profile')}
              >
                {isRu ? 'Добавить ссылку на карту' : 'Add map link'}
              </Button>
            ) : null}
            {missingInputs.includes('services') ? (
              <Button
                type="button"
                variant="outline"
                className={[
                  'bg-white',
                  networkHasSearchPlanFoundation
                    ? 'border-emerald-300 text-emerald-900 hover:bg-emerald-100'
                    : 'border-amber-300 text-amber-900 hover:bg-amber-100',
                ].join(' ')}
                onClick={() => navigate('/dashboard/card?tab=services')}
              >
                {isNetworkContext
                  ? (isRu ? 'Добавить меню/услуги' : 'Add menu/services')
                  : (isRu ? 'Добавить услуги' : 'Add services')}
              </Button>
            ) : null}
          </div>
        </div>
      ) : null}

      {currentPlan?.items?.length ? (
        <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-5 py-4 text-sm text-emerald-950">
          <div className="font-semibold">
            {isRu ? 'План уже создан' : 'A plan already exists'}
          </div>
          <div className="mt-1 leading-6 text-emerald-900/90">
            {isRu
              ? `Сейчас активен план «${currentPlan.title || 'Контент-план'}»: ${planOperationalSummary.total} тем, ${planOperationalSummary.readyToPublish} текстов готово, ${planOperationalSummary.needsDraft} без текста. Работать с ним нужно во вкладке «Готовая очередь по плану».`
              : `The active plan is "${currentPlan.title || 'Content plan'}": ${planOperationalSummary.total} topics, ${planOperationalSummary.readyToPublish} drafts ready, ${planOperationalSummary.needsDraft} without text. Work with it in the Plan queue tab.`}
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            <Button type="button" size="sm" onClick={() => setActiveZone('queue')}>
              {isRu ? 'Перейти в готовую очередь' : 'Open plan queue'}
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="bg-white/80"
              onClick={() => {
                setShowRecentPlans(true);
              }}
            >
              {isRu ? `Показать старые планы · ${plans.length}` : `Show old plans · ${plans.length}`}
            </Button>
          </div>
        </div>
      ) : null}

      {showRecentPlans && plans.length > 0 ? (
        <div className="space-y-3 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm leading-6 text-amber-900">
            {isRu
              ? 'Здесь можно открыть любой старый план, сравнить его с текущим по счётчикам, отредактировать темы или удалить лишнее. Детали открытого плана появятся во вкладке «Готовая очередь по плану».'
              : 'Here you can open any old plan, compare it by counters, edit topics, or delete what is not needed. The selected plan details appear in the Plan queue tab.'}
          </div>
          <div className="flex flex-wrap gap-2">
            {availablePlanTargets.map((target) => (
              <button
                key={target.key}
                type="button"
                onClick={() => setSelectedPlanTargetKey(target.key)}
                className={[
                  'rounded-full border px-3 py-1.5 text-sm transition-colors',
                  selectedPlanTargetKey === target.key
                    ? 'border-indigo-300 bg-indigo-50 text-indigo-800'
                    : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50',
                ].join(' ')}
              >
                {target.label}
              </button>
            ))}
          </div>
          <div className="grid gap-3 lg:grid-cols-2">
            {visiblePlans.map((plan, index) => {
              const isActivePlan = currentPlan?.id === plan.id;
              const planTitle = plan.title || `${_scopeChipLabel(plan.scope_type, isRu)} · ${_planTargetLabel(plan, isRu)} · ${plan.period_days} ${isRu ? 'дней' : 'days'}`;
              return (
                <div
                  key={plan.id}
                  className={[
                    'rounded-2xl border bg-white px-4 py-4 shadow-sm',
                    isActivePlan ? 'border-indigo-300 ring-2 ring-indigo-100' : 'border-slate-200',
                  ].join(' ')}
                >
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <button type="button" className="min-w-0 text-left" onClick={() => { void openPlan(plan.id); }}>
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-600">
                          {index === 0 ? (isRu ? 'Последний' : 'Latest') : `${isRu ? 'План' : 'Plan'} ${plans.length - index}`}
                        </span>
                        {isActivePlan ? (
                          <span className="rounded-full bg-indigo-50 px-2.5 py-1 text-xs font-medium text-indigo-800">
                            {isRu ? 'Открыт сейчас' : 'Open now'}
                          </span>
                        ) : null}
                      </div>
                      <div className="mt-2 text-sm font-semibold leading-5 text-slate-950">
                        {planTitle}
                      </div>
                      <div className="mt-1 text-xs leading-5 text-slate-500">
                        {_planTargetLabel(plan, isRu)} · {_formatPlanItemDate(plan.period_start || plan.created_at, isRu)}
                        {plan.period_end ? ` - ${_formatPlanItemDate(plan.period_end, isRu)}` : ''}
                      </div>
                    </button>
                    <div className="flex shrink-0 flex-wrap gap-2">
                      <Button
                        type="button"
                        size="sm"
                        variant={isActivePlan ? 'default' : 'outline'}
                        onClick={() => { void openPlan(plan.id); }}
                      >
                        {isRu ? 'Открыть' : 'Open'}
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        className="border-red-200 text-red-700 hover:bg-red-50"
                        onClick={() => { void deletePlan(plan.id); }}
                      >
                        <Trash2 className="mr-1.5 h-3.5 w-3.5" />
                        {isRu ? 'Удалить' : 'Delete'}
                      </Button>
                    </div>
                  </div>
                  <div className="mt-4 grid grid-cols-5 gap-2 text-center text-xs text-slate-500">
                    <div className="rounded-xl bg-slate-50 px-2 py-2">
                      <div className="text-sm font-semibold text-slate-950">{Number(plan.items_count || 0)}</div>
                      <div>{isRu ? 'тем' : 'topics'}</div>
                    </div>
                    <div className="rounded-xl bg-amber-50 px-2 py-2">
                      <div className="text-sm font-semibold text-amber-900">{Number(plan.needs_draft_count || 0)}</div>
                      <div>{isRu ? 'без текста' : 'no draft'}</div>
                    </div>
                    <div className="rounded-xl bg-emerald-50 px-2 py-2">
                      <div className="text-sm font-semibold text-emerald-900">{Number(plan.ready_count || 0)}</div>
                      <div>{isRu ? 'готово' : 'ready'}</div>
                    </div>
                    <div className="rounded-xl bg-blue-50 px-2 py-2">
                      <div className="text-sm font-semibold text-blue-900">{Number(plan.news_count || 0)}</div>
                      <div>{isRu ? 'новостей' : 'news'}</div>
                    </div>
                    <div className="rounded-xl bg-slate-50 px-2 py-2">
                      <div className="text-sm font-semibold text-slate-950">{Number(plan.skipped_count || 0)}</div>
                      <div>{isRu ? 'пропущено' : 'skipped'}</div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      ) : null}

      <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="mb-4">
            <div className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-500">
              {isRu ? 'Что сделать сейчас' : 'What to do now'}
            </div>
            <div className="mt-1 text-lg font-semibold text-slate-950">
              {currentPlan?.items?.length
                ? (isRu ? 'У вас уже есть рабочий план' : 'You already have a working plan')
                : (isRu ? 'Соберите первый план публикаций' : 'Build the first publication plan')}
            </div>
            <div className="mt-1 text-sm leading-6 text-slate-600">
              {isRu
                ? (currentPlan?.items?.length
                  ? 'Новый план создавать не нужно, если вы просто хотите найти тему, дописать текст или создать публикацию. Для этого откройте очередь.'
                  : 'Создайте один план. Источники, плотность и тонкие настройки спрятаны, чтобы экран не начинался с перегруза.')
                : (currentPlan?.items?.length
                  ? 'You do not need a new plan if you only want to find a topic, edit a draft, or create a publication. Open the queue instead.'
                  : 'Create one plan. Sources, density, and detailed controls are tucked away to reduce first-screen noise.')}
            </div>
          </div>
          <div className="grid gap-4 md:grid-cols-3">
            <div className="space-y-2">
              <div className="text-sm font-semibold text-slate-700">{isRu ? 'Куда строить план' : 'Scope'}</div>
              <Select value={selectedScopeKey} onValueChange={setSelectedScopeKey}>
                <SelectTrigger className="rounded-xl border-slate-200">
                  <SelectValue placeholder={isRu ? 'Выберите точку или сеть' : 'Select scope'} />
                </SelectTrigger>
                <SelectContent>
                  {scopeOptions.map((item) => {
                    const key = `${item.scope_type}:${item.scope_target_id}`;
                    const labelPrefix = item.is_parent
                      ? (isRu ? 'Материнская точка' : 'Parent network')
                      : item.scope_type === 'network_location'
                        ? (isRu ? 'Точка сети' : 'Network location')
                        : (isRu ? 'Текущий бизнес' : 'Current business');
                    return (
                      <SelectItem key={key} value={key}>
                        {labelPrefix}: {item.label}
                      </SelectItem>
                    );
                  })}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <div className="text-sm font-semibold text-slate-700">{isRu ? 'Горизонт планирования' : 'Planning horizon'}</div>
              <div className="grid grid-cols-3 gap-2">
                {PERIOD_OPTIONS.map((period) => {
                  const allowed = allowedHorizons.includes(period);
                  return (
                    <button
                      key={period}
                      type="button"
                      disabled={!allowed}
                      onClick={() => allowed && setSelectedPeriod(String(period))}
                      className={[
                        'rounded-xl border px-3 py-2 text-sm font-medium transition-colors',
                        selectedPeriod === String(period) && allowed
                          ? 'border-indigo-300 bg-indigo-50 text-indigo-800'
                          : 'border-slate-200 bg-white text-slate-700',
                        !allowed ? 'cursor-not-allowed opacity-60' : 'hover:bg-slate-50',
                      ].join(' ')}
                    >
                      <div className="flex items-center justify-center gap-1">
                        {!allowed ? <Lock className="h-3.5 w-3.5" /> : null}
                        {period}
                      </div>
                    </button>
                  );
                })}
              </div>
              {!allowedHorizons.includes(60) || !allowedHorizons.includes(90) ? (
                <div className="text-xs text-amber-700">
                  {isRu
                    ? 'Планы на 60 и 90 дней доступны на тарифах 25k и Elite.'
                    : '60 and 90 day plans are available on 25k and Elite tiers.'}
                </div>
              ) : null}
            </div>

            <div className="space-y-2">
              <div className="flex items-center gap-2 text-sm font-semibold text-slate-700">
                <Globe className="h-4 w-4 text-slate-500" />
                {isRu ? 'Язык публикаций' : 'Publication language'}
              </div>
              <Select value={contentLanguage} onValueChange={(value) => setContentLanguage(_normalizeContentLanguage(value))}>
                <SelectTrigger className="rounded-xl border-slate-200">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {CONTENT_LANGUAGE_OPTIONS.map((item) => (
                    <SelectItem key={item.value} value={item.value}>
                      {item.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <div className="text-xs text-slate-500">
                {isRu
                  ? 'Новые черновики из плана будут генерироваться на этом языке.'
                  : 'New drafts from the plan will use this language.'}
              </div>
            </div>

            {showPlanSetupDetails ? (
              <>
                <div className="space-y-2">
                  <div className="text-sm font-semibold text-slate-700">{isRu ? 'Плотность' : 'Density'}</div>
                  <Select value={selectedDensity} onValueChange={setSelectedDensity}>
                    <SelectTrigger className="rounded-xl border-slate-200">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {DENSITY_OPTIONS.map((item) => (
                        <SelectItem key={item.value} value={item.value}>
                          {isRu ? item.labelRu : item.labelEn}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <div className="text-sm font-semibold text-slate-700">{isRu ? 'Что использовать' : 'Use signals from'}</div>
                  <div className="flex flex-wrap gap-2">
                    {CONTENT_MIX_OPTIONS.map((item) => (
                      <button
                        key={item.key}
                        type="button"
                        onClick={() => toggleMix(item.key)}
                        className={[
                          'rounded-full border px-3 py-1.5 text-sm transition-colors',
                          contentMix[item.key]
                            ? 'border-emerald-300 bg-emerald-50 text-emerald-800'
                            : 'border-slate-200 bg-white text-slate-600',
                        ].join(' ')}
                      >
                        {isRu ? item.labelRu : item.labelEn}
                      </button>
                    ))}
                  </div>
                </div>
              </>
            ) : null}
          </div>

          <div className="mt-5 flex flex-wrap items-center gap-3">
            <Button onClick={() => { void generatePlan(); }} disabled={generating || loading || !selectedScopeOption}>
              <Sparkles className="mr-2 h-4 w-4" />
              {generating
                ? (isRu ? 'Собираем план...' : 'Building plan...')
                : currentPlan?.items?.length
                  ? (isRu ? 'Создать новый план' : 'Create new plan')
                  : (isRu ? 'Собрать план' : 'Build plan')}
            </Button>
            <Button variant="outline" onClick={() => { void loadContext(); void loadPlans(); }} disabled={loading}>
              <Wand2 className="mr-2 h-4 w-4" />
              {isRu ? 'Обновить контекст' : 'Refresh context'}
            </Button>
            <button
              type="button"
              onClick={() => setShowPlanSetupDetails((prev) => !prev)}
              className="rounded-full border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50"
            >
              {showPlanSetupDetails
                ? (isRu ? 'Скрыть настройки' : 'Hide settings')
                : (isRu ? 'Настроить источники' : 'Tune sources')}
            </button>
          </div>

          {error ? (
            <div className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          ) : null}
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-500">
                {isRu ? 'Качество данных' : 'Data quality'}
              </div>
              <div className="mt-1 text-lg font-semibold text-slate-950">
                {readiness?.is_grounded_for_search || networkHasSearchPlanFoundation
                  ? (isRu ? 'Данных достаточно для плана' : 'Enough data for planning')
                  : (isRu ? 'Плану не хватает источников' : 'The plan needs more inputs')}
              </div>
              {networkHasSearchPlanFoundation ? (
                <div className="mt-1 text-sm leading-6 text-slate-600">
                  {isRu
                    ? 'Для сети уже есть поисковый фундамент. Услуги и товары нужны как следующий слой конкретики.'
                    : 'The network already has a search foundation. Services and products are the next layer of specificity.'}
                </div>
              ) : null}
            </div>
            <button
              type="button"
              onClick={() => setShowContextDetails((prev) => !prev)}
              className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 transition-colors hover:bg-slate-50"
            >
              {showContextDetails ? (isRu ? 'Скрыть' : 'Hide') : (isRu ? 'Подробнее' : 'Details')}
            </button>
          </div>
          <div className="mt-4 grid grid-cols-3 gap-2 text-sm text-slate-700">
            <div className="rounded-2xl bg-slate-50 px-3 py-3">
              <div className="text-lg font-semibold text-slate-950">{mapLinksCount}</div>
              <div className="text-xs text-slate-500">{isNetworkContext ? (isRu ? 'ссылок на карты' : 'map links') : (isRu ? 'карты' : 'maps')}</div>
            </div>
            <div className="rounded-2xl bg-slate-50 px-3 py-3">
              <div className="text-lg font-semibold text-slate-950">{servicesCount}</div>
              <div className="text-xs text-slate-500">{isNetworkContext ? (isRu ? 'меню/услуг' : 'menu/services') : (isRu ? 'услуг' : 'services')}</div>
            </div>
            <div className="rounded-2xl bg-slate-50 px-3 py-3">
              <div className="text-lg font-semibold text-slate-950">{seoKeywordsCount}</div>
              <div className="text-xs text-slate-500">{isRu ? 'SEO' : 'SEO'}</div>
            </div>
          </div>
          {showContextDetails ? (
          <div className="mt-4 space-y-3 text-sm text-slate-700">
            {isNetworkContext ? (
              <div>
                <div className="font-semibold text-slate-900">{isRu ? 'Режим сети' : 'Network mode'}</div>
                <div>
                  {context?.scope?.network?.has_parent_scope
                    ? `${isRu ? 'Точек в сети' : 'Locations in network'}: ${networkLocationsCount}`
                    : (isRu ? 'План строится по текущему бизнесу.' : 'Planning uses the current business.')}
                </div>
              </div>
            ) : null}
            <div>
              <div className="font-semibold text-slate-900">{isRu ? 'Ссылки на карты' : 'Map listings'}</div>
              <div>{mapLinksCount}</div>
            </div>
            <div>
              <div className="font-semibold text-slate-900">{isNetworkContext ? (isRu ? 'Меню, товары или услуги' : 'Menu, products, or services') : (isRu ? 'Услуги' : 'Services')}</div>
              <div>{servicesCount}</div>
            </div>
            <div>
              <div className="font-semibold text-slate-900">{isRu ? 'SEO-ключи' : 'SEO keywords'}</div>
              <div>{seoKeywordsCount}</div>
            </div>
            <div>
              <div className="font-semibold text-slate-900">{isRu ? 'Продажи' : 'Sales signals'}</div>
              <div>{context?.sales_signals?.length || 0}</div>
            </div>
            <div>
              <div className="font-semibold text-slate-900">{isRu ? 'Сигналы аудита' : 'Audit signals'}</div>
              <div>{context?.audit_signals?.length || 0}</div>
            </div>
            <div>
              <div className="font-semibold text-slate-900">{isRu ? 'Последние новости' : 'Recent news'}</div>
              <div>{context?.recent_news?.length || 0}</div>
            </div>
          </div>
          ) : null}
        </div>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex items-center justify-between gap-4">
          <div>
            <div className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-500">
              {isRu ? 'Качество плана' : 'Plan quality'}
            </div>
            <div className="mt-1 text-lg font-semibold text-slate-950">
              {isRu ? 'Что система уже поняла по работе с темами' : 'What the system learned from topic work'}
            </div>
          </div>
          <button
            type="button"
            onClick={() => setShowLearningDetails((prev) => !prev)}
            className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 transition-colors hover:bg-slate-50"
          >
            {metricsLoading
              ? (isRu ? 'Обновляем...' : 'Refreshing...')
              : showLearningDetails
                ? (isRu ? 'Скрыть метрики' : 'Hide metrics')
                : `${isRu ? 'Показать метрики' : 'Show metrics'} · ${learningMetrics?.window_days || 30} ${isRu ? 'дней' : 'days'}`}
          </button>
        </div>
        {operatorQualityInsights.length > 0 ? (
          <div className="mt-4 grid gap-3 lg:grid-cols-2">
            {operatorQualityInsights.map((item) => (
              <div
                key={item.key}
                className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm leading-6 text-slate-700"
              >
                {isRu ? item.textRu : item.textEn}
              </div>
            ))}
          </div>
        ) : (
          <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm leading-6 text-slate-600">
            {isRu
              ? 'Пока мало истории, чтобы делать выводы. После публикаций и правок здесь появятся подсказки по качеству тем.'
              : 'There is not enough history yet. After edits and publications, quality guidance will appear here.'}
          </div>
        )}
        {showLearningDetails ? (
          <>
        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-5">
          <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
            <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">{isRu ? 'Сгенерировано' : 'Generated'}</div>
            <div className="mt-2 text-2xl font-semibold text-slate-950">{learningMetrics?.summary?.generated_total || 0}</div>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
            <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">{isRu ? 'Принято' : 'Accepted'}</div>
            <div className="mt-2 text-2xl font-semibold text-slate-950">{learningMetrics?.summary?.accepted_total || 0}</div>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
            <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">{isRu ? 'Правили перед публикацией' : 'Edited before accept'}</div>
            <div className="mt-2 text-2xl font-semibold text-slate-950">{learningMetrics?.summary?.accepted_edited_total || 0}</div>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
            <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">{isRu ? 'Пропущено' : 'Skipped'}</div>
            <div className="mt-2 text-2xl font-semibold text-slate-950">{learningMetrics?.summary?.skipped_total || 0}</div>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
            <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">{isRu ? 'Правки до принятия' : 'Edited before accept'}</div>
            <div className="mt-2 text-2xl font-semibold text-slate-950">{Number(learningMetrics?.summary?.edited_before_accept_pct || 0).toFixed(0)}%</div>
          </div>
        </div>
        <div className="mt-3 grid gap-3 md:grid-cols-2">
          <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3">
            <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">{isRu ? 'Небольшие правки' : 'Minor edits'}</div>
            <div className="mt-2 text-xl font-semibold text-slate-950">{learningMetrics?.summary?.minor_edit_total || 0}</div>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3">
            <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">{isRu ? 'Смысловые переписывания' : 'Major rewrites'}</div>
            <div className="mt-2 text-xl font-semibold text-slate-950">{learningMetrics?.summary?.major_rewrite_total || 0}</div>
          </div>
        </div>
        {learningMetrics?.quality_insights && learningMetrics.quality_insights.length > 0 ? (
          <div className="mt-4 space-y-2">
            {learningMetrics.quality_insights.map((item) => (
              <div
                key={`${item.kind}:${item.text_ru || item.text_en}`}
                className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700"
              >
                {isRu ? item.text_ru : item.text_en}
              </div>
            ))}
          </div>
        ) : null}
        {learningMetrics?.items && learningMetrics.items.length > 0 ? (
          <div className="mt-4 flex flex-wrap gap-2">
            {learningMetrics.items.map((item) => (
              <div
                key={item.capability}
                className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-700"
              >
                {_learningCapabilityLabel(item.capability, isRu)} · {isRu ? 'принято' : 'accepted'} {item.accepted_total} · {isRu ? 'сгенерировано' : 'generated'} {item.generated_total}
              </div>
            ))}
          </div>
        ) : null}
        {(learningMetrics?.source_kind_breakdown && learningMetrics.source_kind_breakdown.length > 0)
          || (learningMetrics?.content_type_breakdown && learningMetrics.content_type_breakdown.length > 0)
          || (learningMetrics?.location_breakdown && learningMetrics.location_breakdown.length > 0) ? (
          <div className="mt-4 grid gap-4 xl:grid-cols-3">
            <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
              <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                {isRu ? 'Чаще правят по сигналу' : 'Most edited by signal'}
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                {(learningMetrics?.source_kind_breakdown || []).slice(0, 5).map((item) => (
                  <div
                    key={item.key}
                    className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-700"
                  >
                    {_sourceKindLabel(item.key, isRu)} · {Number(item.edited_before_accept_pct || 0).toFixed(0)}%
                  </div>
                ))}
              </div>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
              <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                {isRu ? 'Чаще правят по типу темы' : 'Most edited by content type'}
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                {(learningMetrics?.content_type_breakdown || []).slice(0, 5).map((item) => (
                  <div
                    key={item.key}
                    className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-700"
                  >
                    {_contentTypeLabel(item.key, isRu)} · {Number(item.edited_before_accept_pct || 0).toFixed(0)}%
                  </div>
                ))}
              </div>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
              <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                {isRu ? 'Чаще правят по точке' : 'Most edited by location'}
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                {(learningMetrics?.location_breakdown || []).slice(0, 5).map((item) => (
                  <div
                    key={item.key}
                    className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-700"
                  >
                    {String(item.label || item.key || (isRu ? 'Точка' : 'Location'))} · {Number(item.edited_before_accept_pct || 0).toFixed(0)}%
                  </div>
                ))}
              </div>
            </div>
          </div>
        ) : null}
        {learningMetrics?.network_quality && learningMetrics.network_quality.length > 0 ? (
          <div className="mt-4 rounded-2xl border border-slate-200 bg-white px-4 py-4">
            <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                  {isRu ? 'Качество по точкам' : 'Quality by location'}
                </div>
                <div className="mt-1 text-sm text-slate-600">
                  {isRu
                    ? 'Показывает, где контент-план чаще требует вмешательства: правки, пропуски, черновики без публикации.'
                    : 'Shows where the content plan needs more operator attention: edits, skips, drafts without publishing.'}
                </div>
              </div>
            </div>
            <div className="mt-4 grid gap-3 lg:grid-cols-3">
              {learningMetrics.network_quality.slice(0, 3).map((item) => (
                <div key={item.key} className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="text-sm font-semibold text-slate-950">
                        {String(item.label || item.key || (isRu ? 'Точка' : 'Location'))}
                      </div>
                      <div className="mt-1 text-xs text-slate-500">
                        {isRu ? 'Индекс риска' : 'Risk score'} · {Number(item.risk_score || 0).toFixed(0)}
                      </div>
                    </div>
                    <span className={[
                      'rounded-full px-2.5 py-1 text-xs font-medium',
                      Number(item.risk_score || 0) >= 60
                        ? 'bg-red-100 text-red-700'
                        : Number(item.risk_score || 0) >= 30
                          ? 'bg-amber-100 text-amber-800'
                          : 'bg-emerald-100 text-emerald-800',
                    ].join(' ')}
                    >
                      {Number(item.risk_score || 0) >= 60
                        ? (isRu ? 'Высокий' : 'High')
                        : Number(item.risk_score || 0) >= 30
                          ? (isRu ? 'Средний' : 'Medium')
                          : (isRu ? 'Норма' : 'Stable')}
                    </span>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2 text-xs">
                    <span className="rounded-full bg-white px-2.5 py-1 text-slate-700">
                      {isRu ? 'Опубликовано' : 'Published'} · {item.accepted_total}
                    </span>
                    <span className="rounded-full bg-white px-2.5 py-1 text-slate-700">
                      {isRu ? 'Правки' : 'Edits'} · {Number(item.edited_before_accept_pct || 0).toFixed(0)}%
                    </span>
                    <span className="rounded-full bg-white px-2.5 py-1 text-slate-700">
                      {isRu ? 'Пропуски' : 'Skipped'} · {item.skipped_total}
                    </span>
                    <span className="rounded-full bg-white px-2.5 py-1 text-slate-700">
                      {isRu ? 'Переписывания' : 'Rewrites'} · {item.major_rewrite_total}
                    </span>
                  </div>
                  {item.reasons && item.reasons.length > 0 ? (
                    <div className="mt-3 text-xs leading-5 text-slate-500">
                      {item.reasons.slice(0, 2).map((reason) => _networkQualityReasonLabel(reason, isRu)).join(' · ')}
                    </div>
                  ) : null}
                </div>
              ))}
            </div>
          </div>
        ) : null}
          </>
        ) : null}
      </div>

      </div>

      <div className={activeZone === 'queue' ? 'rounded-2xl border border-slate-200 bg-white p-5 shadow-sm' : 'hidden'}>
        <div className="flex items-center justify-between gap-4">
          <div>
            <div className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-500">
              {isRu ? 'Готовая очередь по плану' : 'Plan queue'}
            </div>
            <div className="mt-1 text-lg font-semibold text-slate-950">
              {currentPlan?.title || (isRu ? 'План ещё не собран' : 'No plan yet')}
            </div>
            <div className="mt-2 inline-flex rounded-full bg-blue-50 px-2.5 py-1 text-xs font-medium text-blue-700 ring-1 ring-blue-100">
              {isRu
                ? 'Каналы: карты + соцсети, публикация только после подтверждения'
                : 'Channels: maps + social, publish only after approval'}
            </div>
            <div className="mt-1 text-sm leading-6 text-slate-600">
              {currentPlan?.items?.length
                ? (isRu
                  ? 'Здесь рабочий список тем из выбранного плана: найти тему, открыть текст, подготовить публикации.'
                  : 'This is the working list from the selected plan: find a topic, open a draft, prepare publications.')
                : (isRu
                  ? 'Очередь появится после создания первого плана.'
                  : 'The queue appears after the first plan is created.')}
            </div>
          </div>
          <div className="flex shrink-0 flex-wrap items-center justify-end gap-2">
            <div className="rounded-full bg-slate-100 px-3 py-1.5 text-sm font-medium text-slate-700">
              {plans.length > 0 ? `${isRu ? 'Планов' : 'Plans'} · ${plans.length}` : `${isRu ? 'Планов' : 'Plans'} · 0`}
            </div>
            <button
              type="button"
              onClick={() => {
                setShowRecentPlans(true);
                setActiveZone('plan');
              }}
              className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 transition-colors hover:bg-slate-50"
            >
              {isRu ? 'Управлять планами' : 'Manage plans'}
            </button>
          </div>
        </div>

        {!currentPlan?.items?.length ? (
          <div className="mt-6 rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-6 py-8 text-sm leading-6 text-slate-600">
            <div className="text-base font-semibold text-slate-950">
              {isRu ? 'Очередь пока пустая' : 'The queue is empty'}
            </div>
            <div className="mt-1">
              {isRu
                ? 'Сначала создайте план во вкладке «План». После этого здесь появятся темы, тексты и действия для публикаций.'
                : 'Create a plan in the Plan tab first. Then topics, drafts, and publishing actions will appear here.'}
            </div>
            <div className="mt-4">
              <Button type="button" onClick={() => setActiveZone('plan')}>
                {isRu ? 'Перейти к созданию плана' : 'Go to plan creation'}
              </Button>
            </div>
          </div>
        ) : null}

        {currentPlan?.items && currentPlan.items.length > 0 ? (
          <div className="mt-6 space-y-4">
            <div className="rounded-[28px] border border-slate-200 bg-slate-950 p-5 text-white shadow-sm">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div>
                  <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
                    {isRu ? 'Что сделать дальше' : 'Next best action'}
                  </div>
                  <div className="mt-2 text-xl font-semibold">
                    {visibleSocialNeedsReview.length > 0
                      ? (isRu ? 'Проверьте готовые публикации' : 'Review prepared publications')
                      : visibleSocialCanQueue.length > 0
                        ? (isRu ? 'Поставьте утверждённые посты в расписание' : 'Queue approved posts on schedule')
                        : visibleSocialNeedsSupervised.length > 0
                          ? (isRu ? 'Откройте контролируемое размещение' : 'Open supervised placement')
                          : visibleSocialNeedsManual.length > 0
                            ? (isRu ? 'Закройте ручные публикации' : 'Finish manual publications')
                            : Number(socialSummary?.scheduled || 0) > 0
                              ? (isRu ? 'Расписание ждёт исполнения' : 'Schedule is waiting for execution')
                              : Number(socialSummary?.published || 0) > 0
                                ? (isRu ? 'Соберите результат и улучшите план' : 'Collect results and improve the plan')
                                : planOperationalSummary.needsDraft > 0
                                  ? (isRu ? 'В плане есть темы без текста' : 'Some plan topics need text')
                                  : planOperationalSummary.readyToPublish > 0
                                    ? (isRu ? 'Теперь можно создать публикации' : 'Now create publications')
                                    : (isRu ? 'План под контролем' : 'Plan is under control')}
                  </div>
                  <div className="mt-2 max-w-3xl text-sm leading-6 text-slate-300">
                    {visibleSocialNeedsReview.length > 0
                      ? (isRu
                        ? 'Главный шаг сейчас — предпросмотр и подтверждение. Текст можно поправить, а наружу ничего не отправится до отдельной постановки в расписание.'
                        : 'The main step now is preview and approval. You can edit copy; nothing external is sent until a separate queue step.')
                      : visibleSocialCanQueue.length > 0
                        ? (isRu
                          ? 'Подтверждение уже есть. Следующий безопасный шаг — поставить посты в расписание, после чего исполнитель обработает их только по дате и готовности каналов.'
                          : 'Approval is done. The next safe step is queueing posts, then the worker processes them only by date and channel readiness.')
                        : visibleSocialNeedsSupervised.length > 0
                          ? (isRu
                            ? 'Яндекс/2ГИС ждут контролируемое размещение: LocalOS подготовит текст и задачу, финальный клик остаётся за человеком.'
                            : 'Yandex/2GIS await supervised placement: LocalOS prepares copy and a task, while the final click stays human-controlled.')
                          : visibleSocialNeedsManual.length > 0
                            ? (isRu
                              ? 'Есть каналы без API или browser-use. Скопируйте готовый текст, разместите вручную и отметьте результат в LocalOS.'
                              : 'Some channels have no API or browser-use. Copy the prepared text, publish manually, and mark the result in LocalOS.')
                            : Number(socialSummary?.published || 0) > 0
                              ? (isRu
                                ? 'Публикации уже вышли. Теперь отметьте заявки/обращения и пересчитайте рекомендации следующего плана.'
                                : 'Posts are already published. Record leads/inquiries and refresh next-plan recommendations.')
                              : (isRu
                                ? 'Это не создаёт новый план. Здесь вы работаете с уже выбранным планом: дописываете тексты, находите нужную тему и создаёте публикации.'
                                : 'This does not create a new plan. Here you work with the selected plan: fill text, find topics, and create publications.')}
                  </div>
                  {Number(socialSummary?.total || 0) > 0 ? (
                    <div className="mt-4 flex flex-col gap-2 sm:flex-row sm:items-center">
                      <Button
                        type="button"
                        size="sm"
                        onClick={runSocialPlanNextStep}
                        disabled={Boolean(bulkBusyAction) || Boolean(socialBusyAction) || Boolean(socialPlanNextStep.disabled)}
                        className="shrink-0 bg-white text-slate-950 hover:bg-slate-100"
                      >
                        {bulkBusyAction || socialBusyAction
                          ? (isRu ? 'Выполняем...' : 'Working...')
                          : `${isRu ? socialPlanNextStep.ctaRu : socialPlanNextStep.ctaEn} · ${socialPlanNextStep.count}`}
                      </Button>
                      <div className="text-xs leading-5 text-slate-300">
                        {isRu
                          ? 'Кнопка ведёт к безопасному шагу: предпросмотр, подтверждение, расписание, контролируемое размещение или сбор результата.'
                          : 'This button opens the safe next step: preview, approval, queueing, supervised placement, or result collection.'}
                      </div>
                    </div>
                  ) : null}
                  {Number(socialSummary?.total || 0) === 0 ? (
                    <div className="mt-4 rounded-2xl border border-white/10 bg-white/10 px-4 py-4">
                      <div className="text-sm font-semibold text-white">
                        {isRu ? 'Первый запуск publishing loop' : 'First publishing-loop launch'}
                      </div>
                      <div className="mt-2 grid gap-2 text-xs leading-5 text-slate-300 md:grid-cols-4">
                        <div className="rounded-xl bg-white/10 px-3 py-2">
                          <div className="font-semibold text-white">{isRu ? '1. Подготовить каналы' : '1. Prepare channels'}</div>
                          <div>{isRu ? 'Создать черновики для карт и соцсетей из тем плана.' : 'Create channel drafts from plan topics.'}</div>
                        </div>
                        <div className="rounded-xl bg-white/10 px-3 py-2">
                          <div className="font-semibold text-white">{isRu ? '2. Проверить тексты' : '2. Review copy'}</div>
                          <div>{isRu ? 'Открыть предпросмотр, поправить общий текст и версии под каналы.' : 'Open preview and edit base plus platform-specific copy.'}</div>
                        </div>
                        <div className="rounded-xl bg-white/10 px-3 py-2">
                          <div className="font-semibold text-white">{isRu ? '3. Утвердить и поставить' : '3. Approve and queue'}</div>
                          <div>{isRu ? 'Подтверждение и расписание идут отдельными безопасными шагами.' : 'Approval and scheduling stay separate safe steps.'}</div>
                        </div>
                        <div className="rounded-xl bg-white/10 px-3 py-2">
                          <div className="font-semibold text-white">{isRu ? '4. Исполнить по режиму' : '4. Execute by mode'}</div>
                          <div>{isRu ? 'API-каналы пойдут через worker, Яндекс/2ГИС - через контролируемое размещение.' : 'API channels run via worker; Yandex/2GIS use supervised placement.'}</div>
                        </div>
                      </div>
                      <div className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                        <div className="text-xs leading-5 text-slate-300">
                          {isRu
                            ? 'Наружу ничего не отправится на первом шаге. Яндекс/2ГИС не нажимают финальную кнопку без человека.'
                            : 'Nothing is sent externally on the first step. Yandex/2GIS never click the final publish button without a person.'}
                        </div>
                        <Button
                          type="button"
                          size="sm"
                          onClick={() => { void prepareSuggestedSocialPosts(); }}
                          disabled={Boolean(bulkBusyAction) || Boolean(socialBusyAction) || visibleItems.length === 0}
                          className="shrink-0 bg-white text-slate-950 hover:bg-slate-100"
                        >
                          {bulkBusyAction === 'suggested-social-prepare'
                            ? (isRu ? 'Готовим...' : 'Preparing...')
                            : (isRu ? 'Подготовить первые публикации' : 'Prepare first posts')}
                        </Button>
                      </div>
                    </div>
                  ) : null}
                </div>
                <div className="grid grid-cols-3 gap-2 text-center text-xs text-slate-300 sm:min-w-[320px]">
                  <div className="rounded-2xl bg-white/10 px-3 py-3">
                    <div className="text-lg font-semibold text-white">{planOperationalSummary.needsDraft}</div>
                    <div>{isRu ? 'без текста' : 'no draft'}</div>
                  </div>
                  <div className="rounded-2xl bg-white/10 px-3 py-3">
                    <div className="text-lg font-semibold text-white">{planOperationalSummary.readyToPublish}</div>
                    <div>{isRu ? 'текст готов' : 'draft ready'}</div>
                  </div>
                  <div className="rounded-2xl bg-white/10 px-3 py-3">
                    <div className="text-lg font-semibold text-white">{planOperationalSummary.published}</div>
                    <div>{isRu ? 'новости' : 'news'}</div>
                  </div>
                </div>
              </div>
              <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                {quickActions.map((action) => (
                  <button
                    key={action.key}
                    type="button"
                    disabled={action.disabled || Boolean(bulkBusyAction) || Boolean(busyItemId)}
                    onClick={() => runQuickAction(action.key)}
                    className={[
                      'rounded-2xl border px-4 py-4 text-left transition-colors',
                      action.disabled
                        ? 'cursor-not-allowed border-white/5 bg-white/[0.03] text-slate-500 opacity-70'
                        : 'border-white/10 bg-white/10 text-white hover:bg-white/15',
                    ].join(' ')}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="text-sm font-semibold">{action.title}</div>
                      <div
                        className={[
                          'rounded-full px-2 py-0.5 text-xs',
                          action.disabled ? 'bg-white/5 text-slate-500' : 'bg-white/10 text-slate-200',
                        ].join(' ')}
                      >
                        {action.disabled ? (isRu ? 'Недоступно' : 'Locked') : action.metric}
                      </div>
                    </div>
                    <div className={['mt-2 line-clamp-2 text-xs leading-5', action.disabled ? 'text-slate-500' : 'text-slate-300'].join(' ')}>
                      {action.description}
                    </div>
                  </button>
                ))}
              </div>
            </div>
            {visibleSocialPublishedPosts.length > 0 ? (
              <div
                data-testid="social-result-collection-guide"
                className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-4 text-sm leading-6 text-emerald-900"
              >
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                  <div>
                    <div className="text-xs font-semibold uppercase tracking-[0.14em] text-emerald-700">
                      {isRu ? 'Сбор результата' : 'Result collection'}
                    </div>
                    <div className="mt-1 text-base font-semibold text-emerald-950">
                      {socialPrimaryResultCount > 0
                        ? (isRu ? 'Есть заявки или обращения' : 'Leads or inquiries recorded')
                        : (isRu ? 'Отметьте заявки и обращения после публикаций' : 'Record leads and inquiries after publishing')}
                    </div>
                    <div className="mt-1 max-w-3xl text-sm leading-6 text-emerald-800">
                      {isRu
                        ? 'LocalOS корректирует следующий план по фактам: сначала заявки и обращения, затем комментарии, репосты, клики и охваты. Изменения плана не применяются без подтверждения.'
                        : 'LocalOS adjusts the next plan from facts: leads and inquiries first, then comments, shares, clicks, and reach. Plan changes are never applied without approval.'}
                    </div>
                  </div>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={selectPublishedSocialPostsForResult}
                    disabled={visibleSocialPublishedPosts.length === 0}
                    className="shrink-0 border-emerald-300 bg-white text-emerald-900 hover:bg-emerald-100"
                  >
                    {isRu ? 'Выбрать опубликованные' : 'Select published'}
                  </Button>
                </div>
                <div className="mt-3 grid gap-2 text-xs sm:grid-cols-4">
                  <div className="rounded-xl bg-white px-3 py-2">
                    <div className="text-base font-semibold text-emerald-950">{visibleSocialPublishedPosts.length}</div>
                    <div>{isRu ? 'опубликовано' : 'published'}</div>
                  </div>
                  <div className="rounded-xl bg-white px-3 py-2">
                    <div className="text-base font-semibold text-emerald-950">{visibleSocialPublishedWithoutPrimaryResult.length}</div>
                    <div>{isRu ? 'без заявки/обращения' : 'without lead/inquiry'}</div>
                  </div>
                  <div className="rounded-xl bg-white px-3 py-2">
                    <div className="text-base font-semibold text-emerald-950">{socialPrimaryResultCount}</div>
                    <div>{isRu ? 'заявки и обращения' : 'leads and inquiries'}</div>
                  </div>
                  <div className="rounded-xl bg-white px-3 py-2">
                    <div className="text-base font-semibold text-emerald-950">{socialEarlySignalCount}</div>
                    <div>{isRu ? 'ранние сигналы' : 'early signals'}</div>
                  </div>
                </div>
                <div className="mt-3 rounded-xl bg-white px-3 py-2 text-xs leading-5 text-emerald-800">
                  {selectedSocialCanRecordResults.length > 0
                    ? (isRu
                      ? `Выбрано опубликованных постов: ${selectedSocialCanRecordResults.length}. Ниже доступны кнопки “Была заявка” и “Было обращение”.`
                      : `Published posts selected: ${selectedSocialCanRecordResults.length}. The “Record lead” and “Record inquiry” buttons are available below.`)
                    : (isRu
                      ? 'Нажмите “Выбрать опубликованные”, затем отметьте результат по выбранным публикациям.'
                      : 'Click “Select published”, then record results for the selected publications.')}
                </div>
              </div>
            ) : null}
            {isNetworkMode && itemLocationSummary.length > 1 ? (
              <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
                <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                  {isRu ? 'Распределение по точкам' : 'Distribution by location'}
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  {itemLocationSummary.map((entry) => (
                    <div
                      key={entry.label}
                      className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-700"
                    >
                      {entry.label} · {entry.count}
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
            {isNetworkMode && networkOperatingSlices.length > 0 ? (
              <details className="rounded-[28px] border border-slate-200 bg-white p-5 shadow-sm">
                <summary className="cursor-pointer list-none text-sm font-semibold text-slate-900">
                  {isRu ? 'Сетевые срезы по точкам' : 'Network slices by location'}
                </summary>
                <div className="mt-4">
                <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
                  <div>
                    <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                      {isRu ? 'Режим управления сетью' : 'Network operating mode'}
                    </div>
                    <div className="mt-1 text-lg font-semibold text-slate-950">
                      {isRu ? 'Точки, где есть работа прямо сейчас' : 'Locations that need work now'}
                    </div>
                    <div className="mt-1 max-w-3xl text-sm leading-6 text-slate-600">
                      {isRu
                        ? 'Откройте конкретную точку и неделю, чтобы не тонуть во всём плане сети сразу.'
                        : 'Open a specific location and week instead of working through the whole network plan at once.'}
                    </div>
                  </div>
                  <div className="rounded-full bg-slate-950 px-4 py-2 text-sm font-medium text-white">
                    {networkOperatingSlices.length} {isRu ? 'точек в фокусе' : 'locations in focus'}
                  </div>
                </div>
                <div className="mt-5 grid gap-3 xl:grid-cols-2">
                  {networkOperatingSlices.map((slice) => (
                    <div key={slice.key} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                        <div>
                          <div className="text-base font-semibold text-slate-950">{slice.label}</div>
                          <div className="mt-1 text-sm text-slate-600">
                            {slice.focusWeekLabel} · {isRu ? 'рабочий срез' : 'operating slice'}
                          </div>
                        </div>
                        <span className={[
                          'w-fit rounded-full px-2.5 py-1 text-xs font-medium',
                          slice.riskScore >= 60
                            ? 'bg-red-100 text-red-700'
                            : slice.riskScore >= 30
                              ? 'bg-amber-100 text-amber-800'
                              : 'bg-emerald-100 text-emerald-800',
                        ].join(' ')}
                        >
                          {_networkRiskLabel(slice.riskScore, isRu)}
                        </span>
                      </div>
                      <div className="mt-4 grid grid-cols-2 gap-2 text-xs sm:grid-cols-5">
                        <div className="rounded-xl bg-white px-3 py-2">
                          <div className="font-semibold text-slate-950">{slice.needsDraft}</div>
                          <div className="text-slate-500">{isRu ? 'без текста' : 'no draft'}</div>
                        </div>
                        <div className="rounded-xl bg-white px-3 py-2">
                          <div className="font-semibold text-slate-950">{slice.readyToPublish}</div>
                          <div className="text-slate-500">{isRu ? 'текст готов' : 'draft ready'}</div>
                        </div>
                        <div className="rounded-xl bg-white px-3 py-2">
                          <div className="font-semibold text-slate-950">{slice.published}</div>
                          <div className="text-slate-500">{isRu ? 'новости' : 'news'}</div>
                        </div>
                        <div className="rounded-xl bg-white px-3 py-2">
                          <div className="font-semibold text-slate-950">{slice.skipped}</div>
                          <div className="text-slate-500">{isRu ? 'пропуски' : 'skipped'}</div>
                        </div>
                        <div className="rounded-xl bg-white px-3 py-2">
                          <div className="font-semibold text-slate-950">{Number(slice.riskScore || 0).toFixed(0)}</div>
                          <div className="text-slate-500">{isRu ? 'риск' : 'risk'}</div>
                        </div>
                      </div>
                      <div className="mt-3 rounded-xl bg-white px-3 py-2 text-sm leading-6 text-slate-700">
                        {slice.recommendation}
                      </div>
                      {slice.reasons.length > 0 ? (
                        <div className="mt-3 flex flex-wrap gap-2 text-xs">
                          {slice.reasons.slice(0, 3).map((reason) => (
                            <span key={reason} className="rounded-full bg-white px-2.5 py-1 text-slate-600">
                              {_networkQualityReasonLabel(reason, isRu)}
                            </span>
                          ))}
                        </div>
                      ) : null}
                      <div className="mt-4 flex flex-wrap items-center gap-2">
                        <Input
                          type="date"
                          value={bulkTargetDate}
                          onChange={(event) => setBulkTargetDate(event.target.value)}
                          className="h-9 w-[158px] bg-white"
                          aria-label={isRu ? 'Дата переноса среза' : 'Slice target date'}
                        />
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={() => applyLocationWeekFocus(slice.key, slice.focusWeekKey)}
                        >
                          {isRu ? 'Открыть точку' : 'Open location'}
                        </Button>
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={() => { void runLocationWeekFocusDrafts(slice.key, slice.focusWeekKey); }}
                          disabled={Boolean(bulkBusyAction) || slice.focusWeekKey === 'all' || slice.focusWeekNeedsDraft === 0}
                        >
                          {bulkBusyAction === `focus-drafts:${slice.key}:${slice.focusWeekKey}`
                            ? (isRu ? 'Генерируем...' : 'Generating...')
                            : `${isRu ? 'Сгенерировать неделю' : 'Generate week'} · ${slice.focusWeekNeedsDraft}`}
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          onClick={() => { void runLocationWeekFocusNews(slice.key, slice.focusWeekKey); }}
                          disabled={Boolean(bulkBusyAction) || slice.focusWeekKey === 'all' || slice.focusWeekReadyToPublish === 0}
                        >
                          {bulkBusyAction === `focus-news:${slice.key}:${slice.focusWeekKey}`
                            ? (isRu ? 'Создаём...' : 'Creating...')
                            : `${isRu ? 'Создать публикации' : 'Create publications'} · ${slice.focusWeekReadyToPublish}`}
                        </Button>
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={() => { void runLocationWeekRescheduleToDate(slice.key, slice.focusWeekKey, bulkTargetDate); }}
                          disabled={Boolean(bulkBusyAction) || slice.focusWeekKey === 'all' || slice.total === 0}
                        >
                          {bulkBusyAction === `focus-reschedule-date:${slice.key}:${slice.focusWeekKey}`
                            ? (isRu ? 'Переносим...' : 'Rescheduling...')
                            : (isRu ? 'Перенести на дату' : 'Move to date')}
                        </Button>
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={() => { void runLocationWeekSkip(slice.key, slice.focusWeekKey); }}
                          disabled={Boolean(bulkBusyAction) || slice.focusWeekKey === 'all' || slice.total === 0}
                        >
                          {bulkBusyAction === `focus-skip:${slice.key}:${slice.focusWeekKey}`
                            ? (isRu ? 'Пропускаем...' : 'Skipping...')
                            : (isRu ? 'Пропустить срез' : 'Skip slice')}
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
                </div>
              </details>
            ) : null}
            <div className="flex flex-wrap gap-2">
              {viewPresets.map((preset) => (
                <button
                  key={preset.key}
                  type="button"
                  onClick={() => applyViewPreset(preset.key)}
                  className={[
                    'rounded-full border px-3 py-1.5 text-sm transition-colors',
                    selectedViewPreset === preset.key
                      ? 'border-indigo-300 bg-indigo-50 text-indigo-800'
                      : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50',
                  ].join(' ')}
                >
                  {preset.label}
                </button>
              ))}
            </div>
            {bulkNewsReview ? (
              <div className="rounded-[28px] border border-slate-900 bg-white p-5 shadow-lg">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                  <div>
                    <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                      {isRu ? 'Подтверждение публикаций' : 'Publication review'}
                    </div>
                    <div className="mt-2 text-lg font-semibold text-slate-950">
                      {isRu ? bulkNewsReview.titleRu : bulkNewsReview.titleEn}
                    </div>
                    <div className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
                      {isRu ? bulkNewsReview.descriptionRu : bulkNewsReview.descriptionEn}
                    </div>
                  </div>
                  <div className="rounded-2xl bg-slate-950 px-4 py-3 text-center text-white">
                    <div className="text-2xl font-semibold">{bulkNewsReview.items.length}</div>
                    <div className="text-xs text-slate-300">{isRu ? 'новостей' : 'news items'}</div>
                  </div>
                </div>
                {bulkNewsReview.items.filter((item) => !_inputDateValue(item.scheduled_for)).length > 0 ? (
                  <div className="mt-4 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm leading-6 text-amber-900">
                    {isRu
                      ? `${bulkNewsReview.items.filter((item) => !_inputDateValue(item.scheduled_for)).length} публикации без даты. Они будут созданы как черновики без календаря.`
                      : `${bulkNewsReview.items.filter((item) => !_inputDateValue(item.scheduled_for)).length} publications have no date. They will be created as drafts without a calendar date.`}
                  </div>
                ) : null}
                <div className="mt-4 grid gap-2">
                  {bulkNewsReview.items.slice(0, 5).map((item) => (
                    <div key={`${bulkNewsReview.key}:${item.id}`} className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                      <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
                        <div className="text-sm font-semibold text-slate-950">
                          {String(item.theme || item.goal || (isRu ? 'Без темы' : 'Untitled')).trim()}
                        </div>
                        <div className="text-xs text-slate-500">{_formatPlanItemDate(item.scheduled_for, isRu)}</div>
                      </div>
                      <div className="mt-1 text-xs text-slate-500">
                        {_itemLocationLabel(item, isRu)} · {_sourceKindLabel(item.source_kind, isRu)}
                      </div>
                    </div>
                  ))}
                  {bulkNewsReview.items.length > 5 ? (
                    <div className="rounded-2xl border border-dashed border-slate-200 bg-white px-4 py-3 text-sm text-slate-500">
                      {isRu
                        ? `И ещё ${bulkNewsReview.items.length - 5} элементов в этом массовом действии.`
                        : `And ${bulkNewsReview.items.length - 5} more items in this bulk action.`}
                    </div>
                  ) : null}
                </div>
                <div className="mt-5 flex flex-wrap gap-2">
                  <Button
                    type="button"
                    onClick={() => { void executeBulkNewsReview(); }}
                    disabled={Boolean(bulkBusyAction)}
                  >
                    {bulkBusyAction === bulkNewsReview.busyAction
                      ? (isRu ? 'Создаём новости...' : 'Creating news...')
                      : (isRu ? 'Подтвердить и создать' : 'Confirm and create')}
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => setBulkNewsReview(null)}
                    disabled={Boolean(bulkBusyAction)}
                  >
                    {isRu ? 'Отменить' : 'Cancel'}
                  </Button>
                  {bulkNewsReview.focusLocationKey && bulkNewsReview.focusWeekKey ? (
                    <Button
                      type="button"
                      variant="outline"
                      className="bg-slate-50"
                      onClick={() => {
                        applyLocationWeekFocus(bulkNewsReview.focusLocationKey || 'all', bulkNewsReview.focusWeekKey || 'all');
                      }}
                      disabled={Boolean(bulkBusyAction)}
                    >
                      {isRu ? 'Открыть срез перед созданием' : 'Open slice before creating'}
                    </Button>
                  ) : null}
                </div>
              </div>
            ) : null}
            {bulkActionReview ? (
              <div className="rounded-[28px] border border-slate-900 bg-white p-5 shadow-lg">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                  <div>
                    <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                      {isRu ? 'Подтверждение массового действия' : 'Bulk action review'}
                    </div>
                    <div className="mt-2 text-lg font-semibold text-slate-950">
                      {isRu ? bulkActionReview.titleRu : bulkActionReview.titleEn}
                    </div>
                    <div className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
                      {isRu ? bulkActionReview.descriptionRu : bulkActionReview.descriptionEn}
                    </div>
                  </div>
                  <div className="rounded-2xl bg-slate-950 px-4 py-3 text-center text-white">
                    <div className="text-2xl font-semibold">{bulkActionReview.items.length}</div>
                    <div className="text-xs text-slate-300">{isRu ? 'элементов' : 'items'}</div>
                  </div>
                </div>
                <div className="mt-4 grid gap-2">
                  {bulkActionReview.items.slice(0, 5).map((item) => (
                    <div key={`${bulkActionReview.key}:${item.id}`} className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                      <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
                        <div className="text-sm font-semibold text-slate-950">
                          {String(item.theme || item.goal || (isRu ? 'Без темы' : 'Untitled')).trim()}
                        </div>
                        <div className="text-xs text-slate-500">
                          {bulkActionReview.kind === 'reschedule' && bulkActionReview.targetDate
                            ? `${_formatPlanItemDate(item.scheduled_for, isRu)} → ${_formatPlanItemDate(bulkActionReview.targetDate, isRu)}`
                            : _formatPlanItemDate(item.scheduled_for, isRu)}
                        </div>
                      </div>
                      <div className="mt-1 text-xs text-slate-500">
                        {_itemLocationLabel(item, isRu)} · {_sourceKindLabel(item.source_kind, isRu)}
                      </div>
                    </div>
                  ))}
                  {bulkActionReview.items.length > 5 ? (
                    <div className="rounded-2xl border border-dashed border-slate-200 bg-white px-4 py-3 text-sm text-slate-500">
                      {isRu
                        ? `И ещё ${bulkActionReview.items.length - 5} элементов в этом массовом действии.`
                        : `And ${bulkActionReview.items.length - 5} more items in this bulk action.`}
                    </div>
                  ) : null}
                </div>
                <div className="mt-5 flex flex-wrap gap-2">
                  <Button
                    type="button"
                    onClick={() => { void executeBulkActionReview(); }}
                    disabled={Boolean(bulkBusyAction)}
                  >
                    {bulkBusyAction === bulkActionReview.busyAction
                      ? (isRu ? 'Выполняем...' : 'Processing...')
                      : (isRu ? bulkActionReview.confirmLabelRu : bulkActionReview.confirmLabelEn)}
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => setBulkActionReview(null)}
                    disabled={Boolean(bulkBusyAction)}
                  >
                    {isRu ? 'Отменить' : 'Cancel'}
                  </Button>
                  {bulkActionReview.focusLocationKey && bulkActionReview.focusWeekKey ? (
                    <Button
                      type="button"
                      variant="outline"
                      className="bg-slate-50"
                      onClick={() => {
                        applyLocationWeekFocus(bulkActionReview.focusLocationKey || 'all', bulkActionReview.focusWeekKey || 'all');
                      }}
                      disabled={Boolean(bulkBusyAction)}
                    >
                      {isRu ? 'Открыть срез' : 'Open slice'}
                    </Button>
                  ) : null}
                </div>
              </div>
            ) : null}
            {socialPreparePreview ? (
              <div
                data-testid="social-prepare-preview-panel"
                className="rounded-2xl border border-blue-200 bg-blue-50 px-4 py-4 text-sm text-blue-950"
              >
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                  <div>
                    <div className="text-xs font-semibold uppercase tracking-[0.16em] text-blue-600">
                      {isRu ? 'Предпросмотр подготовки каналов' : 'Channel preparation preview'}
                    </div>
                    <div className="mt-1 text-base font-semibold text-blue-950">
                      {socialPreparePreview.previewItemTitle}
                    </div>
                    <div className="mt-1 text-xs leading-5 text-blue-800">
                      {isRu
                        ? 'Это отдельный безопасный шаг: LocalOS показал, что будет создано, но черновики ещё не записаны и наружу ничего не опубликовано.'
                        : 'This is a separate safe step: LocalOS shows what will be created, but drafts are not written yet and nothing is published externally.'}
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-center text-xs sm:grid-cols-4">
                    <div className="rounded-xl bg-white px-3 py-2 ring-1 ring-blue-100">
                      <div className="text-lg font-semibold text-blue-950">{Number(socialPreparePreview.preview.summary?.total || 0)}</div>
                      <div>{isRu ? 'каналов' : 'channels'}</div>
                    </div>
                    <div className="rounded-xl bg-white px-3 py-2 ring-1 ring-blue-100">
                      <div className="text-lg font-semibold text-blue-950">{Number(socialPreparePreview.preview.summary?.would_create || 0)}</div>
                      <div>{isRu ? 'создать' : 'create'}</div>
                    </div>
                    <div className="rounded-xl bg-white px-3 py-2 ring-1 ring-blue-100">
                      <div className="text-lg font-semibold text-blue-950">{Number(socialPreparePreview.preview.summary?.would_update || 0)}</div>
                      <div>{isRu ? 'обновить' : 'update'}</div>
                    </div>
                    <div className="rounded-xl bg-white px-3 py-2 ring-1 ring-blue-100">
                      <div className="text-lg font-semibold text-blue-950">{Number(socialPreparePreview.preview.summary?.would_preserve || 0)}</div>
                      <div>{isRu ? 'сохранить' : 'preserve'}</div>
                    </div>
                  </div>
                </div>
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {(socialPreparePreview.preview.posts || []).slice(0, 8).map((post) => (
                    <span
                      key={`${String(post.platform || '')}:${String(post.prepare_action || '')}`}
                      className="rounded-full bg-white px-2.5 py-1 text-xs font-medium text-blue-800 ring-1 ring-blue-100"
                    >
                      {String(post.platform_label || post.platform || '')}
                      {' · '}
                      {String(post.prepare_action || 'preview')}
                    </span>
                  ))}
                </div>
                <div className="mt-3 rounded-xl bg-white px-3 py-2 text-xs leading-5 text-blue-800 ring-1 ring-blue-100">
                  {isRu
                    ? `Выбрано тем: ${socialPreparePreview.itemIds.length}. Подробный предпросмотр показан по первой теме; при продолжении черновики будут созданы для всех выбранных тем.`
                    : `Selected items: ${socialPreparePreview.itemIds.length}. The detailed preview is shown for the first item; continuing creates drafts for all selected items.`}
                </div>
                <div className="mt-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-end">
                  <Button
                    type="button"
                    variant="outline"
                    className="bg-white"
                    onClick={() => setSocialPreparePreview(null)}
                    disabled={Boolean(bulkBusyAction)}
                  >
                    {isRu ? 'Отменить' : 'Cancel'}
                  </Button>
                  <Button
                    type="button"
                    onClick={() => { void executeSocialPreparePreview(); }}
                    disabled={Boolean(bulkBusyAction) || Boolean(socialBusyAction)}
                  >
                    {bulkBusyAction === socialPreparePreview.busyAction
                      ? (isRu ? 'Создаём черновики...' : 'Creating drafts...')
                      : (isRu ? 'Создать черновики для проверки' : 'Create drafts for review')}
                  </Button>
                </div>
              </div>
            ) : null}
            {socialApprovalPreview && socialApprovalPreviewSummary ? (
              <div
                data-testid="social-approval-preview-panel"
                className="rounded-2xl border border-sky-200 bg-sky-50 px-4 py-4 text-sm text-sky-950"
              >
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                  <div>
                    <div className="text-xs font-semibold uppercase tracking-[0.16em] text-sky-600">
                      {isRu ? 'Предпросмотр перед подтверждением' : 'Preview before approval'}
                    </div>
                    <div className="mt-1 text-base font-semibold text-sky-950">
                      {isRu
                        ? `Подтвердить тексты: ${socialApprovalPreviewSummary.total}`
                        : `Approve copy: ${socialApprovalPreviewSummary.total}`}
                    </div>
                    <div className="mt-1 text-xs leading-5 text-sky-800">
                      {isRu
                        ? 'Подтверждение только фиксирует проверку текста. Наружу ничего не публикуется: после этого отдельный шаг - “Поставить в расписание”.'
                        : 'Approval only records copy review. Nothing is published externally: the separate next step is “Queue on schedule”.'}
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-center text-xs sm:grid-cols-4">
                    <div className="rounded-xl bg-white px-3 py-2 ring-1 ring-sky-100">
                      <div className="text-lg font-semibold text-sky-950">{socialApprovalPreviewSummary.total}</div>
                      <div>{isRu ? 'всего' : 'total'}</div>
                    </div>
                    <div className="rounded-xl bg-white px-3 py-2 ring-1 ring-sky-100">
                      <div className="text-lg font-semibold text-sky-950">{socialApprovalPreviewSummary.api}</div>
                      <div>{isRu ? 'API' : 'API'}</div>
                    </div>
                    <div className="rounded-xl bg-white px-3 py-2 ring-1 ring-sky-100">
                      <div className="text-lg font-semibold text-sky-950">{socialApprovalPreviewSummary.supervised}</div>
                      <div>{isRu ? 'карты' : 'maps'}</div>
                    </div>
                    <div className="rounded-xl bg-white px-3 py-2 ring-1 ring-sky-100">
                      <div className="text-lg font-semibold text-sky-950">{socialApprovalPreviewSummary.emptyText}</div>
                      <div>{isRu ? 'без текста' : 'empty'}</div>
                    </div>
                  </div>
                </div>
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {socialApprovalPreviewSummary.platformLabels.slice(0, 10).map((label) => (
                    <span
                      key={`approval-preview-platform:${label}`}
                      className="rounded-full bg-white px-2.5 py-1 text-xs font-medium text-sky-800 ring-1 ring-sky-100"
                    >
                      {label}
                    </span>
                  ))}
                </div>
                <div className="mt-3 grid gap-2 md:grid-cols-2">
                  <div className="rounded-xl bg-white px-3 py-2 text-xs leading-5 text-sky-800 ring-1 ring-sky-100">
                    <div className="font-semibold text-sky-950">
                      {isRu ? 'Что произойдёт сейчас' : 'What happens now'}
                    </div>
                    <div className="mt-1">
                      {isRu
                        ? 'LocalOS сохранит подтверждение человека. API-публикация не начнётся, пока вы отдельно не поставите посты в расписание.'
                        : 'LocalOS will save human approval. API publishing will not start until you separately queue posts on schedule.'}
                    </div>
                  </div>
                  <div className="rounded-xl bg-white px-3 py-2 text-xs leading-5 text-sky-800 ring-1 ring-sky-100">
                    <div className="font-semibold text-sky-950">
                      {isRu ? 'Яндекс/2ГИС' : 'Yandex/2GIS'}
                    </div>
                    <div className="mt-1">
                      {isRu
                        ? 'Для карт подтверждение не означает автопубликацию: после постановки в расписание LocalOS создаст контролируемую или ручную задачу, финальный клик остаётся за человеком.'
                        : 'For map platforms, approval does not mean autopublish: after queueing, LocalOS creates a supervised or manual task, and the final click stays human-controlled.'}
                    </div>
                  </div>
                </div>
                {socialApprovalPreviewSummary.blockedApiWarnings.length > 0 ? (
                  <div className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-900">
                    <div className="font-semibold text-amber-950">
                      {isRu ? 'API-каналы можно подтвердить, но они ещё не готовы к публикации' : 'API channels can be approved, but are not ready to publish yet'}
                    </div>
                    <div className="mt-1">
                      {isRu
                        ? 'Подтверждение текста разрешено, но исполнитель не опубликует эти каналы без ключей, прав или привязки аккаунта.'
                        : 'Copy approval is allowed, but the worker will not publish these channels without keys, permissions, or account binding.'}
                    </div>
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {socialApprovalPreviewSummary.blockedApiWarnings.slice(0, 6).map((warning) => (
                        <span
                          key={`approval-api-warning:${warning.postId}:${warning.platform}`}
                          className="rounded-full bg-white px-2.5 py-1 font-medium text-amber-800"
                        >
                          {warning.label} · {warning.status}
                        </span>
                      ))}
                    </div>
                  </div>
                ) : null}
                {socialApprovalPreviewSummary.emptyText > 0 ? (
                  <div className="mt-3 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-xs leading-5 text-red-800">
                    {isRu
                      ? `Перед подтверждением заполните и сохраните текст: ${socialApprovalPreviewSummary.emptyText}.`
                      : `Add and save copy before approval: ${socialApprovalPreviewSummary.emptyText}.`}
                  </div>
                ) : null}
                <div className="mt-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-end">
                  <Button
                    type="button"
                    variant="outline"
                    className="bg-white"
                    onClick={() => setSocialApprovalPreview(null)}
                    disabled={Boolean(bulkBusyAction)}
                  >
                    {isRu ? 'Отменить' : 'Cancel'}
                  </Button>
                  <Button
                    type="button"
                    onClick={() => { void executeSocialApprovalPreview(); }}
                    disabled={Boolean(bulkBusyAction) || socialApprovalPreviewSummary.emptyText > 0}
                  >
                    {bulkBusyAction === socialApprovalPreview.busyAction
                      ? (isRu ? 'Подтверждаем тексты...' : 'Approving copy...')
                      : (isRu ? 'Подтвердить тексты' : 'Approve copy')}
                  </Button>
                </div>
              </div>
            ) : null}
            {socialQueuePreview && socialQueuePreviewSummary ? (
              <div
                data-testid="social-queue-preview-panel"
                className="rounded-2xl border border-indigo-200 bg-indigo-50 px-4 py-4 text-sm text-indigo-950"
              >
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                  <div>
                    <div className="text-xs font-semibold uppercase tracking-[0.16em] text-indigo-600">
                      {isRu ? 'Предпросмотр постановки в расписание' : 'Queue preview'}
                    </div>
                    <div className="mt-1 text-base font-semibold text-indigo-950">
                      {isRu
                        ? `Разрешить исполнение по дате: ${socialQueuePreviewSummary.total}`
                        : `Allow scheduled execution: ${socialQueuePreviewSummary.total}`}
                    </div>
                    <div className="mt-1 text-xs leading-5 text-indigo-800">
                      {isRu
                        ? 'Этот шаг переводит утверждённые посты в расписание. После второго клика исполнитель сможет обработать API-каналы по дате; это уже шаг исполнения, но не мгновенная публикация всех каналов.'
                        : 'Queue moves approved posts onto the schedule. After the second click, the worker can process due API channels by date; this is an execution step, but not instant publishing for every channel.'}
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-center text-xs sm:grid-cols-4">
                    <div className="rounded-xl bg-white px-3 py-2 ring-1 ring-indigo-100">
                      <div className="text-lg font-semibold text-indigo-950">{socialQueuePreviewSummary.total}</div>
                      <div>{isRu ? 'в расписание' : 'to queue'}</div>
                    </div>
                    <div className="rounded-xl bg-white px-3 py-2 ring-1 ring-indigo-100">
                      <div className="text-lg font-semibold text-indigo-950">{socialQueuePreviewSummary.api}</div>
                      <div>{isRu ? 'API' : 'API'}</div>
                    </div>
                    <div className="rounded-xl bg-white px-3 py-2 ring-1 ring-indigo-100">
                      <div className="text-lg font-semibold text-indigo-950">{socialQueuePreviewSummary.supervised}</div>
                      <div>{isRu ? 'карты' : 'maps'}</div>
                    </div>
                    <div className="rounded-xl bg-white px-3 py-2 ring-1 ring-indigo-100">
                      <div className="text-lg font-semibold text-indigo-950">{socialQueuePreviewSummary.dueNow}</div>
                      <div>{isRu ? 'уже due' : 'due now'}</div>
                    </div>
                  </div>
                </div>
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {socialQueuePreviewSummary.platformLabels.slice(0, 10).map((label) => (
                    <span
                      key={`queue-preview-platform:${label}`}
                      className="rounded-full bg-white px-2.5 py-1 text-xs font-medium text-indigo-800 ring-1 ring-indigo-100"
                    >
                      {label}
                    </span>
                  ))}
                </div>
                <div className="mt-3 grid gap-2 md:grid-cols-3">
                  <div className="rounded-xl bg-white px-3 py-2 text-xs leading-5 text-indigo-800 ring-1 ring-indigo-100">
                    <div className="font-semibold text-indigo-950">
                      {isRu ? 'Когда' : 'When'}
                    </div>
                    <div className="mt-1">
                      {socialQueuePreviewSummary.firstScheduledFor
                        ? _formatPlanItemDate(socialQueuePreviewSummary.firstScheduledFor, isRu)
                        : (isRu ? 'Дата не указана' : 'No date set')}
                    </div>
                    <div className="mt-1 text-indigo-700">
                      {socialQueuePreviewSummary.dueNow > 0
                        ? (isRu
                          ? 'Часть постов уже пора публиковать: исполнитель сможет взять их в ближайший цикл.'
                          : 'Some posts are already due: the worker can pick them up in the next cycle.')
                        : (isRu
                          ? 'Исполнитель будет ждать дату публикации.'
                          : 'The worker will wait for the scheduled date.')}
                    </div>
                  </div>
                  <div className="rounded-xl bg-white px-3 py-2 text-xs leading-5 text-indigo-800 ring-1 ring-indigo-100">
                    <div className="font-semibold text-indigo-950">
                      {isRu ? 'API-каналы' : 'API channels'}
                    </div>
                    <div className="mt-1">
                      {socialDispatchEnabled && !socialDispatchBlockedWithoutScope && !socialDispatchScopeMismatch
                        ? (isRu
                          ? 'Фоновый запуск включён для этого бизнеса и обработает готовые API-каналы.'
                          : 'The worker is enabled for this business and will process ready API channels.')
                        : (isRu
                          ? 'Расписание сохранится, но фоновый запуск сейчас не отправит эти API-посты.'
                          : 'Queue will be saved, but the external worker will not run these API posts right now.')}
                    </div>
                  </div>
                  <div className="rounded-xl bg-white px-3 py-2 text-xs leading-5 text-indigo-800 ring-1 ring-indigo-100">
                    <div className="font-semibold text-indigo-950">
                      {isRu ? 'Яндекс/2ГИС' : 'Yandex/2GIS'}
                    </div>
                    <div className="mt-1">
                      {isRu
                        ? 'Карты после постановки в расписание не публикуются тихо: LocalOS создаст контролируемую или ручную задачу, финальный клик остаётся за человеком.'
                        : 'Maps do not publish silently after queueing: LocalOS creates a supervised or manual task, and the final click stays human-controlled.'}
                    </div>
                  </div>
                </div>
                {socialQueuePreviewSummary.blockedApiWarnings.length > 0 ? (
                  <div className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-900">
                    <div className="font-semibold text-amber-950">
                      {isRu ? 'Эти API-каналы попадут в расписание, но пока не готовы к публикации' : 'These API channels will be queued, but are not ready to publish yet'}
                    </div>
                    <div className="mt-1">
                      {isRu
                        ? 'Исполнитель пропустит их или переведёт в понятный статус, пока не появятся ключи, права или привязка аккаунта.'
                        : 'The worker will skip them or move them into a clear status until keys, permissions, or account binding are present.'}
                    </div>
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {socialQueuePreviewSummary.blockedApiWarnings.slice(0, 6).map((warning) => (
                        <span
                          key={`queue-api-warning:${warning.postId}:${warning.platform}`}
                          className="rounded-full bg-white px-2.5 py-1 font-medium text-amber-800"
                        >
                          {warning.label} · {warning.status}
                        </span>
                      ))}
                    </div>
                  </div>
                ) : null}
                <div className="mt-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-end">
                  <Button
                    type="button"
                    variant="outline"
                    className="bg-white"
                    onClick={() => setSocialQueuePreview(null)}
                    disabled={Boolean(bulkBusyAction)}
                  >
                    {isRu ? 'Отменить' : 'Cancel'}
                  </Button>
                  <Button
                    type="button"
                    onClick={() => { void executeSocialQueuePreview(); }}
                    disabled={Boolean(bulkBusyAction)}
                  >
                    {bulkBusyAction === socialQueuePreview.busyAction
                      ? (isRu ? 'Ставим в расписание...' : 'Queueing...')
                      : (isRu ? 'Поставить в расписание после проверки' : 'Queue after review')}
                  </Button>
                </div>
              </div>
            ) : null}
            {actionSummary ? (
              <div
                className={[
                  'rounded-2xl border px-4 py-3 text-sm',
                  actionSummary.tone === 'success'
                    ? 'border-emerald-200 bg-emerald-50 text-emerald-800'
                    : actionSummary.tone === 'warning'
                      ? 'border-amber-200 bg-amber-50 text-amber-900'
                      : 'border-slate-200 bg-slate-50 text-slate-700',
                ].join(' ')}
              >
                <div>{isRu ? actionSummary.text_ru : actionSummary.text_en}</div>
                {(isRu ? actionSummary.details_ru : actionSummary.details_en)?.length ? (
                  <div className="mt-2 space-y-1 text-xs opacity-90">
                    {(isRu ? actionSummary.details_ru : actionSummary.details_en)?.map((detail) => (
                      <div key={detail}>{detail}</div>
                    ))}
                  </div>
                ) : null}
                {actionSummary.focusLocationKey && actionSummary.focusWeekKey ? (
                  <div className="mt-3">
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      className="bg-white/70"
                      onClick={() => applyLocationWeekFocus(String(actionSummary.focusLocationKey || ''), String(actionSummary.focusWeekKey || ''))}
                    >
                      {isRu ? 'Открыть этот срез' : 'Open this slice'}
                    </Button>
                  </div>
                ) : null}
              </div>
            ) : null}
            <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3">
              <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                <div>
                  <div className="text-sm font-semibold text-slate-950">
                    {isRu ? 'Найти тему в очереди' : 'Find a topic in the queue'}
                  </div>
                  <div className="mt-1 text-xs leading-5 text-slate-500">
                    {isRu
                      ? 'Поиск ищет по теме, тексту черновика, ключу и точке. Например: отпуск, ХИТ, стрижка.'
                      : 'Search by topic, draft text, keyword, and location. For example: vacation, haircut, promo.'}
                  </div>
                </div>
                <div className="flex w-full gap-2 lg:w-[420px]">
                  <Input
                    value={queueSearch}
                    onChange={(event) => setQueueSearch(event.target.value)}
                    placeholder={isRu ? 'Поиск: отпуск, ХИТ, стрижка...' : 'Search: vacation, haircut...'}
                    className="bg-white"
                  />
                  {queueSearch.trim() ? (
                    <Button type="button" variant="outline" onClick={() => setQueueSearch('')}>
                      {isRu ? 'Сбросить' : 'Clear'}
                    </Button>
                  ) : null}
                </div>
              </div>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-white px-4 py-4">
              <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
                <div className="min-w-0">
                  <div className="text-sm font-semibold text-slate-950">
                    {isRu ? 'Показать в очереди' : 'Show in queue'}
                  </div>
                  <div className="mt-1 text-xs leading-5 text-slate-500">
                    {isRu
                      ? 'Выберите состояние и период публикации. Список ниже сразу обновится по календарной дате.'
                      : 'Choose status and publication period. The list below updates by calendar date.'}
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {ITEM_FILTER_OPTIONS.map((filterKey) => (
                      <button
                        key={filterKey}
                        type="button"
                        onClick={() => {
                          setSelectedItemFilter(filterKey);
                          setSortMode('date');
                        }}
                        className={[
                          'rounded-full border px-3 py-1.5 text-sm transition-colors',
                          selectedItemFilter === filterKey
                            ? 'border-slate-900 bg-slate-900 text-white'
                            : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50',
                        ].join(' ')}
                      >
                        {_itemFilterLabel(filterKey, isRu)} · {itemFilterCounts[filterKey]}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="grid gap-3 sm:grid-cols-[minmax(150px,1fr)_minmax(150px,1fr)_auto] sm:items-end">
                  <label className="grid gap-1 text-xs font-medium text-slate-600">
                    <span>{isRu ? 'С даты' : 'From date'}</span>
                    <Input
                      type="date"
                      value={dateFromFilter}
                      onChange={(event) => {
                        setDateFromFilter(event.target.value);
                        setSortMode('date');
                      }}
                      className="bg-white"
                    />
                  </label>
                  <label className="grid gap-1 text-xs font-medium text-slate-600">
                    <span>{isRu ? 'По дату' : 'To date'}</span>
                    <Input
                      type="date"
                      value={dateToFilter}
                      onChange={(event) => {
                        setDateToFilter(event.target.value);
                        setSortMode('date');
                      }}
                      className="bg-white"
                    />
                  </label>
                  <Button type="button" variant="outline" onClick={resetViewState}>
                    {isRu ? 'Сбросить' : 'Reset'}
                  </Button>
                </div>
              </div>
              <div className="mt-3 text-xs text-slate-500">
                <span className="font-medium text-slate-700">
                  {isRu ? 'Сейчас показано:' : 'Current view:'}
                </span>{' '}
                {_itemFilterLabel(selectedItemFilter, isRu)}
                {dateFromFilter || dateToFilter
                  ? ` · ${dateFromFilter || '...'} - ${dateToFilter || '...'}`
                  : ` · ${isRu ? 'все даты' : 'all dates'}`}
              </div>
              <div className="rounded-2xl border border-slate-200 bg-white px-3 py-3">
                <div
                  data-testid="social-publishing-next-step"
                  className="rounded-2xl border border-slate-200 bg-slate-950 px-4 py-4 text-white"
                >
                  <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                    <div>
                      <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">
                        {isRu ? 'Следующий шаг публикаций' : 'Publishing next step'}
                      </div>
                      <div className="mt-2 text-lg font-semibold">
                        {isRu ? socialPlanNextStep.titleRu : socialPlanNextStep.titleEn}
                      </div>
                      <div className="mt-2 max-w-3xl text-sm leading-6 text-slate-300">
                        {isRu ? socialPlanNextStep.descriptionRu : socialPlanNextStep.descriptionEn}
                      </div>
                      <div
                        data-testid="social-owner-simple-goal"
                        className="mt-3 grid gap-2 text-xs leading-5 md:grid-cols-3"
                      >
                        <div className="rounded-xl bg-white/10 px-3 py-2 text-slate-100">
                          <div className="font-semibold text-white">
                            {isRu ? '1. Что делать первым' : '1. First action'}
                          </div>
                          <div className="mt-1">
                            {isRu ? socialPlanNextStep.descriptionRu : socialPlanNextStep.descriptionEn}
                          </div>
                        </div>
                        <div className="rounded-xl bg-white/10 px-3 py-2 text-slate-100">
                          <div className="font-semibold text-white">
                            {isRu ? '2. Что не произойдёт само' : '2. What will not happen silently'}
                          </div>
                          <div className="mt-1">
                            {isRu
                              ? 'Наружу ничего не уйдёт без предпросмотра, подтверждения и расписания. Финальный клик в Яндекс/2ГИС остаётся за человеком.'
                              : 'Nothing goes external without preview, approval, and queueing. The final Yandex/2GIS click stays human-controlled.'}
                          </div>
                        </div>
                        <div className="rounded-xl bg-white/10 px-3 py-2 text-slate-100">
                          <div className="font-semibold text-white">
                            {isRu ? '3. Как понять успех' : '3. Success signal'}
                          </div>
                          <div className="mt-1">
                            {isRu
                              ? 'Посты опубликованы, ручные задачи закрыты, заявки/обращения отмечены. После этого LocalOS предлагает изменения следующего плана.'
                              : 'Posts are published, manual tasks are closed, and leads/inquiries are recorded. Then LocalOS suggests next-plan changes.'}
                          </div>
                        </div>
                      </div>
                      <SocialOwnerLaunchPath
                        isRu={isRu}
                        currentAction={socialPlanNextStep.action}
                      />
                    </div>
                    <div className="flex flex-col gap-2 sm:min-w-[260px]">
                      <Button
                        type="button"
                        onClick={runSocialPlanNextStep}
                        disabled={Boolean(bulkBusyAction) || Boolean(socialBusyAction) || Boolean(socialPlanNextStep.disabled)}
                        className="bg-white text-slate-950 hover:bg-slate-100"
                      >
                        {Boolean(bulkBusyAction) || Boolean(socialBusyAction)
                          ? (isRu ? 'Выполняем...' : 'Working...')
                          : `${isRu ? socialPlanNextStep.ctaRu : socialPlanNextStep.ctaEn} · ${socialPlanNextStep.count}`}
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        onClick={() => document.getElementById('content-plan-topic-queue')?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
                        className="border-white/20 bg-transparent text-white hover:bg-white/10 hover:text-white"
                      >
                        {isRu ? 'К списку тем' : 'Go to topic list'}
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        onClick={() => { void previewSocialDispatch(); }}
                        disabled={Boolean(bulkBusyAction) || Boolean(socialBusyAction)}
                        className="border-white/20 bg-transparent text-white hover:bg-white/10 hover:text-white"
                      >
                        {socialBusyAction === 'dispatch-preview'
                          ? (isRu ? 'Проверяем...' : 'Checking...')
                          : (isRu ? 'Проверить расписание' : 'Preview schedule')}
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        data-testid="social-check-worker-launch"
                        onClick={() => { void checkSocialLaunchPreflight(); }}
                        disabled={Boolean(bulkBusyAction) || Boolean(socialBusyAction) || !businessId}
                        className="border-white/20 bg-transparent text-white hover:bg-white/10 hover:text-white"
                      >
                        {socialBusyAction === 'launch-preflight'
                          ? (isRu ? 'Проверяем запуск...' : 'Checking launch...')
                          : (isRu ? 'Проверить запуск по расписанию' : 'Check worker launch')}
                      </Button>
                      <div className="text-[11px] leading-4 text-slate-400">
                        {isRu
                          ? 'Безопасная проверка: ничего не публикует, только показывает первый цикл и блокеры.'
                          : 'Safe check: publishes nothing, only shows the first cycle and blockers.'}
                      </div>
                      <div className="grid grid-cols-3 gap-2 text-center text-[11px] text-slate-300">
                        <div className="rounded-xl bg-white/10 px-2 py-2">
                          <div className="text-sm font-semibold text-white">{socialReadinessSummary.apiReady}</div>
                          <div>{isRu ? 'API готово' : 'API ready'}</div>
                        </div>
                        <div className="rounded-xl bg-white/10 px-2 py-2">
                          <div className="text-sm font-semibold text-white">{socialReadinessSummary.supervisedOrManual}</div>
                          <div>{isRu ? 'контроль' : 'supervised'}</div>
                        </div>
                        <div className="rounded-xl bg-white/10 px-2 py-2">
                          <div className="text-sm font-semibold text-white">{socialReadinessSummary.needsAttention}</div>
                          <div>{isRu ? 'ключи/права' : 'keys/rights'}</div>
                        </div>
                      </div>
                      <SocialLaunchChecklist
                        isRu={isRu}
                        stages={socialLaunchStages}
                        summary={socialLaunchChecklistSummary}
                        compact
                      />
                      {socialRuntimeStatus ? (
                        <div
                          className="rounded-xl bg-white/10 px-3 py-2 text-xs leading-5 text-slate-200"
                          data-testid="social-runtime-owner-status"
                          data-schema="localos_social_runtime_owner_status_v1"
                        >
                            <div className="font-semibold text-white">
                              {isRu ? 'Runtime расписания' : 'Schedule runtime'}
                          </div>
                          {socialRuntimeStatus.owner_status ? (
                            <div className="mt-2 rounded-lg border border-white/10 bg-white/10 px-2 py-2">
                              <div className="font-semibold text-white">
                                {isRu
                                  ? String(socialRuntimeStatus.owner_status.title_ru || '')
                                  : String(socialRuntimeStatus.owner_status.title_en || '')}
                              </div>
                              <div className="mt-1 text-slate-200">
                                {isRu
                                  ? String(socialRuntimeStatus.owner_status.summary_ru || '')
                                  : String(socialRuntimeStatus.owner_status.summary_en || '')}
                              </div>
                              <div className="mt-1 font-medium text-slate-100">
                                {isRu
                                  ? String(socialRuntimeStatus.owner_status.next_action_ru || '')
                                  : String(socialRuntimeStatus.owner_status.next_action_en || '')}
                              </div>
                              <div className="mt-1 text-[11px] text-slate-300">
                                {isRu
                                  ? String(socialRuntimeStatus.owner_status.metrics_summary_ru || '')
                                  : String(socialRuntimeStatus.owner_status.metrics_summary_en || '')}
                              </div>
                            </div>
                          ) : null}
                          <div className="mt-1 grid gap-1">
                            <div className="flex items-center justify-between gap-3">
                              <span>{isRu ? 'Публикация по расписанию' : 'Scheduled dispatch'}</span>
                              <span className={socialRuntimeStatus.dispatch?.enabled ? 'font-semibold text-emerald-200' : 'font-semibold text-amber-200'}>
                                {socialRuntimeStatus.dispatch?.enabled ? (isRu ? 'включена' : 'enabled') : (isRu ? 'выключена' : 'disabled')}
                              </span>
                            </div>
                            <div className="text-[11px] text-slate-300">
                              {isRu
                                ? `интервал ${Number(socialRuntimeStatus.dispatch?.interval_sec || 0)}с · batch ${Number(socialRuntimeStatus.dispatch?.batch_size || 0)}`
                                : `interval ${Number(socialRuntimeStatus.dispatch?.interval_sec || 0)}s · batch ${Number(socialRuntimeStatus.dispatch?.batch_size || 0)}`}
                            </div>
                            <div className="text-[11px] text-slate-300">
                              {socialRuntimeStatus.dispatch?.blocked_without_scope
                                ? (isRu
                                  ? 'область: заблокировано без выбранного бизнеса'
                                  : 'scope: blocked until a business scope is set')
                                : socialRuntimeStatus.dispatch?.scoped
                                ? (isRu
                                  ? `область: только бизнес ${String(socialRuntimeStatus.dispatch?.business_scope || '')}`
                                  : `scope: business ${String(socialRuntimeStatus.dispatch?.business_scope || '')}`)
                                : socialRuntimeStatus.dispatch?.allow_unscoped
                                  ? (isRu ? 'область: все due-посты явно разрешены' : 'scope: all due posts explicitly allowed')
                                  : (isRu ? 'область: нужен business scope перед запуском' : 'scope: business scope required before dispatch')}
                            </div>
                            {socialRuntimeStatus.dispatch?.blocked_without_scope ? (
                              <div className="rounded-lg border border-amber-300/30 bg-amber-400/10 px-2 py-1 text-[11px] font-medium text-amber-100">
                                {isRu
                                  ? 'Dispatch включён, но LocalOS не запустит публикации без SOCIAL_POST_DISPATCH_BUSINESS_ID или явного allow-all.'
                                  : 'Dispatch is enabled, but LocalOS will not publish without SOCIAL_POST_DISPATCH_BUSINESS_ID or explicit allow-all.'}
                              </div>
                            ) : null}
                            <div className="flex items-center justify-between gap-3">
                              <span>{isRu ? 'Сбор реакций' : 'Metrics collection'}</span>
                              <span className={socialRuntimeStatus.metrics?.enabled ? 'font-semibold text-emerald-200' : 'font-semibold text-amber-200'}>
                                {socialRuntimeStatus.metrics?.enabled ? (isRu ? 'включён' : 'enabled') : (isRu ? 'выключен' : 'disabled')}
                              </span>
                            </div>
                            <div className="text-[11px] text-slate-300">
                              {socialRuntimeStatus.metrics?.blocked_without_scope
                                ? (isRu
                                  ? 'реакции: заблокировано без выбранного бизнеса'
                                  : 'metrics: blocked until a business scope is set')
                                : socialRuntimeStatus.metrics?.scoped
                                ? (isRu
                                  ? `реакции: только бизнес ${String(socialRuntimeStatus.metrics?.business_scope || '')}`
                                  : `metrics: business ${String(socialRuntimeStatus.metrics?.business_scope || '')}`)
                                : socialRuntimeStatus.metrics?.allow_unscoped
                                  ? (isRu ? 'реакции: все опубликованные посты явно разрешены' : 'metrics: all published posts explicitly allowed')
                                  : (isRu ? 'реакции: нужен business scope перед сбором' : 'metrics: business scope required before collection')}
                            </div>
                            {socialRuntimeStatus.metrics?.blocked_without_scope ? (
                              <div className="rounded-lg border border-amber-300/30 bg-amber-400/10 px-2 py-1 text-[11px] font-medium text-amber-100">
                                {isRu
                                  ? 'Сбор реакций включён, но LocalOS не будет вызывать внешние API без SOCIAL_POST_METRICS_BUSINESS_ID или явного allow-all.'
                                  : 'Metrics collection is enabled, but LocalOS will not call external APIs without SOCIAL_POST_METRICS_BUSINESS_ID or explicit allow-all.'}
                              </div>
                            ) : null}
                            {socialRuntimeStatus.telegram_transport ? (
                              <div
                                data-testid="social-runtime-telegram-transport"
                                data-schema={String(socialRuntimeStatus.telegram_transport.schema || 'localos_telegram_transport_status_v1')}
                                className={[
                                  'rounded-lg border px-2 py-1.5 text-[11px] leading-4',
                                  socialRuntimeStatus.telegram_transport.ready
                                    ? 'border-emerald-300/30 bg-emerald-400/10 text-emerald-50'
                                    : 'border-amber-300/30 bg-amber-400/10 text-amber-50',
                                ].join(' ')}
                              >
                                <div className="flex items-center justify-between gap-3 font-semibold">
                                  <span>{isRu ? 'Telegram transport' : 'Telegram transport'}</span>
                                  <span>
                                    {socialRuntimeStatus.telegram_transport.ready
                                      ? (isRu ? 'готов' : 'ready')
                                      : (isRu ? 'требует проверки' : 'needs check')}
                                  </span>
                                </div>
                                <div className="mt-1">
                                  {isRu
                                    ? String(socialRuntimeStatus.telegram_transport.summary_ru || '')
                                    : String(socialRuntimeStatus.telegram_transport.summary_en || '')}
                                </div>
                                <div className="mt-1 font-medium">
                                  {isRu
                                    ? String(socialRuntimeStatus.telegram_transport.next_action_ru || '')
                                    : String(socialRuntimeStatus.telegram_transport.next_action_en || '')}
                                </div>
                              </div>
                            ) : null}
                          </div>
                          <div className="mt-1 text-[11px] text-slate-300">
                              {isRu
                                ? 'Внешние публикации всё равно требуют подтверждения; Яндекс/2ГИС не нажимают финальную кнопку без человека.'
                                : 'External posts still require approval; Yandex/2GIS do not click final publish without a human.'}
                          </div>
                        </div>
                      ) : null}
                      {socialRuntimeStatus && (visibleSocialCanQueue.length > 0 || Number(socialSummary?.scheduled || 0) > 0) ? (
                        <div
                          className={[
                            'rounded-xl border px-3 py-2 text-xs leading-5',
                            socialQueueExecutionNotice.tone === 'ok'
                              ? 'border-emerald-300/30 bg-emerald-400/10 text-emerald-100'
                              : 'border-amber-300/30 bg-amber-400/10 text-amber-100',
                          ].join(' ')}
                        >
                          <div className="font-semibold">
                            {isRu ? socialQueueExecutionNotice.titleRu : socialQueueExecutionNotice.titleEn}
                          </div>
                          <div className="mt-1">
                            {isRu ? socialQueueExecutionNotice.textRu : socialQueueExecutionNotice.textEn}
                          </div>
                        </div>
                      ) : null}
                      {socialLaunchPreflight ? (
                        <div
                          className={[
                            'rounded-xl border px-3 py-2 text-xs leading-5',
                            socialLaunchPreflight.safe_to_enable_scoped_dispatch
                              ? 'border-emerald-300/30 bg-emerald-400/10 text-emerald-100'
                              : 'border-amber-300/30 bg-amber-400/10 text-amber-100',
                          ].join(' ')}
                        >
                          <div className="flex items-center justify-between gap-2">
                            <span className="font-semibold">
                              {isRu ? 'Проверка запуска по расписанию' : 'Worker launch preflight'}
                            </span>
                            <span className="rounded-full bg-white/10 px-2 py-0.5 text-[11px] font-semibold text-white">
                              {socialLaunchPreflight.safe_to_enable_scoped_dispatch
                                ? (isRu ? 'можно scoped' : 'scoped ready')
                                : (isRu ? 'сначала подготовить' : 'prepare first')}
                            </span>
                          </div>
                          <div className="mt-1">
                            {isRu
                              ? String(socialLaunchPreflight.message_ru || '')
                              : String(socialLaunchPreflight.message_en || '')}
                          </div>
                          <div className="mt-1 text-[11px] text-slate-200">
                            {isRu
                              ? `Due ${Number(socialLaunchPreflight.summary?.due_posts || 0)} · API ${Number(socialLaunchPreflight.summary?.api_due_posts || 0)} · контролируемо ${Number(socialLaunchPreflight.summary?.controlled_due_posts || 0)} · вручную ${Number(socialLaunchPreflight.summary?.manual_due_posts || 0)}`
                              : `Due ${Number(socialLaunchPreflight.summary?.due_posts || 0)} · API ${Number(socialLaunchPreflight.summary?.api_due_posts || 0)} · supervised ${Number(socialLaunchPreflight.summary?.controlled_due_posts || 0)} · manual ${Number(socialLaunchPreflight.summary?.manual_due_posts || 0)}`}
                          </div>
                          {socialLaunchPreflight.worker_idle_reason ? (
                            <div
                              data-testid="social-worker-idle-reason"
                              className="mt-2 rounded-lg border border-amber-200/30 bg-amber-400/10 px-2 py-2 text-[11px] leading-5 text-amber-50"
                            >
                              <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
                                <div>
                                  <div className="font-semibold text-white">
                                    {isRu ? 'Почему worker ждёт' : 'Why the worker is waiting'}
                                    {' · '}
                                    {isRu
                                      ? String(socialLaunchPreflight.worker_idle_reason.title_ru || '')
                                      : String(socialLaunchPreflight.worker_idle_reason.title_en || '')}
                                  </div>
                                  <div className="mt-1">
                                    {isRu
                                      ? String(socialLaunchPreflight.worker_idle_reason.next_action_ru || '')
                                      : String(socialLaunchPreflight.worker_idle_reason.next_action_en || '')}
                                  </div>
                                  {String(socialLaunchPreflight.worker_idle_reason.status || '') === 'waiting_for_review' ? (
                                    <div className="mt-2">
                                      <Button
                                        size="sm"
                                        variant="secondary"
                                        onClick={openSocialPostsWaitingForReview}
                                        data-testid="social-open-waiting-review"
                                      >
                                        <CheckSquare className="mr-2 h-4 w-4" />
                                        {isRu ? 'Открыть посты на проверку' : 'Open posts for review'}
                                      </Button>
                                    </div>
                                  ) : null}
                                  {String(socialLaunchPreflight.worker_idle_reason.status || '') === 'waiting_for_queue' ? (
                                    <div className="mt-2">
                                      <Button
                                        size="sm"
                                        variant="secondary"
                                        onClick={openSocialPostsWaitingForQueue}
                                        data-testid="social-open-waiting-queue"
                                      >
                                        <CalendarDays className="mr-2 h-4 w-4" />
                                        {isRu ? 'Поставить утверждённые в расписание' : 'Queue approved posts'}
                                      </Button>
                                    </div>
                                  ) : null}
                                  {String(socialLaunchPreflight.worker_idle_reason.status || '') === 'has_due_queued_posts' ? (
                                    <div className="mt-2">
                                      <Button
                                        size="sm"
                                        variant="secondary"
                                        onClick={() => { void previewSocialDispatch(true); }}
                                        disabled={socialBusyAction === 'dispatch-preview'}
                                        data-testid="social-open-due-dispatch-preview"
                                      >
                                        <Globe className="mr-2 h-4 w-4" />
                                        {socialBusyAction === 'dispatch-preview'
                                          ? (isRu ? 'Проверяем due...' : 'Checking due...')
                                          : (isRu ? 'Проверить due-публикации' : 'Preview due dispatch')}
                                      </Button>
                                    </div>
                                  ) : null}
                                </div>
                                <span className="shrink-0 rounded-full bg-white/10 px-2 py-0.5 font-semibold text-white">
                                  {isRu
                                    ? `постов: ${Number(socialLaunchPreflight.worker_idle_reason.count || 0)}`
                                    : `posts: ${Number(socialLaunchPreflight.worker_idle_reason.count || 0)}`}
                                </span>
                              </div>
                              <div className="mt-2 grid gap-1 sm:grid-cols-4">
                                <div className="rounded-md bg-white/10 px-2 py-1">
                                  <span className="font-semibold text-white">{Number(socialLaunchPreflight.workflow_stage_counts?.needs_review || socialLaunchPreflight.summary?.workflow_needs_review || 0)}</span>
                                  {' '}
                                  {isRu ? 'проверить' : 'review'}
                                </div>
                                <div className="rounded-md bg-white/10 px-2 py-1">
                                  <span className="font-semibold text-white">{Number(socialLaunchPreflight.workflow_stage_counts?.approved_not_queued || socialLaunchPreflight.summary?.workflow_approved_not_queued || 0)}</span>
                                  {' '}
                                  {isRu ? 'утверждено' : 'approved'}
                                </div>
                                <div className="rounded-md bg-white/10 px-2 py-1">
                                  <span className="font-semibold text-white">{Number(socialLaunchPreflight.workflow_stage_counts?.queued_future || socialLaunchPreflight.summary?.workflow_queued_future || 0)}</span>
                                  {' '}
                                  {isRu ? 'будущие' : 'future'}
                                </div>
                                <div className="rounded-md bg-white/10 px-2 py-1">
                                  <span className="font-semibold text-white">{Number(socialLaunchPreflight.workflow_stage_counts?.queued_due || socialLaunchPreflight.summary?.due_posts || 0)}</span>
                                  {' '}
                                  {isRu ? 'готовы сейчас' : 'due now'}
                                </div>
                              </div>
                            </div>
                          ) : null}
                          {socialLaunchPreflight.production_readiness ? (
                            <div
                              data-testid="social-production-readiness"
                              className={[
                                'mt-2 rounded-lg border px-2 py-2 text-[11px] leading-5',
                                socialLaunchPreflight.production_readiness.ready_for_first_scoped_cycle
                                  ? 'border-emerald-200/30 bg-emerald-400/10 text-emerald-50'
                                  : Number(socialLaunchPreflight.production_readiness.blockers?.length || 0) > 0
                                    ? 'border-amber-200/30 bg-amber-950/20 text-amber-50'
                                    : 'border-sky-200/30 bg-sky-400/10 text-sky-50',
                              ].join(' ')}
                            >
                              <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
                                <div>
                                  <div className="font-semibold text-white">
                                    {isRu ? 'Готовность к первому циклу' : 'First-cycle readiness'}
                                    {' · '}
                                    {isRu
                                      ? String(socialLaunchPreflight.production_readiness.title_ru || '')
                                      : String(socialLaunchPreflight.production_readiness.title_en || '')}
                                  </div>
                                  <div className="mt-1">
                                    {isRu
                                      ? String(socialLaunchPreflight.production_readiness.summary_ru || '')
                                      : String(socialLaunchPreflight.production_readiness.summary_en || '')}
                                  </div>
                                </div>
                                <span className="shrink-0 rounded-full bg-white/10 px-2 py-0.5 font-semibold text-white">
                                  {String(socialLaunchPreflight.production_readiness.status || 'prepare_first')}
                                </span>
                              </div>
                              {Number(socialLaunchPreflight.production_readiness.blockers?.length || 0) > 0 ? (
                                <div className="mt-2 rounded-lg bg-white/10 px-2 py-2">
                                  <div className="font-semibold text-white">
                                    {isRu ? 'Блокеры перед запуском' : 'Launch blockers'}
                                  </div>
                                  <ul className="mt-1 space-y-1">
                                    {(socialLaunchPreflight.production_readiness.blockers || []).slice(0, 4).map((item) => (
                                      <li key={`production-blocker:${String(item.key || '')}`} className="text-amber-50">
                                        <span className="font-semibold text-white">
                                          {isRu ? String(item.label_ru || '') : String(item.label_en || '')}
                                        </span>
                                        {': '}
                                        {isRu ? String(item.action_ru || '') : String(item.action_en || '')}
                                      </li>
                                    ))}
                                  </ul>
                                </div>
                              ) : null}
                              {Number(socialLaunchPreflight.production_readiness.warnings?.length || 0) > 0 ? (
                                <div className="mt-2 flex flex-wrap gap-1">
                                  {(socialLaunchPreflight.production_readiness.warnings || []).slice(0, 4).map((item) => (
                                    <span
                                      key={`production-warning:${String(item.key || '')}`}
                                      className="rounded-full bg-white/10 px-2 py-0.5 font-medium text-slate-50"
                                    >
                                      {isRu ? String(item.label_ru || '') : String(item.label_en || '')}
                                    </span>
                                  ))}
                                </div>
                              ) : null}
                              <div className="mt-2 font-medium text-white">
                                {isRu ? 'Что сделать: ' : 'What to do: '}
                                {isRu
                                  ? String(socialLaunchPreflight.production_readiness.next_action_ru || '')
                                  : String(socialLaunchPreflight.production_readiness.next_action_en || '')}
                              </div>
                            </div>
                          ) : null}
                          {socialLaunchPreflight.proof_requirements ? (
                            <div
                              data-testid="social-proof-requirements"
                              data-schema={String(socialLaunchPreflight.proof_requirements.schema || 'localos_social_proof_requirements_v1')}
                              className={[
                                'mt-2 rounded-lg border px-2 py-2 text-[11px] leading-5',
                                String(socialLaunchPreflight.proof_requirements.status || '') === 'ready_for_live_proof'
                                  ? 'border-emerald-200/30 bg-emerald-400/10 text-emerald-50'
                                  : 'border-sky-200/30 bg-sky-400/10 text-sky-50',
                              ].join(' ')}
                            >
                              <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
                                <div>
                                  <div className="font-semibold text-white">
                                    {isRu
                                      ? String(socialLaunchPreflight.proof_requirements.title_ru || 'Что осталось для живого теста')
                                      : String(socialLaunchPreflight.proof_requirements.title_en || 'What remains for the live proof')}
                                  </div>
                                  <div className="mt-1">
                                    {isRu
                                      ? String(socialLaunchPreflight.proof_requirements.summary_ru || '')
                                      : String(socialLaunchPreflight.proof_requirements.summary_en || '')}
                                  </div>
                                </div>
                                <span className="shrink-0 rounded-full bg-white/10 px-2 py-0.5 font-semibold text-white">
                                  {Number(socialLaunchPreflight.proof_requirements.ready_groups || 0)}
                                  {'/'}
                                  {Number(socialLaunchPreflight.proof_requirements.total_groups || 0)}
                                </span>
                              </div>
                              <div className="mt-2 grid gap-2 lg:grid-cols-3">
                                {(socialLaunchPreflight.proof_requirements.groups || []).slice(0, 3).map((group) => {
                                  const state = String(group.state || '');
                                  const ready = state === 'ready' || state === 'complete';
                                  const attention = state === 'needs_setup' || state === 'needs_channel' || state === 'needs_manual_fallback';
                                  const stateClass = ready
                                    ? 'border-emerald-200/30 bg-emerald-400/10 text-emerald-50'
                                    : attention
                                      ? 'border-amber-200/30 bg-amber-400/10 text-amber-50'
                                      : 'border-white/10 bg-white/10 text-slate-100';
                                  const checklist = isRu ? group.checklist_ru : group.checklist_en;
                                  return (
                                    <div
                                      key={`proof-requirement:${String(group.key || '')}`}
                                      className={['rounded-lg border px-2 py-2', stateClass].join(' ')}
                                    >
                                      <div className="flex items-center justify-between gap-2">
                                        <span className="font-semibold text-white">
                                          {isRu
                                            ? String(group.title_ru || (
                                              String(group.key || '') === 'telegram_vk_api_proof'
                                                ? 'Telegram/VK API proof'
                                                : String(group.key || '') === 'maps_supervised_handoff'
                                                  ? 'Яндекс/2ГИС handoff'
                                                  : String(group.key || '') === 'metrics_and_recommendation'
                                                    ? 'Метрики и заявки'
                                                    : ''
                                            ))
                                            : String(group.title_en || '')}
                                        </span>
                                        <span className="rounded-full bg-white/10 px-2 py-0.5 text-[10px] font-semibold text-white">
                                          {state || 'pending'}
                                        </span>
                                      </div>
                                      <div className="mt-1">
                                        {isRu ? String(group.summary_ru || '') : String(group.summary_en || '')}
                                      </div>
                                      {Array.isArray(checklist) && checklist.length > 0 ? (
                                        <ul className="mt-2 space-y-1">
                                          {checklist.slice(0, 3).map((step, index) => (
                                            <li key={`proof-step:${String(group.key || '')}:${index}:${step}`} className="flex gap-1.5">
                                              <span className="font-semibold text-white">{index + 1}.</span>
                                              <span>{step}</span>
                                            </li>
                                          ))}
                                        </ul>
                                      ) : null}
                                      <div className="mt-2 font-medium text-white">
                                        {isRu ? 'Дальше: ' : 'Next: '}
                                        {isRu ? String(group.next_action_ru || '') : String(group.next_action_en || '')}
                                      </div>
                                    </div>
                                  );
                                })}
                              </div>
                              <div className="mt-2 rounded-md bg-white/10 px-2 py-1 text-slate-100">
                                <span className="font-semibold text-white">
                                  {isRu ? 'Главный KPI: ' : 'Primary KPI: '}
                                </span>
                                {isRu
                                  ? String(socialLaunchPreflight.proof_requirements.primary_metric_ru || 'Заявки и обращения')
                                  : String(socialLaunchPreflight.proof_requirements.primary_metric_en || 'Leads and inquiries')}
                                {' · '}
                                {isRu
                                  ? 'внешняя публикация только после подтверждения, карты без финального автоклика.'
                                  : 'external publish only after approval, maps without final auto-click.'}
                              </div>
                              {(socialLaunchPreflight.proof_requirements.next_action_ru || socialLaunchPreflight.proof_requirements.next_action_en) ? (
                                <div className="mt-2 font-medium text-white">
                                  {isRu ? 'Ближайший шаг: ' : 'Closest next step: '}
                                  {isRu
                                    ? String(socialLaunchPreflight.proof_requirements.next_action_ru || '')
                                    : String(socialLaunchPreflight.proof_requirements.next_action_en || '')}
                                </div>
                              ) : null}
                            </div>
                          ) : null}
                          {socialLaunchPreflight.first_api_publish_readiness ? (
                            <div
                              className={[
                                'mt-2 rounded-lg border px-2 py-2 text-[11px] leading-5',
                                socialLaunchPreflight.first_api_publish_readiness.ready
                                  ? 'border-emerald-200/30 bg-emerald-400/10 text-emerald-50'
                                  : 'border-amber-200/30 bg-amber-400/10 text-amber-50',
                              ].join(' ')}
                            >
                              <div className="flex items-center justify-between gap-2">
                                <span className="font-semibold text-white">
                                  {isRu ? 'Первый API-пост' : 'First API post'}
                                </span>
                                <span className="rounded-full bg-white/10 px-2 py-0.5 font-semibold text-white">
                                  {socialLaunchPreflight.first_api_publish_readiness.ready
                                    ? (isRu ? 'есть готовый канал' : 'ready channel')
                                    : (isRu ? 'нужны ключи' : 'needs keys')}
                                </span>
                              </div>
                              <div className="mt-1">
                                {isRu
                                  ? String(socialLaunchPreflight.first_api_publish_readiness.message_ru || '')
                                  : String(socialLaunchPreflight.first_api_publish_readiness.message_en || '')}
                              </div>
                              {(socialLaunchPreflight.first_api_publish_readiness.ready_platforms || []).length > 0 ? (
                                <div className="mt-1 flex flex-wrap gap-1">
                                  {(socialLaunchPreflight.first_api_publish_readiness.ready_platforms || []).slice(0, 4).map((item) => (
                                    <span
                                      key={`launch-api-ready:${String(item.platform || '')}`}
                                      className="rounded-full bg-emerald-400/20 px-2 py-0.5 font-medium text-emerald-50"
                                    >
                                      {item.platform_label || _socialPlatformLabel(String(item.platform || ''), isRu)}
                                    </span>
                                  ))}
                                </div>
                              ) : null}
                              {(socialLaunchPreflight.first_api_publish_readiness.blocked_platforms || []).length > 0 ? (
                                <div className="mt-1 flex flex-wrap gap-1">
                                  {(socialLaunchPreflight.first_api_publish_readiness.blocked_platforms || []).slice(0, 4).map((item) => (
                                    <span
                                      key={`launch-api-blocked:${String(item.platform || '')}`}
                                      className="rounded-full bg-white/10 px-2 py-0.5 font-medium text-amber-50"
                                    >
                                      {item.platform_label || _socialPlatformLabel(String(item.platform || ''), isRu)}
                                      {' · '}
                                      {String(item.status || 'not_ready')}
                                    </span>
                                  ))}
                                </div>
                              ) : null}
                              <div
                                data-testid="social-first-api-fast-start"
                                className="mt-2 rounded-lg bg-white/10 px-2 py-2"
                              >
                                <div className="font-semibold text-white">
                                  {isRu ? 'Быстрый старт API' : 'Fast API start'}
                                </div>
                                <div className="mt-1 text-slate-100">
                                  {isRu
                                    ? String(socialLaunchPreflight.first_api_publish_readiness.fast_start_message_ru || 'Telegram или VK быстрее всего дают первый проверенный API-пост.')
                                    : String(socialLaunchPreflight.first_api_publish_readiness.fast_start_message_en || 'Telegram or VK usually provide the fastest proven API post.')}
                                </div>
                                {(
                                  (socialLaunchPreflight.first_api_publish_readiness.fast_start_ready_platforms || []).length > 0
                                  || (socialLaunchPreflight.first_api_publish_readiness.fast_start_blocked_platforms || []).length > 0
                                ) ? (
                                  <div className="mt-2 flex flex-wrap gap-1">
                                    {(socialLaunchPreflight.first_api_publish_readiness.fast_start_ready_platforms || []).slice(0, 2).map((item) => (
                                      <span
                                        key={`fast-api-ready:${String(item.platform || '')}`}
                                        className="rounded-full bg-emerald-400/20 px-2 py-0.5 font-medium text-emerald-50"
                                      >
                                        {item.platform_label || _socialPlatformLabel(String(item.platform || ''), isRu)}
                                        {' · '}
                                        {isRu ? 'готов' : 'ready'}
                                      </span>
                                    ))}
                                    {(socialLaunchPreflight.first_api_publish_readiness.fast_start_blocked_platforms || []).slice(0, 2).map((item) => (
                                      <span
                                        key={`fast-api-blocked:${String(item.platform || '')}`}
                                        className="rounded-full bg-amber-950/20 px-2 py-0.5 font-medium text-amber-50"
                                      >
                                        {item.platform_label || _socialPlatformLabel(String(item.platform || ''), isRu)}
                                        {' · '}
                                        {String(item.status || 'not_ready')}
                                      </span>
                                    ))}
                                  </div>
                                ) : null}
                                {(
                                  isRu
                                    ? socialLaunchPreflight.first_api_publish_readiness.safe_path_ru
                                    : socialLaunchPreflight.first_api_publish_readiness.safe_path_en
                                )?.length ? (
                                  <ol className="mt-2 grid gap-1 sm:grid-cols-2">
                                    {(
                                      isRu
                                        ? socialLaunchPreflight.first_api_publish_readiness.safe_path_ru
                                        : socialLaunchPreflight.first_api_publish_readiness.safe_path_en
                                    )?.slice(0, 5).map((step, index) => (
                                      <li key={`fast-api-safe-path:${index}:${step}`} className="flex gap-1.5 text-slate-100">
                                        <span className="font-semibold text-white">{index + 1}.</span>
                                        <span>{step}</span>
                                      </li>
                                    ))}
                                  </ol>
                                ) : null}
                                {(socialLaunchPreflight.first_api_publish_readiness.pre_proof_checks || []).length > 0 ? (
                                  <div
                                    data-testid="social-first-api-pre-proof-checks"
                                    className="mt-2 rounded-lg border border-white/10 bg-white/10 px-2 py-2"
                                  >
                                    <div className="font-semibold text-white">
                                      {isRu ? 'Проверка перед первым API-proof' : 'Check before first API proof'}
                                    </div>
                                    <div className="mt-1 space-y-2">
                                      {(socialLaunchPreflight.first_api_publish_readiness.pre_proof_checks || []).slice(0, 3).map((check) => (
                                        <div key={`first-api-pre-proof:${String(check.key || check.platform || '')}`} className="rounded-md bg-white/10 px-2 py-1.5 text-slate-100">
                                          <div className="font-semibold text-white">
                                            {isRu
                                              ? String(check.label_ru || 'Проверить API-канал без публикации')
                                              : String(check.label_en || 'Check API channel without publishing')}
                                          </div>
                                          <div className="mt-0.5">
                                            {isRu ? String(check.message_ru || '') : String(check.message_en || '')}
                                          </div>
                                          <div className="mt-0.5">
                                            <span className="font-semibold text-white">{isRu ? 'Что сделать: ' : 'Next: '}</span>
                                            {isRu ? String(check.action_ru || '') : String(check.action_en || '')}
                                          </div>
                                          {check.endpoint ? (
                                            <div className="mt-0.5 text-[10px] text-slate-200">
                                              {String(check.endpoint)}
                                              {' · '}
                                              {check.external_post_published === false
                                                ? (isRu ? 'без публикации' : 'no publish')
                                                : ''}
                                            </div>
                                          ) : null}
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                ) : null}
                              </div>
                              <div className="mt-1 font-medium text-white">
                                {isRu
                                  ? String(socialLaunchPreflight.first_api_publish_readiness.next_action_ru || '')
                                  : String(socialLaunchPreflight.first_api_publish_readiness.next_action_en || '')}
                              </div>
                              {(
                                isRu
                                  ? socialLaunchPreflight.first_api_publish_readiness.first_post_checklist_ru
                                  : socialLaunchPreflight.first_api_publish_readiness.first_post_checklist_en
                              )?.length ? (
                                <div className="mt-2 rounded-lg bg-white/10 px-2 py-2">
                                  <div className="font-semibold text-white">
                                    {isRu ? 'Чеклист первого API-поста' : 'First API post checklist'}
                                  </div>
                                  <ol className="mt-1 space-y-1">
                                    {(
                                      isRu
                                        ? socialLaunchPreflight.first_api_publish_readiness.first_post_checklist_ru
                                        : socialLaunchPreflight.first_api_publish_readiness.first_post_checklist_en
                                    )?.slice(0, 5).map((step, index) => (
                                      <li key={`first-api-checklist:${index}:${step}`} className="flex gap-1.5 text-slate-100">
                                        <span className="font-semibold text-white">{index + 1}.</span>
                                        <span>{step}</span>
                                      </li>
                                    ))}
                                  </ol>
                                </div>
                              ) : null}
                              {(
                                isRu
                                  ? socialLaunchPreflight.first_api_publish_readiness.first_api_launch_plan_ru
                                  : socialLaunchPreflight.first_api_publish_readiness.first_api_launch_plan_en
                              )?.length ? (
                                <div
                                  data-testid="social-first-api-launch-plan"
                                  className="mt-2 rounded-lg bg-white/10 px-2 py-2"
                                >
                                  <div className="font-semibold text-white">
                                    {isRu ? 'План первого API-поста' : 'First API post launch plan'}
                                  </div>
                                  <ol className="mt-1 space-y-1">
                                    {(
                                      isRu
                                        ? socialLaunchPreflight.first_api_publish_readiness.first_api_launch_plan_ru
                                        : socialLaunchPreflight.first_api_publish_readiness.first_api_launch_plan_en
                                    )?.slice(0, 5).map((step, index) => (
                                      <li key={`first-api-launch-plan:${index}:${step}`} className="flex gap-1.5 text-slate-100">
                                        <span className="font-semibold text-white">{index + 1}.</span>
                                        <span>{step}</span>
                                      </li>
                                    ))}
                                  </ol>
                                  <div className="mt-2 rounded-md bg-white/10 px-2 py-1 text-slate-100">
                                    <span className="font-semibold text-white">
                                      {isRu ? 'Почему этот канал: ' : 'Why this channel: '}
                                    </span>
                                    {isRu
                                      ? String(socialLaunchPreflight.first_api_publish_readiness.recommended_start_reason_ru || '')
                                      : String(socialLaunchPreflight.first_api_publish_readiness.recommended_start_reason_en || '')}
                                  </div>
                                  <div className="mt-1 rounded-md bg-white/10 px-2 py-1 text-slate-100">
                                    <span className="font-semibold text-white">
                                      {isRu ? 'Proof-check: ' : 'Proof check: '}
                                    </span>
                                    {isRu
                                      ? String(socialLaunchPreflight.first_api_publish_readiness.proof_check_ru || 'После первого запуска проверьте provider_post_id/provider_post_url; без этого цикл не доказан.')
                                      : String(socialLaunchPreflight.first_api_publish_readiness.proof_check_en || 'After the first run, check provider_post_id/provider_post_url; without that, the loop is not proven.')}
                                  </div>
                                  <div className="mt-1 rounded-md bg-white/10 px-2 py-1 text-slate-100">
                                    <span className="font-semibold text-white">
                                      {isRu ? 'После публикации: ' : 'After publishing: '}
                                    </span>
                                    {isRu
                                      ? String(socialLaunchPreflight.first_api_publish_readiness.metrics_followup_ru || 'После первого подтверждённого запуска соберите реакции/заявки; следующий план не меняется автоматически без подтверждения.')
                                      : String(socialLaunchPreflight.first_api_publish_readiness.metrics_followup_en || 'After proof, collect reactions/leads; the next plan is not changed automatically without approval.')}
                                  </div>
                                </div>
                              ) : null}
                              <div className="mt-1 text-slate-200">
                                {isRu
                                  ? String(socialLaunchPreflight.first_api_publish_readiness.publish_path_ru || 'Только после предпросмотра, подтверждения, расписания и наступления даты.')
                                  : String(socialLaunchPreflight.first_api_publish_readiness.publish_path_en || 'Only after preview, human approval, queueing, and the due date.')}
                              </div>
                            </div>
                          ) : null}
                          {socialLaunchPreflight.launch_rehearsal ? (
                            <div
                              data-testid="social-launch-rehearsal"
                              className={[
                                'mt-2 rounded-lg border px-2 py-2 text-[11px] leading-5',
                                Number(socialLaunchPreflight.launch_rehearsal.summary?.manual_or_blocked || 0) > 0
                                  ? 'border-amber-200/30 bg-amber-400/10 text-amber-50'
                                  : Number(socialLaunchPreflight.launch_rehearsal.summary?.ready || 0) > 0
                                    ? 'border-emerald-200/30 bg-emerald-400/10 text-emerald-50'
                                    : 'border-sky-200/30 bg-sky-400/10 text-sky-50',
                              ].join(' ')}
                            >
                              <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
                                <div>
                                  <div className="font-semibold text-white">
                                    {isRu ? 'Проверка постов на текущую дату' : 'Due-post launch check'}
                                  </div>
                                  <div className="mt-1">
                                    {isRu
                                      ? String(socialLaunchPreflight.launch_rehearsal.summary?.message_ru || '')
                                      : String(socialLaunchPreflight.launch_rehearsal.summary?.message_en || '')}
                                  </div>
                                </div>
                                <span className="shrink-0 rounded-full bg-white/10 px-2 py-0.5 font-semibold text-white">
                                  {String(socialLaunchPreflight.launch_rehearsal.summary?.status || 'empty')}
                                </span>
                              </div>
                              <div className="mt-2 grid gap-1 sm:grid-cols-4">
                                <div className="rounded-md bg-white/10 px-2 py-1">
                                  <span className="font-semibold text-white">{Number(socialLaunchPreflight.launch_rehearsal.summary?.ready || 0)}</span>
                                  {' '}
                                  {isRu ? 'готово' : 'ready'}
                                </div>
                                <div className="rounded-md bg-white/10 px-2 py-1">
                                  <span className="font-semibold text-white">{Number(socialLaunchPreflight.launch_rehearsal.summary?.api_ready || 0)}</span>
                                  {' '}
                                  API
                                </div>
                                <div className="rounded-md bg-white/10 px-2 py-1">
                                  <span className="font-semibold text-white">{Number(socialLaunchPreflight.launch_rehearsal.summary?.supervised_ready || 0)}</span>
                                  {' '}
                                  {isRu ? 'контроль' : 'supervised'}
                                </div>
                                <div className="rounded-md bg-white/10 px-2 py-1">
                                  <span className="font-semibold text-white">{Number(socialLaunchPreflight.launch_rehearsal.summary?.manual_or_blocked || 0)}</span>
                                  {' '}
                                  {isRu ? 'внимание' : 'attention'}
                                </div>
                              </div>
                              <div className="mt-2 font-medium text-white">
                                {isRu ? 'Следующий шаг: ' : 'Next step: '}
                                {isRu
                                  ? String(socialLaunchPreflight.launch_rehearsal.summary?.next_action_ru || '')
                                  : String(socialLaunchPreflight.launch_rehearsal.summary?.next_action_en || '')}
                              </div>
                              <div className="mt-1 text-slate-200">
                                {isRu
                                  ? 'Проверка запуска: наружу ничего не отправлено, provider write не выполнялся, финальный клик в Яндекс/2ГИС запрещён.'
                                  : 'Launch check: nothing was sent externally, provider write did not run, and the Yandex/2GIS final click is disabled.'}
                              </div>
                            </div>
                          ) : null}
                          {socialLaunchPreflight.next_action_ru || socialLaunchPreflight.next_action_en ? (
                            <div className="mt-1 font-medium text-white">
                              {isRu ? 'Следующий шаг: ' : 'Next step: '}
                              {isRu
                                ? String(socialLaunchPreflight.next_action_ru || '')
                                : String(socialLaunchPreflight.next_action_en || '')}
                            </div>
                          ) : null}
                          {Number(socialLaunchPreflight.api_preflight_blocked_due_posts?.length || 0) > 0 ? (
                            <div className="mt-2 rounded-lg border border-amber-200/30 bg-amber-950/20 px-2 py-2 text-[11px] leading-5 text-amber-50">
                              <div className="font-semibold text-white">
                                {isRu ? 'Live API-preflight остановил запуск' : 'Live API preflight blocked launch'}
                              </div>
                              <div className="mt-1">
                                {isRu
                                  ? 'Исполнитель не будет запущен, пока API-посты с наступившей датой смотрят в канал без готовых ключей, прав, локации или адаптера.'
                                  : 'The worker will not run while due API posts target a channel without ready keys, permissions, location, or adapter.'}
                              </div>
                              <div className="mt-1 flex flex-wrap gap-1">
                                {(socialLaunchPreflight.api_preflight_blocked_due_posts || []).slice(0, 4).map((item) => (
                                  <div
                                    key={`launch-api-block:${String(item.id || '')}:${String(item.platform || '')}`}
                                    className="rounded-lg bg-white/10 px-2 py-1.5 text-amber-50"
                                  >
                                    <div className="flex flex-wrap items-center justify-between gap-2">
                                      <span className="font-semibold text-white">
                                        {item.platform_label || _socialPlatformLabel(String(item.platform || ''), isRu)}
                                        {' · '}
                                        {String(item.status || 'not_ready')}
                                      </span>
                                      {item.settings_path ? (
                                        <button
                                          type="button"
                                          className="rounded-full bg-white/10 px-2 py-0.5 text-[10px] font-semibold text-white hover:bg-white/20"
                                          onClick={() => navigate(String(item.settings_path || _socialSettingsPathForPlatform(String(item.platform || ''))))}
                                        >
                                          {isRu ? 'Открыть настройку' : 'Open setup'}
                                        </button>
                                      ) : null}
                                    </div>
                                    {(isRu ? item.message_ru : item.message_en) ? (
                                      <div className="mt-1 text-amber-100">
                                        {isRu ? String(item.message_ru || '') : String(item.message_en || '')}
                                      </div>
                                    ) : null}
                                    {(isRu ? item.next_action_ru : item.next_action_en) ? (
                                      <div className="mt-1 font-medium text-white">
                                        {isRu ? 'Что сделать: ' : 'What to do: '}
                                        {isRu ? String(item.next_action_ru || '') : String(item.next_action_en || '')}
                                      </div>
                                    ) : null}
                                    <div className="mt-1 text-[10px] leading-4 text-amber-100">
                                      {isRu
                                        ? String(item.safety_summary_ru || 'Исполнитель не будет публиковать этот пост, пока канал не пройдёт live API-проверку.')
                                        : String(item.safety_summary_en || 'The worker will not publish this due post until the channel passes live API preflight.')}
                                    </div>
                                  </div>
                                ))}
                              </div>
                            </div>
                          ) : null}
                          <div className="mt-2 rounded-lg bg-white/10 px-2 py-1.5 text-[11px] text-slate-200">
                            {isRu
                              ? `Рекомендованный бизнес для запуска: SOCIAL_POST_DISPATCH_BUSINESS_ID=${String(socialLaunchPreflight.recommended_env?.dispatch?.SOCIAL_POST_DISPATCH_BUSINESS_ID || businessId || '')}`
                              : `Recommended scope: SOCIAL_POST_DISPATCH_BUSINESS_ID=${String(socialLaunchPreflight.recommended_env?.dispatch?.SOCIAL_POST_DISPATCH_BUSINESS_ID || businessId || '')}`}
                          </div>
                          {socialLaunchPreflight.runtime_alignment ? (
                            <div className="mt-2 rounded-lg bg-white/10 px-2 py-1.5 text-[11px] leading-5 text-slate-200">
                              <div className="flex items-center justify-between gap-2">
                                <span className="font-semibold text-white">
                                  {isRu ? 'Исполнитель этого бизнеса' : 'This business runtime'}
                                </span>
                                <span
                                  className={[
                                    'rounded-full px-2 py-0.5 font-semibold',
                                    socialLaunchPreflight.runtime_alignment.dispatch?.can_process_this_business
                                      ? 'bg-emerald-400/20 text-emerald-100'
                                      : 'bg-amber-400/20 text-amber-100',
                                  ].join(' ')}
                                >
                                  {socialLaunchPreflight.runtime_alignment.dispatch?.can_process_this_business
                                    ? (isRu ? 'совпадает' : 'matches')
                                    : (isRu ? 'нужно настроить' : 'needs setup')}
                                </span>
                              </div>
                              <div className="mt-1">
                                {isRu
                                  ? String(socialLaunchPreflight.runtime_alignment.dispatch?.message_ru || '')
                                  : String(socialLaunchPreflight.runtime_alignment.dispatch?.message_en || '')}
                              </div>
                              <div className="mt-1">
                                {isRu
                                  ? String(socialLaunchPreflight.runtime_alignment.metrics?.message_ru || '')
                                  : String(socialLaunchPreflight.runtime_alignment.metrics?.message_en || '')}
                              </div>
                              {(socialLaunchPreflight.runtime_alignment.next_action_ru || socialLaunchPreflight.runtime_alignment.next_action_en) ? (
                                <div className="mt-1 font-medium text-white">
                                  {isRu
                                    ? String(socialLaunchPreflight.runtime_alignment.next_action_ru || '')
                                    : String(socialLaunchPreflight.runtime_alignment.next_action_en || '')}
                                </div>
                              ) : null}
                            </div>
                          ) : null}
                          {socialLaunchPreflight.launch_gate ? (
                            <div
                              data-testid="social-first-cycle-launch-gate"
                              className={[
                                'mt-2 rounded-lg border px-2 py-2 text-[11px] leading-5',
                                socialLaunchPreflight.launch_gate.allowed
                                  ? 'border-emerald-200/30 bg-emerald-400/10 text-emerald-50'
                                  : 'border-amber-200/30 bg-amber-950/20 text-amber-50',
                              ].join(' ')}
                            >
                              <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
                                <div>
                                  <div className="font-semibold text-white">
                                    {isRu ? 'Можно ли запускать сейчас' : 'Can run now'}
                                    {' · '}
                                    {isRu
                                      ? String(socialLaunchPreflight.launch_gate.title_ru || '')
                                      : String(socialLaunchPreflight.launch_gate.title_en || '')}
                                  </div>
                                  <div className="mt-1">
                                    {isRu
                                      ? String(socialLaunchPreflight.launch_gate.summary_ru || '')
                                      : String(socialLaunchPreflight.launch_gate.summary_en || '')}
                                  </div>
                                </div>
                                <span className="shrink-0 rounded-full bg-white/10 px-2 py-0.5 font-semibold text-white">
                                  {socialLaunchPreflight.launch_gate.allowed
                                    ? (isRu ? 'разрешено' : 'allowed')
                                    : (isRu ? 'стоп' : 'blocked')}
                                </span>
                              </div>
                              <div className="mt-2 grid gap-1 sm:grid-cols-4">
                                <div className="rounded-md bg-white/10 px-2 py-1">
                                  <span className="font-semibold text-white">{Number(socialLaunchPreflight.launch_gate.api_posts || 0)}</span>
                                  {' '}
                                  {isRu ? 'API' : 'API'}
                                </div>
                                <div className="rounded-md bg-white/10 px-2 py-1">
                                  <span className="font-semibold text-white">{Number(socialLaunchPreflight.launch_gate.supervised_posts || 0)}</span>
                                  {' '}
                                  {isRu ? 'контроль' : 'supervised'}
                                </div>
                                <div className="rounded-md bg-white/10 px-2 py-1">
                                  <span className="font-semibold text-white">{Number(socialLaunchPreflight.launch_gate.manual_posts || 0)}</span>
                                  {' '}
                                  {isRu ? 'вручную' : 'manual'}
                                </div>
                                <div className="rounded-md bg-white/10 px-2 py-1">
                                  <span className="font-semibold text-white">{Number(socialLaunchPreflight.launch_gate.blocked_posts || 0)}</span>
                                  {' '}
                                  {isRu ? 'блокеры' : 'blocked'}
                                </div>
                              </div>
                              <div className="mt-2 font-medium text-white">
                                {isRu ? 'Следующий шаг: ' : 'Next step: '}
                                {isRu
                                  ? String(socialLaunchPreflight.launch_gate.next_action_ru || '')
                                  : String(socialLaunchPreflight.launch_gate.next_action_en || '')}
                              </div>
                              <div className="mt-1 text-slate-200">
                                {isRu
                                  ? 'Нажатие запуска всё равно требует подтверждения; Яндекс/2ГИС без финального клика.'
                                  : 'Running still requires confirmation; Yandex/2GIS keep the final click disabled.'}
                              </div>
                            </div>
                          ) : null}
                          {socialLaunchPreflight.first_api_proof_gate ? (
                            <div
                              data-testid="social-first-api-proof-gate"
                              data-schema="localos_social_first_api_proof_gate_v1"
                              className={[
                                'mt-2 rounded-lg border px-2 py-2 text-[11px] leading-5',
                                socialLaunchPreflight.first_api_proof_gate.allowed
                                  ? 'border-emerald-200/30 bg-emerald-400/10 text-emerald-50'
                                  : 'border-amber-200/30 bg-amber-950/20 text-amber-50',
                              ].join(' ')}
                            >
                              <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
                                <div>
                                  <div className="font-semibold text-white">
                                    {isRu ? 'Первый API-proof' : 'First API proof'}
                                    {' · '}
                                    {isRu
                                      ? String(socialLaunchPreflight.first_api_proof_gate.title_ru || '')
                                      : String(socialLaunchPreflight.first_api_proof_gate.title_en || '')}
                                  </div>
                                  <div className="mt-1">
                                    {isRu
                                      ? String(socialLaunchPreflight.first_api_proof_gate.summary_ru || '')
                                      : String(socialLaunchPreflight.first_api_proof_gate.summary_en || '')}
                                  </div>
                                </div>
                                <span className="shrink-0 rounded-full bg-white/10 px-2 py-0.5 font-semibold text-white">
                                  {socialLaunchPreflight.first_api_proof_gate.allowed
                                    ? (isRu ? 'можно проверить' : 'can verify')
                                    : (isRu ? 'не готово' : 'not ready')}
                                </span>
                              </div>
                              <div className="mt-2 grid gap-1 sm:grid-cols-3">
                                <div className="rounded-md bg-white/10 px-2 py-1">
                                  <span className="font-semibold text-white">
                                    {socialLaunchPreflight.first_api_proof_gate.ui_run_once_allowed ? (isRu ? 'да' : 'yes') : (isRu ? 'нет' : 'no')}
                                  </span>
                                  {' '}
                                  {isRu ? 'запуск из LocalOS' : 'LocalOS run'}
                                </div>
                                <div className="rounded-md bg-white/10 px-2 py-1">
                                  <span className="font-semibold text-white">
                                    {socialLaunchPreflight.first_api_proof_gate.background_worker_aligned ? (isRu ? 'да' : 'yes') : (isRu ? 'нет' : 'no')}
                                  </span>
                                  {' '}
                                  {isRu ? 'бизнес запуска' : 'worker scope'}
                                </div>
                                <div className="rounded-md bg-white/10 px-2 py-1">
                                  <span className="font-semibold text-white">
                                    {Number(socialLaunchPreflight.first_api_proof_gate.blocked_posts || 0)}
                                  </span>
                                  {' '}
                                  {isRu ? 'блокеры' : 'blockers'}
                                </div>
                              </div>
                              {socialLaunchPreflight.first_api_proof_gate.candidate?.ready ? (
                                <div className="mt-2 rounded-md bg-white/10 px-2 py-1.5 text-slate-100">
                                  <div className="font-semibold text-white">
                                    {socialLaunchPreflight.first_api_proof_gate.candidate.platform_label
                                      || _socialPlatformLabel(String(socialLaunchPreflight.first_api_proof_gate.candidate.platform || ''), isRu)}
                                  </div>
                                  <div>
                                    {isRu
                                      ? String(socialLaunchPreflight.first_api_proof_gate.candidate.proof_check_ru || 'После запуска должен появиться provider_post_id/provider_post_url.')
                                      : String(socialLaunchPreflight.first_api_proof_gate.candidate.proof_check_en || 'After launch, provider_post_id/provider_post_url must appear.')}
                                  </div>
                                </div>
                              ) : null}
                              <div className="mt-2 font-medium text-white">
                                {isRu ? 'Следующий шаг: ' : 'Next step: '}
                                {isRu
                                  ? String(socialLaunchPreflight.first_api_proof_gate.next_action_ru || '')
                                  : String(socialLaunchPreflight.first_api_proof_gate.next_action_en || '')}
                              </div>
                            </div>
                          ) : null}
                          {socialLaunchPreflight.first_cycle_proof_packet ? (
                            <div
                              data-testid="social-first-cycle-proof-packet"
                              data-schema="localos_social_first_cycle_proof_packet_v1"
                              className={[
                                'mt-2 rounded-lg border px-2 py-2 text-[11px] leading-5',
                                socialLaunchPreflight.first_cycle_proof_packet.ready_to_run_once
                                  ? 'border-emerald-200/30 bg-emerald-400/10 text-emerald-50'
                                  : 'border-amber-200/30 bg-amber-950/20 text-amber-50',
                              ].join(' ')}
                            >
                              <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
                                <div>
                                  <div className="font-semibold text-white">
                                    {isRu ? 'Пакет первого запуска' : 'First-cycle proof packet'}
                                  </div>
                                  <div className="mt-1">
                                    {isRu
                                      ? String(socialLaunchPreflight.first_cycle_proof_packet.run_once_action_ru || '')
                                      : String(socialLaunchPreflight.first_cycle_proof_packet.run_once_action_en || '')}
                                  </div>
                                </div>
                                <span className="shrink-0 rounded-full bg-white/10 px-2 py-0.5 font-semibold text-white">
                                  {socialLaunchPreflight.first_cycle_proof_packet.ready_to_run_once
                                    ? (isRu ? 'можно один цикл' : 'one cycle ready')
                                    : (isRu ? 'не готово' : 'not ready')}
                                </span>
                              </div>
                              <div className="mt-2 grid gap-1 sm:grid-cols-3">
                                <div className="rounded-md bg-white/10 px-2 py-1">
                                  <span className="font-semibold text-white">
                                    {String(socialLaunchPreflight.first_cycle_proof_packet.dispatch_business_id || '-')}
                                  </span>
                                  {' '}
                                  {isRu ? 'бизнес запуска' : 'dispatch scope'}
                                </div>
                                <div className="rounded-md bg-white/10 px-2 py-1">
                                  <span className="font-semibold text-white">
                                    {socialLaunchPreflight.first_cycle_proof_packet.candidate_platform_label
                                      || _socialPlatformLabel(String(socialLaunchPreflight.first_cycle_proof_packet.candidate_platform || ''), isRu)
                                      || '-'}
                                  </span>
                                  {' '}
                                  API-proof
                                </div>
                                <div className="rounded-md bg-white/10 px-2 py-1">
                                  <span className="font-semibold text-white">
                                    {Number(socialLaunchPreflight.first_cycle_proof_packet.checklist_done || 0)}
                                    /
                                    {Number(socialLaunchPreflight.first_cycle_proof_packet.checklist_total || 0)}
                                  </span>
                                  {' '}
                                  {isRu ? 'чеклист' : 'checklist'}
                                </div>
                              </div>
                              {socialLaunchPreflight.first_cycle_proof_packet.external_publish_confirmation_phrase ? (
                                <div
                                  data-testid="social-first-cycle-confirmation-phrase"
                                  className="mt-2 rounded-md border border-white/10 bg-white/10 px-2 py-1.5 text-slate-100"
                                >
                                  <div className="font-semibold text-white">
                                    {isRu ? 'Фраза подтверждения внешней публикации' : 'External publish confirmation phrase'}
                                  </div>
                                  <div className="mt-1">
                                    {isRu
                                      ? String(socialLaunchPreflight.first_cycle_proof_packet.external_publish_confirmation_ru || '')
                                      : String(socialLaunchPreflight.first_cycle_proof_packet.external_publish_confirmation_en || '')}
                                  </div>
                                  <div className="mt-1 inline-flex rounded-md bg-white/15 px-2 py-0.5 font-mono text-[11px] font-semibold text-white">
                                    {String(socialLaunchPreflight.first_cycle_proof_packet.external_publish_confirmation_phrase || '')}
                                  </div>
                                </div>
                              ) : null}
                              {socialLaunchPreflight.first_cycle_proof_packet.ready_to_run_once ? (
                                <div className="mt-2 rounded-md bg-white/10 px-2 py-1.5 text-slate-100">
                                  <div className="font-semibold text-white">
                                    {isRu ? 'Что проверить после цикла' : 'What to verify after the cycle'}
                                  </div>
                                  <ol className="mt-1 space-y-1">
                                    {(
                                      isRu
                                        ? socialLaunchPreflight.first_cycle_proof_packet.after_run_checks_ru || []
                                        : socialLaunchPreflight.first_cycle_proof_packet.after_run_checks_en || []
                                    ).slice(0, 4).map((step, index) => (
                                      <li key={`first-cycle-proof-check:${index}:${step}`} className="flex gap-1.5">
                                        <span className="font-semibold text-white">{index + 1}.</span>
                                        <span>{step}</span>
                                      </li>
                                    ))}
                                  </ol>
                                </div>
                              ) : (
                                <div className="mt-2 rounded-md bg-white/10 px-2 py-1.5 text-amber-50">
                                  <span className="font-semibold text-white">
                                    {isRu ? 'Что мешает: ' : 'Blocked by: '}
                                  </span>
                                  {isRu
                                    ? String(socialLaunchPreflight.first_cycle_proof_packet.blocked_reason_ru || '')
                                    : String(socialLaunchPreflight.first_cycle_proof_packet.blocked_reason_en || '')}
                                </div>
                              )}
                            </div>
                          ) : null}
                          {Number(socialLaunchPreflight.live_validation_checklist?.length || 0) > 0 ? (
                            <div
                              data-testid="social-live-validation-checklist"
                              className="mt-2 rounded-lg border border-sky-200/30 bg-sky-400/10 px-2 py-2 text-[11px] leading-5 text-sky-50"
                            >
                              <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
                                <div>
                                  <div className="font-semibold text-white">
                                    {isRu ? 'Чеклист живой проверки' : 'Live validation checklist'}
                                  </div>
                                  <div className="mt-1 text-sky-100">
                                    {isRu
                                      ? 'Эти пункты показывают, доказан ли полный loop: публикация, контроль карт, сбор результата и корректировка плана.'
                                      : 'These items show whether the full loop is proven: publishing, map control, result collection, and plan correction.'}
                                  </div>
                                </div>
                                <span className="shrink-0 rounded-full bg-white/10 px-2 py-0.5 font-semibold text-white">
                                  {Number(socialLaunchPreflight.live_validation_checklist?.filter((item) => item.status === 'done').length || 0)}
                                  /
                                  {Number(socialLaunchPreflight.live_validation_checklist?.length || 0)}
                                </span>
                              </div>
                              <div className="mt-2 grid gap-2 md:grid-cols-2">
                                {(socialLaunchPreflight.live_validation_checklist || []).map((item) => {
                                  const itemStatus = String(item.status || '').trim();
                                  const tone = itemStatus === 'done'
                                    ? 'border-emerald-200/30 bg-emerald-400/10 text-emerald-50'
                                    : itemStatus === 'attention'
                                      ? 'border-amber-200/30 bg-amber-400/10 text-amber-50'
                                      : itemStatus === 'current'
                                        ? 'border-sky-200/40 bg-white/10 text-sky-50'
                                        : 'border-slate-200/20 bg-white/5 text-slate-100';
                                  return (
                                    <div
                                      key={`live-validation:${String(item.key || item.label_ru || item.label_en || '')}`}
                                      className={`rounded-lg border px-2 py-1.5 ${tone}`}
                                    >
                                      <div className="flex items-start justify-between gap-2">
                                        <span className="font-semibold text-white">
                                          {isRu ? String(item.label_ru || '') : String(item.label_en || '')}
                                        </span>
                                        <span className="shrink-0 rounded-full bg-white/10 px-2 py-0.5 text-[10px] font-medium text-white">
                                          {_socialLearningChecklistStatusLabel(itemStatus, isRu)}
                                        </span>
                                      </div>
                                      <div className="mt-1">
                                        {isRu ? String(item.detail_ru || '') : String(item.detail_en || '')}
                                      </div>
                                    </div>
                                  );
                                })}
                              </div>
                            </div>
                          ) : null}
                          <Button
                            type="button"
                            size="sm"
                            onClick={() => { void runSocialDispatchOnce(); }}
                            disabled={
                              Boolean(bulkBusyAction)
                              || Boolean(socialBusyAction)
                              || !(socialLaunchPreflight.launch_gate?.allowed ?? socialLaunchPreflight.safe_to_enable_scoped_dispatch)
                            }
                            className="mt-2 h-8 bg-white text-slate-950 hover:bg-slate-100"
                          >
                            {socialBusyAction === 'dispatch-run-once'
                              ? (isRu ? 'Запускаем цикл...' : 'Running cycle...')
                              : (isRu ? 'Запустить один ограниченный цикл' : 'Run one scoped cycle')}
                          </Button>
                          <div className="mt-1 text-[11px] text-slate-300">
                            {isRu
                              ? 'Запускает только посты текущего бизнеса, у которых наступила дата. API может опубликовать подтверждённые посты в расписании; Яндекс/2ГИС останутся в контролируемом или ручном размещении.'
                              : 'Runs only due posts for the current business. API may publish approved/queued posts; Yandex/2GIS stay supervised or manual.'}
                          </div>
                          <div className="mt-2 rounded-lg bg-slate-950/30 px-2 py-2 text-[11px] text-slate-100 ring-1 ring-white/10">
                            <div className="font-semibold text-white">
                              {isRu ? 'Команды для безопасного запуска' : 'Safe launch env'}
                            </div>
                            <div className="mt-1 space-y-0.5 font-mono text-[10px] leading-4 text-slate-200">
                              {_socialWorkerEnvLines(
                                socialLaunchPreflight.recommended_env?.dispatch || {},
                                socialLaunchPreflight.recommended_env?.metrics || {},
                              ).map((line) => (
                                <div key={line} className="break-all">{line}</div>
                              ))}
                            </div>
                              <Button
                                type="button"
                                size="sm"
                              variant="outline"
                              className="mt-2 h-7 border-white/20 bg-white/10 px-2 text-[11px] text-white hover:bg-white/20"
                              onClick={() => { void copySocialWorkerEnv(); }}
                            >
                              {isRu ? 'Скопировать настройки запуска' : 'Copy worker env'}
                            </Button>
                          </div>
                          {_socialFirstCycleVerificationBlock(socialLaunchPreflight.first_cycle_verification, isRu)}
                          {_socialLaunchRunbookBlock(socialLaunchPreflight.launch_runbook, isRu)}
                          <div className="mt-1 text-[11px] text-slate-300">
                            {isRu
                              ? 'Проверка ничего не публикует: подтверждение обязательно, карты остаются контролируемыми или ручными без финального клика.'
                              : 'Preflight publishes nothing: approval is required, and maps stay supervised without the final click.'}
                          </div>
                        </div>
                      ) : null}
                      {socialDispatchExecutionReport ? (
                        <div
                          data-testid="social-dispatch-execution-report"
                          className={[
                            'rounded-xl border px-3 py-2 text-xs leading-5',
                            Number(socialDispatchExecutionReport.failed || 0) > 0
                              ? 'border-red-300/30 bg-red-400/10 text-red-100'
                              : Number(socialDispatchExecutionReport.manual || 0) > 0
                                ? 'border-amber-300/30 bg-amber-400/10 text-amber-100'
                                : 'border-emerald-300/30 bg-emerald-400/10 text-emerald-100',
                          ].join(' ')}
                        >
                          <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
                            <div>
                              <div className="font-semibold text-white">
                                {isRu ? 'Результат последнего запуска' : 'Last launch result'}
                                {' · '}
                                {isRu
                                  ? String(socialDispatchExecutionReport.title_ru || '')
                                  : String(socialDispatchExecutionReport.title_en || '')}
                              </div>
                              <div className="mt-1">
                                {isRu
                                  ? String(socialDispatchExecutionReport.summary_ru || '')
                                  : String(socialDispatchExecutionReport.summary_en || '')}
                              </div>
                            </div>
                            <span className="shrink-0 rounded-full bg-white/10 px-2 py-0.5 text-[11px] font-semibold text-white">
                              {String(socialDispatchExecutionReport.status || 'empty')}
                            </span>
                          </div>
                          <div className="mt-2 grid gap-1 sm:grid-cols-5">
                            <div className="rounded-md bg-white/10 px-2 py-1">
                              <span className="font-semibold text-white">{Number(socialDispatchExecutionReport.published || 0)}</span>
                              {' '}
                              {isRu ? 'опубликовано' : 'published'}
                            </div>
                            <div className="rounded-md bg-white/10 px-2 py-1">
                              <span className="font-semibold text-white">{Number(socialDispatchExecutionReport.supervised || 0)}</span>
                              {' '}
                              {isRu ? 'контроль' : 'supervised'}
                            </div>
                            <div className="rounded-md bg-white/10 px-2 py-1">
                              <span className="font-semibold text-white">{Number(socialDispatchExecutionReport.manual || 0)}</span>
                              {' '}
                              {isRu ? 'вручную' : 'manual'}
                            </div>
                            <div className="rounded-md bg-white/10 px-2 py-1">
                              <span className="font-semibold text-white">{Number(socialDispatchExecutionReport.failed || 0)}</span>
                              {' '}
                              {isRu ? 'ошибки' : 'failed'}
                            </div>
                            <div className="rounded-md bg-white/10 px-2 py-1">
                              <span className="font-semibold text-white">{Number(socialDispatchExecutionReport.provider_write_summary?.published_with_provider_proof || 0)}</span>
                              {' '}
                              proof
                            </div>
                          </div>
                          <div className="mt-2 font-medium text-white">
                            {isRu ? 'Следующий шаг: ' : 'Next step: '}
                            {isRu
                              ? String(socialDispatchExecutionReport.next_action_ru || '')
                              : String(socialDispatchExecutionReport.next_action_en || '')}
                          </div>
                          {socialDispatchExecutionReport.after_run_proof_packet ? (
                            <div
                              data-testid="social-after-run-proof-packet"
                              data-schema="localos_social_after_run_proof_packet_v1"
                              className={[
                                'mt-2 rounded-lg border px-2 py-2 text-[11px] leading-5',
                                socialDispatchExecutionReport.after_run_proof_packet.can_collect_results
                                  ? 'border-emerald-300/20 bg-emerald-400/10 text-emerald-50'
                                  : Number(socialDispatchExecutionReport.after_run_proof_packet.failed || 0) > 0
                                    ? 'border-red-300/20 bg-red-400/10 text-red-50'
                                    : 'border-amber-300/20 bg-amber-400/10 text-amber-50',
                              ].join(' ')}
                            >
                              <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
                                <div>
                                  <div className="font-semibold text-white">
                                    {isRu ? 'Проверка после запуска' : 'After-run proof'}
                                    {' · '}
                                    {isRu
                                      ? String(socialDispatchExecutionReport.after_run_proof_packet.title_ru || '')
                                      : String(socialDispatchExecutionReport.after_run_proof_packet.title_en || '')}
                                  </div>
                                  <div className="mt-1">
                                    {isRu
                                      ? String(socialDispatchExecutionReport.after_run_proof_packet.next_action_ru || '')
                                      : String(socialDispatchExecutionReport.after_run_proof_packet.next_action_en || '')}
                                  </div>
                                </div>
                                <span className="shrink-0 rounded-full bg-white/10 px-2 py-0.5 font-semibold text-white">
                                  {socialDispatchExecutionReport.after_run_proof_packet.api_proof_ready
                                    ? 'API proof'
                                    : (isRu ? 'proof нужен' : 'proof needed')}
                                </span>
                              </div>
                              <div className="mt-2 grid gap-1 sm:grid-cols-3">
                                <div className="rounded-md bg-white/10 px-2 py-1">
                                  <span className="font-semibold text-white">
                                    {socialDispatchExecutionReport.after_run_proof_packet.can_collect_results ? (isRu ? 'да' : 'yes') : (isRu ? 'нет' : 'no')}
                                  </span>
                                  {' '}
                                  {isRu ? 'собирать результат' : 'collect results'}
                                </div>
                                <div className="rounded-md bg-white/10 px-2 py-1">
                                  <span className="font-semibold text-white">
                                    {socialDispatchExecutionReport.after_run_proof_packet.maps_handoff_created ? (isRu ? 'да' : 'yes') : (isRu ? 'нет' : 'no')}
                                  </span>
                                  {' '}
                                  {isRu ? 'карты handoff' : 'maps handoff'}
                                </div>
                                <div className="rounded-md bg-white/10 px-2 py-1">
                                  <span className="font-semibold text-white">
                                    {socialDispatchExecutionReport.after_run_proof_packet.browser_final_click_allowed === false
                                      ? (isRu ? 'человек' : 'human')
                                      : (isRu ? 'неясно' : 'unclear')}
                                  </span>
                                  {' '}
                                  {isRu ? 'финальный клик' : 'final click'}
                                </div>
                              </div>
                              <ol className="mt-2 space-y-1">
                                {(
                                  isRu
                                    ? socialDispatchExecutionReport.after_run_proof_packet.checks_ru || []
                                    : socialDispatchExecutionReport.after_run_proof_packet.checks_en || []
                                ).slice(0, 4).map((step, index) => (
                                  <li key={`after-run-proof:${index}:${step}`} className="flex gap-1.5 text-slate-100">
                                    <span className="font-semibold text-white">{index + 1}.</span>
                                    <span>{step}</span>
                                  </li>
                                ))}
                              </ol>
                            </div>
                          ) : null}
                          {socialDispatchExecutionReport.first_api_proof_summary ? (
                            <div
                              data-testid="social-first-api-proof-summary"
                              className={[
                                'mt-2 rounded-lg border px-2 py-2 text-[11px] leading-5',
                                socialDispatchExecutionReport.first_api_proof_summary.ready
                                  ? 'border-emerald-300/20 bg-emerald-400/10 text-emerald-50'
                                  : 'border-amber-300/20 bg-amber-400/10 text-amber-50',
                              ].join(' ')}
                            >
                              <div className="font-semibold text-white">
                                {isRu ? 'Proof первого API-loop' : 'First API-loop proof'}
                              </div>
                              <div>
                                {isRu
                                  ? String(socialDispatchExecutionReport.first_api_proof_summary.summary_ru || '')
                                  : String(socialDispatchExecutionReport.first_api_proof_summary.summary_en || '')}
                              </div>
                              <div className="mt-1 text-slate-100">
                                {isRu ? 'Проверено API-постов: ' : 'API posts checked: '}
                                {Number(socialDispatchExecutionReport.first_api_proof_summary.api_posts_checked || 0)}
                                {' · '}
                                {isRu ? 'с provider_post_id/provider_post_url: ' : 'with provider_post_id/provider_post_url: '}
                                {Number(socialDispatchExecutionReport.first_api_proof_summary.published_with_provider_proof || 0)}
                              </div>
                              {socialDispatchExecutionReport.first_api_proof_summary.provider_post_url || socialDispatchExecutionReport.first_api_proof_summary.provider_post_id ? (
                                <div className="mt-1 break-all text-slate-100">
                                  {String(
                                    socialDispatchExecutionReport.first_api_proof_summary.provider_post_url
                                    || socialDispatchExecutionReport.first_api_proof_summary.provider_post_id
                                    || ''
                                  )}
                                </div>
                              ) : null}
                              <div className="mt-1 font-medium text-white">
                                {isRu
                                  ? String(socialDispatchExecutionReport.first_api_proof_summary.next_action_ru || '')
                                  : String(socialDispatchExecutionReport.first_api_proof_summary.next_action_en || '')}
                              </div>
                            </div>
                          ) : null}
                          <div className="mt-1 text-[11px] text-slate-200">
                            {isRu
                              ? 'API-публикации возможны только после подтверждения и расписания; Яндекс/2ГИС остаются контролируемыми или ручными без финального клика.'
                              : 'API publishes only after approval/queue; Yandex/2GIS stay supervised/manual without the final click.'}
                          </div>
                          {socialDispatchExecutionReport.post_publish_learning_gate ? (
                            <div
                              data-testid="social-post-publish-learning-gate"
                              data-schema="localos_social_post_publish_learning_gate_v1"
                              className={[
                                'mt-2 rounded-lg border px-2 py-2 text-[11px] leading-5',
                                socialDispatchExecutionReport.post_publish_learning_gate.allowed
                                  ? 'border-emerald-300/20 bg-emerald-400/10 text-emerald-50'
                                  : 'border-amber-300/20 bg-amber-400/10 text-amber-50',
                              ].join(' ')}
                            >
                              <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
                                <div>
                                  <div className="font-semibold text-white">
                                    {isRu ? 'Сбор реакций и заявок' : 'Reactions and leads'}
                                  </div>
                                  <div className="mt-1">
                                    {isRu
                                      ? String(socialDispatchExecutionReport.post_publish_learning_gate.summary_ru || '')
                                      : String(socialDispatchExecutionReport.post_publish_learning_gate.summary_en || '')}
                                  </div>
                                </div>
                                <span className="shrink-0 rounded-full bg-white/10 px-2 py-0.5 font-semibold text-white">
                                  {socialDispatchExecutionReport.post_publish_learning_gate.allowed
                                    ? (isRu ? 'можно собирать' : 'can collect')
                                    : (isRu ? 'сначала publish' : 'publish first')}
                                </span>
                              </div>
                              <div className="mt-2 grid gap-1 sm:grid-cols-3">
                                <div className="rounded-md bg-white/10 px-2 py-1">
                                  <span className="font-semibold text-white">
                                    {Number(socialDispatchExecutionReport.post_publish_learning_gate.published_posts || 0)}
                                  </span>
                                  {' '}
                                  {isRu ? 'published' : 'published'}
                                </div>
                                <div className="rounded-md bg-white/10 px-2 py-1">
                                  <span className="font-semibold text-white">
                                    {Number(socialDispatchExecutionReport.post_publish_learning_gate.published_with_api_proof || 0)}
                                  </span>
                                  {' '}
                                  API proof
                                </div>
                                <div className="rounded-md bg-white/10 px-2 py-1">
                                  <span className="font-semibold text-white">
                                    {isRu
                                      ? String(socialDispatchExecutionReport.post_publish_learning_gate.primary_metric_ru || 'Заявки и обращения')
                                      : String(socialDispatchExecutionReport.post_publish_learning_gate.primary_metric_en || 'Leads and inquiries')}
                                  </span>
                                </div>
                              </div>
                              <div className="mt-2 font-medium text-white">
                                {isRu ? 'Следующий шаг: ' : 'Next step: '}
                                {isRu
                                  ? String(socialDispatchExecutionReport.post_publish_learning_gate.next_action_ru || '')
                                  : String(socialDispatchExecutionReport.post_publish_learning_gate.next_action_en || '')}
                              </div>
                              {(socialDispatchExecutionReport.post_publish_learning_gate.learning_actions || []).length > 0 ? (
                                <div
                                  data-testid="social-post-publish-learning-actions"
                                  className="mt-2 rounded-md bg-white/10 px-2 py-1.5"
                                >
                                  <div className="font-semibold text-white">
                                    {isRu ? 'Порядок после публикации' : 'After-publish sequence'}
                                  </div>
                                  <ol className="mt-1 space-y-1">
                                    {(socialDispatchExecutionReport.post_publish_learning_gate.learning_actions || [])
                                      .slice()
                                      .sort((left, right) => Number(left.order || 0) - Number(right.order || 0))
                                      .slice(0, 4)
                                      .map((action) => (
                                        <li key={`publish-learning-action:${String(action.key || action.label_ru || action.label_en || '')}`} className="flex gap-1.5 text-slate-100">
                                          <span className="font-semibold text-white">{Number(action.order || 0) || ''}</span>
                                          <span>
                                            <span className="font-semibold text-white">
                                              {isRu ? String(action.label_ru || '') : String(action.label_en || '')}
                                            </span>
                                            {action.primary_metric ? (
                                              <span className="ml-1 rounded-full bg-emerald-400/20 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-50">
                                                {isRu ? 'главный KPI' : 'main KPI'}
                                              </span>
                                            ) : null}
                                            <span className="block text-slate-200">
                                              {isRu ? String(action.summary_ru || '') : String(action.summary_en || '')}
                                            </span>
                                          </span>
                                        </li>
                                      ))}
                                  </ol>
                                </div>
                              ) : null}
                            </div>
                          ) : null}
                          <div
                            data-testid="social-post-publish-to-learning-next-step"
                            className="mt-2 rounded-lg bg-white/10 px-2 py-2"
                          >
                            <div className="text-[11px] font-semibold text-white">
                              {isRu ? 'После публикации' : 'After publishing'}
                            </div>
                            <div className="mt-1 text-[11px] leading-4 text-slate-200">
                              {isRu
                                ? 'Следующий шаг в loop: собрать реакции, отметить заявки/обращения и пересчитать следующий контент-план. Изменения плана не применяются автоматически.'
                                : 'Next loop step: collect reactions, mark leads/inquiries, and recalculate the next content plan. Plan changes are not applied automatically.'}
                            </div>
                            <div className="mt-2 flex flex-wrap gap-2">
                              <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                className="h-7 border-white/20 bg-white/10 px-2 text-[11px] text-white hover:bg-white/20"
                                onClick={() => { void collectSocialPostMetricsForBusiness(); }}
                                disabled={
                                  socialBusyAction === 'collect-metrics'
                                  || Number(socialDispatchExecutionReport.published || 0) <= 0
                                }
                              >
                                {socialBusyAction === 'collect-metrics'
                                  ? (isRu ? 'Собираем...' : 'Collecting...')
                                  : (isRu ? 'Собрать реакции' : 'Collect reactions')}
                              </Button>
                              <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                className="h-7 border-white/20 bg-white/10 px-2 text-[11px] text-white hover:bg-white/20"
                                onClick={selectPublishedSocialPostsForResult}
                                disabled={visibleSocialPublishedPosts.length === 0}
                              >
                                {isRu ? 'Отметить заявки/обращения' : 'Record leads/inquiries'}
                              </Button>
                              <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                className="h-7 border-white/20 bg-white/10 px-2 text-[11px] text-white hover:bg-white/20"
                                onClick={() => { void recommendNextSocialPlan(); }}
                                disabled={socialBusyAction === 'recommend'}
                              >
                                {socialBusyAction === 'recommend'
                                  ? (isRu ? 'Считаем...' : 'Calculating...')
                                  : (isRu ? 'Предложить изменения' : 'Suggest changes')}
                              </Button>
                            </div>
                          </div>
                          {Number(socialDispatchExecutionReport.details?.length || 0) > 0 ? (
                            <div className="mt-2 space-y-1">
                              {(socialDispatchExecutionReport.details || []).slice(0, 4).map((item) => (
                                <div
                                  key={`dispatch-report:${String(item.id || '')}:${String(item.platform || '')}`}
                                  className="rounded-lg bg-white/10 px-2 py-1.5 text-[11px] leading-4 text-slate-100"
                                >
                                  <div className="flex items-center justify-between gap-2">
                                    <span className="font-medium text-white">
                                      {_socialPlatformLabel(String(item.platform || ''), isRu)}
                                    </span>
                                    <span>{String(item.status || '')}</span>
                                  </div>
                                  {item.provider_post_url || item.provider_post_id || item.automation_task_id || item.last_error ? (
                                    <div className="mt-0.5 break-all text-slate-200">
                                      {item.provider_post_url
                                        ? String(item.provider_post_url)
                                        : item.provider_post_id
                                          ? `provider id: ${String(item.provider_post_id)}`
                                          : item.automation_task_id
                                            ? `task: ${String(item.automation_task_id)}`
                                            : String(item.last_error || '')}
                                    </div>
                                  ) : null}
                                </div>
                              ))}
                            </div>
                          ) : null}
                        </div>
                      ) : null}
                      {socialDispatchPreview ? (
                        <div
                          data-testid="social-dispatch-preview-panel"
                          className="rounded-xl bg-white/10 px-3 py-2 text-xs leading-5 text-slate-200"
                        >
                          <div className="font-semibold text-white">
                            {isRu ? 'Проверка исполнителя' : 'Worker dry-run'}
                          </div>
                          <div>
                            {isRu
                              ? `К дате: ${Number(socialDispatchPreview.picked || 0)} · API: ${Number(socialDispatchPreview.by_action?.publish_api || 0)} · контролируемо: ${Number(socialDispatchPreview.by_action?.create_supervised_task || 0)} · вручную: ${Number(socialDispatchPreview.by_action?.manual_handoff || 0)}`
                              : `Due: ${Number(socialDispatchPreview.picked || 0)} · API: ${Number(socialDispatchPreview.by_action?.publish_api || 0)} · supervised: ${Number(socialDispatchPreview.by_action?.create_supervised_task || 0)} · manual: ${Number(socialDispatchPreview.by_action?.manual_handoff || 0)}`}
                          </div>
                          <div className="text-[11px] text-slate-300">
                            {isRu ? 'Внешняя публикация не запускалась.' : 'No external publishing was started.'}
                          </div>
                          <div className="text-[11px] text-slate-300">
                            {socialDispatchPreview.business_scope
                              ? (isRu
                                ? `Проверка ограничена бизнесом: ${String(socialDispatchPreview.business_scope)}`
                                : `Dry-run scoped to business: ${String(socialDispatchPreview.business_scope)}`)
                              : (isRu ? 'Проверка без ограничения по бизнесу.' : 'Dry-run is not business-scoped.')}
                          </div>
                          {socialDispatchPreview.readiness?.message_ru || socialDispatchPreview.readiness?.message_en ? (
                            <div
                              className={[
                                'mt-2 rounded-lg border px-2 py-1.5 text-[11px] leading-5',
                                socialDispatchPreview.readiness?.has_external_publish
                                  ? 'border-emerald-300/20 bg-emerald-400/10 text-emerald-100'
                                  : socialDispatchPreview.readiness?.has_manual_fallback
                                    ? 'border-amber-300/20 bg-amber-400/10 text-amber-100'
                                    : 'border-slate-300/20 bg-white/10 text-slate-200',
                              ].join(' ')}
                            >
                              <div className="font-semibold">
                                {isRu ? 'Вывод перед запуском' : 'Dispatch readiness'}
                              </div>
                              <div>
                                {isRu
                                  ? String(socialDispatchPreview.readiness?.message_ru || '')
                                  : String(socialDispatchPreview.readiness?.message_en || '')}
                              </div>
                              {socialDispatchPreview.readiness?.next_action_ru || socialDispatchPreview.readiness?.next_action_en ? (
                                <div className="mt-1 font-medium text-white">
                                  {isRu ? 'Следующий шаг: ' : 'Next step: '}
                                  {isRu
                                    ? String(socialDispatchPreview.readiness?.next_action_ru || '')
                                    : String(socialDispatchPreview.readiness?.next_action_en || '')}
                                </div>
                              ) : null}
                              <div className="mt-1 text-slate-300">
                                {isRu
                                  ? `API ${Number(socialDispatchPreview.readiness?.external_publish_count || 0)} · контролируемо ${Number(socialDispatchPreview.readiness?.controlled_count || 0)} · вручную ${Number(socialDispatchPreview.readiness?.manual_count || 0)}`
                                  : `external ${Number(socialDispatchPreview.readiness?.external_publish_count || 0)} · supervised ${Number(socialDispatchPreview.readiness?.controlled_count || 0)} · manual ${Number(socialDispatchPreview.readiness?.manual_count || 0)}`}
                              </div>
                            </div>
                          ) : null}
                          {socialDispatchPreview.readiness?.first_api_proof_candidate ? (
                            <div
                              data-testid="social-first-api-proof-candidate"
                              className={[
                                'mt-2 rounded-lg border px-2 py-2 text-[11px] leading-5',
                                socialDispatchPreview.readiness.first_api_proof_candidate.ready
                                  ? 'border-emerald-300/20 bg-emerald-400/10 text-emerald-50'
                                  : 'border-slate-300/20 bg-white/10 text-slate-200',
                              ].join(' ')}
                            >
                              <div className="font-semibold text-white">
                                {isRu ? 'Кандидат на первый API-proof' : 'First API-proof candidate'}
                              </div>
                              <div>
                                {socialDispatchPreview.readiness.first_api_proof_candidate.ready
                                  ? (isRu
                                    ? `${String(socialDispatchPreview.readiness.first_api_proof_candidate.platform_label || '')}: после worker должен появиться provider_post_id/provider_post_url.`
                                    : `${String(socialDispatchPreview.readiness.first_api_proof_candidate.platform_label || '')}: after the worker runs, provider_post_id/provider_post_url must appear.`)
                                  : (isRu
                                    ? 'Нет due API-поста для доказательства loop.'
                                    : 'No due API post is available to prove the loop.')}
                              </div>
                              <div className="mt-1 text-slate-100">
                                {isRu
                                  ? String(socialDispatchPreview.readiness.first_api_proof_candidate.proof_check_ru || '')
                                  : String(socialDispatchPreview.readiness.first_api_proof_candidate.proof_check_en || '')}
                              </div>
                              <div className="mt-1 text-slate-100">
                                {isRu
                                  ? String(socialDispatchPreview.readiness.first_api_proof_candidate.metrics_followup_ru || '')
                                  : String(socialDispatchPreview.readiness.first_api_proof_candidate.metrics_followup_en || '')}
                              </div>
                            </div>
                          ) : null}
                          {_socialFirstCycleVerificationBlock(socialDispatchPreview.readiness?.first_cycle_verification, isRu)}
                          {Number(socialDispatchPreview.readiness?.first_cycle_steps?.length || 0) > 0 ? (
                            <div className="mt-2 rounded-lg border border-sky-300/20 bg-sky-400/10 px-2 py-2 text-[11px] leading-5 text-sky-50">
                              <div className="font-semibold text-white">
                                {isRu ? 'Что сделает первый цикл' : 'What the first cycle will do'}
                              </div>
                              <div className="mt-1 space-y-1.5">
                                {(socialDispatchPreview.readiness?.first_cycle_steps || []).map((step) => (
                                  <div key={String(step.key || step.label_ru || step.label_en)} className="rounded-md bg-white/10 px-2 py-1.5">
                                    <div className="flex items-center justify-between gap-2">
                                      <span className="font-medium text-white">
                                        {isRu ? String(step.label_ru || '') : String(step.label_en || '')}
                                      </span>
                                      <span className="shrink-0 rounded-full bg-white/10 px-2 py-0.5 text-[10px] font-semibold text-white">
                                        {Number(step.count || 0)}
                                      </span>
                                    </div>
                                    <div className="mt-0.5 text-sky-100">
                                      {isRu ? String(step.description_ru || '') : String(step.description_en || '')}
                                    </div>
                                    <div className="mt-0.5 text-sky-200">
                                      {isRu ? 'Ожидаемый статус: ' : 'Expected status: '}
                                      {isRu ? String(step.expected_status_ru || '') : String(step.expected_status_en || '')}
                                    </div>
                                  </div>
                                ))}
                              </div>
                            </div>
                          ) : null}
                          {Number((isRu ? socialDispatchPreview.readiness?.safety_notes_ru : socialDispatchPreview.readiness?.safety_notes_en)?.length || 0) > 0 ? (
                            <div className="mt-2 rounded-lg bg-white/10 px-2 py-1.5 text-[11px] leading-5 text-slate-200">
                              <div className="font-semibold text-white">
                                {isRu ? 'Границы безопасности' : 'Safety boundaries'}
                              </div>
                              {((isRu ? socialDispatchPreview.readiness?.safety_notes_ru : socialDispatchPreview.readiness?.safety_notes_en) || []).map((note) => (
                                <div key={String(note)}>{String(note)}</div>
                              ))}
                            </div>
                          ) : null}
                          {Number(socialDispatchPreview.items?.length || 0) > 0 ? (
                            <div className="mt-2 space-y-1">
                              {(socialDispatchPreview.items || []).slice(0, 5).map((item) => (
                                <div key={String(item.id || `${item.platform}-${item.dispatch_action}`)} className="rounded-lg bg-white/10 px-2 py-1.5">
                                  <div className="flex items-center justify-between gap-2">
                                    <span className="truncate font-medium text-white">
                                      {String(item.platform_label || _socialPlatformLabel(String(item.platform || ''), isRu))}
                                    </span>
                                    <span className="shrink-0 text-[11px] text-slate-200">
                                      {isRu
                                        ? String(item.action_label_ru || _socialDispatchActionLabel(String(item.dispatch_action || ''), isRu))
                                        : String(item.action_label_en || _socialDispatchActionLabel(String(item.dispatch_action || ''), false))}
                                    </span>
                                  </div>
                                  {item.would_status ? (
                                    <div className="mt-0.5 text-[11px] font-medium text-slate-200">
                                      {isRu ? 'Итог: ' : 'Result: '}
                                      {String(item.would_status || '')}
                                    </div>
                                  ) : null}
                                  {item.reason ? (
                                    <div className="mt-0.5 line-clamp-2 text-[11px] text-slate-300">
                                      {isRu
                                        ? String(item.reason_label_ru || _socialDispatchReasonLabel(String(item.reason || ''), isRu))
                                        : String(item.reason_label_en || _socialDispatchReasonLabel(String(item.reason || ''), false))}
                                    </div>
                                  ) : null}
                                  {item.safety_summary_ru || item.safety_summary_en ? (
                                    <div className="mt-1 rounded-md bg-black/10 px-2 py-1 text-[11px] leading-4 text-slate-200">
                                      {isRu ? String(item.safety_summary_ru || '') : String(item.safety_summary_en || '')}
                                    </div>
                                  ) : null}
                                </div>
                              ))}
                              {Number(socialDispatchPreview.items?.length || 0) > 5 ? (
                                <div className="text-[11px] text-slate-300">
                                  {isRu
                                    ? `Ещё ${Number(socialDispatchPreview.items?.length || 0) - 5} в этом dry-run.`
                                    : `${Number(socialDispatchPreview.items?.length || 0) - 5} more in this dry-run.`}
                                </div>
                              ) : null}
                            </div>
                          ) : null}
                        </div>
                      ) : null}
                    </div>
                  </div>
                </div>
                <div
                  data-testid="social-launch-readiness"
                  className="mt-4 rounded-2xl border border-slate-200 bg-white px-4 py-4"
                >
                  <div className="flex flex-col gap-2 lg:flex-row lg:items-start lg:justify-between">
                    <div>
                      <div className="text-sm font-semibold text-slate-950">
                        {isRu ? 'Готовность к рабочему запуску' : 'Launch readiness'}
                      </div>
                      <div className="mt-1 text-xs leading-5 text-slate-500">
                        {isRu
                          ? 'Короткий путь до полного цикла: подготовить каналы, проверить тексты, поставить в расписание, выполнить публикации и собрать результат.'
                          : 'The short path to a full loop: prepare channels, review copy, queue, publish, and collect results.'}
                      </div>
                    </div>
                    <div className="rounded-xl bg-slate-50 px-3 py-2 text-xs leading-5 text-slate-600 lg:max-w-[360px]">
                      <span className="font-semibold text-slate-900">
                        {isRu ? 'Главный ориентир: ' : 'Main signal: '}
                      </span>
                      {isRu
                        ? 'заявки и обращения важнее охватов; изменения плана применяются только после подтверждения.'
                        : 'leads and inquiries matter more than reach; plan changes apply only after confirmation.'}
                    </div>
                  </div>
                  <div className="mt-3 grid gap-2 md:grid-cols-2 xl:grid-cols-3">
                    {socialLaunchStages.map((stage) => (
                      <div
                        key={stage.key}
                        className={[
                          'rounded-xl border px-3 py-3',
                          stage.status === 'done'
                            ? 'border-emerald-100 bg-emerald-50'
                            : stage.status === 'current'
                              ? 'border-sky-100 bg-sky-50'
                              : stage.status === 'attention'
                                ? 'border-red-100 bg-red-50'
                                : 'border-slate-200 bg-slate-50',
                        ].join(' ')}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div>
                            <div
                              className={[
                                'text-xs font-semibold',
                                stage.status === 'done'
                                  ? 'text-emerald-950'
                                  : stage.status === 'current'
                                    ? 'text-sky-950'
                                    : stage.status === 'attention'
                                      ? 'text-red-950'
                                      : 'text-slate-700',
                              ].join(' ')}
                            >
                              {isRu ? stage.labelRu : stage.labelEn}
                            </div>
                            <div
                              className={[
                                'mt-1 text-xs leading-5',
                                stage.status === 'done'
                                  ? 'text-emerald-800'
                                  : stage.status === 'current'
                                    ? 'text-sky-800'
                                    : stage.status === 'attention'
                                      ? 'text-red-800'
                                      : 'text-slate-500',
                              ].join(' ')}
                            >
                              {isRu ? stage.detailRu : stage.detailEn}
                            </div>
                          </div>
                          <span
                            className={[
                              'shrink-0 rounded-full px-2 py-0.5 text-[11px] font-semibold',
                              stage.status === 'done'
                                ? 'bg-white text-emerald-700'
                                : stage.status === 'current'
                                  ? 'bg-white text-sky-700'
                                  : stage.status === 'attention'
                                    ? 'bg-white text-red-700'
                                    : 'bg-white text-slate-500',
                            ].join(' ')}
                          >
                            {stage.status === 'done'
                              ? (isRu ? 'готово' : 'done')
                              : stage.status === 'current'
                                ? (isRu ? 'сейчас' : 'now')
                                : stage.status === 'attention'
                                  ? (isRu ? 'внимание' : 'attention')
                                  : (isRu ? 'позже' : 'later')}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
                <div
                  data-testid="social-channel-queue"
                  className="mt-4 flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between"
                >
                  <div>
                    <div className="text-sm font-semibold text-slate-950">
                      {isRu ? 'Очередь публикаций по каналам' : 'Channel publishing queue'}
                    </div>
                    <div className="mt-1 text-xs leading-5 text-slate-500">
                      {isRu
                        ? 'Здесь видно, что нужно проверить, что готово к API и где требуется контролируемое размещение.'
                        : 'See what needs review, what is API-ready, and where supervised placement is required.'}
                    </div>
                  </div>
                  {Number(socialSummary?.total || 0) > 0 ? (
                    <div className="text-xs font-medium text-slate-500">
                      {isRu ? `Всего публикаций: ${socialSummary?.total || 0}` : `Posts: ${socialSummary?.total || 0}`}
                    </div>
                  ) : null}
                </div>
                {socialQueueGroups.length > 0 ? (
                  <div className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-6">
                    {socialQueueGroups.map((group) => (
                      <div key={group.key} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-3">
                        <div className="flex items-center justify-between gap-2">
                          <div className="text-xs font-semibold text-slate-700">
                            {_socialQueueGroupLabel(group, isRu)}
                          </div>
                          <div className="rounded-full bg-white px-2 py-0.5 text-xs font-semibold text-slate-900">
                            {group.count || 0}
                          </div>
                        </div>
                        <div className="mt-2 min-h-[40px] text-xs leading-5 text-slate-500">
                          {_socialQueueGroupNextAction(group, isRu)}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="mt-3 rounded-xl border border-dashed border-slate-200 bg-slate-50 px-3 py-3 text-sm leading-6 text-slate-600">
                    {isRu
                      ? 'Подготовьте каналы для тем плана, чтобы увидеть рабочую очередь публикаций.'
                      : 'Prepare channels for plan items to see the publishing workload.'}
                  </div>
                )}
                {socialChannelReadiness.length > 0 ? (
                  <>
                    <div className="mt-3 rounded-xl border border-slate-200 bg-white px-3 py-3">
                      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                        <div>
                          <div className="text-sm font-semibold text-slate-950">
                            {isRu ? 'Готовность каналов' : 'Channel readiness'}
                          </div>
                          <div className="mt-1 text-xs leading-5 text-slate-600">
                            {socialReadinessSummary.blockedApiChannels.length > 0
                              ? (isRu
                                ? 'Перед постановкой API-каналов в расписание подключите ключи или права. Карты останутся контролируемыми или ручными и не будут выглядеть как автопубликация.'
                                : 'Connect keys or permissions before queueing API channels. Maps stay supervised/manual and are not shown as autopublish.')
                              : (isRu
                                ? 'API-каналы готовы к публикации после подтверждения. Карты идут через контролируемое или ручное размещение.'
                                : 'API channels are ready to publish after approval. Maps use supervised placement.')}
                          </div>
                          {socialOpenClawReadiness ? (
                            (() => {
                              const openClawOperational = _socialOpenClawReadinessOperational(socialOpenClawReadiness);
                              return (
                                <div className={[
                                  'mt-3 rounded-lg border px-3 py-2 text-xs leading-5',
                                  openClawOperational
                                    ? 'border-sky-100 bg-sky-50 text-sky-800'
                                    : 'border-amber-100 bg-amber-50 text-amber-800',
                                ].join(' ')}
                                >
                                  <div className={openClawOperational ? 'font-semibold text-sky-950' : 'font-semibold text-amber-950'}>
                                    {_socialOpenClawReadinessTitle(socialOpenClawReadiness, isRu)}
                                  </div>
                                  <div className="mt-1">
                                    {isRu ? socialOpenClawReadiness.message_ru : socialOpenClawReadiness.message_en}
                                  </div>
                                  <div className="mt-1 font-medium">
                                    {isRu ? socialOpenClawReadiness.next_action_ru : socialOpenClawReadiness.next_action_en}
                                  </div>
                                  {_socialOpenClawReadinessDetails(socialOpenClawReadiness, isRu).length > 0 ? (
                                    <ul className="mt-2 space-y-1">
                                      {_socialOpenClawReadinessDetails(socialOpenClawReadiness, isRu).slice(0, 4).map((detail) => (
                                        <li key={`openclaw-readiness:${detail}`} className="flex gap-2">
                                          <span className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-current opacity-70" />
                                          <span>{detail}</span>
                                        </li>
                                      ))}
                                    </ul>
                                  ) : null}
                                  <div className="mt-2 rounded-md bg-white/70 px-2 py-1.5 text-[11px] leading-4">
                                    {_socialOpenClawOwnerCheckSummary(socialOpenClawReadiness, isRu)}
                                  </div>
                                  <Button
                                    type="button"
                                    size="sm"
                                    variant="outline"
                                    className="mt-2 h-7 rounded-lg bg-white/80 px-2 text-[11px]"
                                    onClick={() => { void checkOpenClawBrowserReadiness(); }}
                                    disabled={socialBusyAction === 'openclaw-check'}
                                  >
                                    {socialBusyAction === 'openclaw-check'
                                      ? (isRu ? 'Проверяем...' : 'Checking...')
                                      : (isRu ? 'Проверить OpenClaw сейчас' : 'Check OpenClaw now')}
                                  </Button>
                                </div>
                              );
                            })()
                          ) : null}
                          {socialReadinessSummary.blockedApiChannels.length > 0 ? (
                            <div className="mt-3 flex flex-wrap gap-2">
                              <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                onClick={() => navigate(socialReadinessSetupPath)}
                              >
                                {isRu ? 'Настроить нужный канал' : 'Open required setup'}
                              </Button>
                              <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                className="bg-white"
                                onClick={() => { void checkApiChannelPreflight(); }}
                                disabled={socialBusyAction === 'api-channel-preflight'}
                              >
                                {socialBusyAction === 'api-channel-preflight'
                                  ? (isRu ? 'Проверяем API...' : 'Checking API...')
                                  : (isRu ? 'Проверить API-каналы' : 'Check API channels')}
                              </Button>
                            </div>
                          ) : (
                            <Button
                              type="button"
                              size="sm"
                              variant="outline"
                              className="mt-3 bg-white"
                              onClick={() => { void checkApiChannelPreflight(); }}
                              disabled={socialBusyAction === 'api-channel-preflight'}
                            >
                              {socialBusyAction === 'api-channel-preflight'
                                ? (isRu ? 'Проверяем API...' : 'Checking API...')
                                : (isRu ? 'Проверить API-каналы' : 'Check API channels')}
                            </Button>
                          )}
                        </div>
                        <div className="grid gap-2 text-xs sm:grid-cols-3 lg:min-w-[360px]">
                          <div className="rounded-lg bg-emerald-50 px-3 py-2 text-emerald-800">
                            <div className="font-semibold text-emerald-950">{socialReadinessSummary.apiReady}</div>
                            <div>{isRu ? 'API готовы' : 'API ready'}</div>
                          </div>
                          <div className="rounded-lg bg-amber-50 px-3 py-2 text-amber-800">
                            <div className="font-semibold text-amber-950">{socialReadinessSummary.needsAttention}</div>
                            <div>{isRu ? 'нужно внимание' : 'need attention'}</div>
                          </div>
                          <div className="rounded-lg bg-sky-50 px-3 py-2 text-sky-800">
                            <div className="font-semibold text-sky-950">{socialReadinessSummary.supervisedOrManual}</div>
                            <div>{isRu ? 'контроль/вручную' : 'supervised/manual'}</div>
                          </div>
                        </div>
                      </div>
                      <div
                        data-testid="social-first-api-publish-readiness"
                        className={[
                          'mt-3 rounded-xl border px-3 py-3 text-xs leading-5',
                          socialFirstApiPublishReadiness.readyForFirstApiPublish
                            ? 'border-emerald-100 bg-emerald-50 text-emerald-900'
                            : socialFirstApiPublishReadiness.hasAnyReadyApi
                              ? 'border-sky-100 bg-sky-50 text-sky-900'
                              : 'border-amber-100 bg-amber-50 text-amber-900',
                        ].join(' ')}
                      >
                        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                          <div>
                            <div className={[
                              'text-sm font-semibold',
                              socialFirstApiPublishReadiness.readyForFirstApiPublish
                                ? 'text-emerald-950'
                                : socialFirstApiPublishReadiness.hasAnyReadyApi
                                  ? 'text-sky-950'
                                  : 'text-amber-950',
                            ].join(' ')}
                            >
                              {isRu ? 'Первый API-пост' : 'First API post'}
                            </div>
                            <div className="mt-1">
                              {socialFirstApiPublishReadiness.readyForFirstApiPublish
                                ? (isRu
                                  ? `Каналы готовы к первому реальному API-посту после предпросмотра, подтверждения и расписания: ${socialFirstApiPublishReadiness.readyLabels.join(', ')}.`
                                  : `Channels are ready for the first real API post after preview, approval, and queueing: ${socialFirstApiPublishReadiness.readyLabels.join(', ')}.`)
                                : socialFirstApiPublishReadiness.hasAnyReadyApi
                                  ? (isRu
                                    ? `Можно начинать с готовых каналов: ${socialFirstApiPublishReadiness.readyLabels.join(', ')}. Заблокированные каналы исполнитель пропустит до настройки.`
                                    : `You can start with ready channels: ${socialFirstApiPublishReadiness.readyLabels.join(', ')}. Blocked channels will be skipped until setup is fixed.`)
                                  : (isRu
                                    ? 'Пока нет готового API-канала для первого реального поста. Сначала подключите ключи и права, затем запустите live API-проверку.'
                                    : 'No API channel is ready for the first real post yet. Connect keys and permissions first, then run the live API check.')}
                            </div>
                            <div className="mt-1 font-medium">
                              {socialFirstApiPublishReadiness.hasLiveCheck
                                ? (isRu ? 'Live API-проверка уже выполнена без публикации.' : 'Live API check has already run without publishing.')
                                : (isRu ? 'Для уверенного запуска нажмите “Проверить API-каналы” перед расписанием.' : 'For a confident launch, click “Check API channels” before queueing.')}
                            </div>
                            {socialFirstApiPublishReadiness.blockedLabels.length > 0 ? (
                              <div className="mt-2">
                                <span className="font-semibold">{isRu ? 'Сначала исправить: ' : 'Fix first: '}</span>
                                {socialFirstApiPublishReadiness.blockedLabels.slice(0, 4).join(', ')}
                              </div>
                            ) : null}
                            {socialFirstApiPublishReadiness.setupFocus ? (
                              <div
                                data-testid="social-first-api-setup-checklist"
                                className="mt-3 rounded-lg border border-white bg-white/70 px-3 py-2 text-xs leading-5"
                              >
                                <div className="font-semibold">
                                  {isRu ? 'Мини-чеклист подключения' : 'Connection mini-checklist'}
                                  {' · '}
                                  {socialFirstApiPublishReadiness.setupFocus.platform_label
                                    || _socialPlatformLabel(String(socialFirstApiPublishReadiness.setupFocus.platform || ''), isRu)}
                                </div>
                                {socialFirstApiPublishReadiness.setupFocusSteps.length > 0 ? (
                                  <ol className="mt-1 list-decimal space-y-1 pl-4">
                                    {socialFirstApiPublishReadiness.setupFocusSteps.map((step) => (
                                      <li key={`first-api-setup-step:${step}`}>{step}</li>
                                    ))}
                                  </ol>
                                ) : null}
                                {socialFirstApiPublishReadiness.setupFocusChecks.length > 0 ? (
                                  <div className="mt-2 flex flex-wrap gap-1.5">
                                    {socialFirstApiPublishReadiness.setupFocusChecks.map((check) => (
                                      <span
                                        key={`first-api-setup-check:${String(check.key || '')}`}
                                        className="rounded-full bg-amber-100 px-2 py-0.5 font-medium text-amber-900"
                                      >
                                        {isRu ? String(check.label_ru || check.key || '') : String(check.label_en || check.key || '')}
                                        {': '}
                                        {isRu ? String(check.detail_ru || '') : String(check.detail_en || '')}
                                      </span>
                                    ))}
                                  </div>
                                ) : null}
                                {socialFirstApiPublishReadiness.setupFocusMissingFields.length > 0 ? (
                                  <div className="mt-2 font-mono text-[11px]">
                                    {isRu ? 'Поля: ' : 'Fields: '}
                                    {socialFirstApiPublishReadiness.setupFocusMissingFields.join(', ')}
                                  </div>
                                ) : null}
                              </div>
                            ) : null}
                          </div>
                          <div className="flex shrink-0 flex-wrap gap-2">
                            {socialFirstApiPublishReadiness.firstBlocked ? (
                              <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                className="h-8 rounded-lg bg-white px-2.5 text-[11px]"
                                onClick={() => navigate(socialFirstApiPublishReadiness.firstBlocked?.settings_path || _socialSettingsPathForPlatform(String(socialFirstApiPublishReadiness.firstBlocked?.platform || '')))}
                              >
                                {isRu ? 'Открыть настройку' : 'Open setup'}
                              </Button>
                            ) : null}
                            <Button
                              type="button"
                              size="sm"
                              variant="outline"
                              className="h-8 rounded-lg bg-white px-2.5 text-[11px]"
                              onClick={() => { void checkApiChannelPreflight(); }}
                              disabled={socialBusyAction === 'api-channel-preflight'}
                            >
                              {socialBusyAction === 'api-channel-preflight'
                                ? (isRu ? 'Проверяем...' : 'Checking...')
                                : (isRu ? 'Проверить API' : 'Check API')}
                            </Button>
                          </div>
                        </div>
                      </div>
                      <div
                        data-testid="social-channel-connection-guide"
                        className="mt-3 rounded-xl border border-slate-200 bg-slate-50 px-3 py-3"
                      >
                        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                          <div>
                            <div className="text-sm font-semibold text-slate-950">
                              {isRu ? 'Подключение каналов' : 'Channel setup guide'}
                            </div>
                            <div className="mt-1 text-xs leading-5 text-slate-600">
                              {socialChannelConnectionGuide.readyToStart
                                ? (isRu
                                  ? `Можно начинать с готового API-канала: ${socialChannelConnectionGuide.quickStartCandidate?.platform_label || _socialPlatformLabel(String(socialChannelConnectionGuide.quickStartCandidate?.platform || ''), isRu)}. Остальные каналы LocalOS покажет как “нужно подключить” или “контролируемое размещение”.`
                                  : `You can start with a ready API channel: ${socialChannelConnectionGuide.quickStartCandidate?.platform_label || _socialPlatformLabel(String(socialChannelConnectionGuide.quickStartCandidate?.platform || ''), isRu)}. Other channels stay marked as setup needed or supervised placement.`)
                                : (isRu
                                  ? 'Для первого реального API-поста быстрее всего подключить Telegram или VK. Яндекс/2ГИС останутся контролируемым размещением, а не скрытой автопубликацией.'
                                  : 'For the first real API post, connect Telegram or VK first. Yandex/2GIS stay supervised placement, not hidden autopublish.')}
                            </div>
                            <div className="mt-2 text-xs font-medium text-slate-700">
                              {socialChannelConnectionGuide.recommendedSetup
                                ? (isRu
                                  ? `Первое действие: открыть настройку ${socialChannelConnectionGuide.recommendedSetup.platform_label || _socialPlatformLabel(String(socialChannelConnectionGuide.recommendedSetup.platform || ''), isRu)} и добавить ключи/права.`
                                  : `First action: open ${socialChannelConnectionGuide.recommendedSetup.platform_label || _socialPlatformLabel(String(socialChannelConnectionGuide.recommendedSetup.platform || ''), isRu)} setup and add keys/permissions.`)
                                : (isRu
                                  ? 'Первое действие: подготовить посты, проверить предпросмотр и поставить готовые API-каналы в расписание.'
                                  : 'First action: prepare posts, review the preview, and queue ready API channels.')}
                            </div>
                          </div>
                          <div className="flex shrink-0 flex-wrap gap-2">
                            {socialChannelConnectionGuide.recommendedSetup ? (
                              <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                className="h-8 rounded-lg bg-white px-2.5 text-[11px]"
                                onClick={() => navigate(socialChannelConnectionGuide.recommendedSetup?.settings_path || _socialSettingsPathForPlatform(String(socialChannelConnectionGuide.recommendedSetup?.platform || '')))}
                              >
                                {isRu ? 'Открыть подключение' : 'Open setup'}
                              </Button>
                            ) : null}
                            <Button
                              type="button"
                              size="sm"
                              variant="outline"
                              className="h-8 rounded-lg bg-white px-2.5 text-[11px]"
                              onClick={() => { void checkApiChannelPreflight(); }}
                              disabled={socialBusyAction === 'api-channel-preflight'}
                            >
                              {socialBusyAction === 'api-channel-preflight'
                                ? (isRu ? 'Проверяем...' : 'Checking...')
                                : (isRu ? 'Проверить готовность' : 'Check readiness')}
                            </Button>
                          </div>
                        </div>
                        <div className="mt-3 grid gap-2 md:grid-cols-2 xl:grid-cols-4">
                          {socialChannelConnectionGuide.apiChannels.map((channel) => (
                            <div
                              key={`connection-guide-api:${channel.platform}`}
                              className={channel.ready
                                ? 'rounded-lg border border-emerald-100 bg-white px-3 py-2 text-xs leading-5 text-emerald-800'
                                : 'rounded-lg border border-amber-100 bg-white px-3 py-2 text-xs leading-5 text-amber-800'}
                            >
                              <div className="flex items-center justify-between gap-2">
                                <span className={channel.ready ? 'font-semibold text-emerald-950' : 'font-semibold text-amber-950'}>
                                  {channel.platform_label || _socialPlatformLabel(channel.platform, isRu)}
                                </span>
                                <span className={channel.ready ? 'rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-semibold text-emerald-700' : 'rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-semibold text-amber-700'}>
                                  {_socialChannelConnectionStateLabel(channel, isRu)}
                                </span>
                              </div>
                              <div className="mt-1">
                                {isRu
                                  ? channel.setup_summary_ru || channel.next_action_ru || channel.message_ru
                                  : channel.setup_summary_en || channel.next_action_en || channel.message_en}
                              </div>
                              {channel.target_setup?.schema ? (
                                <div
                                  data-testid={`social-channel-guide-target-setup-${String(channel.platform || '')}`}
                                  className={channel.ready
                                    ? 'mt-2 rounded-lg bg-emerald-50 px-2 py-1.5 text-[11px] leading-4 text-emerald-900'
                                    : 'mt-2 rounded-lg bg-amber-50 px-2 py-1.5 text-[11px] leading-4 text-amber-900'}
                                >
                                  <div className={channel.ready ? 'font-semibold text-emerald-950' : 'font-semibold text-amber-950'}>
                                    {isRu
                                      ? String(channel.target_setup.target_label_ru || 'Цель публикации')
                                      : String(channel.target_setup.target_label_en || 'Publish target')}
                                  </div>
                                  {channel.target_setup.owner_telegram_present ? (
                                    <div
                                      data-testid={`social-channel-guide-owner-telegram-linked-${String(channel.platform || '')}`}
                                      className="mt-1 inline-flex rounded-full bg-sky-100 px-2 py-0.5 text-[10px] font-semibold text-sky-800"
                                    >
                                      {isRu ? 'Владелец подключён' : 'Owner linked'}
                                    </div>
                                  ) : null}
                                  {channel.target_setup.telegram_app_present ? (
                                    <div
                                      data-testid={`social-channel-guide-telegram-app-linked-${String(channel.platform || '')}`}
                                      className="ml-1 mt-1 inline-flex rounded-full bg-violet-100 px-2 py-0.5 text-[10px] font-semibold text-violet-800"
                                    >
                                      {isRu ? 'Telegram app подключён' : 'Telegram app linked'}
                                    </div>
                                  ) : null}
                                  <div className="mt-1">
                                    {isRu
                                      ? String(channel.target_setup.summary_ru || '')
                                      : String(channel.target_setup.summary_en || '')}
                                  </div>
                                  <div className="mt-1 text-slate-600">
                                    {isRu
                                      ? String(channel.target_setup.not_a_target_ru || '')
                                      : String(channel.target_setup.not_a_target_en || '')}
                                  </div>
                                  <div className="mt-1 font-medium">
                                    {isRu
                                      ? String(channel.target_setup.proof_ru || '')
                                      : String(channel.target_setup.proof_en || '')}
                                  </div>
                                </div>
                              ) : null}
                            </div>
                          ))}
                          {socialChannelConnectionGuide.supervisedChannels.length > 0 ? (
                            <div className="rounded-lg border border-sky-100 bg-white px-3 py-2 text-xs leading-5 text-sky-800">
                              <div className="flex items-center justify-between gap-2">
                                <span className="font-semibold text-sky-950">
                                  {isRu ? 'Яндекс/2ГИС' : 'Yandex/2GIS'}
                                </span>
                                <span className="rounded-full bg-sky-50 px-2 py-0.5 text-[10px] font-semibold text-sky-700">
                                  {isRu ? 'контролируемо' : 'supervised'}
                                </span>
                              </div>
                              <div className="mt-1">
                                {isRu
                                  ? 'LocalOS подготовит текст и задачу. Финальный клик остаётся за человеком.'
                                  : 'LocalOS prepares the text and task. The final click stays with a human.'}
                              </div>
                            </div>
                          ) : null}
                        </div>
                      </div>
                      {socialReadinessSummary.blockedApiChannels.length > 0 ? (
                        <div className="mt-3 flex flex-wrap gap-2">
                          {socialReadinessSummary.blockedApiChannels.slice(0, 4).map((channel) => (
                            <span key={channel.platform} className="rounded-full bg-amber-100 px-3 py-1 text-xs font-medium text-amber-800">
                              {channel.platform_label || _socialPlatformLabel(channel.platform, isRu)} · {isRu ? channel.setup_summary_ru || channel.next_action_ru || channel.message_ru : channel.setup_summary_en || channel.next_action_en || channel.message_en}
                            </span>
                          ))}
                        </div>
                      ) : null}
                      {socialApiPreflightSummary.checked > 0 ? (
                        <div className="mt-3 rounded-xl border border-sky-100 bg-sky-50 px-3 py-3 text-xs leading-5 text-sky-900">
                          <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                            <div>
                              <div className="font-semibold text-sky-950">
                                {isRu ? 'Live API-проверка каналов' : 'Live API channel check'}
                              </div>
                              <div className="mt-1 text-sky-800">
                                {isRu
                                  ? `Проверено без публикации: ${socialApiPreflightSummary.checked}. Готово: ${socialApiPreflightSummary.ready.length}. Нужно внимание: ${socialApiPreflightSummary.needsAttention.length}.`
                                  : `Checked without publishing: ${socialApiPreflightSummary.checked}. Ready: ${socialApiPreflightSummary.ready.length}. Needs attention: ${socialApiPreflightSummary.needsAttention.length}.`}
                              </div>
                            </div>
                            <span className="rounded-full bg-white px-2.5 py-1 text-[11px] font-semibold text-sky-800">
                              {isRu ? 'публикация только после подтверждения' : 'publish only after approval'}
                            </span>
                          </div>
                          <div className="mt-2 flex flex-wrap gap-1.5">
                            {socialApiPreflight.map((item) => {
                              const missingFields = (item.missing_fields || []).slice(0, 3);
                              const setupPath = item.settings_path || _socialSettingsPathForPlatform(String(item.platform || ''));
                              return (
                                <span
                                  key={`api-preflight-summary:${String(item.platform || '')}`}
                                  className={
                                    item.ready
                                      ? 'inline-flex flex-wrap items-center gap-1 rounded-full bg-emerald-100 px-2.5 py-1 text-[11px] font-medium text-emerald-800'
                                      : 'inline-flex flex-wrap items-center gap-1 rounded-full bg-white px-2.5 py-1 text-[11px] font-medium text-amber-800'
                                  }
                                >
                                  <span>
                                    {item.platform_label || _socialPlatformLabel(String(item.platform || ''), isRu)}
                                    {' · '}
                                    {item.ready ? (isRu ? 'готов' : 'ready') : String(item.status || (isRu ? 'нужно внимание' : 'needs attention'))}
                                  </span>
                                  {!item.ready && missingFields.length > 0 ? (
                                    <span className="text-[10px] font-semibold text-amber-700">
                                      {missingFields.join(', ')}
                                    </span>
                                  ) : null}
                                  {!item.ready ? (
                                    <button
                                      type="button"
                                      className="rounded-full bg-amber-50 px-1.5 py-0.5 text-[10px] font-semibold text-amber-800 underline-offset-2 hover:underline"
                                      onClick={() => navigate(setupPath)}
                                    >
                                      {isRu ? 'настроить' : 'setup'}
                                    </button>
                                  ) : null}
                                </span>
                              );
                            })}
                          </div>
                          {socialApiPreflightSummary.needsAttention.length > 0 ? (
                            <div className="mt-2 text-sky-800">
                              {isRu
                                ? 'Перед расписанием исправьте ключи, права или используйте ручной режим для заблокированных каналов.'
                                : 'Before queueing, fix keys, permissions, or use manual fallback for blocked channels.'}
                            </div>
                          ) : null}
                        </div>
                      ) : null}
                    </div>
                    <div className="mt-3 grid gap-2 md:grid-cols-2 xl:grid-cols-4">
                      {socialChannelReadiness.map((channel) => (
                        <div
                          key={channel.platform}
                          className={[
                            'rounded-xl border px-3 py-2',
                            channel.ready
                              ? 'border-emerald-100 bg-emerald-50'
                              : 'border-amber-100 bg-amber-50',
                          ].join(' ')}
                        >
                          <div className="flex items-center justify-between gap-2">
                            <div className={channel.ready ? 'text-xs font-semibold text-emerald-950' : 'text-xs font-semibold text-amber-950'}>
                              {channel.platform_label || _socialPlatformLabel(channel.platform, isRu)}
                            </div>
                            <span className={channel.ready ? 'text-[11px] font-medium text-emerald-700' : 'text-[11px] font-medium text-amber-700'}>
                              {channel.ready ? (isRu ? 'готов' : 'ready') : (isRu ? 'нужно внимание' : 'needs attention')}
                            </span>
                          </div>
                          <div className={channel.ready ? 'mt-1 text-xs leading-5 text-emerald-800' : 'mt-1 text-xs leading-5 text-amber-800'}>
                            {isRu ? channel.message_ru : channel.message_en}
                          </div>
                          <div className={channel.ready ? 'mt-2 text-[11px] font-medium text-emerald-700' : 'mt-2 text-[11px] font-medium text-amber-700'}>
                            {_socialPublishModeLabel(channel.publish_mode || '', isRu)}
                          </div>
                          {channel.setup_summary_ru || channel.setup_summary_en ? (
                            <div className={channel.ready ? 'mt-2 rounded-lg bg-white/80 px-2 py-1.5 text-[11px] leading-4 text-emerald-900' : 'mt-2 rounded-lg bg-white/80 px-2 py-1.5 text-[11px] leading-4 text-amber-900'}>
                              <span className="font-semibold">
                                {isRu ? 'Сейчас: ' : 'Now: '}
                              </span>
                              {isRu ? channel.setup_summary_ru : channel.setup_summary_en}
                            </div>
                          ) : null}
                          {channel.next_action_ru || channel.next_action_en ? (
                            <div className={channel.ready ? 'mt-2 rounded-lg bg-white/70 px-2 py-1.5 text-[11px] leading-4 text-emerald-900' : 'mt-2 rounded-lg bg-white/70 px-2 py-1.5 text-[11px] leading-4 text-amber-900'}>
                              <span className="font-semibold">
                                {isRu ? 'Что сделать: ' : 'Next: '}
                              </span>
                              {isRu ? channel.next_action_ru : channel.next_action_en}
                            </div>
                          ) : null}
                          {channel.target_setup?.schema ? (
                            <div
                              data-testid={`social-channel-target-setup-${String(channel.platform || '')}`}
                              data-schema={String(channel.target_setup.schema || 'localos_social_channel_target_setup_v1')}
                              className={channel.ready ? 'mt-2 rounded-lg border border-emerald-100 bg-white/80 px-2 py-1.5 text-[11px] leading-4 text-emerald-900' : 'mt-2 rounded-lg border border-amber-100 bg-white/80 px-2 py-1.5 text-[11px] leading-4 text-amber-900'}
                            >
                              <div className={channel.ready ? 'font-semibold text-emerald-950' : 'font-semibold text-amber-950'}>
                                {isRu
                                  ? String(channel.target_setup.target_label_ru || 'Цель публикации')
                                  : String(channel.target_setup.target_label_en || 'Publish target')}
                              </div>
                              {channel.target_setup.owner_telegram_present ? (
                                <div
                                  data-testid={`social-channel-owner-telegram-linked-${String(channel.platform || '')}`}
                                  className="mt-1 inline-flex rounded-full bg-sky-100 px-2 py-0.5 text-[10px] font-semibold text-sky-800"
                                >
                                  {isRu ? 'Владелец подключён в Telegram' : 'Owner Telegram is linked'}
                                </div>
                              ) : null}
                              {channel.target_setup.telegram_app_present ? (
                                <div
                                  data-testid={`social-channel-telegram-app-linked-${String(channel.platform || '')}`}
                                  className="ml-1 mt-1 inline-flex rounded-full bg-violet-100 px-2 py-0.5 text-[10px] font-semibold text-violet-800"
                                >
                                  {isRu ? 'Telegram app подключён' : 'Telegram app linked'}
                                </div>
                              ) : null}
                              <div className="mt-1">
                                {isRu
                                  ? String(channel.target_setup.summary_ru || '')
                                  : String(channel.target_setup.summary_en || '')}
                              </div>
                              {(isRu ? channel.target_setup.not_a_target_ru : channel.target_setup.not_a_target_en) ? (
                                <div className="mt-1 text-slate-600">
                                  {isRu
                                    ? String(channel.target_setup.not_a_target_ru || '')
                                    : String(channel.target_setup.not_a_target_en || '')}
                                </div>
                              ) : null}
                              {((isRu ? channel.target_setup.steps_ru : channel.target_setup.steps_en) || []).length > 0 ? (
                                <ol className="mt-1 space-y-1">
                                  {((isRu ? channel.target_setup.steps_ru : channel.target_setup.steps_en) || []).slice(0, 4).map((step, index) => (
                                    <li key={`${channel.platform}-target-setup-${index}`} className="flex gap-1.5">
                                      <span className="mt-[1px] shrink-0 font-semibold">{index + 1}.</span>
                                      <span>{step}</span>
                                    </li>
                                  ))}
                                </ol>
                              ) : null}
                              <div className="mt-1 font-medium">
                                {isRu
                                  ? String(channel.target_setup.proof_ru || '')
                                  : String(channel.target_setup.proof_en || '')}
                              </div>
                            </div>
                          ) : null}
                          {(channel.connection_checks || []).length > 0 ? (
                            <div className={channel.ready ? 'mt-2 rounded-lg border border-emerald-100 bg-white/70 px-2 py-1.5' : 'mt-2 rounded-lg border border-amber-100 bg-white/70 px-2 py-1.5'}>
                              <div className={channel.ready ? 'text-[11px] font-semibold text-emerald-950' : 'text-[11px] font-semibold text-amber-950'}>
                                {isRu ? 'Что проверить' : 'What to check'}
                              </div>
                              <div className="mt-1 space-y-1">
                                {(channel.connection_checks || []).slice(0, 4).map((check) => {
                                  const checkOk = Boolean(check.ok);
                                  const state = String(check.state || '').trim();
                                  const neutral = state === 'deferred' || state === 'manual' || state === 'recommended' || state === 'human_approval';
                                  const checkStateLabel = checkOk
                                    ? (isRu ? 'Готово' : 'Ready')
                                    : neutral
                                      ? (isRu ? 'Инфо' : 'Info')
                                      : (isRu ? 'Нужно' : 'Needed');
                                  return (
                                    <div
                                      key={`${channel.platform}-check-${String(check.key || check.label_en || check.label_ru || '')}`}
                                      className="flex gap-2 text-[11px] leading-4"
                                    >
                                      <span className={[
                                        'mt-[1px] shrink-0 rounded-full px-1.5 py-0.5 text-[10px] font-semibold',
                                        checkOk ? 'bg-emerald-50 text-emerald-700' : neutral ? 'bg-sky-50 text-sky-700' : 'bg-amber-50 text-amber-700',
                                      ].join(' ')}
                                      >
                                        {checkStateLabel}
                                      </span>
                                      <span className={checkOk ? 'text-emerald-800' : neutral ? 'text-sky-800' : 'text-amber-800'}>
                                        <span className="font-medium">
                                          {isRu ? String(check.label_ru || '') : String(check.label_en || '')}
                                        </span>
                                        {(isRu ? check.detail_ru : check.detail_en) ? ` · ${isRu ? String(check.detail_ru || '') : String(check.detail_en || '')}` : ''}
                                      </span>
                                    </div>
                                  );
                                })}
                              </div>
                            </div>
                          ) : null}
                          {socialApiPreflightByPlatform[String(channel.platform || '')] ? (
                            <div
                              className={
                                socialApiPreflightByPlatform[String(channel.platform || '')].ready
                                  ? 'mt-2 rounded-lg border border-emerald-200 bg-white px-2 py-1.5'
                                  : 'mt-2 rounded-lg border border-amber-200 bg-white px-2 py-1.5'
                              }
                            >
                              <div
                                className={
                                  socialApiPreflightByPlatform[String(channel.platform || '')].ready
                                    ? 'text-[11px] font-semibold text-emerald-950'
                                    : 'text-[11px] font-semibold text-amber-950'
                                }
                              >
                                {isRu ? 'Live API-проверка' : 'Live API preflight'}
                              </div>
                              <div
                                className={
                                  socialApiPreflightByPlatform[String(channel.platform || '')].ready
                                    ? 'mt-1 text-[11px] leading-4 text-emerald-800'
                                    : 'mt-1 text-[11px] leading-4 text-amber-800'
                                }
                              >
                                {isRu
                                  ? socialApiPreflightByPlatform[String(channel.platform || '')].message_ru
                                  : socialApiPreflightByPlatform[String(channel.platform || '')].message_en}
                              </div>
                              <div className="mt-1 space-y-1">
                                {(socialApiPreflightByPlatform[String(channel.platform || '')].connection_checks || []).slice(-2).map((check) => (
                                  <div key={`${channel.platform}-live-${String(check.key || check.label_en || check.label_ru || '')}`} className="flex gap-1.5 text-[11px] leading-4">
                                    <span className={check.ok ? 'text-emerald-700' : 'text-amber-700'}>
                                      {check.ok ? '✓' : '!'}
                                    </span>
                                    <span className={check.ok ? 'text-emerald-800' : 'text-amber-800'}>
                                      <span className="font-medium">{isRu ? String(check.label_ru || '') : String(check.label_en || '')}</span>
                                      {(isRu ? check.detail_ru : check.detail_en) ? ` · ${isRu ? String(check.detail_ru || '') : String(check.detail_en || '')}` : ''}
                                    </span>
                                  </div>
                                ))}
                              </div>
                              <div className="mt-1 text-[10px] font-medium text-slate-500">
                                {isRu ? 'Посты не отправлялись. Публикация только после подтверждения.' : 'No posts were sent. Publish only after approval.'}
                              </div>
                            </div>
                          ) : null}
                          {((isRu ? channel.setup_steps_ru : channel.setup_steps_en) || []).length > 0 ? (
                            <div className={channel.ready ? 'mt-2 rounded-lg border border-emerald-100 bg-white/70 px-2 py-1.5' : 'mt-2 rounded-lg border border-amber-100 bg-white/70 px-2 py-1.5'}>
                              <div className={channel.ready ? 'text-[11px] font-semibold text-emerald-950' : 'text-[11px] font-semibold text-amber-950'}>
                                {isRu ? 'Чеклист' : 'Checklist'}
                              </div>
                              <ul className={channel.ready ? 'mt-1 space-y-1 text-[11px] leading-4 text-emerald-800' : 'mt-1 space-y-1 text-[11px] leading-4 text-amber-800'}>
                                {((isRu ? channel.setup_steps_ru : channel.setup_steps_en) || []).slice(0, 3).map((step, index) => (
                                  <li key={`${channel.platform}-setup-${index}`} className="flex gap-1.5">
                                    <span className="mt-[1px] shrink-0 font-semibold">{index + 1}.</span>
                                    <span>{step}</span>
                                  </li>
                                ))}
                              </ul>
                            </div>
                          ) : null}
                          {!channel.ready && (channel.missing_fields || []).length > 0 ? (
                            <div className="mt-2 flex flex-wrap gap-1">
                              {(channel.missing_fields || []).slice(0, 3).map((field) => (
                                <span key={`${channel.platform}-missing-${field}`} className="rounded-full bg-white/80 px-2 py-0.5 text-[10px] font-medium text-amber-800">
                                  {field}
                                </span>
                              ))}
                            </div>
                          ) : null}
                          {!channel.ready && channel.publish_mode === 'api' ? (
                            <Button
                              type="button"
                              size="sm"
                              variant="outline"
                              className="mt-2 h-7 rounded-lg px-2 text-[11px]"
                              onClick={() => navigate(channel.settings_path || _socialSettingsPathForPlatform(String(channel.platform || '')))}
                            >
                              {isRu ? 'Открыть настройку канала' : 'Open channel setup'}
                            </Button>
                          ) : null}
                        </div>
                      ))}
                    </div>
                  </>
                ) : null}
                <div className="mt-3 flex flex-wrap gap-2">
                  {['all', 'social', 'maps'].map((filterKey) => (
                    <button
                      key={filterKey}
                      type="button"
                      onClick={() => setSelectedChannelFilter(_normalizeSocialChannelFilter(filterKey))}
                      className={[
                        'rounded-full border px-3 py-1.5 text-xs font-medium transition-colors',
                        selectedChannelFilter === filterKey
                          ? 'border-slate-900 bg-slate-900 text-white'
                          : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50',
                      ].join(' ')}
                    >
                      {_socialChannelFilterLabel(filterKey, isRu)}
                    </button>
                  ))}
                </div>
                <div
                  data-testid="social-next-plan-recommendation"
                  className="mt-3 rounded-xl border border-emerald-100 bg-emerald-50 px-3 py-3"
                >
                  <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                    <div>
                      <div className="text-sm font-semibold text-emerald-950">
                        {isRu ? 'Что менять в следующем плане' : 'What to change next'}
                      </div>
                        <div className="mt-1 text-xs leading-5 text-emerald-800">
                          {isRu
                            ? String(socialRecommendation?.recommendation?.text_ru || 'После публикаций LocalOS будет ранжировать темы по заявкам и обращениям, затем по комментариям и охвату.')
                            : String(socialRecommendation?.recommendation?.text_en || 'After publishing, LocalOS will rank topics by leads and inquiries first, then comments and reach.')}
                        </div>
                        <div
                          data-testid="social-learning-loop-status"
                          className={[
                            'mt-3 rounded-lg border px-3 py-2 text-xs leading-5',
                            socialLearningLoopStatus.tone === 'success'
                              ? 'border-emerald-200 bg-white text-emerald-900'
                              : socialLearningLoopStatus.tone === 'warning'
                                ? 'border-amber-200 bg-amber-50 text-amber-900'
                                : socialLearningLoopStatus.tone === 'caution'
                                  ? 'border-sky-200 bg-sky-50 text-sky-900'
                                  : 'border-slate-200 bg-white text-slate-700',
                          ].join(' ')}
                        >
                          <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
                            <div>
                              <div className="font-semibold">
                                {isRu ? 'Статус learning loop' : 'Learning loop status'} · {isRu ? socialLearningLoopStatus.titleRu : socialLearningLoopStatus.titleEn}
                              </div>
                              <div className="mt-1">
                                {isRu ? socialLearningLoopStatus.textRu : socialLearningLoopStatus.textEn}
                              </div>
                            </div>
                            <span className="shrink-0 rounded-full bg-white px-2 py-0.5 text-[11px] font-medium">
                              {socialPrimaryResultCount > 0
                                ? (isRu ? 'заявки главнее' : 'leads first')
                                : socialEarlySignalCount > 0
                              ? (isRu ? 'ранний сигнал' : 'early signal')
                              : Number(socialSummary?.published || 0) > 0
                                ? (isRu ? 'ждём реакции' : 'needs reactions')
                                : (isRu ? 'после publish' : 'after publish')}
                            </span>
                          </div>
                        </div>
                        {socialMetricsLearningPacket ? (
                          <div
                            data-testid="social-metrics-learning-packet"
                            data-schema="localos_social_metrics_learning_packet_v1"
                            className={[
                              'mt-3 rounded-lg border px-3 py-2 text-xs leading-5',
                              Number(socialMetricsLearningPacket.primary_result_total || 0) > 0
                                ? 'border-emerald-200 bg-white text-emerald-900'
                                : Number(socialMetricsLearningPacket.early_signal_total || 0) > 0
                                  ? 'border-sky-200 bg-sky-50 text-sky-900'
                                  : Number(socialMetricsLearningPacket.failed_posts || 0) > 0
                                    ? 'border-amber-200 bg-amber-50 text-amber-900'
                                    : 'border-slate-200 bg-white text-slate-700',
                            ].join(' ')}
                          >
                            <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                              <div>
                                <div className="font-semibold">
                                  {isRu ? 'Результат после сбора реакций' : 'Result after collecting reactions'}
                                </div>
                                <div className="mt-1">
                                  {isRu
                                    ? String(socialMetricsLearningPacket.summary_ru || '')
                                    : String(socialMetricsLearningPacket.summary_en || '')}
                                </div>
                              </div>
                              <span className="shrink-0 rounded-full bg-white px-2 py-0.5 text-[11px] font-medium">
                                {isRu
                                  ? `обновлено: ${Number(socialMetricsLearningPacket.collected_posts || 0)}`
                                  : `updated: ${Number(socialMetricsLearningPacket.collected_posts || 0)}`}
                              </span>
                            </div>
                            <div className="mt-2 grid gap-2 text-[11px] sm:grid-cols-3">
                              <div className="rounded-lg bg-white px-2.5 py-2">
                                <div className="font-semibold">
                                  {isRu ? 'Главная метрика' : 'Main metric'}
                                </div>
                                <div className="mt-1">
                                  {isRu
                                    ? String(socialMetricsLearningPacket.primary_metric_ru || 'Заявки и обращения')
                                    : String(socialMetricsLearningPacket.primary_metric_en || 'Leads and inquiries')}
                                </div>
                                <div className="mt-1 text-base font-semibold">
                                  {Number(socialMetricsLearningPacket.primary_result_total || 0)}
                                </div>
                              </div>
                              <div className="rounded-lg bg-white px-2.5 py-2">
                                <div className="font-semibold">
                                  {isRu ? 'Ранние сигналы' : 'Early signals'}
                                </div>
                                <div className="mt-1">
                                  {isRu
                                    ? `комм. ${Number(socialMetricsLearningPacket.comments || 0)}, репосты ${Number(socialMetricsLearningPacket.shares || 0)}, клики ${Number(socialMetricsLearningPacket.clicks || 0)}`
                                    : `comments ${Number(socialMetricsLearningPacket.comments || 0)}, shares ${Number(socialMetricsLearningPacket.shares || 0)}, clicks ${Number(socialMetricsLearningPacket.clicks || 0)}`}
                                </div>
                                <div className="mt-1 text-base font-semibold">
                                  {Number(socialMetricsLearningPacket.early_signal_total || 0)}
                                </div>
                              </div>
                              <div className="rounded-lg bg-white px-2.5 py-2">
                                <div className="font-semibold">
                                  {isRu ? 'Для проверки' : 'Need attention'}
                                </div>
                                <div className="mt-1">
                                  {isRu
                                    ? `ошибок: ${Number(socialMetricsLearningPacket.failed_posts || 0)}`
                                    : `failed: ${Number(socialMetricsLearningPacket.failed_posts || 0)}`}
                                </div>
                                <div className="mt-1">
                                  {isRu
                                    ? `заявки ${Number(socialMetricsLearningPacket.leads || 0)}, обращения ${Number(socialMetricsLearningPacket.inquiries || 0)}`
                                    : `leads ${Number(socialMetricsLearningPacket.leads || 0)}, inquiries ${Number(socialMetricsLearningPacket.inquiries || 0)}`}
                                </div>
                              </div>
                            </div>
                            <div className="mt-2 rounded-lg bg-white px-2.5 py-2 text-[11px] font-medium">
                              {isRu ? 'Следующий шаг: ' : 'Next step: '}
                              {isRu
                                ? String(socialMetricsLearningPacket.next_action_ru || '')
                                : String(socialMetricsLearningPacket.next_action_en || '')}
                            </div>
                          </div>
                        ) : null}
                        {socialRecommendation?.learning_readiness ? (
                          <div className={_socialLearningReadinessClassName(socialRecommendation.learning_readiness.confidence || '')}>
                            <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                              <div>
                                <div className="text-xs font-semibold">
                                  {isRu ? 'Готовность к корректировке плана' : 'Plan correction readiness'}
                                </div>
                                <div className="mt-1 text-xs leading-5">
                                  {isRu
                                    ? String(socialRecommendation.learning_readiness.summary_ru || '')
                                    : String(socialRecommendation.learning_readiness.summary_en || '')}
                                </div>
                              </div>
                              <span className="rounded-full bg-white px-2.5 py-1 text-[11px] font-medium">
                                {_socialLearningConfidenceLabel(socialRecommendation.learning_readiness.confidence || '', isRu)}
                              </span>
                            </div>
                            <div className="mt-2 grid gap-2 text-[11px] sm:grid-cols-3">
                              <div>
                                <span className="font-semibold">{isRu ? 'Опубликовано: ' : 'Published: '}</span>
                                {Number(socialRecommendation.learning_readiness.published_posts || 0)}
                              </div>
                              <div>
                                <span className="font-semibold">{isRu ? 'Заявки/обращения: ' : 'Leads/inquiries: '}</span>
                                {Number(socialRecommendation.learning_readiness.posts_with_primary_result || 0)}
                              </div>
                              <div>
                                <span className="font-semibold">{isRu ? 'Нужно закрыть: ' : 'Need action: '}</span>
                                {Number(socialRecommendation.learning_readiness.pending_manual_or_supervised_posts || 0) + Number(socialRecommendation.learning_readiness.failed_posts || 0)}
                              </div>
                            </div>
                            <div className="mt-2 rounded-lg bg-white px-2.5 py-2 text-[11px] leading-5">
                              <div className="font-semibold">
                                {isRu ? 'Факты для следующего плана' : 'Facts for the next plan'}
                              </div>
                              <div className="mt-1 grid gap-1 sm:grid-cols-3">
                                <div>
                                  {isRu
                                    ? `заявки ${Number(socialRecommendation.learning_readiness.leads || 0)}, обращения ${Number(socialRecommendation.learning_readiness.inquiries || 0)}`
                                    : `leads ${Number(socialRecommendation.learning_readiness.leads || 0)}, inquiries ${Number(socialRecommendation.learning_readiness.inquiries || 0)}`}
                                </div>
                                <div>
                                  {isRu
                                    ? `комментарии ${Number(socialRecommendation.learning_readiness.comments || 0)}, репосты ${Number(socialRecommendation.learning_readiness.shares || 0)}, клики ${Number(socialRecommendation.learning_readiness.clicks || 0)}`
                                    : `comments ${Number(socialRecommendation.learning_readiness.comments || 0)}, shares ${Number(socialRecommendation.learning_readiness.shares || 0)}, clicks ${Number(socialRecommendation.learning_readiness.clicks || 0)}`}
                                </div>
                                <div>
                                  {isRu
                                    ? `лайки ${Number(socialRecommendation.learning_readiness.likes || 0)}, охват/просмотры ${Number(socialRecommendation.learning_readiness.reach || 0)}`
                                    : `likes ${Number(socialRecommendation.learning_readiness.likes || 0)}, reach/views ${Number(socialRecommendation.learning_readiness.reach || 0)}`}
                                </div>
                              </div>
                            </div>
                            {Number(socialRecommendation.learning_readiness.checklist?.length || 0) > 0 ? (
                              <div
                                data-testid="social-learning-readiness-checklist"
                                className="mt-2 rounded-lg bg-white px-2.5 py-2 text-[11px] leading-5"
                              >
                                <div className="font-semibold">
                                  {isRu ? 'Чеклист перед корректировкой' : 'Checklist before changing the plan'}
                                </div>
                                <div className="mt-2 grid gap-2 md:grid-cols-2">
                                  {(socialRecommendation.learning_readiness.checklist || []).map((item) => {
                                    const itemStatus = String(item.status || '').trim();
                                    const tone = itemStatus === 'done'
                                      ? 'border-emerald-100 bg-emerald-50 text-emerald-900'
                                      : itemStatus === 'attention'
                                        ? 'border-amber-100 bg-amber-50 text-amber-900'
                                        : itemStatus === 'current'
                                          ? 'border-sky-100 bg-sky-50 text-sky-900'
                                          : 'border-slate-200 bg-slate-50 text-slate-700';
                                    return (
                                      <div
                                        key={String(item.key || item.label_ru || item.label_en || '')}
                                        className={`rounded-lg border px-2.5 py-2 ${tone}`}
                                      >
                                        <div className="flex items-center justify-between gap-2">
                                          <span className="font-semibold">
                                            {isRu ? String(item.label_ru || '') : String(item.label_en || '')}
                                          </span>
                                          <span className="rounded-full bg-white px-2 py-0.5 text-[10px] font-medium">
                                            {_socialLearningChecklistStatusLabel(itemStatus, isRu)}
                                          </span>
                                        </div>
                                        <div className="mt-1">
                                          {isRu ? String(item.detail_ru || '') : String(item.detail_en || '')}
                                        </div>
                                      </div>
                                    );
                                  })}
                                </div>
                              </div>
                            ) : null}
                            <div className="mt-2 text-[11px] leading-5">
                              {isRu
                                ? String(socialRecommendation.learning_readiness.next_action_ru || '')
                                : String(socialRecommendation.learning_readiness.next_action_en || '')}
                            </div>
                          </div>
                        ) : null}
                        {socialPrimaryResultCount > 0 || socialEarlySignalCount > 0 ? (
                          <div className="mt-3 rounded-lg border border-emerald-100 bg-white px-3 py-2 text-xs leading-5 text-emerald-900">
                          <div className="font-semibold text-emerald-950">
                            {socialPrimaryResultCount > 0
                              ? (isRu
                                ? `Есть заявки/обращения: ${socialPrimaryResultCount}`
                                : `Leads/inquiries recorded: ${socialPrimaryResultCount}`)
                              : (isRu
                                ? `Есть ранние сигналы: ${socialEarlySignalCount}`
                                : `Early signals recorded: ${socialEarlySignalCount}`)}
                          </div>
                          <div className="mt-1 text-emerald-800">
                            {isRu
                              ? 'Нажмите «Предложить изменения», чтобы пересчитать следующую неделю по этим фактам. LocalOS не применит изменения без подтверждения.'
                              : 'Click “Suggest changes” to recalculate next week from these facts. LocalOS will not apply changes without confirmation.'}
                          </div>
                        </div>
                      ) : null}
                      {Number(socialRecommendation?.recommendation?.signal_priority?.length || 0) > 0 ? (
                        <div className="mt-3 grid gap-2 sm:grid-cols-4">
                          {(socialRecommendation?.recommendation?.signal_priority || []).slice(0, 4).map((signal) => (
                            <div key={String(signal.key || signal.rank || '')} className="rounded-lg border border-emerald-100 bg-white px-2.5 py-2">
                              <div className="text-[11px] font-medium text-emerald-700">
                                #{Number(signal.rank || 0)} · {isRu ? String(signal.role_ru || '') : String(signal.role_en || '')}
                              </div>
                              <div className="mt-1 flex items-baseline justify-between gap-2">
                                <span className="text-xs font-semibold text-emerald-950">
                                  {isRu ? String(signal.label_ru || signal.key || '') : String(signal.label_en || signal.key || '')}
                                </span>
                                <span className="text-sm font-semibold text-emerald-900">
                                  {Number(signal.value || 0)}
                                </span>
                              </div>
                            </div>
                          ))}
                        </div>
                      ) : null}
                      {socialMetricsSourceSummary.length > 0 ? (
                        <div className="mt-3 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs leading-5 text-slate-700">
                          <div className="font-semibold text-slate-950">
                            {isRu ? 'Как считаем результат' : 'How results are counted'}
                          </div>
                          <div className="mt-1 text-slate-500">
                            {isRu
                              ? 'Заявки и обращения всегда главнее охватов. Где API-метрик нет, LocalOS честно ждёт ручную отметку результата.'
                              : 'Leads and inquiries always rank above reach. Where API metrics are unavailable, LocalOS clearly uses manual result marking.'}
                          </div>
                          <div className="mt-2 grid gap-2 md:grid-cols-2">
                            {socialMetricsSourceSummary.map((item) => (
                              <div key={item.platform} className="rounded-lg bg-slate-50 px-2.5 py-2">
                                <div className="flex items-center justify-between gap-2">
                                  <span className="font-semibold text-slate-900">{item.label}</span>
                                  <span className="shrink-0 rounded-full bg-white px-2 py-0.5 text-[11px] font-medium text-slate-600">
                                    {isRu
                                      ? `опубликовано ${item.published}/${item.posts}`
                                      : `published ${item.published}/${item.posts}`}
                                  </span>
                                </div>
                                <div className="mt-1 text-[11px] leading-4 text-slate-600">
                                  {isRu ? item.sourceRu : item.sourceEn}
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      ) : null}
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={() => { void collectSocialPostMetricsForBusiness(); }}
                        disabled={socialBusyAction === 'collect-metrics' || !Number(socialSummary?.published || 0)}
                      >
                        {socialBusyAction === 'collect-metrics'
                          ? (isRu ? 'Собираем...' : 'Collecting...')
                          : `${isRu ? 'Собрать реакции один раз' : 'Collect reactions once'} · ${Number(socialSummary?.published || 0)}`}
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={selectPublishedSocialPostsForResult}
                        disabled={!Number(socialSummary?.published || 0)}
                      >
                        {`${isRu ? 'Отметить заявки/обращения' : 'Record leads/inquiries'} · ${Number(socialSummary?.published || 0)}`}
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={() => { void recommendNextSocialPlan(); }}
                        disabled={socialBusyAction === 'recommend'}
                      >
                        {socialBusyAction === 'recommend'
                          ? (isRu ? 'Считаем...' : 'Calculating...')
                          : (isRu ? 'Предложить изменения' : 'Suggest changes')}
                      </Button>
                        <Button
                          type="button"
                          size="sm"
                          onClick={() => { void applySocialPlanRecommendation(); }}
                          disabled={
                            socialBusyAction === 'apply-recommendation'
                            || !Number(socialRecommendation?.proposed_changes?.length || 0)
                            || !socialRecommendationApproved
                            || socialRecommendation?.learning_readiness?.safe_to_apply_recommendation === false
                          }
                        >
                        {socialBusyAction === 'apply-recommendation'
                          ? (isRu ? 'Применяем...' : 'Applying...')
                          : (isRu ? 'Применить после подтверждения' : 'Apply with approval')}
                      </Button>
                    </div>
                  </div>
                  {Number(socialRecommendation?.recommendation?.winning_topics?.length || 0)
                    || Number(socialRecommendation?.recommendation?.weak_channels?.length || 0)
                    || Number(socialRecommendation?.recommendation?.no_result_topics?.length || 0)
                    || Number(socialRecommendation?.recommendation?.owner_next_steps?.length || 0)
                    || Number(socialRecommendation?.recommendation?.cta_suggestions?.length || 0)
                    || Number(socialRecommendation?.recommendation?.frequency_suggestions?.length || 0) ? (
                    <div className="mt-3 grid gap-2 lg:grid-cols-3">
                      {Number(socialRecommendation?.recommendation?.owner_next_steps?.length || 0) > 0 ? (
                        <div className="rounded-lg border border-emerald-200 bg-white px-3 py-2 lg:col-span-3">
                          <div className="text-xs font-semibold text-emerald-950">
                            {isRu ? 'Что сделать первым' : 'What to do first'}
                          </div>
                          <div className="mt-2 grid gap-2 md:grid-cols-2">
                            {(socialRecommendation?.recommendation?.owner_next_steps || []).slice(0, 4).map((step, index) => (
                              <div key={String(step.key || index)} className="flex gap-2 rounded-md bg-emerald-50 px-2.5 py-2 text-xs leading-5 text-emerald-900">
                                <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-white text-[11px] font-semibold text-emerald-800">
                                  {Number(step.priority || index + 1)}
                                </span>
                                <span>{isRu ? String(step.ru || '') : String(step.en || '')}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      ) : null}
                      {Number(socialRecommendation?.recommendation?.winning_topics?.length || 0) > 0 ? (
                        <div className="rounded-lg border border-emerald-100 bg-white px-3 py-2">
                          <div className="text-xs font-semibold text-emerald-950">
                            {isRu ? 'Что сработало' : 'What worked'}
                          </div>
                          <div className="mt-2 space-y-2">
                            {(socialRecommendation?.recommendation?.winning_topics || []).slice(0, 3).map((topic) => (
                              <div key={String(topic.item_id || topic.theme || '')} className="text-xs leading-5 text-emerald-800">
                                <span className="font-medium">{String(topic.theme || (isRu ? 'Тема плана' : 'Plan topic'))}</span>
                                <span className="block text-[11px] text-emerald-700">
                                  {_socialInsightMetricLine(topic.metrics, isRu)}
                                </span>
                              </div>
                            ))}
                          </div>
                        </div>
                      ) : null}
                      {Number(socialRecommendation?.recommendation?.weak_channels?.length || 0) > 0 ? (
                        <div className="rounded-lg border border-amber-100 bg-white px-3 py-2">
                          <div className="text-xs font-semibold text-amber-950">
                            {isRu ? 'Слабые каналы' : 'Weak channels'}
                          </div>
                          <div className="mt-2 space-y-2">
                            {(socialRecommendation?.recommendation?.weak_channels || []).slice(0, 3).map((channel) => (
                              <div key={String(channel.platform || channel.platform_label || '')} className="text-xs leading-5 text-amber-800">
                                <span className="font-medium">{String(channel.platform_label || _socialPlatformLabel(String(channel.platform || ''), isRu))}</span>
                                <span className="block">{isRu ? String(channel.reason_ru || '') : String(channel.reason_en || '')}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      ) : null}
                      {Number(socialRecommendation?.recommendation?.no_result_topics?.length || 0) > 0 ? (
                        <div className="rounded-lg border border-slate-200 bg-white px-3 py-2">
                          <div className="text-xs font-semibold text-slate-950">
                            {isRu ? 'Темы без результата' : 'No-result topics'}
                          </div>
                          <div className="mt-2 space-y-2">
                            {(socialRecommendation?.recommendation?.no_result_topics || []).slice(0, 3).map((topic) => (
                              <div key={String(topic.item_id || topic.theme || '')} className="text-xs leading-5 text-slate-700">
                                {String(topic.theme || (isRu ? 'Тема плана' : 'Plan topic'))}
                              </div>
                            ))}
                          </div>
                        </div>
                      ) : null}
                      <div className="rounded-lg border border-emerald-100 bg-white px-3 py-2 lg:col-span-3">
                        <div className="grid gap-3 md:grid-cols-2">
                          <div>
                            <div className="text-xs font-semibold text-emerald-950">
                              {isRu ? 'CTA' : 'CTA'}
                            </div>
                            <div className="mt-1 space-y-1 text-xs leading-5 text-emerald-800">
                              {(socialRecommendation?.recommendation?.cta_suggestions || []).slice(0, 2).map((suggestion, index) => (
                                <div key={`cta-${index}`}>{isRu ? String(suggestion.ru || '') : String(suggestion.en || '')}</div>
                              ))}
                            </div>
                          </div>
                          <div>
                            <div className="text-xs font-semibold text-emerald-950">
                              {isRu ? 'Частота' : 'Frequency'}
                            </div>
                            <div className="mt-1 space-y-1 text-xs leading-5 text-emerald-800">
                              {(socialRecommendation?.recommendation?.frequency_suggestions || []).slice(0, 2).map((suggestion, index) => (
                                <div key={`frequency-${index}`}>{isRu ? String(suggestion.ru || '') : String(suggestion.en || '')}</div>
                              ))}
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  ) : null}
                  {Number(socialRecommendation?.proposed_changes?.length || 0) > 0 ? (
                    <>
                      <div className="mt-3 rounded-lg border border-emerald-100 bg-white px-3 py-3">
                        <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
                          <div>
                            <div className="text-xs font-semibold text-emerald-950">
                              {isRu ? 'Предпросмотр изменений плана' : 'Plan changes preview'}
                            </div>
                            <div className="mt-1 text-xs leading-5 text-emerald-800">
                              {isRu
                                ? 'LocalOS покажет, какие будущие цели изменятся. Уже опубликованные и прошлые пункты не перезаписываются.'
                                : 'LocalOS shows which future goals will change. Published and past items are not overwritten.'}
                            </div>
                          </div>
                          <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-[11px] font-medium text-emerald-800">
                            {isRu
                              ? `изменений: ${Number(socialRecommendation?.proposed_changes?.length || 0)}`
                              : `changes: ${Number(socialRecommendation?.proposed_changes?.length || 0)}`}
                          </span>
                        </div>
                        <div className="mt-3 grid gap-2 md:grid-cols-2">
                          {(socialRecommendation?.proposed_changes || []).slice(0, 4).map((change) => (
                            <div key={String(change.item_id || change.theme || '')} className="rounded-lg border border-slate-100 bg-slate-50 px-3 py-2">
                              <div className="line-clamp-1 text-xs font-semibold text-slate-950">
                                {String(change.theme || (isRu ? 'Тема плана' : 'Plan topic'))}
                              </div>
                              <div className="mt-2 grid gap-2 text-[11px] leading-4 text-slate-700">
                                <div>
                                  <span className="font-semibold text-slate-500">{isRu ? 'Сейчас: ' : 'Now: '}</span>
                                  {String(change.current_goal || (isRu ? 'цель не задана' : 'no goal set'))}
                                </div>
                                <div>
                                  <span className="font-semibold text-emerald-700">{isRu ? 'Станет: ' : 'Will become: '}</span>
                                  {String(change.proposed_goal || '')}
                                </div>
                              </div>
                              <div className="mt-2 text-xs leading-5 text-emerald-800">
                                {isRu ? String(change.reason_ru || '') : String(change.reason_en || '')}
                              </div>
                              <div className="mt-1 text-[11px] text-slate-500">
                                {isRu
                                  ? `сигналы: заявки ${Number(change.metrics?.leads || 0)}, обращения ${Number(change.metrics?.inquiries || 0)}, комментарии ${Number(change.metrics?.comments || 0)}, охват ${Number(change.metrics?.reach || 0)}`
                                  : `signals: leads ${Number(change.metrics?.leads || 0)}, inquiries ${Number(change.metrics?.inquiries || 0)}, comments ${Number(change.metrics?.comments || 0)}, reach ${Number(change.metrics?.reach || 0)}`}
                              </div>
                              {change.channel_breakdown?.summary_ru || change.channel_breakdown?.summary_en ? (
                                <div className="mt-2 rounded-md border border-emerald-100 bg-white px-2 py-1.5 text-[11px] leading-5 text-emerald-900">
                                  <div className="font-semibold text-emerald-950">
                                    {isRu ? 'По каналам' : 'By channel'}
                                  </div>
                                  <div>
                                    {isRu
                                      ? String(change.channel_breakdown?.summary_ru || '')
                                      : String(change.channel_breakdown?.summary_en || '')}
                                  </div>
                                  {Number(change.channel_breakdown?.best_channels?.length || 0) > 0 ? (
                                    <div className="mt-1 text-emerald-800">
                                      {(change.channel_breakdown?.best_channels || []).slice(0, 2).map((channel) => (
                                        <div key={`best:${String(change.item_id || '')}:${String(channel.platform || channel.platform_label || '')}`}>
                                          + {String(channel.platform_label || _socialPlatformLabel(String(channel.platform || ''), isRu))}: {_socialInsightMetricLine(channel.metrics, isRu)}
                                        </div>
                                      ))}
                                    </div>
                                  ) : null}
                                  {Number(change.channel_breakdown?.weak_channels?.length || 0) > 0 ? (
                                    <div className="mt-1 text-amber-800">
                                      {(change.channel_breakdown?.weak_channels || []).slice(0, 2).map((channel) => (
                                        <div key={`weak:${String(change.item_id || '')}:${String(channel.platform || channel.platform_label || '')}`}>
                                          - {String(channel.platform_label || _socialPlatformLabel(String(channel.platform || ''), isRu))}: {isRu ? String(channel.reason_ru || '') : String(channel.reason_en || '')}
                                        </div>
                                      ))}
                                    </div>
                                  ) : null}
                                </div>
                              ) : null}
                            </div>
                          ))}
                        </div>
                        {socialRecommendation?.application_preview ? (
                          <div
                            data-testid="social-recommendation-application-preview"
                            className="mt-3 rounded-lg border border-sky-100 bg-sky-50 px-3 py-2 text-xs leading-5 text-sky-900"
                          >
                            <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                              <div>
                                <div className="font-semibold text-sky-950">
                                  {isRu ? 'Что реально изменится' : 'What will actually change'}
                                </div>
                                <div className="mt-1">
                                  {isRu
                                    ? String(socialRecommendation.application_preview.summary_ru || '')
                                    : String(socialRecommendation.application_preview.summary_en || '')}
                                </div>
                              </div>
                              <div className="flex flex-wrap gap-1.5">
                                <span className="rounded-full bg-white px-2 py-0.5 font-medium text-sky-800">
                                  {isRu
                                    ? `изменится: ${Number(socialRecommendation.application_preview.applicable_count || 0)}`
                                    : `changes: ${Number(socialRecommendation.application_preview.applicable_count || 0)}`}
                                </span>
                                <span className="rounded-full bg-white px-2 py-0.5 font-medium text-sky-800">
                                  {isRu
                                    ? `пропустится: ${Number(socialRecommendation.application_preview.skipped_count || 0)}`
                                    : `skipped: ${Number(socialRecommendation.application_preview.skipped_count || 0)}`}
                                </span>
                              </div>
                            </div>
                            {Number(socialRecommendation.application_preview.items?.length || 0) > 0 ? (
                              <div className="mt-2 grid gap-1.5 md:grid-cols-2">
                                {(socialRecommendation.application_preview.items || []).slice(0, 4).map((item) => (
                                  <div
                                    key={`application-preview:${String(item.item_id || item.theme || '')}`}
                                    className={[
                                      'rounded-md border px-2 py-1.5',
                                      item.applicable
                                        ? 'border-emerald-100 bg-white text-emerald-900'
                                        : 'border-amber-100 bg-white text-amber-900',
                                    ].join(' ')}
                                  >
                                    <div className="flex items-start justify-between gap-2">
                                      <span className="line-clamp-1 font-semibold">
                                        {String(item.theme || item.item_id || (isRu ? 'Пункт плана' : 'Plan item'))}
                                      </span>
                                      <span className="shrink-0 rounded-full bg-slate-50 px-2 py-0.5 text-[10px] font-medium">
                                        {isRu ? String(item.label_ru || '') : String(item.label_en || '')}
                                      </span>
                                    </div>
                                    <div className="mt-1 text-[11px]">
                                      {isRu
                                        ? `дата: ${String(item.scheduled_for || 'не задана')}${item.status ? ` · статус: ${String(item.status)}` : ''}`
                                        : `date: ${String(item.scheduled_for || 'not set')}${item.status ? ` · status: ${String(item.status)}` : ''}`}
                                    </div>
                                  </div>
                                ))}
                              </div>
                            ) : null}
                          </div>
                        ) : null}
                        {Number(socialRecommendation?.proposed_changes?.length || 0) > 4 ? (
                          <div className="mt-2 text-[11px] text-emerald-700">
                            {isRu
                              ? `Ещё ${Number(socialRecommendation?.proposed_changes?.length || 0) - 4} изменений будут применены по тому же правилу.`
                              : `${Number(socialRecommendation?.proposed_changes?.length || 0) - 4} more changes will be applied by the same rule.`}
                          </div>
                        ) : null}
                      </div>
                      <label className="mt-3 flex items-start gap-2 rounded-lg border border-emerald-100 bg-white px-3 py-2 text-xs leading-5 text-emerald-900">
                        <input
                            type="checkbox"
                            className="mt-1 h-4 w-4 rounded border-emerald-300 text-emerald-700 focus:ring-emerald-500"
                            checked={socialRecommendationApproved}
                            disabled={socialRecommendation?.learning_readiness?.safe_to_apply_recommendation === false}
                            onChange={(event) => setSocialRecommendationApproved(event.target.checked)}
                          />
                        <span>
                          {isRu
                            ? 'Я проверил предпросмотр выше и подтверждаю применение только к будущим пунктам плана.'
                            : 'I reviewed the preview above and approve applying it only to future plan items.'}
                        </span>
                      </label>
                      {socialRecommendation?.learning_readiness?.safe_to_apply_recommendation === false ? (
                        <div className="mt-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-900">
                          <div className="font-semibold text-amber-950">
                            {isRu ? 'Почему нельзя применить сейчас' : 'Why apply is blocked'}
                          </div>
                          <div className="mt-1">
                            {isRu
                              ? String(socialRecommendation.learning_readiness.apply_blocked_reason_ru || socialRecommendation.learning_readiness.next_action_ru || '')
                              : String(socialRecommendation.learning_readiness.apply_blocked_reason_en || socialRecommendation.learning_readiness.next_action_en || '')}
                          </div>
                        </div>
                      ) : null}
                    </>
                  ) : null}
                </div>
              </div>
              {selectedItems.length > 0 ? (
                <div className="flex w-full flex-wrap items-center gap-2 rounded-2xl border border-slate-200 bg-white px-3 py-3">
                  <div className="mr-auto flex items-center gap-2 text-sm font-medium text-slate-900">
                    <CheckSquare className="h-4 w-4" />
                    {isRu ? `Выбрано: ${selectedItems.length}` : `Selected: ${selectedItems.length}`}
                  </div>
                  <div className="w-full rounded-xl border border-blue-100 bg-blue-50 px-3 py-2 text-xs leading-5 text-blue-900">
                    <div className="font-semibold text-blue-950">
                      {isRu ? 'Маршрут выбранных постов' : 'Selected post path'}
                    </div>
                    <div className="mt-1">
                      {isRu
                        ? `Проверить предпросмотр: ${selectedSocialNeedsReview.length} · поставить в расписание: ${selectedSocialCanQueue.length} · ручное/контролируемое размещение: ${selectedSocialCanMarkPublished.length} · отметить результат: ${selectedSocialCanRecordResults.length}.`
                        : `Review preview: ${selectedSocialNeedsReview.length} · queue on schedule: ${selectedSocialCanQueue.length} · manual/supervised placement: ${selectedSocialCanMarkPublished.length} · record result: ${selectedSocialCanRecordResults.length}.`}
                    </div>
                    <div className="mt-1 text-blue-800">
                      {selectedSocialNeedsReview.length > 0
                        ? (isRu
                          ? 'Сначала откройте карточку темы ниже, проверьте “Предпросмотр перед подтверждением”, затем нажмите “Подтвердить посты”.'
                          : 'First open a topic card below, review “Preview before approval”, then click “Approve posts”.')
                        : selectedSocialCanQueue.length > 0
                          ? (isRu
                            ? 'Посты подтверждены: следующий безопасный шаг - “Поставить в расписание”.'
                            : 'Posts are approved: the next safe step is “Queue on schedule”.')
                          : selectedSocialCanMarkPublished.length > 0
                            ? (isRu
                              ? 'Для этих каналов нужен ручной или контролируемый финал: проверьте задачу и отметьте размещение.'
                              : 'These channels need a manual or supervised finish: review the task and mark placement.')
                            : selectedSocialCanRecordResults.length > 0
                              ? (isRu
                                ? 'Посты опубликованы: отметьте заявки, обращения и ранние реакции, чтобы LocalOS корректировал следующий план по реальному результату.'
                                : 'Posts are published: record leads, inquiries, and early reactions so LocalOS can adjust the next plan by real outcomes.')
                              : (isRu
                                ? 'Если кнопки ниже показывают 0, сначала подготовьте каналы для выбранных тем.'
                                : 'If the buttons below show 0, prepare channels for the selected topics first.')}
                    </div>
                  </div>
                  {selectedSocialQueueApiWarnings.length > 0 ? (
                    <div className="w-full rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-900">
                      <div className="font-semibold text-amber-950">
                        {isRu ? 'Перед расписанием эти API-каналы не готовы' : 'These API channels are not ready before queueing'}
                      </div>
                      <div className="mt-1">
                        {isRu
                          ? 'Расписание можно сохранить, но исполнитель не будет публиковать эти каналы, пока не появятся ключи, права, локация или адаптер.'
                          : 'Queue can still be saved, but the worker will not publish these channels until keys, permissions, location, or adapter are ready.'}
                      </div>
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {selectedSocialQueueApiWarnings.slice(0, 6).map((warning) => (
                          <span
                            key={`selected-api-warning:${warning.postId}:${warning.platform}`}
                            className="rounded-full bg-white px-2.5 py-1 font-medium text-amber-800"
                          >
                            {warning.label} · {warning.status}
                          </span>
                        ))}
                      </div>
                    </div>
                  ) : null}
                  {socialBulkPublishRehearsal ? (
                    <div
                      data-testid="social-bulk-publish-rehearsal"
                      className={[
                        'w-full rounded-xl border px-3 py-3 text-xs leading-5',
                        Number(socialBulkPublishRehearsal.summary?.manual_or_blocked || 0) > 0
                          ? 'border-amber-200 bg-amber-50 text-amber-900'
                          : 'border-emerald-200 bg-emerald-50 text-emerald-900',
                      ].join(' ')}
                    >
                      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                        <div>
                          <div className={Number(socialBulkPublishRehearsal.summary?.manual_or_blocked || 0) > 0 ? 'font-semibold text-amber-950' : 'font-semibold text-emerald-950'}>
                            {isRu ? 'Проверка запуска выбранных' : 'Selected launch check'}
                          </div>
                          <div className="mt-1">
                            {isRu
                              ? String(socialBulkPublishRehearsal.summary?.message_ru || '')
                              : String(socialBulkPublishRehearsal.summary?.message_en || '')}
                          </div>
                          <div className="mt-1 font-medium">
                            {isRu
                              ? String(socialBulkPublishRehearsal.summary?.next_action_ru || '')
                              : String(socialBulkPublishRehearsal.summary?.next_action_en || '')}
                          </div>
                        </div>
                        <span className="rounded-full bg-white px-2.5 py-1 text-[11px] font-semibold">
                          {isRu ? 'наружу ничего не отправлено' : 'nothing sent externally'}
                        </span>
                      </div>
                      <div className="mt-2 grid gap-2 sm:grid-cols-4">
                        <div className="rounded-lg bg-white/70 px-2.5 py-2">
                          <div className="font-semibold">{Number(socialBulkPublishRehearsal.summary?.ready || 0)}</div>
                          <div>{isRu ? 'готово' : 'ready'}</div>
                        </div>
                        <div className="rounded-lg bg-white/70 px-2.5 py-2">
                          <div className="font-semibold">{Number(socialBulkPublishRehearsal.summary?.api_ready || 0)}</div>
                          <div>{isRu ? 'API' : 'API'}</div>
                        </div>
                        <div className="rounded-lg bg-white/70 px-2.5 py-2">
                          <div className="font-semibold">{Number(socialBulkPublishRehearsal.summary?.supervised_ready || 0)}</div>
                          <div>{isRu ? 'контроль' : 'supervised'}</div>
                        </div>
                        <div className="rounded-lg bg-white/70 px-2.5 py-2">
                          <div className="font-semibold">{Number(socialBulkPublishRehearsal.summary?.manual_or_blocked || 0)}</div>
                          <div>{isRu ? 'внимание' : 'attention'}</div>
                        </div>
                      </div>
                      {Number(socialBulkPublishRehearsal.failed?.length || 0) > 0 ? (
                        <div className="mt-2 rounded-lg bg-white/70 px-2.5 py-2 text-[11px]">
                          {isRu
                            ? `Не удалось проверить: ${Number(socialBulkPublishRehearsal.failed?.length || 0)}.`
                            : `Could not check: ${Number(socialBulkPublishRehearsal.failed?.length || 0)}.`}
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                  <Button
                    variant="outline"
                    onClick={() => { void runSelectedGenerateDrafts(); }}
                    disabled={Boolean(bulkBusyAction) || selectedDraftCandidates.length === 0}
                  >
                    <Sparkles className="mr-2 h-4 w-4" />
                    {bulkBusyAction === 'selected-drafts'
                      ? (isRu ? 'Генерируем тексты...' : 'Generating texts...')
                      : `${isRu ? 'Сгенерировать тексты' : 'Generate texts'} · ${selectedDraftCandidates.length}`}
                  </Button>
                  <Button
                    onClick={runSelectedCreateNews}
                    disabled={Boolean(bulkBusyAction) || selectedNewsCandidates.length === 0}
                  >
                    {bulkBusyAction === 'selected-news'
                      ? (isRu ? 'Создаём публикации...' : 'Creating publications...')
                      : `${isRu ? 'Создать выбранные публикации' : 'Create selected publications'} · ${selectedNewsCandidates.length}`}
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => { void prepareSelectedSocialPosts(); }}
                    disabled={Boolean(bulkBusyAction) || selectedItems.length === 0}
                  >
                    <Globe className="mr-2 h-4 w-4" />
                    {bulkBusyAction === 'selected-social-prepare'
                      ? (isRu ? 'Готовим каналы...' : 'Preparing channels...')
                      : `${isRu ? 'Подготовить каналы' : 'Prepare channels'} · ${selectedItems.length}`}
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => { void rehearseSelectedSocialPosts(); }}
                    disabled={Boolean(bulkBusyAction) || selectedSocialPosts.length === 0}
                  >
                    {bulkBusyAction === 'selected-social-rehearsal'
                      ? (isRu ? 'Проверяем запуск...' : 'Checking launch...')
                      : `${isRu ? 'Проверить запуск выбранных' : 'Check selected launch'} · ${selectedSocialPosts.length}`}
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => { void approveSelectedSocialPosts(); }}
                    disabled={Boolean(bulkBusyAction) || selectedSocialNeedsReview.length === 0 || selectedSocialDirtyReviewPosts.length > 0}
                  >
                    {bulkBusyAction === 'selected-social-approve'
                      ? (isRu ? 'Подтверждаем...' : 'Approving...')
                      : `${isRu ? 'Подтвердить посты' : 'Approve posts'} · ${selectedSocialNeedsReview.length}`}
                  </Button>
                  {selectedSocialDirtyReviewPosts.length > 0 ? (
                    <div className="w-full rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-800">
                      {isRu
                        ? `Сначала сохраните правки текста: ${selectedSocialDirtyReviewPosts.length}. После этого можно подтверждать выбранные посты.`
                        : `Save copy edits first: ${selectedSocialDirtyReviewPosts.length}. Then selected posts can be approved.`}
                    </div>
                  ) : null}
                  <Button
                    variant="outline"
                    onClick={() => { void queueSelectedSocialPosts(); }}
                    disabled={Boolean(bulkBusyAction) || selectedSocialCanQueue.length === 0}
                  >
                    {bulkBusyAction === 'selected-social-queue'
                      ? (isRu ? 'Ставим в расписание...' : 'Queueing...')
                      : `${isRu ? 'Поставить в расписание' : 'Queue on schedule'} · ${selectedSocialCanQueue.length}`}
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => { void markSelectedSocialPostsPublished(); }}
                    disabled={Boolean(bulkBusyAction) || selectedSocialCanMarkPublished.length === 0}
                  >
                    {bulkBusyAction === 'selected-social-manual'
                      ? (isRu ? 'Отмечаем...' : 'Marking...')
                      : `${isRu ? 'Отметить размещёнными' : 'Mark published'} · ${selectedSocialCanMarkPublished.length}`}
                  </Button>
                  {selectedSocialCanRecordResults.length > 0 ? (
                    <div
                      data-testid="social-bulk-attribution-actions"
                      className="w-full rounded-xl border border-emerald-100 bg-emerald-50 px-3 py-2 text-xs leading-5 text-emerald-900"
                    >
                      <div className="font-semibold text-emerald-950">
                        {isRu ? 'Отметить результат по выбранным публикациям' : 'Record result for selected posts'}
                      </div>
                      <div className="mt-1">
                        {isRu
                          ? 'Сначала отмечайте заявки и обращения. Комментарии, репосты, клики, лайки и просмотры помогают понять формат, но стоят ниже бизнес-результата.'
                          : 'Record leads and inquiries first. Comments, shares, clicks, likes, and views help evaluate the format, but rank below business outcomes.'}
                      </div>
                    </div>
                  ) : null}
                  <span className="w-full text-xs font-semibold uppercase tracking-wide text-emerald-700">
                    {isRu ? 'Главный результат' : 'Primary result'}
                  </span>
                  <Button
                    variant="outline"
                    onClick={() => { void recordSelectedSocialPostAttribution('lead'); }}
                    disabled={Boolean(bulkBusyAction) || selectedSocialCanRecordResults.length === 0}
                  >
                    {bulkBusyAction === 'selected-social-attribute-lead'
                      ? (isRu ? 'Отмечаем заявки...' : 'Recording leads...')
                      : `${isRu ? 'Была заявка' : 'Record lead'} · ${selectedSocialCanRecordResults.length}`}
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => { void recordSelectedSocialPostAttribution('inquiry'); }}
                    disabled={Boolean(bulkBusyAction) || selectedSocialCanRecordResults.length === 0}
                  >
                    {bulkBusyAction === 'selected-social-attribute-inquiry'
                      ? (isRu ? 'Отмечаем обращения...' : 'Recording inquiries...')
                      : `${isRu ? 'Было обращение' : 'Record inquiry'} · ${selectedSocialCanRecordResults.length}`}
                  </Button>
                  <span className="w-full text-xs font-semibold uppercase tracking-wide text-slate-500">
                    {isRu ? 'Ранние сигналы' : 'Early signals'}
                  </span>
                  <Button
                    variant="outline"
                    onClick={() => { void recordSelectedSocialPostAttribution('comment'); }}
                    disabled={Boolean(bulkBusyAction) || selectedSocialCanRecordResults.length === 0}
                  >
                    {bulkBusyAction === 'selected-social-attribute-comment'
                      ? (isRu ? 'Отмечаем комментарии...' : 'Recording comments...')
                      : `${isRu ? 'Был комментарий' : 'Record comment'} · ${selectedSocialCanRecordResults.length}`}
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => { void recordSelectedSocialPostAttribution('share'); }}
                    disabled={Boolean(bulkBusyAction) || selectedSocialCanRecordResults.length === 0}
                  >
                    {bulkBusyAction === 'selected-social-attribute-share'
                      ? (isRu ? 'Отмечаем репосты...' : 'Recording shares...')
                      : `${isRu ? 'Был репост' : 'Record share'} · ${selectedSocialCanRecordResults.length}`}
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => { void recordSelectedSocialPostAttribution('click'); }}
                    disabled={Boolean(bulkBusyAction) || selectedSocialCanRecordResults.length === 0}
                  >
                    {bulkBusyAction === 'selected-social-attribute-click'
                      ? (isRu ? 'Отмечаем клики...' : 'Recording clicks...')
                      : `${isRu ? 'Был клик' : 'Record click'} · ${selectedSocialCanRecordResults.length}`}
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => { void recordSelectedSocialPostAttribution('like'); }}
                    disabled={Boolean(bulkBusyAction) || selectedSocialCanRecordResults.length === 0}
                  >
                    {bulkBusyAction === 'selected-social-attribute-like'
                      ? (isRu ? 'Отмечаем лайки...' : 'Recording likes...')
                      : `${isRu ? 'Был лайк' : 'Record like'} · ${selectedSocialCanRecordResults.length}`}
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => { void recordSelectedSocialPostAttribution('view'); }}
                    disabled={Boolean(bulkBusyAction) || selectedSocialCanRecordResults.length === 0}
                  >
                    {bulkBusyAction === 'selected-social-attribute-view'
                      ? (isRu ? 'Отмечаем просмотры...' : 'Recording views...')
                      : `${isRu ? 'Был просмотр' : 'Record view'} · ${selectedSocialCanRecordResults.length}`}
                  </Button>
                  <Button type="button" variant="ghost" onClick={clearSelectedItems}>
                    {isRu ? 'Снять выбор' : 'Clear'}
                  </Button>
                </div>
              ) : null}
            </div>
            {visibleItems.length > 0 ? (
              <div className="grid gap-4">
                <div id="content-plan-topic-queue" className="scroll-mt-6 rounded-[28px] border border-slate-200 bg-slate-50 p-3">
                  <div className="px-2 pb-3">
                    <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                      {isRu ? 'Очередь тем' : 'Topic queue'}
                    </div>
                    <div className="mt-1 text-sm text-slate-600">
                      {isRu ? 'Выберите тему, чтобы открыть редактор в окне.' : 'Select one item to open the editor in a modal.'}
                    </div>
                  </div>
                  <div className="max-h-[680px] space-y-2 overflow-y-auto pr-1">
                    {visibleItems.map((item) => {
                      const status = _planItemStatus(item, isRu);
                      const isSelected = selectedQueueItem?.id === item.id;
                      const itemSocialPosts = socialPostsByItem[item.id] || [];
                      const itemSocialSummary = _socialItemQueueSummary(itemSocialPosts, isRu);
                      return (
                        <button
                          key={item.id}
                          type="button"
                          onClick={() => {
                            setSelectedQueueItemId(item.id);
                            setEditorItemId(item.id);
                            setShowSelectedItemDetails(false);
                          }}
                          className={[
                            'w-full rounded-2xl border px-4 py-3 text-left transition-colors',
                            isSelected
                              ? 'border-slate-950 bg-white shadow-sm'
                              : 'border-transparent bg-white/70 hover:border-slate-200 hover:bg-white',
                          ].join(' ')}
                        >
                          <div className="flex items-start justify-between gap-3">
                            <span className="flex items-center gap-2">
                              <span
                                role="checkbox"
                                aria-checked={Boolean(selectedItemIds[item.id])}
                                onClick={(event) => {
                                  event.stopPropagation();
                                  toggleSelectedItem(item.id);
                                }}
                                className={[
                                  'flex h-5 w-5 items-center justify-center rounded-md border transition-colors',
                                  selectedItemIds[item.id]
                                    ? 'border-slate-900 bg-slate-900 text-white'
                                    : 'border-slate-300 bg-white text-transparent',
                                ].join(' ')}
                              >
                                <CheckSquare className="h-3.5 w-3.5" />
                              </span>
                              <span className={status.className}>{status.label}</span>
                            </span>
                            <span className="shrink-0 text-xs font-medium text-slate-400">
                              {_formatPlanItemDate(item.scheduled_for, isRu)}
                            </span>
                          </div>
                          <div className="mt-2 line-clamp-2 text-sm font-semibold leading-5 text-slate-950">
                            {_humanizePlanTitle(item, isRu)}
                          </div>
                          <div className="mt-2 flex flex-wrap gap-1.5 text-xs text-slate-500">
                            <span>{_contentTypeLabel(item.content_type, isRu)}</span>
                            <span>·</span>
                            <span>{_sourceKindLabel(item.source_kind, isRu)}</span>
                            {_seoViewsLabel(item, isRu) ? (
                              <>
                                <span>·</span>
                                <span>{_seoViewsLabel(item, isRu)}</span>
                              </>
                            ) : null}
                            {isNetworkMode && item.location_label ? (
                              <>
                                <span>·</span>
                                <span className="line-clamp-1">{_itemLocationLabel(item, isRu)}</span>
                              </>
                            ) : null}
                          </div>
                          {itemSocialPosts.length > 0 ? (
                            <div className="mt-3 rounded-xl border border-slate-100 bg-slate-50 px-3 py-2">
                              <div className="flex flex-wrap items-center justify-between gap-2">
                                <span className={itemSocialSummary.className}>
                                  {itemSocialSummary.label}
                                </span>
                                <span className="text-[11px] font-medium text-slate-500">
                                  {itemSocialSummary.totalLabel}
                                </span>
                              </div>
                              <div className="mt-1 text-xs leading-5 text-slate-600">
                                {itemSocialSummary.detail}
                              </div>
                            </div>
                          ) : (
                            <div className="mt-3 rounded-xl border border-dashed border-slate-200 bg-slate-50 px-3 py-2 text-xs leading-5 text-slate-500">
                              {isRu
                                ? 'Каналы ещё не подготовлены: откройте тему и нажмите “Подготовить каналы”.'
                                : 'Channels are not prepared yet: open the topic and click “Prepare channels”.'}
                            </div>
                          )}
                        </button>
                      );
                    })}
                  </div>
                </div>

                {editorItem ? (() => {
                  const item = editorItem;
                  const currentDraft = draftEdits[item.id] !== undefined ? draftEdits[item.id] : item.draft_text;
                  const currentTheme = themeEdits[item.id] !== undefined ? themeEdits[item.id] : item.theme;
                  const currentDate = dateEdits[item.id] !== undefined ? dateEdits[item.id] : item.scheduled_for;
                  const currentInputDate = _inputDateValue(currentDate);
                  const duplicateTargetOptions = getDuplicateTargetLocationOptions(item);
                  const selectedDuplicateTargets = duplicateTargetSelections[item.id] || [];
                  const duplicateTargetDate = duplicateDateOverrides[item.id] || currentInputDate;
                  const status = _planItemStatus(item, isRu);
                  const itemSocialPosts = socialPostsByItem[item.id] || [];
                  const hasDraft = Boolean(String(currentDraft || '').trim());
                  const hasNews = Boolean(String(item.usernews_id || '').trim());
                  return (
                    <div
                      className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4 backdrop-blur-sm"
                      onClick={() => setEditorItemId('')}
                    >
                      <div
                        className="max-h-[92vh] w-full max-w-5xl overflow-y-auto rounded-[28px] border border-slate-200 bg-white p-5 shadow-2xl"
                        onClick={(event) => event.stopPropagation()}
                      >
                      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                        <div>
                          <div className="flex flex-wrap items-center gap-2">
                            <span className={status.className}>{status.label}</span>
                            <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
                              {_contentTypeLabel(item.content_type, isRu)}
                            </span>
                            {isNetworkMode && item.location_label ? (
                              <span className="rounded-full bg-sky-50 px-3 py-1 text-xs font-medium text-sky-800">
                                {_itemLocationLabel(item, isRu)}
                              </span>
                            ) : null}
                          </div>
                          <h5 className="mt-3 text-2xl font-semibold tracking-tight text-slate-950">
                            {_humanizePlanTitle(item, isRu)}
                          </h5>
                          {recentGeneratedItemId === item.id ? (
                            <div className="mt-3 rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-medium text-emerald-800">
                              {isRu
                                ? 'Черновик сгенерирован именно для этой темы.'
                                : 'The draft was generated for this selected item.'}
                            </div>
                          ) : null}
                        </div>
                        <div className="grid min-w-[180px] grid-cols-2 gap-2 text-center text-xs text-slate-500">
                          <button
                            type="button"
                            onClick={() => setEditorItemId('')}
                            className="col-span-2 rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50"
                          >
                            {isRu ? 'Закрыть редактор' : 'Close editor'}
                          </button>
                          <div className="rounded-2xl bg-slate-50 px-3 py-3">
                            <div className="text-sm font-semibold text-slate-950">{_formatPlanItemDate(currentDate, isRu)}</div>
                            <div>{isRu ? 'дата' : 'date'}</div>
                          </div>
                          <div className="rounded-2xl bg-slate-50 px-3 py-3">
                            <div className="text-sm font-semibold text-slate-950">{_sourceKindLabel(item.source_kind, isRu)}</div>
                            <div>{isRu ? 'сигнал' : 'signal'}</div>
                          </div>
                          {_seoViewsLabel(item, isRu) ? (
                            <div className="col-span-2 rounded-2xl bg-blue-50 px-3 py-3">
                              <div className="text-sm font-semibold text-blue-950">{_seoViewsLabel(item, isRu)}</div>
                              <div>{isRu ? 'частотность запроса' : 'query demand'}</div>
                            </div>
                          ) : null}
                        </div>
                      </div>

                      <div className="mt-6 grid gap-4 lg:grid-cols-[180px_1fr]">
                        <div className="space-y-2">
                          <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                            {isRu ? 'Дата' : 'Date'}
                          </div>
                          <Input
                            type="date"
                            value={currentInputDate}
                            onChange={(event) => setDateEdits((prev) => ({ ...prev, [item.id]: event.target.value }))}
                          />
                          {!currentInputDate ? (
                            <div className="text-xs leading-5 text-amber-700">
                              {isRu ? 'Назначьте дату публикации' : 'Set a publication date'}
                            </div>
                          ) : null}
                        </div>
                        <div className="space-y-2">
                          <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                            {isRu ? 'Тема' : 'Theme'}
                          </div>
                          <Input
                            value={currentTheme}
                            onChange={(event) => setThemeEdits((prev) => ({ ...prev, [item.id]: event.target.value }))}
                          />
                        </div>
                      </div>

                      <div className="mt-5 space-y-2">
                        <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                          {isRu ? 'Черновик' : 'Draft'}
                        </div>
                        <Textarea
                          rows={8}
                          value={currentDraft}
                          onChange={(event) => setDraftEdits((prev) => ({ ...prev, [item.id]: event.target.value }))}
                          placeholder={isRu ? 'Здесь появится текст публикации' : 'Draft text will appear here'}
                        />
                      </div>

                      <div className="mt-5 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
                        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                          <div>
                            <div className="text-sm font-semibold text-slate-950">
                              {isRu ? 'Каналы публикации' : 'Publishing channels'}
                            </div>
                            <div className="mt-1 text-sm leading-6 text-slate-600">
                              {isRu
                                ? 'Один пункт плана раскладывается на карты и соцсети. Внешняя публикация идёт только после проверки.'
                                : 'One plan item becomes map and social posts. External publishing starts only after review.'}
                            </div>
                          </div>
                          <Button
                            type="button"
                            size="sm"
                            variant={itemSocialPosts.length ? 'outline' : 'default'}
                            onClick={() => { void prepareSocialPosts(item.id); }}
                            disabled={socialBusyAction === `prepare:${item.id}` || !String(currentDraft || currentTheme || '').trim()}
                          >
                            <Globe className="mr-2 h-4 w-4" />
                            {itemSocialPosts.length
                              ? (isRu ? 'Обновить каналы' : 'Refresh channels')
                              : (isRu ? 'Подготовить каналы' : 'Prepare channels')}
                          </Button>
                        </div>

                        {itemSocialPosts.length > 0 ? (
                          <div className="mt-4 grid gap-3 xl:grid-cols-2">
                            {itemSocialPosts.map((post) => {
                              const postBusy = socialBusyAction.endsWith(`:${post.id}`);
                              const needsReview = post.status === 'draft' || post.status === 'needs_review';
                              const canQueue = post.status === 'approved';
                              const canMarkPublished = post.status === 'needs_supervised_publish' || post.status === 'needs_manual_publish';
                              const canRecordResult = post.status === 'published';
                              const isSupervisedPost = _isSupervisedPlatform(post.platform);
                              const canCreateSupervisedTask = isSupervisedPost
                                && (post.status === 'approved' || post.status === 'queued' || post.status === 'needs_manual_publish');
                              const publishEvidence = post.publish_evidence || null;
                              const resultPacket = publishEvidence?.result_packet || null;
                              const publishRehearsal = socialPublishRehearsals[post.id] || null;
                              const supervisedPayload = _socialSupervisedPayload(post);
                              const placementPacket = publishEvidence?.placement_packet || null;
                              const supervisedHandoffState = supervisedPayload?.handoff_state || null;
                              const manualRefs = manualPublishRefs[post.id] || {
                                url: String(post.provider_post_url || ''),
                                id: String(post.provider_post_id || ''),
                              };
                              const postTextFallback = String(currentDraft || '').trim();
                              const postTextValue = String(socialTextEdits[post.id] ?? post.platform_text ?? postTextFallback);
                              const postTextLocked = _isSocialPostTextLocked(post.status);
                              const postTextDirty = postTextValue.trim() !== String(post.platform_text || '').trim();
                              const supervisedLedgerId = String(post.metadata_json?.agent_action_ledger_id || '').trim();
                              const supervisedCapabilityLine = _socialOpenClawCapabilityLine(supervisedPayload?.openclaw_capability_status, isRu);
                              const supervisedTaskStatus = String(supervisedPayload?.task_status || '').trim();
                              const supervisedActionRef = String(supervisedPayload?.openclaw_action_ref || '').trim();
                              const supervisedManualHandoff = supervisedPayload?.manual_handoff || null;
                              const supervisedManualInstruction = String(
                                isRu
                                  ? supervisedPayload?.manual_instruction_ru || supervisedManualHandoff?.instruction_ru || ''
                                  : supervisedPayload?.manual_instruction_en || supervisedManualHandoff?.instruction_en || ''
                              ).trim();
                              const supervisedManualChecklistSource = isRu
                                ? supervisedPayload?.manual_checklist_ru || supervisedManualHandoff?.checklist_ru || publishEvidence?.manual_checklist_ru || []
                                : supervisedPayload?.manual_checklist_en || supervisedManualHandoff?.checklist_en || publishEvidence?.manual_checklist_en || [];
                              const supervisedManualChecklist = Array.isArray(supervisedManualChecklistSource)
                                ? supervisedManualChecklistSource.filter(Boolean).map(String)
                                : [];
                              const supervisedCopyReadyText = String(
                                placementPacket?.copy_ready_text || supervisedPayload?.copy_ready_text || supervisedManualHandoff?.copy_ready_text || publishEvidence?.copy_ready_text || ''
                              ).trim();
                              const supervisedProfileHint = String(
                                placementPacket?.profile_hint || supervisedPayload?.profile_hint || supervisedManualHandoff?.profile_hint || publishEvidence?.profile_hint || ''
                              ).trim();
                              const supervisedTargetUrl = String(
                                placementPacket?.target_url || supervisedPayload?.target_url || supervisedManualHandoff?.target_url || publishEvidence?.target_url || ''
                              ).trim();
                              const placementChecklistSource = isRu
                                ? placementPacket?.checklist_ru || []
                                : placementPacket?.checklist_en || [];
                              const placementChecklist = Array.isArray(placementChecklistSource)
                                ? placementChecklistSource.filter(Boolean).map(String)
                                : [];
                              const placementHandoffChecklistSource = isRu
                                ? placementPacket?.handoff_checklist_ru || supervisedPayload?.handoff_checklist_ru || []
                                : placementPacket?.handoff_checklist_en || supervisedPayload?.handoff_checklist_en || [];
                              const placementHandoffChecklist = Array.isArray(placementHandoffChecklistSource)
                                ? placementHandoffChecklistSource.filter(Boolean).map(String).slice(0, 5)
                                : [];
                              const placementNextAction = String(
                                isRu
                                  ? placementPacket?.owner_next_action_ru || ''
                                  : placementPacket?.owner_next_action_en || ''
                              ).trim();
                              const placementTaskId = String(placementPacket?.automation_task_id || post.automation_task_id || '').trim();
                              const placementOutboxId = String(placementPacket?.openclaw_outbox_id || '').trim();
                              const placementLedgerId = String(placementPacket?.agent_action_ledger_id || supervisedLedgerId || '').trim();
                              const placementOperatorNextAction = String(
                                isRu
                                  ? placementPacket?.operator_next_action_ru || supervisedPayload?.operator_next_action_ru || ''
                                  : placementPacket?.operator_next_action_en || supervisedPayload?.operator_next_action_en || ''
                              ).trim();
                              const placementCompletionFields = Array.isArray(placementPacket?.completion_required_fields)
                                ? placementPacket.completion_required_fields.filter(Boolean).map(String).slice(0, 5)
                                : [];
                              const placementDoneCriteriaFallback = isRu
                                ? [
                                  'Предпросмотр на площадке показан человеку.',
                                  'Финальную публикацию нажал человек, не браузер-автоматизация.',
                                  'В LocalOS внесена ссылка или ID опубликованного поста, если площадка их даёт.',
                                  'Пост отмечен размещённым, чтобы реакции и заявки попали в следующий план.',
                                ]
                                : [
                                  'The platform preview was shown to a human.',
                                  'The final publish click was made by a human, not browser automation.',
                                  'LocalOS has the published post URL or ID if the platform provides one.',
                                  'The post is marked as published so reactions and leads can inform the next plan.',
                                ];
                              const placementDoneCriteriaSource = isRu
                                ? placementPacket?.done_criteria_ru || placementDoneCriteriaFallback
                                : placementPacket?.done_criteria_en || placementDoneCriteriaFallback;
                              const placementDoneCriteria = Array.isArray(placementDoneCriteriaSource)
                                ? placementDoneCriteriaSource.filter(Boolean).map(String).slice(0, 5)
                                : [];
                              const placementReadyChips = [
                                placementPacket?.target_ready
                                  ? (isRu ? 'цель готова' : 'target ready')
                                  : (isRu ? 'нужна ссылка на профиль' : 'profile link needed'),
                                placementPacket?.copy_ready
                                  ? (isRu ? 'текст готов' : 'copy ready')
                                  : (isRu ? 'нужен текст' : 'copy needed'),
                                placementPacket?.openclaw_task_requested
                                  ? (isRu ? 'задача отправлена' : 'task sent')
                                  : (isRu ? 'ожидает запуска' : 'waiting to start'),
                                placementPacket?.browser_final_click_allowed === false
                                  ? (isRu ? 'финальный клик человеком' : 'human final click')
                                  : '',
                              ].filter(Boolean);
                              const supervisedFallbackReasons = Array.isArray(supervisedPayload?.fallback_reasons)
                                ? supervisedPayload.fallback_reasons.filter(Boolean).map(String)
                                : [];
                              const supervisedSafety = _socialSupervisedSafetySummary(supervisedPayload?.safety_contract, isRu);
                              const supervisedHandoffStatus = String(
                                isRu
                                  ? supervisedHandoffState?.owner_status_ru || ''
                                  : supervisedHandoffState?.owner_status_en || ''
                              ).trim();
                              const supervisedHandoffNextAction = String(
                                isRu
                                  ? supervisedHandoffState?.owner_next_action_ru || ''
                                  : supervisedHandoffState?.owner_next_action_en || ''
                              ).trim();
                              const supervisedHandoffStateLabel = _socialSupervisedHandoffStateLabel(
                                String(supervisedHandoffState?.state || ''),
                                isRu,
                              );
                              const preflightStatus = String(post.metadata_json?.queue_preflight_status || post.metadata_json?.provider_status || '').trim();
                              const preflightMessage = String(
                                isRu
                                  ? post.metadata_json?.queue_preflight_message_ru || post.metadata_json?.provider_note || ''
                                  : post.metadata_json?.queue_preflight_message_en || post.metadata_json?.provider_note || ''
                              ).trim();
                              const nextActionLabel = _socialNextActionLabel(post.next_action || '', isRu);
                              const hasNextAction = Boolean(String(post.next_action || '').trim());
                              const evidenceTitle = String(isRu ? publishEvidence?.title_ru || '' : publishEvidence?.title_en || '').trim();
                              const evidenceSummary = String(isRu ? publishEvidence?.summary_ru || '' : publishEvidence?.summary_en || '').trim();
                              const evidenceNextAction = String(isRu ? publishEvidence?.next_action_ru || '' : publishEvidence?.next_action_en || '').trim();
                              const evidenceProofUrl = String(publishEvidence?.proof_url || post.provider_post_url || '').trim();
                              const evidenceProofId = String(publishEvidence?.proof_id || post.provider_post_id || '').trim();
                              const evidenceProviderStatus = String(publishEvidence?.provider_status || '').trim();
                              const scheduleAttention = post.schedule_attention || {};
                              const scheduleNeedsAttention = Boolean(scheduleAttention.requires_attention);
                              const scheduleAttentionMessage = String(
                                isRu
                                  ? scheduleAttention.message_ru || ''
                                  : scheduleAttention.message_en || ''
                              ).trim();
                              const scheduleAttentionNextAction = String(
                                isRu
                                  ? scheduleAttention.next_action_ru || ''
                                  : scheduleAttention.next_action_en || ''
                              ).trim();
                              const evidenceProofSource = String(publishEvidence?.proof_source || '').trim();
                              const evidenceProofQuality = String(publishEvidence?.proof_quality || '').trim();
                              const rehearsalSummary = String(isRu ? publishRehearsal?.summary_ru || '' : publishRehearsal?.summary_en || '').trim();
                              const rehearsalNextAction = String(isRu ? publishRehearsal?.next_action_ru || '' : publishRehearsal?.next_action_en || '').trim();
                              const rehearsalAction = String(isRu ? publishRehearsal?.dispatch_decision?.action_label_ru || '' : publishRehearsal?.dispatch_decision?.action_label_en || '').trim();
                              const rehearsalReason = String(isRu ? publishRehearsal?.dispatch_decision?.reason_label_ru || '' : publishRehearsal?.dispatch_decision?.reason_label_en || '').trim();
                              const rehearsalReady = Boolean(publishRehearsal?.ready_for_execution);
                              const rehearsalBlockers = Array.isArray(publishRehearsal?.blockers) ? publishRehearsal.blockers : [];
                              const actionHint = needsReview
                                  ? {
                                    tone: 'safe',
                                    textRu: 'Подтверждение только фиксирует, что текст проверен. Наружу ничего не отправится.',
                                    textEn: 'Approval only records that the copy was reviewed. Nothing is sent externally.',
                                  }
                                  : canQueue
                                    ? {
                                      tone: 'queue',
                                      textRu: isSupervisedPost
                                        ? 'Расписание зафиксирует дату. Для Яндекс/2ГИС LocalOS создаст контролируемое или ручное размещение, не автопубликацию.'
                                        : 'Расписание передаст пост worker-у: API-публикация начнётся только по дате и только при готовом канале.',
                                      textEn: isSupervisedPost
                                        ? 'Queueing records the date. For Yandex/2GIS, LocalOS creates supervised placement, not autopublish.'
                                        : 'Queueing hands the post to the worker: API publishing starts only on schedule and only when the channel is ready.',
                                    }
                                    : post.status === 'queued'
                                      ? {
                                        tone: 'queue',
                                        textRu: isSupervisedPost
                                          ? 'Пост ждёт дату. Когда наступит время, он перейдёт в контролируемое или ручное размещение.'
                                          : 'Пост ждёт дату. Worker обработает только due-публикации с подтверждённым текстом.',
                                        textEn: isSupervisedPost
                                          ? 'The post is waiting for its date. When due, it moves to supervised placement.'
                                          : 'The post is waiting for its date. The worker processes only due posts with approved copy.',
                                      }
                                      : canCreateSupervisedTask
                                        ? {
                                          tone: 'controlled',
                                          textRu: 'Контролируемое размещение подготовит текст, ссылку и инструкцию. Финальную кнопку публикации нажимает человек.',
                                          textEn: 'Supervised placement prepares copy, link, and instructions. A human clicks the final publish button.',
                                        }
                                        : canMarkPublished
                                          ? {
                                            tone: 'manual',
                                            textRu: 'Используйте это, когда пост уже размещён вручную или через контролируемое размещение, чтобы LocalOS смог собрать результат.',
                                            textEn: 'Use this after manual or supervised placement so LocalOS can collect results.',
                                          }
                                          : null;
                                return (
                                <div key={post.id} className="rounded-2xl border border-slate-200 bg-white p-3">
                                  <div className="flex flex-wrap items-start justify-between gap-2">
                                    <div>
                                      <div className="font-semibold text-slate-950">
                                        {_socialPlatformLabel(post.platform, isRu)}
                                      </div>
                                      <div className="mt-1 text-xs text-slate-500">
                                        {_socialPublishModeLabel(post.publish_mode, isRu)}
                                      </div>
                                    </div>
                                    <span className={_socialStatusClassName(post.status)}>
                                      {_socialStatusLabel(post.status, isRu)}
                                    </span>
                                  </div>
                                  {hasNextAction ? (
                                    <div className="mt-3 rounded-xl border border-blue-100 bg-blue-50 px-3 py-2 text-xs leading-5 text-blue-800">
                                      <div className="font-semibold text-blue-950">
                                        {isRu ? 'Следующий шаг' : 'Next action'}
                                      </div>
                                      <div>{nextActionLabel}</div>
                                    </div>
                                  ) : null}
                                  {scheduleNeedsAttention ? (
                                    <div
                                      data-testid={`social-post-schedule-attention-${post.id}`}
                                      className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-900"
                                    >
                                      <div className="font-semibold text-amber-950">
                                        {isRu ? 'Проверьте дату публикации' : 'Check publish date'}
                                      </div>
                                      {scheduleAttentionMessage ? <div>{scheduleAttentionMessage}</div> : null}
                                      {scheduleAttentionNextAction ? (
                                        <div className="mt-1">
                                          <span className="font-semibold">{isRu ? 'Что сделать: ' : 'Next: '}</span>
                                          {scheduleAttentionNextAction}
                                        </div>
                                      ) : null}
                                    </div>
                                  ) : null}
                                  <div className="mt-3 space-y-2">
                                    <div className="flex items-center justify-between gap-2">
                                      <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                                        {isRu ? 'Текст для канала' : 'Channel copy'}
                                      </div>
                                      {postTextLocked ? (
                                        <span className="text-[11px] font-medium text-slate-400">
                                          {isRu ? 'заблокировано после расписания' : 'locked after queue'}
                                        </span>
                                      ) : null}
                                    </div>
                                    <Textarea
                                      rows={5}
                                      value={postTextValue}
                                      onChange={(event) => setSocialTextEdits((prev) => ({ ...prev, [post.id]: event.target.value }))}
                                      disabled={postTextLocked || postBusy}
                                      placeholder={isRu ? 'Текст ещё не подготовлен' : 'Text is not prepared yet'}
                                    />
                                    {!postTextLocked && postTextDirty ? (
                                      <div className="flex flex-wrap items-center gap-2">
                                        <Button
                                          type="button"
                                          size="sm"
                                          variant="outline"
                                          onClick={() => { void saveSocialPostText(post, postTextFallback); }}
                                          disabled={postBusy}
                                        >
                                          {socialBusyAction === `save-text:${post.id}`
                                            ? (isRu ? 'Сохраняем...' : 'Saving...')
                                            : (isRu ? 'Сохранить текст' : 'Save copy')}
                                        </Button>
                                        <span className="text-xs leading-5 text-amber-700">
                                          {isRu
                                            ? 'После сохранения текст снова нужно подтвердить перед публикацией.'
                                            : 'After saving, copy must be approved again before publishing.'}
                                        </span>
                                      </div>
                                    ) : null}
                                  </div>
                                  {isSupervisedPost ? (
                                    <div
                                      data-testid="social-supervised-handoff"
                                      className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-800"
                                    >
                                      <div className="font-semibold text-amber-950">
                                        {isRu ? 'Контролируемое размещение' : 'Supervised placement'}
                                      </div>
                                      <div className="mt-1">
                                        {isRu
                                          ? 'Для этого канала LocalOS готовит задачу для OpenClaw/manual handoff, а не делает вид стабильной API-автопубликации.'
                                          : 'For this channel LocalOS prepares an OpenClaw/manual handoff task instead of pretending stable API autopublishing exists.'}
                                      </div>
                                      {placementPacket ? (
                                        <div
                                          data-testid="social-supervised-placement-packet"
                                          className="mt-3 rounded-lg border border-amber-200 bg-white px-3 py-2 text-amber-950"
                                        >
                                          <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                                            <div>
                                              <div className="font-semibold">
                                                {isRu ? 'Пакет для размещения' : 'Placement packet'}
                                              </div>
                                              <div className="mt-1 text-[11px] leading-5 text-amber-900">
                                                {placementNextAction || (isRu
                                                  ? 'Откройте площадку, проверьте предпросмотр и завершите размещение вручную.'
                                                  : 'Open the platform, review the preview, and finish placement manually.')}
                                              </div>
                                            </div>
                                            <span className="rounded-full bg-amber-100 px-2.5 py-1 text-[11px] font-semibold text-amber-800">
                                              {placementPacket.manual_fallback_required
                                                ? (isRu ? 'ручной режим' : 'manual mode')
                                                : (isRu ? 'контролируемо' : 'supervised')}
                                            </span>
                                          </div>
                                          <div className="mt-2 grid gap-2 sm:grid-cols-2">
                                            <div className="rounded-md bg-amber-50 px-2 py-1.5">
                                              <div className="font-semibold">
                                                {isRu ? 'Куда размещать' : 'Where to post'}
                                              </div>
                                              <div className="mt-1 break-all text-[11px] leading-5 text-amber-900">
                                                {supervisedTargetUrl || supervisedProfileHint || (isRu ? 'Ссылка на профиль не найдена' : 'Profile link is missing')}
                                              </div>
                                            </div>
                                            <div className="rounded-md bg-amber-50 px-2 py-1.5">
                                              <div className="font-semibold">
                                                {isRu ? 'Что готово' : 'Ready assets'}
                                              </div>
                                              <div className="mt-1 text-[11px] leading-5 text-amber-900">
                                                {isRu
                                                  ? `текст: ${placementPacket.copy_ready ? 'готов' : 'нужен'} · шагов: ${Number(placementPacket.checklist_count || placementChecklist.length || 0)}`
                                                  : `copy: ${placementPacket.copy_ready ? 'ready' : 'needed'} · steps: ${Number(placementPacket.checklist_count || placementChecklist.length || 0)}`}
                                              </div>
                                            </div>
                                          </div>
                                          {placementReadyChips.length > 0 ? (
                                            <div className="mt-2 flex flex-wrap gap-1.5 text-[11px]">
                                              {placementReadyChips.map((chip) => (
                                                <span key={`${post.id}:placement-chip:${chip}`} className="rounded-full bg-amber-100 px-2 py-0.5 font-medium text-amber-800">
                                                  {chip}
                                                </span>
                                              ))}
                                            </div>
                                          ) : null}
                                          {placementTaskId || placementOutboxId || placementLedgerId ? (
                                            <div className="mt-2 grid gap-1 text-[11px] text-amber-900 sm:grid-cols-3">
                                              {placementTaskId ? (
                                                <div>
                                                  <span className="font-semibold">task:</span>{' '}
                                                  <span className="font-mono">{placementTaskId}</span>
                                                </div>
                                              ) : null}
                                              {placementOutboxId ? (
                                                <div>
                                                  <span className="font-semibold">outbox:</span>{' '}
                                                  <span className="font-mono">{placementOutboxId}</span>
                                                </div>
                                              ) : null}
                                              {placementLedgerId ? (
                                                <div>
                                                  <span className="font-semibold">ledger:</span>{' '}
                                                  <span className="font-mono">{placementLedgerId}</span>
                                                </div>
                                              ) : null}
                                            </div>
                                          ) : null}
                                          {placementOperatorNextAction || placementCompletionFields.length > 0 || placementPacket.preview_required ? (
                                            <div className="mt-2 rounded-md bg-amber-50 px-2 py-1.5 text-[11px] leading-5 text-amber-900">
                                              {placementOperatorNextAction ? (
                                                <div>
                                                  <span className="font-semibold">
                                                    {isRu ? 'Как выполнить: ' : 'How to execute: '}
                                                  </span>
                                                  {placementOperatorNextAction}
                                                </div>
                                              ) : null}
                                              {placementPacket.preview_required ? (
                                                <div>
                                                  <span className="font-semibold">
                                                    {isRu ? 'Предпросмотр: ' : 'Preview: '}
                                                  </span>
                                                  {isRu ? 'обязателен перед финальным кликом' : 'required before the final click'}
                                                </div>
                                              ) : null}
                                              {placementCompletionFields.length > 0 ? (
                                                <div>
                                                  <span className="font-semibold">
                                                    {isRu ? 'Вернуть результат: ' : 'Return result: '}
                                                  </span>
                                                  {placementCompletionFields.join(', ')}
                                                </div>
                                              ) : null}
                                            </div>
                                          ) : null}
                                          {placementHandoffChecklist.length > 0 ? (
                                            <div
                                              data-testid="social-supervised-handoff-checklist"
                                              className="mt-2 rounded-md border border-amber-100 bg-amber-50 px-2 py-1.5 text-[11px] leading-5 text-amber-900"
                                            >
                                              <div className="font-semibold text-amber-950">
                                                {isRu ? 'Маршрут handoff' : 'Handoff route'}
                                              </div>
                                              <ol className="mt-1 list-decimal space-y-1 pl-4">
                                                {placementHandoffChecklist.map((step, index) => (
                                                  <li key={`${post.id}:handoff-checklist:${index}`}>{step}</li>
                                                ))}
                                              </ol>
                                            </div>
                                          ) : null}
                                          {placementDoneCriteria.length > 0 ? (
                                            <div
                                              data-testid="social-supervised-done-criteria"
                                              className="mt-2 rounded-md border border-amber-100 bg-amber-50 px-2 py-1.5 text-[11px] leading-5 text-amber-900"
                                            >
                                              <div className="font-semibold text-amber-950">
                                                {isRu ? 'Готово, когда' : 'Done when'}
                                              </div>
                                              <ul className="mt-1 list-disc space-y-1 pl-4">
                                                {placementDoneCriteria.map((criterion, index) => (
                                                  <li key={`${post.id}:done-criterion:${index}`}>{criterion}</li>
                                                ))}
                                              </ul>
                                            </div>
                                          ) : null}
                                        </div>
                                      ) : null}
                                      {supervisedHandoffState ? (
                                        <div className="mt-3 rounded-lg border border-amber-200 bg-white px-3 py-2 text-amber-950">
                                          <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                                            <div>
                                              <div className="font-semibold">
                                                {isRu ? 'Состояние handoff' : 'Handoff state'}
                                              </div>
                                              <div className="mt-1 text-[11px] leading-5 text-amber-900">
                                                {supervisedHandoffStatus || supervisedHandoffStateLabel}
                                              </div>
                                              {supervisedHandoffNextAction ? (
                                                <div className="mt-1 text-[11px] leading-5 text-amber-900">
                                                  <span className="font-semibold">
                                                    {isRu ? 'Что сделать: ' : 'Next: '}
                                                  </span>
                                                  {supervisedHandoffNextAction}
                                                </div>
                                              ) : null}
                                            </div>
                                            {supervisedHandoffStateLabel ? (
                                              <span className="rounded-full bg-amber-100 px-2.5 py-1 text-[11px] font-semibold text-amber-800">
                                                {supervisedHandoffStateLabel}
                                              </span>
                                            ) : null}
                                          </div>
                                          <div className="mt-2 flex flex-wrap gap-1.5 text-[11px]">
                                            {supervisedHandoffState.task_payload_ready ? (
                                              <span className="rounded-full bg-emerald-50 px-2 py-0.5 font-medium text-emerald-800">
                                                {isRu ? 'payload готов' : 'payload ready'}
                                              </span>
                                            ) : null}
                                            {supervisedHandoffState.openclaw_ready ? (
                                              <span className="rounded-full bg-sky-50 px-2 py-0.5 font-medium text-sky-800">
                                                {isRu ? 'OpenClaw готов' : 'OpenClaw ready'}
                                              </span>
                                            ) : (
                                              <span className="rounded-full bg-amber-100 px-2 py-0.5 font-medium text-amber-800">
                                                {isRu ? 'ручной режим' : 'manual fallback'}
                                              </span>
                                            )}
                                            {supervisedHandoffState.openclaw_task_requested ? (
                                              <span className="rounded-full bg-sky-50 px-2 py-0.5 font-medium text-sky-800">
                                                {isRu ? 'task отправлен' : 'task requested'}
                                              </span>
                                            ) : (
                                              <span className="rounded-full bg-white px-2 py-0.5 font-medium text-amber-800">
                                                {isRu ? 'task не отправлен во внешний runtime' : 'task not sent to external runtime'}
                                              </span>
                                            )}
                                            {supervisedHandoffState.ledger_recorded ? (
                                              <span className="rounded-full bg-slate-100 px-2 py-0.5 font-medium text-slate-700">
                                                {isRu ? 'журнал записан' : 'ledger recorded'}
                                              </span>
                                            ) : null}
                                            {supervisedHandoffState.browser_final_click_allowed === false ? (
                                              <span className="rounded-full bg-red-50 px-2 py-0.5 font-medium text-red-700">
                                                {isRu ? 'финальный клик запрещён' : 'final click forbidden'}
                                              </span>
                                            ) : null}
                                          </div>
                                          {supervisedHandoffState.openclaw_outbox_id ? (
                                            <div className="mt-2 font-mono text-[11px] text-amber-900">
                                              outbox: {supervisedHandoffState.openclaw_outbox_id}
                                            </div>
                                          ) : null}
                                        </div>
                                      ) : null}
                                      {supervisedPayload?.instruction_ru || supervisedPayload?.instruction_en ? (
                                        <div className="mt-2 text-amber-900">
                                          {isRu
                                            ? String(supervisedPayload.instruction_ru || '')
                                            : String(supervisedPayload.instruction_en || '')}
                                        </div>
                                      ) : null}
                                      <div className="mt-3 grid gap-2 rounded-lg bg-white px-3 py-2 text-[11px] leading-5 text-amber-950 sm:grid-cols-2">
                                        <div>
                                          <div className="font-semibold">
                                            {isRu ? 'Ассистент сделает' : 'Assistant will'}
                                          </div>
                                          <div className="mt-1 text-amber-900">
                                            {supervisedSafety.allowed.join(', ')}
                                          </div>
                                        </div>
                                        <div>
                                          <div className="font-semibold">
                                            {isRu ? 'Ассистент не сделает' : 'Assistant will not'}
                                          </div>
                                          <div className="mt-1 text-amber-900">
                                            {supervisedSafety.forbidden.join(', ')}
                                          </div>
                                        </div>
                                        {supervisedSafety.fallback.length > 0 ? (
                                          <div className="sm:col-span-2 text-amber-900">
                                            <span className="font-semibold">
                                              {isRu ? 'Если мешает логин/капча/интерфейс: ' : 'If login/captcha/UI blocks it: '}
                                            </span>
                                            {supervisedSafety.fallback.join(', ')}
                                          </div>
                                        ) : null}
                                      </div>
                                      {supervisedManualInstruction || supervisedManualChecklist.length > 0 || supervisedCopyReadyText ? (
                                        <div className="mt-3 rounded-lg bg-white px-3 py-2 text-amber-950">
                                          <div className="font-semibold">
                                            {isRu ? 'Ручной режим без догадок' : 'Manual fallback without guessing'}
                                          </div>
                                          {supervisedManualInstruction ? (
                                            <div className="mt-1 text-[11px] leading-5 text-amber-900">
                                              {supervisedManualInstruction}
                                            </div>
                                          ) : null}
                                          {supervisedProfileHint ? (
                                            <div className="mt-1 text-[11px] leading-5 text-amber-900">
                                              {isRu ? 'Профиль: ' : 'Profile: '}
                                              {supervisedProfileHint}
                                            </div>
                                          ) : null}
                                          {supervisedCopyReadyText ? (
                                            <div className="mt-2 rounded-md border border-amber-100 bg-amber-50 px-2 py-1.5 text-[11px] leading-5 text-slate-700">
                                              {supervisedCopyReadyText}
                                            </div>
                                          ) : null}
                                          {supervisedManualChecklist.length > 0 ? (
                                            <ol className="mt-2 list-decimal space-y-1 pl-4 text-[11px] leading-5 text-amber-900">
                                              {supervisedManualChecklist.map((step, index) => (
                                                <li key={`${post.id}:manual-step:${index}`}>{step}</li>
                                              ))}
                                            </ol>
                                          ) : null}
                                        </div>
                                      ) : null}
                                      {post.automation_task_id || supervisedTaskStatus || supervisedActionRef || supervisedTargetUrl ? (
                                        <div className="mt-3 grid gap-2 rounded-lg bg-white px-3 py-2 text-[11px] text-amber-950 sm:grid-cols-2">
                                          {post.automation_task_id ? (
                                            <div>
                                              <span className="font-semibold">task:</span>{' '}
                                              <span className="font-mono">{post.automation_task_id}</span>
                                            </div>
                                          ) : null}
                                          {supervisedTaskStatus ? (
                                            <div>
                                              <span className="font-semibold">status:</span>{' '}
                                              <span className="font-mono">{supervisedTaskStatus}</span>
                                            </div>
                                          ) : null}
                                          {supervisedActionRef ? (
                                            <div>
                                              <span className="font-semibold">action:</span>{' '}
                                              <span className="font-mono">{supervisedActionRef}</span>
                                            </div>
                                          ) : null}
                                          {supervisedTargetUrl ? (
                                            <div>
                                              <span className="font-semibold">{isRu ? 'цель:' : 'target:'}</span>{' '}
                                              <span className="break-all">{supervisedTargetUrl}</span>
                                            </div>
                                          ) : null}
                                        </div>
                                      ) : null}
                                      {supervisedLedgerId ? (
                                        <div className="mt-1 font-mono text-[11px] text-amber-900">
                                          ledger: {supervisedLedgerId}
                                        </div>
                                      ) : null}
                                      {supervisedCapabilityLine ? (
                                        <div className="mt-1 text-[11px] text-amber-900">
                                          {supervisedCapabilityLine}
                                        </div>
                                      ) : null}
                                      {supervisedFallbackReasons.length > 0 ? (
                                        <div className="mt-1 text-[11px] text-amber-900">
                                          {isRu ? 'ручной режим: ' : 'fallback: '}
                                          {supervisedFallbackReasons.join(', ')}
                                        </div>
                                      ) : null}
                                      {post.automation_task_id || supervisedLedgerId ? (
                                        <div className="mt-2 text-[11px] font-medium text-amber-900">
                                          {isRu
                                            ? 'Журнал действия создан; финальная публикация остаётся за человеком.'
                                            : 'Action ledger is recorded; final publishing stays human-controlled.'}
                                        </div>
                                        ) : null}
                                      </div>
                                    ) : null}
                                    {publishEvidence && (evidenceTitle || evidenceSummary || evidenceNextAction || evidenceProofUrl || evidenceProofId) ? (
                                      <div className={_socialPublishEvidenceClassName(publishEvidence.tone || '')}>
                                        {evidenceTitle ? (
                                          <div className="font-semibold">
                                            {evidenceTitle}
                                          </div>
                                        ) : null}
                                        {evidenceSummary ? (
                                          <div className="mt-1">
                                            {evidenceSummary}
                                          </div>
                                        ) : null}
                                        {evidenceNextAction ? (
                                          <div className="mt-1 font-medium">
                                            {evidenceNextAction}
                                          </div>
                                        ) : null}
                                        {evidenceProofQuality || evidenceProofSource || publishEvidence.ready_for_metrics || publishEvidence.external_publish_proven ? (
                                          <div
                                            data-testid="social-provider-proof-quality"
                                            className="mt-2 flex flex-wrap gap-1.5 text-[11px]"
                                          >
                                            {evidenceProofQuality ? (
                                              <span className="rounded-full bg-white/70 px-2 py-0.5 font-medium">
                                                {isRu ? 'proof: ' : 'proof: '}
                                                {_socialProofQualityLabel(evidenceProofQuality, isRu)}
                                              </span>
                                            ) : null}
                                            {evidenceProofSource ? (
                                              <span className="rounded-full bg-white/70 px-2 py-0.5 font-mono">
                                                {evidenceProofSource}
                                              </span>
                                            ) : null}
                                            {publishEvidence.external_publish_proven ? (
                                              <span className="rounded-full bg-emerald-50 px-2 py-0.5 font-medium text-emerald-700">
                                                {isRu ? 'внешняя публикация подтверждена' : 'external publish proven'}
                                              </span>
                                            ) : null}
                                            {publishEvidence.ready_for_metrics ? (
                                              <span className="rounded-full bg-sky-50 px-2 py-0.5 font-medium text-sky-700">
                                                {isRu ? 'готово к метрикам' : 'ready for metrics'}
                                              </span>
                                            ) : null}
                                            {publishEvidence.manual_confirmation ? (
                                              <span className="rounded-full bg-amber-50 px-2 py-0.5 font-medium text-amber-700">
                                                {isRu ? 'ручная отметка' : 'manual confirmation'}
                                              </span>
                                            ) : null}
                                          </div>
                                        ) : null}
                                        {evidenceProofUrl || evidenceProofId || evidenceProviderStatus ? (
                                          <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px]">
                                            {evidenceProofUrl ? (
                                              <a
                                                href={evidenceProofUrl}
                                                target="_blank"
                                                rel="noreferrer"
                                                className="font-medium underline underline-offset-2"
                                              >
                                                {isRu ? 'Открыть опубликованный пост' : 'Open published post'}
                                              </a>
                                            ) : null}
                                            {evidenceProofId ? (
                                              <span className="font-mono">
                                                id: {evidenceProofId}
                                              </span>
                                            ) : null}
                                            {evidenceProviderStatus ? (
                                              <span className="font-mono">
                                                status: {evidenceProviderStatus}
                                              </span>
                                            ) : null}
                                          </div>
                                        ) : null}
                                      </div>
                                    ) : null}
                                    {post.last_error && !publishEvidence ? (
                                      <div className="mt-3 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-xs leading-5 text-red-700">
                                        {post.last_error}
                                      </div>
                                    ) : null}
                                  {!isSupervisedPost && (preflightMessage || preflightStatus) ? (
                                    <div className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-800">
                                      <div className="font-semibold text-amber-950">
                                        {isRu ? 'Готовность канала' : 'Channel readiness'}
                                      </div>
                                      {preflightMessage ? (
                                        <div className="mt-1 text-amber-900">{preflightMessage}</div>
                                      ) : null}
                                      {preflightStatus ? (
                                        <div className="mt-1 font-mono text-[11px] text-amber-900">
                                          status: {preflightStatus}
                                        </div>
                                      ) : null}
                                    </div>
                                  ) : null}
                                  {publishRehearsal ? (
                                    <div
                                      data-testid="social-publish-rehearsal"
                                      className={[
                                        'mt-3 rounded-xl border px-3 py-2 text-xs leading-5',
                                        rehearsalReady
                                          ? 'border-emerald-200 bg-emerald-50 text-emerald-800'
                                          : 'border-amber-200 bg-amber-50 text-amber-800',
                                      ].join(' ')}
                                    >
                                      <div className={rehearsalReady ? 'font-semibold text-emerald-950' : 'font-semibold text-amber-950'}>
                                        {isRu ? 'Проверка запуска' : 'Launch check'}
                                      </div>
                                      {rehearsalSummary ? (
                                        <div className="mt-1">{rehearsalSummary}</div>
                                      ) : null}
                                      {rehearsalNextAction ? (
                                        <div className="mt-1 font-medium">
                                          {rehearsalNextAction}
                                        </div>
                                      ) : null}
                                      <div className="mt-2 flex flex-wrap gap-1.5 text-[11px]">
                                        <span className="rounded-full bg-white/70 px-2 py-0.5 font-medium">
                                          {isRu ? 'наружу ничего не отправлено' : 'nothing sent externally'}
                                        </span>
                                        <span className="rounded-full bg-white/70 px-2 py-0.5 font-medium">
                                          {publishRehearsal.would_external_publish
                                            ? (isRu ? 'API готов к публикации' : 'API publish ready')
                                            : (isRu ? 'без API-публикации сейчас' : 'no API publish now')}
                                        </span>
                                        {publishRehearsal.would_create_supervised_task ? (
                                          <span className="rounded-full bg-white/70 px-2 py-0.5 font-medium">
                                            {isRu ? 'создаст supervised task' : 'will create supervised task'}
                                          </span>
                                        ) : null}
                                        {publishRehearsal.browser_final_click_allowed === false ? (
                                          <span className="rounded-full bg-white/70 px-2 py-0.5 font-medium">
                                            {isRu ? 'финальный клик запрещён' : 'final click forbidden'}
                                          </span>
                                        ) : null}
                                      </div>
                                      {rehearsalAction || rehearsalReason || rehearsalBlockers.length > 0 ? (
                                        <div className="mt-2 grid gap-1 rounded-lg bg-white/70 px-3 py-2 text-[11px]">
                                          {rehearsalAction ? (
                                            <div>
                                              <span className="font-semibold">{isRu ? 'Что будет: ' : 'Action: '}</span>
                                              {rehearsalAction}
                                            </div>
                                          ) : null}
                                          {rehearsalReason ? (
                                            <div>
                                              <span className="font-semibold">{isRu ? 'Причина: ' : 'Reason: '}</span>
                                              {rehearsalReason}
                                            </div>
                                          ) : null}
                                          {rehearsalBlockers.length > 0 ? (
                                            <div>
                                              <span className="font-semibold">{isRu ? 'Блокер: ' : 'Blocker: '}</span>
                                              {String(
                                                isRu
                                                  ? rehearsalBlockers[0]?.message_ru || rehearsalBlockers[0]?.code || ''
                                                  : rehearsalBlockers[0]?.message_en || rehearsalBlockers[0]?.code || ''
                                              )}
                                            </div>
                                          ) : null}
                                        </div>
                                      ) : null}
                                    </div>
                                  ) : null}
                                  {!canRecordResult ? (
                                    <div
                                      data-testid="social-preview-before-approval"
                                      className="mt-3 rounded-xl border border-sky-100 bg-sky-50 px-3 py-3 text-xs leading-5 text-sky-900"
                                    >
                                      <div className="flex flex-wrap items-center justify-between gap-2">
                                        <div className="font-semibold text-sky-950">
                                          {isRu ? 'Предпросмотр перед подтверждением' : 'Preview before approval'}
                                        </div>
                                        <span className="rounded-full bg-white px-2 py-0.5 text-[11px] font-medium text-sky-800">
                                          {_formatPlanItemDate(post.scheduled_for, isRu)}
                                        </span>
                                      </div>
                                      <div className="mt-2 grid gap-2 sm:grid-cols-2">
                                        <div>
                                          <div className="text-[11px] uppercase tracking-[0.12em] text-sky-700">
                                            {isRu ? 'Канал' : 'Channel'}
                                          </div>
                                          <div className="font-medium">
                                            {_socialPlatformLabel(post.platform, isRu)}
                                          </div>
                                        </div>
                                        <div>
                                          <div className="text-[11px] uppercase tracking-[0.12em] text-sky-700">
                                            {isRu ? 'Исполнение' : 'Execution'}
                                          </div>
                                          <div className="font-medium">
                                            {_socialPublishModeLabel(post.publish_mode, isRu)}
                                          </div>
                                        </div>
                                      </div>
                                      <div className="mt-2 rounded-lg bg-white px-3 py-2 text-slate-700">
                                        {postTextValue.trim()
                                          ? postTextValue.trim()
                                          : (isRu ? 'Текст ещё пустой: перед подтверждением нужно сохранить текст.' : 'Copy is still empty: save copy before approval.')}
                                      </div>
                                      <div className="mt-2 text-[11px] text-sky-800">
                                        {isSupervisedPost
                                          ? (isRu
                                            ? 'После подтверждения LocalOS подготовит контролируемое или ручное размещение; финальная публикация остаётся за человеком.'
                                            : 'After approval, LocalOS prepares supervised or manual placement; final publishing stays human-controlled.')
                                          : (isRu
                                            ? 'После подтверждения можно поставить в расписание; API-публикация запустится только исполнителем и только по дате.'
                                            : 'After approval, you can queue it; API publishing starts only through the worker and only on schedule.')}
                                      </div>
                                    </div>
                                  ) : null}
                                  {canMarkPublished ? (
                                    <div className="mt-3 grid gap-2 rounded-xl border border-slate-200 bg-slate-50 p-3 md:grid-cols-2">
                                      <div className="md:col-span-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                                        {isRu ? 'Факт размещения' : 'Placement proof'}
                                      </div>
                                      <Input
                                        value={manualRefs.url}
                                        onChange={(event) => setManualPublishRefs((prev) => ({
                                          ...prev,
                                          [post.id]: {
                                            url: event.target.value,
                                            id: prev[post.id]?.id ?? String(post.provider_post_id || ''),
                                          },
                                        }))}
                                        placeholder={isRu ? 'Ссылка на пост, если есть' : 'Post URL, if available'}
                                        disabled={postBusy}
                                      />
                                      <Input
                                        value={manualRefs.id}
                                        onChange={(event) => setManualPublishRefs((prev) => ({
                                          ...prev,
                                          [post.id]: {
                                            url: prev[post.id]?.url ?? String(post.provider_post_url || ''),
                                            id: event.target.value,
                                          },
                                        }))}
                                        placeholder={isRu ? 'ID поста, если есть' : 'Post ID, if available'}
                                        disabled={postBusy}
                                      />
                                      <div className="md:col-span-2 text-xs leading-5 text-slate-500">
                                        {isRu
                                          ? 'Можно оставить пустым, но ссылка помогает потом связать реакции и заявки с конкретной публикацией.'
                                          : 'Optional, but a URL helps connect reactions and leads to the exact publication later.'}
                                      </div>
                                    </div>
                                  ) : null}
                                    {(post.provider_post_url || post.provider_post_id) && !publishEvidence ? (
                                      <div className="mt-3 rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs leading-5 text-emerald-800">
                                      {post.provider_post_url ? (
                                        <a
                                          href={post.provider_post_url}
                                          target="_blank"
                                          rel="noreferrer"
                                          className="font-medium underline underline-offset-2"
                                        >
                                          {isRu ? 'Открыть опубликованный пост' : 'Open published post'}
                                        </a>
                                      ) : null}
                                      {post.provider_post_id ? (
                                        <div className="font-mono text-[11px] text-emerald-900">
                                          id: {post.provider_post_id}
                                        </div>
                                      ) : null}
                                    </div>
                                  ) : null}
                                  <div className="mt-3 flex flex-wrap gap-2">
                                    {post.status !== 'published' ? (
                                      <Button
                                        type="button"
                                        size="sm"
                                        variant="outline"
                                        onClick={() => { void rehearseSocialPostPublish(post); }}
                                        disabled={postBusy || postTextDirty}
                                      >
                                        {socialBusyAction === `rehearsal:${post.id}`
                                          ? (isRu ? 'Проверяем...' : 'Checking...')
                                          : (isRu ? 'Проверить запуск' : 'Check launch')}
                                      </Button>
                                    ) : null}
                                    {needsReview ? (
                                      <Button
                                        type="button"
                                        size="sm"
                                        onClick={() => { void approveSocialPostItem(post); }}
                                        disabled={postBusy || postTextDirty}
                                      >
                                        {isRu ? 'Подтвердить' : 'Approve'}
                                      </Button>
                                    ) : null}
                                    {canQueue ? (
                                      <Button
                                        type="button"
                                        size="sm"
                                        variant="outline"
                                        onClick={() => { void queueSocialPostItem(post); }}
                                        disabled={postBusy || postTextDirty}
                                      >
                                        {isRu ? 'Поставить в расписание' : 'Queue on schedule'}
                                      </Button>
                                    ) : null}
                                    {post.status === 'queued' ? (
                                      <span className="rounded-full border border-blue-200 bg-blue-50 px-3 py-1.5 text-xs font-medium text-blue-800">
                                        {isRu ? 'В расписании' : 'Scheduled'}
                                      </span>
                                    ) : null}
                                    {canCreateSupervisedTask ? (
                                      <Button
                                        type="button"
                                        size="sm"
                                        variant="outline"
                                        onClick={() => { void createSupervisedPostTask(post); }}
                                        disabled={postBusy || postTextDirty}
                                      >
                                        {isRu ? 'Подготовить контролируемое размещение' : 'Prepare supervised placement'}
                                      </Button>
                                    ) : null}
                                    {canMarkPublished ? (
                                      <>
                                        {postTextValue.trim() ? (
                                          <Button
                                            type="button"
                                            size="sm"
                                            variant="outline"
                                            onClick={() => { void copySocialPostText(post, postTextValue); }}
                                            disabled={postBusy}
                                          >
                                            {isRu ? 'Скопировать текст' : 'Copy text'}
                                          </Button>
                                        ) : null}
                                        {supervisedTargetUrl ? (
                                          <Button
                                            type="button"
                                            size="sm"
                                            variant="outline"
                                            onClick={() => window.open(supervisedTargetUrl, '_blank', 'noopener,noreferrer')}
                                          >
                                            {isRu ? 'Открыть площадку' : 'Open platform'}
                                          </Button>
                                        ) : null}
                                        {post.status === 'needs_supervised_publish' ? (
                                          <Button
                                            type="button"
                                            size="sm"
                                            variant="outline"
                                            onClick={() => { void markSupervisedPostBlocked(post); }}
                                            disabled={postBusy}
                                          >
                                            {isRu ? 'Нужен ручной режим' : 'Manual fallback needed'}
                                          </Button>
                                        ) : null}
                                        <Button
                                          type="button"
                                          size="sm"
                                          variant="outline"
                                          onClick={() => { void markSocialPostPublished(post); }}
                                          disabled={postBusy}
                                        >
                                          {isRu ? 'Отметить размещённым' : 'Mark published'}
                                        </Button>
                                      </>
                                    ) : null}
                                    {actionHint ? (
                                      <div
                                        className={[
                                          'w-full rounded-xl border px-3 py-2 text-xs leading-5',
                                          actionHint.tone === 'safe'
                                            ? 'border-sky-100 bg-sky-50 text-sky-800'
                                            : actionHint.tone === 'queue'
                                              ? 'border-blue-100 bg-blue-50 text-blue-800'
                                              : actionHint.tone === 'controlled'
                                                ? 'border-amber-100 bg-amber-50 text-amber-800'
                                                : 'border-slate-200 bg-slate-50 text-slate-700',
                                        ].join(' ')}
                                      >
                                        {isRu ? actionHint.textRu : actionHint.textEn}
                                      </div>
                                    ) : null}
                                    {canRecordResult ? (
                                      <div className="mt-1 flex w-full flex-col gap-2 rounded-xl border border-emerald-100 bg-emerald-50/60 px-3 py-2">
                                        {resultPacket ? (
                                          <div
                                            data-testid="social-result-collection-packet"
                                            className="rounded-lg border border-emerald-100 bg-white px-3 py-2 text-xs leading-5 text-emerald-900"
                                          >
                                            <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                                              <div>
                                                <div className="font-semibold text-emerald-950">
                                                  {isRu ? 'Результат публикации' : 'Post result'}
                                                </div>
                                                <div className="mt-1">
                                                  {isRu
                                                    ? String(resultPacket.owner_next_action_ru || 'Отметьте заявки, обращения или ранние сигналы.')
                                                    : String(resultPacket.owner_next_action_en || 'Record leads, inquiries, or early signals.')}
                                                </div>
                                              </div>
                                              <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-[11px] font-semibold text-emerald-800">
                                                {resultPacket.ready_for_recommendation
                                                  ? (isRu ? 'есть данные для плана' : 'plan data ready')
                                                  : (isRu ? 'нужен результат' : 'result needed')}
                                              </span>
                                            </div>
                                            <div className="mt-2 grid gap-2 sm:grid-cols-2">
                                              <div className="rounded-md bg-emerald-50 px-2 py-1.5">
                                                <div className="font-semibold">
                                                  {isRu ? 'Главная метрика' : 'Primary metric'}
                                                </div>
                                                <div className="mt-1 text-[11px] text-emerald-900">
                                                  {isRu
                                                    ? `заявки ${Number(resultPacket.leads || 0)} · обращения ${Number(resultPacket.inquiries || 0)}`
                                                    : `leads ${Number(resultPacket.leads || 0)} · inquiries ${Number(resultPacket.inquiries || 0)}`}
                                                </div>
                                              </div>
                                              <div className="rounded-md bg-emerald-50 px-2 py-1.5">
                                                <div className="font-semibold">
                                                  {isRu ? 'Ранние сигналы' : 'Early signals'}
                                                </div>
                                                <div className="mt-1 text-[11px] text-emerald-900">
                                                  {isRu
                                                    ? `комм. ${Number(resultPacket.comments || 0)} · репосты ${Number(resultPacket.shares || 0)} · клики ${Number(resultPacket.clicks || 0)} · лайки ${Number(resultPacket.likes || 0)} · просмотры ${Number(resultPacket.views || 0)}`
                                                    : `comments ${Number(resultPacket.comments || 0)} · shares ${Number(resultPacket.shares || 0)} · clicks ${Number(resultPacket.clicks || 0)} · likes ${Number(resultPacket.likes || 0)} · views ${Number(resultPacket.views || 0)}`}
                                                </div>
                                              </div>
                                            </div>
                                          </div>
                                        ) : null}
                                        <div className="text-xs leading-5 text-emerald-900">
                                          {isRu
                                            ? 'Отмечайте заявки и обращения в первую очередь: LocalOS считает их главным результатом и по ним предлагает изменения следующего плана. Лайки и просмотры - только ранний сигнал.'
                                            : 'Record leads and inquiries first: LocalOS treats them as the main result and uses them to suggest next-plan changes. Likes and views are only early signals.'}
                                        </div>
                                        <div className="flex flex-wrap items-center gap-2">
                                          <span className="text-xs font-semibold uppercase text-emerald-800">
                                            {isRu ? 'Главный результат' : 'Primary result'}
                                          </span>
                                          <Button
                                            type="button"
                                            size="sm"
                                            className="h-7 bg-emerald-700 px-2 text-xs text-white hover:bg-emerald-800"
                                            onClick={() => { void recordSocialPostAttribution(post, 'lead'); }}
                                            disabled={postBusy}
                                          >
                                            {isRu ? 'Была заявка' : 'Record lead'}
                                          </Button>
                                          <Button
                                            type="button"
                                            size="sm"
                                            className="h-7 bg-emerald-700 px-2 text-xs text-white hover:bg-emerald-800"
                                            onClick={() => { void recordSocialPostAttribution(post, 'inquiry'); }}
                                            disabled={postBusy}
                                          >
                                            {isRu ? 'Было обращение' : 'Record inquiry'}
                                          </Button>
                                        </div>
                                        <div className="flex flex-wrap items-center gap-2">
                                          <span className="text-xs font-semibold uppercase text-slate-500">
                                            {isRu ? 'Ранние сигналы' : 'Early signals'}
                                          </span>
                                          <Button
                                            type="button"
                                            size="sm"
                                            variant="outline"
                                            className="h-7 bg-white px-2 text-xs"
                                            onClick={() => { void recordSocialPostAttribution(post, 'comment'); }}
                                            disabled={postBusy}
                                          >
                                            {isRu ? 'Комментарий' : 'Comment'}
                                          </Button>
                                          <Button
                                            type="button"
                                            size="sm"
                                            variant="outline"
                                            className="h-7 bg-white px-2 text-xs"
                                            onClick={() => { void recordSocialPostAttribution(post, 'share'); }}
                                            disabled={postBusy}
                                          >
                                            {isRu ? 'Репост' : 'Share'}
                                          </Button>
                                          <Button
                                            type="button"
                                            size="sm"
                                            variant="outline"
                                            className="h-7 bg-white px-2 text-xs"
                                            onClick={() => { void recordSocialPostAttribution(post, 'click'); }}
                                            disabled={postBusy}
                                          >
                                            {isRu ? 'Клик' : 'Click'}
                                          </Button>
                                          <Button
                                            type="button"
                                            size="sm"
                                            variant="outline"
                                            className="h-7 bg-white px-2 text-xs"
                                            onClick={() => { void recordSocialPostAttribution(post, 'like'); }}
                                            disabled={postBusy}
                                          >
                                            {isRu ? 'Лайк' : 'Like'}
                                          </Button>
                                          <Button
                                            type="button"
                                            size="sm"
                                            variant="outline"
                                            className="h-7 bg-white px-2 text-xs"
                                            onClick={() => { void recordSocialPostAttribution(post, 'view'); }}
                                            disabled={postBusy}
                                          >
                                            {isRu ? 'Просмотр' : 'View'}
                                          </Button>
                                        </div>
                                      </div>
                                    ) : null}
                                  </div>
                                  <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-500">
                                    {Number(post.leads || 0) || Number(post.inquiries || 0) ? (
                                      <span className="font-medium text-emerald-700">
                                        {isRu ? `заявки/обращения: ${Number(post.leads || 0) + Number(post.inquiries || 0)}` : `leads/inquiries: ${Number(post.leads || 0) + Number(post.inquiries || 0)}`}
                                      </span>
                                    ) : null}
                                    {Number(post.comments || 0) || Number(post.shares || 0) || Number(post.clicks || 0) || Number(post.likes || 0) || Number(post.views || 0) || Number(post.reach || 0) ? (
                                      <span>
                                        {isRu
                                          ? `ранние сигналы: комментарии ${Number(post.comments || 0)}, репосты ${Number(post.shares || 0)}, клики ${Number(post.clicks || 0)}, лайки ${Number(post.likes || 0)}, просмотры ${Number(post.views || post.reach || 0)}`
                                          : `early signals: comments ${Number(post.comments || 0)}, shares ${Number(post.shares || 0)}, clicks ${Number(post.clicks || 0)}, likes ${Number(post.likes || 0)}, views ${Number(post.views || post.reach || 0)}`}
                                      </span>
                                    ) : null}
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        ) : (
                          <div className="mt-4 rounded-xl border border-dashed border-slate-200 bg-white px-3 py-3">
                            <div className="text-sm font-semibold text-slate-950">
                              {isRu ? 'Сначала подготовьте варианты по каналам' : 'First prepare channel variants'}
                            </div>
                            <div className="mt-1 text-sm leading-6 text-slate-600">
                              {isRu
                                ? 'LocalOS создаст отдельные черновики для карт и соцсетей. Это безопасный шаг: посты не подтверждаются, не ставятся в расписание и не публикуются.'
                                : 'LocalOS creates separate drafts for maps and social channels. This is a safe step: posts are not approved, queued, or published.'}
                            </div>
                            <div className="mt-3 grid gap-2 text-xs leading-5 text-slate-600 md:grid-cols-3">
                              <div className="rounded-lg bg-slate-50 px-3 py-2">
                                <div className="font-semibold text-slate-950">
                                  1. {isRu ? 'Подготовка' : 'Prepare'}
                                </div>
                                <div>
                                  {isRu
                                    ? 'Создаём тексты под Яндекс, 2ГИС, Google, Telegram, VK и Meta.'
                                    : 'Create copy for Yandex, 2GIS, Google, Telegram, VK, and Meta.'}
                                </div>
                              </div>
                              <div className="rounded-lg bg-slate-50 px-3 py-2">
                                <div className="font-semibold text-slate-950">
                                  2. {isRu ? 'Предпросмотр и подтверждение' : 'Preview and approval'}
                                </div>
                                <div>
                                  {isRu
                                    ? 'Вы проверяете каждый текст и отдельно нажимаете «Подтвердить».'
                                    : 'You review each copy and explicitly click “Approve”.'}
                                </div>
                              </div>
                              <div className="rounded-lg bg-slate-50 px-3 py-2">
                                <div className="font-semibold text-slate-950">
                                  3. {isRu ? 'Расписание' : 'Queue'}
                                </div>
                                <div>
                                  {isRu
                                    ? 'Только после подтверждения можно поставить API-каналы в расписание; карты останутся контролируемыми или ручными.'
                                    : 'Only after approval can API channels be queued; maps remain supervised/manual.'}
                                </div>
                              </div>
                            </div>
                          </div>
                        )}
                      </div>

                      <div className="sticky bottom-3 z-10 mt-5 flex flex-wrap items-center gap-2 rounded-2xl border border-slate-200 bg-white/95 px-3 py-3 shadow-lg backdrop-blur">
                          <Button
                            onClick={() => createNews(item.id)}
                            disabled={busyItemId === item.id || !String(currentDraft || '').trim() || hasNews}
                          >
                            {hasNews
                              ? (isRu ? 'Публикация создана' : 'Publication created')
                              : (isRu ? 'Создать публикацию' : 'Create publication')}
                          </Button>
                          <Button
                            variant="outline"
                            onClick={() => saveItem(item.id)}
                            disabled={busyItemId === item.id}
                          >
                            {isRu ? 'Сохранить' : 'Save'}
                          </Button>
                          {!hasDraft ? (
                            <Button
                              type="button"
                              variant="outline"
                              onClick={() => generateDraft(item.id)}
                              disabled={busyItemId === item.id}
                            >
                              <Sparkles className="mr-2 h-4 w-4" />
                              {isRu ? 'Сгенерировать текст' : 'Generate text'}
                            </Button>
                          ) : null}
                          <details className="relative">
                            <summary className="flex cursor-pointer list-none items-center gap-2 rounded-xl border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">
                              <MoreHorizontal className="h-4 w-4" />
                              {isRu ? 'Ещё' : 'More'}
                            </summary>
                            <div className="absolute bottom-11 right-0 z-20 w-56 rounded-2xl border border-slate-200 bg-white p-2 shadow-xl">
                              <button
                                type="button"
                                onClick={() => generateDraft(item.id)}
                                disabled={busyItemId === item.id}
                                className="block w-full rounded-xl px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                              >
                                {hasDraft ? (isRu ? 'Перегенерировать' : 'Regenerate') : (isRu ? 'Сгенерировать текст' : 'Generate text')}
                              </button>
                              <button
                                type="button"
                                onClick={() => runItemReschedule(item.id, currentDate, 7)}
                                disabled={busyItemId === item.id}
                                className="block w-full rounded-xl px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                              >
                                {isRu ? 'Перенести на 7 дней' : 'Move by 7 days'}
                              </button>
                              <button
                                type="button"
                                onClick={() => runItemDuplicate(item.id)}
                                disabled={busyItemId === item.id}
                                className="block w-full rounded-xl px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                              >
                                {isRu ? 'Дублировать' : 'Duplicate'}
                              </button>
                              {isNetworkMode && availableItemLocations.length > 2 ? (
                                <button
                                  type="button"
                                  onClick={() => openDuplicateTargetPicker(item)}
                                  disabled={busyItemId === item.id || !String(currentDraft || item.usernews_id || '').trim()}
                                  className="block w-full rounded-xl px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                                >
                                  {isRu ? 'Выбрать точки' : 'Choose locations'}
                                </button>
                              ) : null}
                              <button
                                type="button"
                                onClick={() => runItemSkip(item.id)}
                                disabled={busyItemId === item.id}
                                className="block w-full rounded-xl px-3 py-2 text-left text-sm text-slate-500 hover:bg-slate-50 disabled:opacity-50"
                              >
                                {isRu ? 'Пропустить' : 'Skip'}
                              </button>
                              <button
                                type="button"
                                onClick={() => { void deleteItem(item.id); }}
                                disabled={busyItemId === item.id}
                                className="block w-full rounded-xl px-3 py-2 text-left text-sm text-red-700 hover:bg-red-50 disabled:opacity-50"
                              >
                                {isRu ? 'Удалить из плана' : 'Delete from plan'}
                              </button>
                            </div>
                          </details>
                      </div>

                      <div className="mt-5 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                        <button
                          type="button"
                          onClick={() => setShowSelectedItemDetails((prev) => !prev)}
                          className="flex w-full items-center justify-between gap-3 text-left text-sm font-semibold text-slate-900"
                        >
                          <span>{isRu ? 'Почему эта тема и откуда сигнал' : 'Why this topic and signal source'}</span>
                          <span className="text-xs font-medium text-slate-500">
                            {showSelectedItemDetails ? (isRu ? 'Скрыть' : 'Hide') : (isRu ? 'Показать' : 'Show')}
                          </span>
                        </button>
                        {showSelectedItemDetails ? (
                          <div className="mt-3 text-sm leading-6 text-slate-700">
                            <div>{_humanizePlanGoal(item, isRu)}</div>
                            <div className="mt-2 text-xs text-slate-500">
                              <MapPinned className="mr-1 inline h-3.5 w-3.5" />
                              {_sourceKindLabel(item.source_kind, isRu)} {item.source_ref ? `· ${item.source_ref}` : ''}
                              {item.seo_keyword ? ` · SEO: ${item.seo_keyword}` : ''}
                              {_seoViewsLabel(item, isRu) ? ` · ${_seoViewsLabel(item, isRu)}` : ''}
                            </div>
                          </div>
                        ) : null}
                      </div>

                      {expandedDuplicateItemId === item.id ? (
                        <div className="mt-4 rounded-2xl border border-slate-200 bg-white px-4 py-4">
                          <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                            <div>
                              <div className="text-sm font-semibold text-slate-950">
                                {isRu ? 'Дублировать удачную тему на выбранные точки' : 'Duplicate this winning topic to selected locations'}
                              </div>
                              <div className="mt-1 text-sm leading-6 text-slate-600">
                                {isRu
                                  ? 'Выберите только те точки, где эта тема действительно уместна. Черновик и дата будут скопированы.'
                                  : 'Pick only locations where this topic fits. The draft and date will be copied.'}
                              </div>
                            </div>
                            <Input
                              type="date"
                              value={duplicateTargetDate}
                              onChange={(event) => setDuplicateDateOverrides((prev) => ({ ...prev, [item.id]: event.target.value }))}
                              className="h-9 max-w-[180px]"
                              aria-label={isRu ? 'Дата дублирования темы' : 'Duplicate target date'}
                            />
                          </div>
                          <div className="mt-3 flex flex-wrap gap-2">
                            {duplicateTargetOptions.map((location) => (
                              <button
                                key={location.key}
                                type="button"
                                onClick={() => toggleDuplicateTargetLocation(item.id, location.key)}
                                className={[
                                  'rounded-full border px-3 py-1.5 text-sm transition-colors',
                                  selectedDuplicateTargets.includes(location.key)
                                    ? 'border-sky-300 bg-sky-50 text-sky-800'
                                    : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50',
                                ].join(' ')}
                              >
                                {location.label}
                              </button>
                            ))}
                          </div>
                          <div className="mt-4 flex flex-wrap gap-2">
                            <Button
                              type="button"
                              size="sm"
                              onClick={() => { void runItemDuplicateToSelectedLocations(item); }}
                              disabled={busyItemId === item.id || selectedDuplicateTargets.length === 0}
                            >
                              {isRu ? `Дублировать · ${selectedDuplicateTargets.length}` : `Duplicate · ${selectedDuplicateTargets.length}`}
                            </Button>
                            <Button
                              type="button"
                              variant="outline"
                              size="sm"
                              onClick={() => setExpandedDuplicateItemId('')}
                            >
                              {isRu ? 'Отмена' : 'Cancel'}
                            </Button>
                            <Button
                              type="button"
                              variant="ghost"
                              size="sm"
                              onClick={() => { void runItemDuplicateToOtherLocations(item); }}
                              disabled={busyItemId === item.id || duplicateTargetOptions.length === 0}
                            >
                              {isRu ? 'На все остальные' : 'All other locations'}
                            </Button>
                          </div>
                        </div>
                      ) : null}
                      </div>
                    </div>
                  );
                })() : null}
              </div>
            ) : null}
            {visibleItems.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-6 py-8 text-sm text-slate-600">
                <div className="font-semibold text-slate-950">
                  {isRu ? 'В этом виде ничего не найдено' : 'Nothing found in this view'}
                </div>
                <div className="mt-1 leading-6">
                  {queueSearch.trim()
                    ? (isRu
                      ? 'Очистите поиск или нажмите «Сбросить», чтобы снова увидеть всю очередь выбранного плана.'
                      : 'Clear search or reset the view to see the full selected plan queue again.')
                    : (isRu
                      ? 'Для выбранного состояния или периода пока нет публикаций. Нажмите «Сбросить» или выберите другой период.'
                      : 'There are no items for this status or period yet. Reset the view or choose another period.')}
                </div>
              </div>
            ) : null}
          </div>
        ) : (
          <div className="mt-6 rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-6 py-10 text-center text-sm text-slate-600">
            {loading
              ? (isRu ? 'Загружаем контекст и планы...' : 'Loading context and plans...')
              : (isRu ? 'Соберите первый контент-план, чтобы здесь появился календарь публикаций.' : 'Build your first content plan to see planned posts here.')}
          </div>
        )}
      </div>
    </div>
  );
}

function SocialLaunchChecklist({
  stages,
  summary,
  isRu,
  compact = false,
}: {
  stages: SocialLaunchStage[];
  summary: {
    done: number;
    total: number;
    attention: number;
    current?: SocialLaunchStage;
  };
  isRu: boolean;
  compact?: boolean;
}) {
  if (!stages.length) return null;
  const current = summary.current;
  return (
    <div
      data-testid={compact ? 'social-launch-checklist-compact' : 'social-launch-checklist'}
      className="mt-3 rounded-xl bg-white/10 px-3 py-3 text-xs leading-5 text-slate-200"
    >
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="font-semibold text-white">
            {isRu ? 'До рабочего запуска' : 'Before launch'}
          </div>
          <div className="mt-1 text-slate-300">
            {isRu
              ? `Готово ${summary.done} из ${summary.total}. ${summary.attention > 0 ? 'Есть блокер, его нужно снять перед исполнением.' : 'Следующий шаг ниже.'}`
              : `${summary.done} of ${summary.total} ready. ${summary.attention > 0 ? 'A blocker needs attention before execution.' : 'Next step is below.'}`}
          </div>
        </div>
        {current ? (
          <div className="rounded-lg bg-white/10 px-2 py-1.5 text-slate-200 sm:max-w-[260px]">
            <span className="font-semibold text-white">
              {isRu ? 'Сейчас: ' : 'Now: '}
            </span>
            {isRu ? current.labelRu : current.labelEn}
          </div>
        ) : null}
      </div>
      <div className={compact ? 'mt-3 grid gap-1' : 'mt-3 grid gap-1 sm:grid-cols-2'}>
        {stages.map((stage) => {
          const tone = _socialLaunchStageTone(stage.status);
          return (
            <div
              key={`launch-checklist-${compact ? 'compact' : 'full'}-${stage.key}`}
              className="flex items-start gap-2 rounded-lg bg-white/10 px-2 py-2"
            >
              <span className={['mt-1 h-2 w-2 shrink-0 rounded-full', tone.dot].join(' ')} />
              <span className="min-w-0 flex-1">
                <span className="font-semibold text-white">
                  {isRu ? stage.labelRu : stage.labelEn}
                </span>
                {!compact ? (
                  <span className="block text-slate-300">
                    {isRu ? stage.detailRu : stage.detailEn}
                  </span>
                ) : null}
              </span>
              <span className={['shrink-0 rounded-full px-2 py-0.5 text-[11px] font-semibold', tone.badge].join(' ')}>
                {_socialLaunchStageStatusLabel(stage.status, isRu)}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function SocialOwnerLaunchPath({
  isRu,
  currentAction,
}: {
  isRu: boolean;
  currentAction: SocialPlanNextAction;
}) {
  const normalized = String(currentAction || 'none').trim() as SocialPlanNextAction;
  const steps: Array<{
    key: string;
    ru: string;
    en: string;
    actions: SocialPlanNextAction[];
  }> = [
    {
      key: 'prepare',
      ru: 'Подготовить',
      en: 'Prepare',
      actions: ['prepare'],
    },
    {
      key: 'review',
      ru: 'Проверить',
      en: 'Review',
      actions: ['review'],
    },
    {
      key: 'launch',
      ru: 'Расписание',
      en: 'Queue',
      actions: ['queue', 'wait', 'supervised', 'manual'],
    },
    {
      key: 'learn',
      ru: 'Результат',
      en: 'Results',
      actions: ['collect', 'recommend'],
    },
  ];
  const currentIndex = steps.findIndex((step) => step.actions.includes(normalized));
  const activeIndex = currentIndex >= 0 ? currentIndex : 0;

  return (
    <div
      data-testid="social-owner-launch-path"
      className="mt-3 grid gap-1.5 text-xs sm:grid-cols-4"
    >
      {steps.map((step, index) => {
        const isCurrent = index === activeIndex;
        const isDone = normalized !== 'none' && index < activeIndex;
        return (
          <div
            key={`owner-launch-path-${step.key}`}
            className={[
              'flex items-center gap-2 rounded-lg px-2 py-1.5',
              isCurrent
                ? 'bg-white text-slate-950'
                : isDone
                  ? 'bg-emerald-300/15 text-emerald-50'
                  : 'bg-white/10 text-slate-300',
            ].join(' ')}
          >
            <span
              className={[
                'flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold',
                isCurrent
                  ? 'bg-slate-950 text-white'
                  : isDone
                    ? 'bg-emerald-200 text-emerald-900'
                    : 'bg-white/10 text-slate-300',
              ].join(' ')}
            >
              {index + 1}
            </span>
            <span className="min-w-0 truncate font-medium">
              {isRu ? step.ru : step.en}
            </span>
          </div>
        );
      })}
    </div>
  );
}

function _isSupervisedPlatform(platform: string): boolean {
  return platform === 'yandex_maps' || platform === 'two_gis';
}

function _isSocialPostTextLocked(status: string): boolean {
  return ['queued', 'publishing', 'published'].includes(String(status || '').trim());
}

function _socialSupervisedPayload(post: SocialPost) {
  return post.metadata_json?.supervised_publish || null;
}

function _socialOpenClawReadinessDetails(
  readiness: SocialOpenClawReadiness | null,
  isRu: boolean,
): string[] {
  if (!readiness) return [];
  const diagnosticsSource = isRu ? readiness.diagnostics_ru : readiness.diagnostics_en;
  const diagnostics = Array.isArray(diagnosticsSource)
    ? diagnosticsSource.map(String).map((item) => item.trim()).filter(Boolean)
    : [];
  const delivery = readiness.delivery_readiness || {};
  const details = diagnostics.length > 0 ? diagnostics : [
    isRu
      ? 'Безопасная проверка: LocalOS ничего не публикует и только проверяет готовность OpenClaw.'
      : 'Safe check: LocalOS publishes nothing and only checks OpenClaw readiness.',
    readiness.ready
      ? (isRu ? 'Следующий шаг: подготовить контролируемое размещение и проверить предпросмотр.' : 'Next step: prepare supervised placement and review the preview.')
      : (isRu ? 'Следующий шаг: использовать ручной режим или проверить настройки OpenClaw.' : 'Next step: use manual fallback or check OpenClaw settings.'),
  ];
  if (readiness.browser_final_click_allowed === false || readiness.stop_before_final_publish) {
    details.push(
      isRu
        ? 'Финальная публикация остаётся за человеком.'
        : 'Final publishing stays human-controlled.',
    );
  }
  const forbidden = Array.isArray(readiness.forbidden_actions)
    ? readiness.forbidden_actions.map(String).filter(Boolean)
    : [];
  if (forbidden.includes('click_final_publish')) {
    details.push(
      isRu
        ? 'OpenClaw не нажимает финальную кнопку публикации.'
        : 'OpenClaw does not click the final publish button.',
    );
  }
  const suggestedCallback = String(delivery.suggested_callback_url || '').trim();
  const callbackEnvVar = String(delivery.callback_env_var || 'OPENCLAW_SOCIAL_SUPERVISED_CALLBACK_URL').trim();
  const blockedCallbackReason = String(delivery.suggested_callback_blocked_reason || '').trim();
  if (suggestedCallback && !delivery.callback_configured) {
    details.push(
      isRu
        ? `Добавить env: ${callbackEnvVar}=${suggestedCallback}`
        : `Add env: ${callbackEnvVar}=${suggestedCallback}`,
    );
    details.push(
      isRu
        ? 'Стандартный адрес обратной связи OpenClaw: /m2m/localos/callbacks'
        : 'Standard OpenClaw receiver: /m2m/localos/callbacks',
    );
  }
  if (!suggestedCallback && blockedCallbackReason === 'sandbox_bridge_private_host') {
    details.push(
      isRu
        ? 'Текущий тестовый bridge не подходит для рабочего callback; нужен доступный адрес OpenClaw.'
        : 'The current sandbox bridge is not suitable for the production callback; use a reachable OpenClaw receiver.',
    );
  }
  if (delivery.outbox_available === true) {
    details.push(isRu ? 'Outbox для доставки task найден.' : 'Task delivery outbox is available.');
  }
  return Array.from(new Set(details)).slice(0, 6);
}

function _socialLaunchStageStatusLabel(status: SocialLaunchStage['status'], isRu: boolean): string {
  if (status === 'done') return isRu ? 'готово' : 'done';
  if (status === 'current') return isRu ? 'сейчас' : 'now';
  if (status === 'attention') return isRu ? 'внимание' : 'attention';
  return isRu ? 'позже' : 'later';
}

function _normalizeSocialGoalStage(stage: SocialGoalStage): SocialLaunchStage | null {
  const key = String(stage?.key || '').trim();
  const labelRu = String(stage?.labelRu || stage?.label_ru || '').trim();
  const labelEn = String(stage?.labelEn || stage?.label_en || '').trim();
  const detailRu = String(stage?.detailRu || stage?.detail_ru || '').trim();
  const detailEn = String(stage?.detailEn || stage?.detail_en || '').trim();
  const status = _normalizeSocialGoalStageStatus(stage?.status);
  if (!key || !labelRu || !labelEn) return null;
  return {
    key,
    labelRu,
    labelEn,
    status,
    detailRu,
    detailEn,
    count: Number(stage?.count || 0),
  };
}

function _normalizeSocialGoalStageStatus(status: SocialGoalStage['status']): SocialLaunchStage['status'] {
  const normalized = String(status || '').trim();
  if (normalized === 'done' || normalized === 'current' || normalized === 'attention' || normalized === 'pending') {
    return normalized;
  }
  return 'pending';
}

function _socialLaunchStageTone(status: SocialLaunchStage['status']): { dot: string; badge: string } {
  if (status === 'done') return { dot: 'bg-emerald-300', badge: 'bg-emerald-100 text-emerald-800' };
  if (status === 'current') return { dot: 'bg-sky-300', badge: 'bg-sky-100 text-sky-800' };
  if (status === 'attention') return { dot: 'bg-red-300', badge: 'bg-red-100 text-red-800' };
  return { dot: 'bg-slate-400', badge: 'bg-slate-100 text-slate-600' };
}

function _socialOpenClawReadinessOperational(readiness: SocialOpenClawReadiness): boolean {
  if (typeof readiness.handoff_ready === 'boolean') return readiness.handoff_ready;
  if (readiness.delivery_readiness && typeof readiness.delivery_readiness.ready === 'boolean') {
    return Boolean(readiness.ready) && Boolean(readiness.delivery_readiness.ready);
  }
  return Boolean(readiness.ready);
}

function _socialOpenClawReadinessTitle(readiness: SocialOpenClawReadiness, isRu: boolean): string {
  if (_socialOpenClawReadinessOperational(readiness)) {
    return isRu ? 'OpenClaw browser-use готов' : 'OpenClaw browser-use ready';
  }
  if (readiness.ready && readiness.delivery_readiness && !readiness.delivery_readiness.ready) {
    return isRu ? 'Доставка OpenClaw task не готова' : 'OpenClaw task delivery is not ready';
  }
  return isRu ? 'OpenClaw browser-use не подтверждён' : 'OpenClaw browser-use not confirmed';
}

function _socialOpenClawOwnerCheckSummary(readiness: SocialOpenClawReadiness, isRu: boolean): string {
  const hasActionRef = Boolean(String(readiness.action_ref || '').trim());
  if (_socialOpenClawReadinessOperational(readiness)) {
    return hasActionRef
      ? (isRu
        ? 'Проверка OpenClaw пройдена: можно создать контролируемую задачу, финальная публикация остаётся за человеком.'
        : 'OpenClaw check passed: LocalOS can create a controlled task, and final publishing stays human-controlled.')
      : (isRu
        ? 'Проверка OpenClaw пройдена: можно готовить контролируемое размещение, финальная публикация остаётся за человеком.'
        : 'OpenClaw check passed: supervised placement can be prepared, and final publishing stays human-controlled.');
  }
  if (readiness.ready && readiness.delivery_readiness && !readiness.delivery_readiness.ready) {
    return isRu
      ? 'OpenClaw browser-use найден, но доставка задачи не готова: LocalOS сохранит ручной режим.'
      : 'OpenClaw browser-use is available, but callback/outbox delivery is not ready: LocalOS keeps manual fallback.';
  }
  if (readiness.provider_status === 'missing_catalog' || readiness.reason === 'openclaw_catalog_not_configured') {
    return isRu
      ? 'OpenClaw пока не подключён к этому экрану: LocalOS сохранит ручное размещение и не сорвёт план.'
      : 'OpenClaw is not connected to this screen yet: LocalOS keeps manual placement and will not block the plan.';
  }
  if (readiness.provider_status === 'error' || readiness.reason === 'openclaw_catalog_error') {
    return isRu
      ? 'LocalOS не смог проверить OpenClaw: используйте ручное размещение, пока доступ не восстановлен.'
      : 'LocalOS could not verify OpenClaw: use manual placement until access is restored.';
  }
  return isRu
    ? 'OpenClaw не подтверждён: для Яндекс/2ГИС будет показан ручной или контролируемый режим.'
    : 'OpenClaw is not confirmed: Yandex/2GIS will use manual or supervised fallback.';
}

function _socialOpenClawCapabilityLine(
  status: string | SocialOpenClawCapabilityStatus | undefined,
  isRu: boolean,
): string {
  if (!status) return '';
  if (typeof status === 'string') {
    return status.trim() ? `OpenClaw browser-use: ${status.trim()}` : '';
  }
  const state = status.ready
    ? (isRu ? 'готов' : 'ready')
    : (isRu ? 'недоступен' : 'unavailable');
  const details = [
    status.status,
    status.source,
    status.reason,
    status.action_ref,
    status.error,
  ].map((item) => String(item || '').trim()).filter(Boolean);
  return `OpenClaw browser-use: ${state}${details.length ? ` · ${details.join(' · ')}` : ''}`;
}

function _socialSupervisedHandoffStateLabel(state: string, isRu: boolean): string {
  const normalized = String(state || '').trim();
  if (normalized === 'ready_for_openclaw_handoff') {
    return isRu ? 'готово к OpenClaw' : 'ready for OpenClaw';
  }
  if (normalized === 'manual_fallback_required') {
    return isRu ? 'нужно вручную' : 'manual fallback';
  }
  return normalized;
}

function _socialApiQueueWarnings(
  posts: SocialPost[],
  preflightByPlatform: Record<string, SocialApiChannelPreflight>,
  readinessByPlatform: Record<string, SocialChannelReadiness>,
  isRu: boolean,
): Array<{ postId: string; platform: string; label: string; status: string }> {
  const warnings: Array<{ postId: string; platform: string; label: string; status: string }> = [];
  for (const post of posts) {
    if (String(post.publish_mode || '').trim() !== 'api') continue;
    const platform = String(post.platform || '').trim();
    const preflight = preflightByPlatform[platform];
    const readiness = readinessByPlatform[platform];
    if (preflight && Boolean(preflight.ready)) continue;
    if (!preflight && (!readiness || Boolean(readiness.ready))) continue;
    warnings.push({
      postId: post.id,
      platform,
      label: String(preflight?.platform_label || readiness?.platform_label || post.platform_label || _socialPlatformLabel(platform, isRu)),
      status: String(preflight?.status || readiness?.status || (isRu ? 'нужно внимание' : 'needs attention')),
    });
  }
  return warnings;
}

function _socialApprovalPostText(post: SocialPost): string {
  return String(post.platform_text || post.base_text || '').trim();
}

function _socialApprovalSummary(
  posts: SocialPost[],
  preflightByPlatform: Record<string, SocialApiChannelPreflight>,
  readinessByPlatform: Record<string, SocialChannelReadiness>,
  isRu: boolean,
): SocialApprovalPreviewSummary {
  let api = 0;
  let supervised = 0;
  let emptyText = 0;
  const labels: string[] = [];
  const seenLabels = new Set<string>();
  for (const post of posts) {
    if (_isSupervisedPlatform(String(post.platform || ''))) {
      supervised += 1;
    } else {
      api += 1;
    }
    if (!_socialApprovalPostText(post)) {
      emptyText += 1;
    }
    const label = String(post.platform_label || _socialPlatformLabel(String(post.platform || ''), isRu));
    if (label && !seenLabels.has(label)) {
      seenLabels.add(label);
      labels.push(label);
    }
  }
  return {
    total: posts.length,
    api,
    supervised,
    emptyText,
    blockedApiWarnings: _socialApiQueueWarnings(posts, preflightByPlatform, readinessByPlatform, isRu),
    platformLabels: labels,
  };
}

function _socialQueueSummary(
  posts: SocialPost[],
  preflightByPlatform: Record<string, SocialApiChannelPreflight>,
  readinessByPlatform: Record<string, SocialChannelReadiness>,
  isRu: boolean,
): SocialQueuePreviewSummary {
  let api = 0;
  let supervised = 0;
  let dueNow = 0;
  let firstScheduledFor = '';
  const labels: string[] = [];
  const seenLabels = new Set<string>();
  const nowMs = Date.now();
  for (const post of posts) {
    if (_isSupervisedPlatform(String(post.platform || ''))) {
      supervised += 1;
    } else {
      api += 1;
    }
    const scheduledFor = String(post.scheduled_for || '').trim();
    if (scheduledFor) {
      if (!firstScheduledFor || scheduledFor < firstScheduledFor) {
        firstScheduledFor = scheduledFor;
      }
      const scheduledMs = Date.parse(scheduledFor);
      if (Number.isFinite(scheduledMs) && scheduledMs <= nowMs) {
        dueNow += 1;
      }
    }
    const label = String(post.platform_label || _socialPlatformLabel(String(post.platform || ''), isRu));
    if (label && !seenLabels.has(label)) {
      seenLabels.add(label);
      labels.push(label);
    }
  }
  return {
    total: posts.length,
    api,
    supervised,
    dueNow,
    blockedApiWarnings: _socialApiQueueWarnings(posts, preflightByPlatform, readinessByPlatform, isRu),
    platformLabels: labels,
    firstScheduledFor,
  };
}

function _socialSupervisedSafetySummary(
  contract: SocialSupervisedSafetyContract | undefined,
  isRu: boolean,
): { allowed: string[]; forbidden: string[]; fallback: string[] } {
  const allowedSource = Array.isArray(contract?.allowed_actions) && contract.allowed_actions.length
    ? contract.allowed_actions
    : ['open_platform', 'fill_text', 'attach_media', 'show_preview'];
  const forbiddenSource = Array.isArray(contract?.forbidden_actions) && contract.forbidden_actions.length
    ? contract.forbidden_actions
    : ['click_final_publish', 'publish_without_human_confirmation'];
  const fallbackSource = Array.isArray(contract?.manual_fallback_triggers) && contract.manual_fallback_triggers.length
    ? contract.manual_fallback_triggers
    : ['captcha', 'login_required', 'changed_ui'];
  return {
    allowed: allowedSource.map((item) => _socialSupervisedSafetyActionLabel(item, isRu)).filter(Boolean).slice(0, 4),
    forbidden: forbiddenSource.map((item) => _socialSupervisedSafetyActionLabel(item, isRu)).filter(Boolean).slice(0, 4),
    fallback: fallbackSource.map((item) => _socialSupervisedSafetyActionLabel(item, isRu)).filter(Boolean).slice(0, 4),
  };
}

function _socialSupervisedSafetyActionLabel(action: string, isRu: boolean): string {
  const normalized = String(action || '').trim();
  if (normalized === 'open_platform') return isRu ? 'откроет площадку' : 'open the platform';
  if (normalized === 'fill_text') return isRu ? 'вставит текст' : 'fill the text';
  if (normalized === 'attach_media') return isRu ? 'добавит медиа' : 'attach media';
  if (normalized === 'show_preview') return isRu ? 'покажет предпросмотр' : 'show preview';
  if (normalized === 'return_task_status') return isRu ? 'вернёт статус задачи' : 'return task status';
  if (normalized === 'click_final_publish') return isRu ? 'не нажмёт финальную публикацию' : 'not click final publish';
  if (normalized === 'bypass_login') return isRu ? 'не обойдёт авторизацию' : 'not bypass login';
  if (normalized === 'solve_captcha_without_user') return isRu ? 'не решит капчу без вас' : 'not solve captcha without you';
  if (normalized === 'change_business_profile_data') return isRu ? 'не изменит карточку бизнеса' : 'not change business profile data';
  if (normalized === 'publish_without_human_confirmation') return isRu ? 'не опубликует без подтверждения' : 'not publish without confirmation';
  if (normalized === 'captcha') return isRu ? 'капча' : 'captcha';
  if (normalized === 'login_required') return isRu ? 'нужен вход' : 'login required';
  if (normalized === 'changed_ui') return isRu ? 'изменился интерфейс' : 'changed UI';
  if (normalized === 'missing_target_url') return isRu ? 'нет ссылки на профиль' : 'missing profile link';
  if (normalized === 'browser_capability_unavailable') return isRu ? 'browser-use недоступен' : 'browser-use unavailable';
  if (normalized === 'unexpected_external_prompt') return isRu ? 'внешний запрос подтверждения' : 'unexpected external prompt';
  return normalized.replace(/_/g, ' ');
}

function _normalizeSocialChannelFilter(value: string): 'all' | 'social' | 'maps' {
  if (value === 'social') return 'social';
  if (value === 'maps') return 'maps';
  return 'all';
}

function _socialChannelFilterLabel(value: string, isRu: boolean): string {
  if (value === 'social') return isRu ? 'Только соцсети' : 'Social only';
  if (value === 'maps') return isRu ? 'Только карты' : 'Maps only';
  return isRu ? 'Все каналы' : 'All channels';
}

function _matchesChannelFilter(
  item: PlanItem,
  postsByItem: Record<string, SocialPost[]>,
  filterKey: 'all' | 'social' | 'maps',
): boolean {
  if (filterKey === 'all') return true;
  const posts = postsByItem[item.id] || [];
  if (!posts.length) return true;
  if (filterKey === 'maps') return posts.some((post) => _isSupervisedPlatform(post.platform) || post.platform === 'google_business');
  return posts.some((post) => !_isSupervisedPlatform(post.platform) && post.platform !== 'google_business');
}

function _socialPlatformLabel(platform: string, isRu: boolean): string {
  const normalized = String(platform || '').trim();
  if (normalized === 'yandex_maps') return isRu ? 'Яндекс Карты' : 'Yandex Maps';
  if (normalized === 'two_gis') return '2ГИС';
  if (normalized === 'google_business') return 'Google Business';
  if (normalized === 'telegram') return 'Telegram';
  if (normalized === 'vk') return 'VK';
  if (normalized === 'instagram') return 'Instagram';
  if (normalized === 'facebook') return 'Facebook';
  return normalized || (isRu ? 'Канал' : 'Channel');
}

function _socialMetricsSourceText(platform: string, isRu: boolean): string {
  const normalized = String(platform || '').trim();
  if (normalized === 'vk') {
    return isRu
      ? 'API-снимок: просмотры, лайки, комментарии и репосты; заявки/обращения можно отметить вручную.'
      : 'API snapshot: views, likes, comments, and shares; leads/inquiries can be marked manually.';
  }
  if (normalized === 'telegram') {
    return isRu
      ? 'Результат учитывается через ручные отметки заявок/обращений; Bot API не даёт полный срез реакций для обычного sendMessage.'
      : 'Results use manual lead/inquiry marking; Bot API does not expose a full reaction snapshot for ordinary sendMessage posts.';
  }
  if (normalized === 'yandex_maps' || normalized === 'two_gis') {
    return isRu
      ? 'После контролируемого или ручного размещения отметьте публикацию и заявки вручную; LocalOS не подставляет недоступные API-метрики.'
      : 'After supervised/manual placement, mark publishing and leads manually; LocalOS does not invent unavailable API metrics.';
  }
  if (normalized === 'google_business') {
    return isRu
      ? 'Метрики собираются через Google boundary там, где есть разрешения; иначе используйте ручные заявки/обращения.'
      : 'Metrics are collected through the Google boundary where permissions allow; otherwise use manual leads/inquiries.';
  }
  if (normalized === 'instagram' || normalized === 'facebook') {
    return isRu
      ? 'Meta-метрики появятся после permissions и business/page binding; до этого результат отмечается вручную.'
      : 'Meta metrics appear after permissions and business/page binding; until then, mark results manually.';
  }
  return isRu
    ? 'Результат учитывается по доступным API-метрикам и ручным отметкам заявок/обращений.'
    : 'Results use available API metrics and manual lead/inquiry marks.';
}

function _socialSettingsPathForPlatform(platform: string): string {
  const normalized = String(platform || '').trim();
  if (normalized === 'telegram') return '/dashboard/settings?focus=telegram';
  if (normalized === 'vk') return '/dashboard/settings?focus=vk';
  if (normalized === 'google_business') return '/dashboard/settings?focus=google_business';
  if (normalized === 'instagram' || normalized === 'facebook') return `/dashboard/settings?focus=${normalized}`;
  if (normalized === 'yandex_maps' || normalized === 'two_gis') return '/dashboard/card?tab=news&mode=plan';
  return '/dashboard/settings?focus=integrations';
}

function _socialChannelSetupSort(left: SocialChannelReadiness, right: SocialChannelReadiness): number {
  const priority = ['telegram', 'vk', 'google_business', 'instagram', 'facebook', 'yandex_maps', 'two_gis'];
  const leftPlatform = String(left.platform || '').trim();
  const rightPlatform = String(right.platform || '').trim();
  const leftIndex = priority.indexOf(leftPlatform);
  const rightIndex = priority.indexOf(rightPlatform);
  const leftRank = leftIndex >= 0 ? leftIndex : priority.length;
  const rightRank = rightIndex >= 0 ? rightIndex : priority.length;
  if (leftRank !== rightRank) return leftRank - rightRank;
  return String(left.platform_label || leftPlatform).localeCompare(String(right.platform_label || rightPlatform));
}

function _socialChannelConnectionStateLabel(channel: SocialChannelReadiness, isRu: boolean): string {
  if (Boolean(channel.ready)) return isRu ? 'готово' : 'ready';
  const status = String(channel.status || '').trim();
  if (status.includes('permission') || status.includes('blocked')) return isRu ? 'нужны права' : 'permissions';
  if ((channel.missing_fields || []).length > 0) return isRu ? 'нужны ключи' : 'keys needed';
  return isRu ? 'нужно подключить' : 'setup needed';
}

function _socialWorkerEnvLines(
  dispatchEnv: Record<string, string>,
  metricsEnv: Record<string, string>,
): string[] {
  const lines: string[] = [];
  for (const key of [
    'SOCIAL_POST_DISPATCH_ENABLED',
    'SOCIAL_POST_DISPATCH_INTERVAL_SEC',
    'SOCIAL_POST_DISPATCH_BATCH_SIZE',
    'SOCIAL_POST_DISPATCH_BUSINESS_ID',
  ]) {
    const value = String(dispatchEnv[key] || '').trim();
    if (value) lines.push(`${key}=${value}`);
  }
  for (const key of [
    'SOCIAL_POST_METRICS_ENABLED',
    'SOCIAL_POST_METRICS_INTERVAL_SEC',
    'SOCIAL_POST_METRICS_BATCH_SIZE',
    'SOCIAL_POST_METRICS_BUSINESS_ID',
  ]) {
    const value = String(metricsEnv[key] || '').trim();
    if (value) lines.push(`${key}=${value}`);
  }
  return lines;
}

function _socialLaunchRunbookBlock(runbook: SocialLaunchRunbook | undefined, isRu: boolean) {
  const steps = Array.isArray(isRu ? runbook?.steps_ru : runbook?.steps_en)
    ? (isRu ? runbook?.steps_ru : runbook?.steps_en) || []
    : [];
  const criteria = Array.isArray(isRu ? runbook?.success_criteria_ru : runbook?.success_criteria_en)
    ? (isRu ? runbook?.success_criteria_ru : runbook?.success_criteria_en) || []
    : [];
  const title = isRu ? String(runbook?.title_ru || '') : String(runbook?.title_en || '');
  const summary = isRu ? String(runbook?.summary_ru || '') : String(runbook?.summary_en || '');
  const blockedReason = isRu ? String(runbook?.blocked_reason_ru || '') : String(runbook?.blocked_reason_en || '');
  if (!title && !summary && !steps.length && !criteria.length && !blockedReason) return null;
  return (
    <div className="mt-2 rounded-lg border border-emerald-300/20 bg-emerald-400/10 px-2 py-2 text-[11px] leading-5 text-emerald-50">
      <div className="flex items-center justify-between gap-2">
        <span className="font-semibold text-white">
          {title || (isRu ? 'Runbook первого цикла' : 'First-cycle runbook')}
        </span>
        <span className={runbook?.ready ? 'rounded-full bg-emerald-300/20 px-2 py-0.5 text-[10px] font-semibold text-emerald-50' : 'rounded-full bg-amber-300/20 px-2 py-0.5 text-[10px] font-semibold text-amber-50'}>
          {runbook?.ready ? (isRu ? 'готов' : 'ready') : (isRu ? 'не готов' : 'not ready')}
        </span>
      </div>
      {summary ? (
        <div className="mt-1 text-emerald-100">{summary}</div>
      ) : null}
      {blockedReason ? (
        <div className="mt-1 rounded-md bg-amber-400/10 px-2 py-1 text-amber-100">
          {blockedReason}
        </div>
      ) : null}
      {steps.length > 0 ? (
        <div className="mt-2 space-y-1">
          <div className="font-semibold text-white">{isRu ? 'Шаги' : 'Steps'}</div>
          {steps.slice(0, 6).map((step, index) => (
            <div key={`${index}-${String(step)}`} className="flex gap-1.5 rounded-md bg-white/10 px-2 py-1">
              <span className="shrink-0 font-semibold text-white">{index + 1}.</span>
              <span>{String(step)}</span>
            </div>
          ))}
        </div>
      ) : null}
      {criteria.length > 0 ? (
        <div className="mt-2 space-y-1">
          <div className="font-semibold text-white">{isRu ? 'Успех первого цикла' : 'First-cycle success'}</div>
          {criteria.slice(0, 5).map((item) => (
            <div key={String(item)} className="rounded-md bg-white/10 px-2 py-1">
              {String(item)}
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function _socialLaunchRunbookClipboardLines(runbook: SocialLaunchRunbook | undefined, isRu: boolean): string[] {
  const steps = Array.isArray(isRu ? runbook?.steps_ru : runbook?.steps_en)
    ? (isRu ? runbook?.steps_ru : runbook?.steps_en) || []
    : [];
  const criteria = Array.isArray(isRu ? runbook?.success_criteria_ru : runbook?.success_criteria_en)
    ? (isRu ? runbook?.success_criteria_ru : runbook?.success_criteria_en) || []
    : [];
  const blockedReason = isRu ? String(runbook?.blocked_reason_ru || '') : String(runbook?.blocked_reason_en || '');
  const lines: string[] = [];
  if (steps.length || criteria.length || blockedReason) {
    lines.push('', isRu ? '# Runbook первого цикла dispatch' : '# First-cycle dispatch runbook');
  }
  if (blockedReason) lines.push(`${isRu ? 'Blocked' : 'Blocked'}: ${blockedReason}`);
  steps.forEach((step, index) => {
    lines.push(`${index + 1}. ${String(step)}`);
  });
  if (criteria.length) {
    lines.push(isRu ? 'Критерии успеха:' : 'Success criteria:');
    criteria.forEach((item) => {
      lines.push(`- ${String(item)}`);
    });
  }
  return lines;
}

function _socialFirstCycleVerificationBlock(
  verification: SocialFirstCycleVerification | undefined,
  isRu: boolean,
) {
  const expected = Array.isArray(verification?.expected_statuses)
    ? verification.expected_statuses.filter(Boolean)
    : [];
  const checks = Array.isArray(isRu ? verification?.checks_ru : verification?.checks_en)
    ? (isRu ? verification?.checks_ru : verification?.checks_en) || []
    : [];
  const logFilter = String(verification?.log_filter || '').trim();
  if (!expected.length && !checks.length && !logFilter) return null;
  return (
    <div className="mt-2 rounded-lg border border-violet-300/20 bg-violet-400/10 px-2 py-2 text-[11px] leading-5 text-violet-50">
      <div className="font-semibold text-white">
        {isRu ? 'Проверка после первого цикла' : 'First-cycle verification'}
      </div>
      {logFilter ? (
        <div className="mt-1 font-mono text-[10px] text-violet-100">
          logs: {logFilter}
        </div>
      ) : null}
      {expected.length > 0 ? (
        <div className="mt-1 space-y-1">
          {expected.slice(0, 4).map((item) => (
            <div key={String(item.key || item.label_ru || item.label_en)} className="rounded-md bg-white/10 px-2 py-1">
              <span className="font-medium text-white">
                {isRu ? String(item.label_ru || '') : String(item.label_en || '')}
              </span>
              <span className="text-violet-100">
                {' '}
                - {isRu ? String(item.expected_ru || '') : String(item.expected_en || '')}
              </span>
            </div>
          ))}
        </div>
      ) : null}
      {checks.length > 0 ? (
        <div className="mt-1 space-y-0.5 text-violet-100">
          {checks.slice(0, 4).map((check) => (
            <div key={String(check)}>{String(check)}</div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

async function copyTextToClipboard(value: string): Promise<void> {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(value);
    return;
  }
  const textarea = document.createElement('textarea');
  textarea.value = value;
  textarea.setAttribute('readonly', 'true');
  textarea.style.position = 'fixed';
  textarea.style.left = '-9999px';
  document.body.appendChild(textarea);
  textarea.select();
  document.execCommand('copy');
  document.body.removeChild(textarea);
}

function _socialPublishModeLabel(mode: string, isRu: boolean): string {
  const normalized = String(mode || '').trim();
  if (normalized === 'api') return isRu ? 'API после подтверждения' : 'API after approval';
  if (normalized === 'openclaw_browser') return isRu ? 'Контролируемый браузер OpenClaw' : 'Supervised OpenClaw browser-use';
  if (normalized === 'local_supervised_browser') return isRu ? 'Локальный контролируемый браузер' : 'Local supervised browser';
  if (normalized === 'manual') return isRu ? 'Ручное размещение' : 'Manual fallback';
  return isRu ? 'Режим не задан' : 'Mode not set';
}

function _socialStatusLabel(status: string, isRu: boolean): string {
  const normalized = String(status || '').trim();
  if (normalized === 'draft') return isRu ? 'Черновик' : 'Draft';
  if (normalized === 'needs_review') return isRu ? 'Нужно проверить' : 'Needs review';
  if (normalized === 'approved') return isRu ? 'Подтверждено' : 'Approved';
  if (normalized === 'queued') return isRu ? 'В расписании' : 'Queued';
  if (normalized === 'publishing') return isRu ? 'Публикуется' : 'Publishing';
  if (normalized === 'published') return isRu ? 'Опубликовано' : 'Published';
  if (normalized === 'failed') return isRu ? 'Ошибка' : 'Failed';
  if (normalized === 'needs_manual_publish') return isRu ? 'Нужно вручную' : 'Manual needed';
  if (normalized === 'needs_supervised_publish') return isRu ? 'Контролируемое размещение' : 'Supervised placement';
  return isRu ? 'Статус неизвестен' : 'Unknown status';
}

function _socialStatusClassName(status: string): string {
  const normalized = String(status || '').trim();
  const base = 'rounded-full px-3 py-1 text-xs font-medium';
  if (normalized === 'published') return `${base} bg-emerald-50 text-emerald-800`;
  if (normalized === 'failed') return `${base} bg-red-50 text-red-800`;
  if (normalized === 'needs_supervised_publish' || normalized === 'needs_manual_publish') return `${base} bg-amber-50 text-amber-800`;
  if (normalized === 'approved' || normalized === 'queued' || normalized === 'publishing') return `${base} bg-blue-50 text-blue-800`;
  return `${base} bg-slate-100 text-slate-700`;
}

function _socialPublishEvidenceClassName(tone: string): string {
  const normalized = String(tone || '').trim();
  const base = 'mt-3 rounded-xl border px-3 py-2 text-xs leading-5';
  if (normalized === 'success') return `${base} border-emerald-200 bg-emerald-50 text-emerald-800`;
  if (normalized === 'danger') return `${base} border-red-200 bg-red-50 text-red-700`;
  if (normalized === 'warning') return `${base} border-amber-200 bg-amber-50 text-amber-800`;
  if (normalized === 'info') return `${base} border-blue-100 bg-blue-50 text-blue-800`;
  return `${base} border-slate-200 bg-slate-50 text-slate-700`;
}

function _socialProofQualityLabel(value: string, isRu: boolean): string {
  const normalized = String(value || '').trim();
  if (normalized === 'url') return isRu ? 'ссылка' : 'URL';
  if (normalized === 'provider_id') return 'provider ID';
  if (normalized === 'published_without_provider_ref') return isRu ? 'без ссылки/ID' : 'no URL/ID';
  if (normalized === 'supervised_task') return isRu ? 'контролируемая задача' : 'supervised task';
  if (normalized === 'error') return isRu ? 'ошибка' : 'error';
  if (normalized === 'pending') return isRu ? 'ожидает результата' : 'pending';
  return normalized || (isRu ? 'неизвестно' : 'unknown');
}

function _socialLearningReadinessClassName(confidence: string): string {
  const normalized = String(confidence || '').trim();
  const base = 'mt-3 rounded-lg border px-3 py-2';
  if (normalized === 'high') return `${base} border-emerald-100 bg-white text-emerald-900`;
  if (normalized === 'medium') return `${base} border-lime-100 bg-white text-lime-900`;
  if (normalized === 'low') return `${base} border-amber-100 bg-white text-amber-900`;
  return `${base} border-slate-200 bg-white text-slate-700`;
}

function _socialLearningConfidenceLabel(confidence: string, isRu: boolean): string {
  const normalized = String(confidence || '').trim();
  if (normalized === 'high') return isRu ? 'доверие высокое' : 'high confidence';
  if (normalized === 'medium') return isRu ? 'среднее доверие' : 'medium confidence';
  if (normalized === 'low') return isRu ? 'данных мало' : 'low data';
  return isRu ? 'ждём факты' : 'waiting for facts';
}

function _socialLearningChecklistStatusLabel(status: string, isRu: boolean): string {
  const normalized = String(status || '').trim();
  if (normalized === 'done') return isRu ? 'готово' : 'done';
  if (normalized === 'current') return isRu ? 'сейчас' : 'now';
  if (normalized === 'attention') return isRu ? 'внимание' : 'attention';
  return isRu ? 'позже' : 'later';
}

function _socialNextActionLabel(action: string, isRu: boolean): string {
  const normalized = String(action || '').trim();
  if (normalized === 'review_required') return isRu ? 'следующий шаг: проверить текст' : 'next: review text';
  if (normalized === 'start_supervised_publish') return isRu ? 'следующий шаг: открыть контролируемое размещение' : 'next: open supervised placement';
  if (normalized === 'wait_for_api_publish') return isRu ? 'следующий шаг: поставить в расписание' : 'next: queue on schedule';
  if (normalized === 'wait_for_scheduled_publish') return isRu ? 'ждёт даты публикации' : 'waiting for scheduled publish';
  if (normalized === 'wait_for_scheduled_supervised_publish') return isRu ? 'ждёт даты контролируемого размещения' : 'waiting for scheduled supervised placement';
  if (normalized === 'open_supervised_publish') return isRu ? 'следующий шаг: завершить контролируемое размещение' : 'next: finish supervised placement';
  if (normalized === 'manual_publish') return isRu ? 'следующий шаг: разместить вручную' : 'next: publish manually';
  if (normalized === 'retry_or_manual') return isRu ? 'следующий шаг: повторить или вручную' : 'next: retry or manual';
  if (normalized === 'collect_metrics') return isRu ? 'следующий шаг: собрать реакции' : 'next: collect reactions';
  return isRu ? 'следующий шаг не требуется' : 'no next action';
}

function _socialItemQueueSummary(posts: SocialPost[], isRu: boolean): {
  label: string;
  detail: string;
  totalLabel: string;
  className: string;
} {
  const counts = posts.reduce((acc, post) => {
    const status = String(post.status || '').trim();
    if (status === 'draft' || status === 'needs_review') acc.review += 1;
    else if (status === 'approved') acc.approved += 1;
    else if (status === 'queued' || status === 'publishing') acc.queued += 1;
    else if (status === 'needs_supervised_publish') acc.supervised += 1;
    else if (status === 'needs_manual_publish') acc.manual += 1;
    else if (status === 'failed') acc.failed += 1;
    else if (status === 'published') acc.published += 1;
    if (_isSupervisedPlatform(String(post.platform || ''))) acc.maps += 1;
    else acc.api += 1;
    return acc;
  }, {
    review: 0,
    approved: 0,
    queued: 0,
    supervised: 0,
    manual: 0,
    failed: 0,
    published: 0,
    api: 0,
    maps: 0,
  });
  const total = posts.length;
  const base = 'rounded-full px-2.5 py-1 text-[11px] font-semibold';
  let label = isRu ? 'Каналы готовы' : 'Channels ready';
  let className = `${base} bg-slate-100 text-slate-700`;

  if (counts.review > 0) {
    label = isRu ? `Проверить тексты: ${counts.review}` : `Review copy: ${counts.review}`;
    className = `${base} bg-sky-100 text-sky-800`;
  } else if (counts.approved > 0) {
    label = isRu ? `Можно в расписание: ${counts.approved}` : `Ready to queue: ${counts.approved}`;
    className = `${base} bg-blue-100 text-blue-800`;
  } else if (counts.failed > 0 || counts.manual > 0) {
    const attention = counts.failed + counts.manual;
    label = isRu ? `Нужно внимание: ${attention}` : `Needs attention: ${attention}`;
    className = `${base} bg-red-100 text-red-700`;
  } else if (counts.supervised > 0) {
    label = isRu ? `Контролируемое размещение: ${counts.supervised}` : `Supervised placement: ${counts.supervised}`;
    className = `${base} bg-amber-100 text-amber-800`;
  } else if (counts.queued > 0) {
    label = isRu ? `В расписании: ${counts.queued}` : `Queued: ${counts.queued}`;
    className = `${base} bg-blue-100 text-blue-800`;
  } else if (counts.published > 0) {
    label = isRu ? `Опубликовано: ${counts.published}` : `Published: ${counts.published}`;
    className = `${base} bg-emerald-100 text-emerald-800`;
  }

  const detailParts = [
    isRu ? `API ${counts.api}` : `API ${counts.api}`,
    isRu ? `карты ${counts.maps}` : `maps ${counts.maps}`,
  ];
  if (counts.review > 0) detailParts.push(isRu ? `проверка ${counts.review}` : `review ${counts.review}`);
  if (counts.approved > 0) detailParts.push(isRu ? `утверждено ${counts.approved}` : `approved ${counts.approved}`);
  if (counts.queued > 0) detailParts.push(isRu ? `расписание ${counts.queued}` : `queued ${counts.queued}`);
  if (counts.supervised > 0) detailParts.push(isRu ? `контролируемо ${counts.supervised}` : `supervised ${counts.supervised}`);
  if (counts.manual > 0) detailParts.push(isRu ? `вручную ${counts.manual}` : `manual ${counts.manual}`);
  if (counts.failed > 0) detailParts.push(isRu ? `ошибки ${counts.failed}` : `failed ${counts.failed}`);
  if (counts.published > 0) detailParts.push(isRu ? `вышло ${counts.published}` : `published ${counts.published}`);

  return {
    label,
    className,
    detail: detailParts.join(' · '),
    totalLabel: isRu ? `каналов: ${total}` : `channels: ${total}`,
  };
}

function _socialDispatchActionLabel(action: string, isRu: boolean): string {
  const normalized = String(action || '').trim();
  if (normalized === 'publish_api') return isRu ? 'API-публикация' : 'API publish';
  if (normalized === 'create_supervised_task') return isRu ? 'контролируемое размещение' : 'supervised placement';
  if (normalized === 'manual_handoff') return isRu ? 'ручной шаг' : 'manual step';
  return isRu ? 'проверить' : 'check';
}

function _socialDispatchReasonLabel(reason: string, isRu: boolean): string {
  const normalized = String(reason || '').trim();
  if (normalized === 'channel_ready') return isRu ? 'Канал готов: после подтверждения исполнитель сможет выполнить API-публикацию.' : 'Channel is ready; after approval the worker can publish via API.';
  if (normalized === 'openclaw_browser_ready') return isRu ? 'OpenClaw browser-use готов, финальная кнопка публикации не нажимается без подтверждения.' : 'OpenClaw browser-use is ready; final publish is not clicked without approval.';
  if (normalized === 'openclaw_browser_unavailable') return isRu ? 'Браузерное размещение недоступно, нужен ручной или контролируемый режим.' : 'Browser-use is unavailable, manual/supervised fallback is needed.';
  if (normalized === 'publish_mode_not_api') return isRu ? 'Для канала нет API-режима, нужен ручной шаг.' : 'This channel has no API mode, manual step is needed.';
  return normalized;
}

function _socialInsightMetricLine(
  metrics: SocialRecommendationTopicInsight['metrics'] | undefined,
  isRu: boolean,
): string {
  const leads = Number(metrics?.leads || 0);
  const inquiries = Number(metrics?.inquiries || 0);
  const comments = Number(metrics?.comments || 0);
  const reach = Number(metrics?.reach || 0);
  return isRu
    ? `заявки ${leads}, обращения ${inquiries}, комментарии ${comments}, охват ${reach}`
    : `leads ${leads}, inquiries ${inquiries}, comments ${comments}, reach ${reach}`;
}

function _socialAttributionFeedback(eventType: SocialAttributionEventType): { ru: string; en: string } {
  if (eventType === 'lead') {
    return {
      ru: 'Заявка привязана к публикации. Следующий план будет учитывать её выше охватов.',
      en: 'Lead recorded for this post. Next plan will rank it above reach.',
    };
  }
  if (eventType === 'inquiry') {
    return {
      ru: 'Обращение привязано к публикации. Следующий план будет учитывать его выше лайков и охватов.',
      en: 'Inquiry recorded for this post. Next plan will rank it above likes and reach.',
    };
  }
  if (eventType === 'comment') {
    return {
      ru: 'Комментарий привязан к публикации как ранний сигнал интереса.',
      en: 'Comment recorded as an early interest signal for this post.',
    };
  }
  if (eventType === 'share') {
    return {
      ru: 'Репост привязан к публикации. Это усилит оценку формата, но ниже заявок и обращений.',
      en: 'Share recorded for this post. It helps evaluate the format, below leads and inquiries.',
    };
  }
  if (eventType === 'like') {
    return {
      ru: 'Лайк привязан к публикации как ранний сигнал. Заявки и обращения всё равно важнее.',
      en: 'Like recorded as an early signal. Leads and inquiries still rank higher.',
    };
  }
  if (eventType === 'view') {
    return {
      ru: 'Просмотр привязан к публикации как ранний сигнал охвата.',
      en: 'View recorded as an early reach signal for this post.',
    };
  }
  return {
    ru: 'Клик привязан к публикации как ранний сигнал интереса.',
    en: 'Click recorded as an early interest signal for this post.',
  };
}

function _socialQueueGroupLabel(group: SocialQueueGroup, isRu: boolean): string {
  const label = isRu ? group.label_ru : group.label_en;
  if (label) return label;
  const key = String(group.key || '').trim();
  if (key === 'needs_review') return isRu ? 'Нужно проверить' : 'Needs review';
  if (key === 'api_ready') return isRu ? 'Готово к API' : 'API ready';
  if (key === 'scheduled') return isRu ? 'Запланировано' : 'Scheduled';
  if (key === 'needs_supervised_publish') return isRu ? 'Нужно контролируемое размещение' : 'Needs supervised placement';
  if (key === 'needs_manual_publish') return isRu ? 'Нужно вручную / подключить канал' : 'Manual / connection needed';
  if (key === 'published') return isRu ? 'Опубликовано' : 'Published';
  if (key === 'failed') return isRu ? 'Ошибка' : 'Failed';
  return isRu ? 'Очередь' : 'Queue';
}

function _socialQueueGroupNextAction(group: SocialQueueGroup, isRu: boolean): string {
  const text = isRu ? group.next_action_ru : group.next_action_en;
  if (text) return text;
  return isRu ? 'Следующее действие будет показано после подготовки каналов.' : 'Next action appears after channel preparation.';
}

function _contentTypeLabel(contentType: string, isRu: boolean): string {
  const normalized = String(contentType || '').trim().toLowerCase();
  if (normalized === 'seo') return isRu ? 'SEO' : 'SEO';
  if (normalized === 'service') return isRu ? 'Услуга' : 'Service';
  if (normalized === 'sales') return isRu ? 'Продажи' : 'Sales';
  if (normalized === 'audit') return isRu ? 'Аудит' : 'Audit';
  if (normalized === 'seasonal') return isRu ? 'Сезонность' : 'Seasonal';
  return isRu ? 'Контент' : 'Content';
}

function _scopeChipLabel(scopeType: string, isRu: boolean): string {
  const normalized = String(scopeType || '').trim().toLowerCase();
  if (normalized === 'network_parent') return isRu ? 'Сеть' : 'Network';
  if (normalized === 'network_location') return isRu ? 'Точка' : 'Location';
  return isRu ? 'Бизнес' : 'Business';
}

function _locationScopeLabel(scopeType: string, isRu: boolean): string {
  const normalized = String(scopeType || '').trim().toLowerCase();
  if (normalized === 'network_parent') return isRu ? 'материнский план' : 'parent plan';
  if (normalized === 'network_location') return isRu ? 'локальный план' : 'local plan';
  return isRu ? 'текущий бизнес' : 'current business';
}

function _planTargetLabel(plan: Pick<PlanPayload, 'scope_type' | 'scope_target_label' | 'scope_target_city' | 'scope_target_address'>, isRu: boolean): string {
  const label = String(plan.scope_target_label || '').trim();
  const city = String(plan.scope_target_city || '').trim();
  const address = String(plan.scope_target_address || '').trim();
  if (label && city) return `${label} · ${city}`;
  if (label && address) return `${label} · ${address}`;
  if (label) return label;
  return _scopeChipLabel(plan.scope_type, isRu);
}

function _itemLocationLabel(item: Pick<PlanItem, 'location_label' | 'location_city' | 'location_address'>, isRu: boolean): string {
  const label = String(item.location_label || '').trim();
  const city = String(item.location_city || '').trim();
  const address = String(item.location_address || '').trim();
  if (label && city) return `${label} · ${city}`;
  if (label && address) return `${label} · ${address}`;
  if (label) return label;
  return isRu ? 'Точка сети' : 'Network location';
}

function _locationLabelByKey(items: PlanItem[], locationKey: string, isRu: boolean): string {
  for (const item of items) {
    const currentKey = String(item.location_scope || item.business_id || '').trim();
    if (currentKey === locationKey) {
      return _itemLocationLabel(item, isRu);
    }
  }
  return isRu ? 'Точка сети' : 'Network location';
}

function _bulkResultText(kind: 'drafts' | 'news', successCount: number, failedCount: number, isRu: boolean): string {
  if (kind === 'drafts') {
    if (failedCount > 0) {
      return isRu
        ? `сгенерировано черновиков ${successCount}, не получилось ${failedCount}`
        : `generated drafts ${successCount}, failed ${failedCount}`;
    }
    return isRu
      ? `сгенерировано черновиков ${successCount}`
      : `generated drafts ${successCount}`;
  }
  if (failedCount > 0) {
    return isRu
      ? `создано новостей ${successCount}, не получилось ${failedCount}`
      : `created news items ${successCount}, failed ${failedCount}`;
  }
  return isRu
    ? `создано новостей ${successCount}`
    : `created news items ${successCount}`;
}

function _bulkResultDetails(failedThemes: string[], isRu: boolean): string[] {
  const cleanThemes = failedThemes
    .map((theme) => String(theme || '').trim())
    .filter(Boolean)
    .slice(0, 3);
  if (cleanThemes.length === 0) return [];
  const prefix = isRu ? 'Не обработано' : 'Not processed';
  return cleanThemes.map((theme) => `${prefix}: ${theme}`);
}

function _learningCapabilityLabel(capability: string, isRu: boolean): string {
  const normalized = String(capability || '').trim().toLowerCase();
  if (normalized === 'content_plan.generate') return isRu ? 'Генерация плана' : 'Plan generation';
  if (normalized === 'content_plan.draft') return isRu ? 'Генерация черновика' : 'Draft generation';
  if (normalized === 'content_plan.item') return isRu ? 'Действия с элементами' : 'Item actions';
  if (normalized === 'content_plan.publish') return isRu ? 'Создание новостей' : 'News creation';
  return isRu ? 'Контент-план' : 'Content plan';
}

function _networkQualityReasonLabel(reason: string, isRu: boolean): string {
  const normalized = String(reason || '').trim();
  if (normalized === 'many_edits') return isRu ? 'часто правят перед публикацией' : 'often edited before publishing';
  if (normalized === 'skipped_items') return isRu ? 'есть пропущенные темы' : 'has skipped topics';
  if (normalized === 'major_rewrites') return isRu ? 'есть смысловые переписывания' : 'has major rewrites';
  if (normalized === 'drafts_not_published') return isRu ? 'черновики не доходят до новостей' : 'drafts do not reach publishing';
  if (normalized === 'stable') return isRu ? 'работает стабильно' : 'stable';
  return isRu ? 'нужна проверка' : 'needs review';
}

function _networkRiskLabel(riskScore: number, isRu: boolean): string {
  if (Number(riskScore || 0) >= 60) return isRu ? 'Высокий риск' : 'High risk';
  if (Number(riskScore || 0) >= 30) return isRu ? 'Средний риск' : 'Medium risk';
  return isRu ? 'Норма' : 'Stable';
}

function _networkOperatingRecommendation(reasons: string[], isRu: boolean): string {
  const normalized = Array.isArray(reasons) ? reasons.map((item) => String(item || '').trim()) : [];
  if (normalized.includes('drafts_not_published')) {
    return isRu
      ? 'Сначала доведите готовые черновики до новостей: здесь уже есть заготовки, но они не превращаются в публикации.'
      : 'Start by turning ready drafts into news: this location has drafts that do not reach publishing.';
  }
  if (normalized.includes('skipped_items')) {
    return isRu
      ? 'Проверьте темы этой точки: часть идей пропускается, значит нужно упростить поводы и оставить только то, что реально выпустить.'
      : 'Review this location themes: skipped items mean the topics should be simpler and easier to publish.';
  }
  if (normalized.includes('major_rewrites')) {
    return isRu
      ? 'Генерируйте черновики точнее: конкретная услуга, понятная выгода, доказательство и одно действие для клиента.'
      : 'Generate tighter drafts: concrete service, clear benefit, proof point, and one customer action.';
  }
  if (normalized.includes('many_edits')) {
    return isRu
      ? 'Перед публикацией проверьте формулировки: по этой точке часто нужны ручные правки.'
      : 'Review wording before publishing: this location often needs manual edits.';
  }
  return isRu
    ? 'Работайте ближайшей неделей: закройте темы без текста, затем создайте новости из готовых черновиков.'
    : 'Work through the nearest week: fill missing drafts, then create news from ready drafts.';
}

function _itemFilterLabel(filterKey: ItemFilterKey, isRu: boolean): string {
  if (filterKey === 'urgent') return isRu ? 'Срочное' : 'Urgent';
  if (filterKey === 'has_draft') return isRu ? 'Текст готов' : 'Draft ready';
  return isRu ? 'Все' : 'All';
}

function _planItemStatus(item: Pick<PlanItem, 'draft_text' | 'usernews_id' | 'status'>, isRu: boolean): { label: string; className: string } {
  const normalizedStatus = String(item.status || '').trim();
  const hasDraft = Boolean(String(item.draft_text || '').trim());
  const hasNews = Boolean(String(item.usernews_id || '').trim());
  const baseClassName = 'rounded-full px-2.5 py-1 text-xs font-semibold';
  if (normalizedStatus === 'skipped') {
    return {
      label: isRu ? 'Пропущено' : 'Skipped',
      className: `${baseClassName} bg-slate-100 text-slate-500`,
    };
  }
  if (hasNews) {
    return {
      label: isRu ? 'Новость создана' : 'News created',
      className: `${baseClassName} bg-emerald-100 text-emerald-800`,
    };
  }
  if (hasDraft) {
    return {
      label: isRu ? 'Текст готов' : 'Draft ready',
      className: `${baseClassName} bg-sky-100 text-sky-800`,
    };
  }
  return {
    label: isRu ? 'Без текста' : 'No draft',
    className: `${baseClassName} bg-amber-100 text-amber-800`,
  };
}

function _humanizePlanTitle(item: Pick<PlanItem, 'theme' | 'goal' | 'seo_keyword' | 'content_type'>, isRu: boolean): string {
  const rawTitle = String(item.theme || item.goal || item.seo_keyword || '').trim();
  const fallback = isRu ? 'Тема для публикации' : 'Publication topic';
  if (!rawTitle) return fallback;
  const noisyPrefixes = [
    'Закрыть слабую зону карточки:',
    'Недопокрытый поисковый сценарий:',
    'Ответить на спрос:',
    'Закрыть слабое место карточки:',
    'Аудит ·',
    'SEO ·',
    'Услуга ·',
    'Продажи ·',
  ];
  let title = rawTitle;
  for (const prefix of noisyPrefixes) {
    if (title.toLowerCase().startsWith(prefix.toLowerCase())) {
      title = title.slice(prefix.length).trim();
    }
  }
  title = title
    .replace(/\s+/g, ' ')
    .replace(/^["'«]+|["'»]+$/g, '')
    .trim();
  if (!title) return fallback;
  if (title.length <= 96) return title;
  return `${title.slice(0, 93).trim()}...`;
}

function _humanizePlanGoal(item: Pick<PlanItem, 'goal' | 'theme' | 'source_kind' | 'source_ref' | 'seo_keyword'>, isRu: boolean): string {
  const rawGoal = String(item.goal || '').trim();
  const rawTheme = String(item.theme || '').trim();
  const sourceRef = String(item.source_ref || item.seo_keyword || '').trim();
  const combined = `${rawGoal} ${rawTheme} ${sourceRef}`.toLowerCase();
  if (!rawGoal && !rawTheme && !sourceRef) {
    return isRu ? 'Причина не указана.' : 'No reason provided.';
  }
  if (
    combined.includes('недопокрытый поисковый сценарий')
    || combined.includes('закрыть слабую зону карточки')
    || combined.includes('закрыть слабое место карточки')
  ) {
    const readableSource = _cleanTechnicalPlanText(sourceRef || rawTheme);
    if (readableSource && /цен|стоимост|прайс|пример|работ|фото/i.test(readableSource)) {
      return isRu
        ? 'Клиенту проще записаться, если в карточке видно цену, результат и понятный следующий шаг.'
        : 'Customers are more likely to book when the listing shows price, result, and the next step.';
    }
    if (readableSource) {
      return isRu
        ? `Карточке нужен понятный ответ на запрос клиента: ${readableSource}.`
        : `The listing needs a clear answer for this customer search: ${readableSource}.`;
    }
    return isRu
      ? 'Карточке нужен более понятный ответ на поисковый сценарий клиента.'
      : 'The listing needs a clearer answer for this customer search scenario.';
  }
  return rawGoal || rawTheme || (isRu ? 'Причина не указана.' : 'No reason provided.');
}

function _cleanTechnicalPlanText(value: string): string {
  const prefixes = [
    'Закрыть слабую зону карточки:',
    'Закрыть слабое место карточки вокруг темы',
    'Закрыть слабое место карточки:',
    'Недопокрытый поисковый сценарий:',
    'Ответить на спрос:',
  ];
  let text = String(value || '').trim();
  let changed = true;
  while (changed) {
    changed = false;
    for (const prefix of prefixes) {
      if (text.toLowerCase().startsWith(prefix.toLowerCase())) {
        text = text.slice(prefix.length).trim();
        changed = true;
      }
    }
  }
  return text
    .replace(/^["'«]+|["'»]+$/g, '')
    .replace(/\s+и снизить сомнения перед звонком, визитом или записью\.?$/i, '')
    .replace(/\s+/g, ' ')
    .trim();
}

function _matchesItemFilter(item: PlanItem, filterKey: ItemFilterKey): boolean {
  const status = String(item.status || '').trim();
  const hasNews = Boolean(String(item.usernews_id || '').trim());
  const hasDraft = Boolean(String(item.draft_text || '').trim());
  if (status === 'skipped') return filterKey === 'all';
  if (filterKey === 'urgent') return !hasNews;
  if (filterKey === 'has_draft') return hasDraft && !hasNews;
  return true;
}

function _matchesDateRange(rawDate: string, fromDate: string, toDate: string): boolean {
  const itemDate = _inputDateValue(rawDate);
  const from = _inputDateValue(fromDate);
  const to = _inputDateValue(toDate);
  if (!itemDate) return !from && !to;
  if (from && itemDate < from) return false;
  if (to && itemDate > to) return false;
  return true;
}

function _signalFilterLabel(filterKey: SignalFilterKey, isRu: boolean): string {
  if (filterKey === 'seo') return 'SEO';
  if (filterKey === 'services') return isRu ? 'Услуги' : 'Services';
  if (filterKey === 'sales') return isRu ? 'Продажи' : 'Sales';
  if (filterKey === 'audit') return isRu ? 'Аудит' : 'Audit';
  if (filterKey === 'seasonal') return isRu ? 'Сезонность' : 'Seasonal';
  return isRu ? 'Все сигналы' : 'All signals';
}

function _sourceKindLabel(sourceKind: string, isRu: boolean): string {
  const normalized = String(sourceKind || '').trim().toLowerCase();
  if (normalized === 'seo_keyword') return isRu ? 'SEO-сигнал' : 'SEO signal';
  if (normalized === 'service') return isRu ? 'Основание: услуга' : 'Reason: service';
  if (normalized === 'transaction') return isRu ? 'Основание: продажи' : 'Reason: sales';
  if (normalized === 'audit_signal') return isRu ? 'Основание: аудит' : 'Reason: audit';
  if (normalized === 'seasonal') return isRu ? 'Основание: сезон' : 'Reason: season';
  if (normalized === 'fallback') return isRu ? 'Базовый сигнал' : 'Baseline signal';
  return isRu ? 'Сигнал' : 'Signal';
}

function _seoViewsLabel(item: Pick<PlanItem, 'source_kind' | 'seo_views'>, isRu: boolean): string {
  if (String(item.source_kind || '').trim().toLowerCase() !== 'seo_keyword') return '';
  const views = Number(item.seo_views || 0);
  if (!Number.isFinite(views) || views <= 0) return '';
  const formatted = new Intl.NumberFormat(isRu ? 'ru-RU' : 'en-US').format(Math.round(views));
  return isRu ? `${formatted} показов` : `${formatted} searches`;
}

function _matchesSignalFilter(item: PlanItem, filterKey: SignalFilterKey): boolean {
  if (filterKey === 'all') return true;
  const normalizedContentType = String(item.content_type || '').trim().toLowerCase();
  if (filterKey === 'services') return normalizedContentType === 'service';
  return normalizedContentType === filterKey;
}

function _matchesItemLocationFilter(item: PlanItem, filterKey: string): boolean {
  if (filterKey === 'all') return true;
  const itemKey = String(item.location_scope || item.business_id || '').trim();
  return itemKey === filterKey;
}

function _readStoredSortMode(): 'priority' | 'date' {
  if (typeof window === 'undefined') return 'priority';
  try {
    const raw = window.localStorage.getItem(CONTENT_PLAN_PREFERENCES_KEY);
    if (!raw) return 'priority';
    const parsed = JSON.parse(raw);
    const sortMode = parsed && typeof parsed.sortMode === 'string' ? parsed.sortMode : '';
    return sortMode === 'date' ? 'date' : 'priority';
  } catch {
    return 'priority';
  }
}

function _readStoredPreferences(businessId: string): Record<string, string> | null {
  if (!businessId || typeof window === 'undefined') return null;
  try {
    const raw = window.localStorage.getItem(`${CONTENT_PLAN_PREFERENCES_KEY}:${businessId}`);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === 'object' ? parsed : null;
  } catch {
    return null;
  }
}

function _writeStoredPreferences(businessId: string, value: Record<string, string>): void {
  if (!businessId || typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(`${CONTENT_PLAN_PREFERENCES_KEY}:${businessId}`, JSON.stringify(value));
    window.localStorage.setItem(CONTENT_PLAN_PREFERENCES_KEY, JSON.stringify({ sortMode: value.sortMode || 'priority' }));
  } catch {
    // Ignore storage write failures to keep the UI operational.
  }
}

function _isValidItemFilterKey(value: string): value is ItemFilterKey {
  return value === 'all'
    || value === 'urgent'
    || value === 'has_draft';
}

function _isValidContentLanguageKey(value: string): value is ContentLanguageKey {
  return CONTENT_LANGUAGE_OPTIONS.some((item) => item.value === value);
}

function _normalizeContentLanguage(value: string): ContentLanguageKey {
  const normalized = String(value || '').trim().toLowerCase();
  return _isValidContentLanguageKey(normalized) ? normalized : 'ru';
}

function _isValidSignalFilterKey(value: string): value is SignalFilterKey {
  return value === 'all'
    || value === 'seo'
    || value === 'services'
    || value === 'sales'
    || value === 'audit'
    || value === 'seasonal';
}

function _isValidViewPresetKey(value: string): value is ViewPresetKey {
  return value === 'overview'
    || value === 'urgent'
    || value === 'ready'
    || value === 'published'
    || value === 'focus'
    || value === 'custom';
}

function _inferViewPresetKey(value: {
  selectedItemFilter: ItemFilterKey;
  selectedSignalFilter: SignalFilterKey;
  selectedPlanTargetKey: string;
  selectedItemLocationKey: string;
  selectedWeekKey: string;
  dateFromFilter: string;
  dateToFilter: string;
  sortMode: 'priority' | 'date';
}): ViewPresetKey {
  if (
    value.selectedSignalFilter !== 'all'
    || value.selectedPlanTargetKey !== 'all'
    || value.selectedItemLocationKey !== 'all'
    || value.selectedWeekKey !== 'all'
    || value.dateFromFilter
    || value.dateToFilter
  ) {
    return 'custom';
  }
  if (value.selectedItemFilter === 'all') {
    return 'overview';
  }
  if (value.selectedItemFilter === 'urgent') {
    return 'urgent';
  }
  if (value.selectedItemFilter === 'has_draft') {
    return 'ready';
  }
  return 'custom';
}

function _shiftIsoDate(input: string, daysDelta: number): string {
  const normalized = _inputDateValue(input);
  if (!normalized) {
    return new Date(Date.now() + daysDelta * 24 * 60 * 60 * 1000).toISOString().slice(0, 10);
  }
  const parsed = new Date(`${normalized}T00:00:00Z`);
  if (Number.isNaN(parsed.getTime())) {
    return normalized;
  }
  parsed.setUTCDate(parsed.getUTCDate() + daysDelta);
  return parsed.toISOString().slice(0, 10);
}

function _autoScheduledDate(index: number): string {
  return _shiftIsoDate('', Math.max(Number(index || 0), 0) * 3);
}

function _inputDateValue(input: unknown): string {
  const rawValue = String(input || '').trim();
  if (!rawValue) return '';
  const isoMatch = rawValue.match(/\d{4}-\d{2}-\d{2}/);
  if (isoMatch) return isoMatch[0];
  const parsed = new Date(rawValue);
  if (Number.isNaN(parsed.getTime())) return '';
  return parsed.toISOString().slice(0, 10);
}

function _removeRecordKeys(source: Record<string, string>, keys: string[]): Record<string, string> {
  const blocked = new Set(keys.map((item) => String(item || '').trim()).filter(Boolean));
  const next: Record<string, string> = {};
  for (const [key, value] of Object.entries(source)) {
    if (!blocked.has(key)) {
      next[key] = value;
    }
  }
  return next;
}

function _formatPlanItemDate(input: unknown, isRu: boolean): string {
  const normalized = _inputDateValue(input);
  if (!normalized) return isRu ? 'Дата не назначена' : 'No date set';
  const parsed = new Date(`${normalized}T00:00:00Z`);
  if (Number.isNaN(parsed.getTime())) return normalized;
  return new Intl.DateTimeFormat(isRu ? 'ru-RU' : 'en-US', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  }).format(parsed);
}

function _itemPriorityRank(item: Pick<PlanItem, 'draft_text' | 'usernews_id'>): number {
  const hasNews = Boolean(String(item.usernews_id || '').trim());
  const hasDraft = Boolean(String(item.draft_text || '').trim());
  if (!hasDraft) return 0;
  if (hasDraft && !hasNews) return 1;
  return 2;
}

function _weekBucketKey(dateValue: string): string {
  const value = _inputDateValue(dateValue);
  if (!value) return '';
  const date = new Date(`${value}T00:00:00Z`);
  if (Number.isNaN(date.getTime())) return '';
  const day = date.getUTCDay() || 7;
  const monday = new Date(date);
  monday.setUTCDate(date.getUTCDate() - day + 1);
  return monday.toISOString().slice(0, 10);
}

function _weekBucketLabel(weekKey: string, isRu: boolean): string {
  const value = String(weekKey || '').trim();
  if (!value) return isRu ? 'Неделя' : 'Week';
  const monday = new Date(`${value}T00:00:00Z`);
  if (Number.isNaN(monday.getTime())) return value;
  const sunday = new Date(monday);
  sunday.setUTCDate(monday.getUTCDate() + 6);
  const formatter = new Intl.DateTimeFormat(isRu ? 'ru-RU' : 'en-US', {
    day: 'numeric',
    month: 'short',
  });
  return `${formatter.format(monday)} - ${formatter.format(sunday)}`;
}
