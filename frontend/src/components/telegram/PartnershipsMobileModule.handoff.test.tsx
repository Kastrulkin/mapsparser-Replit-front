import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { PartnershipsMobileModule } from './PartnershipsMobileModule';

const first = { id: 'partner-1', name: 'Детская студия', updated_at: '2026-10-17T00:00:00Z' };
const second = { id: 'partner-2', name: 'Семейный клуб', updated_at: '2026-10-17T00:00:00Z' };
afterEach(() => { vi.unstubAllGlobals(); window.history.replaceState({}, '', '/'); });

it('opens the decoded MAX partner without preparing or sending anything', async () => {
  window.history.replaceState({}, '', '/max/control?WebAppStartParam=nav_' + btoa(JSON.stringify({ screen:'partnerships', item_type:'partner', item_id:first.id })));
  const requests: string[] = [];
  const discuss = vi.fn();
  vi.stubGlobal('fetch', vi.fn((url: RequestInfo | URL, options?: RequestInit) => {
    requests.push(`${options?.method || 'GET'} ${String(url)}`);
    const payload = String(url).includes('/leads?') ? { items:[first,second] } : {drafts:[],items:[],batches:[],counts:{}};
    return Promise.resolve(new Response(JSON.stringify(payload),{status:200}));
  }));
  render(<PartnershipsMobileModule scope={{kind:'business',id:'business'}} onDiscuss={discuss} />);
  const button = await screen.findByRole('button',{name:'Обсудить партнёра'});
  expect(screen.getByRole('button',{name:'Продолжить в боте MAX'})).toBeInTheDocument();
  fireEvent.click(button);
  expect(discuss).toHaveBeenCalledWith(expect.objectContaining(first));
  expect(requests.every(request => request.startsWith('GET '))).toBe(true);
});

it('opens a new focused partner in the same business and keeps native preparation behind a click', async () => {
  vi.stubGlobal('fetch', vi.fn((url: RequestInfo | URL) => Promise.resolve(new Response(JSON.stringify(
    String(url).includes('/leads?') ? {items:[first,second]} : {drafts:[],items:[],batches:[],counts:{}}
  ),{status:200}))));
  const discuss=vi.fn();
  const view=render(<PartnershipsMobileModule scope={{kind:'business',id:'business'}} focusItemId={first.id} onDiscuss={discuss} />);
  await screen.findByRole('button',{name:'Обсудить партнёра'});
  await act(async () => view.rerender(<PartnershipsMobileModule scope={{kind:'business',id:'business'}} focusItemId={second.id} onDiscuss={discuss} />));
  fireEvent.click(await screen.findByRole('button',{name:'Обсудить партнёра'}));
  expect(discuss).toHaveBeenLastCalledWith(expect.objectContaining(second));
});
