import { describe, expect, it } from 'vitest';
import type { Language } from './LanguageContext.logic';
import { todayClarityCopy } from './todayClarityCopy';
const languages: Language[] = ['ru','en','fr','es','el','de','th','ar','ha','tr','hy'];
describe('Today clarity localization', () => {
  it.each(languages)('has every nonempty label for %s', language => {
    const copy = todayClarityCopy(language);
    expect(Object.keys(copy)).toEqual(Object.keys(todayClarityCopy('ru')));
    expect(Object.values(copy)).toHaveLength(43);
    expect(Object.values(copy).every(value => value?.trim())).toBe(true);
    if (language !== 'ru') expect(JSON.stringify(copy)).not.toMatch(/[А-Яа-яЁё]/);
  });
});
