import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { PartnershipResultView } from './PartnershipResultView';
const leads=[{id:'new',name:'Новый партнёр',source:'file_import',created_at:'2026-10-16'}, {id:'old',name:'Прежний партнёр',source:'file_import',created_at:'2026-06-04',pipeline_status:'contacted'}];
const letters=[{id:'d',lead_id:'new',generated_text:'Сохранённое первое письмо',channel:'email'},{id:'old-d',lead_id:'old',generated_text:'Прежнее письмо'}];
beforeEach(()=>localStorage.clear());
describe('partners results first',()=>{
 it('opens latest saved group and readable letter without editing or sending', async()=>{
  const edit=vi.fn(),launch=vi.fn();render(<PartnershipResultView businessId="business" leads={leads} letters={letters} edit={edit} launch={launch} refresh={vi.fn()} />);
  expect(screen.getByText('Новый партнёр')).toBeInTheDocument();expect(screen.queryByText('Прежний партнёр')).not.toBeInTheDocument();
  await userEvent.click(screen.getByText(/Прочитать письмо/));expect(screen.getByText('Сохранённое первое письмо')).toBeVisible();expect(screen.queryByRole('textbox')).not.toBeInTheDocument();expect(edit).not.toHaveBeenCalled();expect(launch).not.toHaveBeenCalled();
 });
 it('opens history without deleting old results or changing current group', async()=>{
  render(<PartnershipResultView businessId="business" leads={leads} letters={letters} edit={vi.fn()} launch={vi.fn()} refresh={vi.fn()} />);
  await userEvent.click(screen.getByRole('button',{name:'История подборок'}));await userEvent.click(screen.getByRole('button',{name:/4 июня 2026/}));
  await userEvent.click(screen.getByRole('button',{name:'Вся подборка'}));expect(screen.getByText('Прежний партнёр')).toBeInTheDocument();expect(screen.getByRole('button',{name:'Вернуться к актуальной'})).toBeInTheDocument();
 });
 it('requires explicit entry to editing',async()=>{
  const edit=vi.fn();render(<PartnershipResultView businessId="business" leads={leads} letters={letters} edit={edit} launch={vi.fn()} refresh={vi.fn()} />);await userEvent.click(screen.getByRole('button',{name:'Изменить подборку'}));expect(edit).toHaveBeenCalledWith();
 });
});

describe('direct partner links', () => {
 it('shows an already contacted partner and its saved letter', () => {
  render(<PartnershipResultView businessId="business" leads={leads} letters={letters} focusLeadId="old" edit={vi.fn()} launch={vi.fn()} refresh={vi.fn()} />);
  expect(screen.getByText('Прежний партнёр')).toBeVisible();
  expect(screen.getByText('Прежнее письмо')).toBeVisible();
  expect(screen.getByRole('button', {name:'Вся подборка'})).toHaveAttribute('aria-pressed','true');
 });
 it('reveals a linked partner after the first page', () => {
  const many = Array.from({length:35}, (_,index) => ({id:`lead-${index}`,name:`Компания ${index}`,source:'file_import',created_at:'2026-10-16'}));
  render(<PartnershipResultView businessId="business" leads={many} letters={[{id:'last-letter',lead_id:'lead-34',generated_text:'Письмо выбранной компании'}]} focusLeadId="lead-34" edit={vi.fn()} launch={vi.fn()} refresh={vi.fn()} />);
  expect(screen.getByText('Компания 34')).toBeVisible();
  expect(screen.getByText('Письмо выбранной компании')).toBeVisible();
 });
});

it('loads the default belonging to the newly selected business', () => {
 localStorage.setItem('localos:partner-result:first', 'saved::file_import:2026-06-04');
 const view = render(<PartnershipResultView businessId="first" leads={leads} letters={letters} edit={vi.fn()} launch={vi.fn()} refresh={vi.fn()} />);
 expect(screen.queryByText('Новый партнёр')).not.toBeInTheDocument();
 view.rerender(<PartnershipResultView businessId="second" leads={leads} letters={letters} edit={vi.fn()} launch={vi.fn()} refresh={vi.fn()} />);
 expect(screen.getByText('Новый партнёр')).toBeVisible();
});
