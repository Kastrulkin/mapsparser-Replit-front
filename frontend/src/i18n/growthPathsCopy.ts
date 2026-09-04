import type { Language } from './LanguageContext';

type DirectionCopy = { title: string; description: string; cta: string };

type GrowthPathsCopy = {
  eyebrow: string;
  title: string;
  intro: string;
  chooseBusiness: string;
  loading: string;
  loadError: string;
  retry: string;
  emptyTitle: string;
  emptyDescription: string;
  accessTitle: string;
  lockedReason: string;
  lockedCta: string;
  obstacle: string;
  statuses: { payment: string; blocked: string; action: string; available: string };
  directions: Record<string, DirectionCopy>;
};

const ru: GrowthPathsCopy = {
  eyebrow: 'Пути роста', title: 'Выберите направление', intro: 'Выберите, с какой задачей хотите начать. Текущий маршрут всегда будет первым.',
  chooseBusiness: 'Выберите бизнес, чтобы увидеть направления.', loading: 'Загрузка направлений', loadError: 'Не удалось загрузить направления.', retry: 'Повторить',
  emptyTitle: 'Направления пока не загрузились', emptyDescription: 'Обновите страницу или попробуйте ещё раз позже.', accessTitle: 'Что откроется',
  lockedReason: 'Полный раздел доступен на подходящем тарифе.', lockedCta: 'Посмотреть тарифы', obstacle: 'Что мешает:',
  statuses: { payment: 'Нужен другой тариф', blocked: 'Нужно внимание', action: 'Есть следующий шаг', available: 'Можно начать' },
  directions: {
    maps: { title: 'Привести карточки в порядок', description: 'Проверить услуги и цены, фото, рейтинг, отзывы и запись в Яндексе и 2ГИС. Понять, что поправить первым.', cta: 'Проверить карточку' },
    maps_content: { title: 'Привести карточки в порядок', description: 'Проверить услуги и цены, фото, рейтинг, отзывы и запись в Яндексе и 2ГИС. Понять, что поправить первым.', cta: 'Проверить карточку' },
    influencer: { title: 'Найти местных блогеров', description: 'Подобрать авторов рядом, согласовать условия и следить за визитами и публикациями.', cta: 'Посмотреть авторов' },
    partnership: { title: 'Найти бизнесы для взаимных рекомендаций', description: 'Увидеть, с кем рядом можно обмениваться клиентами и какое предложение сделать.', cta: 'Посмотреть бизнесы' },
    content: { title: 'Не думать каждый раз, что публиковать', description: 'Получать темы и черновики из услуг, отзывов и событий бизнеса.', cta: 'Открыть контент' },
    average_ticket: { title: 'Понять, что ещё предложить клиенту', description: 'Увидеть подходящие дополнения и следить, предлагают ли их сотрудники и записывают ли клиента на следующий визит.', cta: 'Посмотреть варианты' },
    automation: { title: 'Снять с себя повторяющиеся задачи', description: 'Выбрать регулярную работу и видеть, что сделано и где требуется ваше решение.', cta: 'Посмотреть задачи' },
  },
};

const en: GrowthPathsCopy = {
  eyebrow: 'Growth paths', title: 'Choose a direction', intro: 'Choose the job you want to start with. Your current path will always appear first.',
  chooseBusiness: 'Choose a business to see the directions.', loading: 'Loading directions', loadError: 'Could not load the directions.', retry: 'Try again',
  emptyTitle: 'The directions have not loaded yet', emptyDescription: 'Refresh the page or try again later.', accessTitle: 'What you will get',
  lockedReason: 'The full section is available on the relevant plan.', lockedCta: 'View plans', obstacle: 'What is getting in the way:',
  statuses: { payment: 'Another plan is required', blocked: 'Needs attention', action: 'Next step ready', available: 'Ready to start' },
  directions: {
    maps: { title: 'Put your listings in order', description: 'Check services and prices, photos, ratings, reviews, and booking links. See what to fix first.', cta: 'Check a listing' },
    maps_content: { title: 'Put your listings in order', description: 'Check services and prices, photos, ratings, reviews, and booking links. See what to fix first.', cta: 'Check a listing' },
    influencer: { title: 'Find local creators', description: 'Find nearby creators, agree on terms, and keep track of visits and posts.', cta: 'View creators' },
    partnership: { title: 'Find businesses for mutual referrals', description: 'See which nearby businesses can exchange referrals with you and what to offer them.', cta: 'View businesses' },
    content: { title: 'Stop wondering what to publish', description: 'Get topics and drafts based on your services, reviews, and business events.', cta: 'Open content' },
    average_ticket: { title: 'See what else to offer each client', description: 'Find relevant add-ons and track whether the team offers them and books the next visit.', cta: 'View options' },
    automation: { title: 'Take repetitive tasks off your plate', description: 'Choose recurring work and see what is done and where your decision is needed.', cta: 'View tasks' },
  },
};

const es: GrowthPathsCopy = {
  eyebrow: 'Rutas de crecimiento', title: 'Elige una dirección', intro: 'Elige la tarea con la que quieres empezar. Tu ruta actual aparecerá siempre primero.',
  chooseBusiness: 'Elige un negocio para ver las direcciones.', loading: 'Cargando direcciones', loadError: 'No se pudieron cargar las direcciones.', retry: 'Reintentar',
  emptyTitle: 'Las direcciones aún no se han cargado', emptyDescription: 'Actualiza la página o inténtalo de nuevo más tarde.', accessTitle: 'Qué se desbloquea',
  lockedReason: 'La sección completa está disponible con el plan correspondiente.', lockedCta: 'Ver planes', obstacle: 'Qué lo impide:',
  statuses: { payment: 'Necesita otro plan', blocked: 'Necesita atención', action: 'Hay un siguiente paso', available: 'Puedes empezar' },
  directions: {
    maps: { title: 'Pon tus fichas al día', description: 'Revisa servicios y precios, fotos, valoración, reseñas y reserva. Descubre qué corregir primero.', cta: 'Revisar una ficha' },
    maps_content: { title: 'Pon tus fichas al día', description: 'Revisa servicios y precios, fotos, valoración, reseñas y reserva. Descubre qué corregir primero.', cta: 'Revisar una ficha' },
    influencer: { title: 'Encuentra creadores locales', description: 'Encuentra creadores cercanos, acuerda las condiciones y sigue las visitas y publicaciones.', cta: 'Ver creadores' },
    partnership: { title: 'Encuentra negocios para recomendaros', description: 'Descubre con qué negocios cercanos puedes intercambiar clientes y qué propuesta hacerles.', cta: 'Ver negocios' },
    content: { title: 'Deja de pensar cada vez qué publicar', description: 'Recibe temas y borradores basados en tus servicios, reseñas y novedades.', cta: 'Abrir contenido' },
    average_ticket: { title: 'Descubre qué más ofrecer a cada cliente', description: 'Encuentra complementos adecuados y comprueba si el equipo los ofrece y reserva la próxima visita.', cta: 'Ver opciones' },
    automation: { title: 'Quita de encima las tareas repetitivas', description: 'Elige el trabajo periódico y comprueba qué está hecho y dónde hace falta tu decisión.', cta: 'Ver tareas' },
  },
};

export const growthPathsCopyFor = (language: Language): GrowthPathsCopy => {
  if (language === 'ru') return ru;
  if (language === 'es') return es;
  return en;
};
