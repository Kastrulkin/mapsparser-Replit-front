import React, { useState, useEffect } from 'react';
import { supabase } from '../lib/supabase';
import { auth } from '../lib/auth';
import { useLocation, useNavigate } from 'react-router-dom';

const SetPassword: React.FC = () => {
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [isAuthorized, setIsAuthorized] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const email = location.state?.email;

  // Проверяем, что пользователь пришел с подтвержденным email
  useEffect(() => {
    const checkUser = async () => {
      if (!email) {
        setError('Email не найден. Попробуйте войти заново.');
        return;
      }

      try {
        // Проверяем, есть ли авторизованный пользователь
        const { data: { user }, error } = await supabase.auth.getUser();
        
        if (error) {
          console.log('Ошибка получения пользователя:', error);
          setError('Не удалось получить данные пользователя. Попробуйте войти заново.');
          return;
        }

        if (user && user.email === email) {
          console.log('Пользователь авторизован:', user.email);
          setIsAuthorized(true);
        } else {
          console.log('Пользователь не авторизован или email не совпадает');
          setError('Пользователь не авторизован. Пожалуйста, подтвердите email и попробуйте снова.');
        }
      } catch (error) {
        console.error('Ошибка проверки пользователя:', error);
        setError('Произошла ошибка при проверке пользователя: ' + (error as Error).message);
      }
    };

    checkUser();
  }, [email]);

  const handleResetPassword = async () => {
    if (!email) {
      setError('Email не найден.');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const { error: resetError } = await supabase.auth.resetPasswordForEmail(email, {
        redirectTo: window.location.origin + '/set-password'
      });

      if (resetError) {
        setError('Ошибка при отправке письма: ' + resetError.message);
      } else {
        setInfo('Письмо для восстановления пароля отправлено на вашу почту. Не забудьте проверить папку СПАМ.');
      }
    } catch (error) {
      setError('Произошла ошибка: ' + (error as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      if (!isAuthorized) {
        setError('Не удалось авторизоваться. Попробуйте восстановить пароль через email.');
        setLoading(false);
        return;
      }

      // Обновляем пароль
      try {
        const { error: updateError } = await supabase.auth.updateUser({ password });
        if (updateError) {
          console.warn('Ошибка обновления пароля в Supabase Auth:', updateError);
          // Продолжаем с нашей системой аутентификации
        }
      } catch (error) {
        console.warn('Ошибка обновления пароля в Supabase Auth:', error);
      }

      // Обновляем пароль в нашей системе аутентификации
      const currentUser = auth.getCurrentUser();
      if (currentUser) {
        localStorage.setItem(`user_${currentUser.id}_password`, password);
      }

      // Очищаем временные данные
      localStorage.removeItem('tempPassword');
      localStorage.removeItem('tempUserId');
      
      // Показываем сообщение об успехе
      alert('Пароль успешно установлен! Теперь вы можете войти в личный кабинет.');
      
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
      
      {!isAuthorized && !error && (
        <div className="text-center py-4">
          <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary mx-auto mb-2"></div>
          <p className="text-sm text-gray-600">Авторизация...</p>
        </div>
      )}

      {isAuthorized && (
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
      )}
      
      {error && (
        <div className="bg-red-50 border border-red-200 rounded p-3">
          <p className="text-red-600 text-sm mb-3">{error}</p>
          <button
            onClick={handleResetPassword}
            disabled={loading}
            className="w-full bg-red-600 text-white rounded px-3 py-2 text-sm hover:bg-red-700 transition disabled:opacity-50"
          >
            {loading ? 'Отправляем...' : 'Восстановить пароль через email'}
          </button>
        </div>
      )}
      
      {info && (
        <div className="bg-green-50 border border-green-200 rounded p-3">
          <p className="text-green-600 text-sm">{info}</p>
        </div>
      )}
      
      {!error && !isAuthorized && (
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
      )}
    </div>
  );
};

export default SetPassword; 