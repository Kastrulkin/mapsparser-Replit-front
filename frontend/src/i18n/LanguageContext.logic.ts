import { createContext, useContext } from "react";

export type Translations = typeof import('./locales/en').en;

export type Language = "ru" | "en" | "fr" | "es" | "el" | "de" | "th" | "ar" | "ha" | "tr";

export interface LanguageContextType {
  language: Language;
  setLanguage: (lang: Language) => void;
  t: Translations;
}

export const LanguageContext = createContext<LanguageContextType | undefined>(undefined);

export const useLanguage = () => {
  const context = useContext(LanguageContext);

  if (!context) {
    throw new Error("useLanguage must be used within a LanguageProvider");
  }

  return context;
};
