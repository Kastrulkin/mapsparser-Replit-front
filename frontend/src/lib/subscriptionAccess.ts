export interface SubscriptionAutomationAccess {
  automationAllowed: boolean;
  message: string | null;
}

const PAID_TIERS = new Set(['starter', 'professional', 'concierge', 'elite', 'promo', 'basic', 'pro', 'enterprise']);
const ACTIVE_STATUSES = new Set(['active', 'trialing']);

export function getAutomationAccessForBusiness(business: any): SubscriptionAutomationAccess {
  const tier = String(business?.subscription_tier || '').trim().toLowerCase();
  const status = String(business?.subscription_status || '').trim().toLowerCase();

  if (PAID_TIERS.has(tier) && ACTIVE_STATUSES.has(status)) {
    return { automationAllowed: true, message: null };
  }

  return {
    automationAllowed: false,
    message: 'Автоматизация доступна только после оплаты тарифа.',
  };
}
