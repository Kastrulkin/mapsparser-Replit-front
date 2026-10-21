import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, it, vi } from 'vitest';
import { LanguageContext } from '@/i18n/LanguageContext.logic';
import { en } from '@/i18n/locales/en';
import { TelegramControlPage } from './TelegramControlPage';

const respond = (data: unknown) => Promise.resolve(new Response(JSON.stringify(data), { status: 200, headers: { 'Content-Type': 'application/json' } }));
afterEach(() => { cleanup(); vi.unstubAllGlobals(); window.localStorage.clear(); window.sessionStorage.clear(); });

for (const platform of ['telegram','max']) it(platform + ': preserves the content editor when menu, back or business switch is requested', async () => {
  window.history.replaceState({},'', '/' + platform + '/control');
  window.localStorage.setItem('localos-mini-onboarding-v3:qa-owner','completed');
  window.sessionStorage.clear();
  Object.defineProperty(window,'Telegram',{ configurable:true,value:{WebApp:{initData:'qa-init',ready:vi.fn(),expand:vi.fn()}} });
  Object.defineProperty(window,'WebApp',{ configurable:true,value:{initData:'qa-init'} });
  vi.stubGlobal('fetch',vi.fn((input:RequestInfo|URL) => {
    const url=String(input);
    if(url.endsWith('/bootstrap'))return respond({success:true,user:{id:'qa-owner',name:'QA'},web_session_token:'qa-session',today_v2_enabled:false,selected_scope:{kind:'business',id:'business-qa',name:'Тестовый бизнес',business_ids:['business-qa'],can_switch:true},summary:{attention_items:[]},catalog:{businesses:[{id:'business-qa',name:'Тестовый бизнес'},{id:'business-other',name:'Другой бизнес'}],networks:[],total_choices:2},navigation:[{key:'today',label:'Сегодня',group:'primary',status:'available'},{key:'content',label:'Контент',group:'tools',status:'available'},{key:'operator',label:'Чат с LocalOS',group:'primary',status:'available'}]});
    if(url.includes('/mobile/modules/content?'))return respond({status:'available',items:[{id:'content-qa',title:'Синтетический пост',draft_text:'Исходный текст',scheduled_for:'2026-10-25',business_id:'business-qa'}]});
    if(url.includes('/mobile/workspace'))return respond({items:[],summary:{attention_items:[]}});
    return respond({items:[],jobs:[]});
  }));
  const user=userEvent.setup();
  render(<LanguageContext.Provider value={{language:'ru',setLanguage:vi.fn(),t:en}}><TelegramControlPage/></LanguageContext.Provider>);
  await user.click(await screen.findByRole('button',{name:'Меню',exact:true}));
  await user.click(await screen.findByRole('button',{name:'Контент',exact:true}));
  await user.click(await screen.findByRole('button',{name:'Редактировать текст',exact:true}));
  await user.type(screen.getByRole('textbox',{name:'Текст публикации'}),' — несохранённая правка');
  await user.click(screen.getByRole('button',{name:'Меню',exact:true}));
  expect(screen.getByRole('textbox',{name:'Текст публикации'})).toHaveValue('Исходный текст — несохранённая правка');
  expect(screen.getByRole('alert')).toHaveTextContent('Сначала сохраните или отмените редактирование публикации');
  await user.click(screen.getByRole('button',{name:'Назад',exact:true}));
  expect(screen.getByRole('textbox',{name:'Текст публикации'})).toBeVisible();
  await user.click(screen.getByRole('button',{name:/Тестовый бизнес/}));
  expect(screen.queryByRole('heading',{name:'Где работаем?'})).not.toBeInTheDocument();
  expect(screen.getByRole('textbox',{name:'Текст публикации'})).toBeVisible();
  await user.click(screen.getByRole('button',{name:'Отменить правки',exact:true}));
  await user.click(screen.getByRole('button',{name:'Меню',exact:true}));
  expect(await screen.findByRole('heading',{name:'Меню',exact:true})).toBeVisible();
});
