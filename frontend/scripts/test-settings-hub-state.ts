import { SettingsHubRawState, mapSettingsState } from '../src/pages/dashboard/settings/settingsHubState';

const strictEqual = (actual: unknown, expected: unknown) => {
  if (actual !== expected) {
    throw new Error(`Expected ${String(expected)}, got ${String(actual)}`);
  }
};

const baseState: SettingsHubRawState = {
  business: {},
  telegramOwnerLinked: false,
  telegramPublishStatus: {
    configured: false,
    global_bot_configured: false,
    telegram_chat_id: null,
  },
  socialReadiness: [],
  externalAccounts: [],
  crmProviders: [],
};

const runCase = (name: string, state: SettingsHubRawState, check: (mapped: ReturnType<typeof mapSettingsState>) => void) => {
  const mapped = mapSettingsState(state);
  check(mapped);
  console.log(`ok - ${name}`);
};

runCase('telegram owner bound but no publication target', {
  ...baseState,
  telegramOwnerLinked: true,
  telegramPublishStatus: {
    configured: false,
    global_bot_configured: true,
    telegram_chat_id: null,
  },
}, (mapped) => {
  strictEqual(mapped.summary.publications, 'attention');
  strictEqual(mapped.nextStep?.module, 'telegram');
  strictEqual(mapped.nextStep?.actionLabel, 'Set publication target');
  strictEqual(mapped.modules.telegram.displayStatus, 'partially_configured');
});

runCase('telegram owner and publication target ready', {
  ...baseState,
  telegramOwnerLinked: true,
  telegramPublishStatus: {
    configured: false,
    global_bot_configured: true,
    telegram_chat_id: '@localos',
  },
}, (mapped) => {
  strictEqual(mapped.modules.telegram.status, 'ready');
});

runCase('whatsapp number without waba needs attention', {
  ...baseState,
  business: {
    whatsapp_phone: '+79990000000',
  },
}, (mapped) => {
  strictEqual(mapped.modules.whatsapp.status, 'attention');
  strictEqual(mapped.modules.whatsapp.primaryAction.label, 'Configure sending');
});

runCase('crm absent is not configured', {
  ...baseState,
  crmProviders: [
    {
      provider: 'demo',
      label: 'Demo CRM',
      connection: null,
    },
  ],
}, (mapped) => {
  strictEqual(mapped.modules.crm.status, 'not_configured');
});

runCase('google connected with location is ready', {
  ...baseState,
  externalAccounts: [
    {
      source: 'google_business',
      external_id: 'locations/123',
      display_name: 'LocalOS Demo',
      is_active: 1,
    },
  ],
}, (mapped) => {
  strictEqual(mapped.modules.google.status, 'ready');
});

runCase('vk and meta absent follow publication readiness defaults', {
  ...baseState,
  socialReadiness: [
    {
      platform: 'vk',
      publish_mode: 'api',
      ready: false,
    },
    {
      platform: 'instagram',
      publish_mode: 'manual',
      ready: false,
    },
  ],
}, (mapped) => {
  strictEqual(mapped.modules.vk.status, 'attention');
  strictEqual(mapped.modules.meta.status, 'manual');
});
