import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { LanguageProvider } from '@/i18n/LanguageContext';
import { newAuth } from '@/lib/auth_new';
import PublicSalesRoomPage from './PublicSalesRoomPage';

vi.mock('@/lib/auth_new', () => ({
  newAuth: {
    makeRequest: vi.fn(),
  },
}));

const demoRoom = {
  slug: 'room-test-audit-offer-20260629',
  mode: 'partner_search',
  business: { name: 'Рога и копыта' },
  manager: { name: 'Александр Демьянов' },
  recipient: { name: 'Ромашка', category: 'Салон красоты', city: 'Москва' },
  proposal: {
    title: 'Предложение партнёрства',
    body_text: 'Предлагаем совместную кампанию для двух локальных бизнесов.',
  },
  welcome: { body_text: 'Рад знакомству. Здесь можно обсудить детали.' },
  permissions: { can_edit_welcome: false },
  messages: [{ id: 'm1', author_name: 'Александр', body_text: 'Буду рад обсудить предложение.' }],
  proposal_review: { suggestions: [] },
};

describe('PublicSalesRoomPage localization', () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.localStorage.setItem('language', 'ru');
    window.history.replaceState({}, '', '/room/room-test-audit-offer-20260629?lang=el');
    vi.mocked(newAuth.makeRequest).mockResolvedValue({ room: demoRoom });
  });

  it('uses the link language and localizes the known demo-room chrome and fixture', async () => {
    const { container } = render(
      <MemoryRouter initialEntries={['/room/room-test-audit-offer-20260629?lang=el']}>
        <LanguageProvider>
          <Routes>
            <Route path="/room/:roomSlug" element={<PublicSalesRoomPage />} />
          </Routes>
        </LanguageProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByText('Πρόταση συνεργασίας')).toBeInTheDocument();
    expect(screen.getByText('Γεια σας.')).toBeInTheDocument();
    await waitFor(() => expect(container.textContent).not.toMatch(/[А-Яа-яЁё]/));
  });
});
