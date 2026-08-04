import { describe, expect, it } from 'vitest';

import { resolveInitialLanguage } from '@/i18n/languagePreference';
import { guidedTourCopyForLanguage, supportedGuidedTourLanguages } from './guidedTourCopy';
import { GUIDED_TOUR_STEP_LAYOUTS, guidedTourStepsForLanguage } from './tourConfig';

describe('guided tour localization', () => {
  it.each(supportedGuidedTourLanguages)('provides complete copy for %s', (language) => {
    const copy = guidedTourCopyForLanguage(language);
    const steps = guidedTourStepsForLanguage(language);

    expect(steps).toHaveLength(GUIDED_TOUR_STEP_LAYOUTS.length);
    expect(copy.welcome.capabilities).toHaveLength(7);
    expect(copy.entry.pageTitle.trim()).not.toBe('');
    expect(copy.banner.notice.trim()).not.toBe('');
    expect(steps.every((step) => step.chapterTitle.trim() && step.title.trim() && step.body.trim())).toBe(true);
    expect(steps.map((step) => step.key)).toEqual(GUIDED_TOUR_STEP_LAYOUTS.map((step) => step.key));
  });

  it.each(supportedGuidedTourLanguages.filter((language) => language !== 'ru'))('does not fall back to Russian steps for %s', (language) => {
    const localizedSteps = guidedTourStepsForLanguage(language);
    const russianSteps = guidedTourStepsForLanguage('ru');

    expect(localizedSteps.every((step, index) => (
      step.title !== russianSteps[index].title && step.body !== russianSteps[index].body
    ))).toBe(true);
  });

  it('uses the demo link language before saved and browser preferences', () => {
    expect(resolveInitialLanguage('/demo', '?lang=tr', 'ru', 'de-DE')).toBe('tr');
    expect(resolveInitialLanguage('/demo', '?lang=ar', null, 'en-US')).toBe('ar');
  });

  it('falls back to saved, browser, and English preferences in that order', () => {
    expect(resolveInitialLanguage('/demo', '?lang=unsupported', 'fr', 'de-DE')).toBe('fr');
    expect(resolveInitialLanguage('/demo', '', null, 'th-TH')).toBe('th');
    expect(resolveInitialLanguage('/demo', '', null, 'it-IT')).toBe('en');
  });
});
