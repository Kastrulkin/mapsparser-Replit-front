const VK_OAUTH_STORAGE_PREFIX = 'localos_vk_oauth:';

type StartVkOAuthParams = {
  businessId: string;
  groupId: string;
  authToken: string;
  returnTo: string;
};

export type VkOAuthCompletion = {
  handled: boolean;
  success: boolean;
  message?: string;
};

const base64Url = (bytes: Uint8Array) => {
  let binary = '';
  bytes.forEach((byte) => {
    binary += String.fromCharCode(byte);
  });
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '');
};

const removeVkOAuthParams = () => {
  const url = new URL(window.location.href);
  ['vk_auth', 'vk_code', 'vk_device_id', 'vk_state', 'vk_client_state'].forEach((key) => {
    url.searchParams.delete(key);
  });
  window.history.replaceState({}, document.title, `${url.pathname}${url.search}${url.hash}`);
};

const readStoredVerifier = (clientState: string, businessId: string) => {
  const storageKey = `${VK_OAUTH_STORAGE_PREFIX}${clientState}`;
  const raw = window.sessionStorage.getItem(storageKey);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object') return null;
    if (String(parsed.businessId || '') !== businessId) return null;
    const createdAt = Number(parsed.createdAt || 0);
    if (!createdAt || Date.now() - createdAt > 20 * 60 * 1000) return null;
    const verifier = String(parsed.verifier || '');
    if (!verifier) return null;
    return { verifier, storageKey };
  } catch {
    return null;
  }
};

export const startVkOAuthConnection = async ({
  businessId,
  groupId,
  authToken,
  returnTo,
}: StartVkOAuthParams) => {
  if (!window.crypto?.subtle) {
    throw new Error('Браузер не поддерживает безопасное подключение VK. Обновите браузер.');
  }
  const verifierBytes = window.crypto.getRandomValues(new Uint8Array(32));
  const verifier = base64Url(verifierBytes);
  const challengeDigest = await window.crypto.subtle.digest(
    'SHA-256',
    new TextEncoder().encode(verifier),
  );
  const codeChallenge = base64Url(new Uint8Array(challengeDigest));
  const clientState = base64Url(window.crypto.getRandomValues(new Uint8Array(24)));
  const storageKey = `${VK_OAUTH_STORAGE_PREFIX}${clientState}`;
  window.sessionStorage.setItem(storageKey, JSON.stringify({
    verifier,
    businessId,
    createdAt: Date.now(),
  }));

  const response = await fetch(`/api/business/${encodeURIComponent(businessId)}/vk/oauth/start`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${authToken}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      group_id: groupId,
      code_challenge: codeChallenge,
      client_state: clientState,
      return_to: returnTo,
    }),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok || !data.success || !data.auth_url) {
    window.sessionStorage.removeItem(storageKey);
    throw new Error(data.error || 'Не удалось начать подключение VK.');
  }
  window.location.href = data.auth_url;
};

export const completeVkOAuthFromLocation = async (
  businessId: string,
  authToken: string,
): Promise<VkOAuthCompletion> => {
  const params = new URLSearchParams(window.location.search);
  const status = String(params.get('vk_auth') || '');
  if (!status) return { handled: false, success: false };
  if (status !== 'pending') {
    removeVkOAuthParams();
    if (status === 'cancelled') {
      return { handled: true, success: false, message: 'Подключение VK отменено.' };
    }
    return { handled: true, success: false, message: 'Не удалось подключить VK. Начните ещё раз.' };
  }

  const code = String(params.get('vk_code') || '');
  const deviceId = String(params.get('vk_device_id') || '');
  const state = String(params.get('vk_state') || '');
  const clientState = String(params.get('vk_client_state') || '');
  const stored = readStoredVerifier(clientState, businessId);
  removeVkOAuthParams();
  if (!code || !deviceId || !state || !stored) {
    return {
      handled: true,
      success: false,
      message: 'Сессия подключения VK истекла. Нажмите «Подключить VK» ещё раз.',
    };
  }

  try {
    const response = await fetch(`/api/business/${encodeURIComponent(businessId)}/vk/oauth/complete`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${authToken}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        code,
        device_id: deviceId,
        state,
        code_verifier: stored.verifier,
      }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok || !data.success) {
      throw new Error(data.error || 'Не удалось завершить подключение VK.');
    }
    return {
      handled: true,
      success: true,
      message: data.message || 'VK подключён и готов к проверке публикаций.',
    };
  } finally {
    window.sessionStorage.removeItem(stored.storageKey);
  }
};
