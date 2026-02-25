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

const languageOptions = [
  { value: 'ru', label: 'Русский' },
  { value: 'en', label: 'English' },
  { value: 'es', label: 'Español' },
  { value: 'de', label: 'Deutsch' },
  { value: 'fr', label: 'Français' },
  { value: 'it', label: 'Italiano' },
  { value: 'pt', label: 'Português' },
  { value: 'zh', label: '中文' },
] as const;

export default function ServiceOptimizer({ 
  businessName, 
  businessId,
  tone: externalTone,
  language: externalLanguage,
  region: externalRegion,
  descriptionLength: externalLength,
  instructions: externalInstructions,
  hideTextInput = false,
  onServicesImported
}: { 
  businessName?: string; 
  businessId?: string;
  tone?: Tone;
  language?: 'ru' | 'en' | 'es' | 'de' | 'fr' | 'it' | 'pt' | 'zh';
  region?: string;
  descriptionLength?: number;
  instructions?: string;
  hideTextInput?: boolean;
  onServicesImported?: () => Promise<void> | void;
}) {
  const [mode, setMode] = useState<'text' | 'file'>(hideTextInput ? 'file' : 'text');
  const [text, setText] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [tone, setTone] = useState<Tone>(externalTone || 'professional');
  const [language, setLanguage] = useState<'ru' | 'en' | 'es' | 'de' | 'fr' | 'it' | 'pt' | 'zh'>(externalLanguage || 'ru');
  const [instructions, setInstructions] = useState(externalInstructions || '');
  const [region, setRegion] = useState(externalRegion || '');
  const [length, setLength] = useState(externalLength || 150);
  
  // Обновляем значения при изменении пропсов
  useEffect(() => {
    if (externalTone) setTone(externalTone);
    if (externalLanguage) setLanguage(externalLanguage);
    if (externalRegion !== undefined) setRegion(externalRegion);
    if (externalLength !== undefined) setLength(externalLength);
    if (externalInstructions !== undefined) setInstructions(externalInstructions);
  }, [externalTone, externalLanguage, externalRegion, externalLength, externalInstructions]);
  const [loading, setLoading] = useState(false);
  const [savingRecognized, setSavingRecognized] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [result, setResult] = useState<OptimizeResultService[] | null>(null);
  const [recs, setRecs] = useState<string[] | null>(null);
  const [addedServices, setAddedServices] = useState<Set<number>>(new Set());
  const [examples, setExamples] = useState<Array<{id: string, text: string}>>([]);
  const [exampleInput, setExampleInput] = useState('');
  // Состояние для отслеживания принятых оптимизаций
  const [acceptedOptimizations, setAcceptedOptimizations] = useState<Map<number, {name?: boolean, description?: boolean}>>(new Map());
  // Состояние для редактируемых значений
  const [editableValues, setEditableValues] = useState<Map<number, {name?: string, description?: string}>>(new Map());

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
    setSuccess(null);
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
        formData.append('language', language);
        if (instructions) formData.append('instructions', instructions);
        if (region) formData.append('region', region);
        formData.append('description_length', String(length));
        formData.append('recognize_only', 'true');
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
          body: JSON.stringify({
            text,
            tone,
            language,
            instructions,
            region,
            description_length: length,
            business_name: businessName || ''
          })
        });
      }
      const data = await response.json();
      if (!response.ok || data.error) {
        setError(data.error || 'Ошибка оптимизации');
      } else {
        const services = Array.isArray(data.result?.services) ? data.result.services : [];
        setResult(services);
        setRecs(Array.isArray(data.result?.general_recommendations) ? data.result.general_recommendations : []);
        if (mode === 'file' && services.length === 0) {
          setError('В файле не найдены подходящие услуги. Проверьте содержание и формат файла.');
        }
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

  // Принять оптимизированное название
  const acceptOptimizedName = (serviceIndex: number) => {
    setAcceptedOptimizations(prev => {
      const newMap = new Map(prev);
      const current = newMap.get(serviceIndex) || {};
      newMap.set(serviceIndex, { ...current, name: true });
      return newMap;
    });
  };

  // Принять оптимизированное описание
  const acceptOptimizedDescription = (serviceIndex: number) => {
    setAcceptedOptimizations(prev => {
      const newMap = new Map(prev);
      const current = newMap.get(serviceIndex) || {};
      newMap.set(serviceIndex, { ...current, description: true });
      return newMap;
    });
  };

  // Обновить редактируемое значение
  const updateEditableValue = (serviceIndex: number, field: 'name' | 'description', value: string) => {
    setEditableValues(prev => {
      const newMap = new Map(prev);
      const current = newMap.get(serviceIndex) || {};
      newMap.set(serviceIndex, { ...current, [field]: value });
      return newMap;
    });
  };

  const addServiceToList = async (serviceIndex: number, preferOriginal: boolean = false): Promise<boolean> => {
    if (!result) return false;
    const service = result[serviceIndex];
    const accepted = acceptedOptimizations.get(serviceIndex) || {};
    const editable = editableValues.get(serviceIndex) || {};
    
    try {
      const token = localStorage.getItem('auth_token');
      // Получаем business_id из пропсов или из localStorage
      const currentBusinessId = businessId || localStorage.getItem('selectedBusinessId');
      if (!currentBusinessId) {
        setError('Не выбран бизнес для сохранения услуг');
        return false;
      }
      
      // Шаг "Распознать -> записать": сохраняем оригинальные названия.
      const finalName = preferOriginal
        ? (service.original_name || service.optimized_name || '').trim()
        : (accepted.name
          ? (editable.name !== undefined ? editable.name : service.optimized_name)
          : service.original_name);

      const finalDescription = preferOriginal
        ? ((service.original_description || service.seo_description || '').trim())
        : (accepted.description
          ? (editable.description !== undefined ? editable.description : service.seo_description)
          : (service.original_description || service.seo_description));
      
      const response = await fetch(`${window.location.origin}/api/services/add`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          category: service.category || 'Общие услуги',
          name: finalName,
          description: finalDescription,
          keywords: service.keywords,
          price: service.price,
          business_id: currentBusinessId
        })
      });
      
      const data = await response.json();
      if (response.ok && data.success) {
        setAddedServices(prev => new Set([...prev, serviceIndex]));
        setError(null);
        setSuccess(null);
        return true;
      } else {
        setError(data.error || 'Ошибка добавления услуги');
        return false;
      }
    } catch (e: any) {
      setError('Ошибка добавления услуги: ' + e.message);
      return false;
    }
  };

  const saveRecognizedServices = async () => {
    if (!result || result.length === 0) {
      setError('Сначала распознайте услуги из файла');
      return;
    }

    setSavingRecognized(true);
    setError(null);
    setSuccess(null);
    try {
      let savedCount = 0;
      let failedCount = 0;
      for (let i = 0; i < result.length; i += 1) {
        if (addedServices.has(i)) continue;
        const ok = await addServiceToList(i, true);
        if (ok) {
          savedCount += 1;
        } else {
          failedCount += 1;
        }
      }

      if (savedCount > 0 && onServicesImported) {
        await onServicesImported();
      }
      if (savedCount === 0 && failedCount === 0) {
        setError('Новых услуг для записи нет');
      } else if (failedCount > 0) {
        setError(`Сохранено: ${savedCount}. Ошибок записи: ${failedCount}. Проверьте выбранный бизнес и логи.`);
      } else {
        setSuccess(`Успешно сохранено услуг: ${savedCount}`);
      }
    } catch (e: any) {
      setError(e?.message || 'Ошибка записи распознанных услуг');
    } finally {
      setSavingRecognized(false);
    }
  };

  return (
    <div className="space-y-6">
      {!hideTextInput && (
      <div>
        <h2 className="text-xl font-semibold text-gray-900 mb-1">Настройте описания услуг для карточки компании на картах</h2>
        <p className="text-sm text-gray-600">🔎 Карты и локальное SEO — это один из самых эффективных каналов продаж.</p>
        <p className="text-sm text-gray-600 mt-2">Правильные названия и описания услуг повышают видимость в поиске, клики на карточку и позиции в выдаче.</p>
        <p className="text-sm text-gray-600 mt-2">Введите услуги текстом или загрузите прайс‑лист — ИИ вернёт краткие SEO‑формулировки в строгом формате с учётом частотности запросов, ваших формулировок и вашего местоположения.</p>
        <p className="text-sm text-gray-600 mt-2">Скопируйте текст и добавьте его в карточку вашей организации на картах.</p>
      </div>
      )}

      {!hideTextInput && (
      <div className="flex gap-2">
        <Button variant={mode==='text' ? undefined : 'outline'} onClick={() => setMode('text')}>Ввод текстом</Button>
        <Button variant={mode==='file' ? undefined : 'outline'} onClick={() => setMode('file')}>Загрузка файла</Button>
      </div>
      )}

      <div className="rounded-lg border border-indigo-100 bg-indigo-50/60 p-4 space-y-4">
        <div className="text-sm font-semibold text-indigo-900">Параметры оптимизации</div>
        <div className="space-y-2">
          <div className="text-xs font-medium text-gray-700">Тон</div>
          <div className="flex flex-wrap gap-2">
            {tonePresets.map((preset) => (
              <Button
                key={preset.key}
                type="button"
                variant={tone === preset.key ? 'default' : 'outline'}
                size="sm"
                onClick={() => setTone(preset.key)}
              >
                {preset.label}
              </Button>
            ))}
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div className="space-y-1">
            <div className="text-xs font-medium text-gray-700">Язык результата</div>
            <select
              value={language}
              onChange={(e) => setLanguage(e.target.value as typeof language)}
              className="w-full rounded-md border border-gray-200 bg-white px-3 py-2 text-sm"
            >
              {languageOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </div>
          <div className="space-y-1">
            <div className="text-xs font-medium text-gray-700">Регион (опционально)</div>
            <Input
              value={region}
              onChange={(e) => setRegion(e.target.value)}
              placeholder="Например: Москва"
            />
          </div>
        </div>
        <div className="space-y-1">
          <div className="text-xs font-medium text-gray-700">Дополнительные пожелания</div>
          <Textarea
            value={instructions}
            onChange={(e) => setInstructions(e.target.value)}
            rows={3}
            placeholder="Что важно сохранить: стиль, ограничения, акценты."
          />
        </div>
        <div className="space-y-2">
          <div className="text-xs font-medium text-gray-700">Примеры формулировок (до 5)</div>
          <div className="flex gap-2">
            <Input
              value={exampleInput}
              onChange={(e) => setExampleInput(e.target.value)}
              placeholder="Пример формулировки услуги"
            />
            <Button type="button" variant="outline" onClick={addExample}>Добавить</Button>
          </div>
          {examples.length > 0 && (
            <div className="space-y-1">
              {examples.map((example) => (
                <div key={example.id} className="flex items-start justify-between gap-3 rounded border border-gray-200 bg-white px-3 py-2 text-sm">
                  <div className="break-words">{example.text}</div>
                  <Button type="button" variant="ghost" size="sm" onClick={() => deleteExample(example.id)}>Удалить</Button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {!hideTextInput && mode === 'text' && (
        <Textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={8}
          placeholder={"Например: Стрижка волос, укладка, окрашивание...\n\nСовет: Укажите желаемый тон и нюансы (материалы, УТП, район/метро)."}
        />
      )}
      
      {(!hideTextInput && mode === 'file') || hideTextInput ? (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <input
              type="file"
              id={hideTextInput ? "file-upload-compact" : "file-upload"}
              accept=".pdf,.doc,.docx,.xls,.xlsx,.csv,.txt,.png,.jpg,.jpeg"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
              className="hidden"
            />
            <Button 
              type="button" 
              variant="outline" 
              onClick={() => document.getElementById(hideTextInput ? "file-upload-compact" : "file-upload")?.click()}
            >
              {hideTextInput ? 'Загрузка файла' : 'Выберите файл'}
            </Button>
            {file && <p className="text-sm text-gray-700">Файл: {file.name}</p>}
          </div>
          {!hideTextInput && (
          <div className="bg-amber-50 border border-amber-200 rounded-md p-3">
            <p className="text-xs text-amber-800">
              <strong>⚠️ Важно:</strong> Для оптимального распознавания рекомендуется загружать файлы с <strong>до 10 услугами</strong> на фото. 
              Файлы с 14-15 услугами могут не распознаться полностью. Большее количество услуг, сомнительно, что подойдут для обработки.
            </p>
          </div>
          )}
        </div>
      ) : null}


      {error && <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-2 rounded">{error}</div>}
      {success && <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-2 rounded">{success}</div>}

      {!hideTextInput && (
      <div className="flex flex-wrap gap-2">
        <Button onClick={callOptimize} disabled={loading || (mode==='text' ? text.trim().length===0 : !file)}>
          {loading ? 'Обрабатываем…' : (mode === 'file' ? 'Распознать из файла (без SEO)' : 'Оптимизировать')}
        </Button>
        {mode === 'file' && (
          <Button
            variant="outline"
            onClick={saveRecognizedServices}
            disabled={savingRecognized || !result || result.length === 0}
          >
            {savingRecognized ? 'Записываем…' : 'Записать в услуги'}
          </Button>
        )}
        {result && mode !== 'file' && <Button variant="outline" onClick={exportCSV}>Экспорт CSV</Button>}
      </div>
      )}

      {hideTextInput && (
        <div className="flex flex-wrap gap-2">
          <Button onClick={callOptimize} disabled={loading || !file}>
            {loading ? 'Распознаем…' : 'Распознать из файла (без SEO)'}
          </Button>
          <Button
            variant="outline"
            onClick={saveRecognizedServices}
            disabled={savingRecognized || !result || result.length === 0}
          >
            {savingRecognized ? 'Записываем…' : 'Записать в услуги'}
          </Button>
        </div>
      )}

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
          {result.length === 0 ? (
            <div className="bg-amber-50 border border-amber-200 text-amber-800 px-4 py-3 rounded text-sm">
              Не удалось распознать услуги из файла. Попробуйте другой формат или файл с более чёткой структурой.
            </div>
          ) : (
          (hideTextInput || mode === 'file') ? (
            <div className="space-y-3">
              {result.map((s, i) => (
                <div key={i} className="rounded-lg border border-gray-200 bg-white p-3">
                  <div className="font-semibold text-gray-900 break-words whitespace-normal">
                    {s.original_name || s.optimized_name || '—'}
                  </div>
                  {(s.original_description || s.seo_description) && (
                    <div className="mt-1 text-sm text-gray-600 break-words whitespace-normal">
                      {s.original_description || s.seo_description}
                    </div>
                  )}
                  <div className="mt-2 flex flex-wrap gap-2 text-sm text-gray-700">
                    <span className="font-medium">Цена:</span>
                    <span>{s.price ? String(s.price) : '—'}</span>
                    {Array.isArray(s.keywords) && s.keywords.length > 0 && (
                      <>
                        <span className="font-medium">Ключевые слова:</span>
                        <span className="break-words whitespace-normal">{s.keywords.join(', ')}</span>
                      </>
                    )}
                  </div>
                  {!addedServices.has(i) ? (
                    <div className="mt-3">
                      <Button size="sm" variant="outline" onClick={() => addServiceToList(i, true)}>
                        Добавить в список услуг
                      </Button>
                    </div>
                  ) : (
                    <div className="mt-3 text-sm text-green-600">✓ Добавлено</div>
                  )}
                </div>
              ))}
            </div>
          ) : (
          <div className="overflow-x-auto w-full">
            <table className="w-full table-fixed text-sm">
              <thead>
                <tr className="text-left text-gray-600">
                  <th className="p-2">Название</th>
                  <th className="p-2">Статус названия</th>
                  <th className="p-2">Описание</th>
                  <th className="p-2">Статус описания</th>
                  <th className="p-2">Ключевые слова</th>
                  <th className="p-2">Цена</th>
                  <th className="p-2">Действие</th>
                </tr>
              </thead>
              <tbody>
                {result.map((s, i) => {
                  const accepted = acceptedOptimizations.get(i) || {};
                  const editable = editableValues.get(i) || {};
                  const displayName = accepted.name 
                    ? (editable.name !== undefined ? editable.name : s.optimized_name)
                    : s.original_name;
                  const displayDescription = accepted.description
                    ? (editable.description !== undefined ? editable.description : s.seo_description)
                    : (s.original_description || s.seo_description);
                  
                  return (
                    <tr key={i} className="border-t">
                      <td className="p-2 align-top min-w-0">
                        <div className="space-y-2">
                          <div className="text-gray-800 font-medium break-words whitespace-normal">{s.original_name}</div>
                          {!accepted.name && (
                            <div className="space-y-1">
                              <div className="text-sm text-green-700 bg-green-50 p-2 rounded border border-green-200">
                                <div className="font-medium mb-1">SEO название:</div>
                                <Textarea
                                  value={editable.name !== undefined ? editable.name : s.optimized_name}
                                  onChange={(e) => updateEditableValue(i, 'name', e.target.value)}
                                  rows={2}
                                  className="text-sm w-full max-w-full"
                                />
                                <Button
                                  size="sm"
                                  variant="outline"
                                  onClick={() => acceptOptimizedName(i)}
                                  className="mt-1 text-xs"
                                >
                                  ✓ Принять
                                </Button>
                              </div>
                            </div>
                          )}
                          {accepted.name && (
                            <div className="text-sm text-green-600">
                              ✓ Используется: {displayName}
                            </div>
                          )}
                        </div>
                      </td>
                      <td className="p-2 align-top min-w-0">
                        {accepted.name ? (
                          <span className="text-green-600 text-sm">✓ Принято</span>
                        ) : (
                          <span className="text-gray-400 text-sm">Ожидает принятия</span>
                        )}
                      </td>
                      <td className="p-2 align-top min-w-0">
                        <div className="space-y-2">
                          <div className="text-gray-600 text-sm break-words whitespace-normal">{s.original_description || '-'}</div>
                          {!accepted.description && s.seo_description && (
                            <div className="space-y-1">
                              <div className="text-sm text-green-700 bg-green-50 p-2 rounded border border-green-200">
                                <div className="font-medium mb-1">SEO описание:</div>
                                <Textarea
                                  value={editable.description !== undefined ? editable.description : s.seo_description}
                                  onChange={(e) => updateEditableValue(i, 'description', e.target.value)}
                                  rows={3}
                                  className="text-sm w-full max-w-full"
                                />
                                <Button
                                  size="sm"
                                  variant="outline"
                                  onClick={() => acceptOptimizedDescription(i)}
                                  className="mt-1 text-xs"
                                >
                                  ✓ Принять
                                </Button>
                              </div>
                            </div>
                          )}
                          {accepted.description && (
                            <div className="text-sm text-green-600">
                              ✓ Используется: {displayDescription.substring(0, 50)}...
                            </div>
                          )}
                        </div>
                      </td>
                      <td className="p-2 align-top min-w-0">
                        {accepted.description ? (
                          <span className="text-green-600 text-sm">✓ Принято</span>
                        ) : (
                          <span className="text-gray-400 text-sm">Ожидает принятия</span>
                        )}
                      </td>
                      <td className="p-2 align-top text-gray-600 break-words whitespace-normal">{(s.keywords||[]).join(', ')}</td>
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
                  );
                })}
              </tbody>
            </table>
          </div>
          )
          )}
        </div>
      )}
    </div>
  );
}
