#!/usr/bin/env python3
"""Reflect 70 canonical drafts in YouGile without reply-check tasks."""

import json, subprocess, sys
from pathlib import Path

ROOT=Path('/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре')
FINAL=ROOT/'outputs/localos-followup-batch-03-final-20260820.json'
API='/Users/alexdemyanov/.codex/skills/yougile-operations/scripts/yougile_api.py'
USER='095560dc-9f48-4150-b479-0310ebf0d1ad'; COLUMN='e26beae7-d1c8-4017-8020-4458e9069c24'
DEADLINES={'2026-08-21':1787302800000,'2026-08-24':1787562000000}

def call(method,path,payload=None):
    wrap="import ssl,certifi,runpy;ssl._create_default_https_context=lambda:ssl.create_default_context(cafile=certifi.where());runpy.run_path(%r,run_name='__main__')"%API
    cmd=[sys.executable,'-c',wrap,'request',method,path]
    if payload is not None: cmd += ['--apply','--data',json.dumps(payload,ensure_ascii=False)]
    return json.loads(subprocess.run(cmd,cwd=ROOT,check=True,capture_output=True,text=True).stdout)

def main():
    p=json.loads(FINAL.read_text(encoding='utf-8')); tasks=call('GET','/tasks?limit=1000&offset=0').get('content') or []; updated=[]; created=[]
    for x in p['items']:
        name=x['name']; expected={name.casefold(),f'сделка с {name}'.casefold()}
        matches=[t for t in tasks if t.get('type')=='deal' and not t.get('completed') and not t.get('archived') and str(t.get('title') or '').strip().casefold() in expected]
        if len(matches)>1: raise RuntimeError(f'ambiguous_yougile_deal:{name}')
        date=x.get('planned_send_date') or x.get('review_date'); touch_id=x['actual_touch_id']; cooldown=x.get('status')=='blocked_cooldown'; collision=x.get('status')=='blocked_channel_collision'
        note=(f"Второе email-касание подготовлено. Получатель: {x['recipient']}. touch_id: {touch_id}. "
              f"Плановая дата: {date}. "
              + ("Статус: blocked_channel_collision; touch_id одновременно отражён как фактическое VK-касание; email не отправлять до разбора. " if collision else ("Статус: blocked_cooldown; до 24 августа не отправлять. " if cooldown else "Статус: draft, pending_user_approval. "))
              + "Текст не утверждён, не поставлен в очередь и не отправлен. Перед отправкой нужны свежий preflight и явное разрешение. Задачу проверки ответа не создавать.")
        if matches:
            task=call('GET',f"/tasks/{matches[0]['id']}"); task_id=task['id']; desc=str(task.get('description') or '')
            if touch_id not in desc or (collision and 'blocked_channel_collision' not in desc): desc=f"{desc}\n\n{note}".strip()
            payload={'title':task.get('title'),'description':desc,'assigned':task.get('assigned') or [USER],'deadline':{'deadline':DEADLINES[date],'withTime':False}}
            call('PUT',f'/tasks/{task_id}',payload); updated.append(task_id)
        else:
            if name!='Fresh Fitness': raise RuntimeError(f'missing_yougile_deal:{name}')
            payload={'title':f'Сделка с {name}','columnId':COLUMN,'description':note,'assigned':[USER],'deadline':{'deadline':DEADLINES[date],'withTime':False}}
            result=call('POST','/tasks',payload); task_id=result['id']; created.append(task_id)
        check=call('GET',f'/tasks/{task_id}')
        if touch_id not in str(check.get('description') or '') or (check.get('deadline') or {}).get('deadline')!=DEADLINES[date]: raise RuntimeError(f'yougile_readback_failed:{name}')
    print(json.dumps({'updated_existing_deals':len(updated),'created_deal_cards':len(created),'created_reply_tasks':0,'total_reflected':len(updated)+len(created)},ensure_ascii=False))

if __name__=='__main__': main()
