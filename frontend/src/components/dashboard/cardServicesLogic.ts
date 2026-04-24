type ServiceLike = {
  source?: string;
  keywords?: string[] | string;
  updated_at?: string | null;
};

export const normalizeServiceText = (value: string) =>
  String(value || '')
    .toLowerCase()
    .replace(/ё/g, 'е')
    .replace(/[^\p{L}\p{N}\s]/gu, ' ')
    .replace(/\s+/g, ' ')
    .trim();

export const getServiceKeywordList = (service: ServiceLike): string[] => {
  const rawKeywords = service?.keywords;
  const flattened: string[] = [];

  const appendKeyword = (value: unknown) => {
    const keyword = String(value || '').trim();
    if (keyword) {
      flattened.push(keyword);
    }
  };

  if (Array.isArray(rawKeywords)) {
    rawKeywords.forEach((item: unknown) => {
      if (Array.isArray(item)) {
        item.forEach(appendKeyword);
        return;
      }
      if (typeof item === 'string') {
        const trimmed = item.trim();
        if (!trimmed) return;
        if (trimmed.startsWith('[') && trimmed.endsWith(']')) {
          try {
            const parsed = JSON.parse(trimmed);
            if (Array.isArray(parsed)) {
              parsed.forEach(appendKeyword);
              return;
            }
          } catch {
          }
        }
        appendKeyword(trimmed);
        return;
      }
      appendKeyword(item);
    });
  } else if (typeof rawKeywords === 'string') {
    const trimmed = rawKeywords.trim();
    if (trimmed) {
      if (trimmed.startsWith('[') && trimmed.endsWith(']')) {
        try {
          const parsed = JSON.parse(trimmed);
          if (Array.isArray(parsed)) {
            parsed.forEach(appendKeyword);
          } else {
            appendKeyword(trimmed);
          }
        } catch {
          appendKeyword(trimmed);
        }
      } else {
        appendKeyword(trimmed);
      }
    }
  }

  return Array.from(new Set(flattened.map((item) => item.trim()).filter(Boolean)));
};

export const isDraftSimilarToCurrent = (draft: string, current: string) => {
  const normalizedDraft = normalizeServiceText(draft);
  const normalizedCurrent = normalizeServiceText(current);
  if (!normalizedDraft || !normalizedCurrent) return false;
  return normalizedDraft === normalizedCurrent;
};

export const getMatchedKeywords = (draft: string, service: ServiceLike): string[] => {
  const normalizedDraft = normalizeServiceText(draft);
  if (!normalizedDraft) return [];
  return getServiceKeywordList(service).filter((keyword) => {
    const normalizedKeyword = normalizeServiceText(keyword);
    return normalizedKeyword.length >= 3 && normalizedDraft.includes(normalizedKeyword);
  });
};

export const formatServiceSource = (service: ServiceLike) => {
  const source = String(service?.source || '').trim().toLowerCase();
  if (!source) return 'Ручная';
  if (source === 'yandex_maps') return 'Яндекс Карты';
  if (source === 'yandex_business') return 'Яндекс Бизнес';
  if (source === '2gis') return '2ГИС';
  if (source === 'google_maps' || source === 'google_business') return 'Google Maps';
  if (source === 'apple_maps' || source === 'apple_business') return 'Apple Maps';
  if (source === 'external') return 'Внешняя';
  if (source === 'file_import') return 'Из файла';
  return source.replace(/_/g, ' ');
};

export const formatMapSourceTab = (source: string) => {
  const normalized = String(source || '').trim().toLowerCase();
  if (normalized === 'yandex') return 'Яндекс';
  if (normalized === '2gis') return '2ГИС';
  if (normalized === 'google') return 'Google';
  if (normalized === 'apple') return 'Apple';
  return source;
};

export const getDisplayedServiceUpdatedAt = (
  service: ServiceLike,
  servicesLastParseDate: string | null,
  lastParseDate: string | null,
  servicesNoNewFromParse: boolean,
) => {
  const latest = servicesLastParseDate || lastParseDate;
  const source = String(service?.source || '').trim().toLowerCase();
  if (servicesNoNewFromParse && latest && !source) {
    return latest;
  }
  return service?.updated_at || null;
};
