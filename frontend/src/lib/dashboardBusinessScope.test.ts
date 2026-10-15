import { expect, it } from 'vitest';
import { demoScopedBusinesses, resolveDashboardBusinessScope } from './dashboardBusinessScope';
it('uses the explicit parent as network scope', () => {
  expect(resolveDashboardBusinessScope({id:'network', network_id:'network', name:'Сеть'})).toEqual({kind:'network', id:'network', name:'Сеть'});
});
it('keeps a branch scope even if its name resembles a parent', () => {
  expect(resolveDashboardBusinessScope({id:'branch', network_id:'network', name:'Материнская точка'})).toEqual({kind:'business', id:'branch', name:'Материнская точка'});
});

it('keeps a public demo network parent inside its authorized business scope', () => {
  const business = {id:'network', network_id:'network', name:'Demo'};
  const kinds: Array<'business' | 'network' | undefined> = [undefined, 'business', 'network'];
  for (const kind of kinds) {
    expect(resolveDashboardBusinessScope(business, kind, true)).toEqual({kind:'business', id:'network', name:'Demo'});
  }
});

it('does not offer inaccessible branches in a public demo', () => {
  const businesses = [{id:'root',name:'Demo'},{id:'branch',name:'Branch'}];
  expect(demoScopedBusinesses(businesses,true,'root')).toEqual([businesses[0]]);
  expect(demoScopedBusinesses(businesses,true,null)).toEqual([]);
  expect(demoScopedBusinesses(businesses,true,'missing')).toEqual([]);
  expect(demoScopedBusinesses(businesses,false,null)).toBe(businesses);
  expect(businesses).toHaveLength(2);
});
