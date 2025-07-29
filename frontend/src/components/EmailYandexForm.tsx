import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { supabase } from '../lib/supabase';
import { rateLimiter } from '../lib/rateLimiter';
import { SupabaseWithRetry } from '../lib/supabaseWithRetry';
import { SupabaseDebug } from '../lib/supabaseDebug';

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

    // Проверяем rate limiting
    const rateKey = `signup_${email}`;
    if (!rateLimiter.canAttempt(rateKey)) {
      const remainingTime = rateLimiter.getRemainingTime(rateKey);
      setError(`Слишком много попыток. Попробуйте через ${Math.ceil(remainingTime / 1000)} секунд.`);
      setLoading(false);
      return;
    }

    let userId: string | null = null;
    
    try {
      // Отладочная информация
      await SupabaseDebug.checkEmailSettings();
      await SupabaseDebug.getRateLimitInfo();
      
      // 1. Проверяем, есть ли пользователь в таблице Users
      let { data: existingUser } = await supabase
        .from('Users')
        .select('id')
        .eq('email', email)
        .single();

      if (existingUser) {
        userId = existingUser.id;
      } else {
        // 2. Создаём пользователя без email-подтверждения
        const tempPassword = generateRandomPassword();
        
        // Сначала создаем пользователя в таблице Users
        const { data: userData, error: userError } = await supabase
          .from('Users')
          .insert({ email: email })
          .select('id')
          .single();
          
        if (userError) {
          console.error('Ошибка создания пользователя в таблице:', userError);
          if (userError.message?.includes('rate limit')) {
            setError('Превышен лимит отправки email. Попробуйте позже или используйте другой email.');
          } else {
            setError('Ошибка при создании пользователя: ' + userError.message);
          }
          setLoading(false);
          return;
        }
        
        userId = userData.id;
        
        // Пропускаем создание пользователя в Auth из-за rate limit
        console.log('Пропускаем создание пользователя в Auth из-за rate limit');
        
        // Сохраняем временный пароль для последующей смены
        localStorage.setItem('tempPassword', tempPassword);
        localStorage.setItem('tempUserId', userId);
      }

      // 3. Сохраняем заявку на отчёт в ParseQueue
      const { error: insertError } = await supabase
        .from('ParseQueue')
        .insert({ user_id: userId, url: yandexUrl });

      if (insertError) {
        setError('Ошибка при сохранении заявки: ' + insertError.message);
        setLoading(false);
        return;
      }

      setSuccess('Заявка успешно отправлена! Переходим к настройке пароля.');
      // 4. Перенаправляем сразу на страницу установки пароля (без email-подтверждения)
      navigate('/set-password', { state: { email, skipEmailConfirmation: true } });
      
    } catch (error) {
      console.error('Общая ошибка:', error);
      setError('Произошла ошибка. Попробуйте ещё раз.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="max-w-md mx-auto bg-white p-6 rounded-xl shadow-md flex flex-col gap-4">
      <h2 className="text-2xl font-bold mb-2">Получить бесплатный анализ</h2>
      <div className="text-xs text-gray-500 bg-blue-50 p-2 rounded">
        ⚠️ Если возникает ошибка "rate limit", подождите несколько минут и попробуйте снова
      </div>
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