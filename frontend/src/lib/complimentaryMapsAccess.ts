/** Complimentary access reuses the admin tier route, never the payment ledger. */
export function complimentaryMapsAccess(businessId: string, now: Date) {
  if (!businessId.trim() || !Number.isFinite(now.getTime())) {
    throw new Error('Не указан бизнес или дата начала доступа.');
  }
  return {
    endpoint: `/admin/businesses/${encodeURIComponent(businessId)}/promo`,
    payload: {
      is_promo: true,
      tier: 'starter',
      subscription_ends_at: new Date(now.getTime() + 30 * 24 * 60 * 60 * 1000).toISOString(),
    },
  };
}
