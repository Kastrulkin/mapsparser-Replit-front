import { fireEvent, render, screen } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
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
