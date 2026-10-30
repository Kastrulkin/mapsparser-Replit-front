import { act, renderHook } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { useClientHandoffLaunch } from './useClientHandoffLaunch';
import type { Bootstrap } from './types';

afterEach(()=>{delete window.Telegram; window.history.replaceState({},'', '/');});
const bootstrap:Bootstrap={resolved_deep_link:{screen:'client_handoffs',item_type:'client_conversation',item_id:'c'},navigation:[{key:'client_handoffs',label:'Сообщения',group:'more',status:'available'}]};
const launch=()=>window.history.replaceState({},'', '/telegram/control?screen=client_handoffs&scope_type=business&scope_id=b');
it('restores the verified conversation on every Telegram activation and cleans up listeners',()=>{
 launch();const handlers=new Map<string,()=>void>();const restore=vi.fn();const offEvent=vi.fn();
 window.Telegram={WebApp:{onEvent:(event,callback)=>handlers.set(event,callback),offEvent}};
 const hook=renderHook(()=>useClientHandoffLaunch(bootstrap,{kind:'business',id:'b'},restore));
 for(let i=0;i<3;i++)act(()=>handlers.get('activated')?.());
 expect(restore).toHaveBeenCalledTimes(3);expect(hook.result.current.reopenRevision).toBe(3);
 act(()=>handlers.get('deactivated')?.());
 expect(restore).toHaveBeenCalledTimes(4);
 hook.unmount();expect(offEvent).toHaveBeenCalledTimes(2);
 act(()=>document.dispatchEvent(new Event('visibilitychange')));
 expect(restore).toHaveBeenCalledTimes(4);
});
it('does not restore a foreign business, hidden destination or rejected object',()=>{
 launch();const restore=vi.fn();const onEvent=vi.fn();window.Telegram={WebApp:{onEvent}};
 const hook=renderHook(({value,business})=>useClientHandoffLaunch(value,{kind:'business',id:business},restore),{initialProps:{value:bootstrap,business:'foreign'}});
 expect(hook.result.current.isDirectClientLaunch).toBe(false);
 hook.rerender({value:{...bootstrap,resolved_deep_link:{...bootstrap.resolved_deep_link,fallback_applied:true}},business:'b'});
 expect(hook.result.current.isDirectClientLaunch).toBe(false);
 hook.rerender({value:{...bootstrap,navigation:[]},business:'b'});
 act(()=>document.dispatchEvent(new Event('visibilitychange')));
 expect(onEvent).not.toHaveBeenCalled();expect(restore).not.toHaveBeenCalled();
});
it('uses the latest callback and restores a cached frame without reloading the page',()=>{
 launch();const first=vi.fn();const second=vi.fn();
 const hook=renderHook(({callback})=>useClientHandoffLaunch(bootstrap,{kind:'business',id:'b'},callback),{initialProps:{callback:first}});
 hook.rerender({callback:second});
 act(()=>document.dispatchEvent(new Event('visibilitychange')));
 expect(first).not.toHaveBeenCalled();expect(second).toHaveBeenCalledOnce();
 expect(hook.result.current.reopenRevision).toBe(1);
});
