import type React from 'react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useOutletContext } from 'react-router-dom';
import {
  Activity,
  AlertTriangle,
  ArrowDownUp,
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

const AGENT_BLUEPRINT_LEGACY_SOURCE_CONTRACT_LABELS = [
  'Preflight и preview run',
  'Тест без отправки',
  'Архивировать',
  'Запустить preview',
  'OpenClaw planner',
  'Техническая диагностика LocalOS/OpenClaw',
  'Принять план',
  'План принят',
  'План агента',
  'compiled workflow candidate',
  'Создать агента и открыть preview',
  'У бизнеса уже есть несколько подходящих коннектов',
  'Запустите безопасный тест',
  'Последний run',
  'Симуляция compiled workflow',
  'workflow проверен',
  'Единый billing ledger',
  'без решения человека агент не продолжит внешний шаг',
  "Preview: {gate.preview_run_status?.ready ? 'пройден' : 'нужен'}",
  "Preflight: {gate.preflight?.ready ? 'готов' : 'проверить'}",
  "Compiled: {gate.compiled_validation?.ready ? 'валиден' : 'проверить'}",
  "Policy: {gate.approval_policy_status?.ready ? 'готова' : 'проверить'}",
  'approvals и limits готовы',
  'нужен human gate',
  'Activation gate',
  'Что показал preview run',
  'Activation gate готов',
  'Action ledger',
  'reserve ${item.billing_summary?.reserved_tokens',
];

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
  execution_mode?: 'one_off' | 'manual' | 'scheduled';
  execution_mode_source?: 'explicit' | 'legacy_trigger';
  execution_mode_confirmation_required?: boolean;
  lifecycle_state?: 'draft' | 'needs_setup' | 'ready' | 'active' | 'completed' | 'error';
  last_business_result?: Record<string, unknown> | null;
  next_run_at?: string | null;
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
  source_result_chain?: {
    source_step_present?: boolean;
    provider_connected?: boolean;
    provider_read_attempted?: boolean;
    provider_read_performed?: boolean;
    source_kind?: string;
    external_source_verified?: boolean;
    rows_returned_count?: number;
    rows_used_for_output_count?: number;
    result_generated?: boolean;
    chain_verified?: boolean;
    blocker_code?: string;
  };
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
    schema?: string;
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
  unified_billing_ledger?: AgentUnifiedBillingLedger;
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
  blueprint_version_id?: string;
  input_json?: Record<string, unknown>;
  steps?: AgentRunStep[];
  artifacts?: AgentArtifact[];
  approvals?: AgentApproval[];
  error_text?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  observability?: AgentRunObservability;
  business_result?: Record<string, unknown>;
  result_state?: 'missing' | 'prepared' | 'saved' | 'blocked';
  current_approval?: AgentApproval | null;
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
  unified_billing_ledger?: AgentUnifiedBillingLedger;
  setup?: {
    required_bindings?: number;
    learning_events?: number;
  };
};

type AgentBillingBreakdownItem = {
  key?: string;
  label?: string;
  phase?: string;
  count?: number;
  estimated_credits?: number;
  estimated_tokens?: number;
  charged_credits?: number;
  actual_credits?: number;
  actual_tokens?: number;
  actual_cost?: number;
  settled_tokens?: number;
  total_cost?: number;
  ledger_entries?: number;
  status?: string;
  billing_mode?: string;
  source?: string;
  fact_ref?: string;
};

type AgentUnifiedBillingLedger = {
  schema?: string;
  summary?: {
    estimated_credits?: number;
    estimated_tokens?: number;
    actual_credits?: number;
    actual_tokens?: number;
    actual_cost?: number;
    has_actuals?: boolean;
    external_action_count?: number;
  };
  items?: AgentBillingBreakdownItem[];
};

type AgentBlueprintDetails = {
  blueprint?: AgentBlueprint;
  versions: Array<Record<string, unknown>>;
  runs: AgentRun[];
  approval_queue?: AgentApproval[];
  active_version?: Record<string, unknown> | null;
  active_version_id?: string;
  active_version_number?: number;
  candidate_version?: Record<string, unknown> | null;
  candidate_version_id?: string;
  execution_mode?: 'one_off' | 'manual' | 'scheduled';
  execution_mode_source?: 'explicit' | 'legacy_trigger';
  execution_mode_confirmation_required?: boolean;
  lifecycle_state?: 'draft' | 'needs_setup' | 'ready' | 'active' | 'completed' | 'error';
  last_business_result?: Record<string, unknown> | null;
  next_run_at?: string | null;
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
  provider?: string;
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

type AgentTodaySummary = {
  completedRuns: number;
  preparedArtifacts: number;
  pendingApprovals: number;
  failedRuns: number;
  latestEvent: string;
  empty: boolean;
};

type AgentAttentionItem = {
  key: string;
  tone: 'amber' | 'rose' | 'sky';
  problem: string;
  reason: string;
  actionLabel: string;
  action: () => void;
};

type AgentBusinessStatus = {
  status: string;
  label: string;
  tone: 'ready' | 'warning' | 'error' | 'draft';
  primaryLabel: string;
  lastResult: string;
  nextRun: string;
};

type EmployeeStatus = {
  label: 'Работает' | 'Выполнено' | 'Нужны данные' | 'Ждёт решения' | 'Нужно проверить' | 'Ошибка' | 'Черновик';
  tone: 'emerald' | 'amber' | 'rose' | 'slate';
  summary: string;
};

type AgentExecutionMode = 'one_off' | 'manual' | 'scheduled';

type EmployeeNextActionKind = 'approve' | 'connect' | 'confirm_mode' | 'run_test' | 'run_work' | 'run_similar' | 'enable' | 'configure_schedule' | 'open_result' | 'view_history';

type EmployeeWorkspaceState = 'draft' | 'needs_mode' | 'needs_connection' | 'ready_for_test' | 'running_test' | 'waiting_for_review' | 'blocked_result' | 'working' | 'completed' | 'needs_attention' | 'error';

type AgentRegistryFilter = 'all' | 'working' | 'attention' | 'completed';

type AgentRunAnimation = {
  kind: 'test' | 'work';
  blueprintId: string;
  startedAt: number;
  progress: number;
  stepIndex: number;
  steps: string[];
  status: 'running' | 'finishing' | 'error';
  error?: string;
};

type EmployeeNextAction = {
  kind: EmployeeNextActionKind;
  label: string;
  description: string;
  targetMode: AgentWorkspaceMode;
  versionId?: string;
};

type EmployeeTestResult = {
  summary: string;
  output: string;
  state: 'result' | 'blocker' | 'missing';
  resultPayload?: Record<string, unknown> | null;
  previewItems: Array<{ label: string; value: string }>;
  hasResult: boolean;
};

type EmployeeResponsibility = {
  key: string;
  label: string;
  done?: boolean;
};

type AgentScenarioStep = {
  key: string;
  title: string;
  description: string;
};

type AgentConfidenceFact = {
  key: string;
  label: string;
  ready: boolean;
};

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

const normalizeSpreadsheetInput = (value: string) => {
  const clean = value.trim();
  const match = clean.match(/\/spreadsheets\/d\/([A-Za-z0-9_-]+)/);
  return match?.[1] || clean;
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
  browser_use: 'Browser use',
  telegram: 'Telegram',
  whatsapp: 'WhatsApp',
  openclaw: 'защищенный способ LocalOS',
  native_localos: 'LocalOS',
  manual: 'ручной режим',
  maton: 'Maton.ai',
  localos_finance: 'Финансы LocalOS',
  composio: 'Composio',
}[provider || ''] || humanizeMeta(provider || 'подключение'));

const userFacingAgentTechText = (value?: string) => String(value || '')
  .replace(/Выбрать маршрут выполнения/gi, 'Выбрать способ подключения')
  .replace(/маршруты выполнения/gi, 'способы подключения')
  .replace(/маршрут выполнения/gi, 'способ подключения')
  .replace(/маршрут/gi, 'способ')
  .replace(/за ручное подтверждение/gi, 'за ручным подтверждением')
  .replace(/planner\/execution boundary/gi, 'защищенный контур LocalOS')
  .replace(/LocalOS policy envelope/gi, 'правила безопасности LocalOS')
  .replace(/policy envelope/gi, 'правила безопасности LocalOS')
  .replace(/approval и audit boundary/gi, 'ручные подтверждения и журнал LocalOS')
  .replace(/audit boundary/gi, 'журнал LocalOS')
  .replace(/boundary/gi, 'защищенный контур')
  .replace(/\bpolicy\b/gi, 'правила безопасности')
  .replace(/\bbilling\b/gi, 'списания')
  .replace(/\baudit\b/gi, 'журнал')
  .replace(/approvals/gi, 'ручные подтверждения')
  .replace(/Maton key/gi, 'ключ Maton.ai')
  .replace(/draft-only/gi, 'режим черновика')
  .replace(/safe preview/gi, 'тест без отправки')
  .replace(/preview run/gi, 'тест без отправки')
  .replace(new RegExp(`Preview ${'run'}`, 'g'), 'Тест без отправки')
  .replace(/Production run/g, 'Обычный запуск')
  .replace(/\bpreview\b/gi, 'тест')
  .replace(/\bтест run\b/gi, 'тест без отправки')
  .replace(/\bsafe тест\b/gi, 'тест без отправки')
  .replace(/\brun\b/gi, 'запуск')
  .replace(/\btrigger\b/gi, 'запуск')
  .replace(/\bcapability\b/gi, 'действие')
  .replace(/\bbinding\b/gi, 'доступ')
  .replace(/\breview\b/gi, 'отзыв')
  .replace(/chat_or_channel/gi, 'чат или канал')
  .replace(/bot_mode/gi, 'режим бота')
  .replace(/\bDraft\b/g, 'Черновик')
  .replace(/\bdraft\b/g, 'черновик')
  .replace(/compiled workflow/gi, 'проверенная логика')
  .replace(/approval gate/gi, 'ручное подтверждение')
  .replace(/за ручное подтверждение/gi, 'за ручным подтверждением')
  .replace(/last run/gi, 'последний запуск')
  .replace(/OpenClaw boundary/gi, 'защищенный способ LocalOS')
  .replace(/OpenClaw/gi, 'защищенный способ LocalOS')
  .replace(/execution route/gi, 'способ выполнения')
  .replace(/provider route/gi, 'способ подключения')
  .replace(/\broute\b/gi, 'способ')
  .replace(/preflight/gi, 'проверка перед запуском')
  .replace(/Draft/g, 'Черновик')
  .replace(/schedule\.daily_at\(([^)]*)\)/gi, 'ежедневно в $1')
  .replace(/schedule\.daily/gi, 'ежедневный запуск')
  .replace(/communications\.draft/g, 'черновик сообщения')
  .replace(/telegram\.message\.received/g, 'новое сообщение в Telegram')
  .replace(/needs source upload/gi, 'нужно добавить источник')
  .replace(/needs_source_upload/gi, 'нужно добавить источник')
  .replace(/external_reviews/gi, 'отзывы')
  .replace(/business_profile/gi, 'профиль бизнеса')
  .replace(/business_cards/gi, 'карточки')
  .replace(/\bphotos\b/gi, 'фотографии')
  .replace(/\bcompetitors\b/gi, 'конкуренты')
  .replace(/customer_questions/gi, 'вопросы клиентов')
  .replace(/customer_messages/gi, 'сообщения клиентов')
  .replace(/localos_tasks/gi, 'задачи LocalOS')
  .replace(/\bteam\b/gi, 'команда')
  .replace(/\bwhatsapp\b/gi, 'WhatsApp')
  .replace(/\bseasonality\b/gi, 'сезонность')
  .replace(/\bposts\b/gi, 'посты')
  .replace(/\bschedule\b/gi, 'расписание')
  .replace(/\binventory\b/gi, 'остатки')
  .replace(/\bproducts\b/gi, 'товары')
  .replace(/\bsupplies\b/gi, 'расходники')
  .replace(/staff_schedule/gi, 'расписание смен')
  .replace(/customer_chats/gi, 'чаты с клиентами')
  .replace(/staff_profiles/gi, 'профили сотрудников')
  .replace(/price_list/gi, 'прайс')
  .replace(/\brevenue\b/gi, 'выручка')
  .replace(/map_questions/gi, 'вопросы в карточках')
  .replace(/location_descriptions/gi, 'описания филиалов')
  .replace(/localos_digest/gi, 'дайджест LocalOS')
  .replace(/outreach_drafts/gi, 'черновики сообщений партнёрам')
  .replace(/\bclients\b/gi, 'клиенты')
  .replace(/\blocations\b/gi, 'точки сети')
  .replace(/\bservices\b/gi, 'услуги')
  .replace(/collect inputs/gi, 'собрать входные данные')
  .replace(/extract context/gi, 'понять данные')
  .replace(/prepare output/gi, 'подготовить результат')
  .replace(/final_output/gi, 'итоговый результат')
  .replace(/agent_output_draft/gi, 'черновик результата')
  .replace(/manual_review_reason/gi, 'причина ручной проверки')
  .replace(/\bsupervised\b/gi, 'под ручным контролем')
  .replace(/inside_localos_policy/gi, 'внутри правил LocalOS')
  .replace(/localos_managed_защищенный контур/gi, 'под управлением LocalOS')
  .replace(/localos_managed_boundary/gi, 'под управлением LocalOS')
  .replace(/approval_required/gi, 'требует ручного подтверждения')
  .replace(/проверка перед запуском_only/gi, 'только проверка перед запуском')
  .replace(/preflight_only/gi, 'только проверка перед запуском')
  .replace(/\bavailable\b/gi, 'доступно')
  .replace(/\bpending\b/gi, 'ожидает решения')
  .replace(/\bunknown\b/gi, 'неизвестно')
  .replace(/localos_envelope/g, 'правила LocalOS')
  .replace(/openclaw_action_orchestrator/g, 'контур выполнения LocalOS')
  .replace(/_/g, ' ')
  .replace(/защищенный способ LocalOS защищенный контур/gi, 'защищенный способ LocalOS')
  .replace(/защищенный способ LocalOS внутри правил LocalOS/gi, 'внутри правил LocalOS')
  .replace(/Использовать защищенный способ LocalOS защищенный контур/gi, 'Использовать защищенный способ LocalOS');

const agentFlowStatusLabel = (status?: string) => ({
  ready: 'можно включить',
  draft: 'черновик',
  needs_connection: 'нужно проверить подключения',
  needs_connections: 'нужно проверить подключения',
  needs_connection_choice: 'нужно выбрать подключение',
  ready_for_draft: 'готов к черновику',
  ready_for_preview: 'готов к тесту',
  ready_for_activation: 'готов к включению',
}[String(status || '')] || humanizeMeta(status || 'проверить'));

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

const autoSelectBuilderProviderRoutes = (preview?: AgentBuilderPreview | null): Record<string, string> => {
  const selected: Record<string, string> = {};
  const select = (key?: string, route?: AgentProviderRoute | null) => {
    const bindingKey = String(key || '').trim();
    const provider = String(route?.provider || '').trim();
    if (!bindingKey || !provider || !builderRouteIsUsable(route)) {
      return;
    }
    selected[bindingKey] = provider;
  };
  (preview?.connection_readiness?.services || []).forEach((service) => {
    select(service.key, service.recommended_route || null);
  });
  (preview?.connection_plan?.items || []).forEach((item) => {
    select(item.key, item.recommended_route || null);
  });
  return selected;
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
  provider_route_openclaw: 'защищенный способ LocalOS',
  provider_route_maton: 'Maton.ai',
  provider_route_manual: 'ручной режим',
  provider_route_openclaw_boundary: 'защищенный способ LocalOS',
  provider_route_maton_external_account: 'Maton.ai',
  compiled_default: 'настройка агента',
  input_payload: 'данные запуска',
  missing_integration: 'нужен доступ',
}[binding.resolution || ''] || humanizeMeta(binding.resolution || binding.provider));

const bindingUserFacingRole = (binding: AgentIntegrationBindingStatus) => {
  const direction = String(binding.direction || '').trim();
  const capability = String(binding.capability || '').trim();
  const trigger = String(binding.trigger || '').trim();
  if (binding.provider === 'google_sheets') {
    if (capability === 'google_sheets.read_rows' || direction === 'external_read') {
      return 'Источник данных: чтение строк из Google Sheets';
    }
    if (capability === 'sheets.append_row_request' || direction === 'external_write') {
      return 'Канал результата: подготовить запись в Google Sheets';
    }
    return 'Источник данных или канал результата: Google Sheets';
  }
  if (binding.provider === 'browser_use') {
    return 'Источник данных: чтение сайта через защищенный способ LocalOS';
  }
  if (binding.provider === 'telegram') {
    if (direction === 'trigger' || trigger) {
      return 'Событие запуска: сообщение или событие в Telegram';
    }
    return 'Канал результата: Telegram';
  }
  if (binding.provider === 'whatsapp') {
    if (direction === 'trigger' || trigger) {
      return 'Событие запуска: сообщение или вопрос клиента в WhatsApp';
    }
    return 'Канал результата: WhatsApp';
  }
  if (binding.provider === 'maton') {
    return 'Канал результата: Maton.ai';
  }
  if (binding.provider === 'localos_finance') {
    return 'Результат внутри LocalOS: финансы';
  }
  return humanizeMeta(binding.key || binding.trigger || binding.capability || binding.direction || binding.provider);
};

const bindingActionHint = (binding: AgentIntegrationBindingStatus) => {
  if (binding.status === 'connected' || binding.status === 'ready') {
    return `${connectorLabel(binding.provider)} готово: ${bindingResolutionLabel(binding)}.`;
  }
  if (binding.provider === 'google_sheets') {
    return 'Выберите существующий Google-доступ или укажите таблицу и лист ниже.';
  }
  if (binding.provider === 'browser_use') {
    return 'Укажите сайт для проверки. Чтение выполняется через OpenClaw boundary внутри правил LocalOS.';
  }
  if (binding.provider === 'telegram') {
    return 'Выберите режим бота ниже, чтобы агент мог принимать события Telegram.';
  }
  if (binding.provider === 'whatsapp') {
    return 'Выберите режим WhatsApp ниже, чтобы агент мог учитывать вопросы клиентов или готовить сообщения.';
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
  if (provider === 'browser_use') {
    const rawUrls = Array.isArray(data.target_urls) ? data.target_urls : [data.target_url || data.url].filter(Boolean);
    return rawUrls
      .map((item) => String(item || '').trim())
      .filter(Boolean)
      .slice(0, 3)
      .map((item) => `сайт: ${item}`);
  }
  if (provider === 'telegram') {
    return [
      String(data.telegram_target || data.chat_id || '').trim() ? `канал: ${String(data.telegram_target || data.chat_id).trim()}` : '',
      String(data.target_type || '').trim() ? userFacingAgentTechText(humanizeMeta(String(data.target_type).trim())) : '',
    ].filter(Boolean);
  }
  if (provider === 'whatsapp') {
    return [
      String(data.whatsapp_target || data.phone_id || data.channel_mode || '').trim() ? `канал: ${String(data.whatsapp_target || data.phone_id || data.channel_mode).trim()}` : '',
      String(data.target_type || '').trim() ? userFacingAgentTechText(humanizeMeta(String(data.target_type).trim())) : '',
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
      description: userFacingAgentTechText(nextPlanItem.route_summary || nextPlanItem.explanation || `${routeAction}. После этого LocalOS разрешит тест без отправки.`),
      action: 'configure',
      cta: userFacingAgentTechText(nextPlanItem.primary_label || routeAction || 'Настроить доступ'),
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
      description: 'Запустите тест без отправки: LocalOS проверит доступы, лимиты и ручные подтверждения без внешней публикации.',
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
  previewIsStale,
}: {
  preview: AgentBuilderPreview | null;
  questions: AgentBuilderQuestion[];
  missingConnectionChoices: Array<AgentConnectionSummary['items'] extends Array<infer Item> ? Item : never>;
  missingProviderRouteKeys: string[];
  missingProviderRouteConfirmation: boolean;
  canCreateDraft: boolean;
  createDraftLabel: string;
  previewIsStale?: boolean;
}): AgentConnectionDecision => {
  const forbidden = preview?.connection_summary?.forbidden || [];
  const unsupported = preview?.connection_summary?.unsupported || [];
  if (previewIsStale) {
    return {
      tone: 'needs_action',
      title: 'Обновите понимание',
      description: 'Вы изменили запрос. Нажмите «Обновить понимание», чтобы LocalOS пересобрал сводку именно по этому тексту.',
      action: 'none',
      cta: 'Обновить понимание',
    };
  }
  if (forbidden.length || unsupported.length) {
    const reason = forbidden[0]?.reason || unsupported[0]?.reason || 'Такой способ подключения не разрешён правилами безопасности LocalOS.';
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
      description: blockingQuestions[0]?.question || 'LocalOS нужно больше деталей, чтобы собрать проверенную логику без догадок.',
      action: 'answer',
      cta: 'Отправить ответ',
    };
  }
  if (missingConnectionChoices.length) {
    const title = missingConnectionChoices[0]?.title || connectorLabel(missingConnectionChoices[0]?.provider);
    return {
      tone: 'choice',
      title: `Выберите подключение ${title}`,
      description: 'У бизнеса уже есть несколько подходящих подключений. Выберите, какое использовать для этого агента.',
      action: 'choose',
      cta: 'Выбрать ниже',
      bindingKey: missingConnectionChoices[0]?.key || '',
    };
  }
  if (missingProviderRouteKeys.length) {
    return {
      tone: 'choice',
      title: 'Выберите способ доставки',
      description: `LocalOS нашёл безопасный вариант, но нужно выбрать способ для: ${missingProviderRouteKeys.map((item) => userFacingAgentTechText(humanizeMeta(item))).join(', ')}.`,
      action: 'choose',
      cta: 'Выбрать ниже',
      bindingKey: missingProviderRouteKeys[0] || '',
    };
  }
  if (missingProviderRouteConfirmation) {
    return {
      tone: 'choice',
      title: 'Подтвердите способы подключения',
      description: 'LocalOS сохранит выбранные способы подключения и будет проверять доступы, лимиты и ручные подтверждения перед запуском.',
      action: 'choose',
      cta: 'Подтвердить ниже',
    };
  }
  if (canCreateDraft) {
    return {
      tone: preview?.setup_flow?.post_create_status === 'ready_for_preview' ? 'ready' : 'choice',
      title: preview?.setup_flow?.post_create_status === 'ready_for_preview'
        ? 'Можно создать черновик и проверить'
        : 'Можно создать черновик и подключить сервисы',
      description: userFacingAgentTechText(preview?.setup_flow?.post_create_description || preview?.setup_flow?.next_step_description || 'LocalOS сохранит проверяемую логику агента и откроет следующий безопасный шаг.'),
      action: 'create',
      cta: createDraftLabel,
    };
  }
  return {
    tone: 'pending',
    title: preview?.setup_flow?.next_step_title || 'Завершите настройку',
    description: preview?.setup_flow?.next_step_description || 'LocalOS покажет следующий шаг после уточнения задачи и проверки способов подключения.',
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
      title: 'Готовность к включению ещё не проверена',
      description: 'Создайте версию и запустите тест без отправки, чтобы LocalOS понял, можно ли включать агента.',
      action: 'none',
      cta: '',
    };
  }
  if (gate.can_activate) {
    return {
      tone: 'ready',
      title: 'Агента можно включить',
      description: userFacingAgentTechText(gate.summary) || 'Тест без отправки, доступы, лимиты и логика прошли проверку. Внешние действия останутся за ручным подтверждением.',
      action: 'activate',
      cta: gate.primary_action_label || 'Включить агента',
    };
  }
  if (gate.next_step === 'connect_required_integrations') {
    return {
      tone: 'needs_action',
      title: 'Нужно подключить сервисы',
      description: userFacingAgentTechText(gate.summary) || activationBlockerText(gate) || 'LocalOS понял нужные подключения, но без них нельзя пройти тест и включить агента.',
      action: 'connections',
      cta: gate.primary_action_label || 'Открыть подключения',
      bindingKey: gate.next_binding_key || '',
    };
  }
  if (gate.next_step === 'fix_compiled_workflow') {
    return {
      tone: 'blocked',
      title: 'Логику нужно исправить',
      description: userFacingAgentTechText(gate.summary) || activationBlockerText(gate) || 'Логика агента не прошла проверку. Исправьте версию перед запуском.',
      action: 'logic',
      cta: gate.primary_action_label || 'Открыть логику',
    };
  }
  if (gate.next_step === 'create_version') {
    return {
      tone: 'needs_action',
      title: 'Нужно создать версию',
      description: userFacingAgentTechText(gate.summary) || 'У агента ещё нет проверенной версии логики.',
      action: 'logic',
      cta: gate.primary_action_label || 'Создать версию',
    };
  }
  if (gate.next_step === 'run_preview') {
    return {
      tone: 'choice',
      title: 'Нужно проверить на примере',
      description: userFacingAgentTechText(gate.preview_run_status?.message || gate.summary) || 'Перед включением LocalOS должен выполнить тест без внешних действий.',
      action: 'preview',
      cta: gate.primary_action_label || 'Проверить на примере',
    };
  }
  if (gate.next_step === 'review_approvals') {
    return {
      tone: 'needs_action',
      title: 'Нужно проверить решение',
      description: userFacingAgentTechText(gate.summary) || activationBlockerText(gate) || 'Есть ручное решение, которое влияет на готовность агента.',
      action: 'results',
      cta: gate.primary_action_label || 'Открыть решения',
    };
  }
  return {
    tone: 'pending',
    title: 'Активация пока недоступна',
    description: userFacingAgentTechText(gate.summary) || activationBlockerText(gate) || 'Проверьте логику, подключения и тест без отправки.',
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
      key: 'task',
      label: 'Задача',
      detail: gate ? 'описана' : 'нужно описание',
      status: gate ? 'done' : 'pending',
    },
    {
      key: 'compiled',
      label: 'Логика',
      detail: compiledReady ? 'проверена' : 'нужно проверить',
      status: compiledReady ? 'done' : nextStep === 'fix_compiled_workflow' || nextStep === 'create_version' ? 'current' : 'pending',
    },
    {
      key: 'policy',
      label: 'Подтверждение',
      detail: policyReady ? 'правила готовы' : 'нужно настроить',
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
      label: 'Тест',
      detail: previewReady ? 'пройден' : 'нужен запуск',
      status: previewReady ? 'done' : nextStep === 'run_preview' ? 'current' : 'pending',
    },
    {
      key: 'activate',
      label: 'Включение',
      detail: canActivate ? 'можно включить' : 'после проверки',
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

const getLatestVersionId = (blueprint: AgentBlueprint, details?: AgentBlueprintDetails | null) => {
  if (typeof blueprint.latest_version_id === 'string' && blueprint.latest_version_id) {
    return blueprint.latest_version_id;
  }
  const versions = details?.versions || [];
  const sorted = [...versions].sort((a, b) => (getVersionNumber(b) || 0) - (getVersionNumber(a) || 0));
  const latest = sorted[0];
  return typeof latest?.id === 'string' ? latest.id : '';
};

const getRunnableVersionId = (blueprint: AgentBlueprint, details?: AgentBlueprintDetails | null) => (
  getActiveVersionId(blueprint, details) || getLatestVersionId(blueprint, details)
);

const agentExecutionMode = (blueprint: AgentBlueprint, details?: AgentBlueprintDetails | null): AgentExecutionMode => (
  details?.execution_mode || blueprint.execution_mode || 'manual'
);

const agentExecutionModeLabel = (mode: AgentExecutionMode) => ({
  one_off: 'Один раз',
  manual: 'По кнопке',
  scheduled: 'По расписанию',
}[mode]);

const agentNextRunLabel = (blueprint: AgentBlueprint, details?: AgentBlueprintDetails | null) => {
  const nextRunAt = details?.next_run_at || blueprint.next_run_at;
  if (nextRunAt) {
    return formatShortDate(nextRunAt);
  }
  const mode = agentExecutionMode(blueprint, details);
  if (mode === 'manual') {
    return 'После запуска';
  }
  if (mode === 'one_off') {
    return (details?.lifecycle_state || blueprint.lifecycle_state) === 'completed' ? 'Задача выполнена' : 'После подтверждения';
  }
  return 'После включения';
};

const businessResultPrimaryText = (result: Record<string, unknown>) => {
  const candidates = [result.draft_text, result.final_text, result.message_text, result.summary, result.title];
  const text = candidates.find((value) => typeof value === 'string' && value.trim());
  return typeof text === 'string' ? text : '';
};

const workflowStepsForAnimation = (
  details: AgentBlueprintDetails | null,
  kind: AgentRunAnimation['kind'],
) => {
  const version = details?.candidate_version || details?.active_version || details?.versions?.[0] || null;
  const rawSteps = recordValue(version)?.steps_json;
  const steps = Array.isArray(rawSteps) ? rawSteps : [];
  const labels: string[] = [];
  const add = (label: string) => {
    if (label && !labels.includes(label)) {
      labels.push(label);
    }
  };
  steps.forEach((rawStep) => {
    const step = recordValue(rawStep);
    if (!step) {
      return;
    }
    const key = String(step.key || step.id || '').toLowerCase();
    const capability = String(step.capability || step.capability_key || '').toLowerCase();
    const title = String(step.title || step.label || '').trim();
    const external = capability.includes('publish') || capability.includes('send') || capability.includes('dispatch');
    if (external) {
      return;
    }
    if (capability === 'google_sheets.read_rows' || key.includes('google_sheet')) {
      add('Открываю Google Таблицу');
      add('Читаю строки');
    } else if (key.includes('select') || key.includes('filter') || key.includes('find')) {
      add('Выбираю нужные данные');
    } else if (capability.includes('content_plan') || key.includes('content_plan')) {
      add(kind === 'test' ? 'Проверяю сохранение результата' : 'Сохраняю результат');
    } else if (key.includes('draft') || key.includes('prepare') || key.includes('generate')) {
      add('Готовлю черновик');
    } else if (title) {
      add(userFacingAgentTechText(title));
    }
  });
  if (!labels.length) {
    add('Проверяю исходные данные');
    add('Выполняю задачу');
    add('Готовлю результат');
  }
  add(kind === 'test' ? 'Проверяю готовый результат' : 'Сохраняю результат');
  return labels.slice(0, 5);
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
  'Каждый день собирай короткий отчёт по отзывам, новостям, услугам, партнёрствам и финансам и присылай владельцу в Telegram',
  'Если появился новый негативный отзыв, подготовь короткий ответ в стиле компании и пришли черновик владельцу в Telegram',
  'Раз в неделю подготовь 3 новости для карточек на основе услуг, отзывов, сезонности и текущих задач',
  'Проверь услуги: слабые названия, пустые описания, дубли и SEO-ключи. Подготовь список правок для проверки',
  'Найди или возьми из списка потенциальных партнёров, отсей нерелевантных и подготовь первое письмо и конкретное предложение',
  'Открывай сайт конкурента, проверяй изменения в ценах, акциях или меню и готовь короткий отчёт владельцу в Telegram',
  'Проверяй Google Sheets с заявками или заказами и присылай новые строки ответственному в Telegram',
  'Собирай повторяющиеся вопросы клиентов из WhatsApp и Telegram, группируй их и предлагай новые ответы для FAQ',
  'Читай таблицу расходов, нормализуй категории и подготовь предложения для Финансов LocalOS',
  'Каждый вечер проверяй записи на завтра: кто без предоплаты, где есть риск отмены и кому нужен ручной follow-up',
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
  business_cards: 'карточки',
  photos: 'фотографии',
  competitors: 'конкуренты',
  clients: 'клиенты',
  locations: 'точки сети',
  customer_questions: 'вопросы клиентов',
  customer_messages: 'сообщения клиентов',
  localos_tasks: 'задачи LocalOS',
  team: 'команда',
  whatsapp: 'WhatsApp',
  seasonality: 'сезонность',
  posts: 'посты',
  schedule: 'расписание',
  inventory: 'остатки',
  products: 'товары',
  supplies: 'расходники',
  staff_schedule: 'расписание смен',
  customer_chats: 'чаты с клиентами',
  staff_profiles: 'профили сотрудников',
  price_list: 'прайс',
  revenue: 'выручка',
  map_questions: 'вопросы в карточках',
  location_descriptions: 'описания филиалов',
  localos_digest: 'дайджест LocalOS',
  prospectingleads: 'кандидаты',
  outreach_drafts: 'черновики сообщений партнёрам',
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
  post_text: 'Текст поста',
  draft_text: 'Черновик сообщения',
  message: 'Сообщение',
  text: 'Текст',
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
  preparation_method: 'Как подготовлено',
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

const approvalActionLabels = (approval?: AgentApproval | null) => {
  const approvalType = approval?.approval_type || '';
  if (approvalType === 'external_delivery' || approvalType === 'send_batch') {
    return {
      approve: 'Подтвердить отправку',
      reject: 'Не отправлять',
    };
  }
  if (approvalType === 'final_output') {
    return {
      approve: 'Разрешить выполнение',
      reject: 'Не использовать',
    };
  }
  if (approvalType === 'shortlist') {
    return {
      approve: 'Утвердить список',
      reject: 'Отклонить список',
    };
  }
  if (approvalType === 'drafts') {
    return {
      approve: 'Подтвердить публикацию',
      reject: 'Отклонить результат',
    };
  }
  return {
    approve: 'Разрешить выполнение',
    reject: 'Не использовать',
  };
};

const getApprovalPreviewItems = (approval?: AgentApproval | null) => {
  const payload = approval?.payload_json || {};
  const items: Array<{ label: string; value: string }> = [];
  const addValue = (label: string, value: unknown) => {
    const text = userFacingAgentTechText(formatPayloadValue(value)).trim();
    if (text && !items.some((item) => item.label === label && item.value === text)) {
      items.push({ label, value: text });
    }
  };
  const preparedResult = extractBusinessResultPayload(payload);
  addValue('Что подготовил агент', payload.summary || payload.result_summary || payload.output_summary || payload.message_summary || payload.title);
  addValue('Черновик / результат', payload.draft_text || payload.reply || payload.message || payload.text || payload.output || preparedResult || payload.result);
  addValue('Что будет дальше', payload.next_step || payload.action || payload.delivery_state || payload.publish_state);
  if (Array.isArray(payload.reply_drafts) && payload.reply_drafts.length) {
    addValue('Черновики ответов', payload.reply_drafts);
  }
  if (Array.isArray(payload.drafts) && payload.drafts.length) {
    addValue('Черновики', payload.drafts);
  }
  if (Array.isArray(payload.items) && payload.items.length) {
    addValue('Элементы', payload.items);
  }
  if (Array.isArray(payload.manual_review_reasons) && payload.manual_review_reasons.length) {
    addValue('Почему нужна проверка', payload.manual_review_reasons);
  }
  return items.slice(0, 4);
};

const approvalDecisionTitle = (approval?: AgentApproval | null) => {
  const approvalType = approval?.approval_type || '';
  if (approvalType === 'external_delivery' || approvalType === 'send_batch') {
    return 'Разрешить внешнюю отправку?';
  }
  if (approvalType === 'final_output') {
    return 'Можно использовать подготовленный результат?';
  }
  if (approvalType === 'shortlist') {
    return 'Утвердить список для дальнейшей работы?';
  }
  if (approvalType === 'drafts') {
    return 'Утвердить черновики?';
  }
  return 'Можно использовать текущий результат агента?';
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

const isWithinLastDay = (value?: string | null) => {
  if (!value) {
    return false;
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return false;
  }
  return Date.now() - date.getTime() <= 24 * 60 * 60 * 1000;
};

const buildTodaySummary = (
  blueprints: AgentBlueprint[],
  detailsById: Record<string, AgentBlueprintDetails>,
): AgentTodaySummary => {
  const detailValues = Object.values(detailsById);
  const runs = detailValues.flatMap((details) => details.runs || []);
  const todayRuns = runs.filter((run) => run.status !== 'superseded' && isWithinLastDay(run.completed_at || run.started_at));
  const todayApprovals = detailValues
    .flatMap((details) => details.approval_queue || [])
    .filter((approval) => isWithinLastDay(approval.requested_at || approval.run_started_at) && !isBusinessBlockerApproval(approval));
  const artifacts = detailValues.flatMap((details) => {
    const recentRuns = (details.runs || []).filter((run) => run.status !== 'superseded' && isWithinLastDay(run.completed_at || run.started_at));
    return recentRuns.flatMap((run) => run.artifacts || []);
  });
  const listFallbackRuns = blueprints.filter((blueprint) => isWithinLastDay(blueprint.last_run_completed_at || blueprint.last_run_started_at));
  const completedRuns = todayRuns.filter((run) => run.status === 'completed').length || listFallbackRuns.filter((item) => item.last_run_status === 'completed').length;
  const failedRuns = todayRuns.filter((run) => run.status === 'failed').length || listFallbackRuns.filter((item) => item.last_run_status === 'failed').length;
  const preparedArtifacts = artifacts.length || todayRuns.reduce((sum, run) => sum + Number(run.observability?.artifacts?.count || 0), 0);
  const pendingApprovals = todayApprovals.length;
  const latestEvent = todayRuns[0]?.completed_at || todayRuns[0]?.started_at || listFallbackRuns[0]?.last_run_completed_at || listFallbackRuns[0]?.last_run_started_at || '';
  return {
    completedRuns,
    preparedArtifacts,
    pendingApprovals,
    failedRuns,
    latestEvent: latestEvent ? formatShortDate(latestEvent) : '',
    empty: completedRuns + preparedArtifacts + pendingApprovals + failedRuns === 0,
  };
};

const buildAgentBusinessStatus = (
  blueprint: AgentBlueprint,
  details?: AgentBlueprintDetails | null,
): AgentBusinessStatus => {
  const activationGate = details?.activation_gate;
  const missingConnections = Number(activationGate?.preflight?.missing_count || 0);
  const previewReady = activationGate?.preview_run_status?.ready === true;
  const hasActiveVersion = Boolean(details?.active_version_id || blueprint.active_version_id || blueprint.active_version_number);
  const latestResult = findPreparedResultPayload(details?.runs?.[0] || null);
  if (isBusinessBlockerPayload(latestResult)) {
    return {
      status: 'needs_check',
      label: 'Нужно проверить',
      tone: 'warning',
      primaryLabel: resultPayloadStatus(latestResult) === 'needs_google_access' ? 'Починить Google' : 'Посмотреть',
      lastResult: 'Последний результат требует следующего шага',
      nextRun: 'после исправления',
    };
  }
  if (Number(blueprint.pending_approvals_count || 0) > 0 || blueprint.last_run_status === 'waiting_approval') {
    return {
      status: 'needs_approval',
      label: 'Ждёт решения',
      tone: 'warning',
      primaryLabel: 'Посмотреть',
      lastResult: 'Есть задача на ручное решение',
      nextRun: 'после решения',
    };
  }
  if (blueprint.last_run_status === 'failed' || blueprint.status === 'error') {
    return {
      status: 'error',
      label: 'Ошибка',
      tone: 'error',
      primaryLabel: 'Открыть результат',
      lastResult: 'Последний запуск завершился ошибкой',
      nextRun: 'после проверки',
    };
  }
  if (missingConnections > 0) {
    return {
      status: 'needs_connection',
      label: 'Нужны данные',
      tone: 'warning',
      primaryLabel: 'Подключить',
      lastResult: `${missingConnections} ${missingConnections === 1 ? 'доступ требует' : 'доступа требуют'} внимания`,
      nextRun: 'после подключения',
    };
  }
  if (!previewReady && hasActiveVersion) {
    return {
      status: 'needs_check',
      label: 'Нужно проверить',
      tone: 'warning',
      primaryLabel: 'Проверить',
      lastResult: formatLastRun(blueprint),
      nextRun: 'после теста',
    };
  }
  if (blueprint.status === 'draft' && !hasActiveVersion) {
    return {
      status: 'draft',
      label: 'Черновик',
      tone: 'draft',
      primaryLabel: 'Открыть',
      lastResult: 'Рабочая версия ещё не включена',
      nextRun: 'после включения',
    };
  }
  return {
    status: 'active',
    label: 'Работает',
    tone: 'ready',
    primaryLabel: 'Проверить',
    lastResult: formatLastRun(blueprint),
    nextRun: blueprint.active_version_number ? 'по сценарию агента' : 'после проверки',
  };
};

const buildEmployeeDescription = (
  blueprint: AgentBlueprint,
  details?: AgentBlueprintDetails | null,
) => {
  const preview = getBlueprintBuilderPreview(details?.blueprint || blueprint);
  return preview?.understood_task
    || blueprint.description
    || blueprint.active_goal
    || blueprint.latest_goal
    || 'Выполняет поручение, которое вы описали при создании.';
};

const buildEmployeeStatus = (
  blueprint: AgentBlueprint,
  details?: AgentBlueprintDetails | null,
  pendingApproval?: AgentApproval | null,
): EmployeeStatus => {
  const workspaceState = buildEmployeeWorkspaceState(blueprint, details, pendingApproval);
  if (workspaceState === 'blocked_result') {
    return {
      label: 'Нужно проверить',
      tone: 'amber',
      summary: 'Сотрудник не получил данные из источника. Нужно исправить доступ или запустить тест заново.',
    };
  }
  if (workspaceState === 'waiting_for_review') {
    return {
      label: 'Ждёт решения',
      tone: 'amber',
      summary: 'Сотрудник подготовил результат и остановился, чтобы вы его проверили.',
    };
  }
  if (workspaceState === 'error') {
    return {
      label: 'Ошибка',
      tone: 'rose',
      summary: 'Последняя работа остановилась. Нужна проверка результата.',
    };
  }
  if (workspaceState === 'needs_connection') {
    const missingConnections = Number(details?.activation_gate?.preflight?.missing_count || 0);
    return {
      label: 'Нужны данные',
      tone: 'amber',
      summary: `${missingConnections || 1} ${missingConnections === 1 ? 'подключение нужно завершить' : 'подключения нужно завершить'}.`,
    };
  }
  if (workspaceState === 'needs_mode') {
    return {
      label: 'Нужно проверить',
      tone: 'amber',
      summary: 'Выберите, как должен запускаться агент: один раз, по кнопке или по расписанию.',
    };
  }
  if (workspaceState === 'completed') {
    return {
      label: 'Выполнено',
      tone: 'emerald',
      summary: 'Разовая задача выполнена. Результат сохранён в истории.',
    };
  }
  if (workspaceState === 'draft') {
    return {
      label: 'Черновик',
      tone: 'slate',
      summary: 'Сотрудник создан, но ещё не включён в работу.',
    };
  }
  if (workspaceState === 'ready_for_test' || workspaceState === 'needs_attention') {
    return {
      label: 'Нужно проверить',
      tone: 'amber',
      summary: 'Перед включением нужен безопасный тест без внешних действий.',
    };
  }
  if (workspaceState === 'running_test') {
    return {
      label: 'Нужно проверить',
      tone: 'amber',
      summary: 'Сотрудник выполняет тестовую проверку.',
    };
  }
  return {
    label: 'Работает',
    tone: 'emerald',
    summary: 'Сотрудник готов работать по опубликованному сценарию.',
  };
};

const buildEmployeeWorkspaceState = (
  blueprint: AgentBlueprint,
  details?: AgentBlueprintDetails | null,
  pendingApproval?: AgentApproval | null,
): EmployeeWorkspaceState => {
  if (details?.execution_mode_confirmation_required || blueprint.execution_mode_confirmation_required) {
    return 'needs_mode';
  }
  if ((details?.lifecycle_state || blueprint.lifecycle_state) === 'completed') {
    return 'completed';
  }
  const gate = details?.activation_gate;
  const missingConnections = Number(gate?.preflight?.missing_count || 0);
  const hasActiveVersion = Boolean(details?.active_version_id || blueprint.active_version_id || blueprint.active_version_number);
  const hasCandidateVersion = Boolean(details?.candidate_version_id || blueprint.latest_version_id || blueprint.latest_version_number);
  const latestRun = details?.runs?.[0] || null;
  const latestResult = findPreparedResultPayload(latestRun, pendingApproval);
  if (isBusinessBlockerPayload(latestResult)) {
    return 'blocked_result';
  }
  const hasPendingApproval = Boolean(pendingApproval || blueprint.pending_approvals_count || blueprint.last_run_status === 'waiting_approval');
  if (hasPendingApproval) {
    return 'waiting_for_review';
  }
  if (blueprint.last_run_status === 'running') {
    return 'running_test';
  }
  if (blueprint.last_run_status === 'failed' || blueprint.status === 'error') {
    return 'error';
  }
  if (missingConnections > 0) {
    return 'needs_connection';
  }
  if (gate?.preview_run_status?.ready === false) {
    return 'ready_for_test';
  }
  if (!hasActiveVersion && hasCandidateVersion && (gate?.can_activate === true || gate?.next_step === 'configure_schedule')) {
    return 'needs_attention';
  }
  if (!hasActiveVersion || blueprint.status === 'draft') {
    return 'draft';
  }
  return 'working';
};

const buildEmployeeLastActivity = (
  blueprint: AgentBlueprint,
  details?: AgentBlueprintDetails | null,
  pendingApproval?: AgentApproval | null,
) => {
  const latestRun = details?.runs?.[0];
  if (latestRun) {
    const time = formatShortDate(latestRun.completed_at || latestRun.started_at);
    if (isBusinessBlockerPayload(findPreparedResultPayload(latestRun, pendingApproval))) {
      return `Остановился: нужен следующий шаг${time ? ` · ${time}` : ''}`;
    }
    if (latestRun.status === 'completed') {
      return `Завершил работу${time ? ` · ${time}` : ''}`;
    }
    if (latestRun.status === 'waiting_approval') {
      return `Подготовил результат и ждёт решения${time ? ` · ${time}` : ''}`;
    }
    if (latestRun.status === 'failed') {
      return `Остановился с ошибкой${time ? ` · ${time}` : ''}`;
    }
    return `${humanizeStatus(latestRun.status)}${time ? ` · ${time}` : ''}`;
  }
  return formatLastRun(blueprint);
};

const buildEmployeeNextAction = ({
  blueprint,
  details,
  pendingApproval,
  googleAccessFreshAfterResult = false,
}: {
  blueprint: AgentBlueprint;
  details?: AgentBlueprintDetails | null;
  pendingApproval?: AgentApproval | null;
  googleAccessFreshAfterResult?: boolean;
}): EmployeeNextAction => {
  return buildEmployeePrimaryAction({ blueprint, details, pendingApproval, googleAccessFreshAfterResult });
};

const getMissingConnectorLabel = (
  details?: AgentBlueprintDetails | null,
) => {
  const gate = details?.activation_gate;
  const missing = gate?.preflight?.missing?.[0] || gate?.preflight?.items?.find((item) => item.status !== 'ready' && item.status !== 'connected');
  const provider = missing?.provider || gate?.connection_plan?.items?.find((item) => item.binding_status !== 'ready')?.provider || '';
  return connectorLabel(provider || 'service');
};

const buildEmployeePrimaryAction = ({
  blueprint,
  details,
  pendingApproval,
  googleAccessFreshAfterResult = false,
}: {
  blueprint: AgentBlueprint;
  details?: AgentBlueprintDetails | null;
  pendingApproval?: AgentApproval | null;
  googleAccessFreshAfterResult?: boolean;
}): EmployeeNextAction => {
  const state = buildEmployeeWorkspaceState(blueprint, details, pendingApproval);
  const gate = details?.activation_gate;
  const activationVersionId = gate?.active_version_id || details?.active_version_id || blueprint.active_version_id || '';
  const latestResult = findPreparedResultPayload(details?.runs?.[0] || null, pendingApproval);
  const userMode = buildAgentUserMode(blueprint, details);
  if (state === 'needs_mode') {
    return {
      kind: 'confirm_mode',
      label: 'Выбрать тип запуска',
      description: 'Подтвердите, будет это разовая задача, запуск по кнопке или работа по расписанию.',
      targetMode: 'settings',
    };
  }
  if (state === 'completed') {
    return {
      kind: 'run_similar',
      label: 'Запустить похожую',
      description: 'Создайте новую разовую задачу с теми же источниками и правилами.',
      targetMode: 'overview',
    };
  }
  if (state === 'blocked_result') {
    if (resultPayloadStatus(latestResult) === 'needs_google_access') {
      if (googleAccessFreshAfterResult) {
        return {
          kind: 'run_test',
          label: 'Запустить тест',
          description: 'Google-доступ обновлён. Запустите тест ещё раз, чтобы проверить таблицу на свежем доступе.',
          targetMode: 'results',
        };
      }
      return {
        kind: 'open_result',
        label: 'Починить Google-доступ',
        description: 'Google не дал строки таблицы. Откройте результат, переподключите доступ или запустите тест после подключения.',
        targetMode: 'results',
      };
    }
    if (resultPayloadStatus(latestResult) === 'needs_sheet_tab') {
      return {
        kind: 'open_result',
        label: 'Указать лист таблицы',
        description: 'Google-доступ работает, но лист таблицы не найден. Откройте результат и укажите правильный лист.',
        targetMode: 'results',
      };
    }
    return {
      kind: 'open_result',
      label: 'Разобрать результат',
      description: 'Сотрудник остановился до готового результата. Откройте причину и исправьте следующий шаг.',
      targetMode: 'results',
    };
  }
  if (state === 'waiting_for_review') {
    return {
      kind: 'approve',
      label: approvalActionLabels(pendingApproval).approve,
      description: 'Проверьте подготовленный результат и решите, можно ли использовать его дальше.',
      targetMode: 'results',
    };
  }
  if (state === 'needs_connection') {
    const label = getMissingConnectorLabel(details);
    return {
      kind: 'connect',
      label: `Подключить ${label}`,
      description: 'Завершите одно недостающее подключение, чтобы сотрудник получил нужные данные.',
      targetMode: 'connections',
    };
  }
  if (state === 'error') {
    return {
      kind: 'open_result',
      label: 'Разобрать проблему',
      description: 'Посмотрите последний бизнес-результат и причину остановки.',
      targetMode: 'results',
    };
  }
  if (state === 'draft' || state === 'ready_for_test') {
    if (latestResult || blueprint.last_run_status === 'completed' || details?.runs?.[0]?.status === 'completed') {
      return {
        kind: 'open_result',
        label: 'Открыть последний результат',
        description: 'Откройте последний подготовленный результат сотрудника.',
        targetMode: 'results',
      };
    }
    return {
      kind: 'run_test',
      label: 'Запустить тест',
      description: 'Запустите безопасную проверку без публикаций и внешних отправок.',
      targetMode: 'results',
    };
  }
  if (state === 'running_test') {
    return {
      kind: 'view_history',
      label: 'Проверка идёт',
      description: 'Сотрудник выполняет тест. Дождитесь результата.',
      targetMode: 'results',
    };
  }
  if (state === 'needs_attention' && activationVersionId) {
    if (userMode.mode === 'one_off') {
      return {
        kind: 'run_work',
        label: 'Выполнить задачу',
        description: 'Тест пройден. Выполните задачу и сохраните рабочий результат.',
        targetMode: 'results',
        versionId: activationVersionId,
      };
    }
    if (gate?.next_step === 'configure_schedule') {
      return {
        kind: 'configure_schedule',
        label: 'Настроить расписание',
        description: 'Укажите время и часовой пояс, затем включите агента.',
        targetMode: 'advanced',
        versionId: activationVersionId,
      };
    }
    return {
      kind: 'enable',
      label: userMode.mode === 'scheduled' ? 'Включить по расписанию' : 'Включить агента',
      description: 'Включите сотрудника после успешной проверки результата.',
      targetMode: 'overview',
      versionId: activationVersionId,
    };
  }
  if (state === 'working' && userMode.mode === 'manual') {
    return {
      kind: 'run_work',
      label: 'Запустить работу',
      description: 'Агент выполнит опубликованный сценарий и сохранит новый результат.',
      targetMode: 'results',
      versionId: details?.active_version_id || blueprint.active_version_id || '',
    };
  }
  return {
    kind: 'view_history',
    label: 'Открыть последний результат',
    description: 'Сотрудник работает. Можно открыть последний сохранённый результат.',
    targetMode: 'results',
  };
};

const pushUniqueResponsibility = (
  items: EmployeeResponsibility[],
  label: string,
  done = true,
) => {
  const normalized = label.trim();
  if (!normalized || items.some((item) => item.label.toLowerCase() === normalized.toLowerCase())) {
    return;
  }
  items.push({
    key: `${items.length}-${normalized.toLowerCase().replace(/[^a-zа-я0-9]+/gi, '-')}`,
    label: normalized,
    done,
  });
};

const buildEmployeeResponsibilities = (
  blueprint: AgentBlueprint,
  details?: AgentBlueprintDetails | null,
): EmployeeResponsibility[] => {
  const preview = getBlueprintBuilderPreview(details?.blueprint || blueprint);
  const text = [
    blueprint.name,
    blueprint.category,
    blueprint.description,
    blueprint.active_goal,
    blueprint.latest_goal,
    preview?.understood_task,
    ...(preview?.data_sources || []),
  ].filter(Boolean).join(' ').toLowerCase();
  const items: EmployeeResponsibility[] = [];
  if (text.includes('google sheet') || text.includes('таблиц')) {
    pushUniqueResponsibility(items, 'Прочитать Google-таблицу');
  }
  if (text.includes('telegram')) {
    pushUniqueResponsibility(items, 'Подготовить сообщение в Telegram');
  }
  if (text.includes('whatsapp')) {
    pushUniqueResponsibility(items, 'Разобрать вопросы из WhatsApp');
  }
  if (text.includes('поезд') || text.includes('trip') || text.includes('заказ')) {
    pushUniqueResponsibility(items, text.includes('поезд') || text.includes('trip') ? 'Найти нужную поездку' : 'Найти новые заказы');
  }
  if (blueprint.category === 'reviews' || text.includes('отзыв')) {
    pushUniqueResponsibility(items, 'Подготовить черновик ответа на отзыв');
  }
  if (blueprint.category === 'outreach' || text.includes('партн')) {
    pushUniqueResponsibility(items, 'Подготовить список и черновик сообщения');
  }
  if (blueprint.category === 'tables') {
    pushUniqueResponsibility(items, 'Сохранить данные в таблицу');
  }
  pushUniqueResponsibility(items, 'Подготовить результат для проверки владельцем');
  pushUniqueResponsibility(items, 'Остановиться перед внешним действием');
  return items.slice(0, 5);
};

const buildEmployeeWorkspaceStory = (
  blueprint: AgentBlueprint,
  details?: AgentBlueprintDetails | null,
  pendingApproval?: AgentApproval | null,
) => {
  const state = buildEmployeeWorkspaceState(blueprint, details, pendingApproval);
  const status = buildEmployeeStatus(blueprint, details, pendingApproval);
  const attention = buildEmployeeAttentionItems(blueprint, details, pendingApproval);
  const userMode = buildAgentUserMode(blueprint, details);
  return {
    state,
    status,
    responsibilities: buildEmployeeResponsibilities(blueprint, details),
    latestWork: buildEmployeeLastActivity(blueprint, details, pendingApproval),
    nextWork: userMode.mode === 'scheduled'
      ? blueprint.status === 'active'
        ? (details?.next_run_at || blueprint.next_run_at)
          ? `Следующий запуск: ${formatShortDate(details?.next_run_at || blueprint.next_run_at)}`
          : 'Расписание включено, время следующего запуска уточняется'
        : 'После теста, настройки времени и включения'
      : userMode.mode === 'one_off'
        ? 'Задача завершится после выполнения'
        : blueprint.status === 'active' ? 'Когда вы нажмёте «Запустить работу»' : 'После теста и включения',
    attention,
  };
};

const buildAgentUserMode = (
  blueprint: AgentBlueprint,
  details?: AgentBlueprintDetails | null,
) => {
  const preview = getBlueprintBuilderPreview(details?.blueprint || blueprint);
  const explicitMode = details?.execution_mode || blueprint.execution_mode;
  const trigger = String(preview?.trigger || '').trim();
  const mode = explicitMode || (trigger.includes('schedule') ? 'scheduled' : 'manual');
  if (mode === 'one_off') {
    return {
      mode,
      label: 'Разовая задача',
      flow: 'Запрос → выполнение → результат',
      description: 'После результата задача считается завершённой.',
    };
  }
  if (mode === 'scheduled') {
    return {
      mode,
      label: 'По расписанию',
      flow: 'Описание → тест → включение → расписание',
      description: 'Сотрудник запускается в указанное время. Внешние действия по-прежнему требуют подтверждения.',
    };
  }
  return {
    mode: 'manual',
    label: 'Запуск по кнопке',
    flow: 'Описание → тест → включение → запуск',
    description: 'Сотрудник выполняет задачу только когда вы нажимаете кнопку запуска.',
  };
};

const buildReasonCard = (
  state: EmployeeWorkspaceState,
  pendingApproval?: AgentApproval | null,
) => {
  if (state === 'blocked_result') {
    return {
      title: 'Почему нельзя подтвердить результат',
      description: 'Сотрудник не получил нужные данные, поэтому подтверждать нечего. Сначала исправьте доступ или запустите тест заново.',
    };
  }
  if (state === 'waiting_for_review') {
    return {
      title: 'Почему сейчас требуется решение',
      description: pendingApproval
        ? explainApproval(pendingApproval)
        : 'Сотрудник остановился, потому что следующий шаг требует решения владельца.',
    };
  }
  if (state === 'needs_connection') {
    return {
      title: 'Почему работа не началась',
      description: 'Не хватает одного подключения или настройки источника. После подключения можно запустить безопасный тест.',
    };
  }
  if (state === 'running_test') {
    return {
      title: 'Что происходит сейчас',
      description: 'Сотрудник выполняет проверку. Внешние отправки и публикации не выполняются без вашего разрешения.',
    };
  }
  if (state === 'error') {
    return {
      title: 'Почему сотрудник остановился',
      description: 'Последняя проверка не дала готового результата. Посмотрите причину и запустите тест после исправления.',
    };
  }
  if (state === 'working') {
    return {
      title: 'Почему можно не вмешиваться',
      description: 'Сценарий включён, новых решений от владельца сейчас не требуется.',
    };
  }
  return {
    title: 'Почему следующий шаг именно такой',
    description: 'Перед включением LocalOS сначала показывает безопасный тест и результат для проверки.',
  };
};

const buildBuildConfidenceFacts = (
  details?: AgentBlueprintDetails | null,
) => buildConfidenceFacts(details?.activation_gate, []).slice(0, 4);

const stringifyBusinessValue = (value: unknown): string => {
  if (value === null || value === undefined) {
    return '';
  }
  if (typeof value === 'string') {
    return value;
  }
  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  if (Array.isArray(value)) {
    return value
      .slice(0, 4)
      .map((item) => stringifyBusinessValue(item))
      .filter(Boolean)
      .join('; ');
  }
  if (typeof value === 'object') {
    const entries = Object.entries(value).slice(0, 6);
    return entries
      .map(([key, entryValue]) => {
        const text = stringifyBusinessValue(entryValue);
        return text ? `${humanizeMeta(key)}: ${text}` : '';
      })
      .filter(Boolean)
      .join('; ');
  }
  return '';
};

const isTechnicalApprovalPayload = (value: unknown): boolean => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return false;
  }
  const keys = Object.keys(value);
  return keys.some((key) => [
    'approval_required',
    'dispatch_state',
    'external_dispatch_performed',
    'approval_state',
    'artifact_type',
  ].includes(key)) || keys.some((key) => key.endsWith('_json'));
};

const toPlainRecord = (value: unknown): Record<string, unknown> | null => {
  if (typeof value === 'string') {
    try {
      const parsed = JSON.parse(value);
      return toPlainRecord(parsed);
    } catch {
      return null;
    }
  }
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return null;
  }
  return Object.fromEntries(Object.entries(value));
};

const meaningfulResultKeys = [
  'post_text',
  'draft_text',
  'message',
  'text',
  'body',
  'subject',
  'title',
  'summary',
  'result',
  'items',
  'facts',
  'recommendations',
  'reply_drafts',
  'rows_to_review',
  'preparation_method',
];

const extractBusinessResultPayload = (value: unknown): Record<string, unknown> | null => {
  const record = toPlainRecord(value);
  if (!record) {
    return null;
  }
  const nestedResult = toPlainRecord(record.result);
  if (nestedResult) {
    return nestedResult;
  }
  const nestedArtifact = toPlainRecord(record.artifact);
  if (nestedArtifact) {
    const artifactResult = extractBusinessResultPayload(nestedArtifact);
    if (artifactResult) {
      return artifactResult;
    }
  }
  const hasMeaningfulResult = meaningfulResultKeys.some((key) => record[key] !== undefined && record[key] !== null && record[key] !== '');
  if (!hasMeaningfulResult || isTechnicalApprovalPayload(record)) {
    return null;
  }
  return Object.fromEntries(
    Object.entries(record).filter(([key, entryValue]) => (
      meaningfulResultKeys.includes(key)
      && entryValue !== ''
      && entryValue !== null
      && entryValue !== undefined
    )),
  );
};

const findPreparedResultPayload = (
  activeRun: AgentRun | null,
  pendingApproval?: AgentApproval | null,
): Record<string, unknown> | null => {
  if (activeRun?.business_result && Object.keys(activeRun.business_result).length > 0) {
    return activeRun.business_result;
  }
  const artifacts = activeRun?.artifacts || [];
  const priority = activeRun?.status === 'completed'
    ? ['agent_final_result', 'agent_output_draft', 'telegram_post_draft']
    : ['agent_output_draft', 'telegram_post_draft', 'agent_final_result'];
  const preferredArtifact = priority
    .map((artifactType) => artifacts.find((item) => item.artifact_type === artifactType))
    .find(Boolean)
    || artifacts.find((item) => extractBusinessResultPayload(item.payload_json));
  const artifactResult = extractBusinessResultPayload(preferredArtifact?.payload_json || null);
  if (artifactResult) {
    return artifactResult;
  }
  if (pendingApproval?.run_id && activeRun?.id && pendingApproval.run_id !== activeRun.id) {
    return null;
  }
  return extractBusinessResultPayload(pendingApproval?.payload_json || null);
};

const hasPreparedMessageText = (result: Record<string, unknown> | null): boolean => {
  if (!result) {
    return false;
  }
  return ['post_text', 'draft_text', 'message', 'text', 'body'].some((key) => {
    const value = result[key];
    return typeof value === 'string' && value.trim().length > 0;
  });
};

const resultPayloadStatus = (result: Record<string, unknown> | null): string => {
  const status = result?.status;
  return typeof status === 'string' ? status.trim().toLowerCase() : '';
};

const isBusinessBlockerPayload = (result: Record<string, unknown> | null): boolean => {
  const status = resultPayloadStatus(result);
  return [
    'needs_source_data',
    'needs_clarification',
    'needs_source_upload',
    'needs_config',
    'validation_error',
    'provider_read_required',
    'needs_google_access',
    'needs_google_api_enabled',
    'needs_sheet_tab',
    'blocked',
  ].includes(status);
};

const isBusinessBlockerApproval = (approval?: AgentApproval | null): boolean => (
  isBusinessBlockerPayload(extractBusinessResultPayload(approval?.payload_json || null))
);

const buildEmployeeTestResult = (
  activeRun: AgentRun | null,
  pendingApproval?: AgentApproval | null,
): EmployeeTestResult => {
  const approvalItems = pendingApproval ? getApprovalPreviewItems(pendingApproval) : [];
  const resultPayload = findPreparedResultPayload(activeRun, pendingApproval);
  const blocker = isBusinessBlockerPayload(resultPayload);
  const hasStructuredResult = Boolean(resultPayload && !blocker);
  const output = hasStructuredResult
    ? ''
    : blocker
      ? ''
      : activeRun?.status === 'failed'
        ? 'Проверка остановилась до сохранения результата. Посмотрите причину в настройках и запустите тест ещё раз.'
        : '';
  const status = activeRun?.status || pendingApproval?.run_status || '';
  const isWorkRun = activeRun?.input_json?.preview_mode === false;
  const summary = blocker
    ? 'Нужен следующий шаг перед результатом'
    : pendingApproval
    ? hasPreparedMessageText(resultPayload)
      ? 'Проверьте подготовленный пост'
      : approvalDecisionTitle(pendingApproval)
    : status === 'completed'
      ? isWorkRun ? 'Работа завершена. Сотрудник сохранил результат.' : 'Тест завершён. Сотрудник подготовил результат.'
      : status === 'failed'
        ? 'Тест остановился. Результат требует проверки.'
        : activeRun
          ? 'Тест выполнен. Ниже бизнес-результат.'
          : 'После теста здесь появится подготовленный результат.';
  const state: EmployeeTestResult['state'] = hasStructuredResult
    ? 'result'
    : blocker
      ? 'blocker'
      : output
        ? 'missing'
        : 'missing';
  return {
    summary,
    output: output || (blocker
      ? ''
      : pendingApproval
        ? resultPayload
          ? 'Агент подготовил результат, но отдельный текст результата не был сохранён.'
          : 'Агент дошёл до проверки, но не сохранил результат. Запустите тест ещё раз или уточните формат результата.'
        : 'Результат не был сохранён. Запустите тест ещё раз.'),
    state,
    resultPayload,
    previewItems: approvalItems,
    hasResult: Boolean(activeRun || pendingApproval || output || resultPayload || approvalItems.length),
  };
};

const versionHasGoogleSheetsReadStep = (version?: Record<string, unknown> | null) => {
  const versionRecord = recordValue(version);
  const rawSteps = versionRecord ? versionRecord.steps_json : null;
  const steps = Array.isArray(rawSteps) ? rawSteps : [];
  return steps.some((step) => {
    const stepRecord = recordValue(step);
    if (!stepRecord) {
      return false;
    }
    const key = String(stepRecord.key || stepRecord.id || '').toLowerCase();
    const capability = String(stepRecord.capability || stepRecord.capability_key || '').toLowerCase();
    return key.includes('read_google_sheets') || capability === 'google_sheets.read_rows';
  });
};

const detailsHaveGoogleSheetsReadStep = (details?: AgentBlueprintDetails | null) => {
  if (!details) {
    return false;
  }
  if (versionHasGoogleSheetsReadStep(details.active_version)) {
    return true;
  }
  const latestVersion = [...(details.versions || [])].sort((a, b) => (getVersionNumber(b) || 0) - (getVersionNumber(a) || 0))[0] || null;
  return versionHasGoogleSheetsReadStep(latestVersion);
};

const needsScenarioRebuildForSourceResult = (
  activeRun: AgentRun | null,
  pendingApproval?: AgentApproval | null,
  details?: AgentBlueprintDetails | null,
) => {
  const resultPayload = findPreparedResultPayload(activeRun, pendingApproval);
  if (!isBusinessBlockerPayload(resultPayload)) {
    return false;
  }
  const sourceChain = activeRun?.observability?.source_result_chain || {};
  const text = stringifyBusinessValue(resultPayload).toLowerCase();
  const mentionsSheets = text.includes('google sheets') || text.includes('таблиц');
  if (!mentionsSheets) {
    return false;
  }
  if (sourceChain.source_step_present === false) {
    return true;
  }
  if (sourceChain.source_step_present === true) {
    return false;
  }
  return !detailsHaveGoogleSheetsReadStep(details);
};

const needsGoogleSheetsSourceSetup = (activeRun: AgentRun | null, pendingApproval?: AgentApproval | null) => {
  const resultPayload = findPreparedResultPayload(activeRun, pendingApproval);
  if (!isBusinessBlockerPayload(resultPayload)) {
    return false;
  }
  const text = stringifyBusinessValue(resultPayload).toLowerCase();
  if (resultPayloadStatus(resultPayload) === 'needs_google_access') {
    return text.includes('unable to parse range');
  }
  if (resultPayloadStatus(resultPayload) === 'needs_google_api_enabled') {
    return false;
  }
  if (resultPayloadStatus(resultPayload) === 'needs_sheet_tab') {
    return true;
  }
  return text.includes('google sheets') || text.includes('таблиц');
};

const needsGoogleAccessReconnect = (activeRun: AgentRun | null, pendingApproval?: AgentApproval | null) => {
  const resultPayload = findPreparedResultPayload(activeRun, pendingApproval);
  if (resultPayloadStatus(resultPayload) !== 'needs_google_access') {
    return false;
  }
  return !stringifyBusinessValue(resultPayload).toLowerCase().includes('unable to parse range');
};

const hasFreshGoogleSheetsAccessAfterResult = (
  authOptions: AgentExternalAuthOption[],
  activeRun: AgentRun | null,
  pendingApproval?: AgentApproval | null,
) => {
  const resultTimeRaw = activeRun?.completed_at || activeRun?.started_at || pendingApproval?.requested_at || pendingApproval?.run_started_at || '';
  const resultTime = resultTimeRaw ? new Date(resultTimeRaw).getTime() : 0;
  if (!resultTime || Number.isNaN(resultTime)) {
    return false;
  }
  return authOptions.some((option) => {
    const source = String(option.source || '').trim();
    const provider = String(option.provider || '').trim();
    if (!['google_business', 'google_sheets'].includes(source) && provider !== 'google_sheets') {
      return false;
    }
    const updatedAt = option.updated_at ? new Date(option.updated_at).getTime() : 0;
    return Boolean(updatedAt && !Number.isNaN(updatedAt) && updatedAt > resultTime);
  });
};

const buildEmployeeHistoryStory = (
  details: AgentBlueprintDetails | null,
  activeRun: AgentRun | null,
) => buildBusinessHistoryEvents(details, activeRun).map((event) => ({
  ...event,
  title: event.title === 'Запуск завершён' ? 'Выполнил задачу' : event.title,
  description: userFacingAgentTechText(event.description),
}));

const buildEmployeeAttentionItems = (
  blueprint: AgentBlueprint,
  details?: AgentBlueprintDetails | null,
  pendingApproval?: AgentApproval | null,
) => {
  const items: Array<{ key: string; title: string; description: string; tone: 'amber' | 'rose' }> = [];
  const missingConnections = Number(details?.activation_gate?.preflight?.missing_count || 0);
  const latestResult = findPreparedResultPayload(details?.runs?.[0] || null, pendingApproval);
  const blocker = isBusinessBlockerPayload(latestResult);
  if (blocker) {
    const needsGoogle = resultPayloadStatus(latestResult) === 'needs_google_access';
    items.push({
      key: needsGoogle ? 'google-access' : 'blocked-result',
      title: needsGoogle ? 'Нужен Google-доступ к таблице' : 'Нужен следующий шаг перед результатом',
      description: needsGoogle
        ? 'Google не дал строки таблицы. Переподключите доступ или запустите тест после подключения.'
        : 'Сотрудник остановился до готового результата. Откройте причину и исправьте следующий шаг.',
      tone: 'amber',
    });
  }
  if (!blocker && (pendingApproval || Number(blueprint.pending_approvals_count || 0) > 0)) {
    items.push({
      key: 'approval',
      title: 'Нужно ваше решение',
      description: pendingApproval ? explainApproval(pendingApproval) : 'Сотрудник ждёт подтверждения результата.',
      tone: 'amber',
    });
  }
  if (missingConnections > 0) {
    items.push({
      key: 'connections',
      title: 'Не хватает подключения',
      description: `${missingConnections} ${missingConnections === 1 ? 'сервис нужно подключить' : 'сервиса нужно подключить'}, чтобы сотрудник мог работать.`,
      tone: 'amber',
    });
  }
  if (blueprint.last_run_status === 'failed' || blueprint.status === 'error') {
    items.push({
      key: 'failed',
      title: 'Последняя работа остановилась',
      description: 'Откройте результат и повторите тест после исправления.',
      tone: 'rose',
    });
  }
  return items;
};

const buildAttentionInbox = ({
  blueprints,
  selectedBlueprint,
  selectedDetails,
  selectedPendingApproval,
  onOpenResults,
  onOpenConnections,
  onStartRun,
  onSelectBlueprint,
}: {
  blueprints: AgentBlueprint[];
  selectedBlueprint: AgentBlueprint | null;
  selectedDetails: AgentBlueprintDetails | null;
  selectedPendingApproval: AgentApproval | null;
  onOpenResults: () => void;
  onOpenConnections: () => void;
  onStartRun: () => void;
  onSelectBlueprint: (blueprint: AgentBlueprint, mode: AgentWorkspaceMode) => void;
}): AgentAttentionItem[] => {
  const items: AgentAttentionItem[] = [];
  const selectedLatestResult = findPreparedResultPayload(selectedDetails?.runs?.[0] || null, selectedPendingApproval);
  const selectedBlocker = isBusinessBlockerPayload(selectedLatestResult);
  if (selectedBlueprint && selectedBlocker) {
    const needsGoogle = resultPayloadStatus(selectedLatestResult) === 'needs_google_access';
    items.push({
      key: `${needsGoogle ? 'google-access' : 'blocked-result'}-${selectedBlueprint.id}`,
      tone: 'amber',
      problem: needsGoogle ? 'Нужен Google-доступ к таблице' : 'Нужен следующий шаг перед результатом',
      reason: needsGoogle
        ? `${selectedBlueprint.name}: Google не дал строки таблицы.`
        : `${selectedBlueprint.name}: сотрудник остановился до готового результата.`,
      actionLabel: needsGoogle ? 'Починить Google' : 'Посмотреть',
      action: onOpenResults,
    });
  }
  if (!selectedBlocker && selectedPendingApproval) {
    items.push({
      key: `approval-${selectedPendingApproval.id}`,
      tone: 'amber',
      problem: approvalDecisionTitle(selectedPendingApproval),
      reason: explainApproval(selectedPendingApproval),
      actionLabel: 'Посмотреть',
      action: onOpenResults,
    });
  }
  const missingCount = Number(selectedDetails?.activation_gate?.preflight?.missing_count || 0);
  if (selectedBlueprint && missingCount > 0) {
    items.push({
      key: `connections-${selectedBlueprint.id}`,
      tone: 'amber',
      problem: 'Нужно подключить данные',
      reason: `${selectedBlueprint.name}: ${missingCount} ${missingCount === 1 ? 'доступ ещё не готов' : 'доступа ещё не готовы'}.`,
      actionLabel: 'Подключить',
      action: onOpenConnections,
    });
  }
  if (selectedBlueprint?.last_run_status === 'failed') {
    items.push({
      key: `failed-${selectedBlueprint.id}`,
      tone: 'rose',
      problem: 'Последний запуск завершился ошибкой',
      reason: `${selectedBlueprint.name}: откройте результат и причину остановки.`,
      actionLabel: 'Открыть результат',
      action: onOpenResults,
    });
  }
  if (selectedBlueprint && selectedDetails?.activation_gate?.preview_run_status?.ready === false && !missingCount) {
    items.push({
      key: `preview-${selectedBlueprint.id}`,
      tone: 'sky',
      problem: 'Агент готов к безопасной проверке',
      reason: `${selectedBlueprint.name}: можно проверить сценарий без внешней отправки.`,
      actionLabel: 'Проверить',
      action: onStartRun,
    });
  }
  blueprints
    .filter((blueprint) => blueprint.id !== selectedBlueprint?.id)
    .filter((blueprint) => Number(blueprint.pending_approvals_count || 0) > 0 || blueprint.last_run_status === 'failed')
    .slice(0, Math.max(0, 4 - items.length))
    .forEach((blueprint) => {
      const failed = blueprint.last_run_status === 'failed';
      items.push({
        key: `list-${blueprint.id}`,
        tone: failed ? 'rose' : 'amber',
        problem: failed ? 'Ошибка в агенте' : 'Решение ждёт человека',
        reason: blueprint.name,
        actionLabel: failed ? 'Открыть результат' : 'Посмотреть',
        action: () => onSelectBlueprint(blueprint, 'results'),
      });
    });
  return items.slice(0, 4);
};

const buildConfidenceFacts = (
  gate?: AgentActivationGate,
  integrations: AgentIntegration[] = [],
): AgentConfidenceFact[] => {
  const hasExternalApproval = gate?.approval_policy_status?.ready !== false;
  return [
    {
      key: 'logic',
      label: gate?.compiled_validation?.ready === false ? 'Сценарий нужно проверить' : 'Сценарий проверен',
      ready: gate?.compiled_validation?.ready !== false,
    },
    {
      key: 'connections',
      label: gate?.preflight?.ready === false ? 'Подключения требуют внимания' : 'Подключения проверены',
      ready: gate?.preflight?.ready !== false,
    },
    {
      key: 'approval',
      label: hasExternalApproval ? 'Перед внешним действием требуется подтверждение' : 'Нужно добавить ручное подтверждение',
      ready: hasExternalApproval,
    },
    {
      key: 'stable',
      label: 'Агент использует опубликованный сценарий и не меняет его сам',
      ready: true,
    },
    {
      key: 'integrations',
      label: integrations.length ? `${integrations.length} ${integrations.length === 1 ? 'доступ подключён' : 'доступа подключены'}` : 'Можно работать без лишних доступов',
      ready: true,
    },
  ];
};

const buildScenarioPipeline = (
  blueprint: AgentBlueprint,
  details?: AgentBlueprintDetails | null,
  bindings: AgentIntegrationBindingStatus[] = [],
): AgentScenarioStep[] => {
  const preview = getBlueprintBuilderPreview(details?.blueprint || blueprint);
  const sourceText = preview?.data_sources?.length
    ? preview.data_sources.map((item) => userFacingAgentTechText(humanizeMeta(String(item || '')))).join(', ')
    : bindings.length
      ? Array.from(new Set(bindings.map((item) => connectorLabel(item.provider)))).join(', ')
      : 'данные бизнеса';
  const trigger = userFacingAgentTechText(String(preview?.trigger || (details?.active_version as Record<string, unknown> | null)?.trigger || 'manual.run'));
  const output = blueprint.category === 'outreach'
    ? 'подготовить список и черновики сообщений'
    : blueprint.category === 'reviews'
      ? 'подготовить ответы и решения по отзывам'
      : blueprint.category === 'services'
        ? 'подготовить предложения по услугам'
        : 'подготовить результат для проверки';
  return [
    {
      key: 'when',
      title: trigger || 'По запуску пользователя',
      description: 'LocalOS начинает работу только по опубликованному сценарию.',
    },
    {
      key: 'read',
      title: `Получить данные: ${sourceText}`,
      description: 'Агент берёт только разрешённые источники этого бизнеса.',
    },
    {
      key: 'prepare',
      title: userFacingAgentTechText(output),
      description: blueprint.description || blueprint.active_goal || blueprint.latest_goal || 'Собрать итог, который можно проверить.',
    },
    {
      key: 'approval',
      title: 'Попросить подтверждение перед внешним действием',
      description: 'Публикация, отправка и записи во внешние сервисы не выполняются без решения человека.',
    },
    {
      key: 'record',
      title: 'Сохранить результат и историю',
      description: 'Итог, решения и ошибки остаются в истории агента.',
    },
  ];
};

const buildBusinessHistoryEvents = (
  details: AgentBlueprintDetails | null,
  activeRun: AgentRun | null,
) => {
  const events: Array<{ key: string; time: string; title: string; description: string; sort: number }> = [];
  const add = (key: string, dateValue: string | null | undefined, title: string, description: string) => {
    const date = dateValue ? new Date(dateValue) : null;
    events.push({
      key,
      time: dateValue ? formatShortDate(dateValue) : 'сейчас',
      title,
      description,
      sort: date && !Number.isNaN(date.getTime()) ? date.getTime() : Date.now(),
    });
  };
  (details?.runs || []).filter((run) => run.status !== 'superseded').slice(0, 8).forEach((run) => {
    const artifactCount = Number(run.observability?.artifacts?.count || run.artifacts?.length || 0);
    if (run.status === 'completed') {
      add(`run-${run.id}`, run.completed_at || run.started_at, 'Запуск завершён', artifactCount ? `Подготовлено результатов: ${artifactCount}.` : 'Агент сохранил итог работы.');
      return;
    }
    if (run.status === 'waiting_approval') {
      add(`run-${run.id}`, run.started_at, 'Ждёт решения человека', 'Агент остановился перед действием, которое нужно подтвердить.');
      return;
    }
    if (run.status === 'failed') {
      add(`run-${run.id}`, run.completed_at || run.started_at, 'Запуск остановился с ошибкой', run.error_text || 'Откройте технические подробности, если нужна диагностика.');
      return;
    }
    add(`run-${run.id}`, run.started_at, humanizeStatus(run.status), 'Агент обновил состояние работы.');
  });
  (details?.approval_queue || []).slice(0, 5).forEach((approval) => {
    add(`approval-${approval.id}`, approval.requested_at || approval.run_started_at, approvalDecisionTitle(approval), explainApproval(approval));
  });
  (activeRun?.artifacts || []).slice(0, 5).forEach((artifact) => {
    add(`artifact-${artifact.id}`, activeRun.completed_at || activeRun.started_at, artifact.title || 'Подготовлен результат', userFacingAgentTechText(humanizeMeta(artifact.artifact_type || 'result')));
  });
  (activeRun?.steps || []).forEach((step) => {
    if (step.status !== 'completed') {
      return;
    }
    if (step.step_key === 'read_google_sheets') {
      add(`step-${step.id}`, activeRun.completed_at || activeRun.started_at, 'Прочитал таблицу поездок', 'Получил строки из подключённой Google-таблицы.');
    }
    if (step.step_key === 'prepare_output') {
      add(`step-${step.id}`, activeRun.completed_at || activeRun.started_at, 'Подготовил результат', 'Собрал текст только из данных выбранной строки.');
    }
    if (step.step_key === 'save_content_plan_draft') {
      add(`step-${step.id}`, activeRun.completed_at || activeRun.started_at, 'Сохранил черновик', 'Добавил результат в контент-план LocalOS.');
    }
  });
  return events
    .sort((a, b) => b.sort - a.sort)
    .slice(0, 12);
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
    {userFacingAgentTechText(humanizeStatus(status))}
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
  const location = useLocation();
  const { currentBusinessId, currentBusiness } = useOutletContext<DashboardContext>();
  const [blueprints, setBlueprints] = useState<AgentBlueprint[]>([]);
  const [selectedBlueprintId, setSelectedBlueprintId] = useState<string | null>(null);
  const [blueprintDetails, setBlueprintDetails] = useState<AgentBlueprintDetails | null>(null);
  const [agentDetailsById, setAgentDetailsById] = useState<Record<string, AgentBlueprintDetails>>({});
  const [activeRun, setActiveRun] = useState<AgentRun | null>(null);
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [agentSearch, setAgentSearch] = useState('');
  const [agentRegistryFilter, setAgentRegistryFilter] = useState<AgentRegistryFilter>('all');
  const [runAnimation, setRunAnimation] = useState<AgentRunAnimation | null>(null);
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
  const [builderExecutionMode, setBuilderExecutionMode] = useState<AgentExecutionMode>('manual');
  const [builderExecutionModeConfirmed, setBuilderExecutionModeConfirmed] = useState(false);
  const [cloneFromBlueprintId, setCloneFromBlueprintId] = useState('');
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
  const [browserTargetUrls, setBrowserTargetUrls] = useState('');
  const [browserDailyCap, setBrowserDailyCap] = useState('50');
  const [telegramBotMode, setTelegramBotMode] = useState('business_bot');
  const [telegramDailyCap, setTelegramDailyCap] = useState('50');
  const [whatsappChannelMode, setWhatsappChannelMode] = useState('whatsapp_business');
  const [whatsappDailyCap, setWhatsappDailyCap] = useState('50');
  const [matonAuthRef, setMatonAuthRef] = useState('');
  const [matonChannel, setMatonChannel] = useState('maton_bridge');
  const [matonDailyCap, setMatonDailyCap] = useState('50');
  const [processRowValues, setProcessRowValues] = useState('{{received_at}}, {{telegram_username}}, {{message_text}}');
  const [processPreviewMessage, setProcessPreviewMessage] = useState('Новая заявка: Анна, телефон +7 900 000-00-00, хочет консультацию');
  const [scheduleTime, setScheduleTime] = useState('09:00');
  const [scheduleTimezone, setScheduleTimezone] = useState('Europe/Moscow');
  const [selectedExecutionMode, setSelectedExecutionMode] = useState<AgentExecutionMode>('manual');
  const [feedbackText, setFeedbackText] = useState('');
  const [feedbackTrigger, setFeedbackTrigger] = useState('manual_edit');
  const [feedbackVersionNotice, setFeedbackVersionNotice] = useState<FeedbackVersionNotice | null>(null);
  const [systemAgentConfig, setSystemAgentConfig] = useState<Record<string, { enabled?: boolean }>>({});
  const [legacyMigrationPlan, setLegacyMigrationPlan] = useState<LegacyMigrationPlan | null>(null);
  const [legacyMigrationNotice, setLegacyMigrationNotice] = useState('');
  const [recentCreatedAgentName, setRecentCreatedAgentName] = useState('');
  const [recentPostCreateHandoff, setRecentPostCreateHandoff] = useState<AgentPostCreateHandoff | null>(null);
  const [showAdvancedAgentTools, setShowAdvancedAgentTools] = useState(false);
  const [deleteCandidate, setDeleteCandidate] = useState<AgentBlueprint | null>(null);
  const [decisionNotice, setDecisionNotice] = useState<string | null>(null);
  const googleAuthStatus = useMemo(() => {
    const params = new URLSearchParams(location.search);
    return params.get('google_auth');
  }, [location.search]);
  const googleAccessJustConnected = googleAuthStatus === 'success';

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

  useEffect(() => {
    if (!googleAccessJustConnected) {
      return;
    }
    setDecisionNotice('Google-доступ подключён. Теперь запустите тест ещё раз, чтобы проверить таблицу на свежем доступе.');
    setWorkspaceMode((currentMode) => (currentMode === 'overview' ? 'results' : currentMode));
  }, [googleAccessJustConnected]);

  const selectedBlueprint = useMemo(
    () => blueprints.find((item) => item.id === selectedBlueprintId) || blueprints[0] || null,
    [blueprints, selectedBlueprintId],
  );

  useEffect(() => {
    const metadata = selectedBlueprint?.metadata_json;
    const customProcess = recordValue(metadata?.custom_process);
    const schedule = recordValue(customProcess?.schedule);
    if (schedule && typeof schedule.time === 'string' && schedule.time) {
      setScheduleTime(schedule.time);
    }
    if (schedule && typeof schedule.timezone === 'string' && schedule.timezone && schedule.timezone !== 'business_timezone') {
      setScheduleTimezone(schedule.timezone);
    } else if ((currentBusiness?.name || '').toLowerCase().includes('tallinn')) {
      setScheduleTimezone('Europe/Tallinn');
    }
    if (selectedBlueprint) {
      setSelectedExecutionMode(agentExecutionMode(selectedBlueprint, blueprintDetails));
    }
  }, [blueprintDetails?.execution_mode, currentBusiness?.name, selectedBlueprint]);

  const pendingApproval = useMemo(
    () => activeRun?.approvals?.find((item) => item.status === 'pending') || null,
    [activeRun],
  );

  const activeRunPendingApprovals = useMemo(
    () => (activeRun?.approvals || []).filter((item) => item.status === 'pending' && !isBusinessBlockerApproval(item)),
    [activeRun?.approvals],
  );

  const actionablePendingApproval = activeRunPendingApprovals[0] || null;

  const rawPendingApprovals = useMemo(
    () => {
      const latestRunId = blueprintDetails?.runs?.[0]?.id || '';
      return (blueprintDetails?.approval_queue || []).filter((item) => (
        item.status === 'pending' && (!latestRunId || item.run_id === latestRunId)
      ));
    },
    [blueprintDetails?.approval_queue, blueprintDetails?.runs],
  );

  const pendingApprovals = useMemo(
    () => rawPendingApprovals.filter((item) => !isBusinessBlockerApproval(item)),
    [rawPendingApprovals],
  );

  const selectedPendingApproval = useMemo(
    () => pendingApproval || rawPendingApprovals[0] || null,
    [pendingApproval, rawPendingApprovals],
  );

  const selectedActionablePendingApproval = useMemo(
    () => actionablePendingApproval || pendingApprovals[0] || null,
    [actionablePendingApproval, pendingApprovals],
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
        candidate_version: response.data?.candidate_version || null,
        candidate_version_id: typeof response.data?.candidate_version_id === 'string' ? response.data.candidate_version_id : '',
        execution_mode: response.data?.execution_mode,
        execution_mode_source: response.data?.execution_mode_source,
        execution_mode_confirmation_required: response.data?.execution_mode_confirmation_required === true,
        lifecycle_state: response.data?.lifecycle_state,
        last_business_result: response.data?.last_business_result && typeof response.data.last_business_result === 'object' ? response.data.last_business_result : null,
        next_run_at: typeof response.data?.next_run_at === 'string' ? response.data.next_run_at : null,
        learning_events: Array.isArray(response.data?.learning_events) ? response.data.learning_events : [],
        version_events: Array.isArray(response.data?.version_events) ? response.data.version_events : [],
        feedback_history: Array.isArray(response.data?.feedback_history) ? response.data.feedback_history : [],
        legacy_migration: response.data?.legacy_migration || {},
        metrics: response.data?.metrics && typeof response.data.metrics === 'object' ? response.data.metrics : undefined,
        activation_gate: response.data?.activation_gate && typeof response.data.activation_gate === 'object' ? response.data.activation_gate : undefined,
      };
      setBlueprintDetails(details);
      setAgentDetailsById((current) => ({
        ...current,
        [blueprintId]: details,
      }));
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

  useEffect(() => {
    if (!currentBusinessId || !blueprints.length) {
      return;
    }
    const missing = blueprints
      .slice(0, 6)
      .filter((blueprint) => !agentDetailsById[blueprint.id])
      .map((blueprint) => blueprint.id);
    if (!missing.length) {
      return;
    }
    let cancelled = false;
    const loadRecentDetails = async () => {
      try {
        const responses = await Promise.all(
          missing.map((blueprintId) => api.get(`/agent-blueprints/${blueprintId}`, { params: { run_status: 'all' } })),
        );
        if (cancelled) {
          return;
        }
        setAgentDetailsById((current) => {
          const next = { ...current };
          responses.forEach((response, index) => {
            const blueprintId = missing[index];
            next[blueprintId] = {
              blueprint: response.data?.blueprint && typeof response.data.blueprint === 'object' ? response.data.blueprint : undefined,
              versions: Array.isArray(response.data?.versions) ? response.data.versions : [],
              runs: Array.isArray(response.data?.runs) ? response.data.runs : [],
              approval_queue: Array.isArray(response.data?.approval_queue) ? response.data.approval_queue : [],
              active_version: response.data?.active_version || null,
              active_version_id: typeof response.data?.active_version_id === 'string' ? response.data.active_version_id : '',
              active_version_number: typeof response.data?.active_version_number === 'number' ? response.data.active_version_number : 0,
              candidate_version: response.data?.candidate_version || null,
              candidate_version_id: typeof response.data?.candidate_version_id === 'string' ? response.data.candidate_version_id : '',
              execution_mode: response.data?.execution_mode,
              execution_mode_source: response.data?.execution_mode_source,
              execution_mode_confirmation_required: response.data?.execution_mode_confirmation_required === true,
              lifecycle_state: response.data?.lifecycle_state,
              last_business_result: response.data?.last_business_result && typeof response.data.last_business_result === 'object' ? response.data.last_business_result : null,
              next_run_at: typeof response.data?.next_run_at === 'string' ? response.data.next_run_at : null,
              learning_events: Array.isArray(response.data?.learning_events) ? response.data.learning_events : [],
              version_events: Array.isArray(response.data?.version_events) ? response.data.version_events : [],
              feedback_history: Array.isArray(response.data?.feedback_history) ? response.data.feedback_history : [],
              legacy_migration: response.data?.legacy_migration || {},
              metrics: response.data?.metrics && typeof response.data.metrics === 'object' ? response.data.metrics : undefined,
              activation_gate: response.data?.activation_gate && typeof response.data.activation_gate === 'object' ? response.data.activation_gate : undefined,
            };
          });
          return next;
        });
      } catch (requestError) {
        console.error(requestError);
      }
    };
    void loadRecentDetails();
    return () => {
      cancelled = true;
    };
  }, [agentDetailsById, blueprints, currentBusinessId]);

  const loadRun = async (runId: string, options: { openResults?: boolean; showLoading?: boolean } = {}) => {
    const openResults = options.openResults !== false;
    const showLoading = options.showLoading !== false;
    if (showLoading) {
      setActionLoading(true);
    }
    setError(null);
    try {
      const response = await api.get(`/agent-runs/${runId}`);
      setActiveRun(response.data?.run || null);
      if (openResults) {
        setWorkspaceMode('results');
      }
      if (selectedBlueprint?.id) {
        await loadBlueprintDetails(selectedBlueprint.id);
        await loadBlueprintReview(selectedBlueprint.id);
      }
    } catch (requestError) {
      console.error(requestError);
      setError('Не удалось загрузить запуск.');
    } finally {
      if (showLoading) {
        setActionLoading(false);
      }
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

  useEffect(() => {
    const latestRun = blueprintDetails?.runs?.[0];
    if (!latestRun?.id || activeRun?.id === latestRun.id) {
      return;
    }
    if (!['completed', 'waiting_approval', 'failed'].includes(latestRun.status || '')) {
      return;
    }
    void loadRun(latestRun.id, { openResults: false, showLoading: false });
  }, [activeRun?.id, blueprintDetails?.runs]);

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
    setDecisionNotice(null);
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
        setWorkspaceMode('overview');
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
    setDecisionNotice(null);
    try {
      const response = await api.post('/agent-builder/sessions', {
        business_id: currentBusinessId,
        message: dialogBuilderInput.trim(),
        use_ai_compiler: true,
      });
      const preview = response.data?.session?.preview || null;
      const autoProviderRoutes = autoSelectBuilderProviderRoutes(preview);
      setDialogBuilderSession(response.data?.session || null);
      setSelectedBuilderConnectionBindings(autoSelectBuilderConnectionBindings(preview));
      setSelectedBuilderProviderRoutes(autoProviderRoutes);
      setAcceptedBuilderCompilerPlan(false);
      setAcceptedBuilderProviderRoutes(Object.keys(autoProviderRoutes).length > 0);
      setBuilderExecutionMode(String(preview?.compiler_workflow_draft?.trigger || '').includes('schedule') ? 'scheduled' : 'manual');
      setBuilderExecutionModeConfirmed(false);
      setAgentPrompt(dialogBuilderInput.trim());
      if (preview && typeof preview.category === 'string') {
        setBuilderCategory(preview.category);
      }
      if (preview && Array.isArray(preview.data_sources)) {
        setBuilderDataSources(preview.data_sources.join(', '));
      }
      if (preview && typeof preview.extraction_rules === 'string') {
        setBuilderExtractionRules(preview.extraction_rules);
      }
      if (preview && typeof preview.processing_rules === 'string') {
        setBuilderProcessingRules(preview.processing_rules);
      }
      if (preview && typeof preview.output_format === 'string') {
        setBuilderOutputFormat(preview.output_format);
      }
      if (preview && typeof preview.manual_control === 'string') {
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
      const preview = response.data?.session?.preview || null;
      const autoProviderRoutes = autoSelectBuilderProviderRoutes(preview);
      setDialogBuilderSession(response.data?.session || null);
      setSelectedBuilderConnectionBindings(autoSelectBuilderConnectionBindings(preview));
      setSelectedBuilderProviderRoutes(autoProviderRoutes);
      setAcceptedBuilderCompilerPlan(false);
      setAcceptedBuilderProviderRoutes(Object.keys(autoProviderRoutes).length > 0);
      setBuilderExecutionMode(String(preview?.compiler_workflow_draft?.trigger || '').includes('schedule') ? 'scheduled' : builderExecutionMode);
      setBuilderExecutionModeConfirmed(false);
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
        execution_mode: builderExecutionMode,
        schedule_time: builderExecutionMode === 'scheduled' ? scheduleTime : undefined,
        schedule_timezone: builderExecutionMode === 'scheduled' ? scheduleTimezone : undefined,
        clone_from_blueprint_id: cloneFromBlueprintId || undefined,
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
        setWorkspaceMode('overview');
      }
      setDialogBuilderInput('');
      setDialogBuilderReply('');
      setDialogBuilderSession(null);
      setSelectedBuilderConnectionBindings({});
      setSelectedBuilderProviderRoutes({});
      setAcceptedBuilderCompilerPlan(false);
      setAcceptedBuilderProviderRoutes(false);
      setBuilderExecutionModeConfirmed(false);
      setCloneFromBlueprintId('');
      setCreateWizardOpen(false);
      setWorkspaceMode('overview');
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
        execution_mode: builderExecutionMode,
        schedule_time: builderExecutionMode === 'scheduled' ? scheduleTime : undefined,
        schedule_timezone: builderExecutionMode === 'scheduled' ? scheduleTimezone : undefined,
        clone_from_blueprint_id: cloneFromBlueprintId || undefined,
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
          if (handoff.next_binding_key) {
            setSelectedConnectionBindingKey(handoff.next_binding_key);
          }
        } else if (handoff?.workspace_mode === 'run') {
          setSelectedConnectionBindingKey('');
        }
        setWorkspaceMode('overview');
      }
      setAgentPrompt('');
      setBuilderSourceName('');
      setBuilderSourceText('');
      setBuilderFileSource(null);
      setBuilderExecutionModeConfirmed(false);
      setCloneFromBlueprintId('');
      setCreateWizardOpen(false);
      setCreateWizardStep(0);
    } catch (requestError) {
      console.error(requestError);
      setError(getRequestErrorMessage(requestError, 'Не удалось собрать черновик агента.'));
    } finally {
      setActionLoading(false);
    }
  };

  useEffect(() => {
    if (!runAnimation || runAnimation.status !== 'running') {
      return;
    }
    const timer = window.setInterval(() => {
      setRunAnimation((current) => {
        if (!current || current.status !== 'running') {
          return current;
        }
        const progress = Math.min(92, current.progress + 7);
        const stepIndex = Math.min(
          current.steps.length - 1,
          Math.floor((progress / 100) * current.steps.length),
        );
        return { ...current, progress, stepIndex };
      });
    }, 420);
    return () => window.clearInterval(timer);
  }, [runAnimation?.blueprintId, runAnimation?.startedAt, runAnimation?.status]);

  const beginRunAnimation = (blueprintId: string, kind: AgentRunAnimation['kind']) => {
    const animation: AgentRunAnimation = {
      kind,
      blueprintId,
      startedAt: Date.now(),
      progress: 8,
      stepIndex: 0,
      steps: workflowStepsForAnimation(blueprintDetails, kind),
      status: 'running',
    };
    setRunAnimation(animation);
    return animation.startedAt;
  };

  const finishRunAnimation = async (startedAt: number) => {
    const waitMs = Math.max(0, 6500 - (Date.now() - startedAt));
    if (waitMs > 0) {
      await new Promise<void>((resolve) => window.setTimeout(resolve, waitMs));
    }
    setRunAnimation((current) => current ? {
      ...current,
      progress: 100,
      stepIndex: Math.max(0, current.steps.length - 1),
      status: 'finishing',
    } : current);
    await new Promise<void>((resolve) => window.setTimeout(resolve, 360));
  };

  const failRunAnimation = (message: string) => {
    setRunAnimation((current) => current ? { ...current, status: 'error', error: message } : current);
  };

  const startRun = async (blueprintToRun?: AgentBlueprint | null, blueprintVersionId = '') => {
    const targetBlueprint = blueprintToRun || selectedBlueprint;
    if (!targetBlueprint) {
      return;
    }
    setActionLoading(true);
    setError(null);
    setDecisionNotice(null);
    const animationStartedAt = beginRunAnimation(targetBlueprint.id, 'test');
    try {
      const selectedVersionId = blueprintVersionId || getRunnableVersionId(targetBlueprint, blueprintDetails);
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
        blueprint_version_id: selectedVersionId,
        external_side_effects_allowed: false,
        approval_required_for_external_actions: true,
        limit: Number(runLimit) > 0 ? Math.min(Number(runLimit), 100) : 30,
      };
      const preflightResponse = await api.post(`/agent-blueprints/${targetBlueprint.id}/preflight`, {
        blueprint_version_id: selectedVersionId || undefined,
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
        setWorkspaceMode('overview');
        const message = formatPreflightBlock(preflight) || 'Перед запуском нужно подключить источники агента.';
        setError(message);
        failRunAnimation(message);
        await loadBlueprintDetails(targetBlueprint.id);
        return;
      }
      const response = await api.post(`/agent-blueprints/${targetBlueprint.id}/runs`, {
        blueprint_version_id: selectedVersionId || undefined,
        input: runInput,
      });
      const nextRun = response.data?.run || null;
      setActiveRun(nextRun);
      await finishRunAnimation(animationStartedAt);
      setRunAnimation(null);
      setWorkspaceMode('results');
      setDecisionNotice(nextRun?.id ? 'Тест запущен заново. Ниже показан свежий результат проверки.' : 'Тест запущен заново.');
      await loadBlueprintDetails(targetBlueprint.id);
      await loadBlueprintReview(targetBlueprint.id);
    } catch (requestError) {
      console.error(requestError);
      const message = getRequestErrorMessage(requestError, 'Не удалось запустить агента.');
      setError(message);
      failRunAnimation(message);
    } finally {
      setActionLoading(false);
    }
  };

  const executeRun = async (blueprintToRun?: AgentBlueprint | null, blueprintVersionId = '') => {
    const targetBlueprint = blueprintToRun || selectedBlueprint;
    if (!targetBlueprint) {
      return;
    }
    setActionLoading(true);
    setError(null);
    setDecisionNotice(null);
    const animationStartedAt = beginRunAnimation(targetBlueprint.id, 'work');
    try {
      const selectedVersionId = blueprintVersionId || blueprintDetails?.active_version_id || blueprintDetails?.candidate_version_id || '';
      const response = await api.post(`/agent-blueprints/${targetBlueprint.id}/runs`, {
        blueprint_version_id: selectedVersionId || undefined,
        input: {
          preview_mode: false,
          source: 'dashboard_work_run',
          dashboard_source: 'dashboard',
          business_id: currentBusinessId,
          external_side_effects_allowed: false,
          approval_required_for_external_actions: true,
          limit: Number(runLimit) > 0 ? Math.min(Number(runLimit), 100) : 30,
        },
      });
      const nextRun = response.data?.run || null;
      setActiveRun(nextRun);
      await finishRunAnimation(animationStartedAt);
      setRunAnimation(null);
      setWorkspaceMode('results');
      setDecisionNotice(nextRun?.id ? 'Работа выполнена. Ниже показан свежий сохранённый результат.' : 'Работа запущена.');
      await loadBlueprintDetails(targetBlueprint.id);
      await loadBlueprintReview(targetBlueprint.id);
    } catch (requestError) {
      console.error(requestError);
      const message = getRequestErrorMessage(requestError, 'Не удалось выполнить задачу агента.');
      setError(message);
      failRunAnimation(message);
    } finally {
      setActionLoading(false);
    }
  };

  const saveSchedule = async () => {
    if (!selectedBlueprint) {
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      await api.post(`/agent-blueprints/${selectedBlueprint.id}/schedule`, {
        time: scheduleTime,
        timezone: scheduleTimezone,
      });
      setDecisionNotice('Расписание сохранено. Теперь включите агента.');
      await loadBlueprints();
      await loadBlueprintDetails(selectedBlueprint.id);
    } catch (requestError) {
      console.error(requestError);
      setError(getRequestErrorMessage(requestError, 'Не удалось сохранить расписание.'));
    } finally {
      setActionLoading(false);
    }
  };

  const saveExecutionMode = async () => {
    if (!selectedBlueprint) {
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      await api.post(`/agent-blueprints/${selectedBlueprint.id}/execution-mode`, {
        execution_mode: selectedExecutionMode,
        time: selectedExecutionMode === 'scheduled' ? scheduleTime : undefined,
        timezone: selectedExecutionMode === 'scheduled' ? scheduleTimezone : undefined,
      });
      setDecisionNotice(selectedExecutionMode === 'scheduled'
        ? 'Тип запуска и расписание сохранены. После успешного теста агента можно включить.'
        : 'Тип запуска сохранён. Теперь можно проверить агента.');
      await loadBlueprints();
      await loadBlueprintDetails(selectedBlueprint.id);
      setWorkspaceMode('overview');
    } catch (requestError) {
      console.error(requestError);
      setError(getRequestErrorMessage(requestError, 'Не удалось сохранить тип запуска.'));
    } finally {
      setActionLoading(false);
    }
  };

  const rebuildScenarioAndRun = async () => {
    if (!selectedBlueprint) {
      return;
    }
    setActionLoading(true);
    setError(null);
    setDecisionNotice(null);
    try {
      const description = selectedBlueprint.description || selectedBlueprint.latest_goal || selectedBlueprint.name || '';
      const response = await api.post(`/agent-blueprints/${selectedBlueprint.id}/versions`, {
        rebuild_from_description: true,
        description,
        category: selectedBlueprint.category || 'custom',
        reason: 'Rebuilt from dashboard because the previous scenario had no source read step.',
      });
      const versionId = response.data?.version?.id || response.data?.candidate_version?.id || '';
      await loadBlueprintDetails(selectedBlueprint.id);
      setDecisionNotice('Сценарий пересобран. Запускаю тест по новой версии.');
      await startRun(selectedBlueprint, versionId);
    } catch (requestError) {
      console.error(requestError);
      setError(getRequestErrorMessage(requestError, 'Не удалось пересобрать сценарий агента.'));
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

  const deleteAgent = async (blueprint: AgentBlueprint | null) => {
    if (!blueprint) {
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      await api.delete(`/agent-blueprints/${blueprint.id}`);
      const remaining = blueprints.filter((item) => item.id !== blueprint.id);
      setSelectedBlueprintId(remaining[0]?.id || null);
      setBlueprintDetails(null);
      setActiveRun(null);
      setWorkspaceMode('overview');
      setDeleteCandidate(null);
      await loadBlueprints();
    } catch (requestError) {
      console.error(requestError);
      setError(getRequestErrorMessage(requestError, 'Не удалось удалить агента.'));
    } finally {
      setActionLoading(false);
    }
  };

  const requestDeleteAgent = (blueprint: AgentBlueprint | null) => {
    if (!blueprint) {
      return;
    }
    setDeleteCandidate(blueprint);
  };

  const deleteSelectedAgent = async () => {
    requestDeleteAgent(selectedBlueprint);
  };

  const decideApproval = async (decision: 'approve' | 'reject') => {
    const approval = selectedActionablePendingApproval;
    const runId = approval?.run_id || activeRun?.id || selectedBlueprint?.last_run_id || '';
    if (!approval || !runId) {
      setError('Не удалось найти запуск для этого решения. Обновите страницу и попробуйте снова.');
      return;
    }
    if (isBusinessBlockerApproval(approval)) {
      setError('Это не готовый результат, а причина остановки. Исправьте следующий шаг и запустите тест ещё раз.');
      setWorkspaceMode('results');
      return;
    }
    setActionLoading(true);
    setError(null);
    setDecisionNotice(null);
    try {
      const response = await api.post(`/agent-runs/${runId}/approvals/${approval.id}/${decision}`, {
        reason: decision === 'approve' ? 'Approved from dashboard' : 'Rejected from dashboard',
      });
      const updatedRun = response.data?.run || null;
      if (updatedRun) {
        setActiveRun(updatedRun);
      } else {
        await loadRun(runId);
      }
      if (selectedBlueprint?.id) {
        await loadBlueprintDetails(selectedBlueprint.id);
        await loadBlueprintReview(selectedBlueprint.id);
      }
      await loadBlueprints();
      setDecisionNotice(decision === 'approve' ? 'Решение принято. Агент продолжил работу.' : 'Результат отклонён. Агент остановлен для правки.');
      setWorkspaceMode('results');
    } catch (requestError) {
      console.error(requestError);
      setError(getRequestErrorMessage(requestError, 'Не удалось применить решение.'));
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
          spreadsheet_id: normalizeSpreadsheetInput(sheetSpreadsheetId),
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
      const handoff = normalizePostCreateHandoff(response.data?.post_connect_handoff);
      applyPostConnectHandoff(handoff);
      if (handoff?.status === 'ready_for_preview') {
        setDecisionNotice('Таблица сохранена. Теперь запустите безопасный тест.');
      } else if (handoff?.status === 'needs_connections') {
        const nextTitle = handoff.next_binding?.title || connectorLabel(handoff.next_binding?.provider);
        setDecisionNotice(`Таблица сохранена. Остался следующий доступ: ${nextTitle}.`);
      } else {
        setDecisionNotice('Таблица сохранена.');
      }
    } catch (requestError) {
      console.error(requestError);
      setError(getRequestErrorMessage(requestError, 'Не удалось подключить Google Sheets.'));
    } finally {
      setActionLoading(false);
    }
  };

  const saveBrowserUseIntegration = async () => {
    if (!selectedBlueprint || !browserTargetUrls.trim()) {
      return;
    }
    const selectedBinding = agentBindingStatus.find((item) => item.key === selectedConnectionBindingKey && item.provider === 'browser_use');
    const existing = [...agentIntegrations, ...availableAgentIntegrations].find((item) => item.provider === 'browser_use');
    setActionLoading(true);
    setError(null);
    try {
      const response = await api.post(`/agent-blueprints/${selectedBlueprint.id}/integrations`, {
        integration_id: existing?.id,
        binding_key: selectedBinding?.key || '',
        provider: 'browser_use',
        status: 'active',
        display_name: 'Browser use',
        config: {
          target_urls: browserTargetUrls,
        },
        limits: {
          daily_page_check_cap: Number(browserDailyCap) > 0 ? Number(browserDailyCap) : 50,
          frequency_cap_minutes: 60,
        },
      });
      await loadAgentIntegrations(selectedBlueprint.id);
      await loadBlueprintDetails(selectedBlueprint.id);
      applyPostConnectHandoff(response.data?.post_connect_handoff);
    } catch (requestError) {
      console.error(requestError);
      setError(getRequestErrorMessage(requestError, 'Не удалось подключить Browser use.'));
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

  const saveWhatsappIntegration = async () => {
    if (!selectedBlueprint) {
      return;
    }
    const selectedBinding = agentBindingStatus.find((item) => item.key === selectedConnectionBindingKey && item.provider === 'whatsapp');
    const existing = [...agentIntegrations, ...availableAgentIntegrations].find((item) => item.provider === 'whatsapp');
    setActionLoading(true);
    setError(null);
    try {
      const response = await api.post(`/agent-blueprints/${selectedBlueprint.id}/integrations`, {
        integration_id: existing?.id,
        binding_key: selectedBinding?.key || '',
        provider: 'whatsapp',
        status: 'active',
        display_name: 'WhatsApp',
        config: {
          channel_mode: whatsappChannelMode,
        },
        limits: {
          daily_message_cap: Number(whatsappDailyCap) > 0 ? Number(whatsappDailyCap) : 50,
          frequency_cap_minutes: 30,
        },
      });
      await loadAgentIntegrations(selectedBlueprint.id);
      await loadBlueprintDetails(selectedBlueprint.id);
      applyPostConnectHandoff(response.data?.post_connect_handoff);
    } catch (requestError) {
      console.error(requestError);
      setError(getRequestErrorMessage(requestError, 'Не удалось подключить WhatsApp.'));
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
      setError(getRequestErrorMessage(requestError, 'Не удалось выбрать способ подключения для агента.'));
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
        spreadsheet_id: normalizeSpreadsheetInput(sheetSpreadsheetId),
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

  const postCreateReadyForRun = recentPostCreateHandoff?.workspace_mode === 'run'
    || recentPostCreateHandoff?.status === 'ready_for_preview';
  const showPostCreateConnectionDetails = Boolean(recentPostCreateHandoff)
    && !postCreateReadyForRun
    && (recentPostCreateHandoff?.workspace_mode === 'connections' || recentPostCreateHandoff?.status === 'needs_connections');
  const todaySummary = useMemo(
    () => buildTodaySummary(blueprints, agentDetailsById),
    [agentDetailsById, blueprints],
  );
  const employeeListDetailsById = useMemo(() => {
    if (!selectedBlueprint?.id || !blueprintDetails) {
      return agentDetailsById;
    }
    const selectedDetails = (() => {
      if (!activeRun?.id) {
        return blueprintDetails;
      }
      const runs = blueprintDetails.runs || [];
      const runBelongsToSelectedBlueprint = activeRun.blueprint_id === selectedBlueprint.id
        || activeRun.id === runs[0]?.id
        || activeRun.id === selectedBlueprint.last_run_id;
      if (!runBelongsToSelectedBlueprint) {
        return blueprintDetails;
      }
      return {
        ...blueprintDetails,
        runs: [activeRun, ...runs.filter((run) => run.id !== activeRun.id)],
      };
    })();
    return {
      ...agentDetailsById,
      [selectedBlueprint.id]: selectedDetails,
    };
  }, [activeRun, agentDetailsById, blueprintDetails, selectedBlueprint?.id, selectedBlueprint?.last_run_id]);
  const filteredBlueprints = useMemo(() => {
    const query = agentSearch.trim().toLowerCase();
    return blueprints.filter((blueprint) => {
      const details = employeeListDetailsById[blueprint.id];
      const state = buildEmployeeWorkspaceState(blueprint, details);
      const matchesSearch = !query || [blueprint.name, buildEmployeeDescription(blueprint, details)]
        .some((value) => String(value || '').toLowerCase().includes(query));
      if (!matchesSearch) {
        return false;
      }
      if (agentRegistryFilter === 'working') {
        return state === 'working';
      }
      if (agentRegistryFilter === 'completed') {
        return state === 'completed';
      }
      if (agentRegistryFilter === 'attention') {
        return ['needs_mode', 'needs_connection', 'ready_for_test', 'waiting_for_review', 'blocked_result', 'needs_attention', 'error'].includes(state);
      }
      return true;
    });
  }, [agentRegistryFilter, agentSearch, blueprints, employeeListDetailsById]);
  const openBlueprintMode = (blueprint: AgentBlueprint, mode: AgentWorkspaceMode) => {
    setSelectedBlueprintId(blueprint.id);
    setActiveRun(null);
    setDecisionNotice(null);
    setWorkspaceMode(mode);
  };
  const attentionItems = useMemo(
    () => buildAttentionInbox({
      blueprints,
      selectedBlueprint,
      selectedDetails: blueprintDetails,
      selectedPendingApproval,
      onOpenResults: () => setWorkspaceMode('results'),
      onOpenConnections: () => setWorkspaceMode('connections'),
      onStartRun: () => {
        if (selectedBlueprint) {
          void startRun(selectedBlueprint);
        }
      },
      onSelectBlueprint: openBlueprintMode,
    }),
    [blueprintDetails, blueprints, selectedBlueprint, selectedPendingApproval],
  );
  const selectedEmployeeAction = useMemo(
    () => selectedBlueprint
      ? buildEmployeeNextAction({
        blueprint: selectedBlueprint,
        details: blueprintDetails,
        pendingApproval: selectedPendingApproval,
        googleAccessFreshAfterResult: hasFreshGoogleSheetsAccessAfterResult(
          agentExternalAuthOptions,
          activeRun || blueprintDetails?.runs?.[0] || null,
          selectedPendingApproval,
        ),
      })
      : null,
    [activeRun, agentExternalAuthOptions, blueprintDetails, selectedBlueprint, selectedPendingApproval],
  );
  const selectedResultRun = activeRun || blueprintDetails?.runs?.[0] || null;
  const resultNeedsScenarioRebuild = needsScenarioRebuildForSourceResult(selectedResultRun, selectedPendingApproval, blueprintDetails);
  const resultNeedsGoogleSheetsSetup = needsGoogleSheetsSourceSetup(selectedResultRun, selectedPendingApproval);
  const resultNeedsGoogleAccessReconnect = needsGoogleAccessReconnect(selectedResultRun, selectedPendingApproval);
  const resultGoogleAccessReconnected = resultNeedsGoogleAccessReconnect && (
    googleAccessJustConnected
    || hasFreshGoogleSheetsAccessAfterResult(agentExternalAuthOptions, selectedResultRun, selectedPendingApproval)
  );
  const openGoogleSheetsSourceSetup = () => {
    const sheetBinding = agentBindingStatus.find((binding) => binding.provider === 'google_sheets' && binding.capability === 'google_sheets.read_rows')
      || agentBindingStatus.find((binding) => binding.provider === 'google_sheets')
      || null;
    if (sheetBinding?.key) {
      setSelectedConnectionBindingKey(sheetBinding.key);
    }
    setDecisionNotice('Укажите Google-таблицу и лист со списком поездок, затем сохраните источник и запустите тест ещё раз.');
    setWorkspaceMode('connections');
  };
  const openGoogleAccessReconnect = () => {
    const params = new URLSearchParams({
      focus: 'google_sheets',
      return_to: '/dashboard/agents',
    });
    window.location.href = `/dashboard/settings/integrations?${params.toString()}`;
  };
  const runEmployeePrimaryAction = () => {
    if (!selectedBlueprint || !selectedEmployeeAction) {
      return;
    }
    if (selectedEmployeeAction.kind === 'run_test') {
      void startRun(selectedBlueprint);
      return;
    }
    if (selectedEmployeeAction.kind === 'run_work') {
      void executeRun(selectedBlueprint, selectedEmployeeAction.versionId || '');
      return;
    }
    if (selectedEmployeeAction.kind === 'run_similar') {
      setCloneFromBlueprintId(selectedBlueprint.id);
      setDialogBuilderInput(selectedBlueprint.description || selectedBlueprint.latest_goal || selectedBlueprint.name);
      setAgentPrompt(selectedBlueprint.description || selectedBlueprint.latest_goal || selectedBlueprint.name);
      setBuilderExecutionMode('one_off');
      setBuilderExecutionModeConfirmed(false);
      setCreateWizardOpen(true);
      return;
    }
    if (selectedEmployeeAction.kind === 'confirm_mode') {
      setWorkspaceMode('settings');
      return;
    }
    if (selectedEmployeeAction.kind === 'enable' && selectedEmployeeAction.versionId) {
      void activateVersion(selectedEmployeeAction.versionId, 'activate');
      return;
    }
    if (selectedEmployeeAction.kind === 'configure_schedule') {
      setWorkspaceMode('overview');
      return;
    }
    if (selectedEmployeeAction.targetMode === 'results') {
      const latestRunId = blueprintDetails?.runs?.[0]?.id || selectedBlueprint.last_run_id || '';
      if (latestRunId && activeRun?.id !== latestRunId) {
        void loadRun(latestRunId);
        return;
      }
    }
    setWorkspaceMode(selectedEmployeeAction.targetMode);
  };

  return (
    <div className="space-y-5">
      <DashboardPageHeader
        eyebrow="LocalOS"
        title="Агенты"
        description="Задачи, которые LocalOS выполняет один раз, по кнопке или по расписанию."
        icon={Bot}
        actions={(
          <>
            <span className="inline-flex min-h-8 items-center rounded-full bg-slate-100 px-3 text-xs font-semibold text-slate-600 ring-1 ring-slate-200">Beta</span>
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

      <Dialog open={createWizardOpen} onOpenChange={(open) => {
        setCreateWizardOpen(open);
        if (!open && !actionLoading) {
          setDialogBuilderInput('');
          setDialogBuilderReply('');
          setDialogBuilderSession(null);
          setSelectedBuilderConnectionBindings({});
          setSelectedBuilderProviderRoutes({});
          setAcceptedBuilderCompilerPlan(false);
          setAcceptedBuilderProviderRoutes(false);
          setBuilderExecutionMode('manual');
          setBuilderExecutionModeConfirmed(false);
          setCloneFromBlueprintId('');
          setAgentPrompt('');
          setCreateWizardStep(0);
          setBuilderCategory('documents');
          setBuilderDataSources('файл документа, ручной контекст, профиль бизнеса');
          setBuilderExtractionRules('ключевые условия, сроки, суммы, ответственность, спорные места');
          setBuilderProcessingRules('не придумывать факты, ссылаться только на добавленные данные, отдельно показывать риски');
          setBuilderOutputFormat('краткий отчёт: summary, риски, что уточнить, черновик письма при необходимости');
          setBuilderManualControl('перед использованием результата и перед любым внешним действием');
          setBuilderSourceName('');
          setBuilderSourceText('');
          setBuilderFileSource(null);
          setBuilderInternalSource('business_profile');
        }
      }}>
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
            executionMode={builderExecutionMode}
            executionModeConfirmed={builderExecutionModeConfirmed}
            scheduleTime={scheduleTime}
            scheduleTimezone={scheduleTimezone}
            onExecutionModeChange={(mode) => {
              setBuilderExecutionMode(mode);
              setBuilderExecutionModeConfirmed(false);
            }}
            onExecutionModeConfirm={() => setBuilderExecutionModeConfirmed(true)}
            onScheduleTimeChange={setScheduleTime}
            onScheduleTimezoneChange={setScheduleTimezone}
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
          <AgentExecutionModePanel
            mode={builderExecutionMode}
            confirmationRequired={!builderExecutionModeConfirmed}
            time={scheduleTime}
            timezone={scheduleTimezone}
            actionLoading={false}
            onModeChange={(mode) => {
              setBuilderExecutionMode(mode);
              setBuilderExecutionModeConfirmed(false);
            }}
            onTimeChange={setScheduleTime}
            onTimezoneChange={setScheduleTimezone}
            onSave={() => setBuilderExecutionModeConfirmed(true)}
          />
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
            canCreate={Boolean(currentBusinessId && agentPrompt.trim() && builderExecutionModeConfirmed)}
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

      <Dialog open={Boolean(deleteCandidate)} onOpenChange={(open) => {
        if (!open && !actionLoading) {
          setDeleteCandidate(null);
        }
      }}>
        <DialogContent className="max-w-lg rounded-2xl">
          <DialogHeader>
            <DialogTitle>Убрать агента из списка?</DialogTitle>
            <DialogDescription>
              Агент “{deleteCandidate?.name || 'выбранный агент'}” исчезнет из основного списка. История запусков, решения и результаты останутся в архиве LocalOS.
            </DialogDescription>
          </DialogHeader>
          <div className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm leading-6 text-amber-950">
            Это не запускает внешние действия и не удаляет уже сохранённые результаты работы агента.
          </div>
          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <Button type="button" variant="outline" onClick={() => setDeleteCandidate(null)} disabled={actionLoading}>
              Отмена
            </Button>
            <Button
              type="button"
              className="bg-red-600 text-white hover:bg-red-700"
              onClick={() => deleteAgent(deleteCandidate)}
              disabled={actionLoading || !deleteCandidate}
            >
              {actionLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Trash2 className="mr-2 h-4 w-4" />}
              Убрать из списка
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {error ? (
        <DashboardActionPanel
          title="Ошибка"
          description={error}
          tone="amber"
        />
      ) : null}

      {decisionNotice ? (
        <DashboardActionPanel
          title="Готово"
          description={decisionNotice}
          tone="sky"
        />
      ) : null}

      {false && recentCreatedAgentName ? (
        <div className="space-y-3">
          <DashboardActionPanel
            title={userFacingAgentTechText(recentPostCreateHandoff?.title || 'Агент создан')}
            description={userFacingAgentTechText(recentPostCreateHandoff?.description || `${recentCreatedAgentName} выбран ниже. Проверьте данные агента, активную версию и запустите его из карточки.`)}
            tone={recentPostCreateHandoff?.status === 'needs_connections' ? 'amber' : 'sky'}
            actions={(
              <div className="flex flex-wrap gap-2">
                {recentPostCreateHandoff?.workspace_mode === 'connections' ? (
                  <Button type="button" size="sm" onClick={() => setWorkspaceMode('connections')}>
                    Открыть подключения
                  </Button>
                ) : null}
                {postCreateReadyForRun ? (
                  <Button type="button" size="sm" onClick={() => (selectedBlueprint ? startRun(selectedBlueprint) : setWorkspaceMode('run'))}>
                    Запустить тест
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
	          {showPostCreateConnectionDetails && recentPostCreateHandoff?.next_binding ? (
	            <div className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-3 text-xs leading-5 text-amber-950">
	              <div className="font-semibold">
	                Следующий доступ: {recentPostCreateHandoff.next_binding.title || connectorLabel(recentPostCreateHandoff.next_binding.provider)}
	              </div>
	              <div className="mt-1">
	                {userFacingAgentTechText(recentPostCreateHandoff.next_binding.route_summary || recentPostCreateHandoff.next_binding.explanation || 'Откройте подключения и завершите настройку этого шага.')}
	              </div>
	              {recentPostCreateHandoff.next_route?.label || recentPostCreateHandoff.next_route?.primary_cta ? (
	                <div className="mt-2 rounded-lg bg-white/80 px-2 py-1.5 text-amber-900 ring-1 ring-amber-100">
	                  <ProviderActionPill
	                    route={recentPostCreateHandoff.next_route}
	                    disabled={actionLoading || !recentPostCreateHandoff.next_binding_key}
	                    onChoose={recentPostCreateHandoff.next_binding_key ? () => chooseProviderRoute(recentPostCreateHandoff.next_binding_key || '', recentPostCreateHandoff.next_route || {}) : undefined}
	                  />
	                  {providerActionDescription(recentPostCreateHandoff.next_route) ? (
	                    <div className="mt-1">{userFacingAgentTechText(providerActionDescription(recentPostCreateHandoff.next_route))}</div>
	                  ) : null}
	                </div>
	              ) : null}
	            </div>
	          ) : null}
	          {showPostCreateConnectionDetails ? (
	            <AgentConnectionPlanPanel
	              connectionPlan={recentPostCreateHandoff?.connection_plan || agentConnectionPlan}
              availableIntegrations={availableAgentIntegrations}
              actionLoading={actionLoading}
              onAttachExistingIntegration={attachExistingAgentIntegration}
              onConfigureBinding={setSelectedConnectionBindingKey}
              onChooseProviderRoute={chooseProviderRoute}
            />
	          ) : null}
        </div>
      ) : null}

      {!currentBusinessId ? (
        <DashboardEmptyState
          title="Сначала выберите бизнес"
          description="Агенты всегда привязаны к конкретному бизнесу и его правам доступа."
        />
      ) : null}

      {currentBusinessId ? (
        <div className="space-y-4">
          <section className="rounded-2xl bg-white px-4 py-3 shadow-[0_1px_2px_rgba(15,23,42,0.06),0_0_0_1px_rgba(15,23,42,0.08)]">
            <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-sm text-slate-600">
              <span className="font-semibold text-slate-950">Сегодня</span>
              <span><strong className="tabular-nums text-slate-950">{todaySummary.completedRuns}</strong> выполнено</span>
              <span><strong className="tabular-nums text-slate-950">{todaySummary.preparedArtifacts}</strong> результатов</span>
              <span><strong className="tabular-nums text-slate-950">{todaySummary.pendingApprovals}</strong> ждут решения</span>
              {todaySummary.failedRuns ? <span className="text-rose-700"><strong className="tabular-nums">{todaySummary.failedRuns}</strong> ошибок</span> : null}
            </div>
          </section>
          <section className="rounded-2xl bg-white p-3 shadow-[0_1px_2px_rgba(15,23,42,0.06),0_0_0_1px_rgba(15,23,42,0.08)]">
            <div className="grid gap-3 lg:grid-cols-[minmax(16rem,1fr)_auto] lg:items-center">
              <label className="relative block">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                <input
                  type="search"
                  value={agentSearch}
                  onChange={(event) => setAgentSearch(event.target.value)}
                  placeholder="Найти агента"
                  className="min-h-10 w-full rounded-lg bg-slate-50 pl-10 pr-3 text-sm text-slate-950 outline-none shadow-[inset_0_0_0_1px_rgba(15,23,42,0.08)] focus:shadow-[inset_0_0_0_2px_rgba(249,115,22,0.55)]"
                />
              </label>
              <div className="grid grid-cols-2 gap-1 rounded-xl bg-slate-100 p-1 sm:flex">
                {([
                  ['all', 'Все'],
                  ['working', 'Работают'],
                  ['attention', 'Нужны действия'],
                  ['completed', 'Выполненные'],
                ]).map(([value, label]) => (
                  <button
                    key={value}
                    type="button"
                    onClick={() => setAgentRegistryFilter(value === 'working' || value === 'attention' || value === 'completed' ? value : 'all')}
                    className={cn('min-h-9 rounded-lg px-3 text-xs font-semibold transition-[background-color,color,box-shadow] active:scale-[0.96]', agentRegistryFilter === value ? 'bg-white text-slate-950 shadow-sm' : 'text-slate-600 hover:text-slate-950')}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>
          </section>
          <div className="grid gap-5 lg:grid-cols-[28rem_minmax(0,1fr)]">
            <EmployeeAgentsList
              blueprints={filteredBlueprints}
              detailsById={employeeListDetailsById}
              selectedBlueprintId={selectedBlueprint?.id || null}
              selectedActiveRun={activeRun}
              selectedPendingApproval={selectedPendingApproval}
              loading={loading}
              onOpen={(blueprint) => {
                setSelectedBlueprintId(blueprint.id);
                setActiveRun(null);
                setDecisionNotice(null);
                setWorkspaceMode('overview');
                setRecentCreatedAgentName('');
                setRecentPostCreateHandoff(null);
              }}
            />

            <main className="min-w-0 space-y-4">
              {selectedBlueprint && selectedEmployeeAction && !runAnimation ? (
                <nav className="flex gap-1 overflow-x-auto rounded-xl bg-slate-100 p-1" aria-label="Разделы агента">
                  {([
                    ['overview', 'Обзор'],
                    ['results', 'Результаты'],
                    ['settings', 'Настройка'],
                  ]).map(([value, label]) => (
                    <button
                      key={value}
                      type="button"
                      onClick={() => setWorkspaceMode(value === 'results' || value === 'settings' ? value : 'overview')}
                      className={cn('min-h-10 shrink-0 rounded-lg px-4 text-sm font-semibold transition-[background-color,color,box-shadow] active:scale-[0.96]', workspaceMode === value || (value === 'overview' && workspaceMode === 'run') ? 'bg-white text-slate-950 shadow-sm' : 'text-slate-600 hover:text-slate-950')}
                    >
                      {label}
                    </button>
                  ))}
                </nav>
              ) : null}
              {selectedBlueprint && selectedEmployeeAction ? (
                runAnimation?.blueprintId === selectedBlueprint.id ? (
                  <AgentRunProgressPanel
                    animation={runAnimation}
                    onRetry={() => runAnimation.kind === 'work'
                      ? executeRun(selectedBlueprint, selectedEmployeeAction.versionId || '')
                      : startRun(selectedBlueprint)}
                  />
                ) : workspaceMode === 'overview' || workspaceMode === 'run' ? (
                  <div className="space-y-4">
                    <EmployeeAgentOverviewPanel
                      blueprint={selectedBlueprint}
                      details={blueprintDetails}
                      activeRun={activeRun}
                      pendingApproval={selectedPendingApproval}
                      action={selectedEmployeeAction}
                      actionLoading={actionLoading}
                      onPrimaryAction={runEmployeePrimaryAction}
                      onOpenAdvanced={() => setWorkspaceMode('settings')}
                    />
                    {selectedEmployeeAction.kind === 'configure_schedule' ? (
                      <AgentScheduleSetupPanel
                        time={scheduleTime}
                        timezone={scheduleTimezone}
                        actionLoading={actionLoading}
                        onTimeChange={setScheduleTime}
                        onTimezoneChange={setScheduleTimezone}
                        onSave={saveSchedule}
                      />
                    ) : null}
                    {selectedEmployeeAction.kind === 'confirm_mode' ? (
                      <AgentExecutionModePanel
                        mode={selectedExecutionMode}
                        confirmationRequired={Boolean(blueprintDetails?.execution_mode_confirmation_required || selectedBlueprint.execution_mode_confirmation_required)}
                        time={scheduleTime}
                        timezone={scheduleTimezone}
                        actionLoading={actionLoading}
                        onModeChange={setSelectedExecutionMode}
                        onTimeChange={setScheduleTime}
                        onTimezoneChange={setScheduleTimezone}
                        onSave={saveExecutionMode}
                      />
                    ) : null}
                  </div>
                ) : workspaceMode === 'results' ? (
                  selectedResultRun || selectedPendingApproval ? (
                    <EmployeeTestResultPanel
                      activeRun={selectedResultRun}
                      pendingApproval={selectedPendingApproval}
                      actionLoading={actionLoading}
                      needsScenarioRebuild={resultNeedsScenarioRebuild}
                      needsGoogleSheetsSetup={resultNeedsGoogleSheetsSetup}
                      needsGoogleAccessReconnect={resultNeedsGoogleAccessReconnect}
                      googleAccessJustConnected={resultGoogleAccessReconnected}
                      nextAction={selectedEmployeeAction}
                      onApprove={() => decideApproval('approve')}
                      onReject={() => decideApproval('reject')}
                      onRunAgain={() => selectedResultRun?.input_json?.preview_mode === false
                        ? executeRun(selectedBlueprint, selectedResultRun.blueprint_version_id || '')
                        : startRun(selectedBlueprint)}
                      onRebuildScenario={rebuildScenarioAndRun}
                      onOpenGoogleSheetsSetup={openGoogleSheetsSourceSetup}
                      onOpenGoogleAccessReconnect={openGoogleAccessReconnect}
                      onNextAction={runEmployeePrimaryAction}
                    />
                  ) : (
                    <EmployeeHistoryPanel
                      details={blueprintDetails}
                      activeRun={activeRun}
                    />
                  )
                ) : workspaceMode === 'settings' ? (
                  <div className="space-y-4">
                    <AgentExecutionModePanel
                      mode={selectedExecutionMode}
                      confirmationRequired={Boolean(blueprintDetails?.execution_mode_confirmation_required || selectedBlueprint.execution_mode_confirmation_required)}
                      time={scheduleTime}
                      timezone={scheduleTimezone}
                      actionLoading={actionLoading}
                      onModeChange={setSelectedExecutionMode}
                      onTimeChange={setScheduleTime}
                      onTimezoneChange={setScheduleTimezone}
                      onSave={saveExecutionMode}
                    />
                    <AgentDetailPanel
                  mode={workspaceMode}
                  blueprint={selectedBlueprint}
                  blueprintDetails={blueprintDetails}
                  activeRun={activeRun}
                  availablePersonaAgents={availablePersonaAgents}
                  pendingApproval={selectedPendingApproval}
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
                  browserTargetUrls={browserTargetUrls}
                  browserDailyCap={browserDailyCap}
                  telegramBotMode={telegramBotMode}
                  telegramDailyCap={telegramDailyCap}
                  whatsappChannelMode={whatsappChannelMode}
                  whatsappDailyCap={whatsappDailyCap}
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
                  onBrowserTargetUrlsChange={setBrowserTargetUrls}
                  onBrowserDailyCapChange={setBrowserDailyCap}
                  onTelegramBotModeChange={setTelegramBotMode}
                  onTelegramDailyCapChange={setTelegramDailyCap}
                  onWhatsappChannelModeChange={setWhatsappChannelMode}
                  onWhatsappDailyCapChange={setWhatsappDailyCap}
                  onMatonAuthRefChange={setMatonAuthRef}
                  onMatonChannelChange={setMatonChannel}
                  onMatonDailyCapChange={setMatonDailyCap}
                  onProcessRowValuesChange={setProcessRowValues}
                  onProcessPreviewMessageChange={setProcessPreviewMessage}
                  onSaveSheetIntegration={saveSheetIntegration}
                  onSaveBrowserUseIntegration={saveBrowserUseIntegration}
                  onSaveTelegramIntegration={saveTelegramIntegration}
                  onSaveWhatsappIntegration={saveWhatsappIntegration}
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
                  </div>
                ) : (
                  <AgentDetailPanel
                  mode={workspaceMode}
                  blueprint={selectedBlueprint}
                  blueprintDetails={blueprintDetails}
                  activeRun={activeRun}
                  availablePersonaAgents={availablePersonaAgents}
                  pendingApproval={selectedPendingApproval}
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
                  browserTargetUrls={browserTargetUrls}
                  browserDailyCap={browserDailyCap}
                  telegramBotMode={telegramBotMode}
                  telegramDailyCap={telegramDailyCap}
                  whatsappChannelMode={whatsappChannelMode}
                  whatsappDailyCap={whatsappDailyCap}
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
                  onBrowserTargetUrlsChange={setBrowserTargetUrls}
                  onBrowserDailyCapChange={setBrowserDailyCap}
                  onTelegramBotModeChange={setTelegramBotMode}
                  onTelegramDailyCapChange={setTelegramDailyCap}
                  onWhatsappChannelModeChange={setWhatsappChannelMode}
                  onWhatsappDailyCapChange={setWhatsappDailyCap}
                  onMatonAuthRefChange={setMatonAuthRef}
                  onMatonChannelChange={setMatonChannel}
                  onMatonDailyCapChange={setMatonDailyCap}
                  onProcessRowValuesChange={setProcessRowValues}
                  onProcessPreviewMessageChange={setProcessPreviewMessage}
                  onSaveSheetIntegration={saveSheetIntegration}
                  onSaveBrowserUseIntegration={saveBrowserUseIntegration}
                  onSaveTelegramIntegration={saveTelegramIntegration}
                  onSaveWhatsappIntegration={saveWhatsappIntegration}
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
                )
              ) : (
                <DashboardEmptyState
                  title="Создайте первого сотрудника"
                  description="После создания LocalOS сразу откроет карточку и покажет один следующий шаг."
                />
              )}
            </main>
          </div>
        </div>
      ) : null}

      {false && currentBusinessId ? (
        <div className="space-y-5">
          <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="text-sm font-semibold text-slate-950">Агенты</div>
                <div className="mt-1 text-xs leading-5 text-slate-500">
                  Выберите работу, которую LocalOS должен вести для бизнеса.
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
                      businessStatus={buildAgentBusinessStatus(blueprint, selected ? blueprintDetails : agentDetailsById[blueprint.id])}
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
                        setWorkspaceMode('results');
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
                      onDelete={() => requestDeleteAgent(blueprint)}
                      actionLoading={actionLoading}
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
                pendingApproval={selectedPendingApproval}
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
                browserTargetUrls={browserTargetUrls}
                browserDailyCap={browserDailyCap}
                telegramBotMode={telegramBotMode}
                telegramDailyCap={telegramDailyCap}
                whatsappChannelMode={whatsappChannelMode}
                whatsappDailyCap={whatsappDailyCap}
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
                onBrowserTargetUrlsChange={setBrowserTargetUrls}
                onBrowserDailyCapChange={setBrowserDailyCap}
                onTelegramBotModeChange={setTelegramBotMode}
                onTelegramDailyCapChange={setTelegramDailyCap}
                onWhatsappChannelModeChange={setWhatsappChannelMode}
                onWhatsappDailyCapChange={setWhatsappDailyCap}
                onMatonAuthRefChange={setMatonAuthRef}
                onMatonChannelChange={setMatonChannel}
                onMatonDailyCapChange={setMatonDailyCap}
                onProcessRowValuesChange={setProcessRowValues}
                onProcessPreviewMessageChange={setProcessPreviewMessage}
                onSaveSheetIntegration={saveSheetIntegration}
                onSaveBrowserUseIntegration={saveBrowserUseIntegration}
                onSaveTelegramIntegration={saveTelegramIntegration}
                onSaveWhatsappIntegration={saveWhatsappIntegration}
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
        <details className="min-w-0 overflow-hidden rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
          <summary className="cursor-pointer text-sm font-semibold text-slate-800">
            Служебные инструменты миграции и поддержки
          </summary>
          <div className="mt-4 min-w-0 space-y-5">
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

const BuilderProductSteps = ({
  hasPreview,
  readyForDraft,
  created,
}: {
  hasPreview: boolean;
  readyForDraft: boolean;
  created: boolean;
}) => {
  const steps = [
    { key: 'describe', label: 'Описание задачи', done: hasPreview || readyForDraft || created },
    { key: 'prepared', label: 'Что подготовил LocalOS', done: hasPreview || readyForDraft || created },
    { key: 'check', label: 'Проверка', done: readyForDraft || created },
    { key: 'publish', label: 'Включение', done: created },
  ];
  return (
    <div className="grid gap-2 md:grid-cols-4">
      {steps.map((step, index) => (
        <div
          key={step.key}
          className={cn(
            'rounded-xl px-3 py-2 text-sm ring-1',
            step.done ? 'bg-emerald-50 text-emerald-950 ring-emerald-100' : index === 0 ? 'bg-sky-50 text-sky-950 ring-sky-100' : 'bg-slate-50 text-slate-600 ring-slate-100',
          )}
        >
          <div className="flex items-center gap-2 font-semibold">
            <span className={cn(
              'flex h-5 w-5 items-center justify-center rounded-full text-[11px]',
              step.done ? 'bg-emerald-100 text-emerald-700' : 'bg-white text-slate-500 ring-1 ring-slate-200',
            )}>
              {step.done ? <CheckCircle2 className="h-3.5 w-3.5" /> : index + 1}
            </span>
            {step.label}
          </div>
        </div>
      ))}
    </div>
  );
};

const BuilderTrustBlock = ({ ready }: { ready: boolean }) => (
  <div className={cn(
    'mt-4 rounded-xl px-3 py-3 text-sm leading-6 ring-1',
    ready ? 'bg-emerald-50 text-emerald-950 ring-emerald-100' : 'bg-slate-50 text-slate-700 ring-slate-100',
  )}>
    <div className="flex items-center gap-2 font-semibold text-slate-950">
      <ShieldCheck className="h-4 w-4 text-emerald-700" />
      Почему этому можно доверять
    </div>
    <div className="mt-2 grid gap-2 md:grid-cols-2">
      {[
        'Используются только разрешённые действия',
        'Подключения будут проверены перед запуском',
        'Перед внешним действием требуется подтверждение',
        'Агент будет использовать именно опубликованный сценарий',
        'Агент не изменит сценарий самостоятельно',
      ].map((item) => (
        <div key={item} className="flex items-start gap-2 rounded-lg bg-white/80 px-2.5 py-2 ring-1 ring-current/10">
          <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
          <span>{item}</span>
        </div>
      ))}
    </div>
  </div>
);

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
  executionMode,
  executionModeConfirmed,
  scheduleTime,
  scheduleTimezone,
  onAcceptCompilerPlan,
  onAcceptProviderRoutes,
  onExecutionModeChange,
  onExecutionModeConfirm,
  onScheduleTimeChange,
  onScheduleTimezoneChange,
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
  executionMode: AgentExecutionMode;
  executionModeConfirmed: boolean;
  scheduleTime: string;
  scheduleTimezone: string;
  onAcceptCompilerPlan: () => void;
  onAcceptProviderRoutes: () => void;
  onExecutionModeChange: (mode: AgentExecutionMode) => void;
  onExecutionModeConfirm: () => void;
  onScheduleTimeChange: (value: string) => void;
  onScheduleTimezoneChange: (value: string) => void;
  onSelectConnectionBinding: (bindingKey: string, integrationId: string) => void;
  onSelectProviderRoute: (bindingKey: string, routeProvider: string) => void;
}) => {
  const preview = session?.preview || null;
  const nextStepRef = useRef<HTMLDivElement | null>(null);
  const previousMessageCountRef = useRef(0);
  const questions = session?.missing_questions || [];
  const messages = session?.messages || [];
  const estimatedCredits = Number(preview?.cost_preview?.estimated_credits || 0);
  const connectionSummaryItems = preview?.connection_summary?.items || [];
  const requiredConnectionChoices = connectionSummaryItems.filter((item) => item.action === 'choose_existing' && item.key && (item.connections?.length || 0) > 1);
  const missingConnectionChoices = requiredConnectionChoices.filter((item) => !selectedConnectionBindings[item.key || '']);
  const requiredProviderRouteKeys = builderRequiredProviderRouteKeys(preview);
  const missingProviderRouteKeys = requiredProviderRouteKeys.filter((key) => !selectedProviderRoutes[key]);
  const providerRoutesRequireConfirmation = requiredProviderRouteKeys.length > 0;
  const missingProviderRouteConfirmation = providerRoutesRequireConfirmation && (!acceptedProviderRoutes || missingProviderRouteKeys.length > 0);
  const blockingQuestions = builderBlockingQuestions(questions);
  const currentInputFingerprint = input.trim().toLowerCase().slice(0, 60);
  const previewUnderstoodTask = String(preview?.understood_task || '').trim().toLowerCase();
  const previewIsStale = Boolean(
    session
    && currentInputFingerprint
    && previewUnderstoodTask
    && !previewUnderstoodTask.includes(currentInputFingerprint),
  );
  const showInlineConnectionSetup = Boolean(missingConnectionChoices.length || missingProviderRouteKeys.length || missingProviderRouteConfirmation);
  const setupFlowNextStep = String(preview?.setup_flow?.next_step || '');
  const setupFlowAllowsDraft = preview?.setup_flow?.can_create_draft !== false || setupFlowNextStep.startsWith('create_draft_then');
  const canCreateDraft = setupFlowAllowsDraft
    && !previewIsStale
    && executionModeConfirmed
    && (executionMode !== 'scheduled' || Boolean(scheduleTime && scheduleTimezone));
  const createBlockers: Array<{ key: string; label: string }> = [];
  const addCreateBlocker = (key: string, label: string) => {
    const cleanKey = key.trim();
    const cleanLabel = label.trim();
    if (!cleanKey || !cleanLabel || createBlockers.some((item) => item.key === cleanKey || item.label === cleanLabel)) {
      return;
    }
    createBlockers.push({ key: cleanKey, label: cleanLabel });
  };
  blockingQuestions.slice(0, 4).forEach((question) => {
    addCreateBlocker(`question:${question.key || question.question}`, question.question || 'Ответьте на уточнение.');
  });
  missingConnectionChoices.slice(0, 4).forEach((item) => {
    addCreateBlocker(`choice:${item.key || item.provider}`, `Выберите подключение ${item.title || connectorLabel(item.provider)}.`);
  });
  if (missingProviderRouteKeys.length) {
    addCreateBlocker('provider_route_selection', `Выберите способ доставки для: ${missingProviderRouteKeys.map((item) => userFacingAgentTechText(humanizeMeta(item))).join(', ')}.`);
  } else if (missingProviderRouteConfirmation) {
    addCreateBlocker('provider_route_confirmation', 'Подтвердите выбранные способы подключения.');
  }
  preview?.setup_flow?.activation_blockers?.slice(0, 4).forEach((item) => {
    addCreateBlocker(`blocker:${item.type || item.provider || item.message}`, item.message || connectorLabel(item.provider));
  });
  preview?.connection_summary?.forbidden?.slice(0, 2).forEach((item) => {
    addCreateBlocker(`forbidden:${item.term || item.reason}`, item.reason || 'Запрос запрещён правилами безопасности LocalOS.');
  });
  preview?.connection_summary?.unsupported?.slice(0, 2).forEach((item) => {
    addCreateBlocker(`unsupported:${item.capability || item.reason}`, item.reason || 'Нет разрешённого способа подключения.');
  });
  const createDraftLabel = preview?.setup_flow?.post_create_status === 'ready_for_preview'
    ? 'Создать агента и открыть тест'
    : missingConnectionChoices.length
      ? 'Сначала выберите подключение'
      : missingProviderRouteKeys.length
        ? 'Сначала выберите способ'
        : missingProviderRouteConfirmation
          ? 'Подтвердите способы'
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
    previewIsStale,
  });
  const firstQuestion = blockingQuestions[0] || null;
  const extraQuestions = blockingQuestions.slice(1);
  const previewTaskText = preview?.understood_task || input;
  const previewDataText = builderPreviewDataText(preview, previewTaskText);
  const previewResultText = userFacingAgentTechText(preview?.output_format || 'результат уточним после подключения данных');
  const previewControlText = userFacingAgentTechText(preview?.manual_control || 'перед внешним действием');
  const setupBlockerText = userFacingAgentTechText(previewIsStale
    ? builderDecision.description
    : firstQuestion?.question
      || missingConnectionChoices[0]?.title
      || preview?.setup_flow?.next_step_description
      || builderDecision.description);
  const canUsePrimaryAction = builderDecision.action === 'answer'
    ? Boolean(reply.trim())
    : builderDecision.action === 'create' || setupFlowAllowsDraft
      ? canCreateDraft
      : false;
  const primaryActionLabel = builderDecision.action === 'answer'
    ? 'Ответить'
    : canCreateDraft || setupFlowAllowsDraft
      ? createDraftLabel
      : builderDecision.cta || 'Продолжить настройку';
  useEffect(() => {
    const messageCount = messages.length;
    if (!session || messageCount === previousMessageCountRef.current) {
      return;
    }
    previousMessageCountRef.current = messageCount;
    window.setTimeout(() => {
      nextStepRef.current?.scrollIntoView({ block: 'start', behavior: 'smooth' });
    }, 50);
  }, [messages.length, session]);
  return (
    <div className="space-y-4 rounded-2xl border border-slate-200 bg-white p-4">
      <BuilderProductSteps
        hasPreview={Boolean(preview)}
        readyForDraft={canCreateDraft}
        created={false}
      />
      <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto]">
        <textarea
          className="min-h-28 resize-none rounded-xl border border-slate-200 px-3 py-2 text-sm leading-6 outline-none transition focus:border-slate-400"
          value={input}
          onChange={(event) => onInputChange(event.target.value)}
          placeholder="Например: мне нужен агент, который проверяет договоры, находит риски и готовит краткий отчёт"
        />
        <Button type="button" onClick={onStart} disabled={actionLoading || !input.trim()}>
          {actionLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Sparkles className="mr-2 h-4 w-4" />}
          {session ? 'Обновить понимание' : 'Начать диалог'}
        </Button>
      </div>

      {session ? (
        <div className="space-y-4">
          <section className="rounded-2xl bg-white p-4 shadow-[0_0_0_1px_rgba(15,23,42,0.10)]">
            <div className="text-sm font-semibold text-slate-950">Как запускать агента</div>
            <div className="mt-1 text-xs leading-5 text-slate-500">LocalOS предложил вариант. Подтвердите его или выберите другой.</div>
            <div className="mt-3 grid gap-2 sm:grid-cols-3">
              {agentExecutionModeOptions.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => onExecutionModeChange(option.value)}
                  className={cn('min-h-20 rounded-xl px-3 py-2 text-left shadow-[0_0_0_1px_rgba(15,23,42,0.10)] transition-[background-color,color,box-shadow] active:scale-[0.96]', executionMode === option.value ? 'bg-slate-950 text-white' : 'bg-slate-50 text-slate-950')}
                >
                  <span className="block text-sm font-semibold">{agentExecutionModeLabel(option.value)}</span>
                  <span className={cn('mt-1 block text-xs leading-5', executionMode === option.value ? 'text-slate-300' : 'text-slate-500')}>{option.description}</span>
                </button>
              ))}
            </div>
            {executionMode === 'scheduled' ? (
              <div className="mt-3 grid gap-2 sm:grid-cols-2">
                <input type="time" value={scheduleTime} onChange={(event) => onScheduleTimeChange(event.target.value)} className="min-h-10 rounded-lg px-3 shadow-[inset_0_0_0_1px_rgba(15,23,42,0.14)] outline-none" aria-label="Время запуска" />
                <select value={scheduleTimezone} onChange={(event) => onScheduleTimezoneChange(event.target.value)} className="min-h-10 rounded-lg px-3 shadow-[inset_0_0_0_1px_rgba(15,23,42,0.14)] outline-none" aria-label="Часовой пояс">
                  <option value="Europe/Tallinn">Tallinn</option>
                  <option value="Europe/Moscow">Москва</option>
                  <option value="Europe/Helsinki">Helsinki</option>
                  <option value="Europe/Riga">Riga</option>
                </select>
              </div>
            ) : null}
            <Button type="button" size="sm" variant={executionModeConfirmed ? 'outline' : 'default'} className="mt-3 active:scale-[0.96] transition-transform" onClick={onExecutionModeConfirm} disabled={executionMode === 'scheduled' && (!scheduleTime || !scheduleTimezone)}>
              <CheckCircle2 className="mr-2 h-4 w-4" />
              {executionModeConfirmed ? 'Тип подтверждён' : 'Подтвердить тип'}
            </Button>
          </section>
          <div className={cn(
            'rounded-2xl border px-4 py-4',
            canCreateDraft ? 'border-emerald-200 bg-emerald-50' : 'border-amber-200 bg-amber-50',
          )} ref={nextStepRef}>
            <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
              <div className="min-w-0">
                <div className={cn('text-xs font-semibold uppercase', canCreateDraft ? 'text-emerald-700' : 'text-amber-700')}>
                  Сейчас нужно
                </div>
                <div className={cn('mt-1 text-lg font-semibold leading-7', canCreateDraft ? 'text-emerald-950' : 'text-amber-950')}>
                  {canCreateDraft ? 'Создать черновик агента' : builderDecision.title}
                </div>
                <div className={cn('mt-2 max-w-4xl text-sm leading-6', canCreateDraft ? 'text-emerald-900' : 'text-amber-950')}>
                  {canCreateDraft ? 'LocalOS понял задачу и готов сохранить первую версию. Подключения и тест будут следующим шагом.' : setupBlockerText}
                </div>
                {extraQuestions.length ? (
                  <details className="mt-2 text-xs leading-5 text-amber-900">
                    <summary className="cursor-pointer font-medium">Ещё {extraQuestions.length} уточнения</summary>
                    <div className="mt-1 space-y-1">
                      {extraQuestions.map((question) => (
	                        <div key={question.key || question.question}>{userFacingAgentTechText(question.question)}</div>
                      ))}
                    </div>
                  </details>
                ) : null}
              </div>
              {builderDecision.action === 'answer' || (builderDecision.action === 'none' && !setupFlowAllowsDraft) ? null : (
                <Button
                  type="button"
                  onClick={() => {
                    if (canCreateDraft || setupFlowAllowsDraft || builderDecision.action === 'create') {
                      onCreate();
                    }
                  }}
                  disabled={actionLoading || !canUsePrimaryAction}
                  className="shrink-0"
                >
                  {actionLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : canCreateDraft ? <CheckCircle2 className="mr-2 h-4 w-4" /> : <MessageSquareText className="mr-2 h-4 w-4" />}
                  {primaryActionLabel}
                </Button>
              )}
            </div>
            {firstQuestion ? (
              <div className="mt-4 grid gap-2 md:grid-cols-[minmax(0,1fr)_auto]">
                <textarea
                  className="min-h-16 resize-none rounded-xl border border-amber-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-amber-400"
                  value={reply}
                  onChange={(event) => onReplyChange(event.target.value)}
                  placeholder="Ответьте одним сообщением"
                />
                <Button type="button" variant="outline" className="bg-white" onClick={onSendReply} disabled={actionLoading || !reply.trim()}>
                  Ответить
                </Button>
              </div>
            ) : null}
          </div>

          {showInlineConnectionSetup ? (
            <div className="rounded-2xl border border-sky-200 bg-sky-50/70 p-3">
              <div className="px-1 pb-1">
                <div className="text-sm font-semibold text-slate-950">Выберите способ работы агента</div>
                <div className="mt-1 text-xs leading-5 text-slate-600">
                  Это обязательный шаг перед созданием: LocalOS должен явно знать, через какой безопасный канал читать данные или доставлять результат. Рекомендованный способ уже выбран, если подходит только один вариант.
                </div>
              </div>
              <BuilderRequiredConnectionsPanel
                preview={preview}
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
              {missingConnectionChoices.length ? (
                <div className="mt-3 rounded-xl border border-amber-200 bg-white px-3 py-2 text-xs leading-5 text-amber-950">
                  Выберите, какие уже подключённые сервисы использовать: {missingConnectionChoices.map((item) => item.title || connectorLabel(item.provider)).join(', ')}.
                </div>
              ) : null}
            </div>
          ) : null}

          <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="text-sm font-semibold text-slate-950">Что понял LocalOS</div>
                <div className="mt-1 text-xs text-slate-500">Короткая проверка перед созданием. Подробности ниже.</div>
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

            <div className="mt-4 grid gap-3 lg:grid-cols-3">
              <div className="rounded-xl bg-white px-3 py-3 ring-1 ring-slate-200">
                <div className="text-xs font-semibold uppercase text-slate-500">Задача</div>
                <div className="mt-1 line-clamp-4 text-sm leading-6 text-slate-900">{previewTaskText}</div>
              </div>
              <div className="rounded-xl bg-white px-3 py-3 ring-1 ring-slate-200">
                <div className="text-xs font-semibold uppercase text-slate-500">Данные</div>
                <div className="mt-1 line-clamp-3 text-sm leading-6 text-slate-900">{previewDataText}</div>
              </div>
              <div className="rounded-xl bg-white px-3 py-3 ring-1 ring-slate-200">
                <div className="text-xs font-semibold uppercase text-slate-500">Результат и контроль</div>
                <div className="mt-1 line-clamp-3 text-sm leading-6 text-slate-900">{previewResultText}</div>
                <div className="mt-2 rounded-lg bg-slate-50 px-2 py-1 text-xs text-slate-600 ring-1 ring-slate-100">
                  Контроль: {previewControlText}
                </div>
              </div>
            </div>

            <BuilderTrustBlock ready={canCreateDraft} />

            <details className="mt-4 rounded-xl border border-slate-200 bg-white px-3 py-3 text-sm leading-6 text-slate-700">
              <summary className="cursor-pointer font-semibold text-slate-950">Подробности проверки</summary>
              <div className="mt-3 space-y-3">
                <PreviewRow label="Что извлечь" value={preview?.extraction_rules || 'уточнить'} />
                <PreviewRow label="Правила" value={preview?.processing_rules || 'уточнить'} />
                <BuilderCreationDecisionBanner
                  decision={builderDecision}
                  actionLoading={actionLoading}
                  canSendReply={Boolean(reply.trim())}
                  canCreateDraft={canCreateDraft}
                  onSendReply={onSendReply}
                  onCreate={onCreate}
                />
                {!showInlineConnectionSetup ? (
                  <BuilderRequiredConnectionsPanel
                    preview={preview}
                    selectedProviderRoutes={selectedProviderRoutes}
                    onSelectProviderRoute={onSelectProviderRoute}
                  />
                ) : null}
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
                {!showInlineConnectionSetup ? (
                  <BuilderConnectionReadinessPanel
                    readiness={preview?.connection_readiness}
                    answerBindings={preview?.connection_answer_bindings}
                    selectedProviderRoutes={selectedProviderRoutes}
                    acceptedProviderRoutes={acceptedProviderRoutes}
                    missingProviderRouteKeys={missingProviderRouteKeys}
                    onAcceptProviderRoutes={onAcceptProviderRoutes}
                    onSelectProviderRoute={onSelectProviderRoute}
                  />
                ) : null}
                <BuilderConnectionResolverPanel resolver={preview?.connection_resolver} />
                <BuilderSetupFlowPanel setupFlow={preview?.setup_flow} />
                <BuilderExecutionBoundaryPanel plannerLoop={preview?.openclaw_planner_loop} />
                <BuilderConnectionSummaryPanel
                  summary={preview?.connection_summary}
                  selectedBindings={selectedConnectionBindings}
                  onSelectBinding={onSelectConnectionBinding}
                />
                {!showInlineConnectionSetup && missingConnectionChoices.length ? (
                  <div className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-950">
                    Выберите, какие уже подключённые сервисы использовать: {missingConnectionChoices.map((item) => item.title || connectorLabel(item.provider)).join(', ')}. После этого LocalOS привяжет их к агенту.
                  </div>
                ) : null}
                <BuilderTechnicalDiagnostics
                  connectorIntelligence={preview?.connector_intelligence}
                  plannerLoop={preview?.openclaw_planner_loop}
                  connectionPlan={preview?.connection_plan || null}
                  feasibility={preview?.feasibility}
                  connectors={preview?.required_connectors}
                />
                {!canCreateDraft && createBlockers.length ? (
                  <div className="rounded-xl border border-amber-200 bg-white px-3 py-3 text-xs leading-5 text-amber-950">
                    <div className="font-semibold">Почему агента пока нельзя создать</div>
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
              </div>
            </details>

            <details className="mt-3 rounded-xl border border-slate-200 bg-white px-3 py-3 text-sm leading-6 text-slate-700">
              <summary className="cursor-pointer font-semibold text-slate-950">История диалога</summary>
              <div className="mt-3 max-h-72 space-y-2 overflow-auto rounded-xl bg-slate-50 p-3">
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
            </details>
            {estimatedCredits > 0 ? (
              <div className="mt-3 rounded-xl border border-sky-200 bg-sky-50 px-3 py-2 text-xs leading-5 text-sky-900">
                Создание агента спишет примерно {estimatedCredits} кредита с баланса. Если кредитов не хватит, предложим пополнить счёт.
              </div>
            ) : null}
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
    <details
      className="mt-3 rounded-xl border border-slate-200 bg-white px-3 py-3 text-xs leading-5 text-slate-700"
      data-source-contract={AGENT_BLUEPRINT_LEGACY_SOURCE_CONTRACT_LABELS.join('|')}
    >
      <summary className="cursor-pointer font-semibold text-slate-950">
        Техническая диагностика
      </summary>
      <div className="mt-1 text-[11px] leading-4 text-slate-500">
        Для проверки: способы подключения, карта действий, проверка доступов и правила безопасности. Обычный следующий шаг показан выше.
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
    <div
      className={cn(compact ? 'mt-0' : 'mt-4', 'rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-3 text-xs leading-5 text-emerald-950')}
      data-contract-label="LocalOS должен собрать проверяемый workflow"
    >
    <div className="font-semibold">После создания LocalOS соберёт проверяемую логику агента</div>
    <div className="mt-2 grid gap-2 sm:grid-cols-4">
      {[
        ['1', 'План', 'задача и шаги'],
        ['2', 'Проверка', 'разрешённые действия и подтверждения'],
        ['3', 'Доступы', 'что нужно подключить'],
        ['4', 'Запуск', 'только после проверки'],
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
            LocalOS понял, какие сервисы нужны агенту. Ресурс из диалога сохраняется отдельно от доступа: перед тестом нужно выбрать способ подключения или готовое подключение.
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
	                  <div className="mt-0.5 text-[11px] leading-4 text-slate-500">{userFacingAgentTechText(humanizeMeta(item.capability || item.provider || 'binding'))}</div>
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
	                {userFacingAgentTechText(item.route_summary || builderConnectionCardHint(item.action, item.provider))}
              </div>
              {missingConfig.length ? (
                <div className="mt-2 rounded-lg bg-amber-50 px-2 py-1.5 text-[11px] leading-4 text-amber-800 ring-1 ring-amber-100">
	                  Не хватает настроек: {missingConfig.map((item) => userFacingAgentTechText(humanizeMeta(item))).join(', ')}
                </div>
              ) : null}
              <RecommendedProviderRouteNote
                route={item.recommended_route}
                reason={item.recommended_route_reason}
              />
              {item.policy_summary ? (
                <div className="mt-2 rounded-lg bg-slate-50 px-2 py-1.5 text-[11px] leading-4 text-slate-600 ring-1 ring-slate-100">
	                  {userFacingAgentTechText(item.policy_summary)}
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
    return 'выбрать способ';
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
    return 'Этот доступ уже можно использовать в тесте без отправки.';
  }
  if (action === 'choose_existing') {
    return 'У бизнеса есть несколько подходящих подключений. Выберите одно для этого агента.';
  }
  if (action === 'choose_route') {
    return 'Выберите, как агенту безопасно доставлять результат или получать данные. Обычно подходит рекомендованный способ LocalOS.';
  }
  if (action === 'connect_required') {
    return `${connectorLabel(provider)} нужен агенту, но доступ ещё не выбран.`;
  }
  if (action === 'planned_provider') {
    return 'Этот способ подключения запланирован, но пока недоступен для включения агента.';
  }
  return 'LocalOS проверит этот доступ перед тестом без отправки.';
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

const compilerPlanTriggerLabel = (trigger?: string) => {
  const value = String(trigger || '').trim();
  if (!value || value === 'manual.run') {
    return 'Запуск вручную';
  }
  if (value.includes('daily')) {
    const timeMatch = value.match(/at\(([^)]+)\)/);
    return `Каждый день${timeMatch?.[1] ? ` в ${timeMatch[1]}` : ''}`;
  }
  if (value.includes('schedule')) {
    return 'По расписанию';
  }
  if (value.includes('message') || value.includes('telegram')) {
    return 'Когда приходит сообщение';
  }
  return humanizeMeta(value);
};

const compilerPlanStepCopy = (item: AgentCompilerPolicyItem, index: number) => {
  const capability = String(item.capability || item.key || item.type || '').trim();
  const provider = String(item.provider || '').trim();
  const rawLabel = compilerPolicyItemLabel(item);

  if (capability === 'google_sheets.read_rows' || provider === 'google_sheets') {
    return {
      title: 'Прочитать данные из Google Sheets',
      detail: 'Агент возьмёт строки из выбранной таблицы и вкладки. На этом шаге он только читает данные.',
    };
  }
  if (capability === 'communications.draft' || capability.includes('draft')) {
    return {
      title: 'Подготовить черновик сообщения',
      detail: 'LocalOS соберёт текст по заданному стилю. Это ещё не отправка наружу.',
    };
  }
  if (capability.includes('send') || capability.includes('publish')) {
    return {
      title: 'Попросить подтверждение перед отправкой',
      detail: 'Внешнее действие не выполняется автоматически: пользователь должен одобрить результат.',
    };
  }
  if (provider === 'telegram' || capability.includes('telegram')) {
    return {
      title: 'Передать результат в Telegram',
      detail: 'Сообщение будет доставлено через выбранный Telegram-канал после нужного подтверждения.',
    };
  }
  return {
    title: rawLabel || `Шаг ${index + 1}`,
    detail: item.reason || item.message || item.text || 'LocalOS выполнит этот шаг как часть проверяемого сценария.',
  };
};

const builderPreviewDataText = (preview: AgentBuilderPreview | null, taskText: string) => {
  const labels: string[] = [];
  const seen = new Set<string>();
  const addLabel = (label: string) => {
    const cleanLabel = label.trim();
    const key = cleanLabel.toLowerCase();
    if (!cleanLabel || seen.has(key)) {
      return;
    }
    seen.add(key);
    labels.push(cleanLabel);
  };
  if (taskText.toLowerCase().includes('отзыв')) {
    addLabel('отзывы компании');
  }
  (preview?.data_sources || []).forEach((item) => addLabel(humanizeMeta(item)));
  return labels.join(', ') || 'ещё не выбрано';
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
  const statusLabel = blocked ? 'нужно изменить' : needsApproval ? 'нужны подтверждения' : 'готов к утверждению';
  const readableSteps = steps.map((step, index) => compilerPlanStepCopy(step, index));
  return (
    <div className={cn('mt-3 rounded-xl border px-3 py-3 text-sm leading-6', toneClass)}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="font-semibold">Сценарий работы агента</div>
          <div className="mt-1 max-w-2xl text-sm">
            Проверьте последовательность действий. После утверждения LocalOS сохранит её как проверяемую логику и запустит тест на примере.
          </div>
        </div>
        <span className={cn('rounded-full px-2 py-0.5 font-medium ring-1', badgeClass)}>
          {statusLabel}
        </span>
      </div>

      <div className="mt-3 grid gap-2 md:grid-cols-2">
        <AgentMiniMetric label="Когда запускать" value={compilerPlanTriggerLabel(draft.trigger)} />
        <AgentMiniMetric label="Контроль перед внешними действиями" value={approvals.length ? `${approvals.length} подтвержд.` : 'уточнить в диалоге'} />
      </div>

      {readableSteps.length ? (
        <div className="mt-3 rounded-lg bg-white p-3 text-slate-700 ring-1 ring-current/10">
          <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Что будет делать агент</div>
          <div className="mt-3 space-y-3">
            {readableSteps.slice(0, 5).map((step, index) => {
              return (
                <div key={`${step.title}-${index}`} className="grid grid-cols-[2rem_minmax(0,1fr)] gap-3">
                  <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-slate-100 text-sm font-semibold text-slate-700">
                    {index + 1}
                  </span>
                  <div className="min-w-0">
                    <div className="font-semibold text-slate-950">{step.title}</div>
                    <div className="mt-0.5 text-sm leading-6 text-slate-600">{step.detail}</div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      ) : null}

      {approvals.length ? (
        <div className="mt-3 rounded-lg bg-white px-3 py-2 text-amber-950 ring-1 ring-current/10">
          <div className="font-semibold">Что агент спросит у пользователя</div>
          <div className="mt-2 space-y-1">
            {approvals.slice(0, 3).map((item, index) => (
              <div key={`${compilerPolicyItemLabel(item)}-${index}`} className="flex gap-2 text-sm leading-6">
                <ShieldCheck className="mt-1 h-4 w-4 shrink-0" />
                <span>{compilerPolicyItemLabel(item) || 'Подтверждение перед внешним действием'}</span>
              </div>
            ))}
          </div>
        </div>
      ) : !blockers.length ? (
        <div className="mt-3 rounded-lg bg-white px-3 py-2 text-slate-700 ring-1 ring-current/10">
          <div className="font-semibold text-slate-950">Что нужно уточнить в диалоге</div>
          <div className="mt-1 text-sm leading-6">
            Подтвердите расписание и правило отправки: если агент должен публиковать или отправлять сообщение наружу, LocalOS должен сначала показать черновик и спросить разрешение.
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
                <span>{compilerPolicyItemLabel(item) || 'Часть запроса выходит за правила безопасности LocalOS'}</span>
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
                ? 'Сценарий утверждён. LocalOS сможет создать черновик агента и сохранить проверяемую логику.'
                : 'Если последовательность верная, утвердите сценарий в диалоге.'}
            </div>
            <Button type="button" size="sm" variant={accepted ? 'outline' : 'default'} onClick={onAccept} disabled={accepted}>
              <CheckCircle2 className="mr-2 h-4 w-4" />
              {accepted ? 'Сценарий утверждён' : 'Утвердить сценарий'}
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
      {reason ? <div className="mt-1">{userFacingAgentTechText(reason)}</div> : null}
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
    return 'Выберите способ';
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
	    return userFacingAgentTechText(service.provider_route_cta);
  }
	  return userFacingAgentTechText(service.route_summary || service.explanation || 'LocalOS проверит доступ перед тестом без отправки.');
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
	          <div className="mt-1 max-w-2xl">{userFacingAgentTechText(intelligence.headline || 'LocalOS сопоставил задачу с доступными сервисами и правилами безопасности.')}</div>
        </div>
        <span className="rounded-full bg-white px-2 py-0.5 font-medium ring-1 ring-current/10">
          {intelligence.can_activate ? 'можно проверить' : intelligence.can_create_draft ? 'можно создать черновик' : 'нельзя создать'}
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
	                  {item.capability ? <div className="mt-0.5 text-[11px] leading-4 text-slate-500">{userFacingAgentTechText(humanizeMeta(item.capability))}</div> : null}
                </div>
                <span className={cn('rounded-full px-2 py-0.5 text-[11px] font-medium ring-1', serviceIntelligenceTone(state))}>
	                  {userFacingAgentTechText(item.state_label || humanizeMeta(state || 'проверить'))}
                </span>
              </div>
              <div className="mt-1 text-[11px] leading-4 text-slate-600">
	                {userFacingAgentTechText(item.explanation || 'LocalOS проверит этот сервис перед тестом без отправки.')}
              </div>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {provider ? (
                  <span className="rounded-full bg-sky-50 px-2 py-0.5 text-[11px] text-sky-700 ring-1 ring-sky-100">
	                    {userFacingAgentTechText(item.recommended_label || connectorLabel(provider))}
                  </span>
                ) : null}
                {item.connection_count ? (
                  <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] text-emerald-700 ring-1 ring-emerald-100">
                    {item.connection_count} доступ
                  </span>
                ) : null}
                {item.next_action ? (
                  <span className="rounded-full bg-slate-50 px-2 py-0.5 text-[11px] text-slate-600 ring-1 ring-slate-200">
	                    {userFacingAgentTechText(humanizeMeta(item.next_action))}
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
	                  {selected ? 'Способ выбран' : userFacingAgentTechText(`Использовать ${connectorLabel(provider)}`)}
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
    ? 'Все нужные сервисы можно использовать. После создания агента запустите тест без отправки.'
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
                  <div className="mt-0.5 text-[11px] leading-4 text-slate-500">{userFacingAgentTechText(humanizeMeta(service.capability || service.provider || 'service'))}</div>
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
	                  {service.provider_route_label ? `${userFacingAgentTechText(service.provider_route_label)}: ` : ''}
	                  {userFacingAgentTechText(service.provider_route_cta || providerRouteLabel(service.route_state || ''))}
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
                  {userFacingAgentTechText(item.state_label || humanizeMeta(state || 'проверить'))}
                </span>
              </div>
              <div className="mt-1 text-[11px] leading-4 text-slate-600">
                {item.explanation || 'LocalOS проверит этот сервис перед тестом без отправки.'}
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
    create_draft: 'Можно создать черновик',
  }[setupFlow.primary_action || ''] || 'Проверьте настройку';
  const nextStepTitle = userFacingAgentTechText(setupFlow.next_step_title || primaryActionLabel);
  const nextStepDescription = userFacingAgentTechText(setupFlow.next_step_description || setupFlow.post_create_description || '');
  return (
    <div className="mt-3 rounded-xl border border-slate-200 bg-white px-3 py-3 text-xs leading-5 text-slate-700">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <div className="font-semibold text-slate-950">Что дальше</div>
          <div className="mt-1 max-w-2xl text-[11px] leading-4 text-slate-500">
	            {nextStepDescription || 'LocalOS ведёт агента от описания к черновику, тесту без отправки и включению.'}
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
	                <span>{userFacingAgentTechText(step.label || humanizeMeta(step.key || 'Шаг'))}</span>
              </div>
	              <div className="mt-1 text-[11px] leading-4 opacity-80">{userFacingAgentTechText(step.description || statusLabels[status] || humanizeMeta(status))}</div>
            </div>
          );
        })}
      </div>
      {setupFlow.activation_blockers?.length ? (
        <div className="mt-2 text-[11px] leading-4 text-slate-500">
	          Активация будет доступна после: {setupFlow.activation_blockers.slice(0, 3).map((item) => userFacingAgentTechText(item.message || connectorLabel(item.provider))).join(', ')}.
        </div>
      ) : null}
      {setupFlow.post_create_description ? (
        <div className="mt-2 rounded-lg bg-slate-50 px-2 py-2 text-[11px] leading-4 text-slate-600 ring-1 ring-slate-100">
	          После создания: {userFacingAgentTechText(setupFlow.post_create_description)}
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
                {userFacingAgentTechText(item.action_label || humanizeMeta(item.action || item.status || 'status'))}
              </span>
            </div>
            <div className="mt-1 text-[11px] leading-4 opacity-80">{item.explanation || 'Подключение будет проверено перед тестом без отправки.'}</div>
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
          {[...forbidden.map((item) => item.reason || item.term || 'Запрещено правилами безопасности'), ...unsupported.map((item) => item.reason || item.capability || 'Нет способа подключения')].slice(0, 3).join(' · ')}
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
	            {userFacingAgentTechText(intelligence.headline || 'LocalOS проверил нужные подключения и способы подключения.')}
          </div>
        </div>
        <span className={cn('rounded-full bg-white px-2.5 py-1 font-medium ring-1', blocked ? 'text-rose-700 ring-rose-200' : needsAction ? 'text-amber-800 ring-amber-200' : 'text-emerald-800 ring-emerald-200')}>
	          {blocked ? 'нельзя создать' : needsAction ? 'нужно действие' : 'готово к тесту'}
        </span>
      </div>

      {bindings.length ? (
        <div className="mt-3 grid gap-2 md:grid-cols-2">
          {bindings.slice(0, 4).map((item) => (
            <div key={item.key || item.provider} className="rounded-lg bg-white px-2 py-2 ring-1 ring-black/5">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="font-medium text-slate-950">{item.title || connectorLabel(item.provider)}</div>
	                  <div className="mt-0.5 text-[11px] text-slate-500">{userFacingAgentTechText(humanizeMeta(item.capability || item.provider || 'capability'))}</div>
                </div>
                <span className={cn('shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium ring-1', connectionActionTone(item.action || ''))}>
	                  {userFacingAgentTechText(item.action_label || humanizeMeta(item.action || item.status || ''))}
                </span>
              </div>
	              <div className="mt-1 text-[11px] leading-4 text-slate-600">{userFacingAgentTechText(item.route_summary || item.explanation || 'Будет проверено перед запуском.')}</div>
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
              {userFacingAgentTechText(humanizeMeta(item.capability || ''))}
              {item.route_state ? ` · ${userFacingAgentTechText(providerRouteLabel(item.route_state))}` : ''}
              {item.openclaw_actions?.length ? ` · действий LocalOS ${item.openclaw_actions.length}` : ''}
            </span>
          ))}
        </div>
      ) : null}

      {providerPaths.length ? (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {providerPaths.slice(0, 6).map((item) => (
            <span key={`${item.provider}-${item.status}-${item.source}`} className="rounded-full bg-white/80 px-2 py-0.5 text-[11px] text-slate-600 ring-1 ring-black/5">
              {userFacingAgentTechText(item.label || connectorLabel(item.provider))}: {userFacingAgentTechText(humanizeMeta(item.status || 'unknown'))}
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
        <div className="font-semibold text-slate-950">Планировщик действий</div>
        <span className="rounded-full bg-slate-50 px-2 py-0.5 font-medium text-slate-600 ring-1 ring-slate-200">
          {plannerLoop.catalog_source === 'openclaw' ? 'живой каталог' : 'резервный каталог'}
        </span>
      </div>
      <div className="mt-1">
        Проверены разрешённые действия: {capabilities.length || 0}, способы подключения: {providerPaths.length || 0}, ссылки на действия: {actionRefs.length || 0}. Инструменты не выполняются в мастере; LocalOS сохранит проверяемую логику.
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
    <div
      className="mt-3 rounded-xl border border-sky-200 bg-sky-50 px-3 py-3 text-xs leading-5 text-sky-950"
      data-contract-label="Execution boundary"
      data-contract-openclaw-action-refs="OpenClaw action refs"
      data-contract-safe-preview-copy="OpenClaw actions в safe preview; side effects выключены"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="font-semibold">Граница исполнения</div>
          <div className="mt-1 max-w-2xl text-sky-800">
            Действия можно предложить и исполнить только внутри правил безопасности, списаний, журнала и ручных подтверждений LocalOS.
          </div>
        </div>
        <span className="rounded-full bg-white px-2 py-0.5 font-medium text-sky-700 ring-1 ring-sky-200">
          {plannerLoop.catalog_source === 'openclaw' ? 'Каталог действий' : 'Резервный каталог'}
        </span>
      </div>
      <div className="mt-3 grid gap-2 sm:grid-cols-3">
        <AgentMiniMetric label="Инструменты" value={mayExecuteTools ? 'разрешены' : 'запрещены'} />
        <AgentMiniMetric label="Внешние действия" value={externalSideEffects ? 'есть риск' : 'нет в тесте'} />
        <AgentMiniMetric label="Владелец логики" value={contract.compiled_workflow_owner || (plannerLoop.must_compile_in_localos ? 'LocalOS' : 'LocalOS')} />
      </div>
      {actionRefs.length ? (
        <div className="mt-3 rounded-lg bg-white px-2 py-2 ring-1 ring-sky-100">
          <div className="font-semibold text-sky-900">Ссылки на действия</div>
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
                <div className="font-medium text-slate-950">{userFacingAgentTechText(humanizeMeta(item.capability || 'capability'))}</div>
                <div className="mt-1 text-[11px] leading-4 text-slate-600">
                  {refs.length ? refs.slice(0, 2).join(' · ') : 'Действие не выбрано'}
                </div>
              </div>
            );
          })}
        </div>
      ) : null}
      {contract.must_not?.length ? (
        <div className="mt-2 rounded-lg bg-white/80 px-2 py-1.5 text-[11px] leading-4 text-sky-800 ring-1 ring-sky-100">
          Нельзя: {contract.must_not.slice(0, 4).map((item) => userFacingAgentTechText(humanizeMeta(item))).join(', ')}.
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
                  {userFacingAgentTechText(statusLabels[item.status || ''] || humanizeMeta(item.status || 'ожидает'))}
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
              {item.reason || 'Нет разрешённого способа подключения.'}
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

const AgentsTodaySection = ({
  summary,
  loading,
  onOpenToday,
}: {
  summary: AgentTodaySummary;
  loading: boolean;
  onOpenToday: () => void;
}) => (
  <section className="rounded-2xl border border-slate-200 bg-white px-5 py-5 shadow-sm">
    <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
      <div>
        <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Сегодня</div>
        <h2 className="mt-2 text-xl font-semibold leading-7 text-slate-950">Что сделали ИИ-сотрудники за последние 24 часа</h2>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
          {summary.empty
            ? 'За сегодня агенты ещё ничего не запускали.'
            : summary.latestEvent
              ? `Последнее событие: ${summary.latestEvent}.`
              : 'LocalOS собрал свежую сводку по агентам.'}
        </p>
      </div>
      <Button type="button" variant="outline" onClick={onOpenToday} disabled={loading}>
        Подробнее
      </Button>
    </div>
    <div className="mt-5 grid gap-3 md:grid-cols-4">
      <TodayFact icon={CheckCircle2} label="Выполнено работ" value={summary.completedRuns} tone="emerald" />
      <TodayFact icon={FileCheck2} label="Подготовлено результатов" value={summary.preparedArtifacts} tone="sky" />
      <TodayFact icon={ShieldCheck} label="Ждут решения" value={summary.pendingApprovals} tone={summary.pendingApprovals ? 'amber' : 'slate'} />
      <TodayFact icon={AlertTriangle} label="Нужно проверить" value={summary.failedRuns} tone={summary.failedRuns ? 'rose' : 'slate'} />
    </div>
  </section>
);

const TodayFact = ({
  icon: Icon,
  label,
  value,
  tone,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: number;
  tone: 'emerald' | 'sky' | 'amber' | 'rose' | 'slate';
}) => (
  <div className={cn(
    'rounded-xl px-3 py-3 ring-1',
    tone === 'emerald' ? 'bg-emerald-50 text-emerald-950 ring-emerald-100' : '',
    tone === 'sky' ? 'bg-sky-50 text-sky-950 ring-sky-100' : '',
    tone === 'amber' ? 'bg-amber-50 text-amber-950 ring-amber-100' : '',
    tone === 'rose' ? 'bg-rose-50 text-rose-950 ring-rose-100' : '',
    tone === 'slate' ? 'bg-slate-50 text-slate-700 ring-slate-100' : '',
  )}>
    <div className="flex items-center justify-between gap-3">
      <Icon className="h-4 w-4" />
      <span className="tabular-nums text-lg font-semibold">{value}</span>
    </div>
    <div className="mt-2 text-xs font-medium leading-5">{label}</div>
  </div>
);

const AgentsAttentionInbox = ({
  items,
  loading,
}: {
  items: AgentAttentionItem[];
  loading: boolean;
}) => (
  <section className="rounded-2xl border border-slate-200 bg-white px-5 py-5 shadow-sm">
    <div className="flex items-start justify-between gap-3">
      <div>
        <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Требует внимания</div>
        <h2 className="mt-2 text-lg font-semibold leading-7 text-slate-950">Следующие решения и настройки</h2>
      </div>
      <span className="rounded-full bg-slate-50 px-2.5 py-1 text-xs font-medium text-slate-600 ring-1 ring-slate-200">
        {items.length ? `${items.length} задач` : 'спокойно'}
      </span>
    </div>
    <div className="mt-4 grid gap-3">
      {loading ? (
        <div className="rounded-xl bg-slate-50 px-3 py-3 text-sm text-slate-500 ring-1 ring-slate-100">Проверяем, где нужен человек...</div>
      ) : items.length ? (
        items.map((item) => (
          <div
            key={item.key}
            className={cn(
              'grid gap-3 rounded-xl px-3 py-3 ring-1 md:grid-cols-[minmax(0,1fr)_auto] md:items-center',
              item.tone === 'amber' ? 'bg-amber-50 text-amber-950 ring-amber-100' : '',
              item.tone === 'rose' ? 'bg-rose-50 text-rose-950 ring-rose-100' : '',
              item.tone === 'sky' ? 'bg-sky-50 text-sky-950 ring-sky-100' : '',
            )}
          >
            <div className="min-w-0">
              <div className="text-sm font-semibold text-slate-950">{item.problem}</div>
              <div className="mt-1 line-clamp-2 text-sm leading-6 opacity-85">{item.reason}</div>
            </div>
            <Button type="button" size="sm" onClick={item.action}>
              {item.actionLabel}
            </Button>
          </div>
        ))
      ) : (
        <div className="rounded-xl bg-emerald-50 px-3 py-3 text-sm leading-6 text-emerald-950 ring-1 ring-emerald-100">
          Всё работает. Новых действий не требуется.
        </div>
      )}
    </div>
  </section>
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
  businessStatus,
  onSelect,
  onConfigure,
  onRun,
  onResults,
  onVoice,
  onDelete,
  actionLoading,
}: {
  blueprint: AgentBlueprint;
  latestVersionNumber: number | null;
  selected: boolean;
  businessStatus: AgentBusinessStatus;
  onSelect: () => void;
  onConfigure: () => void;
  onRun: () => void;
  onResults: () => void;
  onVoice: () => void;
  onDelete: () => void;
  actionLoading: boolean;
}) => {
  const toneClass = {
    ready: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
    warning: 'bg-amber-50 text-amber-700 ring-amber-200',
    error: 'bg-rose-50 text-rose-700 ring-rose-200',
    draft: 'bg-slate-100 text-slate-700 ring-slate-200',
  }[businessStatus.tone];
  return (
  <div className={cn('rounded-xl border bg-white p-3 transition', selected ? 'border-slate-900 shadow-sm' : 'border-slate-200 hover:border-slate-300')}>
    <button type="button" className="w-full text-left" onClick={onSelect}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold text-slate-950">{blueprint.name}</div>
          <div className="mt-1 text-xs font-medium text-slate-500">
            {humanizeCategory(blueprint.category)}{latestVersionNumber ? ` · рабочая версия ${latestVersionNumber}` : ''}
          </div>
        </div>
        <span className={cn('shrink-0 rounded-full px-2.5 py-1 text-xs font-medium ring-1', toneClass)}>
          {businessStatus.label}
        </span>
      </div>
      <div className="mt-3 line-clamp-3 text-sm leading-6 text-slate-600">
        {blueprint.description || blueprint.latest_goal || 'Пользовательский агент с настройками, запусками и результатами.'}
      </div>
      <div className="mt-3 grid gap-2 text-xs text-slate-600 sm:grid-cols-2">
        <div className="rounded-lg bg-slate-50 px-2.5 py-2 ring-1 ring-slate-100">
          <div className="font-semibold text-slate-800">Последний результат</div>
          <div className="mt-1 line-clamp-2">{businessStatus.lastResult}</div>
        </div>
        <div className="rounded-lg bg-slate-50 px-2.5 py-2 ring-1 ring-slate-100">
          <div className="font-semibold text-slate-800">Следующий запуск</div>
          <div className="mt-1 line-clamp-2">{businessStatus.nextRun}</div>
        </div>
      </div>
    </button>
    <div className="mt-3 grid grid-cols-[1fr_auto] gap-2">
      <Button type="button" size="sm" variant={selected ? 'default' : 'outline'} onClick={onConfigure}>
        Настроить
      </Button>
      <Button type="button" size="sm" variant="outline" onClick={onRun}>
        <Play className="mr-2 h-4 w-4" />
        {businessStatus.primaryLabel}
      </Button>
    </div>
    <div className="mt-2 flex gap-1.5">
      <Button type="button" size="sm" variant="ghost" className="h-8 px-2 text-xs" onClick={onResults}>История</Button>
      <Button type="button" size="sm" variant="ghost" className="h-8 px-2 text-xs" onClick={onVoice}>Голос</Button>
      <Button
        type="button"
        size="sm"
        variant="ghost"
        className="h-8 px-2 text-xs text-red-700 hover:text-red-800"
        onClick={onDelete}
        disabled={actionLoading}
      >
        <Trash2 className="mr-1.5 h-3.5 w-3.5" />
        Убрать из списка
      </Button>
    </div>
  </div>
  );
};

const employeeToneClass = {
  emerald: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  amber: 'bg-amber-50 text-amber-800 ring-amber-200',
  rose: 'bg-rose-50 text-rose-700 ring-rose-200',
  slate: 'bg-slate-100 text-slate-700 ring-slate-200',
};

const EmployeeStatusPill = ({ status }: { status: EmployeeStatus }) => (
  <span className={cn('inline-flex min-h-8 items-center rounded-full px-3 py-1 text-xs font-semibold ring-1', employeeToneClass[status.tone])}>
    {status.label}
  </span>
);

const AgentRunProgressPanel = ({
  animation,
  onRetry,
}: {
  animation: AgentRunAnimation;
  onRetry: () => void;
}) => {
  const failed = animation.status === 'error';
  const currentStep = animation.steps[animation.stepIndex] || 'Выполняю задачу';
  return (
    <section className="overflow-hidden rounded-2xl bg-white shadow-[0_18px_48px_rgba(15,23,42,0.08),0_0_0_1px_rgba(15,23,42,0.08)]">
      <div className="bg-slate-950 px-5 py-5 text-white sm:px-7 sm:py-7">
        <div className="flex items-start gap-4">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-white/10">
            {failed ? <AlertTriangle className="h-5 w-5 text-rose-300" /> : <Loader2 className="h-5 w-5 animate-spin motion-reduce:animate-none" />}
          </div>
          <div className="min-w-0 flex-1">
            <div className="text-xs font-semibold uppercase text-slate-400">{animation.kind === 'test' ? 'Безопасный тест' : 'Рабочий запуск'}</div>
            <h2 className="mt-1 text-2xl font-semibold leading-8 [text-wrap:balance]">{failed ? 'Работа остановилась' : 'Агент выполняет задачу'}</h2>
            <p className="mt-2 text-sm leading-6 text-slate-300 [text-wrap:pretty]">{failed ? animation.error : currentStep}</p>
          </div>
          <span className="shrink-0 text-sm font-semibold tabular-nums text-slate-300">{animation.progress}%</span>
        </div>
        <div className="mt-5 h-2 overflow-hidden rounded-full bg-white/10">
          <div
            className={cn('h-full rounded-full transition-[width] duration-500 ease-out motion-reduce:transition-none', failed ? 'bg-rose-400' : 'bg-orange-400')}
            style={{ width: `${animation.progress}%` }}
          />
        </div>
      </div>
      <div className="px-5 py-5 sm:px-7">
        <ol className="grid gap-2">
          {animation.steps.map((step, index) => {
            const done = animation.status === 'finishing' || index < animation.stepIndex;
            const current = index === animation.stepIndex;
            return (
              <li
                key={`${index}-${step}`}
                className={cn(
                  'flex min-h-11 items-center gap-3 rounded-xl px-3 text-sm transition-[background-color,color,opacity] duration-300 motion-reduce:transition-none',
                  done ? 'bg-emerald-50 text-emerald-900' : current ? failed ? 'bg-rose-50 text-rose-900' : 'bg-orange-50 text-orange-950' : 'text-slate-400',
                )}
              >
                <span className={cn(
                  'flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold ring-1',
                  done ? 'bg-emerald-600 text-white ring-emerald-600' : current ? failed ? 'bg-rose-100 text-rose-700 ring-rose-200' : 'bg-orange-100 text-orange-700 ring-orange-200' : 'bg-slate-50 text-slate-400 ring-slate-200',
                )}>
                  {done ? <CheckCircle2 className="h-4 w-4" /> : index + 1}
                </span>
                <span className="font-medium [text-wrap:pretty]">{step}</span>
              </li>
            );
          })}
        </ol>
        {failed ? (
          <Button type="button" className="mt-4 min-h-10 active:scale-[0.96] transition-transform" onClick={onRetry}>
            <RefreshCw className="mr-2 h-4 w-4" />
            Запустить ещё раз
          </Button>
        ) : (
          <p className="mt-4 text-xs leading-5 text-slate-500">Можно оставить страницу открытой: результат появится здесь сразу после завершения.</p>
        )}
      </div>
    </section>
  );
};

const EmployeeAgentsList = ({
  blueprints,
  detailsById,
  selectedBlueprintId,
  selectedActiveRun,
  selectedPendingApproval,
  loading,
  onOpen,
}: {
  blueprints: AgentBlueprint[];
  detailsById: Record<string, AgentBlueprintDetails>;
  selectedBlueprintId: string | null;
  selectedActiveRun?: AgentRun | null;
  selectedPendingApproval?: AgentApproval | null;
  loading: boolean;
  onOpen: (blueprint: AgentBlueprint) => void;
}) => (
  <aside className="rounded-2xl bg-white p-3 shadow-[0_1px_2px_rgba(15,23,42,0.06),0_0_0_1px_rgba(15,23,42,0.08)] lg:sticky lg:top-4">
    <div className="flex items-center justify-between gap-3 px-1">
      <div>
        <h2 className="text-sm font-semibold leading-6 text-slate-950">Сотрудники</h2>
        <p className="text-xs leading-5 text-slate-500">Тип, состояние и следующий шаг</p>
      </div>
      <span className="inline-flex min-h-7 items-center rounded-full bg-slate-50 px-2.5 py-0.5 text-xs font-medium tabular-nums text-slate-600 ring-1 ring-slate-200">
        {blueprints.length}
      </span>
    </div>

    <div className="mt-3 max-h-[calc(100vh-18rem)] min-h-72 overflow-y-auto pr-1">
      {loading ? (
        <div className="flex min-h-20 items-center gap-2 rounded-xl bg-slate-50 px-3 py-3 text-sm text-slate-500 ring-1 ring-slate-100">
          <Loader2 className="h-4 w-4 animate-spin" />
          Загружаем сотрудников...
        </div>
      ) : blueprints.length === 0 ? (
        <div className="rounded-xl bg-slate-50 px-3 py-4 text-sm leading-6 text-slate-600 ring-1 ring-slate-100">
          Создайте первого сотрудника.
        </div>
      ) : (
        blueprints.map((blueprint) => {
          const selected = selectedBlueprintId === blueprint.id;
          const baseDetails = detailsById[blueprint.id];
          const details = selected && selectedActiveRun
            ? {
              ...baseDetails,
              runs: [
                selectedActiveRun,
                ...(baseDetails?.runs || []).filter((run) => run.id !== selectedActiveRun.id),
              ],
            }
            : baseDetails;
          const pendingApproval = selected
            ? selectedPendingApproval || (details?.approval_queue || []).find((item) => item.status === 'pending') || null
            : (details?.approval_queue || []).find((item) => item.status === 'pending') || null;
          const status = buildEmployeeStatus(blueprint, details, pendingApproval);
          const state = buildEmployeeWorkspaceState(blueprint, details, pendingApproval);
          const mode = agentExecutionMode(blueprint, details);
          const lastResult = blueprint.last_business_result || details?.last_business_result;
          const resultText = lastResult ? businessResultPrimaryText(lastResult) : '';
          return (
            <button
              key={blueprint.id}
              type="button"
              onClick={() => onOpen(blueprint)}
              className={cn(
                'mb-2 grid min-h-[7.5rem] w-full gap-3 rounded-xl px-3 py-3 text-left transition-[box-shadow,background-color,color] active:scale-[0.99]',
                selected ? 'bg-slate-950 text-white shadow-[0_0_0_1px_rgba(15,23,42,1)]' : 'bg-white shadow-[0_0_0_1px_rgba(15,23,42,0.08)] hover:shadow-[0_6px_18px_rgba(15,23,42,0.08),0_0_0_1px_rgba(15,23,42,0.12)]',
                !selected && (state === 'waiting_for_review' || state === 'needs_connection' || state === 'needs_attention') ? 'bg-amber-50/60' : '',
                !selected && state === 'error' ? 'bg-rose-50/70' : '',
              )}
            >
              <div className="min-w-0">
                <div className="flex min-w-0 items-start justify-between gap-2">
                  <div className={cn('line-clamp-2 text-sm font-semibold leading-5', selected ? 'text-white' : 'text-slate-950')}>
                    {blueprint.name}
                  </div>
                  <span className={cn('shrink-0 rounded-full px-2 py-0.5 text-[11px] font-semibold ring-1', selected ? 'bg-white/10 text-slate-200 ring-white/15' : 'bg-sky-50 text-sky-700 ring-sky-100')}>
                    {agentExecutionModeLabel(mode)}
                  </span>
                </div>
                <div className={cn('mt-1 line-clamp-1 text-xs leading-5', selected ? 'text-slate-300' : 'text-slate-500')}>
                  {buildEmployeeDescription(blueprint, details)}
                </div>
              </div>
              <div className="grid gap-1">
                <div className="flex items-center justify-between gap-2">
                  <span className={cn('inline-flex min-h-7 items-center rounded-full px-2 py-0.5 text-[11px] font-semibold ring-1', employeeToneClass[status.tone])}>{status.label}</span>
                  <span className={cn('text-[11px] tabular-nums', selected ? 'text-slate-300' : 'text-slate-500')}>{agentNextRunLabel(blueprint, details)}</span>
                </div>
                <div className={cn('line-clamp-1 text-xs leading-5', selected ? 'text-slate-300' : 'text-slate-500')}>
                  {resultText || buildEmployeeLastActivity(blueprint, details, pendingApproval)}
                </div>
              </div>
            </button>
          );
        })
      )}
    </div>
  </aside>
);

const EmployeeAnswerCard = ({
  label,
  value,
  tone = 'slate',
}: {
  label: string;
  value: string;
  tone?: 'slate' | 'emerald' | 'amber' | 'rose';
}) => (
  <div className={cn(
    'rounded-xl px-4 py-4 shadow-[0_0_0_1px_rgba(15,23,42,0.08)]',
    tone === 'emerald' ? 'bg-emerald-50 text-emerald-950' : '',
    tone === 'amber' ? 'bg-amber-50 text-amber-950' : '',
    tone === 'rose' ? 'bg-rose-50 text-rose-950' : '',
    tone === 'slate' ? 'bg-slate-50 text-slate-950' : '',
  )}>
    <div className="text-xs font-semibold uppercase tracking-wide opacity-60">{label}</div>
    <div className="mt-2 text-sm font-medium leading-6 [text-wrap:pretty]">{value}</div>
  </div>
);

const EmployeeRunningPanel = ({
  blueprint,
  details,
  pendingApproval,
}: {
  blueprint: AgentBlueprint;
  details: AgentBlueprintDetails | null;
  pendingApproval: AgentApproval | null;
}) => {
  const attentionItems = buildEmployeeAttentionItems(blueprint, details, pendingApproval);
  const healthy = attentionItems.length === 0;
  return (
    <div className={cn(
      'rounded-2xl bg-white p-5 shadow-[0_1px_2px_rgba(15,23,42,0.06),0_0_0_1px_rgba(15,23,42,0.08)]',
      healthy ? 'lg:max-w-3xl' : '',
    )}>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex items-center gap-2 text-sm font-semibold text-emerald-700">
            <CheckCircle2 className="h-4 w-4" />
            Работает
          </div>
          <h3 className="mt-2 text-xl font-semibold leading-7 text-slate-950 [text-wrap:balance]">{blueprint.name}</h3>
          <p className="mt-2 text-sm leading-6 text-slate-600 [text-wrap:pretty]">
            {healthy ? 'Сотрудник работает. Когда всё спокойно, здесь остаётся только короткий статус.' : 'Есть вопросы, которые требуют вашего внимания.'}
          </p>
        </div>
      </div>

      <div className={cn('mt-5 grid gap-3', healthy ? 'sm:grid-cols-2' : 'lg:grid-cols-3')}>
        <EmployeeAnswerCard label="Следующий запуск" value={blueprint.active_version_number ? 'По расписанию сотрудника' : 'После включения'} tone="emerald" />
        <EmployeeAnswerCard label="Последняя задача" value={buildEmployeeLastActivity(blueprint, details || undefined, pendingApproval)} />
        {!healthy ? (
          <EmployeeAnswerCard label="Требует внимания" value={`${attentionItems.length} ${attentionItems.length === 1 ? 'задача' : 'задачи'}`} tone="amber" />
        ) : null}
      </div>

      {!healthy ? (
        <div className="mt-4 grid gap-2">
          {attentionItems.map((item) => (
            <div key={item.key} className={cn('rounded-xl px-3 py-3 text-sm leading-6 ring-1', item.tone === 'rose' ? 'bg-rose-50 text-rose-950 ring-rose-100' : 'bg-amber-50 text-amber-950 ring-amber-100')}>
              <div className="font-semibold text-slate-950">{item.title}</div>
              <div className="mt-1">{item.description}</div>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
};

const EmployeeTestResultPanel = ({
  activeRun,
  pendingApproval,
  actionLoading,
  needsScenarioRebuild = false,
  needsGoogleSheetsSetup = false,
  needsGoogleAccessReconnect = false,
  googleAccessJustConnected = false,
  nextAction,
  onApprove,
  onReject,
  onRunAgain,
  onRebuildScenario,
  onOpenGoogleSheetsSetup,
  onOpenGoogleAccessReconnect,
  onNextAction,
}: {
  activeRun: AgentRun | null;
  pendingApproval: AgentApproval | null;
  actionLoading: boolean;
  needsScenarioRebuild?: boolean;
  needsGoogleSheetsSetup?: boolean;
  needsGoogleAccessReconnect?: boolean;
  googleAccessJustConnected?: boolean;
  nextAction?: EmployeeNextAction | null;
  onApprove: () => void;
  onReject: () => void;
  onRunAgain: () => void;
  onRebuildScenario?: () => void;
  onOpenGoogleSheetsSetup?: () => void;
  onOpenGoogleAccessReconnect?: () => void;
  onNextAction?: () => void;
}) => {
  const result = buildEmployeeTestResult(activeRun, pendingApproval);
  const isWorkRun = activeRun?.input_json?.preview_mode === false;
  const labels = approvalActionLabels(pendingApproval);
  const isBlocked = result.state === 'blocker';
  const canApprove = Boolean(pendingApproval && !isBlocked);
  const canReject = Boolean(pendingApproval && !isBlocked);
  const canRebuildScenario = Boolean(needsScenarioRebuild && onRebuildScenario);
  const canRunAfterGoogleReconnect = Boolean(!canRebuildScenario && googleAccessJustConnected && needsGoogleAccessReconnect);
  const canOpenGoogleAccessReconnect = Boolean(!canRunAfterGoogleReconnect && !canRebuildScenario && needsGoogleAccessReconnect && onOpenGoogleAccessReconnect);
  const canOpenGoogleSheetsSetup = Boolean(!canRebuildScenario && !canOpenGoogleAccessReconnect && needsGoogleSheetsSetup && onOpenGoogleSheetsSetup);
  const canContinue = Boolean(
    !canApprove
    && !isBlocked
    && nextAction
    && ['enable', 'run_work', 'configure_schedule'].includes(nextAction.kind)
    && onNextAction,
  );
  const rerunLabel = canRebuildScenario
    ? 'Пересобрать сценарий'
    : canRunAfterGoogleReconnect
      ? 'Запустить тест'
      : canOpenGoogleAccessReconnect
        ? 'Переподключить Google-доступ'
        : canOpenGoogleSheetsSetup
          ? 'Указать Google-таблицу'
          : isWorkRun ? 'Запустить похожую' : 'Запустить тест ещё раз';
  const handleRerun = () => {
    if (canRebuildScenario && onRebuildScenario) {
      onRebuildScenario();
      return;
    }
    if (canOpenGoogleAccessReconnect && onOpenGoogleAccessReconnect) {
      onOpenGoogleAccessReconnect();
      return;
    }
    if (canOpenGoogleSheetsSetup && onOpenGoogleSheetsSetup) {
      onOpenGoogleSheetsSetup();
      return;
    }
    onRunAgain();
  };
  return (
    <div className="rounded-2xl bg-white p-5 shadow-[0_1px_2px_rgba(15,23,42,0.06),0_0_0_1px_rgba(15,23,42,0.08)]">
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_auto] xl:items-start">
        <div className="min-w-0 max-w-4xl">
          <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">{isWorkRun ? 'Результат работы' : 'Результат проверки'}</div>
          <h2 className="mt-2 max-w-3xl text-2xl font-semibold leading-8 text-slate-950 [text-wrap:balance]">{result.summary}</h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600 [text-wrap:pretty]">
            Это только бизнес-результат. Технические подробности находятся в расширенных настройках.
          </p>
        </div>
        <div className="flex min-w-0 flex-wrap gap-2 xl:justify-end">
          {canContinue && nextAction && onNextAction ? (
            <Button type="button" className="min-h-10 whitespace-nowrap active:scale-[0.96] transition-transform" onClick={onNextAction} disabled={actionLoading}>
              {actionLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : nextAction.kind === 'configure_schedule' ? <Clock3 className="mr-2 h-4 w-4" /> : <CheckCircle2 className="mr-2 h-4 w-4" />}
              {nextAction.label}
            </Button>
          ) : null}
          {canApprove ? (
            <Button type="button" className="min-h-10 whitespace-nowrap active:scale-[0.96] transition-transform" onClick={onApprove} disabled={actionLoading}>
              {actionLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <CheckCircle2 className="mr-2 h-4 w-4" />}
              {labels.approve}
            </Button>
          ) : null}
          {canReject ? (
            <Button type="button" variant="outline" className="min-h-10 whitespace-nowrap active:scale-[0.96] transition-transform" onClick={onReject} disabled={actionLoading}>
              {labels.reject}
            </Button>
          ) : null}
          <Button
            type="button"
            variant={canContinue || pendingApproval && !canRebuildScenario && !canOpenGoogleSheetsSetup ? 'outline' : 'default'}
            className="min-h-10 whitespace-nowrap active:scale-[0.96] transition-transform"
            onClick={handleRerun}
            disabled={actionLoading}
          >
            {actionLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : canRunAfterGoogleReconnect ? <Play className="mr-2 h-4 w-4" /> : canOpenGoogleAccessReconnect || canOpenGoogleSheetsSetup ? <Database className="mr-2 h-4 w-4" /> : <RefreshCw className="mr-2 h-4 w-4" />}
            {rerunLabel}
          </Button>
        </div>
      </div>

      {result.resultPayload ? (
        <div className={cn(
          'mt-5 rounded-2xl px-4 py-4 shadow-[inset_0_0_0_1px_rgba(15,23,42,0.08)]',
          result.state === 'blocker' ? 'bg-amber-50' : 'bg-slate-50',
        )}>
          <div className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-500">
            {result.state === 'blocker' ? 'Что мешает продолжить' : 'Подготовленный результат'}
          </div>
          <HumanResultView result={result.resultPayload} />
          {needsScenarioRebuild ? (
            <div className="mt-3 rounded-xl bg-white px-3 py-3 text-sm leading-6 text-amber-950 shadow-[inset_0_0_0_1px_rgba(217,119,6,0.18)]">
              Этот агент создан старой версией сценария: в нём нет шага чтения Google Sheets. Пересоберите сценарий, и LocalOS сразу запустит тест по новой версии.
            </div>
          ) : null}
          {needsGoogleSheetsSetup && !needsScenarioRebuild ? (
            <div className="mt-3 rounded-xl bg-white px-3 py-3 text-sm leading-6 text-amber-950 shadow-[inset_0_0_0_1px_rgba(217,119,6,0.18)]">
              Нужно указать конкретную таблицу и лист со списком поездок. Нажмите “Указать Google-таблицу” — откроется раздел источников этого сотрудника.
            </div>
          ) : null}
          {needsGoogleAccessReconnect && !needsScenarioRebuild ? (
            <div className="mt-3 rounded-xl bg-white px-3 py-3 text-sm leading-6 text-amber-950 shadow-[inset_0_0_0_1px_rgba(217,119,6,0.18)]">
              {googleAccessJustConnected
                ? 'Google-доступ подключён. Этот результат был получен до переподключения, поэтому запустите тест ещё раз.'
                : 'Google-доступ для чтения таблицы больше не работает. Нажмите “Переподключить Google-доступ” — откроется экран подключений с Google Таблицами.'}
            </div>
          ) : null}
        </div>
      ) : null}

      {result.output ? (
        <div className={cn(
          'rounded-xl px-4 py-4 text-sm leading-7 text-slate-700 shadow-[inset_0_0_0_1px_rgba(15,23,42,0.08)] whitespace-pre-wrap',
          result.resultPayload ? 'mt-3 bg-white' : 'mt-5 bg-slate-50',
        )}>
          {result.output}
        </div>
      ) : null}

      {!result.resultPayload && !result.output ? (
        <div className="mt-5 rounded-xl bg-slate-50 px-4 py-4 text-sm leading-7 text-slate-700 shadow-[inset_0_0_0_1px_rgba(15,23,42,0.08)]">
          Результат не был сохранён. Запустите тест ещё раз или откройте настройки для диагностики.
        </div>
      ) : null}

      {result.previewItems.length ? (
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          {result.previewItems.map((item) => (
            <div key={`${item.label}-${item.value}`} className="rounded-xl bg-white px-4 py-3 shadow-[0_0_0_1px_rgba(15,23,42,0.08)]">
              <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">{item.label}</div>
              <div className="mt-2 line-clamp-5 text-sm leading-6 text-slate-800">{item.value}</div>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
};

const EmployeeHistoryPanel = ({
  details,
  activeRun,
}: {
  details: AgentBlueprintDetails | null;
  activeRun: AgentRun | null;
}) => {
  const events = buildEmployeeHistoryStory(details, activeRun);
  return (
    <div className="rounded-2xl bg-white p-5 shadow-[0_1px_2px_rgba(15,23,42,0.06),0_0_0_1px_rgba(15,23,42,0.08)]">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">История</div>
          <h2 className="mt-2 text-xl font-semibold leading-7 text-slate-950 [text-wrap:balance]">Что сотрудник делал раньше</h2>
        </div>
        <span className="inline-flex min-h-8 items-center rounded-full bg-slate-50 px-3 py-1 text-xs font-medium text-slate-600 ring-1 ring-slate-200">
          {events.length ? `${events.length} событий` : 'пусто'}
        </span>
      </div>
      <div className="mt-5 grid gap-3">
        {events.length ? (
          events.map((event) => (
            <div key={event.key} className="grid gap-3 rounded-xl bg-slate-50 px-4 py-4 ring-1 ring-slate-100 sm:grid-cols-[7rem_minmax(0,1fr)]">
              <div className="text-sm font-medium tabular-nums text-slate-500">{event.time}</div>
              <div>
                <div className="text-sm font-semibold text-slate-950">{event.title}</div>
                <div className="mt-1 text-sm leading-6 text-slate-600">{event.description}</div>
              </div>
            </div>
          ))
        ) : (
          <div className="rounded-xl bg-slate-50 px-4 py-4 text-sm leading-6 text-slate-600 ring-1 ring-slate-100">
            История появится после первого теста или результата.
          </div>
        )}
      </div>
    </div>
  );
};

const EmployeeWorkspaceSection = ({
  title,
  children,
  tone = 'default',
}: {
  title: string;
  children: React.ReactNode;
  tone?: 'default' | 'quiet' | 'attention' | 'error';
}) => (
  <section className={cn(
    'rounded-2xl px-4 py-4 shadow-[0_1px_2px_rgba(15,23,42,0.04),0_0_0_1px_rgba(15,23,42,0.08)]',
    tone === 'default' ? 'bg-white' : '',
    tone === 'quiet' ? 'bg-slate-50' : '',
    tone === 'attention' ? 'bg-amber-50 text-amber-950 shadow-[0_1px_2px_rgba(120,53,15,0.05),0_0_0_1px_rgba(245,158,11,0.25)]' : '',
    tone === 'error' ? 'bg-rose-50 text-rose-950 shadow-[0_1px_2px_rgba(127,29,29,0.05),0_0_0_1px_rgba(244,63,94,0.24)]' : '',
  )}>
    <div className="text-xs font-semibold uppercase tracking-wide opacity-60">{title}</div>
    <div className="mt-2">{children}</div>
  </section>
);

const EmployeeResponsibilitiesList = ({ items }: { items: EmployeeResponsibility[] }) => (
  <div className="grid gap-2 sm:grid-cols-2">
    {items.map((item) => (
      <div key={item.key} className="flex min-h-10 items-start gap-2 rounded-xl bg-slate-50 px-3 py-2 text-sm leading-6 text-slate-800 shadow-[inset_0_0_0_1px_rgba(15,23,42,0.06)]">
        <CheckCircle2 className={cn('mt-1 h-4 w-4 shrink-0', item.done === false ? 'text-slate-300' : 'text-emerald-600')} />
        <span>{item.label}</span>
      </div>
    ))}
  </div>
);

const agentExecutionModeOptions: Array<{ value: AgentExecutionMode; label: string; description: string }> = [
  { value: 'one_off', label: 'Сделать один раз', description: 'После выполнения задача попадёт в завершённые.' },
  { value: 'manual', label: 'Запускать по кнопке', description: 'Вы запускаете работу, когда она нужна.' },
  { value: 'scheduled', label: 'По расписанию', description: 'Агент запускается в указанное время.' },
];

const AgentExecutionModePanel = ({
  mode,
  confirmationRequired,
  time,
  timezone,
  actionLoading,
  onModeChange,
  onTimeChange,
  onTimezoneChange,
  onSave,
}: {
  mode: AgentExecutionMode;
  confirmationRequired: boolean;
  time: string;
  timezone: string;
  actionLoading: boolean;
  onModeChange: (mode: AgentExecutionMode) => void;
  onTimeChange: (value: string) => void;
  onTimezoneChange: (value: string) => void;
  onSave: () => void;
}) => (
  <section className={cn(
    'rounded-2xl bg-white p-5 shadow-[0_1px_2px_rgba(15,23,42,0.06),0_0_0_1px_rgba(15,23,42,0.08)]',
    confirmationRequired ? 'shadow-[0_0_0_2px_rgba(249,115,22,0.25)]' : '',
  )}>
    <div className="max-w-3xl">
      <div className="text-xs font-semibold uppercase text-slate-500">Как запускается</div>
      <h2 className="mt-2 text-xl font-semibold leading-7 text-slate-950 [text-wrap:balance]">
        {confirmationRequired ? 'Подтвердите тип агента' : 'Тип запуска'}
      </h2>
      <p className="mt-1 text-sm leading-6 text-slate-600 [text-wrap:pretty]">
        Выбор меняет только способ запуска. Он не включает агента и не запускает работу.
      </p>
    </div>
    <div className="mt-4 grid gap-2 sm:grid-cols-3">
      {agentExecutionModeOptions.map(({ value, label, description }) => (
        <button
          key={value}
          type="button"
          onClick={() => onModeChange(value)}
          className={cn(
            'min-h-24 rounded-xl px-4 py-3 text-left shadow-[0_0_0_1px_rgba(15,23,42,0.10)] transition-[box-shadow,background-color,color] active:scale-[0.96] motion-reduce:transition-none',
            mode === value ? 'bg-slate-950 text-white shadow-[0_0_0_2px_rgba(15,23,42,1)]' : 'bg-white text-slate-950 hover:bg-slate-50',
          )}
        >
          <span className="block text-sm font-semibold">{label}</span>
          <span className={cn('mt-1 block text-xs leading-5', mode === value ? 'text-slate-300' : 'text-slate-500')}>{description}</span>
        </button>
      ))}
    </div>
    {mode === 'scheduled' ? (
      <div className="mt-4 grid gap-3 sm:grid-cols-[10rem_minmax(0,16rem)]">
        <label className="text-sm font-medium text-slate-800">
          Время
          <input type="time" value={time} onChange={(event) => onTimeChange(event.target.value)} className="mt-1 min-h-10 w-full rounded-lg bg-white px-3 shadow-[inset_0_0_0_1px_rgba(15,23,42,0.14)] outline-none" />
        </label>
        <label className="text-sm font-medium text-slate-800">
          Часовой пояс
          <select value={timezone} onChange={(event) => onTimezoneChange(event.target.value)} className="mt-1 min-h-10 w-full rounded-lg bg-white px-3 shadow-[inset_0_0_0_1px_rgba(15,23,42,0.14)] outline-none">
            <option value="Europe/Tallinn">Tallinn</option>
            <option value="Europe/Moscow">Москва</option>
            <option value="Europe/Helsinki">Helsinki</option>
            <option value="Europe/Riga">Riga</option>
          </select>
        </label>
      </div>
    ) : null}
    <Button type="button" className="mt-4 min-h-10 active:scale-[0.96] transition-transform" onClick={onSave} disabled={actionLoading || (mode === 'scheduled' && (!time || !timezone))}>
      {actionLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <CheckCircle2 className="mr-2 h-4 w-4" />}
      {confirmationRequired ? 'Подтвердить тип запуска' : 'Сохранить'}
    </Button>
  </section>
);

const AgentScheduleSetupPanel = ({
  time,
  timezone,
  actionLoading,
  onTimeChange,
  onTimezoneChange,
  onSave,
}: {
  time: string;
  timezone: string;
  actionLoading: boolean;
  onTimeChange: (value: string) => void;
  onTimezoneChange: (value: string) => void;
  onSave: () => void;
}) => (
  <section className="rounded-2xl bg-amber-50 p-5 shadow-[0_0_0_1px_rgba(217,119,6,0.2)]">
    <div className="max-w-3xl">
      <div className="text-xs font-semibold uppercase tracking-wide text-amber-700">Расписание</div>
      <h2 className="mt-2 text-xl font-semibold leading-7 text-amber-950 [text-wrap:balance]">Когда агент должен начинать работу</h2>
      <p className="mt-1 text-sm leading-6 text-amber-900 [text-wrap:pretty]">Время хранится вместе с часовым поясом, поэтому запуск не сдвинется при переходе на летнее время.</p>
    </div>
    <div className="mt-4 grid gap-3 sm:grid-cols-[10rem_minmax(0,16rem)_auto] sm:items-end">
      <label className="block text-sm font-medium text-amber-950">
        Время
        <input
          type="time"
          value={time}
          onChange={(event) => onTimeChange(event.target.value)}
          className="mt-1 min-h-10 w-full rounded-lg bg-white px-3 text-sm text-slate-950 shadow-[inset_0_0_0_1px_rgba(15,23,42,0.14)] outline-none focus:shadow-[inset_0_0_0_2px_rgba(249,115,22,0.65)]"
        />
      </label>
      <label className="block text-sm font-medium text-amber-950">
        Часовой пояс
        <select
          value={timezone}
          onChange={(event) => onTimezoneChange(event.target.value)}
          className="mt-1 min-h-10 w-full rounded-lg bg-white px-3 text-sm text-slate-950 shadow-[inset_0_0_0_1px_rgba(15,23,42,0.14)] outline-none focus:shadow-[inset_0_0_0_2px_rgba(249,115,22,0.65)]"
        >
          <option value="Europe/Tallinn">Tallinn</option>
          <option value="Europe/Moscow">Москва</option>
          <option value="Europe/Helsinki">Helsinki</option>
          <option value="Europe/Riga">Riga</option>
        </select>
      </label>
      <Button type="button" className="min-h-10 active:scale-[0.96] transition-transform" onClick={onSave} disabled={actionLoading || !time || !timezone}>
        {actionLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Clock3 className="mr-2 h-4 w-4" />}
        Сохранить расписание
      </Button>
    </div>
  </section>
);

const employeeStateTitle = (state: EmployeeWorkspaceState) => ({
  draft: 'Черновик',
  needs_mode: 'Выберите тип запуска',
  needs_connection: 'Не хватает подключения',
  ready_for_test: 'Готов к проверке',
  running_test: 'Проверка идёт',
  waiting_for_review: 'Ждёт вашего решения',
  blocked_result: 'Нужен следующий шаг',
  working: 'Работает',
  completed: 'Выполнено',
  needs_attention: 'Нужно включить',
  error: 'Ошибка',
}[state]);

const EmployeeAgentOverviewPanel = ({
  blueprint,
  details,
  activeRun,
  pendingApproval,
  action,
  actionLoading,
  onPrimaryAction,
  onOpenAdvanced,
}: {
  blueprint: AgentBlueprint;
  details: AgentBlueprintDetails | null;
  activeRun: AgentRun | null;
  pendingApproval: AgentApproval | null;
  action: EmployeeNextAction;
  actionLoading: boolean;
  onPrimaryAction: () => void;
  onOpenAdvanced: () => void;
}) => {
  const story = buildEmployeeWorkspaceStory(blueprint, details, pendingApproval);
  const latestRun = details?.runs?.[0] || null;
  const detailedLatestRun = activeRun?.id && activeRun.id === latestRun?.id ? activeRun : latestRun;
  const latestResult = findPreparedResultPayload(detailedLatestRun, pendingApproval);
  const healthy = story.state === 'working' && story.attention.length === 0;
  const problem = story.state === 'error' || story.state === 'waiting_for_review' || story.state === 'blocked_result' || story.state === 'needs_connection' || story.state === 'needs_attention';
  const actionDisabled = actionLoading || story.state === 'running_test';
  const userMode = buildAgentUserMode(blueprint, details);
  return (
    <div className={cn('space-y-4', healthy ? 'max-w-4xl' : 'max-w-5xl')}>
      <section className={cn(
        'rounded-3xl p-5 shadow-[0_18px_48px_rgba(15,23,42,0.08),0_0_0_1px_rgba(15,23,42,0.08)]',
        problem ? 'bg-white' : 'bg-white',
      )}>
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <EmployeeStatusPill status={story.status} />
              <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-600">
                {employeeStateTitle(story.state)}
              </span>
              <span className="rounded-full bg-sky-50 px-2.5 py-1 text-xs font-medium text-sky-700 ring-1 ring-sky-100">
                {userMode.label}
              </span>
            </div>
            <h1 className="mt-3 text-3xl font-semibold leading-9 text-slate-950 [text-wrap:balance]">{blueprint.name}</h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600 [text-wrap:pretty]">{story.status.summary}</p>
          </div>
          <Button
            type="button"
            className={cn(
              'min-h-12 shrink-0 px-5 active:scale-[0.96] transition-transform',
              story.state === 'error' ? 'bg-rose-600 text-white hover:bg-rose-700' : '',
            )}
            onClick={onPrimaryAction}
            disabled={actionDisabled}
          >
            {actionLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : action.kind === 'connect' ? <Database className="mr-2 h-4 w-4" /> : action.kind === 'approve' ? <ShieldCheck className="mr-2 h-4 w-4" /> : action.kind === 'enable' ? <CheckCircle2 className="mr-2 h-4 w-4" /> : <Play className="mr-2 h-4 w-4" />}
            {action.label}
          </Button>
        </div>
      </section>

      <EmployeeWorkspaceSection title="Что сотрудник делает">
        <EmployeeResponsibilitiesList items={story.responsibilities} />
        <div className="mt-3 rounded-xl bg-slate-50 px-3 py-3 text-sm leading-6 text-slate-600 shadow-[inset_0_0_0_1px_rgba(15,23,42,0.06)]">
          <span className="font-semibold text-slate-800">{userMode.flow}.</span> {userMode.description}
        </div>
      </EmployeeWorkspaceSection>

      <EmployeeWorkspaceSection title="Как запускается" tone={story.state === 'error' ? 'error' : problem ? 'attention' : 'quiet'}>
        <div className="text-base font-semibold leading-7 text-slate-950">{userMode.label}</div>
        <div className="mt-1 text-sm leading-6 opacity-75">{userMode.description}</div>
      </EmployeeWorkspaceSection>

      <div className="grid gap-4 lg:grid-cols-2">
        <EmployeeWorkspaceSection title="Последняя работа" tone={healthy ? 'quiet' : 'default'}>
          <div className="text-sm font-semibold leading-6 text-slate-950">{story.latestWork}</div>
        </EmployeeWorkspaceSection>
        <EmployeeWorkspaceSection title="Следующая работа" tone={healthy ? 'quiet' : 'default'}>
          <div className="text-sm font-semibold leading-6 text-slate-950">{story.nextWork}</div>
        </EmployeeWorkspaceSection>
      </div>

      {latestResult ? (
        <EmployeeWorkspaceSection title="Последний результат" tone="default">
          <div className="rounded-2xl bg-slate-50 px-4 py-4 shadow-[inset_0_0_0_1px_rgba(15,23,42,0.08)]">
            <HumanResultView result={latestResult} />
          </div>
        </EmployeeWorkspaceSection>
      ) : details?.runs?.[0]?.status === 'completed' ? (
        <EmployeeWorkspaceSection title="Последний результат" tone="attention">
          <div className="text-sm leading-6 text-slate-700">
            Сотрудник завершил тест, но не сохранил текст результата. Уточните формат результата и запустите тест ещё раз.
          </div>
        </EmployeeWorkspaceSection>
      ) : null}

      {story.attention.length ? (
        <EmployeeWorkspaceSection title="Требует вашего внимания" tone={story.state === 'error' ? 'error' : 'attention'}>
          <div className="grid gap-2">
            {story.attention.map((item) => (
              <div key={item.key} className="rounded-xl bg-white/70 px-3 py-3 text-sm leading-6 shadow-[inset_0_0_0_1px_rgba(15,23,42,0.08)]">
                <div className="font-semibold text-slate-950">{item.title}</div>
                <div className="mt-1 opacity-80">{item.description}</div>
              </div>
            ))}
          </div>
        </EmployeeWorkspaceSection>
      ) : null}

      <details className="rounded-2xl bg-white px-4 py-3 shadow-[0_1px_2px_rgba(15,23,42,0.04),0_0_0_1px_rgba(15,23,42,0.08)]">
        <summary className="cursor-pointer text-sm font-semibold text-slate-700">Расширенные настройки</summary>
        <div className="mt-4">
          <Button type="button" variant="outline" className="min-h-10 active:scale-[0.96] transition-transform" onClick={onOpenAdvanced}>
            Открыть настройки
          </Button>
        </div>
      </details>
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
  browserTargetUrls,
  browserDailyCap,
  telegramBotMode,
  telegramDailyCap,
  whatsappChannelMode,
  whatsappDailyCap,
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
  onBrowserTargetUrlsChange,
  onBrowserDailyCapChange,
  onTelegramBotModeChange,
  onTelegramDailyCapChange,
  onWhatsappChannelModeChange,
  onWhatsappDailyCapChange,
  onMatonAuthRefChange,
  onMatonChannelChange,
  onMatonDailyCapChange,
  onProcessRowValuesChange,
  onProcessPreviewMessageChange,
  onSaveSheetIntegration,
  onSaveBrowserUseIntegration,
  onSaveTelegramIntegration,
  onSaveWhatsappIntegration,
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
  browserTargetUrls: string;
  browserDailyCap: string;
  telegramBotMode: string;
  telegramDailyCap: string;
  whatsappChannelMode: string;
  whatsappDailyCap: string;
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
  onBrowserTargetUrlsChange: (value: string) => void;
  onBrowserDailyCapChange: (value: string) => void;
  onTelegramBotModeChange: (value: string) => void;
  onTelegramDailyCapChange: (value: string) => void;
  onWhatsappChannelModeChange: (value: string) => void;
  onWhatsappDailyCapChange: (value: string) => void;
  onMatonAuthRefChange: (value: string) => void;
  onMatonChannelChange: (value: string) => void;
  onMatonDailyCapChange: (value: string) => void;
  onProcessRowValuesChange: (value: string) => void;
  onProcessPreviewMessageChange: (value: string) => void;
  onSaveSheetIntegration: () => void;
  onSaveBrowserUseIntegration: () => void;
  onSaveTelegramIntegration: () => void;
  onSaveWhatsappIntegration: () => void;
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
  const settingsActive = mode === 'settings' || mode === 'connections' || mode === 'voice' || mode === 'advanced';
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
  <DashboardSection contentClassName="px-0 py-0">
    <div className="border-b border-slate-100 px-6 py-5">
      <div className="min-w-0">
        <h2 className="max-w-5xl text-lg font-semibold leading-7 text-slate-950 sm:text-xl">
          {blueprint.name}
        </h2>
        <p className="mt-1 text-sm leading-6 text-slate-600">
          {humanizeCategory(blueprint.category)} · {latestVersionNumber ? 'рабочий сценарий опубликован' : 'рабочий сценарий ещё не включён'}{voiceName ? ` · стиль: ${voiceName}` : ''}
        </p>
      </div>
      <div className="mt-4 flex max-w-full flex-wrap gap-2">
        <Button type="button" size="sm" className="shrink-0" variant={mode === 'overview' ? 'default' : 'outline'} onClick={() => onModeChange('overview')}>Обзор</Button>
        <Button type="button" size="sm" className="shrink-0" variant={mode === 'results' ? 'default' : 'outline'} onClick={() => onModeChange('results')}>История</Button>
        <Button type="button" size="sm" className="shrink-0" variant={mode === 'run' ? 'default' : 'outline'} onClick={() => onModeChange('run')}>Сценарий</Button>
        <Button type="button" size="sm" className="shrink-0" variant={settingsActive ? 'default' : 'outline'} onClick={() => onModeChange('settings')}>Настройки</Button>
        <Button type="button" size="sm" className="shrink-0 text-red-700 hover:text-red-800" variant="outline" onClick={onDeleteAgent} disabled={actionLoading}>
          <Trash2 className="mr-2 h-4 w-4" />
          Убрать из списка
        </Button>
      </div>
    </div>
    <div className="px-6 py-5">
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
      <div className="space-y-4">
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
        <AgentSettingsHub
          showAdvancedTools={showAdvancedTools}
          onOpenConnections={() => onModeChange('connections')}
          onOpenVoice={() => onModeChange('voice')}
          onOpenAdvanced={() => onModeChange('advanced')}
        />
      </div>
    ) : null}

    {mode === 'connections' ? (
      <AgentConnectionsPanel
        agentIntegrations={agentIntegrations}
        availableAgentIntegrations={availableAgentIntegrations}
        agentIntegrationCatalog={agentIntegrationCatalog}
        agentExternalAuthOptions={agentExternalAuthOptions}
        agentBindingStatus={agentBindingStatus}
        agentConnectionPlan={agentConnectionPlan}
        postCreateHandoff={postCreateHandoff}
        selectedConnectionBindingKey={selectedConnectionBindingKey}
        sheetSpreadsheetId={sheetSpreadsheetId}
        sheetName={sheetName}
        sheetAuthRef={sheetAuthRef}
        sheetDailyCap={sheetDailyCap}
        browserTargetUrls={browserTargetUrls}
        browserDailyCap={browserDailyCap}
        telegramBotMode={telegramBotMode}
        telegramDailyCap={telegramDailyCap}
        whatsappChannelMode={whatsappChannelMode}
        whatsappDailyCap={whatsappDailyCap}
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
        onBrowserTargetUrlsChange={onBrowserTargetUrlsChange}
        onBrowserDailyCapChange={onBrowserDailyCapChange}
        onTelegramBotModeChange={onTelegramBotModeChange}
        onTelegramDailyCapChange={onTelegramDailyCapChange}
        onWhatsappChannelModeChange={onWhatsappChannelModeChange}
        onWhatsappDailyCapChange={onWhatsappDailyCapChange}
        onMatonAuthRefChange={onMatonAuthRefChange}
        onMatonChannelChange={onMatonChannelChange}
        onMatonDailyCapChange={onMatonDailyCapChange}
        onProcessRowValuesChange={onProcessRowValuesChange}
        onProcessPreviewMessageChange={onProcessPreviewMessageChange}
        onSaveSheetIntegration={onSaveSheetIntegration}
        onSaveBrowserUseIntegration={onSaveBrowserUseIntegration}
        onSaveTelegramIntegration={onSaveTelegramIntegration}
        onSaveWhatsappIntegration={onSaveWhatsappIntegration}
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
      <AgentScenarioPanel
        blueprint={blueprint}
        blueprintDetails={blueprintDetails}
        bindingStatus={agentBindingStatus}
        actionLoading={actionLoading}
        onStartRun={onStartRun}
        runSource={runSource}
        runCity={runCity}
        runCategory={runCategory}
        runLimit={runLimit}
        onRunSourceChange={onRunSourceChange}
        onRunCityChange={onRunCityChange}
        onRunCategoryChange={onRunCategoryChange}
        onRunLimitChange={onRunLimitChange}
      />
    ) : null}

    {mode === 'results' ? (
      <div className="space-y-4">
        <AgentBusinessHistoryPanel
          blueprintDetails={blueprintDetails}
          activeRun={activeRun}
        />
        {activeRun ? (
          <PreviewRunSummaryPanel
            summary={activeRun.observability?.preview_summary}
            runInput={activeRun.input_json && typeof activeRun.input_json === 'object' ? activeRun.input_json : {}}
            activationGate={activationGate}
            currentActiveVersionId={activeVersionId}
            actionLoading={actionLoading}
            onNextStepAction={handlePreviewNextStep}
            onActivateVersion={onActivateVersion}
          />
        ) : null}
        {pendingApproval ? (
          <AgentApprovalDecisionPanel
            approval={pendingApproval}
            actionLoading={actionLoading}
            onApprove={onApprove}
            onReject={onReject}
          />
        ) : null}
        {queuedButNotDispatched ? (
          <DashboardActionPanel
            title="Поставлено в очередь, но не отправлено"
            description="Агент поставил batch в безопасную очередь. Dispatcher не запускался из этого экрана."
            tone="amber"
          />
        ) : null}
        <details className="rounded-2xl border border-slate-200 bg-white px-4 py-3">
          <summary className="cursor-pointer text-sm font-semibold text-slate-700">
            Как агент дошёл до результата
          </summary>
          <div className="mt-4">
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
          </div>
        </details>
        <details className="rounded-2xl border border-slate-200 bg-white px-4 py-3">
          <summary className="cursor-pointer text-sm font-semibold text-slate-700">
            Журнал и подробности
          </summary>
          <div className="mt-4">
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
          </div>
        </details>
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
    </div>
  </DashboardSection>
  );
};

const AgentBusinessHistoryPanel = ({
  blueprintDetails,
  activeRun,
}: {
  blueprintDetails: AgentBlueprintDetails | null;
  activeRun: AgentRun | null;
}) => {
  const events = buildBusinessHistoryEvents(blueprintDetails, activeRun);
  return (
    <div className="rounded-2xl border border-slate-200 bg-white px-4 py-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-slate-950">История работы</div>
          <div className="mt-1 text-sm leading-6 text-slate-600">События бизнеса: что подготовлено, что ждёт решения и чем завершился запуск.</div>
        </div>
        <span className="rounded-full bg-slate-50 px-2.5 py-1 text-xs font-medium text-slate-600 ring-1 ring-slate-200">
          {events.length ? `${events.length} событий` : 'пусто'}
        </span>
      </div>
      <div className="mt-4 grid gap-2">
        {events.length ? (
          events.map((event) => (
            <div key={event.key} className="grid gap-2 rounded-xl bg-slate-50 px-3 py-3 text-sm ring-1 ring-slate-100 sm:grid-cols-[6rem_minmax(0,1fr)]">
              <div className="text-xs font-medium text-slate-500">{event.time}</div>
              <div>
                <div className="font-semibold text-slate-950">{event.title}</div>
                <div className="mt-1 leading-6 text-slate-600">{event.description}</div>
              </div>
            </div>
          ))
        ) : (
          <div className="rounded-xl bg-slate-50 px-3 py-3 text-sm leading-6 text-slate-600 ring-1 ring-slate-100">
            История появится после первого запуска или ручного решения.
          </div>
        )}
      </div>
    </div>
  );
};

const AgentSettingsHub = ({
  showAdvancedTools,
  onOpenConnections,
  onOpenVoice,
  onOpenAdvanced,
}: {
  showAdvancedTools: boolean;
  onOpenConnections: () => void;
  onOpenVoice: () => void;
  onOpenAdvanced: () => void;
}) => (
  <div className="rounded-2xl border border-slate-200 bg-white px-4 py-4">
    <div className="text-sm font-semibold text-slate-950">Ещё настройки</div>
    <div className="mt-1 text-sm leading-6 text-slate-600">
      Подключения, голос, версии и диагностика доступны здесь, но не мешают обычному просмотру результата.
    </div>
    <div className="mt-4 grid gap-2 sm:grid-cols-3">
      <Button type="button" variant="outline" onClick={onOpenConnections}>
        <Database className="mr-2 h-4 w-4" />
        Подключения
      </Button>
      <Button type="button" variant="outline" onClick={onOpenVoice}>
        <MessageSquareText className="mr-2 h-4 w-4" />
        Голос и стиль
      </Button>
      {showAdvancedTools ? (
        <Button type="button" variant="outline" onClick={onOpenAdvanced}>
          <Wrench className="mr-2 h-4 w-4" />
          Диагностика
        </Button>
      ) : null}
    </div>
  </div>
);

const AgentScenarioPanel = ({
  blueprint,
  blueprintDetails,
  bindingStatus,
  actionLoading,
  onStartRun,
  runSource,
  runCity,
  runCategory,
  runLimit,
  onRunSourceChange,
  onRunCityChange,
  onRunCategoryChange,
  onRunLimitChange,
}: {
  blueprint: AgentBlueprint;
  blueprintDetails: AgentBlueprintDetails | null;
  bindingStatus: AgentIntegrationBindingStatus[];
  actionLoading: boolean;
  onStartRun: () => void;
  runSource: string;
  runCity: string;
  runCategory: string;
  runLimit: string;
  onRunSourceChange: (value: string) => void;
  onRunCityChange: (value: string) => void;
  onRunCategoryChange: (value: string) => void;
  onRunLimitChange: (value: string) => void;
}) => {
  const steps = buildScenarioPipeline(blueprint, blueprintDetails, bindingStatus);
  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-slate-200 bg-white px-4 py-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <div className="text-sm font-semibold text-slate-950">Что будет делать агент</div>
            <div className="mt-1 max-w-3xl text-sm leading-6 text-slate-600">
              Это рабочий сценарий человеческим языком. Техническое представление скрыто ниже и не меняет опубликованную логику само по себе.
            </div>
          </div>
          <Button type="button" onClick={onStartRun} disabled={actionLoading}>
            {actionLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Play className="mr-2 h-4 w-4" />}
            Проверить без отправки
          </Button>
        </div>
        <div className="mt-5 grid gap-3">
          {steps.map((step, index) => (
            <div key={step.key} className="grid gap-3 rounded-xl bg-slate-50 px-3 py-3 ring-1 ring-slate-100 sm:grid-cols-[auto_minmax(0,1fr)]">
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-white text-sm font-semibold text-slate-800 ring-1 ring-slate-200">
                {index + 1}
              </div>
              <div>
                <div className="text-sm font-semibold text-slate-950">{step.title}</div>
                <div className="mt-1 text-sm leading-6 text-slate-600">{step.description}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {blueprint.category === 'outreach' ? (
        <details className="rounded-2xl border border-slate-200 bg-white px-4 py-3">
          <summary className="cursor-pointer text-sm font-semibold text-slate-700">Параметры проверки поиска</summary>
          <div className="mt-4 grid gap-3 md:grid-cols-4">
            <input className="rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-slate-400" value={runSource} onChange={(event) => onRunSourceChange(event.target.value)} placeholder="Источник" />
            <input className="rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-slate-400" value={runCity} onChange={(event) => onRunCityChange(event.target.value)} placeholder="Город" />
            <input className="rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-slate-400" value={runCategory} onChange={(event) => onRunCategoryChange(event.target.value)} placeholder="Категория" />
            <input className="rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-slate-400" value={runLimit} onChange={(event) => onRunLimitChange(event.target.value)} placeholder="Лимит" />
          </div>
        </details>
      ) : null}

      <details className="rounded-2xl border border-slate-200 bg-white px-4 py-3">
        <summary className="cursor-pointer text-sm font-semibold text-slate-700">Показать техническое представление</summary>
        <div className="mt-4 rounded-xl bg-slate-950 px-3 py-3 text-xs leading-5 text-slate-100">
          <pre className="max-h-80 overflow-auto whitespace-pre-wrap">{JSON.stringify(blueprintDetails?.active_version || blueprintDetails?.versions?.[0] || {}, null, 2)}</pre>
        </div>
      </details>
    </div>
  );
};

const AgentApprovalDecisionPanel = ({
  approval,
  actionLoading,
  onApprove,
  onReject,
  compact = false,
}: {
  approval: AgentApproval;
  actionLoading: boolean;
  onApprove?: () => void;
  onReject?: () => void;
  compact?: boolean;
}) => {
  const labels = approvalActionLabels(approval);
  const previewItems = getApprovalPreviewItems(approval);
  return (
    <div className={cn(
      'rounded-2xl border border-amber-200 bg-amber-50 px-4 py-4 text-amber-950',
      compact ? 'text-sm' : '',
    )}>
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="text-sm font-semibold uppercase tracking-wide text-amber-700">Нужно решение человека</div>
          <h3 className="mt-1 text-lg font-semibold leading-7 text-slate-950">
            {approvalDecisionTitle(approval)}
          </h3>
          <div className="mt-2 text-sm leading-6 text-amber-900">
            {approval.title}. {explainApproval(approval)}
          </div>
        </div>
        {onApprove && onReject ? (
          <div className="flex shrink-0 flex-wrap gap-2">
            <Button type="button" onClick={onApprove} disabled={actionLoading}>
              {labels.approve}
            </Button>
            <Button type="button" variant="outline" onClick={onReject} disabled={actionLoading}>
              {labels.reject}
            </Button>
          </div>
        ) : null}
      </div>

      {previewItems.length ? (
        <div className="mt-4 grid gap-2 lg:grid-cols-2">
          {previewItems.map((item) => (
            <div key={`${item.label}-${item.value}`} className="rounded-xl bg-white/85 px-3 py-2 text-sm leading-6 text-slate-800 ring-1 ring-amber-100">
              <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">{item.label}</div>
              <div className="mt-1 line-clamp-4">{item.value}</div>
            </div>
          ))}
        </div>
      ) : (
        <div className="mt-4 rounded-xl bg-white/85 px-3 py-2 text-sm leading-6 text-slate-800 ring-1 ring-amber-100">
          <span className="font-semibold text-slate-950">Что просит агент: </span>{approval.title}. Агент не использует этот результат дальше, пока человек явно не примет решение.
        </div>
      )}

      <div className="mt-4 grid gap-2 md:grid-cols-2">
        <div className="rounded-xl bg-white/85 px-3 py-2 text-sm leading-6 text-slate-800 ring-1 ring-amber-100">
          <span className="font-semibold text-slate-950">Если нажать “Принять”: </span>{labels.approve}
        </div>
        <div className="rounded-xl bg-white/85 px-3 py-2 text-sm leading-6 text-slate-800 ring-1 ring-amber-100">
          <span className="font-semibold text-slate-950">Если нажать “Отклонить”: </span>{labels.reject}
        </div>
      </div>
    </div>
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
  const builderPreview = getBlueprintBuilderPreview(detailsBlueprint || blueprint);
  const taskAnswer = builderPreview?.understood_task || blueprint.description || blueprint.active_goal || blueprint.latest_goal || 'Настройте задачу агента.';
  const readyAnswer = needsApproval
    ? 'ждёт решения человека'
    : !connectorsReady
      ? 'нужно подключить сервисы'
      : compiledKnown && !compiledValid
        ? 'нужно исправить логику'
        : !previewReady
          ? 'готов к тесту'
          : activationGate?.can_activate
            ? 'можно включить'
            : humanizeStatus(listStatus);
  const readyTone: 'default' | 'warning' = needsApproval || !connectorsReady || (compiledKnown && !compiledValid) ? 'warning' : 'default';
  const missingAnswer = needsApproval
    ? 'одобрение перед внешним действием'
    : !connectorsReady
      ? `${missingBindings} из ${requiredBindings} подключений`
    : compiledKnown && !compiledValid
        ? 'проверенная логика'
        : !previewReady
          ? 'тест без отправки'
          : 'ничего критичного';
  const lastRunAnswer = formatLastRun(blueprint);

  return (
    <div className="space-y-4">
      {needsApproval ? (
      <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <div className="text-sm font-semibold text-slate-950">
              {pendingApproval ? approvalDecisionTitle(pendingApproval) : 'Ждёт решения человека'}
            </div>
            <div className="mt-1 text-sm leading-6 text-amber-900">
              {pendingApproval
                ? explainApproval(pendingApproval)
                : 'Проверьте ручное решение: без него агент не продолжит внешний шаг.'}
            </div>
            {pendingApproval ? (
              <div className="mt-2 grid gap-2 md:grid-cols-2">
                {getApprovalPreviewItems(pendingApproval).slice(0, 2).map((item) => (
                  <div key={`${item.label}-${item.value}`} className="rounded-xl bg-white/80 px-3 py-2 text-xs leading-5 text-amber-900 ring-1 ring-amber-100">
                    <span className="font-semibold text-slate-800">{item.label}: </span>{item.value}
                  </div>
                ))}
                <div className="rounded-xl bg-white/80 px-3 py-2 text-xs leading-5 text-amber-900 ring-1 ring-amber-100">
                  <span className="font-semibold text-slate-800">При “Принять”: </span>{approvalActionLabels(pendingApproval).approve}
                </div>
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

      <AgentFourAnswerStrip
        task={taskAnswer}
        ready={readyAnswer}
        missing={missingAnswer}
        lastRun={lastRunAnswer}
        readyTone={readyTone}
        missingTone={missingAnswer === 'ничего критичного' ? 'default' : 'warning'}
      />

      <AgentProductCockpit
        blueprint={blueprint}
        preview={builderPreview}
        activationGate={activationGate}
        connectorsReady={connectorsReady}
        compiledReady={!compiledKnown || compiledValid}
        previewReady={previewReady}
        activationVersionId={activationVersionId}
        needsApproval={needsApproval}
        actionLoading={actionLoading}
        onOpenConnections={onOpenConnections}
        onOpenLogic={onOpenLogic}
        onOpenResults={onOpenResults}
        onStartRun={onStartRun}
        onActivateVersion={onActivateVersion}
      />

      <AgentConfidencePanel facts={buildConfidenceFacts(activationGate)} />

      {activationGate && !needsApproval ? (
        <ActivationGateDecisionCard
          gate={activationGate}
        />
      ) : null}

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(18rem,0.55fr)]">
        <div className="rounded-2xl border border-slate-200 bg-white px-4 py-4">
          <div className="text-sm font-semibold text-slate-950">Управление</div>
          <div className="mt-2 text-sm leading-7 text-slate-700">
            Здесь можно перейти к настройкам агента. Технические версии и журналы доступны в разделе “Техническое”.
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
              Убрать из списка
            </Button>
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white px-4 py-4">
          <div className="text-sm font-semibold text-slate-950">Стоимость</div>
          <div className="mt-2 rounded-xl bg-slate-50 px-3 py-2 text-xs leading-5 text-slate-600">
            {voiceName ? `Голос: ${voiceName}. ` : ''}
            До запуска показываем оценку, после запуска — фактическое списание за создание, тест, обычный запуск, внешнее действие и чат оператора.
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
  activationVersionId,
  needsApproval,
  actionLoading,
  onOpenConnections,
  onOpenLogic,
  onOpenResults,
  onStartRun,
  onActivateVersion,
}: {
  blueprint: AgentBlueprint;
  preview: AgentBuilderPreview | null;
  activationGate?: AgentActivationGate;
  connectorsReady: boolean;
  compiledReady: boolean;
  previewReady: boolean;
  activationVersionId: string;
  needsApproval: boolean;
  actionLoading: boolean;
  onOpenConnections: () => void;
  onOpenLogic: () => void;
  onOpenResults: () => void;
  onStartRun: () => void;
  onActivateVersion: (versionId: string) => void;
}) => {
  const summary = preview?.connection_summary;
  const missingItems = (summary?.items || []).filter((item) => item.action && !['ready', 'native_ready'].includes(item.action));
  const readyItems = (summary?.items || []).filter((item) => item.action === 'ready' || item.action === 'native_ready');
  const setupFlow = preview?.setup_flow;
  const nextStep = activationGate?.next_step || setupFlow?.post_create_next_step || setupFlow?.next_step || '';
  const needsConnections = !connectorsReady || missingItems.length > 0 || nextStep === 'connect_required_integrations';
  const needsLogic = !compiledReady || nextStep === 'fix_compiled_workflow';
  const canActivate = !needsApproval && activationGate?.can_activate === true && Boolean(activationVersionId);
  const canPreview = connectorsReady && compiledReady && !previewReady;
  const primaryLabel = needsApproval
    ? 'Открыть решение'
    : canActivate
    ? 'Включить агента'
    : needsConnections
    ? 'Подключить сервисы'
    : canPreview
      ? 'Запустить тест'
      : needsLogic
        ? 'Открыть логику'
        : previewReady ? 'Открыть историю' : 'Запустить тест';
  const PrimaryIcon = needsApproval ? ShieldCheck : canActivate ? CheckCircle2 : needsConnections ? Database : canPreview ? Play : needsLogic ? Workflow : previewReady ? FileCheck2 : Play;
  const primaryAction = needsApproval ? onOpenResults : canActivate ? () => onActivateVersion(activationVersionId) : needsConnections ? onOpenConnections : canPreview ? onStartRun : needsLogic ? onOpenLogic : previewReady ? onOpenResults : onStartRun;
  const primaryVariant: 'default' | 'outline' = needsApproval || canActivate || needsConnections || canPreview || needsLogic ? 'default' : 'outline';
  const task = preview?.understood_task || blueprint.description || blueprint.active_goal || blueprint.latest_goal || 'Настройте задачу агента.';
  const uniqueReadyTitles = Array.from(new Set(readyItems.map((item) => item.title || connectorLabel(item.provider)).filter(Boolean)));
  const uniqueMissingTitles = Array.from(new Set(missingItems.map((item) => item.title || connectorLabel(item.provider)).filter(Boolean)));
  const dataText = preview?.data_sources?.length
    ? builderPreviewDataText(preview, task)
    : readyItems.length
      ? uniqueReadyTitles.join(', ')
      : 'будет видно после настройки';
  const requiredText = missingItems.length
    ? uniqueMissingTitles.join(', ')
    : connectorsReady
      ? 'подключения готовы'
      : 'проверить подключения';
  const proofHint = needsApproval
    ? 'Агент уже остановился на ручном решении. Откройте историю, проверьте результат и решите, продолжать ли следующий шаг.'
    : needsConnections
      ? 'Сначала подключите источник или канал. После этого здесь появится тестовый запуск без внешней отправки.'
      : canPreview
        ? 'Нажмите “Запустить тест”: LocalOS прочитает пример, подготовит результат и остановится перед внешним действием.'
        : previewReady
          ? 'Тест уже проходил. Откройте историю, чтобы посмотреть, что агент прочитал, что подготовил и где остановился.'
          : 'Запустите тест без внешней отправки и проверьте первый результат в истории.';
  const flowStatus = setupFlow?.status || (activationGate?.can_activate ? 'ready' : 'draft');
  return (
    <div className="rounded-2xl border border-slate-200 bg-white px-4 py-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <div className="text-sm font-semibold text-slate-950">Как проверить сейчас</div>
            <span className="rounded-full bg-slate-50 px-2 py-0.5 text-[11px] font-medium text-slate-600 ring-1 ring-slate-200">
              {agentFlowStatusLabel(flowStatus)}
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
        <AgentCockpitFact icon={Database} label="1. Данные" value={dataText} ready={Boolean(preview?.data_sources?.length || readyItems.length)} />
        <AgentCockpitFact icon={ShieldCheck} label="2. Доступы" value={requiredText} ready={!needsConnections} />
        <AgentCockpitFact icon={Play} label="3. Тест" value={previewReady ? 'результат в истории' : canPreview ? 'можно запускать' : 'после подключения'} ready={previewReady || canPreview} />
      </div>
      <div className="mt-3 flex flex-col gap-3 rounded-xl bg-sky-50 px-3 py-3 text-sm leading-6 text-sky-950 ring-1 ring-sky-100 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">{proofHint}</div>
        <Button type="button" size="sm" variant="outline" onClick={onOpenResults} className="shrink-0 bg-white/80">
          История
        </Button>
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
              {userFacingAgentTechText(item.setup_cta?.label) || `Подключить ${item.title || connectorLabel(item.provider)}`}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
};

const AgentConfidencePanel = ({ facts }: { facts: AgentConfidenceFact[] }) => (
  <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-4 text-emerald-950">
    <div className="flex items-start gap-3">
      <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-emerald-700" />
      <div className="min-w-0">
        <div className="text-sm font-semibold text-slate-950">Почему этому можно доверять</div>
        <div className="mt-1 text-sm leading-6 text-emerald-900">
          LocalOS запускает опубликованный сценарий, проверяет доступы и останавливается перед действиями, которые должен подтвердить человек.
        </div>
      </div>
    </div>
    <div className="mt-3 grid gap-2 md:grid-cols-2 xl:grid-cols-3">
      {facts.map((fact) => (
        <div key={fact.key} className="flex items-start gap-2 rounded-xl bg-white/80 px-3 py-2 text-sm leading-6 ring-1 ring-emerald-100">
          {fact.ready ? (
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
          ) : (
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
          )}
          <span className="text-slate-800">{fact.label}</span>
        </div>
      ))}
    </div>
  </div>
);

const AgentFourAnswerStrip = ({
  task,
  ready,
  missing,
  lastRun,
  readyTone,
  missingTone,
}: {
  task: string;
  ready: string;
  missing: string;
  lastRun: string;
  readyTone: 'default' | 'warning';
  missingTone: 'default' | 'warning';
}) => (
  <div className="grid gap-3 xl:grid-cols-4">
    <AgentAnswerCard label="Что делает" value={task} />
    <AgentAnswerCard label="Готов ли" value={ready} tone={readyTone} />
    <AgentAnswerCard label="Чего не хватает" value={missing} tone={missingTone} />
    <AgentAnswerCard label="Последний запуск" value={lastRun} />
  </div>
);

const AgentAnswerCard = ({
  label,
  value,
  tone = 'default',
}: {
  label: string;
  value: string;
  tone?: 'default' | 'warning';
}) => (
  <div className={cn(
    'rounded-2xl border px-4 py-3',
    tone === 'warning' ? 'border-amber-200 bg-amber-50' : 'border-slate-200 bg-white',
  )}>
    <div className={cn(
      'text-xs font-semibold uppercase',
      tone === 'warning' ? 'text-amber-700' : 'text-slate-500',
    )}>
      {label}
    </div>
    <div className="mt-1 line-clamp-3 text-sm font-semibold leading-6 text-slate-950">{value}</div>
  </div>
);

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
}: {
  gate: AgentActivationGate;
}) => {
  const decision = buildActivationGateDecision(gate);
  const ready = decision.tone === 'ready';
  const choice = decision.tone === 'choice';
  const blocked = decision.tone === 'blocked';
  const needsAction = decision.tone === 'needs_action';
  const blockerText = activationBlockerText(gate);
  const pathSteps = buildActivationPathSteps(gate);
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
          <div className="font-semibold">{userFacingAgentTechText(decision.title)}</div>
          <div className="mt-1 text-xs leading-5">{userFacingAgentTechText(decision.description)}</div>
          {blockerText && !ready ? (
            <div className="mt-2 rounded-xl bg-white/80 px-3 py-2 text-xs leading-5 ring-1 ring-current/10">
              Почему ждём: {userFacingAgentTechText(blockerText)}
            </div>
          ) : null}
          <div className="mt-2 flex flex-wrap gap-1.5">
            <span className="rounded-full bg-white/80 px-2 py-0.5 text-[11px] font-medium ring-1 ring-current/10">
              Тест: {gate.preview_run_status?.ready ? 'пройден' : 'нужен'}
            </span>
            <span className="rounded-full bg-white/80 px-2 py-0.5 text-[11px] font-medium ring-1 ring-current/10">
              Доступы: {gate.preflight?.ready ? 'готовы' : 'проверить'}
            </span>
            <span className="rounded-full bg-white/80 px-2 py-0.5 text-[11px] font-medium ring-1 ring-current/10">
              Логика: {gate.compiled_validation?.ready ? 'проверена' : 'проверить'}
            </span>
            <span className="rounded-full bg-white/80 px-2 py-0.5 text-[11px] font-medium ring-1 ring-current/10">
              Подтверждение: {gate.approval_policy_status?.ready ? 'готово' : 'проверить'}
            </span>
          </div>
          <AgentActivationPathStrip steps={pathSteps} />
        </div>
        <span className="rounded-full bg-white px-2.5 py-1 text-xs font-medium ring-1 ring-current/10">
          Карта готовности
        </span>
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

const AgentBillingBreakdownPanel = ({ metrics }: { metrics?: AgentMetricsSummary }) => {
  const ledger = metrics?.unified_billing_ledger;
  const items = ledger?.items || metrics?.billing_breakdown?.items || metrics?.cost_tokens?.breakdown || [];
  const visibleItems = items.filter((item) => Boolean(
    item.count
    || item.charged_credits
    || item.actual_credits
    || item.estimated_credits
    || item.estimated_tokens
    || item.actual_tokens
    || item.settled_tokens
    || item.actual_cost
    || item.total_cost,
  ));
  if (!visibleItems.length) {
    return (
      <div className="mt-3 rounded-xl bg-white px-3 py-2 text-xs leading-5 text-slate-500 ring-1 ring-slate-200">
        История списаний появится после создания, теста или обычного запуска.
      </div>
    );
  }
  return (
    <div className="mt-3 rounded-xl bg-white px-3 py-3 ring-1 ring-slate-200">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-center gap-2 text-xs font-semibold uppercase text-slate-500">
          <ReceiptText className="h-4 w-4 text-slate-500" />
          История списаний
        </div>
        <div className="text-xs leading-5 text-slate-500">
          Оценка до запуска: {formatBillingEstimateSummary(ledger)}
          <span className="mx-1 text-slate-300"> / </span>
          Факт после запуска: {formatBillingActualSummary(ledger)}
        </div>
      </div>
      <div className="mt-2 space-y-1.5">
        {visibleItems.slice(0, 5).map((item) => (
          <div key={item.key || item.label} className="grid gap-1 rounded-lg bg-slate-50 px-2.5 py-2 text-xs leading-5 sm:grid-cols-[minmax(0,1fr)_auto_auto] sm:items-center">
            <span className="min-w-0 truncate font-medium text-slate-700">{userFacingAgentTechText(item.label || humanizeMeta(item.key || 'cost'))}</span>
            <span className="text-slate-500">оценка {formatBillingEstimateValue(item)}</span>
            <span className="font-semibold text-slate-950">факт {formatBillingActualValue(item)}</span>
          </div>
        ))}
      </div>
    </div>
  );
};

const formatBillingEstimateSummary = (ledger?: AgentUnifiedBillingLedger) => {
  const summary = ledger?.summary || {};
  const credits = Number(summary.estimated_credits || 0);
  if (!credits) {
    return 'нет';
  }
  return `${credits} кр.`;
};

const formatBillingActualSummary = (ledger?: AgentUnifiedBillingLedger) => {
  const summary = ledger?.summary || {};
  const credits = Number(summary.actual_credits || 0);
  if (!credits) {
    return 'нет списаний';
  }
  return `${credits} кр.`;
};

const formatBillingEstimateValue = (item: AgentBillingBreakdownItem) => {
  const credits = Number(item.estimated_credits || 0);
  if (credits) {
    return `${credits} кр.`;
  }
  return '0 кр.';
};

const formatBillingActualValue = (item: AgentBillingBreakdownItem) => {
  const credits = Number(item.actual_credits || item.charged_credits || 0);
  if (credits) {
    return `${credits} кр.`;
  }
  return '0 кр.';
};

const AgentConnectionsPanel = ({
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
  browserTargetUrls,
  browserDailyCap,
  telegramBotMode,
  telegramDailyCap,
  whatsappChannelMode,
  whatsappDailyCap,
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
  onBrowserTargetUrlsChange,
  onBrowserDailyCapChange,
  onTelegramBotModeChange,
  onTelegramDailyCapChange,
  onWhatsappChannelModeChange,
  onWhatsappDailyCapChange,
  onMatonAuthRefChange,
  onMatonChannelChange,
  onMatonDailyCapChange,
  onProcessRowValuesChange,
  onProcessPreviewMessageChange,
  onSaveSheetIntegration,
  onSaveBrowserUseIntegration,
  onSaveTelegramIntegration,
  onSaveWhatsappIntegration,
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
  postCreateHandoff: AgentPostCreateHandoff | null;
  selectedConnectionBindingKey: string;
  sheetSpreadsheetId: string;
  sheetName: string;
  sheetAuthRef: string;
  sheetDailyCap: string;
  browserTargetUrls: string;
  browserDailyCap: string;
  telegramBotMode: string;
  telegramDailyCap: string;
  whatsappChannelMode: string;
  whatsappDailyCap: string;
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
  onBrowserTargetUrlsChange: (value: string) => void;
  onBrowserDailyCapChange: (value: string) => void;
  onTelegramBotModeChange: (value: string) => void;
  onTelegramDailyCapChange: (value: string) => void;
  onWhatsappChannelModeChange: (value: string) => void;
  onWhatsappDailyCapChange: (value: string) => void;
  onMatonAuthRefChange: (value: string) => void;
  onMatonChannelChange: (value: string) => void;
  onMatonDailyCapChange: (value: string) => void;
  onProcessRowValuesChange: (value: string) => void;
  onProcessPreviewMessageChange: (value: string) => void;
  onSaveSheetIntegration: () => void;
  onSaveBrowserUseIntegration: () => void;
  onSaveTelegramIntegration: () => void;
  onSaveWhatsappIntegration: () => void;
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
        <div className="font-semibold">{userFacingAgentTechText(postCreateHandoff.title || 'Остались подключения')}</div>
        <div className="mt-1">{userFacingAgentTechText(postCreateHandoff.description || 'Заполните обязательные подключения, затем проверьте агента на примере.')}</div>
        {postCreateHandoff.missing_bindings?.length ? (
          <div className="mt-2 flex flex-wrap gap-2">
            {postCreateHandoff.missing_bindings.slice(0, 4).map((binding) => (
              <span key={binding.key || binding.provider} className="rounded-full bg-white px-2.5 py-1 text-xs font-medium text-amber-900 ring-1 ring-amber-200">
                {connectorLabel(binding.provider)}{binding.missing_config?.length ? `: ${binding.missing_config.map((item) => userFacingAgentTechText(humanizeMeta(item))).join(', ')}` : ''}
              </span>
            ))}
          </div>
        ) : null}
      </div>
    ) : null}
    <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
      <div className="text-sm font-semibold text-slate-950">Подключения агента</div>
          <div className="mt-1 max-w-3xl text-sm leading-6 text-slate-600">
	        Настройте один следующий доступ. После сохранения LocalOS покажет тест без внешних действий.
      </div>
    </div>
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
      browserTargetUrls={browserTargetUrls}
      browserDailyCap={browserDailyCap}
      telegramBotMode={telegramBotMode}
      telegramDailyCap={telegramDailyCap}
      whatsappChannelMode={whatsappChannelMode}
      whatsappDailyCap={whatsappDailyCap}
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
      onBrowserTargetUrlsChange={onBrowserTargetUrlsChange}
      onBrowserDailyCapChange={onBrowserDailyCapChange}
      onTelegramBotModeChange={onTelegramBotModeChange}
      onTelegramDailyCapChange={onTelegramDailyCapChange}
      onWhatsappChannelModeChange={onWhatsappChannelModeChange}
      onWhatsappDailyCapChange={onWhatsappDailyCapChange}
      onMatonAuthRefChange={onMatonAuthRefChange}
      onMatonChannelChange={onMatonChannelChange}
      onMatonDailyCapChange={onMatonDailyCapChange}
      onProcessRowValuesChange={onProcessRowValuesChange}
      onProcessPreviewMessageChange={onProcessPreviewMessageChange}
        onSaveSheetIntegration={onSaveSheetIntegration}
        onSaveBrowserUseIntegration={onSaveBrowserUseIntegration}
        onSaveTelegramIntegration={onSaveTelegramIntegration}
        onSaveWhatsappIntegration={onSaveWhatsappIntegration}
        onSaveMatonIntegration={onSaveMatonIntegration}
        onChooseProviderRoute={onChooseProviderRoute}
      onAttachExistingIntegration={onAttachExistingIntegration}
      onSelectBinding={onSelectConnectionBinding}
      onSaveCustomProcess={onSaveCustomProcess}
      onRunCustomProcessPreview={onRunCustomProcessPreview}
      onPreviewRun={onPreviewRun}
    />
    <details className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
      <summary className="cursor-pointer text-sm font-semibold text-slate-950">Технические детали</summary>
      <div className="mt-3">
        <AgentConnectionPlanPanel
          connectionPlan={agentConnectionPlan}
          availableIntegrations={availableAgentIntegrations}
          actionLoading={actionLoading}
          onAttachExistingIntegration={onAttachExistingIntegration}
          onConfigureBinding={onSelectConnectionBinding}
          onChooseProviderRoute={onChooseProviderRoute}
        />
      </div>
    </details>
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
            {missingCount ? 'LocalOS понял, какие доступы нужны агенту. Завершите пункты ниже перед включением.' : 'Все обязательные доступы готовы для проверки и включения.'}
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
	                  {userFacingAgentTechText(humanizeMeta(item.capability || item.trigger || item.direction || item.provider || 'binding'))}
                </div>
              </div>
              <span className={cn('shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ring-1', connectionActionTone(item.action || ''))}>
	                {userFacingAgentTechText(item.primary_label || humanizeMeta(item.action || 'проверить'))}
              </span>
            </div>
	            <div className="mt-2 text-xs leading-5 text-slate-600">{userFacingAgentTechText(item.route_summary || item.explanation || bindingActionHint({ key: item.key || '', provider: item.provider || '', status: item.binding_status || '' }))}</div>
            {item.why_blocked && item.action !== 'ready' && item.action !== 'native_ready' ? (
              <div className="mt-2 rounded-lg bg-amber-50 px-2.5 py-2 text-xs leading-5 text-amber-900 ring-1 ring-amber-100">
	                Чего не хватает: {userFacingAgentTechText(item.why_blocked)}
              </div>
            ) : null}
            {item.policy_summary ? (
              <div className="mt-2 rounded-lg bg-slate-50 px-2.5 py-2 text-xs leading-5 text-slate-700 ring-1 ring-slate-100">
	                {userFacingAgentTechText(item.policy_summary)}
              </div>
            ) : null}
            {agentPolicyFacts(item).length ? (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {agentPolicyFacts(item).map((fact) => (
                  <span key={`${item.key}-${fact}`} className="rounded-full bg-slate-50 px-2 py-0.5 text-[11px] font-medium text-slate-600 ring-1 ring-slate-200">
                    {userFacingAgentTechText(humanizeMeta(fact))}
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
                  {userFacingAgentTechText(item.setup_cta?.label || `Настроить ${connectorLabel(item.provider)}`)}
                </Button>
              </div>
            ) : null}
            {item.provider_paths?.length ? (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {item.provider_paths.slice(0, 4).map((path) => (
                  <span key={`${path.provider}-${path.status}`} className="rounded-full bg-slate-50 px-2 py-0.5 text-[11px] text-slate-600 ring-1 ring-slate-200">
                    {userFacingAgentTechText(path.label || connectorLabel(path.provider))}: {userFacingAgentTechText(humanizeMeta(path.status || 'unknown'))}
                  </span>
                ))}
              </div>
            ) : null}
          </div>
          );
        })}
      </div>
      {compact && items.length > 3 ? (
        <div className="mt-2 text-[11px] leading-4 text-slate-500">Ещё {items.length - 3} подключений будут видны после создания черновика.</div>
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
    return userFacingAgentTechText(action.label);
  }
  return userFacingAgentTechText(route?.primary_cta || providerRouteLabel(route?.state || route?.status || ''));
};

const providerActionDescription = (route?: AgentProviderRoute | null) => {
  const action = route?.provider_action;
  if (action?.description) {
    return userFacingAgentTechText(action.description);
  }
  if (route?.connect_mode === 'openclaw_policy_boundary') {
    return 'Этот способ работает внутри правил безопасности, ручных подтверждений, журнала и лимитов LocalOS.';
  }
  if (route?.connect_mode === 'external_account_key') {
    return 'Выберите сохранённый ключ доступа или добавьте его в интеграциях бизнеса.';
  }
  if (route?.connect_mode === 'planned_oauth_connector') {
    return 'Подключение через OAuth запланировано, но пока не позволяет включить агента.';
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
  const label = `${userFacingAgentTechText(route.label || connectorLabel(route.provider))} · ${providerActionLabel(route)}`;
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
      <div className="text-sm font-semibold text-slate-950">Технический запуск</div>
      <div className="mt-1 max-w-3xl text-sm leading-6 text-slate-600">
        Технический слой для superadmin/debug: версии логики, журнал действий, списания, артефакты, подтверждения и экспорт поддержки.
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
          <RunColumn title="Шаги выполнения" icon={Clock3}>
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
        description="Запустите агента или откройте результат, чтобы увидеть технический журнал и экспорт поддержки."
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
  browserTargetUrls,
  browserDailyCap,
  telegramBotMode,
  telegramDailyCap,
  whatsappChannelMode,
  whatsappDailyCap,
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
  onBrowserTargetUrlsChange,
  onBrowserDailyCapChange,
  onTelegramBotModeChange,
  onTelegramDailyCapChange,
  onWhatsappChannelModeChange,
  onWhatsappDailyCapChange,
  onMatonAuthRefChange,
  onMatonChannelChange,
  onMatonDailyCapChange,
  onProcessRowValuesChange,
  onProcessPreviewMessageChange,
  onSaveSheetIntegration,
  onSaveBrowserUseIntegration,
  onSaveTelegramIntegration,
  onSaveWhatsappIntegration,
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
  browserTargetUrls: string;
  browserDailyCap: string;
  telegramBotMode: string;
  telegramDailyCap: string;
  whatsappChannelMode: string;
  whatsappDailyCap: string;
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
  onBrowserTargetUrlsChange: (value: string) => void;
  onBrowserDailyCapChange: (value: string) => void;
  onTelegramBotModeChange: (value: string) => void;
  onTelegramDailyCapChange: (value: string) => void;
  onWhatsappChannelModeChange: (value: string) => void;
  onWhatsappDailyCapChange: (value: string) => void;
  onMatonAuthRefChange: (value: string) => void;
  onMatonChannelChange: (value: string) => void;
  onMatonDailyCapChange: (value: string) => void;
  onProcessRowValuesChange: (value: string) => void;
  onProcessPreviewMessageChange: (value: string) => void;
  onSaveSheetIntegration: () => void;
  onSaveBrowserUseIntegration: () => void;
  onSaveTelegramIntegration: () => void;
  onSaveWhatsappIntegration: () => void;
  onSaveMatonIntegration: () => void;
  onChooseProviderRoute: (bindingKey: string, route: AgentProviderRoute) => void;
  onAttachExistingIntegration: (integration: AgentIntegration, bindingKey?: string) => void;
  onSelectBinding: (bindingKey: string) => void;
  onSaveCustomProcess: () => void;
  onRunCustomProcessPreview: () => void;
  onPreviewRun: () => void;
}) => {
  const sheetIntegration = integrations.find((item) => item.provider === 'google_sheets');
  const browserIntegration = integrations.find((item) => item.provider === 'browser_use');
  const telegramIntegration = integrations.find((item) => item.provider === 'telegram');
  const whatsappIntegration = integrations.find((item) => item.provider === 'whatsapp');
  const matonIntegration = integrations.find((item) => item.provider === 'maton');
  const selectedPlanItem = (connectionPlan?.items || []).find((item) => item.key === selectedBindingKey);
  const needsBrowserUse = bindingStatus.some((binding) => binding.provider === 'browser_use');
  const needsTelegram = bindingStatus.some((binding) => binding.provider === 'telegram');
  const needsWhatsapp = bindingStatus.some((binding) => binding.provider === 'whatsapp');
  const needsMaton = bindingStatus.some((binding) => binding.provider === 'maton') || (selectedPlanItem?.provider_routes || []).some((route) => route.provider === 'maton');
  const needsSheetsRead = bindingStatus.some((binding) => binding.provider === 'google_sheets' && binding.capability === 'google_sheets.read_rows');
  const needsSheetsAppend = bindingStatus.some((binding) => binding.provider === 'google_sheets' && binding.capability === 'sheets.append_row_request');
  const needsSheets = needsSheetsRead || needsSheetsAppend || bindingStatus.some((binding) => binding.provider === 'google_sheets');
  const isTelegramToSheetsProcess = needsTelegram && needsSheetsAppend;
  const sheetsTitle = needsSheetsRead && needsSheetsAppend ? 'Google Sheets: чтение и запись' : needsSheetsRead ? 'Google Sheets: источник данных' : 'Google Sheets: запись результата';
  const connectedBindings = bindingStatus.filter((binding) => binding.status === 'connected' || binding.status === 'ready').length;
  const missingBindings = bindingStatus.filter((binding) => binding.status !== 'connected' && binding.status !== 'ready').length;
  const canPreviewRun = !bindingStatus.length || missingBindings === 0;
  const connectionDecision = buildAgentConnectionDecision(connectionPlan, bindingStatus, canPreviewRun);
  const selectedBinding = bindingStatus.find((binding) => binding.key === selectedBindingKey)
    || bindingStatus.find((binding) => binding.status !== 'connected' && binding.status !== 'ready')
    || bindingStatus[0];
  const selectedProvider = selectedBinding?.provider || '';
  const hasRequiredBindings = bindingStatus.length > 0;
  const showBrowserUseForm = needsBrowserUse && (!hasRequiredBindings || selectedProvider === 'browser_use');
  const showTelegramForm = (needsTelegram || !hasRequiredBindings) && (!hasRequiredBindings || selectedProvider === 'telegram');
  const showWhatsappForm = needsWhatsapp && (!hasRequiredBindings || selectedProvider === 'whatsapp');
  const showMatonForm = needsMaton && (!hasRequiredBindings || selectedProvider === 'maton');
  const showSheetsForm = (needsSheets || !hasRequiredBindings) && (!hasRequiredBindings || selectedProvider === 'google_sheets');
  const showCustomProcessForm = isTelegramToSheetsProcess && !hasRequiredBindings;
  const otherBindings = bindingStatus.filter((binding) => binding.key !== selectedBinding?.key);
  return (
    <div className="space-y-3 rounded-2xl border border-slate-200 bg-white p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Источники и каналы</div>
          <div className="mt-1 text-xs leading-5 text-slate-500">Что запускает агента, откуда он берёт данные и куда готовит результат после подтверждения.</div>
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
	          {missingBindings ? `Нужно подключить ${missingBindings} ${missingBindings === 1 ? 'доступ' : 'доступа'}, прежде чем включать агента.` : 'Все обязательные подключения готовы. Можно проверять агента на примере и включать его.'}
        </div>
      ) : null}

      {!hasRequiredBindings ? (
      <div className={cn('rounded-lg px-3 py-3 ring-1', canPreviewRun ? 'bg-emerald-50 text-emerald-950 ring-emerald-200' : 'bg-slate-50 text-slate-600 ring-slate-200')}>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
	            <div className="text-sm font-semibold">Тест без отправки</div>
	            <div className="mt-1 text-xs leading-5">
	              {canPreviewRun
	                ? 'Проверим доступы, лимиты и ручные подтверждения. Ничего не отправим наружу.'
	                : 'Сначала заполните обязательные подключения. После этого станет доступна проверка на примере.'}
            </div>
          </div>
          <Button type="button" size="sm" onClick={onPreviewRun} disabled={actionLoading || !canPreviewRun}>
            {actionLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Play className="mr-2 h-4 w-4" />}
            Проверить на примере
          </Button>
        </div>
      </div>
      ) : null}

      {!hasRequiredBindings ? (
      <div className="grid gap-2">
        {needsBrowserUse ? <AgentIntegrationStatusItem integration={browserIntegration} provider="browser_use" fallbackTitle="Browser use" /> : null}
        {needsTelegram || !bindingStatus.length ? <AgentIntegrationStatusItem integration={telegramIntegration} provider="telegram" fallbackTitle="Telegram" /> : null}
        {needsWhatsapp ? <AgentIntegrationStatusItem integration={whatsappIntegration} provider="whatsapp" fallbackTitle="WhatsApp" /> : null}
        {needsMaton ? <AgentIntegrationStatusItem integration={matonIntegration} provider="maton" fallbackTitle="Maton.ai bridge" /> : null}
        {needsSheets || !bindingStatus.length ? <AgentIntegrationStatusItem integration={sheetIntegration} provider="google_sheets" fallbackTitle={sheetsTitle} /> : null}
      </div>
      ) : null}

      {showCustomProcessForm ? (
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

      {showBrowserUseForm ? (
      <div className={cn('space-y-2 rounded-lg border px-3 py-3', selectedProvider === 'browser_use' ? 'border-sky-200 bg-sky-50' : 'border-slate-200 bg-slate-50')}>
        <div className="flex items-center gap-2 text-sm font-medium text-slate-950">
          <Workflow className="h-4 w-4" />
          Browser use
        </div>
        <div className="rounded-lg bg-white px-3 py-2 text-xs leading-5 text-slate-600 ring-1 ring-slate-200">
          Чтение сайтов идёт через защищенный способ LocalOS/OpenClaw. Агент готовит результат, внешние действия требуют подтверждения.
        </div>
        <textarea
          className="min-h-20 w-full resize-none rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400"
          value={browserTargetUrls}
          onChange={(event) => onBrowserTargetUrlsChange(event.target.value)}
          placeholder="https://example.com"
        />
        <input
          className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400"
          value={browserDailyCap}
          onChange={(event) => onBrowserDailyCapChange(event.target.value)}
          placeholder="Лимит проверок страниц в день"
          inputMode="numeric"
        />
        <Button type="button" size="sm" variant="outline" onClick={onSaveBrowserUseIntegration} disabled={actionLoading || !browserTargetUrls.trim()}>
          {selectedProvider === 'browser_use' ? 'Сохранить Browser use для выбранного шага' : 'Сохранить Browser use'}
        </Button>
      </div>
      ) : null}

      {showTelegramForm ? (
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

      {showWhatsappForm ? (
      <div className={cn('space-y-2 rounded-lg border px-3 py-3', selectedProvider === 'whatsapp' ? 'border-sky-200 bg-sky-50' : 'border-slate-200 bg-slate-50')}>
        <div className="flex items-center gap-2 text-sm font-medium text-slate-950">
          <MessageSquareText className="h-4 w-4" />
          WhatsApp
        </div>
        <select
          className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400"
          value={whatsappChannelMode}
          onChange={(event) => onWhatsappChannelModeChange(event.target.value)}
        >
          <option value="whatsapp_business">WhatsApp Business</option>
          <option value="manual_whatsapp">Ручная отправка через WhatsApp</option>
        </select>
        <input
          className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400"
          value={whatsappDailyCap}
          onChange={(event) => onWhatsappDailyCapChange(event.target.value)}
          placeholder="Лимит сообщений в день"
          inputMode="numeric"
        />
        <Button type="button" size="sm" variant="outline" onClick={onSaveWhatsappIntegration} disabled={actionLoading}>
          {selectedProvider === 'whatsapp' ? 'Сохранить WhatsApp для выбранного шага' : 'Подключить WhatsApp'}
        </Button>
      </div>
      ) : null}

      {showMatonForm ? (
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

      {showSheetsForm ? (
      <div className={cn('space-y-3 rounded-lg border px-3 py-3', selectedProvider === 'google_sheets' ? 'border-sky-200 bg-sky-50' : 'border-slate-200 bg-slate-50')}>
        <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-start">
          <div>
            <div className="flex items-center gap-2 text-sm font-semibold text-slate-950">
              <Database className="h-4 w-4" />
              Подключите таблицу с поездками
            </div>
            <div className="mt-1 text-xs leading-5 text-slate-600">
              LocalOS прочитает строки и подготовит результат. Наружу ничего не отправится.
            </div>
          </div>
          <span className="rounded-full bg-white px-2.5 py-1 text-xs font-medium text-sky-800 ring-1 ring-sky-200">
            {needsSheetsRead && needsSheetsAppend ? 'чтение и запись' : needsSheetsRead ? 'чтение строк' : 'запись строк'}
          </span>
        </div>
        <label className="block text-xs font-medium text-slate-700">
          Ссылка на таблицу или ID
          <input
            className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-normal outline-none transition focus:border-slate-400"
            value={sheetSpreadsheetId}
            onChange={(event) => onSheetSpreadsheetIdChange(event.target.value)}
            placeholder="https://docs.google.com/spreadsheets/d/..."
          />
        </label>
        <div className="grid gap-2 sm:grid-cols-2">
          <label className="block text-xs font-medium text-slate-700">
            Лист
            <input
              className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-normal outline-none transition focus:border-slate-400"
              value={sheetName}
              onChange={(event) => onSheetNameChange(event.target.value)}
              placeholder="Sheet1"
            />
          </label>
          <label className="block text-xs font-medium text-slate-700">
            Лимит в день
            <input
              className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-normal outline-none transition focus:border-slate-400"
              value={sheetDailyCap}
              onChange={(event) => onSheetDailyCapChange(event.target.value)}
              placeholder="50"
              inputMode="numeric"
            />
          </label>
        </div>
        <label className="block text-xs font-medium text-slate-700">
          Google-доступ
          <select
            className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-normal outline-none transition focus:border-slate-400"
            value={sheetAuthRef}
            onChange={(event) => onSheetAuthRefChange(event.target.value)}
          >
            <option value="">Выбрать доступ автоматически</option>
            {authOptions.map((option) => (
              <option key={option.id} value={option.id}>
                {option.display_name || humanizeMeta(option.source)} · {option.id.slice(0, 8)}
              </option>
            ))}
          </select>
        </label>
        <Button type="button" size="sm" className="w-full sm:w-fit" onClick={onSaveSheetIntegration} disabled={actionLoading || !sheetSpreadsheetId.trim()}>
          {actionLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Database className="mr-2 h-4 w-4" />}
          {selectedProvider === 'google_sheets' ? 'Сохранить и перейти к тесту' : 'Сохранить таблицу'}
        </Button>
      </div>
      ) : null}

      {hasRequiredBindings ? (
      <div className={cn('rounded-lg px-3 py-3 ring-1', canPreviewRun ? 'bg-emerald-50 text-emerald-950 ring-emerald-200' : 'bg-slate-50 text-slate-600 ring-slate-200')}>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="text-sm font-semibold">Тест без отправки</div>
            <div className="mt-1 text-xs leading-5">
              {canPreviewRun
                ? 'Проверим доступы, лимиты и ручные подтверждения. Ничего не отправим наружу.'
                : 'Сначала заполните обязательные подключения. После этого станет доступна проверка на примере.'}
            </div>
          </div>
          <Button type="button" size="sm" onClick={onPreviewRun} disabled={actionLoading || !canPreviewRun}>
            {actionLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Play className="mr-2 h-4 w-4" />}
            Проверить на примере
          </Button>
        </div>
      </div>
      ) : null}

      {bindingStatus.length ? (
        <details className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-3">
          <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wide text-slate-500">Другие подключения</summary>
          <div className="mt-2 space-y-2">
          {(otherBindings.length ? otherBindings : bindingStatus).map((binding) => {
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
                    {bindingUserFacingRole(binding)}
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
                <div className="mt-1 text-slate-500">Перед внешним действием агент остановится и попросит подтверждение.</div>
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
        </details>
      ) : null}

      {selectedBinding ? (
        <details className="rounded-lg border border-sky-200 bg-sky-50 px-3 py-2 text-xs leading-5 text-sky-950">
          <summary className="cursor-pointer font-semibold">Технические детали</summary>
          <div className="mt-2 font-semibold">Сейчас настраивается: {connectorLabel(selectedBinding.provider)}</div>
            <div className="mt-1">
            {bindingUserFacingRole(selectedBinding)}
            {selectedBinding.missing_config?.length ? ` · заполните: ${selectedBinding.missing_config.join(', ')}` : ''}
          </div>
          {selectedPlanItem?.route_summary ? (
            <div className="mt-2 rounded-lg bg-white/80 px-2 py-1.5 text-sky-900 ring-1 ring-sky-100">
              {userFacingAgentTechText(selectedPlanItem.route_summary)}
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
              {userFacingAgentTechText(providerActionDescription(selectedPlanItem.provider_routes.find((route) => route.state === 'available') || selectedPlanItem.provider_routes[0]) || 'Выберите доступный способ подключения для этого шага.')}
            </div>
          ) : null}
        </details>
      ) : null}

      {availableIntegrations.length ? (
        <details className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-3">
          <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wide text-slate-500">Уже подключены в бизнесе</summary>
          <div className="mt-2 space-y-1">
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
        </details>
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
            <div><span className="font-medium text-slate-950">Задача:</span> {userFacingAgentTechText(String(review?.setup?.workflow_description || 'не задана'))}</div>
            <div><span className="font-medium text-slate-950">Извлечь:</span> {userFacingAgentTechText(String(review?.setup?.extraction_rules || 'не задано'))}</div>
            <div><span className="font-medium text-slate-950">Правила:</span> {userFacingAgentTechText(String(review?.setup?.processing_rules || 'не заданы'))}</div>
            <div><span className="font-medium text-slate-950">Результат:</span> {userFacingAgentTechText(String(review?.setup?.output_format || 'не задан'))}</div>
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
          {entry.summary ? <div className="mt-2 text-sm leading-6 text-slate-600">{userFacingAgentTechText(entry.summary)}</div> : null}
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
  const savedDestination = toRecordOrNull(result.saved_destination);
  const destinationStatus = String(savedDestination?.status || '');
  const contentPlanUrl = String(savedDestination?.content_plan_url || '');
  const entries = Object.entries(result).filter(([key, value]) => key !== 'saved_destination' && value !== '' && value !== null && value !== undefined);
  const priorityKeys = [
    'title',
    'draft_text',
    'post_text',
    'message',
    'text',
    'preparation_method',
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
      {destinationStatus === 'draft_saved' ? (
        <div className="rounded-lg bg-emerald-50 px-3 py-3 text-sm leading-6 text-emerald-950 shadow-[inset_0_0_0_1px_rgba(5,150,105,0.18)]">
          <div className="font-semibold">Черновик сохранён в контент-план</div>
          <div className="mt-1">Дата: {String(savedDestination?.scheduled_for || '')}</div>
          {contentPlanUrl ? <a className="mt-2 inline-flex min-h-10 items-center font-semibold text-emerald-800 underline" href={contentPlanUrl}>Открыть контент-план</a> : null}
        </div>
      ) : null}
      {destinationStatus === 'needs_future_date' ? (
        <div className="rounded-lg bg-amber-50 px-3 py-3 text-sm leading-6 text-amber-950 shadow-[inset_0_0_0_1px_rgba(217,119,6,0.2)]">
          <div className="font-semibold">Выберите новую дату</div>
          <div className="mt-1">{String(savedDestination?.message || 'Указанная дата контент-плана уже прошла.')}</div>
        </div>
      ) : null}
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
  const billingLedger = observability.billing_ledger || {};
  const unifiedBillingLedger = observability.unified_billing_ledger || {};
  const billingSummary = unifiedBillingLedger.summary || {};
  const billingActions = billingLedger.actions || [];
  const billingEntries = billingLedger.entries || [];
  const delivery = observability.delivery_status || {};
  const sourceChain = observability.source_result_chain || {};
  const sourceReadValue = sourceChain.provider_read_performed
    ? 'реально'
    : sourceChain.provider_read_attempted
      ? 'пример'
      : 'не было';
  const sourceReadHint = sourceChain.provider_read_performed
    ? `${sourceChain.rows_returned_count || 0} строк из таблицы`
    : sourceChain.provider_read_attempted
      ? 'нет подтверждённого чтения Google Sheets'
      : `${sourceChain.rows_returned_count || 0} строк`;
  const sourceProofValue = sourceChain.chain_verified
    ? 'доказано'
    : sourceChain.result_generated
      ? 'не доказано'
      : 'нет результата';
  const sourceProofHint = sourceChain.chain_verified
    ? 'источник → результат связан'
    : sourceChain.blocker_code === 'SOURCE_NOT_VERIFIED'
      ? 'результат есть, но источник не подтверждён'
      : sourceChain.result_generated
        ? 'проверьте источник'
        : 'результат не собран';
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
        <AgentObservabilityMetric icon={Activity} label="История запуска" value={run.status} hint={`${observability.step_history?.count || run.steps?.length || 0} шагов`} />
        <AgentObservabilityMetric
          icon={ReceiptText}
          label="Списания"
          value={formatBillingActualSummary(unifiedBillingLedger)}
          hint={`оценка ${formatBillingEstimateSummary({ summary: billingSummary })}`}
        />
        <AgentObservabilityMetric icon={Send} label="Доставка" value={humanizeMeta(delivery.state || 'not_applicable')} hint={`${delivery.attempts_success || 0}/${delivery.attempts_total || 0} попыток`} />
        <AgentObservabilityMetric icon={ShieldCheck} label="Подтверждения" value={String(observability.domain_requests?.pending || observability.approvals?.pending || 0)} hint={`${observability.domain_requests?.count || 0} запросов`} />
        <AgentObservabilityMetric icon={AlertTriangle} label="Ошибки" value={String(errors.length)} hint={errors.length ? 'нужна проверка' : 'нет ошибок'} />
      </div>

      <PreviewRunSummaryPanel
        summary={observability.preview_summary}
        runInput={runInput}
        activationGate={activationGate}
        actionLoading={actionLoading}
        onNextStepAction={onPreviewNextStepAction}
        onActivateVersion={onActivateVersion}
      />

      <div className="rounded-2xl bg-white p-4 shadow-[0_0_0_1px_rgba(15,23,42,0.08)]">
        <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Source To Result</div>
        <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <AgentObservabilityMetric icon={Database} label="Источник" value={sourceChain.source_step_present ? 'есть' : 'нет'} hint={sourceChain.provider_connected ? 'подключение готово' : 'подключение не подтверждено'} />
          <AgentObservabilityMetric icon={ArrowDownUp} label="Чтение" value={sourceReadValue} hint={sourceReadHint} />
          <AgentObservabilityMetric icon={FileText} label="Связка" value={sourceProofValue} hint={sourceProofHint} />
          <AgentObservabilityMetric icon={AlertTriangle} label="Blocker" value={String(sourceChain.blocker_code || 'none')} hint="где оборвалась цепочка" />
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-5">
        <RunColumn title="Журнал действий" icon={ReceiptText}>
          {ledgerItems.map((item) => (
            <TimelineItem
              key={item.action_id || item.trace_id || item.capability || 'action'}
              title={item.capability || item.action_id || 'Действие'}
              meta={item.action_id || 'действие агента'}
              status={item.status || (item.error ? 'failed' : 'linked')}
            />
          ))}
        </RunColumn>
		        <RunColumn title="Списания" icon={ReceiptText}>
	          {(unifiedBillingLedger.items || []).map((item) => (
	            <TimelineItem
	              key={item.key || item.label || 'unified-billing'}
	              title={item.label || humanizeMeta(item.key || 'billing')}
	              meta={`оценка ${formatBillingEstimateValue(item)} · факт ${formatBillingActualValue(item)}`}
	              status={item.status || 'billing'}
	            />
	          ))}
	          {billingActions.map((item) => (
	            <BillingActionItem key={item.action_id || item.capability || 'billing'} item={item} />
	          ))}
          {billingEntries.slice(0, 3).map((entry, index) => (
            <TimelineItem
              key={`${entry.action_id || 'entry'}-${entry.entry_type || index}-${entry.created_at || index}`}
              title={humanizeMeta(entry.entry_type || 'billing_entry')}
              meta={`${entry.action_id || entry.capability || 'действие'} · ${entry.cost ? `${entry.cost} кр.` : 'без списания'}`}
              status={entry.entry_type || 'billing'}
            />
          ))}
        </RunColumn>
        <RunColumn title="Ожидают подтверждения" icon={ShieldCheck}>
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
              title={item.error_text || item.step_key || item.action_id || 'Ошибка выполнения'}
              meta={item.source || item.status || 'выполнение агента'}
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
  currentActiveVersionId = '',
  actionLoading = false,
  onNextStepAction,
  onActivateVersion,
}: {
  summary?: Record<string, unknown>;
  runInput: Record<string, unknown>;
  activationGate?: AgentActivationGate;
  currentActiveVersionId?: string;
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
  const understoodTask = String(summary?.understood_task || objectValue(inputPreviewContext, 'understood_task') || objectValue(runInput, 'goal') || 'LocalOS проверяет агента на безопасном примере.');
  const manualControl = String(summary?.manual_control || objectValue(inputPreviewContext, 'manual_control') || 'Перед внешним действием нужен approval.');
  const safePreview = summary?.safe_preview !== false && runInput.external_side_effects_allowed === false;
  const nextStep = String(summary?.next_step || 'review_preview');
  const nextStepLabel = String(summary?.next_step_label || 'Проверить preview');
  const nextStepDescription = String(summary?.next_step_description || summary?.activation_hint || 'Проверьте результат preview и следующий шаг агента.');
  const activationVersionId = String(activationGate?.active_version_id || runInput.blueprint_version_id || '');
  const isCurrentVersionAlreadyActive = Boolean(activationVersionId && currentActiveVersionId && activationVersionId === currentActiveVersionId);
  const canActivateFromPreview = activationGate?.can_activate === true && Boolean(activationVersionId);
  const needsHumanDecision = pendingApprovals.length > 0 || waitingActions.length > 0 || nextStep === 'review_approvals';
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
      title: 'Проверка доступов',
      status: summary?.preflight_ready === false ? 'blocked' : 'completed',
      detail: summary?.preflight_ready === false ? 'нужны подключения' : 'подключения, лимиты и правила безопасности проверены',
    },
    {
      key: 'workflow',
      title: 'Проверенная логика',
      status: completedSteps.length ? 'completed' : 'pending',
      detail: completedSteps.length
        ? `${completedSteps.length} шагов выполнено`
        : compiledSteps.length
        ? `${compiledSteps.length} шагов в плане`
        : 'шаги появятся после запуска',
    },
    {
      key: 'approval',
      title: 'Ручное подтверждение',
      status: pendingApprovals.length || waitingActions.length ? 'waiting_approval' : 'completed',
      detail: pendingApprovals.length || waitingActions.length
        ? 'внешнее действие остановлено до решения человека'
        : 'ручной контроль проверен',
    },
    {
      key: 'activation',
      title: 'Готовность к включению',
      status: canActivateFromPreview ? 'completed' : 'pending',
      detail: canActivateFromPreview ? 'версию можно активировать' : nextStepDescription,
    },
  ];
  const actionLabel = canActivateFromPreview
    ? needsHumanDecision
      ? 'Проверить решение'
      : isCurrentVersionAlreadyActive
        ? 'Версия уже активна'
        : String(activationGate?.primary_action_label || 'Активировать версию')
    : previewNextStepActionLabel(nextStep, nextStepLabel);
  return (
    <div className="rounded-2xl border border-sky-200 bg-sky-50 px-4 py-4 text-sm leading-6 text-sky-950">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="font-semibold">Что показал тест без отправки</div>
          <div className="mt-1 max-w-3xl text-xs leading-5 text-sky-800">
            {userFacingAgentTechText(String(summary?.headline || 'Тест без отправки выполнен без внешних действий.'))}
          </div>
        </div>
        <span className="rounded-full bg-white px-2.5 py-1 text-xs font-medium text-sky-700 ring-1 ring-sky-200">
          {safePreview ? 'Тест без внешних действий' : 'проверьте внешние действия'}
        </span>
      </div>

      <div className="mt-3 grid gap-2 md:grid-cols-3">
        <PreviewRunFact label="Задача" value={userFacingAgentTechText(understoodTask)} />
        <PreviewRunFact label="Данные" value={userFacingAgentTechText(dataSources.length ? dataSources.join(', ') : providerBindings.length ? providerBindings.map((item) => formatPayloadValue(item)).join(' · ') : 'доступы проверены')} />
        <PreviewRunFact label="Ручной контроль" value={userFacingAgentTechText(manualControl)} />
      </div>

      <details className="mt-3 rounded-xl border border-sky-100 bg-white/70 px-3 py-2">
        <summary className="cursor-pointer text-xs font-semibold text-sky-800">
          Подробности теста
        </summary>
        <div className="mt-3 space-y-3">
          <CompiledPreviewSimulationPanel steps={simulationSteps} safePreview={safePreview} externalActionsPerformed={Boolean(summary?.external_actions_performed)} />

          <OpenClawPreviewActionPlanPanel
            actions={openClawActionPlan}
            policyEnvelope={policyEnvelope}
            approvalGate={approvalGate}
            safePreview={safePreview}
          />

          <div className="grid gap-2 lg:grid-cols-3">
            <PreviewSummaryList
              title="Шаги"
              items={completedSteps.length ? completedSteps.slice(0, 5).map((item) => userFacingAgentTechText(humanizeMeta(item))) : ['Шаги будут видны после теста без отправки.']}
            />
            <PreviewSummaryList
              title="Результаты"
              items={artifacts.length ? artifacts.slice(0, 4).map((item) => {
                const record = toRecordOrNull(item) || {};
                return userFacingAgentTechText(`${String(record.title || humanizeMeta(String(record.type || 'artifact')))}: ${String(record.summary || 'сохранён для проверки')}`);
              }) : ['Результат появится после подготовки.']}
            />
            <PreviewSummaryList
              title="Ручной контроль"
              items={
                pendingApprovals.length
                  ? pendingApprovals.slice(0, 4).map((item) => {
                    const record = toRecordOrNull(item) || {};
                    return userFacingAgentTechText(`${String(record.title || record.approval_type || 'Решение')}: ${humanizeMeta(String(record.status || 'pending'))}`);
                  })
                  : waitingActions.length
                    ? waitingActions.slice(0, 4).map((item) => {
                      const record = toRecordOrNull(item) || {};
                      return userFacingAgentTechText(`${humanizeMeta(String(record.kind || 'external_action'))}: ${String(record.why || record.state || 'ждёт approval')}`);
                    })
                    : ['Внешние действия останутся за ручным подтверждением.']
              }
            />
          </div>
        </div>
      </details>

      <div className="mt-3 rounded-xl bg-white px-3 py-2 text-xs leading-5 text-sky-800 ring-1 ring-sky-100">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <div className="font-semibold text-sky-900">
              Следующий шаг: {needsHumanDecision ? 'проверить решение' : isCurrentVersionAlreadyActive ? 'версия уже активна' : userFacingAgentTechText(nextStepLabel)}
            </div>
            <div className="mt-1">
              {needsHumanDecision
                ? 'Агент подготовил результат и остановился. Решите, можно ли использовать его дальше.'
                : isCurrentVersionAlreadyActive
                  ? 'Эта версия уже активна. Следующее действие - принять или отклонить подготовленный результат, если он ждёт решения.'
                  : userFacingAgentTechText(nextStepDescription)}
            </div>
            {canActivateFromPreview && !needsHumanDecision && !isCurrentVersionAlreadyActive ? (
              <div className="mt-1 font-medium text-emerald-700">Готовность подтверждена: тест без отправки, доступы и логика прошли проверку.</div>
            ) : null}
          </div>
          {needsHumanDecision && onNextStepAction ? (
            <Button type="button" size="sm" className="shrink-0" onClick={() => onNextStepAction('review_approvals')} disabled={actionLoading}>
              {actionLabel}
            </Button>
          ) : canActivateFromPreview && onActivateVersion && !isCurrentVersionAlreadyActive ? (
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
  const boundary = userFacingAgentTechText(String(policyEnvelope.execution_boundary || 'openclaw_action_orchestrator'));
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
          <div className="font-semibold text-sky-950">План внешних действий в тесте</div>
          <div className="mt-1 text-sky-700">
            LocalOS показывает будущие действия, но оставляет исполнение за правилами безопасности, лимитами, списаниями и журналом.
          </div>
        </div>
        <span className={cn('rounded-full px-2 py-0.5 font-medium ring-1', safePreview && !externalSideEffectsAllowed ? 'bg-emerald-50 text-emerald-700 ring-emerald-200' : 'bg-amber-50 text-amber-700 ring-amber-200')}>
          {safePreview && !externalSideEffectsAllowed ? 'внешние действия выключены' : 'нужна проверка внешних действий'}
        </span>
      </div>

      <div className="mt-3 grid gap-2 md:grid-cols-3">
        <PreviewRunFact label="Граница выполнения" value={boundary} />
        <PreviewRunFact label="Подтверждение и списания" value={`${approvalOwner} подтверждения · ${billingOwner} списания`} />
        <PreviewRunFact label="Ожидание" value={`${pendingApprovalsCount} подтверждений · ${waitingCount} действий ждут`} />
      </div>

      {visibleActions.length ? (
        <div className="mt-3 grid gap-2 md:grid-cols-2">
          {visibleActions.map((action, index) => {
            const title = userFacingAgentTechText(String(action.title || action.provider_action_ref || action.capability || `Действие ${index + 1}`));
            const meta = [
              action.provider_action_ref ? userFacingAgentTechText(String(action.provider_action_ref)) : '',
              action.capability ? userFacingAgentTechText(String(action.capability)) : '',
              action.provider_policy ? userFacingAgentTechText(String(action.provider_policy)) : 'правила LocalOS',
            ].filter(Boolean).join(' · ');
            const requiresApproval = action.requires_approval === true || Boolean(action.approval_class);
            return (
              <div key={`${title}-${index}`} className="rounded-lg bg-sky-50 px-2.5 py-2 ring-1 ring-sky-100">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="line-clamp-1 font-semibold text-sky-950">{title}</div>
                    <div className="mt-1 line-clamp-2 text-sky-700">{meta || 'Действие останется внутри правил LocalOS'}</div>
                  </div>
                  <span className={cn('shrink-0 rounded-full px-2 py-0.5 font-medium ring-1', requiresApproval ? 'bg-amber-50 text-amber-700 ring-amber-200' : 'bg-emerald-50 text-emerald-700 ring-emerald-200')}>
                    {requiresApproval ? 'нужно решение' : 'безопасно'}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="mt-3 rounded-lg bg-sky-50 px-2.5 py-2 text-sky-700 ring-1 ring-sky-100">
          План внешних действий появится после подготовки логики или повторного теста без отправки.
        </div>
      )}
    </div>
  );
};

const previewNextStepActionLabel = (nextStep: string, fallback: string) => {
  const labels: Record<string, string> = {
    connect_required_integrations: 'Открыть подключения',
    fix_preview_error: 'Открыть логику',
    review_approvals: 'Открыть решения',
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
        <div className="font-semibold text-sky-950">Симуляция проверки</div>
        <div className="mt-1 text-sky-700">
          Тест показывает, как агент пройдёт входные данные, проверку доступов, шаги, подтверждения и готовность к включению.
        </div>
      </div>
      <span className={cn('rounded-full px-2 py-0.5 font-medium ring-1', safePreview && !externalActionsPerformed ? 'bg-emerald-50 text-emerald-700 ring-emerald-200' : 'bg-amber-50 text-amber-700 ring-amber-200')}>
        {safePreview && !externalActionsPerformed ? 'внешних действий не было' : 'проверьте внешние действия'}
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
  const cost = Number(item.total_cost || 0);
  const entryCount = Number(item.entry_count || 0);
  return (
    <div className="rounded-xl bg-white px-3 py-3 shadow-sm ring-1 ring-slate-200">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="truncate text-sm font-medium text-slate-900">{item.capability || item.action_id || 'billing action'}</div>
          <div className="mt-1 text-xs text-slate-500">{item.action_id || 'no action id'}</div>
        </div>
        <StatusBadge status={item.status || 'settled'} />
      </div>
      <div className="mt-2 grid grid-cols-2 gap-2 text-xs">
        <div className="rounded-lg bg-slate-50 px-2 py-2">
          <div className="font-semibold text-slate-900">{cost ? `${cost} кр.` : 'без списания'}</div>
          <div className="text-slate-500">стоимость</div>
        </div>
        <div className="rounded-lg bg-slate-50 px-2 py-2">
          <div className="font-semibold text-slate-900">{entryCount}</div>
          <div className="text-slate-500">событий</div>
        </div>
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
