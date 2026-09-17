
export const providerName = (value: string) => value.includes('2gis') || value.includes('two') || value.includes('2_gis') ? '2ГИС' : value.includes('yandex') ? 'Яндекс' : value;

export const dateLabel = (value?: string) => {
  if (!value) return 'дата неизвестна';
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? 'дата неизвестна'
    : date.toLocaleString('ru-RU', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
};

export const isPreview = () => ['localhost', '127.0.0.1'].includes(window.location.hostname) && new URLSearchParams(window.location.search).get('preview') === '1';
