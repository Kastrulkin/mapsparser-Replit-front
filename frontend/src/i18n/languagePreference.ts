import type { Language } from './LanguageContext';

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
  value === 'tr'
);

export const resolveInitialLanguage = (
  pathname: string,
  search: string,
  savedLanguage: string | null,
  browserLanguage: string,
): Language => {
  const requestedLanguage = pathname === '/demo'
    ? new URLSearchParams(search).get('lang')
    : null;

  if (requestedLanguage && isSupportedLanguage(requestedLanguage)) {
    return requestedLanguage;
  }

  if (savedLanguage && isSupportedLanguage(savedLanguage)) {
    return savedLanguage;
  }

  const browserLang = browserLanguage.split('-')[0];
  return isSupportedLanguage(browserLang) ? browserLang : 'en';
};
