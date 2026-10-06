import { describe, expect, it } from 'vitest';
import { buildCandidateSearchGroups, resolveSearchTask, taskLabel } from './partnershipSearchGroups';

describe('candidate search groups', () => {
  it('does not crash when a disabled-business response lacks search conditions', () => {
    expect(taskLabel({ id: 'missing', config: undefined })).toBe('Поиск компаний');
  });

  it('finds a linked search under another accessible business', async () => {
    const requested: string[] = [];
    const task = await resolveSearchTask('search-1', 'hair', ['hair', 'riderra'], async (businessId) => {
      requested.push(businessId);
      return businessId === 'hair' ? { enabled: false, items: [] }
        : { id: 'search-1', business_id: 'riderra', config: { agency_country: 'Индия', sold_destination: 'Пхукет' }, state: { lead_ids: [] } };
    });
    expect(requested).toEqual(['hair', 'riderra']);
    expect(task?.business_id).toBe('riderra');
    if (!task) throw new Error('search_not_resolved');
    expect(taskLabel(task)).toContain('Индия');
  });

  it('does not treat a disabled response or an inaccessible task as a search', async () => {
    const task = await resolveSearchTask('search-1', 'hair', ['hair', 'other'], async (businessId) => {
      if (businessId === 'hair') return { enabled: false, items: [] };
      throw new Error('access_denied');
    });
    expect(task).toBeNull();
  });

  it('does not associate a returned task with a different business', async () => {
    const task = await resolveSearchTask('search-1', 'hair', ['hair'], async () => ({
      id: 'search-1', business_id: 'riderra', config: { agency_country: 'Индия' },
    }));
    expect(task).toBeNull();
  });
  it('keeps chat search candidates together by the saved task, including older imported leads', () => {
    const grouped = buildCandidateSearchGroups([
      { id: 'india-1', search_payload_json: { continuation_id: 'task-1' } },
      { id: 'india-2', search_payload_json: { continuation_id: 'task-1' } },
      { id: 'manual-1', search_payload_json: { job_id: 'job-1', query: 'tours', location: 'Delhi' } },
      { id: 'unknown-1' },
    ], [{ id: 'task-1', created_at: '2026-10-04T08:00:00Z',
      config: { agency_country: 'Индия', sold_destination: 'Пхукет' },
      state: { lead_ids: ['india-1', 'india-2'] } }]);
    expect(grouped.groups.map(({ id, count }) => ({ id, count }))).toEqual([
      { id: 'task:task-1', count: 2 }, { id: 'job:job-1', count: 1 }, { id: 'other', count: 1 },
    ]);
    expect(grouped.labels.get('task:task-1')).toContain('Индия → Пхукет');
    expect(grouped.leadGroup.get('india-2')).toBe('task:task-1');
  });

  it('uses saved task membership if a later import changes the lead search payload', () => {
    const grouped = buildCandidateSearchGroups([
      { id: 'lead-1', search_payload_json: { job_id: 'later-job' } },
    ], [{ id: 'original-task', config: { audience: 'Турагентства' }, state: { lead_ids: ['lead-1'] } }]);
    expect(grouped.groups[0].id).toBe('task:original-task');
  });
});
