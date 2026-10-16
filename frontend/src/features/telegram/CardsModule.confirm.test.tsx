import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, it, vi } from 'vitest';
import { CardsModule } from './CardsModule';

afterEach(() => vi.unstubAllGlobals());

it('shows a rejected refresh inside its still-open confirmation instead of behind it', async () => {
  const user = userEvent.setup();
  const fetch = vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({success:true,preview:{action_id:'action-1',capability:'cards.refresh',estimated_credits:10,target_businesses:[{id:'biz-1',name:'Riderra'}],changes:[{label:'Обновить данные Яндекса'}]}}),{status:200})).mockResolvedValueOnce(new Response(JSON.stringify({success:false,error:'Действие не выполнено',operator_result:{blocked_reasons:['map_organization_id_required']}}),{status:400}));
  vi.stubGlobal('fetch',fetch);
  render(<CardsModule scope={{kind:'business',id:'biz-1'}} items={[{id:'biz-1',title:'Riderra',business_id:'biz-1'}]} reload={vi.fn().mockResolvedValue(undefined)} />);
  await user.click(screen.getByRole('button',{name:/^Обновить$/}));
  const dialog = await screen.findByRole('dialog');
  await user.click(within(dialog).getByRole('button',{name:'Обновить Яндекс'}));
  expect(await within(dialog).findByRole('alert')).toHaveTextContent('Не удалось определить организацию');
  expect(within(dialog).getByRole('button',{name:'Обновить Яндекс'})).toBeEnabled();
  expect(fetch).toHaveBeenCalledTimes(2);
  expect(screen.getByText(/только данные Яндекса/)).toBeInTheDocument();
});
