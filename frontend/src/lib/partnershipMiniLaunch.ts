/** Scoped, non-authorizing navigation hints from a Telegram Web App button. */
export const partnershipMiniLaunch = (search: string, businessId: string) => {
  const params = new URLSearchParams(search);
  const sameBusiness = Boolean(businessId && params.get('scope_type') === 'business' && params.get('scope_id') === businessId);
  const uuid = /^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i;
  const group = params.get('filter_search_task_id') || '';
  const draft = params.get('filter_draft_id') || '';
  const section = params.get('filter_section');
  return {
    groupId: sameBusiness && uuid.test(group) ? group : '',
    draftId: sameBusiness && uuid.test(draft) ? draft : '',
    tab: sameBusiness && ['drafts', 'send', 'leads', 'overview'].includes(section || '')
      ? section as 'drafts' | 'send' | 'leads' | 'overview' : 'overview' as const,
  };
};
