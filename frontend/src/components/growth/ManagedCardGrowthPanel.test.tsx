import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { newAuth } from '@/lib/auth_new';
import { ManagedCardGrowthPanel, type ManagedCardGrowth } from './ManagedCardGrowthPanel';

vi.mock('@/lib/auth_new', () => ({
  newAuth: { makeRequest: vi.fn() },
}));

const growth: ManagedCardGrowth = {
  policy_version: '2026-09-11.1',
  goal: {
    value: 'bookings',
    label: 'Больше записей',
    status: 'recommended',
    options: [
      { value: 'bookings', label: 'Больше записей' },
      { value: 'inquiries', label: 'Больше обращений' },
    ],
  },
  card_state: {
    status: 'needs_attention',
    locations: [{
      business_id: 'business-1',
      business_name: 'Тестовая точка',
      critical: true,
      providers: [{
        provider: 'yandex',
        provider_label: 'Яндекс',
        source_state: 'observed',
        observed_at: '2026-09-11T08:00:00+00:00',
        facts: {
          category: { state: 'missing' },
          publications: { state: 'unknown' },
        },
        benchmark: { sample_size: 12, period_days: 90 },
      }],
    }],
  },
  measurement: { status: 'goal_not_confirmed', checkpoints: [] },
  next_actions: [{ id: 'next-1', title: 'Проверить путь записи', business_name: 'Тестовая точка', gate_label: 'Можно обратиться' }],
};

describe('ManagedCardGrowthPanel', () => {
  it('distinguishes missing and unknown evidence', async () => {
    render(<ManagedCardGrowthPanel businessId="business-1" growth={growth} onUpdated={vi.fn()} />);

    await userEvent.click(screen.getByText('Яндекс'));

    expect(screen.getByText('Нужно заполнить')).toBeInTheDocument();
    expect(screen.getByText('Нет данных')).toBeInTheDocument();
    expect(screen.getByText(/12 сопоставимых компаний/)).toBeInTheDocument();
  });

  it('confirms the recommended goal', async () => {
    vi.mocked(newAuth.makeRequest).mockResolvedValue({ success: true });
    const onUpdated = vi.fn();
    render(<ManagedCardGrowthPanel businessId="business-1" growth={growth} onUpdated={onUpdated} />);

    await userEvent.click(screen.getByRole('button', { name: 'Подтвердить цель' }));

    expect(newAuth.makeRequest).toHaveBeenCalledWith('/business/business-1/growth-goal', {
      method: 'PUT',
      body: JSON.stringify({ goal: 'bookings' }),
    });
    expect(onUpdated).toHaveBeenCalled();
  });
});
