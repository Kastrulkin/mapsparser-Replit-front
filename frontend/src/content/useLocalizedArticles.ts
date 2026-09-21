import type { Language } from '@/i18n/LanguageContext.logic';
import { useEffect, useState } from "react";
import { publishedArticles } from "./articles";
import type { ArticleContent } from "./contentTypes";
import { localizedVideoArticles } from "./videoArticleTranslations";

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

export const mergeLocalizedArticles = (language: Exclude<Language, "ru">, localizedArticles: ArticleContent[]) => {
  const articles = [...localizedArticles, ...localizedVideoArticles(language)];
  const expectedSlugs = new Set(publishedArticles.map((article) => article.slug));
  const actualSlugs = new Set(articles.map((article) => article.slug));
  if (actualSlugs.size !== expectedSlugs.size || [...expectedSlugs].some((slug) => !actualSlugs.has(slug))) {
    throw new Error(`Incomplete ${language} article translation set`);
  }
  const titles = new Map(articles.map((article) => [`/articles/${article.slug}`, article.title]));
  return articles.map((article) => ({
    ...article,
    related: article.related.map((item) => ({
      ...item,
      title: titles.get(item.href) ?? item.title,
    })),
  }));
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
        setArticles(language === "ru" ? loaded : mergeLocalizedArticles(language, loaded));
        setIsLoading(false);
      }
    });

    return () => {
      active = false;
    };
  }, [language]);

  return { articles, isLoading };
};
