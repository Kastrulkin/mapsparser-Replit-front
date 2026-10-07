import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { newAuth } from '@/lib/auth_new';
import { CreatorRoomPage } from './CreatorRoomPage';

vi.mock('@/lib/auth_new', () => ({ newAuth: { makeRequest: vi.fn() } }));

const room = {
  status: 'invited',
  display_name: 'Локальный автор',
  campaign_title: 'Обзор семейного места',
  campaign_goal: 'Познакомить жителей района с бизнесом',
  business_name: 'Семейный салон',
  business_city: 'Санкт-Петербург',
  formats: ['обзор', 'пост'],
  deliverables: [],
};

const renderRoom = () => render(
  <MemoryRouter initialEntries={['/creator-room/secret-token']}>
    <Routes><Route path="/creator-room/:token" element={<CreatorRoomPage />} /></Routes>
  </MemoryRouter>,
);

describe('CreatorRoomPage', () => {
  beforeEach(() => {
    vi.mocked(newAuth.makeRequest).mockReset();
    vi.mocked(newAuth.makeRequest).mockResolvedValue({ room });
  });

  it('shows the proposal and keeps payments and rights explicit', async () => {
    renderRoom();

    expect(await screen.findByRole('heading', { name: 'Обзор семейного места' })).toBeInTheDocument();
    expect(screen.getByText(/Платежи выполняются вне LocalOS/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Принять условия' })).toBeInTheDocument();
  });

  it('records acceptance through the private token endpoint', async () => {
    const user = userEvent.setup();
    renderRoom();
    await screen.findByRole('heading', { name: 'Обзор семейного места' });

    await user.click(screen.getByRole('button', { name: 'Принять условия' }));

    expect(newAuth.makeRequest).toHaveBeenLastCalledWith('/promotion/influencers/public/secret-token', {
      method: 'PATCH',
      body: JSON.stringify({ action: 'accept' }),
    });
  });

  it('shows attribution instructions and sends metrics for a scheduled checkpoint', async () => {
    const user = userEvent.setup();
    vi.mocked(newAuth.makeRequest).mockResolvedValue({
      room: {
        ...room,
        deliverables: [{
          id: 'deliverable-1',
          platform: 'telegram',
          deliverable_type: 'post',
          publication_url: 'https://t.me/creator/10',
          verification_status: 'verified',
          tracking: {
            tracked_url: 'https://salon.example/book?utm_source=telegram',
            promo_code: 'SALON10',
            cta: 'Записаться на детскую стрижку',
          },
          measurement_checkpoints: [
            { checkpoint: '24h', status: 'pending', due_at: '2026-08-22T10:00:00Z' },
            { checkpoint: '7d', status: 'pending', due_at: '2026-08-28T10:00:00Z' },
            { checkpoint: '14d', status: 'pending', due_at: '2026-09-04T10:00:00Z' },
          ],
        }],
      },
    });
    renderRoom();

    expect(await screen.findByText(/SALON10/)).toBeInTheDocument();
    expect(screen.getByText(/Записаться на детскую стрижку/)).toBeInTheDocument();
    await user.selectOptions(screen.getByRole('combobox', { name: 'Материал' }), 'deliverable-1');
    await user.selectOptions(screen.getByRole('combobox', { name: 'Контрольная точка' }), '24h');
    await user.type(screen.getByPlaceholderText('Охват'), '5000');
    await user.type(screen.getByPlaceholderText('Просмотры'), '6500');
    await user.click(screen.getByRole('button', { name: 'Передать статистику' }));

    expect(newAuth.makeRequest).toHaveBeenLastCalledWith('/promotion/influencers/public/secret-token', {
      method: 'PATCH',
      body: JSON.stringify({ action: 'add_metrics', deliverable_id: 'deliverable-1', checkpoint: '24h', reach: 5000, views: 6500 }),
    });
  });
});
