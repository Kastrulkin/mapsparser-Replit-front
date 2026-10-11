import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { NewAuth } from './auth_new';
beforeEach(() => { localStorage.clear(); });
afterEach(() => vi.unstubAllGlobals());
it.each([401,403,404,503])('keeps HTTP %s for safe refresh recovery', async status => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({error: status===401 ? 'invalid token' : 'unavailable'}), {status,headers:{'content-type':'application/json'}})));
  await expect(new NewAuth().makeRequest('/operator/today')).rejects.toMatchObject({status});
});
