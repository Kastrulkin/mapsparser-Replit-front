import '@testing-library/jest-dom/vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

import Header from './Header';

vi.mock('../lib/auth_new', () => ({
  newAuth: { signOut: vi.fn() },
}));

vi.mock('../i18n/LanguageContext', () => ({
  useLanguage: () => ({
    language: 'ru',
    t: {
      header: {
        prices: 'Цены',
        login: 'Вход',
        tryFree: 'Попробовать бесплатно',
      },
    },
  }),
}));

vi.mock('./LanguageSwitcher', () => ({
  LanguageSwitcher: () => <div>Русский</div>,
}));

describe('Header agents navigation', () => {
  it('leaves the cross-page agents link to the browser instead of React Router', () => {
    render(
      <MemoryRouter initialEntries={['/docs']}>
        <Header />
      </MemoryRouter>,
    );

    const link = screen.getAllByRole('link', { name: 'Как работает LocalOS' })[0];
    const clickEvent = new MouseEvent('click', { bubbles: true, cancelable: true });

    link.dispatchEvent(clickEvent);

    expect(link).toHaveAttribute('href', '/#agents');
    expect(clickEvent.defaultPrevented).toBe(false);
  });
});
