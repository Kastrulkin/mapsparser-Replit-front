import React, { useState, useEffect } from 'react';
import { newAuth } from '../lib/auth_new';
import { useLocation, useNavigate } from 'react-router-dom';

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
  const [token, setToken] = useState<string>('');

  // Проверяем, что пользователь пришел с подтвержденным email или пропускаем проверку
  useEffect(() => {
    const checkUser = async () => {
      // Получаем email и токен из URL параметров
      const urlParams = new URLSearchParams(window.location.search);
      const userEmail = urlParams.get('email');
      const userToken = urlParams.get('token');
      
      if (userEmail) {
        setEmail(userEmail);
        console.log('Email получен из URL параметров:', userEmail);
      }
      
      if (userToken) {
        setToken(userToken);
        console.log('Токен получен из URL параметров:', userToken);
      }

      if (!userEmail) {
        setError('Email не найден. Попробуйте войти заново.');
        return;
      }

      // Для новой системы просто разрешаем установку пароля
      setIsAuthorized(true);
    };

    checkUser();
  }, [location.state]);

  const handleSetPassword = async () => {
    if (!email) {
      setError('Email не найден.');
      return;
    }

    if (!password) {
      setError('Введите пароль.');
      return;
    }

    if (password.length < 6) {
      setError('Пароль должен содержать минимум 6 символов.');
      return;
    }

    setLoading(true);
    setError(null);
    setInfo(null);

    try {
      let result;
      
      // Если есть токен, используем восстановление пароля
      if (token) {
        const response = await fetch('/api/auth/confirm-reset', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            email: email,
            token: token,
            password: password
          })
        });
        
        const data = await response.json();
        
        if (response.ok) {
          setInfo('Пароль успешно изменен! Выполняется вход...');
          setTimeout(() => {
            navigate('/login');
          }, 2000);
          return;
        } else {
          setError(data.error || 'Ошибка сброса пароля');
          return;
        }
      } else {
        // Обычная установка пароля
        result = await newAuth.setPassword(email, password);
        
        if (result.error) {
          setError(result.error);
        } else if (result.user) {
          setInfo('Пароль успешно установлен! Выполняется вход...');
          setTimeout(() => {
            navigate('/dashboard');
          }, 2000);
        }
      }
    } catch (error) {
      setError('Ошибка установки пароля: ' + (error as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await handleSetPassword();
  };

  // Упрощенная версия без альтернативного восстановления

  return (
    <div className="max-w-md mx-auto bg-white p-6 rounded-xl shadow-md flex flex-col gap-4 mt-12">
      <h2 className="text-2xl font-bold mb-2">
        {token ? 'Восстановление пароля' : 'Установите пароль для входа'}
      </h2>
      
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
              onClick={handleSetPassword}
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
              onClick={handleSetPassword}
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