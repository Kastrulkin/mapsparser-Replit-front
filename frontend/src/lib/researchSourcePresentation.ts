export interface ResearchSourcePresentationInput {
  title?: string;
  url?: string;
  source_type?: string;
}

export interface ResearchSourcePresentation {
  destination: string;
  context: string;
}

const normalizedSourceType = (value?: string) => String(value || '')
  .trim()
  .toLowerCase()
  .replace(/[^a-z0-9]+/g, '_');

const sourceHost = (value?: string) => {
  try {
    return new URL(String(value || '')).hostname.replace(/^www\./, '');
  } catch {
    return '';
  }
};

const sourcePathParts = (value?: string) => {
  try {
    return new URL(String(value || '')).pathname.split('/').filter(Boolean);
  } catch {
    return [];
  }
};

const destinationFromHost = (host: string, sourceType: string) => {
  if (host === 't.me' || host.endsWith('.t.me')) return 'Публичный Telegram-канал';
  if (host === 'vk.com' || host === 'vk.ru' || host.endsWith('.vk.com') || host.endsWith('.vk.ru')) {
    return 'Страница или сообщество ВКонтакте';
  }
  if (host.includes('instagram.com')) return 'Профиль Instagram';
  if (host.includes('yandex.') && host.includes('maps')) return 'Карточка на Яндекс Картах';
  if (host === 'yandex.ru' || host.endsWith('.yandex.ru')) return 'Карточка на Яндекс Картах';
  if (host === '2gis.ru' || host.endsWith('.2gis.ru')) return 'Карточка в 2ГИС';
  if (host.includes('google.') && sourceType.includes('map')) return 'Карточка на Google Картах';
  if (host === 'localos.pro' || host.endsWith('.localos.pro')) return 'Аудит LocalOS';
  return '';
};

const destinationFromType = (sourceType: string) => {
  if (sourceType.includes('review')) return 'Отзывы в карточке на картах';
  if (sourceType.includes('service_catalog')) return 'Услуги и цены в карточке на картах';
  if (sourceType.includes('audit')) return 'Аудит LocalOS';
  if (sourceType.includes('map') || sourceType === 'public_business_card') return 'Карточка компании на картах';
  if (sourceType.includes('telegram')) return 'Публичный Telegram-канал';
  if (sourceType.includes('social')) return 'Публичная социальная сеть';
  if (sourceType.includes('website') || sourceType === 'public_web') return 'Официальный сайт';
  if (sourceType === 'operator_input' || sourceType === 'operator_approved_partnership_reason') {
    return 'Причина, подтверждённая вручную';
  }
  return '';
};

export const researchSourcePresentation = (
  source: ResearchSourcePresentationInput,
): ResearchSourcePresentation => {
  const sourceType = normalizedSourceType(source.source_type);
  const host = sourceHost(source.url);
  const pathParts = sourcePathParts(source.url);
  const typedDestination = destinationFromType(sourceType);
  const directTelegramPost = host === 't.me' && pathParts.length >= 2;
  const hostedDestination = directTelegramPost
    ? 'Публикация в Telegram'
    : destinationFromHost(host, sourceType);
  const genericWebType = ['', 'public_source', 'public_web', 'official_website'].includes(sourceType);
  const destination = (directTelegramPost
    ? hostedDestination
    : genericWebType
      ? hostedDestination || typedDestination
      : typedDestination || hostedDestination)
    || (host ? `Веб-страница на ${host}` : 'Публичный источник');
  const title = String(source.title || '').trim();
  const contextParts = [title, host].filter((item, index, items) => item && items.indexOf(item) === index);

  return {
    destination,
    context: contextParts.join(' · ') || 'Откроется в новой вкладке',
  };
};
