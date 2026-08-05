import { describe, expect, it } from 'vitest';
import { publicAuditUiTextForLanguage, supportedPublicAuditLanguages } from '@/components/audit/publicAuditCopy';

describe('public audit copy', () => {
  it.each(supportedPublicAuditLanguages)('provides progressive-disclosure labels for %s', (lang) => {
    const text = publicAuditUiTextForLanguage(lang);

    expect(text.auditScore.trim()).not.toBe('');
    expect(text.auditFixYourself.trim()).not.toBe('');
    expect(text.auditPrepareWithLocalOS.trim()).not.toBe('');
    expect(text.auditFixToday.trim()).not.toBe('');
    expect(text.auditStrengths.trim()).not.toBe('');
    expect(text.auditCustomerUnderstanding.trim()).not.toBe('');
    expect(text.auditShowMore.trim()).not.toBe('');
    expect(text.auditFullPlan.trim()).not.toBe('');
  });
});
