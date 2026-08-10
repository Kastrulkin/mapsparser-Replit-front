import '@testing-library/jest-dom/vitest';
import { render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { CompaniesMobileModule } from './CompaniesMobileModule';

describe('CompaniesMobileModule dates', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('never exposes Invalid Date for malformed provider timestamps', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(new Response(JSON.stringify({
      company: { id: 'company-1', name: 'Компания', roles: [] },
      freshness: { status: 'stale', updated_at: 'not-a-date' },
      locations: [],
      external_profiles: [{ id: 'profile-1', provider: 'yandex', last_collected_at: 'not-a-date' }],
      contacts: [],
    }), { status: 200, headers: { 'Content-Type': 'application/json' } }))));

    render(<CompaniesMobileModule businessId="business-1" />);

    expect(await screen.findByText('Компания')).toBeInTheDocument();
    expect(screen.queryByText(/Invalid Date/i)).not.toBeInTheDocument();
    expect(screen.getAllByText('Дата неизвестна').length).toBeGreaterThan(0);
  });
});
