import { describe, expect, it } from 'vitest';

import type { Language } from './LanguageContext';
import { getTodayPageCopy } from './todayPageCopy';

const languages: Language[] = ['ru', 'en', 'fr', 'es', 'el', 'de', 'th', 'ar', 'ha', 'tr'];

describe('today page localization', () => {
  it.each(languages)('contains complete copy for %s', (language) => {
    const values = Object.values(getTodayPageCopy(language)).filter((value) => typeof value === 'string');
    expect(values.length).toBeGreaterThan(40);
    expect(values.every((value) => value.trim().length > 0)).toBe(true);
  });

  it.each(languages.filter((language) => language !== 'ru'))('does not contain Russian fallback for %s', (language) => {
    expect(JSON.stringify(getTodayPageCopy(language))).not.toMatch(/[А-Яа-яЁё]/);
  });
});
