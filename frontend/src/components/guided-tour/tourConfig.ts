export type GuidedTourChapter = 'network-pulse' | 'card-content' | 'partnership';

export type GuidedTourStep = {
  key: string;
  chapter: GuidedTourChapter;
  chapterTitle: string;
  title: string;
  body: string;
  route: string;
  target?: string;
  final?: boolean;
};

export const GUIDED_TOUR_KEY = 'roga-i-kopyta-v1';
export const GUIDED_TOUR_VERSION = 1;

export const GUIDED_TOUR_STEPS: GuidedTourStep[] = [
  {
    key: 'welcome',
    chapter: 'network-pulse',
    chapterTitle: 'Скрепка LocalOS',
    title: 'Я помогу освоиться',
    body: 'За 8–10 минут мы посмотрим состояние сети, карточку на картах, контент и партнёрство. Вы можете свободно исследовать кабинет и в любой момент вернуться к маршруту.',
    route: '/dashboard/operator',
  },
  {
    key: 'operator-nav',
    chapter: 'network-pulse',
    chapterTitle: 'Скрепка LocalOS',
    title: 'Оператор — управление через чат',
    body: 'Здесь можно управлять LocalOS обычными сообщениями вместо переходов по разделам. Тот же способ управления доступен в Telegram-боте.',
    route: '/dashboard/operator',
    target: 'nav-operator',
  },
  {
    key: 'operator-overview',
    chapter: 'network-pulse',
    chapterTitle: 'Скрепка LocalOS',
    title: 'Сводка по текущему бизнесу',
    body: 'Оператор знает контекст выбранной точки. В демо команды не запускаются, но видно, как будет выглядеть работа.',
    route: '/dashboard/operator',
    target: 'operator-overview',
  },
  {
    key: 'network-switcher',
    chapter: 'network-pulse',
    chapterTitle: 'Скрепка LocalOS',
    title: 'Сеть из шести точек',
    body: 'Переключатель меняет контекс всего кабинета. Можно сравнивать головной бизнес и каждую локацию.',
    route: '/dashboard/operator',
    target: 'network-switcher',
  },
  {
    key: 'progress-nav',
    chapter: 'network-pulse',
    chapterTitle: 'Скрепка LocalOS',
    title: 'Прогресс собирает результаты',
    body: 'Тут видно, что уже сделано, где есть риск и какое действие даст наибольший эффект.',
    route: '/dashboard/operator',
    target: 'nav-progress',
  },
  {
    key: 'progress-overview',
    chapter: 'network-pulse',
    chapterTitle: 'Скрепка LocalOS',
    title: 'Один ясный следующий шаг',
    body: 'Сводка соединяет карты, контент, партнёрства и автоматизацию. Раскройте любой блок и изучите доказательства.',
    route: '/dashboard/progress',
    target: 'progress-overview',
  },
  {
    key: 'card-nav',
    chapter: 'card-content',
    chapterTitle: 'Карточка и контент',
    title: 'Карточка на картах',
    body: 'В этом разделе собраны рейтинг, отзывы, услуги, фото и видимость на картах.',
    route: '/dashboard/progress',
    target: 'nav-card',
  },
  {
    key: 'card-overview',
    chapter: 'card-content',
    chapterTitle: 'Карточка и контент',
    title: 'Данные из нескольких источников',
    body: 'Сводка показывает состояние выбранной точки. Обновление данных в демо заблокировано.',
    route: '/dashboard/card',
    target: 'card-overview',
  },
  {
    key: 'card-services',
    chapter: 'card-content',
    chapterTitle: 'Карточка и контент',
    title: 'Услуги как источник спроса',
    body: 'В «Рогах и копытах» загружена 101 услуга. LocalOS находит дубли, слабые названия и незаполненные описания.',
    route: '/dashboard/card',
    target: 'card-services',
  },
  {
    key: 'content-nav',
    chapter: 'card-content',
    chapterTitle: 'Карточка и контент',
    title: 'Контент проходит через проверку',
    body: 'Календарь хранит темы, черновики и статусы. Публикация всегда остаётся ручным решением.',
    route: '/dashboard/card',
    target: 'nav-content',
  },
  {
    key: 'content-calendar',
    chapter: 'card-content',
    chapterTitle: 'Карточка и контент',
    title: 'Подготовленный контент-план',
    body: 'Откройте ближайший материал и посмотрите, как идея превращается в черновик. Кнопки утверждения в демо не изменяют данные.',
    route: '/dashboard/content',
    target: 'content-calendar',
  },
  {
    key: 'partnership-nav',
    chapter: 'partnership',
    chapterTitle: 'Партнёрство',
    title: 'Партнёрства ведутся по этапам',
    body: 'Кандидаты, отбор, письма, отправка и ответы не смешиваются в один список.',
    route: '/dashboard/content',
    target: 'nav-partnerships',
  },
  {
    key: 'partnership-workspace',
    chapter: 'partnership',
    chapterTitle: 'Партнёрство',
    title: 'От кандидата до диалога',
    body: 'Для демо уже подготовлены партнёры и история кампании. Все исходящие действия заблокированы.',
    route: '/dashboard/partnerships?demo=romashka',
    target: 'partnership-workspace',
  },
  {
    key: 'partnership-candidates',
    chapter: 'partnership',
    chapterTitle: 'Партнёрство',
    title: 'История с «Ромашкой»',
    body: 'Карточка партнёра хранит контекст, предложение, канал связи и следующее действие.',
    route: '/dashboard/partnerships?demo=romashka',
    target: 'partnership-candidates',
  },
  {
    key: 'finish',
    chapter: 'partnership',
    chapterTitle: 'Партнёрство',
    title: 'Маршрут пройден',
    body: 'Теперь можно открыть цифровую комнату «Ромашки» и посмотреть на предложение глазами лида. Или создайте свой аккаунт и загрузите реальный бизнес.',
    route: '/dashboard/partnerships?demo=romashka',
    final: true,
  },
];
