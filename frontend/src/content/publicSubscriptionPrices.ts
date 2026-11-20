// Public display values shared with the existing pricing page; billing owns charges.
export const publicSubscriptionPrices = {
  starter: { rub: 1200, usd: 15, credits: 240 },
  professional: { rub: 5000, usd: 55, credits: 1000 },
  concierge: { rub: 25000, usd: 310, credits: null },
};
export const publicPlanPrice = (tier: keyof typeof publicSubscriptionPrices, english = false) => {
  const price = publicSubscriptionPrices[tier];
  return english ? `$${price.usd}` : `${price.rub.toLocaleString('ru-RU').replace(/\u00a0/g, ' ')} ₽`;
};
