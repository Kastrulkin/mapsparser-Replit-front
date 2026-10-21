/** Scoped navigation hints; the API still determines access. */
export const partnershipMiniLaunch = (search: string, businessId: string): { groupId: string; draftId: string; tab: 'drafts' | 'send' | 'leads' | 'overview' } => {
  const params = new URLSearchParams(search);
  const sameBusiness = Boolean(businessId && params.get('scope_type') === 'business' && params.get('scope_id') === businessId);
  const uuid = /^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i;
  const group = params.get('filter_search_task_id') || '';
  const draft = params.get('filter_draft_id') || '';
  const section = sameBusiness ? params.get('filter_section') : null;
  return {
    groupId: sameBusiness && uuid.test(group) ? group : '',
    draftId: sameBusiness && uuid.test(draft) ? draft : '',
    tab: section === 'drafts' ? 'drafts' : section === 'send' ? 'send' : section === 'leads' ? 'leads' : 'overview',
  };
};
