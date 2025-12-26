import React, { useState, useEffect } from 'react';
import { Button } from './ui/button';
import { Textarea } from './ui/textarea';
import { Input } from './ui/input';

type Tone = 'friendly' | 'professional' | 'premium' | 'youth' | 'business';

interface OptimizeResultService {
  original_name: string;
  optimized_name: string;
  original_description?: string;
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

export default function ServiceOptimizer({ 
  businessName, 
  businessId,
  tone: externalTone,
  region: externalRegion,
  descriptionLength: externalLength,
  instructions: externalInstructions
}: { 
  businessName?: string; 
  businessId?: string;
  tone?: Tone;
  region?: string;
  descriptionLength?: number;
  instructions?: string;
}) {
  const [mode, setMode] = useState<'text' | 'file'>('text');
  const [text, setText] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [tone, setTone] = useState<Tone>(externalTone || 'professional');
  const [instructions, setInstructions] = useState(externalInstructions || '');
  const [region, setRegion] = useState(externalRegion || '');
  const [length, setLength] = useState(externalLength || 150);
  
  // Обновляем значения при изменении пропсов
  useEffect(() => {
    if (externalTone) setTone(externalTone);
    if (externalRegion !== undefined) setRegion(externalRegion);
    if (externalLength !== undefined) setLength(externalLength);
    if (externalInstructions !== undefined) setInstructions(externalInstructions);
  }, [externalTone, externalRegion, externalLength, externalInstructions]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<OptimizeResultService[] | null>(null);
  const [recs, setRecs] = useState<string[] | null>(null);
  const [addedServices, setAddedServices] = useState<Set<number>>(new Set());
  const [examples, setExamples] = useState<Array<{id: string, text: string}>>([]);
  const [exampleInput, setExampleInput] = useState('');

  const loadExamples = async () => {
    try {
      const token = localStorage.getItem('auth_token');
      const res = await fetch(`${window.location.origin}/api/examples`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await res.json();
      if (data.success) {
        setExamples((data.examples || []).map((e:any)=>({ id: e.id, text: e.text })));
      }
    } catch {}
  };

  useEffect(()=>{ loadExamples(); }, []);

  const addExample = async () => {
    const text = exampleInput.trim();
    if (!text) return;
    try {
      const token = localStorage.getItem('auth_token');
      const res = await fetch(`${window.location.origin}/api/examples`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ text })
      });
      const data = await res.json();
      if (data.success) {
        setExampleInput('');
        await loadExamples();
      } else {
        setError(data.error || 'Ошибка добавления примера');
      }
    } catch (e:any) {
      setError(e.message || 'Ошибка добавления примера');
    }
  };

  const deleteExample = async (id: string) => {
    try {
      const token = localStorage.getItem('auth_token');
      const res = await fetch(`${window.location.origin}/api/examples/${id}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await res.json();
      if (data.success) {
        await loadExamples();
      } else {
        setError(data.error || 'Ошибка удаления примера');
      }
    } catch (e:any) {
      setError(e.message || 'Ошибка удаления примера');
    }
  };

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
      // Получаем business_id из пропсов или из localStorage
      const currentBusinessId = businessId || localStorage.getItem('selectedBusinessId');
      
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
          price: service.price,
          business_id: currentBusinessId
        })
      });
      
      const data = await response.json();
      if (response.ok && data.success) {
        setAddedServices(prev => new Set([...prev, serviceIndex]));
        setError(null);
        // Можно добавить уведомление об успехе
      } else {
        setError(data.error || 'Ошибка добавления услуги');
      }
    } catch (e: any) {
      setError('Ошибка добавления услуги: ' + e.message);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-gray-900 mb-1">Настройте описания услуг для карточки компании на картах</h2>
        <p className="text-sm text-gray-600">🔎 Карты и локальное SEO — это один из самых эффективных каналов продаж.</p>
        <p className="text-sm text-gray-600 mt-2">Правильные названия и описания услуг повышают видимость в поиске, клики на карточку и позиции в выдаче.</p>
        <p className="text-sm text-gray-600 mt-2">Введите услуги текстом или загрузите прайс‑лист — ИИ вернёт краткие SEO‑формулировки в строгом формате с учётом частотности запросов, ваших формулировок и вашего местоположения.</p>
        <p className="text-sm text-gray-600 mt-2">Скопируйте текст и добавьте его в карточку вашей организации на картах.</p>
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
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <input
              type="file"
              id="file-upload"
              accept=".pdf,.doc,.docx,.xls,.xlsx,.csv,.txt,.png,.jpg,.jpeg"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
              className="hidden"
            />
            <Button 
              type="button" 
              variant="outline" 
              onClick={() => document.getElementById('file-upload')?.click()}
            >
              Выберите файл
            </Button>
            {file && <p className="text-sm text-gray-700">Файл: {file.name}</p>}
          </div>
          <div className="bg-amber-50 border border-amber-200 rounded-md p-3">
            <p className="text-xs text-amber-800">
              <strong>⚠️ Важно:</strong> Для оптимального распознавания рекомендуется загружать файлы с <strong>до 10 услугами</strong> на фото. 
              Файлы с 14-15 услугами могут не распознаться полностью. Большее количество услуг, сомнительно, что подойдут для обработки.
            </p>
          </div>
        </div>
      )}


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
                  <th className="p-2">Исходное название</th>
                  <th className="p-2">Оптимизированное название</th>
                  <th className="p-2">Исходное описание</th>
                  <th className="p-2">Оптимизированное описание</th>
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
                    <td className="p-2 align-top text-gray-600 text-sm">{s.original_description || '-'}</td>
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


