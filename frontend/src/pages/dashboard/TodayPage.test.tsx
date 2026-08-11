import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Outlet, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { newAuth } from '@/lib/auth_new';
import { TodayPage } from './TodayPage';

vi.mock('@/lib/auth_new', () => ({ newAuth: { makeRequest: vi.fn() } }));

const ContextRoute = () => <Outlet context={{ currentBusinessId: 'business-1' }} />;
const NetworkContextRoute = () => <Outlet context={{ currentBusinessId: 'business-1', controlScope: { kind: 'network', id: 'network-1', name: 'Сеть' } }} />;
const renderPage = () => render(<MemoryRouter><Routes><Route element={<ContextRoute />}><Route index element={<TodayPage />} /></Route></Routes></MemoryRouter>);

describe('TodayPage', () => {
  beforeEach(() => vi.mocked(newAuth.makeRequest).mockReset());

  it('keeps a loading state until the operational summary is available', async () => {
    let resolveRequest: (value: unknown) => void = () => undefined;
    vi.mocked(newAuth.makeRequest).mockReturnValue(new Promise((resolve) => { resolveRequest = resolve; }));
    renderPage();
    expect(screen.getByText('Загружаем новые события и текущие задачи.')).toBeInTheDocument();
    resolveRequest({ active_work: [], changes_24h: [], completed_results: [] });
    await screen.findByText('Что изменилось');
  });

  it('shows an evidence-led empty state without inventing changes or active work', async () => {
    vi.mocked(newAuth.makeRequest).mockResolvedValue({ active_work: [], changes_24h: [], completed_results: [] });
    renderPage();
    expect(await screen.findByText('За последние 24 часа новых отзывов, продаж и других подтверждённых событий не найдено.')).toBeInTheDocument();
    expect(screen.getByText('Сейчас у LocalOS нет активных задач.')).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: 'Открыть прогресс' })).toHaveLength(2);
  });

  it('uses a single-column-first responsive layout for narrow screens', async () => {
    vi.mocked(newAuth.makeRequest).mockResolvedValue({ active_work: [], changes_24h: [], completed_results: [] });
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

  it('loads the neutral today endpoint for the selected network scope', async () => {
    vi.mocked(newAuth.makeRequest).mockResolvedValue({ active_work: [], changes_24h: [], completed_results: [] });
    render(<MemoryRouter><Routes><Route element={<NetworkContextRoute />}><Route index element={<TodayPage />} /></Route></Routes></MemoryRouter>);
    await screen.findByText('Что изменилось');
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
      completed_results: [{ id: 'result-1', title: 'Контент-план создан' }],
      community_pulse: [{ id: 'pulse-1', title: 'Вопрос из Telegram' }],
      data_health: { status: 'missing', source: 'unknown', missing: ['продажи'] },
    });
    const { container } = renderPage();

    expect(await screen.findByText('Финансовая сводка ещё не загружена.')).toBeInTheDocument();
    expect(screen.getByText('После загрузки здесь появятся выручка, расходы, средний чек и загрузка за выбранный период.')).toBeInTheDocument();
    expect(screen.getByText('Данные за последние 8 недель')).toBeInTheDocument();
    expect(screen.getByText('Сравнение показателей по неделям: загрузите сводку')).toBeInTheDocument();
    expect(screen.getByText('Готово в LocalOS')).toBeInTheDocument();
    expect(screen.getByText('Что обсуждают в ваших источниках')).toBeInTheDocument();
    expect(screen.getByText('не указан', { exact: false })).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/выбранного контура|ритм данных|финансовую картину|точки роста|доказательные рекомендации|пульс сообщества|путь роста/i);
  });
});
