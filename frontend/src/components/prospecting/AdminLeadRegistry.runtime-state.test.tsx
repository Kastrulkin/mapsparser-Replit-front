import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { newAuth } from '@/lib/auth_new';

import { AdminLeadRegistry, outreachDefaultsForWorkstream, workstreamLabel } from './AdminLeadRegistry';

const staleCampaign = {
  id: 'campaign-estem-stale',
  version: 1,
  status: 'draft',
  requires_regeneration: true,
  touches: [{
    id: 'touch-estem-email',
    sequence_index: 0,
    channel: 'email',
    status: 'draft',
    channel_status: 'recipient_missing',
    contact_point_id: null,
    generated_text: 'Эстем, здравствуйте! Старый текст.',
    message_brief_json: { channel_status: 'ready' },
    quality_gate_json: {
      passed: true,
      verdict: 'approve',
      total_score: 18,
      max_score: 18,
      criterion_scores: {},
      reason_codes: [],
    },
  }],
  inbound_events: [],
  deliveries: [],
};

const leadPayload = {
  leads: [{
    id: 'estem',
    name: 'Эстем',
    category: 'Клиника',
    city: 'Санкт-Петербург',
    workstreams: [{
      id: 'ws-estem',
      workstream_type: 'localos_sales',
      status: 'postponed',
      contact_points: [{
        id: 'different-email',
        type: 'email',
        value: 'office@estem.example',
        verification_status: 'confirmed_source',
      }],
    }],
  }],
  client_options: [],
  business_category_options: [],
};

describe('AdminLeadRegistry current campaign runtime state', () => {
  beforeEach(() => {
    window.history.replaceState({}, '', '?lead=estem&workstream=ws-estem');
    vi.spyOn(newAuth, 'makeRequest').mockImplementation(async (url) => {
      const requestUrl = String(url);
      if (requestUrl.startsWith('/admin/prospecting/leads?')) return leadPayload;
      if (requestUrl === '/outreach/sender-accounts?scope_type=platform') {
        return { sender_accounts: [] };
      }
      if (requestUrl.startsWith('/admin/prospecting/leads/estem/contact-intelligence?')) {
        return {
          contacts: leadPayload.leads[0].workstreams[0].contact_points,
          selected_recipient: null,
          job: null,
        };
      }
      if (requestUrl === '/outreach/workstreams/ws-estem/campaigns') {
        return { campaigns: [staleCampaign] };
      }
      return {};
    });
  });

  afterEach(() => {
    window.history.replaceState({}, '', '/');
    vi.restoreAllMocks();
  });

  it('does not present a saved 18/18 score as current after runtime invalidates the recipient', async () => {
    render(<AdminLeadRegistry businessOptions={[]} senderBusinessLabel="LocalOS" />);

    expect((await screen.findAllByText('Эстем')).length).toBeGreaterThan(0);
    await waitFor(() => expect(newAuth.makeRequest).toHaveBeenCalledWith(
      '/outreach/workstreams/ws-estem/campaigns',
    ));
    expect(screen.queryByText('18/18')).not.toBeInTheDocument();
  });

  it('uses top-level runtime recipient_missing ahead of saved brief readiness and another contact', async () => {
    render(<AdminLeadRegistry businessOptions={[]} senderBusinessLabel="LocalOS" />);

    await waitFor(() => expect(newAuth.makeRequest).toHaveBeenCalledWith(
      '/outreach/workstreams/ws-estem/campaigns',
    ));
    expect(await screen.findByText(/\u0421\u0442\u0430\u0440\u044b\u0439 \u0442\u0435\u043a\u0441\u0442/)).toBeInTheDocument();
    expect(screen.queryByText('Контакт найден')).not.toBeInTheDocument();
    expect(screen.getByText('Нет контакта')).toBeInTheDocument();
  });
});

describe('AdminLeadRegistry creator invitation setup', () => {
  afterEach(() => {
    window.history.replaceState({}, '', '/');
    vi.restoreAllMocks();
  });

  it('uses a single LocalOS email touch for creator collaborations without changing other defaults', () => {
    expect(outreachDefaultsForWorkstream('creator_collaboration')).toEqual({
      senderMode: 'localos_for_partner',
      sequenceChannels: ['email'],
      sequenceDays: [0],
    });
    expect(outreachDefaultsForWorkstream('client_partnership')).toEqual({
      senderMode: 'partner_business',
      sequenceChannels: ['telegram', 'email', 'max', 'vk'],
      sequenceDays: [0, 3, 7, 12],
    });
    expect(outreachDefaultsForWorkstream('localos_sales').senderMode).toBe('localos');
    expect(workstreamLabel({
      id: 'creator-ws',
      workstream_type: 'creator_collaboration',
      client_business_name: 'Весёлая расчёска',
    } as never)).toBe('Автор LocalOS');
  });

  it('shows the platform email sender selector and no extra creator touches', async () => {
    const creatorLead = {
      id: 'creator-lead',
      name: 'Экологические экскурсии',
      category: 'creator',
      city: 'Санкт-Петербург',
      workstreams: [{
        id: 'creator-ws',
        workstream_type: 'creator_collaboration',
        client_business_name: 'Весёлая расчёска',
        status: 'new',
        contact_points: [{
          id: 'creator-email',
          type: 'email',
          value: 'creator@example.com',
          verification_status: 'confirmed_source',
        }],
        selected_recipient: {
          id: 'creator-email',
          type: 'email',
          value: 'creator@example.com',
          verification_status: 'confirmed_source',
        },
      }],
    };
    window.history.replaceState({}, '', '?lead=creator-lead&workstream=creator-ws');
    vi.spyOn(newAuth, 'makeRequest').mockImplementation(async (url) => {
      const requestUrl = String(url);
      if (requestUrl.startsWith('/admin/prospecting/leads?')) {
        return { leads: [creatorLead], client_options: [], business_category_options: [] };
      }
      if (requestUrl === '/outreach/sender-accounts?scope_type=platform') {
        return { sender_accounts: [{
          id: 'localos-email',
          channel: 'email',
          sender_identity: 'localosgo@gmail.com',
          status: 'connected',
          outreach_enabled: true,
          capabilities: { direct_send: true, reply_sync: true },
        }] };
      }
      if (requestUrl.startsWith('/admin/prospecting/leads/creator-lead/contact-intelligence?')) {
        return {
          contacts: creatorLead.workstreams[0].contact_points,
          selected_recipient: creatorLead.workstreams[0].selected_recipient,
          job: null,
        };
      }
      if (requestUrl === '/outreach/workstreams/creator-ws/campaigns') return { campaigns: [] };
      return {};
    });

    render(<AdminLeadRegistry businessOptions={[]} senderBusinessLabel="LocalOS" />);

    expect(await screen.findByText('Приглашение автора от LocalOS')).toBeInTheDocument();
    expect(screen.getAllByText('Автор LocalOS').length).toBeGreaterThan(0);
    expect(screen.queryByText('Лид-партнёр · Весёлая расчёска')).not.toBeInTheDocument();
    const sequenceSection = screen.getByRole('button', { name: /Цепочка, расписание и запуск/ });
    await waitFor(() => expect(sequenceSection).toHaveTextContent('Первый шаг: Email'));
    fireEvent.click(sequenceSection);
    const channel = screen.getByRole('combobox', { name: 'Канал касания 1' }) as HTMLSelectElement;
    expect(channel.value).toBe('email');
    expect(screen.queryByRole('combobox', { name: 'Канал касания 2' })).not.toBeInTheDocument();
    await waitFor(() => expect(
      (screen.getByRole('combobox', { name: 'Отправитель касания 1' }) as HTMLSelectElement).value,
    ).toBe('localos-email'));
  });
});
