import '@testing-library/jest-dom/vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import MobileOnboarding from './MobileOnboarding';

describe('MobileOnboarding', () => {
  it('explains the product before opening the daily workspace', async () => {
    const user = userEvent.setup();
    const finish = vi.fn();
    render(<MobileOnboarding hasSwitcher networkMode onFinish={finish} />);

    expect(screen.getByRole('heading', { name: /Получайте больше клиентов/ })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Проверить мой бизнес' }));
    expect(await screen.findByRole('heading', { name: 'Поручайте работу обычными словами' })).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Дальше' }));
    expect(await screen.findByRole('heading', { name: 'Сразу видно, что важно сейчас' })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Дальше' }));
    expect(await screen.findByRole('heading', { name: 'Сеть целиком или одна точка' })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Дальше' }));
    expect(await screen.findByRole('heading', { name: 'Один план вместо десятков задач' })).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Открыть Сегодня' }));
    expect(finish).toHaveBeenCalledTimes(1);
  });

  it('skips the network step for a single business', async () => {
    const user = userEvent.setup();
    render(<MobileOnboarding hasSwitcher={false} networkMode={false} onFinish={vi.fn()} />);

    await user.click(screen.getByRole('button', { name: 'Проверить мой бизнес' }));
    await screen.findByRole('heading', { name: 'Поручайте работу обычными словами' });
    await user.click(screen.getByRole('button', { name: 'Дальше' }));
    await screen.findByRole('heading', { name: 'Сразу видно, что важно сейчас' });
    await user.click(screen.getByRole('button', { name: 'Дальше' }));
    expect(await screen.findByRole('heading', { name: 'Один план вместо десятков задач' })).toBeInTheDocument();
    expect(screen.queryByText('Сеть целиком или одна точка')).not.toBeInTheDocument();
  });
});
