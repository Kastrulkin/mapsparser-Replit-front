import React, { useState } from 'react';
import { supabase } from '@/lib/supabase';
import { useLocation, useNavigate } from 'react-router-dom';

const SetPassword: React.FC = () => {
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();
  const location = useLocation();
  const email = location.state?.email;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      // Получаем временный пароль и ID из localStorage
      const tempPassword = localStorage.getItem('tempPassword');
      const tempUserId = localStorage.getItem('tempUserId');
      
      if (!tempPassword || !email) {
        setError('Не удалось найти временный пароль или email. Попробуйте войти заново.');
        setLoading(false);
        return;
      }

      // Пытаемся войти с временным паролем
      let { error: signInError } = await supabase.auth.signInWithPassword({
        email,
        password: tempPassword,
      });

      // Если не удалось войти, возможно пользователь ещё не подтверждён
      if (signInError) {
        console.log('Ошибка входа с временным паролем:', signInError);
        
        // Пытаемся создать пользователя заново (если он не был создан)
        const { data: signUpData, error: signUpError } = await supabase.auth.signUp({
          email,
          password: tempPassword,
        });
        
        if (signUpError) {
          setError('Ошибка при создании пользователя: ' + signUpError.message);
          setLoading(false);
          return;
        }
        
        // Если пользователь создан, но требует подтверждения email
        if (signUpData.user && !signUpData.user.email_confirmed_at) {
          setError('Проверьте почту и подтвердите email для завершения регистрации.');
          setLoading(false);
          return;
        }
        
        // Если пользователь создан и подтверждён, пытаемся войти снова
        if (signUpData.user) {
          const { error: retrySignInError } = await supabase.auth.signInWithPassword({
            email,
            password: tempPassword,
          });
          
          if (retrySignInError) {
            setError('Ошибка входа после создания пользователя: ' + retrySignInError.message);
            setLoading(false);
            return;
          }
        }
      }

      // Обновляем пароль
      const { error: updateError } = await supabase.auth.updateUser({ password });
      if (updateError) {
        setError('Ошибка при установке пароля: ' + updateError.message);
        setLoading(false);
        return;
      }

      // Очищаем временные данные
      localStorage.removeItem('tempPassword');
      localStorage.removeItem('tempUserId');
      
      // Редирект в личный кабинет
      navigate('/dashboard');
      
    } catch (error) {
      console.error('Общая ошибка в SetPassword:', error);
      setError('Произошла ошибка. Попробуйте ещё раз.');
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="max-w-md mx-auto bg-white p-6 rounded-xl shadow-md flex flex-col gap-4 mt-12">
      <h2 className="text-2xl font-bold mb-2">Установите пароль для входа</h2>
      <input
        type="password"
        value={password}
        onChange={e => setPassword(e.target.value)}
        required
        className="border rounded px-3 py-2"
        placeholder="Новый пароль"
      />
      <button
        type="submit"
        disabled={loading}
        className="bg-primary text-white rounded px-4 py-2 font-semibold hover:bg-primary/90 transition"
      >
        {loading ? 'Сохраняем...' : 'Установить пароль'}
      </button>
      {error && <div className="text-red-600">{error}</div>}
    </form>
  );
};

export default SetPassword; 