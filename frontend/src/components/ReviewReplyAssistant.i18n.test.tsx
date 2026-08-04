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

const ContextRoute = () => <Outlet context={{ currentBusinessId: 'demo-business', onBusinessChange: vi.fn() }} />;

describe('ReviewReplyAssistant localization', () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.localStorage.setItem('language', 'el');
    vi.mocked(newAuth.makeRequest).mockImplementation((url: string) => {
      if (url.includes('/external/reviews')) return Promise.resolve({ success: true, reviews: [] });
      return Promise.resolve({ success: true, examples: [] });
    });
  });

  it('renders the review workflow in Greek without a missing tones dictionary crash', async () => {
    render(
      <MemoryRouter>
        <LanguageProvider>
          <Routes>
            <Route element={<ContextRoute />}>
              <Route index element={<ReviewReplyAssistant businessName="Roga i Kopyta" />} />
            </Route>
          </Routes>
        </LanguageProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByRole('heading', { name: 'Απαντήσεις σε κριτικές' })).toBeInTheDocument();
  });
});
