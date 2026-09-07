// Shared product copy for the public pricing page and account billing.
// Access checks and prices remain owned by the billing backend.
export const subscriptionPlanCopy = (language: string) => language === 'ru' ? {
  subtitle: 'Выберите задачи, с которыми LocalOS будет помогать вашему бизнесу',
  starter: {
    name: 'Карты',
    lead: 'Помогите клиентам найти и выбрать вас на картах',
    features: [
      'Аудит карточек и план улучшений',
      'Услуги, отзывы, фото и сравнение с конкурентами',
      'Черновики ответов на отзывы и новостей для карт',
      'Отраслевые новости в Telegram-радаре',
      'Статистика посещений и действий на вашем сайте',
    ],
  },
  professional: {
    name: 'Привлечение',
    lead: 'Находите клиентов через местных авторов и партнёров',
    features: [
      'Всё из тарифа «Карты»',
      'Каталоги инфлюенсеров и партнёров, фильтры и отбор',
      'Предложения о сотрудничестве и персональные сообщения',
      'Отправка через подключённые каналы после подтверждения',
      'Ответы, размещения и учёт результатов сотрудничества',
      'Проверка видимости бизнеса в AI-чатах',
    ],
  },
  concierge: {
    name: 'Управление',
    lead: 'Поручайте регулярные задачи ИИ и контролируйте результат',
    features: [
      'Всё из тарифа «Привлечение»',
      'Контент-план, черновики и публикации в подключённых соцсетях',
      'Финансовые показатели и работа со средним чеком',
      'ИИ-сотрудники для регулярных задач бизнеса',
      'Рабочие чаты и история выполнения задач',
    ],
  },
  approval: 'Управление через чат доступно на любом тарифе. Доступ к действиям зависит от подписки. Публикации и отправки — после вашего подтверждения.',
} : {
  subtitle: 'Choose the business tasks you want LocalOS to help with',
  starter: {
    name: 'Maps',
    lead: 'Help customers find and choose you on maps',
    features: [
      'Listing audits and an improvement plan',
      'Services, reviews, photos and competitor comparisons',
      'Draft review replies and news for map listings',
      'Industry news with Telegram Radar',
      'Website visits and visitor actions',
    ],
  },
  professional: {
    name: 'Acquisition',
    lead: 'Reach customers through local creators and partners',
    features: [
      'Everything in Maps',
      'Creator and partner catalogs, filters and shortlists',
      'Collaboration proposals and personalized messages',
      'Send through connected channels after approval',
      'Track replies, placements and collaboration results',
      'Check business visibility in AI chats',
    ],
  },
  concierge: {
    name: 'Management',
    lead: 'Delegate recurring tasks to AI and review the results',
    features: [
      'Everything in Acquisition',
      'Content plans, drafts and posts for connected social channels',
      'Financial metrics and average transaction value',
      'AI employees for recurring business tasks',
      'Work chats and task history',
    ],
  },
  approval: 'Chat control is available on every plan. Actions depend on your subscription. Posts and messages require your approval.',
};
