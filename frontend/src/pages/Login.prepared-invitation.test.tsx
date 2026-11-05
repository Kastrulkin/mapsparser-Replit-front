import '@testing-library/jest-dom/vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Login from './Login';
import { newAuth } from '@/lib/auth_new';

vi.mock('@/components/Footer', () => ({ default: () => null }));
vi.mock('@/i18n/LanguageContext.logic', () => ({ useLanguage: () => ({ language: 'ru' }) }));
vi.mock('@/lib/auth_new', () => ({ newAuth: { signIn: vi.fn(), makeRequest: vi.fn() } }));

beforeEach(() => { window.localStorage.clear(); });

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it('lets an owner request email confirmation after activating with an invitation', async () => {
  vi.mocked(newAuth.signIn).mockResolvedValueOnce({ user: null, error: 'EMAIL_NOT_VERIFIED' });
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ success: true }) });
  vi.stubGlobal('fetch', fetchMock);
  render(<MemoryRouter initialEntries={['/login']}><Login /></MemoryRouter>);

  fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'owner@example.test' } });
  fireEvent.change(screen.getByLabelText('Пароль'), { target: { value: 'synthetic-test-only' } });
  fireEvent.click(screen.getByRole('button', { name: 'Войти' }));
  const resend = await screen.findByRole('button', { name: 'Отправить письмо ещё раз' });
  expect(fetchMock).not.toHaveBeenCalled();
  fireEvent.click(resend);
  await screen.findByRole('status');
  expect(fetchMock).toHaveBeenCalledWith('/api/auth/resend-verification', expect.objectContaining({
    body: JSON.stringify({ email: 'owner@example.test' }),
  }));
});
