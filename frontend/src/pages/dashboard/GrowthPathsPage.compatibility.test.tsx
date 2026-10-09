import '@testing-library/jest-dom/vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Outlet, Route, Routes } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { newAuth } from '@/lib/auth_new';
import { GrowthPathsPage } from './GrowthPathsPage';

vi.mock('@/lib/auth_new', () => ({ newAuth: { makeRequest: vi.fn() } }));
vi.mock('@/i18n/LanguageContext.logic', () => ({ useLanguage: () => ({ language: 'ru' }) }));
const Context = () => <Outlet context={{ currentBusinessId: 'business-1' }} />;
const renderPage = () => render(<MemoryRouter><Routes><Route element={<Context />}><Route index element={<GrowthPathsPage />} /></Route></Routes></MemoryRouter>);

describe('growth path response compatibility', () => {
  it('keeps known directions when server returns maps_content or a future direction', async () => {
    vi.mocked(newAuth.makeRequest).mockResolvedValue({
      focus_action: { flow_type: 'future_direction' },
      paths: [
        { flow_type: 'maps', opportunity: 'Проверить карточку', access: { status: 'available' } },
        { flow_type: 'maps_content', opportunity: 'Новости', access: { status: 'available' } },
        { flow_type: 'future_direction', access: { status: 'available' } },
        { flow_type: '__proto__' },
        null,
      ],
    });
    renderPage();
    expect(await screen.findAllByRole('heading', { level: 2 })).toHaveLength(1);
    expect(screen.getByRole('link')).toHaveAttribute('href', '/dashboard/card');
  });
  it('shows an empty state instead of crashing for only unsupported directions', async () => {
    vi.mocked(newAuth.makeRequest).mockResolvedValue({ paths: [{ flow_type: 'future_direction' }] });
    renderPage();
    expect(await screen.findByRole('heading', { level: 2 })).toBeVisible();
    expect(screen.queryByRole('link')).not.toBeInTheDocument();
  });
});
