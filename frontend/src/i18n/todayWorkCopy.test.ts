import { describe, expect, it } from 'vitest';
import type { Language } from './LanguageContext.logic';
import { todayWorkActionLabel, todayWorkDescription } from './todayWorkCopy';

const languages: Language[] = ['ru', 'en', 'es', 'fr', 'de', 'el', 'tr', 'th', 'ar', 'ha'];
const statuses = ['waiting_provider', 'provider_request_queued', 'provider_executing', 'provider_reconciliation_required', 'provider_failed', 'provider_unavailable', 'approval_invalid'];

describe('Today system work copy', () => {
  it.each(languages)('has explicit display copy for every sheet state in %s', (language) => {
    const messages = statuses.map((status) => todayWorkDescription(language, `today.automation.${status}`, 'fallback'));
    expect(messages.every((message) => message.length > 0 && message !== 'fallback')).toBe(true);
    expect(messages[0]).toBe(messages[1]);
    expect(new Set(messages).size).toBe(6);
    if (language !== 'ru') expect(messages.every((message) => !/[А-Яа-яЁё]/u.test(message))).toBe(true);
    expect(todayWorkActionLabel(language, 'today.open', 'fallback')).not.toBe('fallback');
  });

  it.each(languages)('leaves arbitrary content byte-for-byte unchanged in %s', (language) => {
    for (const code of [undefined, '', 'unknown', 'toString', '__proto__', 'today.automation.completed']) {
      expect(todayWorkDescription(language, code, '  Выполняется запись в таблицу.\n')).toBe('  Выполняется запись в таблицу.\n');
      expect(todayWorkActionLabel(language, code, ' Моя кнопка ')).toBe(' Моя кнопка ');
    }
    expect(todayWorkDescription(language, 'today.open', 'Описание')).toBe('Описание');
    expect(todayWorkActionLabel(language, 'today.automation.provider_failed', 'Кнопка')).toBe('Кнопка');
  });

  it('does not describe uncertain or pending writes as completed in Spanish or English', () => {
    expect(todayWorkDescription('es', 'today.automation.provider_reconciliation_required', '')).toBe('Se desconoce el resultado de la escritura. Revisa la hoja antes de continuar.');
    expect(todayWorkDescription('en', 'today.automation.provider_reconciliation_required', '')).toBe('The write outcome is unknown. Check the spreadsheet before taking further action.');
    expect(todayWorkDescription('es', 'today.automation.provider_request_queued', '')).toBe('La escritura en la hoja está aprobada y pendiente de ejecución.');
    expect(todayWorkDescription('en', 'today.automation.approval_invalid', '')).toBe('The write approval is no longer valid. Open the result to review it.');
  });
});
