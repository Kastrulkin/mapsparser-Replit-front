export type PromotionKey = 'home' | 'maps' | 'bloggers' | 'partners';
export type PromotionSection = { title: string; text: string; items?: string[] };
export type PromotionPage = {
  key: PromotionKey; path: string; label: string; eyebrow: string; title: string;
  description: string; seoTitle: string; reason: string; sections: PromotionSection[];
  questions: { question: string; answer: string }[];
};
export const promotionKeys: PromotionKey[] = ['home', 'maps', 'bloggers', 'partners'];
export const promotionContent = (english = false): Record<PromotionKey, PromotionPage> => {
  const l = (ru: string, en: string) => english ? en : ru;
  const commonQuestions = [
    { question: l('Нужно ли разбираться в системе?', 'Do I need to learn the software?'), answer: l('Нет. Мы настроим LocalOS и будем вести работу. От вас нужны доступы, сведения о бизнесе и согласование материалов. Посмотреть систему можно в демо.', 'No. Our team handles setup and the work. You provide the necessary access, confirm business details and approve decisions. The dashboard and demo remain available.') },
    { question: l('Что произойдёт после заявки?', 'What happens after my request?'), answer: l('Менеджер свяжется с вами, уточнит задачу и предложит состав работ. После согласования стоимости поможем предоставить доступы и начнём работу. За отправку заявки платить не нужно.', 'A manager will contact you to discuss your task, scope and cost. Once agreed, we help you grant access and start the agreed work. A request does not activate a service or charge you.') },
    { question: l('Вы публикуете и отправляете всё сами?', 'Do you publish and send on our behalf?'), answer: l('Да, подготовку и размещение берём на себя. Тексты, отправку предложений и изменения в карточках предварительно согласуем с вами.', 'Our team prepares and carries out the work. Content, external messages and changes on behalf of your business require the appropriate approvals. We agree the working process during setup.') },
    { question: l('Сколько это стоит?', 'How much does it cost?'), answer: l('Тарифы подписки указаны на странице «Цены». Стоимость работы команды согласуем до начала. Размещения у блогеров и расходы на акции обсуждаются отдельно.', 'The pricing page lists LocalOS subscription plans. Team service scope and additional costs are agreed before work starts. Creator fees and joint promotion costs are not automatically included in the subscription.') },
  ];
  return {
    home: {
      key: 'home', path: '/', label: 'LocalOS', eyebrow: l('Продвижение локального бизнеса', 'Marketing for local businesses'),
      title: l("Привлекайте клиентов рядом, даже когда некогда заниматься продвижением", "Attract customers nearby, even when you have no time for marketing"),
      seoTitle: l('Продвижение локального бизнеса на Картах, у блогеров и партнёров — LocalOS', 'Local business marketing: maps, creators and partnerships — LocalOS'),
      description: l("Карты, локальные блогеры и партнёры по соседству — три способа познакомить с вашим бизнесом людей, которым удобно к вам прийти. LocalOS помогает готовить материалы и предложения для каждого из них", "Maps, local creators and neighbouring businesses are three ways to introduce your business to people who can conveniently visit. LocalOS helps prepare materials and proposals for each channel."),
      reason: l('Выберите, откуда хотите получать обращения: с Карт, от местных блогеров или по рекомендациям соседних компаний.', 'Three ways to reach people who can conveniently visit your business.'),
      sections: [
        { title: l('Карты', 'Maps'), text: l('Когда вашу услугу уже ищут рядом', 'When people are already looking nearby'), items: [l('Понятная карточка и услуги', 'A clear listing and services'), l('Отзывы и регулярные обновления', 'Reviews and regular updates')] },
        { title: l('Локальные блогеры', 'Local creators'), text: l('Когда о вас могут рассказать местные авторы', 'When local creators can tell your story'), items: [l('Подбор авторов для вашего бизнеса', 'A shortlist with selection reasons'), l('Предложение о сотрудничестве', 'A collaboration proposal')] },
        { title: l('Локальные партнёры', 'Nearby partners'), text: l('Когда вас могут рекомендовать соседи', 'When neighbouring businesses can recommend you'), items: [l('Бизнесы с подходящими услугами', 'Complementary nearby businesses'), l('Взаимные рекомендации и акции', 'Mutual value and a joint promotion')] },
      ], questions: commonQuestions,
    },
    maps: {
      key: 'maps', path: '/prodvizhenie-na-yandex-kartah', label: l('Карты', 'Maps'), eyebrow: l('Продвижение бизнеса на Яндекс Картах', 'Local business map marketing'),
      title: l("Увеличивайте поток клиентов с Карт — без ручной работы", "Increase customer traffic from maps — without manual work"),
      seoTitle: l('Продвижение на Яндекс Картах с сопровождением команды — LocalOS', 'Map marketing with team support — LocalOS'),
      description: l("LocalOS готовит оформление карточки, SEO-описания услуг, публикации и ответы на отзывы — чтобы повышать видимость на картах и привлекать клиентов рядом", "LocalOS prepares your business listing, SEO service descriptions, posts and review replies to improve map visibility and attract customers nearby."),
      reason: l('Клиент ищет услугу, сравнивает компании и решает, куда обратиться. Поможем подготовить карточку к каждому из этих шагов.', 'Yandex Maps, Google Maps and 2GIS — scope and available actions are agreed for each platform.'),
      sections: [
        { title: l('Ищет услугу рядом', 'Searches for a nearby service'), text: l('Укажем услуги и категории, по которым клиенты ищут ваш бизнес.', 'We help describe services so the listing answers the customer’s need.') },
        { title: l('Сравнивает варианты', 'Compares options'), text: l('Проверим фотографии, цены и отзывы: по ним клиент выбирает компанию.', 'We work on presentation, photos, reviews and your business offer.') },
        { title: l('Выбирает и обращается', 'Chooses and gets in touch'), text: l('Проверим контакты, часы работы и способы записи.', 'We check that services, terms and ways to contact you are clear.') },
      ], questions: [
        { question: l('Подойдёт, если карточка уже есть?', 'Does this work with an existing listing?'), answer: l('Да. Проверим вашу карточку и предложим, что исправить. Если карточки ещё нет, обсудим создание и подтверждение.', 'Yes. We start with your current listing, services, reviews and access. If you do not have a listing, we discuss creation and verification.') },
        { question: l('Что означает SEO для Карт?', 'What does SEO for maps mean?'), answer: l('Понятные категории и описания услуг, актуальные сведения и полезное содержание карточки. Позиции зависят и от других факторов, поэтому конкретное место в выдаче и число клиентов не гарантируем.', 'Clear categories and service descriptions, current business details and useful listing content. Rankings also depend on other factors, so we do not guarantee a position or number of customers.') },
      ],
    },
    bloggers: {
      key: 'bloggers', path: '/lokalnye-blogery', label: l('Локальные блогеры', 'Local creators'), eyebrow: l('Реклама у локальных блогеров', 'Local creator marketing'),
      title: l("Привлекайте внимание к бизнесу через локальных блогеров", "Attract attention to your business through local creators"),
      seoTitle: l('Локальные блогеры для рекламы бизнеса — подбор и сопровождение | LocalOS', 'Local creators for your business — selection and support | LocalOS'),
      description: l("LocalOS помогает найти местных авторов и подготовить предложение о сотрудничестве, чтобы познакомить с вашей точкой людей, которым удобно стать вашими клиентами", "LocalOS helps find local creators and prepare a collaboration proposal to introduce your location to people who can conveniently become your customers."),
      reason: l('Проверяем, о чём пишет автор, где живут его читатели и подойдёт ли им ваша услуга.', 'Follower count is not enough: location and relevance to your business matter.'),
      sections: [
        { title: l('Подходящий автор', 'A relevant creator'), text: l('Изучаем публикации и сведения об аудитории. При необходимости запрашиваем статистику у автора.', 'We review topics, location signals and available audience information, noting what still needs verification.') },
        { title: l('Понятный формат', 'A clear format'), text: l('Предлагаем обзор, знакомство с услугой или акцию для подписчиков.', 'A service introduction, review or subscriber offer matched to your business task.') },
        { title: l('Подготовка размещения', 'Placement preparation'), text: l('Готовим обращение к автору. До размещения согласуем цену, содержание и дату публикации.', 'We prepare a personalised proposal. Creator participation, fees and publication are agreed separately.') },
      ], questions: [
        { question: l('Как выбираете блогеров?', 'How do you choose creators?'), answer: l('Смотрим, о чём пишет автор, насколько его аудитория близка к вашей точке и подходит ли ей ваша услуга. При необходимости запрашиваем статистику аудитории.', 'We check the creator’s topics, how close their audience is to your location, and whether your service is relevant to them. We ask for audience statistics when needed.') },
        { question: l('Какие форматы рекламы можно предложить?', 'Which placement formats can you suggest?'), answer: l('Обзор, знакомство с услугой или предложение для подписчиков. Подбираем формат под задачу бизнеса и то, как автор обычно общается с аудиторией.', 'A review, a service introduction or an offer for followers. We match the format to your goal and the creator’s usual style.') },
        { question: l('Как понять, что аудитория местная?', 'How do you verify a local audience?'), answer: l('Оцениваем географию контента и доступные подтверждения. До размещения запрашиваем у автора статистику аудитории, если она нужна для решения. Место жительства автора само по себе не подтверждает географию его подписчиков.', 'We assess content geography and available evidence. Audience statistics may need to be requested before a placement. A local creator does not mean all followers live nearby.') },
        { question: l('Как учитывать обращения?', 'How can enquiries be measured?'), answer: l('До размещения выбираем способ учёта: отдельная ссылка, кодовое слово или вопрос при записи. Согласуем его с вами и автором; точность зависит от выбранного способа.', 'Before placement, we agree a tracking method: a dedicated link, code word or booking question. Accuracy depends on the method used.') },
      ],
    },
    partners: {
      key: 'partners', path: '/lokalnye-partnery', label: l('Локальные партнёры', 'Nearby partners'), eyebrow: l('Локальные партнёры для взаимопиара и совместных акций', 'Local partners for cross-promotion and joint offers'),
      title: l("Привлекайте клиентов через рекомендации бизнесов по соседству", "Attract customers through recommendations from nearby businesses"),
      seoTitle: l('Локальные партнёры для взаимопиара и совместных акций — LocalOS', 'Nearby business partners for cross-promotion — LocalOS'),
      description: l("Найдите локальных партнёров рядом с вашей точкой на Яндекс Картах и предложите взаимные рекомендации или общую акцию. LocalOS помогает подобрать бизнес и подготовить предложение с выгодой для обеих сторон", "Find local partners near your location on Yandex Maps and propose mutual recommendations or a joint offer. LocalOS helps select businesses and prepare a proposal that benefits both sides."),
      reason: l('Ищем компании, чьи услуги дополняют ваши: например, кофейню рядом со студией тренировок.', 'Proximity opens the conversation. Compatibility and mutual value make collaboration worthwhile.'),
      sections: [
        { title: l('Подходящие соседи', 'Relevant neighbours'), text: l('Выбираем компании поблизости, которым могут быть интересны ваши клиенты.', 'We look for nearby businesses with complementary services and a clear reason to recommend each other.') },
        { title: l('Выгода обеим сторонам', 'Value for both sides'), text: l('Предлагаем, что каждый партнёр даст клиентам: скидку, бонус или рекомендацию.', 'We define what each participant contributes and what the customer receives.') },
        { title: l('Совместная акция', 'A joint offer'), text: l('Пишем партнёру, что предлагаем и на каких условиях. Запуск и расходы согласуем с обеими сторонами.', 'We prepare the promotion mechanics and partner proposal. Terms, costs and launch require agreement.') },
      ], questions: [
        { question: l('Как учитывать отклики на совместную акцию?', 'How can we track responses to a joint offer?'), answer: l('Выберите с партнёром способ учёта до запуска: отдельную ссылку, кодовое слово или вопрос при записи. Считайте обращения и записи по акции отдельно.', 'Before launch, agree how to track responses with your partner: a dedicated link, a code word or a question at booking. Count enquiries and bookings from the offer separately.') },
        { question: l('Партнёрами могут быть только соседи?', 'Do partners have to be next door?'), answer: l('Нет. Главное, чтобы клиентам были нужны услуги обеих компаний. Обсудим подходящие категории и расстояние от вашей точки.', 'Proximity matters, but is not enough. We consider your task, complementary services and customer convenience. We agree a suitable search radius.') },
        { question: l('Что, если бизнес откажется?', 'What if a business declines?'), answer: l('Предложим другого партнёра или пересмотрим условия. Сотрудничество начнётся, когда обе стороны договорятся.', 'Partner acceptance is not guaranteed. We record the response and discuss another candidate or an adjusted proposal. A declined proposal is not a launched partnership.') },
      ],
    },
  };
};

// No verified count is available in the supplied materials. Enable only with dated evidence.
export const promotionTrust: { text: string; evidence: string } | null = null;

export const promotionExamples = (english = false) => english ? [
  { title: 'Listing presentation', text: 'Massage studio · Massage category · Opening hours, entrance photo and booking contacts.' },
  { title: 'SEO service description', text: 'Back massage in the studio. Ask the receptionist about session length, price and availability when booking.' },
  { title: 'A business post', text: 'Looking for a back massage this week? Message us through the listing and we will help you find a time.' },
  { title: 'A review reply', text: 'Thank you for your review! We’re glad you enjoyed your visit. See you next time.' },
] : [
  { title: 'Оформление карточки', text: 'Студия массажа · Категория «Массаж» · Часы работы, фото входа и контакты для записи.' },
  { title: 'SEO-описание услуги', text: 'Массаж спины в студии. При записи администратор подскажет продолжительность сеанса, стоимость и свободное время.' },
  { title: 'Публикация о бизнесе', text: 'Хотите записаться на массаж спины на этой неделе? Напишите нам через карточку, подберём удобное время.' },
  { title: 'Ответ на отзыв', text: 'Спасибо за отзыв! Рады, что вам понравилось. До следующей встречи.' },
];

// Preserve only marketing context and locale in links, never arbitrary URL fields.
export const promotionLinkSearch = (search: string) => {
  const source = new URLSearchParams(search);
  const target = new URLSearchParams();
  for (const key of ['lang', 'utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term']) {
    const value = source.get(key);
    if (value) target.set(key, value.slice(0, 160));
  }
  const result = target.toString();
  return result ? `?${result}` : '';
};

export const promotionAttribution = (search: string) => {
  const params = new URLSearchParams(search);
  const result: Record<string, string> = {};
  for (const key of ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term']) {
    const value = params.get(key);
    if (value) result[key] = value.slice(0, 160);
  }
  return result;
};


export const readPromotionDirection = (search: string): PromotionKey | undefined => {
  const value = new URLSearchParams(search).get('direction');
  return promotionKeys.find((key) => key === value);
};

export const promotionContextSearch = (search: string, direction?: PromotionKey) => {
  const params = new URLSearchParams(promotionLinkSearch(search));
  const selected = direction || readPromotionDirection(search);
  if (selected) params.set('direction', selected);
  const result = params.toString();
  return result ? `?${result}` : '';
};

const commonWorkSteps = (english: boolean) => english ? [
  { title: 'Tell us your task', text: 'A manager will discuss your business, the work and the price.' },
  { title: 'Provide access', text: 'We help connect your accounts, prepare materials and agree them with you.' },
  { title: 'Receive reports', text: 'See completed work and enquiries, and discuss what to do next.' },
] : [
  { title: 'Оставьте заявку', text: 'Менеджер уточнит, что нужно продвигать, предложит состав работ и назовёт стоимость.' },
  { title: 'Предоставьте доступы', text: 'Поможем подключить аккаунты. Подготовим материалы и согласуем их с вами.' },
  { title: 'Получайте отчёты', text: 'Покажем, что изменили и какие отклики получили. Обсудим, что делать дальше.' },
];

export const promotionWorkSteps = (english = false, direction: PromotionKey = 'home') => {
  const steps = commonWorkSteps(english);
  if (direction === 'home') return steps;

  const l = (ru: string, en: string) => english ? en : ru;
  const startingWork = {
    maps: {
      title: l('Подключим карточку', 'Connect your listing'),
      text: l('Поможем предоставить доступ, проверим карточку и подготовим первые улучшения.', 'We help you grant access, review your listing and prepare the first improvements.'),
    },
    bloggers: {
      title: l('Начнём подбор авторов', 'Start finding creators'),
      text: l('Уточним район и аудиторию, подберём первых авторов и предложим формат размещения.', 'We confirm the area and audience, shortlist the first creators and suggest a placement format.'),
    },
    partners: {
      title: l('Найдём подходящих соседей', 'Find suitable nearby businesses'),
      text: l('Определим, какие компании подходят, и подготовим предложение о сотрудничестве.', 'We identify suitable businesses and prepare a collaboration proposal.'),
    },
  };
  return [steps[0], startingWork[direction], steps[2]];
};

export const promotionFaqGroups = (english = false) => {
  const pages = promotionContent(english);
  const common = pages.home.questions;
  const l = (ru: string, en: string) => english ? en : ru;
  return [
    { id: 'start', title: l('Начало работы', 'Getting started'), questions: common.slice(0, 2) },
    { id: 'access', title: l('Доступы и согласования', 'Access and approvals'), questions: [
      { question: l('Какие доступы понадобятся?', 'What access will you need?'), answer: l('Это зависит от выбранного направления. Менеджер объяснит, какие аккаунты подключить и как предоставить доступ сотруднику. Доступы не нужны для отправки заявки.', 'It depends on the direction. A manager will explain which accounts to connect and how to grant staff access. No account access is needed to send a request.') },
      common[2],
    ] },
    { id: 'pricing', title: l('Стоимость', 'Pricing'), questions: [common[3]] },
    { id: 'maps', title: pages.maps.label, questions: pages.maps.questions },
    { id: 'bloggers', title: pages.bloggers.label, questions: pages.bloggers.questions },
    { id: 'partners', title: pages.partners.label, questions: pages.partners.questions },
  ];
};
