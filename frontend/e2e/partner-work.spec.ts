import { expect, test } from '@playwright/test';

const leadId = '05c27874-2807-407b-a87d-c25b6da63fb1';
const businessId = 'raschyoska-test';
for (const platform of ['telegram', 'max']) {
  test(`${platform}: partner voice request requires approval and returns to same partner`, async ({ page }) => {
    const errors: string[] = [];
    const mutations: string[] = [];
    const chats: Record<string, unknown>[] = [];
    let confirmations = 0;
    page.on('pageerror', error => errors.push(error.message));
    await page.route('https://telegram.org/js/telegram-web-app.js*', route => route.fulfill({ body: '' }));
    await page.route('https://st.max.ru/js/max-web-app.js*', route => route.fulfill({ body: '' }));
    await page.addInitScript(({ platform }) => {
      localStorage.setItem('localos-mini-onboarding-v3:partner-owner', 'completed');
      const open = (url: string) => document.documentElement.setAttribute('data-opened-bot', url);
      const bridge = { initData:'fixture', ready() {}, expand() {}, openLink:open, openMaxLink:open, openTelegramLink:open };
      if (platform === 'max') Object.defineProperty(window,'WebApp',{value:bridge,configurable:true});
      else Object.defineProperty(window,'Telegram',{value:{WebApp:bridge},configurable:true});
    }, { platform });
    await page.route('**/api/**', async route => {
      const request=route.request(); const path=new URL(request.url()).pathname;
      if (request.method() !== 'GET') mutations.push(path);
      if (path === `/api/operator/${platform}/bootstrap`) {
        expect(request.postDataJSON()).toMatchObject({screen:'partnerships',item_type:'partner',item_id:leadId});
        return route.fulfill({json:{success:true,user:{id:'partner-owner'},web_session_token:'fixture-session',today_v2_enabled:false,
          selected_scope:{kind:'business',id:businessId,name:'Расчёска',business_ids:[businessId]},
          resolved_deep_link:{screen:'partnerships',item_type:'partner',item_id:leadId},summary:{attention_items:[]},catalog:{businesses:[],networks:[],total_choices:1},
          navigation:['today','operator','partnerships'].map(key=>({key,label:key,status:'available',group:'primary'}))}});
      }
      if (path === '/api/partnership/leads') return route.fulfill({json:{items:[{id:leadId,name:'Детская студия',selected_channel:'email',pipeline_status:'ready_for_outreach',updated_at:'2060-01-01T00:00:00Z'}],count:1,access:{allowed:true}}});
      if (path === '/api/operator/audio/config') return route.fulfill({json:{input_enabled:true,output_enabled:false}});
      if (path === '/api/operator/audio/transcriptions') return route.fulfill({status:202,json:{asset_id:'audio',job_id:'voice-job',conversation_id:'partner-conversation'}});
      if (path === '/api/operator/mobile/jobs/voice-job') return route.fulfill({json:{job:{status:'completed',result:{transcript:'Подготовь первое письмо'}}}});
      if (path === '/api/operator/chat') {
        const payload=request.postDataJSON();chats.push(payload);
        expect(payload).toMatchObject({business_id:businessId,channel:`${platform}_mini_app`,selected_object:{type:'partner',id:leadId}});
        const preparing=payload.message === 'Подготовь первое письмо';
        if (preparing) expect(payload.transcription_id).toBe('audio');
        return route.fulfill({json:{conversation_id:'partner-conversation',operator_result:{message_id:preparing?'prepare':'read',status:preparing?'approval_required':'completed',
          chat_response:preparing?'Проверим контакт и подготовим первое письмо. Отправку нужно подтвердить отдельно.':'Письмо для Детской студии: проверенный текст предложения.',
          selected_partner:{item_id:leadId,version:'partner-version'},...(preparing?{approval:{action_id:'prepare-action'}}:{})}}});
      }
      if (path === '/api/operator/actions/prepare-action/confirm') {
        confirmations++;
        return route.fulfill({json:{operator_result:{status:'completed',chat_response:'Подготовка поставлена в очередь. Письмо не отправлено.'}}});
      }
      if (path === '/api/operator/work-handoff') {
        expect(request.postDataJSON()).toMatchObject({business_id:businessId,item_id:leadId,item_type:'partner',platform});
        return route.fulfill({json:{url:`https://${platform === 'max'?'max.ru':'t.me'}/fixture_bot?start=work_partner`}});
      }
      return route.fulfill({json:{success:true,items:[],drafts:[],batches:[],counts:{},summary:{attention_items:[]}}});
    });
    const nav=Buffer.from(JSON.stringify({screen:'partnerships',scope_type:'business',scope_id:businessId,item_type:'partner',item_id:leadId})).toString('base64url');
    await page.goto(`/${platform}/control?${platform === 'max'?'WebAppStartParam':'tgWebAppStartParam'}=nav_${nav}`);
    await page.getByRole('button',{name:'Обсудить партнёра',exact:true}).click();
    await expect(page.getByText('Обсуждаем партнёра: Детская студия')).toBeVisible();
    await page.getByPlaceholder('Напишите задачу').fill('Покажи письмо');
    await page.getByPlaceholder('Напишите задачу').press('Enter');
    await expect(page.getByText('Письмо для Детской студии: проверенный текст предложения.')).toBeVisible();
    await page.getByLabel('Загрузить аудио',{exact:true}).setInputFiles({name:'voice.ogg',mimeType:'audio/ogg',buffer:Buffer.from('fixture transport')});
    await page.getByRole('button',{name:'Распознать запись',exact:true}).click();
    await expect(page.getByRole('button',{name:'Подтвердить',exact:true})).toBeVisible();
    expect(confirmations).toBe(0);
    await page.getByRole('button',{name:'Подтвердить',exact:true}).click();
    await expect(page.getByText('Подготовка поставлена в очередь. Письмо не отправлено.')).toBeVisible();
    expect(confirmations).toBe(1);expect(chats).toHaveLength(2);
    await page.getByRole('button',{name:'Вернуться к партнёру',exact:true}).click();
    await page.getByRole('button',{name:`Продолжить в боте ${platform === 'max'?'MAX':'Telegram'}`,exact:true}).click();
    await expect(page.locator('html')).toHaveAttribute('data-opened-bot',/fixture_bot/);
    expect(mutations.some(path=>path.includes('send-batches')||path.endsWith('/manual-contact')||path.endsWith('/draft-offer'))).toBe(false);
    expect(errors).toEqual([]);
  });
}
