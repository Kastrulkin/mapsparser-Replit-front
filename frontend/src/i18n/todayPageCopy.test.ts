import { describe, expect, it } from 'vitest';

import type { Language } from './LanguageContext.logic';
import { getTodayOperationalCopy, getTodayPageCopy } from './todayPageCopy';

const languages: Language[] = ['ru', 'en', 'fr', 'es', 'el', 'de', 'th', 'ar', 'ha', 'tr', 'hy', 'kk'];

describe('today page localization', () => {
  it.each(languages)('contains complete copy for %s', (language) => {
    const values = Object.values(getTodayPageCopy(language)).filter((value) => typeof value === 'string');
    expect(values.length).toBeGreaterThan(40);
    expect(values.every((value) => value.trim().length > 0)).toBe(true);
  });

  it.each(languages.filter((language) => language !== 'ru' && language !== 'kk'))('does not contain Russian fallback for %s', (language) => {
    expect(JSON.stringify(getTodayPageCopy(language))).not.toMatch(/[А-Яа-яЁё]/);
  });

  it.each(languages)('contains complete operational copy for %s', (language) => {
    const operationalCopy = getTodayOperationalCopy(language);
    const values = [
      ...Object.values(operationalCopy.preference),
      ...Object.values(operationalCopy.emptyMissions.content),
      ...Object.values(operationalCopy.emptyMissions.influencers),
      ...Object.values(operationalCopy.emptyMissions.automation),
      operationalCopy.decisionTitle,
      operationalCopy.decisionDescription,
    ];
    expect(values.every((value) => value.trim().length > 0)).toBe(true);
  });

  it.each(languages.filter((language) => language !== 'ru' && language !== 'kk'))('does not use Russian operational fallback for %s', (language) => {
    expect(JSON.stringify(getTodayOperationalCopy(language))).not.toMatch(/[А-Яа-яЁё]/);
  });

  it('contains Kazakh instead of the English Today heading', () => {
    expect(JSON.stringify(getTodayPageCopy('kk'))).toMatch(/[ӘәҒғҚқҢңӨөҰұҮүҺһІі]/);
    expect(getTodayPageCopy('kk').title).not.toBe(getTodayPageCopy('en').title);
  });
});
