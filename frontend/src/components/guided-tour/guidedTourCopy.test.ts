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

  it.each(supportedGuidedTourLanguages)('explains the agents automation bridge for %s', (language) => {
    const copy = guidedTourCopyForLanguage(language);
    const chapterEntries = Object.entries(copy.chapters);
    const stepEntries = Object.entries(copy.steps);

    expect(chapterEntries.find(([key]) => key === 'automation')?.[1]).toBeTruthy();
    expect(stepEntries.find(([key]) => key === 'agents-nav')?.[1]).toMatchObject({
      title: expect.any(String),
      body: expect.any(String),
    });
    ['agents-signals', 'agents-today', 'agents-employees', 'agents-control'].forEach((key) => {
      expect(stepEntries.find(([stepKey]) => stepKey === key)?.[1]).toMatchObject({
        title: expect.any(String),
        body: expect.any(String),
      });
    });
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

  it('uses an explicit public-room link language before saved and browser preferences', () => {
    expect(resolveInitialLanguage('/room/room-test-audit-offer-20260629', '?lang=el', 'ru', 'ru-RU')).toBe('el');
  });

  it('falls back to saved, browser, and English preferences in that order', () => {
    expect(resolveInitialLanguage('/demo', '?lang=unsupported', 'fr', 'de-DE')).toBe('fr');
    expect(resolveInitialLanguage('/demo', '', null, 'th-TH')).toBe('th');
    expect(resolveInitialLanguage('/demo', '', null, 'it-IT')).toBe('en');
  });
});
