import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, it, vi } from 'vitest';
import { BusinessChangeForm, type BusinessManagementSchema } from './BusinessChangeForm';
import { newAuth } from '@/lib/auth_new';
vi.mock('@/lib/auth_new', () => ({ newAuth: { makeRequest: vi.fn() } }));
afterEach(() => { cleanup(); vi.clearAllMocks(); });
const schema: BusinessManagementSchema = {fields:[],roles:[{key:'master',label:'Мастер',permissions:['свои рабочие сведения']}],
  businesses:[{id:'b',name:'Салон',network_id:null}],can_manage_team:true,can_edit:true,profile:{values:{}}};

it('requires review before granting access and preserves a failed invitation result', async () => {
  const request=vi.mocked(newAuth.makeRequest);
  request.mockResolvedValueOnce({operator_result:{status:'approval_required',chat_response:'Анна · Мастер · Салон',approval:{action_id:'a'}}});
  request.mockResolvedValueOnce({operator_result:{status:'completed',chat_response:'Доступ сохранён. Приглашение отправить не удалось.'}});
  const saved=vi.fn();const user=userEvent.setup();
  render(<BusinessChangeForm businessId="b" kind="team" schema={schema} isRu onSaved={saved} />);
  await user.type(screen.getByLabelText('Имя сотрудника'),'Анна');
  await user.type(screen.getByLabelText('Email'),'anna@example.ru');
  await user.selectOptions(screen.getByLabelText('Роль'),'master');
  await user.click(screen.getByLabelText('Отправить приглашение по email после подтверждения'));
  await user.click(screen.getByRole('button',{name:'Проверить изменения'}));
  expect(await screen.findByRole('status')).toHaveTextContent('Анна · Мастер · Салон');
  expect(saved).not.toHaveBeenCalled();expect(request).toHaveBeenCalledTimes(1);
  const data=JSON.parse(String(request.mock.calls[0][1]?.body));
  expect(data.arguments).toMatchObject({email:'anna@example.ru',role:'master',scope:'business',businesses:['b'],send_invitation:true});
  await user.click(screen.getByRole('button',{name:'Подтвердить'}));
  expect(saved).toHaveBeenCalledWith('Доступ сохранён. Приглашение отправить не удалось.');
});

it('invalidates the visible confirmation when the recipient changes', async () => {
  vi.mocked(newAuth.makeRequest).mockResolvedValueOnce({operator_result:{status:'approval_required',chat_response:'Preview',approval:{action_id:'a'}}});
  const user=userEvent.setup();render(<BusinessChangeForm businessId="b" kind="team" schema={schema} isRu onSaved={vi.fn()} />);
  await user.type(screen.getByLabelText('Email'),'anna@example.ru');await user.selectOptions(screen.getByLabelText('Роль'),'master');
  await user.click(screen.getByRole('button',{name:'Проверить изменения'}));
  expect(await screen.findByRole('button',{name:'Подтвердить'})).toBeInTheDocument();
  await user.type(screen.getByLabelText('Email'),'x');
  expect(screen.queryByRole('button',{name:'Подтвердить'})).not.toBeInTheDocument();
});
