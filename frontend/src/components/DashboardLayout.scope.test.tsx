import '@testing-library/jest-dom/vitest';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { useState, type ReactNode } from 'react';
import { MemoryRouter, Outlet, Route, Routes, useOutletContext } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { DashboardOutletContext } from '@/types/business';

const mocks = vi.hoisted(() => {
  class TestHttpError extends Error {
    status: number | null;

    constructor(status: number | null) {
      super('request failed');
      this.status = status;
    }
  }

  return {
    HttpError: TestHttpError,
    auth: {
      getCurrentUser: vi.fn(),
      makeRequest: vi.fn(),
    },
  };
});

const { auth } = mocks;

vi.mock('../lib/auth_new', () => ({
  HttpError: mocks.HttpError,
  newAuth: mocks.auth,
}));

vi.mock('./DashboardHeader', () => ({
  DashboardHeader: () => <div data-testid="dashboard-header" />,
}));

vi.mock('./DashboardSidebar', () => ({
  DashboardSidebar: () => <div data-testid="dashboard-sidebar" />,
}));

vi.mock('./guided-tour/GuidedTourProvider', () => ({
  DemoModeBanner: () => null,
  GuidedTourProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

import { DashboardLayout } from './DashboardLayout';

const businessA = { id: 'business-a', name: 'Бизнес A', network_id: 'network-a', network_name: 'Сеть A' };
const businessB = { id: 'business-b', name: 'Бизнес B' };

const ScopeProbe = () => {
  const { controlScope, currentBusinessId, onBusinessChange, reloadBusinesses } = useOutletContext<DashboardOutletContext>();
  const [privateState, setPrivateState] = useState('чистое состояние');

  return (
    <>
      <div data-testid="current-business">{currentBusinessId || 'none'}</div>
      <div data-testid="control-scope">{controlScope ? `${controlScope.kind}:${controlScope.id}` : 'none'}</div>
      <div data-testid="private-state">{privateState}</div>
      <button type="button" onClick={() => void reloadBusinesses()}>Обновить доступ</button>
      <button type="button" onClick={() => onBusinessChange('business-b')}>Выбрать B</button>
      <button type="button" onClick={() => setPrivateState('данные A')}>Записать приватные данные</button>
    </>
  );
};

const renderLayout = () => render(
  <MemoryRouter initialEntries={['/dashboard']}>
    <Routes>
      <Route path="/dashboard" element={<DashboardLayout />}>
        <Route index element={<ScopeProbe />} />
      </Route>
    </Routes>
  </MemoryRouter>,
);

const configureInitialUser = () => {
  auth.getCurrentUser.mockResolvedValue({
    id: 'user-1',
    email: 'owner@example.test',
    businesses: [businessA, businessB],
  });
};

const deferredResponse = () => {
  let resolveRequest: (value: { businesses: (typeof businessA)[] }) => void = () => undefined;
  const promise = new Promise<{ businesses: (typeof businessA)[] }>((resolve) => {
    resolveRequest = resolve;
  });
  return { promise, resolve: resolveRequest };
};

describe('DashboardLayout membership scope', () => {
  beforeEach(() => {
    auth.getCurrentUser.mockReset();
    auth.makeRequest.mockReset();
    window.localStorage.clear();
  });

  it('replaces a revoked current business and clears scope-bound child state', async () => {
    configureInitialUser();
    window.localStorage.setItem('selectedBusinessId', businessA.id);
    window.localStorage.setItem('dashboard_control_scope', JSON.stringify({ kind: 'network', id: 'network-a', name: 'Сеть A' }));
    auth.makeRequest.mockResolvedValue({ businesses: [businessB] });

    renderLayout();

    await screen.findByText('business-a');
    fireEvent.click(screen.getByRole('button', { name: 'Записать приватные данные' }));
    expect(screen.getByTestId('private-state')).toHaveTextContent('данные A');
    fireEvent.click(screen.getByRole('button', { name: 'Обновить доступ' }));

    await waitFor(() => expect(screen.getByTestId('current-business')).toHaveTextContent('business-b'));
    expect(screen.getByTestId('control-scope')).toHaveTextContent('business:business-b');
    expect(screen.getByTestId('private-state')).toHaveTextContent('чистое состояние');
    expect(window.localStorage.getItem('selectedBusinessId')).toBe('business-b');
    expect(window.localStorage.getItem('dashboard_control_scope')).toBe(JSON.stringify({ kind: 'business', id: 'business-b', name: 'Бизнес B' }));
  });

  it('clears the active business, persisted selection, and scope when membership is empty', async () => {
    configureInitialUser();
    window.localStorage.setItem('selectedBusinessId', businessA.id);
    window.localStorage.setItem('dashboard_control_scope', JSON.stringify({ kind: 'network', id: 'network-a', name: 'Сеть A' }));
    auth.makeRequest.mockResolvedValue({ businesses: [] });

    renderLayout();

    await screen.findByText('business-a');
    fireEvent.click(screen.getByRole('button', { name: 'Обновить доступ' }));

    await waitFor(() => expect(screen.getByTestId('current-business')).toHaveTextContent('none'));
    expect(screen.getByTestId('control-scope')).toHaveTextContent('none');
    expect(window.localStorage.getItem('selectedBusinessId')).toBeNull();
    expect(window.localStorage.getItem('dashboard_control_scope')).toBeNull();
  });

  it('clears the active scope when the membership endpoint reports no remaining access', async () => {
    configureInitialUser();
    window.localStorage.setItem('selectedBusinessId', businessA.id);
    window.localStorage.setItem('dashboard_control_scope', JSON.stringify({ kind: 'network', id: 'network-a', name: 'Сеть A' }));
    auth.makeRequest.mockRejectedValue(new mocks.HttpError(403));

    renderLayout();

    await screen.findByText('business-a');
    fireEvent.click(screen.getByRole('button', { name: 'Обновить доступ' }));

    await waitFor(() => expect(screen.getByTestId('current-business')).toHaveTextContent('none'));
    expect(screen.getByTestId('control-scope')).toHaveTextContent('none');
    expect(window.localStorage.getItem('selectedBusinessId')).toBeNull();
    expect(window.localStorage.getItem('dashboard_control_scope')).toBeNull();
  });

  it('retains the current scope and offers retry when membership refresh has a transient failure', async () => {
    configureInitialUser();
    window.localStorage.setItem('selectedBusinessId', businessA.id);
    window.localStorage.setItem('dashboard_control_scope', JSON.stringify({ kind: 'network', id: 'network-a', name: 'Сеть A' }));
    auth.makeRequest.mockRejectedValue(new Error('network unavailable'));

    renderLayout();

    await screen.findByText('business-a');
    fireEvent.click(screen.getByRole('button', { name: 'Обновить доступ' }));

    expect(await screen.findByRole('status')).toHaveTextContent('Текущий бизнес сохранён');
    expect(screen.getByRole('button', { name: 'Повторить' })).toBeVisible();
    expect(screen.getByTestId('current-business')).toHaveTextContent('business-a');
    expect(screen.getByTestId('control-scope')).toHaveTextContent('network:network-a');
    expect(window.localStorage.getItem('selectedBusinessId')).toBe('business-a');
  });

  it('ignores a membership response that becomes stale after a business switch', async () => {
    configureInitialUser();
    window.localStorage.setItem('selectedBusinessId', businessA.id);
    const pending = deferredResponse();
    auth.makeRequest.mockReturnValue(pending.promise);

    renderLayout();

    await screen.findByText('business-a');
    fireEvent.click(screen.getByRole('button', { name: 'Обновить доступ' }));
    fireEvent.click(screen.getByRole('button', { name: 'Выбрать B' }));
    await act(async () => {
      pending.resolve({ businesses: [businessA] });
    });

    await waitFor(() => expect(screen.getByTestId('current-business')).toHaveTextContent('business-b'));
    expect(screen.getByTestId('control-scope')).toHaveTextContent('business:business-b');
    expect(window.localStorage.getItem('selectedBusinessId')).toBe('business-b');
  });
});
