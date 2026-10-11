import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route, useLocation } from 'react-router-dom';
import { workDestinations, safeWorkReturn, workChatRoute, workNavigationCopy } from './workNavigation';
import { workStatus, workStatusDetail, workStatusLabel } from './workStatus';
import { workSections } from '@/pages/dashboard/todayWorkModel';
import { targetForAccess } from '@/components/access/AccessBoundary';
import { WorkRouteAlias } from '@/components/WorkRouteAlias';
import type { Language } from '@/i18n/LanguageContext.logic';

const languages: Language[] = ['ru','en','fr','es','el','de','th','ar','ha','tr','hy'];
describe('one work navigation contract', () => {
 it('exposes six directions directly in a stable grouped order', () => {
  expect(workDestinations.filter(item => item.group === 'directions').map(item => item.id)).toEqual(['maps','content','partnerships','influencers','upsells','automation']);
  expect(workDestinations.map(item => item.id)).not.toContain('growth-paths');
  expect(new Set(workDestinations.map(item => item.mobileKey)).size).toBe(workDestinations.length);
 });
 it.each(languages)('has human labels for all destinations in %s', language => {
  const copy = workNavigationCopy(language);
  for (const item of workDestinations) expect(copy.label(item.id)).not.toBe(item.id);
  expect(copy.discuss).toBeTruthy(); expect(copy.back).toBeTruthy();
 });
 it.each(['https://example.test','//example.test','/dashboard/../../admin','/dashboard/fake','/dashboard/card\\evil','/dashboard/card\n','/login'])('rejects an unsafe return: %s', value => expect(safeWorkReturn(value)).toBeNull());
 it('preserves safe IDs, parameters and fragments and canonicalizes old work links', () => {
  expect(safeWorkReturn('/dashboard/content?item_id=7#draft')).toBe('/dashboard/content?item_id=7#draft');
  expect(safeWorkReturn('/dashboard/promotion/partnerships?lead_id=7')).toBe('/dashboard/partnerships?lead_id=7');
  const chat = new URL(workChatRoute('/dashboard/content?item_id=7','branch','action'), 'https://localos.pro');
  expect(chat.searchParams.get('work_ref')).toBe('/dashboard/content?item_id=7&business_id=branch');
  expect(chat.searchParams.get('business_id')).toBe('branch');
  expect(chat.searchParams.get('journey_action')).toBe('action');
 });
 it('redirects old addresses without losing identity or fragment', async () => {
  function Target() { const location = useLocation(); return <p>{location.pathname + location.search + location.hash}</p>; }
  render(<MemoryRouter initialEntries={['/dashboard/promotion/partnerships?business_id=b&lead_id=l#offer']}><Routes><Route path="/dashboard/promotion/partnerships" element={<WorkRouteAlias path="/dashboard/partnerships"/>}/><Route path="/dashboard/partnerships" element={<Target/>}/></Routes></MemoryRouter>);
  expect(await screen.findByText('/dashboard/partnerships?business_id=b&lead_id=l#offer')).toBeVisible();
 });
 it('distinguishes access remedies and preserves the originating task', () => {
  const access = { status: 'setup_required', reason: 'Connect', cta_label: 'Connect', cta_target: { focus: 'telegram' } } satisfies Parameters<typeof targetForAccess>[0];
  const url = new URL(targetForAccess(access, '/dashboard/content?item_id=7') || '', 'https://localos.pro');
  expect(url.pathname).toBe('/dashboard/settings'); expect(url.searchParams.get('focus')).toBe('telegram');
  expect(url.searchParams.get('return_to')).toBe('/dashboard/content?item_id=7');
  expect(targetForAccess({...access,status:'unavailable'})).toBeNull();
  expect(targetForAccess({...access,status:'payment_required'})).toContain('focus=subscription');
 });
 it('never claims approval, queue or unknown status is a confirmed result', () => {
  expect(workStatus('approved_for_send')).toBe('decision'); expect(workStatus('queued')).toBe('planned');
  expect(workStatus('future')).toBe('unknown'); expect(workStatusLabel('future','ru')).toBe('Статус не уточнён');
  expect(workStatusDetail('approved_for_send','ru')).not.toBe(workStatusDetail('sent','ru'));
 });
 it('deduplicates within a business without losing a different location', () => {
  const item = { id:'a',entity_type:'content_item',entity_id:'same',business_id:'one',title:'Draft',status:'draft',action:{url:'/dashboard/content?item_id=same'}};
  const result = workSections({ work_sections: {needs_decision:[item,{...item,id:'duplicate'},{...item,business_id:'two'}]}}, Date.now());
  expect(result.decisions).toHaveLength(2);
 });
});

 it('does not present a completed observation as a confirmed result', () => {
  const sections = workSections({work_sections:{results:[{id:'note',title:'Observation',kind:'work_observation',entity_type:'work_observation',status:'completed',occurred_at:'2026-10-11T10:00:00Z',action:{url:'/dashboard/work-journal?entry=note'}}]}},Date.parse('2026-10-11T12:00:00Z'));
  expect(sections.results).toEqual([]);
 });
