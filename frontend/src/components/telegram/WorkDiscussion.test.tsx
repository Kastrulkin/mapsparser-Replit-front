import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { WorkDiscussion } from './WorkDiscussion';
afterEach(() => {vi.unstubAllGlobals(); delete window.WebApp; delete window.Telegram; window.history.replaceState({}, '', '/');});
it.each(['telegram','max'])('opens only an authorized %s handoff without sending a command', async platform => {
  window.history.replaceState({}, '', `/${platform}/control`);
  const open = vi.fn();
  if(platform==='telegram')window.Telegram={WebApp:{openTelegramLink:open}};
  else window.WebApp={openMaxLink:open,openLink:vi.fn()};
  const fetch=vi.fn().mockResolvedValue(new Response(JSON.stringify({success:true,url:`https://${platform==='max'?'max.ru':'t.me'}/localos?start=work_123`}),{status:200}));
  vi.stubGlobal('fetch',fetch);
  render(<WorkDiscussion businessId="meliora" itemId="post" updatedAt="2026-10-16" />);
  fireEvent.click(screen.getByRole('button'));
  await waitFor(()=>expect(open).toHaveBeenCalledOnce());
  expect(JSON.parse(fetch.mock.calls[0][1].body)).toMatchObject({business_id:'meliora',item_id:'post',platform,updated_at:'2026-10-16'});
  expect(fetch).toHaveBeenCalledOnce();
});
it('shows an access failure without opening a different account', async () => {
  vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response(JSON.stringify({error:'Нет доступа'}),{status:403})));
  const open=vi.fn();vi.stubGlobal('open',open);
  render(<WorkDiscussion businessId="meliora" itemId="post" />);
  fireEvent.click(screen.getByRole('button'));
  expect(await screen.findByRole('alert')).toHaveTextContent('Нет доступа');
  expect(open).not.toHaveBeenCalled();
});
