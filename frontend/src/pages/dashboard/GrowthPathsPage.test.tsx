import '@testing-library/jest-dom/vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Outlet, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { newAuth } from '@/lib/auth_new';
import { GrowthPathsPage } from './GrowthPathsPage';

vi.mock('@/lib/auth_new', () => ({ newAuth: { makeRequest: vi.fn() } }));

const Context = () => <Outlet context={{ currentBusinessId: 'business-1' }} />;

describe('GrowthPathsPage', () => {
  beforeEach(() => vi.clearAllMocks());

  it('puts the active path first and explains a locked block without hiding its value', async () => {
    vi.mocked(newAuth.makeRequest).mockResolvedValue({
      focus_action: { id: 'action-1', flow_type: 'influencer' },
      paths: [
        { flow_type: 'maps', title: 'Карты', status: 'not_started', opportunity: 'Исправить карточку', access: { status: 'available', reason: 'Доступно', cta_label: 'Открыть карты', cta_target: { screen: 'progress' } } },
        { flow_type: 'content', title: 'Контент', status: 'not_started', opportunity: 'Подготовить публикацию', access: { status: 'payment_required', reason: 'Полный черновик и календарь открываются на платном тарифе.', cta_label: 'Выбрать тариф', cta_target: { screen: 'settings' } } },
        { flow_type: 'influencer', title: 'Инфлюенсеры', status: 'ready', opportunity: 'Автор уже выбран', access: { status: 'available', reason: 'Доступно', cta_label: 'Открыть автора', cta_target: { screen: 'influencers', action_id: 'action-1' } }, action: { id: 'action-1', flow_type: 'influencer', entity_type: 'creator_profile', action_type: 'send_message', status: 'ready', priority: 100, title: 'Написать автору', description: 'Сообщение готово', cta_label: 'Открыть автора', allowed_commands: ['copy', 'mark_sent'], version: 1, cta_target: { screen: 'influencers' } } },
        { flow_type: 'partnership', title: 'Партнёрства', status: 'not_started', opportunity: 'Найти партнёра', access: { status: 'available', reason: 'Доступно', cta_label: 'Открыть партнёров', cta_target: { screen: 'partnerships' } } },
      ],
    });

    render(<MemoryRouter><Routes><Route element={<Context />}><Route index element={<GrowthPathsPage />} /></Route></Routes></MemoryRouter>);

    const headings = await screen.findAllByRole('heading', { level: 2 });
    expect(newAuth.makeRequest).toHaveBeenCalledWith('/growth-paths?business_id=business-1');
    expect(headings[0]).toHaveTextContent('Инфлюенсеры');
    expect(screen.getByText('Подготовить публикацию')).toBeVisible();
    expect(screen.getByText('Полный черновик и календарь открываются на платном тарифе.')).toBeVisible();
    expect(screen.getByRole('link', { name: 'Выбрать тариф' })).toHaveAttribute('href', '/dashboard/profile?focus=subscription#subscription');
    expect(screen.getByRole('link', { name: /Открыть автора/ })).toHaveAttribute('href', '/dashboard/promotion/influencers?journey_action=action-1');
  });
});
