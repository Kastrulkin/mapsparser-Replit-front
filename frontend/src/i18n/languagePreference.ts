import type { Language } from './LanguageContext.logic';

export const isSupportedLanguage = (value: string): value is Language => (
  value === 'ru' ||
  value === 'en' ||
  value === 'fr' ||
  value === 'es' ||
  value === 'el' ||
  value === 'de' ||
  value === 'th' ||
  value === 'ar' ||
  value === 'ha' ||
  value === 'tr' ||
  value === 'hy'
);

export const resolveInitialLanguage = (
  _pathname: string,
  search: string,
  savedLanguage: string | null,
  browserLanguage: string,
): Language => {
  const requestedLanguage = new URLSearchParams(search).get('lang');

  if (requestedLanguage && isSupportedLanguage(requestedLanguage)) {
    return requestedLanguage;
  }

  if (savedLanguage && isSupportedLanguage(savedLanguage)) {
    return savedLanguage;
  }

  const browserLang = browserLanguage.split('-')[0];
  return isSupportedLanguage(browserLang) ? browserLang : 'en';
};

export const urlWithLanguage = (
  pathname: string,
  search: string,
  hash: string,
  language: Language,
): string => {
  const params = new URLSearchParams(search);
  params.set('lang', language);
  return `${pathname}?${params.toString()}${hash}`;
};
