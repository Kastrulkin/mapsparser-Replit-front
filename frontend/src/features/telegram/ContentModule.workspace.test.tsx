import { Suspense } from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { ContentModule } from './ContentModule';
const item={id:'46d70108-0df5-42e1-a4a3-b0560caa7f3c',business_id:'meliora',title:'Пост Мелиоры',draft_text:'Реальный текст для проверки',scheduled_for:'2060-01-01',version:'version-1'};
const props={items:[item],busy:'',generate:vi.fn(),reload:vi.fn(),update:vi.fn()};
it('keeps unsaved text and its original version after a concurrent update and save rejection', async () => {
  const update=vi.fn().mockRejectedValue(new Error('Пост уже изменился'));
  const view=render(<ContentModule {...props} update={update} />);
  fireEvent.click(screen.getByRole('button',{name:'Редактировать текст'}));
  fireEvent.change(screen.getByRole('textbox',{name:'Текст публикации'}),{target:{value:'Моя незавершённая правка'}});
  view.rerender(<ContentModule {...props} items={[{...item,draft_text:'Новая версия из веба',version:'version-2'}]} update={update} />);
  expect(screen.getByRole('textbox',{name:'Текст публикации'})).toHaveValue('Моя незавершённая правка');
  fireEvent.click(screen.getByRole('button',{name:'Сохранить'}));
  expect(await screen.findByRole('alert')).toHaveTextContent('Пост уже изменился');
  expect(update.mock.calls[0][1]).toMatchObject({draft_text:'Моя незавершённая правка',expected_version:'version-1'});
  expect(screen.getByRole('textbox',{name:'Текст публикации'})).toHaveValue('Моя незавершённая правка');
});
it('opens a linked post for reading and does not automatically enter editing', () => {
  render(<ContentModule {...props} focusItemId={item.id} />);
  expect(screen.getByRole('button',{name:'Свернуть текст'})).toBeInTheDocument();
  expect(screen.queryByRole('textbox',{name:'Текст публикации'})).not.toBeInTheDocument();
});


it('keeps a linked plan post editable during rerenders and background refresh', async () => {
  HTMLElement.prototype.scrollIntoView = vi.fn();
  const focused = {...item, plan_id: 'plan-1'};
  const view = render(<Suspense fallback={null}><ContentModule {...props} items={[focused]} focusItemId={item.id} /></Suspense>);
  await screen.findByRole('button', {name:'Редактировать текст'});
  fireEvent.click(screen.getByRole('button', {name:'Редактировать текст'}));
  fireEvent.change(screen.getByRole('textbox', {name:'Текст публикации'}), {target:{value:'Незавершённая правка по ссылке'}});
  view.rerender(<Suspense fallback={null}><ContentModule {...props} items={[{...focused,version:'version-2',draft_text:'Обновлено в другом окне'}]} focusItemId={item.id} /></Suspense>);
  expect(screen.getByRole('textbox', {name:'Текст публикации'})).toHaveValue('Незавершённая правка по ссылке');
});

it('reports an open editor and prevents the top action from discarding its text', async () => {
  const onEditingChange = vi.fn();
  const planned = { ...item, plan_id: 'qa-plan', plan_title: 'План QA' };
  const view = render(<Suspense fallback={null}><ContentModule {...props} items={[planned]} onEditingChange={onEditingChange} /></Suspense>);
  fireEvent.click(await screen.findByRole('button', { name: 'Редактировать текст' }));
  fireEvent.change(screen.getByRole('textbox', { name: 'Текст публикации' }), { target: { value: 'Не терять эту правку' } });
  expect(onEditingChange).toHaveBeenLastCalledWith(true);
  const topAction = screen.getByRole('button', { name: 'Вернуться к редактированию' });
  expect(topAction).toBeEnabled();
  fireEvent.click(topAction);
  expect(screen.getByRole('textbox', { name: 'Текст публикации' })).toHaveValue('Не терять эту правку');
  fireEvent.click(screen.getByRole('button', { name: 'Отменить правки' }));
  expect(onEditingChange).toHaveBeenLastCalledWith(false);
  view.unmount();
  expect(onEditingChange).toHaveBeenLastCalledWith(false);
});

afterEach(()=>vi.unstubAllGlobals());
it.each(['telegram','max'])('opens dated source analysis directly in %s without opening profile or generating a plan',async surface=>{
 window.history.replaceState({},'',`/${surface}/control`);
 const mock=vi.fn(async()=>new Response(JSON.stringify({industry_label:'Тестовый анализ',items:[],pending:[],can_manage:true,can_moderate:false,settings_version:1}),{status:200}));vi.stubGlobal('fetch',mock);
 render(<ContentModule {...props} scope={{kind:'business',id:'qa-business'}}/>);
 fireEvent.click(screen.getByRole('button',{name:'Источники и подходы',exact:true}));
 await screen.findByRole('heading',{name:'Источники и подходы',exact:true});
 expect(screen.queryByRole('heading',{name:'Настроить контент'})).not.toBeInTheDocument();
 await screen.findByText('Тестовый анализ');
 expect(mock.mock.calls.every(([input])=>String(input).includes('/content-voice/references?'))).toBe(true);
 window.history.replaceState({},'','/');
});
