import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { PromotionLeadDialog } from './PromotionLeadDialog';
import { promotionContent, promotionLinkSearch, promotionAttribution } from '@/content/promotionContent';

const setup = () => {
  render(<MemoryRouter initialEntries={['/lokalnye-blogery?utm_source=search&utm_campaign=local']}><PromotionLeadDialog page={promotionContent().bloggers} english={false} /></MemoryRouter>);
  fireEvent.click(screen.getByRole('button', { name: 'Хочу клиентов' }));
  fireEvent.change(screen.getByLabelText('Имя'), { target: { value: 'Тест' } });
  fireEvent.change(screen.getByLabelText('Номер телефона'), { target: { value: '+79991234567' } });
  fireEvent.click(screen.getByRole('checkbox'));
};

afterEach(() => { vi.unstubAllGlobals(); sessionStorage.clear(); });

describe('managed promotion contact', () => {
  it('sends a phone-only request with the correct direction and attribution', async () => {
    const fetcher = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ success: true }) });
    vi.stubGlobal('fetch', fetcher);
    setup();
    fireEvent.click(screen.getByRole('button', { name: 'Отправить заявку' }));
    expect(await screen.findByText('Спасибо! Заявка принята')).toBeInTheDocument();
    const body = JSON.parse(fetcher.mock.calls[0][1].body);
    expect(body).toMatchObject({ name: 'Тест', phone: '+79991234567', direction: 'bloggers', page: '/lokalnye-blogery', attribution: { utm_source: 'search', utm_campaign: 'local' }, personal_data_consent: true });
    expect(body).not.toHaveProperty('email');
  });

  it('retains entries on delivery failure, blocks concurrent submission and allows retry', async () => {
    let resolve: (value: unknown) => void = () => undefined;
    const pending = new Promise((done) => { resolve = done; });
    const fetcher = vi.fn().mockReturnValueOnce(pending).mockResolvedValue({ ok: true, json: async () => ({ success: true }) });
    vi.stubGlobal('fetch', fetcher);
    setup();
    const button = screen.getByRole('button', { name: 'Отправить заявку' });
    fireEvent.click(button);
    fireEvent.click(button);
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('button', { name: 'Отправляем…' })).toBeDisabled();
    resolve({ ok: false, json: async () => ({ error: 'delivery_failed' }) });
    expect(await screen.findByRole('alert')).toBeInTheDocument();
    expect(screen.getByLabelText('Имя')).toHaveValue('Тест');
    expect(screen.getByLabelText('Номер телефона')).toHaveValue('+79991234567');
    expect(screen.queryByText('Спасибо! Заявка принята')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Отправить заявку' }));
    expect(await screen.findByText('Спасибо! Заявка принята')).toBeInTheDocument();
  });

  it('does not trust an HTTP 200 without an explicit successful delivery result', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ success: false }) }));
    setup();
    fireEvent.click(screen.getByRole('button', { name: 'Отправить заявку' }));
    expect(await screen.findByRole('alert')).toBeInTheDocument();
    expect(screen.queryByText('Спасибо! Заявка принята')).not.toBeInTheDocument();
  });

  it('rejects a phone with no digits before making a delivery request', async () => {
    const fetcher = vi.fn();
    vi.stubGlobal('fetch', fetcher);
    setup();
    fireEvent.change(screen.getByLabelText('Номер телефона'), { target: { value: '-------' } });
    fireEvent.click(screen.getByRole('button', { name: 'Отправить заявку' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('от 7 до 15 цифр');
    expect(fetcher).not.toHaveBeenCalled();
  });

  it('collects only attribution fields rather than arbitrary query parameters', () => {
    expect(promotionAttribution('?phone=private&token=secret&utm_source=search')).toEqual({ utm_source: 'search' });
    expect(promotionLinkSearch('?lang=ru&phone=private&token=secret&utm_source=search')).toBe('?lang=ru&utm_source=search');
  });
});
