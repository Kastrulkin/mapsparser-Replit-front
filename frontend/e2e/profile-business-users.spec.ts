import test, { expect } from './offline-test';

test('profile lists business users and grants staff access only after confirmation', async ({page},testInfo) => {
  test.setTimeout(60_000);
  let confirmed = false;
  let previews = 0;
  const errors: string[] = [];
  page.on('pageerror',error=>errors.push(error.message));
  const business = {id:'business',name:'Тестовый салон',owner_id:'owner',subscription_tier:'concierge',subscription_status:'active'};
  await page.addInitScript(() => {
    localStorage.setItem('auth_token','profile-test');localStorage.setItem('selectedBusinessId','business');localStorage.setItem('language','ru');
  });
  await page.route('**/api/**',async route=>{
    const path = new URL(route.request().url()).pathname;
    if(path === '/api/auth/me')return route.fulfill({json:{id:'owner',name:'Владелец',email:'owner@example.ru',businesses:[business]}});
    if(path === '/api/business/business')return route.fulfill({json:business});
    if(path === '/api/client-info')return route.fulfill({json:{success:true,businessName:business.name,city:'Москва',currency:'RUB',timezone:'Europe/Moscow',mapLinks:[],owner:{id:'owner',name:'Владелец',email:'owner@example.ru'}}});
    if(path === '/api/operator/business-members')return route.fulfill({json:{business_id:'business',members:[
      {id:'owner',name:'Владелец',email:'owner@example.ru',is_active:true,access:[{role:'owner',scope:'business'}]},
      {id:'network-staff',name:'Сотрудник сети',email:'network@example.ru',is_active:true,access:[{role:'manager',scope:'network'}]},
      ...(confirmed ? [{id:'anna',name:'Анна',email:'anna@example.ru',is_active:true,access:[{role:'master',scope:'business'}]}] : []),
    ]}});
    if(path === '/api/operator/business-management') {
      if(route.request().method()==='GET')return route.fulfill({json:{fields:[],roles:[{key:'master',label:'Мастер',permissions:['просмотр бизнеса','свои рабочие сведения']}],businesses:[business],can_manage_team:true,can_edit:true,profile:{values:{}}}});
      previews++;
      expect(route.request().postDataJSON().arguments).toMatchObject({email:'anna@example.ru',role:'master',scope:'business',businesses:['business'],send_invitation:true});
      return route.fulfill({json:{operator_result:{status:'approval_required',chat_response:'Анна · anna@example.ru\nМастер · Тестовый салон\nОтправить приглашение после подтверждения?',approval:{action_id:'team'}}}});
    }
    if(path === '/api/operator/actions/team/confirm') {
      confirmed=true;
      return route.fulfill({json:{success:true,operator_result:{status:'completed',chat_response:'Доступ сотрудника сохранён. Приглашение отправить не удалось.'}}});
    }
    return route.fulfill({json:{success:true,items:[],businesses:[business],services:[],mapLinks:[]}});
  });
  await page.goto('/dashboard/profile');
  await expect(page.getByRole('heading',{name:'Пользователи бизнеса'})).toBeVisible({timeout:20_000});
  await expect(page.getByText('Сотрудник сети',{exact:true})).toBeVisible();
  await expect(page.getByText('Управляющий · Через сеть',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Добавить сотрудника',exact:true}).click();
  await page.getByLabel('Имя сотрудника',{exact:true}).fill('Анна');
  await page.getByLabel('Email',{exact:true}).fill('anna@example.ru');
  await page.getByLabel('Роль',{exact:true}).selectOption('master');
  await page.getByLabel('Отправить приглашение по email после подтверждения').check();
  await page.getByRole('button',{name:'Проверить изменения',exact:true}).click();
  await expect(page.getByRole('button',{name:'Подтвердить',exact:true})).toBeVisible();
  expect(confirmed).toBe(false);expect(previews).toBe(1);
  await page.screenshot({path:testInfo.outputPath('profile-team-preview.png'),fullPage:true});
  await page.getByRole('button',{name:'Подтвердить',exact:true}).click();
  await expect(page.getByText('Мастер · Этот бизнес',{exact:true})).toBeVisible();
  await expect(page.getByText('Доступ сотрудника сохранён. Приглашение отправить не удалось.',{exact:true})).toBeVisible();
  expect(errors).toEqual([]);
});
