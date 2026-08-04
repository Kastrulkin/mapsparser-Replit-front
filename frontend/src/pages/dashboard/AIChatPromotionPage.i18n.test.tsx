import { describe, expect, it } from 'vitest';

import { ar } from '@/i18n/locales/ar';
import { de } from '@/i18n/locales/de';
import { el } from '@/i18n/locales/el';
import { en } from '@/i18n/locales/en';
import { es } from '@/i18n/locales/es';
import { fr } from '@/i18n/locales/fr';
import { ha } from '@/i18n/locales/ha';
import { ru } from '@/i18n/locales/ru';
import { th } from '@/i18n/locales/th';
import { tr } from '@/i18n/locales/tr';
import { normalizeGeoPromotionSteps } from '@/i18n/demoWorkspaceCopy';
import type { Language } from '@/i18n/LanguageContext';

const locales = { ru, en, fr, es, el, de, th, ar, ha, tr };
const supportedLanguages: Language[] = ['ru', 'en', 'fr', 'es', 'el', 'de', 'th', 'ar', 'ha', 'tr'];

describe('AIChatPromotionPage locale contract', () => {
  it.each(supportedLanguages)('%s exposes renderable promotion steps', (language) => {
    const steps = normalizeGeoPromotionSteps(language, locales[language].dashboard.aiChatPromotion.steps);

    expect(Array.isArray(steps)).toBe(true);
    expect(steps.length).toBeGreaterThan(0);
    expect(steps.every((step) => (
      typeof step.id === 'number'
      && typeof step.title === 'string'
      && typeof step.description === 'string'
      && Array.isArray(step.details)
    ))).toBe(true);
  });
});
