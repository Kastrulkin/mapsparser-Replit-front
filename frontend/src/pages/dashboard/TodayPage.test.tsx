import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Outlet, Route, Routes, useLocation } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { newAuth } from '@/lib/auth_new';
import { LEAD_JOURNEY_STORAGE_KEY } from '@/lib/leadJourney';
import { TodayPage } from './TodayPage';

vi.mock('@/lib/auth_new', () => ({ newAuth: { makeRequest: vi.fn() } }));
vi.mock('@/i18n/LanguageContext', () => ({ useLanguage: () => ({ language: 'ru' }) }));

const ContextRoute = () => <Outlet context={{ currentBusinessId: 'business-1' }} />;
const NetworkContextRoute = () => <Outlet context={{ currentBusinessId: 'business-1', controlScope: { kind: 'network', id: 'network-1', name: 'Сеть' } }} />;
const renderPage = () => render(<MemoryRouter><Routes><Route element={<ContextRoute />}><Route index element={<TodayPage />} /></Route></Routes></MemoryRouter>);
const LocationProbe = () => {
  const location = useLocation();
  return <div>{`${location.pathname}${location.search}`}</div>;
};

describe('TodayPage', () => {
  beforeEach(() => {
    vi.mocked(newAuth.makeRequest).mockReset();
    window.localStorage.clear();
  });

  it('shows a concrete maps task instead of registration journey copy', async () => {
    window.localStorage.setItem(LEAD_JOURNEY_STORAGE_KEY, 'maps');
    vi.mocked(newAuth.makeRequest).mockResolvedValue({ active_work: [], changes_24h: [], completed_results: [] });

    render(
      <MemoryRouter initialEntries={['/dashboard/today']}>
        <Routes>
          <Route element={<ContextRoute />}>
            <Route path="/dashboard/today" element={<TodayPage />} />
            <Route path="/dashboard/card" element={<LocationProbe />} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByRole('heading', { name: 'Проверьте карточку на картах' })).toBeInTheDocument();
    expect(screen.getByText(/Добавьте ссылку на карточку/)).toBeInTheDocument();
    expect(screen.queryByText('Вы выбрали до регистрации')).not.toBeInTheDocument();
    expect(screen.queryByText(/зафиксирует статус или результат/)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Проверить карточку' }));
    expect(screen.getByText('/dashboard/card')).toBeInTheDocument();
  });

  it('keeps a loading state until the operational summary is available', async () => {
    let resolveRequest: (value: unknown) => void = () => undefined;
    vi.mocked(newAuth.makeRequest).mockReturnValue(new Promise((resolve) => { resolveRequest = resolve; }));
    renderPage();
    expect(screen.getByText('Загружаем новые события и текущие задачи.')).toBeInTheDocument();
    resolveRequest({ active_work: [], changes_24h: [], completed_results: [] });
    await screen.findByText('Сейчас у LocalOS нет активных задач.');
  });

  it('shows an evidence-led empty state without inventing changes or active work', async () => {
    vi.mocked(newAuth.makeRequest).mockResolvedValue({ active_work: [], changes_24h: [], completed_results: [] });
    renderPage();
    expect(await screen.findByText('Сейчас у LocalOS нет активных задач.')).toBeInTheDocument();
    expect(screen.queryByText('Что изменилось')).not.toBeInTheDocument();
    expect(screen.queryByText('Что LocalOS делает сейчас')).not.toBeInTheDocument();
    expect(screen.queryByText('1. Действие')).not.toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: 'Открыть прогресс' })).toHaveLength(1);
  });

  it('uses a single-column-first responsive layout for narrow screens', async () => {
    vi.mocked(newAuth.makeRequest).mockResolvedValue({
      active_work: [{ id: 'work-1', title: 'Подготовить ответ' }],
      changes_24h: [{ id: 'change-1', title: 'Получен отзыв' }],
      completed_results: [],
    });
    const { container } = renderPage();
    await waitFor(() => expect(screen.getByText('Что изменилось')).toBeInTheDocument());
    expect(container.querySelector('.lg\\:grid-cols-2')).toBeInTheDocument();
  });

  it('keeps external changes separate from LocalOS results', async () => {
    vi.mocked(newAuth.makeRequest).mockResolvedValue({
      active_work: [],
      changes_24h: [{ id: 'change-1', title: 'Получен новый отзыв' }],
      completed_results: [{ id: 'result-1', title: 'Подготовлен черновик ответа' }],
    });
    renderPage();

    expect(await screen.findByText('Получен новый отзыв')).toBeInTheDocument();
    expect(screen.getByText('Готово в LocalOS')).toBeInTheDocument();
    expect(screen.getByText('Подготовлен черновик ответа')).toBeInTheDocument();
  });

  it('keeps the target publication when opening a story-facts action', async () => {
    vi.mocked(newAuth.makeRequest).mockResolvedValue({
      focus_action: {
        id: 'content_story_facts:item-1',
        title: 'Добавьте факты для истории',
        reason: 'Для истории не хватает реального эпизода.',
        expected_outcome: 'После фактов LocalOS подготовит текст.',
        cta_label: 'Добавить факты',
        screen: 'content',
        plan_id: 'plan-1',
        item_id: 'item-1',
      },
      active_work: [],
      changes_24h: [],
      completed_results: [],
    });

    render(
      <MemoryRouter initialEntries={['/dashboard/today']}>
        <Routes>
          <Route element={<ContextRoute />}>
            <Route path="/dashboard/today" element={<TodayPage />} />
            <Route path="/dashboard/content" element={<LocationProbe />} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    fireEvent.click(await screen.findByRole('button', { name: 'Добавить факты' }));

    expect(screen.getByText('/dashboard/content?plan_id=plan-1&item_id=item-1&focus=story_facts')).toBeInTheDocument();
  });

  it('opens unanswered reviews with the unanswered filter preserved', async () => {
    vi.mocked(newAuth.makeRequest).mockResolvedValue({
      focus_action: {
        id: 'reviews_unanswered',
        title: 'Ответьте на отзывы без ответа',
        reason: 'Клиенты ждут ответа.',
        expected_outcome: 'Все новые отзывы будут обработаны.',
        cta_label: 'Открыть отзывы без ответа',
        screen: 'reviews',
      },
      active_work: [],
      changes_24h: [],
      completed_results: [],
    });

    render(
      <MemoryRouter initialEntries={['/dashboard/today']}>
        <Routes>
          <Route element={<ContextRoute />}>
            <Route path="/dashboard/today" element={<TodayPage />} />
            <Route path="/dashboard/card" element={<LocationProbe />} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    fireEvent.click(await screen.findByRole('button', { name: 'Открыть отзывы без ответа' }));

    expect(screen.getByText('/dashboard/card?tab=reviews&review_filter=needs_reply')).toBeInTheDocument();
  });

  it('loads the neutral today endpoint for the selected network scope', async () => {
    vi.mocked(newAuth.makeRequest).mockResolvedValue({ active_work: [], changes_24h: [], completed_results: [] });
    render(<MemoryRouter><Routes><Route element={<NetworkContextRoute />}><Route index element={<TodayPage />} /></Route></Routes></MemoryRouter>);
    await screen.findByText('Сейчас у LocalOS нет активных задач.');
    expect(vi.mocked(newAuth.makeRequest)).toHaveBeenCalledWith('/operator/today?scope_type=network&scope_id=network-1', { method: 'GET' });
  });

  it('explains data, results, and the next action without abstract product language', async () => {
    vi.mocked(newAuth.makeRequest).mockResolvedValue({
      focus_action: {
        title: 'Обновите финансовые данные',
        reason: 'Нет финансовых данных для аналитики.',
        expected_outcome: 'LocalOS сможет показать актуальную финансовую картину и точки роста.',
        cta_label: 'Загрузить данные',
      },
      data_rhythm: { coverage: 25, completed_periods_8w: 2 },
      analytics_modules: [{ key: 'trend', label: 'Динамика и доказательные рекомендации', status: 'locked' }],
      active_work: [],
      changes_24h: [],
      completed_results: [{ id: 'result-1', title: 'Контент-план создан', source: 'Прогресс LocalOS' }],
      community_pulse: [{ id: 'pulse-1', title: 'Вопрос из Telegram' }],
      data_health: { status: 'missing', source: 'unknown', missing: ['продажи'] },
    });
    const { container } = renderPage();

    expect(await screen.findByText('Финансовая сводка ещё не загружена.')).toBeInTheDocument();
    expect(screen.getByText('После загрузки здесь появятся выручка, расходы, средний чек и загрузка за выбранный период.')).toBeInTheDocument();
    expect(screen.getByText('Данные за последние 8 недель')).toBeInTheDocument();
    expect(screen.getByText('Данные за последние 8 недель').closest('details')).not.toHaveAttribute('open');
    expect(screen.getByText('Сравнение показателей по неделям: загрузите сводку')).toBeInTheDocument();
    expect(screen.getByText('Готово в LocalOS')).toBeInTheDocument();
    expect(screen.getByText('Готово в LocalOS').closest('details')).not.toHaveAttribute('open');
    expect(screen.getByText('Источник: история выполненных задач')).toBeInTheDocument();
    expect(screen.getByText('Что обсуждают в ваших источниках')).toBeInTheDocument();
    expect(screen.getByText('Источник финансовых данных:', { exact: false })).toBeInTheDocument();
    expect(screen.getByText('не указан', { exact: false })).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/выбранного контура|ритм данных|финансовую картину|точки роста|доказательные рекомендации|пульс сообщества|путь роста/i);
  });
});
