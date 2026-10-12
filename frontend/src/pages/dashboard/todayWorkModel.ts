import type { JourneyAction } from '@/lib/leadJourney';
export type Mission = { id?: string; title: string; reason: string; expected_outcome: string; cta_label: string; screen?: string; cta_url?: string; plan_id?: string; item_id?: string; target_scope?: { kind?: string; id?: string } };
export type TodayItem = { id: string; status?: string; work_status?: string; kind?: string; entity_type?: string; entity_id?: string; timezone?: string; requires_decision?: boolean; title: string; description?: string; stage?: string; source?: string; occurred_at?: string; progress?: number | null; screen?: string; business_id?: string; business_name?: string; flow?: TodayPreference['primary_flow']; urgency?: 'urgent' | 'normal'; due_at?: string | null; preview?: string | null; action?: { label?: string; label_code?: string; url?: string }; freshness?: { as_of?: string; status?: string }; reason_code?: string; message_code?: string; params?: Record<string, unknown> };
export type TodayPreference = {
  scope_type: 'business' | 'network';
  scope_id: string;
  primary_flow: 'overview' | 'content' | 'influencers' | 'partnerships' | 'maps' | 'upsells' | 'automation';
  suggestions_enabled: boolean;
  revision: number;
  updated_at?: string | null;
  previous_flow?: string | null;
  can_undo?: boolean;
  available_flows?: Array<'overview' | 'content' | 'influencers' | 'partnerships' | 'maps' | 'upsells' | 'automation'>;
};
export type PriorityProposal = { id: string; flow: TodayPreference['primary_flow']; active_days: number; confirmed_actions: number; reason_code: 'activity_shift' };
type ProblemLocation = { business_id: string; business_name: string; problem?: string; data_health_status?: string; focus_action?: Mission | null };
export type TodayOverview = {
  as_of?: string; timezone?: string;
  focus_action?: Mission | null;
  journey_actions?: JourneyAction[];
  data_health?: { status?: string; source?: string; source_label?: string; source_updated_at?: string | null; updated_at?: string | null; last_updated_at?: string | null; stale?: boolean; is_stale?: boolean; missing?: string[] } | null;
  active_work?: TodayItem[];
  changes_24h?: TodayItem[];
  community_pulse?: TodayItem[];
  completed_results?: TodayItem[];
  network_summary?: { locations_count?: number; problem_locations_count?: number; healthy_locations_count?: number; finance?: { missing?: number; stale?: number; due?: number; fresh?: number } } | null;
  problem_locations?: ProblemLocation[];
  data_rhythm?: { status?: string; coverage?: number; completed_periods_8w?: number; next_due_at?: string | null } | null;
  analytics_modules?: Array<{ key?: string; label?: string; status?: string; next_unlock?: string | null }>;
  preference?: TodayPreference;
  priority_proposal?: PriorityProposal | null;
  work_sections?: { needs_decision?: TodayItem[]; continue_work?: TodayItem[]; results?: TodayItem[] };
  work_source_states?: Partial<Record<'content' | 'influencers' | 'automation', { status?: 'live' | 'error' | 'unavailable'; as_of?: string }>>;
};


export const completedStatuses = new Set(['completed', 'published', 'succeeded']);
const decisionStatuses = new Set(['draft', 'ready', 'approved', 'approved_for_send', 'failed', 'waiting_approval', 'awaiting_approval', 'needs_review', 'replied', 'negotiating', 'disputed', 'overdue', 'draft_generated', 'edited', 'blocked', 'provider_reconciliation_required', 'provider_failed', 'provider_unavailable', 'approval_invalid']);
const backgroundStatuses = new Set(['pending', 'queued', 'running', 'processing', 'in_progress', 'waiting_provider', 'provider_request_queued', 'provider_executing', 'scheduled', 'waiting']);
const errors = new Set(['failed', 'blocked', 'disputed', 'provider_reconciliation_required', 'provider_failed', 'provider_unavailable', 'approval_invalid']);
export const validDate = (value?: string | null) => Boolean(value && Number.isFinite(Date.parse(value)));
export const needsHuman = (item: TodayItem) => item.requires_decision === true || decisionStatuses.has(item.status || '') || item.kind === 'owner_action';
export const isOverdue = (item: TodayItem, observedAt: number) => !completedStatuses.has(item.status || '') && validDate(item.due_at) && Date.parse(item.due_at || '') < observedAt;

export const workRoute = (item: TodayItem): string | undefined => {
  if (item.action?.url?.startsWith('/dashboard/')) return item.action.url;
  const routes: Record<string, string> = { cards: '/dashboard/card', reviews: '/dashboard/card?tab=reviews&review_filter=needs_reply', services: '/dashboard/card?tab=services', content: '/dashboard/content', finance: '/dashboard/finance', partnerships: '/dashboard/partnerships', influencers: '/dashboard/influencers', agents: '/dashboard/agents', tasks: '/dashboard/operator', operator: '/dashboard/operator', progress: '/dashboard/progress' };
  if (item.kind === 'owner_action' && item.entity_id) return `/dashboard/operator?journey_action=${encodeURIComponent(item.entity_id)}`;
  return routes[item.screen || ''];
};

export const orderWork = (items: TodayItem[], primaryFlow: TodayPreference['primary_flow'] | undefined, observedAt: number) => [...items].sort((a, b) => {
  const rank = (item: TodayItem) => needsHuman(item) && isOverdue(item, observedAt) ? 0 : needsHuman(item) && errors.has(item.status || '') ? 1 : needsHuman(item) ? 2 : 3;
  return rank(a) - rank(b) || Number(b.urgency === 'urgent') - Number(a.urgency === 'urgent') || Number(b.flow === primaryFlow) - Number(a.flow === primaryFlow) || (validDate(a.due_at) ? Date.parse(a.due_at || '') : Infinity) - (validDate(b.due_at) ? Date.parse(b.due_at || '') : Infinity) || a.id.localeCompare(b.id);
});

const workIdentity = (item: TodayItem) => JSON.stringify([item.business_id, item.entity_type || item.kind, item.entity_id || item.id]);
export const workSections = (overview: TodayOverview, observedAt: number) => {
  const sections = overview.work_sections;
  const current = sections
    ? [...(sections.needs_decision || []).map(item => ({ ...item, requires_decision: true })), ...(sections.continue_work || [])]
    : overview.active_work || [];
  const unique = [...new Map([...current].reverse().map(item => [workIdentity(item), { ...item, status: item.work_status || item.status }])).values()].filter(item => !completedStatuses.has(item.status || ''));
  const ordered = orderWork(unique, overview.preference?.primary_flow, observedAt);
  const decisions = ordered.filter(needsHuman);
  const continuing = ordered.filter(item => !needsHuman(item));
  const results = [...new Map((sections?.results || overview.completed_results || []).map(item => [workIdentity(item), item])).values()]
    .filter(item => validDate(item.occurred_at) && !['growth_achievement', 'aggregate', 'summary', 'work_observation', 'observation'].includes(item.kind || '') && item.entity_type !== 'work_observation' && Boolean(workRoute(item)) && (completedStatuses.has(item.status || '') || item.kind === 'confirmed_action'))
    .sort((a, b) => Date.parse(b.occurred_at || '') - Date.parse(a.occurred_at || ''));
  const actionable = decisions[0] || continuing.find(item => workRoute(item) && !backgroundStatuses.has(item.status || ''));
  return { decisions, continuing, results, primary: actionable };
};

export const statusKey = (item: TodayItem, observedAt: number): 'unknown' | 'queued' | 'running' | 'scheduled' | 'decision' | 'blocked' | 'failed' | 'completed' | 'published' | 'waiting' | 'overdue' => {
  const status = item.status || '';
  if (isOverdue(item, observedAt)) return 'overdue';
  if (status === 'published') return 'published';
  if (completedStatuses.has(status)) return 'completed';
  if (status === 'failed' || status === 'provider_failed') return 'failed';
  if (errors.has(status)) return 'blocked';
  if ((status === 'approved' && needsHuman(item)) || decisionStatuses.has(status) || item.kind === 'owner_action') return 'decision';
  if (['pending', 'queued', 'provider_request_queued'].includes(status)) return 'queued';
  if (['running', 'processing', 'provider_executing'].includes(status)) return 'running';
  if (status === 'scheduled') return 'scheduled';
  if (['waiting', 'waiting_provider'].includes(status)) return 'waiting';
  return 'unknown';
};
