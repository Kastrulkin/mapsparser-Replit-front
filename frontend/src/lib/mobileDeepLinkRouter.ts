export type MobileNavigationEntry = {
  key: string;
  status: 'available' | 'read_only' | 'hidden';
};

export type MobileResolvedDeepLink = {
  screen?: string;
  item_type?: string | null;
  item_id?: string | null;
  filters?: Record<string, string>;
};

export type MobileRoute = {
  tab: 'today' | 'tasks' | 'feed' | 'reviews' | 'progress' | 'operator' | 'more';
  module: string;
  itemId: string;
  reviewId: string;
  filters: Record<string, string>;
};

const primaryTabs = new Set(['today', 'tasks', 'feed', 'reviews', 'progress', 'operator']);

export const resolveMobileRoute = (
  target: MobileResolvedDeepLink | undefined,
  navigation: MobileNavigationEntry[],
): MobileRoute => {
  const allowed = new Set(navigation.filter((item) => item.status !== 'hidden').map((item) => item.key));
  const requested = target?.screen || 'today';
  const screen = requested === 'analytics' ? 'finance' : requested;
  const canOpen = allowed.has(screen);
  const safeScreen = canOpen ? screen : 'today';
  let tab: MobileRoute['tab'] = 'today';
  if (safeScreen === 'tasks' || safeScreen === 'feed' || safeScreen === 'reviews' || safeScreen === 'progress' || safeScreen === 'operator') tab = safeScreen;
  else if (!primaryTabs.has(safeScreen) && safeScreen !== 'today') tab = 'more';
  return {
    tab,
    module: primaryTabs.has(safeScreen) || safeScreen === 'today' || safeScreen === 'more' ? '' : safeScreen,
    itemId: canOpen ? target?.item_id || '' : '',
    reviewId: safeScreen === 'reviews' && target?.item_type === 'review' ? target.item_id || '' : '',
    filters: target?.filters || {},
  };
};
