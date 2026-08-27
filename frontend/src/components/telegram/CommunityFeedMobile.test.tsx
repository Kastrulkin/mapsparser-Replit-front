import '@testing-library/jest-dom/vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { CommunityFeedMobile } from './CommunityFeedMobile';

describe('CommunityFeedMobile', () => {
  beforeEach(() => {
    window.sessionStorage.setItem('localos_mini_session', 'session');
  });

  it('shows topic summaries and opens the original Telegram message', async () => {
    const openTelegramLink = vi.fn();
    Object.defineProperty(window, 'Telegram', {
      configurable: true,
      value: { WebApp: { openTelegramLink } },
    });
    const user = userEvent.setup();

    render(<CommunityFeedMobile scope={{ kind: 'business', id: 'preview', name: 'Бизнесс', business_ids: ['preview'] }} preview />);

    expect(screen.getByRole('heading', { name: 'Лента' })).toBeInTheDocument();
    expect(screen.getByText('Растут цены на красители')).toBeInTheDocument();
    expect(screen.getByText('Главные темы в динамике')).toBeInTheDocument();
    expect(screen.getByText('27%')).toBeInTheDocument();
    expect(screen.getAllByRole('progressbar')).toHaveLength(5);
    expect(screen.getAllByText('Открыть сообщение')).toHaveLength(2);

    await user.click(screen.getByRole('tab', { name: 'Квартал' }));
    expect(await screen.findByText('23%')).toBeInTheDocument();

    await user.click(screen.getAllByText('Открыть сообщение')[0]);
    expect(openTelegramLink).toHaveBeenCalledWith('https://t.me/beauty_business/101');
  });

  it('shows topic statistics before the daily discussion summary', () => {
    render(<CommunityFeedMobile scope={{ kind: 'business', id: 'preview', name: 'Бизнесс', business_ids: ['preview'] }} preview />);

    const statistics = screen.getByRole('heading', { name: 'Главные темы в динамике' });
    const dailySummary = screen.getByRole('heading', { name: 'О чём говорят предприниматели' });

    expect(statistics.compareDocumentPosition(dailySummary) & Node.DOCUMENT_POSITION_FOLLOWING).not.toBe(0);
  });

  it('loads only the verified scope from the mobile feed endpoint', async () => {
    const fetchMock = vi.fn(() => Promise.resolve(new Response(JSON.stringify({
      success: true,
      topics: [],
      topic_trends: [],
      items: [{ id: 'message-1', platform: 'telegram', source_name: 'Канал', text: 'Новое сообщение', published_at: '2026-08-26T08:00:00Z', url: 'https://t.me/channel/1' }],
      cursor: null,
      as_of: '2026-08-26T08:01:00Z',
      available_actions: ['community_sources.manage'],
    }), { status: 200, headers: { 'Content-Type': 'application/json' } })));
    vi.stubGlobal('fetch', fetchMock);

    render(<CommunityFeedMobile scope={{ kind: 'network', id: 'network-1', name: 'Сеть', business_ids: ['b-1', 'b-2'] }} />);

    expect(await screen.findByText('Новое сообщение')).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('scope_type=network&scope_id=network-1'), expect.anything());
  });
});
