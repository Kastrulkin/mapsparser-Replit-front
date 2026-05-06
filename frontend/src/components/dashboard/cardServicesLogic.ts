type ServiceLike = {
  source?: string;
  keywords?: string[] | string;
  updated_at?: string | null;
};

export type KeywordMatchLevel = 'exact' | 'normalized' | 'close';

export type KeywordMatch = {
  keyword: string;
  level: KeywordMatchLevel;
};

export type KeywordScore = {
  status: 'ok' | 'partial' | 'no_keywords';
  total: number;
  found: number;
  missingCount: number;
  coverage: number;
  exactCount: number;
  normalizedCount: number;
  closeCount: number;
  matches: KeywordMatch[];
  missing: string[];
  added: string[];
  weak: string[];
};

export type ServiceQuality = {
  status: 'good' | 'needs_review' | 'manual_review';
  needsReview: boolean;
  manualReview: boolean;
  issueCodes: string[];
  issueLabels: string[];
  keywordScore: KeywordScore;
};

export type ServicesQualityAudit = {
  summary: {
    total: number;
    good: number;
    needsReview: number;
    manualReview: number;
    fallback: number;
    missingKeywords: number;
    weakMatchesOnly: number;
    guardrailFailed: number;
    noKeywords: number;
  };
  items: Array<ServiceQuality & { serviceId: string; name: string }>;
  telegramSummary: string;
};

const createKeywordMatch = (keyword: string, level: KeywordMatchLevel): KeywordMatch => ({
  keyword,
  level,
});

export const normalizeServiceText = (value: string) =>
  String(value || '')
    .toLowerCase()
    .replace(/ё/g, 'е')
    .replace(/[^\p{L}\p{N}\s]/gu, ' ')
    .replace(/\s+/g, ' ')
    .trim();

const normalizeKeywordToken = (value: string) => {
  const token = normalizeServiceText(value);
  if (token.length <= 4) return token;
  return token
    .replace(/(иями|ями|ами|его|ому|ыми|ими|ая|яя|ое|ее|ый|ий|ой|ых|их|ую|юю|ого|ему|ам|ям|ах|ях|ов|ев|ей|ой|ом|ем|ой|ою|ею|ы|и|а|я|о|е|у|ю)$/u, '')
    .replace(/(ическ|ичес|ическа)$/u, '');
};

const tokenizeKeywordText = (value: string) =>
  normalizeServiceText(value)
    .split(' ')
    .map(normalizeKeywordToken)
    .filter((token) => token.length >= 3);

const BEAUTY_CLOSE_GROUPS: string[][] = [
  ['ваксинг', 'восковая депиляция', 'депиляция воском'],
  ['афро', 'афрокудри', 'афро кудри'],
  ['брови', 'бровей', 'бровная коррекция'],
  ['ресницы', 'ресниц'],
  ['биозавивка', 'завивка'],
  ['косметология', 'косметологическая процедура'],
  ['инъекции', 'инъекционная косметология'],
  ['детская', 'для детей', 'ребенок', 'ребёнок', 'дети'],
  ['макияж', 'визаж'],
  ['эпиляция', 'лазерная эпиляция'],
  ['перманент', 'татуаж', 'пудровое напыление', 'перманентный макияж'],
  ['маникюр', 'ногти', 'покрытие ногтей', 'покрытие'],
  ['педикюр', 'стопы', 'ногти на ногах'],
  ['ботокс', 'ботулинотерапия', 'ботулинический токсин'],
  ['чистка лица', 'уход за лицом', 'пилинг', 'уход'],
  ['ламинирование', 'долговременная укладка'],
];

const getCloseGroupTokens = (keyword: string) => {
  const normalizedKeyword = normalizeServiceText(keyword);
  const keywordTokens = tokenizeKeywordText(keyword);
  return BEAUTY_CLOSE_GROUPS
    .filter((group) => group.some((item) => {
      const normalizedItem = normalizeServiceText(item);
      const itemTokens = tokenizeKeywordText(item);
      return normalizedKeyword.includes(normalizedItem)
        || normalizedItem.includes(normalizedKeyword)
        || itemTokens.some((token) => keywordTokens.includes(token));
    }))
    .flatMap((group) => group.flatMap(tokenizeKeywordText));
};

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
  return getKeywordMatches(draft, service).map((match) => match.keyword);
};

export const getKeywordScore = (
  draft: string,
  service: ServiceLike,
  sourceText = '',
): KeywordScore => {
  const keywords = getServiceKeywordList(service);
  const matches = getKeywordMatches(draft, service);
  const matchedKeywords = new Set(matches.map((match) => match.keyword));
  const missing = keywords.filter((keyword) => !matchedKeywords.has(keyword));
  const added = sourceText
    ? matches
      .filter((match) => {
        const sourceMatch = getKeywordMatches(sourceText, { keywords: [match.keyword] })[0];
        return !sourceMatch || sourceMatch.level === 'close';
      })
      .map((match) => match.keyword)
    : [];
  const weak = matches.filter((match) => match.level === 'close').map((match) => match.keyword);
  const total = keywords.length;
  const found = matches.length;

  return {
    status: total === 0 ? 'no_keywords' : missing.length > 0 ? 'partial' : 'ok',
    total,
    found,
    missingCount: missing.length,
    coverage: total > 0 ? Math.round((found / total) * 100) / 100 : 0,
    exactCount: matches.filter((match) => match.level === 'exact').length,
    normalizedCount: matches.filter((match) => match.level === 'normalized').length,
    closeCount: matches.filter((match) => match.level === 'close').length,
    matches,
    missing,
    added,
    weak,
  };
};

export const getKeywordMatches = (draft: string, service: ServiceLike): KeywordMatch[] => {
  const normalizedDraft = normalizeServiceText(draft);
  if (!normalizedDraft) return [];
  const draftTokens = tokenizeKeywordText(draft);
  return getServiceKeywordList(service).flatMap((keyword) => {
    const normalizedKeyword = normalizeServiceText(keyword);
    if (normalizedKeyword.length < 3) return [];
    if (normalizedDraft.includes(normalizedKeyword)) {
      return [createKeywordMatch(keyword, 'exact')];
    }

    const keywordTokens = tokenizeKeywordText(keyword);
    if (
      keywordTokens.length > 0
      && keywordTokens.every((token) => draftTokens.includes(token))
    ) {
      return [createKeywordMatch(keyword, 'normalized')];
    }

    const closeTokens = getCloseGroupTokens(keyword);
    if (closeTokens.some((token) => draftTokens.includes(token))) {
      if (normalizedKeyword === 'педикюр' && normalizedDraft.includes('маникюр')) {
        return [];
      }
      return [createKeywordMatch(keyword, 'close')];
    }

    return [];
  });
};

const normalizeGuardrailReasons = (value: unknown): string[] => {
  if (Array.isArray(value)) {
    return value.map((item) => String(item || '').trim()).filter(Boolean);
  }
  const trimmed = String(value || '').trim();
  if (!trimmed) return [];
  if (trimmed.startsWith('[') && trimmed.endsWith(']')) {
    try {
      const parsed = JSON.parse(trimmed);
      if (Array.isArray(parsed)) {
        return parsed.map((item) => String(item || '').trim()).filter(Boolean);
      }
    } catch {
    }
  }
  return [trimmed];
};

export const getServiceQuality = (service: ServiceLike & {
  id?: string;
  name?: string;
  description?: string;
  optimized_name?: string;
  optimized_description?: string;
  fallback_used?: boolean;
  guardrail_reasons?: string[] | string;
  regeneration_status?: string;
}): ServiceQuality => {
  const name = String(service.name || '').trim();
  const description = String(service.description || '').trim();
  const optimizedName = String(service.optimized_name || '').trim();
  const optimizedDescription = String(service.optimized_description || '').trim();
  const score = getKeywordScore(`${optimizedName} ${optimizedDescription}`, service, `${name} ${description}`);
  const guardrailReasons = normalizeGuardrailReasons(service.guardrail_reasons);
  const manualReview = String(service.regeneration_status || '').trim().toLowerCase() === 'manual_review';
  const issueCodes: string[] = [];
  const issueLabels: string[] = [];

  const addIssue = (code: string, label: string) => {
    if (!issueCodes.includes(code)) issueCodes.push(code);
    if (!issueLabels.includes(label)) issueLabels.push(label);
  };

  if (score.total === 0) addIssue('no_keywords', 'нет SEO-ключей');
  if (score.missing.length > 0) addIssue('missing_keywords', `потерян ключ: ${score.missing.slice(0, 3).join(', ')}`);
  if (score.found > 0 && score.found === score.closeCount) addIssue('weak_matches_only', 'только близкое совпадение');
  if (optimizedDescription && normalizeServiceText(optimizedDescription).includes('услуга по исходному формату записи')) addIssue('fallback_description', 'fallback-описание');
  if (service.fallback_used) addIssue('fallback_used', 'fallback после guardrails');
  if (guardrailReasons.length > 0) addIssue('guardrail_reasons', `сработали guardrails: ${guardrailReasons.slice(0, 2).join(', ')}`);
  if (optimizedName && name && isDraftSimilarToCurrent(optimizedName, name)) addIssue('name_unchanged', 'название почти не изменилось');
  if (optimizedDescription && description && isDraftSimilarToCurrent(optimizedDescription, description)) addIssue('description_unchanged', 'описание почти не изменилось');
  if (!optimizedName && !optimizedDescription) addIssue('no_suggestion', 'нет SEO-предложения');
  if (manualReview) addIssue('manual_review', 'нужна ручная проверка');

  return {
    status: manualReview ? 'manual_review' : issueCodes.length > 0 ? 'needs_review' : 'good',
    needsReview: !manualReview && issueCodes.length > 0,
    manualReview,
    issueCodes,
    issueLabels,
    keywordScore: score,
  };
};

export const buildServicesQualityAudit = (
  services: Array<ServiceLike & {
    id?: string;
    name?: string;
    description?: string;
    optimized_name?: string;
    optimized_description?: string;
    fallback_used?: boolean;
    guardrail_reasons?: string[] | string;
    regeneration_status?: string;
  }>,
): ServicesQualityAudit => {
  const items = services.map((service) => ({
    serviceId: String(service.id || ''),
    name: String(service.name || ''),
    ...getServiceQuality(service),
  }));
  const fallback = items.filter((item) => item.issueCodes.includes('fallback_used') || item.issueCodes.includes('fallback_description')).length;
  const summary = {
    total: items.length,
    good: items.filter((item) => item.status === 'good').length,
    needsReview: items.filter((item) => item.needsReview).length,
    manualReview: items.filter((item) => item.manualReview).length,
    fallback,
    missingKeywords: items.filter((item) => item.issueCodes.includes('missing_keywords')).length,
    weakMatchesOnly: items.filter((item) => item.issueCodes.includes('weak_matches_only')).length,
    guardrailFailed: items.filter((item) => item.issueCodes.includes('guardrail_reasons')).length,
    noKeywords: items.filter((item) => item.issueCodes.includes('no_keywords')).length,
  };
  return {
    summary,
    items,
    telegramSummary: [
      `Проверено ${summary.total} услуг`,
      `ОК: ${summary.good}`,
      `Требуют доработки: ${summary.needsReview}`,
      `Нужна ручная проверка: ${summary.manualReview}`,
      `Потеряны SEO-ключи: ${summary.missingKeywords}`,
      `Fallback: ${summary.fallback}`,
    ].join('\n'),
  };
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
