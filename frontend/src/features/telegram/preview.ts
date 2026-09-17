import type { ProgressPayload } from '@/components/telegram/ProgressMobileModule';
import type { TodayPayload } from '@/components/telegram/TodayMobileV2';
import type { Bootstrap,FinanceDashboardMobile,ModuleData,Review } from './types';

export const previewBootstrap: Bootstrap = {
  success: true,
  user: { id: 'preview', name: 'Алексей' },
  today_v2_enabled: true,
  selected_scope: { kind: 'business', id: 'preview', name: 'Весёлая расчёска · Центр', business_ids: ['preview'], can_switch: true, parent_scope: { kind: 'network', id: 'network', name: 'Сеть «Весёлая расчёска»' } },
  summary: {
    attention_items: [
      { id: 'reviews_unanswered', title: '50 отзывов ждут ответа', description: 'ЛокалОС собрал их в одну очередь.', count: 50, severity: 'high' },
      { id: 'drafts', title: '12 черновиков готовы', description: 'Нужно проверить тон и подтвердить.', count: 12, severity: 'medium' },
    ],
    metrics: [
      { key: 'map', label: 'На карте', value: 296, source_label: 'Яндекс Карты', updated_at: new Date().toISOString() },
      { key: 'loaded', label: 'В ЛокалОС', value: 164, source_label: 'Отзывы ЛокалОС', updated_at: new Date().toISOString() },
    ],
  },
  catalog: {
    platform: { kind: 'platform', name: 'Вся платформа' },
    networks: [{ id: 'network', name: 'Сеть «Весёлая расчёска»', locations_count: 2 }],
    businesses: [
      { id: 'preview', name: 'Весёлая расчёска · Центр', address: 'Москва, Тверская, 7', network_id: 'network', network_name: 'Сеть «Весёлая расчёска»' },
      { id: 'preview-2', name: 'Весёлая расчёска · Север', address: 'Москва, Лесная, 4', network_id: 'network', network_name: 'Сеть «Весёлая расчёска»' },
    ], total_choices: 3,
  },
  navigation: [
    { key: 'today', label: 'Сегодня', group: 'primary', status: 'available' },
    { key: 'tasks', label: 'В работе', group: 'primary', status: 'available' },
    { key: 'reviews', label: 'Отзывы', group: 'more', status: 'available' },
    { key: 'operator', label: 'Оператор', group: 'primary', status: 'available' },
    { key: 'progress', label: 'Прогресс', group: 'primary', status: 'available' },
    { key: 'cards', label: 'Карточки', group: 'more', status: 'read_only' },
    { key: 'content', label: 'Контент', group: 'more', status: 'available' },
    { key: 'influencers', label: 'Инфлюенсеры', group: 'more', status: 'available' },
    { key: 'partnerships', label: 'Партнёрства', group: 'more', status: 'available' },
    { key: 'services', label: 'Услуги', group: 'more', status: 'available' },
    { key: 'finance', label: 'Финансы', group: 'more', status: 'available' },
  ],
};

export const previewReviews: Review[] = [
  { id: '1', business_id: 'preview', location_name: 'Весёлая расчёска', source: 'Яндекс', rating: 5, author_name: 'Анна К.', text: 'Очень понравилась стрижка и отношение мастера. Обязательно вернусь!', published_at: new Date().toISOString() },
  { id: '2', business_id: 'preview', location_name: 'Весёлая расчёска', source: '2ГИС', rating: 3, author_name: 'Игорь', text: 'Пришлось ждать почти 20 минут, но результат хороший.', published_at: new Date().toISOString(), reply_draft_text: 'Игорь, спасибо, что поделились. Извините за ожидание.', reply_draft_id: 'd2' },
];

export const previewModules: Record<string, ModuleData> = {
  cards: { items: [{ id: 'preview', title: 'Весёлая расчёска', subtitle: 'Москва, Тверская, 7', status: 'fresh', provider_sources: ['yandex', '2gis'], rating: 4.8, reviews_count: 296, seo_score: 82, parse_updated_at: new Date().toISOString() }] },
  content: { items: [{ id: 'content-1', plan_id: 'plan-preview', title: 'Как выбрать уход после окрашивания', subtitle: 'Черновик ещё не подготовлен', business_name: 'Весёлая расчёска', status: 'planned', plan_title: 'Контент-план · август', scheduled_for: '2026-08-02', content_type: 'news', draft_text: '' }, { id: 'content-2', plan_id: 'plan-preview', title: 'Летнее восстановление волос', subtitle: 'После солнца волосам особенно нужен бережный уход. Подготовили несколько рекомендаций от мастеров.', business_name: 'Весёлая расчёска', status: 'draft_generated', plan_title: 'Контент-план · август', scheduled_for: '2026-08-05', content_type: 'news', draft_text: 'После солнца волосам особенно нужен бережный уход. Подготовили несколько рекомендаций от мастеров.' }] },
  services: { items: [{ id: 'service-1', title: 'Женская стрижка', subtitle: 'Стрижка с консультацией мастера и укладкой.', business_name: 'Весёлая расчёска', status: 'active', price: 'от 2 900 ₽', category: 'Стрижки' }] },
  finance: { items: [{ id: 'finance-1', title: 'Стрижка', amount: 2900, transaction_type: 'income', updated_at: new Date().toISOString() }] },
};

export const previewFinanceDashboard: FinanceDashboardMobile = {
  period: { start_date: '2026-04-01', end_date: '2026-07-24' },
  kpis: { revenue: 10100000, average_ticket: 2961, operating_profit: 3333000, operating_margin: 0.33, workplace_occupancy: 0.702, idle_workplace_hours: 3147, rebooking_rate: 0.389, no_show_rate: 0.047 },
  statuses: { operating_margin: 'green', workplace_occupancy: 'green', rebooking_rate: 'red' },
  data_quality: { score: 100, missing: [], approximate: [], precise: ['выручка', 'расходы', 'загрузка'] },
  recommendations: [{ code: 'rebooking', target_metric: 'rebooking_rate', title: 'Клиенты уходят без следующей записи', text: 'Добавьте мягкое предложение следующего визита перед выходом клиента.', severity: 'high' }],
  action_impact: { completed_actions_count: 0, deltas: [] },
  period_history: [{ label: 'апр.', period_start: '2026-04-01', period_end: '2026-04-30', revenue: 2850000 }, { label: 'май', period_start: '2026-05-01', period_end: '2026-05-31', revenue: 3250000 }, { label: 'июнь', period_start: '2026-06-01', period_end: '2026-06-30', revenue: 3600000 }, { label: 'июль', period_start: '2026-07-01', period_end: '2026-07-24', revenue: 400000 }],
  services: [{ service_name: 'Женская стрижка', category: 'Стрижки', revenue: 420000, visits_count: 42, avg_price: 10000 }],
  staff: [{ staff_name: 'Анна', role: 'Стилист', revenue: 520000, visits_count: 58, occupancy: 0.76 }],
  workplaces: [{ name: 'Кресло 1', type: 'Кресло', revenue: 520000, occupancy: 0.76, idle_hours: 45 }],
};

export const previewToday: TodayPayload = {
  scope: previewBootstrap.selected_scope,
  focus_action: {
    id: 'reviews_unanswered',
    title: 'Ответьте на четыре новых отзыва',
    reason: 'Клиенты уже ждут реакции, а ЛокалОС собрал отзывы в одну очередь.',
    expected_outcome: 'Клиенты увидят, что бизнес внимательно относится к обратной связи.',
    cta_label: 'Открыть отзывы',
    screen: 'reviews',
    count: 4,
  },
  active_work: [{ id: 'work-1', title: 'Обновляет данные карточки', stage: 'Собирает данные Яндекса и 2ГИС', progress: 65, screen: 'cards', business_name: 'Весёлая расчёска' }],
  changes_24h: [{ id: 'change-1', title: 'Загружено новых отзывов: 6', description: 'Отзывы появились в ЛокалОС после последнего сбора данных.', source: 'Отзывы с карт', occurred_at: new Date().toISOString(), screen: 'reviews' }],
  community_pulse: [{ id: 'pulse-1', title: 'Подорожание красителей', description: 'За сутки тема повторилась в 21 сообщении из 3 источников.', message_count: 21, sources_count: 3, source_name: 'Beauty Owners Chat', source_url: 'https://t.me/', last_discussed_at: new Date().toISOString() }],
  completed_results: [{ id: 'result-1', title: 'Подготовлено два черновика публикаций', description: 'Тексты готовы к проверке — публикации ещё не выполнялись.', source: 'Контент ЛокалОС', occurred_at: new Date().toISOString(), screen: 'content' }],
  progress_summary: { completed_milestones: 7, total_milestones: 15, percent: 47 },
  as_of: new Date().toISOString(),
};

export const previewProgress: ProgressPayload = {
  status: 'available',
  focus_action: previewToday.focus_action,
  summary: { completed_milestones: 7, total_milestones: 15, active_areas: 4, needs_attention: 2, completed_last_30_days: 5, percent: 47 },
  areas: [
    { key: 'maps', label: 'Карты и репутация', status: 'needs_attention', summary: 'Карточка обновляется, новые отзывы ждут ответа.', problem: 'Без ответа осталось четыре отзыва.', progress: { completed: 3, total: 4 }, milestones: [{ key: 'map-linked', label: 'Карточка подключена', status: 'done', evidence: 'Яндекс и 2ГИС доступны ЛокалОС.' }, { key: 'reviews', label: 'Ответить на новые отзывы', status: 'next' }], action: { cta_label: 'Открыть отзывы', screen: 'reviews' } },
    { key: 'content', label: 'Контент', status: 'in_progress', summary: 'План создан, два черновика готовы.', progress: { completed: 2, total: 3 }, milestones: [{ key: 'plan', label: 'Контент-план создан', status: 'done' }, { key: 'publish', label: 'Подтвердить первую публикацию', status: 'next' }], action: { cta_label: 'Открыть контент', screen: 'content' } },
  ],
};
