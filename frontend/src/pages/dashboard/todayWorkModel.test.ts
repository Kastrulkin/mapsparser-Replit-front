import { describe, expect, it } from 'vitest';
import { statusKey, workSections, workRoute, type TodayItem } from './todayWorkModel';
const now = Date.parse('2026-10-11T10:00:00Z');
const item = (id: string, status: string, extra: Partial<TodayItem> = {}): TodayItem => ({ id, title: id, status, screen: 'content', ...extra });
describe('Today work integrity', () => {
  it('puts real overdue decisions ahead of failures and preferred drafts', () => {
    const view = workSections({ preference: { scope_type: 'business', scope_id: 'b', primary_flow: 'content', revision: 1, suggestions_enabled: false }, work_sections: { needs_decision: [item('draft', 'edited', {flow:'content'}), item('failed', 'failed'), item('late', 'ready', {due_at:'2026-10-10T12:00:00Z'})] } }, now);
    expect(view.decisions.map(i=>i.id)).toEqual(['late','failed','draft']);
    expect(view.primary?.id).toBe('late');
  });
  it('never selects background jobs as a primary action', () => {
    const view = workSections({ active_work: [item('queue','queued'),item('run','running')] }, now);
    expect(view.primary).toBeUndefined();
    expect(view.continuing).toHaveLength(2);
  });
  it('retains a blocked decision even without a destination', () => {
    expect(workSections({active_work:[{id:'x',title:'Blocked',status:'blocked'}]}, now).primary?.id).toBe('x');
  });
  it('preserves queued state in a legacy response and never invents overdue on completed work', () => {
    const view=workSections({active_work:[item('q','in_progress',{work_status:'queued'})]},now);
    expect(statusKey(view.continuing[0],now)).toBe('queued');
    expect(statusKey(item('c','completed',{due_at:'2026-10-10T00:00:00Z'}),now)).toBe('completed');
    expect(statusKey(item('u','future_state'),now)).toBe('unknown');
  });
  it('removes aggregates and undated results and sorts real dated results', () => {
    const view=workSections({work_sections:{results:[item('aggregate','completed',{kind:'aggregate',occurred_at:'2026-10-11'}),item('undated','completed'),item('setup','completed',{kind:'growth_achievement',occurred_at:'2026-10-11'}),item('old','completed',{occurred_at:'2026-10-01'}),item('new','published',{occurred_at:'2026-10-11'})]}},now);
    expect(view.results.map(i=>i.id)).toEqual(['new','old']);
  });
  it('preserves the selected entity URL and resolves owner tasks to the approval panel', () => {
    const target='/dashboard/content?plan_id=p&item_id=i&business_id=b';
    expect(workRoute(item('i','edited',{action:{url:target}}))).toBe(target);
    expect(workRoute(item('j','ready',{kind:'owner_action',entity_id:'owner1'}))).toBe('/dashboard/operator?journey_action=owner1');
    expect(workRoute({id:'u',title:'Unknown'})).toBeUndefined();
  });
  it('deduplicates an item appearing in both sections without losing its decision', () => {
    const view=workSections({work_sections:{needs_decision:[item('same','ready')],continue_work:[item('same','ready')]}},now);
    expect(view.decisions).toHaveLength(1);
    expect(view.continuing).toHaveLength(0);
  });
});
