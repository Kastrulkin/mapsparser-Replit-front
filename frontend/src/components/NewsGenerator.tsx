import React, { useEffect, useState } from 'react';
import { Button } from './ui/button';
import { Textarea } from './ui/textarea';
import { Input } from './ui/input';

type ServiceLite = { id: string; name: string };

export default function NewsGenerator({ services }: { services: ServiceLite[] }) {
  const [useService, setUseService] = useState(false);
  const [serviceId, setServiceId] = useState<string>('');
  const [rawInfo, setRawInfo] = useState('');
  const [loading, setLoading] = useState(false);
  const [generated, setGenerated] = useState<string>('');
  const [news, setNews] = useState<any[]>([]);
  const [exampleInput, setExampleInput] = useState('');
  const [examples, setExamples] = useState<{id:string, text:string}[]>([]);

  const loadNews = async () => {
    try {
      const token = localStorage.getItem('auth_token');
      const res = await fetch(`${window.location.origin}/api/news/list`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await res.json();
      if (data.success) setNews(data.news || []);
    } catch {}
  };

  useEffect(()=>{ loadNews(); }, []);
  useEffect(()=>{ (async()=>{
    try {
      const token = localStorage.getItem('auth_token');
      const res = await fetch(`${window.location.origin}/api/news-examples`, { headers: { 'Authorization': `Bearer ${token}` } });
      const data = await res.json();
      if (data.success) setExamples((data.examples||[]).map((e:any)=>({ id: e.id, text: e.text })));
    } catch {}
  })(); }, []);

  const generate = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('auth_token');
      const res = await fetch(`${window.location.origin}/api/news/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ use_service: useService, service_id: serviceId || undefined, raw_info: rawInfo })
      });
      const data = await res.json();
      if (data.success) {
        setGenerated(data.generated_text || '');
        await loadNews();
      }
    } finally {
      setLoading(false);
    }
  };

  const approve = async (id: string) => {
    const token = localStorage.getItem('auth_token');
    const res = await fetch(`${window.location.origin}/api/news/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
      body: JSON.stringify({ news_id: id })
    });
    const data = await res.json();
    if (data.success) await loadNews();
  };

  const saveEdited = async (id: string, text: string) => {
    const token = localStorage.getItem('auth_token');
    const res = await fetch(`${window.location.origin}/api/news/update`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
      body: JSON.stringify({ news_id: id, text })
    });
    const data = await res.json();
    if (data.success) await loadNews();
  };

  const addExample = async () => {
    const text = exampleInput.trim();
    if (!text) return;
    const token = localStorage.getItem('auth_token');
    const res = await fetch(`${window.location.origin}/api/news-examples`, {
      method: 'POST', headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` }, body: JSON.stringify({ text })
    });
    const data = await res.json();
    if (data.success) {
      setExampleInput('');
      const list = await fetch(`${window.location.origin}/api/news-examples`, { headers: { 'Authorization': `Bearer ${token}` } });
      const json = await list.json();
      if (json.success) setExamples((json.examples||[]).map((e:any)=>({ id: e.id, text: e.text })));
    }
  };

  const deleteExample = async (id: string) => {
    const token = localStorage.getItem('auth_token');
    const res = await fetch(`${window.location.origin}/api/news-examples/${id}`, { method: 'DELETE', headers: { 'Authorization': `Bearer ${token}` } });
    const data = await res.json();
    if (data.success) {
      const list = await fetch(`${window.location.origin}/api/news-examples`, { headers: { 'Authorization': `Bearer ${token}` } });
      const json = await list.json();
      if (json.success) setExamples((json.examples||[]).map((e:any)=>({ id: e.id, text: e.text })));
    }
  };

  return (
    <div>
      <h2 className="text-xl font-semibold text-gray-900 mb-2">Новости</h2>
      <div className="mb-3">
        <label className="block text-sm text-gray-600 mb-1">Примеры новостей (до 5)</label>
        <div className="flex gap-2">
          <Input value={exampleInput} onChange={(e)=> setExampleInput(e.target.value)} placeholder="Например: Запустили экспресс-маникюр — запись уже открыта" />
          <Button variant="outline" onClick={addExample}>Добавить</Button>
        </div>
        {examples.length>0 && (
          <ul className="mt-2 space-y-1">
            {examples.map(e => (
              <li key={e.id} className="flex items-center justify-between text-sm text-gray-700 bg-gray-50 border border-gray-200 rounded px-2 py-1">
                <span className="mr-2 truncate">{e.text}</span>
                <button className="text-xs text-red-600" onClick={()=> deleteExample(e.id)}>Удалить</button>
              </li>
            ))}
          </ul>
        )}
      </div>
      <label className="flex items-center gap-2 text-sm text-gray-700 mb-3">
        <input type="checkbox" checked={useService} onChange={(e)=> setUseService(e.target.checked)} />
        Сгенерировать новость на основе услуг
      </label>
      {useService && (
        <div className="mb-3">
          <label className="block text-sm text-gray-600 mb-1">Выберите услугу</label>
          <select className="border rounded px-2 py-2 w-full" value={serviceId} onChange={(e)=> setServiceId(e.target.value)}>
            <option value="">— выбрать —</option>
            {services.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
        </div>
      )}
      <div className="mb-3">
        <label className="block text-sm text-gray-600 mb-1">Неотформатированная информация (необязательно)</label>
        <Textarea rows={3} value={rawInfo} onChange={(e)=> setRawInfo(e.target.value)} placeholder="Например: Новый сотрудник, акция, праздник и т.п." />
      </div>
      <Button onClick={generate} disabled={loading}>{loading ? 'Генерация…' : 'Сгенерировать новость'}</Button>

      {generated && (
        <div className="mt-3 p-3 bg-blue-50 border border-blue-200 rounded text-sm text-blue-900">
          <div className="font-medium mb-1">Сгенерированный вариант</div>
          <div className="mb-2">{generated}</div>
        </div>
      )}

      <div className="mt-4">
        <div className="text-sm font-medium text-gray-900 mb-2">Ваши новости</div>
        {news.length === 0 ? (
          <div className="text-sm text-gray-500">Пока нет новостей</div>
        ) : (
          <ul className="space-y-2">
            {news.map((n:any) => (
              <li key={n.id} className="border border-gray-200 rounded p-2 text-sm">
                <Textarea rows={3} defaultValue={n.generated_text} onBlur={(e)=> saveEdited(n.id, e.target.value)} />
                <div className="mt-2 flex gap-2">
                  {!n.approved && (
                    <Button size="sm" variant="outline" onClick={()=> approve(n.id)}>Принять</Button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}


