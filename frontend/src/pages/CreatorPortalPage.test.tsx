import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { CreatorPortalPage } from './CreatorPortalPage';

const offer = {
  id: 'recipient-1',
  status: 'selected',
  title: 'Семейная стрижка за результат',
  goal: 'Привести трёх новых клиентов',
  business_name: 'Весёлая расчёска',
  offer_kind: 'distributed',
  collaboration_id: 'collaboration-1',
  collaboration_status: 'agreed',
  offer: { service: 'Детская стрижка', benefit: 'Бесплатная стрижка', result_condition: 'Если придут 3 новых клиента' },
  deliverables: [],
  messages: [],
};

const workspace = {
  account: { display_name: 'Анна', notification_preferences: {} },
  profile: { display_name: 'Анна' },
  offers: { new: [], active: [offer], finished: [] },
};

describe('CreatorPortalPage publication flow', () => {
  beforeEach(() => {
    window.localStorage.setItem('localos_creator_portal_token', 'creator-session');
    vi.unstubAllGlobals();
  });

  it('lets a selected creator submit the publication URL', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith('/me')) return { ok: true, json: async () => ({ success: true, workspace }) };
      if (url.endsWith('/publication')) return { ok: true, json: async () => ({ success: true, offer: { ...offer, status: 'published', deliverables: [{ id: 'deliverable-1', platform: 'telegram', deliverable_type: 'post', publication_url: 'https://t.me/anna/42', verification_status: 'submitted' }] } }) };
      return { ok: true, json: async () => ({ success: true, offer }) };
    });
    vi.stubGlobal('fetch', fetchMock);
    const user = userEvent.setup();

    render(<MemoryRouter initialEntries={['/creator/offers/recipient-1']}><Routes><Route path="/creator/offers/:offerId" element={<CreatorPortalPage />} /></Routes></MemoryRouter>);

    expect(await screen.findByRole('heading', { name: 'Публикация и результат' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Запросить детали' })).toBeInTheDocument();
    await user.type(screen.getByPlaceholderText('https://...'), 'https://t.me/anna/42');
    await user.click(screen.getByRole('button', { name: 'Передать ссылку LocalOS' }));

    expect(await screen.findByText('Ссылка передана LocalOS на проверку.')).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith('/api/creator-portal/offers/recipient-1/publication', expect.objectContaining({ method: 'POST' }));
  });

  it('registers an invited creator through four profile steps', async () => {
    let completed = false;
    const onboardingWorkspace = {
      account: { display_name: 'Анна', notification_preferences: {} },
      profile: { display_name: 'Анна', channels: [], formats: [] },
      offers: { new: [], active: [], finished: [] },
      onboarding_required: true,
      city_options: ['Санкт-Петербург', 'Москва'],
    };
    const fetchMock = vi.fn(async (input: RequestInfo | URL, options?: RequestInit) => {
      const url = String(input);
      if (url.endsWith('/me')) return { ok: true, json: async () => ({ success: true, workspace: completed ? { ...onboardingWorkspace, onboarding_required: false } : onboardingWorkspace }) };
      if (url.endsWith('/profile') && options?.method === 'PATCH') { completed = true; return { ok: true, json: async () => ({ success: true, profile: {} }) }; }
      return { ok: true, json: async () => ({ success: true }) };
    });
    vi.stubGlobal('fetch', fetchMock);
    const user = userEvent.setup();

    render(<MemoryRouter initialEntries={['/creator']}><Routes><Route path="/creator" element={<CreatorPortalPage />} /></Routes></MemoryRouter>);

    expect(await screen.findByRole('heading', { name: 'Расскажите о себе' })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Продолжить' }));
    expect(screen.getByRole('heading', { name: 'Где и как вы публикуете' })).toBeInTheDocument();
    await user.click(screen.getByRole('checkbox', { name: 'Telegram' }));
    await user.click(screen.getByRole('checkbox', { name: 'Пост' }));
    await user.click(screen.getByRole('button', { name: 'Да, рассматриваю' }));
    await user.click(screen.getByRole('button', { name: 'Продолжить' }));
    expect(screen.getByRole('heading', { name: 'Где вы готовы работать' })).toBeInTheDocument();
    await user.click(screen.getByRole('combobox', { name: 'Основной город *' }));
    await user.click(screen.getByRole('option', { name: 'Санкт-Петербург' }));
    await user.click(screen.getByRole('button', { name: 'По всему городу' }));
    await user.click(screen.getByRole('button', { name: 'Продолжить' }));
    expect(screen.getByRole('heading', { name: 'Добавьте свои площадки' })).toBeInTheDocument();
    expect(screen.getByText('Укажите ссылки на страницы, где вы публикуете контент.')).toBeInTheDocument();
    expect(screen.queryByText('Безопасное подключение.')).not.toBeInTheDocument();
    await user.type(screen.getByPlaceholderText('t.me/username'), 't.me/anna_spb');
    await user.click(screen.getByRole('button', { name: 'Завершить регистрацию' }));

    expect(await screen.findByRole('heading', { name: 'Новые' })).toBeInTheDocument();
    const profileCall = fetchMock.mock.calls.find(([input]) => String(input).endsWith('/profile'));
    expect(profileCall?.[1]).toEqual(expect.objectContaining({ method: 'PATCH' }));
    expect(JSON.parse(String(profileCall?.[1]?.body))).toEqual(expect.objectContaining({ home_city: 'Санкт-Петербург', accepts_barter: true, onboarding_completed: true, channels: [{ platform: 'telegram', url: 't.me/anna_spb' }] }));
  });
});
