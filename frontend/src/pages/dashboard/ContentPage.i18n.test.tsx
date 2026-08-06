import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { AudienceInsights } from '@/components/AudienceInsights';
import { LanguageProvider } from '@/i18n/LanguageContext';
import { newAuth } from '@/lib/auth_new';

vi.mock('@/lib/auth_new', () => ({
  newAuth: {
    makeRequest: vi.fn(),
  },
}));

describe('Content audience workspace localization', () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.localStorage.setItem('language', 'el');
    vi.mocked(newAuth.makeRequest).mockResolvedValue({ items: [] });
  });

  it('renders the Greek audience heading and useful empty state without Russian copy', async () => {
    const { container } = render(
      <LanguageProvider>
        <AudienceInsights businessId="demo-business" />
      </LanguageProvider>,
    );

    expect(await screen.findByRole('heading', { name: 'Τι απασχολεί το κοινό' })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText('Δεν υπάρχουν ακόμη επαναλαμβανόμενα θέματα')).toBeInTheDocument());
    expect(container.textContent).not.toMatch(/[А-Яа-яЁё]/);
  });
});
