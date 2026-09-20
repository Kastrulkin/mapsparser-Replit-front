import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { newAuth } from '@/lib/auth_new';

import { OutreachCampaignBuilder } from './OutreachCampaignBuilder';

const savedCampaign = (id: string, recipient: string, text: string, version: number) => ({
  id,
  version,
  status: 'draft',
  generation_current: true,
  requires_regeneration: false,
  touches: [{
    id: `touch-${id}`,
    sequence_index: 0,
    channel: 'email',
    channel_status: 'ready',
    sender_account_id: `sender-${id}`,
    day_offset: 0,
    angle: 'signal',
    subject: `Тема ${id}`,
    text,
    generated_text: text,
    approved_text: text,
    recipient,
    quality_gate_json: { passed: true, total_score: 18, max_score: 18 },
  }],
});

const campaignPreview = (recipient: string, text: string) => ({
  status: 'ready',
  channel_availability: {},
  quality_gate: { passed: true, total_score: 18, max_score: 18 },
  touches: [{
    sequence_index: 0,
    channel: 'email',
    channel_status: 'ready',
    day_offset: 0,
    angle: 'signal',
    subject: 'Новая тема B',
    text,
    recipient,
    quality_gate: { passed: true, total_score: 18, max_score: 18 },
  }],
});

describe('OutreachCampaignBuilder approval consent boundary', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('does not approve saved campaign A while an unsaved preview B is visible', async () => {
    const requests: string[] = [];
    vi.spyOn(newAuth, 'makeRequest').mockImplementation(async (url) => {
      const requestUrl = String(url);
      requests.push(requestUrl);
      if (requestUrl.endsWith('/campaigns')) return {
        campaigns: [savedCampaign('campaign-A', 'owner-a@example.invalid', 'Сохранённый текст A', 1)],
      };
      if (requestUrl.endsWith('/preview')) return {
        preview: campaignPreview('owner-b@example.invalid', 'Новый preview текст B'),
      };
      return {};
    });
    const user = userEvent.setup();

    render(<OutreachCampaignBuilder workstreamId="workstream-1" />);
    expect(await screen.findByText('Получатель: owner-a@example.invalid')).toBeVisible();
    await user.click(screen.getByRole('button', { name: 'Показать всю цепочку' }));
    expect(await screen.findByText('Получатель: owner-b@example.invalid')).toBeVisible();
    expect(screen.getByText('Новый preview текст B')).toBeVisible();

    expect(screen.getByRole('button', { name: 'Утвердить цепочку и перейти к отправке' })).toBeDisabled();
    expect(requests).not.toContain('/outreach/campaigns/campaign-A/approve');
  });

  it('allows approval of an unchanged saved campaign A', async () => {
    const requests: string[] = [];
    vi.spyOn(newAuth, 'makeRequest').mockImplementation(async (url) => {
      const requestUrl = String(url);
      requests.push(requestUrl);
      if (requestUrl.endsWith('/campaigns')) return {
        campaigns: [savedCampaign('campaign-A', 'owner-a@example.invalid', 'Сохранённый текст A', 1)],
      };
      return {};
    });
    const user = userEvent.setup();

    render(<OutreachCampaignBuilder workstreamId="workstream-1" />);
    expect(await screen.findByText('Получатель: owner-a@example.invalid')).toBeVisible();
    await user.click(screen.getByRole('button', { name: 'Утвердить цепочку и перейти к отправке' }));

    expect(requests).toContain('/outreach/campaigns/campaign-A/approve');
  });

  it('approves only saved campaign B after preview B is saved and reloaded', async () => {
    const requests: string[] = [];
    let previewCalls = 0;
    let campaignLoads = 0;
    vi.spyOn(newAuth, 'makeRequest').mockImplementation(async (url) => {
      const requestUrl = String(url);
      requests.push(requestUrl);
      if (requestUrl.endsWith('/campaigns')) {
        campaignLoads += 1;
        return {
          campaigns: campaignLoads === 1
            ? [savedCampaign('campaign-A', 'owner-a@example.invalid', 'Сохранённый текст A', 1)]
            : [
              savedCampaign('campaign-B', 'owner-b@example.invalid', 'Сохранённый текст B', 2),
              savedCampaign('campaign-A', 'owner-a@example.invalid', 'Сохранённый текст A', 1),
            ],
        };
      }
      if (requestUrl.endsWith('/preview')) {
        previewCalls += 1;
        return previewCalls === 1
          ? { preview: campaignPreview('owner-b@example.invalid', 'Новый preview текст B') }
          : {
            preview: campaignPreview('transient-b@example.invalid', 'Transient preview после save B'),
            campaign: { id: 'campaign-B' },
          };
      }
      return {};
    });
    const user = userEvent.setup();

    render(<OutreachCampaignBuilder workstreamId="workstream-1" />);
    expect(await screen.findByText('Получатель: owner-a@example.invalid')).toBeVisible();
    await user.click(screen.getByRole('button', { name: 'Показать всю цепочку' }));
    expect(await screen.findByText('Новый preview текст B')).toBeVisible();
    await user.click(screen.getByRole('button', { name: 'Сохранить изменения' }));
    expect(await screen.findByText('Сохранённый текст B')).toBeVisible();
    expect(screen.queryByText('Transient preview после save B')).not.toBeInTheDocument();
    expect(screen.getByRole('combobox', { name: 'Версия' })).toHaveValue('campaign-B');

    await user.click(screen.getByRole('button', { name: 'Утвердить цепочку и перейти к отправке' }));

    expect(requests).toContain('/outreach/campaigns/campaign-B/approve');
    expect(requests).not.toContain('/outreach/campaigns/campaign-A/approve');
  });

  it('blocks approval after an unsaved schedule change', async () => {
    const requests: string[] = [];
    vi.spyOn(newAuth, 'makeRequest').mockImplementation(async (url) => {
      const requestUrl = String(url);
      requests.push(requestUrl);
      if (requestUrl.endsWith('/campaigns')) return {
        campaigns: [savedCampaign('campaign-A', 'owner-a@example.invalid', 'Сохранённый текст A', 1)],
      };
      return {};
    });

    render(<OutreachCampaignBuilder workstreamId="workstream-1" />);
    await screen.findByText('Получатель: owner-a@example.invalid');
    fireEvent.change(screen.getByRole('combobox', { name: 'Канал касания 1' }), { target: { value: 'telegram' } });

    expect(screen.getByText('Порядок изменён. Обновите preview; прежний approval не будет перенесён.')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Утвердить цепочку и перейти к отправке' })).toBeDisabled();
    expect(requests).not.toContain('/outreach/campaigns/campaign-A/approve');
  });

  it('blocks approval after an unsaved text edit is accepted into the preview', async () => {
    const requests: string[] = [];
    vi.spyOn(newAuth, 'makeRequest').mockImplementation(async (url) => {
      const requestUrl = String(url);
      requests.push(requestUrl);
      if (requestUrl.endsWith('/campaigns')) return {
        campaigns: [savedCampaign('campaign-A', 'owner-a@example.invalid', 'Сохранённый текст A', 1)],
      };
      return {};
    });
    const user = userEvent.setup();

    render(<OutreachCampaignBuilder workstreamId="workstream-1" />);
    await screen.findByText('Сохранённый текст A');
    await user.click(screen.getByRole('button', { name: 'Редактировать' }));
    const textEditor = screen.getByRole('textbox', { name: 'Текст сообщения' });
    await user.clear(textEditor);
    await user.type(textEditor, 'Несохранённая правка текста B');
    await user.click(screen.getByRole('button', { name: 'Принять изменения' }));

    expect(screen.getByText('Несохранённая правка текста B')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Утвердить цепочку и перейти к отправке' })).toBeDisabled();
    expect(requests).not.toContain('/outreach/campaigns/campaign-A/approve');
  });

  it('removes old pilot-dispatch permission when a different unsaved preview is visible', async () => {
    const requests: string[] = [];
    vi.spyOn(newAuth, 'makeRequest').mockImplementation(async (url) => {
      const requestUrl = String(url);
      requests.push(requestUrl);
      if (requestUrl.endsWith('/campaigns')) return {
        campaigns: [{
          ...savedCampaign('campaign-A', 'owner-a@example.invalid', 'Сохранённый текст A', 1),
          status: 'approved',
        }],
      };
      if (requestUrl.endsWith('/campaign-A/pilot-preflight')) {
        return {
          pilot_readiness: {
            can_dispatch_first_touch: true,
            next_action: 'Можно отправить пилот.',
          },
        };
      }
      if (requestUrl.endsWith('/preview')) return {
        preview: campaignPreview('owner-b@example.invalid', 'Несохранённый preview B'),
      };
      return {};
    });
    const user = userEvent.setup();

    render(<OutreachCampaignBuilder workstreamId="workstream-1" />);
    await screen.findByText('Получатель: owner-a@example.invalid');
    await user.click(screen.getByRole('button', { name: 'Проверить перед отправкой' }));
    expect(await screen.findByRole('button', { name: 'Отправить только первое касание' })).toBeVisible();
    await user.click(screen.getByRole('button', { name: 'Показать всю цепочку' }));
    expect(await screen.findByText('Несохранённый preview B')).toBeVisible();

    expect(screen.queryByRole('button', { name: 'Отправить только первое касание' })).not.toBeInTheDocument();
    expect(requests).not.toContain('/outreach/campaigns/campaign-A/pilot-dispatch-first-touch');
  });

  it('does not fall back to approval of A when save B reloads without campaign B', async () => {
    const requests: string[] = [];
    let previewCalls = 0;
    let campaignLoads = 0;
    vi.spyOn(newAuth, 'makeRequest').mockImplementation(async (url) => {
      const requestUrl = String(url);
      requests.push(requestUrl);
      if (requestUrl.endsWith('/campaigns')) {
        campaignLoads += 1;
        return {
          campaigns: [savedCampaign('campaign-A', 'owner-a@example.invalid', 'Сохранённый текст A', 1)],
        };
      }
      if (requestUrl.endsWith('/preview')) {
        previewCalls += 1;
        return previewCalls === 1
          ? { preview: campaignPreview('owner-b@example.invalid', 'Новый preview текст B') }
          : {
            preview: campaignPreview('transient-b@example.invalid', 'Transient preview после save B'),
            campaign: { id: 'campaign-B' },
          };
      }
      return {};
    });
    const user = userEvent.setup();

    render(<OutreachCampaignBuilder workstreamId="workstream-1" />);
    await screen.findByText('Получатель: owner-a@example.invalid');
    await user.click(screen.getByRole('button', { name: 'Показать всю цепочку' }));
    await user.click(screen.getByRole('button', { name: 'Сохранить изменения' }));
    expect(await screen.findByText('Transient preview после save B')).toBeVisible();

    expect(screen.getByRole('button', { name: 'Утвердить цепочку и перейти к отправке' })).toBeDisabled();
    expect(requests).not.toContain('/outreach/campaigns/campaign-A/approve');
    expect(campaignLoads).toBe(2);
  });

  it('does not fall back to approval of A when save B reload fails', async () => {
    const requests: string[] = [];
    let previewCalls = 0;
    let campaignLoads = 0;
    vi.spyOn(newAuth, 'makeRequest').mockImplementation(async (url) => {
      const requestUrl = String(url);
      requests.push(requestUrl);
      if (requestUrl.endsWith('/campaigns')) {
        campaignLoads += 1;
        if (campaignLoads === 1) {
          return { campaigns: [savedCampaign('campaign-A', 'owner-a@example.invalid', 'Сохранённый текст A', 1)] };
        }
        throw new Error('reload B failed');
      }
      if (requestUrl.endsWith('/preview')) {
        previewCalls += 1;
        return previewCalls === 1
          ? { preview: campaignPreview('owner-b@example.invalid', 'Новый preview текст B') }
          : {
            preview: campaignPreview('transient-b@example.invalid', 'Transient preview после save B'),
            campaign: { id: 'campaign-B' },
          };
      }
      return {};
    });
    const user = userEvent.setup();

    render(<OutreachCampaignBuilder workstreamId="workstream-1" />);
    await screen.findByText('Получатель: owner-a@example.invalid');
    await user.click(screen.getByRole('button', { name: 'Показать всю цепочку' }));
    await user.click(screen.getByRole('button', { name: 'Сохранить изменения' }));
    expect(await screen.findByText('Transient preview после save B')).toBeVisible();

    expect(screen.getByRole('button', { name: 'Утвердить цепочку и перейти к отправке' })).toBeDisabled();
    expect(requests).not.toContain('/outreach/campaigns/campaign-A/approve');
    expect(campaignLoads).toBe(2);
  });

  it('keeps a failed save blocked until cancelling the preview restores saved A', async () => {
    const requests: string[] = [];
    let previewCalls = 0;
    vi.spyOn(newAuth, 'makeRequest').mockImplementation(async (url) => {
      const requestUrl = String(url);
      requests.push(requestUrl);
      if (requestUrl.endsWith('/campaigns')) {
        return { campaigns: [savedCampaign('campaign-A', 'owner-a@example.invalid', 'Сохранённый текст A', 1)] };
      }
      if (requestUrl.endsWith('/preview')) {
        previewCalls += 1;
        if (previewCalls === 1) return { preview: campaignPreview('owner-b@example.invalid', 'Несохранённый preview B') };
        throw new Error('save B failed');
      }
      return {};
    });
    const user = userEvent.setup();

    render(<OutreachCampaignBuilder workstreamId="workstream-1" />);
    await screen.findByText('Сохранённый текст A');
    await user.click(screen.getByRole('button', { name: 'Показать всю цепочку' }));
    expect(await screen.findByText('Несохранённый preview B')).toBeVisible();
    await user.click(screen.getByRole('button', { name: 'Сохранить изменения' }));
    expect(await screen.findByText('save B failed')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Утвердить цепочку и перейти к отправке' })).toBeDisabled();

    await user.click(screen.getByRole('button', { name: 'Отменить правки и показать сохранённую версию' }));
    expect(await screen.findByText('Сохранённый текст A')).toBeVisible();
    expect(screen.queryByText('Несохранённый preview B')).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Утвердить цепочку и перейти к отправке' }));

    expect(requests).toContain('/outreach/campaigns/campaign-A/approve');
  });

  it('selecting saved C after preview B clears B and approves only C', async () => {
    const requests: string[] = [];
    vi.spyOn(newAuth, 'makeRequest').mockImplementation(async (url) => {
      const requestUrl = String(url);
      requests.push(requestUrl);
      if (requestUrl.endsWith('/campaigns')) {
        return {
          campaigns: [
            savedCampaign('campaign-A', 'owner-a@example.invalid', 'Сохранённый текст A', 1),
            savedCampaign('campaign-C', 'owner-c@example.invalid', 'Сохранённый текст C', 3),
          ],
        };
      }
      if (requestUrl.endsWith('/preview')) return { preview: campaignPreview('owner-b@example.invalid', 'Несохранённый preview B') };
      return {};
    });
    const user = userEvent.setup();

    render(<OutreachCampaignBuilder workstreamId="workstream-1" />);
    await screen.findByText('Сохранённый текст A');
    await user.click(screen.getByRole('button', { name: 'Показать всю цепочку' }));
    expect(await screen.findByText('Несохранённый preview B')).toBeVisible();
    await user.selectOptions(screen.getByRole('combobox', { name: 'Версия' }), 'campaign-C');
    expect(await screen.findByText('Сохранённый текст C')).toBeVisible();
    expect(screen.queryByText('Несохранённый preview B')).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Утвердить цепочку и перейти к отправке' }));
    expect(requests).toContain('/outreach/campaigns/campaign-C/approve');
    expect(requests).not.toContain('/outreach/campaigns/campaign-A/approve');
  });

  it('shows the reloaded learning campaign B and approves only B', async () => {
    const requests: string[] = [];
    let campaignLoads = 0;
    vi.spyOn(newAuth, 'makeRequest').mockImplementation(async (url) => {
      const requestUrl = String(url);
      requests.push(requestUrl);
      if (requestUrl.endsWith('/campaigns')) {
        campaignLoads += 1;
        return {
          campaigns: campaignLoads === 1
            ? [savedCampaign('campaign-A', 'owner-a@example.invalid', 'Сохранённый текст A', 1)]
            : [savedCampaign('campaign-B', 'owner-b@example.invalid', 'Сохранённый текст B из learning', 2)],
        };
      }
      if (requestUrl.startsWith('/outreach/learning/strategy-stats?')) {
        return {
          stats: [{
            strategy_fingerprint: 'learning-b',
            recommendation_status: 'candidate_for_reuse',
            dimensions_json: { segment: 'рестораны', channel: 'email', angle: 'signal' },
            positive_reply_count: 2,
            delivered_count: 3,
            confidence: 0.8,
          }],
        };
      }
      if (requestUrl.endsWith('/apply-learning-recommendation')) {
        return {
          preview: campaignPreview('transient-b@example.invalid', 'Transient learning B'),
          campaign: { id: 'campaign-B', version: 2 },
        };
      }
      return {};
    });
    const user = userEvent.setup();

    render(<OutreachCampaignBuilder workstreamId="workstream-1" businessId="business-1" leadSegment="рестораны" />);
    await screen.findByText('Сохранённый текст A');
    await user.click(await screen.findByRole('button', { name: 'Применить в новой версии' }));
    expect(await screen.findByText('Сохранённый текст B из learning')).toBeVisible();
    expect(screen.queryByText('Transient learning B')).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Утвердить цепочку и перейти к отправке' }));
    expect(requests).toContain('/outreach/campaigns/campaign-B/approve');
    expect(requests).not.toContain('/outreach/campaigns/campaign-A/approve');
  });

  it('keeps a learning preview blocked when its saved campaign cannot be reloaded', async () => {
    const requests: string[] = [];
    let campaignLoads = 0;
    vi.spyOn(newAuth, 'makeRequest').mockImplementation(async (url) => {
      const requestUrl = String(url);
      requests.push(requestUrl);
      if (requestUrl.endsWith('/campaigns')) {
        campaignLoads += 1;
        if (campaignLoads === 1) return { campaigns: [savedCampaign('campaign-A', 'owner-a@example.invalid', 'Сохранённый текст A', 1)] };
        throw new Error('learning B reload failed');
      }
      if (requestUrl.startsWith('/outreach/learning/strategy-stats?')) {
        return {
          stats: [{
            strategy_fingerprint: 'learning-b',
            recommendation_status: 'candidate_for_reuse',
            dimensions_json: { segment: 'рестораны', channel: 'email', angle: 'signal' },
          }],
        };
      }
      if (requestUrl.endsWith('/apply-learning-recommendation')) {
        return {
          preview: campaignPreview('owner-b@example.invalid', 'Learning preview B'),
          campaign: { id: 'campaign-B', version: 2 },
        };
      }
      return {};
    });
    const user = userEvent.setup();

    render(<OutreachCampaignBuilder workstreamId="workstream-1" businessId="business-1" leadSegment="рестораны" />);
    await screen.findByText('Сохранённый текст A');
    await user.click(await screen.findByRole('button', { name: 'Применить в новой версии' }));
    expect(await screen.findByText('Learning preview B')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Утвердить цепочку и перейти к отправке' })).toBeDisabled();
    expect(requests).not.toContain('/outreach/campaigns/campaign-A/approve');
  });

  it('dispatches newly saved and approved B only after an explicit confirmation', async () => {
    const requests: string[] = [];
    const confirm = vi.spyOn(window, 'confirm').mockReturnValueOnce(false).mockReturnValueOnce(true);
    let campaignLoads = 0;
    let previewCalls = 0;
    vi.spyOn(newAuth, 'makeRequest').mockImplementation(async (url) => {
      const requestUrl = String(url);
      requests.push(requestUrl);
      if (requestUrl.endsWith('/campaigns')) {
        campaignLoads += 1;
        return {
          campaigns: campaignLoads === 1
            ? [savedCampaign('campaign-A', 'owner-a@example.invalid', 'Сохранённый текст A', 1)]
            : [{
              ...savedCampaign('campaign-B', 'owner-b@example.invalid', 'Сохранённый текст B', 2),
              status: campaignLoads === 2 ? 'draft' : 'approved',
            }],
        };
      }
      if (requestUrl.endsWith('/preview')) {
        previewCalls += 1;
        return previewCalls === 1
          ? { preview: campaignPreview('owner-b@example.invalid', 'Несохранённый preview B') }
          : { preview: campaignPreview('owner-b@example.invalid', 'Transient preview B'), campaign: { id: 'campaign-B', version: 2 } };
      }
      if (requestUrl.endsWith('/campaign-B/pilot-preflight')) {
        return { pilot_readiness: { can_dispatch_first_touch: true, next_action: 'Можно отправить пилот.' } };
      }
      return {};
    });
    const user = userEvent.setup();

    render(<OutreachCampaignBuilder workstreamId="workstream-1" />);
    await screen.findByText('Сохранённый текст A');
    await user.click(screen.getByRole('button', { name: 'Показать всю цепочку' }));
    await user.click(screen.getByRole('button', { name: 'Сохранить изменения' }));
    expect(await screen.findByText('Сохранённый текст B')).toBeVisible();
    await user.click(screen.getByRole('button', { name: 'Утвердить цепочку и перейти к отправке' }));
    expect(await screen.findByRole('button', { name: 'Проверить перед отправкой' })).toBeVisible();
    await user.click(screen.getByRole('button', { name: 'Проверить перед отправкой' }));
    const dispatch = await screen.findByRole('button', { name: 'Отправить только первое касание' });
    await user.click(dispatch);
    expect(confirm).toHaveBeenCalledTimes(1);
    expect(requests).not.toContain('/outreach/campaigns/campaign-B/pilot-dispatch-first-touch');

    await user.click(dispatch);
    expect(requests).toContain('/outreach/campaigns/campaign-B/pilot-dispatch-first-touch');
    expect(requests).not.toContain('/outreach/campaigns/campaign-A/pilot-dispatch-first-touch');
  });

  it('prevents resuming paused A while an unsaved preview B is visible', async () => {
    const requests: string[] = [];
    vi.spyOn(newAuth, 'makeRequest').mockImplementation(async (url) => {
      const requestUrl = String(url);
      requests.push(requestUrl);
      if (requestUrl.endsWith('/campaigns')) {
        return {
          campaigns: [{
            ...savedCampaign('campaign-A', 'owner-a@example.invalid', 'Сохранённый текст A', 1),
            status: 'paused',
          }],
        };
      }
      if (requestUrl.endsWith('/preview')) return { preview: campaignPreview('owner-b@example.invalid', 'Несохранённый preview B') };
      return {};
    });
    const user = userEvent.setup();

    render(<OutreachCampaignBuilder workstreamId="workstream-1" />);
    await screen.findByText('Сохранённый текст A');
    await user.click(screen.getByRole('button', { name: 'Показать всю цепочку' }));
    expect(await screen.findByText('Несохранённый preview B')).toBeVisible();

    expect(screen.getByRole('button', { name: 'Возобновить' })).toBeDisabled();
    expect(requests).not.toContain('/outreach/campaigns/campaign-A/resume');

    await user.click(screen.getByRole('button', { name: 'Отменить правки и показать сохранённую версию' }));
    expect(await screen.findByText('Сохранённый текст A')).toBeVisible();
    await user.click(screen.getByRole('button', { name: 'Возобновить' }));
    expect(requests).toContain('/outreach/campaigns/campaign-A/resume');
  });
});
