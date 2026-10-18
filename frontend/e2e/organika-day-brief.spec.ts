import { expect, test } from '@playwright/test';

for (const platform of ['telegram', 'max']) {
  test(`${platform}: voice focus, recipient review, approval, bot return and employee completion`, async ({ page }, testInfo) => {
    const errors: string[] = [];
    let confirmed = false;
    let employee = false;
    let done = false;
    let confirmations = 0;
    let saves = 0;
    let focus = '';
    page.on('pageerror', error => errors.push(error.message));
    await page.route('https://telegram.org/js/telegram-web-app.js*', route => route.fulfill({ body: '' }));
    await page.route('https://st.max.ru/js/max-web-app.js*', route => route.fulfill({ body: '' }));
    await page.addInitScript(({ platform }) => {
      localStorage.setItem('localos-mini-onboarding-v3:organika-owner', 'completed');
      localStorage.setItem('localos-mini-onboarding-v3:organika-employee', 'completed');
      const open = (url: string) => document.documentElement.setAttribute('data-opened-bot', url);
      const bridge = { initData:'fixture', ready() {}, expand() {}, openLink:open, openMaxLink:open, openTelegramLink:open };
      if (platform === 'max') Object.defineProperty(window, 'WebApp', {value:bridge,configurable:true});
      else Object.defineProperty(window, 'Telegram', {value:{WebApp:bridge},configurable:true});
    }, { platform });
    const tasks = [{ id:'task-one', text:'Подготовить материалы', done:false }];
    const draft = () => saves ? { id:'record',focus,date:'2026-10-17',version:1,status:confirmed?'assigned':'draft',recipients:[{user_id:'organika-employee',platforms:[platform],tasks}] } : null;
    await page.route('**/api/**', async route => {
      const request = route.request(); const path = new URL(request.url()).pathname;
      if (path === `/api/operator/${platform}/bootstrap`) return route.fulfill({json:{success:true,user:{id:employee?'organika-employee':'organika-owner'},web_session_token:'fixture',today_v2_enabled:false,
        selected_scope:{kind:'business',id:'organika-test',name:'Органика',business_ids:['organika-test']},resolved_deep_link:{screen:'work_journal',item_type:'day_brief',item_id:'record'},
        summary:{attention_items:[]},catalog:{businesses:[],networks:[],total_choices:1},navigation:['today','operator','work_journal'].map(key=>({key,label:key,status:'available',group:'primary'}))}});
      if (path === '/api/work-journal') return route.fulfill({json:{enabled:true,role:employee?'member':'owner',items:[]}});
      if (path === '/api/operator/audio/config') return route.fulfill({json:{input_enabled:true,output_enabled:false}});
      if (path === '/api/operator/audio/transcriptions') return route.fulfill({status:202,json:{asset_id:'audio',job_id:'voice-job',conversation_id:'voice-conversation'}});
      if (path === '/api/operator/mobile/jobs/voice-job') return route.fulfill({json:{job:{status:'completed',result:{transcript:'Внимательно встречаем новых клиентов.'}}}});
      if (path === '/api/operator/day-brief') {
        if (request.method() === 'POST') { const body=request.postDataJSON();expect(body).toMatchObject({business_id:'organika-test',channel:`${platform}_mini_app`,transcription_id:'audio'});focus=body.focus;saves++;return route.fulfill({json:{draft:draft()}}); }
        return route.fulfill({json:{date:'2026-10-17',user_id:employee?'organika-employee':'organika-owner',can_manage:!employee,can_complete:true,delivery_enabled:false,draft:employee?null:draft(),
          members:employee?[]:[{id:'organika-employee',name:'Анна',platforms:[platform]}],assignments:confirmed?[{id:'assignment',user_id:'organika-employee',version:done?2:1,status:done?'completed':'ready',payload_json:{date:'2026-10-17',focus,tasks:tasks.map(task=>({...task,done})),tips:[{main_service:'Окрашивание',service:'Уход',wording:'Хотите добавить подходящий уход?'}],note:'Проверьте свободное время.'}}]:[]}});
      }
      if (path === '/api/operator/day-brief/preview') { expect(confirmed).toBe(false);return route.fulfill({json:{approval:{action_id:'approval'},day_brief_preview:{delivery_enabled:false,messages:[{user_id:'organika-employee',name:'Анна',platforms:[platform],text:'Фокус дня: '+focus+'\nПодготовить материалы.\nХотите добавить подходящий уход?\nПроверьте свободное время.'}]}}}); }
      if (path === '/api/operator/actions/approval/confirm') { confirmed=true;confirmations++;return route.fulfill({json:{operator_result:{status:'completed',chat_response:'Задачи доступны сотруднику. Уведомления выключены.'}}}); }
      if (path === '/api/operator/day-brief/task') { expect(employee).toBe(true);expect(request.postDataJSON()).toMatchObject({action_id:'assignment',task_id:'task-one',done:true});done=true;return route.fulfill({json:{status:'completed'}}); }
      if (path === '/api/operator/work-handoff') { expect(request.postDataJSON()).toMatchObject({item_type:'day_brief',platform});return route.fulfill({json:{url:`https://${platform==='max'?'max.ru':'t.me'}/fixture_bot?start=work_day`}}); }
      return route.fulfill({json:{success:true,items:[],summary:{attention_items:[]}}});
    });
    const nav=Buffer.from(JSON.stringify({screen:'work_journal',scope_type:'business',scope_id:'organika-test',item_type:'day_brief',item_id:'record'})).toString('base64url');
    const url=`/${platform}/control?${platform==='max'?'WebAppStartParam':'tgWebAppStartParam'}=nav_${nav}`;
    await page.goto(url);
    const panel=page.locator('section[aria-label="Планёрка дня"]');
    await expect(panel.getByText('Анна',{exact:true})).toBeVisible();
    await panel.getByLabel('Загрузить аудио',{exact:true}).setInputFiles({name:'focus.ogg',mimeType:'audio/ogg',buffer:Buffer.from('fixture audio')});
    await panel.getByRole('button',{name:'Распознать запись',exact:true}).click();
    await panel.getByRole('button',{name:'Вставить в фокус дня',exact:true}).click();
    await expect(panel.getByLabel('Фокус дня',{exact:true})).toHaveValue('Внимательно встречаем новых клиентов.');
    expect(saves).toBe(0);expect(confirmations).toBe(0);
    await panel.getByLabel('Анна',{exact:true}).check();
    await panel.getByLabel('Задачи для Анна, каждая с новой строки').fill('Подготовить материалы');
    await panel.getByRole('button',{name:'Проверить перед передачей',exact:true}).click();
    await expect(panel.getByRole('button',{name:'Подтвердить передачу задач',exact:true})).toBeVisible();
    await expect(panel.getByText(/Хотите добавить подходящий уход/)).toBeVisible();
    expect(confirmations).toBe(0);
    await page.screenshot({ path: '/tmp/organika-' + platform + '-' + testInfo.project.name + '.png', fullPage: true });
    await panel.getByRole('button',{name:'Подтвердить передачу задач',exact:true}).click();
    await expect(panel.getByText('Задачи доступны сотруднику. Уведомления выключены.')).toBeVisible();
    expect(confirmations).toBe(1);
    await panel.getByRole('button',{name:`Продолжить в боте ${platform==='max'?'MAX':'Telegram'}`,exact:true}).click();
    await expect(page.locator('html')).toHaveAttribute('data-opened-bot',/work_day/);
    employee=true;
    const employeeNav=Buffer.from(JSON.stringify({screen:'work_journal',scope_type:'business',scope_id:'organika-test',item_type:'day_brief',item_id:'assignment'})).toString('base64url');
    await page.goto(`/${platform}/control?${platform==='max'?'WebAppStartParam':'tgWebAppStartParam'}=nav_${employeeNav}`);
    await expect(panel.getByText('Подготовить материалы',{exact:true})).toBeVisible();
    expect(await panel.getByLabel('Фокус дня',{exact:true}).count()).toBe(0);
    await panel.getByRole('checkbox').check();
    await expect.poll(()=>done).toBe(true);
    await expect(panel.getByRole('checkbox')).toBeChecked();
    expect(errors).toEqual([]);
  });
}
