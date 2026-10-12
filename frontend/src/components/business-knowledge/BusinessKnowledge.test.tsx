import { useState } from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { BusinessKnowledge,formatKnowledgeValue } from './BusinessKnowledge';
import type { KnowledgeData, KnowledgeRecord } from './types';

vi.mock('@/i18n/LanguageContext.logic',()=>({useLanguage:()=>({language:'ru'})}));
const field:KnowledgeRecord={id:'chairs',kind:'field',record_key:'chairs',scope_type:'business',scope_id:'a',payload_json:{label:'Парикмахерские кресла',type:'integer',group:'Помещение',unit:'шт.',min:0},version:1,audience:'team',archived:false,updated_at:'2026-10-12T08:00:00Z',updated_by:'owner'};
const fixture=(name='Салон'):KnowledgeData=>({enabled:true,name,can_edit:true,can_configure:true,fields:[field],rules:[],documents:[],members:[],editors:[],existing_sources:[]});
const json=(body:unknown,status=200)=>Promise.resolve(new Response(JSON.stringify(body),{status,headers:{'Content-Type':'application/json'}}));
let fetchMock:ReturnType<typeof vi.fn>;
const mount=(url='/dashboard/profile?section=knowledge')=>render(<MemoryRouter initialEntries={[url]}><BusinessKnowledge scope={{type:'business',id:'a'}} /></MemoryRouter>);
beforeEach(()=>{fetchMock=vi.fn(()=>json(fixture()));vi.stubGlobal('fetch',fetchMock);vi.stubGlobal('crypto',{randomUUID:()=>Math.random().toString()});Element.prototype.scrollIntoView=vi.fn();});

describe('knowledge meaning and forms',()=>{
  it('distinguishes absent, zero and not applicable',()=>{
    expect(formatKnowledgeValue()).toBe('Не указано');
    expect(formatKnowledgeValue({...field,payload_json:{state:'set',value:0}})).toBe('0');
    expect(formatKnowledgeValue({...field,payload_json:{state:'not_applicable'}})).toBe('Не применяется');
  });
  it('saves zero explicitly with the source and original field identity',async()=>{
    mount();await screen.findByText('Парикмахерские кресла');
    fireEvent.click(screen.getByRole('button',{name:'Изменить'}));
    fireEvent.change(screen.getByLabelText('Состояние значения'),{target:{value:'set'}});
    fireEvent.change(screen.getByRole('spinbutton'),{target:{value:'0'}});
    fireEvent.click(screen.getByRole('button',{name:'Сохранить сведения'}));
    await waitFor(()=>expect(fetchMock).toHaveBeenCalledWith(expect.any(String),expect.objectContaining({method:'POST'})));
    const request=fetchMock.mock.calls.find((args)=>args[1]?.method==='POST');
    expect(JSON.parse(request?.[1].body).payload).toMatchObject({field_id:'chairs',value:0,state:'set'});
  });
  it('opens a linked rule and keeps navigation free of writes',async()=>{
    const rule={...field,id:'rule',kind:'rule',payload_json:{label:'Условия приёма',text:'Только по записи'}};
    fetchMock.mockImplementation(()=>json({...fixture(),rules:[rule]}));
    mount('/dashboard/profile?section=knowledge&rule=rule&return_to=%2Fdashboard%2Fcontent%3Fitem_id%3D7');
    await screen.findByText('Только по записи');
    expect(screen.getByRole('tab',{name:'Правила и особенности'})).toHaveAttribute('data-state','active');
    expect(fetchMock.mock.calls.every(args=>!args[1]?.method)).toBe(true);
  });
  it('gives a useful first action without inserting a template automatically',async()=>{
    fetchMock.mockImplementation(()=>json({...fixture(),fields:[]}));mount();
    await screen.findByRole('button',{name:'Добавить сведения'});
    expect(fetchMock.mock.calls).toHaveLength(1);
  });
  it('selects a MiniApp record without a write or editing permission',async()=>{
    const rule={...field,id:'rule',kind:'rule',payload_json:{label:'Правило сети',text:'Только по записи'}};
    fetchMock.mockImplementation(()=>json({...fixture(),can_edit:false,can_configure:false,rules:[rule]}));
    render(<MemoryRouter><BusinessKnowledge embedded scope={{type:'business',id:'a'}} focusRecordId="rule" /></MemoryRouter>);
    await screen.findByText('Только по записи');
    expect(screen.getByRole('tab',{name:'Правила и особенности'})).toHaveAttribute('data-state','active');
    expect(screen.queryByRole('button',{name:'Добавить правило'})).not.toBeInTheDocument();
    expect(fetchMock.mock.calls.every(args=>!args[1]?.method)).toBe(true);
  });
  it('prepares a journal change before requiring a separate confirmation',async()=>{
    fetchMock.mockImplementation((url:string)=>url.includes('/preview')?json({approval:{action_id:'review',business_id:'a'},preview:{after:{state:'not_applicable'}}}):url.includes('/actions/')?json({success:true,operator_result:{status:'completed'}}):json(fixture()));
    mount('/dashboard/profile?section=knowledge&field=chairs&source_entry=journal-entry');
    await screen.findByText('Парикмахерские кресла');
    fireEvent.click(screen.getByRole('button',{name:'Изменить'}));
    fireEvent.change(screen.getByLabelText('Состояние значения'),{target:{value:'not_applicable'}});
    fireEvent.click(screen.getByRole('button',{name:'Сохранить сведения'}));
    const confirm=await screen.findByRole('button',{name:'Подтвердить изменение'});
    expect(screen.getByText('Не применяется')).toBeInTheDocument();
    expect(fetchMock.mock.calls.filter(args=>args[1]?.method==='POST')).toHaveLength(1);
    const preview=fetchMock.mock.calls.find(args=>args[0].includes('/preview'));
    expect(JSON.parse(preview?.[1].body).source_entry_id).toBe('journal-entry');
    fireEvent.click(confirm);
    await screen.findByText('Изменение из журнала подтверждено и сохранено.');
    expect(fetchMock.mock.calls.some(args=>args[0].includes('/actions/review/confirm'))).toBe(true);
  });
});

describe('scope and failures',()=>{
  it('does not open an old uploaded document after switching context during refresh',async()=>{
    let uploaded=false;let resolveRefresh:(value:Response)=>void=()=>undefined;
    const oldDocument={...field,id:'private-doc',kind:'document',payload_json:{label:'Приватный документ старой точки',text:'Старый приватный текст',status:'needs_review'}};
    fetchMock.mockImplementation((url:string,options:RequestInit)=>{
      if(options?.method==='POST'){uploaded=true;return json({record:oldDocument});}
      if(url.includes('scope_id=b'))return json(fixture('Новая точка'));
      if(uploaded)return new Promise<Response>(resolve=>{resolveRefresh=resolve;});
      return json(fixture());
    });
    function Switch(){const [id,setId]=useState('a');return <><button onClick={()=>setId('b')}>Сменить контекст</button><BusinessKnowledge scope={{type:'business',id}} /></>;}
    render(<MemoryRouter><Switch /></MemoryRouter>);
    await screen.findByText('Парикмахерские кресла');
    fireEvent.mouseDown(screen.getByRole('tab',{name:'Документы'}),{button:0,ctrlKey:false});
    fireEvent.click(await screen.findByRole('button',{name:'Загрузить документ'}));
    fireEvent.change(screen.getByLabelText('Документ'),{target:{files:[new File(['Private'],'policy.txt',{type:'text/plain'})]}});
    const uploadForm=screen.getByRole('button',{name:'Загрузить и проверить текст'}).closest('form');
    if(!uploadForm)throw new Error('Missing upload form');
    fireEvent.submit(uploadForm);
    await waitFor(()=>expect(uploaded).toBe(true));
    fireEvent.click(screen.getByText('Сменить контекст'));await screen.findByText(/Новая точка/);
    await act(async()=>resolveRefresh(new Response(JSON.stringify({...fixture(),documents:[oldDocument]}))));
    expect(screen.queryByText('Приватный документ старой точки')).not.toBeInTheDocument();
    expect(screen.queryByDisplayValue('Старый приватный текст')).not.toBeInTheDocument();
  });
  it('retries the same edit with its original request identifier after a lost response',async()=>{
    mount();await screen.findByText('Парикмахерские кресла');
    fireEvent.click(screen.getByRole('button',{name:'Изменить'}));
    fireEvent.change(screen.getByLabelText('Состояние значения'),{target:{value:'set'}});
    fireEvent.change(screen.getByRole('spinbutton'),{target:{value:'6'}});
    fetchMock.mockImplementation((url:string,options:RequestInit)=>options?.method==='POST'?Promise.reject(new Error('Ответ потерян')):json(fixture()));
    fireEvent.click(screen.getByRole('button',{name:'Сохранить сведения'}));
    await screen.findByText(/Ответ потерян/);
    fireEvent.click(screen.getByRole('button',{name:'Сохранить сведения'}));
    await waitFor(()=>expect(fetchMock.mock.calls.filter(args=>args[1]?.method==='POST')).toHaveLength(2));
    const requests=fetchMock.mock.calls.filter(args=>args[1]?.method==='POST').map(args=>JSON.parse(args[1].body));
    expect(requests[0].request_id).toBe(requests[1].request_id);
  });
  it('ignores a late old response after a rapid context change',async()=>{
    let resolveOld:(value:Response)=>void=()=>undefined;
    fetchMock.mockImplementation((url:string)=>url.includes('scope_id=a')?new Promise<Response>(resolve=>{resolveOld=resolve;}):json(fixture('Школа')));
    function ScopeSwitch(){const [id,setId]=useState('a');return <><button onClick={()=>setId('b')}>Сменить бизнес</button><BusinessKnowledge scope={{type:'business',id}} /></>;}
    render(<MemoryRouter><ScopeSwitch /></MemoryRouter>);
    fireEvent.click(screen.getByText('Сменить бизнес'));await screen.findByText(/Школа/);
    await act(async()=>resolveOld(new Response(JSON.stringify(fixture('Старый салон')))));
    expect(screen.queryByText(/Старый салон/)).not.toBeInTheDocument();
  });
  it('retains current data on refresh failure and clears on lost access',async()=>{
    mount();await screen.findByText('Парикмахерские кресла');
    fetchMock.mockImplementation(()=>json({error:'Временный сбой'},503));fireEvent.click(screen.getByRole('button',{name:'Обновить'}));
    await screen.findByRole('alert');expect(screen.getByText('Парикмахерские кресла')).toBeInTheDocument();
    fetchMock.mockImplementation(()=>json({error:'Доступ отозван'},403));fireEvent.click(screen.getByRole('button',{name:'Повторить'}));
    await waitFor(()=>expect(screen.queryByText('Парикмахерские кресла')).not.toBeInTheDocument());
  });
  it('shows an explicit server unavailable state without a false empty start',async()=>{
    fetchMock.mockImplementation(()=>json({...fixture(),enabled:false,fields:[]}));mount();
    await screen.findByText(/Раздел ещё не установлен/);expect(screen.queryByRole('button',{name:'Добавить сведения'})).not.toBeInTheDocument();
  });
});
