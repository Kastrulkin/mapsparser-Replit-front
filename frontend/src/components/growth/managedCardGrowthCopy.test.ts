import { describe, expect, it } from 'vitest';

import type { Language } from '@/i18n/LanguageContext.logic';
import { managedActionCopy, managedCardGrowthCopyForLanguage, managedProviderLabel } from './managedCardGrowthCopy';

const languages: Language[] = ['ru', 'en', 'es', 'fr', 'el', 'de', 'th', 'ar', 'ha', 'tr'];
const actionCodes = ['refresh', 'restore', 'add_provider', 'blocked', 'access', 'verified', 'duplicate', 'category', 'contacts', 'schedule', 'action_path', 'services', 'prices', 'reviews', 'review_responses', 'photos', 'publications'];
const keys = (values: Record<string | number, unknown>) => Object.keys(values).sort();

describe('managed card growth copy', () => {
  it('provides every structured action message in every supported language', () => {
    const russian = managedCardGrowthCopyForLanguage('ru');
    for (const language of languages) {
      const copy = managedCardGrowthCopyForLanguage(language);
      expect(keys(copy.actionMessages)).toEqual(actionCodes.slice().sort());
      expect(keys(copy.facts)).toEqual(keys(russian.facts));
      expect(keys(copy.states)).toEqual(keys(russian.states));
      expect(keys(copy.evidence)).toEqual(keys(russian.evidence));
      expect(keys(copy.goals)).toEqual(keys(russian.goals));
      expect(keys(copy.decisions)).toEqual(keys(russian.decisions));
      expect(keys(copy.gates)).toEqual(keys(russian.gates));
      for (const code of actionCodes) {
        const action = managedActionCopy(language, code, 'Яндекс', 'bookings', 12);
        expect(action.title).not.toBe(copy.safeFallback);
        expect(action.reason).not.toBe('');
        expect(action.cta).not.toBe('');
        expect(action.outcome).not.toBe('');
      }
    }
  });

  it('keeps known action semantics and benchmark data instead of using the generic fallback', () => {
    const action = managedActionCopy('es', 'contacts', 'Яндекс', 'bookings', 12);

    expect(action.title).toBe('Completa los contactos en Яндекс');
    expect(action.reason).toContain('12');
    expect(action.outcome).toBe('Facilitar las reservas y comprobar el cambio en reservas o consultas.');
    expect(action.cta).toBe('Revisar contactos');
  });

  it('uses raw legacy text only for Russian missing codes and never reads prototype keys', () => {
    const legacy = { title: 'Старое действие', reason: 'Старая причина', cta: 'Открыть', outcome: 'Старый результат' };
    const russian = managedActionCopy('ru', undefined, 'Яндекс', 'bookings', undefined, legacy);
    const spanish = managedActionCopy('es', '__proto__', 'Яндекс', 'bookings', undefined, legacy);

    expect(russian).toEqual(legacy);
    expect(spanish.title).not.toBe(legacy.title);
    expect(spanish.reason).not.toBe(legacy.reason);
    expect(spanish.cta).not.toBe(legacy.cta);
    expect(spanish.outcome).not.toBe(legacy.outcome);
    expect(spanish.title).toBe(managedCardGrowthCopyForLanguage('es').safeFallback);
  });

  it('keeps provider, unknown goals and non-finite benchmark data safe in every language', () => {
    expect(managedProviderLabel('__proto__')).toBe('__proto__');
    for (const language of languages) {
      const nanMedian = managedActionCopy(language, 'contacts', managedProviderLabel('__proto__'), '__proto__', Number.NaN);
      const infiniteMedian = managedActionCopy(language, 'contacts', managedProviderLabel('__proto__'), '__proto__', Number.POSITIVE_INFINITY);

      expect(typeof nanMedian.title).toBe('string');
      expect(typeof nanMedian.outcome).toBe('string');
      expect(nanMedian.reason).not.toContain('NaN');
      expect(infiniteMedian.reason).not.toContain('∞');
      expect(infiniteMedian.reason).not.toContain('Infinity');
    }
  });
});
