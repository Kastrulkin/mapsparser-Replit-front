import { renderHook, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { useContentResult } from './useContentResult';
afterEach(()=>vi.unstubAllGlobals());
const items=[{id:'post',business_id:'business',plan_id:'ready',plan_title:'Готовый план',draft_text:'Сохранённый текст'}];
const plans=[{id:'new',title:'Незавершённый',items_count:0,plan_status:'generating',created_at:'2026-10-22'}, {id:'ready',title:'Готовый план',items_count:1,ready_count:1,created_at:'2026-10-15'}, {id:'history',title:'Прошлый план',items_count:1,ready_count:1,plan_status:'archived',created_at:'2026-06-04'}];
const response=(body:unknown,status=200)=>Promise.resolve(new Response(JSON.stringify(body),{status,headers:{'Content-Type':'application/json'}}));
it('opens current saved result without mutations and preserves an archived history',async()=>{
 const fetch=vi.fn((url:string)=>url.includes('?')?response({plans}):response({plan:{...plans[1],items}}));vi.stubGlobal('fetch',fetch);
 const {result}=renderHook(()=>useContentResult('business',items,''));await waitFor(()=>expect(result.current.loading).toBe(false));await waitFor(()=>expect(result.current.plans).toHaveLength(3));expect(result.current.activeId).toBe('ready');expect(result.current.items[0].draft_text).toBe('Сохранённый текст');
 expect(fetch.mock.calls.every(call=>String(call[0]).startsWith('/api/content-plans'))).toBe(true);
});
it('opens selected archived plan without replacing current choice',async()=>{
 vi.stubGlobal('fetch',vi.fn((url:string)=>url.includes('?')?response({plans}):response({plan:{...plans[2],items:[{id:'archived-post',business_id:'business',theme:'Прежний пост',draft_text:'Прежний текст'}]}})));
 const {result}=renderHook(()=>useContentResult('business',items,'history'));await waitFor(()=>expect(result.current.activeId).toBe('history'));await waitFor(()=>expect(result.current.items[0]?.id).toBe('archived-post'));expect(result.current.currentId).toBe('ready');
});
it('clears private content when the plan read is forbidden',async()=>{
 vi.stubGlobal('fetch',vi.fn((url:string)=>url.includes('?')?response({plans}):response({error:'Нет доступа'},403)));
 const {result}=renderHook(()=>useContentResult('business',items,''));await waitFor(()=>expect(result.current.denied).toBe(true));expect(result.current.items).toEqual([]);expect(result.current.plans).toEqual([]);
});
it('filters other business posts from a network plan',async()=>{
 vi.stubGlobal('fetch',vi.fn((url:string)=>url.includes('?')?response({plans}):response({plan:{...plans[1],items:[...items,{id:'foreign',business_id:'other',draft_text:'Чужой пост'}]}})));
 const {result}=renderHook(()=>useContentResult('business',items,''));await waitFor(()=>expect(result.current.loading).toBe(false));expect(result.current.items.some(item=>item.id==='foreign')).toBe(false);
});
it('preserves saved content with a readable error on a transient failure',async()=>{
 vi.stubGlobal('fetch',vi.fn(()=>Promise.reject(new Error('Сеть недоступна'))));
 const {result}=renderHook(()=>useContentResult('business',items,''));await waitFor(()=>expect(result.current.error).toBe('Сеть недоступна'));expect(result.current.items[0].draft_text).toBe('Сохранённый текст');
});
it('does not show the previous business while a new scope is loading',async()=>{
 vi.stubGlobal('fetch',vi.fn((url:string)=>url.includes('?')?response({plans}):response({plan:{...plans[1],items}})));
 const view=renderHook(({businessId})=>useContentResult(businessId,items,''),{initialProps:{businessId:'business'}});
 await waitFor(()=>expect(view.result.current.loading).toBe(false));
 vi.stubGlobal('fetch',vi.fn(()=>new Promise<Response>(()=>{})));
 view.rerender({businessId:'other'});expect(view.result.current.items).toEqual([]);
 view.unmount();
});
