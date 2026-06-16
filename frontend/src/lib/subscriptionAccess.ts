export interface SubscriptionAutomationAccess {
  automationAllowed: boolean;
  message: string | null;
}

const PAID_TIERS = new Set(['starter', 'professional', 'concierge', 'elite', 'promo', 'basic', 'pro', 'enterprise']);
const ACTIVE_STATUSES = new Set(['active', 'trialing']);

function isSubscriptionExpired(value: unknown): boolean {
  if (!value) {
    return false;
  }
  const date = new Date(String(value));
  if (Number.isNaN(date.getTime())) {
    return false;
  }
  return date.getTime() < Date.now();
}

export function getAutomationAccessForBusiness(business: any): SubscriptionAutomationAccess {
  const tier = String(business?.subscription_tier || '').trim().toLowerCase();
  const status = String(business?.subscription_status || '').trim().toLowerCase();
  const subscriptionExpired = isSubscriptionExpired(business?.subscription_ends_at);

  if (PAID_TIERS.has(tier) && ACTIVE_STATUSES.has(status) && !subscriptionExpired) {
    return { automationAllowed: true, message: null };
  }

  if (subscriptionExpired) {
    return {
      automationAllowed: false,
      message: 'Оплаченный период закончился.',
    };
  }

  return {
    automationAllowed: false,
    message: 'Автоматизация доступна только после оплаты тарифа.',
  };
}
