import { ruSections } from "./publicDocsContent";
import { leadJourneyDirections } from "./growthDirections";
import { publishedArticles } from "./articles";
import { publishedDocuments } from "./documents";
import { solutions } from "./solutions";
import { describe, expect, it } from "vitest";
import { publishedCases } from "./cases";
import { publicHomeContent } from "./publicHomeContent";
import { buildPublicPageFallbacks } from "./publicPageFallbacks";

describe("public page fallback manifest", () => {
  it("has the exact finite public route set and renderer contract", () => {
    const manifest = buildPublicPageFallbacks();
    const expectedRoutes = ["/growth", ...leadJourneyDirections.map((item) => `/growth?direction=${item.key}`), ...ruSections.map((item) => item.slug === "overview" ? "/docs" : `/docs/${item.slug}`), "/", "/about", "/pricing", "/cases", ...publishedCases.map((caseItem) => `/cases/${caseItem.slug}`), "/articles", "/documents", ...publishedArticles.map((item) => `/articles/${item.slug}`), ...publishedDocuments.map((item) => `/documents/${item.slug}`), ...solutions.map((item) => `/solutions/${item.slug}`)].sort();

    expect(manifest.version).toBe(1);
    expect(Object.keys(manifest.routes).sort()).toEqual(expectedRoutes);
    for (const page of Object.values(manifest.routes)) {
      expect(page).toMatchObject({ title: expect.any(String), description: expect.any(String), heading: expect.any(String), intro: expect.any(Array), sections: expect.any(Array) });
      expect(page.title).not.toHaveLength(0);
      expect(page.description).not.toHaveLength(0);
      expect(page.heading).not.toHaveLength(0);
      for (const section of page.sections) {
        for (const link of section.links ?? []) expect(link.href.startsWith("/") || link.href.startsWith("https://")).toBe(true);
      }
    }
  });

  it("shares truthful home metadata and canonical prices", () => {
    const manifest = buildPublicPageFallbacks();
    const home = manifest.routes["/"];
    const pricing = manifest.routes["/pricing"];

    expect(home.title).toBe(publicHomeContent.title);
    expect(home.description).toBe(publicHomeContent.description);
    expect(home.heading).toBe(publicHomeContent.heading);
    expect(home.intro).toEqual(publicHomeContent.intro);
    expect(JSON.stringify(home)).toMatch(/Яндекс Картах и 2ГИС/);
    expect(JSON.stringify(home)).toMatch(/1 200 ₽.*5 000 ₽.*25 000 ₽/);
    expect(pricing.sections.map((section) => section.heading)).toEqual(expect.arrayContaining([
      expect.stringContaining("1 200 ₽"),
      expect.stringContaining("5 000 ₽"),
      expect.stringContaining("25 000 ₽"),
    ]));
    expect(JSON.stringify(manifest)).not.toMatch(/170%|3\s*месяц|от\s*15\s*000/i);
  });

  it("uses the published case copy without changing its text or metrics", () => {
    const manifest = buildPublicPageFallbacks();

    for (const caseItem of publishedCases) {
      const page = manifest.routes[`/cases/${caseItem.slug}`];
      expect(page).toMatchObject({ title: caseItem.seoTitle, description: caseItem.seoDescription, heading: caseItem.title, intro: [caseItem.excerpt] });
      expect(page.sections).toEqual(expect.arrayContaining([
        expect.objectContaining({ heading: "Исходная ситуация", paragraphs: [caseItem.situation] }),
        expect.objectContaining({ heading: "Показатели опубликованного кейса", items: caseItem.metrics.map((metric) => `${metric.label}: ${metric.value}`) }),
        expect.objectContaining({ heading: "Что сделали", items: caseItem.actions }),
        expect.objectContaining({ heading: "Результат", paragraphs: [caseItem.result] }),
      ]));
      expect(manifest.routes["/"].sections).toEqual(expect.arrayContaining([
        expect.objectContaining({ heading: caseItem.title, items: caseItem.metrics.map((metric) => `${metric.label}: ${metric.value}`) }),
      ]));
      expect(manifest.routes["/cases"].sections).toEqual(expect.arrayContaining([
        expect.objectContaining({ heading: caseItem.title, items: caseItem.metrics.map((metric) => `${metric.label}: ${metric.value}`) }),
      ]));
    }
  });
});


describe("public content coverage", () => {
  it("includes every published article, document and solution with its actual body", () => {
    const { routes } = buildPublicPageFallbacks();
    for (const { prefix, items } of [{ prefix: "articles", items: publishedArticles }, { prefix: "documents", items: publishedDocuments }, { prefix: "solutions", items: solutions }]) {
      for (const item of items) {
        const page = routes[`/${prefix}/${item.slug}`];
        expect(page.heading).toBe(item.title);
        expect(page.title).toBe(item.seoTitle);
        for (const section of item.body) {
          if (section.body) expect(JSON.stringify(page)).toContain(section.body);
          for (const text of section.items || []) expect(JSON.stringify(page)).toContain(text);
        }
      }
    }
    expect(routes["/articles/missing"]).toBeUndefined();
    expect(routes["/solutions/missing"]).toBeUndefined();
  });
  it("provides review examples without the download form", () => {
    const page = buildPublicPageFallbacks().routes["/documents/shablony-otvetov-na-otzyvy"];
    expect(page.sections.map((section) => section.heading)).toEqual(expect.arrayContaining(["Положительный отзыв", "Отзыв без текста", "Претензия к ожиданию", "Конфликт"]));
  });
});
