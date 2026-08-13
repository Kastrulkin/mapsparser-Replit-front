import { describe, expect, it } from 'vitest';

import { resolveInitialLanguage } from '@/i18n/languagePreference';
import { guidedTourCopyForLanguage, supportedGuidedTourLanguages } from './guidedTourCopy';
import { GUIDED_TOUR_STEP_LAYOUTS, guidedTourStepsForLanguage } from './tourConfig';

describe('guided tour localization', () => {
  it.each(supportedGuidedTourLanguages)('provides complete copy for %s', (language) => {
    const copy = guidedTourCopyForLanguage(language);
    const steps = guidedTourStepsForLanguage(language);

    expect(steps).toHaveLength(GUIDED_TOUR_STEP_LAYOUTS.length);
    expect(copy.welcome.capabilities).toHaveLength(6);
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
    ['agents-signals', 'agents-today', 'agents-employees', 'agents-control', 'agents-run', 'agents-review', 'agents-history'].forEach((key) => {
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
    expect(JSON.stringify(guidedTourCopyForLanguage(language))).not.toMatch(/[А-Яа-яЁё]/);
  });

  it.each(supportedGuidedTourLanguages)('keeps customer-facing tour copy concise for %s', (language) => {
    const copy = guidedTourCopyForLanguage(language);
    const steps = guidedTourStepsForLanguage(language);
    const internalJargon = /\b(?:LLM|prompt|workflow|blueprint|capability|orchestrator|trigger)\b/i;

    expect(steps.every((step) => step.title.length <= 48 && step.body.length <= 280)).toBe(true);
    expect(JSON.stringify(copy)).not.toMatch(internalJargon);
  });

  it('uses concrete Russian copy instead of abstract product language', () => {
    const steps = guidedTourStepsForLanguage('ru');
    const text = steps.map((step) => `${step.title} ${step.body}`).join(' ');
    const vaguePhrases = /хранит контекст|ведутся по этапам|картина бизнеса|практический результат|следующий результат|рабочий экран|история сохраняет факты|решение остаётся за вами/i;

    expect(text).not.toMatch(vaguePhrases);
    expect(steps.find((step) => step.key === 'partnership-candidates')).toMatchObject({
      title: 'Что уже обсудили с «Ромашкой»',
      body: 'Здесь видно, что предложили компании, как планировали связаться и что нужно сделать дальше.',
    });
  });

  it('gives every Russian content-plan and agent step its own explanation', () => {
    const steps = guidedTourStepsForLanguage('ru');
    const keys = [
      'content-plan-setup', 'content-plan-preview', 'content-plan-save', 'content-plan-review',
      'agents-signals', 'agents-today', 'agents-employees', 'agents-control', 'agents-run', 'agents-review', 'agents-history',
    ];
    const selected = steps.filter((step) => keys.includes(step.key));

    expect(selected).toHaveLength(keys.length);
    expect(new Set(selected.map((step) => step.title)).size).toBe(keys.length);
    expect(new Set(selected.map((step) => step.body)).size).toBe(keys.length);
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
