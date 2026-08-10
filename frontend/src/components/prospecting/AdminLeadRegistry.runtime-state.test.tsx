import { render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { newAuth } from '@/lib/auth_new';

import { AdminLeadRegistry } from './AdminLeadRegistry';

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
