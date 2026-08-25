import { describe, expect, it } from 'vitest';

import type { Language } from '@/i18n/LanguageContext';
import type { AgentTemplate } from './types';
import {
  agentTemplateGalleryCopy,
  getLocalizedAgentTemplateContent,
} from './template-gallery-copy';
import { getAgentDeepCopy } from './agent-deep-copy';

const supportedLanguages: Language[] = ['ru', 'en', 'fr', 'es', 'el', 'de', 'th', 'ar', 'ha', 'tr'];

const template: AgentTemplate = {
  key: 'daily_owner_digest',
  version: '1.0.0',
  name: 'Ежедневная сводка владельцу',
  business_result: 'Русский результат',
  vertical: 'operations',
  trigger: 'schedule.daily',
  required_connections: [],
  risk_level: 'low',
  certification_status: 'beta',
  localized_content: Object.fromEntries(supportedLanguages
    .filter((language) => language !== 'ru')
    .map((language) => [language, { name: `${language} name`, business_result: `${language} result` }])),
};

describe('agent template gallery localization', () => {
  it.each(supportedLanguages)('%s has complete gallery chrome', (language) => {
    const copy = agentTemplateGalleryCopy[language];
    Object.values(copy).forEach((value) => expect(value.trim()).not.toBe(''));
  });

  it.each(supportedLanguages)('%s resolves template content without leaking another language', (language) => {
    const content = getLocalizedAgentTemplateContent(template, language);
    if (language === 'ru') {
      expect(content.name).toBe('Ежедневная сводка владельцу');
      expect(content.business_result).toBe('Русский результат');
      return;
    }
    expect(content.name).toBe(`${language} name`);
    expect(content.business_result).toBe(`${language} result`);
  });

  it.each(supportedLanguages)('%s has complete technical workspace copy', (language) => {
    const serialized = JSON.stringify(getAgentDeepCopy(language));
    expect(serialized).not.toContain('undefined');
    expect(serialized.length).toBeGreaterThan(500);
    if (language !== 'ru') {
      expect(serialized).not.toMatch(/[А-Яа-яЁё]/);
    }
  });
});
