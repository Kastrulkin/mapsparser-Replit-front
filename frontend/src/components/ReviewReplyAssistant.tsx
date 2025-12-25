import React, { useState, useEffect } from 'react';
import { useOutletContext } from 'react-router-dom';
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

interface ExternalReview {
  id: string;
  source: string;
  rating: number | null;
  author_name: string;
  text: string;
  response_text: string | null;
  published_at: string | null;
  has_response: boolean;
}

export default function ReviewReplyAssistant({ businessName }: { businessName?: string }){
  const { currentBusinessId } = useOutletContext<any>();
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
  const [externalReviews, setExternalReviews] = useState<ExternalReview[]>([]);
  const [loadingReviews, setLoadingReviews] = useState(false);
  const [generatingForReviewId, setGeneratingForReviewId] = useState<string | null>(null);
  const [generatedReplies, setGeneratedReplies] = useState<Record<string, string>>({});

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

  const loadExternalReviews = async () => {
    if (!currentBusinessId) return;
    setLoadingReviews(true);
    try {
      const token = localStorage.getItem('auth_token');
      const res = await fetch(`${window.location.origin}/api/business/${currentBusinessId}/external/reviews`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await res.json();
      if (data.success) {
        setExternalReviews(data.reviews || []);
      }
    } catch (e: any) {
      console.error('Ошибка загрузки отзывов:', e);
    } finally {
      setLoadingReviews(false);
    }
  };

  useEffect(()=>{ 
    loadExamples();
    loadExternalReviews();
  }, [currentBusinessId]);

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

  const handleGenerate = async (reviewText?: string, reviewId?: string) => {
    const textToGenerate = reviewText || review;
    if (!textToGenerate.trim()) return;

    if (reviewId) {
      setGeneratingForReviewId(reviewId);
    } else {
      setLoading(true);
    }
    setError(null);
    
    try {
      const token = localStorage.getItem('auth_token');
      const res = await fetch(`${window.location.origin}/api/reviews/reply`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ 
          review: textToGenerate, 
          tone, 
          business_name: businessName || '', 
          language,
          examples: examples.map(e => e.text) // Передаём примеры для генерации
        })
      });
      const data = await res.json();
      console.log('Ответ API генерации:', data); // Для отладки
      if (!res.ok || data.error){ 
        setError(data.error || 'Ошибка генерации'); 
      } else { 
        // Проверяем разные форматы ответа
        let generatedReply = '';
        if (data.result?.reply) {
          generatedReply = data.result.reply;
        } else if (data.reply) {
          generatedReply = data.reply;
        } else if (typeof data.result === 'string') {
          generatedReply = data.result;
        } else if (data.result && typeof data.result === 'object' && 'text' in data.result) {
          generatedReply = data.result.text;
        }
        
        console.log('Извлечённый ответ:', generatedReply); // Для отладки
        
        if (reviewId) {
          // Сохраняем ответ для конкретного отзыва
          setGeneratedReplies(prev => ({ ...prev, [reviewId]: generatedReply }));
        } else {
          // Для ручного ввода
          setReply(generatedReply);
          setEditableReply(generatedReply);
          setIsEditing(false);
        }
      }
    } catch (e: any) { 
      setError(e.message || 'Ошибка запроса'); 
    } finally { 
      if (reviewId) {
        setGeneratingForReviewId(null);
      } else {
        setLoading(false);
      }
    }
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

      {/* Блок со спарсенными отзывами */}
      <div className="mt-8 pt-6 border-t border-gray-300">
        <h4 className="text-md font-semibold text-gray-900 mb-3">Отзывы из ваших карт</h4>
        {loadingReviews ? (
          <div className="text-sm text-gray-500">Загрузка отзывов...</div>
        ) : externalReviews.length === 0 ? (
          <div className="text-sm text-gray-500">Нет спарсенных отзывов. Запустите синхронизацию в настройках внешних аккаунтов.</div>
        ) : (
          <div className="space-y-4">
            {externalReviews.map((reviewItem) => (
              <div key={reviewItem.id} className="bg-white border border-gray-200 rounded-lg p-4">
                <div className="flex items-start justify-between mb-2">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-medium text-gray-900">{reviewItem.author_name}</span>
                      {reviewItem.rating && (
                        <span className="text-sm text-gray-600">⭐ {reviewItem.rating}</span>
                      )}
                      {reviewItem.published_at && (
                        <span className="text-xs text-gray-500">
                          {new Date(reviewItem.published_at).toLocaleDateString('ru-RU')}
                        </span>
                      )}
                    </div>
                    <div className="text-sm text-gray-700 mb-3">{reviewItem.text}</div>
                  </div>
                </div>
                
                <div className="space-y-2">
                  <label className="block text-sm font-medium text-gray-700">Ответ организации:</label>
                  {reviewItem.has_response && reviewItem.response_text ? (
                    <div className="bg-green-50 border border-green-200 rounded p-3">
                      <div className="text-sm text-gray-900">{reviewItem.response_text}</div>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      <Textarea 
                        rows={3}
                        value={generatedReplies[reviewItem.id] || ''}
                        onChange={(e) => setGeneratedReplies(prev => ({ ...prev, [reviewItem.id]: e.target.value }))}
                        placeholder="Ответ организации..."
                        className="w-full"
                      />
                      <Button
                        onClick={() => handleGenerate(reviewItem.text, reviewItem.id)}
                        disabled={generatingForReviewId === reviewItem.id}
                        size="sm"
                        variant="outline"
                      >
                        {generatingForReviewId === reviewItem.id ? 'Генерируем…' : 'Сгенерировать ответ'}
                      </Button>
                      {generatedReplies[reviewItem.id] && (
                        <div className="flex gap-2 mt-2">
                          <Button
                            onClick={() => navigator.clipboard.writeText(generatedReplies[reviewItem.id])}
                            size="sm"
                            variant="outline"
                          >
                            Копировать
                          </Button>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}


