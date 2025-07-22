import React, { useState } from 'react';
import { supabase } from '@/lib/supabase';

const EmailYandexForm: React.FC = () => {
  const [email, setEmail] = useState('');
  const [yandexUrl, setYandexUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setSuccess(null);
    setError(null);
    const { error } = await supabase.from('Cards').insert({ email, url: yandexUrl });
    setLoading(false);
    if (error) {
      setError('Ошибка при сохранении. Попробуйте ещё раз.');
    } else {
      setSuccess('Данные успешно отправлены!');
      setEmail('');
      setYandexUrl('');
    }
  };

  return (
    <form onSubmit={handleSubmit} className="max-w-md mx-auto bg-white p-6 rounded-xl shadow-md flex flex-col gap-4">
      <h2 className="text-2xl font-bold mb-2">Получить бесплатный анализ</h2>
      <input
        type="email"
        placeholder="Ваша почта"
        value={email}
        onChange={e => setEmail(e.target.value)}
        required
        className="border rounded px-3 py-2"
      />
      <input
        type="url"
        placeholder="Ссылка на Яндекс.Карты"
        value={yandexUrl}
        onChange={e => setYandexUrl(e.target.value)}
        required
        className="border rounded px-3 py-2"
      />
      <button
        type="submit"
        disabled={loading}
        className="bg-primary text-white rounded px-4 py-2 font-semibold hover:bg-primary/90 transition"
      >
        {loading ? 'Отправка...' : 'Отправить'}
      </button>
      {success && <div className="text-green-600">{success}</div>}
      {error && <div className="text-red-600">{error}</div>}
    </form>
  );
};

export default EmailYandexForm; 