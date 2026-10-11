import { expect, it } from 'vitest';
import { resolveDashboardBusinessScope } from './dashboardBusinessScope';
it('uses the explicit parent as network scope', () => {
  expect(resolveDashboardBusinessScope({id:'network', network_id:'network', name:'Сеть'})).toEqual({kind:'network', id:'network', name:'Сеть'});
});
it('keeps a branch scope even if its name resembles a parent', () => {
  expect(resolveDashboardBusinessScope({id:'branch', network_id:'network', name:'Материнская точка'})).toEqual({kind:'business', id:'branch', name:'Материнская точка'});
});
