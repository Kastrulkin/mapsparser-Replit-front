import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { WorkDiscussion } from './WorkDiscussion';
afterEach(()=>{vi.unstubAllGlobals();delete window.Telegram;delete window.WebApp;window.history.replaceState({},'','/');});
it('opens the authorized bot first, then closes the Telegram miniapp',async()=>{
 window.history.replaceState({},'','/telegram/control');
 const calls:string[]=[];
 window.Telegram={WebApp:{openTelegramLink:()=>calls.push('open'),close:()=>calls.push('close')}};
 vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response(JSON.stringify({url:'https://t.me/qa_bot?start=qa'}),{status:200})));
 render(<WorkDiscussion businessId="qa" itemId="qa-item"/>);
 fireEvent.click(screen.getByRole('button'));
 await waitFor(()=>expect(calls).toEqual(['open','close']));
});
it('keeps the miniapp open if the handoff was denied',async()=>{
 window.history.replaceState({},'','/telegram/control');const close=vi.fn(),open=vi.fn();
 window.Telegram={WebApp:{close,openTelegramLink:open}};
 vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response(JSON.stringify({error:'Нет доступа'}),{status:403})));
 render(<WorkDiscussion businessId="qa" itemId="qa-item"/>);fireEvent.click(screen.getByRole('button'));
 expect(await screen.findByRole('alert')).toHaveTextContent('Нет доступа');expect(close).not.toHaveBeenCalled();expect(open).not.toHaveBeenCalled();
});
it('uses MAX bridge and explains how to reveal the bot without inventing a close method',async()=>{
 window.history.replaceState({},'','/max/control');const open=vi.fn();window.WebApp={openMaxLink:open,openLink:vi.fn()};
 vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response(JSON.stringify({url:'https://max.ru/qa_bot?start=qa'}),{status:200})));
 render(<WorkDiscussion businessId="qa" itemId="qa-item"/>);fireEvent.click(screen.getByRole('button'));
 expect(await screen.findByRole('status')).toHaveTextContent('Если чат не виден');expect(open).toHaveBeenCalledOnce();
});
