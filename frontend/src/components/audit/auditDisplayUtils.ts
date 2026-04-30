export type AuditDataScope =
  | 'network'
  | 'location'
  | 'sample'
  | 'current_snapshot'
  | 'detailed_analysis'
  | 'limited'
  | 'model_estimate';

const isFiniteNumber = (value: unknown): value is number =>
  typeof value === 'number' && Number.isFinite(value);

const toNumber = (value: unknown): number | null => {
  if (isFiniteNumber(value)) return value;
  if (typeof value === 'string' && value.trim() !== '') {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
};

export const formatAuditNumber = (
  value: unknown,
  options: { locale?: string; maximumFractionDigits?: number; minimumFractionDigits?: number } = {},
): string => {
  const numberValue = toNumber(value);
  if (numberValue === null) return '—';
  return new Intl.NumberFormat(options.locale || 'ru-RU', {
    maximumFractionDigits: options.maximumFractionDigits ?? 0,
    minimumFractionDigits: options.minimumFractionDigits ?? 0,
  }).format(numberValue);
};

export const formatAuditRating = (value: unknown, locale = 'ru-RU'): string => {
  const numberValue = toNumber(value);
  if (numberValue === null) return '—';
  return new Intl.NumberFormat(locale, {
    minimumFractionDigits: numberValue % 1 === 0 ? 0 : 1,
    maximumFractionDigits: 2,
  }).format(numberValue);
};

export const formatAuditScore = (value: unknown, locale = 'ru-RU'): string =>
  formatAuditNumber(value, { locale, maximumFractionDigits: 0 });

export const formatAuditPercent = (value: unknown, locale = 'ru-RU'): string => {
  const numberValue = toNumber(value);
  if (numberValue === null) return '—';
  return `${new Intl.NumberFormat(locale, { maximumFractionDigits: 1 }).format(numberValue)}%`;
};

export const formatAuditMoney = (value: unknown, locale = 'ru-RU'): string => {
  const numberValue = toNumber(value);
  if (numberValue === null) return '—';
  return `${new Intl.NumberFormat(locale, { maximumFractionDigits: 0 }).format(Math.round(numberValue))} ₽`;
};

export const formatAuditMoneyRange = (min: unknown, max: unknown, locale = 'ru-RU'): string => {
  const minValue = toNumber(min);
  const maxValue = toNumber(max);
  if (minValue === null && maxValue === null) return '—';
  if (minValue !== null && maxValue !== null) return `${formatAuditMoney(minValue, locale)} — ${formatAuditMoney(maxValue, locale)}`;
  return formatAuditMoney(minValue ?? maxValue, locale);
};

export const auditScopeLabel = (scope?: AuditDataScope): string => {
  switch (scope) {
    case 'network':
      return 'Вся сеть';
    case 'location':
      return 'Одна точка';
    case 'sample':
      return 'Выборка';
    case 'current_snapshot':
      return 'Текущий срез';
    case 'detailed_analysis':
      return 'Детальный анализ';
    case 'limited':
      return 'Данные ограничены';
    case 'model_estimate':
      return 'Модельная оценка';
    default:
      return 'Источник данных';
  }
};

export const auditScoreBusinessLabel = (score: unknown, fallback?: string): string => {
  const numberValue = toNumber(score);
  if (numberValue === null) return fallback || 'Оценка будет понятнее после обновления данных.';
  if (numberValue >= 80) return 'Сильная база: важно поддерживать регулярность и не терять накопленное доверие.';
  if (numberValue >= 55) return 'Рабочая база, но часть спроса и доверия теряется из-за неравномерного ведения карточки.';
  return 'Карточка заметно теряет доверие и локальный спрос: сначала стоит закрыть базовые проблемы.';
};

export const localosOperationalHelp =
  'LocalOS может взять это в регулярную работу: обновлять карточки, готовить ответы и публикации, подсвечивать приоритеты и контролировать изменения без ручной проверки всего отчёта.';

export const compactAuditText = (value: unknown, fallback = 'Данных пока недостаточно.'): string => {
  if (typeof value !== 'string') return fallback;
  const trimmed = value.trim();
  return trimmed || fallback;
};
