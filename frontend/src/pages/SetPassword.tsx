import React, { useState, useEffect } from 'react';
import { supabase } from '../lib/supabase';
import { auth } from '../lib/auth';
import { useLocation, useNavigate } from 'react-router-dom';
import AlternativePasswordReset from '../components/AlternativePasswordReset';

const SetPassword: React.FC = () => {
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [isAuthorized, setIsAuthorized] = useState(false);
  const [showAlternativeReset, setShowAlternativeReset] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState<string>('');

  // Проверяем, что пользователь пришел с подтвержденным email или пропускаем проверку
  useEffect(() => {
    const checkUser = async () => {
      // Получаем email из разных источников
      let userEmail = location.state?.email;
      const skipEmailConfirmation = location.state?.skipEmailConfirmation;
      
      // Если email не передан в state, пробуем получить из URL параметров
      if (!userEmail) {
        const urlParams = new URLSearchParams(window.location.search);
        userEmail = urlParams.get('email');
        if (userEmail) {
          console.log('Email получен из URL параметров:', userEmail);
        }
      }
      
      // Если email не передан в state или URL, пробуем получить из Supabase Auth
      if (!userEmail) {
        try {
          const { data: { user }, error } = await supabase.auth.getUser();
          if (user && user.email) {
            userEmail = user.email;
            setEmail(userEmail);
            console.log('Email получен из Auth:', userEmail);
          }
        } catch (error) {
          console.log('Ошибка получения пользователя из Auth:', error);
        }
      } else {
        setEmail(userEmail);
      }

      if (!userEmail) {
        setError('Email не найден. Попробуйте войти заново.');
        return;
      }

      if (skipEmailConfirmation) {
        // Пропускаем проверку email-подтверждения
        console.log('Пропускаем проверку email-подтверждения');
        setIsAuthorized(true);
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

        if (user && user.email === userEmail) {
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
  }, [location.state]);

  const handleResetPassword = async () => {
    if (!email) {
      setError('Email не найден.');
      return;
    }

    setLoading(true);
    setError(null);
    setInfo(null);

    // Функция для повторных попыток
    const attemptReset = async (attempt: number = 1): Promise<boolean> => {
      try {
        console.log(`Попытка восстановления пароля #${attempt} для ${email}`);
        
        const { error: resetError } = await supabase.auth.resetPasswordForEmail(email, {
          redirectTo: window.location.origin + '/set-password?email=' + encodeURIComponent(email)
        });

        if (resetError) {
          console.error(`Ошибка попытки #${attempt}:`, resetError);
          
          // Проверяем тип ошибки
          if (resetError.message?.includes('rate limit') || resetError.message?.includes('too many requests')) {
            setError('Превышен лимит отправки email. Попробуйте позже.');
            return false;
          } else if (resetError.message?.includes('timeout') || resetError.message?.includes('504')) {
            if (attempt < 3) {
              setInfo(`Попытка ${attempt} не удалась из-за таймаута. Повторяем через 2 секунды...`);
              await new Promise(resolve => setTimeout(resolve, 2000));
              return await attemptReset(attempt + 1);
            } else {
              setError('Сервер временно недоступен. Попробуйте позже или обратитесь в поддержку.');
              return false;
            }
          } else {
            setError('Ошибка при отправке письма: ' + resetError.message);
            return false;
          }
        } else {
          console.log('Письмо для восстановления пароля отправлено успешно');
          setInfo('Письмо для восстановления пароля отправлено на вашу почту. Не забудьте проверить папку СПАМ.');
          return true;
        }
      } catch (error) {
        console.error(`Исключение в попытке #${attempt}:`, error);
        
        if (attempt < 3) {
          setInfo(`Попытка ${attempt} не удалась. Повторяем через 2 секунды...`);
          await new Promise(resolve => setTimeout(resolve, 2000));
          return await attemptReset(attempt + 1);
        } else {
          setError('Произошла ошибка при отправке письма. Попробуйте позже.');
          return false;
        }
      }
    };

    // Запускаем процесс восстановления с повторными попытками
    await attemptReset();
    setLoading(false);
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

      // Обновляем пароль в нашей системе аутентификации
      const tempUserId = localStorage.getItem('tempUserId');
      if (tempUserId) {
        localStorage.setItem(`user_${tempUserId}_password`, password);
        console.log('Пароль сохранен в локальной системе аутентификации');
      }

      // Пытаемся обновить пароль в Supabase Auth (но не критично)
      try {
        const { error: updateError } = await supabase.auth.updateUser({ password });
        if (updateError) {
          console.warn('Ошибка обновления пароля в Supabase Auth:', updateError);
        } else {
          console.log('Пароль обновлен в Supabase Auth');
        }
      } catch (error) {
        console.warn('Ошибка обновления пароля в Supabase Auth:', error);
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

  // Если показываем альтернативное восстановление пароля
  if (showAlternativeReset) {
    return (
      <AlternativePasswordReset
        email={email}
        onSuccess={() => {
          setShowAlternativeReset(false);
          setError(null);
          setInfo('Пароль успешно обновлен!');
        }}
        onCancel={() => {
          setShowAlternativeReset(false);
          setError(null);
        }}
      />
    );
  }

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
          <div className="flex flex-col gap-2">
            <button
              onClick={handleResetPassword}
              disabled={loading}
              className="w-full bg-red-600 text-white rounded px-3 py-2 text-sm hover:bg-red-700 transition disabled:opacity-50"
            >
              {loading ? 'Отправляем...' : 'Восстановить пароль через email'}
            </button>
            <button
              onClick={() => setShowAlternativeReset(true)}
              disabled={loading}
              className="w-full bg-blue-600 text-white rounded px-3 py-2 text-sm hover:bg-blue-700 transition disabled:opacity-50"
            >
              Альтернативное восстановление пароля
            </button>
          </div>
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
          <div className="flex flex-col gap-2">
            <button
              onClick={handleResetPassword}
              disabled={loading}
              className="w-full text-sm text-blue-600 hover:text-blue-800 underline disabled:opacity-50"
            >
              Восстановить пароль через email
            </button>
            <button
              onClick={() => setShowAlternativeReset(true)}
              disabled={loading}
              className="w-full text-sm text-green-600 hover:text-green-800 underline disabled:opacity-50"
            >
              Альтернативное восстановление пароля
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default SetPassword; 