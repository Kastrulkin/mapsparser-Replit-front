import React, { createContext, useContext, useEffect, useMemo, useState, ReactNode } from "react";

type Translations = typeof import("./locales/ru").ru;

export type Language = "ru" | "en" | "fr" | "es" | "el" | "de" | "th" | "ar" | "ha" | "tr";

interface LanguageContextType {
  language: Language;
  setLanguage: (lang: Language) => void;
  t: Translations;
}

const LanguageContext = createContext<LanguageContextType | undefined>(undefined);

const isLanguage = (value: string): value is Language => {
  return (
    value === "ru" ||
    value === "en" ||
    value === "fr" ||
    value === "es" ||
    value === "el" ||
    value === "de" ||
    value === "th" ||
    value === "ar" ||
    value === "ha" ||
    value === "tr"
  );
};

const detectInitialLanguage = (): Language => {
  const saved = localStorage.getItem("language");

  if (saved && isLanguage(saved)) {
    return saved;
  }

  if (typeof navigator !== "undefined" && navigator.language) {
    const browserLang = navigator.language.split("-")[0];

    if (isLanguage(browserLang)) {
      return browserLang;
    }
  }

  return "en";
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
    <div className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-500 shadow-sm">
      Загружаем язык...
    </div>
  </div>
);

export const LanguageProvider: React.FC<LanguageProviderProps> = ({ children }) => {
  const [language, setLanguageState] = useState<Language>(detectInitialLanguage);
  const [translations, setTranslations] = useState<Translations | null>(null);

  useEffect(() => {
    localStorage.setItem("language", language);
  }, [language]);

  useEffect(() => {
    let active = true;

    const applyTranslations = async () => {
      try {
        const loadedTranslations = await loadTranslations(language);

        if (active) {
          setTranslations(loadedTranslations);
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
