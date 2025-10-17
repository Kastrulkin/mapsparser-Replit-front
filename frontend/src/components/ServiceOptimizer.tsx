import React, { useState } from 'react';
import { Button } from './ui/button';
import { Textarea } from './ui/textarea';
import { Input } from './ui/input';

type Tone = 'friendly' | 'professional' | 'premium' | 'youth' | 'business';

interface OptimizeResultService {
  original_name: string;
  optimized_name: string;
  seo_description: string;
  keywords: string[];
  price?: string | null;
  category?: string | null;
}

const tonePresets: { key: Tone; label: string; example: string }[] = [
  { key: 'friendly', label: 'Дружелюбный', example: "Сделаем вас неотразимой! Стрижка + укладка феном" },
  { key: 'professional', label: 'Профессиональный', example: "Женская стрижка любой сложности. Консультация включена" },
  { key: 'premium', label: 'Премиум', example: "Авторская стрижка от топ-стилиста. Индивидуальный подход" },
  { key: 'youth', label: 'Молодёжный', example: "Крутые стрижки и окрашивание! Следим за трендами 2025" },
  { key: 'business', label: 'Деловой', example: "Экспресс-стрижка для занятых. Без ожидания" },
];

export default function ServiceOptimizer({ businessName }: { businessName?: string }) {
  const [mode, setMode] = useState<'text' | 'file'>('text');
  const [text, setText] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [tone, setTone] = useState<Tone>('professional');
  const [instructions, setInstructions] = useState('');
  const [region, setRegion] = useState('');
  const [length, setLength] = useState(150);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<OptimizeResultService[] | null>(null);
  const [recs, setRecs] = useState<string[] | null>(null);
  const [addedServices, setAddedServices] = useState<Set<number>>(new Set());

  const callOptimize = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const token = localStorage.getItem('auth_token');
      let response: Response;
      if (mode === 'file') {
        if (!file) {
          setError('Выберите файл с услугами');
          setLoading(false);
          return;
        }
        const formData = new FormData();
        formData.append('file', file);
        formData.append('tone', tone);
        if (instructions) formData.append('instructions', instructions);
        if (region) formData.append('region', region);
        formData.append('description_length', String(length));
        response = await fetch(`${window.location.origin}/api/services/optimize`, {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${token}` },
          body: (()=>{ formData.append('business_name', businessName || ''); return formData; })(),
        });
      } else {
        response = await fetch(`${window.location.origin}/api/services/optimize`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          },
          body: JSON.stringify({ text, tone, instructions, region, description_length: length, business_name: businessName || '' })
        });
      }
      const data = await response.json();
      if (!response.ok || data.error) {
        setError(data.error || 'Ошибка оптимизации');
      } else {
        setResult(Array.isArray(data.result?.services) ? data.result.services : []);
        setRecs(Array.isArray(data.result?.general_recommendations) ? data.result.general_recommendations : []);
      }
    } catch (e: any) {
      setError(e.message || 'Ошибка запроса');
    } finally {
      setLoading(false);
    }
  };

  const exportCSV = () => {
    if (!result) return;
    const header = 'Исходное название,SEO название,SEO описание,Ключевые слова,Цена\n';
    const rows = result.map(s => `${s.original_name || ''},${s.optimized_name || ''},"${(s.seo_description || '').replace(/"/g,'""')}" ,${(s.keywords||[]).join(';')},${s.price||''}`).join('\n');
    const blob = new Blob([header + rows], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'services-optimized.csv'; a.click();
    URL.revokeObjectURL(url);
  };

  const addServiceToList = async (serviceIndex: number) => {
    if (!result) return;
    const service = result[serviceIndex];
    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(`${window.location.origin}/api/services/add`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          category: service.category || 'Общие услуги',
          name: service.optimized_name,
          description: service.seo_description,
          keywords: service.keywords,
          price: service.price
        })
      });
      
      if (response.ok) {
        setAddedServices(prev => new Set([...prev, serviceIndex]));
        // Можно добавить уведомление об успехе
      } else {
        setError('Ошибка добавления услуги');
      }
    } catch (e: any) {
      setError('Ошибка добавления услуги: ' + e.message);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-gray-900 mb-1">Настройте описания услуг для Яндекс.Карт</h2>
        <p className="text-sm text-gray-600">🔎 Карты и локальное SEO — это один из самых эффективных каналов продаж.</p>
        <p className="text-sm text-gray-600 mt-2">Правильные названия и описания услуг повышают видимость в поиске, клики на карточку и позиции в выдаче.</p>
        <p className="text-sm text-gray-600 mt-2">Введите услуги текстом или загрузите прайс‑лист — ИИ вернёт краткие SEO‑формулировки в строгом формате с учётом частотности запросов, ваших формулировок и вашего местоположения.</p>
        <p className="text-sm text-gray-600 mt-2">Скопируйте текст и добавьте его в карточку вашей организации на Яндекс.Картах.</p>
      </div>

      <div className="flex gap-2">
        <Button variant={mode==='text' ? undefined : 'outline'} onClick={() => setMode('text')}>Ввод текстом</Button>
        <Button variant={mode==='file' ? undefined : 'outline'} onClick={() => setMode('file')}>Загрузка файла</Button>
      </div>

      {mode === 'text' ? (
        <Textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={8}
          placeholder={"Например: Стрижка волос, укладка, окрашивание...\n\nСовет: Укажите желаемый тон и нюансы (материалы, УТП, район/метро)."}
        />
      ) : (
        <div>
          <Input type="file" accept=".pdf,.doc,.docx,.xls,.xlsx,.csv,.txt,.png,.jpg,.jpeg" onChange={(e)=> setFile(e.target.files?.[0] || null)} />
          {file && <p className="text-xs text-gray-500 mt-1">Файл: {file.name}</p>}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div>
          <label className="block text-sm text-gray-600 mb-1">Тон</label>
          <div className="flex flex-wrap gap-2">
            {tonePresets.map(p => (
              <button key={p.key} type="button" onClick={()=>setTone(p.key)}
                className={`text-xs px-3 py-1 rounded-full border ${tone===p.key ? 'bg-blue-600 text-white border-blue-600' : 'border-gray-300 text-gray-700'}`}>
                {p.label}
              </button>
            ))}
          </div>
          <p className="text-xs text-gray-500 mt-2">Примеры формулировок для выбранного тона появятся автоматически в подсказках.</p>
        </div>
        <div>
          <label className="block text-sm text-gray-600 mb-1">Регион (для локального SEO)</label>
          <Input value={region} onChange={(e)=>setRegion(e.target.value)} placeholder="Санкт‑Петербург, м. Чернышевская" />
        </div>
        <div>
          <label className="block text-sm text-gray-600 mb-1">Длина описания (символов)</label>
          <Input type="number" min={80} max={200} value={length} onChange={(e)=> setLength(Number(e.target.value)||150)} />
        </div>
      </div>

      <div>
        <label className="block text-sm text-gray-600 mb-1">Дополнительные инструкции (необязательно)</label>
        <Textarea rows={3} value={instructions} onChange={(e)=> setInstructions(e.target.value)} placeholder="Например: только безаммиачные красители; подчеркнуть опыт мастеров; указать гарантию; избегать эмодзи." />
      </div>

      {error && <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-2 rounded">{error}</div>}

      <div className="flex gap-2">
        <Button onClick={callOptimize} disabled={loading || (mode==='text' ? text.trim().length===0 : !file)}>
          {loading ? 'Обрабатываем…' : 'Оптимизировать'}
        </Button>
        {result && <Button variant="outline" onClick={exportCSV}>Экспорт CSV</Button>}
      </div>

      {result && (
        <div className="mt-4 space-y-3">
          {recs && recs.length>0 && (
            <div className="bg-blue-50 border border-blue-200 p-3 rounded">
              <div className="text-sm font-medium text-blue-900 mb-1">Общие рекомендации</div>
              <ul className="list-disc list-inside text-sm text-blue-900">
                {recs.map((r, i) => <li key={i}>{r}</li>)}
              </ul>
            </div>
          )}
          <div className="overflow-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="text-left text-gray-600">
                  <th className="p-2">Исходное</th>
                  <th className="p-2">SEO название</th>
                  <th className="p-2">SEO описание</th>
                  <th className="p-2">Ключевые слова</th>
                  <th className="p-2">Цена</th>
                  <th className="p-2">Действие</th>
                </tr>
              </thead>
              <tbody>
                {result.map((s, i) => (
                  <tr key={i} className="border-t">
                    <td className="p-2 align-top text-gray-800">{s.original_name}</td>
                    <td className="p-2 align-top text-green-700 font-medium">{s.optimized_name}</td>
                    <td className="p-2 align-top text-gray-700">{s.seo_description}</td>
                    <td className="p-2 align-top text-gray-600">{(s.keywords||[]).join(', ')}</td>
                    <td className="p-2 align-top text-gray-600">{s.price || ''}</td>
                    <td className="p-2 align-top">
                      {addedServices.has(i) ? (
                        <span className="text-green-600 text-sm">✓ Добавлено</span>
                      ) : (
                        <Button 
                          size="sm" 
                          variant="outline" 
                          onClick={() => addServiceToList(i)}
                          className="text-xs"
                        >
                          Добавить в список услуг
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}


