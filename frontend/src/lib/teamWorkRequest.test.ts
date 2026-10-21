import { afterEach, expect, it, vi } from 'vitest';
import { teamWorkJson } from './teamWorkRequest';
afterEach(()=>{vi.useRealTimers();vi.unstubAllGlobals();});
it('stops a stalled request without repeating a mutation',async()=>{
 vi.useFakeTimers();
 const fetcher=vi.fn((_url:string,options:RequestInit)=>new Promise<Response>((_resolve,reject)=>options.signal?.addEventListener('abort',()=>reject(new DOMException('Aborted','AbortError')))));
 vi.stubGlobal('fetch',fetcher);
 const result=expect(teamWorkJson('/api/operator/day-brief',{method:'POST',body:'private draft'})).rejects.toThrow('20 секунд');
 await vi.advanceTimersByTimeAsync(20000);await result;expect(fetcher).toHaveBeenCalledTimes(1);
});
it('preserves a scope cancellation instead of showing a network failure',async()=>{
 const scope=new AbortController();
 vi.stubGlobal('fetch',vi.fn((_url:string,options:RequestInit)=>new Promise<Response>((_resolve,reject)=>options.signal?.addEventListener('abort',()=>reject(new DOMException('Scope changed','AbortError'))))));
 const result=expect(teamWorkJson('/api/work-journal',{signal:scope.signal})).rejects.toThrow('Scope changed');scope.abort();await result;
});
it('does not expose raw database errors',async()=>{
 vi.stubGlobal('fetch',vi.fn(()=>Promise.resolve(new Response(JSON.stringify({error:'SQL constraint internal table secret'}),{status:500}))));
 await expect(teamWorkJson('/api/operator/day-brief')).rejects.toThrow('Данные остались в форме');
});
it('turns a network failure into an actionable message',async()=>{
 vi.stubGlobal('fetch',vi.fn(()=>Promise.reject(new TypeError('Failed to fetch'))));
 await expect(teamWorkJson('/api/work-journal')).rejects.toThrow('Проверьте соединение');
});
it('keeps permission status available even with a malformed response so private state can be cleared',async()=>{
 vi.stubGlobal('fetch',vi.fn(()=>Promise.resolve(new Response('<html>Forbidden</html>',{status:403}))));
 expect((await teamWorkJson('/api/work-journal')).response.status).toBe(403);
});
