import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Outlet, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { LanguageProvider } from '@/i18n/LanguageContext';
import { api } from '@/services/api';
import { OperatorPage } from './OperatorPage';

vi.mock('@/services/api', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

const ContextRoute = () => (
  <Outlet context={{ currentBusinessId: 'demo-business', currentBusiness: { id: 'demo-business', name: 'Demo Business' } }} />
);

describe('OperatorPage localization', () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.localStorage.setItem('language', 'el');
    vi.mocked(api.get).mockResolvedValue({ data: { messages: [], conversation: null } });
  });

  it('renders Greek Operator copy without loading the legacy daily summary', async () => {
    const { container } = render(
      <MemoryRouter>
        <LanguageProvider>
          <Routes>
            <Route element={<ContextRoute />}>
              <Route index element={<OperatorPage />} />
            </Route>
          </Routes>
        </LanguageProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByRole('heading', { name: 'Διαχείριση μέσω συνομιλίας' })).toBeInTheDocument();
    await waitFor(() => expect(api.get).toHaveBeenCalled());
    expect(vi.mocked(api.get).mock.calls.some(([url]) => url === '/operator/summary')).toBe(false);
    expect(screen.getByRole('button', { name: 'Αναφορά προβλήματος' })).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/[А-Яа-яЁё]/);
    expect(container.textContent).not.toContain('Telegram shows the same summary');
  });

  it('keeps the saved conversation when history refresh has a temporary failure', async () => {
    window.localStorage.setItem('language', 'ru');
    window.localStorage.setItem('localos_operator_conversation_demo-business', 'saved-conversation');
    vi.mocked(api.get).mockRejectedValue({ response: { status: 503 } });

    render(
      <MemoryRouter>
        <LanguageProvider>
          <Routes>
            <Route element={<ContextRoute />}>
              <Route index element={<OperatorPage />} />
            </Route>
          </Routes>
        </LanguageProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByText('Не удалось обновить историю. Последние сообщения сохранены на экране.')).toBeInTheDocument();
    expect(window.localStorage.getItem('localos_operator_conversation_demo-business')).toBe('saved-conversation');
    expect(screen.getByRole('button', { name: 'Повторить' })).toBeInTheDocument();
  });

  it('clears stored history after access is revoked', async () => {
    window.localStorage.setItem('language', 'ru');
    window.localStorage.setItem('localos_operator_conversation_demo-business', 'saved-conversation');
    vi.mocked(api.get).mockRejectedValue({ response: { status: 403 } });
    render(<MemoryRouter><LanguageProvider><Routes><Route element={<ContextRoute />}><Route index element={<OperatorPage />} /></Route></Routes></LanguageProvider></MemoryRouter>);
    expect(await screen.findByText('Нет доступа к этой истории. Проверьте выбранный бизнес или обратитесь к владельцу.')).toBeInTheDocument();
    expect(window.localStorage.getItem('localos_operator_conversation_demo-business')).toBeNull();
  });
});
