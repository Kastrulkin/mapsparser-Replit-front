import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, it, vi } from 'vitest';

import { newAuth } from '@/lib/auth_new';
import { OutreachContinuation } from './OutreachContinuation';

afterEach(() => vi.restoreAllMocks());

it('shows a clear compact starting action and opens the reviewed search flow', async () => {
  const request = vi.spyOn(newAuth, 'makeRequest').mockResolvedValue({ enabled: true, items: [] });

  render(<OutreachContinuation businessId="business-1" compact />);
  await act(async () => {});

  expect(await screen.findByRole('heading', { name: 'Найдите новых партнёров' })).toBeVisible();
  await userEvent.click(screen.getByRole('button', { name: 'Новый поиск' }));

  expect(screen.getByRole('dialog')).toBeVisible();
  expect(screen.getByRole('heading', { name: 'Новый поиск' })).toBeVisible();
  expect(request).toHaveBeenCalledWith('/partnership/continuations?business_id=business-1');
});
