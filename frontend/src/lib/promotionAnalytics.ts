import type { PromotionKey } from '@/content/promotionContent';

declare global {
  interface Window {
    localosMetrikaEnabled?: boolean;
    ym?: (counter: number, action: string, goal: string, parameters?: Record<string, string>) => void;
  }
}

// Use the site's existing counter and consent state. Never send form values.
export function promotionGoal(goal: 'promotion_form_open' | 'promotion_request_accepted' | 'promotion_request_error', direction: PromotionKey) {
  if (window.localosMetrikaEnabled && typeof window.ym === 'function') {
    try { window.ym(105600878, 'reachGoal', goal, { direction }); } catch { /* Analytics must not affect delivery. */ }
  }
}
