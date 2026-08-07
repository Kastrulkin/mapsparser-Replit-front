import { describe, expect, it } from 'vitest';
import { leadMapLink } from './leadMapLink';

describe('leadMapLink', () => {
  it('returns a direct Yandex Maps card with a human label', () => {
    expect(leadMapLink([{
      url: 'https://yandex.ru/maps/org/persona_lab/123',
    }])).toEqual({
      url: 'https://yandex.ru/maps/org/persona_lab/123',
      label: 'Открыть на Яндекс Картах',
    });
  });

  it('recognizes the international Yandex Maps domain used by imported leads', () => {
    expect(leadMapLink([{
      url: 'https://yandex.com/maps/org/imidzh_laboratoriya_persona/1389312493/',
    }])).toEqual({
      url: 'https://yandex.com/maps/org/imidzh_laboratoriya_persona/1389312493/',
      label: 'Открыть на Яндекс Картах',
    });
  });

  it('uses a map source from research when the lead source is missing', () => {
    expect(leadMapLink([
      { url: '' },
      { url: 'https://2gis.ru/moscow/firm/123', source_type: 'map_card' },
    ])?.label).toBe('Открыть в 2ГИС');
  });

  it('does not turn an audit or social URL into a map link', () => {
    expect(leadMapLink([
      { url: 'https://localos.pro/persona-lab', source_type: 'public_audit' },
      { url: 'https://t.me/persona_lab', source_type: 'telegram_public' },
    ])).toBeNull();
  });
});
