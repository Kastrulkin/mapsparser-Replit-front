import { describe, expect, it } from 'vitest';
import { buildCompanyMapViewport, getCompanyHeatmapColor, getCompanyMapRole } from './companyRegistryMapModel';

describe('CompanyRegistryMap', () => {
  it('uses a stable role priority for marker colors', () => {
    const role = getCompanyMapRole([
      { key: 'localos_lead', label: 'Лид LocalOS' },
      { key: 'client', label: 'Клиент' },
    ]);

    expect(role.key).toBe('client');
    expect(role.color).toBe('#10b981');
  });

  it('builds bounds around all visible companies', () => {
    const viewport = buildCompanyMapViewport([
      { id: 'one', name: 'Один', latitude: 55.7, longitude: 37.5 },
      { id: 'two', name: 'Два', latitude: 56.1, longitude: 38.2 },
    ]);

    expect(viewport.center[0]).toBeCloseTo(55.9);
    expect(viewport.center[1]).toBeCloseTo(37.85);
    expect(viewport.bounds).toEqual([[55.7, 37.5], [56.1, 38.2]]);
  });

  it('uses a light-to-dark blue palette for density intensity', () => {
    const low = getCompanyHeatmapColor(0.1);
    const high = getCompanyHeatmapColor(1);

    expect(low.blue).toBeGreaterThan(low.red);
    expect(high.red).toBeLessThan(low.red);
    expect(high.green).toBeLessThan(low.green);
    expect(high.alpha).toBeGreaterThan(low.alpha);
  });
});
