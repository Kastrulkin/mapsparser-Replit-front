import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Outlet, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { LanguageProvider } from '@/i18n/LanguageContext';
import NewsGenerator from './NewsGenerator';

const ContextRoute = () => <Outlet context={{ user: { id: 'demo-user', demo_mode: true } }} />;

describe('NewsGenerator localization', () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.localStorage.setItem('language', 'tr');
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ success: true, news: [], transactions: [], keywords: [], available: false }),
    }));
  });

  it('renders the Turkish demo news workspace without Russian or English source labels', async () => {
    const { container } = render(
      <MemoryRouter>
        <LanguageProvider>
          <Routes>
            <Route element={<ContextRoute />}>
              <Route index element={<NewsGenerator services={[]} businessId="demo-business" />} />
            </Route>
            <Route path="/dashboard/content" element={<h1>Content calendar</h1>} />
          </Routes>
        </LanguageProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByText('Kaynak materyal')).toBeInTheDocument();
    const planLink = screen.getByRole('link', { name: 'İçerik planı' });
    expect(planLink).toHaveAttribute('href', '/dashboard/content?section=calendar');
    expect(container.textContent).not.toMatch(/[А-Яа-яЁё]/);
    expect(container.textContent).not.toContain('Source Material');
    expect(fetch).not.toHaveBeenCalled();
    fireEvent.click(planLink);
    expect(await screen.findByRole('heading', { name: 'Content calendar' })).toBeInTheDocument();
  });
});
