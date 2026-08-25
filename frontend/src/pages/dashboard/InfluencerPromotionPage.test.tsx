import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Outlet, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { newAuth } from '@/lib/auth_new';
import { InfluencerPromotionPage } from './InfluencerPromotionPage';

vi.mock('@/lib/auth_new', () => ({
  newAuth: {
    makeRequest: vi.fn(),
  },
}));

const emptyOverview = {
  overview: {
    feature_state: { discovery: true, outreach: true, metrics: true },
    latest_search: null,
    campaigns: [],
    collaborations: [],
    metrics: {},
    next_action: 'Запустить первый поиск локальных авторов',
  },
};

const DashboardContext = () => (
  <Outlet context={{
    currentBusinessId: 'business-1',
    currentBusiness: {
      creator_promotion_available: true,
      city: 'Санкт-Петербург',
      name: 'Органика',
    },
  }} />
);

const renderPage = () => render(
  <MemoryRouter initialEntries={['/dashboard/promotion/influencers']}>
    <Routes>
      <Route element={<DashboardContext />}>
        <Route path="/dashboard/promotion/influencers" element={<InfluencerPromotionPage />} />
      </Route>
    </Routes>
  </MemoryRouter>,
);

describe('InfluencerPromotionPage accessibility states', () => {
  beforeEach(() => {
    vi.mocked(newAuth.makeRequest).mockReset();
    vi.mocked(newAuth.makeRequest).mockResolvedValue(emptyOverview);
  });

  it('renders a useful empty state and exposes the workspace as keyboard tabs', async () => {
    const user = userEvent.setup();
    renderPage();

    expect(await screen.findByRole('heading', { name: 'Подходящих авторов ещё не искали' })).toBeInTheDocument();
    const searchTab = screen.getByRole('tab', { name: 'Поиск' });
    const campaignTab = screen.getByRole('tab', { name: 'Кампании' });
    expect(searchTab).toHaveAttribute('aria-selected', 'true');
    expect(searchTab).toHaveAttribute('aria-controls', 'influencer-panel-search');

    searchTab.focus();
    await user.keyboard('{ArrowRight}');

    expect(campaignTab).toHaveFocus();
    expect(campaignTab).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('heading', { name: 'Кампаний пока нет' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Перейти к поиску' })).toBeInTheDocument();
  });

  it('offers a retry after an overview loading error', async () => {
    const user = userEvent.setup();
    vi.mocked(newAuth.makeRequest)
      .mockRejectedValueOnce(new Error('Сервис временно недоступен'))
      .mockResolvedValueOnce(emptyOverview);
    renderPage();

    expect(await screen.findByRole('alert')).toHaveTextContent('Сервис временно недоступен');
    await user.click(screen.getByRole('button', { name: 'Повторить' }));

    await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument());
    expect(screen.getByRole('heading', { name: 'Подходящих авторов ещё не искали' })).toBeInTheDocument();
    expect(newAuth.makeRequest).toHaveBeenCalledTimes(2);
  });

  it('sends structured local filters when launching discovery', async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByRole('heading', { name: 'Подходящих авторов ещё не искали' });
    vi.mocked(newAuth.makeRequest).mockClear();

    await user.type(screen.getByLabelText('Район или метро'), 'Выборгский');
    await user.type(screen.getByLabelText('Аудитория'), 'родители');
    await user.click(screen.getByRole('button', { name: 'Уточнить площадки и формат' }));
    await user.selectOptions(screen.getByLabelText('Подача'), 'reviews');
    await user.selectOptions(screen.getByLabelText('Канал'), 'instagram');
    await user.clear(screen.getByLabelText('Сколько кандидатов'));
    await user.type(screen.getByLabelText('Сколько кандидатов'), '30');
    await user.click(screen.getByRole('button', { name: 'Запустить поиск' }));

    await waitFor(() => expect(newAuth.makeRequest).toHaveBeenCalled());
    const searchCall = vi.mocked(newAuth.makeRequest).mock.calls.find(([path]) => path === '/promotion/influencers/searches');
    const requestBody = searchCall?.[1]?.body;
    if (typeof requestBody !== 'string') throw new Error('Search request body was not serialized');
    const payload = JSON.parse(requestBody);
    expect(payload.brief).toMatchObject({
      city: 'Санкт-Петербург',
      area: 'Выборгский',
      audience: 'родители',
      content_styles: ['reviews'],
      platforms: ['instagram'],
      result_limit: 30,
      audience_size_bands: ['nano', 'micro'],
      contact_required: true,
    });
  });

  it('prioritizes a reviewable first batch instead of rendering the whole catalog', async () => {
    const user = userEvent.setup();
    const results = Array.from({ length: 31 }, (_, index) => ({
      id: `result-${index}`,
      creator_profile_id: `creator-${index}`,
      display_name: `Автор ${index + 1}`,
      result_group: 'needs_review',
      shortlist_status: index === 30 ? 'shortlisted' : 'suggested',
      score: index,
      platform: index === 30 ? 'instagram' : 'telegram',
      public_metrics: index === 30 ? { followers: 12500 } : {},
      reasons: ['Публичные данные требуют проверки'],
    }));
    vi.mocked(newAuth.makeRequest).mockImplementation(async (path) => {
      if (path.startsWith('/promotion/influencers/overview')) {
        return { ...emptyOverview, overview: { ...emptyOverview.overview, latest_search: { id: 'search-1' } } };
      }
      return { search: { id: 'search-1', status: 'ready', results } };
    });
    renderPage();

    const candidateHeading = await screen.findByRole('heading', { name: 'Автор 31' });
    expect(candidateHeading.closest('article')).toHaveTextContent('Канал: Instagram');
    expect(candidateHeading.closest('article')).toHaveTextContent(/Аудитория: 12.500 подписчиков/);
    expect(screen.getByRole('heading', { name: 'Кандидаты' }).parentElement).toHaveTextContent('30 из 31');
    expect(screen.getAllByRole('article')).toHaveLength(30);

    await user.click(screen.getByRole('button', { name: 'Показать ещё 1' }));

    expect(screen.getAllByRole('article')).toHaveLength(31);
  });

  it('shows a read-only personalized invitation before campaign approval', async () => {
    const user = userEvent.setup();
    vi.mocked(newAuth.makeRequest).mockImplementation(async (path) => {
      if (path.startsWith('/promotion/influencers/overview')) {
        return {
          overview: {
            ...emptyOverview.overview,
            campaigns: [{
              id: 'campaign-1',
              title: 'Локальное продвижение · Органика',
              goal: 'Получить обращения',
              status: 'draft',
              candidates: [{ id: 'candidate-1', display_name: 'Локальный автор', platform: 'telegram' }],
            }],
          },
        };
      }
      if (path.startsWith('/promotion/influencers/campaigns/campaign-1/candidates/candidate-1/outreach-preview')) {
        return {
          preview: {
            display_name: 'Локальный автор',
            message: 'Здравствуйте!\n\nВидим, что вы рассказываете о локальном wellness.',
            personalization: { summary: 'Публичный профиль посвящён локальному wellness', source_url: 'https://example.test/evidence' },
            contact: { status: 'public_unverified', value: '@local_author' },
            terms_review: { missing: ['бюджет или бартер', 'сроки', 'права на материал'] },
            requires_campaign_approval: true,
          },
        };
      }
      if (path.startsWith('/promotion/influencers/campaigns/campaign-1/candidates/candidate-1/confirm-contact')) {
        return {
          preview: {
            display_name: 'Локальный автор',
            message: 'Здравствуйте!',
            contact: { status: 'confirmed', value: '@local_author' },
            terms_review: { missing: ['бюджет или бартер', 'сроки', 'права на материал'] },
          },
        };
      }
      return {};
    });
    renderPage();
    await screen.findByRole('heading', { name: 'Подходящих авторов ещё не искали' });
    await user.click(screen.getByRole('tab', { name: 'Кампании' }));

    expect(screen.getByRole('button', { name: 'Подготовить контакт: Локальный автор' })).toBeDisabled();
    await user.click(screen.getByRole('button', { name: 'Черновик приглашения: Локальный автор' }));

    expect(await screen.findByText(/локальном wellness/)).toBeInTheDocument();
    expect(screen.getByText(/принадлежность не подтверждена/)).toBeInTheDocument();
    expect(screen.getByText(/бюджет или бартер, сроки, права на материал/)).toBeInTheDocument();
    const confirmButton = screen.getByRole('button', { name: 'Подтвердить контакт' });
    expect(confirmButton).toBeDisabled();
    await user.click(screen.getByRole('checkbox'));
    await user.click(confirmButton);
    expect(await screen.findByText('Контакт подтверждён')).toBeInTheDocument();
  });

  it('prefills safe timing and rights without inventing a budget', async () => {
    const user = userEvent.setup();
    vi.mocked(newAuth.makeRequest).mockResolvedValue({
      overview: {
        ...emptyOverview.overview,
        campaigns: [{
          id: 'campaign-eur',
          title: 'Riderra Tallinn',
          goal: 'Проверить бронирования',
          status: 'draft',
          budget: { maximum: 500, currency: 'EUR' },
          candidates: [],
        }],
      },
    });
    renderPage();
    await screen.findByRole('heading', { name: 'Подходящих авторов ещё не искали' });
    await user.click(screen.getByRole('tab', { name: 'Кампании' }));
    await user.click(screen.getByRole('button', { name: 'Изменить условия' }));

    expect(screen.getByLabelText('Валюта бюджета')).toHaveValue('EUR');
    expect(screen.getByPlaceholderText('Например, 15 000')).toHaveValue('500');
    await user.click(screen.getByRole('button', { name: 'Заполнить рекомендуемые условия' }));
    expect(screen.getByDisplayValue(/14 дней после согласования/)).toBeInTheDocument();
    expect(screen.getByDisplayValue(/90 дней с указанием автора/)).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Например, 15 000')).toHaveValue('500');
  });
});
