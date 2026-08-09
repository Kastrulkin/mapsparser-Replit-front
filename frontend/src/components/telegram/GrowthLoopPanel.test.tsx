import '@testing-library/jest-dom/vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { GrowthLoopPanel } from './GrowthLoopPanel';

describe('GrowthLoopPanel', () => {
  it('shows data freshness, cadence and a single import action when analytics are locked', async () => {
    const onOpenImport = vi.fn();
    render(<GrowthLoopPanel dataHealth={{ status: 'stale', age_days: 19 }} growthLoop={{ analytics_level: { label: 'Нужны данные', next_unlock: 'Загрузите свежую сводку.' }, rhythm: { label: 'Ритм формируется', active_weeks: 1 } }} onOpenImport={onOpenImport} />);

    expect(screen.getByText('Данные устарели')).toBeVisible();
    expect(screen.getByText('Ритм формируется')).toBeVisible();
    expect(screen.getByText('Нужны данные')).toBeVisible();
    await userEvent.click(screen.getByRole('button', { name: 'Загрузить финансовую сводку' }));
    expect(onOpenImport).toHaveBeenCalledOnce();
  });

  it('does not add another action once data is fresh', () => {
    render(<GrowthLoopPanel dataHealth={{ status: 'fresh', age_days: 1 }} growthLoop={{ analytics_level: { label: 'Готово к решениям' }, rhythm: { label: 'Регулярный ритм', active_weeks: 4 } }} onOpenImport={vi.fn()} />);

    expect(screen.getByText('Данные свежие')).toBeVisible();
    expect(screen.queryByRole('button', { name: 'Загрузить финансовую сводку' })).not.toBeInTheDocument();
  });

  it('does not duplicate the import action when it is already the main mission', () => {
    render(<GrowthLoopPanel dataHealth={{ status: 'missing' }} showImportAction={false} onOpenImport={vi.fn()} />);

    expect(screen.getByText('Данных пока нет')).toBeVisible();
    expect(screen.queryByRole('button', { name: 'Загрузить финансовую сводку' })).not.toBeInTheDocument();
  });
});
