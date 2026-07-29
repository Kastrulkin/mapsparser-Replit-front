import '@testing-library/jest-dom/vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { newAuth } from '@/lib/auth_new';
import { TelegramSourceCatalog } from './TelegramSourceCatalog';

vi.mock('@/lib/auth_new', () => ({
  newAuth: { makeRequest: vi.fn() },
}));

describe('TelegramSourceCatalog', () => {
  beforeEach(() => {
    vi.mocked(newAuth.makeRequest).mockReset();
    vi.mocked(newAuth.makeRequest).mockResolvedValue({
      items: [{
        id: 'source-1',
        title: 'Владельцы салонов',
        canonical_url: 'https://t.me/salonowners',
        status: 'active',
        documents_count: 42,
        categories: [],
      }],
    });
  });

  it('lets a superadmin assign several categories to one source', async () => {
    render(<TelegramSourceCatalog />);

    expect(await screen.findByText('Владельцы салонов')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Разметить/ }));
    fireEvent.click(screen.getByRole('button', { name: 'бьюти' }));
    fireEvent.click(screen.getByRole('button', { name: 'чат' }));
    fireEvent.click(screen.getByRole('button', { name: 'владельцы' }));

    vi.mocked(newAuth.makeRequest).mockResolvedValueOnce({
      source: { categories: ['бьюти', 'чат', 'владельцы'] },
    });
    fireEvent.click(screen.getByRole('button', { name: /Сохранить/ }));

    await waitFor(() => expect(newAuth.makeRequest).toHaveBeenLastCalledWith(
      '/admin/knowledge/sources/source-1/categories',
      expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify({ categories: ['бьюти', 'чат', 'владельцы'] }),
      }),
    ));
    expect((await screen.findAllByText('бьюти')).length).toBeGreaterThan(0);
  });
});
