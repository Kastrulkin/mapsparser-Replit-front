import React, { useState, useEffect } from 'react';
import { supabase } from '@/lib/supabase';
import { useLocation, useNavigate } from 'react-router-dom';

const SetPassword: React.FC = () => {
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [isEmailConfirmed, setIsEmailConfirmed] = useState(false);
  const [isChecking, setIsChecking] = useState(true);
  const navigate = useNavigate();
  const location = useLocation();
  const email = location.state?.email;

  // Проверяем подтверждение email при загрузке
  useEffect(() => {
    const checkEmailConfirmation = async () => {
      if (!email) return;
      
      try {
        // Пытаемся получить текущего пользователя
        const { data: { user } } = await supabase.auth.getUser();
        
        if (user && user.email === email) {
          // Если пользователь авторизован и email совпадает, проверяем подтверждение
          setIsEmailConfirmed(!!user.email_confirmed_at);
        } else {
          // Если пользователь не авторизован, показываем сообщение о необходимости подтверждения
          setIsEmailConfirmed(false);
        }
      } catch (error) {
        console.error('Ошибка проверки email:', error);
        setIsEmailConfirmed(false);
      } finally {
        setIsChecking(false);
      }
    };

    checkEmailConfirmation();
  }, [email]);

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
      // Если email не подтвержден, отправляем письмо для восстановления пароля
      if (!isEmailConfirmed) {
        const { error: resetError } = await supabase.auth.resetPasswordForEmail(email, {
          redirectTo: window.location.origin + '/set-password'
        });
        
        if (resetError) {
          setError('Ошибка при отправке письма для восстановления пароля: ' + resetError.message);
          setLoading(false);
          return;
        }
        
        setInfo('Письмо для восстановления пароля отправлено на вашу почту. Не забудьте проверить папку СПАМ.');
        setLoading(false);
        return;
      }

      // Если email подтвержден, обновляем пароль напрямую
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
      
      {isChecking && (
        <div className="text-center py-4">
          <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary mx-auto mb-2"></div>
          <p className="text-sm text-gray-600">Проверка подтверждения email...</p>
        </div>
      )}

      {!isChecking && !isEmailConfirmed && (
        <div className="text-center py-4">
          <p className="text-sm text-gray-600 mb-4">
            Ваш email не подтвержден. Для установки пароля, пожалуйста, подтвердите ваш email.
            Мы отправили письмо для подтверждения на вашу почту.
          </p>
          <button
            onClick={handleResetPassword}
            disabled={loading}
            className="w-full text-sm text-blue-600 hover:text-blue-800 underline disabled:opacity-50"
          >
            Отправить письмо подтверждения повторно
          </button>
        </div>
      )}

      {!isChecking && isEmailConfirmed && (
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