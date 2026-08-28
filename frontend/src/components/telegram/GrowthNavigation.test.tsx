import '@testing-library/jest-dom/vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import GrowthNavigation from './GrowthNavigation';

const navigation = [
  { key: 'progress', label: 'Прогресс', status: 'available' },
  { key: 'cards', label: 'Карточки', status: 'available' },
  { key: 'reviews', label: 'Отзывы', status: 'available' },
  { key: 'content', label: 'Контент', status: 'available' },
  { key: 'finance', label: 'Финансы', status: 'available' },
  { key: 'services', label: 'Услуги', status: 'available' },
  { key: 'agents', label: 'ИИ-агенты', status: 'available' },
  { key: 'settings', label: 'Настройки', status: 'read_only', reason: 'Доступны уведомления' },
] satisfies Parameters<typeof GrowthNavigation>[0]['navigation'];

describe('GrowthNavigation', () => {
  it('organizes modules around business outcomes and preserves fast actions', async () => {
    const user = userEvent.setup();
    const open = vi.fn();
    const openProgress = vi.fn();
    render(<GrowthNavigation navigation={navigation} onOpen={open} onOpenProgress={openProgress} onLocked={vi.fn()} onRestartTour={vi.fn()} />);

    expect(screen.getByText('Больше клиентов из карт')).toBeInTheDocument();
    expect(screen.getByText('Контент без рутины')).toBeInTheDocument();
    expect(screen.getByText('Больше выручки')).toBeInTheDocument();
    expect(screen.getByText('Автоматизировать работу')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /Ответить на отзывы/ }));
    expect(open).toHaveBeenCalledWith('reviews');
    await user.click(screen.getByRole('button', { name: /Открыть план роста/ }));
    expect(openProgress).toHaveBeenCalledTimes(1);
  });

  it('routes an unpaid module to the payment gate instead of opening it', async () => {
    const user = userEvent.setup();
    const open = vi.fn();
    const locked = vi.fn();
    const unpaidNavigation: Parameters<typeof GrowthNavigation>[0]['navigation'] = navigation.map((item) => item.key === 'content'
      ? { ...item, status: 'read_only', reason: 'Раздел доступен после оплаты тарифа.' }
      : item);

    render(<GrowthNavigation navigation={unpaidNavigation} onOpen={open} onOpenProgress={vi.fn()} onLocked={locked} onRestartTour={vi.fn()} />);

    await user.click(screen.getByRole('button', { name: /Контент без рутины/ }));
    expect(open).not.toHaveBeenCalled();
    expect(locked).toHaveBeenCalledWith(expect.objectContaining({ key: 'content', status: 'read_only' }));
  });
});
