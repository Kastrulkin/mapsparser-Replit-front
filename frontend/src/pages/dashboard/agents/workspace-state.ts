import { Bot, Zap } from 'lucide-react';

import type {
  AgentBlueprint,
  AgentBlueprintDetails,
  AgentRun,
  AgentServerTodaySummary,
  LegacyMigrationPlan,
} from './types';
import { buildEmployeeDescription, buildEmployeeWorkspaceState, buildTodaySummary } from './model';

export const queuedButNotDispatchedForRun = (run?: AgentRun | null) => {
  const artifact = (run?.artifacts || []).find((item) => {
    const payload = item.payload_json || {};
    return payload.dispatch_state === 'queued_not_dispatched' || (
      payload.status === 'queued_for_dispatch' && payload.external_dispatch_performed === false
    );
  });
  if (artifact?.payload_json) return artifact.payload_json;
  const step = (run?.steps || []).find((item) => {
    const output = item.output_json?.orchestrator?.result || item.output_json || {};
    return output.dispatch_state === 'queued_not_dispatched' || (
      output.status === 'queued_for_dispatch' && output.external_dispatch_performed === false
    );
  });
  return step?.output_json?.orchestrator?.result || step?.output_json || null;
};

export const systemAgentsForConfig = (config: Record<string, { enabled?: boolean }>) => [
  {
    key: 'booking_agent',
    title: 'Агент записи',
    description: 'Помогает с правилами записи, вопросами клиенту и сценарием общения.',
    icon: Bot,
    enabled: Boolean(config.booking_agent?.enabled),
  },
  {
    key: 'marketing_agent',
    title: 'Маркетинговый агент',
    description: 'Готовит идеи, тексты и маркетинговые черновики в стиле бизнеса.',
    icon: Zap,
    enabled: Boolean(config.marketing_agent?.enabled),
  },
];

export const migrationStatsForPlan = (plan: LegacyMigrationPlan | null) => {
  const legacyAgents = plan?.legacy_agents || [];
  const businessFields = plan?.business_settings?.fields || {};
  return {
    totalLegacyAgents: legacyAgents.length,
    linkedVoices: legacyAgents.filter((item) => item.action === 'use_as_persona').length,
    needsBlueprint: legacyAgents.filter((item) => item.action === 'create_blueprint_candidate').length,
    archiveCandidates: legacyAgents.filter((item) => item.action === 'archive_candidate').length,
    deprecatedFieldsPresent: Object.values(businessFields).filter((item) => item.present).length,
    legacyWorkflowPresent: legacyAgents.filter((item) => item.legacy_workflow?.present).length,
  };
};

export const todaySummaryForServer = (
  serverSummary: AgentServerTodaySummary | null,
  blueprints: AgentBlueprint[],
  detailsById: Record<string, AgentBlueprintDetails>,
) => {
  if (!serverSummary) return buildTodaySummary(blueprints, detailsById);
  const completedRuns = Number(serverSummary.completed_runs || 0);
  const preparedArtifacts = Number(serverSummary.prepared_results || 0);
  const pendingApprovals = Number(serverSummary.pending_approvals || 0);
  const failedRuns = Number(serverSummary.failed_runs || 0);
  return {
    completedRuns,
    preparedArtifacts,
    pendingApprovals,
    failedRuns,
    latestEvent: '',
    empty: completedRuns + preparedArtifacts + pendingApprovals + failedRuns === 0,
  };
};

export const employeeListDetails = (
  detailsById: Record<string, AgentBlueprintDetails>,
  selectedBlueprint: AgentBlueprint | null,
  blueprintDetails: AgentBlueprintDetails | null,
  activeRun: AgentRun | null,
) => {
  if (!selectedBlueprint?.id || !blueprintDetails) return detailsById;
  if (!activeRun?.id) return { ...detailsById, [selectedBlueprint.id]: blueprintDetails };
  const runs = blueprintDetails.runs || [];
  const runBelongsToSelectedBlueprint = activeRun.blueprint_id === selectedBlueprint.id
    || activeRun.id === runs[0]?.id
    || activeRun.id === selectedBlueprint.last_run_id;
  const selectedDetails = runBelongsToSelectedBlueprint
    ? { ...blueprintDetails, runs: [activeRun, ...runs.filter((run) => run.id !== activeRun.id)] }
    : blueprintDetails;
  return { ...detailsById, [selectedBlueprint.id]: selectedDetails };
};

export const filterAgentBlueprints = (
  blueprints: AgentBlueprint[],
  detailsById: Record<string, AgentBlueprintDetails>,
  search: string,
  filter: string,
) => {
  const query = search.trim().toLowerCase();
  return blueprints.filter((blueprint) => {
    const details = detailsById[blueprint.id];
    const state = buildEmployeeWorkspaceState(blueprint, details);
    const matchesSearch = !query || [blueprint.name, buildEmployeeDescription(blueprint, details)]
      .some((value) => String(value || '').toLowerCase().includes(query));
    if (!matchesSearch) return false;
    if (filter === 'working') return state === 'working';
    if (filter === 'completed') return state === 'completed';
    if (filter === 'attention') {
      return ['needs_mode', 'needs_connection', 'ready_for_test', 'waiting_for_review', 'blocked_result', 'needs_attention', 'error'].includes(state);
    }
    return true;
  });
};
