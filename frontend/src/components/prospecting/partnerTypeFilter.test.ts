import { describe, expect, it } from 'vitest';
import { partnerTypeForCategory } from './partnerTypeFilter';

describe('partnerTypeForCategory', () => {
  it('groups residential complexes and apartment hotels together', () => {
    expect(partnerTypeForCategory('Жилой комплекс')).toBe('residential');
    expect(partnerTypeForCategory('Апарт-отель / жилой комплекс')).toBe('residential');
  });

  it('keeps dentistry separate from general medicine', () => {
    expect(partnerTypeForCategory('Медицинский центр / стоматология')).toBe('dentistry');
    expect(partnerTypeForCategory('Диагностический центр / медцентр, клиника')).toBe('medicine');
  });

  it('groups child sports by the concrete activity type', () => {
    expect(partnerTypeForCategory('Детская спортивная/развивающая секция')).toBe('sport');
  });

  it('separates child retail, education and leisure', () => {
    expect(partnerTypeForCategory('Магазин детской одежды / детский магазин')).toBe('children_retail');
    expect(partnerTypeForCategory('Детский сад, ясли / центр развития ребёнка')).toBe('children_education');
    expect(partnerTypeForCategory('Детский город профессий')).toBe('children_leisure');
  });

  it('uses a visible fallback for uncommon categories', () => {
    expect(partnerTypeForCategory('Банк')).toBe('other');
    expect(partnerTypeForCategory(null)).toBe('other');
  });
});
