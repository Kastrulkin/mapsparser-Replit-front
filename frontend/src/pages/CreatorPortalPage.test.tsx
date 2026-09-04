import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { CreatorPortalPage } from './CreatorPortalPage';

const offer = {
  id: 'recipient-1',
  status: 'selected',
  title: 'Семейная стрижка за результат',
  goal: 'Привести трёх новых клиентов',
  business_name: 'Весёлая расчёска',
  offer_kind: 'distributed',
  collaboration_id: 'collaboration-1',
  collaboration_status: 'agreed',
  offer: { service: 'Детская стрижка', benefit: 'Бесплатная стрижка', result_condition: 'Если придут 3 новых клиента' },
  deliverables: [],
  messages: [],
};

const workspace = {
  account: { display_name: 'Анна', notification_preferences: {} },
  profile: { display_name: 'Анна' },
  offers: { new: [], active: [offer], finished: [] },
};

describe('CreatorPortalPage publication flow', () => {
  beforeEach(() => {
    window.localStorage.setItem('localos_creator_portal_token', 'creator-session');
    vi.unstubAllGlobals();
  });

  it('lets a selected creator submit the publication URL', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith('/me')) return { ok: true, json: async () => ({ success: true, workspace }) };
      if (url.endsWith('/publication')) return { ok: true, json: async () => ({ success: true, offer: { ...offer, status: 'published', deliverables: [{ id: 'deliverable-1', platform: 'telegram', deliverable_type: 'post', publication_url: 'https://t.me/anna/42', verification_status: 'submitted' }] } }) };
      return { ok: true, json: async () => ({ success: true, offer }) };
    });
    vi.stubGlobal('fetch', fetchMock);
    const user = userEvent.setup();

    render(<MemoryRouter initialEntries={['/creator/offers/recipient-1']}><Routes><Route path="/creator/offers/:offerId" element={<CreatorPortalPage />} /></Routes></MemoryRouter>);

    expect(await screen.findByRole('heading', { name: 'Публикация и результат' })).toBeInTheDocument();
    await user.type(screen.getByPlaceholderText('https://...'), 'https://t.me/anna/42');
    await user.click(screen.getByRole('button', { name: 'Передать ссылку LocalOS' }));

    expect(await screen.findByText('Ссылка передана LocalOS на проверку.')).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith('/api/creator-portal/offers/recipient-1/publication', expect.objectContaining({ method: 'POST' }));
  });
});
