import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { InfluencersMobileModule } from './InfluencersMobileModule';

const responseBody = {
  success: true,
  workspace: {
    next_action: 'Выберите подходящих авторов',
    offer: { service: 'Стрижка', reward: 'стрижку в подарок', threshold: 3 },
    creators: [{ id: 'creator-1', result_id: 'result-1', display_name: 'Анна про Петербург', platform: 'telegram', public_url: 'https://t.me/anna', city: 'Санкт-Петербург', audience_count: 4200, accepts_barter: true, fit_reasons: ['Локальная аудитория'], shortlist_status: 'suggested' }],
    counts: { total: 1, returned: 1, shortlisted: 0 },
    filters: { platforms: ['telegram'] },
    access: { message_generation: { status: 'payment_required', reason: 'После оплаты', cta_label: 'Выбрать тариф', cta_target: { screen: 'settings' } } },
  },
};

describe('InfluencersMobileModule', () => {
  beforeEach(() => {
    window.sessionStorage.setItem('localos_mini_session', 'mini-token');
    vi.stubGlobal('fetch', vi.fn().mockImplementation(() => Promise.resolve(new Response(JSON.stringify(responseBody), { status: 200, headers: { 'Content-Type': 'application/json' } }))));
  });

  afterEach(() => vi.unstubAllGlobals());

  it('opens a real creator workspace instead of redirecting to Operator', async () => {
    const user = userEvent.setup();
    render(<InfluencersMobileModule scope={{ kind: 'business', id: 'business-1', name: 'Салон' }} />);

    expect(await screen.findByRole('heading', { name: 'Анна про Петербург' })).toBeInTheDocument();
    expect(screen.getByText('4 200')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Выбрать тариф' })).toHaveAttribute('href', expect.stringContaining('screen%3Dinfluencers'));
    await user.click(screen.getByRole('button', { name: 'В shortlist' }));
    expect(fetch).toHaveBeenCalledWith('/api/promotion/influencers/search-results/result-1', expect.objectContaining({ method: 'PATCH' }));
  });

  it('shortlists a shared catalog creator through the profile disposition endpoint', async () => {
    const catalogResponse = {
      ...responseBody,
      workspace: {
        ...responseBody.workspace,
        creators: [{
          ...responseBody.workspace.creators[0],
          id: 'creator-public-1',
          result_id: 'catalog:creator-public-1',
          display_name: 'Публичный автор',
        }],
      },
    };
    vi.stubGlobal('fetch', vi.fn().mockImplementation(() => Promise.resolve(new Response(JSON.stringify(catalogResponse), { status: 200, headers: { 'Content-Type': 'application/json' } }))));
    const user = userEvent.setup();

    render(<InfluencersMobileModule scope={{ kind: 'business', id: 'business-1', name: 'Салон' }} />);

    expect(await screen.findByRole('heading', { name: 'Публичный автор' })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'В shortlist' }));
    expect(fetch).toHaveBeenCalledWith(
      '/api/promotion/influencers/catalog/creator-public-1/disposition',
      expect.objectContaining({ method: 'PATCH' }),
    );
  });
});
