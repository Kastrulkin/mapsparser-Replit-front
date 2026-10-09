import base from '@playwright/test';
import { createOfflineBrowserPolicy } from './offline-browser-policy';

export { expect } from '@playwright/test';
export type { Page, Route } from '@playwright/test';

type BlockedRequest = {
  action: 'api' | 'external';
  safeUrl: string;
};

const formatBlockedRequests = (blockedRequests: BlockedRequest[]) => {
  const listedRequests = blockedRequests
    .slice(0, 10)
    .map(({ action, safeUrl }) => `${action}: ${safeUrl}`)
    .join(', ');
  const omittedRequests = blockedRequests.length - 10;
  return omittedRequests > 0 ? `${listedRequests}, and ${omittedRequests} more` : listedRequests;
};

// Page-scoped routes installed by each spec take precedence over this context fallback.
const offlineTest = base.extend({
  serviceWorkers: 'block',
  context: async ({ baseURL, context }, provideContext, testInfo) => {
    const policy = createOfflineBrowserPolicy(baseURL ?? '');
    const blockedRequests: BlockedRequest[] = [];
    let allowedHttpRequests = 0;
    let allowedWebSocketConnections = 0;
    let telegramSdkStubs = 0;

    await context.route('**/*', async (route) => {
      const decision = policy.decide(route.request().url());
      if (decision.action === 'allow') {
        allowedHttpRequests += 1;
        await route.continue();
        return;
      }
      if (decision.action === 'stub-telegram-sdk') {
        telegramSdkStubs += 1;
        await route.fulfill({ contentType: 'application/javascript', body: '' });
        return;
      }
      blockedRequests.push({
        action: decision.action === 'block-api' ? 'api' : 'external',
        safeUrl: decision.safeUrl,
      });
      await route.abort('blockedbyclient');
    });

    await context.routeWebSocket('**/*', async (webSocketRoute) => {
      const decision = policy.decide(webSocketRoute.url());
      if (decision.action === 'allow') {
        allowedWebSocketConnections += 1;
        webSocketRoute.connectToServer();
        return;
      }
      blockedRequests.push({
        action: decision.action === 'block-api' ? 'api' : 'external',
        safeUrl: decision.safeUrl,
      });
      await webSocketRoute.close({ code: 1008, reason: 'Offline browser audit guard' });
    });

    await provideContext(context);

    const blockedApiRequests = blockedRequests.filter(({ action }) => action === 'api').length;
    const blockedExternalRequests = blockedRequests.length - blockedApiRequests;
    await testInfo.attach('offline-browser-guard', {
      body: Buffer.from(JSON.stringify({
        guard_active: true,
        base_origin: new URL(baseURL ?? '').origin,
        allowed_http_requests: allowedHttpRequests,
        allowed_websocket_connections: allowedWebSocketConnections,
        telegram_sdk_stubs: telegramSdkStubs,
        blocked_api_requests: blockedApiRequests,
        blocked_external_requests: blockedExternalRequests,
      })),
      contentType: 'application/json',
    });

    if (blockedRequests.length > 0) {
      throw new Error(`Offline browser guard blocked unexpected requests: ${formatBlockedRequests(blockedRequests)}`);
    }
  },
});

export default offlineTest;
