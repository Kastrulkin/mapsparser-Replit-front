import '@testing-library/jest-dom/vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { TodayMobileV2 } from './TodayMobileV2';

describe('TodayMobileV2', () => {
  it('keeps the ЛокалОС assignment field visible in Russian', () => {
    render(
      <TodayMobileV2
        data={{ scope: { kind: 'business', id: 'business-1', name: 'Тестовый бизнес' } }}
        loading={false}
        slowLoading={false}
        command=""
        setCommand={vi.fn()}
        ask={vi.fn()}
        openTarget={vi.fn()}
        openProgress={vi.fn()}
        track={vi.fn()}
      />,
    );

    expect(screen.getByRole('heading', { name: 'Поручить ЛокалОС' })).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Например: подготовь ответы')).toBeVisible();
    expect(screen.queryByRole('button', { name: 'Поручить ЛокалОС' })).not.toBeInTheDocument();
  });

  it('opens a network card problem directly in the card screen for that location', async () => {
    const openTarget = vi.fn();
    render(
      <TodayMobileV2
        data={{
          scope: { kind: 'network', id: 'network-1', name: 'Сеть салонов' },
          focus_action: { title: 'Обновить данные сети', reason: 'Одна точка отстаёт', screen: 'finance' },
          data_health: { status: 'stale' },
          network_summary: { locations_count: 2, healthy_locations_count: 1, problem_locations_count: 1, finance: { total: 2, fresh: 1, stale: 1, due: 0, missing: 0 } },
          problem_locations: [{ business_id: 'business-2', business_name: 'Север', data_health_status: 'stale', problem_areas: ['maps'], focus_action: { cta_url: '/dashboard/card' }, target_scope: { kind: 'business', id: 'business-2' } }],
          location_breakdown: [{ business_id: 'business-2', business_name: 'Север', data_health: { status: 'stale' }, rhythm: { label: 'Ритм формируется' }, analytics_level: { label: 'Нужны данные', next_unlock: 'Загрузите свежую сводку.' } }],
          analytics_modules: [{ key: 'sales', label: 'Продажи и средний чек', status: 'locked', next_unlock: 'Добавьте данные: продажи и средний чек.' }],
        }}
        loading={false}
        slowLoading={false}
        command=""
        setCommand={vi.fn()}
        ask={vi.fn()}
        openTarget={openTarget}
        openProgress={vi.fn()}
        track={vi.fn()}
      />,
    );

    expect(screen.getByText('Что сделать сейчас')).toBeInTheDocument();
    expect(screen.getByText('Данные по точкам')).toBeVisible();
    await userEvent.click(screen.getByRole('button', { name: /Север/ }));
    expect(openTarget).toHaveBeenCalledWith('cards', { kind: 'business', id: 'business-2' });
  });

  it('uses natural Russian declension for community message counts', () => {
    render(
      <TodayMobileV2
        data={{
          scope: { kind: 'business', id: 'business-1', name: 'Салон' },
          community_pulse: [{ id: 'topic-1', title: 'Рост цен', summary: 'Обсуждают новых поставщиков.', source_name: 'Beauty Owners', message_count: 21 }],
        }}
        loading={false}
        slowLoading={false}
        command=""
        setCommand={vi.fn()}
        ask={vi.fn()}
        openTarget={vi.fn()}
        openProgress={vi.fn()}
        track={vi.fn()}
      />,
    );

    expect(screen.getByText(/21 сообщение/)).toBeInTheDocument();
    expect(screen.queryByText(/21 сообщений/)).not.toBeInTheDocument();
  });

  it('shows a useful business history reminder and opens the right business', async () => {
    const openTarget = vi.fn();
    render(
      <TodayMobileV2
        data={{
          scope: { kind: 'business', id: 'business-1', name: 'Органика' },
          profile_reminders: [{
            id: 'business-history:business-1',
            title: 'Расскажите о бизнесе',
            description: 'ЛокалОС будет точнее готовить контент и предложения партнёрам.',
            screen: 'partnerships',
            target_scope: { kind: 'business', id: 'business-1' },
          }],
        }}
        loading={false}
        slowLoading={false}
        command=""
        setCommand={vi.fn()}
        ask={vi.fn()}
        openTarget={openTarget}
        openProgress={vi.fn()}
        track={vi.fn()}
      />,
    );

    expect(screen.getByRole('heading', { name: 'Сделайте ЛокалОС точнее' })).toBeVisible();
    await userEvent.click(screen.getByRole('button', { name: /Расскажите о бизнесе/ }));
    expect(openTarget).toHaveBeenCalledWith('partnerships', { kind: 'business', id: 'business-1' });
  });
});
