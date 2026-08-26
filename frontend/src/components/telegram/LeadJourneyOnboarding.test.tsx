import '@testing-library/jest-dom/vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { LEAD_JOURNEY_STORAGE_KEY } from '@/lib/leadJourney';
import LeadJourneyOnboarding from './LeadJourneyOnboarding';

describe('LeadJourneyOnboarding', () => {
  beforeEach(() => window.localStorage.clear());

  it('uses the same direction-detail-result flow in the Mini App', async () => {
    const user = userEvent.setup();
    const finish = vi.fn();
    render(<LeadJourneyOnboarding onFinish={finish} />);

    expect(screen.getByRole('heading', { name: 'Откуда привести следующего клиента?' })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /Бизнесы рядом/ }));
    expect(await screen.findByRole('heading', { name: 'Предложение, полезное обеим сторонам' })).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Подготовить предложение партнёру' }));
    expect(await screen.findByRole('heading', { name: 'Предложение партнёру подготовлено' })).toBeInTheDocument();
    expect(screen.getByText('Статус')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Открыть рабочий шаг' }));
    expect(finish).toHaveBeenCalledWith('partnerships');
    expect(window.localStorage.getItem(LEAD_JOURNEY_STORAGE_KEY)).toBe('partnerships');
  }, 15_000);
});
