import { describe, expect, it } from 'vitest';
import { getLeadPipelineStatus } from './usePartnershipWorkspaceDerivedData';
describe('partnership contact evidence', () => {
 it.each(['approved_for_send', 'queued_for_send'])('does not present %s as contact', status => {
  expect(getLeadPipelineStatus({ id: 'lead', pipeline_status: status })).toBe('in_progress');
 });
 it('keeps approved drafts in progress until delivery is recorded', () => {
  expect(getLeadPipelineStatus({ id: 'lead', partnership_stage: 'approved_for_send' })).toBe('in_progress');
  expect(getLeadPipelineStatus({ id: 'lead', partnership_stage: 'sent' })).toBe('contacted');
  expect(getLeadPipelineStatus({ id: 'lead', partnership_stage: 'delivered' })).toBe('contacted');
 });
});
