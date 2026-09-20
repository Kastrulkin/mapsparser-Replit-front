import type { Language } from '@/i18n/LanguageContext.logic';
import { actionMessages, managedCardGrowthCopyAdditional } from './managedCardGrowthCopyAdditional';

export type ManagedCardGrowthActionCode = 'refresh' | 'restore' | 'add_provider' | 'blocked' | 'access' | 'verified' | 'duplicate' | 'category' | 'contacts' | 'schedule' | 'action_path' | 'services' | 'prices' | 'reviews' | 'review_responses' | 'photos' | 'publications';

export type ManagedCardGrowthActionCopy = {
  title: (provider: string) => string;
  reason: (provider: string, params: { benchmarkMedian?: number }) => string;
  cta: string;
  outcome: (goal: string) => string;
};

export type ManagedCardGrowthCopy = {
  eyebrow: string;
  title: string;
  description: string;
  goal: string;
  chooseGoal: string;
  saving: string;
  confirmGoal: string;
  goalConfirmed: string;
  networkGoal: string;
  saveError: string;
  waitingUntil: (date: string) => string;
  waitingDescription: string;
  baseline: string;
  views: string;
  clicks: string;
  actions: string;
  baselineDisclaimer: string;
  resultDisclaimer: string;
  result: string;
  critical: string;
  noCritical: string;
  needsAttention: string;
  snapshot: (date: string) => string;
  sourceObserved: string;
  sourceBlocked: string;
  sourceUnknown: string;
  benchmark: (count: number, days: number) => string;
  smallSample: string;
  median: string;
  upperQuartile: string;
  benchmarkDisclaimer: string;
  noProviders: string;
  noCardState: string;
  nextSteps: string;
  nextStepsDescription: string;
  policyVersion: string;
  policyUnknown: string;
  openEvidence: string;
  dateUnknown: string;
  actionHeading: string;
  actionDescription: string;
  expectedOutcome: string;
  continue: string;
  auditState: string;
  auditDescription: string;
  source: string;
  snapshotMissing: string;
  safeFallback: string;
  goals: Record<string, string>;
  gates: Record<number, string>;
  facts: Record<string, string>;
  states: Record<string, string>;
  evidence: Record<string, string>;
  decisions: Record<string, string>;
  actionMessages: Record<ManagedCardGrowthActionCode, ManagedCardGrowthActionCopy>;
};

const facts = {
  access: 'Access', verified: 'Verification', duplicate: 'Duplicates', category: 'Category', contacts: 'Contacts', schedule: 'Hours', action_path: 'Contact path', services: 'Services', prices: 'Prices', reviews: 'Reviews', review_responses: 'Review replies', photos: 'Photos', publications: 'Updates',
};
const states = { observed: 'Verified', missing: 'Needs completion', unknown: 'No data', not_applicable: 'Not applicable', blocked: 'Source unavailable' };
const goals = { inquiries: 'More enquiries', bookings: 'More bookings', orders: 'More orders', directions: 'More directions', website_visits: 'More website visits' };
const gates = { 0: 'Data available', 1: 'Listing is correct', 2: 'Customers can contact you', 3: 'Offer is clear', 4: 'Trust is present', 5: 'Proof is present', 6: 'Reason to return exists' };
const evidence = {
  connected: 'Listing connected', link_missing: 'No listing link has been added', no_duplicates: 'No duplicates found', duplicate_unverified: 'The platform did not provide a reliable duplicate signal', internal_contacts: 'Internal business contacts do not prove publication on the platform', internal_schedule: 'Internal hours do not prove the platform hours are current', internal_services: 'Internal services do not prove they are published on the platform', internal_prices: 'Internal prices exist, but the platform still needs checking', no_organic_news: '2GIS has no organic news channel', conversion_content: 'Updates are conversion content, not a mandatory ranking factor', source_error: 'The last platform refresh failed',
};
const decisions = { insufficient_data: 'There is not enough comparable platform data to assess the result.', continue: 'Verified actions on the listings increased compared with the baseline.', adjust: 'There is no growth at the first checkpoint yet; the next period will be checked.', replace: 'No action growth was recorded for the checkpoint; a different hypothesis is needed.' };
const ruActions = actionMessages("ru-RU", {
  "refresh": [
    "Обновите данные {provider}",
    "Для выбора первого исправления нужен свежий снимок карточки.",
    "Обновить данные"
  ],
  "restore": [
    "Восстановите обновление {provider}",
    "Последнее обновление завершилось ошибкой.",
    "Проверить подключение"
  ],
  "add_provider": [
    "Добавьте площадку для проверки",
    "LocalOS пока не знает, какие карточки принадлежат этой точке. Добавьте Google, Яндекс или 2ГИС, чтобы получить первый снимок.",
    "Добавить площадку"
  ],
  "blocked": [
    "Восстановите обновление {provider}",
    "Площадка временно не отдаёт достоверные данные. Сначала восстановите источник.",
    "Проверить подключение"
  ],
  "access": [
    "Подключите карточку {provider}",
    "Без подключения LocalOS не может проверить карточку и отслеживать результат.",
    "Добавить площадку"
  ],
  "verified": [
    "Проверьте управление карточкой в {provider}",
    "Площадка не подтверждает, что карточка находится под управлением бизнеса.",
    "Открыть карточку"
  ],
  "duplicate": [
    "Проверьте дубли в {provider}",
    "Дубль может разделять отзывы и вводить клиентов в заблуждение.",
    "Проверить карточку"
  ],
  "category": [
    "Уточните основную категорию в {provider}",
    "Категория должна точно описывать основную деятельность этой точки.",
    "Проверить категорию"
  ],
  "contacts": [
    "Заполните контакты в {provider}",
    "Клиент должен сразу понимать, как связаться с этой точкой.",
    "Проверить контакты"
  ],
  "schedule": [
    "Уточните часы работы в {provider}",
    "Актуальное расписание снижает риск потерянного визита.",
    "Проверить расписание"
  ],
  "action_path": [
    "Добавьте понятный путь обращения в {provider}",
    "Телефон, сайт или запись должны вести к конкретной точке и работать без лишних шагов.",
    "Проверить запись"
  ],
  "services": [
    "Опубликуйте основные услуги в {provider}",
    "По карточке пока нельзя уверенно понять, что именно предлагает бизнес.",
    "Открыть услуги"
  ],
  "prices": [
    "Добавьте цены в {provider}",
    "Цена или понятный ориентир помогают принять решение до обращения.",
    "Открыть услуги"
  ],
  "reviews": [
    "Начните системно собирать отзывы в {provider}",
    "Для этой карточки доверие пока подтверждено слабее, чем у сопоставимых компаний.",
    "Открыть отзывы"
  ],
  "review_responses": [
    "Ответьте на отзывы в {provider}",
    "На карточке есть отзывы без ответа.",
    "Открыть отзывы"
  ],
  "photos": [
    "Добавьте полезные фотографии в {provider}",
    "Покажите вход, пространство, команду, процесс и результат, чтобы клиенту было проще выбрать.",
    "Открыть фотографии"
  ],
  "publications": [
    "Подготовьте актуальную публикацию для {provider}",
    "Публикация должна дать конкретный повод обратиться сейчас; она не заменяет заполнение карточки.",
    "Открыть контент"
  ]
}, {
  "inquiries": "Упростить обращение и проверить изменение подтверждённых действий в карточке.",
  "bookings": "Упростить запись и проверить изменение записей или обращений.",
  "orders": "Упростить заказ и проверить изменение заказов или обращений.",
  "directions": "Сделать визит понятнее и проверить изменение построенных маршрутов.",
  "website_visits": "Сделать переход на сайт заметнее и проверить изменение кликов."
}, "Получить достоверное состояние карточки и выбрать первое исправление.", "Получить свежие данные карточки и определить первое исправление.", "У сопоставимых карточек медиана");

const enActions = actionMessages("en-GB", {
  "refresh": [
    "Refresh data for {provider}",
    "A fresh listing snapshot is needed to select the first correction.",
    "Refresh data"
  ],
  "restore": [
    "Restore updates for {provider}",
    "The last update failed.",
    "Check connection"
  ],
  "add_provider": [
    "Add a platform to check",
    "LocalOS does not yet know which listings belong to this location. Add Google, Yandex or 2GIS to get the first snapshot.",
    "Add platform"
  ],
  "blocked": [
    "Restore updates for {provider}",
    "The platform is temporarily not returning reliable data. Restore the source first.",
    "Check connection"
  ],
  "access": [
    "Connect the {provider} listing",
    "Without a connection, LocalOS cannot check the listing or track the result.",
    "Add platform"
  ],
  "verified": [
    "Check listing management in {provider}",
    "The platform does not confirm that the business manages this listing.",
    "Open listing"
  ],
  "duplicate": [
    "Check duplicates in {provider}",
    "A duplicate can split reviews and confuse customers.",
    "Check listing"
  ],
  "category": [
    "Clarify the primary category in {provider}",
    "The category should accurately describe this location’s main activity.",
    "Check category"
  ],
  "contacts": [
    "Complete contacts in {provider}",
    "Customers should immediately understand how to contact this location.",
    "Check contacts"
  ],
  "schedule": [
    "Clarify opening hours in {provider}",
    "Current opening hours reduce the risk of a wasted visit.",
    "Check hours"
  ],
  "action_path": [
    "Add a clear contact path in {provider}",
    "Phone, website or booking should lead to this location and work without unnecessary steps.",
    "Check booking"
  ],
  "services": [
    "Publish the main services in {provider}",
    "The listing does not yet clearly show what the business offers.",
    "Open services"
  ],
  "prices": [
    "Add prices in {provider}",
    "A price or clear guide helps customers decide before contacting you.",
    "Open services"
  ],
  "reviews": [
    "Start collecting reviews consistently in {provider}",
    "Trust in this listing is currently less supported than for comparable businesses.",
    "Open reviews"
  ],
  "review_responses": [
    "Reply to reviews in {provider}",
    "There are unanswered reviews on this listing.",
    "Open reviews"
  ],
  "photos": [
    "Add useful photos to {provider}",
    "Show the entrance, space, team, process and result to make choosing easier.",
    "Open photos"
  ],
  "publications": [
    "Prepare a timely post for {provider}",
    "The post should give a concrete reason to contact you now; it does not replace completing the listing.",
    "Open content"
  ]
}, {
  "inquiries": "Make contacting the business easier and check the change in verified listing actions.",
  "bookings": "Make booking easier and check the change in bookings or enquiries.",
  "orders": "Make ordering easier and check the change in orders or enquiries.",
  "directions": "Make visiting clearer and check the change in requested directions.",
  "website_visits": "Make the website link more visible and check the change in clicks."
}, "Get a reliable listing status and select the first correction.", "Get fresh listing data and identify the first correction.", "Median for comparable listings");

const esActions = actionMessages("es-ES", {
  "refresh": [
    "Actualiza los datos de {provider}",
    "Se necesita una instantánea reciente de la ficha para elegir la primera corrección.",
    "Actualizar datos"
  ],
  "restore": [
    "Restablece las actualizaciones de {provider}",
    "La última actualización falló.",
    "Revisar conexión"
  ],
  "add_provider": [
    "Añade una plataforma para revisar",
    "LocalOS aún no sabe qué fichas pertenecen a esta ubicación. Añade Google, Yandex o 2GIS para obtener la primera instantánea.",
    "Añadir plataforma"
  ],
  "blocked": [
    "Restablece las actualizaciones de {provider}",
    "La plataforma no está proporcionando datos fiables temporalmente. Restablece primero la fuente.",
    "Revisar conexión"
  ],
  "access": [
    "Conecta la ficha de {provider}",
    "Sin conexión, LocalOS no puede revisar la ficha ni seguir el resultado.",
    "Añadir plataforma"
  ],
  "verified": [
    "Revisa la gestión de la ficha en {provider}",
    "La plataforma no confirma que el negocio gestione la ficha.",
    "Abrir ficha"
  ],
  "duplicate": [
    "Revisa los duplicados en {provider}",
    "Un duplicado puede dividir las reseñas y confundir a los clientes.",
    "Revisar ficha"
  ],
  "category": [
    "Aclara la categoría principal en {provider}",
    "La categoría debe describir con precisión la actividad principal de esta ubicación.",
    "Revisar categoría"
  ],
  "contacts": [
    "Completa los contactos en {provider}",
    "El cliente debe entender enseguida cómo contactar con esta ubicación.",
    "Revisar contactos"
  ],
  "schedule": [
    "Aclara el horario en {provider}",
    "Un horario actualizado reduce el riesgo de una visita perdida.",
    "Revisar horario"
  ],
  "action_path": [
    "Añade una vía de contacto clara en {provider}",
    "El teléfono, el sitio web o la reserva deben llevar a esta ubicación y funcionar sin pasos innecesarios.",
    "Revisar reservas"
  ],
  "services": [
    "Publica los servicios principales en {provider}",
    "La ficha aún no permite entender con claridad qué ofrece el negocio.",
    "Abrir servicios"
  ],
  "prices": [
    "Añade precios en {provider}",
    "Un precio o una referencia clara ayudan a decidir antes de contactar.",
    "Abrir servicios"
  ],
  "reviews": [
    "Empieza a recopilar reseñas de forma sistemática en {provider}",
    "La confianza en esta ficha está menos respaldada que en negocios comparables.",
    "Abrir reseñas"
  ],
  "review_responses": [
    "Responde a las reseñas en {provider}",
    "Hay reseñas sin respuesta en la ficha.",
    "Abrir reseñas"
  ],
  "photos": [
    "Añade fotos útiles en {provider}",
    "Muestra la entrada, el espacio, el equipo, el proceso y el resultado para facilitar la elección.",
    "Abrir fotos"
  ],
  "publications": [
    "Prepara una publicación actual para {provider}",
    "La publicación debe dar un motivo concreto para contactar ahora; no sustituye completar la ficha.",
    "Abrir contenido"
  ]
}, {
  "inquiries": "Facilitar el contacto y comprobar el cambio en las acciones verificadas de la ficha.",
  "bookings": "Facilitar las reservas y comprobar el cambio en reservas o consultas.",
  "orders": "Facilitar los pedidos y comprobar el cambio en pedidos o consultas.",
  "directions": "Aclarar cómo llegar y comprobar el cambio en las rutas solicitadas.",
  "website_visits": "Destacar el enlace al sitio web y comprobar el cambio en los clics."
}, "Obtener un estado fiable de la ficha y elegir la primera corrección.", "Obtener datos recientes de la ficha e identificar la primera corrección.", "Mediana de fichas comparables");

const en: ManagedCardGrowthCopy = {
  eyebrow: 'Managed listing work', title: 'Listing goal and status', description: 'LocalOS checks platforms in order: listing access and accuracy first, then the contact path, offer, trust, photos and timely reasons to act.', goal: 'Goal', chooseGoal: 'Choose a goal', saving: 'Saving…', confirmGoal: 'Confirm goal', goalConfirmed: 'Goal confirmed. The next step is selected against it.', networkGoal: 'Confirm the goal separately for each location in the network.', saveError: 'Could not save the goal', waitingUntil: (date) => `Waiting for data until ${date}`, waitingDescription: 'The change is already in place. On the checkpoint date, LocalOS will compare listing actions with the 28-day baseline.', baseline: 'Baseline: 28 days', views: 'Views', clicks: 'Clicks', actions: 'Actions', baselineDisclaimer: 'Views and clicks are not confirmed customers or sales.', result: 'Review result', critical: 'A critical blocker exists', noCritical: 'No critical blockers found', needsAttention: 'Needs attention', snapshot: (date) => `Snapshot: ${date}`, sourceObserved: 'Data received', sourceBlocked: 'Source unavailable', sourceUnknown: 'A new snapshot is needed', benchmark: (count, days) => `Benchmark: ${count} comparable businesses, data no older than ${days} days.`, smallSample: ' The sample is below the minimum of 10 businesses.', median: 'median', upperQuartile: 'upper quartile', benchmarkDisclaimer: 'The comparison is a reference, not proof of the cause of a result.', noProviders: 'No platforms have been added yet. Connect Google, Yandex or 2GIS and collect a fresh snapshot.', noCardState: 'Listing status has not been received yet.', nextSteps: 'Next steps', nextStepsDescription: 'They become primary only after the current step is completed and data is checked.', policyVersion: 'Policy version', policyUnknown: 'not specified', openEvidence: 'Open audit evidence', dateUnknown: 'date unavailable', actionHeading: 'Main action', actionDescription: 'Complete this step first. LocalOS will then wait for the checkpoint date and compare the result.', expectedOutcome: 'Expected result', continue: 'Continue', auditState: 'Status by platform', auditDescription: 'Each conclusion is tied to a source and snapshot date. Unknown data is not treated as missing.', source: 'Source', snapshotMissing: 'not received', safeFallback: 'Open the listing to review the next step.', goals, gates, facts, states, evidence, decisions, actionMessages: enActions,
  resultDisclaimer: 'Platform actions are not confirmed customers, orders or sales.',
};

const copy: Record<Language, ManagedCardGrowthCopy> = {
  ru: { eyebrow: 'Управляемое ведение карточки', title: 'Цель и состояние карточек', description: 'LocalOS проверяет площадки по очереди: сначала доступность и корректность карточки, затем путь обращения, предложение, доверие, фотографии и актуальные поводы.', goal: 'Цель', chooseGoal: 'Выберите цель', saving: 'Сохраняем…', confirmGoal: 'Подтвердить цель', goalConfirmed: 'Цель подтверждена. Следующий шаг выбран относительно неё.', networkGoal: 'Для сети цель подтверждается отдельно у каждой точки.', saveError: 'Не удалось сохранить цель', waitingUntil: (date) => `Ждём данные до ${date}`, waitingDescription: 'Исправление уже внесено. В контрольную дату сравним действия в карточке с базовыми 28 днями.', baseline: 'Базовые 28 дней', views: 'Показы', clicks: 'Клики', actions: 'Действия', baselineDisclaimer: 'Показы и нажатия не считаются подтверждёнными клиентами или продажами.', result: 'Результат проверки', critical: 'Есть критичное препятствие', noCritical: 'Критичных препятствий не обнаружено', needsAttention: 'Нужно внимание', snapshot: (date) => `Снимок: ${date}`, sourceObserved: 'Данные получены', sourceBlocked: 'Источник недоступен', sourceUnknown: 'Нужен новый снимок', benchmark: (count, days) => `Ориентир: ${count} сопоставимых компаний, данные не старше ${days} дней.`, smallSample: ' Выборка меньше минимальных 10 компаний.', median: 'медиана', upperQuartile: 'верхний квартиль', benchmarkDisclaimer: 'Сравнение показывает ориентир, а не доказательство причины результата.', noProviders: 'Ни одна площадка ещё не добавлена. Сначала подключите Google, Яндекс или 2ГИС и получите свежий снимок.', noCardState: 'Состояние карточек пока не получено.', nextSteps: 'Следующие шаги', nextStepsDescription: 'Они станут главными только после завершения текущего шага и проверки данных.', policyVersion: 'Версия правил', policyUnknown: 'не определена', openEvidence: 'Открыть доказательства аудита', dateUnknown: 'дата не получена', actionHeading: 'Главное действие', actionDescription: 'Сначала выполните этот шаг. После него LocalOS дождётся контрольной даты и сравнит результат.', expectedOutcome: 'Ожидаемый результат', continue: 'Продолжить', auditState: 'Состояние по площадкам', auditDescription: 'Каждый вывод привязан к источнику и дате снимка. Неизвестные данные не считаются отсутствующими.', source: 'Источник', snapshotMissing: 'не получен', safeFallback: 'Откройте карточку, чтобы проверить следующий шаг.', facts: { access: 'Доступ', verified: 'Подтверждение', duplicate: 'Дубли', category: 'Категория', contacts: 'Контакты', schedule: 'Расписание', action_path: 'Запись или заказ', services: 'Услуги', prices: 'Цены', reviews: 'Отзывы', review_responses: 'Ответы на отзывы', photos: 'Фотографии', publications: 'Публикации' }, states: { observed: 'Проверено', missing: 'Нужно заполнить', unknown: 'Нет данных', not_applicable: 'Не применяется', blocked: 'Источник недоступен' }, goals: { inquiries: 'Больше обращений', bookings: 'Больше записей', orders: 'Больше заказов', directions: 'Больше построенных маршрутов', website_visits: 'Больше переходов на сайт' }, gates: { 0: 'Данные доступны', 1: 'Карточка корректна', 2: 'Можно обратиться', 3: 'Предложение понятно', 4: 'Есть доверие', 5: 'Есть доказательства', 6: 'Есть повод вернуться' }, evidence: { connected: 'Карточка подключена', link_missing: 'Ссылка на площадку не добавлена', no_duplicates: 'Дубли не обнаружены', duplicate_unverified: 'Площадка не передала надёжный признак дубля', internal_contacts: 'Контакты из профиля бизнеса не доказывают, что они опубликованы на площадке', internal_schedule: 'Внутреннее расписание не доказывает, что часы обновлены на площадке', internal_services: 'Внутренние услуги не доказывают их публикацию на площадке', internal_prices: 'Во внутреннем справочнике цены есть, но нужна проверка площадки', no_organic_news: 'У 2ГИС нет органического канала новостей', conversion_content: 'Публикации оцениваются как конверсионный контент, а не обязательный фактор позиции', source_error: 'Последнее обновление площадки завершилось ошибкой' }, decisions: { insufficient_data: 'Недостаточно сопоставимых данных площадок для вывода о результате.', continue: 'Подтверждённые действия в карточках выросли относительно базового периода.', adjust: 'На первой контрольной точке роста действий пока нет; проверим следующий период.', replace: 'За контрольный период роста действий не зафиксировано; нужна другая гипотеза.' }, actionMessages: ruActions, resultDisclaimer: 'Платформенные действия не являются подтверждёнными клиентами, заказами или продажами.' },
  en,
  es: { eyebrow: 'Gestión de fichas', title: 'Objetivo y estado de las fichas', description: 'LocalOS revisa las plataformas por orden: primero el acceso y la precisión de la ficha, después el contacto, la oferta, la confianza, las fotos y los motivos actuales para actuar.', goal: 'Objetivo', chooseGoal: 'Elige un objetivo', saving: 'Guardando…', confirmGoal: 'Confirmar objetivo', goalConfirmed: 'Objetivo confirmado. El siguiente paso se elige según este objetivo.', networkGoal: 'Confirma el objetivo por separado para cada ubicación de la red.', saveError: 'No se pudo guardar el objetivo', waitingUntil: (date) => `Esperando datos hasta ${date}`, waitingDescription: 'El cambio ya está aplicado. En la fecha de control, LocalOS comparará las acciones de la ficha con la base de 28 días.', baseline: 'Base de 28 días', views: 'Vistas', clicks: 'Clics', actions: 'Acciones', baselineDisclaimer: 'Las vistas y los clics no son clientes ni ventas confirmadas.', result: 'Resultado de la revisión', critical: 'Hay un bloqueo crítico', noCritical: 'No se encontraron bloqueos críticos', needsAttention: 'Requiere atención', snapshot: (date) => `Instantánea: ${date}`, sourceObserved: 'Datos recibidos', sourceBlocked: 'Fuente no disponible', sourceUnknown: 'Se necesita una nueva instantánea', benchmark: (count, days) => `Referencia: ${count} negocios comparables, datos de no más de ${days} días.`, smallSample: ' La muestra es menor de 10 negocios.', median: 'mediana', upperQuartile: 'cuartil superior', benchmarkDisclaimer: 'La comparación es una referencia, no una prueba de la causa del resultado.', noProviders: 'Aún no se añadió ninguna plataforma. Conecta Google, Yandex o 2GIS y obtiene una instantánea reciente.', noCardState: 'Aún no se recibió el estado de las fichas.', nextSteps: 'Siguientes pasos', nextStepsDescription: 'Solo serán prioritarios después de completar el paso actual y comprobar los datos.', policyVersion: 'Versión de la política', policyUnknown: 'sin especificar', openEvidence: 'Abrir evidencias de la auditoría', dateUnknown: 'fecha no disponible', actionHeading: 'Acción principal', actionDescription: 'Completa primero este paso. Después LocalOS esperará la fecha de control y comparará el resultado.', expectedOutcome: 'Resultado esperado', continue: 'Continuar', auditState: 'Estado por plataforma', auditDescription: 'Cada conclusión está vinculada a una fuente y una fecha. Los datos desconocidos no se consideran ausentes.', source: 'Fuente', snapshotMissing: 'no recibida', safeFallback: 'Abre la ficha para revisar el siguiente paso.', goals: { inquiries: 'Más consultas', bookings: 'Más reservas', orders: 'Más pedidos', directions: 'Más rutas', website_visits: 'Más visitas al sitio' }, gates: { 0: 'Datos disponibles', 1: 'La ficha es correcta', 2: 'Se puede contactar', 3: 'La oferta es clara', 4: 'Hay confianza', 5: 'Hay pruebas', 6: 'Hay un motivo para volver' }, facts: { access: 'Acceso', verified: 'Verificación', duplicate: 'Duplicados', category: 'Categoría', contacts: 'Contactos', schedule: 'Horario', action_path: 'Vía de contacto', services: 'Servicios', prices: 'Precios', reviews: 'Reseñas', review_responses: 'Respuestas a reseñas', photos: 'Fotos', publications: 'Publicaciones' }, states: { observed: 'Verificado', missing: 'Debe completarse', unknown: 'Sin datos', not_applicable: 'No aplica', blocked: 'Fuente no disponible' }, evidence: { connected: 'Ficha conectada', link_missing: 'No se añadió un enlace a la ficha', no_duplicates: 'No se encontraron duplicados', duplicate_unverified: 'La plataforma no dio una señal fiable de duplicado', internal_contacts: 'Los contactos internos no prueban que estén publicados en la plataforma', internal_schedule: 'El horario interno no prueba que el horario de la plataforma esté actualizado', internal_services: 'Los servicios internos no prueban que estén publicados', internal_prices: 'Hay precios internos, pero la plataforma debe comprobarse', no_organic_news: '2GIS no tiene un canal de noticias orgánico', conversion_content: 'Las publicaciones son contenido de conversión, no un factor obligatorio de posición', source_error: 'La última actualización de la plataforma falló' }, decisions: { insufficient_data: 'No hay datos comparables suficientes para evaluar el resultado.', continue: 'Las acciones verificadas en las fichas crecieron frente al periodo base.', adjust: 'Aún no hay crecimiento en el primer control; se comprobará el siguiente periodo.', replace: 'No se registró crecimiento durante el periodo de control; se necesita otra hipótesis.' }, actionMessages: esActions, resultDisclaimer: 'Las acciones de las plataformas no son clientes, pedidos ni ventas confirmadas.' },
  fr: managedCardGrowthCopyAdditional.fr,
  el: managedCardGrowthCopyAdditional.el,
  de: managedCardGrowthCopyAdditional.de,
  th: managedCardGrowthCopyAdditional.th,
  ar: managedCardGrowthCopyAdditional.ar,
  ha: managedCardGrowthCopyAdditional.ha,
  tr: managedCardGrowthCopyAdditional.tr,
};

const own = (values: Record<string | number, string>, key: string | number | null | undefined) => (
  key != null && Object.prototype.hasOwnProperty.call(values, key) ? values[key] : undefined
);

const localized = (language: Language, value: string | undefined, fallback?: string) => (
  value || (language === 'ru' && fallback ? fallback : copy[language].safeFallback)
);

export const managedCardGrowthCopyForLanguage = (language: Language) => copy[language];
export const managedCardDateLocale: Record<Language, string> = { ru: 'ru-RU', en: 'en-GB', fr: 'fr-FR', es: 'es-ES', el: 'el-GR', de: 'de-DE', th: 'th-TH', ar: 'ar', ha: 'ha-NG', tr: 'tr-TR' };

export const managedGoalLabel = (language: Language, goal?: string | null, fallback?: string) => localized(language, own(copy[language].goals, goal), fallback);
export const managedGateLabel = (language: Language, gate?: number, fallback?: string) => localized(language, own(copy[language].gates, gate), fallback);
export const managedFactLabel = (language: Language, fact?: string) => own(copy[language].facts, fact) || copy[language].safeFallback;
export const managedStateLabel = (language: Language, state?: string) => own(copy[language].states, state) || copy[language].states.unknown;
export const managedProviderLabel = (provider?: string | null, label?: string | null) => label || own({ google: 'Google', yandex: 'Яндекс', '2gis': '2ГИС' }, provider) || provider || '';
export const managedBenchmarkLabel = (language: Language, metric: string) => {
  const ratings: Record<Language, string> = { ru: 'Рейтинг', en: 'Rating', fr: 'Note', es: 'Valoración', el: 'Βαθμολογία', de: 'Bewertung', th: 'คะแนน', ar: 'التقييم', ha: 'Ƙimar ra’ayi', tr: 'Puan' };
  if (metric === 'rating') return ratings[language];
  const fact = own({ reviews_count: 'reviews', photos_count: 'photos', services_count: 'services' }, metric);
  return managedFactLabel(language, fact || metric);
};
export const managedEvidence = (language: Language, code?: string | null, fallback?: string) => {
  if (!code && !fallback) return '';
  return localized(language, own(copy[language].evidence, code), fallback);
};
export const managedDecision = (language: Language, code?: string | null, fallback?: string | null) => localized(language, own(copy[language].decisions, code), fallback || undefined);

export const managedDisclaimer = (language: Language, code?: string | null, fallback?: string) => {
  const item = copy[language];
  const messages: Record<string, string> = {
    views_not_sales: item.baselineDisclaimer,
    platform_actions_not_sales: item.resultDisclaimer,
    relative_benchmark: item.benchmarkDisclaimer,
  };
  return localized(language, own(messages, code), fallback);
};

export type ManagedActionFallback = { title?: string; reason?: string; cta?: string; outcome?: string };

export const managedActionCopy = (
  language: Language, code?: string | null, provider?: string | null, goal?: string,
  benchmarkMedian?: number, fallback: ManagedActionFallback = {},
) => {
  const item = copy[language];
  const message = Object.entries(item.actionMessages).find(([key]) => key === code)?.[1];
  if (!message) return {
    title: localized(language, undefined, fallback.title),
    reason: localized(language, undefined, fallback.reason),
    cta: language === 'ru' && fallback.cta ? fallback.cta : item.continue,
    outcome: localized(language, undefined, fallback.outcome),
  };
  return {
    title: message.title(provider || ''),
    reason: message.reason(provider || '', { benchmarkMedian }),
    cta: message.cta,
    outcome: message.outcome(goal || ''),
  };
};
