import { beforeEach, describe, expect, it, vi } from 'vitest';

import { fetchDashboardBusinessData } from '@/components/dashboard/dashboardData';
import { newAuth } from './auth_new';
import { uploadAgentSource } from '@/pages/dashboard/agents/api';


describe('primary cookie-auth consumers', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(newAuth, 'getToken').mockReturnValue(null);
  });

  it('loads map business data without requiring a JavaScript token', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ business: { id: 'business-1', name: 'Maps business' } }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    vi.stubGlobal('fetch', fetchMock);

    const result = await fetchDashboardBusinessData('business-1');

    expect(result?.business?.id).toBe('business-1');
    expect(fetchMock).toHaveBeenCalledOnce();
  });

  it('uploads an automation source without requiring a JavaScript token', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ success: true, source: { id: 'source-1' } }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    vi.stubGlobal('fetch', fetchMock);

    const result = await uploadAgentSource('blueprint-1', new File(['facts'], 'facts.txt'), 'Facts');

    expect(result.source.id).toBe('source-1');
    expect(fetchMock).toHaveBeenCalledOnce();
  });
});
