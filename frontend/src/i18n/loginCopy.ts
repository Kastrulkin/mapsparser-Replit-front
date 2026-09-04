import type { Language } from './LanguageContext';

type LoginCopy = {
  loginTitle: string;
  registerTitle: string;
  resetTitle: string;
  journeyTitle: string;
  loginSubtitle: string;
  loginTab: string;
  registerTab: string;
  resetTab: string;
  loginError: string;
  registerError: string;
  registrationFailed: string;
  registerRequired: string;
  businessRequired: string;
  consentRequired: string;
  consentText: string;
  policyLabel: string;
  registerSuccess: string;
  registerPending: string;
  resetSent: string;
  resetError: string;
  resetFailed: string;
  email: string;
  password: string;
  personalData: string;
  businessData: string;
  name: string;
  phone: string;
  businessName: string;
  address: string;
  addressPlaceholder: string;
  city: string;
  country: string;
  countryPlaceholder: string;
  countryHint: string;
  signIn: string;
  signingIn: string;
  signUp: string;
  signingUp: string;
  postRegisterHint: string;
  checkEmailHint: string;
  resendVerification: string;
  resendVerificationDone: string;
  resendVerificationFailed: string;
  sendReset: string;
  sendingReset: string;
  mapLinkAddressError: string;
  mapLinkCityError: string;
  journeyResultTitle: string;
  journeyResultText: string;
};

const ru: LoginCopy = {
  loginTitle: 'Вход в систему', registerTitle: 'Регистрация', resetTitle: 'Восстановление пароля', journeyTitle: 'Завершите первое действие', loginSubtitle: 'Новые клиенты для вашего бизнеса',
  loginTab: 'Вход', registerTab: 'Регистрация', resetTab: 'Восстановление', loginError: 'Ошибка входа: ', registerError: 'Ошибка регистрации: ', registrationFailed: 'Ошибка регистрации',
  registerRequired: 'Email и пароль обязательны', businessRequired: 'Название бизнеса, адрес и город обязательны', consentRequired: 'Нужно согласие на обработку персональных данных',
  consentText: 'Я согласен на обработку персональных данных и принимаю политику сервиса', policyLabel: 'Политика обработки персональных данных',
  registerSuccess: 'Регистрация почти завершена. Проверьте почту и подтвердите email.', registerPending: 'Бизнес создан и ожидает модерации. Осталось подтвердить email по письму.',
  resetSent: 'Инструкции по восстановлению пароля отправлены на email. Проверьте почту!', resetError: 'Ошибка восстановления пароля: ', resetFailed: 'Ошибка восстановления пароля',
  email: 'Email', password: 'Пароль', personalData: 'Личные данные', businessData: 'Данные бизнеса', name: 'Имя', phone: 'Телефон', businessName: 'Название бизнеса *',
  address: 'Адрес *', addressPlaceholder: 'Например: Невский проспект, 10', city: 'Город *', country: 'Страна', countryPlaceholder: 'Начните вводить название страны',
  countryHint: 'Можно выбрать из списка или вписать страну вручную.', signIn: 'Войти', signingIn: 'Вход...', signUp: 'Зарегистрироваться', signingUp: 'Регистрация...',
  postRegisterHint: 'После подтверждения email откроется кабинет: можно заполнить профиль и добавить ссылку на компанию. Платные действия включаются отдельно.',
  checkEmailHint: 'Мы отправили письмо со ссылкой подтверждения. После подтверждения email вы автоматически войдёте в кабинет без оплаты.',
  resendVerification: 'Отправить письмо ещё раз', resendVerificationDone: 'Письмо подтверждения отправлено повторно.', resendVerificationFailed: 'Не удалось отправить письмо повторно',
  sendReset: 'Восстановить пароль', sendingReset: 'Отправка...', mapLinkAddressError: 'Поле «Адрес» не должно содержать ссылку на карту', mapLinkCityError: 'Поле «Город» не должно содержать ссылку на карту',
  journeyResultTitle: 'Выбранное направление сохранено', journeyResultText: 'После регистрации откроется нужный раздел LocalOS.',
};

const en: LoginCopy = {
  loginTitle: 'Sign in', registerTitle: 'Create an account', resetTitle: 'Reset your password', journeyTitle: 'Complete your first action', loginSubtitle: 'New clients for your business',
  loginTab: 'Login', registerTab: 'Register', resetTab: 'Reset', loginError: 'Sign-in error: ', registerError: 'Registration error: ', registrationFailed: 'Registration failed',
  registerRequired: 'Email and password are required', businessRequired: 'Business name, address, and city are required', consentRequired: 'Personal data consent is required',
  consentText: 'I agree to personal data processing and accept the service policy', policyLabel: 'Personal data policy',
  registerSuccess: 'Registration is almost complete. Check your email and confirm it.', registerPending: 'Your business is pending moderation. Confirm your email to continue.',
  resetSent: 'Password reset instructions were sent to your email.', resetError: 'Password reset error: ', resetFailed: 'Password reset failed',
  email: 'Email', password: 'Password', personalData: 'Personal details', businessData: 'Business details', name: 'Name', phone: 'Phone', businessName: 'Business name *',
  address: 'Address *', addressPlaceholder: 'Example: 123 Main St', city: 'City *', country: 'Country', countryPlaceholder: 'Start typing a country',
  countryHint: 'Choose from the list or enter the country manually.', signIn: 'Sign in', signingIn: 'Signing in...', signUp: 'Sign up', signingUp: 'Registering...',
  postRegisterHint: 'After email confirmation you can fill in your profile and add a company link. Paid actions are enabled separately.',
  checkEmailHint: 'We sent a confirmation link. After confirming the email you will be signed in without payment.',
  resendVerification: 'Send email again', resendVerificationDone: 'Confirmation email was sent again.', resendVerificationFailed: 'Could not resend the email',
  sendReset: 'Reset password', sendingReset: 'Sending...', mapLinkAddressError: 'The address field must not contain a map link', mapLinkCityError: 'The city field must not contain a map link',
  journeyResultTitle: 'Your chosen direction is saved', journeyResultText: 'The relevant LocalOS section will open after registration.',
};

const es: LoginCopy = {
  loginTitle: 'Iniciar sesión', registerTitle: 'Crea tu cuenta', resetTitle: 'Recupera tu contraseña', journeyTitle: 'Completa el primer paso', loginSubtitle: 'Más clientes para tu negocio',
  loginTab: 'Acceso', registerTab: 'Registro', resetTab: 'Recuperar', loginError: 'Error al iniciar sesión: ', registerError: 'Error al registrarse: ', registrationFailed: 'No se pudo completar el registro',
  registerRequired: 'El email y la contraseña son obligatorios', businessRequired: 'El nombre del negocio, la dirección y la ciudad son obligatorios', consentRequired: 'Debes aceptar el tratamiento de datos personales',
  consentText: 'Acepto el tratamiento de mis datos personales y la política del servicio', policyLabel: 'Política de tratamiento de datos personales',
  registerSuccess: 'El registro está casi terminado. Revisa tu email y confírmalo.', registerPending: 'El negocio está pendiente de moderación. Confirma tu email para continuar.',
  resetSent: 'Te hemos enviado por email las instrucciones para recuperar la contraseña.', resetError: 'Error al recuperar la contraseña: ', resetFailed: 'No se pudo recuperar la contraseña',
  email: 'Email', password: 'Contraseña', personalData: 'Datos personales', businessData: 'Datos del negocio', name: 'Nombre', phone: 'Teléfono', businessName: 'Nombre del negocio *',
  address: 'Dirección *', addressPlaceholder: 'Ejemplo: Gran Vía, 10', city: 'Ciudad *', country: 'País', countryPlaceholder: 'Empieza a escribir un país',
  countryHint: 'Elige un país de la lista o escríbelo.', signIn: 'Entrar', signingIn: 'Entrando...', signUp: 'Registrarse', signingUp: 'Registrando...',
  postRegisterHint: 'Después de confirmar el email podrás completar el perfil y añadir el enlace de tu negocio. Las funciones de pago se activan por separado.',
  checkEmailHint: 'Te hemos enviado un enlace de confirmación. Después de confirmar el email entrarás automáticamente en el panel.',
  resendVerification: 'Volver a enviar el email', resendVerificationDone: 'El email de confirmación se ha enviado de nuevo.', resendVerificationFailed: 'No se pudo volver a enviar el email',
  sendReset: 'Recuperar contraseña', sendingReset: 'Enviando...', mapLinkAddressError: 'El campo «Dirección» no debe contener un enlace a un mapa', mapLinkCityError: 'El campo «Ciudad» no debe contener un enlace a un mapa',
  journeyResultTitle: 'Hemos guardado la dirección elegida', journeyResultText: 'Después del registro se abrirá la sección correspondiente de LocalOS.',
};

export const loginCopyFor = (language: Language): LoginCopy => {
  if (language === 'ru') return ru;
  if (language === 'es') return es;
  return en;
};

export const countryOptionsFor = (language: Language): string[] => {
  if (language === 'es') return ['Rusia', 'España', 'Estados Unidos', 'Ucrania', 'Kazajistán', 'Bielorrusia', 'Alemania', 'Francia', 'Italia', 'Turquía', 'Emiratos Árabes Unidos', 'Israel', 'Polonia', 'Chequia', 'Letonia', 'Lituania', 'Estonia', 'Canadá', 'Reino Unido', 'Australia', 'Suiza', 'Serbia', 'Georgia', 'Armenia', 'Kirguistán', 'Uzbekistán', 'Tayikistán', 'Azerbaiyán'];
  if (language === 'ru') return ['Россия', 'США', 'Украина', 'Казахстан', 'Беларусь', 'Германия', 'Франция', 'Испания', 'Италия', 'Турция', 'ОАЭ', 'Израиль', 'Польша', 'Чехия', 'Латвия', 'Литва', 'Эстония', 'Канада', 'Великобритания', 'Австралия', 'Швейцария', 'Сербия', 'Грузия', 'Армения', 'Кыргызстан', 'Узбекистан', 'Таджикистан', 'Азербайджан'];
  return ['Russia', 'United States', 'Ukraine', 'Kazakhstan', 'Belarus', 'Germany', 'France', 'Spain', 'Italy', 'Türkiye', 'United Arab Emirates', 'Israel', 'Poland', 'Czechia', 'Latvia', 'Lithuania', 'Estonia', 'Canada', 'United Kingdom', 'Australia', 'Switzerland', 'Serbia', 'Georgia', 'Armenia', 'Kyrgyzstan', 'Uzbekistan', 'Tajikistan', 'Azerbaijan'];
};
