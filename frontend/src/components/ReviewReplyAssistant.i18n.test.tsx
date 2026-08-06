import { render, screen } from '@testing-library/react';
import { MemoryRouter, Outlet, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { LanguageProvider } from '@/i18n/LanguageContext';
import { newAuth } from '@/lib/auth_new';
import ReviewReplyAssistant from './ReviewReplyAssistant';

vi.mock('@/lib/auth_new', () => ({
  newAuth: {
    makeRequest: vi.fn(),
  },
}));

const ContextRoute = () => <Outlet context={{ user: { id: 'demo-user', demo_mode: true }, currentBusinessId: 'demo-business', onBusinessChange: vi.fn() }} />;

describe('ReviewReplyAssistant localization', () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.localStorage.setItem('language', 'el');
    vi.mocked(newAuth.makeRequest).mockImplementation((url: string) => {
      if (url.includes('/external/reviews')) return Promise.resolve({
        success: true,
        reviews: [{
          id: 'demo-review',
          author_name: 'Сергей Новиков',
          text: 'DEMO Яндекс Карты: отзыв о груминге, аккуратности мастера и удобстве записи.',
          rating: 5,
          published_at: '2026-06-20T12:00:00Z',
          source: 'yandex',
          response_text: 'Спасибо большое за добрые слова! Нам важно ваше мнение.',
        }],
      });
      return Promise.resolve({ success: true, examples: [] });
    });
  });

  it('renders the review workflow in Greek without a missing tones dictionary crash', async () => {
    render(
      <MemoryRouter>
        <LanguageProvider>
          <Routes>
            <Route element={<ContextRoute />}>
              <Route index element={<ReviewReplyAssistant businessName="Roga i Kopyta" aggregateScope="network" />} />
            </Route>
          </Routes>
        </LanguageProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByRole('heading', { name: 'Απαντήσεις σε κριτικές' })).toBeInTheDocument();
    expect(await screen.findByText('Κριτική επίδειξης για την περιποίηση, την προσοχή του ειδικού και την εύκολη κράτηση.')).toBeInTheDocument();
    expect(screen.queryByText(/DEMO Яндекс Карты/)).not.toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/[А-Яа-яЁё]/);
  });
});
