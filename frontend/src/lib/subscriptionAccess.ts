export type SubscriptionCapability =
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
  maps: 'starter', 'maps.news': 'starter', telegram_radar: 'starter', web_analytics: 'starter',
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
  const requiredTierName = TIER_NAMES[requiredTier];
  const active = ACTIVE_STATUSES.has(status) && !isSubscriptionExpired(business?.subscription_ends_at);
  const allowed = active && (TIER_RANK[tier] || 0) >= TIER_RANK[requiredTier];
  return { allowed, capability, tier, tierName: TIER_NAMES[tier] || 'Без тарифа', requiredTier, requiredTierName, message: allowed ? null : `Функция входит в тариф «${requiredTierName}».` };
};

export function getAutomationAccessForBusiness(business: any): SubscriptionAutomationAccess {
  const access = getCapabilityAccessForBusiness(business, 'automation');
  return { automationAllowed: access.allowed, message: access.message };
}
