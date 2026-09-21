import { describe, expect, it } from "vitest";
import { publishedCases } from "./cases";
import { publicHomeContent } from "./publicHomeContent";
import { buildPublicPageFallbacks } from "./publicPageFallbacks";

describe("public page fallback manifest", () => {
  it("has the exact finite public route set and renderer contract", () => {
    const manifest = buildPublicPageFallbacks();
    const expectedRoutes = ["/", "/about", "/pricing", "/cases", ...publishedCases.map((caseItem) => `/cases/${caseItem.slug}`)].sort();

    expect(manifest.version).toBe(1);
    expect(Object.keys(manifest.routes).sort()).toEqual(expectedRoutes);
    for (const page of Object.values(manifest.routes)) {
      expect(page).toMatchObject({ title: expect.any(String), description: expect.any(String), heading: expect.any(String), intro: expect.any(Array), sections: expect.any(Array) });
      expect(page.title).not.toHaveLength(0);
      expect(page.description).not.toHaveLength(0);
      expect(page.heading).not.toHaveLength(0);
      for (const section of page.sections) {
        for (const link of section.links ?? []) expect(link.href.startsWith("/")).toBe(true);
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
