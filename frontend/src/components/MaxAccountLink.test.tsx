import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import MaxAccountLink from './MaxAccountLink';
import { maxAccountInviteCode } from '@/lib/maxAccountInvite';

const code = 'a'.repeat(43);
const signed = `auth_date=123&start_param=connect_${code}&hash=signed`;

afterEach(() => { vi.unstubAllGlobals(); window.history.replaceState({}, '', '/'); });

describe('MAX personal invitations', () => {
  it('reads signed launch data and the MAX query fallback, rejecting malformed values', () => {
    expect(maxAccountInviteCode(signed, '')).toBe(code);
    expect(maxAccountInviteCode('', `?WebAppStartParam=connect_${code}`)).toBe(code);
    expect(maxAccountInviteCode('start_param=invalid', `?WebAppStartParam=connect_${code}`)).toBe('');
    for (const invalid of ['connect_short', `connect_${code}extra`, `nav_${code}`, `connect_${'!'.repeat(43)}`]) {
      expect(maxAccountInviteCode('', `?WebAppStartParam=${encodeURIComponent(invalid)}`)).toBe('');
    }
  });

  it('needs no pasted code and submits only after confirmation with signed MAX identity', async () => {
    const request = vi.fn().mockResolvedValue(new Response(JSON.stringify({ success: true })));
    vi.stubGlobal('fetch', request);
    const linked = vi.fn();
    render(<MaxAccountLink initData={signed} onLinked={linked} />);
    expect(screen.queryByRole('textbox')).toBeNull();
    expect(request).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Подключить аккаунт' }));
    await waitFor(() => expect(linked).toHaveBeenCalledOnce());
    expect(request).toHaveBeenCalledWith('/api/max/link', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ init_data: signed, code }),
    });
  });

  it('explains an expired invitation without treating it as a successful login', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: 'Код недействителен или истёк' }), { status: 400 })));
    const linked = vi.fn();
    render(<MaxAccountLink initData={signed} onLinked={linked} />);
    fireEvent.click(screen.getByRole('button', { name: 'Подключить аккаунт' }));
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Код недействителен'));
    expect(screen.getByText(/попросите новую персональную ссылку/)).toBeVisible();
    expect(linked).not.toHaveBeenCalled();
  });

  it('keeps the existing manual connection available without an invitation', () => {
    render(<MaxAccountLink initData="auth_date=123&hash=signed" onLinked={vi.fn()} />);
    expect(screen.getByLabelText('Код из кабинета LocalOS')).toHaveValue('');
    expect(screen.getByRole('button', { name: 'Подключить аккаунт' })).toBeDisabled();
  });
});
