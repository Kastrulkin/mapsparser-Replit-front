import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { describe, expect, it } from 'vitest';

import { CreatorCityCombobox } from './CreatorCityCombobox';

describe('CreatorCityCombobox', () => {
  it('finds the canonical city by alias and typo', async () => {
    const user = userEvent.setup();
    const cities = ['Санкт-Петербург', 'Москва', 'Таллинн'];
    const TestHost = () => { const [city, setCity] = useState(''); return <CreatorCityCombobox value={city} options={cities} onChange={setCity} />; };
    const view = render(<TestHost />);

    const input = screen.getByRole('combobox', { name: 'Город' });
    await user.type(input, 'спб');
    await user.click(screen.getByRole('option', { name: 'Санкт-Петербург' }));
    expect(input).toHaveValue('Санкт-Петербург');

    view.rerender(<CreatorCityCombobox value="петебург" options={cities} onChange={() => undefined} />);
    await user.click(screen.getByRole('combobox', { name: 'Город' }));
    expect(screen.getByRole('option', { name: 'Санкт-Петербург' })).toBeVisible();
  });
});
