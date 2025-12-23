import { useEffect, useState } from "react";
import Footer from "../components/Footer";
import { Button } from "../components/ui/button";
import { newAuth } from "../lib/auth_new";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useLanguage } from "@/i18n/LanguageContext";

// Список популярных стран для автодополнения при регистрации
const COUNTRY_OPTIONS = [
  'Россия',
  'США',
  'Украина',
  'Казахстан',
  'Беларусь',
  'Германия',
  'Франция',
  'Испания',
  'Италия',
  'Турция',
  'ОАЭ',
  'Израиль',
  'Польша',
  'Чехия',
  'Латвия',
  'Литва',
  'Эстония',
  'Канада',
  'Великобритания',
  'Австралия',
  'Швейцария',
  'Сербия',
  'Грузия',
  'Армения',
  'Кыргызстан',
  'Узбекистан',
  'Таджикистан',
  'Азербайджан',
];

const Login = () => {
  const [searchParams] = useSearchParams();

  const [tab, setTab] = useState<'login' | 'register' | 'reset'>('login');
  const [loginForm, setLoginForm] = useState({ email: '', password: '' });
  const [registerForm, setRegisterForm] = useState({
    name: '',
    phone: '',
    email: '',
    password: '',
    business_name: '',
    business_address: '',
    business_city: '',
    business_country: 'Россия',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const navigate = useNavigate();
  const { language } = useLanguage();
  const isRu = language === 'ru';

  // Инициализация вкладки и запоминание выбранного тарифа из URL
  useEffect(() => {
    const initialTab = searchParams.get('tab');
    const tierFromUrl = searchParams.get('tier');

    if (initialTab === 'register') {
      setTab('register');
    }

    if (tierFromUrl) {
      // Запоминаем выбранный тариф для последующего редиректа на оплату
      localStorage.setItem('selectedTier', tierFromUrl);
    }
  }, [searchParams]);

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
        const tierFromUrl = searchParams.get('tier');
        const source = searchParams.get('source');

        if (tierFromUrl && source === 'pricing') {
          localStorage.setItem('selectedTier', tierFromUrl);
          navigate(`/dashboard/settings?payment=required&tier=${tierFromUrl}`);
        } else {
          navigate('/dashboard');
        }
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
    
    // Валидация
    if (!registerForm.email || !registerForm.password) {
      setError('Email и пароль обязательны');
      setLoading(false);
      return;
    }
    
    if (!registerForm.business_name || !registerForm.business_address || !registerForm.business_city) {
      setError('Название бизнеса, адрес и город обязательны');
      setLoading(false);
      return;
    }
    
    try {
      // Используем новый endpoint для регистрации с бизнесом
      const response = await fetch('/api/auth/register-with-business', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name: registerForm.name,
          email: registerForm.email,
          phone: registerForm.phone,
          password: registerForm.password,
          business_name: registerForm.business_name,
          business_address: registerForm.business_address,
          business_city: registerForm.business_city,
          business_country: registerForm.business_country
        })
      });
      
      const data = await response.json();
      
      if (response.ok && data.success) {
        const tierFromUrl = searchParams.get('tier');

        // Сохраняем токен
        if (data.token) {
          localStorage.setItem('auth_token', data.token);
        }

        if (tierFromUrl) {
          localStorage.setItem('selectedTier', tierFromUrl);
        }

        // Перенаправляем на страницу оплаты/подписки
        const targetUrl = tierFromUrl
          ? `/dashboard/settings?payment=required&tier=${tierFromUrl}`
          : '/dashboard/settings?payment=required';

        if (data.business?.moderation_status === 'pending') {
          setInfo('Регистрация успешна! Ваш бизнес ожидает модерации. Перенаправляем в личный кабинет...');
          setTimeout(() => {
            navigate(targetUrl);
          }, 2000);
        } else {
          navigate(targetUrl);
        }
      } else {
        setError(data.error || 'Ошибка регистрации');
      }
    } catch (error) {
      setError('Ошибка регистрации: ' + (error as Error).message);
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
            {isRu ? 'Вход в систему' : 'Sign in'}
          </h2>
          <p className="mt-2 text-center text-sm text-gray-600">
            {isRu ? 'Новые клиенты для вашего бизнеса' : 'New clients for your business'}
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
              {isRu ? 'Вход' : 'Login'}
            </button>
            <button
              onClick={() => setTab('register')}
              className={`flex-1 py-2 px-4 text-sm font-medium rounded-md ${
                tab === 'register'
                  ? 'bg-indigo-100 text-indigo-700'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              {isRu ? 'Регистрация' : 'Register'}
            </button>
            <button
              onClick={() => setTab('reset')}
              className={`flex-1 py-2 px-4 text-sm font-medium rounded-md ${
                tab === 'reset'
                  ? 'bg-indigo-100 text-indigo-700'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              {isRu ? 'Восстановление' : 'Reset'}
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
                {loading ? (isRu ? 'Вход...' : 'Signing in...') : (isRu ? 'Войти' : 'Sign in')}
              </Button>
            </form>
          )}

          {/* Форма регистрации */}
          {tab === 'register' && (
            <form className="space-y-4" onSubmit={handleRegister}>
              <div className="border-b border-gray-200 pb-4">
                <h3 className="text-sm font-medium text-gray-700 mb-3">Личные данные</h3>
                <div className="space-y-4">
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
                      Email *
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
                    <label htmlFor="register-password" className="block text-sm font-medium text-gray-700">
                      Пароль *
                    </label>
                    <input
                      id="register-password"
                      type="password"
                      required
                      value={registerForm.password}
                      onChange={(e) => setRegisterForm({...registerForm, password: e.target.value})}
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
                </div>
              </div>

              <div className="border-b border-gray-200 pb-4">
                <h3 className="text-sm font-medium text-gray-700 mb-3">Данные бизнеса</h3>
                <div className="space-y-4">
                  <div>
                    <label htmlFor="register-business-name" className="block text-sm font-medium text-gray-700">
                      Название бизнеса *
                    </label>
                    <input
                      id="register-business-name"
                      type="text"
                      required
                      value={registerForm.business_name}
                      onChange={(e) => setRegisterForm({...registerForm, business_name: e.target.value})}
                      className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
                    />
                  </div>
                  <div>
                    <label htmlFor="register-business-address" className="block text-sm font-medium text-gray-700">
                      Адрес *
                    </label>
                    <input
                      id="register-business-address"
                      type="text"
                      required
                      value={registerForm.business_address}
                      onChange={(e) => setRegisterForm({...registerForm, business_address: e.target.value})}
                      placeholder="Например: 123 Main St"
                      className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label htmlFor="register-business-city" className="block text-sm font-medium text-gray-700">
                        Город *
                      </label>
                      <input
                        id="register-business-city"
                        type="text"
                        required
                        value={registerForm.business_city}
                        onChange={(e) => setRegisterForm({...registerForm, business_city: e.target.value})}
                        className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
                      />
                    </div>
                    <div>
                      <label htmlFor="register-business-country" className="block text-sm font-medium text-gray-700">
                        Страна
                      </label>
                      <input
                        id="register-business-country"
                        list="business-country-options"
                        value={registerForm.business_country}
                        onChange={(e) =>
                          setRegisterForm({ ...registerForm, business_country: e.target.value })
                        }
                        placeholder="Начните вводить название страны"
                        className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
                      />
                      <datalist id="business-country-options">
                        {COUNTRY_OPTIONS.map((country) => (
                          <option key={country} value={country} />
                        ))}
                      </datalist>
                      <p className="mt-1 text-xs text-gray-500">
                        Можно выбрать из списка или вписать страну вручную.
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              <Button
                type="submit"
                className="w-full"
                disabled={loading}
              >
                {loading ? (isRu ? 'Регистрация...' : 'Registering...') : (isRu ? 'Зарегистрироваться' : 'Sign up')}
              </Button>
              <p className="text-xs text-gray-500 text-center">
                {isRu
                  ? 'После регистрации вам будет предложено выбрать тариф и оплатить подписку'
                  : 'After registration you will be able to choose a plan and pay for your subscription.'}
              </p>
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
