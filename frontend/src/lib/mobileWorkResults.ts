export type ResultLead = {
  id: string; name?: string; address?: string; city?: string; source?: string; source_kind?: string;
  last_contact_at?: string; status?: string; created_at?: string; pilot_cohort?: string; pipeline_status?: string; partnership_stage?: string;
  search_payload_json?: Record<string, unknown>;
};
export type ResultLetter = {
  id: string; lead_id: string; lead_name?: string; channel?: string; status?: string; generated_text?: string;
  edited_text?: string; approved_text?: string; updated_at?: string; recipient_value?: string | null;
  recipient_source_url?: string | null; learning_note_json?: { recipient?: string | null; manual_delivery_only?: boolean };
};
const resultTime = (value?: string) => { const time = Date.parse(value || ''); return Number.isFinite(time) ? time : 0; };
const resultDay = (value?: string) => resultTime(value) ? new Date(resultTime(value)).toISOString().slice(0, 10) : '';
export const resultDate = (value?: string) => {
  const date = new Date(value || '');
  return Number.isNaN(date.getTime()) ? 'Дата не указана' : date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' });
};
export const wasContacted = (lead: ResultLead) => Boolean(lead.last_contact_at) || ['sent', 'contacted', 'responded', 'replied', 'delivered'].includes(lead.status || '') || ['contacted', 'waiting_reply', 'sent', 'delivered', 'replied', 'responded', 'converted', 'partner', 'reply_received'].includes(lead.pipeline_status || '') || ['sent', 'responded', 'reply_received', 'converted'].includes(lead.partnership_stage || '');
export function partnerResultGroups(leads: ResultLead[], letters: ResultLetter[]) {
  const groups = new Map<string, { id: string; title: string; createdAt: string; leads: ResultLead[]; letters: ResultLetter[] }>();
  for (const lead of leads) {
    const payload = lead.search_payload_json || {};
    const task = String(payload.continuation_id || payload.job_id || '');
    const date = resultDay(lead.created_at);
    const origin = String(payload.filename || payload.file_name || lead.source_kind || lead.source || 'saved');
    const id = task ? `search:${task}` : `saved:${lead.pilot_cohort || ''}:${origin}:${date}`;
    const title = task ? String(payload.audience || payload.query || payload.location || 'Результат поиска') : /import|file|csv/i.test(origin) ? 'Подборка из таблицы' : 'Сохранённая подборка';
    if (!groups.has(id)) groups.set(id, { id, title, createdAt: lead.created_at || '', leads: [], letters: [] });
    groups.get(id)?.leads.push(lead);
  }
  for (const group of groups.values()) {
    const ids = new Set(group.leads.map(lead => lead.id));
    group.letters = letters.filter(letter => ids.has(letter.lead_id));
  }
  const known = new Set(leads.map(lead => lead.id));
  const orphaned = letters.filter(letter => !known.has(letter.lead_id));
  if (orphaned.length) groups.set('letters-only', { id: 'letters-only', title: 'Сохранённые письма без подборки', createdAt: '', leads: [...new Map(orphaned.map(letter => [letter.lead_id, { id: letter.lead_id, name: letter.lead_name || 'Партнёр' }])).values()], letters: orphaned });
  return [...groups.values()].sort((a, b) => resultTime(b.createdAt) - resultTime(a.createdAt) || a.id.localeCompare(b.id));
}
export type ResultPlan = { id: string; title?: string; created_at?: string; plan_status?: string; items_count?: number; ready_count?: number; news_count?: number; period_start?: string; period_end?: string; period_days?: number };
export function currentResultPlan(plans: ResultPlan[], today = new Date().toISOString().slice(0, 10)) {
  const completed = plans.filter(plan => (plan.items_count || 0) > 0 && !['archived', 'failed', 'running', 'generating', 'pending'].includes(plan.plan_status || ''));
  const ready = completed.filter(plan => (plan.ready_count || 0) + (plan.news_count || 0) > 0);
  return [...(ready.length ? ready : completed)].sort((a, b) => {
    const active = (plan: ResultPlan) => ['active', 'approved', 'published'].includes(plan.plan_status || '') ? 1 : 0;
    const coversToday = (plan: ResultPlan) => plan.period_start && plan.period_end && resultDay(plan.period_start) <= today && resultDay(plan.period_end) >= today ? 1 : 0;
    return coversToday(b) - coversToday(a) || active(b) - active(a) || resultTime(b.created_at) - resultTime(a.created_at);
  })[0];
}
