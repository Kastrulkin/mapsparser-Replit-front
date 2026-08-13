import { useEffect, useState } from "react";
import type { Language } from "@/i18n/LanguageContext";
import type { ArticleContent } from "./contentTypes";
import { publishedArticles } from "./articles";

const loadArticles = async (language: Language): Promise<ArticleContent[]> => {
  switch (language) {
    case "ru": return publishedArticles;
    case "en": return import("./article-locales/en.json").then((module) => module.default);
    case "fr": return import("./article-locales/fr.json").then((module) => module.default);
    case "es": return import("./article-locales/es.json").then((module) => module.default);
    case "el": return import("./article-locales/el.json").then((module) => module.default);
    case "de": return import("./article-locales/de.json").then((module) => module.default);
    case "th": return import("./article-locales/th.json").then((module) => module.default);
    case "ar": return import("./article-locales/ar.json").then((module) => module.default);
    case "ha": return import("./article-locales/ha.json").then((module) => module.default);
    case "tr": return import("./article-locales/tr.json").then((module) => module.default);
  }
};

export const useLocalizedArticles = (language: Language) => {
  const [articles, setArticles] = useState<ArticleContent[]>(language === "ru" ? publishedArticles : []);
  const [isLoading, setIsLoading] = useState(language !== "ru");

  useEffect(() => {
    let active = true;
    setIsLoading(language !== "ru");
    setArticles(language === "ru" ? publishedArticles : []);

    void loadArticles(language).then((loaded) => {
      if (active) {
        setArticles(loaded);
        setIsLoading(false);
      }
    });

    return () => {
      active = false;
    };
  }, [language]);

  return { articles, isLoading };
};
