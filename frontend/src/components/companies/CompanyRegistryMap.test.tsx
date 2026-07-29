import { describe, expect, it } from 'vitest';
import { buildCompanyDensityCells, buildCompanyMapViewport, getCompanyMapRole } from './companyRegistryMapModel';

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

  it('aggregates nearby companies into density cells', () => {
    const cells = buildCompanyDensityCells([
      { id: 'one', name: 'Один', latitude: 59.9311, longitude: 30.3609 },
      { id: 'two', name: 'Два', latitude: 59.9318, longitude: 30.3615 },
      { id: 'three', name: 'Три', latitude: 59.999, longitude: 30.42 },
    ], 13);

    expect(cells).toHaveLength(2);
    expect(cells.at(-1)?.count).toBe(2);
    expect(cells.at(-1)?.intensity).toBe(1);
    expect(cells[0].intensity).toBeLessThan(1);
  });

  it('uses finer density cells as the map is zoomed in', () => {
    const items = [
      { id: 'one', name: 'Один', latitude: 59.9311, longitude: 30.3609 },
      { id: 'two', name: 'Два', latitude: 59.936, longitude: 30.369 },
    ];

    expect(buildCompanyDensityCells(items, 9)).toHaveLength(1);
    expect(buildCompanyDensityCells(items, 16)).toHaveLength(2);
  });
});
