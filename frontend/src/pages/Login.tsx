import { useState } from "react";
import Footer from "../components/Footer";
import { Button } from "../components/ui/button";
import { newAuth } from "../lib/auth_new";
import { useNavigate } from "react-router-dom";

const Login = () => {
  const [tab, setTab] = useState<'login' | 'register' | 'reset'>('login');
  const [loginForm, setLoginForm] = useState({ email: '', password: '' });
  const [registerForm, setRegisterForm] = useState({ name: '', phone: '', email: '', password: '', yandexUrl: '' });
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
      const { user, error } = await newAuth.signIn(loginForm.email, loginForm.password);
      
      if (error) {
        if (error.includes('NEED_PASSWORD')) {
          // Пользователь существует, но не установил пароль
          navigate('/set-password', { state: { email: loginForm.email } });
        } else {
          setError(error);
        }
      } else if (user) {
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
    
    try {
      // Отправляем заявку на регистрацию
      const response = await fetch('/api/public/request-registration', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name: registerForm.name,
          email: registerForm.email,
          phone: registerForm.phone,
          yandex_url: registerForm.yandexUrl
        })
      });
      
      const data = await response.json();
      
      if (response.ok) {
        setInfo(data.message || 'Заявка на регистрацию принята. Мы свяжемся с вами в ближайшее время.');
        // Очищаем форму
        setRegisterForm({ name: '', phone: '', email: '', password: '', yandexUrl: '' });
      } else {
        setError(data.error || 'Ошибка отправки заявки на регистрацию');
      }
    } catch (error) {
      setError('Ошибка отправки заявки: ' + (error as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const handleResetPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setInfo(null);
    
    try {
      const response = await fetch('/api/auth/reset-password', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          email: registerForm.email
        })
      });
      
      const data = await response.json();
      
      if (response.ok) {
        setInfo('Инструкции по восстановлению пароля отправлены на email. Проверьте почту!');
      } else {
        setError(data.error || 'Ошибка восстановления пароля');
      }
    } catch (error) {
      setError('Ошибка восстановления пароля: ' + (error as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        <div>
          <h2 className="mt-6 text-center text-3xl font-extrabold text-gray-900">
            Вход в систему
          </h2>
          <p className="mt-2 text-center text-sm text-gray-600">
            Новые клиенты для вашего бизнеса
          </p>
        </div>

        <div className="bg-white py-8 px-4 shadow sm:rounded-lg sm:px-10">
          {/* Табы */}
          <div className="flex space-x-1 mb-6">
            <button
              onClick={() => setTab('login')}
              className={`flex-1 py-2 px-4 text-sm font-medium rounded-md ${
                tab === 'login'
                  ? 'bg-indigo-100 text-indigo-700'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              Вход
            </button>
            <button
              onClick={() => setTab('register')}
              className={`flex-1 py-2 px-4 text-sm font-medium rounded-md ${
                tab === 'register'
                  ? 'bg-indigo-100 text-indigo-700'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              Регистрация
            </button>
            <button
              onClick={() => setTab('reset')}
              className={`flex-1 py-2 px-4 text-sm font-medium rounded-md ${
                tab === 'reset'
                  ? 'bg-indigo-100 text-indigo-700'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              Восстановление
            </button>
          </div>

          {error && (
            <div className="mb-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
              {error}
            </div>
          )}

          {info && (
            <div className="mb-4 bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded">
              {info}
            </div>
          )}

          {/* Форма входа */}
          {tab === 'login' && (
            <form className="space-y-6" onSubmit={handleLogin}>
              <div>
                <label htmlFor="login-email" className="block text-sm font-medium text-gray-700">
                  Email
                </label>
                <input
                  id="login-email"
                  type="email"
                  required
                  value={loginForm.email}
                  onChange={(e) => setLoginForm({...loginForm, email: e.target.value})}
                  className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
                />
              </div>
              <div>
                <label htmlFor="login-password" className="block text-sm font-medium text-gray-700">
                  Пароль
                </label>
                <input
                  id="login-password"
                  type="password"
                  required
                  value={loginForm.password}
                  onChange={(e) => setLoginForm({...loginForm, password: e.target.value})}
                  className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
                />
              </div>
              <Button
                type="submit"
                className="w-full"
                disabled={loading}
              >
                {loading ? 'Вход...' : 'Войти'}
              </Button>
            </form>
          )}

          {/* Форма регистрации */}
          {tab === 'register' && (
            <form className="space-y-6" onSubmit={handleRegister}>
              <div>
                <label htmlFor="register-name" className="block text-sm font-medium text-gray-700">
                  Имя
                </label>
                <input
                  id="register-name"
                  type="text"
                  value={registerForm.name}
                  onChange={(e) => setRegisterForm({...registerForm, name: e.target.value})}
                  className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
                />
              </div>
              <div>
                <label htmlFor="register-email" className="block text-sm font-medium text-gray-700">
                  Email
                </label>
                <input
                  id="register-email"
                  type="email"
                  required
                  value={registerForm.email}
                  onChange={(e) => setRegisterForm({...registerForm, email: e.target.value})}
                  className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
                />
              </div>
              <div>
                <label htmlFor="register-phone" className="block text-sm font-medium text-gray-700">
                  Телефон
                </label>
                <input
                  id="register-phone"
                  type="tel"
                  value={registerForm.phone}
                  onChange={(e) => setRegisterForm({...registerForm, phone: e.target.value})}
                  className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
                />
              </div>
              <div>
                <label htmlFor="register-yandex-url" className="block text-sm font-medium text-gray-700">
                  Ссылка на карты
                </label>
                <input
                  id="register-yandex-url"
                  type="url"
                  value={registerForm.yandexUrl}
                  onChange={(e) => setRegisterForm({...registerForm, yandexUrl: e.target.value})}
                  placeholder="https://yandex.ru/maps/org/..."
                  className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
                />
              </div>
              <Button
                type="submit"
                className="w-full"
                disabled={loading}
              >
                {loading ? 'Отправка заявки...' : 'Отправить заявку на регистрацию'}
              </Button>
            </form>
          )}

          {/* Форма восстановления пароля */}
          {tab === 'reset' && (
            <form className="space-y-6" onSubmit={handleResetPassword}>
              <div>
                <label htmlFor="reset-email" className="block text-sm font-medium text-gray-700">
                  Email
                </label>
                <input
                  id="reset-email"
                  type="email"
                  required
                  value={registerForm.email}
                  onChange={(e) => setRegisterForm({...registerForm, email: e.target.value})}
                  className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
                />
              </div>
              <Button
                type="submit"
                className="w-full"
                disabled={loading}
              >
                {loading ? 'Отправка...' : 'Восстановить пароль'}
              </Button>
            </form>
          )}
        </div>
      </div>
      <Footer />
    </div>
  );
};

export default Login;
