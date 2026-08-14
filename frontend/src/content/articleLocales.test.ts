import { describe, expect, it } from "vitest";
import { publishedArticles } from "./articles";
import { contentCopy } from "./contentCopy";
import en from "./article-locales/en.json";
import fr from "./article-locales/fr.json";
import es from "./article-locales/es.json";
import el from "./article-locales/el.json";
import de from "./article-locales/de.json";
import th from "./article-locales/th.json";
import ar from "./article-locales/ar.json";
import ha from "./article-locales/ha.json";
import tr from "./article-locales/tr.json";
import { mergeLocalizedArticles } from "./useLocalizedArticles";

const localizedArticles = [
  { language: "en", articles: en, copy: contentCopy.en },
  { language: "fr", articles: fr, copy: contentCopy.fr },
  { language: "es", articles: es, copy: contentCopy.es },
  { language: "el", articles: el, copy: contentCopy.el },
  { language: "de", articles: de, copy: contentCopy.de },
  { language: "th", articles: th, copy: contentCopy.th },
  { language: "ar", articles: ar, copy: contentCopy.ar },
  { language: "ha", articles: ha, copy: contentCopy.ha },
  { language: "tr", articles: tr, copy: contentCopy.tr },
];
const compiledAiSlug = "compiled-ai-pochemu-ii-dolzhen-dumat-odin-raz";
const cyrillic = /[А-Яа-яЁё]/;

describe("article translations", () => {
  localizedArticles.forEach(({ language, articles, copy }) => {
    it(`keeps translated articles intact and falls back to Russian for new articles in ${language}`, () => {
      const mergedArticles = mergeLocalizedArticles(articles);

      expect(mergedArticles.map((article) => article.slug)).toEqual(expect.arrayContaining(publishedArticles.map((article) => article.slug)));
      expect(new Set(mergedArticles.map((article) => article.slug)).size).toBe(publishedArticles.length);
      expect(mergedArticles.slice(0, articles.length)).toEqual(articles);
      expect(JSON.stringify(articles)).not.toMatch(cyrillic);
    });

    it(`contains translated resource navigation in ${language}`, () => {
      expect(copy.materials).not.toMatch(cyrillic);
      expect(copy.navigation.articles.name).not.toMatch(cyrillic);
      expect(copy.articles.title).not.toMatch(cyrillic);
    });
  });

  it("keeps the Greek article metadata complete and free of known broken machine-translation fragments", () => {
    const serialized = JSON.stringify(el);

    expect(el.every((article) => typeof article.seoDescription === "string" && article.seoDescription.length > 0)).toBe(true);
    expect(serialized).not.toMatch(/seoDeπρόγραμμαion|πρόγραμμαs|εντολήs|μέση απόδειξη|συνεχής άγχος|Γεμάτη καταχώριση|μικρά studios|full-time|audit καταχώρισης|food photography|marketing budget|ζωντανή landing|πλαίσιο πλοήγησης/);
  });

  it("keeps the Turkish articles natural and free of known machine-translation fragments", () => {
    const serialized = JSON.stringify(tr);

    expect(tr.every((article) => typeof article.seoDescription === "string" && article.seoDescription.length > 0)).toBe(true);
    expect(serialized).not.toMatch(/kartlardaki bir kartı|tam bir kayıt|teknisyenler penceresiz|mini bir site|canlı iniş|kurşun büyümesi|Reaksiyon hızı|Kartlar aktiviteyi|puannin|puanlarden|Yorumlarin|incelemeler|inceleme/);
  });

  it("keeps every Compiled AI article aligned with the v2 runtime boundary", () => {
    const articleSets = [
      { language: "ru", articles: publishedArticles },
      ...localizedArticles.map(({ language, articles }) => ({ language, articles })),
    ];

    articleSets.forEach(({ language, articles }) => {
      const article = articles.find((candidate) => candidate.slug === compiledAiSlug);
      const serialized = JSON.stringify(article);

      expect(article, `missing Compiled AI article in ${language}`).toBeDefined();
      expect(serialized, `missing v2 source in ${language}`).toContain("2604.05150v2");
      expect(serialized, `stale v1 source in ${language}`).not.toContain("2604.05150v1");
      expect(article?.body[6]?.items, `incomplete runtime boundary in ${language}`).toHaveLength(4);
    });
  });
});
