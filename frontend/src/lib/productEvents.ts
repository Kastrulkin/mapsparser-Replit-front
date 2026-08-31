import { browserBearerToken } from '@/lib/browserSessionFetch';
type ProductEvent = {
  eventName: 'progress_open' | 'mission_open' | 'statistics_flow_opened' | 'crm_request_created';
  businessId?: string | null;
  objectType?: string;
  objectId?: string;
  properties?: Record<string, string | number | boolean | null | undefined>;
};

/** Analytics must never delay or block an operational action. */
export const trackProductEvent = ({ eventName, businessId, objectType, objectId, properties }: ProductEvent) => {
  if (!businessId || typeof window === 'undefined') return;
  if (window.sessionStorage.getItem('localos_demo_mode') === '1' || window.localStorage.getItem('demo_auth_token')) return;

  const payload = {
    event_name: eventName,
    business_id: businessId,
    surface: 'web',
    object_type: objectType,
    object_id: objectId,
    properties,
  };

  try {
    void fetch('/api/product/events', {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${browserBearerToken() || ''}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
      keepalive: true,
    }).catch(() => undefined);
  } catch {
    // Tracking is best-effort: the dashboard remains available offline and in privacy-restricted browsers.
  }
};
