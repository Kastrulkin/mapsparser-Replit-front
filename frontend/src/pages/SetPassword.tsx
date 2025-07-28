import React, { useState } from 'react';
import { supabase } from '@/lib/supabase';
import { useLocation, useNavigate } from 'react-router-dom';

const SetPassword: React.FC = () => {
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const navigate = useNavigate();
  const location = useLocation();
  const email = location.state?.email;

  const handleResetPassword = async () => {
    if (!email) return;
    
    setLoading(true);
    setError(null);
    setInfo(null);
    
    try {
      const { error } = await supabase.auth.resetPasswordForEmail(email, {
        redirectTo: window.location.origin + '/set-password'
      });
      
      if (error) {
        setError('Ошибка при отправке письма для восстановления пароля: ' + error.message);
      } else {
        setInfo('Письмо для восстановления пароля отправлено на вашу почту. Не забудьте проверить папку СПАМ.');
      }
    } catch (error) {
      setError('Произошла ошибка при отправке письма.');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      // Получаем временный пароль из localStorage
      const tempPassword = localStorage.getItem('tempPassword');
      
      if (!tempPassword || !email) {
        setError('Не удалось найти данные для установки пароля. Попробуйте войти заново.');
        setLoading(false);
        return;
      }

      // Пытаемся войти с временным паролем
      const { error: signInError } = await supabase.auth.signInWithPassword({
        email,
        password: tempPassword,
      });

      if (signInError) {
        console.log('Ошибка входа с временным паролем:', signInError);
        
        // Если не удалось войти, предлагаем восстановление пароля
        setError('Не удалось войти с временным паролем. Попробуйте восстановить пароль через email.');
        setLoading(false);
        return;
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
      
      // Показываем сообщение о необходимости подтверждения email
      alert('Пароль успешно установлен! Теперь подтвердите email, чтобы завершить регистрацию. Не забудьте проверить папку СПАМ.');
      
      // Редирект в личный кабинет
      navigate('/dashboard');
      
    } catch (error) {
      console.error('Общая ошибка в SetPassword:', error);
      setError('Произошла ошибка. Попробуйте ещё раз.');
      setLoading(false);
    }
  };

  return (
    <div className="max-w-md mx-auto bg-white p-6 rounded-xl shadow-md flex flex-col gap-4 mt-12">
      <h2 className="text-2xl font-bold mb-2">Установите пароль для входа</h2>
      
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
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
          className="bg-primary text-white rounded px-4 py-2 font-semibold hover:bg-primary/90 transition disabled:opacity-50"
        >
          {loading ? 'Сохраняем...' : 'Установить пароль'}
        </button>
      </form>
      
      <div className="border-t pt-4">
        <p className="text-sm text-gray-600 mb-3">
          Не получается установить пароль?
        </p>
        <button
          onClick={handleResetPassword}
          disabled={loading}
          className="w-full text-sm text-blue-600 hover:text-blue-800 underline disabled:opacity-50"
        >
          Восстановить пароль через email
        </button>
      </div>
      
      {error && <div className="text-red-600 text-sm">{error}</div>}
      {info && <div className="text-green-600 text-sm">{info}</div>}
    </div>
  );
};

export default SetPassword; 