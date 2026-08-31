import { browserBearerToken } from '@/lib/browserSessionFetch';
import { newAuth } from '@/lib/auth_new';

export type LeadJourneyKey = 'influencers' | 'partnerships' | 'maps' | 'content' | 'automation';

export type LeadJourneyDirection = {
  key: LeadJourneyKey;
  eyebrow: string;
  title: string;
  preview: string;
  detailTitle: string;
  detail: string;
  steps: Array<{ title: string; description: string }>;
  detailSections?: Array<{ title: string; items: string[] }>;
  continueTitle?: string;
  continueText?: string;
  businessRole: string;
  localosRole: string;
  prepareLabel: string;
  resultTitle: string;
  resultPreview: string[];
  lockedResult: string;
  dashboardRoute: string;
};

export const LEAD_JOURNEY_STORAGE_KEY = 'localos_lead_journey_intent';
export const LEAD_JOURNEY_TOKEN_STORAGE_KEY = 'localos_lead_journey_token';

export type JourneyOpportunity = {
  flow_type: 'influencer' | 'partnership' | 'maps' | 'content' | 'automation';
  entity_type: string;
  entity_id?: string;
  title: string;
  summary: string;
  reason: string;
  mechanic?: string;
  message_excerpt?: string;
  public_url?: string;
  count?: number;
  metrics?: Record<string, string | number | boolean>;
  tasks?: Array<{ title: string; reason?: string }>;
};

export type PublicLeadJourney = {
  id: string;
  status: string;
  source: string;
  business?: { name?: string; city?: string; address?: string };
  opportunities: JourneyOpportunity[];
  selected_flow?: string | null;
  expires_at?: string;
};

export type JourneyAction = {
  id: string;
  journey_id?: string | null;
  business_id?: string | null;
  flow_type: 'influencer' | 'partnership' | 'maps' | 'content' | 'automation' | 'upgrade';
  entity_type: string;
  entity_id?: string | null;
  action_type: string;
  status: 'ready' | 'in_progress' | 'waiting' | 'blocked' | 'completed' | 'superseded' | 'cancelled';
  priority: number;
  due_at?: string | null;
  title: string;
  description: string;
  cta_label: string;
  cta_target?: { screen?: string; action_id?: string };
  payload?: Record<string, unknown>;
  allowed_commands: string[];
  version: number;
};

const readJson = async (response: Response) => {
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'Не удалось продолжить действие');
  return data;
};

export const loadPublicLeadJourney = async (token: string): Promise<PublicLeadJourney> => {
  const response = await fetch(`/api/journeys/public/${encodeURIComponent(token)}`);
  const data = await readJson(response);
  return data.journey;
};

export const trackPublicJourneyEvent = async (token: string, eventName: string, opportunity?: JourneyOpportunity) => {
  try {
    await fetch(`/api/journeys/public/${encodeURIComponent(token)}/events`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      keepalive: true,
      body: JSON.stringify({
        event_name: eventName,
        surface: 'web',
        flow_type: opportunity?.flow_type,
        entity_type: opportunity?.entity_type,
        entity_id: opportunity?.entity_id,
      }),
    });
  } catch {
    // Telemetry never blocks the public journey.
  }
};

export const preparePublicOpportunity = async (token: string, opportunity: JourneyOpportunity) => {
  const entityId = opportunity.entity_id || '_';
  const response = await fetch(`/api/journeys/public/${encodeURIComponent(token)}/opportunities/${opportunity.flow_type}/${encodeURIComponent(entityId)}/preview`, { method: 'POST' });
  const data = await readJson(response);
  return data.preview;
};

export const loadJourneyActions = async (businessId: string): Promise<JourneyAction[]> => {
  const response = await fetch(`/api/journey-actions?business_id=${encodeURIComponent(businessId)}`, {
    headers: { Authorization: `Bearer ${browserBearerToken() || ''}` },
  });
  const data = await readJson(response);
  return data.actions || [];
};

export const claimLeadJourney = async (token: string, businessId: string, surface: 'web' | 'telegram_mini_app' = 'web'): Promise<JourneyAction> => {
  const data = await newAuth.makeRequest('/journeys/claim', {
    method: 'POST',
    body: JSON.stringify({ token, business_id: businessId, surface }),
  });
  return data.action;
};

export const createJourneyCommandIdempotencyKey = () => (
  typeof crypto.randomUUID === 'function' ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`
);

export const runJourneyCommand = async ({
  action,
  businessId,
  command,
  payload = {},
  surface = 'web',
  idempotencyKey = createJourneyCommandIdempotencyKey(),
}: {
  action: JourneyAction;
  businessId: string;
  command: string;
  payload?: Record<string, unknown>;
  surface?: 'web' | 'telegram_mini_app';
  idempotencyKey?: string;
}) => {
  if (surface === 'web') {
    return newAuth.makeRequest(`/journey-actions/${encodeURIComponent(action.id)}/commands`, {
      method: 'POST',
      headers: { 'Idempotency-Key': idempotencyKey },
      body: JSON.stringify({ business_id: businessId, command, version: action.version, surface, payload }),
    });
  }
  const miniSession = window.sessionStorage.getItem('localos_mini_session') || '';
  const response = await fetch(`/api/journey-actions/${encodeURIComponent(action.id)}/commands`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${miniSession}`,
      'Content-Type': 'application/json',
      'Idempotency-Key': idempotencyKey,
    },
    body: JSON.stringify({ business_id: businessId, command, version: action.version, surface, payload }),
  });
  return readJson(response);
};

export const leadJourneyDirections: LeadJourneyDirection[] = [
  {
    key: 'influencers',
    eyebrow: 'Инфлюенсеры рядом',
    title: 'Местные авторы рассказывают о вашем бизнесе',
    preview: 'Подбор местных авторов, условия сотрудничества и статусы публикаций — в одном месте.',
    detailTitle: 'Продвижение через местных авторов',
    detail: 'LocalOS подбирает авторов рядом, готовит предложение и собирает договорённости, визиты и публикации в одном месте.',
    steps: [
      { title: 'Задаём рамки', description: 'Указываете город, аудиторию, услугу для продвижения и допустимый формат: бартер, оплата или промокод.' },
      { title: 'Собираем кандидатов', description: 'LocalOS показывает авторов по географии, тематике и открытым данным. Вы видите, почему каждый кандидат попал в список.' },
      { title: 'Согласовываем предложение', description: 'Вы выбираете автора и проверяете текст, условия визита, дату и то, что нужно показать в публикации.' },
      { title: 'Фиксируем результат', description: 'После ответа отмечаете договорённость, публикацию или отказ. Следующий шаг зависит от фактического статуса, а не запускается вслепую.' },
    ],
    detailSections: [
      {
        title: 'Авторы и публикации',
        items: [
          'Подбор по городу, тематике и аудитории',
          'Бартер, оплата или промокод',
          'Статусы: договорённость, визит, публикация или отказ',
        ],
      },
      {
        title: 'Всё под вашим контролем',
        items: [
          'Вы видите, кто согласился и когда запланирован визит',
          'Заранее указываете, что показать в видео или посте',
          'Любое обращение отправляется только после вашего подтверждения',
        ],
      },
    ],
    continueTitle: 'Начать подбор',
    continueText: 'Укажите бизнес и город — откроется список местных авторов. Ничего не отправляется без подтверждения.',
    businessRole: 'Вы утверждаете автора, условия, текст обращения и любую внешнюю отправку.',
    localosRole: 'LocalOS собирает открытые данные, объясняет подбор и хранит ход договорённостей.',
    prepareLabel: 'Показать персональное превью',
    resultTitle: 'Что будет в обращении к автору',
    resultPreview: [
      'Короткое персональное открытие по публичному материалу автора',
      'Одна механика на выбор: бартер, фиксированная оплата или промокод',
      'Один простой вопрос без давления и массовой рассылки',
    ],
    lockedResult: 'После регистрации откроются полный текст, источник персонализации и кнопка «Отметить, что написал».',
    dashboardRoute: '/dashboard/influencers',
  },
  {
    key: 'partnerships',
    eyebrow: 'Бизнесы рядом',
    title: 'Найти партнёра с похожей аудиторией',
    preview: 'Покажем один соседний бизнес и конкретную идею взаимного продвижения.',
    detailTitle: 'Предложение, полезное обеим сторонам',
    detail: 'LocalOS сопоставляет аудитории и услуги, объясняет взаимную пользу и готовит безопасный первый тест, который легко обсудить.',
    steps: [
      { title: 'Определяем общую аудиторию', description: 'Выбираете услугу и тип соседнего бизнеса, с которым имеет смысл обмениваться рекомендациями.' },
      { title: 'Сравниваем кандидатов', description: 'LocalOS показывает компании рядом и объясняет, где аудитории и предложения действительно пересекаются.' },
      { title: 'Выбираем небольшой тест', description: 'Согласовываете одну механику: совместное предложение, взаимную рекомендацию или локальное событие.' },
      { title: 'Отмечаем ответ', description: 'После ручной отправки фиксируете ответ. Продолжение появляется только по фактическому результату.' },
    ],
    businessRole: 'Вы выбираете партнёра, условия теста и подтверждаете обращение.',
    localosRole: 'LocalOS помогает сравнить кандидатов и собрать предложение без массовой рассылки.',
    prepareLabel: 'Подготовить предложение партнёру',
    resultTitle: 'Предложение партнёру подготовлено',
    resultPreview: [
      'Почему аудитории двух бизнесов пересекаются',
      'Конкретный тест: совместное предложение или взаимная рекомендация',
      'Первое сообщение с одним вопросом и ручным подтверждением отправки',
    ],
    lockedResult: 'После регистрации откроются подходящие компании, полный текст и цикл follow-up по фактическому статусу ответа.',
    dashboardRoute: '/dashboard/promotion/partnerships',
  },
  {
    key: 'maps',
    eyebrow: 'Карты',
    title: 'Исправить то, что сейчас мешает выбрать вас',
    preview: 'Покажем одно приоритетное исправление карточки вместо длинного аудита.',
    detailTitle: 'Первое исправление с понятным эффектом',
    detail: 'LocalOS проверяет услуги, категории, фото, публикации и отзывы, а затем ставит изменения в правильной последовательности по существующему плану карт.',
    steps: [
      { title: 'Читаем карточку как клиент', description: 'Проверяем категории, услуги, фото, публикации, рейтинг и отзывы в открытой карточке.' },
      { title: 'Находим главный пробел', description: 'Показываем одно исправление, которое сейчас сильнее остальных мешает выбору бизнеса.' },
      { title: 'Проверяем изменение', description: 'Вы видите точный текст или действие до применения и решаете, использовать его или нет.' },
      { title: 'Смотрим результат', description: 'После изменения сравниваем состояние карточки и только затем предлагаем следующий шаг.' },
    ],
    businessRole: 'Вы проверяете данные и отдельно подтверждаете каждое изменение.',
    localosRole: 'LocalOS проводит аудит, расставляет приоритеты и сохраняет историю проверки.',
    prepareLabel: 'Показать первое исправление',
    resultTitle: 'Первое исправление определено',
    resultPreview: [
      'Что именно изменить в карточке в первую очередь',
      'Почему этот шаг важнее остальных сейчас',
      'Когда проверить эффект и какое исправление делать следующим',
    ],
    lockedResult: 'После регистрации откроются точный текст изменения, полный план карт и контроль результата по расписанию.',
    dashboardRoute: '/dashboard/card',
  },
  {
    key: 'content',
    eyebrow: 'Контент',
    title: 'Подготовить материал, который напомнит о вашем бизнесе',
    preview: 'Покажем одну подходящую тему и короткий фрагмент будущего материала.',
    detailTitle: 'Тема с понятной целью и следующим шагом',
    detail: 'LocalOS использует услуги, сезон, отзывы и контекст бизнеса, чтобы предложить не абстрактную идею, а материал для конкретной площадки.',
    steps: [
      { title: 'Выбираем площадку и задачу', description: 'Определяете, где выйдет материал и что он должен объяснить клиенту.' },
      { title: 'Собираем факты', description: 'LocalOS использует подтверждённые услуги, цены, сезонность и отзывы бизнеса.' },
      { title: 'Проверяем черновик', description: 'Вы редактируете текст, факты и призыв к действию до сохранения в план.' },
      { title: 'Публикуем отдельно', description: 'Сохранение черновика ничего не публикует. Выход материала требует отдельного подтверждения.' },
    ],
    businessRole: 'Вы отвечаете за факты, финальную редактуру и решение о публикации.',
    localosRole: 'LocalOS предлагает тему, собирает черновик и помогает держать календарь.',
    prepareLabel: 'Подготовить черновик',
    resultTitle: 'Структура первого материала готова',
    resultPreview: [
      'Тема и цель публикации для конкретной аудитории',
      'Короткий черновик в понятном голосе бизнеса',
      'Проверка, календарь и отдельное подтверждение публикации',
    ],
    lockedResult: 'После регистрации откроются полный черновик, редактирование и сохранение в контент-календарь.',
    dashboardRoute: '/dashboard/content',
  },
  {
    key: 'automation',
    eyebrow: 'ИИ-сотрудники',
    title: 'Поручить LocalOS повторяющуюся задачу',
    preview: 'Покажем один безопасный сценарий автоматизации и что останется под вашим подтверждением.',
    detailTitle: 'Одна регулярная задача под контролем',
    detail: 'LocalOS помогает выбрать повторяющуюся работу, проверить источники данных и ограничения, а затем запустить ИИ-сотрудника через существующий preflight.',
    steps: [
      { title: 'Выбираем одну задачу', description: 'Фиксируете повторяющуюся работу и понятный результат, который должен появляться в кабинете.' },
      { title: 'Проверяем доступы и ограничения', description: 'LocalOS показывает, какие данные нужны и какие действия нельзя выполнять без человека.' },
      { title: 'Делаем пробный запуск', description: 'Сначала вы видите результат на примере и проверяете его до регулярной работы.' },
      { title: 'Следим за статусом', description: 'В кабинете видно, что выполнено, где нужна проверка и почему задача остановилась.' },
    ],
    businessRole: 'Вы задаёте правила и подтверждаете публикации, отправки и другие внешние действия.',
    localosRole: 'LocalOS выполняет согласованную внутреннюю работу и показывает результат и статус.',
    prepareLabel: 'Показать сценарий автоматизации',
    resultTitle: 'Сценарий автоматизации подготовлен',
    resultPreview: [
      'Какая повторяющаяся задача будет выполняться',
      'Какие данные нужны и что проверит LocalOS до запуска',
      'Какие внешние действия всё равно потребуют ручного подтверждения',
    ],
    lockedResult: 'После регистрации откроется настройка ИИ-сотрудника. Проверка плана и запуск доступны после оплаты и отдельного подтверждения.',
    dashboardRoute: '/dashboard/agents',
  },
];

export const isLeadJourneyKey = (value: string | null): value is LeadJourneyKey => (
  value === 'influencers' || value === 'partnerships' || value === 'maps' || value === 'content' || value === 'automation'
);

export const leadJourneyKeyForFlow = (flow: string | null | undefined): LeadJourneyKey | null => {
  if (flow === 'influencer') return 'influencers';
  if (flow === 'partnership') return 'partnerships';
  return isLeadJourneyKey(flow || null) ? flow : null;
};

export const journeyActionRoute = (action: JourneyAction) => {
  const screen = action.cta_target?.screen;
  const routes: Record<string, string> = {
    influencers: '/dashboard/influencers',
    partnerships: '/dashboard/promotion/partnerships',
    progress: '/dashboard/card',
    maps: '/dashboard/card',
    content: '/dashboard/content',
    agents: '/dashboard/agents',
    settings: '/dashboard/settings',
    today: '/dashboard/today',
  };
  const base = routes[screen || ''] || '/dashboard/today';
  const separator = base.includes('?') ? '&' : '?';
  return `${base}${separator}journey_action=${encodeURIComponent(action.id)}`;
};

const businessIdFromUser = (user: { businesses?: unknown[] } | null | undefined) => {
  const businesses = Array.isArray(user?.businesses) ? user.businesses : [];
  const savedBusinessId = window.localStorage.getItem('selectedBusinessId') || '';
  const availableIds = businesses.map((business) => {
    if (!business || typeof business !== 'object' || !('id' in business)) return '';
    const value = business.id;
    return typeof value === 'string' ? value : '';
  }).filter(Boolean);
  if (savedBusinessId && availableIds.includes(savedBusinessId)) return savedBusinessId;
  return availableIds[0] || '';
};

export const resolveStoredLeadJourney = async (preferredBusinessId = '') => {
  const token = readLeadJourneyToken();
  if (!token) return null;
  const user = await newAuth.getCurrentUser();
  const businessId = preferredBusinessId || businessIdFromUser(user);
  if (!businessId) throw new Error('Не найден бизнес для продолжения персонального сценария');
  const action = await claimLeadJourney(token, businessId);
  const route = journeyActionRoute(action);
  clearLeadJourneyToken();
  clearLeadJourneyIntent();
  return { action, businessId, route };
};

export const getLeadJourneyDirection = (key: LeadJourneyKey | null | undefined) => (
  leadJourneyDirections.find((direction) => direction.key === key) || null
);

export const saveLeadJourneyIntent = (key: LeadJourneyKey) => {
  try {
    window.localStorage.setItem(LEAD_JOURNEY_STORAGE_KEY, key);
  } catch {
    // Storage may be unavailable in privacy mode; navigation still works.
  }
};

export const saveLeadJourneyToken = (token: string) => {
  try {
    window.localStorage.setItem(LEAD_JOURNEY_TOKEN_STORAGE_KEY, token);
  } catch {
    // The token is also carried in the registration URL.
  }
};

export const readLeadJourneyToken = () => {
  try {
    return window.localStorage.getItem(LEAD_JOURNEY_TOKEN_STORAGE_KEY) || '';
  } catch {
    return '';
  }
};

export const clearLeadJourneyToken = () => {
  try {
    window.localStorage.removeItem(LEAD_JOURNEY_TOKEN_STORAGE_KEY);
  } catch {
    // No cleanup is possible in restricted storage mode.
  }
};

export const readLeadJourneyIntent = (): LeadJourneyKey | null => {
  try {
    const value = window.localStorage.getItem(LEAD_JOURNEY_STORAGE_KEY);
    return isLeadJourneyKey(value) ? value : null;
  } catch {
    return null;
  }
};

export const clearLeadJourneyIntent = () => {
  try {
    window.localStorage.removeItem(LEAD_JOURNEY_STORAGE_KEY);
  } catch {
    // Nothing else is required when storage is unavailable.
  }
};
