import React, { useState } from 'react';
import { Button } from './ui/button';
import { Textarea } from './ui/textarea';

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

  const handleGenerate = async () => {
    setLoading(true); setError(null); setReply('');
    try {
      const token = localStorage.getItem('auth_token');
      const res = await fetch(`${window.location.origin}/api/reviews/reply`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ review, tone, business_name: businessName || '' })
      });
      const data = await res.json();
      if (!res.ok || data.error){ setError(data.error || 'Ошибка генерации'); }
      else { setReply(data.result?.reply || ''); }
    } catch (e: any) { setError(e.message || 'Ошибка запроса'); }
    finally { setLoading(false); }
  };

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-gray-900">Ответы на отзывы</h3>
      <p className="text-sm text-gray-600">Вставьте отзыв клиента, выберите тон и сгенерируйте краткий корректный ответ. Без “воды” и лишних рассуждений.</p>
      <div className="flex flex-wrap gap-2">
        {tones.map(t => (
          <button key={t.key} type="button" onClick={()=> setTone(t.key)}
            className={`text-xs px-3 py-1 rounded-full border ${tone===t.key ? 'bg-blue-600 text-white border-blue-600' : 'border-gray-300 text-gray-700'}`}>
            {t.label}
          </button>
        ))}
      </div>
      <Textarea rows={5} value={review} onChange={(e)=> setReview(e.target.value)} placeholder="Текст отзыва клиента..." />
      {error && <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-2 rounded">{error}</div>}
      <div className="flex gap-2">
        <Button onClick={handleGenerate} disabled={loading || !review.trim()}>{loading ? 'Генерируем…' : 'Сгенерировать ответ'}</Button>
        {reply && (
          <Button variant="outline" onClick={()=> { navigator.clipboard.writeText(reply); }}>
            Копировать
          </Button>
        )}
      </div>
      {reply && (
        <div className="bg-gray-50 border border-gray-200 p-3 rounded">
          <div className="text-sm text-gray-600 mb-1">Предложение ответа:</div>
          <div className="text-gray-900">{reply}</div>
        </div>
      )}
    </div>
  );
}


