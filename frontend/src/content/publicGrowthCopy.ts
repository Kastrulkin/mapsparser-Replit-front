export type PublicLeadJourneyCopy = {
  seoTitle: string;
  seoDescription: string;
  loading: string;
  unavailableTitle: string;
  unavailableBack: string;
  allDirections: string;
  home: string;
  eyebrow: string;
  title: string;
  intro: string;
  customers: string;
  customersIntro: string;
  work: string;
  moreOptions: string;
  secondary: string;
  defaultChoice: string;
  resultPreview: string;
  howItWorks: string;
  processRoles: string;
  businessRoleTitle: string;
  localosRoleTitle: string;
  publicExample: string;
  continueTitle: string;
  continueText: string;
  continueButton: string;
  recommendedMechanic: string;
  openDirection: string;
  openDirectionText: string;
  approvalNote: string;
  otherTitle: string;
  otherText: string;
  prepareError: string;
  genericSteps: Array<{ title: string; description: string }>;
  businessRole: string;
  localosRole: string;
  prepareLabel: string;
  directionResultTitle: string;
  directionResultPreview: string[];
  lockedResult: string;
};

export const publicGrowthCopy: PublicLeadJourneyCopy = {
  seoTitle: 'Шесть направлений LocalOS для бизнеса',
  seoDescription: 'Выберите одно из шести направлений: авторы, бизнесы рядом, карты, контент, средний чек или автоматизация.',
  loading: 'Загружаем персональные возможности…', unavailableTitle: 'Персональная ссылка недоступна', unavailableBack: 'Вернуться на LocalOS',
  allDirections: 'Все направления', home: 'На главную', eyebrow: '6 направлений', title: 'Выберите направление',
  intro: 'Откройте направление, чтобы увидеть, как оно работает и с чего начать.', customers: 'Клиенты', customersIntro: 'Авторы, бизнесы рядом и карты.', work: 'Контент и автоматизация',
  moreOptions: 'Ещё вариантов:', secondary: 'Доступно для исследования после регистрации', defaultChoice: 'Посмотреть возможность', resultPreview: 'Это превью состава результата, а не уже выполненная работа.',
  howItWorks: 'Как это работает', processRoles: 'Роли в процессе', businessRoleTitle: 'Что делает бизнес', localosRoleTitle: 'Что делает LocalOS', publicExample: 'Посмотреть публичный пример',
  continueTitle: 'Продолжить с этим направлением', continueText: 'После регистрации откроется нужный раздел. Сначала вы заполните данные бизнеса и увидите кандидатов или проверку — без автоматической отправки и публикации.', continueButton: 'Продолжить в LocalOS',
  recommendedMechanic: 'Рекомендуемая механика', openDirection: 'Открыть выбранное направление', openDirectionText: 'Создайте бизнес-профиль. Выбор сохранится, а кабинет откроет нужный раздел.',
  approvalNote: 'Внешние отправки и изменения остаются под ручным подтверждением.', otherTitle: 'Что ещё можно улучшить', otherText: 'Другие области можно посмотреть позже — выбранное действие сохранится.', prepareError: 'Не удалось подготовить результат',
  genericSteps: [], businessRole: '', localosRole: '', prepareLabel: '', directionResultTitle: '', directionResultPreview: [], lockedResult: '',
};
