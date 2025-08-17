import React, { useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { supabase } from '../lib/supabase';

const EmailConfirmation: React.FC = () => {
  const [email, setEmail] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [isExistingUser, setIsExistingUser] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    const emailFromState = location.state?.email;
    if (emailFromState) {
      setEmail(emailFromState);
      checkExistingUser(emailFromState);
    } else {
      // Если email не передан, перенаправляем на главную
      navigate('/');
    }
  }, [location, navigate]);

  const checkExistingUser = async (email: string) => {
    try {
      // Проверяем, есть ли пользователь в базе
      const { data: existingUser } = await supabase
        .from('Users')
        .select('id')
        .eq('email', email)
        .single();

      if (existingUser) {
        setIsExistingUser(true);
        setInfo('Пользователь с таким email уже существует. Можно отправить письмо для восстановления пароля.');
      }
    } catch (error) {
      console.log('Пользователь не найден в базе:', error);
    }
  };

    const handleResendEmail = async () => {
    if (!email) {
      setError('Email не найден.');
      return;
    }

    setLoading(true);
    setError(null);
    setInfo(null);

    // Функция для повторных попыток восстановления пароля
    const attemptResetPassword = async (attempt: number = 1): Promise<boolean> => {
      try {
        console.log(`Попытка восстановления пароля #${attempt} для ${email}`);
        
        const { error: resetError } = await supabase.auth.resetPasswordForEmail(email, {
          redirectTo: window.location.origin + '/set-password?email=' + encodeURIComponent(email)
        });

        if (resetError) {
          console.error(`Ошибка попытки #${attempt}:`, resetError);
          
          if (resetError.message?.includes('rate limit') || resetError.message?.includes('too many requests')) {
            setError('Превышен лимит отправки email. Попробуйте позже или используйте другой email.');
            return false;
          } else if (resetError.message?.includes('timeout') || resetError.message?.includes('504')) {
            if (attempt < 3) {
              setInfo(`Попытка ${attempt} не удалась из-за таймаута. Повторяем через 2 секунды...`);
              await new Promise(resolve => setTimeout(resolve, 2000));
              return await attemptResetPassword(attempt + 1);
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
          return await attemptResetPassword(attempt + 1);
        } else {
          setError('Произошла ошибка при отправке письма. Попробуйте позже.');
          return false;
        }
      }
    };

    // Функция для повторных попыток регистрации
    const attemptSignUp = async (attempt: number = 1): Promise<boolean> => {
      try {
        console.log(`Попытка регистрации #${attempt} для ${email}`);
        
        const { data, error: signUpError } = await supabase.auth.signUp({
          email,
          password: 'temporary-password-' + Date.now(), // Временный пароль
          options: {
            emailRedirectTo: window.location.origin + '/set-password'
          }
        });

        if (signUpError) {
          console.error(`Ошибка регистрации #${attempt}:`, signUpError);
          
          if (signUpError.message?.includes('already registered')) {
            // Если пользователь уже зарегистрирован, отправляем reset password
            setIsExistingUser(true);
            return await attemptResetPassword();
          } else if (signUpError.message?.includes('rate limit') || signUpError.message?.includes('too many requests')) {
            setError('Превышен лимит отправки email. Попробуйте позже или используйте другой email.');
            return false;
          } else if (signUpError.message?.includes('timeout') || signUpError.message?.includes('504')) {
            if (attempt < 3) {
              setInfo(`Попытка регистрации ${attempt} не удалась из-за таймаута. Повторяем через 2 секунды...`);
              await new Promise(resolve => setTimeout(resolve, 2000));
              return await attemptSignUp(attempt + 1);
            } else {
              setError('Сервер временно недоступен. Попробуйте позже или обратитесь в поддержку.');
              return false;
            }
          } else {
            setError('Ошибка при отправке письма: ' + signUpError.message);
            return false;
          }
        } else {
          console.log('Письмо с подтверждением отправлено успешно');
          setInfo('Письмо с подтверждением отправлено на вашу почту. Не забудьте проверить папку СПАМ.');
          return true;
        }
      } catch (error) {
        console.error(`Исключение в регистрации #${attempt}:`, error);
        
        if (attempt < 3) {
          setInfo(`Попытка регистрации ${attempt} не удалась. Повторяем через 2 секунды...`);
          await new Promise(resolve => setTimeout(resolve, 2000));
          return await attemptSignUp(attempt + 1);
        } else {
          setError('Произошла ошибка при отправке письма. Попробуйте позже.');
          return false;
        }
      }
    };

    try {
      if (isExistingUser) {
        // Для существующего пользователя отправляем reset password
        await attemptResetPassword();
      } else {
        // Для нового пользователя пытаемся зарегистрировать
        await attemptSignUp();
      }
    } catch (error) {
      console.error('Общая ошибка:', error);
      setError('Произошла ошибка: ' + (error as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const handleCheckConfirmation = async () => {
    setLoading(true);
    setError(null);

    try {
      // Проверяем, есть ли авторизованный пользователь
      const { data: { user }, error } = await supabase.auth.getUser();
      
      if (error) {
        setError('Ошибка при проверке статуса: ' + error.message);
      } else if (user && user.email === email) {
        // Пользователь авторизован, перенаправляем на установку пароля
        navigate('/set-password', { state: { email } });
      } else {
        setInfo('Email еще не подтвержден или пользователь не авторизован. Проверьте почту и нажмите на ссылку в письме.');
      }
    } catch (error) {
      setError('Произошла ошибка: ' + (error as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-md mx-auto bg-white p-6 rounded-xl shadow-md flex flex-col gap-4 mt-12">
      <h2 className="text-2xl font-bold mb-2">
        {isExistingUser ? 'Восстановление доступа' : 'Подтвердите ваш email'}
      </h2>
      
      <div className="text-center py-4">
        <div className="text-green-600 mb-4">
          <svg className="w-16 h-16 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 4.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
          </svg>
        </div>
        
        <p className="text-gray-600 mb-4">
          {isExistingUser 
            ? 'Мы отправим письмо для восстановления пароля на адрес:'
            : 'Мы отправили письмо с подтверждением на адрес:'
          }
        </p>
        <p className="font-semibold text-lg mb-4">{email}</p>
        
        <div className="bg-blue-50 border border-blue-200 rounded p-3 mb-4">
          <p className="text-blue-800 text-sm">
            <strong>Важно:</strong> Проверьте также папку СПАМ, письмо может попасть туда.
          </p>
        </div>

        {isExistingUser && (
          <div className="bg-yellow-50 border border-yellow-200 rounded p-3 mb-4">
            <p className="text-yellow-800 text-sm">
              <strong>Информация:</strong> Пользователь с таким email уже существует. Отправляем письмо для восстановления пароля.
            </p>
          </div>
        )}
      </div>

      <div className="flex flex-col gap-3">
        <button
          onClick={handleCheckConfirmation}
          disabled={loading}
          className="bg-primary text-white rounded px-4 py-2 font-semibold hover:bg-primary/90 transition disabled:opacity-50"
        >
          {loading ? 'Проверяем...' : 'Я подтвердил email'}
        </button>
        
        <button
          onClick={handleResendEmail}
          disabled={loading}
          className="bg-gray-500 text-white rounded px-4 py-2 font-semibold hover:bg-gray-600 transition disabled:opacity-50"
        >
          {loading ? 'Отправляем...' : isExistingUser ? 'Отправить письмо для восстановления' : 'Отправить письмо заново'}
        </button>

        {isExistingUser && (
          <button
            onClick={() => navigate('/login')}
            className="bg-blue-500 text-white rounded px-4 py-2 font-semibold hover:bg-blue-600 transition"
          >
            Войти с паролем
          </button>
        )}
      </div>
      
      {error && (
        <div className="bg-red-50 border border-red-200 rounded p-3">
          <p className="text-red-600 text-sm">{error}</p>
        </div>
      )}
      
      {info && (
        <div className="bg-green-50 border border-green-200 rounded p-3">
          <p className="text-green-600 text-sm">{info}</p>
        </div>
      )}
    </div>
  );
};

export default EmailConfirmation; 