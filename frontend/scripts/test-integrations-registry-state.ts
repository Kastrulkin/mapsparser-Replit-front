import { IntegrationsRegistryRawState, mapIntegrationsState } from '../src/pages/dashboard/settings/integrationsRegistryState';

const strictEqual = (actual: unknown, expected: unknown) => {
  if (actual !== expected) {
    throw new Error(`Expected ${String(expected)}, got ${String(actual)}`);
  }
};

const service = (state: IntegrationsRegistryRawState, id: string) => {
  const item = mapIntegrationsState(state).find((connection) => connection.id === id);
  if (!item) throw new Error(`Missing service ${id}`);
  return item;
};

const baseState: IntegrationsRegistryRawState = {
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

const runCase = (name: string, check: () => void) => {
  check();
  console.log(`ok - ${name}`);
};

runCase('registry has one flat row per planned service', () => {
  strictEqual(mapIntegrationsState(baseState).length, 11);
});

runCase('telegram partial needs action', () => {
  strictEqual(service({
    ...baseState,
    telegramOwnerLinked: true,
    telegramPublishStatus: {
      configured: false,
      global_bot_configured: true,
      telegram_chat_id: null,
    },
  }, 'telegram').status, 'action_required');
});

runCase('whatsapp phone without waba needs action', () => {
  strictEqual(service({
    ...baseState,
    business: {
      whatsapp_phone: '+79990000000',
    },
  }, 'whatsapp').status, 'action_required');
});

runCase('google sheets connected is separate from business location', () => {
  const state: IntegrationsRegistryRawState = {
    ...baseState,
    externalAccounts: [
      {
        source: 'google_business',
        external_id: null,
        display_name: 'Google access',
        is_active: true,
      },
    ],
  };
  strictEqual(service(state, 'google_sheets').status, 'connected');
  strictEqual(service(state, 'google_business').status, 'action_required');
});

runCase('vk missing is not connected and short', () => {
  const vk = service(baseState, 'vk');
  strictEqual(vk.status, 'not_connected');
  strictEqual(vk.nextAction, 'Добавьте токен и ID сообщества.');
});

runCase('manual map services stay manual by default', () => {
  strictEqual(service(baseState, 'yandex_maps').status, 'manual');
  strictEqual(service(baseState, '2gis').status, 'manual');
});

runCase('yclients and altegio are separate rows', () => {
  const state: IntegrationsRegistryRawState = {
    ...baseState,
    crmProviders: [
      {
        provider: 'yclients',
        label: 'YCLIENTS',
        connection: null,
      },
      {
        provider: 'altegio',
        label: 'Altegio',
        connection: {
          status: 'connected',
          display_name: 'Altegio Tallinn',
        },
      },
    ],
  };
  strictEqual(service(state, 'yclients').status, 'action_required');
  strictEqual(service(state, 'altegio').status, 'connected');
});

runCase('maton connected from external account', () => {
  strictEqual(service({
    ...baseState,
    externalAccounts: [
      {
        source: 'maton',
        external_id: 'maton',
        display_name: 'Maton.ai',
        is_active: true,
      },
    ],
  }, 'maton').status, 'connected');
});
