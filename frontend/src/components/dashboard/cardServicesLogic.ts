export type ServiceLike = {
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

export type ServiceCatalogCompressionGroup = {
  id: string;
  title: string;
  currentCount: number;
  recommendedCount: number;
  reason: string;
  action: string;
  examples: string[];
};

export type ServiceCatalogCompressionSuggestion = {
  beforeCount: number;
  estimatedAfterCount: number;
  highPriority: boolean;
  categoryCounts: Array<{ category: string; count: number }>;
  summary: string;
  groups: ServiceCatalogCompressionGroup[];
  generalRecommendations: string[];
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
  fallback_reason?: string;
  guardrail_reasons?: string[] | string;
  pattern_version_ids?: string[] | string;
  regeneration_status?: string;
}): ServiceQuality => {
  const name = String(service.name || '').trim();
  const description = String(service.description || '').trim();
  const optimizedName = String(service.optimized_name || '').trim();
  const optimizedDescription = String(service.optimized_description || '').trim();
  const sourceText = `${name} ${description}`.trim();
  const hasOptimizationDraft = Boolean(optimizedName || optimizedDescription);
  const draftText = hasOptimizationDraft ? `${optimizedName} ${optimizedDescription}`.trim() : sourceText;
  const score = getKeywordScore(draftText, service, sourceText);
  const guardrailReasons = normalizeGuardrailReasons(service.guardrail_reasons);
  const manualReview = String(service.regeneration_status || '').trim().toLowerCase() === 'manual_review';
  const issueCodes: string[] = [];
  const issueLabels: string[] = [];

  const addIssue = (code: string, label: string) => {
    if (!issueCodes.includes(code)) issueCodes.push(code);
    if (!issueLabels.includes(label)) issueLabels.push(label);
  };

  if (score.total === 0) addIssue('no_keywords', 'нет SEO-запросов для проверки');
  if (score.missing.length > 0) addIssue('missing_keywords', `не хватает запроса: ${score.missing.slice(0, 3).join(', ')}`);
  if (score.found > 0 && score.found === score.closeCount) addIssue('weak_matches_only', 'запрос использован слишком неточно');
  if (optimizedDescription && normalizeServiceText(optimizedDescription).includes('услуга по исходному формату записи')) addIssue('fallback_description', 'описание выглядит шаблонно');
  if (service.fallback_used) {
    const fallbackReason = String(service.fallback_reason || '').trim();
    addIssue('fallback_used', fallbackReason ? `fallback: ${fallbackReason}` : 'описание нужно переписать точнее');
  }
  if (guardrailReasons.length > 0) addIssue('guardrail_reasons', 'нужна проверка смысла и обещаний');
  const descriptionUnchanged = Boolean(hasOptimizationDraft && optimizedDescription && description && isDraftSimilarToCurrent(optimizedDescription, description));
  const nameUnchanged = Boolean(hasOptimizationDraft && optimizedName && name && isDraftSimilarToCurrent(optimizedName, name));
  if (nameUnchanged && (!optimizedDescription || Boolean(service.fallback_used) || descriptionUnchanged)) addIssue('name_unchanged', 'название почти не изменилось');
  if (descriptionUnchanged) addIssue('description_unchanged', 'описание почти не изменилось');
  if (!hasOptimizationDraft && !sourceText) addIssue('no_suggestion', 'нет SEO-предложения');
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
      `Не хватает важных запросов: ${summary.missingKeywords}`,
      `Шаблонные описания: ${summary.fallback}`,
    ].join('\n'),
  };
};

type CompressionServiceLike = ServiceLike & {
  id?: string;
  category?: string;
  name?: string;
  description?: string;
  price?: string | number | null;
};

const SERVICE_CATALOG_GENERAL_RECOMMENDATIONS = [
  'Сократите список до понятных клиенту направлений, а варианты оставьте внутри описания: зона, длина, пол, объём препарата, размер рубца.',
  'Не держите акции как обычные услуги: сезонные предложения лучше вынести в новости, акции или выделенные блоки.',
  'Для SEO оставляйте отдельными только услуги, которые клиент реально ищет как самостоятельный запрос.',
  'Внутри категории показывайте 5-12 ключевых позиций, остальное группируйте как варианты.',
  'Цены лучше показывать диапазоном или таблицей вариантов, а не десятками почти одинаковых строк.',
];

const SERVICE_CATALOG_COMPRESSION_RULES: Array<{
  id: string;
  title: string;
  pattern: RegExp;
  recommendedCount: number;
  reason: string;
  action: string;
}> = [
  {
    id: 'laser_epilation',
    title: 'Лазерная эпиляция',
    pattern: /эпиляц|бикини|подмыш|голен|бедр|ноги|руки|усики|ареол|пальц|зона mini|тотальное/iu,
    recommendedCount: 8,
    reason: 'Много строк отличаются только зоной, полом клиента или размером комплекса.',
    action: 'Свернуть в группы по зонам и добавить варианты “женщины/мужчины” внутри услуги.',
  },
  {
    id: 'injectable_cosmetology',
    title: 'Инъекционная косметология',
    pattern: /биоревитализац|ботулинотерап|токсин|гипергидроз|коллагенотерап|collost|контурная пластика|филлер|мезотерап|belarti|bellarti|revi|plinest|meso/iu,
    recommendedCount: 12,
    reason: 'Часть строк описывает одну процедуру разными препаратами или объёмами.',
    action: 'Оставить семьи процедур, а препараты и ml вынести в варианты или описание.',
  },
  {
    id: 'seasonal_offers',
    title: 'Сезонные предложения',
    pattern: /сезонное\s+предложение/iu,
    recommendedCount: 3,
    reason: 'Акционные формулировки смешаны с постоянным меню услуг.',
    action: 'Вынести сезонные позиции в акции, новости или выделенные предложения.',
  },
  {
    id: 'hair_services',
    title: 'Волосы: завивка, окрашивание, уходы и дети',
    pattern: /биозавив|афро|окрашив|балаяж|шатуш|air touch|эйр|блонд|тонирован|контуринг|выход из темного|выход из тёмного|биксипласт|ботокс для волос|кератин|счастье для волос|уход за волос|детск|стрижка/iu,
    recommendedCount: 14,
    reason: 'Строки дробятся по длине волос, возрасту или сложности.',
    action: 'Объединить по базовой услуге, а длину, возраст и сложность показать как варианты.',
  },
  {
    id: 'scar_aesthetics',
    title: 'Эстетика рубцов',
    pattern: /рубц|растяж|стрии|абдоминопласт|блефаропласт|брахиопласт|хейлопласт|ареол/iu,
    recommendedCount: 6,
    reason: 'Похожие процедуры отличаются размером зоны или типом рубца.',
    action: 'Сгруппировать по типу процедуры и размеру рубца.',
  },
  {
    id: 'permanent_makeup',
    title: 'Перманентный макияж',
    pattern: /перманент|пудров|межреснич|стрелк|татуаж|ремувер|акварель|помада/iu,
    recommendedCount: 6,
    reason: 'Позиции можно понятнее собрать по зоне и технике.',
    action: 'Группировать по зонам: брови, губы, веки, коррекция и удаление.',
  },
  {
    id: 'podology',
    title: 'Подология и ногтевой сервис',
    pattern: /подолог|стоп|вросш|ногт|титанов|биоматериал|педикюр|маникюр|мозол|гиперкератоз/iu,
    recommendedCount: 8,
    reason: 'Медицинские и обычные ногтевые услуги смешаны в одном списке.',
    action: 'Отделить подологию от маникюра/педикюра и сгруппировать лечебные варианты.',
  },
];

const compressionServiceText = (service: CompressionServiceLike) =>
  `${service.category || ''} ${service.name || ''} ${service.description || ''}`;

const compressionServiceName = (service: CompressionServiceLike) =>
  String(service.name || '').trim();

export const buildServiceCatalogCompressionSuggestion = (
  services: CompressionServiceLike[],
): ServiceCatalogCompressionSuggestion => {
  const activeServices = Array.isArray(services) ? services : [];
  const beforeCount = activeServices.length;
  const categoryCounter = new Map<string, number>();

  activeServices.forEach((service) => {
    const category = String(service.category || 'Без категории').trim() || 'Без категории';
    categoryCounter.set(category, (categoryCounter.get(category) || 0) + 1);
  });

  const categoryCounts = Array.from(categoryCounter.entries())
    .map(([category, count]) => ({ category, count }))
    .sort((left, right) => right.count - left.count || left.category.localeCompare(right.category));

  const usedNames = new Set<string>();
  const groups = SERVICE_CATALOG_COMPRESSION_RULES.map((rule) => {
    const matches = activeServices.filter((service) => rule.pattern.test(compressionServiceText(service)));
    const examples = matches
      .map(compressionServiceName)
      .filter((name) => {
        const normalized = normalizeServiceText(name);
        if (!normalized || usedNames.has(`${rule.id}:${normalized}`)) return false;
        usedNames.add(`${rule.id}:${normalized}`);
        return true;
      })
      .slice(0, 4);

    return {
      id: rule.id,
      title: rule.title,
      currentCount: matches.length,
      recommendedCount: Math.min(rule.recommendedCount, Math.max(1, matches.length)),
      reason: rule.reason,
      action: rule.action,
      examples,
    };
  }).filter((group) => group.currentCount >= 3);

  categoryCounts
    .filter((item) => item.count > 25)
    .forEach((item) => {
      if (groups.some((group) => normalizeServiceText(group.title) === normalizeServiceText(item.category))) {
        return;
      }
      groups.push({
        id: `category_${normalizeServiceText(item.category).replace(/\s+/g, '_')}`,
        title: item.category,
        currentCount: item.count,
        recommendedCount: 12,
        reason: 'В категории слишком много равнозначных строк, клиенту трудно быстро выбрать.',
        action: 'Оставить ключевые направления, а редкие или технические варианты перенести внутрь описаний.',
        examples: activeServices
          .filter((service) => String(service.category || '').trim() === item.category)
          .map(compressionServiceName)
          .filter(Boolean)
          .slice(0, 4),
      });
    });

  const coveredCurrentCount = groups.reduce((sum, group) => sum + group.currentCount, 0);
  const coveredRecommendedCount = groups.reduce((sum, group) => sum + group.recommendedCount, 0);
  const estimatedAfterCount = Math.max(
    Math.min(beforeCount, 12),
    beforeCount - Math.max(0, coveredCurrentCount - coveredRecommendedCount),
  );
  const highPriority = beforeCount >= 150;
  const summary = beforeCount >= 80
    ? `В меню ${beforeCount} услуг. Клиенту будет проще выбрать, если сократить видимый список примерно до ${estimatedAfterCount} направлений и перенести варианты внутрь карточек услуг.`
    : `В меню ${beforeCount} услуг. Список пока не перегружен, но часть похожих позиций всё равно можно сгруппировать.`;

  return {
    beforeCount,
    estimatedAfterCount,
    highPriority,
    categoryCounts,
    summary,
    groups,
    generalRecommendations: SERVICE_CATALOG_GENERAL_RECOMMENDATIONS,
  };
};

export const formatServiceSource = (service: ServiceLike) => {
  const source = String(service?.source || '').trim().toLowerCase();
  if (!source) return 'LocalOS';
  if (source === 'manual' || source === 'localos') return 'LocalOS';
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
