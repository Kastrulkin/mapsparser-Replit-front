import type { PartnershipLead } from './partnershipTypes';

export type SearchTaskGroup = {
  id: string;
  business_id?: string;
  display_name?: string;
  report?: { found?: number; imported?: number; eligible?: number };
  created_at?: string;
  config?: { audience?: string; agency_country?: string; sold_destination?: string };
  state?: { lead_ids?: string[]; workstream_ids?: string[]; verified_contact_workstream_ids?: string[]; qualifications?: Record<string, { status?: string; criteria?: Record<string, { status?: string; source_url?: string; quote?: string }> }>; history?: Array<{ action?: string; at?: string }> };
};

export type CandidateSearchGroup = { id: string; label: string; count: number };

const shortDate = (value?: string) => {
  if (!value) return '';
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? '' : parsed.toLocaleString('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
};

export const taskLabel = (task: SearchTaskGroup) => {
  if (task.display_name?.trim()) return task.display_name.trim();
  const country = String(task.config?.agency_country || '').trim();
  const destination = String(task.config?.sold_destination || '').trim();
  const audience = String(task.config?.audience || '').trim();
  const purpose = country && destination ? `${country} → ${destination}` : audience || 'Поиск компаний';
  const launch = [...(task.state?.history || [])].reverse().find((entry) => entry.action === 'start');
  return [purpose, shortDate(launch?.at || task.created_at)].filter(Boolean).join(' · ');
};

export function isSearchTaskGroup(value: unknown): value is SearchTaskGroup {
  return Boolean(value && typeof value === 'object' && 'id' in value && typeof value.id === 'string'
    && 'config' in value && value.config && typeof value.config === 'object');
}

export async function resolveSearchTask(
  taskId: string,
  selectedBusinessId: string,
  businessIds: string[],
  load: (businessId: string) => Promise<unknown>,
): Promise<(SearchTaskGroup & { business_id: string }) | null> {
  const candidates = [selectedBusinessId, ...businessIds.filter((id) => id !== selectedBusinessId)];
  for (const businessId of candidates) {
    try {
      const value = await load(businessId);
      if (isSearchTaskGroup(value) && value.id === taskId && value.business_id === businessId) {
        return { ...value, business_id: businessId };
      }
    } catch {
      // A search may belong to another accessible business. Try that business.
    }
  }
  return null;
}

export function buildCandidateSearchGroups(leads: PartnershipLead[], tasks: SearchTaskGroup[]) {
  const leadToTask = new Map<string, SearchTaskGroup>();
  for (const task of tasks) {
    for (const leadId of task.state?.lead_ids || []) {
      if (!leadToTask.has(leadId)) leadToTask.set(leadId, task);
    }
  }
  const labels = new Map<string, string>();
  const leadGroup = new Map<string, string>();
  const counts = new Map<string, number>();
  for (const lead of leads) {
    const task = leadToTask.get(lead.id);
    const payload = lead.search_payload_json || {};
    const continuationId = String(payload.continuation_id || '').trim();
    const jobId = String(payload.job_id || '').trim();
    const id = task ? `task:${task.id}` : continuationId ? `task:${continuationId}` : jobId ? `job:${jobId}` : 'other';
    const label = task ? taskLabel(task)
      : continuationId ? 'Поиск из чата'
      : jobId ? [String(payload.location || payload.query || 'Поиск на картах'), shortDate(lead.created_at)].filter(Boolean).join(' · ')
      : 'Другие кандидаты';
    leadGroup.set(lead.id, id);
    if (!labels.has(id)) labels.set(id, label);
    counts.set(id, (counts.get(id) || 0) + 1);
  }
  const groups: CandidateSearchGroup[] = [...counts].map(([id, count]) => ({ id, count, label: labels.get(id) || 'Поиск компаний' }));
  return { groups, leadGroup, labels };
}
