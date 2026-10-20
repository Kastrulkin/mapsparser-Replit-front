import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ContentReferences } from './ContentReferences';

const { request } = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock('@/lib/auth_new', () => ({ newAuth: { makeRequest: request } }));
const catalogue = {
  industry_label: 'Пошив брендированной одежды', settings_version: 0,
  can_manage: true, can_moderate: false, pending: [],
  items: [{ id: 'default', source_name: 'BOMONTI', source_url: 'https://bomonti.pro/production',
    techniques: ['Показать образец и детали'], scope: 'industry', owned: false,
    moderation: 'default', enabled: true, version: 1 }],
};

describe('content references', () => {
  beforeEach(() => { request.mockReset(); });
  afterEach(() => vi.unstubAllGlobals());

  it.each(['telegram', 'max'])('uses the %s session for the same source report', async (surface) => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(catalogue), {
      status: 200, headers: { 'Content-Type': 'application/json' },
    }));
    vi.stubGlobal('fetch', fetchMock);
    const headers = () => ({ 'X-LocalOS-Session': `${surface}-test-session` });
    render(<ContentReferences businessId="a" open onOpenChange={vi.fn()} headers={headers} />);
    await screen.findByRole('button', { name: 'BOMONTI' });
    expect(request).not.toHaveBeenCalled();
    expect(fetchMock.mock.calls[0][0]).toBe('/api/content-voice/references?business_id=a');
    expect(fetchMock.mock.calls[0][1].headers.get('X-LocalOS-Session')).toBe(`${surface}-test-session`);
  });

  it('does not load a hidden settings panel', () => {
    render(<ContentReferences businessId="a" open={false} onOpenChange={vi.fn()} />);
    expect(request).not.toHaveBeenCalled();
    expect(screen.queryByText('BOMONTI')).toBeNull();
  });

  it('disables only this business and renders saved selection', async () => {
    request.mockResolvedValueOnce(catalogue).mockResolvedValueOnce({ ...catalogue,
      settings_version: 1, items: [{ ...catalogue.items[0], enabled: false }] });
    render(<ContentReferences businessId="a" open onOpenChange={vi.fn()} />);
    fireEvent.click(await screen.findByRole('button', { name: 'BOMONTI', exact: true }));
    fireEvent.click(screen.getByText('Использование ориентира в новых черновиках'));
    fireEvent.click(await screen.findByRole('button', { name: 'Отключить BOMONTI' }));
    await screen.findByRole('button', { name: 'Включить BOMONTI' });
    expect(JSON.parse(request.mock.calls[1][1].body)).toEqual({
      action: 'disable', id: 'default', expected_version: 0, business_id: 'a',
    });
    expect(screen.queryByText(/Включить в общий набор/)).toBeNull();
  });

  it('saves an own reference privately unless sharing is explicitly selected', async () => {
    request.mockResolvedValue(catalogue);
    render(<ContentReferences businessId="a" open onOpenChange={vi.fn()} />);
    await screen.findByRole('button', { name: 'BOMONTI' });
    fireEvent.change(screen.getByLabelText('Название компании или примера'), { target: { value: 'Моя мастерская' } });
    fireEvent.change(screen.getByLabelText('Публичная ссылка'), { target: { value: 'https://example.com/work' } });
    fireEvent.change(screen.getByLabelText('Что взять из примера'), { target: { value: 'Показать общий вид вещи и детали отделки' } });
    fireEvent.click(screen.getByRole('button', { name: 'Добавить ориентир' }));
    await waitFor(() => expect(request).toHaveBeenCalledTimes(2));
    expect(JSON.parse(request.mock.calls[1][1].body).submit_for_review).toBe(false);
  });

  it('discards a late response from the previous business', async () => {
    let resolveOld: (value: unknown) => void = () => {};
    request.mockReturnValueOnce(new Promise((resolve) => { resolveOld = resolve; }))
      .mockResolvedValueOnce({ ...catalogue, items: [], industry_label: 'Школа' });
    const view = render(<ContentReferences businessId="a" open onOpenChange={vi.fn()} />);
    view.rerender(<ContentReferences businessId="b" open onOpenChange={vi.fn()} />);
    await screen.findByText('Школа');
    await act(async () => { resolveOld(catalogue); });
    expect(screen.queryByText('BOMONTI')).toBeNull();
    expect(screen.getByText('Школа')).toBeTruthy();
  });

  it('shows load failure and retries without writing', async () => {
    request.mockRejectedValueOnce(new Error('Временно недоступно')).mockResolvedValueOnce(catalogue);
    render(<ContentReferences businessId="a" open onOpenChange={vi.fn()} />);
    expect(await screen.findByRole('alert')).toHaveTextContent('Временно недоступно');
    fireEvent.click(screen.getByRole('button', { name: 'Обновить список' }));
    await screen.findByRole('button', { name: 'BOMONTI' });
    expect(request.mock.calls.every((call) => !call[1])).toBe(true);
  });
});
