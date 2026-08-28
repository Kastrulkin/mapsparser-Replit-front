import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { newAuth } from '@/lib/auth_new';
import { CommunityFeedPage } from './CommunityFeedPage';

vi.mock('@/lib/auth_new', () => ({ newAuth: { makeRequest: vi.fn() } }));

const renderPage = () => render(
  <MemoryRouter initialEntries={['/dashboard/feed']}>
    <Routes>
      <Route element={<CommunityFeedPage />} path="/dashboard/feed" />
    </Routes>
  </MemoryRouter>,
);

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return {
    ...actual,
    useOutletContext: () => ({
      currentBusinessId: 'business-1',
      controlScope: { kind: 'business', id: 'business-1', name: 'Тестовый бизнес' },
    }),
  };
});
describe('CommunityFeedPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(newAuth.makeRequest).mockResolvedValue({
      topics: [{ id: 'topic-1', title: 'Продвижение через локальных авторов', description: 'Бизнесы обсуждают микроинфлюенсеров.' }],
      topic_trends: [],
      items: [{ id: 'item-1', platform: 'telegram', source_name: 'Beauty Business', title: 'Beauty Business', text: 'Новое сообщение из отраслевого канала.', url: 'https://t.me/example/1' }],
      cursor: null,
      as_of: new Date().toISOString(),
    });
  });

  it('loads the canonical feed for the selected business', async () => {
    renderPage();

    expect(await screen.findByRole('heading', { name: 'Сообщения и новости вашей индустрии' })).toBeInTheDocument();
    expect(await screen.findByText('Продвижение через локальных авторов')).toBeInTheDocument();
    expect(screen.getByText('Новое сообщение из отраслевого канала.')).toHaveClass('line-clamp-4');
    expect(screen.getAllByText('Beauty Business')).toHaveLength(1);
    expect(screen.getByRole('link', { name: /Beauty Business.*Новое сообщение из отраслевого канала/i })).toHaveAttribute('href', 'https://t.me/example/1');
    expect(screen.queryByText('Открыть сообщение')).not.toBeInTheDocument();
    await waitFor(() => expect(newAuth.makeRequest).toHaveBeenCalledWith(expect.stringContaining('/operator/feed?')));
  });
});
