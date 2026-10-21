import { render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { LanguageContext } from '@/i18n/LanguageContext.logic';
import { en } from '@/i18n/locales/en';
import { TelegramControlPage } from './TelegramControlPage';
const reply=(data:unknown)=>Promise.resolve(new Response(JSON.stringify(data),{status:200}));
afterEach(()=>{vi.unstubAllGlobals();window.localStorage.clear();window.sessionStorage.clear();});
it.each(['telegram','max'])('%s: opens a selected post without a second unrelated job modal',async platform=>{
 Object.defineProperty(window.HTMLElement.prototype,'scrollIntoView',{configurable:true,value:vi.fn()});
 window.history.replaceState({},'',`/${platform}/control`);
 window.localStorage.setItem('localos-mini-onboarding-v3:qa-owner','completed');
 Object.defineProperty(window,'Telegram',{configurable:true,value:{WebApp:{initData:'qa',ready:vi.fn(),expand:vi.fn()}}});
 Object.defineProperty(window,'WebApp',{configurable:true,value:{initData:'qa'}});
 vi.stubGlobal('fetch',vi.fn((input:RequestInfo|URL)=>{
  const url=String(input);
  if(url.endsWith('/bootstrap'))return reply({user:{id:'qa-owner'},selected_scope:{kind:'business',id:'qa-business'},today_v2_enabled:false,web_session_token:'qa',navigation:[{key:'content',status:'available'},{key:'today',status:'available'}],summary:{attention_items:[]},resolved_deep_link:{screen:'content',item_type:'content_item',item_id:'qa-item'},active_job:{id:'other-job',kind:'content_plan_generate',status:'waiting_for_review',stage:'Другой план ждёт проверки',progress:100}});
  if(url.includes('/mobile/modules/content?'))return reply({status:'available',items:[{id:'qa-item',title:'Синтетический пост',draft_text:'Сохранённый текст',business_id:'qa-business'}]});
  return reply({items:[],summary:{attention_items:[]}});
 }));
 render(<LanguageContext.Provider value={{language:'ru',setLanguage:vi.fn(),t:en}}><TelegramControlPage/></LanguageContext.Provider>);
 await screen.findByText('Синтетический пост');
 expect(screen.queryByRole('dialog',{name:'Проверьте результат'})).not.toBeInTheDocument();
});
