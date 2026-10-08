import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { OutreachDeliveryCard } from './OutreachDeliveryCard';
const { request } = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock('@/lib/auth_new', () => ({ newAuth: { makeRequest: request } }));
afterEach(() => { cleanup(); request.mockReset(); });
const campaign = { business_id: 'riderra', touches: [{ id: 'touch', recipient: 'test@example.com', sender_identity: 'sender@example.com', subject: 'Проверка', generated_text: 'Контрольный текст', status: 'scheduled' }], deliveries: [{ touch_id: 'touch', delivery_status: 'queued' }], inbound_events: [] };
it('opens the exact queued letter without claiming it was sent', async () => {
  request.mockResolvedValue({ campaign });
  render(<OutreachDeliveryCard campaignId="campaign-1" businessId="riderra" />);
  expect(await screen.findByText('Контрольный текст')).toBeInTheDocument();
  expect(screen.getByText('В очереди')).toBeInTheDocument();
  expect(screen.getByText('test@example.com')).toBeInTheDocument();
  expect(request).toHaveBeenCalledWith('/outreach/campaigns/campaign-1');
  expect(request.mock.calls.every(call => call.length === 1)).toBe(true);
});
it('does not show another business letter', async () => {
  request.mockResolvedValue({ campaign });
  render(<OutreachDeliveryCard campaignId="campaign-1" businessId="organica" />);
  expect(await screen.findByRole('alert')).toHaveTextContent('недоступно');
  expect(screen.queryByText('Контрольный текст')).not.toBeInTheDocument();
});
it('ignores a late response after switching business', async () => {
  let resolve: (value: unknown) => void = () => {};
  request.mockImplementationOnce(() => new Promise(done => { resolve = done; })).mockResolvedValue({ campaign: { ...campaign, business_id: 'organica', touches: [] } });
  const view = render(<OutreachDeliveryCard campaignId="campaign-1" businessId="riderra" />);
  view.rerender(<OutreachDeliveryCard campaignId="campaign-2" businessId="organica" />);
  await waitFor(() => expect(request).toHaveBeenCalledTimes(2));
  resolve({ campaign });
  await waitFor(() => expect(screen.queryByText('Контрольный текст')).not.toBeInTheDocument());
});
