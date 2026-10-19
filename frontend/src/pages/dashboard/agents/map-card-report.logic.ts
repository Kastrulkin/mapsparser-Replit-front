const object = (value: unknown): Record<string, unknown> | null => value && typeof value === 'object' && !Array.isArray(value) ? Object.fromEntries(Object.entries(value)) : null;
export const mapRows = (value: unknown): Record<string, unknown>[] => Array.isArray(value) ? value.map(object).filter((row) => row !== null) : [];
export const mapFieldLabels: Record<string, string> = {
  name: 'Название', title: 'Название', address: 'Адрес', phone: 'Телефон', website: 'Сайт', schedule: 'Часы работы', working_hours: 'Часы работы',
  description: 'Описание', category: 'Рубрика', contacts: 'Контакты', access: 'Доступ к данным', verified: 'Подтверждение компании', duplicate: 'Дубли карточки',
  services: 'Услуги', prices: 'Цены', reviews: 'Отзывы', review_responses: 'Ответы на отзывы', photos: 'Фотографии', publications: 'Публикации', action_path: 'Путь до обращения',
  count: 'Количество', total: 'Всего', rating: 'Рейтинг', value: 'Значение', text: 'Текст',
};
export const mapValue = (value: unknown): string => {
  if (value === null || value === undefined || value === '') return 'Нет подтверждённых данных';
  if (typeof value === 'string' || typeof value === 'number') return String(value);
  if (typeof value === 'boolean') return value ? 'Да' : 'Нет';
  if (Array.isArray(value)) {
    const items = value.filter((item) => typeof item === 'string' || typeof item === 'number').slice(0, 8);
    return items.length ? items.map(String).join(', ') : 'Нужна дополнительная проверка';
  }
  const row = object(value) || {};
  const values = Object.entries(row).filter(([key, item]) => mapFieldLabels[key] && ['string', 'number', 'boolean'].includes(typeof item));
  return values.length ? values.map(([key, item]) => `${mapFieldLabels[key]}: ${mapValue(item)}`).join('\n') : 'Нужна дополнительная проверка';
};
export const mapDate = (value: unknown): string => {
  if (typeof value !== 'string' || !value) return 'дата не указана';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 'дата не указана' : new Intl.DateTimeFormat('ru-RU', { dateStyle: 'short', timeStyle: 'short', timeZone: 'Europe/Moscow' }).format(date)+' МСК';
};
export const mapPublicLink = (value: unknown): string => {
  if (typeof value !== 'string') return '';
  try { const url = new URL(value); return url.protocol === 'https:' && !url.username && !url.password ? url.href : ''; } catch { return ''; }
};
export const getMapCardReport = (value: unknown): Record<string, unknown> | null => {
  let row = object(value);
  for (let depth = 0; row && depth < 4; depth += 1) {
    if (row.schema === 'map_card_report_v1') return row;
    const cards = mapRows(row.cards);
    const legacy = cards.some((card) => ['google', 'yandex', '2gis'].includes(String(card.provider)) && (Array.isArray(card.checks) || Array.isArray(card.fields)));
    if (legacy) return { ...row, schema: 'map_card_report_v1', legacy_report: true,
      kind: row.kind || (cards.some((card) => Array.isArray(card.fields) && card.fields.length) ? 'preparation' : 'check') };
    row = object(row.result) || object(row.artifact);
  }
  return null;
};
