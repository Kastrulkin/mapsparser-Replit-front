import type { Language } from './LanguageContext';
import { growthPathsCopyFor } from './growthPathsCopy';
import type { LeadJourneyDirection } from '@/lib/leadJourney';

export type PublicLeadJourneyCopy = {
  seoTitle: string;
  seoDescription: string;
  loading: string;
  unavailableTitle: string;
  unavailableBack: string;
  allDirections: string;
  home: string;
  eyebrow: string;
  title: string;
  intro: string;
  customers: string;
  customersIntro: string;
  work: string;
  moreOptions: string;
  secondary: string;
  defaultChoice: string;
  resultPreview: string;
  howItWorks: string;
  processRoles: string;
  businessRoleTitle: string;
  localosRoleTitle: string;
  publicExample: string;
  continueTitle: string;
  continueText: string;
  continueButton: string;
  recommendedMechanic: string;
  openDirection: string;
  openDirectionText: string;
  approvalNote: string;
  otherTitle: string;
  otherText: string;
  prepareError: string;
  genericSteps: Array<{ title: string; description: string }>;
  businessRole: string;
  localosRole: string;
  prepareLabel: string;
  directionResultTitle: string;
  directionResultPreview: string[];
  lockedResult: string;
};

const ru: PublicLeadJourneyCopy = {
  seoTitle: 'Шесть направлений LocalOS для бизнеса',
  seoDescription: 'Выберите одно из шести направлений: авторы, бизнесы рядом, карты, контент, средний чек или автоматизация.',
  loading: 'Загружаем персональные возможности…', unavailableTitle: 'Персональная ссылка недоступна', unavailableBack: 'Вернуться на LocalOS',
  allDirections: 'Все направления', home: 'На главную', eyebrow: '6 направлений', title: 'Выберите направление',
  intro: 'Откройте направление, чтобы увидеть, как оно работает и с чего начать.', customers: 'Клиенты', customersIntro: 'Авторы, бизнесы рядом и карты.', work: 'Контент и автоматизация',
  moreOptions: 'Ещё вариантов:', secondary: 'Доступно для исследования после регистрации', defaultChoice: 'Посмотреть возможность', resultPreview: 'Это превью состава результата, а не уже выполненная работа.',
  howItWorks: 'Как это работает', processRoles: 'Роли в процессе', businessRoleTitle: 'Что делает бизнес', localosRoleTitle: 'Что делает LocalOS', publicExample: 'Посмотреть публичный пример',
  continueTitle: 'Продолжить с этим направлением', continueText: 'После регистрации откроется нужный раздел. Сначала вы заполните данные бизнеса и увидите кандидатов или проверку — без автоматической отправки и публикации.', continueButton: 'Продолжить в LocalOS',
  recommendedMechanic: 'Рекомендуемая механика', openDirection: 'Открыть выбранное направление', openDirectionText: 'Создайте бизнес-профиль. Выбор сохранится, а кабинет откроет нужный раздел.',
  approvalNote: 'Внешние отправки и изменения остаются под ручным подтверждением.', otherTitle: 'Что ещё можно улучшить', otherText: 'Другие области можно посмотреть позже — выбранное действие сохранится.', prepareError: 'Не удалось подготовить результат',
  genericSteps: [], businessRole: '', localosRole: '', prepareLabel: '', directionResultTitle: '', directionResultPreview: [], lockedResult: '',
};

const en: PublicLeadJourneyCopy = {
  seoTitle: 'Six LocalOS directions for your business',
  seoDescription: 'Choose one of six directions: local creators, nearby businesses, listings, content, average ticket, or automation.',
  loading: 'Loading your opportunities…', unavailableTitle: 'This personal link is unavailable', unavailableBack: 'Back to LocalOS',
  allDirections: 'All directions', home: 'Back to home', eyebrow: '6 directions', title: 'Choose a direction',
  intro: 'Open a direction to see how it works and where to start.', customers: 'Customers', customersIntro: 'Local creators, nearby businesses, and listings.', work: 'Content and automation',
  moreOptions: 'More options:', secondary: 'Available to explore after registration', defaultChoice: 'View opportunity', resultPreview: 'This is a preview of what the result contains, not completed work.',
  howItWorks: 'How it works', processRoles: 'Roles in the process', businessRoleTitle: 'What your business does', localosRoleTitle: 'What LocalOS does', publicExample: 'View a public example',
  continueTitle: 'Continue with this direction', continueText: 'After registration, LocalOS opens the relevant workspace. Nothing is sent or published automatically.', continueButton: 'Continue in LocalOS',
  recommendedMechanic: 'Recommended approach', openDirection: 'Open the selected direction', openDirectionText: 'Create a business profile. LocalOS will save your choice and open the right workspace.',
  approvalNote: 'External messages and changes still require your approval.', otherTitle: 'What else you can improve', otherText: 'You can review other areas later. Your selected action will stay saved.', prepareError: 'Could not prepare the result',
  genericSteps: [
    { title: 'Add the business context', description: 'Provide only the details needed to review this direction.' },
    { title: 'Review the prepared result', description: 'LocalOS shows the candidates, checks, or draft before anything is used.' },
    { title: 'Approve the next step', description: 'External messages, publications, and changes wait for your confirmation.' },
  ],
  businessRole: 'You choose the direction, review the prepared result, and approve any external action.',
  localosRole: 'LocalOS checks the available data, prepares a useful next step, and keeps the result in one workspace.',
  prepareLabel: 'Show a personal preview', directionResultTitle: 'Your preview is ready',
  directionResultPreview: ['A clear first step', 'The evidence used for the recommendation', 'The next action waiting for your review'],
  lockedResult: 'Create a business profile to open the full result.',
};

const es: PublicLeadJourneyCopy = {
  seoTitle: 'Seis direcciones de LocalOS para tu negocio',
  seoDescription: 'Elige una de seis direcciones: creadores locales, negocios cercanos, fichas, contenido, ticket medio o automatización.',
  loading: 'Cargando tus oportunidades…', unavailableTitle: 'Este enlace personal no está disponible', unavailableBack: 'Volver a LocalOS',
  allDirections: 'Todas las direcciones', home: 'Volver al inicio', eyebrow: '6 direcciones', title: 'Elige una dirección',
  intro: 'Abre una dirección para ver cómo funciona y por dónde empezar.', customers: 'Clientes', customersIntro: 'Creadores locales, negocios cercanos y fichas.', work: 'Contenido y automatización',
  moreOptions: 'Más opciones:', secondary: 'Disponible para explorar después de registrarte', defaultChoice: 'Ver oportunidad', resultPreview: 'Esta es una vista previa del resultado, no un trabajo ya realizado.',
  howItWorks: 'Cómo funciona', processRoles: 'Funciones en el proceso', businessRoleTitle: 'Qué hace tu negocio', localosRoleTitle: 'Qué hace LocalOS', publicExample: 'Ver un ejemplo público',
  continueTitle: 'Continuar con esta dirección', continueText: 'Después del registro, LocalOS abrirá el espacio adecuado. Nada se envía ni se publica automáticamente.', continueButton: 'Continuar en LocalOS',
  recommendedMechanic: 'Enfoque recomendado', openDirection: 'Abrir la dirección elegida', openDirectionText: 'Crea un perfil de negocio. LocalOS guardará tu elección y abrirá el espacio adecuado.',
  approvalNote: 'Los mensajes externos y los cambios siguen requiriendo tu aprobación.', otherTitle: 'Qué más puedes mejorar', otherText: 'Puedes revisar otras áreas más tarde. La acción elegida quedará guardada.', prepareError: 'No se pudo preparar el resultado',
  genericSteps: [
    { title: 'Añade el contexto del negocio', description: 'Indica solo los datos necesarios para revisar esta dirección.' },
    { title: 'Revisa el resultado preparado', description: 'LocalOS muestra los candidatos, comprobaciones o borradores antes de usarlos.' },
    { title: 'Aprueba el siguiente paso', description: 'Los mensajes, publicaciones y cambios externos esperan tu confirmación.' },
  ],
  businessRole: 'Eliges la dirección, revisas el resultado preparado y apruebas cualquier acción externa.',
  localosRole: 'LocalOS comprueba los datos disponibles, prepara un siguiente paso útil y guarda el resultado en un solo espacio.',
  prepareLabel: 'Mostrar una vista previa personal', directionResultTitle: 'Tu vista previa está lista',
  directionResultPreview: ['Un primer paso claro', 'Las pruebas usadas para la recomendación', 'La siguiente acción pendiente de tu revisión'],
  lockedResult: 'Crea un perfil de negocio para abrir el resultado completo.',
};

export const publicLeadJourneyCopyFor = (language: Language): PublicLeadJourneyCopy => {
  if (language === 'ru') return ru;
  if (language === 'es') return es;
  return en;
};

export const localizePublicLeadJourneyDirections = (
  directions: LeadJourneyDirection[],
  language: Language,
): LeadJourneyDirection[] => {
  if (language === 'ru') return directions;
  const pageCopy = publicLeadJourneyCopyFor(language);
  const directionCopy = growthPathsCopyFor(language).directions;
  return directions.map((direction) => {
    const flowKey = direction.key === 'influencers' ? 'influencer' : direction.key === 'partnerships' ? 'partnership' : direction.key;
    const localized = directionCopy[flowKey];
    return {
      ...direction,
      eyebrow: localized.title,
      title: localized.title,
      preview: localized.description,
      choiceCta: localized.cta,
      detailTitle: localized.title,
      detail: localized.description,
      steps: pageCopy.genericSteps,
      detailSections: undefined,
      continueTitle: pageCopy.continueTitle,
      continueText: pageCopy.continueText,
      today: { title: localized.title, description: localized.description, cta: localized.cta },
      businessRole: pageCopy.businessRole,
      localosRole: pageCopy.localosRole,
      prepareLabel: pageCopy.prepareLabel,
      resultTitle: pageCopy.directionResultTitle,
      resultPreview: pageCopy.directionResultPreview,
      lockedResult: pageCopy.lockedResult,
    };
  });
};
