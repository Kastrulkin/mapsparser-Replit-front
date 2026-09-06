import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
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

  it.each([false, true])('keeps the chosen direction one click away when only other work exists (urgent=%s)', async (urgent) => {
    const otherWork = { id: 'review-1', title: 'Ответьте на отзыв', flow: 'maps', urgency: urgent ? 'urgent' : 'normal', action: { label: 'Открыть отзыв', url: '/dashboard/card?tab=reviews' } };
    vi.mocked(newAuth.makeRequest).mockResolvedValue({
      preference: { scope_type: 'business', scope_id: 'business-1', primary_flow: 'influencers', suggestions_enabled: true, revision: 1 },
      focus_action: { title: 'Обновите финансовые данные', screen: 'finance' },
      work_sections: { needs_decision: urgent ? [otherWork] : [], continue_work: urgent ? [] : [otherWork], results: [] },
    });
    render(<MemoryRouter initialEntries={['/dashboard/today']}><Routes><Route element={<ContextRoute />}>
      <Route path="/dashboard/today" element={<TodayPage />} />
      <Route path="/dashboard/influencers" element={<LocationProbe />} />
    </Route></Routes></MemoryRouter>);
    const action = await screen.findByRole('button', { name: 'Открыть инфлюенсеров' });
    const titles = screen.getAllByRole('heading').map((heading) => heading.textContent);
    expect(titles[1]).toBe(urgent ? 'Ответьте на отзыв' : 'Продолжите работу с инфлюенсерами');
    fireEvent.click(action);
    expect(screen.getByText('/dashboard/influencers')).toBeInTheDocument();
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

  it('does not say there is no work while a primary decision is on screen', async () => {
    vi.mocked(newAuth.makeRequest).mockResolvedValue({
      work_sections: { needs_decision: [{ id: 'decision-1', title: 'Подтвердите черновик', description: 'Проверьте условия.' }], continue_work: [], results: [] },
      active_work: [], changes_24h: [], completed_results: [],
    });
    renderPage();
    expect(await screen.findByRole('heading', { name: 'Подтвердите черновик' })).toBeInTheDocument();
    expect(screen.queryByText('Сейчас у LocalOS нет активных задач.')).not.toBeInTheDocument();
  });

  it.each([
    ['content', 'Подготовьте следующий материал', 'Открыть контент'],
    ['influencers', 'Продолжите работу с инфлюенсерами', 'Открыть инфлюенсеров'],
    ['automation', 'Проверьте автоматизацию', 'Открыть автоматизацию'],
  ])('gives an empty %s priority a direct next action', async (primaryFlow, title, button) => {
    vi.mocked(newAuth.makeRequest).mockResolvedValue({
      preference: { scope_type: 'business', scope_id: 'business-1', primary_flow: primaryFlow, suggestions_enabled: true, revision: 1 },
      active_work: [], changes_24h: [], completed_results: [],
    });
    renderPage();

    expect(await screen.findByRole('heading', { name: title })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: button })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Открыть прогресс' })).not.toBeInTheDocument();
  });

  it('opens the influencer workspace from its empty-priority action', async () => {
    vi.mocked(newAuth.makeRequest).mockResolvedValue({
      preference: { scope_type: 'business', scope_id: 'business-1', primary_flow: 'influencers', suggestions_enabled: true, revision: 1 },
      active_work: [], changes_24h: [], completed_results: [],
    });
    render(
      <MemoryRouter initialEntries={['/dashboard/today']}>
        <Routes>
          <Route element={<ContextRoute />}>
            <Route path="/dashboard/today" element={<TodayPage />} />
            <Route path="/dashboard/influencers" element={<LocationProbe />} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    fireEvent.click(await screen.findByRole('button', { name: 'Открыть инфлюенсеров' }));
    expect(screen.getByText('/dashboard/influencers')).toBeInTheDocument();
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

  it('does not show an empty generic outcome for an operator task', async () => {
    vi.mocked(newAuth.makeRequest).mockResolvedValue({
      focus_action: {
        id: 'reviews_unanswered',
        title: 'Отзывы без ответа',
        reason: 'Есть новые отзывы.',
        expected_outcome: '',
        cta_label: 'Открыть задачу',
        screen: 'reviews',
      },
      active_work: [],
      changes_24h: [],
      completed_results: [],
    });

    renderPage();

    expect(await screen.findByRole('heading', { name: 'Отзывы без ответа' })).toBeInTheDocument();
    expect(screen.queryByText('После этого:')).not.toBeInTheDocument();
  });

  it('puts an urgent decision ahead of a finance focus and does not duplicate it below', async () => {
    vi.mocked(newAuth.makeRequest).mockResolvedValue({
      focus_action: { title: 'Обновите финансовые данные', reason: 'Нет сводки', cta_label: 'Загрузить данные', screen: 'finance' },
      work_sections: { needs_decision: [{ id: 'urgent-1', title: 'Подтвердите ответ клиенту', description: 'Сообщение ждёт решения', urgency: 'urgent', action: { label: 'Проверить', url: '/dashboard/card?review=1' } }], continue_work: [], results: [] },
      active_work: [], changes_24h: [], completed_results: [],
    });
    renderPage();
    expect(await screen.findByRole('heading', { name: 'Подтвердите ответ клиенту' })).toBeInTheDocument();
    expect(screen.getAllByText('Подтвердите ответ клиенту')).toHaveLength(1);
  });

  it('keeps preference controls behind settings and sends the scoped revision', async () => {
    vi.mocked(newAuth.makeRequest)
      .mockResolvedValueOnce({ preference: { scope_type: 'business', scope_id: 'business-1', primary_flow: 'overview', suggestions_enabled: true, revision: 4, available_flows: ['overview', 'content'] }, active_work: [], changes_24h: [], completed_results: [] })
      .mockResolvedValueOnce({ preference: { scope_type: 'business', scope_id: 'business-1', primary_flow: 'content', suggestions_enabled: true, revision: 5 } });
    renderPage();
    expect(await screen.findByText('Что показывать первым на «Сегодня»: Обзор')).toBeInTheDocument();
    expect(screen.getByText('Что показывать первым на «Сегодня»: Обзор').closest('details')).not.toHaveAttribute('open');
    fireEvent.click(screen.getByText('Что показывать первым на «Сегодня»: Обзор'));
    fireEvent.click(screen.getByRole('button', { name: 'Контент' }));
    await waitFor(() => expect(vi.mocked(newAuth.makeRequest)).toHaveBeenLastCalledWith('/operator/today/preference?scope_type=business&scope_id=business-1', { method: 'POST', body: JSON.stringify({ action: 'set', expected_revision: 4, primary_flow: 'content' }) }));
  });

  it('clears a previously loaded overview when the current scope becomes unavailable', async () => {
    const forbidden = Object.assign(new Error('Доступ отозван'), { status: 403 });
    vi.mocked(newAuth.makeRequest)
      .mockResolvedValueOnce({ active_work: [{ id: 'private-work', title: 'Закрытая задача' }], changes_24h: [], completed_results: [] })
      .mockRejectedValueOnce(forbidden);
    renderPage();

    expect(await screen.findByText('Закрытая задача')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Обновить' }));

    expect(await screen.findByText('Страница временно недоступна')).toBeInTheDocument();
    expect(screen.queryByText('Закрытая задача')).not.toBeInTheDocument();
  });

  it('keeps a confirmed overview visible after a transient refresh failure', async () => {
    const unavailable = Object.assign(new Error('Сервис временно недоступен'), { status: 503 });
    vi.mocked(newAuth.makeRequest)
      .mockResolvedValueOnce({ active_work: [{ id: 'work-1', title: 'Продолжить контент' }], changes_24h: [], completed_results: [] })
      .mockRejectedValueOnce(unavailable);
    renderPage();

    expect(await screen.findByText('Продолжить контент')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Обновить' }));

    expect(await screen.findByRole('status')).toHaveTextContent('Попробуйте ещё раз');
    expect(screen.getByText('Продолжить контент')).toBeInTheDocument();
  });

  it('refreshes scoped work after a priority choice while urgent work remains first', async () => {
    vi.mocked(newAuth.makeRequest)
      .mockResolvedValueOnce({
        preference: { scope_type: 'business', scope_id: 'business-1', primary_flow: 'content', suggestions_enabled: true, revision: 4, available_flows: ['content', 'influencers'] },
        work_sections: {
          needs_decision: [{ id: 'urgent-1', title: 'Подтвердите договор', urgency: 'urgent' }],
          continue_work: [{ id: 'content-1', title: 'Продолжить контент' }],
          results: [],
        },
        changes_24h: [], completed_results: [],
      })
      .mockResolvedValueOnce({ preference: { scope_type: 'business', scope_id: 'business-1', primary_flow: 'influencers', suggestions_enabled: true, revision: 5 } })
      .mockResolvedValueOnce({
        preference: { scope_type: 'business', scope_id: 'business-1', primary_flow: 'influencers', suggestions_enabled: true, revision: 5, available_flows: ['content', 'influencers'] },
        work_sections: {
          needs_decision: [{ id: 'urgent-1', title: 'Подтвердите договор', urgency: 'urgent' }],
          continue_work: [{ id: 'influencer-1', title: 'Согласуйте инфлюенсера' }],
          results: [],
        },
        changes_24h: [], completed_results: [],
      });
    renderPage();

    expect(await screen.findByRole('heading', { name: 'Подтвердите договор' })).toBeInTheDocument();
    fireEvent.click(screen.getByText('Что показывать первым на «Сегодня»: Контент'));
    fireEvent.click(screen.getByRole('button', { name: 'Инфлюенсеры' }));

    expect(await screen.findByText('Согласуйте инфлюенсера')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Подтвердите договор' })).toBeInTheDocument();
    expect(screen.queryByText('Продолжить контент')).not.toBeInTheDocument();
  });

  it('removes a proposal when the preference response explicitly returns null', async () => {
    vi.mocked(newAuth.makeRequest)
      .mockResolvedValueOnce({
        preference: { scope_type: 'business', scope_id: 'business-1', primary_flow: 'content', suggestions_enabled: true, revision: 4 },
        priority_proposal: { id: 'proposal-1', flow: 'influencers', active_days: 3, confirmed_actions: 5, reason_code: 'activity_shift' },
        active_work: [], changes_24h: [], completed_results: [],
      })
      .mockResolvedValueOnce({
        preference: { scope_type: 'business', scope_id: 'business-1', primary_flow: 'content', suggestions_enabled: true, revision: 5 },
        priority_proposal: null,
      })
      .mockResolvedValueOnce({
        preference: { scope_type: 'business', scope_id: 'business-1', primary_flow: 'content', suggestions_enabled: true, revision: 5 },
        priority_proposal: null,
        active_work: [], changes_24h: [], completed_results: [],
      });
    renderPage();

    expect(await screen.findByText(/Вы стали чаще работать с/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Не сейчас' }));

    await waitFor(() => expect(screen.queryByText(/Вы стали чаще работать с/)).not.toBeInTheDocument());
  });

  it('does not let a late response from the previous scope overwrite the selected business', async () => {
    let resolveFirst = (_value: unknown) => undefined;
    let resolveSecond = (_value: unknown) => undefined;
    const firstRequest = new Promise((resolve) => { resolveFirst = resolve; });
    const secondRequest = new Promise((resolve) => { resolveSecond = resolve; });
    vi.mocked(newAuth.makeRequest)
      .mockImplementationOnce(() => firstRequest)
      .mockImplementationOnce(() => secondRequest);
    const page = (businessId: string) => (
      <MemoryRouter>
        <Routes>
          <Route element={<Outlet context={{ currentBusinessId: businessId }} />}>
            <Route index element={<TodayPage />} />
          </Route>
        </Routes>
      </MemoryRouter>
    );
    const view = render(page('business-1'));
    await waitFor(() => expect(vi.mocked(newAuth.makeRequest)).toHaveBeenCalledTimes(1));
    view.rerender(page('business-2'));
    await waitFor(() => expect(vi.mocked(newAuth.makeRequest)).toHaveBeenCalledTimes(2));

    await act(async () => { resolveSecond({ active_work: [{ id: 'second-work', title: 'Задача второго бизнеса' }], changes_24h: [], completed_results: [] }); });
    expect(await screen.findByText('Задача второго бизнеса')).toBeInTheDocument();
    await act(async () => { resolveFirst({ active_work: [{ id: 'first-work', title: 'Закрытая задача первого бизнеса' }], changes_24h: [], completed_results: [] }); });

    expect(screen.getByText('Задача второго бизнеса')).toBeInTheDocument();
    expect(screen.queryByText('Закрытая задача первого бизнеса')).not.toBeInTheDocument();
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
