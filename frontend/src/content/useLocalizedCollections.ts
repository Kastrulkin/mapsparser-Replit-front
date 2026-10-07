import { useEffect, useState } from "react";
import type { Language } from "@/i18n/LanguageContext";
import type { CaseContent, DocumentContent } from "./contentTypes";
import { publishedCases } from "./cases";
import { publishedDocuments } from "./documents";

const loadDocuments = async (language: Language): Promise<DocumentContent[]> => {
  switch (language) {
    case "ru": return publishedDocuments;
    case "en": return import("./collection-locales/documents-en.json").then((module) => module.default);
    case "fr": return import("./collection-locales/documents-fr.json").then((module) => module.default);
    case "es": return import("./collection-locales/documents-es.json").then((module) => module.default);
    case "el": return import("./collection-locales/documents-el.json").then((module) => module.default);
    case "de": return import("./collection-locales/documents-de.json").then((module) => module.default);
    case "th": return import("./collection-locales/documents-en.json").then((module) => module.default);
    case "ar": return import("./collection-locales/documents-en.json").then((module) => module.default);
    case "ha": return import("./collection-locales/documents-en.json").then((module) => module.default);
    case "tr": return import("./collection-locales/documents-tr.json").then((module) => module.default);
  }
};

const loadCases = async (language: Language): Promise<CaseContent[]> => {
  switch (language) {
    case "ru": return publishedCases;
    case "en": return import("./collection-locales/cases-en.json").then((module) => module.default);
    case "fr": return import("./collection-locales/cases-fr.json").then((module) => module.default);
    case "es": return import("./collection-locales/cases-es.json").then((module) => module.default);
    case "el": return import("./collection-locales/cases-el.json").then((module) => module.default);
    case "de": return import("./collection-locales/cases-de.json").then((module) => module.default);
    case "th": return import("./collection-locales/cases-th.json").then((module) => module.default);
    case "ar": return import("./collection-locales/cases-ar.json").then((module) => module.default);
    case "ha": return import("./collection-locales/cases-ha.json").then((module) => module.default);
    case "tr": return import("./collection-locales/cases-tr.json").then((module) => module.default);
  }
};

export const useLocalizedDocuments = (language: Language) => {
  const [documents, setDocuments] = useState<DocumentContent[]>(language === "ru" ? publishedDocuments : []);
  const [isLoading, setIsLoading] = useState(language !== "ru");

  useEffect(() => {
    let active = true;
    setIsLoading(language !== "ru");
    setDocuments(language === "ru" ? publishedDocuments : []);
    void loadDocuments(language).then((loaded) => {
      if (active) {
        setDocuments(loaded);
        setIsLoading(false);
      }
    });
    return () => { active = false; };
  }, [language]);

  return { documents, isLoading };
};

export const useLocalizedCases = (language: Language) => {
  const [cases, setCases] = useState<CaseContent[]>(language === "ru" ? publishedCases : []);
  const [isLoading, setIsLoading] = useState(language !== "ru");

  useEffect(() => {
    let active = true;
    setIsLoading(language !== "ru");
    setCases(language === "ru" ? publishedCases : []);
    void loadCases(language).then((loaded) => {
      if (active) {
        setCases(loaded);
        setIsLoading(false);
      }
    });
    return () => { active = false; };
  }, [language]);

  return { cases, isLoading };
};
