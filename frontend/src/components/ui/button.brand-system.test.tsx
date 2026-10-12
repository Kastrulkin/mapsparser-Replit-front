import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { Button } from './button';
import { buttonVariants } from './button.logic';
import css from '@/index.css?raw';

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

  it('keeps hover and dark-mode product accents black instead of legacy rust', () => {
    const accents = [...css.matchAll(/--accent:\s*([^;]+);/g)].map(match => match[1]);
    const primary = [...css.matchAll(/--primary:\s*([^;]+);/g)].map(match => match[1]);
    expect(accents).toEqual(['222 47% 6%', '222 47% 6%']);
    expect(primary).toEqual(['222 47% 6%', '222 47% 6%']);
    expect(buttonVariants({ variant: 'outline' })).toContain('hover:bg-accent');
    expect(buttonVariants({ variant: 'ghost' })).toContain('hover:bg-accent');
  });
});
