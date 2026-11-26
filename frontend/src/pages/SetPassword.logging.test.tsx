import { act, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';

import SetPassword from './SetPassword';
import { newAuth } from '@/lib/auth_new';

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

describe('SetPassword invitation', () => {
  afterEach(() => {
    vi.clearAllTimers();
    vi.useRealTimers();
    window.history.replaceState({}, '', '/');
  });

  it('opens the prepared cabinet immediately after the password is saved', async () => {
    vi.useFakeTimers();
    const email = 'owner@localos-e2e.invalid';
    const invite = `/set-password#email=${encodeURIComponent(email)}&token=prepared.test-only`;
    window.history.replaceState({}, '', invite);
    let complete: (result: Awaited<ReturnType<typeof newAuth.setPassword>>) => void = () => undefined;
    vi.mocked(newAuth.setPassword).mockImplementationOnce(() => new Promise(resolve => { complete = resolve; }));

    function Cabinet() {
      return <p>Кабинет {new URLSearchParams(useLocation().search).get('business_id')}</p>;
    }

    render(<MemoryRouter initialEntries={[invite]}><Routes>
      <Route path="/set-password" element={<SetPassword />} />
      <Route path="/dashboard/operator" element={<Cabinet />} />
    </Routes></MemoryRouter>);

    fireEvent.change(screen.getByLabelText('Новый пароль'), { target: { value: 'synthetic-password' } });
    fireEvent.click(screen.getByRole('checkbox'));
    fireEvent.click(screen.getByRole('button', { name: 'Установить пароль' }));
    expect(screen.getByRole('button', { name: 'Сохраняем...' })).toBeDisabled();
    expect(screen.queryByText('Кабинет pilot-owner')).not.toBeInTheDocument();

    await act(async () => {
      complete({ user: { id: 'new-owner', email }, error: null, businessId: 'pilot-owner', initialSetup: true });
    });

    expect(screen.getByText('Кабинет pilot-owner')).toBeVisible();
  });
});
