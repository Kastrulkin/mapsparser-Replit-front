import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { newAuth } from '../../lib/auth_new';
import { OutreachMessageQueue } from './OutreachMessageQueue';

vi.mock('../../lib/auth_new', () => ({
  newAuth: {
    makeRequest: vi.fn(),
  },
}));

describe('OutreachMessageQueue', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows current touches as messages with delivery and reply states', async () => {
    vi.mocked(newAuth.makeRequest).mockResolvedValue({
      items: [
        {
          touch_id: 'touch-1',
          lead_id: 'lead-1',
          workstream_id: 'workstream-1',
          lead_name: 'Yes Apart',
          recipient: 'pr@yesapart.com',
          channel: 'email',
          sequence_index: 0,
          campaign_version: 11,
          sender_identity: 'localosgo@gmail.com',
          provider_message_id: '<message-1@localos.pro>',
          subject: 'Идея для соседей',
          message_text: 'Хотим предложить локальный проект для семей.',
          scheduled_at: '2026-07-28T14:00:00+03:00',
          status: 'delivered',
        },
        {
          touch_id: 'touch-2',
          lead_id: 'lead-2',
          workstream_id: 'workstream-2',
          lead_name: 'Кидбург',
          recipient: 'https://vk.com/kidburg',
          channel: 'vk',
          sequence_index: 1,
          campaign_version: 4,
          message_text: 'Прислать несколько идей?',
          reply_payload_json: { raw_reply: 'Да, пришлите.' },
          replied_at: '2026-07-28T15:00:00+03:00',
          status: 'replied',
        },
      ],
      summary: { all: 2, delivered: 1, replied: 1 },
      total: 2,
    });
    const openLead = vi.fn();

    render(
      <OutreachMessageQueue
        query=""
        scope="all"
        businessId=""
        channel=""
        status=""
        onChannelChange={vi.fn()}
        onStatusChange={vi.fn()}
        onOpenLead={openLead}
      />,
    );

    expect(await screen.findByText('Yes Apart')).toBeInTheDocument();
    expect(screen.getAllByText('Доставлено').length).toBeGreaterThan(1);
    expect(screen.getByText('Получен ответ')).toBeInTheDocument();
    expect(screen.getByText('Да, пришлите.')).toBeInTheDocument();
    expect(screen.getByText('pr@yesapart.com')).toBeInTheDocument();
    expect(screen.getByText('От: localosgo@gmail.com')).toBeInTheDocument();
    expect(screen.getByText('ID: <message-1@localos.pro>')).toBeInTheDocument();

    const openButtons = screen.getAllByRole('button', { name: 'Открыть лид' });
    await userEvent.click(openButtons[0]);
    expect(openLead).toHaveBeenCalledWith('lead-1', 'workstream-1');
    await waitFor(() => expect(newAuth.makeRequest).toHaveBeenCalledOnce());
  });
});

it('opens an exact letter inside the shared letters list with its full text', async () => {
  vi.mocked(newAuth.makeRequest).mockResolvedValue({ items: [{ touch_id: 'control', campaign_id: 'campaign-1', lead_id: 'lead-1', workstream_id: 'work-1', recipient: 'demyanovap@yandex.ru', sender_identity: 'localosgo@gmail.com', subject: 'Проверка отправки LocalOS', message_text: 'Контрольное письмо', status: 'queued' }], summary: { all: 1, queued: 1 } });
  render(<OutreachMessageQueue query="" scope="client_partnership" businessId="riderra" channel="" status="" campaignId="campaign-1" presentation="letters" onChannelChange={() => {}} onStatusChange={() => {}} onOpenLead={() => {}} />);
  expect(await screen.findByText('Проверка отправки LocalOS')).toBeInTheDocument();
  expect(screen.getByRole('heading', { name: 'Письма' })).toBeInTheDocument();
  const request = String(vi.mocked(newAuth.makeRequest).mock.calls.at(-1)?.[0]);
  expect(request).toContain('campaign_id=campaign-1');
  expect(request).toContain('business_id=riderra');
  expect(screen.getByText('Полный текст письма').parentElement?.hasAttribute('open')).toBe(true);
});
