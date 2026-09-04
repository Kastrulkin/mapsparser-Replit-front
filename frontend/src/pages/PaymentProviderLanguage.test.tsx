import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import { SubscriptionManagement } from '@/components/SubscriptionManagement';
import { LanguageProvider } from '@/i18n/LanguageContext';
import About from './About';


const jsonResponse = (payload: unknown, status = 200) => new Response(JSON.stringify(payload), {
  status,
  headers: { 'Content-Type': 'application/json' },
});


describe('payment provider follows the selected interface language', () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
    window.localStorage.setItem('language', 'en');
    window.localStorage.setItem('auth_token', 'test-token');
    window.localStorage.setItem('selectedBusinessId', 'business-1');
    window.history.replaceState({}, '', '/');
    vi.restoreAllMocks();
    vi.stubEnv('VITE_BROWSER_COOKIE_AUTH_ENABLED', 'false');
    vi.stubGlobal('alert', vi.fn());
  });

  it('uses Stripe in subscription management even when geo detection says Russia', async () => {
    const checkoutPayloads: Array<Record<string, unknown>> = [];
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.startsWith('/api/billing/status')) {
        return jsonResponse({ success: true, subscription: null });
      }
      if (url === '/api/geo/payment-provider') {
        return jsonResponse({ success: true, country: 'RU', payment_provider: 'russia' });
      }
      if (url === '/api/billing/checkout/session/start') {
        checkoutPayloads.push(JSON.parse(String(init?.body || '{}')));
        return jsonResponse({ error: 'test stop' }, 400);
      }
      return jsonResponse({});
    });
    vi.stubGlobal('fetch', fetchMock);

    render(
      <MemoryRouter>
        <LanguageProvider>
          <SubscriptionManagement
            businessId="business-1"
            business={{ subscription_tier: 'trial', subscription_status: 'inactive' }}
          />
        </LanguageProvider>
      </MemoryRouter>,
    );

    const selectButtons = await screen.findAllByRole('button', { name: 'Select' });
    fireEvent.click(selectButtons[0]);

    await waitFor(() => expect(checkoutPayloads).toHaveLength(1));
    expect(checkoutPayloads[0]?.provider).toBe('stripe');
  });

  it('uses Stripe on the pricing page even when geo detection says Russia', async () => {
    const checkoutPayloads: Array<Record<string, unknown>> = [];
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === '/api/geo/payment-provider') {
        return jsonResponse({ success: true, country: 'RU', payment_provider: 'russia' });
      }
      if (url === '/api/billing/checkout/session/start') {
        checkoutPayloads.push(JSON.parse(String(init?.body || '{}')));
        return jsonResponse({ error: 'test stop' }, 400);
      }
      return jsonResponse({});
    });
    vi.stubGlobal('fetch', fetchMock);

    render(
      <MemoryRouter>
        <LanguageProvider>
          <About />
        </LanguageProvider>
      </MemoryRouter>,
    );

    fireEvent.click(await screen.findByRole('button', { name: 'Start' }));

    await waitFor(() => expect(checkoutPayloads).toHaveLength(1));
    expect(checkoutPayloads[0]?.provider).toBe('stripe');
  });
});
