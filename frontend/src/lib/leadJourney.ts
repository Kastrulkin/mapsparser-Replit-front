import type { LeadJourneyKey, LeadJourneyDirection } from "../content/growthDirections";
export type { LeadJourneyKey, LeadJourneyDirection } from "../content/growthDirections";
import { leadJourneyDirections } from "../content/growthDirections";
export { leadJourneyDirections } from "../content/growthDirections";
import { browserBearerToken } from '@/lib/browserSessionFetch';
import { newAuth } from '@/lib/auth_new';

export const LEAD_JOURNEY_STORAGE_KEY = 'localos_lead_journey_intent';
export const LEAD_JOURNEY_TOKEN_STORAGE_KEY = 'localos_lead_journey_token';

export type JourneyOpportunity = {
  flow_type: 'influencer' | 'partnership' | 'maps' | 'content' | 'automation' | 'average_ticket';
  entity_type: string;
  entity_id?: string;
  title: string;
  summary: string;
  reason: string;
  mechanic?: string;
  message_excerpt?: string;
  public_url?: string;
  count?: number;
  metrics?: Record<string, string | number | boolean>;
  tasks?: Array<{ title: string; reason?: string }>;
};

export type PublicLeadJourney = {
  id: string;
  status: string;
  source: string;
  business?: { name?: string; city?: string; address?: string };
  opportunities: JourneyOpportunity[];
  selected_flow?: string | null;
  expires_at?: string;
};

export type JourneyAction = {
  id: string;
  journey_id?: string | null;
  business_id?: string | null;
  flow_type: 'influencer' | 'partnership' | 'maps' | 'content' | 'automation' | 'average_ticket' | 'upgrade';
  entity_type: string;
  entity_id?: string | null;
  action_type: string;
  status: 'ready' | 'in_progress' | 'waiting' | 'blocked' | 'completed' | 'superseded' | 'cancelled';
  priority: number;
  due_at?: string | null;
  title: string;
  description: string;
  cta_label: string;
  cta_target?: { screen?: string; action_id?: string };
  payload?: Record<string, unknown>;
  allowed_commands: string[];
  access?: {
    allowed: boolean;
    capability: string;
    status: 'available' | 'payment_required';
    code?: string | null;
    payment_required?: boolean;
    required_tier?: string;
    required_tier_name?: string;
    reason?: string;
    cta_label?: string;
    cta_target?: { screen?: string; url?: string };
  };
  version: number;
};

const readJson = async (response: Response) => {
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'Не удалось продолжить действие');
  return data;
};

export const loadPublicLeadJourney = async (token: string): Promise<PublicLeadJourney> => {
  const response = await fetch(`/api/journeys/public/${encodeURIComponent(token)}`);
  const data = await readJson(response);
  return data.journey;
};

export const trackPublicJourneyEvent = async (token: string, eventName: string, opportunity?: JourneyOpportunity) => {
  try {
    await fetch(`/api/journeys/public/${encodeURIComponent(token)}/events`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      keepalive: true,
      body: JSON.stringify({
        event_name: eventName,
        surface: 'web',
        flow_type: opportunity?.flow_type,
        entity_type: opportunity?.entity_type,
        entity_id: opportunity?.entity_id,
      }),
    });
  } catch {
    // Telemetry never blocks the public journey.
  }
};

export const preparePublicOpportunity = async (token: string, opportunity: JourneyOpportunity) => {
  const entityId = opportunity.entity_id || '_';
  const response = await fetch(`/api/journeys/public/${encodeURIComponent(token)}/opportunities/${opportunity.flow_type}/${encodeURIComponent(entityId)}/preview`, { method: 'POST' });
  const data = await readJson(response);
  return data.preview;
};

export const loadJourneyActions = async (businessId: string): Promise<JourneyAction[]> => {
  const response = await fetch(`/api/journey-actions?business_id=${encodeURIComponent(businessId)}`, {
    headers: { Authorization: `Bearer ${browserBearerToken() || ''}` },
  });
  const data = await readJson(response);
  return data.actions || [];
};

export const claimLeadJourney = async (token: string, businessId: string, surface: 'web' | 'telegram_mini_app' = 'web'): Promise<JourneyAction> => {
  const data = await newAuth.makeRequest('/journeys/claim', {
    method: 'POST',
    body: JSON.stringify({ token, business_id: businessId, surface }),
  });
  return data.action;
};

export const createJourneyCommandIdempotencyKey = () => (
  typeof crypto.randomUUID === 'function' ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`
);

export const runJourneyCommand = async ({
  action,
  businessId,
  command,
  payload = {},
  surface = 'web',
  idempotencyKey = createJourneyCommandIdempotencyKey(),
}: {
  action: JourneyAction;
  businessId: string;
  command: string;
  payload?: Record<string, unknown>;
  surface?: 'web' | 'telegram_mini_app';
  idempotencyKey?: string;
}) => {
  if (surface === 'web') {
    return newAuth.makeRequest(`/journey-actions/${encodeURIComponent(action.id)}/commands`, {
      method: 'POST',
      headers: { 'Idempotency-Key': idempotencyKey },
      body: JSON.stringify({ business_id: businessId, command, version: action.version, surface, payload }),
    });
  }
  const miniSession = window.sessionStorage.getItem('localos_mini_session') || '';
  const response = await fetch(`/api/journey-actions/${encodeURIComponent(action.id)}/commands`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${miniSession}`,
      'Content-Type': 'application/json',
      'Idempotency-Key': idempotencyKey,
    },
    body: JSON.stringify({ business_id: businessId, command, version: action.version, surface, payload }),
  });
  return readJson(response);
};

export const isLeadJourneyKey = (value: string | null): value is LeadJourneyKey => (
  value === 'influencers' || value === 'partnerships' || value === 'maps' || value === 'content' || value === 'automation' || value === 'average_ticket'
);

export const leadJourneyKeyForFlow = (flow: string | null | undefined): LeadJourneyKey | null => {
  if (flow === 'influencer') return 'influencers';
  if (flow === 'partnership') return 'partnerships';
  const candidate = flow || null;
  return isLeadJourneyKey(candidate) ? candidate : null;
};

export const journeyActionRoute = (action: JourneyAction) => {
  const screen = action.cta_target?.screen;
  const routes: Record<string, string> = {
    influencers: '/dashboard/influencers',
    partnerships: '/dashboard/promotion/partnerships',
    progress: '/dashboard/card',
    maps: '/dashboard/card',
    content: '/dashboard/content',
    agents: '/dashboard/agents',
    average_ticket: '/dashboard/average-ticket',
    settings: '/dashboard/settings',
    today: '/dashboard/today',
  };
  const base = routes[screen || ''] || '/dashboard/today';
  const separator = base.includes('?') ? '&' : '?';
  return `${base}${separator}journey_action=${encodeURIComponent(action.id)}`;
};

const businessIdFromUser = (user: { businesses?: unknown[] } | null | undefined) => {
  const businesses = Array.isArray(user?.businesses) ? user.businesses : [];
  const savedBusinessId = window.localStorage.getItem('selectedBusinessId') || '';
  const availableIds = businesses.map((business) => {
    if (!business || typeof business !== 'object' || !('id' in business)) return '';
    const value = business.id;
    return typeof value === 'string' ? value : '';
  }).filter(Boolean);
  if (savedBusinessId && availableIds.includes(savedBusinessId)) return savedBusinessId;
  return availableIds[0] || '';
};

export const resolveStoredLeadJourney = async (preferredBusinessId = '') => {
  const token = readLeadJourneyToken();
  if (!token) return null;
  const user = await newAuth.getCurrentUser();
  const businessId = preferredBusinessId || businessIdFromUser(user);
  if (!businessId) throw new Error('Не найден бизнес для продолжения персонального сценария');
  const action = await claimLeadJourney(token, businessId);
  const route = journeyActionRoute(action);
  clearLeadJourneyToken();
  clearLeadJourneyIntent();
  return { action, businessId, route };
};

export const getLeadJourneyDirection = (key: LeadJourneyKey | null | undefined) => (
  leadJourneyDirections.find((direction) => direction.key === key) || null
);

export const saveLeadJourneyIntent = (key: LeadJourneyKey) => {
  try {
    window.localStorage.setItem(LEAD_JOURNEY_STORAGE_KEY, key);
  } catch {
    // Storage may be unavailable in privacy mode; navigation still works.
  }
};

export const saveLeadJourneyToken = (token: string) => {
  try {
    window.localStorage.setItem(LEAD_JOURNEY_TOKEN_STORAGE_KEY, token);
  } catch {
    // The token is also carried in the registration URL.
  }
};

export const readLeadJourneyToken = () => {
  try {
    return window.localStorage.getItem(LEAD_JOURNEY_TOKEN_STORAGE_KEY) || '';
  } catch {
    return '';
  }
};

export const clearLeadJourneyToken = () => {
  try {
    window.localStorage.removeItem(LEAD_JOURNEY_TOKEN_STORAGE_KEY);
  } catch {
    // No cleanup is possible in restricted storage mode.
  }
};

export const readLeadJourneyIntent = (): LeadJourneyKey | null => {
  try {
    const value = window.localStorage.getItem(LEAD_JOURNEY_STORAGE_KEY);
    return isLeadJourneyKey(value) ? value : null;
  } catch {
    return null;
  }
};

export const clearLeadJourneyIntent = () => {
  try {
    window.localStorage.removeItem(LEAD_JOURNEY_STORAGE_KEY);
  } catch {
    // Nothing else is required when storage is unavailable.
  }
};
