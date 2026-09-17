import { newAuth } from '@/lib/auth_new';
import { browserCookieAuthEnabled, browserCookieValue } from '@/lib/browserSessionFetch';

export type HeadersProvider = () => Record<string, string>;

export const voiceHeaders = (): Record<string, string> => {
  const token = newAuth.getToken();
  const result: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};
  const csrf = browserCookieValue('localos_csrf');
  if (browserCookieAuthEnabled() && csrf) result['X-CSRF-Token'] = csrf;
  return result;
};

export async function jsonRequest(url: string, options: RequestInit) {
  const response = await fetch(url, options);
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || 'Не удалось обработать аудио');
  return body;
}

export async function waitForOperatorResult<T extends { async_job_id?: string }>(result: T, businessId: string, headers: HeadersProvider, isCurrent: () => boolean): Promise<T> {
  if (!result.async_job_id) return result;
  const query=new URLSearchParams({scope_type:'business',scope_id:businessId});
  for(let attempt=0;attempt<150 && isCurrent();attempt++) {
    const body=await jsonRequest(`/api/operator/mobile/jobs/${result.async_job_id}?${query}`,{headers:headers()});
    if(!isCurrent())return result;
    if(body.job?.status==='completed')return body.job.result;
    if(['failed','cancelled'].includes(body.job?.status))return {...result,status:body.job.status,chat_response:'Подготовить изменение не удалось. План остался прежним. '+(body.job.error || '')};
    await new Promise<void>(resolve=>window.setTimeout(resolve,2000));
  }
  return result;
}
