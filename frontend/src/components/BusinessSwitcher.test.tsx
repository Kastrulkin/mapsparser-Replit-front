import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { BusinessSwitcher } from './BusinessSwitcher';

describe('BusinessSwitcher', () => {
  it('finds a company by name and resets the filter when the menu closes', () => {
    const businesses = Array.from({ length: 8 }, (_, index) => ({ id: String(index), name: `Клиент ${index}` }));
    render(<BusinessSwitcher businesses={businesses} currentBusinessId="0" onBusinessChange={vi.fn()} isSuperadmin />);
    const trigger = screen.getByRole('button', { name: 'Клиент 0' });
    fireEvent.click(trigger);
    const search = screen.getByRole('searchbox', { name: 'Поиск бизнеса' });
    expect(document.activeElement).toBe(search);
    fireEvent.change(search, { target: { value: 'КЛИЕНТ 7' } });
    expect(within(screen.getByRole('listbox')).getAllByRole('option')).toHaveLength(1);
    expect(screen.getByRole('option', { name: 'Клиент 7' })).toBeInTheDocument();
    fireEvent.change(search, { target: { value: 'нет такого клиента' } });
    expect(screen.getByText('Ничего не найдено')).toBeInTheDocument();
    fireEvent.keyDown(search, { key: 'Escape' });
    expect(screen.queryByRole('searchbox')).not.toBeInTheDocument();
    expect(document.activeElement).toBe(trigger);
    fireEvent.click(trigger);
    expect(within(screen.getByRole('listbox')).getAllByRole('option')).toHaveLength(8);
  });

  it('allows switching directly to every location in a business network', async () => {
    const onBusinessChange = vi.fn();
    const businesses = [
      { id: 'riderra-main', name: 'Riderra', network_id: 'riderra-network', network_name: 'Riderra' },
      { id: 'riderra-tallinn', name: 'Riderra (Tallinn)', network_id: 'riderra-network', network_name: 'Riderra', address: 'Tallinn' },
      { id: 'independent', name: 'Another business' },
    ];

    render(
      <BusinessSwitcher
        businesses={businesses}
        currentBusinessId="riderra-main"
        onBusinessChange={onBusinessChange}
        isSuperadmin
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: /Riderra/ }));

    expect(screen.getAllByRole('option')).toHaveLength(3);
    fireEvent.click(screen.getByRole('option', { name: /Riderra \(Tallinn\)/ }));

    expect(onBusinessChange).toHaveBeenCalledWith('riderra-tallinn');
    await waitFor(() => expect(screen.getByRole('button', { name: /Riderra \(Tallinn\)/ })).toBeInTheDocument());
  });
});
