import '@testing-library/jest-dom/vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { ProgressMobileModule } from './ProgressMobileModule';

describe('ProgressMobileModule network scope', () => {
  it('shows the network summary and opens a problem location in business scope', async () => {
    const openTarget = vi.fn();
    render(<ProgressMobileModule
      data={{
        status: 'available',
        scope: { kind: 'network', id: 'network-1', name: 'Сеть салонов' },
        summary: { completed_milestones: 5, total_milestones: 10, percent: 50, locations_count: 3 },
        data_health: { status: 'missing' },
        network_summary: { locations_count: 3, healthy_locations_count: 2, problem_locations_count: 1, finance: { total: 3, fresh: 2, due: 0, stale: 0, missing: 1 } },
        problem_locations: [{ business_id: 'business-3', business_name: 'Запад', data_health_status: 'missing', problem_areas: ['upsells'], focus_action: { cta_url: '/dashboard/average-ticket' }, target_scope: { kind: 'business', id: 'business-3' } }],
        location_breakdown: [{ business_id: 'business-3', business_name: 'Запад', data_health: { status: 'missing' }, rhythm: { label: 'Ритм ещё не начат' }, analytics_level: { label: 'Нужны данные', next_unlock: 'Загрузите первую финансовую сводку.' } }],
        analytics_modules: [{ key: 'sales', label: 'Продажи и средний чек', status: 'locked', next_unlock: 'Добавьте данные: продажи и средний чек.' }],
        areas: [],
      }}
      loading={false}
      openTarget={openTarget}
      track={vi.fn()}
    />);

    expect(screen.getByText('Общий путь сети')).toBeVisible();
    expect(screen.getByRole('heading', { name: 'Все точки — в одной картине' })).toBeVisible();
    expect(screen.getAllByText(/3 точек/)).toHaveLength(2);
    await userEvent.click(screen.getByRole('button', { name: /Запад/ }));
    expect(openTarget).toHaveBeenCalledWith('finance', { kind: 'business', id: 'business-3' });
  });
});
