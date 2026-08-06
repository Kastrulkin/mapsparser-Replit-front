import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Outlet, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { AudienceInsights } from '@/components/AudienceInsights';
import { LanguageProvider } from '@/i18n/LanguageContext';
import { newAuth } from '@/lib/auth_new';
import { ContentPage } from './ContentPage';

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

  it('localizes the Russian demo business name on the Turkish content page', async () => {
    window.localStorage.setItem('language', 'tr');
    vi.mocked(newAuth.makeRequest).mockImplementation(async (path) => {
      if (path.startsWith('/content-plans/context')) return { context: {} };
      if (path.startsWith('/content-plans?')) return { plans: [{ id: 'demo-plan', period_days: 14 }] };
      if (path === '/content-plans/demo-plan') {
        return {
          plan: {
            id: 'demo-plan',
            period_days: 14,
            items: [{ id: 'demo-item', theme: 'Evcil hayvan bakımı', draft_text: 'Yaz bakımı için kısa bir öneri.', scheduled_for: '2026-08-08' }],
          },
        };
      }
      if (path === '/content-plans/demo-plan/social-posts') {
        return {
          posts: [{ id: 'demo-post', content_plan_item_id: 'demo-item', platform: 'telegram', status: 'needs_review' }],
          summary: { needs_review: 1 },
        };
      }
      return {};
    });

    const ContextRoute = () => (
      <Outlet context={{
        user: { id: 'demo-user', demo_mode: true },
        currentBusinessId: 'demo-business',
        currentBusiness: { id: 'demo-business', name: 'Рога и копыта' },
      }} />
    );

    const { container } = render(
      <MemoryRouter initialEntries={['/dashboard/content']}>
        <LanguageProvider>
          <Routes>
            <Route element={<ContextRoute />}>
              <Route path="/dashboard/content" element={<ContentPage />} />
            </Route>
          </Routes>
        </LanguageProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByRole('heading', { name: 'İçerik' })).toBeInTheDocument();
    expect(screen.getByText('Roga i Kopyta')).toBeInTheDocument();
    expect(await screen.findByRole('heading', { name: 'İçerik hazır' })).toBeInTheDocument();
    await waitFor(() => expect(container.textContent).not.toMatch(/[А-Яа-яЁё]/));
  });
});
