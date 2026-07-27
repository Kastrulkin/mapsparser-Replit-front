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
  if (!response.ok || payload?.success === false) {
    throw new Error(payload?.error || 'Не удалось выполнить запрос.');
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
