import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { Button, buttonVariants } from './button';

describe('LocalOS button hierarchy', () => {
  it('uses black for the default product action', () => {
    render(<Button>Сохранить</Button>);

    const button = screen.getByRole('button', { name: 'Сохранить' });
    expect(button).toHaveClass('bg-slate-950');
    expect(button).toHaveClass('active:scale-[0.96]');
    expect(button.className).not.toMatch(/bg-(?:orange|blue|indigo|violet|purple)-/);
  });

  it('keeps the gold gradient on a disabled public conversion action', () => {
    render(<Button variant="brand" disabled>Зарегистрироваться</Button>);

    const button = screen.getByRole('button', { name: 'Зарегистрироваться' });
    expect(button).toBeDisabled();
    expect(button).toHaveClass('btn-iridescent');
    expect(button).toHaveClass('active:scale-[0.96]');
  });

  it('keeps secondary actions neutral', () => {
    expect(buttonVariants({ variant: 'outline' })).not.toMatch(/(?:blue|indigo|violet|purple)-/);
  });
});
