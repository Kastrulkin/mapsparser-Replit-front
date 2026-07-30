import '@testing-library/jest-dom/vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { NetworkScopePicker } from '@/pages/TelegramControlPage';

describe('NetworkScopePicker', () => {
  it('separates the network summary from its locations', async () => {
    const choose = vi.fn();
    render(
      <NetworkScopePicker
        network={{ id: 'network-1', name: 'Весёлая расчёска', locations_count: 2 }}
        currentScope={{ kind: 'network', id: 'network-1', name: 'Весёлая расчёска' }}
        locations={[
          { id: 'business-1', name: 'Весёлая расчёска · Центр', address: 'Невский, 10' },
          { id: 'business-2', name: 'Весёлая расчёска · Север', address: 'Лесная, 4' },
        ]}
        total={2}
        search=""
        setSearch={vi.fn()}
        loading={false}
        choose={choose}
        back={vi.fn()}
        loadMore={vi.fn()}
      />,
    );

    expect(screen.getByRole('button', { name: /Саммари сети/ })).toBeInTheDocument();
    expect(screen.getByText('Невский, 10')).toBeInTheDocument();
    expect(screen.getByText('Лесная, 4')).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: /Весёлая расчёска · Север/ }));
    expect(choose).toHaveBeenCalledWith('business', 'business-2');
  });
});
