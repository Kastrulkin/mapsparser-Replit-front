import { useEffect, useRef, useState } from 'react';
import type { Bootstrap } from '@/features/telegram/types';
import type { MobileScope } from '@/components/telegram/ScopeProvider.logic';
import { miniAppLaunchParams, miniAppPlatform, miniWebApp } from '@/lib/miniAppPlatform';
import { resolveMobileRoute } from '@/lib/mobileDeepLinkRouter';

/** Restore only the server-verified conversation belonging to this launch's business. */
export function useClientHandoffLaunch(bootstrap: Bootstrap | null, scope: MobileScope | undefined, restore: () => void) {
  const callback = useRef(restore); callback.current = restore;
  const [reopenRevision, setReopenRevision] = useState(0);
  const target = bootstrap?.resolved_deep_link;
  const params = miniAppLaunchParams();
  const isDirectClientLaunch = miniAppPlatform() === 'telegram'
    && params.get('screen') === 'client_handoffs' && params.get('scope_type') === 'business'
    && scope?.kind === 'business' && scope.id === params.get('scope_id')
    && target?.screen === 'client_handoffs' && target.item_type === 'client_conversation'
    && Boolean(target.item_id) && !target.fallback_applied
    && resolveMobileRoute(target, bootstrap?.navigation || []).module === 'client_handoffs';

  useEffect(() => {
    if (!isDirectClientLaunch) return;
    const app = miniWebApp();
    const resume = () => { callback.current(); setReopenRevision(value => value + 1); };
    // Telegram Web retains the iframe. Restore while hidden as well as on activation,
    // so the cached frame never resumes on a screen chosen before closing.
    const visibility = () => resume();
    const pageshow = (event: PageTransitionEvent) => { if (event.persisted) resume(); };
    app?.onEvent?.('activated', resume);
    app?.onEvent?.('deactivated', resume);
    document.addEventListener('visibilitychange', visibility);
    window.addEventListener('pageshow', pageshow);
    return () => {
      app?.offEvent?.('activated', resume);
      app?.offEvent?.('deactivated', resume);
      document.removeEventListener('visibilitychange', visibility);
      window.removeEventListener('pageshow', pageshow);
    };
  }, [isDirectClientLaunch, target?.item_id, scope?.id]);
  return { isDirectClientLaunch, reopenRevision };
}
