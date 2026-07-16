import {
  SettingsHubBusiness,
  SettingsHubCrmProvider,
  SettingsHubExternalAccount,
  SettingsHubSocialReadiness,
} from './settingsHubState';

export type ConnectionType = 'oauth' | 'api_key' | 'manual' | 'credentials';

export type ConnectionStatus =
  | 'connected'
  | 'action_required'
  | 'not_connected'
  | 'manual'
  | 'error';

export type ServiceConnection = {
  id: string;
  name: string;
  tag?: string;
  description: string;
  connectionType: ConnectionType;
  status: ConnectionStatus;
  nextAction: string;
  primaryAction: {
    label: string;
    type: 'button' | 'link' | 'drawer';
    target: string;
  };
  hasLogs: boolean;
  hasHelp: boolean;
};

export type IntegrationsRegistryRawState = {
  business?: SettingsHubBusiness | null;
  telegramOwnerLinked?: boolean | null;
  telegramPublishStatus?: {
    configured?: boolean | null;
    global_bot_configured?: boolean | null;
    telegram_chat_id?: string | null;
  } | null;
  socialReadiness?: SettingsHubSocialReadiness[];
  externalAccounts?: SettingsHubExternalAccount[];
  crmProviders?: SettingsHubCrmProvider[];
};

const hasText = (value: unknown) => String(value || '').trim().length > 0;

const accountIsActive = (account: SettingsHubExternalAccount) => {
  if (typeof account.is_active === 'number') return account.is_active !== 0;
  if (typeof account.is_active === 'boolean') return account.is_active;
  return true;
};

const findAccount = (accounts: SettingsHubExternalAccount[], sources: string[]) => (
  accounts.find((account) => account.source ? sources.includes(account.source) && accountIsActive(account) : false) || null
);

const findReadiness = (readiness: SettingsHubSocialReadiness[], platforms: string[]) => (
  readiness.find((item) => item.platform ? platforms.includes(item.platform) : false) || null
);

const socialConnectionStatus = (
  readiness: SettingsHubSocialReadiness | null,
  fallback: ConnectionStatus,
): ConnectionStatus => {
  if (!readiness) return fallback;
  if (readiness.status === 'error') return 'error';
  if (readiness.ready) return 'connected';
  if (readiness.publish_mode === 'api') return 'action_required';
  return 'manual';
};

const crmProviderStatus = (provider: SettingsHubCrmProvider | null): ConnectionStatus => {
  if (!provider) return 'not_connected';
  if (provider.connection?.status === 'connected') return 'connected';
  if (provider.connection?.status === 'error') return 'error';
  return 'action_required';
};

const crmNextAction = (provider: SettingsHubCrmProvider | null, label: string) => {
  if (!provider) return `${label} можно подключить через токены филиала.`;
  if (provider.connection?.status === 'connected') return 'Подключение есть, можно проверить импорт в деталях.';
  if (provider.connection?.status === 'error') return 'Проверьте токены и повторите подключение.';
  return 'Заполните ID филиала и токены в настройке.';
};

export const mapIntegrationsState = (rawState: IntegrationsRegistryRawState): ServiceConnection[] => {
  const business = rawState.business || {};
  const accounts = rawState.externalAccounts || [];
  const readiness = rawState.socialReadiness || [];
  const crmProviders = rawState.crmProviders || [];

  const ownerBotConnected = Boolean(rawState.telegramOwnerLinked);
  const publicationTargetSet = hasText(rawState.telegramPublishStatus?.telegram_chat_id) || hasText(business.telegram_chat_id);
  const telegramCanPublish = Boolean(rawState.telegramPublishStatus?.configured || rawState.telegramPublishStatus?.global_bot_configured);
  const telegramReady = ownerBotConnected && publicationTargetSet && telegramCanPublish;
  const telegramPartial = ownerBotConnected || publicationTargetSet || telegramCanPublish;

  const phoneAdded = hasText(business.whatsapp_phone);
  const wabaConnected = hasText(business.waba_phone_id) && hasText(business.waba_access_token);

  const googleAccount = findAccount(accounts, ['google_business']);
  const googleSheetsConnected = Boolean(googleAccount);
  const googleBusinessConnected = Boolean(googleAccount && hasText(googleAccount.external_id));
  const vkAccount = findAccount(accounts, ['vk', 'vk_group', 'vk_business']);
  const vkOauthConnected = vkAccount?.connection_mode === 'vk_id_oauth';
  const metaAccount = findAccount(accounts, ['meta', 'instagram', 'facebook']);
  const matonAccount = findAccount(accounts, ['maton']);

  const vkReadiness = findReadiness(readiness, ['vk']);
  const metaReadiness = findReadiness(readiness, ['meta', 'instagram', 'facebook']);
  const yandexReadiness = findReadiness(readiness, ['yandex_maps', 'yandex_business', 'yandex']);
  const twoGisReadiness = findReadiness(readiness, ['2gis', 'dgis']);

  const yclientsProvider = crmProviders.find((provider) => provider.provider === 'yclients') || null;
  const altegioProvider = crmProviders.find((provider) => provider.provider === 'altegio') || null;

  return [
    {
      id: 'telegram',
      name: 'Telegram',
      tag: 'Коммуникации',
      description: 'Бот LocalOS для управления и отдельный канал/чат для постов.',
      connectionType: 'credentials',
      status: telegramReady ? 'connected' : telegramPartial ? 'action_required' : 'not_connected',
      nextAction: telegramReady ? 'Готов к управлению и согласованным постам.' : !ownerBotConnected ? 'Привяжите бот LocalOS в Telegram.' : 'Выберите канал или чат для постов.',
      primaryAction: { label: telegramReady ? 'Проверить' : 'Настроить', type: 'drawer', target: 'telegram' },
      hasLogs: true,
      hasHelp: true,
    },
    {
      id: 'whatsapp',
      name: 'WhatsApp',
      tag: 'Коммуникации',
      description: 'Номер и WABA-доступ для сообщений клиентам.',
      connectionType: 'credentials',
      status: wabaConnected ? 'connected' : phoneAdded ? 'action_required' : 'not_connected',
      nextAction: wabaConnected ? 'Отправка настроена.' : phoneAdded ? 'Добавьте WABA-доступ.' : 'Добавьте номер WhatsApp.',
      primaryAction: { label: wabaConnected ? 'Проверить' : 'Настроить', type: 'drawer', target: 'whatsapp' },
      hasLogs: true,
      hasHelp: true,
    },
    {
      id: 'google_sheets',
      name: 'Google Sheets',
      tag: 'Данные',
      description: 'Доступ агентам к строкам Google Таблиц.',
      connectionType: 'oauth',
      status: googleSheetsConnected ? 'connected' : 'not_connected',
      nextAction: googleSheetsConnected ? 'Google-доступ подключён.' : 'Подключите Google-доступ для таблиц.',
      primaryAction: { label: googleSheetsConnected ? 'Переподключить' : 'Подключить', type: 'drawer', target: 'google_sheets' },
      hasLogs: true,
      hasHelp: true,
    },
    {
      id: 'google_business',
      name: 'Google Business',
      tag: 'Публикации',
      description: 'Карточка компании, отзывы и посты Google.',
      connectionType: 'oauth',
      status: googleBusinessConnected ? 'connected' : googleSheetsConnected ? 'action_required' : 'not_connected',
      nextAction: googleBusinessConnected ? 'Карточка выбрана.' : googleSheetsConnected ? 'Выберите карточку компании.' : 'Сначала подключите Google-доступ.',
      primaryAction: { label: googleBusinessConnected ? 'Синхронизировать' : 'Настроить', type: 'drawer', target: 'google_business' },
      hasLogs: true,
      hasHelp: true,
    },
    {
      id: 'vk',
      name: 'VK',
      tag: 'Публикации',
      description: 'Посты в сообщество после подтверждения.',
      connectionType: 'oauth',
      status: vkOauthConnected
        ? socialConnectionStatus(vkReadiness, 'action_required')
        : vkAccount ? 'action_required' : 'not_connected',
      nextAction: vkOauthConnected && vkReadiness?.ready
        ? 'Сообщество готово к согласованным публикациям.'
        : vkAccount
          ? 'Обновите доступ через VK.'
          : 'Укажите ID сообщества и подтвердите доступ через VK.',
      primaryAction: { label: vkOauthConnected && vkReadiness?.ready ? 'Проверить' : vkAccount ? 'Обновить доступ' : 'Подключить', type: 'drawer', target: 'vk' },
      hasLogs: true,
      hasHelp: true,
    },
    {
      id: 'meta',
      name: 'Meta',
      tag: 'Публикации',
      description: 'Facebook и Instagram в контролируемом режиме.',
      connectionType: 'oauth',
      status: metaAccount ? 'connected' : socialConnectionStatus(metaReadiness, 'manual'),
      nextAction: metaAccount ? 'Аккаунт подключён.' : 'Выберите страницу и Instagram-актив в настройке.',
      primaryAction: { label: metaAccount ? 'Проверить' : 'Настроить', type: 'drawer', target: 'meta' },
      hasLogs: true,
      hasHelp: true,
    },
    {
      id: 'yandex_maps',
      name: 'Yandex Maps',
      tag: 'Публикации',
      description: 'Тексты для карт с ручным финальным шагом.',
      connectionType: 'manual',
      status: socialConnectionStatus(yandexReadiness, 'manual'),
      nextAction: 'Публикации вручную.',
      primaryAction: { label: 'Открыть детали', type: 'drawer', target: 'yandex_maps' },
      hasLogs: true,
      hasHelp: true,
    },
    {
      id: '2gis',
      name: '2GIS',
      tag: 'Публикации',
      description: 'Подготовка материалов для карточки 2GIS.',
      connectionType: 'manual',
      status: socialConnectionStatus(twoGisReadiness, 'manual'),
      nextAction: 'Публикации вручную.',
      primaryAction: { label: 'Открыть детали', type: 'drawer', target: '2gis' },
      hasLogs: true,
      hasHelp: true,
    },
    {
      id: 'yclients',
      name: 'YCLIENTS',
      tag: 'CRM',
      description: 'Записи, услуги и оплаты для финансов.',
      connectionType: 'credentials',
      status: crmProviderStatus(yclientsProvider),
      nextAction: crmNextAction(yclientsProvider, 'YCLIENTS'),
      primaryAction: { label: yclientsProvider?.connection?.status === 'connected' ? 'Проверить' : 'Подключить', type: 'drawer', target: 'yclients' },
      hasLogs: true,
      hasHelp: true,
    },
    {
      id: 'altegio',
      name: 'Altegio',
      tag: 'CRM',
      description: 'Записи и платежи филиала Altegio.',
      connectionType: 'credentials',
      status: crmProviderStatus(altegioProvider),
      nextAction: crmNextAction(altegioProvider, 'Altegio'),
      primaryAction: { label: altegioProvider?.connection?.status === 'connected' ? 'Проверить' : 'Подключить', type: 'drawer', target: 'altegio' },
      hasLogs: true,
      hasHelp: true,
    },
    {
      id: 'maton',
      name: 'Maton.ai',
      tag: 'Автоматизация',
      description: 'API-ключ для внешних сервисов и агентов.',
      connectionType: 'api_key',
      status: matonAccount ? 'connected' : 'not_connected',
      nextAction: matonAccount ? 'Ключ сохранён.' : 'Добавьте API-ключ Maton.ai.',
      primaryAction: { label: matonAccount ? 'Проверить' : 'Подключить', type: 'drawer', target: 'maton' },
      hasLogs: true,
      hasHelp: true,
    },
  ];
};
