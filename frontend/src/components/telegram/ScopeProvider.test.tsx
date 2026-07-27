import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { ScopeProvider, useMobileScope } from './ScopeProvider';

function ScopeProbe() {
  const { scope, hasSwitcher, openSwitcher } = useMobileScope();
  return <button type="button" disabled={!hasSwitcher} onClick={openSwitcher}>{scope?.name}</button>;
}

describe('ScopeProvider', () => {
  it('shares the verified scope and switch action with mobile modules', async () => {
    const openSwitcher = vi.fn();
    render(<ScopeProvider value={{ scope: { kind: 'network', id: 'network-1', name: 'Сеть' }, hasSwitcher: true, openSwitcher }}><ScopeProbe /></ScopeProvider>);

    await userEvent.click(screen.getByRole('button', { name: 'Сеть' }));
    expect(openSwitcher).toHaveBeenCalledOnce();
  });
});
