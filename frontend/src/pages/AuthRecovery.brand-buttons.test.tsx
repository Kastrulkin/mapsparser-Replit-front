import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import SetPassword from './SetPassword';

vi.mock('@/lib/auth_new', () => ({
  newAuth: {
    setPassword: vi.fn(),
  },
}));

describe('Authentication recovery public brand buttons', () => {
  beforeEach(() => {
    window.history.pushState({}, '', '/set-password');
  });

  it('keeps the disabled password CTA gold with the canonical press state', async () => {
    window.history.pushState({}, '', '/set-password?email=owner@example.com&token=valid-token');

    render(
      <MemoryRouter initialEntries={['/set-password?email=owner@example.com&token=valid-token']}>
        <SetPassword />
      </MemoryRouter>,
    );

    const submit = await screen.findByRole('button', { name: 'Установить пароль' });
    expect(submit).toBeDisabled();
    expect.soft(submit).toHaveClass('btn-iridescent');
    expect.soft(submit).toHaveClass('active:scale-[0.96]');
  });

  it('does not introduce blue recovery actions', async () => {
    render(
      <MemoryRouter initialEntries={['/set-password']}>
        <SetPassword />
      </MemoryRouter>,
    );

    const retry = await screen.findByRole('button', { name: 'Восстановить пароль через email' });
    const alternative = screen.getByRole('button', { name: 'Альтернативное восстановление пароля' });

    expect.soft(retry).toHaveClass('btn-iridescent');
    expect.soft(retry).toHaveClass('active:scale-[0.96]');
    expect.soft(alternative.className).not.toMatch(/(?:blue|indigo)-/);
    expect.soft(alternative).toHaveClass('active:scale-[0.96]');
  });
});
