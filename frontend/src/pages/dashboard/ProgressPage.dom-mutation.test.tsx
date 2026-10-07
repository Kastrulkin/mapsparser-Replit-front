import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Outlet, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ErrorBoundary } from '@/components/ErrorBoundary';
import { LanguageProvider } from '@/i18n/LanguageContext';
import { newAuth } from '@/lib/auth_new';
import { ProgressPage } from './ProgressPage';

vi.mock('@/lib/auth_new', () => ({
  newAuth: {
    makeRequest: vi.fn(),
  },
}));

const overview = {
  summary: {
    completed_milestones: 2,
    total_milestones: 4,
    active_areas: 1,
    needs_attention: 1,
    completed_last_30_days: 0,
    locations_count: 1,
  },
  focus_action: null,
  areas: [{
    key: 'maps',
    label: 'Карты и репутация',
    status: 'needs_attention',
    summary: 'Карта подключена, аудит ещё не готов',
    problem: 'Нужны свежие данные.',
    expected_outcome: 'Появится аудит карточки.',
    action: {
      title: 'Получите данные карты',
      reason: 'Нужны свежие данные.',
      expected_outcome: 'Появится аудит карточки.',
      cta_label: 'Обновить карту',
      cta_url: '/dashboard/profile',
    },
    progress: { completed: 2, total: 4 },
    milestones: [
      { key: 'map_connected', label: 'Карта подключена', status: 'done' },
      { key: 'map_audited', label: 'Данные и аудит получены', status: 'next' },
    ],
    metrics: [],
  }],
  recent_achievements: [],
  scope: {
    business_id: 'demo-business',
    business_name: 'Рога и копыта',
    is_network: false,
    locations: [{ id: 'demo-business', name: 'Рога и копыта' }],
  },
  generated_at: '2026-08-13T12:00:00Z',
};

const ContextRoute = () => (
  <Outlet context={{ currentBusinessId: 'demo-business' }} />
);

describe('Progress page DOM ownership', () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.localStorage.setItem('language', 'ru');
    vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => {
      callback(0);
      return 1;
    });
    vi.stubGlobal('cancelAnimationFrame', vi.fn());
    HTMLElement.prototype.scrollIntoView = vi.fn();
    HTMLElement.prototype.focus = vi.fn();

    let progressRequests = 0;
    vi.mocked(newAuth.makeRequest).mockImplementation((url: string) => {
      if (url.startsWith('/operator/progress?')) {
        progressRequests += 1;
        if (progressRequests === 1) return Promise.resolve(overview);
        return Promise.resolve({
          ...overview,
          summary: { ...overview.summary, completed_milestones: 3 },
          scope: { ...overview.scope, locations: [] },
        });
      }
      return Promise.resolve({ success: true, status: 'idle' });
    });
  });

  it('does not crash when translated audit text is removed after refresh', async () => {
    render(
      <MemoryRouter initialEntries={['/?section=maps&audit=open']}>
        <LanguageProvider>
          <ErrorBoundary>
            <Routes>
              <Route element={<ContextRoute />}>
                <Route index element={<ProgressPage />} />
              </Route>
            </Routes>
          </ErrorBoundary>
        </LanguageProvider>
      </MemoryRouter>,
    );

    const auditDescription = await screen.findByText(/Точка: Рога и копыта/);
    const locationText = auditDescription.firstChild;
    expect(locationText).not.toBeNull();

    const translatedWrapper = document.createElement('font');
    translatedWrapper.setAttribute('data-external-translation', 'true');
    auditDescription.insertBefore(translatedWrapper, locationText);
    translatedWrapper.appendChild(locationText!);

    fireEvent.click(screen.getByRole('button', { name: 'Обновить' }));

    expect(await screen.findByText(/3 из 4/)).toBeInTheDocument();
    expect(screen.queryByText('Что-то пошло не так')).not.toBeInTheDocument();
  });
});
