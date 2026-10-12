import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import GrowthNavigation from './GrowthNavigation';
const navigation = [
 {key:'content',label:'Content',status:'available'},
 {key:'cards',label:'Cards',status:'available'},
 {key:'work_journal',label:'Journal',status:'available'},
 {key:'chats',label:'Chats',status:'available'},
 {key:'community_sources',label:'Radar',status:'available'},
] satisfies Parameters<typeof GrowthNavigation>[0]['navigation'];
describe('Telegram utility menu', () => {
 it('keeps primary work areas out of More and links discovery with scope', async () => {
  const open=vi.fn();
  render(<GrowthNavigation navigation={navigation} onOpen={open} onOpenProgress={vi.fn()} onLocked={vi.fn()} onRestartTour={vi.fn()} scope={{kind:'network',id:'network'}}/>);
  expect(screen.queryByRole('button',{name:'Content'})).not.toBeInTheDocument();
  const href=screen.getByRole('link',{name:/Пути роста/}).getAttribute('href') || '';
  expect(href).toContain('business_id=network'); expect(href).toContain('scope_type=network');
  await userEvent.click(screen.getByRole('button',{name:'Сообщения клиентов'})); expect(open).toHaveBeenCalledWith('chats');
 });
 it('explains a locked utility and calls the existing paywall',async()=>{
  const locked=vi.fn();const open=vi.fn();
  render(<GrowthNavigation navigation={[{key:'work_journal',label:'Journal',status:'read_only',reason:'Нужен тариф'}]} onOpen={open} onOpenProgress={vi.fn()} onLocked={locked} onRestartTour={vi.fn()}/>);
  await userEvent.click(screen.getByRole('button',{name:/Рабочий журнал/})); expect(open).not.toHaveBeenCalled();expect(locked).toHaveBeenCalledWith(expect.objectContaining({key:'work_journal'}));
 });
});
