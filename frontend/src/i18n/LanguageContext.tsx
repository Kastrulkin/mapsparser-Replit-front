import React, { createContext, useContext, useEffect, useMemo, useState, ReactNode } from "react";

import { resolveInitialLanguage } from './languagePreference';

type Translations = any;

export type Language = "ru" | "en" | "fr" | "es" | "el" | "de" | "th" | "ar" | "ha" | "tr";

interface LanguageContextType {
  language: Language;
  setLanguage: (lang: Language) => void;
  t: Translations;
}

const LanguageContext = createContext<LanguageContextType | undefined>(undefined);

const isTranslationRecord = (value: unknown): value is Record<string, unknown> =>
  Boolean(value) && typeof value === 'object' && !Array.isArray(value);

const mergeTranslations = (
  fallback: Record<string, unknown>,
  selected: unknown,
): Record<string, unknown> => {
  const result = { ...fallback };
  if (!isTranslationRecord(selected)) return result;
  Object.entries(selected).forEach(([key, value]) => {
    const fallbackValue = fallback[key];
    result[key] = isTranslationRecord(fallbackValue) && isTranslationRecord(value)
      ? mergeTranslations(fallbackValue, value)
      : value;
  });
  return result;
};

const detectInitialLanguage = (): Language => {
  const pathname = typeof window === "undefined" ? "" : window.location.pathname;
  const search = typeof window === "undefined" ? "" : window.location.search;
  const saved = typeof window === "undefined" ? null : window.localStorage.getItem("language");
  const browserLanguage = typeof navigator === "undefined" ? "" : navigator.language;
  return resolveInitialLanguage(pathname, search, saved, browserLanguage);
};

const loadTranslations = async (language: Language): Promise<Translations> => {
  switch (language) {
    case "ru":
      return import("./locales/ru").then((module) => module.ru);
    case "en":
      return import("./locales/en").then((module) => module.en);
    case "fr":
      return import("./locales/fr").then((module) => module.fr);
    case "es":
      return import("./locales/es").then((module) => module.es);
    case "el":
      return import("./locales/el").then((module) => module.el);
    case "de":
      return import("./locales/de").then((module) => module.de);
    case "th":
      return import("./locales/th").then((module) => module.th);
    case "ar":
      return import("./locales/ar").then((module) => module.ar);
    case "ha":
      return import("./locales/ha").then((module) => module.ha);
    case "tr":
      return import("./locales/tr").then((module) => module.tr);
  }
};

export const useLanguage = () => {
  const context = useContext(LanguageContext);

  if (!context) {
    throw new Error("useLanguage must be used within a LanguageProvider");
  }

  return context;
};

interface LanguageProviderProps {
  children: ReactNode;
}

const LanguageLoadingFallback = () => (
  <div className="flex min-h-screen items-center justify-center bg-background px-4 py-12">
    <span className="h-8 w-8 animate-spin rounded-full border-2 border-slate-200 border-t-orange-500 motion-reduce:animate-none" aria-hidden="true" />
    <span className="sr-only">LocalOS</span>
  </div>
);

export const LanguageProvider: React.FC<LanguageProviderProps> = ({ children }) => {
  const [language, setLanguageState] = useState<Language>(detectInitialLanguage);
  const [translations, setTranslations] = useState<Translations | null>(null);

  useEffect(() => {
    localStorage.setItem("language", language);
    document.documentElement.lang = language;
    document.documentElement.dir = language === "ar" ? "rtl" : "ltr";
  }, [language]);

  useEffect(() => {
    let active = true;

    const applyTranslations = async () => {
      try {
        const loadedTranslations = await loadTranslations(language);
        const fallbackTranslations = language === 'en' ? loadedTranslations : await loadTranslations('en');

        if (active) {
          setTranslations(mergeTranslations(fallbackTranslations, loadedTranslations));
        }
      } catch (error) {
        console.error("Failed to load translations:", error);

        if (!active || language === "en") {
          return;
        }

        const fallbackTranslations = await loadTranslations("en");

        if (active) {
          setTranslations(fallbackTranslations);
        }
      }
    };

    setTranslations(null);
    void applyTranslations();

    return () => {
      active = false;
    };
  }, [language]);

  const setLanguage = (lang: Language) => {
    setLanguageState(lang);
  };

  const value = useMemo(() => {
    if (!translations) {
      return null;
    }

    return {
      language,
      setLanguage,
      t: translations,
    };
  }, [language, translations]);

  if (!value) {
    return <LanguageLoadingFallback />;
  }

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
};
