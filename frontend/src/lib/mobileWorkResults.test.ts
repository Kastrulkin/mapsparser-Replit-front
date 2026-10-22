import { describe, it, expect } from 'vitest';
import { partnerResultGroups, currentResultPlan, wasContacted } from './mobileWorkResults';
describe('saved results selection', () => {
  it('keeps separate imports and only their letters', () => {
    const groups = partnerResultGroups([{id:'new',source:'file_import',created_at:'2026-10-16T12:00:00Z'}, {id:'old',source:'file_import',created_at:'2026-06-04T12:00:00Z'}], [{id:'d1',lead_id:'old'}, {id:'d2',lead_id:'new'}]);
    expect(groups.map(group => group.leads[0].id)).toEqual(['new','old']);
    expect(groups[0].letters.map(letter => letter.id)).toEqual(['d2']);
  });
  it('never merges different search launches on the same day', () => {
    expect(partnerResultGroups([{id:'a',search_payload_json:{job_id:'one'}},{id:'b',search_payload_json:{job_id:'two'}}],[])).toHaveLength(2);
  });
  it('separates named files imported on the same day', () => {
    expect(partnerResultGroups([{id:'a',created_at:'2026-10-16',search_payload_json:{filename:'a.csv'}},{id:'b',created_at:'2026-10-16',search_payload_json:{filename:'b.csv'}}],[])).toHaveLength(2);
  });
  it('does not confuse an approved draft with a sent letter', () => {
    expect(wasContacted({id:'a',status:'approved',partnership_stage:'proposal_approved'})).toBe(false);
    expect(wasContacted({id:'a',pipeline_status:'contacted'})).toBe(true);
    expect(wasContacted({id:'a',last_contact_at:'2026-09-23'})).toBe(true);
  });
  it('does not let a newer unfinished plan replace a working result', () => {
    expect(currentResultPlan([{id:'old',plan_status:'active',items_count:9,ready_count:9,created_at:'2026-10-15'}, {id:'new',plan_status:'generating',items_count:0,created_at:'2026-10-22'}])?.id).toBe('old');
  });
  it('prefers ready posts to a newer topic-only draft', () => {
    expect(currentResultPlan([{id:'ready',items_count:9,ready_count:9,created_at:'2026-10-15'}, {id:'draft',items_count:9,ready_count:0,created_at:'2026-10-22'}])?.id).toBe('ready');
  });
  it('keeps archived plans in history without choosing them by default', () => {
    expect(currentResultPlan([{id:'archived',plan_status:'archived',items_count:9,ready_count:9}])).toBeUndefined();
  });
  it('selects the latest usable plan, independent of response order', () => {
    expect(currentResultPlan([{id:'one',items_count:3,ready_count:3,created_at:'2026-10-01'}, {id:'two',items_count:3,ready_count:3,created_at:'2026-10-16'}])?.id).toBe('two');
  });
});
it('compares Flask RFC dates by time instead of weekday text',()=>{
 const groups=partnerResultGroups([{id:'august',source:'file_import',created_at:'Tue, 25 Aug 2026 10:00:00 GMT'}, {id:'october',source:'file_import',created_at:'Fri, 16 Oct 2026 13:45:02 GMT'}],[]);
 expect(groups[0].leads[0].id).toBe('october');
 expect(currentResultPlan([{id:'august',items_count:3,ready_count:3,created_at:'Tue, 25 Aug 2026 10:00:00 GMT'}, {id:'october',items_count:3,ready_count:3,created_at:'Fri, 16 Oct 2026 13:45:02 GMT'}])?.id).toBe('october');
});
