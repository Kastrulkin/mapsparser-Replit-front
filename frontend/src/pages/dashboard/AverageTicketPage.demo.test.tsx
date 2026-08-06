import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Outlet, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { LanguageProvider } from '@/i18n/LanguageContext';
import { newAuth } from '@/lib/auth_new';
import { AverageTicketPage } from './AverageTicketPage';

const toastSpy = vi.hoisted(() => vi.fn());

vi.mock('@/hooks/use-toast', () => ({
  useToast: () => ({ toast: toastSpy }),
}));

vi.mock('@/lib/auth_new', () => ({
  newAuth: { makeRequest: vi.fn() },
}));

const ContextRoute = () => (
  <Outlet context={{
    currentBusinessId: 'demo-business',
    user: { id: 'demo-user', demo_mode: true },
  }} />
);

describe('AverageTicketPage demo mode', () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.localStorage.setItem('language', 'tr');
    toastSpy.mockReset();
    vi.mocked(newAuth.makeRequest).mockReset();
    vi.mocked(newAuth.makeRequest).mockRejectedValue(new Error('demo_route_not_allowed'));
  });

  it('uses a local demo overview without calling a forbidden API route or showing an error toast', async () => {
    render(
      <MemoryRouter>
        <LanguageProvider>
          <Routes>
            <Route element={<ContextRoute />}>
              <Route index element={<AverageTicketPage />} />
            </Route>
          </Routes>
        </LanguageProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByText('Matris henüz oluşturulmadı')).toBeInTheDocument();
    await waitFor(() => {
      expect(newAuth.makeRequest).not.toHaveBeenCalled();
      expect(toastSpy).not.toHaveBeenCalled();
    });
  });
});
