import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Outlet, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { newAuth } from '@/lib/auth_new';
import { loadJourneyActions } from '@/lib/leadJourney';
import { InfluencersPage } from './InfluencersPage';

vi.mock('@/lib/auth_new', () => ({ newAuth: { makeRequest: vi.fn() } }));
vi.mock('@/lib/leadJourney', async () => {
  const actual = await vi.importActual<typeof import('@/lib/leadJourney')>('@/lib/leadJourney');
  return { ...actual, loadJourneyActions: vi.fn() };
});

const Context = () => <Outlet context={{ currentBusinessId: 'business-1', currentBusiness: { name: 'Салон', city: 'Санкт-Петербург' } }} />;

const workspace = {
  next_action: 'Выберите 2–5 подходящих авторов',
  offer: { service: 'Стрижка', reward: 'стрижку в подарок', threshold: 3 },
  latest_search: { id: 'search-1', brief: { area: 'Петроградский район', service: 'Стрижка' }, results_count: 1, shortlisted_count: 0 },
  creators: [{
    id: 'creator-1', result_id: 'result-1', display_name: 'Анна про Петербург', platform: 'telegram',
    public_url: 'https://t.me/anna', city: 'Санкт-Петербург', area: 'Петроградский район', audience_count: 4200,
    primary_topic: 'Красота и уход', accepts_barter: true, contactability: 'advertising_contact', score: 86,
    fit_reasons: ['Пишет о локальных услугах'], shortlist_status: 'suggested', evidence: [{ summary: 'Публичный обзор салона' }],
  }],
  counts: { total: 1, returned: 1, shortlisted: 0 },
  filters: { platforms: ['telegram'], cities: ['Санкт-Петербург'], topics: ['Красота и уход'], audience_size_bands: [] },
  access: {
    discovery: { status: 'available', reason: 'Доступно', cta_label: 'Смотреть', cta_target: { screen: 'influencers' } },
    message_generation: { status: 'payment_required', reason: 'Подготовка сообщений доступна после оплаты.', cta_label: 'Выбрать тариф', cta_target: { screen: 'settings' } },
  },
};

describe('InfluencersPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(loadJourneyActions).mockResolvedValue([]);
    vi.mocked(newAuth.makeRequest).mockImplementation((path) => {
      if (path.startsWith('/promotion/influencers/workspace')) return Promise.resolve({ workspace });
      return Promise.resolve({ success: true });
    });
  });

  it('keeps creator discovery free and locks only personalized messages', async () => {
    const user = userEvent.setup();
    render(<MemoryRouter initialEntries={['/dashboard/influencers']}><Routes><Route element={<Context />}><Route path="/dashboard/influencers" element={<InfluencersPage />} /></Route></Routes></MemoryRouter>);

    expect(await screen.findByRole('heading', { name: 'Анна про Петербург' })).toBeInTheDocument();
    expect(screen.getByText(/Публичный обзор салона/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Выбрать' })).toBeEnabled();

    await user.click(screen.getByRole('tab', { name: 'Сообщения' }));
    expect(await screen.findByText('Подготовка сообщений доступна после оплаты.')).toBeVisible();
    expect(screen.getByRole('link', { name: 'Выбрать тариф' })).toHaveAttribute('href', '/dashboard/profile?focus=subscription#subscription');
  });
});
