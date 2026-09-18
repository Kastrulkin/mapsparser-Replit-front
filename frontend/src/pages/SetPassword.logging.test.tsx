import { act, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';

import SetPassword from './SetPassword';

vi.mock('@/lib/auth_new', () => ({
  newAuth: {
    setPassword: vi.fn(),
  },
}));

describe('SetPassword reset URL logging', () => {
  afterEach(() => {
    vi.clearAllTimers();
    vi.useRealTimers();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it('keeps reset credentials out of console calls while preserving reset submission', async () => {
    vi.useFakeTimers();
    const email = 'owner@localos-e2e.invalid';
    const token = 'synthetic-reset-token';
    const password = 'safe-password';
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ success: true }),
    });
    const consoleLog = vi.spyOn(console, 'log').mockImplementation(() => undefined);
    const consoleWarn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => undefined);

    vi.stubGlobal('fetch', fetchMock);
    window.history.pushState({}, '', `/reset-password?email=${email}&token=${token}`);

    render(
      <MemoryRouter initialEntries={[`/reset-password?email=${email}&token=${token}`]}>
        <SetPassword />
      </MemoryRouter>,
    );

    fireEvent.change(screen.getByPlaceholderText('Новый пароль'), { target: { value: password } });
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Установить пароль' }));
    });

    expect(screen.getByText('Пароль успешно изменен! Выполняется вход...')).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith('/api/auth/confirm-reset', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ email, token, password }),
    });

    const capturedConsole = [consoleLog, consoleWarn, consoleError]
      .flatMap(spy => spy.mock.calls)
      .flatMap(call => call)
      .map(argument => String(argument))
      .join('\n');

    expect(capturedConsole).not.toContain(email);
    expect(capturedConsole).not.toContain(token);
  });
});
