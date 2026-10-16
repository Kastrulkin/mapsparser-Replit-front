export type MobileScopeRef = {
  kind?: string;
  id?: string | null;
};

export const readMobileJson = async <T,>(response: Response): Promise<T> => {
  let payload;
  try {
    payload = await response.json();
  } catch {
    throw new Error('Сервис временно вернул некорректный ответ. Попробуйте ещё раз.');
  }
  window.dispatchEvent(new Event('localos:mobile-response'));
  if (!response.ok || payload?.success === false) {
    const reasons: Record<string, string> = {
      map_link_required: 'Добавьте ссылку на карточку Яндекса в настройках бизнеса.',
      map_organization_id_required: 'Не удалось определить организацию по ссылке Яндекса. Проверьте ссылку в настройках бизнеса.',
      unsupported_map_provider: 'Это обновление поддерживает карточку Яндекса. Выберите ссылку Яндекса.',
      preview_expired: 'Время подтверждения истекло. Закройте окно и проверьте обновление ещё раз.',
      insufficient_balance: 'Недостаточно кредитов для обновления.',
    };
    const blocked = payload?.operator_result?.blocked_reasons;
    const detail = Array.isArray(blocked) ? blocked.map((reason) => reasons[String(reason)]).filter(Boolean).join(' ') : '';
    throw new Error(detail || payload?.error || 'Не удалось выполнить запрос.');
  }
  return payload;
};

export const mobileScopeQuery = (scope?: MobileScopeRef) => {
  const params = new URLSearchParams();
  if (scope?.kind) params.set('scope_type', scope.kind);
  if (scope?.id) params.set('scope_id', scope.id);
  return params;
};

const sessionToken = () => window.sessionStorage.getItem('localos_mini_session') || '';

export const mobileJsonHeaders = () => ({
  'Content-Type': 'application/json',
  Authorization: `Bearer ${sessionToken()}`,
});

export const mobileAuthHeaders = () => ({ Authorization: `Bearer ${sessionToken()}` });

export type MobileJob = {
  id?: string;
  kind?: string;
  status?: 'queued' | 'running' | 'waiting_for_review' | 'completed' | 'failed' | 'cancelled';
  progress?: number;
  stage?: string;
  result?: Record<string, unknown>;
  error?: string | null;
  terminal?: boolean;
  available_actions?: string[];
};

export type MobileActionResult = {
  action_id?: string;
  job_id?: string;
  job?: MobileJob;
  status?: string;
  capability?: string;
};

export const confirmMobileAction = (actionId: string, scope?: MobileScopeRef) => fetch(
  `/api/operator/mobile/actions/${actionId}/confirm`,
  {
    method: 'POST',
    headers: mobileJsonHeaders(),
    body: JSON.stringify({ scope_type: scope?.kind, scope_id: scope?.id || null }),
  },
).then(readMobileJson<{ success?: boolean; idempotent?: boolean; operator_result?: MobileActionResult }>);

export const loadMobileJob = (jobId: string, scope?: MobileScopeRef, signal?: AbortSignal) => {
  const params = mobileScopeQuery(scope);
  return fetch(`/api/operator/mobile/jobs/${jobId}?${params.toString()}`, { headers: mobileAuthHeaders(), signal })
    .then(readMobileJson<{ success?: boolean; job?: MobileJob }>);
};

export const retryMobileJob = (jobId: string, scope?: MobileScopeRef) => fetch(
  `/api/operator/mobile/jobs/${jobId}/retry`,
  {
    method: 'POST',
    headers: mobileJsonHeaders(),
    body: JSON.stringify({ scope_type: scope?.kind, scope_id: scope?.id || null }),
  },
).then(readMobileJson<{ success?: boolean; job?: MobileJob }>);

export const cancelMobileJob = (jobId: string, scope?: MobileScopeRef) => fetch(
  `/api/operator/mobile/jobs/${jobId}/cancel`,
  {
    method: 'POST',
    headers: mobileJsonHeaders(),
    body: JSON.stringify({ scope_type: scope?.kind, scope_id: scope?.id || null }),
  },
).then(readMobileJson<{ success?: boolean; job?: MobileJob }>);
