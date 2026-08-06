import '@testing-library/jest-dom/vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { newAuth } from '@/lib/auth_new';
import { KnowledgeMarketOverview } from './KnowledgeMarketOverview';

vi.mock('@/lib/auth_new', () => ({
  newAuth: { makeRequest: vi.fn() },
}));

describe('KnowledgeMarketOverview semantic search', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.mocked(newAuth.makeRequest).mockReset();
    vi.mocked(newAuth.makeRequest).mockImplementation(async (endpoint) => {
      if (endpoint === '/admin/knowledge/overview') {
        return { data: { enabled: true, summary: {} } };
      }
      if (String(endpoint).startsWith('/admin/knowledge/signals?')) {
        return { items: [] };
      }
      if (endpoint === '/admin/knowledge/embeddings/search') {
        return {
          data: {
            mode: 'hybrid',
            latency_ms: 240,
            hits: [{
              document_id: 'document-1',
              chunk_id: 'chunk-1',
              excerpt: 'Турагенту важно быстро получить подтверждение трансфера.',
              permalink: 'https://t.me/source/1',
              published_at: '2026-08-05T10:00:00Z',
              provenance: { source_title: 'Чат турагентов', modes: ['vector', 'lexical'] },
            }],
          },
        };
      }
      return { items: [] };
    });
  });

  it('sends a natural-language query for the selected business and renders sourced results', async () => {
    render(<KnowledgeMarketOverview businessOptions={[{ id: 'business-1', name: 'Riderra' }]} />);

    const input = await screen.findByPlaceholderText(/какие проблемы с трансферами/i);
    fireEvent.change(input, { target: { value: 'Что волнует турагентов при заказе трансфера?' } });
    fireEvent.click(screen.getByRole('button', { name: 'Найти' }));

    await waitFor(() => expect(newAuth.makeRequest).toHaveBeenCalledWith(
      '/admin/knowledge/embeddings/search',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          business_id: 'business-1',
          query: 'Что волнует турагентов при заказе трансфера?',
          purpose: 'market',
          limit: 12,
          consumer: 'admin_market_knowledge_search',
        }),
      }),
    ));
    expect(await screen.findByText('Чат турагентов')).toBeInTheDocument();
    expect(screen.getByText(/быстро получить подтверждение трансфера/)).toBeInTheDocument();
  });
});
