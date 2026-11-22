import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Outlet, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { LanguageProvider } from '@/i18n/LanguageContext';
import SEOKeywordsTab from './SEOKeywordsTab';

const response = (data: Record<string, unknown>) => Promise.resolve(new Response(JSON.stringify(data), {
  status: 200,
  headers: { 'Content-Type': 'application/json' },
}));

const ContextRoute = () => (
  <Outlet context={{ user: { id: 'demo-user', demo_mode: true } }} />
);

describe('SEOKeywordsTab localization', () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.localStorage.setItem('language', 'tr');
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes('/api/wordstat/negative-keywords')) {
        return response({ success: true, items: [] });
      }
      if (url.includes('/api/wordstat/keywords')) {
        return response({ success: true, items: [], grouped: {} });
      }
      return response({ success: true });
    }));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('renders the Turkish demo negative-keyword controls without Cyrillic fallback copy', async () => {
    const { container } = render(
      <MemoryRouter>
        <LanguageProvider>
          <Routes>
            <Route element={<ContextRoute />}>
              <Route index element={<SEOKeywordsTab businessId="demo-business" />} />
            </Route>
          </Routes>
        </LanguageProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByText('köpek bakımı')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'SEO negatif anahtar kelimeleri' })).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Negatif anahtar kelime ekle')).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Güncellendi' })).toBeInTheDocument();
    expect(fetch).not.toHaveBeenCalled();
    await waitFor(() => expect(container.textContent).not.toMatch(/[А-Яа-яЁё]/));
  });

  it('labels the rendered update-date column in Russian', async () => {
    window.localStorage.setItem('language', 'ru');
    render(
      <MemoryRouter>
        <LanguageProvider>
          <Routes>
            <Route element={<ContextRoute />}>
              <Route index element={<SEOKeywordsTab businessId="demo-business" />} />
            </Route>
          </Routes>
        </LanguageProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByRole('columnheader', { name: 'Обновлено' })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Показов в месяц' })).toBeInTheDocument();
  });
});
