import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { ru } from './locales/ru';
import { en } from './locales/en';
import { fr } from './locales/fr';
import { es } from './locales/es';
import { el } from './locales/el';
import { de } from './locales/de';
import { th } from './locales/th';
import { ar } from './locales/ar';
import { ha } from './locales/ha';

export type Language = 'ru' | 'en' | 'fr' | 'es' | 'el' | 'de' | 'th' | 'ar' | 'ha';

const translations = {
  ru,
  en,
  fr,
  es,
  el,
  de,
  th,
  ar,
  ha
};

interface LanguageContextType {
  language: Language;
  setLanguage: (lang: Language) => void;
  t: typeof ru;
}

const LanguageContext = createContext<LanguageContextType | undefined>(undefined);

export const useLanguage = () => {
  const context = useContext(LanguageContext);
  if (!context) {
    throw new Error('useLanguage must be used within a LanguageProvider');
  }
  return context;
};

interface LanguageProviderProps {
  children: ReactNode;
}

export const LanguageProvider: React.FC<LanguageProviderProps> = ({ children }) => {
  const [language, setLanguageState] = useState<Language>(() => {
    const saved = localStorage.getItem('language');
    if (saved && (saved === 'ru' || saved === 'en' || saved === 'fr' || saved === 'es' || saved === 'el' || saved === 'de' || saved === 'th' || saved === 'ar' || saved === 'ha')) {
      return saved as Language;
    }
    return 'ru';
  });

  useEffect(() => {
    localStorage.setItem('language', language);
  }, [language]);

  const setLanguage = (lang: Language) => {
    setLanguageState(lang);
  };

  const value = {
    language,
    setLanguage,
    t: translations[language]
  };

  return (
    <LanguageContext.Provider value={value}>
      {children}
    </LanguageContext.Provider>
  );
};

