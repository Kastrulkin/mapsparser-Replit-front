export type HubStatus = 'ready' | 'attention' | 'not_configured' | 'manual' | 'error';

export type SettingsHubModuleKey =
  | 'telegram'
  | 'whatsapp'
  | 'google_sheets'
  | 'google'
  | 'vk'
  | 'meta'
  | 'crm'
  | 'maton';

export type SettingsHubAction = {
  label: string;
  type: 'link' | 'drawer' | 'button';
  target: string;
};

export type ModuleState = {
  key: SettingsHubModuleKey;
  status: HubStatus;
  displayStatus?: HubStatus | 'partially_configured';
  label: string;
  description: string;
  primaryAction: SettingsHubAction;
  secondaryAction?: {
    label: string;
    target: string;
  };
  meta?: {
    ownerBotConnected?: boolean;
    publicationTargetSet?: boolean;
    phoneAdded?: boolean;
    wabaConnected?: boolean;
    provider?: string | null;
    connected?: boolean;
  };
};

export type SettingsHubState = {
  summary: {
    communications: HubStatus;
    publications: HubStatus;
    crm: HubStatus;
  };
  nextStep: {
    module: SettingsHubModuleKey;
    title: string;
    actionLabel: string;
    href?: string;
    drawer?: string;
  } | null;
  modules: Record<SettingsHubModuleKey, ModuleState>;
};

export type SettingsHubBusiness = {
  whatsapp_phone?: string | null;
  telegram_chat_id?: string | null;
  waba_phone_id?: string | null;
  waba_access_token?: string | null;
};

export type SettingsHubExternalAccount = {
  source?: string | null;
  external_id?: string | null;
  display_name?: string | null;
  is_active?: boolean | number | null;
  connection_mode?: string | null;
};

export type SettingsHubSocialReadiness = {
  platform?: string | null;
  publish_mode?: string | null;
  ready?: boolean | null;
  status?: string | null;
};

export type SettingsHubCrmProvider = {
  provider?: string | null;
  label?: string | null;
  connection?: {
    status?: string | null;
    display_name?: string | null;
  } | null;
};

export type SettingsHubRawState = {
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

const socialStatus = (readiness: SettingsHubSocialReadiness | null, fallback: HubStatus) => {
  if (!readiness) return fallback;
  if (readiness.ready) return 'ready';
  if (readiness.publish_mode === 'api') return 'attention';
  if (readiness.status === 'error') return 'error';
  return 'manual';
};

const combineStatus = (statuses: HubStatus[]) => {
  if (statuses.includes('error')) return 'error';
  if (statuses.includes('attention')) return 'attention';
  if (statuses.includes('not_configured')) return 'not_configured';
  if (statuses.includes('manual')) return 'manual';
  return 'ready';
};

export const mapSettingsState = (rawState: SettingsHubRawState): SettingsHubState => {
  const business = rawState.business || {};
  const externalAccounts = rawState.externalAccounts || [];
  const socialReadiness = rawState.socialReadiness || [];
  const crmProviders = rawState.crmProviders || [];

  const ownerBotConnected = Boolean(rawState.telegramOwnerLinked);
  const publicationTargetSet = hasText(rawState.telegramPublishStatus?.telegram_chat_id) || hasText(business.telegram_chat_id);
  const telegramCanPublish = Boolean(rawState.telegramPublishStatus?.configured || rawState.telegramPublishStatus?.global_bot_configured);
  const telegramReady = ownerBotConnected && publicationTargetSet && telegramCanPublish;
  const telegramPartial = ownerBotConnected || publicationTargetSet || telegramCanPublish;

  const phoneAdded = hasText(business.whatsapp_phone);
  const wabaConnected = hasText(business.waba_phone_id) && hasText(business.waba_access_token);

  const googleAccount = findAccount(externalAccounts, ['google_business']);
  const vkAccount = findAccount(externalAccounts, ['vk', 'vk_group', 'vk_business']);
  const metaAccount = findAccount(externalAccounts, ['meta', 'instagram', 'facebook']);
  const matonAccount = findAccount(externalAccounts, ['maton']);
  const googleSheetsReady = Boolean(googleAccount);
  const googleReady = Boolean(googleAccount && hasText(googleAccount.external_id));
  const vkReady = Boolean(vkAccount);
  const matonReady = Boolean(matonAccount);

  const metaReadiness = findReadiness(socialReadiness, ['meta', 'instagram', 'facebook']);
  const vkReadiness = findReadiness(socialReadiness, ['vk']);
  const googleReadiness = findReadiness(socialReadiness, ['google_business']);
  const metaStatus = metaAccount ? 'ready' : socialStatus(metaReadiness, 'manual');
  const vkStatus = vkReady ? 'ready' : socialStatus(vkReadiness, 'attention');
  const googleStatus = googleReady ? 'ready' : socialStatus(googleReadiness, 'not_configured');

  const connectedCrm = crmProviders.find((provider) => provider.connection?.status === 'connected') || null;
  const crmConnected = Boolean(connectedCrm);
  const crmLabel = connectedCrm?.connection?.display_name || connectedCrm?.label || connectedCrm?.provider || null;

  const telegramStatus: HubStatus = telegramReady ? 'ready' : telegramPartial ? 'attention' : 'not_configured';
  const whatsappStatus: HubStatus = wabaConnected ? 'ready' : phoneAdded ? 'attention' : 'not_configured';
  const crmStatus: HubStatus = crmConnected ? 'ready' : 'not_configured';
  const matonStatus: HubStatus = matonReady ? 'ready' : 'not_configured';

  const modules: Record<SettingsHubModuleKey, ModuleState> = {
    telegram: {
      key: 'telegram',
      status: telegramStatus,
      displayStatus: telegramReady ? 'ready' : telegramPartial ? 'partially_configured' : 'not_configured',
      label: 'Telegram',
      description: 'Бот LocalOS для управления и отдельный канал/чат для постов.',
      primaryAction: {
        label: !ownerBotConnected ? 'Connect bot' : !publicationTargetSet ? 'Set publication target' : 'Check connection',
        type: 'drawer',
        target: 'telegram',
      },
      secondaryAction: { label: 'Advanced', target: '/dashboard/settings/publications?focus=telegram' },
      meta: { ownerBotConnected, publicationTargetSet },
    },
    whatsapp: {
      key: 'whatsapp',
      status: whatsappStatus,
      label: 'WhatsApp',
      description: 'Номер и отправка сообщений клиентам.',
      primaryAction: {
        label: phoneAdded ? 'Configure sending' : 'Connect number',
        type: 'drawer',
        target: 'whatsapp',
      },
      secondaryAction: { label: 'Advanced', target: '/dashboard/settings/integrations?focus=whatsapp' },
      meta: { phoneAdded, wabaConnected },
    },
    google_sheets: {
      key: 'google_sheets',
      status: googleSheetsReady ? 'ready' : 'not_configured',
      label: 'Google Таблицы',
      description: 'Доступ для агентов к строкам таблиц.',
      primaryAction: {
        label: googleSheetsReady ? 'Check connection' : 'Connect Google',
        type: 'drawer',
        target: 'google_sheets',
      },
      secondaryAction: { label: 'Open details', target: '/dashboard/settings/integrations?focus=google_sheets' },
      meta: { connected: googleSheetsReady },
    },
    google: {
      key: 'google',
      status: googleStatus,
      label: 'Google Business',
      description: 'Карточка, отзывы и публикации Google.',
      primaryAction: {
        label: googleReady ? 'Check connection' : 'Connect Google',
        type: 'drawer',
        target: 'google_business',
      },
      secondaryAction: { label: 'Open details', target: '/dashboard/settings/integrations?focus=google_business' },
      meta: { connected: googleReady },
    },
    vk: {
      key: 'vk',
      status: vkStatus,
      label: 'VK',
      description: 'Публикации в сообщество после проверки.',
      primaryAction: {
        label: vkReady ? 'Check connection' : 'Connect VK',
        type: 'drawer',
        target: 'vk',
      },
      secondaryAction: { label: 'Open details', target: '/dashboard/settings/integrations?focus=vk' },
      meta: { connected: vkReady },
    },
    meta: {
      key: 'meta',
      status: metaStatus,
      label: 'Meta',
      description: 'Instagram и Facebook в контролируемом режиме.',
      primaryAction: {
        label: metaStatus === 'ready' ? 'Check connection' : 'Configure Meta',
        type: 'drawer',
        target: 'meta',
      },
      secondaryAction: { label: 'Open details', target: '/dashboard/settings/integrations?focus=meta' },
      meta: { connected: metaStatus === 'ready' },
    },
    crm: {
      key: 'crm',
      status: crmStatus,
      label: 'CRM',
      description: crmLabel ? `${crmLabel} подключена к финансам.` : 'Записи и оплаты для финансовой модели.',
      primaryAction: {
        label: 'Connect CRM',
        type: 'drawer',
        target: 'crm',
      },
      secondaryAction: { label: 'Open details', target: '/dashboard/settings/integrations?focus=crm' },
      meta: { provider: crmLabel },
    },
    maton: {
      key: 'maton',
      status: matonStatus,
      label: 'Maton.ai',
      description: 'Единый ключ для сторонних сервисов.',
      primaryAction: {
        label: matonReady ? 'Check connection' : 'Connect Maton',
        type: 'drawer',
        target: 'maton',
      },
      secondaryAction: { label: 'Open details', target: '/dashboard/settings/integrations?focus=maton' },
      meta: { connected: matonReady },
    },
  };

  const nextStep: SettingsHubState['nextStep'] = !ownerBotConnected
    ? { module: 'telegram', title: 'Connect Telegram owner bot', actionLabel: 'Connect bot', drawer: 'telegram' }
    : !publicationTargetSet
      ? { module: 'telegram', title: 'Set Telegram publication target', actionLabel: 'Set publication target', drawer: 'telegram' }
      : !phoneAdded
        ? { module: 'whatsapp', title: 'Add WhatsApp number', actionLabel: 'Connect number', drawer: 'whatsapp' }
        : !googleSheetsReady
          ? { module: 'google_sheets', title: 'Connect Google Sheets', actionLabel: 'Connect Google', drawer: 'google_sheets' }
          : !googleReady
            ? { module: 'google', title: 'Connect Google Business', actionLabel: 'Connect Google', drawer: 'google_business' }
          : (!vkReady || metaStatus !== 'ready')
            ? { module: vkReady ? 'meta' : 'vk', title: vkReady ? 'Configure Meta' : 'Connect VK', actionLabel: vkReady ? 'Configure Meta' : 'Connect VK', drawer: vkReady ? 'meta' : 'vk' }
            : !crmConnected
              ? { module: 'crm', title: 'Connect CRM', actionLabel: 'Connect CRM', drawer: 'crm' }
              : null;

  return {
    summary: {
      communications: combineStatus([telegramStatus, whatsappStatus]),
      publications: combineStatus([publicationTargetSet ? 'ready' : 'attention', googleSheetsReady ? 'ready' : 'not_configured', googleStatus, vkStatus, metaStatus]),
      crm: combineStatus([crmStatus, matonStatus]),
    },
    nextStep,
    modules,
  };
};
