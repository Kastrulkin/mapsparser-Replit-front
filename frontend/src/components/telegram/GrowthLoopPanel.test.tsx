import '@testing-library/jest-dom/vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { GrowthLoopPanel } from './GrowthLoopPanel';

describe('GrowthLoopPanel', () => {
  it('shows data freshness, cadence and a single import action when analytics are locked', async () => {
    const onOpenImport = vi.fn();
    render(<GrowthLoopPanel dataHealth={{ status: 'stale', age_days: 19 }} growthLoop={{ analytics_level: { label: 'Нужны данные', next_unlock: 'Загрузите свежую сводку.' }, rhythm: { label: 'Ритм формируется', active_weeks: 1 } }} onOpenImport={onOpenImport} />);

    expect(screen.getByText('Нужна свежая сводка')).toBeVisible();
    expect(screen.getByText('История собирается')).toBeVisible();
    expect(screen.getByText('Расчёты нужно обновить')).toBeVisible();
    await userEvent.click(screen.getByRole('button', { name: 'Загрузить финансовую сводку' }));
    expect(onOpenImport).toHaveBeenCalledOnce();
  });

  it('does not add another action once data is fresh', () => {
    render(<GrowthLoopPanel dataHealth={{ status: 'fresh', age_days: 1 }} growthLoop={{ analytics_level: { label: 'Готово к решениям' }, rhythm: { label: 'Регулярный ритм', active_weeks: 4 } }} onOpenImport={vi.fn()} />);

    expect(screen.getByText('Данные актуальны')).toBeVisible();
    expect(screen.queryByRole('button', { name: 'Загрузить финансовую сводку' })).not.toBeInTheDocument();
  });

  it('does not duplicate the import action when it is already the main mission', () => {
    render(<GrowthLoopPanel dataHealth={{ status: 'missing' }} showImportAction={false} onOpenImport={vi.fn()} />);

    expect(screen.getByText('Сводок пока нет')).toBeVisible();
    expect(screen.queryByRole('button', { name: 'Загрузить финансовую сводку' })).not.toBeInTheDocument();
  });

  it('shows at most five problem locations with their rhythm and analytics unlock', async () => {
    const onOpenLocation = vi.fn();
    const locations = Array.from({ length: 6 }, (_, index) => ({
      business_id: `business-${index + 1}`,
      business_name: `Точка ${index + 1}`,
      data_health: { status: index === 0 ? 'missing' : 'stale' },
      rhythm: { label: index === 0 ? 'Ритм ещё не начат' : 'Ритм формируется' },
      analytics_level: { label: 'Нужны данные', next_unlock: 'Загрузите свежую сводку.' },
    }));
    render(<GrowthLoopPanel scopeKind="network" dataHealth={{ status: 'missing' }} networkSummary={{ locations_count: 6, problem_locations_count: 6, healthy_locations_count: 0, finance: { total: 6, fresh: 0, due: 0, stale: 5, missing: 1 } }} problemLocations={locations.map((location) => ({ business_id: location.business_id, business_name: location.business_name, data_health_status: location.data_health.status, target_scope: { kind: 'business', id: location.business_id } }))} locationBreakdown={locations} analyticsModules={[{ key: 'sales', label: 'Продажи и средний чек', status: 'available' }, { key: 'services', label: 'Услуги и допродажи', status: 'locked', next_unlock: 'Добавьте данные: услуги и допродажи.' }]} onOpenImport={vi.fn()} onOpenLocation={onOpenLocation} />);

    expect(screen.getByText('Данные по точкам')).toBeVisible();
    expect(screen.getByText('6 точек')).toBeVisible();
    expect(screen.getAllByText('Добавьте первую недельную сводку.').length).toBeGreaterThan(0);
    expect(screen.getByText('Продажи и средний чек')).toBeVisible();
    expect(screen.getByText('Обновите сводку')).toBeVisible();
    expect(screen.queryByText('Точка 6')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Загрузить финансовую сводку' })).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: /Точка 1/ }));
    expect(onOpenLocation).toHaveBeenCalledWith('business-1', 'finance_import');
  });

  it('opens a card problem in cards instead of the finance import', async () => {
    const onOpenLocation = vi.fn();
    render(<GrowthLoopPanel scopeKind="network" dataHealth={{ status: 'fresh' }} networkSummary={{ locations_count: 2 }} problemLocations={[{ business_id: 'business-2', business_name: 'Север', data_health_status: 'fresh', problem_areas: ['maps'], focus_action: { cta_url: '/dashboard/card' }, target_scope: { kind: 'business', id: 'business-2' } }]} locationBreakdown={[{ business_id: 'business-2', business_name: 'Север', data_health: { status: 'fresh' } }]} onOpenImport={vi.fn()} onOpenLocation={onOpenLocation} />);

    await userEvent.click(screen.getByRole('button', { name: /Север/ }));
    expect(onOpenLocation).toHaveBeenCalledWith('business-2', 'cards');
  });
});
