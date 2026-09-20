import { StrictMode } from 'react';
import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { newAuth } from '@/lib/auth_new';

import { OutreachCampaignBuilder } from './OutreachCampaignBuilder';

type Deferred<Value> = {
  promise: Promise<Value>;
  resolve: (value: Value) => void;
  reject: (reason?: unknown) => void;
};

const deferred = <Value,>(): Deferred<Value> => {
  let resolvePromise: (value: Value) => void = () => {};
  let rejectPromise: (reason?: unknown) => void = () => {};
  const promise = new Promise<Value>((resolve, reject) => {
    resolvePromise = resolve;
    rejectPromise = reject;
  });
  return {
    promise,
    resolve: (value) => resolvePromise(value),
    reject: (reason) => rejectPromise(reason),
  };
};

const campaign = (id: string, recipient: string) => ({
  id,
  version: 1,
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
    text: `Текст ${id}`,
    generated_text: `Текст ${id}`,
    recipient,
    quality_gate_json: { passed: true, total_score: 18, max_score: 18 },
  }],
});

const preview = (recipient: string) => ({
  status: 'ready',
  channel_availability: {},
  quality_gate: { passed: true, total_score: 18, max_score: 18 },
  touches: [{
    sequence_index: 0,
    channel: 'email',
    channel_status: 'ready',
    day_offset: 0,
    angle: 'signal',
    text: `Preview ${recipient}`,
    recipient,
    quality_gate: { passed: true, total_score: 18, max_score: 18 },
  }],
});

describe('OutreachCampaignBuilder workstream scope', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('keeps the newer workstream campaign when an older campaign request resolves last', async () => {
    const campaignsA = deferred<{ campaigns: ReturnType<typeof campaign>[] }>();
    const campaignsB = deferred<{ campaigns: ReturnType<typeof campaign>[] }>();
    const requests: string[] = [];
    vi.spyOn(newAuth, 'makeRequest').mockImplementation(async (url) => {
      const requestUrl = String(url);
      requests.push(requestUrl);
      if (requestUrl.endsWith('/workstream-A/campaigns')) return campaignsA.promise;
      if (requestUrl.endsWith('/workstream-B/campaigns')) return campaignsB.promise;
      return {};
    });
    const user = userEvent.setup();
    const view = render(<OutreachCampaignBuilder workstreamId="workstream-A" />);

    view.rerender(<OutreachCampaignBuilder workstreamId="workstream-B" />);
    await act(async () => {
      campaignsB.resolve({ campaigns: [campaign('campaign-B', 'owner-b@example.invalid')] });
    });
    expect(await screen.findByText('Получатель: owner-b@example.invalid')).toBeVisible();

    await act(async () => {
      campaignsA.resolve({ campaigns: [campaign('campaign-A', 'owner-a@example.invalid')] });
    });

    expect(screen.getByText('Получатель: owner-b@example.invalid')).toBeVisible();
    expect(screen.queryByText('Получатель: owner-a@example.invalid')).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Утвердить цепочку и перейти к отправке' }));
    expect(requests).toContain('/outreach/campaigns/campaign-B/approve');
    expect(requests).not.toContain('/outreach/campaigns/campaign-A/approve');
  });

  it('does not render a late preview from the previous workstream', async () => {
    const previewA = deferred<{ preview: ReturnType<typeof preview> }>();
    vi.spyOn(newAuth, 'makeRequest').mockImplementation(async (url) => {
      const requestUrl = String(url);
      if (requestUrl.endsWith('/workstream-A/campaigns')) return { campaigns: [campaign('campaign-A', 'owner-a@example.invalid')] };
      if (requestUrl.endsWith('/workstream-B/campaigns')) return { campaigns: [campaign('campaign-B', 'owner-b@example.invalid')] };
      if (requestUrl.endsWith('/workstream-A/preview')) return previewA.promise;
      return {};
    });
    const user = userEvent.setup();
    const view = render(<OutreachCampaignBuilder workstreamId="workstream-A" />);

    expect(await screen.findByText('Получатель: owner-a@example.invalid')).toBeVisible();
    await user.click(screen.getByRole('button', { name: 'Показать всю цепочку' }));
    view.rerender(<OutreachCampaignBuilder workstreamId="workstream-B" />);
    expect(await screen.findByText('Получатель: owner-b@example.invalid')).toBeVisible();

    await act(async () => {
      previewA.resolve({ preview: preview('preview-a@example.invalid') });
    });

    expect(screen.getByText('Получатель: owner-b@example.invalid')).toBeVisible();
    expect(screen.queryByText('Получатель: preview-a@example.invalid')).not.toBeInTheDocument();
  });

  it('does not route approval to an old campaign after a late campaign response', async () => {
    const campaignsA = deferred<{ campaigns: ReturnType<typeof campaign>[] }>();
    const campaignsB = deferred<{ campaigns: ReturnType<typeof campaign>[] }>();
    const requests: string[] = [];
    vi.spyOn(newAuth, 'makeRequest').mockImplementation(async (url) => {
      const requestUrl = String(url);
      requests.push(requestUrl);
      if (requestUrl.endsWith('/workstream-A/campaigns')) return campaignsA.promise;
      if (requestUrl.endsWith('/workstream-B/campaigns')) return campaignsB.promise;
      return {};
    });
    const user = userEvent.setup();
    const view = render(<OutreachCampaignBuilder workstreamId="workstream-A" />);

    view.rerender(<OutreachCampaignBuilder workstreamId="workstream-B" />);
    await act(async () => {
      campaignsB.resolve({ campaigns: [campaign('campaign-B', 'owner-b@example.invalid')] });
    });
    await act(async () => {
      campaignsA.resolve({ campaigns: [campaign('campaign-A', 'owner-a@example.invalid')] });
    });

    await user.click(screen.getByRole('button', { name: 'Утвердить цепочку и перейти к отправке' }));

    expect(requests).toContain('/outreach/campaigns/campaign-B/approve');
    expect(requests).not.toContain('/outreach/campaigns/campaign-A/approve');
  });

  it('ignores a late save from the previous workstream without reloading its campaign', async () => {
    const savedA = deferred<{ preview: ReturnType<typeof preview>; campaign: { id: string } }>();
    const requests: string[] = [];
    let previewCalls = 0;
    const onChanged = vi.fn();
    vi.spyOn(newAuth, 'makeRequest').mockImplementation(async (url) => {
      const requestUrl = String(url);
      requests.push(requestUrl);
      if (requestUrl.endsWith('/workstream-A/campaigns')) return { campaigns: [campaign('campaign-A', 'owner-a@example.invalid')] };
      if (requestUrl.endsWith('/workstream-B/campaigns')) return { campaigns: [campaign('campaign-B', 'owner-b@example.invalid')] };
      if (requestUrl.endsWith('/workstream-A/preview')) {
        previewCalls += 1;
        return previewCalls === 1 ? { preview: preview('preview-a@example.invalid') } : savedA.promise;
      }
      return {};
    });
    const user = userEvent.setup();
    const view = render(<OutreachCampaignBuilder workstreamId="workstream-A" onChanged={onChanged} />);

    await screen.findByText('Получатель: owner-a@example.invalid');
    await user.click(screen.getByRole('button', { name: 'Показать всю цепочку' }));
    await screen.findByText('Получатель: preview-a@example.invalid');
    await user.click(screen.getByRole('button', { name: 'Сохранить изменения' }));
    view.rerender(<OutreachCampaignBuilder workstreamId="workstream-B" onChanged={onChanged} />);
    expect(await screen.findByText('Получатель: owner-b@example.invalid')).toBeVisible();

    await act(async () => {
      savedA.resolve({ preview: preview('saved-a@example.invalid'), campaign: { id: 'campaign-A' } });
      await Promise.resolve();
    });

    expect(screen.getByText('Получатель: owner-b@example.invalid')).toBeVisible();
    expect(screen.queryByText('Получатель: saved-a@example.invalid')).not.toBeInTheDocument();
    expect(requests.filter((requestUrl) => requestUrl.endsWith('/workstream-A/campaigns'))).toHaveLength(1);
    expect(onChanged).not.toHaveBeenCalled();
  });

  it('does not carry an old request error or busy state into the new workstream', async () => {
    const previewA = deferred<{ preview: ReturnType<typeof preview> }>();
    vi.spyOn(newAuth, 'makeRequest').mockImplementation(async (url) => {
      const requestUrl = String(url);
      if (requestUrl.endsWith('/workstream-A/campaigns')) return { campaigns: [campaign('campaign-A', 'owner-a@example.invalid')] };
      if (requestUrl.endsWith('/workstream-B/campaigns')) return { campaigns: [campaign('campaign-B', 'owner-b@example.invalid')] };
      if (requestUrl.endsWith('/workstream-A/preview')) return previewA.promise;
      return {};
    });
    const user = userEvent.setup();
    const view = render(<OutreachCampaignBuilder workstreamId="workstream-A" />);

    await screen.findByText('Получатель: owner-a@example.invalid');
    await user.click(screen.getByRole('button', { name: 'Показать всю цепочку' }));
    view.rerender(<OutreachCampaignBuilder workstreamId="workstream-B" />);
    await screen.findByText('Получатель: owner-b@example.invalid');

    await act(async () => {
      previewA.reject(new Error('old workstream preview failed'));
    });

    await waitFor(() => {
      expect(screen.queryByText('old workstream preview failed')).not.toBeInTheDocument();
    });
    expect(screen.getByText('Получатель: owner-b@example.invalid')).toBeVisible();
  });

  it('releases the new workstream controls while an old preview remains pending', async () => {
    const previewA = deferred<{ preview: ReturnType<typeof preview> }>();
    vi.spyOn(newAuth, 'makeRequest').mockImplementation(async (url) => {
      const requestUrl = String(url);
      if (requestUrl.endsWith('/workstream-A/campaigns')) return { campaigns: [campaign('campaign-A', 'owner-a@example.invalid')] };
      if (requestUrl.endsWith('/workstream-B/campaigns')) return { campaigns: [campaign('campaign-B', 'owner-b@example.invalid')] };
      if (requestUrl.endsWith('/workstream-A/preview')) return previewA.promise;
      return {};
    });
    const user = userEvent.setup();
    const view = render(<OutreachCampaignBuilder workstreamId="workstream-A" />);

    await screen.findByText('Получатель: owner-a@example.invalid');
    await user.click(screen.getByRole('button', { name: 'Показать всю цепочку' }));
    view.rerender(<OutreachCampaignBuilder workstreamId="workstream-B" />);
    await screen.findByText('Получатель: owner-b@example.invalid');

    expect(screen.getByRole('button', { name: 'Показать всю цепочку' })).toBeEnabled();
  });

  it('clears the old campaign immediately while the next workstream is still loading', async () => {
    const campaignsB = deferred<{ campaigns: ReturnType<typeof campaign>[] }>();
    vi.spyOn(newAuth, 'makeRequest').mockImplementation(async (url) => {
      const requestUrl = String(url);
      if (requestUrl.endsWith('/workstream-A/campaigns')) return { campaigns: [campaign('campaign-A', 'owner-a@example.invalid')] };
      if (requestUrl.endsWith('/workstream-B/campaigns')) return campaignsB.promise;
      return {};
    });
    const view = render(<OutreachCampaignBuilder workstreamId="workstream-A" />);

    expect(await screen.findByText('Получатель: owner-a@example.invalid')).toBeVisible();
    view.rerender(<OutreachCampaignBuilder workstreamId="workstream-B" />);

    expect(screen.queryByText('Получатель: owner-a@example.invalid')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Утвердить цепочку и перейти к отправке' })).not.toBeInTheDocument();
  });

  it('uses the newest A lifecycle after an A-to-B-to-A transition', async () => {
    const campaignsAFirst = deferred<{ campaigns: ReturnType<typeof campaign>[] }>();
    const campaignsASecond = deferred<{ campaigns: ReturnType<typeof campaign>[] }>();
    const campaignsB = deferred<{ campaigns: ReturnType<typeof campaign>[] }>();
    let requestsA = 0;
    vi.spyOn(newAuth, 'makeRequest').mockImplementation(async (url) => {
      const requestUrl = String(url);
      if (requestUrl.endsWith('/workstream-A/campaigns')) {
        requestsA += 1;
        return requestsA === 1 ? campaignsAFirst.promise : campaignsASecond.promise;
      }
      if (requestUrl.endsWith('/workstream-B/campaigns')) return campaignsB.promise;
      return {};
    });
    const view = render(<OutreachCampaignBuilder workstreamId="workstream-A" />);

    view.rerender(<OutreachCampaignBuilder workstreamId="workstream-B" />);
    view.rerender(<OutreachCampaignBuilder workstreamId="workstream-A" />);
    await act(async () => {
      campaignsASecond.resolve({ campaigns: [campaign('campaign-A-new', 'owner-a-new@example.invalid')] });
    });
    expect(await screen.findByText('Получатель: owner-a-new@example.invalid')).toBeVisible();

    await act(async () => {
      campaignsAFirst.resolve({ campaigns: [campaign('campaign-A-old', 'owner-a-old@example.invalid')] });
      campaignsB.resolve({ campaigns: [campaign('campaign-B', 'owner-b@example.invalid')] });
    });

    expect(screen.getByText('Получатель: owner-a-new@example.invalid')).toBeVisible();
    expect(screen.queryByText('Получатель: owner-a-old@example.invalid')).not.toBeInTheDocument();
    expect(screen.queryByText('Получатель: owner-b@example.invalid')).not.toBeInTheDocument();
  });

  it('invalidates an old preview when business or lead segment changes under the same workstream', async () => {
    const previewA = deferred<{ preview: ReturnType<typeof preview> }>();
    let campaignLoads = 0;
    vi.spyOn(newAuth, 'makeRequest').mockImplementation(async (url) => {
      const requestUrl = String(url);
      if (requestUrl.endsWith('/workstream-A/campaigns')) {
        campaignLoads += 1;
        return {
          campaigns: [campaign(
            campaignLoads === 1 ? 'campaign-A-before' : 'campaign-A-after',
            campaignLoads === 1 ? 'owner-before@example.invalid' : 'owner-after@example.invalid',
          )],
        };
      }
      if (requestUrl.endsWith('/workstream-A/preview')) return previewA.promise;
      return {};
    });
    const user = userEvent.setup();
    const view = render(<OutreachCampaignBuilder workstreamId="workstream-A" businessId="business-A" leadSegment="beauty" />);

    expect(await screen.findByText('Получатель: owner-before@example.invalid')).toBeVisible();
    await user.click(screen.getByRole('button', { name: 'Показать всю цепочку' }));
    view.rerender(<OutreachCampaignBuilder workstreamId="workstream-A" businessId="business-B" leadSegment="medical" />);
    expect(await screen.findByText('Получатель: owner-after@example.invalid')).toBeVisible();

    await act(async () => {
      previewA.resolve({ preview: preview('preview-before@example.invalid') });
    });

    expect(screen.getByText('Получатель: owner-after@example.invalid')).toBeVisible();
    expect(screen.queryByText('Получатель: preview-before@example.invalid')).not.toBeInTheDocument();
  });

  it('does not reload or notify after an approval response arrives after unmount', async () => {
    const approvalA = deferred<Record<string, never>>();
    const requests: string[] = [];
    const onChanged = vi.fn();
    vi.spyOn(newAuth, 'makeRequest').mockImplementation(async (url) => {
      const requestUrl = String(url);
      requests.push(requestUrl);
      if (requestUrl.endsWith('/workstream-A/campaigns')) return { campaigns: [campaign('campaign-A', 'owner-a@example.invalid')] };
      if (requestUrl.endsWith('/campaign-A/approve')) return approvalA.promise;
      return {};
    });
    const user = userEvent.setup();
    const view = render(<OutreachCampaignBuilder workstreamId="workstream-A" onChanged={onChanged} />);

    await screen.findByText('Получатель: owner-a@example.invalid');
    await user.click(screen.getByRole('button', { name: 'Утвердить цепочку и перейти к отправке' }));
    view.unmount();
    await act(async () => {
      approvalA.resolve({});
      await Promise.resolve();
    });

    expect(requests.filter((requestUrl) => requestUrl.endsWith('/workstream-A/campaigns'))).toHaveLength(1);
    expect(onChanged).not.toHaveBeenCalled();
  });

  it('ignores a delayed campaign reload started by an old approval after switching workstreams', async () => {
    const campaignReloadA = deferred<{ campaigns: ReturnType<typeof campaign>[] }>();
    let campaignLoadsA = 0;
    const onChanged = vi.fn();
    vi.spyOn(newAuth, 'makeRequest').mockImplementation(async (url) => {
      const requestUrl = String(url);
      if (requestUrl.endsWith('/workstream-A/campaigns')) {
        campaignLoadsA += 1;
        return campaignLoadsA === 1
          ? { campaigns: [campaign('campaign-A', 'owner-a@example.invalid')] }
          : campaignReloadA.promise;
      }
      if (requestUrl.endsWith('/workstream-B/campaigns')) return { campaigns: [campaign('campaign-B', 'owner-b@example.invalid')] };
      if (requestUrl.endsWith('/campaign-A/approve')) return {};
      return {};
    });
    const user = userEvent.setup();
    const view = render(<OutreachCampaignBuilder workstreamId="workstream-A" onChanged={onChanged} />);

    await screen.findByText('Получатель: owner-a@example.invalid');
    await user.click(screen.getByRole('button', { name: 'Утвердить цепочку и перейти к отправке' }));
    view.rerender(<OutreachCampaignBuilder workstreamId="workstream-B" onChanged={onChanged} />);
    expect(await screen.findByText('Получатель: owner-b@example.invalid')).toBeVisible();

    await act(async () => {
      campaignReloadA.resolve({ campaigns: [campaign('campaign-A-reload', 'owner-a-reload@example.invalid')] });
    });

    expect(screen.getByText('Получатель: owner-b@example.invalid')).toBeVisible();
    expect(screen.queryByText('Получатель: owner-a-reload@example.invalid')).not.toBeInTheDocument();
    expect(onChanged).not.toHaveBeenCalled();
  });

  it('keeps normal approval of a saved campaign in the same workstream working', async () => {
    const requests: string[] = [];
    vi.spyOn(newAuth, 'makeRequest').mockImplementation(async (url) => {
      const requestUrl = String(url);
      requests.push(requestUrl);
      if (requestUrl.endsWith('/workstream-A/campaigns')) return { campaigns: [campaign('campaign-A', 'owner-a@example.invalid')] };
      return {};
    });
    const user = userEvent.setup();

    render(<OutreachCampaignBuilder workstreamId="workstream-A" />);
    expect(await screen.findByText('Получатель: owner-a@example.invalid')).toBeVisible();
    await user.click(screen.getByRole('button', { name: 'Утвердить цепочку и перейти к отправке' }));
    expect(requests).toContain('/outreach/campaigns/campaign-A/approve');
  });

  it('keeps a same-workstream preview, save, then approval flow working', async () => {
    const requests: string[] = [];
    let previewCalls = 0;
    let campaignLoads = 0;
    vi.spyOn(newAuth, 'makeRequest').mockImplementation(async (url) => {
      const requestUrl = String(url);
      requests.push(requestUrl);
      if (requestUrl.endsWith('/workstream-A/campaigns')) {
        campaignLoads += 1;
        return campaignLoads === 1 ? { campaigns: [] } : { campaigns: [campaign('campaign-A', 'owner-a@example.invalid')] };
      }
      if (requestUrl.endsWith('/workstream-A/preview')) {
        previewCalls += 1;
        return previewCalls === 1
          ? { preview: preview('preview-a@example.invalid') }
          : { preview: preview('saved-a@example.invalid'), campaign: { id: 'campaign-A' } };
      }
      return {};
    });
    const user = userEvent.setup();

    render(<OutreachCampaignBuilder workstreamId="workstream-A" />);
    await user.click(screen.getByRole('button', { name: 'Показать всю цепочку' }));
    expect(await screen.findByText('Получатель: preview-a@example.invalid')).toBeVisible();
    await user.click(screen.getByRole('button', { name: 'Сохранить изменения' }));
    expect(await screen.findByText('Получатель: owner-a@example.invalid')).toBeVisible();
    expect(screen.queryByText('Получатель: saved-a@example.invalid')).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Утвердить цепочку и перейти к отправке' }));
    expect(requests).toContain('/outreach/campaigns/campaign-A/approve');
  });

  it('keeps the second StrictMode lifetime when its first setup resolves late', async () => {
    const firstSetup = deferred<{ campaigns: ReturnType<typeof campaign>[] }>();
    const secondSetup = deferred<{ campaigns: ReturnType<typeof campaign>[] }>();
    let campaignLoads = 0;
    vi.spyOn(newAuth, 'makeRequest').mockImplementation(async (url) => {
      if (!String(url).endsWith('/workstream-A/campaigns')) return {};
      campaignLoads += 1;
      return campaignLoads === 1 ? firstSetup.promise : secondSetup.promise;
    });

    render(
      <StrictMode>
        <OutreachCampaignBuilder workstreamId="workstream-A" />
      </StrictMode>,
    );
    await waitFor(() => {
      expect(campaignLoads).toBeGreaterThanOrEqual(2);
    });
    await act(async () => {
      secondSetup.resolve({ campaigns: [campaign('campaign-new', 'owner-new@example.invalid')] });
    });
    expect(await screen.findByText('Получатель: owner-new@example.invalid')).toBeVisible();

    await act(async () => {
      firstSetup.resolve({ campaigns: [campaign('campaign-old', 'owner-old@example.invalid')] });
    });

    expect(screen.getByText('Получатель: owner-new@example.invalid')).toBeVisible();
    expect(screen.queryByText('Получатель: owner-old@example.invalid')).not.toBeInTheDocument();
  });

  it('keeps an unsaved draft when the scope key is unchanged', async () => {
    let previewCalls = 0;
    vi.spyOn(newAuth, 'makeRequest').mockImplementation(async (url) => {
      const requestUrl = String(url);
      if (requestUrl.endsWith('/workstream-A/campaigns')) return { campaigns: [] };
      if (requestUrl.endsWith('/workstream-A/preview')) {
        previewCalls += 1;
        return { preview: preview('preview-a@example.invalid') };
      }
      return {};
    });
    const user = userEvent.setup();
    const view = render(<OutreachCampaignBuilder workstreamId="workstream-A" businessId="business-A" leadSegment="beauty" />);

    await user.click(screen.getByRole('button', { name: 'Показать всю цепочку' }));
    expect(await screen.findByText('Получатель: preview-a@example.invalid')).toBeVisible();
    view.rerender(<OutreachCampaignBuilder workstreamId="workstream-A" businessId="business-A" leadSegment="beauty" />);

    expect(screen.getByText('Получатель: preview-a@example.invalid')).toBeVisible();
    expect(previewCalls).toBe(1);
  });

  it('invalidates an old preview when only the business changes', async () => {
    const previewA = deferred<{ preview: ReturnType<typeof preview> }>();
    let campaignLoads = 0;
    vi.spyOn(newAuth, 'makeRequest').mockImplementation(async (url) => {
      const requestUrl = String(url);
      if (requestUrl.endsWith('/workstream-A/campaigns')) {
        campaignLoads += 1;
        return { campaigns: [campaign(`campaign-${campaignLoads}`, `owner-${campaignLoads}@example.invalid`)] };
      }
      if (requestUrl.endsWith('/workstream-A/preview')) return previewA.promise;
      return {};
    });
    const user = userEvent.setup();
    const view = render(<OutreachCampaignBuilder workstreamId="workstream-A" businessId="business-A" leadSegment="beauty" />);

    expect(await screen.findByText('Получатель: owner-1@example.invalid')).toBeVisible();
    await user.click(screen.getByRole('button', { name: 'Показать всю цепочку' }));
    view.rerender(<OutreachCampaignBuilder workstreamId="workstream-A" businessId="business-B" leadSegment="beauty" />);
    expect(await screen.findByText('Получатель: owner-2@example.invalid')).toBeVisible();
    await act(async () => {
      previewA.resolve({ preview: preview('preview-business-a@example.invalid') });
    });

    expect(screen.getByText('Получатель: owner-2@example.invalid')).toBeVisible();
    expect(screen.queryByText('Получатель: preview-business-a@example.invalid')).not.toBeInTheDocument();
  });

  it('invalidates an old preview when only the lead segment changes', async () => {
    const previewA = deferred<{ preview: ReturnType<typeof preview> }>();
    let campaignLoads = 0;
    vi.spyOn(newAuth, 'makeRequest').mockImplementation(async (url) => {
      const requestUrl = String(url);
      if (requestUrl.endsWith('/workstream-A/campaigns')) {
        campaignLoads += 1;
        return { campaigns: [campaign(`campaign-${campaignLoads}`, `owner-${campaignLoads}@example.invalid`)] };
      }
      if (requestUrl.endsWith('/workstream-A/preview')) return previewA.promise;
      return {};
    });
    const user = userEvent.setup();
    const view = render(<OutreachCampaignBuilder workstreamId="workstream-A" businessId="business-A" leadSegment="beauty" />);

    expect(await screen.findByText('Получатель: owner-1@example.invalid')).toBeVisible();
    await user.click(screen.getByRole('button', { name: 'Показать всю цепочку' }));
    view.rerender(<OutreachCampaignBuilder workstreamId="workstream-A" businessId="business-A" leadSegment="medical" />);
    expect(await screen.findByText('Получатель: owner-2@example.invalid')).toBeVisible();
    await act(async () => {
      previewA.resolve({ preview: preview('preview-beauty@example.invalid') });
    });

    expect(screen.getByText('Получатель: owner-2@example.invalid')).toBeVisible();
    expect(screen.queryByText('Получатель: preview-beauty@example.invalid')).not.toBeInTheDocument();
  });

  it('ignores late recommendations from the previous business scope', async () => {
    const recommendationsA = deferred<{ stats: Array<Record<string, unknown>> }>();
    vi.spyOn(newAuth, 'makeRequest').mockImplementation(async (url) => {
      const requestUrl = String(url);
      if (requestUrl.endsWith('/workstream-A/campaigns')) return { campaigns: [] };
      if (requestUrl.includes('business_id=business-A')) return recommendationsA.promise;
      if (requestUrl.includes('business_id=business-B')) return { stats: [] };
      return {};
    });
    const view = render(<OutreachCampaignBuilder workstreamId="workstream-A" businessId="business-A" leadSegment="beauty" />);

    view.rerender(<OutreachCampaignBuilder workstreamId="workstream-A" businessId="business-B" leadSegment="medical" />);
    await act(async () => {
      recommendationsA.resolve({
        stats: [{
          id: 'recommendation-A',
          strategy_fingerprint: 'strategy-A',
          recommendation_status: 'candidate_for_reuse',
          dimensions_json: { segment: 'beauty', channel: 'email', angle: 'signal' },
          positive_reply_count: 1,
          delivered_count: 2,
          confidence: 0.5,
        }],
      });
    });

    expect(screen.queryByText('Найдена рабочая связка')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Применить в новой версии' })).not.toBeInTheDocument();
  });

  it('keeps a new pending preview busy when an old preview resolves after the scope switch', async () => {
    const previewA = deferred<{ preview: ReturnType<typeof preview> }>();
    const previewB = deferred<{ preview: ReturnType<typeof preview> }>();
    vi.spyOn(newAuth, 'makeRequest').mockImplementation(async (url) => {
      const requestUrl = String(url);
      if (requestUrl.endsWith('/workstream-A/campaigns')) return { campaigns: [campaign('campaign-A', 'owner-a@example.invalid')] };
      if (requestUrl.endsWith('/workstream-B/campaigns')) return { campaigns: [campaign('campaign-B', 'owner-b@example.invalid')] };
      if (requestUrl.endsWith('/workstream-A/preview')) return previewA.promise;
      if (requestUrl.endsWith('/workstream-B/preview')) return previewB.promise;
      return {};
    });
    const user = userEvent.setup();
    const view = render(<OutreachCampaignBuilder workstreamId="workstream-A" />);

    await screen.findByText('Получатель: owner-a@example.invalid');
    await user.click(screen.getByRole('button', { name: 'Показать всю цепочку' }));
    view.rerender(<OutreachCampaignBuilder workstreamId="workstream-B" />);
    await screen.findByText('Получатель: owner-b@example.invalid');
    await user.click(screen.getByRole('button', { name: 'Показать всю цепочку' }));
    expect(screen.getByRole('button', { name: 'Показать всю цепочку' })).toBeDisabled();

    await act(async () => {
      previewA.resolve({ preview: preview('preview-a@example.invalid') });
    });

    expect(screen.getByRole('button', { name: 'Показать всю цепочку' })).toBeDisabled();
    expect(screen.queryByText('Получатель: preview-a@example.invalid')).not.toBeInTheDocument();
    expect(screen.queryByText('old workstream preview failed')).not.toBeInTheDocument();
    await act(async () => {
      previewB.resolve({ preview: preview('preview-b@example.invalid') });
    });

    expect(await screen.findByText('Получатель: preview-b@example.invalid')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Показать всю цепочку' })).toBeEnabled();
  });

  it('keeps a new pending preview busy when an old preview rejects after the scope switch', async () => {
    const previewA = deferred<{ preview: ReturnType<typeof preview> }>();
    const previewB = deferred<{ preview: ReturnType<typeof preview> }>();
    vi.spyOn(newAuth, 'makeRequest').mockImplementation(async (url) => {
      const requestUrl = String(url);
      if (requestUrl.endsWith('/workstream-A/campaigns')) return { campaigns: [campaign('campaign-A', 'owner-a@example.invalid')] };
      if (requestUrl.endsWith('/workstream-B/campaigns')) return { campaigns: [campaign('campaign-B', 'owner-b@example.invalid')] };
      if (requestUrl.endsWith('/workstream-A/preview')) return previewA.promise;
      if (requestUrl.endsWith('/workstream-B/preview')) return previewB.promise;
      return {};
    });
    const user = userEvent.setup();
    const view = render(<OutreachCampaignBuilder workstreamId="workstream-A" />);

    await screen.findByText('Получатель: owner-a@example.invalid');
    await user.click(screen.getByRole('button', { name: 'Показать всю цепочку' }));
    view.rerender(<OutreachCampaignBuilder workstreamId="workstream-B" />);
    await screen.findByText('Получатель: owner-b@example.invalid');
    await user.click(screen.getByRole('button', { name: 'Показать всю цепочку' }));
    expect(screen.getByRole('button', { name: 'Показать всю цепочку' })).toBeDisabled();

    await act(async () => {
      previewA.reject(new Error('old workstream preview failed'));
    });

    expect(screen.getByRole('button', { name: 'Показать всю цепочку' })).toBeDisabled();
    expect(screen.queryByText('old workstream preview failed')).not.toBeInTheDocument();
    await act(async () => {
      previewB.resolve({ preview: preview('preview-b@example.invalid') });
    });

    expect(await screen.findByText('Получатель: preview-b@example.invalid')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Показать всю цепочку' })).toBeEnabled();
  });
});
