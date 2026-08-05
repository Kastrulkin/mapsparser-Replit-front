import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { OutreachDateTimePicker } from './OutreachDateTimePicker';

describe('OutreachDateTimePicker', () => {
  it('keeps a selected outside-month day visually prominent', async () => {
    const user = userEvent.setup();

    render(
      <OutreachDateTimePicker
        value="2026-07-30T18:30"
        onChange={vi.fn()}
      />,
    );

    await user.click(screen.getByRole('button', { name: 'Дата и время первого касания' }));
    await screen.findByText('Когда отправить первый шаг');
    await user.click(screen.getByRole('button', { name: 'Go to next month' }));

    const selectedDay = document.querySelector('button[aria-selected="true"]');
    if (!(selectedDay instanceof HTMLButtonElement)) {
      throw new Error('Selected calendar day is missing');
    }

    expect(selectedDay).not.toHaveClass('aria-selected:opacity-30');
    expect(selectedDay).toHaveClass('aria-selected:opacity-100');
  });
});
