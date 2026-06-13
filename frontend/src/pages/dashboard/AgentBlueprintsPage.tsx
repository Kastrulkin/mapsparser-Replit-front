import type React from 'react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import {
  Activity,
  AlertTriangle,
  Bot,
  CheckCircle2,
  Clock3,
  Database,
  Download,
  FileCheck2,
  FileText,
  LifeBuoy,
  Loader2,
  Mail,
  MessageSquareText,
  Play,
  ReceiptText,
  RefreshCw,
  Search,
  Send,
  ShieldCheck,
  Sparkles,
  Star,
  Trash2,
  Upload,
  Users,
  Wrench,
  Workflow,
  Zap,
} from 'lucide-react';

import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  DashboardActionPanel,
  DashboardEmptyState,
  DashboardPageHeader,
  DashboardSection,
} from '@/components/dashboard/DashboardPrimitives';
import { newAuth } from '@/lib/auth_new';
import { api } from '@/services/api';
import { cn } from '@/lib/utils';

type DashboardContext = {
  currentBusinessId: string | null;
  currentBusiness?: ({ id?: string; name?: string } & Record<string, unknown>) | null;
};

type AgentBlueprint = {
  id: string;
  business_id: string;
  name: string;
  category: string;
  description?: string | null;
  status: string;
  latest_version_id?: string | null;
  latest_version_number?: number | null;
  latest_goal?: string | null;
  active_version_id?: string | null;
  active_version_number?: number | null;
  active_goal?: string | null;
  active_persona_agent_id?: string | null;
  latest_persona_agent_id?: string | null;
  persona?: AgentVoicePersona | null;
  voice?: AgentVoicePersona | null;
  product_agent?: ProductAgentView | null;
  last_run_id?: string | null;
  last_run_status?: string | null;
  last_run_started_at?: string | null;
  last_run_completed_at?: string | null;
  pending_approvals_count?: number;
  sources_count?: number;
  journal_entries_count?: number;
  versions_count?: number;
  metadata_json?: Record<string, unknown>;
};

type AgentVoicePersona = {
  id: string;
  name?: string;
  role?: string;
  source?: string;
  description?: string;
  identity?: string;
  speech_style?: string;
  is_active?: boolean;
};

type ProductAgentView = {
  id?: string;
  kind?: string;
  source?: string;
  persona_agent_id?: string | null;
  persona?: AgentVoicePersona | null;
  voice?: AgentVoicePersona | null;
};

type AgentApproval = {
  id: string;
  run_id?: string;
  status: string;
  approval_type: string;
  title: string;
  payload_json?: Record<string, unknown>;
  decision_reason?: string | null;
  requested_at?: string | null;
  run_status?: string | null;
  run_started_at?: string | null;
};

type AgentArtifact = {
  id: string;
  artifact_type: string;
  title: string;
  payload_json?: {
    status?: string;
    source?: string;
    count?: number;
    items?: Array<Record<string, unknown>>;
    external_dispatch_performed?: boolean;
    dispatch_state?: string;
    operator_note?: string;
    next_step?: string;
    source_artifact?: string;
    filters?: Record<string, unknown>;
    queue_count?: number;
    queued_count?: number;
    draft_ids?: string[];
    [key: string]: unknown;
  };
};

type AgentRunStep = {
  id: string;
  step_key: string;
  step_type: string;
  status: string;
  output_json?: {
    status?: string;
    dispatch_state?: string;
    external_dispatch_performed?: boolean;
    queue_count?: number;
    orchestrator?: {
      result?: {
        status?: string;
        dispatch_state?: string;
        external_dispatch_performed?: boolean;
        queue_count?: number;
        [key: string]: unknown;
      };
      [key: string]: unknown;
    };
    [key: string]: unknown;
  };
  error_text?: string | null;
};

type AgentRunBillingAction = {
  action_id?: string;
  capability?: string;
  status?: string;
  reserved_tokens?: number;
  settled_tokens?: number;
  released_tokens?: number;
  inflight_reserved_tokens?: number;
  total_cost?: number;
  entry_count?: number;
};

type AgentRunObservability = {
  schema?: string;
  preview_summary?: Record<string, unknown>;
  run_history?: Record<string, unknown>;
  step_history?: { count?: number; completed?: number; failed?: number; items?: AgentRunStep[] };
  artifacts?: { count?: number; items?: AgentArtifact[] };
  approvals?: { count?: number; pending?: number; items?: AgentApproval[] };
  action_ids?: string[];
  action_ledger?: {
    count?: number;
    items?: Array<{
      action_id?: string;
      capability?: string;
      status?: string;
      trace_id?: string;
      billing_summary?: {
        reserved_tokens?: number;
        settled_tokens?: number;
        released_tokens?: number;
        inflight_reserved_tokens?: number;
        total_cost?: number;
      };
      delivery_stats?: Record<string, unknown>;
      timeline?: { count?: number; events?: Array<Record<string, unknown>> };
      error?: string;
    }>;
  };
  domain_requests?: {
    count?: number;
    pending?: number;
    items?: Array<{
      kind?: string;
      id?: string;
      action_id?: string;
      review_id?: string;
      title?: string;
      summary?: string;
      status?: string;
      approval_state?: string;
      apply_state?: string;
      delivery_state?: string;
      why_waiting?: string;
      recipient_count?: number;
      recipients?: Array<Record<string, unknown>>;
      row_values?: unknown[];
      mapping?: Record<string, unknown>;
      limits?: Record<string, unknown>;
      consent?: Record<string, unknown>;
      suggestions?: Array<Record<string, unknown>>;
      visual_diff?: Array<Record<string, unknown>>;
      delivery_journal?: {
        count?: number;
        queued?: number;
        blocked?: number;
        items?: Array<Record<string, unknown>>;
      };
      publish_requests?: {
        count?: number;
        queued?: number;
        items?: Array<Record<string, unknown>>;
      };
      provider_handoff?: Record<string, unknown>;
      error?: string | null;
      rows_requiring_review?: Array<Record<string, unknown>>;
      proposal_count?: number;
      review_count?: number;
      error_count?: number;
      rows_total?: number;
      rows_imported?: number;
      rows_skipped?: number;
      rows_failed?: number;
      localos_write_performed?: boolean;
      can_apply?: boolean;
      apply_endpoint?: string;
      provider_write_performed?: boolean;
      created_at?: string;
    }>;
  };
  integration_preflight?: AgentIntegrationPreflight;
  delivery_status?: {
    state?: string;
    queued_count?: number;
    attempts_total?: number;
    attempts_success?: number;
    attempts_failed?: number;
    last_error?: string | null;
    external_dispatch_performed?: boolean;
  };
  cost_tokens?: {
    reserved_tokens?: number;
    settled_tokens?: number;
    released_tokens?: number;
    inflight_reserved_tokens?: number;
    total_cost?: number;
  };
  billing_ledger?: {
    summary?: {
      reserved_tokens?: number;
      settled_tokens?: number;
      released_tokens?: number;
      inflight_reserved_tokens?: number;
      total_cost?: number;
    };
    actions?: AgentRunBillingAction[];
    entries?: Array<{
      action_id?: string;
      capability?: string;
      entry_type?: string;
      tokens_in?: number;
      tokens_out?: number;
      cost?: number;
      tariff_id?: string;
      month_key?: string;
      created_at?: string;
    }>;
  };
  errors?: Array<{
    source?: string;
    step_key?: string;
    action_id?: string;
    status?: string;
    error_text?: string | null;
  }>;
  recovery_actions?: Array<{
    code?: string;
    label?: string;
    target?: string;
  }>;
  support_export?: {
    endpoint?: string;
    formats?: string[];
    source?: string;
  };
};

type AgentRun = {
  id: string;
  status: string;
  blueprint_id: string;
  input_json?: Record<string, unknown>;
  steps?: AgentRunStep[];
  artifacts?: AgentArtifact[];
  approvals?: AgentApproval[];
  error_text?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  observability?: AgentRunObservability;
};

type AgentMetricsSummary = {
  schema?: string;
  compiled?: {
    candidate_status?: string;
    validation_status?: string;
    validation_valid?: boolean;
    error_count?: number;
    warning_count?: number;
    runtime_llm_required?: boolean;
  };
  versions?: {
    total?: number;
    active_version_id?: string;
    active_version_number?: number;
  };
  runs?: {
    loaded?: number;
    by_status?: Record<string, number>;
    last_run?: Record<string, unknown>;
  };
  approvals?: {
    pending?: number;
    waiting_reasons?: string[];
  };
  cost_tokens?: {
    reserved_tokens?: number;
    settled_tokens?: number;
    released_tokens?: number;
    inflight_reserved_tokens?: number;
    total_cost?: number;
    agent_creation_charged?: number;
    breakdown?: AgentBillingBreakdownItem[];
  };
  billing_breakdown?: {
    schema?: string;
    total_items?: number;
    items?: AgentBillingBreakdownItem[];
  };
  setup?: {
    required_bindings?: number;
    learning_events?: number;
  };
};

type AgentBillingBreakdownItem = {
  key?: string;
  label?: string;
  count?: number;
  estimated_credits?: number;
  charged_credits?: number;
  settled_tokens?: number;
  total_cost?: number;
  ledger_entries?: number;
  status?: string;
};

type AgentBlueprintDetails = {
  blueprint?: AgentBlueprint;
  versions: Array<Record<string, unknown>>;
  runs: AgentRun[];
  approval_queue?: AgentApproval[];
  active_version?: Record<string, unknown> | null;
  active_version_id?: string;
  active_version_number?: number;
  learning_events?: AgentLearningEvent[];
  version_events?: AgentVersionEvent[];
  feedback_history?: Array<Record<string, unknown>>;
  legacy_migration?: Record<string, unknown>;
  metrics?: AgentMetricsSummary;
  activation_gate?: AgentActivationGate;
};

type AgentVersionDiff = {
  summary?: string;
  changed_fields?: string[];
  changes?: Array<{
    field?: string;
    label?: string;
    change_type?: string;
    before?: string;
    after?: string;
  }>;
};

type AgentLearningLoop = {
  schema?: string;
  mode?: string;
  trigger_type?: string;
  trigger_label?: string;
  activation_state?: string;
  human_gate_required?: boolean;
  candidate_version_id?: string;
  candidate_version_number?: number;
  previous_version_id?: string;
  previous_version_number?: number;
  diff?: AgentVersionDiff;
  explanation?: string;
};

type AgentLearningEvent = {
  run_id?: string;
  trigger_type?: string;
  feedback?: string;
  previous_version_id?: string;
  candidate_version_id?: string;
  candidate_version_number?: number;
  activation_state?: string;
  created_at?: string;
};

type AgentVersionEvent = {
  action?: string;
  reason?: string;
  previous_active_version_id?: string;
  active_version_id?: string;
  active_version_number?: number;
  created_at?: string;
};

type AgentSource = {
  id?: string;
  source_type?: string;
  name?: string;
  file_name?: string;
  internal_source?: string;
  extraction_state?: string;
  extraction_error?: string;
  file_size_bytes?: number;
  content_length?: number;
};

type AgentSourceCatalogItem = {
  key: string;
  title: string;
  description?: string;
  available_count?: number;
  connected?: boolean;
  preview?: string[];
  state?: string;
  source_type?: string;
  extraction_state?: string;
  error?: string;
};

type AgentIntegration = {
  id: string;
  provider: string;
  provider_label?: string;
  status: string;
  display_name?: string;
  auth_ref?: string;
  has_auth_ref?: boolean;
  attached?: boolean;
  config?: Record<string, unknown>;
  limits?: Record<string, unknown>;
  execution_boundary?: {
    capabilities?: string[];
    triggers?: string[];
    approval_required?: boolean;
    executor?: string;
    external_write?: string;
  };
};

type AgentExternalAuthOption = {
  id: string;
  source: string;
  display_name?: string;
  updated_at?: string;
};

type AgentIntegrationCatalogItem = {
  provider: string;
  title: string;
  description?: string;
  required_config?: string[];
  default_limits?: Record<string, unknown>;
  status?: string;
  providers?: Array<{ provider?: string; label?: string; status?: string }>;
};

type AgentIntegrationBindingStatus = {
  key: string;
  provider: string;
  direction?: string;
  required?: boolean;
  approval_required?: boolean;
  capability?: string;
  trigger?: string;
  status: string;
  integration_id?: string;
  missing_config?: string[];
  resolution?: string;
  route_provider?: string;
  route?: AgentProviderRoute;
  execution_boundary?: string;
  autonomy_level?: string;
  credential_state?: string;
  approval_state?: string;
  policy_summary?: string;
  next_action_label?: string;
  answer_config?: Record<string, unknown>;
};

type AgentIntegrationPreflight = {
  status?: string;
  ready?: boolean;
  missing_count?: number;
  next_action?: string;
  items?: AgentIntegrationBindingStatus[];
  missing?: AgentIntegrationBindingStatus[];
};

type AgentProviderAction = {
  kind?: string;
  available?: boolean;
  ui_target?: string;
  label?: string;
  description?: string;
  role?: string;
};

type AgentProviderRoute = {
  provider?: string;
  label?: string;
  state?: string;
  status?: string;
  role?: string;
  kind?: string;
  connect_mode?: string;
  primary_cta?: string;
  provider_action?: AgentProviderAction;
};

type AgentConnectionPlanItem = {
  key?: string;
  provider?: string;
  title?: string;
  capability?: string;
  trigger?: string;
  direction?: string;
  binding_status?: string;
  action?: string;
  primary_label?: string;
  explanation?: string;
  route_state?: string;
  route_summary?: string;
  why_blocked?: string;
  setup_cta?: {
    label?: string;
    action?: string;
    binding_key?: string;
    provider?: string;
    route_provider?: string;
  };
  execution_boundary?: string;
  autonomy_level?: string;
  credential_state?: string;
  approval_state?: string;
  policy_summary?: string;
  next_action_label?: string;
  missing_config?: string[];
  approval_required?: boolean;
  existing_integrations?: Array<{ id?: string; provider?: string; display_name?: string; status?: string }>;
  attached_integrations?: Array<{ id?: string; provider?: string; display_name?: string; status?: string }>;
  provider_routes?: AgentProviderRoute[];
  provider_paths?: Array<{ provider?: string; label?: string; status?: string }>;
  recommended_route?: AgentProviderRoute | null;
  recommended_route_reason?: string;
};

type AgentConnectionPlan = {
  schema?: string;
  status?: string;
  missing_count?: number;
  items?: AgentConnectionPlanItem[];
};

type AgentConnectionDecision = {
  tone: string;
  title: string;
  description: string;
  action: string;
  cta: string;
  bindingKey?: string;
};

type AgentActivationGate = {
  schema?: string;
  status?: string;
  can_activate?: boolean;
  next_step?: string;
  next_binding_key?: string;
  active_version_id?: string;
  blockers?: Array<{ type?: string; provider?: string; message?: string }>;
  human_blockers?: Array<{ type?: string; provider?: string; title?: string; message?: string; action?: string }>;
  summary?: string;
  primary_action_label?: string;
  connection_plan?: AgentConnectionPlan;
  preflight?: AgentIntegrationPreflight;
  preview_run_status?: {
    ready?: boolean;
    status?: string;
    message?: string;
    latest_run?: Record<string, unknown> | null;
    passed_run?: Record<string, unknown> | null;
  };
  compiled_validation?: {
    ready?: boolean;
    validation?: {
      status?: string;
      errors?: Array<{ field?: string; message?: string }>;
      warnings?: Array<{ field?: string; message?: string }>;
    };
  };
  approval_policy_status?: {
    ready?: boolean;
    status?: string;
    summary?: string;
    write_steps?: Array<{ key?: string; capability?: string; requires_approval?: boolean; required_approval_type?: string }>;
    missing_approval_steps?: string[];
    autonomous_writes_allowed?: boolean;
  };
};

type AgentActivationPathStep = {
  key: string;
  label: string;
  detail: string;
  status: string;
};

type AgentPostCreateHandoff = {
  schema?: string;
  status?: string;
  next_step?: string;
  workspace_mode?: AgentWorkspaceMode;
  next_binding_key?: string;
  next_binding?: AgentConnectionPlanItem | null;
  next_route?: AgentProviderRoute | null;
  title?: string;
  description?: string;
  missing_bindings?: AgentIntegrationBindingStatus[];
  items?: AgentIntegrationBindingStatus[];
  connection_plan?: AgentConnectionPlan | null;
};

type AgentReviewSection = {
  title?: string;
  artifact_type?: string;
  status?: string;
  summary?: string;
  payload?: Record<string, unknown>;
};

type AgentJournalEntry = {
  kind?: string;
  title?: string;
  status?: string;
  summary?: string;
  details?: Array<{ label?: string; value?: string }>;
  payload?: Record<string, unknown>;
};

type AgentReview = {
  has_run?: boolean;
  run_id?: string;
  run_status?: string;
  setup?: Record<string, unknown>;
  sources?: AgentSource[];
  used_sources?: AgentSource[];
  sections?: AgentReviewSection[];
  journal?: AgentJournalEntry[];
  approvals?: AgentApproval[];
};

type AgentBuilderScenario = {
  category: string;
  title: string;
  description: string;
  prompt: string;
  dataSources: string;
  extraction: string;
  processing: string;
  output: string;
  manualControl: string;
  icon: typeof FileText;
};

type PersonaAgent = {
  id: string;
  name?: string;
  type?: string;
  description?: string;
  task?: string;
  identity?: string;
  is_active?: boolean;
};

type LegacyMigrationPlan = {
  mode?: string;
  legacy_agents?: Array<{
    agent_id?: string;
    name?: string;
    action?: string;
    reason?: string;
    linked_to_blueprint?: boolean;
    legacy_workflow?: {
      present?: boolean;
      status?: string;
    };
  }>;
  business_settings?: {
    fields?: Record<string, { present?: boolean; status?: string; target?: string; current_value_preview?: unknown }>;
    rule?: string;
  };
  runtime_truth?: Record<string, string>;
  deletion_rule?: {
    allowed?: boolean;
    required_before_delete?: string[];
  };
};

type AgentWorkspaceMode = 'overview' | 'settings' | 'run' | 'results' | 'connections' | 'voice' | 'advanced';

type FeedbackVersionNotice = {
  version_id?: string;
  previous_version_id?: string;
  version_number?: number;
  feedback?: string;
  next_run_note?: string;
  activation_state?: string;
  trigger_label?: string;
  diff?: AgentVersionDiff;
};

type AgentBuilderMessage = {
  role: 'user' | 'assistant';
  content: string;
};

type AgentBuilderQuestion = {
  key?: string;
  question: string;
  reason?: string;
  provider?: string;
  role?: string;
};

type AgentBuilderConnectorPreview = {
  key?: string;
  provider?: string;
  title?: string;
  status?: string;
  connection_count?: number;
  missing_config?: string[];
  connections?: Array<{ id?: string; display_name?: string; provider?: string }>;
  action?: {
    kind?: string;
    label?: string;
    description?: string;
    after_draft?: string;
  };
};

type AgentBuilderFeasibility = {
  status?: string;
  ready?: boolean;
  next_action?: string;
  missing_connections?: AgentBuilderConnectorPreview[];
  connection_choices?: AgentBuilderConnectorPreview[];
  ready_bindings?: AgentBuilderConnectorPreview[];
  forbidden?: Array<{ term?: string; reason?: string }>;
  unsupported?: Array<{ capability?: string; reason?: string }>;
};

type AgentBuilderSetupStep = {
  key?: string;
  label?: string;
  status?: string;
  description?: string;
  questions?: AgentBuilderQuestion[];
  missing_connections?: AgentBuilderConnectorPreview[];
  connection_choices?: AgentBuilderConnectorPreview[];
};

type AgentBuilderSetupFlow = {
  schema?: string;
  status?: string;
  primary_action?: string;
  next_step?: string;
  next_step_title?: string;
  next_step_description?: string;
  can_create_draft?: boolean;
  can_run_preview?: boolean;
  can_activate?: boolean;
  post_create_status?: string;
  post_create_next_step?: string;
  post_create_description?: string;
  activation_blockers?: Array<{ type?: string; provider?: string; message?: string }>;
  steps?: AgentBuilderSetupStep[];
};

type AgentBuilderPlannerLoop = {
  schema?: string;
  status?: string;
  may_execute_tools?: boolean;
  must_compile_in_localos?: boolean;
  catalog_source?: string;
  capability_plan?: Array<{
    capability?: string;
    openclaw_supported?: boolean;
    provider_paths?: string[];
    openclaw_actions?: Array<{ service?: string; action?: string; openclaw_action_ref?: string }>;
  }>;
  workflow_proposal?: {
    openclaw_action_refs?: string[];
    provider_paths?: Array<{ capability?: string; provider_path?: string }>;
    policy?: string;
  };
  planner_contract?: {
    execution_mode?: string;
    tool_execution_allowed?: boolean;
    external_side_effects_allowed?: boolean;
    compiled_workflow_owner?: string;
    must_not?: string[];
  };
};

type AgentCompilerPolicyItem = {
  key?: string;
  title?: string;
  type?: string;
  request?: string;
  reason?: string;
  capability?: string;
  provider?: string;
  message?: string;
  text?: string;
};

type AgentCompilerWorkflowDraft = {
  trigger?: string;
  steps?: AgentCompilerPolicyItem[];
  outputs?: AgentCompilerPolicyItem[];
  output?: AgentCompilerPolicyItem[];
  limits?: Record<string, unknown>;
};

type AgentCompilerPolicyReview = {
  schema?: string;
  source?: string;
  status?: string;
  workflow_draft?: AgentCompilerWorkflowDraft;
  approval_points?: AgentCompilerPolicyItem[];
  unsupported_requests?: AgentCompilerPolicyItem[];
};

type AgentConnectorIntelligence = {
  schema?: string;
  status?: string;
  headline?: string;
  can_compile_draft?: boolean;
  can_preview_after_connections?: boolean;
  next_action?: string;
  bindings?: Array<{
    key?: string;
    provider?: string;
    title?: string;
    capability?: string;
    status?: string;
    action?: string;
    route_state?: string;
    route_summary?: string;
    action_label?: string;
    explanation?: string;
    setup_cta?: { mode?: string; label?: string; description?: string };
    connection_count?: number;
    missing_config?: string[];
    connections?: Array<{ id?: string; display_name?: string; provider?: string }>;
    provider_routes?: AgentProviderRoute[];
    recommended_route?: AgentProviderRoute | null;
    recommended_route_reason?: string;
    provider_paths?: Array<{ provider?: string; label?: string; status?: string; source?: string }>;
  }>;
  capabilities?: Array<{
    capability?: string;
    status?: string;
    route_state?: string;
    provider_routes?: AgentProviderRoute[];
    provider_candidates?: Array<{ provider?: string; state?: string; role?: string; label?: string }>;
    openclaw_actions?: Array<{ service?: string; action?: string; openclaw_action_ref?: string }>;
  }>;
  provider_paths?: Array<{ provider?: string; label?: string; status?: string; source?: string }>;
  forbidden?: Array<{ term?: string; reason?: string }>;
  unsupported?: Array<{ capability?: string; reason?: string }>;
};

type AgentConnectionSummary = {
  schema?: string;
  status?: string;
  headline?: string;
  next_action?: string;
  next_action_label?: string;
  ready_count?: number;
  missing_count?: number;
  choice_count?: number;
  blocked_count?: number;
  items?: Array<{
    key?: string;
    provider?: string;
    title?: string;
    capability?: string;
    status?: string;
    action?: string;
    action_label?: string;
    explanation?: string;
    setup_cta?: { mode?: string; label?: string; description?: string };
    connection_count?: number;
    connections?: Array<{ id?: string; display_name?: string; provider?: string }>;
    missing_config?: string[];
    provider_paths?: Array<{ provider?: string; label?: string; status?: string; source?: string }>;
  }>;
  forbidden?: Array<{ term?: string; reason?: string }>;
  unsupported?: Array<{ capability?: string; reason?: string }>;
};

type AgentConnectionReadinessService = {
  key?: string;
  provider?: string;
  title?: string;
  capability?: string;
  action?: string;
  action_label?: string;
  status?: string;
  route_state?: string;
  route_summary?: string;
  explanation?: string;
  provider_route_label?: string;
  provider_route_cta?: string;
  recommended_route?: AgentProviderRoute | null;
  recommended_route_reason?: string;
  connect_mode?: string;
  connection_count?: number;
  missing_config?: string[];
  connections?: Array<{ id?: string; display_name?: string; provider?: string }>;
  setup_cta?: { mode?: string; label?: string; description?: string };
};

type AgentConnectionReadiness = {
  schema?: string;
  status?: string;
  next_action?: string;
  title?: string;
  description?: string;
  required_count?: number;
  ready_count?: number;
  missing_count?: number;
  choice_count?: number;
  blocked_count?: number;
  can_create_draft?: boolean;
  can_run_preview_after_create?: boolean;
  post_create_workspace?: string;
  services?: AgentConnectionReadinessService[];
  ready_services?: AgentConnectionReadinessService[];
  missing_services?: AgentConnectionReadinessService[];
  choice_services?: AgentConnectionReadinessService[];
  blocked_services?: AgentConnectionReadinessService[];
  forbidden?: Array<{ term?: string; reason?: string }>;
  unsupported?: Array<{ capability?: string; reason?: string }>;
};

type AgentConnectionResolverItem = {
  key?: string;
  role?: string;
  role_label?: string;
  provider?: string;
  service_label?: string;
  capability?: string;
  direction?: string;
  state?: string;
  state_label?: string;
  recommended_provider?: string;
  recommended_label?: string;
  recommended_cta?: string;
  connect_mode?: string;
  explanation?: string;
  resolution_hint?: string;
  connection_count?: number;
  connections?: Array<{ id?: string; display_name?: string; provider?: string }>;
  missing_config?: string[];
  provider_routes?: AgentProviderRoute[];
  recommended_route?: AgentProviderRoute | null;
};

type AgentConnectionResolver = {
  schema?: string;
  status?: string;
  title?: string;
  summary?: string;
  next_action?: string;
  next_action_label?: string;
  can_continue?: boolean;
  required_count?: number;
  resolved_count?: number;
  unresolved_count?: number;
  blocked_count?: number;
  items?: AgentConnectionResolverItem[];
  forbidden?: Array<{ term?: string; reason?: string }>;
  unsupported?: Array<{ capability?: string; reason?: string }>;
};

type AgentServiceIntelligenceItem = {
  kind?: string;
  key?: string;
  provider?: string;
  service_label?: string;
  capability?: string;
  direction?: string;
  state?: string;
  state_label?: string;
  explanation?: string;
  next_action?: string;
  recommended_provider?: string;
  recommended_label?: string;
  recommended_route?: AgentProviderRoute | null;
  provider_routes?: AgentProviderRoute[];
  connection_count?: number;
  connections?: Array<{ id?: string; display_name?: string; provider?: string }>;
  missing_config?: string[];
};

type AgentServiceIntelligence = {
  schema?: string;
  status?: string;
  headline?: string;
  can_create_draft?: boolean;
  can_activate?: boolean;
  state_counts?: Record<string, number>;
  items?: AgentServiceIntelligenceItem[];
};

type AgentBuilderPreview = {
  understood_task?: string;
  category?: string;
  category_label?: string;
  agent_name?: string;
  data_sources?: string[];
  extraction_rules?: string;
  processing_rules?: string;
  output_format?: string;
  manual_control?: string;
  approval_boundaries?: string[];
  required_connectors?: AgentBuilderConnectorPreview[];
  feasibility?: AgentBuilderFeasibility;
  connector_intelligence?: AgentConnectorIntelligence;
  service_intelligence?: AgentServiceIntelligence;
  connection_readiness?: AgentConnectionReadiness;
  connection_resolver?: AgentConnectionResolver;
  connection_answer_bindings?: Record<string, Record<string, unknown>>;
  connection_summary?: AgentConnectionSummary;
  setup_flow?: AgentBuilderSetupFlow;
  connection_plan?: AgentConnectionPlan;
  openclaw_planner_loop?: AgentBuilderPlannerLoop;
  compiler_policy_review?: AgentCompilerPolicyReview;
  compiler_workflow_draft?: AgentCompilerWorkflowDraft;
  compiler_approval_points?: AgentCompilerPolicyItem[];
  compiler_unsupported_requests?: AgentCompilerPolicyItem[];
  external_dispatch_performed?: boolean;
  cost_preview?: {
    label?: string;
    estimated_credits?: number;
    actual_credits?: number;
    billing_url?: string;
    copy?: string;
  };
};

type AgentBuilderSession = {
  id: string;
  business_id: string;
  status: string;
  category: string;
  messages?: AgentBuilderMessage[];
  preview?: AgentBuilderPreview;
  missing_questions?: AgentBuilderQuestion[];
  blueprint_id?: string | null;
};

const getRequestErrorMessage = (requestError: unknown, fallback: string) => {
  if (requestError instanceof Error && requestError.message.trim()) {
    return requestError.message
      .replace(/^Ошибка соединения с сервером:\s*/i, '')
      .replace(/^Ошибка запроса:\s*/i, '');
  }
  return fallback;
};

const objectValue = (value: object, key: string): unknown => {
  const entry = Object.entries(value).find(([entryKey]) => entryKey === key);
  return entry ? entry[1] : undefined;
};

const recordValue = (value: unknown): Record<string, unknown> | null => (
  value && typeof value === 'object' && !Array.isArray(value) ? Object.fromEntries(Object.entries(value)) : null
);

const getBlueprintMetadata = (blueprint?: AgentBlueprint | null): Record<string, unknown> => (
  recordValue(blueprint?.metadata_json) || {}
);

const getBlueprintBuilderPreview = (blueprint?: AgentBlueprint | null): AgentBuilderPreview | null => {
  const metadata = getBlueprintMetadata(blueprint);
  const preview = recordValue(metadata.agent_builder_preview);
  return preview ? { ...preview } : null;
};

const normalizePostCreateHandoff = (value: unknown): AgentPostCreateHandoff | null => {
  if (!value || typeof value !== 'object') {
    return null;
  }
  const missingBindings = objectValue(value, 'missing_bindings');
  const items = objectValue(value, 'items');
  const connectionPlan = normalizeConnectionPlan(objectValue(value, 'connection_plan'));
  const nextBinding = normalizeConnectionPlanItem(objectValue(value, 'next_binding'));
  const nextRoute = normalizeProviderRoute(objectValue(value, 'next_route'));
  const normalizedMissingBindings = Array.isArray(missingBindings) ? missingBindings : [];
  const firstMissingBinding = normalizedMissingBindings.find((item) => item && typeof item === 'object');
  return {
    schema: String(objectValue(value, 'schema') || ''),
    status: String(objectValue(value, 'status') || ''),
    next_step: String(objectValue(value, 'next_step') || ''),
    workspace_mode: String(objectValue(value, 'workspace_mode') || ''),
    next_binding_key: String(objectValue(value, 'next_binding_key') || (firstMissingBinding && typeof firstMissingBinding === 'object' ? objectValue(firstMissingBinding, 'key') || '' : '')),
    next_binding: nextBinding,
    next_route: nextRoute,
    title: String(objectValue(value, 'title') || ''),
    description: String(objectValue(value, 'description') || ''),
    missing_bindings: normalizedMissingBindings,
    items: Array.isArray(items) ? items : [],
    connection_plan: connectionPlan,
  };
};

const normalizeAgentIntegrationPreflight = (value: unknown): AgentIntegrationPreflight | undefined => {
  if (!value || typeof value !== 'object') {
    return undefined;
  }
  const missingCount = objectValue(value, 'missing_count');
  const items = objectValue(value, 'items');
  const missing = objectValue(value, 'missing');
  const ready = objectValue(value, 'ready');
  return {
    status: String(objectValue(value, 'status') || ''),
    ready: typeof ready === 'boolean' ? ready : undefined,
    missing_count: typeof missingCount === 'number' ? missingCount : undefined,
    next_action: String(objectValue(value, 'next_action') || ''),
    items: Array.isArray(items) ? items : [],
    missing: Array.isArray(missing) ? missing : [],
  };
};

const normalizeConnectionPlan = (value: unknown): AgentConnectionPlan | null => {
  if (!value || typeof value !== 'object') {
    return null;
  }
  const items = objectValue(value, 'items');
  const missingCount = objectValue(value, 'missing_count');
  return {
    schema: String(objectValue(value, 'schema') || ''),
    status: String(objectValue(value, 'status') || ''),
    missing_count: typeof missingCount === 'number' ? missingCount : undefined,
    items: Array.isArray(items) ? items : [],
  };
};

const normalizeConnectionPlanItem = (value: unknown): AgentConnectionPlanItem | null => {
  if (!value || typeof value !== 'object') {
    return null;
  }
  const providerRoutes = objectValue(value, 'provider_routes');
  const providerPaths = objectValue(value, 'provider_paths');
  const recommendedRoute = normalizeProviderRoute(objectValue(value, 'recommended_route'));
  const missingConfig = objectValue(value, 'missing_config');
  const existingIntegrations = objectValue(value, 'existing_integrations');
  const attachedIntegrations = objectValue(value, 'attached_integrations');
  return {
    key: String(objectValue(value, 'key') || ''),
    provider: String(objectValue(value, 'provider') || ''),
    title: String(objectValue(value, 'title') || ''),
    capability: String(objectValue(value, 'capability') || ''),
    trigger: String(objectValue(value, 'trigger') || ''),
    direction: String(objectValue(value, 'direction') || ''),
    binding_status: String(objectValue(value, 'binding_status') || ''),
    action: String(objectValue(value, 'action') || ''),
    primary_label: String(objectValue(value, 'primary_label') || ''),
    explanation: String(objectValue(value, 'explanation') || ''),
    route_state: String(objectValue(value, 'route_state') || ''),
    route_summary: String(objectValue(value, 'route_summary') || ''),
    missing_config: Array.isArray(missingConfig) ? missingConfig : [],
    approval_required: objectValue(value, 'approval_required') === true,
    existing_integrations: Array.isArray(existingIntegrations) ? existingIntegrations : [],
    attached_integrations: Array.isArray(attachedIntegrations) ? attachedIntegrations : [],
    provider_routes: Array.isArray(providerRoutes) ? providerRoutes : [],
    provider_paths: Array.isArray(providerPaths) ? providerPaths : [],
    recommended_route: recommendedRoute,
    recommended_route_reason: String(objectValue(value, 'recommended_route_reason') || ''),
  };
};

const normalizeProviderRoute = (value: unknown) => {
  if (!value || typeof value !== 'object') {
    return null;
  }
  const providerAction = objectValue(value, 'provider_action');
  return {
    provider: String(objectValue(value, 'provider') || ''),
    label: String(objectValue(value, 'label') || ''),
    state: String(objectValue(value, 'state') || ''),
    status: String(objectValue(value, 'status') || ''),
    role: String(objectValue(value, 'role') || ''),
    kind: String(objectValue(value, 'kind') || ''),
    connect_mode: String(objectValue(value, 'connect_mode') || ''),
    primary_cta: String(objectValue(value, 'primary_cta') || ''),
    provider_action: providerAction && typeof providerAction === 'object' ? {
      kind: String(objectValue(providerAction, 'kind') || ''),
      available: objectValue(providerAction, 'available') === true,
      ui_target: String(objectValue(providerAction, 'ui_target') || ''),
      label: String(objectValue(providerAction, 'label') || ''),
      description: String(objectValue(providerAction, 'description') || ''),
      role: String(objectValue(providerAction, 'role') || ''),
    } : undefined,
  };
};

const formatPreflightBlock = (preflight?: AgentIntegrationPreflight | null) => {
  const missing = Array.isArray(preflight?.missing) ? preflight.missing : [];
  if (!missing.length) {
    return '';
  }
  const items = missing
    .map((item) => {
      const label = humanizeMeta(item.provider || item.key || 'integration');
      const config = item.missing_config?.length ? ` (${item.missing_config.join(', ')})` : '';
      return `${label}${config}`;
    })
    .join(', ');
  const needsOnlyConfig = missing.every((item) => item.status === 'needs_config' || item.resolution?.includes('missing_config'));
  if (needsOnlyConfig) {
    return `Перед запуском нужно заполнить настройки подключений: ${items}.`;
  }
  return `Перед запуском нужно подключить или настроить: ${items}.`;
};

const connectorLabel = (provider?: string) => ({
  google_sheets: 'Google Sheets',
  telegram: 'Telegram',
  maton: 'Maton.ai',
  localos_finance: 'Финансы LocalOS',
  composio: 'Composio',
}[provider || ''] || humanizeMeta(provider || 'подключение'));

const autoSelectBuilderConnectionBindings = (preview?: AgentBuilderPreview | null): Record<string, string> => {
  const items = preview?.connection_summary?.items || [];
  const selected: Record<string, string> = {};
  items.forEach((item) => {
    const key = item.key || '';
    const connections = item.connections || [];
    const integrationId = connections.length === 1 ? connections[0]?.id || '' : '';
    if (key && integrationId) {
      selected[key] = integrationId;
    }
  });
  return selected;
};

const autoSelectBuilderProviderRoutes = (_preview?: AgentBuilderPreview | null): Record<string, string> => {
  return {};
};

const builderRouteIsUsable = (route?: AgentProviderRoute | null): boolean => {
  const provider = String(route?.provider || '').trim();
  const state = String(route?.state || route?.status || '').trim();
  return Boolean(provider && ['available', 'connected', 'manual'].includes(state) && route?.provider_action?.available !== false);
};

const builderRequiredProviderRouteKeys = (preview?: AgentBuilderPreview | null): string[] => {
  const keys = new Set<string>();
  const inspect = (key?: string, route?: AgentProviderRoute | null, routes?: AgentProviderRoute[]) => {
    const bindingKey = String(key || '').trim();
    if (!bindingKey) {
      return;
    }
    const candidates = [route, ...(routes || [])];
    if (candidates.some((candidate) => builderRouteIsUsable(candidate))) {
      keys.add(bindingKey);
    }
  };
  (preview?.connection_readiness?.services || []).forEach((service) => {
    inspect(service.key, service.recommended_route || null, undefined);
  });
  (preview?.connection_plan?.items || []).forEach((item) => {
    inspect(item.key, item.recommended_route || null, item.provider_routes || []);
  });
  return Array.from(keys);
};

const bindingResolutionLabel = (binding: AgentIntegrationBindingStatus) => ({
  native_localos: 'внутри LocalOS',
  agent_integration: 'подключение бизнеса',
  blueprint_metadata: 'настройка агента',
  provider_route_openclaw: 'OpenClaw boundary',
  provider_route_maton: 'Maton.ai bridge',
  provider_route_manual: 'ручной режим',
  provider_route_openclaw_boundary: 'OpenClaw boundary',
  provider_route_maton_external_account: 'Maton.ai bridge',
  compiled_default: 'настройка workflow',
  input_payload: 'данные запуска',
  missing_integration: 'нужен доступ',
}[binding.resolution || ''] || humanizeMeta(binding.resolution || binding.provider));

const bindingActionHint = (binding: AgentIntegrationBindingStatus) => {
  if (binding.status === 'connected' || binding.status === 'ready') {
    return `${connectorLabel(binding.provider)} готово: ${bindingResolutionLabel(binding)}.`;
  }
  if (binding.provider === 'google_sheets') {
    return 'Выберите существующий Google-доступ или укажите таблицу и лист ниже.';
  }
  if (binding.provider === 'telegram') {
    return 'Выберите режим бота ниже, чтобы агент мог принимать события Telegram.';
  }
  if (binding.provider === 'maton') {
    return 'Используйте сохранённый Maton.ai доступ бизнеса или добавьте ключ в интеграциях.';
  }
  if (binding.provider === 'composio') {
    return 'Composio будет доступен как OAuth-provider позже; пока используйте ручной или native путь.';
  }
  return 'Подключите источник или оставьте агент в draft-only режиме.';
};

const connectionResourceFacts = (provider?: string, config?: Record<string, unknown> | null): string[] => {
  const data = config || {};
  if (!Object.keys(data).length) {
    return [];
  }
  if (provider === 'google_sheets') {
    return [
      String(data.spreadsheet_id || data.spreadsheet_url || '').trim() ? `таблица: ${String(data.spreadsheet_id || data.spreadsheet_url).trim()}` : '',
      String(data.sheet_name || '').trim() ? `лист: ${String(data.sheet_name).trim()}` : '',
      String(data.gid || '').trim() ? `gid: ${String(data.gid).trim()}` : '',
    ].filter(Boolean);
  }
  if (provider === 'telegram') {
    return [
      String(data.telegram_target || data.chat_id || '').trim() ? `канал: ${String(data.telegram_target || data.chat_id).trim()}` : '',
      String(data.target_type || '').trim() ? humanizeMeta(String(data.target_type).trim()) : '',
    ].filter(Boolean);
  }
  if (provider === 'maton') {
    return [
      String(data.channel || '').trim() ? `канал: ${String(data.channel).trim()}` : '',
      String(data.auth_ref || '').trim() ? 'ключ выбран' : '',
    ].filter(Boolean);
  }
  return Object.entries(data)
    .slice(0, 3)
    .map(([key, value]) => String(value || '').trim() ? `${humanizeMeta(key)}: ${String(value).trim()}` : '')
    .filter(Boolean);
};

const isReadyConnectionAction = (action?: string) => action === 'ready' || action === 'native_ready';

const buildAgentConnectionDecision = (
  connectionPlan: AgentConnectionPlan | null,
  bindingStatus: AgentIntegrationBindingStatus[],
  canPreviewRun: boolean,
): AgentConnectionDecision => {
  const planItems = Array.isArray(connectionPlan?.items) ? connectionPlan.items : [];
  const nextPlanItem = planItems.find((item) => !isReadyConnectionAction(item.action));
  if (nextPlanItem) {
    const provider = connectorLabel(nextPlanItem.provider);
    const routes = nextPlanItem.provider_routes || [];
    const route = routes.find((item) => item.state === 'available') || routes[0];
    const routeAction = route?.primary_cta || providerRouteLabel(route?.state || route?.status || '');
    const title = nextPlanItem.action === 'choose_existing'
      ? `Выберите подключение ${provider}`
      : nextPlanItem.action === 'complete_config'
      ? `Заполните настройки ${provider}`
      : `Подключите ${provider}`;
    return {
      tone: nextPlanItem.action === 'choose_existing' ? 'choice' : 'needs_action',
      title,
      description: nextPlanItem.route_summary || nextPlanItem.explanation || `${routeAction}. После этого LocalOS разрешит preview run.`,
      action: 'configure',
      cta: nextPlanItem.primary_label || routeAction || 'Настроить доступ',
      bindingKey: nextPlanItem.key || '',
    };
  }
  const nextBinding = bindingStatus.find((binding) => binding.status !== 'connected' && binding.status !== 'ready');
  if (nextBinding) {
    return {
      tone: 'needs_action',
      title: `Настройте ${connectorLabel(nextBinding.provider)}`,
      description: bindingActionHint(nextBinding),
      action: 'configure',
      cta: 'Открыть настройку',
      bindingKey: nextBinding.key || '',
    };
  }
  if (canPreviewRun) {
    return {
      tone: 'ready',
      title: 'Подключения готовы',
      description: 'Запустите safe preview run: LocalOS проверит preflight, limits и approvals без внешней отправки.',
      action: 'preview',
      cta: 'Проверить на примере',
    };
  }
  return {
    tone: 'pending',
    title: 'Проверьте подключения',
    description: 'LocalOS покажет следующий шаг после загрузки connection plan.',
    action: 'none',
    cta: '',
  };
};

const buildBuilderCreationDecision = ({
  preview,
  questions,
  missingConnectionChoices,
  missingProviderRouteKeys,
  missingProviderRouteConfirmation,
  canCreateDraft,
  createDraftLabel,
}: {
  preview: AgentBuilderPreview | null;
  questions: AgentBuilderQuestion[];
  missingConnectionChoices: Array<AgentConnectionSummary['items'] extends Array<infer Item> ? Item : never>;
  missingProviderRouteKeys: string[];
  missingProviderRouteConfirmation: boolean;
  canCreateDraft: boolean;
  createDraftLabel: string;
}): AgentConnectionDecision => {
  const forbidden = preview?.connection_summary?.forbidden || [];
  const unsupported = preview?.connection_summary?.unsupported || [];
  if (forbidden.length || unsupported.length) {
    const reason = forbidden[0]?.reason || unsupported[0]?.reason || 'Такой provider path не разрешён LocalOS policy envelope.';
    return {
      tone: 'blocked',
      title: 'Такого агента нельзя создать',
      description: reason,
      action: 'none',
      cta: '',
    };
  }
  const blockingQuestions = builderBlockingQuestions(questions);
  if (blockingQuestions.length) {
    return {
      tone: 'needs_action',
      title: 'Ответьте на уточнение',
      description: blockingQuestions[0]?.question || 'LocalOS/OpenClaw нужно больше деталей, чтобы скомпилировать workflow без догадок.',
      action: 'answer',
      cta: 'Отправить ответ',
    };
  }
  if (missingConnectionChoices.length) {
    const title = missingConnectionChoices[0]?.title || connectorLabel(missingConnectionChoices[0]?.provider);
    return {
      tone: 'choice',
      title: `Выберите подключение ${title}`,
      description: 'У бизнеса уже есть несколько подходящих коннектов. LocalOS должен явно привязать один из них к compiled workflow.',
      action: 'choose',
      cta: 'Выбрать ниже',
      bindingKey: missingConnectionChoices[0]?.key || '',
    };
  }
  if (missingProviderRouteKeys.length) {
    return {
      tone: 'choice',
      title: 'Выберите маршруты выполнения',
      description: `Для compiled workflow нужно явно выбрать route: ${missingProviderRouteKeys.join(', ')}.`,
      action: 'choose',
      cta: 'Выбрать ниже',
      bindingKey: missingProviderRouteKeys[0] || '',
    };
  }
  if (missingProviderRouteConfirmation) {
    return {
      tone: 'choice',
      title: 'Подтвердите маршруты выполнения',
      description: 'LocalOS зафиксирует выбранные routes в версии агента и будет проверять их через preflight, limits, audit и approvals.',
      action: 'choose',
      cta: 'Подтвердить ниже',
    };
  }
  if (canCreateDraft) {
    return {
      tone: preview?.setup_flow?.post_create_status === 'ready_for_preview' ? 'ready' : 'choice',
      title: preview?.setup_flow?.post_create_status === 'ready_for_preview'
        ? 'Можно создать draft и открыть preview'
        : 'Можно создать draft и подключить сервисы',
      description: preview?.setup_flow?.post_create_description || 'LocalOS сохранит compiled workflow candidate и откроет следующий безопасный шаг.',
      action: 'create',
      cta: createDraftLabel,
    };
  }
  return {
    tone: 'pending',
    title: preview?.setup_flow?.next_step_title || 'Завершите настройку',
    description: preview?.setup_flow?.next_step_description || 'LocalOS покажет следующий шаг после уточнения задачи и проверки provider paths.',
    action: 'none',
    cta: '',
  };
};

const builderBlockingQuestions = (questions: AgentBuilderQuestion[]) => questions.filter((question) => {
  const reason = String(question.reason || '').trim();
  const key = String(question.key || '').trim();
  if (['connection_resolver', 'binding_config_needed', 'required_connection_missing', 'required_connection_missing_config', 'multiple_connections_available'].includes(reason)) {
    return false;
  }
  if (key.startsWith('connect_') || key.startsWith('choose_')) {
    return false;
  }
  return true;
});

const activationBlockerText = (gate?: AgentActivationGate) => {
  const humanBlockers = gate?.human_blockers || [];
  const blockers = gate?.blockers || [];
  const labels = [
    ...humanBlockers.map((item) => item.message || item.title || connectorLabel(item.provider)),
    ...blockers.map((item) => item.message || connectorLabel(item.provider)),
  ].map((item) => item.trim()).filter(Boolean);
  return labels.slice(0, 3).join(', ');
};

const buildActivationGateDecision = (gate?: AgentActivationGate): AgentConnectionDecision => {
  if (!gate) {
    return {
      tone: 'pending',
      title: 'Activation gate ещё не проверен',
      description: 'Создайте версию и запустите safe preview, чтобы LocalOS понял, можно ли включать агента.',
      action: 'none',
      cta: '',
    };
  }
  if (gate.can_activate) {
    return {
      tone: 'ready',
      title: 'Версию можно активировать',
      description: gate.summary || 'Safe preview, preflight, limits и compiled workflow прошли проверку. Внешние действия останутся за approval gate.',
      action: 'activate',
      cta: gate.primary_action_label || 'Активировать версию',
    };
  }
  if (gate.next_step === 'connect_required_integrations') {
    return {
      tone: 'needs_action',
      title: 'Нужно подключить сервисы',
      description: gate.summary || activationBlockerText(gate) || 'LocalOS понял нужные подключения, но без них нельзя пройти preview и активацию.',
      action: 'connections',
      cta: gate.primary_action_label || 'Открыть подключения',
      bindingKey: gate.next_binding_key || '',
    };
  }
  if (gate.next_step === 'fix_compiled_workflow') {
    return {
      tone: 'blocked',
      title: 'Compiled workflow требует правки',
      description: gate.summary || activationBlockerText(gate) || 'Логика агента не прошла проверку. Исправьте версию перед запуском.',
      action: 'logic',
      cta: gate.primary_action_label || 'Открыть логику',
    };
  }
  if (gate.next_step === 'create_version') {
    return {
      tone: 'needs_action',
      title: 'Нужно создать версию',
      description: gate.summary || 'У агента ещё нет проверенной версии workflow.',
      action: 'logic',
      cta: gate.primary_action_label || 'Создать версию',
    };
  }
  if (gate.next_step === 'run_preview') {
    return {
      tone: 'choice',
      title: 'Нужно запустить safe preview',
      description: gate.preview_run_status?.message || gate.summary || 'Перед активацией LocalOS должен выполнить preview без внешних side effects.',
      action: 'preview',
      cta: gate.primary_action_label || 'Запустить preview',
    };
  }
  if (gate.next_step === 'review_approvals') {
    return {
      tone: 'needs_action',
      title: 'Нужно проверить approval',
      description: gate.summary || activationBlockerText(gate) || 'Есть решение человека, которое влияет на готовность агента.',
      action: 'results',
      cta: gate.primary_action_label || 'Открыть approvals',
    };
  }
  return {
    tone: 'pending',
    title: 'Активация пока недоступна',
    description: gate.summary || activationBlockerText(gate) || 'Проверьте логику, подключения и safe preview агента.',
    action: 'none',
    cta: '',
  };
};

const buildActivationPathSteps = (gate?: AgentActivationGate): AgentActivationPathStep[] => {
  const nextStep = gate?.next_step || '';
  const compiledReady = gate?.compiled_validation?.ready === true;
  const policyReady = gate?.approval_policy_status?.ready === true;
  const connectionsReady = gate?.preflight?.ready === true;
  const previewReady = gate?.preview_run_status?.ready === true;
  const canActivate = gate?.can_activate === true;
  return [
    {
      key: 'compiled',
      label: 'Логика',
      detail: compiledReady ? 'workflow проверен' : 'нужно проверить',
      status: compiledReady ? 'done' : nextStep === 'fix_compiled_workflow' || nextStep === 'create_version' ? 'current' : 'pending',
    },
    {
      key: 'policy',
      label: 'Policy',
      detail: policyReady ? 'approvals и limits готовы' : 'нужен human gate',
      status: policyReady ? 'done' : nextStep === 'fix_compiled_workflow' ? 'current' : 'pending',
    },
    {
      key: 'connections',
      label: 'Доступы',
      detail: connectionsReady ? 'готовы' : 'нужно подключить',
      status: connectionsReady ? 'done' : nextStep === 'connect_required_integrations' ? 'current' : 'pending',
    },
    {
      key: 'preview',
      label: 'Preview',
      detail: previewReady ? 'безопасно пройден' : 'нужен запуск',
      status: previewReady ? 'done' : nextStep === 'run_preview' ? 'current' : 'pending',
    },
    {
      key: 'activate',
      label: 'Активация',
      detail: canActivate ? 'можно включить' : 'после gate',
      status: canActivate ? 'current' : 'pending',
    },
  ];
};

const getVersionNumber = (version: Record<string, unknown> | undefined) => {
  const value = version?.version_number;
  return typeof value === 'number' ? value : null;
};

const getLatestVersionNumber = (blueprint: AgentBlueprint, details?: AgentBlueprintDetails | null) => {
  if (typeof blueprint.latest_version_number === 'number') {
    return blueprint.latest_version_number;
  }
  const versionNumbers: number[] = [];
  (details?.versions || []).forEach((version) => {
    const versionNumber = getVersionNumber(version);
    if (typeof versionNumber === 'number') {
      versionNumbers.push(versionNumber);
    }
  });
  return versionNumbers.length ? Math.max(...versionNumbers) : null;
};

const getActiveVersionNumber = (blueprint: AgentBlueprint, details?: AgentBlueprintDetails | null) => {
  if (typeof details?.active_version_number === 'number' && details.active_version_number > 0) {
    return details.active_version_number;
  }
  if (typeof blueprint.active_version_number === 'number' && blueprint.active_version_number > 0) {
    return blueprint.active_version_number;
  }
  const active = (details?.versions || []).find((version) => version.is_active === true);
  const activeNumber = getVersionNumber(active);
  if (typeof activeNumber === 'number') {
    return activeNumber;
  }
  return getLatestVersionNumber(blueprint, details);
};

const getActiveVersionId = (blueprint: AgentBlueprint, details?: AgentBlueprintDetails | null) => {
  if (typeof details?.active_version_id === 'string' && details.active_version_id) {
    return details.active_version_id;
  }
  if (typeof blueprint.active_version_id === 'string' && blueprint.active_version_id) {
    return blueprint.active_version_id;
  }
  const active = (details?.versions || []).find((version) => version.is_active === true);
  return typeof active?.id === 'string' ? active.id : '';
};

const getAgentVoiceName = (blueprint: AgentBlueprint, details?: AgentBlueprintDetails | null) => {
  const detailVoice = details?.active_version?.voice;
  if (typeof detailVoice === 'object' && detailVoice !== null) {
    const name = Reflect.get(detailVoice, 'name');
    if (typeof name === 'string') {
      return name;
    }
  }
  const voice = blueprint.voice || blueprint.persona || blueprint.product_agent?.voice || blueprint.product_agent?.persona;
  return voice?.name || '';
};

const runStatusFilters = [
  { value: 'all', label: 'Все' },
  { value: 'running', label: 'В работе' },
  { value: 'waiting_approval', label: 'Ждёт решения' },
  { value: 'completed', label: 'Готово' },
  { value: 'failed', label: 'Ошибка' },
];

const learningTriggerOptions = [
  { value: 'manual_edit', label: 'Ручная правка текста' },
  { value: 'approval_rejected', label: 'Отклонение' },
  { value: 'bad_outcome', label: 'Плохой результат' },
  { value: 'runtime_error', label: 'Ошибка' },
  { value: 'manual_feedback', label: 'Комментарий' },
];

const agentPromptExamples = [
  'Напомни клиентам о записи и подготовь пакетное предложение',
  'Подготовь письмо клиентам по шаблону',
  'Обработай документ и найди риски',
  'Найди клиентов и покажи черновики сообщений',
  'Отвечай на отзывы в моём стиле',
];

const agentScenarios: AgentBuilderScenario[] = [
  {
    category: 'communications',
    title: 'Коммуникации',
    description: 'Напоминания, follow-up, возврат клиентов, пакетные предложения и ответы на входящие.',
    prompt: 'Сделай агента, который напоминает клиентам о записи и сообщает про пакетное предложение',
    dataSources: 'записи, услуги, пакеты, профиль бизнеса, история коммуникаций',
    extraction: 'триггер, аудитория, согласие, релевантная услуга, канал и лимиты частоты',
    processing: 'подготовить черновики, проверить согласие, поставить отправку только после ручного подтверждения',
    output: 'черновики, отчёт доставки и журнал outcomes',
    manualControl: 'первый запуск, шаблон и каждая массовая отправка подтверждаются человеком',
    icon: MessageSquareText,
  },
  {
    category: 'documents',
    title: 'Документы',
    description: 'Извлечь поля, проверить правила и собрать результат по образцу.',
    prompt: 'Обработай документ, найди риски и подготовь краткий результат для проверки',
    dataSources: 'файл документа, ручной контекст, профиль бизнеса',
    extraction: 'ключевые условия, сроки, суммы, ответственность, спорные места',
    processing: 'не придумывать факты, ссылаться только на добавленный документ, отдельно показывать риски',
    output: 'краткий отчёт: summary, риски, что уточнить, черновик письма при необходимости',
    manualControl: 'перед использованием результата и перед любым внешним действием',
    icon: FileText,
  },
  {
    category: 'email',
    title: 'Письма',
    description: 'Подготовить черновик, показать на подтверждение и сохранить результат.',
    prompt: 'Подготовь письмо клиенту по моему контексту и шаблону',
    dataSources: 'ручной контекст, шаблон письма, профиль бизнеса',
    extraction: 'цель письма, адресат, факты, ограничения по тону',
    processing: 'писать коротко, без неподтверждённых обещаний, сохранять стиль бизнеса',
    output: 'тема письма и готовый черновик',
    manualControl: 'письмо только как черновик, отправка вручную после проверки',
    icon: Mail,
  },
  {
    category: 'tables',
    title: 'Таблицы',
    description: 'Разобрать строки, найти исключения и подготовить отчёт.',
    prompt: 'Разбери таблицу, найди исключения и собери отчёт',
    dataSources: 'CSV/XLSX, ручной контекст',
    extraction: 'строки, пустые поля, аномалии, суммы и статусы',
    processing: 'показывать только проверяемые исключения, группировать по причине',
    output: 'отчёт по исключениям и список строк для проверки',
    manualControl: 'перед изменением данных или отправкой отчёта',
    icon: FileCheck2,
  },
  {
    category: 'outreach',
    title: 'Поиск клиентов',
    description: 'Найти лидов, собрать shortlist и подготовить сообщения.',
    prompt: 'Найди клиентов и покажи черновики сообщений перед отправкой',
    dataSources: 'prospectingleads, профиль бизнеса, услуги',
    extraction: 'подходящие лиды, канал связи, причина релевантности',
    processing: 'не отправлять без ручного подтверждения, ограничить объём, сохранять источник лида',
    output: 'shortlist и черновики сообщений',
    manualControl: 'shortlist, черновики и очередь отправки подтверждаются вручную',
    icon: Users,
  },
  {
    category: 'reviews',
    title: 'Отзывы',
    description: 'Подготовить ответы в стиле бизнеса и ждать ручного подтверждения.',
    prompt: 'Подготовь ответы на отзывы в стиле моего бизнеса',
    dataSources: 'отзывы, профиль бизнеса, услуги',
    extraction: 'тон отзыва, проблема, услуга, факты для ответа',
    processing: 'не спорить, не обещать невозможное, негативные отзывы помечать отдельно',
    output: 'черновики ответов на отзывы',
    manualControl: 'публикация только вручную после проверки',
    icon: Star,
  },
  {
    category: 'partnerships',
    title: 'Партнёрства',
    description: 'Найти подходящие компании и подготовить предложение.',
    prompt: 'Подготовь партнёрское предложение для локальных компаний',
    dataSources: 'prospectingleads, услуги, профиль бизнеса',
    extraction: 'тип партнёра, пересечение аудитории, повод для предложения',
    processing: 'не отправлять наружу, сначала показать предложение',
    output: 'короткое партнёрское предложение и список адресатов',
    manualControl: 'перед отправкой и публикацией',
    icon: Sparkles,
  },
  {
    category: 'services',
    title: 'Услуги',
    description: 'Понять текущие услуги и предложить улучшения без автоприменения.',
    prompt: 'Оптимизируй описание услуг и покажи предложения перед применением',
    dataSources: 'услуги, профиль бизнеса, отзывы',
    extraction: 'названия услуг, цены, длительность, слабые описания',
    processing: 'не менять услуги без отдельного подтверждения',
    output: 'предложения по улучшению услуг',
    manualControl: 'применение изменений только вручную',
    icon: Wrench,
  },
  {
    category: 'booking',
    title: 'Бронирование',
    description: 'Собрать правила записи и подготовить сценарий общения.',
    prompt: 'Помоги настроить агента записи: вопросы клиенту, правила и ограничения',
    dataSources: 'профиль бизнеса, услуги, ручной контекст',
    extraction: 'правила записи, ограничения, обязательные вопросы, доступные услуги',
    processing: 'не подтверждать запись без понятных правил и ручного контроля',
    output: 'сценарий записи и список недостающих правил',
    manualControl: 'сложные случаи и изменения расписания подтверждаются человеком',
    icon: MessageSquareText,
  },
];

const statusTone: Record<string, string> = {
  active: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  connected: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  ready: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  completed: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  running: 'bg-sky-50 text-sky-700 ring-sky-200',
  waiting_approval: 'bg-amber-50 text-amber-700 ring-amber-200',
  needs_approval: 'bg-amber-50 text-amber-700 ring-amber-200',
  failed: 'bg-rose-50 text-rose-700 ring-rose-200',
  error: 'bg-rose-50 text-rose-700 ring-rose-200',
  rejected: 'bg-slate-100 text-slate-700 ring-slate-200',
  draft: 'bg-slate-100 text-slate-700 ring-slate-200',
  paused: 'bg-slate-100 text-slate-700 ring-slate-200',
  queued_for_dispatch: 'bg-amber-50 text-amber-700 ring-amber-200',
  pending: 'bg-amber-50 text-amber-700 ring-amber-200',
  needs_connection: 'bg-amber-50 text-amber-700 ring-amber-200',
  needs_choice: 'bg-amber-50 text-amber-700 ring-amber-200',
  needs_clarification: 'bg-amber-50 text-amber-700 ring-amber-200',
  blocked: 'bg-rose-50 text-rose-700 ring-rose-200',
};

const statusLabels: Record<string, string> = {
  active: 'Включён',
  connected: 'Готово',
  ready: 'Готово',
  completed: 'Готово',
  running: 'В работе',
  waiting_approval: 'Ждёт решения',
  needs_approval: 'Нужно решение',
  failed: 'Ошибка',
  error: 'Ошибка',
  rejected: 'Отклонён',
  draft: 'Черновик',
  paused: 'Пауза',
  queued_for_dispatch: 'В очереди',
  queued_not_dispatched: 'В очереди',
  generated: 'Подготовлено',
  approved: 'Подтверждено',
  pending: 'Ожидает',
  needs_connection: 'Подключить',
  needs_choice: 'Выбрать',
  needs_clarification: 'Уточнить',
  blocked: 'Блокер',
};

const stepLabels: Record<string, string> = {
  source_leads: 'Найти потенциальных клиентов',
  shortlist: 'Сформировать список',
  approve_shortlist: 'Подтвердить список',
  draft_messages: 'Подготовить сообщения',
  approve_drafts: 'Подтвердить тексты',
  send_limited_batch: 'Поставить в очередь',
  record_outcomes: 'Сохранить ответы',
};

const metaLabels: Record<string, string> = {
  artifact: 'результат',
  approval: 'требуется подтверждение',
  capability: 'действие через безопасный контур',
  input: 'входные данные',
  output: 'результат',
  extraction: 'извлечение',
  final: 'принятый итог',
  sourcing: 'поиск лидов',
  shortlist: 'список клиентов',
  drafts: 'черновики сообщений',
  queue: 'очередь',
  business_profile: 'профиль бизнеса',
  appointments: 'записи',
  packages: 'пакеты',
  services: 'услуги',
  reviews: 'отзывы',
  external_reviews: 'отзывы',
  prospectingleads: 'лиды',
  outreach_drafts: 'черновики outreach',
  uploaded_documents: 'документы',
  uploaded_tables: 'таблицы',
  manual_context: 'ручной контекст',
  goal: 'цель',
  inputs_schema: 'входные данные',
  steps: 'шаги',
  persona_agent_id: 'голос агента',
  capability_allowlist: 'разрешённые действия',
  approval_policy: 'ручной контроль',
  output_schema: 'формат результата',
  final_output: 'финальный результат',
  external_delivery: 'внешняя отправка',
  title: 'название',
  summary: 'кратко',
  risks: 'риски',
  subject: 'тема',
  body: 'текст',
  format: 'формат',
  source_name: 'источник',
  raw: 'данные',
  missing_information: 'что уточнить',
  rules_applied: 'правила',
  feedback_notes: 'правки',
  communications: 'коммуникации',
  documents: 'документы',
  tables: 'таблицы',
  outreach: 'outreach',
  services_optimize: 'услуги',
  telegram: 'Telegram',
  google_sheets: 'Google Sheets',
  google_sheets_read: 'чтение Google Sheets',
  google_sheets_append: 'запись в Google Sheets',
  localos_finance: 'финансы LocalOS',
  maton: 'Maton.ai',
  composio: 'Composio',
  trigger_boundary: 'граница запуска',
  approved_executor: 'исполнитель после подтверждения',
  approved_delivery_bridge: 'доставка после подтверждения',
  approved_localos_write: 'запись в LocalOS после подтверждения',
  'telegram.message.received': 'новое сообщение в Telegram',
  'google_sheets.append': 'запись строки в Google Sheets',
  'outreach.send_batch': 'отправка согласованной пачки',
  'reviews.reply.draft': 'черновик ответа на отзыв',
  'reviews.reply.publish_request': 'запрос на публикацию ответа',
  'services.optimize': 'оптимизация услуг',
  'news.generate': 'подготовка новости',
  'appointments.read': 'чтение записей',
  'appointments.create_request': 'запрос на создание записи',
  'communications.draft': 'черновик сообщения',
  'communications.send_reminder': 'напоминание клиенту',
  'communications.send_offer': 'предложение клиенту',
  'support.export': 'выгрузка для поддержки',
  'billing.reserve': 'резерв токенов',
  'billing.settle': 'списание токенов',
  not_applicable: 'не применимо',
};

const resultFieldLabels: Record<string, string> = {
  title: 'Название результата',
  summary: 'Краткий вывод',
  risks: 'Риски',
  facts: 'Факты',
  fields: 'Поля',
  next_questions: 'Что уточнить',
  subject: 'Тема письма',
  body: 'Текст письма',
  checklist: 'Проверить перед использованием',
  exceptions: 'Исключения',
  rows_to_review: 'Строки к проверке',
  recommendations: 'Рекомендации',
  reply_drafts: 'Черновики ответов',
  manual_review_reasons: 'Почему нужен ручной контроль',
  rules_applied: 'Применённые правила',
  provenance: 'Источники',
  delivery_state: 'Отправка',
  publish_state: 'Публикация',
};

const outreachProgressStages = [
  { kind: 'sourcing', title: 'Нашёл лидов', detailLabel: 'Найдено лидов', icon: Search },
  { kind: 'shortlist', title: 'Собрал shortlist', detailLabel: 'Лидов в shortlist', icon: Users },
  { kind: 'drafts', title: 'Подготовил черновики', detailLabel: 'Черновиков', icon: MessageSquareText },
  { kind: 'queue', title: 'Поставил в очередь', detailLabel: 'В очереди', icon: Send },
];

const genericRunStages = [
  { kind: 'input', title: 'Входные данные', description: 'Что агент получил на вход', icon: Database },
  { kind: 'extraction', title: 'Что понял', description: 'Что извлёк из источников', icon: Search },
  { kind: 'output', title: 'Результат', description: 'Что подготовил для проверки', icon: FileCheck2 },
  { kind: 'approval', title: 'Ручной контроль', description: 'Что требует решения человека', icon: ShieldCheck },
];

const humanizeStatus = (status: string) => statusLabels[status] || status;
const humanizeStep = (step: string) => stepLabels[step] || step;
const humanizeMeta = (meta: string) => metaLabels[meta] || meta;
const humanizeCategory = (category?: string) => ({
  communications: 'Коммуникации',
  outreach: 'Поиск клиентов',
  documents: 'Документы',
  email: 'Письма',
  tables: 'Таблицы',
  reviews: 'Отзывы',
  partnerships: 'Партнёрства',
  services: 'Услуги',
  booking: 'Бронирование',
  custom: 'Кастомная задача',
}[category || 'custom'] || category || 'Кастомная задача');

const explainApproval = (approval?: AgentApproval | null) => {
  const approvalType = approval?.approval_type || '';
  const payload = approval?.payload_json || {};
  const draftCount = Array.isArray(payload.draft_ids) ? payload.draft_ids.length : typeof payload.count === 'number' ? payload.count : 0;
  if (approvalType === 'external_delivery' || approvalType === 'send_batch') {
    return draftCount
      ? `Агент подготовил ${draftCount} внешних отправок. Нужно подтвердить batch перед любым сообщением клиентам.`
      : 'Агент дошёл до внешнего действия. Нужен human gate перед отправкой.';
  }
  if (approvalType === 'final_output') {
    return 'Агент подготовил результат, но не использует его дальше без проверки человеком.';
  }
  if (approvalType === 'shortlist') {
    return 'Агент собрал shortlist. Нужно проверить, кого брать в работу дальше.';
  }
  if (approvalType === 'drafts') {
    return 'Агент подготовил черновики. Нужно проверить текст, тон и ограничения перед следующим шагом.';
  }
  return 'Агент остановился на безопасной границе и ждёт решение человека.';
};

const getAgentListStatus = (blueprint: AgentBlueprint) => {
  if (Number(blueprint.pending_approvals_count || 0) > 0 || blueprint.last_run_status === 'waiting_approval') {
    return 'needs_approval';
  }
  if (blueprint.last_run_status === 'failed' || blueprint.status === 'error') {
    return 'error';
  }
  return blueprint.status || 'draft';
};

const formatShortDate = (value?: string | null) => {
  if (!value) {
    return '';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
};

const formatLastRun = (blueprint: AgentBlueprint) => {
  if (!blueprint.last_run_id) {
    return 'запусков ещё не было';
  }
  const date = formatShortDate(blueprint.last_run_started_at || blueprint.last_run_completed_at);
  return `${humanizeStatus(blueprint.last_run_status || 'running')}${date ? ` · ${date}` : ''}`;
};

const humanizeSourceType = (sourceType?: string) => ({
  text: 'Текст',
  file: 'Файл',
  internal: 'Источник LocalOS',
}[sourceType || ''] || 'Источник');

const humanizeSourceState = (state?: string) => ({
  ready: 'готово',
  available: 'доступно',
  empty: 'нет данных',
  unsupported_file_type: 'неподдерживаемый файл',
  needs_text_export: 'нужно извлечь текст',
  extraction_failed: 'не удалось прочитать',
}[state || ''] || state || 'готово');

const formatSourceSize = (chars?: number, bytes?: number) => {
  if (typeof chars === 'number' && chars > 0) {
    return `${chars} знаков`;
  }
  if (typeof bytes === 'number' && bytes > 0) {
    return bytes >= 1024 ? `${Math.round(bytes / 1024)} KB` : `${bytes} B`;
  }
  return 'без текста';
};

const StatusBadge = ({ status }: { status: string }) => (
  <span className={cn('inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ring-1', statusTone[status] || 'bg-slate-50 text-slate-600 ring-slate-200')}>
    {humanizeStatus(status)}
  </span>
);

const parseAgentConfig = (business?: DashboardContext['currentBusiness']) => {
  const rawConfig = business?.ai_agents_config;
  if (!rawConfig) {
    return {};
  }
  try {
    const parsed = typeof rawConfig === 'string' ? JSON.parse(rawConfig) : rawConfig;
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      return {};
    }
    const normalized: Record<string, { enabled?: boolean }> = {};
    Object.entries(parsed).forEach(([key, value]) => {
      if (value && typeof value === 'object' && !Array.isArray(value)) {
        const enabledEntry = Object.entries(value).find(([entryKey]) => entryKey === 'enabled');
        normalized[key] = { enabled: Boolean(enabledEntry ? enabledEntry[1] : false) };
      }
    });
    return normalized;
  } catch {
    return {};
  }
};

const uploadAgentSource = async (blueprintId: string, file: File, name: string) => {
  const token = newAuth.getToken();
  if (!token) {
    throw new Error('Authorization required');
  }
  const formData = new FormData();
  formData.append('file', file);
  formData.append('name', name || file.name);
  const response = await fetch(`/api/agent-blueprints/${blueprintId}/sources/upload`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: formData,
  });
  const data = await response.json();
  if (!response.ok || !data.success) {
    const code = String(data.code || data.error_code || '');
    const friendlyMessage = code === 'FILE_TOO_LARGE'
      ? 'Файл слишком большой. Загрузите файл меньшего размера или вставьте текст вручную.'
      : code === 'UNSUPPORTED_FILE_TYPE'
        ? 'Этот тип файла пока не поддерживается. Поддерживаются TXT, CSV, TSV, MD, PDF, DOCX и XLSX.'
        : code === 'EMPTY_FILE'
          ? 'Файл пустой. Добавьте файл с текстом или вставьте контекст вручную.'
          : data.error || 'Не удалось извлечь текст из файла. Попробуйте другой файл или вставьте текст вручную.';
    throw new Error(friendlyMessage);
  }
  return data;
};

export const AgentBlueprintsPage = () => {
  const { currentBusinessId, currentBusiness } = useOutletContext<DashboardContext>();
  const [blueprints, setBlueprints] = useState<AgentBlueprint[]>([]);
  const [selectedBlueprintId, setSelectedBlueprintId] = useState<string | null>(null);
  const [blueprintDetails, setBlueprintDetails] = useState<AgentBlueprintDetails | null>(null);
  const [activeRun, setActiveRun] = useState<AgentRun | null>(null);
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [runStatusFilter, setRunStatusFilter] = useState('all');
  const [runSource, setRunSource] = useState('dashboard');
  const [runCity, setRunCity] = useState('');
  const [runCategory, setRunCategory] = useState('');
  const [runLimit, setRunLimit] = useState('30');
  const [createWizardOpen, setCreateWizardOpen] = useState(false);
  const [createWizardStep, setCreateWizardStep] = useState(0);
  const [workspaceMode, setWorkspaceMode] = useState<AgentWorkspaceMode>('overview');
  const [availablePersonaAgents, setAvailablePersonaAgents] = useState<PersonaAgent[]>([]);
  const [agentPrompt, setAgentPrompt] = useState('');
  const [builderCategory, setBuilderCategory] = useState('documents');
  const [builderDataSources, setBuilderDataSources] = useState('файл документа, ручной контекст, профиль бизнеса');
  const [builderExtractionRules, setBuilderExtractionRules] = useState('ключевые условия, сроки, суммы, ответственность, спорные места');
  const [builderProcessingRules, setBuilderProcessingRules] = useState('не придумывать факты, ссылаться только на добавленные данные, отдельно показывать риски');
  const [builderOutputFormat, setBuilderOutputFormat] = useState('краткий отчёт: summary, риски, что уточнить, черновик письма при необходимости');
  const [builderManualControl, setBuilderManualControl] = useState('перед использованием результата и перед любым внешним действием');
  const [builderSourceName, setBuilderSourceName] = useState('');
  const [builderSourceText, setBuilderSourceText] = useState('');
  const [builderFileSource, setBuilderFileSource] = useState<File | null>(null);
  const [builderInternalSource, setBuilderInternalSource] = useState('business_profile');
  const [dialogBuilderInput, setDialogBuilderInput] = useState('');
  const [dialogBuilderReply, setDialogBuilderReply] = useState('');
  const [dialogBuilderSession, setDialogBuilderSession] = useState<AgentBuilderSession | null>(null);
  const [selectedBuilderConnectionBindings, setSelectedBuilderConnectionBindings] = useState<Record<string, string>>({});
  const [selectedBuilderProviderRoutes, setSelectedBuilderProviderRoutes] = useState<Record<string, string>>({});
  const [acceptedBuilderCompilerPlan, setAcceptedBuilderCompilerPlan] = useState(false);
  const [acceptedBuilderProviderRoutes, setAcceptedBuilderProviderRoutes] = useState(false);
  const [agentReview, setAgentReview] = useState<AgentReview | null>(null);
  const [sourceCatalog, setSourceCatalog] = useState<AgentSourceCatalogItem[]>([]);
  const [setupDataSources, setSetupDataSources] = useState('профиль бизнеса, ручной контекст');
  const [setupExtractionRules, setSetupExtractionRules] = useState('');
  const [setupProcessingRules, setSetupProcessingRules] = useState('');
  const [setupOutputFormat, setSetupOutputFormat] = useState('');
  const [setupManualControl, setSetupManualControl] = useState('Показывать результат перед любым внешним действием');
  const [sourceName, setSourceName] = useState('');
  const [sourceText, setSourceText] = useState('');
  const [internalSource, setInternalSource] = useState('business_profile');
  const [agentIntegrations, setAgentIntegrations] = useState<AgentIntegration[]>([]);
  const [availableAgentIntegrations, setAvailableAgentIntegrations] = useState<AgentIntegration[]>([]);
  const [agentIntegrationCatalog, setAgentIntegrationCatalog] = useState<AgentIntegrationCatalogItem[]>([]);
  const [agentExternalAuthOptions, setAgentExternalAuthOptions] = useState<AgentExternalAuthOption[]>([]);
  const [agentBindingStatus, setAgentBindingStatus] = useState<AgentIntegrationBindingStatus[]>([]);
  const [agentConnectionPlan, setAgentConnectionPlan] = useState<AgentConnectionPlan | null>(null);
  const [selectedConnectionBindingKey, setSelectedConnectionBindingKey] = useState('');
  const [sheetSpreadsheetId, setSheetSpreadsheetId] = useState('');
  const [sheetName, setSheetName] = useState('Sheet1');
  const [sheetAuthRef, setSheetAuthRef] = useState('');
  const [sheetDailyCap, setSheetDailyCap] = useState('50');
  const [telegramBotMode, setTelegramBotMode] = useState('business_bot');
  const [telegramDailyCap, setTelegramDailyCap] = useState('50');
  const [matonAuthRef, setMatonAuthRef] = useState('');
  const [matonChannel, setMatonChannel] = useState('maton_bridge');
  const [matonDailyCap, setMatonDailyCap] = useState('50');
  const [processRowValues, setProcessRowValues] = useState('{{received_at}}, {{telegram_username}}, {{message_text}}');
  const [processPreviewMessage, setProcessPreviewMessage] = useState('Новая заявка: Анна, телефон +7 900 000-00-00, хочет консультацию');
  const [feedbackText, setFeedbackText] = useState('');
  const [feedbackTrigger, setFeedbackTrigger] = useState('manual_edit');
  const [feedbackVersionNotice, setFeedbackVersionNotice] = useState<FeedbackVersionNotice | null>(null);
  const [systemAgentConfig, setSystemAgentConfig] = useState<Record<string, { enabled?: boolean }>>({});
  const [legacyMigrationPlan, setLegacyMigrationPlan] = useState<LegacyMigrationPlan | null>(null);
  const [legacyMigrationNotice, setLegacyMigrationNotice] = useState('');
  const [recentCreatedAgentName, setRecentCreatedAgentName] = useState('');
  const [recentPostCreateHandoff, setRecentPostCreateHandoff] = useState<AgentPostCreateHandoff | null>(null);
  const [showAdvancedAgentTools, setShowAdvancedAgentTools] = useState(false);

  useEffect(() => {
    setSystemAgentConfig(parseAgentConfig(currentBusiness));
  }, [currentBusiness]);

  useEffect(() => {
    let mounted = true;
    const syncUserRole = async () => {
      const cachedUser = newAuth.getCurrentUserSync();
      if (mounted) {
        setShowAdvancedAgentTools(Boolean(cachedUser?.is_superadmin));
      }
      const user = await newAuth.getCurrentUser();
      if (mounted) {
        setShowAdvancedAgentTools(Boolean(user?.is_superadmin));
      }
    };
    void syncUserRole();
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    if (!showAdvancedAgentTools && workspaceMode === 'advanced') {
      setWorkspaceMode('overview');
    }
  }, [showAdvancedAgentTools, workspaceMode]);

  const selectedBlueprint = useMemo(
    () => blueprints.find((item) => item.id === selectedBlueprintId) || blueprints[0] || null,
    [blueprints, selectedBlueprintId],
  );

  const pendingApproval = useMemo(
    () => activeRun?.approvals?.find((item) => item.status === 'pending') || null,
    [activeRun],
  );

  const activeRunPendingApprovals = useMemo(
    () => (activeRun?.approvals || []).filter((item) => item.status === 'pending'),
    [activeRun?.approvals],
  );

  const pendingApprovals = useMemo(
    () => (blueprintDetails?.approval_queue || []).filter((item) => item.status === 'pending'),
    [blueprintDetails?.approval_queue],
  );

  const queuedButNotDispatched = useMemo(() => {
    const artifact = (activeRun?.artifacts || []).find((item) => {
      const payload = item.payload_json || {};
      return payload.dispatch_state === 'queued_not_dispatched' || (
        payload.status === 'queued_for_dispatch' && payload.external_dispatch_performed === false
      );
    });
    if (artifact?.payload_json) {
      return artifact.payload_json;
    }
    const step = (activeRun?.steps || []).find((item) => {
      const output = item.output_json?.orchestrator?.result || item.output_json || {};
      return output.dispatch_state === 'queued_not_dispatched' || (
        output.status === 'queued_for_dispatch' && output.external_dispatch_performed === false
      );
    });
    return step?.output_json?.orchestrator?.result || step?.output_json || null;
  }, [activeRun?.artifacts, activeRun?.steps]);

  const selectedScenario = useMemo(
    () => agentScenarios.find((item) => item.category === builderCategory) || agentScenarios[0],
    [builderCategory],
  );

  const systemAgents = useMemo(() => [
    {
      key: 'booking_agent',
      title: 'Агент записи',
      description: 'Помогает с правилами записи, вопросами клиенту и сценарием общения.',
      icon: Bot,
      enabled: Boolean(systemAgentConfig.booking_agent?.enabled),
    },
    {
      key: 'marketing_agent',
      title: 'Маркетинговый агент',
      description: 'Готовит идеи, тексты и маркетинговые черновики в стиле бизнеса.',
      icon: Zap,
      enabled: Boolean(systemAgentConfig.marketing_agent?.enabled),
    },
  ], [systemAgentConfig]);

  const activeAgentsCount = useMemo(
    () => systemAgents.filter((item) => item.enabled).length + blueprints.filter((item) => getAgentListStatus(item) === 'active').length,
    [blueprints, systemAgents],
  );

  const totalPendingApprovals = useMemo(
    () => blueprints.reduce((sum, item) => sum + Number(item.pending_approvals_count || 0), 0),
    [blueprints],
  );

  const migrationStats = useMemo(() => {
    const legacyAgents = legacyMigrationPlan?.legacy_agents || [];
    const businessFields = legacyMigrationPlan?.business_settings?.fields || {};
    return {
      totalLegacyAgents: legacyAgents.length,
      linkedVoices: legacyAgents.filter((item) => item.action === 'use_as_persona').length,
      needsBlueprint: legacyAgents.filter((item) => item.action === 'create_blueprint_candidate').length,
      archiveCandidates: legacyAgents.filter((item) => item.action === 'archive_candidate').length,
      deprecatedFieldsPresent: Object.values(businessFields).filter((item) => item.present).length,
      legacyWorkflowPresent: legacyAgents.filter((item) => item.legacy_workflow?.present).length,
    };
  }, [legacyMigrationPlan]);

  const applyBuilderScenario = (scenario: AgentBuilderScenario) => {
    setBuilderCategory(scenario.category);
    setAgentPrompt(scenario.prompt);
    setBuilderDataSources(scenario.dataSources);
    setBuilderExtractionRules(scenario.extraction);
    setBuilderProcessingRules(scenario.processing);
    setBuilderOutputFormat(scenario.output);
    setBuilderManualControl(scenario.manualControl);
  };

  const loadBlueprints = useCallback(async () => {
    if (!currentBusinessId) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const response = await api.get('/agent-blueprints', { params: { business_id: currentBusinessId } });
      const items = Array.isArray(response.data?.blueprints) ? response.data.blueprints : [];
      setBlueprints(items);
      if (!selectedBlueprintId && items.length > 0) {
        setSelectedBlueprintId(items[0].id);
      }
    } catch (requestError) {
      console.error(requestError);
      setError('Не удалось загрузить агентов.');
    } finally {
      setLoading(false);
    }
  }, [currentBusinessId, selectedBlueprintId]);

  useEffect(() => {
    void loadBlueprints();
  }, [loadBlueprints]);

  const loadLegacyMigrationPlan = useCallback(async () => {
    if (!currentBusinessId) {
      setLegacyMigrationPlan(null);
      return;
    }
    try {
      const response = await api.get('/agent-blueprints/legacy-migration-plan', { params: { business_id: currentBusinessId } });
      setLegacyMigrationPlan(response.data?.migration_plan || null);
    } catch (requestError) {
      console.error(requestError);
      setLegacyMigrationPlan(null);
    }
  }, [currentBusinessId]);

  useEffect(() => {
    void loadLegacyMigrationPlan();
  }, [loadLegacyMigrationPlan]);

  const loadPersonaAgents = useCallback(async () => {
    if (!currentBusinessId) {
      setAvailablePersonaAgents([]);
      return;
    }
    try {
      const token = newAuth.getToken();
      if (!token) {
        setAvailablePersonaAgents([]);
        return;
      }
      const response = await fetch(`/api/business/${currentBusinessId}/ai-agents/manage`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) {
        setAvailablePersonaAgents([]);
        return;
      }
      const data = await response.json();
      const agents = Array.isArray(data.agents) ? data.agents : [];
      const normalized = agents
        .filter((agent) => agent && typeof agent === 'object')
        .map((agent) => ({
          id: String(agent.id || ''),
          name: typeof agent.name === 'string' ? agent.name : '',
          type: typeof agent.type === 'string' ? agent.type : '',
          description: typeof agent.description === 'string' ? agent.description : '',
          task: typeof agent.task === 'string' ? agent.task : '',
          identity: typeof agent.identity === 'string' ? agent.identity : '',
          is_active: agent.is_active !== false,
        }))
        .filter((agent) => agent.id);
      setAvailablePersonaAgents(normalized);
    } catch (requestError) {
      console.error(requestError);
      setAvailablePersonaAgents([]);
    }
  }, [currentBusinessId]);

  useEffect(() => {
    void loadPersonaAgents();
  }, [loadPersonaAgents]);

  const loadBlueprintDetails = useCallback(async (blueprintId: string) => {
    setError(null);
    try {
      const params = runStatusFilter === 'all' ? {} : { run_status: runStatusFilter };
      const response = await api.get(`/agent-blueprints/${blueprintId}`, { params });
      const details = {
        blueprint: response.data?.blueprint && typeof response.data.blueprint === 'object' ? response.data.blueprint : undefined,
        versions: Array.isArray(response.data?.versions) ? response.data.versions : [],
        runs: Array.isArray(response.data?.runs) ? response.data.runs : [],
        approval_queue: Array.isArray(response.data?.approval_queue) ? response.data.approval_queue : [],
        active_version: response.data?.active_version || null,
        active_version_id: typeof response.data?.active_version_id === 'string' ? response.data.active_version_id : '',
        active_version_number: typeof response.data?.active_version_number === 'number' ? response.data.active_version_number : 0,
        learning_events: Array.isArray(response.data?.learning_events) ? response.data.learning_events : [],
        version_events: Array.isArray(response.data?.version_events) ? response.data.version_events : [],
        feedback_history: Array.isArray(response.data?.feedback_history) ? response.data.feedback_history : [],
        legacy_migration: response.data?.legacy_migration || {},
        metrics: response.data?.metrics && typeof response.data.metrics === 'object' ? response.data.metrics : undefined,
        activation_gate: response.data?.activation_gate && typeof response.data.activation_gate === 'object' ? response.data.activation_gate : undefined,
      };
      setBlueprintDetails(details);
    } catch (requestError) {
      console.error(requestError);
      setError('Не удалось загрузить историю агента.');
    }
  }, [runStatusFilter]);

  useEffect(() => {
    if (selectedBlueprint?.id) {
      void loadBlueprintDetails(selectedBlueprint.id);
    } else {
      setBlueprintDetails(null);
      setActiveRun(null);
    }
  }, [loadBlueprintDetails, selectedBlueprint?.id]);

  const loadRun = async (runId: string) => {
    setActionLoading(true);
    setError(null);
    try {
      const response = await api.get(`/agent-runs/${runId}`);
      setActiveRun(response.data?.run || null);
      setWorkspaceMode('results');
      if (selectedBlueprint?.id) {
        await loadBlueprintDetails(selectedBlueprint.id);
        await loadBlueprintReview(selectedBlueprint.id);
      }
    } catch (requestError) {
      console.error(requestError);
      setError('Не удалось загрузить запуск.');
    } finally {
      setActionLoading(false);
    }
  };

  const loadBlueprintReview = useCallback(async (blueprintId: string) => {
    try {
      const response = await api.get(`/agent-blueprints/${blueprintId}/review`);
      setAgentReview(response.data?.review || null);
    } catch (requestError) {
      console.error(requestError);
    }
  }, []);

  const loadSourceCatalog = useCallback(async (blueprintId: string) => {
    try {
      const response = await api.get(`/agent-blueprints/${blueprintId}/sources/catalog`);
      const catalog = Array.isArray(response.data?.catalog) ? response.data.catalog : [];
      setSourceCatalog(catalog);
    } catch (requestError) {
      console.error(requestError);
      setSourceCatalog([]);
    }
  }, []);

  const loadAgentIntegrations = useCallback(async (blueprintId: string) => {
    try {
      const response = await api.get(`/agent-blueprints/${blueprintId}/integrations`);
      const integrations = Array.isArray(response.data?.integrations) ? response.data.integrations : [];
      const available = Array.isArray(response.data?.available_integrations) ? response.data.available_integrations : [];
      const providerCatalog = Array.isArray(response.data?.provider_catalog) ? response.data.provider_catalog : [];
      const authOptions = Array.isArray(response.data?.external_auth_options) ? response.data.external_auth_options : [];
      const bindingStatus = Array.isArray(response.data?.binding_status) ? response.data.binding_status : [];
      const connectionPlan = normalizeConnectionPlan(response.data?.connection_plan);
      const customProcess = response.data?.custom_process && typeof response.data.custom_process === 'object' ? response.data.custom_process : {};
      setAgentIntegrations(integrations);
      setAvailableAgentIntegrations(available);
      setAgentIntegrationCatalog(providerCatalog);
      setAgentExternalAuthOptions(authOptions);
      setAgentBindingStatus(bindingStatus);
      setAgentConnectionPlan(connectionPlan);
      const selectedBindingStillExists = bindingStatus.some((binding) => binding.key === selectedConnectionBindingKey);
      if (selectedConnectionBindingKey && !selectedBindingStillExists) {
        setSelectedConnectionBindingKey('');
      }
      if (Array.isArray(customProcess.row_values)) {
        setProcessRowValues(customProcess.row_values.map((item) => String(item || '').trim()).filter(Boolean).join(', '));
      }
      const sheet = integrations.find((item) => item.provider === 'google_sheets') || available.find((item) => item.provider === 'google_sheets');
      if (sheet) {
        setSheetSpreadsheetId(String(sheet.config?.spreadsheet_id || ''));
        setSheetName(String(sheet.config?.sheet_name || 'Sheet1'));
        setSheetAuthRef(String(sheet.auth_ref || ''));
        setSheetDailyCap(String(sheet.limits?.daily_append_cap || 50));
      }
      const telegram = integrations.find((item) => item.provider === 'telegram') || available.find((item) => item.provider === 'telegram');
      if (telegram) {
        setTelegramBotMode(String(telegram.config?.bot_mode || 'business_bot'));
        setTelegramDailyCap(String(telegram.limits?.daily_message_cap || 50));
      }
      const maton = integrations.find((item) => item.provider === 'maton') || available.find((item) => item.provider === 'maton');
      const matonAuth = authOptions.find((item) => item.source === 'maton');
      if (maton || matonAuth) {
        setMatonAuthRef(String(maton?.auth_ref || matonAuth?.id || ''));
        setMatonChannel(String(maton?.config?.channel || 'maton_bridge'));
        setMatonDailyCap(String(maton?.limits?.daily_message_cap || 50));
      }
    } catch (requestError) {
      console.error(requestError);
      setAgentIntegrations([]);
      setAvailableAgentIntegrations([]);
      setAgentIntegrationCatalog([]);
      setAgentExternalAuthOptions([]);
      setAgentBindingStatus([]);
      setAgentConnectionPlan(null);
      setSelectedConnectionBindingKey('');
    }
  }, [selectedConnectionBindingKey]);

  const applyPostConnectHandoff = (value: unknown) => {
    const handoff = normalizePostCreateHandoff(value);
    if (!handoff) {
      return;
    }
    setRecentPostCreateHandoff(handoff);
    if (handoff.workspace_mode === 'run') {
      setSelectedConnectionBindingKey('');
      setWorkspaceMode('run');
    } else if (handoff.workspace_mode === 'connections') {
      if (handoff.next_binding_key) {
        setSelectedConnectionBindingKey(handoff.next_binding_key);
      }
      setWorkspaceMode('connections');
    }
  };

  useEffect(() => {
    if (selectedBlueprint?.id) {
      void loadBlueprintReview(selectedBlueprint.id);
      void loadSourceCatalog(selectedBlueprint.id);
      void loadAgentIntegrations(selectedBlueprint.id);
    } else {
      setAgentReview(null);
      setSourceCatalog([]);
      setAgentIntegrations([]);
      setAvailableAgentIntegrations([]);
      setAgentIntegrationCatalog([]);
      setAgentExternalAuthOptions([]);
      setAgentBindingStatus([]);
      setSelectedConnectionBindingKey('');
    }
  }, [loadAgentIntegrations, loadBlueprintReview, loadSourceCatalog, selectedBlueprint?.id]);

  const createDefaultBlueprint = async (requestText = '') => {
    if (!currentBusinessId) {
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      const response = await api.post('/agent-blueprints', {
        business_id: currentBusinessId,
        name: requestText.trim() ? requestText.trim().slice(0, 80) : 'Агент поиска клиентов',
        category: 'outreach',
        description: requestText.trim() || 'Ищет лиды, готовит список и черновики, внешние отправки только через ручное подтверждение.',
        status: 'active',
        template: 'supervised_outreach',
      });
      const blueprint = response.data?.blueprint;
      await loadBlueprints();
      if (blueprint?.id) {
        setSelectedBlueprintId(blueprint.id);
        await loadBlueprintDetails(blueprint.id);
        await loadBlueprintReview(blueprint.id);
        await loadSourceCatalog(blueprint.id);
        await loadAgentIntegrations(blueprint.id);
        setRecentCreatedAgentName(String(blueprint.name || 'Новый агент'));
      }
    } catch (requestError) {
      console.error(requestError);
      setError('Не удалось создать агента поиска клиентов.');
    } finally {
      setActionLoading(false);
    }
  };

  const startDialogBuilderSession = async () => {
    if (!currentBusinessId || !dialogBuilderInput.trim()) {
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      const response = await api.post('/agent-builder/sessions', {
        business_id: currentBusinessId,
        message: dialogBuilderInput.trim(),
        use_ai_compiler: true,
      });
      setDialogBuilderSession(response.data?.session || null);
      setSelectedBuilderConnectionBindings(autoSelectBuilderConnectionBindings(response.data?.session?.preview || null));
      setSelectedBuilderProviderRoutes(autoSelectBuilderProviderRoutes(response.data?.session?.preview || null));
      setAcceptedBuilderCompilerPlan(false);
      setAcceptedBuilderProviderRoutes(false);
      setAgentPrompt(dialogBuilderInput.trim());
      const preview = response.data?.session?.preview || {};
      if (typeof preview.category === 'string') {
        setBuilderCategory(preview.category);
      }
      if (Array.isArray(preview.data_sources)) {
        setBuilderDataSources(preview.data_sources.join(', '));
      }
      if (typeof preview.extraction_rules === 'string') {
        setBuilderExtractionRules(preview.extraction_rules);
      }
      if (typeof preview.processing_rules === 'string') {
        setBuilderProcessingRules(preview.processing_rules);
      }
      if (typeof preview.output_format === 'string') {
        setBuilderOutputFormat(preview.output_format);
      }
      if (typeof preview.manual_control === 'string') {
        setBuilderManualControl(preview.manual_control);
      }
    } catch (requestError) {
      console.error(requestError);
      setError(getRequestErrorMessage(requestError, 'Не удалось начать диалог создания агента.'));
    } finally {
      setActionLoading(false);
    }
  };

  const sendDialogBuilderReply = async () => {
    if (!dialogBuilderSession || !dialogBuilderReply.trim()) {
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      const response = await api.post(`/agent-builder/sessions/${dialogBuilderSession.id}/message`, {
        message: dialogBuilderReply.trim(),
        use_ai_compiler: true,
      });
      setDialogBuilderSession(response.data?.session || null);
      setSelectedBuilderConnectionBindings(autoSelectBuilderConnectionBindings(response.data?.session?.preview || null));
      setSelectedBuilderProviderRoutes(autoSelectBuilderProviderRoutes(response.data?.session?.preview || null));
      setAcceptedBuilderCompilerPlan(false);
      setAcceptedBuilderProviderRoutes(false);
      setDialogBuilderReply('');
    } catch (requestError) {
      console.error(requestError);
      setError(getRequestErrorMessage(requestError, 'Не удалось отправить уточнение агенту.'));
    } finally {
      setActionLoading(false);
    }
  };

  const createAgentFromDialogSession = async () => {
    if (!dialogBuilderSession) {
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      const response = await api.post(`/agent-builder/sessions/${dialogBuilderSession.id}/create-blueprint`, {
        use_ai_compiler: true,
        selected_connection_bindings: selectedBuilderConnectionBindings,
        selected_provider_routes: acceptedBuilderProviderRoutes ? selectedBuilderProviderRoutes : {},
        accepted_compiler_plan: acceptedBuilderCompilerPlan,
        accepted_provider_routes: acceptedBuilderProviderRoutes,
      });
      const blueprint = response.data?.blueprint;
      const handoff = normalizePostCreateHandoff(response.data?.post_create_handoff);
      await loadBlueprints();
      if (blueprint?.id) {
        setSelectedBlueprintId(blueprint.id);
        await loadBlueprintDetails(blueprint.id);
        await loadBlueprintReview(blueprint.id);
        await loadSourceCatalog(blueprint.id);
        await loadAgentIntegrations(blueprint.id);
        setRecentCreatedAgentName(String(blueprint.name || 'Новый агент'));
        setRecentPostCreateHandoff(handoff);
        if (handoff?.workspace_mode === 'run') {
          setSelectedConnectionBindingKey('');
        } else if (handoff?.next_binding_key) {
          setSelectedConnectionBindingKey(handoff.next_binding_key);
        }
      }
      setDialogBuilderInput('');
      setDialogBuilderReply('');
      setDialogBuilderSession(null);
      setSelectedBuilderConnectionBindings({});
      setSelectedBuilderProviderRoutes({});
      setAcceptedBuilderCompilerPlan(false);
      setAcceptedBuilderProviderRoutes(false);
      setCreateWizardOpen(false);
      const handoffMode = handoff?.workspace_mode || '';
      setWorkspaceMode(
        handoffMode === 'connections' || handoffMode === 'settings' || handoffMode === 'run'
          ? handoffMode
          : (response.data?.next_step === 'connect_required_integrations' ? 'connections' : 'run'),
      );
    } catch (requestError) {
      console.error(requestError);
      setError(getRequestErrorMessage(requestError, 'Не удалось создать агента из диалога.'));
    } finally {
      setActionLoading(false);
    }
  };

  const createAgentFromPrompt = async () => {
    if (!currentBusinessId || !agentPrompt.trim()) {
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      const response = await api.post('/agent-blueprints/draft', {
        business_id: currentBusinessId,
        description: agentPrompt.trim(),
        category: builderCategory,
      });
      const blueprint = response.data?.blueprint;
      const handoff = normalizePostCreateHandoff(response.data?.post_create_handoff);
      await loadBlueprints();
      if (blueprint?.id) {
        await api.post(`/agent-blueprints/${blueprint.id}/setup`, {
          workflow_description: agentPrompt.trim(),
          data_sources: builderDataSources.split(',').map((item) => item.trim()).filter(Boolean),
          extraction_rules: builderExtractionRules,
          processing_rules: builderProcessingRules,
          output_format: builderOutputFormat,
          approval_boundaries: ['final_output', 'external_delivery'],
          manual_control: builderManualControl,
        });
        if (builderSourceText.trim()) {
          await api.post(`/agent-blueprints/${blueprint.id}/sources`, {
            source_type: 'text',
            name: builderSourceName.trim() || 'Контекст для агента',
            content_text: builderSourceText,
          });
        }
        if (builderFileSource) {
          await uploadAgentSource(blueprint.id, builderFileSource, builderSourceName.trim() || builderFileSource.name);
        }
        if (builderInternalSource !== 'none') {
          await api.post(`/agent-blueprints/${blueprint.id}/sources`, {
            source_type: 'internal',
            name: humanizeMeta(builderInternalSource),
            internal_source: builderInternalSource,
          });
        }
        setSelectedBlueprintId(blueprint.id);
        await loadBlueprintDetails(blueprint.id);
        await loadBlueprintReview(blueprint.id);
        await loadSourceCatalog(blueprint.id);
        await loadAgentIntegrations(blueprint.id);
        setRecentCreatedAgentName(String(blueprint.name || 'Новый агент'));
        setRecentPostCreateHandoff(handoff);
        if (handoff?.workspace_mode === 'connections') {
          setWorkspaceMode('connections');
          if (handoff.next_binding_key) {
            setSelectedConnectionBindingKey(handoff.next_binding_key);
          }
        } else if (handoff?.workspace_mode === 'run') {
          setWorkspaceMode('run');
          setSelectedConnectionBindingKey('');
        } else {
          setWorkspaceMode('settings');
        }
      }
      setAgentPrompt('');
      setBuilderSourceName('');
      setBuilderSourceText('');
      setBuilderFileSource(null);
      setCreateWizardOpen(false);
      setCreateWizardStep(0);
    } catch (requestError) {
      console.error(requestError);
      setError(getRequestErrorMessage(requestError, 'Не удалось собрать черновик агента.'));
    } finally {
      setActionLoading(false);
    }
  };

  const startRun = async (blueprintToRun?: AgentBlueprint | null, blueprintVersionId = '') => {
    const targetBlueprint = blueprintToRun || selectedBlueprint;
    if (!targetBlueprint) {
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      const runInput = {
        schema: 'localos_agent_preview_input_v1',
        preview_mode: true,
        source: 'agent_preview',
        dashboard_source: runSource.trim() || 'dashboard',
        city: runCity.trim(),
        category: runCategory.trim(),
        goal: targetBlueprint.description || targetBlueprint.latest_goal || '',
        intent: 'agent_preview',
        business_id: currentBusinessId,
        blueprint_id: targetBlueprint.id,
        blueprint_version_id: blueprintVersionId || getActiveVersionId(targetBlueprint, blueprintDetails) || '',
        external_side_effects_allowed: false,
        approval_required_for_external_actions: true,
        limit: Number(runLimit) > 0 ? Math.min(Number(runLimit), 100) : 30,
      };
      const preflightResponse = await api.post(`/agent-blueprints/${targetBlueprint.id}/preflight`, {
        blueprint_version_id: blueprintVersionId || undefined,
        input: runInput,
      });
      const preflight = normalizeAgentIntegrationPreflight(preflightResponse.data?.preflight);
      if (preflightResponse.data?.can_start === false || preflight?.ready === false) {
        const connectionPlan = normalizeConnectionPlan(preflightResponse.data?.connection_plan);
        if (connectionPlan) {
          setAgentConnectionPlan(connectionPlan);
        }
        const nextBindingKey = String(preflightResponse.data?.next_binding_key || '');
        if (nextBindingKey) {
          setSelectedConnectionBindingKey(nextBindingKey);
        }
        setWorkspaceMode('connections');
        setError(formatPreflightBlock(preflight) || 'Перед запуском нужно подключить источники агента.');
        await loadBlueprintDetails(targetBlueprint.id);
        return;
      }
      const response = await api.post(`/agent-blueprints/${targetBlueprint.id}/runs`, {
        blueprint_version_id: blueprintVersionId || undefined,
        input: runInput,
      });
      setActiveRun(response.data?.run || null);
      setWorkspaceMode('results');
      await loadBlueprintDetails(targetBlueprint.id);
      await loadBlueprintReview(targetBlueprint.id);
    } catch (requestError) {
      console.error(requestError);
      setError(getRequestErrorMessage(requestError, 'Не удалось запустить агента.'));
    } finally {
      setActionLoading(false);
    }
  };

  const activateVersion = async (versionId: string, action: 'activate' | 'rollback') => {
    if (!selectedBlueprint || !versionId) {
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      await api.post(`/agent-blueprints/${selectedBlueprint.id}/versions/${versionId}/${action}`, {
        reason: action === 'rollback' ? 'Откат из карточки агента' : 'Активировано из карточки агента',
      });
      if (feedbackVersionNotice?.version_id === versionId) {
        setFeedbackVersionNotice({
          ...feedbackVersionNotice,
          activation_state: action === 'rollback' ? 'rolled_back' : 'active',
          next_run_note: action === 'rollback'
            ? 'Активная версия возвращена к выбранной версии. История feedback сохранена.'
            : 'Candidate-версия активирована. Следующие запуски будут использовать её.',
        });
      }
      await loadBlueprints();
      await loadBlueprintDetails(selectedBlueprint.id);
      await loadBlueprintReview(selectedBlueprint.id);
    } catch (requestError) {
      console.error(requestError);
      setError(action === 'rollback' ? 'Не удалось откатить версию агента.' : 'Не удалось активировать версию агента.');
    } finally {
      setActionLoading(false);
    }
  };

  const deleteSelectedAgent = async () => {
    if (!selectedBlueprint) {
      return;
    }
    const confirmed = window.confirm(`Убрать агента “${selectedBlueprint.name}” из списка? История запусков сохранится в архиве.`);
    if (!confirmed) {
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      await api.delete(`/agent-blueprints/${selectedBlueprint.id}`);
      const remaining = blueprints.filter((item) => item.id !== selectedBlueprint.id);
      setSelectedBlueprintId(remaining[0]?.id || null);
      setBlueprintDetails(null);
      setActiveRun(null);
      setWorkspaceMode('overview');
      await loadBlueprints();
    } catch (requestError) {
      console.error(requestError);
      setError(getRequestErrorMessage(requestError, 'Не удалось удалить агента.'));
    } finally {
      setActionLoading(false);
    }
  };

  const decideApproval = async (decision: 'approve' | 'reject') => {
    if (!activeRun || !pendingApproval) {
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      const response = await api.post(`/agent-runs/${activeRun.id}/approvals/${pendingApproval.id}/${decision}`, {
        reason: decision === 'approve' ? 'Approved from dashboard' : 'Rejected from dashboard',
      });
      setActiveRun(response.data?.run || null);
      if (selectedBlueprint?.id) {
        await loadBlueprintDetails(selectedBlueprint.id);
        await loadBlueprintReview(selectedBlueprint.id);
      }
    } catch (requestError) {
      console.error(requestError);
      setError('Не удалось применить решение.');
    } finally {
      setActionLoading(false);
    }
  };

  const applyFinanceRequests = async (runId: string) => {
    setActionLoading(true);
    setError(null);
    try {
      const response = await api.post(`/agent-runs/${runId}/finance-requests/apply`, {
        reason: 'Applied from agent run dashboard',
      });
      setActiveRun(response.data?.run || null);
      if (selectedBlueprint?.id) {
        await loadBlueprintDetails(selectedBlueprint.id);
        await loadBlueprintReview(selectedBlueprint.id);
      }
    } catch (requestError) {
      console.error(requestError);
      setError(getRequestErrorMessage(requestError, 'Не удалось применить операции в финансы.'));
    } finally {
      setActionLoading(false);
    }
  };

  const saveAgentSetup = async () => {
    if (!selectedBlueprint) {
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      await api.post(`/agent-blueprints/${selectedBlueprint.id}/setup`, {
        workflow_description: selectedBlueprint.latest_goal || selectedBlueprint.description || selectedBlueprint.name,
        data_sources: setupDataSources.split(',').map((item) => item.trim()).filter(Boolean),
        extraction_rules: setupExtractionRules,
        processing_rules: setupProcessingRules,
        output_format: setupOutputFormat,
        approval_boundaries: ['final_output', 'external_delivery'],
        manual_control: setupManualControl,
      });
      await loadBlueprintDetails(selectedBlueprint.id);
      await loadBlueprintReview(selectedBlueprint.id);
      await loadSourceCatalog(selectedBlueprint.id);
    } catch (requestError) {
      console.error(requestError);
      setError('Не удалось сохранить настройку агента.');
    } finally {
      setActionLoading(false);
    }
  };

  const addTextSource = async () => {
    if (!selectedBlueprint || !sourceText.trim()) {
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      await api.post(`/agent-blueprints/${selectedBlueprint.id}/sources`, {
        source_type: 'text',
        name: sourceName.trim() || 'Ручной контекст',
        content_text: sourceText,
      });
      setSourceName('');
      setSourceText('');
      await loadBlueprintReview(selectedBlueprint.id);
      await loadSourceCatalog(selectedBlueprint.id);
    } catch (requestError) {
      console.error(requestError);
      setError('Не удалось добавить источник данных.');
    } finally {
      setActionLoading(false);
    }
  };

  const addInternalSource = async () => {
    if (!selectedBlueprint) {
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      await api.post(`/agent-blueprints/${selectedBlueprint.id}/sources`, {
        source_type: 'internal',
        name: humanizeMeta(internalSource),
        internal_source: internalSource,
      });
      await loadBlueprintReview(selectedBlueprint.id);
      await loadSourceCatalog(selectedBlueprint.id);
    } catch (requestError) {
      console.error(requestError);
      setError('Не удалось подключить источник LocalOS.');
    } finally {
      setActionLoading(false);
    }
  };

  const addInternalSourceByKey = async (sourceKey: string) => {
    if (!selectedBlueprint || !sourceKey) {
      return;
    }
    setInternalSource(sourceKey);
    setActionLoading(true);
    setError(null);
    try {
      await api.post(`/agent-blueprints/${selectedBlueprint.id}/sources`, {
        source_type: 'internal',
        name: humanizeMeta(sourceKey),
        internal_source: sourceKey,
      });
      await loadBlueprintReview(selectedBlueprint.id);
      await loadSourceCatalog(selectedBlueprint.id);
    } catch (requestError) {
      console.error(requestError);
      setError('Не удалось подключить источник LocalOS.');
    } finally {
      setActionLoading(false);
    }
  };

  const addFileSource = async (file?: File | null) => {
    if (!selectedBlueprint || !file) {
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      await uploadAgentSource(selectedBlueprint.id, file, file.name);
      await loadBlueprintReview(selectedBlueprint.id);
      await loadSourceCatalog(selectedBlueprint.id);
    } catch (requestError) {
      console.error(requestError);
      setError(getRequestErrorMessage(requestError, 'Не удалось добавить файл.'));
    } finally {
      setActionLoading(false);
    }
  };

  const saveSheetIntegration = async () => {
    if (!selectedBlueprint || !sheetSpreadsheetId.trim()) {
      return;
    }
    const selectedBinding = agentBindingStatus.find((item) => item.key === selectedConnectionBindingKey && item.provider === 'google_sheets');
    const existing = [...agentIntegrations, ...availableAgentIntegrations].find((item) => item.provider === 'google_sheets');
    const needsRead = agentBindingStatus.some((item) => item.provider === 'google_sheets' && item.capability === 'google_sheets.read_rows');
    const needsAppend = agentBindingStatus.some((item) => item.provider === 'google_sheets' && item.capability === 'sheets.append_row_request');
    const selectedCapability = selectedBinding?.capability || '';
    const operation = selectedCapability === 'google_sheets.read_rows'
      ? 'read_rows'
      : selectedCapability === 'sheets.append_row_request'
        ? 'append_row'
        : needsRead && needsAppend ? 'read_write' : needsRead ? 'read_rows' : 'append_row';
    setActionLoading(true);
    setError(null);
    try {
      const response = await api.post(`/agent-blueprints/${selectedBlueprint.id}/integrations`, {
        integration_id: existing?.id,
        binding_key: selectedBinding?.key || '',
        provider: 'google_sheets',
        status: 'active',
        display_name: 'Google Sheets',
        auth_ref: sheetAuthRef.trim(),
        config: {
          spreadsheet_id: sheetSpreadsheetId.trim(),
          sheet_name: sheetName.trim() || 'Sheet1',
          operation,
        },
        limits: {
          daily_append_cap: Number(sheetDailyCap) > 0 ? Number(sheetDailyCap) : 50,
          frequency_cap_minutes: 0,
        },
      });
      await loadAgentIntegrations(selectedBlueprint.id);
      await loadBlueprintDetails(selectedBlueprint.id);
      applyPostConnectHandoff(response.data?.post_connect_handoff);
    } catch (requestError) {
      console.error(requestError);
      setError(getRequestErrorMessage(requestError, 'Не удалось подключить Google Sheets.'));
    } finally {
      setActionLoading(false);
    }
  };

  const saveTelegramIntegration = async () => {
    if (!selectedBlueprint) {
      return;
    }
    const selectedBinding = agentBindingStatus.find((item) => item.key === selectedConnectionBindingKey && item.provider === 'telegram');
    const existing = [...agentIntegrations, ...availableAgentIntegrations].find((item) => item.provider === 'telegram');
    setActionLoading(true);
    setError(null);
    try {
      const response = await api.post(`/agent-blueprints/${selectedBlueprint.id}/integrations`, {
        integration_id: existing?.id,
        binding_key: selectedBinding?.key || '',
        provider: 'telegram',
        status: 'active',
        display_name: 'Telegram',
        config: {
          bot_mode: telegramBotMode,
        },
        limits: {
          daily_message_cap: Number(telegramDailyCap) > 0 ? Number(telegramDailyCap) : 50,
          frequency_cap_minutes: 30,
        },
      });
      await loadAgentIntegrations(selectedBlueprint.id);
      await loadBlueprintDetails(selectedBlueprint.id);
      applyPostConnectHandoff(response.data?.post_connect_handoff);
    } catch (requestError) {
      console.error(requestError);
      setError(getRequestErrorMessage(requestError, 'Не удалось подключить Telegram.'));
    } finally {
      setActionLoading(false);
    }
  };

  const saveMatonIntegration = async () => {
    if (!selectedBlueprint) {
      return;
    }
    const selectedBinding = agentBindingStatus.find((item) => item.key === selectedConnectionBindingKey && item.provider === 'maton');
    const existing = [...agentIntegrations, ...availableAgentIntegrations].find((item) => item.provider === 'maton');
    setActionLoading(true);
    setError(null);
    try {
      const response = await api.post(`/agent-blueprints/${selectedBlueprint.id}/integrations`, {
        integration_id: existing?.id,
        binding_key: selectedBinding?.key || '',
        provider: 'maton',
        status: 'active',
        display_name: 'Maton.ai',
        auth_ref: matonAuthRef.trim(),
        config: {
          channel: matonChannel.trim() || 'maton_bridge',
        },
        limits: {
          daily_message_cap: Number(matonDailyCap) > 0 ? Number(matonDailyCap) : 50,
          frequency_cap_minutes: 30,
        },
      });
      await loadAgentIntegrations(selectedBlueprint.id);
      await loadBlueprintDetails(selectedBlueprint.id);
      applyPostConnectHandoff(response.data?.post_connect_handoff);
    } catch (requestError) {
      console.error(requestError);
      setError(getRequestErrorMessage(requestError, 'Не удалось подключить Maton.ai.'));
    } finally {
      setActionLoading(false);
    }
  };

  const chooseProviderRoute = async (bindingKey: string, route: AgentProviderRoute) => {
    if (!selectedBlueprint || !bindingKey || !route.provider) {
      return;
    }
    if (route.provider === 'maton' && !matonAuthRef.trim()) {
      setSelectedConnectionBindingKey(bindingKey);
      setWorkspaceMode('connections');
      setError('Выберите сохранённый Maton.ai key для этого шага.');
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      const response = await api.post(`/agent-blueprints/${selectedBlueprint.id}/provider-routes`, {
        binding_key: bindingKey,
        route_provider: route.provider,
        external_account_id: route.provider === 'maton' ? matonAuthRef.trim() : '',
      });
      await loadAgentIntegrations(selectedBlueprint.id);
      await loadBlueprintDetails(selectedBlueprint.id);
      await loadBlueprintReview(selectedBlueprint.id);
      applyPostConnectHandoff(response.data?.post_connect_handoff);
    } catch (requestError) {
      console.error(requestError);
      setError(getRequestErrorMessage(requestError, 'Не удалось выбрать provider route для агента.'));
    } finally {
      setActionLoading(false);
    }
  };

  const attachExistingAgentIntegration = async (integration: AgentIntegration, bindingKey = '') => {
    if (!selectedBlueprint || !integration?.id || !integration.provider) {
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      const response = await api.post(`/agent-blueprints/${selectedBlueprint.id}/integrations`, {
        integration_id: integration.id,
        binding_key: bindingKey,
        provider: integration.provider,
        status: 'active',
        display_name: integration.display_name || integration.provider_label || humanizeMeta(integration.provider),
        auth_ref: integration.auth_ref || '',
        config: integration.config || {},
        limits: integration.limits || {},
      });
      await loadAgentIntegrations(selectedBlueprint.id);
      await loadBlueprintDetails(selectedBlueprint.id);
      applyPostConnectHandoff(response.data?.post_connect_handoff);
    } catch (requestError) {
      console.error(requestError);
      setError(getRequestErrorMessage(requestError, 'Не удалось подключить существующий доступ к агенту.'));
    } finally {
      setActionLoading(false);
    }
  };

  const saveCustomProcess = async () => {
    if (!selectedBlueprint) {
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      await api.post(`/agent-blueprints/${selectedBlueprint.id}/custom-process`, {
        trigger: 'telegram.message.received',
        target: 'google_sheets.append_row',
        row_values: processRowValues,
        integration_id: agentIntegrations.find((item) => item.provider === 'google_sheets')?.id || '',
        spreadsheet_id: sheetSpreadsheetId.trim(),
        sheet_name: sheetName.trim() || 'Leads',
        daily_append_cap: Number(sheetDailyCap) > 0 ? Number(sheetDailyCap) : 50,
      });
      await loadAgentIntegrations(selectedBlueprint.id);
      await loadBlueprintDetails(selectedBlueprint.id);
      await loadBlueprintReview(selectedBlueprint.id);
    } catch (requestError) {
      console.error(requestError);
      setError(getRequestErrorMessage(requestError, 'Не удалось сохранить процесс агента.'));
    } finally {
      setActionLoading(false);
    }
  };

  const runCustomProcessPreview = async () => {
    if (!selectedBlueprint) {
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      const response = await api.post(`/agent-blueprints/${selectedBlueprint.id}/custom-process/preview`, {
        message_text: processPreviewMessage.trim() || 'Новая заявка для проверки',
        telegram_username: 'preview_user',
      });
      setActiveRun(response.data?.run || null);
      setWorkspaceMode('results');
      await loadBlueprintDetails(selectedBlueprint.id);
      await loadBlueprintReview(selectedBlueprint.id);
    } catch (requestError) {
      console.error(requestError);
      setError(getRequestErrorMessage(requestError, 'Не удалось проверить процесс на примере.'));
    } finally {
      setActionLoading(false);
    }
  };

  const applyLegacyMigration = async () => {
    if (!currentBusinessId) {
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      const response = await api.post('/agent-blueprints/legacy-migration/apply', {
        business_id: currentBusinessId,
      });
      const migration = response.data?.migration || {};
      const appliedCount = typeof migration.applied_count === 'number' ? migration.applied_count : 0;
      const skippedCount = typeof migration.skipped_count === 'number' ? migration.skipped_count : 0;
      setLegacyMigrationNotice(`Миграция выполнена: создано ${appliedCount}, пропущено ${skippedCount}. Legacy поля не удалялись.`);
      await loadBlueprints();
      await loadLegacyMigrationPlan();
      if (selectedBlueprint?.id) {
        await loadBlueprintDetails(selectedBlueprint.id);
      }
    } catch (requestError) {
      console.error(requestError);
      setError(getRequestErrorMessage(requestError, 'Не удалось применить legacy migration.'));
    } finally {
      setActionLoading(false);
    }
  };

  const sendRunFeedback = async () => {
    if (!activeRun || !feedbackText.trim()) {
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      const response = await api.post(`/agent-runs/${activeRun.id}/feedback`, {
        feedback: feedbackText,
        trigger_type: feedbackTrigger,
        auto_activate: false,
      });
      const version = response.data?.version || {};
      const learning: AgentLearningLoop = response.data?.learning || {};
      setFeedbackVersionNotice({
        version_id: typeof version.id === 'string' ? version.id : learning.candidate_version_id,
        previous_version_id: learning.previous_version_id,
        version_number: typeof version.version_number === 'number' ? version.version_number : undefined,
        feedback: feedbackText,
        activation_state: learning.activation_state || 'candidate',
        trigger_label: learning.trigger_label || learningTriggerOptions.find((item) => item.value === feedbackTrigger)?.label || 'Обратная связь',
        diff: learning.diff || response.data?.diff || undefined,
        next_run_note: 'Это кандидатная версия. Она сохранена с diff, но не станет активной, пока человек не активирует её.',
      });
      setFeedbackText('');
      if (selectedBlueprint?.id) {
        await loadBlueprintDetails(selectedBlueprint.id);
        await loadBlueprintReview(selectedBlueprint.id);
      }
    } catch (requestError) {
      console.error(requestError);
      setError(getRequestErrorMessage(requestError, 'Не удалось сохранить правку агента.'));
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <div className="space-y-5">
      <DashboardPageHeader
        eyebrow="LocalOS"
        title="Мои агенты"
        description="Создайте агента обычным языком, подключите данные и проверьте первый запуск перед внешним действием."
        icon={Bot}
        actions={(
          <>
            <Button type="button" variant="outline" onClick={loadBlueprints} disabled={loading || !currentBusinessId}>
              <RefreshCw className={cn('mr-2 h-4 w-4', loading && 'animate-spin')} />
              Обновить
            </Button>
            <Button type="button" onClick={() => setCreateWizardOpen(true)} disabled={actionLoading || !currentBusinessId}>
              <Sparkles className="mr-2 h-4 w-4" />
              Создать агента
            </Button>
          </>
        )}
      />

      <Dialog open={createWizardOpen} onOpenChange={setCreateWizardOpen}>
        <DialogContent className="max-h-[88vh] max-w-5xl overflow-y-auto rounded-2xl">
          <DialogHeader>
            <DialogTitle>Создать агента</DialogTitle>
            <DialogDescription>
              Опишите задачу обычным языком. LocalOS уточнит недостающие детали и покажет понятную проверку перед созданием.
            </DialogDescription>
          </DialogHeader>
          <DialogAgentBuilder
            input={dialogBuilderInput}
            reply={dialogBuilderReply}
            session={dialogBuilderSession}
            actionLoading={actionLoading}
            onInputChange={setDialogBuilderInput}
            onReplyChange={setDialogBuilderReply}
            onStart={startDialogBuilderSession}
            onSendReply={sendDialogBuilderReply}
            onCreate={createAgentFromDialogSession}
            selectedConnectionBindings={selectedBuilderConnectionBindings}
            selectedProviderRoutes={selectedBuilderProviderRoutes}
            acceptedCompilerPlan={acceptedBuilderCompilerPlan}
            acceptedProviderRoutes={acceptedBuilderProviderRoutes}
            onAcceptCompilerPlan={() => setAcceptedBuilderCompilerPlan(true)}
            onAcceptProviderRoutes={() => setAcceptedBuilderProviderRoutes(true)}
            onSelectConnectionBinding={(bindingKey, integrationId) => {
              setSelectedBuilderConnectionBindings((current) => ({
                ...current,
                [bindingKey]: integrationId,
              }));
            }}
            onSelectProviderRoute={(bindingKey, routeProvider) => {
              setAcceptedBuilderProviderRoutes(false);
              setSelectedBuilderProviderRoutes((current) => ({
                ...current,
                [bindingKey]: routeProvider,
              }));
            }}
          />
          <details className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
            <summary className="cursor-pointer text-sm font-medium text-slate-700">
              Расширенная ручная настройка
            </summary>
            <div className="mt-4">
          <CreateAgentWizard
            step={createWizardStep}
            prompt={agentPrompt}
            selectedScenario={selectedScenario}
            scenarios={agentScenarios}
            examples={agentPromptExamples}
            dataSources={builderDataSources}
            extractionRules={builderExtractionRules}
            processingRules={builderProcessingRules}
            outputFormat={builderOutputFormat}
            manualControl={builderManualControl}
            sourceName={builderSourceName}
            sourceText={builderSourceText}
            fileSource={builderFileSource}
            internalSource={builderInternalSource}
            actionLoading={actionLoading}
            canCreate={Boolean(currentBusinessId && agentPrompt.trim())}
            onStepChange={setCreateWizardStep}
            onScenarioSelect={applyBuilderScenario}
            onPromptChange={setAgentPrompt}
            onDataSourcesChange={setBuilderDataSources}
            onExtractionRulesChange={setBuilderExtractionRules}
            onProcessingRulesChange={setBuilderProcessingRules}
            onOutputFormatChange={setBuilderOutputFormat}
            onManualControlChange={setBuilderManualControl}
            onSourceNameChange={setBuilderSourceName}
            onSourceTextChange={setBuilderSourceText}
            onFileSourceChange={setBuilderFileSource}
            onInternalSourceChange={setBuilderInternalSource}
            onCreate={createAgentFromPrompt}
          />
            </div>
          </details>
        </DialogContent>
      </Dialog>

      {error ? (
        <DashboardActionPanel
          title="Ошибка"
          description={error}
          tone="amber"
        />
      ) : null}

      {recentCreatedAgentName ? (
        <div className="space-y-3">
          <DashboardActionPanel
            title={recentPostCreateHandoff?.title || 'Агент создан'}
            description={recentPostCreateHandoff?.description || `${recentCreatedAgentName} выбран ниже. Проверьте данные агента, активную версию и запустите его из карточки.`}
            tone={recentPostCreateHandoff?.status === 'needs_connections' ? 'amber' : 'sky'}
            actions={(
              <div className="flex flex-wrap gap-2">
                {recentPostCreateHandoff?.workspace_mode === 'connections' ? (
                  <Button type="button" size="sm" onClick={() => setWorkspaceMode('connections')}>
                    Открыть подключения
                  </Button>
                ) : null}
                {recentPostCreateHandoff?.workspace_mode === 'run' ? (
                  <Button type="button" size="sm" onClick={() => setWorkspaceMode('run')}>
                    Запустить preview
                  </Button>
                ) : null}
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    setRecentCreatedAgentName('');
                    setRecentPostCreateHandoff(null);
                  }}
                >
                  Понятно
                </Button>
              </div>
            )}
	          />
	          {recentPostCreateHandoff?.next_binding ? (
	            <div className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-3 text-xs leading-5 text-amber-950">
	              <div className="font-semibold">
	                Следующий доступ: {recentPostCreateHandoff.next_binding.title || connectorLabel(recentPostCreateHandoff.next_binding.provider)}
	              </div>
	              <div className="mt-1">
	                {recentPostCreateHandoff.next_binding.route_summary || recentPostCreateHandoff.next_binding.explanation || 'Откройте подключения и завершите настройку этого шага.'}
	              </div>
	              {recentPostCreateHandoff.next_route?.label || recentPostCreateHandoff.next_route?.primary_cta ? (
	                <div className="mt-2 rounded-lg bg-white/80 px-2 py-1.5 text-amber-900 ring-1 ring-amber-100">
	                  <ProviderActionPill
	                    route={recentPostCreateHandoff.next_route}
	                    disabled={actionLoading || !recentPostCreateHandoff.next_binding_key}
	                    onChoose={recentPostCreateHandoff.next_binding_key ? () => chooseProviderRoute(recentPostCreateHandoff.next_binding_key || '', recentPostCreateHandoff.next_route || {}) : undefined}
	                  />
	                  {providerActionDescription(recentPostCreateHandoff.next_route) ? (
	                    <div className="mt-1">{providerActionDescription(recentPostCreateHandoff.next_route)}</div>
	                  ) : null}
	                </div>
	              ) : null}
	            </div>
	          ) : null}
	          <AgentConnectionPlanPanel
	            connectionPlan={recentPostCreateHandoff?.connection_plan || agentConnectionPlan}
            availableIntegrations={availableAgentIntegrations}
            actionLoading={actionLoading}
            onAttachExistingIntegration={attachExistingAgentIntegration}
            onConfigureBinding={setSelectedConnectionBindingKey}
            onChooseProviderRoute={chooseProviderRoute}
          />
        </div>
      ) : null}

      {currentBusinessId ? (
          <AgentCommandCenter
            activeAgentsCount={activeAgentsCount}
            totalAgents={blueprints.length}
          pendingApprovals={totalPendingApprovals || pendingApprovals.length || activeRunPendingApprovals.length}
          selectedBlueprint={selectedBlueprint}
          loading={loading}
          actionLoading={actionLoading}
          onCreate={() => setCreateWizardOpen(true)}
          onConfigureSelected={() => {
            if (selectedBlueprint) {
              setWorkspaceMode('settings');
            }
          }}
          onOpenApprovals={() => {
            if (selectedBlueprint) {
              setWorkspaceMode('results');
            }
          }}
        />
      ) : null}

      {!currentBusinessId ? (
        <DashboardEmptyState
          title="Сначала выберите бизнес"
          description="Агенты всегда привязаны к конкретному бизнесу и его правам доступа."
        />
      ) : null}

      {currentBusinessId ? (
        <div className="space-y-5">
          <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="text-sm font-semibold text-slate-950">Агенты</div>
                <div className="mt-1 text-xs leading-5 text-slate-500">
                  Выберите агента, чтобы изменить логику, подключить данные или посмотреть журнал.
                </div>
              </div>
              <span className="rounded-full bg-slate-50 px-2.5 py-1 text-xs font-medium text-slate-600 ring-1 ring-slate-200">
                {blueprints.length} всего
              </span>
            </div>
            <div className="mt-4 grid max-h-[28rem] gap-3 overflow-y-auto pr-1 lg:grid-cols-2 2xl:grid-cols-3">
              {loading ? (
                <div className="flex items-center gap-2 rounded-xl bg-slate-50 px-3 py-4 text-sm text-slate-500">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Загружаем агентов...
                </div>
              ) : blueprints.length === 0 ? (
                <DashboardEmptyState
                  title="Агентов пока нет"
                  description="Создайте первого агента через мастер. Голос и стиль подключаются позже."
                />
              ) : (
                blueprints.map((blueprint) => {
                  const selected = selectedBlueprint?.id === blueprint.id;
                  return (
                    <BlueprintAgentCard
                      key={blueprint.id}
                      blueprint={blueprint}
                      latestVersionNumber={getActiveVersionNumber(blueprint, selected ? blueprintDetails : null)}
                      selected={selected}
                      onSelect={() => {
                        setSelectedBlueprintId(blueprint.id);
                        setActiveRun(null);
                        setWorkspaceMode('overview');
                      }}
                      onConfigure={() => {
                        setSelectedBlueprintId(blueprint.id);
                        setActiveRun(null);
                        setWorkspaceMode('settings');
                      }}
                      onRun={() => {
                        setSelectedBlueprintId(blueprint.id);
                        setWorkspaceMode('run');
                        void startRun(blueprint);
                      }}
                      onResults={() => {
                        setSelectedBlueprintId(blueprint.id);
                        setWorkspaceMode('results');
                      }}
                      onVoice={() => {
                        setSelectedBlueprintId(blueprint.id);
                        setActiveRun(null);
                        setWorkspaceMode('voice');
                      }}
                    />
                  );
                })
              )}
            </div>
          </section>

          <div className="min-w-0">
            {selectedBlueprint ? (
              <AgentDetailPanel
                mode={workspaceMode}
                blueprint={selectedBlueprint}
                blueprintDetails={blueprintDetails}
                activeRun={activeRun}
                availablePersonaAgents={availablePersonaAgents}
                pendingApproval={pendingApproval}
                queuedButNotDispatched={queuedButNotDispatched}
                agentReview={agentReview}
                feedbackText={feedbackText}
                feedbackTrigger={feedbackTrigger}
                feedbackVersionNotice={feedbackVersionNotice}
                actionLoading={actionLoading}
                setupDataSources={setupDataSources}
                setupExtractionRules={setupExtractionRules}
                setupProcessingRules={setupProcessingRules}
                setupOutputFormat={setupOutputFormat}
                setupManualControl={setupManualControl}
                sourceName={sourceName}
                sourceText={sourceText}
                internalSource={internalSource}
                sourceCatalog={sourceCatalog}
                agentIntegrations={agentIntegrations}
                availableAgentIntegrations={availableAgentIntegrations}
                agentIntegrationCatalog={agentIntegrationCatalog}
                agentExternalAuthOptions={agentExternalAuthOptions}
                agentBindingStatus={agentBindingStatus}
                agentConnectionPlan={agentConnectionPlan}
                selectedConnectionBindingKey={selectedConnectionBindingKey}
                sheetSpreadsheetId={sheetSpreadsheetId}
                sheetName={sheetName}
                sheetAuthRef={sheetAuthRef}
                sheetDailyCap={sheetDailyCap}
                telegramBotMode={telegramBotMode}
                telegramDailyCap={telegramDailyCap}
                matonAuthRef={matonAuthRef}
                matonChannel={matonChannel}
                matonDailyCap={matonDailyCap}
                processRowValues={processRowValues}
                processPreviewMessage={processPreviewMessage}
                runSource={runSource}
                runCity={runCity}
                runCategory={runCategory}
                runLimit={runLimit}
                onModeChange={setWorkspaceMode}
                onStartRun={() => startRun(selectedBlueprint)}
                onStartVersionRun={(versionId) => startRun(selectedBlueprint, versionId)}
                onActivateVersion={(versionId) => activateVersion(versionId, 'activate')}
                onRollbackVersion={(versionId) => activateVersion(versionId, 'rollback')}
                onApprove={() => decideApproval('approve')}
                onReject={() => decideApproval('reject')}
                onDeleteAgent={deleteSelectedAgent}
                onFeedbackTextChange={setFeedbackText}
                onFeedbackTriggerChange={setFeedbackTrigger}
                onSubmitFeedback={sendRunFeedback}
                onActivateFeedbackVersion={(versionId) => activateVersion(versionId, 'activate')}
                onRollbackFeedbackVersion={(versionId) => activateVersion(versionId, 'rollback')}
                onSetupDataSourcesChange={setSetupDataSources}
                onSetupExtractionRulesChange={setSetupExtractionRules}
                onSetupProcessingRulesChange={setSetupProcessingRules}
                onSetupOutputFormatChange={setSetupOutputFormat}
                onSetupManualControlChange={setSetupManualControl}
                onSourceNameChange={setSourceName}
                onSourceTextChange={setSourceText}
                onInternalSourceChange={setInternalSource}
                onSaveSetup={saveAgentSetup}
                onAddTextSource={addTextSource}
                onAddInternalSource={addInternalSource}
                onAddCatalogSource={addInternalSourceByKey}
                onAddFileSource={addFileSource}
                onSheetSpreadsheetIdChange={setSheetSpreadsheetId}
                onSheetNameChange={setSheetName}
                onSheetAuthRefChange={setSheetAuthRef}
                onSheetDailyCapChange={setSheetDailyCap}
                onTelegramBotModeChange={setTelegramBotMode}
                onTelegramDailyCapChange={setTelegramDailyCap}
                onMatonAuthRefChange={setMatonAuthRef}
                onMatonChannelChange={setMatonChannel}
                onMatonDailyCapChange={setMatonDailyCap}
                onProcessRowValuesChange={setProcessRowValues}
                onProcessPreviewMessageChange={setProcessPreviewMessage}
                onSaveSheetIntegration={saveSheetIntegration}
                onSaveTelegramIntegration={saveTelegramIntegration}
                onSaveMatonIntegration={saveMatonIntegration}
                onChooseProviderRoute={chooseProviderRoute}
                onAttachExistingIntegration={attachExistingAgentIntegration}
                onSelectConnectionBinding={setSelectedConnectionBindingKey}
                onSaveCustomProcess={saveCustomProcess}
                onRunCustomProcessPreview={runCustomProcessPreview}
                onRunSourceChange={setRunSource}
                onRunCityChange={setRunCity}
                onRunCategoryChange={setRunCategory}
                onRunLimitChange={setRunLimit}
                showAdvancedTools={showAdvancedAgentTools}
              />
            ) : (
              <DashboardEmptyState
                title="Выберите агента"
                description="Откройте существующего агента или создайте нового через кнопку сверху."
              />
            )}
          </div>
        </div>
      ) : null}

      {currentBusinessId && showAdvancedAgentTools ? (
        <details className="rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
          <summary className="cursor-pointer text-sm font-semibold text-slate-800">
            Служебные инструменты миграции и поддержки
          </summary>
          <div className="mt-4 space-y-5">
            <AgentCockpitPanel
              blueprints={blueprints}
              systemAgents={systemAgents}
              migrationPlan={legacyMigrationPlan}
              migrationStats={migrationStats}
              migrationNotice={legacyMigrationNotice}
              actionLoading={actionLoading}
              onApplyMigration={applyLegacyMigration}
              onOpenLegacySettings={() => setWorkspaceMode('voice')}
            />

            {availablePersonaAgents.length ? (
              <DashboardActionPanel
                title="Голоса и стиль перенесены внутрь агента"
                description={`${availablePersonaAgents.length} старых голосов доступны во вкладке “Голос и стиль” выбранного агента. Отдельный редактор старой логики больше не используется как основной вход.`}
                tone="sky"
              />
            ) : null}

            {selectedBlueprint ? (
              <div className="grid gap-5 xl:grid-cols-2">
                <DashboardSection
                  title="Последние запуски"
                  description="Короткая история выбранного агента."
                  actions={(
                    <div className="flex flex-wrap gap-2">
                      {runStatusFilters.map((filter) => (
                        <Button
                          key={filter.value}
                          type="button"
                          size="sm"
                          variant={runStatusFilter === filter.value ? 'default' : 'outline'}
                          onClick={() => setRunStatusFilter(filter.value)}
                        >
                          {filter.label}
                        </Button>
                      ))}
                    </div>
                  )}
                >
                  {blueprintDetails?.runs?.length ? (
                    <div className="grid gap-3">
                      {blueprintDetails.runs.map((run) => (
                        <button
                          key={run.id}
                          type="button"
                          className={cn(
                            'rounded-xl border px-4 py-3 text-left transition',
                            activeRun?.id === run.id ? 'border-slate-900 bg-slate-950 text-white' : 'border-slate-200 bg-white hover:border-slate-300',
                          )}
                          onClick={() => void loadRun(run.id)}
                        >
                          <div className="flex items-center justify-between gap-3">
                            <div className="flex min-w-0 items-center gap-2">
                              <Workflow className="h-4 w-4 shrink-0" />
                              <span className="truncate text-sm font-semibold">Запуск {run.id.slice(0, 8)}</span>
                            </div>
                            <StatusBadge status={run.status} />
                          </div>
                          <div className={cn('mt-2 text-xs', activeRun?.id === run.id ? 'text-slate-300' : 'text-slate-500')}>
                            {run.started_at || 'Дата запуска недоступна'}
                          </div>
                        </button>
                      ))}
                    </div>
                  ) : (
                    <DashboardEmptyState
                      title="История пуста"
                      description="Запустите агента, чтобы здесь появилась история."
                    />
                  )}
                </DashboardSection>

                <DashboardSection
                  title="Ждут решения"
                  description="Решения, без которых агент не продолжит рискованное действие."
                >
                  {pendingApprovals.length ? (
                    <div className="grid gap-3">
                      {pendingApprovals.map((approval) => (
                        <button
                          key={approval.id}
                          type="button"
                          className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-left transition hover:border-amber-300"
                          onClick={() => approval.run_id ? void loadRun(approval.run_id) : undefined}
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0">
                              <div className="truncate text-sm font-semibold text-slate-950">{approval.title}</div>
                              <div className="mt-1 text-xs text-amber-700">
                                Запуск {approval.run_id ? approval.run_id.slice(0, 8) : 'неизвестен'} · {humanizeMeta(approval.approval_type)}
                              </div>
                            </div>
                            <StatusBadge status={approval.status} />
                          </div>
                          <div className="mt-2 text-xs text-slate-500">{approval.requested_at || humanizeStatus(approval.run_status || 'pending')}</div>
                          <div className="mt-2 rounded-lg bg-white/70 px-2 py-2 text-xs leading-5 text-amber-900 ring-1 ring-amber-100">
                            {explainApproval(approval)}
                          </div>
                          <ApprovalPayloadSummary approval={approval} />
                        </button>
                      ))}
                    </div>
                  ) : (
                    <DashboardEmptyState
                      title="Очередь решений пуста"
                      description="Когда агент остановится на ручном подтверждении, решение появится здесь."
                    />
                  )}
                </DashboardSection>
              </div>
            ) : null}
          </div>
        </details>
      ) : null}
    </div>
  );
};

const CreateAgentWizard = ({
  step,
  prompt,
  selectedScenario,
  scenarios,
  examples,
  dataSources,
  extractionRules,
  processingRules,
  outputFormat,
  manualControl,
  sourceName,
  sourceText,
  fileSource,
  internalSource,
  actionLoading,
  canCreate,
  onStepChange,
  onScenarioSelect,
  onPromptChange,
  onDataSourcesChange,
  onExtractionRulesChange,
  onProcessingRulesChange,
  onOutputFormatChange,
  onManualControlChange,
  onSourceNameChange,
  onSourceTextChange,
  onFileSourceChange,
  onInternalSourceChange,
  onCreate,
}: {
  step: number;
  prompt: string;
  selectedScenario: AgentBuilderScenario;
  scenarios: AgentBuilderScenario[];
  examples: string[];
  dataSources: string;
  extractionRules: string;
  processingRules: string;
  outputFormat: string;
  manualControl: string;
  sourceName: string;
  sourceText: string;
  fileSource: File | null;
  internalSource: string;
  actionLoading: boolean;
  canCreate: boolean;
  onStepChange: (value: number) => void;
  onScenarioSelect: (scenario: AgentBuilderScenario) => void;
  onPromptChange: (value: string) => void;
  onDataSourcesChange: (value: string) => void;
  onExtractionRulesChange: (value: string) => void;
  onProcessingRulesChange: (value: string) => void;
  onOutputFormatChange: (value: string) => void;
  onManualControlChange: (value: string) => void;
  onSourceNameChange: (value: string) => void;
  onSourceTextChange: (value: string) => void;
  onFileSourceChange: (value: File | null) => void;
  onInternalSourceChange: (value: string) => void;
  onCreate: () => void;
}) => {
  const steps = ['Тип агента', 'Данные', 'Правила и контроль', 'Результат'];
  const handleBuilderFile = async (file?: File | null) => {
    if (!file) {
      onFileSourceChange(null);
      return;
    }
    onFileSourceChange(file);
  };

  return (
    <div className="space-y-5">
      <div className="grid gap-2 md:grid-cols-4">
        {steps.map((label, index) => (
          <button
            key={label}
            type="button"
            className={cn(
              'rounded-xl border px-3 py-2 text-left text-sm font-medium transition',
              step === index ? 'border-slate-900 bg-slate-950 text-white' : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300',
            )}
            onClick={() => onStepChange(index)}
          >
            <span className="mr-2 inline-flex h-5 w-5 items-center justify-center rounded-full bg-white/15 text-xs">{index + 1}</span>
            {label}
          </button>
        ))}
      </div>

      {step === 0 ? (
        <div className="space-y-4">
          <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-4">
            {scenarios.map((scenario) => {
              const Icon = scenario.icon;
              const selected = scenario.category === selectedScenario.category;
              return (
                <button
                  key={scenario.category}
                  type="button"
                  className={cn(
                    'rounded-xl border px-3 py-3 text-left transition',
                    selected ? 'border-slate-900 bg-slate-950 text-white' : 'border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50',
                  )}
                  onClick={() => onScenarioSelect(scenario)}
                >
                  <div className="flex items-center gap-2">
                    <Icon className="h-4 w-4 shrink-0" />
                    <span className="text-sm font-semibold">{scenario.title}</span>
                  </div>
                  <div className={cn('mt-1 line-clamp-2 text-xs leading-5', selected ? 'text-slate-300' : 'text-slate-500')}>
                    {scenario.description}
                  </div>
                </button>
              );
            })}
          </div>
          <textarea
            className="min-h-32 w-full resize-none rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm leading-6 text-slate-900 outline-none transition focus:border-slate-400"
            value={prompt}
            onChange={(event) => onPromptChange(event.target.value)}
            placeholder="Опишите, какого агента хотите создать"
          />
          <div className="flex flex-wrap gap-2">
            {examples.map((example) => (
              <button
                key={example}
                type="button"
                className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 transition hover:border-slate-300 hover:text-slate-950"
                onClick={() => onPromptChange(example)}
              >
                {example}
              </button>
            ))}
          </div>
        </div>
      ) : null}

      {step === 1 ? (
        <div className="grid gap-4 lg:grid-cols-[1fr_20rem]">
          <div className="space-y-3">
            <WizardTextArea label="Какие данные использовать" value={dataSources} onChange={onDataSourcesChange} placeholder="Файл, текст, профиль бизнеса, услуги, отзывы" />
            <div className="rounded-xl border border-slate-200 bg-white px-3 py-3 text-sm leading-6 text-slate-600">
              <div className="font-medium text-slate-950">Что уже будет подключено</div>
              <div className="mt-1">
                {[
                  sourceText.trim() ? `текст “${sourceName.trim() || 'Контекст для агента'}”` : '',
                  fileSource ? `файл ${fileSource.name}` : '',
                  internalSource !== 'none' ? humanizeMeta(internalSource) : '',
                ].filter(Boolean).join(', ') || 'пока ничего; добавьте текст, файл или источник LocalOS'}
              </div>
              <div className="mt-2 text-xs text-slate-500">
                PDF, DOCX и XLSX читаются на backend. Если текст извлечь не получится, агент покажет понятную ошибку и не запустит внешнее действие.
              </div>
            </div>
          </div>
          <div className="space-y-3 rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
            <input
              className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400"
              value={sourceName}
              onChange={(event) => onSourceNameChange(event.target.value)}
              placeholder="Название источника"
            />
            <textarea
              className="min-h-28 w-full resize-none rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400"
              value={sourceText}
              onChange={(event) => onSourceTextChange(event.target.value)}
              placeholder="Вставьте текст, CSV или контекст задачи"
            />
            <div className="flex flex-wrap gap-2">
              <label className="inline-flex cursor-pointer items-center rounded-md border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50">
                <Upload className="mr-2 h-4 w-4" />
                {fileSource ? fileSource.name : 'Файл'}
                <input
                  type="file"
                  className="hidden"
                  accept=".txt,.csv,.tsv,.md,.pdf,.docx,.xlsx"
                  onChange={(event) => {
                    void handleBuilderFile(event.target.files?.[0] || null);
                    event.target.value = '';
                  }}
                />
              </label>
              {fileSource ? (
                <Button type="button" size="sm" variant="outline" onClick={() => onFileSourceChange(null)}>
                  Убрать
                </Button>
              ) : null}
            </div>
            <select
              className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400"
              value={internalSource}
              onChange={(event) => onInternalSourceChange(event.target.value)}
            >
              <option value="business_profile">Профиль бизнеса</option>
              <option value="services">Услуги</option>
              <option value="reviews">Отзывы</option>
              <option value="prospectingleads">Лиды</option>
              <option value="outreach_drafts">Черновики outreach</option>
              <option value="none">Не подключать источник LocalOS</option>
            </select>
          </div>
        </div>
      ) : null}

      {step === 2 ? (
        <div className="grid gap-3 md:grid-cols-2">
          <WizardTextArea label="Что агент должен извлечь или понять" value={extractionRules} onChange={onExtractionRulesChange} placeholder="Поля, риски, сроки, исключения, факты" />
          <WizardTextArea label="Какие правила применить" value={processingRules} onChange={onProcessingRulesChange} placeholder="Не придумывать факты, учитывать стиль, помечать спорное" />
          <WizardTextArea label="Где нужен ручной контроль" value={manualControl} onChange={onManualControlChange} placeholder="Перед отправкой, публикацией, платежом, изменением данных" />
          <div className="rounded-xl border border-emerald-100 bg-emerald-50 px-4 py-4 text-sm leading-6 text-emerald-900">
            Первые версии агентов готовят результат и ждут проверки. Внешние отправки, публикации, платежи и опасные изменения не запускаются из мастера.
          </div>
        </div>
      ) : null}

      {step === 3 ? (
        <div className="grid gap-4 lg:grid-cols-[1fr_20rem]">
          <WizardTextArea label="Какой результат подготовить" value={outputFormat} onChange={onOutputFormatChange} placeholder="Отчёт, письмо, таблица, shortlist, черновики" />
          <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4 text-sm leading-6 text-slate-700">
            <div className="font-semibold text-slate-950">{selectedScenario.title}</div>
            <div className="mt-2">{prompt || selectedScenario.prompt}</div>
            <div className="mt-4 space-y-2">
              <PreviewRow label="Данные" value={dataSources || 'уточнить'} />
              <PreviewRow label="Что понял" value={extractionRules || 'уточнить'} />
              <PreviewRow label="Правила" value={processingRules || 'уточнить'} />
              <PreviewRow label="Ручной контроль" value={manualControl || 'перед внешним действием'} />
            </div>
            <div className="mt-3 text-xs text-slate-500">
              После создания LocalOS сразу откроет карточку агента. Там будут данные, активная версия, запуск и журнал результатов.
            </div>
          </div>
        </div>
      ) : null}

      <DialogFooter className="gap-2 sm:justify-between">
        <Button type="button" variant="outline" onClick={() => onStepChange(Math.max(0, step - 1))} disabled={step === 0}>
          Назад
        </Button>
        {step < 3 ? (
          <Button type="button" onClick={() => onStepChange(Math.min(3, step + 1))}>
            Далее
          </Button>
        ) : (
          <Button type="button" onClick={onCreate} disabled={actionLoading || !canCreate}>
            {actionLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Sparkles className="mr-2 h-4 w-4" />}
            Создать агента
          </Button>
        )}
      </DialogFooter>
    </div>
  );
};

const DialogAgentBuilder = ({
  input,
  reply,
  session,
  actionLoading,
  onInputChange,
  onReplyChange,
  onStart,
  onSendReply,
  onCreate,
  selectedConnectionBindings,
  selectedProviderRoutes,
  acceptedCompilerPlan,
  acceptedProviderRoutes,
  onAcceptCompilerPlan,
  onAcceptProviderRoutes,
  onSelectConnectionBinding,
  onSelectProviderRoute,
}: {
  input: string;
  reply: string;
  session: AgentBuilderSession | null;
  actionLoading: boolean;
  onInputChange: (value: string) => void;
  onReplyChange: (value: string) => void;
  onStart: () => void;
  onSendReply: () => void;
  onCreate: () => void;
  selectedConnectionBindings: Record<string, string>;
  selectedProviderRoutes: Record<string, string>;
  acceptedCompilerPlan: boolean;
  acceptedProviderRoutes: boolean;
  onAcceptCompilerPlan: () => void;
  onAcceptProviderRoutes: () => void;
  onSelectConnectionBinding: (bindingKey: string, integrationId: string) => void;
  onSelectProviderRoute: (bindingKey: string, routeProvider: string) => void;
}) => {
  const preview = session?.preview || null;
  const questions = session?.missing_questions || [];
  const messages = session?.messages || [];
  const estimatedCredits = Number(preview?.cost_preview?.estimated_credits || 0);
  const connectionSummaryItems = preview?.connection_summary?.items || [];
  const requiredConnectionChoices = connectionSummaryItems.filter((item) => item.action === 'choose_existing' && item.key && (item.connections?.length || 0) > 1);
  const missingConnectionChoices = requiredConnectionChoices.filter((item) => !selectedConnectionBindings[item.key || '']);
  const compilerPlanRequiresConfirmation = builderCompilerPlanRequiresConfirmation(preview);
  const missingCompilerPlanConfirmation = compilerPlanRequiresConfirmation && !acceptedCompilerPlan;
  const requiredProviderRouteKeys = builderRequiredProviderRouteKeys(preview);
  const missingProviderRouteKeys = requiredProviderRouteKeys.filter((key) => !selectedProviderRoutes[key]);
  const providerRoutesRequireConfirmation = requiredProviderRouteKeys.length > 0;
  const missingProviderRouteConfirmation = providerRoutesRequireConfirmation && (!acceptedProviderRoutes || missingProviderRouteKeys.length > 0);
  const canCreateDraft = preview?.setup_flow?.can_create_draft !== false
    && !missingConnectionChoices.length
    && !missingCompilerPlanConfirmation
    && !missingProviderRouteKeys.length
    && !missingProviderRouteConfirmation;
  const createBlockers: Array<{ key: string; label: string }> = [];
  const addCreateBlocker = (key: string, label: string) => {
    const cleanKey = key.trim();
    const cleanLabel = label.trim();
    if (!cleanKey || !cleanLabel || createBlockers.some((item) => item.key === cleanKey || item.label === cleanLabel)) {
      return;
    }
    createBlockers.push({ key: cleanKey, label: cleanLabel });
  };
  questions.slice(0, 4).forEach((question) => {
    addCreateBlocker(`question:${question.key || question.question}`, question.question || 'Ответьте на уточнение.');
  });
  missingConnectionChoices.slice(0, 4).forEach((item) => {
    addCreateBlocker(`choice:${item.key || item.provider}`, `Выберите подключение ${item.title || connectorLabel(item.provider)}.`);
  });
  if (missingCompilerPlanConfirmation) {
    addCreateBlocker('compiler_plan_confirmation', 'Подтвердите план перед созданием агента.');
  }
  if (missingProviderRouteKeys.length) {
    addCreateBlocker('provider_route_selection', `Выберите способ подключения для шагов: ${missingProviderRouteKeys.join(', ')}.`);
  } else if (missingProviderRouteConfirmation) {
    addCreateBlocker('provider_route_confirmation', 'Подтвердите выбранные маршруты выполнения.');
  }
  preview?.setup_flow?.activation_blockers?.slice(0, 4).forEach((item) => {
    addCreateBlocker(`blocker:${item.type || item.provider || item.message}`, item.message || connectorLabel(item.provider));
  });
  preview?.connection_summary?.forbidden?.slice(0, 2).forEach((item) => {
    addCreateBlocker(`forbidden:${item.term || item.reason}`, item.reason || 'Запрос запрещён policy envelope LocalOS.');
  });
  preview?.connection_summary?.unsupported?.slice(0, 2).forEach((item) => {
    addCreateBlocker(`unsupported:${item.capability || item.reason}`, item.reason || 'Нет разрешённого provider path.');
  });
  const createDraftLabel = preview?.setup_flow?.post_create_status === 'ready_for_preview'
    ? 'Создать агента и открыть preview'
    : missingConnectionChoices.length
      ? 'Сначала выберите подключение'
      : missingProviderRouteKeys.length
        ? 'Сначала выберите маршруты'
        : missingProviderRouteConfirmation
          ? 'Подтвердите маршруты'
          : preview?.setup_flow?.post_create_status === 'needs_connection' || preview?.setup_flow?.post_create_status === 'needs_connection_choice'
      ? 'Создать агента и подключить сервисы'
      : 'Создать агента';
  const builderDecision = buildBuilderCreationDecision({
    preview,
    questions,
    missingConnectionChoices,
    missingProviderRouteKeys,
    missingProviderRouteConfirmation,
    canCreateDraft,
    createDraftLabel,
  });
  return (
    <div className="space-y-4 rounded-2xl border border-slate-200 bg-white p-4">
      <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto]">
        <textarea
          className="min-h-28 resize-none rounded-xl border border-slate-200 px-3 py-2 text-sm leading-6 outline-none transition focus:border-slate-400"
          value={input}
          onChange={(event) => onInputChange(event.target.value)}
          placeholder="Например: мне нужен агент, который проверяет договоры, находит риски и готовит краткий отчёт"
        />
        <Button type="button" onClick={onStart} disabled={actionLoading || !input.trim()}>
          {actionLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Sparkles className="mr-2 h-4 w-4" />}
          Начать диалог
        </Button>
      </div>

      {session ? (
        <div className="grid gap-4 lg:grid-cols-[minmax(0,0.95fr)_minmax(20rem,1.05fr)]">
          <div className="space-y-3">
            <div className="text-sm font-semibold text-slate-950">Диалог настройки</div>
            <div className="max-h-72 space-y-2 overflow-auto rounded-xl bg-slate-50 p-3">
              {messages.slice(-6).map((message, index) => (
                <div
                  key={`${message.role}-${index}-${message.content.slice(0, 12)}`}
                  className={cn(
                    'rounded-xl px-3 py-2 text-sm leading-6',
                    message.role === 'user' ? 'ml-8 bg-slate-950 text-white' : 'mr-8 bg-white text-slate-700 ring-1 ring-slate-200',
                  )}
                >
                  {message.content}
                </div>
              ))}
            </div>
            {questions.length ? (
              <div className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-3">
                <div className="text-sm font-semibold text-amber-900">Нужно уточнить</div>
                <div className="mt-2 space-y-1">
                  {questions.map((question) => (
                    <div key={question.key || question.question} className="text-sm leading-6 text-amber-900">
                      <span>{question.question}</span>
                      {question.reason === 'connection_resolver' ? (
                        <span className="ml-2 rounded-full bg-white px-2 py-0.5 text-[11px] font-medium text-amber-800 ring-1 ring-amber-200">
                          подключение
                        </span>
                      ) : null}
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-3 text-sm text-emerald-900">
                Данных достаточно для первой версии агента. После создания можно добавить файлы и источники.
              </div>
            )}
            <div className="grid gap-2 md:grid-cols-[1fr_auto]">
              <textarea
                className="min-h-16 resize-none rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none transition focus:border-slate-400"
                value={reply}
                onChange={(event) => onReplyChange(event.target.value)}
                placeholder="Ответьте на уточнение или добавьте правило"
              />
              <Button type="button" variant="outline" onClick={onSendReply} disabled={actionLoading || !reply.trim()}>
                Ответить
              </Button>
            </div>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="text-sm font-semibold text-slate-950">Проверка будущего агента</div>
                <div className="mt-1 text-xs text-slate-500">Проверьте задачу, данные, правила и ручной контроль перед созданием.</div>
              </div>
              <div className="flex flex-wrap gap-2">
                <span className="rounded-full bg-white px-2.5 py-1 text-xs font-medium text-slate-700 ring-1 ring-slate-200">
                  {preview?.category_label || humanizeCategory(session.category)}
                </span>
                {estimatedCredits > 0 ? (
                  <span className="rounded-full bg-sky-50 px-2.5 py-1 text-xs font-medium text-sky-700 ring-1 ring-sky-200">
                    ~{estimatedCredits} кредита
                  </span>
                ) : null}
              </div>
            </div>
            <div className="mt-4 space-y-3 text-sm leading-6 text-slate-700">
              <PreviewRow label="Понял задачу так" value={preview?.understood_task || input} />
              <PreviewRow label="Данные" value={(preview?.data_sources || []).map((item) => humanizeMeta(item)).join(', ') || 'уточнить'} />
              <PreviewRow label="Что извлечь" value={preview?.extraction_rules || 'уточнить'} />
              <PreviewRow label="Правила" value={preview?.processing_rules || 'уточнить'} />
              <PreviewRow label="Результат" value={preview?.output_format || 'уточнить'} />
              <PreviewRow label="Ручной контроль" value={preview?.manual_control || 'перед внешним действием'} />
            </div>
            <BuilderCreationDecisionBanner
              decision={builderDecision}
              actionLoading={actionLoading}
              canSendReply={Boolean(reply.trim())}
              canCreateDraft={canCreateDraft}
              onSendReply={onSendReply}
              onCreate={onCreate}
            />
            <BuilderRequiredConnectionsPanel
              preview={preview}
              selectedProviderRoutes={selectedProviderRoutes}
              onSelectProviderRoute={onSelectProviderRoute}
            />
            <BuilderCompilerPolicyReviewPanel
              review={preview?.compiler_policy_review}
              workflowDraft={preview?.compiler_workflow_draft}
              approvalPoints={preview?.compiler_approval_points}
              unsupportedRequests={preview?.compiler_unsupported_requests}
              accepted={acceptedCompilerPlan}
              onAccept={onAcceptCompilerPlan}
            />
            <BuilderServiceIntelligencePanel
              intelligence={preview?.service_intelligence}
              selectedProviderRoutes={selectedProviderRoutes}
              onSelectProviderRoute={onSelectProviderRoute}
            />
            <BuilderConnectionReadinessPanel
              readiness={preview?.connection_readiness}
              answerBindings={preview?.connection_answer_bindings}
              selectedProviderRoutes={selectedProviderRoutes}
              acceptedProviderRoutes={acceptedProviderRoutes}
              missingProviderRouteKeys={missingProviderRouteKeys}
              onAcceptProviderRoutes={onAcceptProviderRoutes}
              onSelectProviderRoute={onSelectProviderRoute}
            />
            <BuilderConnectionResolverPanel resolver={preview?.connection_resolver} />
            <BuilderSetupFlowPanel setupFlow={preview?.setup_flow} />
            <BuilderExecutionBoundaryPanel plannerLoop={preview?.openclaw_planner_loop} />
            <BuilderConnectionSummaryPanel
              summary={preview?.connection_summary}
              selectedBindings={selectedConnectionBindings}
              onSelectBinding={onSelectConnectionBinding}
            />
            {missingConnectionChoices.length ? (
              <div className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-950">
                Выберите, какие уже подключённые сервисы использовать: {missingConnectionChoices.map((item) => item.title || connectorLabel(item.provider)).join(', ')}. После этого LocalOS привяжет их к compiled workflow.
              </div>
            ) : null}
            <BuilderTechnicalDiagnostics
              connectorIntelligence={preview?.connector_intelligence}
              plannerLoop={preview?.openclaw_planner_loop}
              connectionPlan={preview?.connection_plan || null}
              feasibility={preview?.feasibility}
              connectors={preview?.required_connectors}
            />
            {estimatedCredits > 0 ? (
              <div className="mt-3 rounded-xl border border-sky-200 bg-sky-50 px-3 py-2 text-xs leading-5 text-sky-900">
                Создание агента спишет примерно {estimatedCredits} кредита с баланса. Если кредитов не хватит, предложим пополнить счёт.
              </div>
            ) : null}
            {!canCreateDraft && createBlockers.length ? (
              <div className="mt-3 rounded-xl border border-amber-200 bg-white px-3 py-3 text-xs leading-5 text-amber-950">
                <div className="font-semibold">Почему агента пока нельзя создать</div>
                <div className="mt-1 text-[11px] leading-4 text-amber-800">
                  LocalOS должен собрать проверяемый workflow до создания агента.
                </div>
                <div className="mt-2 space-y-1">
                  {createBlockers.slice(0, 5).map((item) => (
                    <div key={item.key} className="flex gap-2">
                      <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                      <span>{item.label}</span>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
            <div className="mt-4 flex flex-wrap items-center justify-end gap-2">
              {!canCreateDraft && preview?.setup_flow?.next_step_title ? (
                <span className="text-xs leading-5 text-slate-500">{preview.setup_flow.next_step_title}</span>
              ) : null}
              <Button type="button" onClick={onCreate} disabled={actionLoading || !canCreateDraft}>
                {actionLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <CheckCircle2 className="mr-2 h-4 w-4" />}
                {canCreateDraft ? createDraftLabel : 'Сначала завершите настройку'}
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
};

const BuilderTechnicalDiagnostics = ({
  connectorIntelligence,
  plannerLoop,
  connectionPlan,
  feasibility,
  connectors,
}: {
  connectorIntelligence?: AgentConnectorIntelligence;
  plannerLoop?: AgentBuilderPlannerLoop;
  connectionPlan?: AgentConnectionPlan | null;
  feasibility?: AgentBuilderFeasibility;
  connectors?: AgentBuilderConnectorPreview[];
}) => {
  const hasDetails = Boolean(
    connectorIntelligence
    || plannerLoop
    || connectionPlan
    || feasibility
    || (connectors && connectors.length),
  );
  if (!hasDetails) {
    return <CompiledBuilderFlow compact />;
  }
  return (
    <details className="mt-3 rounded-xl border border-slate-200 bg-white px-3 py-3 text-xs leading-5 text-slate-700">
      <summary className="cursor-pointer font-semibold text-slate-950">
        Техническая диагностика LocalOS/OpenClaw
      </summary>
      <div className="mt-1 text-[11px] leading-4 text-slate-500">
        Для проверки: provider paths, capability map, preflight и policy envelope. Обычный следующий шаг показан выше.
      </div>
      <div className="mt-3">
        <CompiledBuilderFlow compact />
        <ConnectorIntelligencePanel intelligence={connectorIntelligence} />
        <BuilderPlannerLoopPanel plannerLoop={plannerLoop} />
        <AgentConnectionPlanPanel connectionPlan={connectionPlan || null} compact />
        <BuilderFeasibilityPanel feasibility={feasibility} connectors={connectors} />
      </div>
    </details>
  );
};

const CompiledBuilderFlow = ({ compact = false }: { compact?: boolean }) => (
  <div className={cn(compact ? 'mt-0' : 'mt-4', 'rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-3 text-xs leading-5 text-emerald-950')}>
    <div className="font-semibold">После создания LocalOS скомпилирует агента</div>
    <div className="mt-2 grid gap-2 sm:grid-cols-4">
      {[
        ['1', 'План', 'задача и шаги'],
        ['2', 'Проверка', 'capabilities и approvals'],
        ['3', 'Доступы', 'что нужно подключить'],
        ['4', 'Запуск', 'только после gate'],
      ].map(([index, title, text]) => (
        <div key={title} className="rounded-lg bg-white/70 px-2 py-2 ring-1 ring-emerald-100">
          <div className="flex items-center gap-2 font-medium">
            <span className="flex h-5 w-5 items-center justify-center rounded-full bg-emerald-100 text-[11px] text-emerald-800">{index}</span>
            {title}
          </div>
          <div className="mt-1 text-emerald-800">{text}</div>
        </div>
      ))}
    </div>
    <div className="mt-2 text-emerald-800">
      Внешние отправки, публикации, платежи и опасные изменения не запускаются из мастера. Рискованные действия требуют ручного подтверждения.
    </div>
  </div>
);

const BuilderCreationDecisionBanner = ({
  decision,
  actionLoading,
  canSendReply,
  canCreateDraft,
  onSendReply,
  onCreate,
}: {
  decision: AgentConnectionDecision;
  actionLoading: boolean;
  canSendReply: boolean;
  canCreateDraft: boolean;
  onSendReply: () => void;
  onCreate: () => void;
}) => {
  const ready = decision.tone === 'ready';
  const choice = decision.tone === 'choice';
  const blocked = decision.tone === 'blocked';
  const needsAction = decision.tone === 'needs_action';
  const canClick = decision.action === 'answer'
    ? canSendReply
    : decision.action === 'create'
    ? canCreateDraft
    : false;
  return (
    <div className={cn(
      'mt-4 rounded-xl border px-3 py-3',
      ready ? 'border-emerald-200 bg-emerald-50' : '',
      choice ? 'border-sky-200 bg-sky-50' : '',
      needsAction ? 'border-amber-200 bg-amber-50' : '',
      blocked ? 'border-rose-200 bg-rose-50' : '',
      !ready && !choice && !needsAction && !blocked ? 'border-slate-200 bg-white' : '',
    )}>
      <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
        <div>
          <div className={cn('text-sm font-semibold', ready ? 'text-emerald-950' : choice ? 'text-sky-950' : needsAction ? 'text-amber-950' : blocked ? 'text-rose-950' : 'text-slate-950')}>
            {decision.title}
          </div>
          <div className={cn('mt-1 text-xs leading-5', ready ? 'text-emerald-800' : choice ? 'text-sky-800' : needsAction ? 'text-amber-900' : blocked ? 'text-rose-900' : 'text-slate-600')}>
            {decision.description}
          </div>
        </div>
        {decision.cta ? (
          <Button
            type="button"
            size="sm"
            variant={ready || decision.action === 'create' ? 'default' : 'outline'}
            className={cn(!(ready || decision.action === 'create') && 'bg-white')}
            disabled={actionLoading || !canClick}
            onClick={() => {
              if (decision.action === 'answer') {
                onSendReply();
                return;
              }
              if (decision.action === 'create') {
                onCreate();
              }
            }}
          >
            {actionLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : decision.action === 'answer' ? <MessageSquareText className="mr-2 h-4 w-4" /> : <CheckCircle2 className="mr-2 h-4 w-4" />}
            {decision.cta}
          </Button>
        ) : null}
      </div>
    </div>
  );
};

const BuilderRequiredConnectionsPanel = ({
  preview,
  selectedProviderRoutes = {},
  onSelectProviderRoute,
}: {
  preview?: AgentBuilderPreview | null;
  selectedProviderRoutes?: Record<string, string>;
  onSelectProviderRoute?: (bindingKey: string, routeProvider: string) => void;
}) => {
  const planItems = preview?.connection_plan?.items || [];
  const readinessServices = preview?.connection_readiness?.services || [];
  const answerBindings = preview?.connection_answer_bindings || {};
  const items = planItems.length
    ? planItems.map((item) => ({
      key: item.key || '',
      provider: item.provider || '',
      title: item.title || connectorLabel(item.provider),
      capability: item.capability || item.trigger || item.direction || '',
      action: item.action || '',
      status: item.binding_status || '',
      route_summary: item.route_summary || item.explanation || '',
      missing_config: item.missing_config || [],
      provider_routes: item.provider_routes || [],
      recommended_route: item.recommended_route || null,
      recommended_route_reason: item.recommended_route_reason || '',
      policy_summary: item.policy_summary || '',
    }))
    : readinessServices.map((service) => ({
      key: service.key || '',
      provider: service.provider || '',
      title: service.title || connectorLabel(service.provider),
      capability: service.capability || '',
      action: service.action || service.status || '',
      status: service.status || '',
      route_summary: service.route_summary || service.explanation || '',
      missing_config: service.missing_config || [],
      provider_routes: [],
      recommended_route: service.recommended_route || null,
      recommended_route_reason: service.recommended_route_reason || '',
      policy_summary: '',
    }));
  if (!preview || !items.length) {
    return null;
  }
  const actionable = items.filter((item) => !['ready', 'native_ready'].includes(item.action));
  const blocked = actionable.some((item) => ['forbidden', 'unsupported', 'planned_provider'].includes(item.action));
  const ready = actionable.length === 0;
  const toneClass = blocked
    ? 'border-rose-200 bg-rose-50 text-rose-950'
    : ready
    ? 'border-emerald-200 bg-emerald-50 text-emerald-950'
    : 'border-amber-200 bg-amber-50 text-amber-950';
  const badgeText = ready
    ? 'доступы готовы'
    : blocked
    ? 'есть блокер'
    : `${actionable.length} нужно закрыть`;
  return (
    <div className={cn('mt-3 rounded-xl border px-3 py-3 text-xs leading-5', toneClass)}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="font-semibold">Доступы перед созданием агента</div>
          <div className="mt-1 max-w-2xl">
            LocalOS понял, какие сервисы нужны workflow. Ресурс из диалога сохраняется отдельно от доступа: перед preview нужно выбрать provider route или подключение.
          </div>
        </div>
        <span className="rounded-full bg-white px-2 py-0.5 font-medium ring-1 ring-current/10">
          {badgeText}
        </span>
      </div>

      <div className="mt-3 grid gap-2 md:grid-cols-2">
        {items.slice(0, 4).map((item) => {
          const bindingKey = item.key || item.provider || '';
          const recommendedProvider = item.recommended_route?.provider || '';
          const selected = Boolean(bindingKey && recommendedProvider && selectedProviderRoutes[bindingKey] === recommendedProvider);
          const resourceFacts = connectionResourceFacts(item.provider, bindingKey ? answerBindings[bindingKey] : null);
          const missingConfig = item.missing_config || [];
          return (
            <div key={`${bindingKey}-${item.provider}-${item.capability}`} className="rounded-lg bg-white px-3 py-2 text-slate-700 ring-1 ring-current/10">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="font-medium text-slate-950">{item.title || connectorLabel(item.provider)}</div>
                  <div className="mt-0.5 text-[11px] leading-4 text-slate-500">{humanizeMeta(item.capability || item.provider || 'binding')}</div>
                </div>
                <span className={cn('rounded-full px-2 py-0.5 text-[11px] font-medium ring-1', connectionActionTone(item.action || item.status || ''))}>
                  {builderConnectionCardStatus(item.action, selected)}
                </span>
              </div>
              {resourceFacts.length ? (
                <div className="mt-2 rounded-lg bg-emerald-50 px-2 py-1.5 text-[11px] leading-4 text-emerald-800 ring-1 ring-emerald-100">
                  Ресурс из диалога: {resourceFacts.join(' · ')}
                </div>
              ) : null}
              <div className="mt-2 text-[11px] leading-4 text-slate-600">
                {item.route_summary || builderConnectionCardHint(item.action, item.provider)}
              </div>
              {missingConfig.length ? (
                <div className="mt-2 rounded-lg bg-amber-50 px-2 py-1.5 text-[11px] leading-4 text-amber-800 ring-1 ring-amber-100">
                  Не хватает настроек: {missingConfig.join(', ')}
                </div>
              ) : null}
              <RecommendedProviderRouteNote
                route={item.recommended_route}
                reason={item.recommended_route_reason}
              />
              {item.policy_summary ? (
                <div className="mt-2 rounded-lg bg-slate-50 px-2 py-1.5 text-[11px] leading-4 text-slate-600 ring-1 ring-slate-100">
                  {item.policy_summary}
                </div>
              ) : null}
              {item.provider_routes.length ? (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {item.provider_routes.slice(0, 4).map((route) => (
                    <ProviderActionPill
                      key={`${bindingKey}-${route.provider}-${route.role}`}
                      route={route}
                      onChoose={onSelectProviderRoute && bindingKey ? () => onSelectProviderRoute(bindingKey, route.provider || '') : undefined}
                    />
                  ))}
                </div>
              ) : null}
              {bindingKey && recommendedProvider && onSelectProviderRoute && !selected ? (
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  className="mt-2 h-7 bg-white px-2 text-[11px]"
                  onClick={() => onSelectProviderRoute(bindingKey, recommendedProvider)}
                >
                  Использовать {connectorLabel(recommendedProvider)}
                </Button>
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
};

const builderConnectionCardStatus = (action: string, selected: boolean) => {
  if (selected) {
    return 'способ выбран';
  }
  if (action === 'ready' || action === 'native_ready') {
    return 'готово';
  }
  if (action === 'choose_existing') {
    return 'выбрать доступ';
  }
  if (action === 'choose_route') {
    return 'выбрать маршрут';
  }
  if (action === 'connect_required') {
    return 'нужен способ';
  }
  if (action === 'planned_provider') {
    return 'позже';
  }
  if (action === 'forbidden' || action === 'unsupported') {
    return 'невозможно';
  }
  return humanizeMeta(action || 'проверить');
};

const builderConnectionCardHint = (action: string, provider: string) => {
  if (action === 'ready' || action === 'native_ready') {
    return 'Этот доступ уже можно использовать в safe preview.';
  }
  if (action === 'choose_existing') {
    return 'У бизнеса есть несколько подходящих подключений. Выберите одно для compiled workflow.';
  }
  if (action === 'choose_route') {
    return 'Выберите маршрут выполнения: существующий доступ, OpenClaw boundary, Maton key или ручной fallback.';
  }
  if (action === 'connect_required') {
    return `${connectorLabel(provider)} нужен workflow, но доступ ещё не выбран.`;
  }
  if (action === 'planned_provider') {
    return 'Этот provider path запланирован, но пока недоступен для activation.';
  }
  return 'LocalOS проверит этот доступ перед safe preview.';
};

const compilerPolicyItemLabel = (item?: AgentCompilerPolicyItem | null): string => {
  if (!item) {
    return '';
  }
  return String(
    item.title
    || item.message
    || item.reason
    || item.request
    || item.capability
    || item.provider
    || item.type
    || item.key
    || item.text
    || '',
  ).trim();
};

const builderCompilerPlanRequiresConfirmation = (preview?: AgentBuilderPreview | null): boolean => {
  const review = preview?.compiler_policy_review || null;
  const draft = preview?.compiler_workflow_draft || review?.workflow_draft || {};
  const steps = Array.isArray(draft.steps) ? draft.steps : [];
  const approvals = preview?.compiler_approval_points || review?.approval_points || [];
  const blockers = preview?.compiler_unsupported_requests || review?.unsupported_requests || [];
  return Boolean(draft.trigger || steps.length || approvals.length || blockers.length);
};

const BuilderCompilerPolicyReviewPanel = ({
  review,
  workflowDraft,
  approvalPoints,
  unsupportedRequests,
  accepted,
  onAccept,
}: {
  review?: AgentCompilerPolicyReview;
  workflowDraft?: AgentCompilerWorkflowDraft;
  approvalPoints?: AgentCompilerPolicyItem[];
  unsupportedRequests?: AgentCompilerPolicyItem[];
  accepted?: boolean;
  onAccept?: () => void;
}) => {
  const draft = workflowDraft || review?.workflow_draft || {};
  const steps = Array.isArray(draft.steps) ? draft.steps : [];
  const approvals = approvalPoints || review?.approval_points || [];
  const blockers = unsupportedRequests || review?.unsupported_requests || [];
  const hasContent = Boolean(
    review
    || steps.length
    || approvals.length
    || blockers.length
    || draft.trigger,
  );
  if (!hasContent) {
    return null;
  }
  const blocked = blockers.length > 0 || review?.status === 'blocked';
  const needsApproval = approvals.length > 0 || review?.status === 'needs_approval';
  const toneClass = blocked
    ? 'border-rose-200 bg-rose-50 text-rose-950'
    : needsApproval
    ? 'border-amber-200 bg-amber-50 text-amber-950'
    : 'border-emerald-200 bg-emerald-50 text-emerald-950';
  const badgeClass = blocked
    ? 'bg-white text-rose-700 ring-rose-200'
    : needsApproval
    ? 'bg-white text-amber-700 ring-amber-200'
    : 'bg-white text-emerald-700 ring-emerald-200';
  const statusLabel = blocked ? 'есть блокер' : needsApproval ? 'нужны approvals' : 'план допустим';
  return (
    <div className={cn('mt-3 rounded-xl border px-3 py-3 text-xs leading-5', toneClass)}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="font-semibold">План агента</div>
          <div className="mt-1 max-w-2xl">
            LocalOS сохранит этот план как compiled workflow candidate и проверит его перед preview run.
          </div>
        </div>
        <span className={cn('rounded-full px-2 py-0.5 font-medium ring-1', badgeClass)}>
          {statusLabel}
        </span>
      </div>

      <div className="mt-3 grid gap-2 md:grid-cols-3">
        <AgentMiniMetric label="Trigger" value={humanizeMeta(draft.trigger || 'manual.run')} />
        <AgentMiniMetric label="Шаги" value={String(steps.length || 0)} />
        <AgentMiniMetric label="Approval" value={String(approvals.length || 0)} />
      </div>

      {steps.length ? (
        <div className="mt-3 grid gap-2">
          {steps.slice(0, 4).map((step, index) => {
            const label = compilerPolicyItemLabel(step) || `Шаг ${index + 1}`;
            const detail = step.capability || step.provider || step.type || step.key || '';
            return (
              <div key={`${label}-${index}`} className="rounded-lg bg-white px-3 py-2 text-slate-700 ring-1 ring-current/10">
                <div className="flex items-center gap-2">
                  <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-slate-100 text-[11px] font-semibold text-slate-700">
                    {index + 1}
                  </span>
                  <span className="font-medium text-slate-950">{label}</span>
                </div>
                {detail ? <div className="mt-1 pl-7 text-[11px] leading-4 text-slate-500">{humanizeMeta(detail)}</div> : null}
              </div>
            );
          })}
        </div>
      ) : null}

      {approvals.length ? (
        <div className="mt-3 rounded-lg bg-white px-3 py-2 text-amber-950 ring-1 ring-current/10">
          <div className="font-semibold">Где человек должен подтвердить</div>
          <div className="mt-2 space-y-1">
            {approvals.slice(0, 3).map((item, index) => (
              <div key={`${compilerPolicyItemLabel(item)}-${index}`} className="flex gap-2 text-[11px] leading-4">
                <ShieldCheck className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                <span>{compilerPolicyItemLabel(item) || 'Ручное подтверждение перед действием'}</span>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {blockers.length ? (
        <div className="mt-3 rounded-lg bg-white px-3 py-2 text-rose-950 ring-1 ring-current/10">
          <div className="font-semibold">Что нужно изменить в логике</div>
          <div className="mt-2 space-y-1">
            {blockers.slice(0, 3).map((item, index) => (
              <div key={`${compilerPolicyItemLabel(item)}-${index}`} className="flex gap-2 text-[11px] leading-4">
                <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                <span>{compilerPolicyItemLabel(item) || 'Часть запроса выходит за policy envelope'}</span>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {!blockers.length && onAccept ? (
        <div className={cn(
          'mt-3 rounded-lg px-3 py-2 ring-1',
          accepted ? 'bg-white text-emerald-800 ring-emerald-200' : 'bg-white text-slate-700 ring-slate-200',
        )}>
          <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
            <div className="text-[11px] leading-4">
              {accepted
                ? 'План подтверждён. LocalOS сможет создать draft и сохранить workflow candidate.'
                : 'Перед созданием draft подтвердите, что этот план соответствует задаче.'}
            </div>
            <Button type="button" size="sm" variant={accepted ? 'outline' : 'default'} onClick={onAccept} disabled={accepted}>
              <CheckCircle2 className="mr-2 h-4 w-4" />
              {accepted ? 'План принят' : 'Принять план'}
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
};

const RecommendedProviderRouteNote = ({
  route,
  reason,
}: {
  route?: AgentProviderRoute | null;
  reason?: string;
}) => {
  if (!route && !reason) {
    return null;
  }
  return (
    <div className="mt-2 rounded-lg bg-white px-2 py-1.5 text-[11px] leading-4 text-slate-700 ring-1 ring-slate-200">
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="font-medium text-slate-950">Рекомендуемый способ</span>
        {route ? <ProviderActionPill route={route} /> : null}
      </div>
      {reason ? <div className="mt-1">{reason}</div> : null}
    </div>
  );
};

const builderConnectionStatusCopy = (service: AgentConnectionReadinessService) => {
  const action = String(service.action || service.status || '').trim();
  if (action === 'ready' || action === 'native_ready') {
    return 'Можно использовать';
  }
  if (action === 'choose_existing') {
    return 'Выберите доступ';
  }
  if (action === 'choose_route') {
    return 'Выберите маршрут';
  }
  if (action === 'planned_provider') {
    return 'Пока недоступно';
  }
  if (action === 'forbidden' || action === 'unsupported') {
    return 'Невозможно';
  }
  if (action === 'connect_required') {
    return 'Нужно подключить';
  }
  return service.action_label || humanizeMeta(action || 'проверить');
};

const builderConnectionNextStepCopy = (service: AgentConnectionReadinessService, selected: boolean) => {
  if (selected) {
    return 'Этот способ будет сохранён в плане агента.';
  }
  const routeDescription = providerActionDescription(service.recommended_route || null);
  if (routeDescription) {
    return routeDescription;
  }
  if (service.connections?.length) {
    return 'Можно использовать уже сохранённое подключение бизнеса.';
  }
  if (service.provider_route_cta) {
    return service.provider_route_cta;
  }
  return service.route_summary || service.explanation || 'LocalOS проверит доступ перед safe preview.';
};

const BuilderServiceIntelligencePanel = ({
  intelligence,
  selectedProviderRoutes = {},
  onSelectProviderRoute,
}: {
  intelligence?: AgentServiceIntelligence;
  selectedProviderRoutes?: Record<string, string>;
  onSelectProviderRoute?: (bindingKey: string, routeProvider: string) => void;
}) => {
  const items = intelligence?.items || [];
  if (!intelligence || !items.length) {
    return null;
  }
  const blocked = items.some((item) => item.state === 'impossible');
  const needsChoice = items.some((item) => item.state === 'multiple_routes');
  const needsConnection = items.some((item) => item.state === 'connectable' || item.state === 'planned');
  return (
    <div className={cn(
      'mt-3 rounded-xl border px-3 py-3 text-xs leading-5',
      blocked ? 'border-rose-200 bg-rose-50 text-rose-950' : '',
      !blocked && (needsChoice || needsConnection) ? 'border-amber-200 bg-amber-50 text-amber-950' : '',
      !blocked && !needsChoice && !needsConnection ? 'border-emerald-200 bg-emerald-50 text-emerald-950' : '',
    )}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="font-semibold">Что возможно</div>
          <div className="mt-1 max-w-2xl">{intelligence.headline || 'LocalOS сопоставил задачу с доступными сервисами и policy.'}</div>
        </div>
        <span className="rounded-full bg-white px-2 py-0.5 font-medium ring-1 ring-current/10">
          {intelligence.can_activate ? 'можно preview' : intelligence.can_create_draft ? 'можно draft' : 'нельзя создать'}
        </span>
      </div>
      <div className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
        {items.slice(0, 8).map((item) => {
          const state = item.state || '';
          const provider = item.recommended_provider || item.provider || '';
          const bindingKey = item.kind === 'binding' ? item.key || '' : '';
          const route = item.recommended_route || null;
          const selected = Boolean(bindingKey && provider && selectedProviderRoutes[bindingKey] === provider);
          const canChooseRoute = Boolean(
            bindingKey
            && provider
            && route
            && ['connectable', 'multiple_routes'].includes(state)
            && ['available', 'connected', 'manual'].includes(String(route.state || route.status || ''))
            && route.provider_action?.available !== false
            && onSelectProviderRoute,
          );
          return (
            <div key={`${item.kind || 'item'}-${item.key || item.provider || item.capability}`} className="rounded-lg bg-white px-3 py-2 ring-1 ring-current/10">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <div className="font-medium text-slate-950">{item.service_label || connectorLabel(item.provider)}</div>
                  {item.capability ? <div className="mt-0.5 text-[11px] leading-4 text-slate-500">{humanizeMeta(item.capability)}</div> : null}
                </div>
                <span className={cn('rounded-full px-2 py-0.5 text-[11px] font-medium ring-1', serviceIntelligenceTone(state))}>
                  {item.state_label || humanizeMeta(state || 'проверить')}
                </span>
              </div>
              <div className="mt-1 text-[11px] leading-4 text-slate-600">
                {item.explanation || 'LocalOS проверит этот сервис перед safe preview.'}
              </div>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {provider ? (
                  <span className="rounded-full bg-sky-50 px-2 py-0.5 text-[11px] text-sky-700 ring-1 ring-sky-100">
                    {item.recommended_label || connectorLabel(provider)}
                  </span>
                ) : null}
                {item.connection_count ? (
                  <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] text-emerald-700 ring-1 ring-emerald-100">
                    {item.connection_count} доступ
                  </span>
                ) : null}
                {item.next_action ? (
                  <span className="rounded-full bg-slate-50 px-2 py-0.5 text-[11px] text-slate-600 ring-1 ring-slate-200">
                    {humanizeMeta(item.next_action)}
                  </span>
                ) : null}
              </div>
              {canChooseRoute ? (
                <Button
                  type="button"
                  size="sm"
                  variant={selected ? 'default' : 'outline'}
                  className={cn('mt-2 h-7 px-2 text-[11px]', selected ? '' : 'bg-white')}
                  onClick={() => onSelectProviderRoute?.(bindingKey, provider)}
                >
                  {selected ? 'Способ выбран' : `Использовать ${connectorLabel(provider)}`}
                </Button>
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
};

const serviceIntelligenceTone = (state: string) => {
  if (state === 'already_connected' || state === 'localos_native' || state === 'available_route') {
    return 'bg-emerald-50 text-emerald-700 ring-emerald-200';
  }
  if (state === 'multiple_routes') {
    return 'bg-sky-50 text-sky-700 ring-sky-200';
  }
  if (state === 'planned') {
    return 'bg-slate-50 text-slate-600 ring-slate-200';
  }
  if (state === 'impossible') {
    return 'bg-rose-50 text-rose-700 ring-rose-200';
  }
  return 'bg-amber-50 text-amber-700 ring-amber-200';
};

const BuilderConnectionReadinessPanel = ({
  readiness,
  answerBindings = {},
  selectedProviderRoutes = {},
  acceptedProviderRoutes = false,
  missingProviderRouteKeys = [],
  onAcceptProviderRoutes,
  onSelectProviderRoute,
}: {
  readiness?: AgentConnectionReadiness;
  answerBindings?: Record<string, Record<string, unknown>>;
  selectedProviderRoutes?: Record<string, string>;
  acceptedProviderRoutes?: boolean;
  missingProviderRouteKeys?: string[];
  onAcceptProviderRoutes?: () => void;
  onSelectProviderRoute?: (bindingKey: string, routeProvider: string) => void;
}) => {
  const services = readiness?.services || [];
  const forbidden = readiness?.forbidden || [];
  const unsupported = readiness?.unsupported || [];
  if (!readiness || (!services.length && !forbidden.length && !unsupported.length)) {
    return null;
  }
  const blocked = Boolean((readiness.blocked_count || 0) > 0 || forbidden.length || unsupported.length);
  const needsAction = Boolean((readiness.missing_count || 0) > 0 || (readiness.choice_count || 0) > 0);
  const ready = !blocked && !needsAction;
  const selectableRouteKeys = services
    .map((service) => service.key || '')
    .filter((key) => key && selectedProviderRoutes[key]);
  const canConfirmRoutes = Boolean(selectableRouteKeys.length && !missingProviderRouteKeys.length && onAcceptProviderRoutes);
  const readyCopy = ready
    ? 'Все нужные сервисы можно использовать. После создания агента запустите safe preview.'
    : needsAction
    ? 'Выберите, как LocalOS будет подключаться к нужным сервисам.'
    : 'LocalOS проверяет, какие сервисы доступны для этого агента.';
  return (
    <div className={cn(
      'mt-3 rounded-xl border px-3 py-3 text-xs leading-5',
      blocked ? 'border-rose-200 bg-rose-50 text-rose-950' : '',
      needsAction ? 'border-amber-200 bg-amber-50 text-amber-950' : '',
      ready ? 'border-emerald-200 bg-emerald-50 text-emerald-950' : '',
      !blocked && !needsAction && !ready ? 'border-slate-200 bg-white text-slate-700' : '',
    )}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="font-semibold">Что нужно агенту для работы</div>
          <div className="mt-1 max-w-2xl">{readiness.description || readyCopy}</div>
        </div>
        <span className="rounded-full bg-white px-2 py-0.5 font-medium ring-1 ring-current/10">
          {readiness.title || (ready ? 'готово к preview' : 'нужны подключения')}
        </span>
      </div>
      <div className="mt-3 grid gap-2 sm:grid-cols-4">
        <AgentMiniMetric label="Нужно" value={String(readiness.required_count || 0)} />
        <AgentMiniMetric label="Готово" value={String(readiness.ready_count || 0)} />
        <AgentMiniMetric label="Выбрать" value={String((readiness.missing_count || 0) + (readiness.choice_count || 0))} />
        <AgentMiniMetric label="Блокеры" value={String(readiness.blocked_count || 0)} />
      </div>
      {services.length ? (
        <div className="mt-3 grid gap-2 md:grid-cols-2">
          {services.slice(0, 4).map((service) => (
            <div key={service.key || service.provider || service.title} className="rounded-lg bg-white px-3 py-2 ring-1 ring-current/10">
              {(() => {
                const bindingKey = service.key || '';
                const routeProvider = service.recommended_route?.provider || '';
                const selected = Boolean(bindingKey && routeProvider && selectedProviderRoutes[bindingKey] === routeProvider);
                const statusCopy = builderConnectionStatusCopy(service);
                const nextStepCopy = builderConnectionNextStepCopy(service, selected);
                const resourceFacts = connectionResourceFacts(service.provider, bindingKey ? answerBindings[bindingKey] : null);
                return (
                  <>
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <div className="font-medium text-slate-950">{service.title || connectorLabel(service.provider)}</div>
                  <div className="mt-0.5 text-[11px] leading-4 text-slate-500">{humanizeMeta(service.capability || service.provider || 'service')}</div>
                </div>
                <span className={cn('rounded-full px-2 py-0.5 text-[11px] font-medium ring-1', connectionActionTone(service.action || ''))}>
                  {statusCopy}
                </span>
              </div>
              <div className="mt-1 text-[11px] leading-4 text-slate-600">
                {nextStepCopy}
              </div>
              {resourceFacts.length ? (
                <div className="mt-2 rounded-lg bg-emerald-50 px-2 py-1.5 text-[11px] leading-4 text-emerald-800 ring-1 ring-emerald-100">
                  Поняли ресурс: {resourceFacts.join(' · ')}
                </div>
              ) : null}
              {service.provider_route_label || service.provider_route_cta ? (
                <div className="mt-2 rounded-lg bg-slate-50 px-2 py-1.5 text-[11px] leading-4 text-slate-700 ring-1 ring-slate-200">
                  {service.provider_route_label ? `${service.provider_route_label}: ` : ''}
                  {service.provider_route_cta || providerRouteLabel(service.route_state || '')}
                </div>
              ) : null}
              <RecommendedProviderRouteNote
                route={service.recommended_route}
                reason={service.recommended_route_reason}
              />
              {bindingKey && routeProvider && onSelectProviderRoute ? (
                <div className="mt-2">
                  <Button
                    type="button"
                    size="sm"
                    variant={selected ? 'default' : 'outline'}
                    className={cn('h-7 px-2 text-[11px]', selected ? '' : 'bg-white')}
                    onClick={() => onSelectProviderRoute(bindingKey, routeProvider)}
                  >
                    {selected ? 'Способ выбран' : 'Использовать этот способ'}
                  </Button>
                </div>
              ) : null}
              {service.connections?.length ? (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {service.connections.slice(0, 3).map((connection) => (
                    <span key={connection.id || connection.display_name} className="rounded-full bg-sky-50 px-2 py-0.5 text-[11px] text-sky-700 ring-1 ring-sky-100">
                      {connection.display_name || connectorLabel(connection.provider)}
                    </span>
                  ))}
                </div>
              ) : null}
                  </>
                );
              })()}
            </div>
          ))}
        </div>
      ) : null}
      {selectableRouteKeys.length ? (
        <div className={cn(
          'mt-3 rounded-lg bg-white px-3 py-2 ring-1',
          acceptedProviderRoutes ? 'text-emerald-800 ring-emerald-200' : missingProviderRouteKeys.length ? 'text-amber-900 ring-amber-200' : 'text-slate-700 ring-slate-200',
        )}>
          <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
            <div className="text-[11px] leading-4">
              {acceptedProviderRoutes
                ? 'Способы подключения подтверждены и будут сохранены в плане агента.'
                : missingProviderRouteKeys.length
                ? `Не выбран способ подключения для: ${missingProviderRouteKeys.join(', ')}.`
                : 'Подтвердите, что LocalOS должен использовать выбранные способы подключения для этого агента.'}
            </div>
            {onAcceptProviderRoutes ? (
              <Button
                type="button"
                size="sm"
                variant={acceptedProviderRoutes ? 'outline' : 'default'}
                disabled={acceptedProviderRoutes || !canConfirmRoutes}
                onClick={onAcceptProviderRoutes}
              >
                <CheckCircle2 className="mr-2 h-4 w-4" />
                {acceptedProviderRoutes ? 'Подключения подтверждены' : 'Подтвердить подключения'}
              </Button>
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  );
};

const BuilderConnectionResolverPanel = ({ resolver }: { resolver?: AgentConnectionResolver }) => {
  const items = resolver?.items || [];
  if (!resolver || !items.length) {
    return null;
  }
  const blocked = Boolean((resolver.blocked_count || 0) > 0);
  const unresolved = Boolean((resolver.unresolved_count || 0) > 0);
  return (
    <div className={cn(
      'mt-3 rounded-xl border px-3 py-3 text-xs leading-5',
      blocked ? 'border-rose-200 bg-rose-50 text-rose-950' : unresolved ? 'border-amber-200 bg-amber-50 text-amber-950' : 'border-emerald-200 bg-emerald-50 text-emerald-950',
    )}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="font-semibold">Как LocalOS подключит сервисы</div>
          <div className="mt-1 max-w-2xl">{resolver.summary || 'LocalOS сопоставил части задачи с доступными сервисами и безопасными способами выполнения.'}</div>
        </div>
        <span className="rounded-full bg-white px-2 py-0.5 font-medium ring-1 ring-current/10">
          {resolver.next_action_label || resolver.title || 'проверить'}
        </span>
      </div>
      <div className="mt-3 grid gap-2 md:grid-cols-2">
        {items.slice(0, 6).map((item) => {
          const state = item.state || '';
          const route = item.recommended_route || null;
          const routeProvider = item.recommended_provider || route?.provider || '';
          return (
            <div key={item.key || `${item.provider}:${item.role}`} className="rounded-lg bg-white px-3 py-2 ring-1 ring-current/10">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <div className="text-[11px] font-semibold uppercase text-slate-500">{item.role_label || 'Сервис'}</div>
                  <div className="font-medium text-slate-950">{item.service_label || connectorLabel(item.provider)}</div>
                </div>
                <span className={cn('rounded-full px-2 py-0.5 text-[11px] font-medium ring-1', resolverStateTone(state))}>
                  {item.state_label || humanizeMeta(state || 'проверить')}
                </span>
              </div>
              <div className="mt-1 text-[11px] leading-4 text-slate-600">
                {item.explanation || 'LocalOS проверит этот сервис перед safe preview.'}
              </div>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {routeProvider ? (
                  <span className="rounded-full bg-sky-50 px-2 py-0.5 text-[11px] text-sky-700 ring-1 ring-sky-100">
                    {item.recommended_label || connectorLabel(routeProvider)}
                  </span>
                ) : null}
                {item.connection_count ? (
                  <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] text-emerald-700 ring-1 ring-emerald-100">
                    {item.connection_count} доступ
                  </span>
                ) : null}
                {item.missing_config?.length ? (
                  <span className="rounded-full bg-amber-50 px-2 py-0.5 text-[11px] text-amber-700 ring-1 ring-amber-100">
                    нужны настройки
                  </span>
                ) : null}
              </div>
              {item.resolution_hint ? (
                <div className="mt-2 rounded-lg bg-slate-50 px-2 py-1.5 text-[11px] leading-4 text-slate-700 ring-1 ring-slate-200">
                  {item.resolution_hint}
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
};

const resolverStateTone = (state: string) => {
  if (state === 'ready' || state === 'native_ready') {
    return 'bg-emerald-50 text-emerald-700 ring-emerald-200';
  }
  if (state === 'available' || state === 'choose_existing') {
    return 'bg-sky-50 text-sky-700 ring-sky-200';
  }
  if (state === 'planned_provider') {
    return 'bg-slate-50 text-slate-600 ring-slate-200';
  }
  return 'bg-amber-50 text-amber-700 ring-amber-200';
};

const BuilderSetupFlowPanel = ({ setupFlow }: { setupFlow?: AgentBuilderSetupFlow }) => {
  const steps = Array.isArray(setupFlow?.steps) ? setupFlow.steps : [];
  if (!setupFlow || !steps.length) {
    return null;
  }
  const primaryActionLabel = {
    answer_question: 'Ответьте на вопрос слева',
    connect_service: 'Подключите сервис',
    choose_connection: 'Выберите подключение',
    top_up_balance: 'Пополните баланс',
    cannot_create: 'Такой агент недоступен',
    create_draft: 'Можно создать draft',
  }[setupFlow.primary_action || ''] || 'Проверьте настройку';
  const nextStepTitle = setupFlow.next_step_title || primaryActionLabel;
  const nextStepDescription = setupFlow.next_step_description || setupFlow.post_create_description || '';
  return (
    <div className="mt-3 rounded-xl border border-slate-200 bg-white px-3 py-3 text-xs leading-5 text-slate-700">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <div className="font-semibold text-slate-950">Что дальше</div>
          <div className="mt-1 max-w-2xl text-[11px] leading-4 text-slate-500">
            {nextStepDescription || 'LocalOS ведёт агента от описания к draft, preview run и активации.'}
          </div>
        </div>
        <span className={cn('rounded-full px-2 py-0.5 font-medium ring-1', statusTone[setupFlow.status || 'pending'] || statusTone.pending)}>
          {nextStepTitle}
        </span>
      </div>
      <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7">
        {steps.map((step) => {
          const status = step.status || 'pending';
          const done = status === 'done' || status === 'ready';
          const active = status === 'active' || status === 'next';
          const blocked = status === 'blocked';
          return (
            <div
              key={step.key || step.label}
              className={cn(
                'min-h-24 rounded-lg px-2 py-2 ring-1',
                done ? 'bg-emerald-50 text-emerald-950 ring-emerald-100' : '',
                active ? 'bg-amber-50 text-amber-950 ring-amber-100' : '',
                blocked ? 'bg-slate-50 text-slate-500 ring-slate-200' : '',
                !done && !active && !blocked ? 'bg-slate-50 text-slate-700 ring-slate-200' : '',
              )}
            >
              <div className="flex items-center gap-1.5 font-medium">
                {done ? <CheckCircle2 className="h-3.5 w-3.5" /> : active ? <Clock3 className="h-3.5 w-3.5" /> : blocked ? <AlertTriangle className="h-3.5 w-3.5" /> : <Clock3 className="h-3.5 w-3.5" />}
                <span>{step.label || humanizeMeta(step.key || 'Шаг')}</span>
              </div>
              <div className="mt-1 text-[11px] leading-4 opacity-80">{step.description || statusLabels[status] || humanizeMeta(status)}</div>
            </div>
          );
        })}
      </div>
      {setupFlow.activation_blockers?.length ? (
        <div className="mt-2 text-[11px] leading-4 text-slate-500">
          Активация будет доступна после: {setupFlow.activation_blockers.slice(0, 3).map((item) => item.message || connectorLabel(item.provider)).join(', ')}.
        </div>
      ) : null}
      {setupFlow.post_create_description ? (
        <div className="mt-2 rounded-lg bg-slate-50 px-2 py-2 text-[11px] leading-4 text-slate-600 ring-1 ring-slate-100">
          После создания: {setupFlow.post_create_description}
        </div>
      ) : null}
    </div>
  );
};

const BuilderConnectionSummaryPanel = ({
  summary,
  selectedBindings = {},
  onSelectBinding,
}: {
  summary?: AgentConnectionSummary;
  selectedBindings?: Record<string, string>;
  onSelectBinding?: (bindingKey: string, integrationId: string) => void;
}) => {
  const items = summary?.items || [];
  const forbidden = summary?.forbidden || [];
  const unsupported = summary?.unsupported || [];
  if (!summary || (!items.length && !forbidden.length && !unsupported.length)) {
    return null;
  }
  const blocked = Boolean((summary.blocked_count || 0) > 0 || forbidden.length || unsupported.length);
  const needsAction = Boolean((summary.missing_count || 0) > 0 || (summary.choice_count || 0) > 0);
  return (
    <div className={cn('mt-3 rounded-xl border px-3 py-3 text-xs leading-5', blocked ? 'border-rose-200 bg-rose-50 text-rose-950' : needsAction ? 'border-amber-200 bg-amber-50 text-amber-950' : 'border-emerald-200 bg-emerald-50 text-emerald-950')}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="font-semibold">Подключения для агента</div>
          <div className="mt-1 max-w-2xl">{summary.headline || 'LocalOS проверил нужные источники и каналы.'}</div>
        </div>
        <span className="rounded-full bg-white px-2 py-0.5 font-medium ring-1 ring-current/10">
          {summary.next_action_label || 'Проверить подключения'}
        </span>
      </div>
      <div className="mt-3 grid gap-2 sm:grid-cols-4">
        <AgentMiniMetric label="Готово" value={String(summary.ready_count || 0)} />
        <AgentMiniMetric label="Подключить" value={String(summary.missing_count || 0)} />
        <AgentMiniMetric label="Выбрать" value={String(summary.choice_count || 0)} />
        <AgentMiniMetric label="Блокеры" value={String(summary.blocked_count || 0)} />
      </div>
      <div className="mt-3 grid gap-2 md:grid-cols-2">
        {items.slice(0, 4).map((item) => (
          <div key={`${item.key || item.provider || item.title}`} className="rounded-lg bg-white px-3 py-2 ring-1 ring-current/10">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div className="font-medium">{item.title || connectorLabel(item.provider)}</div>
              <span className="rounded-full bg-slate-50 px-2 py-0.5 text-[11px] text-slate-600 ring-1 ring-slate-200">
                {item.action_label || humanizeMeta(item.action || item.status || 'status')}
              </span>
            </div>
            <div className="mt-1 text-[11px] leading-4 opacity-80">{item.explanation || 'Подключение будет проверено перед preview run.'}</div>
            {item.setup_cta?.mode && item.setup_cta.mode !== 'none' ? (
              <div className="mt-2 rounded-lg bg-slate-50 px-2 py-1.5 text-[11px] leading-4 text-slate-700 ring-1 ring-slate-200">
                <div className="font-medium">{item.setup_cta.label || 'Настроить подключение'}</div>
                {item.setup_cta.description ? <div className="mt-0.5">{item.setup_cta.description}</div> : null}
              </div>
            ) : null}
            {item.connections?.length ? (
              <div className="mt-2 space-y-1.5">
                <div className="text-[11px] font-medium opacity-80">
                  Доступно: {item.connections.slice(0, 2).map((connection) => connection.display_name || connectorLabel(connection.provider)).join(', ')}
                </div>
                {item.connections.length === 1 && selectedBindings[item.key || ''] === item.connections[0]?.id ? (
                  <div className="inline-flex rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] font-medium text-emerald-700 ring-1 ring-emerald-200">
                    Выбрано автоматически
                  </div>
                ) : null}
                {item.connections.length > 1 && onSelectBinding ? (
                  <div className="flex flex-wrap gap-1.5">
                    {item.connections.slice(0, 4).map((connection) => {
                      const bindingKey = item.key || item.provider || '';
                      const integrationId = connection.id || '';
                      const selected = Boolean(bindingKey && integrationId && selectedBindings[bindingKey] === integrationId);
                      return (
                        <Button
                          key={`${bindingKey}-${integrationId}`}
                          type="button"
                          size="sm"
                          variant={selected ? 'default' : 'outline'}
                          className={cn('h-7 px-2 text-[11px]', selected ? '' : 'bg-white')}
                          disabled={!bindingKey || !integrationId}
                          onClick={() => onSelectBinding(bindingKey, integrationId)}
                        >
                          {selected ? 'Выбрано' : 'Использовать'} {connection.display_name || connectorLabel(connection.provider)}
                        </Button>
                      );
                    })}
                  </div>
                ) : null}
              </div>
            ) : null}
          </div>
        ))}
      </div>
      {forbidden.length || unsupported.length ? (
        <div className="mt-3 rounded-lg bg-white px-3 py-2 text-[11px] leading-4 ring-1 ring-current/10">
          {[...forbidden.map((item) => item.reason || item.term || 'Запрещено policy'), ...unsupported.map((item) => item.reason || item.capability || 'Нет provider path')].slice(0, 3).join(' · ')}
        </div>
      ) : null}
    </div>
  );
};

const AgentMiniMetric = ({ label, value }: { label: string; value: string }) => (
  <div className="rounded-lg bg-white px-3 py-2 ring-1 ring-current/10">
    <div className="text-[11px] font-medium opacity-70">{label}</div>
    <div className="mt-1 text-base font-semibold">{value}</div>
  </div>
);

const ConnectorIntelligencePanel = ({ intelligence }: { intelligence?: AgentConnectorIntelligence }) => {
  const bindings = intelligence?.bindings || [];
  const capabilities = intelligence?.capabilities || [];
  const providerPaths = intelligence?.provider_paths || [];
  const forbidden = intelligence?.forbidden || [];
  const unsupported = intelligence?.unsupported || [];
  if (!intelligence || (!bindings.length && !capabilities.length && !forbidden.length && !unsupported.length)) {
    return null;
  }
  const blocked = Boolean(forbidden.length || unsupported.length);
  const needsAction = bindings.some((item) => !['ready', 'native_ready'].includes(item.action || ''));
  return (
    <div className={cn('mt-3 rounded-xl border px-3 py-3 text-xs leading-5', blocked ? 'border-rose-200 bg-rose-50 text-rose-950' : needsAction ? 'border-amber-200 bg-amber-50 text-amber-950' : 'border-emerald-200 bg-emerald-50 text-emerald-950')}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="font-semibold">Доступность сервисов</div>
          <div className="mt-1 max-w-2xl">
            {intelligence.headline || 'LocalOS проверил нужные подключения и provider paths.'}
          </div>
        </div>
        <span className={cn('rounded-full bg-white px-2.5 py-1 font-medium ring-1', blocked ? 'text-rose-700 ring-rose-200' : needsAction ? 'text-amber-800 ring-amber-200' : 'text-emerald-800 ring-emerald-200')}>
          {blocked ? 'нельзя создать' : needsAction ? 'нужно действие' : 'готово к preview'}
        </span>
      </div>

      {bindings.length ? (
        <div className="mt-3 grid gap-2 md:grid-cols-2">
          {bindings.slice(0, 4).map((item) => (
            <div key={item.key || item.provider} className="rounded-lg bg-white px-2 py-2 ring-1 ring-black/5">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="font-medium text-slate-950">{item.title || connectorLabel(item.provider)}</div>
                  <div className="mt-0.5 text-[11px] text-slate-500">{humanizeMeta(item.capability || item.provider || 'capability')}</div>
                </div>
                <span className={cn('shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium ring-1', connectionActionTone(item.action || ''))}>
                  {item.action_label || humanizeMeta(item.action || item.status || '')}
                </span>
              </div>
              <div className="mt-1 text-[11px] leading-4 text-slate-600">{item.route_summary || item.explanation || 'Будет проверено на preflight.'}</div>
              {item.connections?.length ? (
                <div className="mt-1 flex flex-wrap gap-1">
                  {item.connections.slice(0, 2).map((connection) => (
                    <span key={connection.id || connection.display_name} className="rounded-full bg-sky-50 px-1.5 py-0.5 text-[10px] text-sky-700 ring-1 ring-sky-100">
                      {connection.display_name || connectorLabel(connection.provider)}
                    </span>
                  ))}
                </div>
              ) : null}
              {item.provider_routes?.length ? (
                <div className="mt-2 flex flex-wrap gap-1">
                  {item.provider_routes.slice(0, 4).map((route) => (
                    <ProviderActionPill key={`${item.key}-${route.provider}-${route.role}`} route={route} />
                  ))}
                </div>
              ) : null}
              <RecommendedProviderRouteNote
                route={item.recommended_route}
                reason={item.recommended_route_reason}
              />
            </div>
          ))}
        </div>
      ) : null}

      {capabilities.length ? (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {capabilities.slice(0, 5).map((item) => (
            <span key={item.capability} className="rounded-full bg-white px-2 py-0.5 text-[11px] text-slate-700 ring-1 ring-black/5">
              {humanizeMeta(item.capability || '')}
              {item.route_state ? ` · ${providerRouteLabel(item.route_state)}` : ''}
              {item.openclaw_actions?.length ? ` · OpenClaw ${item.openclaw_actions.length}` : ''}
            </span>
          ))}
        </div>
      ) : null}

      {providerPaths.length ? (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {providerPaths.slice(0, 6).map((item) => (
            <span key={`${item.provider}-${item.status}-${item.source}`} className="rounded-full bg-white/80 px-2 py-0.5 text-[11px] text-slate-600 ring-1 ring-black/5">
              {item.label || connectorLabel(item.provider)}: {humanizeMeta(item.status || 'unknown')}
            </span>
          ))}
        </div>
      ) : null}
    </div>
  );
};

const BuilderPlannerLoopPanel = ({ plannerLoop }: { plannerLoop?: AgentBuilderPlannerLoop }) => {
  if (!plannerLoop) {
    return null;
  }
  const capabilities = plannerLoop.capability_plan || [];
  const actionRefs = plannerLoop.workflow_proposal?.openclaw_action_refs || [];
  const providerPaths = plannerLoop.workflow_proposal?.provider_paths || [];
  return (
    <div className="mt-3 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs leading-5 text-slate-600">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="font-semibold text-slate-950">OpenClaw planner</div>
        <span className="rounded-full bg-slate-50 px-2 py-0.5 font-medium text-slate-600 ring-1 ring-slate-200">
          {plannerLoop.catalog_source === 'openclaw' ? 'live catalog' : 'fallback catalog'}
        </span>
      </div>
      <div className="mt-1">
        Проверены {capabilities.length || 0} capabilities, {providerPaths.length || 0} provider paths и {actionRefs.length || 0} action refs. Tools не выполняются в мастере; workflow будет скомпилирован LocalOS.
      </div>
    </div>
  );
};

const BuilderExecutionBoundaryPanel = ({ plannerLoop }: { plannerLoop?: AgentBuilderPlannerLoop }) => {
  if (!plannerLoop) {
    return null;
  }
  const actionRefs = plannerLoop.workflow_proposal?.openclaw_action_refs || [];
  const providerPaths = plannerLoop.workflow_proposal?.provider_paths || [];
  const capabilities = plannerLoop.capability_plan || [];
  const contract = plannerLoop.planner_contract || {};
  if (!actionRefs.length && !capabilities.length && !providerPaths.length) {
    return null;
  }
  const mayExecuteTools = plannerLoop.may_execute_tools === true || contract.tool_execution_allowed === true;
  const externalSideEffects = contract.external_side_effects_allowed === true;
  return (
    <div className="mt-3 rounded-xl border border-sky-200 bg-sky-50 px-3 py-3 text-xs leading-5 text-sky-950">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="font-semibold">Execution boundary</div>
          <div className="mt-1 max-w-2xl text-sky-800">
            OpenClaw может предложить и исполнить действия только за LocalOS policy, billing, audit и approval gate.
          </div>
        </div>
        <span className="rounded-full bg-white px-2 py-0.5 font-medium text-sky-700 ring-1 ring-sky-200">
          {plannerLoop.catalog_source === 'openclaw' ? 'OpenClaw catalog' : 'fallback catalog'}
        </span>
      </div>
      <div className="mt-3 grid gap-2 sm:grid-cols-3">
        <AgentMiniMetric label="Tools" value={mayExecuteTools ? 'разрешены' : 'запрещены'} />
        <AgentMiniMetric label="Side effects" value={externalSideEffects ? 'есть риск' : 'нет в preview'} />
        <AgentMiniMetric label="Owner" value={contract.compiled_workflow_owner || (plannerLoop.must_compile_in_localos ? 'LocalOS' : 'LocalOS')} />
      </div>
      {actionRefs.length ? (
        <div className="mt-3 rounded-lg bg-white px-2 py-2 ring-1 ring-sky-100">
          <div className="font-semibold text-sky-900">OpenClaw action refs</div>
          <div className="mt-1 flex flex-wrap gap-1.5">
            {actionRefs.slice(0, 6).map((actionRef) => (
              <span key={actionRef} className="rounded-full bg-slate-50 px-2 py-0.5 font-mono text-[11px] text-slate-700 ring-1 ring-slate-200">
                {actionRef}
              </span>
            ))}
          </div>
        </div>
      ) : null}
      {capabilities.length ? (
        <div className="mt-2 grid gap-2 md:grid-cols-2">
          {capabilities.slice(0, 4).map((item) => {
            const refs = item.openclaw_actions?.map((action) => action.openclaw_action_ref).filter(Boolean) || [];
            return (
              <div key={item.capability || refs.join(':')} className="rounded-lg bg-white px-2 py-2 ring-1 ring-sky-100">
                <div className="font-medium text-slate-950">{humanizeMeta(item.capability || 'capability')}</div>
                <div className="mt-1 text-[11px] leading-4 text-slate-600">
                  {refs.length ? refs.slice(0, 2).join(' · ') : 'OpenClaw action не выбран'}
                </div>
              </div>
            );
          })}
        </div>
      ) : null}
      {contract.must_not?.length ? (
        <div className="mt-2 rounded-lg bg-white/80 px-2 py-1.5 text-[11px] leading-4 text-sky-800 ring-1 ring-sky-100">
          Нельзя: {contract.must_not.slice(0, 4).map((item) => humanizeMeta(item)).join(', ')}.
        </div>
      ) : null}
    </div>
  );
};

const PreviewRow = ({ label, value }: { label: string; value: string }) => (
  <div className="rounded-xl bg-white px-3 py-2 ring-1 ring-slate-200">
    <div className="text-xs font-semibold uppercase text-slate-500">{label}</div>
    <div className="mt-1 text-slate-800">{value}</div>
  </div>
);

const BuilderFeasibilityPanel = ({ feasibility, connectors }: { feasibility?: AgentBuilderFeasibility; connectors?: AgentBuilderConnectorPreview[] }) => {
  const status = feasibility?.status || 'ready';
  const items = connectors || [];
  const forbidden = feasibility?.forbidden || [];
  const unsupported = feasibility?.unsupported || [];
  const isProblem = status === 'forbidden' || status === 'unsupported';
  const isReady = status === 'ready';
  const tone = isReady
    ? 'border-emerald-200 bg-emerald-50 text-emerald-950'
    : isProblem
      ? 'border-red-200 bg-red-50 text-red-950'
      : 'border-amber-200 bg-amber-50 text-amber-950';
  const title = status === 'ready'
    ? 'Подключения готовы'
    : status === 'needs_choice'
      ? 'Нужно выбрать подключение'
      : status === 'needs_connection'
        ? 'Нужно подключить сервисы'
        : status === 'forbidden'
          ? 'Нельзя создать в LocalOS'
          : status === 'unsupported'
            ? 'Нет разрешённого способа'
            : 'Нужно проверить ограничения';
  if (!items.length && !forbidden.length && !unsupported.length && isReady) {
    return null;
  }
  return (
    <div className={cn('mt-3 rounded-xl border px-3 py-3 text-xs leading-5', tone)}>
      <div className="font-semibold">{title}</div>
      {items.length ? (
        <div className="mt-2 grid gap-2 sm:grid-cols-2">
          {items.map((item) => (
            <div key={`${item.key || item.provider || item.title}`} className="rounded-lg bg-white/70 px-2 py-2 ring-1 ring-black/5">
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium">{item.title || connectorLabel(item.provider)}</span>
                <span className="rounded-full bg-white px-2 py-0.5 text-[11px] font-medium ring-1 ring-black/10">
                  {statusLabels[item.status || ''] || humanizeMeta(item.status || 'ожидает')}
                </span>
              </div>
              {item.status === 'missing' ? (
                <div className="mt-1 opacity-80">{item.action?.description || 'Подключите доступ перед активацией агента.'}</div>
              ) : null}
              {item.status === 'needs_choice' ? (
                <div className="mt-1 opacity-80">{item.action?.description || `Найдено подключений: ${item.connection_count || 0}. Нужно выбрать одно.`}</div>
              ) : null}
              {item.status === 'ready' ? (
                <div className="mt-1 opacity-80">{item.action?.description || 'Подключение готово.'}</div>
              ) : null}
              {item.connections?.length ? (
                <div className="mt-2 flex flex-wrap gap-1">
                  {item.connections.slice(0, 2).map((connection) => (
                    <span key={connection.id || connection.display_name} className="rounded-full bg-white px-2 py-0.5 text-[11px] ring-1 ring-black/10">
                      {connection.display_name || connectorLabel(connection.provider)}
                    </span>
                  ))}
                </div>
              ) : null}
              {item.action?.label && item.status !== 'ready' ? (
                <div className="mt-2 inline-flex rounded-full bg-white px-2 py-0.5 text-[11px] font-medium ring-1 ring-black/10">
                  {item.action.label}
                </div>
              ) : null}
            </div>
          ))}
        </div>
      ) : null}
      {forbidden.length ? (
        <div className="mt-2 space-y-2">
          {forbidden.map((item) => (
            <div key={`${item.term || item.reason}`} className="rounded-lg bg-white/70 px-2 py-2 ring-1 ring-red-100">
              {item.reason || 'Действие запрещено политикой LocalOS.'}
            </div>
          ))}
        </div>
      ) : null}
      {unsupported.length ? (
        <div className="mt-2 space-y-2">
          {unsupported.map((item) => (
            <div key={`${item.capability || item.reason}`} className="rounded-lg bg-white/70 px-2 py-2 ring-1 ring-red-100">
              {item.reason || 'Нет разрешённого provider path.'}
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
};

const SystemAgentCard = ({
  title,
  description,
  icon: Icon,
  enabled,
  onConfigure,
}: {
  title: string;
  description: string;
  icon: typeof Bot;
  enabled: boolean;
  onConfigure: () => void;
}) => (
  <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
    <div className="flex items-start justify-between gap-3">
      <div className="flex min-w-0 items-start gap-3">
        <div className="rounded-xl bg-slate-100 p-2 text-slate-700">
          <Icon className="h-5 w-5" />
        </div>
        <div className="min-w-0">
          <div className="text-sm font-semibold text-slate-950">{title}</div>
          <div className="mt-1 text-sm leading-6 text-slate-600">{description}</div>
        </div>
      </div>
      <span className={cn('shrink-0 rounded-full px-2.5 py-1 text-xs font-medium ring-1', enabled ? 'bg-emerald-50 text-emerald-700 ring-emerald-200' : 'bg-slate-100 text-slate-600 ring-slate-200')}>
        {enabled ? 'Включён' : 'Выключен'}
      </span>
    </div>
    <div className="mt-4 flex justify-end">
      <Button type="button" size="sm" variant="outline" onClick={onConfigure}>
        Настроить
      </Button>
    </div>
  </div>
);

const AgentCommandCenter = ({
  activeAgentsCount,
  totalAgents,
  pendingApprovals,
  selectedBlueprint,
  loading,
  actionLoading,
  onCreate,
  onConfigureSelected,
  onOpenApprovals,
}: {
  activeAgentsCount: number;
  totalAgents: number;
  pendingApprovals: number;
  selectedBlueprint: AgentBlueprint | null;
  loading: boolean;
  actionLoading: boolean;
  onCreate: () => void;
  onConfigureSelected: () => void;
  onOpenApprovals: () => void;
}) => (
  <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
    <div className="grid gap-3 lg:grid-cols-3">
      <button
        type="button"
        className="group rounded-xl border border-slate-900 bg-slate-950 px-4 py-4 text-left text-white transition hover:bg-slate-900"
        onClick={onCreate}
        disabled={actionLoading}
      >
        <div className="flex items-center justify-between gap-3">
          <Sparkles className="h-5 w-5" />
          <span className="text-xs font-medium text-slate-300">{totalAgents} всего</span>
        </div>
        <div className="mt-4 text-sm font-semibold">Создать агента</div>
        <div className="mt-1 text-sm leading-6 text-slate-300">
          Опишите задачу, проверьте будущую логику, затем подключите данные.
        </div>
      </button>

      <button
        type="button"
        className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-4 text-left transition hover:border-slate-300 hover:bg-white"
        onClick={onConfigureSelected}
        disabled={!selectedBlueprint || loading}
      >
        <div className="flex items-center justify-between gap-3">
          <Workflow className="h-5 w-5 text-slate-600" />
          <span className="text-xs font-medium text-slate-500">{activeAgentsCount} активны</span>
        </div>
        <div className="mt-4 text-sm font-semibold text-slate-950">Настроить выбранного</div>
        <div className="mt-1 line-clamp-2 text-sm leading-6 text-slate-600">
          {selectedBlueprint ? selectedBlueprint.name : 'Сначала выберите агента в списке.'}
        </div>
      </button>

      <button
        type="button"
        className={cn(
          'rounded-xl border px-4 py-4 text-left transition',
          pendingApprovals ? 'border-amber-200 bg-amber-50 hover:border-amber-300' : 'border-slate-200 bg-slate-50 hover:border-slate-300 hover:bg-white',
        )}
        onClick={onOpenApprovals}
        disabled={!selectedBlueprint}
      >
        <div className="flex items-center justify-between gap-3">
          <ShieldCheck className={cn('h-5 w-5', pendingApprovals ? 'text-amber-700' : 'text-slate-600')} />
          <span className={cn('text-xs font-medium', pendingApprovals ? 'text-amber-800' : 'text-slate-500')}>
            {pendingApprovals} ждут
          </span>
        </div>
        <div className="mt-4 text-sm font-semibold text-slate-950">Проверить решения</div>
        <div className={cn('mt-1 text-sm leading-6', pendingApprovals ? 'text-amber-900' : 'text-slate-600')}>
          Ручные решения, журнал и результаты открываются внутри выбранного агента.
        </div>
      </button>
    </div>
  </section>
);

const BlueprintAgentCard = ({
  blueprint,
  latestVersionNumber,
  selected,
  onSelect,
  onConfigure,
  onRun,
  onResults,
  onVoice,
}: {
  blueprint: AgentBlueprint;
  latestVersionNumber: number | null;
  selected: boolean;
  onSelect: () => void;
  onConfigure: () => void;
  onRun: () => void;
  onResults: () => void;
  onVoice: () => void;
}) => {
  const listStatus = getAgentListStatus(blueprint);
  const voiceName = getAgentVoiceName(blueprint);
  return (
  <div className={cn('rounded-xl border bg-white p-3 transition', selected ? 'border-slate-900 shadow-sm' : 'border-slate-200 hover:border-slate-300')}>
    <button type="button" className="w-full text-left" onClick={onSelect}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold text-slate-950">{blueprint.name}</div>
          <div className="mt-1 text-xs font-medium text-slate-500">
            {humanizeCategory(blueprint.category)} · {latestVersionNumber ? `активная версия v${latestVersionNumber}` : 'версия ещё не создана'}
          </div>
        </div>
        <StatusBadge status={listStatus} />
      </div>
      <div className="mt-3 line-clamp-3 text-sm leading-6 text-slate-600">
        {blueprint.description || blueprint.latest_goal || 'Пользовательский агент с настройками, запусками и результатами.'}
      </div>
      <div className="mt-3 flex flex-wrap gap-1.5 text-xs">
        <span className="rounded-full bg-slate-50 px-2.5 py-1 text-slate-600 ring-1 ring-slate-200">
          {formatLastRun(blueprint)}
        </span>
        <span className={cn('rounded-full px-2.5 py-1 ring-1', blueprint.pending_approvals_count ? 'bg-amber-50 text-amber-800 ring-amber-200' : 'bg-slate-50 text-slate-600 ring-slate-200')}>
          {blueprint.pending_approvals_count || 0} решений
        </span>
        <span className="rounded-full bg-slate-50 px-2.5 py-1 text-slate-600 ring-1 ring-slate-200">
          {blueprint.sources_count || 0} источников
        </span>
      </div>
      <div className="mt-2 text-xs text-slate-500">
        {voiceName ? `Голос: ${voiceName}` : 'Голос не привязан'}
      </div>
    </button>
    <div className="mt-3 grid grid-cols-[1fr_auto] gap-2">
      <Button type="button" size="sm" variant={selected ? 'default' : 'outline'} onClick={onConfigure}>
        Изменить логику
      </Button>
      <Button type="button" size="sm" variant="outline" onClick={onRun}>
        <Play className="mr-2 h-4 w-4" />
        Запустить
      </Button>
    </div>
    <div className="mt-2 flex gap-1.5">
      <Button type="button" size="sm" variant="ghost" className="h-8 px-2 text-xs" onClick={onResults}>Журнал</Button>
      <Button type="button" size="sm" variant="ghost" className="h-8 px-2 text-xs" onClick={onVoice}>Голос</Button>
    </div>
  </div>
  );
};

const AgentCockpitPanel = ({
  blueprints,
  systemAgents,
  migrationPlan,
  migrationStats,
  migrationNotice,
  actionLoading,
  onApplyMigration,
  onOpenLegacySettings,
}: {
  blueprints: AgentBlueprint[];
  systemAgents: Array<{ key: string; title: string; description: string; icon: typeof Bot; enabled: boolean }>;
  migrationPlan: LegacyMigrationPlan | null;
  migrationStats: {
    totalLegacyAgents: number;
    linkedVoices: number;
    needsBlueprint: number;
    archiveCandidates: number;
    deprecatedFieldsPresent: number;
    legacyWorkflowPresent: number;
  };
  migrationNotice: string;
  actionLoading: boolean;
  onApplyMigration: () => void;
  onOpenLegacySettings: () => void;
}) => {
  const activeBlueprints = blueprints.filter((item) => getAgentListStatus(item) === 'active').length;
  const pendingBlueprints = blueprints.filter((item) => getAgentListStatus(item) === 'needs_approval').length;
  const deprecatedFields = migrationPlan?.business_settings?.fields || {};
  return (
    <div className="space-y-4">
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <CockpitTile icon={Bot} label="Агенты продукта" value={`${activeBlueprints}/${blueprints.length}`} hint="включены / всего" />
        <CockpitTile icon={ShieldCheck} label="Ручные решения" value={String(pendingBlueprints)} hint="агенты ждут человека" tone={pendingBlueprints ? 'warning' : 'default'} />
        <CockpitTile icon={RefreshCw} label="Старые обёртки" value={String(migrationStats.needsBlueprint)} hint={`${migrationStats.linkedVoices} голосов привязано`} tone={migrationStats.needsBlueprint ? 'warning' : 'default'} />
        <CockpitTile icon={AlertTriangle} label="Устаревшие поля" value={String(migrationStats.deprecatedFieldsPresent)} hint="старые настройки бизнеса" tone={migrationStats.deprecatedFieldsPresent ? 'warning' : 'default'} />
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(20rem,0.75fr)]">
        <div className="rounded-2xl border border-slate-200 bg-white p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="text-sm font-semibold text-slate-950">Состояние миграции</div>
              <div className="mt-1 text-sm leading-6 text-slate-600">
                Старые AIAgents остаются голосом и стилем. Активная логика агента хранится в версиях blueprint.
              </div>
            </div>
            <Button type="button" onClick={onApplyMigration} disabled={actionLoading || !migrationStats.needsBlueprint}>
              {actionLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
              Применить миграцию
            </Button>
          </div>
          {migrationNotice ? (
            <div className="mt-3 rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-900">
              {migrationNotice}
            </div>
          ) : null}
          <div className="mt-4 grid gap-2 md:grid-cols-2">
            {(migrationPlan?.legacy_agents || []).slice(0, 6).map((agent) => (
              <div key={agent.agent_id || agent.name} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="truncate font-medium text-slate-950">{agent.name || 'Старый голос'}</div>
                    <div className="mt-1 text-xs text-slate-500">{agent.reason || 'решение миграции'}</div>
                  </div>
                  <StatusBadge status={agent.action === 'use_as_persona' ? 'active' : agent.action === 'create_blueprint_candidate' ? 'needs_approval' : 'paused'} />
                </div>
                {agent.legacy_workflow?.present ? (
                  <div className="mt-2 rounded-md border border-amber-200 bg-amber-50 px-2 py-1 text-xs text-amber-900">
                    AIAgents.workflow: {agent.legacy_workflow.status || 'deprecated'}
                  </div>
                ) : null}
              </div>
            ))}
          </div>
        </div>

        <div className="space-y-4">
          <div className="rounded-2xl border border-slate-200 bg-white p-4">
            <div className="text-sm font-semibold text-slate-950">Устаревшие настройки бизнеса</div>
            <div className="mt-3 space-y-2">
              {Object.entries(deprecatedFields).map(([field, info]) => (
                <div key={field} className="flex items-center justify-between gap-3 rounded-lg bg-slate-50 px-3 py-2 text-xs">
                  <div>
                    <div className="font-medium text-slate-800">{field}</div>
                    <div className="text-slate-500">{info.target || 'agent_blueprints'}</div>
                  </div>
                  <StatusBadge status={info.present ? 'needs_approval' : 'completed'} />
                </div>
              ))}
            </div>
          </div>
          <div className="grid gap-3">
            {systemAgents.map((agent) => (
              <SystemAgentCard
                key={agent.key}
                title={agent.title}
                description={agent.description}
                icon={agent.icon}
                enabled={agent.enabled}
                onConfigure={onOpenLegacySettings}
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

const CockpitTile = ({
  icon: Icon,
  label,
  value,
  hint,
  tone = 'default',
}: {
  icon: typeof Bot;
  label: string;
  value: string;
  hint: string;
  tone?: 'default' | 'warning';
}) => (
  <div className={cn('rounded-2xl border p-4', tone === 'warning' ? 'border-amber-200 bg-amber-50' : 'border-slate-200 bg-white')}>
    <div className="flex items-center justify-between gap-3">
      <div className="text-xs font-semibold uppercase text-slate-500">{label}</div>
      <Icon className={cn('h-4 w-4', tone === 'warning' ? 'text-amber-700' : 'text-slate-500')} />
    </div>
    <div className="mt-2 text-2xl font-semibold text-slate-950">{value}</div>
    <div className="mt-1 text-xs text-slate-500">{hint}</div>
  </div>
);

const AgentSummaryPill = ({ label, value, tone = 'default' }: { label: string; value: string; tone?: 'default' | 'warning' }) => (
  <div className={cn('rounded-lg px-3 py-2 ring-1', tone === 'warning' ? 'bg-amber-50 text-amber-900 ring-amber-200' : 'bg-slate-50 text-slate-700 ring-slate-200')}>
    <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">{label}</div>
    <div className="mt-1 truncate text-xs font-medium">{value}</div>
  </div>
);

const PersonaAgentCard = ({ agent, onConfigure }: { agent: PersonaAgent; onConfigure: () => void }) => (
  <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
    <div className="flex items-start justify-between gap-3">
      <div className="min-w-0">
        <div className="truncate text-sm font-semibold text-slate-950">{agent.name || 'Persona agent'}</div>
        <div className="mt-1 text-xs font-medium text-slate-500">Голос и стиль общения</div>
      </div>
      <span className={cn('rounded-full px-2.5 py-1 text-xs font-medium ring-1', agent.is_active ? 'bg-emerald-50 text-emerald-700 ring-emerald-200' : 'bg-slate-100 text-slate-600 ring-slate-200')}>
        {agent.is_active ? 'Включён' : 'Выключен'}
      </span>
    </div>
    <div className="mt-3 line-clamp-3 text-sm leading-6 text-slate-600">
      {agent.description || agent.task || agent.identity || 'Настраивает тон, стиль и ограничения общения. Не является отдельной логикой запуска.'}
    </div>
    <div className="mt-4 flex justify-end">
      <Button type="button" size="sm" variant="outline" onClick={onConfigure}>
        Открыть настройки
      </Button>
    </div>
  </div>
);

const AgentDetailPanel = ({
  mode,
  blueprint,
  blueprintDetails,
  activeRun,
  availablePersonaAgents,
  pendingApproval,
  queuedButNotDispatched,
  agentReview,
  feedbackText,
  feedbackTrigger,
  feedbackVersionNotice,
  actionLoading,
  setupDataSources,
  setupExtractionRules,
  setupProcessingRules,
  setupOutputFormat,
  setupManualControl,
  sourceName,
  sourceText,
  internalSource,
  sourceCatalog,
  agentIntegrations,
  availableAgentIntegrations,
  agentIntegrationCatalog,
  agentExternalAuthOptions,
  agentBindingStatus,
  agentConnectionPlan,
  postCreateHandoff,
  selectedConnectionBindingKey,
  sheetSpreadsheetId,
  sheetName,
  sheetAuthRef,
  sheetDailyCap,
  telegramBotMode,
  telegramDailyCap,
  matonAuthRef,
  matonChannel,
  matonDailyCap,
  processRowValues,
  processPreviewMessage,
  runSource,
  runCity,
  runCategory,
  runLimit,
  onModeChange,
  onStartRun,
  onStartVersionRun,
  onActivateVersion,
  onRollbackVersion,
  onApprove,
  onReject,
  onDeleteAgent,
  onFeedbackTextChange,
  onFeedbackTriggerChange,
  onSubmitFeedback,
  onActivateFeedbackVersion,
  onRollbackFeedbackVersion,
  onSetupDataSourcesChange,
  onSetupExtractionRulesChange,
  onSetupProcessingRulesChange,
  onSetupOutputFormatChange,
  onSetupManualControlChange,
  onSourceNameChange,
  onSourceTextChange,
  onInternalSourceChange,
  onSaveSetup,
  onAddTextSource,
  onAddInternalSource,
  onAddCatalogSource,
  onAddFileSource,
  onSheetSpreadsheetIdChange,
  onSheetNameChange,
  onSheetAuthRefChange,
  onSheetDailyCapChange,
  onTelegramBotModeChange,
  onTelegramDailyCapChange,
  onMatonAuthRefChange,
  onMatonChannelChange,
  onMatonDailyCapChange,
  onProcessRowValuesChange,
  onProcessPreviewMessageChange,
  onSaveSheetIntegration,
  onSaveTelegramIntegration,
  onSaveMatonIntegration,
  onChooseProviderRoute,
  onAttachExistingIntegration,
  onSelectConnectionBinding,
  onSaveCustomProcess,
  onRunCustomProcessPreview,
  onRunSourceChange,
  onRunCityChange,
  onRunCategoryChange,
  onRunLimitChange,
  showAdvancedTools,
}: {
  mode: AgentWorkspaceMode;
  blueprint: AgentBlueprint;
  blueprintDetails: AgentBlueprintDetails | null;
  activeRun: AgentRun | null;
  availablePersonaAgents: PersonaAgent[];
  pendingApproval: AgentApproval | null;
  queuedButNotDispatched: AgentArtifact['payload_json'] | AgentRunStep['output_json'] | null;
  agentReview: AgentReview | null;
  feedbackText: string;
  feedbackTrigger: string;
  feedbackVersionNotice: FeedbackVersionNotice | null;
  actionLoading: boolean;
  setupDataSources: string;
  setupExtractionRules: string;
  setupProcessingRules: string;
  setupOutputFormat: string;
  setupManualControl: string;
  sourceName: string;
  sourceText: string;
  internalSource: string;
  sourceCatalog: AgentSourceCatalogItem[];
  agentIntegrations: AgentIntegration[];
  availableAgentIntegrations: AgentIntegration[];
  agentIntegrationCatalog: AgentIntegrationCatalogItem[];
  agentExternalAuthOptions: AgentExternalAuthOption[];
  agentBindingStatus: AgentIntegrationBindingStatus[];
  agentConnectionPlan: AgentConnectionPlan | null;
  postCreateHandoff: AgentPostCreateHandoff | null;
  selectedConnectionBindingKey: string;
  sheetSpreadsheetId: string;
  sheetName: string;
  sheetAuthRef: string;
  sheetDailyCap: string;
  telegramBotMode: string;
  telegramDailyCap: string;
  matonAuthRef: string;
  matonChannel: string;
  matonDailyCap: string;
  processRowValues: string;
  processPreviewMessage: string;
  runSource: string;
  runCity: string;
  runCategory: string;
  runLimit: string;
  onModeChange: (mode: AgentWorkspaceMode) => void;
  onStartRun: () => void;
  onStartVersionRun: (versionId: string) => void;
  onActivateVersion: (versionId: string) => void;
  onRollbackVersion: (versionId: string) => void;
  onApprove: () => void;
  onReject: () => void;
  onDeleteAgent: () => void;
  onFeedbackTextChange: (value: string) => void;
  onFeedbackTriggerChange: (value: string) => void;
  onSubmitFeedback: () => void;
  onActivateFeedbackVersion: (versionId: string) => void;
  onRollbackFeedbackVersion: (versionId: string) => void;
  onSetupDataSourcesChange: (value: string) => void;
  onSetupExtractionRulesChange: (value: string) => void;
  onSetupProcessingRulesChange: (value: string) => void;
  onSetupOutputFormatChange: (value: string) => void;
  onSetupManualControlChange: (value: string) => void;
  onSourceNameChange: (value: string) => void;
  onSourceTextChange: (value: string) => void;
  onInternalSourceChange: (value: string) => void;
  onSaveSetup: () => void;
  onAddTextSource: () => void;
  onAddInternalSource: () => void;
  onAddCatalogSource: (sourceKey: string) => void;
  onAddFileSource: (file?: File | null) => void;
  onSheetSpreadsheetIdChange: (value: string) => void;
  onSheetNameChange: (value: string) => void;
  onSheetAuthRefChange: (value: string) => void;
  onSheetDailyCapChange: (value: string) => void;
  onTelegramBotModeChange: (value: string) => void;
  onTelegramDailyCapChange: (value: string) => void;
  onMatonAuthRefChange: (value: string) => void;
  onMatonChannelChange: (value: string) => void;
  onMatonDailyCapChange: (value: string) => void;
  onProcessRowValuesChange: (value: string) => void;
  onProcessPreviewMessageChange: (value: string) => void;
  onSaveSheetIntegration: () => void;
  onSaveTelegramIntegration: () => void;
  onSaveMatonIntegration: () => void;
  onChooseProviderRoute: (bindingKey: string, route: AgentProviderRoute) => void;
  onAttachExistingIntegration: (integration: AgentIntegration, bindingKey?: string) => void;
  onSelectConnectionBinding: (bindingKey: string) => void;
  onSaveCustomProcess: () => void;
  onRunCustomProcessPreview: () => void;
  onRunSourceChange: (value: string) => void;
  onRunCityChange: (value: string) => void;
  onRunCategoryChange: (value: string) => void;
  onRunLimitChange: (value: string) => void;
  showAdvancedTools: boolean;
}) => {
  const latestVersionNumber = getActiveVersionNumber(blueprint, blueprintDetails);
  const activeVersionId = getActiveVersionId(blueprint, blueprintDetails);
  const activationGate = blueprintDetails?.activation_gate;
  const voiceName = getAgentVoiceName(blueprint, blueprintDetails);
  const versions = blueprintDetails?.versions || [];
  const listStatus = getAgentListStatus(blueprint);
  const openConnectionsFromActivationGate = () => {
    if (activationGate?.next_binding_key) {
      onSelectConnectionBinding(activationGate.next_binding_key);
    }
    onModeChange('connections');
  };
  const handlePreviewNextStep = (nextStep: string) => {
    if (nextStep === 'connect_required_integrations') {
      onModeChange('connections');
      return;
    }
    if (nextStep === 'fix_preview_error') {
      onModeChange('settings');
      return;
    }
    if (nextStep === 'review_approvals') {
      onModeChange('results');
      return;
    }
    if (nextStep === 'check_activation_gate') {
      onModeChange('overview');
      return;
    }
    if (nextStep === 'review_preview') {
      onModeChange('run');
      return;
    }
    onModeChange('overview');
  };
  return (
  <DashboardSection
    title={blueprint.name}
    description={`${humanizeCategory(blueprint.category)} · ${latestVersionNumber ? `активная версия v${latestVersionNumber}` : 'нет активной версии'}${voiceName ? ` · голос: ${voiceName}` : ''}`}
    actions={(
      <div className="flex max-w-full gap-2 overflow-x-auto pb-1">
        <Button type="button" size="sm" className="shrink-0" variant={mode === 'overview' ? 'default' : 'outline'} onClick={() => onModeChange('overview')}>Обзор</Button>
        <Button type="button" size="sm" className="shrink-0" variant={mode === 'settings' ? 'default' : 'outline'} onClick={() => onModeChange('settings')}>Логика</Button>
        <Button type="button" size="sm" className="shrink-0" variant={mode === 'run' ? 'default' : 'outline'} onClick={() => onModeChange('run')}>Запуски</Button>
        <Button type="button" size="sm" className="shrink-0" variant={mode === 'results' ? 'default' : 'outline'} onClick={() => onModeChange('results')}>Обучение</Button>
        <Button type="button" size="sm" className="shrink-0" variant={mode === 'connections' ? 'default' : 'outline'} onClick={() => onModeChange('connections')}>Подключения</Button>
        <Button type="button" size="sm" className="shrink-0" variant={mode === 'voice' ? 'default' : 'outline'} onClick={() => onModeChange('voice')}>Голос и стиль</Button>
        {showAdvancedTools ? (
          <Button type="button" size="sm" className="shrink-0" variant={mode === 'advanced' ? 'default' : 'outline'} onClick={() => onModeChange('advanced')}>Advanced</Button>
        ) : null}
        <Button type="button" size="sm" className="shrink-0 text-red-700 hover:text-red-800" variant="outline" onClick={onDeleteAgent} disabled={actionLoading}>
          <Trash2 className="mr-2 h-4 w-4" />
          Удалить
        </Button>
      </div>
    )}
  >
    {mode === 'overview' ? (
      <AgentOverviewPanel
        blueprint={blueprint}
        detailsBlueprint={blueprintDetails?.blueprint}
        latestVersionNumber={latestVersionNumber}
        voiceName={voiceName}
        listStatus={listStatus}
        pendingApproval={pendingApproval}
        review={agentReview}
        metrics={blueprintDetails?.metrics}
        activationGate={activationGate}
        bindingStatus={agentBindingStatus}
        actionLoading={actionLoading}
        onStartRun={onStartRun}
        onActivateVersion={onActivateVersion}
        onOpenLogic={() => onModeChange('settings')}
        onOpenResults={() => onModeChange('results')}
        onOpenConnections={openConnectionsFromActivationGate}
        onOpenVoice={() => onModeChange('voice')}
        onDeleteAgent={onDeleteAgent}
      />
    ) : null}

    {mode === 'settings' ? (
        <AgentWorkspacePanel
        versions={versions}
        learningEvents={blueprintDetails?.learning_events || []}
        versionEvents={blueprintDetails?.version_events || []}
        legacyMigration={blueprintDetails?.legacy_migration || {}}
        latestVersionNumber={latestVersionNumber}
        activeVersionId={activeVersionId}
        setupDataSources={setupDataSources}
        setupExtractionRules={setupExtractionRules}
        setupProcessingRules={setupProcessingRules}
        setupOutputFormat={setupOutputFormat}
        setupManualControl={setupManualControl}
        sourceName={sourceName}
        sourceText={sourceText}
        internalSource={internalSource}
        sourceCatalog={sourceCatalog}
        review={agentReview}
        actionLoading={actionLoading}
        onSetupDataSourcesChange={onSetupDataSourcesChange}
        onSetupExtractionRulesChange={onSetupExtractionRulesChange}
        onSetupProcessingRulesChange={onSetupProcessingRulesChange}
        onSetupOutputFormatChange={onSetupOutputFormatChange}
        onSetupManualControlChange={onSetupManualControlChange}
        onSourceNameChange={onSourceNameChange}
        onSourceTextChange={onSourceTextChange}
        onInternalSourceChange={onInternalSourceChange}
        onSaveSetup={onSaveSetup}
        onStartVersionRun={onStartVersionRun}
        onActivateVersion={onActivateVersion}
        onRollbackVersion={onRollbackVersion}
        onAddTextSource={onAddTextSource}
        onAddInternalSource={onAddInternalSource}
        onAddCatalogSource={onAddCatalogSource}
        onAddFileSource={onAddFileSource}
      />
    ) : null}

    {mode === 'connections' ? (
      <AgentConnectionsPanel
        agentIntegrations={agentIntegrations}
        availableAgentIntegrations={availableAgentIntegrations}
        agentIntegrationCatalog={agentIntegrationCatalog}
        agentExternalAuthOptions={agentExternalAuthOptions}
        agentBindingStatus={agentBindingStatus}
        agentConnectionPlan={agentConnectionPlan}
        postCreateHandoff={recentPostCreateHandoff}
        selectedConnectionBindingKey={selectedConnectionBindingKey}
        sheetSpreadsheetId={sheetSpreadsheetId}
        sheetName={sheetName}
        sheetAuthRef={sheetAuthRef}
        sheetDailyCap={sheetDailyCap}
        telegramBotMode={telegramBotMode}
        telegramDailyCap={telegramDailyCap}
        matonAuthRef={matonAuthRef}
        matonChannel={matonChannel}
        matonDailyCap={matonDailyCap}
        processRowValues={processRowValues}
        processPreviewMessage={processPreviewMessage}
        actionLoading={actionLoading}
        onSheetSpreadsheetIdChange={onSheetSpreadsheetIdChange}
        onSheetNameChange={onSheetNameChange}
        onSheetAuthRefChange={onSheetAuthRefChange}
        onSheetDailyCapChange={onSheetDailyCapChange}
        onTelegramBotModeChange={onTelegramBotModeChange}
        onTelegramDailyCapChange={onTelegramDailyCapChange}
        onMatonAuthRefChange={onMatonAuthRefChange}
        onMatonChannelChange={onMatonChannelChange}
        onMatonDailyCapChange={onMatonDailyCapChange}
        onProcessRowValuesChange={onProcessRowValuesChange}
        onProcessPreviewMessageChange={onProcessPreviewMessageChange}
        onSaveSheetIntegration={onSaveSheetIntegration}
        onSaveTelegramIntegration={onSaveTelegramIntegration}
        onSaveMatonIntegration={onSaveMatonIntegration}
        onChooseProviderRoute={onChooseProviderRoute}
        onAttachExistingIntegration={onAttachExistingIntegration}
        onSelectConnectionBinding={onSelectConnectionBinding}
        onSaveCustomProcess={onSaveCustomProcess}
        onRunCustomProcessPreview={onRunCustomProcessPreview}
        onPreviewRun={onStartRun}
      />
    ) : null}

    {mode === 'run' ? (
      <div className="rounded-2xl border border-slate-200 bg-white p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="text-sm font-semibold text-slate-950">Запуск агента</div>
            <div className="mt-1 text-sm leading-6 text-slate-600">
              Запуск открывается из карточки конкретного агента. Для outreach показываем поля поиска, для остальных типов используем подключённые данные агента.
            </div>
          </div>
          <Button type="button" onClick={onStartRun} disabled={actionLoading}>
            {actionLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Play className="mr-2 h-4 w-4" />}
            Запустить
          </Button>
        </div>
        {blueprint.category === 'outreach' ? (
          <div className="mt-4 grid gap-3 md:grid-cols-4">
            <input className="rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-slate-400" value={runSource} onChange={(event) => onRunSourceChange(event.target.value)} placeholder="Источник" />
            <input className="rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-slate-400" value={runCity} onChange={(event) => onRunCityChange(event.target.value)} placeholder="Город" />
            <input className="rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-slate-400" value={runCategory} onChange={(event) => onRunCategoryChange(event.target.value)} placeholder="Категория" />
            <input className="rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-slate-400" value={runLimit} onChange={(event) => onRunLimitChange(event.target.value)} placeholder="Лимит" />
          </div>
        ) : (
          <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm leading-6 text-slate-600">
            Этот агент возьмёт данные из блока “Данные агента” и подготовит результат без внешней отправки.
          </div>
        )}
      </div>
    ) : null}

    {mode === 'results' ? (
      <div className="space-y-4">
        {activeRun ? (
          <PreviewRunSummaryPanel
            summary={activeRun.observability?.preview_summary}
            runInput={activeRun.input_json && typeof activeRun.input_json === 'object' ? activeRun.input_json : {}}
            activationGate={activationGate}
            actionLoading={actionLoading}
            onNextStepAction={handlePreviewNextStep}
            onActivateVersion={onActivateVersion}
          />
        ) : null}
        {blueprint.category === 'outreach' ? (
          <OutreachRunProgress review={agentReview} activeRun={activeRun} />
        ) : (
          <GenericRunProgress
            category={blueprint.category}
            review={agentReview}
            activeRun={activeRun}
            pendingApproval={pendingApproval}
          />
        )}
        {queuedButNotDispatched ? (
          <DashboardActionPanel
            title="Поставлено в очередь, но не отправлено"
            description="Агент поставил batch в безопасную очередь. Dispatcher не запускался из этого экрана."
            tone="amber"
          />
        ) : null}
        {pendingApproval ? (
          <DashboardActionPanel
            title="Ждёт решения"
            description={`${pendingApproval.title}. ${explainApproval(pendingApproval)}`}
            tone="amber"
            actions={(
              <div className="flex flex-wrap gap-2">
                <Button type="button" onClick={onApprove} disabled={actionLoading}>Принять</Button>
                <Button type="button" variant="outline" onClick={onReject} disabled={actionLoading}>Отклонить</Button>
              </div>
            )}
          />
        ) : null}
        <AgentRunReviewPanel
          review={agentReview}
          latestVersionNumber={latestVersionNumber}
          feedbackText={feedbackText}
          feedbackTrigger={feedbackTrigger}
          feedbackVersionNotice={feedbackVersionNotice}
          actionLoading={actionLoading}
          onFeedbackTextChange={onFeedbackTextChange}
          onFeedbackTriggerChange={onFeedbackTriggerChange}
          onSubmitFeedback={onSubmitFeedback}
          onActivateFeedbackVersion={onActivateFeedbackVersion}
          onRollbackFeedbackVersion={onRollbackFeedbackVersion}
        />
        {activeRun ? null : (
          <DashboardEmptyState title="Нет активных запусков" description="Запустите агента из карточки, чтобы увидеть результат." />
        )}
      </div>
    ) : null}
    {mode === 'voice' ? (
      <AgentVoiceStylePanel
        blueprint={blueprint}
        availablePersonaAgents={availablePersonaAgents}
      />
    ) : null}
    {showAdvancedTools && mode === 'advanced' ? (
      <AgentAdvancedPanel
        activeRun={activeRun}
        versions={versions}
        activationGate={activationGate}
        actionLoading={actionLoading}
        onPreviewNextStepAction={handlePreviewNextStep}
        onActivateVersion={onActivateVersion}
        onApplyFinanceRequests={applyFinanceRequests}
      />
    ) : null}
  </DashboardSection>
  );
};

const AgentOverviewPanel = ({
  blueprint,
  detailsBlueprint,
  latestVersionNumber,
  voiceName,
  listStatus,
  pendingApproval,
  review,
  metrics,
  activationGate,
  bindingStatus,
  actionLoading,
  onStartRun,
  onActivateVersion,
  onOpenLogic,
  onOpenResults,
  onOpenConnections,
  onOpenVoice,
  onDeleteAgent,
}: {
  blueprint: AgentBlueprint;
  detailsBlueprint?: AgentBlueprint;
  latestVersionNumber: number | null;
  voiceName: string;
  listStatus: string;
  pendingApproval: AgentApproval | null;
  review: AgentReview | null;
  metrics?: AgentMetricsSummary;
  activationGate?: AgentActivationGate;
  bindingStatus: AgentIntegrationBindingStatus[];
  actionLoading: boolean;
  onStartRun: () => void;
  onActivateVersion: (versionId: string) => void;
  onOpenLogic: () => void;
  onOpenResults: () => void;
  onOpenConnections: () => void;
  onOpenVoice: () => void;
  onDeleteAgent: () => void;
}) => {
  const needsApproval = Boolean(pendingApproval || blueprint.pending_approvals_count);
  const compiledValid = metrics?.compiled?.validation_valid === true;
  const compiledKnown = Boolean(metrics?.compiled?.validation_status || metrics?.compiled?.candidate_status);
  const missingBindings = bindingStatus.filter((binding) => binding.status !== 'connected' && binding.status !== 'ready').length;
  const requiredBindings = bindingStatus.length || Number(metrics?.setup?.required_bindings || 0);
  const connectorsReady = requiredBindings === 0 || missingBindings === 0;
  const previewReady = activationGate?.preview_run_status?.ready === true;
  const activationVersionId = activationGate?.active_version_id || blueprint.active_version_id || '';
  const settledTokens = Number(metrics?.cost_tokens?.settled_tokens || 0);
  const totalCost = Number(metrics?.cost_tokens?.total_cost || 0);
  const builderPreview = getBlueprintBuilderPreview(detailsBlueprint || blueprint);

  return (
    <div className="space-y-4">
      {needsApproval ? (
      <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <div className="text-sm font-semibold text-slate-950">Ждёт решения человека</div>
            <div className="mt-1 text-sm leading-6 text-amber-900">
              Проверьте pending approval: без решения человека агент не продолжит внешний шаг.
            </div>
            {pendingApproval ? (
              <div className="mt-2 rounded-xl bg-white/80 px-3 py-2 text-xs leading-5 text-amber-900 ring-1 ring-amber-100">
                {pendingApproval.title}: {explainApproval(pendingApproval)}
              </div>
            ) : null}
          </div>
          <div className="flex shrink-0 flex-wrap gap-2">
            <Button type="button" onClick={onOpenResults}>
              Открыть решение
            </Button>
            <Button type="button" variant="outline" onClick={onOpenLogic}>
              Изменить логику
            </Button>
          </div>
        </div>
      </div>
      ) : null}

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <AgentSummaryPill label="Статус" value={humanizeStatus(listStatus)} tone={needsApproval ? 'warning' : 'default'} />
        <AgentSummaryPill label="Последний запуск" value={formatLastRun(blueprint)} />
        <AgentSummaryPill label="Compiled" value={compiledKnown ? (compiledValid ? 'проверен' : 'ошибка') : 'черновик'} tone={compiledKnown && !compiledValid ? 'warning' : 'default'} />
        <AgentSummaryPill label="Подключения" value={requiredBindings ? `${Math.max(requiredBindings - missingBindings, 0)}/${requiredBindings}` : 'не нужны'} tone={connectorsReady ? 'default' : 'warning'} />
      </div>

      <AgentProductCockpit
        blueprint={blueprint}
        preview={builderPreview}
        activationGate={activationGate}
        connectorsReady={connectorsReady}
        compiledReady={!compiledKnown || compiledValid}
        previewReady={previewReady}
        actionLoading={actionLoading}
        onOpenConnections={onOpenConnections}
        onOpenLogic={onOpenLogic}
        onStartRun={onStartRun}
      />

      {activationGate ? (
        <ActivationGateDecisionCard
          gate={activationGate}
          activationVersionId={activationVersionId}
          actionLoading={actionLoading}
          onActivateVersion={onActivateVersion}
          onOpenConnections={onOpenConnections}
          onOpenLogic={onOpenLogic}
          onOpenResults={onOpenResults}
          onStartRun={onStartRun}
        />
      ) : null}

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(18rem,0.55fr)]">
        <div className="rounded-2xl border border-slate-200 bg-white px-4 py-4">
          <div className="text-sm font-semibold text-slate-950">Что делает агент</div>
          <div className="mt-2 text-sm leading-7 text-slate-700">
            {blueprint.description || blueprint.active_goal || blueprint.latest_goal || 'Описание появится после настройки логики агента.'}
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            <Button type="button" size="sm" variant="outline" onClick={onOpenLogic}>
              Логика и данные
            </Button>
            <Button type="button" size="sm" variant="outline" onClick={onOpenResults}>
              Запуски и обучение
            </Button>
            <Button type="button" size="sm" variant="outline" onClick={onOpenConnections}>
              Подключения
            </Button>
            <Button type="button" size="sm" variant="outline" onClick={onOpenVoice}>
              Голос и стиль
            </Button>
            <Button type="button" size="sm" variant="outline" className="text-red-700 hover:text-red-800" onClick={onDeleteAgent} disabled={actionLoading}>
              <Trash2 className="mr-2 h-4 w-4" />
              Архивировать
            </Button>
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white px-4 py-4">
          <div className="text-sm font-semibold text-slate-950">Готовность</div>
          <div className="mt-3 space-y-2 text-sm">
            <ReadinessRow label="Логика" ready={Boolean(latestVersionNumber)} readyText={`v${latestVersionNumber || 1}`} blockedText="нужна версия" />
            <ReadinessRow label="Validation" ready={!compiledKnown || compiledValid} readyText={compiledKnown ? 'пройден' : 'ожидает'} blockedText="исправить" />
            <ReadinessRow label="Подключения" ready={connectorsReady} readyText={requiredBindings ? 'готовы' : 'не нужны'} blockedText={`нужно ${missingBindings}`} />
            <ReadinessRow label="Preview" ready={previewReady} readyText="пройден" blockedText="нужен запуск" />
            <ReadinessRow label="Ручной контроль" ready blockedText="" readyText="включён" />
            <ReadinessRow label="Результаты" ready={Boolean(review?.has_run || blueprint.last_run_id)} readyText="есть запуск" blockedText="нет запуска" />
          </div>
          <div className="mt-3 rounded-xl bg-slate-50 px-3 py-2 text-xs leading-5 text-slate-600">
            {voiceName ? `Голос: ${voiceName}. ` : ''}
            Запусков загружено: {metrics?.runs?.loaded || 0}. Токены: {settledTokens}. Стоимость: {totalCost ? totalCost.toFixed(2) : '0'}.
          </div>
          <AgentBillingBreakdownPanel metrics={metrics} />
        </div>
      </div>
    </div>
  );
};

const AgentProductCockpit = ({
  blueprint,
  preview,
  activationGate,
  connectorsReady,
  compiledReady,
  previewReady,
  actionLoading,
  onOpenConnections,
  onOpenLogic,
  onStartRun,
}: {
  blueprint: AgentBlueprint;
  preview: AgentBuilderPreview | null;
  activationGate?: AgentActivationGate;
  connectorsReady: boolean;
  compiledReady: boolean;
  previewReady: boolean;
  actionLoading: boolean;
  onOpenConnections: () => void;
  onOpenLogic: () => void;
  onStartRun: () => void;
}) => {
  const summary = preview?.connection_summary;
  const missingItems = (summary?.items || []).filter((item) => item.action && !['ready', 'native_ready'].includes(item.action));
  const readyItems = (summary?.items || []).filter((item) => item.action === 'ready' || item.action === 'native_ready');
  const setupFlow = preview?.setup_flow;
  const nextStep = activationGate?.next_step || setupFlow?.post_create_next_step || setupFlow?.next_step || '';
  const needsConnections = !connectorsReady || missingItems.length > 0 || nextStep === 'connect_required_integrations';
  const needsLogic = !compiledReady || nextStep === 'fix_compiled_workflow';
  const canPreview = connectorsReady && compiledReady && !previewReady;
  const primaryLabel = needsConnections
    ? 'Подключить сервисы'
    : canPreview
      ? 'Проверить на примере'
      : needsLogic
        ? 'Открыть логику'
        : 'Открыть запуски';
  const PrimaryIcon = needsConnections ? Database : canPreview ? Play : needsLogic ? Workflow : Play;
  const primaryAction = needsConnections ? onOpenConnections : canPreview ? onStartRun : needsLogic ? onOpenLogic : onStartRun;
  const primaryVariant: 'default' | 'outline' = needsConnections || canPreview || needsLogic ? 'default' : 'outline';
  const task = preview?.understood_task || blueprint.description || blueprint.active_goal || blueprint.latest_goal || 'Настройте задачу агента.';
  const dataText = preview?.data_sources?.length
    ? preview.data_sources.map((item) => humanizeMeta(item)).join(', ')
    : readyItems.length
      ? readyItems.map((item) => item.title || connectorLabel(item.provider)).join(', ')
      : 'будет видно после настройки';
  const requiredText = missingItems.length
    ? missingItems.map((item) => item.title || connectorLabel(item.provider)).join(', ')
    : connectorsReady
      ? 'подключения готовы'
      : 'проверить подключения';
  const flowStatus = setupFlow?.status || (activationGate?.can_activate ? 'ready' : 'draft');
  return (
    <div className="rounded-2xl border border-slate-200 bg-white px-4 py-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <div className="text-sm font-semibold text-slate-950">Рабочая карточка агента</div>
            <span className="rounded-full bg-slate-50 px-2 py-0.5 text-[11px] font-medium text-slate-600 ring-1 ring-slate-200">
              {humanizeMeta(flowStatus)}
            </span>
          </div>
          <div className="mt-2 text-sm leading-7 text-slate-700">{task}</div>
        </div>
        <Button type="button" variant={primaryVariant} onClick={primaryAction} disabled={actionLoading} className="shrink-0">
          {actionLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <PrimaryIcon className="mr-2 h-4 w-4" />}
          {primaryLabel}
        </Button>
      </div>
      <div className="mt-4 grid gap-2 md:grid-cols-3">
        <AgentCockpitFact icon={Database} label="Данные" value={dataText} ready={Boolean(preview?.data_sources?.length || readyItems.length)} />
        <AgentCockpitFact icon={ShieldCheck} label="Доступы" value={requiredText} ready={!needsConnections} />
        <AgentCockpitFact icon={Play} label="Preview" value={previewReady ? 'пройден' : canPreview ? 'готов к проверке' : 'после preflight'} ready={previewReady} />
      </div>
      {missingItems.length ? (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {missingItems.slice(0, 4).map((item) => (
            <button
              key={item.key || item.provider || item.title}
              type="button"
              onClick={onOpenConnections}
              className="rounded-full bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-800 ring-1 ring-amber-200 transition hover:bg-amber-100"
            >
              {item.setup_cta?.label || `Подключить ${item.title || connectorLabel(item.provider)}`}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
};

const AgentCockpitFact = ({
  icon: Icon,
  label,
  value,
  ready,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
  ready: boolean;
}) => (
  <div className="rounded-xl bg-slate-50 px-3 py-3 ring-1 ring-slate-200">
    <div className="flex items-center gap-2 text-xs font-semibold uppercase text-slate-500">
      <Icon className={cn('h-4 w-4', ready ? 'text-emerald-600' : 'text-amber-600')} />
      {label}
    </div>
    <div className="mt-1 text-sm leading-6 text-slate-800">{value}</div>
  </div>
);

const ActivationGateDecisionCard = ({
  gate,
  activationVersionId,
  actionLoading,
  onActivateVersion,
  onOpenConnections,
  onOpenLogic,
  onOpenResults,
  onStartRun,
}: {
  gate: AgentActivationGate;
  activationVersionId: string;
  actionLoading: boolean;
  onActivateVersion: (versionId: string) => void;
  onOpenConnections: () => void;
  onOpenLogic: () => void;
  onOpenResults: () => void;
  onStartRun: () => void;
}) => {
  const decision = buildActivationGateDecision(gate);
  const ready = decision.tone === 'ready';
  const choice = decision.tone === 'choice';
  const blocked = decision.tone === 'blocked';
  const needsAction = decision.tone === 'needs_action';
  const blockerText = activationBlockerText(gate);
  const pathSteps = buildActivationPathSteps(gate);
  const runAction = () => {
    if (decision.action === 'activate') {
      onActivateVersion(activationVersionId);
      return;
    }
    if (decision.action === 'connections') {
      onOpenConnections();
      return;
    }
    if (decision.action === 'logic') {
      onOpenLogic();
      return;
    }
    if (decision.action === 'results') {
      onOpenResults();
      return;
    }
    if (decision.action === 'preview') {
      onStartRun();
    }
  };
  const canClick = decision.action === 'activate' ? Boolean(activationVersionId) : decision.action !== 'none';
  return (
    <div className={cn(
      'rounded-2xl border px-4 py-4 text-sm leading-6',
      ready ? 'border-emerald-200 bg-emerald-50 text-emerald-950' : '',
      choice ? 'border-sky-200 bg-sky-50 text-sky-950' : '',
      needsAction ? 'border-amber-200 bg-amber-50 text-amber-950' : '',
      blocked ? 'border-rose-200 bg-rose-50 text-rose-950' : '',
      !ready && !choice && !needsAction && !blocked ? 'border-slate-200 bg-slate-50 text-slate-700' : '',
    )}>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="font-semibold">{decision.title}</div>
          <div className="mt-1 text-xs leading-5">{decision.description}</div>
          {blockerText && !ready ? (
            <div className="mt-2 rounded-xl bg-white/80 px-3 py-2 text-xs leading-5 ring-1 ring-current/10">
              Почему ждём: {blockerText}
            </div>
          ) : null}
          <div className="mt-2 flex flex-wrap gap-1.5">
            <span className="rounded-full bg-white/80 px-2 py-0.5 text-[11px] font-medium ring-1 ring-current/10">
              Preview: {gate.preview_run_status?.ready ? 'пройден' : 'нужен'}
            </span>
            <span className="rounded-full bg-white/80 px-2 py-0.5 text-[11px] font-medium ring-1 ring-current/10">
              Preflight: {gate.preflight?.ready ? 'готов' : 'проверить'}
            </span>
            <span className="rounded-full bg-white/80 px-2 py-0.5 text-[11px] font-medium ring-1 ring-current/10">
              Compiled: {gate.compiled_validation?.ready ? 'валиден' : 'проверить'}
            </span>
            <span className="rounded-full bg-white/80 px-2 py-0.5 text-[11px] font-medium ring-1 ring-current/10">
              Policy: {gate.approval_policy_status?.ready ? 'готова' : 'проверить'}
            </span>
          </div>
          <AgentActivationPathStrip steps={pathSteps} />
        </div>
        {decision.cta ? (
          <Button
            type="button"
            size="sm"
            variant={ready ? 'default' : 'outline'}
            className={cn(!ready && 'bg-white')}
            onClick={runAction}
            disabled={actionLoading || !canClick}
          >
            {actionLoading && decision.action === 'preview' ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : ready ? <CheckCircle2 className="mr-2 h-4 w-4" /> : decision.action === 'preview' ? <Play className="mr-2 h-4 w-4" /> : <Zap className="mr-2 h-4 w-4" />}
            {decision.cta}
          </Button>
        ) : null}
      </div>
      {!ready && gate.connection_plan ? (
        <AgentConnectionPlanPanel connectionPlan={gate.connection_plan} compact />
      ) : null}
    </div>
  );
};

const AgentActivationPathStrip = ({ steps }: { steps: AgentActivationPathStep[] }) => (
  <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
    {steps.map((step, index) => {
      const done = step.status === 'done';
      const current = step.status === 'current';
      return (
        <div
          key={step.key}
          className={cn(
            'rounded-xl border bg-white/75 px-3 py-2 ring-1 ring-current/5',
            done ? 'border-emerald-200 text-emerald-900' : '',
            current ? 'border-sky-200 text-sky-900' : '',
            !done && !current ? 'border-slate-200 text-slate-500' : '',
          )}
        >
          <div className="flex items-center gap-2 text-xs font-semibold">
            <span className={cn(
              'flex h-5 w-5 items-center justify-center rounded-full text-[11px]',
              done ? 'bg-emerald-100 text-emerald-700' : '',
              current ? 'bg-sky-100 text-sky-700' : '',
              !done && !current ? 'bg-slate-100 text-slate-500' : '',
            )}>
              {done ? <CheckCircle2 className="h-3.5 w-3.5" /> : index + 1}
            </span>
            {step.label}
          </div>
          <div className="mt-1 text-[11px] leading-4 opacity-80">{step.detail}</div>
        </div>
      );
    })}
  </div>
);

const ReadinessRow = ({
  label,
  ready,
  readyText,
  blockedText,
}: {
  label: string;
  ready: boolean;
  readyText: string;
  blockedText: string;
}) => (
  <div className="flex items-center justify-between gap-3 rounded-xl bg-slate-50 px-3 py-2">
    <span className="text-slate-600">{label}</span>
    <span className={cn('rounded-full px-2 py-0.5 text-xs font-medium ring-1', ready ? 'bg-emerald-50 text-emerald-700 ring-emerald-200' : 'bg-amber-50 text-amber-800 ring-amber-200')}>
      {ready ? readyText : blockedText}
    </span>
  </div>
);

const AgentBillingBreakdownPanel = ({ metrics }: { metrics?: AgentMetricsSummary }) => {
  const items = metrics?.billing_breakdown?.items || metrics?.cost_tokens?.breakdown || [];
  const visibleItems = items.filter((item) => Boolean(item.count || item.charged_credits || item.estimated_credits || item.settled_tokens || item.total_cost));
  if (!visibleItems.length) {
    return (
      <div className="mt-3 rounded-xl bg-white px-3 py-2 text-xs leading-5 text-slate-500 ring-1 ring-slate-200">
        Расходы появятся после compile, preview или production run.
      </div>
    );
  }
  return (
    <div className="mt-3 rounded-xl bg-white px-3 py-3 ring-1 ring-slate-200">
      <div className="flex items-center gap-2 text-xs font-semibold uppercase text-slate-500">
        <ReceiptText className="h-4 w-4 text-slate-500" />
        Расходы
      </div>
      <div className="mt-2 space-y-1.5">
        {visibleItems.slice(0, 5).map((item) => (
          <div key={item.key || item.label} className="flex items-center justify-between gap-3 text-xs leading-5">
            <span className="min-w-0 truncate text-slate-600">{item.label || humanizeMeta(item.key || 'cost')}</span>
            <span className="shrink-0 font-medium text-slate-900">
              {formatBillingBreakdownValue(item)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};

const formatBillingBreakdownValue = (item: AgentBillingBreakdownItem) => {
  if (item.charged_credits) {
    return `${item.charged_credits} кр.`;
  }
  if (item.total_cost) {
    return item.total_cost.toFixed(2);
  }
  if (item.settled_tokens) {
    return `${item.settled_tokens} ток.`;
  }
  if (item.estimated_credits) {
    return `~${item.estimated_credits} кр.`;
  }
  return `${item.count || 0}`;
};

const AgentConnectionsPanel = ({
  agentIntegrations,
  availableAgentIntegrations,
  agentIntegrationCatalog,
  agentExternalAuthOptions,
  agentBindingStatus,
  agentConnectionPlan,
  selectedConnectionBindingKey,
  sheetSpreadsheetId,
  sheetName,
  sheetAuthRef,
  sheetDailyCap,
  telegramBotMode,
  telegramDailyCap,
  matonAuthRef,
  matonChannel,
  matonDailyCap,
  processRowValues,
  processPreviewMessage,
  actionLoading,
  onSheetSpreadsheetIdChange,
  onSheetNameChange,
  onSheetAuthRefChange,
  onSheetDailyCapChange,
  onTelegramBotModeChange,
  onTelegramDailyCapChange,
  onMatonAuthRefChange,
  onMatonChannelChange,
  onMatonDailyCapChange,
  onProcessRowValuesChange,
  onProcessPreviewMessageChange,
  onSaveSheetIntegration,
  onSaveTelegramIntegration,
  onSaveMatonIntegration,
  onChooseProviderRoute,
  onAttachExistingIntegration,
  onSelectConnectionBinding,
  onSaveCustomProcess,
  onRunCustomProcessPreview,
  onPreviewRun,
}: {
  agentIntegrations: AgentIntegration[];
  availableAgentIntegrations: AgentIntegration[];
  agentIntegrationCatalog: AgentIntegrationCatalogItem[];
  agentExternalAuthOptions: AgentExternalAuthOption[];
  agentBindingStatus: AgentIntegrationBindingStatus[];
  agentConnectionPlan: AgentConnectionPlan | null;
  selectedConnectionBindingKey: string;
  sheetSpreadsheetId: string;
  sheetName: string;
  sheetAuthRef: string;
  sheetDailyCap: string;
  telegramBotMode: string;
  telegramDailyCap: string;
  matonAuthRef: string;
  matonChannel: string;
  matonDailyCap: string;
  processRowValues: string;
  processPreviewMessage: string;
  actionLoading: boolean;
  onSheetSpreadsheetIdChange: (value: string) => void;
  onSheetNameChange: (value: string) => void;
  onSheetAuthRefChange: (value: string) => void;
  onSheetDailyCapChange: (value: string) => void;
  onTelegramBotModeChange: (value: string) => void;
  onTelegramDailyCapChange: (value: string) => void;
  onMatonAuthRefChange: (value: string) => void;
  onMatonChannelChange: (value: string) => void;
  onMatonDailyCapChange: (value: string) => void;
  onProcessRowValuesChange: (value: string) => void;
  onProcessPreviewMessageChange: (value: string) => void;
  onSaveSheetIntegration: () => void;
  onSaveTelegramIntegration: () => void;
  onSaveMatonIntegration: () => void;
  onChooseProviderRoute: (bindingKey: string, route: AgentProviderRoute) => void;
  onAttachExistingIntegration: (integration: AgentIntegration, bindingKey?: string) => void;
  onSelectConnectionBinding: (bindingKey: string) => void;
  onSaveCustomProcess: () => void;
  onRunCustomProcessPreview: () => void;
  onPreviewRun: () => void;
}) => (
  <div className="space-y-4">
    {postCreateHandoff?.status === 'needs_connections' ? (
      <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm leading-6 text-amber-950">
        <div className="font-semibold">{postCreateHandoff.title || 'Остались подключения'}</div>
        <div className="mt-1">{postCreateHandoff.description || 'Заполните обязательные подключения, затем проверьте агента на примере.'}</div>
        {postCreateHandoff.missing_bindings?.length ? (
          <div className="mt-2 flex flex-wrap gap-2">
            {postCreateHandoff.missing_bindings.slice(0, 4).map((binding) => (
              <span key={binding.key || binding.provider} className="rounded-full bg-white px-2.5 py-1 text-xs font-medium text-amber-900 ring-1 ring-amber-200">
                {connectorLabel(binding.provider)}{binding.missing_config?.length ? `: ${binding.missing_config.join(', ')}` : ''}
              </span>
            ))}
          </div>
        ) : null}
      </div>
    ) : null}
    <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
      <div className="text-sm font-semibold text-slate-950">Подключения агента</div>
      <div className="mt-1 max-w-3xl text-sm leading-6 text-slate-600">
        Здесь настраиваются входящие каналы, внешняя запись и безопасный процесс доставки. Логика агента остаётся во вкладке “Логика”.
      </div>
    </div>
    <AgentConnectionPlanPanel
      connectionPlan={agentConnectionPlan}
      availableIntegrations={availableAgentIntegrations}
      actionLoading={actionLoading}
      onAttachExistingIntegration={onAttachExistingIntegration}
      onConfigureBinding={onSelectConnectionBinding}
      onChooseProviderRoute={onChooseProviderRoute}
    />
    <AgentIntegrationsPanel
      integrations={agentIntegrations}
      availableIntegrations={availableAgentIntegrations}
      providerCatalog={agentIntegrationCatalog}
      authOptions={agentExternalAuthOptions}
      bindingStatus={agentBindingStatus}
      connectionPlan={agentConnectionPlan}
      selectedBindingKey={selectedConnectionBindingKey}
      sheetSpreadsheetId={sheetSpreadsheetId}
      sheetName={sheetName}
      sheetAuthRef={sheetAuthRef}
      sheetDailyCap={sheetDailyCap}
      telegramBotMode={telegramBotMode}
      telegramDailyCap={telegramDailyCap}
      matonAuthRef={matonAuthRef}
      matonChannel={matonChannel}
      matonDailyCap={matonDailyCap}
      processRowValues={processRowValues}
      processPreviewMessage={processPreviewMessage}
      actionLoading={actionLoading}
      onSheetSpreadsheetIdChange={onSheetSpreadsheetIdChange}
      onSheetNameChange={onSheetNameChange}
      onSheetAuthRefChange={onSheetAuthRefChange}
      onSheetDailyCapChange={onSheetDailyCapChange}
      onTelegramBotModeChange={onTelegramBotModeChange}
      onTelegramDailyCapChange={onTelegramDailyCapChange}
      onMatonAuthRefChange={onMatonAuthRefChange}
      onMatonChannelChange={onMatonChannelChange}
      onMatonDailyCapChange={onMatonDailyCapChange}
      onProcessRowValuesChange={onProcessRowValuesChange}
      onProcessPreviewMessageChange={onProcessPreviewMessageChange}
        onSaveSheetIntegration={onSaveSheetIntegration}
        onSaveTelegramIntegration={onSaveTelegramIntegration}
        onSaveMatonIntegration={onSaveMatonIntegration}
        onChooseProviderRoute={onChooseProviderRoute}
      onAttachExistingIntegration={onAttachExistingIntegration}
      onSelectBinding={onSelectConnectionBinding}
      onSaveCustomProcess={onSaveCustomProcess}
      onRunCustomProcessPreview={onRunCustomProcessPreview}
      onPreviewRun={onPreviewRun}
    />
  </div>
);

const AgentConnectionPlanPanel = ({
  connectionPlan,
  compact = false,
  availableIntegrations = [],
  actionLoading = false,
  onAttachExistingIntegration,
  onConfigureBinding,
  onChooseProviderRoute,
}: {
  connectionPlan: AgentConnectionPlan | null;
  compact?: boolean;
  availableIntegrations?: AgentIntegration[];
  actionLoading?: boolean;
  onAttachExistingIntegration?: (integration: AgentIntegration, bindingKey?: string) => void;
  onConfigureBinding?: (bindingKey: string) => void;
  onChooseProviderRoute?: (bindingKey: string, route: AgentProviderRoute) => void;
}) => {
  const items = Array.isArray(connectionPlan?.items) ? connectionPlan.items : [];
  if (!items.length) {
    return null;
  }
  const missingCount = typeof connectionPlan?.missing_count === 'number'
    ? connectionPlan.missing_count
    : items.filter((item) => !['ready', 'native_ready'].includes(item.action || '')).length;
  return (
    <div className={cn(compact ? 'mt-3 rounded-xl border px-3 py-3' : 'rounded-2xl border px-4 py-4', missingCount ? 'border-amber-200 bg-amber-50/70' : 'border-emerald-200 bg-emerald-50/70')}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-slate-950">План подключений</div>
          <div className="mt-1 text-xs leading-5 text-slate-600">
            {missingCount ? 'LocalOS понял, какие доступы нужны агенту. Завершите пункты ниже перед активацией.' : 'Все обязательные доступы готовы для preflight и активации.'}
          </div>
        </div>
        <span className={cn('rounded-full px-2.5 py-1 text-xs font-medium ring-1', missingCount ? 'bg-white text-amber-800 ring-amber-200' : 'bg-white text-emerald-800 ring-emerald-200')}>
          {missingCount ? `${missingCount} действий` : 'готово'}
        </span>
      </div>
      <div className={cn('mt-3 grid gap-2', compact ? 'sm:grid-cols-1' : 'lg:grid-cols-2')}>
        {(compact ? items.slice(0, 3) : items).map((item) => {
          const matchingExisting = (item.existing_integrations || [])
            .map((summary) => availableIntegrations.find((integration) => integration.id === summary.id))
            .filter((integration) => Boolean(integration));
          return (
          <div key={item.key || item.provider || item.title} className="rounded-xl bg-white px-3 py-3 text-sm ring-1 ring-slate-200">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="font-semibold text-slate-950">{item.title || connectorLabel(item.provider)}</div>
                <div className="mt-1 text-xs leading-5 text-slate-500">
                  {humanizeMeta(item.capability || item.trigger || item.direction || item.provider || 'binding')}
                </div>
              </div>
              <span className={cn('shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ring-1', connectionActionTone(item.action || ''))}>
                {item.primary_label || humanizeMeta(item.action || 'проверить')}
              </span>
            </div>
            <div className="mt-2 text-xs leading-5 text-slate-600">{item.route_summary || item.explanation || bindingActionHint({ key: item.key || '', provider: item.provider || '', status: item.binding_status || '' })}</div>
            {item.why_blocked && item.action !== 'ready' && item.action !== 'native_ready' ? (
              <div className="mt-2 rounded-lg bg-amber-50 px-2.5 py-2 text-xs leading-5 text-amber-900 ring-1 ring-amber-100">
                Чего не хватает: {item.why_blocked}
              </div>
            ) : null}
            {item.policy_summary ? (
              <div className="mt-2 rounded-lg bg-slate-50 px-2.5 py-2 text-xs leading-5 text-slate-700 ring-1 ring-slate-100">
                {item.policy_summary}
              </div>
            ) : null}
            {agentPolicyFacts(item).length ? (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {agentPolicyFacts(item).map((fact) => (
                  <span key={`${item.key}-${fact}`} className="rounded-full bg-slate-50 px-2 py-0.5 text-[11px] font-medium text-slate-600 ring-1 ring-slate-200">
                    {humanizeMeta(fact)}
                  </span>
                ))}
              </div>
            ) : null}
            {item.provider_routes?.length ? (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {item.provider_routes.slice(0, 5).map((route) => (
                  <ProviderActionPill
                    key={`${item.key}-${route.provider}-${route.role}`}
                    route={route}
                    disabled={actionLoading || !item.key}
                    onChoose={compact ? undefined : onChooseProviderRoute ? () => onChooseProviderRoute(item.key || '', route) : undefined}
                  />
                ))}
              </div>
            ) : null}
            <RecommendedProviderRouteNote
              route={item.recommended_route}
              reason={item.recommended_route_reason}
            />
            {item.existing_integrations?.length ? (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {item.existing_integrations.slice(0, 3).map((integration) => (
                  <span key={integration.id || integration.display_name} className="rounded-full bg-sky-50 px-2 py-0.5 text-[11px] font-medium text-sky-700 ring-1 ring-sky-100">
                    {integration.display_name || connectorLabel(integration.provider)}
                  </span>
                ))}
              </div>
            ) : null}
            {!compact && item.action === 'choose_existing' && matchingExisting.length && onAttachExistingIntegration ? (
              <div className="mt-2 flex flex-wrap gap-2">
                {matchingExisting.slice(0, 3).map((integration) => integration ? (
                  <Button
                    key={integration.id}
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() => onAttachExistingIntegration(integration, item.key || '')}
                    disabled={actionLoading}
                  >
                    Использовать {integration.display_name || connectorLabel(integration.provider)}
                  </Button>
                ) : null)}
              </div>
            ) : null}
            {!compact && item.action !== 'ready' && item.action !== 'native_ready' && onConfigureBinding ? (
              <div className="mt-2">
                <Button
                  type="button"
                  size="sm"
                  variant={item.action === 'choose_existing' ? 'outline' : 'default'}
                  onClick={() => onConfigureBinding(item.key || '')}
                  disabled={actionLoading || !item.key}
                >
                  {item.setup_cta?.label || `Настроить ${connectorLabel(item.provider)}`}
                </Button>
              </div>
            ) : null}
            {item.provider_paths?.length ? (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {item.provider_paths.slice(0, 4).map((path) => (
                  <span key={`${path.provider}-${path.status}`} className="rounded-full bg-slate-50 px-2 py-0.5 text-[11px] text-slate-600 ring-1 ring-slate-200">
                    {path.label || path.provider}: {humanizeMeta(path.status || 'unknown')}
                  </span>
                ))}
              </div>
            ) : null}
          </div>
          );
        })}
      </div>
      {compact && items.length > 3 ? (
        <div className="mt-2 text-[11px] leading-4 text-slate-500">Ещё {items.length - 3} подключений будут видны после создания draft.</div>
      ) : null}
    </div>
  );
};

const connectionActionTone = (action: string) => {
  if (action === 'ready' || action === 'native_ready') {
    return 'bg-emerald-50 text-emerald-700 ring-emerald-200';
  }
  if (action === 'choose_existing' || action === 'choose_route') {
    return 'bg-sky-50 text-sky-700 ring-sky-200';
  }
  if (action === 'planned_provider') {
    return 'bg-slate-50 text-slate-600 ring-slate-200';
  }
  return 'bg-amber-50 text-amber-700 ring-amber-200';
};

const agentPolicyFacts = (item: AgentConnectionPlanItem) => {
  const rawFacts = [
    item.autonomy_level,
    item.execution_boundary,
    item.credential_state,
    item.approval_state,
    item.next_action_label,
  ];
  const facts: string[] = [];
  rawFacts.forEach((fact) => {
    const normalized = String(fact || '').trim();
    if (normalized && !facts.includes(normalized)) {
      facts.push(normalized);
    }
  });
  return facts.slice(0, 5);
};

const providerRouteLabel = (state: string) => ({
  connected: 'подключено',
  available: 'доступно',
  manual: 'ручной режим',
  planned: 'позже',
  unavailable: 'недоступно',
}[state] || humanizeMeta(state || 'unknown'));

const providerRouteTone = (state: string) => {
  if (state === 'connected' || state === 'available') {
    return 'bg-emerald-50 text-emerald-700 ring-emerald-200';
  }
  if (state === 'manual') {
    return 'bg-sky-50 text-sky-700 ring-sky-200';
  }
  if (state === 'planned') {
    return 'bg-slate-50 text-slate-600 ring-slate-200';
  }
  return 'bg-rose-50 text-rose-700 ring-rose-200';
};

const providerActionLabel = (route?: AgentProviderRoute | null) => {
  const action = route?.provider_action;
  if (action?.label) {
    return action.label;
  }
  return route?.primary_cta || providerRouteLabel(route?.state || route?.status || '');
};

const providerActionDescription = (route?: AgentProviderRoute | null) => {
  const action = route?.provider_action;
  if (action?.description) {
    return action.description;
  }
  if (route?.connect_mode === 'openclaw_policy_boundary') {
    return 'OpenClaw используется только внутри LocalOS policy, approval, audit и limits.';
  }
  if (route?.connect_mode === 'external_account_key') {
    return 'Выберите сохранённый API key или добавьте его в интеграциях бизнеса.';
  }
  if (route?.connect_mode === 'planned_oauth_connector') {
    return 'OAuth connector запланирован и пока не активирует агента.';
  }
  return '';
};

const ProviderActionPill = ({
  route,
  onChoose,
  disabled = false,
}: {
  route?: AgentProviderRoute | null;
  onChoose?: () => void;
  disabled?: boolean;
}) => {
  if (!route) {
    return null;
  }
  const state = route.state || route.status || '';
  const canChoose = Boolean(onChoose && ['openclaw', 'maton', 'manual'].includes(route.provider || '') && route.provider_action?.available !== false && ['available', 'connected', 'manual'].includes(state));
  const className = cn(
    'rounded-full px-2 py-0.5 text-[11px] font-medium ring-1',
    providerRouteTone(state),
    canChoose ? 'transition hover:shadow-sm disabled:cursor-not-allowed disabled:opacity-60' : '',
  );
  const label = `${route.label || connectorLabel(route.provider)} · ${providerActionLabel(route)}`;
  if (canChoose) {
    return (
      <button type="button" className={className} onClick={onChoose} disabled={disabled}>
        {label}
      </button>
    );
  }
  return (
    <span className={className}>
      {label}
    </span>
  );
};

const AgentAdvancedPanel = ({
  activeRun,
  versions,
  activationGate,
  actionLoading,
  onPreviewNextStepAction,
  onActivateVersion,
  onApplyFinanceRequests,
}: {
  activeRun: AgentRun | null;
  versions: Array<Record<string, unknown>>;
  activationGate?: AgentActivationGate;
  actionLoading: boolean;
  onPreviewNextStepAction: (nextStep: string) => void;
  onActivateVersion: (versionId: string) => void;
  onApplyFinanceRequests: (runId: string) => void;
}) => (
  <div className="space-y-4">
    <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
      <div className="text-sm font-semibold text-slate-950">Advanced runtime</div>
      <div className="mt-1 max-w-3xl text-sm leading-6 text-slate-600">
        Технический слой для superadmin/debug: raw workflow versions, action ledger, OpenClaw billing, artifacts, approvals и support export.
      </div>
    </div>
    {activeRun ? (
      <>
        <AgentRunObservabilityPanel
          run={activeRun}
          activationGate={activationGate}
          actionLoading={actionLoading}
          onPreviewNextStepAction={onPreviewNextStepAction}
          onActivateVersion={onActivateVersion}
          onApplyFinanceRequests={onApplyFinanceRequests}
        />
        <div className="grid gap-4 xl:grid-cols-3">
          <RunColumn title="Шаги runtime" icon={Clock3}>
            {(activeRun.steps || []).map((step) => (
              <TimelineItem key={step.id} title={humanizeStep(step.step_key)} meta={humanizeMeta(step.step_type)} status={step.status} />
            ))}
          </RunColumn>
          <RunColumn title="Сохранённые результаты" icon={FileCheck2}>
            {(activeRun.artifacts || []).map((artifact) => <ArtifactItem key={artifact.id} artifact={artifact} />)}
          </RunColumn>
          <RunColumn title="Решения" icon={ShieldCheck}>
            {(activeRun.approvals || []).map((approval) => (
              <TimelineItem key={approval.id} title={approval.title} meta={humanizeMeta(approval.approval_type)} status={approval.status} />
            ))}
          </RunColumn>
        </div>
      </>
    ) : (
      <DashboardEmptyState
        title="Нет выбранного запуска"
        description="Запустите агента или откройте результат, чтобы увидеть runtime ledger и support export."
      />
    )}
    <details className="rounded-2xl border border-slate-200 bg-white px-4 py-3">
      <summary className="cursor-pointer text-sm font-semibold text-slate-700 hover:text-slate-950">
        Raw versions payload
      </summary>
      <pre className="mt-3 max-h-96 overflow-auto rounded-xl bg-slate-950 p-3 text-[11px] leading-5 text-slate-100">
        {JSON.stringify(versions.slice(0, 5), null, 2)}
      </pre>
    </details>
  </div>
);

const AgentVoiceStylePanel = ({
  blueprint,
  availablePersonaAgents,
}: {
  blueprint: AgentBlueprint;
  availablePersonaAgents: PersonaAgent[];
}) => {
  const voiceName = getAgentVoiceName(blueprint);
  const productAgent = blueprint.product_agent || {};
  const personaId = blueprint.active_persona_agent_id || blueprint.latest_persona_agent_id || productAgent.persona_agent_id || '';
  return (
    <div className="space-y-4">
      <div className="grid gap-4 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
        <div className="rounded-2xl border border-slate-200 bg-white p-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="text-sm font-semibold text-slate-950">Голос выбранного агента</div>
              <div className="mt-1 text-sm leading-6 text-slate-600">
                Голос задаёт стиль общения. Логика, ручные подтверждения и разрешённые действия остаются в настройках агента.
              </div>
            </div>
            <StatusBadge status={voiceName ? 'active' : 'draft'} />
          </div>
          <div className="mt-4 grid gap-2">
            <AgentSummaryPill label="Текущий голос" value={voiceName || 'не привязан'} />
            <AgentSummaryPill label="Связь" value={String(personaId || 'нет связи')} />
            <AgentSummaryPill label="Источник" value="старый голос AIAgents" />
          </div>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-4">
          <div className="text-sm font-semibold text-slate-950">Доступные голоса</div>
          <div className="mt-1 text-sm leading-6 text-slate-600">
            Эти записи больше не отдельные пользовательские агенты. Они ждут привязки как “Голос агента”.
          </div>
          <div className="mt-4 grid gap-2 md:grid-cols-2">
            {availablePersonaAgents.length ? availablePersonaAgents.map((agent) => (
              <div key={agent.id} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="truncate text-sm font-semibold text-slate-950">{agent.name || 'Голос агента'}</div>
                    <div className="mt-1 text-xs text-slate-500">{agent.type || 'голос'} · {agent.is_active === false ? 'выключен' : 'доступен'}</div>
                  </div>
                  {agent.id === personaId ? <StatusBadge status="active" /> : null}
                </div>
                <div className="mt-2 line-clamp-2 text-xs leading-5 text-slate-600">
                  {agent.description || agent.task || agent.identity || 'Стиль общения без отдельной логики запуска.'}
                </div>
              </div>
            )) : (
              <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50 px-3 py-3 text-sm text-slate-500">
                Старых голосов пока нет. Их можно создать отдельно и потом привязать к версии агента.
              </div>
            )}
          </div>
        </div>
      </div>
      <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4">
        <div className="text-sm font-semibold text-amber-950">Старая логика больше не основной редактор</div>
        <div className="mt-1 text-sm leading-6 text-amber-900">
          AIAgents показываются как голоса. Логика агента редактируется через версии, diff, активацию и откат.
        </div>
      </div>
    </div>
  );
};

const AgentWorkspacePanel = ({
  versions,
  learningEvents,
  versionEvents,
  legacyMigration,
  latestVersionNumber,
  activeVersionId,
  setupDataSources,
  setupExtractionRules,
  setupProcessingRules,
  setupOutputFormat,
  setupManualControl,
  sourceName,
  sourceText,
  internalSource,
  sourceCatalog,
  review,
  actionLoading,
  onSetupDataSourcesChange,
  onSetupExtractionRulesChange,
  onSetupProcessingRulesChange,
  onSetupOutputFormatChange,
  onSetupManualControlChange,
  onSourceNameChange,
  onSourceTextChange,
  onInternalSourceChange,
  onSaveSetup,
  onStartVersionRun,
  onActivateVersion,
  onRollbackVersion,
  onAddTextSource,
  onAddInternalSource,
  onAddCatalogSource,
  onAddFileSource,
}: {
  versions: Array<Record<string, unknown>>;
  learningEvents: AgentLearningEvent[];
  versionEvents: AgentVersionEvent[];
  legacyMigration: Record<string, unknown>;
  latestVersionNumber: number | null;
  activeVersionId: string;
  setupDataSources: string;
  setupExtractionRules: string;
  setupProcessingRules: string;
  setupOutputFormat: string;
  setupManualControl: string;
  sourceName: string;
  sourceText: string;
  internalSource: string;
  sourceCatalog: AgentSourceCatalogItem[];
  review: AgentReview | null;
  actionLoading: boolean;
  onSetupDataSourcesChange: (value: string) => void;
  onSetupExtractionRulesChange: (value: string) => void;
  onSetupProcessingRulesChange: (value: string) => void;
  onSetupOutputFormatChange: (value: string) => void;
  onSetupManualControlChange: (value: string) => void;
  onSourceNameChange: (value: string) => void;
  onSourceTextChange: (value: string) => void;
  onInternalSourceChange: (value: string) => void;
  onSaveSetup: () => void;
  onStartVersionRun: (versionId: string) => void;
  onActivateVersion: (versionId: string) => void;
  onRollbackVersion: (versionId: string) => void;
  onAddTextSource: () => void;
  onAddInternalSource: () => void;
  onAddCatalogSource: (sourceKey: string) => void;
  onAddFileSource: (file?: File | null) => void;
}) => (
  <DashboardSection
    title="Настройка агента"
    description="Данные, правила, результат и ручной контроль. Технический JSON спрятан в расширенном режиме."
  >
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1.2fr)_minmax(20rem,0.8fr)]">
      <div className="grid gap-3">
        <VersionSummary
          versions={versions}
          latestVersionNumber={latestVersionNumber}
          activeVersionId={activeVersionId}
          onStartVersionRun={onStartVersionRun}
          onActivateVersion={onActivateVersion}
          onRollbackVersion={onRollbackVersion}
        />
        <LearningHistoryPanel
          learningEvents={learningEvents}
          versionEvents={versionEvents}
          legacyMigration={legacyMigration}
        />
        <WizardTextArea label="Какие данные использовать" value={setupDataSources} onChange={onSetupDataSourcesChange} placeholder="Например: профиль бизнеса, отзывы, файл с договором" />
        <WizardTextArea label="Что извлечь или понять" value={setupExtractionRules} onChange={onSetupExtractionRulesChange} placeholder="Например: риски, сроки, суммы, обязательства сторон" />
        <WizardTextArea label="Какие правила применить" value={setupProcessingRules} onChange={onSetupProcessingRulesChange} placeholder="Например: выделять спорные условия и не придумывать факты" />
        <WizardTextArea label="Какой результат подготовить" value={setupOutputFormat} onChange={onSetupOutputFormatChange} placeholder="Например: краткий отчёт, письмо клиенту, таблица исключений" />
        <WizardTextArea label="Где нужен ручной контроль" value={setupManualControl} onChange={onSetupManualControlChange} placeholder="Например: перед отправкой письма или публикацией ответа" />
        <div>
          <Button type="button" onClick={onSaveSetup} disabled={actionLoading}>
            {actionLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <CheckCircle2 className="mr-2 h-4 w-4" />}
            Сохранить настройку
          </Button>
        </div>
      </div>
      <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
        <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-900">
          <Database className="h-4 w-4" />
          Данные агента
        </div>
        <div className="space-y-3">
          <input
            className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400"
            value={sourceName}
            onChange={(event) => onSourceNameChange(event.target.value)}
            placeholder="Название источника"
          />
          <textarea
            className="min-h-24 w-full resize-none rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400"
            value={sourceText}
            onChange={(event) => onSourceTextChange(event.target.value)}
            placeholder="Вставьте текст, шаблон письма, выдержку из документа или CSV"
          />
          <div className="flex flex-wrap gap-2">
            <Button type="button" size="sm" onClick={onAddTextSource} disabled={actionLoading || !sourceText.trim()}>
              Добавить текст
            </Button>
            <label className="inline-flex cursor-pointer items-center rounded-md border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50">
              <Upload className="mr-2 h-4 w-4" />
              Файл
              <input
                type="file"
                className="hidden"
                accept=".txt,.csv,.tsv,.md,.pdf,.docx,.xlsx"
                onChange={(event) => {
                  void onAddFileSource(event.target.files?.[0] || null);
                  event.target.value = '';
                }}
              />
            </label>
          </div>
          <div className="flex gap-2">
            <select
              className="min-w-0 flex-1 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400"
              value={internalSource}
              onChange={(event) => onInternalSourceChange(event.target.value)}
            >
              <option value="business_profile">Профиль бизнеса</option>
              <option value="services">Услуги</option>
              <option value="reviews">Отзывы</option>
              <option value="prospectingleads">Лиды</option>
              <option value="outreach_drafts">Черновики outreach</option>
            </select>
            <Button type="button" size="sm" variant="outline" onClick={onAddInternalSource} disabled={actionLoading}>
              Подключить
            </Button>
          </div>
          <DatahubCatalogList
            catalog={sourceCatalog}
            actionLoading={actionLoading}
            onConnect={onAddCatalogSource}
          />
          <AgentSourcesList sources={review?.sources || []} />
        </div>
      </div>
    </div>
  </DashboardSection>
);

const WizardTextArea = ({ label, value, onChange, placeholder }: { label: string; value: string; onChange: (value: string) => void; placeholder: string }) => (
  <label className="text-xs font-medium text-slate-600">
    {label}
    <textarea
      className="mt-1 min-h-16 w-full resize-none rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-slate-400"
      value={value}
      onChange={(event) => onChange(event.target.value)}
      placeholder={placeholder}
    />
  </label>
);

const DatahubCatalogList = ({
  catalog,
  actionLoading,
  onConnect,
}: {
  catalog: AgentSourceCatalogItem[];
  actionLoading: boolean;
  onConnect: (sourceKey: string) => void;
}) => {
  const connected = catalog.filter((item) => item.connected);
  const available = catalog.filter((item) => !item.connected);
  return (
    <div className="space-y-3 rounded-xl border border-slate-200 bg-white p-3">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Данные агента</div>
          <div className="mt-1 text-xs text-slate-500">Сначала подключённые источники, ниже доступные источники LocalOS.</div>
        </div>
        <span className="text-xs text-slate-400">{catalog.length ? `${catalog.length} источников` : 'источники не загружены'}</span>
      </div>
      {catalog.length ? (
        <>
          <DatahubCatalogGroup
            title="Подключено к агенту"
            emptyText="У агента пока нет подключённых источников."
            items={connected}
            actionLoading={actionLoading}
            onConnect={onConnect}
          />
          <DatahubCatalogGroup
            title="Доступно в LocalOS"
            emptyText="Доступных источников LocalOS пока нет."
            items={available}
            actionLoading={actionLoading}
            onConnect={onConnect}
          />
        </>
      ) : (
        <div className="rounded-lg border border-dashed border-slate-200 px-3 py-3 text-sm text-slate-500">
          Каталог появится после выбора агента.
        </div>
      )}
    </div>
  );
};

const DatahubCatalogGroup = ({
  title,
  emptyText,
  items,
  actionLoading,
  onConnect,
}: {
  title: string;
  emptyText: string;
  items: AgentSourceCatalogItem[];
  actionLoading: boolean;
  onConnect: (sourceKey: string) => void;
}) => (
  <div className="space-y-2">
    <div className="text-xs font-semibold text-slate-700">{title}</div>
    {items.length ? items.map((item) => (
      <DatahubCatalogItem key={item.key} item={item} actionLoading={actionLoading} onConnect={onConnect} />
    )) : (
      <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-3 py-3 text-xs text-slate-500">
        {emptyText}
      </div>
    )}
  </div>
);

const DatahubCatalogItem = ({
  item,
  actionLoading,
  onConnect,
}: {
  item: AgentSourceCatalogItem;
  actionLoading: boolean;
  onConnect: (sourceKey: string) => void;
}) => {
  const state = item.extraction_state || item.state;
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-sm font-medium text-slate-950">{item.title || humanizeMeta(item.key)}</div>
          <div className="mt-1 text-xs leading-5 text-slate-500">{item.description || 'Источник данных LocalOS'}</div>
        </div>
        <span className={cn(
          'shrink-0 rounded-full px-2 py-1 text-xs font-medium ring-1',
          item.connected ? 'bg-emerald-50 text-emerald-700 ring-emerald-200' : item.available_count ? 'bg-white text-slate-700 ring-slate-200' : 'bg-slate-100 text-slate-500 ring-slate-200',
        )}>
          {item.connected ? humanizeSourceState(state) : item.available_count ? `${item.available_count}` : humanizeSourceState(state)}
        </span>
      </div>
      {item.error ? (
        <div className="mt-2 rounded-md border border-amber-200 bg-amber-50 px-2 py-1 text-xs text-amber-800">
          {item.error}
        </div>
      ) : null}
      {item.preview?.length ? (
        <div className="mt-2 space-y-1">
          {item.preview.slice(0, 2).map((line, index) => (
            <div key={`${item.key}-${index}`} className="truncate rounded-md bg-white px-2 py-1 text-xs text-slate-600 ring-1 ring-slate-100">
              {line}
            </div>
          ))}
        </div>
      ) : null}
      <div className="mt-2 flex justify-end">
        <Button
          type="button"
          size="sm"
          variant={item.connected ? 'outline' : 'default'}
          onClick={() => onConnect(item.key)}
          disabled={actionLoading || Boolean(item.connected) || item.state === 'empty'}
        >
          {item.connected ? 'Уже подключено' : 'Подключить'}
        </Button>
      </div>
    </div>
  );
};

const AgentSourcesList = ({ sources, compact = false }: { sources: AgentSource[]; compact?: boolean }) => (
  <div className={cn('space-y-2', compact && 'space-y-1')}>
    {sources.length ? sources.map((source) => (
      <div key={source.id || source.name || source.file_name || source.internal_source} className={cn('rounded-lg bg-white px-3 py-2 text-xs leading-5 text-slate-600 ring-1 ring-slate-200', compact && 'bg-emerald-50 ring-emerald-100')}>
        <div className="font-medium text-slate-900">{source.name || source.file_name || source.internal_source || 'Источник'}</div>
        <div>
          {source.internal_source ? humanizeMeta(source.internal_source) : humanizeSourceType(source.source_type)}
          {' · '}
          {humanizeSourceState(source.extraction_state)}
          {' · '}
          {formatSourceSize(source.content_length, source.file_size_bytes)}
        </div>
        {source.extraction_error ? (
          <div className="mt-1 rounded-md border border-amber-200 bg-amber-50 px-2 py-1 text-amber-800">
            {source.extraction_error}
          </div>
        ) : null}
      </div>
    )) : (
      <div className="rounded-lg border border-dashed border-slate-200 bg-white px-3 py-3 text-sm text-slate-500">
        Добавьте текст, файл или источник LocalOS.
      </div>
    )}
  </div>
);

const AgentConnectionDecisionBanner = ({
  decision,
  actionLoading,
  onConfigure,
  onPreview,
}: {
  decision: AgentConnectionDecision;
  actionLoading: boolean;
  onConfigure: (bindingKey: string) => void;
  onPreview: () => void;
}) => {
  const ready = decision.tone === 'ready';
  const choice = decision.tone === 'choice';
  const blocked = decision.tone === 'needs_action';
  const canClick = decision.action === 'preview' || (decision.action === 'configure' && Boolean(decision.bindingKey));
  return (
    <div className={cn(
      'rounded-xl border px-3 py-3',
      ready ? 'border-emerald-200 bg-emerald-50' : '',
      choice ? 'border-sky-200 bg-sky-50' : '',
      blocked ? 'border-amber-200 bg-amber-50' : '',
      !ready && !choice && !blocked ? 'border-slate-200 bg-slate-50' : '',
    )}>
      <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
        <div>
          <div className={cn('text-sm font-semibold', ready ? 'text-emerald-950' : choice ? 'text-sky-950' : blocked ? 'text-amber-950' : 'text-slate-950')}>
            {decision.title}
          </div>
          <div className={cn('mt-1 text-xs leading-5', ready ? 'text-emerald-800' : choice ? 'text-sky-800' : blocked ? 'text-amber-900' : 'text-slate-600')}>
            {decision.description}
          </div>
        </div>
        {decision.cta ? (
          <Button
            type="button"
            size="sm"
            variant={ready ? 'default' : 'outline'}
            className={cn(!ready && 'bg-white')}
            disabled={actionLoading || !canClick}
            onClick={() => {
              if (decision.action === 'preview') {
                onPreview();
                return;
              }
              if (decision.bindingKey) {
                onConfigure(decision.bindingKey);
              }
            }}
          >
            {actionLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : ready ? <Play className="mr-2 h-4 w-4" /> : <Zap className="mr-2 h-4 w-4" />}
            {decision.cta}
          </Button>
        ) : null}
      </div>
    </div>
  );
};

const AgentIntegrationsPanel = ({
  integrations,
  availableIntegrations,
  providerCatalog,
  authOptions,
  bindingStatus,
  connectionPlan,
  selectedBindingKey,
  sheetSpreadsheetId,
  sheetName,
  sheetAuthRef,
  sheetDailyCap,
  telegramBotMode,
  telegramDailyCap,
  matonAuthRef,
  matonChannel,
  matonDailyCap,
  processRowValues,
  processPreviewMessage,
  actionLoading,
  onSheetSpreadsheetIdChange,
  onSheetNameChange,
  onSheetAuthRefChange,
  onSheetDailyCapChange,
  onTelegramBotModeChange,
  onTelegramDailyCapChange,
  onMatonAuthRefChange,
  onMatonChannelChange,
  onMatonDailyCapChange,
  onProcessRowValuesChange,
  onProcessPreviewMessageChange,
  onSaveSheetIntegration,
  onSaveTelegramIntegration,
  onSaveMatonIntegration,
  onChooseProviderRoute,
  onAttachExistingIntegration,
  onSelectBinding,
  onSaveCustomProcess,
  onRunCustomProcessPreview,
  onPreviewRun,
}: {
  integrations: AgentIntegration[];
  availableIntegrations: AgentIntegration[];
  providerCatalog: AgentIntegrationCatalogItem[];
  authOptions: AgentExternalAuthOption[];
  bindingStatus: AgentIntegrationBindingStatus[];
  connectionPlan: AgentConnectionPlan | null;
  selectedBindingKey: string;
  sheetSpreadsheetId: string;
  sheetName: string;
  sheetAuthRef: string;
  sheetDailyCap: string;
  telegramBotMode: string;
  telegramDailyCap: string;
  matonAuthRef: string;
  matonChannel: string;
  matonDailyCap: string;
  processRowValues: string;
  processPreviewMessage: string;
  actionLoading: boolean;
  onSheetSpreadsheetIdChange: (value: string) => void;
  onSheetNameChange: (value: string) => void;
  onSheetAuthRefChange: (value: string) => void;
  onSheetDailyCapChange: (value: string) => void;
  onTelegramBotModeChange: (value: string) => void;
  onTelegramDailyCapChange: (value: string) => void;
  onMatonAuthRefChange: (value: string) => void;
  onMatonChannelChange: (value: string) => void;
  onMatonDailyCapChange: (value: string) => void;
  onProcessRowValuesChange: (value: string) => void;
  onProcessPreviewMessageChange: (value: string) => void;
  onSaveSheetIntegration: () => void;
  onSaveTelegramIntegration: () => void;
  onSaveMatonIntegration: () => void;
  onChooseProviderRoute: (bindingKey: string, route: AgentProviderRoute) => void;
  onAttachExistingIntegration: (integration: AgentIntegration, bindingKey?: string) => void;
  onSelectBinding: (bindingKey: string) => void;
  onSaveCustomProcess: () => void;
  onRunCustomProcessPreview: () => void;
  onPreviewRun: () => void;
}) => {
  const sheetIntegration = integrations.find((item) => item.provider === 'google_sheets');
  const telegramIntegration = integrations.find((item) => item.provider === 'telegram');
  const matonIntegration = integrations.find((item) => item.provider === 'maton');
  const selectedPlanItem = (connectionPlan?.items || []).find((item) => item.key === selectedBindingKey);
  const needsTelegram = bindingStatus.some((binding) => binding.provider === 'telegram');
  const needsMaton = bindingStatus.some((binding) => binding.provider === 'maton') || (selectedPlanItem?.provider_routes || []).some((route) => route.provider === 'maton');
  const needsSheetsRead = bindingStatus.some((binding) => binding.provider === 'google_sheets' && binding.capability === 'google_sheets.read_rows');
  const needsSheetsAppend = bindingStatus.some((binding) => binding.provider === 'google_sheets' && binding.capability === 'sheets.append_row_request');
  const needsSheets = needsSheetsRead || needsSheetsAppend || bindingStatus.some((binding) => binding.provider === 'google_sheets');
  const isTelegramToSheetsProcess = needsTelegram && needsSheetsAppend;
  const sheetsTitle = needsSheetsRead && needsSheetsAppend ? 'Google Sheets read/write' : needsSheetsRead ? 'Google Sheets read' : 'Google Sheets append';
  const connectedBindings = bindingStatus.filter((binding) => binding.status === 'connected' || binding.status === 'ready').length;
  const missingBindings = bindingStatus.filter((binding) => binding.status !== 'connected' && binding.status !== 'ready').length;
  const canPreviewRun = !bindingStatus.length || missingBindings === 0;
  const connectionDecision = buildAgentConnectionDecision(connectionPlan, bindingStatus, canPreviewRun);
  const selectedBinding = bindingStatus.find((binding) => binding.key === selectedBindingKey);
  const selectedProvider = selectedBinding?.provider || '';
  return (
    <div className="space-y-3 rounded-2xl border border-slate-200 bg-white p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Каналы и действия</div>
          <div className="mt-1 text-xs leading-5 text-slate-500">Что может запускать агента и куда он может записывать результат после подтверждения.</div>
        </div>
        <span className="shrink-0 text-xs text-slate-400">{bindingStatus.length ? `${connectedBindings}/${bindingStatus.length}` : `${integrations.length}/${providerCatalog.length || 2}`}</span>
      </div>

      <AgentConnectionDecisionBanner
        decision={connectionDecision}
        actionLoading={actionLoading}
        onConfigure={onSelectBinding}
        onPreview={onPreviewRun}
      />

      {bindingStatus.length ? (
        <div className={cn('rounded-lg px-3 py-2 text-xs leading-5 ring-1', missingBindings ? 'bg-amber-50 text-amber-900 ring-amber-200' : 'bg-emerald-50 text-emerald-900 ring-emerald-200')}>
          {missingBindings ? `Нужно подключить ${missingBindings} ${missingBindings === 1 ? 'доступ' : 'доступа'}, прежде чем активировать агента.` : 'Все обязательные подключения готовы. Можно проверять запуск и активировать версию.'}
        </div>
      ) : null}

      <div className={cn('rounded-lg px-3 py-3 ring-1', canPreviewRun ? 'bg-emerald-50 text-emerald-950 ring-emerald-200' : 'bg-slate-50 text-slate-600 ring-slate-200')}>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="text-sm font-semibold">Preflight и preview run</div>
            <div className="mt-1 text-xs leading-5">
              {canPreviewRun
                ? 'Проверим права, лимиты, approvals и выполним тестовый запуск без автономной внешней отправки.'
                : 'Сначала заполните обязательные подключения. После этого станет доступна проверка на примере.'}
            </div>
          </div>
          <Button type="button" size="sm" onClick={onPreviewRun} disabled={actionLoading || !canPreviewRun}>
            {actionLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Play className="mr-2 h-4 w-4" />}
            Проверить на примере
          </Button>
        </div>
      </div>

      <div className="grid gap-2">
        {needsTelegram || !bindingStatus.length ? <AgentIntegrationStatusItem integration={telegramIntegration} provider="telegram" fallbackTitle="Telegram trigger" /> : null}
        {needsMaton ? <AgentIntegrationStatusItem integration={matonIntegration} provider="maton" fallbackTitle="Maton.ai bridge" /> : null}
        {needsSheets || !bindingStatus.length ? <AgentIntegrationStatusItem integration={sheetIntegration} provider="google_sheets" fallbackTitle={sheetsTitle} /> : null}
      </div>

      {bindingStatus.length ? (
        <div className="space-y-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-3">
          <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Что нужно подключить</div>
          {bindingStatus.map((binding) => {
            const resourceFacts = connectionResourceFacts(binding.provider, binding.answer_config || null);
            return (
              <div
                key={binding.key || binding.provider}
                className={cn(
                  'rounded-lg bg-white px-3 py-2 text-xs ring-1',
                  selectedBindingKey && binding.key === selectedBindingKey ? 'ring-sky-300' : 'ring-slate-200',
                )}
              >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="font-medium text-slate-900">{connectorLabel(binding.provider)}</div>
                  <div className="mt-1 text-slate-500">
                    {humanizeMeta(binding.key || binding.trigger || binding.capability || binding.direction || binding.provider)}
                  </div>
                </div>
                <StatusBadge status={binding.status} />
              </div>
              <div className="mt-1 text-slate-600">{bindingActionHint(binding)}</div>
              {resourceFacts.length ? (
                <div className="mt-2 rounded-lg bg-emerald-50 px-2 py-1.5 text-emerald-800 ring-1 ring-emerald-100">
                  Ресурс из диалога: {resourceFacts.join(' · ')}
                </div>
              ) : null}
              {binding.missing_config?.length ? (
                <div className="mt-1 text-amber-700">Нужно заполнить: {binding.missing_config.join(', ')}</div>
              ) : null}
              {binding.approval_required ? (
                <div className="mt-1 text-slate-500">Перед внешним действием агент остановится на подтверждение.</div>
              ) : null}
              {binding.status !== 'connected' && binding.status !== 'ready' ? (
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  className="mt-2"
                  onClick={() => onSelectBinding(binding.key || '')}
                  disabled={!binding.key}
                >
                  Настроить этот доступ
                </Button>
              ) : null}
              </div>
            );
          })}
        </div>
      ) : null}

      {selectedBinding ? (
        <div className="rounded-lg border border-sky-200 bg-sky-50 px-3 py-2 text-xs leading-5 text-sky-950">
          <div className="font-semibold">Сейчас настраивается: {connectorLabel(selectedBinding.provider)}</div>
          <div className="mt-1">
            {humanizeMeta(selectedBinding.key || selectedBinding.capability || selectedBinding.provider)}
            {selectedBinding.missing_config?.length ? ` · заполните: ${selectedBinding.missing_config.join(', ')}` : ''}
          </div>
          {selectedPlanItem?.route_summary ? (
            <div className="mt-2 rounded-lg bg-white/80 px-2 py-1.5 text-sky-900 ring-1 ring-sky-100">
              {selectedPlanItem.route_summary}
            </div>
          ) : null}
          {selectedPlanItem?.provider_routes?.length ? (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {selectedPlanItem.provider_routes.slice(0, 5).map((route) => (
                <ProviderActionPill
                  key={`${selectedPlanItem.key}-${route.provider}-${route.role}`}
                  route={route}
                  disabled={actionLoading || !selectedPlanItem.key}
                  onChoose={() => onChooseProviderRoute(selectedPlanItem.key || '', route)}
                />
              ))}
            </div>
          ) : null}
          {selectedPlanItem?.provider_routes?.length ? (
            <div className="mt-2 rounded-lg bg-white/80 px-2 py-1.5 text-sky-900 ring-1 ring-sky-100">
              {providerActionDescription(selectedPlanItem.provider_routes.find((route) => route.state === 'available') || selectedPlanItem.provider_routes[0]) || 'Выберите доступный provider route для этого binding.'}
            </div>
          ) : null}
        </div>
      ) : null}

      {isTelegramToSheetsProcess ? (
      <div className="space-y-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-3">
        <div className="flex items-center gap-2 text-sm font-medium text-slate-950">
          <Workflow className="h-4 w-4" />
          Логика канала Telegram → Google Sheets
        </div>
        <textarea
          className="min-h-20 w-full resize-none rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400"
          value={processRowValues}
          onChange={(event) => onProcessRowValuesChange(event.target.value)}
          placeholder="{{received_at}}, {{telegram_username}}, {{message_text}}"
        />
        <div className="text-xs leading-5 text-slate-500">
          Значения идут в строку таблицы по порядку. Сохранение создаёт новую активную версию агента.
        </div>
        <textarea
          className="min-h-20 w-full resize-none rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400"
          value={processPreviewMessage}
          onChange={(event) => onProcessPreviewMessageChange(event.target.value)}
          placeholder="Новая заявка: Анна, телефон +7..."
        />
        <div className="flex flex-wrap gap-2">
          <Button type="button" size="sm" onClick={onSaveCustomProcess} disabled={actionLoading}>
            Сохранить логику канала
          </Button>
          <Button type="button" size="sm" variant="outline" onClick={onRunCustomProcessPreview} disabled={actionLoading}>
            Проверить на примере
          </Button>
        </div>
      </div>
      ) : null}

      {needsTelegram || !bindingStatus.length ? (
      <div className={cn('space-y-2 rounded-lg border px-3 py-3', selectedProvider === 'telegram' ? 'border-sky-200 bg-sky-50' : 'border-slate-200 bg-slate-50')}>
        <div className="flex items-center gap-2 text-sm font-medium text-slate-950">
          <MessageSquareText className="h-4 w-4" />
          Telegram
        </div>
        <select
          className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400"
          value={telegramBotMode}
          onChange={(event) => onTelegramBotModeChange(event.target.value)}
        >
          <option value="business_bot">Бот бизнеса</option>
          <option value="global_control_bot">Глобальный control bot</option>
        </select>
        <input
          className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400"
          value={telegramDailyCap}
          onChange={(event) => onTelegramDailyCapChange(event.target.value)}
          placeholder="Лимит сообщений в день"
          inputMode="numeric"
        />
        <Button type="button" size="sm" variant="outline" onClick={onSaveTelegramIntegration} disabled={actionLoading}>
          {selectedProvider === 'telegram' ? 'Сохранить Telegram для выбранного шага' : 'Подключить Telegram'}
        </Button>
      </div>
      ) : null}

      {needsMaton ? (
      <div className={cn('space-y-2 rounded-lg border px-3 py-3', selectedProvider === 'maton' ? 'border-sky-200 bg-sky-50' : 'border-slate-200 bg-slate-50')}>
        <div className="flex items-center gap-2 text-sm font-medium text-slate-950">
          <Workflow className="h-4 w-4" />
          Maton.ai bridge
        </div>
        <div className="rounded-lg bg-white px-3 py-2 text-xs leading-5 text-slate-600 ring-1 ring-slate-200">
          Используем сохранённый Maton.ai API key как delivery/provider bridge за LocalOS approval и audit boundary.
        </div>
        <select
          className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400"
          value={matonAuthRef}
          onChange={(event) => onMatonAuthRefChange(event.target.value)}
        >
          <option value="">Maton key не выбран</option>
          {authOptions.filter((option) => option.source === 'maton').map((option) => (
            <option key={option.id} value={option.id}>
              {option.display_name || 'Maton.ai'} · {option.id.slice(0, 8)}
            </option>
          ))}
        </select>
        <div className="grid gap-2 sm:grid-cols-2">
          <input
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400"
            value={matonChannel}
            onChange={(event) => onMatonChannelChange(event.target.value)}
            placeholder="maton_bridge"
          />
          <input
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400"
            value={matonDailyCap}
            onChange={(event) => onMatonDailyCapChange(event.target.value)}
            placeholder="Лимит действий в день"
            inputMode="numeric"
          />
        </div>
        <Button type="button" size="sm" onClick={onSaveMatonIntegration} disabled={actionLoading || !matonAuthRef.trim()}>
          {selectedProvider === 'maton' ? 'Сохранить Maton для выбранного шага' : 'Подключить Maton.ai'}
        </Button>
      </div>
      ) : null}

      {needsSheets || !bindingStatus.length ? (
      <div className={cn('space-y-2 rounded-lg border px-3 py-3', selectedProvider === 'google_sheets' ? 'border-sky-200 bg-sky-50' : 'border-slate-200 bg-slate-50')}>
        <div className="flex items-center gap-2 text-sm font-medium text-slate-950">
          <Database className="h-4 w-4" />
          {needsSheetsRead && needsSheetsAppend ? 'Google Sheets: чтение и запись' : needsSheetsRead ? 'Google Sheets: чтение строк' : 'Google Sheets: запись строк'}
        </div>
        <input
          className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400"
          value={sheetSpreadsheetId}
          onChange={(event) => onSheetSpreadsheetIdChange(event.target.value)}
          placeholder="Spreadsheet ID"
        />
        <div className="grid gap-2 sm:grid-cols-2">
          <input
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400"
            value={sheetName}
            onChange={(event) => onSheetNameChange(event.target.value)}
            placeholder="Sheet1"
          />
          <input
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400"
            value={sheetDailyCap}
            onChange={(event) => onSheetDailyCapChange(event.target.value)}
            placeholder="Лимит append в день"
            inputMode="numeric"
          />
        </div>
        <select
          className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400"
          value={sheetAuthRef}
          onChange={(event) => onSheetAuthRefChange(event.target.value)}
        >
          <option value="">Google-доступ не выбран</option>
          {authOptions.map((option) => (
            <option key={option.id} value={option.id}>
              {option.display_name || humanizeMeta(option.source)} · {option.id.slice(0, 8)}
            </option>
          ))}
        </select>
        <Button type="button" size="sm" onClick={onSaveSheetIntegration} disabled={actionLoading || !sheetSpreadsheetId.trim()}>
          {selectedProvider === 'google_sheets' ? 'Сохранить таблицу для выбранного шага' : 'Сохранить таблицу'}
        </Button>
      </div>
      ) : null}

      {availableIntegrations.length ? (
        <div className="space-y-1">
          <div className="text-xs font-semibold text-slate-700">Уже подключены в бизнесе</div>
          {availableIntegrations.slice(0, 3).map((integration) => (
            <div key={integration.id} className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto]">
              <AgentIntegrationStatusItem integration={integration} provider={integration.provider} fallbackTitle={integration.display_name || integration.provider_label || integration.provider} />
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={() => onAttachExistingIntegration(integration, selectedProvider === integration.provider ? selectedBindingKey : '')}
                disabled={actionLoading}
              >
                {selectedProvider === integration.provider ? 'Использовать для шага' : 'Использовать'}
              </Button>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
};

const AgentIntegrationStatusItem = ({
  integration,
  provider,
  fallbackTitle,
}: {
  integration?: AgentIntegration;
  provider: string;
  fallbackTitle: string;
}) => {
  const boundary = integration?.execution_boundary || {};
  const operation = String(integration?.config?.operation || '');
  const googleSheetsMode = operation === 'read_rows' ? 'Чтение строк' : operation === 'read_write' ? 'Чтение и запись после подтверждения' : 'Запись после подтверждения';
  const boundaryItems = [
    ...(boundary.triggers || []),
    ...(boundary.capabilities || []),
  ];
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-3 py-2">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="truncate text-sm font-medium text-slate-950">{integration?.display_name || integration?.provider_label || fallbackTitle}</div>
          <div className="mt-1 text-xs text-slate-500">{provider === 'google_sheets' ? googleSheetsMode : 'Когда запускать и куда отвечать'}</div>
        </div>
        <StatusBadge status={integration?.status || 'draft'} />
      </div>
      <div className="mt-2 text-xs leading-5 text-slate-600">
        {boundaryItems.length ? boundaryItems.slice(0, 3).map((item) => humanizeMeta(item)).join(', ') : 'Действие пока не подключено'}
      </div>
      {integration?.has_auth_ref ? (
        <div className="mt-1 text-xs text-emerald-700">Доступ подключён</div>
      ) : provider === 'google_sheets' ? (
        <div className="mt-1 text-xs text-amber-700">Нужен доступ к Google Sheets перед записью</div>
      ) : null}
    </div>
  );
};

const VersionSummary = ({
  versions,
  latestVersionNumber,
  activeVersionId,
  onStartVersionRun,
  onActivateVersion,
  onRollbackVersion,
}: {
  versions: Array<Record<string, unknown>>;
  latestVersionNumber: number | null;
  activeVersionId: string;
  onStartVersionRun: (versionId: string) => void;
  onActivateVersion: (versionId: string) => void;
  onRollbackVersion: (versionId: string) => void;
}) => {
  const newestVersions = versions.slice(0, 5);
  return (
    <div className="rounded-xl border border-slate-200 bg-white px-3 py-3 text-sm leading-6 text-slate-700">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="font-semibold text-slate-950">Версия агента</div>
        <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700 ring-1 ring-emerald-200">
          {latestVersionNumber ? `Активна v${latestVersionNumber}` : 'Нет активной версии'}
        </span>
      </div>
      <div className="mt-1 text-xs text-slate-500">
        Новые запуски используют активную версию. Старые результаты остаются привязаны к версии, на которой были созданы.
      </div>
      {newestVersions.length ? (
        <div className="mt-3 space-y-2">
          {newestVersions.map((version) => {
            const versionNumber = getVersionNumber(version);
            const versionId = typeof version.id === 'string' ? version.id : '';
            const isActive = Boolean(version.is_active) || Boolean(versionId && versionId === activeVersionId);
            const summaryValue = version.diff_from_previous && typeof version.diff_from_previous === 'object' && 'summary' in version.diff_from_previous
              ? version.diff_from_previous.summary
              : '';
            const summary = typeof summaryValue === 'string' ? summaryValue : '';
            const diffValue = version.diff_from_previous && typeof version.diff_from_previous === 'object' ? version.diff_from_previous : {};
            const changedFieldsValue = 'changed_fields' in diffValue ? diffValue.changed_fields : [];
            const changedFields = Array.isArray(changedFieldsValue) ? changedFieldsValue.map((item) => humanizeMeta(String(item))) : [];
            const createdAt = typeof version.created_at === 'string' ? version.created_at : '';
            return (
              <div key={String(version.id || versionNumber || 'version')} className={cn('rounded-lg px-2 py-2 text-xs text-slate-600 ring-1', isActive ? 'bg-emerald-50 ring-emerald-200' : 'bg-slate-50 ring-slate-200')}>
                <div className="flex items-center justify-between gap-3">
                  <span className="font-medium text-slate-900">{versionNumber ? `v${versionNumber}` : 'версия'}</span>
                  <span>{isActive ? 'активна сейчас' : 'кандидат / архив'}</span>
                </div>
                {summary ? <div className="mt-1 text-slate-500">{summary}</div> : null}
                {changedFields.length ? (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {changedFields.slice(0, 4).map((field) => (
                      <span key={`${versionId}-${field}`} className="rounded-full bg-white px-2 py-0.5 text-[11px] text-slate-600 ring-1 ring-slate-200">
                        {field}
                      </span>
                    ))}
                  </div>
                ) : null}
                {createdAt ? <div className="mt-1 text-[11px] text-slate-400">Создана: {createdAt}</div> : null}
                <div className="mt-2 flex flex-wrap gap-2">
                  <Button type="button" size="sm" variant="outline" onClick={() => onStartVersionRun(versionId)} disabled={!versionId}>
                    Проверить на примере
                  </Button>
                  {!isActive ? (
                    <Button type="button" size="sm" onClick={() => onActivateVersion(versionId)} disabled={!versionId}>
                      Активировать
                    </Button>
                  ) : null}
                  {!isActive && versionNumber && latestVersionNumber && versionNumber < latestVersionNumber ? (
                    <Button type="button" size="sm" variant="outline" onClick={() => onRollbackVersion(versionId)} disabled={!versionId}>
                      Откатиться сюда
                    </Button>
                  ) : null}
                </div>
              </div>
            );
          })}
        </div>
      ) : null}
    </div>
  );
};

const LearningHistoryPanel = ({
  learningEvents,
  versionEvents,
  legacyMigration,
}: {
  learningEvents: AgentLearningEvent[];
  versionEvents: AgentVersionEvent[];
  legacyMigration: Record<string, unknown>;
}) => {
  const legacySource = typeof legacyMigration.source === 'string' ? legacyMigration.source : '';
  const latestLearning = learningEvents.slice(-5).reverse();
  const latestVersionEvents = versionEvents.slice(-5).reverse();
  return (
    <div className="rounded-xl border border-slate-200 bg-white px-3 py-3 text-sm leading-6 text-slate-700">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="font-semibold text-slate-950">Обучение и версии</div>
        <span className="rounded-full bg-slate-50 px-2.5 py-1 text-xs font-medium text-slate-600 ring-1 ring-slate-200">
          {learningEvents.length} событий
        </span>
      </div>
      {legacySource ? (
        <div className="mt-2 rounded-lg border border-amber-200 bg-amber-50 px-2 py-2 text-xs text-amber-900">
          Мигрировано из {legacySource}. Старая логика больше не является активной логикой агента.
        </div>
      ) : null}
      <div className="mt-3 grid gap-3 md:grid-cols-2">
        <div className="space-y-2">
          <div className="text-xs font-semibold uppercase text-slate-500">История обучения</div>
          {latestLearning.length ? latestLearning.map((event) => (
            <div key={`${event.run_id || 'run'}-${event.candidate_version_id || event.created_at}`} className="rounded-lg bg-slate-50 px-3 py-2 text-xs">
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium text-slate-900">{humanizeLearningTrigger(event.trigger_type)}</span>
                <span className="text-slate-500">{event.candidate_version_number ? `v${event.candidate_version_number}` : humanizeVersionState(event.activation_state)}</span>
              </div>
              <div className="mt-1 line-clamp-2 text-slate-600">{event.feedback || 'обратная связь сохранена'}</div>
              <div className="mt-1 text-[11px] text-slate-400">{event.created_at || ''}</div>
            </div>
          )) : (
            <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-3 py-3 text-xs text-slate-500">
              История обучения появится после правки, отклонения, плохого результата или ошибки.
            </div>
          )}
        </div>
        <div className="space-y-2">
          <div className="text-xs font-semibold uppercase text-slate-500">История версий</div>
          {latestVersionEvents.length ? latestVersionEvents.map((event) => (
            <div key={`${event.action || 'event'}-${event.created_at || event.active_version_id}`} className="rounded-lg bg-slate-50 px-3 py-2 text-xs">
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium text-slate-900">{humanizeVersionAction(event.action)}</span>
                <span className="text-slate-500">{event.active_version_number ? `v${event.active_version_number}` : ''}</span>
              </div>
              <div className="mt-1 line-clamp-2 text-slate-600">{event.reason || 'событие версии'}</div>
              <div className="mt-1 text-[11px] text-slate-400">{event.created_at || ''}</div>
            </div>
          )) : (
            <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-3 py-3 text-xs text-slate-500">
              История активации и отката появится после смены активной версии.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

const humanizeLearningTrigger = (trigger?: string) => ({
  manual_edit: 'Ручная правка',
  approval_rejected: 'Отклонение',
  bad_outcome: 'Плохой результат',
  runtime_error: 'Ошибка',
  manual_feedback: 'Комментарий',
  run_review: 'Проверка запуска',
}[trigger || ''] || trigger || 'Событие обучения');

const humanizeVersionAction = (action?: string) => ({
  created: 'Создана версия',
  setup_updated: 'Обновлена логика',
  activated: 'Активирована',
  rollback: 'Откат',
  feedback_applied: 'Обратная связь применена',
  legacy_migration_created: 'Создано миграцией',
}[action || ''] || action || 'Событие версии');

const humanizeVersionState = (state?: string) => ({
  candidate: 'кандидатная версия',
  active: 'активная',
  rolled_back: 'откачена',
  archived: 'в архиве',
}[state || ''] || state || 'кандидатная версия');

const AgentRunReviewPanel = ({
  review,
  latestVersionNumber,
  feedbackText,
  feedbackTrigger,
  feedbackVersionNotice,
  actionLoading,
  onFeedbackTextChange,
  onFeedbackTriggerChange,
  onSubmitFeedback,
  onActivateFeedbackVersion,
  onRollbackFeedbackVersion,
}: {
  review: AgentReview | null;
  latestVersionNumber: number | null;
  feedbackText: string;
  feedbackTrigger: string;
  feedbackVersionNotice: FeedbackVersionNotice | null;
  actionLoading: boolean;
  onFeedbackTextChange: (value: string) => void;
  onFeedbackTriggerChange: (value: string) => void;
  onSubmitFeedback: () => void;
  onActivateFeedbackVersion: (versionId: string) => void;
  onRollbackFeedbackVersion: (versionId: string) => void;
}) => {
  const journal = review?.journal && review.journal.length ? review.journal : buildJournalFromSections(review?.sections || []);
  const noticeVersionId = feedbackVersionNotice?.version_id || '';
  const previousVersionId = feedbackVersionNotice?.previous_version_id || '';
  const noticeState = feedbackVersionNotice?.activation_state || 'candidate';
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-slate-950">Журнал запуска</div>
          <div className="mt-1 text-xs text-slate-500">
            Входные данные, что агент извлёк, какие правила применил, результат и ручной контроль.
            {latestVersionNumber ? ` Следующий запуск пойдёт на v${latestVersionNumber}.` : ''}
          </div>
        </div>
        {review?.run_status ? <StatusBadge status={review.run_status} /> : null}
      </div>
      <div className="mb-4 grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(16rem,0.7fr)]">
        <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-3">
          <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Как настроен агент</div>
          <div className="mt-2 space-y-1 text-sm leading-6 text-slate-700">
            <div><span className="font-medium text-slate-950">Задача:</span> {String(review?.setup?.workflow_description || 'не задана')}</div>
            <div><span className="font-medium text-slate-950">Извлечь:</span> {String(review?.setup?.extraction_rules || 'не задано')}</div>
            <div><span className="font-medium text-slate-950">Правила:</span> {String(review?.setup?.processing_rules || 'не заданы')}</div>
            <div><span className="font-medium text-slate-950">Результат:</span> {String(review?.setup?.output_format || 'не задан')}</div>
          </div>
        </div>
        <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-3">
          <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Источники</div>
          {review?.used_sources?.length ? (
            <div className="mb-3">
              <div className="mb-2 text-xs font-medium text-slate-700">Использовано в последнем запуске</div>
              <AgentSourcesList sources={review.used_sources} compact />
            </div>
          ) : null}
          <div className="mb-2 text-xs font-medium text-slate-700">Подключено к агенту</div>
          <AgentSourcesList sources={review?.sources || []} />
        </div>
      </div>
      {journal.length ? (
        <div className="space-y-3">
          {journal.map((entry, index) => <JournalEntryCard key={`${entry.kind || 'entry'}-${entry.title || index}`} entry={entry} />)}
        </div>
      ) : (
        <DashboardEmptyState title="Журнал появится после запуска" description="Запустите агента, чтобы увидеть входные данные, выводы, правила и результат." />
      )}
      <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 px-3 py-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="text-sm font-semibold text-slate-950">Улучшение версии</div>
            <div className="mt-1 text-xs leading-5 text-slate-500">
              Правка, отклонение, плохой результат или ошибка сохраняются как обратная связь и создают новую версию со списком изменений. Активирует её человек.
            </div>
          </div>
          <span className="rounded-full bg-white px-2.5 py-1 text-xs font-medium text-slate-700 ring-1 ring-slate-200">
            версионное улучшение
          </span>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          {learningTriggerOptions.map((option) => (
            <Button
              key={option.value}
              type="button"
              size="sm"
              variant={feedbackTrigger === option.value ? 'default' : 'outline'}
              onClick={() => onFeedbackTriggerChange(option.value)}
            >
              {option.label}
            </Button>
          ))}
        </div>
        <div className="mt-3 grid gap-2 md:grid-cols-[1fr_auto]">
          <textarea
            className="min-h-20 resize-none rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400"
            value={feedbackText}
            onChange={(event) => onFeedbackTextChange(event.target.value)}
            placeholder="Что исправить в логике агента для следующей версии?"
          />
          <Button type="button" onClick={onSubmitFeedback} disabled={actionLoading || !feedbackText.trim()}>
            Зафиксировать улучшение
          </Button>
        </div>
      </div>
      {feedbackVersionNotice ? (
        <div className={cn('mt-3 rounded-xl border px-3 py-3 text-sm leading-6', noticeState === 'active' ? 'border-emerald-200 bg-emerald-50 text-emerald-900' : 'border-amber-200 bg-amber-50 text-amber-950')}>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="font-semibold">
                Candidate-версия {feedbackVersionNotice.version_number ? `v${feedbackVersionNotice.version_number}` : 'агента'} готова
              </div>
              <div className="mt-1 text-xs">
                {feedbackVersionNotice.trigger_label || 'Обратная связь'} · {noticeState === 'active' ? 'активирована' : noticeState === 'rolled_back' ? 'откат выполнен' : 'ждёт решения'}
              </div>
            </div>
            <StatusBadge status={noticeState === 'active' ? 'active' : noticeState === 'rolled_back' ? 'paused' : 'needs_approval'} />
          </div>
          <div className="mt-1">Правка: {feedbackVersionNotice.feedback}</div>
          {feedbackVersionNotice.diff?.summary ? (
            <div className="mt-1">Diff: {feedbackVersionNotice.diff.summary}</div>
          ) : null}
          {feedbackVersionNotice.diff?.changed_fields?.length ? (
            <div className="mt-2 flex flex-wrap gap-1">
              {feedbackVersionNotice.diff.changed_fields.slice(0, 5).map((field) => (
                <span key={`${noticeVersionId}-${field}`} className="rounded-full bg-white px-2 py-0.5 text-[11px] text-slate-700 ring-1 ring-slate-200">
                  {humanizeMeta(field)}
                </span>
              ))}
            </div>
          ) : null}
          <div className="mt-1 text-xs">{feedbackVersionNotice.next_run_note}</div>
          {noticeVersionId && noticeState === 'candidate' ? (
            <div className="mt-3 flex flex-wrap gap-2">
              <Button type="button" size="sm" onClick={() => onActivateFeedbackVersion(noticeVersionId)} disabled={actionLoading}>
                Активировать версию
              </Button>
            </div>
          ) : null}
          {noticeState === 'active' && previousVersionId ? (
            <div className="mt-3 flex flex-wrap gap-2">
              <Button type="button" size="sm" variant="outline" onClick={() => onRollbackFeedbackVersion(previousVersionId)} disabled={actionLoading}>
                Откатиться к прошлой версии
              </Button>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
};

const buildJournalFromSections = (sections: AgentReviewSection[]) => sections.map((section) => ({
  kind: humanizeMeta(section.artifact_type || 'artifact'),
  title: section.title || 'Результат',
  status: section.status || 'completed',
  summary: section.summary || '',
  details: [],
  payload: section.payload || {},
}));

const GenericRunProgress = ({
  category,
  review,
  activeRun,
  pendingApproval,
}: {
  category: string;
  review: AgentReview | null;
  activeRun: AgentRun | null;
  pendingApproval: AgentApproval | null;
}) => {
  const journal = review?.journal && review.journal.length ? review.journal : buildJournalFromSections(review?.sections || []);
  const stepStatuses = buildStepStatusMap(activeRun?.steps || []);
  const hasRunData = Boolean(activeRun || journal.length || review?.has_run);

  if (!hasRunData) {
    return null;
  }

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-slate-950">Путь {humanizeCategory(category).toLowerCase()}-агента</div>
          <div className="mt-1 text-sm leading-6 text-slate-600">
            Агент проходит понятный цикл: данные, понимание, результат и ручной контроль. Технические детали спрятаны ниже.
          </div>
        </div>
        {activeRun?.status || review?.run_status ? <StatusBadge status={activeRun?.status || review?.run_status || ''} /> : null}
      </div>
      <div className="mt-4 grid gap-3 lg:grid-cols-4">
        {genericRunStages.map((stage) => {
          const entry = findJournalEntryForGenericStage(journal, stage.kind);
          const stageStatus = getGenericStageStatus(stage.kind, entry, stepStatuses, pendingApproval);
          const detail = getGenericStageDetail(stage.kind, entry, category, pendingApproval);
          const Icon = stage.icon;
          return (
            <div
              key={stage.kind}
              className={cn(
                'rounded-xl border px-3 py-3',
                stageStatus === 'completed' || stageStatus === 'approved' || stageStatus === 'generated'
                  ? 'border-emerald-200 bg-emerald-50/60'
                  : stageStatus === 'waiting_approval' || stageStatus === 'pending'
                    ? 'border-amber-200 bg-amber-50/60'
                    : 'border-slate-200 bg-slate-50',
              )}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex min-w-0 items-center gap-2">
                  <span className={cn(
                    'flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white ring-1',
                    stageStatus === 'completed' || stageStatus === 'approved' || stageStatus === 'generated'
                      ? 'text-emerald-700 ring-emerald-200'
                      : stageStatus === 'waiting_approval' || stageStatus === 'pending'
                        ? 'text-amber-700 ring-amber-200'
                        : 'text-slate-500 ring-slate-200',
                  )}>
                    <Icon className="h-4 w-4" />
                  </span>
                  <div className="min-w-0">
                    <div className="text-sm font-semibold text-slate-950">{stage.title}</div>
                    <div className="mt-0.5 text-xs text-slate-500">{stage.description}</div>
                  </div>
                </div>
                {stageStatus ? <StatusBadge status={stageStatus} /> : null}
              </div>
              {detail ? <div className="mt-3 text-sm leading-6 text-slate-700">{detail}</div> : null}
            </div>
          );
        })}
      </div>
    </div>
  );
};

const buildStepStatusMap = (steps: AgentRunStep[]) => {
  const statuses: Record<string, string> = {};
  steps.forEach((step) => {
    if (step.step_key && step.status) {
      statuses[step.step_key] = step.status;
    }
  });
  return statuses;
};

const findJournalEntryForGenericStage = (journal: AgentJournalEntry[], kind: string) => {
  if (kind === 'approval') {
    return journal.find((entry) => entry.kind === 'approval');
  }
  return journal.find((entry) => entry.kind === kind);
};

const getGenericStageStatus = (
  kind: string,
  entry: AgentJournalEntry | undefined,
  stepStatuses: Record<string, string>,
  pendingApproval: AgentApproval | null,
) => {
  if (kind === 'approval' && pendingApproval) {
    return 'waiting_approval';
  }
  if (entry?.status) {
    return entry.status;
  }
  if (kind === 'input') {
    return stepStatuses.collect_inputs || '';
  }
  if (kind === 'extraction') {
    return stepStatuses.extract_context || '';
  }
  if (kind === 'output') {
    return stepStatuses.prepare_output || '';
  }
  if (kind === 'approval') {
    return stepStatuses.approve_output || '';
  }
  return '';
};

const getGenericStageDetail = (
  kind: string,
  entry: AgentJournalEntry | undefined,
  category: string,
  pendingApproval: AgentApproval | null,
) => {
  if (kind === 'input') {
    return findJournalDetailValue(entry, 'Подключено источников') || findJournalDetailValue(entry, 'Источники') || 'Данные агента подключены к запуску.';
  }
  if (kind === 'extraction') {
    return findJournalDetailValue(entry, 'Извлечено элементов') || findJournalDetailValue(entry, 'Что обработано') || entry?.summary || 'Агент разобрал источники.';
  }
  if (kind === 'output') {
    return getOutputStageDetail(entry, category);
  }
  if (kind === 'approval') {
    if (pendingApproval) {
      return explainApproval(pendingApproval);
    }
    return findJournalDetailValue(entry, 'Статус') || entry?.summary || 'Решения сохранены в журнале.';
  }
  return '';
};

const getOutputStageDetail = (entry: AgentJournalEntry | undefined, category: string) => {
  if (!entry) {
    return 'Результат появится после запуска.';
  }
  if (category === 'documents') {
    return compactJoin([
      labelCount('Фактов', findJournalDetailValue(entry, 'Фактов')),
      labelCount('Рисков', findJournalDetailValue(entry, 'Рисков')),
      findJournalDetailValue(entry, 'Внешняя отправка'),
    ]);
  }
  if (category === 'email') {
    return compactJoin([
      findJournalDetailValue(entry, 'Тема письма'),
      labelCount('Пунктов чеклиста', findJournalDetailValue(entry, 'Чеклист')),
      findJournalDetailValue(entry, 'Внешняя отправка'),
    ]);
  }
  if (category === 'tables') {
    return compactJoin([
      labelCount('Исключений', findJournalDetailValue(entry, 'Исключений')),
      labelCount('Строк к проверке', findJournalDetailValue(entry, 'Строк к проверке')),
      findJournalDetailValue(entry, 'Внешняя отправка'),
    ]);
  }
  if (category === 'reviews') {
    return compactJoin([
      labelCount('Черновиков ответов', findJournalDetailValue(entry, 'Черновиков ответов')),
      labelCount('Причин ручной проверки', findJournalDetailValue(entry, 'Причин ручной проверки')),
      findJournalDetailValue(entry, 'Публикация'),
    ]);
  }
  return entry.summary || 'Агент подготовил результат.';
};

const labelCount = (label: string, value: string) => (value ? `${label}: ${value}` : '');
const compactJoin = (items: string[]) => items.filter((item) => item.trim()).join(' · ');

const OutreachRunProgress = ({ review, activeRun }: { review: AgentReview | null; activeRun: AgentRun | null }) => {
  const journal = review?.journal && review.journal.length ? review.journal : [];
  const completedStepKeys = new Set((activeRun?.steps || []).filter((step) => step.status === 'completed').map((step) => step.step_key));
  const hasAnyStage = outreachProgressStages.some((stage) => journal.some((entry) => entry.kind === stage.kind));

  if (!activeRun && !hasAnyStage) {
    return null;
  }

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-slate-950">Путь outreach-агента</div>
          <div className="mt-1 text-sm leading-6 text-slate-600">
            Агент проходит этапы по порядку: лиды, shortlist, черновики и безопасная очередь.
          </div>
        </div>
        {activeRun?.status ? <StatusBadge status={activeRun.status} /> : null}
      </div>
      <div className="mt-4 grid gap-3 lg:grid-cols-4">
        {outreachProgressStages.map((stage) => {
          const entry = journal.find((item) => item.kind === stage.kind);
          const detailValue = findJournalDetailValue(entry, stage.detailLabel);
          const boundary = stage.kind === 'queue' ? findJournalDetailValue(entry, 'Внешняя отправка') : '';
          const isDone = Boolean(entry) || (
            stage.kind === 'sourcing' && completedStepKeys.has('source_leads')
          ) || (
            stage.kind === 'shortlist' && completedStepKeys.has('shortlist')
          ) || (
            stage.kind === 'drafts' && completedStepKeys.has('draft_messages')
          ) || (
            stage.kind === 'queue' && completedStepKeys.has('send_limited_batch')
          );
          const Icon = stage.icon;
          return (
            <div
              key={stage.kind}
              className={cn(
                'rounded-xl border px-3 py-3',
                isDone ? 'border-emerald-200 bg-emerald-50/60' : 'border-slate-200 bg-slate-50',
              )}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex min-w-0 items-center gap-2">
                  <span className={cn(
                    'flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ring-1',
                    isDone ? 'bg-white text-emerald-700 ring-emerald-200' : 'bg-white text-slate-500 ring-slate-200',
                  )}>
                    <Icon className="h-4 w-4" />
                  </span>
                  <div className="min-w-0">
                    <div className="text-sm font-semibold text-slate-950">{stage.title}</div>
                    <div className="mt-0.5 text-xs text-slate-500">{isDone ? 'готово' : 'ещё не выполнено'}</div>
                  </div>
                </div>
                {entry?.status ? <StatusBadge status={entry.status} /> : null}
              </div>
              <div className="mt-3 text-sm font-semibold text-slate-950">{detailValue || '0'}</div>
              {entry?.summary ? <div className="mt-1 line-clamp-2 text-xs leading-5 text-slate-600">{entry.summary}</div> : null}
              {boundary ? <div className="mt-2 rounded-lg bg-white px-2 py-1.5 text-xs font-medium text-amber-700 ring-1 ring-amber-200">{boundary}</div> : null}
            </div>
          );
        })}
      </div>
    </div>
  );
};

const findJournalDetailValue = (entry: AgentJournalEntry | undefined, label: string) => {
  if (!entry || !Array.isArray(entry.details)) {
    return '';
  }
  const detail = entry.details.find((item) => item.label === label);
  return detail?.value || '';
};

const JournalEntryCard = ({ entry }: { entry: AgentJournalEntry }) => {
  const payload = entry.payload || {};
  const details = Array.isArray(entry.details) ? entry.details : [];
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full bg-white px-2 py-1 text-xs font-medium text-slate-600 ring-1 ring-slate-200">
              {humanizeMeta(entry.kind || 'step')}
            </span>
            <div className="text-sm font-semibold text-slate-950">{entry.title || 'Шаг запуска'}</div>
          </div>
          {entry.summary ? <div className="mt-2 text-sm leading-6 text-slate-600">{entry.summary}</div> : null}
        </div>
        {entry.status ? <StatusBadge status={entry.status} /> : null}
      </div>
      {details.length ? (
        <div className="mt-3 grid gap-2 md:grid-cols-2">
          {details.map((detail) => (
            <div key={`${detail.label || ''}-${detail.value || ''}`} className="rounded-lg bg-white px-3 py-2 text-xs leading-5 ring-1 ring-slate-200">
              <div className="font-medium text-slate-950">{detail.label || 'Деталь'}</div>
              <div className="mt-1 text-slate-600">{detail.value || ''}</div>
            </div>
          ))}
        </div>
      ) : null}
      <HumanPayloadView payload={payload} />
      <details className="mt-3">
        <summary className="cursor-pointer text-xs font-medium text-slate-500 hover:text-slate-900">Технический журнал</summary>
        <pre className="mt-2 max-h-72 overflow-auto rounded-lg bg-slate-950 p-3 text-[11px] leading-5 text-slate-100">
          {JSON.stringify(payload, null, 2)}
        </pre>
      </details>
    </div>
  );
};

const HumanPayloadView = ({ payload }: { payload: Record<string, unknown> }) => {
  const result = toRecordOrNull(payload.result);
  const items = Array.isArray(payload.items) ? payload.items : [];
  const missing = Array.isArray(payload.missing_information) ? payload.missing_information : [];
  const provenance = Array.isArray(payload.provenance) ? payload.provenance : [];

  return (
    <div className="mt-3 space-y-2 text-xs leading-5 text-slate-700">
      {missing.length ? (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-2 py-2 text-amber-800">
          Нужно уточнить: {missing.map((item) => String(item)).join(', ')}
        </div>
      ) : null}
      {provenance.length ? (
        <div className="rounded-lg bg-white px-2 py-2 ring-1 ring-slate-200">
          Источники: {provenance.map((item) => String(item)).join(', ')}
        </div>
      ) : null}
      {items.length ? (
        <div className="space-y-1">
          {items.slice(0, 3).map((item, index) => (
            <div key={`payload-item-${index}`} className="rounded-lg bg-white px-2 py-2 ring-1 ring-slate-200">
              {formatPayloadItem(item)}
            </div>
          ))}
        </div>
      ) : null}
      {result ? <HumanResultView result={result} /> : null}
    </div>
  );
};

const toRecordOrNull = (value: unknown): Record<string, unknown> | null => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return null;
  }
  return Object.fromEntries(Object.entries(value));
};

const HumanResultView = ({ result }: { result: Record<string, unknown> }) => {
  const entries = Object.entries(result).filter(([, value]) => value !== '' && value !== null && value !== undefined);
  const priorityKeys = [
    'title',
    'summary',
    'risks',
    'facts',
    'fields',
    'next_questions',
    'subject',
    'body',
    'checklist',
    'exceptions',
    'rows_to_review',
    'recommendations',
    'reply_drafts',
    'manual_review_reasons',
    'rules_applied',
    'provenance',
    'delivery_state',
    'publish_state',
  ];
  const priorityEntries = priorityKeys
    .map((key) => ({ key, value: result[key] }))
    .filter((entry) => entry.value !== '' && entry.value !== null && entry.value !== undefined);
  return (
    <div className="space-y-2">
      {priorityEntries.slice(0, 6).map(({ key, value }) => (
        <div key={key} className="rounded-lg bg-white px-2 py-2 ring-1 ring-slate-200">
          <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">{resultFieldLabels[key] || humanizeMeta(key)}</div>
          <div className="mt-1 text-slate-700">{formatPayloadValue(value)}</div>
        </div>
      ))}
      {priorityEntries.length ? null : (
        <div className="rounded-lg bg-white px-2 py-2 ring-1 ring-slate-200">
          {entries.slice(0, 5).map(([key, value]) => (
            <div key={key} className="mt-1 first:mt-0">
              <span className="font-medium text-slate-950">{humanizeMeta(key)}:</span> {formatPayloadValue(value)}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

const formatPayloadItem = (value: unknown) => {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    const entries = Object.entries(value).filter(([, itemValue]) => itemValue !== '' && itemValue !== null && itemValue !== undefined);
    return entries.slice(0, 3).map(([key, itemValue]) => `${humanizeMeta(key)}: ${formatPayloadValue(itemValue)}`).join(' · ');
  }
  return formatPayloadValue(value);
};

const formatPayloadValue = (value: unknown): string => {
  if (Array.isArray(value)) {
    return value.slice(0, 4).map((item) => formatPayloadValue(item)).join(', ');
  }
  if (value && typeof value === 'object') {
    const entries = Object.entries(value).filter(([, itemValue]) => itemValue !== '' && itemValue !== null && itemValue !== undefined);
    return entries.slice(0, 3).map(([key, itemValue]) => `${humanizeMeta(key)}: ${formatPayloadValue(itemValue)}`).join('; ');
  }
  return String(value ?? '');
};

const AgentRunObservabilityPanel = ({
  run,
  activationGate,
  actionLoading,
  onPreviewNextStepAction,
  onActivateVersion,
  onApplyFinanceRequests,
}: {
  run: AgentRun;
  activationGate?: AgentActivationGate;
  actionLoading: boolean;
  onPreviewNextStepAction: (nextStep: string) => void;
  onActivateVersion: (versionId: string) => void;
  onApplyFinanceRequests: (runId: string) => void;
}) => {
  const [downloading, setDownloading] = useState(false);
  const observability = run.observability || {};
  const costTokens = observability.cost_tokens || {};
  const billingLedger = observability.billing_ledger || {};
  const billingActions = billingLedger.actions || [];
  const billingEntries = billingLedger.entries || [];
  const delivery = observability.delivery_status || {};
  const ledgerItems = observability.action_ledger?.items || [];
  const domainRequests = observability.domain_requests?.items || [];
  const errors = observability.errors || [];
  const recoveryActions = observability.recovery_actions || [];
  const runInput = run.input_json && typeof run.input_json === 'object' ? run.input_json : {};
  const rawSupportEndpoint = observability.support_export?.endpoint || `/api/agent-runs/${run.id}/support-export`;
  const supportEndpoint = rawSupportEndpoint.startsWith('/api/') ? rawSupportEndpoint.slice(4) : rawSupportEndpoint;

  const downloadSupportExport = async () => {
    setDownloading(true);
    try {
      const response = await api.get(supportEndpoint, {
        params: { format: 'json' },
      });
      const content = JSON.stringify(response.data, null, 2);
      const blob = new Blob([content], { type: 'application/json;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `agent-run-${run.id}-support.json`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className="mt-4 space-y-4">
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
        <AgentObservabilityMetric icon={Activity} label="Run history" value={run.status} hint={`${observability.step_history?.count || run.steps?.length || 0} шагов`} />
        <AgentObservabilityMetric icon={ReceiptText} label="Billing" value={`${costTokens.settled_tokens || 0} ток.`} hint={`reserve ${costTokens.reserved_tokens || 0} · release ${costTokens.released_tokens || 0}`} />
        <AgentObservabilityMetric icon={Send} label="Delivery" value={humanizeMeta(delivery.state || 'not_applicable')} hint={`${delivery.attempts_success || 0}/${delivery.attempts_total || 0} attempts`} />
        <AgentObservabilityMetric icon={ShieldCheck} label="Approvals" value={String(observability.domain_requests?.pending || observability.approvals?.pending || 0)} hint={`${observability.domain_requests?.count || 0} domain requests`} />
        <AgentObservabilityMetric icon={AlertTriangle} label="Errors" value={String(errors.length)} hint={errors.length ? 'нужна проверка' : 'нет ошибок'} />
      </div>

      <PreviewRunSummaryPanel
        summary={observability.preview_summary}
        runInput={runInput}
        activationGate={activationGate}
        actionLoading={actionLoading}
        onNextStepAction={onPreviewNextStepAction}
        onActivateVersion={onActivateVersion}
      />

      <div className="grid gap-4 xl:grid-cols-5">
        <RunColumn title="Action ledger" icon={ReceiptText}>
          {ledgerItems.map((item) => (
            <TimelineItem
              key={item.action_id || item.trace_id || item.capability || 'action'}
              title={item.capability || item.action_id || 'OpenClaw action'}
              meta={`${item.action_id || 'no action id'} · reserve ${item.billing_summary?.reserved_tokens || 0} · settle ${item.billing_summary?.settled_tokens || 0}`}
              status={item.status || (item.error ? 'failed' : 'linked')}
            />
          ))}
        </RunColumn>
        <RunColumn title="Billing" icon={ReceiptText}>
          {billingActions.map((item) => (
            <BillingActionItem key={item.action_id || item.capability || 'billing'} item={item} />
          ))}
          {billingEntries.slice(0, 3).map((entry, index) => (
            <TimelineItem
              key={`${entry.action_id || 'entry'}-${entry.entry_type || index}-${entry.created_at || index}`}
              title={humanizeMeta(entry.entry_type || 'billing_entry')}
              meta={`${entry.action_id || entry.capability || 'action'} · ${entry.tokens_out || 0} ток. · ${entry.cost || 0}`}
              status={entry.entry_type || 'billing'}
            />
          ))}
        </RunColumn>
        <RunColumn title="Ожидают approval" icon={ShieldCheck}>
          {domainRequests.map((item) => (
            <DomainRequestItem
              key={`${item.kind || 'request'}-${item.id || item.action_id || item.review_id || item.title}`}
              item={item}
              runId={run.id}
              actionLoading={actionLoading}
              onApplyFinanceRequests={onApplyFinanceRequests}
            />
          ))}
        </RunColumn>
        <RunColumn title="Ошибки и статусы" icon={AlertTriangle}>
          {errors.map((item, index) => (
            <TimelineItem
              key={`${item.source || 'error'}-${item.action_id || item.step_key || index}`}
              title={item.error_text || item.step_key || item.action_id || 'Ошибка runtime'}
              meta={item.source || item.status || 'agent runtime'}
              status={item.status || 'failed'}
            />
          ))}
        </RunColumn>
        <RunColumn title="Recovery / support" icon={LifeBuoy}>
          {recoveryActions.map((item) => (
            <TimelineItem key={item.code || item.label || 'recovery'} title={item.label || item.code || 'Recovery action'} meta={item.target || 'support boundary'} status="needs_approval" />
          ))}
          <Button type="button" variant="outline" size="sm" onClick={downloadSupportExport} disabled={downloading}>
            {downloading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Download className="mr-2 h-4 w-4" />}
            Support export
          </Button>
        </RunColumn>
      </div>
    </div>
  );
};

const DomainRequestItem = ({
  item,
  runId,
  actionLoading,
  onApplyFinanceRequests,
}: {
  item: NonNullable<NonNullable<AgentRunObservability['domain_requests']>['items']>[number];
  runId: string;
  actionLoading: boolean;
  onApplyFinanceRequests: (runId: string) => void;
}) => {
  const isFinanceRequest = item.kind === 'finance_transaction_request';
  const canApplyFinance = isFinanceRequest && item.can_apply === true && item.apply_state === 'apply_ready';
  const detailEntries = [
    item.why_waiting ? ['why_waiting', item.why_waiting] : null,
    isFinanceRequest ? ['finance_rows', {
      prepared: item.proposal_count || item.rows_total || 0,
      imported: item.rows_imported || 0,
      skipped: item.rows_skipped || 0,
      failed: item.rows_failed || 0,
    }] : null,
    item.limits ? ['limits', item.limits] : null,
    item.consent ? ['consent', item.consent] : null,
    item.delivery_journal ? ['delivery_journal', item.delivery_journal] : null,
    item.publish_requests ? ['publish_requests', item.publish_requests] : null,
    item.provider_handoff ? ['provider_handoff', item.provider_handoff] : null,
    item.error ? ['error', item.error] : null,
    item.row_values?.length ? ['row_values', item.row_values] : null,
    item.visual_diff?.length ? ['visual_diff', item.visual_diff] : null,
    item.suggestions?.length ? ['suggestions', item.suggestions] : null,
  ].filter((entry): entry is [string, unknown] => Boolean(entry));
  return (
    <div className="rounded-xl bg-white px-3 py-3 shadow-sm ring-1 ring-slate-200">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="truncate text-sm font-medium text-slate-900">{item.title || humanizeMeta(item.kind || 'domain request')}</div>
          <div className="mt-1 text-xs text-slate-500">{item.summary || item.id || 'domain request'}</div>
        </div>
        <StatusBadge status={item.approval_state || item.apply_state || item.delivery_state || item.status || 'pending'} />
      </div>
      {detailEntries.length ? (
        <div className="mt-2 space-y-1 text-xs leading-5 text-slate-600">
          {detailEntries.slice(0, 3).map(([key, value]) => (
            <div key={key}>
              <span className="font-medium text-slate-800">{humanizeMeta(key)}:</span> {formatPayloadValue(value)}
            </div>
          ))}
        </div>
      ) : null}
      {canApplyFinance ? (
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <Button
            type="button"
            size="sm"
            onClick={() => onApplyFinanceRequests(runId)}
            disabled={actionLoading}
          >
            {actionLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <ReceiptText className="mr-2 h-4 w-4" />}
            Применить в финансы
          </Button>
          <span className="text-[11px] leading-4 text-slate-500">
            Запись в LocalOS Finance выполнится только после этого действия.
          </span>
        </div>
      ) : null}
    </div>
  );
};

const AgentObservabilityMetric = ({
  icon: Icon,
  label,
  value,
  hint,
}: {
  icon: typeof Clock3;
  label: string;
  value: string;
  hint: string;
}) => (
  <div className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3">
    <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-slate-500">
      <Icon className="h-4 w-4" />
      {label}
    </div>
    <div className="mt-2 text-lg font-semibold text-slate-950">{value}</div>
    <div className="mt-1 text-xs text-slate-500">{hint}</div>
  </div>
);

const PreviewRunSummaryPanel = ({
  summary,
  runInput,
  activationGate,
  actionLoading = false,
  onNextStepAction,
  onActivateVersion,
}: {
  summary?: Record<string, unknown>;
  runInput: Record<string, unknown>;
  activationGate?: AgentActivationGate;
  actionLoading?: boolean;
  onNextStepAction?: (nextStep: string) => void;
  onActivateVersion?: (versionId: string) => void;
}) => {
  const inputPreviewContext = runInput.preview_context && typeof runInput.preview_context === 'object' ? toRecordOrNull(runInput.preview_context) || {} : {};
  const isPreview = Boolean(summary?.is_preview || runInput.preview_mode);
  if (!isPreview) {
    return null;
  }
  const dataSources = Array.isArray(summary?.data_sources)
    ? summary.data_sources.map((item) => String(item || '')).filter(Boolean)
    : [];
  const completedSteps = Array.isArray(summary?.completed_steps)
    ? summary.completed_steps.map((item) => String(item || '')).filter(Boolean)
    : [];
  const artifacts = Array.isArray(summary?.artifacts) ? summary.artifacts : [];
  const pendingApprovals = Array.isArray(summary?.pending_approvals) ? summary.pending_approvals : [];
  const waitingActions = Array.isArray(summary?.waiting_actions) ? summary.waiting_actions : [];
  const summaryActionPlan = Array.isArray(summary?.openclaw_action_plan) ? summary.openclaw_action_plan : [];
  const inputActionPlan = Array.isArray(runInput.openclaw_action_plan) ? runInput.openclaw_action_plan : [];
  const openClawActionPlan = summaryActionPlan.length ? summaryActionPlan : inputActionPlan;
  const policyEnvelope = toRecordOrNull(summary?.policy_envelope) || toRecordOrNull(runInput.policy_envelope) || {};
  const approvalGate = toRecordOrNull(summary?.approval_gate) || {};
  const providerBindings = Array.isArray(runInput.provider_bindings) ? runInput.provider_bindings : [];
  const understoodTask = String(summary?.understood_task || objectValue(inputPreviewContext, 'understood_task') || objectValue(runInput, 'goal') || 'LocalOS проверяет compiled workflow на безопасном примере.');
  const manualControl = String(summary?.manual_control || objectValue(inputPreviewContext, 'manual_control') || 'Перед внешним действием нужен approval.');
  const safePreview = summary?.safe_preview !== false && runInput.external_side_effects_allowed === false;
  const nextStep = String(summary?.next_step || 'review_preview');
  const nextStepLabel = String(summary?.next_step_label || 'Проверить preview');
  const nextStepDescription = String(summary?.next_step_description || summary?.activation_hint || 'Проверьте результат preview и следующий шаг агента.');
  const activationVersionId = String(activationGate?.active_version_id || runInput.blueprint_version_id || '');
  const canActivateFromPreview = activationGate?.can_activate === true && Boolean(activationVersionId);
  const sourceEvent = toRecordOrNull(runInput.source_event) || {};
  const eventType = String(sourceEvent.event_type || runInput.trigger || 'manual.preview');
  const compiledSteps = Array.isArray(objectValue(inputPreviewContext, 'steps')) ? objectValue(inputPreviewContext, 'steps') : [];
  const simulationSteps = [
    {
      key: 'input',
      title: 'Входные данные',
      status: safePreview ? 'completed' : 'pending',
      detail: eventType,
    },
    {
      key: 'preflight',
      title: 'Preflight',
      status: summary?.preflight_ready === false ? 'blocked' : 'completed',
      detail: summary?.preflight_ready === false ? 'нужны подключения' : 'подключения, лимиты и policy проверены',
    },
    {
      key: 'workflow',
      title: 'Compiled workflow',
      status: completedSteps.length ? 'completed' : 'pending',
      detail: completedSteps.length
        ? `${completedSteps.length} шагов выполнено`
        : compiledSteps.length
        ? `${compiledSteps.length} шагов в плане`
        : 'шаги появятся после запуска',
    },
    {
      key: 'approval',
      title: 'Approval gate',
      status: pendingApprovals.length || waitingActions.length ? 'waiting_approval' : 'completed',
      detail: pendingApprovals.length || waitingActions.length
        ? 'внешнее действие остановлено до решения человека'
        : 'ручной контроль проверен',
    },
    {
      key: 'activation',
      title: 'Activation gate',
      status: canActivateFromPreview ? 'completed' : 'pending',
      detail: canActivateFromPreview ? 'версию можно активировать' : nextStepDescription,
    },
  ];
  const actionLabel = canActivateFromPreview
    ? String(activationGate?.primary_action_label || 'Активировать версию')
    : previewNextStepActionLabel(nextStep, nextStepLabel);
  return (
    <div className="rounded-2xl border border-sky-200 bg-sky-50 px-4 py-4 text-sm leading-6 text-sky-950">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="font-semibold">Что показал preview run</div>
          <div className="mt-1 max-w-3xl text-xs leading-5 text-sky-800">
            {String(summary?.headline || 'Safe preview выполнен без внешних действий.')}
          </div>
        </div>
        <span className="rounded-full bg-white px-2.5 py-1 text-xs font-medium text-sky-700 ring-1 ring-sky-200">
          {safePreview ? 'Preview run без внешних действий' : 'проверьте внешние действия'}
        </span>
      </div>

      <div className="mt-3 grid gap-2 md:grid-cols-3">
        <PreviewRunFact label="Задача" value={understoodTask} />
        <PreviewRunFact label="Данные" value={dataSources.length ? dataSources.join(', ') : providerBindings.length ? providerBindings.map((item) => formatPayloadValue(item)).join(' · ') : 'проверены preflight'} />
        <PreviewRunFact label="Ручной контроль" value={manualControl} />
      </div>

      <CompiledPreviewSimulationPanel steps={simulationSteps} safePreview={safePreview} externalActionsPerformed={Boolean(summary?.external_actions_performed)} />

      <OpenClawPreviewActionPlanPanel
        actions={openClawActionPlan}
        policyEnvelope={policyEnvelope}
        approvalGate={approvalGate}
        safePreview={safePreview}
      />

      <div className="mt-3 grid gap-2 lg:grid-cols-3">
        <PreviewSummaryList
          title="Шаги"
          items={completedSteps.length ? completedSteps.slice(0, 5).map((item) => humanizeMeta(item)) : ['Шаги будут видны после выполнения preview.']}
        />
        <PreviewSummaryList
          title="Результаты"
          items={artifacts.length ? artifacts.slice(0, 4).map((item) => {
            const record = toRecordOrNull(item) || {};
            return `${String(record.title || humanizeMeta(String(record.type || 'artifact')))}: ${String(record.summary || 'сохранён для проверки')}`;
          }) : ['Artifact появится после подготовки результата.']}
        />
        <PreviewSummaryList
          title="Approval"
          items={
            pendingApprovals.length
              ? pendingApprovals.slice(0, 4).map((item) => {
                const record = toRecordOrNull(item) || {};
                return `${String(record.title || record.approval_type || 'Approval')}: ${humanizeMeta(String(record.status || 'pending'))}`;
              })
              : waitingActions.length
                ? waitingActions.slice(0, 4).map((item) => {
                  const record = toRecordOrNull(item) || {};
                  return `${humanizeMeta(String(record.kind || 'external_action'))}: ${String(record.why || record.state || 'ждёт approval')}`;
                })
                : ['Внешние действия останутся за approval gate.']
          }
        />
      </div>

      <div className="mt-3 rounded-xl bg-white px-3 py-2 text-xs leading-5 text-sky-800 ring-1 ring-sky-100">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <div className="font-semibold text-sky-900">Следующий шаг: {nextStepLabel}</div>
            <div className="mt-1">{nextStepDescription}</div>
            {canActivateFromPreview ? (
              <div className="mt-1 font-medium text-emerald-700">Activation gate готов: safe preview, preflight и compiled workflow прошли проверку.</div>
            ) : null}
            <div className="mt-1 text-sky-700">
              {String(summary?.activation_hint || 'После safe preview activation gate покажет, можно ли активировать версию.')}
            </div>
          </div>
          {canActivateFromPreview && onActivateVersion ? (
            <Button type="button" size="sm" className="shrink-0" onClick={() => onActivateVersion(activationVersionId)} disabled={actionLoading}>
              {actionLabel}
            </Button>
          ) : onNextStepAction ? (
            <Button type="button" size="sm" variant="outline" className="shrink-0 bg-white" onClick={() => onNextStepAction(nextStep)} disabled={actionLoading}>
              {actionLabel}
            </Button>
          ) : null}
        </div>
      </div>
    </div>
  );
};

const OpenClawPreviewActionPlanPanel = ({
  actions,
  policyEnvelope,
  approvalGate,
  safePreview,
}: {
  actions: unknown[];
  policyEnvelope: Record<string, unknown>;
  approvalGate: Record<string, unknown>;
  safePreview: boolean;
}) => {
  const boundary = String(policyEnvelope.execution_boundary || 'openclaw_action_orchestrator');
  const approvalOwner = String(policyEnvelope.approval_owner || 'LocalOS');
  const billingOwner = String(policyEnvelope.billing_owner || policyEnvelope.cost_owner || 'LocalOS');
  const externalSideEffectsAllowed = policyEnvelope.external_side_effects_allowed_in_preview === true;
  const waitingCount = Number(approvalGate.waiting_actions_count || 0);
  const pendingApprovalsCount = Number(approvalGate.pending_approvals_count || 0);
  const visibleActions = actions.slice(0, 4).map((item) => toRecordOrNull(item) || {});
  if (!visibleActions.length && !Object.keys(policyEnvelope).length) {
    return null;
  }
  return (
    <div className="mt-3 rounded-xl bg-white px-3 py-3 text-xs leading-5 text-sky-800 ring-1 ring-sky-100">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <div className="font-semibold text-sky-950">OpenClaw actions в safe preview</div>
          <div className="mt-1 text-sky-700">
            LocalOS показывает будущие tool calls, но оставляет исполнение за policy, limits, billing и audit.
          </div>
        </div>
        <span className={cn('rounded-full px-2 py-0.5 font-medium ring-1', safePreview && !externalSideEffectsAllowed ? 'bg-emerald-50 text-emerald-700 ring-emerald-200' : 'bg-amber-50 text-amber-700 ring-amber-200')}>
          {safePreview && !externalSideEffectsAllowed ? 'side effects выключены' : 'нужна проверка side effects'}
        </span>
      </div>

      <div className="mt-3 grid gap-2 md:grid-cols-3">
        <PreviewRunFact label="Boundary" value={boundary} />
        <PreviewRunFact label="Approval / billing" value={`${approvalOwner} approvals · ${billingOwner} billing`} />
        <PreviewRunFact label="Gate" value={`${pendingApprovalsCount} approvals · ${waitingCount} действий ждут`} />
      </div>

      {visibleActions.length ? (
        <div className="mt-3 grid gap-2 md:grid-cols-2">
          {visibleActions.map((action, index) => {
            const title = String(action.title || action.provider_action_ref || action.capability || `OpenClaw action ${index + 1}`);
            const meta = [
              action.provider_action_ref ? String(action.provider_action_ref) : '',
              action.capability ? String(action.capability) : '',
              action.provider_policy ? String(action.provider_policy) : 'localos_envelope',
            ].filter(Boolean).join(' · ');
            const requiresApproval = action.requires_approval === true || Boolean(action.approval_class);
            return (
              <div key={`${title}-${index}`} className="rounded-lg bg-sky-50 px-2.5 py-2 ring-1 ring-sky-100">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="line-clamp-1 font-semibold text-sky-950">{title}</div>
                    <div className="mt-1 line-clamp-2 text-sky-700">{meta || 'OpenClaw action за LocalOS envelope'}</div>
                  </div>
                  <span className={cn('shrink-0 rounded-full px-2 py-0.5 font-medium ring-1', requiresApproval ? 'bg-amber-50 text-amber-700 ring-amber-200' : 'bg-emerald-50 text-emerald-700 ring-emerald-200')}>
                    {requiresApproval ? 'approval' : 'safe'}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="mt-3 rounded-lg bg-sky-50 px-2.5 py-2 text-sky-700 ring-1 ring-sky-100">
          OpenClaw action plan появится после компиляции workflow или повторного safe preview.
        </div>
      )}
    </div>
  );
};

const previewNextStepActionLabel = (nextStep: string, fallback: string) => {
  const labels: Record<string, string> = {
    connect_required_integrations: 'Открыть подключения',
    fix_preview_error: 'Открыть логику',
    review_approvals: 'Открыть approvals',
    check_activation_gate: 'Проверить активацию',
    review_preview: 'Открыть запуск',
  };
  return labels[nextStep] || fallback || 'Открыть следующий шаг';
};

const CompiledPreviewSimulationPanel = ({
  steps,
  safePreview,
  externalActionsPerformed,
}: {
  steps: Array<{ key: string; title: string; status: string; detail: string }>;
  safePreview: boolean;
  externalActionsPerformed: boolean;
}) => (
  <div className="mt-3 rounded-xl bg-white px-3 py-3 text-xs leading-5 text-sky-800 ring-1 ring-sky-100">
    <div className="flex flex-wrap items-start justify-between gap-2">
      <div>
        <div className="font-semibold text-sky-950">Симуляция compiled workflow</div>
        <div className="mt-1 text-sky-700">
          Preview показывает, как агент пройдёт workflow в runtime: вход, preflight, шаги, approvals и activation gate.
        </div>
      </div>
      <span className={cn('rounded-full px-2 py-0.5 font-medium ring-1', safePreview && !externalActionsPerformed ? 'bg-emerald-50 text-emerald-700 ring-emerald-200' : 'bg-amber-50 text-amber-700 ring-amber-200')}>
        {safePreview && !externalActionsPerformed ? 'внешних действий не было' : 'проверьте side effects'}
      </span>
    </div>
    <div className="mt-3 grid gap-2 md:grid-cols-5">
      {steps.map((step, index) => (
        <div key={step.key} className={cn('rounded-lg px-2 py-2 ring-1', previewSimulationTone(step.status))}>
          <div className="flex items-center gap-2">
            <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-white text-[11px] font-semibold ring-1 ring-current/10">
              {index + 1}
            </span>
            <div className="min-w-0 font-semibold">{step.title}</div>
          </div>
          <div className="mt-1 line-clamp-3 text-[11px] leading-4">{step.detail}</div>
        </div>
      ))}
    </div>
  </div>
);

const previewSimulationTone = (status: string) => {
  if (status === 'completed') {
    return 'bg-emerald-50 text-emerald-800 ring-emerald-100';
  }
  if (status === 'waiting_approval') {
    return 'bg-amber-50 text-amber-800 ring-amber-100';
  }
  if (status === 'blocked' || status === 'failed') {
    return 'bg-rose-50 text-rose-800 ring-rose-100';
  }
  return 'bg-slate-50 text-slate-600 ring-slate-200';
};

const PreviewSummaryList = ({ title, items }: { title: string; items: string[] }) => (
  <div className="rounded-xl bg-white px-3 py-2 text-xs leading-5 ring-1 ring-sky-100">
    <div className="font-semibold text-sky-900">{title}</div>
    <div className="mt-1 space-y-1 text-sky-700">
      {items.map((item, index) => (
        <div key={`${title}-${index}`} className="line-clamp-2">{item}</div>
      ))}
    </div>
  </div>
);

const PreviewRunFact = ({ label, value }: { label: string; value: string }) => (
  <div className="rounded-xl bg-white px-3 py-2 text-xs leading-5 ring-1 ring-sky-100">
    <div className="font-semibold text-sky-900">{label}</div>
    <div className="mt-1 text-sky-700">{value || 'не указано'}</div>
  </div>
);

const RunColumn = ({
  title,
  icon: Icon,
  children,
}: {
  title: string;
  icon: typeof Clock3;
  children: React.ReactNode;
}) => (
  <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
    <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-900">
      <Icon className="h-4 w-4" />
      {title}
    </div>
    <div className="space-y-2">
      {children || <div className="text-sm text-slate-500">Пока пусто</div>}
    </div>
  </div>
);

const TimelineItem = ({ title, meta, status }: { title: string; meta: string; status: string }) => (
  <div className="rounded-xl bg-white px-3 py-3 shadow-sm ring-1 ring-slate-200">
    <div className="flex items-start justify-between gap-3">
      <div className="min-w-0">
        <div className="truncate text-sm font-medium text-slate-900">{title}</div>
        <div className="mt-1 text-xs text-slate-500">{meta}</div>
      </div>
      <StatusBadge status={status} />
    </div>
  </div>
);

const BillingActionItem = ({
  item,
}: {
  item: AgentRunBillingAction;
}) => {
  const reserved = item.reserved_tokens || 0;
  const settled = item.settled_tokens || 0;
  const released = item.released_tokens || 0;
  const inflight = item.inflight_reserved_tokens || Math.max(reserved - settled - released, 0);
  return (
    <div className="rounded-xl bg-white px-3 py-3 shadow-sm ring-1 ring-slate-200">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="truncate text-sm font-medium text-slate-900">{item.capability || item.action_id || 'billing action'}</div>
          <div className="mt-1 text-xs text-slate-500">{item.action_id || 'no action id'}</div>
        </div>
        <StatusBadge status={inflight > 0 ? 'reserved' : item.status || 'settled'} />
      </div>
      <div className="mt-2 grid grid-cols-3 gap-2 text-xs">
        <div className="rounded-lg bg-slate-50 px-2 py-2">
          <div className="font-semibold text-slate-900">{reserved}</div>
          <div className="text-slate-500">reserve</div>
        </div>
        <div className="rounded-lg bg-slate-50 px-2 py-2">
          <div className="font-semibold text-slate-900">{settled}</div>
          <div className="text-slate-500">settle</div>
        </div>
        <div className="rounded-lg bg-slate-50 px-2 py-2">
          <div className="font-semibold text-slate-900">{released}</div>
          <div className="text-slate-500">release</div>
        </div>
      </div>
      <div className="mt-2 text-xs text-slate-500">
        inflight {inflight} ток. · cost {item.total_cost || 0} · entries {item.entry_count || 0}
      </div>
    </div>
  );
};

const compactValue = (value: unknown) => {
  if (Array.isArray(value)) {
    return value.length ? value.join(', ') : 'any';
  }
  if (typeof value === 'number') {
    return String(value);
  }
  if (typeof value === 'string' && value.trim()) {
    return value.trim();
  }
  return 'any';
};

const ArtifactSourceSummary = ({ payload }: { payload: AgentArtifact['payload_json'] }) => {
  const filters = payload?.filters || {};
  const filterEntries = Object.entries(filters).filter(([, value]) => {
    if (Array.isArray(value)) {
      return value.length > 0;
    }
    return value !== '' && value !== null && value !== undefined;
  });
  if (payload?.source !== 'prospectingleads' && !payload?.source_artifact && filterEntries.length === 0) {
    return null;
  }
  return (
    <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs leading-5 text-slate-600">
      {payload?.source === 'prospectingleads' ? (
        <div className="font-medium text-slate-800">Источник лидов: prospectingleads</div>
      ) : null}
      {payload?.source_artifact ? (
        <div>Сформировано из: {payload.source_artifact}</div>
      ) : null}
      {filterEntries.length ? (
        <div className="mt-1 flex flex-wrap gap-1.5">
          {filterEntries.map(([key, value]) => (
            <span key={key} className="rounded-md bg-white px-2 py-1 ring-1 ring-slate-200">
              {key}: {compactValue(value)}
            </span>
          ))}
        </div>
      ) : null}
    </div>
  );
};

const ApprovalPayloadSummary = ({ approval }: { approval: AgentApproval }) => {
  const payload = approval.payload_json || {};
  const count = typeof payload.count === 'number' ? payload.count : null;
  const artifactType = typeof payload.artifact_type === 'string' ? payload.artifact_type : '';
  if (!artifactType && count === null) {
    return null;
  }
  return (
    <div className="mt-3 rounded-lg bg-white/80 px-3 py-2 text-xs leading-5 text-slate-600 ring-1 ring-amber-100">
      {artifactType ? <div>Результат: {artifactType}</div> : null}
      {count !== null ? <div>Ожидают решения: {count}</div> : null}
    </div>
  );
};

const ArtifactItem = ({ artifact }: { artifact: AgentArtifact }) => {
  const payload = artifact.payload_json || {};
  const items = Array.isArray(payload.items) ? payload.items : [];
  const preview = items.slice(0, 3);
  return (
    <div className="rounded-xl bg-white px-3 py-3 shadow-sm ring-1 ring-slate-200">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="truncate text-sm font-medium text-slate-900">{artifact.title}</div>
          <div className="mt-1 text-xs text-slate-500">
            {payload.source || artifact.artifact_type} · {payload.count ?? items.length} items
          </div>
        </div>
        <StatusBadge status={typeof payload.status === 'string' ? payload.status : 'completed'} />
      </div>
      <ArtifactSourceSummary payload={payload} />
      {preview.length ? (
        <div className="mt-3 space-y-2">
          {preview.map((item, index) => (
            <div key={`${artifact.id}-${index}`} className="rounded-lg bg-slate-50 px-2 py-2 text-xs leading-5 text-slate-600">
              {String(item.name || item.lead_name || item.status || item.delivery_status || item.id || 'item')}
            </div>
          ))}
        </div>
      ) : null}
      <details className="mt-3">
        <summary className="cursor-pointer text-xs font-medium text-slate-500 hover:text-slate-900">
          Технический журнал
        </summary>
        <pre className="mt-2 max-h-72 overflow-auto rounded-lg bg-slate-950 p-3 text-[11px] leading-5 text-slate-100">
          {JSON.stringify(payload, null, 2)}
        </pre>
      </details>
    </div>
  );
};
