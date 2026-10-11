export interface SubscriptionAccessPayload {
  tier: string;
  tier_name: string;
  status: string;
  active: boolean;
  subscription_expired?: boolean;
  capabilities: SubscriptionCapability[];
  groups?: { maps?: boolean; acquisition?: boolean; management?: boolean };
}
export type SubscriptionCapability = 'progress'
  | 'maps' | 'maps.news' | 'telegram_radar' | 'web_analytics'
  | 'acquisition' | 'partnerships' | 'influencers' | 'ai_visibility'
  | 'management' | 'finance' | 'average_ticket' | 'agents' | 'operator'
  | 'chats' | 'social_content' | 'automation';

export interface SubscriptionAutomationAccess {
  automationAllowed: boolean;
  message: string | null;
}

export interface BusinessCapabilityAccess {
  allowed: boolean;
  capability: SubscriptionCapability;
  tier: string;
  tierName: string;
  requiredTier: 'starter' | 'professional' | 'concierge';
  requiredTierName: 'Карты' | 'Привлечение' | 'Управление';
  message: string | null;
}

const ACTIVE_STATUSES = new Set(['active', 'trialing']);
const TIER_ALIASES: Record<string, string> = { basic: 'starter', pro: 'professional', enterprise: 'concierge' };
const TIER_RANK: Record<string, number> = { starter: 1, professional: 2, concierge: 3, elite: 3, promo: 3 };
const TIER_NAMES: Record<string, string> = { starter: 'Карты', professional: 'Привлечение', concierge: 'Управление', elite: 'Elite', promo: 'Промо' };
const CAPABILITY_TIER: Record<SubscriptionCapability, 'starter' | 'professional' | 'concierge'> = {
  progress: 'starter', maps: 'starter', 'maps.news': 'starter', telegram_radar: 'starter', web_analytics: 'starter',
  acquisition: 'professional', partnerships: 'professional', influencers: 'professional', ai_visibility: 'professional',
  management: 'concierge', finance: 'concierge', average_ticket: 'concierge', agents: 'concierge',
  operator: 'concierge', chats: 'concierge', social_content: 'concierge', automation: 'concierge',
};

const isSubscriptionExpired = (value: unknown) => {
  if (!value) return false;
  const date = new Date(String(value));
  return !Number.isNaN(date.getTime()) && date.getTime() < Date.now();
};

export const getCapabilityAccessForBusiness = (business: any, capability: SubscriptionCapability): BusinessCapabilityAccess => {
  const rawTier = String(business?.subscription_tier || '').trim().toLowerCase();
  const tier = TIER_ALIASES[rawTier] || rawTier || 'none';
  const status = String(business?.subscription_status || '').trim().toLowerCase();
  const requiredTier = CAPABILITY_TIER[capability];
  const requiredTierName = requiredTier === 'starter' ? 'Карты' : requiredTier === 'professional' ? 'Привлечение' : 'Управление';
  const active = ACTIVE_STATUSES.has(status) && !isSubscriptionExpired(business?.subscription_ends_at);
  const serverAccess = business?.subscription_access;
  const allowed = serverAccess && Array.isArray(serverAccess.capabilities) ? Boolean(serverAccess.active) && serverAccess.capabilities.includes(capability) : active && (TIER_RANK[tier] || 0) >= TIER_RANK[requiredTier];
  return { allowed, capability, tier, tierName: TIER_NAMES[tier] || 'Без тарифа', requiredTier, requiredTierName, message: allowed ? null : `Функция входит в тариф «${requiredTierName}».` };
};

export function getAutomationAccessForBusiness(business: any): SubscriptionAutomationAccess {
  const access = getCapabilityAccessForBusiness(business, 'automation');
  return { automationAllowed: access.allowed, message: access.message };
}
