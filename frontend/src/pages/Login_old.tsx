import { useState } from "react";

import Footer from "../components/Footer";
import { Button } from "../components/ui/button";
import { supabase } from "../lib/supabase";
import { auth } from "../lib/auth";
import { useNavigate } from "react-router-dom";

const Login = () => {
  const [tab, setTab] = useState<'login' | 'register' | 'reset'>('login');
  const [loginForm, setLoginForm] = useState({ email: '', password: '' });
  const [registerForm, setRegisterForm] = useState({ name: '', phone: '', email: '', yandexUrl: '', password: '' });
  const [resetEmail, setResetEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const navigate = useNavigate();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setInfo(null);
    
    try {
      // Сначала пробуем через нашу простую систему аутентификации
      const { user, error: simpleAuthError } = await auth.signIn(loginForm.email, loginForm.password);
      
      if (user) {
        navigate('/dashboard');
        setLoading(false);
        return;
      }

      // Если не получилось, пробуем через Supabase Auth
      const { error } = await supabase.auth.signInWithPassword({
        email: loginForm.email,
        password: loginForm.password,
      });
      
      if (error) {
        setError('Неверная почта или пароль');
      } else {
        navigate('/dashboard');
      }
    } catch (error) {
      setError('Ошибка входа: ' + (error as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setInfo(null);
    // Регистрируем пользователя через Supabase Auth
    const { data, error: regError } = await supabase.auth.signUp({
      email: registerForm.email,
      password: registerForm.password,
      options: {
        redirectTo: 'https://beautybot.pro/set-password'
      }
    });
    if (regError || !data.user) {
      if (regError?.message?.toLowerCase().includes('user already registered') || regError?.message?.toLowerCase().includes('user already exists')) {
        setError('Пользователь с таким email уже существует. Попробуйте войти или восстановить пароль.');
      } else {
        setError('Ошибка регистрации: ' + (regError?.message || ''));
      }
      setLoading(false);
      return;
    }
    // Сохраняем профиль в users
    const { error: profileError } = await supabase.from('Users').upsert({
      id: data.user.id,
      email: registerForm.email,
      phone: registerForm.phone,
      name: registerForm.name,
      yandex_url: registerForm.yandexUrl,
    });
    
    if (profileError) {
      console.error('Ошибка сохранения профиля:', profileError);
      setError('Ошибка сохранения профиля: ' + profileError.message);
      setLoading(false);
      return;
    }
    
    console.log('Профиль сохранен:', {
      id: data.user.id,
      email: registerForm.email,
      phone: registerForm.phone,
      name: registerForm.name,
      yandex_url: registerForm.yandexUrl
    });
    setLoading(false);
    setInfo('Проверьте почту и подтвердите email для завершения регистрации.');
    setTab('login');
  };

  const handleReset = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setInfo(null);

    // Функция для повторных попыток
    const attemptReset = async (attempt: number = 1): Promise<boolean> => {
      try {
        console.log(`Попытка восстановления пароля #${attempt} для ${resetEmail}`);
        
        const { error } = await supabase.auth.resetPasswordForEmail(resetEmail, { 
          redirectTo: 'https://beautybot.pro/set-password?email=' + encodeURIComponent(resetEmail) 
        });

        if (error) {
          console.error(`Ошибка попытки #${attempt}:`, error);
          
          // Проверяем тип ошибки
          if (error.message?.includes('rate limit') || error.message?.includes('too many requests')) {
            setError('Превышен лимит отправки email. Попробуйте позже.');
            return false;
          } else if (error.message?.includes('timeout') || error.message?.includes('504')) {
            if (attempt < 3) {
              setInfo(`Попытка ${attempt} не удалась из-за таймаута. Повторяем через 2 секунды...`);
              await new Promise(resolve => setTimeout(resolve, 2000));
              return await attemptReset(attempt + 1);
            } else {
              setError('Сервер временно недоступен. Попробуйте позже или обратитесь в поддержку.');
              return false;
            }
          } else {
            setError('Ошибка при отправке письма для сброса пароля: ' + error.message);
            return false;
          }
        } else {
          console.log('Письмо для сброса пароля отправлено успешно');
          setInfo('Письмо для сброса пароля отправлено на вашу почту.');
          setTab('login');
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

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <main className="flex-1 flex items-center justify-center py-16 px-4 sm:px-6 lg:px-8">
        <div className="w-full max-w-lg bg-card rounded-2xl shadow-xl p-8 border border-border">
          <div className="flex mb-8">
            <button
              className={`flex-1 py-2 font-semibold rounded-l-2xl ${tab === 'login' ? 'bg-primary text-white' : 'bg-muted text-foreground'}`}
              onClick={() => setTab('login')}
            >
              Вход
            </button>
            <button
              className={`flex-1 py-2 font-semibold rounded-r-2xl ${tab === 'register' ? 'bg-primary text-white' : 'bg-muted text-foreground'}`}
              onClick={() => setTab('register')}
            >
              Регистрация
            </button>
          </div>
          {tab === 'login' && (
            <form onSubmit={handleLogin} className="space-y-6">
              <div>
                <label className="block text-sm font-medium mb-1 text-foreground" htmlFor="login-email">Почта</label>
                <input
                  type="email"
                  id="login-email"
                  value={loginForm.email}
                  onChange={e => setLoginForm(f => ({ ...f, email: e.target.value }))}
                  className="w-full border rounded px-3 py-2 bg-background text-foreground"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1 text-foreground" htmlFor="login-password">Пароль</label>
                <input
                  type="password"
                  id="login-password"
                  value={loginForm.password}
                  onChange={e => setLoginForm(f => ({ ...f, password: e.target.value }))}
                  className="w-full border rounded px-3 py-2 bg-background text-foreground"
                  required
                />
              </div>
              {error && <div className="text-red-600 text-sm">{error}</div>}
              {info && <div className="text-green-600 text-sm">{info}</div>}
              <div className="flex justify-between items-center mt-2">
                <Button type="submit" size="lg" className="text-lg px-8 py-3 bg-primary text-white" disabled={loading}>
                  {loading ? 'Вход...' : 'Войти'}
                </Button>
                <button type="button" className="text-primary underline ml-4" onClick={() => setTab('reset')}>
                  Забыли пароль?
                </button>
              </div>
            </form>
          )}
          {tab === 'register' && (
            <form onSubmit={handleRegister} className="space-y-6">
              <div>
                <label className="block text-sm font-medium mb-1 text-foreground" htmlFor="reg-name">Имя</label>
                <input
                  type="text"
                  id="reg-name"
                  value={registerForm.name}
                  onChange={e => setRegisterForm(f => ({ ...f, name: e.target.value }))}
                  className="w-full border rounded px-3 py-2 bg-background text-foreground"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1 text-foreground" htmlFor="reg-phone">Телефон</label>
                <input
                  type="text"
                  id="reg-phone"
                  value={registerForm.phone}
                  onChange={e => setRegisterForm(f => ({ ...f, phone: e.target.value }))}
                  className="w-full border rounded px-3 py-2 bg-background text-foreground"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1 text-foreground" htmlFor="reg-email">Почта</label>
                <input
                  type="email"
                  id="reg-email"
                  value={registerForm.email}
                  onChange={e => setRegisterForm(f => ({ ...f, email: e.target.value }))}
                  className="w-full border rounded px-3 py-2 bg-background text-foreground"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1 text-foreground" htmlFor="reg-yandex">Ссылка на организацию на Яндекс.Картах</label>
                <input
                  type="url"
                  id="reg-yandex"
                  value={registerForm.yandexUrl}
                  onChange={e => setRegisterForm(f => ({ ...f, yandexUrl: e.target.value }))}
                  className="w-full border rounded px-3 py-2 bg-background text-foreground"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1 text-foreground" htmlFor="reg-password">Пароль</label>
                <input
                  type="password"
                  id="reg-password"
                  value={registerForm.password}
                  onChange={e => setRegisterForm(f => ({ ...f, password: e.target.value }))}
                  className="w-full border rounded px-3 py-2 bg-background text-foreground"
                  required
                />
              </div>
              {error && <div className="text-red-600 text-sm">{error}</div>}
              {info && <div className="text-green-600 text-sm">{info}</div>}
              <Button type="submit" size="lg" className="w-full text-lg px-8 py-3 bg-primary text-white mt-2" disabled={loading}>
                {loading ? 'Регистрация...' : 'Зарегистрироваться'}
              </Button>
            </form>
          )}
          {tab === 'reset' && (
            <form onSubmit={handleReset} className="space-y-6">
              <div>
                <label className="block text-sm font-medium mb-1 text-foreground" htmlFor="reset-email">Почта</label>
                <input
                  type="email"
                  id="reset-email"
                  value={resetEmail}
                  onChange={e => setResetEmail(e.target.value)}
                  className="w-full border rounded px-3 py-2 bg-background text-foreground"
                  required
                />
              </div>
              {error && <div className="text-red-600 text-sm">{error}</div>}
              {info && <div className="text-green-600 text-sm">{info}</div>}
              <Button type="submit" size="lg" className="w-full text-lg px-8 py-3 bg-primary text-white mt-2" disabled={loading}>
                {loading ? 'Отправка...' : 'Сбросить пароль'}
              </Button>
              <button type="button" className="text-primary underline mt-2" onClick={() => setTab('login')}>
                Назад к входу
              </button>
            </form>
          )}
        </div>
      </main>
      <Footer />
    </div>
  );
};

export default Login; 