import { describe, expect, it } from 'vitest';

import articlesKk from '@/content/article-locales/kk.json';
import casesKk from '@/content/collection-locales/cases-kk.json';
import documentsKk from '@/content/collection-locales/documents-kk.json';
import docsKk from '@/content/docs-kk.json';
import { subscriptionPlanCopy } from '@/content/subscriptionPlanCopy';
import { kk } from './locales/kk';
import { ru } from './locales/ru';

const keysOf = (value: unknown): unknown => {
  if (Array.isArray(value)) return value.map(keysOf);
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.entries(value).map(([key, entry]) => [key, keysOf(entry)]));
  }
  return null;
};

describe('Kazakh localization coverage', () => {
  it('keeps every key in the main interface dictionary', () => {
    expect(keysOf(kk)).toEqual(keysOf(ru));
    expect(kk.common.save).toMatch(/[ӘәҒғҚқҢңӨөҰұҮүҺһІі]/);
  });

  it('keeps dynamic placeholders in the main interface dictionary', () => {
    const collect = (source: unknown, translated: unknown, path = ''): string[] => {
      if (typeof source === 'string' && typeof translated === 'string') {
        const sourceTokens = [...source.matchAll(/\{([\p{L}_][\p{L}\p{N}_]*)\}/gu)].map((match) => match[1]).sort();
        const translatedTokens = [...translated.matchAll(/\{([\p{L}_][\p{L}\p{N}_]*)\}/gu)].map((match) => match[1]).sort();
        return JSON.stringify(sourceTokens) === JSON.stringify(translatedTokens) ? [] : [path];
      }
      if (source && translated && typeof source === 'object' && typeof translated === 'object') {
        return Object.entries(source).flatMap(([key, value]) =>
          collect(value, Object.entries(translated).find(([translatedKey]) => translatedKey === key)?.[1], `${path}.${key}`));
      }
      return [];
    };
    expect(collect(ru, kk)).toEqual([]);
  });

  it('keeps public documentation routes and technical status codes stable', () => {
    expect(docsKk.sections.map((section) => section.slug)).toEqual([
      'overview', 'capabilities', 'approval-policy', 'security-model',
      'api', 'agent-use-cases', 'gaps',
    ]);
    expect(docsKk.sections[0].title).toMatch(/[ӘәҒғҚқҢңӨөҰұҮүҺһІі]/);
    expect(docsKk.sections.find((section) => section.slug === 'api')?.items
      .some((item) => item.text.includes('POST /api/agent-api/self-test'))).toBe(true);
  });

  it('ships Kazakh articles, cases, documents, and pricing', () => {
    expect(articlesKk.length).toBeGreaterThan(0);
    expect(casesKk.length).toBeGreaterThan(0);
    expect(documentsKk.length).toBeGreaterThan(0);
    expect(subscriptionPlanCopy('kk').starter.name).toBe('Карталар');
    expect(subscriptionPlanCopy('kk').approval).toContain('растағаннан кейін');
  });
});
