import { render, screen } from '@testing-library/react';
import { MemoryRouter, Outlet, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { LanguageProvider } from '@/i18n/LanguageContext';
import { newAuth } from '@/lib/auth_new';
import { ChatsPage } from './ChatsPage';

vi.mock('@/lib/auth_new', () => ({
  newAuth: {
    getToken: vi.fn(),
  },
}));

vi.mock('@/components/outreach/OutreachSandbox', () => ({
  OutreachSandbox: () => <div data-testid="outreach-sandbox" />,
}));

const ContextRoute = () => <Outlet context={{ currentBusinessId: 'demo-business' }} />;

describe('ChatsPage localization', () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.localStorage.setItem('language', 'de');
    vi.mocked(newAuth.getToken).mockResolvedValue('demo-token');
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes('/ai-agents')) {
        return new Response(JSON.stringify({
          success: true,
          agents: [{ id: 'booking', name: 'Booking Agent', type: 'booking', description: null }],
        }), { status: 200, headers: { 'Content-Type': 'application/json' } });
      }
      return new Response(JSON.stringify({ success: true, conversations: [] }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }));
    HTMLElement.prototype.scrollIntoView = vi.fn();
  });

  it('renders chat navigation and empty states in German', async () => {
    const { container } = render(
      <MemoryRouter initialEntries={['/dashboard/chats']}>
        <LanguageProvider>
          <Routes>
            <Route element={<ContextRoute />}>
              <Route path="/dashboard/chats" element={<ChatsPage />} />
            </Route>
          </Routes>
        </LanguageProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByRole('tab', { name: 'Gespräche' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Agent testen' })).toBeInTheDocument();
    expect(await screen.findByText('Keine aktiven Chats')).toBeInTheDocument();
    expect(screen.getByText('Wählen Sie einen Chat oder Testbereich aus')).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/[А-Яа-яЁё]/);
  });
});
