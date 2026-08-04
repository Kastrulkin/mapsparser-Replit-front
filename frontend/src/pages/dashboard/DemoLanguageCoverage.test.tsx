import { describe, expect, it } from 'vitest';

import type { Language } from '@/i18n/LanguageContext';
import { GUIDED_TOUR_STEP_LAYOUTS } from '@/components/guided-tour/tourConfig';
import { guidedTourStepsForLanguage } from '@/components/guided-tour/tourConfig';
import { getDemoWorkspaceCopy } from '@/i18n/demoWorkspaceCopy';
import { getCardOverviewPageCopy } from './cardOverviewPageCopy';

const supportedLanguages: Language[] = ['ru', 'en', 'fr', 'es', 'el', 'de', 'th', 'ar', 'ha', 'tr'];
const localizedCardLanguages = supportedLanguages.filter((language) => language !== 'ru' && language !== 'en');
const nonRussianLanguages = supportedLanguages.filter((language) => language !== 'ru');

describe('demo language coverage', () => {
  it('keeps the language contract aligned with all 26 guided-tour steps', () => {
    expect(supportedLanguages).toHaveLength(10);
    expect(GUIDED_TOUR_STEP_LAYOUTS).toHaveLength(26);
    supportedLanguages.forEach((language) => {
      expect(guidedTourStepsForLanguage(language)).toHaveLength(26);
    });
  });

  it.each(localizedCardLanguages)('%s does not receive the English card-page fallback', (language) => {
    const localizedCopy = getCardOverviewPageCopy(language);
    const englishCopy = getCardOverviewPageCopy('en');

    expect(localizedCopy.title).not.toBe(englishCopy.title);
    expect(localizedCopy.subtitle).not.toBe(englishCopy.subtitle);
  });

  it.each(nonRussianLanguages)('%s has localized copy for the reported demo workspaces', (language) => {
    const localized = getDemoWorkspaceCopy(language);
    const english = getDemoWorkspaceCopy('en');
    const renderedCopy = JSON.stringify(localized);

    expect(renderedCopy).not.toMatch(/[А-Яа-яЁё]/);
    if (language !== 'en') {
      expect(localized.telegram.pageTitle).not.toBe(english.telegram.pageTitle);
      expect(localized.averageTicket.title).not.toBe(english.averageTicket.title);
      expect(localized.competitors.title).not.toBe(english.competitors.title);
      expect(localized.sidebar.upsells).not.toBe(english.sidebar.upsells);
    }
  });
});
