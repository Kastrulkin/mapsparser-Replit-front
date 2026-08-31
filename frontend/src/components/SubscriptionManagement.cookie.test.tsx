import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import { LanguageProvider } from '@/i18n/LanguageContext';
import { SubscriptionManagement } from './SubscriptionManagement';


describe('SubscriptionManagement cookie session', () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.history.replaceState({}, '', '/dashboard/billing/return?yookassa_return=1');
    vi.restoreAllMocks();
    vi.stubEnv('VITE_BROWSER_COOKIE_AUTH_ENABLED', 'true');
  });

  it('checks the billing result after provider return without a JavaScript bearer token', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ success: true, subscription: { status: 'active', tier: 'professional' } }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    vi.stubGlobal('fetch', fetchMock);

    render(
      <MemoryRouter initialEntries={['/dashboard/billing/return?yookassa_return=1']}>
        <LanguageProvider>
          <SubscriptionManagement businessId="business-1" business={{}} />
        </LanguageProvider>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/api/billing/status?business_id=business-1'),
        expect.any(Object),
      );
    });
  });
});
