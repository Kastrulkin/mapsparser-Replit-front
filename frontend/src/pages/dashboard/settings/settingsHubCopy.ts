import { Language } from '@/i18n/LanguageContext';

import { HubStatus, SettingsHubModuleKey } from './settingsHubState';

type StatusLabelKey = HubStatus | 'partially_configured';

type ModuleCopy = {
  label: string;
  description: string;
};

export type SettingsHubCopy = {
  page: {
    eyebrow: string;
    title: string;
    description: string;
    openDetails: string;
    loading: string;
  };
  status: Record<StatusLabelKey, string>;
  summary: {
    communications: { label: string; hint: string };
    publications: { label: string; hint: string };
    crm: { label: string; hint: string };
  };
  nextStep: {
    readyTitle: string;
    readyDescription: string;
    openContentPlan: string;
    eyebrow: string;
    description: string;
    titles: Record<string, string>;
    actions: Record<string, string>;
  };
  modules: Record<SettingsHubModuleKey, ModuleCopy>;
  metaRows: {
    ownerBot: string;
    publicationTarget: string;
    connected: string;
    missing: string;
    set: string;
    number: string;
    added: string;
    sending: string;
    configured: string;
    notConfigured: string;
  };
  actions: Record<string, string>;
  secondaryLinks: {
    agents: string;
    network: string;
    diagnostics: string;
  };
  details: Record<string, { title: string; description: string }>;
  routes: {
    advancedEyebrow: string;
    settingsEyebrow: string;
    diagnosticsTitle: string;
    diagnosticsDescription: string;
    diagnosticsSectionTitle: string;
    diagnosticsSectionDescription: string;
    publicationsTitle: string;
    publicationsDescription: string;
    integrationsTitle: string;
    integrationsDescription: string;
    backToHub: string;
  };
};

const en: SettingsHubCopy = {
  page: {
    eyebrow: 'LocalOS',
    title: 'Settings readiness',
    description: 'See what is ready, what needs one step, and where to open detailed setup.',
    openDetails: 'Open details',
    loading: 'Refreshing setup state...',
  },
  status: {
    ready: 'Ready',
    attention: 'Needs attention',
    not_configured: 'Not configured',
    manual: 'Manual',
    error: 'Error',
    partially_configured: 'Partially configured',
  },
  summary: {
    communications: { label: 'Communications', hint: 'Owner updates and client messaging.' },
    publications: { label: 'Publications', hint: 'Channels for approved content.' },
    crm: { label: 'CRM & Data', hint: 'Finance inputs and service connectors.' },
  },
  nextStep: {
    readyTitle: 'Core setup is ready',
    readyDescription: 'You can review details or continue with content and automation workflows.',
    openContentPlan: 'Open content plan',
    eyebrow: 'Recommended next step',
    description: 'Finish this first so the rest of setup has a clear path forward.',
    titles: {
      'Set Telegram publication target': 'Choose a Telegram channel for posts',
      'Connect Telegram owner bot': 'Connect the LocalOS bot in Telegram',
      'Add WhatsApp number': 'Add WhatsApp number',
      'Connect Google Sheets': 'Connect Google Sheets',
      'Connect Google Business': 'Connect Google Business',
      'Configure Meta': 'Configure Meta',
      'Connect VK': 'Connect VK',
      'Connect CRM': 'Connect CRM',
    },
    actions: {
      'Set publication target': 'Choose post channel',
      'Connect bot': 'Connect LocalOS bot',
      'Connect number': 'Connect number',
      'Connect Google': 'Connect Google',
      'Configure Meta': 'Configure Meta',
      'Connect VK': 'Connect VK',
      'Connect CRM': 'Connect CRM',
    },
  },
  modules: {
    telegram: { label: 'Telegram', description: 'LocalOS bot for account control plus a separate channel or chat for posts.' },
    whatsapp: { label: 'WhatsApp', description: 'Business number and client message sending.' },
    google_sheets: { label: 'Google Sheets', description: 'Agent access to table rows.' },
    google: { label: 'Google Business', description: 'Google profile, reviews, and posts.' },
    vk: { label: 'VK', description: 'Community posts after review.' },
    meta: { label: 'Meta', description: 'Instagram and Facebook in a controlled mode.' },
    crm: { label: 'CRM', description: 'Records and payments for the finance model.' },
    maton: { label: 'Maton.ai', description: 'Shared key for external services.' },
  },
  metaRows: {
    ownerBot: 'LocalOS owner bot',
    publicationTarget: 'Post channel/chat',
    connected: 'connected',
    missing: 'missing',
    set: 'set',
    number: 'Number',
    added: 'added',
    sending: 'Sending',
    configured: 'configured',
    notConfigured: 'not configured',
  },
  actions: {
    'Connect bot': 'Connect LocalOS bot',
    'Set publication target': 'Choose post channel',
    'Check connection': 'Check connection',
    Advanced: 'Advanced',
    'Configure sending': 'Configure sending',
    'Connect number': 'Connect number',
    'Connect Google': 'Connect Google',
    'Open details': 'Open details',
    'Connect VK': 'Connect VK',
    'Configure Meta': 'Configure Meta',
    'Connect CRM': 'Connect CRM',
    'Connect Maton': 'Connect Maton',
  },
  secondaryLinks: {
    agents: 'Agents',
    network: 'Network',
    diagnostics: 'Diagnostics',
  },
  details: {
    telegram: {
      title: 'Telegram setup',
      description: 'Connect the LocalOS bot for account control, updates, work results, and Telegram-side actions. Separately choose the channel or chat where approved posts should be sent.',
    },
    whatsapp: {
      title: 'WhatsApp setup',
      description: 'Add the business number and configure sending credentials when they are available.',
    },
    crm: {
      title: 'CRM setup',
      description: 'Choose a CRM provider, preview imported data, then confirm when the preview is right.',
    },
    publications: {
      title: 'Publication channels',
      description: 'Review channel setup and keep external publishing behind preview and approval.',
    },
    integrations: {
      title: 'Connections',
      description: 'Sign in to Google, VK, or Meta, or add the Maton API key.',
    },
  },
  routes: {
    advancedEyebrow: 'Advanced',
    settingsEyebrow: 'Settings',
    diagnosticsTitle: 'Settings diagnostics',
    diagnosticsDescription: 'Technical channel checks, delivery health, and support exports live here instead of the main setup hub.',
    diagnosticsSectionTitle: 'Diagnostics and support tools',
    diagnosticsSectionDescription: 'Use this when a setup looks wrong or a support export is needed.',
    publicationsTitle: 'Publication channels',
    publicationsDescription: 'Connect channels that can receive approved content from LocalOS.',
    integrationsTitle: 'Connections',
    integrationsDescription: 'Sign in to Google, VK, or Meta, or add the Maton API key.',
    backToHub: 'Back to hub',
  },
};

const ru: SettingsHubCopy = {
  page: {
    eyebrow: 'LocalOS',
    title: 'Готовность настроек',
    description: 'Посмотрите, что уже готово, какой один шаг важнее всего и где открыть подробную настройку.',
    openDetails: 'Открыть детали',
    loading: 'Обновляем состояние настроек...',
  },
  status: {
    ready: 'Готово',
    attention: 'Нужно внимание',
    not_configured: 'Не настроено',
    manual: 'Вручную',
    error: 'Ошибка',
    partially_configured: 'Частично настроено',
  },
  summary: {
    communications: { label: 'Связь', hint: 'Уведомления владельцу и сообщения клиентам.' },
    publications: { label: 'Публикации', hint: 'Каналы для согласованного контента.' },
    crm: { label: 'CRM и данные', hint: 'Финансовые данные и сервисные подключения.' },
  },
  nextStep: {
    readyTitle: 'Базовая настройка готова',
    readyDescription: 'Можно проверить детали или перейти к контенту и автоматизации.',
    openContentPlan: 'Открыть контент-план',
    eyebrow: 'Рекомендуемый следующий шаг',
    description: 'Сделайте это первым, чтобы остальные настройки шли по понятному маршруту.',
    titles: {
      'Set Telegram publication target': 'Выберите Telegram-канал для постов',
      'Connect Telegram owner bot': 'Привяжите бот LocalOS в Telegram',
      'Add WhatsApp number': 'Добавьте номер WhatsApp',
      'Connect Google Sheets': 'Подключите Google Таблицы',
      'Connect Google Business': 'Подключите Google Business',
      'Configure Meta': 'Настройте Meta',
      'Connect VK': 'Подключите VK',
      'Connect CRM': 'Подключите CRM',
    },
    actions: {
      'Set publication target': 'Выбрать канал для постов',
      'Connect bot': 'Привязать бот LocalOS',
      'Connect number': 'Подключить номер',
      'Connect Google': 'Подключить Google',
      'Configure Meta': 'Настроить Meta',
      'Connect VK': 'Подключить VK',
      'Connect CRM': 'Подключить CRM',
    },
  },
  modules: {
    telegram: { label: 'Telegram', description: 'Бот LocalOS для управления аккаунтом и отдельный канал/чат для постов.' },
    whatsapp: { label: 'WhatsApp', description: 'Номер бизнеса и отправка сообщений клиентам.' },
    google_sheets: { label: 'Google Таблицы', description: 'Доступ агентов к строкам таблиц.' },
    google: { label: 'Google Business', description: 'Карточка, отзывы и публикации Google.' },
    vk: { label: 'VK', description: 'Публикации в сообщество после проверки.' },
    meta: { label: 'Meta', description: 'Instagram и Facebook в контролируемом режиме.' },
    crm: { label: 'CRM', description: 'Записи и оплаты для финансовой модели.' },
    maton: { label: 'Maton.ai', description: 'Единый ключ для сторонних сервисов.' },
  },
  metaRows: {
    ownerBot: 'Бот LocalOS в Telegram',
    publicationTarget: 'Канал/чат для постов',
    connected: 'подключен',
    missing: 'не указан',
    set: 'выбран',
    number: 'Номер',
    added: 'добавлен',
    sending: 'Отправка',
    configured: 'настроена',
    notConfigured: 'не настроена',
  },
  actions: {
    'Connect bot': 'Привязать бот LocalOS',
    'Set publication target': 'Выбрать канал для постов',
    'Check connection': 'Проверить подключение',
    Advanced: 'Расширенные настройки',
    'Configure sending': 'Настроить отправку',
    'Connect number': 'Подключить номер',
    'Connect Google': 'Подключить Google',
    'Open details': 'Открыть детали',
    'Connect VK': 'Подключить VK',
    'Configure Meta': 'Настроить Meta',
    'Connect CRM': 'Подключить CRM',
    'Connect Maton': 'Подключить Maton',
  },
  secondaryLinks: {
    agents: 'Сотрудники ИИ',
    network: 'Сеть локаций',
    diagnostics: 'Диагностика',
  },
  details: {
    telegram: {
      title: 'Настройка Telegram',
      description: 'Привяжите бот LocalOS для управления аккаунтом, уведомлений, результатов работы и действий из Telegram. Отдельно выберите канал или чат, куда LocalOS будет отправлять согласованные посты.',
    },
    whatsapp: {
      title: 'Настройка WhatsApp',
      description: 'Добавьте номер бизнеса и настройте отправку, когда доступы готовы.',
    },
    crm: {
      title: 'Настройка CRM',
      description: 'Выберите CRM, проверьте импортированные данные и подтвердите подключение.',
    },
    publications: {
      title: 'Каналы публикаций',
      description: 'Проверьте каналы и оставьте публикации за предпросмотром и подтверждением.',
    },
    integrations: {
      title: 'Подключения',
      description: 'Войдите в Google, VK или Meta либо добавьте API-ключ Maton.',
    },
  },
  routes: {
    advancedEyebrow: 'Дополнительно',
    settingsEyebrow: 'Настройки',
    diagnosticsTitle: 'Диагностика настроек',
    diagnosticsDescription: 'Проверки каналов, состояния доставки и материалы для поддержки находятся здесь, а не на главном экране.',
    diagnosticsSectionTitle: 'Диагностика и поддержка',
    diagnosticsSectionDescription: 'Используйте этот раздел, если настройка выглядит неправильно или нужен экспорт для поддержки.',
    publicationsTitle: 'Каналы публикаций',
    publicationsDescription: 'Подключите каналы, куда LocalOS сможет отправлять согласованный контент.',
    integrationsTitle: 'Подключения',
    integrationsDescription: 'Войдите в Google, VK или Meta либо добавьте API-ключ Maton.',
    backToHub: 'Назад к готовности',
  },
};

export const getSettingsHubCopy = (language: Language): SettingsHubCopy => {
  if (language === 'ru') return ru;
  return en;
};
