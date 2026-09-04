import '@testing-library/jest-dom/vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

import Login from './Login';

vi.mock('@/components/Footer', () => ({ default: () => null }));
vi.mock('@/i18n/LanguageContext', () => ({
  useLanguage: () => ({ language: 'es' }),
}));
vi.mock('@/lib/auth_new', () => ({
  newAuth: {
    signIn: vi.fn(),
    makeRequest: vi.fn(),
  },
}));

describe('Login Spanish localization', () => {
  it('renders the registration form in Spanish when Spanish is selected', () => {
    render(
      <MemoryRouter initialEntries={['/login?tab=register']}>
        <Login />
      </MemoryRouter>,
    );

    expect(screen.getByRole('button', { name: 'Registro' })).toBeVisible();
    expect(screen.getByText('Datos personales')).toBeVisible();
    expect(screen.getByLabelText('Nombre')).toBeVisible();
    expect(screen.getByLabelText('Contraseña *')).toBeVisible();
    expect(screen.getByText('Datos del negocio')).toBeVisible();
    expect(screen.getByLabelText('Nombre del negocio *')).toBeVisible();
    expect(screen.getByLabelText('Dirección *')).toBeVisible();
    expect(screen.getByLabelText('Ciudad *')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Registrarse' })).toBeDisabled();

    expect(screen.queryByRole('button', { name: 'Register' })).not.toBeInTheDocument();
    expect(screen.queryByText('Personal details')).not.toBeInTheDocument();
  });
});
