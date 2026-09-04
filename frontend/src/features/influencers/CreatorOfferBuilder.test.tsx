import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { CreatorOfferBuilder } from './CreatorOfferBuilder';


describe('CreatorOfferBuilder', () => {
  it('explains mass distribution and requires a recipient preview before submission', () => {
    render(<CreatorOfferBuilder businessId="business-1" businessCity="Санкт-Петербург" onSubmitted={vi.fn()} />);

    expect(screen.getByRole('heading', { name: 'Что получит автор и какой результат вы ждёте?' })).toBeInTheDocument();
    expect(screen.getByText(/Shortlist влияет на приоритет, но не ограничивает охват/)).toBeInTheDocument();
    expect(screen.getByLabelText('Город')).toHaveValue('Санкт-Петербург');
    expect(screen.getByLabelText('Только бартер')).toBeChecked();
    expect(screen.getByLabelText('Способ учёта')).toHaveValue('promo_code');
    expect(screen.getByLabelText('Целевое количество')).toHaveValue(3);
    expect(screen.getByRole('button', { name: 'Передать LocalOS' })).toBeDisabled();
  });
});
