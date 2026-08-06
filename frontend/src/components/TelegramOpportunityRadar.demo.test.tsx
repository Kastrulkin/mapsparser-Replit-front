import { render, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { LanguageProvider } from '@/i18n/LanguageContext';
import { api } from '@/services/api';
import { TelegramOpportunityRadar } from './TelegramOpportunityRadar';

vi.mock('@/services/api', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
  },
}));

describe('TelegramOpportunityRadar demo mode', () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.localStorage.setItem('language', 'tr');
    vi.mocked(api.get).mockRejectedValue(new Error('demo_route_not_allowed'));
  });

  it('renders localized empty demo state without calling restricted routes', async () => {
    const { container } = render(
      <LanguageProvider>
        <TelegramOpportunityRadar businessId="demo-business" mode="work" demoMode />
      </LanguageProvider>,
    );

    await waitFor(() => expect(container.textContent).toContain('Bulunan mesajlar'));
    expect(api.get).not.toHaveBeenCalled();
    expect(container.textContent).not.toContain('demo_route_not_allowed');
    expect(container.textContent).not.toMatch(/[А-Яа-яЁё]/);
  });
});
