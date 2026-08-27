import '@testing-library/jest-dom/vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Outlet, Route, Routes } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

import { newAuth } from '@/lib/auth_new';
import { JourneyAdminPage } from './JourneyAdminPage';

vi.mock('@/lib/auth_new', () => ({ newAuth: { makeRequest: vi.fn() } }));

describe('JourneyAdminPage', () => {
  it('fails closed for a non-superadmin without loading lead data', () => {
    const Context = () => <Outlet context={{ user: { is_superadmin: false } }} />;
    render(<MemoryRouter><Routes><Route element={<Context />}><Route index element={<JourneyAdminPage />} /></Route></Routes></MemoryRouter>);

    expect(screen.getByText('Доступ только для администратора')).toBeInTheDocument();
    expect(newAuth.makeRequest).not.toHaveBeenCalled();
  });
});
