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
const cyrillic = /[А-Яа-яЁё]/;

describe("article translations", () => {
  localizedArticles.forEach(({ language, articles, copy }) => {
    it(`contains every published article in ${language}`, () => {
      expect(articles).toHaveLength(publishedArticles.length);
      expect(articles.map((article) => article.slug)).toEqual(publishedArticles.map((article) => article.slug));
      expect(articles.map((article) => article.body.length)).toEqual(publishedArticles.map((article) => article.body.length));
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
});
