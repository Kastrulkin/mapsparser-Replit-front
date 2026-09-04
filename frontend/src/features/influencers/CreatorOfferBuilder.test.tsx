import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { CreatorOfferBuilder } from './CreatorOfferBuilder';


describe('CreatorOfferBuilder', () => {
  it('explains mass distribution and requires a recipient preview before submission', () => {
    render(<CreatorOfferBuilder businessId="business-1" businessCity="Санкт-Петербург" onSubmitted={vi.fn()} />);

    expect(screen.getByRole('heading', { name: 'Что получит автор и за что?' })).toBeInTheDocument();
    expect(screen.getByText(/Отметка «Подходит» влияет на приоритет/)).toBeInTheDocument();
    expect(screen.getByLabelText('Город')).toHaveValue('Санкт-Петербург');
    expect(screen.getByRole('button', { name: 'Услугу' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: 'За результат' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByLabelText('Способ учёта')).toHaveValue('promo_code');
    expect(screen.getByLabelText('Целевое количество')).toHaveValue(3);
    expect(screen.getByRole('button', { name: 'Передать LocalOS' })).toBeDisabled();
  });

  it('supports money for a fixed number of publications', async () => {
    render(<CreatorOfferBuilder businessId="business-1" businessCity="Санкт-Петербург" onSubmitted={vi.fn()} />);
    const user = userEvent.setup();

    await user.click(screen.getByRole('button', { name: 'Деньги' }));
    await user.click(screen.getByRole('button', { name: 'За публикации' }));

    expect(screen.getByLabelText('Сумма')).toBeInTheDocument();
    expect(screen.getByLabelText('Валюта')).toHaveValue('RUB');
    expect(screen.getByLabelText('Сколько публикаций нужно')).toHaveValue(1);
    expect(screen.queryByLabelText('Способ учёта')).not.toBeInTheDocument();
    expect(screen.getByText(/количеству проверенных публикаций/)).toBeInTheDocument();
  });
});
