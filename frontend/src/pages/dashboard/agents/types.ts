export type DashboardContext = {
  currentBusinessId: string | null;
  currentBusiness?: ({ id?: string; name?: string } & Record<string, unknown>) | null;
};

export type AgentBlueprint = {
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

export type AgentVoicePersona = {
  id: string;
  name?: string;
  role?: string;
  source?: string;
  description?: string;
  identity?: string;
  speech_style?: string;
  is_active?: boolean;
};

export type ProductAgentView = {
  id?: string;
  kind?: string;
  source?: string;
  persona_agent_id?: string | null;
  persona?: AgentVoicePersona | null;
  voice?: AgentVoicePersona | null;
};

export type AgentApproval = {
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

export type AgentArtifact = {
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

export type AgentRunStep = {
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

export type AgentRunBillingAction = {
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

export type AgentRunObservability = {
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

export type AgentRun = {
  id: string;
  status: string;
  blueprint_id: string;
  blueprint_version_id?: string;
  input_json?: Record<string, unknown>;
  steps?: AgentRunStep[];
  artifacts?: AgentArtifact[];
  approvals?: AgentApproval[];
  error_text?: string | null;
  queued_at?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  attempt_count?: number;
  max_attempts?: number;
  next_attempt_at?: string | null;
  billing_reservation_id?: string | null;
  run_billing?: Record<string, unknown>;
  observability?: AgentRunObservability;
  business_result?: Record<string, unknown>;
  result_state?: 'missing' | 'prepared' | 'saved' | 'blocked';
  current_approval?: AgentApproval | null;
  evaluation?: {
    rating?: 'useful' | 'not_useful';
    feedback?: string;
    created_at?: string;
  } | null;
  progress?: {
    state?: string;
    total_steps?: number;
    completed_steps?: number;
    current_step_index?: number;
    current_step_key?: string;
    current_step_status?: string;
    percent?: number;
  };
};

export type AgentRunInputField = {
  type?: 'string' | 'number' | 'integer' | 'boolean' | 'array';
  format?: 'date' | 'time' | 'date-time' | 'textarea';
  title?: string;
  description?: string;
  default?: unknown;
  example?: unknown;
  enum?: unknown[];
};

export type AgentRunInputSchema = {
  type?: 'object';
  properties?: Record<string, AgentRunInputField>;
  required?: string[];
};

export type AgentServerTodaySummary = {
  completed_runs?: number;
  prepared_results?: number;
  pending_approvals?: number;
  failed_runs?: number;
  timezone?: string;
  day?: string;
};

export type AgentMetricsSummary = {
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

export type AgentBillingBreakdownItem = {
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

export type AgentUnifiedBillingLedger = {
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

export type AgentBlueprintDetails = {
  blueprint?: AgentBlueprint;
  versions: Array<Record<string, unknown>>;
  runs: AgentRun[];
  approval_queue?: AgentApproval[];
  active_version?: Record<string, unknown> | null;
  active_version_id?: string;
  active_version_number?: number;
  candidate_version?: Record<string, unknown> | null;
  candidate_version_id?: string;
  run_input_schema?: AgentRunInputSchema;
  candidate_run_input_schema?: AgentRunInputSchema;
  active_run_input_schema?: AgentRunInputSchema;
  execution_mode?: 'one_off' | 'manual' | 'scheduled';
  execution_mode_source?: 'explicit' | 'legacy_trigger';
  execution_mode_confirmation_required?: boolean;
  lifecycle_state?: 'draft' | 'needs_setup' | 'ready' | 'active' | 'completed' | 'error';
  last_business_result?: Record<string, unknown> | null;
  next_run_at?: string | null;
  learning_events?: AgentLearningEvent[];
  version_events?: AgentVersionEvent[];
  lifecycle_events?: Array<Record<string, unknown>>;
  feedback_history?: Array<Record<string, unknown>>;
  legacy_migration?: Record<string, unknown>;
  metrics?: AgentMetricsSummary;
  activation_gate?: AgentActivationGate;
  execution_contract?: AgentExecutionContract;
};

export type AgentExecutionContractStep = {
  key?: string;
  position?: number;
  title?: string;
  step_type?: string;
  capability?: string;
  artifact_type?: string;
  requires_approval?: boolean;
  approval_type?: string;
};

export type AgentExecutionVersionContract = {
  role?: 'candidate' | 'active';
  version_id?: string;
  version_number?: number;
  goal?: string;
  trigger?: string;
  schedule?: { time?: string | null; timezone?: string | null; next_run_at?: string | null };
  inputs_schema?: AgentRunInputSchema;
  steps?: AgentExecutionContractStep[];
  sources?: unknown[];
  connections?: Record<string, unknown>;
  expected_result?: Record<string, unknown>;
  approval_boundaries?: Array<{ step_key?: string; title?: string; approval_type?: string }>;
  validation?: { tested?: boolean; status?: string; last_test?: Record<string, unknown> | null };
  is_active?: boolean;
};

export type AgentExecutionContract = {
  schema?: string;
  original_request?: string;
  execution_mode?: AgentExecutionMode;
  candidate?: AgentExecutionVersionContract | null;
  active?: AgentExecutionVersionContract | null;
  has_unpublished_changes?: boolean;
  description_complete?: boolean;
};

export type AgentVersionDiff = {
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

export type AgentLearningLoop = {
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

export type AgentLearningEvent = {
  run_id?: string;
  trigger_type?: string;
  feedback?: string;
  previous_version_id?: string;
  candidate_version_id?: string;
  candidate_version_number?: number;
  activation_state?: string;
  created_at?: string;
};

export type AgentVersionEvent = {
  action?: string;
  reason?: string;
  previous_active_version_id?: string;
  active_version_id?: string;
  active_version_number?: number;
  created_at?: string;
};

export type AgentSource = {
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

export type AgentSourceCatalogItem = {
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

export type AgentIntegration = {
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

export type AgentExternalAuthOption = {
  id: string;
  source: string;
  provider?: string;
  display_name?: string;
  updated_at?: string;
};

export type AgentIntegrationCatalogItem = {
  provider: string;
  title: string;
  description?: string;
  required_config?: string[];
  default_limits?: Record<string, unknown>;
  status?: string;
  providers?: Array<{ provider?: string; label?: string; status?: string }>;
};

export type AgentIntegrationBindingStatus = {
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

export type AgentIntegrationPreflight = {
  status?: string;
  ready?: boolean;
  missing_count?: number;
  next_action?: string;
  items?: AgentIntegrationBindingStatus[];
  missing?: AgentIntegrationBindingStatus[];
};

export type AgentProviderAction = {
  kind?: string;
  available?: boolean;
  ui_target?: string;
  label?: string;
  description?: string;
  role?: string;
};

export type AgentProviderRoute = {
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

export type AgentConnectionPlanItem = {
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

export type AgentConnectionPlan = {
  schema?: string;
  status?: string;
  missing_count?: number;
  items?: AgentConnectionPlanItem[];
};

export type AgentConnectionDecision = {
  tone: string;
  title: string;
  description: string;
  action: string;
  cta: string;
  bindingKey?: string;
};

export type AgentActivationGate = {
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

export type AgentActivationPathStep = {
  key: string;
  label: string;
  detail: string;
  status: string;
};

export type AgentPostCreateHandoff = {
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

export type AgentReviewSection = {
  title?: string;
  artifact_type?: string;
  status?: string;
  summary?: string;
  payload?: Record<string, unknown>;
};

export type AgentJournalEntry = {
  kind?: string;
  title?: string;
  status?: string;
  summary?: string;
  details?: Array<{ label?: string; value?: string }>;
  payload?: Record<string, unknown>;
};

export type AgentReview = {
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

export type AgentBuilderScenario = {
  category: string;
  title: string;
  description: string;
  prompt: string;
  dataSources: string;
  extraction: string;
  processing: string;
  output: string;
  manualControl: string;
  icon: LucideIcon;
};

export type PersonaAgent = {
  id: string;
  name?: string;
  type?: string;
  description?: string;
  task?: string;
  identity?: string;
  is_active?: boolean;
};

export type LegacyMigrationPlan = {
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

export type AgentWorkspaceMode = 'overview' | 'scenario' | 'settings' | 'run' | 'results' | 'connections' | 'voice' | 'advanced';

export type AgentTodaySummary = {
  completedRuns: number;
  preparedArtifacts: number;
  pendingApprovals: number;
  failedRuns: number;
  latestEvent: string;
  empty: boolean;
};

export type AgentAttentionItem = {
  key: string;
  tone: 'amber' | 'rose' | 'sky';
  problem: string;
  reason: string;
  actionLabel: string;
  action: () => void;
};

export type AgentBusinessStatus = {
  status: string;
  label: string;
  tone: 'ready' | 'warning' | 'error' | 'draft';
  primaryLabel: string;
  lastResult: string;
  nextRun: string;
};

export type EmployeeStatus = {
  label: 'Работает' | 'Выполнено' | 'Нужны данные' | 'Ждёт решения' | 'Нужно проверить' | 'Ошибка' | 'Черновик';
  tone: 'emerald' | 'amber' | 'rose' | 'slate';
  summary: string;
};

export type AgentExecutionMode = 'one_off' | 'manual' | 'scheduled';

export type EmployeeNextActionKind = 'approve' | 'connect' | 'confirm_mode' | 'run_test' | 'run_work' | 'run_similar' | 'enable' | 'configure_schedule' | 'open_result' | 'view_history';

export type EmployeeWorkspaceState = 'draft' | 'needs_mode' | 'needs_connection' | 'ready_for_test' | 'running_test' | 'waiting_for_review' | 'blocked_result' | 'working' | 'completed' | 'needs_attention' | 'error';

export type AgentRegistryFilter = 'all' | 'working' | 'attention' | 'completed';

export type AgentRunAnimation = {
  kind: 'test' | 'work';
  blueprintId: string;
  startedAt: number;
  progress: number;
  stepIndex: number;
  steps: string[];
  status: 'running' | 'finishing' | 'error';
  runId?: string;
  serverCompletedSteps?: number;
  serverCurrentStepIndex?: number;
  queueState?: string;
  recoveredFromReload?: boolean;
  error?: string;
};

export type EmployeeNextAction = {
  kind: EmployeeNextActionKind;
  label: string;
  description: string;
  targetMode: AgentWorkspaceMode;
  versionId?: string;
  secondaryAction?: 'clone_agent';
};

export type EmployeeTestResult = {
  summary: string;
  output: string;
  state: 'result' | 'blocker' | 'missing';
  resultPayload?: Record<string, unknown> | null;
  previewItems: Array<{ label: string; value: string }>;
  hasResult: boolean;
};

export type EmployeeResponsibility = {
  key: string;
  label: string;
  done?: boolean;
};

export type AgentScenarioStep = {
  key: string;
  title: string;
  description: string;
};

export type AgentConfidenceFact = {
  key: string;
  label: string;
  ready: boolean;
};

export type FeedbackVersionNotice = {
  version_id?: string;
  previous_version_id?: string;
  version_number?: number;
  feedback?: string;
  next_run_note?: string;
  activation_state?: string;
  trigger_label?: string;
  diff?: AgentVersionDiff;
};

export type AgentBuilderMessage = {
  role: 'user' | 'assistant';
  content: string;
};

export type AgentBuilderQuestion = {
  key?: string;
  question: string;
  reason?: string;
  provider?: string;
  role?: string;
};

export type AgentBuilderConnectorPreview = {
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

export type AgentBuilderFeasibility = {
  status?: string;
  ready?: boolean;
  next_action?: string;
  missing_connections?: AgentBuilderConnectorPreview[];
  connection_choices?: AgentBuilderConnectorPreview[];
  ready_bindings?: AgentBuilderConnectorPreview[];
  forbidden?: Array<{ term?: string; reason?: string }>;
  unsupported?: Array<{ capability?: string; reason?: string }>;
};

export type AgentBuilderSetupStep = {
  key?: string;
  label?: string;
  status?: string;
  description?: string;
  questions?: AgentBuilderQuestion[];
  missing_connections?: AgentBuilderConnectorPreview[];
  connection_choices?: AgentBuilderConnectorPreview[];
};

export type AgentBuilderSetupFlow = {
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

export type AgentBuilderPlannerLoop = {
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

export type AgentCompilerPolicyItem = {
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

export type AgentCompilerWorkflowDraft = {
  trigger?: string;
  steps?: AgentCompilerPolicyItem[];
  outputs?: AgentCompilerPolicyItem[];
  output?: AgentCompilerPolicyItem[];
  limits?: Record<string, unknown>;
};

export type AgentCompilerPolicyReview = {
  schema?: string;
  source?: string;
  status?: string;
  workflow_draft?: AgentCompilerWorkflowDraft;
  approval_points?: AgentCompilerPolicyItem[];
  unsupported_requests?: AgentCompilerPolicyItem[];
};

export type AgentConnectorIntelligence = {
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

export type AgentConnectionSummary = {
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

export type AgentConnectionReadinessService = {
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

export type AgentConnectionReadiness = {
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

export type AgentConnectionResolverItem = {
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

export type AgentConnectionResolver = {
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

export type AgentServiceIntelligenceItem = {
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

export type AgentServiceIntelligence = {
  schema?: string;
  status?: string;
  headline?: string;
  can_create_draft?: boolean;
  can_activate?: boolean;
  state_counts?: Record<string, number>;
  items?: AgentServiceIntelligenceItem[];
};

export type AgentBuilderPreview = {
  understood_task?: string;
  trigger?: string;
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

export type AgentBuilderSession = {
  id: string;
  business_id: string;
  status: string;
  category: string;
  messages?: AgentBuilderMessage[];
  preview?: AgentBuilderPreview;
  missing_questions?: AgentBuilderQuestion[];
  blueprint_id?: string | null;
};
import type { LucideIcon } from 'lucide-react';
