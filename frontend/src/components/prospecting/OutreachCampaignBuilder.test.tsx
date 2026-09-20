import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { newAuth } from '@/lib/auth_new';

import { OutreachCampaignBuilder } from './OutreachCampaignBuilder';

const savedCampaign = (recipient: string | null) => ({
  id: 'campaign-1',
  version: 1,
  status: 'draft',
  generation_current: true,
  requires_regeneration: false,
  touches: [{
    id: 'touch-1',
    sequence_index: 0,
    channel: 'email',
    channel_status: 'ready',
    sender_account_id: 'sender-1',
    day_offset: 0,
    angle: 'signal',
    text: 'Проверенный текст.',
    generated_text: 'Проверенный текст.',
    recipient,
    quality_gate_json: { passed: true, total_score: 18, max_score: 18 },
  }],
});

const preview = (recipient: string | null) => ({
  status: 'ready',
  channel_availability: {},
  quality_gate: { passed: true, total_score: 18, max_score: 18 },
  touches: [{
    sequence_index: 0,
    channel: 'email',
    channel_status: 'ready',
    day_offset: 0,
    angle: 'signal',
    text: 'Новый проверенный текст.',
    recipient,
    quality_gate: { passed: true, total_score: 18, max_score: 18 },
  }],
});

describe('OutreachCampaignBuilder', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('labels an operator-approved partnership proposal as an idea, not a public fact', async () => {
    vi.spyOn(newAuth, 'makeRequest').mockImplementation(async (url) => {
      if (String(url).endsWith('/campaigns')) {
        return { campaigns: [] };
      }
      if (String(url).endsWith('/preview')) {
        return {
          preview: {
            status: 'ready',
            channel_availability: {},
            quality_gate: { passed: true, total_score: 18, max_score: 18 },
            touches: [{
              sequence_index: 0,
              channel: 'vk_manual',
              day_offset: 0,
              angle: 'signal',
              text: 'Тестовое сообщение?',
              channel_status: 'manual',
              evidence_kind: 'operator_approved_partnership_reason',
              observation: 'Предложить совместный показ в ТРК Гранд Каньон.',
              relevance_bridge: 'У каждого участника есть понятная роль.',
              template_selection: {
                status: 'selected',
                key: 'local_partnership_acquisition_v1',
                version: 1,
                label: 'Новые клиенты через партнёрства',
              },
              quality_gate: { passed: true, total_score: 18, max_score: 18 },
            }],
          },
        };
      }
      return {};
    });
    const user = userEvent.setup();

    render(<OutreachCampaignBuilder workstreamId="workstream-1" />);
    await user.click(screen.getByRole('button', { name: 'Показать всю цепочку' }));

    expect(await screen.findByText('Подтверждённая идея:')).toBeInTheDocument();
    expect(screen.queryByText('Факт:')).not.toBeInTheDocument();
    expect(screen.getByText('Почему предложение подходит:')).toBeInTheDocument();
    expect(screen.getByText('Основа: Новые клиенты через партнёрства')).toBeInTheDocument();
  });

  it('shows the saved touch recipient before the campaign approval control', async () => {
    vi.spyOn(newAuth, 'makeRequest').mockImplementation(async (url) => {
      if (String(url).endsWith('/campaigns')) return { campaigns: [savedCampaign('owner@example.invalid')] };
      return {};
    });

    render(<OutreachCampaignBuilder workstreamId="workstream-1" />);

    expect(await screen.findByText('Получатель: owner@example.invalid')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Утвердить цепочку и перейти к отправке' })).toBeVisible();
  });

  it('shows the exact server recipient from a fresh preview', async () => {
    vi.spyOn(newAuth, 'makeRequest').mockImplementation(async (url) => {
      if (String(url).endsWith('/campaigns')) return { campaigns: [] };
      if (String(url).endsWith('/preview')) return { preview: preview('reviewed.telegram@example.invalid') };
      return {};
    });
    const user = userEvent.setup();

    render(<OutreachCampaignBuilder workstreamId="workstream-1" />);
    await user.click(screen.getByRole('button', { name: 'Показать всю цепочку' }));

    expect(await screen.findByText('Получатель: reviewed.telegram@example.invalid')).toBeVisible();
  });

  it('warns when a touch has no server recipient instead of guessing one', async () => {
    vi.spyOn(newAuth, 'makeRequest').mockImplementation(async (url) => {
      if (String(url).endsWith('/campaigns')) return { campaigns: [savedCampaign(null)] };
      return {};
    });

    render(<OutreachCampaignBuilder workstreamId="workstream-1" />);

    expect(await screen.findByText('Получатель не указан для этого касания.')).toBeVisible();
  });

  it('renders an untrusted recipient as ordinary text', async () => {
    const recipient = '<img src=x onerror=alert(1)> reviewed@example.invalid';
    vi.spyOn(newAuth, 'makeRequest').mockImplementation(async (url) => {
      if (String(url).endsWith('/campaigns')) return { campaigns: [savedCampaign(recipient)] };
      return {};
    });

    const { container } = render(<OutreachCampaignBuilder workstreamId="workstream-1" />);

    expect(await screen.findByText(`Получатель: ${recipient}`)).toBeVisible();
    expect(container.querySelector('img')).not.toBeInTheDocument();
  });

  it('clears recipients from the previous campaign and preview when the workstream changes', async () => {
    vi.spyOn(newAuth, 'makeRequest').mockImplementation(async (url) => {
      const requestUrl = String(url);
      if (requestUrl.endsWith('/workstream-1/campaigns')) return { campaigns: [savedCampaign('saved@example.invalid')] };
      if (requestUrl.endsWith('/workstream-2/campaigns')) return { campaigns: [savedCampaign('new-owner@example.invalid')] };
      if (requestUrl.endsWith('/preview')) return { preview: preview('preview@example.invalid') };
      return {};
    });
    const user = userEvent.setup();
    const view = render(<OutreachCampaignBuilder workstreamId="workstream-1" />);

    expect(await screen.findByText('Получатель: saved@example.invalid')).toBeVisible();
    await user.click(screen.getByRole('button', { name: 'Показать всю цепочку' }));
    expect(await screen.findByText('Получатель: preview@example.invalid')).toBeVisible();

    view.rerender(<OutreachCampaignBuilder workstreamId="workstream-2" />);

    expect(await screen.findByText('Получатель: new-owner@example.invalid')).toBeVisible();
    expect(screen.queryByText('Получатель: saved@example.invalid')).not.toBeInTheDocument();
    expect(screen.queryByText('Получатель: preview@example.invalid')).not.toBeInTheDocument();
  });
});
