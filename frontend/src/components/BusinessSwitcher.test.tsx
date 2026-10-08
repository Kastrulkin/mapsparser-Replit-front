import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { BusinessSwitcher } from './BusinessSwitcher';

describe('BusinessSwitcher', () => {
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
