import { describe, expect, it } from 'vitest';

import type { Language } from './LanguageContext';
import { formatWebAnalyticsCopy, getWebAnalyticsCopy } from './webAnalyticsCopy';

const languages: Language[] = ['ru', 'en', 'fr', 'es', 'el', 'de', 'th', 'ar', 'ha', 'tr'];

describe('webAnalyticsCopy', () => {
  it('provides complete analytics copy for every supported language', () => {
    for (const language of languages) {
      const copy = getWebAnalyticsCopy(language);

      expect(copy.title).not.toHaveLength(0);
      expect(copy.sourceLabels.direct).not.toHaveLength(0);
      expect(copy.actionLabels.form).not.toHaveLength(0);
      expect(formatWebAnalyticsCopy(copy.periodDays, { days: 30 })).not.toContain('{days}');
      expect(formatWebAnalyticsCopy(copy.comparison, { value: 12 })).not.toContain('{value}');
    }
  });
});
