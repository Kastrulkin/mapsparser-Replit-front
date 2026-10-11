import { useState } from 'react';
import { configure, act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Outlet, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { LanguageProvider } from '@/i18n/LanguageContext';
import { HttpError, newAuth } from '@/lib/auth_new';
import { ProgressPage } from './ProgressPage';
import { progressResultsCopies } from './progressResultsCopy';

// Locale modules load asynchronously; allow cold filesystem reads without weakening assertions.
configure({ asyncUtilTimeout: 10_000 });

vi.mock('@/lib/auth_new', async (importOriginal) => {
  const original = await importOriginal<typeof import('@/lib/auth_new')>();
  return { ...original, newAuth: { makeRequest: vi.fn() } };
});
vi.mock('@/components/CardAuditPanel', () => ({ default: ({ businessId }: { businessId: string }) => <p>Audit evidence: {businessId}</p> }));
vi.mock('@/components/MapParseTable', () => ({ default: () => <p>Card update history</p> }));

const fixture = (name = 'First business') => ({
  summary: { completed_milestones: 3, total_milestones: 7, active_areas: 2, needs_attention: 1, completed_last_30_days: 1, locations_count: 1 },
  focus_action: null,
  data_health: { status: 'missing', source: 'unknown', missing: ['Продажи'] },
  areas: [
    { key: 'maps', label: 'Карты и репутация', status: 'needs_attention', summary: `Map for ${name}`, problem: 'Нужны свежие данные.',
      expected_outcome: 'Появится аудит.', action: { title: 'Обновить карту', reason: '', expected_outcome: '', cta_label: 'Обновить карту', cta_url: '/dashboard/card' },
      progress: { completed: 1, total: 4 }, milestones: [{ key: 'map_audited', label: 'Аудит получен', status: 'next' }], metrics: [] },
    { key: 'content', label: 'Контент', status: 'healthy', summary: 'Готовых материалов: 28, опубликовано: 15', problem: null,
      expected_outcome: '', action: { title: 'Открыть контент', reason: '', expected_outcome: '', cta_label: 'Посмотреть материалы', cta_url: '/dashboard/content' },
      progress: { completed: 2, total: 3 }, milestones: [], metrics: [] },
    { key: 'partnerships', label: 'Партнёры', status: 'unavailable', summary: 'Нет доступа к направлению', problem: 'Доступ ограничен тарифом.',
      expected_outcome: '', action: { title: '', reason: '', expected_outcome: '', cta_label: 'Запустить поиск', cta_url: '/dashboard/partnerships' },
      progress: { completed: 0, total: 4 }, milestones: [], metrics: [] },
  ],
  recent_achievements: [],
  scope: { business_id: 'a', business_name: name, is_network: false, locations: [{ id: 'a', name }] },
  generated_at: '2026-10-09T12:00:00Z',
});

const ContextRoute = () => {
  const [id, setId] = useState('a');
  const [kind, setKind] = useState('business');
  return <>
    <button onClick={() => setId('b')}>Select B</button>
    <button onClick={() => setKind('network')}>Select network</button>
    <Outlet context={{ currentBusinessId: id, controlScope: { kind, id } }} />
  </>;
};
const mount = (url = '/dashboard/progress') => render(<MemoryRouter initialEntries={[url]}><LanguageProvider><Routes>
  <Route path="dashboard" element={<ContextRoute />}>
    <Route path="progress" element={<ProgressPage />} />
    <Route path="content" element={<p>Content destination</p>} />
    <Route path="card" element={<p>Map destination</p>} />
    <Route path="today" element={<p>Today destination</p>} />
  </Route>
</Routes></LanguageProvider></MemoryRouter>);
const request = vi.mocked(newAuth.makeRequest);

beforeEach(() => {
  window.localStorage.clear();
  window.localStorage.setItem('language', 'ru');
  request.mockReset();
  request.mockImplementation((url: string) => Promise.resolve(url.startsWith('/operator/progress?') ? fixture() : { success: true, status: 'idle' }));
  HTMLElement.prototype.scrollIntoView = vi.fn();
});

describe('Results page', () => {
  it('starts with truthful results and closed details while financial data is missing', async () => {
    mount();
    expect(await screen.findByText('Готовых материалов: 28, опубликовано: 15')).toBeVisible();
    expect(screen.getByText('Подтверждено этапов за 30 дней')).toBeVisible();
    expect(screen.queryByText(/задач завершено/)).not.toBeInTheDocument();
    expect(screen.getByText(progressResultsCopies.ru.recentResultsEmpty)).toBeVisible();
    for (const button of screen.getAllByRole('button', { expanded: false })) expect(button).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByRole('button', { name: 'Загрузить файл из CRM' })).not.toBeInTheDocument();
    await userEvent.click(screen.getByText(/^Данные для отчёта/));
    expect(await screen.findByRole('button', { name: 'Загрузить файл из CRM' })).toBeVisible();
    expect(screen.getByText(/Источник: не указан/)).toBeVisible();
  });

  it('supports keyboard disclosure and does not offer an audit before it exists', async () => {
    mount();
    const maps = await screen.findByRole('button', { name: /Карты и репутация/ });
    maps.focus();
    await userEvent.keyboard('{Enter}');
    expect(maps).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByText('Аудит ещё не получен')).toBeVisible();
    expect(screen.queryByRole('button', { name: 'Посмотреть аудит' })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Обновить карту' }));
    expect(screen.getByText('Map destination')).toBeVisible();
  });

  it('opens a ready audit, keeps deep links and focuses the audit section', async () => {
    const ready = fixture();
    ready.areas[0].milestones[0].status = 'done';
    request.mockImplementation((url: string) => Promise.resolve(url.startsWith('/operator/progress?') ? ready : { success: true, status: 'idle' }));
    mount();
    await userEvent.click(await screen.findByRole('button', { name: /Карты и репутация/ }));
    await userEvent.click(screen.getByRole('button', { name: 'Посмотреть аудит' }));
    expect(await screen.findByText('Audit evidence: a')).toBeVisible();
    await waitFor(() => expect(screen.getByRole('region', { name: 'Аудит карточки' })).toHaveFocus());
    await userEvent.click(screen.getByRole('button', { name: 'Скрыть аудит' }));
    expect(screen.queryByText('Audit evidence: a')).not.toBeInTheDocument();
  });

  it('honours a direct audit link even when no milestone has been recorded', async () => {
    mount('/dashboard/progress?section=maps&audit=open');
    expect(await screen.findByText('Audit evidence: a')).toBeVisible();
    expect(screen.getByRole('button', { name: /Карты и репутация/ })).toHaveAttribute('aria-expanded', 'true');
  });

  it('keeps every provided area visible with managed map data, including blocked sources', async () => {
    request.mockImplementation((url: string) => Promise.resolve(url.startsWith('/operator/progress?') ? {
      ...fixture(), card_state: { status: 'needs_attention', locations: [{ business_id: 'a', business_name: 'First business', providers: [{ provider: 'google', source_state: 'blocked', facts: {} }] }] },
    } : { success: true, status: 'idle' }));
    mount();
    expect(await screen.findByRole('button', { name: /Контент/ })).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByRole('heading', { name: 'Цель и состояние карточек' })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /Карты и репутация/ }));
    expect(screen.getByRole('heading', { name: 'Цель и состояние карточек' })).toBeVisible();
    expect(screen.queryByRole('button', { name: 'Обновить карту' })).not.toBeInTheDocument();
    expect(screen.getAllByText(/Нет доступа/).length).toBeGreaterThan(0);
  });

  it('uses employee language for automation without changing the reported counts', async () => {
    const data = fixture();
    data.areas.push({ ...data.areas[1], key: 'automation', label: 'Автоматизация', summary: 'Агентов: 21, работают: 5, выполнено задач: 24' });
    request.mockImplementation((url: string) => Promise.resolve(url.startsWith('/operator/progress?') ? data : { success: true, status: 'idle' }));
    mount();
    expect(await screen.findByText('ИИ-сотрудников: 21, работают: 5, выполнено задач: 24')).toBeVisible();
    expect(screen.queryByText(/^Агентов:/)).not.toBeInTheDocument();
  });

  it('does not attach a financial mission to a synthesized maps area', async () => {
    request.mockImplementation((url: string) => Promise.resolve(url.startsWith('/operator/progress?') ? {
      ...fixture(), areas: [],
      focus_action: { title: 'Обновите финансовые данные', cta_label: 'Загрузить данные', screen: 'finance', reason: '', expected_outcome: '' },
      card_state: { status: 'needs_attention', locations: [] },
    } : { success: true, status: 'idle' }));
    mount();
    await userEvent.click(await screen.findByRole('button', { name: /Карты и отзывы/ }));
    expect(screen.queryByRole('button', { name: 'Загрузить данные' })).not.toBeInTheDocument();
    expect(screen.getByText('Аудит ещё не получен')).toBeVisible();
  });

  it('does not expose a launch action for an unavailable area', async () => {
    mount();
    await userEvent.click(await screen.findByRole('button', { name: /Партнёры/ }));
    expect(screen.getByText('Доступ ограничен тарифом.')).toBeVisible();
    expect(screen.queryByRole('button', { name: 'Запустить поиск' })).not.toBeInTheDocument();
  });

  it('sorts dated milestones newest first, excludes invalid dates and shows no more than eight', async () => {
    const events = Array.from({ length: 10 }, (_, i) => ({ key: `content:event${i}`, area: 'content', title: `Event ${i}`, description: '', occurred_at: `2026-10-${String(i + 1).padStart(2, '0')}T12:00:00Z` }));
    events.push({ key: 'invalid', area: 'content', title: 'Invalid date', description: '', occurred_at: 'unknown' });
    request.mockImplementation((url: string) => Promise.resolve(url.startsWith('/operator/progress?') ? { ...fixture(), recent_achievements: events } : { success: true, status: 'idle' }));
    mount();
    const heading = await screen.findByRole('heading', { name: 'Последние подтверждённые этапы' });
    const section = heading.closest('section');
    if (!section) throw new Error('Missing milestones section');
    const text = section.textContent || '';
    expect(text.indexOf('Event 9')).toBeLessThan(text.indexOf('Event 8'));
    expect(within(section).queryByText('Event 1')).not.toBeInTheDocument();
    expect(within(section).queryByText('Invalid date')).not.toBeInTheDocument();
  });

  it('ignores a delayed response after changing business and resets details', async () => {
    let resolveOld: (data: ReturnType<typeof fixture>) => void = () => {};
    const oldRequest = new Promise<ReturnType<typeof fixture>>((resolve) => { resolveOld = resolve; });
    request.mockImplementation((url: string) => {
      if (!url.startsWith('/operator/progress?')) return Promise.resolve({ success: true, status: 'idle' });
      return url.includes('scope_id=a') ? oldRequest : Promise.resolve(fixture('Second business'));
    });
    mount();
    await userEvent.click(await screen.findByRole('button', { name: 'Select B' }));
    expect(await screen.findByText('Map for Second business')).toBeVisible();
    await act(async () => resolveOld(fixture('Old business')));
    expect(screen.queryByText('Map for Old business')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Карты и репутация/ })).toHaveAttribute('aria-expanded', 'false');
  });

  it('distinguishes business and network scopes even when their ids match', async () => {
    let resolveNetwork: (data: ReturnType<typeof fixture>) => void = () => {};
    const pending = new Promise<ReturnType<typeof fixture>>((resolve) => { resolveNetwork = resolve; });
    request.mockImplementation((url: string) => {
      if (!url.startsWith('/operator/progress?')) return Promise.resolve({ success: true, status: 'idle' });
      return url.includes('scope_type=network') ? pending : Promise.resolve(fixture());
    });
    mount();
    await userEvent.click(await screen.findByRole('button', { name: /Карты и репутация/ }));
    await userEvent.click(screen.getByRole('button', { name: 'Select network' }));
    expect(screen.queryByText('Map for First business')).not.toBeInTheDocument();
    await act(async () => resolveNetwork(fixture('Network')));
    expect(await screen.findByText('Map for Network')).toBeVisible();
    expect(screen.getByRole('button', { name: /Карты и репутация/ })).toHaveAttribute('aria-expanded', 'false');
  });

  it.each([401, 403])('clears previous results on loss of access (%s)', async (status) => {
    mount();
    expect(await screen.findByText('Map for First business')).toBeVisible();
    request.mockImplementation((url: string) => url.startsWith('/operator/progress?') ? Promise.reject(new HttpError('Access denied', status, 'HTTP_ERROR')) : Promise.resolve({ success: true, status: 'idle' }));
    fireEvent.click(screen.getByRole('button', { name: 'Обновить' }));
    expect(await screen.findByText('Access denied')).toBeVisible();
    expect(screen.queryByText('Map for First business')).not.toBeInTheDocument();
    expect(screen.queryByText('Готовых материалов: 28, опубликовано: 15')).not.toBeInTheDocument();
  });

  it('preserves the current results after a transient refresh failure and retries', async () => {
    mount();
    expect(await screen.findByText('Map for First business')).toBeVisible();
    request.mockImplementation((url: string) => url.startsWith('/operator/progress?') ? Promise.reject(new HttpError('Network failure', null, 'NETWORK_ERROR')) : Promise.resolve({ success: true, status: 'idle' }));
    fireEvent.click(screen.getByRole('button', { name: 'Обновить' }));
    expect(await screen.findByText(/Показываем предыдущую сводку/)).toBeVisible();
    expect(screen.getByText('Map for First business')).toBeVisible();
    request.mockImplementation((url: string) => Promise.resolve(url.startsWith('/operator/progress?') ? fixture('Refreshed business') : { success: true, status: 'idle' }));
    fireEvent.click(screen.getByRole('button', { name: 'Повторить' }));
    expect(await screen.findByText('Map for Refreshed business')).toBeVisible();
    expect(screen.queryByText(/Показываем предыдущую сводку/)).not.toBeInTheDocument();
  });

  it('gives an honest start for a new business with no areas', async () => {
    request.mockImplementation((url: string) => Promise.resolve(url.startsWith('/operator/progress?') ? { ...fixture(), areas: [], summary: { completed_milestones: 0, total_milestones: 0, active_areas: 0, needs_attention: 0, completed_last_30_days: 0 } } : { success: true, status: 'idle' }));
    mount();
    expect(await screen.findByText(progressResultsCopies.ru.noAreas)).toBeVisible();
    await userEvent.click(screen.getByRole('button', { name: 'План работы на сегодня' }));
    expect(screen.getByText('Today destination')).toBeVisible();
  });
});
