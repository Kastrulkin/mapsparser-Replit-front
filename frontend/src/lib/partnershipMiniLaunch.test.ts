import { expect, it } from 'vitest';
import { partnershipMiniLaunch } from './partnershipMiniLaunch';
it('accepts only the selected business and known section',()=>{
 expect(partnershipMiniLaunch('?scope_type=business&scope_id=qa&filter_section=drafts','qa').tab).toBe('drafts');
 expect(partnershipMiniLaunch('?scope_type=business&scope_id=other&filter_section=drafts','qa')).toEqual({groupId:'',draftId:'',tab:'overview'});
 expect(partnershipMiniLaunch('?scope_type=business&scope_id=qa&filter_section=admin&filter_draft_id=invalid','qa')).toEqual({groupId:'',draftId:'',tab:'overview'});
});
