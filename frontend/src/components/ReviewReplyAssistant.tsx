import React, { useState, useEffect } from 'react';
import { Button } from './ui/button';
import { Textarea } from './ui/textarea';
import { Input } from './ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { useLanguage } from '@/i18n/LanguageContext';

type Tone = 'friendly' | 'professional' | 'premium' | 'youth' | 'business';

const tones: { key: Tone; label: string }[] = [
  { key: 'friendly', label: 'Дружелюбный' },
  { key: 'professional', label: 'Профессиональный' },
  { key: 'premium', label: 'Премиум' },
  { key: 'youth', label: 'Молодёжный' },
  { key: 'business', label: 'Деловой' },
];

export default function ReviewReplyAssistant({ businessName }: { businessName?: string }){
  const [tone, setTone] = useState<Tone>('professional');
  const [review, setReview] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reply, setReply] = useState('');
  const [editableReply, setEditableReply] = useState('');
  const [isEditing, setIsEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [exampleInput, setExampleInput] = useState('');
  const [examples, setExamples] = useState<{id:string, text:string}[]>([]);
  const { language: interfaceLanguage } = useLanguage();
  const [language, setLanguage] = useState<string>(interfaceLanguage);

  const LANGUAGE_OPTIONS = [
    { value: 'ru', label: 'Русский' },
    { value: 'en', label: 'English' },
    { value: 'es', label: 'Español' },
    { value: 'de', label: 'Deutsch' },
    { value: 'fr', label: 'Français' },
    { value: 'it', label: 'Italiano' },
    { value: 'pt', label: 'Português' },
    { value: 'zh', label: '中文' },
  ];

  const loadExamples = async () => {
    try {
      const token = localStorage.getItem('auth_token');
      const res = await fetch(`${window.location.origin}/api/review-examples`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await res.json();
      if (data.success) setExamples((data.examples||[]).map((e:any)=>({ id: e.id, text: e.text })));
    } catch {}
  };
  useEffect(()=>{ loadExamples(); }, []);

  const addExample = async () => {
    const text = exampleInput.trim();
    if (!text) return;
    try {
      const token = localStorage.getItem('auth_token');
      const res = await fetch(`${window.location.origin}/api/review-examples`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ text })
      });
      const data = await res.json();
      if (data.success) { setExampleInput(''); await loadExamples(); }
      else setError(data.error || 'Ошибка добавления примера');
    } catch (e:any) { setError(e.message || 'Ошибка добавления примера'); }
  };

  const deleteExample = async (id: string) => {
    try {
      const token = localStorage.getItem('auth_token');
      const res = await fetch(`${window.location.origin}/api/review-examples/${id}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await res.json();
      if (data.success) await loadExamples(); else setError(data.error || 'Ошибка удаления примера');
    } catch (e:any) { setError(e.message || 'Ошибка удаления примера'); }
  };

  const handleGenerate = async () => {
    setLoading(true); setError(null); setReply('');
    try {
      const token = localStorage.getItem('auth_token');
      const res = await fetch(`${window.location.origin}/api/reviews/reply`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ review, tone, business_name: businessName || '', language })
      });
      const data = await res.json();
      if (!res.ok || data.error){ setError(data.error || 'Ошибка генерации'); }
      else { 
        const generatedReply = data.result?.reply || '';
        setReply(generatedReply);
        setEditableReply(generatedReply);
        setIsEditing(false);
      }
    } catch (e: any) { setError(e.message || 'Ошибка запроса'); }
    finally { setLoading(false); }
  };

  const handleEditReply = () => {
    setIsEditing(true);
    setEditableReply(reply);
  };

  const handleSaveReply = async () => {
    if (!editableReply.trim()) {
      setError('Текст ответа не может быть пустым');
      return;
    }
    
    setSaving(true);
    setError(null);
    
    try {
      const token = localStorage.getItem('auth_token');
      const replyId = `reply_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
      
      const res = await fetch(`${window.location.origin}/api/review-replies/update`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ 
          replyId, 
          replyText: editableReply.trim() 
        })
      });
      
      const data = await res.json();
      if (data.success) {
        setReply(editableReply);
        setIsEditing(false);
        setError(null);
      } else {
        setError(data.error || 'Ошибка сохранения ответа');
      }
    } catch (e: any) {
      setError(e.message || 'Ошибка сохранения ответа');
    } finally {
      setSaving(false);
    }
  };

  const handleCancelEdit = () => {
    setIsEditing(false);
    setEditableReply(reply);
  };

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-gray-900">Ответы на отзывы</h3>
      <p className="text-sm text-gray-600">Вставьте отзыв клиента, выберите тон и сгенерируйте краткий корректный ответ. Без “воды” и лишних рассуждений.</p>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="space-y-2">
          <div className="flex flex-wrap gap-2">
            {tones.map(t => (
              <button key={t.key} type="button" onClick={()=> setTone(t.key)}
                className={`text-xs px-3 py-1 rounded-full border ${tone===t.key ? 'bg-blue-600 text-white border-blue-600' : 'border-gray-300 text-gray-700'}`}>
                {t.label}
              </button>
            ))}
          </div>
          <p className="text-xs text-gray-500 mt-1">
            Тон, в котором будет написан ответ.
          </p>
        </div>
        <div className="space-y-2">
          <label className="block text-sm text-gray-700 mb-1">Язык ответа</label>
          <Select value={language} onValueChange={setLanguage}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {LANGUAGE_OPTIONS.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <p className="text-xs text-gray-500 mt-1">
            Язык, на котором будет сгенерирован ответ. По умолчанию — язык интерфейса (
            {LANGUAGE_OPTIONS.find((l) => l.value === interfaceLanguage)?.label || interfaceLanguage}).
          </p>
        </div>
      </div>

      {/* Примеры ответов (до 5) */}
      <div>
        <label className="block text-sm text-gray-600 mb-1">Примеры ответов (до 5)</label>
        <div className="flex gap-2">
          <Input value={exampleInput} onChange={(e)=> setExampleInput(e.target.value)} placeholder="Например: Спасибо за отзыв! Нам важно ваше мнение" />
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

      <Textarea rows={5} value={review} onChange={(e)=> setReview(e.target.value)} placeholder="Текст отзыва клиента..." />
      {error && <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-2 rounded">{error}</div>}
      <div className="flex gap-2">
        <Button onClick={handleGenerate} disabled={loading || !review.trim()}>{loading ? 'Генерируем…' : 'Сгенерировать ответ'}</Button>
      </div>
      {reply && (
        <div className="bg-gray-50 border border-gray-200 p-3 rounded">
          <div className="text-sm text-gray-600 mb-2">Предложение ответа:</div>
          {isEditing ? (
            <div className="space-y-2">
              <Textarea 
                value={editableReply} 
                onChange={(e) => setEditableReply(e.target.value)}
                rows={3}
                className="w-full"
                placeholder="Отредактируйте ответ..."
              />
              <div className="flex gap-2">
                <Button 
                  onClick={handleSaveReply} 
                  disabled={saving || !editableReply.trim()}
                  size="sm"
                >
                  {saving ? 'Сохранение...' : 'Сохранить'}
                </Button>
                <Button 
                  onClick={handleCancelEdit} 
                  variant="outline" 
                  size="sm"
                >
                  Отмена
                </Button>
              </div>
            </div>
          ) : (
            <div className="space-y-2">
              <div className="text-gray-900">{reply}</div>
              <div className="flex gap-2">
                <Button 
                  onClick={handleEditReply} 
                  variant="outline" 
                  size="sm"
                >
                  Редактировать
                </Button>
                <Button 
                  variant="outline" 
                  size="sm"
                  onClick={() => navigator.clipboard.writeText(reply)}
                >
                  Копировать
                </Button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}


