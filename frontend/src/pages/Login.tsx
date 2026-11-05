import { rememberMaxConnection, consumeMaxConnection } from "@/lib/maxAuthContinuation";
import { featureFlags } from '@/config/featureFlags';
import { useLanguage } from '@/i18n/LanguageContext.logic';
import { countryOptionsFor, loginCopyFor } from '@/i18n/loginCopy';
import { clearLeadJourneyIntent, clearLeadJourneyToken, getLeadJourneyDirection, isLeadJourneyKey, resolveStoredLeadJourney, saveLeadJourneyIntent, saveLeadJourneyToken } from "@/lib/leadJourney";
import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import Footer from "../components/Footer";
import { Button } from "../components/ui/button";
import { newAuth } from "../lib/auth_new";

const Login = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const { language } = useLanguage();
  const copy = loginCopyFor(language);
  const countryOptions = countryOptionsFor(language);

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
    business_country: countryOptions[0],
    personal_data_consent: false,
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [registrationReceipt, setRegistrationReceipt] = useState<{
    email: string;
    businessName: string;
    emailSent: boolean;
    pending: boolean;
  } | null>(null);
  const [unavailableJourney, setUnavailableJourney] = useState(false);
  const [skipJourney, setSkipJourney] = useState(false);
  const [resendingVerification, setResendingVerification] = useState(false);
  const errorRef = useRef<HTMLDivElement>(null);
  const receiptRef = useRef<HTMLElement>(null);
  const navigate = useNavigate();

  useEffect(() => {
    const target = error ? errorRef.current : registrationReceipt ? receiptRef.current : null;
    target?.focus({ preventScroll: true });
    target?.scrollIntoView?.({ block: 'start' });
  }, [error, registrationReceipt]);
  const journeyParam = searchParams.get('journey');
  const journeyTokenParam = searchParams.get('journey_token') || '';
  const journey = getLeadJourneyDirection(isLeadJourneyKey(journeyParam) ? journeyParam : null);
  const tabButtonClass = "min-h-10 min-w-0 flex-1 rounded-md px-2 py-2 text-xs sm:px-4 sm:text-sm font-medium transition-[background-color,color,box-shadow,transform] duration-150 ease-out focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-500 focus-visible:ring-offset-2 active:scale-[0.96] motion-reduce:transition-none motion-reduce:active:scale-100";

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
    const source = searchParams.get('source');

    if (initialTab === 'register') {
      setTab('register');
    }

    if (searchParams.get('return_to') === '/dashboard/max') rememberMaxConnection();
    if (isLeadJourneyKey(journeyParam)) {
      saveLeadJourneyIntent(journeyParam);
    }
    if (journeyTokenParam) saveLeadJourneyToken(journeyTokenParam);

    if (tierFromUrl) {
      // Запоминаем выбранный тариф для последующего редиректа на оплату
      localStorage.setItem('selectedTier', tierFromUrl);
      if (source === 'pricing') {
        localStorage.setItem('selectedTierSource', 'pricing');
      }
    }

    if (source === 'public_audit' || source === 'lead_journey') {
      const nextBusinessName = searchParams.get('business_name') || '';
      const nextBusinessAddress = searchParams.get('business_address') || '';
      const nextBusinessCity = searchParams.get('business_city') || '';
      const nextBusinessCountry = searchParams.get('business_country') || '';
      setRegisterForm((current) => ({
        ...current,
        business_name: nextBusinessName || current.business_name,
        business_address: nextBusinessAddress || current.business_address,
        business_city: nextBusinessCity || current.business_city,
        business_country: nextBusinessCountry || current.business_country,
      }));
    }
  }, [journeyParam, journeyTokenParam, searchParams]);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setInfo(null);
    // A plain sign-in must not resume a different visit's saved offer.
    if (!journeyTokenParam) {
      clearLeadJourneyToken();
      if (!journey) clearLeadJourneyIntent();
    }

    try {
      const { user, error } = await newAuth.signIn(loginForm.email, loginForm.password);

      if (error) {
        if (error.includes('NEED_PASSWORD')) {
          // Пользователь существует, но не установил пароль
          navigate('/set-password', { state: { email: loginForm.email } });
        } else if (error.includes('EMAIL_NOT_VERIFIED')) {
          setError(language === 'ru' ? 'Email не подтверждён. Проверьте почту или запросите письмо ещё раз.' : language === 'es' ? 'El email no está confirmado. Revisa tu bandeja o solicita otro mensaje.' : 'Email is not verified. Check your inbox or request another email.');
        } else {
          setError(error);
        }
      } else if (user) {
        const tierFromUrl = searchParams.get('tier');
        const source = searchParams.get('source');

        if (consumeMaxConnection() || searchParams.get("return_to") === "/dashboard/max") {
          navigate('/dashboard/max');
        } else if (journeyTokenParam && featureFlags.journeyPostAuthRedirect) {
          try {
            const resolved = await resolveStoredLeadJourney();
            navigate(resolved?.route || '/dashboard/today');
          } catch (journeyError) {
            setError(language === 'ru' ? `Вход выполнен, но выбранное направление пока не открылось: ${journeyError instanceof Error ? journeyError.message : 'повторите попытку'}` : language === 'es' ? 'Has iniciado sesión, pero la dirección elegida no se ha podido abrir. Inténtalo de nuevo.' : 'Signed in, but the chosen direction could not be opened yet. Please retry.');
          }
        } else if (tierFromUrl && source === 'pricing') {
          localStorage.setItem('selectedTier', tierFromUrl);
          localStorage.setItem('selectedTierSource', 'pricing');
          navigate(`/dashboard/profile?payment=required&source=pricing&autostart=1&tier=${tierFromUrl}#subscription`);
        } else {
          navigate('/dashboard');
        }
      }
    } catch (error) {
      setError(copy.loginError + (error instanceof Error ? error.message : String(error)));
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    if (loading || registrationReceipt) return;
    setUnavailableJourney(false);
    const registrationJourneyToken = skipJourney ? '' : journeyTokenParam;
    // Only the current URL may opt registration into a personal offer. History
    // from localStorage must never block plain registration or email confirmation.
    if (!registrationJourneyToken) {
      clearLeadJourneyToken();
      if (!journey) clearLeadJourneyIntent();
    }
    setLoading(true);
    setError(null);
    setInfo(null);

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
    if (!registerForm.personal_data_consent) {
      setError(copy.consentRequired);
      setLoading(false);
      return;
    }
    if (looksLikeUrl(registerForm.business_address)) {
      setError(copy.mapLinkAddressError);
      setLoading(false);
      return;
    }
    if (looksLikeUrl(registerForm.business_city)) {
      setError(copy.mapLinkCityError);
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
          business_country: registerForm.business_country,
          personal_data_consent: registerForm.personal_data_consent,
          consent_version: 'localos-personal-data-v1-2026-05-11',
          source: searchParams.get('source') || undefined,
          audit_slug: searchParams.get('audit_slug') || undefined,
          audit_public_url: searchParams.get('audit_slug')
            ? `${window.location.origin}/${searchParams.get('audit_slug') || ''}`
            : undefined,
          journey_token: registrationJourneyToken || undefined,
        })
      });

      const data = await response.json();

      if (response.ok && data.success) {
        setRegistrationReceipt({
          email: data.user?.email || registerForm.email.trim(),
          businessName: data.business?.name || registerForm.business_name.trim(),
          emailSent: data.email_sent === true,
          pending: data.business?.moderation_status === 'pending',
        });
        setRegisterForm((current) => ({ ...current, password: '' }));
      } else {
        setError(data.error || copy.registrationFailed);
        setUnavailableJourney(['journey_expired', 'journey_revoked', 'journey_not_found'].includes(data.code));
      }
    } catch (error) {
      setError(copy.registerError + (error instanceof Error ? error.message : String(error)));
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
        setError(data.error || copy.resetFailed);
      }
    } catch (error) {
      setError(copy.resetError + (error instanceof Error ? error.message : String(error)));
    } finally {
      setLoading(false);
    }
  };

  const handleResendVerification = async () => {
    if (!registrationReceipt?.email || resendingVerification) {
      return;
    }

    setResendingVerification(true);
    setError(null);
    try {
      const response = await fetch('/api/auth/resend-verification', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: registrationReceipt.email }),
      });
      const data = await response.json();
      if (response.ok && data.success) {
        setRegistrationReceipt((current) => current ? { ...current, emailSent: true } : current);
        setInfo(copy.resendVerificationDone);
      } else {
        setError(data.error || copy.resendVerificationFailed);
      }
    } catch (error) {
      setError(copy.resendVerificationFailed);
    } finally {
      setResendingVerification(false);
    }
  };

  const changeTab = (next: 'login' | 'register' | 'reset') => {
    if (loading || resendingVerification) return;
    setError(null);
    setInfo(null);
    setUnavailableJourney(false);
    setTab(next);
  };

  const continueWithoutJourney = () => {
    clearLeadJourneyToken();
    clearLeadJourneyIntent();
    setSkipJourney(true);
    setUnavailableJourney(false);
    setError(null);
    const nextParams = new URLSearchParams(searchParams);
    nextParams.delete('journey_token');
    nextParams.delete('journey');
    setSearchParams(nextParams, { replace: true });
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      <div className="flex min-h-screen items-center justify-center px-4 py-12 sm:px-6 lg:px-8">
        <div className="max-w-md w-full space-y-8">
        <div>
          <h2 className="mt-6 text-center text-3xl font-extrabold text-gray-900">
            {journey && tab === 'register' ? copy.journeyTitle : tab === 'register' ? copy.registerTitle : tab === 'reset' ? copy.resetTitle : copy.loginTitle}
          </h2>
          <p className="mt-2 text-center text-sm text-gray-600">
            {journey && tab === 'register' ? copy.journeyResultText : copy.loginSubtitle}
          </p>
        </div>

        <div className="bg-white py-8 px-4 shadow sm:rounded-lg sm:px-10">
          {/* Табы */}
          <div className="flex space-x-1 mb-6">
            <button
              type="button"
              aria-pressed={tab === 'login'}
              disabled={loading || resendingVerification}
              onClick={() => changeTab('login')}
              className={`${tabButtonClass} ${tab === 'login'
                  ? 'bg-slate-950 text-white shadow-sm'
                  : 'text-slate-600 hover:bg-slate-100 hover:text-slate-950'
                }`}
            >
              {copy.loginTab}
            </button>
            <button
              type="button"
              aria-pressed={tab === 'register'}
              disabled={loading || resendingVerification}
              onClick={() => changeTab('register')}
              className={`${tabButtonClass} ${tab === 'register'
                  ? 'bg-slate-950 text-white shadow-sm'
                  : 'text-slate-600 hover:bg-slate-100 hover:text-slate-950'
                }`}
            >
              {copy.registerTab}
            </button>
            <button
              type="button"
              aria-pressed={tab === 'reset'}
              disabled={loading || resendingVerification}
              onClick={() => changeTab('reset')}
              className={`${tabButtonClass} ${tab === 'reset'
                  ? 'bg-slate-950 text-white shadow-sm'
                  : 'text-slate-600 hover:bg-slate-100 hover:text-slate-950'
                }`}
            >
              {copy.resetTab}
            </button>
          </div>

          {error && (
            <div ref={errorRef} role="alert" tabIndex={-1} className="mb-4 scroll-mt-24 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
              <p>{error}</p>
              {unavailableJourney && tab === 'register' && (
                <div className="mt-3 space-y-3">
                  <p>{copy.journeyUnavailableHint}</p>
                  <Button type="button" variant="outline" className="h-auto min-h-10 whitespace-normal text-left" onClick={continueWithoutJourney}>
                    {copy.continueWithoutJourney}
                  </Button>
                </div>
              )}
            </div>
          )}

          {info && (
            <div role="status" className="mb-4 bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded">
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
                      autoComplete="username"
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
                      autoComplete="current-password"
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

          {tab === 'register' && registrationReceipt && (
            <section ref={receiptRef} tabIndex={-1} aria-labelledby="registration-complete-title" className="scroll-mt-24 space-y-4">
              <h3 id="registration-complete-title" className="text-lg font-semibold text-gray-900">
                {copy.accountCreated}
              </h3>
              <dl className="space-y-2 break-words text-sm text-gray-700">
                <div><dt className="font-medium">{copy.email}</dt><dd>{registrationReceipt.email}</dd></div>
                <div><dt className="font-medium">{copy.businessData}</dt><dd>{registrationReceipt.businessName}</dd></div>
              </dl>
              {registrationReceipt.emailSent ? (
                <div role="status" className="space-y-2 text-sm text-gray-700">
                  <p>{registrationReceipt.pending ? copy.registerPending : copy.registerSuccess}</p>
                  <p>{copy.checkEmailHint}</p>
                </div>
              ) : (
                <p role="alert" className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                  {copy.emailDeliveryFailed}
                </p>
              )}
              <Button type="button" variant="outline" className="w-full" disabled={resendingVerification} onClick={handleResendVerification}>
                {resendingVerification ? copy.sendingReset : copy.resendVerification}
              </Button>
            </section>
          )}

          {/* Форма регистрации */}
          {tab === 'register' && !registrationReceipt && (
            <form className="space-y-4" onSubmit={handleRegister}>
              {journey ? (
                <div className="rounded-lg border border-orange-200 bg-orange-50 px-4 py-3 text-sm text-slate-700">
                  <strong className="block text-slate-950">{copy.journeyResultTitle}</strong>
                  <span className="mt-1 block leading-5">{copy.journeyResultText}</span>
                </div>
              ) : null}
              <div className="border-b border-gray-200 pb-4">
                <h3 className="text-sm font-medium text-gray-700 mb-3">{copy.personalData}</h3>
                <div className="space-y-4">
                  <div>
                    <label htmlFor="register-name" className="block text-sm font-medium text-gray-700">
                      {copy.name}
                    </label>
                    <input
                      id="register-name"
                      autoComplete="name"
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
                      autoComplete="email"
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
                      autoComplete="new-password"
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
                      autoComplete="tel"
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
                      autoComplete="street-address"
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
                      autoComplete="address-level2"
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
                      autoComplete="country-name"
                        list="business-country-options"
                        value={registerForm.business_country}
                        onChange={(e) =>
                          setRegisterForm({ ...registerForm, business_country: e.target.value })
                        }
                        placeholder={copy.countryPlaceholder}
                        className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
                      />
                      <datalist id="business-country-options">
                        {countryOptions.map((country) => (
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

              <label className="flex items-start gap-3 rounded-md border border-gray-200 bg-white px-3 py-3 text-sm text-gray-700">
                <input
                  type="checkbox"
                  checked={registerForm.personal_data_consent}
                  onChange={(e) => setRegisterForm({ ...registerForm, personal_data_consent: e.target.checked })}
                  className="mt-1 h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                />
                <span>
                  {copy.consentText}{' '}
                  <a className="font-medium text-indigo-600 hover:text-indigo-700" href="/policy" target="_blank" rel="noreferrer">
                    {copy.policyLabel}
                  </a>
                </span>
              </label>

              <Button
                type="submit"
                className="w-full btn-iridescent"
                disabled={loading || !registerForm.personal_data_consent}
              >
                {loading ? copy.signingUp : copy.signUp}
              </Button>
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
                className="w-full btn-iridescent"
                disabled={loading}
              >
                {loading ? copy.sendingReset : copy.sendReset}
              </Button>
            </form>
          )}
        </div>
        </div>
      </div>
      <Footer />
    </div>
  );
};

export default Login;
