type ParseRefreshPolicy = {
  can_refresh: boolean;
  reason: string | null;
  message: string | null;
  cooldown_days: number;
  last_completed_at: string | null;
  cooldown_until: string | null;
  invite_override_available: boolean;
  accepted_invites_count: number;
};

type MapSourcesResult = {
  sources: string[];
  hasConfiguredMapLink: boolean;
  hasSupportedConfiguredMapLink: boolean;
};

const authHeaders = () => ({
  Authorization: `Bearer ${localStorage.getItem('auth_token')}`,
});

const jsonRequest = async (path: string, init?: RequestInit) => {
  const response = await fetch(`${window.location.origin}${path}`, {
    ...init,
    headers: {
      ...authHeaders(),
      ...(init?.headers || {}),
    },
  });
  const data = await response.json();
  return { response, data };
};

export const normalizeParseRefreshPolicy = (value: any): ParseRefreshPolicy => {
  const source = value && typeof value === 'object' ? value : {};
  return {
    can_refresh: Boolean(source.can_refresh ?? true),
    reason: String(source.reason || '').trim() || null,
    message: String(source.message || '').trim() || null,
    cooldown_days: Number(source.cooldown_days || 7),
    last_completed_at: String(source.last_completed_at || '').trim() || null,
    cooldown_until: String(source.cooldown_until || '').trim() || null,
    invite_override_available: Boolean(source.invite_override_available),
    accepted_invites_count: Number(source.accepted_invites_count || 0),
  };
};

export const loadCardExternalSummary = (businessId: string, scopeNetwork: boolean) => {
  const scopeQuery = scopeNetwork ? '?scope=network' : '';
  return jsonRequest(`/api/business/${businessId}/external/summary${scopeQuery}`);
};

export const loadCardServices = (params: {
  businessId: string;
  scopeNetwork: boolean;
  source: string;
}) => {
  const query = new URLSearchParams();
  query.set('business_id', params.businessId);
  if (params.scopeNetwork) query.set('scope', 'network');
  if (params.source && params.source !== 'all') query.set('source', params.source);
  return jsonRequest(`/api/services/list?${query.toString()}`);
};

export const loadCardExternalPosts = (businessId: string, scopeNetwork: boolean) => {
  const scopeQuery = scopeNetwork ? '?scope=network' : '';
  return jsonRequest(`/api/business/${businessId}/external/posts${scopeQuery}`);
};

export const loadCardParseStatus = (businessId: string) => jsonRequest(`/api/business/${businessId}/parse-status`);

export const fetchManualCompetitors = (businessId: string) =>
  jsonRequest(`/api/business/${businessId}/competitors/manual`);

export const createManualCompetitor = (businessId: string, payload: { url: string; name: string }) =>
  jsonRequest(`/api/business/${businessId}/competitors/manual`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

export const requestManualCompetitorAudit = (businessId: string, competitorId: string) =>
  jsonRequest(`/api/business/${businessId}/competitors/manual/${competitorId}/audit`, { method: 'POST' });

export const removeManualCompetitor = (businessId: string, competitorId: string) =>
  jsonRequest(`/api/business/${businessId}/competitors/manual/${competitorId}`, { method: 'DELETE' });

export const loadCardClientInfo = (businessId: string) => jsonRequest(`/api/client-info?business_id=${businessId}`);

export const extractMapSources = (data: any, externalPosts: any[]): MapSourcesResult => {
  const sources = new Set<string>();
  let hasConfiguredMapLink = false;
  let hasSupportedConfiguredMapLink = false;

  if (Array.isArray(data?.mapLinks)) {
    data.mapLinks.forEach((link: any) => {
      const url = String(link?.url || '').trim().toLowerCase();
      if (!url) return;
      hasConfiguredMapLink = true;
      if (url.includes('yandex')) {
        sources.add('yandex');
        hasSupportedConfiguredMapLink = true;
      } else if (url.includes('2gis')) {
        sources.add('2gis');
        hasSupportedConfiguredMapLink = true;
      } else if (url.includes('google')) {
        sources.add('google');
      } else if (url.includes('apple')) {
        sources.add('apple');
      }
    });
  }

  externalPosts.forEach((post) => {
    const source = String(post?.source || '').trim().toLowerCase();
    if (source) sources.add(source);
  });

  return {
    sources: Array.from(sources),
    hasConfiguredMapLink,
    hasSupportedConfiguredMapLink,
  };
};

export const loadOperationsLearningMetrics = () => {
  const query = new URLSearchParams({ intent: 'operations' });
  return jsonRequest(`/api/admin/ai/learning-metrics?${query.toString()}`);
};

export const refreshCardDataFromSource = (businessId: string, source: string) => {
  const endpoint = source === '2gis'
    ? `/api/admin/2gis/sync/business/${businessId}`
    : `/api/admin/yandex/sync/business/${businessId}`;
  return jsonRequest(endpoint, { method: 'POST' });
};

export const loadNetworkLocationsState = (businessId: string) =>
  jsonRequest(`/api/business/${businessId}/network-locations`, {
    headers: { 'Content-Type': 'application/json' },
  });

export const createCardService = (payload: Record<string, unknown>) =>
  jsonRequest('/api/services/add', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

export const optimizeCardService = (payload: Record<string, unknown>) =>
  jsonRequest('/api/services/optimize', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

export const updateCardService = (serviceId: string, payload: Record<string, unknown>) =>
  jsonRequest(`/api/services/update/${serviceId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

export const removeCardService = (serviceId: string) =>
  jsonRequest(`/api/services/delete/${serviceId}`, { method: 'DELETE' });
