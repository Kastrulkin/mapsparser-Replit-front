import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

import Login from './Login';

vi.mock('@/components/Footer', () => ({ default: () => null }));
vi.mock('@/i18n/LanguageContext', () => ({
  useLanguage: () => ({ language: 'ru' }),
}));
vi.mock('@/lib/auth_new', () => ({
  newAuth: {
    signIn: vi.fn(),
    makeRequest: vi.fn(),
  },
}));

describe('Login public brand buttons', () => {
  it('keeps the disabled registration CTA gold and uses neutral tabs', () => {
    render(
      <MemoryRouter initialEntries={['/login?tab=register']}>
        <Login />
      </MemoryRouter>,
    );

    const registration = screen.getByRole('button', { name: 'Зарегистрироваться' });
    expect(registration).toBeDisabled();
    expect.soft(registration).toHaveClass('btn-iridescent');
    expect.soft(registration).toHaveClass('active:scale-[0.96]');

    const activeTab = screen.getByRole('button', { name: 'Регистрация' });
    expect.soft(activeTab.className).not.toMatch(/(?:blue|indigo)-/);
    expect.soft(activeTab).toHaveClass('active:scale-[0.96]');
  });
});
