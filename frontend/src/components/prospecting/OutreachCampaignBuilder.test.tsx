import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { newAuth } from '@/lib/auth_new';

import { OutreachCampaignBuilder } from './OutreachCampaignBuilder';

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
});
