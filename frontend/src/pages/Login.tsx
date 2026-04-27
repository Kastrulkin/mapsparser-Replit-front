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
  const [registrationComplete, setRegistrationComplete] = useState(false);
  const navigate = useNavigate();
  const { language } = useLanguage();
  const isRu = language === 'ru';
  const copy = {
    loginTitle: isRu ? 'Вход в систему' : 'Sign in',
    loginSubtitle: isRu ? 'Новые клиенты для вашего бизнеса' : 'New clients for your business',
    loginTab: isRu ? 'Вход' : 'Login',
    registerTab: isRu ? 'Регистрация' : 'Register',
    resetTab: isRu ? 'Восстановление' : 'Reset',
    loginError: isRu ? 'Ошибка входа: ' : 'Sign-in error: ',
    registerError: isRu ? 'Ошибка регистрации: ' : 'Registration error: ',
    registerRequired: isRu ? 'Email и пароль обязательны' : 'Email and password are required',
    businessRequired: isRu ? 'Название бизнеса, адрес и город обязательны' : 'Business name, address, and city are required',
    registerSuccess: isRu ? 'Регистрация прошла успешно. Перенаправляем в личный кабинет...' : 'Registration successful. Redirecting to your dashboard...',
    registerPending: isRu ? 'Регистрация успешна! Ваш бизнес ожидает модерации. Перенаправляем в личный кабинет...' : 'Registration successful. Your business is pending moderation. Redirecting to your dashboard...',
    resetSent: isRu ? 'Инструкции по восстановлению пароля отправлены на email. Проверьте почту!' : 'Password reset instructions were sent to your email.',
    resetError: isRu ? 'Ошибка восстановления пароля: ' : 'Password reset error: ',
    email: 'Email',
    password: isRu ? 'Пароль' : 'Password',
    personalData: isRu ? 'Личные данные' : 'Personal details',
    businessData: isRu ? 'Данные бизнеса' : 'Business details',
    name: isRu ? 'Имя' : 'Name',
    phone: isRu ? 'Телефон' : 'Phone',
    businessName: isRu ? 'Название бизнеса *' : 'Business name *',
    address: isRu ? 'Адрес *' : 'Address *',
    addressPlaceholder: isRu ? 'Например: Невский проспект, 10' : 'Example: 123 Main St',
    city: isRu ? 'Город *' : 'City *',
    country: isRu ? 'Страна' : 'Country',
    countryPlaceholder: isRu ? 'Начните вводить название страны' : 'Start typing a country',
    countryHint: isRu ? 'Можно выбрать из списка или вписать страну вручную.' : 'Choose from the list or enter the country manually.',
    signIn: isRu ? 'Войти' : 'Sign in',
    signingIn: isRu ? 'Вход...' : 'Signing in...',
    signUp: isRu ? 'Зарегистрироваться' : 'Sign up',
    signingUp: isRu ? 'Регистрация...' : 'Registering...',
    postRegisterHint: isRu ? 'После регистрации вам будет предложено выбрать тариф и оплатить подписку' : 'After registration you will be able to choose a plan and pay for your subscription.',
    sendReset: isRu ? 'Восстановить пароль' : 'Reset password',
    sendingReset: isRu ? 'Отправка...' : 'Sending...',
  };

  const looksLikeUrl = (value: string) => {
    const text = value.trim().toLowerCase();
    if (!text) return false;
    return (
      text.includes('://') ||
      text.startsWith('www.') ||
      text.includes('maps.app.goo.gl') ||
      text.includes('yandex.') ||
      text.includes('2gis.') ||
      text.includes('google.com/maps') ||
      text.includes('maps.apple.com')
    );
  };

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
    setRegistrationComplete(false);

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
      setError(copy.loginError + (error as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setInfo(null);
    setRegistrationComplete(false);

    // Валидация
    if (!registerForm.email || !registerForm.password) {
      setError(copy.registerRequired);
      setLoading(false);
      return;
    }

    if (!registerForm.business_name || !registerForm.business_address || !registerForm.business_city) {
      setError(copy.businessRequired);
      setLoading(false);
      return;
    }
    if (looksLikeUrl(registerForm.business_address)) {
      setError(isRu ? 'Поле «Адрес» не должно содержать ссылку на карту' : 'The address field must not contain a map link');
      setLoading(false);
      return;
    }
    if (looksLikeUrl(registerForm.business_city)) {
      setError(isRu ? 'Поле «Город» не должно содержать ссылку на карту' : 'The city field must not contain a map link');
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
        setRegistrationComplete(true);

        // Сохраняем токен
        if (data.token) {
          localStorage.setItem('auth_token', data.token);
        }

        if (tierFromUrl) {
          localStorage.setItem('selectedTier', tierFromUrl);
        }

        // Первый вход должен вести в стартовый first-run сценарий, а не в разрозненные разделы
        const targetUrl = tierFromUrl
          ? `/dashboard/profile?payment=required&tier=${tierFromUrl}`
          : '/dashboard/profile?payment=required';

        if (data.business?.moderation_status === 'pending') {
          setInfo(copy.registerPending);
          setTimeout(() => {
            navigate(targetUrl);
          }, 1500);
        } else {
          setInfo(copy.registerSuccess);
          setTimeout(() => {
            navigate(targetUrl);
          }, 1200);
        }
      } else {
        setError(data.error || (isRu ? 'Ошибка регистрации' : 'Registration failed'));
      }
    } catch (error) {
      setError(copy.registerError + (error as Error).message);
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
        setInfo(copy.resetSent);
      } else {
        setError(data.error || (isRu ? 'Ошибка восстановления пароля' : 'Password reset failed'));
      }
    } catch (error) {
      setError(copy.resetError + (error as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        <div>
          <h2 className="mt-6 text-center text-3xl font-extrabold text-gray-900">
            {copy.loginTitle}
          </h2>
          <p className="mt-2 text-center text-sm text-gray-600">
            {copy.loginSubtitle}
          </p>
        </div>

        <div className="bg-white py-8 px-4 shadow sm:rounded-lg sm:px-10">
          {/* Табы */}
          <div className="flex space-x-1 mb-6">
            <button
              onClick={() => setTab('login')}
              className={`flex-1 py-2 px-4 text-sm font-medium rounded-md ${tab === 'login'
                  ? 'bg-indigo-100 text-indigo-700'
                  : 'text-gray-500 hover:text-gray-700'
                }`}
            >
              {copy.loginTab}
            </button>
            <button
              onClick={() => setTab('register')}
              className={`flex-1 py-2 px-4 text-sm font-medium rounded-md ${tab === 'register'
                  ? 'bg-indigo-100 text-indigo-700'
                  : 'text-gray-500 hover:text-gray-700'
                }`}
            >
              {copy.registerTab}
            </button>
            <button
              onClick={() => setTab('reset')}
              className={`flex-1 py-2 px-4 text-sm font-medium rounded-md ${tab === 'reset'
                  ? 'bg-indigo-100 text-indigo-700'
                  : 'text-gray-500 hover:text-gray-700'
                }`}
            >
              {copy.resetTab}
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
                  {copy.email}
                </label>
                <input
                  id="login-email"
                  type="email"
                  required
                  value={loginForm.email}
                  onChange={(e) => setLoginForm({ ...loginForm, email: e.target.value })}
                  className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
                />
              </div>
              <div>
                <label htmlFor="login-password" className="block text-sm font-medium text-gray-700">
                  {copy.password}
                </label>
                <input
                  id="login-password"
                  type="password"
                  required
                  value={loginForm.password}
                  onChange={(e) => setLoginForm({ ...loginForm, password: e.target.value })}
                  className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
                />
              </div>
              <Button
                type="submit"
                className="w-full btn-iridescent"
                disabled={loading}
              >
                {loading ? copy.signingIn : copy.signIn}
              </Button>
            </form>
          )}

          {/* Форма регистрации */}
          {tab === 'register' && (
            <form className="space-y-4" onSubmit={handleRegister}>
              <div className="border-b border-gray-200 pb-4">
                <h3 className="text-sm font-medium text-gray-700 mb-3">{copy.personalData}</h3>
                <div className="space-y-4">
                  <div>
                    <label htmlFor="register-name" className="block text-sm font-medium text-gray-700">
                      {copy.name}
                    </label>
                    <input
                      id="register-name"
                      type="text"
                      value={registerForm.name}
                      onChange={(e) => setRegisterForm({ ...registerForm, name: e.target.value })}
                      className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
                    />
                  </div>
                  <div>
                    <label htmlFor="register-email" className="block text-sm font-medium text-gray-700">
                      {copy.email} *
                    </label>
                    <input
                      id="register-email"
                      type="email"
                      required
                      value={registerForm.email}
                      onChange={(e) => setRegisterForm({ ...registerForm, email: e.target.value })}
                      className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
                    />
                  </div>
                  <div>
                    <label htmlFor="register-password" className="block text-sm font-medium text-gray-700">
                      {copy.password} *
                    </label>
                    <input
                      id="register-password"
                      type="password"
                      required
                      value={registerForm.password}
                      onChange={(e) => setRegisterForm({ ...registerForm, password: e.target.value })}
                      className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
                    />
                  </div>
                  <div>
                    <label htmlFor="register-phone" className="block text-sm font-medium text-gray-700">
                      {copy.phone}
                    </label>
                    <input
                      id="register-phone"
                      type="tel"
                      value={registerForm.phone}
                      onChange={(e) => setRegisterForm({ ...registerForm, phone: e.target.value })}
                      className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
                    />
                  </div>
                </div>
              </div>

              <div className="border-b border-gray-200 pb-4">
                <h3 className="text-sm font-medium text-gray-700 mb-3">{copy.businessData}</h3>
                <div className="space-y-4">
                  <div>
                    <label htmlFor="register-business-name" className="block text-sm font-medium text-gray-700">
                      {copy.businessName}
                    </label>
                    <input
                      id="register-business-name"
                      type="text"
                      required
                      value={registerForm.business_name}
                      onChange={(e) => setRegisterForm({ ...registerForm, business_name: e.target.value })}
                      className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
                    />
                  </div>
                  <div>
                    <label htmlFor="register-business-address" className="block text-sm font-medium text-gray-700">
                      {copy.address}
                    </label>
                    <input
                      id="register-business-address"
                      type="text"
                      required
                      value={registerForm.business_address}
                      onChange={(e) => setRegisterForm({ ...registerForm, business_address: e.target.value })}
                      placeholder={copy.addressPlaceholder}
                      className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label htmlFor="register-business-city" className="block text-sm font-medium text-gray-700">
                        {copy.city}
                      </label>
                      <input
                        id="register-business-city"
                        type="text"
                        required
                        value={registerForm.business_city}
                        onChange={(e) => setRegisterForm({ ...registerForm, business_city: e.target.value })}
                        className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
                      />
                    </div>
                    <div>
                      <label htmlFor="register-business-country" className="block text-sm font-medium text-gray-700">
                        {copy.country}
                      </label>
                      <input
                        id="register-business-country"
                        list="business-country-options"
                        value={registerForm.business_country}
                        onChange={(e) =>
                          setRegisterForm({ ...registerForm, business_country: e.target.value })
                        }
                        placeholder={copy.countryPlaceholder}
                        className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
                      />
                      <datalist id="business-country-options">
                        {COUNTRY_OPTIONS.map((country) => (
                          <option key={country} value={country} />
                        ))}
                      </datalist>
                      <p className="mt-1 text-xs text-gray-500">
                        {copy.countryHint}
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
                {loading ? copy.signingUp : copy.signUp}
              </Button>
              {registrationComplete && (
                <div className="rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
                  {info || copy.registerSuccess}
                </div>
              )}
              <p className="text-xs text-gray-500 text-center">
                {copy.postRegisterHint}
              </p>
            </form>
          )}

          {/* Форма восстановления пароля */}
          {tab === 'reset' && (
            <form className="space-y-6" onSubmit={handleResetPassword}>
              <div>
                <label htmlFor="reset-email" className="block text-sm font-medium text-gray-700">
                  {copy.email}
                </label>
                <input
                  id="reset-email"
                  type="email"
                  required
                  value={registerForm.email}
                  onChange={(e) => setRegisterForm({ ...registerForm, email: e.target.value })}
                  className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
                />
              </div>
              <Button
                type="submit"
                className="w-full"
                disabled={loading}
              >
                {loading ? copy.sendingReset : copy.sendReset}
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
