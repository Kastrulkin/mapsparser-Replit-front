import React, { useState } from 'react';
import { supabase } from '@/lib/supabase';
import { useNavigate } from 'react-router-dom';

function generateRandomPassword(length = 12) {
  return Math.random().toString(36).slice(-length);
}

const EmailYandexForm: React.FC = () => {
  const [email, setEmail] = useState('');
  const [yandexUrl, setYandexUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setSuccess(null);
    setError(null);

    let userId: string | null = null;
    // 1. Проверяем, есть ли пользователь
    let { data: existingUser } = await supabase
      .from('users')
      .select('id')
      .eq('email', email)
      .single();

    if (existingUser) {
      userId = existingUser.id;
    } else {
      // 2. Создаём пользователя с временным паролем
      const tempPassword = generateRandomPassword();
      const { data, error: signUpError } = await supabase.auth.signUp({
        email,
        password: tempPassword,
      });
      if (signUpError || !data?.user) {
        setError('Ошибка при создании пользователя');
        setLoading(false);
        return;
      }
      userId = data.user.id;
      // Сохраняем временный пароль для последующей смены
      localStorage.setItem('tempPassword', tempPassword);
    }

    // 3. Сохраняем заявку на отчёт
    const { error: insertError } = await supabase
      .from('Cards')
      .insert({ email, url: yandexUrl, user_id: userId });

    if (insertError) {
      setError('Ошибка при сохранении заявки');
      setLoading(false);
      return;
    }

    // 4. Перенаправляем на страницу установки пароля
    navigate('/set-password', { state: { email } });
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